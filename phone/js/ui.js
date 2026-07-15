/**
 * UI rendering for phone controller status and metrics.
 */
const PhoneUI = (() => {
  const els = {};

  function init() {
    els.status = document.getElementById("status");
    els.debug = document.getElementById("debug");
    els.fps = document.getElementById("fpsVal");
    els.latency = document.getElementById("latencyVal");
    els.battery = document.getElementById("batteryVal");
    els.sendRate = document.getElementById("sendRateVal");
    els.clientBadge = document.getElementById("clientBadge");
    els.btnConnect = document.getElementById("btnConnect");
    els.btnCalibrate = document.getElementById("btnCalibrate");
    els.btnRecenter = document.getElementById("btnRecenter");
    els.btnStartGame = document.getElementById("btnStartGame");
    els.btnStopGame = document.getElementById("btnStopGame");
  }

  function setStatus(text, cls) {
    if (!els.status) return;
    els.status.textContent = text;
    els.status.className = "status" + (cls ? " " + cls : "");
  }

  function setConnected(connected) {
    const disabled = !connected;
    if (els.btnCalibrate) els.btnCalibrate.disabled = disabled;
    if (els.btnRecenter) els.btnRecenter.disabled = disabled;
    if (els.btnStartGame) els.btnStartGame.disabled = disabled;
    if (els.btnStopGame) els.btnStopGame.disabled = disabled;
  }

  function setClientInfo(clientId, color) {
    if (!els.clientBadge) return;
    if (!clientId) {
      els.clientBadge.hidden = true;
      return;
    }
    els.clientBadge.hidden = false;
    els.clientBadge.textContent = `ID ${clientId}`;
    if (color) els.clientBadge.style.borderLeft = `4px solid ${color}`;
  }

  function updateMetrics({ fps, latencyMs, batteryPct, sendHz }) {
    if (els.fps) els.fps.textContent = fps != null ? fps.toFixed(0) : "—";
    if (els.latency) els.latency.textContent = latencyMs != null ? `${latencyMs.toFixed(0)} ms` : "—";
    if (els.battery) els.battery.textContent = batteryPct != null ? `${batteryPct}%` : "—";
    if (els.sendRate) els.sendRate.textContent = sendHz != null ? `${sendHz.toFixed(0)} Hz` : "—";
  }

  function updateDebug(text) {
    if (els.debug) els.debug.textContent = text;
  }

  return {
    init,
    setStatus,
    setConnected,
    setClientInfo,
    updateMetrics,
    updateDebug,
    get btnConnect() { return els.btnConnect; },
    get btnCalibrate() { return els.btnCalibrate; },
    get btnRecenter() { return els.btnRecenter; },
    get btnStartGame() { return els.btnStartGame; },
    get btnStopGame() { return els.btnStopGame; },
  };
})();
