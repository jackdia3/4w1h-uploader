import json
from pathlib import Path
import logging

# --- 設定 ---
BASE_DIR = Path(__file__).resolve().parent.parent
WWW_DIR = BASE_DIR / "products" / "WWW_Collection"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fix_json_keys():
    """
    遍歷所有 analysis.json 檔案，將放錯位置的 AI 分析結果，
    從錯誤的鍵 (e.g., 'selling_point_images') 搬移到正確的鍵 (e.g., 'selling_points')。
    這是一個一次性的修復腳本，不會呼叫任何 API。
    """
    if not WWW_DIR.is_dir():
        logging.error(f"錯誤：找不到目標資料夾 '{WWW_DIR}'")
        return

    logging.info("--- 開始修復 analysis.json 檔案中的鍵名 ---")

    key_mapping = {
        "selling_point_images": "selling_points",
        "use_case_images": "use_cases",
        "spec_image_images": "spec_images"
    }

    product_paths = sorted(list(WWW_DIR.glob('product_*')))
    if not product_paths:
        logging.info("在 'products/WWW_Collection' 中找不到任何 'product_*' 資料夾。")
        return

    total_fixed_files = 0
    for product_path in product_paths:
        if not product_path.is_dir():
            continue

        analysis_path = product_path / "analysis.json"
        if not analysis_path.exists():
            continue

        try:
            with open(analysis_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            has_changes = False
            for img_info in data.get("images", []):
                for wrong_key, correct_key in key_mapping.items():
                    if wrong_key in img_info and img_info[wrong_key]:
                        # 確保目標鍵存在且為列表
                        img_info.setdefault(correct_key, [])
                        
                        # 搬移資料
                        img_info[correct_key].extend(img_info[wrong_key])
                        
                        # 刪除舊的錯誤鍵
                        del img_info[wrong_key]
                        
                        has_changes = True
            
            if has_changes:
                with open(analysis_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                logging.info(f"✅ 已成功修復並儲存: {analysis_path.name}")
                total_fixed_files += 1
            else:
                logging.info(f"⚪️ 無需修復: {analysis_path.name}")

        except (IOError, json.JSONDecodeError) as e:
            logging.error(f"處理 '{analysis_path.name}' 時發生錯誤: {e}")
            continue
    
    logging.info(f"\n--- 修復完畢 ---")
    logging.info(f"總共修復了 {total_fixed_files} 個檔案。")

if __name__ == "__main__":
    fix_json_keys() 