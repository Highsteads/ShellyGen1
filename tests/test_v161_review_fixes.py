#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename:    test_v161_review_fixes.py
# Description: v1.6.1: the independent review of 1.6.0. A copied or re-pointed
#              device no longer goes back to the old Shelly, Last Switched By
#              holds between polls, a replaced Shelly can be accepted, push
#              settings apply without a reload, a switched-off slot of someone
#              else's is left alone, a push beats an older poll, a disabled or
#              wrong device takes no push, and push set-up checks identity.
# Author:      CliveS & Claude Opus 5.5
# Date:        27-09-2026
# Version:     1.0

import json
import threading
import types

import pytest

from test_sql_logger_churn import MOD
from test_v153_fixes import _Log, plugin
from test_v160_features import RelayDev, _Devs, _p


@pytest.fixture
def logged(monkeypatch):
    lg = _Log()
    monkeypatch.setattr(MOD, "log", lg)
    return lg


# ── H1: copied or re-pointed devices ─────────────────────────────────────────

def test_a_new_address_forgets_the_old_mac(monkeypatch):
    dev = RelayDev(1, "Porch Relay", ip="192.168.1.28", props={"mac_address": "AABBCC000002"})
    monkeypatch.setattr(MOD.indigo, "devices", _Devs([dev]))
    monkeypatch.setattr(MOD.indigo, "Dict", dict, raising=False)
    ok, values, _e = plugin().validateDeviceConfigUi(
        {"ip_address": "192.168.1.30", "mac_address": "AABBCC000002"}, "shellyRelay", 1)
    assert ok and values["mac_address"] == ""
    ok, values, _e = plugin().validateDeviceConfigUi(
        {"ip_address": "192.168.1.28", "mac_address": "AABBCC000002"}, "shellyRelay", 1)
    assert ok and values["mac_address"] == "AABBCC000002", "same address keeps its MAC"


def test_two_relays_cannot_share_a_shelly(monkeypatch):
    garage = RelayDev(1, "Garage Relay", ip="192.168.1.28")
    uni = RelayDev(3, "Qashqai", type_id="shellyUniADC", ip="192.168.1.25")
    monkeypatch.setattr(MOD.indigo, "devices", _Devs([garage, uni]))
    monkeypatch.setattr(MOD.indigo, "Dict", dict, raising=False)
    ok, _v, errors = plugin().validateDeviceConfigUi({"ip_address": "192.168.1.28"}, "shellyRelay", 2)
    assert not ok and "Garage Relay" in errors["ip_address"]
    ok, _v, _e = plugin().validateDeviceConfigUi({"ip_address": "192.168.1.25"}, "shellyRelay", 2)
    assert ok, "a UNI's relay and its voltage input are different kinds of device"


def test_a_search_never_moves_a_device_onto_anothers_address(monkeypatch, logged):
    garage = RelayDev(1, "Garage Relay", ip="192.168.1.28", props={"mac_address": "AABBCC000002"})
    copy = RelayDev(2, "Porch Relay", ip="192.168.1.30", props={"mac_address": "AABBCC000002"})
    monkeypatch.setattr(MOD.indigo, "devices", _Devs([garage, copy]))
    monkeypatch.setattr(MOD, "_http_get", lambda url, timeout=None: json.dumps(
        {"mac": "AABBCC000002"}) if url == "http://192.168.1.28/shelly" else None)
    _p()._relocate(2)
    assert copy.pluginProps["ip_address"] == "192.168.1.30"
    assert "Garage Relay" in logged.lines[-1][1]


# ── H2: Last Switched By holds ───────────────────────────────────────────────

def _poll(monkeypatch, p, dev, relay):
    monkeypatch.setattr(MOD.indigo, "devices", _Devs([dev]))
    p._fetch_status = lambda d: {"relays": [relay]}
    p._update_relay(dev)


def test_an_unmoved_relay_keeps_who_switched_it(monkeypatch):
    p = _p()
    p._fire_trigger = lambda *a: None
    dev = RelayDev(1, "Garage Strip Lights")
    dev.states.update(onOffState=True, lastChangedBy="Indigo")
    _poll(monkeypatch, p, dev, {"ison": True, "source": "http"})
    assert dev.states["lastChangedBy"] == "Indigo"
    assert not any(k["key"] == "lastChangedBy" for b in dev.batches for k in b)


def test_indigos_command_counts_until_the_next_reading(monkeypatch):
    """A command whose reply was lost is still Indigo's at the next poll,
    however long that takes - it came after the previous reading."""
    p = _p(_last_read={1: 1000.0}, _last_command={1: 1005.0})
    fired = []
    p._fire_trigger = lambda t, d: fired.append(t)
    dev = RelayDev(1, "Garage Strip Lights")
    dev.states.update(onOffState=False)
    _poll(monkeypatch, p, dev, {"ison": True, "source": "http"})
    assert dev.states["lastChangedBy"] == "Indigo" and fired == []


