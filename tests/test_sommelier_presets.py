"""P5a Tasks 1 & 2 — sommelier_presets DB methods + WS handlers."""

from __future__ import annotations

import inspect
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import voluptuous as vol

from custom_components.melitta_barista.sommelier_db import (
    SCHEMA_VERSION,
    SommelierDB,
)


@pytest.mark.asyncio
async def test_schema_version_is_7():
    """SCHEMA_VERSION bumped to 7."""
    assert SCHEMA_VERSION == 7


@pytest.mark.asyncio
async def test_add_preset_returns_id_and_persists():
    """Adding a preset returns its id and the row appears in list_presets."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()

        payload = {"mode": "surprise_me", "servings": 2, "mood": "cozy"}
        preset_id = await db.async_add_preset("Morning routine", "Daily go-to", payload)
        assert isinstance(preset_id, str) and len(preset_id) > 0

        presets = await db.async_list_presets()
        assert len(presets) == 1
        row = presets[0]
        assert row["id"] == preset_id
        assert row["name"] == "Morning routine"
        assert row["description"] == "Daily go-to"
        assert row["payload"] == payload
        assert isinstance(row["created_at"], str) and len(row["created_at"]) > 0
        assert row["updated_at"] is None

        await db.async_close()


@pytest.mark.asyncio
async def test_list_presets_orders_by_name_case_insensitive():
    """LOWER(name) ordering: Apple, morning, Zebra regardless of case."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()

        await db.async_add_preset("Zebra", None, {"a": 1})
        await db.async_add_preset("Apple", None, {"a": 2})
        await db.async_add_preset("morning", None, {"a": 3})

        presets = await db.async_list_presets()
        names = [p["name"] for p in presets]
        assert names == ["Apple", "morning", "Zebra"]

        await db.async_close()


@pytest.mark.asyncio
async def test_update_preset_patches_fields_and_sets_updated_at():
    """Partial patch updates only the supplied column and bumps updated_at."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()

        preset_id = await db.async_add_preset("Evening", "Original", {"x": 1})
        ok = await db.async_update_preset(preset_id, description="Updated text")
        assert ok is True

        presets = await db.async_list_presets()
        assert len(presets) == 1
        row = presets[0]
        assert row["name"] == "Evening"
        assert row["description"] == "Updated text"
        assert row["payload"] == {"x": 1}
        assert row["updated_at"] is not None
        assert isinstance(row["updated_at"], str) and len(row["updated_at"]) > 0

        await db.async_close()


@pytest.mark.asyncio
async def test_update_preset_raises_when_no_fields():
    """Empty patch raises ValueError('no_fields')."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()

        preset_id = await db.async_add_preset("Anything", None, {"y": 2})
        with pytest.raises(ValueError) as exc_info:
            await db.async_update_preset(preset_id)
        assert exc_info.value.args[0] == "no_fields"

        await db.async_close()


@pytest.mark.asyncio
async def test_update_preset_unknown_id_returns_false():
    """Patching a non-existent id returns False, does not raise."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()

        ok = await db.async_update_preset("nonexistent-id", name="Whatever")
        assert ok is False

        await db.async_close()


@pytest.mark.asyncio
async def test_delete_preset_removes_row():
    """Delete returns True and the preset disappears from the listing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()

        preset_id = await db.async_add_preset("Doomed", None, {"z": 3})
        assert len(await db.async_list_presets()) == 1

        removed = await db.async_delete_preset(preset_id)
        assert removed is True
        assert await db.async_list_presets() == []

        await db.async_close()


