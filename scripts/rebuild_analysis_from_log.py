import os
import json
import re
import logging
from pathlib import Path
from collections import defaultdict

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_FILE_PATH = Path(__file__).parent / 'update_json_with_crops1.log'
PRODUCTS_DIR = PROJECT_ROOT / 'products' / 'WWW_Collection'

def parse_log_file(log_path):
    """
    Parses the log file to extract AI analysis data for each cropped image,
    organized by product and parent image.
    """
    if not log_path.exists():
        logging.error(f"Log file not found at: {log_path}")
        return None

    logging.info(f"Parsing log file: {log_path.name}")
    
    log_content = log_path.read_text(encoding='utf-8')
    
    # This dictionary will store all the structured data from the log
    # { product_id: { parent_image_name: { crop_image_name: {analysis_data} } } }
    log_data = defaultdict(lambda: defaultdict(dict))
    
    current_product_id = None
    current_parent_image = None

    # Regex to find the JSON blocks from the AI response
    # It looks for the start marker, and then captures everything until the next log timestamp
    # using a non-greedy match `(.+?)` within a lookahead assertion.
    response_pattern = re.compile(
        r"OpenAI GPT-4V 回應內容:\s*\n(\{.+?\})\s*\n\d{4}-\d{2}-\d{2}",
        re.DOTALL
    )

    # Use a line-by-line scan to establish context (product_id, parent_image)
    # This is more reliable than trying to capture everything with one complex regex.
    lines = log_content.splitlines()
    json_blob_indices = []

    for i, line in enumerate(lines):
        product_match = re.search(r"處理產品：(product_\d+)", line)
        if product_match:
            current_product_id = product_match.group(1)
            continue

        parent_match = re.search(r"為父圖片 '([^']+?\.jpg)' 找到", line)
        if parent_match:
            # The parent image filename in the log might have URL encoding for Korean chars,
            # but the AI response uses the decoded version. We store the raw version from the log.
            current_parent_image = parent_match.group(1)
            continue
        
        # When we find the response marker, we store the current context with the line number
        if "OpenAI GPT-4V 回應內容:" in line:
            if current_product_id and current_parent_image:
                json_blob_indices.append({
                    'product_id': current_product_id,
                    'parent_image': current_parent_image,
                    'start_line': i
                })

    # Now, parse the JSON blobs using the start line indices
    for i, context in enumerate(json_blob_indices):
        start_line = context['start_line']
        # Find the end of the JSON blob
        # It ends right before the next "INFO -" or "WARNING -" or "ERROR -" log entry
        end_line = len(lines)
        for j in range(start_line + 1, len(lines)):
             if re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - (INFO|WARNING|ERROR)", lines[j]):
                end_line = j
                break
        
        json_str = "\n".join(lines[start_line+1 : end_line]).strip()
        # Clean up potential markdown code blocks
        json_str = json_str.lstrip('```json').rstrip('```').strip()
        
        try:
            analysis_data = json.loads(json_str)
            # The keys in the AI response might have escaped Korean chars, we use them as is.
            log_data[context['product_id']][context['parent_image']].update(analysis_data)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON for {context['product_id']}/{context['parent_image']} at line {start_line+1}. Error: {e}")
            logging.debug(f"Problematic JSON string:\n{json_str}")

    logging.info("Successfully parsed log file.")
    return log_data

def rebuild_analysis_json(product_path, log_data_for_product):
    """
    Rebuilds the analysis.json for a single product using the parsed log data.
    """
    analysis_path = product_path / "analysis.json"
    if not analysis_path.exists():
        logging.warning(f"Skipping {product_path.name}, analysis.json not found.")
        return

    try:
        with open(analysis_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        logging.error(f"Could not read or parse {analysis_path}. Error: {e}")
        return

    logging.info(f"Rebuilding {analysis_path}...")
    
    new_images_list = []
    
    # Iterate through the original parent images to maintain order and metadata
    for parent_img_info in data.get("images", []):
        new_parent_info = parent_img_info.copy()
        
        # Ensure category lists exist
        new_parent_info['selling_points'] = []
        new_parent_info['use_cases'] = []
        new_parent_info['spec_images'] = []
        new_parent_info['generic_images'] = []
        
        parent_filename = Path(parent_img_info.get("local_path", "")).name
        
        # Find the analysis for this parent's children in the log data
        crop_analyses = log_data_for_product.get(parent_filename, {})
        
        if not crop_analyses:
            logging.warning(f"  - No crop analysis found in log for parent: {parent_filename}")
        
        for crop_filename, analysis in crop_analyses.items():
            category = analysis.get("category", "generic_image") # Default to generic
            
            # Map category to the correct list name
            if category == "selling_point":
                target_list_name = "selling_points"
            elif category == "use_case":
                target_list_name = "use_cases"
            elif category == "spec_image":
                target_list_name = "spec_images"
            else:
                target_list_name = "generic_images"

            # Reconstruct the crop info object
            rebuilt_crop = {
                # Construct path relative to product dir, as seen in existing files
                "local_path": f"{product_path.name}/images/{crop_filename}",
                "summary": analysis.get("summary", ""),
                "text_blocks": analysis.get("text_blocks", [])
            }
            new_parent_info[target_list_name].append(rebuilt_crop)
            
        new_images_list.append(new_parent_info)

    # Overwrite the old images list with the newly built one
    data['images'] = new_images_list
    
    # Write the fully rebuilt data back to the file
    try:
        with open(analysis_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.info(f"  -> Successfully rebuilt and saved {analysis_path.name}")
    except IOError as e:
        logging.error(f"  -> Failed to write to {analysis_path.name}. Error: {e}")

def main():
    """Main function to orchestrate the rebuilding process."""
    log_data = parse_log_file(LOG_FILE_PATH)
    
    if not log_data:
        logging.error("Could not parse log data. Aborting.")
        return

    if not PRODUCTS_DIR.is_dir():
        logging.error(f"Products directory not found at: {PRODUCTS_DIR}")
        return

    logging.info(f"--- Starting to rebuild analysis.json files in {PRODUCTS_DIR} ---")
    
    # Iterate through all product directories found in the log
    for product_id, data_for_product in log_data.items():
        product_path = PRODUCTS_DIR / product_id
        if product_path.is_dir():
            rebuild_analysis_json(product_path, data_for_product)
        else:
            logging.warning(f"Directory for product '{product_id}' from log not found. Skipping.")
            
    logging.info("\n✅ Rebuilding process complete.")

if __name__ == "__main__":
    main() 