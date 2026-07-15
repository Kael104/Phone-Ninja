"""Flick / slash gesture detection from ProcessedSample stream."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto

from controller.sensor_processor import ProcessedSample


class FlickDirection(Enum):
    LEFT = auto()
    RIGHT = auto()
    UP = auto()
    DOWN = auto()
    DIAG_UP_RIGHT = auto()
    DIAG_UP_LEFT = auto()
    DIAG_DOWN_RIGHT = auto()
    DIAG_DOWN_LEFT = auto()


@dataclass(slots=True)
class FlickGesture:
    direction: FlickDirection
    intensity: float  # peak combined magnitude
    arrival_time: float
    # Unit vector in phone "screen plane" (x right, y up) used for slice aim
    dir_x: float
    dir_y: float


def classify_direction(dx: float, dy: float, diag_ratio: float = 0.4) -> FlickDirection:
    """
    Map a 2D direction (x right, y up) to a slash class.
    diag_ratio: if both |dx| and |dy| exceed this fraction of the dominant axis → diagonal.
    """
    mag = math.hypot(dx, dy)
    if mag < 1e-8:
        return FlickDirection.RIGHT
    nx, ny = dx / mag, dy / mag
    ax, ay = abs(nx), abs(ny)

    if ax > 0 and ay / max(ax, 1e-8) >= diag_ratio and ay > 0 and ax / max(ay, 1e-8) >= diag_ratio:
        if nx >= 0 and ny >= 0:
            return FlickDirection.DIAG_UP_RIGHT
        if nx < 0 and ny >= 0:
            return FlickDirection.DIAG_UP_LEFT
        if nx >= 0 and ny < 0:
            return FlickDirection.DIAG_DOWN_RIGHT
        return FlickDirection.DIAG_DOWN_LEFT

    if ax >= ay:
        return FlickDirection.RIGHT if nx >= 0 else FlickDirection.LEFT
    return FlickDirection.UP if ny >= 0 else FlickDirection.DOWN


class GestureDetector:
    """
    Stateless flick detector: magnitude threshold + dominant direction.

    Uses calibrated linear accel (xy) for direction and a blend of
    accel_mag + gyro_mag for energy. Rising edge starts a window;
    peak direction is locked near the energy peak, then emitted once
    energy falls or the window ends. Cooldown prevents multi-fire.
    """

    def __init__(
        self,
        *,
        accel_threshold: float = 6.0,
        gyro_threshold: float = 8.0,
        gyro_weight: float = 0.35,
        min_duration: float = 0.04,
        max_duration: float = 0.35,
        cooldown: float = 0.28,
        release_ratio: float = 0.45,
    ) -> None:
        self.accel_threshold = accel_threshold
        self.gyro_threshold = gyro_threshold
        self.gyro_weight = gyro_weight
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.cooldown = cooldown
        self.release_ratio = release_ratio

        self._active = False
        self._start_t = 0.0
        self._peak_energy = 0.0
        self._sum_ax = 0.0
        self._sum_ay = 0.0
        self._samples = 0
        self._cooldown_until = 0.0
        self.last_gesture: FlickGesture | None = None

    def reset(self) -> None:
        self._active = False
        self._start_t = 0.0
        self._peak_energy = 0.0
        self._sum_ax = 0.0
        self._sum_ay = 0.0
        self._samples = 0
        self._cooldown_until = 0.0
        self.last_gesture = None

    def _energy(self, sample: ProcessedSample) -> float:
        return sample.accel_mag + self.gyro_weight * sample.gyro_mag

    def _threshold(self) -> float:
        return self.accel_threshold

    def update(self, sample: ProcessedSample) -> FlickGesture | None:
        t = sample.arrival_time
        if t < self._cooldown_until:
            return None

        energy = self._energy(sample)
        # Direction from phone plane: ax ~ left/right, ay ~ up/down after calibration.
        # Flip ay so positive = up on screen for typical portrait DeviceMotion.
        dir_ax = sample.calibrated.ax
        dir_ay = -sample.calibrated.ay
        # Blend a bit of gyro for rotational slashes
        dir_ax += 0.15 * sample.calibrated.gy
        dir_ay += 0.15 * sample.calibrated.gx

        thr = self._threshold()
        # Also allow strong gyro-only flicks
        gyro_fire = sample.gyro_mag >= self.gyro_threshold

        if not self._active:
            if energy >= thr or gyro_fire:
                self._active = True
                self._start_t = t
                self._peak_energy = energy
                self._sum_ax = dir_ax
                self._sum_ay = dir_ay
                self._samples = 1
            return None

        # Active flick window
        self._samples += 1
        self._sum_ax += dir_ax
        self._sum_ay += dir_ay
        if energy > self._peak_energy:
            self._peak_energy = energy

        elapsed = t - self._start_t
        released = energy < thr * self.release_ratio and not gyro_fire
        timed_out = elapsed >= self.max_duration

        if not (released or timed_out):
            return None

        # Finalize
        self._active = False
        if elapsed < self.min_duration and self._peak_energy < thr * 1.2:
            return None
        if self._samples < 2:
            return None

        dx = self._sum_ax / self._samples
        dy = self._sum_ay / self._samples
        mag = math.hypot(dx, dy)
        if mag < 1e-6:
            # Fall back to horizontal slash if direction collapsed
            dx, dy = 1.0, 0.0
            mag = 1.0
        nx, ny = dx / mag, dy / mag
        direction = classify_direction(nx, ny)
        gesture = FlickGesture(
            direction=direction,
            intensity=self._peak_energy,
            arrival_time=t,
            dir_x=nx,
            dir_y=ny,
        )
        self.last_gesture = gesture
        self._cooldown_until = t + self.cooldown
        return gesture
