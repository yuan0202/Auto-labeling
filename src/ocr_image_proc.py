"""
3_auto_generate_label.src.ocr_image_proc 的 Docstring
fix_1_vs_7_by_top_width: 輸入二值化圖與 OCR 文字，修正 1 與 7 的誤判
find_dot: 輸入單個二值化裁切圖，判斷是否為小數點
find_minus_or_missing: 找出可能小數點的位置
recognize_digit_with_anchor: 錨點策略
class ImageProcessor: 圖片處理
"""
import cv2
import numpy as np
from constants import OCR_DOT_PROC
from utils import load_templates, apply_shear, get_bg_color

def fix_1_vs_7_by_top_width(img_binary, ocr_text):
    """
    針對七段顯示器修正：
    當 OCR 讀到 '1' 時，檢查二值化圖的【頂部區域】。
    如果不只是一堆散點，而是存在一條【寬度夠寬】的連通線段，就判定為 7。
    """
    if '1' not in ocr_text:
        print(" 7 fix function dont need to work")
        return ocr_text

    # 1. 找出所有數字的 bounding box
    contours, _ = cv2.findContours(img_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # 過濾極小雜訊
    h_img = img_binary.shape[0]
    valid_boxes = [cv2.boundingRect(c) for c in contours]
    # 這裡放寬一點標準，以免斷掉的數字被過濾掉，但太矮的還是去掉
    valid_boxes = [b for b in valid_boxes if b[3] > h_img * 0.3]
    
    # 由左至右排序
    valid_boxes.sort(key=lambda x: x[0])

    text_list = list(ocr_text)
    fixed_text_list = []

    count_boxes = len(valid_boxes)
    count_text = len(text_list)
    print(f"輪廓數量 ({count_boxes}) vs. OCR 文字長度 ({count_text})")
    
    # 如果輪廓數量跟文字長度一致，這是最理想的情況，可以精準對應
    if len(valid_boxes) == len(text_list):
        for i, box in enumerate(valid_boxes):
            char = text_list[i]
            x, y, w, h = box
            
            if char == '1':
                # === 關鍵邏輯：檢查頭頂有沒有「線」 ===
                
                # 1. 切出頭頂區域 (Top 25%)
                # 為了避免邊緣沾黏，左右稍微內縮 (padding)
                roi_top = img_binary[y : y + int(h*0.25), x : x + w]
                
                # 2. 在這個頭頂小區域內找輪廓
                sub_contours, _ = cv2.findContours(roi_top, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                max_width = 0
                if sub_contours:
                    # 找出頭頂區域內「最寬」的那個物體
                    for c in sub_contours:
                        _, _, cw, _ = cv2.boundingRect(c)
                        if cw > max_width:
                            max_width = cw
                
                # 3. 判斷邏輯
                # 如果頭頂最寬的物體，寬度超過了該數字總寬度的 25% (使用者建議約 20%)
                # 並且這個寬度大於 3 個像素 (避免極細雜訊)
                threshold_ratio = 0.25
                
                if max_width > (w * threshold_ratio) and max_width > 7:
                    print(f"  [修正] 偵測到 '1' 但頭頂有寬度 {max_width} 的橫線 (佔比 {max_width/w:.2f}) -> 改為 '7'")
                    fixed_text_list.append('7')
                else:
                    print(f"偵測為1時則為1, 頭頂有寬度 {max_width} 的橫線 (佔比 {max_width/w:.2f})")
                    fixed_text_list.append('1')
            else:
                fixed_text_list.append(char)
        
        return "".join(fixed_text_list)
    
    else:
        new_text = list(ocr_text)
        return "".join(new_text)
    
def find_dot(label_boxes, fixed_text, max_area=OCR_DOT_PROC["max_area"], ratio_threshold=OCR_DOT_PROC["ratio_threshold"]):
    """
    透過標註框的幾何特徵 (面積與寬高比) 找回 OCR 遺漏的小數點。

    此函式不依賴 OCR 辨識內容，而是直接根據標註框 (Bounding Box) 的物理尺寸
    判斷該位置是否應為「小數點」，並利用索引對位將 "." 插入字串的正確位置。

    Args:
        label_boxes (list): 原始標註框清單，格式為 [(x, y, w, h), ...]。
        fixed_text (str): 經由 OCR 辨識並修正後的原始字串 (通常不含小數點)。
        max_area (int, optional): 判定為小數點的最大面積門檻 (w * h)。預設為 120。
        ratio_threshold (float, optional): 寬高比 (w/h) 門檻，低於此值視為字元過窄。預設為 0.4。

    Returns:
        str: 修正後包含小數點的完整字串。若未偵測到點則回傳原字串。

    Note:
        - 傳入的 label_boxes 會在函式內自動進行 X 軸排序，以確保與字串索引對應。
        - 使用 list.insert() 邏輯，當補入小數點時，原索引後的字元會自動後移。
    """
    if not label_boxes or not isinstance(fixed_text, str):
        return fixed_text

    # 1. 依照 X 座標排序所有紅框，確保從左至右順序與字串一致
    sorted_boxes = sorted(label_boxes, key=lambda b: b[0])
    
    # 2. 將字串轉為列表以利進行插入操作 (String 在 Python 中不可變)
    text_list = list(fixed_text)

    # 3. 遍歷排序後的框，找出幾何特徵符合「點」的目標
    for i, (x, y, w, h) in enumerate(sorted_boxes):
        # 計算該框的物理面積
        box_area = w * h
        # 計算寬高比 (避免除以零)
        aspect_ratio = (w / h) if h > 0 else 0
        
        # 4. 判斷邏輯：面積極小 或 寬度極窄
        is_dot = False
        if box_area < max_area or aspect_ratio < ratio_threshold:
            is_dot = True

        # 5. 執行插入邏輯
        if is_dot:
            # 在目前的索引 i 位置插入點
            # 若 fixed_text="123" 且 i=2，則結果為 ['1', '2', '.', '3']
            text_list.insert(i, ".")
            break 

    return "".join(text_list)

def find_minus(image_input, ocr_result_text):
    """
    輸入: 
    - image_input: 原始讀入的圖片 (灰階或二值皆可)
    - ocr_result_text: EasyOCR 的結果
    """
    
    # --- 關鍵修正 Step 1: 確保圖片是二值化 (0 或 255) ---
    # Otsu's method 會自動找閾值，適合黑白分明的圖片
    _, bin_img = cv2.threshold(image_input, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # --- 關鍵修正 Step 2: 檢查是否需要反轉 (由白底黑字 -> 黑底白字) ---
    # 計算圖片角落的像素值，如果角落是白色 (255)，代表是白底，需要反轉
    h, w = bin_img.shape
    corner_pixel = bin_img[0, 0] # 左上角像素
    
    if corner_pixel > 127:
        print("[Debug] 偵測到白底黑字，執行反轉 (Invert)...")
        bin_img = cv2.bitwise_not(bin_img)
    else:
        print("[Debug] 偵測到黑底白字，無需反轉")

    # 1. 找出所有獨立的輪廓 (現在文字是白色，應該能正確抓到了)
    contours, _ = cv2.findContours(bin_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # 2. 取得 Bounding Box 並排序
    bounding_boxes = [cv2.boundingRect(c) for c in contours]
    bounding_boxes.sort(key=lambda b: b[0])
    
    # 3. 過濾極小雜訊 (針對你的圖片解析度，可能需要調整這裡的數值)
    # 這裡放寬一點條件 > 5，以免負號太小被濾掉
    valid_boxes = [b for b in bounding_boxes if b[2] * b[3] > 5] 
    
    feature_count = len(valid_boxes)
    ocr_count = len(ocr_result_text)
    
    print(f"[Debug] 輪廓區塊數量: {feature_count}, OCR 偵測字數: {ocr_count}")

    # --- 邏輯判斷 ---
    # 預期情況：共 3 個區塊，OCR 讀到 "10" (長度2)
    # 3 > 2 -> 進入邏輯
    if ocr_count < feature_count and feature_count >= 2:
        
        minus_box = valid_boxes[0]     # 最左邊 (預期是 minus)
        digit_box = valid_boxes[1]     # 隔壁 (預期是 number)
        
        minus_h = minus_box[3]
        digit_h = digit_box[3]
        
        print(f"[Debug] 最左邊高度: {minus_h}, 右邊數字高度: {digit_h}")

        if digit_h > 0:
            ratio = minus_h / digit_h
            print(f"[Debug] 高度比例: {ratio:.2f}")
            
            # 條件寬容一點，如果高度小於 30% 都算負號
            if ratio < 0.30: 
                print("判定結果: 補回負號 (-)")
                return "-" + ocr_result_text
            else:
                print("判定結果: 左邊區塊過高，非負號")
        
    else:
        print("數量邏輯不符合補償條件")
        # 印出細節幫忙除錯
        if feature_count <= ocr_count:
            print(f"原因: 輪廓數量 ({feature_count}) 沒有多於 OCR 字數 ({ocr_count})，可能 '1' 和 '0' 連在一起了？")

    return ocr_result_text

def recognize_digit_with_anchor(reader, single_digit_img, anchor_id):
    """
    Anchor Strategy (錨點策略):為了解決單獨偵測時0會被判斷成幾何圖形,1會被判斷成垂直分割線或雜訊,
    所以用一個"3"的圖片放在數字後面作為錨點,之後交給ocr判斷整串數字,處理完再刪除3
    
    :param reader: OCR模型名稱
    :param single_digit_img: 檢測圖
    :param anchor_id: 錨點圖

    Returns:
        detected_digit: list, OCR判斷結果
    """
    anchor_img = load_templates(anchor_id)

    merged_img = cv2.hconcat([single_digit_img, anchor_img])

    # OCR
    result = reader.readtext(merged_img, allowlist='0123456789', detail=1)

    if result:
        text = result[0][1] # 例如辨識出 "13"
        
        # 【修改點 2】：字串切片邏輯改變
        # text[:-1] 代表「從頭取到倒數第二個字」，也就是去掉最後一個字
        detected_digit = text[:-1] if len(text) > 1 else ""
        
        # 補救措施：如果結果是空字串 (代表只讀到了錨點 '3'，前面的沒讀到)
        if detected_digit == "":
            return None
            
        return detected_digit
    
    return None

class ImageProcessor:
    @staticmethod
    def apply_processing(img, config):
        # 1. Gamma 校正
        if config['gamma'] != 1.0:
            invGamma = 1.0 / config['gamma']
            table = np.array([((i / 255.0) ** invGamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
            img = cv2.LUT(img, table)

        # 2. 高斯濾波 (Gaussian Blur)
        # 通常在轉 HSV 之前或之後做都可以，這裡放在 HSV 之前可以平滑噪點
        blur_k = int(config.get('blur_k', 0))
        if blur_k > 0:
            # 確保核大小是奇數
            if blur_k % 2 == 0: blur_k += 1
            img = cv2.GaussianBlur(img, (blur_k, blur_k), 0)

        # 4. Shear (傾斜校正)
        if config['shear'] != 0:
            img = apply_shear(img, config['shear'], bg_color=0)
            """h, w = img.shape[:2]
            # 這裡完全保留你的邏輯：負號係數、寬度計算、黑色補邊
            shear_factor = -config['shear'] / 20.0
            M = np.float32([[1, shear_factor, 0], [0, 1, 0]])
            img = cv2.warpAffine(img, M, (w + abs(config['shear'])*2, h), borderValue=(0,0,0))"""

        # 3. HSV 過濾
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        lower = np.array([config['h_min'], config['s_min'], config['v_min']])
        upper = np.array([config['h_max'], config['s_max'], config['v_max']])
        mask = cv2.inRange(hsv, lower, upper)
        
        

        # 轉成白底黑字 (EasyOCR 偏好)
        bin_img = cv2.bitwise_not(mask)

        return bin_img, mask # 回傳 mask 供後續分析用 (fix_1_vs_7 邏輯)