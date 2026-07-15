"""Drawing: background, shapes, slice trail, HUD."""

from __future__ import annotations

import pygame
from pygame import gfxdraw

from config.settings import Settings
from controller.base import SliceInput
from game.objects import GameObject, ShapeKind
from game.physics import Vector2


_GLOW_CACHE: dict[tuple[int, int, int], list[tuple[pygame.Surface, int]]] = {}


def _aa_circle(
    surface: pygame.Surface,
    center: tuple[int, int],
    radius: int,
    color: tuple[int, int, int],
    *,
    antialias: bool,
    width: int = 0,
) -> None:
    if radius <= 0:
        return
    if antialias:
        x, y = center
        if width <= 0:
            gfxdraw.filled_circle(surface, x, y, radius, color)
            gfxdraw.aacircle(surface, x, y, radius, color)
        else:
            gfxdraw.aacircle(surface, x, y, radius, color)
            if radius > width:
                gfxdraw.aacircle(surface, x, y, radius - width, color)
    elif width <= 0:
        pygame.draw.circle(surface, color, center, radius)
    else:
        pygame.draw.circle(surface, color, center, radius, width=width)


def _aa_polygon(
    surface: pygame.Surface,
    pts: list[tuple[int, int]],
    color: tuple[int, int, int],
    *,
    antialias: bool,
    width: int = 0,
) -> None:
    if len(pts) < 3:
        return
    if antialias:
        if width <= 0:
            gfxdraw.filled_polygon(surface, pts, color)
            gfxdraw.aapolygon(surface, pts, color)
        else:
            gfxdraw.aapolygon(surface, pts, color)
    elif width <= 0:
        pygame.draw.polygon(surface, color, pts)
    else:
        pygame.draw.polygon(surface, color, pts, width=width)


def _aa_line(
    surface: pygame.Surface,
    a: tuple[int, int],
    b: tuple[int, int],
    color: tuple[int, int, int],
    width: int,
    *,
    antialias: bool,
) -> None:
    if antialias:
        if width <= 1:
            gfxdraw.line(surface, a[0], a[1], b[0], b[1], color)
            pygame.draw.aaline(surface, color, a, b)
            return
        pygame.draw.line(surface, color, a, b, width)
        for offset in range(-(width // 2), width // 2 + 1):
            if offset == 0:
                continue
            if a[0] == b[0]:
                pygame.draw.aaline(
                    surface, color, (a[0] + offset, a[1]), (b[0] + offset, b[1])
                )
            elif a[1] == b[1]:
                pygame.draw.aaline(
                    surface, color, (a[0], a[1] + offset), (b[0], b[1] + offset)
                )
            else:
                pygame.draw.aaline(
                    surface, color, (a[0], a[1] + offset), (b[0], b[1] + offset)
                )
    else:
        pygame.draw.line(surface, color, a, b, width)


def _glow_layers(color: tuple[int, int, int]) -> list[tuple[pygame.Surface, int]]:
    cached = _GLOW_CACHE.get(color)
    if cached is not None:
        return cached
    layers: list[tuple[pygame.Surface, int]] = []
    for r, alpha in ((22, 40), (16, 70), (10, 120)):
        glow = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*color, alpha), (r, r), r)
        layers.append((glow, r))
    _GLOW_CACHE[color] = layers
    return layers


class SliceTrail:
    """Short-lived trail segments for visual feedback."""

    def __init__(self, max_points: int = 24, ttl: float = 0.18) -> None:
        self.max_points = max_points
        self.ttl = ttl
        self._points: list[tuple[Vector2, float]] = []

    def push(self, slice_input: SliceInput) -> None:
        self.push_point(slice_input.end)

    def push_point(self, pos: Vector2) -> None:
        self._points.append((pos.copy(), self.ttl))
        if len(self._points) > self.max_points:
            self._points = self._points[-self.max_points :]

    def update(self, dt: float) -> None:
        alive: list[tuple[Vector2, float]] = []
        for pos, life in self._points:
            life -= dt
            if life > 0:
                alive.append((pos, life))
        self._points = alive

    def clear(self) -> None:
        self._points.clear()

    def draw(
        self,
        surface: pygame.Surface,
        color: tuple[int, int, int],
        *,
        antialias: bool = True,
    ) -> None:
        if len(self._points) < 2:
            return
        for i in range(1, len(self._points)):
            a, life_a = self._points[i - 1]
            b, life_b = self._points[i]
            alpha = max(life_a, life_b) / self.ttl
            width = max(2, int(8 * alpha))
            c = tuple(int(ch * (0.4 + 0.6 * alpha)) for ch in color)
            _aa_line(
                surface,
                a.as_int_tuple(),
                b.as_int_tuple(),
                c,
                width,
                antialias=antialias,
            )


