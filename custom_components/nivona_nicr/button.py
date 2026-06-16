"""Button platform — brew / cancel / maintenance for Nivona machines."""

from __future__ import annotations

import asyncio
import logging

from bleak.exc import BleakError
from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.const import CONF_ADDRESS, CONF_NAME
from .ble_client import resolve_caps_from_scanner
from .coffee_platform.contract import CoffeeMachineClient
from .const import (
    HE_CMD_FACTORY_RESET_RECIPES,
    HE_CMD_FACTORY_RESET_SETTINGS,
    PROMPT_MANIPULATIONS,
    MachineProcess,
)
from .entity import MelittaDeviceMixin
from .protocol import MachineStatus


PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger("nivona_nicr")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities for Nivona coffee machine."""
    client: CoffeeMachineClient = entry.runtime_data
    name = entry.data.get(CONF_NAME) or f"{client.brand.brand_name} Coffee Machine"

    entities: list[ButtonEntity] = []

    # HE-selector brew button (Nivona uses HE instead of HC)
    entities.append(NivonaBrewButton(client, entry, name))

    # Cancel button
    entities.append(MelittaCancelButton(client, entry, name))

    # Confirm machine prompt (HY command)
    entities.append(MelittaConfirmPromptButton(client, entry, name))

    # Factory reset buttons — only for families that advertise the capability
    brand_supports_factory_reset = any(
        c.supports_factory_reset for c in client.brand.families.values()
    )
    if brand_supports_factory_reset:
        entities.append(NivonaFactoryResetSettingsButton(client, entry, name))
        entities.append(NivonaFactoryResetRecipesButton(client, entry, name))

    # MyCoffee slot brew buttons
    caps_for_brew = client.capabilities or resolve_caps_from_scanner(
        hass, entry.data.get(CONF_ADDRESS, ""), client.brand,
    )
    if (
        caps_for_brew is not None
        and caps_for_brew.my_coffee_slots > 0
        and client.brand.mycoffee_layout(caps_for_brew.family_key) is not None
    ):
        for slot in range(caps_for_brew.my_coffee_slots):
            entities.append(NivonaBrewMyCoffeeButton(client, entry, name, slot))

    # Reset brew overrides button (clears user_set on all override sliders)
    entities.append(NivonaResetOverridesButton(client, entry, name))

    # Maintenance buttons
    entities.append(MelittaMaintenanceButton(
        client, entry, name,
        key="easy_clean", label="Easy Clean",
        icon="mdi:shimmer", process=MachineProcess.EASY_CLEAN,
    ))
    entities.append(MelittaMaintenanceButton(
        client, entry, name,
        key="intensive_clean", label="Intensive Clean",
        icon="mdi:dishwasher", process=MachineProcess.INTENSIVE_CLEAN,
    ))
    entities.append(MelittaMaintenanceButton(
        client, entry, name,
        key="descaling", label="Descaling",
        icon="mdi:water-sync", process=MachineProcess.DESCALING,
    ))
    entities.append(MelittaMaintenanceButton(
        client, entry, name,
        key="filter_insert", label="Filter Insert",
        icon="mdi:filter-plus", process=MachineProcess.FILTER_INSERT,
    ))
    entities.append(MelittaMaintenanceButton(
        client, entry, name,
        key="filter_replace", label="Filter Replace",
        icon="mdi:filter-cog", process=MachineProcess.FILTER_REPLACE,
    ))
    entities.append(MelittaMaintenanceButton(
        client, entry, name,
        key="filter_remove", label="Filter Remove",
        icon="mdi:filter-remove", process=MachineProcess.FILTER_REMOVE,
    ))
    entities.append(MelittaMaintenanceButton(
        client, entry, name,
        key="evaporating", label="Evaporating",
        icon="mdi:air-humidifier", process=MachineProcess.EVAPORATING,
    ))
    entities.append(MelittaMaintenanceButton(
        client, entry, name,
        key="switch_off", label="Switch Off",
        icon="mdi:power", process=MachineProcess.SWITCH_OFF,
    ))

    async_add_entities(entities)


class _MelittaButtonBase(MelittaDeviceMixin, ButtonEntity):
    """Base class shared by all coffee-machine buttons."""

    _attr_has_entity_name = True

    def __init__(self, client: CoffeeMachineClient, entry: ConfigEntry, machine_name: str) -> None:
        self._client = client
        self._entry = entry
        self._machine_name = machine_name

    async def async_added_to_hass(self) -> None:
        self._client.add_status_callback(self._on_status_update)
        self._client.add_connection_callback(self._on_connection_change)

    async def async_will_remove_from_hass(self) -> None:
        self._client.remove_status_callback(self._on_status_update)
        self._client.remove_connection_callback(self._on_connection_change)

    @callback
    def _on_status_update(self, status: MachineStatus) -> None:
        self.async_write_ha_state()

    @callback
    def _on_connection_change(self, connected: bool) -> None:
        self.async_write_ha_state()


class MelittaCancelButton(_MelittaButtonBase):
    """Button to cancel current operation."""

    _attr_name = "Cancel"
    _attr_icon = "mdi:stop-circle"

    @property
    def unique_id(self) -> str:
        return f"{self._client.address}_cancel"

    @property
    def available(self) -> bool:
        if not self._client.connected or not self._client.status:
            return False
        return self._client.status.process not in (MachineProcess.READY, None)

    async def async_press(self) -> None:
        status = self._client.status
        if status and status.process:
            _LOGGER.info("Cancelling process %s", status.process)
            try:
                await self._client.cancel_process(status.process)
            except (BleakError, OSError, asyncio.TimeoutError):
                _LOGGER.exception("BLE error while cancelling")


class _NivonaFactoryResetButtonBase(_MelittaButtonBase):
    """Shared base for the two Nivona factory-reset buttons."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_icon = "mdi:restore-alert"

    _command_id: int = 0
    _slug: str = ""
    _log_label: str = ""

    @property
    def unique_id(self) -> str:
        return f"{self._client.address}_factory_reset_{self._slug}"

    @property
    def available(self) -> bool:
        if not self._client.connected:
            return False
        caps = getattr(self._client, "capabilities", None)
        if caps is None:
            return False
        return caps.supports_factory_reset

    async def async_press(self) -> None:
        _LOGGER.warning(
            "Initiating Nivona factory reset (%s, HE commandId=%d) on %s",
            self._log_label, self._command_id, self._client.address,
        )
        try:
            success = await self._client.execute_he_command(self._command_id)
        except (BleakError, OSError, asyncio.TimeoutError):
            _LOGGER.exception("BLE error during factory reset %s", self._log_label)
            return
        if not success:
            _LOGGER.warning("Factory reset %s returned NACK or timeout", self._log_label)


