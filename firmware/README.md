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
    boards/m5stack_stamps3_procpu.*         bench node on a StampS3: console + network, no USB host
    web/index.html               status page and serial console (embedded gzipped)
    web/vendor/xterm/            xterm.js 6.0.0 + fit addon (MIT), served from flash
    web/dev_server.py            the page against a simulated node, to work on the UI
    tests/rfc2217/               host test of the RFC 2217 server against pyserial
    tests/console_sim/           the console, web server and RFC 2217 code on native_sim, with a Zephyr DUT
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

An M5Stack StampS3 is an even smaller bench node for the serial console and
the network side: no muxes, INA226 or USB host, and its USB-C port carries
the node's shell and logs (USB-Serial-JTAG).  The AUX UART and the
RESET/BOOT lines are on header pins (G1/G2, G4/G5; the map is in
[the overlay](bay-node/boards/m5stack_stamps3_procpu.overlay)), and
`bay aux loopback on` loops the UART back on itself to try the console
without a DUT:

```bash
west build -b m5stack_stamps3/esp32s3/procpu hw-testing-rack/firmware/bay-node
west flash --erase    # over its USB-C port; --erase once, see below
```

A module that ran other firmware may hold something else where the
settings live (`settings unavailable (-45)` at boot, nothing saved): erase
the flash once (`west flash --erase`, or just the `storage` partition).

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
$ open http://bay-b3.local/                # status page and DUT console
$ telnet bay-b3.local                     # bay shell
$ python -m serial.tools.miniterm rfc2217://bay-b3.local:4001 115200   # DUT console
```

## What it does

| Feature | Implementation |
|---|---|
| USB/IP export of the DUT | `CONFIG_USBIP` on `zephyr_uhc0` (= `&usb_otg`, DWC2 host, ESP32-S3 FS quirk); TCP 3240; one device, bus id `1-<address>` (normally `1-1`) |
| DUT power | TPS2553 EN on IO41, kept **on** at boot (the board pulls it up); `bay power on/off/cycle` |
| Over-current | TPS2553 ~FAULT on IO40 (interrupt): logged and counted; after `CONFIG_BAY_DUT_FAULT_OFF_MS` (1 s) in current limit VBUS is switched off and the fault latched until `bay power on` |
| Telemetry | INA226 @ 0x40 through the Zephyr sensor API (`ti,ina226`, 50 mΩ, 50 µA/LSB, 16× averaging): bus mV, mA, mW in `bay power` / `bay status` |
| Data path | reads PC_DET (IO13) and SVC (IO15); `bay mode classic` drives MUX_FORCE_PC (IO14), persisted |
| SERVICE mode | stops the USB host and routes the internal PHY to the USB-Serial-JTAG (`CONFIG_BAY_SERVICE_PHY_HANDOVER`); restarts the host when SERVICE goes off |
| AUX console | UART1 (IO47 TX / IO33 RX), interrupt driven, shared by the web console (WebSocket, xterm.js), an RFC 2217 server (port 4001) and raw TCP (port 4000); settings persisted per bay; BREAK; TX released while the DUT is off.  See [Serial console](#serial-console) |
| AUX RESET/BOOT | open-drain pulses (IO34/IO48): `bay reset`, `bay boot`, the console's buttons, optionally RFC 2217 DTR/RTS (esptool) |
| Status LED | WS2812B on IO12 through the RMT (`worldsemi,ws2812-pulse-io`), see below |
| Buttons | BOOT (IO0) held ≥ 1 s once booted: DUT power cycle.  RESET is the ESP32's EN |
| Network | Wi-Fi station, DHCP, Wi-Fi credentials library (settings or build time), reconnects on its own; hostname `bay-<id>` answered over mDNS |
| Shell | `bay …` commands plus the stock `wifi`, `net` shells, on UART0 and telnet |
| Web | Zephyr HTTP server on port 80: status page, JSON API (same actions as the shell), Prometheus `/metrics` through Zephyr's Prometheus library |

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
| `bay aux` | AUX UART settings, consoles connected, byte counters |
| `bay aux <baud> [8N1]` | set and save the AUX UART baud rate and format (`7E1`, `8O2`, …) |
| `bay aux break [ms]` | hold the DUT's RX line low (default 250 ms) |
| `bay aux send <text>` | send a line to the DUT (with the console's Enter) |
| `bay aux loopback [on\|off]` | test without a DUT: the UART loops its TX back to its RX (ESP32) |
| `bay id [id]` | show or set the bay id (persistent), hostname `bay-<id>.local` |

### Network services

| Port | Service |
|---|---|
| TCP 3240 | USB/IP (`usbip list` / `usbip attach`) |
| TCP 80 | status page, serial console (WebSocket `/console/ws/<n>`), JSON API, `/metrics` (`CONFIG_BAY_HTTP_PORT`) |
| TCP 23 | telnet shell (no authentication: keep the rack on a lab network) |
| TCP 4001 | AUX UART, RFC 2217, one client (`CONFIG_BAY_RFC2217_PORT`) |
| TCP 4000 | AUX UART, raw bytes, one client (`CONFIG_BAY_AUX_TCP_PORT`) |
| UDP 5353 | mDNS: `bay-<id>.local` (default `bay<MAC>` until an id is set) |

### Web page and API

`http://bay-<id>.local/` is a single self-contained page: plain HTML, CSS and
an ES module, no framework or CDN, about 9 KB gzipped in flash (plus
xterm.js for the console, below).  It follows the browser's light/dark
theme, polls `/api/status` every 2 s while visible, and offers the shell's
main actions.

