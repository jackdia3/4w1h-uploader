import os
import json
import time
import argparse
from pathlib import Path
from typing import Any
import openai
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# 設定 OpenAI API
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("請設定 OPENAI_API_KEY 環境變數")

# 基準目錄（專案根目錄）
BASE_DIR = Path(__file__).resolve().parent.parent
PRODUCTS_DIR = BASE_DIR / "products"
CACHE_DIR = BASE_DIR / ".cache"
CACHE_DIR.mkdir(exist_ok=True)

# 確保 products 目錄存在
if not PRODUCTS_DIR.exists():
    print(f"建立 products 目錄：{PRODUCTS_DIR}")
    PRODUCTS_DIR.mkdir(parents=True, exist_ok=True)

NO_TRANSLATE_KEYS = {"code", "brand", "filename", "youtube", "status"}

def get_product_context(data: dict) -> dict:
    """從配置檔中提取產品上下文資訊"""
    return {
        "brand": data.get("brand", "4w1h"),
        "product_name": data.get("name", ""),
        "code": data.get("code", ""),
        "category": "廚房用品",  # 可以根據實際情況調整
        "features": [
            item["text"] for item in data.get("wh", [])
            if item.get("title") in ["What", "Why"]
        ],
        "tone": "自然口語、專業清晰，適合商品介紹用"
    }

def generate_system_prompt(context: dict) -> str:
    """根據產品上下文生成系統提示詞"""
    return (
        f"你是一位擅長日文轉繁體中文的台灣商品文案編輯，熟悉日系廚具、設計品與生活雜貨的語氣與風格，"
        f"請將輸入的日文翻譯為自然流暢、口語親切、適合網路商品頁（如 Shopify）呈現的繁體中文。"
        f"保持原意、避免過度意譯，也不要添加額外說明或評論。\n\n"
        f"本次商品資訊：\n"
        f"- 品牌：{context['brand']}\n"
        f"- 品名：{context['product_name']}\n"
        f"- 型號：{context['code']}\n"
        f"- 類別：{context['category']}\n"
        f"- 特色：\n" + "\n".join(f"  * {feature}" for feature in context['features']) + "\n"
        f"- 語氣：{context['tone']}\n\n"
        f"請依據這些背景翻譯下文。"
    )