class NivonaFactoryResetSettingsButton(_NivonaFactoryResetButtonBase):
    _attr_name = "Factory Reset Settings"
    _command_id = HE_CMD_FACTORY_RESET_SETTINGS
    _slug = "settings"
    _log_label = "settings"


class NivonaFactoryResetRecipesButton(_NivonaFactoryResetButtonBase):
    _attr_name = "Factory Reset Recipes"
    _command_id = HE_CMD_FACTORY_RESET_RECIPES
    _slug = "recipes"
    _log_label = "recipes"


class MelittaConfirmPromptButton(_MelittaButtonBase):
    """Confirm an active machine prompt via HY."""

    _attr_name = "Confirm Prompt"
    _attr_icon = "mdi:check-circle-outline"

    @property
    def unique_id(self) -> str:
        return f"{self._client.address}_confirm_prompt"

    @property
    def available(self) -> bool:
        if not self._client.connected or not self._client.status:
            return False
        return self._client.status.manipulation in PROMPT_MANIPULATIONS

    async def async_press(self) -> None:
        status = self._client.status
        manip = status.manipulation if status else None
        if manip is None or manip not in PROMPT_MANIPULATIONS:
            _LOGGER.debug("No active prompt to confirm")
            return
        _LOGGER.info("Confirming prompt: %s", manip.name)
        try:
            success = await self._client.confirm_prompt()
            if not success:
                _LOGGER.warning("Confirm prompt %s: machine returned NACK or timeout", manip.name)
        except (BleakError, OSError, asyncio.TimeoutError):
            _LOGGER.exception("BLE error while confirming prompt %s", manip.name)


