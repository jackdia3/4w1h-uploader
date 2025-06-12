import json
import pathlib
import os
import re
import sys

# 支援命令列參數指定商品資料夾與語系
if len(sys.argv) > 1:
    prod_code = sys.argv[1]
else:
    prod_code = "flyer"  # 預設
lang = None
if len(sys.argv) > 2:
    lang = sys.argv[2].lower()

BASE = pathlib.Path(__file__).resolve().parents[1]
PROD = BASE / "products" / prod_code
CONFIG_PATH = PROD / "config.json"
CONFIG_ZH_PATH = PROD / "config.zh.json"
TEMPLATE = pathlib.Path(__file__).parent / "index.html"
OUTPUT = PROD / "index.html"

# 決定要用哪個 config
if lang == "zh":
    config_file = CONFIG_ZH_PATH if CONFIG_ZH_PATH.exists() else CONFIG_PATH
else:
    config_file = CONFIG_ZH_PATH if CONFIG_ZH_PATH.exists() else CONFIG_PATH

CDN_BASE_URL = "https://cdn.shopify.com/s/files/1/0633/7511/4460/files/"
CDN_VERSION = "v=1749379651"  # Shopify CDN 版本號

# 4W1H 標題圖對應
WH_IMG_MAP = {
    "When": "4w1h-ttl-when.png",
    "Who": "4w1h-ttl-who.png",
    "What": "4w1h-ttl-what.png",
    "Why": "4w1h-ttl-why.png",
    "How": "4w1h-ttl-how.png"
}

# 預設注意事項（繁體中文）
DEFAULT_NOTICES = [
    "原廠授權公司貨，請放心選購。",
    "鑑賞期非試用期，經拆封使用過後無提供退換貨服務。",
    "商品顏色會因拍照光線環境或螢幕色差等因素有所差異，依實際出貨為準。",
    "商品細節如有疑問，歡迎聯繫客服。"
]

def to_cdn_url(filename_or_obj):
    if not filename_or_obj:
        return ""
    if isinstance(filename_or_obj, dict):
        filename = filename_or_obj.get("filename")
        return f"{CDN_BASE_URL}{filename}?{CDN_VERSION}" if filename else ""
    elif isinstance(filename_or_obj, str):
        return f"{CDN_BASE_URL}{filename_or_obj}?{CDN_VERSION}"
    return ""

def format_text(text):
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    paragraphs = text.split('。')
    paragraphs = [p.strip() + '。' for p in paragraphs if p.strip()]
    return '<br>'.join(paragraphs)

def generate_features_html(features):
    if not features:
        return ""
    html = ""
    for feat in features:
        html += '<div class="feature-block">\n'
        if feat.get("youtube"):
            html += f'    <div class="youtube">\n'
            html += f'        <iframe title="YouTube 產品介紹影片" src="{feat.get("youtube")}" allowfullscreen></iframe>\n'
            html += f'    </div>\n'
        if feat.get("filename"):
            html += f'    <img src="{to_cdn_url(feat.get("filename"))}" alt="{feat.get("alt", feat.get("title", ""))}" class="full-img">\n'
        html += f'    <div class="main-text">\n'
        html += f'        <p class="p1"><u>{feat.get("title", "")}</u><br>{feat.get("desc", "")}</p>\n'
        html += f'    </div>\n'
        html += '</div>\n'
    return html

def generate_wh_html(wh_items):
    if not wh_items:
        return ""
    html = '<div class="wh-block" style="text-align: center">\n'
    for item in wh_items:
        html += f'    <div class="wh-item">\n'
        html += f'        <img src="{item.get("img", "")}" alt="{item.get("alt", "")}">\n'
        html += f'        <div class="main-text">\n'
        html += f'            <p class="p1">{item.get("text", "")}</p>\n'
        html += f'        </div>\n'
        html += f'    </div>\n'
    html += '</div>'
    return html

def generate_spec_html(spec):
    if not spec:
        return ""
    html = '<table class="spec">\n'
    html += '    <tbody>\n'
    for key, value in spec.items():
        html += f'        <tr>\n'
        html += f'            <th>{key}</th>\n'
        html += f'            <td>{value}</td>\n'
        html += f'        </tr>\n'
    html += '    </tbody>\n'
    html += '</table>'
    return html

def generate_notices_html(notices):
    if not notices:
        return ""
    html = ""
    for notice in notices:
        html += f'<li style="text-align: left">{notice}</li>\n'
    return html

def generate_slides_html(slides):
    if not slides:
        return ""
    html = '<div class="feature-block">\n'
    for slide in slides:
        html += f'    <figure>\n'
        html += f'        <img src="{to_cdn_url(slide.get("filename", ""))}" class="full-img" alt="{slide.get("alt", "")}">\n'
        html += f'    </figure>\n'
    html += '</div>'
    return html

def generate_hashtags_html(hashtags):
    if not hashtags:
        return ""
    return f'<p>{hashtags}</p>'

def generate_notice_img_html(notice_img):
    if not notice_img:
        return ""
    return f'<p><img style="float: left" src="{to_cdn_url(notice_img.get("filename", ""))}" class="full-img" alt="{notice_img.get("alt", "")}"></p>'

def generate_html(config):
    with open("index.html", "r", encoding="utf-8") as f:
        template = f.read()

    # 讀取 config.json
    with open(config, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 產生各區塊 HTML
    wh_html = generate_wh_html(data.get("wh", []))
    features_html = generate_features_html(data.get("features", []))
    slides_html = generate_slides_html(data.get("slides", []))
    hashtags_html = generate_hashtags_html(data.get("hashtags", ""))
    spec_html = generate_spec_html(data.get("spec", {}))
    notices_html = generate_notices_html(data.get("notices", []))
    notice_img_html = generate_notice_img_html(data.get("notice_img", {}))

    # 替換模板中的變數
    html = template.replace("{{wh}}", wh_html)
    html = html.replace("{{features}}", features_html)
    html = html.replace("{{slides}}", slides_html)
    html = html.replace("{{hashtags}}", hashtags_html)
    html = html.replace("{{spec}}", spec_html)
    html = html.replace("{{notices}}", notices_html)
    html = html.replace("{{notice_img}}", notice_img_html)
    html = html.replace("{{hero_img}}", to_cdn_url(data.get("hero_img", "")))
    html = html.replace("{{hero_alt}}", data.get("hero_alt", ""))
    html = html.replace("{{thema_img}}", to_cdn_url(data.get("thema_img", "")))
    html = html.replace("{{thema_text}}", data.get("thema_text", ""))
    html = html.replace("{{title}}", data.get("title", ""))
    html = html.replace("{{meta_description}}", data.get("meta_description", ""))

    # 寫入輸出檔案
    output_file = os.path.join("products", data.get("product_id", ""), "index.html")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    generate_html("config.json") 