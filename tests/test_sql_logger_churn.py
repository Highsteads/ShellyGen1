#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename:    test_sql_logger_churn.py
# Description: v1.5.2. The UNI ADC poll wrote voltage and lastUpdate as two state
#              updates, so SQL Logger stored two rows every 30 s, one of them
#              lastUpdate alone. The states now go in ONE call, and lastUpdate is
#              added to the device's sqlLoggerIgnoreStates shared prop.
# Author:      CliveS & Claude Opus 5.5
# Date:        23-09-2026
# Version:     1.0

import os
import sys
import types
from unittest.mock import MagicMock

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(os.path.dirname(HERE), "ShellyGen1.indigoPlugin", "Contents", "Server Plugin")

_ind = types.ModuleType("indigo")


class _PB:
    def __init__(self, *a, **k):
        self.logger = MagicMock()


_ind.PluginBase = _PB
_ind.kStateImageSel = MagicMock()
_ind.server = MagicMock()
_ind.devices = MagicMock()
sys.modules["indigo"] = _ind
sys.path.insert(0, SERVER)

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("shellyg1_plugin", os.path.join(SERVER, "plugin.py"))
MOD = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(MOD)


class FakeDev:
    def __init__(self, shared=None):
        self.id = 1
        self.name = "Qashqai Battery Monitor"
        self.deviceTypeId = "shellyUniADC"
        self.sharedProps = dict(shared or {})
        self.shared_writes = 0
        self.batches = []
        self.singles = []

    def replaceSharedPropsOnServer(self, props):
        self.sharedProps = dict(props)
        self.shared_writes += 1

    def updateStatesOnServer(self, states):
        self.batches.append(states)

    def updateStateOnServer(self, *a, **k):
        self.singles.append(a)

    def updateStateImageOnServer(self, *a):
        pass


def plugin():
    p = MOD.Plugin.__new__(MOD.Plugin)
    p.logger = MagicMock()
    p.debug = False
    return p


def test_the_merge_keeps_the_user_and_never_narrows_star():
    assert MOD.merge_sql_logger_ignore("") == "lastUpdate"
    assert MOD.merge_sql_logger_ignore("onOffState") == "onOffState, lastUpdate"
    assert MOD.merge_sql_logger_ignore("LASTUPDATE") is None
    assert MOD.merge_sql_logger_ignore("*") is None


def test_one_reading_is_one_state_update():
    p = plugin()
    p._fetch_status = lambda dev: {"adcs": [{"voltage": 12.34}]}
    dev = FakeDev()
    p._update_adc(dev)
    assert dev.singles == []
    assert len(dev.batches) == 1
    keys = [s["key"] for s in dev.batches[0]]
    assert keys == ["onOffState", "voltage", "lastUpdate"]
    assert dev.batches[0][1]["uiValue"] == "12.34 V"


def test_start_comm_adds_last_update_once():
    p = plugin()
    p._update_device = lambda dev: None
    dev = FakeDev()
    p.deviceStartComm(dev)
    p.deviceStartComm(dev)
    assert dev.sharedProps["sqlLoggerIgnoreStates"] == "lastUpdate"
    assert dev.shared_writes == 1


def test_a_failed_write_does_not_stop_the_device():
    p = plugin()
    polled = []
    p._update_device = lambda dev: polled.append(dev)
    dev = FakeDev()

    def boom(props):
        raise RuntimeError("server said no")
    dev.replaceSharedPropsOnServer = boom
    p.deviceStartComm(dev)
    assert polled == [dev]