class NivonaBrewButton(_MelittaButtonBase):
    """Brew the recipe selected in NivonaRecipeSelect via HE."""

    _attr_name = "Brew"
    _attr_icon = "mdi:coffee"

    _OVERRIDE_FIELDS = (
        "strength", "coffee_amount", "water_amount", "temperature", "milk_amount",
    )

    @property
    def unique_id(self) -> str:
        return f"{self._client.address}_nivona_brew"

    def _collect_user_overrides(self, registry) -> dict:
        """Collect overrides from NivonaBrewOverrideNumber entities.

        If ANY field has user_set=True (triggering temp-recipe mode), ALL
        current slider values are included so the machine receives a complete
        temp recipe and does not fall back to hardware defaults for unset fields.
        """
        field_states: dict[str, int] = {}
        has_user_set = False

        for field in self._OVERRIDE_FIELDS:
            uid = f"{self._client.address}_brew_{field}"
            for eid, reg_entry in registry.entities.items():
                if reg_entry.unique_id != uid:
                    continue
                st = self.hass.states.get(eid)
                if not st or st.state in (None, "unknown", "unavailable"):
                    break
                try:
                    field_states[field] = int(float(st.state))
                except ValueError:
                    break
                if st.attributes.get("user_set"):
                    has_user_set = True
                break

        if not has_user_set:
            return {}

        # When temp-recipe mode is triggered, send ALL current slider values
        # to prevent the machine from filling unset fields with hardware defaults.
        return field_states

    @property
    def available(self) -> bool:
        return (
            self._client.connected
            and self._client.status is not None
            and self._client.status.is_ready
        )

    async def async_press(self) -> None:
        from homeassistant.helpers import entity_registry as er
        registry = er.async_get(self.hass)
        target_uid = f"{self._client.address}_nivona_recipe_select"
        entity_id = None
        for eid, entry in registry.entities.items():
            if entry.unique_id == target_uid:
                entity_id = eid
                break
        if not entity_id:
            _LOGGER.warning("NivonaRecipeSelect not found")
            return
        state = self.hass.states.get(entity_id)
        if not state:
            _LOGGER.warning("recipe select state unavailable")
            return

        caps = self._client.capabilities
        if not caps or not caps.recipes:
            _LOGGER.warning("no recipes in capabilities")
            return
        recipe_id = None
        for r in caps.recipes:
            if r.name == state.state:
                recipe_id = r.recipe_id
                break
        if recipe_id is None:
            _LOGGER.warning("recipe %s not matched", state.state)
            return

        overrides = self._collect_user_overrides(registry)
        try:
            success = await self._client.brew_nivona(recipe_id, overrides or None)
            if not success:
                _LOGGER.error("Nivona brew failed for recipe_id=%d", recipe_id)
        except (BleakError, OSError, asyncio.TimeoutError):
            _LOGGER.exception("BLE error during Nivona brew")


class NivonaResetOverridesButton(_MelittaButtonBase):
    """Reset all brew override sliders — clears user_set so next brew uses machine defaults."""

    _attr_name = "Reset Brew Overrides"
    _attr_icon = "mdi:restore"
    _attr_entity_category = EntityCategory.CONFIG

    _OVERRIDE_FIELDS = (
        "strength", "coffee_amount", "water_amount", "temperature", "milk_amount",
    )

    @property
    def unique_id(self) -> str:
        return f"{self._client.address}_reset_brew_overrides"

    @property
    def available(self) -> bool:
        return True  # always available so user can reset even when disconnected

    async def async_press(self) -> None:
        from homeassistant.helpers import entity_registry as er
        from homeassistant.helpers import entity_component as ec
        registry = er.async_get(self.hass)

        for field in self._OVERRIDE_FIELDS:
            uid = f"{self._client.address}_brew_{field}"
            for eid, reg_entry in registry.entities.items():
                if reg_entry.unique_id != uid:
                    continue
                # Retrieve the live entity object from hass entity platform
                entity_obj = self.hass.states.get(eid)
                if entity_obj is not None:
                    # Fire an event that NivonaBrewOverrideNumber listens for
                    self.hass.bus.async_fire(
                        f"nivona_nicr_reset_override_{uid}",
                    )
                break
        _LOGGER.info("Brew overrides reset — user_set cleared on all sliders")


