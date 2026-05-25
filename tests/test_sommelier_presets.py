"""P5a Task 1 — sommelier_presets table + async_{list,add,update,delete}_preset."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

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
