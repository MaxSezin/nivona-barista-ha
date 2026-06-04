"""Domain relocation invariants: self-containment + shim identity."""

from __future__ import annotations

import ast
import pathlib


def test_coffee_platform_has_no_melitta_imports():
    """coffee_platform/ must not import from melitta_barista internals.

    It depends only on stdlib so it can be lifted into a standalone repo.
    Walks every .py file in the subpackage and rejects any relative import
    that escapes the subpackage (level >= 2 reaching into melitta_barista)
    or any absolute `custom_components.melitta_barista` import.
    """
    pkg = (
        pathlib.Path(__file__).resolve().parents[2]
        / "custom_components"
        / "melitta_barista"
        / "coffee_platform"
    )
    offenders = []
    for path in pkg.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level and node.level >= 2:
                    offenders.append(f"{path.name}: from {'.' * node.level}{node.module or ''}")
                if node.module and "melitta_barista" in node.module:
                    offenders.append(f"{path.name}: from {node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if "melitta_barista" in alias.name:
                        offenders.append(f"{path.name}: import {alias.name}")
    assert not offenders, "coffee_platform imports melitta_barista internals:\n" + "\n".join(offenders)


def test_shims_reexport_identical_objects():
    """Old import locations re-export the SAME objects now living in domain.

    Guards against a shim accidentally redefining instead of re-exporting.
    """
    from custom_components.melitta_barista.coffee_platform import domain
    from custom_components.melitta_barista.brands import base
    from custom_components.melitta_barista import const, protocol

    assert base.MachineCapabilities is domain.MachineCapabilities
    assert base.BrandProfile is domain.BrandProfile
    assert base.RecipeDescriptor is domain.RecipeDescriptor
    assert base.FeatureNotSupported is domain.FeatureNotSupported
    assert const.MachineProcess is domain.MachineProcess
    assert const.SubProcess is domain.SubProcess
    assert const.InfoMessage is domain.InfoMessage
    assert const.Manipulation is domain.Manipulation
    assert protocol.MachineStatus is domain.MachineStatus
