"""Lightweight 2D vectors and integration helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(slots=True)
class Vector2:
    x: float = 0.0
    y: float = 0.0

    def __add__(self, other: Vector2) -> Vector2:
        return Vector2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Vector2) -> Vector2:
        return Vector2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> Vector2:
        return Vector2(self.x * scalar, self.y * scalar)

    def __rmul__(self, scalar: float) -> Vector2:
        return self.__mul__(scalar)

    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def length_squared(self) -> float:
        return self.x * self.x + self.y * self.y

    def normalized(self) -> Vector2:
        length = self.length()
        if length <= 1e-8:
            return Vector2(0.0, 0.0)
        return Vector2(self.x / length, self.y / length)

    def copy(self) -> Vector2:
        return Vector2(self.x, self.y)

    def as_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)

    def as_int_tuple(self) -> tuple[int, int]:
        return (int(self.x), int(self.y))

    def lerp(self, other: Vector2, t: float) -> Vector2:
        t = max(0.0, min(1.0, t))
        return Vector2(
            self.x + (other.x - self.x) * t,
            self.y + (other.y - self.y) * t,
        )


def integrate(
    position: Vector2,
    velocity: Vector2,
    gravity: float,
    dt: float,
) -> tuple[Vector2, Vector2]:
    """Semi-implicit Euler: v += g*dt, p += v*dt."""
    new_vel = Vector2(velocity.x, velocity.y + gravity * dt)
    new_pos = Vector2(position.x + new_vel.x * dt, position.y + new_vel.y * dt)
    return new_pos, new_vel
