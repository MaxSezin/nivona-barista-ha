"""MachineRegistry — central registry of connected machine clients.

Brand providers register their `CoffeeMachineClient` instances here; consumers
(Sommelier, services, future cross-machine features) discover machines without
knowing which brand/transport produced them. Single-machine today, multi-ready.
"""

from __future__ import annotations

from .contract import CoffeeMachineClient


class MachineRegistry:
    """Address-keyed registry of machine clients."""

    def __init__(self) -> None:
        self._machines: dict[str, CoffeeMachineClient] = {}

    def register(self, client: CoffeeMachineClient) -> str:
        """Register a client. Returns its address (the registration key)."""
        self._machines[client.address] = client
        return client.address

    def unregister(self, address: str) -> None:
        """Remove a client by address. No-op if absent."""
        self._machines.pop(address, None)

    def get_by_address(self, address: str) -> CoffeeMachineClient | None:
        """Return the client for `address`, or None."""
        return self._machines.get(address)

    def list_machines(self) -> list[CoffeeMachineClient]:
        """All registered clients."""
        return list(self._machines.values())
