# Power hub firmware (Zephyr)

Firmware for the ESP32-S3 on the [power hub](../../electronics/power-hub/design.py),
the rack controller in the power box: it takes the rack's power from a
USB-C PD charger, switches and meters its four rows (A–D; the rack uses A–C),
and runs the rack bus
(CAN) that finds every bay node and tells it where it sits.

> **Status:** builds against Zephyr main (pinned in [`west.yml`](../west.yml));
> **not yet run on hardware**: no hub v1.0 has been assembled.  The rack
> bus protocol runs in a simulated rack on native_sim
> ([`common/tests/rack_bus`](../common/tests/rack_bus/)).  See
> [open items](#open-items).

How to build, flash and use it is on the documentation site:

| | |
|---|---|
| Build | [Build or download the firmware](../../docs/build/get-the-firmware.md), [Flash the hub and the nodes](../../docs/build/flash.md), [Power box and charger](../../docs/build/power-box.md) |
| Use | [Rows and the rack's page](../../docs/use/rack-page.md), [Access rules and security](../../docs/use/access.md), [Update the firmware](../../docs/use/update-firmware.md), [Power budget and queued ports](../../docs/use/power-budget.md) |
| Reference | [Power hub shell](../../docs/reference/hub-shell.md), [Power hub HTTP API](../../docs/reference/hub-api.md), [Network ports, names, metrics](../../docs/reference/network.md), [LEDs, buttons and switches](../../docs/reference/leds-and-buttons.md) |
| Without a hub | the simulated hub: [Try it without hardware](../../docs/plan/try-it-without-hardware.md); the bench stand-ins and the tests: [Work on the firmware](../../docs/dev/work-on-the-firmware.md) |
| Design | [docs/firmware.md › Power hub application](../../docs/firmware.md#power-hub-application), [docs/power.md](../../docs/power.md), the rack bus: [docs/rack-protocol.md](../../docs/rack-protocol.md) |

## Source layout

```
firmware/power-hub/
  src/main.c        start-up in that order, stored settings, BOOT, the CTL LED, the update's health check
  src/pd.c          USB-C PD: VBUS sense, the CH224A, 20 V (28 V EPR opt-in)
  src/rows.c        rows A–D: eFuse enables (held across resets), FLT, IMON, sequencing, shedding
  src/budget.c      the rows' power budget from the PD contract: which row to shed, which back
  src/bus.c         rack bus master: TWAI, POS tokens, enumeration (common/lib/rack_hub.c)
  src/web.c         status page, JSON API, /metrics
  src/shell.c       "hub" shell commands
  src/events.c      event log (page, shell)
  web/index.html    status page (embedded gzipped; shares /rack.css and /rack.mjs)
  web/dev_server.py the page against a simulated hub
  web/screenshots.py  docs/img/hub-ui-*.png
  tests/budget      budget.c on native_sim with made-up contracts (ztest)
```

Shared with the bay node, in [`firmware/common`](../common/): the rack bus
protocol ([`docs/rack-protocol.md`](../../docs/rack-protocol.md)), the
CH224A driver, Wi-Fi and hostname, the web pages' CSS and helpers, the
development server and screenshot tooling.

## CH224A driver

Out of tree in [`firmware/common/drivers/regulator`](../common/drivers/regulator/): the
CH224A has one function, the contract, so it is a regulator (`wch,ch224a`, on the I²C
bus), not a multi-function device.  Register map from the WCH CH224 datasheet (manual
1, v2.1, 5.2.3); Zephyr has no CH224 driver.

| API | What the chip gives |
|---|---|
| `list_voltage` | 5, 9, 12, 15, 20, 28 V: the voltage register's values |
| `set_voltage` | the lowest of those in the range (register 0x0A), else a PPS or AVS voltage in 100 mV steps (0x53, 0x51/0x52) inside a range the charger offers |
| `get_voltage` | the voltage asked for (`startup-microvolt` until then, the CFG1 resistor's), while the status says PD; 5 V otherwise.  The chip cannot report the contract |
| `get_current_limit` | the current the charger grants (0x50, 50 mA steps), with PD only |
| `set_callback` | PG (`pg-gpios`): `REGULATOR_VOLTAGE_DETECTED` / `REMOVED` |
| no `enable`/`disable` | the chip has no switch |
| `regulator_ch224a_get_status()` | the protocol in place (0x09: BC, QC2, QC3, PD, EPR) |
| `regulator_ch224a_power_good()` | PG |
| `regulator_ch224a_get_pdos()` | the charger's offers (0x60–0x8F): the whole (EPR_)Source_Capabilities message, decoded; the datasheet promises the SPR one only from chargers under 100 W |

The chip runs from VBUS: its node carries `zephyr,deferred-init`, and `pd.c`
initializes it once VBUS is up and the chip answers (a deferred init that fails
cannot be run again).

## Pin map

From `electronics/power-hub/design.py` (U4, ESP32-S3-MINI-1); devicetree in
[`boards/hwtr/power_hub/power_hub.dtsi`](../boards/hwtr/power_hub/power_hub.dtsi)
and [`power_hub-pinctrl.dtsi`](../boards/hwtr/power_hub/power_hub-pinctrl.dtsi).

<!-- site:pin-map -->
| ESP32-S3 | Net | Use | Devicetree |
|---|---|---|---|
| IO0 | BOOT | SW2 BOOT button (strapping pin) | `boot_button` (`sw0`) |
| IO1 | ADC_IMON_A | row A eFuse IMON (1.404 V/A, 1k + 10 nF), ADC1 ch 0 | `imon_a` |
| IO2 | ADC_IMON_B | row B IMON, ADC1 ch 1 | `imon_b` |
| IO4 | ADC_IMON_C | row C IMON, ADC1 ch 3 | `imon_c` |
| IO5 | ADC_IMON_D | row D IMON, ADC1 ch 4 | `imon_d` |
| IO6 | VBUS_SENSE | VBUS through 100k/10k, ADC1 ch 5 | `vbus_sense` |
| IO7 | CAN_TXD | TJA1462AT TXD | `&twai` |
| IO8 | CAN_RXD | TJA1462AT RXD | `&twai` |
| IO9 | CAN_STB | TJA1462AT standby (10k pull-down) | `can_phy` `standby-gpios` |
| IO10 | POS_A | row A POS token (10k, BAT54S clamp) | `row_a` `pos-gpios` |
| IO11 | POS_B | row B POS | `row_b` `pos-gpios` |
| IO12 | POS_C | row C POS | `row_c` `pos-gpios` |
| IO13 | POS_D | row D POS | `row_d` `pos-gpios` |
| IO14 | ROW_EN_A | row A eFuse SHDN through 10k (100k pull-down: off) | `row_a` `enable-gpios` |
| IO15 | ROW_EN_B | row B SHDN | `row_b` `enable-gpios` |
| IO16 | ROW_EN_C | row C SHDN | `row_c` `enable-gpios` |
| IO17 | ROW_EN_D | row D SHDN | `row_d` `enable-gpios` |
| IO18 | FLT_A | row A eFuse ~FLT (100k pull-up, red LED) | `row_a` `fault-gpios` |
| IO19 | USB_DN | console USB-C D− (USB-Serial-JTAG) | `&usb_serial` |
| IO20 | USB_DP | console USB-C D+ | `&usb_serial` |
| IO21 | FLT_B | row B ~FLT | `row_b` `fault-gpios` |
| IO33 | FLT_D | row D ~FLT | `row_d` `fault-gpios` |
| IO35 | CTL_LED | the controller's green LED (330 Ω) | `ctl_led` |
| IO39 | PD_INT | CH224A PG (open drain, 10k pull-up, low once the contract is in place; also the front PD LED) | `pd_sink` `pg-gpios` |
| IO40 | PD_SCL | I²C0 SCL to the CH224A (its CFG2) | `&i2c0` |
| IO41 | PD_SDA | I²C0 SDA (its CFG3) | `&i2c0` |
| IO42 | I2C_PU | the CH224A's 5.1k pull-ups: driven high once VBUS is up, an input (floating) otherwise | `power_hub` `i2c-pullup-gpios` |
| IO47 | FLT_C | row C ~FLT | `row_c` `fault-gpios` |
| TXD0 (IO43) | U0TX | test pad TP1 | `&uart0` |
| RXD0 (IO44) | U0RX | test pad TP2 | `&uart0` |
| EN | EN | SW1 RESET button | — |
<!-- /site:pin-map -->

`python3 firmware/tools/check_pinmap.py` checks this table and the board
devicetree against U4 in `design.py`, as it does for the bay node.

## Open items

The hub's open items (bring-up, the budget from the worst case, updates on hardware) are in
[docs/firmware.md › Open items](../../docs/firmware.md#open-items).
