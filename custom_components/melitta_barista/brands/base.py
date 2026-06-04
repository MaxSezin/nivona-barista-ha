"""BrandProfile abstraction — re-export shim.

The canonical definitions moved to ``coffee_platform.domain`` (the
platform owns the shared vocabulary). This module re-exports them so
existing ``from .base import X`` / ``from ..brands.base import X``
imports keep working unchanged.
"""

from __future__ import annotations

from ..coffee_platform.domain import (
    BrandProfile,
    FeatureNotSupported,
    MachineCapabilities,
    RecipeDescriptor,
    RecipeFieldLayout,
    SettingDescriptor,
    StatDescriptor,
    supports_extension,
)

__all__ = [
    "BrandProfile",
    "FeatureNotSupported",
    "MachineCapabilities",
    "RecipeDescriptor",
    "RecipeFieldLayout",
    "SettingDescriptor",
    "StatDescriptor",
    "supports_extension",
]
