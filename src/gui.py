"""
gui.py - 標註工具基礎介面佈局模組

本模組定義了 LabelingWindow 類別，負責建構 PyQt6 圖形使用者介面 (GUI)。
設計核心為「動態適應性面板」，能根據選取的工作模式 (標註、預覽、OCR) 即時調整控制元件的顯示狀態。

介面構成元件:
    1. 圖片顯示區 (Left): 
       - 基於 QScrollArea 與 QLabel，支援大圖滾動查看。
       - 整合 OpenCV 繪圖結果，即時顯示標註框。
    2. 控制面板 (Right):
       - 專案路徑設定: 包含 Root 目錄輸入與結構檢查狀態標籤。
       - 模式切換區: 動態顯示/隱藏「自動預覽設定」、「OCR 辨識選項」等元件。
       - 圖片清單: 使用 QListWidget，配合 utils 模組實現紅/橘/綠三色狀態標記。
       - 導覽按鈕: 提供 上一張/下一張 與 自定義主功能按鈕 (顏色與文字依模式切換)。

關鍵機制:
    - 模式感應器 (on_mode_changed): 偵測 WORKING_MODE ID，切換 PREVIEW 與 LABELING 專屬 UI 狀態。
    - 樣式管理器 (apply_button_style): 統一管理按鈕的視覺回饋，提升操作直覺性。
    - 信號連動: 確保 UI 狀態 (如自動播放間隔) 與背景邏輯 (QTimer) 的同步。

作者: shengyuanshaw (Yenprotek)
最後更新日期: 2026/02/24
"""
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QListWidget, QLabel, QScrollArea,
                             QLineEdit, QComboBox, QCheckBox, QGroupBox, QSpinBox)
from PyQt6.QtCore import Qt
import constants
from constants import WORKING_MODE

class LabelingWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python 標註工具")
        self.resize(1200, 800)

        # 主視窗中心元件
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)

        # --- 左側：圖片顯示區 ---
        self.image_container = QVBoxLayout()
        self.scroll_area = QScrollArea()
        self.image_label = QLabel("請選擇路徑後開始工作")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet(
            "background-color: #2b2b2b; color: white; font-size: 18px;")
        self.scroll_area.setWidget(self.image_label)
        self.scroll_area.setWidgetResizable(True)
        self.image_container.addWidget(self.scroll_area)
        self.main_layout.addLayout(self.image_container, stretch=4)

        # --- 右側：控制面板 ---
        self.panel_layout = QVBoxLayout()

        # --- 1.專案根目錄設定區 ---
        path_group = QGroupBox("專案路徑設定")
        path_layout = QVBoxLayout()

        # 第一行：選取根目錄
        
        self.root_path_row_name = QLabel("專案根目錄 (Root):")
        path_layout.addWidget(self.root_path_row_name)
        root_path_row = QHBoxLayout()
        self.edit_root_path = QLineEdit()
        self.edit_root_path.setPlaceholderText("請選original_img folder")
        self.btn_browse_root = QPushButton("瀏覽")
        root_path_row.addWidget(self.edit_root_path)
        root_path_row.addWidget(self.btn_browse_root)
        path_layout.addLayout(root_path_row)

        # 第二行：結構檢查狀態 (視覺反饋)
        self.lbl_struct_status = QLabel("狀態: 等待選取路徑...")
        self.lbl_struct_status.setStyleSheet("color: gray;")
        path_layout.addWidget(self.lbl_struct_status)

        path_group.setLayout(path_layout)
        self.panel_layout.addWidget(path_group)

        # 2. 模式與功能區
        mode_group = QGroupBox("模式與功能")
        self.mode_layout = QVBoxLayout()

        self.mode_layout.addWidget(QLabel("工作模式:"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(list(constants.WORKING_MODE.keys()))
        self.mode_layout.addWidget(self.combo_mode)

        # --- 功能選項：編寫模式專用(數字辨識功能) ---
        self.check_digit_ocr = QCheckBox("啟用數字辨識功能(OCR)")
        self.check_digit_ocr.setChecked(True)
        self.mode_layout.addWidget(self.check_digit_ocr)
        self.check_digit_ocr.setVisible(False)#hidden

        # --- 功能選項：編寫模式專用(OCR辨識模式變更) ---
        self.label_ocr_model = QLabel("OCR辨識模式:")
        self.mode_layout.addWidget(self.label_ocr_model)
        self.label_ocr_model.setVisible(False)#hidden
        self.combo_ocr_type = QComboBox()
        self.combo_ocr_type.addItems(constants.OCR_MODE_CONFIG.keys())
        self.combo_ocr_type.setVisible(False)#hidden
        self.mode_layout.addWidget(self.combo_ocr_type)

        # --- 功能選項：預覽模式專用 ---
        self.auto_preview_container = QWidget()  # 用一個小容器方便一起隱藏/顯示
        auto_v_layout = QVBoxLayout(self.auto_preview_container)
        auto_v_layout.setContentsMargins(0, 0, 0, 0)

        self.check_show_boxes = QCheckBox("顯示框架")
        self.check_show_boxes.setEnabled(False)  # 預設禁用，直到有標註路徑
        auto_v_layout.addWidget(self.check_show_boxes)

        self.check_auto_preview = QCheckBox("啟用自動預覽")
        auto_v_layout.addWidget(self.check_auto_preview)

        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("間隔秒數:"))
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(1, 60)  # 1~60 秒
        self.spin_interval.setValue(3)     # 預設 3 秒
        self.spin_interval.setSuffix(" 秒")
        interval_layout.addWidget(self.spin_interval)
        auto_v_layout.addLayout(interval_layout)

        self.mode_layout.addWidget(self.auto_preview_container)

        mode_group.setLayout(self.mode_layout)
        self.panel_layout.addWidget(mode_group)

        # 3. 圖片列表區
        self.panel_layout.addWidget(QLabel("圖片清單:"))
        self.label_list = QListWidget()
        self.panel_layout.addWidget(self.label_list)

        # 4. 控制按鈕
        self.btn_prev = QPushButton("上一張")
        self.btn_next = QPushButton("下一張")
        self.btn_main_action = QPushButton("開始自動標註")
        self.btn_main_action.setEnabled(False)
        self.btn_main_action.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; 
                color: white; 
                height: 40px; 
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:disabled {
                background-color: #e0e0e0; 
                color: #a0a0a0;
            }
        """)

        self.panel_layout.addWidget(self.btn_prev)
        self.panel_layout.addWidget(self.btn_next)
        self.panel_layout.addWidget(self.btn_main_action)

        self.main_layout.addLayout(self.panel_layout, stretch=1)

        # --- 訊號連接 (Signals) ---
        self.combo_mode.currentIndexChanged.connect(self.on_mode_changed)
        self.check_auto_preview.toggled.connect(self.on_auto_preview_toggled)
        self.check_digit_ocr.toggled.connect(self.on_ocr_model_toggled)

    def on_mode_changed(self):
        """
        Improved Mode Switcher: 
        Uses mode IDs to determine UI state, making it compatible with all stages.
        """
        selected_text = self.combo_mode.currentText()
        mode_id = WORKING_MODE.get(selected_text, "")

        # 1. Determine State Category
        # Check if the internal ID contains 'PREVIEW' or 'LABELING'
        is_preview = "PREVIEW" in mode_id
        is_labeling = "LABELING" in mode_id
        is_ocr = "OCR" in mode_id

        # OCR controls only show in Labeling mode AND when it's an OCR stage
        self.check_digit_ocr.setVisible(is_labeling and is_ocr)
        self.label_ocr_model.setVisible(is_labeling and is_ocr)
        if hasattr(self, 'combo_ocr_type'):
            self.combo_ocr_type.setVisible(is_labeling and is_ocr)

        # 3. Dynamic Button Styling
        if is_preview:
            self.apply_button_style(
                text="修改標註資料 (Modify)", 
                color="#2196F3"  # Blue
            )
        else:
            self.apply_button_style(
                text="開始自動標註 (Start Auto)", 
                color="#4CAF50"  # Green
            )
        
        # Refresh the list because different stages look at different folders
        self.refresh_image_list()

    def apply_button_style(self, text, color):
        """Helper to avoid repeating CSS strings"""
        self.btn_main_action.setText(text)
        self.btn_main_action.setStyleSheet(f"""
            background-color: {color}; 
            color: white; 
            height: 40px; 
            font-weight: bold;
            border-radius: 4px;
        """)

    def on_auto_preview_toggled(self, checked):
        """自動預覽勾選時，才允許修改秒數"""
        self.spin_interval.setEnabled(checked)

    
    def on_ocr_model_toggled(self, checked):
        self.combo_ocr_type.setEnabled(self.check_digit_ocr.isChecked())
