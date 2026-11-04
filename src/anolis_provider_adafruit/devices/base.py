"""What each supported Adafruit board provides to the provider."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from anolis_provider_sdk import DeviceType, Function

from ..mock import FakeChip


class NotAnswering(Exception):
    """Raised by a board module when the board at the address is absent, is a
    different chip, or has not finished starting. The provider reports the
    board UNREACHABLE and tries it again on the next read or call, as it does
    for a failed I2C transfer. Any other exception is a provider fault."""


def nothing_at(err: ValueError) -> bool:
    """Whether a ValueError is adafruit_bus_device's probe finding nothing
    acknowledging the address, which every driver here constructs through."""
    return str(err).startswith("No I2C device at address")


class DeviceDriver:
    """One supported board: its ADPP declaration and a thin wrapper over the
    Adafruit driver. Construct it with an open I2C bus and an address; the
    constructor raises NotAnswering, or lets the bus's OSError through, if the
    board does not answer there.

    A function whose category is CONFIG, that is idempotent and that takes at
    least one argument is a setting. The provider records the latest arguments
    of each setting called and, when it reconnects a board it had lost, calls
    them on the new driver in the order they were last set, so a setting
    survives a reconnect. Declare a function that way only if calling it again
    with the same arguments puts the setting back. A setting that fails to
    apply again leaves the board lost, like any failed transfer."""

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
