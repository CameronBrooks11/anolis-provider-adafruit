# anolis-provider-adafruit

An [Anolis](https://github.com/anolishq/anolis) device provider for Adafruit
hardware. It puts the
[Python provider SDK](https://github.com/anolishq/anolis-provider-sdk-python) on
top of Adafruit's own CircuitPython drivers, so each board is a short
declaration plus a call into the driver Adafruit already maintains. On Linux the
drivers run through [Adafruit Blinka](https://github.com/adafruit/Adafruit_Blinka),
which they depend on.

> **Status: v0.1.0.** One board so far. It passes the anolis-protocol 1.10.0
> conformance harness at level 2 in mock mode, from source and as the frozen
> release binary, on x86_64 and arm64. Not yet verified on a Raspberry Pi.

## Supported boards

| `type` | Board | Driver | Addresses |
| --- | --- | --- | --- |
| `bme280` | BME280 temperature, humidity and pressure (STEMMA QT) | `adafruit-circuitpython-bme280` | `0x77` (default), `0x76` |

All boards share one Linux I2C bus (`i2c_bus`, default 1: the Raspberry Pi
header, and any STEMMA QT or Qwiic adapter on it).

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
```

`mock: true` replaces the bus with a simulated one holding a register model of
each configured board. Adafruit's driver runs unchanged against it. The full
schema: `anolis-provider-adafruit --config-schema`.

A board that does not answer is listed anyway and reported `UNREACHABLE`; reads
and calls fail with `UNAVAILABLE` and retry the board each time, so reseating a
cable recovers it without a restart.

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

Requires [uv](https://docs.astral.sh/uv/) and [just](https://just.systems/).

```sh
just setup    # uv sync --locked --extra dev
just check    # ruff format check, ruff lint, mypy --strict
just test     # unit tests, and the conformance harness in mock mode
just freeze   # the single-file release binary, in dist/
```

Adding a board: [docs/adding-a-board.md](docs/adding-a-board.md).

## License

Apache-2.0. See [LICENSE](LICENSE).