@pytest.mark.asyncio
async def test_delete_preset_unknown_id_returns_false():
    """Deleting a non-existent id returns False, no exception."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()

        removed = await db.async_delete_preset("nonexistent-id")
        assert removed is False

        await db.async_close()


@pytest.mark.asyncio
async def test_migration_v6_to_v7_idempotent():
    """Re-opening the DB after v6→v7 leaves the table intact and usable."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")

        db = SommelierDB(db_path)
        await db.async_setup()
        preset_id = await db.async_add_preset("Persistent", None, {"k": "v"})
        await db.async_close()

        db = SommelierDB(db_path)
        await db.async_setup()
        presets = await db.async_list_presets()
        assert len(presets) == 1
        assert presets[0]["id"] == preset_id
        assert presets[0]["payload"] == {"k": "v"}

        await db.async_close()


# ── WS handlers (P5a Task 2) ──────────────────────────────────────────


async def _make_hass_with_db(db: SommelierDB) -> MagicMock:
    """Build a MagicMock hass exposing the DB at hass.data[DOMAIN]['sommelier_db']."""
    hass = MagicMock()
    hass.data = {"melitta_barista": {"sommelier_db": db}}
    return hass


def _make_connection() -> MagicMock:
    """Build a MagicMock connection with send_result / send_error stubs."""
    connection = MagicMock()
    connection.send_result = MagicMock()
    connection.send_error = MagicMock()
    return connection


@pytest.mark.asyncio
async def test_ws_presets_list_returns_db_rows():
    """ws_presets_list returns rows from async_list_presets with dict payload."""
    from custom_components.melitta_barista import sommelier_api as sa

    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()
        await db.async_add_preset("Solo", "Single row", {"mode": "surprise_me"})

        hass = await _make_hass_with_db(db)
        connection = _make_connection()
        msg = {"id": 1, "type": "melitta_barista/sommelier/presets/list"}

        handler = inspect.unwrap(sa.ws_presets_list)
        await handler(hass, connection, msg)

        connection.send_result.assert_called_once()
        args, _ = connection.send_result.call_args
        assert args[0] == 1
        result = args[1]
        assert "presets" in result
        assert len(result["presets"]) == 1
        row = result["presets"][0]
        assert row["name"] == "Solo"
        assert row["description"] == "Single row"
        assert row["payload"] == {"mode": "surprise_me"}
        connection.send_error.assert_not_called()

        await db.async_close()


@pytest.mark.asyncio
async def test_ws_presets_add_persists_and_returns_id():
    """ws_presets_add returns an id and the row is persisted."""
    from custom_components.melitta_barista import sommelier_api as sa

    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()

        hass = await _make_hass_with_db(db)
        connection = _make_connection()
        msg = {
            "id": 7,
            "type": "melitta_barista/sommelier/presets/add",
            "name": "Morning",
            "description": "Light wake-up",
            "payload": {"mode": "surprise_me"},
        }

        handler = inspect.unwrap(sa.ws_presets_add)
        await handler(hass, connection, msg)

        connection.send_result.assert_called_once()
        args, _ = connection.send_result.call_args
        assert args[0] == 7
        result = args[1]
        assert isinstance(result["id"], str) and len(result["id"]) > 0
        connection.send_error.assert_not_called()

        presets = await db.async_list_presets()
        assert len(presets) == 1
        assert presets[0]["name"] == "Morning"
        assert presets[0]["description"] == "Light wake-up"
        assert presets[0]["payload"] == {"mode": "surprise_me"}

        await db.async_close()


def test_ws_presets_add_validates_empty_name():
    """ws_presets_add schema rejects an empty name via voluptuous Length(min=1)."""
    from custom_components.melitta_barista import sommelier_api as sa

    schema = sa.ws_presets_add._ws_schema
    msg = {
        "id": 1,
        "type": "melitta_barista/sommelier/presets/add",
        "name": "",
        "payload": {"mode": "surprise_me"},
    }
    with pytest.raises(vol.Invalid):
        schema(msg)


