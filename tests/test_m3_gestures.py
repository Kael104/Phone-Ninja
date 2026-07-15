"""M3 tests: gesture detection, slice generation, fixture slash."""

from __future__ import annotations

from pathlib import Path

from controller.filters import Vec6
from controller.gesture_detector import FlickDirection, GestureDetector, classify_direction
from controller.recorder import load_recording, replay
from controller.sensor_processor import ProcessedSample, SensorProcessor
from controller.slice_generator import SliceGenerator

FIXTURE = Path(__file__).parent / "fixtures" / "slash_burst.jsonl"


def _sample(
    ax: float,
    ay: float = 0.0,
    az: float = 0.0,
    gx: float = 0.0,
    gy: float = 0.0,
    gz: float = 0.0,
    t: float = 0.0,
) -> ProcessedSample:
    cal = Vec6(ax, ay, az, gx, gy, gz)
    accel_mag = (ax * ax + ay * ay + az * az) ** 0.5
    gyro_mag = (gx * gx + gy * gy + gz * gz) ** 0.5
    return ProcessedSample(
        raw=cal,
        filtered=cal,
        calibrated=cal,
        arrival_time=t,
        phone_ts=t * 1000,
        accel_mag=accel_mag,
        gyro_mag=gyro_mag,
        dt=1 / 60,
    )


def test_classify_cardinal_and_diagonal() -> None:
    assert classify_direction(1, 0) == FlickDirection.RIGHT
    assert classify_direction(-1, 0) == FlickDirection.LEFT
    assert classify_direction(0, 1) == FlickDirection.UP
    assert classify_direction(0, -1) == FlickDirection.DOWN
    assert classify_direction(1, 1) == FlickDirection.DIAG_UP_RIGHT
    assert classify_direction(-1, -1) == FlickDirection.DIAG_DOWN_LEFT


def test_detector_emits_right_flick() -> None:
    det = GestureDetector(accel_threshold=5.0, cooldown=0.05, min_duration=0.02)
    # idle
    for i in range(5):
        assert det.update(_sample(0.1, 0.0, t=i / 60)) is None
    # slash to the right (positive ax)
    got = None
    for i in range(5, 20):
        amp = 12.0 if 5 <= i <= 12 else 1.0
        g = det.update(_sample(amp, 0.2, t=i / 60))
        if g is not None:
            got = g
            break
    assert got is not None
    assert got.direction in (FlickDirection.RIGHT, FlickDirection.DIAG_UP_RIGHT)


def test_detector_emits_up_flick() -> None:
    # dir_ay = -calibrated.ay, so negative ay → up on screen
    det = GestureDetector(accel_threshold=5.0, cooldown=0.05, min_duration=0.02)
    got = None
    for i in range(20):
        amp = 14.0 if 3 <= i <= 10 else 0.2
        g = det.update(_sample(0.1, -amp, t=i / 60))
        if g is not None:
            got = g
    assert got is not None
    assert got.direction in (FlickDirection.UP, FlickDirection.DIAG_UP_LEFT, FlickDirection.DIAG_UP_RIGHT)


def test_slice_generator_orientation() -> None:
    gen = SliceGenerator(screen_width=1280, screen_height=720, base_length=400)
    det = GestureDetector(accel_threshold=5.0, cooldown=0.05, min_duration=0.02)
    gesture = None
    for i in range(20):
        amp = 12.0 if 4 <= i <= 11 else 0.2
        g = det.update(_sample(amp, 0.0, t=i / 60))
        if g is not None:
            gesture = g
    assert gesture is not None
    slice_in = gen.from_gesture(gesture)
    assert slice_in.end.x > slice_in.start.x


def test_fixture_produces_at_least_one_flick() -> None:
    packets = load_recording(FIXTURE)
    proc = SensorProcessor(filter_mode="ema", ema_alpha=0.5)
    proc.begin_calibration_capture()
    head = list(replay(packets[:25], start_time=0.0))
    proc.process_many(head)
    assert proc.end_calibration_capture(min_samples=15) is True

    det = GestureDetector(accel_threshold=4.0, gyro_threshold=6.0, cooldown=0.15)
    proc2 = SensorProcessor(filter_mode="ema", ema_alpha=0.5)
    proc2.calibration = proc.calibration
    samples = proc2.process_many(list(replay(packets, start_time=0.0)))
    gestures = [det.update(s) for s in samples]
    assert any(g is not None for g in gestures)
