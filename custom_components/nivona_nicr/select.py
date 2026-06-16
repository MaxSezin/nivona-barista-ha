"""Select platform — recipe and brand settings for Nivona machines."""

from __future__ import annotations

import asyncio
import logging

from bleak.exc import BleakError

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .ble_client import resolve_caps_from_scanner
from .coffee_platform.contract import CoffeeMachineClient
from .entity import MelittaDeviceMixin


PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger("nivona_nicr")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities for Nivona coffee machine."""
    client: CoffeeMachineClient = entry.runtime_data
    name = entry.data.get(CONF_NAME) or f"{client.brand.brand_name} Coffee Machine"

    entities: list = []

    # Brand capability-driven settings selects (Nivona recipe, temperature, profile, etc.)
    caps = client.capabilities or resolve_caps_from_scanner(
        hass, entry.data.get(CONF_ADDRESS, ""), client.brand,
    )
    if caps is not None and caps.settings:
        for descriptor in caps.settings:
            if not descriptor.options:
                continue
            entities.append(BrandSettingSelect(client, entry, name, descriptor))

    # HE-selector brew recipe select
    entities.append(NivonaRecipeSelect(client, entry, name))

    async_add_entities(entities)


class BrandSettingSelect(MelittaDeviceMixin, SelectEntity):
    """Generic setting select driven by a SettingDescriptor from the BrandProfile.

    Reads via HR, writes via HW.
    """

    _attr_has_entity_name = True
    _attr_entity_category = None

    def __init__(
        self, client: CoffeeMachineClient, entry: ConfigEntry, name: str, descriptor,
    ) -> None:
        self._client = client
        self._entry = entry
        self._machine_name = name
        self._desc = descriptor
        self._value_code: int | None = None
        self._label_to_code: dict[str, int] = {label: code for code, label in descriptor.options}
        self._code_to_label: dict[int, str] = {code: label for code, label in descriptor.options}
        self._attr_options = list(self._label_to_code.keys())
        self._attr_name = descriptor.title
        self._attr_translation_key = descriptor.key

    @property
    def unique_id(self) -> str:
        return f"{self._client.address}_setting_{self._desc.key}"

    @property
    def icon(self) -> str:
        return "mdi:tune"

    @property
    def current_option(self) -> str | None:
        if self._value_code is None:
            return None
        code = self._value_code & 0xFFFF
        return self._code_to_label.get(code)

    @property
    def available(self) -> bool:
        return self._client.connected

    async def async_added_to_hass(self) -> None:
        self._client.add_connection_callback(self._on_connection_change)
        if self._client.connected:
            await self._refresh()

    async def async_will_remove_from_hass(self) -> None:
        self._client.remove_connection_callback(self._on_connection_change)

    @callback
    def _on_connection_change(self, connected: bool) -> None:
        if connected:
            self.hass.async_create_task(self._refresh())
        self.async_write_ha_state()

    async def _refresh(self) -> None:
        try:
            value = await self._client.read_setting(self._desc.setting_id)
            if value is not None:
                self._value_code = value
                self.async_write_ha_state()
        except (BleakError, OSError, asyncio.TimeoutError):
            _LOGGER.debug("BrandSettingSelect %s refresh failed", self._desc.key, exc_info=True)

    async def async_select_option(self, option: str) -> None:
        code = self._label_to_code.get(option)
        if code is None:
            _LOGGER.warning("Unknown option %s for %s", option, self._desc.key)
            return
        try:
            success = await self._client.write_setting(self._desc.setting_id, code)
        except (BleakError, OSError, asyncio.TimeoutError):
            _LOGGER.exception("BLE error writing %s", self._desc.key)
            return
        if success:
            self._value_code = code
            self.async_write_ha_state()
        else:
            _LOGGER.warning("Machine rejected %s=%s (NACK/timeout)", self._desc.key, option)


class NivonaRecipeSelect(MelittaDeviceMixin, SelectEntity):
    """Recipe selector for Nivona (picks recipe_id for HE brew).

    Recipe list comes from capabilities.recipes resolved after first BLE connect.
    """

    _attr_has_entity_name = True
    _attr_name = "Recipe"
    _attr_icon = "mdi:coffee-maker-outline"
    _attr_should_poll = True

    def __init__(self, client: CoffeeMachineClient, entry: ConfigEntry, machine_name: str) -> None:
        self._client = client
        self._entry = entry
        self._machine_name = machine_name
        self._attr_unique_id = f"{client.address}_nivona_recipe_select"
        self._attr_options = ["(loading...)"]
        self._attr_current_option = "(loading...)"

    def _refresh_options(self) -> None:
        caps = self._client.capabilities
        if caps and caps.recipes:
            new_opts = [r.name for r in caps.recipes]
            if new_opts != self._attr_options:
                self._attr_options = new_opts
                if self._attr_current_option not in new_opts:
                    self._attr_current_option = new_opts[0]
                self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._refresh_options()

    async def async_update(self) -> None:
        self._refresh_options()

    @property
    def available(self) -> bool:
        caps = self._client.capabilities
        return bool(caps and caps.recipes)

    async def async_select_option(self, option: str) -> None:
        self._refresh_options()
        if option in self._attr_options:
            self._attr_current_option = option
            self.async_write_ha_state()

    @property
    def selected_recipe_id(self) -> int | None:
        caps = self._client.capabilities
        if not (caps and caps.recipes) or self._attr_current_option is None:
            return None
        for r in caps.recipes:
            if r.name == self._attr_current_option:
                return r.recipe_id
        return None