def draw_object(
    surface: pygame.Surface,
    obj: GameObject,
    alpha: float = 1.0,
    *,
    antialias: bool = True,
) -> None:
    if not obj.alive:
        return
    pos = obj.render_position(alpha)
    pos_int = (int(pos.x), int(pos.y))
    if obj.kind == ShapeKind.CIRCLE:
        radius = int(obj.radius)
        _aa_circle(surface, pos_int, radius, obj.color, antialias=antialias)
        _aa_circle(
            surface,
            pos_int,
            radius,
            (255, 255, 255),
            antialias=antialias,
            width=2,
        )
        return
    pts = [(int(x), int(y)) for x, y in obj.polygon_points(center=pos)]
    if len(pts) >= 3:
        _aa_polygon(surface, pts, obj.color, antialias=antialias)
        _aa_polygon(surface, pts, (255, 255, 255), antialias=antialias, width=2)


def draw_hud(
    surface: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    settings: Settings,
    score: int,
    lives: int,
    combo: int,
    fps: float,
    controller_label: str,
) -> None:
    body = fonts["body"]
    small = fonts["small"]
    score_surf = body.render(f"Score  {score}", True, settings.white)
    if settings.infinite_lives:
        lives_text = "Lives  ∞"
        lives_color = settings.amber
    else:
        lives_text = f"Lives  {lives}"
        lives_color = settings.magenta
    lives_surf = body.render(lives_text, True, lives_color)
    surface.blit(score_surf, (24, 18))
    surface.blit(lives_surf, (24, 58))
    if combo > 1:
        combo_surf = body.render(f"Combo x{combo}", True, settings.amber)
        surface.blit(combo_surf, (24, 98))
    conn = small.render(controller_label, True, settings.lime)
    surface.blit(conn, (settings.width - conn.get_width() - 24, 18))
    if settings.debug:
        fps_surf = small.render(f"{fps:.0f} FPS", True, settings.muted)
        surface.blit(fps_surf, (settings.width - fps_surf.get_width() - 24, 46))
        if settings.infinite_lives:
            dbg = small.render("DEBUG  infinite lives", True, settings.amber)
            surface.blit(dbg, (settings.width - dbg.get_width() - 24, 70))


def draw_blade(
    surface: pygame.Surface,
    pos: Vector2,
    color: tuple[int, int, int],
    *,
    core: tuple[int, int, int] = (255, 255, 255),
    antialias: bool = True,
) -> None:
    """Glowing floating blade reticle (always visible)."""
    x, y = int(pos.x), int(pos.y)
    for glow, r in _glow_layers(color):
        surface.blit(glow, (x - r, y - r))
    _aa_circle(surface, (x, y), 8, color, antialias=antialias)
    _aa_circle(surface, (x, y), 4, core, antialias=antialias)
    _aa_line(surface, (x - 14, y), (x + 14, y), core, 2, antialias=antialias)
    _aa_line(surface, (x, y - 14), (x, y + 14), core, 2, antialias=antialias)


def draw_slice_segment(
    surface: pygame.Surface,
    slice_input: SliceInput | None,
    color: tuple[int, int, int],
    *,
    antialias: bool = True,
) -> None:
    if slice_input is None:
        return
    _aa_line(
        surface,
        slice_input.start.as_int_tuple(),
        slice_input.end.as_int_tuple(),
        color,
        5,
        antialias=antialias,
    )


