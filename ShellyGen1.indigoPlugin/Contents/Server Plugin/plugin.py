#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    plugin.py
# Description: Shelly Gen 1 device integration for Indigo
#              Supports: Shelly 1 relay (on/off + pulse), Shelly UNI ADC voltage
# Author:      CliveS & Claude Fable 5.1; Claude Opus 5.5 (1.5.2 - 1.6.1)
# Date:        27-09-2026
# Version:     1.6.1
#
# v1.6.1 (27-09-2026): INDEPENDENT REVIEW OF 1.6.0 - fourteen fixes.
# * A new address in the device dialog forgets the stored MAC, two devices of
#   one kind cannot share an address, and the MAC search never moves a device
#   onto another device's address (a copied device used to go back to the
#   original's Shelly and control it).
# * Last Switched By is only written when the relay moves; an http change is
#   Indigo's when Indigo sent a command after the previous reading, and
#   Indigo's own commands record Indigo as they switch (_write_own_switch).
# * Accept Replaced Shellys menu item: a swapped unit was locked out for good.
# * Push settings apply at once (listener restarted, devices re-pointed);
#   switching push off removes our URLs and keeps everyone else's.
# * A switched-off action slot holding someone else's URLs is left alone; a
#   full slot says what it dropped.
# * A push that lands while a poll is out beats the poll's older reading.
# * A disabled or wrong device takes no push; stopping a device forgets a
#   pending one; push set-up confirms the MAC at /shelly before writing.
# * The MAC is recorded at INFO; counters and the search throttle are locked;
#   the search re-reads the device before writing and uses daemon threads.
#
# v1.6.0 (27-09-2026): FULL REVIEW, the features.
# * PUSH: each relay's out_on_url / out_off_url action (index 0) is pointed at a
#   plugin listener (port 8179, path /shellyG1), keeping every URL that is not
#   ours (merge_action_urls). A push must come from the device's own address;
#   it sets onOffState at once and reads the relay back for who switched it.
#   Re-checked every six hours. Pref push_enabled / indigo_server_ip (secrets
#   first) / push_port.
# * IDENTITY BY MAC: /status carries the MAC, so every poll checks it. Learned
#   when missing; on a mismatch nothing is written, no command is sent, one
#   warning, and the /24 is searched for the MAC (/shelly, throttled hourly,
#   never for an Often Unpowered device that is merely away).
# * lastChangedBy state + Switched Outside Indigo trigger from relays[0].source;
#   an http change within 10 s of our command, or a timer-off inside our pulse,
#   is Indigo.
# * Pulse Relay takes its length from the action (default 2 s for older steps).
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
import http.server
import json
import re
import socketserver
import threading
import time
import urllib.parse
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
try:
    from plugin_utils import as_bool
except ImportError:
    def as_bool(value, default=False):
        if isinstance(value, bool):
            return value
        if value is None or value == "":
            return default
        return str(value).strip().lower() in ("true", "1", "yes", "on", "t")

# Secrets first, the plugin's Configure dialog as the fallback (estate rule).
_sys.path.insert(0, "/Library/Application Support/Perceptive Automation")
try:
    from IndigoSecrets import INDIGO_SERVER_IP as _SECRETS_INDIGO_IP
except ImportError:
    _SECRETS_INDIGO_IP = ""

PLUGIN_ID   = "com.clives.indigoplugin.shellyg1"
POLL_SECS   = 30
HTTP_TIMEOUT = 5
RETRY_DELAY  = 0.5        # seconds before the single retry on a failed GET
FAIL_REMIND_EVERY = 60    # re-log a still-down device every Nth consecutive fail
FAIL_WARN_AFTER   = 3     # v1.5.3: consecutive failed polls before a device is called down
PULSE_REPOLL_SECS = 1.0   # v1.5.3: re-read a pulsed relay this long after its timer ends
PULSE_DEFAULT_SECS = 2    # v1.6.0: the pulse length when an action does not say

