"""Blade touch + swept-segment collision (no speed gate)."""

from __future__ import annotations

from controller.base import SliceInput
from game.objects import GameObject, ShapeKind
from game.physics import Vector2


def _point_segment_distance_sq(p: Vector2, a: Vector2, b: Vector2) -> float:
    ab = b - a
    ab_len_sq = ab.length_squared()
    if ab_len_sq < 1e-8:
        return (p - a).length_squared()
    t = ((p.x - a.x) * ab.x + (p.y - a.y) * ab.y) / ab_len_sq
    t = max(0.0, min(1.0, t))
    closest = Vector2(a.x + ab.x * t, a.y + ab.y * t)
    return (p - closest).length_squared()


def _segments_intersect(a1: Vector2, a2: Vector2, b1: Vector2, b2: Vector2) -> bool:
    def cross(o: Vector2, p: Vector2, q: Vector2) -> float:
        return (p.x - o.x) * (q.y - o.y) - (p.y - o.y) * (q.x - o.x)

    d1 = cross(a1, a2, b1)
    d2 = cross(a1, a2, b2)
    d3 = cross(b1, b2, a1)
    d4 = cross(b1, b2, a2)
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and (
        (d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)
    ):
        return True
    return False


def slice_hits_object(slice_input: SliceInput, obj: GameObject) -> bool:
    if not obj.alive:
        return False
    start, end = slice_input.start, slice_input.end

    if obj.kind == ShapeKind.CIRCLE:
        dist_sq = _point_segment_distance_sq(obj.position, start, end)
        return dist_sq <= (obj.radius * obj.radius)

    verts = obj.polygon_points()
    if not verts:
        return False
    n = len(verts)
    for i in range(n):
        p1 = Vector2(verts[i][0], verts[i][1])
        p2 = Vector2(verts[(i + 1) % n][0], verts[(i + 1) % n][1])
        if _segments_intersect(start, end, p1, p2):
            return True
    dist_sq = _point_segment_distance_sq(obj.position, start, end)
    return dist_sq <= (obj.radius * 0.55) ** 2


def collect_hits(slice_input: SliceInput, objects: list[GameObject]) -> list[GameObject]:
    return [obj for obj in objects if slice_hits_object(slice_input, obj)]


def blade_hits_object(
    pos: Vector2,
    prev: Vector2 | None,
    radius: float,
    obj: GameObject,
) -> bool:
    """Touch + swept blade vs shape. No speed threshold."""
    if not obj.alive:
        return False

    blade_r = max(radius, 1.0)
    combined = obj.radius + blade_r

    if prev is not None:
        start, end = prev, pos
        if obj.kind == ShapeKind.CIRCLE:
            dist_sq = _point_segment_distance_sq(obj.position, start, end)
            if dist_sq <= combined * combined:
                return True
        else:
            verts = obj.polygon_points()
            n = len(verts)
            for i in range(n):
                p1 = Vector2(verts[i][0], verts[i][1])
                p2 = Vector2(verts[(i + 1) % n][0], verts[(i + 1) % n][1])
                if _segments_intersect(start, end, p1, p2):
                    return True
            dist_sq = _point_segment_distance_sq(obj.position, start, end)
            if dist_sq <= combined * combined:
                return True

    # Stationary blade: point overlap
    dx = obj.position.x - pos.x
    dy = obj.position.y - pos.y
    return (dx * dx + dy * dy) <= combined * combined


def collect_blade_hits(
    pos: Vector2,
    prev: Vector2 | None,
    radius: float,
    objects,
) -> list[GameObject]:
    return [obj for obj in objects if blade_hits_object(pos, prev, radius, obj)]
