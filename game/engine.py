"""Main loop, scene manager, fixed-timestep update."""

from __future__ import annotations

import sys

import pygame

from config.settings import Settings
from controller.aim import AimMapper
from controller.sensor_processor import SensorProcessor
from game.game import GameplayScene
from game.ui import ConnectionScene, GameOverScene, MainMenuScene, Scene, SettingsScene
from network.hub import ControlAction, NetworkHub
from network.websocket_server import MotionServer


class Engine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.running = False
        self.fps = 0.0
        self.scene: Scene | None = None
        self._scene_name = ""
        self.screen: pygame.Surface | None = None
        self.clock: pygame.time.Clock | None = None
        self.fonts: dict[str, pygame.font.Font] = {}
        self.hub = NetworkHub()
        self.server = MotionServer(
            hub=self.hub,
            host=settings.ws_host,
            port=settings.ws_port,
            require_pairing=settings.require_pairing,
        )
        self.processor = SensorProcessor(
            filter_mode=settings.filter_mode,
            ema_alpha=settings.ema_alpha,
            ma_window=settings.ma_window,
            lowpass_tau=settings.lowpass_tau,
            sensitivity=settings.sensor_sensitivity,
        )
        self.aim_mapper = AimMapper(
            screen_width=float(settings.width),
            screen_height=float(settings.height),
            view_distance_cm=settings.pointer_view_distance_cm,
            screen_width_cm=settings.pointer_screen_width_cm,
            screen_height_cm=settings.pointer_screen_height_cm,
            smoothing=settings.aim_smoothing,
            smoothing_tau=settings.aim_smoothing_tau,
            invert_x=settings.aim_invert_x,
            invert_y=settings.aim_invert_y,
            sensitivity_x=settings.aim_sensitivity_x,
            sensitivity_y=settings.aim_sensitivity_y,
            deadzone_deg=settings.aim_deadzone_deg,
            max_angle_deg=settings.aim_max_angle_deg,
            roll_compensation=settings.aim_roll_compensation,
            roll_offset_deg=settings.aim_roll_offset_deg,
        )
        self._pending_display_apply = False
        if settings.record_sensors:
            self.processor.recorder.start()

    def quit(self) -> None:
        self.running = False

    def ingest_sensors(self, max_n: int = 128):
        """Drain hub → processor. Returns list of ProcessedSample."""
        packets = self.hub.drain(max_n=max_n)
        return [self.processor.process(p) for p in packets]

    def process_controls(self) -> None:
        """Handle remote control events from phone (calibrate, start/stop game)."""
        for event in self.hub.drain_controls():
            self._handle_control(event)

    def _handle_control(self, event) -> None:
        action = event.action
        proc = self.processor
        aim = self.aim_mapper
        s = self.settings

        if action == ControlAction.CALIBRATE_START:
            proc.begin_calibration_capture()
            aim.begin_capture()
        elif action == ControlAction.CALIBRATE_STOP:
            proc.end_calibration_capture(min_samples=s.calibration_min_samples)
            aim.end_capture(min_samples=s.calibration_min_samples)
        elif action == ControlAction.RECENTER:
            last = proc.last
            if last is not None and last.has_orientation:
                aim.recenter(last.alpha, last.beta, last.gamma)
        elif action == ControlAction.START_GAME:
            if self._scene_name != "gameplay":
                self.set_scene("gameplay")
        elif action == ControlAction.STOP_GAME:
            if self._scene_name == "gameplay":
                self.set_scene("menu")

    def set_scene(self, name: str, **kwargs) -> None:
        if self.scene is not None:
            self.scene.on_exit()
        self._scene_name = name
        if name == "connection":
            self.scene = ConnectionScene(self)
        elif name == "menu":
            self.scene = MainMenuScene(self)
        elif name == "settings":
            self.scene = SettingsScene(self)
        elif name == "gameplay":
            self.scene = GameplayScene(self)
        elif name == "game_over":
            self.scene = GameOverScene(
                self,
                score=int(kwargs.get("score", 0)),
                best=int(kwargs.get("best", 0)),
            )
        else:
            raise ValueError(f"Unknown scene: {name}")
        self.scene.on_enter()

    def apply_display_settings(self) -> None:
        """Queue a display mode change (safe to call from event handlers)."""
        self._pending_display_apply = True

    def _set_mode(self, size: tuple[int, int], flags: int, vsync: int) -> pygame.Surface:
        return pygame.display.set_mode(size, flags, vsync=vsync)

    def _apply_display_settings_now(self) -> None:
        """Apply windowed / windowed-fullscreen / exclusive fullscreen.

        Windowed Fullscreen (borderless) fully re-initializes the display before
        recreating it with SCALED | FULLSCREEN. Reusing the existing SCALED window
        via a second set_mode()/toggle_fullscreen() left a frozen window on
        Windows/SDL2 (the OS window never resized while the loop kept running).
        """
        size = (self.settings.width, self.settings.height)
        mode = self.settings.display_mode
        vsync = 1 if self.settings.vsync else 0

        try:
            if mode == "fullscreen":
                self.screen = self._set_mode(
                    size, pygame.FULLSCREEN | pygame.DOUBLEBUF, vsync
                )
            elif mode == "borderless":
                # Windowed (desktop) fullscreen. A second set_mode() that reuses the
                # existing SCALED window leaves a frozen window on Windows/SDL2, so
                # fully tear down and recreate the display before applying the mode.
                pygame.display.quit()
                pygame.display.init()
                pygame.display.set_caption(self.settings.title)
                self.screen = self._set_mode(
                    size, pygame.SCALED | pygame.FULLSCREEN | pygame.DOUBLEBUF, vsync
                )
            else:
                self.screen = self._set_mode(
                    size, pygame.SCALED | pygame.DOUBLEBUF, vsync
                )
            return
        except pygame.error:
            pass

        self.settings.display_mode = "windowed"
        self.screen = self._set_mode(size, pygame.SCALED | pygame.DOUBLEBUF, 0)

    def run(self) -> None:
        pygame.init()
        pygame.display.set_caption(self.settings.title)
        self._apply_display_settings_now()
        self._pending_display_apply = False
        self.clock = pygame.time.Clock()
        self.fonts = {
            "title": pygame.font.SysFont("segoeui", 64, bold=True),
            "body": pygame.font.SysFont("segoeui", 28),
            "small": pygame.font.SysFont("segoeui", 18),
        }

        self.server.start()
        self.running = True
        self.set_scene("connection")

        accumulator = 0.0
        fixed_dt = self.settings.fixed_dt

        try:
            while self.running:
                assert self.clock is not None and self.screen is not None and self.scene is not None
                raw_dt = self.clock.tick(self.settings.fps) / 1000.0
                raw_dt = min(raw_dt, 0.05)
                self.fps = self.clock.get_fps()

                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    else:
                        self.scene.handle_event(event)

                if self._pending_display_apply:
                    self._pending_display_apply = False
                    self._apply_display_settings_now()

                accumulator += raw_dt
                while accumulator >= fixed_dt:
                    self.process_controls()
                    self.scene.update(fixed_dt)
                    accumulator -= fixed_dt
                    if not self.running:
                        break

                alpha = accumulator / fixed_dt if fixed_dt > 0 else 0.0
                self.scene.draw(self.screen, alpha)
                pygame.display.flip()
        finally:
            if self.processor.recorder.recording:
                self.processor.recorder.stop()
            self.server.stop()
            pygame.quit()
        sys.exit(0)
