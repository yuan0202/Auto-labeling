"""
utils.py - 影像處理與 YOLO 標註輔助工具集

本模組封裝了所有與檔案系統、OpenCV 影像處理以及標註格式轉換相關的靜態工具函數。
核心設計考量在於支援「中文路徑相容性」以及「標註結果的視覺化」。

主要功能分類:
    1. 檔案與路徑處理:
       - imread_chinese / imwrite_chinese: 解決 OpenCV 預設不支援 UTF-8 編碼路徑的問題。
       - get_image_files: 掃描並過濾常見影像格式，確保排序一致。
       - get_dataset_status: 整合標註狀態偵測，為 UI 提供紅/橘/綠三色狀態依據。
    2. YOLO 標註邏輯:
       - read_yolo_labels / save_yolo_labels: 負責 YOLO (.txt) 格式與 Python 列表間的轉換。
       - id_to_name / name_to_id: 處理 classes.txt 與標註索引間的對映。
    3. 影像增強與繪圖:
       - draw_labels: 自動偵測圖片尺寸，支援「一般模式」與「吊牌模式(Padding)」，解決小圖標籤重疊問題。
       - apply_shear / trim_whitespace: 用於特徵提取前的影像校正與去背。
    4. 裁切與管理:
       - crop_and_save_by_label: 根據標註座標自動裁切子圖。
       - clear_existing_crops: 在重新標註時同步清理舊有的裁切緩存，維持資料一致性。

作者: shengyuanshaw (Yenprotek)
最後更新日期: 2026/02/24
"""

import cv2
import numpy as np
import os
from PyQt6.QtGui import QImage, QPixmap


def imread_chinese(path):
    """
    支援中文路徑的影像讀取函數。
    原理：先將檔案讀取為二進制流，再透過 numpy 轉為 OpenCV 矩陣。
    """
    try:
        # 使用 np.fromfile 讀取原始位元組，避免 path 解析編碼錯誤
        img_array = np.fromfile(path, dtype=np.uint8)
        # 將位元組解碼為 OpenCV 影像格式
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        print(f"讀取圖片發生錯誤: {e}")
        return None
    
def imwrite_chinese(path, img):
    """
    支援中文路徑的影像儲存函數。
    當你之後需要儲存辨識結果或處理後的影像時會用到。
    """
    try:
        ext = os.path.splitext(path)[-1]
        result, nparray = cv2.imencode(ext, img)
        if result:
            nparray.tofile(path)
            return True
    except Exception as e:
        print(f"儲存圖片發生錯誤: {e}")
    return False

def get_image_files(directory):
    """
    掃描資料夾，找出所有支援的圖片格式，並依照名稱排序。
    """
    valid_extensions = ('.jpg', '.jpeg', '.png', '.bmp',
                        '.webp', '.tif', '.tiff')
    if not directory or not os.path.exists(directory):
        return []

    # 取得檔案清單並過濾副檔名
    files = [f for f in os.listdir(directory)
             if f.lower().endswith(valid_extensions)]

    # 排序確保「下一張」的順序邏輯正確
    return sorted(files)

def load_classes(label_dir):
    """
    讀取 classes.txt,回傳類別名稱的 List。
    index (行數) 就是 ID
    例如: ['0', '1', 'dot']
    對應 ID: 0 -> 0, 1 -> 1, 2 -> dot
    """
    path = os.path.join(label_dir, "classes.txt")
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            # 去除換行符號並過濾空行
            return [line.strip() for line in f.readlines() if line.strip()]
    
    # 如果找不到檔案，回傳預設值，避免程式崩潰
    return ["default"]

def load_templates(id):
    # 1. 取得目前這隻程式 (main.py) 的絕對路徑
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # 2. 組合出圖片的路徑
    TEMPLATE_DIR = os.path.join(BASE_DIR, 'assets', 'templates')
    file_path = os.path.join(TEMPLATE_DIR, f'template_{id}.png')

    if os.path.exists(file_path):
        return cv2.imread(file_path, 0)
    else:
        print(f"Warning: {file_path} not found")


def id_to_name(cls_id, class_list):
    """把 數字 ID (int/str) 轉成 名稱 (str)"""
    try:
        idx = int(cls_id)
        if 0 <= idx < len(class_list):
            return class_list[idx]
    except ValueError:
        pass
    return str(cls_id) # 如果找不到或轉失敗，回傳原本的數字字串

