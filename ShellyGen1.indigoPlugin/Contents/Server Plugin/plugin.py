#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    plugin.py
# Description: Shelly Gen 1 device integration for Indigo
#              Supports: Shelly 1 relay (on/off + pulse), Shelly UNI ADC voltage
# Author:      CliveS & Claude Opus 4.8
# Date:        29-05-2026
# Version:     1.4
#
# v1.3 (29-05-2026): Resilience — one quick retry before a device is declared
# unreachable, and reachability failures are logged once on the way down plus
# once on recovery (with an occasional heartbeat) instead of on every poll, so
# a flaky Shelly Gen 1 / ESP8266 can no longer flood the event log. Device
# error state is cleared automatically on recovery.
# v1.1 (23-05-2026): Millisecond timestamp [HH:MM:SS.mmm] prefix on every
# log line via plugin_utils.install_timestamp_filter() — matches Device
# Activity Monitor convention. New "Toggle Timestamps in Log" menu item.

import indigo
import os as _os
import sys as _sys
import json
import time
import urllib.request
import urllib.error
from datetime import datetime

_sys.path.insert(0, _os.getcwd())
try:
    from plugin_utils import log_startup_banner
except ImportError:
    log_startup_banner = None
try:
    from plugin_utils import install_timestamp_filter
except ImportError:
    install_timestamp_filter = None

PLUGIN_ID   = "com.clives.indigoplugin.shellyg1"
POLL_SECS   = 30
HTTP_TIMEOUT = 5
RETRY_DELAY  = 0.5        # seconds before the single retry on a failed GET
FAIL_REMIND_EVERY = 60    # re-log a still-down device every Nth consecutive fail