@pytest.mark.asyncio
async def test_ws_presets_update_patches_description_only():
    """ws_presets_update with only description patches that field and leaves name."""
    from custom_components.melitta_barista import sommelier_api as sa

    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()
        preset_id = await db.async_add_preset("Original", "Old desc", {"k": 1})

        hass = await _make_hass_with_db(db)
        connection = _make_connection()
        msg = {
            "id": 2,
            "type": "melitta_barista/sommelier/presets/update",
            "preset_id": preset_id,
            "description": "new",
        }

        handler = inspect.unwrap(sa.ws_presets_update)
        await handler(hass, connection, msg)

        connection.send_result.assert_called_once_with(2, {"updated": True})
        connection.send_error.assert_not_called()

        presets = await db.async_list_presets()
        assert len(presets) == 1
        assert presets[0]["name"] == "Original"
        assert presets[0]["description"] == "new"
        assert presets[0]["payload"] == {"k": 1}

        await db.async_close()


@pytest.mark.asyncio
async def test_ws_presets_update_empty_payload_returns_no_fields():
    """ws_presets_update with only preset_id surfaces 'no_fields' from DB layer."""
    from custom_components.melitta_barista import sommelier_api as sa

    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()
        preset_id = await db.async_add_preset("Stay", None, {"k": 1})

        hass = await _make_hass_with_db(db)
        connection = _make_connection()
        msg = {
            "id": 3,
            "type": "melitta_barista/sommelier/presets/update",
            "preset_id": preset_id,
        }

        handler = inspect.unwrap(sa.ws_presets_update)
        await handler(hass, connection, msg)

        connection.send_error.assert_called_once()
        args, _ = connection.send_error.call_args
        assert args[0] == 3
        assert args[1] == "no_fields"
        connection.send_result.assert_not_called()

        await db.async_close()


@pytest.mark.asyncio
async def test_ws_presets_update_unknown_id_returns_not_found():
    """ws_presets_update on a missing preset_id surfaces 'not_found'."""
    from custom_components.melitta_barista import sommelier_api as sa

    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()

        hass = await _make_hass_with_db(db)
        connection = _make_connection()
        msg = {
            "id": 4,
            "type": "melitta_barista/sommelier/presets/update",
            "preset_id": "no-such-id",
            "name": "Whatever",
        }

        handler = inspect.unwrap(sa.ws_presets_update)
        await handler(hass, connection, msg)

        connection.send_error.assert_called_once()
        args, _ = connection.send_error.call_args
        assert args[0] == 4
        assert args[1] == "not_found"
        connection.send_result.assert_not_called()

        await db.async_close()


@pytest.mark.asyncio
async def test_ws_presets_delete_removes():
    """ws_presets_delete drops the row and returns {'deleted': True}."""
    from custom_components.melitta_barista import sommelier_api as sa

    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()
        preset_id = await db.async_add_preset("Doomed", None, {"k": 1})

        hass = await _make_hass_with_db(db)
        connection = _make_connection()
        msg = {
            "id": 5,
            "type": "melitta_barista/sommelier/presets/delete",
            "preset_id": preset_id,
        }

        handler = inspect.unwrap(sa.ws_presets_delete)
        await handler(hass, connection, msg)

        connection.send_result.assert_called_once_with(5, {"deleted": True})
        connection.send_error.assert_not_called()
        assert await db.async_list_presets() == []

        await db.async_close()


@pytest.mark.asyncio
async def test_ws_presets_delete_unknown_id_returns_not_found():
    """ws_presets_delete on a missing preset_id surfaces 'not_found'."""
    from custom_components.melitta_barista import sommelier_api as sa

    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()

        hass = await _make_hass_with_db(db)
        connection = _make_connection()
        msg = {
            "id": 6,
            "type": "melitta_barista/sommelier/presets/delete",
            "preset_id": "no-such-id",
        }

        handler = inspect.unwrap(sa.ws_presets_delete)
        await handler(hass, connection, msg)

        connection.send_error.assert_called_once()
        args, _ = connection.send_error.call_args
        assert args[0] == 6
        assert args[1] == "not_found"
        connection.send_result.assert_not_called()

        await db.async_close()
