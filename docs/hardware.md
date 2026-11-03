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
