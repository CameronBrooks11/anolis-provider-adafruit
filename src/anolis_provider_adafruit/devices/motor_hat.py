"""Adafruit DC & Stepper Motor HAT for Raspberry Pi: four DC motor terminals,
M1 to M4 (I2C 0x60 by default; 0x60 to 0x7F by solder jumper).

Drivers: adafruit-circuitpython-pca9685 for the board's PWM controller and
adafruit-circuitpython-motor for each DC motor. The channel map is the board's
wiring, as adafruit-circuitpython-motorkit declares it. MotorKit itself is not
used because it keeps the PWM controller private, and the throttle signals read
the controller's registers back rather than what was last commanded.

Safe state: throttle 0, which brakes (both bridge inputs high). The board drives
all four terminals there when it connects, at start-up and when it answers again
after being lost, and again whenever it is found to have restarted on its own.
Every motor function has one required numeric argument, so the runtime's zero
rung (`safety.safe_state.zero_is_safe`) drives each one to 0.

A PCA9685 that restarted on its own (a glitch on the HAT's logic supply) comes
back asleep, with every output off and auto-increment and All Call as at power
on. The board checks MODE1 on every read and call and connects again when it is
not as the board left it: awake, auto-incrementing, All Call off.

All Call: at power on a PCA9685 also answers 0x70, the SHTC3's fixed address,
so until the provider has reset it, traffic for an SHTC3 reaches the HAT too.
The provider connects every Motor HAT before the other boards, and the reset
at connect turns All Call off. A PCA9685 the provider does not initialise keeps
answering 0x70, so an SHTC3 cannot share a bus with one.

A throttle change never passes through, or stops in, a state that drives
harder than both the old and the new throttle, or the other way. adafruit_motor
sets a terminal's two bridge inputs in two separate I2C writes, and the state
between them can be full forward on the way from forward to brake, or nearly
full reverse on the way from brake to forward. So a change that brakes, starts
or reverses first takes the bridge's PWM input to 0, which the TB6612 treats as
short brake whatever the two inputs are (or off, with both low), then sets the
inputs, then drives the PWM input full on again. A transfer that fails at any
one of those writes leaves the bridge braked, or at the old or the new
throttle. A change in the same direction writes the inputs directly: only the
input carrying the PWM changes, so there is no state in between.

The board has no command watchdog, so the provider's stop() is the only thing
that stops the motors when the runtime goes away: it brakes every terminal
when the session ends on stdin EOF (the runtime exited, crashed or closed the
pipe), a malformed frame, a broken pipe, an error in the serving loop, or
SIGTERM. A SIGKILL or a crash of the provider's Python process skips it, and
the motors keep their last throttle until the board loses power.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from anolis_provider_sdk import Arg, Category, DeviceType, Function, Quality, Reading, Signal, ValueType

from ..mock import FakePCA9685
from .base import DeviceDriver, NotAnswering, nothing_at

log = logging.getLogger(__name__)

# PCA9685 channels per terminal: (TB6612 PWM enable, forward input, reverse input).
# From adafruit_motorkit.MotorKit.motor1 .. motor4.
CHANNELS = {1: (8, 9, 10), 2: (13, 11, 12), 3: (2, 3, 4), 4: (7, 5, 6)}

PWM_FREQUENCY_HZ = 1600.0  # MotorKit's default
FULL = 0xFFFF
# MODE1 bits (PCA9685 datasheet rev. 4, section 7.3.1).
MODE1_AI, MODE1_SLEEP, MODE1_ALLCALL = 0x20, 0x10, 0x01


def _throttle_function(motor: int) -> Function:
    return Function(
        f"set_motor{motor}_throttle",
        description=f"Drive motor terminal M{motor}. 0 brakes; the sign sets the direction.",
        args=(
            Arg(
                "throttle",
                ValueType.DOUBLE,
                min=-1.0,
                max=1.0,
                description="Fraction of the motor supply: -1 full reverse, 0 brake, 1 full forward",
            ),
        ),
        category=Category.ACTUATE,
        is_idempotent=True,
    )


TYPE = DeviceType(
    id="motor_hat",
    signals=tuple(
        Signal(
            f"motor{m}_throttle",
            ValueType.DOUBLE,
            description=(
                f"M{m} throttle read back from the PWM controller: -1 to 1, 0 when braking, released or disabled"
            ),
        )
        for m in CHANNELS
    ),
    functions=tuple(_throttle_function(m) for m in CHANNELS),
)


def throttle_from_duty(enable: int, forward: int, reverse: int) -> float | None:
    """The throttle a terminal's three duty cycles mean, or None for a pattern
    this provider never writes. 16-bit duty cycles, as the PCA9685 driver reads
    them back (12 bits of resolution)."""
    if enable == 0:
        return 0.0  # bridge disabled, the power-on state
    if enable != FULL:
        return None
    if forward == reverse and forward in (0, FULL):
        return 0.0  # released (both off) or braking (both full on)
    if reverse == 0:
        return forward / FULL
    if forward == 0:
        return -reverse / FULL
    return None


class MotorHat(DeviceDriver):
    type = TYPE
    addresses = tuple(a for a in range(0x60, 0x80) if a != 0x70)  # 0x70 is the PCA9685 All Call address

    connect_first = True  # its reset turns off All Call, which answers the SHTC3's address

    def __init__(self, i2c: Any, address: int) -> None:
        from adafruit_pca9685 import PCA9685

        self._address = address
        # The constructor resets the chip: MODE1 = 0, awake with All Call off.
        try:
            self._pca = PCA9685(i2c, address=address)
        except ValueError as err:
            if not nothing_at(err):
                raise
            raise NotAnswering(f"nothing answers at {address:#04x}") from err
        self._setup()

    def _setup(self) -> None:
        from adafruit_motor.motor import DCMotor

        # Also sets MODE1.AI, which every channel write after it depends on.
        self._pca.frequency = PWM_FREQUENCY_HZ
        self._motors: dict[int, Any] = {}
        for motor, (enable, forward, reverse) in CHANNELS.items():
            self._pca.channels[enable].duty_cycle = FULL
            dc = DCMotor(self._pca.channels[forward], self._pca.channels[reverse])
            dc.throttle = 0.0  # the safe state: brake
            self._motors[motor] = dc

    def _check_restarted(self) -> None:
        mode1 = self._pca.mode1_reg
        if mode1 & (MODE1_SLEEP | MODE1_ALLCALL) or not mode1 & MODE1_AI:
            log.warning("PCA9685 at %#04x restarted (MODE1 %#04x); braking its motors again", self._address, mode1)
            self._pca.reset()
            self._setup()

    @staticmethod
    def fake() -> FakePCA9685:
        return FakePCA9685()

    def read(self, signal_ids: list[str]) -> Mapping[str, Any]:
        self._check_restarted()
        out: dict[str, Any] = {}
        for sid in signal_ids:
            motor = int(sid.removeprefix("motor").removesuffix("_throttle"))
            enable, forward, reverse = (self._pca.channels[c].duty_cycle for c in CHANNELS[motor])
            value = throttle_from_duty(enable, forward, reverse)
            # A pattern nothing here wrote, such as another program's slow-decay PWM.
            out[sid] = Reading(0.0, Quality.UNKNOWN) if value is None else round(value, 4)
        return out

    def call(self, function: Function, args: Mapping[str, Any]) -> Mapping[str, Any] | None:
        self._check_restarted()
        motor = int(function.name.removeprefix("set_motor").removesuffix("_throttle"))
        self._set(motor, float(args["throttle"]))
        return None

    def stop(self) -> None:
        """Brake every terminal: the safe state the board takes at connect."""
        self._check_restarted()
        for motor in CHANNELS:
            self._set(motor, 0.0)

    def _set(self, motor: int, target: float) -> None:
        dc = self._motors[motor]
        start = dc.throttle
        if start == target or start * target > 0:
            dc.throttle = target
            return
        enable = self._pca.channels[CHANNELS[motor][0]]
        enable.duty_cycle = 0  # short brake while the inputs change
        dc.throttle = target
        enable.duty_cycle = FULL
