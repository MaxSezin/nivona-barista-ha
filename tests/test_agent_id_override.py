"""B7 — per-request agent_id override in /sommelier/generate."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.melitta_barista import sommelier_api as sa
from custom_components.melitta_barista.panel_api import _resolve_agent_id


@pytest.mark.asyncio
async def test_resolve_agent_id_msg_wins_over_settings():
    """msg['agent_id'] takes precedence over settings.llm_agent_id."""
    db = MagicMock()
    db.async_get_settings = AsyncMock(return_value={"llm_agent_id": "default_agent"})

    hass = MagicMock()
    hass.data = {"melitta_barista": {"sommelier_db": db}}

    with patch(
        "custom_components.melitta_barista.panel_api._async_get_db",
        new=AsyncMock(return_value=db),
    ):
        # Explicit msg agent_id wins
        assert await _resolve_agent_id(hass, {"agent_id": "override_agent"}) == "override_agent"
        # Empty / missing -> settings fallback
        assert await _resolve_agent_id(hass, {}) == "default_agent"


@pytest.mark.asyncio
async def test_ws_generate_uses_resolve_agent_id():
    """ws_generate routes agent_id through _resolve_agent_id (not direct settings lookup)."""
    captured: dict = {}

    async def _fake_structured_call(hass, **kwargs):
        captured.update(kwargs)
        return {"parsed": {"recipes": []}, "validation_errors": []}

    db = MagicMock()
    db.async_get_hoppers = AsyncMock(return_value={"hopper1": {}, "hopper2": {}})
    db.async_get_milk = AsyncMock(return_value=[])
    db.async_get_extras = AsyncMock(return_value={"syrups": [], "toppings": [], "liqueurs": [], "misc": []})
    db.async_get_active_profile = AsyncMock(return_value=None)
    # If ws_generate consults settings directly (the old behaviour) the test
    # will see "settings_default" instead of the override and fail.
    db.async_get_settings = AsyncMock(return_value={"llm_agent_id": "settings_default"})
    db.async_get_preferences = AsyncMock(return_value={})

    hass = MagicMock()
    hass.data = {"melitta_barista": {"sommelier_db": db}}
    hass.config = MagicMock()
    hass.config.language = "en"
    hass.config_entries = MagicMock()
    hass.config_entries.async_entries = MagicMock(return_value=[])
    hass.states = MagicMock()
    hass.states.async_all = MagicMock(return_value=[])
    hass.states.get = MagicMock(return_value=None)

    connection = MagicMock()
    connection.context = MagicMock(return_value=None)
    connection.send_result = MagicMock()
    connection.send_error = MagicMock()

    # async_response wraps require_admin wraps the underlying coroutine.
    # Walk __wrapped__ until we reach a coroutine function.
    ws_generate = sa.ws_generate
    while hasattr(ws_generate, "__wrapped__"):
        ws_generate = ws_generate.__wrapped__
        import inspect as _i
        if _i.iscoroutinefunction(ws_generate):
            break

    msg = {
        "id": 1,
        "type": "melitta_barista/sommelier/generate",
        "mode": "surprise_me",
        "count": 3,
        "agent_id": "override_agent",
    }

    with patch(
        "custom_components.melitta_barista.sommelier_api._async_get_db",
        new=AsyncMock(return_value=db),
    ), patch(
        "custom_components.melitta_barista.panel_api._async_get_db",
        new=AsyncMock(return_value=db),
    ), patch(
        "custom_components.melitta_barista.panel_api._structured_call",
        new=_fake_structured_call,
    ), patch(
        "custom_components.melitta_barista.panel_api._resolve_prompt",
        new=AsyncMock(return_value=None),
    ):
        await ws_generate(hass, connection, msg)

    assert captured.get("agent_id") == "override_agent", \
        f"Expected agent_id=override_agent, got {captured.get('agent_id')!r}"


def test_ws_generate_schema_accepts_agent_id():
    """Schema for /sommelier/generate accepts an optional agent_id string."""
    # HA's @websocket_api.websocket_command decorator stores the dict schema
    # on `_ws_schema`. Verify our new optional field is listed.
    schema = getattr(sa.ws_generate, "_ws_schema", None)
    assert schema is not None, "ws_generate has no _ws_schema attribute"
    # voluptuous Schema wraps the dict on `.schema`.
    schema_dict = schema.schema
    keys = [str(k) for k in schema_dict.keys()]
    assert "agent_id" in keys, f"agent_id not in schema keys: {keys}"
