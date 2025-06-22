#!/usr/bin/env python3
"""
極簡 4w1h 商品爬蟲：
1. 讀 https://4w1h.jp/product/
2. 取得所有商品連結（只抓 /product/<slug>/ 格式）
3. 依產品型號（code）建資料夾，若抓不到則用 slug
4. 抓取產品型號、名稱、主圖、規格表、4W1H 區塊，存成 config.json
"""
import json, os, re, time, unicodedata, pathlib
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from PIL import Image
from io import BytesIO

# 新增：讀取 selector 設定檔
SELECTOR_PATH = pathlib.Path(__file__).parent / "image_selectors.json"
with open(SELECTOR_PATH, encoding="utf-8") as f:
    IMAGE_SELECTORS = json.load(f)["4w1h"]

BASE   = "https://4w1h.jp"
LIST   = f"{BASE}/product/"
CSS_BASE = "https://4w1h.jp/wp-content/themes/4w1h_v1.3"

HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}
OUT  = pathlib.Path(__file__).resolve().parents[1] / "products"
OUT.mkdir(exist_ok=True)

def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", text)

def get_product_code(soup: BeautifulSoup) -> str:
    # 嘗試從產品頁抓取型號，例如 <span class="code">...</span>
    code_elem = soup.select_one(".code")
    if code_elem:
        return code_elem.text.strip()
    return ""

def get_name(soup):
    """取得商品名稱"""
    # 從 title 標籤中取得商品名稱
    title = soup.find("title").text
    # 以 | 分隔，取第一個部分
    name = title.split("|")[0].strip()
    return name

def get_hero_img_by_code(code: str) -> str:
    # 直接組合主圖路徑
    return f"{CSS_BASE}/img/product/_{code}_mainimg.jpg"

def get_thema_img_by_code(code: str) -> str:
    # 直接組合主題圖路徑
    return f"{CSS_BASE}/img/product/_{code}_thema.png"

def get_spec(soup: BeautifulSoup) -> list:
    # 先找 class 含 spec 的 table
    spec_tbl = soup.select_one('table.spec, table[class*=spec]')
    # 排除 #wh 區塊內的 table
    if not spec_tbl:
        tables = soup.find_all('table')
        wh = soup.select_one('#wh')
        wh_tables = wh.find_all('table') if wh else []
        wh_tables_set = set(wh_tables)
        # 選擇不在 #wh 區塊內的最後一個 table
        non_wh_tables = [t for t in tables if t not in wh_tables_set]
        if non_wh_tables:
            spec_tbl = non_wh_tables[-1]
    spec = []
    if spec_tbl:
        for tr in spec_tbl.select('tr'):
            th = tr.select_one('th')
            td = tr.select_one('td')
            if th and td:
                spec.append({"label": th.text.strip(), "value": td.text.strip()})
    return spec

# 4W1H 標題圖對應
WH_IMG_MAP = {
    "When": "4w1h-ttl-when.png",
    "Who": "4w1h-ttl-who.png",
    "What": "4w1h-ttl-what.png",
    "Why": "4w1h-ttl-why.png",
    "How": "4w1h-ttl-how.png"
}

