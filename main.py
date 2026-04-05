from __future__ import annotations

import queue
import subprocess
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import cv2
import numpy as np
from PIL import Image, ImageTk
from screeninfo import get_monitors

from cs2vision.calibration import map_to_reference, run_calibration
from cs2vision.capture import ScreenCaptureWorker
from cs2vision.debug_overlay import draw_minimap_debug, draw_reference_debug
from cs2vision.lineup_matcher import LineupMatcher
from cs2vision.minimap_tracker import MinimapTracker
from cs2vision.models import MinimapROI, RuntimeState
from cs2vision.output_manager import OutputStateManager, build_output_payload
from cs2vision.roi_locator import safe_crop
from cs2vision.second_screen_window import SecondScreenWindow
from cs2vision.utils import (
    APP_ROOT,
    DEFAULT_CONFIG_PATH,
    DEFAULT_LINEUPS_PATH,
    DEFAULT_ZONES_PATH,
    LOG_DIR,
    ensure_demo_assets,
    load_json,
    save_json,
    setup_logging,
)
from cs2vision.zone_matcher import ZoneMatcher

DEFAULT_APP_CONFIG = {
    "capture_monitor_index": 1,
    "output_monitor_index": 2,
    "output_fullscreen": True,
    "minimap_roi": {"x": 30, "y": 30, "w": 280, "h": 280},
    "current_map": "de_mirage",
    "current_side": "T",
    "debug_enabled": True,
    "fps_limit": 20,
    "detect_interval_ms": 30,
    "zone_stable_frames": 3,
    "lineup_stable_frames": 3,
    "lineup_hold_seconds": 0.8,
    "unknown_timeout_seconds": 1.2,
}


