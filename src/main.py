"""
3_auto_generate_label - 多階層影像標註與自動化裁切系統 (Main Entry Point)

本模組為標註工具的主程式進入點，採用 PyQt6 打造，旨在建立一套自動化的「影像標註 -> 裁切 -> 子區塊標註 -> 辨識」流水線。
透過階層式的資料夾結構管理，支援從原始大圖到字元層級的深度標註。

核心專案結構 (Hierarchical Structure):
    Root/
    ├── Original_folder/   [Stage 1: 大區域標註]
    │   ├── Original_img/  <-- 起始圖片 (使用者選取路徑)
    │   └── Box01_label/   <-- YOLO 標註檔 (標籤: Box01)
    ├── Box01_folder/      [Stage 2: 子區塊標註]
    │   ├── Box01_img/     <-- 由 Stage 1 自動裁切產生
    │   └── Box02_label/   <-- YOLO 標註檔 (標籤: Box02)
    └── Box02_folder/      [Stage 3: 字元辨識]
        ├── Box02_img/     <-- 由 Stage 2 自動裁切產生
        └── Number/        <-- 辨識結果與最終標註 (0-9, Dot, minus)



主要功能特性:
    1. 智慧路徑管理: 
       - 採「向上回溯」邏輯，使用者僅需選取 Original_img，系統自動推算 Project Root 並驗證完整階層。
       - 自動初始化：偵測缺失資料夾時，可一鍵生成符合規範的目錄與 classes.txt。
    2. 多模式標註工作流:
       - Offset 自動標註：整合 offset.py，利用特徵偏移量實現批量標註與影像裁切。
       - OCR 輔助標註：針對末端字元階段，整合 EasyOCR 快速填充標籤。
       - 手動修正 (Redraw)：支援互動式矩形框調整，並連動更新後續階段的裁切圖。
    3. 直覺式視覺回饋:
       - 狀態顏色標記：清單即時顯示標註進度 (紅色:未處理, 橘色:已標註未裁切, 綠色:完成)。
       - 快速預覽：支援自動播放預覽、標註框同步顯示與快速鍵 (Enter) 呼叫修正視窗。

依賴組件:
    - PyQt6: 介面驅動與事件處理。
    - utils: 封裝 OpenCV 繪圖、YOLO 格式轉換及跨目錄檔案維護。
    - dialogs: 包含 RedrawDialog, AutoLabelingDialog, OcrEditorDiolog。

作者: shengyuanshaw (Yenprotek)
最後更新日期: 2026/02/24
"""
import sys
import os
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt, QTimer

from editor_diolog import RedrawDialog
from auto_editor_diolog import AutoLabelingDialog
from ocr_editor_diolog import OcrEditorDiolog
from gui import LabelingWindow
from constants import WORKING_MODE, MODE_PATH_MAP
import utils

