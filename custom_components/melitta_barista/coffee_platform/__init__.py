"""coffee_platform — transport-agnostic coffee-machine platform contract.

Self-contained subpackage. Defines the `CoffeeMachineClient` Protocol that
entities and the Sommelier consume. Has NO imports back into `melitta_barista`
internals so it can be lifted into a standalone `coffee-platform-ha` repo later.
"""

from __future__ import annotations

from .contract import CoffeeMachineClient

__all__ = ["CoffeeMachineClient"]
