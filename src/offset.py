"""
select_feature_area(img):
offset_calculation(pre_img, now_img, original_xy):
"""

import cv2

def select_feature_area(img):
    """
    開啟視窗讓使用者框選特徵區域 (Anchor)。
    
    Args:
        img: 來源圖片 (OpenCV numpy array)
    
    Returns:
        template: 框選出的特徵圖片區域
        (x, y): 特徵區域在原圖的左上角座標
        (如果使用者取消或未框選，則回傳 None, None)
    """
    window_name = "Select Feature Area"
    
    # 設定視窗屬性確保彈出至最上層
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)
    cv2.moveWindow(window_name, 100, 100)
    
    print("【操作提示】請框選特徵區域，完成後按 ENTER 或 空白鍵 確認；按 c 取消。")
    
    # 調用 OpenCV 的 ROI 選擇器
    rect = cv2.selectROI(window_name, img, fromCenter=False, showCrosshair=True)
    cv2.destroyWindow(window_name)
    
    x, y, w, h = rect
    
    # 檢查是否有效框選 (寬高不得為 0)
    if w == 0 or h == 0:
        return None, None
        
    # 裁切圖片
    template = img[y:y+h, x:x+w]
    return template, (x, y)

def offset_calculation(pre_img, now_img, original_xy):
    """
    計算特徵圖片在目標圖片中的位移偏差 (Offset)。
    
    Args:
        pre_img:  前一張圖擷取的特徵區域 (Template / Anchor)
        now_img:  目前要搜尋的完整目標圖片 (Target Image)
        original_xy: 特徵在原本圖片中的座標 (x_old, y_old)
        
    Returns:
        dx: X 軸偏差量 (向右為正)
        dy: Y 軸偏差量 (向下為正)
        max_val: 匹配信心度 (0~1)
        (如果信心度過低或是發生錯誤，回傳 None, None, 0)
    """
    try:
        # 執行模板匹配
        res = cv2.matchTemplate(now_img, pre_img, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        
        # 設定信心度門檻 (例如 0.6)
        if max_val < 0.6:
            return None, None, max_val
            
        # max_loc 為新圖片中匹配到的左上角座標 (x_new, y_new)
        new_x, new_y = max_loc
        old_x, old_y = original_xy
        
        # 計算偏差公式
        dx = new_x - old_x
        dy = new_y - old_y
        
        return dx, dy, max_val
        
    except Exception as e:
        print(f"Error in calculation: {e}")
        return None, None, 0