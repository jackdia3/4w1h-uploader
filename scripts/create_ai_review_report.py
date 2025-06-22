import os
import json
import logging
from pathlib import Path
from PIL import Image
import google.generativeai as genai
import base64
from io import BytesIO

# --- 設定 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TARGET_PRODUCT_ID = "product_956"  # 指定要審查的產品
WWW_DIR = PROJECT_ROOT / "products" / "WWW_Collection"
PRODUCT_PATH = WWW_DIR / TARGET_PRODUCT_ID
REPORT_FILE = PROJECT_ROOT / "scripts" / f"ai_review_report_{TARGET_PRODUCT_ID}.md"

try:
    from config import GOOGLE_API_KEY
except ImportError:
    GOOGLE_API_KEY = "YOUR_GOOGLE_API_KEY" # Fallback

genai.configure(api_key=GOOGLE_API_KEY)


def image_to_base64(image_path, size=(200, 200)):
    """將圖片轉換為 Base64 字串以便在 Markdown 中顯示"""
    try:
        img = Image.open(image_path)
        img.thumbnail(size)
        buffered = BytesIO()
        img.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode()
    except Exception:
        return None

def analyze_single_image_with_ai(product_name, image_path):
    """對單張圖片進行詳細分析，獲取其分類、摘要與文字區塊。"""
    try:
        logging.info(f"正在分析圖片：{image_path.name}")
        model = genai.GenerativeModel('gemini-1.5-flash')
        img = Image.open(image_path)
        
        prompt = f"""
        你是一位頂尖的電商內容策略總監。我會提供給你一個產品「{product_name}」的一張特寫圖片。你的任務是為這張圖片，分配一個最符合其內容的『角色』(category)，並提供對應的分析。

        圖片角色分類如下:
        *   `selling_point`: 強調產品核心功能、設計細節、材質工藝、或特殊設計（如掛勾、標籤）的圖片。
        *   `use_case`: 展示產品在實際情境中如何被使用的圖片，即使只有產品本身，但若能看出特定動作或用途（如抓握、防火）亦可歸類於此。
        *   `spec_image`: 主要用於說明尺寸、規格或組件的圖片。

        如果圖片無法明確歸入以上三類，請優先考慮歸類為 `selling_point`。避免使用 `generic`。

        請為這張圖片，嚴格按照以下 JSON 格式回傳單一一個分析結果。如果圖片中有韓文，請將其翻譯成自然的繁體中文。

        {{
          "category": "...",
          "summary": "...",
          "text_blocks": [{{ "type": "...", "content": "..." }}]
        }}
        """
        
        response = model.generate_content([prompt, f"檔名: {image_path.name}", img])
        response.resolve()
        
        cleaned_text = response.text.strip().lstrip('```json').rstrip('```')
        return json.loads(cleaned_text)

    except Exception as e:
        logging.error(f"分析圖片 {image_path.name} 失敗: {e}")
        return None

def create_review_report():
    """為指定產品的所有裁切圖生成一份 AI 分析審查報告。"""
    if not PRODUCT_PATH.is_dir():
        logging.error(f"找不到產品資料夾：{PRODUCT_PATH}")
        return

    # 從 analysis.json 讀取產品名稱
    analysis_path = PRODUCT_PATH / "analysis.json"
    product_name = "未知產品"
    if analysis_path.exists():
        with open(analysis_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            product_name = data.get("product_name", product_name)

    # 找到所有裁切圖
    images_dir = PRODUCT_PATH / "images"
    crop_images = sorted(images_dir.glob('*-crop*.jpg'))

    if not crop_images:
        logging.warning(f"在 {images_dir} 中找不到任何裁切圖。")
        return

    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write(f"# AI 圖片分析審查報告：{product_name} ({TARGET_PRODUCT_ID})\n\n")
        f.write("此報告旨在檢視 AI 對每張裁切圖的分類、摘要及文字識別結果，以便優化 Prompt。\n\n")
        f.write("---\n\n")

        for img_path in crop_images:
            analysis = analyze_single_image_with_ai(product_name, img_path)
            base64_img = image_to_base64(img_path)

            f.write(f"## 檔案：`{img_path.name}`\n\n")
            
            if base64_img:
                f.write(f"![{img_path.name}](data:image/jpeg;base64,{base64_img})\n\n")

            if analysis:
                f.write(f"**AI 分類結果：**\n\n")
                f.write(f"```json\n{json.dumps(analysis, ensure_ascii=False, indent=2)}\n```\n\n")
            else:
                f.write("**AI 分析失敗**\n\n")
            
            f.write("---\n\n")

    logging.info(f"✅ 分析報告已生成：{REPORT_FILE}")

if __name__ == "__main__":
    create_review_report() 