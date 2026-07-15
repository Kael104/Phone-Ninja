"""Mouse / keyboard fallback controller — always-visible blade at cursor."""

from __future__ import annotations

import pygame

from controller.base import BladeSample, SliceInput
from game.physics import Vector2


class FallbackController:
    """
    Mouse position is the always-visible blade reticle.
    Touch collision uses blade position (no speed gate).
    """

    def __init__(self, min_slice_speed: float = 80.0) -> None:
        self._min_slice_speed = min_slice_speed  # kept for API compat
        self._prev_pos: Vector2 | None = None
        self._last_pos: Vector2 | None = None
        self._has_sample = False

    @property
    def connected(self) -> bool:
        return True

    def handle_event(self, event: pygame.event.Event) -> None:
        return

    def _cursor(self) -> Vector2:
        mx, my = pygame.mouse.get_pos()
        return Vector2(float(mx), float(my))

    def blade(self, dt: float, alpha: float = 1.0) -> BladeSample:
        cur = self._cursor()
        if alpha < 1.0:
            if self._has_sample and self._prev_pos is not None:
                pos = self._prev_pos.lerp(cur, alpha)
            else:
                pos = cur
            return BladeSample(pos=pos, prev=self._prev_pos, visible=True)

        if not self._has_sample:
            self._last_pos = cur.copy()
            self._prev_pos = cur.copy()
            self._has_sample = True
            return BladeSample(pos=cur, prev=None, visible=True)

        prev = self._last_pos.copy() if self._last_pos is not None else None
        self._prev_pos = self._last_pos.copy() if self._last_pos is not None else cur.copy()
        self._last_pos = cur.copy()
        return BladeSample(pos=cur, prev=prev, visible=True)

    def poll(self, dt: float) -> SliceInput | None:
        return None
