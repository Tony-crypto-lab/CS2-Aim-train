from __future__ import annotations

from typing import Any

import cv2

from .models import MinimapROI


def select_roi_with_opencv(frame, window_name: str = "Select Minimap ROI") -> MinimapROI | None:
    try:
        clone = frame.copy()
        rect = cv2.selectROI(window_name, clone, showCrosshair=True, fromCenter=False)
        cv2.destroyWindow(window_name)
        x, y, w, h = [int(v) for v in rect]
        if w <= 0 or h <= 0:
            return None
        return MinimapROI(x=x, y=y, w=w, h=h)
    except Exception:
        return None


def safe_crop(frame, roi: MinimapROI, logger: Any | None = None):
    try:
        h, w = frame.shape[:2]
        x = max(0, min(roi.x, w - 1))
        y = max(0, min(roi.y, h - 1))
        cw = max(1, min(roi.w, w - x))
        ch = max(1, min(roi.h, h - y))
        return frame[y : y + ch, x : x + cw]
    except Exception as exc:
        if logger:
            logger.error("safe_crop failed: %s", exc)
        return None
