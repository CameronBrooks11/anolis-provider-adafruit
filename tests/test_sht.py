"""The SHT4x and SHTC3 boards against their sensor models: readings, the chips
they refuse, and readings that fail their CRC."""

from __future__ import annotations

import adafruit_sht4x
import adafruit_shtc3
import pytest
from anolis_provider_sdk import DeviceState, ProviderError

from anolis_provider_adafruit.devices.sht4x import SHT4x
from anolis_provider_adafruit.devices.shtc3 import SHTC3
from anolis_provider_adafruit.mock import FakeI2C, FakeSHT4x, FakeSHTC3, sensirion_crc
from anolis_provider_adafruit.provider import AdafruitProvider

SIGNALS = ["temperature", "relative_humidity"]


class Garbled:
    """Flips a bit in every reply, so each word fails its CRC, while ``on``."""

    on = False

    def read(self, length: int) -> bytes:
        out = super().read(length)  # type: ignore[misc]
        return bytes(b ^ 0x01 for b in out) if self.on else out


class GarbledSHT4x(Garbled, FakeSHT4x):
    pass


class GarbledSHTC3(Garbled, FakeSHTC3):
    pass


def provider(kind: str, chip: object | None = None) -> AdafruitProvider:
    p = AdafruitProvider({"mock": True, "devices": [{"id": "rh0", "type": kind}]})
    p.start(0.0)
    if chip is not None:
        bus = p._bus
        assert isinstance(bus, FakeI2C)
        bus.chips[{"sht4x": 0x44, "shtc3": 0x70}[kind]] = chip  # type: ignore[assignment]
    return p


@pytest.mark.parametrize("kind", ["sht4x", "shtc3"])
def test_readings_come_through(kind: str) -> None:
    p = provider(kind)
    d = p.devices()[0]
    bus = p._bus
    assert isinstance(bus, FakeI2C)
    chip = next(iter(bus.chips.values()))
    assert isinstance(chip, FakeSHT4x | FakeSHTC3)
    chip.set_measurement(temperature=31.25, humidity=62.5)
    assert p.read(d, SIGNALS) == {
        "temperature": pytest.approx(31.25, abs=0.01),
        "relative_humidity": pytest.approx(62.5, abs=0.01),
    }


def test_the_sht4x_driver_constructor_accepts_any_chip_that_acks() -> None:
    # Why the board reads the serial number: the driver only sends a soft reset.
    chip = GarbledSHT4x()
    chip.on = True
    adafruit_sht4x.SHT4x(FakeI2C({0x44: chip}), 0x44)


def test_an_sht4x_whose_serial_fails_its_crc_is_refused() -> None:
    chip = GarbledSHT4x()
    chip.on = True
    with pytest.raises(ValueError, match="serial number"):
        SHT4x(FakeI2C({0x44: chip}), 0x44)


def test_the_shtc3_driver_returns_none_for_a_reading_that_fails_its_crc() -> None:
    chip = GarbledSHTC3()
    sensor = adafruit_shtc3.SHTC3(FakeI2C({0x70: chip}))
    chip.on = True
    assert sensor.measurements == (None, None)


@pytest.mark.parametrize(("kind", "chip_class"), [("sht4x", GarbledSHT4x), ("shtc3", GarbledSHTC3)])
def test_a_reading_that_fails_its_crc_is_unavailable_and_the_board_recovers(
    kind: str, chip_class: type[Garbled]
) -> None:
    chip = chip_class()
    p = provider(kind, chip)
    p._slots["rh0"].driver = None  # connect again, to the chip given
    d = p.devices()[0]
    assert set(p.read(d, SIGNALS)) == set(SIGNALS)
    chip.on = True
    with pytest.raises(ProviderError, match="CRC"):
        p.read(d, SIGNALS)
    health = p.device_health(d)
    assert health and health.state is DeviceState.UNREACHABLE
    chip.on = False
    assert set(p.read(d, SIGNALS)) == set(SIGNALS)


def test_an_shtc3_left_asleep_by_an_earlier_session_is_woken() -> None:
    chip = FakeSHTC3()
    chip.asleep = True
    s = SHTC3(FakeI2C({0x70: chip}), 0x70)
    assert s.read(["temperature"])["temperature"] == pytest.approx(22.5, abs=0.02)  # the driver truncates to 0.01


def test_another_chip_at_0x70_is_not_taken_for_an_shtc3() -> None:
    class OtherId(FakeSHTC3):
        ID = 0x1234

    p = provider("shtc3", OtherId())
    p._slots["rh0"].driver = None
    with pytest.raises(ProviderError):
        p.read(p.devices()[0], SIGNALS)


def test_the_shtc3_sleeps_between_readings_and_answers_only_wakeup_asleep() -> None:
    chip = FakeSHTC3()
    s = SHTC3(FakeI2C({0x70: chip}), 0x70)
    s.read(SIGNALS)
    assert chip.asleep
    with pytest.raises(OSError):
        chip.write(FakeSHTC3.READ_ID.to_bytes(2, "big"))
    chip.write(FakeSHTC3.WAKEUP.to_bytes(2, "big"))
    assert not chip.asleep


def test_sensirion_crc_matches_the_datasheet_example() -> None:
    assert sensirion_crc(b"\xbe\xef") == 0x92
