"""Every board loads on the Raspberry Pis the provider targets.

Blinka picks its platform modules from the board it detects, and on a Pi those
need platform libraries (gpiod, the Pi PWM library) that a generic x86 or arm64
host never loads. Forcing Blinka's board detection to a Pi 4 and a Pi 5 runs
that path on any host. Detection happens once per process, when Blinka is
first imported, so each identity runs in its own interpreter.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

PROBE = """
import json, sys, yaml
from anolis_provider_adafruit.provider import AdafruitProvider
with open(sys.argv[1]) as f:
    p = AdafruitProvider(yaml.safe_load(f))
p.start(10.0)
out = {}
for d in p.devices():
    h = p.device_health(d)
    out[d.id] = None if h is None else f"{h.state.name}: {h.message}"
print(json.dumps(out))
"""


@pytest.mark.parametrize(
    ("chip", "board"),
    [("BCM2XXX", "RASPBERRY_PI_4B"), ("BCM2712", "RASPBERRY_PI_5")],
    ids=["pi4", "pi5"],
)
def test_every_board_is_healthy_on_a_pi(chip: str, board: str) -> None:
    env = {**os.environ, "BLINKA_FORCECHIP": chip, "BLINKA_FORCEBOARD": board}
    proc = subprocess.run(
        [sys.executable, "-c", PROBE, str(REPO / "config" / "conformance.yaml")],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr[-4000:]
    health = json.loads(proc.stdout.splitlines()[-1])
    assert health and all(h is None for h in health.values()), health


BLOCKED_IMPORT = """
import sys
sys.modules[sys.argv[1]] = None  # as if the platform library were not installed
try:
    __import__(sys.argv[2])
except RuntimeError as err:
    print(f"RuntimeError: {err}")
else:
    print("imported")
"""


@pytest.mark.parametrize(
    ("chip", "board", "library", "driver"),
    [
        # https://github.com/adafruit/Adafruit_CircuitPython_BME280/issues/72
        ("BCM2XXX", "RASPBERRY_PI_4B", "gpiod", "adafruit_bme280.basic"),
        # https://github.com/adafruit/Adafruit_CircuitPython_BusDevice/issues/104
        ("BCM2XXX", "RASPBERRY_PI_4B", "gpiod", "adafruit_pca9685"),
        # https://github.com/adafruit/Adafruit_CircuitPython_Motor/issues/80
        ("BCM2712", "RASPBERRY_PI_5", "adafruit_blinka_raspberry_pi_pwm", "adafruit_motor.motor"),
    ],
    ids=["bme280-pi4", "pca9685-pi4", "motor-pi5"],
)
def test_the_drivers_need_the_pi_platform_libraries(chip: str, board: str, library: str, driver: str) -> None:
    # Why pyproject.toml depends on gpiod and the Pi PWM library. When one of
    # these fails, that driver loads without the library: once none needs it,
    # drop the dependency and this test.
    env = {**os.environ, "BLINKA_FORCECHIP": chip, "BLINKA_FORCEBOARD": board}
    proc = subprocess.run(
        [sys.executable, "-c", BLOCKED_IMPORT, library, driver],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr[-4000:]
    assert f"platform library '{library}' was not found" in proc.stdout, proc.stdout
