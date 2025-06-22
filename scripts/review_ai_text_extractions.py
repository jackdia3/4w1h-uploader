import json
from pathlib import Path

# --- 設定 ---
BASE_DIR = Path(__file__).resolve().parent.parent
WWW_DIR = BASE_DIR / "products" / "WWW_Collection"

def review_text_extractions():
    """掃描所有 analysis.json，並報告 AI 提取的文字區塊以便審核。"""
    if not WWW_DIR.is_dir():
        print(f"錯誤：找不到目標資料夾 '{WWW_DIR}'")
        return

    print("\n--- AI 文字提取審閱報告 ---")
    
    found_any_text = False
    
    for product_path in sorted(WWW_DIR.glob('product_*')):
        if not product_path.is_dir():
            continue

        analysis_path = product_path / "analysis.json"
        if not analysis_path.exists():
            continue

        try:
            with open(analysis_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            images_list = data.get("images", [])
            product_has_text = False
            
            output_for_product = []

            for img_info in images_list:
                crops = img_info.get("crops", [])
                if not (crops and isinstance(crops, list)):
                    continue

                for crop in crops:
                    text_blocks = crop.get("ai_text_blocks", [])
                    if text_blocks and isinstance(text_blocks, list):
                        if not product_has_text:
                            output_for_product.append(f"\n產品: {product_path.name}")
                            product_has_text = True
                            found_any_text = True

                        output_for_product.append(f"  - 圖片: {Path(crop.get('local_path', '')).name}")
                        for block in text_blocks:
                            b_type = block.get('type', '未知')
                            b_content = block.get('content', '').replace('\n', ' ')
                            output_for_product.append(f"    - [{b_type}] {b_content}")
            
            if product_has_text:
                print("\n".join(output_for_product))

        except (json.JSONDecodeError, KeyError) as e:
            print(f"處理 '{analysis_path}' 時發生錯誤: {e}")
            continue
            
    if not found_any_text:
        print("\n在所有產品中，未發現任何由 AI 提取的文字區塊。")

if __name__ == "__main__":
    review_text_extractions() 