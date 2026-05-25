"""P4a Task 2 — async_set_extra_available upsert for user_extras.

P4b Task 1 — async_get_pantry_extras: catalogue-first pantry reader.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from custom_components.melitta_barista import panel_api
from custom_components.melitta_barista.sommelier_db import SommelierDB


@pytest.mark.asyncio
async def test_set_extra_available_inserts_when_missing():
    """A fresh (category, item) pair is INSERTed with the right `available` bit."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()

        await db.async_set_extra_available("syrups", "Vanilla", True)

        cursor = await db.db.execute(
            "SELECT category, item, available FROM user_extras "
            "WHERE category = ? AND item = ?",
            ("syrups", "Vanilla"),
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["category"] == "syrups"
        assert row["item"] == "Vanilla"
        assert row["available"] == 1

        await db.async_close()


@pytest.mark.asyncio
async def test_set_extra_available_updates_when_present():
    """An existing row's `available` is UPDATEd in place (no duplicate row)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()

        # Seed an available=1 row.
        await db.db.execute(
            "INSERT INTO user_extras (category, item, available) VALUES (?, ?, 1)",
            ("toppings", "Cocoa"),
        )
        await db.db.commit()

        await db.async_set_extra_available("toppings", "Cocoa", False)

        cursor = await db.db.execute(
            "SELECT available FROM user_extras WHERE category = ? AND item = ?",
            ("toppings", "Cocoa"),
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["available"] == 0

        # No duplicate row sneaked in.
        cursor = await db.db.execute(
            "SELECT COUNT(*) FROM user_extras WHERE category = ? AND item = ?",
            ("toppings", "Cocoa"),
        )
        count = (await cursor.fetchone())[0]
        assert count == 1

        await db.async_close()


# ── P4b Task 1: async_get_pantry_extras ─────────────────────────────────────


async def _seed_panel_schema(db: SommelierDB) -> None:
    """Bootstrap panel-side syrups/toppings catalogue tables on the given DB."""
    await panel_api._ensure_panel_schema(db)


@pytest.mark.asyncio
async def test_pantry_extras_pulls_syrups_toppings_from_catalogue():
    """Catalogue rows with available=1 surface; available=0 rows are filtered out."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()
        await _seed_panel_schema(db)

        now = "2026-05-26T00:00:00+00:00"
        # Two syrups: one available, one not.
        await db.db.execute(
            "INSERT INTO syrups (name, brand, notes, available, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("Vanilla", None, None, 1, now),
        )
        await db.db.execute(
            "INSERT INTO syrups (name, brand, notes, available, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("Hazelnut", None, None, 0, now),
        )
        # Two toppings: one available, one not.
        await db.db.execute(
            "INSERT INTO toppings (name, brand, notes, available, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("Cocoa", None, None, 1, now),
        )
        await db.db.execute(
            "INSERT INTO toppings (name, brand, notes, available, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("Cinnamon", None, None, 0, now),
        )
        await db.db.commit()

        result = await db.async_get_pantry_extras()

        assert result["syrups"] == ["Vanilla"]
        assert result["toppings"] == ["Cocoa"]

        await db.async_close()


@pytest.mark.asyncio
async def test_pantry_extras_returns_liqueurs_and_misc_from_user_extras():
    """Liqueurs/misc come from user_extras with available=1 filter applied."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()
        await _seed_panel_schema(db)

        await db.db.execute(
            "INSERT INTO user_extras (category, item, available) VALUES (?, ?, ?)",
            ("liqueurs", "Amaretto", 1),
        )
        await db.db.execute(
            "INSERT INTO user_extras (category, item, available) VALUES (?, ?, ?)",
            ("liqueurs", "Sambuca", 0),
        )
        await db.db.execute(
            "INSERT INTO user_extras (category, item, available) VALUES (?, ?, ?)",
            ("misc", "ice", 1),
        )
        await db.db.commit()

        result = await db.async_get_pantry_extras()

        assert result["liqueurs"] == ["Amaretto"]
        assert result["misc"] == ["ice"]

        await db.async_close()


@pytest.mark.asyncio
async def test_pantry_extras_empty_catalogue_returns_empty_lists():
    """All four keys are present and equal to [] when nothing is seeded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()
        await _seed_panel_schema(db)

        result = await db.async_get_pantry_extras()

        assert result == {
            "syrups": [],
            "toppings": [],
            "liqueurs": [],
            "misc": [],
        }

        await db.async_close()


@pytest.mark.asyncio
async def test_pantry_extras_missing_catalogue_tables_returns_empty():
    """Catalogue table absence is swallowed: syrups/toppings come back as []."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SommelierDB(str(Path(tmpdir) / "test.db"))
        await db.async_setup()
        # Deliberately skip _ensure_panel_schema: the panel tables don't exist.
        # The helper should treat the OperationalError as "empty catalogue".

        result = await db.async_get_pantry_extras()

        assert result["syrups"] == []
        assert result["toppings"] == []
        # user_extras lives in the sommelier_db schema and is always present,
        # so liqueurs/misc come back as [] too (no rows seeded).
        assert result["liqueurs"] == []
        assert result["misc"] == []

        await db.async_close()
