"""
3_auto_generate_label.src.ocr_editor_diolog 的 Docstring
啟用OCR編著模式
引用main.py 的編註檔和圖片路徑
ocr偵測, 自動處理圖片, 設定基準檔(offset區域, 數字錨點圖, ocr偵測區域)
自動處理秒數控制
左邊預覽圖顯示
"""
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, 
                             QGroupBox, QTextEdit, QMessageBox, QSplitter,
                             QListWidget, QSizePolicy, QDialog, QDialogButtonBox,
                             QInputDialog, QLineEdit, QSpinBox)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QPixmap, QColor, QImage
from easyocr import Reader
from os import path
from sys import exit, argv
import cv2
import numpy as np

try:
    from offset import select_feature_area, offset_calculation
    from utils import get_image_files, load_classes, get_dataset_status, save_yolo_labels, name_to_id, setup_path_label
    from number_template_operation import template_merge
    from constants import DEFAULT_PARAMS, CHAR_MAP
    from ocr_tuning_ui import TuningDialog
    from ocr_image_proc import ImageProcessor, fix_1_vs_7_by_top_width, find_dot, find_minus
except ImportError as e:
    print(f"錯誤：找不到模組 ({e})。請確保目錄下存在相關 .py 檔案。")
    exit(1)

# ==========================================
# 輔助視窗：預覽參照圖與標註
# ==========================================
class PreviewDialog(QDialog):
    def __init__(self, img, boxes, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"步驟 1/4: 確認基準圖標註 (紅色框)")
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        self.display_img = img.copy()
        
        # 畫出所有讀取到的框 (紅色 - 標註)
        for (x, y, w, h) in boxes:
            cv2.rectangle(self.display_img, (x, y), (x+w, y+h), (0, 0, 255), 2)
        
        height, width, channel = self.display_img.shape
        bytes_per_line = 3 * width
        q_img = QImage(cv2.cvtColor(self.display_img, cv2.COLOR_BGR2RGB).data, 
                       width, height, bytes_per_line, QImage.Format.Format_RGB888)
        
        lbl_img = QLabel()
        lbl_img.setPixmap(QPixmap.fromImage(q_img).scaled(780, 500, Qt.AspectRatioMode.KeepAspectRatio))
        lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_img)
        
        lbl_info = QLabel("請確認【紅色框】(標註檔內容) 是否正確。\n\n接下來將設定：\n1. 特徵定位點 (Anchor)\n2. 實際處理區域 (Blue ROI)")
        lbl_info.setStyleSheet("font-size: 14px; color: #2196F3; font-weight: bold;")
        lbl_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_info)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

