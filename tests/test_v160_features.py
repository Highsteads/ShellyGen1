#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename:    test_v160_features.py
# Description: v1.6.0: push from the relay (actions pointed at the plugin,
#              other URLs kept, the sender checked), identity by MAC, Last
#              Switched By + Switched Outside Indigo, and the pulse length.
# Author:      CliveS & Claude Opus 5.5
# Date:        27-09-2026
# Version:     1.0

import json
import types

import pytest

from test_sql_logger_churn import MOD
from test_v153_fixes import Dev, _Log, plugin


class RelayDev(Dev):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.pluginId = MOD.PLUGIN_ID
        self.batches = []

    def updateStatesOnServer(self, kv, triggerEvents=True, clearErrorState=True):
        self.batches.append(kv)
        for item in kv:
            self.states[item["key"]] = item["value"]
        if clearErrorState:
            self.errorState = ""

    def replacePluginPropsOnServer(self, props):
        self.pluginProps = dict(props)


class _Devs(dict):
    """indigo.devices as the code uses it: [id] and iter()."""

    def __init__(self, devs):
        super().__init__({d.id: d for d in devs})

    def iter(self, *a):
        return list(self.values())


@pytest.fixture
def logged(monkeypatch):
    lg = _Log()
    monkeypatch.setattr(MOD, "log", lg)
    return lg


def _p(**over):
    p = plugin()
    p.server_ip, p.push_port, p.push_enabled = "192.168.1.9", 8179, True
    p._push_lock = MOD.threading.Lock()
    for k, v in over.items():
        setattr(p, k, v)
    return p


# ── the URL list of one action slot ──────────────────────────────────────────

OURS = "http://192.168.1.9:8179/shellyG1?devId=1&ev=on"


def test_ours_is_added_beside_somebody_elses():
    dead = "http://192.168.1.9:7987/?onOffState=1"
    assert MOD.merge_action_urls([dead], OURS) == [dead, OURS]


def test_nothing_changes_when_ours_is_already_there():
    assert MOD.merge_action_urls(["http://x/other", OURS], OURS) is None


def test_our_stale_url_is_replaced():
    old = "http://192.168.1.8:8179/shellyG1?devId=1&ev=on"
    assert MOD.merge_action_urls([old, "http://x/other"], OURS) == ["http://x/other", OURS]


def test_a_full_slot_makes_room_for_ours():
    full = [f"http://x/{i}" for i in range(5)]
    assert MOD.merge_action_urls(full, OURS) == full[:4] + [OURS]


def test_ensure_push_writes_both_slots_and_keeps_other_urls(monkeypatch, logged):
    dead_on, dead_off = "http://192.168.1.9:7987/?onOffState=1", "http://192.168.1.9:7987/?onOffState=0"
    actions = {"actions": {"out_on_url": [{"index": 0, "enabled": True, "urls": [dead_on]}],
                           "out_off_url": [{"index": 0, "enabled": True, "urls": [dead_off]}]}}
    sent = []

    def fake_get(url, timeout=None):
        if url.endswith("/shelly"):
            return json.dumps({"mac": "8CAAB5056390"})
        if url.endswith("/settings/actions"):
            return json.dumps(actions)
        sent.append(url)
        # Echo back what a Shelly saves: the query read the way the device reads it.
        q = url.split("?", 1)[1]
        name = MOD.urllib.parse.parse_qs(q)["name"][0]
        saved = [MOD.urllib.parse.unquote(v) for k, v in
                 (pair.split("=", 1) for pair in q.split("&")) if k == "urls[]"]
        return json.dumps({"actions": {name: [{"index": 0, "urls": saved}]}})
    monkeypatch.setattr(MOD, "_http_get", fake_get)
    _p()._ensure_push(RelayDev(1, "Garage Strip Lights", ip="192.168.1.28",
                               props={"mac_address": "8CAAB5056390"}))
    assert len(sent) == 2
    assert "urls[]=" in sent[0] and "%5B%5D" not in sent[0], "brackets must be literal"
    on = MOD.urllib.parse.parse_qs(sent[0].split("?", 1)[1])
    assert on["name"] == ["out_on_url"] and on["enabled"] == ["true"]
    assert on["urls[]"] == [dead_on, "http://192.168.1.9:8179/shellyG1?devId=1&ev=on"]
    assert any("tells Indigo the moment it switches" in m for _l, m in logged.lines)


