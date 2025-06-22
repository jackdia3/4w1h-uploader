from dataclasses import dataclass, asdict
import cv2
import numpy as np
import logging
from PIL import Image
from pathlib import Path
from image_utils import read_image, ensure_output_dir
import os
from itertools import groupby
import itertools
import matplotlib.pyplot as plt
from typing import Dict, List
import shutil

logger = logging.getLogger(__name__)

# 在 import 區塊之後新增常數與工具函式
LONG_SIDE_THRESHOLD = 2000  # h > 2000 視為長圖
MIN_CROP_HEIGHT = 350       # 裁片最小高度

@dataclass
class CropInfo:
    dst: str
    y_start: int
    y_end: int
    height: int

def debug_cut(gray, lines, refined, path):
    # 只記錄數據，不產生圖檔
    print(f'[DEBUG] {path} | lines: {lines} | refined: {refined}')

def should_drop(crop_h, width, orig_h):
    min_keep = max(int(0.30 * width), int(0.05 * orig_h), 300)
    return crop_h < min_keep

def is_mostly_blank(img, mean_th=248, std_th=2, dark_ratio_th=0.002):
    """檢查圖片是否主要為空白
    使用雙門檻：平均亮度 + 標準差，以及非白像素比例
    """
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape
    if gray.mean() > mean_th and gray.std() < std_th:
        return True
    # 非白像素比例（含灰）再保險一次
    dark_ratio = (gray < 245).sum() / (h * w)
    return dark_ratio < dark_ratio_th

