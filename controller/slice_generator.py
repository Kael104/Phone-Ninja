"""Convert FlickGesture into on-screen SliceInput segments."""

from __future__ import annotations

from controller.base import SliceInput
from controller.gesture_detector import FlickGesture
from game.physics import Vector2


class SliceGenerator:
    """
    Maps a recognized flick to a canned screen-space slash through the playfield.
    Position is not tracked from the IMU (too drift-prone); direction + intensity only.
    """

    def __init__(
        self,
        *,
        screen_width: float,
        screen_height: float,
        base_length: float = 420.0,
        length_per_intensity: float = 18.0,
        max_length: float = 900.0,
        base_speed: float = 2200.0,
    ) -> None:
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.base_length = base_length
        self.length_per_intensity = length_per_intensity
        self.max_length = max_length
        self.base_speed = base_speed

    def from_gesture(self, gesture: FlickGesture) -> SliceInput:
        cx = self.screen_width * 0.5
        cy = self.screen_height * 0.45  # slightly above center (fruit apex zone)
        length = min(
            self.max_length,
            self.base_length + gesture.intensity * self.length_per_intensity,
        )
        half = length * 0.5
        dx, dy = gesture.dir_x, gesture.dir_y
        start = Vector2(cx - dx * half, cy - dy * half)
        end = Vector2(cx + dx * half, cy + dy * half)
        # Clamp lightly into screen with margin
        start = self._clamp(start)
        end = self._clamp(end)
        speed = self.base_speed * (0.7 + min(gesture.intensity, 40.0) / 40.0)
        return SliceInput(start=start, end=end, speed=speed)

    def _clamp(self, p: Vector2) -> Vector2:
        margin = 20.0
        return Vector2(
            max(margin, min(self.screen_width - margin, p.x)),
            max(margin, min(self.screen_height - margin, p.y)),
        )
