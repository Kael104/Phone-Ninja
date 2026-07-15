"""Scene base, buttons, simple menu widgets."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

import pygame

from config.settings import Settings


class Scene(ABC):
    def __init__(self, engine: "Engine") -> None:  # noqa: F821
        self.engine = engine

    @abstractmethod
    def handle_event(self, event: pygame.event.Event) -> None: ...

    @abstractmethod
    def update(self, dt: float) -> None: ...

    @abstractmethod
    def draw(self, surface: pygame.Surface, alpha: float = 0.0) -> None: ...

    def on_enter(self) -> None:
        pass

    def on_exit(self) -> None:
        pass


class Button:
    def __init__(
        self,
        rect: pygame.Rect,
        label: str,
        on_click: Callable[[], None],
        settings: Settings,
        accent: tuple[int, int, int] | None = None,
    ) -> None:
        self.rect = rect
        self.label = label
        self.on_click = on_click
        self.settings = settings
        self.accent = accent or settings.cyan
        self._hover = False

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self._hover = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.on_click()

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        s = self.settings
        fill = self.accent if self._hover else (30, 36, 44)
        border = self.accent
        if s.antialiasing:
            scale = 3
            w, h = self.rect.width * scale, self.rect.height * scale
            hi = pygame.Surface((w, h), pygame.SRCALPHA)
            hi_rect = pygame.Rect(0, 0, w, h)
            pygame.draw.rect(hi, fill, hi_rect, border_radius=8 * scale)
            pygame.draw.rect(
                hi,
                border,
                hi_rect,
                width=2 * scale,
                border_radius=8 * scale,
            )
            lo = pygame.transform.smoothscale(hi, (self.rect.width, self.rect.height))
            surface.blit(lo, self.rect.topleft)
        else:
            pygame.draw.rect(surface, fill, self.rect, border_radius=8)
            pygame.draw.rect(surface, border, self.rect, width=2, border_radius=8)
        text = font.render(self.label, True, s.white)
        text_rect = text.get_rect(center=self.rect.center)
        surface.blit(text, text_rect)


def _draw_rounded_box(
    surface: pygame.Surface,
    rect: pygame.Rect,
    fill: tuple[int, int, int],
    border: tuple[int, int, int],
    settings: Settings,
    *,
    border_width: int = 2,
    radius: int = 8,
) -> None:
    if settings.antialiasing:
        scale = 3
        w, h = rect.width * scale, rect.height * scale
        hi = pygame.Surface((w, h), pygame.SRCALPHA)
        hi_rect = pygame.Rect(0, 0, w, h)
        pygame.draw.rect(hi, fill, hi_rect, border_radius=radius * scale)
        pygame.draw.rect(
            hi,
            border,
            hi_rect,
            width=border_width * scale,
            border_radius=radius * scale,
        )
        lo = pygame.transform.smoothscale(hi, (rect.width, rect.height))
        surface.blit(lo, rect.topleft)
    else:
        pygame.draw.rect(surface, fill, rect, border_radius=radius)
        pygame.draw.rect(surface, border, rect, width=border_width, border_radius=radius)


class Dropdown:
    """Simple single-select dropdown for settings."""

    def __init__(
        self,
        rect: pygame.Rect,
        options: list[tuple[str, str]],
        current: str,
        on_select: Callable[[str], None],
        settings: Settings,
        accent: tuple[int, int, int] | None = None,
    ) -> None:
        self.rect = rect
        self.options = options
        self.current = current
        self.on_select = on_select
        self.settings = settings
        self.accent = accent or settings.cyan
        self.open = False
        self._hover_header = False
        self._hover_index = -1
        self._row_h = rect.height

    def _label_for(self, value: str) -> str:
        for opt_value, opt_label in self.options:
            if opt_value == value:
                return opt_label
        return value

    def _option_rect(self, index: int) -> pygame.Rect:
        return pygame.Rect(
            self.rect.x,
            self.rect.y + self.rect.height + index * self._row_h,
            self.rect.width,
            self._row_h,
        )

    def _option_at(self, pos: tuple[int, int]) -> int:
        for i in range(len(self.options)):
            if self._option_rect(i).collidepoint(pos):
                return i
        return -1

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self._hover_header = self.rect.collidepoint(event.pos)
            if self.open:
                self._hover_index = self._option_at(event.pos)
            else:
                self._hover_index = -1
            return False

        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False

        if self.open:
            idx = self._option_at(event.pos)
            if idx >= 0:
                value, _ = self.options[idx]
                self.current = value
                self.on_select(value)
                self.open = False
                self._hover_index = -1
                return True
            self.open = False
            self._hover_index = -1
            return True

        if self.rect.collidepoint(event.pos):
            self.open = True
            self._hover_index = -1
            return True

        return False

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        s = self.settings
        fill = self.accent if self._hover_header or self.open else (30, 36, 44)
        _draw_rounded_box(surface, self.rect, fill, self.accent, s)
        label = font.render(self._label_for(self.current), True, s.white)
        label_rect = label.get_rect(midleft=(self.rect.x + 14, self.rect.centery))
        surface.blit(label, label_rect)
        caret = font.render("v", True, s.muted)
        surface.blit(caret, caret.get_rect(midright=(self.rect.right - 12, self.rect.centery)))

    def draw_overlay(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        if not self.open:
            return
        s = self.settings
        for i, (value, label) in enumerate(self.options):
            row = self._option_rect(i)
            selected = value == self.current
            hovered = i == self._hover_index
            fill = self.accent if selected else ((40, 48, 58) if hovered else (30, 36, 44))
            _draw_rounded_box(surface, row, fill, self.accent, s, radius=6)
            text = font.render(label, True, s.white)
            surface.blit(text, text.get_rect(midleft=(row.x + 14, row.centery)))


class AimSensitivityPanel:
    """On-screen +/- controls for live X/Y aim sensitivity tuning."""

    _MIN = 0.1
    _MAX = 3.0
    _STEP = 0.1

    def __init__(self, engine: "Engine") -> None:  # noqa: F821
        self.engine = engine
        s = engine.settings
        self._panel = pygame.Rect(s.width - 228, s.height - 132, 204, 108)
        self._buttons: list[Button] = []
        self._layout()

    def _layout(self) -> None:
        s = self.engine.settings
        self._panel = pygame.Rect(s.width - 228, s.height - 132, 204, 108)
        px = self._panel.x
        row_y = (self._panel.y + 36, self._panel.y + 76)
        btn_w, btn_h = 36, 32
        minus_x = px + 52
        plus_x = px + 152
        self._buttons = [
            Button(
                pygame.Rect(minus_x, row_y[0], btn_w, btn_h),
                "-",
                lambda: self._adjust("x", -self._STEP),
                s,
                s.magenta,
            ),
            Button(
                pygame.Rect(plus_x, row_y[0], btn_w, btn_h),
                "+",
                lambda: self._adjust("x", self._STEP),
                s,
                s.lime,
            ),
            Button(
                pygame.Rect(minus_x, row_y[1], btn_w, btn_h),
                "-",
                lambda: self._adjust("y", -self._STEP),
                s,
                s.magenta,
            ),
            Button(
                pygame.Rect(plus_x, row_y[1], btn_w, btn_h),
                "+",
                lambda: self._adjust("y", self._STEP),
                s,
                s.lime,
            ),
        ]

    def _adjust(self, axis: str, delta: float) -> None:
        s = self.engine.settings
        aim = self.engine.aim_mapper
        if axis == "x":
            value = max(self._MIN, min(self._MAX, round(s.aim_sensitivity_x + delta, 2)))
            s.aim_sensitivity_x = value
            aim.sensitivity_x = value
        else:
            value = max(self._MIN, min(self._MAX, round(s.aim_sensitivity_y + delta, 2)))
            s.aim_sensitivity_y = value
            aim.sensitivity_y = value

    def handle_event(self, event: pygame.event.Event) -> None:
        for btn in self._buttons:
            btn.handle_event(event)

    def draw(self, surface: pygame.Surface, fonts: dict[str, pygame.font.Font]) -> None:
        s = self.engine.settings
        aim = self.engine.aim_mapper
        small = fonts["small"]
        body = fonts["body"]

        pygame.draw.rect(surface, (20, 24, 32), self._panel, border_radius=8)
        pygame.draw.rect(surface, s.muted, self._panel, width=1, border_radius=8)

        title = small.render("Aim sensitivity", True, s.muted)
        surface.blit(title, (self._panel.x + 12, self._panel.y + 8))

        x_label = body.render("X", True, s.cyan)
        y_label = body.render("Y", True, s.cyan)
        surface.blit(x_label, (self._panel.x + 16, self._panel.y + 40))
        surface.blit(y_label, (self._panel.x + 16, self._panel.y + 80))

        x_val = body.render(f"{aim.sensitivity_x:.1f}", True, s.white)
        y_val = body.render(f"{aim.sensitivity_y:.1f}", True, s.white)
        surface.blit(x_val, x_val.get_rect(center=(self._panel.x + 120, self._panel.y + 48)))
        surface.blit(y_val, y_val.get_rect(center=(self._panel.x + 120, self._panel.y + 88)))

        for btn in self._buttons:
            btn.draw(surface, body)


class MainMenuScene(Scene):
    def __init__(self, engine: "Engine") -> None:  # noqa: F821
        super().__init__(engine)
        s = engine.settings
        cx = s.width // 2
        self.buttons = [
            Button(
                pygame.Rect(cx - 140, 280, 280, 56),
                "Play",
                lambda: engine.set_scene("gameplay"),
                s,
                s.lime,
            ),
            Button(
                pygame.Rect(cx - 140, 356, 280, 56),
                "Connect Phone",
                lambda: engine.set_scene("connection"),
                s,
                s.cyan,
            ),
            Button(
                pygame.Rect(cx - 140, 432, 280, 56),
                "Settings",
                lambda: engine.set_scene("settings"),
                s,
                s.amber,
            ),
            Button(
                pygame.Rect(cx - 140, 508, 280, 56),
                "Exit",
                engine.quit,
                s,
                s.magenta,
            ),
        ]

    def handle_event(self, event: pygame.event.Event) -> None:
        for btn in self.buttons:
            btn.handle_event(event)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self.engine.set_scene("gameplay")

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface, alpha: float = 0.0) -> None:
        s = self.engine.settings
        surface.fill(s.bg)
        title_font = self.engine.fonts["title"]
        body_font = self.engine.fonts["body"]
        title = title_font.render(s.title, True, s.cyan)
        surface.blit(title, title.get_rect(center=(s.width // 2, 140)))
        subtitle = body_font.render(
            "Point phone at screen or move mouse — blade cuts on touch  ·  Esc pause",
            True,
            s.muted,
        )
        surface.blit(subtitle, subtitle.get_rect(center=(s.width // 2, 210)))
        for btn in self.buttons:
            btn.draw(surface, body_font)


class SettingsScene(Scene):
    """Display, gameplay, and aim options."""

    _AIM_MIN = 0.1
    _AIM_MAX = 3.0
    _AIM_STEP = 0.1
    _LIVES_MIN = 1
    _LIVES_MAX = 9

    def __init__(self, engine: "Engine") -> None:  # noqa: F821
        super().__init__(engine)
        self._rows: list[tuple[str, str]] = []
        self.buttons: list[Button] = []
        self._back: Button | None = None
        self._display_dropdown: Dropdown | None = None
        self._layout()

    def _layout(self) -> None:
        s = self.engine.settings
        cx = s.width // 2
        row_y = 190
        stride = 58
        control_x = cx + 80
        btn_w, btn_h = 88, 44
        step_w, step_h = 40, 44

        self._rows = [
            ("Display", "display_mode"),
            ("VSync", "vsync"),
            ("Antialiasing", "antialiasing"),
            ("Infinite lives", "infinite_lives"),
            ("Starting lives", "starting_lives"),
            ("Aim sensitivity X", "aim_x"),
            ("Aim sensitivity Y", "aim_y"),
        ]

        self.buttons = []
        for i, (_, key) in enumerate(self._rows):
            y = row_y + i * stride
            if key == "display_mode":
                self._display_dropdown = Dropdown(
                    pygame.Rect(control_x, y, 220, btn_h),
                    [
                        ("windowed", "Windowed"),
                        ("borderless", "Windowed Fullscreen"),
                        ("fullscreen", "Fullscreen"),
                    ],
                    s.display_mode,
                    self._set_display_mode,
                    s,
                    s.cyan,
                )
            elif key in {"vsync", "antialiasing", "infinite_lives"}:
                self.buttons.append(
                    Button(
                        pygame.Rect(control_x, y, btn_w, btn_h),
                        self._toggle_label(key),
                        lambda k=key: self._toggle_bool(k),
                        s,
                        s.cyan,
                    )
                )
            elif key == "starting_lives":
                self.buttons.extend(
                    [
                        Button(
                            pygame.Rect(control_x, y, step_w, step_h),
                            "-",
                            lambda: self._adjust_lives(-1),
                            s,
                            s.magenta,
                        ),
                        Button(
                            pygame.Rect(control_x + 108, y, step_w, step_h),
                            "+",
                            lambda: self._adjust_lives(1),
                            s,
                            s.lime,
                        ),
                    ]
                )
            elif key == "aim_x":
                self.buttons.extend(
                    [
                        Button(
                            pygame.Rect(control_x, y, step_w, step_h),
                            "-",
                            lambda: self._adjust_aim("x", -self._AIM_STEP),
                            s,
                            s.magenta,
                        ),
                        Button(
                            pygame.Rect(control_x + 108, y, step_w, step_h),
                            "+",
                            lambda: self._adjust_aim("x", self._AIM_STEP),
                            s,
                            s.lime,
                        ),
                    ]
                )
            elif key == "aim_y":
                self.buttons.extend(
                    [
                        Button(
                            pygame.Rect(control_x, y, step_w, step_h),
                            "-",
                            lambda: self._adjust_aim("y", -self._AIM_STEP),
                            s,
                            s.magenta,
                        ),
                        Button(
                            pygame.Rect(control_x + 108, y, step_w, step_h),
                            "+",
                            lambda: self._adjust_aim("y", self._AIM_STEP),
                            s,
                            s.lime,
                        ),
                    ]
                )

        self._back = Button(
            pygame.Rect(cx - 140, s.height - 120, 280, 56),
            "Back",
            lambda: self.engine.set_scene("menu"),
            s,
            s.muted,
        )

    def _toggle_label(self, key: str) -> str:
        s = self.engine.settings
        value = getattr(s, key)
        return "On" if value else "Off"

    def _toggle_bool(self, key: str) -> None:
        s = self.engine.settings
        setattr(s, key, not getattr(s, key))
        if key == "vsync":
            self.engine.apply_display_settings()
        self._sync_toggle_labels()

    def _set_display_mode(self, mode: str) -> None:
        s = self.engine.settings
        s.display_mode = mode
        if self._display_dropdown is not None:
            self._display_dropdown.current = mode
        self.engine.apply_display_settings()

    def _sync_toggle_labels(self) -> None:
        toggle_keys = ("vsync", "antialiasing", "infinite_lives")
        toggle_btns = [
            btn for btn in self.buttons if btn.label in {"On", "Off"}
        ]
        for btn, key in zip(toggle_btns, toggle_keys):
            btn.label = self._toggle_label(key)
        if self._display_dropdown is not None:
            self._display_dropdown.current = self.engine.settings.display_mode

    def _adjust_lives(self, delta: int) -> None:
        s = self.engine.settings
        s.starting_lives = max(
            self._LIVES_MIN,
            min(self._LIVES_MAX, s.starting_lives + delta),
        )

    def _adjust_aim(self, axis: str, delta: float) -> None:
        s = self.engine.settings
        aim = self.engine.aim_mapper
        if axis == "x":
            value = max(
                self._AIM_MIN,
                min(self._AIM_MAX, round(s.aim_sensitivity_x + delta, 2)),
            )
            s.aim_sensitivity_x = value
            aim.sensitivity_x = value
        else:
            value = max(
                self._AIM_MIN,
                min(self._AIM_MAX, round(s.aim_sensitivity_y + delta, 2)),
            )
            s.aim_sensitivity_y = value
            aim.sensitivity_y = value

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self._display_dropdown is not None and self._display_dropdown.open:
                self._display_dropdown.open = False
                return
            self.engine.set_scene("menu")
            return

        consumed = False
        if self._display_dropdown is not None:
            consumed = self._display_dropdown.handle_event(event)

        if consumed or (self._display_dropdown is not None and self._display_dropdown.open):
            return

        for btn in self.buttons:
            btn.handle_event(event)
        if self._back is not None:
            self._back.handle_event(event)

    def update(self, dt: float) -> None:
        self._sync_toggle_labels()

    def draw(self, surface: pygame.Surface, alpha: float = 0.0) -> None:
        s = self.engine.settings
        surface.fill(s.bg)
        title_font = self.engine.fonts["title"]
        body_font = self.engine.fonts["body"]

        title = title_font.render("Settings", True, s.cyan)
        surface.blit(title, title.get_rect(center=(s.width // 2, 100)))

        row_y = 190
        stride = 58
        label_x = s.width // 2 - 260
        value_x = s.width // 2 + 80

        for i, (label, key) in enumerate(self._rows):
            y = row_y + i * stride
            label_surf = body_font.render(label, True, s.white)
            surface.blit(label_surf, (label_x, y + 6))

            if key == "starting_lives":
                value = body_font.render(str(s.starting_lives), True, s.amber)
                surface.blit(value, value.get_rect(center=(value_x + 74, y + 22)))
            elif key == "aim_x":
                value = body_font.render(f"{s.aim_sensitivity_x:.1f}", True, s.amber)
                surface.blit(value, value.get_rect(center=(value_x + 74, y + 22)))
            elif key == "aim_y":
                value = body_font.render(f"{s.aim_sensitivity_y:.1f}", True, s.amber)
                surface.blit(value, value.get_rect(center=(value_x + 74, y + 22)))

        for btn in self.buttons:
            btn.draw(surface, body_font)
        if self._display_dropdown is not None:
            self._display_dropdown.draw(surface, body_font)
        if self._back is not None:
            self._back.draw(surface, body_font)
        if self._display_dropdown is not None:
            self._display_dropdown.draw_overlay(surface, body_font)


class ConnectionScene(Scene):
    """Pair phone via LAN HTTPS URL + QR; show live sensor pipeline debug."""

    def __init__(self, engine: "Engine") -> None:  # noqa: F821
        super().__init__(engine)
        s = engine.settings
        cx = s.width // 2
        self._qr: pygame.Surface | None = None
        self._qr_url = ""
        self._calib_msg = ""
        self._calib_timer = 0.0
        self.buttons = [
            Button(
                pygame.Rect(cx - 240, s.height - 140, 140, 52),
                "Skip",
                lambda: engine.set_scene("menu"),
                s,
                s.muted,
            ),
            Button(
                pygame.Rect(cx - 80, s.height - 140, 160, 52),
                "Calibrate",
                self._toggle_calibrate,
                s,
                s.amber,
            ),
            Button(
                pygame.Rect(cx + 100, s.height - 140, 140, 52),
                "Continue",
                lambda: engine.set_scene("menu"),
                s,
                s.lime,
            ),
        ]

    def on_enter(self) -> None:
        self._refresh_qr()
        self._calib_msg = ""
        self._calib_timer = 0.0

    def _toggle_calibrate(self) -> None:
        proc = self.engine.processor
        aim = self.engine.aim_mapper
        s = self.engine.settings
        if proc.capturing_calibration:
            ok_imu = proc.end_calibration_capture(min_samples=s.calibration_min_samples)
            ok_aim = aim.end_capture(min_samples=s.calibration_min_samples)
            if ok_imu and ok_aim:
                self._calib_msg = "Calibration saved (IMU + pointer)"
            elif ok_imu:
                self._calib_msg = "IMU saved; need more orientation samples"
            elif ok_aim:
                self._calib_msg = "Pointer saved; need more IMU samples"
            else:
                self._calib_msg = f"Need {s.calibration_min_samples}+ still samples"
            self._calib_timer = 3.0
        else:
            proc.begin_calibration_capture()
            aim.begin_capture()
            self._calib_msg = "Hold phone still…"
            self._calib_timer = 10.0

    def _recenter_aim(self) -> None:
        last = self.engine.processor.last
        if last is not None and last.has_orientation:
            self.engine.aim_mapper.recenter(last.alpha, last.beta, last.gamma)
            self._calib_msg = "Aim recentered"
            self._calib_timer = 2.0
        else:
            self._calib_msg = "No orientation data yet"
            self._calib_timer = 2.0

    def _refresh_qr(self) -> None:
        hub = getattr(self.engine, "hub", None)
        if hub is None:
            return
        snap = hub.snapshot()
        url = snap.url or f"https://…:{self.engine.settings.ws_port}/"
        if url == self._qr_url and self._qr is not None:
            return
        self._qr_url = url
        try:
            from network.qr_util import make_qr_surface

            self._qr = make_qr_surface(url)
        except Exception:
            self._qr = None

    def handle_event(self, event: pygame.event.Event) -> None:
        for btn in self.buttons:
            btn.handle_event(event)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.engine.set_scene("menu")
            elif event.key == pygame.K_c:
                self._toggle_calibrate()
            elif event.key == pygame.K_t:
                self._recenter_aim()
            elif event.key == pygame.K_v:
                rec = self.engine.processor.recorder
                if rec.recording:
                    path = rec.stop()
                    self._calib_msg = f"Saved {path.name}" if path else "Recording stopped"
                else:
                    path = rec.start()
                    self._calib_msg = f"Recording → {path.name}"
                self._calib_timer = 3.0

    def update(self, dt: float) -> None:
        samples = self.engine.ingest_sensors(max_n=128)
        for sample in samples:
            if sample.has_orientation:
                sample_dt = sample.dt if sample.dt > 0 else dt
                self.engine.aim_mapper.update(
                    sample.alpha,
                    sample.beta,
                    sample.gamma,
                    sample_dt,
                )
        self._refresh_qr()
        if self._calib_timer > 0:
            self._calib_timer -= dt
            # Auto-finish calibration after timer if still capturing
            proc = self.engine.processor
            if (
                proc.capturing_calibration
                and proc.calibration.sample_count() >= self.engine.settings.calibration_min_samples
            ):
                # Enough samples — user can press again; don't auto-stop mid-hold
                pass
            if self._calib_timer <= 0 and proc.capturing_calibration:
                self._toggle_calibrate()

    def draw(self, surface: pygame.Surface, alpha: float = 0.0) -> None:
        from game.renderer import draw_sensor_debug

        s = self.engine.settings
        surface.fill(s.bg)
        title = self.engine.fonts["title"].render("Connect Phone", True, s.cyan)
        surface.blit(title, title.get_rect(midtop=(s.width // 2, 36)))

        hub = getattr(self.engine, "hub", None)
        snap = hub.snapshot() if hub is not None else None
        url = (snap.url if snap else "") or "(starting server…)"
        body = self.engine.fonts["body"]
        small = self.engine.fonts["small"]

        hint = small.render(
            "Wi‑Fi · accept cert · Enable Motion · C calibrate · T recenter · V record",
            True,
            s.muted,
        )
        surface.blit(hint, hint.get_rect(center=(s.width // 2, 110)))

        url_surf = body.render(url, True, s.white)
        surface.blit(url_surf, url_surf.get_rect(center=(s.width // 2, 150)))

        server = getattr(self.engine, "server", None)
        if server is not None and getattr(server, "bound_all_interfaces", False):
            warn = small.render(
                "Warning: listening on all interfaces — use a trusted Wi‑Fi only",
                True,
                s.magenta,
            )
            surface.blit(warn, warn.get_rect(center=(s.width // 2, 176)))

        if self._qr is not None:
            qr_rect = self._qr.get_rect(center=(s.width // 2 - 220, 360))
            surface.blit(self._qr, qr_rect)
        else:
            placeholder = body.render("QR unavailable", True, s.muted)
            surface.blit(placeholder, placeholder.get_rect(center=(s.width // 2 - 220, 360)))

        if snap is not None:
            draw_sensor_debug(
                surface,
                self.engine.fonts,
                s,
                snap,
                processed=self.engine.processor.last,
                aim_mapper=self.engine.aim_mapper,
                calibrated=self.engine.processor.calibration.calibrated,
                capturing=self.engine.processor.capturing_calibration,
                recording=self.engine.processor.recorder.recording,
                topleft=(s.width // 2 + 20, 200),
            )

        if self._calib_msg and self._calib_timer > 0:
            msg = small.render(self._calib_msg, True, s.amber)
            surface.blit(msg, msg.get_rect(center=(s.width // 2, s.height - 170)))

        for btn in self.buttons:
            btn.draw(surface, body)



class GameOverScene(Scene):
    def __init__(self, engine: "Engine", score: int, best: int) -> None:  # noqa: F821
        super().__init__(engine)
        self.score = score
        self.best = best
        s = engine.settings
        cx = s.width // 2
        self.buttons = [
            Button(
                pygame.Rect(cx - 140, 360, 280, 56),
                "Retry",
                lambda: engine.set_scene("gameplay"),
                s,
                s.lime,
            ),
            Button(
                pygame.Rect(cx - 140, 440, 280, 56),
                "Menu",
                lambda: engine.set_scene("menu"),
                s,
                s.cyan,
            ),
        ]

    def handle_event(self, event: pygame.event.Event) -> None:
        for btn in self.buttons:
            btn.handle_event(event)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                self.engine.set_scene("gameplay")
            elif event.key == pygame.K_ESCAPE:
                self.engine.set_scene("menu")

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface, alpha: float = 0.0) -> None:
        s = self.engine.settings
        surface.fill(s.bg)
        title_font = self.engine.fonts["title"]
        body_font = self.engine.fonts["body"]
        title = title_font.render("Game Over", True, s.magenta)
        surface.blit(title, title.get_rect(center=(s.width // 2, 160)))
        score = body_font.render(f"Score  {self.score}", True, s.white)
        best = body_font.render(f"Best   {self.best}", True, s.amber)
        surface.blit(score, score.get_rect(center=(s.width // 2, 250)))
        surface.blit(best, best.get_rect(center=(s.width // 2, 300)))
        for btn in self.buttons:
            btn.draw(surface, body_font)


class PauseOverlay:
    """Drawn on top of frozen gameplay; not a full scene swap."""

    def __init__(self, engine: "Engine") -> None:  # noqa: F821
        self.engine = engine
        s = engine.settings
        cx = s.width // 2
        self._veil: pygame.Surface | None = None
        self._veil_size: tuple[int, int] = (0, 0)
        self.buttons = [
            Button(
                pygame.Rect(cx - 140, 280, 280, 52),
                "Resume",
                self._resume,
                s,
                s.lime,
            ),
            Button(
                pygame.Rect(cx - 140, 350, 280, 52),
                "Quit to Menu",
                lambda: engine.set_scene("menu"),
                s,
                s.magenta,
            ),
        ]

    def _resume(self) -> None:
        from game.game import GameplayScene

        scene = self.engine.scene
        if isinstance(scene, GameplayScene):
            scene.paused = False

    def handle_event(self, event: pygame.event.Event) -> None:
        for btn in self.buttons:
            btn.handle_event(event)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._resume()

    def _veil_surface(self, width: int, height: int) -> pygame.Surface:
        if self._veil is None or self._veil_size != (width, height):
            veil = pygame.Surface((width, height), pygame.SRCALPHA)
            veil.fill((0, 0, 0, 160))
            self._veil = veil
            self._veil_size = (width, height)
        return self._veil

    def draw(self, surface: pygame.Surface, alpha: float = 0.0) -> None:
        s = self.engine.settings
        surface.blit(self._veil_surface(s.width, s.height), (0, 0))
        title = self.engine.fonts["title"].render("Paused", True, s.white)
        surface.blit(title, title.get_rect(center=(s.width // 2, 180)))
        for btn in self.buttons:
            btn.draw(surface, self.engine.fonts["body"])
