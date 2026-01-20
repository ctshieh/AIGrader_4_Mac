# Copyright (c) 2026 [謝忠村/Chung Tsun Shieh]. All Rights Reserved.
# This software is proprietary and confidential.
# Unauthorized copying of this file, via any medium is strictly prohibited.

# services/vision_service.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.01-Vision-Page-Fix
# Description: 
# 1. [Fix] 'align_document' ignores QR/Barcodes to prevent "Black Screen" distortion.
# 2. [Safety] Added a "Sanity Check" - if alignment results in a black/tiny image, return original.
# 3. [Fix] Cutoff logic now respects manual slider (Priority: Barcode > QR > Manual > Default).
# 4. [Logic] Regex-based page detection (Robust for P3, P10, and Marketing QR).

import cv2
import numpy as np
import logging
import re  # [New] 用於正則表達式提取頁碼
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

class VisionService:

    @staticmethod
    def detect_qr_marker(image: np.ndarray) -> Optional[str]:
        """Detects the top-right QR Code."""
        try:
            qcd = cv2.QRCodeDetector()
            retval, decoded_info, points, _ = qcd.detectAndDecodeMulti(image)
            if retval and len(decoded_info) > 0:
                return decoded_info[0]
            return None
        except Exception:
            return None

    @staticmethod
    def detect_linear_barcode_position(image: np.ndarray) -> Optional[int]:
        """
        Attempts to detect the [START_Q] linear barcode.
        Returns the Y-coordinate of the bottom of the barcode if found.
        """
        try:
            if not hasattr(cv2, 'barcode_BarcodeDetector'): return None
            bd = cv2.barcode_BarcodeDetector()
            retval, decoded_info, decoded_type, points = bd.detectAndDecode(image)
            
            if retval and len(decoded_info) > 0:
                for i, info in enumerate(decoded_info):
                    # Check for our specific marker
                    if "START_Q" in info or "[START_Q]" in info:
                        pts = points[i]
                        max_y = np.max(pts[:, 1])
                        return int(max_y)
            return None
        except Exception:
            return None

    @staticmethod
    def get_header_cutoff_y(image: np.ndarray, is_first_page: bool = True, manual_p1_ratio: float = 0.15) -> int:
        img_h = image.shape[0]
        if not is_first_page:
            # 非首頁，只留極少邊界 (0.5%)
            return int(img_h * 0.005) 

        default_cutoff = int(img_h * manual_p1_ratio)

        # 1. [Priority 1] Linear Barcode (Absolute Truth)
        barcode_y = VisionService.detect_linear_barcode_position(image)
        if barcode_y is not None:
            return int(barcode_y + (img_h * 0.015))

        # 2. [Priority 2] QR Code vs Manual Slider
        try:
            qcd = cv2.QRCodeDetector()
            retval, decoded_info, points, _ = qcd.detectAndDecodeMulti(image)
            if retval and len(points) > 0:
                qr_points = points[0]
                max_y = np.max(qr_points[:, 1])
                dynamic_cutoff = int(max_y + (img_h * 0.01))
                
                # [CRITICAL FIX] Use MAX. If manual slider is huge, it overrides auto-detection.
                # 防止誤判：如果 QR Code 在右下角 (System QR)，位置會很低 (>30%)，
                # 此時應忽略該 QR 的位置，改用 Manual Slider 或 Default。
                if dynamic_cutoff < img_h * 0.3:
                    return max(dynamic_cutoff, default_cutoff)
                    
            return default_cutoff
        except Exception:
            return default_cutoff

    @staticmethod
    def extract_header_image(image: np.ndarray, is_first_page: bool = True, manual_p1_ratio: float = 0.15) -> Optional[np.ndarray]:
        cutoff_y = VisionService.get_header_cutoff_y(image, is_first_page, manual_p1_ratio)
        if cutoff_y < 50: return None
        return image[0:cutoff_y, :]

    @staticmethod
    def align_document(image: np.ndarray) -> np.ndarray:
        """
        Aligns document using 4-corner detection.
        Includes safety mechanisms to prevent black screens caused by QR interference.
        """
        if len(image.shape) == 3: gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else: gray = image
        
        orig_h, orig_w = image.shape[:2]
        
        # --- Step 1: Identify Forbidden Zones (QR/Barcodes) ---
        forbidden_rects = []
        try:
            qcd = cv2.QRCodeDetector()
            retval, _, points, _ = qcd.detectAndDecodeMulti(image)
            if retval and len(points) > 0:
                for pts in points:
                    pts = pts.astype(int)
                    x, y, w, h = cv2.boundingRect(pts)
                    forbidden_rects.append((x-10, y-10, w+20, h+20))
        except: pass

        try:
            if hasattr(cv2, 'barcode_BarcodeDetector'):
                bd = cv2.barcode_BarcodeDetector()
                retval, _, _, points = bd.detectAndDecode(image)
                if retval and len(points) > 0:
                    for pts in points:
                        pts = pts.astype(int)
                        x, y, w, h = cv2.boundingRect(pts)
                        forbidden_rects.append((x-10, y-10, w+20, h+20))
        except: pass

        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        potential_markers = []
        img_area = orig_w * orig_h
        
        for cnt in contours:
            area = cv2.contourArea(cnt)
            # Filter 1: Size (Too small = noise, Too big = page border)
            if area < img_area * 0.0005 or area > img_area * 0.05: continue
            
            # Filter 2: Forbidden Zones (The Fix!)
            x, y, w, h = cv2.boundingRect(cnt)
            cx, cy = x + w//2, y + h//2
            is_interference = False
            for (fx, fy, fw, fh) in forbidden_rects:
                if fx <= cx <= fx+fw and fy <= cy <= fy+fh:
                    is_interference = True
                    break
            if is_interference: continue

            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)
            if len(approx) == 4: potential_markers.append((area, approx))
        
        # If we can't find 4 markers, return original (Don't force it!)
        if len(potential_markers) < 4: 
            return image
        
        potential_markers.sort(key=lambda x: x[0], reverse=True)
        best_4_markers = [x[1] for x in potential_markers[:4]]
        
        centers = []
        for marker in best_4_markers:
            M = cv2.moments(marker)
            if M["m00"] != 0: centers.append([int(M["m10"]/M["m00"]), int(M["m01"]/M["m00"])])
            
        if len(centers) != 4: return image
        
        # --- Step 3: Order Points & Warp ---
        centers = np.array(centers)
        sorted_y = centers[np.argsort(centers[:, 1])]
        top_2 = sorted_y[:2]; bottom_2 = sorted_y[2:]
        
        rect = np.zeros((4, 2), dtype="float32")
        rect[0] = top_2[np.argmin(top_2[:, 0])] # TL
        rect[1] = top_2[np.argmax(top_2[:, 0])] # TR
        rect[2] = bottom_2[np.argmax(bottom_2[:, 0])] # BR
        rect[3] = bottom_2[np.argmin(bottom_2[:, 0])] # BL
        
        width, height = 1654, 2339 # Standard A4 at ~200dpi
        dst = np.array([[0, 0], [width-1, 0], [width-1, height-1], [0, height-1]], dtype="float32")
        M = cv2.getPerspectiveTransform(rect, dst)
        aligned_img = cv2.warpPerspective(image, M, (width, height))

        # --- Step 4: Final Sanity Check (Anti-Blackout) ---
        # If the result is suspicious (e.g. mostly black or tiny file size), revert.
        if aligned_img is None or aligned_img.size == 0:
            return image
            
        # Check mean brightness. Valid docs are mostly white (>200). 
        # If mean < 50, it's pitch black or dark grey -> Fail.
        gray_aligned = cv2.cvtColor(aligned_img, cv2.COLOR_BGR2GRAY)
        mean_val = np.mean(gray_aligned)
        if mean_val < 50: 
            return image

        return aligned_img

    @staticmethod
    def _is_inside(boxA, boxB):
        xa, ya, wa, ha = boxA
        xb, yb, wb, hb = boxB
        pad = 5
        return (xa >= xb - pad) and (ya >= yb - pad) and \
               ((xa + wa) <= (xb + wb + pad)) and ((ya + ha) <= (yb + hb + pad))

    @staticmethod
    def _compute_iou(boxA, boxB):
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[0] + boxA[2], boxB[0] + boxB[2])
        yB = min(boxA[1] + boxA[3], boxB[1] + boxB[3])

        interArea = max(0, xB - xA) * max(0, yB - yA)
        boxAArea = boxA[2] * boxA[3]
        boxBArea = boxB[2] * boxB[3]

        iou = interArea / float(boxAArea + boxBArea - interArea + 1e-6)
        return iou

    @staticmethod
    def _find_boxes_with_cutoff(image: np.ndarray, cutoff_y: int) -> List[Tuple[int, int, int, int]]:
        if len(image.shape) == 3: gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else: gray = image
        
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 15, 2)
        kernel = np.ones((3,3), np.uint8)
        dilated = cv2.dilate(thresh, kernel, iterations=1)
        
        contours, _ = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        candidate_boxes = []
        img_h, img_w = image.shape[:2]
        min_w = img_w * 0.10
        min_h = img_h * 0.03
        
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w > min_w and h > min_h:
                if w > img_w * 0.96 and h > img_h * 0.96: continue
                if x > 5 and y > 5 and (x+w) < img_w-5 and (y+h) < img_h-5:
                    if y > cutoff_y:
                        candidate_boxes.append((x, y, w, h))

        if not candidate_boxes: return []

        # Filter 1: IoU
        unique_boxes = []
        candidate_boxes.sort(key=lambda b: b[2]*b[3], reverse=True)
        keep_indices = [True] * len(candidate_boxes)
        for i in range(len(candidate_boxes)):
            if not keep_indices[i]: continue
            for j in range(i + 1, len(candidate_boxes)):
                if not keep_indices[j]: continue
                if VisionService._compute_iou(candidate_boxes[i], candidate_boxes[j]) > 0.8:
                    keep_indices[j] = False
        for i in range(len(candidate_boxes)):
            if keep_indices[i]: unique_boxes.append(candidate_boxes[i])

        # Filter 2: Container
        final_boxes = []
        for i, boxA in enumerate(unique_boxes):
            is_inner_box = False
            for j, boxB in enumerate(unique_boxes):
                if i == j: continue
                if VisionService._is_inside(boxA, boxB):
                     areaA = boxA[2] * boxA[3]
                     areaB = boxB[2] * boxB[3]
                     if areaB > areaA * 1.1:
                        is_inner_box = True; break
            if not is_inner_box: final_boxes.append(boxA)

        # Sort
        boxes_with_center = []
        for b in final_boxes:
            x, y, w, h = b
            cy = y + (h / 2)
            boxes_with_center.append({'box': b, 'cy': cy, 'x': x})
        boxes_with_center.sort(key=lambda k: k['cy'])

        rows = []
        if not boxes_with_center: return []
        current_row = [boxes_with_center[0]]
        row_threshold = 50
        for item in boxes_with_center[1:]:
            prev_cy = current_row[0]['cy']
            curr_cy = item['cy']
            if abs(curr_cy - prev_cy) < row_threshold: current_row.append(item)
            else: rows.append(current_row); current_row = [item]
        rows.append(current_row)

        sorted_boxes = []
        for row in rows:
            row.sort(key=lambda k: k['x'])
            for item in row: sorted_boxes.append(item['box'])
                
        return sorted_boxes

    @staticmethod
    def detect_answer_areas(
        image: np.ndarray, 
        is_first_page: bool = True,
        manual_p1_ratio: float = 0.15
    ) -> Tuple[List[Tuple[int, int, int, int]], int]:
        
        qr_content = VisionService.detect_qr_marker(image)
        
        # [FIX] 使用 Regex 提取頁碼，解決 P3+ 與 P10 誤判問題
        if qr_content:
            # 搜尋 -P數字 或 -Page數字 (例如 -P1, -P2, -P10)
            match = re.search(r'-(?:P|Page)(\d+)', qr_content)
            if match:
                page_num = int(match.group(1))
                # 如果頁碼 > 1，強制設為 False；如果是 1，設為 True
                is_first_page = (page_num == 1)
            # 若沒搜尋到頁碼 (例如行銷 QR)，則維持傳入的 is_first_page 狀態，不做更動
            
        current_cutoff = VisionService.get_header_cutoff_y(image, is_first_page=is_first_page, manual_p1_ratio=manual_p1_ratio)
        if len(image.shape) == 3: gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else: gray = image
        
        boxes = VisionService._find_boxes_with_cutoff(image, current_cutoff)
        if not boxes and current_cutoff > image.shape[0] * 0.05:
            retry_cutoff = int(image.shape[0] * 0.005) 
            boxes_retry = VisionService._find_boxes_with_cutoff(image, retry_cutoff)
            if boxes_retry: return boxes_retry, retry_cutoff

        return boxes, current_cutoff

    @staticmethod
    def draw_debug_boxes(image: np.ndarray, boxes: List[Tuple], labels: List[str] = None, start_q_num: int = 1, actual_cutoff: int = None) -> np.ndarray:
        debug_img = image.copy()
        if actual_cutoff is not None and actual_cutoff > 50:
            cv2.line(debug_img, (0, actual_cutoff), (image.shape[1], actual_cutoff), (0, 0, 255), 3)
            cv2.putText(debug_img, f"Cutoff Y={actual_cutoff}", (20, max(20, actual_cutoff - 10)), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        
        for i, (x, y, w, h) in enumerate(boxes):
            cv2.rectangle(debug_img, (x, y), (x + w, y + h), (0, 0, 255), 3)
            if labels and i < len(labels): label_text = labels[i]
            else: label_text = f"Box {start_q_num + i}"
            (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)
            cv2.rectangle(debug_img, (x, y - 35), (x + tw + 10, y), (0, 0, 255), -1)
            cv2.putText(debug_img, label_text, (x + 5, y - 5), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        return debug_img

    @staticmethod
    def crop_images_by_layout(image: np.ndarray, boxes: List[Tuple], padding: int = 20) -> List[np.ndarray]:
        crops = []
        img_h, img_w = image.shape[:2]
        for (x, y, w, h) in boxes:
            y1 = max(0, y - 150) 
            y2 = min(img_h, y + h + padding)
            x1 = max(0, x - 10)
            x2 = min(img_w, x + w + 10)
            if y2 > y1 and x2 > x1:
                crop = image[y1:y2, x1:x2]
                crops.append(crop)
        return crops