def test_another_apps_command_is_not_indigos(monkeypatch):
    p = _p(_last_read={1: 1000.0}, _last_command={1: 900.0})
    fired = []
    p._fire_trigger = lambda t, d: fired.append(t)
    dev = RelayDev(1, "Garage Strip Lights")
    dev.states.update(onOffState=False)
    _poll(monkeypatch, p, dev, {"ison": True, "source": "http"})
    assert dev.states["lastChangedBy"] == "another app on the network"
    assert fired == ["switchedOutsideIndigo"]


# ── M4: a push beats an older reading ────────────────────────────────────────

def test_a_push_during_a_poll_wins(monkeypatch):
    p = _p()
    dev = RelayDev(1, "Garage Strip Lights")
    dev.states.update(onOffState=True)
    p._moved[1] = True

    def slow_status(d):
        p._push_at[1] = MOD.time.time() + 1      # the push lands while this read is out
        return {"relays": [{"ison": False, "source": "input"}]}
    monkeypatch.setattr(MOD.indigo, "devices", _Devs([dev]))
    p._fetch_status = slow_status
    p._update_relay(dev)
    assert dev.states["onOffState"] is True and dev.batches == []
    assert p._moved[1] is True, "left for the push's own read-back"


# ── M5 / L1: pushes a device must not take ───────────────────────────────────

def _handle(monkeypatch, p, dev):
    monkeypatch.setattr(MOD.indigo, "devices", _Devs([dev]))
    monkeypatch.setattr(MOD.threading, "Thread", lambda target=None, args=(), daemon=None:
                        types.SimpleNamespace(start=lambda: None))
    return p._handle_push("/shellyG1?devId=1&ev=on", "192.168.1.28")


def test_a_disabled_device_takes_no_push(monkeypatch):
    dev = RelayDev(1, "Garage Strip Lights", ip="192.168.1.28")
    dev.enabled = False
    p = _p()
    assert _handle(monkeypatch, p, dev) == 409 and "onOffState" not in dev.states
    assert 1 not in p._moved


def test_stopping_a_device_forgets_a_pending_push():
    p = _p()
    p._moved[1] = True
    p.deviceStopComm(RelayDev(1, "Garage Strip Lights"))
    assert 1 not in p._moved


def test_the_wrong_device_takes_no_push(monkeypatch):
    p = _p()
    p._wrong_device[1] = "AABBCC000001"
    dev = RelayDev(1, "Garage Strip Lights", ip="192.168.1.28")
    assert _handle(monkeypatch, p, dev) == 409 and "onOffState" not in dev.states


def test_push_setup_checks_identity_first(monkeypatch):
    sent = []
    monkeypatch.setattr(MOD, "_http_get", lambda url, timeout=None: json.dumps(
        {"mac": "AABBCC000001"}) if url.endswith("/shelly") else sent.append(url))
    _p()._ensure_push(RelayDev(1, "Garage", ip="192.168.1.28", props={"mac_address": "AABBCC000002"}))
    assert sent == [], "another box at the address gets nothing written to it"


# ── M1: a replaced Shelly ────────────────────────────────────────────────────

def test_a_replaced_shelly_can_be_accepted(monkeypatch, logged):
    dev = RelayDev(1, "Garage Strip Lights", ip="192.168.1.28", props={"mac_address": "AABBCC000002"})
    dev.errorState = "wrong device"
    monkeypatch.setattr(MOD.indigo, "devices", _Devs([dev]))
    p = _p()
    p._wrong_device[1] = "AABBCC000009"
    p._wrong_warned.add(1)
    p.menuAcceptReplaced()
    assert dev.pluginProps["mac_address"] == "AABBCC000009"
    assert p._wrong_device == {} and dev.errorState == ""
    assert logged.lines[-1][1] == "Accepted replaced Shellys: Garage Strip Lights is now AABBCC000009."


# ── M2 / L4: push settings apply without a reload ────────────────────────────

def test_a_new_port_moves_the_listener(monkeypatch, logged):
    p = _p(push_port=8180)
    stopped, started, ensured = [], [], []
    p.push_server = types.SimpleNamespace(shutdown=lambda: stopped.append(1), server_close=lambda: None)
    p._start_push_server = lambda: started.append(p.push_port) or setattr(p, "push_server", object())
    p._ensure_push_all = lambda: ensured.append(1)
    p._apply_push_change((True, 8179, "192.168.1.9"))
    assert stopped == [1] and started == [8180] and ensured == [1]


