"""Sensirion SHT40, SHT41 and SHT45 on Adafruit boards (SHT40 4885, SHT41 5776,
SHT45 5665, SHT45 with PTFE cap 6174): temperature and humidity (STEMMA QT,
I2C 0x44).

Driver: adafruit-circuitpython-sht4x.

The driver's constructor only soft-resets the chip, so the board reads the
serial number, which comes back with a CRC, to check that an SHT4x answers.
A reading whose CRC fails raises RuntimeError in the driver; the board reports
it as a failed transfer, so the provider retries the board rather than
treating it as a provider fault.

Measurements are high precision with the heater off. The heater modes are not
exposed: run long enough, they damage the sensor.
"""

from __future__ import annotations

import errno
from collections.abc import Mapping
from typing import Any

from anolis_provider_sdk import DeviceType, Function, Signal, ValueType

from ..mock import FakeSHT4x
from .base import DeviceDriver

TYPE = DeviceType(
    id="sht4x",
    signals=(
        Signal("temperature", ValueType.DOUBLE, unit="C", description="Air temperature"),
        Signal("relative_humidity", ValueType.DOUBLE, unit="%", description="Relative humidity"),
    ),
)


class SHT4x(DeviceDriver):
    type = TYPE
    addresses = (0x44,)

    def __init__(self, i2c: Any, address: int) -> None:
        import adafruit_sht4x

        self._sensor = adafruit_sht4x.SHT4x(i2c, address)
        self._sensor.mode = adafruit_sht4x.Mode.NOHEAT_HIGHPRECISION
        try:
            self._sensor.serial_number  # noqa: B018 - read for its CRC check
        except RuntimeError as err:
            raise ValueError(f"no SHT4x at {address:#04x}: its serial number did not read back intact") from err

    @staticmethod
    def fake() -> FakeSHT4x:
        return FakeSHT4x()

    def read(self, signal_ids: list[str]) -> Mapping[str, Any]:
        try:
            temperature, humidity = self._sensor.measurements
        except RuntimeError as err:  # the driver's CRC check
            raise OSError(errno.EIO, f"SHT4x reading failed its CRC: {err}") from err
        values = {"temperature": temperature, "relative_humidity": humidity}
        return {sid: float(values[sid]) for sid in signal_ids}

    def call(self, function: Function, args: Mapping[str, Any]) -> Mapping[str, Any] | None:
        raise NotImplementedError("the SHT4x declares no functions")
