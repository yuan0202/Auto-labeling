"""
3_auto_generate_label.src.ocr_tuning_ui 的 Docstring
TuningDialog: 此GUI設定二值化的數值
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QSlider, QCheckBox, QPushButton, QWidget)
from PyQt6.QtCore import Qt, pyqtSignal

class TuningDialog(QDialog):
    # 定義訊號，傳送參數字典回主視窗
    params_changed = pyqtSignal(dict)

    def __init__(self, initial_params, parent=None):
        super().__init__(parent)
        self.setWindowTitle("二值化參數調整")
        self.resize(400, 650)
        
        layout = QVBoxLayout()
        self.sliders = {}
        
        # 定義所有控制項的配置
        # 格式: (顯示名稱, 參數Key, 最小值, 最大值, 縮放比例/類型)
        # scale=1 (整數), scale=0.1 (浮點數), type='raw' (不需轉換)
        controls_config = [
            # HSV
            ("Hue Min", 'h_min', 0, 179, 1),
            ("Hue Max", 'h_max', 0, 179, 1),
            ("Sat Min", 's_min', 0, 255, 1),
            ("Sat Max", 's_max', 0, 255, 1),
            ("Val Min", 'v_min', 0, 255, 1),
            ("Val Max", 'v_max', 0, 255, 1),
            
            # Gamma: 1~30 代表 0.1~3.0
            ("Gamma (x0.1)", 'gamma', 1, 30, 0.1),
            
            # Shear: 支援負值，直接對應角度
            ("Shear (傾斜)", 'shear', -45, 45, 1),

            # [新增] 高斯濾波: 0~15
            ("Gaussian Blur", 'blur_k', 0, 15, 1)
        ]

        # 動態生成 Slider
        for label_text, key, min_v, max_v, scale in controls_config:
            row = QHBoxLayout()
            
            # 取得初始值並轉換為 Slider 數值
            raw_val = initial_params.get(key, 0)
            slider_val = int(raw_val)
            
            # 特殊處理 Gamma (float -> int slider)
            if scale == 0.1:
                slider_val = int(initial_params.get(key, 1.0) * 10)
            
            # 建立標籤
            lbl = QLabel(f"{label_text}: {raw_val}")
            lbl.setFixedWidth(140)
            
            # 建立滑桿
            sld = QSlider(Qt.Orientation.Horizontal)
            sld.setRange(min_v, max_v)
            sld.setValue(slider_val)
            
            # 連接訊號 (利用 Closure 綁定變數)
            # 注意: 這裡傳遞 scale 參數進去以便在顯示時正確還原數值
            sld.valueChanged.connect(
                lambda v, k=key, l=lbl, txt=label_text, s=scale: self.on_change(v, k, l, txt, s)
            )
            
            row.addWidget(lbl)
            row.addWidget(sld)
            layout.addLayout(row)
            
            # 儲存引用以便 emit 使用
            self.sliders[key] = (sld, scale)

        # 底部控制區
        bottom_layout = QHBoxLayout()
        self.chk_auto = QCheckBox("即時預覽")
        self.chk_auto.setChecked(True)
        
        btn_close = QPushButton("隱藏面板")
        btn_close.clicked.connect(self.hide)
        
        bottom_layout.addWidget(self.chk_auto)
        bottom_layout.addStretch()
        bottom_layout.addWidget(btn_close)
        
        layout.addLayout(bottom_layout)
        self.setLayout(layout)

    def on_change(self, value, key, label_widget, label_text, scale):
        """ 當滑桿數值改變時更新 Label 並決定是否送出訊號 """
        display_val = value
        
        if scale == 0.1:
            display_val = round(value * 0.1, 1)
        
        # 特殊顯示邏輯: 高斯濾波如果是偶數(且不為0)，雖然 Slider 可能是偶數，
        # 但後端處理會強制轉奇數，這裡顯示 Slider 值即可，或是顯示 "Off"
        if key == 'blur_k' and value == 0:
            label_widget.setText(f"{label_text}: Off")
        else:
            label_widget.setText(f"{label_text}: {display_val}")

        if self.chk_auto.isChecked():
            self.emit_params()

    def emit_params(self):
        """ 收集所有 Slider 數值並送出 """
        p = {}
        for key, (slider, scale) in self.sliders.items():
            val = slider.value()
            
            if scale == 0.1:
                p[key] = val / 10.0
            else:
                p[key] = val
                
        self.params_changed.emit(p)
    
    def closeEvent(self, event):
        self.hide()
        event.ignore()