class LabelerApp(LabelingWindow):
    def __init__(self):
        super().__init__()
        self.root_dir = ""  # 專案根目錄 (由 Original_img 往上推兩層)
        self.img_dir = ""   # 使用者選取的 Original_img
        self.lbl_dir = ""   # 對應的 label
        self.cut_dir = ""   # 對應的 cut_img
        self.image_files = []
        self.current_index = -1
        self.classes = []

        self.auto_timer = QTimer()
        self.auto_timer.timeout.connect(self.next_image)

        # --- 連結動作 ---
        # 注意：雖然按鈕叫 btn_browse_root,但現在邏輯是「選擇圖片夾」
        self.btn_browse_root.clicked.connect(self.handle_browse_Original_images)
        self.label_list.itemClicked.connect(self.handle_image_selection)
        self.btn_next.clicked.connect(self.next_image)
        self.btn_prev.clicked.connect(self.prev_image)
        self.btn_main_action.clicked.connect(self.handle_main_action)

        # 即時連動
        self.check_auto_preview.toggled.connect(self.handle_auto_preview)
        self.spin_interval.valueChanged.connect(self.update_timer_interval)
        self.check_show_boxes.toggled.connect(self.update_display)
        self.combo_mode.currentIndexChanged.connect(self.sync_paths_and_display)

    # --- 1. 關鍵邏輯：由選取的資料夾往上推算根目錄 ---
    def handle_browse_Original_images(self):
        """使用者選擇 Original_img 資料夾"""
        selected_path = QFileDialog.getExistingDirectory(self, "選擇原始圖片資料夾 (Original_img)", "")
        if not selected_path:
            return

        # 檢查選取的資料夾名稱是否正確 (選配,增加防呆)
        if os.path.basename(selected_path) != "Original_img":
            QMessageBox.warning(self, "路徑警告", "建議選取名稱為 'Original_img' 的資料夾以符合預期結構.")

        self.img_dir = selected_path
        # 往上跳兩層： Original_img -> Original_folder -> Root
        self.root_dir = os.path.abspath(os.path.join(selected_path, "../../"))
        self.edit_root_path.setText(selected_path) # 顯示選取的路徑

        # 2. 驗證結構
        if self.validate_structure(self.root_dir):
            self.setup_first_stage()
        else:
            # 3. 若結構不對,詢問是否在該 Root 建立完整結構
            reply = QMessageBox.question(
                self, "建立專案結構", 
                f"偵測到結構不完整.\n系統將以：\n{self.root_dir}\n作為專案根目錄並初始化結構,是否繼續？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.init_structure(self.root_dir)
                if self.validate_structure(self.root_dir):
                    self.setup_first_stage()

    def validate_structure(self, root_path):
        """驗證：Root 下是否有三個 Folder 及其子夾"""
        check_list = [
            ("Original_folder", "Original_img", "Box01_label", ["Box01"]),
            ("Box01_folder",    "Box01_img",    "Box02_label", ["Box02"]),
            ("Box02_folder",    "Box02_img",    "Number",      ["0","1","2","3","4","5","6","7","8","9","Dot","minus"])
        ]

        errors = []
        for stage_f, img_f, lbl_f, expected_cls in check_list:
            stage_p = os.path.join(root_path, stage_f)
            img_p = os.path.join(stage_p, img_f)
            lbl_p = os.path.join(stage_p, lbl_f)
            
            if not os.path.isdir(stage_p): errors.append(f"缺失階段: {stage_f}")
            if not os.path.isdir(img_p): errors.append(f"缺失圖片夾: {img_f}")
            if not os.path.isdir(lbl_p): errors.append(f"缺失標註夾: {lbl_f}")
            
            cls_f = os.path.join(lbl_p, "classes.txt")
            if os.path.isfile(cls_f):
                content = utils.load_classes(lbl_p)
                for cls in expected_cls:
                    if cls not in content: errors.append(f"{lbl_f} 缺少標籤: {cls}")
            else:
                errors.append(f"缺失檔案: {lbl_f}/classes.txt")

        if errors:
            self.lbl_struct_status.setText("❌ 結構錯誤")
            self.lbl_struct_status.setStyleSheet("color: #FF5252;")
            return False
        else:
            self.lbl_struct_status.setText("✅ 專案結構正確")
            self.lbl_struct_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
            return True

    def init_structure(self, root_path):
        """依照規範建立資料夾"""
        specs = [
            {"s": "Original_folder", "i": "Original_img", "l": "Box01_label", "c": ["Box01"]},
            {"s": "Box01_folder",    "i": "Box01_img",    "l": "Box02_label", "c": ["Box02"]},
            {"s": "Box02_folder",    "i": "Box02_img",    "l": "Number",      "c": ["0","1","2","3","4","5","6","7","8","9","Dot","minus"]}
        ]
        try:
            for s in specs:
                stage_p = os.path.join(root_path, s["s"])
                os.makedirs(os.path.join(stage_p, s["i"]), exist_ok=True)
                lbl_p = os.path.join(stage_p, s["l"])
                os.makedirs(lbl_p, exist_ok=True)
                with open(os.path.join(lbl_p, "classes.txt"), "w", encoding="utf-8") as f:
                    f.write("\n".join(s["c"]))
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"初始化失敗: {e}")

    def setup_first_stage(self):
        """強制指定到第一階段"""
        if not self.root_dir: return

        rel_img, rel_lbl, rel_cut = MODE_PATH_MAP["STAGE1"]

        self.img_dir = os.path.join(self.root_dir, rel_img)
        self.lbl_dir = os.path.join(self.root_dir, rel_lbl)
        self.cut_dir = os.path.join(self.root_dir, rel_cut)
        self.classes = utils.load_classes(self.lbl_dir)
        self.btn_main_action.setEnabled(True)
        self.current_index = 0

        self.refresh_image_list()
        if self.lbl_dir:
                self.check_show_boxes.setEnabled(True)

    # --- 核心顯示與功能 (確保 next_image 存在) ---
    def refresh_image_list(self):
        """更新圖片清單，並根據標註與裁切狀態顯示紅/橘/綠三色"""
        if not self.img_dir: 
            return
        
        # 1. 呼叫整合後的狀態檢查 (傳入 img, lbl, 以及當前的 cut_dir)
        # 註：self.cut_dir 必須在切換模式時被正確賦值
        files, status_map = utils.get_dataset_status(self.img_dir, self.lbl_dir, self.cut_dir)
        self.image_files = files 
        self.label_list.clear()

        # 2. 遍歷檔案並設定顏色
        for f in files:
            self.label_list.addItem(f)
            item = self.label_list.item(self.label_list.count() - 1)
            
            stat = status_map.get(f, {'labeled': False, 'cropped': False})
            
            # 核心顏色邏輯
            if not stat['labeled']:
                # 狀態：未標註 -> 紅色
                item.setForeground(QColor("#FF5252")) 
            elif self.cut_dir and not stat['cropped']:
                # 狀態：已標註但未偵測到裁切圖 -> 橘色
                item.setForeground(QColor("#FFA500")) 
            else:
                # 狀態：標註與裁切皆完成 -> 綠色
                item.setForeground(QColor("#4CAF50"))

        # 3. 處理索引重置
        if self.image_files and self.current_index == -1:
            self.current_index = 0
            
        self.update_display()

    def update_display(self):
        if 0 <= self.current_index < len(self.image_files):
            self.label_list.setCurrentRow(self.current_index)
            filename = self.image_files[self.current_index]
            image_path = os.path.join(self.img_dir, filename)
            cv_img = utils.imread_chinese(image_path)
            if cv_img is not None:
                if self.check_show_boxes.isChecked() and self.lbl_dir:
                    label_filename = os.path.splitext(filename)[0] + ".txt"
                    label_full_path = os.path.join(self.lbl_dir, label_filename)
                    cv_img = utils.draw_labels(cv_img, label_full_path, self.classes)
                self.display_image(utils.convert_cv_to_pixmap(cv_img))

    def next_image(self):
        if self.image_files:
            self.current_index = (self.current_index + 1) % len(self.image_files)
            self.update_display()

    def prev_image(self):
        if self.image_files:
            self.current_index = (self.current_index - 1) % len(self.image_files)
            self.update_display()

    def display_image(self, pixmap):
        if pixmap.isNull(): return
        w, h = self.scroll_area.width() - 20, self.scroll_area.height() - 20
        scaled = pixmap.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.image_label.setPixmap(scaled)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    # --- 其餘事件處理 (OCR, AutoLabeling 等保持原樣) ---
    def handle_main_action(self):
        if not self.img_dir: return
        
        selected_text = self.combo_mode.currentText()
        current_mode_id = WORKING_MODE.get(selected_text)
        
        # 1. 找出目前的階段關鍵字 (STAGE1, STAGE2, 或 OCR)
        stage_key = next((key for key in MODE_PATH_MAP if key in current_mode_id), None)
        
        if not stage_key:
            return

        # 2. 從對照表取出該階段對應的三個路徑
        img_d, lbl_d, cut_d = MODE_PATH_MAP[stage_key]

        # 3. 根據動作類型分流
        if "PREVIEW_MODE" in current_mode_id:
            self.handle_modify_action(img_dir=img_d, lbl_dir=lbl_d, cut_dir=cut_d)
        elif "LABELING_MODE" in current_mode_id:
            self.handle_save_labeling(img_dir=img_d, lbl_dir=lbl_d, cut_dir=cut_d)

    def handle_save_labeling(self, img_dir, lbl_dir, cut_dir):
        """自動偵測階段並配置 AutoLabelingDialog"""
        if not self.root_dir:
            QMessageBox.warning(self, "錯誤", "請先選取專案根目錄")
            return
        
        # --- 1. 定義所有階段的路徑 ---
        st_img = os.path.join(self.root_dir, img_dir)
        st_lbl = os.path.join(self.root_dir, lbl_dir)
        st_cut = os.path.join(self.root_dir, cut_dir)

        if not utils.get_image_files(st_img):
            QMessageBox.warning(self, "錯誤", "目標資料夾中無資料可進行處理")
            return

        self.img_dir, self.lbl_dir, self.cut_dir = st_img, st_lbl, st_cut
        #只有OCR的cut_dir為空值
        if cut_dir != "":
            window_title = f"{img_dir} -> {cut_dir}"
            self.refresh_image_list
            dialog = AutoLabelingDialog(st_img, st_lbl, st_cut)
            dialog.setWindowTitle(window_title)
            dialog.exec()
        else:
            window_title = "OCR MODE"
            self.refresh_image_list
            OcrEditorDiolog(st_img, st_lbl, self).exec()

        self.refresh_image_list()

    def handle_modify_action(self, img_dir, lbl_dir, cut_dir):
        """
        Revised Modify Action: Now accepts subdirectories to ensure 
        we are modifying the correct stage's data.
        """
        if not self.root_dir or self.current_index == -1: 
            return

        # 1. Dynamically build paths based on current project root
        target_img_dir = os.path.join(self.root_dir, img_dir)
        target_lbl_dir = os.path.join(self.root_dir, lbl_dir)
        target_cut_dir = os.path.join(self.root_dir, cut_dir)
        
        filename = self.image_files[self.current_index]
        image_path = os.path.join(target_img_dir, filename)
        label_path = os.path.join(target_lbl_dir, os.path.splitext(filename)[0] + ".txt")

        # 2. Validation
        if not os.path.exists(image_path):
            QMessageBox.warning(self, "Error", f"Image not found: {filename}")
            return

        # 3. Load Data
        cv_img = utils.imread_chinese(image_path)
        if cv_img is None: return
        
        # Ensure classes are loaded for the specific stage
        current_classes = utils.load_classes(target_lbl_dir)
        existing_labels = utils.read_yolo_labels(label_path)
        
        # 4. Open Dialog
        pixmap = utils.convert_cv_to_pixmap(cv_img)
        dialog = RedrawDialog(pixmap, existing_labels, current_classes, self)
        
        if dialog.exec():
            new_labels = dialog.get_final_labels()
            if utils.save_yolo_labels(label_path, new_labels):
                
                # 只有當 cut_dir 有值時才進行裁切 (OCR 模式會跳過這段)
                if cut_dir: 
                    target_cut_dir = os.path.join(self.root_dir, cut_dir)
                    self.cut_dir = target_cut_dir
                    
                    # 執行裁切相關動作
                    utils.clear_existing_crops(filename, self.cut_dir, current_classes)
                    utils.crop_and_save_by_label(image_path, new_labels, current_classes, self.cut_dir)
                else:
                    # 如果是 OCR 模式 (cut_dir 為空)，我們只更新成員變數
                    self.cut_dir = "" 
                # --- 結束 ---

                # Refresh UI
                self.update_display() 
                self.refresh_image_list()

    def handle_auto_preview(self, is_enabled):
        if is_enabled and self.image_files:
            self.auto_timer.start(self.spin_interval.value() * 1000)
        else:
            self.auto_timer.stop()

    def update_timer_interval(self):
        if self.auto_timer.isActive():
            self.auto_timer.start(self.spin_interval.value() * 1000)

    def handle_image_selection(self, item):
        self.current_index = self.label_list.row(item)
        self.update_display()

    def sync_paths_and_display(self):
        """切換模式時，自動更新當前操作的目錄並刷新 UI 顯示區"""
        if not self.root_dir: return

        selected_text = self.combo_mode.currentText()
        current_mode_id = WORKING_MODE.get(selected_text, "")
        
        # 找到對應的階段路徑
        stage_key = next((key for key in MODE_PATH_MAP if key in current_mode_id), None)
        if stage_key:
            img_d, lbl_d, cut_d = MODE_PATH_MAP[stage_key]
            
            # 更新 App 目前鎖定的目錄
            self.img_dir = os.path.join(self.root_dir, img_d)
            self.lbl_dir = os.path.join(self.root_dir, lbl_d)
            
            if cut_d:
                self.cut_dir = os.path.join(self.root_dir, cut_d)
            else:
                self.cut_dir = ""

            if self.lbl_dir:
                self.check_show_boxes.setEnabled(True)

            # 重新讀取標籤清單與刷新 UI
            self.classes = utils.load_classes(self.lbl_dir)
            self.current_index = 0 # 回到第一張，或你可以維持原索引
            self.refresh_image_list()

    def keyPressEvent(self, event):
        # 1. 取得當前模式資訊
        selected_text = self.combo_mode.currentText()
        current_mode_id = WORKING_MODE.get(selected_text, "")

        # 偵錯用：看看現在抓到的是什麼按鍵
        # print(f"按下的按鍵代碼: {event.key()}") 

        # 2. 同時檢查 Return (大 Enter) 與 Enter (小 Enter)
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            
            # 3. 確認是否處於預覽模式
            if "PREVIEW_MODE" in current_mode_id:
                stage_key = next((key for key in MODE_PATH_MAP if key in current_mode_id), None)
                
                if stage_key:
                    img_d, lbl_d, cut_d = MODE_PATH_MAP[stage_key]
                    
                    # 執行動作
                    self.next_image()
                    self.handle_modify_action(img_dir=img_d, lbl_dir=lbl_d, cut_dir=cut_d)
                    
                    # 告知系統此事件已處理，不要再往外傳
                    event.accept()
                    return 

        # 4. 其他按鍵交還給父類別處理 (避免 Tab 或 Esc 失效)
        super().keyPressEvent(event)
        

def main():
    app = QApplication(sys.argv)
    window = LabelerApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()