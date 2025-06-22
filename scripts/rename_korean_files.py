import json
import logging
from pathlib import Path
from unidecode import unidecode
import re
import os

# --- 設定 ---
BASE_DIR = Path(__file__).resolve().parent.parent
WWW_DIR = BASE_DIR / "products" / "WWW_Collection"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def has_non_ascii(text):
    """檢查字串是否包含非 ASCII 字元"""
    return not all(ord(c) < 128 for c in text)

def sanitize_filename(filename):
    """將檔名中的非 ASCII 字元音譯，並清理字元"""
    if not has_non_ascii(filename):
        return filename
    
    # 1. 將非 ASCII 字元音譯為 ASCII
    # e.g., 'Wet-Tissue-Case_필드컷_01.jpg' -> 'Wet-Tissue-Case_pildeukeos_01.jpg'
    sanitized = unidecode(filename)
    
    # 2. (可選) 清理常見的特殊字元，以空格取代
    # sanitized = re.sub(r'[^a-zA-Z0-9._-]', ' ', sanitized)
    
    return sanitized

def rename_and_update_json():
    """
    遍歷所有產品圖片，將包含非 ASCII 字元的檔名進行標準化重命名，
    並同步更新對應的 analysis.json 檔案中的路徑。
    """
    logging.info("--- 開始掃描並標準化檔名 ---")
    total_renamed_files = 0
    
    try:
        product_names = [name for name in os.listdir(WWW_DIR) if (WWW_DIR / name).is_dir() and (name.startswith('product_') or name.endswith('_fixed'))]
        product_paths = sorted([WWW_DIR / name for name in product_names])
    except FileNotFoundError:
        logging.error(f"錯誤：找不到目標資料夾 '{WWW_DIR}'")
        return

    if not product_paths:
        logging.warning(f"在 '{WWW_DIR}' 中沒有找到任何 'product_*' 資料夾。")
        return

    for product_path in product_paths:
        if not product_path.is_dir():
            continue

        images_dir = product_path / "images"
        analysis_path = product_path / "analysis.json"

        if not images_dir.is_dir() or not analysis_path.exists():
            continue

        logging.info(f"正在處理產品: {product_path.name}")
        try:
            with open(analysis_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            rename_map = {}

            # --- 第一階段：掃描並重命名實體檔案 ---
            files_to_rename = [f for f in images_dir.glob('*.*') if has_non_ascii(f.name)]

            if not files_to_rename:
                logging.info(f"  -> {product_path.name}: 所有檔名皆為標準 ASCII，無需處理。")
                continue

            for old_path in files_to_rename:
                new_name = sanitize_filename(old_path.name)
                new_path = old_path.with_name(new_name)
                
                if old_path == new_path:
                    continue

                try:
                    old_path.rename(new_path)
                    logging.info(f"  [重命名] '{old_path.name}' -> '{new_path.name}'")
                    # 記錄完整的相對路徑變更，供 JSON 更新使用
                    old_rel_path = f"{product_path.name}/images/{old_path.name}"
                    new_rel_path = f"{product_path.name}/images/{new_path.name}"
                    rename_map[old_rel_path] = new_rel_path
                    total_renamed_files += 1
                except OSError as e:
                    logging.error(f"  重命名檔案 '{old_path}' 時發生錯誤: {e}")
                    # 如果重命名失敗，則不記錄到 map 中，避免後續 JSON 出錯
                    continue
            
            # --- 第二階段：如果發生了重命名，則更新 JSON ---
            if not rename_map:
                logging.info(f"  -> {product_path.name}: 發現非 ASCII 檔名，但音譯後檔名未改變，無需處理。")
                continue

            logging.info(f"  正在更新 '{analysis_path.name}' for product {product_path.name}...")
            
            # 將整個 JSON 資料轉換為字串，以便進行全局替換
            json_string = json.dumps(data, ensure_ascii=False)

            # 遍歷 rename_map，替換所有舊路徑
            for old_path_str, new_path_str in rename_map.items():
                # 確保我們替換的是被引號包圍的完整路徑字串，避免部分匹配
                json_string = json_string.replace(f'"{old_path_str}"', f'"{new_path_str}"')

            # 將更新後的字串解析回 JSON 物件
            updated_data = json.loads(json_string)

            # 寫回檔案
            with open(analysis_path, 'w', encoding='utf-8') as f:
                json.dump(updated_data, f, ensure_ascii=False, indent=2)
            logging.info(f"  ✅ '{analysis_path.name}' 已成功同步。")

        except Exception as e:
            logging.error(f"處理產品 '{product_path.name}' 時發生未預期的嚴重錯誤: {e}", exc_info=True)
            continue

    logging.info("\n--- 標準化流程完畢 ---")
    if total_renamed_files > 0:
        logging.info(f"總共重命名並同步了 {total_renamed_files} 個檔案。")
    else:
        logging.info("所有檔名都符合標準，無需任何變更。")


if __name__ == "__main__":
    # 為了運行此腳本，需要安裝 unidecode 套件
    # 請執行: pip install unidecode
    try:
        from unidecode import unidecode
    except ImportError:
        logging.error("錯誤：缺少 'unidecode' 套件。")
        logging.error("請在您的終端機中執行 'pip install unidecode' 來安裝它。")
        exit(1)
    
    rename_and_update_json() 