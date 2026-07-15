"""Phone motion controller — pointer-aimed always-visible blade."""

from __future__ import annotations

import pygame

from controller.aim import AimMapper
from controller.base import BladeSample, SliceInput
from controller.sensor_processor import ProcessedSample


class MotionController:
    """
    Consumes ProcessedSample batches, maps orientation to screen aim via AimMapper.
    Returns a visible BladeSample while the phone link is live.
    """

    def __init__(self, aim_mapper: AimMapper) -> None:
        self.aim = aim_mapper
        self._connected = False
        self._has_orientation = False
        self._last_alpha = 0.0
        self._last_beta = 0.0
        self._last_gamma = 0.0

    @property
    def connected(self) -> bool:
        return self._connected

    def set_connected(self, value: bool) -> None:
        self._connected = value

    def handle_event(self, event: pygame.event.Event) -> None:
        return

    def push_samples(self, samples: list[ProcessedSample], dt: float = 1.0 / 60.0) -> None:
        for sample in samples:
            self._last_alpha = sample.alpha
            self._last_beta = sample.beta
            self._last_gamma = sample.gamma
            if sample.has_orientation:
                self._has_orientation = True
                sample_dt = sample.dt if sample.dt > 0 else dt
                self.aim.update(sample.alpha, sample.beta, sample.gamma, sample_dt)

    def blade(self, dt: float, alpha: float = 1.0) -> BladeSample:
        if not self._connected or not self._has_orientation:
            return BladeSample(pos=self.aim.position, prev=None, visible=False)
        if alpha < 1.0:
            pos = self.aim.render_position(alpha)
        else:
            pos = self.aim.position
        prev = self.aim.previous
        return BladeSample(pos=pos, prev=prev, visible=True)

    def poll(self, dt: float) -> SliceInput | None:
        return None  # touch blade cuts; no flick segments

    def reset(self) -> None:
        self._has_orientation = False
        self.aim.reset_motion()


class CompositeController:
    """
    Phone blade when connected with orientation; otherwise mouse blade.
    """

    def __init__(self, mouse: "FallbackController", motion: MotionController) -> None:  # noqa: F821
        self.mouse = mouse
        self.motion = motion

    @property
    def connected(self) -> bool:
        return True

    def handle_event(self, event: pygame.event.Event) -> None:
        self.mouse.handle_event(event)
        self.motion.handle_event(event)

    def blade(self, dt: float, alpha: float = 1.0) -> BladeSample:
        motion_blade = self.motion.blade(dt, alpha)
        if motion_blade.visible:
            return motion_blade
        return self.mouse.blade(dt, alpha)

    def poll(self, dt: float) -> SliceInput | None:
        return None
