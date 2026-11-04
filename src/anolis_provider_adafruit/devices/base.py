"""What each supported Adafruit board provides to the provider."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from anolis_provider_sdk import DeviceType, Function

from ..mock import FakeChip


class DeviceDriver:
    """One supported board: its ADPP declaration and a thin wrapper over the
    Adafruit driver. Construct it with an open I2C bus and an address; the
    constructor raises if the board does not answer there."""

    type: ClassVar[DeviceType]
    # Addresses the board can be strapped to. The first is the factory default.
    addresses: ClassVar[tuple[int, ...]]
    # Connect this board before the others at start-up, whatever the config order:
    # for a board that answers another board's address until it is set up.
    connect_first: ClassVar[bool] = False

    def __init__(self, i2c: Any, address: int) -> None:
        raise NotImplementedError

    @staticmethod
    def fake() -> FakeChip:
        """A register model of the chip, for mock mode."""
        raise NotImplementedError

    def read(self, signal_ids: list[str]) -> Mapping[str, Any]:
        raise NotImplementedError

    def call(self, function: Function, args: Mapping[str, Any]) -> Mapping[str, Any] | None:
        raise NotImplementedError