![Status page of bay B3, dark theme: VBUS on with live V/I/P and a current sparkline, a USB/IP client attached](../docs/img/web-ui-dark.png)

| ![Status page, light theme: the DUT is enumerated and ready to be attached](../docs/img/web-ui-light.png) | ![Status page after an over-current trip: red banner with a Power on button, VBUS off](../docs/img/web-ui-fault.png) |
|---|---|
| Light theme, DUT enumerated and ready to attach | Over-current: VBUS cut by the firmware |

| Endpoint | |
|---|---|
| `GET /api/status` | everything `bay status` shows, as JSON |
| `POST /api/power` | `{"action": "on" \| "off" \| "cycle", "ms": 1000}` |
| `POST /api/reset` | `{"ms": 100}` (body optional) |
| `POST /api/boot` | DUT into its bootloader (BOOT held across a RESET pulse) |
| `POST /api/mode` | `{"mode": "usbip" \| "classic"}` (persistent) |
| `GET /api/aux` | AUX UART settings, consoles connected, byte counters |
| `POST /api/aux` | any of `{"baud": 115200, "data_bits": 8, "parity": "none" \| "odd" \| "even", "stop_bits": 1, "enter": "cr" \| "lf" \| "crlf", "echo": false, "esptool_reset": false}`, applied and saved; answers with `GET /api/aux` |
| `POST /api/aux/break` | `{"ms": 250}` (body optional) |
| `GET /console/ws/<n>` | WebSocket to the AUX UART, `n` < `CONFIG_BAY_CONSOLE_WEB_CLIENTS` (see below) |
| `GET /metrics` | Prometheus: `bay_dut_vbus_volts`, `bay_dut_current_amperes`, `bay_dut_power_watts`, `bay_dut_power_on`, `bay_dut_fault`, `bay_dut_faults_total`, `bay_usb_devices`, `bay_usbip_sessions`, `bay_aux_{rx,tx}_bytes_total`, all labelled `bay="<id>"` |

Every other POST answers with the new status document; errors come back as
`{"error": "..."}` with a 4xx status.  Like telnet, there is no
authentication.

