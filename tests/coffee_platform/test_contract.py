"""Contract compliance — MelittaBleClient must satisfy CoffeeMachineClient."""

from __future__ import annotations

import typing

from custom_components.melitta_barista.ble_client import MelittaBleClient
from custom_components.melitta_barista.coffee_platform.contract import (
    CoffeeMachineClient,
)


def _protocol_members(proto) -> set[str]:
    """Declared members of a Protocol: methods (via dir) + data attrs (via
    __annotations__), minus typing.Protocol machinery.

    Bare-annotation data attributes (e.g. `address: str`) don't appear in
    dir(proto) — they only live in __annotations__ — so we must union both
    sources to check the full contract surface.
    """
    base = set(dir(typing.Protocol))
    from_dir = {name for name in dir(proto) if not name.startswith("_")} - base
    from_annotations = set(getattr(proto, "__annotations__", {}))
    return from_dir | from_annotations


def test_melitta_client_satisfies_contract():
    """Every member declared in CoffeeMachineClient exists on MelittaBleClient.

    Catches contract drift: if the contract gains a member the Eugster client
    doesn't provide, this fails — forcing the provider to implement it or the
    contract to drop it.
    """
    required = _protocol_members(CoffeeMachineClient)
    missing = sorted(m for m in required if not hasattr(MelittaBleClient, m))
    assert not missing, f"MelittaBleClient missing contract members: {missing}"
