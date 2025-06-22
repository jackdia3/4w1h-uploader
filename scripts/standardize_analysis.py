import json
import os
from pathlib import Path
import logging

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent.parent / 'products' / 'WWW_Collection'
LOG_FILE_PATH = Path(__file__).parent / 'standardize_analysis.log'

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=LOG_FILE_PATH,
    filemode='w',
    encoding='utf-8'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(levelname)s: %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

def needs_standardization(data):
    """
    Detects if the JSON data uses the old, nested or hybrid structure.
    It checks if ANY image object in the list contains nested category keys.
    This is the definitive test for the old format.
    """
    # FORCING RETRY: Temporarily returning True to re-process all files.
    return True

    images = data.get('images', [])
    if not images or not isinstance(images, list):
        return False # Nothing to do.

    for image in images:
        if not isinstance(image, dict):
            continue # Skip malformed entries in the list.
        # If any of these keys exist in any top-level image object, it's the old format.
        if any(key in image for key in ['selling_points', 'use_cases', 'spec_images', 'generic_images']):
            return True # Needs standardization.
            
    return False # It's already flat.

def standardize_nested_json(data):
    """
    Converts a JSON object from the old nested/hybrid structure to the new flat structure,
    carefully preserving and consolidating all textual descriptions.
    """
    product_name = data.get('product_name', 'Unknown Product')
    logging.info(f"Standardizing nested structure for: {product_name}")
    
    flat_images = []
    
    # Consolidate specs from the old format into a simple list
    all_specs = []
    if 'specs' in data and isinstance(data['specs'], list):
        for spec_group in data.get('specs', []):
            if isinstance(spec_group, list):
                for spec_item in spec_group:
                    if isinstance(spec_item, dict) and 'label' in spec_item and 'value' in spec_item:
                        all_specs.append({'name': spec_item['label'], 'value': spec_item['value']})

    original_images = data.get('images', [])
    if not isinstance(original_images, list):
        logging.warning(f"  'images' key for {product_name} is not a list. Skipping image processing.")
        original_images = []

    for parent_image_obj in original_images:
        if not isinstance(parent_image_obj, dict):
            continue

        parent_local_path = parent_image_obj.get("local_path", "").replace('\\', '/')
        base_name_match = re.match(r'^(.*?)(?:-crop\d+|_crop\d+)?\..*$', Path(parent_local_path).name)
        parent_base_name = base_name_match.group(1) if base_name_match else Path(parent_local_path).stem
        
        child_categories = ['selling_points', 'use_cases', 'spec_images', 'generic_images']
        has_children = any(parent_image_obj.get(cat) for cat in child_categories)

        # Collect all text from the parent object itself, which might contain descriptions
        parent_texts = []
        if 'summary' in parent_image_obj and parent_image_obj['summary']:
            parent_texts.append(parent_image_obj['summary'])
        if 'text_blocks' in parent_image_obj and isinstance(parent_image_obj['text_blocks'], list):
            for text_block in parent_image_obj['text_blocks']:
                if isinstance(text_block, dict) and 'content' in text_block and text_block['content']:
                    parent_texts.append(text_block['content'])
        
        if has_children:
            # If parent has children, iterate through them
            for category_plural in child_categories:
                if category_plural in parent_image_obj and isinstance(parent_image_obj[category_plural], list):
                    category_singular = category_plural.replace('_images', '').rstrip('s')
                    for child_image_obj in parent_image_obj[category_plural]:
                        if not isinstance(child_image_obj, dict) or not child_image_obj.get('local_path'):
                            continue

                        child_local_path = child_image_obj.get('local_path', '').replace('\\', '/')
                        
                        description_parts = []
                        # Child's own text takes precedence
                        if 'summary' in child_image_obj and child_image_obj['summary']:
                            description_parts.append(child_image_obj['summary'])
                        if 'text_blocks' in child_image_obj and isinstance(child_image_obj['text_blocks'], list):
                            for text_block in child_image_obj['text_blocks']:
                                if isinstance(text_block, dict) and 'content' in text_block and text_block['content']:
                                    description_parts.append(text_block['content'])
                        
                        # If the child is the parent image and has no text, it inherits the parent's text
                        if child_local_path == parent_local_path and not description_parts:
                            description_parts.extend(parent_texts)

                        flat_images.append({
                            "local_path": child_local_path,
                            "description": " ".join(part for part in description_parts if part),
                            "category": category_singular,
                            "base_name": parent_base_name,
                            "is_parent": child_local_path == parent_local_path,
                            "is_hero": parent_image_obj.get('is_hero', False)
                        })
        else:
            # If parent has NO children, it's a standalone image. Use its own text.
            if parent_local_path:
                 flat_images.append({
                    "local_path": parent_local_path,
                    "description": " ".join(part for part in parent_texts if part),
                    "category": "generic", # No category info available, so defaults to generic
                    "base_name": parent_base_name,
                    "is_parent": True,
                    "is_hero": parent_image_obj.get('is_hero', False)
                })

    # Create the new standardized data structure
    standardized_data = {
        "product_id": data.get('product_id', ''),
        "product_name": product_name,
        "meta_description": "",
        "images": flat_images,
        "specs": all_specs,
        "is_hero": any(img.get('is_hero') for img in flat_images)
    }
    
    logging.info(f"  Successfully standardized. Found {len(flat_images)} images.")
    return standardized_data

def main():
    """
    Main function to find, check, and standardize all analysis.json files.
    """
    logging.info("--- Starting Standardization of analysis.json Files ---")
    
    product_dirs = sorted([d for d in BASE_DIR.iterdir() if d.is_dir() and d.name.startswith('product_')])
    
    if not product_dirs:
        logging.warning("No product directories found.")
        return

    stats = {'total': len(product_dirs), 'standardized': 0, 'skipped': 0, 'failed': 0}
    
    for product_dir in product_dirs:
        analysis_file = product_dir / 'analysis.json'
        
        if not analysis_file.exists():
            logging.warning(f"Skipping {product_dir.name}: analysis.json not found.")
            stats['skipped'] += 1
            continue
            
        try:
            with open(analysis_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Use the new, more robust checker.
            if needs_standardization(data):
                standardized_data = standardize_nested_json(data)
                
                # Overwrite the original file with the new standardized data
                with open(analysis_file, 'w', encoding='utf-8') as f:
                    json.dump(standardized_data, f, ensure_ascii=False, indent=2)
                
                logging.info(f"Successfully wrote standardized file for {product_dir.name}")
                stats['standardized'] += 1
            else:
                logging.info(f"Skipping {product_dir.name}: Already in clean, flat structure.")
                stats['skipped'] += 1

        except json.JSONDecodeError:
            logging.error(f"Failed to process {product_dir.name}: Invalid JSON in {analysis_file}")
            stats['failed'] += 1
        except Exception as e:
            logging.error(f"An unexpected error occurred processing {product_dir.name}: {e}")
            stats['failed'] += 1

    logging.info("\n--- Standardization Summary ---")
    logging.info(f"  Total product directories: {stats['total']}")
    logging.info(f"  ✅ Standardized: {stats['standardized']}")
    logging.info(f"  ⏩ Skipped (already flat): {stats['skipped']}")
    logging.info(f"  ❌ Failed: {stats['failed']}")
    logging.info(f"--- Log file saved to: {LOG_FILE_PATH} ---")

if __name__ == '__main__':
    # Add a check for the 're' module since it was used without being imported
    import re
    main() 