"""The Motor HAT in mock mode: the safe state at connect, throttle in both
directions, read-back from the PWM controller, and fitness for the runtime's
zero rung. Register state is checked on the fake chip itself, so the oracle is
independent of the driver's read path."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from anolis_provider_sdk import Category, DeviceState, ProviderError, Quality, Reading, StatusCode, ValueType
from anolis_provider_sdk.cli import ConfigError, load_config

from anolis_provider_adafruit.devices.motor_hat import CHANNELS, TYPE, MotorHat, throttle_from_duty
from anolis_provider_adafruit.mock import FakeI2C, FakePCA9685
from anolis_provider_adafruit.provider import AdafruitProvider

FULL_ON = (0x1000, 0)  # LEDn_ON full-on bit
FULL_OFF = (0, 0x1000)  # LEDn_OFF full-off bit
SIGNALS = [f"motor{m}_throttle" for m in CHANNELS]


def started(*devices: dict[str, Any]) -> AdafruitProvider:
    provider = AdafruitProvider({"mock": True, "devices": list(devices) or [{"id": "m", "type": "motor_hat"}]})
    provider.start(0.0)
    return provider


def chip(provider: AdafruitProvider, address: int = 0x60) -> FakePCA9685:
    fake = provider._bus
    assert isinstance(fake, FakeI2C)
    pca = fake.chips[address]
    assert isinstance(pca, FakePCA9685)
    return pca


def throttle(provider: AdafruitProvider, motor: int, value: float) -> None:
    device = provider.devices()[0]
    fn = device.type.function_by_name(f"set_motor{motor}_throttle")
    assert fn
    provider.call(device, fn, {"throttle": value})


def test_connecting_brakes_every_terminal() -> None:
    pca = chip(started())
    for enable, forward, reverse in CHANNELS.values():
        assert pca.duty(enable) == FULL_ON
        assert pca.duty(forward) == FULL_ON
        assert pca.duty(reverse) == FULL_ON


def test_connecting_wakes_the_controller_at_1600_hz_with_auto_increment() -> None:
    pca = chip(started())
    mode1 = pca.registers[FakePCA9685.MODE1]
    assert not mode1 & FakePCA9685.SLEEP
    assert mode1 & FakePCA9685.AI
    assert pca.registers[FakePCA9685.PRE_SCALE] == round(25_000_000 / (4096 * 1600)) - 1


def test_forward_and_reverse_drive_one_input_each() -> None:
    p = started()
    pca = chip(p)
    _, forward, reverse = CHANNELS[1]
    throttle(p, 1, 0.5)
    assert pca.duty(forward) == (0, 0x7FFF >> 4)
    assert pca.duty(reverse) == FULL_OFF
    throttle(p, 1, -1.0)
    assert pca.duty(forward) == FULL_OFF
    assert pca.duty(reverse) == FULL_ON
    throttle(p, 1, 0.0)
    assert pca.duty(forward) == pca.duty(reverse) == FULL_ON


@pytest.mark.parametrize(
    ("motor", "enable", "forward", "reverse"),
    # Written out from adafruit_motorkit 1.6.21 (MotorKit.motor1 .. motor4), not
    # read from CHANNELS, so a wrong map fails here.
    [(1, 8, 9, 10), (2, 13, 11, 12), (3, 2, 3, 4), (4, 7, 5, 6)],
)
def test_full_forward_drives_the_board_channels_motorkit_uses(
    motor: int, enable: int, forward: int, reverse: int
) -> None:
    p = started()
    pca = chip(p)
    throttle(p, motor, 1.0)
    assert (pca.duty(enable), pca.duty(forward), pca.duty(reverse)) == (FULL_ON, FULL_ON, FULL_OFF)


def test_each_function_drives_only_its_own_terminal() -> None:
    p = started()
    pca = chip(p)
    throttle(p, 3, 1.0)
    _, forward, reverse = CHANNELS[3]
    assert pca.duty(forward) == FULL_ON and pca.duty(reverse) == FULL_OFF
    for motor in (1, 2, 4):
        _, f, r = CHANNELS[motor]
        assert pca.duty(f) == pca.duty(r) == FULL_ON


def test_throttle_is_read_back_from_the_controller() -> None:
    p = started()
    d = p.devices()[0]
    throttle(p, 2, 0.5)
    throttle(p, 4, -0.25)
    # The controller holds 12 bits: 0.5 is stored as 2047/4096.
    assert p.read(d, SIGNALS) == {
        "motor1_throttle": 0.0,
        "motor2_throttle": pytest.approx(0.5, abs=1 / 4096),
        "motor3_throttle": 0.0,
        "motor4_throttle": pytest.approx(-0.25, abs=1 / 4096),
    }
    # Written behind the driver's back: the read reports the chip, not the last command.
    _, forward, _ = CHANNELS[2]
    base = FakePCA9685.LED0 + 4 * forward
    chip(p).registers[base : base + 4] = bytes([0x00, 0x10, 0x00, 0x00])  # full on
    assert p.read(d, ["motor2_throttle"])["motor2_throttle"] == 1.0


def test_a_pattern_the_provider_never_writes_reads_as_unknown() -> None:
    p = started()
    _, forward, reverse = CHANNELS[1]
    for channel in (forward, reverse):  # both inputs at half: not a state this provider sets
        base = FakePCA9685.LED0 + 4 * channel
        chip(p).registers[base : base + 4] = bytes([0x00, 0x00, 0xFF, 0x07])
    value = p.read(p.devices()[0], ["motor1_throttle"])["motor1_throttle"]
    assert isinstance(value, Reading)
    assert value.quality is Quality.UNKNOWN


@pytest.mark.parametrize(
    ("enable", "forward", "reverse", "expected"),
    [
        (0, 0, 0, 0.0),  # power-on: bridge disabled
        (0, 0xFFFF, 0, 0.0),  # disabled wins over the inputs
        (0xFFFF, 0, 0, 0.0),  # released
        (0xFFFF, 0xFFFF, 0xFFFF, 0.0),  # braking
        (0xFFFF, 0xFFFF, 0, 1.0),
        (0xFFFF, 0, 0xFFFF, -1.0),
        (0xFFFF, 0x8000, 0, 0x8000 / 0xFFFF),
        (0x8000, 0xFFFF, 0, None),  # a half-enabled bridge
        (0xFFFF, 0x8000, 0x8000, None),
        (0xFFFF, 0xFFFF, 0x8000, None),  # slow decay, which nothing here writes
    ],
)
def test_throttle_from_duty(enable: int, forward: int, reverse: int, expected: float | None) -> None:
    assert throttle_from_duty(enable, forward, reverse) == expected


def test_every_actuating_function_can_be_driven_by_the_zero_rung() -> None:
    # The runtime's zero rung (safe_state.cpp build_zero_args) refuses a function
    # with no required numeric argument, which would leave the software stop
    # reporting safe_state_achieved: false.
    numeric = {ValueType.DOUBLE, ValueType.INT64, ValueType.UINT64}
    actuating = [f for f in TYPE.functions if f.category is Category.ACTUATE]
    assert len(actuating) == 4
    for fn in actuating:
        required = [a for a in fn.args if a.required]
        assert required, fn.name
        assert all(a.type in numeric for a in required), fn.name
        assert all(a.min is not None and a.max is not None and a.min <= 0 <= a.max for a in required), fn.name


def test_zero_throttle_on_every_function_brakes_everything() -> None:
    p = started()
    pca = chip(p)
    for motor in CHANNELS:
        throttle(p, motor, 0.7)
    for motor in CHANNELS:  # what the zero rung sends
        throttle(p, motor, 0.0)
    for _, forward, reverse in CHANNELS.values():
        assert pca.duty(forward) == pca.duty(reverse) == FULL_ON


def test_a_board_that_answers_again_comes_back_braked() -> None:
    p = started()
    d = p.devices()[0]
    throttle(p, 1, 0.8)
    fake = p._bus
    assert isinstance(fake, FakeI2C)
    fake.fail = True
    with pytest.raises(ProviderError) as err:
        p.read(d, SIGNALS)
    assert err.value.code is StatusCode.UNAVAILABLE
    health = p.device_health(d)
    assert health and health.state is DeviceState.UNREACHABLE
    fake.fail = False
    assert p.read(d, ["motor1_throttle"]) == {"motor1_throttle": 0.0}


def test_a_hat_shares_the_bus_with_a_sensor() -> None:
    p = started({"id": "m", "type": "motor_hat", "address": 0x61}, {"id": "env", "type": "bme280"})
    assert [(d.id, d.address) for d in p.devices()] == [("m", "i2c-1:0x61"), ("env", "i2c-1:0x77")]
    throttle(p, 1, 1.0)
    assert p.read(p.devices()[1], ["temperature"])["temperature"] == pytest.approx(25.08, abs=0.01)


def test_addresses_cover_the_jumper_range_except_all_call() -> None:
    assert MotorHat.addresses[0] == 0x60
    assert set(MotorHat.addresses) == set(range(0x60, 0x80)) - {0x70}


@pytest.mark.parametrize(
    "body",
    [
        "devices: [{id: m, type: motor_hat, address: 0x70}]",
        "devices: [{id: m, type: motor_hat, address: 0x5F}]",
    ],
)
def test_the_schema_rejects_an_address_the_hat_cannot_take(tmp_path: Path, body: str) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(body)
    with pytest.raises(ConfigError):
        load_config(AdafruitProvider, str(path))


def test_a_hat_and_a_sensor_on_one_address_are_refused() -> None:
    with pytest.raises(ValueError, match="0x77"):
        AdafruitProvider(
            {
                "mock": True,
                "devices": [{"id": "env", "type": "bme280"}, {"id": "m", "type": "motor_hat", "address": 0x77}],
            }
        )


def level(pca: FakePCA9685, channel: int) -> float:
    """The fraction of each PWM period a channel is high, from its registers."""
    on, off = pca.duty(channel)
    if on & 0x1000:
        return 1.0
    if off & 0x1000:
        return 0.0
    assert on == 0, "every channel this provider writes starts its period high"
    return off / 4096


def drive(pca: FakePCA9685, motor: int) -> float:
    """What the TB6612 drives a terminal at, from -1 (full reverse) to 1.

    Every channel goes high at the start of the period, so each input is high
    from 0 until its level. The bridge drives forward while the PWM input and
    the forward input are high and the reverse input is low, and reverse the
    other way about. Any other combination is short brake (an input pair H/H,
    or the PWM input low) or off (both inputs low): no drive."""
    enable, forward, reverse = (level(pca, c) for c in CHANNELS[motor])
    return max(0.0, min(enable, forward) - reverse) - max(0.0, min(enable, reverse) - forward)


RUNAWAY_CASES = [(0.0, 0.1), (0.0, -0.1), (0.3, 0.0), (-0.3, 0.0), (0.5, -0.5), (-0.5, 0.5)]
# The same direction is written without the brake step; it must be just as safe.
SAME_DIRECTION_CASES = [(0.3, 0.5), (0.5, 0.3), (-0.3, -0.5), (0.4, 0.4), (0.0, 0.0)]


@pytest.mark.parametrize(("start", "target"), RUNAWAY_CASES + SAME_DIRECTION_CASES)
def test_a_write_that_fails_partway_never_leaves_the_bridge_driving_harder_or_backwards(
    start: float, target: float
) -> None:
    def at_start() -> tuple[AdafruitProvider, FakeI2C, float]:
        p = started()
        throttle(p, 1, start)
        fake = p._bus
        assert isinstance(fake, FakeI2C)
        return p, fake, drive(chip(p), 1)

    p, fake, start_drive = at_start()
    before = fake.writes
    throttle(p, 1, target)
    writes = fake.writes - before
    target_drive = drive(chip(p), 1)
    assert target_drive == pytest.approx(target, abs=1 / 4096)
    assert writes >= 2

    for k in range(writes):
        p, fake, _ = at_start()
        fake.fail_write = fake.writes + k
        with pytest.raises(ProviderError) as err:
            throttle(p, 1, target)
        assert err.value.code is StatusCode.UNAVAILABLE
        left = drive(chip(p), 1)
        allowed = [0.0, start_drive, target_drive]
        assert any(left == pytest.approx(a, abs=1 / 4096) for a in allowed), (
            f"{start} -> {target}, write {k} of {writes} failed: bridge left driving at {left:+.4f}"
        )
