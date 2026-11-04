# Coverage: candidate Adafruit boards

Which Adafruit I2C boards this provider could support, grouped by the chip and
the Adafruit CircuitPython driver that runs it, not by SKU. One driver usually
covers several boards, so a row here is one unit of work: a module in
`devices/` as described in [adding-a-board.md](adding-a-board.md).

Supported today: `bme280`, and `motor_hat` (PCA9685 with
`adafruit-circuitpython-motor`). Everything else is a candidate.

Sources, all retrieved 2026-11-03:

- The CircuitPython library bundle's `.gitmodules`
  (`adafruit/Adafruit_CircuitPython_Bundle`, `main`): the driver list.
- Each listed driver's `README.rst`, `pyproject.toml` and main module source,
  from its repository's `main` branch: PyPI name, product links, default
  address.
- Adafruit's STEMMA QT shop category (adafruit.com/category/1018) and its
  three subcategories: product names and numbers.
- `adafruit/awesome-stemma`, `awesome-stemma-qt.md`: Adafruit's curated list.
- Product pages for #4280 and #6318, where the chip or a board
  feature was not in the driver source.

"Product numbers" are Adafruit's product IDs (adafruit.com/product/N). An
address is the driver's default as written in its source; "alt" addresses are
the ones the source names. Where a fact came from somewhere else, the cell
says so. Where no fetched source stated it, the cell says **unconfirmed**.

## Actuators and outputs

