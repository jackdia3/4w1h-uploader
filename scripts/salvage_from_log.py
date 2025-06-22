import json
import re
import logging
from pathlib import Path
from urllib.parse import unquote
import os

# --- 設定 ---
BASE_DIR = Path(__file__).resolve().parent.parent
WWW_DIR = BASE_DIR / "products" / "WWW_Collection"
LOG_FILES = [
    Path(__file__).parent / "update_json_with_crops.log",
    Path(__file__).parent / "update_json_with_crops1.log"
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def find_json_objects_robust(log_content):
    """
    從日誌內容中穩健地提取完整的 JSON 物件字串。
    它通過尋找 "OpenAI GPT-4V 回應內容:" 標記，然後從第一個 '{' 開始，
    通過匹配大括號來精確地捕獲整個 JSON 物件。
    """
    json_objects = []
    start_marker = "OpenAI GPT-4V 回應內容:"
    
    current_pos = 0
    while True:
        start_index = log_content.find(start_marker, current_pos)
        if start_index == -1:
            break

        first_brace_index = log_content.find('{', start_index + len(start_marker))
        if first_brace_index == -1:
            current_pos = start_index + len(start_marker)
            continue

        open_braces = 0
        json_str_start = first_brace_index
        for i in range(first_brace_index, len(log_content)):
            char = log_content[i]
            if char == '{':
                open_braces += 1
            elif char == '}':
                open_braces -= 1
            
            if open_braces == 0:
                json_str = log_content[json_str_start : i + 1]
                json_objects.append(json_str)
                current_pos = i + 1
                break
        else:
            current_pos = start_index + len(start_marker)
            
    return json_objects

def salvage_from_log():
    """
    從多個日誌檔案中提取 AI 的分析結果，並用它來修復/補充 analysis.json 檔案中
    因各種問題（如檔名編碼、意外刪除）而遺漏的分析資料。
    """
    logging.info(f"--- 開始從 {len(LOG_FILES)} 個日誌檔案中救援分析資料 (穩健模式) ---")

    # 1. 建立「救援資料庫」，從所有日誌檔中收集資料
    salvage_db = {}
    for log_file in LOG_FILES:
        if not log_file.exists():
            logging.warning(f"警告：找不到日誌檔案 '{log_file.name}'，已跳過。")
            continue

        logging.info(f"正在讀取日誌: {log_file.name}")
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                log_content = f.read()
            
            # 改用更穩健的 JSON 提取方法
            json_blocks = find_json_objects_robust(log_content)
            
            if not json_blocks:
                logging.warning(f"在 '{log_file.name}' 中沒有找到任何 AI 回應區塊。")
                continue

            for block in json_blocks:
                try:
                    # 在解析前，先清理掉可能的尾隨逗號或不合規的換行符
                    cleaned_block = block.strip()
                    parsed_json = json.loads(cleaned_block)
                    salvage_db.update(parsed_json)
                except json.JSONDecodeError as e:
                    logging.warning(f"解析日誌中的 JSON 區塊時發生錯誤，已跳過。錯誤: {e}\n問題區塊: {block[:250]}...")
                    continue
        except IOError as e:
            logging.error(f"讀取日誌檔案 '{log_file.name}' 時發生錯誤: {e}")
            continue

    if not salvage_db:
        logging.error("未能從任何日誌檔案中建立可用的救援資料。")
        return

    logging.info(f"成功從所有日誌中載入 {len(salvage_db)} 筆獨特的 AI 分析記錄。")

    # 2. 遍歷所有產品，進行智慧匹配與修復
    total_repaired_items = 0
    try:
        product_names = [name for name in os.listdir(WWW_DIR) if (WWW_DIR / name).is_dir() and (name.startswith('product_') or name.endswith('_fixed'))]
        product_paths = sorted([WWW_DIR / name for name in product_names])
    except FileNotFoundError:
        logging.error(f"錯誤：找不到目標資料夾 '{WWW_DIR}'")
        return
        
    for product_path in product_paths:
        if not product_path.is_dir():
            continue

        analysis_path = product_path / "analysis.json"
        if not analysis_path.exists():
            continue
            
        logging.info(f"正在檢查產品: {product_path.name}")
        try:
            with open(analysis_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            product_has_changes = False
            for img_info in data.get("images", []):
                parent_name_stem = Path(img_info.get("local_path", "")).stem
                image_search_dirs = [product_path / "images"]
                split_dir = product_path / "images" / "split"
                if split_dir.is_dir():
                    image_search_dirs.append(split_dir)
                
                for search_dir in image_search_dirs:
                    for crop_path_on_disk in search_dir.glob(f"{parent_name_stem}*"):
                        if crop_path_on_disk.is_dir() or not crop_path_on_disk.is_file():
                            continue

                        is_already_analyzed = False
                        for category_key in ["selling_points", "use_cases", "spec_images", "generic_images"]:
                            if any(Path(item.get("local_path", "")).name == crop_path_on_disk.name for item in img_info.get(category_key, [])):
                                is_already_analyzed = True
                                break
                        if is_already_analyzed:
                            continue
                            
                        decoded_name = unquote(crop_path_on_disk.name)
                        
                        if decoded_name in salvage_db:
                            result = salvage_db[decoded_name]
                            
                            relative_crop_path = Path(product_path.name) / "images" / crop_path_on_disk.name
                            
                            full_crop_info = {
                                "local_path": str(relative_crop_path).replace('\\', '/'),
                                "summary": result.get("summary"),
                                "text_blocks": result.get("text_blocks", [])
                            }
                            category = result.get("category", "generic")
                            target_list_name = f"{category}s" if category in ["selling_point", "use_case"] else "spec_images" if category == "spec_image" else "generic_images"
                            
                            img_info.setdefault(target_list_name, []).append(full_crop_info)
                            logging.info(f"  [救援成功] {product_path.name} -> {crop_path_on_disk.name}")
                            total_repaired_items += 1
                            product_has_changes = True

            if product_has_changes:
                with open(analysis_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                logging.info(f"✅ 已儲存對 {product_path.name} 的修復。")

        except Exception as e:
            logging.error(f"處理產品 '{product_path.name}' 時發生未預期的嚴重錯誤: {e}", exc_info=True)
            continue
            
    logging.info(f"\n--- 救援完畢 ---")
    if total_repaired_items > 0:
        logging.info(f"總共從日誌中救援並修復了 {total_repaired_items} 個項目。")
    else:
        logging.info("所有產品的分析資料都已是最新狀態，無需救援。")


if __name__ == "__main__":
    salvage_from_log() 