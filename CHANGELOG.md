# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- The Adafruit DC & Stepper Motor HAT (`motor_hat`): four DC motor terminals,
  each set by `set_motor<n>_throttle` and read back from the board's PWM
  controller. The board brakes every terminal when it connects, and throttle 0
  is its safe state, so the runtime's `zero_is_safe` rung can stop it.
- The Sensirion SHT40/41/45 (`sht4x`) and SHTC3 (`shtc3`): temperature and
  humidity. A chip that does not answer as the sensor is refused, and a
  reading that fails its CRC reports the board unavailable and is retried,
  where the SHTC3 driver would return no value without an error.
- Mock mode models the PCA9685 PWM controller, including auto-increment,
  sleep-only prescale writes and the self-clearing restart bit, and the
  SHT4x and SHTC3, including the SHTC3's sleep between readings.

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
