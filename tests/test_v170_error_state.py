#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename:    test_v170_error_state.py
# Description: v1.7.0: a dead Shelly keeps its error state. Indigo's state
#              writes clear a device's error unless told not to, so a push or
#              a command reply wiped "unreachable" while the failure count
#              stood - and the error was never set again, so Device Health
#              Monitor saw a healthy device. Only a good poll ends the fault.
# Author:      CliveS & Claude Opus 5.5
# Date:        27-09-2026
# Version:     1.0

import ast
import json
import os
import types

import pytest

from test_sql_logger_churn import MOD, SERVER
from test_v153_fixes import _Log
from test_v160_features import RelayDev, _Devs, _p

IP = "192.168.1.28"


@pytest.fixture
def logged(monkeypatch):
    lg = _Log()
    monkeypatch.setattr(MOD, "log", lg)
    return lg


@pytest.fixture
def no_threads(monkeypatch):
    started = []
    monkeypatch.setattr(MOD.threading, "Thread", lambda target=None, args=(), daemon=None:
                        types.SimpleNamespace(start=lambda: started.append((target, args))))
    return started


def _down(p, dev):
    """Three failed polls: the device is called unreachable."""
    for _ in range(MOD.FAIL_WARN_AFTER):
        p._note_failure(dev, IP)
    assert dev.errorState == "unreachable"


def test_a_push_keeps_the_unreachable_error(monkeypatch, logged, no_threads):
    dev = RelayDev(1, "Garage Strip Lights", ip=IP)
    monkeypatch.setattr(MOD.indigo, "devices", _Devs([dev]))
    p = _p()
    _down(p, dev)
    assert p._handle_push("/shellyG1?devId=1&ev=on", IP) == 200
    assert dev.states["onOffState"] is True
    assert dev.errorState == "unreachable", "a push is not the plugin deciding it has recovered"


def test_the_error_survives_a_push_whose_read_back_fails(monkeypatch, logged, no_threads):
    """The case that hid a dead device for good: the push cleared the error,
    the read-back failed, and the count was past the point where it is set."""
    dev = RelayDev(1, "Garage Strip Lights", ip=IP)
    monkeypatch.setattr(MOD.indigo, "devices", _Devs([dev]))
    monkeypatch.setattr(MOD, "_http_get_retry", lambda url, timeout=None: None)
    p = _p()
    _down(p, dev)
    p._handle_push("/shellyG1?devId=1&ev=off", IP)
    for _ in range(5):
        p._update_relay(dev)
    assert dev.errorState == "unreachable"


def test_a_command_reply_keeps_the_error(monkeypatch, logged):
    dev = RelayDev(1, "Garage Strip Lights", ip=IP)
    dev.states.update(onOffState=False)
    p = _p()
    _down(p, dev)
    monkeypatch.setattr(MOD, "_http_get_retry", lambda url, timeout=None: json.dumps({"ison": True}))
    p._relay_cmd(dev, IP, "on")
    assert dev.states["onOffState"] is True and dev.states["lastChangedBy"] == "Indigo"
    assert dev.errorState == "unreachable"


def test_a_good_poll_still_ends_the_fault(monkeypatch, logged):
    dev = RelayDev(1, "Garage Strip Lights", ip=IP)
    monkeypatch.setattr(MOD.indigo, "devices", _Devs([dev]))
    p = _p()
    p._fire_trigger = lambda *a: None
    _down(p, dev)
    monkeypatch.setattr(MOD, "_http_get_retry", lambda url, timeout=None: json.dumps(
        {"relays": [{"ison": True, "source": "input"}]}))
    p._update_relay(dev)
    assert dev.errorState == "" and dev.states["onOffState"] is True


def test_a_wrong_device_keeps_its_error_through_a_command_elsewhere(monkeypatch, logged):
    """Wrong device is cleared only when the right MAC answers again."""
    dev = RelayDev(1, "Garage Strip Lights", ip=IP, props={"mac_address": "AABBCC000001"})
    monkeypatch.setattr(MOD.indigo, "devices", _Devs([dev]))
    p = _p()
    p._relocate = lambda *a: None
    monkeypatch.setattr(MOD.threading, "Thread", lambda target=None, args=(), daemon=None:
                        types.SimpleNamespace(start=lambda: None))
    monkeypatch.setattr(MOD, "_http_get_retry", lambda url, timeout=None: json.dumps(
        {"mac": "AABBCC000009", "relays": [{"ison": True}]}))
    p._update_relay(dev)
    assert dev.errorState == "wrong device" and dev.batches == []
    monkeypatch.setattr(MOD, "_http_get_retry", lambda url, timeout=None: json.dumps(
        {"mac": "AABBCC000001", "relays": [{"ison": True, "source": "input"}]}))
    p._fire_trigger = lambda *a: None
    p._update_relay(dev)
    assert dev.errorState == ""


def test_a_wrong_device_that_went_quiet_is_called_wrong_again(monkeypatch, logged):
    """Wrong box answers, goes quiet (unreachable), answers again: the label
    goes back to "wrong device", and the warning is still said only once."""
    dev = RelayDev(1, "Garage Strip Lights", ip=IP, props={"mac_address": "AABBCC000001"})
    monkeypatch.setattr(MOD.indigo, "devices", _Devs([dev]))
    monkeypatch.setattr(MOD.threading, "Thread", lambda target=None, args=(), daemon=None:
                        types.SimpleNamespace(start=lambda: None))
    p = _p()
    wrong = json.dumps({"mac": "AABBCC000009", "relays": [{"ison": True}]})
    monkeypatch.setattr(MOD, "_http_get_retry", lambda url, timeout=None: wrong)
    p._update_relay(dev)
    assert dev.errorState == "wrong device"
    monkeypatch.setattr(MOD, "_http_get_retry", lambda url, timeout=None: None)
    for _ in range(MOD.FAIL_WARN_AFTER):
        p._update_relay(dev)
    assert dev.errorState == "unreachable"
    monkeypatch.setattr(MOD, "_http_get_retry", lambda url, timeout=None: wrong)
    p._update_relay(dev)
    assert dev.errorState == "wrong device" and dev.batches == []
    assert sum("is answering as" in m for _l, m in logged.lines) == 1


def test_every_state_write_leaves_the_error_alone():
    """A guard on the source: any new state write must pass
    clearErrorState=False, or it would start wiping the error again."""
    tree = ast.parse(open(os.path.join(SERVER, "plugin.py"), encoding="utf-8").read())
    writes = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
              and isinstance(n.func, ast.Attribute)
              and n.func.attr in ("updateStateOnServer", "updateStatesOnServer")]
    assert len(writes) >= 4
    for call in writes:
        flag = {k.arg: k.value for k in call.keywords}.get("clearErrorState")
        assert isinstance(flag, ast.Constant) and flag.value is False, \
            f"line {call.lineno}: {call.func.attr} without clearErrorState=False"
