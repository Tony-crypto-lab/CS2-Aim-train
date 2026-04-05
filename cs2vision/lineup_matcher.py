from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import cv2

from .models import LineupMatchResult


class LineupMatcher:
    def __init__(self, lineups: list[dict[str, Any]], app_root: Path) -> None:
        self.lineups = lineups
        self.app_root = app_root

    def match(
        self,
        x: float,
        y: float,
        current_map: str,
        side: str,
        zone_name: str,
        heading: float | None,
        center_view_frame=None,
    ) -> LineupMatchResult:
        candidates = []
        for item in self.lineups:
            if item.get("map") != current_map:
                continue
            if item.get("side", "T") != side:
                continue

            dx = x - float(item.get("minimap_x", 0))
            dy = y - float(item.get("minimap_y", 0))
            d = math.hypot(dx, dy)
            radius = float(item.get("trigger_radius", 40))
            if d > radius * 1.5:
                continue

            score = max(0.0, 1.0 - d / max(radius, 1))
            if item.get("region") == zone_name:
                score += 0.2

            hmin = item.get("optional_heading_min")
            hmax = item.get("optional_heading_max")
            if heading is not None and hmin is not None and hmax is not None:
                if float(hmin) <= heading <= float(hmax):
                    score += 0.1
                else:
                    score -= 0.15

            view_template = item.get("optional_view_template")
            if view_template and center_view_frame is not None:
                score += self._match_view_template(center_view_frame, view_template) * 0.2

            score += float(item.get("priority", 0)) * 0.01
            candidates.append((score, item))

        if not candidates:
            return LineupMatchResult()

        score, best = max(candidates, key=lambda t: t[0])
        if score < 0.25:
            return LineupMatchResult()

        preview = self.app_root / best.get("preview_image", "")
        return LineupMatchResult(
            lineup_id=best.get("id", "unknown"),
            lineup_name=best.get("lineup_name", "UNKNOWN"),
            throw_type=best.get("throw_type", "N/A"),
            region=best.get("region", "UNKNOWN"),
            confidence=max(0.0, min(1.0, score)),
            preview_image=preview,
            metadata=best,
        )

    def _match_view_template(self, frame, template_path: str) -> float:
        path = self.app_root / template_path
        if not path.exists():
            return 0.0
        temp = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if temp is None:
            return 0.0
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if gray.shape[0] < temp.shape[0] or gray.shape[1] < temp.shape[1]:
            return 0.0
        res = cv2.matchTemplate(gray, temp, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        return float(max_val)
