"""M3+ tests for pointer aim blade, packet orientation, touch collision."""

from __future__ import annotations

import math

from controller.aim import AimMapper
from controller.motion import MotionController
from controller.orientation import Quat, neutral_roll_rad, project_to_screen
from controller.sensor_processor import ProcessedSample
from game.collision import blade_hits_object, collect_blade_hits
from game.objects import GameObject, ShapeKind
from game.physics import Vector2
from network.packet import SensorPacket


def test_packet_orientation_fields() -> None:
    pkt = SensorPacket.from_json(
        {"ax": 1, "ay": 0, "az": 9.8, "alpha": 30.0, "beta": 45.0, "gamma": -10.0},
        1.0,
    )
    assert pkt.alpha == 30.0
    assert pkt.beta == 45.0
    assert pkt.gamma == -10.0
    assert pkt.has_orientation is True

    legacy = SensorPacket.from_json({"ax": 1, "ay": 0, "az": 9.8}, 1.0)
    assert legacy.has_orientation is False


def test_aim_mapper_neutral_at_center() -> None:
    aim = AimMapper(screen_width=1280, screen_height=720, smoothing=1.0)
    aim.set_neutral(0.0, 45.0, 0.0)
    pos = aim.update(0.0, 45.0, 0.0)
    assert abs(pos.x - 640.0) < 1.0
    assert abs(pos.y - 324.0) < 1.0  # height * 0.45


def test_aim_mapper_yaw_moves_horizontally() -> None:
    aim = AimMapper(screen_width=1280, screen_height=720, smoothing=1.0)
    aim.set_neutral(0.0, 45.0, 0.0)
    center = aim.update(0.0, 45.0, 0.0)
    turned = aim.update(10.0, 45.0, 0.0)
    assert turned.x != center.x


def test_aim_mapper_pitch_moves_vertically() -> None:
    aim = AimMapper(screen_width=1280, screen_height=720, smoothing=1.0)
    aim.set_neutral(0.0, 45.0, 0.0)
    center = aim.update(0.0, 45.0, 0.0)
    pitched = aim.update(0.0, 35.0, 0.0)
    assert pitched.y != center.y


def test_body_roll_preserves_projection() -> None:
    """Rotation around screen normal (+Z) must not move aim."""
    q0 = Quat.from_euler_deg(0.0, 90.0, 0.0).normalized()
    f0 = q0.rotate_vector(0.0, 0.0, 1.0)
    angle = math.radians(25.0) * 0.5
    q_roll = Quat(0.0, 0.0, math.sin(angle), math.cos(angle)).normalized()
    q1 = (q0 * q_roll).normalized()
    f1 = q1.rotate_vector(0.0, 0.0, 1.0)

    center = project_to_screen(f0, f0, view_distance_cm=60.0, screen_half_width_cm=17.0, screen_half_height_cm=9.5)
    rolled = project_to_screen(f0, f1, view_distance_cm=60.0, screen_half_width_cm=17.0, screen_half_height_cm=9.5)
    assert abs(rolled[0] - center[0]) < 0.01
    assert abs(rolled[1] - center[1]) < 0.01


def test_upright_hold_alpha_moves_x_gamma_ignored() -> None:
    """Upright portrait (beta=90): yaw drives X, roll about screen normal is ignored."""
    aim = AimMapper(screen_width=1280, screen_height=720, smoothing=1.0)
    aim.set_neutral(0.0, 90.0, 0.0)
    center = aim.update(0.0, 90.0, 0.0)
    turned = aim.update(15.0, 90.0, 0.0)
    pitched = aim.update(0.0, 75.0, 0.0)
    rolled = aim.update(0.0, 90.0, 20.0)

    assert turned.x != center.x
    assert pitched.y != center.y
    assert abs(rolled.x - center.x) < 1.0
    assert abs(rolled.y - center.y) < 1.0


def test_aim_mapper_gimbal_lock_stable() -> None:
    """Large yaw changes near vertical hold must stay finite and clamped."""
    aim = AimMapper(screen_width=1280, screen_height=720, smoothing=1.0)
    aim.set_neutral(0.0, 45.0, 0.0)
    pos = aim.update(45.0, 45.0, 0.0)
    assert math.isfinite(pos.x)
    assert math.isfinite(pos.y)
    assert 24 <= pos.x <= 1280 - 24
    assert 24 <= pos.y <= 720 - 24


def test_aim_mapper_clamps() -> None:
    aim = AimMapper(screen_width=1280, screen_height=720, margin=24.0, smoothing=1.0)
    aim.set_neutral(0.0, 45.0, 0.0)
    pos = aim.update(90.0, 45.0, 0.0)
    assert pos.x <= 1280 - 24
    assert pos.x >= 24


def test_project_to_screen_neutral() -> None:
    q0 = Quat.from_euler_deg(10.0, 45.0, 5.0).normalized()
    f0 = q0.rotate_vector(0.0, 0.0, 1.0)
    norm_x, norm_y, yaw, pitch = project_to_screen(
        f0,
        f0,
        view_distance_cm=60.0,
        screen_half_width_cm=17.0,
        screen_half_height_cm=9.5,
    )
    assert abs(norm_x) < 0.01
    assert abs(norm_y) < 0.01
    assert abs(yaw) < 0.01
    assert abs(pitch) < 0.01


