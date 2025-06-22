import os
import json
import time
import logging
import argparse
import base64
from pathlib import Path
from PIL import Image
from dotenv import load_dotenv
import google.generativeai as genai
import openai

# --- 設定 ---
# 載入 .env 檔案中的環境變數 (例如 .env 檔案在 scripts/ 底下)
load_dotenv(Path(__file__).parent / '.env')

# 配置日誌記錄，同時輸出到控制台和檔案
log_file_path = Path(__file__).parent / 'update_json_with_crops.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file_path, mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

BASE_DIR = Path(__file__).resolve().parent.parent
# 根據 crawl_www.py 的定義，確保路徑一致性
WWW_DIR = BASE_DIR / "products" / "WWW_Collection"

# --- API 金鑰與客戶端初始化 ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    logging.warning("未在 .env 檔案中找到 GOOGLE_API_KEY。")

# OpenAI 客戶端會自動從環境變數讀取金鑰
openai_client = openai.OpenAI() if OPENAI_API_KEY else None
if not OPENAI_API_KEY:
    logging.warning("未在 .env 檔案中找到 OPENAI_API_KEY。")

def batch_images(image_list, batch_size=6):
    """將圖片列表切分為指定大小的批次。"""
    for i in range(0, len(image_list), batch_size):
        yield image_list[i:i + batch_size]

# --- AI 分析函式 ---

# 這是我們給兩個 AI 模型的通用指令
AI_PROMPT_TEMPLATE = """
你是一位頂尖的電商內容策略總監。你的任務是為產品「{product_name}」的一系列特寫圖片，分配一個最符合其內容的『角色』(category)，並提供對應的分析。

請嚴格遵循以下的分類標準：

1.  **`use_case` (使用情境):**
    *   **定義:** 展示產品在特定場景或活動中被使用的圖片。
    *   **範例:** 一雙手套正在夾起滾燙的木炭、或使用者戴著手套在戶外進行精細操作的畫面。
    *   **關鍵:** 圖片需傳達出「正在做某事」的動態感或情境感。

2.  **`selling_point` (產品特點):**
    *   **定義:** 聚焦於產品本身的材質、工藝、設計細節的特寫圖片。
    *   **範例:** 手套上 Logo 或縫線的特寫、展示其皮革紋理的畫面、或其掛勾設計的細節圖。
    *   **關鍵:** 圖片需強調產品「是什麼」或「有什麼特別之處」。

3.  **`spec_image` (規格圖示):**
    *   **定義:** 用於說明尺寸、規格、或組件的圖片。
    *   **範例:** 任何包含尺寸標示線、或以純白為背景展示產品規格表的圖片。
    *   **關鍵:** 圖片的核心目的是傳達數據或客觀資訊。

**分類指令:**
*   請為提供的每一張圖片，都按照以下 JSON 格式，回傳其分類與分析結果。
*   如果圖片中有韓文，請將其翻譯成自然的繁體中文。
*   如果一張圖的內容模糊，無法明確判斷，請基於以上定義，盡力做出最合理的分類，**避免使用 `generic` 或其他未定義的分類**。

{{
  "category": "...",
  "summary": "...",
  "text_blocks": [{{ "type": "...", "content": "..." }}]
}}

最後，將所有圖片的分析結果，打包成一個以**圖片檔名**為鍵 (key) 的單一 JSON 物件回傳。不要包含任何額外的 markdown 語法。
"""

def analyze_batch_with_google(product_name, image_batch):
    """使用 Google Gemini 對一個批次的圖片進行分類與分析。"""
    if not image_batch: return None
    if not GOOGLE_API_KEY:
        logging.error("未設定 GOOGLE_API_KEY，無法使用 Google Gemini。")
        return None

    try:
        logging.info(f"送出新批次至 Google Gemini (共 {len(image_batch)} 張圖)...")
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = AI_PROMPT_TEMPLATE.format(product_name=product_name)
        prompt_parts = [prompt]

        for image_path in image_batch:
            try:
                img = Image.open(image_path)
                prompt_parts.append(f"檔名: {image_path.name}")
                prompt_parts.append(img)
            except Exception as e:
                logging.warning(f"無法讀取圖片 {image_path.name}，已跳過。錯誤: {e}")
                continue
        
        response = model.generate_content(prompt_parts, stream=False)
        response.resolve()
        
        cleaned_text = response.text.strip().lstrip('```json').rstrip('```')
        logging.info(f"Google Gemini 回應內容:\n{cleaned_text}")
        analysis_result = json.loads(cleaned_text)
        
        logging.info(f"Google Gemini 批次分析成功。")
        return analysis_result

    except Exception as e:
        logging.error(f"Google Gemini 批次分析失敗: {e}")
        return None

