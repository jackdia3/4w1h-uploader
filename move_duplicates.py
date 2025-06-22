import os
import shutil
from pathlib import Path
from collections import defaultdict

# 設定搜尋路徑與共用資料夾
BASE = Path('4w1h-min/products/WWW_Collection')
SHARED = BASE / 'shared_images'
SHARED.mkdir(exist_ok=True)

# 支援的圖片副檔名
EXTS = {'.jpg', '.jpeg', '.png', '.webp'}

# 1. 掃描所有圖片
all_images = defaultdict(list)
for p in BASE.rglob('*'):
    if p.is_file() and p.suffix.lower() in EXTS:
        all_images[p.name].append(p)

# 2. 找出重複檔案
duplicates = {k: v for k, v in all_images.items() if len(v) > 1}

# 3. 搬移重複檔案到 shared_images，並保留原始路徑清單
move_log = []
for fname, paths in duplicates.items():
    # 只搬第一個，其餘用 symlink 或複製
    target = SHARED / fname
    if not target.exists():
        shutil.copy2(paths[0], target)
    for src in paths:
        if src.resolve() == target.resolve():
            continue
        try:
            # Windows symlink 需管理員權限，否則直接複製
            os.remove(src)
            try:
                os.symlink(target.resolve(), src)
                move_log.append(f'symlink: {src} -> {target}')
            except Exception:
                shutil.copy2(target, src)
                move_log.append(f'copy: {src} (from {target})')
        except Exception as e:
            move_log.append(f'fail: {src} ({e})')

# 4. 輸出搬移紀錄
with open(SHARED / 'move_duplicates.log', 'w', encoding='utf-8') as f:
    for line in move_log:
        f.write(line + '\n')

print(f'共搬移 {len(duplicates)} 組重複圖片到 {SHARED}') 