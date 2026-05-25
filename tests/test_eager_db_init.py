"""Tests for eager sommelier_db initialization in async_setup_entry."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.melitta_barista import _make_capabilities_probe_callback


@pytest.mark.asyncio
async def test_probe_callback_factory_contract():
    """The probe-callback factory contract: callable returned, no work on disconnect."""
    db_mock = MagicMock()
    db_mock.async_save_capabilities = AsyncMock()
    client_mock = MagicMock()

    hass_mock = MagicMock()
    hass_mock.async_create_task = lambda c: None
    hass_mock.data = {"melitta_barista": {"sommelier_db": db_mock}}

    callback = _make_capabilities_probe_callback(hass_mock, db_mock, client_mock, "entry_test")
    assert callable(callback)
    callback(False)  # disconnect — no work scheduled
    db_mock.async_save_capabilities.assert_not_called()
