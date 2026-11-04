# Adding a board

A board is one module in `src/anolis_provider_adafruit/devices/`, registered in
`devices/__init__.py` under the `type` a config names it with. It holds:

- **The declaration**: a `DeviceType` listing the board's signals and functions
  (see the SDK's guide to writing a provider). The SDK derives function ids,
  default reads and argument validation from it.
- **A `DeviceDriver` subclass** that constructs Adafruit's driver for the board
  and maps signals and function calls onto it. Keep it thin: the driver does the
  work.
- **`addresses`**: the I2C addresses the board can be strapped to, factory
  default first. The config schema accepts only these.
- **`fake()`**: a register model of the chip for mock mode, in `mock.py`.
- **`connect_first`**, rarely: set it on a board that answers another board's
  address until it is set up (the PCA9685's All Call address is the SHTC3's),
  and the provider connects it before the others.

## When the board does not answer

The provider reports a board UNREACHABLE, and tries it again on the next read
or call, for exactly two exceptions: an `OSError` from a failed I2C transfer
(an errno in `_BUS_ERRNOS` in `provider.py`), and `NotAnswering` from
`devices/base.py`. Raise `NotAnswering`, with a message saying what was found,
when the board at the address is absent, is a different chip, or has not
finished starting, whether at connect or when the board sets the chip up again
during a read or call. Where the driver signals one of those by raising, catch
that exception narrowly and raise `NotAnswering` from it: the probe's
`ValueError` for an empty address (`nothing_at` in `devices/base.py` tells it
apart) and the driver's own chip-id `RuntimeError`. Every other exception, a
`ValueError` or `RuntimeError` included, is a fault in the provider and is
reported as one.

## Settings

A function whose category is `CONFIG`, that is idempotent and that takes at
least one argument is a setting, such as the BME280's
`set_sea_level_pressure`. The provider records the latest arguments of each
setting called on a board and, when it reconnects that board after losing it,
calls them again on the new driver, in the order they were last set: a new
driver starts from its defaults, and the chip may have lost power with the
cable. Declare a function that way only if calling it again with the same
arguments puts the setting back. A setting that fails to apply again leaves the
board lost, like any failed transfer, and the next read or call retries it.

## The fake chip

Mock mode runs Adafruit's real driver against `FakeI2C`, so the fake has to
behave like the chip at the register level: the id register, calibration data,
and raw readings the driver converts. Take the values from the datasheet's
worked example where it has one, and test that the driver's output matches the
datasheet (see `tests/test_mock.py`). A fake the driver accepts is evidence the
model is right; one written to match the provider's own code is not.

## Boards with outputs

A board that drives anything (a motor, a relay, a heater) has three more rules,
from the runtime's safety contract:

- **Drive the safe state when the board connects.** The constructor runs at
  start-up and again when a lost board answers, and leaves every output safe.
  Name the safe state in the module docstring.
- **Notice a chip that restarted on its own.** A brown-out between two polls
  fails no transfer, so the provider never sees the board lost. Check on every
  read and call for the chip's power-on state (the Motor HAT checks the
  PCA9685's MODE1) and run the connect sequence again when you find it.
- **Give every `ACTUATE` function a required numeric argument for which 0 is
  safe and in range.** The runtime's zero rung (`safety.safe_state.zero_is_safe`)
  calls each actuating function with its required numeric arguments set to 0,
  and counts any function it cannot do that for as a failure, so the software
  stop then reports `safe_state_achieved: false`. That rules out a function with
  no arguments, a required boolean or string, and a channel-index argument (0 is
  not a channel). Use one function per output instead, as `motor_hat` does.
- **Read outputs back from the chip,** not from what the driver was last told,
  so a signal shows what the hardware is doing. A register pattern the provider
  never writes reads with quality `UNKNOWN`.

Say in the module whether the board has a command watchdog. Most Adafruit
boards do not, and then the outputs hold their last value if the provider stops.

## Before opening a PR

- Add the board to `config/conformance.yaml`, so the harness covers it.
- `just check && just test`.
- `just freeze`, then run the harness against the frozen binary:
  `ANOLIS_PROVIDER_BIN=$PWD/dist/anolis-provider-adafruit uv run pytest tests/test_conformance.py`.
  A driver may load data files or modules that only the frozen build misses.
- Read the board on real hardware, and say in the PR which board and which
  readings you checked.
