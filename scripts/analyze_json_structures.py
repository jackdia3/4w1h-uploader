import json
import os
import glob
from collections import defaultdict

def get_json_structure(data, path=""):
    """Recursively traverses a JSON object and returns a simplified structure."""
    if isinstance(data, dict):
        structure = {}
        for key, value in data.items():
            new_path = f"{path}.{key}" if path else key
            # Limit array analysis to the first element to avoid excessive output
            if isinstance(value, list) and len(value) > 1:
                structure[key] = [get_json_structure(value[0], f"{path}[]")]
            else:
                structure[key] = get_json_structure(value, new_path)
        return structure
    elif isinstance(data, list):
        if data:
            return [get_json_structure(data[0], f"{path}[]")]
        else:
            return []
    else:
        return type(data).__name__

def main():
    """
    Analyzes the structure of all analysis.json files in the WWW_Collection
    and prints a markdown report.
    """
    base_path = "products/WWW_Collection"
    json_files = glob.glob(os.path.join(base_path, "product_*", "analysis.json"))

    unique_structures = {}
    report_lines = ["# analysis.json 結構分析報告\n"]
    file_errors = []

    for file_path in sorted(json_files):
        product_id = os.path.basename(os.path.dirname(file_path))
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            structure = get_json_structure(data)
            # Use a frozenset of items for dicts to make structure hashable
            structure_str = json.dumps(structure, sort_keys=True)

            if structure_str not in unique_structures:
                unique_structures[structure_str] = {
                    "structure": structure,
                    "products": [product_id]
                }
            else:
                unique_structures[structure_str]["products"].append(product_id)

        except json.JSONDecodeError as e:
            file_errors.append(f"- `{file_path}`: JSON 格式錯誤 - {e}")
        except Exception as e:
            file_errors.append(f"- `{file_path}`: 讀取或處理失敗 - {e}")
    
    if file_errors:
        report_lines.append("## 檔案讀取錯誤\n")
        report_lines.extend(file_errors)
        report_lines.append("\n---\n")

    report_lines.append("## 偵測到的結構類型\n")
    if not unique_structures:
        report_lines.append("在 `products/WWW_Collection` 中找不到或無法處理任何 `analysis.json` 檔案。")
    
    # Sort structures by the number of products they apply to
    sorted_structures = sorted(unique_structures.items(), key=lambda item: len(item[1]['products']), reverse=True)

    for i, (_, info) in enumerate(sorted_structures):
        report_lines.append(f"### 結構類型 {i+1}\n")
        report_lines.append(f"**蹤跡發現於以下產品:** {', '.join(info['products'])} ({len(info['products'])} 個)\n")
        report_lines.append("```json")
        report_lines.append(json.dumps(info['structure'], sort_keys=True, indent=2, ensure_ascii=False))
        report_lines.append("```\n")

    # --- Comparison Section ---
    report_lines.append("---\n\n## 結構差異比較\n")
    
    all_top_level_keys = set()
    all_image_level_keys = set()
    structure_details = []

    for _, info in sorted_structures:
        struct = info['structure']
        top_keys = set(struct.keys())
        all_top_level_keys.update(top_keys)
        
        image_keys = set()
        if 'images' in struct and isinstance(struct.get('images'), list) and struct['images']:
            if isinstance(struct['images'][0], dict):
                image_keys = set(struct['images'][0].keys())
        all_image_level_keys.update(image_keys)
        
        structure_details.append({
            "products": info['products'],
            "top_keys": top_keys,
            "image_keys": image_keys
        })

    report_lines.append("### 頂層屬性 (Top-Level Keys)\n")
    report_lines.append(f"**所有檔案中出現過的頂層屬性:** `{','.join(sorted(list(all_top_level_keys)))}`\n")
    for i, detail in enumerate(structure_details):
        report_lines.append(f"\n**結構類型 {i+1}** (用於 `{detail['products'][0]}` 等 {len(detail['products'])} 個產品):")
        report_lines.append(f"  - **包含:** `{','.join(sorted(list(detail['top_keys'])))}`")
        missing = all_top_level_keys - detail['top_keys']
        if missing:
            report_lines.append(f"  - **缺少:** `{','.join(sorted(list(missing)))}`")

    report_lines.append("\n### `images` 陣列內物件的屬性 (Image-Level Keys)\n")
    report_lines.append(f"**所有檔案中出現過的圖片層級屬性:** `{','.join(sorted(list(all_image_level_keys)))}`\n")
    for i, detail in enumerate(structure_details):
        report_lines.append(f"\n**結構類型 {i+1}** (用於 `{detail['products'][0]}` 等 {len(detail['products'])} 個產品):")
        if not detail['image_keys']:
            report_lines.append("  - (此結構的 `images` 陣列為空或格式無法分析)")
            continue
        report_lines.append(f"  - **包含:** `{','.join(sorted(list(detail['image_keys'])))}`")
        missing = all_image_level_keys - detail['image_keys']
        if missing:
            report_lines.append(f"  - **缺少:** `{','.join(sorted(list(missing)))}`")

    report_content = "\n".join(report_lines)
    
    report_filename = "scripts/json_structure_analysis.md"
    with open(report_filename, 'w', encoding='utf-8') as f:
        f.write(report_content)
        
    print(f"分析完成！報告已生成於: {report_filename}")
    print("\n--- 報告預覽 ---\n")
    print(report_content)


if __name__ == "__main__":
    main() 