def get_wh(soup: BeautifulSoup) -> list:
    wh_items = []
    wh_elem = soup.select_one("#wh")
    wh_titles = ["When", "Who", "What", "Why", "How"]
    wh_title_idx = 0
    if wh_elem:
        table = wh_elem.select_one("table")
        if table:
            trs = table.select("tr")
            idx = 0
            while idx < len(trs):
                th = trs[idx].select_one("th")
                td = trs[idx].select_one("td")
                title = ""
                text = ""
                if th:
                    img = th.select_one("img[alt]")
                    title = img["alt"].strip() if img and img.has_attr("alt") else th.get_text(strip=True)
                if td:
                    text = td.get_text(strip=True)
                    rowspan = td.get("rowspan")
                    if rowspan == "2":
                        t1 = title or (wh_titles[wh_title_idx] if wh_title_idx < len(wh_titles) else "")
                        wh_items.append({"title": t1, "text": text})
                        wh_title_idx += 1
                        if idx + 1 < len(trs):
                            th2 = trs[idx+1].select_one("th")
                            title2 = ""
                            if th2:
                                img2 = th2.select_one("img[alt]")
                                title2 = img2["alt"].strip() if img2 and img2.has_attr("alt") else th2.get_text(strip=True)
                            t2 = title2 or (wh_titles[wh_title_idx] if wh_title_idx < len(wh_titles) else "")
                            wh_items.append({"title": t2, "text": text})
                            wh_title_idx += 1
                        idx += 2
                        continue
                t = title or (wh_titles[wh_title_idx] if wh_title_idx < len(wh_titles) else "")
                if t or text:
                    wh_items.append({"title": t, "text": text})
                    wh_title_idx += 1
                idx += 1
        how = wh_elem.select_one("p.how")
        if how:
            icon_img = how.select_one("i img")
            title = icon_img["alt"].strip() if icon_img and icon_img.has_attr("alt") else "How"
            text = how.select_one("span.text").get_text(strip=True) if how.select_one("span.text") else ""
            t = title or (wh_titles[wh_title_idx] if wh_title_idx < len(wh_titles) else "How")
            wh_items.append({"title": t, "text": text})
    if not wh_items:
        wh_elem = soup.select_one("#wh") or soup.select_one("ul")
        if wh_elem:
            for li in wh_elem.select("li"):
                title = li.select_one("strong, b, h3, h4")
                t = title.text.strip() if title else (wh_titles[wh_title_idx] if wh_title_idx < len(wh_titles) else "")
                wh_items.append({"title": t, "text": li.text.strip()})
                wh_title_idx += 1
    return wh_items

def get_product_brand(soup: BeautifulSoup) -> str:
    # 品牌名稱，預設寫死
    return "燕三条キッチン研究所"

def get_product_desc(soup: BeautifulSoup) -> str:
    # 嘗試抓取產品理念或一句話特色
    desc_elem = soup.select_one(".top_text") or soup.select_one(".txt-wrap")
    if desc_elem:
        return desc_elem.text.strip()
    return ""

def get_product_intro(soup: BeautifulSoup) -> str:
    # 嘗試抓取產品介紹文字
    intro_elem = soup.select_one('.product_intro') or soup.select_one('.intro_text')
    if intro_elem:
        return intro_elem.text.strip()
    return ""

def get_notices(soup: BeautifulSoup) -> list:
    # 嘗試抓取注意事項區塊
    notices = []
    notice_elem = soup.select_one('.notice') or soup.select_one('.notices')
    if notice_elem:
        for li in notice_elem.select('li'):
            notices.append(li.text.strip())
    return notices

def get_images_with_alt(soup, selector: str, key: str) -> list:
    imgs = soup.select(selector)
    seen_src = set()
    img_list = []
    for img in imgs:
        src = img.get("src")
        if not src or src in seen_src:
            continue
        seen_src.add(src)
        img_url = urljoin(BASE, src)
        fname = os.path.basename(urlparse(img_url).path)
        alt = img.get("alt") or key or fname
        img_list.append({
            "filename": fname,
            "url": img_url,
            "alt": alt,
            "status": "ok"
        })
    return img_list

def get_features(soup: BeautifulSoup, images_info, code, images_dir_webp) -> list:
    features = []
    for block in soup.select('#feature .flex > div'):
        # 先判斷有沒有 iframe（YouTube）
        iframe = block.select_one('iframe')
        title_elem = block.select_one('div.text > h4')
        desc_list = [p.text.strip() for p in block.select('div.text > p')]
        desc = '<br>'.join(desc_list)
        if iframe:
            youtube = iframe.get('src')
            features.append({
                "filename": None,
                "alt": "",
                "title": title_elem.text.strip() if title_elem else "",
                "desc": desc,
                "youtube": youtube
            })
        else:
            img = block.select_one('figure img')
            filename = None
            if img:
                src_url = img.get('src')
                if src_url:
                    orig_name = os.path.splitext(os.path.basename(src_url))[0]
                    webp_filename = f"uncle-benny-{code}_{orig_name}.webp"
                    webp_path = images_dir_webp / webp_filename

                    if webp_path.exists():
                        print(f"[feature exists] {webp_filename} 已存在，跳過下載。")
                    else:
                        ok = download_and_save_webp(src_url, webp_path)
                        print(f"[features fallback] src={src_url} → {webp_filename} (ok={ok})")

                    filename = webp_filename
                alt = img.get('alt') or (title_elem.text.strip() if title_elem else "")
                features.append({
                    "filename": filename,
                    "alt": alt,
                    "title": title_elem.text.strip() if title_elem else "",
                    "desc": desc,
                    "youtube": None
                })
    return features

