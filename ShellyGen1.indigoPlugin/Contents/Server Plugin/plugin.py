#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    plugin.py
# Description: Shelly Gen 1 device integration for Indigo
#              Supports: Shelly 1 relay (on/off + pulse), Shelly UNI ADC voltage
# Author:      CliveS & Claude Fable 5.1; Claude Opus 5.5 (1.5.2, 1.5.3)
# Date:        27-09-2026
# Version:     1.5.3
#
# v1.5.3 (27-09-2026): FULL REVIEW, the bug fixes.
# * runConcurrentThread guards every device and every tick; one unexpected error
#   used to end all polling until a restart.
# * deviceStartComm polls in a thread: an absent device held up start-up for
#   over ten seconds.
# * Send Status Request now works on a relay (RequestStatus was ignored).
# * Pulse Relay re-reads the relay when the timer ends, so Indigo shows it off
#   again at once instead of up to 30 seconds later; a deleted device is handled.
# * validateDeviceConfigUi requires a real IPv4 address; the no-address warning
#   is said once, not every 30 seconds.
# * Three polls in a row before a device is called down (and marked with an
#   error state); a single missed poll raised a WARNING before.
# * on/off narration goes to the plugin's own log unless the new setting puts it
#   in the event log; a pulse keeps its event-log line.
# * lastUpdate carries the date.
#
# v1.5.2 (23-09-2026): ONE HISTORY ROW PER READING. _update_adc wrote the voltage
# and lastUpdate as two separate state updates every 30 s, so SQL Logger stored
# two rows per poll -- one of them lastUpdate alone (the Qashqai Battery Monitor
# reached 714,000 rows in five months). The three ADC states now go in one
# updateStatesOnServer call, and deviceStartComm adds lastUpdate to the device's
# `sqlLoggerIgnoreStates` shared prop (merged into the user's own list, never
# narrowing "*"). The voltage history is unchanged.
#
# v1.5.1 (11-09-2026): GITHUBINFO. The bundle now carries the standard GitHub record
# (GithubInfo: GithubUser/GithubRepo), as the Indigo Domotics and community plugins do.
# No behaviour change.
#
# v1.5.0 (15-08-2026): new per-device "Often Unpowered" setting. A car that has
# driven off, or an appliance plug switched off at the wall, is unreachable as
# its NORMAL state — but every failed poll logged a WARNING, so the Qashqai's
# UNI produced amber lines every time the car left the drive.
# Tick the box and those are reported at INFO instead.
# * A per-device SETTING, not a list of device names in the code. A hardcoded
#   exemption rots: the device it names can die for real with nobody hearing,
#   and it silently covers any future device that happens to match.
# * Quietening is NOT hiding. The failure is still counted, the line still
#   appears, and setErrorStateOnServer("unreachable") still runs — so the
#   device still shows red in the device list and DeviceHealthMonitor still
#   sees it. A thing allowed to go silent is a thing whose death nobody
#   notices.
#
# v1.4.3 (08-08-2026): REQUIRED Info.plist KEY. `CFBundleURLTypes` was PRESENT but
# EMPTY, so the plugin shipped without the support URL that becomes its
# "About" menu item — one of the SIX keys the official Developer's Guide lists as
# required. An empty array satisfies "key exists" while giving users nowhere to go,
# which is why an earlier sweep that only looked for a MISSING key passed it. Found
# by an estate check auditing the VALUE rather than the key's presence.
# No plugin logic changed.
#
# v1.4.2 (21-07-2026): shared plugin_utils.py refreshed to v1.3 — the
# estate-wide propagation of the four Appliance Monitor deep-review fixes.
# * install_timestamp_filter() is idempotent — a second call used to stack a
#   second filter, so every log line came out with two timestamps.
# * `import indigo` is soft, so the module imports outside the Indigo host and
#   can be exercised by offline tests.
# * A malformed log call keeps its arguments in the log instead of dropping
#   them, so a %-placeholder mismatch is visible.
# * New shared as_bool() — a pref re-serialised as the string "false" is
#   truthy, which is exactly the wrong answer.
#
# v1.4.1 (21-07-2026): LOG-LEVEL FIX. indigo.server.log(level=...) wants a Python
# logging INT — a STRING is silently ignored and the line logs as plain Info.
# The log() helper passed its level name straight through, so every WARNING and
# ERROR raised through it had been appearing as an ordinary Info line. Added
# _lvl() to map the name to a real level. Estate-wide sweep (38 files).
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
import threading
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
FAIL_WARN_AFTER   = 3     # v1.5.3: consecutive failed polls before a device is called down
PULSE_REPOLL_SECS = 1.0   # v1.5.3: re-read a pulsed relay this long after its timer ends

# v1.5.2: states rewritten on every poll that carry no history worth keeping.
# SQL Logger reads the comma-separated `sqlLoggerIgnoreStates` shared prop.
SQL_LOGGER_CHURN_STATES = ("lastUpdate",)


import logging