class MelittaMaintenanceButton(_MelittaButtonBase):
    """Button for maintenance operations (cleaning, descaling, power off)."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, client: CoffeeMachineClient, entry: ConfigEntry,
        machine_name: str, *, key: str, label: str, icon: str,
        process: MachineProcess,
    ) -> None:
        super().__init__(client, entry, machine_name)
        self._process = process
        self._key = key
        self._attr_name = label
        self._attr_icon = icon

    @property
    def unique_id(self) -> str:
        return f"{self._client.address}_{self._key}"

    @property
    def available(self) -> bool:
        return self._client.connected and (
            self._client.status is not None and self._client.status.is_ready
        )

    async def async_press(self) -> None:
        _LOGGER.info("Starting %s", self._attr_name)
        method_map = {
            MachineProcess.EASY_CLEAN: self._client.start_easy_clean,
            MachineProcess.INTENSIVE_CLEAN: self._client.start_intensive_clean,
            MachineProcess.DESCALING: self._client.start_descaling,
            MachineProcess.FILTER_INSERT: self._client.start_filter_insert,
            MachineProcess.FILTER_REPLACE: self._client.start_filter_replace,
            MachineProcess.FILTER_REMOVE: self._client.start_filter_remove,
            MachineProcess.EVAPORATING: self._client.start_evaporating,
            MachineProcess.SWITCH_OFF: self._client.switch_off,
        }
        method = method_map.get(self._process)
        if not method:
            _LOGGER.error("Unknown process %s", self._process)
            return
        try:
            success = await method()
            if not success:
                _LOGGER.error("Failed to start %s", self._attr_name)
        except (BleakError, OSError, asyncio.TimeoutError):
            _LOGGER.exception("BLE error while starting %s", self._attr_name)


class NivonaBrewMyCoffeeButton(_MelittaButtonBase):
    """Brew a saved MyCoffee recipe by slot (Nivona only)."""

    _attr_icon = "mdi:coffee-to-go"

    def __init__(
        self,
        client: CoffeeMachineClient,
        entry: ConfigEntry,
        name: str,
        slot: int,
    ) -> None:
        super().__init__(client, entry, name)
        self._slot = slot
        self._attr_name = f"Brew MyCoffee slot {slot + 1}"

    @property
    def unique_id(self) -> str:
        return f"{self._client.address}_brew_mycoffee_slot_{self._slot}"

    @property
    def available(self) -> bool:
        if not self._client.connected:
            return False
        status = self._client.status
        caps = getattr(self._client, "capabilities", None)
        tolerated = caps.tolerated_brew_manipulations if caps else ()
        if status is None or not status.is_ready_for_brew(tolerated):
            return False
        slots = self._client.my_coffee_slots
        if slots is None or self._slot >= len(slots):
            return False
        return slots[self._slot].get("enabled", 0) == 1

    async def async_press(self) -> None:
        _LOGGER.info("Brewing MyCoffee slot %d", self._slot + 1)
        try:
            success = await self._client.brew_mycoffee_slot(self._slot)
            if not success:
                _LOGGER.error("Failed to start MyCoffee brew for slot %d", self._slot + 1)
        except (BleakError, OSError, asyncio.TimeoutError):
            _LOGGER.exception("BLE error while brewing MyCoffee slot %d", self._slot + 1)