def draw_sensor_debug(
    surface: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    settings: Settings,
    snap: "ConnectionState",  # noqa: F821
    *,
    processed: "ProcessedSample | None" = None,  # noqa: F821
    aim_mapper: "AimMapper | None" = None,  # noqa: F821
    calibrated: bool = False,
    capturing: bool = False,
    recording: bool = False,
    topleft: tuple[int, int] = (24, 140),
) -> None:
    """Live connection + IMU readout with cursor, latency, and filter info."""
    body = fonts["body"]
    small = fonts["small"]
    x, y = topleft
    status = "CONNECTED" if snap.connected else "WAITING"
    status_color = settings.lime if snap.connected else settings.amber
    surface.blit(body.render(f"Phone  {status}", True, status_color), (x, y))
    y += 36
    surface.blit(small.render(f"Rate  {snap.hz:.0f} Hz", True, settings.white), (x, y))
    y += 22
    if snap.latency_ms > 0:
        surface.blit(
            small.render(f"Latency  {snap.latency_ms:.0f} ms", True, settings.white),
            (x, y),
        )
        y += 22
    if snap.active_client_id:
        surface.blit(
            small.render(f"Client  {snap.active_client_id}", True, settings.cyan),
            (x, y),
        )
        y += 22
    surface.blit(
        small.render(f"Packets  {snap.packets_received}", True, settings.muted),
        (x, y),
    )
    y += 22
    surface.blit(
        small.render(f"Filter  {settings.filter_mode}", True, settings.muted),
        (x, y),
    )
    y += 22
    if aim_mapper is not None:
        surface.blit(
            small.render(
                f"Map  dz {aim_mapper.deadzone_deg:.1f}°  max {aim_mapper.max_angle_deg:.0f}°  "
                f"sx {aim_mapper.sensitivity_x:.1f} sy {aim_mapper.sensitivity_y:.1f}",
                True,
                settings.muted,
            ),
            (x, y),
        )
        y += 22
    flags = []
    if calibrated:
        flags.append("CAL")
    if capturing:
        flags.append("CAPTURING")
    if recording:
        flags.append("REC")
    if aim_mapper is not None and aim_mapper.calibrated:
        flags.append("AIM")
    if flags:
        surface.blit(small.render(" · ".join(flags), True, settings.amber), (x, y))
        y += 22
    if snap.error:
        surface.blit(small.render(snap.error[:48], True, settings.magenta), (x, y))
        y += 22
    if processed is not None:
        c = processed.calibrated
        f = processed.filtered
        lines = [
            f"filt  {f.ax:+6.2f} {f.ay:+6.2f} {f.az:+6.2f}",
            f"cal   {c.ax:+6.2f} {c.ay:+6.2f} {c.az:+6.2f}",
            f"|a| {processed.accel_mag:5.2f}   |g| {processed.gyro_mag:5.2f}",
        ]
        if processed.has_orientation:
            lines.append(
                f"orient α {processed.alpha:+5.1f}  β {processed.beta:+5.1f}  γ {processed.gamma:+5.1f}"
            )
            if aim_mapper is not None:
                pos = aim_mapper.position
                lines.append(
                    f"aim  yaw {aim_mapper.last_yaw_deg:+5.1f}  pitch {aim_mapper.last_pitch_deg:+5.1f}"
                )
                lines.append(f"cursor  {pos.x:6.0f}  {pos.y:6.0f}")
        for line in lines:
            surface.blit(small.render(line, True, settings.cyan), (x, y))
            y += 20
        return
    pkt = snap.last_packet
    if pkt is None:
        surface.blit(small.render("No sensor data yet", True, settings.muted), (x, y))
        return
    lines = [
        f"ax {pkt.ax:+7.2f}   ay {pkt.ay:+7.2f}   az {pkt.az:+7.2f}",
        f"gx {pkt.gx:+7.2f}   gy {pkt.gy:+7.2f}   gz {pkt.gz:+7.2f}",
    ]
    for line in lines:
        surface.blit(small.render(line, True, settings.cyan), (x, y))
        y += 22

