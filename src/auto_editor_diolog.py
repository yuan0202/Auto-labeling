"""由main.py偵測當點擊到標注模式的開始自動標註按鈕時,依照是否有開啟OCR模式分成2種畫面
兩個不同的試窗呈現, withoutOCR是讓使用者自己畫框並且讀取標注檔資料夾中的class.txt裡的label給使用者選擇匡對應的標籤,
之後寫成標注檔(檔名:圖片檔名.txt)存放進標註檔資料夾所在,標註檔和圖片資料假餓路進都可以從utils.py中取得,右邊有圖片清單可以用顏色標註哪些已經有標註檔哪些還沒有底下有一個自動處理按鈕會搜尋下一個沒有標註黨的圖片,先用offset.py找出偏移再自動標注匡的位置加上偏移量,右邊可以調正自動處理時圖片的停留秒數,在自動處理時按下e鍵會跳出editor_diolog.py手動調整,調整完確認後繼續自動處理"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QListWidget, QLabel, QSpinBox, QMessageBox, 
                             QWidget, QSplitter, QInputDialog, QGroupBox, 
                             QLineEdit, QFileDialog)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QPixmap, QColor
import os
import sys

import utils
from offset import select_feature_area, offset_calculation
from editor_diolog import RedrawDialog

class AutoLabelingDialog(QDialog):
    def __init__(self, img_dir, lbl_dir, cut_img_dir, parent=None):
        super().__init__(parent)
        self.setWindowTitle("自動標註控制台 (Offset Mode)")
        self.resize(1100, 700)
        
        # --- 資料初始化 ---
        self.img_dir = img_dir
        self.lbl_dir = lbl_dir
        self.cut_img_dir = cut_img_dir
        self.image_files = utils.get_image_files(img_dir)
        self.current_index = 0
        self.classes = utils.load_classes(lbl_dir) # 讀取 classes.txt
        
        # 自動化需要的變數
        self.is_auto_running = False
        self.base_labels = None     # 基準標註框 (YOLO)
        self.anchor_template = None # 特徵圖 (OpenCV)
        self.anchor_xy = None       # 特徵座標
        
        # Timer
        self.process_timer = QTimer()
        self.process_timer.timeout.connect(self.run_next_auto_step)

        # --- UI 佈局 ---
        main_layout = QHBoxLayout(self)

        # 1. 左側：圖片預覽區
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        self.image_label = QLabel("請先設定基準，再開始自動處理")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #2b2b2b; color: white; font-size: 16px;")
        self.image_label.setMinimumSize(600, 500)
        left_layout.addWidget(self.image_label)

        # 路徑區
        grp_path = QGroupBox("1. 路徑")
        path_layout = QVBoxLayout()
        self.lbl_img_path = QLabel(utils.setup_path_label(self.img_dir, "Img: "))
        self.lbl_img_path.setToolTip(self.img_dir)
        path_layout.addWidget(self.lbl_img_path)

        self.lbl_lbl_path = QLabel(utils.setup_path_label(self.lbl_dir, "Lbl: "))
        self.lbl_lbl_path.setToolTip(self.lbl_dir)
        path_layout.addWidget(self.lbl_lbl_path)

        self.cut_img_path = QLabel(utils.setup_path_label(self.cut_img_dir, "Cut_Img: "))
        self.cut_img_path.setToolTip(self.cut_img_dir)
        path_layout.addWidget(self.cut_img_path)

        grp_path.setLayout(path_layout)
        left_layout.addWidget(grp_path)
        
        # 2. 右側：控制面板
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # 圖片清單
        right_layout.addWidget(QLabel("圖片標註狀態:"))
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        right_layout.addWidget(self.list_widget)
        
        # 設定區
        setting_group = QWidget()
        setting_layout = QVBoxLayout(setting_group)
        
        # 延遲設定
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("自動停留秒數:"))
        self.spin_delay = QSpinBox()
        self.spin_delay.setRange(0, 10)
        self.spin_delay.setValue(1)
        self.spin_delay.setSuffix(" 秒")
        delay_layout.addWidget(self.spin_delay)
        setting_layout.addLayout(delay_layout)
        
        # 按鈕區
        self.btn_set_base = QPushButton("1. 手動設定基準 (Set Base)")
        self.btn_set_base.setStyleSheet("background-color: #4CAF50; color: white;")
        self.btn_set_base.clicked.connect(self.set_base_label)
        
        self.btn_auto_start = QPushButton("2. 開始自動處理 (Start Auto)")
        self.btn_auto_start.setStyleSheet("""
            QPushButton {
                background-color: #FF9800; 
                color: white; 
                font-weight: bold;
                height: 40px;
            }
            QPushButton:disabled {
                background-color: #e0e0e0; 
                color: #a0a0a0;
                font-weight: bold;
                height: 40px;
            }
        """)
        self.btn_auto_start.setEnabled(False)
        self.btn_auto_start.clicked.connect(self.toggle_auto_process)
        
        setting_layout.addWidget(self.btn_set_base)
        setting_layout.addWidget(self.btn_auto_start)
        setting_layout.addWidget(QLabel("提示: 處理中按 'E' 暫停並手動調整"))
        
        right_layout.addWidget(setting_group)
        
        # 加入主佈局 (設定比例 7:3)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)
        main_layout.addWidget(splitter)
        
        # 初始化清單
        self.refresh_list()
        self.show_current_image()

    # --- 核心邏輯區 ---

    def refresh_list(self):
        """
        更新清單顏色：
        - 紅色：無標註檔 (.txt)
        - 橘色：有標註檔，但無裁切圖 (_0.png...)
        - 綠色：標註與裁切皆完成
        """
        # 1. 取得狀態 (必須傳入 cut_dir 才能判定橘色/綠色)
        files, status_map = utils.get_dataset_status(self.img_dir, self.lbl_dir, self.cut_img_dir)
        self.img_files = files 
        
        # 2. 同步列表內容
        if self.list_widget.count() != len(files):
            self.list_widget.clear()
            self.list_widget.addItems(files)

        # 3. 更新顏色邏輯
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            filename = item.text()
            
            # 取得該檔案的狀態字典
            stat = status_map.get(filename, {'labeled': False, 'cropped': False})
            
            is_labeled = stat.get('labeled', False)
            is_cropped = stat.get('cropped', False)
            
            if not is_labeled:
                # 狀態 1：沒標註檔 -> 紅色
                item.setForeground(QColor("#FF5252")) 
            elif is_labeled and not is_cropped:
                # 狀態 2：有標註但沒切圖 -> 橘色
                item.setForeground(QColor("#FFA500")) 
            else:
                # 狀態 3：兩者皆有 -> 綠色
                item.setForeground(QColor("#4CAF50"))

    def on_item_clicked(self, item):
        """點擊清單切換圖片"""
        if self.is_auto_running: return # 自動跑的時候禁止亂點
        self.current_index = self.list_widget.row(item)
        self.show_current_image()

    def show_current_image(self):
        """顯示目前索引的圖片"""
        if 0 <= self.current_index < len(self.image_files):
            filename = self.image_files[self.current_index]
            path = os.path.join(self.img_dir, filename)

            # 取得classes.txt
            classes_list = utils.load_classes(self.lbl_dir)
            
            # 讀取並顯示
            cv_img = utils.imread_chinese(path)
            if cv_img is not None:
                # 如果有標註，畫出來給使用者看
                label_path = os.path.join(self.lbl_dir, os.path.splitext(filename)[0] + ".txt")
                if utils.is_labeled(filename, self.lbl_dir):
                    cv_img = utils.draw_labels(cv_img, label_path, classes_list) # 使用 utils 的畫圖功能
                
                pixmap = utils.convert_cv_to_pixmap(cv_img)
                # 簡單縮放以適應視窗
                scaled = pixmap.scaled(self.image_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.image_label.setPixmap(scaled)

    # --- 步驟 1: 手動設定基準 ---
    def set_base_label(self):
        """手動設定基準標註"""
        if self.current_index < 0 or self.current_index >= len(self.image_files):
            return

        filename = self.image_files[self.current_index]
        img_path = os.path.join(self.img_dir, filename)
        label_path = os.path.join(self.lbl_dir, os.path.splitext(filename)[0] + ".txt")
        
        # 準備資料
        pixmap = QPixmap(img_path)
        existing_labels = utils.read_yolo_labels(label_path)
        
        # 開啟編輯器
        dialog = RedrawDialog(pixmap, existing_labels, self.classes, self)
        
        if dialog.exec():
            # 取得編輯結果
            new_labels = dialog.get_final_labels()
            if new_labels:
                if utils.save_yolo_labels(label_path, new_labels):
                    self.base_labels = new_labels
                    
                    # --- 執行裁切存檔 ---
                    utils.clear_existing_crops(filename, self.cut_img_dir, self.classes)
                    utils.crop_and_save_by_label(img_path, new_labels, self.classes, self.cut_img_dir)
                    
                    self.refresh_list()
                    self.show_current_image()
                    #開放自動處理功能
                    self.btn_auto_start.setEnabled(True)
                    QMessageBox.information(self, "設定完成", "標註與裁切圖片已儲存。")
            else:
                QMessageBox.information(self, "處理錯誤", "無編輯結果")

    # --- 步驟 2: 自動處理流程 ---
    def toggle_auto_process(self):
        if self.is_auto_running:
            self.stop_auto("使用者停止")
        else:
            self.start_auto()

    def start_auto(self):
        # 檢查前置條件
        if not self.base_labels:
            QMessageBox.warning(self, "缺少基準", "請先執行步驟 1：手動設定一張圖片的標註作為基準。")
            return
            
        # 檢查 Anchor (特徵點)
        if self.anchor_template is None:
            current_path = os.path.join(self.img_dir, self.image_files[self.current_index])
            current_img = utils.imread_chinese(current_path)
            
            # ★ 呼叫 offset.py 選擇特徵 ★
            template, xy = select_feature_area(current_img)
            if template is None:
                return # 取消
            
            self.anchor_template = template
            self.anchor_xy = xy
        
        # 開始 Loop
        self.is_auto_running = True
        self.btn_auto_start.setText("停止處理 (執行中...)")
        self.btn_auto_start.setStyleSheet("background-color: #F44336; color: white;")
        self.list_widget.setEnabled(False) # 鎖定清單
        
        self.run_next_auto_step()

    def run_next_auto_step(self):
        if not self.is_auto_running: return

        # 1. 取得最新狀態 (傳入 cut_img_dir 才能辨識橘色)
        _, status_map = utils.get_dataset_status(self.img_dir, self.lbl_dir, self.cut_img_dir)

        # 2. 找下一個需要處理的 (紅色 或 橘色)
        next_idx = -1
        for i in range(len(self.image_files)):
            filename = self.image_files[i]
            stat = status_map.get(filename, {'labeled': False, 'cropped': False})
            
            # 邏輯：只要裁切沒完成 (cropped == False)，不論有沒有標註，都停下來處理
            # 這會同時涵蓋：
            # - 紅色 (labeled: False, cropped: False)
            # - 橘色 (labeled: True,  cropped: False)
            if not stat.get('cropped', False):
                next_idx = i
                break
        
        if next_idx == -1:
            self.stop_auto("所有圖片（含裁切）處理完成！")
            return

        # 2. 切換圖片並顯示
        self.current_index = next_idx
        self.list_widget.setCurrentRow(next_idx) # 清單跟著跑
        
        filename = self.image_files[self.current_index]
        img_path = os.path.join(self.img_dir, filename)
        current_img = utils.imread_chinese(img_path)
        
        # 3. ★ 呼叫 offset.py 計算偏移 ★
        dx, dy, conf = offset_calculation(self.anchor_template, current_img, self.anchor_xy)
        
        if dx is None:
            print(f"[{filename}] 匹配失敗")
            # 這裡可以選擇跳過，或暫停讓人處理。目前選擇跳過不存檔。
        else:
            new_labels = self.apply_offset(self.base_labels, dx, dy, current_img.shape)           
            save_path = os.path.join(self.lbl_dir, os.path.splitext(filename)[0] + ".txt")
            utils.save_yolo_labels(save_path, new_labels)
            
            # --- 自動執行裁切清空後存檔 ---
            utils.clear_existing_crops(filename, self.cut_img_dir, self.classes)
            utils.crop_and_save_by_label(img_path, new_labels, self.classes, self.cut_img_dir)
            
            self.refresh_list()
        
        # 更新畫面預覽
        self.show_current_image()

        # 6. 設定延遲
        delay = self.spin_delay.value() * 100
        if delay < 100: delay = 100
        self.process_timer.start(delay)

    def apply_offset(self, base_labels, dx, dy, img_shape):
        """將偏移量應用到基準標註"""
        h, w = img_shape[:2]
        new_labels = []
        for lbl in base_labels:
            cls, xc, yc, bw, bh = lbl
            
            # 轉像素 -> 加偏移 -> 轉回 YOLO
            px = xc * w + dx
            py = yc * h + dy
            
            n_xc = px / w
            n_yc = py / h
            new_labels.append([cls, n_xc, n_yc, bw, bh])
        return new_labels

    def stop_auto(self, msg=""):
        self.is_auto_running = False
        self.process_timer.stop()
        self.list_widget.setEnabled(True)
        self.btn_auto_start.setText("2. 開始自動處理 (Start Auto)")
        self.btn_auto_start.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold;")
        if msg:
            QMessageBox.information(self, "結束", msg)

    # --- 步驟 3: 鍵盤監聽 'E' ---
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_E and self.is_auto_running:
            # 暫停自動化
            self.process_timer.stop()
            
            # ★ 跳出 editor_dialog.py 讓使用者手動調整 ★
            filename = self.image_files[self.current_index]
            img_path = os.path.join(self.img_dir, filename)
            label_path = os.path.join(self.lbl_dir, os.path.splitext(filename)[0] + ".txt")
            
            pixmap = QPixmap(img_path)
            existing_labels = utils.read_yolo_labels(label_path)
            
            dialog = RedrawDialog(pixmap, existing_labels, self)
            if dialog.exec():
                # 修正後存檔
                new_labels = dialog.get_final_labels()
                utils.save_yolo_labels(label_path, new_labels)
                self.show_current_image()
            
            # 詢問是否繼續
            reply = QMessageBox.question(self, "暫停", "手動調整結束，是否繼續自動處理？", 
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.process_timer.start(1000)
            else:
                self.stop_auto("使用者中止")
        else:
            super().keyPressEvent(event)

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    
    # 1. 建立 QApplication 實例
    app = QApplication(sys.argv)
    
    # 2. 設定測試路徑 (請根據你的電腦實際路徑調整，或使用相對路徑)
    test_img_dir = '/Users/shengyuanshaw/Desktop/yenprotek/BoxTest/original_folder/Original_img'
    test_lbl_dir = '/Users/shengyuanshaw/Desktop/yenprotek/BoxTest/original_folder/Box01_label'
    test_cut_dir = '/Users/shengyuanshaw/Desktop/yenprotek/BoxTest/Box01_folder/Box01_img'

    # 3. 確保測試資料夾存在，否則會報錯
    if not os.path.exists(test_img_dir):
        os.makedirs(test_img_dir, exist_ok=True)
        print(f"提示：已自動建立圖片資料夾 {test_img_dir}，請放入測試圖片。")
    if not os.path.exists(test_lbl_dir):
        os.makedirs(test_lbl_dir, exist_ok=True)
        # 自動建立一個空的 classes.txt 避免讀取失敗
        with open(os.path.join(test_lbl_dir, "classes.txt"), "w") as f:
            f.write("Header_A\nHeader_B\nTable_Content")
        print(f"提示：已自動建立標註資料夾與 classes.txt。")

    # 4. 初始化並顯示對話框
    # 注意：因為這是 QDialog，我們可以用 show() 或 exec()
    # 這裡用 exec() 會阻斷主程式直到視窗關閉
    try:
        dialog = AutoLabelingDialog(img_dir=test_img_dir, lbl_dir=test_lbl_dir, cut_img_dir=test_cut_dir)
        dialog.show()
        
        print("--- 測試啟動成功 ---")
        print(f"圖片路徑: {test_img_dir}")
        print(f"標註路徑: {test_lbl_dir}")
        print(f"裁切路徑: {test_cut_dir}")
        print("提示：點擊 '手動設定基準' 來開始測試裁切功能。")
        
        sys.exit(app.exec())
    except Exception as e:
        print(f"啟動失敗: {e}")