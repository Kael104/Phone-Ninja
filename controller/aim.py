"""Geometric laser-pointer aim mapping (quaternion ray-cast)."""

from __future__ import annotations

import math

from controller.orientation import (
    POINTING_AXIS,
    Quat,
    neutral_roll_rad,
    project_to_screen,
)
from game.physics import Vector2


def _apply_deadzone(value: float, deadzone: float) -> float:
    """Zero small angles to kill micro-jitter at rest."""
    if abs(value) <= deadzone:
        return 0.0
    sign = 1.0 if value >= 0 else -1.0
    return sign * (abs(value) - deadzone)


def _clamp_angle(value: float, max_angle: float) -> float:
    return max(-max_angle, min(max_angle, value))


def _compensate_roll(yaw_deg: float, pitch_deg: float, phi_rad: float) -> tuple[float, float]:
    """Transform gravity-frame yaw/pitch into phone-aligned axes (undo grip roll)."""
    c = math.cos(phi_rad)
    s = math.sin(phi_rad)
    yaw_c = yaw_deg * c - pitch_deg * s
    pitch_c = yaw_deg * s + pitch_deg * c
    return yaw_c, pitch_c


class AimMapper:
    """
    Maps DeviceOrientation (alpha, beta, gamma) to a screen cursor via ray-cast.
    Supports flat laser-pointer hold; roll compensation decouples vertical tilt
    from horizontal cursor drift when the grip has a fixed roll offset.

    Absolute position control: tilt angle maps directly to cursor position.
    Cursor holds still when the phone is held still (no velocity integration).
    """

    def __init__(
        self,
        *,
        screen_width: float,
        screen_height: float,
        view_distance_cm: float = 60.0,
        screen_width_cm: float = 34.0,
        screen_height_cm: float = 19.0,
        smoothing: float = 0.35,
        smoothing_tau: float = 0.04,
        invert_x: bool = False,
        invert_y: bool = False,
        sensitivity_x: float = 1.0,
        sensitivity_y: float = 1.0,
        deadzone_deg: float = 1.5,
        max_angle_deg: float = 45.0,
        roll_compensation: bool = True,
        roll_offset_deg: float = 0.0,
        margin: float = 24.0,
    ) -> None:
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.view_distance_cm = max(1.0, view_distance_cm)
        self.screen_width_cm = max(1.0, screen_width_cm)
        self.screen_height_cm = max(1.0, screen_height_cm)
        self.smoothing = max(0.01, min(1.0, smoothing))
        self.smoothing_tau = max(1e-4, smoothing_tau)
        self.invert_x = invert_x
        self.invert_y = invert_y
        self.sensitivity_x = max(0.1, sensitivity_x)
        self.sensitivity_y = max(0.1, sensitivity_y)
        self.deadzone_deg = max(0.0, deadzone_deg)
        self.max_angle_deg = max(1.0, max_angle_deg)
        self.roll_compensation = roll_compensation
        self.roll_offset_deg = roll_offset_deg
        self.margin = margin

        self._q0 = Quat(0.0, 0.0, 0.0, 1.0)
        self._forward0 = POINTING_AXIS
        self._roll_rad = 0.0
        self.calibrated = False

        self._capturing = False
        self._capture_quats: list[Quat] = []

        self._last_yaw_deg = 0.0
        self._last_pitch_deg = 0.0
        self._last_norm_x = 0.0
        self._last_norm_y = 0.0

        cx = screen_width * 0.5
        cy = screen_height * 0.45
        self._pos = Vector2(cx, cy)
        self._prev = Vector2(cx, cy)
        self._has_sample = False

    @property
    def position(self) -> Vector2:
        return self._pos.copy()

    @property
    def previous(self) -> Vector2:
        return self._prev.copy()

    def render_position(self, alpha: float) -> Vector2:
        return self._prev.lerp(self._pos, alpha)

    @property
    def last_yaw_deg(self) -> float:
        return self._last_yaw_deg

    @property
    def last_pitch_deg(self) -> float:
        return self._last_pitch_deg

    @property
    def roll_rad(self) -> float:
        return self._roll_rad

    def _set_neutral_quat(self, q: Quat) -> None:
        self._q0 = q.normalized()
        self._forward0 = self._q0.rotate_vector(*POINTING_AXIS)
        self._roll_rad = neutral_roll_rad(self._q0)
        self.calibrated = True

    def begin_capture(self) -> None:
        self._capturing = True
        self._capture_quats = []

    def feed_capture(self, alpha: float, beta: float, gamma: float) -> None:
        if not self._capturing:
            return
        self._capture_quats.append(Quat.from_euler_deg(alpha, beta, gamma))

    def end_capture(self, min_samples: int = 20) -> bool:
        self._capturing = False
        if len(self._capture_quats) < min_samples:
            return False
        self._set_neutral_quat(Quat.average(self._capture_quats))
        return True

    def recenter(self, alpha: float, beta: float, gamma: float) -> None:
        """Instant neutral reset from current orientation."""
        self._set_neutral_quat(Quat.from_euler_deg(alpha, beta, gamma))

    def set_neutral(self, alpha: float, beta: float, gamma: float) -> None:
        self._set_neutral_quat(Quat.from_euler_deg(alpha, beta, gamma))

    def _map_angles(self, yaw_deg: float, pitch_deg: float) -> tuple[float, float]:
        """Apply deadzone, clamp, and per-axis sensitivity to yaw/pitch."""
        yaw = _apply_deadzone(yaw_deg, self.deadzone_deg)
        pitch = _apply_deadzone(pitch_deg, self.deadzone_deg)
        yaw = _clamp_angle(yaw, self.max_angle_deg)
        pitch = _clamp_angle(pitch, self.max_angle_deg)
        norm_x = (yaw / self.max_angle_deg) * self.sensitivity_x
        norm_y = (pitch / self.max_angle_deg) * self.sensitivity_y
        norm_x = max(-1.0, min(1.0, norm_x))
        norm_y = max(-1.0, min(1.0, norm_y))
        return norm_x, norm_y

    def update(
        self,
        alpha: float,
        beta: float,
        gamma: float,
        dt: float = 1.0 / 60.0,
    ) -> Vector2:
        if self._capturing:
            self.feed_capture(alpha, beta, gamma)

        q = Quat.from_euler_deg(alpha, beta, gamma).normalized()
        forward = q.rotate_vector(*POINTING_AXIS)
        half_w_cm = self.screen_width_cm * 0.5
        half_h_cm = self.screen_height_cm * 0.5

        _, _, yaw_deg, pitch_deg = project_to_screen(
            self._forward0,
            forward,
            view_distance_cm=self.view_distance_cm,
            screen_half_width_cm=half_w_cm,
            screen_half_height_cm=half_h_cm,
        )

        phi_rad = 0.0
        if self.roll_compensation and self.calibrated:
            phi_rad = self._roll_rad + math.radians(self.roll_offset_deg)
        yaw_comp, pitch_comp = _compensate_roll(yaw_deg, pitch_deg, phi_rad)

        self._last_yaw_deg = yaw_comp
        self._last_pitch_deg = pitch_comp

        norm_x, norm_y = self._map_angles(yaw_comp, pitch_comp)
        self._last_norm_x = norm_x
        self._last_norm_y = norm_y

        if self.invert_x:
            norm_x = -norm_x
        if self.invert_y:
            norm_y = -norm_y

        half_w = (self.screen_width - 2 * self.margin) * 0.5
        half_h = (self.screen_height - 2 * self.margin) * 0.5
        cx = self.screen_width * 0.5
        cy = self.screen_height * 0.45

        target_x = cx + norm_x * half_w
        target_y = cy - norm_y * half_h

        target_x = max(self.margin, min(self.screen_width - self.margin, target_x))
        target_y = max(self.margin, min(self.screen_height - self.margin, target_y))
        target = Vector2(target_x, target_y)

        if not self._has_sample:
            self._pos = target
            self._prev = target.copy()
            self._has_sample = True
            return self._pos.copy()

        self._prev = self._pos.copy()
        if self.smoothing >= 0.999:
            blend = 1.0
        else:
            blend = 1.0 - math.exp(-dt / self.smoothing_tau)
        self._pos = Vector2(
            self._pos.x + (target.x - self._pos.x) * blend,
            self._pos.y + (target.y - self._pos.y) * blend,
        )
        return self._pos.copy()

    def reset_motion(self) -> None:
        cx = self.screen_width * 0.5
        cy = self.screen_height * 0.45
        self._pos = Vector2(cx, cy)
        self._prev = Vector2(cx, cy)
        self._has_sample = False