# ==========================================
# 主視窗
# ==========================================
class OcrEditorDiolog(QDialog):
    def __init__(self, img_dir, lbl_dir, parent=None):
        super().__init__(parent)
        self.setWindowTitle("自動檢測標註控制台 (OCR Mode)")
        self.resize(1400, 950)

        self.img_dir = img_dir
        self.lbl_dir = lbl_dir
        self.img_files = get_image_files(img_dir)
        self.classes = load_classes(lbl_dir)

        self.current_anchor_number_img_bgr = None #img of anchor number
        self.current_anchor_number_img_binary = None #img of binrary anchor number
        self.is_auto_running = False
        self.process_timer = QTimer()
        self.process_timer.timeout.connect(self.auto_process_flow)

        self.current_label_boxes = [] #red boxes for label original boxes place
        self.current_roi_box = None #blue box for label ocr scan place
        self.manual_roi_stored = None

        self.current_params = DEFAULT_PARAMS.copy()
        self.display_mode = "FULL" 

        self.ref_data = {
            'active': False,
            'name': "",
            'img': None,
            'label_boxes': [],
            'roi_box': None,
            'anchor_offset': None,
            'anchor_xy': None,
            'anchor_number': None
        }

        print("正在載入 EasyOCR...")
        self.reader = Reader(['en'])
        self.allowlist = '1234567890.-'

        self.tuner_dialog = None # set ocr setting gui
        self.initUI()
        self.populate_file_list()

    def initUI(self):
        main_layout = QHBoxLayout(self)

        # =================================================
        # LEFT SIDE
        # =================================================
        left_splitter = QSplitter(Qt.Orientation.Vertical)

        # 上方：顯示 Offset 結果 (紅框 + 藍框)
        self.lbl_origin = QLabel("上方預覽區 (原圖+框線)")
        self.lbl_origin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_origin.setStyleSheet("background: #333; border: 1px solid #555; color: #AAA;")
        self.lbl_origin.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        left_splitter.addWidget(self.lbl_origin)

        bottom_h_splitter = QSplitter(Qt.Orientation.Horizontal)

        # [左側] 下方預覽區 (二值化 ROI)
        self.lbl_binary = QLabel("下方預覽區 (藍框 ROI 二值化)")
        self.lbl_binary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_binary.setStyleSheet("background: #000; border: 1px solid #555; color: #AAA;")
        self.lbl_binary.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        bottom_h_splitter.addWidget(self.lbl_binary)

        # [右側] 錨點圖 (Anchor)
        self.lbl_anchor = QLabel("錨點圖")
        self.lbl_anchor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_anchor.setStyleSheet("background: #444; border: 1px solid #555; color: #EEE;")
        self.lbl_anchor.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        bottom_h_splitter.addWidget(self.lbl_anchor)


        left_splitter.addWidget(bottom_h_splitter)

        
        main_layout.addWidget(left_splitter, stretch=3)

        # =================================================
        # RIGHT SIDE: Controls
        # =================================================
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # 1. 路徑
        grp_path = QGroupBox("1. 路徑")
        path_layout = QVBoxLayout()
        self.lbl_img_path = QLabel(setup_path_label(self.img_dir, "Img: "))
        self.lbl_img_path.setToolTip(self.img_dir)
        path_layout.addWidget(self.lbl_img_path)
        self.lbl_lbl_path = QLabel(setup_path_label(self.lbl_dir, "Lbl: "))
        self.lbl_lbl_path.setToolTip(self.lbl_dir)
        path_layout.addWidget(self.lbl_lbl_path)
        grp_path.setLayout(path_layout)
        right_layout.addWidget(grp_path)

        # 2. Offset 設定 (包含 ROI 設定)
        grp_ref = QGroupBox("2. 基準圖設定 (Auto Offset)")
        ref_layout = QVBoxLayout()
        self.btn_select_ref = QPushButton("選取基準圖 & 設定 ROI")
        self.btn_select_ref.setStyleSheet("background-color: #009688; color: white; font-weight: bold;")
        self.btn_select_ref.clicked.connect(self.select_reference_from_list)
        self.lbl_ref_info = QLabel("未設定")
        ref_layout.addWidget(self.btn_select_ref)
        ref_layout.addWidget(self.lbl_ref_info)
        grp_ref.setLayout(ref_layout)
        right_layout.addWidget(grp_ref)

        # 3. 手動覆蓋 (Optional)
        grp_ctrl = QGroupBox("3. 設定二值圖或更改ROI區域")
        ctrl_layout = QVBoxLayout()
        h_roi = QHBoxLayout()
        self.btn_roi = QPushButton("臨時手動 ROI")
        self.btn_roi.clicked.connect(self.set_roi_cv2)
        self.btn_roi.setEnabled(False)
        self.btn_reset_roi = QPushButton("重置 (回選取基準圖)")
        self.btn_reset_roi.clicked.connect(self.reset_roi)
        self.btn_reset_roi.setEnabled(False)
        h_roi.addWidget(self.btn_roi)
        h_roi.addWidget(self.btn_reset_roi)
        ctrl_layout.addLayout(h_roi)
        
        self.btn_tune = QPushButton("調整二值化參數")
        self.btn_tune.setStyleSheet("""
            QPushButton {
                background-color: #2196F3; 
                color: white; 
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:disabled {
                background-color: #e0e0e0; 
                color: #a0a0a0;
            }
        """)
        self.btn_tune.clicked.connect(self.open_tuning_dialog)
        self.btn_tune.setEnabled(False)
        ctrl_layout.addWidget(self.btn_tune)
        grp_ctrl.setLayout(ctrl_layout)
        right_layout.addWidget(grp_ctrl)

        # 4. OCR (針對下方預覽)
        grp_ocr = QGroupBox("4. OCR 與 結果修正")
        ocr_layout = QVBoxLayout()
        
        # 原始 OCR 結果顯示 (唯讀)
        self.txt_result = QTextEdit()
        self.txt_result.setReadOnly(True)
        self.txt_result.setMaximumHeight(60)
        self.txt_result.setPlaceholderText("OCR 原始辨識結果...")
        
        btn_run = QPushButton("執行 OCR")
        btn_run.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        btn_run.clicked.connect(self.run_ocr)
        
        # 新增：最後準備輸出的數值欄位與修改按鈕
        h_output = QHBoxLayout()
        self.edit_final_value = QLineEdit()
        self.edit_final_value.setPlaceholderText("最終輸出數值...")
        # 這裡可以連接一個簡單的 slot 來處理修改邏輯
        h_output.addWidget(QLabel("輸出值:"))
        h_output.addWidget(self.edit_final_value)

        ocr_layout.addWidget(self.txt_result)
        ocr_layout.addWidget(btn_run)
        ocr_layout.addLayout(h_output) # 加入輸出欄位
        grp_ocr.setLayout(ocr_layout)
        right_layout.addWidget(grp_ocr)

        # 5. 標註與自動化 (新區塊)
        grp_export = QGroupBox("5. 標註與執行")
        export_layout = QVBoxLayout()
        
        h_action = QHBoxLayout()
        self.btn_save_yolo = QPushButton("寫成 YOLO 標註檔")
        self.btn_save_yolo.setStyleSheet("""
            QPushButton {
                background-color: #2196F3; 
                color: white; 
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:disabled {
                background-color: #e0e0e0; 
                color: #a0a0a0;
            }
        """)
        self.btn_save_yolo.setEnabled(False) # 預設禁用
        self.btn_save_yolo.clicked.connect(self.save_labels)
        
        self.btn_auto_run = QPushButton("自動執行")
        self.btn_auto_run.setStyleSheet("""
            QPushButton {
                background-color: #FF9800; 
                color: white; 
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:disabled {
                background-color: #e0e0e0; 
                color: #a0a0a0;
            }
        """)
        self.btn_auto_run.setEnabled(False) # 預設禁用
        self.btn_auto_run.clicked.connect(self.toggle_auto_proc)
        
        h_action.addWidget(self.btn_save_yolo)
        h_action.addWidget(self.btn_auto_run)

        

        # 延遲設定
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("自動停留秒數:"))
        self.spin_delay = QSpinBox()
        self.spin_delay.setRange(0, 10)
        self.spin_delay.setValue(1)
        self.spin_delay.setSuffix(" 秒")
        delay_layout.addWidget(self.spin_delay)

        export_layout.addLayout(h_action)
        export_layout.addLayout(delay_layout)

        grp_export.setLayout(export_layout)
        right_layout.addWidget(grp_export)

        # List
        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self.on_list_click)
        right_layout.addWidget(self.list_widget, stretch=1)

        main_layout.addWidget(right_panel, stretch=1)

    def populate_file_list(self):
        """
        初始化專用：呼叫 refresh_list 載入資料，並設定按鈕狀態與預設選取。
        """
        # 1. 呼叫核心更新 (載入檔案 + 上色)
        self.refresh_list()

        # 2. 根據載入結果設定 UI 狀態 (只有初始化時需要做)
        if self.img_files:
            self.btn_select_ref.setEnabled(True) 
            
            # 預設選取第一張 (觸發 load_image)
            if self.list_widget.count() > 0:
                self.list_widget.setCurrentRow(0)
        else:
            # 如果沒檔案，鎖定按鈕
            self.btn_roi.setEnabled(False)
            self.btn_tune.setEnabled(False)
            self.btn_reset_roi.setEnabled(False)
            self.btn_select_ref.setEnabled(False)
            self.btn_auto_run.setEnabled(False)
            self.btn_save_yolo.setEnabled(False)
            self.txt_result.setText("目錄中找不到影像檔案")

    # ==========================
    # Logic: Offset & Ref Setup
    # ==========================
    def select_reference_from_list(self):
        files, status_map = get_dataset_status(self.img_dir, self.lbl_dir)
        labeled_files = [f for f in files if status_map.get(f, {}).get('labeled', False)]
        if not labeled_files:
            QMessageBox.warning(self, "無可用檔案", "無綠色(已標註)檔案。")
            return
        item, ok = QInputDialog.getItem(self, "選取基準圖", "選擇已標註圖片:", labeled_files, 0, False)
        if ok and item:
            self.setup_reference(item)

    def setup_reference(self, filename):
        """ 設定基準圖的完整流程：確認標註 -> 選 offset anchor -> 選 ROI -> 選 number anchor """
        img_path = path.join(self.img_dir, filename)
        txt_name = path.splitext(filename)[0] + ".txt"
        lbl_path = path.join(self.lbl_dir, txt_name)
        
        if not path.exists(lbl_path): return

        ref_img = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), -1)
        if ref_img is None: return

        # 1. 讀取標註 (紅框)
        label_boxes = []
        try:
            with open(lbl_path, 'r') as f:
                h_img, w_img = ref_img.shape[:2]
                for line in f:
                    parts = list(map(float, line.strip().split()))
                    if len(parts) >= 5:
                        _, xc, yc, w_norm, h_norm = parts[:5]
                        w_box = int(w_norm * w_img); h_box = int(h_norm * h_img)
                        x_box = int((xc * w_img) - (w_box / 2)); y_box = int((yc * h_img) - (h_box / 2))
                        label_boxes.append((x_box, y_box, w_box, h_box))
        except: pass

        if not label_boxes: return

        # 2. 預覽標註
        dlg = PreviewDialog(ref_img, label_boxes, self)
        if dlg.exec() != QDialog.DialogCode.Accepted: return

        # 3. 選取 全域偏移 Anchor (Offset Template)
        # 這是用來修正整張圖片的大範圍位移
        template, anchor_xy = select_feature_area(ref_img)
        if template is None: return

        # 4. 選取 ROI (藍框) - 用於 Image Processing
        # 這是實際要進行二值化與 OCR 的區域
        QMessageBox.information(self, "步驟 3/4: 設定 ROI", "請框選【藍色 ROI 區域】。\n(這是實際要進行二值化與 OCR 的掃描範圍)")
        
        roi_win = "Select Processing ROI (Blue Box)"
        cv2.namedWindow(roi_win, cv2.WINDOW_NORMAL)
        cv2.setWindowProperty(roi_win, cv2.WND_PROP_TOPMOST, 1)
        roi_rect = cv2.selectROI(roi_win, ref_img, showCrosshair=True)
        cv2.destroyWindow(roi_win)
        
        # 檢查 ROI 是否有效
        if roi_rect[2] == 0 or roi_rect[3] == 0:
            QMessageBox.warning(self, "取消", "未選取 ROI 區域，流程中止。")
            return

        # 5. 選取 數字錨點 (Number Anchor) - 用於局部定位
        # 這是你要求的：紀錄一個「數字圖片」，而非座標
        QMessageBox.information(self, "步驟 4/4: 設定數字錨點", 
                              "請框選一個【特徵明顯的數字】作為錨點。\n"
                              "(系統將儲存此數字的圖像內容，用於精確定位)")
        
        anchor_win = "Select Number Anchor Image"
        cv2.namedWindow(anchor_win, cv2.WINDOW_NORMAL)
        cv2.setWindowProperty(anchor_win, cv2.WND_PROP_TOPMOST, 1)
        anchor_rect = cv2.selectROI(anchor_win, ref_img, showCrosshair=True)
        cv2.destroyWindow(anchor_win)

        anchor_img = None
        # 檢查錨點選取是否有效
        if anchor_rect[2] > 0 and anchor_rect[3] > 0:
            ax, ay, aw, ah = anchor_rect
            # [關鍵] 這裡切片取出圖片內容，並使用 copy() 確保獨立於原圖
            anchor_img = ref_img[ay:ay+ah, ax:ax+aw].copy()
            self.current_anchor_number_img_bgr = anchor_img
            self.show_anchor_preview(self.current_anchor_number_img_bgr)
        else:
            QMessageBox.warning(self, "取消", "未選取數字錨點，流程中止。")
            return

        # 6. 儲存所有資料
        # 確保所有步驟都成功後才 update
        self.ref_data.update({
            'active': True, 
            'name': filename, 
            'img': ref_img,
            'label_boxes': label_boxes, # 原標註紅框
            'roi_box': roi_rect,        # 藍框 (x, y, w, h)
            'anchor_offset': template,  # 全域偏移用的圖
            'anchor_xy': anchor_xy,     # 全域偏移用的原始座標
            'anchor_number': anchor_img # 數字錨點圖片
        })
        
        self.lbl_ref_info.setText(f"基準: {filename}\nROI: {roi_rect[2]}x{roi_rect[3]}\n錨點已設定")
        self.lbl_ref_info.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.btn_roi.setEnabled(True)
        self.btn_tune.setEnabled(True)
        self.btn_reset_roi.setEnabled(True)
        
        # 立即重新載入當前圖片，應用新的設定
        self.load_image()

    # ==========================
    # Logic: Load & Display
    # ==========================
    def on_list_click(self, row):
        if row >= 0 and row < len(self.img_files):
            self.current_idx = row
            self.load_image()

    def load_image(self):
        if not self.img_files: return
        fname = self.img_files[self.current_idx]
        full_path = path.join(self.img_dir, fname)
        
        # 讀取圖片
        self.original_img = cv2.imdecode(np.fromfile(full_path, dtype=np.uint8), -1)
        
        # 初始化清空
        self.current_label_boxes = []
        self.current_roi_box = None
        
        dx, dy = 0, 0  # 預設位移為 0

        # --- 第一階段：計算位移與紅框 (無論 ROI 是手動還是自動，通常都需要位移紅框) ---
        if self.ref_data['active']:
            # 執行 Offset 計算
            calc_dx, calc_dy, conf = offset_calculation(
                self.ref_data['anchor_offset'], 
                self.original_img, 
                self.ref_data['anchor_xy']
            )
            
            if calc_dx is not None:
                dx, dy = calc_dx, calc_dy
                # 更新所有 紅色標註框
                for (rx, ry, rw, rh) in self.ref_data['label_boxes']:
                    self.current_label_boxes.append((int(rx + dx), int(ry + dy), rw, rh))
                print(f"[{fname}] Offset Success: {dx}, {dy}")
            else:
                print(f"[{fname}] Offset Failed, using original positions")
                # 若位移失敗，可選擇顯示原始位置的紅框
                self.current_label_boxes = self.ref_data['label_boxes'].copy()

        # --- 第二階段：決定藍框 ROI ---
        # 1. 優先判斷是否為手動覆蓋模式
        if self.display_mode == "MANUAL_ROI" and self.manual_roi_stored:
            self.current_roi_box = self.manual_roi_stored
            print(f"[{fname}] Mode: Manual ROI")
            
        # 2. 否則，若有基準圖資料，則使用自動位移後的 ROI
        elif self.ref_data['active']:
            rx, ry, rw, rh = self.ref_data['roi_box']
            self.current_roi_box = (int(rx + dx), int(ry + dy), rw, rh)
            print(f"[{fname}] Mode: Auto Offset ROI")
        
        # 3. 以上皆非，全圖模式
        else:
            self.display_mode = "FULL"
            print(f"[{fname}] Mode: Full View")

        # 最後刷新
        self.update_displays()
        self.txt_result.clear()
        self.edit_final_value.clear()

    def update_displays(self):
        if self.original_img is None: return

        # -----------------------------------
        # 1. 上方預覽圖 (Top View)
        # -----------------------------------
        top_view = self.original_img.copy()
        
        # 繪製 紅色框 (標註)
        for (x, y, w, h) in self.current_label_boxes:
            cv2.rectangle(top_view, (x, y), (x+w, y+h), (0, 0, 255), 2)
            
        # 繪製 藍色框 (ROI)
        if self.current_roi_box:
            x, y, w, h = self.current_roi_box
            cv2.rectangle(top_view, (x, y), (x+w, y+h), (255, 0, 0), 3) # Blue BGR=(255,0,0)

        # 顯示
        rgb = cv2.cvtColor(top_view, cv2.COLOR_BGR2RGB)
        h, w, c = rgb.shape
        pix = QPixmap.fromImage(QImage(rgb.data, w, h, w*c, QImage.Format.Format_RGB888))
        self.lbl_origin.setPixmap(pix.scaled(self.lbl_origin.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

        # -----------------------------------
        # 2. 下方二值化預覽 (Bottom View)
        # -----------------------------------
        # 只針對 藍色 ROI 區域 進行處理
        proc_target = None
        
        if self.current_roi_box:
            x, y, w, h = self.current_roi_box
            # 邊界檢查
            h_img, w_img = self.original_img.shape[:2]
            x = max(0, min(x, w_img-1)); y = max(0, min(y, h_img-1))
            w = min(w, w_img-x); h = min(h, h_img-y)
            
            if w > 0 and h > 0:
                proc_target = self.original_img[y:y+h, x:x+w]
        
        if proc_target is not None:
            final_img, _ = ImageProcessor.apply_processing(proc_target, self.current_params)
            h, w = final_img.shape
            pix_bin = QPixmap.fromImage(QImage(final_img.data, w, h, w, QImage.Format.Format_Grayscale8))
            self.lbl_binary.setPixmap(pix_bin.scaled(self.lbl_binary.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.lbl_binary.clear()
            self.lbl_binary.setText("無有效 ROI 區域")

    def show_anchor_preview(self, img_bgr):
        """ 顯示錨點圖片到 lbl_anchor """
        if img_bgr is None:
            self.lbl_anchor.clear()
            self.lbl_anchor.setText("無錨點")
            return
        
        # 1. 處理影像
        final_img, _ = ImageProcessor.apply_processing(img_bgr, self.current_params)
        self.current_anchor_number_img_binary = final_img
        
        # 2. 轉換為 QImage 時務必使用 .copy()
        h, w = final_img.shape
        # 增加 .copy() 確保記憶體獨立性
        qimg = QImage(final_img.data, w, h, w, QImage.Format.Format_Grayscale8).copy() 
        
        pix_bin = QPixmap.fromImage(qimg)
        
        # 3. 縮放時參照自己的 size()，並確認 size 是否有效
        target_size = self.lbl_anchor.size()
        if target_size.width() < 10: # 防呆：如果尚未佈局完成
            target_size = QSize(200, 100)
            
        self.lbl_anchor.setPixmap(pix_bin.scaled(
            target_size, 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        ))

    def toggle_auto_proc(self):
        """
        [按鈕觸發] 啟動或停止自動流程
        """
        if hasattr(self, 'is_auto_running') and self.is_auto_running:
            self.is_auto_running = False
            self.btn_auto_run.setText("自動流程開始")
        else:
            self.is_auto_running = True
            self.btn_auto_run.setText("自動流程停止")
            self.auto_process_flow()

    # ==========================
    # Manual ROI (Override)
    # ==========================
    def set_roi_cv2(self):
        if self.original_img is None: return
        roi = cv2.selectROI("Manual ROI Override", self.original_img, showCrosshair=True)
        cv2.destroyWindow("Manual ROI Override")
        
        if roi[2] > 0 and roi[3] > 0:
            self.display_mode = "MANUAL_ROI"
            self.manual_roi_stored = roi
            self.current_roi_box = roi
            # 手動模式下，紅色框暫時不變，或者您可以選擇清空
            self.update_displays()

    def reset_roi(self):
        # 重置回 Auto Offset 模式
        self.display_mode = "OFFSET"
        self.load_image() # 重新計算 Offset

    # =================================================
    # Utils
    # =================================================
    # ocr_editor_dialog.py

    def open_tuning_dialog(self):
        # 1. 建立視窗 (若不存在)
        if self.tuner_dialog is None:
            # 【關鍵設定 A】: parent 必須是 self
            # 這樣 Tuner 屬於 Editor 的「自己人」，Editor 被 exec() 鎖定時，Tuner 依然可以動
            self.tuner_dialog = TuningDialog(self.current_params, parent=self)
            
            self.tuner_dialog.params_changed.connect(self.on_params_changed)
            
            # 【關鍵設定 B】: 設定視窗旗標
            # 設為 "Tool"，定義為此視窗的工具,避免出現與ocr_editor_diolog爭搶控制權
            from PyQt6.QtCore import Qt
            self.tuner_dialog.setWindowFlags(Qt.WindowType.Tool)

        # 2. 顯示視窗 (若被隱藏)
        if self.tuner_dialog.isHidden():
            # 【關鍵設定 C】: 使用 .show() 而不是 .exec()
            # 這樣 Tuner 出現後，你依然可以點擊原本的 Editor (例如拖曳圖片)
            self.tuner_dialog.show()
        
        # 3. 如果最小化了就還原，並拉到最上層
        if self.tuner_dialog.isMinimized():
            self.tuner_dialog.showNormal()
            
        self.tuner_dialog.raise_()
        self.tuner_dialog.activateWindow()
        
    def save_labels(self):
        """
        將目前的辨識結果 (包含 Dot 與 minus 轉換) 存成 YOLO 標註檔。
        """
        if self.original_img is None or not self.current_label_boxes:
            return
        
        # 1. 準備路徑與影像尺寸
        img_name = self.img_files[self.current_idx]
        txt_name = path.splitext(img_name)[0] + ".txt"
        label_path = path.join(self.lbl_dir, txt_name)
        h_img, w_img = self.original_img.shape[:2]

        # 2. 準備數值與排序後的標註框
        final_text = self.edit_final_value.text()
        # 假設 box 格式是 (x, y, w, h)，我們依照 x (索引 0) 來排序
        self.current_label_boxes.sort(key=lambda box: box[0])
        
        yolo_data = []

        for i, char in enumerate(final_text):
            if i >= len(self.current_label_boxes):
                break

            cls_name = CHAR_MAP.get(char, char)
            cls_id = name_to_id(cls_name, self.classes)
            if cls_id is None or cls_id < 0:
                continue

            # 座標歸一化
            px, py, pw, ph = self.current_label_boxes[i]
            xc = (px + pw / 2.0) / w_img
            yc = (py + ph / 2.0) / h_img
            wn = pw / w_img
            hn = ph / h_img
            
            yolo_data.append([cls_id, xc, yc, wn, hn])
        # 存檔
        if save_yolo_labels(label_path, yolo_data):
            print(f"成功存檔：{txt_name}")
            self.btn_save_yolo.setEnabled(False)
            current_item = self.list_widget.currentItem()
            if current_item:
                current_item.setForeground(QColor("green"))
            return True
        return False

    def auto_process_flow(self):
        """
        自動流程邏輯：
        Skip Labeled -> Next Img -> Offset(Auto) -> OCR -> Save -> Delay -> Loop
        """
        # 0. 安全檢查
        if not hasattr(self, 'is_auto_running') or not self.is_auto_running:
            return

        # 1. 取得最新的標註狀態
        # 這樣才能知道哪些檔案已經是綠色 (已標註)
        _, status_map = get_dataset_status(self.img_dir, self.lbl_dir)

        # 2. 尋找下一個「未標註」的檔案索引
        # 從目前位置的下一張開始找
        next_idx = self.current_idx + 1
        
        while next_idx < len(self.img_files):
            fname = self.img_files[next_idx]

            stat = status_map.get(fname, {})
            # 檢查狀態：如果是 False (未標註)，這就是我們要處理的，停止尋找
            if not stat.get('labeled', False):
                break
            # 如果是 True (已標註)，就繼續往後找 (Skip)
            next_idx += 1

        # 3. 判斷是否還有檔案需要處理
        if next_idx < len(self.img_files):
            # 更新當前索引為找到的那張
            self.current_idx = next_idx

            # UI 同步
            self.list_widget.setCurrentRow(self.current_idx)
            
            # [修正] processEvents 是一個函式，記得加括號 ()
            QApplication.processEvents() 
            
            # 執行 OCR
            self.run_ocr()
            
            # 存檔 (通常建議 OCR 完確認無誤就存，或者你想放在 OCR 內部也可)
            self.save_labels()
            
            # 刷新 UI 以顯示剛才的存檔狀態變色 (選用)
            # self.refresh_list() 
            QApplication.processEvents()

            # 設定延遲並排程下一次
            delay_ms = self.spin_delay.value() * 1000
            QTimer.singleShot(delay_ms, self.auto_process_flow)
            
        else:
            # 列表跑完了 (或是剩下的全部都已經標註過)
            self.is_auto_running = False
            self.btn_auto_run.setText("自動執行")
            self.btn_auto_run.setEnabled(True)
            QMessageBox.information(self, "完成", "已完成列表中的所有未標註圖片處理。")

    def on_params_changed(self, new_params):
        self.current_params = new_params
        self.update_displays()

        if self.current_anchor_number_img_bgr is not None:
            self.show_anchor_preview(self.current_anchor_number_img_bgr)

    def refresh_list(self):
        """
        核心函式：讀取檔案列表並更新 ListWidget 的內容與顏色。
        被 populate_file_list 和 save_labels 呼叫。
        """
        # 1. 取得最新的檔案與標註狀態
        files, status_map = get_dataset_status(self.img_dir, self.lbl_dir)
        self.img_files = files # 同步更新內部的檔案清單變數
        
        # 2. 同步列表內容 (如果檔案數量變了，或者列表是空的，就重繪)
        # 這樣做的好處是：如果是單純存檔導致的顏色變更，不會造成列表閃爍
        if self.list_widget.count() != len(files):
            self.list_widget.clear()
            self.list_widget.addItems(files)

        # 3. 原地更新顏色 (這段是所有情況都需要的)
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            filename = item.text()
            
            stat = status_map.get(filename, {})
            is_labeled = stat.get('labeled', False)
            
            # 顏色邏輯：有 .txt 綠色，沒 .txt 紅色
            item.setForeground(QColor("#4CAF50") if is_labeled else QColor("#FF5252"))

    def run_ocr(self):
        """
        OCR 主流程指揮官：準備圖片 -> 執行策略 -> 後處理 -> 更新 UI
        """
        # 1. 準備目標圖片 (Target Image)
        if not self.current_roi_box or self.original_img is None:
            return

        x, y, w, h = self.current_roi_box
        h_img, w_img = self.original_img.shape[:2]
        
        # 簡單防呆
        if w <= 0 or h <= 0 or x >= w_img or y >= h_img:
            return

        target_img = self.original_img[y:y+h, x:x+w]
        
        # 取得二值化圖片 (這是所有後續步驟都需要的)
        target_bin, _ = ImageProcessor.apply_processing(target_img, self.current_params)

        # ==========================================
        # 2. [核心策略] 執行 OCR (包含自動重試邏輯)
        # ==========================================
        raw_text, conf, used_method = self._execute_smart_ocr(target_bin)

        # ==========================================
        # 3. [後處理] 修正字元 (1vs7, 點, 負號)
        # ==========================================
        final_text = self._apply_post_processing(target_bin, raw_text)

        # ==========================================
        # 4. 更新 UI
        # ==========================================
        self.txt_result.setText(f"OCR ({used_method}): {raw_text}\nConf: {conf:.4f}")
        self.edit_final_value.setText(final_text)
        
        # 開啟自動功能
        self.btn_auto_run.setEnabled(True)
        self.btn_auto_run.setText("自動流程開始")
        self.btn_save_yolo.setEnabled(True)

    def _execute_smart_ocr(self, target_bin):
        """
        執行 OCR 策略：
        先試普通辨識，如果信心低，則嘗試「錨點拼接辨識」。
        回傳: (text, conf, method_name)
        """
        # --- 策略 1: 標準 OCR ---
        res = self.reader.readtext(target_bin, allowlist=self.allowlist, mag_ratio=2.5, decoder='beamsearch')
        
        text = res[0][1] if res else ""
        conf = res[0][2] if res else 0.0
        method = "Standard"

        # --- 判斷是否需要啟用「錨點增強」 ---
        # 條件: 1. 有錨點圖 2. (信心度低 OR 字數太少)
        need_retry = (conf < 0.6) # 門檻可自行調整
        has_anchor = (self.current_anchor_number_img_binary is not None)

        if need_retry and has_anchor:
            print(f"Confidence low ({conf:.2f}), retrying with Anchor Merge...")
            
            # 1. 執行圖片拼接
            merged_img = template_merge(target_bin, self.current_anchor_number_img_binary, self.current_params)
            
            if merged_img is not None:
                # 2. 重新 OCR
                res_retry = self.reader.readtext(merged_img, allowlist=self.allowlist, detail=1)
                count = cv2.findContours
                
                if res_retry:
                    # 將結果合併成一個字串並去空白，例如 "356.73"
                    raw_retry = "".join([item[1] for item in res_retry]).strip()
                    
                    # ==========================================
                    # 刪除邏輯：直接刪除最後的數字
                    # ==========================================
                    cleaned_text = raw_retry[:-1].strip()
                    
                    # 4. 判斷新結果是否更好？
                    if len(cleaned_text) > 0:
                        text = cleaned_text
                        conf = res_retry[0][2] 
                        method = "Anchor Merge"
                        print(f"Anchor Retry Result: {text}")

        return text, conf, method
    
    def _apply_post_processing(self, img_bin, text):
        """
        執行一連串的文字修正邏輯
        """
        current_text = text

        # 1. 1 vs 7 修正 (利用頂部寬度)
        current_text = fix_1_vs_7_by_top_width(img_bin, current_text)

        # 2. 小數點偵測 (若 OCR 沒讀到，利用紅框距離找)
        if "." not in current_text:
            current_text = find_dot(self.current_label_boxes, current_text)

        # 3. 負號或缺位偵測 (利用影像像素找)
        if "-" not in current_text:
            current_text = find_minus(img_bin, current_text)
            
        return current_text

if __name__ == '__main__':
    img_dir = '/Users/shengyuanshaw/Desktop/yenprotek/自動標註測試資料/Number/Image'
    lbl_dir = '/Users/shengyuanshaw/Desktop/yenprotek/自動標註測試資料/Number/Label'

    app = QApplication(argv)
    window = OcrEditorDiolog(img_dir, lbl_dir, None)
    window.show()
    exit(app.exec())