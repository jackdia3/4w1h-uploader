import os
import json
from pathlib import Path
import logging
import cv2
import numpy as np
import re
from PIL import Image

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 設定基礎路徑
BASE_DIR = Path(__file__).parent.parent
PRODUCTS_DIR = BASE_DIR / "products"
CROPPED_OUTPUT_DIR = BASE_DIR / "cropped"

class NumpyEncoder(json.JSONEncoder):
    """處理 numpy 類型的 JSON 編碼器"""
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        return super(NumpyEncoder, self).default(obj)

class ImageAnalyzer:
    def __init__(self):
        # 支援的圖片格式
        self.supported_formats = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
        
    def is_supported_image(self, filename):
        """檢查是否為支援的圖片格式"""
        return any(filename.lower().endswith(fmt) for fmt in self.supported_formats)
        
    def is_combined_image(self, filename):
        """檢查是否為組合圖片"""
        # 檢查檔名是否符合組合圖片的命名規則
        pattern = r'F\d{4}_[A-Za-z-]+_\d{2}\.jpg$'
        return bool(re.match(pattern, filename))

    def read_image(self, image_path):
        """讀取圖片，支援多種格式"""
        try:
            # 使用 PIL 讀取圖片
            with Image.open(image_path) as img:
                # 轉換為 RGB 模式
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                # 轉換為 numpy array
                return np.array(img)
        except Exception as e:
            logger.error(f"讀取圖片失敗 {image_path}: {str(e)}")
            return None

    def detect_content_regions(self, img):
        """檢測圖片中的內容區域"""
        try:
            # 轉換為灰度圖
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            
            # 使用自適應閾值處理
            binary = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY_INV, 11, 2
            )
            
            # 使用形態學操作改善邊緣
            kernel = np.ones((3,3), np.uint8)
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            
            # 尋找輪廓
            contours, _ = cv2.findContours(
                binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            
            return contours
        except Exception as e:
            logger.error(f"檢測內容區域失敗: {str(e)}")
            return []

    def analyze_region_features(self, img, contour):
        """分析區域特徵"""
        try:
            x, y, w, h = cv2.boundingRect(contour)
            roi = img[y:y+h, x:x+w]
            
            # 計算區域特徵
            area = cv2.contourArea(contour)
            aspect_ratio = w / h if h > 0 else 0
            
            # 計算區域的顏色特徵
            if roi.size > 0:
                mean_color = cv2.mean(roi)[:3]
                std_color = np.std(roi, axis=(0,1))[:3]
            else:
                mean_color = (0, 0, 0)
                std_color = (0, 0, 0)
            
            # 計算區域的邊緣強度
            if roi.size > 0:
                edges = cv2.Canny(roi, 100, 200)
                edge_density = np.sum(edges > 0) / (w * h)
            else:
                edge_density = 0
            
            return {
                "position": {
                    "x": int(x),
                    "y": int(y),
                    "width": int(w),
                    "height": int(h)
                },
                "features": {
                    "area": float(area),
                    "aspect_ratio": round(float(aspect_ratio), 2),
                    "center": [int(x + w//2), int(y + h//2)],
                    "area_ratio": round(float(area) / (img.shape[0] * img.shape[1]), 3),
                    "mean_color": [float(c) for c in mean_color],
                    "color_std": [float(c) for c in std_color],
                    "edge_density": round(float(edge_density), 3)
                }
            }
        except Exception as e:
            logger.error(f"分析區域特徵失敗: {str(e)}")
            return None

    def find_cut_points(self, img, regions):
        """尋找合適的裁切點"""
        try:
            height, width = img.shape[:2]
            cut_points = []
            
            # 計算區域間距
            region_gaps = []
            sorted_regions = sorted(regions, key=lambda x: x["position"]["y"])
            
            for i in range(len(sorted_regions)-1):
                current = sorted_regions[i]
                next_region = sorted_regions[i+1]
                gap = next_region["position"]["y"] - (current["position"]["y"] + current["position"]["height"])
                region_gaps.append({
                    "gap": gap,
                    "y": current["position"]["y"] + current["position"]["height"],
                    "confidence": 0.0
                })
            
            # 分析區域特徵
            for region in regions:
                features = region["features"]
                # 計算區域的視覺特徵
                is_product = features["aspect_ratio"] > 0.7 and features["aspect_ratio"] < 1.3
                is_detail = features["edge_density"] > 0.15
                is_text = features["area_ratio"] < 0.15 and features["aspect_ratio"] > 2.5
                
                # 根據特徵分類區域
                if is_product:
                    region["type"] = "product"
                elif is_detail:
                    region["type"] = "detail"
                elif is_text:
                    region["type"] = "text"
                else:
                    # 根據位置和大小進一步判斷
                    if region["position"]["y"] < height * 0.3:
                        region["type"] = "header"
                    elif region["position"]["y"] > height * 0.7:
                        region["type"] = "footer"
                    else:
                        region["type"] = "content"
            
            # 根據區域類型和間距判斷裁切點
            for i, gap in enumerate(region_gaps):
                current_region = sorted_regions[i]
                next_region = sorted_regions[i+1]
                
                # 計算置信度
                confidence = 0.0
                
                # 根據區域類型判斷
                if current_region["type"] != next_region["type"]:
                    confidence += 0.4
                    # 特定類型組合的額外加分
                    if (current_region["type"] == "product" and next_region["type"] == "detail") or \
                       (current_region["type"] == "detail" and next_region["type"] == "text"):
                        confidence += 0.2
                
                # 根據間距判斷
                if gap["gap"] > height * 0.05:  # 間距大於圖片高度的 5%
                    confidence += 0.3
                
                # 根據區域大小判斷
                if abs(current_region["features"]["area"] - next_region["features"]["area"]) > height * width * 0.05:
                    confidence += 0.3
                
                if confidence > 0.6:  # 提高置信度閾值
                    cut_points.append({
                        "y": int(gap["y"]),
                        "confidence": round(confidence, 2),
                        "type": f"{current_region['type']}_to_{next_region['type']}"
                    })
            
            # 根據區域類型重新排序裁切點
            cut_points.sort(key=lambda x: x["y"])
            
            return cut_points
        except Exception as e:
            logger.error(f"尋找裁切點失敗: {str(e)}")
            return []

    def analyze_image_content(self, image_path):
        """分析圖片內容，識別可能的裁切區域"""
        try:
            # 讀取圖片
            img = self.read_image(image_path)
            if img is None:
                return None

            # 檢測內容區域
            contours = self.detect_content_regions(img)
            
            if not contours:
                return None
                
            # 過濾小輪廓
            min_area = img.shape[0] * img.shape[1] * 0.05  # 最小面積為圖片的 5%
            valid_contours = [cnt for cnt in contours if cv2.contourArea(cnt) > min_area]
            
            if not valid_contours:
                return None
                
            # 分析每個區域
            regions = []
            for i, cnt in enumerate(valid_contours):
                region_analysis = self.analyze_region_features(img, cnt)
                if region_analysis:
                    region_analysis["index"] = i + 1
                    regions.append(region_analysis)
            
            # 找出裁切點
            cut_points = self.find_cut_points(img, regions)
            
            # 判斷是否為組合圖片
            is_combined = len(regions) > 1 and any(cp["confidence"] > 0.5 for cp in cut_points)
            
            return {
                "image_size": {
                    "width": int(img.shape[1]),
                    "height": int(img.shape[0])
                },
                "regions": regions,
                "cut_points": cut_points,
                "is_combined": is_combined
            }
            
        except Exception as e:
            logger.error(f"分析圖片內容失敗: {str(e)}")
            return None

    def analyze_image(self, image_path):
        """分析圖片基本資訊和內容"""
        try:
            with Image.open(image_path) as img:
                analysis = {
                    "filename": os.path.basename(image_path),
                    "format": img.format,
                    "mode": img.mode,
                    "size": [int(s) for s in img.size],
                    "width": int(img.width),
                    "height": int(img.height),
                    "aspect_ratio": round(float(img.width) / float(img.height), 2)
                }
                
                # 分析圖片內容
                content_analysis = self.analyze_image_content(image_path)
                if content_analysis:
                    analysis["content_analysis"] = content_analysis
                    analysis["is_combined"] = content_analysis["is_combined"]
                else:
                    analysis["is_combined"] = False
                
                return analysis
        except Exception as e:
            logger.error(f"分析圖片失敗 {image_path}: {str(e)}")
            return None

def ensure_output_dir(image_path):
    # 在原圖所在目錄下建立 cropped 子資料夾
    output_dir = image_path.parent / "cropped"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

def read_image(image_path):
    try:
        with Image.open(image_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            return np.array(img)
    except Exception as e:
        logger.error(f"讀取圖片失敗 {image_path}: {str(e)}")
        return None

def detect_cut_lines_by_projection(gray_image, threshold=10, min_gap_height=30):
    height, width = gray_image.shape
    projection = np.sum(255 - gray_image, axis=1)
    cut_lines = []
    in_blank = False
    start = 0

    for y in range(height):
        if projection[y] < threshold:
            if not in_blank:
                in_blank = True
                start = y
        else:
            if in_blank:
                in_blank = False
                if y - start >= min_gap_height:
                    cut_lines.append((start + y) // 2)
    logger.info(f"偵測到裁切點: {cut_lines}")
    return cut_lines

def crop_image_by_lines(img, lines, image_path):
    cropped_images = []
    output_dir = ensure_output_dir(image_path)
    lines = [0] + lines + [img.shape[0]]
    for i in range(len(lines) - 1):
        cropped = img[lines[i]:lines[i+1], :, :]
        filename = f"{image_path.stem}_{i+1:02d}.jpg"
        filepath = output_dir / filename
        Image.fromarray(cropped).save(filepath)
        logger.info(f"已儲存裁切圖 {filepath}，尺寸: {cropped.shape}")
        cropped_images.append(str(filepath))
    return cropped_images

def analyze_and_crop_combined_image(image_path, threshold=10, min_gap_height=30):
    img = read_image(image_path)
    if img is None:
        logger.warning(f"無法處理圖片 {image_path}，跳過。")
        return []

    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    cut_lines = detect_cut_lines_by_projection(gray, threshold, min_gap_height)
    if not cut_lines:
        logger.info(f"圖片 {image_path} 未檢測到裁切點，跳過。")
        return []
        
    cropped_files = crop_image_by_lines(img, cut_lines, image_path)
    logger.info(f"完成裁切 {len(cropped_files)} 張圖片於 {image_path.parent}/cropped")
    return cropped_files

def process_product_images(product_dir):
    """處理單個產品目錄下的所有圖片"""
    analyzer = ImageAnalyzer()
    product_analysis = {
        "product_id": os.path.basename(product_dir),
        "images": []
    }
    
    # 遍歷目錄及其子目錄中的所有檔案
    for root, dirs, files in os.walk(product_dir):
        for filename in files:
            if analyzer.is_supported_image(filename):
                image_path = os.path.join(root, filename)
                # 計算相對路徑
                rel_path = os.path.relpath(image_path, product_dir)
                analysis = analyzer.analyze_image(image_path)
                if analysis:
                    # 添加相對路徑資訊
                    analysis["relative_path"] = rel_path
                    product_analysis["images"].append(analysis)
                    logger.info(f"已分析圖片: {rel_path}")
    
    return product_analysis

def process_www_collection():
    """處理 WWW_Collection 目錄下的所有產品圖片"""
    base_dir = "4w1h-min/products/WWW_Collection"
    
    # 遍歷所有產品目錄
    for product_dir in os.listdir(base_dir):
        if product_dir.startswith("product_"):
            product_path = os.path.join(base_dir, product_dir)
            if os.path.isdir(product_path):
                logger.info(f"處理產品目錄: {product_dir}")
                
                # 分析產品目錄中的所有圖片
                product_analysis = process_product_images(product_path)
                
                # 保存分析結果
                analysis_file = os.path.join(product_path, "image_analysis.json")
                with open(analysis_file, 'w', encoding='utf-8') as f:
                    json.dump(product_analysis, f, ensure_ascii=False, indent=2, cls=NumpyEncoder)
                logger.info(f"分析結果已保存: {analysis_file}")

def main():
    # 處理所有產品目錄
    for product_dir in PRODUCTS_DIR.iterdir():
        if product_dir.is_dir():
            logger.info(f"處理產品目錄: {product_dir.name}")
            # 搜尋所有 jpg 圖片，包括子目錄
            for image_path in product_dir.glob("**/*.jpg"):
                logger.info(f"處理圖片: {image_path}")
                analyze_and_crop_combined_image(image_path)

if __name__ == "__main__":
    main() 