def detect_cut_lines(gray):
    h, w = gray.shape
    # 動態參數
    ratio_thresh = 0.02 if w < 1200 else 0.015
    min_blank_run = 10 if w < 1200 else 15
    SAFE_SCAN = 15 if h < 2000 else 30
    # 計算每行非白像素比例
    row_ratio = np.mean(gray < 245, axis=1)
    blank_mask = row_ratio < ratio_thresh
    # 找連續空白行
    cut_lines = []
    run = 0
    for y, is_blank in enumerate(blank_mask):
        if is_blank:
            run += 1
        else:
            if run >= min_blank_run:
                cut_lines.append(y - run // 2)
            run = 0
    # 合併距離拉大
    cut_lines = merge_close_lines(cut_lines, h)
    # --- 投影法補偵測 ---
    if (len(cut_lines) < 1) and (h >= 3500):
        proj_cuts = find_candidate_bands(gray)
        cut_lines = merge_close_lines(sorted(set(cut_lines + proj_cuts)), h)
    return cut_lines

def merge_close_lines(lines, orig_h, min_gap_ratio=0.06):
    min_gap = max(120, int(min_gap_ratio * orig_h))
    merged = []
    for y in lines:
        if merged and y - merged[-1] < min_gap:
            continue
        merged.append(y)
    return merged

def find_candidate_bands(gray, band_h=40, step=20):
    h, w = gray.shape
    scores = []
    for y in range(0, h - band_h, step):
        band = gray[y:y+band_h]
        scores.append((y, band.mean(), band.std()))
    thresh_mu = 245
    thresh_std = 3
    return [y for y, mu, sd in scores if mu > thresh_mu and sd < thresh_std]

def crop_by_lines(img, cut_lines, output_dir=None, image_path=None):
    height, width = img.shape[:2]
    crops = []
    lines = [0] + cut_lines + [height]
    for i in range(len(lines) - 1):
        start = lines[i]
        end = lines[i + 1]
        crop_height = end - start
        crop = img[start:end, :]
        # 判斷是否丟棄
        if should_drop(crop_height, width, height) and not is_text_image(crop):
            continue
        crop_path = (os.path.join(output_dir, f"{Path(image_path).stem}_crop_{i}.webp")
                    if output_dir else f"{Path(image_path).stem}_crop_{i}.webp")
        if output_dir:
            cv2.imwrite(crop_path, crop)
        crops.append({
            'path': str(crop_path),
            'height': crop_height,
            'width': width
        })
    return crops

def trim_border(img: np.ndarray, bg_thresh: int = 245, consec: int = 20):
    """偵測並回傳應裁掉的 (top, bottom, left, right) 邊框像素數。"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    def _scan(indices, axis: str):
        cnt = 0
        for idx in indices:
            line = gray[idx] if axis == 'row' else gray[:, idx]
            if (line > bg_thresh).all():
                cnt += 1
                if cnt >= consec:
                    continue
            else:
                break
        return cnt

    top = _scan(range(h), 'row')
    bottom = _scan(range(h - 1, -1, -1), 'row')
    left = _scan(range(w), 'col')
    right = _scan(range(w - 1, -1, -1), 'col')
    return top, bottom, left, right

def find_cut_lines(img: np.ndarray, long_side: int = LONG_SIDE_THRESHOLD, band_height: int = 40, edge_ratio: float = 0.05):
    """當影像高度大於 long_side 時，利用邊緣投影尋找低對比水平帶作為切點。"""
    h, w, _ = img.shape
    if h <= long_side:
        return []
    edges = cv2.Canny(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 50, 150)
    horiz_profile = edges.sum(axis=1) / w
    low = (horiz_profile < (edge_ratio * 255)).astype(np.uint8)
    kernel = np.ones((band_height, 1), np.uint8)
    low_band = cv2.morphologyEx(low[:, None], cv2.MORPH_CLOSE, kernel)[:, 0]

    ys, start = [], None
    for i, val in enumerate(low_band):
        if val and start is None:
            start = i
        elif not val and start is not None:
            end = i
            mid = (start + end) // 2
            if 0.1 * h < mid < 0.9 * h:
                ys.append(mid)
            start = None
    return ys

def is_text_image(segment: np.ndarray, edge_density: float = 0.05) -> bool:
    """簡易判斷裁片是否為文字說明圖：高邊緣密度 + 低背景雜訊。"""
    gray = cv2.cvtColor(segment, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    ratio = edges.sum() / edges.size
    bg_std = gray.std()
    return (ratio > edge_density) and (bg_std < 15)

def smart_crop(image_path: str, output_dir: str = None) -> dict:
    try:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"無法讀取圖片: {image_path}")

        # 1) 去白／黑邊
        t, b, l, r = trim_border(img)
        if any([t, b, l, r]):
            img = img[t:img.shape[0]-b, l:img.shape[1]-r]

        h, w = img.shape[:2]
        # icon/窄圖直接略過
        if h < 120 or w < 120:
            return {'success': False, 'error': 'tiny_icon'}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 2) 長圖分割 cut lines
        cut_lines_long = find_cut_lines(img)
        # 3) 空白帶 cut lines (原有)
        cut_lines_blank = detect_cut_lines(gray)
        cut_lines = sorted(set(cut_lines_long + cut_lines_blank))

        if not cut_lines:
            # 無需切割，但若有 trim_border 仍輸出 1 張裁片 (保持介面一致)
            if output_dir:
                out_path = os.path.join(output_dir, f"{Path(image_path).stem}_crop_0.webp")
                cv2.imwrite(out_path, img)
            else:
                out_path = image_path  # 無指定輸出資料夾則覆寫使用者自行決定
            return {
                'success': True,
                'crops': [{
                    'path': str(out_path),
                    'height': img.shape[0],
                    'width': img.shape[1]
                }]
            }

        crops = crop_by_lines(img, cut_lines, output_dir, image_path)
        # 移除小碎片後若無裁片則回傳失敗
        if not crops:
            return {'success': False, 'error': 'all_dropped'}
        return {
            'success': True,
            'crops': crops
        }
    except Exception as e:
        logging.error(f"處理圖片時發生錯誤 {image_path}: {str(e)}")
        return {'success': False, 'error': str(e)}

def detect_cut_lines_sobel(gray: np.ndarray) -> list[int]:
    """使用 Sobel 算子檢測水平線"""
    sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    magnitude = np.sqrt(sobelx**2 + sobely**2)
    magnitude = np.uint8(magnitude * 255 / magnitude.max())
    
    # 水平線檢測
    lines = cv2.HoughLinesP(magnitude, 1, np.pi/180, threshold=100, minLineLength=gray.shape[1]*0.5, maxLineGap=20)
    if lines is None:
        return []
    
    # 提取 y 座標
    y_coords = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if abs(x2 - x1) > abs(y2 - y1):  # 水平線
            y_coords.append((y1 + y2) // 2)
    
    return sorted(list(set(y_coords)))

def detect_cut_lines_by_projection(gray: np.ndarray,
                     max_dark_ratio: float = None,
                     min_blank_run: int = None) -> list[int]:
    h, w = gray.shape
    # 根據解析度自動調整參數
    if max_dark_ratio is None:
        if w <= 800:
            max_dark_ratio = 0.02
        elif w <= 1600:
            max_dark_ratio = 0.015
        else:
            max_dark_ratio = 0.01
    if min_blank_run is None:
        if w <= 800:
            min_blank_run = 6
        elif w <= 1600:
            min_blank_run = 8
        else:
            min_blank_run = 10
    # 非白 = 灰度 < 250
    dark_pixels = (gray < 250).astype(np.uint8)
    row_dark_ratio = dark_pixels.sum(axis=1) / w
    blank_mask = row_dark_ratio < max_dark_ratio
    cut_lines, run_start = [], None
    for y, is_blank in enumerate(blank_mask):
        if is_blank and run_start is None:
            run_start = y
        elif not is_blank and run_start is not None:
            run_len = y - run_start
            if run_len >= min_blank_run:
                cut_lines.append((run_start + y - 1) // 2)
            run_start = None
    if run_start is not None and (h - run_start) >= min_blank_run:
        cut_lines.append((run_start + h - 1) // 2)
    return cut_lines 