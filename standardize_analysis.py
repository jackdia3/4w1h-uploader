import os
import json

def standardize_analysis(data):
    blocks = []
    # 處理 captions/sections/texts
    for src in ['captions', 'sections', 'texts']:
        if src in data:
            for item in data[src]:
                block = {}
                # 處理圖片
                if 'image' in item:
                    block['images'] = [item['image']]
                elif 'images' in item:
                    block['images'] = item['images']
                elif 'local_path' in item:
                    block['images'] = [item['local_path']]
                # 處理描述型態
                block['type'] = item.get('role') or item.get('type') or 'copy'
                # 處理多語言描述
                texts = {}
                if 'texts' in item:
                    for lang in ['zh', 'zh_TW', 'kr', 'en']:
                        if lang in item['texts']:
                            val = item['texts'][lang]
                            texts[lang] = val if isinstance(val, list) else [val]
                else:
                    for lang in ['zh', 'zh_TW', 'kr', 'en']:
                        if lang in item:
                            val = item[lang]
                            texts[lang] = val if isinstance(val, list) else [val]
                if texts:
                    block['texts'] = texts
                # 處理 table
                if 'table' in item:
                    block['table'] = []
                    for row in item['table']:
                        if isinstance(row, dict):
                            block['table'].append(row)
                        elif isinstance(row, list) and len(row) == 2:
                            block['table'].append({'label_kr': row[0], 'value_kr': row[1]})
                # 處理 note
                if 'note' in item:
                    block['note'] = item['note']
                blocks.append(block)
    # 處理 specs
    specs = []
    if 'specs' in data:
        for spec in data['specs']:
            if isinstance(spec, dict):
                specs.append(spec)
            elif isinstance(spec, list):
                for row in spec:
                    specs.append(row)
    # 處理 notices
    notices = []
    for key in ['notice', 'notices']:
        if key in data:
            for n in data[key]:
                if isinstance(n, dict):
                    notices.append(n)
                elif isinstance(n, str):
                    notices.append({'zh': n})
    return {
        'blocks': blocks,
        'specs': specs,
        'notices': notices
    }

def main():
    base_dir = 'WWW_Collection'
    for prod in os.listdir(base_dir):
        prod_path = os.path.join(base_dir, prod)
        if not (os.path.isdir(prod_path) and prod.startswith('product_')):
            continue
        path = os.path.join(prod_path, 'analysis.json')
        if not os.path.exists(path):
            continue
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        std = standardize_analysis(data)
        out_path = os.path.join(prod_path, 'analysis_std.json')
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(std, f, ensure_ascii=False, indent=2)
        print(f'標準化完成: {out_path}')

if __name__ == '__main__':
    main() 