# ── v1.6.0: push from the device ────────────────────────────────────────────
# A Gen 1 Shelly calls a URL when its relay switches (the "actions" in its own
# settings). The plugin listens for those calls, so a change made at the wall or
# in the Shelly app reaches Indigo at once instead of on the next 30-second poll.
PUSH_PORT_DEFAULT = 8179  # ShellyDirect (Gen 2+) listens on 8178
PUSH_PATH         = "/shellyG1"
PUSH_EVENTS       = ("out_on_url", "out_off_url")
PUSH_MAX_URLS     = 5     # a Gen 1 action holds at most five URLs
PUSH_CHECK_SECS   = 6 * 3600
COMMAND_WINDOW    = 10    # an http-sourced change this soon after our command was ours

# ── v1.6.0: identity by MAC ──────────────────────────────────────────────────
RELOCATE_EVERY    = 3600  # at most one address search per device per hour
SCAN_TIMEOUT      = 0.6
SCAN_WORKERS      = 32

_SOURCE_LABELS = {
    "input":    "the switch wired to the device",
    "timer":    "the device's own timer",
    "init":     "the device starting up",
    "cloud":    "the Shelly app",
    "schedule": "a schedule on the device",
    "mqtt":     "another app on the network",
    "coiot":    "another app on the network",
    "ws_in":    "another app on the network",
}


def normalise_mac(value):
    """Bare upper-case hex, or "" if it is not a MAC."""
    cleaned = re.sub(r"[^0-9A-Fa-f]", "", str(value or "")).upper()
    return cleaned if len(cleaned) == 12 else ""


def switch_source_label(source, ours_recently=False):
    """Who last changed a Gen 1 relay, in words. 'http' is Indigo when the
    plugin sent a command moments before, otherwise some other app; an unknown
    source is shown in quotes so a new one surfaces rather than vanishing."""
    src = str(source or "").strip().lower()
    if not src:
        return ""
    if src == "http":
        return "Indigo" if ours_recently else "another app on the network"
    return _SOURCE_LABELS.get(src, f'"{source}"')


def join_urls(urls):
    urls = [str(u) for u in urls]
    return urls[0] if len(urls) == 1 else ", ".join(urls[:-1]) + " and " + urls[-1]


def plugin_push_url(url):
    return PUSH_PATH + "?" in str(url or "")


def merge_action_urls(existing, wanted):
    """The URL list for one action slot: every URL that is not ours kept as it
    is, our stale ones (another device id, an old address or port) dropped,
    and ours added once. None when nothing needs to change."""
    keep = [u for u in (existing or []) if not plugin_push_url(u)]
    ours = [u for u in (existing or []) if plugin_push_url(u)]
    if ours == [wanted]:
        return None
    urls = keep + [wanted]
    if len(urls) > PUSH_MAX_URLS:
        urls = keep[:PUSH_MAX_URLS - 1] + [wanted]
    return urls

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


