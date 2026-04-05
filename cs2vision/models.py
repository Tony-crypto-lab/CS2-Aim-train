from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MinimapROI:
    x: int = 0
    y: int = 0
    w: int = 300
    h: int = 300

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "MinimapROI":
        if not data:
            return cls()
        return cls(
            x=int(data.get("x", 0)),
            y=int(data.get("y", 0)),
            w=max(1, int(data.get("w", 300))),
            h=max(1, int(data.get("h", 300))),
        )


@dataclass
class DetectionResult:
    found: bool
    x: float = 0.0
    y: float = 0.0
    heading: float | None = None
    confidence: float = 0.0
    method: str = "none"


@dataclass
class ZoneMatchResult:
    zone_id: str = "unknown"
    zone_name: str = "UNKNOWN"
    score: float = 0.0
    stable: bool = False


@dataclass
class LineupMatchResult:
    lineup_id: str = "unknown"
    lineup_name: str = "UNKNOWN"
    throw_type: str = "N/A"
    region: str = "UNKNOWN"
    confidence: float = 0.0
    preview_image: Path | None = None
    stable: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeState:
    frame_id: int = 0
    fps: float = 0.0
    status: str = "paused"
    map_name: str = "de_mirage"
    side: str = "T"
    player_x: float | None = None
    player_y: float | None = None
    heading: float | None = None
    zone_name: str = "UNKNOWN"
    lineup_name: str = "UNKNOWN"
    confidence: float = 0.0