class App:
    def __init__(self) -> None:
        ensure_demo_assets()
        self.logger = setup_logging()

        self.config = load_json(DEFAULT_CONFIG_PATH, DEFAULT_APP_CONFIG)
        if not DEFAULT_CONFIG_PATH.exists():
            save_json(DEFAULT_CONFIG_PATH, self.config)

        self.zones_data = load_json(DEFAULT_ZONES_PATH, {"zones": []})
        self.lineups_data = load_json(DEFAULT_LINEUPS_PATH, {"lineups": []})

        self.runtime = RuntimeState(map_name=self.config.get("current_map", "de_mirage"), side=self.config.get("current_side", "T"))

        self.frame_queue: queue.Queue = queue.Queue(maxsize=2)
        self.ui_queue: queue.Queue = queue.Queue(maxsize=2)
        self.capture_worker: ScreenCaptureWorker | None = None
        self.process_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.started = False

        self.monitors = get_monitors()
        self.second_screen: SecondScreenWindow | None = None

        self.minimap_tracker = MinimapTracker(APP_ROOT / "assets/maps/de_mirage/debug/self_icon_template.png", self.logger)
        self.zone_matcher = ZoneMatcher(self.zones_data.get("zones", []))
        self.lineup_matcher = LineupMatcher(self.lineups_data.get("lineups", []), APP_ROOT)
        self.output_state = OutputStateManager(
            self.config.get("zone_stable_frames", 3),
            self.config.get("lineup_stable_frames", 3),
            self.config.get("lineup_hold_seconds", 0.8),
        )

        self.ref_img = cv2.imread(str(APP_ROOT / "assets/maps/de_mirage/minimap_reference.png"))
        if self.ref_img is None:
            self.ref_img = np.zeros((512, 512, 3), dtype=np.uint8)

        self.root = tk.Tk()
        self.root.title("CS2 Vision Lineup Assistant")
        self.root.geometry("1240x780")

        self._build_ui()
        self._recreate_second_screen()
        self._refresh_ui_loop()

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root)
        top.pack(fill="x", padx=8, pady=6)

        self.status_var = tk.StringVar(value="Paused")
        self.fps_var = tk.StringVar(value="FPS: 0.0")
        self.map_var = tk.StringVar(value=f"Map: {self.runtime.map_name}")
        self.zone_var = tk.StringVar(value="Zone: UNKNOWN")
        self.lineup_var = tk.StringVar(value="Lineup: UNKNOWN")
        self.conf_var = tk.StringVar(value="Confidence: 0.00")

        for var in [self.status_var, self.fps_var, self.map_var, self.zone_var, self.lineup_var, self.conf_var]:
            ttk.Label(top, textvariable=var).pack(side="left", padx=8)

        controls = ttk.Frame(self.root)
        controls.pack(fill="x", padx=8, pady=4)

        ttk.Button(controls, text="Start", command=self.start).pack(side="left", padx=4)
        ttk.Button(controls, text="Pause", command=self.pause).pack(side="left", padx=4)
        ttk.Button(controls, text="Recalibrate", command=self.recalibrate).pack(side="left", padx=4)
        ttk.Button(controls, text="Save Debug Snapshot", command=self.save_debug_snapshot).pack(side="left", padx=4)
        ttk.Button(controls, text="Open Config Folder", command=self.open_config_folder).pack(side="left", padx=4)

        ttk.Label(controls, text="Capture Monitor").pack(side="left", padx=4)
        self.capture_monitor_var = tk.IntVar(value=int(self.config.get("capture_monitor_index", 1)))
        ttk.Combobox(controls, textvariable=self.capture_monitor_var, values=list(range(1, len(self.monitors) + 1)), width=4).pack(side="left")

        ttk.Label(controls, text="Output Monitor").pack(side="left", padx=4)
        self.output_monitor_var = tk.IntVar(value=int(self.config.get("output_monitor_index", 1)))
        ttk.Combobox(controls, textvariable=self.output_monitor_var, values=list(range(1, len(self.monitors) + 1)), width=4).pack(side="left")

        self.debug_enabled_var = tk.BooleanVar(value=bool(self.config.get("debug_enabled", True)))
        ttk.Checkbutton(controls, text="Debug Preview", variable=self.debug_enabled_var).pack(side="left", padx=8)

        self.output_fullscreen_var = tk.BooleanVar(value=bool(self.config.get("output_fullscreen", False)))
        ttk.Checkbutton(controls, text="Output Fullscreen", variable=self.output_fullscreen_var).pack(side="left", padx=8)

        panes = ttk.Frame(self.root)
        panes.pack(fill="both", expand=True, padx=8, pady=6)

        self.minimap_label = ttk.Label(panes)
        self.minimap_label.grid(row=0, column=0, sticky="nsew", padx=4)
        self.reference_label = ttk.Label(panes)
        self.reference_label.grid(row=0, column=1, sticky="nsew", padx=4)

        panes.columnconfigure(0, weight=1)
        panes.columnconfigure(1, weight=1)
        panes.rowconfigure(0, weight=1)

        self.log_text = tk.Text(self.root, height=10)
        self.log_text.pack(fill="x", padx=8, pady=6)

    def log_ui(self, msg: str) -> None:
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")

    def start(self) -> None:
        if self.started:
            return
        self.stop_event.clear()
        self.started = True

        self.config["capture_monitor_index"] = int(self.capture_monitor_var.get())
        self.config["output_monitor_index"] = int(self.output_monitor_var.get())
        self.config["debug_enabled"] = bool(self.debug_enabled_var.get())
        self.config["output_fullscreen"] = bool(self.output_fullscreen_var.get())
        save_json(DEFAULT_CONFIG_PATH, self.config)

        self._recreate_second_screen()

        self.capture_worker = ScreenCaptureWorker(
            output_queue=self.frame_queue,
            monitor_index=self.config.get("capture_monitor_index", 1),
            fps_limit=self.config.get("fps_limit", 10),
            logger=self.logger,
        )
        self.capture_worker.start()
        self.process_thread = threading.Thread(target=self._process_loop, daemon=True)
        self.process_thread.start()
        self.status_var.set("Running")
        self.runtime.status = "running"
        self.log_ui("Capture started")

    def _recreate_second_screen(self) -> None:
        try:
            if self.second_screen:
                self.second_screen.stop()
        except Exception:
            pass
        output_idx = min(max(1, int(self.config.get("output_monitor_index", 1))), len(self.monitors))
        self.second_screen = SecondScreenWindow(
            parent=self.root,
            monitor=self.monitors[output_idx - 1],
            logger=self.logger,
            fullscreen=bool(self.config.get("output_fullscreen", False)),
        )
        self.second_screen.start()

    def pause(self) -> None:
        self.started = False
        self.stop_event.set()
        if self.capture_worker:
            self.capture_worker.stop()
        self.status_var.set("Paused")
        self.runtime.status = "paused"
        self.log_ui("Capture paused")

    def recalibrate(self) -> None:
        self.pause()
        self.config = run_calibration(self.config, DEFAULT_CONFIG_PATH, self.logger)
        self.runtime.map_name = self.config.get("current_map", "de_mirage")
        self.runtime.side = self.config.get("current_side", "T")
        self.map_var.set(f"Map: {self.runtime.map_name}")

    def save_debug_snapshot(self) -> None:
        item = None
        try:
            item = self.ui_queue.get_nowait()
        except Exception:
            pass
        if not item:
            messagebox.showwarning("Snapshot", "当前没有可保存的调试帧")
            return

        ts = int(time.time() * 1000)
        p1 = LOG_DIR / f"debug_minimap_{ts}.png"
        p2 = LOG_DIR / f"debug_reference_{ts}.png"
        cv2.imwrite(str(p1), item["minimap_debug"])
        cv2.imwrite(str(p2), item["reference_debug"])
        self.log_ui(f"Saved snapshot: {p1.name}, {p2.name}")

    def open_config_folder(self) -> None:
        try:
            subprocess.Popen(["explorer", str((APP_ROOT / "config").resolve())])
        except Exception:
            self.log_ui("无法打开配置目录")

    def _process_loop(self) -> None:
        last_ts = time.time()
        while not self.stop_event.is_set():
            try:
                item = self.frame_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            frame = item["frame"]
            frame_id = item["frame_id"]
            roi = MinimapROI.from_dict(self.config.get("minimap_roi"))
            minimap = safe_crop(frame, roi, self.logger)
            if minimap is None:
                continue

            det = self.minimap_tracker.detect(minimap)
            px = py = None
            heading = None
            zone_name = "UNKNOWN"
            lineup_name = "UNKNOWN"
            confidence = 0.0

            lineup_result = None
            if det.found:
                px, py = map_to_reference(det.x, det.y, roi, (self.ref_img.shape[1], self.ref_img.shape[0]))
                heading = det.heading
                zone = self.zone_matcher.match(px, py)
                zone_name = zone.zone_name

                h, w = frame.shape[:2]
                cx1, cy1, cx2, cy2 = w // 3, h // 3, 2 * w // 3, 2 * h // 3
                center_view = frame[cy1:cy2, cx1:cx2]
                lineup_result = self.lineup_matcher.match(
                    px,
                    py,
                    self.runtime.map_name,
                    self.runtime.side,
                    zone_name,
                    heading,
                    center_view,
                )
                stable_zone, stable_lineup, confidence = self.output_state.update(zone, lineup_result)
                zone_name = stable_zone
                lineup_name = stable_lineup

                payload = build_output_payload(self.runtime.map_name, self.runtime.side, zone_name, lineup_result, lineup_name)
                if self.second_screen:
                    self.second_screen.submit(payload)

            if lineup_result is None:
                from cs2vision.models import LineupMatchResult

                lineup_result = LineupMatchResult()

            minimap_debug = draw_minimap_debug(minimap, det, zone_name, lineup_name)
            reference_debug = draw_reference_debug(self.ref_img, px, py, zone_name)

            now = time.time()
            fps = 1.0 / max(1e-6, now - last_ts)
            last_ts = now

            self.runtime.frame_id = frame_id
            self.runtime.fps = fps
            self.runtime.player_x = px
            self.runtime.player_y = py
            self.runtime.heading = heading
            self.runtime.zone_name = zone_name
            self.runtime.lineup_name = lineup_name
            self.runtime.confidence = confidence

            self.logger.info(
                "frame=%s player=(%s,%s) heading=%s zone=%s lineup=%s conf=%.2f",
                frame_id,
                f"{px:.1f}" if px is not None else "None",
                f"{py:.1f}" if py is not None else "None",
                f"{heading:.1f}" if heading is not None else "None",
                zone_name,
                lineup_name,
                confidence,
            )

            try:
                self.ui_queue.put_nowait({"minimap_debug": minimap_debug, "reference_debug": reference_debug})
            except queue.Full:
                _ = self.ui_queue.get_nowait()
                self.ui_queue.put_nowait({"minimap_debug": minimap_debug, "reference_debug": reference_debug})

            time.sleep(self.config.get("detect_interval_ms", 80) / 1000.0)

    def _refresh_ui_loop(self) -> None:
        self.fps_var.set(f"FPS: {self.runtime.fps:.1f}")
        self.zone_var.set(f"Zone: {self.runtime.zone_name}")
        self.lineup_var.set(f"Lineup: {self.runtime.lineup_name}")
        self.conf_var.set(f"Confidence: {self.runtime.confidence:.2f}")

        try:
            item = self.ui_queue.get_nowait()
            self._update_preview(self.minimap_label, item["minimap_debug"], (520, 520))
            self._update_preview(self.reference_label, item["reference_debug"], (520, 520))
        except Exception:
            pass

        self.root.after(120, self._refresh_ui_loop)

    def _update_preview(self, widget, bgr, max_size):
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        img.thumbnail(max_size)
        tk_img = ImageTk.PhotoImage(img)
        widget.configure(image=tk_img)
        widget.image = tk_img

    def run(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    def on_close(self) -> None:
        self.pause()
        if self.second_screen:
            self.second_screen.stop()
        self.root.destroy()


if __name__ == "__main__":
    app = App()
    if not app.config.get("minimap_roi"):
        app.recalibrate()
    app.run()
