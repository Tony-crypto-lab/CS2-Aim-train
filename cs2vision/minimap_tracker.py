from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .models import DetectionResult
from .utils import clamp


class MinimapTracker:
    def __init__(self, template_path: Path | None = None, logger: Any | None = None) -> None:
        self.logger = logger
        self.template_path = template_path
        self.template = None
        if template_path and template_path.exists():
            self.template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)

    def detect(self, minimap_bgr: np.ndarray) -> DetectionResult:
        if minimap_bgr is None or minimap_bgr.size == 0:
            return DetectionResult(found=False)

        color_result = self._detect_by_color(minimap_bgr)
        if color_result.found and color_result.confidence >= 0.35:
            return color_result

        template_result = self._detect_by_template(minimap_bgr)
        if template_result.found:
            return template_result

        return color_result if color_result.found else DetectionResult(found=False)

    def _detect_by_color(self, img: np.ndarray) -> DetectionResult:
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        # 适配常见雷达箭头高亮色（可在配置中扩展）
        lower = np.array([30, 80, 100], dtype=np.uint8)
        upper = np.array([95, 255, 255], dtype=np.uint8)
        mask = cv2.inRange(hsv, lower, upper)
        mask = cv2.medianBlur(mask, 5)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return DetectionResult(found=False)

        candidates = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < 4 or area > (img.shape[0] * img.shape[1]) * 0.2:
                continue
            x, y, w, h = cv2.boundingRect(c)
            aspect = w / max(h, 1)
            if 0.35 <= aspect <= 2.8:
                candidates.append((area, c))

        if not candidates:
            return DetectionResult(found=False)

        area, best = max(candidates, key=lambda t: t[0])
        m = cv2.moments(best)
        if m["m00"] == 0:
            return DetectionResult(found=False)
        cx = m["m10"] / m["m00"]
        cy = m["m01"] / m["m00"]

        heading = self._estimate_heading(best)
        conf = clamp(area / 60.0, 0.2, 0.85)
        return DetectionResult(found=True, x=cx, y=cy, heading=heading, confidence=conf, method="color")

    def _estimate_heading(self, contour: np.ndarray) -> float | None:
        try:
            if len(contour) < 5:
                return None
            (cx, cy), (major, minor), angle = cv2.fitEllipse(contour)
            _ = (cx, cy, major, minor)
            return float(angle)
        except Exception:
            return None

    def _detect_by_template(self, img: np.ndarray) -> DetectionResult:
        if self.template is None:
            return DetectionResult(found=False)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        t_h, t_w = self.template.shape[:2]
        if gray.shape[0] < t_h or gray.shape[1] < t_w:
            return DetectionResult(found=False)
        res = cv2.matchTemplate(gray, self.template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val < 0.45:
            return DetectionResult(found=False)
        x = max_loc[0] + t_w / 2
        y = max_loc[1] + t_h / 2
        return DetectionResult(found=True, x=x, y=y, heading=None, confidence=float(max_val), method="template")