def scan_hosts(hosts, probe, workers=SCAN_WORKERS):
    """Run probe(host) over hosts on daemon threads; return the truthy results
    in host order. Daemon threads, unlike a ThreadPoolExecutor's, never hold up
    the plugin host's exit while a scan is running (v1.6.1)."""
    hosts = list(hosts)
    results = [None] * len(hosts)
    lock = threading.Lock()
    todo = iter(range(len(hosts)))

    def work():
        while True:
            with lock:
                i = next(todo, None)
            if i is None:
                return
            try:
                results[i] = probe(hosts[i])
            except Exception:
                results[i] = None

    threads = [threading.Thread(target=work, daemon=True) for _ in range(min(workers, len(hosts)))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return [r for r in results if r]


def action_query(name, urls, enabled=True):
    """The query string for a Gen 1 /settings/actions write. The device only
    reads `urls[]` with literal brackets -- encoded as %5B%5D it answers as
    though it worked and changes nothing (measured on a Shelly 1, 1.14.0) --
    while each URL itself must be fully encoded."""
    parts = [f"index=0&name={urllib.parse.quote(name)}&enabled={'true' if enabled else 'false'}"]
    parts += ["urls[]=" + urllib.parse.quote(u, safe="") for u in urls]
    return "&".join(parts)


def saved_action_urls(reply, name):
    """The URLs the device reports for action `name` (index 0) after a write."""
    try:
        data = json.loads(reply or "")
        slots = (data.get("actions") or {}).get(name) or []
        slot = next((a for a in slots if a.get("index", 0) == 0), {})
        return list(slot.get("urls") or [])
    except (ValueError, AttributeError, TypeError):
        return []


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

        # v1.6.0
        self._load_push_prefs(pluginPrefs)
        self.push_server   = None
        # The start-up set-up is done per device in deviceStartComm; the first
        # periodic check waits its full interval, or the two run together.
        self._push_checked = time.time()
        self._push_lock    = threading.Lock()
        self._last_command = {}      # {dev.id: ts} of our last relay command
        self._pulse_until  = {}      # {dev.id: ts} a pulse's own timer-off is ours
        self._moved        = {}      # {dev.id: True} a push saw the relay change
        self._wrong_device = {}      # {dev.id: MAC found instead} commands and writes refused
        self._wrong_warned = set()
        self._relocate_at  = {}      # {dev.id: ts} last address search
        self.triggers      = []
        # v1.6.1
        self._state_lock   = threading.Lock()   # counters and throttles shared by threads
        self._last_read    = {}      # {dev.id: ts} a /status request last STARTED
        self._push_at      = {}      # {dev.id: ts} the last push arrived
        self._slot_warned  = set()   # (dev.id, slot) already told about

        if install_timestamp_filter:
            self._ts_filter = install_timestamp_filter(self, enabled=self.timestamp_enabled)
        else:
            self._ts_filter = None

        # Startup banner moved to showPluginInfo on demand (revised 25-May-2026 per Jay).

    # ── Lifecycle ─────────────────────────────────────────────────────

    def startup(self):
        self.logger.debug("startup()")
        if self.push_enabled:
            self._start_push_server()

    def shutdown(self):
        self.logger.debug("shutdown()")
        if self.push_server:
            try:
                self.push_server.shutdown()
                self.push_server.server_close()
            except Exception as exc:
                self.logger.debug(f"push listener shutdown: {exc}")

    # ── Triggers (v1.6.0) ─────────────────────────────────────────────

    def triggerStartProcessing(self, trigger):
        self.triggers.append(trigger)

    def triggerStopProcessing(self, trigger):
        self.triggers = [t for t in self.triggers if t.id != trigger.id]

    def _fire_trigger(self, type_id, dev_id):
        for trigger in list(self.triggers):
            if trigger.pluginTypeId != type_id:
                continue
            want = trigger.pluginProps.get("deviceId", "any")
            if want and want != "any" and want != str(dev_id):
                continue
            try:
                indigo.trigger.execute(trigger)
            except Exception as exc:
                log(f"trigger {trigger.name} failed: {exc}", level="WARNING")

    def getRelayDevices(self, filter="", valuesDict=None, typeId="", targetId=0):
        result = [("any", "Any Relay")]
        for dev in sorted(indigo.devices.iter("self"), key=lambda d: d.name):
            if dev.deviceTypeId == "shellyRelay":
                result.append((str(dev.id), dev.name))
        return result

    def deviceStartComm(self, dev):
        self.logger.debug(f"deviceStartComm: {dev.name}")
        # v1.6.0: a device made before a state was added to Devices.xml does not
        # have it until its state list is refreshed; writes to it are dropped.
        dev.stateListOrDisplayStateIdChanged()
        self._keep_churn_out_of_sql_logger(dev)
        # v1.5.3: the first poll runs off the lifecycle thread. Done inline, a
        # device that does not answer (the Qashqai when the car is out) held up
        # plugin start-up for the full timeout and retry, over ten seconds.
        threading.Thread(target=self._safe_update, args=(dev.id, True), daemon=True).start()

    def _safe_update(self, dev_id, set_up_push=False):
        """Poll one device by id, never letting an error escape a thread."""
        try:
            dev = indigo.devices[dev_id]
            if dev.enabled:
                self._update_device(dev)
                if set_up_push:
                    self._ensure_push(indigo.devices[dev_id])
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
        # v1.6.1: a push seen while stopping must not fire a trigger when the
        # device is enabled again, possibly days later.
        self._moved.pop(dev.id, None)

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
                if self.push_enabled and (time.time() - self._push_checked) >= PUSH_CHECK_SECS:
                    self._push_checked = time.time()
                    threading.Thread(target=self._ensure_push_all, daemon=True).start()
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
        if not isinstance(status, dict) or not self._identity_ok(dev, ip, status.get("mac")):
            return None
        self._note_recovery(dev)
        return status

    # ── Identity by MAC (v1.6.0) ──────────────────────────────────────

    def _identity_ok(self, dev, ip, reported_mac):
        """The box at this address must be the device we think it is.

        A Gen 1 Shelly puts its MAC in every /status, so the check costs
        nothing. A device with no MAC stored learns it here. On a mismatch
        nothing is written and no command is sent, one warning names both
        MACs, and the plugin looks for the device on the subnet. The same
        fault in ShellyDirect once cross-wrote two plugs' energy readings.
        """
        found  = normalise_mac(reported_mac)
        stored = normalise_mac(dev.pluginProps.get("mac_address", ""))
        if not found:
            return True                       # nothing to compare - trust the address
        if not stored:
            props = dict(dev.pluginProps)
            props["mac_address"] = found
            dev.replacePluginPropsOnServer(props)
            # v1.6.1: said at INFO - this is the moment identity is decided.
            log(f"{dev.name}: recorded {found} as this device's MAC address "
                f"(the Shelly at {ip})")
            return True
        if found == stored:
            if self._wrong_device.pop(dev.id, None):
                self._wrong_warned.discard(dev.id)
                log(f"{dev.name}: the right device is answering at {ip} again")
            return True
        self._wrong_device[dev.id] = found
        if dev.id not in self._wrong_warned:
            self._wrong_warned.add(dev.id)
            dev.setErrorStateOnServer("wrong device")
            log(f"{dev.name}: {ip} is answering as {found}, not {stored}. Nothing is recorded "
                f"and no command is sent until the device is found again; looking for it "
                f"on the network. If you replaced this Shelly, use Plugins -> Shelly Gen 1 "
                f"-> Accept Replaced Shellys.", level="WARNING")
        threading.Thread(target=self._relocate, args=(dev.id,), daemon=True).start()
        return False

    def _relocate(self, dev_id):
        """Look for a device by MAC on its own /24. Throttled to once an hour
        per device; a device marked Often Unpowered is only searched for when
        another box has taken its address, never just for being away."""
        try:
            dev = indigo.devices[dev_id]
        except KeyError:
            return
        now = time.time()
        with self._state_lock:                  # v1.6.1: one search at a time
            if now - self._relocate_at.get(dev_id, 0) < RELOCATE_EVERY:
                return
            self._relocate_at[dev_id] = now
        mac = normalise_mac(dev.pluginProps.get("mac_address", ""))
        ip  = dev.pluginProps.get("ip_address", "").strip()
        parts = ip.split(".")
        if not mac or len(parts) != 4:
            return
        subnet = ".".join(parts[:3])

        def probe(host):
            body = _http_get(f"http://{host}/shelly", timeout=SCAN_TIMEOUT)
            if not body:
                return None
            try:
                return host if normalise_mac(json.loads(body).get("mac")) == mac else None
            except (ValueError, AttributeError):
                return None

        hits = scan_hosts([f"{subnet}.{i}" for i in range(1, 255)], probe)
        if not hits or hits[0] == ip:
            return
        # v1.6.1: never onto an address another device of this plugin owns. A
        # duplicated device carries its original's MAC, and moving it there put
        # two Indigo devices on one relay.
        owner = self._address_owner(hits[0], dev.id)
        if owner:
            log(f"{dev.name}: its MAC {mac} answers at {hits[0]}, which is \"{owner}\"'s "
                f"address, so it was not moved. If this device is a copy of that one, open "
                f"it and give it its own address.", level="WARNING")
            return
        try:
            dev = indigo.devices[dev_id]            # v1.6.1: fresh, after a ~5 s scan
        except KeyError:
            return
        props = dict(dev.pluginProps)
        props["ip_address"] = hits[0]
        dev.replacePluginPropsOnServer(props)       # the address change restarts the device
        log(f"{dev.name}: found at {hits[0]} by its MAC {mac} (was {ip}) - address updated")

    def _address_owner(self, ip, not_id, type_id=None):
        """Name of another device of this plugin at this address, or ""."""
        for other in indigo.devices.iter("self"):
            if other.id == not_id:
                continue
            if type_id and other.deviceTypeId != type_id:
                continue
            if other.pluginProps.get("ip_address", "").strip() == ip:
                return other.name
        return ""

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
        with self._state_lock:                  # v1.6.1: polls run on several threads
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
            # v1.6.0: a device that is NOT often away may simply have a new
            # address. Look for it by MAC (throttled, and never for a car).
            if not self._expected_absent(dev) and dev.pluginProps.get("mac_address"):
                threading.Thread(target=self._relocate, args=(dev.id,), daemon=True).start()
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
        started = time.time()
        prev_read = self._last_read.get(dev.id, 0)
        self._last_read[dev.id] = started
        status = self._fetch_status(dev)
        if status is None:
            return
        try:
            relay = status["relays"][0]
            is_on = bool(relay["ison"])
        except (KeyError, IndexError, TypeError):
            log(f"{dev.name}: unexpected relay status format", level="WARNING")
            return
        # v1.6.1: a push that arrived while this request was out is newer than
        # this reading. Writing the reading would flip the state back, and the
        # push's own read-back follows anyway.
        if self._push_at.get(dev.id, 0) > started:
            return
        dev = indigo.devices[dev.id]                 # current states, not the loop's copy
        prev   = dev.states.get("onOffState")
        moved  = self._moved.pop(dev.id, False) or (prev is not None and bool(prev) != is_on)
        now    = time.time()
        source = str(relay.get("source", "") or "").lower()
        # v1.6.1: a change is Indigo's when Indigo sent a command after the
        # previous reading (not merely within ten seconds - a command whose
        # reply was lost would otherwise count as someone else's), or it is
        # the timer ending Indigo's own pulse.
        ours = ((source == "http" and self._last_command.get(dev.id, 0) >= prev_read)
                or (source == "timer" and now < self._pulse_until.get(dev.id, 0)))
        who = "Indigo" if ours else switch_source_label(source)
        kv = [{"key": "onOffState", "value": is_on}]
        # v1.6.1: only when the relay MOVED (or nothing is recorded yet). A poll
        # of an unmoved relay re-derived the answer from a source that no longer
        # described anything recent, so "Indigo" turned into "another app"
        # thirty seconds after every Indigo command.
        if who and (moved or not dev.states.get("lastChangedBy")) \
                and who != dev.states.get("lastChangedBy"):
            kv.append({"key": "lastChangedBy", "value": who})
        dev.updateStatesOnServer(kv)
        if moved and who and who != "Indigo":
            self._log_activity(f'"{dev.name}" turned {"on" if is_on else "off"} by {who}')
            self._fire_trigger("switchedOutsideIndigo", dev.id)
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

    def _refuse_wrong_device(self, dev):
        found = self._wrong_device.get(dev.id)
        if found:
            log(f"{dev.name}: command not sent - the Shelly at its address is {found}, "
                f"not this device", level="ERROR")
            return True
        return False

    def _relay_cmd(self, dev, ip, turn):
        if self._refuse_wrong_device(dev):
            return
        self._last_command[dev.id] = time.time()
        body = _http_get_retry(f"http://{ip}/relay/0?turn={turn}")
        if body is None:
            log(f"{dev.name}: relay command '{turn}' failed — no response from {ip}", level="ERROR")
            return
        try:
            is_on = bool(json.loads(body).get("ison", turn == "on"))
        except (json.JSONDecodeError, AttributeError):
            is_on = (turn == "on")
        self._write_own_switch(dev, is_on)
        self._log_activity(f'sent "{dev.name}" {"on" if is_on else "off"}')

    def _write_own_switch(self, dev, is_on):
        """Record a switch Indigo itself made, with Indigo as who did it.

        v1.6.1: this write already brings onOffState up to date, so the
        device's own report of the change (push or poll) sees nothing move and,
        rightly, leaves Last Switched By alone. So it has to be set here, or an
        Indigo command would never show as Indigo's (found live).
        """
        kv = [{"key": "onOffState", "value": is_on}]
        if bool(dev.states.get("onOffState")) != is_on and dev.states.get("lastChangedBy") != "Indigo":
            kv.append({"key": "lastChangedBy", "value": "Indigo"})
        dev.updateStatesOnServer(kv)

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
        if self._refuse_wrong_device(dev):
            return
        # v1.6.0: the length comes from the action; older actions carry none.
        try:
            seconds = float(str(action.props.get("seconds", PULSE_DEFAULT_SECS)).strip())
        except (TypeError, ValueError, AttributeError):
            seconds = PULSE_DEFAULT_SECS
        seconds = max(0.5, min(seconds, 3600))
        seconds = int(seconds) if seconds == int(seconds) else seconds
        self._last_command[dev.id] = time.time()
        self._pulse_until[dev.id] = time.time() + seconds + COMMAND_WINDOW
        body = _http_get_retry(f"http://{ip}/relay/0?turn=on&timer={seconds}")
        if body is None:
            log(f"{dev.name}: pulse failed — no response from {ip}", level="ERROR")
            return
        # A pulse moves something in the house (a garage door), so it keeps its
        # event-log line.
        log(f"{dev.name}: pulsed ON for {seconds} seconds")
        self._write_own_switch(dev, True)
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
            old = (self.push_enabled, self.push_port, self.server_ip)
            self._load_push_prefs(valuesDict)
            new = (self.push_enabled, self.push_port, self.server_ip)
            if new != old:
                # v1.6.1: applied now. The listener used to keep its old port
                # until a reload while the devices were already being pointed
                # at the new one, and pushes stopped with no message.
                threading.Thread(target=self._apply_push_change, args=(old,), daemon=True).start()

    def _apply_push_change(self, old):
        old_enabled, old_port, _old_ip = old
        if self.push_server and (not self.push_enabled or self.push_port != old_port):
            try:
                self.push_server.shutdown()
                self.push_server.server_close()
            except Exception as exc:
                self.logger.debug(f"push listener stop: {exc}")
            self.push_server = None
        if self.push_enabled and not self.push_server:
            self._start_push_server()
        self._ensure_push_all()
        log("Push settings applied: " + (f"listening on port {self.push_port}"
                                          if self.push_enabled else "push updates switched off"))

    def menuAcceptReplaced(self, valuesDict=None, typeId=""):
        """v1.6.1: adopt the MAC now answering for each device flagged as the
        wrong device - for a Shelly that has been swapped for a new one at the
        same address. There was no way back from that state before."""
        accepted = []
        for dev_id, found in list(self._wrong_device.items()):
            try:
                dev = indigo.devices[dev_id]
            except KeyError:
                self._wrong_device.pop(dev_id, None)
                continue
            props = dict(dev.pluginProps)
            props["mac_address"] = found
            dev.replacePluginPropsOnServer(props)
            self._wrong_device.pop(dev_id, None)
            self._wrong_warned.discard(dev_id)
            dev.setErrorStateOnServer("")
            accepted.append(f"{dev.name} is now {found}")
        log("Accepted replaced Shellys: " + "; ".join(accepted) + "."
            if accepted else "No device is waiting for a replaced Shelly to be accepted.")
        return True

    def validatePrefsConfigUi(self, valuesDict):
        errors = indigo.Dict()
        try:
            port = int(str(valuesDict.get("push_port", PUSH_PORT_DEFAULT)).strip())
            if not 1024 <= port <= 65535:
                raise ValueError
        except ValueError:
            errors["push_port"] = "Enter a port from 1024 to 65535 (8179 unless it is taken)."
        ip = str(valuesDict.get("indigo_server_ip", "")).strip()
        if ip:
            parts = ip.split(".")
            if len(parts) != 4 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
                errors["indigo_server_ip"] = "That is not an IPv4 address (e.g. 192.168.1.5)."
        return (len(errors) == 0), valuesDict, errors

    def validateActionConfigUi(self, valuesDict, typeId, devId):
        errors = indigo.Dict()
        if typeId == "pulseRelay":
            try:
                secs = float(str(valuesDict.get("seconds", "")).strip())
                if not 0.5 <= secs <= 3600:
                    raise ValueError
            except ValueError:
                errors["seconds"] = "Enter a number of seconds from 0.5 to 3600."
        return (len(errors) == 0), valuesDict, errors

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
            # v1.6.1: two devices of the same kind cannot share a Shelly.
            owner = self._address_owner(ip, devId, typeId)
            if owner:
                errors["ip_address"] = (f"{ip} is already \"{owner}\". Give this device "
                                        f"its own Shelly's address.")
            else:
                # v1.6.1: a new address means a different Shelly, so the stored
                # MAC no longer applies. Kept, it made the plugin move the device
                # straight back to the old one.
                try:
                    old_ip = indigo.devices[devId].pluginProps.get("ip_address", "").strip()
                except (KeyError, TypeError, ValueError):
                    old_ip = None
                if old_ip != ip:
                    valuesDict["mac_address"] = ""
        return (len(errors) == 0), valuesDict, errors

    # ── Push from the device (v1.6.0) ─────────────────────────────────

    def _load_push_prefs(self, prefs):
        self.push_enabled = as_bool(prefs.get("push_enabled"), True)
        self.server_ip = (_SECRETS_INDIGO_IP or str(prefs.get("indigo_server_ip", "") or "")).strip()
        try:
            self.push_port = int(str(prefs.get("push_port", PUSH_PORT_DEFAULT)).strip())
        except (TypeError, ValueError):
            self.push_port = PUSH_PORT_DEFAULT

    def _push_url(self, dev, turn):
        return (f"http://{self.server_ip}:{self.push_port}{PUSH_PATH}"
                f"?devId={dev.id}&ev={turn}")

    def _ensure_push_all(self):
        for dev in indigo.devices.iter("self"):
            if dev.enabled:
                try:
                    self._ensure_push(dev)
                except Exception as exc:
                    self.logger.debug(f"{dev.name}: push check failed: {exc}")

    def _ensure_push(self, dev):
        """Point the relay's on and off actions at the plugin, keeping any URL
        that is not ours. Quiet when nothing needs changing. One at a time:
        two overlapping runs read the same list and both wrote it. With push
        switched off it takes our URLs away instead (v1.6.1)."""
        if dev.deviceTypeId != "shellyRelay":
            return
        with self._push_lock:
            if self.push_enabled:
                self._ensure_push_locked(dev)
            else:
                self._remove_push_locked(dev)

    def _identity_confirmed(self, dev, ip):
        """/shelly at this address reports this device's MAC (v1.6.1). A push
        URL written to the wrong box is the cross-write the MAC check exists
        to prevent."""
        stored = normalise_mac(dev.pluginProps.get("mac_address", ""))
        if not stored:
            return False
        try:
            return normalise_mac(json.loads(_http_get(f"http://{ip}/shelly") or "{}").get("mac")) == stored
        except (ValueError, AttributeError):
            return False

    def _remove_push_locked(self, dev):
        ip = dev.pluginProps.get("ip_address", "").strip()
        body = _http_get(f"http://{ip}/settings/actions") if ip else None
        try:
            actions = json.loads(body or "{}").get("actions", {})
        except (ValueError, AttributeError):
            return
        removed = False
        for name in PUSH_EVENTS:
            slot = next((a for a in actions.get(name, []) if a.get("index", 0) == 0), None)
            if not slot or not any(plugin_push_url(u) for u in slot.get("urls", [])):
                continue
            keep = [u for u in slot.get("urls", []) if not plugin_push_url(u)]
            resp = _http_get(f"http://{ip}/settings/actions?"
                             + action_query(name, keep, enabled=bool(keep) and slot.get("enabled")))
            if not any(plugin_push_url(u) for u in saved_action_urls(resp, name)):
                removed = True
        if removed:
            log(f"{dev.name}: no longer sends push updates to Indigo")

    def _ensure_push_locked(self, dev):
        if not self.server_ip:
            if "push_no_ip" not in self._wrong_warned:
                self._wrong_warned.add("push_no_ip")
                log("Push updates need the Indigo server's address: set it in Plugins -> "
                    "Shelly Gen 1 -> Configure, or INDIGO_SERVER_IP in IndigoSecrets.py",
                    level="WARNING")
            return
        if dev.id in self._wrong_device:
            return
        ip = dev.pluginProps.get("ip_address", "").strip()
        if not ip or not self._identity_confirmed(dev, ip):
            return
        body = _http_get(f"http://{ip}/settings/actions")
        if not body:
            return
        try:
            actions = json.loads(body).get("actions", {})
        except (ValueError, AttributeError):
            return
        changed = []
        for name in PUSH_EVENTS:
            slot = next((a for a in actions.get(name, []) if a.get("index", 0) == 0), None)
            if slot is None:
                continue
            want = self._push_url(dev, "on" if name == "out_on_url" else "off")
            current = slot.get("urls", []) or []
            foreign = [u for u in current if not plugin_push_url(u)]
            # v1.6.1: a slot someone switched OFF while it holds their own URLs
            # is theirs. Enabling it for ours would switch theirs back on.
            if not slot.get("enabled") and foreign:
                if (dev.id, name) not in self._slot_warned:
                    self._slot_warned.add((dev.id, name))
                    log(f"{dev.name}: its {name} action is switched off and holds other "
                        f"addresses, so push was not added there. Clear or enable it in the "
                        f"Shelly's own settings to use push.", level="WARNING")
                continue
            urls = merge_action_urls(current, want)
            if urls is None and slot.get("enabled"):
                continue
            urls = urls if urls is not None else current
            dropped = [u for u in foreign if u not in urls]
            if dropped:
                log(f"{dev.name}: its {name} action was full, so {join_urls(dropped)} "
                    f"was removed to make room for Indigo's", level="WARNING")
            resp = _http_get(f"http://{ip}/settings/actions?" + action_query(name, urls))
            # The reply carries the list as saved. Believe that, not the fact
            # that it answered: a query the device misread was accepted and
            # changed nothing (found live while building this).
            if want not in saved_action_urls(resp, name):
                log(f"{dev.name}: could not set its {name} push address", level="WARNING")
                continue
            changed.append(name)
        if changed:
            log(f"{dev.name}: now tells Indigo the moment it switches")

    def _start_push_server(self):
        plugin = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                try:
                    code = plugin._handle_push(self.path, self.client_address[0])
                except Exception as exc:
                    plugin.logger.debug(f"push handler: {exc}")
                    code = 500
                self.send_response(code)
                self.end_headers()

            def log_message(self, fmt, *args):
                pass

        class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True
            allow_reuse_address = True

        try:
            self.push_server = Server(("", self.push_port), Handler)
            threading.Thread(target=self.push_server.serve_forever, daemon=True).start()
            self.logger.debug(f"push listener on port {self.push_port}")
        except OSError as exc:
            self.push_server = None
            log(f"Could not listen for push updates on port {self.push_port} ({exc}). "
                f"Devices are polled every 30 seconds meanwhile; choose another port in "
                f"Plugins -> Shelly Gen 1 -> Configure.", level="WARNING")

    def _handle_push(self, path, sender):
        """One push from a device. The sender must be the device it names."""
        parts = urllib.parse.urlparse(path)
        if parts.path != PUSH_PATH:
            return 404
        query = urllib.parse.parse_qs(parts.query)
        try:
            dev_id = int(query.get("devId", ["0"])[0])
            dev = indigo.devices[dev_id]
        except (ValueError, KeyError):
            return 404
        if dev.pluginId != PLUGIN_ID or dev.deviceTypeId != "shellyRelay":
            return 404
        if not dev.enabled or dev.id in self._wrong_device:
            return 409                                # v1.6.1
        if dev.pluginProps.get("ip_address", "").strip() != sender:
            self.logger.debug(f"push for {dev.name} from {sender} ignored (not its address)")
            return 409
        turn = query.get("ev", [""])[0]
        if turn not in ("on", "off"):
            return 400
        is_on = turn == "on"
        self._push_at[dev.id] = time.time()
        if bool(dev.states.get("onOffState")) != is_on:
            self._moved[dev.id] = True
        dev.updateStateOnServer("onOffState", is_on)
        # Read the relay straight back: it says who switched it.
        threading.Thread(target=self._safe_update, args=(dev.id,), daemon=True).start()
        return 200

