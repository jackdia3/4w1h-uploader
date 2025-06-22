#!/usr/bin/env python3
"""
批次裁切圖片處理器
===================

使用範例
--------
$ python batch_runner.py
# → 處理 WWW_Collection 下所有產品圖片，輸出到各產品的 images/cropped 目錄

可選參數：
  --ratio    白色區域判定比例（預設 0.03）
  --workers  並行處理數（預設 CPU核心數×4）
  --ext      要處理的副檔名（預設 jpg,jpeg,png）
"""

import argparse
import json
import logging
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import cv2
import numpy as np

# ───────────────────────────── 常數定義
MIN_CROP_HEIGHT = 200             # 裁片最小高度（px）
BG_THRESH = 245                   # > 此灰度視為白
CONSEC_BORDER = 15                # 邊框掃描連續白行/列門檻
MIN_BAND_MEAN = 250              # 判斷 '純白帶' 的平均亮度門檻
MIN_WHITE_RATIO = 0.92           # 該 band 內 >245 的像素佔比

# ───────────────────────────── 工具函數

class NumpyEncoder(json.JSONEncoder):
    """處理 numpy 數值型別的 JSON 編碼器"""
    def default(self, obj):
        if isinstance(obj, np.integer): return int(obj)
        if isinstance(obj, np.floating): return float(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        return super().default(obj)

def to_serializable(obj: Any) -> Any:
    """將物件轉換為可序列化的格式"""
    if isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [to_serializable(i) for i in obj]
    elif isinstance(obj, tuple):
        return tuple(to_serializable(i) for i in obj)
    elif hasattr(obj, 'as_posix'):  # Path 物件
        return str(obj)
    else:
        return obj

# ───────────────────────────── 圖片處理函數

def trim_border(img: np.ndarray, bg_thresh: int = BG_THRESH, consec: int = CONSEC_BORDER) -> tuple[int, int, int, int]:
    """偵測四周純白邊框，回傳 (top, bottom, left, right) 應裁掉的像素數"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    def _scan(indices, axis: str) -> int:
        run = 0
        for idx in indices:
            line = gray[idx] if axis == "row" else gray[:, idx]
            if (line > bg_thresh).all():
                run += 1
                if run >= consec:
                    continue
            else:
                break
        return run

    top = _scan(range(h), "row")
    bottom = _scan(range(h - 1, -1, -1), "row")
    left = _scan(range(w), "col")
    right = _scan(range(w - 1, -1, -1), "col")
    return top, bottom, left, right

def merge_close(lines: List[int], orig_h: int) -> List[int]:
    """合併太近的切線"""
    if not lines:
        return []
    
    # 對長圖使用固定間距，避免過度合併
    min_gap = 180 if orig_h > 4000 else max(120, int(0.025 * orig_h))
    
    merged = []
    for y in sorted(lines):
        if not merged or y - merged[-1] >= min_gap:
            merged.append(y)
    return merged

# ───────────────────────────── 新的白帶偵測
def find_white_gaps(gray: np.ndarray,
                    row_mu_th: int = 250,
                    row_std_th: int = 3,
                    min_run: int = 18) -> List[int]:
    """回傳所有「水平留白」的中心 y 座標"""
    # 計算每行的平均亮度
    row_means = np.mean(gray, axis=1)
    row_stds = np.std(gray, axis=1)
    
    # 找出符合條件的行
    white = (row_means > row_mu_th) & (row_stds < row_std_th)
    
    # 找出連續的白行
    gaps = []
    run_start = None
    
    # 連續白行 run 至少得有「任意行的 row_std < 1.5」才算真正純白
    for y, flag in enumerate(white):
        if flag and run_start is None:
            run_start = y
        elif (not flag) and run_start is not None:
            run_len = y - run_start
            if run_len >= min_run and (gray[run_start:y].std() < 1.5):
                gaps.append((run_start + y - 1) // 2)
            run_start = None
    
    # 處理最後一段
    if run_start is not None:
        run_len = len(white) - run_start
        if run_len >= min_run and (gray[run_start:].std() < 1.5):
            gaps.append((run_start + len(white) - 1) // 2)
    
    return gaps

def long_edge_projection(gray: np.ndarray) -> List[int]:
    """偵測長圖的稀疏邊緣帶"""
    h, w = gray.shape
    if h <= 2000:  # 非長圖不處理
        return []
    
    # 計算每行的邊緣密度
    edges = cv2.Canny(gray, 50, 150)
    edge_density = edges.sum(axis=1) / w
    
    # 找出邊緣密度特別低的行
    threshold = edge_density.mean() * 0.3
    sparse_rows = edge_density < threshold
    
    # 合併連續的稀疏行
    lines, run_start = [], None
    for y, is_sparse in enumerate(sparse_rows):
        if is_sparse and run_start is None:
            run_start = y
        elif (not is_sparse) and run_start is not None:
            if y - run_start >= 10:  # 至少 10 行才視為有效
                lines.append((run_start + y - 1) // 2)
            run_start = None
    if run_start is not None and (h - run_start) >= 10:
        lines.append((run_start + h - 1) // 2)
    
    return lines

def looks_like_text(seg: np.ndarray) -> bool:
    """判斷是否為文字區塊"""
    gray = cv2.cvtColor(seg, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    ratio = edges.sum() / edges.size
    return ratio > 0.05 and gray.std() < 15

def small_fragment(crop: np.ndarray, orig_h: int) -> bool:
    """判斷是否為過小的片段"""
    h, w = crop.shape[:2]
    # 對『自己就是長條圖』的寬 < 250 圖片再加一道 hard-limit
    ABS_MIN = 320 if w > h else 400  # 橫幅圖放寬到 320px
    REL_MIN = 0.10 * orig_h  # 或 < 10 % 整張高度
    min_keep = max(int(0.10 * orig_h), int(0.30 * w), ABS_MIN)
    too_small = h < max(min_keep, ABS_MIN, REL_MIN)
    return too_small and (not looks_like_text(crop))

# ───────────────────────────── NEW: uniform_gap() 低變異度分隔帶
def uniform_gaps(gray: np.ndarray,
                 std_th: float = 2.5,
                 mu_hi: int = 235,
                 mu_lo: int = 25,
                 min_run: int = 4) -> List[int]:
    """
    找出「整行都很平」且亮度極高或極低的水平帶。適用：
      - 微灰白分隔線（row_mean≈240，std≈0）
      - 全黑分隔線  （row_mean≈10， std≈0）
    只要連續 ≥ min_run 行就算有效分隔。
    """
    h, _ = gray.shape
    row_mu  = gray.mean(axis=1)
    row_std = gray.std(axis=1)

    flat = (row_std < std_th) & ((row_mu > mu_hi) | (row_mu < mu_lo))

    gaps, run = [], None
    for y, f in enumerate(flat):
        if f and run is None:
            run = y
        elif (not f) and run is not None:
            if y - run >= min_run:
                gaps.append((run + y - 1) // 2)
            run = None
    if run is not None and h - run >= min_run:
        gaps.append((run + h - 1) // 2)
    return gaps

def smart_crop(img: np.ndarray) -> Dict[str, Any]:
    """智慧裁切圖片"""
    try:
        h, w = img.shape[:2]
        
        # 檢查圖片是否太小
        if max(h, w) < 120 or min(h, w) < 80:   # 高或寬 < 80 視為 icon
            return {
                "success": True,
                "crops": [img],
                "height": h,
                "width": w
            }
        
        # 先算一次，trim 之後再重算
        if len(img.shape) == 3 and img.shape[2] == 4:  # 處理 PNG alpha
            gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
        else:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 裁掉純白邊框
        t, b, l, r = trim_border(img)
        if any((t, b, l, r)):
            img  = img[t : img.shape[0] - b, l : img.shape[1] - r]
            gray = gray[t : gray.shape[0] - b, l : gray.shape[1] - r]
            h, w = gray.shape
        
        # 根據圖片高度決定裁切策略
        if h <= 2000:  # 短圖：直接保留
            return {
                "success": True,
                "crops": [img],
                "height": h,
                "width": w
            }
        
        # 找出所有水平白帶
        gap_lines = find_white_gaps(gray)       # ① 純白帶
        uniform_lines = uniform_gaps(gray) if h > 2800 else []  # ② 低變異度極亮/極暗帶（只針對長圖）
        sparse_lines = long_edge_projection(gray) # ③ 長圖稀疏邊緣帶
        
        # 合併所有切線
        cut_lines = merge_close(sorted(set(gap_lines + uniform_lines + sparse_lines)), h)
        if not cut_lines:
            return {
                "success": True,
                "crops": [img],
                "height": h,
                "width": w
            }
        
        # 根據切線裁切
        crops = []
        y0 = 0
        for y in cut_lines:
            if y - y0 >= MIN_CROP_HEIGHT:
                crop = img[y0:y]
                if not small_fragment(crop, h):
                    crops.append(crop)
            y0 = y  # 無論是否裁切，都更新 y0
        
        # 處理最後一段
        if h - y0 >= MIN_CROP_HEIGHT:
            crop = img[y0:]
            if not small_fragment(crop, h):
                crops.append(crop)
        
        # 如果沒有裁切出任何片段，返回原圖
        if not crops:
            return {
                "success": True,
                "crops": [img],
                "height": h,
                "width": w
            }
        
        # 檢查裁切覆蓋率
        total_crop_h = sum(crop.shape[0] for crop in crops)
        coverage = total_crop_h / h
        
        # 如果覆蓋率太低，嘗試使用原始切線（不併片）
        if coverage < 0.8:
            crops = []
            y0 = 0
            for y in sorted(set(gap_lines + uniform_lines + sparse_lines)):
                if y - y0 >= MIN_CROP_HEIGHT:
                    crop = img[y0:y]
                    if not small_fragment(crop, h):
                        crops.append(crop)
                y0 = y
            
            if h - y0 >= MIN_CROP_HEIGHT:
                crop = img[y0:]
                if not small_fragment(crop, h):
                    crops.append(crop)
            
            # 如果回退後覆蓋率仍低，強制三等分
            total_crop_h = sum(crop.shape[0] for crop in crops)
            if total_crop_h / h < 0.8:
                n_slices = 3
                slice_h = h // n_slices
                crops = [img[i:i+slice_h] for i in range(0, h, slice_h)]
        
        # 檢查是否裁切過碎
        if len(crops) > 3:
            avg_crop_h = sum(crop.shape[0] for crop in crops) / len(crops)
            if avg_crop_h < 950:  # 提高門檻
                n_slices = 2 if h < 3500 else 3  # 中圖鎖在 2 片
                slice_h = h // n_slices
                crops = [img[i:i+slice_h] for i in range(0, h, slice_h)]
        
        # 合併過小的相鄰片段
        merged_crops = []
        i = 0
        while i < len(crops):
            if i < len(crops) - 1 and crops[i].shape[0] < 350:
                # 合併當前片段和下一片段
                merged = np.vstack((crops[i], crops[i+1]))
                merged_crops.append(merged)
                i += 2
            else:
                merged_crops.append(crops[i])
                i += 1
        
        return {
            "success": True,
            "crops": merged_crops,
            "height": h,
            "width": w
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# ───────────────────────────── 批次處理函數

def clean_cropped_dirs(base_dir: Path) -> None:
    """清理所有 cropped 目錄"""
    try:
        for product_dir in base_dir.iterdir():
            if not product_dir.is_dir() or not product_dir.name.startswith('product_'):
                continue
            images_dir = product_dir / "images"
            if not images_dir.exists():
                continue
            cropped_dir = images_dir / "cropped"
            if cropped_dir.exists():
                try:
                    shutil.rmtree(cropped_dir, ignore_errors=True)
                    logging.info(f"已刪除目錄: {cropped_dir}")
                except Exception as e:
                    logging.warning(f"無法刪除目錄 {cropped_dir}: {e}")
    except Exception as e:
        logging.error(f"清理 cropped 目錄時發生錯誤: {e}")

def get_all_images(base_dir: Path, exts: Tuple[str, ...]) -> List[Path]:
    """獲取所有需要處理的圖片路徑"""
    www_dir = base_dir / "WWW_Collection"
    results_dir = base_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        clean_cropped_dirs(www_dir)
    except Exception as e:
        logging.warning(f"清理舊目錄時發生錯誤: {e}")
    
    image_paths = []
    for product_dir in www_dir.iterdir():
        if product_dir.is_dir() and product_dir.name.startswith('product_'):
            images_dir = product_dir / "images"
            if images_dir.exists():
                for ext in exts:
                    image_paths.extend(images_dir.glob(f"*{ext}"))
                
    return image_paths

def save_results(results: List[Dict[str, Any]], failed: List[Dict[str, Any]], args: argparse.Namespace) -> None:
    """保存處理結果"""
    base_dir = Path(__file__).parent.parent
    results_dir = base_dir / "results"
    
    # 儲存成功結果
    output_file = results_dir / "crop_meta.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(to_serializable(results), f, cls=NumpyEncoder, ensure_ascii=False, indent=2)
    logging.info(f"結果已儲存至 {output_file}")
    
    # 儲存失敗記錄
    if failed:
        failed_file = results_dir / "failed.json"
        with open(failed_file, 'w', encoding='utf-8') as f:
            json.dump(to_serializable(failed), f, ensure_ascii=False, indent=2)
        logging.info(f"失敗記錄已儲存至 {failed_file}")

def process_image(img_path: Path, args: argparse.Namespace) -> Dict[str, Any]:
    """處理單張圖片"""
    try:
        # 嘗試讀取圖片，最多重試3次
        img = None
        for attempt in range(3):
            try:
                img = cv2.imread(str(img_path))
                if img is not None and img.size > 0:  # 使用 size 而不是 empty
                    break
                time.sleep(0.1)  # 等待100ms後重試
            except Exception as e:
                logging.warning(f"第 {attempt + 1} 次讀取圖片失敗: {img_path} - {str(e)}")
                time.sleep(0.1)
        
        if img is None or img.size == 0:  # 使用 size 而不是 empty
            raise ValueError(f"無法讀取圖片: {img_path}")
            
        # 建立輸出目錄
        out_dir = img_path.parent / "cropped"
        out_dir.mkdir(parents=True, exist_ok=True)
        
        # 裁切圖片
        result = smart_crop(img)
        
        if not result["success"]:
            raise ValueError(result["error"])
        
        # 儲存裁切後的圖片
        crops = []
        for i, crop in enumerate(result["crops"]):
            out_path = out_dir / f"{img_path.stem}_crop{i+1}{img_path.suffix}"
            cv2.imwrite(str(out_path), crop)
            crops.append({
                "path": str(out_path),
                "height": crop.shape[0],
                "width": crop.shape[1]
            })
        
        return {
            "path": str(img_path),
            "crops": crops,
            "height": result["height"],
            "width": result["width"]
        }
        
    except Exception as e:
        logging.error(f"處理圖片失敗: {img_path} - {str(e)}")
        return {
            "path": str(img_path),
            "error": str(e)
        }

# ───────────────────────────── CLI

def cli() -> argparse.Namespace:
    """解析命令列參數"""
    p = argparse.ArgumentParser(description="批次裁切圖片處理器")
    p.add_argument("--ratio", type=float, default=0.03,
                  help="白色區域判定比例（預設 0.03）")
    p.add_argument("--workers", type=int, 
                  default=min(32, (os.cpu_count() or 4)*4),
                  help="並行處理數（預設 CPU核心數×4）")
    p.add_argument("--ext", default="jpg,jpeg,png",
                  help="要處理的副檔名（預設 jpg,jpeg,png）")
    return p.parse_args()

def main():
    """主函數"""
    # 解析命令列參數
    args = cli()
    IMG_EXTS = tuple(f".{e.lower()}" for e in args.ext.split(','))
    
    # 設定日誌
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # 記錄開始時間
    t0 = time.time()
    
    # 清理前一次的記錄和已轉換的圖片
    base_dir = Path(__file__).parent.parent
    www_dir = base_dir / "WWW_Collection"
    results_dir = base_dir / "results"
    
    # 清理記錄檔案
    if results_dir.exists():
        try:
            for file in results_dir.glob("*.json"):
                try:
                    file.unlink()
                    logging.info(f"已刪除舊記錄: {file}")
                except Exception as e:
                    logging.warning(f"無法刪除檔案 {file}: {e}")
        except Exception as e:
            logging.warning(f"清理舊記錄時發生錯誤: {e}")
    
    # 清理所有 cropped 目錄
    if www_dir.exists():
        try:
            clean_cropped_dirs(www_dir)
        except Exception as e:
            logging.warning(f"清理已轉換圖片時發生錯誤: {e}")
    
    # 獲取所有圖片路徑
    image_paths = get_all_images(base_dir, IMG_EXTS)
    if not image_paths:
        logging.warning("沒有找到需要處理的圖片")
        return
    
    logging.info(f"找到 {len(image_paths)} 張圖片需要處理")
    
    # 使用線程池處理圖片
    results = []
    failed = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_map = {executor.submit(process_image, p, args): p for p in image_paths}
        
        for i, future in enumerate(as_completed(future_map), 1):
            try:
                result = future.result()
                if "error" in result:
                    failed.append(result)
                else:
                    results.append(result)
                logging.info(f"完成處理: {future_map[future].name}")
            except Exception as e:
                logging.error(f"處理圖片 {future_map[future]} 時發生錯誤: {e}")
                failed.append({
                    "path": str(future_map[future]),
                    "error": str(e)
                })
    
    # 儲存結果
    save_results(results, failed, args)
    
    # 輸出統計資訊
    logging.info(f"處理完成！成功: {len(results)} 張，失敗: {len(failed)} 張")
    if failed:
        logging.warning(f"失敗的圖片已記錄在 {results_dir}/failed.json")
    
    # 輸出總耗時
    logging.info(f"總耗時: {time.time() - t0:.2f} 秒")

if __name__ == "__main__":
    main() 