```console
$ curl -s bay-b3.local/api/status | jq .dut
$ curl -s -X POST bay-b3.local/api/power -d '{"action":"cycle","ms":2000}'
$ curl -s bay-b3.local/metrics
```

To work on the page without a node, `python firmware/bay-node/web/dev_server.py`
serves it on <http://localhost:8766> with a simulated node, console included
(a fake Zephyr board that boots, logs in colour and runs a small shell;
`/dev/fault` trips a fake over-current, `/dev/attach` toggles a fake USB/IP
client).  The screenshots come from that simulation:
`python firmware/bay-node/web/screenshots.py` (Playwright and an installed
Chrome or Edge) regenerates `docs/img/web-ui-*.png`.

## Serial console

The DUT's console on the AUX connector (UART1) is reachable three ways at
once.  Everything the board sends goes to every client; everything a client
sends goes to the board, so with several writers the keystrokes simply
interleave: one person typing at a time is the rule.

| Client | How | Port settings |
|---|---|---|
| Web console | the Console card of the status page (xterm.js over a binary WebSocket), up to `CONFIG_BAY_CONSOLE_WEB_CLIENTS` (2) browsers | the page's ⚙ panel: applied at once and saved for the bay (Zephyr settings) |
| RFC 2217 | one client on TCP 4001: pyserial `rfc2217://`, labgrid `NetworkSerialPort`, esptool | set by the client for its session; the saved ones come back when it disconnects |
| Raw TCP | one client on TCP 4000: `socat`, `nc` | the saved ones |

![Screencast of the web console: the DUT's Zephyr shell answers help and kernel version (with tab completion), the baud rate is changed from the settings panel, RESET reboots the DUT and its boot banner appears](../docs/img/web-console.webp)

*Recorded on [native_sim](bay-node/tests/console_sim/): the node's real
console, web server and RFC 2217 code, with Zephyr's shell sample running
as the DUT on its AUX UART.  `python firmware/bay-node/web/screencast.py
--workspace <west workspace>` records it again (Docker, Playwright, ffmpeg).*

**Web console.**  Raw bytes both ways, so full VT100/xterm escape
sequences and UTF-8 work.  The node keeps the last
`CONFIG_BAY_AUX_LOG_SIZE` (16 KB) received in RAM and replays them to a
browser that connects, so a page opened after a crash still shows it; a page
that reconnects (Wi-Fi hiccup) skips what it already shows, and marks a node
reboot.  Next to the terminal: RESET and BOOT pulses, DUT power off/on/cycle,
BREAK, timestamps (added by the browser to each line), clear, and download
of everything received since the page opened.  The ⚙ panel sets the baud
rate (9600–921600 or any value from 300 to 5 M), data bits, parity, stop
bits, what Enter sends (CR, LF, CR LF), local echo, and whether RFC 2217
DTR/RTS drive BOOT/RESET.  Default: 115200 8N1, CR, no echo.

**RFC 2217.**  Telnet with the Com Port Control option (baud, data bits,
parity none/odd/even, stop bits 1/2, BREAK, DTR/RTS, purge); mark/space
parity, 1.5 stop bits and flow control are refused, as a client expects.

```console
$ python -m serial.tools.miniterm rfc2217://bay-b3.local:4001 115200
$ esptool --port 'rfc2217://bay-b3.local:4001' chip-id    # with "DTR/RTS drive BOOT/RESET" on
```

```yaml
# labgrid
NetworkSerialPort:
  host: bay-b3.local
  port: 4001
  speed: 115200
  protocol: rfc2217
```

With *DTR/RTS drive BOOT/RESET* on, the lines behave like the two-transistor
auto-reset circuit of ESP32 boards (RESET while RTS and not DTR, BOOT while
DTR and not RTS), so esptool can reset an ESP32 DUT into its ROM loader and a
terminal that raises both lines leaves the board alone.  Off by default.

**BREAK and the TX line.**  BREAK holds the board's RX line low (`tx-gpios`
of `hwtr,dut-port` takes the pin from the UART for the duration).  While the
DUT is powered off the same pin is released (input), so the node does not
feed the unpowered board through its RX pin; it goes back to the UART when
the power comes back.

