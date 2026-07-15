"""Gameplay scene: spawn, physics, blade touch collision, score/lives."""

from __future__ import annotations

import pygame

from controller.fallback import FallbackController
from controller.motion import CompositeController, MotionController
from game.collision import collect_blade_hits
from game.objects import ObjectPool, spawn_random
from game.renderer import (
    SliceTrail,
    draw_blade,
    draw_hud,
    draw_object,
    draw_sensor_debug,
)
from game.ui import AimSensitivityPanel, PauseOverlay, Scene


class GameplayScene(Scene):
    def __init__(self, engine: "Engine") -> None:  # noqa: F821
        super().__init__(engine)
        s = engine.settings
        self.pool = ObjectPool(capacity=s.max_active_objects)
        mouse = FallbackController(min_slice_speed=s.min_slice_speed)
        self.motion = MotionController(engine.aim_mapper)
        self.controller = CompositeController(mouse, self.motion)
        self.trail = SliceTrail(
            max_points=s.slice_trail_max,
            ttl=s.slice_trail_ttl,
        )
        self.pause_ui = PauseOverlay(engine)
        self.sensitivity_ui = AimSensitivityPanel(engine)
        self.score = 0
        self.lives = s.starting_lives
        self.combo = 0
        self.spawn_timer = 0.0
        self.spawn_interval = s.spawn_interval
        self.elapsed = 0.0
        self.paused = False
        self._miss_y = float(s.height) + 80.0
        self._conn_label = "Mouse  ·  connected"

    def on_enter(self) -> None:
        self.pool.clear()
        self.trail.clear()
        self.motion.reset()
        self.score = 0
        self.lives = self.engine.settings.starting_lives
        self.combo = 0
        self.spawn_timer = 0.3
        self.spawn_interval = self.engine.settings.spawn_interval
        self.elapsed = 0.0
        self.paused = False

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.paused:
            self.pause_ui.handle_event(event)
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.paused = True
                return
            if event.key == pygame.K_F3:
                s = self.engine.settings
                s.infinite_lives = not s.infinite_lives
            if event.key == pygame.K_t:
                last = self.engine.processor.last
                if last is not None and last.has_orientation:
                    self.engine.aim_mapper.recenter(last.alpha, last.beta, last.gamma)
        self.sensitivity_ui.handle_event(event)
        self.controller.handle_event(event)

    def update(self, dt: float) -> None:
        samples = self.engine.ingest_sensors(max_n=128)
        snap = self.engine.hub.snapshot()
        self.motion.set_connected(snap.connected)
        if snap.connected:
            self._conn_label = f"Phone  ·  {snap.hz:.0f} Hz"
        else:
            self._conn_label = "Mouse  ·  blade"

        if not self.paused:
            self.motion.push_samples(samples, dt)

        if self.paused:
            return

        s = self.engine.settings
        self.elapsed += dt
        self.spawn_interval = max(
            s.spawn_interval_min,
            s.spawn_interval - self.elapsed * 0.015,
        )

        self.spawn_timer -= dt
        if self.spawn_timer <= 0 and self.pool.alive_count() < s.max_active_objects:
            spawn_random(
                self.pool,
                float(s.width),
                float(s.height),
                s.gravity,
                apex_min_from_bottom=s.spawn_apex_min_from_bottom,
                apex_max_from_bottom=s.spawn_apex_max_from_bottom,
            )
            self.spawn_timer = self.spawn_interval

        for obj in self.pool.iter_alive():
            obj.update(s.gravity, dt)

        for obj in list(self.pool.iter_alive()):
            if obj.position.y > self._miss_y and obj.velocity.y > 0:
                self.pool.kill(obj)
                if not s.infinite_lives:
                    self.lives -= 1
                    self.combo = 0
                    if self.lives <= 0:
                        self._game_over()
                        return
                else:
                    self.combo = 0

        blade = self.controller.blade(dt)
        if blade.visible:
            self.trail.push_point(blade.pos)
            hits = collect_blade_hits(
                blade.pos,
                blade.prev,
                s.blade_radius,
                self.pool.iter_alive(),
            )
            if hits:
                for obj in hits:
                    self.score += obj.points * max(1, self.combo)
                    self.pool.kill(obj)
                self.combo += len(hits)

        self.trail.update(dt)

    def _game_over(self) -> None:
        best = max(self.engine.settings.best_score, self.score)
        self.engine.settings.best_score = best
        self.engine.set_scene("game_over", score=self.score, best=best)

    def draw(self, surface: pygame.Surface, alpha: float = 0.0) -> None:
        s = self.engine.settings
        surface.fill(s.bg)
        pygame.draw.rect(surface, (20, 24, 32), pygame.Rect(0, 0, s.width, 4))

        for obj in self.pool.iter_alive():
            draw_object(surface, obj, alpha, antialias=s.antialiasing)

        self.trail.draw(surface, s.cyan, antialias=s.antialiasing)

        blade = self.controller.blade(0.0, alpha)
        if blade.visible:
            draw_blade(surface, blade.pos, s.cyan, core=s.white, antialias=s.antialiasing)

        draw_hud(
            surface,
            self.engine.fonts,
            s,
            score=self.score,
            lives=self.lives,
            combo=self.combo,
            fps=self.engine.fps,
            controller_label=self._conn_label,
        )

        if s.debug:
            hub = getattr(self.engine, "hub", None)
            if hub is not None:
                draw_sensor_debug(
                    surface,
                    self.engine.fonts,
                    s,
                    hub.snapshot(),
                    processed=self.engine.processor.last,
                    aim_mapper=self.engine.aim_mapper,
                    calibrated=self.engine.processor.calibration.calibrated,
                    capturing=self.engine.processor.capturing_calibration,
                    recording=self.engine.processor.recorder.recording,
                    topleft=(24, 140),
                )

        if not self.paused:
            self.sensitivity_ui.draw(surface, self.engine.fonts)

        if self.paused:
            self.pause_ui.draw(surface)
