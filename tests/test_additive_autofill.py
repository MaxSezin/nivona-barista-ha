"""P8b R1 slice 2 — /syrups/autofill + /toppings/autofill LLM endpoints."""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.melitta_barista import panel_api as pa


def _unwrap(handler):
    """Walk ``__wrapped__`` until we reach the underlying async coroutine.

    HA's ``@websocket_api.async_response`` wraps ``@websocket_api.require_admin``
    which wraps the actual coroutine function. The agent_id_override tests use
    the same pattern (see `tests/test_agent_id_override.py`).
    """
    fn = handler
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
        if inspect.iscoroutinefunction(fn):
            break
    return fn


def _make_connection():
    """Build a MagicMock connection with the bits the handler touches."""
    connection = MagicMock()
    connection.context = MagicMock(return_value=None)
    connection.send_result = MagicMock()
    connection.send_error = MagicMock()
    return connection


def _make_hass():
    """Minimal hass mock — _resolve_agent_id reads settings via _async_get_db."""
    hass = MagicMock()
    hass.data = {"melitta_barista": {}}
    return hass


@pytest.mark.asyncio
async def test_syrups_autofill_happy_path():
    """Happy path: _structured_call output is shipped verbatim, with fmt_vars."""
    captured: dict = {}
    fake_result = {
        "raw": "{}",
        "parsed": {
            "flavor_notes": ["vanilla"],
            "composition": "sugar, water, natural vanilla",
            "attributes": {"vegan": True, "gluten_free": True},
            "variant": "",
        },
        "validation_errors": [],
        "via": "text_with_validation",
    }

    async def _fake_call(hass, slot, fmt_vars, agent_id, ctx, **kwargs):
        captured["slot"] = slot
        captured["fmt_vars"] = fmt_vars
        captured["agent_id"] = agent_id
        return fake_result

    hass = _make_hass()
    connection = _make_connection()
    msg = {
        "id": 7,
        "type": "melitta_barista/syrups/autofill",
        "brand": "Monin",
    }

    db = MagicMock()
    db.async_get_settings = AsyncMock(return_value={})
    with patch(
        "custom_components.melitta_barista.panel_api._structured_call",
        new=_fake_call,
    ), patch(
        "custom_components.melitta_barista.panel_api._async_get_db",
        new=AsyncMock(return_value=db),
    ):
        await _unwrap(pa._ws_syrups_autofill)(hass, connection, msg)

    # Slot routing
    assert captured["slot"] == "syrups_autofill"
    # fmt_vars carries the expected keys
    assert captured["fmt_vars"]["brand"] == "Monin"
    assert "variant_hint" in captured["fmt_vars"]
    assert "website_hint" in captured["fmt_vars"]
    # Without variant / website the hints are empty fragments.
    assert captured["fmt_vars"]["variant_hint"] == ""
    assert captured["fmt_vars"]["website_hint"] == ""

    # The structured-call payload is shipped verbatim through _send_versioned
    connection.send_result.assert_called_once()
    sent_id, sent_payload = connection.send_result.call_args[0]
    assert sent_id == 7
    # _send_versioned wraps with schema_version + payload keys
    assert sent_payload["schema_version"] == 1
    for key, value in fake_result.items():
        assert sent_payload[key] == value
    connection.send_error.assert_not_called()


@pytest.mark.asyncio
async def test_toppings_autofill_happy_path():
    """Same shape as syrups, but routed through ``toppings_autofill``."""
    captured: dict = {}

    async def _fake_call(hass, slot, fmt_vars, agent_id, ctx, **kwargs):
        captured["slot"] = slot
        captured["fmt_vars"] = fmt_vars
        return {
            "raw": "{}",
            "parsed": {
                "flavor_notes": ["cocoa"],
                "composition": "cocoa powder",
                "attributes": {"vegan": True},
                "variant": "",
            },
            "validation_errors": [],
            "via": "text_with_validation",
        }

    hass = _make_hass()
    connection = _make_connection()
    msg = {
        "id": 11,
        "type": "melitta_barista/toppings/autofill",
        "brand": "Cacao Barry",
    }

    db = MagicMock()
    db.async_get_settings = AsyncMock(return_value={})
    with patch(
        "custom_components.melitta_barista.panel_api._structured_call",
        new=_fake_call,
    ), patch(
        "custom_components.melitta_barista.panel_api._async_get_db",
        new=AsyncMock(return_value=db),
    ):
        await _unwrap(pa._ws_toppings_autofill)(hass, connection, msg)

    assert captured["slot"] == "toppings_autofill"
    assert captured["fmt_vars"]["brand"] == "Cacao Barry"
    connection.send_result.assert_called_once()
    connection.send_error.assert_not_called()


