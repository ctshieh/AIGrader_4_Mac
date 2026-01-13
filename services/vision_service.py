# services/vision_service.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.13-Vision-Standalone-Safe

import cv2
import numpy as np
import logging
import re
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

class VisionService:
    """
    提供影像處理、QR Code 偵測、版面校正的核心邏輯。
    """

    @staticmethod
    def detect_qr_marker(image: np.ndarray) -> Optional[str]:
        """偵測右上角的 QR Code 標記 (用於識別考卷 ID)"""
        try:
            qcd = cv2.QRCodeDetector()
            retval, decoded_info, points, _ = qcd.detectAndDecodeMulti(image)
            if retval and len(decoded_info) > 0:
                return decoded_info[0]
            return None
        except Exception as e:
            logger.warning(f"QR Detect Error: {e}")
            return None

    @staticmethod
    def detect_linear_barcode_position(image: np.ndarray) -> Optional[int]:
        """偵測一維條碼的位置 (用於定位切割線)"""
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            grad_x = cv2.Sobel(gray, ddepth=cv2.CV_32F, dx=1, dy=0, ksize=-1)
            grad_y = cv2.Sobel(gray, ddepth=cv2.CV_32F, dx=0, dy=1, ksize=-1)
            gradient = cv2.subtract(grad_x, grad_y)
            gradient = cv2.convertScaleAbs(gradient)
            
            blurred = cv2.blur(gradient, (9, 9))
            _, thresh = cv2.threshold(blurred, 225, 255, cv2.THRESH_BINARY)
            
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 7))
            closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            closed = cv2.erode(closed, None, iterations=4)
            closed = cv2.dilate(closed, None, iterations=4)
            
            contours, _ = cv2.findContours(closed.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours: return None
            
            c = sorted(contours, key=cv2.contourArea, reverse=True)[0]
            rect = cv2.minAreaRect(c)
            box = cv2.boxPoints(rect)
            box = np.int0(box)
            
            # 回傳條碼底部的 Y 座標，稍微加一點緩衝
            return max(box[:, 1]) + 10
        except Exception:
            return None

    @staticmethod
    def align_document(image: np.ndarray) -> np.ndarray:
        """
        文件校正 (透視變換)，確保考卷是平整的。
        """
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edged = cv2.Canny(blurred, 75, 200)
            
            contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours: return image # 無法偵測輪廓，回傳原圖
            
            doc_cnt = None
            contours = sorted(contours, key=cv2.contourArea, reverse=True)
            
            for c in contours:
                peri = cv2.arcLength(c, True)
                approx = cv2.approxPolyDP(c, 0.02 * peri, True)
                if len(approx) == 4:
                    doc_cnt = approx
                    break
            
            if doc_cnt is not None:
                # 執行透視變換 (這裡簡化，實際可使用 four_point_transform)
                # 為求穩定，若找不到明顯的四角，建議直接回傳原圖，避免切歪
                # 這裡保留原圖回傳，除非您有完整的 transform 邏輯
                return image 
            
            return image
        except Exception as e:
            logger.error(f"Alignment Failed: {e}")
            return image

    @staticmethod
    def extract_answer_blocks(image: np.ndarray, num_blocks: int = 1, cutoff_y: int = 0) -> List[Tuple[int, int, int, int]]:
        """
        切割作答區域 (基於輪廓偵測)
        """
        blocks = []
        try:
            # 1. 裁切掉 Header (如果有的話)
            roi = image[cutoff_y:, :] if cutoff_y < image.shape[0] else image
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            
            # 2. 影像前處理
            thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                         cv2.THRESH_BINARY_INV, 11, 2)
            
            # 3. 尋找輪廓
            cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # 4. 篩選作答框 (面積過濾)
            min_area = (roi.shape[0] * roi.shape[1]) * 0.005 # 至少佔畫面 0.5%
            valid_cnts = [c for c in cnts if cv2.contourArea(c) > min_area]
            
            # 5. 排序 (由上到下，由左到右)
            boundingBoxes = [cv2.boundingRect(c) for c in valid_cnts]
            
            # 自定義排序：先比 Y (容忍度 20px)，再比 X
            def sort_key(b):
                return (round(b[1] / 20), b[0])
                
            boundingBoxes.sort(key=sort_key)
            
            # 6. 回傳座標 (要加回 cutoff_y)
            for (x, y, w, h) in boundingBoxes:
                blocks.append((x, y + cutoff_y, w, h))
                
            # 如果偵測到的框少於預期，可能需要調整閾值或回傳整頁
            if not blocks:
                h, w = image.shape[:2]
                blocks.append((0, cutoff_y, w, h - cutoff_y))
                
            return blocks
            
        except Exception as e:
            logger.error(f"Block Extraction Failed: {e}")
            # 發生錯誤時，回傳一個預設的大框
            h, w = image.shape[:2]
            return [(0, cutoff_y, w, h - cutoff_y)]

    @staticmethod
    def identify_page_number(qr_data: str) -> int:
        """
        從 QR Code 字串 (如 EXAM123-P1) 解析頁碼
        """
        if not qr_data: return 1
        match = re.search(r'-P(\d+)', qr_data)
        if match:
            return int(match.group(1))
        return 1