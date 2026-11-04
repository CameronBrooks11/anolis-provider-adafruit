"""The boards this provider supports, by the ``type`` a config names them with."""

from __future__ import annotations

from .base import DeviceDriver, NotAnswering
from .bme280 import BME280
from .motor_hat import MotorHat
from .sht4x import SHT4x
from .shtc3 import SHTC3

KINDS: dict[str, type[DeviceDriver]] = {
    "bme280": BME280,
    "motor_hat": MotorHat,
    "sht4x": SHT4x,
    "shtc3": SHTC3,
}

__all__ = ["KINDS", "DeviceDriver", "NotAnswering"]
