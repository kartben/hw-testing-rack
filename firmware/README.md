# Bay node firmware (Zephyr)

Firmware for the ESP32-S3 on each [bay node](../electronics/bay-node/design.py):
it exports the board under test (DUT) over the network with Zephyr's
**USB/IP host service**, switches and meters its 5 V, and gives remote access
to its console and RESET/BOOT lines.  It dogfoods Zephyr's new USB host stack
(`uhc_dwc2` on the ESP32-S3 OTG controller + `subsys/usb/host/usbip.c`).

> **Status:** builds against Zephyr main (4.5.0-rc2, pinned in
> [`west.yml`](west.yml)); **not yet run on hardware** — no bay node PCB has
> been assembled.  See [open items](#open-items).

```
firmware/
  west.yml                       west manifest (Zephyr main + hal_espressif + crypto)
  boards/hwtr/bay_node/          board definition: bay_node/esp32s3/procpu
  dts/bindings/                  hwtr,dut-port and hwtr,usb-mux bindings
  bay-node/                      the application
    boards/esp32s3_devkitc_procpu.overlay   stand-in: same pin map on a DevKitC-1
    wifi.conf.example            build-time Wi-Fi credentials (copy to wifi.conf)
```

## Building

A dedicated workspace, with this repository as the manifest repository:

```bash
west init -m https://github.com/kartben/hw-testing-rack --mf firmware/west.yml rack-ws
cd rack-ws
west update
west blobs fetch hal_espressif          # Wi-Fi binary blobs
west packages pip --install             # esptool & co. for the ESP32 build
west build -b bay_node/esp32s3/procpu hw-testing-rack/firmware/bay-node
```

The application adds `firmware/` to `BOARD_ROOT` and `DTS_ROOT` itself, so it
also builds from any existing Zephyr workspace at a recent `main` (with
`hal_espressif` blobs fetched):

```bash
west build -b bay_node/esp32s3/procpu path/to/hw-testing-rack/firmware/bay-node
```

No bay node yet?  An ESP32-S3-DevKitC-1 with the same GPIO map stands in
(status on the devkit's RGB LED, DUT on its "USB" port through an OTG adapter):

```bash
west build -b esp32s3_devkitc/esp32s3/procpu hw-testing-rack/firmware/bay-node
```

Wi-Fi credentials can be built in — handy to flash a whole rack:

```bash
cp hw-testing-rack/firmware/bay-node/wifi.conf.example hw-testing-rack/firmware/bay-node/wifi.conf   # edit it
west build -b bay_node/esp32s3/procpu hw-testing-rack/firmware/bay-node -- -DEXTRA_CONF_FILE=wifi.conf
```

`wifi.conf` is git-ignored.  On Windows keep the workspace and build
directory on a short path (e.g. `C:\rack-ws`): `hal_espressif` and
`tf-psa-crypto` have file paths long enough to hit `MAX_PATH`.

## Flashing

1. Slide the bay's **SERVICE** switch on and plug a laptop into the front
   **PC** port.  The firmware stops its USB host and hands the ESP32-S3's
   single USB PHY back to the USB-Serial-JTAG (LED yellow), which shows up
   as a serial port (and a JTAG adapter for OpenOCD).
2. `west flash` (esptool resets the chip into its ROM loader over USB).  On
   a blank module, or if the firmware is wedged, hold **BOOT** and tap
   **RESET** (reachable through the deck window) to force the ROM loader.
3. SERVICE off: the host controller restarts and the DUT is back on USB/IP.

## First boot

The shell runs on the UART test pads (TP1 = TXD0, TP2 = RXD0, 115200 8N1) and,
once the node is on the network, over telnet (port 23).

```console
uart:~$ wifi cred add -s MyLab -k 1 -p secret      # stored in flash (settings)
uart:~$ wifi cred auto_connect
uart:~$ bay id b3                                   # hostname bay-b3.local, stored
uart:~$ bay status
```

Then, from any Linux machine on the LAN:

```console
$ usbip list -r bay-b3.local
$ sudo usbip attach -r bay-b3.local -b 1-1
$ telnet bay-b3.local                     # bay shell
$ socat -,raw,echo=0 TCP:bay-b3.local:4000   # DUT console (AUX UART)
```

## What it does

| Feature | Implementation |
|---|---|
| USB/IP export of the DUT | `CONFIG_USBIP` on `zephyr_uhc0` (= `&usb_otg`, DWC2 host, ESP32-S3 FS quirk); TCP 3240; one device, bus id `1-<address>` (normally `1-1`) |
| DUT power | TPS2553 EN on IO6, kept **on** at boot (the board pulls it up); `bay power on/off/cycle` |
| Over-current | TPS2553 ~FAULT on IO7 (interrupt): logged and counted; after `CONFIG_BAY_DUT_FAULT_OFF_MS` (1 s) in current limit VBUS is switched off and the fault latched until `bay power on` |
| Telemetry | INA226 @ 0x40 through the Zephyr sensor API (`ti,ina226`, 50 mΩ, 50 µA/LSB, 16× averaging): bus mV, mA, mW in `bay power` / `bay status` |
| Data path | reads PC_DET (IO4) and SVC (IO5); `bay mode classic` drives MUX_FORCE_PC (IO10), persisted |
| SERVICE mode | stops the USB host and routes the internal PHY to the USB-Serial-JTAG (`CONFIG_BAY_SERVICE_PHY_HANDOVER`); restarts the host when SERVICE goes off |
| AUX | UART1 (IO17/IO18) ↔ raw TCP on port 4000 (one client); `bay aux <baud>`; RESET/BOOT open-drain pulses (IO11/IO12): `bay reset`, `bay boot` |
| Status LED | WS2812B on IO13 through the RMT (`worldsemi,ws2812-pulse-io`), see below |
| Buttons | BOOT (IO0) held ≥ 1 s once booted: DUT power cycle.  RESET is the ESP32's EN |
| Network | Wi-Fi station, DHCP, Wi-Fi credentials library (settings or build time), reconnects on its own; hostname `bay-<id>` answered over mDNS |
| Shell | `bay …` commands plus the stock `wifi`, `net` shells, on UART0 and telnet |

### Shell

| Command | Effect |
|---|---|
| `bay status` | id/hostname, IP, data path, USB host (devices, USB/IP sessions), power and V/I/P, fault count, AUX stats |
| `bay power` | DUT VBUS state and V/I/P |
| `bay power on` / `off` | switch DUT VBUS (`on` also clears a latched fault) |
| `bay power cycle [ms]` | off, wait (default 1000 ms), on |
| `bay reset [ms]` | pulse the DUT's RESET line low (default 100 ms) |
| `bay reset hold` / `release` | hold / release RESET |
| `bay boot` | hold BOOT, pulse RESET, release BOOT 200 ms later: ROM bootloader on most MCUs |
| `bay boot hold` / `release` | hold / release the BOOT strap |
| `bay mode [usbip\|classic]` | show, or force/release classic mode (persistent) |
| `bay aux [baud]` | show or set the AUX UART baud rate |
| `bay id [id]` | show or set the bay id (persistent), hostname `bay-<id>.local` |

### Network services

| Port | Service |
|---|---|
| TCP 3240 | USB/IP (`usbip list` / `usbip attach`) |
| TCP 23 | telnet shell (no authentication: keep the rack on a lab network) |
| TCP 4000 | AUX UART, raw bytes, one client (`CONFIG_BAY_AUX_TCP_PORT`) |
| UDP 5353 | mDNS: `bay-<id>.local` (default `bay<MAC>` until an id is set) |

### Status LED

| Colour | Meaning |
|---|---|
| off | no firmware / booting |
| red, blinking | DUT VBUS in current limit, or switched off by a fault |
| yellow | SERVICE: front port → node |
| magenta | classic: DUT → front port (laptop plugged, or `bay mode classic`) |
| dim white | DUT power switched off |
| orange, blinking | USB/IP mode, no network yet |
| dim blue | USB/IP ready, nothing enumerated on the DUT port |
| blue | USB/IP, DUT enumerated and exportable |
| green | USB/IP, a client is attached |

## Pin map

From `electronics/bay-node/design.py` (U3, ESP32-S3-MINI-1-N8); devicetree in
[`boards/hwtr/bay_node/bay_node.dtsi`](boards/hwtr/bay_node/bay_node.dtsi) and
[`bay_node-pinctrl.dtsi`](boards/hwtr/bay_node/bay_node-pinctrl.dtsi).

| ESP32-S3 | Net | Use | Devicetree |
|---|---|---|---|
| IO0 | BOOT | SW2 BOOT button (strapping pin, 10k pull-up); input once booted | `boot_button` (`sw0`), `gpio-keys` |
| IO4 | PC_DET | front port VBUS via 10k/20k: laptop plugged | `usb_mux` `pc-detect-gpios` |
| IO5 | SVC | SERVICE slide switch | `usb_mux` `service-gpios` |
| IO6 | DUT_EN | TPS2553 EN (100k pull-up: on without firmware) | `dut_port` `enable-gpios` |
| IO7 | DUT_FLT_N | TPS2553 ~FAULT (10k pull-up) | `dut_port` `fault-gpios` |
| IO8 | I2C_SDA | I²C0 → INA226 @ 0x40 (4.7k pull-ups) | `&i2c0`, `ina226` |
| IO9 | I2C_SCL | I²C0 | `&i2c0` |
| IO10 | MUX_FORCE_PC | OR gate → MUX_DUT SEL: force classic (100k pull-down) | `usb_mux` `force-pc-gpios` |
| IO11 | AUX_RST_CTL | 2N7002 Q2 → AUX RESET (open drain, 100k pull-down) | `dut_port` `reset-gpios` |
| IO12 | AUX_BOOT_CTL | 2N7002 Q3 → AUX BOOT (open drain, 100k pull-down) | `dut_port` `boot-gpios` |
| IO13 | LED_DIN | WS2812B (33 Ω), RMT channel 0 | `status_led` |
| IO14 | INA_ALERT_N | INA226 ~ALERT (10k pull-up), not used yet | `ina226` `alert-gpios` |
| IO17 | AUX_TX | UART1 TX → AUX pin 3 (1k) | `&uart1` (`dut_port` `uart`) |
| IO18 | AUX_RX | UART1 RX ← AUX pin 4 (1k) | `&uart1` |
| IO19 | ESP_DN | USB D−, internal FS PHY → MUX_DUT / MUX_PC | `zephyr_uhc0: &usb_otg` |
| IO20 | ESP_DP | USB D+ | `zephyr_uhc0: &usb_otg` |
| TXD0 (IO43) | U0TX | TP1, console + shell | `&uart0` |
| RXD0 (IO44) | U0RX | TP2 | `&uart0` |
| EN | EN | SW1 RESET button (10k/1µF) | — |

Strapping pins IO3/IO45/IO46 are not used.  The DevKitC overlay keeps this
map, moves the LED to the devkit's GPIO38 and disables SPI2 (IO10–IO13).

`python3 firmware/tools/check_pinmap.py` checks this table and the board
devicetree against U3 in `design.py`; CI ([`firmware.yml`](../.github/workflows/firmware.yml))
runs it and builds both targets with warnings as errors on every push.

## Open items

* **Hardware bring-up not done.**  Nothing here has run on a bay node yet:
  the board definition, the INA226 calibration, the LED timing and the
  SERVICE-mode PHY handover (stop host → route the PHY to USB-Serial-JTAG →
  restart host) are untested.
* **USB transfer types.**  The DWC2 host driver does control, bulk and
  interrupt IN; interrupt OUT, isochronous and split transactions (hubs) are
  not implemented yet.  Probes with an interrupt OUT endpoint, UAC/UVC
  devices and DUTs behind an on-board hub won't work over USB/IP.
* **USB/IP service** is experimental upstream: one device per controller,
  fixed bus id `1-<address>`, no access control.
* **Not yet written:** REST API (`/api/power`, `/api/mode`) and Prometheus
  `/metrics`, DNS-SD advertisement of `_usbip._tcp`, MCUboot + mcumgr OTA
  (the partition table already has two 3.75 MB slots), the shell on the
  USB-Serial-JTAG in SERVICE mode, INA226 alert handling, tri-stating AUX TX
  while the DUT is off.
