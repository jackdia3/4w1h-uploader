import os
import hashlib
import shutil
from pathlib import Path
from collections import defaultdict

def hash_file(filepath, chunk_size=8192):
    """產生檔案的 SHA256 hash"""
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(chunk_size):
            sha256.update(chunk)
    return sha256.hexdigest()

def find_and_move_duplicates(base_dir):
    base_path = Path(base_dir)
    parent_path = base_path.parent

    hash_map = defaultdict(list)

    # 遍歷所有子檔案
    for file in base_path.rglob("*"):
        if file.is_file():
            file_hash = hash_file(file)
            hash_map[file_hash].append(file)

    # 處理重複項
    for file_list in hash_map.values():
        if len(file_list) > 1:
            # 保留一份原地，其餘搬移到上一層
            for dup_file in file_list[1:]:
                target_path = parent_path / dup_file.name
                # 若目標已存在，加上編號避免覆蓋
                count = 1
                while target_path.exists():
                    target_path = parent_path / f"{dup_file.stem}_{count}{dup_file.suffix}"
                    count += 1
                print(f"Moving {dup_file} → {target_path}")
                shutil.move(str(dup_file), str(target_path))

# 使用
if __name__ == "__main__":
    find_and_move_duplicates(r"D:\OneDrive\Documents\GitHub\berry\WWW_Collection")
