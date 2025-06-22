import os
import json
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path

# --- Custom Filters ---
def nl2br(value):
    """Converts newlines in a string to HTML line breaks."""
    if isinstance(value, str):
        return value.replace('\n', '<br>\n')
    return value

# --- Constants and Configuration ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASE_DIR = PROJECT_ROOT / 'products' / 'WWW_Collection'
TEMPLATE_NAME = 'index_template_std.html.jinja'
CDN_BASE_URL = "https://cdn.shopify.com/s/files/1/0633/7511/4460/files/"
BRAND_NAME = "WILDWILDWEST"
LOGO_URL = "https://cdn.shopify.com/s/files/1/0633/7511/4460/files/wildwildwest_logo.jpg?v=1750422561"

# --- Content Blocks ---
NOTICE_TEXT = [
    "注意事項",
    "原廠授權公司貨，請放心選購。",
    "鑑賞期非試用期，經拆封使用過後無提供退換貨服務。",
    "金屬製品在製作過程中難免會產生加工痕跡，此為正常現象，不在瑕疵範圍內。",
    "商品顏色會因拍照光線環境或手機螢幕色差等因素有所差異，依實際出貨為準。",
    "本頁面的圖片及文字的所有權歸韓國原廠WILDWILDWEST所有，Uncle Benny取得授權使用，嚴禁未經授權擅自使用、修改、轉載，如未經協議而使用，將依法承擔法律責任。"
]

# --- Helper Functions ---
def to_cdn(local_path):
    """Converts a local file path to its CDN URL."""
    if not local_path:
        return ""
    return f"{CDN_BASE_URL}{Path(local_path).name}"

def extract_render_context(raw_data):
    """
    Extracts and structures all necessary data for rendering directly from the
    AI-processed analysis.json.
    """
    hero_image = None
    selling_points = []
    use_cases = []
    spec_images = []
    generic_images = []

    # Find the main hero image and collect all categorized images
    for img_info in raw_data.get('images', []):
        # The hero image is the one that contains the categorized lists
        if any(key in img_info for key in ['selling_points', 'use_cases', 'spec_images']):
            hero_image = img_info
            selling_points.extend(img_info.get('selling_points', []))
            use_cases.extend(img_info.get('use_cases', []))
            spec_images.extend(img_info.get('spec_images', []))
            generic_images.extend(img_info.get('generic_images', []))

    # Determine intro text: use summary from the first selling point, then remove it
    intro_text = ""
    if selling_points and selling_points[0].get('summary'):
        intro_text = selling_points.pop(0).get('summary')
    elif use_cases and use_cases[0].get('summary'):
        intro_text = use_cases.pop(0).get('summary')

    return {
        'hero_image': hero_image,
        'selling_points': selling_points,
        'use_cases': use_cases,
        'spec_images': spec_images,
        'generic_images': generic_images,
        'intro_text': intro_text,
    }

def process_product(prod_path, template):
    """Loads data for a single product and renders its HTML page."""
    raw_path = prod_path / 'analysis.json'

    if not raw_path.exists():
        return

    with open(raw_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)

    page_context = extract_render_context(raw_data)

    # Clean up specs list if it's nested
    raw_specs = raw_data.get('specs', [])
    if raw_specs and isinstance(raw_specs[0], list):
        raw_specs = raw_specs[0]

    render_data = {
        'product_name': raw_data.get('product_name', ''),
        'meta_description': raw_data.get('meta_description', ''),
        'brand_name': BRAND_NAME,
        'logo_url': LOGO_URL,
        'specs': raw_specs,
        'hero_image': page_context['hero_image'],
        'selling_points': page_context['selling_points'],
        'use_cases': page_context['use_cases'],
        'spec_images': page_context['spec_images'],
        'intro_text': page_context['intro_text'],
        'notices': NOTICE_TEXT[1:] # Pass notices without the title
    }
    
    html_content = template.render(**render_data)
    out_path = prod_path / 'index.html'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

def main():
    """Main function to generate all product pages."""
    env = Environment(
        loader=FileSystemLoader(PROJECT_ROOT),
        autoescape=select_autoescape(['html', 'xml'])
    )
    env.filters['nl2br'] = nl2br
    env.globals['to_cdn'] = to_cdn
    template = env.get_template(TEMPLATE_NAME)
    
    print(f"--- Generating HTML from new structure in '{BASE_DIR}' ---")
    
    # 手動指定要處理的產品，以繞過檔案系統枚舉問題
    # product_dir_names = ['product_321', 'product_383', 'product_516', 'product_630', 'product_907_fixed', 'product_956', 'product_974']
    product_dir_names = ['product_956', 'product_974']


    if not product_dir_names:
        print(f"Warning: No product directories specified in the script.")
        return

    for prod_name in sorted(product_dir_names):
        prod_path = BASE_DIR / prod_name
        if not prod_path.is_dir():
            print(f"Warning: Directory '{prod_path}' not found, skipping.")
            continue
        print(f"Processing: {prod_path.name}")
        process_product(prod_path, template)
    
    print("\n✅ Generation complete.")

if __name__ == '__main__':
    main() 