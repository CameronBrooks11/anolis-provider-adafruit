"""The provider in mock mode: inventory, reads, calls, and losing and regaining a board."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import adafruit_bme280.basic as driver
import pytest
from anolis_provider_sdk import DeviceState, HealthState, ProviderError, StatusCode
from anolis_provider_sdk.cli import ConfigError, load_config

from anolis_provider_adafruit.devices.bme280 import BME280
from anolis_provider_adafruit.mock import FakeBME280, FakeI2C
from anolis_provider_adafruit.provider import AdafruitProvider, bus_device

ALL_SIGNALS = ["temperature", "relative_humidity", "pressure", "altitude", "sea_level_pressure"]


def started(config: dict[str, Any]) -> AdafruitProvider:
    provider = AdafruitProvider(config)
    provider.start(0.0)
    return provider


def mock(*devices: dict[str, Any]) -> dict[str, Any]:
    return {"mock": True, "devices": list(devices) or [{"id": "env0", "type": "bme280"}]}


def bus(provider: AdafruitProvider) -> FakeI2C:
    fake = provider._bus
    assert isinstance(fake, FakeI2C)
    return fake


def test_devices_come_from_the_config_with_their_address() -> None:
    p = started(mock({"id": "env0", "type": "bme280"}, {"id": "env1", "type": "bme280", "address": 0x76}))
    assert [(d.id, d.type.id, d.address) for d in p.devices()] == [
        ("env0", "bme280", "i2c-1:0x77"),
        ("env1", "bme280", "i2c-1:0x76"),
    ]


def test_read_returns_every_signal_asked_for() -> None:
    p = started(mock())
    values = p.read(p.devices()[0], ALL_SIGNALS)
    assert set(values) == set(ALL_SIGNALS)
    assert values["temperature"] == pytest.approx(25.08, abs=0.01)
    assert values["sea_level_pressure"] == 1013.25


def test_sea_level_pressure_moves_the_altitude_and_survives_a_soft_reset() -> None:
    p = started(mock())
    d = p.devices()[0]
    fn = d.type.function_by_name("set_sea_level_pressure")
    reset = d.type.function_by_name("soft_reset")
    assert fn and reset
    before = p.read(d, ["altitude"])["altitude"]
    p.call(d, fn, {"sea_level_pressure": 1020.0})
    after = p.read(d, ["altitude", "sea_level_pressure"])
    assert after["sea_level_pressure"] == 1020.0
    assert after["altitude"] > before
    p.call(d, reset, {})
    assert p.read(d, ["sea_level_pressure"])["sea_level_pressure"] == 1020.0


def test_a_board_that_stops_answering_is_unreachable_then_recovers() -> None:
    p = started(mock())
    d = p.devices()[0]
    bus(p).fail = True
    with pytest.raises(ProviderError) as err:
        p.read(d, ["temperature"])
    assert err.value.code is StatusCode.UNAVAILABLE
    health = p.device_health(d)
    assert health and health.state is DeviceState.UNREACHABLE
    assert p.health().state is HealthState.DEGRADED
    # Still down: the retry on the next read fails the same way.
    with pytest.raises(ProviderError):
        p.read(d, ["temperature"])
    bus(p).fail = False
    assert p.read(d, ["temperature"])["temperature"] == pytest.approx(25.08, abs=0.01)
    assert p.device_health(d) is None
    assert p.health().state is HealthState.OK


def test_a_board_missing_at_start_is_listed_and_unreachable() -> None:
    p = AdafruitProvider(mock())
    original = FakeI2C.__init__

    def empty_bus(self: FakeI2C, chips: Any) -> None:
        original(self, {})

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(FakeI2C, "__init__", empty_bus)
        p.start(0.0)
    d = p.devices()[0]
    health = p.device_health(d)
    assert health and health.state is DeviceState.UNREACHABLE
    assert "0x77" in health.message
    with pytest.raises(ProviderError) as err:
        p.read(d, ["temperature"])
    assert err.value.code is StatusCode.UNAVAILABLE


def test_health_is_ok_before_start() -> None:
    p = AdafruitProvider(mock())
    assert p.health().state is HealthState.OK
    assert p.device_health(p.devices()[0]) is None


@pytest.mark.parametrize(
    ("devices", "message"),
    [
        ([{"id": "a", "type": "bme280"}, {"id": "a", "type": "bme280", "address": 0x76}], "configured twice"),
        ([{"id": "a", "type": "bme280"}, {"id": "b", "type": "bme280", "address": 0x77}], "0x77"),
    ],
)
def test_conflicting_devices_are_refused(devices: list[dict[str, Any]], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        AdafruitProvider({"mock": True, "devices": devices})


@pytest.mark.parametrize(
    "body",
    [
        "devices: []",
        "devices: [{id: env0, type: bme280, address: 0x50}]",
        "devices: [{id: env0, type: sht40}]",
        "devices: [{id: Env0, type: bme280}]",
        "i2c_bus: -1\ndevices: [{id: env0, type: bme280}]",
        "devices: [{id: env0, type: bme280}]\nextra: 1",
    ],
)
def test_the_schema_rejects_bad_configs(tmp_path: Path, body: str) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(body)
    with pytest.raises(ConfigError):
        load_config(AdafruitProvider, str(path))


def test_check_host_needs_nothing_in_mock_mode() -> None:
    assert AdafruitProvider.check_host(mock()) == []


REAL = {"i2c_bus": 3, "devices": [{"id": "env0", "type": "bme280"}]}


def check_host_with_node(monkeypatch: pytest.MonkeyPatch, node: Path) -> Any:
    def fake_bus_device(bus: int) -> str:
        assert bus == 3
        return str(node)

    monkeypatch.setattr("anolis_provider_adafruit.provider.bus_device", fake_bus_device)
    [req] = AdafruitProvider.check_host(REAL)
    assert req.id == "i2c_bus"
    return req


def test_check_host_reports_a_missing_bus(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    req = check_host_with_node(monkeypatch, tmp_path / "i2c-3")
    assert req.status == "unmet"
    assert "does not exist" in req.detail
    assert "raspi-config" in req.remedy


def test_check_host_reports_a_bus_the_user_cannot_open(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    node = tmp_path / "i2c-3"
    node.touch(mode=0o000)
    if os.access(node, os.R_OK):
        pytest.skip("running as root: file permissions do not apply")
    req = check_host_with_node(monkeypatch, node)
    assert req.status == "unmet"
    assert "not readable and writable" in req.detail
    assert "i2c group" in req.remedy


def test_check_host_accepts_an_accessible_bus(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    node = tmp_path / "i2c-3"
    node.touch(mode=0o600)
    assert check_host_with_node(monkeypatch, node).status == "met"


def test_the_bus_device_node_follows_the_bus_number() -> None:
    assert bus_device(1) == "/dev/i2c-1"


def test_an_error_that_is_not_a_bus_error_fails_start_instead_of_hiding_as_unreachable() -> None:
    # A frozen build missing a data file fails like this: it is a provider fault,
    # and reporting the board as merely unreachable would hide it.
    p = AdafruitProvider(mock())

    def broken(self: Any, i2c: Any, address: int) -> None:
        raise FileNotFoundError(2, "No such file or directory", "microcontroller_imports.json")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(BME280, "__init__", broken)
        with pytest.raises(FileNotFoundError):
            p.start(0.0)


def test_an_error_that_is_not_a_bus_error_on_read_is_not_unreachable() -> None:
    p = started(mock())
    d = p.devices()[0]

    def broken(self: Any, signal_ids: list[str]) -> Any:
        raise PermissionError(13, "Permission denied")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(BME280, "read", broken)
        with pytest.raises(PermissionError):
            p.read(d, ["temperature"])
    assert p.device_health(d) is None


def bme280_chip(provider: AdafruitProvider, address: int = 0x77) -> FakeBME280:
    chip = bus(provider).chips[address]
    assert isinstance(chip, FakeBME280)
    return chip


def test_a_bme280_that_restarted_on_its_own_is_set_up_again() -> None:
    p = started(mock())
    d = p.devices()[0]
    fn = d.type.function_by_name("set_sea_level_pressure")
    assert fn
    p.call(d, fn, {"sea_level_pressure": 1030.0})
    before = p.read(d, ALL_SIGNALS)
    chip = bme280_chip(p)
    chip.power_cycle()  # a brown-out: asleep, every setting 0, data at reset values
    assert chip.registers[0xFA:0xFD] == (FakeBME280.SKIPPED_TP << 4).to_bytes(3, "big")
    assert p.read(d, ALL_SIGNALS) == before
    assert chip.registers[FakeBME280.CTRL_MEAS] & 0b11 == driver.MODE_NORMAL
    assert p.device_health(d) is None
