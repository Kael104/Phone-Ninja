"""HTTPS + WSS server (aiohttp) running in a background thread."""

from __future__ import annotations

import asyncio
import json
import secrets
import ssl
import threading
import time
from pathlib import Path

from aiohttp import WSMsgType, web

from network.cert import ensure_self_signed_cert, get_primary_lan_ip
from network.hub import ControlAction, NetworkHub
from network.packet import SensorPacket
from network.protocol import (
    WS_CLOSE_UNAUTHORIZED,
    MessageType,
    make_ack,
    make_hello,
    make_pong,
    parse_type,
)

# Modular phone controller served from project root phone/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PHONE_DIR = PROJECT_ROOT / "phone"
PHONE_HTML = PHONE_DIR / "index.html"
# Legacy fallback
LEGACY_CONTROLLER = Path(__file__).resolve().parent / "controller" / "controller.html"


class MotionServer:
    def __init__(
        self,
        hub: NetworkHub,
        host: str = "0.0.0.0",
        port: int = 8765,
        *,
        require_pairing: bool = True,
    ) -> None:
        self.hub = hub
        self.host = host
        self.port = port
        self.require_pairing = require_pairing
        self.pairing_token = secrets.token_urlsafe(16)
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._runner: web.AppRunner | None = None
        self._stop = threading.Event()
        self._client_counter = 0

    def _token_valid(self, token: str) -> bool:
        return secrets.compare_digest(token, self.pairing_token)

    def resolve_bind_host(self) -> str:
        """Resolve the configured host to a concrete bind address.

        "auto" (the default) binds only to the primary LAN interface so the
        server is not exposed on every adapter the way "0.0.0.0" would be.
        """
        if self.host in ("", "auto"):
            return get_primary_lan_ip()
        return self.host

    @property
    def bound_all_interfaces(self) -> bool:
        """True when the server listens on every interface (wildcard bind).

        Only an explicit "0.0.0.0"/"::" is a wildcard bind; "auto"/"" resolve
        to a single LAN address.
        """
        return self.host in ("0.0.0.0", "::")

    @property
    def public_url(self) -> str:
        base = f"https://{get_primary_lan_ip()}:{self.port}/"
        if self.require_pairing:
            return f"{base}?token={self.pairing_token}"
        return base

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="MotionServer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._loop and self._loop.is_running():
            fut = asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop)
            try:
                fut.result(timeout=3.0)
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None

    def _run(self) -> None:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            loop.run_until_complete(self._serve())
        except Exception as exc:
            self.hub.set_error(f"Server failed: {exc}")
        finally:
            try:
                if self._loop and not self._loop.is_closed():
                    self._loop.close()
            except Exception:
                pass

    async def _serve(self) -> None:
        cert_path, key_path = ensure_self_signed_cert()
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(str(cert_path), str(key_path))

        app = web.Application()
        app.router.add_get("/", self._handle_index)
        app.router.add_get("/ws", self._handle_ws)
        if PHONE_DIR.exists():
            app.router.add_static("/js", PHONE_DIR / "js", show_index=False)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(
            self._runner, self.resolve_bind_host(), self.port, ssl_context=ssl_ctx
        )
        await site.start()
        self.hub.set_url(self.public_url)

        while not self._stop.is_set():
            await asyncio.sleep(0.2)

        await self._shutdown()

    async def _shutdown(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    async def _handle_index(self, request: web.Request) -> web.Response:
        if PHONE_HTML.exists():
            html = PHONE_HTML.read_text(encoding="utf-8")
            return web.Response(text=html, content_type="text/html")
        if LEGACY_CONTROLLER.exists():
            html = LEGACY_CONTROLLER.read_text(encoding="utf-8")
            return web.Response(text=html, content_type="text/html")
        return web.Response(text="phone/index.html missing", status=500)

    async def _handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        if self.require_pairing:
            token = request.query.get("token", "")
            if not self._token_valid(token):
                raise web.HTTPForbidden(text="pairing token required")

        ws = web.WebSocketResponse(heartbeat=20.0)
        await ws.prepare(request)

        self._client_counter += 1
        ws_id = str(self._client_counter)
        client_id, color = self.hub.assign_client(ws_id)

        self.hub.on_client_connect()
        await ws.send_json(make_hello(client_id=client_id, color=color))

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except json.JSONDecodeError:
                        await ws.send_json(make_ack(False, "invalid json"))
                        continue
                    msg_type = parse_type(data)
                    if msg_type == MessageType.SENSOR.value:
                        packet = SensorPacket.from_json(
                            data,
                            arrival_time=time.perf_counter(),
                            client_id=client_id,
                        )
                        self.hub.push_packet(packet)
                    elif msg_type == MessageType.HEARTBEAT.value:
                        await ws.send_json(make_ack(True, "pong"))
                    elif msg_type == MessageType.HELLO.value:
                        if self.require_pairing:
                            hello_token = str(data.get("token", ""))
                            if not self._token_valid(hello_token):
                                await ws.send_json(make_ack(False, "invalid token"))
                                await ws.close(
                                    code=WS_CLOSE_UNAUTHORIZED,
                                    message=b"invalid pairing token",
                                )
                                break
                        await ws.send_json(make_hello(client_id=client_id, color=color))
                    elif msg_type == MessageType.PING.value:
                        echo_ts = float(data.get("ts", 0.0))
                        await ws.send_json(make_pong(echo_ts))
                        # Server-side latency estimate (half RTT if phone sends ts)
                        if echo_ts > 0:
                            now_ms = time.perf_counter() * 1000.0
                            rtt = max(0.0, now_ms - echo_ts)
                            self.hub.record_latency(rtt)
                    elif msg_type == MessageType.CALIBRATE.value:
                        action = str(data.get("action", "start")).lower()
                        if action in ("stop", "end", "finish"):
                            self.hub.push_control(ControlAction.CALIBRATE_STOP, client_id)
                        elif action in ("recenter", "center"):
                            self.hub.push_control(ControlAction.RECENTER, client_id)
                        else:
                            self.hub.push_control(ControlAction.CALIBRATE_START, client_id)
                        await ws.send_json(make_ack(True, f"calibrate_{action}"))
                    elif msg_type == MessageType.START_GAME.value:
                        self.hub.push_control(ControlAction.START_GAME, client_id)
                        await ws.send_json(make_ack(True, "start_game"))
                    elif msg_type == MessageType.STOP_GAME.value:
                        self.hub.push_control(ControlAction.STOP_GAME, client_id)
                        await ws.send_json(make_ack(True, "stop_game"))
                    elif msg_type == MessageType.DISCONNECT.value:
                        break
                elif msg.type in (WSMsgType.ERROR, WSMsgType.CLOSE):
                    break
        finally:
            self.hub.release_client(ws_id)
            self.hub.on_client_disconnect()
            await ws.close()
        return ws
