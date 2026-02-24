# 定義 OCR 類型與對應的內部代碼 (或是模型路徑)
# --- 基礎字符集 ---
DIGITS = "0123456789"
SYMBOLS = "."
NEGATIVE = "-"

OCR_MODE_CONFIG = {
    # Key (顯示文字) : Value (內部邏輯用的代碼或模型檔名)
    "7段數字": "seven_seg_simple",
    "7段數字(含逗號)": "seven_seg_comma",
    "7段數字(含逗號,負號)": "seven_seg_full",
    "電腦數字": "digital_simple",
    "電腦數字(含逗號)": "digital_comma",
    "電腦數字(含逗號, 負號)": "digital_full"
}

WORKING_MODE = {
    # --- 第一階段：大區塊標註 (Stage 1) ---
    "1. 批量自動標註 (偏移計算專用)": "STAGE1_LABELING_MODE",
    "1. 單圖手動修正 (預覽與調整)": "STAGE1_PREVIEW_MODE",

    # --- 第二階段：子區塊標註 (Stage 2) ---
    "2. 批量自動標註 (偏移計算專用)": "STAGE2_LABELING_MODE",
    "2. 單圖手動修正 (預覽與調整)": "STAGE2_PREVIEW_MODE",

    # --- 第三階段：OCR 辨識 (OCR Stage) ---
    "3. OCR 快速辨識 (批量填充)": "OCR_LABELING_MODE",
    "3. 辨識結果修正 (文字校對)": "OCR_PREVIEW_MODE"
}

MODE_PATH_MAP = {
    "STAGE1": ("Original_folder/Original_img", "Original_folder/Box01_label", "Box01_folder/Box01_img"),
    "STAGE2": ("Box01_folder/Box01_img", "Box01_folder/Box02_label", "Box02_folder/Box02_img"),
    "OCR":    ("Box02_folder/Box02_img", "Box02_folder/Number", "")
}

CHAR_MAP = {
    # 符號與類別名稱的映射表
    ".": "Dot",
    "-": "minus"
}

# --- 內部邏輯用的白名單對應 ---
ALLOWLIST_MAP = {
    "seven_seg_simple": DIGITS,
    "seven_seg_comma": DIGITS + SYMBOLS,
    "seven_seg_full": DIGITS + SYMBOLS + NEGATIVE,
    
    "digital_simple": DIGITS,
    "digital_comma": DIGITS + SYMBOLS,
    "digital_full": DIGITS + SYMBOLS + NEGATIVE
}

# OCR 相關參數配置
OCR_DOT_PROC = {
    # 面積閾值：小於此值視為 Dot (預設 120)
    "max_area": 120,
    
    # 寬高比閾值 (w/h)：小於此值視為過窄 (預設 0.4)
    "ratio_threshold": 0.4
}

# constant.py

# Default image processing parameters
DEFAULT_PARAMS = {
    # --- HSV Color Space Thresholds ---
    # Hue: Represents the color type (e.g., red, blue). 
    # In OpenCV, Hue ranges from 0 to 179 (not 0-360).
    'h_min': 0,    # Minimum Hue
    'h_max': 179,  # Maximum Hue 

    # Saturation: Represents the intensity/purity of the color.
    # Range: 0 (Gray/Faded) to 255 (Vibrant).
    's_min': 0,    # Minimum Saturation
    's_max': 255,  # Maximum Saturation

    # Value: Represents the brightness of the color.
    # Range: 0 (Black) to 255 (Brightest).
    'v_min': 0,    # Minimum Value (Brightness)
    'v_max': 255,  # Maximum Value (Brightness)

    # --- Pre-processing / Transformations ---
    # Gamma Correction: Non-linear adjustment for luminance.
    # Value > 1 makes image darker, Value < 1 makes image brighter.
    'gamma': 1.0,  

    # Shear: Geometric transformation that shifts image pixels horizontally.
    'shear': 0,    

    # Blur Kernel: Size of the kernel used for smoothing/blurring (e.g., Gaussian Blur).
    # Typically an odd number (1, 3, 5...). 0 usually means no blur.
    'blur_k': 0    
}