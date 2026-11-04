# Hardware

## Wiring a STEMMA QT or Qwiic board to a Raspberry Pi

STEMMA QT and Qwiic use the same 4-pin JST SH connector and pinout, and both
run at 3.3 V. Use a STEMMA QT/Qwiic cable to female jumpers, or a Qwiic adapter
board for the Pi header:

| Cable wire | Pi header pin |
| --- | --- |
| red, 3.3 V | 1 |
| blue, SDA | 3 (GPIO 2) |
| yellow, SCL | 5 (GPIO 3) |
| black, GND | 6 |

Boards daisy-chain on the same cable run: each needs its own address on the bus.

## The DC & Stepper Motor HAT

The HAT sits on the Pi's 40-pin header and talks I2C on the same pins, so it
shares bus 1 with any STEMMA QT boards. The current revision has its 2x20
header soldered on, so nothing stacks above it: to add STEMMA QT boards, fit a
Qwiic/STEMMA QT SHIM or a stacking header between the Pi and the HAT and plug
the sensor cable into that.

- **Motor power is separate.** The HAT drives motors from its own supply, on the
  polarity-protected 2-pin terminal (Adafruit: 4.5 to 13.5 V DC), not from the
  Pi. Size the supply for the motors' stall current; the TB6612 drivers are
  rated 1.2 A per bridge, with peaks of 3 A for about 20 ms. Leave the Pi
  powered on its own USB-C supply.
- **Terminals:** M1 to M4, each one DC motor. A motor that turns the wrong way
  for a positive throttle: swap its two wires.
- **Address:** `0x60` from the factory. Bridging the A0 to A4 jumpers adds 1, 2,
  4, 8 or 16. Avoid `0x70`, which every PCA9685
  also answers as its All Call address; the config refuses it.
- **Check it:** `i2cdetect -y 1` shows `60` and `70` with one HAT fitted.

The provider brakes all four terminals when it connects. Before the first run,
check that each motor can turn freely and that nothing is attached that would
move when it spins.

### Bench check of the software stop

With the runtime config's `safety.safe_state.zero_is_safe: true`, and a motor on
M1:

```sh
TOKEN=...   # from /etc/anolis/runtime.env when auth is on
H="Authorization: Bearer $TOKEN"
curl -s -H "$H" http://127.0.0.1:8080/v0/runtime/status | jq .startup_safe_state
curl -s -H "$H" -X POST http://127.0.0.1:8080/v0/call -H "Content-Type: application/json" \
  -d '{"provider_id":"adafruit0","device_id":"drive0","function_id":1,"args":{"throttle":{"type":"double","double":0.3}}}'
curl -s -H "$H" -X POST http://127.0.0.1:8080/v0/estop | jq .safe_state_achieved
curl -s -H "$H" "http://127.0.0.1:8080/v0/state/adafruit0/drive0?signal_id=motor1_throttle" | jq '.values[0].value'
curl -s -H "$H" -X POST http://127.0.0.1:8080/v0/estop/clear
```

The motor should spin at the call, stop at the stop, and read back 0. Function
ids follow the terminals: `set_motor1_throttle` is 1, up to 4.

## The SHT4x and SHTC3

Two Sensirion temperature and humidity sensors, on STEMMA QT boards: the SHT40,
SHT41 and SHT45 (`sht4x`) and the SHTC3 (`shtc3`).

- **Address:** the SHT4x boards answer at `0x44`, the SHTC3 at `0x70`. Neither
  has an address jumper, so one of each per bus.
- **Check it:** `i2cdetect -y 1` shows `44` or `70`, and the readings come back
  near the room's: about 20 to 25 C and 30 to 60 %.
- **Heater:** the SHT4x has a built-in heater for driving off condensation. The
  provider never turns it on: run for long, it damages the sensor.

## Preparing the host

On Raspberry Pi OS:

```sh
sudo raspi-config nonint do_i2c 0   # enable I2C, then reboot
sudo usermod -aG i2c anolis         # the service user opens /dev/i2c-1
sudo apt install i2c-tools          # optional: i2cdetect for checking wiring
i2cdetect -y 1                      # a BME280 shows as 77 (or 76)
```

`install.sh` runs the provider's `--check-host` before installing and stops on
an unmet requirement. The provider reports whether `/dev/i2c-<n>` exists and
whether the user it runs as can open it.

## Measuring start-up time on the target

The runtime waits `hello_timeout_ms` (default 5000) for a provider's Hello
reply, then `ready_timeout_ms` for start-up to finish. The release binary is a
single self-extracting file, so its start-up is slower than a source install,
and slowest on first launch after boot. Measure it on the target with only
`python3` and the binary:

```sh
python3 scripts/cold_start.py /opt/anolis/bin/anolis-provider-adafruit \
  /opt/anolis/projects/<project>/config/provider-adafruit.yaml --runs 5
```

It prints the median and slowest time to the Hello reply and to the WaitReady
reply, and exits 1 if the slowest Hello is over `--hello-budget-ms`. Set the
runtime's `hello_timeout_ms` with room above the slowest figure.
