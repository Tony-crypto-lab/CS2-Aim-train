from __future__ import annotations

import cv2


def draw_minimap_debug(minimap_img, det, zone_name: str, lineup_name: str):
    canvas = minimap_img.copy()
    if det and det.found:
        cv2.circle(canvas, (int(det.x), int(det.y)), 6, (0, 255, 0), -1)
        cv2.putText(
            canvas,
            f"c={det.confidence:.2f} {det.method}",
            (8, 18),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 255, 255),
            1,
            cv2.LINE_AA,
        )
    cv2.putText(canvas, f"zone: {zone_name}", (8, canvas.shape[0] - 28), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 180, 0), 1)
    cv2.putText(canvas, f"lineup: {lineup_name}", (8, canvas.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 180, 0), 1)
    return canvas


def draw_reference_debug(reference_img, x: float | None, y: float | None, zone_name: str):
    canvas = reference_img.copy()
    if x is not None and y is not None:
        cv2.circle(canvas, (int(x), int(y)), 7, (255, 0, 255), -1)
    cv2.putText(canvas, zone_name, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
    return canvas
