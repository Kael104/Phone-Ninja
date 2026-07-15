"""Controller Protocol, SliceInput, and BladeSample — shared input API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from game.physics import Vector2


@dataclass(slots=True)
class SliceInput:
    """A single slice segment for one frame of input."""

    start: Vector2
    end: Vector2
    speed: float  # pixels per second


@dataclass(slots=True)
class BladeSample:
    """Always-visible blade reticle position for touch cutting."""

    pos: Vector2
    prev: Vector2 | None
    visible: bool


class Controller(Protocol):
    """Input source: persistent blade + optional legacy slice segments."""

    def poll(self, dt: float) -> SliceInput | None:
        """Return a slice segment for this frame, or None if not slicing."""
        ...

    def blade(self, dt: float) -> BladeSample:
        """Current blade reticle (always-on when visible)."""
        ...

    @property
    def connected(self) -> bool:
        ...

    def handle_event(self, event) -> None:
        """Optional pygame event hook (menus / mouse buttons)."""
        ...
