"""Game configuration (in-memory settings for M0)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Settings:
    width: int = 1280
    height: int = 720
    fps: int = 60
    fixed_dt: float = 1.0 / 60.0
    vsync: bool = True
    display_mode: str = "windowed"  # windowed | borderless | fullscreen
    debug: bool = True
    antialiasing: bool = True
    infinite_lives: bool = True  # debug play: misses never end the game

    # Networking (local LAN only)
    # "auto" binds only to the primary LAN interface (not 0.0.0.0), limiting
    # exposure to the local subnet. Set to "0.0.0.0" to bind all interfaces.
    ws_host: str = "auto"
    ws_port: int = 8765
    require_pairing: bool = True  # reject /ws without session token from QR URL

    # Sensor pipeline (M2)
    filter_mode: str = "ema"  # ema | moving_avg | lowpass
    ema_alpha: float = 0.35
    ma_window: int = 5
    lowpass_tau: float = 0.04
    sensor_sensitivity: float = 1.0
    calibration_min_samples: int = 30
    record_sensors: bool = False

    # Gestures (M3, optional future power slash)
    flick_accel_threshold: float = 6.0
    flick_gyro_threshold: float = 8.0
    flick_gyro_weight: float = 0.35
    flick_cooldown: float = 0.28
    slice_base_length: float = 420.0
    slice_length_per_intensity: float = 18.0

    # Pointer aim (always-visible blade)
    pointer_view_distance_cm: float = 60.0
    pointer_screen_width_cm: float = 34.0
    pointer_screen_height_cm: float = 19.0
    aim_smoothing: float = 0.35
    aim_smoothing_tau: float = 0.04
    aim_invert_x: bool = False
    aim_invert_y: bool = True
    aim_sensitivity_x: float = 1.0
    aim_sensitivity_y: float = 1.3
    aim_deadzone_deg: float = 1.5
    aim_max_angle_deg: float = 45.0
    aim_roll_compensation: bool = True
    aim_roll_offset_deg: float = 0.0
    blade_radius: float = 28.0

    # Gameplay
    starting_lives: int = 3
    gravity: float = 980.0
    spawn_interval: float = 1.1
    spawn_interval_min: float = 0.45
    max_active_objects: int = 12
    miss_y: float | None = None  # defaults to height + margin in engine
    spawn_apex_min_from_bottom: float = 0.25  # lowest peak (1/4 up from bottom)
    spawn_apex_max_from_bottom: float = 0.80  # highest peak (4/5 up from bottom)

    # Slice
    min_slice_speed: float = 80.0
    slice_trail_max: int = 24
    slice_trail_ttl: float = 0.18

    # Colors (Neon Arcade)
    bg: tuple[int, int, int] = (14, 17, 22)
    cyan: tuple[int, int, int] = (34, 211, 238)
    magenta: tuple[int, int, int] = (240, 57, 139)
    lime: tuple[int, int, int] = (163, 230, 53)
    amber: tuple[int, int, int] = (251, 191, 36)
    white: tuple[int, int, int] = (240, 244, 248)
    muted: tuple[int, int, int] = (120, 130, 145)

    title: str = "Phone Ninja"

    # Session (not persisted)
    best_score: int = field(default=0, repr=False)


SETTINGS = Settings()
