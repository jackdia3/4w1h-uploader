import sys
from PIL import Image
import os
from pathlib import Path

def is_mostly_white(img):
    """檢查圖片是否主要為白色"""
    datas = img.getdata()
    white_pixels = 0
    total_pixels = 0
    
    for item in datas:
        if item[3] > 0:  # 只計算非透明像素
            total_pixels += 1
            # 如果 RGB 值都大於 200，視為白色
            if item[0] > 200 and item[1] > 200 and item[2] > 200:
                white_pixels += 1
    
    # 如果白色像素佔比超過 80%，則視為白色圖片
    return total_pixels > 0 and (white_pixels / total_pixels) > 0.8

def convert_to_black(img):
    """將圖片轉換為黑色"""
    datas = img.getdata()
    new_data = []
    for item in datas:
        if item[3] == 0:
            new_data.append(item)
        else:
            new_data.append((0, 0, 0, item[3]))
    return new_data

def process_image(img_path):
    """處理單一圖片"""
    try:
        print(f"正在處理：{img_path}")
        img = Image.open(img_path).convert("RGBA")
        
        # 檢查是否為白色圖片
        if is_mostly_white(img):
            print(f"  - 檢測到白色圖片")
            # 先將原始檔案改名為 _white 版本
            base_name = os.path.splitext(img_path)[0]
            ext = os.path.splitext(img_path)[1]
            white_path = f"{base_name}_white{ext}"
            os.rename(img_path, white_path)
            
            # 處理黑色版本
            new_data = convert_to_black(img)
            img.putdata(new_data)
            # 黑色版本使用原始檔名
            img.save(img_path)
            print(f"  - 原始檔案改名為：{white_path}")
            print(f"  - 已產生黑色版本：{img_path}")
        else:
            print(f"  - 跳過（非白色圖片）")
            
    except Exception as e:
        print(f"處理 {img_path} 時發生錯誤：{str(e)}")

def main():
    # 取得產品目錄路徑
    script_dir = Path(__file__).parent
    products_dir = script_dir.parent / "products"
    
    print(f"腳本目錄：{script_dir}")
    print(f"產品目錄：{products_dir}")
    
    if not products_dir.exists():
        print(f"錯誤：找不到產品目錄 {products_dir}")
        return
        
    # 遍歷所有產品目錄
    product_dirs = list(products_dir.iterdir())
    print(f"找到 {len(product_dirs)} 個產品目錄")
    
    for product_dir in product_dirs:
        if not product_dir.is_dir():
            continue
            
        print(f"\n檢查產品目錄：{product_dir.name}")
        # 尋找 thema.webp 檔案
        thema_file = product_dir / "images" / "webp" / f"uncle-benny-{product_dir.name}_thema.webp"
        if thema_file.exists():
            print(f"找到 thema.webp：{thema_file}")
            process_image(str(thema_file))
        else:
            print(f"找不到 thema.webp：{thema_file}")

if __name__ == "__main__":
    main()