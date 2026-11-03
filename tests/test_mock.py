"""The fake bus against Adafruit's real driver: if the register model were wrong,
the driver's own chip-id check and compensation maths would show it."""

from __future__ import annotations

import adafruit_bme280.basic as driver
import pytest

from anolis_provider_adafruit.mock import FakeBME280, FakeI2C


def test_driver_reads_the_datasheet_example_through_the_fake_bus() -> None:
    sensor = driver.Adafruit_BME280_I2C(FakeI2C({0x77: FakeBME280()}), 0x77)
    # Bosch BME280 datasheet, section 8.1: 25.08 C and 100653 Pa.
    assert sensor.temperature == pytest.approx(25.08, abs=0.01)
    assert sensor.pressure == pytest.approx(1006.53, abs=0.01)
    assert 0.0 < sensor.relative_humidity < 100.0


def test_raw_readings_change_what_the_driver_reports() -> None:
    chip = FakeBME280()
    sensor = driver.Adafruit_BME280_I2C(FakeI2C({0x77: chip}), 0x77)
    before = sensor.temperature
    chip.set_raw(temperature=530000, pressure=415148, humidity=28000)
    assert sensor.temperature > before


def test_an_empty_address_fails_the_driver_probe() -> None:
    with pytest.raises(ValueError, match="No I2C device"):
        driver.Adafruit_BME280_I2C(FakeI2C({0x77: FakeBME280()}), 0x76)


def test_a_failed_bus_raises_oserror() -> None:
    bus = FakeI2C({0x77: FakeBME280()})
    sensor = driver.Adafruit_BME280_I2C(bus, 0x77)
    bus.fail = True
    with pytest.raises(OSError):
        _ = sensor.temperature


def test_the_register_pointer_advances_across_reads() -> None:
    chip = FakeBME280()
    chip.write(bytes([0x88]))
    first, second = chip.read(2), chip.read(2)
    assert first + second == bytes(chip.registers[0x88:0x8C])


def test_a_write_stores_bytes_from_the_pointer() -> None:
    chip = FakeBME280()
    chip.write(bytes([0xF4, 0x27, 0xA0]))
    assert chip.registers[0xF4:0xF6] == bytes([0x27, 0xA0])
