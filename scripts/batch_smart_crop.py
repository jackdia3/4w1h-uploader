#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批次裁切 /WWW_Collection 內所有圖片：
  1. 先用灰階投影法找水平留白，切長圖
  2. 再用 smartcrop.py 對每一塊找「構圖最佳」的矩形
  3. 存 WebP、寫 JSON
"""

import cv2, json, os, shutil, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from smartcrop import SmartCrop
from PIL import Image
from tqdm import tqdm

# -------------- 參數 -----------------
BASE_DIR   = Path(__file__).resolve().parent
ROOT_DIR   = BASE_DIR.parent / "products" / "WWW_Collection"
OUT_DIR    = BASE_DIR / "results" / "cropped"
META_FILE  = BASE_DIR / "results" / "crop_meta.json"
MAX_WORKER = min(32, os.cpu_count() * 4)
MIN_H_PX   = 300                 # 單塊高度門檻
TARGET_W   = 1000                # smartcrop 目標寬
TARGET_H   = 1000                # smartcrop 目標高
# -------------------------------------

def is_blank_row(row, dark_ratio_th=0.02):
    return (row < 250).mean() < dark_ratio_th

def detect_cut_lines(gray, min_gap=40):
    h, _ = gray.shape
    blank_mask = [is_blank_row(gray[y, :]) for y in range(h)]
    cut = []
    run = None
    for y, blank in enumerate(blank_mask):
        if blank and run is None:
            run = y
        elif not blank and run is not None:
            if y - run > 10:                 # 連續空白列夠多才認定
                cut.append((run + y) // 2)
            run = None
    if run is not None and h - run > 10:
        cut.append((run + h) // 2)

    # 合併太近的 cut line
    merged = []
    for y in cut:
        if not merged or y - merged[-1] > min_gap:
            merged.append(y)
    return merged

def smart_crop_piece(pil_img):
    crop = SmartCrop().crop(pil_img, width=TARGET_W, height=TARGET_H)
    box  = crop["top_crop"]
    x, y = box["x"], box["y"]
    w, h = box["width"], box["height"]
    return pil_img.crop((x, y, x + w, y + h))

def process_one(path: Path):
    try:
        img_bgr = cv2.imread(str(path))
        if img_bgr is None:
            return None

        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        cuts = detect_cut_lines(gray)

        # 加首尾
        h, w = gray.shape
        lines = [0] + cuts + [h]

        out_meta = []
        for idx in range(len(lines) - 1):
            y0, y1 = lines[idx], lines[idx + 1]
            if y1 - y0 < MIN_H_PX:
                continue

            piece = img_bgr[y0:y1, :]
            # PIL 走 RGB
            pil_piece = Image.fromarray(cv2.cvtColor(piece, cv2.COLOR_BGR2RGB))
            cropped   = smart_crop_piece(pil_piece)

            rel_dir   = OUT_DIR / path.relative_to(ROOT_DIR).parent
            rel_dir.mkdir(parents=True, exist_ok=True)
            out_name  = f"{path.stem}_crop_{idx}.webp"
            out_path  = rel_dir / out_name
            cropped.save(out_path, "webp", quality=90, method=6)

            out_meta.append({
                "path": str(out_path),
                "height": cropped.height,
                "width":  cropped.width,
            })
        return {
            "image": str(path),
            "crops": out_meta
        }
    except Exception as e:
        return {"image": str(path), "error": str(e)}

def main():
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    img_paths = [p for p in ROOT_DIR.rglob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
    results   = []

    with ThreadPoolExecutor(MAX_WORKER) as exe:
        futures = {exe.submit(process_one, p): p for p in img_paths}
        for fut in tqdm(as_completed(futures), total=len(futures), desc="Processing"):
            res = fut.result()
            if res: results.append(res)

    META_FILE.parent.mkdir(exist_ok=True)
    with META_FILE.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"✅ 完成！共 {len(results)} 張，metadata -> {META_FILE}")

if __name__ == "__main__":
    tic = time.time()
    main()
    print(f"用時 {time.time() - tic:.1f}s")
