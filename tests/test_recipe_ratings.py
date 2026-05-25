"""P3a — recipe_ratings table + async_{set,clear,get}_rating."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from custom_components.melitta_barista.sommelier_db import (
    SCHEMA_VERSION,
    SommelierDB,
)


@pytest.mark.asyncio
async def test_schema_version_is_6():
    """SCHEMA_VERSION bumped to 6."""
    assert SCHEMA_VERSION == 6


@pytest.mark.asyncio
async def test_set_and_get_rating_generated():
    """Setting a rating for a generated recipe and reading it back."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()

        await db.async_set_rating("rec_1", "generated", 4, "Solid morning brew.")
        result = await db.async_get_rating("rec_1", "generated")
        assert result is not None
        assert result["rating"] == 4
        assert result["note"] == "Solid morning brew."
        assert result["target_type"] == "generated"
        assert isinstance(result["created_at"], str) and len(result["created_at"]) > 0

        await db.async_close()


@pytest.mark.asyncio
async def test_set_rating_upserts():
    """Second set replaces the first (same target_id+target_type)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()

        await db.async_set_rating("rec_1", "generated", 3, None)
        await db.async_set_rating("rec_1", "generated", 5, "Loved it.")
        result = await db.async_get_rating("rec_1", "generated")
        assert result["rating"] == 5
        assert result["note"] == "Loved it."

        await db.async_close()


@pytest.mark.asyncio
async def test_get_rating_returns_none_when_absent():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()

        result = await db.async_get_rating("never_rated", "generated")
        assert result is None

        await db.async_close()


@pytest.mark.asyncio
async def test_clear_rating():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()

        await db.async_set_rating("rec_1", "generated", 4, "note")
        await db.async_clear_rating("rec_1", "generated")
        assert await db.async_get_rating("rec_1", "generated") is None

        await db.async_close()


@pytest.mark.asyncio
async def test_rating_distinct_per_target_type():
    """Same target_id can have separate ratings for generated vs favorite."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()

        await db.async_set_rating("uuid_1", "generated", 3, "First impression")
        await db.async_set_rating("uuid_1", "favorite", 5, "After saving")

        gen = await db.async_get_rating("uuid_1", "generated")
        fav = await db.async_get_rating("uuid_1", "favorite")
        assert gen["rating"] == 3
        assert fav["rating"] == 5

        await db.async_close()


@pytest.mark.asyncio
async def test_rating_validates_range():
    """rating must be in 1..5; outside range raises."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()

        with pytest.raises(ValueError):
            await db.async_set_rating("rec_1", "generated", 0, None)
        with pytest.raises(ValueError):
            await db.async_set_rating("rec_1", "generated", 6, None)

        await db.async_close()


@pytest.mark.asyncio
async def test_rating_validates_target_type():
    """target_type must be 'generated' or 'favorite'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()

        with pytest.raises(ValueError):
            await db.async_set_rating("rec_1", "session", 4, None)

        await db.async_close()


@pytest.mark.asyncio
async def test_migration_from_v5_adds_recipe_ratings():
    """Existing v5 DB upgraded to v6 gains the recipe_ratings table without dropping data."""
    import aiosqlite

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")

        async with aiosqlite.connect(db_path) as conn:
            await conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
            await conn.execute("INSERT INTO settings(key, value) VALUES('schema_version', '5')")
            await conn.execute(
                "CREATE TABLE coffee_beans (id TEXT PRIMARY KEY, brand TEXT, product TEXT)"
            )
            await conn.execute(
                "INSERT INTO coffee_beans(id, brand, product) VALUES('b1', 'Lavazza', 'Crema')"
            )
            await conn.commit()

        db = SommelierDB(db_path)
        await db.async_setup()

        async with aiosqlite.connect(db_path) as conn:
            cur = await conn.execute("SELECT value FROM settings WHERE key='schema_version'")
            row = await cur.fetchone()
            assert row[0] == "6"

        await db.async_set_rating("b1", "generated", 4, None)
        assert (await db.async_get_rating("b1", "generated"))["rating"] == 4

        await db.async_close()