| Chip / family | PyPI driver | Example boards (#) | I2C address | Notes for Anolis |
| --- | --- | --- | --- | --- |
| PCA9685 16-channel PWM, DC motors via TB6612 | `adafruit-circuitpython-pca9685`, `-motor`, `-motorkit` | DC & Stepper Motor HAT (2348) **supported as `motor_hat`**; DC Motor + Stepper FeatherWing (2927); Motor/Stepper/Servo Shield v2 (1438); DC & Stepper Motor Bonnet (4280) | MotorKit default 0x60 | Throttle 0 brakes, `None` coasts (`adafruit_motor.motor`). No command watchdog: outputs hold if the provider stops. The FeatherWing and Shield share the HAT's driver, so they are a config entry, not a module. Bonnet: the product page says a "dedicated PWM driver chip" without naming it, and MotorKit's docstring does not list it, so PCA9685 is **unconfirmed** for 4280. |
| PCA9685 16-channel PWM, servos and raw PWM | `adafruit-circuitpython-pca9685`, `-motor`, `-servokit` | 16-Channel 12-bit PWM/Servo Driver (815); 16-Channel PWM/Servo HAT (2327); PWM/Servo Bonnet (3416); PWM/Servo Shield (1411); 8-Channel PWM/Servo FeatherWing (2928) | 0x40 default (driver and ServoKit) | A servo angle of 0 is a position, not a safe state. The off state is no pulse (`fraction = None` writes duty 0 in `adafruit_motor.servo`). The zero rung needs a numeric argument where 0 is safe, so expose pulse width or duty (0 = no pulse), not angle. Same chip and register model as `motor_hat`, so the mock fake already exists. No watchdog. |
| MCP23017 driving 8 low-side MOSFETs (solenoids) | `adafruit-circuitpython-mcp230xx` | I2C to 8 Channel Solenoid Driver (6318) | 0x20 default; 3 address jumpers, up to 8 boards (product page) | Output low = solenoid off. Port B is spare GPIO (product page). MCP23017 power-on pin direction not checked against the datasheet: **unconfirmed** that outputs are off before the provider connects. No watchdog. Same driver as the GPIO expanders below. |
| DRV2605L haptic driver | `adafruit-circuitpython-drv2605` | DRV2605L Haptic Motor Controller (2305) | 0x5A | Plays effects rather than holding a level; low value for a lab rig. |
| EMC2101 fan controller + temperature | `adafruit-circuitpython-emc2101` | EMC2101 PC Fan Controller (4808) | 0x4C (fixed in driver) | 0 % fan is not necessarily safe if the fan cools something; decide per rig. Also a temperature sensor. |
| MCP4728 quad 12-bit DAC | `adafruit-circuitpython-mcp4728` | MCP4728 Quad DAC with EEPROM (4470) | 0x60 default | 0 V output. Power-up values come from on-chip EEPROM (driver: `save_to_eeprom` sets "defaults on power up"), so the board can start non-zero if someone saved values: drive 0 on connect. |
| MCP4725 12-bit DAC | `adafruit-circuitpython-mcp4725` | MCP4725 breakout (935) | 0x62 default | 0 V output. Not in the STEMMA QT category. |
| AD5693R 16-bit DAC | `adafruit-circuitpython-ad569x` | AD5693R Breakout (5811) | 0x4C | 0 V output. |
| DAC7578 / DAC6578 8-channel DAC | `adafruit-circuitpython-dacx578` | DAC7578 Breakout (6223); DAC6578 Breakout (6258) | 0x4C (constant; a docstring in the same file says 0x47) | 0 V output. 6258 is not linked from the driver; it is matched by name only. |
| GP8403 2-channel 0-10 V DAC | `adafruit-circuitpython-gp8403` | GP8403 I2C DAC with 12V Booster + NVM (6516) | 0x58 | 0-10 V is the common analog setpoint input on lab and industrial kit. Power-up value comes from NVM; writing NVM needs a bit-banged waveform on raw pins (driver docstring), which the provider should not do. Drive 0 on connect. |
| PCF8591 4-ch 8-bit ADC + 1 DAC | `adafruit-circuitpython-pcf8591` | PCF8591 Quad ADC + DAC (4648) | 0x48 | Also listed under analog in. |
| ADG728 / ADG729 analog matrix switch | `adafruit-circuitpython-adg72x` | ADG728 1-to-8 (5899); ADG729 dual 1-to-4 (5932) | ADG728 0x4C, ADG729 0x44 | Routes signals rather than driving a load. "All open" is the natural safe state, but 0 is a channel index, so it needs a per-channel function to fit the zero rung. |

No Adafruit relay board appeared in the STEMMA QT category (searched names for
`relay`; see How this was counted).

## Discrete I/O (GPIO expanders)

| Chip / family | PyPI driver | Example boards (#) | I2C address | Notes for Anolis |
| --- | --- | --- | --- | --- |
| MCP23017 / MCP23008 | `adafruit-circuitpython-mcp230xx` | MCP23017 GPIO Expander Breakout (5346); GPIO Expander Bonnet (4132); Solenoid Driver (6318) | 0x20 default | One driver covers three boards here. Pin-change interrupt pins exist on the chip; using them is out of scope (needs a host GPIO). Poll instead. |
| PCF8574 / PCF8575 | `adafruit-circuitpython-pcf8574`, `-pcf8575` | PCF8574 Expander (5545); PCF8575 16 GPIO Expander (5611) | 0x20 default | Quasi-bidirectional pins: "output high" is a weak pull-up, so read-back of an output is the pin level, not the latch. |
| AW9523 | `adafruit-circuitpython-aw9523` | AW9523 GPIO Expander and LED Driver (4886) | 0x58 default | Pins can run as constant-current LED drivers. |
| TCA8418 | `adafruit-circuitpython-tca8418` | TCA8418 Keypad Matrix and GPIO Expander (4918) | 0x34 | Mainly a keypad scanner; see human input. |
| seesaw on ATtiny8x7 / ATtinyx16 | `adafruit-circuitpython-seesaw` | ATtiny816 (5681), ATtiny817 (5233), ATtiny1616 (5690) Breakouts with seesaw | 0x49 (driver default) | Firmware gives GPIO, ADC and PWM over I2C. PWM out at 0 is off. One driver also covers every seesaw board under human input. |

## Analog in (ADCs, load cell)

| Chip / family | PyPI driver | Example boards (#) | I2C address | Notes for Anolis |
| --- | --- | --- | --- | --- |
| NAU7802 24-bit bridge ADC | `cedargrove-nau7802` (bundled community driver) | NAU7802 24-Bit ADC (4538) | 0x2A | Load cells and strain gauges. The PyPI name is not `adafruit-…`: the bundle ships a community driver here. |
| ADS1015 / ADS1115 | `adafruit-circuitpython-ads1x15` | **unconfirmed**: no product number in the driver README or the STEMMA QT category | 0x48 default | Very common on bench rigs. Find the board numbers before committing to it. |
| ADS7830 8-ch 8-bit | `adafruit-circuitpython-ads7830` | ADS7830 8-Channel ADC (5836) | 0x48 | |
| ADS122C04 24-bit | `adafruit-circuitpython-ads122c04` | ADS122C04 24-Bit ADC (6432) | 0x40 | RTD and thermocouple-grade front end. |
| ADS7128 8-ch 12-bit | `adafruit-circuitpython-ads7128` | product 6494 (linked from driver; not in STEMMA QT category) | **unconfirmed** (module not found at the guessed path) | |
| MCP3421 18-bit | `adafruit-circuitpython-mcp3421` | MCP3421 18-Bit ADC (5870) | 0x68 | |
| PCF8591 | `adafruit-circuitpython-pcf8591` | PCF8591 Quad ADC + DAC (4648) | 0x48 | 8-bit. |
| HX711 load-cell amp | `adafruit-circuitpython-hx711` | HX711 (5974) | none | **Out of scope**: bit-banged on two GPIO pins (`__init__(data_pin, clock_pin)`), not I2C. |

## Environment (temperature, humidity, pressure)

| Chip / family | PyPI driver | Example boards (#) | I2C address | Notes for Anolis |
| --- | --- | --- | --- | --- |
| BME280 | `adafruit-circuitpython-bme280` | **supported** as `bme280` | 0x77, alt 0x76 | Product number not in the fetched sources. |
| BME680 / BME688 | `adafruit-circuitpython-bme680` | BME680 (3660); BME688 (5046) | 0x77 | Adds a gas resistance reading. 5046 matched by name. |
| BMP280 / BMP3xx / BMP5xx | `-bmp280`, `-bmp3xx`, `-bmp5xx` | BMP280 (2651); BMP388 (3966); BMP390 (4816); BMP5xx (6407, 6411, 6413) | 0x77 (BMP280, BMP3xx); 0x47 (BMP5xx) | Pressure only (plus temperature). |
| DPS310 | `adafruit-circuitpython-dps310` | DPS310 (4494) | 0x77 | |
| LPS22 / LPS25 / LPS28 / LPS33/35 | `-lps2x`, `-lps28`, `-lps35hw` | LPS25 (4530); LPS22 (4633); LPS28 (6067); LPS33HW (4414); LPS35HW (4258) | 0x5D (lps2x, lps35hw); 0x5C (lps28) | LPS33HW is the water-resistant one. |
| MPRLS ported pressure | `adafruit-circuitpython-mprls` | MPRLS (3965) | 0x18 | Gauge for pneumatic or vacuum lines. Not in the STEMMA QT category. |
| MS8607 | `adafruit-circuitpython-ms8607` | MS8607 PHT (4716) | two addresses in source (0x40, 0x76) | |
| SHT4x | `adafruit-circuitpython-sht4x` | SHT40 (4885); SHT41 (5776); SHT45 (5665); SHT45 with PTFE (6174) | 0x44 | One driver, four boards. Only 4885 is linked from the driver; the rest are matched by name. |
| SHT3x | `adafruit-circuitpython-sht31d` | SHT31-D (2857) | 0x44, alt 0x45 | |
| SHTC3, AHT20, HTU31D, HDC302x, Si7021, HTS221 | `-shtc3`, `-ahtx0`, `-htu31d`, `-hdc302x`, `-si7021`, `-hts221` | SHTC3 (4636); AHT20 (4566); HTU31 (4832); HDC3022 (5989); Si7021 (3251); HTS221 (4535) | 0x70; 0x38; 0x40/0x41; 0x44; 0x40; 0x5F | Humidity alternatives; each its own driver. |
| MCP9808 | `adafruit-circuitpython-mcp9808` | MCP9808 (5027; driver links 1782) | 0x18 | |
| TMP117 | `adafruit-circuitpython-tmp117` | TMP117 (4821) | 0x48 | ±0.1 °C. Whether this driver also covers the TMP119 (6482) is **unconfirmed**. |
| ADT7410, PCT2075 | `-adt7410`, `-pct2075` | ADT7410 (4089); PCT2075 (4369) | 0x48; 0x37 | |
| MCP9600 / MCP9601 thermocouple | `adafruit-circuitpython-mcp9600` | MCP9601 (5165; driver links MCP9600 4101) | 0x67 | Thermocouple amplifier, common for heater rigs. |
| DS2484 / DS2482S-800 I2C-to-1-Wire | `adafruit-circuitpython-ds248x` | DS2484 (5976); DS2482S-800 8-channel (6027) | 0x18 | Bridges to DS18B20 probes. The provider would enumerate 1-Wire devices behind it: a bus device, like a mux. |
| MLX90614 / MLX90632 IR thermometers | `-mlx90614`, `-mlx90632` | MLX90614 (1747, 1748); MLX90632 (6403) | 0x5A; 0x3A | Non-contact temperature. |

## Gas and air quality

| Chip / family | PyPI driver | Example boards (#) | I2C address | Notes for Anolis |
| --- | --- | --- | --- | --- |
| SCD4x (SCD40/41/43) NDIR CO2 | `adafruit-circuitpython-scd4x` | SCD-40 (5187); SCD-41 (5190); SCD-43 (6512) | 0x62 | One driver, three boards (5190 and 6512 matched by name). Readings every ~5 s; the provider must not block on them. |
| SCD30 NDIR CO2 | `adafruit-circuitpython-scd30` | SCD-30 (4867) | 0x61 | |
| STCC4 CO2 | `adafruit-circuitpython-stcc4` | STCC4 and SHT41 (6478) | 0x64 | |
| SGP30 / SGP40 / SGP41 | `-sgp30`, `-sgp40`, `-sgp41` | SGP30 (3709); SGP40 (4829); SGP41 (6455) | 0x58; 0x59; 0x59 | VOC (and NOx on SGP41) indices need humidity compensation from another sensor. |
| ENS160 MOX | `adafruit-circuitpython-ens160` | ENS160 (5606) | 0x53 | Whether it also covers ENS161 (6431) is **unconfirmed**. |
| CCS811 | `adafruit-circuitpython-ccs811` | CCS811 (3566) | 0x5A | Superseded by ENS160 per the shop's own product name. |
| PMSA003I particulates | `adafruit-circuitpython-pm25` | PMSA003I (4632) | 0x12 (`adafruit_pm25/i2c.py`) | Use the I2C class. The driver also links 3686 and 4505, not checked here. |
| SEN6x (SEN66) | `adafruit-circuitpython-sen6x` | SEN6x Breakout (6331) | 0x6B (source also names 0x6C) | |
| SEN54 / SEN55 | none found in the bundle | SEN54 or SEN55 Adapter (5964) | | **Unconfirmed**: no bundle driver. |
| AGS02MA | `adafruit-circuitpython-ags02ma` | AGS02MA (5593) | 0x1A | Not in the STEMMA QT category. |

## Motion and IMU

| Chip / family | PyPI driver | Example boards (#) | I2C address | Notes for Anolis |
| --- | --- | --- | --- | --- |
| LSM6DS family (LSM6DSOX, LSM6DSO32, LSM6DS33, LSM6DS3TR-C, ISM330DHCX) | `adafruit-circuitpython-lsm6ds` | LSM6DSOX (4438); LSM6DS33 (4480); ISM330DHCX (4502); LSM6DSO32 (4692); combos with LIS3MDL (4485, 4517, 4565, 4569) | 0x6A | One driver, eight linked boards: the widest single family here. |
| LIS3DH, ADXL34x, ADXL37x, LIS331, MSA301/311 | `-lis3dh`, `-adxl34x`, `-adxl37x`, `-lis331`, `-msa301` | LIS3DH (2809); ADXL345 (1231); ADXL375 (5374); LIS331/H3LIS331 (4626, 4627); MSA301 (4344), MSA311 (5309) | 0x18; 0x53; 0x53; 0x18; MSA301 0x26, MSA311 0x62 | Vibration and tilt. ADXL34x/37x boards also have SPI; only I2C is in scope. |
| BNO055 / BNO08x fusion | `-bno055`, `-bno08x` | BNO055 (4646); BNO085 (4754) | 0x28; 0x4A | On-chip sensor fusion. |
| ICM-20649 / ICM-20948, MPU-6050 | `-icm20x`, `-mpu6050` | ICM-20649 (4464); ICM-20948 (4554); MPU-6050 (3886) | 0x68 / 0x69; 0x68 | |
| Magnetometers and angle | `-lis3mdl`, `-lis2mdl`, `-mmc56x3`, `-mlx90393`, `-tlv493d`, `-tmag5273`, `-as5600` | LIS3MDL (4479); LIS2MDL (4488); MMC5603 (5579); MLX90393 (4022); TLV493D (4366); TMAG5273 (6489, 6490); AS5600 (6357) | 0x1C; 0x1E; 0x30; 0x0C; 0x5E; 0x35; 0x36 | AS5600 is a magnetic rotary-position sensor: shaft angle on a rig. |

## Distance and ToF

| Chip / family | PyPI driver | Example boards (#) | I2C address | Notes for Anolis |
| --- | --- | --- | --- | --- |
| VL53L0X / VL53L1X / VL53L4CD | `-vl53l0x`, `-vl53l1x`, `-vl53l4cd` | VL53L0X (3317); VL53L1X (3967); VL53L4CD (5396) | 0x29 (VL53L0X `address=41`) | All share 0x29. Several on one bus need either per-device XSHUT pins (a host GPIO: out of scope) or a mux. VL53L4CX (5425) has no bundle driver: **unconfirmed**. |
| VL6180X | `adafruit-circuitpython-vl6180x` | VL6180X (3316) | 0x29 | Short range. Same address clash. |
| TMF8801 / TMF8806 | `-tmf8801`, `-tmf8806` | TMF8801 (6522); TMF8806 (6501) | **unconfirmed** (module path not found) | |
| VCNL4040 / 4020 / 4200, APDS9960 | `-vcnl4040`, `-vcnl4020`, `-vcnl4200`, `-apds9960` | VCNL4040 (4161); VCNL4020 (5810); VCNL4200 (6064); APDS9960 (3595) | 0x60; 0x13; 0x51; 0x39 | Proximity, not ranging. |

## Light and colour

| Chip / family | PyPI driver | Example boards (#) | I2C address | Notes for Anolis |
| --- | --- | --- | --- | --- |
| Lux: VEML7700, TSL2591, BH1750, LTR-329/303, MAX44009, TSL2585 | `-veml7700`, `-tsl2591`, `-bh1750`, `-ltr329-ltr303`, `-max44009`, `-tsl2585` | VEML7700 (4162, 5378); TSL2591 (1980); BH1750 (4681); LTR-329 (5591), LTR-303 (5610); MAX44009 (6498); TSL2585 (6524) | 0x10; 0x29; 0x23/0x5C; 0x29; 0x4A/0x4B; 0x39 | |
| UV: LTR390, AS7331 | `-ltr390`, `-as7331` | LTR390 (4831); AS7331 (6476) | 0x53; 0x74 | |
| Spectral / colour: AS7341, AS7343, AS726x, OPT4048, TCS3430, APDS9999 | `-as7341`, `-as7343`, `-as726x`, `-opt4048`, `-tcs3430`, `-apds9999` | AS7341 (4698); AS7343 (6477); AS726x (3779, linked from driver); OPT4048 (6335); TCS3430 (6479); APDS9999 (6461) | 0x39; 0x39; 0x49; 0x44; 0x39; 0x52 | Plate and cuvette colour readings. |
| MLX90640 thermal camera | `adafruit-circuitpython-mlx90640` | MLX90640 55° (4407), 110° (4469) | 0x33 | 768-pixel frames: a large signal for the protocol. |

## Power monitoring

| Chip / family | PyPI driver | Example boards (#) | I2C address | Notes for Anolis |
| --- | --- | --- | --- | --- |
| INA219 | `adafruit-circuitpython-ina219` | INA219 (904) | 0x40 | Most common current sensor on bench rigs. |
| INA228 / INA237 / INA238 / INA260 | `-ina228`, `-ina23x`, `-ina260` | INA228 (5832); INA237 (6340); INA238 (6349); INA260 (4226) | 0x40 | Higher voltage (85 V) and resolution. |
| INA3221 | `adafruit-circuitpython-ina3221` | INA3221 triple (6062) | 0x40 | Three rails in one board. |
| MAX17048, LC709203F fuel gauges | `-max1704x`, `-lc709203f` | MAX17048 (5580); LC709203F (4712) | 0x36; 0x0B | Battery rigs only. |
| HUSB238 USB-PD sink | `adafruit-circuitpython-husb238` | HUSB238 PD Dummy (5991; driver links 5807) | 0x08 | Selects the supply voltage, so it is an output too. Safe state undefined in the source: **unconfirmed**. |

## Human input

| Chip / family | PyPI driver | Example boards (#) | I2C address | Notes for Anolis |
| --- | --- | --- | --- | --- |
| seesaw firmware boards | `adafruit-circuitpython-seesaw` (NeoKey also `-neokey`) | Rotary Encoder (4991, 5880); Quad Rotary Encoder (5752); ANO Rotary (5740, 6310); LED Arcade Button 1x4 (5296); Mini I2C Gamepad (5743); PC Joystick adapter (5753); NeoSlider (5295); NeoKey 1x4 (4980) | per board, from the driver's examples: rotary 0x36, quad rotary 0x49, ANO 0x49, arcade 0x3A, gamepad 0x50, PC joystick 0x49 | One driver for all. Software-configurable addresses. Each board has a different pin map, so each is a small module even though the driver is shared. NeoSlider and NeoKey addresses **unconfirmed**. |
| MPR121 capacitive touch | `adafruit-circuitpython-mpr121` | MPR121 12-Key (1982) | 0x5A | |
| TCA8418 keypad matrix | `adafruit-circuitpython-tca8418` | TCA8418 (4918) | 0x34 | Event FIFO; polled read is fine. |
| Wii Nunchuck / Classic | `-nunchuk`, `-wii-classic` | Wii Nunchuck Breakout Adapter (4836) | 0x52 | |
| TSC2007 resistive touch | `adafruit-circuitpython-tsc2007` | TSC2007 (5423) | 0x48 | |

## Displays

| Chip / family | PyPI driver | Example boards (#) | I2C address | Notes for Anolis |
| --- | --- | --- | --- | --- |
| HT16K33 LED backpacks | `adafruit-circuitpython-ht16k33` | 14-seg Alphanumeric (1910, 1911, 1912, 2157, 2160); 7-seg (5599, 5603); 8x8 matrix (1048, 1050, 1614, 1632) | 0x70 default | Status readout on the rig. Product numbers matched by name; the driver README links none. |
| SSD1306 / SH1106 / SH1107 / SSD1327 OLED | `-ssd1306` or `-displayio-ssd1306`, `-displayio-sh1107`, `-ssd1327` | 128x32 (4440); 0.96" 128x64 (326); 1.3" 128x64 (938); FeatherWing OLED (4650, 6313); 1.12" 128x128 (5297); 1.5" grayscale (4741) | 0x3C (`-ssd1306`) | `displayio` drivers need CircuitPython's display stack; on Blinka use the framebuf drivers. **Unconfirmed** which of these work under Blinka. |
| IS31FL3741 / IS31FL3731 LED matrix | `-is31fl3741`, `-is31fl3731` | IS31FL3741 (5201); IS31FL3731 (2946) | 0x30; 0x74 | |
| Character LCD backpack | `adafruit-circuitpython-charlcd` | I2C / SPI character LCD backpack (292) | **unconfirmed** | Driver links other products; the backpack's chip is not stated in the fetched sources. |

## Bus infrastructure

| Chip / family | PyPI driver | Example boards (#) | I2C address | Notes for Anolis |
| --- | --- | --- | --- | --- |
| TCA9548A / PCA9548 8-channel mux | `adafruit-circuitpython-tca9548a` | PCA9548 8-Channel Mux (5626); TCA9548A (2717, linked from driver) | 0x70 default | **Bus device.** The provider has to own channel selection and give each board behind it a bus handle (the driver's `TCA9548A_Channel` is one). This is how several 0x29 ToF sensors or two SCD4x share a bus. Config schema needs a `bus: {mux, channel}` field. |
| PCA9546 4-channel mux | `adafruit-circuitpython-tca9548a` (**unconfirmed**: the driver source names only TCA9548A) | PCA9546 4-Channel Mux (5664) | | Same handling as above if the driver works with it. |
| LTC4316 address translator | none needed | LTC4316 I2C Address Translator (5914) | translates by jumper | Transparent: the provider sees the translated address. The config schema's address list per board would have to allow it. |
| ISO1540 isolator, LTC4311 terminator, TCA4307 hot-swap buffer, level shifters | none needed | ISO1540 (4903); LTC4311 (4756); TCA4307 (5159); 3V-to-5V (5649), 5V-to-3V (5637) | | Passive to software. Worth recommending in the hardware guide (isolation and hot-swap matter on rigs). |

## Other

| Chip / family | PyPI driver | Example boards (#) | I2C address | Notes for Anolis |
| --- | --- | --- | --- | --- |
| DS3502 / DS1841 digital potentiometers | `-ds3502`, `-ds1841` | DS3502 (4286); DS1841 (4570) | 0x28 | An output: wiper position. Safe value depends on the circuit. |
| RTCs: DS3231, PCF8523, RV-8803 | `-ds3231`, `-pcf8523`, `-rv8803` | DS3231 (5188); PCF8523 (5189); RV-8803 (6538) | RV-8803 0x32; others **unconfirmed** | The host clock is usually better; low value. |
| EEPROM / FRAM, ATECC608, Si5351, S-35710 | `-24lc32`, `-fram`, `-atecc`, `-si5351`, `-s35710` | 24LC32 (5146); ATECC608 (4314); Si5351A (5640); S-35710 (5959) | 0x50; ; ; 0x60; 0x32 | Not runtime devices. |
| PA1010D GPS | `adafruit-circuitpython-gps` | Mini GPS PA1010D (4415) | 0x10 | Also UART; I2C works. Low value for a lab. |

## Suggested order

Ranked by value per effort for a lab-automation runtime.

1. **PCA9685 servo/PWM** (815, 2327, 3416, 1411, 2928). Same chip and fake as
   `motor_hat`; adds servos and raw PWM. The design work is the pulse-width
   function shape that makes 0 mean "no pulse".
2. **MotorKit siblings** (2927, 1438). No new code beyond declaring the boards
   on the `motor_hat` module. Do this alongside 1.
3. **MCP230xx** (5346, 4132, 6318). One driver gives GPIO and the solenoid
   driver, whose safe state (output low, solenoid off) is unambiguous.
4. **INA219 / INA2xx** power monitors. Every rig has a rail worth watching;
   INA219 alone is one small register model.
5. **SHT4x** and **SCD4x**. Four and three boards per driver; humidity and CO2
   are the commonest enclosure readings after temperature.
6. **NAU7802** load cell (4538). Weighing is frequent in bench automation.
7. **TCA9548A mux**. Not a sensor, but it unlocks duplicates of everything
   above. Needs a design decision in the config schema first.
8. **MCP9600 thermocouple** and **DAC family** (MCP4728, GP8403). Heater and
   setpoint control; the DACs need the "drive 0 on connect" rule because they
   restore stored values at power-up.

Next tier: LSM6DS (eight boards, one driver), seesaw input boards, ADS1x15
once its board numbers are confirmed.

## How this was counted

Counted on 2026-11-03 from the sources above, fetched fresh; the scripts and
downloads were not kept in this repository, so each method below names what
was read rather than a file to rerun.

| Figure | Value | Method |
| --- | --- | --- |
| Bundle driver submodules | 277 | `path = ` lines in the bundle's `.gitmodules` under `libraries/drivers/` |
| Bundle helper submodules (MotorKit, ServoKit, Motor live here) | 135 | the same, under `libraries/helpers/` |
| Bundle drivers whose source or README mentions I2C | 191 (182 by source, 9 by README only) | a search of each driver's main module and README for I2C. **Estimate**: it misses packages whose `__init__.py` is empty (it reports `cap1188`, `atecc`, `neotrellis` as non-I2C, which they are not). |
| Products in the STEMMA QT category page | 309 distinct product IDs | product IDs parsed from the category page's product links. The page's subcategory labels read Devices and Sensors (200), Controllers (91), Cables and Connectors (19); parsing each subcategory page gives the same 200 / 91 / 19, which sum to 310 because 5681 is listed in two subcategories. |
| Devices and Sensors products linked by product number from a bundle driver's README or module docstring | 108 of 200 | the Devices and Sensors product IDs joined against product links in driver READMEs and docstrings. The other 92 are matched to a driver by name in the tables above, or not at all. |
| awesome-stemma-qt rows | 91 sensors, 55 devices, 26 displays | table rows per section of the list. The list is curated and lags the shop (e.g. it has no PCA9685 or Motor HAT, which are not STEMMA QT). |
| Relay boards in the STEMMA QT category | 0 | a case-insensitive search for `relay` over the category's product names: no match (exit status 1 confirmed); the same search for `solenoid` matches 6318. |

Not counted: Adafruit's whole I2C range outside the STEMMA QT category. The
motor and servo boards above (815, 2348, 2327, 3416, 1411, 2927, 2928, 1438)
come from driver docstrings, not the category, because most of them have no
STEMMA QT connector.