def test_an_answer_that_did_not_save_our_url_is_a_failure(monkeypatch, logged):
    """The device accepted a misread query and saved nothing: live, 27-09-2026."""
    actions = {"actions": {n: [{"index": 0, "enabled": True, "urls": []}] for n in MOD.PUSH_EVENTS}}
    monkeypatch.setattr(MOD, "_http_get", lambda url, timeout=None: json.dumps(
        {"mac": "8CAAB5056390"} if url.endswith("/shelly") else actions))
    _p()._ensure_push(RelayDev(1, "Garage Strip Lights", ip="192.168.1.28",
                               props={"mac_address": "8CAAB5056390"}))
    assert [lvl for lvl, _m in logged.lines] == ["WARNING", "WARNING"]
    assert not any("tells Indigo" in m for _l, m in logged.lines)


def test_ensure_push_is_quiet_when_already_set(monkeypatch, logged):
    p = _p()
    dev = RelayDev(1, "Garage Strip Lights", ip="192.168.1.28",
                   props={"mac_address": "8CAAB5056390"})
    actions = {"actions": {n: [{"index": 0, "enabled": True,
                                "urls": [p._push_url(dev, "on" if n == "out_on_url" else "off")]}]
                           for n in MOD.PUSH_EVENTS}}
    sent = []

    def fake_get(url, timeout=None):
        if url.endswith("/shelly"):
            return json.dumps({"mac": "8CAAB5056390"})
        if url.endswith("/settings/actions"):
            return json.dumps(actions)
        sent.append(url)
    monkeypatch.setattr(MOD, "_http_get", fake_get)
    p._ensure_push(dev)
    assert sent == [] and logged.lines == []


# ── the listener ─────────────────────────────────────────────────────────────

def _listener(monkeypatch, dev):
    p = _p()
    monkeypatch.setattr(MOD.indigo, "devices", {dev.id: dev})
    started = []
    monkeypatch.setattr(MOD.threading, "Thread", lambda target=None, args=(), daemon=None:
                        types.SimpleNamespace(start=lambda: started.append(args)))
    return p, started


def test_a_push_from_the_device_sets_the_state_and_reads_it_back(monkeypatch):
    dev = RelayDev(1, "Garage Strip Lights", ip="192.168.1.28", )
    dev.states["onOffState"] = False
    p, started = _listener(monkeypatch, dev)
    assert p._handle_push("/shellyG1?devId=1&ev=on", "192.168.1.28") == 200
    assert dev.states["onOffState"] is True and p._moved[1] is True
    assert started == [(1,)]


def test_a_push_from_any_other_address_is_ignored(monkeypatch):
    dev = RelayDev(1, "Garage Strip Lights", ip="192.168.1.28")
    dev.states["onOffState"] = False
    p, _s = _listener(monkeypatch, dev)
    assert p._handle_push("/shellyG1?devId=1&ev=on", "192.168.1.99") == 409
    assert dev.states["onOffState"] is False


@pytest.mark.parametrize("path", ["/other?devId=1&ev=on", "/shellyG1?devId=2&ev=on",
                                  "/shellyG1?devId=x", "/shellyG1?devId=1&ev=sideways"])
def test_bad_pushes_change_nothing(monkeypatch, path):
    dev = RelayDev(1, "Garage Strip Lights", ip="192.168.1.28")
    p, _s = _listener(monkeypatch, dev)
    assert p._handle_push(path, "192.168.1.28") in (400, 404)
    assert "onOffState" not in dev.states


# ── identity by MAC ──────────────────────────────────────────────────────────

def test_a_mac_is_learned_then_held_to(monkeypatch, logged):
    p = _p()
    monkeypatch.setattr(MOD.threading, "Thread", lambda target=None, args=(), daemon=None:
                        types.SimpleNamespace(start=lambda: None))
    dev = RelayDev(1, "Garage Strip Lights", ip="192.168.1.28")
    assert p._identity_ok(dev, "192.168.1.28", "8C:AA:B5:05:63:90") is True
    assert dev.pluginProps["mac_address"] == "8CAAB5056390"
    assert p._identity_ok(dev, "192.168.1.28", "AABBCC000001") is False
    assert dev.errorState == "wrong device" and p._wrong_device[1] == "AABBCC000001"
    assert [lvl for lvl, _m in logged.lines] == ["INFO", "WARNING"], "learned at INFO (v1.6.1)"
    assert p._identity_ok(dev, "192.168.1.28", "AABBCC000001") is False
    assert len(logged.lines) == 2, "the warning is said once"
    assert p._identity_ok(dev, "192.168.1.28", "8CAAB5056390") is True
    assert 1 not in p._wrong_device


def test_no_command_goes_to_the_wrong_device(monkeypatch, logged):
    p = _p()
    p._wrong_device[1] = "AABBCC000001"
    sent = []
    monkeypatch.setattr(MOD, "_http_get_retry", lambda url: sent.append(url))
    p._relay_cmd(RelayDev(1, "Garage Strip Lights"), "192.168.1.28", "on")
    assert sent == [] and logged.lines[0][0] == "ERROR"


