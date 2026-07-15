"""Sensor pipeline: raw → filter → calibrate → ProcessedSample."""

from __future__ import annotations

import math
from dataclasses import dataclass

from controller.calibration import Calibration
from controller.filters import EMAFilter, LowPassFilter, MovingAverageFilter, Vec6
from controller.recorder import SensorRecorder
from network.packet import SensorPacket


@dataclass(slots=True)
class ProcessedSample:
    """Filtered + calibrated IMU sample ready for aim / gesture detection."""

    raw: Vec6
    filtered: Vec6
    calibrated: Vec6
    arrival_time: float
    phone_ts: float
    accel_mag: float
    gyro_mag: float
    dt: float
    alpha: float = 0.0
    beta: float = 0.0
    gamma: float = 0.0
    has_orientation: bool = False


class SensorProcessor:
    """
    Orchestrates Stage 1–3 of the motion pipeline.
    Stage 4+ (gestures) lives in later milestones.
    """

    def __init__(
        self,
        *,
        filter_mode: str = "ema",
        ema_alpha: float = 0.35,
        ma_window: int = 5,
        lowpass_tau: float = 0.04,
        sensitivity: float = 1.0,
        recorder: SensorRecorder | None = None,
    ) -> None:
        self.filter_mode = filter_mode
        self.ema = EMAFilter(alpha=ema_alpha)
        self.moving_avg = MovingAverageFilter(window=ma_window)
        self.lowpass = LowPassFilter(tau=lowpass_tau)
        self.calibration = Calibration(sensitivity=sensitivity)
        self.recorder = recorder if recorder is not None else SensorRecorder()
        self._last_arrival: float | None = None
        self._capturing = False
        self.last: ProcessedSample | None = None
        self.samples_processed = 0

    def reset(self) -> None:
        self.ema.reset()
        self.moving_avg.reset()
        self.lowpass.reset()
        self._last_arrival = None
        self._capturing = False
        self.last = None
        self.samples_processed = 0

    def set_sensitivity(self, value: float) -> None:
        self.calibration.sensitivity = max(0.1, float(value))

    def process(self, packet: SensorPacket) -> ProcessedSample:
        if self.recorder.recording:
            self.recorder.write(packet)

        raw = Vec6(packet.ax, packet.ay, packet.az, packet.gx, packet.gy, packet.gz)
        dt = 0.0
        if self._last_arrival is not None:
            dt = max(0.0, packet.arrival_time - self._last_arrival)
        self._last_arrival = packet.arrival_time

        if self.filter_mode == "moving_avg":
            filtered = self.moving_avg.push(raw)
        elif self.filter_mode == "lowpass":
            filtered = self.lowpass.push(raw, dt if dt > 0 else 1.0 / 60.0)
        else:
            filtered = self.ema.push(raw)

        if self._capturing:
            self.calibration.accumulate(filtered)

        calibrated = self.calibration.apply(filtered)

        accel_mag = math.sqrt(
            calibrated.ax * calibrated.ax
            + calibrated.ay * calibrated.ay
            + calibrated.az * calibrated.az
        )
        gyro_mag = math.sqrt(
            calibrated.gx * calibrated.gx
            + calibrated.gy * calibrated.gy
            + calibrated.gz * calibrated.gz
        )

        sample = ProcessedSample(
            raw=raw,
            filtered=filtered,
            calibrated=calibrated,
            arrival_time=packet.arrival_time,
            phone_ts=packet.phone_ts,
            accel_mag=accel_mag,
            gyro_mag=gyro_mag,
            dt=dt,
            alpha=packet.alpha,
            beta=packet.beta,
            gamma=packet.gamma,
            has_orientation=packet.has_orientation,
        )
        self.last = sample
        self.samples_processed += 1
        return sample

    def process_many(self, packets: list[SensorPacket]) -> list[ProcessedSample]:
        return [self.process(p) for p in packets]

    def begin_calibration_capture(self) -> None:
        self.calibration.reset_capture()
        self._capturing = True

    def end_calibration_capture(self, min_samples: int = 20) -> bool:
        self._capturing = False
        return self.calibration.finalize_capture(min_samples=min_samples)

    @property
    def capturing_calibration(self) -> bool:
        return self._capturing
