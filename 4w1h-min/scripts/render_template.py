#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import sys
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

# 基礎注意事項（所有商品通用）
DEFAULT_NOTICES = [
    "原廠授權公司貨，請放心選購。",
    "鑑賞期非試用期，經拆封使用過後無提供退換貨服務。",
    "首次使用前請以中性清潔劑手洗並充分乾燥。",
    "商品顏色會因拍照光線環境或手機螢幕色差等因素有所差異，依實際出貨為準。",
    "商品細節如有疑問，歡迎聯繫客服。"
]

def to_cdn(filename):
    """將檔案名稱轉換為 CDN URL"""
    # 這裡可以根據實際需求修改 CDN 路徑
    return f"https://cdn.shopify.com/s/files/1/0633/7511/4460/files/{filename}"

def merge_notices(config_notices):
    """合併基礎注意事項和商品特定注意事項"""
    # 如果配置檔中有注意事項，則合併
    if config_notices:
        return DEFAULT_NOTICES + config_notices
    return DEFAULT_NOTICES

def render_template(config_path, output_path=None):
    """渲染模板並輸出 HTML 檔案"""
    # 讀取設定檔
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # 設定 Jinja2 環境
    env = Environment(
        loader=FileSystemLoader(os.path.dirname(__file__)),
        autoescape=True
    )
    
    # 註冊自定義過濾器
    env.filters['to_cdn'] = to_cdn

    # 載入模板
    template = env.get_template('index_template.html.jinja')

    # 轉換資料格式以符合模板需求
    template_data = {
        "images": {
            "hero": {"filename": config["images"]["hero"]["filename"], "alt": config["images"]["hero"]["alt"]},
            "logo": {"filename": "4W1H_logo.png", "alt": "4W1H 品牌標誌"},
            "thema": {"filename": config["images"]["thema"]["filename"], "alt": config["images"]["thema"]["alt"]},
            "divider": {"filename": "4w1h-divider.png", "alt": ""},
            "slides": config["images"]["slides"],
            "notice": config.get("notice_img")  # 如果有 notice 圖片可以加入
        },
        "intro_paragraphs": config.get("intro", []),  # 品牌介紹段落
        "product_intro": config["desc"],  # 產品介紹
        "wh_items": [
            {
                "title_img": {"filename": f"4w1h-ttl-{item['title'].lower()}.png", "alt": item["title"]},
                "description": item["text"]
            }
            for item in config["wh"]
        ],
        "features": [
            {
                "image": {"filename": feature["filename"], "alt": feature["alt"]},
                "title": feature["title"],
                "description": feature["desc"],
                "youtube": feature.get("youtube")  # 從 feature 中提取 YouTube 影片資訊
            }
            for feature in config["features"]
        ],
        "hashtags": config["hashtags"].split(),
        "spec": {item["label"]: item["value"] for item in config["spec"]},
        "notices": merge_notices(config.get("notices", []))  # 合併基礎注意事項
    }

    # 渲染模板
    html = template.render(**template_data)

    # 如果沒有指定輸出路徑，則使用設定檔名稱作為輸出檔名
    if output_path is None:
        output_path = Path(config_path).parent / "index.html"

    # 寫入輸出檔案
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"已成功生成 HTML 檔案：{output_path}")

def process_all_products(products_dir):
    """處理所有產品的配置檔"""
    products_dir = Path(products_dir)
    if not products_dir.exists():
        print(f"錯誤：找不到產品目錄 {products_dir}")
        return

    # 遍歷所有產品目錄
    for product_dir in products_dir.iterdir():
        if not product_dir.is_dir():
            continue

        config_path = product_dir / "config.zh.json"
        if not config_path.exists():
            print(f"警告：找不到配置檔 {config_path}")
            continue

        try:
            render_template(config_path)
        except Exception as e:
            print(f"處理 {product_dir.name} 時發生錯誤：{str(e)}")

def main():
    """主程式"""
    if len(sys.argv) < 2:
        print("使用方式：")
        print("1. 處理單一產品：python render_template.py <config.json> [output.html]")
        print("2. 處理所有產品：python render_template.py --all <products_dir>")
        sys.exit(1)

    if sys.argv[1] == "--all":
        if len(sys.argv) < 3:
            print("錯誤：請指定產品目錄")
            sys.exit(1)
        process_all_products(sys.argv[2])
    else:
        config_path = sys.argv[1]
        output_path = sys.argv[2] if len(sys.argv) > 2 else None
        try:
            render_template(config_path, output_path)
        except Exception as e:
            print(f"錯誤：{str(e)}")
            sys.exit(1)

if __name__ == '__main__':
    main() 