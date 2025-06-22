#!/usr/bin/env python3
"""
Batch smart‑cropper
===================

使用範例
--------
$ python smart_crop_v2.py /path/to/product_383
# → 於 /path/to/product_383/split 產生裁片，且寫入 process_summary.json

可選參數：
  --out   指定輸出根資料夾（預設為 <input>/split）
  --ext   逗號分隔的副檔名列表（預設 jpg,jpeg,png,webp,bmp,tif,tiff）

程式特色
--------
* **兩階段 cut‑line 偵測**：
  1. 連續純白行 (projection)
  2. 長圖 edge‑projection（僅於 h > 2,000 時啟用）
* **動態門檻** 依圖片寬度自調。
* 自動去除連續純白邊框 & 小碎片。
* 輸出 JSON summary 供後續流水線使用。
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime
from itertools import chain
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np
from PIL import Image

# ───────────────────────────── 常數 及 logging
LONG_SIDE_THRESHOLD = 2_000       # h > 此值視為長圖，啟用 edge‑projection
MIN_CROP_HEIGHT = 120             # 裁片最小高度（px）
BG_THRESH = 245                   # > 此灰度視為白
CONSEC_BORDER = 15                # 邊框掃描連續白行/列門檻
MIN_BAND_MEAN = 250              # 判斷 '純白帶' 的平均亮度門檻
MIN_WHITE_RATIO = 0.92           # 該 band 內 >245 的像素佔比

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("smart_crop")

# ───────────────────────────── 基本工具

def trim_border(img: np.ndarray, bg_thresh: int = BG_THRESH, consec: int = CONSEC_BORDER) -> Tuple[int, int, int, int]:
    """偵測四周純白邊框，回傳 (top, bottom, left, right) 應裁掉的像素數"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    def _scan(indices, axis: str):
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


def merge_close(lines: List[int], orig_h: int, ratio: float = 0.06) -> List[int]:
    """合併彼此距離過近的 cut‑lines"""
    if not lines:
        return []
    min_gap = max(120, int(ratio * orig_h))
    merged = [lines[0]]
    for y in lines[1:]:
        if y - merged[-1] >= min_gap:
            merged.append(y)
    return merged


# ───────────────────────────── cut‑line 偵測

