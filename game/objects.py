"""Falling geometric shapes + simple object pool."""

from __future__ import annotations

import math
import random
from enum import Enum, auto

from game.physics import Vector2, integrate


class ShapeKind(Enum):
    CIRCLE = auto()
    SQUARE = auto()
    TRIANGLE = auto()


# Neon Arcade shape colors
SHAPE_COLORS: dict[ShapeKind, tuple[int, int, int]] = {
    ShapeKind.CIRCLE: (34, 211, 238),
    ShapeKind.SQUARE: (240, 57, 139),
    ShapeKind.TRIANGLE: (163, 230, 53),
}


class GameObject:
    __slots__ = (
        "kind",
        "position",
        "prev_position",
        "velocity",
        "radius",
        "rotation",
        "angular_velocity",
        "alive",
        "color",
        "points",
    )

    def __init__(self) -> None:
        self.kind = ShapeKind.CIRCLE
        self.position = Vector2()
        self.prev_position = Vector2()
        self.velocity = Vector2()
        self.radius = 36.0
        self.rotation = 0.0
        self.angular_velocity = 0.0
        self.alive = False
        self.color = SHAPE_COLORS[ShapeKind.CIRCLE]
        self.points = 10

    def reset(
        self,
        kind: ShapeKind,
        position: Vector2,
        velocity: Vector2,
        radius: float,
        angular_velocity: float,
    ) -> None:
        self.kind = kind
        self.position = position
        self.prev_position = position.copy()
        self.velocity = velocity
        self.radius = radius
        self.rotation = random.uniform(0.0, math.tau)
        self.angular_velocity = angular_velocity
        self.alive = True
        self.color = SHAPE_COLORS[kind]
        self.points = {ShapeKind.CIRCLE: 10, ShapeKind.SQUARE: 15, ShapeKind.TRIANGLE: 20}[kind]

    def update(self, gravity: float, dt: float) -> None:
        if not self.alive:
            return
        self.prev_position = self.position.copy()
        self.position, self.velocity = integrate(self.position, self.velocity, gravity, dt)
        self.rotation += self.angular_velocity * dt

    def render_position(self, alpha: float) -> Vector2:
        return self.prev_position.lerp(self.position, alpha)

    def polygon_points(self, center: Vector2 | None = None) -> list[tuple[float, float]]:
        """World-space vertices for square / triangle (circle uses radius)."""
        pos = center if center is not None else self.position
        cx, cy = pos.x, pos.y
        r = self.radius
        rot = self.rotation
        if self.kind == ShapeKind.SQUARE:
            half = r * 0.85
            corners = [(-half, -half), (half, -half), (half, half), (-half, half)]
        elif self.kind == ShapeKind.TRIANGLE:
            corners = [
                (0.0, -r),
                (r * 0.866, r * 0.5),
                (-r * 0.866, r * 0.5),
            ]
        else:
            return []
        cos_r, sin_r = math.cos(rot), math.sin(rot)
        out: list[tuple[float, float]] = []
        for x, y in corners:
            rx = x * cos_r - y * sin_r
            ry = x * sin_r + y * cos_r
            out.append((cx + rx, cy + ry))
        return out


class ObjectPool:
    def __init__(self, capacity: int = 32) -> None:
        self._pool = [GameObject() for _ in range(capacity)]

    def acquire(self) -> GameObject | None:
        for obj in self._pool:
            if not obj.alive:
                return obj
        return None

    def active(self) -> list[GameObject]:
        return [obj for obj in self._pool if obj.alive]

    def iter_alive(self):
        for obj in self._pool:
            if obj.alive:
                yield obj

    def alive_count(self) -> int:
        return sum(1 for obj in self._pool if obj.alive)

    def kill(self, obj: GameObject) -> None:
        obj.alive = False

    def clear(self) -> None:
        for obj in self._pool:
            obj.alive = False


def spawn_random(
    pool: ObjectPool,
    screen_width: float,
    screen_height: float,
    gravity: float,
    *,
    apex_min_from_bottom: float = 0.25,
    apex_max_from_bottom: float = 0.80,
) -> GameObject | None:
    obj = pool.acquire()
    if obj is None:
        return None
    kind = random.choice(list(ShapeKind))
    radius = random.uniform(28.0, 44.0)
    x = random.uniform(radius + 40.0, screen_width - radius - 40.0)
    y0 = screen_height + radius + 10.0

    # Peak height band measured from the bottom of the screen.
    lo = min(apex_min_from_bottom, apex_max_from_bottom)
    hi = max(apex_min_from_bottom, apex_max_from_bottom)
    apex_top_y = screen_height * (1.0 - hi) + radius
    apex_bottom_y = screen_height * (1.0 - lo) - radius
    if apex_bottom_y <= apex_top_y:
        apex_bottom_y = apex_top_y + 1.0
    target_apex_y = random.uniform(apex_top_y, apex_bottom_y)

    rise = max(1.0, y0 - target_apex_y)
    speed_y = -math.sqrt(2.0 * gravity * rise)
    speed_x = random.uniform(-180.0, 180.0)
    ang = random.uniform(-3.5, 3.5)
    obj.reset(
        kind=kind,
        position=Vector2(x, y0),
        velocity=Vector2(speed_x, speed_y),
        radius=radius,
        angular_velocity=ang,
    )
    return obj