def name_to_id(cls_name, class_list):
    """把 名稱 (str) 轉成 數字 ID (int)"""
    # 確保 cls_name 是字串格式以利比對
    cls_name = str(cls_name)
    
    # 1. 如果名稱在清單內，直接回傳索引 (int)
    if cls_name in class_list:
        return class_list.index(cls_name)
    
    # 2. 如果名稱不在清單內，但它本身就是數字字串 (例如 "5")
    if cls_name.isdigit():
        return int(cls_name)
        
    # 3. 真的找不到時，回傳 -1 
    # 回傳 -1 比回傳 0 好，因為 0 通常代表數字「0」，回傳 -1 可以讓主程式知道「出錯了」
    return -1

def is_labeled(image_filename, label_dir):
    """
    檢查該圖片是否已有對應的標註檔
    """
    if not label_dir: return False
    
    # 確保副檔名被換成 .txt
    label_name = os.path.splitext(image_filename)[0] + ".txt"
    full_path = os.path.join(label_dir, label_name)
    
    # 檢查檔案是否存在
    return os.path.exists(full_path)

def is_cropped(image_filename, cut_dir):
    """
    檢查該圖片是否已經產生過裁切後的子圖。
    適用場景：所有裁切圖都堆在同一個資料夾 (cut_dir) 內。
    """
    if not cut_dir or not os.path.exists(cut_dir):
        return False
        
    base_name = os.path.splitext(image_filename)[0]
    
    # 直接在該資料夾內尋找有無符合 "圖片名_" 開頭的檔案
    try:
        for f in os.listdir(cut_dir):
            if f.startswith(f"{base_name}_"):
                return True
    except OSError:
        return False
        
    return False

def convert_cv_to_pixmap(cv_img):
    """
    將 OpenCV 的 BGR 格式轉換為 PyQt 顯示用的 QPixmap。
    """
    if cv_img is None:
        return None

    # OpenCV 預設是 BGR，但 PyQt/QImage 預設是 RGB
    rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)

    # 取得影像維度
    height, width, channels = rgb_image.shape
    bytes_per_line = channels * width

    # 建立 QImage 物件
    q_img = QImage(
        rgb_image.data,
        width,
        height,
        bytes_per_line,
        QImage.Format.Format_RGB888
    )

    return QPixmap.fromImage(q_img)