def test_switching_push_off_takes_our_urls_away(monkeypatch, logged):
    ours = "http://192.168.1.9:8179/shellyG1?devId=1&ev=on"
    theirs = "http://nas.local/hook"
    actions = {"actions": {"out_on_url": [{"index": 0, "enabled": True, "urls": [theirs, ours]}],
                           "out_off_url": [{"index": 0, "enabled": True, "urls": []}]}}
    writes = []

    def fake_get(url, timeout=None):
        if url.endswith("/settings/actions"):
            return json.dumps(actions)
        writes.append(url)
        return json.dumps({"actions": {"out_on_url": [{"index": 0, "urls": [theirs]}]}})
    monkeypatch.setattr(MOD, "_http_get", fake_get)
    _p(push_enabled=False)._ensure_push(RelayDev(1, "Garage", ip="192.168.1.28"))
    assert len(writes) == 1 and "nas.local" in writes[0] and "shellyG1" not in writes[0]
    assert "enabled=true" in writes[0], "their URL stays switched on"
    assert logged.lines[-1][1] == "Garage: no longer sends push updates to Indigo"


# ── M3 / L3: other people's action slots ─────────────────────────────────────

def _slot_run(monkeypatch, slot):
    actions = {"actions": {"out_on_url": [slot], "out_off_url": [slot]}}
    writes = []

    def fake_get(url, timeout=None):
        if url.endswith("/shelly"):
            return json.dumps({"mac": "AABBCC000002"})
        if url.endswith("/settings/actions"):
            return json.dumps(actions)
        writes.append(url)
        q = url.split("?", 1)[1]
        name = MOD.urllib.parse.parse_qs(q)["name"][0]
        saved = [MOD.urllib.parse.unquote(v) for k, v in
                 (pair.split("=", 1) for pair in q.split("&")) if k == "urls[]"]
        return json.dumps({"actions": {name: [{"index": 0, "urls": saved}]}})
    monkeypatch.setattr(MOD, "_http_get", fake_get)
    p = _p()
    dev = RelayDev(1, "Garage", ip="192.168.1.28", props={"mac_address": "AABBCC000002"})
    p._ensure_push(dev)
    p._ensure_push(dev)
    return writes


def test_a_switched_off_slot_of_someone_elses_is_left_alone(monkeypatch, logged):
    writes = _slot_run(monkeypatch, {"index": 0, "enabled": False, "urls": ["http://nas.local/x"]})
    assert writes == []
    assert len([m for lvl, m in logged.lines if lvl == "WARNING"]) == 2, "once per slot, not per run"


def test_a_full_slot_says_what_it_dropped(monkeypatch, logged):
    full = [f"http://x/{i}" for i in range(5)]
    writes = _slot_run(monkeypatch, {"index": 0, "enabled": True, "urls": full})
    assert writes
    assert any("http://x/4 was removed to make room" in m for _l, m in logged.lines)


# ── L7: the scan ─────────────────────────────────────────────────────────────

def test_the_scan_keeps_host_order_and_uses_daemon_threads(monkeypatch):
    seen = []
    real = threading.Thread

    def spy(*a, **k):
        seen.append(k.get("daemon"))
        return real(*a, **k)
    monkeypatch.setattr(MOD.threading, "Thread", spy)
    hits = MOD.scan_hosts([f"h{i}" for i in range(40)], lambda h: h if h in ("h30", "h3") else None)
    assert hits == ["h3", "h30"]
    assert seen and all(seen)


def test_an_indigo_command_records_indigo_and_the_read_back_keeps_it(monkeypatch, logged):
    """Found live: the command wrote onOffState itself, so the device's own
    report saw no change and Last Switched By never said Indigo."""
    p = _p()
    fired = []
    p._fire_trigger = lambda t, d: fired.append(t)
    dev = RelayDev(1, "Garage Strip Lights")
    dev.states.update(onOffState=False, lastChangedBy="another app on the network")
    monkeypatch.setattr(MOD, "_http_get_retry", lambda url: '{"ison": true}')
    p._relay_cmd(dev, "192.168.1.28", "on")
    assert dev.states["lastChangedBy"] == "Indigo" and dev.states["onOffState"] is True
    _poll(monkeypatch, p, dev, {"ison": True, "source": "http"})
    assert dev.states["lastChangedBy"] == "Indigo" and fired == []


def test_a_command_that_changes_nothing_claims_nothing(monkeypatch, logged):
    p = _p()
    dev = RelayDev(1, "Garage Strip Lights")
    dev.states.update(onOffState=True, lastChangedBy="the switch wired to the device")
    monkeypatch.setattr(MOD, "_http_get_retry", lambda url: '{"ison": true}')
    p._relay_cmd(dev, "192.168.1.28", "on")
    assert dev.states["lastChangedBy"] == "the switch wired to the device"