def get_slides(soup: BeautifulSoup) -> list:
    slides = []
    for img in soup.select('#slides img, .slides img, .slide img'):
        slides.append({
            "img": img.get('src'),
            "alt": img.get('alt', '')
        })
    return slides

def get_keywords(soup: BeautifulSoup) -> list:
    return [li.text.strip() for li in soup.select('#tags li')]

def download_and_save_webp(url, webp_path, max_width=900, quality=85):
    if os.path.exists(webp_path):
        print(f"  ✔️ 本地已存在：{webp_path.name}，略過下載")
        return True
    try:
        r = requests.get(url, headers=HDRS, timeout=10)
        r.raise_for_status()
        img = Image.open(BytesIO(r.content))
        if img.width > max_width:
            ratio = max_width / img.width
            new_size = (max_width, int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        os.makedirs(os.path.dirname(webp_path), exist_ok=True)
        img.save(webp_path, 'WEBP', quality=quality)
        print(f"  ✅ 成功下載並儲存：{webp_path.name}")
        return True
    except Exception as e:
        print(f"  × 下載失敗：{url}，且本地不存在此圖。錯誤訊息：{e}")
        return False

def normalize_filename(code, usage, idx=None):
    prefix = f"uncle-benny-{code}_{usage}"
    if idx is not None:
        prefix += f"_{idx:02d}"
    return f"{prefix}.webp"

def get_and_save_images(soup, code, images_dir_webp):
    images_info = {"hero": [], "gallery": []}
    
    # 遍歷所有圖片選擇器
    for key, selector in IMAGE_SELECTORS.items():
        imgs = get_images_with_alt(soup, selector, key)
        for img_data in imgs:
            img_url = img_data["url"]
            # 產生標準化的 webp 檔名
            base_fname = os.path.splitext(img_data["filename"])[0]
            webp_filename = f"uncle-benny-{code}__{base_fname}.webp"
            webp_path = images_dir_webp / webp_filename

            if webp_path.exists():
                print(f"[{key} exists] {webp_filename} 已存在，跳過下載。")
                ok = True
            else:
                ok = download_and_save_webp(img_url, webp_path)

            if ok:
                images_info.setdefault(key, []).append({
                    "filename": webp_filename,
                    "alt": img_data["alt"]
                })
    return images_info

def main():
    print(f"正在讀取 {LIST}")
    res = requests.get(LIST, headers=HDRS, timeout=10)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    print(f"頁面標題: {soup.title.text if soup.title else '無標題'}")

    # 嘗試不同的選擇器
    cards = soup.select(".p-list__item a")
    if not cards:
        print("嘗試其他選擇器...")
        cards = soup.select(".product-list a")
    if not cards:
        cards = soup.select("article a")
    if not cards:
        cards = soup.select("a[href*='/product/']")

    print(f"共抓到 {len(cards)} 個連結（含分類頁）")
    if not cards:
        print("HTML 結構：")
        print(soup.prettify()[:1000])
        return

    count = 0
    for a in cards:
        href = a["href"]
        path = urlparse(href).path
        m = re.match(r"^/product/([a-zA-Z0-9-]+)/$", path)
        if not m:
            continue  # 跳過 /product/（分類頁）或其他非產品頁
        slug = m.group(1).lower()
        url = urljoin(BASE, href)
        print(f"下載 {slug} → {url}")
        try:
            r = requests.get(url, headers=HDRS, timeout=10)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            code = get_product_code(soup)
            if not code:
                code = slug
            prod_dir = OUT / code
            prod_dir.mkdir(parents=True, exist_ok=True)
            with open(prod_dir / "raw.html", "w", encoding="utf-8") as f:
                f.write(r.text)
            # 新增：分類抓圖（自動補 alt）
            images_dir_webp = prod_dir / "images" / "webp"
            images_info = get_and_save_images(soup, code, images_dir_webp)

            # 主圖自動下載與 webp 儲存
            main_img_url = get_hero_img_by_code(code)
            main_img_filename = f"uncle-benny-{code}_mainimg.webp"
            main_img_webp_path = images_dir_webp / main_img_filename
            ok = download_and_save_webp(main_img_url, main_img_webp_path)
            main_img = {"filename": main_img_filename, "url": None, "alt": code, "status": "ok" if ok else "error"}

            # 主題圖自動下載與 webp 儲存
            thema_img_url = get_thema_img_by_code(code)
            thema_img_filename = f"uncle-benny-{code}__{code}_thema.webp"
            thema_img_webp_path = images_dir_webp / thema_img_filename
            thema_ok = download_and_save_webp(thema_img_url, thema_img_webp_path)
            thema_img = {"filename": thema_img_filename, "url": None, "alt": code, "status": "ok" if thema_ok else "error"}

            slides = images_info.get("slides", [])
            if isinstance(slides, dict):
                slides = [slides]
            notice_img = images_info.get("notice_img")

            # features/slides 統一格式
            features = get_features(soup, images_info, code, images_dir_webp)

            # hashtags
            keywords = get_keywords(soup)
            hashtags = " ".join([f"#{k}" for k in keywords])

            # thema 區塊
            thema = {
                "img": thema_img["filename"] if thema_img else "",
                "text": ""  # 可根據實際需求補抓主題說明
            }

            # 缺漏檢查
            missing = []
            if not ok:
                missing.append("主圖下載失敗")
            if not thema_ok:
                missing.append("thema下載失敗")
            if not features:
                missing.append("features")
            if not slides:
                missing.append("slides")
            if not keywords:
                missing.append("hashtags")
            notices = get_notices(soup)
            if not notices:
                missing.append("notices")
            spec = get_spec(soup)
            if not spec:
                missing.append("spec")
            if missing:
                print(f"  ⚠️ 缺少：{', '.join(missing)}")
            else:
                print("  ✅ 資料完整")

            config = {
                "images": {
                    "hero": main_img,
                    "logo": {"filename": "4W1H_logo.png", "alt": "4W1H 品牌標誌"},
                    "divider": {"filename": "4w1h-divider.png", "alt": ""},
                    "thema": thema_img,
                    "slides": slides,
                    "notice": notice_img
                },
                "intro_paragraphs": [p.strip() for p in get_product_desc(soup).split('\n') if p.strip()],
                "product_intro": get_product_intro(soup),
                "wh_items": [{"title_img": {"filename": f"4w1h-ttl-{item['title'].lower()}.png", "alt": item['title']}, "description": item['text']} for item in get_wh(soup)],
                "youtube_video": {
                    "title": "YouTube 產品介紹影片",
                    "embed_url": next((f['youtube'] for f in features if f.get('youtube')), None)
                },
                "features": [{
                    "image": {
                        "filename": f['filename'],
                        "alt": f['alt']
                    },
                    "title": f['title'],
                    "description": f['desc']
                } for f in features if f.get('filename')],
                "hashtags": [tag.strip('#') for tag in hashtags.split()],
                "spec": {item['label']: item['value'] for item in spec},
                "notices": get_notices(soup)
            }
            with open(prod_dir / "config.json", "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            count += 1
            time.sleep(0.5)
        except Exception as e:
            print(f"  × 下載失敗：{url} - {e}")
    print(f"實際下載 {count} 個產品頁。")

if __name__ == "__main__":
    main() 