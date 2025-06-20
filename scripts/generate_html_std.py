# -*- coding: utf-8 -*-
"""
依據 analysis_std.json 產出最終商品頁 (index.html)
--------------------------------------------------
1. 以 blocks 原始順序來決定圖片排列，確保與官網相符。
2. 同步輸出對應的翻譯文字 (blocks › texts)。
3. 若同一張長圖被裁成多張 -cropXX.jpg，會依序插入所有裁切圖。
4. 仍支援 NOTICE / SHOP 兩張特殊提示圖，並內建預設繁中文字。

使用方法：
    python scripts/generate_html_std.py  # 於 repo 根目錄執行

相依套件：
    pip install Jinja2
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from jinja2 import Environment, FileSystemLoader  # type: ignore

# ------------------------------------------------------------
# 基本設定
# ------------------------------------------------------------
CDN_BASE_URL = "https://cdn.shopify.com/s/files/1/0633/7511/4460/files/"
BASE_DIR = Path("WWW_Collection")
TEMPLATE_PATH = Path("index_template_std.html.jinja")

# 需插入固定文案的圖片檔名（完整檔名，大小寫需一致）
NOTICE_IMG_KEYS = {
    "F2775_%EB%B0%B0%EC%86%A1%EC%9C%A0%EC%9D%98%EC%82%AC%ED%95%AD_02.jpg",
    "F2775_%EB%B0%B0%EC%86%A1%EC%9C%A0%EC%9D%98%EC%82%AC%ED%95%AD_02_1.jpg",
}
SHOP_IMG_KEYS = {
    "F2776_%EB%B0%B0%EC%86%A1%EC%9C%A0%EC%9D%98%EC%82%AC%ED%95%AD_03.jpg",
    "F2776_%EB%B0%B0%EC%86%A1%EC%9C%A0%EC%9D%98%EC%82%AC%ED%95%AD_03_1.jpg",
}

# 固定文案（繁體中文）
NOTICE_TEXT_ZH = [
    "為了打造更好的品質，產品的部分材料和材質可能在無預告的情況下更改。",
    "所有商品的特性可能會因設計的變更、生產工藝等而略有差異。",
    "尺寸可能因測量位置不同而有誤差。",
    "根據顯示器的解析度、亮度、電腦或裝置的顯示環境不同，顏色可能會有差異。",
    "請避免將產品接近火源或高溫處。",
    "商品品質基準依據公平交易委員會頒布之「消費者紛爭解決標準」。",
    "",
    "© 2017. WILDWILDWEST All rights reserved.",
    "本資料的設計著作權屬於 WILDWILDWEST。",
    "圖片及文字的所有權歸原創所有，嚴禁未經授權擅自使用、修改、轉載。",
    "如未經協議而使用，將依法承擔法律責任。",
]

SHOP_TEXT_ZH = [
    "【商品結帳資訊】",
    "為保障付款安全，可能會有電話確認程序。",
    "若判定訂單為非正常訂購或冒用他人信用卡，將可能取消訂單。",
    "免運優惠僅限部分區域，偏遠地區需自付運費。",
    "訂單完成後 7 天內未付款者，系統將自動取消訂單。",
    "",
    "【品牌出貨說明】",
    "品牌合作商品通常於 2–3 日內出貨。",
    "若與 WILDWILDWEST 其他商品合併訂購，出貨時間可能會不同。",
    "若因商品問題無法出貨，將主動聯繫通知。",
    "",
    "【商品退換說明】",
    "收到商品後 7 天內可退換貨（商品未拆封、無損壞者）。",
    "若商品因使用、清洗或人為損壞，恕不接受退換。",
    "開封使用後無法恢復原狀之商品，恕無法退換。",
    "瑕疵商品請拍照並與客服聯繫，經確認後可申請更換。",
    "有下列情況者恕不接受退換：",
    "  - 顧客責任造成的破損或污染（香味、煙味、洗滌、刮痕等）",
    "  - 商品本體、包裝、配件遺失或損毀",
    "  - 僅為主觀不滿意（顏色、大小等）",
]

# ------------------------------------------------------------
# 工具函式
# ------------------------------------------------------------

def to_cdn(filename: str) -> str:
    """轉成 Shopify CDN URL"""
    fname = Path(filename).name
    return CDN_BASE_URL + fname


def natural_sort_key(s: str):
    """用於排序字串，使 crop01, crop02… 按數字排序"""
    import re

    def try_int(text: str):
        return int(text) if text.isdigit() else text

    return [try_int(c) for c in re.split(r"(\d+)", s)]


# ------------------------------------------------------------
# 主要流程
# ------------------------------------------------------------

def build_crop_map(images_dir: Path) -> Dict[str, List[str]]:
    crop_map: Dict[str, List[str]] = {}
    for fname in images_dir.iterdir():
        if fname.suffix.lower() == ".jpg" and "-crop" in fname.stem:
            original = fname.stem.split("-crop")[0] + fname.suffix  # 含副檔名
            crop_map.setdefault(original, []).append(fname.name)
    # 排序 cropXX
    for lst in crop_map.values():
        lst.sort(key=natural_sort_key)
    return crop_map


def collect_main_images(
    std_blocks: List[dict],
    crop_map: Dict[str, List[str]],
) -> List[dict]:
    """將 blocks → main_images (保持原順序)"""
    main_images: List[dict] = []

    for block in std_blocks:
        texts = block.get("texts", {})
        for img_path in block.get("images", []):
            fname = Path(img_path).name

            # 1. 若有裁切圖，依序展開
            if fname in crop_map:
                for crop_fname in crop_map[fname]:
                    main_images.append(
                        {
                            "src": to_cdn(crop_fname),
                            "is_crop": True,
                            "texts": texts,
                            "alt": "",
                        }
                    )
            else:
                # 2. 特殊 NOTICE / SHOP 圖
                if fname in NOTICE_IMG_KEYS:
                    main_images.append(
                        {
                            "src": to_cdn(fname),
                            "is_crop": False,
                            "texts": {"zh_TW": NOTICE_TEXT_ZH},
                            "alt": "",
                        }
                    )
                elif fname in SHOP_IMG_KEYS:
                    main_images.append(
                        {
                            "src": to_cdn(fname),
                            "is_crop": False,
                            "texts": {"zh_TW": SHOP_TEXT_ZH},
                            "alt": "",
                        }
                    )
                else:
                    # 3. 一般長圖
                    main_images.append(
                        {
                            "src": to_cdn(fname),
                            "is_crop": False,
                            "texts": texts,
                            "alt": "",
                        }
                    )
    return main_images


def render_product(prod_path: Path, env: Environment):
    std_path = prod_path / "analysis_std.json"
    raw_path = prod_path / "analysis.json"
    images_dir = prod_path / "images"

    if not std_path.exists() or not raw_path.exists():
        return  # 必須兩檔皆存在

    with std_path.open(encoding="utf-8") as f:
        std_data = json.load(f)
    with raw_path.open(encoding="utf-8") as f:
        raw_data = json.load(f)

    crop_map = build_crop_map(images_dir)
    main_images = collect_main_images(std_data.get("blocks", []), crop_map)

    # 裝填到 template context
    ctx = {
        **std_data,
        "product_name": raw_data.get("product_name", ""),
        "meta_description": raw_data.get("meta_description", ""),
        "main_images": main_images,
    }

    template = env.get_template(str(TEMPLATE_PATH))
    out_html = template.render(**ctx)
    output_file = prod_path / "index.html"
    output_file.write_text(out_html, encoding="utf-8")
    print(f"✓ 產生完成: {output_file.relative_to(Path.cwd())}")


def main():
    if not BASE_DIR.exists():
        raise SystemExit(f"資料夾不存在: {BASE_DIR}")

    env = Environment(loader=FileSystemLoader(str(Path.cwd())))
    env.globals["to_cdn"] = to_cdn

    for prod_folder in sorted(BASE_DIR.iterdir(), key=lambda p: p.name):
        if prod_folder.is_dir() and prod_folder.name.startswith("product_"):
            render_product(prod_folder, env)


if __name__ == "__main__":
    main()