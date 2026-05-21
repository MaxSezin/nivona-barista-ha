"""Diagnostics support — dumps runtime state for bug reports."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .ble_client import MelittaBleClient

REDACT_KEYS = {"address", "unique_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    client: MelittaBleClient = entry.runtime_data

    # Redact BLE address for privacy
    address = entry.data.get("address", "")
    redacted_address = (
        f"{address[:5]}:**:**:**:**:{address[-2:]}" if len(address) >= 17 else "redacted"
    )

    # Frame logs for protocol-level diagnostics. _recent_frames captures raw
    # bytes on every BLE notification (pre-decryption). _frame_log on the
    # protocol object stores decoded payloads — useful for inspecting
    # unsolicited commands like HF / HQ / HP that the integration does not
    # currently decode.
    protocol = getattr(client, "_protocol", None)
    frame_log = list(getattr(protocol, "_frame_log", []))
    recent_frames = list(getattr(client, "_recent_frames", []))

    return {
        "entry": {
            "title": entry.title,
            "address": redacted_address,
            "source": entry.source,
            "version": entry.version,
        },
        "device": {
            "connected": client.connected,
            "firmware": client.firmware_version,
            "serial": client.serial_number,
            "features": str(client.features) if client.features is not None else None,
            "machine_type": str(client.machine_type) if client.machine_type else None,
            "model_name": client.model_name,
        },
        "status": {
            "process": str(client.status.process) if client.status else None,
            "sub_process": str(client.status.sub_process) if client.status else None,
            "progress": client.status.progress if client.status else None,
            "is_ready": client.status.is_ready if client.status else None,
        },
        "counters": {
            "total_cups": client.total_cups,
            "per_recipe": dict(client.cup_counters),
        },
        "profiles": {
            "count": len(client.profile_names),
            "active_profile": client.active_profile,
            "names": dict(client.profile_names),
        },
        "options": dict(entry.options),
        "ble_trace": {
            "recent_frames_raw": recent_frames,
            "frame_log_decoded": frame_log,
        },
    }
