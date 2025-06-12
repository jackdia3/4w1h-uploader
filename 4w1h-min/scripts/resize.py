#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from pathlib import Path
from PIL import Image

# 設定基準目錄（專案根目錄）
BASE_DIR = Path(__file__).resolve().parent.parent
PRODUCTS_DIR = BASE_DIR / "products"

# 目標尺寸和背景顏色
TARGET_SIZE = (1000, 1000)
BG_COLOR = (0, 0, 0, 0)  # 透明背景

def add_padding(img, target_size=TARGET_SIZE, bg_color=BG_COLOR):
    """為圖片加上透明邊框，使其達到目標尺寸"""
    # 創建新的透明背景圖片
    new_img = Image.new("RGBA", target_size, bg_color)
    
    # 計算置中位置
    width, height = img.size
    left = (target_size[0] - width) // 2
    top = (target_size[1] - height) // 2
    
    # 將原圖貼到新圖片上
    if img.mode == "RGBA":
        new_img.paste(img, (left, top), img)
    else:
        # 如果原圖不是 RGBA 模式，先轉換
        img_rgba = img.convert("RGBA")
        new_img.paste(img_rgba, (left, top), img_rgba)
    
    return new_img

def process_all_slides():
    """處理所有產品的 slides 圖片"""
    # 確保 products 目錄存在
    if not PRODUCTS_DIR.exists():
        print(f"建立 products 目錄：{PRODUCTS_DIR}")
        PRODUCTS_DIR.mkdir(parents=True, exist_ok=True)
        return

    # 遍歷所有產品目錄
    for prod in os.listdir(PRODUCTS_DIR):
        prod_dir = PRODUCTS_DIR / prod
        if not prod_dir.is_dir():
            continue

        # 處理 webp 目錄
        webp_dir = prod_dir / "images" / "webp"
        if not webp_dir.exists():
            continue

        print(f"處理產品：{prod}")
        for img in os.listdir(webp_dir):
            if not img.endswith('.webp'):
                continue

            # 只處理 slide 圖片
            if "_slide_" not in img:
                continue

            img_path = webp_dir / img
            try:
                with Image.open(img_path) as im:
                    # 檢查圖片尺寸
                    width, height = im.size
                    if width != TARGET_SIZE[0] or height != TARGET_SIZE[1]:
                        # 加上透明邊框
                        padded_img = add_padding(im)
                        # 儲存調整後的圖片
                        padded_img.save(img_path, quality=95, optimize=True)
                        print(f"已調整圖片：{img}")
            except Exception as e:
                print(f"處理 {img} 時發生錯誤：{str(e)}")

if __name__ == "__main__":
    try:
        process_all_slides()
    except Exception as e:
        print(f"執行時發生錯誤：{str(e)}")