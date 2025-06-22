import logging
from pathlib import Path
from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)

def read_image(image_path: Path) -> np.ndarray:
    """讀取圖片並轉換為 RGB 格式的 numpy 陣列"""
    try:
        with Image.open(image_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            return np.array(img)
    except Exception as e:
        logger.error(f"讀取圖片失敗 {image_path}: {str(e)}")
        return None

def ensure_output_dir(image_path: Path) -> Path:
    """確保輸出目錄存在"""
    output_dir = image_path.parent / "cropped"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir 