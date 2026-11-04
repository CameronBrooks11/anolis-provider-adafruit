"""Adafruit BME280: temperature, humidity and pressure (STEMMA QT, I2C 0x77 or 0x76).

Driver: adafruit-circuitpython-bme280.

A chip that restarted on its own (a brown-out) comes back asleep, with its data
registers at reset values that convert to plausible readings, and the driver
keeps its own copy of the mode, so it never notices. The board reads the mode
back from the chip on every read, through the driver, and sets the chip up
again, keeping the sea-level pressure, when it finds it asleep.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from typing import Any

from anolis_provider_sdk import Arg, Category, DeviceType, Function, Signal, ValueType

from ..mock import FakeBME280
from .base import DeviceDriver

log = logging.getLogger(__name__)

# The longest the first measurement takes once the chip is in normal mode, at
# the driver's oversampling (temperature x1, pressure x16, humidity x1): BME280
# datasheet section 9.1, 1.25 + 2.3 + (2.3 * 16 + 0.575) + (2.3 + 0.575) ms.
# Until it completes, the data registers hold their reset values.
FIRST_MEASUREMENT_S = 0.044

TYPE = DeviceType(
    id="bme280",
    signals=(
        Signal("temperature", ValueType.DOUBLE, unit="C", description="Air temperature"),
        Signal("relative_humidity", ValueType.DOUBLE, unit="%", description="Relative humidity"),
        Signal("pressure", ValueType.DOUBLE, unit="hPa", description="Barometric pressure"),
        Signal(
            "altitude",
            ValueType.DOUBLE,
            unit="m",
            description="Altitude estimated from pressure and the sea-level pressure",
            default=False,
            poll_hint_hz=0.0,
        ),
        Signal(
            "sea_level_pressure",
            ValueType.DOUBLE,
            unit="hPa",
            description="Sea-level pressure the altitude estimate uses",
            default=False,
            poll_hint_hz=0.0,
        ),
    ),
    functions=(
        Function(
            "set_sea_level_pressure",
            description="Set the local sea-level pressure, which calibrates the altitude estimate",
            args=(
                Arg(
                    "sea_level_pressure",
                    ValueType.DOUBLE,
                    min=870.0,
                    max=1085.0,
                    unit="hPa",
                    description="Local sea-level pressure; the recorded extremes bound it",
                ),
            ),
            category=Category.CONFIG,
            is_idempotent=True,
        ),
        Function(
            "soft_reset",
            description="Reset the sensor and reapply its settings, the sea-level pressure included",
            category=Category.CONFIG,
            is_idempotent=True,
        ),
    ),
)


class BME280(DeviceDriver):
    type = TYPE
    addresses = (0x77, 0x76)

    def __init__(self, i2c: Any, address: int) -> None:
        self._i2c = i2c
        self._address = address
        self._sensor = self._open()

    def _open(self) -> Any:
        import adafruit_bme280.basic as driver

        # The driver's constructor checks the chip id and soft-resets the chip.
        sensor = driver.Adafruit_BME280_I2C(self._i2c, self._address)
        # Normal mode: the chip measures continuously, so a read fetches the
        # latest result instead of triggering and waiting for a conversion.
        sensor.mode = driver.MODE_NORMAL
        time.sleep(FIRST_MEASUREMENT_S)
        return sensor

    def _reopen(self) -> None:
        """Set the chip up again from its reset state, keeping the sea-level pressure."""
        sea_level_pressure = self._sensor.sea_level_pressure
        self._sensor = self._open()
        self._sensor.sea_level_pressure = sea_level_pressure

    def _check_restarted(self) -> None:
        import adafruit_bme280.basic as driver

        mode = self._sensor._read_byte(driver._BME280_REGISTER_CTRL_MEAS) & 0b11
        if mode != driver.MODE_NORMAL:
            log.warning("BME280 at %#04x restarted (mode %d); setting it up again", self._address, mode)
            self._reopen()

    @staticmethod
    def fake() -> FakeBME280:
        return FakeBME280()

    def read(self, signal_ids: list[str]) -> Mapping[str, Any]:
        self._check_restarted()
        s = self._sensor
        getters = {
            "temperature": lambda: s.temperature,
            "relative_humidity": lambda: s.relative_humidity,
            "pressure": lambda: s.pressure,
            "altitude": lambda: s.altitude,
            "sea_level_pressure": lambda: s.sea_level_pressure,
        }
        return {sid: float(getters[sid]()) for sid in signal_ids}

    def call(self, function: Function, args: Mapping[str, Any]) -> Mapping[str, Any] | None:
        if function.name == "set_sea_level_pressure":
            self._sensor.sea_level_pressure = args["sea_level_pressure"]
        elif function.name == "soft_reset":
            self._reopen()
        return None
