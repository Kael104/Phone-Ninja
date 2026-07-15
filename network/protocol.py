"""WebSocket message types and helpers."""

from __future__ import annotations

from enum import Enum
from typing import Any


PROTOCOL_VERSION = 1

# WebSocket close code sent when a client fails pairing-token validation.
# Uses the 4000-4999 private-use range reserved for application close codes.
WS_CLOSE_UNAUTHORIZED = 4401


class MessageType(str, Enum):
    HELLO = "hello"
    SENSOR = "sensor"
    HEARTBEAT = "heartbeat"
    ACK = "ack"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"
    CALIBRATE = "calibrate"
    START_GAME = "start_game"
    STOP_GAME = "stop_game"
    DISCONNECT = "disconnect"


def make_hello(*, client_id: str = "", color: str = "") -> dict[str, Any]:
    msg: dict[str, Any] = {
        "type": MessageType.HELLO.value,
        "version": PROTOCOL_VERSION,
        "role": "server",
    }
    if client_id:
        msg["client_id"] = client_id
    if color:
        msg["color"] = color
    return msg


def make_ack(ok: bool = True, detail: str = "") -> dict[str, Any]:
    return {"type": MessageType.ACK.value, "ok": ok, "detail": detail}


def make_pong(echo_ts: float) -> dict[str, Any]:
    """Echo phone client timestamp for RTT / latency measurement."""
    return {"type": MessageType.PONG.value, "ts": echo_ts}


def make_error(detail: str) -> dict[str, Any]:
    return {"type": MessageType.ERROR.value, "detail": detail}


def parse_type(data: dict[str, Any]) -> str:
    return str(data.get("type", ""))
