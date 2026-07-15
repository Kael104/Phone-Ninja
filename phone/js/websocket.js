/**
 * WebSocket client with auto-reconnect, PING/PONG latency, and control messages.
 */
const PhoneSocket = (() => {
  const TOKEN = new URLSearchParams(location.search).get("token") || "";
  let ws = null;
  let clientId = "";
  let clientColor = "";
  let reconnectAttempt = 0;
  let reconnectTimer = null;
  let pingTimer = null;
  let latencyMs = null;
  let onOpenCb = null;
  let onCloseCb = null;
  let onMessageCb = null;

  const PING_INTERVAL_MS = 2000;
  const MAX_BACKOFF_MS = 15000;

  function wsUrl() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const q = TOKEN ? "?token=" + encodeURIComponent(TOKEN) : "";
    return proto + "//" + location.host + "/ws" + q;
  }

  function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return;
    }
    ws = new WebSocket(wsUrl());

    ws.onopen = () => {
      reconnectAttempt = 0;
      ws.send(JSON.stringify({ type: "hello", role: "phone", version: 1, token: TOKEN }));
      startPingLoop();
      if (onOpenCb) onOpenCb();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "hello") {
          clientId = data.client_id || "";
          clientColor = data.color || "";
        } else if (data.type === "pong") {
          const echo = Number(data.ts);
          if (echo > 0) {
            const now = performance.now();
            latencyMs = Math.max(0, now - echo);
          }
        }
        if (onMessageCb) onMessageCb(data);
      } catch (_) {
        /* ignore malformed */
      }
    };

    ws.onclose = () => {
      stopPingLoop();
      scheduleReconnect();
      if (onCloseCb) onCloseCb();
    };

    ws.onerror = () => {
      /* onclose handles reconnect */
    };
  }

  function scheduleReconnect() {
    if (reconnectTimer) return;
    const delay = Math.min(500 * Math.pow(2, reconnectAttempt), MAX_BACKOFF_MS);
    reconnectAttempt += 1;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, delay);
  }

  function startPingLoop() {
    stopPingLoop();
    pingTimer = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "ping", ts: performance.now() }));
      }
    }, PING_INTERVAL_MS);
  }

  function stopPingLoop() {
    if (pingTimer) {
      clearInterval(pingTimer);
      pingTimer = null;
    }
  }

  function disconnect() {
    stopPingLoop();
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    reconnectAttempt = 999;
    if (ws) {
      try {
        ws.send(JSON.stringify({ type: "disconnect" }));
      } catch (_) {}
      ws.close();
      ws = null;
    }
  }

  function send(data) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data));
      return true;
    }
    return false;
  }

  function sendSensor(packet) {
    if (clientId) packet.client_id = clientId;
    return send(packet);
  }

  function isConnected() {
    return ws != null && ws.readyState === WebSocket.OPEN;
  }

  function getLatencyMs() {
    return latencyMs;
  }

  function getClientInfo() {
    return { clientId, clientColor };
  }

  function onOpen(cb) { onOpenCb = cb; }
  function onClose(cb) { onCloseCb = cb; }
  function onMessage(cb) { onMessageCb = cb; }

  return {
    connect,
    disconnect,
    send,
    sendSensor,
    isConnected,
    getLatencyMs,
    getClientInfo,
    onOpen,
    onClose,
    onMessage,
  };
})();