def blank_projection(gray: np.ndarray) -> List[int]:
    """依純白帶偵測 cut‑lines（動態門檻）"""
    h, w = gray.shape
    if w <= 800:
        min_blank_run = 6
    elif w <= 1600:
        min_blank_run = 8
    else:
        min_blank_run = 10

    # 算每列 "真白"(>245) 的比例 & 平均亮度
    white_ratio = (gray > BG_THRESH).mean(axis=1)
    row_mean = gray.mean(axis=1)

    blank_mask = (white_ratio > MIN_WHITE_RATIO) & (row_mean > MIN_BAND_MEAN)

    lines, run = [], None
    for y, blank in enumerate(blank_mask):
        if blank and run is None:
            run = y
        elif not blank and run is not None:
            if y - run >= min_blank_run:
                lines.append((run + y - 1) // 2)
            run = None
    if run is not None and h - run >= min_blank_run:
        lines.append((run + h - 1) // 2)
    return lines


def long_edge_projection(gray: np.ndarray) -> List[int]:
    """長圖才啟用：找邊緣稀疏帶"""
    h, w = gray.shape
    if h <= LONG_SIDE_THRESHOLD:
        return []
    edges = cv2.Canny(gray, 50, 150)
    profile = edges.sum(axis=1) / w
    low = profile < 0.05 * 255
    kernel = np.ones((40, 1), np.uint8)
    band = cv2.morphologyEx(low.astype(np.uint8)[:, None], cv2.MORPH_CLOSE, kernel)[:, 0]

    lines = []
    start = None
    for y, val in enumerate(band):
        if val and start is None:
            start = y
        elif not val and start is not None:
            if 0.1 * h < (mid := (start + y) // 2) < 0.9 * h:
                lines.append(mid)
            start = None
    return lines


# ───────────────────────────── 保留/捨棄邏輯

def small_fragment(h_seg: int, width: int, orig_h: int, is_text: bool = False) -> bool:
    """判斷片段是否過小可丟棄"""
    min_keep = max(int(0.08 * orig_h), int(0.25 * width), MIN_CROP_HEIGHT)
    return (h_seg < min_keep) and (not is_text)


def looks_like_text(seg: np.ndarray) -> bool:
    gray = cv2.cvtColor(seg, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    ratio = edges.sum() / edges.size
    return ratio > 0.05 and gray.std() < 15


# ───────────────────────────── 主裁切

def crop_image(img: np.ndarray, image_path: Path, out_root: Path) -> List[dict]:
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    lines = merge_close(sorted(set(blank_projection(gray) + long_edge_projection(gray))), h)
    # 若無切點 → 不裁但仍輸出 1 張
    lines = [0] + lines + [h]

    # 處理相對路徑
    try:
        rel_dir = image_path.parent.relative_to(out_root.parent)
    except ValueError:
        # out_root 不在 input_dir 裡 → 只用最後一層資料夾名
        rel_dir = Path(image_path.parent.name)
    out_dir = out_root / rel_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    crops = []
    crop_idx = 0  # 連續編號計數器
    for idx in range(len(lines) - 1):
        y1, y2 = lines[idx], lines[idx + 1]
        seg_h = y2 - y1
        seg = img[y1:y2]
        if small_fragment(seg_h, w, h, looks_like_text(seg)):
            continue
            
        dst = out_dir / f"{image_path.stem}_crop_{crop_idx}.webp"
        cv2.imwrite(str(dst), seg)
        crops.append(
            {
                "path": str(dst),
                "height": seg_h,
                "width": w,
                "y_start": y1,
                "y_end": y2,
            }
        )
        crop_idx += 1  # 只有成功儲存才增加編號
    return crops


# ───────────────────────────── 批次處理

def process_dir(input_dir: Path, out_root: Path, exts: Tuple[str, ...]):
    summary = {
        "input_dir": str(input_dir),
        "output_dir": str(out_root),
        "start": datetime.now().isoformat(),
        "total_images": 0,
        "total_crops": 0,
        "files": {},
    }
    
    # 檢查是否為單一檔案
    if input_dir.is_file():
        paths = [input_dir]
    else:
        paths = sorted(p for p in input_dir.rglob("*") 
                      if p.suffix.lower().lstrip(".") in exts)
    
    for path in paths:
        try:
            img = cv2.imread(str(path))
            if img is None:
                log.warning(f"⚠️  無法讀取 {path}")
                continue
                
            # 去邊
            t, b, l, r = trim_border(img)
            if any((t, b, l, r)):
                img = img[t : img.shape[0] - b, l : img.shape[1] - r]
                
            crops = crop_image(img, path, out_root)
            summary["total_images"] += 1
            summary["total_crops"] += len(crops)
            summary["files"][str(path)] = crops
            
        except Exception as e:
            log.error(f"處理 {path} 失敗: {e}")
            
    summary["end"] = datetime.now().isoformat()
    with open(out_root / "process_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    log.info(f"✅ 完成！共處理 {summary['total_images']} 張，輸出 {summary['total_crops']} 個裁片")


# ───────────────────────────── CLI

def parse_args():
    p = argparse.ArgumentParser(description="Smart batch cropper")
    p.add_argument("input", type=Path, help="要處理的目錄")
    p.add_argument("--out", type=Path, default=None, help="輸出根資料夾 (預設 <input>/split)")
    p.add_argument(
        "--ext",
        default="jpg,jpeg,png,webp,bmp,tif,tiff",
        help="要處理的副檔名 (逗號分隔)"
    )
    return p.parse_args()


def main():
    args = parse_args()
    input_dir: Path = args.input.resolve()
    out_root: Path = (args.out or (input_dir / "split")).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    exts = tuple(e.lower() for e in args.ext.split(','))
    log.info(f"📂 來源: {input_dir}")
    log.info(f"📦 輸出: {out_root}")
    log.info(f"🔍 副檔名: {exts}")
    process_dir(input_dir, out_root, exts)


if __name__ == "__main__":
    main()
