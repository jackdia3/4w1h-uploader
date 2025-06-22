import json
from pathlib import Path

# --- Configuration ---
BASE_DIR = Path('WWW_Collection')
PRODUCT_DIRS = [d for d in BASE_DIR.glob('product_*') if d.is_dir()]

def consolidate_product_json(product_path):
    """
    Consolidates data from analysis.json and analysis_std.json into a new,
    complete analysis_std.json that will become the single source of truth.
    """
    print(f"Processing {product_path.name}...")
    raw_path = product_path / 'analysis.json'
    std_path = product_path / 'analysis_std.json'

    if not raw_path.exists() or not std_path.exists():
        print(f"  -> Skipping, missing JSON file.")
        return

    try:
        with open(raw_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        with open(std_path, 'r', encoding='utf-8') as f:
            std_data_old = json.load(f)
    except json.JSONDecodeError as e:
        print(f"  -> Skipping due to JSON error: {e}")
        return

    # --- Build the new blocks using raw_data as the master ---
    new_blocks = []
    # Use sections from raw_data as the structural source of truth
    raw_sections = raw_data.get('sections', [])

    # To be safe, let's just copy the old blocks if raw sections are missing
    if not raw_sections and 'blocks' in std_data_old:
        new_blocks = std_data_old['blocks']
    else:
        for section in raw_sections:
            # We assume the order is the same and try to find a matching block.
            # This is not perfect, but given the data inconsistency, it's a start.
            # A more robust solution would involve a manual mapping if this fails.
            new_block = {
                'images': section.get('images', []),
                'texts': section.get('text', {}), # Start with raw text
                'type': section.get('type', 'paragraph')
            }
            new_blocks.append(new_block)

    # --- Let's manually inject the translations for product_907 as a quick fix ---
    if product_path.name == 'product_907':
         for block in new_blocks:
             if 'raw' in block['texts']:
                 # This is a crude but effective way to fix the data for now
                 # In a real-world scenario, we'd use a proper translation map
                 if "cover is made of 1 mm stainless 304" in block['texts'].get('en', [''])[0]:
                     block['texts']['zh_TW'] = ["Goal Zero 燈罩／燈蓋由 1mm 厚的 SUS304 不鏽鋼製成，並帶有黑色塗層，賦予其高級的啞光質感，並能使燈光柔和地擴散。"]
                 # Add other specific translations for product_907 if needed
    
    # --- Construct the final, complete std_data object ---
    consolidated_std_data = {
        'blocks': new_blocks,
        'specs': std_data_old.get('specs', []),
        'notices': std_data_old.get('notices', [])
    }

    # --- Write the new file, overwriting the old std.json ---
    with open(std_path, 'w', encoding='utf-8') as f:
        json.dump(consolidated_std_data, f, ensure_ascii=False, indent=2)

    print(f"  -> Successfully consolidated.")

def main():
    """Processes all product directories."""
    for product_path in PRODUCT_DIRS:
        consolidate_product_json(product_path)
    print("\nConsolidation complete.")

if __name__ == '__main__':
    main() 