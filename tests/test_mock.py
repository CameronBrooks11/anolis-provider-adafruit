"""The fake bus against Adafruit's real driver: if the register model were wrong,
the driver's own chip-id check and compensation maths would show it."""

from __future__ import annotations

import adafruit_bme280.basic as driver
import pytest

from anolis_provider_adafruit.mock import FakeBME280, FakeI2C, FakePCA9685


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


def test_the_pca9685_powers_on_asleep_with_every_output_off() -> None:
    chip = FakePCA9685()
    assert chip.registers[FakePCA9685.MODE1] & FakePCA9685.SLEEP
    assert all(chip.duty(channel) == (0, 0x1000) for channel in range(16))


def test_the_pca9685_pointer_stays_put_without_auto_increment() -> None:
    chip = FakePCA9685()
    chip.write(bytes([FakePCA9685.MODE1, 0x00]))  # awake, AI clear
    chip.write(bytes([0x06, 0x11, 0x22]))
    assert chip.registers[0x06:0x08] == bytes([0x22, 0x00])
    chip.write(bytes([FakePCA9685.MODE1, FakePCA9685.AI]))
    chip.write(bytes([0x06, 0x11, 0x22]))
    assert chip.registers[0x06:0x08] == bytes([0x11, 0x22])


def test_the_pca9685_takes_a_prescale_only_while_asleep() -> None:
    chip = FakePCA9685()
    chip.write(bytes([FakePCA9685.PRE_SCALE, 0x03]))
    assert chip.registers[FakePCA9685.PRE_SCALE] == 0x03
    chip.write(bytes([FakePCA9685.MODE1, 0x00]))
    chip.write(bytes([FakePCA9685.PRE_SCALE, 0x79]))
    assert chip.registers[FakePCA9685.PRE_SCALE] == 0x03


def test_the_pca9685_restart_bit_clears_itself() -> None:
    chip = FakePCA9685()
    chip.write(bytes([FakePCA9685.MODE1, FakePCA9685.RESTART | FakePCA9685.AI]))
    assert chip.registers[FakePCA9685.MODE1] == FakePCA9685.AI
