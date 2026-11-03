"""The boards this provider supports, by the ``type`` a config names them with."""

from __future__ import annotations

from .base import DeviceDriver
from .bme280 import BME280

KINDS: dict[str, type[DeviceDriver]] = {
    "bme280": BME280,
}

__all__ = ["KINDS", "DeviceDriver"]
