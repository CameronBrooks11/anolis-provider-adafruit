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

## The fake chip

Mock mode runs Adafruit's real driver against `FakeI2C`, so the fake has to
behave like the chip at the register level: the id register, calibration data,
and raw readings the driver converts. Take the values from the datasheet's
worked example where it has one, and test that the driver's output matches the
datasheet (see `tests/test_mock.py`). A fake the driver accepts is evidence the
model is right; one written to match the provider's own code is not.

## Before opening a PR

- Add the board to `config/conformance.yaml`, so the harness covers it.
- `just check && just test`.
- `just freeze`, then run the harness against the frozen binary:
  `ANOLIS_PROVIDER_BIN=$PWD/dist/anolis-provider-adafruit uv run pytest tests/test_conformance.py`.
  A driver may load data files or modules that only the frozen build misses.
- Read the board on real hardware, and say in the PR which board and which
  readings you checked.
