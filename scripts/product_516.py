import cv2, os, numpy as np
from pathlib import Path
from PIL import Image, ImageChops
import logging
import json
from datetime import datetime

# ── 設定 logging ───────────────────────────
def setup_logging(product_dir: Path):
    """為每個產品建立獨立的 log 檔案"""
    log_file = product_dir / "process.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    ))
    
    # 建立產品專屬的 logger
    product_logger = logging.getLogger(f"product_{product_dir.name}")
    product_logger.setLevel(logging.INFO)
    product_logger.addHandler(file_handler)
    
    return file_handler, product_logger

# ── 參數 ───────────────────────────
BASE_DIR = Path(r"D:\OneDrive\Documents\GitHub\berry")
ROOT_DIR = BASE_DIR / "WWW_Collection"
OUT_DIR = ROOT_DIR / "product_383" / "split"

# 文字/圖形分類參數
TXT_MAX_H = 150        # 小於此高度才有可能是純文字
TXT_STDDEV_MAX = 25    # 同一列灰度標準差 < 25 視為字少、背景白
TXT_BLACK_RATIO = 0.02 # 黑畫素佔比 > 2% 才算真的有字
MERGE_GAP_PX = 40      # 文字塊間的空白 ≤ 40px 併在一起

# 原本的參數
MIN_GAP_PCT = .96      # 一列有 ≥96% 的像素近白，就視為分隔帶
MIN_GAP_H = 6          # 分隔帶最少高度（px）
TRIM_TOL = 5           # 去白邊時，<5px 灰度視為白

# 加 debug print
print("ROOT_DIR =", ROOT_DIR)
print("OUT_DIR =", OUT_DIR)

OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── 工具函式 ────────────────────────
def find_h_splits(img: np.ndarray) -> list[int]:
    """傳回需要切的 y 座標清單（不含 0 / h）。"""
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # 每列計算「白色比例」
    white_ratio = (gray > 245).mean(axis=1)
    # 找到連續高於門檻的區段
    splits, run = [], []
    for y, r in enumerate(white_ratio):
        if r >= MIN_GAP_PCT:
            run.append(y)
        elif run:
            if len(run) >= MIN_GAP_H:
                splits.append(int(np.mean(run)))  # 分隔帶中心
            run.clear()
    return splits

def is_text_block(img_piece: np.ndarray) -> bool:
    """判斷是否為文字區塊"""
    h, w = img_piece.shape[:2]
    if h > TXT_MAX_H:
        return False                      # 太高，直接當圖
    gray = cv2.cvtColor(img_piece, cv2.COLOR_BGR2GRAY)

    # ① 背景是否幾乎全白
    row_std = gray.std(axis=1).mean()     # 整塊平均「行標準差」
    if row_std > TXT_STDDEV_MAX:
        return False

    # ② 至少要有一些「黑/灰文字」
    black_ratio = (gray < 200).mean()
    return black_ratio > TXT_BLACK_RATIO

def merge_text_blocks(img_bgr: np.ndarray, ys: list[int]) -> list[tuple[int, int]]:
    """合併連續的文字區塊"""
    merged = []
    i = 0
    while i < len(ys)-1:
        y1, y2 = ys[i], ys[i+1]
        piece = img_bgr[y1:y2]

        if is_text_block(piece):
            # 一直往後併，直到遇到「圖片」或「空白 > MERGE_GAP_PX」
            j = i + 1
            while j < len(ys)-1:
                gap = ys[j] - ys[j-1]
                nxt = img_bgr[ys[j]:ys[j+1]]
                if gap > MERGE_GAP_PX or not is_text_block(nxt):
                    break
                j += 1
            merged.append((y1, ys[j]))   # ys[j] 是最後文字塊下緣
            i = j
        else:
            merged.append((y1, y2))
            i += 1
    return merged

def trim_white(pil: Image.Image) -> Image.Image:
    """把四周接近純白(>TRIM_TOL)的邊緣裁掉。"""
    bg = Image.new(pil.mode, pil.size, (255,255,255))
    diff = ImageChops.difference(pil, bg).convert("L")
    bbox = diff.point(lambda p: p>TRIM_TOL and 255).getbbox()
    return pil.crop(bbox) if bbox else pil

