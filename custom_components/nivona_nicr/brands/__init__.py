"""BrandRegistry — central lookup for BrandProfile instances."""

from __future__ import annotations

import logging

from .base import (
    BrandProfile,
    FeatureNotSupported,
    MachineCapabilities,
    RecipeDescriptor,
    SettingDescriptor,
    StatDescriptor,
    supports_extension,
)
from .nivona import NivonaProfile

_LOGGER = logging.getLogger("nivona_nicr")


_PROFILES: dict[str, BrandProfile] = {
    NivonaProfile.brand_slug: NivonaProfile(),
}


def get_profile(slug: str) -> BrandProfile:
    """Return the registered profile for ``slug``. Raises KeyError."""
    return _PROFILES[slug]


def all_profiles() -> dict[str, BrandProfile]:
    """All registered profiles (slug → instance). Used by config_flow."""
    return dict(_PROFILES)


def detect_from_advertisement(local_name: str | None) -> BrandProfile | None:
    """Return the matching BrandProfile for a BLE advertisement local_name."""
    if not local_name:
        return None
    for profile in _PROFILES.values():
        if profile.ble_name_regex.match(local_name):
            return profile
    return None


__all__ = [
    "BrandProfile",
    "FeatureNotSupported",
    "MachineCapabilities",
    "NivonaProfile",
    "RecipeDescriptor",
    "SettingDescriptor",
    "StatDescriptor",
    "all_profiles",
    "detect_from_advertisement",
    "get_profile",
    "supports_extension",
]
