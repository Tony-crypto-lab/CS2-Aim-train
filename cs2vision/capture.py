from __future__ import annotations

import threading
import time
from queue import Full, Queue
from typing import Any

import cv2
import mss
import numpy as np


class ScreenCaptureWorker(threading.Thread):
    def __init__(
        self,
        output_queue: Queue,
        monitor_index: int,
        fps_limit: int = 15,
        region: dict[str, int] | None = None,
        logger: Any | None = None,
    ) -> None:
        super().__init__(daemon=True)
        self.output_queue = output_queue
        self.monitor_index = monitor_index
        self.fps_limit = max(1, fps_limit)
        self.region = region
        self.logger = logger
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._pause.clear()

    def pause(self) -> None:
        self._pause.set()

    def resume(self) -> None:
        self._pause.clear()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        interval = 1.0 / self.fps_limit
        frame_id = 0
        with mss.mss() as sct:
            monitors = sct.monitors
            mon = monitors[min(max(1, self.monitor_index), len(monitors) - 1)]
            full_monitor = {
                "left": int(mon.get("left", 0)),
                "top": int(mon.get("top", 0)),
                "width": int(mon.get("width", 0)),
                "height": int(mon.get("height", 0)),
            }
            while not self._stop.is_set():
                if self._pause.is_set():
                    time.sleep(0.1)
                    continue

                t0 = time.perf_counter()
                try:
                    target = self.region or full_monitor
                    shot = sct.grab(target)
                    frame = np.array(shot)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                    payload = {
                        "frame_id": frame_id,
                        "frame": frame,
                        "timestamp": time.time(),
                        "monitor": mon,
                    }
                    try:
                        self.output_queue.put_nowait(payload)
                    except Full:
                        _ = self.output_queue.get_nowait()
                        self.output_queue.put_nowait(payload)
                    frame_id += 1
                except Exception as exc:
                    if self.logger:
                        self.logger.exception("Capture error: %s", exc)
                    time.sleep(0.2)

                dt = time.perf_counter() - t0
                if dt < interval:
                    time.sleep(interval - dt)
