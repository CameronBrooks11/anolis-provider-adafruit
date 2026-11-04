"""The provider: Adafruit boards on one I2C bus, each driven by Adafruit's own driver.

Devices come from the config and stay listed for the life of the process. A
board that does not answer at start-up, or stops answering, is reported
UNREACHABLE and retried on the next read or call, so a loose cable recovers
without a restart.
"""

from __future__ import annotations

import errno
import logging
import os
import sys
from collections.abc import Mapping, Sequence
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from anolis_provider_sdk import (
    Category,
    Device,
    DeviceHealth,
    DeviceState,
    Function,
    Health,
    HealthState,
    HostRequirement,
    Provider,
    ProviderError,
    StatusCode,
    run,
)

from .devices import KINDS, DeviceDriver, NotAnswering
from .mock import FakeI2C

log = logging.getLogger("anolis_provider_adafruit")

# What a failed I2C transfer looks like from Linux: the board did not acknowledge
# (ENXIO, EREMOTEIO), the transfer failed or timed out (EIO, ETIMEDOUT), or the
# bus was busy (EAGAIN). Any other OSError, such as a missing file, is a fault in
# the provider rather than an absent board, and is not reported as UNREACHABLE.
_BUS_ERRNOS = {errno.ENXIO, errno.EREMOTEIO, errno.EIO, errno.ETIMEDOUT, errno.EAGAIN}


def _not_answering(err: Exception) -> bool:
    """Whether an exception from a board means the board is not answering: a
    failed I2C transfer, or a board module's NotAnswering. Anything else is a
    fault in the provider."""
    return isinstance(err, NotAnswering) or (isinstance(err, OSError) and err.errno in _BUS_ERRNOS)


def _is_setting(function: Function) -> bool:
    """A function the provider calls again after a reconnect: one that
    configures the board, gives the same result when repeated, and takes
    the setting as an argument."""
    return function.category is Category.CONFIG and function.is_idempotent and bool(function.args)


try:
    __version__ = version("anolis-provider-adafruit")
except PackageNotFoundError:  # a source tree that is not installed
    __version__ = "0.0.0"


def _device_schema() -> dict[str, Any]:
    per_kind = [
        {
            "if": {"properties": {"type": {"const": kind}}},
            "then": {"properties": {"address": {"enum": list(cls.addresses)}}},
        }
        for kind, cls in KINDS.items()
    ]
    return {
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "pattern": "^[a-z][a-z0-9_]*$",
                "description": "Device id, stable across restarts",
            },
            "type": {"enum": sorted(KINDS), "description": "Which board"},
            "address": {
                "type": "integer",
                "description": "I2C address; defaults to the board's factory address",
            },
            "label": {"type": "string"},
        },
        "required": ["id", "type"],
        "additionalProperties": False,
        "allOf": per_kind,
    }


CONFIG_SCHEMA: dict[str, Any] = {
    "title": "anolis-provider-adafruit config",
    "type": "object",
    "properties": {
        "i2c_bus": {
            "type": "integer",
            "minimum": 0,
            "default": 1,
            "description": "Linux I2C bus number, /dev/i2c-<n>. 1 is the Raspberry Pi header.",
        },
        "mock": {
            "type": "boolean",
            "default": False,
            "description": "Use a simulated bus with a register model of each configured board instead of hardware",
        },
        "devices": {"type": "array", "minItems": 1, "items": _device_schema()},
    },
    "required": ["devices"],
    "additionalProperties": False,
}


def bus_device(bus: int) -> str:
    """The Linux device node for an I2C bus number."""
    return f"/dev/i2c-{bus}"


class _Slot:
    """One configured board and its driver, when it is answering."""

    def __init__(self, kind: type[DeviceDriver], address: int) -> None:
        self.kind = kind
        self.address = address
        self.driver: DeviceDriver | None = None
        self.error = "not started"
        # The latest arguments of each setting function called, in the order
        # they were last set, for a reconnect to apply again.
        self.settings: dict[str, tuple[Function, Mapping[str, Any]]] = {}


