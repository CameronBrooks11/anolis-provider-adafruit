"""Sensirion SHTC3 on Adafruit boards (4636): temperature and humidity
(STEMMA QT, I2C 0x70, fixed).

Driver: adafruit-circuitpython-shtc3. Its constructor wakes the chip, resets
it and checks the chip id. The chip sleeps between measurements, which the
driver handles.

A reading whose CRC fails comes back from the driver as (None, None), with no
error. The board reports it as a failed transfer, so the provider retries the
board instead of passing on a missing value.
"""

from __future__ import annotations

import errno
from collections.abc import Mapping
from typing import Any

from anolis_provider_sdk import DeviceType, Function, Signal, ValueType

from ..mock import FakeSHTC3
from .base import DeviceDriver

TYPE = DeviceType(
    id="shtc3",
    signals=(
        Signal("temperature", ValueType.DOUBLE, unit="C", description="Air temperature"),
        Signal("relative_humidity", ValueType.DOUBLE, unit="%", description="Relative humidity"),
    ),
)


class SHTC3(DeviceDriver):
    type = TYPE
    addresses = (0x70,)  # the driver has no address argument: the chip has one address

    def __init__(self, i2c: Any, address: int) -> None:
        import adafruit_shtc3

        self._sensor = adafruit_shtc3.SHTC3(i2c)

    @staticmethod
    def fake() -> FakeSHTC3:
        return FakeSHTC3()

    def read(self, signal_ids: list[str]) -> Mapping[str, Any]:
        temperature, humidity = self._sensor.measurements
        if temperature is None or humidity is None:
            raise OSError(errno.EIO, "SHTC3 reading failed its CRC")
        values = {"temperature": temperature, "relative_humidity": humidity}
        return {sid: float(values[sid]) for sid in signal_ids}

    def call(self, function: Function, args: Mapping[str, Any]) -> Mapping[str, Any] | None:
        raise NotImplementedError("the SHTC3 declares no functions")
