#!/usr/bin/env python3
"""
Wild Wild West 商品爬蟲：
- 下載商品資訊
- 下載商品圖片
- 儲存原始資料
"""
import json, os, re, time, unicodedata, pathlib
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from PIL import Image
from io import BytesIO

# 基本設定
BASE = "https://wildwildwest.co.kr"
PRODUCTS = [
    {"id": "956", "name": "專業級耐磨麂皮焚火手套"},
    {"id": "907", "name": "Goal Zero 金屬燈帽＋燈衣套組 (霧黑)"},
    {"id": "974", "name": "Log Table 焚火桌 (鋁合金天板)"},
    # {"id": "630", "name": "Goal Zero 金屬燈帽＋燈衣套組 (霧銀)"},
    # {"id": "516", "name": "Log Table 焚火桌 (黑天板)"},
    # {"id": "383", "name": "Log Table 焚火桌 (不鏽鋼天板)"},
    # {"id": "321", "name": "Wild Wild West  戰術面紙套"}
]
OUT = pathlib.Path(__file__).resolve().parents[1] / "products" / "WWW_Collection"
OUT.mkdir(parents=True, exist_ok=True)

HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}

def download_image(url: str, save_path: pathlib.Path) -> bool:
    """下載圖片"""
    try:
        r = requests.get(url, headers=HDRS, timeout=10)
        r.raise_for_status()
        
        # 確保目錄存在
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 儲存圖片
        with open(save_path, "wb") as f:
            f.write(r.content)
        
        print(f"✅ 下載圖片：{save_path.name}")
        return True
    except Exception as e:
        print(f"× 下載圖片失敗：{url} - {e}")
        return False

def analyze_product(url: str, product_id: str, product_name: str):
    """分析產品頁面"""
    print(f"\n分析產品：{product_name}")
    
    try:
        r = requests.get(url, headers=HDRS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        
        # 建立產品目錄
        product_dir = OUT / f"product_{product_id}"
        product_dir.mkdir(exist_ok=True)
        
        # 儲存原始 HTML
        with open(product_dir / "raw.html", "w", encoding="utf-8") as f:
            f.write(r.text)
        
        # 分析頁面結構
        analysis = {
            "url": url,
            "product_id": product_id,
            "product_name": product_name,
            "title": soup.title.text if soup.title else None,
            "meta_description": soup.find("meta", {"name": "description"})["content"] if soup.find("meta", {"name": "description"}) else None,
            "images": [],
            "specs": [],
            "features": []
        }
        
        # 下載所有圖片
        for img in soup.select("img"):
            src = img.get("src", "")
            img_name = src.split("/")[-1]

            # 檔名黑名單，過濾掉不必要的 UI 圖片
            blacklist = [
                'best.png', 'new.png',
                'F2775_%EB%B0%B0%EC%86%A1%EC%9C%A0%EC%9D%98%EC%82%AC%ED%95%AD_02.jpg',
                'F2776_%EB%B0%B0%EC%86%A1%EC%9C%A0%EC%9D%98%EC%82%AC%ED%95%AD_03.jpg',
                'F1533_%EB%B0%B0%EC%86%A1%EC%9C%A0%EC%9D%98%EC%82%AC%ED%95%AD_02.jpg',
                'F1534_%EB%B0%B0%EC%86%A1%EC%9C%A0%EC%9D%98%EC%82%AC%ED%95%AD_03.jpg'
            ]
            if not src or "mangboard" not in src or \
               img_name.startswith('btn_') or \
               img_name.startswith('icon_') or \
               img_name.lower().endswith('.gif') or \
               img_name in blacklist:
                continue

            if src and "mangboard" in src:
                # 建立圖片資訊
                img_info = {
                    "src": src,
                    "alt": img.get("alt", ""),
                    "class": img.get("class", []),
                    "id": img.get("id", ""),
                    "parent_tag": img.parent.name if img.parent else None,
                    "parent_class": img.parent.get("class", []) if img.parent else None,
                    "parent_id": img.parent.get("id", "") if img.parent else None,
                    "is_main": "main" in src.lower() or "thumb" in src.lower()
                }
                
                # 下載圖片
                img_path = product_dir / "images" / img_name
                if download_image(src, img_path):
                    img_info["local_path"] = str(img_path.relative_to(OUT))
                    analysis["images"].append(img_info)
        
        # 分析規格表
        for table in soup.select("table"):
            specs = []
            for row in table.select("tr"):
                th = row.select_one("th")
                td = row.select_one("td")
                if th and td:
                    specs.append({
                        "label": th.text.strip(),
                        "value": td.text.strip()
                    })
            if specs:
                analysis["specs"].append(specs)
        
        # 分析特點
        for ul in soup.select("ul"):
            features = []
            for li in ul.select("li"):
                features.append(li.text.strip())
            if features:
                analysis["features"].append(features)
        
        # 儲存分析結果
        with open(product_dir / "analysis.json", "w", encoding="utf-8") as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 分析完成：{product_name}")
        return analysis
        
    except Exception as e:
        print(f"× 分析失敗：{e}")
        return None

def main():
    """主程式"""
    print(f"開始下載 Wild Wild West 商品資訊")
    
    # 分析每個產品
    for product in PRODUCTS:
        url = f"{BASE}/online-shop/?vid={product['id']}"
        analyze_product(url, product["id"], product["name"])
        time.sleep(1)  # 避免請求過於頻繁
    
    print("\n✅ 完成所有商品分析")

if __name__ == "__main__":
    main() 