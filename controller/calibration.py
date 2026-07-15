"""Neutral-pose calibration and sensitivity."""

from __future__ import annotations

from dataclasses import dataclass, field

from controller.filters import Vec6


@dataclass
class Calibration:
    """
    Subtract neutral offsets, then scale by sensitivity.
    Capture neutral while the phone is held still in play posture.
    """

    accel_offset: Vec6 = field(default_factory=Vec6)
    gyro_offset: Vec6 = field(default_factory=Vec6)
    sensitivity: float = 1.0
    calibrated: bool = False

    # Accumulation for capture
    _sum: Vec6 = field(default_factory=Vec6, repr=False)
    _count: int = field(default=0, repr=False)

    def reset_capture(self) -> None:
        self._sum = Vec6()
        self._count = 0

    def accumulate(self, sample: Vec6) -> None:
        self._sum = self._sum + sample
        self._count += 1

    def sample_count(self) -> int:
        return self._count

    def finalize_capture(self, min_samples: int = 20) -> bool:
        """Average accumulated samples into offsets. Returns False if not enough data."""
        if self._count < min_samples:
            return False
        inv = 1.0 / self._count
        mean = self._sum * inv
        # Offsets for accel include gravity bias at neutral pose.
        self.accel_offset = Vec6(mean.ax, mean.ay, mean.az, 0.0, 0.0, 0.0)
        self.gyro_offset = Vec6(0.0, 0.0, 0.0, mean.gx, mean.gy, mean.gz)
        self.calibrated = True
        self.reset_capture()
        return True

    def clear(self) -> None:
        self.accel_offset = Vec6()
        self.gyro_offset = Vec6()
        self.calibrated = False
        self.reset_capture()

    def apply(self, sample: Vec6) -> Vec6:
        s = self.sensitivity
        return Vec6(
            (sample.ax - self.accel_offset.ax) * s,
            (sample.ay - self.accel_offset.ay) * s,
            (sample.az - self.accel_offset.az) * s,
            (sample.gx - self.gyro_offset.gx) * s,
            (sample.gy - self.gyro_offset.gy) * s,
            (sample.gz - self.gyro_offset.gz) * s,
        )
