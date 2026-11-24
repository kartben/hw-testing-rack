# Firmware (Zephyr)

Two applications, both on an ESP32-S3, share this tree:

| | |
|---|---|
| **Bay node** ([`bay-node/`](bay-node/), this page) | one per bay: the DATA lead's power and its boards under test over USB/IP, the AUX console, the wires, the logic analyzer and the camera |
| **[Power hub](power-hub/README.md)** | one per rack: USB-C PD in, rows A–D, the rack bus (CAN) master |

They speak the rack bus protocol ([docs/rack-protocol.md](../docs/rack-protocol.md)) and share
[`common/`](common/): the protocol, the CH224A and CH446Q drivers, Wi-Fi, hostname and DNS-SD, the access
rules and the admin key, updates, the web pages' CSS and helpers, xterm.js, the development server and the
screenshot tooling.  The node dogfoods Zephyr's new USB host stack (`uhc_dwc2` on the ESP32-S3 OTG
controller and `subsys/usb/host/usbip.c`).

> **Status:** both applications build against the Zephyr main pinned in [`west.yml`](west.yml), and their
> tests run on native_sim; the node and the hub have run on a XIAO ESP32-S3 bench stand-in.
> **Not yet run on a PCB:** the five v1.0 PCBs have been at the fab since 2026-11-11 and none is on a
> bench.  See [open items](#open-items).

```
firmware/
  west.yml                       west manifest (Zephyr main, hal_espressif, mbedtls, tf-psa-crypto,
                                 mcuboot, lvgl)
  boards/hwtr/bay_node/          board definition: bay_node/esp32s3/procpu
  boards/hwtr/power_hub/         board definition: power_hub/esp32s3/procpu
  dts/bindings/                  hwtr,* bindings (dut-port, usb-mux, rack-bus, rack-rows,
                                 power-hub) and wch,ch224a (the hub's PD sink, a regulator)
  snippets/front-display/        the front display study (no v1.0 node has its connector)
  tools/check_pinmap.py          the two pin maps against design.py and the devicetree
  common/                        shared by both applications
    include/hwtr/, lib/          rack bus protocol (frames, hub and node state machines), Wi-Fi,
                                 DNS-SD, access rules and admin key, updates, JPEG end finder
    drivers/                     CH224A USB PD sink as a regulator, CH446Q crosspoint as a mux
                                 (out of tree)
    web/                         rack.css, rack.mjs, vendor/xterm (xterm.js 6.0.0, MIT),
                                 analyzer/ (the logic analyzer's page), devserver.py, shots.py
    tests/                       rack_bus, update, usbh_hub, dnssd, ch446q (ztest, native_sim);
                                 usbip: the patched USB/IP service on native_sim's virtual USB bus
  spikes/usb-hub/                bench app: a hub and several DUTs behind an ESP32-S3
  spikes/coproc/                 build-only: the DATA ×4 co-processor's jobs on a Pico 2 (RP2350)
  power-hub/                     the power hub application (its own README)
  bay-node/                      the bay node application
    src/                         USB host and USB/IP, the DATA lead and ports, console, RFC 2217,
                                 wires, analyzer relay, co-processor loader, camera, web, shell
    boards/esp32s3_devkitc_procpu.overlay   stand-in: same pin map on a DevKitC-1
    boards/m5stack_stamps3_procpu.*         bench node on a StampS3: console + network, no USB host
    boards/m5stack_cores3_procpu.*          bench node on a CoreS3: USB host and USB/IP on its USB-C ([docs/bench.md](../docs/bench.md))
    boards/xiao_esp32s3_procpu.*            bench node on a XIAO ESP32-S3: octal PSRAM as the node, USB host on its USB-C (same doc)
    i2c-400k.overlay             the I²C bus at 400 kHz, to try at bring-up (100 kHz by default)
    app.overlay, data-x4.dtsi    a DATA ×4 on the DATA lead (the application's, not the board's: MCUboot)
    data-x6.dtsi                 or a DATA ×6: the same lead and image, told apart at each probe
    web/index.html               status page and serial console (embedded gzipped)
    web/wires-card.mjs, analyzer-card.mjs   the Wires and Logic analyzer cards
    web/dev_server.py            the page against a simulated node, to work on the UI
    web/camera/, grab_camera.py  its camera's frames, grabbed from the 3D viewer (site/)
    web/screenshots.py, screencast.py       the site's screenshots and console screencast
    tests/                       ports, data_lead, wires, coproc, analyzer (ztest, native_sim);
                                 console_sim (console, web server, access control on native_sim);
                                 rfc2217, acl, jpeg (host tests)
    wifi.conf.example            build-time Wi-Fi credentials (copy to wifi.conf)
```

## Where its documentation is

The documentation site, written from this page, has the instructions:

- [Build or download the firmware](../docs/build/get-the-firmware.md): the west workspace, Wi-Fi in the
  node's image, your own signing key, the two builds, the options a builder may change
- [Flash the hub and the nodes](../docs/build/flash.md): SERVICE and the PC port, `west flash`, a module
  that ran other firmware, the module's one-time fuse
- [Check each PCB › Bay node](../docs/build/check-the-pcbs/bay-node.md): the first boot, the shell on the UART
  pads, the Wi-Fi credentials
- [Bring the rack online](../docs/build/bring-the-rack-online.md): every bay at its place, the claim, the
  camera's focus
- [What a bay can do](../docs/use/index.md), then a page per feature:
  [power and reset](../docs/use/power-and-reset.md), [USB/IP and flashing](../docs/use/usb-and-flashing.md),
  [the front port and its modes](../docs/use/front-port.md), [reservations](../docs/use/reserve-a-bay.md),
  [updates](../docs/use/update-firmware.md), [recovery](../docs/use/recover.md)
- [Bay node shell](../docs/reference/node-shell.md), [Bay node HTTP API](../docs/reference/node-api.md),
  [Network ports, names, metrics](../docs/reference/network.md),
  [LEDs, buttons and switches](../docs/reference/leds-and-buttons.md),
  [States and error messages](../docs/reference/states-and-messages.md)
- [Try it without hardware](../docs/plan/try-it-without-hardware.md): the simulated node, `dev_server.py`
- [Work on the firmware](../docs/dev/work-on-the-firmware.md): the Zephyr pin and its patches, the
  stand-in boards, the tests, the pin-map check
- [docs/firmware.md](../docs/firmware.md): the design log, what has run where, the open items

The sections of this page that other files link to now point to their page:

### Building

[Build or download the firmware](../docs/build/get-the-firmware.md); a build from another Zephyr workspace:
[Work on the firmware](../docs/dev/work-on-the-firmware.md#the-zephyr-pin-and-the-carried-patches).

### Wi-Fi in the rack

[Wi-Fi in the rack](../docs/use/wifi.md): the access point, the nodes' radio settings, flashes at once.

### Web page and API

[Bay node HTTP API](../docs/reference/node-api.md); the page, card by card: [What a bay can do](../docs/use/index.md).

### Board targets

[Board targets](../docs/use/board-targets.md).

### Camera

[Camera](../docs/use/camera.md); the lens's focus: [Bring the rack online](../docs/build/bring-the-rack-online.md#focus-the-camera).

### Wires

[Wires between boards](../docs/use/wires.md).

### Logic analyzer

[Logic analyzer](../docs/use/logic-analyzer.md).

### Front display (study)

[docs/firmware.md › Front display (study)](../docs/firmware.md#front-display-study).

### Access control

[Access rules and security](../docs/use/access.md); the signature: [Bay node HTTP API](../docs/reference/node-api.md#the-admin-signature).

### Serial console

[Serial console](../docs/use/serial-console.md).

## Pin map

From `electronics/bay-node/design.py` (U3, ESP32-S3-WROOM-1-N8R8: 8 MB flash, 8 MB octal PSRAM on IO35–IO37;
the WROOM-1 has no IO26/IO33/IO34); devicetree in
[`boards/hwtr/bay_node/bay_node.dtsi`](boards/hwtr/bay_node/bay_node.dtsi) and
[`bay_node-pinctrl.dtsi`](boards/hwtr/bay_node/bay_node-pinctrl.dtsi).  Since node v1.0 the DATA lead has no INT
(map B): the node polls the DATA board over I²C, and IO4 carries the camera's CS.

<!-- site:pin-map -->
| ESP32-S3 | Net | Use | Devicetree |
|---|---|---|---|
| IO0 | BOOT | SW2 BOOT button (strapping pin, 10k pull-up); input once booted | `boot_button` (`sw0`), `gpio-keys` |
| IO1 | I2C_SCL | I²C0; also out on J7.7 to the drawer's DATA board | `&i2c0` |
| IO2 | I2C_SDA | I²C0 → INA226 @ 0x40 (2.2k pull-ups, 100 kHz: the DATA lead; `i2c-400k.overlay` tries 400 kHz); also out on J7.6 to the drawer's DATA board (its devices keep off 0x40) | `&i2c0`, `ina226` |
| IO4 | CAM_CS | camera SPI2 CS → J6.7 (33 Ω; 10k pull-up R37 beside the pin; IO8 before node v1.0) | `&spi2` `cs-gpios` |
| IO7 | CAM_LED | camera light: AO3400A Q4 gate → J6.6 LED_K (J6.8 before node v1.0; 100k pull-down: off at boot), LEDC PWM ≥ 20 kHz or on/off | `camera_light` (`pwm-leds`, `&ledc0` channel 0, 25 kHz) |
| IO9 | CAM_MISO | camera SPI2 MISO ← J6.5 (J6.6 before node v1.0; 33 Ω; R35 divider footprint if the Mega drives 5 V) | `&spi2` (`camera`: `arducam,mega`) |
| IO10 | CAM_MOSI | camera SPI2 MOSI → J6.4 (J6.5 before node v1.0; 33 Ω) | `&spi2` |
| IO11 | CAM_SCK | camera SPI2 SCK → J6.2 (J6.3 before node v1.0; 33 Ω), mode 0, 4 MHz | `&spi2` |
| IO12 | AUX_RST_CTL | 2N7002 Q2 → AUX RESET (open drain, 100k pull-down) | `dut_port` `reset-gpios` |
| IO13 | PC_DET | front port VBUS via 10k/20k: laptop plugged | `usb_mux` `pc-detect-gpios` |
| IO14 | MUX_FORCE_PC | OR gate → MUX_DUT SEL: force classic (100k pull-down) | `usb_mux` `force-pc-gpios` |
| IO15 | SVC | SERVICE slide switch | `usb_mux` `service-gpios` |
| IO16 | POS_IN | POS token from J1.6 (10k, BAT54S clamp, 100k pull-down) | `rack_bus` `pos-in-gpios` |
| IO17 | CAN_RXD | TJA1462AT RXD (rack CAN bus) | `&twai` |
| IO18 | CAN_TXD | TJA1462AT TXD | `&twai` |
| IO19 | ESP_DN | USB D−, internal FS PHY → MUX_DUT / MUX_PC | `zephyr_uhc0: &usb_otg` |
| IO20 | ESP_DP | USB D+ | `zephyr_uhc0: &usb_otg` |
| IO21 | AUX_RX | UART1 RX ← AUX pin 4 (1k) | `&uart1` |
| IO38 | LED_DIN | WS2812B (33 Ω), RMT channel 0 (the DevKitC-1 v1.1's own RGB LED pin) | `status_led` |
| IO39 | INA_ALERT_N | INA226 ~ALERT (10k pull-up): over 1.25 A on the DATA lead's supply (DUT_5V; DATA_VIN, 20–28 V, from node v1.0), the DATA ×4 port switched on last goes off (`src/ports.c`) | `ina226` `alert-gpios` |
| IO40 | DUT_FLT_N | TPS2553 ~FAULT (10k pull-up); from node v1.0 the TPS26600's ~FLT through 1k (R43), also low while it is off or ramping | `dut_port` `fault-gpios` |
| IO41 | DUT_EN | TPS2553 EN (100k pull-up: on without firmware); from node v1.0 the TPS26600's SHDN (10k pull-down: **off** without firmware, [docs/firmware.md](../docs/firmware.md#the-data-leads-power-on-rule-node-v10)) | `dut_port` `enable-gpios` |
| IO42 | POS_OUT | POS token to J2.1 (10k, BAT54S clamp): low until addressed | `rack_bus` `pos-out-gpios` |
| IO47 | AUX_TX | UART1 TX → AUX pin 3 (1k) | `&uart1` (`dut_port` `uart`) |
| IO48 | AUX_BOOT_CTL | 2N7002 Q3 → AUX BOOT (open drain, 100k pull-down) | `dut_port` `boot-gpios` |
| TXD0 (IO43) | U0TX | TP1, console + shell | `&uart0` |
| RXD0 (IO44) | U0RX | TP2 | `&uart0` |
| EN | EN | SW1 RESET button (10k/1µF) | — |
<!-- /site:pin-map -->

Each signal sits on the module edge that faces where it goes on the board: the right column feeds
the DUT power block (I²C at its rear end) and POS_OUT runs to J2 (docs/can.md); the bottom row the
AUX connector (right half), the mode logic and the camera's SPI (left half); the left column the
rack bus block (CAN transceiver, POS input), SERVICE, the camera's light, and its CS at the column's
rear end (IO4 since node v1.0: under the module along the B.Cu lane the DATA board's INT left;
IO8 before).  IO5, IO6 and IO8 are free.  The rack bus protocol runs on the CAN pins (`src/rack.c`, [docs/rack-protocol.md](../docs/rack-protocol.md)).
Strapping pins IO3/IO45/IO46 are not used; IO39–IO42 are the pad JTAG pins, free as GPIOs since
the node debugs over USB-Serial-JTAG.  The map is chosen so that an ESP32-S3-DevKitC-1 v1.1
(N8R8, the same module) takes it as is: every pin is on its headers, none is the octal PSRAM's
(IO35–IO37), and the status LED is the devkit's own RGB LED on IO38 (on a v1.0 devkit that LED is
on IO48, AUX_BOOT_CTL here: harmless).

`python3 firmware/tools/check_pinmap.py` checks this table and the board
devicetree against U3 in `design.py`; CI ([`firmware.yml`](../.github/workflows/firmware.yml))
runs it and builds both targets with warnings as errors on every push.

## Open items

What the firmware does not do yet, and what has not run on hardware: [docs/firmware.md › Open items](../docs/firmware.md#open-items).
