"""Record / replay sensor streams for deterministic testing."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Iterator

from network.packet import SensorPacket

DEFAULT_RECORDINGS_DIR = Path(__file__).resolve().parents[1] / "recordings"


class SensorRecorder:
    """Append SensorPackets as JSONL while the game runs."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._file = None
        self.recording = False
        self.count = 0

    def start(self, path: Path | None = None) -> Path:
        if self.recording:
            self.stop()
        DEFAULT_RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
        if path is None:
            stamp = time.strftime("%Y%m%d_%H%M%S")
            path = DEFAULT_RECORDINGS_DIR / f"session_{stamp}.jsonl"
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("w", encoding="utf-8")
        self.recording = True
        self.count = 0
        return self.path

    def write(self, packet: SensorPacket) -> None:
        if not self.recording or self._file is None:
            return
        row = {
            "ax": packet.ax,
            "ay": packet.ay,
            "az": packet.az,
            "gx": packet.gx,
            "gy": packet.gy,
            "gz": packet.gz,
            "t": packet.phone_ts,
            "arrival": packet.arrival_time,
            "alpha": packet.alpha,
            "beta": packet.beta,
            "gamma": packet.gamma,
        }
        self._file.write(json.dumps(row, separators=(",", ":")) + "\n")
        self.count += 1

    def stop(self) -> Path | None:
        if self._file is not None:
            self._file.close()
            self._file = None
        self.recording = False
        return self.path


def load_recording(path: Path) -> list[SensorPacket]:
    packets: list[SensorPacket] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            arrival = float(data.get("arrival", 0.0))
            packets.append(SensorPacket.from_json(data, arrival_time=arrival))
    return packets


def replay(
    packets: list[SensorPacket],
    *,
    start_time: float | None = None,
    realtime: bool = False,
) -> Iterator[SensorPacket]:
    """
    Yield packets. If realtime=True, sleep to match original inter-arrival gaps.
    arrival_time is remapped relative to start_time (default: now).
    """
    if not packets:
        return
    t0 = start_time if start_time is not None else time.perf_counter()
    base = packets[0].arrival_time
    prev_wall = time.perf_counter()
    prev_arrival = base

    for pkt in packets:
        offset = pkt.arrival_time - base
        if realtime:
            gap = max(0.0, (pkt.arrival_time - prev_arrival))
            # Sleep remaining wall time for this gap
            elapsed = time.perf_counter() - prev_wall
            delay = gap - elapsed
            if delay > 0:
                time.sleep(delay)
            prev_wall = time.perf_counter()
            prev_arrival = pkt.arrival_time
        yield SensorPacket(
            ax=pkt.ax,
            ay=pkt.ay,
            az=pkt.az,
            gx=pkt.gx,
            gy=pkt.gy,
            gz=pkt.gz,
            phone_ts=pkt.phone_ts,
            arrival_time=t0 + offset,
            alpha=pkt.alpha,
            beta=pkt.beta,
            gamma=pkt.gamma,
            has_orientation=pkt.has_orientation,
        )


def save_packets(path: Path, packets: list[SensorPacket]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for packet in packets:
            row = {
                "ax": packet.ax,
                "ay": packet.ay,
                "az": packet.az,
                "gx": packet.gx,
                "gy": packet.gy,
                "gz": packet.gz,
                "t": packet.phone_ts,
                "arrival": packet.arrival_time,
                "alpha": packet.alpha,
                "beta": packet.beta,
                "gamma": packet.gamma,
            }
            f.write(json.dumps(row, separators=(",", ":")) + "\n")
