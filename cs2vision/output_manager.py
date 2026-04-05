from __future__ import annotations

import time
from collections import deque
from typing import Any

from .models import LineupMatchResult, ZoneMatchResult


class OutputStateManager:
    def __init__(self, zone_stable_frames: int, lineup_stable_frames: int, hold_seconds: float) -> None:
        self.zone_stable_frames = max(1, zone_stable_frames)
        self.lineup_stable_frames = max(1, lineup_stable_frames)
        self.hold_seconds = max(0.1, hold_seconds)
        self.zone_hist = deque(maxlen=self.zone_stable_frames)
        self.lineup_hist = deque(maxlen=self.lineup_stable_frames)
        self.active_zone = "UNKNOWN"
        self.active_lineup = "UNKNOWN"
        self.last_switch_ts = 0.0

    def update(self, zone_result: ZoneMatchResult, lineup_result: LineupMatchResult) -> tuple[str, str, float]:
        now = time.time()
        self.zone_hist.append(zone_result.zone_name)
        self.lineup_hist.append(lineup_result.lineup_name)

        if len(self.zone_hist) == self.zone_hist.maxlen and len(set(self.zone_hist)) == 1:
            self.active_zone = self.zone_hist[-1]

        can_switch_lineup = now - self.last_switch_ts > self.hold_seconds
        if can_switch_lineup and len(self.lineup_hist) == self.lineup_hist.maxlen and len(set(self.lineup_hist)) == 1:
            new_name = self.lineup_hist[-1]
            if new_name != self.active_lineup:
                self.active_lineup = new_name
                self.last_switch_ts = now

        return self.active_zone, self.active_lineup, lineup_result.confidence


def build_output_payload(
    map_name: str,
    side: str,
    zone_name: str,
    lineup: LineupMatchResult,
    forced_name: str,
) -> dict[str, Any]:
    preview = lineup.preview_image if forced_name != "UNKNOWN" else None
    return {
        "preview_image": str(preview) if preview else None,
        "info": {
            "map": map_name,
            "side": side,
            "region": zone_name,
            "lineup_name": forced_name,
            "throw_type": lineup.throw_type if forced_name != "UNKNOWN" else "N/A",
            "confidence": lineup.confidence,
        },
    }
