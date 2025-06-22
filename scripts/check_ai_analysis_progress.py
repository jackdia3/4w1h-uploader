import json
from pathlib import Path

# --- 設定 ---
BASE_DIR = Path(__file__).resolve().parent.parent
WWW_DIR = BASE_DIR / "products" / "WWW_Collection"

def check_progress():
    """
    掃描所有產品的 analysis.json，統計已由 AI 分析的裁切圖數量，並與磁碟上的總數進行比較。
    """
    if not WWW_DIR.is_dir():
        print(f"錯誤：找不到目標資料夾 '{WWW_DIR}'")
        return

    total_analyzed_count = 0
    total_disk_count = 0
    
    print("--- AI 圖片分析進度報告 ---\n")

    product_paths = sorted(list(WWW_DIR.glob('product_*')))
    if not product_paths:
        print("在 'products/WWW_Collection' 中找不到任何 'product_*' 資料夾。")
        return

    for product_path in product_paths:
        if not product_path.is_dir():
            continue

        analysis_path = product_path / "analysis.json"
        images_dir = product_path / "images"

        if not analysis_path.exists():
            # print(f"產品 {product_path.name}: 找不到 analysis.json，跳過。")
            continue

        # 1. 統計磁碟上的總裁切圖數量
        disk_crops = list(images_dir.glob('*-crop*.jpg'))
        disk_crop_count = len(disk_crops)
        total_disk_count += disk_crop_count

        # 2. 統計已分析的裁切圖數量
        analyzed_crop_count = 0
        try:
            with open(analysis_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            analyzed_crops_in_json = set()
            for img_info in data.get("images", []):
                # 修正：使用與分析腳本完全一致的鍵名
                for category_key in ["selling_points", "use_cases", "spec_images", "generic_images"]:
                    for crop_analysis in img_info.get(category_key, []):
                        if "local_path" in crop_analysis:
                            analyzed_crops_in_json.add(Path(crop_analysis["local_path"]).name)
            
            analyzed_crop_count = len(analyzed_crops_in_json)
            total_analyzed_count += analyzed_crop_count

            status = "✅" if analyzed_crop_count == disk_crop_count and disk_crop_count > 0 else "⏳"
            print(f"{status} {product_path.name}: {analyzed_crop_count} / {disk_crop_count}")

        except (IOError, json.JSONDecodeError) as e:
            # print(f"產品 {product_path.name}: 讀取或解析 analysis.json 時發生錯誤 - {e}")
            continue # 即使某個檔案出錯，也繼續處理下一個

    print("\n--- 總結 ---")
    print(f"總裁切圖數量: {total_disk_count}")
    print(f"已分析圖片總數: {total_analyzed_count}")

    if total_disk_count > 0:
        percentage = (total_analyzed_count / total_disk_count) * 100
        print(f"完成度: {percentage:.2f}%")
    
    print("\n報告完畢。")


if __name__ == "__main__":
    check_progress() 