_LOG_LEVELS = {
    "DEBUG":   logging.DEBUG,
    "INFO":    logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR":   logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _lvl(level):
    """Map a level NAME to a Python logging int.

    indigo.server.log(level=...) wants an int. A STRING is silently ignored
    and the line logs as plain Info, which hid every WARNING and ERROR raised
    through log() until this was corrected (21-07-2026).
    """
    if isinstance(level, int):
        return level
    return _LOG_LEVELS.get(str(level).upper(), logging.INFO)


def log(message, level="INFO"):
    indigo.server.log(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {message}", level=_lvl(level))


def merge_sql_logger_ignore(existing, extra=SQL_LOGGER_CHURN_STATES):
    """Return the new sqlLoggerIgnoreStates value, or None when nothing changes.

    Keeps every entry the user already listed, in their order, and appends the
    missing churn states. "*" (ignore the whole device) is left as it is.
    """
    current = [t.strip() for t in str(existing or "").split(",") if t.strip()]
    if len(current) == 1 and current[0] == "*":
        return None
    have = {t.lower() for t in current}
    missing = [t for t in extra if t.lower() not in have]
    if not missing:
        return None
    return ", ".join(current + missing)


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
        # v1.5.3: routine on/off narration goes to this plugin's own log unless
        # the user asks for it in the shared event log (the estate rule).
        self.log_activity = bool(pluginPrefs.get("logActivityToEventLog", False))
        self._fail_state = {}   # {dev.id: consecutive poll-failure count} — log throttling
        self._no_ip_warned = set()   # device ids already told they have no address

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
        self._keep_churn_out_of_sql_logger(dev)
        # v1.5.3: the first poll runs off the lifecycle thread. Done inline, a
        # device that does not answer (the Qashqai when the car is out) held up
        # plugin start-up for the full timeout and retry, over ten seconds.
        threading.Thread(target=self._safe_update, args=(dev.id,), daemon=True).start()

    def _safe_update(self, dev_id):
        """Poll one device by id, never letting an error escape a thread."""
        try:
            dev = indigo.devices[dev_id]
            if dev.enabled:
                self._update_device(dev)
        except Exception as exc:
            self.logger.debug(f"poll of device {dev_id} failed: {exc}")

    def _keep_churn_out_of_sql_logger(self, dev):
        """v1.5.2: see SQL_LOGGER_CHURN_STATES. Writes only when something is
        missing, so a restart re-checks every device without rewriting it."""
        try:
            shared = dev.sharedProps
            merged = merge_sql_logger_ignore(shared.get("sqlLoggerIgnoreStates", ""))
            if merged is None:
                return
            shared["sqlLoggerIgnoreStates"] = merged
            dev.replaceSharedPropsOnServer(shared)
            self.logger.debug(f"{dev.name}: SQL Logger now skips {merged}")
        except Exception as exc:
            log(f"{dev.name}: could not set the SQL Logger ignore list ({exc}); "
                f"history keeps a row for every poll", level="WARNING")

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
        # v1.5.3: every device and every tick is guarded. Unguarded, one
        # unexpected error (an Indigo API hiccup, a device deleted mid-loop)
        # ended the loop, and with it all polling, until the plugin restarted.
        try:
            while True:
                try:
                    for dev in indigo.devices.iter("self"):
                        try:
                            if dev.enabled:
                                self._update_device(dev)
                        except self.StopThread:
                            raise
                        except Exception as exc:
                            log(f"{getattr(dev, 'name', '?')}: poll error: {exc}", level="WARNING")
                except self.StopThread:
                    raise
                except Exception as exc:
                    log(f"poll loop error: {exc}", level="WARNING")
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
            # v1.5.3: once, not every 30 seconds for ever.
            if dev.id not in self._no_ip_warned:
                self._no_ip_warned.add(dev.id)
                log(f"{dev.name}: no IP address configured - open the device and enter one",
                    level="WARNING")
            return None
        self._no_ip_warned.discard(dev.id)
        body = _http_get_retry(f"http://{ip}/status")
        if body is None:
            self._note_failure(dev, ip)
            return None
        try:
            status = json.loads(body)
        except json.JSONDecodeError:
            log(f"{dev.name}: invalid JSON from {ip}", level="WARNING")
            return None
        self._note_recovery(dev)
        return status

    @staticmethod
    def _expected_absent(dev):
        """True when the user has said this device is often away or unpowered.

        A per-device setting, deliberately, rather than a list of names in the
        code. A hardcoded exemption rots: the device it names can die for real
        and nobody hears, and it silently covers any future device that happens
        to match. This way the user states the fact about their own kit, and
        the plugin reports what it sees at a level that matches.
        """
        return bool(dev.pluginProps.get("expected_absent", False))

    def _note_failure(self, dev, ip):
        """Count a consecutive poll failure; log only the first and then every
        FAIL_REMIND_EVERY-th, to keep the log readable during an outage.

        For a device marked as often unpowered — a car that has driven off, an
        appliance plug switched off at the wall — not answering is the NORMAL
        state, so it is reported at INFO instead. What it is NOT is silent:
        the failure is still counted, the device still carries its unreachable
        error state, and the line still appears. Quietening the log must never
        become hiding the device, because a thing that is allowed to go quiet
        is a thing whose death nobody notices.
        """
        fails = self._fail_state.get(dev.id, 0) + 1
        self._fail_state[dev.id] = fails
        level = "INFO" if self._expected_absent(dev) else "WARNING"
        # v1.5.3: FAIL_WARN_AFTER polls in a row (about 1.5 minutes) before the
        # device is called down. A single missed poll had raised a WARNING: the
        # garage light produced five in 25 minutes on 19-09-2026, each answering
        # again 30 seconds later. The error state waits for the same threshold.
        if fails < FAIL_WARN_AFTER:
            self.logger.debug(f"{dev.name}: no response from {ip} (poll {fails}, retrying)")
        elif fails == FAIL_WARN_AFTER:
            dev.setErrorStateOnServer("unreachable")
            log(f"{dev.name}: no response from {ip} for {fails} polls in a row — "
                f"suppressing repeats until it recovers", level=level)
        elif fails % FAIL_REMIND_EVERY == 0:
            log(f"{dev.name}: still no response from {ip} ({fails} consecutive failed polls)",
                level=level)

    def _note_recovery(self, dev):
        """Log recovery and clear the error state if the device had been failing.
        A recovery is only announced when the loss was (v1.5.3)."""
        fails = self._fail_state.get(dev.id, 0)
        if fails >= FAIL_WARN_AFTER:
            log(f"{dev.name}: responding again after {fails} failed poll(s)", level="INFO")
        elif fails:
            self.logger.debug(f"{dev.name}: answered again after {fails} missed poll(s)")
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

    def _log_activity(self, message):
        """Routine narration: this plugin's own log, or the event log on request.
        Faults never come through here."""
        if self.log_activity:
            self.logger.info(message)
        else:
            self.logger.debug(message)

    def _update_adc(self, dev):
        status = self._fetch_status(dev)
        if status is None:
            return
        try:
            voltage = float(status["adcs"][0]["voltage"])
        except (KeyError, IndexError, TypeError, ValueError):
            log(f"{dev.name}: unexpected ADC status format", level="WARNING")
            return
        # One call, so SQL Logger stores one history row per reading (v1.5.2).
        dev.updateStatesOnServer([
            {"key": "onOffState", "value": True},
            {"key": "voltage",    "value": voltage, "uiValue": f"{voltage:.2f} V"},
            # v1.5.3: with the date. A time alone made a two-day-old reading
            # (the car away) look current.
            {"key": "lastUpdate", "value": datetime.now().strftime("%d-%m-%Y %H:%M:%S")},
        ])
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
        elif action.deviceAction == indigo.kDeviceAction.RequestStatus:
            # v1.5.3: Send Status Request used to do nothing at all on a relay.
            self._update_device(dev)

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
        self._log_activity(f'sent "{dev.name}" {"on" if is_on else "off"}')

    # ── Custom action: pulse relay ────────────────────────────────────

    def pulseRelay(self, action):
        """Turn relay on for 2 seconds then off (on-device Shelly timer)."""
        try:
            dev = indigo.devices[action.deviceId]
        except KeyError:
            log(f"Pulse Relay: device {action.deviceId} no longer exists", level="ERROR")
            return
        ip  = dev.pluginProps.get("ip_address", "").strip()
        if not ip:
            log(f"{dev.name}: no IP configured", level="ERROR")
            return
        seconds = 2
        body = _http_get_retry(f"http://{ip}/relay/0?turn=on&timer={seconds}")
        if body is None:
            log(f"{dev.name}: pulse failed — no response from {ip}", level="ERROR")
            return
        # A pulse moves something in the house (a garage door), so it keeps its
        # event-log line.
        log(f"{dev.name}: pulsed ON for {seconds} seconds")
        dev.updateStateOnServer("onOffState", True)
        # v1.5.3: read it back once the timer has run. Indigo used to show ON
        # until the next 30-second poll after the relay had already opened.
        timer = threading.Timer(seconds + PULSE_REPOLL_SECS, self._safe_update, args=(dev.id,))
        timer.daemon = True
        timer.start()

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
            self.log_activity = bool(valuesDict.get("logActivityToEventLog", False))

    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        """v1.5.3: an address is required and must look like one. A device saved
        without one used to log a warning every 30 seconds for ever."""
        errors = indigo.Dict()
        ip = str(valuesDict.get("ip_address", "")).strip()
        parts = ip.split(".")
        if not ip:
            errors["ip_address"] = "Enter the Shelly's IP address (e.g. 192.168.1.10)."
        elif len(parts) != 4 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
            errors["ip_address"] = "That is not an IPv4 address (e.g. 192.168.1.10)."
        else:
            valuesDict["ip_address"] = ip
        return (len(errors) == 0), valuesDict, errors
