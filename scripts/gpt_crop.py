#!/usr/bin/env python3
"""
GPT 智能裁切圖片處理器
===================

使用 OpenAI 的圖像分析能力來進行智能裁切。
分析圖片內容段落，返回合適的裁切點。

使用範例
--------
$ python gpt_crop.py
"""

import argparse
import base64
import json
import logging
import os
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import cv2
import numpy as np
from openai import OpenAI
from PIL import Image
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# 設定日誌
log_dir = Path("WWW_Collection")
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f"gpt_crop_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def get_image_base64(image_path: str) -> str:
    """將圖片轉換為 base64 字串"""
    try:
        # 讀取圖片
        with Image.open(image_path) as img:
            # 轉換為 RGB 模式（如果是 RGBA）
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            
            # 調整圖片大小，避免超過 API 限制
            max_size = 2048
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = tuple(int(dim * ratio) for dim in img.size)
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # 轉換為 JPEG 格式的 bytes
            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=95)
            buffer.seek(0)
            
            # 轉換為 base64
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as e:
        logging.error(f"圖片轉換失敗: {e}")
        raise

def analyze_image_with_gpt(image_path: str, client: OpenAI) -> Dict[str, Any]:
    """
    使用 GPT 分析圖片內容段落
    
    Args:
        image_path: 圖片路徑
        client: OpenAI 客戶端
    
    Returns:
        包含裁切段落的字典
    """
    try:
        # 將圖片轉為 base64
        base64_image = get_image_base64(image_path)
        
        # 使用 chat.completions.create 分析圖片
        response = client.chat.completions.create(
            model="gpt-4o",  # 使用新的模型名稱
            messages=[
                {
                    "role": "system",
                    "content": """你是圖像內容分析助手。請分析圖片內容，找出自然的段落分界點。
請注意：
1. 找出內容的自然分界點，如標題、段落間距等
2. 避免切到文字或重要內容
3. 必須返回有效的 JSON 格式
4. 每個段落的高度建議在 800-1200 像素之間
5. 直接返回 JSON，不要加任何說明文字"""
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """請分析這張圖，並依內容段落返回 Y 軸裁切座標。
直接返回以下格式的 JSON，不要加任何說明文字：
{
    "segments": [
        {"top": 0, "bottom": 1200},
        {"top": 1200, "bottom": 2400},
        ...
    ]
}"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=500,
            temperature=0.3  # 降低隨機性
        )
        
        # 記錄完整回應
        logging.info(f"GPT 完整回應:\n{response.model_dump_json(indent=2)}")
        
        # 解析回應
        try:
            content = response.choices[0].message.content.strip()
            logging.info(f"GPT 回應內容:\n{content}")
            
            # 移除可能的 markdown 代碼塊標記
            content = content.replace("```json", "").replace("```", "").strip()
            
            # 嘗試找出 JSON 部分
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                logging.info(f"提取的 JSON 字串:\n{json_str}")
                
                result = json.loads(json_str)
                
                # 驗證結果格式
                if not isinstance(result, dict) or "segments" not in result:
                    raise ValueError("回應格式不正確")
                
                segments = result["segments"]
                if not isinstance(segments, list) or not segments:
                    raise ValueError("segments 必須是非空列表")
                
                for seg in segments:
                    if not isinstance(seg, dict) or "top" not in seg or "bottom" not in seg:
                        raise ValueError("segment 格式不正確")
                    if not isinstance(seg["top"], (int, float)) or not isinstance(seg["bottom"], (int, float)):
                        raise ValueError("top/bottom 必須是數字")
                
                logging.info(f"解析後的結果:\n{json.dumps(result, indent=2, ensure_ascii=False)}")
                return result
            else:
                raise ValueError("找不到有效的 JSON 格式")
            
        except (json.JSONDecodeError, ValueError) as e:
            logging.error(f"GPT 回應格式錯誤: {e}")
            logging.error(f"原始回應: {content}")
            return {
                "segments": [],
                "raw_response": content,
                "error": str(e)
            }
            
    except Exception as e:
        logging.error(f"GPT 分析失敗: {e}")
        return {
            "segments": [],
            "error": str(e)
        }

def crop_image(image_path: str, segments: List[Dict[str, int]], output_dir: str) -> List[Dict[str, Any]]:
    """
    根據 GPT 分析結果裁切圖片
    
    Args:
        image_path: 原始圖片路徑
        segments: 裁切段落列表
        output_dir: 輸出目錄
    
    Returns:
        裁切結果列表
    """
    try:
        # 建立輸出目錄
        os.makedirs(output_dir, exist_ok=True)
        
        # 讀取圖片
        img = Image.open(image_path)
        width, height = img.size
        
        # 裁切並儲存
        results = []
        for i, seg in enumerate(segments):
            # 確保座標在有效範圍內
            top = max(0, min(seg["top"], height))
            bottom = max(0, min(seg["bottom"], height))
            
            if bottom <= top:
                continue
                
            # 裁切並儲存
            crop = img.crop((0, top, width, bottom))
            output_path = os.path.join(output_dir, f"{Path(image_path).stem}_crop{i+1}.webp")
            crop.save(output_path, "WEBP", quality=85)
            
            results.append({
                "path": output_path,
                "height": bottom - top,
                "width": width,
                "top": top,
                "bottom": bottom
            })
            
        return results
        
    except Exception as e:
        logging.error(f"裁切失敗: {e}")
        return []

def process_image(image_path: str, client: OpenAI) -> Dict[str, Any]:
    """處理單張圖片"""
    try:
        # 檢查圖片高度
        img = Image.open(image_path)
        if img.height < 1500:  # 降低最小高度限制
            return {
                "success": False,
                "error": "圖片高度不足 800px",
                "path": image_path
            }
        
        # 建立輸出目錄
        output_dir = Path(image_path).parent / "cropped"
        
        # 分析圖片
        analysis = analyze_image_with_gpt(image_path, client)
        segments = analysis.get("segments", [])
        
        # 如果 GPT 分析失敗，直接返回錯誤
        if not segments:
            return {
                "success": False,
                "error": "GPT 分析失敗",
                "path": image_path,
                "gpt_response": analysis.get("raw_response", "")
            }
        
        # 裁切圖片
        results = crop_image(image_path, segments, str(output_dir))
        if not results:
            return {
                "success": False,
                "error": "裁切失敗",
                "path": image_path
            }
        
        return {
            "success": True,
            "path": image_path,
            "crops": results
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "path": image_path
        }

def main():
    # 初始化 OpenAI 客戶端
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    if not client.api_key:
        logging.error("未設定 OpenAI API 金鑰")
        return
    
    # 獲取所有圖片
    base_dir = Path("WWW_Collection")
    image_paths = []
    for ext in [".jpg", ".jpeg", ".png"]:
        image_paths.extend(base_dir.rglob(f"*{ext}"))
    
    # 過濾掉 cropped 目錄下的圖片
    image_paths = [p for p in image_paths if "cropped" not in p.parts]
    
    # 處理結果
    results = []
    failed = []
    
    try:
        # 依序處理每張圖片
        total = len(image_paths)
        for i, image_path in enumerate(image_paths, 1):
            logging.info(f"\n處理進度: {i}/{total} ({i/total*100:.1f}%)")
            logging.info(f"正在處理: {image_path}")
            
            result = process_image(str(image_path), client)
            if result["success"]:
                results.append(result)
                logging.info(f"成功處理: {result['path']}")
                for crop in result["crops"]:
                    logging.info(f"  - 裁切片: {crop['height']}x{crop['width']} @ {crop['path']}")
            else:
                failed.append(result)
                logging.error(f"處理失敗: {result['path']} - {result['error']}")
                if "gpt_response" in result:
                    logging.error(f"GPT 回應: {result['gpt_response']}")
            
            # 每處理完一張圖片就儲存一次結果
            meta_file = base_dir / "gpt_crop_meta.json"
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump({
                    "success": results,
                    "failed": failed,
                    "progress": {
                        "current": i,
                        "total": total,
                        "percentage": i/total*100
                    }
                }, f, ensure_ascii=False, indent=2)
    
    except KeyboardInterrupt:
        logging.warning("\n使用者中斷處理")
    except Exception as e:
        logging.error(f"處理過程發生錯誤: {e}")
    finally:
        # 輸出統計
        logging.info(f"\n處理完成:")
        logging.info(f"- 成功: {len(results)} 張")
        logging.info(f"- 失敗: {len(failed)} 張")
        logging.info(f"- 結果已儲存至: {meta_file}")
        
        if failed:
            logging.info("\n失敗的圖片:")
            for f in failed:
                logging.info(f"- {f['path']}: {f['error']}")
                if "gpt_response" in f:
                    logging.info(f"  GPT 回應: {f['gpt_response']}")

if __name__ == "__main__":
    main() 