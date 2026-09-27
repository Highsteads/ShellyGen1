#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename:    test_v153_fixes.py
# Description: v1.5.3 full-review fixes: the guarded poll loop, Send Status
#              Request on a relay, the address check, three polls before a
#              device is called down, the pulse read-back, the no-address
#              warning said once, and on/off narration kept out of the event log.
# Author:      CliveS & Claude Opus 5.5
# Date:        27-09-2026
# Version:     1.0

import types
from unittest.mock import MagicMock

import pytest

from test_sql_logger_churn import MOD
from test_sql_logger_churn import plugin as _bare_plugin


def plugin():
    """A Plugin with the state __init__ sets, without Indigo behind it."""
    p = _bare_plugin()
    p._fail_state = {}
    p._no_ip_warned = set()
    p.log_activity = False
    # v1.6.0 state
    p.push_enabled = False
    p._push_checked = 0.0
    p._last_command = {}
    p._pulse_until = {}
    p._moved = {}
    p._wrong_device = {}
    p._wrong_warned = set()
    p._relocate_at = {}
    p.triggers = []
    # v1.6.1 state
    p._state_lock = MOD.threading.Lock()
    p._last_read = {}
    p._push_at = {}
    p._slot_warned = set()
    return p


class Dev:
    def __init__(self, dev_id=1, name="Garage Strip Lights", type_id="shellyRelay",
                 ip="192.168.1.28", props=None):
        self.id, self.name, self.deviceTypeId = dev_id, name, type_id
        self.enabled = True
        self.pluginProps = {"ip_address": ip}
        self.pluginProps.update(props or {})
        self.errorState = ""
        self.error_writes = []
        self.states = {}

    def setErrorStateOnServer(self, text):
        self.errorState = text
        self.error_writes.append(text)

    def updateStateOnServer(self, key, value, **k):
        self.states[key] = value

    def updateStatesOnServer(self, kv):
        for item in kv:
            self.states[item["key"]] = item["value"]


class _Log:
    def __init__(self):
        self.lines = []

    def __call__(self, msg, level="INFO"):
        self.lines.append((level, msg))


@pytest.fixture
def logged(monkeypatch):
    lg = _Log()
    monkeypatch.setattr(MOD, "log", lg)
    return lg


class _Stop(Exception):
    pass


def test_one_bad_device_does_not_stop_polling(monkeypatch, logged):
    p = plugin()
    p.StopThread = _Stop
    bad, good = Dev(1, "Bad"), Dev(2, "Good")
    polled = []

    def update(dev):
        if dev is bad:
            raise RuntimeError("indigo hiccup")
        polled.append(dev.name)
    p._update_device = update
    monkeypatch.setattr(MOD.indigo, "devices", types.SimpleNamespace(iter=lambda *a: [bad, good]))
    ticks = []

    def sleep(_s):
        ticks.append(1)
        if len(ticks) == 2:
            raise _Stop()
    p.sleep = sleep
    p.runConcurrentThread()
    assert polled == ["Good", "Good"], "the loop carried on past the error, tick after tick"
    assert any("Bad: poll error" in m for _l, m in logged.lines)


def test_send_status_request_polls_a_relay(monkeypatch):
    p = plugin()
    polled = []
    p._update_device = lambda dev: polled.append(dev)
    monkeypatch.setattr(MOD.indigo, "kDeviceAction", types.SimpleNamespace(
        TurnOn=1, TurnOff=2, Toggle=3, RequestStatus=4), raising=False)
    dev = Dev()
    p.actionControlDevice(types.SimpleNamespace(deviceAction=4), dev, None)
    assert polled == [dev]


@pytest.mark.parametrize("ip,ok", [("192.168.1.28", True), (" 192.168.1.28 ", True),
                                   ("", False), ("192.168.1", False), ("192.168.1.300", False),
                                   ("garage", False)])
