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
    filename = Path(local_path).name
    return f"{CDN_BASE_URL}{filename}"

def extract_render_context(raw_data):
    """
    Extracts and structures all necessary data for rendering from the
    rebuilt, nested analysis.json.
    """
    all_images_source = raw_data.get('images', [])
    
    hero_image = None
    main_description_image = None
    
    # First pass: identify and separate special images
    for img in all_images_source:
        if img.get('is_main'):
            hero_image = img
        if img.get('is_main_description'):
            main_description_image = img

    # Filter out special images from the main processing list to avoid duplicates
    all_images = [
        img for img in all_images_source 
        if not img.get('is_main') and not img.get('is_main_description')
    ]

    all_selling_points = []
    all_use_cases = []
    all_spec_images = []

    # Aggregate all categorized images from the remaining parent images
    for img_info in all_images:
        all_selling_points.extend(img_info.get('selling_points', []))
        all_use_cases.extend(img_info.get('use_cases', []))
        all_spec_images.extend(img_info.get('spec_images', []))

    # Prepare the final context for the template
    context = {
        'product_name': raw_data.get('product_name', ''),
        'title': raw_data.get('title', ''),
        'meta_description': raw_data.get('meta_description', ''),
        'hero_image': hero_image,
        'main_description_image': main_description_image,
        'selling_points': all_selling_points,
        'use_cases': all_use_cases,
        'spec_images': all_spec_images,
        'specs': raw_data.get('specs', []),
        'to_cdn': to_cdn
    }
    return context

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
        'main_description_image': page_context['main_description_image'],
        'selling_points': page_context['selling_points'],
        'use_cases': page_context['use_cases'],
        'spec_images': page_context['spec_images'],
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