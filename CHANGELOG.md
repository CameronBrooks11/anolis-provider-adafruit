# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- The provider, built on the Python provider SDK and Adafruit's CircuitPython
  drivers, with the BME280 (temperature, humidity, pressure, altitude) as its
  first board.
- Mock mode: a simulated I2C bus with a register model of each board, which
  Adafruit's driver runs against unchanged.
- A frozen single-file release binary for x86_64 and arm64, laid out for anolis
  `install.sh`, with the config schema assets the Workbench reads.
- `scripts/cold_start.py`, which measures start-up time on the target.
