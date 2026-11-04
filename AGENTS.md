# AGENTS.md: anolis-provider-adafruit

Per-repo conventions for coding agents.

## Build / test

- `just setup`, `just check` (ruff format, ruff lint, `mypy --strict`), `just test` (pytest), `just freeze` (PyInstaller).
- `just check && just test` is what CI runs, plus the frozen binary on x86_64 and arm64 under the harness. The required
  status check is the **`ok`** job.
- `tests/test_conformance.py` runs the anolis-protocol conformance harness against the provider in mock mode. A skip
  fails it unless listed in `EXPECTED_SKIPS` with a reason. `ANOLIS_PROVIDER_BIN` points it at another build.

## Design rules

- **The SDK on top of the vendor's driver.** A board module declares the device type and calls Adafruit's driver. No
  register-level code outside `mock.py`; if a driver is missing or broken, fix it upstream or write a driver as its own
  package, not inside a board module.
- **Mock mode runs the real driver.** The fake bus emulates the chip's registers; never stub the driver itself.
- **Only a failed I2C transfer or `NotAnswering` means a board is unreachable.** A transfer error is an `OSError`
  whose errno is in `_BUS_ERRNOS` (`provider.py`); `NotAnswering` (`devices/base.py`) is what a board module raises
  when the board at the address is absent, is a different chip, or has not finished starting, wrapping only the
  driver exceptions that mean that. The provider treats those two alike in `_connect`, `read()` and `call()`: the
  board is marked lost, reported UNREACHABLE and retried. Any other exception is a provider fault and must surface
  as one.
- **Outputs: safe at connect, zero-rung drivable, read back from the chip.** See `docs/adding-a-board.md`, "Boards with
  outputs".
- **Only what the config names.** The provider opens one I2C bus and the configured addresses. It does not scan, and
  does not expose GPIO or SPI.

## Repo-specific gotchas

- Blinka installs `board_imports.json` and `microcontroller_imports.json` at the top of site-packages and picks its
  platform module at run time. The PyInstaller spec collects both; a freeze that misses one passes `--version` and
  fails on the first driver construction. Only the harness against the frozen binary catches it.
- `anolis-provider-sdk` is pinned by commit in `pyproject.toml` until it is published.
- Release binaries link the build runner's glibc (Ubuntu 24.04: 2.39).
- When running a mutation check, disable bytecode (`PYTHONDONTWRITEBYTECODE=1`).
