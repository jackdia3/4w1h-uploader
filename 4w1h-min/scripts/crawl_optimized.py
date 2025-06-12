#!/usr/bin/env python3
"""
優化版 4w1h 商品爬蟲：
- 支援從 JSON 配置檔讀取 selector
- 更好的錯誤處理和 fallback 機制
- 統一的資料結構
"""
import json, os, re, time, unicodedata, pathlib
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from PIL import Image
from io import BytesIO

# 載入 selector 配置
SCRIPT_DIR = pathlib.Path(__file__).parent
FIELD_SELECTORS = json.load(open(SCRIPT_DIR / "field_selectors.json", encoding="utf-8"))
IMAGE_SELECTORS = json.load(open(SCRIPT_DIR / "image_selectors_optimized.json", encoding="utf-8"))["4w1h"]

BASE = "https://4w1h.jp"
LIST = f"{BASE}/product/"
CSS_BASE = "https://4w1h.jp/wp-content/themes/4w1h_v1.3"

HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}

OUT = pathlib.Path(__file__).resolve().parents[1] / "products"
OUT.mkdir(exist_ok=True)

def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", text)

def get_by_selector(soup: BeautifulSoup, config: dict, default=None):
    """根據配置取得元素內容"""
    try:
        # 主要 selector
        if "selector" in config:
            elem = soup.select_one(config["selector"])
            if elem:
                # 如果有 regex 處理
                if "regex" in config:
                    match = re.search(config["regex"], elem.text.strip())
                    return match.group(1) if match else elem.text.strip()
                # 如果要取屬性
                if "attr" in config:
                    return elem.get(config["attr"], "").strip()
                return elem.text.strip()
        
        # 固定值
        if "value" in config:
            return config["value"]
        
        # Fallback selector
        if "fallback" in config and config["fallback"]:
            if isinstance(config["fallback"], str):
                elem = soup.select_one(config["fallback"])
                return elem.text.strip() if elem else default
            return config["fallback"]
        
        return default
    except Exception as e:
        print(f"  ⚠️ Selector 錯誤: {e}")
        return default

