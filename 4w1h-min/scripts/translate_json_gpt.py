import os
import sys
import json
import openai
import time
from typing import Any
from termcolor import colored

# 讀取 API KEY
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("請設定 OPENAI_API_KEY 環境變數")
    sys.exit(1)
openai.api_key = OPENAI_API_KEY

# 翻譯函數
SYSTEM_PROMPT = "你是一個專業的日文到繁體中文翻譯，請將輸入的日文翻譯成自然流暢的繁體中文。如果內容不是日文，請原樣回傳。只回傳翻譯後的內容，不要加註解。"

# 不翻譯的 key 名單
NO_TRANSLATE_KEYS = {"code", "brand", "filename", "youtube", "status"}

# 精美 log 輸出
def log_translate(key_path, src, tgt):
    print(colored(f"[翻譯] {key_path}", "cyan"))
    print(colored(f"  原文: {src}", "yellow"))
    print(colored(f"  翻譯: {tgt}", "green"))
    print("-" * 40)

# 遞迴翻譯，支援 wh.title 不翻譯

def translate_obj(obj: Any, parent_key: str = "", parent_obj: Any = None, key_path: str = "") -> Any:
    if isinstance(obj, str):
        # wh 區塊的 title 不翻譯
        if parent_key == "title" and isinstance(parent_obj, dict) and set(parent_obj.keys()) >= {"title", "text"}:
            return obj
        # 其他不翻譯 key
        if parent_key in NO_TRANSLATE_KEYS and parent_key != "desc":
            return obj
        tgt = gpt_translate(obj)
        log_translate(key_path, obj, tgt)
        return tgt
    elif isinstance(obj, list):
        return [translate_obj(item, parent_key=parent_key, parent_obj=item, key_path=f"{key_path}[{i}]") for i, item in enumerate(obj)]
    elif isinstance(obj, dict):
        return {k: translate_obj(v, parent_key=k, parent_obj=obj, key_path=f"{key_path}.{k}" if key_path else k) for k, v in obj.items()}
    else:
        return obj

def gpt_translate(text: str) -> str:
    for _ in range(3):  # 最多重試3次
        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text}
                ],
                max_tokens=2048,
                temperature=0.2
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"API error: {e}, retrying...")
            time.sleep(2)
    return text  # 若失敗則回傳原文

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python translate_json_gpt.py <商品代碼>")
        print("範例: python translate_json_gpt.py pan")
        sys.exit(1)
    try:
        from termcolor import colored
    except ImportError:
        def colored(s, *a, **k):
            return s
    
    # 取得商品代碼
    product_code = sys.argv[1]
    # 自動組合 config.json 路徑
    json_path = f"products/{product_code}/config.json"
    
    if not os.path.exists(json_path):
        print(f"錯誤: 找不到 {json_path}")
        sys.exit(1)
        
    print(f"正在翻譯: {json_path}")
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    
    translated = translate_obj(data)
    out_path = json_path.replace(".json", ".zh.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(translated, f, ensure_ascii=False, indent=2)
    print(f"已輸出: {out_path}") 