/**
 * Calibration and game control messages to laptop.
 */
const PhoneCalibration = (() => {
  function sendCalibrateStart() {
    return PhoneSocket.send({ type: "calibrate", action: "start" });
  }

  function sendCalibrateStop() {
    return PhoneSocket.send({ type: "calibrate", action: "stop" });
  }

  function sendRecenter() {
    return PhoneSocket.send({ type: "calibrate", action: "recenter" });
  }

  function sendStartGame() {
    return PhoneSocket.send({ type: "start_game" });
  }

  function sendStopGame() {
    return PhoneSocket.send({ type: "stop_game" });
  }

  return {
    sendCalibrateStart,
    sendCalibrateStop,
    sendRecenter,
    sendStartGame,
    sendStopGame,
  };
})();
