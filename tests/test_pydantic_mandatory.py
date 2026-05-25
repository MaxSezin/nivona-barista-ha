"""B8 — pydantic is mandatory; soft-degrade path is gone."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Module-level imports — pytest-homeassistant-custom-component shadows the
# `custom_components` namespace once tests start running, so imports must
# happen at collection time to resolve against the worktree's package.
from custom_components.melitta_barista import panel_api
from custom_components.melitta_barista.panel_api import (
    RESPONSE_MODELS,
    ValidationError,
)
from pydantic import ValidationError as PydanticVE


def test_pydantic_ok_flag_gone():
    """`_PYDANTIC_OK` no longer exists in panel_api — module has no soft-degrade."""
    assert not hasattr(panel_api, "_PYDANTIC_OK"), \
        "_PYDANTIC_OK is a leftover from the soft-degrade path that B8 removed"


def test_response_models_populated():
    """RESPONSE_MODELS is non-empty (pydantic loaded at import time)."""
    assert "sommelier_intro" in RESPONSE_MODELS, \
        "sommelier_intro model must always be present (pydantic is mandatory)"


def test_validation_error_is_pydantic():
    """`ValidationError` imported from pydantic, not the Exception fallback."""
    assert ValidationError is PydanticVE, \
        "ValidationError must be the real pydantic class, not Exception"


def test_manifest_lists_pydantic():
    """manifest.json must declare pydantic as a runtime requirement."""
    manifest_path = (
        Path(__file__).parent.parent
        / "custom_components" / "melitta_barista" / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text())
    requirements = manifest.get("requirements", [])
    assert any("pydantic" in r for r in requirements), \
        f"pydantic missing from manifest requirements: {requirements}"
