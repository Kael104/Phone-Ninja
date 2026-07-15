"""Noise filters for IMU samples (independently testable)."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass(slots=True)
class Vec6:
    """Accel (ax,ay,az) + gyro (gx,gy,gz)."""

    ax: float = 0.0
    ay: float = 0.0
    az: float = 0.0
    gx: float = 0.0
    gy: float = 0.0
    gz: float = 0.0

    def as_tuple(self) -> tuple[float, float, float, float, float, float]:
        return (self.ax, self.ay, self.az, self.gx, self.gy, self.gz)

    @classmethod
    def from_tuple(cls, values: tuple[float, float, float, float, float, float]) -> Vec6:
        return cls(*values)

    def __add__(self, other: Vec6) -> Vec6:
        return Vec6(
            self.ax + other.ax,
            self.ay + other.ay,
            self.az + other.az,
            self.gx + other.gx,
            self.gy + other.gy,
            self.gz + other.gz,
        )

    def __sub__(self, other: Vec6) -> Vec6:
        return Vec6(
            self.ax - other.ax,
            self.ay - other.ay,
            self.az - other.az,
            self.gx - other.gx,
            self.gy - other.gy,
            self.gz - other.gz,
        )

    def __mul__(self, scalar: float) -> Vec6:
        return Vec6(
            self.ax * scalar,
            self.ay * scalar,
            self.az * scalar,
            self.gx * scalar,
            self.gy * scalar,
            self.gz * scalar,
        )


class MovingAverageFilter:
    """Simple sliding-window mean per axis."""

    def __init__(self, window: int = 5) -> None:
        if window < 1:
            raise ValueError("window must be >= 1")
        self.window = window
        self._buf: deque[Vec6] = deque(maxlen=window)

    def reset(self) -> None:
        self._buf.clear()

    def push(self, sample: Vec6) -> Vec6:
        self._buf.append(sample)
        n = len(self._buf)
        sx = sy = sz = sgx = sgy = sgz = 0.0
        for v in self._buf:
            sx += v.ax
            sy += v.ay
            sz += v.az
            sgx += v.gx
            sgy += v.gy
            sgz += v.gz
        inv = 1.0 / n
        return Vec6(sx * inv, sy * inv, sz * inv, sgx * inv, sgy * inv, sgz * inv)


class EMAFilter:
    """Exponential moving average. alpha closer to 1 = less smoothing."""

    def __init__(self, alpha: float = 0.35) -> None:
        if not 0.0 < alpha <= 1.0:
            raise ValueError("alpha must be in (0, 1]")
        self.alpha = alpha
        self._state: Vec6 | None = None

    def reset(self) -> None:
        self._state = None

    def push(self, sample: Vec6) -> Vec6:
        if self._state is None:
            self._state = sample
            return sample
        a = self.alpha
        s = self._state
        self._state = Vec6(
            a * sample.ax + (1.0 - a) * s.ax,
            a * sample.ay + (1.0 - a) * s.ay,
            a * sample.az + (1.0 - a) * s.az,
            a * sample.gx + (1.0 - a) * s.gx,
            a * sample.gy + (1.0 - a) * s.gy,
            a * sample.gz + (1.0 - a) * s.gz,
        )
        return self._state


class LowPassFilter:
    """
    First-order low-pass using time constant tau.
    y += (x - y) * (dt / (tau + dt))
    """

    def __init__(self, tau: float = 0.04) -> None:
        if tau < 0.0:
            raise ValueError("tau must be >= 0")
        self.tau = tau
        self._state: Vec6 | None = None

    def reset(self) -> None:
        self._state = None

    def push(self, sample: Vec6, dt: float) -> Vec6:
        if self._state is None or dt <= 0.0:
            self._state = sample
            return sample
        blend = dt / (self.tau + dt) if self.tau > 0 else 1.0
        s = self._state
        self._state = Vec6(
            s.ax + (sample.ax - s.ax) * blend,
            s.ay + (sample.ay - s.ay) * blend,
            s.az + (sample.az - s.az) * blend,
            s.gx + (sample.gx - s.gx) * blend,
            s.gy + (sample.gy - s.gy) * blend,
            s.gz + (sample.gz - s.gz) * blend,
        )
        return self._state