def read_yolo_labels(label_path):
    """
    讀取 YOLO 格式，回傳列表 [[cls, xc, yc, w, h], ...]
    """
    labels = []
    if os.path.exists(label_path):
        with open(label_path, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 5:
                    labels.append([parts[0]] + [float(x) for x in parts[1:]])
    return labels

def get_bg_color(img):
    """
    單純偵測圖片背景色 (0 或 255)
    """
    h, w = img.shape[:2]
    corners = [
        img[0, 0], img[0, w-1], 
        img[h-1, 0], img[h-1, w-1]
    ]
    return int(max(set(corners), key=corners.count))

def get_dataset_status(image_dir, label_dir, cut_dir=None):
    """
    統一取得目前的資料集狀態 (整合標註與裁切檢查)
    """
    if not image_dir:
        return [], {}

    # 1. 取得排序好的圖片列表
    files = get_image_files(image_dir)
    
    # 2. 建立狀態字典
    status_map = {}
    for f in files:
        labeled = is_labeled(f, label_dir)
        
        # 邏輯：只有在 labeled 為 True 時，去檢查 cut_dir 是否有圖
        # 如果有標註但沒切圖，狀態會是 {'labeled': True, 'cropped': False} -> 對應橘色
        cropped = False
        if labeled and cut_dir:
            cropped = is_cropped(f, cut_dir)
            
        status_map[f] = {
            'labeled': labeled,
            'cropped': cropped
        }
        
    return files, status_map

def save_yolo_labels(label_path, labels):
    """
    將修改後的列表存回檔案 (包含錯誤處理)
    """
    try:
        with open(label_path, 'w', encoding='utf-8') as f:
            for lbl in labels:
                # 確保數值格式正確 (class id, x, y, w, h)
                line = f"{lbl[0]} {lbl[1]:.6f} {lbl[2]:.6f} {lbl[3]:.6f} {lbl[4]:.6f}\n"
                f.write(line)
        return True # 寫入成功回傳 True
        
    except Exception as e:
        print(f"寫入標註檔失敗: {e}") # 在終端機印出錯誤原因方便除錯
        return False # 寫入失敗回傳 False


def draw_labels(cv_img, label_path, classes=None):
    if not os.path.exists(label_path) or cv_img is None:
        return cv_img

    img_h, img_w = cv_img.shape[:2]
    
    # 如果高度小於 150px，執行動態擴展邊界模式
    if img_h < 150:
        return _draw_with_dynamic_padding(cv_img, label_path, classes)
    else:
        return _draw_with_mask(cv_img, label_path, classes)

def _draw_with_dynamic_padding(cv_img, label_path, classes):
    """ 小圖模式：新增與原圖頂部顏色一致的區域 """
    # 增加 padding 高度，給標籤重疊時留出跳階空間 (100px 較穩)
    padding_h = 100 
    img_h_orig, img_w = cv_img.shape[:2]
    
    # 1. 取得原圖最頂部的顏色 (採樣第一行)
    top_edge = cv_img[0:1, :, :] if len(cv_img.shape) == 3 else cv_img[0:1, :]
    avg_color = np.mean(top_edge, axis=(0, 1))
    
    # 2. 建立與原圖色調一致的填充區
    if len(cv_img.shape) == 3:
        padding = np.full((padding_h, img_w, 3), avg_color, dtype=np.uint8)
    else:
        padding = np.full((padding_h, img_w), avg_color, dtype=np.uint8)
    
    #3.將padding圖層放置於cv_img上方
    draw_img = cv2.vconcat([padding, cv_img])

    # 3. 繪製標註 (y_offset 確保框線位置正確)
    _process_yolo_file(label_path, img_w, img_h_orig, draw_img, classes, 
                       y_offset=padding_h, enable_padding = True)
    return draw_img

def _draw_with_mask(cv_img, label_path, classes, alpha=0.5):
    img_h, img_w = cv_img.shape[:2]
    overlay = cv_img.copy()
    _process_yolo_file(label_path, img_w, img_h, overlay, classes)
    return cv2.addWeighted(overlay, alpha, cv_img, 1 - alpha, 0)

def _process_yolo_file(label_path, image_width, image_height, target_image, class_names, y_offset=0, enable_padding=False):
    """ 
    繪製 YOLO 標註框與標籤
    
    參數:
    - enable_padding: 
        True (吊牌模式): 文字顯示在頂部填充區，並畫線連到紅框中心。
        False (一般模式): 文字直接顯示在紅框左上角。
    - y_offset: 
        當啟用 Padding 時，這通常等於 padding 的高度 ，
        用來將紅框原本的 Y 座標向下推移。
    """
    
    # --- 1. 基礎設定 ---
    scale_factor = image_width / 1000.0 
    font_scale = max(0.4, 0.5 * (scale_factor if scale_factor > 0 else 1))
    boxex_font_thickness = 1 if enable_padding else 3
    text_font_thickness = 1
    font_face = cv2.FONT_HERSHEY_SIMPLEX
    
    # 顏色定義 (BGR 格式)
    color_red_box = (0, 0, 255)       # 紅色框
    color_leader_line = (200, 200, 200) # 淺灰色引導線
    color_text = (0, 0, 0)            # 黑色文字
    color_background_white = (255, 255, 255) # 白色背景
    color_border_black = (0, 0, 0)    # 黑色邊框

    # 吊牌模式專用：文字在 Padding 區的基準高度
    padding_text_base_y = int(y_offset / 2) + 5
    
    # 吊牌模式專用：紀錄已佔用的文字區間，防止重疊 [(start_x, end_x, level), ...]
    occupied_text_intervals = [] 

    try:
        with open(label_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            
        for line in lines:
            parts = line.strip().split()
            if len(parts) < 5:
                continue
                
            class_id = int(parts[0])
            relative_center_x, relative_center_y, relative_width, relative_height = map(float, parts[1:5])

            # --- 2. 座標轉換 (YOLO 相對座標 -> 像素絕對座標) ---
            # 計算邊界框 (Bounding Box)
            box_width = relative_width * image_width
            box_height = relative_height * image_height
            
            # 左上角座標 (Top-Left)
            box_x1 = int((relative_center_x * image_width) - (box_width / 2))
            box_y1 = int((relative_center_y * image_height) - (box_height / 2)) + y_offset
            
            # 右下角座標 (Bottom-Right)
            box_x2 = int((relative_center_x * image_width) + (box_width / 2))
            box_y2 = int((relative_center_y * image_height) + (box_height / 2)) + y_offset
            
            # 中心點座標 (Center)
            box_center_x = int(relative_center_x * image_width)
            box_center_y = int(relative_center_y * image_height) + y_offset

            # 取得類別名稱
            label_text = class_names[class_id] if class_names and class_id < len(class_names) else f"ID:{class_id}"
            
            # 計算文字標籤的寬高
            (text_width, text_height), _ = cv2.getTextSize(label_text, font_face, font_scale, boxex_font_thickness)

            # --- 3. 繪製紅色邊框 (所有模式通用) ---
            cv2.rectangle(target_image, (box_x1, box_y1), (box_x2, box_y2), color_red_box, boxex_font_thickness)
            
            # --- 4. 根據模式繪製標籤 ---
            pad_margin = 4  # 文字背景的留白大小

            if enable_padding:
                # ==========================
                # 模式 A: 吊牌模式 (Tag Mode)
                # ==========================

                # 計算文字在頂部 Padding 區的位置 (水平置中於紅框中心)
                text_start_x = box_center_x - (text_width // 2)
                text_end_x = box_center_x + (text_width // 2)
                
                # 防重疊邏輯：檢查水平區間是否已被佔用
                current_level = 0
                for occupied_start, occupied_end, occupied_level in occupied_text_intervals:
                    # 判斷是否重疊 (給予 2px 緩衝)
                    if not (text_end_x < occupied_start - 2 or text_start_x > occupied_end + 2):
                        if current_level <= occupied_level:
                            current_level = occupied_level + 1
                
                occupied_text_intervals.append((text_start_x, text_end_x, current_level))

                # 計算最終文字 Y 座標 (錯開高度)
                final_text_y = padding_text_base_y + (current_level * 18) 
                
                # 定義引導線的轉折點 (Padding 邊緣)
                anchor_y = y_offset - 2 

                # (A) 畫引導線：中心 -> Padding 邊緣
                cv2.line(target_image, (box_center_x, box_center_y), (box_center_x, anchor_y), color_leader_line, 1)
                
                # (B) 畫引導線：Padding 邊緣 -> 文字底部 (若距離夠遠才畫)
                if abs(final_text_y - anchor_y) > 5:
                    cv2.line(target_image, (box_center_x, anchor_y), (box_center_x, final_text_y + 2), color_leader_line, 1)

                # (C) 畫文字背景 (白底黑框)
                cv2.rectangle(target_image, 
                              (text_start_x - pad_margin, final_text_y - text_height - pad_margin), 
                              (text_end_x + pad_margin, final_text_y + pad_margin), 
                              color_background_white, -1)
                cv2.rectangle(target_image, 
                              (text_start_x - pad_margin, final_text_y - text_height - pad_margin), 
                              (text_end_x + pad_margin, final_text_y + pad_margin), 
                              color_border_black, 1)

                # (D) 寫入文字
                cv2.putText(target_image, label_text, (text_start_x, final_text_y),
                            font_face, font_scale, color_text, text_font_thickness)

            else:
                # ==========================
                # 模式 B: 一般模式 (Standard Mode)
                # ==========================
                
                # 文字位置：對齊紅框左上角
                text_x = box_x1
                text_y = box_y1 - 5 
                
                # 邊界檢查：如果文字超出圖片頂部，改放到框內
                if text_y - text_height < 0:
                    text_y = box_y1 + text_height + 5

                # (A) 畫文字背景 (白底黑框)
                # 修正：背景寬度應該基於 text_x + text_width，而非吊牌模式的 text_end_x
                cv2.rectangle(target_image, 
                              (text_x - pad_margin, text_y - text_height - pad_margin), 
                              (text_x + text_width + pad_margin, text_y + pad_margin), 
                              color_background_white, -1)
                cv2.rectangle(target_image, 
                              (text_x - pad_margin, text_y - text_height - pad_margin), 
                              (text_x + text_width + pad_margin, text_y + pad_margin), 
                              color_border_black, 1)
                
                # (B) 寫入文字
                cv2.putText(target_image, label_text, (text_x, text_y),
                            font_face, font_scale, color_text, text_font_thickness)

    except Exception as error:
        print(f"解析標註檔錯誤: {error}")

def setup_path_label(full_path: str, prefix: str = "", max_chars: int = 20):
        """
        自動設定 Label 的顯示文字 (縮短版) 與 Tooltip (完整版)
        
        Args:
            full_path: 完整的檔案路徑
            prefix: 顯示在前方的文字 (例如 "Img: ", "Lbl: ")
            max_chars: 顯示的最大字數
        """
        if len(full_path) > max_chars:
            truncated_path = full_path[-max_chars:]
            display_text = f"...{truncated_path}"
        else:
            display_text = full_path

        return f"{prefix}{display_text}"

def extract_feature_content(img):
    """
    extract_feature_content 的 Docstring
    
    :param img: 需被裁切的圖片

    裁切邏輯：抓取最大輪廓或特定條件的輪廓
    """
    inverted = cv2.bitwise_not(img)
    contours, _ = cv2.findContours(inverted, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours: return img
    
    valid_rects = []
    min_area = 20 
    for c in contours:
        if cv2.contourArea(c) > min_area:
            x, y, w, h = cv2.boundingRect(c)
            valid_rects.append((x, y, x + w, y + h))
            
    if not valid_rects:
        max_contour = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(max_contour)
        valid_rects.append((x, y, x + w, y + h))

    x_min = min([r[0] for r in valid_rects])
    y_min = min([r[1] for r in valid_rects])
    x_max = max([r[2] for r in valid_rects])
    y_max = max([r[3] for r in valid_rects])

    pad = 1 
    y1, y2 = max(0, y_min - pad), min(img.shape[0], y_max + pad)
    x1, x2 = max(0, x_min - pad), min(img.shape[1], x_max + pad)
    return img[y1:y2, x1:x2]

def apply_shear(img, shear_deg, bg_color=255):
    if shear_deg == 0: return img
    h, w = img.shape[:2]
    shear_factor = shear_deg / 20.0
    M = np.float32([[1, shear_factor, 0], [0, 1, 0]])
    corners = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
    corners_trans = cv2.transform(np.array([corners]), M)[0]
    min_x = corners_trans[:, 0].min()
    max_x = corners_trans[:, 0].max()
    new_w = int(max_x - min_x)
    tx = -min_x 
    M[0, 2] = tx
    img_sheared = cv2.warpAffine(img, M, (new_w, h), borderValue=(bg_color, bg_color, bg_color))
    return img_sheared

def trim_whitespace(img):
    inverted = cv2.bitwise_not(img)
    contours, _ = cv2.findContours(inverted, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours: return img
    all_contours = np.vstack(contours)
    x, y, w, h = cv2.boundingRect(all_contours)
    return img[y:y+h, x:x+w]

def clear_existing_crops(image_filename, cut_root, classes):
    """防止標註數量變動導致舊裁切圖殘留"""
    if not cut_root or not os.path.exists(cut_root): return
    base_name = os.path.splitext(image_filename)[0]
    
    for cls in classes:
        cls_dir = os.path.join(cut_root, cls)
        if not os.path.isdir(cls_dir): continue
        for f in os.listdir(cls_dir):
            if f.startswith(f"{base_name}_"):
                try: os.remove(os.path.join(cls_dir, f))
                except: pass

def crop_and_save_by_label(img_path, labels, classes, cut_img_dir):
    """執行實際裁切與分資料夾儲存"""
    img = imread_chinese(img_path)
    if img is None: return
    h, w = img.shape[:2]
    img_name = os.path.splitext(os.path.basename(img_path))[0]

    for i, lbl in enumerate(labels):
        cls_idx, cx, cy, bw, bh = lbl

        # YOLO (0~1) 轉 Pixel 座標
        x1 = max(0, int((cx - bw / 2) * w))
        y1 = max(0, int((cy - bh / 2) * h))
        x2 = min(w, int((cx + bw / 2) * w))
        y2 = min(h, int((cy + bh / 2) * h))

        crop_img = img[y1:y2, x1:x2]
        if crop_img.size > 0:
            save_path = os.path.join(cut_img_dir, f"{img_name}_{i}.png")
            imwrite_chinese(save_path, crop_img)