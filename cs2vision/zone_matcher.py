from __future__ import annotations

import math
from typing import Any

from .models import ZoneMatchResult


def _point_in_polygon(x: float, y: float, points: list[list[float]]) -> bool:
    inside = False
    n = len(points)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = points[i]
        xj, yj = points[j]
        intersect = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-6) + xi
        )
        if intersect:
            inside = not inside
        j = i
    return inside


def _distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x1 - x2, y1 - y2)


class ZoneMatcher:
    def __init__(self, zones: list[dict[str, Any]]) -> None:
        self.zones = sorted(zones, key=lambda z: z.get("priority", 0), reverse=True)

    def match(self, x: float, y: float) -> ZoneMatchResult:
        best_fallback: tuple[float, dict[str, Any]] | None = None

        for zone in self.zones:
            ztype = zone.get("type", "polygon")
            if ztype == "polygon":
                points = zone.get("points", [])
                if _point_in_polygon(x, y, points):
                    return ZoneMatchResult(zone_id=zone["id"], zone_name=zone["name"], score=0.95)
                # fallback: dist to centroid
                if points:
                    cx = sum(p[0] for p in points) / len(points)
                    cy = sum(p[1] for p in points) / len(points)
                    d = _distance(x, y, cx, cy)
                    score = max(0.0, 1.0 - d / 300.0)
                    best_fallback = max(best_fallback or (0.0, zone), (score, zone), key=lambda t: t[0])

            elif ztype == "circle":
                cx, cy = zone.get("center", [0, 0])
                r = max(1, float(zone.get("radius", 1)))
                d = _distance(x, y, cx, cy)
                if d <= r:
                    return ZoneMatchResult(zone_id=zone["id"], zone_name=zone["name"], score=0.9)
                score = max(0.0, 1.0 - d / (r * 3))
                best_fallback = max(best_fallback or (0.0, zone), (score, zone), key=lambda t: t[0])

            elif ztype == "rect":
                rx, ry, rw, rh = zone.get("rect", [0, 0, 1, 1])
                if rx <= x <= rx + rw and ry <= y <= ry + rh:
                    return ZoneMatchResult(zone_id=zone["id"], zone_name=zone["name"], score=0.92)
                cx = rx + rw / 2
                cy = ry + rh / 2
                d = _distance(x, y, cx, cy)
                score = max(0.0, 1.0 - d / 300.0)
                best_fallback = max(best_fallback or (0.0, zone), (score, zone), key=lambda t: t[0])

        if best_fallback and best_fallback[0] > 0.25:
            z = best_fallback[1]
            return ZoneMatchResult(zone_id=z["id"], zone_name=z["name"], score=best_fallback[0])

        return ZoneMatchResult(zone_id="unknown", zone_name="UNKNOWN", score=0.0)
