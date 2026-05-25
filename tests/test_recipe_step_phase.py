"""P2b — RecipeStep.phase enum."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from custom_components.melitta_barista.panel_api import RecipeStep


def test_phase_defaults_to_during():
    """RecipeStep without explicit phase defaults to 'during' (backward-compat)."""
    s = RecipeStep(order=1, action="brew espresso")
    assert s.phase == "during"


def test_phase_accepts_pre():
    s = RecipeStep(order=1, action="take 240ml cup", phase="pre")
    assert s.phase == "pre"


def test_phase_accepts_during():
    s = RecipeStep(order=2, action="brew shot", phase="during")
    assert s.phase == "during"


def test_phase_accepts_post():
    s = RecipeStep(order=3, action="dust with cinnamon", phase="post")
    assert s.phase == "post"


def test_phase_rejects_invalid():
    """Invalid phase value is rejected."""
    with pytest.raises(ValidationError):
        RecipeStep(order=1, action="foo", phase="middle")