class AdafruitProvider(Provider):
    name = "anolis-provider-adafruit"
    version = __version__
    conformance_level = 2
    config_schema = CONFIG_SCHEMA

    @classmethod
    def check_config(cls, config: Mapping[str, Any]) -> None:
        # What the schema cannot say. The SDK calls this for --check-config,
        # --check-host and before construction; __init__ calls it too.
        ids: set[str] = set()
        claimed: dict[int, str] = {}
        for entry in config["devices"]:
            address = entry.get("address", KINDS[entry["type"]].addresses[0])
            if entry["id"] in ids:
                raise ValueError(f"device id {entry['id']!r} is configured twice")
            if address in claimed:
                raise ValueError(
                    f"I2C address {address:#04x} is configured for both {claimed[address]!r} and {entry['id']!r}"
                )
            ids.add(entry["id"])
            claimed[address] = entry["id"]

    def __init__(self, config: Mapping[str, Any]) -> None:
        super().__init__(config)
        self.check_config(config)
        self._devices: list[Device] = []
        self._slots: dict[str, _Slot] = {}
        for entry in config["devices"]:
            kind = KINDS[entry["type"]]
            address = entry.get("address", kind.addresses[0])
            self._slots[entry["id"]] = _Slot(kind, address)
            self._devices.append(
                Device(
                    entry["id"],
                    kind.type,
                    label=entry.get("label", entry["id"]),
                    address=f"i2c-{config.get('i2c_bus', 1)}:{address:#04x}",
                )
            )
        self._bus: Any = None
        self._started = False
        self._bus_error: str | None = None

    # ---- lifecycle ----------------------------------------------------------------

    def start(self, budget_s: float) -> None:
        self._started = True
        try:
            if self.config.get("mock", False):
                self._bus = FakeI2C({s.address: s.kind.fake() for s in self._slots.values()})
            else:
                # Imported here: Blinka detects the board on import, which is slow on a Pi
                # and does not belong before Hello.
                from adafruit_extended_bus import ExtendedI2C

                self._bus = ExtendedI2C(self.config.get("i2c_bus", 1))
        except Exception as err:
            # Every board is unreachable, and says why.
            self._bus_error = f"the I2C bus did not open: {err}"
            for slot in self._slots.values():
                slot.error = self._bus_error
            raise
        # Stable: the config order holds within each group.
        for device_id, slot in sorted(self._slots.items(), key=lambda item: not item[1].kind.connect_first):
            self._connect(device_id, slot)

    def _connect(self, device_id: str, slot: _Slot) -> DeviceDriver | None:
        try:
            driver = slot.kind(self._bus, slot.address)
            # After a loss, a new driver starts from its defaults and the chip
            # may have lost power: set again what was set before.
            for function, args in slot.settings.values():
                driver.call(function, args)
            slot.driver = driver
        except (OSError, NotAnswering) as err:
            if not _not_answering(err):
                raise
            slot.driver = None
            slot.error = f"{slot.kind.type.id} at {slot.address:#04x}: {err}"
            log.warning("%s: %s", device_id, slot.error)
        return slot.driver

    def stop(self) -> None:
        # The SDK calls this once when the session ends, however it ends. The
        # Motor HAT has no watchdog, so this is what stops its motors when the
        # runtime goes away. One board failing must not leave the others running.
        for device_id, slot in self._slots.items():
            if slot.driver is None:
                continue
            try:
                slot.driver.stop()
            except Exception as err:
                if _not_answering(err):
                    log.warning("%s: could not drive it safe at stop: %s", device_id, err)
                else:
                    log.exception("%s: could not drive it safe at stop", device_id)

    # ---- ADPP -----------------------------------------------------------------------

    def devices(self) -> Sequence[Device]:
        return self._devices

    def _driver(self, device: Device) -> DeviceDriver:
        slot = self._slots[device.id]
        driver = slot.driver or (self._connect(device.id, slot) if self._bus is not None else None)
        if driver is None:
            raise ProviderError(StatusCode.UNAVAILABLE, f"{device.id} is not answering: {slot.error}")
        return driver

    def _lost(self, device: Device, err: Exception) -> ProviderError:
        slot = self._slots[device.id]
        slot.driver = None
        slot.error = f"{slot.kind.type.id} at {slot.address:#04x}: {err}"
        log.warning("%s: %s", device.id, slot.error)
        return ProviderError(StatusCode.UNAVAILABLE, f"{device.id} stopped answering: {err}")

    def read(self, device: Device, signal_ids: list[str]) -> Mapping[str, Any]:
        driver = self._driver(device)
        try:
            return driver.read(signal_ids)
        except (OSError, NotAnswering) as err:
            if not _not_answering(err):
                raise
            raise self._lost(device, err) from err

    def call(self, device: Device, function: Function, args: Mapping[str, Any]) -> Mapping[str, Any] | None:
        driver = self._driver(device)
        try:
            result = driver.call(function, args)
        except (OSError, NotAnswering) as err:
            if not _not_answering(err):
                raise
            raise self._lost(device, err) from err
        if _is_setting(function):
            settings = self._slots[device.id].settings
            settings.pop(function.name, None)  # to the end: the order they were last set in
            settings[function.name] = (function, dict(args))
        return result

    def health(self) -> Health:
        if self._bus_error is not None:
            return Health(HealthState.FAULT, self._bus_error)
        down = [device_id for device_id, slot in self._slots.items() if slot.driver is None]
        if down and self._started:
            return Health(HealthState.DEGRADED, f"not answering: {', '.join(down)}")
        return Health()

    def device_health(self, device: Device) -> DeviceHealth | None:
        slot = self._slots[device.id]
        if slot.driver is None and self._started:
            return DeviceHealth(DeviceState.UNREACHABLE, slot.error)
        return None

    # ---- executable profile §6 --------------------------------------------------------

    @classmethod
    def check_host(cls, config: Mapping[str, Any]) -> Sequence[HostRequirement]:
        if config.get("mock", False):
            return []
        path = bus_device(config.get("i2c_bus", 1))
        if not os.path.exists(path):
            return [
                HostRequirement(
                    "i2c_bus",
                    "unmet",
                    detail=f"{path} does not exist",
                    remedy="enable I2C (on Raspberry Pi OS: sudo raspi-config nonint do_i2c 0), then reboot",
                )
            ]
        if not os.access(path, os.R_OK | os.W_OK):
            return [
                HostRequirement(
                    "i2c_bus",
                    "unmet",
                    detail=f"{path} is not readable and writable by this user",
                    remedy="add the service user to the i2c group: sudo usermod -aG i2c anolis",
                )
            ]
        return [HostRequirement("i2c_bus", "met", detail=f"{path} is accessible")]


def main() -> None:
    sys.exit(run(AdafruitProvider))
