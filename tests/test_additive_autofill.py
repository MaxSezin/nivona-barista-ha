"""P8b R1 slice 2 — /syrups/autofill + /toppings/autofill LLM endpoints.

P12-B: input shape switched from a free-text ``brand`` to ``(name,
producer_id)``; the handler now resolves the producer name + fallback
website from the ``producers`` table before invoking the LLM.
"""

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


def _make_db_with_producer(name: str = "Monin", website: str = "") -> MagicMock:
    """Build a ``_async_get_db`` stub whose producer SELECT returns ``(name, website)``.

    Mirrors the ``aiosqlite`` chain the handler uses: ``db._db.execute(...)``
    returns a cursor whose ``fetchone`` resolves to a single row. The cursor
    object is returned synchronously from ``execute`` (HA's executor wraps
    the call but ``aiosqlite`` cursors themselves are not awaited).
    """
    cursor = MagicMock()
    cursor.fetchone = AsyncMock(return_value=(name, website))
    db = MagicMock()
    db._db = MagicMock()
    db._db.execute = AsyncMock(return_value=cursor)
    db.async_get_settings = AsyncMock(return_value={})
    return db


def _make_db_without_producer() -> MagicMock:
    """Same shape as `_make_db_with_producer` but ``fetchone`` resolves to ``None``."""
    cursor = MagicMock()
    cursor.fetchone = AsyncMock(return_value=None)
    db = MagicMock()
    db._db = MagicMock()
    db._db.execute = AsyncMock(return_value=cursor)
    db.async_get_settings = AsyncMock(return_value={})
    return db


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
        "name": "Vanilla",
        "producer_id": 1,
    }

    db = _make_db_with_producer(name="Monin")
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
    assert captured["fmt_vars"]["name"] == "Vanilla"
    assert captured["fmt_vars"]["producer"] == "Monin"
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
        "name": "Cocoa",
        "producer_id": 2,
    }

    db = _make_db_with_producer(name="Cacao Barry")
    with patch(
        "custom_components.melitta_barista.panel_api._structured_call",
        new=_fake_call,
    ), patch(
        "custom_components.melitta_barista.panel_api._async_get_db",
        new=AsyncMock(return_value=db),
    ):
        await _unwrap(pa._ws_toppings_autofill)(hass, connection, msg)

    assert captured["slot"] == "toppings_autofill"
    assert captured["fmt_vars"]["name"] == "Cocoa"
    assert captured["fmt_vars"]["producer"] == "Cacao Barry"
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
        "name": "Vanilla",
        "producer_id": 1,
    }

    db = _make_db_with_producer(name="Monin")
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
        "name": "Vanilla",
        "producer_id": 1,
        "variant": "Sugar-free",
    }

    db = _make_db_with_producer(name="Monin")
    with patch(
        "custom_components.melitta_barista.panel_api._structured_call",
        new=_fake_call,
    ), patch(
        "custom_components.melitta_barista.panel_api._async_get_db",
        new=AsyncMock(return_value=db),
    ):
        await _unwrap(pa._ws_syrups_autofill)(hass, connection, msg)

    fmt_vars = captured["fmt_vars"]
    assert fmt_vars["name"] == "Vanilla"
    assert fmt_vars["producer"] == "Monin"
    # The raw variant value is passed through too — some prompts may use it
    # directly instead of the variant_hint fragment.
    assert fmt_vars["variant"] == "Sugar-free"
    # The auto-built fragment mentions the variant value.
    assert "Sugar-free" in fmt_vars["variant_hint"]


@pytest.mark.asyncio
async def test_autofill_unknown_producer_id_returns_send_error():
    """When the producer lookup returns no row, the handler emits ``producer_not_found``.

    Guards against silently calling the LLM with a phantom producer name —
    the modal's dropdown should always carry an existing id, but a stale
    UI state or a manual WS call should be rejected.
    """
    hass = _make_hass()
    connection = _make_connection()
    msg = {
        "id": 23,
        "type": "melitta_barista/syrups/autofill",
        "name": "Vanilla",
        "producer_id": 9999,
    }

    db = _make_db_without_producer()
    structured_called = False

    async def _should_not_be_called(*args, **kwargs):
        nonlocal structured_called
        structured_called = True
        return {"raw": "", "parsed": None, "validation_errors": [], "via": "noop"}

    with patch(
        "custom_components.melitta_barista.panel_api._structured_call",
        new=_should_not_be_called,
    ), patch(
        "custom_components.melitta_barista.panel_api._async_get_db",
        new=AsyncMock(return_value=db),
    ):
        await _unwrap(pa._ws_syrups_autofill)(hass, connection, msg)

    assert structured_called is False, "LLM must not be called for unknown producer"
    connection.send_error.assert_called_once()
    err_args = connection.send_error.call_args[0]
    assert err_args[0] == 23
    assert err_args[1] == "producer_not_found"
    connection.send_result.assert_not_called()


@pytest.mark.asyncio
async def test_autofill_uses_producer_website_when_msg_has_none():
    """When the WS payload omits ``website``, fall back to the producer row's URL."""
    captured: dict = {}

    async def _fake_call(hass, slot, fmt_vars, agent_id, ctx, **kwargs):
        captured["fmt_vars"] = fmt_vars
        return {
            "raw": "{}",
            "parsed": {
                "flavor_notes": ["vanilla"],
                "composition": "",
                "attributes": {},
                "variant": "",
            },
            "validation_errors": [],
            "via": "text_with_validation",
        }

    hass = _make_hass()
    connection = _make_connection()
    msg = {
        "id": 29,
        "type": "melitta_barista/syrups/autofill",
        "name": "Vanilla",
        "producer_id": 1,
    }

    db = _make_db_with_producer(name="Monin", website="https://monin.com/")
    with patch(
        "custom_components.melitta_barista.panel_api._structured_call",
        new=_fake_call,
    ), patch(
        "custom_components.melitta_barista.panel_api._async_get_db",
        new=AsyncMock(return_value=db),
    ):
        await _unwrap(pa._ws_syrups_autofill)(hass, connection, msg)

    fmt_vars = captured["fmt_vars"]
    # The fallback URL ends up inside website_hint, which is otherwise empty.
    assert "https://monin.com/" in fmt_vars["website_hint"]


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
    msg = {
        "id": 1,
        "type": "melitta_barista/syrups/autofill",
        "name": "x",
        "producer_id": 1,
    }

    with pytest.raises(Unauthorized):
        admin_layer(hass, connection, msg)
