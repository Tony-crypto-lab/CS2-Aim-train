from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from queue import Empty, Queue
from typing import Any

from PIL import Image, ImageDraw, ImageTk


class SecondScreenWindow:
    def __init__(self, monitor, logger: Any | None = None) -> None:
        self.monitor = monitor
        self.logger = logger
        self.queue: Queue = Queue(maxsize=8)
        self.root: tk.Tk | None = None
        self.label: tk.Label | None = None
        self.tk_image = None
        self.running = False

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        t = threading.Thread(target=self._run_tk, daemon=True)
        t.start()

    def stop(self) -> None:
        self.running = False
        if self.root:
            self.root.after(0, self.root.destroy)

    def submit(self, payload: dict[str, Any]) -> None:
        try:
            self.queue.put_nowait(payload)
        except Exception:
            pass

    def _run_tk(self) -> None:
        self.root = tk.Tk()
        self.root.title("CS2 Lineup Output")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        x, y = self.monitor.x, self.monitor.y
        w, h = self.monitor.width, self.monitor.height
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.configure(bg="black")

        self.label = tk.Label(self.root, bg="black")
        self.label.pack(fill="both", expand=True)
        self._set_image(self._placeholder((w, h), "Waiting for lineup..."))

        self.root.after(100, self._tick)
        self.root.mainloop()

    def _tick(self) -> None:
        if not self.running or self.root is None:
            return
        payload = None
        try:
            while True:
                payload = self.queue.get_nowait()
        except Empty:
            pass

        if payload:
            self._render_payload(payload)

        self.root.after(100, self._tick)

    def _render_payload(self, payload: dict[str, Any]) -> None:
        w, h = self.monitor.width, self.monitor.height
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
