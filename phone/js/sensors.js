/**
 * DeviceMotion / DeviceOrientation capture at ~60 Hz.
 */
const PhoneSensors = (() => {
  let streaming = false;
  let lastSend = 0;
  let lastAlpha = 0;
  let lastBeta = 0;
  let lastGamma = 0;
  let wakeLock = null;
  let sendCount = 0;
  let sendWindowStart = 0;
  let sendHz = 0;
  let frameCount = 0;
  let fpsWindowStart = 0;
  let fps = 0;
  let unsupportedReason = "";

  const TARGET_HZ = 60;
  const MIN_INTERVAL = 1000 / TARGET_HZ;

  async function requestPermission() {
    if (typeof DeviceMotionEvent === "undefined") {
      throw new Error("DeviceMotion not supported");
    }
    if (typeof DeviceMotionEvent.requestPermission === "function") {
      const res = await DeviceMotionEvent.requestPermission();
      if (res !== "granted") throw new Error("Motion permission denied");
    }
    if (typeof DeviceOrientationEvent !== "undefined" &&
        typeof DeviceOrientationEvent.requestPermission === "function") {
      const res = await DeviceOrientationEvent.requestPermission();
      if (res !== "granted") throw new Error("Orientation permission denied");
    }
  }

  async function acquireWakeLock() {
    try {
      if ("wakeLock" in navigator) {
        wakeLock = await navigator.wakeLock.request("screen");
        wakeLock.addEventListener("release", () => { wakeLock = null; });
      }
    } catch (_) {
      /* optional */
    }
  }

  async function releaseWakeLock() {
    if (wakeLock) {
      try { await wakeLock.release(); } catch (_) {}
      wakeLock = null;
    }
  }

  function onOrientation(event) {
    if (event.alpha != null) lastAlpha = event.alpha;
    if (event.beta != null) lastBeta = event.beta;
    if (event.gamma != null) lastGamma = event.gamma;
  }

  function onMotion(event) {
    if (!streaming || !PhoneSocket.isConnected()) return;

    const now = performance.now();
    if (now - lastSend < MIN_INTERVAL) return;
    lastSend = now;

    frameCount += 1;
    if (fpsWindowStart <= 0) fpsWindowStart = now;
    const fpsElapsed = now - fpsWindowStart;
    if (fpsElapsed >= 1000) {
      fps = (frameCount * 1000) / fpsElapsed;
      frameCount = 0;
      fpsWindowStart = now;
    }

    sendCount += 1;
    if (sendWindowStart <= 0) sendWindowStart = now;
    const sendElapsed = now - sendWindowStart;
    if (sendElapsed >= 500) {
      sendHz = (sendCount * 1000) / sendElapsed;
      sendCount = 0;
      sendWindowStart = now;
    }

    const a = event.accelerationIncludingGravity || event.acceleration || {};
    const r = event.rotationRate || {};
    const packet = {
      type: "sensor",
      t: event.timeStamp || now,
      ax: a.x || 0,
      ay: a.y || 0,
      az: a.z || 0,
      gx: r.alpha || 0,
      gy: r.beta || 0,
      gz: r.gamma || 0,
      alpha: lastAlpha,
      beta: lastBeta,
      gamma: lastGamma,
    };
    PhoneSocket.sendSensor(packet);
  }

  function attachListeners() {
    window.removeEventListener("devicemotion", onMotion);
    window.removeEventListener("deviceorientation", onOrientation);
    window.removeEventListener("deviceorientationabsolute", onOrientation);
    window.addEventListener("devicemotion", onMotion, { passive: true });
    if ("ondeviceorientationabsolute" in window) {
      window.addEventListener("deviceorientationabsolute", onOrientation, { passive: true });
    } else {
      window.addEventListener("deviceorientation", onOrientation, { passive: true });
    }
  }

  function detachListeners() {
    window.removeEventListener("devicemotion", onMotion);
    window.removeEventListener("deviceorientation", onOrientation);
    window.removeEventListener("deviceorientationabsolute", onOrientation);
  }

  async function start() {
    await requestPermission();
    attachListeners();
    await acquireWakeLock();
    streaming = true;
    lastSend = 0;
    sendCount = 0;
    sendWindowStart = 0;
    frameCount = 0;
    fpsWindowStart = 0;
  }

  function stop() {
    streaming = false;
    detachListeners();
    releaseWakeLock();
  }

  function isStreaming() {
    return streaming;
  }

  function getOrientation() {
    return { alpha: lastAlpha, beta: lastBeta, gamma: lastGamma };
  }

  function getMetrics() {
    return { fps, sendHz };
  }

  function checkSupport() {
    if (typeof DeviceMotionEvent === "undefined") {
      unsupportedReason = "DeviceMotion API unavailable";
      return false;
    }
    unsupportedReason = "";
    return true;
  }

  function getUnsupportedReason() {
    return unsupportedReason;
  }

  // Re-acquire wake lock when page becomes visible again (phone sleep)
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && streaming) {
      acquireWakeLock();
    }
  });

  // Screen rotation: orientation values update automatically via listeners
  window.addEventListener("orientationchange", () => {
    /* values refresh on next event */
  });

  return {
    start,
    stop,
    isStreaming,
    getOrientation,
    getMetrics,
    checkSupport,
    getUnsupportedReason,
  };
})();