def log(message, level="INFO"):
    indigo.server.log(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {message}", level=level)


def _http_get(url, timeout=HTTP_TIMEOUT):
    """GET url, return response body string. Returns None on any failure."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        # OSError covers urllib.error.URLError/HTTPError, socket timeouts and connection
        # failures; UnicodeDecodeError covers a bad body. Real programming errors propagate.
        return None


def _http_get_retry(url, timeout=HTTP_TIMEOUT):
    """GET with a single quick retry — absorbs a one-off dropped packet or a
    momentarily busy ESP8266 web server. Returns body string or None."""
    body = _http_get(url, timeout)
    if body is None:
        time.sleep(RETRY_DELAY)
        body = _http_get(url, timeout)
    return body


class Plugin(indigo.PluginBase):

    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super().__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
        self.debug = pluginPrefs.get("showDebugInfo", False)
        self.timestamp_enabled = bool(pluginPrefs.get("timestampEnabled", True))
        self._fail_state = {}   # {dev.id: consecutive poll-failure count} — log throttling

        if install_timestamp_filter:
            self._ts_filter = install_timestamp_filter(self, enabled=self.timestamp_enabled)
        else:
            self._ts_filter = None

        # Startup banner moved to showPluginInfo on demand (revised 25-May-2026 per Jay).

    # ── Lifecycle ─────────────────────────────────────────────────────

    def startup(self):
        self.logger.debug("startup()")

    def shutdown(self):
        self.logger.debug("shutdown()")

    def deviceStartComm(self, dev):
        self.logger.debug(f"deviceStartComm: {dev.name}")
        self._update_device(dev)

    def deviceStopComm(self, dev):
        self.logger.debug(f"deviceStopComm: {dev.name}")
        self._fail_state.pop(dev.id, None)

    @staticmethod
    def didDeviceCommPropertyChange(oldDevice, newDevice):
        """Restart comm only when the Shelly's IP address changes.

        The HTTP poller targets `ip_address`; nothing else in pluginProps
        affects the connection.
        """
        return oldDevice.pluginProps.get("ip_address") != newDevice.pluginProps.get("ip_address")

    def runConcurrentThread(self):
        try:
            while True:
                for dev in indigo.devices.iter("self"):
                    if dev.enabled:
                        self._update_device(dev)
                self.sleep(POLL_SECS)
        except self.StopThread:
            pass

    # ── Polling ───────────────────────────────────────────────────────

    def _update_device(self, dev):
        if dev.deviceTypeId == "shellyRelay":
            self._update_relay(dev)
        elif dev.deviceTypeId == "shellyUniADC":
            self._update_adc(dev)

    def _fetch_status(self, dev):
        """Fetch /status from the device (one retry). Returns parsed dict or None.

        Reachability failures are logged once on the way down and once on
        recovery — not on every poll — so a flaky device can't flood the log.
        The device's UI error state still tracks the live condition.
        """
        ip = dev.pluginProps.get("ip_address", "").strip()
        if not ip:
            log(f"{dev.name}: no IP address configured", level="WARNING")
            return None
        body = _http_get_retry(f"http://{ip}/status")
        if body is None:
            self._note_failure(dev, ip)
            dev.setErrorStateOnServer("unreachable")
            return None
        try:
            status = json.loads(body)
        except json.JSONDecodeError:
            log(f"{dev.name}: invalid JSON from {ip}", level="WARNING")
            return None
        self._note_recovery(dev)
        return status

    def _note_failure(self, dev, ip):
        """Count a consecutive poll failure; log only the first and then every
        FAIL_REMIND_EVERY-th, to keep the log readable during an outage."""
        fails = self._fail_state.get(dev.id, 0) + 1
        self._fail_state[dev.id] = fails
        if fails == 1:
            log(f"{dev.name}: no response from {ip} — suppressing repeats until it recovers", level="WARNING")
        elif fails % FAIL_REMIND_EVERY == 0:
            log(f"{dev.name}: still no response from {ip} ({fails} consecutive failed polls)", level="WARNING")

    def _note_recovery(self, dev):
        """Log recovery and clear the error state if the device had been failing."""
        if self._fail_state.get(dev.id, 0):
            log(f"{dev.name}: responding again after {self._fail_state[dev.id]} failed poll(s)", level="INFO")
            self._fail_state[dev.id] = 0
        if dev.errorState:
            dev.setErrorStateOnServer("")

    def _update_relay(self, dev):
        status = self._fetch_status(dev)
        if status is None:
            return
        try:
            is_on = bool(status["relays"][0]["ison"])
        except (KeyError, IndexError, TypeError):
            log(f"{dev.name}: unexpected relay status format", level="WARNING")
            return
        dev.updateStateOnServer("onOffState", is_on)
        if self.debug:
            log(f"{dev.name}: {'ON' if is_on else 'OFF'}")

    def _update_adc(self, dev):
        status = self._fetch_status(dev)
        if status is None:
            return
        try:
            voltage = float(status["adcs"][0]["voltage"])
        except (KeyError, IndexError, TypeError, ValueError):
            log(f"{dev.name}: unexpected ADC status format", level="WARNING")
            return
        dev.updateStateOnServer("onOffState", True)
        dev.updateStateOnServer("voltage", voltage, uiValue=f"{voltage:.2f} V")
        dev.updateStateOnServer("lastUpdate", datetime.now().strftime("%H:%M:%S"))
        dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
        if self.debug:
            log(f"{dev.name}: {voltage:.2f} V")

    # ── Device actions (on/off/toggle) ────────────────────────────────

    def actionControlSensor(self, action, dev, callerWaitingForResult=None):
        # shellyUniADC is type="sensor"; without this, a Send Status Request logged
        # "plugin does not define method actionControlSensor" (seen live 2026-06-05 07:35).
        if action.sensorAction == indigo.kSensorAction.RequestStatus:
            self._update_device(dev)
        else:
            log(f"{dev.name}: unsupported sensor action {action.sensorAction}", level="WARNING")

    def actionControlDevice(self, action, dev, callerWaitingForResult):
        ip = dev.pluginProps.get("ip_address", "").strip()
        if not ip:
            log(f"{dev.name}: no IP configured", level="ERROR")
            return

        if action.deviceAction == indigo.kDeviceAction.TurnOn:
            self._relay_cmd(dev, ip, "on")
        elif action.deviceAction == indigo.kDeviceAction.TurnOff:
            self._relay_cmd(dev, ip, "off")
        elif action.deviceAction == indigo.kDeviceAction.Toggle:
            self._relay_cmd(dev, ip, "toggle")

    def _relay_cmd(self, dev, ip, turn):
        body = _http_get_retry(f"http://{ip}/relay/0?turn={turn}")
        if body is None:
            log(f"{dev.name}: relay command '{turn}' failed — no response from {ip}", level="ERROR")
            return
        try:
            is_on = bool(json.loads(body).get("ison", turn == "on"))
        except (json.JSONDecodeError, AttributeError):
            is_on = (turn == "on")
        dev.updateStateOnServer("onOffState", is_on)
        log(f"{dev.name}: {'ON' if is_on else 'OFF'}")

    # ── Custom action: pulse relay ────────────────────────────────────

    def pulseRelay(self, action):
        """Turn relay on for 2 seconds then off (on-device Shelly timer)."""
        dev = indigo.devices[action.deviceId]
        ip  = dev.pluginProps.get("ip_address", "").strip()
        if not ip:
            log(f"{dev.name}: no IP configured", level="ERROR")
            return
        body = _http_get_retry(f"http://{ip}/relay/0?turn=on&timer=2")
        if body is None:
            log(f"{dev.name}: pulse failed — no response from {ip}", level="ERROR")
            return
        log(f"{dev.name}: pulsed ON for 2 seconds")
        dev.updateStateOnServer("onOffState", True)

    # ── Menu ──────────────────────────────────────────────────────────

    def showPluginInfo(self, valuesDict=None, typeId=None):
        extras = [
            ("Supported Devices:", "Shelly 1 relay, Shelly UNI ADC"),
            ("Timestamps in Log:", "ON" if self.timestamp_enabled else "OFF"),
        ]
        if log_startup_banner:
            log_startup_banner(self.pluginId, self.pluginDisplayName, self.pluginVersion, extras=extras)
        else:
            indigo.server.log(f"{self.pluginDisplayName} v{self.pluginVersion}")
            for label, value in extras:
                indigo.server.log(f"  {label} {value}")

    def menuToggleTimestamps(self):
        self.timestamp_enabled = not self.timestamp_enabled
        self.pluginPrefs["timestampEnabled"] = self.timestamp_enabled
        if self._ts_filter:
            self._ts_filter.enabled = self.timestamp_enabled
        state = "ON" if self.timestamp_enabled else "OFF"
        indigo.server.log(f"[{self.pluginDisplayName}] Timestamps in Log -> {state}")

    # ── Prefs ─────────────────────────────────────────────────────────

    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        if not userCancelled:
            self.debug = valuesDict.get("showDebugInfo", False)