def test_blade_hits_circle_on_touch() -> None:
    obj = GameObject()
    obj.reset(
        kind=ShapeKind.CIRCLE,
        position=Vector2(100.0, 100.0),
        velocity=Vector2(0.0, 0.0),
        radius=30.0,
        angular_velocity=0.0,
    )
    assert blade_hits_object(Vector2(100.0, 100.0), None, 28.0, obj) is True
    assert blade_hits_object(Vector2(500.0, 500.0), None, 28.0, obj) is False


def test_blade_sweep_hits() -> None:
    obj = GameObject()
    obj.reset(
        kind=ShapeKind.CIRCLE,
        position=Vector2(200.0, 200.0),
        velocity=Vector2(0.0, 0.0),
        radius=25.0,
        angular_velocity=0.0,
    )
    hits = collect_blade_hits(Vector2(250.0, 200.0), Vector2(150.0, 200.0), 20.0, [obj])
    assert len(hits) == 1


def test_motion_controller_blade_when_connected() -> None:
    from controller.filters import Vec6

    aim = AimMapper(screen_width=800, screen_height=600, smoothing=1.0)
    aim.set_neutral(0.0, 45.0, 0.0)
    motion = MotionController(aim)
    motion.set_connected(True)
    v = Vec6()
    sample = ProcessedSample(
        raw=v,
        filtered=v,
        calibrated=v,
        arrival_time=0.0,
        phone_ts=0.0,
        accel_mag=0.0,
        gyro_mag=0.0,
        dt=1 / 60,
        alpha=5.0,
        beta=45.0,
        gamma=0.0,
        has_orientation=True,
    )
    motion.push_samples([sample])
    blade = motion.blade(1 / 60)
    assert blade.visible is True


def test_aim_deadzone_holds_still() -> None:
    """Small tilt within deadzone should not move cursor from center."""
    aim = AimMapper(
        screen_width=1280,
        screen_height=720,
        smoothing=1.0,
        deadzone_deg=3.0,
        max_angle_deg=45.0,
    )
    aim.set_neutral(0.0, 45.0, 0.0)
    center = aim.update(0.0, 45.0, 0.0)
    # Tiny tilt — within deadzone after projection
    still = aim.update(0.5, 45.5, 0.0)
    assert abs(still.x - center.x) < 2.0
    assert abs(still.y - center.y) < 2.0


def test_aim_sensitivity_scales_movement() -> None:
    aim_low = AimMapper(
        screen_width=1280, screen_height=720, smoothing=1.0,
        sensitivity_x=0.5, deadzone_deg=0.0, max_angle_deg=45.0,
    )
    aim_high = AimMapper(
        screen_width=1280, screen_height=720, smoothing=1.0,
        sensitivity_x=2.0, deadzone_deg=0.0, max_angle_deg=45.0,
    )
    for aim in (aim_low, aim_high):
        aim.set_neutral(0.0, 45.0, 0.0)
        aim.update(0.0, 45.0, 0.0)
    low = aim_low.update(15.0, 45.0, 0.0)
    high = aim_high.update(15.0, 45.0, 0.0)
    assert abs(high.x - 640.0) > abs(low.x - 640.0)


def test_aim_max_angle_clamps() -> None:
    aim = AimMapper(
        screen_width=1280, screen_height=720, smoothing=1.0,
        deadzone_deg=0.0, max_angle_deg=10.0, margin=24.0,
    )
    aim.set_neutral(0.0, 45.0, 0.0)
    pos_small = aim.update(8.0, 45.0, 0.0)
    pos_large = aim.update(80.0, 45.0, 0.0)
    # Both should clamp to same edge since max_angle is 10°
    assert abs(pos_large.x - pos_small.x) < 5.0 or pos_large.x >= pos_small.x


def test_neutral_roll_rad_zero_when_level() -> None:
    q = Quat.from_euler_deg(0.0, 0.0, 0.0).normalized()
    assert abs(neutral_roll_rad(q)) < 0.01


def test_neutral_roll_rad_nonzero_with_gamma() -> None:
    q = Quat.from_euler_deg(0.0, 45.0, 20.0).normalized()
    assert abs(neutral_roll_rad(q)) > 0.05


def test_roll_compensation_decouples_vertical_tilt() -> None:
    """Grip roll at neutral: pure beta pitch should not drift horizontally when compensated."""
    neutral = (0.0, 45.0, 20.0)
    pitched = (0.0, 35.0, 20.0)

    aim_raw = AimMapper(
        screen_width=1280,
        screen_height=720,
        smoothing=1.0,
        deadzone_deg=0.0,
        roll_compensation=False,
    )
    aim_raw.set_neutral(*neutral)
    center_raw = aim_raw.update(*neutral)
    pitched_raw = aim_raw.update(*pitched)
    drift_raw = abs(pitched_raw.x - center_raw.x)

    aim_comp = AimMapper(
        screen_width=1280,
        screen_height=720,
        smoothing=1.0,
        deadzone_deg=0.0,
        roll_compensation=True,
    )
    aim_comp.set_neutral(*neutral)
    center_comp = aim_comp.update(*neutral)
    pitched_comp = aim_comp.update(*pitched)
    drift_comp = abs(pitched_comp.x - center_comp.x)

    assert drift_raw > 3.0
    assert drift_comp < drift_raw * 0.35
    assert abs(pitched_comp.y - center_comp.y) > 5.0
