"""P3a — WS handlers for recipe rating."""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.melitta_barista import sommelier_api as sa


@pytest.mark.asyncio
async def test_ws_recipe_rate_calls_db_set_rating():
    db = MagicMock()
    db.async_set_rating = AsyncMock()
    hass = MagicMock()
    hass.data = {"melitta_barista": {"sommelier_db": db}}

    connection = MagicMock()
    connection.send_result = MagicMock()
    connection.send_error = MagicMock()

    ws_recipe_rate = inspect.unwrap(sa.ws_recipe_rate)

    msg = {
        "id": 1,
        "type": "melitta_barista/sommelier/recipe/rate",
        "target_id": "rec_42",
        "target_type": "generated",
        "rating": 4,
        "note": "Solid",
    }
    await ws_recipe_rate(hass, connection, msg)

    db.async_set_rating.assert_awaited_once_with("rec_42", "generated", 4, "Solid")
    connection.send_result.assert_called_once()
    connection.send_error.assert_not_called()


@pytest.mark.asyncio
async def test_ws_recipe_rate_handles_none_note():
    db = MagicMock()
    db.async_set_rating = AsyncMock()
    hass = MagicMock()
    hass.data = {"melitta_barista": {"sommelier_db": db}}

    connection = MagicMock()
    connection.send_result = MagicMock()

    ws_recipe_rate = inspect.unwrap(sa.ws_recipe_rate)

    msg = {
        "id": 1,
        "type": "melitta_barista/sommelier/recipe/rate",
        "target_id": "rec_x",
        "target_type": "favorite",
        "rating": 5,
    }
    await ws_recipe_rate(hass, connection, msg)
    db.async_set_rating.assert_awaited_once_with("rec_x", "favorite", 5, None)


@pytest.mark.asyncio
async def test_ws_recipe_unrate_calls_db_clear_rating():
    db = MagicMock()
    db.async_clear_rating = AsyncMock()
    hass = MagicMock()
    hass.data = {"melitta_barista": {"sommelier_db": db}}

    connection = MagicMock()
    connection.send_result = MagicMock()

    ws_recipe_unrate = inspect.unwrap(sa.ws_recipe_unrate)

    msg = {
        "id": 2,
        "type": "melitta_barista/sommelier/recipe/unrate",
        "target_id": "rec_99",
        "target_type": "generated",
    }
    await ws_recipe_unrate(hass, connection, msg)
    db.async_clear_rating.assert_awaited_once_with("rec_99", "generated")
    connection.send_result.assert_called_once()


@pytest.mark.asyncio
async def test_ws_recipe_rate_validation_error_via_db():
    db = MagicMock()
    db.async_set_rating = AsyncMock(side_effect=ValueError("rating out of range"))
    hass = MagicMock()
    hass.data = {"melitta_barista": {"sommelier_db": db}}

    connection = MagicMock()
    connection.send_result = MagicMock()
    connection.send_error = MagicMock()

    ws_recipe_rate = inspect.unwrap(sa.ws_recipe_rate)

    msg = {
        "id": 3,
        "type": "melitta_barista/sommelier/recipe/rate",
        "target_id": "rec_0",
        "target_type": "generated",
        "rating": 3,  # valid range; DB mock raises regardless
        "note": None,
    }
    await ws_recipe_rate(hass, connection, msg)
    connection.send_error.assert_called_once()
    connection.send_result.assert_not_called()
