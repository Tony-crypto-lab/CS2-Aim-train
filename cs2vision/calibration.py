from __future__ import annotations

from pathlib import Path
from tkinter import messagebox, simpledialog
from typing import Any

import mss
import numpy as np

from .models import MinimapROI
from .roi_locator import select_roi_with_opencv
from .utils import save_json


def run_calibration(config: dict[str, Any], config_path: Path, logger=None) -> dict[str, Any]:
    monitor_index = int(config.get("capture_monitor_index", 1))
    try:
        with mss.mss() as sct:
            mon = sct.monitors[min(max(1, monitor_index), len(sct.monitors) - 1)]
            frame = np.array(sct.grab(mon))[:, :, :3]
        roi = select_roi_with_opencv(frame, "请选择小地图 ROI")
        if roi is None:
            messagebox.showwarning("Calibration", "未选择 ROI，保持原配置")
            return config

        map_name = simpledialog.askstring("Map", "输入地图名", initialvalue=config.get("current_map", "de_mirage")) or "de_mirage"
        side = simpledialog.askstring("Side", "输入阵营 (T/CT)", initialvalue=config.get("current_side", "T")) or "T"

        config["minimap_roi"] = roi.to_dict()
        config["current_map"] = map_name
        config["current_side"] = side.upper()
        save_json(config_path, config)
        messagebox.showinfo("Calibration", "校准完成并保存")
        return config
    except Exception as exc:
        if logger:
            logger.exception("Calibration failed: %s", exc)
        messagebox.showerror("Calibration", f"校准失败: {exc}")
        return config


def map_to_reference(x: float, y: float, roi: MinimapROI, ref_shape: tuple[int, int]) -> tuple[float, float]:
    ref_w, ref_h = ref_shape
    rx = (x / max(roi.w, 1)) * ref_w
    ry = (y / max(roi.h, 1)) * ref_h
    return rx, ry
