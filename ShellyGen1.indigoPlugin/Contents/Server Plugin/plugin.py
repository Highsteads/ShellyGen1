#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    plugin.py
# Description: Shelly Gen 1 device integration for Indigo
#              Supports: Shelly 1 relay (on/off + pulse), Shelly UNI ADC voltage
# Author:      CliveS & Claude Sonnet 4.6
# Date:        09-04-2026
# Version:     1.0

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

PLUGIN_ID   = "com.clives.indigoplugin.shellyg1"
POLL_SECS   = 30
HTTP_TIMEOUT = 5


def log(message, level="INFO"):
    indigo.server.log(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", level=level)


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

        if log_startup_banner:
            log_startup_banner(pluginId, pluginDisplayName, pluginVersion, extras=[
                ("Supported Devices:", "Shelly 1 relay, Shelly UNI ADC"),
            ])
        else:
            indigo.server.log(f"{pluginDisplayName} v{pluginVersion} starting")

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
        if log_startup_banner:
            log_startup_banner(self.pluginId, self.pluginDisplayName, self.pluginVersion, extras=[
                ("Supported Devices:", "Shelly 1 relay, Shelly UNI ADC"),
            ])
        else:
            indigo.server.log(f"{self.pluginDisplayName} v{self.pluginVersion}")

    # ── Prefs ─────────────────────────────────────────────────────────

    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        if not userCancelled:
            self.debug = valuesDict.get("showDebugInfo", False)
