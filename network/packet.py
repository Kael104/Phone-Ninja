"""Sensor packet schema and (de)serialization."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class SensorPacket:
    """One IMU sample from the phone. arrival_time is laptop-side (authoritative)."""

    ax: float
    ay: float
    az: float
    gx: float
    gy: float
    gz: float
    phone_ts: float  # ms from DeviceMotion (relative; do not trust across devices)
    arrival_time: float  # time.perf_counter() on laptop
    alpha: float = 0.0  # DeviceOrientation compass yaw (degrees)
    beta: float = 0.0  # DeviceOrientation front-back tilt (degrees)
    gamma: float = 0.0  # DeviceOrientation left-right tilt (degrees)
    has_orientation: bool = False
    client_id: str = ""  # future multi-player support

    @classmethod
    def from_json(
        cls,
        data: dict[str, Any],
        arrival_time: float | None = None,
        client_id: str = "",
    ) -> SensorPacket:
        has_o = "alpha" in data or "beta" in data or "gamma" in data
        return cls(
            ax=float(data.get("ax", 0.0)),
            ay=float(data.get("ay", 0.0)),
            az=float(data.get("az", 0.0)),
            gx=float(data.get("gx", 0.0)),
            gy=float(data.get("gy", 0.0)),
            gz=float(data.get("gz", 0.0)),
            phone_ts=float(data.get("t", 0.0)),
            arrival_time=arrival_time if arrival_time is not None else time.perf_counter(),
            alpha=float(data.get("alpha", 0.0)),
            beta=float(data.get("beta", 0.0)),
            gamma=float(data.get("gamma", 0.0)),
            has_orientation=has_o,
            client_id=str(data.get("client_id", client_id)),
        )

    def as_debug_tuple(self) -> tuple[float, float, float, float, float, float]:
        return (self.ax, self.ay, self.az, self.gx, self.gy, self.gz)