**Cost.**  About +170 KB of flash (xterm.js and its CSS, 91 KB gzipped, the
WebSocket and console code) and +25 KB of RAM: the 16 KB receive log, a
1 KB transmit ring, one 3 KB thread for all the console sockets, two
WebSocket contexts and their buffers, two more TCP contexts.  Static data
RAM is now at 95 % (379 of 399 KB, heaps included).  The knobs, if a
feature needs RAM later: `CONFIG_BAY_AUX_LOG_SIZE`,
`CONFIG_BAY_CONSOLE_WEB_CLIENTS`, and `CONFIG_USBIP_BUF_POOL_SIZE` (64 KB by
default upstream, the largest single buffer in the image).

The RFC 2217 server ([`src/rfc2217.c`](bay-node/src/rfc2217.c)) has no Zephyr
dependency and is tested on the host against pyserial's client, with a
looped-back "UART":

```bash
pip install pyserial
python firmware/bay-node/tests/rfc2217/test_rfc2217.py      # needs a C compiler (CC, default gcc)
```

The whole console also runs on native_sim, no hardware needed (Linux, or the
Zephyr build image in Docker as `screencast.py` does):
[`tests/console_sim`](bay-node/tests/console_sim/) builds `aux_console.c`,
`rfc2217.c` and `web.c` with the hardware stubbed and host sockets (NSOS),
and `run.py` starts it next to Zephyr's shell sample, wired to its AUX UART
as the DUT; RESET and the power buttons restart or stop that DUT.

```bash
python3 firmware/bay-node/tests/console_sim/run.py --workspace <west workspace> --build <dir>
# http://localhost/ (port 80), rfc2217://localhost:4001
```

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
| IO12 | LED_DIN | WS2812B (33 Ω), RMT channel 0 | `status_led` |
| IO13 | PC_DET | front port VBUS via 10k/20k: laptop plugged | `usb_mux` `pc-detect-gpios` |
| IO14 | MUX_FORCE_PC | OR gate → MUX_DUT SEL: force classic (100k pull-down) | `usb_mux` `force-pc-gpios` |
| IO15 | SVC | SERVICE slide switch | `usb_mux` `service-gpios` |
| IO19 | ESP_DN | USB D−, internal FS PHY → MUX_DUT / MUX_PC | `zephyr_uhc0: &usb_otg` |
| IO20 | ESP_DP | USB D+ | `zephyr_uhc0: &usb_otg` |
| IO33 | AUX_RX | UART1 RX ← AUX pin 4 (1k) | `&uart1` |
| IO34 | AUX_RST_CTL | 2N7002 Q2 → AUX RESET (open drain, 100k pull-down) | `dut_port` `reset-gpios` |
| IO37 | I2C_SCL | I²C0 | `&i2c0` |
| IO38 | I2C_SDA | I²C0 → INA226 @ 0x40 (4.7k pull-ups) | `&i2c0`, `ina226` |
| IO39 | INA_ALERT_N | INA226 ~ALERT (10k pull-up), not used yet | `ina226` `alert-gpios` |
| IO40 | DUT_FLT_N | TPS2553 ~FAULT (10k pull-up) | `dut_port` `fault-gpios` |
| IO41 | DUT_EN | TPS2553 EN (100k pull-up: on without firmware) | `dut_port` `enable-gpios` |
| IO47 | AUX_TX | UART1 TX → AUX pin 3 (1k) | `&uart1` (`dut_port` `uart`) |
| IO48 | AUX_BOOT_CTL | 2N7002 Q3 → AUX BOOT (open drain, 100k pull-down) | `dut_port` `boot-gpios` |
| TXD0 (IO43) | U0TX | TP1, console + shell | `&uart0` |
| RXD0 (IO44) | U0RX | TP2 | `&uart0` |
| EN | EN | SW1 RESET button (10k/1µF) | — |

