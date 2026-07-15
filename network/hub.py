"""Connection hub shared between network thread and game loop."""

from __future__ import annotations

import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto

from network.packet import SensorPacket

# Player colors for future multi-cursor support
CLIENT_COLORS = (
    "#22d3ee",  # cyan
    "#f0398b",  # magenta
    "#a3e635",  # lime
    "#fbbf24",  # amber
    "#818cf8",  # indigo
    "#fb7185",  # rose
)


class ControlAction(Enum):
    """Remote control events from phone → game loop."""

    CALIBRATE_START = auto()
    CALIBRATE_STOP = auto()
    RECENTER = auto()
    START_GAME = auto()
    STOP_GAME = auto()


@dataclass
class ControlEvent:
    action: ControlAction
    client_id: str = ""


@dataclass
class ConnectionState:
    connected: bool = False
    client_count: int = 0
    packets_received: int = 0
    last_packet: SensorPacket | None = None
    last_arrival: float = 0.0
    hz: float = 0.0
    url: str = ""
    error: str = ""
    latency_ms: float = 0.0
    active_client_id: str = ""
    active_client_color: str = CLIENT_COLORS[0]

    # Internal rate tracking
    _hz_window_start: float = field(default=0.0, repr=False)
    _hz_count: int = field(default=0, repr=False)


class NetworkHub:
    """
    Thread-safe bridge: WebSocket server pushes SensorPackets here;
    the game loop drains them each frame.
    """

    def __init__(self, max_queue: int = 256) -> None:
        self.queue: queue.Queue[SensorPacket] = queue.Queue(maxsize=max_queue)
        self.control_queue: queue.Queue[ControlEvent] = queue.Queue(maxsize=32)
        self.state = ConnectionState()
        self._lock = threading.Lock()
        self._next_color_idx = 0
        self._client_ids: dict[str, str] = {}  # ws_id -> color

    def set_url(self, url: str) -> None:
        with self._lock:
            self.state.url = url

    def set_error(self, message: str) -> None:
        with self._lock:
            self.state.error = message

    def assign_client(self, ws_id: str) -> tuple[str, str]:
        """Return (client_id, hex_color) for a new connection."""
        client_id = str(uuid.uuid4())[:8]
        color = CLIENT_COLORS[self._next_color_idx % len(CLIENT_COLORS)]
        self._next_color_idx += 1
        with self._lock:
            self._client_ids[ws_id] = color
            self.state.active_client_id = client_id
            self.state.active_client_color = color
        return client_id, color

    def release_client(self, ws_id: str) -> None:
        with self._lock:
            self._client_ids.pop(ws_id, None)

    def on_client_connect(self) -> None:
        with self._lock:
            self.state.client_count += 1
            self.state.connected = self.state.client_count > 0
            self.state.error = ""

    def on_client_disconnect(self) -> None:
        with self._lock:
            self.state.client_count = max(0, self.state.client_count - 1)
            self.state.connected = self.state.client_count > 0
            if not self.state.connected:
                self.state.last_packet = None
                self.state.hz = 0.0
                self.state.latency_ms = 0.0
                self.state.active_client_id = ""
                self.state.active_client_color = CLIENT_COLORS[0]

    def push_packet(self, packet: SensorPacket) -> None:
        try:
            self.queue.put_nowait(packet)
        except queue.Full:
            # Drop oldest then push — prefer freshest samples
            try:
                self.queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self.queue.put_nowait(packet)
            except queue.Full:
                return

        now = packet.arrival_time
        with self._lock:
            self.state.packets_received += 1
            self.state.last_packet = packet
            self.state.last_arrival = now
            if self.state._hz_window_start <= 0:
                self.state._hz_window_start = now
            self.state._hz_count += 1
            elapsed = now - self.state._hz_window_start
            if elapsed >= 0.5:
                self.state.hz = self.state._hz_count / elapsed
                self.state._hz_window_start = now
                self.state._hz_count = 0

    def record_latency(self, rtt_ms: float) -> None:
        """Store measured round-trip latency from PING/PONG."""
        with self._lock:
            # Exponential moving average for stability
            if self.state.latency_ms <= 0:
                self.state.latency_ms = rtt_ms
            else:
                self.state.latency_ms = self.state.latency_ms * 0.7 + rtt_ms * 0.3

    def push_control(self, action: ControlAction, client_id: str = "") -> None:
        try:
            self.control_queue.put_nowait(ControlEvent(action=action, client_id=client_id))
        except queue.Full:
            try:
                self.control_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self.control_queue.put_nowait(ControlEvent(action=action, client_id=client_id))
            except queue.Full:
                pass

    def drain(self, max_n: int = 64) -> list[SensorPacket]:
        out: list[SensorPacket] = []
        for _ in range(max_n):
            try:
                out.append(self.queue.get_nowait())
            except queue.Empty:
                break
        return out

    def drain_controls(self, max_n: int = 8) -> list[ControlEvent]:
        out: list[ControlEvent] = []
        for _ in range(max_n):
            try:
                out.append(self.control_queue.get_nowait())
            except queue.Empty:
                break
        return out

    def snapshot(self) -> ConnectionState:
        with self._lock:
            return ConnectionState(
                connected=self.state.connected,
                client_count=self.state.client_count,
                packets_received=self.state.packets_received,
                last_packet=self.state.last_packet,
                last_arrival=self.state.last_arrival,
                hz=self.state.hz,
                url=self.state.url,
                error=self.state.error,
                latency_ms=self.state.latency_ms,
                active_client_id=self.state.active_client_id,
                active_client_color=self.state.active_client_color,
            )

    def seconds_since_packet(self) -> float:
        with self._lock:
            if self.state.last_arrival <= 0:
                return float("inf")
            return time.perf_counter() - self.state.last_arrival