def test_a_device_is_found_again_by_its_mac(monkeypatch, logged):
    p = _p()
    dev = RelayDev(1, "Garage Strip Lights", ip="192.168.1.28",
                   props={"mac_address": "8CAAB5056390"})
    monkeypatch.setattr(MOD.indigo, "devices", _Devs([dev]))

    def fake_get(url, timeout=None):
        if url == "http://192.168.1.40/shelly":
            return json.dumps({"mac": "8CAAB5056390"})
        return None
    monkeypatch.setattr(MOD, "_http_get", fake_get)
    p._relocate(1)
    assert dev.pluginProps["ip_address"] == "192.168.1.40"
    assert "found at 192.168.1.40" in logged.lines[-1][1]
    p._relocate(1)          # throttled: a second search inside the hour does nothing
    assert len(logged.lines) == 1


# ── who switched it ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("source,ours,expect", [
    ("http", True, "Indigo"), ("http", False, "another app on the network"),
    ("input", False, "the switch wired to the device"), ("timer", False, "the device's own timer"),
    ("init", False, "the device starting up"), ("cloud", False, "the Shelly app"),
    ("newthing", False, '"newthing"'), ("", False, "")])
def test_sources_in_words(source, ours, expect):
    assert MOD.switch_source_label(source, ours) == expect


def _relay_poll(monkeypatch, relay, before, **p_over):
    p = _p(**p_over)
    fired = []
    p._fire_trigger = lambda t, d: fired.append((t, d))
    dev = RelayDev(1, "Garage Strip Lights")
    dev.states["onOffState"] = before
    monkeypatch.setattr(MOD.indigo, "devices", _Devs([dev]))
    p._fetch_status = lambda d: {"relays": [relay]}
    p._update_relay(dev)
    return dev, fired


def test_the_wall_switch_fires_switched_outside_indigo(monkeypatch):
    dev, fired = _relay_poll(monkeypatch, {"ison": True, "source": "input"}, False)
    assert dev.states["lastChangedBy"] == "the switch wired to the device"
    assert fired == [("switchedOutsideIndigo", 1)]


def test_indigos_own_command_does_not(monkeypatch):
    dev, fired = _relay_poll(monkeypatch, {"ison": True, "source": "http"}, False,
                             _last_command={1: MOD.time.time()}, _last_read={1: 0.0})
    assert dev.states["lastChangedBy"] == "Indigo" and fired == []


def test_a_pulse_ending_on_its_timer_is_indigos(monkeypatch):
    dev, fired = _relay_poll(monkeypatch, {"ison": False, "source": "timer"}, True,
                             _pulse_until={1: MOD.time.time() + 5})
    assert dev.states["lastChangedBy"] == "Indigo" and fired == []


# ── pulse length ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("props,expect", [({}, "timer=2"), ({"seconds": "5"}, "timer=5"),
                                          ({"seconds": "1.5"}, "timer=1.5"),
                                          ({"seconds": "junk"}, "timer=2")])
def test_the_pulse_length_comes_from_the_action(monkeypatch, logged, props, expect):
    p = _p()
    dev = RelayDev(1, "Garage Strip Lights")
    monkeypatch.setattr(MOD.indigo, "devices", {1: dev})
    sent = []
    monkeypatch.setattr(MOD, "_http_get_retry", lambda url: sent.append(url) or "{}")
    monkeypatch.setattr(MOD.threading, "Timer", lambda *a, **k: types.SimpleNamespace(
        start=lambda: None, daemon=False))
    p.pulseRelay(types.SimpleNamespace(deviceId=1, props=props))
    assert sent[0].endswith(expect)


@pytest.mark.parametrize("secs,ok", [("2", True), ("0.5", True), ("0.1", False), ("x", False)])
def test_the_pulse_dialog_checks_its_number(monkeypatch, secs, ok):
    monkeypatch.setattr(MOD.indigo, "Dict", dict, raising=False)
    valid, _v, _e = plugin().validateActionConfigUi({"seconds": secs}, "pulseRelay", 1)
    assert valid is ok


@pytest.mark.parametrize("port,ip,ok", [("8179", "", True), ("80", "", False),
                                        ("8179", "192.168.1.9", True), ("8179", "mac", False)])
def test_the_settings_check_port_and_address(monkeypatch, port, ip, ok):
    monkeypatch.setattr(MOD.indigo, "Dict", dict, raising=False)
    valid, _v, _e = plugin().validatePrefsConfigUi({"push_port": port, "indigo_server_ip": ip})
    assert valid is ok