def test_the_dialog_insists_on_a_real_address(monkeypatch, ip, ok):
    monkeypatch.setattr(MOD.indigo, "Dict", dict, raising=False)
    valid, values, errors = plugin().validateDeviceConfigUi({"ip_address": ip}, "shellyRelay", 1)
    assert valid is ok
    if ok:
        assert values["ip_address"] == "192.168.1.28"


def test_a_single_missed_poll_is_not_a_warning(logged):
    p = plugin()
    dev = Dev()
    p._note_failure(dev, "192.168.1.28")
    p._note_failure(dev, "192.168.1.28")
    assert logged.lines == [] and dev.error_writes == []
    p._note_recovery(dev)
    assert logged.lines == [], "no all-clear for an alarm nobody heard"


def test_three_missed_polls_are(logged):
    p = plugin()
    dev = Dev()
    for _ in range(3):
        p._note_failure(dev, "192.168.1.28")
    assert dev.errorState == "unreachable"
    assert [lvl for lvl, _m in logged.lines] == ["WARNING"]
    p._note_recovery(dev)
    assert logged.lines[-1] == ("INFO", "Garage Strip Lights: responding again after 3 failed poll(s)")
    assert dev.errorState == ""


def test_an_often_unpowered_device_is_reported_at_info(logged):
    p = plugin()
    dev = Dev(props={"expected_absent": True})
    for _ in range(3):
        p._note_failure(dev, "192.168.1.25")
    assert [lvl for lvl, _m in logged.lines] == ["INFO"]


def test_no_address_is_said_once(logged):
    p = plugin()
    dev = Dev(ip="")
    for _ in range(5):
        assert p._fetch_status(dev) is None
    assert len(logged.lines) == 1


def test_a_pulse_reads_the_relay_back_when_its_timer_ends(monkeypatch, logged):
    p = plugin()
    dev = Dev()
    monkeypatch.setattr(MOD.indigo, "devices", {dev.id: dev})
    monkeypatch.setattr(MOD, "_http_get_retry", lambda url: '{"ison": true}')
    timers = []

    class _Timer:
        def __init__(self, delay, fn, args=()):
            timers.append((delay, fn, args))
            self.daemon = False

        def start(self):
            pass
    monkeypatch.setattr(MOD.threading, "Timer", _Timer)
    p.pulseRelay(types.SimpleNamespace(deviceId=dev.id))
    assert dev.states["onOffState"] is True
    delay, fn, args = timers[0]
    assert delay == 2 + MOD.PULSE_REPOLL_SECS and args == (dev.id,)


def test_a_pulse_on_a_deleted_device_says_so(monkeypatch, logged):
    monkeypatch.setattr(MOD.indigo, "devices", {})
    plugin().pulseRelay(types.SimpleNamespace(deviceId=99))
    assert logged.lines == [("ERROR", "Pulse Relay: device 99 no longer exists")]


def test_on_off_narration_stays_in_the_plugins_own_log(monkeypatch, logged):
    p = plugin()
    p.logger = MagicMock()
    p.log_activity = False
    monkeypatch.setattr(MOD, "_http_get_retry", lambda url: '{"ison": false}')
    dev = Dev()
    p._relay_cmd(dev, "192.168.1.28", "off")
    assert logged.lines == []
    p.logger.debug.assert_called_with('sent "Garage Strip Lights" off')
    p.log_activity = True
    p._relay_cmd(dev, "192.168.1.28", "off")
    p.logger.info.assert_called_with('sent "Garage Strip Lights" off')


def test_last_update_carries_the_date(monkeypatch):
    p = plugin()
    dev = types.SimpleNamespace(id=1, name="Qashqai", batches=[], states={},
                                updateStatesOnServer=lambda kv: dev.batches.append(kv),
                                updateStateImageOnServer=lambda *a: None)
    p._fetch_status = lambda d: {"adcs": [{"voltage": 12.6}]}
    p._update_adc(dev)
    stamp = next(k["value"] for k in dev.batches[0] if k["key"] == "lastUpdate")
    assert len(stamp) == 19 and stamp[2] == "-" and stamp[5] == "-"
