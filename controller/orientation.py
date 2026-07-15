"""Quaternion helpers for DeviceOrientation (W3C Z-X-Y intrinsic)."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(slots=True)
class Quat:
    """Unit quaternion (x, y, z, w)."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    w: float = 1.0

    @classmethod
    def from_euler_deg(cls, alpha: float, beta: float, gamma: float) -> Quat:
        """W3C DeviceOrientation: Q = Q_z(alpha) * Q_x(beta) * Q_y(gamma)."""
        a = math.radians(alpha) * 0.5
        b = math.radians(beta) * 0.5
        g = math.radians(gamma) * 0.5

        cz, sz = math.cos(a), math.sin(a)
        cx, sx = math.cos(b), math.sin(b)
        cy, sy = math.cos(g), math.sin(g)

        return cls(
            x=sx * cy * cz - cx * sy * sz,
            y=cx * sy * cz + sx * cy * sz,
            z=cx * cy * sz - sx * sy * cz,
            w=cx * cy * cz + sx * sy * sz,
        )

    def normalized(self) -> Quat:
        length = math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z + self.w * self.w)
        if length <= 1e-12:
            return Quat(0.0, 0.0, 0.0, 1.0)
        inv = 1.0 / length
        return Quat(self.x * inv, self.y * inv, self.z * inv, self.w * inv)

    def conjugate(self) -> Quat:
        return Quat(-self.x, -self.y, -self.z, self.w)

    def __mul__(self, other: Quat) -> Quat:
        return Quat(
            self.w * other.x + self.x * other.w + self.y * other.z - self.z * other.y,
            self.w * other.y - self.x * other.z + self.y * other.w + self.z * other.x,
            self.w * other.z + self.x * other.y - self.y * other.x + self.z * other.w,
            self.w * other.w - self.x * other.x - self.y * other.y - self.z * other.z,
        )

    def dot(self, other: Quat) -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z + self.w * other.w

    def rotate_vector(self, vx: float, vy: float, vz: float) -> tuple[float, float, float]:
        """Rotate vector v by this unit quaternion."""
        qx, qy, qz, qw = self.x, self.y, self.z, self.w
        tx = 2.0 * (qy * vz - qz * vy)
        ty = 2.0 * (qz * vx - qx * vz)
        tz = 2.0 * (qx * vy - qy * vx)
        return (
            vx + qw * tx + (qy * tz - qz * ty),
            vy + qw * ty + (qz * tx - qx * tz),
            vz + qw * tz + (qx * ty - qy * tx),
        )

    @classmethod
    def average(cls, quats: list[Quat]) -> Quat:
        if not quats:
            return Quat(0.0, 0.0, 0.0, 1.0)
        ref = quats[0].normalized()
        sx = sy = sz = sw = 0.0
        for q in quats:
            qn = q.normalized()
            if qn.dot(ref) < 0.0:
                qn = Quat(-qn.x, -qn.y, -qn.z, -qn.w)
            sx += qn.x
            sy += qn.y
            sz += qn.z
            sw += qn.w
        inv = 1.0 / len(quats)
        return Quat(sx * inv, sy * inv, sz * inv, sw * inv).normalized()


def _normalize(v: tuple[float, float, float]) -> tuple[float, float, float]:
    length = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if length <= 1e-12:
        return (0.0, 1.0, 0.0)
    inv = 1.0 / length
    return (v[0] * inv, v[1] * inv, v[2] * inv)


def _tangent_basis(
    forward: tuple[float, float, float],
    world_up: tuple[float, float, float] = (0.0, 0.0, 1.0),
) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    """Return (forward, right, up) orthonormal basis for screen projection."""
    f = _normalize(forward)
    rx = world_up[1] * f[2] - world_up[2] * f[1]
    ry = world_up[2] * f[0] - world_up[0] * f[2]
    rz = world_up[0] * f[1] - world_up[1] * f[0]
    rlen = math.sqrt(rx * rx + ry * ry + rz * rz)
    if rlen <= 1e-8:
        world_up = (0.0, 1.0, 0.0)
        rx = world_up[1] * f[2] - world_up[2] * f[1]
        ry = world_up[2] * f[0] - world_up[0] * f[2]
        rz = world_up[0] * f[1] - world_up[1] * f[0]
        rlen = math.sqrt(rx * rx + ry * ry + rz * rz)
    inv = 1.0 / rlen
    right = (rx * inv, ry * inv, rz * inv)
    ux = f[1] * right[2] - f[2] * right[1]
    uy = f[2] * right[0] - f[0] * right[2]
    uz = f[0] * right[1] - f[1] * right[0]
    return f, right, (ux, uy, uz)


def project_to_screen(
    forward_neutral: tuple[float, float, float],
    forward_current: tuple[float, float, float],
    *,
    view_distance_cm: float,
    screen_half_width_cm: float,
    screen_half_height_cm: float,
) -> tuple[float, float, float, float]:
    """
    Ray-cast current pointing direction onto a virtual screen plane.
    Returns (norm_x, norm_y, yaw_deg, pitch_deg).
    Roll around the neutral forward axis leaves the result unchanged.
    """
    f0, right, up = _tangent_basis(forward_neutral)
    f1 = _normalize(forward_current)

    along = f1[0] * f0[0] + f1[1] * f0[1] + f1[2] * f0[2]
    if along <= 1e-6:
        along = 1e-6

    yaw_deg = math.degrees(
        math.atan2(
            f1[0] * right[0] + f1[1] * right[1] + f1[2] * right[2],
            along,
        )
    )
    pitch_deg = math.degrees(
        math.atan2(
            f1[0] * up[0] + f1[1] * up[1] + f1[2] * up[2],
            along,
        )
    )

    scale = view_distance_cm / along
    hit_x = scale * f1[0] * right[0] + scale * f1[1] * right[1] + scale * f1[2] * right[2]
    hit_z = scale * f1[0] * up[0] + scale * f1[1] * up[1] + scale * f1[2] * up[2]

    norm_x = hit_x / max(screen_half_width_cm, 1e-6)
    norm_y = hit_z / max(screen_half_height_cm, 1e-6)
    return norm_x, norm_y, yaw_deg, pitch_deg


# Device frame axes (W3C: X right, Y up, Z out of screen toward user).
POINTING_AXIS = (0.0, 0.0, 1.0)
SCREEN_UP = (0.0, 1.0, 0.0)


def neutral_roll_rad(q0: Quat) -> float:
    """
    Signed roll of phone screen-up from gravity-up about the pointing axis.
    Used to decouple vertical phone tilt from horizontal cursor drift.
    """
    qn = q0.normalized()
    forward = qn.rotate_vector(*POINTING_AXIS)
    _, right, up = _tangent_basis(forward)
    screen_up = qn.rotate_vector(*SCREEN_UP)
    dot_r = screen_up[0] * right[0] + screen_up[1] * right[1] + screen_up[2] * right[2]
    dot_u = screen_up[0] * up[0] + screen_up[1] * up[1] + screen_up[2] * up[2]
    return math.atan2(dot_r, dot_u)
