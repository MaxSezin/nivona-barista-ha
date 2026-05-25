"""P3a — favorites/update endpoint and DB layer."""

from __future__ import annotations

import inspect
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.melitta_barista.sommelier_db import SommelierDB


def _sample_recipe(**overrides):
    base = {
        "name": "Original",
        "description": "Desc",
        "blend": 1,
        "machine_phases": [
            {
                "component": {"process": "coffee", "portion_ml": 40},
                "user_action_before": [],
            }
        ],
        "extras": None,
        "steps": [{"order": 1, "action": "brew", "phase": "during"}],
        "cup_type": "espresso_cup",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_update_favorite_renames():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()

        added = await db.async_add_favorite(_sample_recipe(name="Original"))
        fav_id = added["id"]
        ok = await db.async_update_favorite(fav_id, name="Renamed")
        assert ok is True

        fav = await db.async_get_favorite(fav_id)
        assert fav["name"] == "Renamed"
        assert fav["description"] == "Desc"
        assert fav["cup_type"] == "espresso_cup"

        await db.async_close()


@pytest.mark.asyncio
async def test_update_favorite_patches_description():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()

        added = await db.async_add_favorite(_sample_recipe(description="Old"))
        fav_id = added["id"]
        ok = await db.async_update_favorite(fav_id, description="New description")
        assert ok is True

        fav = await db.async_get_favorite(fav_id)
        assert fav["description"] == "New description"
        assert fav["name"] == "Original"

        await db.async_close()


@pytest.mark.asyncio
async def test_update_favorite_rejects_unknown_field():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()

        added = await db.async_add_favorite(_sample_recipe())
        fav_id = added["id"]
        with pytest.raises(ValueError):
            await db.async_update_favorite(fav_id, evil="injected")

        await db.async_close()


@pytest.mark.asyncio
async def test_update_favorite_returns_false_if_not_found():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()

        result = await db.async_update_favorite("nonexistent", name="X")
        assert result is False

        await db.async_close()


@pytest.mark.asyncio
async def test_update_favorite_note_requires_existing_rating():
    """Setting a note without a prior rating raises (note lives on rating row)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()

        added = await db.async_add_favorite(_sample_recipe())
        fav_id = added["id"]
        # No rating yet — note alone should fail.
        with pytest.raises(ValueError):
            await db.async_update_favorite(fav_id, note="standalone note")

        # After a rating exists, note can be set.
        await db.async_set_rating(fav_id, "favorite", 4, None)
        ok = await db.async_update_favorite(fav_id, note="now with rating")
        assert ok is True

        rating = await db.async_get_rating(fav_id, "favorite")
        assert rating["note"] == "now with rating"
        assert rating["rating"] == 4  # preserved

        await db.async_close()


@pytest.mark.asyncio
async def test_ws_favorites_update_calls_db():
    from custom_components.melitta_barista import sommelier_api as sa

    db = MagicMock()
    db.async_update_favorite = AsyncMock(return_value=True)
    hass = MagicMock()
    hass.data = {"melitta_barista": {"sommelier_db": db}}

    connection = MagicMock()
    connection.send_result = MagicMock()
    connection.send_error = MagicMock()

    ws_favorites_update = inspect.unwrap(sa.ws_favorites_update)

    msg = {
        "id": 1,
        "type": "melitta_barista/sommelier/favorites/update",
        "favorite_id": "fav_42",
        "name": "Renamed",
        "description": "New desc",
    }
    await ws_favorites_update(hass, connection, msg)

    db.async_update_favorite.assert_awaited_once()
    call_args = db.async_update_favorite.call_args
    assert call_args.args[0] == "fav_42"
    assert call_args.kwargs.get("name") == "Renamed"
    assert call_args.kwargs.get("description") == "New desc"
    connection.send_result.assert_called_once()
    connection.send_error.assert_not_called()
