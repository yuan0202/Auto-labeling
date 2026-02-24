"""
3_auto_generate_label.src.template_create 的 Docstring
template_marge: 將裁切過後的template和測試原圖整合
clean_anchor: 進行ocr處理之後清除錨點圖
"""
import cv2
from utils import get_bg_color, apply_shear, trim_whitespace
import numpy as np

def template_merge(img, template, config):
    """
    將測試圖 (img) 與 Template 合併
    前提：傳入的 img 與 template 都已經是「二值化」且「背景色一致」的圖片。
    """
    # 0. 防呆
    if img is None or template is None:
        return None
        
    h_target, w_target = img.shape[:2]
    if h_target == 0: return None

    # ==========================================
    # 1. 取得背景色 (只為了補邊用)
    # ==========================================
    # 雖然不用做極性反轉，但 Shear 和 Resize 補邊時需要知道背景是黑(0)還是白(255)
    # 直接從測試圖偵測即可
    bg_color = get_bg_color(img)
    
    # ==========================================
    # 2. Shear (傾斜校正)
    # ==========================================
    shear_deg = config.get('shear', 0)
    
    # 兩者都做 Shear，補邊顏色使用 bg_color
    target_sheared = apply_shear(img, shear_deg, bg_color)
    template_sheared = apply_shear(template, shear_deg, bg_color)

    # ==========================================
    # 3. Trim Template (裁切 Template 多餘白邊)
    # ==========================================
    template_trimmed = trim_whitespace(template_sheared)
    
    # ==========================================
    # 4. Resize Template (高度對齊)
    # ==========================================
    h_target_final = target_sheared.shape[0]
    h_tpl, w_tpl = template_trimmed.shape[:2]
    
    if h_tpl == 0: return None

    # 計算縮放比例
    scale_ratio = h_target_final / float(h_tpl)
    new_w = int(w_tpl * scale_ratio)
    if new_w <= 0: new_w = 1
    
    # 縮放
    # 注意：雖然輸入是二值圖，但 Resize 線性插值會產生灰色邊緣
    resized_anchor = cv2.resize(template_trimmed, (new_w, h_target_final), interpolation=cv2.INTER_LINEAR)
    
    # [必要] 再次二值化：確保 Resize 後的邊緣銳利，適合 OCR
    _, resized_anchor = cv2.threshold(resized_anchor, 127, 255, cv2.THRESH_BINARY)

    # ==========================================
    # 5. 拼接 (Concat)
    # ==========================================
    spacer_w = max(1, int(h_target_final * 0.3))
    spacer = np.full((h_target_final, spacer_w), int(bg_color), dtype=np.uint8)
    
    # 組合：[Target] [Spacer] [Template]
    merged_img = cv2.hconcat([target_sheared, spacer, resized_anchor])
    
    # ==========================================
    # 6. 加外框 (Border)
    # ==========================================
    border = 20
    final_img = cv2.copyMakeBorder(
        merged_img, border, border, border, border, 
        cv2.BORDER_CONSTANT, value=int(bg_color)
    )
    
    return final_img