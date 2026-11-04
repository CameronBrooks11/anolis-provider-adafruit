# anolis-provider-adafruit

An [Anolis](https://github.com/anolishq/anolis) device provider for Adafruit
hardware. It puts the
[Python provider SDK](https://github.com/anolishq/anolis-provider-sdk-python) on
top of Adafruit's own CircuitPython drivers, so each board is a short
declaration plus a call into the driver Adafruit already maintains. On Linux the
drivers run through [Adafruit Blinka](https://github.com/adafruit/Adafruit_Blinka),
which they depend on.

> **Status: v0.1.0.** It passes the anolis-protocol 1.10.0 conformance harness
> at level 2 in mock mode, from source and as the frozen release binary, on
> x86_64 and arm64. Not yet verified on a Raspberry Pi. v0.1.0 has the BME280
> only: the SHT4x, the SHTC3 and the Motor HAT are unreleased.

## Supported boards

| `type` | Board | Driver | Addresses | Since |
| --- | --- | --- | --- | --- |
| `bme280` | BME280 temperature, humidity and pressure (STEMMA QT) | `adafruit-circuitpython-bme280` | `0x77` (default), `0x76` | 0.1.0 |
| `sht4x` | SHT40, SHT41 or SHT45 temperature and humidity (STEMMA QT) | `adafruit-circuitpython-sht4x` | `0x44` | unreleased |
| `shtc3` | SHTC3 temperature and humidity (STEMMA QT) | `adafruit-circuitpython-shtc3` | `0x70` (fixed) | unreleased |
| `motor_hat` | DC & Stepper Motor HAT for Raspberry Pi: four DC motors | `adafruit-circuitpython-pca9685`, `adafruit-circuitpython-motor` | `0x60` (default) to `0x7F`, except `0x70` | unreleased |

All boards share one Linux I2C bus (`i2c_bus`, default 1: the Raspberry Pi
header, and any STEMMA QT or Qwiic adapter on it).

The SHTC3's fixed address, `0x70`, is also the All Call address of every
PCA9685 PWM controller (the Motor HAT's) until it is reset. The provider sets
up each `motor_hat` before the other boards, which turns All Call off, so an
SHTC3 and a configured Motor HAT share a bus. An SHTC3 cannot share a bus with
a PCA9685 the provider does not initialise. See
[docs/hardware.md](docs/hardware.md#the-sht4x-and-shtc3).

## Config

```yaml
i2c_bus: 1
devices:
  - id: env0
    type: bme280
    label: Bench air
  - id: env1
    type: bme280
    address: 0x76
  - id: drive0
    type: motor_hat   # unreleased: not accepted by 0.1.0
```

`mock: true` replaces the bus with a simulated one holding a register model of
each configured board. Adafruit's driver runs unchanged against it. The full
schema: `anolis-provider-adafruit --config-schema`.

A board that does not answer is listed anyway and reported `UNREACHABLE`; reads
and calls fail with `UNAVAILABLE` and retry the board each time, so reseating a
cable recovers it without a restart. Settings made since start-up, such as the
BME280's sea-level pressure, are applied again when it answers.

At start-up the provider runs the same checks as `--check-host`. If
`/dev/i2c-<n>` is missing, or the user it runs as cannot open it, it stays up
but not ready: it opens no bus, lists no devices, and `WaitReady` reports
`host_check=unmet` with the reason in `host_unmet`. If the device node is there
but the bus does not open, the provider reports a fault and every board
`UNREACHABLE` with the bus error.

## Motors and the software stop

`motor_hat` has one function per terminal, `set_motor<n>_throttle(throttle)`
with `throttle` from -1 to 1, where 0 brakes. The board brakes all four
terminals when it connects: at start-up, and when it answers again after being
lost. So a supervised restart of the provider stops the motors, whatever
`safety.on_startup` says; there is no setting to leave them running. Each
`motor<n>_throttle` signal is read back from the board's PWM controller.

Throttle 0 is the safe state, so the runtime's zero rung drives it:

```yaml
safety:
  safe_state:
    zero_is_safe: true
```

With that, the startup safe state and `POST /v0/estop` brake every motor.

When the provider exits, it brakes every terminal of every Motor HAT it has
connected, as at connect. That covers the runtime shutting down, crashing or
closing the provider's stdin, and the provider receiving `SIGTERM`. A board that
fails to answer then is logged and the others are still braked. The board has
no command watchdog, so this is the only thing that stops the motors when the
runtime goes away: if the provider is killed with `SIGKILL`, or its Python
process crashes, nothing brakes them and they keep their last throttle until
the motor supply is cut.

This is a software stop, not an emergency stop. Cut the motor supply for an
emergency stop. See the runtime's
[safety guide](https://github.com/anolishq/anolis/blob/main/docs/safety.md).

## Install

Pin it in a machine profile like any provider. `install.sh` installs from any
`owner/repo`:

```yaml
components:
  providers:
    adafruit:
      repo: CameronBrooks11/anolis-provider-adafruit
      version: "0.1.0"
```

0.1.0 accepts only `bme280` devices; a config with any other `type` fails its
schema check until the next release.

and give the runtime config an entry for it:

```yaml
providers:
  - id: adafruit0
    command: /opt/anolis/bin/anolis-provider-adafruit
    args: ["--config", "/opt/anolis/projects/<project>/config/provider-adafruit.yaml"]
    hello_timeout_ms: 5000
    ready_timeout_ms: 10000
```

The host needs I2C enabled and the `anolis` user in the `i2c` group;
`--check-host` reports both. See [docs/hardware.md](docs/hardware.md) for
wiring, host preparation and measuring start-up time on the target.

Release binaries are built on Ubuntu 24.04 and need glibc 2.39 or newer: Debian
13 (Raspberry Pi OS trixie) or Ubuntu 24.04 and later.

## Development

Requires [uv](https://docs.astral.sh/uv/) and [just](https://just.systems/). On
Linux, `just setup` builds the Raspberry Pi PWM library Blinka uses on a Pi,
which has no wheel, so it also needs a C compiler.

```sh
just setup    # uv sync --locked --extra dev
just check    # ruff format check, ruff lint, mypy --strict
just test     # unit tests, and the conformance harness in mock mode
just freeze   # the single-file release binary, in dist/
```

Adding a board: [docs/adding-a-board.md](docs/adding-a-board.md). Candidate boards: [docs/coverage.md](docs/coverage.md).

## License

Apache-2.0. See [LICENSE](LICENSE).
