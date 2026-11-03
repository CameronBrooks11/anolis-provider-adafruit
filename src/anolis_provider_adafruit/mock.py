"""A fake I2C bus for mock mode, CI and tests.

It implements the bus interface the Adafruit drivers call (busio.I2C: try_lock,
unlock, writeto, readfrom_into, writeto_then_readfrom, scan) and puts a register
model of each chip behind it. The real drivers run unchanged against it, so mock
mode exercises the same driver code as the hardware does, from the first
register read on.
"""

from __future__ import annotations

import struct
from collections.abc import Mapping
from typing import Protocol


class FakeChip(Protocol):
    def write(self, data: bytes) -> None: ...
    def read(self, length: int) -> bytes: ...


class RegisterChip:
    """A chip with an 8-bit register pointer: a write sets the pointer and
    writes any following bytes from it; a read returns bytes from the pointer.
    The pointer advances with each byte, as on most I2C register chips."""

    def __init__(self) -> None:
        self.registers = bytearray(256)
        self._pointer = 0

    def write(self, data: bytes) -> None:
        if not data:
            return
        self._pointer = data[0]
        for byte in data[1:]:
            self.on_write(self._pointer, byte)
            self._pointer = self.next_register(self._pointer)

    def read(self, length: int) -> bytes:
        out = bytearray()
        for _ in range(length):
            out.append(self.registers[self._pointer])
            self._pointer = self.next_register(self._pointer)
        return bytes(out)

    def next_register(self, register: int) -> int:
        """Where the pointer goes after a byte is transferred."""
        return (register + 1) & 0xFF

    def on_write(self, register: int, value: int) -> None:
        self.registers[register] = value


class FakeBME280(RegisterChip):
    """A BME280 holding the calibration and raw readings of the Bosch datasheet's
    worked example (section 8.1): 25.08 C and 1006.53 hPa through the driver's
    compensation. The humidity calibration is a typical part's, giving about 45 %."""

    CHIP_ID = 0x60

    def __init__(self) -> None:
        super().__init__()
        r = self.registers
        r[0xD0] = self.CHIP_ID
        # dig_T1..T3, dig_P1..P9 from 0x88, little-endian.
        r[0x88:0xA0] = struct.pack(
            "<HhhHhhhhhhhh", 27504, 26435, -1000, 36477, -10685, 3024, 2855, 140, -7, 15500, -14600, 6000
        )
        r[0xA1] = 75  # dig_H1
        # dig_H2 = 362, dig_H3 = 0, dig_H4 = 313, dig_H5 = 50, dig_H6 = 30, packed as the chip packs them.
        r[0xE1:0xE8] = struct.pack("<hBbBbb", 362, 0, 313 >> 4, ((50 & 0xF) << 4) | (313 & 0xF), 50 >> 4, 30)
        self.set_raw(temperature=519888, pressure=415148, humidity=28000)

    def set_raw(self, *, temperature: int, pressure: int, humidity: int) -> None:
        """Raw ADC values: 20-bit temperature and pressure, 16-bit humidity."""
        self.registers[0xF7:0xFA] = (pressure << 4).to_bytes(3, "big")
        self.registers[0xFA:0xFD] = (temperature << 4).to_bytes(3, "big")
        self.registers[0xFD:0xFF] = humidity.to_bytes(2, "big")

    def on_write(self, register: int, value: int) -> None:
        if register == 0xE0:  # soft reset: no state to clear in the model
            return
        super().on_write(register, value)
        # The status register (0xF3) stays 0: a measurement is always complete.


class FakePCA9685(RegisterChip):
    """A PCA9685 16-channel PWM controller, at its power-on register values
    (NXP datasheet rev. 4, section 7.3): asleep, every output fully off.

    Modelled because a driver can get each of them wrong: the pointer advances
    only with MODE1.AI set, PRE_SCALE takes a write only while MODE1.SLEEP is
    set, and RESTART clears itself."""

    MODE1, MODE2, LED0, PRE_SCALE = 0x00, 0x01, 0x06, 0xFE
    AI, SLEEP, RESTART = 0x20, 0x10, 0x80

    def __init__(self) -> None:
        super().__init__()
        r = self.registers
        r[self.MODE1] = 0x11  # SLEEP | ALLCALL
        r[self.MODE2] = 0x04  # OUTDRV
        for channel in range(16):
            r[self.LED0 + 4 * channel + 3] = 0x10  # LEDn_OFF_H: full off
        r[self.PRE_SCALE] = 0x1E  # 200 Hz

    def next_register(self, register: int) -> int:
        if self.registers[self.MODE1] & self.AI:
            return super().next_register(register)
        return register

    def on_write(self, register: int, value: int) -> None:
        if register == self.PRE_SCALE and not self.registers[self.MODE1] & self.SLEEP:
            return
        if register == self.MODE1:
            value &= ~self.RESTART
        super().on_write(register, value)

    def duty(self, channel: int) -> tuple[int, int]:
        """A channel's (LEDn_ON, LEDn_OFF) words, as the driver writes them."""
        base = self.LED0 + 4 * channel
        on, off = struct.unpack("<HH", self.registers[base : base + 4])
        return on, off


class FakeI2C:
    """A bus with fake chips at fixed addresses. An address with no chip raises
    OSError, as Linux reports a NACK, so a driver's probe fails as on hardware."""

    def __init__(self, chips: Mapping[int, FakeChip]) -> None:
        self.chips = dict(chips)
        self._locked = False
        self.fail = False  # set to make every transfer fail, as a disconnected bus does

    def _chip(self, address: int) -> FakeChip:
        if self.fail:
            raise OSError(5, "Input/output error")
        chip = self.chips.get(address)
        if chip is None:
            raise OSError(121, "Remote I/O error")
        return chip

    def try_lock(self) -> bool:
        if self._locked:
            return False
        self._locked = True
        return True

    def unlock(self) -> None:
        self._locked = False

    def scan(self) -> list[int]:
        return sorted(self.chips)

    def writeto(self, address: int, buffer: bytes, *, start: int = 0, end: int | None = None) -> None:
        self._chip(address).write(bytes(buffer[start:end]))

    def readfrom_into(self, address: int, buffer: bytearray, *, start: int = 0, end: int | None = None) -> None:
        end = len(buffer) if end is None else end
        buffer[start:end] = self._chip(address).read(end - start)

    def writeto_then_readfrom(
        self,
        address: int,
        buffer_out: bytes,
        buffer_in: bytearray,
        *,
        out_start: int = 0,
        out_end: int | None = None,
        in_start: int = 0,
        in_end: int | None = None,
    ) -> None:
        self.writeto(address, buffer_out, start=out_start, end=out_end)
        self.readfrom_into(address, buffer_in, start=in_start, end=in_end)

    def deinit(self) -> None:
        pass
