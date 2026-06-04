"""Time platform — machine wall-clock (read setting 20, write setting 21)."""

from __future__ import annotations

import logging
from datetime import time as dt_time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coffee_platform.contract import CoffeeMachineClient
from .entity import MelittaDeviceMixin

PARALLEL_UPDATES = 0  # BLE: single connection, serialize via locks

_LOGGER = logging.getLogger("melitta_barista")

# Protocol setting IDs — verified against the OEM protocol.
# 20 = read current machine clock (minutes since midnight)
# 21 = write/set machine clock (same encoding)
_CLOCK_READ_ID = 20
_CLOCK_WRITE_ID = 21


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the clock time entity for the configured machine."""
    client: CoffeeMachineClient = entry.runtime_data
    name = entry.data.get(CONF_NAME) or f"{client.brand.brand_name} Coffee Machine"
    async_add_entities([MelittaClockEntity(client, entry, name)])


class MelittaClockEntity(MelittaDeviceMixin, TimeEntity):
    """Machine wall-clock as an HA time entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:clock-outline"
    _attr_translation_key = "clock"

    def __init__(
        self,
        client: CoffeeMachineClient,
        entry: ConfigEntry,
        machine_name: str,
    ) -> None:
        self._client = client
        self._entry = entry
        self._machine_name = machine_name
        self._attr_native_value: dt_time | None = None

    @property
    def unique_id(self) -> str:
        return f"{self._client.address}_clock"

    @property
    def available(self) -> bool:
        return self._client.connected

    async def async_added_to_hass(self) -> None:
        self._client.add_connection_callback(self._on_connection_change)

    async def async_will_remove_from_hass(self) -> None:
        self._client.remove_connection_callback(self._on_connection_change)

    @callback
    def _on_connection_change(self, connected: bool) -> None:
        if connected:
            self.hass.async_create_task(self._async_read_value())
        self.async_write_ha_state()

    async def _async_read_value(self) -> None:
        """Read machine clock once on connect."""
        try:
            value = await self._client.read_setting(_CLOCK_READ_ID)
        except Exception:
            _LOGGER.debug("Failed to read machine clock", exc_info=True)
            return
        if value is None:
            return
        minutes = int(value) % 1440
        self._attr_native_value = dt_time(hour=minutes // 60, minute=minutes % 60)
        self.async_write_ha_state()

    async def async_set_value(self, value: dt_time) -> None:
        """Write the picked time to the machine RTC (setting 21)."""
        minutes = value.hour * 60 + value.minute
        ok = await self._client.write_setting(_CLOCK_WRITE_ID, minutes)
        if ok:
            self._attr_native_value = dt_time(hour=value.hour, minute=value.minute)
            self.async_write_ha_state()
        else:
            _LOGGER.warning("Clock write rejected by machine (NACK)")
