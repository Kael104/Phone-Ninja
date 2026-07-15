"""M1 smoke tests for packets / cert helpers."""

from __future__ import annotations

import asyncio
import ssl
import time

import pytest
from aiohttp import ClientSession, ClientResponseError, WSMsgType

from network.cert import get_primary_lan_ip
from network.hub import ControlAction, NetworkHub
from network.packet import SensorPacket
from network.protocol import (
    WS_CLOSE_UNAUTHORIZED,
    MessageType,
    make_hello,
    make_pong,
    parse_type,
)
from network.websocket_server import MotionServer


def _ssl_no_verify() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _wait_for_server(hub: NetworkHub, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if hub.snapshot().url:
            return
        time.sleep(0.05)
    raise TimeoutError("MotionServer did not start")


async def _ws_rejects_missing_pairing_token() -> None:
    hub = NetworkHub()
    port = 18766
    server = MotionServer(hub, host="127.0.0.1", port=port, require_pairing=True)
    server.start()
    try:
        _wait_for_server(hub)
        url = f"https://127.0.0.1:{port}/ws"
        with pytest.raises(ClientResponseError) as exc:
            async with ClientSession() as session:
                async with session.ws_connect(url, ssl=_ssl_no_verify()):
                    pass
        assert exc.value.status == 403
    finally:
        server.stop()


async def _ws_accepts_valid_pairing_token() -> None:
    hub = NetworkHub()
    port = 18767
    server = MotionServer(hub, host="127.0.0.1", port=port, require_pairing=True)
    server.start()
    try:
        _wait_for_server(hub)
        token = server.pairing_token
        url = f"https://127.0.0.1:{port}/ws?token={token}"
        async with ClientSession() as session:
            async with session.ws_connect(url, ssl=_ssl_no_verify()) as ws:
                msg = await ws.receive()
                assert msg.type == WSMsgType.TEXT
                data = msg.json()
                assert data["type"] == "hello"
                await ws.send_json(
                    {"type": "hello", "role": "phone", "version": 1, "token": token}
                )
                msg2 = await ws.receive()
                assert msg2.type == WSMsgType.TEXT
                assert msg2.json()["type"] == "hello"
    finally:
        server.stop()


async def _ws_rejects_invalid_hello_token() -> None:
    hub = NetworkHub()
    port = 18768
    server = MotionServer(hub, host="127.0.0.1", port=port, require_pairing=True)
    server.start()
    try:
        _wait_for_server(hub)
        # Valid query token opens the socket, but a bad hello token is rejected.
        token = server.pairing_token
        url = f"https://127.0.0.1:{port}/ws?token={token}"
        async with ClientSession() as session:
            async with session.ws_connect(url, ssl=_ssl_no_verify()) as ws:
                await ws.receive()  # server hello
                await ws.send_json(
                    {"type": "hello", "role": "phone", "version": 1, "token": "wrong"}
                )
                # Expect an ack(False) then a close with the unauthorized code.
                saw_close = False
                for _ in range(4):
                    msg = await ws.receive()
                    if msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED):
                        saw_close = True
                        break
                assert saw_close
                assert ws.close_code == WS_CLOSE_UNAUTHORIZED
    finally:
        server.stop()


def test_ws_rejects_missing_pairing_token() -> None:
    asyncio.run(_ws_rejects_missing_pairing_token())


def test_ws_rejects_invalid_hello_token() -> None:
    asyncio.run(_ws_rejects_invalid_hello_token())


def test_ws_accepts_valid_pairing_token() -> None:
    asyncio.run(_ws_accepts_valid_pairing_token())


def test_resolve_bind_host_auto_uses_lan_ip() -> None:
    hub = NetworkHub()
    server = MotionServer(hub, host="auto")
    resolved = server.resolve_bind_host()
    assert resolved == get_primary_lan_ip()
    assert resolved != "0.0.0.0"


def test_resolve_bind_host_explicit_is_preserved() -> None:
    hub = NetworkHub()
    server = MotionServer(hub, host="0.0.0.0")
    assert server.resolve_bind_host() == "0.0.0.0"
    specific = MotionServer(hub, host="192.168.1.50")
    assert specific.resolve_bind_host() == "192.168.1.50"


def test_bound_all_interfaces_flag() -> None:
    hub = NetworkHub()
    assert MotionServer(hub, host="0.0.0.0").bound_all_interfaces is True
    assert MotionServer(hub, host="::").bound_all_interfaces is True
    assert MotionServer(hub, host="auto").bound_all_interfaces is False
    assert MotionServer(hub, host="192.168.1.50").bound_all_interfaces is False


def test_public_url_includes_pairing_token_when_required() -> None:
    hub = NetworkHub()
    server = MotionServer(hub, require_pairing=True)
    assert f"?token={server.pairing_token}" in server.public_url


def test_public_url_omits_token_when_pairing_disabled() -> None:
    hub = NetworkHub()
    server = MotionServer(hub, require_pairing=False)
    assert "?token=" not in server.public_url


def test_sensor_packet_from_json() -> None:
    pkt = SensorPacket.from_json(
        {"ax": 1, "ay": 2, "az": 3, "gx": 4, "gy": 5, "gz": 6, "t": 99},
        arrival_time=1.5,
    )
    assert pkt.ax == 1.0
    assert pkt.arrival_time == 1.5
    assert pkt.phone_ts == 99.0


def test_sensor_packet_client_id() -> None:
    pkt = SensorPacket.from_json(
        {"ax": 0, "ay": 0, "az": 9.8, "client_id": "abc123"},
        arrival_time=1.0,
        client_id="fallback",
    )
    assert pkt.client_id == "abc123"


def test_protocol_hello() -> None:
    msg = make_hello()
    assert parse_type(msg) == MessageType.HELLO.value
    assert msg["version"] == 1


def test_protocol_hello_with_client() -> None:
    msg = make_hello(client_id="x1", color="#22d3ee")
    assert msg["client_id"] == "x1"
    assert msg["color"] == "#22d3ee"


def test_protocol_pong() -> None:
    msg = make_pong(1234.5)
    assert parse_type(msg) == MessageType.PONG.value
    assert msg["ts"] == 1234.5


def test_protocol_message_types_exist() -> None:
    assert MessageType.PING.value == "ping"
    assert MessageType.CALIBRATE.value == "calibrate"
    assert MessageType.START_GAME.value == "start_game"
    assert MessageType.STOP_GAME.value == "stop_game"
    assert MessageType.DISCONNECT.value == "disconnect"


def test_hub_latency_ema() -> None:
    hub = NetworkHub()
    hub.record_latency(20.0)
    assert hub.snapshot().latency_ms == 20.0
    hub.record_latency(40.0)
    snap = hub.snapshot()
    assert 20.0 < snap.latency_ms < 40.0


def test_hub_control_events() -> None:
    hub = NetworkHub()
    hub.push_control(ControlAction.CALIBRATE_START, "c1")
    hub.push_control(ControlAction.START_GAME, "c1")
    events = hub.drain_controls()
    assert len(events) == 2
    assert events[0].action == ControlAction.CALIBRATE_START
    assert events[1].action == ControlAction.START_GAME


def test_hub_assign_client() -> None:
    hub = NetworkHub()
    client_id, color = hub.assign_client("ws1")
    assert len(client_id) == 8
    assert color.startswith("#")
    snap = hub.snapshot()
    assert snap.active_client_id == client_id


def test_lan_ip_string() -> None:
    ip = get_primary_lan_ip()
    assert isinstance(ip, str)
    assert len(ip) > 0
