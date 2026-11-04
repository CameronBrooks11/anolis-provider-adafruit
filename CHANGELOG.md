# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- The Adafruit DC & Stepper Motor HAT (`motor_hat`): four DC motor terminals,
  each set by `set_motor<n>_throttle` and read back from the board's PWM
  controller. The board brakes every terminal when it connects, and throttle 0
  is its safe state, so the runtime's `zero_is_safe` rung can stop it. A
  throttle change that brakes, starts or reverses a motor brakes the bridge
  while its inputs change, so a transfer that fails partway never leaves it
  driving harder than the old and new throttle, or the other way. A PCA9685
  that restarted on its own (it comes back asleep) is found on the next read
  or call and set up and braked again, so a command after it takes effect.
  Every Motor HAT connects before the other boards, so its reset turns off
  the PCA9685's All Call address, `0x70`, before an SHTC3 there is opened.
- The Sensirion SHT40/41/45 (`sht4x`) and SHTC3 (`shtc3`): temperature and
  humidity. A chip that does not answer as the sensor is refused, and a
  reading that fails its CRC reports the board unavailable and is retried,
  where the SHTC3 driver would return no value without an error.
- Mock mode models the PCA9685 PWM controller, including auto-increment,
  sleep-only prescale writes and the self-clearing restart bit, and the
  SHT4x and SHTC3, including the SHTC3's sleep between readings. The BME280
  model now starts asleep with its data registers at their reset values, takes
  the datasheet's measurement time for its first measurement in normal mode,
  and can be power-cycled, and the PCA9685 model can be power-cycled and
  answers its All Call address.

### Fixed

- A BME280 that restarted on its own (a brown-out between two reads) is set up
  again on the next read, keeping its sea-level pressure. Before, the driver
  kept the chip's old mode in Python, and the provider reported the reset-value
  registers of the sleeping chip as good readings until it restarted. Every
  connect now waits out the first measurement, so the first read after it is
  not of those reset values either.
- A board is reported unreachable only when it is not answering: a failed I2C
  transfer, or the board module finding nothing at the address, another chip,
  or a chip still starting. Any other error from a driver, such as a missing
  platform library or a setting the chip cannot take, is now a provider fault
  instead of an unreachable board. The same holds during a read or call, so a
  BME280 that comes back as another chip is unreachable rather than an
  internal error.
- When the I2C bus does not open, every device reports `UNREACHABLE` with the
  bus error and the provider reports a fault, where every device used to
  report healthy.
- Settings survive a reconnect: the latest value of each setting function
  (category `CONFIG`, idempotent, with an argument) is applied again when a
  lost board answers, so the BME280's sea-level pressure no longer resets to
  1013.25 hPa after a cable is reseated.
- The BME280 and the Motor HAT load on a Raspberry Pi. Blinka needs `gpiod`
  and the Pi PWM library there, which it does not declare and the drivers
  import for type hints, so on a Pi 4 or Pi 5 neither driver loaded. The
  provider now depends on both on Linux, and the release binary bundles them.
- `scripts/cold_start.py` exits 1 with the status code and message when a Hello
  or WaitReady reply is not OK, where it used to time any reply as a success.

## [0.1.0] - 2026-11-03

### Added

- The provider, built on the Python provider SDK and Adafruit's CircuitPython
  drivers, with the BME280 (temperature, humidity, pressure, altitude) as its
  first board.
- Mock mode: a simulated I2C bus with a register model of each board, which
  Adafruit's driver runs against unchanged.
- A frozen single-file release binary for x86_64 and arm64, laid out for anolis
  `install.sh`, with the config schema assets the Workbench reads.
- `scripts/cold_start.py`, which measures start-up time on the target.

[Unreleased]: https://github.com/CameronBrooks11/anolis-provider-adafruit/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/CameronBrooks11/anolis-provider-adafruit/releases/tag/v0.1.0