def translate_text(text: str, cache: dict, context: dict) -> str:
    """使用 OpenAI API 翻譯文字"""
    # 檢查快取
    if text in cache:
        print(f"使用快取翻譯：{text[:30]}...")
        return cache[text]
    
    # 如果文字太短或不需要翻譯，直接返回
    if not text.strip():
        print(f"跳過翻譯（空白字串）")
        return text
        
    if len(text.strip()) < 2 or text.isdigit():
        print(f"跳過翻譯（太短或數字）：{text[:30]}...")
        return text
    
    print(f"正在翻譯：{text[:30]}...")
    
    try:
        # 呼叫 OpenAI API
        response = openai.chat.completions.create(
            model="gpt-4o",  # 使用更快的 gpt-4o 模型
            messages=[
                {
                    "role": "system",
                    "content": generate_system_prompt(context)
                },
                {
                    "role": "user",
                    "content": f"請將以下日文翻譯成繁體中文：\n{text}"
                }
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        # 檢查回應結構
        if not response.choices:
            raise ValueError("OpenAI API 回傳空選擇")
        
        message = response.choices[0].message.content.strip()
        if not message:
            raise ValueError("OpenAI API 回傳空白內容")
            
        print(f"翻譯結果：{message[:30]}...")
        
        # 儲存到快取
        cache[text] = message
        
        # 避免 API 限制
        time.sleep(0.5)
        
        return message
        
    except Exception as e:
        print(f"❌ 翻譯失敗：{str(e)}")
        return f"[翻譯失敗]{text}"  # 標記失敗的翻譯

def load_cache() -> dict:
    cache_path = CACHE_DIR / "translate_cache.json"
    if cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            cache = json.load(f)
            print(f"已載入 {len(cache)} 筆翻譯快取")
            return cache
    return {}

def save_cache(cache: dict):
    cache_path = CACHE_DIR / "translate_cache.json"
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    print(f"已儲存 {len(cache)} 筆翻譯快取")

def translate_obj(obj: Any, parent_key: str = "", parent_obj: Any = None, key_path: str = "", cache: dict = {}, context: dict = {}) -> Any:
    if isinstance(obj, str):
        # 檢查是否需要翻譯
        print(f"🧪 檢查翻譯條件: key={parent_key}, text={obj[:20]}")
        
        if parent_key in NO_TRANSLATE_KEYS and parent_key != "desc":
            print(f"跳過翻譯（NO_TRANSLATE_KEYS）：{obj[:30]}...")
            return obj
            
        if parent_key == "title" and isinstance(parent_obj, dict) and set(parent_obj.keys()) >= {"title", "text"}:
            print(f"跳過翻譯（title 條件）：{obj[:30]}...")
            return obj
            
        # 執行翻譯
        return translate_text(obj, cache, context)
    elif isinstance(obj, list):
        return [translate_obj(item, parent_key=parent_key, parent_obj=item, key_path=f"{key_path}[{i}]", cache=cache, context=context) for i, item in enumerate(obj)]
    elif isinstance(obj, dict):
        return {k: translate_obj(v, parent_key=k, parent_obj=obj, key_path=f"{key_path}.{k}" if key_path else k, cache=cache, context=context) for k, v in obj.items()}
    else:
        return obj

def batch_translate_configs(clear_cache: bool = False):
    # 根據參數決定是否清除快取
    if clear_cache:
        cache_path = CACHE_DIR / "translate_cache.json"
        if cache_path.exists():
            print("清除舊的快取檔案...")
            cache_path.unlink()
    
    cache = load_cache()
    translated_count = 0
    failed_products = []

    # 檢查 products 目錄是否存在
    if not PRODUCTS_DIR.exists():
        print(f"錯誤：找不到產品目錄 {PRODUCTS_DIR}")
        return

    # 檢查是否有產品配置檔
    config_files = list(PRODUCTS_DIR.glob("**/config.json"))
    if not config_files:
        print(f"警告：在 {PRODUCTS_DIR} 中找不到任何 config.json 檔案")
        return

    print(f"找到 {len(config_files)} 個配置檔")

    for config_path in config_files:
        prod_dir = config_path.parent
        out_path = prod_dir / "config.zh.json"
        
        try:
            print(f"\n處理產品：{prod_dir.name}")
            with open(config_path, encoding="utf-8") as f:
                data = json.load(f)

            # 檢查是否已經翻譯過
            if out_path.exists():
                print(f"⚠️ 已存在翻譯檔：{out_path}")
                continue

            # 取得產品上下文
            context = get_product_context(data)
            print(f"產品上下文：{context['product_name']} ({context['code']})")

            translated = translate_obj(data, cache=cache, context=context)

            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(translated, f, ensure_ascii=False, indent=2)

            print(f"✅ 已翻譯: {prod_dir.name}")
            translated_count += 1
            
        except Exception as e:
            error_msg = f"❌ 處理 {prod_dir.name} 時發生錯誤：{str(e)}"
            print(error_msg)
            failed_products.append(error_msg)
            continue

    # 儲存快取
    save_cache(cache)
    
    # 記錄失敗的產品
    if failed_products:
        failed_path = BASE_DIR / "failed_products.txt"
        with open(failed_path, "w", encoding="utf-8") as f:
            f.write("\n".join(failed_products))
        print(f"\n⚠️ 有 {len(failed_products)} 個產品翻譯失敗，詳情請見：{failed_path}")
    
    print(f"\n🎉 總共翻譯完成 {translated_count} 項商品 config。")

def main():
    parser = argparse.ArgumentParser(description="批次翻譯產品配置檔")
    parser.add_argument("--clear-cache", action="store_true", help="清除翻譯快取")
    args = parser.parse_args()
    
    try:
        batch_translate_configs(clear_cache=args.clear_cache)
    except Exception as e:
        print(f"❌ 執行時發生錯誤：{str(e)}")

if __name__ == "__main__":
    main()
