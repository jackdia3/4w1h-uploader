import argparse
import cv2
import layoutparser as lp
import os
from pathlib import Path
import torch
import logging
import numpy as np
import time
import sys
from typing import List, Dict, Any, Optional, Tuple

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 驗證 GPU
if not torch.cuda.is_available():
    logging.error("CUDA 未啟用！請確認 PyTorch 安裝正確版本")
    logging.error("建議執行：pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118")
    logging.error("然後：pip install detectron2 -f https://dl.fbaipublicfiles.com/detectron2/wheels/cu118/torch2.2/index.html")
    exit(1)

logging.info(f"使用 GPU: {torch.cuda.get_device_name(0)}")

def debug_print(msg: str):
    """立即輸出調試訊息"""
    print(msg, flush=True)
    sys.stdout.flush()

class LayoutAnalyzer:
    def __init__(self, model_name: str = "lp://PubLayNet/mask_rcnn_R_50_FPN_3x/config"):
        """初始化 Layout 分析器"""
        self.model_name = model_name
        self.model = self._load_model(model_name)
        self.target_types = {"Text", "Title", "List", "Table", "Figure"}
        
        # 圖片處理參數（根據 Detectron2 建議）
        self.max_long = 2000   # 最長邊上限（考慮 VRAM）
        self.min_short = 800   # 最短邊下限（避免 anchor 不覆蓋）
    
    def _load_model(self, model_name: str) -> Optional[lp.AutoLayoutModel]:
        """載入 layout 分析模型"""
        try:
            logging.info("開始載入模型...")
            logging.info(f"使用模型: {model_name}")
            
            # 檢查 CUDA 是否可用
            if not torch.cuda.is_available():
                logging.error("CUDA 不可用，請確認 GPU 驅動程式是否正確安裝")
                return None
            
            # 檢查 GPU 記憶體
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
            logging.info(f"GPU 記憶體: {gpu_memory:.1f} GB")
            
            # 檢查 layoutparser 版本
            import layoutparser
            logging.info(f"layoutparser 版本: {layoutparser.__version__}")
            
            # 檢查權重檔案
            model_path = os.path.expanduser("~/.cache/layoutparser/publaynet_R50.pth")
            if not Path(model_path).exists():
                logging.error(f"權重檔案不存在: {model_path}")
                logging.error("請先下載權重檔案：")
                logging.error("https://huggingface.co/layoutparser/detectron2/resolve/main/PubLayNet/mask_rcnn_R_50_FPN_3x/model_final.pth")
                return None
            
            # 載入模型
            model = lp.Detectron2LayoutModel(
                config_path=model_name,  # 只決定網路結構 & label_map
                model_path=model_path,   # 手動下載的權重檔案
                device="cuda",
                extra_config=[
                    "MODEL.ROI_HEADS.SCORE_THRESH_TEST", 0.05,  # 降低閾值以提高召回率
                    "MODEL.ROI_HEADS.NMS_THRESH_TEST", 0.5,    # 調整 NMS
                    "MODEL.RPN.PRE_NMS_TOPK_TEST", 1000,       # 增加候選框
                    "MODEL.RPN.POST_NMS_TOPK_TEST", 1000,      # 增加候選框
                    "MODEL.RPN.MIN_SIZE", 8,                   # 降低最小尺寸
                    "MODEL.RPN.ANCHOR_SCALES", [4, 8, 16, 32, 64]  # 調整錨點尺寸
                ]
            )
            
            # 驗證模型是否正確載入
            if not hasattr(model, 'model') or model.model is None:
                logging.error("模型載入失敗：model.model 為 None")
                return None
            
            logging.info("模型載入成功")
            return model
            
        except Exception as e:
            logging.error(f"模型載入失敗: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return None
    
    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """預處理圖片（確保尺寸在安全範圍內）"""
        h, w = image.shape[:2]
        logging.info(f"原始圖片尺寸: {image.shape}")
        
        # 計算安全縮放比例
        # 1. 先確保最短邊 >= 800px
        scale = self.min_short / min(h, w)
        # 2. 如果最長邊超過 2000px，取較小的縮放比例
        if max(h, w) * scale > self.max_long:
            scale = self.max_long / max(h, w)
        
        if scale != 1:
            new_w = round(w * scale)
            new_h = round(h * scale)
            image = cv2.resize(image, (new_w, new_h), cv2.INTER_AREA)
            logging.info(f"縮放比例: {scale:.3f}")
            logging.info(f"resize  →  {image.shape}")
        
        # 確保圖片格式正確
        if image.dtype != np.uint8:
            image = (image * 255).astype(np.uint8)
            logging.info(f"轉換圖片格式: {image.dtype}")
        
        # 確保色彩空間正確
        if image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
            logging.info("轉換 BGRA 到 RGB")
        elif image.shape[2] == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            logging.info("轉換 BGR 到 RGB")
            
        return image
    
    def analyze_image(self, image: np.ndarray, debug: bool = False) -> Optional[lp.Layout]:
        """分析圖片並返回結果"""
        logging.info("開始分析圖片...")
        
        # 檢查模型
        if self.model is None:
            logging.error("模型未正確載入")
            return None
        
        if not hasattr(self.model, 'model') or self.model.model is None:
            logging.error("模型物件無效")
            return None
        
        try:
            best_layout = None
            max_blocks = 0
            
            # 先嘗試原始方向
            try:
                debug_print(f"[DEBUG] 準備呼叫 detect，原始方向")
                debug_print(f"[DEBUG] 圖片尺寸: {image.shape}")
                debug_print(f"[DEBUG] 圖片類型: {image.dtype}")
                
                # 第一次嘗試
                layout = self.model.detect(image)
                debug_print(f"[DEBUG] 第一次檢測結果: {len(layout)} 個框")
                
                # 如果沒有框，降低閾值再試一次
                if len(layout) == 0:
                    debug_print("[DEBUG] 第一次檢測無框，降低閾值重試")
                    self.model.model.roi_heads.score_thresh = 0.05
                    layout = self.model.detect(image)
                    debug_print(f"[DEBUG] 降低閾值後檢測結果: {len(layout)} 個框")
                    # 恢復原始閾值
                    self.model.model.roi_heads.score_thresh = 0.1
                
                debug_print(f"[DEBUG] 原始方向 layout=")
                debug_print(str(layout))
                
                if debug:
                    viz = lp.draw_box(image, layout, box_width=3)
                    debug_path = "debug_layout_original.jpg"
                    cv2.imwrite(debug_path, cv2.cvtColor(viz, cv2.COLOR_RGB2BGR))
                    logging.info(f"已儲存調試圖片: {debug_path}")
                
                if len(layout) > max_blocks:
                    max_blocks = len(layout)
                    best_layout = layout
                    
            except Exception as e:
                debug_print(f"[DEBUG] 原始方向分析失敗: {str(e)}")
                import traceback
                debug_print(f"[DEBUG] 錯誤堆疊: {traceback.format_exc()}")
                logging.error(f"原始方向分析失敗: {str(e)}")
            
            # 如果原始方向失敗，嘗試旋轉
            if best_layout is None:
                for rot in [cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_180, cv2.ROTATE_90_COUNTERCLOCKWISE]:
                    try:
                        img2 = cv2.rotate(image, rot)
                        debug_print(f"[DEBUG] 準備呼叫 detect，旋轉 {rot}")
                        debug_print(f"[DEBUG] 圖片尺寸: {img2.shape}")
                        debug_print(f"[DEBUG] 圖片類型: {img2.dtype}")
                        
                        # 第一次嘗試
                        layout = self.model.detect(img2)
                        debug_print(f"[DEBUG] 第一次檢測結果: {len(layout)} 個框")
                        
                        # 如果沒有框，降低閾值再試一次
                        if len(layout) == 0:
                            debug_print("[DEBUG] 第一次檢測無框，降低閾值重試")
                            self.model.model.roi_heads.score_thresh = 0.05
                            layout = self.model.detect(img2)
                            debug_print(f"[DEBUG] 降低閾值後檢測結果: {len(layout)} 個框")
                            # 恢復原始閾值
                            self.model.model.roi_heads.score_thresh = 0.1
                        
                        debug_print(f"[DEBUG] 旋轉 {rot} layout=")
                        debug_print(str(layout))
                        
                        if debug:
                            viz = lp.draw_box(img2, layout, box_width=3)
                            debug_path = f"debug_layout_{rot}.jpg"
                            cv2.imwrite(debug_path, cv2.cvtColor(viz, cv2.COLOR_RGB2BGR))
                            logging.info(f"已儲存調試圖片: {debug_path}")
                        
                        if len(layout) > max_blocks:
                            max_blocks = len(layout)
                            best_layout = layout
                            
                    except Exception as e:
                        debug_print(f"[DEBUG] 旋轉 {rot} 分析失敗: {str(e)}")
                        import traceback
                        debug_print(f"[DEBUG] 錯誤堆疊: {traceback.format_exc()}")
                        logging.error(f"旋轉 {rot} 分析失敗: {str(e)}")
                        continue
            
            if best_layout is None:
                logging.error("所有方向都分析失敗")
                return None
                
            logging.info(f"分析完成，找到 {len(best_layout)} 個區塊")
            if debug:
                logging.info(f"檢測到的區塊類型: {set(b.type for b in best_layout)}")
            return best_layout
            
        except Exception as e:
            debug_print(f"[DEBUG] 分析過程發生錯誤: {str(e)}")
            import traceback
            debug_print(f"[DEBUG] 錯誤堆疊: {traceback.format_exc()}")
            logging.error(f"分析過程發生錯誤: {str(e)}")
            logging.error(traceback.format_exc())
            return None
    
    def process_image(self, image_path: Path, output_dir: Optional[Path] = None, debug: bool = False) -> Dict[str, Any]:
        """處理單張圖片"""
        if not image_path.exists():
            logging.error(f"錯誤：找不到圖片 {image_path}")
            return {"success": False, "error": "找不到圖片"}
        
        # 設定輸出目錄
        if output_dir is None:
            output_dir = image_path.parent
        crop_dir = output_dir / "layout_crops"
        crop_dir.mkdir(exist_ok=True)
        
        # 讀取圖片
        logging.info(f"讀取圖片: {image_path}")
        image = cv2.imread(str(image_path))
        if image is None:
            logging.error(f"錯誤：無法讀取圖片 {image_path}")
            return {"success": False, "error": "無法讀取圖片"}
        
        logging.info(f"原始圖片尺寸: {image.shape}")
        
        # 預處理圖片
        image = self.preprocess_image(image)
        logging.info(f"預處理後圖片尺寸: {image.shape}")
        
        # 分析圖片
        layout = self.analyze_image(image, debug)
        if layout is None:
            return {"success": False, "error": "圖片分析失敗"}
        
        if len(layout) == 0:
            logging.warning("未找到任何區塊")
            return {"success": False, "error": "未找到任何區塊"}
        
        # 過濾並排序區塊
        filtered_layout = lp.Layout(sorted(
            [b for b in layout if b.type in self.target_types],
            key=lambda b: b.coordinates[1]
        ))
        
        if len(filtered_layout) == 0:
            logging.warning("過濾後沒有符合的區塊，使用所有區塊")
            filtered_layout = layout
        
        # 生成視覺化結果
        viz = lp.draw_box(image, filtered_layout, box_width=3)
        viz_path = output_dir / f"{image_path.stem}_layout.jpg"
        cv2.imwrite(str(viz_path), cv2.cvtColor(viz, cv2.COLOR_RGB2BGR))
        
        # 裁切並儲存區塊
        crops = []
        for i, block in enumerate(filtered_layout):
            x1, y1, x2, y2 = map(int, block.coordinates)
            cropped = image[y1:y2, x1:x2]
            crop_path = crop_dir / f"{image_path.stem}_crop_{i+1}.webp"
            cv2.imwrite(str(crop_path), cv2.cvtColor(cropped, cv2.COLOR_RGB2BGR))
            crops.append({
                "path": str(crop_path),
                "type": block.type,
                "coordinates": [x1, y1, x2, y2],
                "size": [x2-x1, y2-y1]
            })
            logging.info(f"已裁切儲存: {crop_path} ({x2-x1}x{y2-y1})")
        
        return {
            "success": True,
            "image_path": str(image_path),
            "layout_path": str(viz_path),
            "crops": crops
        }

def main():
    parser = argparse.ArgumentParser(description="Layout 分析工具")
    parser.add_argument("--file", type=str, help="要處理的圖片路徑")
    parser.add_argument("--debug", action="store_true", help="啟用調試模式")
    args = parser.parse_args()
    
    if not args.file:
        parser.print_help()
        return
        
    analyzer = LayoutAnalyzer()
    result = analyzer.process_image(Path(args.file), debug=args.debug)
    
    if result["success"]:
        logging.info(f"處理完成: {result['image_path']}")
        logging.info(f"裁切結果: {len(result['crops'])} 個區塊")
    else:
        logging.error(f"處理失敗: {result.get('error', '未知錯誤')}")

if __name__ == "__main__":
    main()
