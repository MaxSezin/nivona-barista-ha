"""MachineRegistry behavior."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.melitta_barista.coffee_platform.registry import (
    MachineRegistry,
)


def _fake_client(address: str):
    c = MagicMock()
    c.address = address
    return c


def test_register_and_get_by_address():
    reg = MachineRegistry()
    client = _fake_client("AA:BB:CC:DD:EE:FF")
    reg.register(client)
    assert reg.get_by_address("AA:BB:CC:DD:EE:FF") is client


def test_list_machines_returns_all():
    reg = MachineRegistry()
    a = _fake_client("AA:BB:CC:DD:EE:01")
    b = _fake_client("AA:BB:CC:DD:EE:02")
    reg.register(a)
    reg.register(b)
    assert set(reg.list_machines()) == {a, b}


def test_unregister_removes():
    reg = MachineRegistry()
    client = _fake_client("AA:BB:CC:DD:EE:FF")
    reg.register(client)
    reg.unregister("AA:BB:CC:DD:EE:FF")
    assert reg.get_by_address("AA:BB:CC:DD:EE:FF") is None
    assert reg.list_machines() == []


def test_get_missing_returns_none():
    reg = MachineRegistry()
    assert reg.get_by_address("NO:SU:CH:AD:DR:ES") is None
