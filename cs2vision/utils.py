from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np

APP_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = APP_ROOT / "config"
ASSETS_DIR = APP_ROOT / "assets"
LOG_DIR = APP_ROOT / "logs"

DEFAULT_CONFIG_PATH = CONFIG_DIR / "app_config.json"
DEFAULT_ZONES_PATH = CONFIG_DIR / "zones_mirage.json"
DEFAULT_LINEUPS_PATH = CONFIG_DIR / "lineups_mirage.json"


def ensure_dirs() -> None:
    for p in [CONFIG_DIR, ASSETS_DIR, LOG_DIR]:
        p.mkdir(parents=True, exist_ok=True)


def setup_logging() -> logging.Logger:
    ensure_dirs()
    logger = logging.getLogger("cs2vision")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "runtime.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)
    return logger


def load_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_asset(relative_path: str) -> Path:
    return APP_ROOT / relative_path


def create_placeholder_image(path: Path, text: str, size: tuple[int, int] = (1280, 720)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    img = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    img[:, :] = (20, 20, 20)
    cv2.putText(img, text, (40, size[1] // 2), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 220, 255), 2, cv2.LINE_AA)
    cv2.imwrite(str(path), img)


def ensure_demo_assets() -> None:
    mirage = ASSETS_DIR / "maps" / "de_mirage"
    create_placeholder_image(mirage / "minimap_reference.png", "Mirage Reference Minimap", (512, 512))
    create_placeholder_image(mirage / "lineups" / "standby.png", "Standby", (1280, 720))
    create_placeholder_image(mirage / "lineups" / "t_spawn_window_smoke.png", "T Spawn Window Smoke")
    create_placeholder_image(mirage / "lineups" / "t_spawn_connector_smoke.png", "T Spawn Connector Smoke")
    create_placeholder_image(mirage / "lineups" / "top_mid_cat_smoke.png", "Top Mid Cat Smoke")
    create_placeholder_image(mirage / "lineups" / "a_ramp_jungle_smoke.png", "A Ramp Jungle Smoke")
    create_placeholder_image(mirage / "debug" / "self_icon_template.png", "Self Icon", (36, 36))


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def set_dpi_awareness() -> None:
    """Enable DPI awareness on Windows to avoid partial/top-left captures."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
