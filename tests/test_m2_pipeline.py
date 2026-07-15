"""M2 tests: filters, calibration, processor, record/replay."""

from __future__ import annotations

from pathlib import Path

from controller.calibration import Calibration
from controller.filters import EMAFilter, MovingAverageFilter, Vec6
from controller.recorder import load_recording, replay, save_packets
from controller.sensor_processor import SensorProcessor
from network.packet import SensorPacket

FIXTURE = Path(__file__).parent / "fixtures" / "slash_burst.jsonl"


def _pkt(ax: float, ay: float = 0.0, az: float = 9.8, t: float = 0.0) -> SensorPacket:
    return SensorPacket(ax=ax, ay=ay, az=az, gx=0, gy=0, gz=0, phone_ts=t * 1000, arrival_time=t)


def test_moving_average_smooths_spike() -> None:
    filt = MovingAverageFilter(window=3)
    filt.push(Vec6(0, 0, 0, 0, 0, 0))
    filt.push(Vec6(0, 0, 0, 0, 0, 0))
    out = filt.push(Vec6(30, 0, 0, 0, 0, 0))
    assert abs(out.ax - 10.0) < 1e-6


def test_ema_tracks_toward_new_value() -> None:
    filt = EMAFilter(alpha=0.5)
    filt.push(Vec6(0, 0, 0, 0, 0, 0))
    out = filt.push(Vec6(10, 0, 0, 0, 0, 0))
    assert abs(out.ax - 5.0) < 1e-6


def test_calibration_removes_neutral_bias() -> None:
    cal = Calibration()
    for _ in range(25):
        cal.accumulate(Vec6(0.2, -0.1, 9.7, 0.01, -0.02, 0.0))
    assert cal.finalize_capture(min_samples=20) is True
    out = cal.apply(Vec6(0.2, -0.1, 9.7, 0.01, -0.02, 0.0))
    assert abs(out.ax) < 1e-6
    assert abs(out.ay) < 1e-6
    assert abs(out.az) < 1e-6
    assert abs(out.gx) < 1e-6


def test_processor_pipeline_and_magnitudes() -> None:
    proc = SensorProcessor(filter_mode="ema", ema_alpha=1.0)  # no smooth for exactness
    proc.begin_calibration_capture()
    for i in range(30):
        proc.process(_pkt(0.5, 0.0, 9.8, t=i / 60.0))
    assert proc.end_calibration_capture(min_samples=20) is True
    sample = proc.process(_pkt(0.5, 0.0, 9.8, t=1.0))
    assert abs(sample.calibrated.ax) < 0.05
    assert sample.accel_mag >= 0.0
    assert proc.samples_processed == 31


def test_record_replay_roundtrip(tmp_path: Path) -> None:
    packets = [_pkt(float(i), t=i / 60.0) for i in range(10)]
    path = tmp_path / "clip.jsonl"
    save_packets(path, packets)
    loaded = load_recording(path)
    assert len(loaded) == 10
    replayed = list(replay(loaded, start_time=100.0, realtime=False))
    assert len(replayed) == 10
    assert abs(replayed[0].arrival_time - 100.0) < 1e-9
    assert abs(replayed[-1].arrival_time - (100.0 + 9 / 60.0)) < 1e-6
    assert replayed[3].ax == packets[3].ax


def test_processor_on_fixture_recording() -> None:
    assert FIXTURE.exists(), f"missing fixture {FIXTURE}"
    packets = load_recording(FIXTURE)
    proc = SensorProcessor(filter_mode="ema", ema_alpha=0.4)
    samples = proc.process_many(list(replay(packets, start_time=0.0)))
    assert len(samples) == len(packets)
    # Fixture includes a slash burst — gyro or accel mag should spike
    peak = max(s.accel_mag for s in samples)
    assert peak > 2.0