def get_product_code(soup: BeautifulSoup) -> str:
    """取得產品代碼，處理全形字元問題"""
    code = get_by_selector(soup, FIELD_SELECTORS["product_code"], "")
    # 將全形英數字轉為半形
    code = code.translate(str.maketrans(
        "０１２３４５６７８９ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ",
        "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ))
    return code

def get_name(soup: BeautifulSoup) -> str:
    """取得產品名稱"""
    return get_by_selector(soup, FIELD_SELECTORS["product_name"], "")

def get_wh(soup: BeautifulSoup) -> list:
    """取得 4W1H 內容"""
    wh_items = []
    config = FIELD_SELECTORS["wh"]
    wh_elem = soup.select_one(config["container"])
    
    if not wh_elem:
        return wh_items
    
    # 處理 table 中的內容
    for tr in wh_elem.select(config["table_selector"]):
        th = tr.select_one("th")
        td = tr.select_one("td")
        if th and td:
            # 優先從 img alt 取得標題
            img = th.select_one("img[alt]")
            title = img["alt"].strip() if img else th.text.strip()
            text = td.text.strip()
            
            # 處理 rowspan="2" 的情況
            rowspan = td.get("rowspan")
            if rowspan == "2":
                wh_items.append({"title": title, "text": text})
                # 下一個 tr 共用相同的 text
                continue
            
            wh_items.append({"title": title, "text": text})
    
    # 處理 How 區塊
    how_elem = wh_elem.select_one(config["how_selector"])
    if how_elem:
        icon_img = how_elem.select_one("img[alt]")
        title = icon_img["alt"].strip() if icon_img else "How"
        text_elem = how_elem.select_one("span.text")
        text = text_elem.text.strip() if text_elem else ""
        wh_items.append({"title": title, "text": text})
    
    return wh_items

def get_spec(soup: BeautifulSoup) -> list:
    """取得規格表"""
    spec = []
    config = FIELD_SELECTORS["spec"]
    
    # 找到規格表（排除 #wh 內的）
    spec_tbl = soup.select_one(config["selector"])
    if spec_tbl:
        # 確認不在 #wh 內
        parent = spec_tbl.find_parent(id="wh")
        if not parent:
            for tr in spec_tbl.select('tr'):
                th = tr.select_one('th')
                td = tr.select_one('td')
                if th and td:
                    spec.append({
                        "label": th.text.strip(),
                        "value": td.text.strip()
                    })
    return spec

def get_features(soup: BeautifulSoup, code: str, images_dir_webp: pathlib.Path) -> list:
    """取得產品特性"""
    features = []
    config = FIELD_SELECTORS["features"]
    
    for block in soup.select(config["selector"]):
        # 檢查是否有 YouTube
        youtube_elem = block.select_one(config["youtube_selector"])
        title_elem = block.select_one(config["title_selector"])
        
        # 組合描述文字
        desc_list = [p.text.strip() for p in block.select(config["desc_selector"])]
        desc = '<br>'.join(desc_list)
        
        if youtube_elem:
            features.append({
                "filename": None,
                "alt": "",
                "title": title_elem.text.strip() if title_elem else "",
                "desc": desc,
                "youtube": youtube_elem.get('src')
            })
        else:
            img_elem = block.select_one(config["image_selector"])
            filename = None
            alt = ""
            
            if img_elem:
                src_url = img_elem.get('src')
                if src_url:
                    orig_name = os.path.splitext(os.path.basename(src_url))[0]
                    webp_filename = f"uncle-benny-{code}_{orig_name}.webp"
                    webp_path = images_dir_webp / webp_filename
                    download_and_save_webp(src_url, webp_path)
                    filename = webp_filename
                alt = img_elem.get('alt') or (title_elem.text.strip() if title_elem else "")
            
            features.append({
                "filename": filename,
                "alt": alt,
                "title": title_elem.text.strip() if title_elem else "",
                "desc": desc,
                "youtube": None
            })
    
    return features

def get_keywords(soup: BeautifulSoup) -> list:
    """取得關鍵字"""
    keywords = []
    config = FIELD_SELECTORS["keywords"]
    
    for li in soup.select(config["selector"]):
        text = li.text.strip()
        if "regex" in config:
            match = re.search(config["regex"], text)
            if match:
                keywords.append(match.group(1))
        else:
            keywords.append(text)
    
    return keywords

def get_hero_img_by_code(code: str, slug: str) -> str:
    """根據產品代碼和 slug 取得主圖 URL"""
    # 使用 slug 作為產品代碼
    return f"{CSS_BASE}/img/product/_{slug}_mainimg.jpg"

def download_and_save_webp(url, webp_path, max_width=900, quality=85):
    """下載並轉換為 WebP 格式"""
    if os.path.exists(webp_path):
        print(f"  ✔️ 已存在：{webp_path.name}")
        return True
    
    try:
        r = requests.get(url, headers=HDRS, timeout=10)
        r.raise_for_status()
        img = Image.open(BytesIO(r.content))
        
        # 調整尺寸
        if img.width > max_width:
            ratio = max_width / img.width
            new_size = (max_width, int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        # 儲存為 WebP
        os.makedirs(os.path.dirname(webp_path), exist_ok=True)
        img.save(webp_path, 'WEBP', quality=quality)
        print(f"  ✅ 已下載：{webp_path.name}")
        return True
        
    except Exception as e:
        print(f"  × 下載失敗：{url} - {e}")
        return False

def process_images(soup: BeautifulSoup, code: str, slug: str, images_dir_webp: pathlib.Path) -> dict:
    """處理所有圖片"""
    images = {}
    
    # 主圖
    main_config = IMAGE_SELECTORS["main"]
    main_elem = soup.select_one(main_config["selector"])
    if main_elem and main_elem.get("src"):
        main_url = urljoin(BASE, main_elem["src"])
    else:
        # 使用 fallback URL
        main_url = main_config["fallback_url_pattern"].replace("{code}", code)
    
    main_filename = f"uncle-benny-{code}_mainimg.webp"
    main_path = images_dir_webp / main_filename
    download_and_save_webp(main_url, main_path)
    images["main"] = {
        "filename": main_filename,
        "url": None,
        "alt": code,
        "status": "ok"
    }
    
    # Hero 圖
    hero_url = get_hero_img_by_code(code, slug)
    hero_filename = f"uncle-benny-{code}_hero.webp"
    hero_path = images_dir_webp / hero_filename
    download_and_save_webp(hero_url, hero_path)
    images["hero"] = {
        "filename": hero_filename,
        "url": None,
        "alt": code,
        "status": "ok"
    }
    
    # Thema 圖
    thema_config = IMAGE_SELECTORS["thema"]
    thema_elem = soup.select_one(thema_config["selector"])
    thema_alt = ""
    if thema_elem:
        thema_url = urljoin(BASE, thema_elem.get("src", ""))
        thema_alt = thema_elem.get("alt", "")
    else:
        thema_url = thema_config["fallback_url_pattern"].replace("{code}", code)
    
    thema_filename = f"uncle-benny-{code}_thema.webp"
    thema_path = images_dir_webp / thema_filename
    download_and_save_webp(thema_url, thema_path)
    images["thema"] = {
        "filename": thema_filename,
        "url": None,
        "alt": thema_alt,
        "status": "ok"
    }
    
    # Slides
    slides = []
    for idx, slide in enumerate(soup.select(IMAGE_SELECTORS["slides"]["selector"])):
        src = slide.get("src")
        if src:
            slide_url = urljoin(BASE, src)
            orig_name = os.path.splitext(os.path.basename(src))[0]
            slide_filename = f"uncle-benny-{code}_{orig_name}.webp"
            slide_path = images_dir_webp / slide_filename
            download_and_save_webp(slide_url, slide_path)
            slides.append({
                "filename": slide_filename,
                "url": None,
                "alt": slide.get("alt", ""),
                "status": "ok"
            })
    
    images["slides"] = slides
    
    return images

def process_product(url: str, slug: str):
    """處理單個產品頁面"""
    print(f"\n處理產品：{slug} → {url}")
    
    try:
        r = requests.get(url, headers=HDRS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        
        # 取得產品代碼
        code = get_product_code(soup)
        if not code:
            code = slug
        
        # 建立目錄
        prod_dir = OUT / code
        prod_dir.mkdir(parents=True, exist_ok=True)
        images_dir_webp = prod_dir / "images" / "webp"
        images_dir_webp.mkdir(parents=True, exist_ok=True)
        
        # 儲存原始 HTML
        with open(prod_dir / "raw.html", "w", encoding="utf-8") as f:
            f.write(r.text)
        
        # 處理圖片
        images = process_images(soup, code, slug, images_dir_webp)
        
        # 處理 features
        features = get_features(soup, code, images_dir_webp)
        
        # 組合 config
        config = {
            "code": code,
            "name": get_name(soup),
            "brand": get_by_selector(soup, FIELD_SELECTORS["brand"], ""),
            "desc": get_by_selector(soup, FIELD_SELECTORS["desc"], ""),
            "spec": get_spec(soup),
            "wh": get_wh(soup),
            "images": images,
            "features": features,
            "notices": get_by_selector(soup, FIELD_SELECTORS["notices"], []),
            "hashtags": " ".join([f"#{k}" for k in get_keywords(soup)])
        }
        
        # 儲存 config.json
        with open(prod_dir / "config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        print(f"  ✅ 完成：{code}")
        
        # 檢查缺失欄位
        missing = []
        if not config["desc"]: missing.append("desc")
        if not config["spec"]: missing.append("spec")
        if not config["features"]: missing.append("features")
        if not config["hashtags"]: missing.append("hashtags")
        if missing:
            print(f"  ⚠️ 缺少：{', '.join(missing)}")
        
    except Exception as e:
        print(f"  × 處理失敗：{e}")

def main():
    """主程式"""
    print(f"開始爬取 {LIST}")
    
    res = requests.get(LIST, headers=HDRS, timeout=10)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    
    # 找產品連結
    links = soup.select("a[href*='/product/']")
    products = []
    
    for a in links:
        href = a["href"]
        path = urlparse(href).path
        m = re.match(r"^/product/([a-zA-Z0-9-]+)/$", path)
        if m:
            slug = m.group(1).lower()
            url = urljoin(BASE, href)
            products.append((url, slug))
    
    print(f"找到 {len(products)} 個產品頁面")
    
    # 處理每個產品
    for url, slug in products:
        process_product(url, slug)
        time.sleep(0.5)
    
    print(f"\n✅ 完成！共處理 {len(products)} 個產品")

if __name__ == "__main__":
    main()