Each signal sits on the module edge that faces where it goes on the board (v0.4): the right
column feeds the DUT power block, the bottom-right pins the AUX connector, the bottom-left pins
the mode logic and the LED.  Strapping pins IO3/IO45/IO46 are not used; IO39–IO42 are the pad
JTAG pins, free as GPIOs since the node debugs over USB-Serial-JTAG.  The DevKitC overlay keeps
this map except I²C (IO8/IO9 there: the devkit's LED is on IO38 and its octal PSRAM takes
IO35–IO37), moves the LED to the devkit's GPIO38 and disables SPI2 (IO10–IO13).

`python3 firmware/tools/check_pinmap.py` checks this table and the board
devicetree against U3 in `design.py`; CI ([`firmware.yml`](../.github/workflows/firmware.yml))
runs it and builds both targets with warnings as errors on every push.

## Open items

* **Hardware bring-up not done.**  Nothing here has run on a bay node yet:
  the board definition, the INA226 calibration, the LED timing and the
  SERVICE-mode PHY handover (stop host → route the PHY to USB-Serial-JTAG →
  restart host) are untested.
* **Serial console: tested off the board only.**  The RFC 2217 server
  passes its host test against pyserial; the console, WebSocket and web
  server code ran on native_sim with a Zephyr DUT (the screencast), over host
  sockets rather than the node's Wi-Fi/TCP stack.  That run found that a
  browser's keep-alive connections can hold all 3 HTTP client slots (the
  server then stops accepting, the console's WebSocket waits), hence the 3 s
  idle timeout in `prj.conf`; whether it is enough on the node is untested
  (on native_sim the idle timeout cannot free a slot at all, so the
  simulation uses 8 slots).  On a StampS3 (no Wi-Fi credentials yet): it
  boots, the HTTP, RFC 2217, raw TCP and telnet listeners are up, the AUX
  settings persist, and with `bay aux loopback on` every byte sent comes
  back at 115200 and 921600, also with the DUT "off"; 22 KB of system heap
  free before Wi-Fi connects, the console thread at 768 of 3072 bytes of
  stack with no client.  Not yet over the network.  To check on a DevKitC with a
  USB-UART adapter on IO47/IO33: throughput at 921600 baud, the console
  thread's stack (3 KB, unmeasured), BREAK and the TX release on power off
  with a scope, two browsers plus miniterm at once, esptool flashing an ESP32
  DUT through RFC 2217.
* **USB transfer types.**  The DWC2 host driver does control, bulk and
  interrupt IN; interrupt OUT, isochronous and split transactions (hubs) are
  not implemented yet.  Probes with an interrupt OUT endpoint, UAC/UVC
  devices and DUTs behind an on-board hub won't work over USB/IP.
* **USB/IP service** is experimental upstream: one device per controller,
  fixed bus id `1-<address>`, no access control.
* **Not yet written:** DNS-SD advertisement of `_usbip._tcp`, `_http._tcp`
  and `_rfc2217._tcp`, MCUboot + mcumgr OTA (the partition table already has
  two 3.75 MB slots), the shell on the USB-Serial-JTAG in SERVICE mode,
  INA226 alert handling, RFC 2217 line/modem state notifications (the server
  answers polls with CTS/DSR/CD up).
* **Zephyr's HTTP server** registers every WebSocket of a resource with that
  resource's one data buffer, so two consoles on one resource would share
  it: the firmware declares one resource per console slot instead.
* **Zephyr's Prometheus library** wants exactly one label per metric and
  refuses negative gauge values (the INA226 reads a few mA below zero at no
  load), so the firmware labels everything `bay="<id>"` and clamps at 0.
