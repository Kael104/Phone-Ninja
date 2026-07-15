/**
 * Main app bootstrap — wires UI, sensors, socket, and calibration.
 */
(() => {
  let calibrating = false;
  let batteryPct = null;
  let metricsTimer = null;

  PhoneUI.init();

  if (!PhoneSensors.checkSupport()) {
    PhoneUI.setStatus(PhoneSensors.getUnsupportedReason(), "warn");
  }

  // Battery API (optional)
  if ("getBattery" in navigator) {
    navigator.getBattery().then((bat) => {
      const update = () => { batteryPct = Math.round(bat.level * 100); };
      update();
      bat.addEventListener("levelchange", update);
    }).catch(() => {});
  }

  PhoneSocket.onOpen(() => {
    PhoneUI.setStatus("Connected — streaming", "ok");
    PhoneUI.setConnected(true);
    const info = PhoneSocket.getClientInfo();
    PhoneUI.setClientInfo(info.clientId, info.clientColor);
  });

  PhoneSocket.onClose(() => {
    PhoneUI.setStatus("Disconnected — reconnecting…", "warn");
    PhoneUI.setConnected(false);
    if (PhoneSensors.isStreaming()) {
      PhoneSocket.connect();
    }
  });

  PhoneSocket.onMessage((data) => {
    if (data.type === "hello") {
      PhoneUI.setClientInfo(data.client_id || "", data.color || "");
    }
    if (data.type === "ack" && data.detail && data.detail.startsWith("calibrate")) {
      PhoneUI.setStatus(`Server: ${data.detail}`, "ok");
    }
  });

  function refreshDebug() {
    const o = PhoneSensors.getOrientation();
    const m = PhoneSensors.getMetrics();
    PhoneUI.updateMetrics({
      fps: m.fps,
      latencyMs: PhoneSocket.getLatencyMs(),
      batteryPct,
      sendHz: m.sendHz,
    });
    PhoneUI.updateDebug(
      `α ${o.alpha.toFixed(1)}°  β ${o.beta.toFixed(1)}°  γ ${o.gamma.toFixed(1)}°\n` +
      `streaming ${PhoneSensors.isStreaming()}  ws ${PhoneSocket.isConnected()}\n` +
      `calibrating ${calibrating}`
    );
  }

  function startMetricsLoop() {
    if (metricsTimer) clearInterval(metricsTimer);
    metricsTimer = setInterval(refreshDebug, 250);
  }

  PhoneUI.btnConnect.addEventListener("click", async () => {
    try {
      PhoneUI.btnConnect.disabled = true;
      PhoneUI.setStatus("Requesting permission…");
      await PhoneSensors.start();
      PhoneSocket.connect();
      PhoneUI.setStatus("Connecting…");
      startMetricsLoop();
    } catch (err) {
      PhoneUI.setStatus(String(err.message || err), "warn");
      PhoneUI.btnConnect.disabled = false;
    }
  });

  PhoneUI.btnCalibrate.addEventListener("click", () => {
    if (calibrating) {
      PhoneCalibration.sendCalibrateStop();
      calibrating = false;
      PhoneUI.setStatus("Calibration sent (stop)", "ok");
    } else {
      PhoneCalibration.sendCalibrateStart();
      calibrating = true;
      PhoneUI.setStatus("Hold phone still at screen center…", "ok");
    }
  });

  PhoneUI.btnRecenter.addEventListener("click", () => {
    PhoneCalibration.sendRecenter();
    PhoneUI.setStatus("Recenter sent", "ok");
  });

  PhoneUI.btnStartGame.addEventListener("click", () => {
    PhoneCalibration.sendStartGame();
    PhoneUI.setStatus("Start game sent", "ok");
  });

  PhoneUI.btnStopGame.addEventListener("click", () => {
    PhoneCalibration.sendStopGame();
    PhoneUI.setStatus("Stop game sent", "ok");
  });
})();
