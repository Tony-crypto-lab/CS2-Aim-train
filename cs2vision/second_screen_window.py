from __future__ import annotations

import tkinter as tk
from pathlib import Path
from queue import Empty, Queue
from typing import Any

from PIL import Image, ImageDraw, ImageTk


class SecondScreenWindow:
    """Second-screen renderer based on Tkinter Toplevel.

    Important: Tk must run on the main thread on Windows.
    This class does not create another Tk root or run another mainloop.
    """

    def __init__(self, parent: tk.Tk, monitor, logger: Any | None = None, fullscreen: bool = True) -> None:
        self.parent = parent
        self.monitor = monitor
        self.logger = logger
        self.fullscreen = fullscreen
        self.queue: Queue = Queue(maxsize=8)

        self.window: tk.Toplevel | None = None
        self.label: tk.Label | None = None
        self.tk_image = None
        self.running = False

    def start(self) -> None:
        if self.running:
            return
        self.running = True

        self.window = tk.Toplevel(self.parent)
        self.window.title("CS2 Lineup Output")
        self.window.configure(bg="black")
        self.window.protocol("WM_DELETE_WINDOW", self.stop)

        x, y = self.monitor.x, self.monitor.y
        w, h = self.monitor.width, self.monitor.height
        if self.fullscreen:
            self.window.overrideredirect(True)
            self.window.attributes("-topmost", True)
            self.window.geometry(f"{w}x{h}+{x}+{y}")
        else:
            ww, hh = min(960, w), min(540, h)
            wx = x + max(0, (w - ww) // 2)
            wy = y + max(0, (h - hh) // 2)
            self.window.attributes("-topmost", False)
            self.window.geometry(f"{ww}x{hh}+{wx}+{wy}")

        self.window.bind("<Escape>", lambda _e: self.stop())

        self.label = tk.Label(self.window, bg="black")
        self.label.pack(fill="both", expand=True)
        self._set_image(self._placeholder(self._target_size(), "Waiting for lineup..."))

        self.window.after(100, self._tick)

    def stop(self) -> None:
        self.running = False
        if self.window is not None:
            try:
                self.window.destroy()
            except Exception:
                pass
            self.window = None
            self.label = None

    def submit(self, payload: dict[str, Any]) -> None:
        try:
            self.queue.put_nowait(payload)
        except Exception:
            # queue full: keep most recent only
            try:
                _ = self.queue.get_nowait()
                self.queue.put_nowait(payload)
            except Exception:
                pass

    def _tick(self) -> None:
        if not self.running or self.window is None:
            return
        payload = None
        try:
            while True:
                payload = self.queue.get_nowait()
        except Empty:
            pass

        if payload:
            self._render_payload(payload)

        if self.window is not None:
            self.window.after(100, self._tick)

    def _render_payload(self, payload: dict[str, Any]) -> None:
        w, h = self._target_size()
        image_path = payload.get("preview_image")
        info = payload.get("info", {})
        if image_path and Path(image_path).exists():
            try:
                img = Image.open(image_path).convert("RGB").resize((w, h))
            except Exception:
                img = self._placeholder((w, h), f"Image load failed:\n{image_path}")
        else:
            img = self._placeholder((w, h), "Standby")

        draw = ImageDraw.Draw(img)
        text = (
            f"map: {info.get('map', 'de_mirage')}\n"
            f"side: {info.get('side', 'T')}\n"
            f"region: {info.get('region', 'UNKNOWN')}\n"
            f"lineup: {info.get('lineup_name', 'UNKNOWN')}\n"
            f"throw: {info.get('throw_type', 'N/A')}\n"
            f"confidence: {info.get('confidence', 0):.2f}"
        )
        draw.rectangle((10, 10, 530, 180), fill=(0, 0, 0))
        draw.text((20, 20), text, fill=(0, 255, 200))
        self._set_image(img)

    def _target_size(self) -> tuple[int, int]:
        if self.window is None:
            return self.monitor.width, self.monitor.height
        self.window.update_idletasks()
        w = max(320, int(self.window.winfo_width()))
        h = max(240, int(self.window.winfo_height()))
        return w, h

    def _set_image(self, img: Image.Image) -> None:
        if not self.label:
            return
        self.tk_image = ImageTk.PhotoImage(img)
        self.label.configure(image=self.tk_image)

    def _placeholder(self, size: tuple[int, int], text: str) -> Image.Image:
        img = Image.new("RGB", size, (0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.text((30, 30), text, fill=(200, 200, 200))
        return img