def encode_image_to_base64(image_path):
    """將圖片檔案編碼為 Base64 字串"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def analyze_batch_with_openai(product_name, image_batch):
    """使用 OpenAI GPT-4V 對一個批次的圖片進行分類與分析。"""
    if not image_batch: return None
    if not openai_client:
        logging.error("未設定 OPENAI_API_KEY，無法使用 OpenAI。")
        return None

    try:
        logging.info(f"送出新批次至 OpenAI GPT-4V (共 {len(image_batch)} 張圖)...")
        
        prompt = AI_PROMPT_TEMPLATE.format(product_name=product_name)
        # OpenAI 的 content 是一個 list，第一個元素是文字 prompt
        content_parts = [{"type": "text", "text": prompt}]

        for image_path in image_batch:
            try:
                base64_image = encode_image_to_base64(image_path)
                # 每個圖片是一個獨立的 dict 元素
                content_parts.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                })
                # 附上檔名讓 AI 知道對應關係
                content_parts.append({"type": "text", "text": f"檔名: {image_path.name}"})
                
            except Exception as e:
                logging.warning(f"無法讀取或編碼圖片 {image_path.name}，已跳過。錯誤: {e}")
                continue
        
        response = openai_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": content_parts}],
            max_tokens=4096 # 增加 token 數量以容納多張圖片的回應
        )

        cleaned_text = response.choices[0].message.content.strip().lstrip('```json').rstrip('```')
        logging.info(f"OpenAI GPT-4V 回應內容:\n{cleaned_text}")
        analysis_result = json.loads(cleaned_text)
        
        logging.info("OpenAI GPT-4V 批次分析成功。")
        return analysis_result
        
    except Exception as e:
        logging.error(f"OpenAI GPT-4V 批次分析失敗: {e}")
        return None


def update_product_json(product_path, model_provider="google"):
    """
    掃描手動裁切的圖片，以「增量更新」的方式，智慧地只分析新的或被遺漏的圖片，
    並將結果補充寫入 analysis.json。
    """
    analysis_path = product_path / "analysis.json"
    images_dir = product_path / "images"

    if not analysis_path.exists() or not images_dir.is_dir():
        logging.warning(f"跳過 {product_path.name}：找不到 analysis.json 或 images 資料夾。")
        return

    try:
        with open(analysis_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        logging.error(f"無法讀取或解析 {analysis_path.name}: {e}")
        return

    product_name = data.get("product_name", "未知產品")
    has_updates = False

    # 1. 掃描現有成果，建立已分析圖片的集合
    analyzed_crops = set()
    for img_info in data.get("images", []):
        # 修正：確保所有裁切圖都有一個紀錄，而不僅僅是已分析的
        parent_name_stem = Path(img_info.get("local_path", "")).stem
        all_disk_crops_for_parent = {p.name for p in images_dir.glob(f"{parent_name_stem}-crop*.jpg")}
        
        # 確保分類列表存在
        for key in ["selling_points", "use_cases", "spec_images", "generic_images"]:
            img_info.setdefault(key, [])
        
        # 收集已分析的檔名
        for category_key in ["selling_points", "use_cases", "spec_images", "generic_images"]:
            for crop_analysis in img_info.get(category_key, []):
                if "local_path" in crop_analysis:
                    analyzed_crops.add(Path(crop_analysis["local_path"]).name)

    # 2. 遍歷每個父圖片，找出未被分析的裁切圖
    for img_info in data.get("images", []):
        parent_local_path = img_info.get("local_path", "")
        if not parent_local_path: continue
        parent_name_stem = Path(parent_local_path).stem
        
        all_disk_crops = {p.name for p in images_dir.glob(f"{parent_name_stem}-crop*.jpg")}
        crops_to_analyze_paths = [images_dir / name for name in sorted(list(all_disk_crops - analyzed_crops))]
        
        if not crops_to_analyze_paths:
            continue  # 這個父圖片的所有裁切圖都已被分析

        logging.info(f"為父圖片 '{parent_name_stem}.jpg' 找到 {len(crops_to_analyze_paths)} 張需要分析的新圖片。")
        has_updates = True
        
        is_first_batch = True
        for batch in batch_images(crops_to_analyze_paths, batch_size=6):
            if not is_first_batch:
                logging.info("等待 10 秒後處理下一批...")
                time.sleep(10)

            if model_provider == "openai":
                batch_result = analyze_batch_with_openai(product_name, batch)
            else:
                batch_result = analyze_batch_with_google(product_name, batch)

            if batch_result:
                for crop_path in batch:
                    result = batch_result.get(crop_path.name)
                    if not result:
                        logging.warning(f"AI 未對 {crop_path.name} 提供分析結果。")
                        continue

                    full_crop_info = {
                        "local_path": f"{product_path.name}/images/{crop_path.name}",
                        "summary": result.get("summary"),
                        "text_blocks": result.get("text_blocks", [])
                    }
                    
                    # 修正：統一分類鍵名 (e.g., selling_point -> selling_points)
                    category = result.get("category", "generic")
                    target_list_name = f"{category}s" if category in ["selling_point", "use_case"] else "spec_images" if category == "spec_image" else "generic_images"
                    
                    img_info.setdefault(target_list_name, []).append(full_crop_info)
            
            is_first_batch = False

    # 3. 如果有任何更新，則在最後將 data 物件完整寫回檔案
    if has_updates:
        try:
            with open(analysis_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logging.info(f"成功將新的分析結果補充寫入 '{analysis_path.name}'")
        except IOError as e:
            logging.error(f"寫入檔案失敗 {analysis_path.name}: {e}")
    else:
        logging.info(f"產品 {product_path.name} 無需更新，所有圖片均已分析。")

def main():
    """主函式，增加命令行參數來選擇 AI 模型"""
    parser = argparse.ArgumentParser(description="使用 AI 分析商品圖片並更新 JSON 檔案。")
    parser.add_argument(
        '--model', 
        type=str, 
        choices=['google', 'openai'], 
        default='google', 
        help='選擇使用的 AI 模型供應商 (預設: google)'
    )
    args = parser.parse_args()
    
    if not WWW_DIR.is_dir():
        logging.error(f"錯誤：找不到目標資料夾 '{WWW_DIR}'")
        return

    logging.info(f"--- 開始使用 {args.model.upper()} 進行敘事設計與分類 (批次模式) ---")
    for product_path in sorted(WWW_DIR.glob('product_*')):
        if product_path.is_dir():
            logging.info(f"處理產品：{product_path.name}")
            update_product_json(product_path, model_provider=args.model)
    
    logging.info("✅ 處理完畢。")

if __name__ == "__main__":
    main() 