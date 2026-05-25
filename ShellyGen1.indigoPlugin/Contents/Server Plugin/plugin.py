#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    plugin.py
# Description: Shelly Gen 1 device integration for Indigo
#              Supports: Shelly 1 relay (on/off + pulse), Shelly UNI ADC voltage
# Author:      CliveS & Claude Opus 4.7
# Date:        23-05-2026
# Version:     1.2
#
# v1.1 (23-05-2026): Millisecond timestamp [HH:MM:SS.mmm] prefix on every
# log line via plugin_utils.install_timestamp_filter() — matches Device
# Activity Monitor convention. New "Toggle Timestamps in Log" menu item.

import indigo
import os as _os
import sys as _sys
import json
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


def log(message, level="INFO"):
    indigo.server.log(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {message}", level=level)


def _http_get(url, timeout=HTTP_TIMEOUT):
    """GET url, return response body string. Returns None on any failure."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except Exception:
        return None


class Plugin(indigo.PluginBase):

    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super().__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
        self.debug = pluginPrefs.get("showDebugInfo", False)
        self.timestamp_enabled = bool(pluginPrefs.get("timestampEnabled", True))

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
        """Fetch /status from the device. Returns parsed dict or None."""
        ip = dev.pluginProps.get("ip_address", "").strip()
        if not ip:
            log(f"{dev.name}: no IP address configured", level="WARNING")
            return None
        body = _http_get(f"http://{ip}/status")
        if body is None:
            log(f"{dev.name}: no response from {ip}", level="WARNING")
            dev.setErrorStateOnServer("unreachable")
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            log(f"{dev.name}: invalid JSON from {ip}", level="WARNING")
            return None

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
        body = _http_get(f"http://{ip}/relay/0?turn={turn}")
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
        body = _http_get(f"http://{ip}/relay/0?turn=on&timer=2")
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