# ── 主流程 ───────────────────────────
def main():
    # 設定根目錄的 logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    root_logger = logging.getLogger(__name__)
    
    root_logger.info(f"BASE_DIR = {BASE_DIR}")
    root_logger.info(f"ROOT_DIR = {ROOT_DIR}")
    root_logger.info(f"OUT_DIR = {OUT_DIR}")
    
    if not ROOT_DIR.exists():
        root_logger.error(f"找不到輸入目錄：{ROOT_DIR}")
        return
        
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    root_logger.info(f"建立輸出資料夾：{OUT_DIR}")

    # 建立總體處理記錄
    process_summary = {
        "start_time": datetime.now().isoformat(),
        "total_processed": 0,
        "total_saved": 0,
        "products": {}
    }

    # 先測試三張圖
    test_inputs = [
        ROOT_DIR / "product_383" / "images" / "F6076_Log-table_01.jpg",
        ROOT_DIR / "product_383" / "images" / "F6077_Log-table_02.jpg",
        ROOT_DIR / "product_383" / "images" / "F6078_Log-table_03.jpg",
    ]

    for img_path in test_inputs:
        root_logger.info(f"處理圖片：{img_path}")
        
        if not img_path.exists():
            root_logger.error(f"找不到圖片：{img_path}")
            continue

        # 設定產品專屬的 log
        file_handler, product_logger = setup_logging(OUT_DIR)
        
        # 初始化產品處理記錄
        product_summary = {
            "image": str(img_path),
            "parts": [],
            "errors": []
        }

        img_bgr = cv2.imread(str(img_path))
        if img_bgr is None:
            error_msg = f"無法讀取圖片：{img_path}"
            root_logger.error(error_msg)
            product_summary["errors"].append(error_msg)
            continue

        h, w = img_bgr.shape[:2]
        product_logger.info(f"圖片尺寸：{w}x{h}")

        # 1. 先用原本的邏輯找切點
        ys = [0] + find_h_splits(img_bgr) + [h]
        product_logger.info(f"找到 {len(ys)-1} 個切點")
        
        # 2. 合併文字區塊
        merged = merge_text_blocks(img_bgr, ys)
        product_logger.info(f"合併後剩 {len(merged)} 個區塊")

        # 3. 處理每個區塊
        for idx, (y1, y2) in enumerate(merged):
            if y2 - y1 < 40:           # 避免切到太薄的空白
                product_logger.info(f"跳過太薄的分段：{y1} -> {y2}")
                continue

            piece = Image.fromarray(cv2.cvtColor(img_bgr[y1:y2], cv2.COLOR_BGR2RGB))
            piece = trim_white(piece)
            
            out_file = OUT_DIR / f"{img_path.stem}_part{idx+1}.webp"
            piece.save(out_file, 'WEBP', quality=92, method=6)
            
            product_logger.info(f"已儲存：{out_file} ({piece.size[0]}x{piece.size[1]})")
            
            # 記錄分段資訊
            product_summary["parts"].append({
                "file": str(out_file),
                "size": f"{piece.size[0]}x{piece.size[1]}",
                "position": f"{y1}-{y2}",
                "is_text": is_text_block(img_bgr[y1:y2])
            })
            
            process_summary["total_saved"] += 1

        # 儲存產品處理記錄
        with open(OUT_DIR / "process.json", "w", encoding="utf-8") as f:
            json.dump(product_summary, f, ensure_ascii=False, indent=2)
            
        process_summary["total_processed"] += 1
        process_summary["products"][img_path.parent.stem] = product_summary
        
        # 移除產品專屬的 log handler
        product_logger.removeHandler(file_handler)
        file_handler.close()

    # 儲存總體處理記錄
    process_summary["end_time"] = datetime.now().isoformat()
    with open(OUT_DIR / "process_summary.json", "w", encoding="utf-8") as f:
        json.dump(process_summary, f, ensure_ascii=False, indent=2)

    root_logger.info(f"處理完成！共處理 {process_summary['total_processed']} 張圖片，儲存 {process_summary['total_saved']} 個分段")

if __name__ == "__main__":
    main()
