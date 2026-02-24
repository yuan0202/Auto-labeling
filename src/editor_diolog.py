from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QScrollArea, QLabel, QHBoxLayout, QInputDialog, QMessageBox
from PyQt6.QtCore import Qt, QRect, QPoint, QSize
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QFont, QBrush, QWheelEvent # ★ 記得引入 QWheelEvent

class RedrawDialog(QDialog):
    def __init__(self, pixmap, existing_labels=None, classes=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("編輯模式 - 滾輪可縮放 (Ctrl+滾輪)")
        self.resize(1200, 800)
        
        self.original_pixmap = pixmap
        self.scale_factor = 1.0 # ★ 新增：縮放比例，預設 1.0 (100%)
        self.classes = classes if classes else ["default"]
        
        # 格式: [[cls, QRect(原始座標)], ...] 
        # ★ 注意：這裡存的一定要是「原始圖片」的座標，不要存縮放後的
        self.labels_metadata = [] 
        
        if existing_labels:
            img_w, img_h = pixmap.width(), pixmap.height()
            for lbl in existing_labels:
                cls_id_raw, xc, yc, w, h = lbl
                
                # ID 轉 Name
                try:
                    idx = int(cls_id_raw)
                    cls_display = self.classes[idx] if 0 <= idx < len(self.classes) else str(cls_id_raw)
                except:
                    cls_display = str(cls_id_raw)

                # 轉回原始像素座標
                x1 = int((xc - w/2) * img_w)
                y1 = int((yc - h/2) * img_h)
                # ★ 這裡存的是原始大小的 Rect
                rect = QRect(x1, y1, int(w * img_w), int(h * img_h))
                self.labels_metadata.append([cls_display, rect])

        self.start_pos = None
        self.current_dragging_rect = None

        layout = QVBoxLayout(self)
        
        # 畫布區域
        self.scroll_area = QScrollArea()
        self.canvas = QLabel()
        self.canvas.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft) # ★ 對齊左上
        self.scroll_area.setWidget(self.canvas)
        self.scroll_area.setWidgetResizable(True) # ★ 允許內容調整大小
        layout.addWidget(self.scroll_area)

        # 按鈕區 (保持不變)
        btn_layout = QHBoxLayout()
        self.btn_clear = QPushButton("清除所有框")
        self.btn_ok = QPushButton("完成並存檔")
        self.btn_cancel = QPushButton("取消修改")
        
        self.btn_clear.setStyleSheet("background-color: #f44336; color: white;")
        self.btn_ok.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        
        btn_layout.addWidget(self.btn_clear)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_ok)
        layout.addLayout(btn_layout)

        self.btn_clear.clicked.connect(self.clear_all)
        self.btn_ok.clicked.connect(self.check_save)
        self.btn_cancel.clicked.connect(self.reject)

        self.canvas.mousePressEvent = self.on_press
        self.canvas.mouseMoveEvent = self.on_move
        self.canvas.mouseReleaseEvent = self.on_release
        
        self.update_canvas_display()

    # ★ 新增：滾輪事件處理
    def wheelEvent(self, event: QWheelEvent):
        # 為了避免跟捲動衝突，通常按住 Ctrl 才縮放，或直接縮放看你習慣
        # 這裡設定：直接滾動就是縮放
        if event.angleDelta().y() > 0:
            self.scale_factor *= 1.1 # 放大 10%
        else:
            self.scale_factor *= 0.9 # 縮小 10%
            
        # 限制縮放範圍 (例如 0.1倍 ~ 5倍)
        self.scale_factor = max(0.1, min(self.scale_factor, 5.0))
        
        self.update_canvas_display()

    def update_canvas_display(self):
        """根據目前的 scale_factor 重新繪製"""
        
        # 1. 產生縮放後的圖片
        new_size = self.original_pixmap.size() * self.scale_factor
        display_pixmap = self.original_pixmap.scaled(
            new_size, 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )
        
        painter = QPainter(display_pixmap)
        font = QFont("Arial", 10 + int(2 * self.scale_factor), QFont.Weight.Bold) # 字體隨縮放調整
        painter.setFont(font)

        # 2. 繪製已存在的框 (需將原始座標 x 縮放比例)
        for cls, original_rect in self.labels_metadata:
            # ★ 關鍵：把原始座標 乘上 縮放比例
            scaled_rect = QRect(
                int(original_rect.x() * self.scale_factor),
                int(original_rect.y() * self.scale_factor),
                int(original_rect.width() * self.scale_factor),
                int(original_rect.height() * self.scale_factor)
            )

            # 畫框
            painter.setPen(QPen(QColor(0, 255, 0), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(scaled_rect)
            
            # 畫文字
            text = f"{cls}"
            fm = painter.fontMetrics()
            text_w = fm.horizontalAdvance(text) + 6
            text_h = fm.height() + 2
            
            if scaled_rect.top() - text_h < 0:
                text_origin = scaled_rect.topLeft() + QPoint(0, text_h)
            else:
                text_origin = scaled_rect.topLeft()
                
            text_rect = QRect(text_origin.x(), text_origin.y() - text_h + 2, text_w, text_h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(0, 0, 0, 150)))
            painter.drawRect(text_rect)
            
            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)
            
        # 3. 繪製正在拖曳的框 (current_dragging_rect 已經是螢幕座標，不需要乘縮放)
        if self.current_dragging_rect:
            painter.setPen(QPen(QColor(255, 0, 0), 2, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.current_dragging_rect)
            
        painter.end()
        
        self.canvas.setPixmap(display_pixmap)
        self.canvas.adjustSize() # ★ 重要：讓 Label 撐開 ScrollArea

    # --- 滑鼠事件 (需處理座標換算) ---

    def on_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # 記錄螢幕座標
            self.start_pos = event.position().toPoint()

    def on_move(self, event):
        if self.start_pos:
            # 拖曳時，current_dragging_rect 存的是「螢幕座標」，方便直接畫
            self.current_dragging_rect = QRect(self.start_pos, event.position().toPoint()).normalized()
            self.update_canvas_display()

    def on_release(self, event):
        if self.start_pos:
            end_pos = event.position().toPoint()
            # 螢幕上的框
            screen_rect = QRect(self.start_pos, end_pos).normalized()
            
            # ★ 關鍵：將螢幕座標 除以 縮放比例 = 原始圖片座標
            original_rect = QRect(
                int(screen_rect.x() / self.scale_factor),
                int(screen_rect.y() / self.scale_factor),
                int(screen_rect.width() / self.scale_factor),
                int(screen_rect.height() / self.scale_factor)
            )

            # 選擇類別
            cls_name, ok = QInputDialog.getItem(self, "選擇類別", "請選擇標籤:", self.classes, 0, False)
            
            if ok and cls_name:
                # 存入的是原始座標
                self.labels_metadata.append([cls_name, original_rect])
            
            self.start_pos = None
            self.current_dragging_rect = None
            self.update_canvas_display()

    # ... (clear_all, check_save, get_final_labels 保持原本的邏輯) ...
    
    def clear_all(self):
        if QMessageBox.question(self, "確認", "清除所有框？") == QMessageBox.StandardButton.Yes:
            self.labels_metadata = []
            self.update_canvas_display()

    def keyPressEvent(self, event):
        """
        處理鍵盤事件：
        - Enter / Return: 觸發儲存 (相當於按下 btn_ok)
        - Esc: 觸發取消 (相當於按下 btn_cancel)
        """
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            # 模擬點擊 "完成並存檔" 按鈕
            self.check_save()  
            event.accept()
        elif event.key() == Qt.Key.Key_Escape:
            # 模擬點擊 "取消" 按鈕 (QDialog 預設行為也是 reject，但明確寫出來比較保險)
            self.reject()
            event.accept()
        else:
            # 其他按鍵交給父類別處理 (例如 Tab 切換焦點)
            super().keyPressEvent(event)

    def check_save(self):
        if QMessageBox.question(self, "確認", "確定儲存？") == QMessageBox.StandardButton.Yes:
            self.accept()

    def get_final_labels(self):
        # 這裡 labels_metadata 已經是原始座標了，直接轉 YOLO 即可
        img_w = self.original_pixmap.width()
        img_h = self.original_pixmap.height()
        yolo_list = []
        for cls_name, rect in self.labels_metadata:
            # 轉換 Name -> ID
            if cls_name in self.classes:
                cls_id = self.classes.index(cls_name)
            else:
                cls_id = int(cls_name) if cls_name.isdigit() else 0
            
            xc = (rect.x() + rect.width() / 2) / img_w
            yc = (rect.y() + rect.height() / 2) / img_h
            w = rect.width() / img_w
            h = rect.height() / img_h
            yolo_list.append([cls_id, xc, yc, w, h])
            
        return yolo_list