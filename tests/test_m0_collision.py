"""M0 smoke tests — run with: python -m pytest tests/ -q"""

from __future__ import annotations

from controller.base import SliceInput
from game.collision import slice_hits_object
from game.objects import GameObject, ObjectPool, ShapeKind, spawn_random
from game.physics import Vector2, integrate


def test_integrate_applies_gravity() -> None:
    pos = Vector2(0.0, 0.0)
    vel = Vector2(0.0, -100.0)
    new_pos, new_vel = integrate(pos, vel, gravity=980.0, dt=1.0 / 60.0)
    assert new_vel.y > vel.y
    assert new_pos.y != pos.y


def test_slice_hits_circle() -> None:
    obj = GameObject()
    obj.reset(
        kind=ShapeKind.CIRCLE,
        position=Vector2(100.0, 100.0),
        velocity=Vector2(0.0, 0.0),
        radius=40.0,
        angular_velocity=0.0,
    )
    slice_in = SliceInput(
        start=Vector2(50.0, 100.0),
        end=Vector2(150.0, 100.0),
        speed=500.0,
    )
    assert slice_hits_object(slice_in, obj) is True


def test_slice_misses_circle() -> None:
    obj = GameObject()
    obj.reset(
        kind=ShapeKind.CIRCLE,
        position=Vector2(100.0, 100.0),
        velocity=Vector2(0.0, 0.0),
        radius=20.0,
        angular_velocity=0.0,
    )
    slice_in = SliceInput(
        start=Vector2(50.0, 200.0),
        end=Vector2(150.0, 200.0),
        speed=500.0,
    )
    assert slice_hits_object(slice_in, obj) is False


def test_spawn_random_apex_within_height_band() -> None:
    pool = ObjectPool(capacity=8)
    height = 720.0
    gravity = 980.0
    min_from_bottom = 0.25
    max_from_bottom = 0.80
    band_top = height * (1.0 - max_from_bottom)
    band_bottom = height * (1.0 - min_from_bottom)

    for _ in range(24):
        obj = spawn_random(
            pool,
            1280.0,
            height,
            gravity,
            apex_min_from_bottom=min_from_bottom,
            apex_max_from_bottom=max_from_bottom,
        )
        assert obj is not None
        vy0 = obj.velocity.y
        apex_y = obj.position.y - (vy0 * vy0) / (2.0 * gravity)
        assert band_top <= apex_y <= band_bottom
        pool.kill(obj)