@pytest.mark.asyncio
async def test_syrups_autofill_conversation_error():
    """When _structured_call raises, the handler emits ``conversation_error``."""

    async def _boom(*args, **kwargs):
        raise RuntimeError("LLM exploded")

    hass = _make_hass()
    connection = _make_connection()
    msg = {
        "id": 13,
        "type": "melitta_barista/syrups/autofill",
        "brand": "Monin",
    }

    db = MagicMock()
    db.async_get_settings = AsyncMock(return_value={})
    with patch(
        "custom_components.melitta_barista.panel_api._structured_call",
        new=_boom,
    ), patch(
        "custom_components.melitta_barista.panel_api._async_get_db",
        new=AsyncMock(return_value=db),
    ):
        await _unwrap(pa._ws_syrups_autofill)(hass, connection, msg)

    connection.send_error.assert_called_once()
    err_args = connection.send_error.call_args[0]
    assert err_args[0] == 13
    assert err_args[1] == "conversation_error"
    # send_result must NOT be called when the call failed
    connection.send_result.assert_not_called()


@pytest.mark.asyncio
async def test_syrups_autofill_includes_variant_in_fmt_vars():
    """When ``variant`` is passed, it reaches the LLM via ``variant_hint``."""
    captured: dict = {}

    async def _fake_call(hass, slot, fmt_vars, agent_id, ctx, **kwargs):
        captured["fmt_vars"] = fmt_vars
        return {
            "raw": "{}",
            "parsed": {
                "flavor_notes": ["vanilla"],
                "composition": "",
                "attributes": {},
                "variant": "Sugar-free",
            },
            "validation_errors": [],
            "via": "text_with_validation",
        }

    hass = _make_hass()
    connection = _make_connection()
    msg = {
        "id": 17,
        "type": "melitta_barista/syrups/autofill",
        "brand": "Monin",
        "variant": "Sugar-free",
    }

    db = MagicMock()
    db.async_get_settings = AsyncMock(return_value={})
    with patch(
        "custom_components.melitta_barista.panel_api._structured_call",
        new=_fake_call,
    ), patch(
        "custom_components.melitta_barista.panel_api._async_get_db",
        new=AsyncMock(return_value=db),
    ):
        await _unwrap(pa._ws_syrups_autofill)(hass, connection, msg)

    fmt_vars = captured["fmt_vars"]
    assert fmt_vars["brand"] == "Monin"
    # The raw variant value is passed through too — some prompts may use it
    # directly instead of the variant_hint fragment.
    assert fmt_vars["variant"] == "Sugar-free"
    # The auto-built fragment mentions the variant value.
    assert "Sugar-free" in fmt_vars["variant_hint"]


def test_syrups_autofill_requires_admin():
    """The handler must enforce admin: calling without an admin user raises.

    HA's ``@websocket_api.require_admin`` doesn't tag the wrapper with a
    sentinel attribute (it uses ``@functools.wraps`` to preserve the inner
    function's name and qualname). We probe behaviour instead: walk
    ``__wrapped__`` until we find the admin-check layer (HA's wrapper
    expects ``connection.user.is_admin``) and confirm it raises
    ``Unauthorized`` for a non-admin user. The outer ``async_response``
    decorator hands work off to the executor, so we drive the admin check
    one layer in.
    """
    from homeassistant.exceptions import Unauthorized

    handler = pa._ws_syrups_autofill
    # The decorator chain must have wrapped the bare coroutine at least once.
    assert hasattr(handler, "__wrapped__"), \
        "handler is not wrapped — @async_response/@require_admin missing"

    # Walk the chain — the inner-most __wrapped__ should be the coroutine
    # function (require_admin's ``with_admin`` wrapper is sync; @wraps keeps
    # the inner __name__, so we can't rely on a name check).
    fn = handler
    layers = [fn]
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
        layers.append(fn)
    # Final unwrapped function should be an async coroutine.
    assert inspect.iscoroutinefunction(fn), \
        f"unwrapped handler is not a coroutine ({fn!r})"

    # The require_admin layer is the sync wrapper above the async coroutine.
    # Pick the layer that is NOT a coroutine — that's the admin gate.
    admin_layer = next(
        (layer for layer in layers if not inspect.iscoroutinefunction(layer)),
        None,
    )
    assert admin_layer is not None, "no sync admin layer in wrapper chain"

    # Drive the admin layer with a non-admin user — it must raise Unauthorized.
    hass = _make_hass()
    connection = MagicMock()
    connection.user = MagicMock()
    connection.user.is_admin = False
    msg = {"id": 1, "type": "melitta_barista/syrups/autofill", "brand": "x"}

    with pytest.raises(Unauthorized):
        admin_layer(hass, connection, msg)
