# Firmware

The bay nodes and the power hub run **Zephyr** — the shelf doubles as a
dogfooding rig for Zephyr's new USB host stack.  The firmware lives in
[`firmware/`](../firmware/): the bay node
([`firmware/README.md`](../firmware/README.md): build, flashing, shell, pin
map), the power hub ([`firmware/power-hub/README.md`](../firmware/power-hub/README.md)),
and what they share ([`firmware/common`](../firmware/common/)): the rack bus
protocol ([rack-protocol.md](rack-protocol.md)), the AP33772S drivers,
Wi-Fi, the web pages' CSS, helpers and tooling.

> **Status:** both boards and applications build against Zephyr main
> (pinned in `firmware/west.yml`); the rack bus protocol runs on a simulated
> rack (native_sim); hardware bring-up has not started.

## What Zephyr provides (main, Oct 2026)

* **USB/IP host service** — `subsys/usb/host/usbip.c`: exports a device
  attached to a host controller to a Linux `usbip` client.  Experimental,
  one device per controller (exactly our 1-board-per-node topology).  Docs:
  *Services → USB → USB/IP protocol support*.
* **DWC2 host controller driver** — `drivers/usb/uhc/uhc_dwc2.c` with the
  ESP32-S3 full-speed OTG quirk (`espressif,esp32-usb-otg-fs`), merged via
  zephyrproject-rtos/zephyr#102967 and follow-ups (tracking issue #102931).
  Control, bulk and interrupt IN transfers; interrupt OUT, isochronous and
  split transactions (hubs) are not implemented yet.
* Wi-Fi, mDNS, telnet shell, settings, HTTP server, Prometheus library,
  `ti,ina226` sensor driver, `worldsemi,ws2812-pulse-io` LED strip on the
  RMT: all used by the node application.  MCUboot + mcumgr OTA is available
  but not used yet.

## Board and application

| | |
|---|---|
| Board | `bay_node/esp32s3/procpu` in `firmware/boards/hwtr/bay_node/` (ESP32-S3-MINI-1-N8, 8 MB, two 3.75 MB image slots), pin map from `electronics/bay-node/design.py` |
| Bindings | `hwtr,dut-port` (TPS2553 EN/FAULT, AUX RESET/BOOT, INA226, AUX UART), `hwtr,usb-mux` (MUX_FORCE_PC, PC_DET, SVC) |
| Stand-in | `esp32s3_devkitc/esp32s3/procpu` + `firmware/bay-node/boards/esp32s3_devkitc_procpu.overlay` (same GPIO map) |
| Bench node | `m5stack_stamps3/esp32s3/procpu` + `firmware/bay-node/boards/m5stack_stamps3_procpu.*`: serial console, network and web page on a StampS3, no USB host (its USB-C is the node's console) |
| Application | `firmware/bay-node/` |
| Power hub | `power_hub/esp32s3/procpu` in `firmware/boards/hwtr/power_hub/`, application `firmware/power-hub/`, bindings `hwtr,power-hub`, `hwtr,rack-rows`, `diodes,ap33772s` (+ `-regulator`, `-sensor`) |
| Shared | `firmware/zephyr/module.yml` makes `firmware/` a Zephyr module (boards, bindings, `common/`), added by each application |
| Host side | [`tools/bayctl.py`](../tools/bayctl.py): power, reset, USB/IP, consoles, twister hardware map, labgrid / PDUDaemon configs ([ci.md](ci.md)) |
| Build | `west build -b bay_node/esp32s3/procpu hw-testing-rack/firmware/bay-node` in a workspace made from `firmware/west.yml` |

## Node application

| Feature | Status | How |
|---|---|---|
| USB/IP export of the DUT | written | `CONFIG_USBIP=y`, `zephyr_uhc0` → OTG controller; client: `usbip attach -r bay-<id>.local -b 1-1` |
| Power control | written | IO41 → TPS2553 EN, kept on at boot (pull-up: the board is on before the firmware runs); `bay power on/off/cycle` |
| Over-current | written | FAULT on IO40 (interrupt): logged, counted, VBUS cut and latched after 1 s in current limit |
| Telemetry | written | INA226 (0x40, 50 mΩ) through the sensor API → V, I, P in the shell, `GET /api/status` and Prometheus `/metrics` |
| Modes | written | reads PC_DET (IO13) and SVC (IO15); `bay mode classic\|usbip` drives MUX_FORCE_PC (IO14), persisted in settings |
| SERVICE mode | written | stops the USB host and gives the ESP32-S3's single PHY back to the USB-Serial-JTAG (flash/JTAG from the front port); restarts it afterwards |
| AUX console | written, host-tested | UART1 (IO47/IO33) shared by a web console in the status page (xterm.js over a WebSocket, 16 KB replayed to late clients), an RFC 2217 server on port 4001 (pyserial, labgrid, esptool) and raw TCP on port 4000; baud/format/Enter/echo saved per bay; BREAK; TX released while the DUT is off |
| AUX RESET/BOOT | written | pulses on IO34/IO48 (`bay reset`, `bay boot`, console buttons), optionally RFC 2217 DTR/RTS like an ESP auto-reset circuit |
| Status LED | written | WS2812B on IO13 (RMT): fault / service / classic / power off / no network / USB/IP idle / enumerated / attached |
| Identity | written | `bay id <id>` (settings) → hostname `bay-<id>.local` over mDNS; without an id, the rack position from the hub (`bay-c3.local`) |
| Rack bus | written, tested on a simulated rack | CAN (IO18/IO17) + POS (IO16 in, IO35 out): position from the hub (`C3` = node 0x23), STATUS every second, INFO, ALERT on DUT faults, the hub's commands (refused while the bay is reserved); [rack-protocol.md](rack-protocol.md) |
| Access control | written, tested on native_sim | per node: which address may use status, control, console, USB/IP, shell (Zephyr packet filter for TCP, a check per HTTP request); a CI reservation (lease); kicks and a refusal log; admin key claimed with a press on BOOT, admin requests signed (HMAC).  See [`firmware/README.md`](../firmware/README.md#access-control) |
| Control interface | written | `bay …` shell on the UART test pads and over telnet; status page, serial console and JSON API on `http://bay-<id>.local/` (`/api/power`, `/api/reset`, `/api/boot`, `/api/mode`, `/api/aux`) |
| Updates | not yet | MCUboot + mcumgr over UDP; for now `west flash` through the front port in SERVICE mode |

![The node's status page (simulated node): live V/I/P, power and reset actions, USB/IP state](img/web-ui-dark.png)

*The status page at `http://bay-<id>.local/`, here with a USB/IP client
attached and the node not claimed yet (open).  More states and the API in
[`firmware/README.md`](../firmware/README.md#web-page-and-api), access
control in [its own section](../firmware/README.md#access-control).*

![Screencast of the web console: a Zephyr shell on the DUT, tab completion, a baud rate change, RESET rebooting the DUT](img/web-console.webp)

*The DUT's serial console in the same page, recorded on native_sim (the
node's real console code, Zephyr's shell sample as the DUT); details in
[`firmware/README.md`](../firmware/README.md#serial-console).*

## Power hub application

| Feature | Status | How |
|---|---|---|
| USB-C PD | written, compile-tested | VBUS on the ADC, I²C pull-ups on once VBUS is up, the AP33772S drivers initialized then (`zephyr,deferred-init`); asks for 28 V EPR when offered, else 20 V; never above 28 V (`regulator-max-microvolt`) |
| Rows | written | eFuse enables held across a controller reset (pad hold); off until the contract has held 500 ms, then staggered (300 ms); `hub row <A–D> on\|off\|cycle`, the page, `POST /api/row` |
| Shedding | written | from the measured row currents (IMON): above 90 % of the contract for 1 s the next row in the shed order goes off, back when the contract has room again |
| Faults | written | each eFuse's FLT and the PD sink's protections as events |
| Rack bus master | written, tested on a simulated rack | enumeration over the POS tokens, the node table, commands with retries, the RACK frame every second |
| Web, shell | written | status page (PD offers, rows and their bays, rack bus, events), JSON API, `/metrics`, `hub …` shell on the console USB-C (no telnet) |
| Access | written | reading is open; the page's actions (rows, contract, enumeration, node commands) are admin requests signed with the hub's key, claimed with a press on its BOOT button (`firmware/common/lib/admin.c`, as the bay nodes) |

![The hub's status page (simulated hub): the PD contract and the charger's offers, the rack bus, rows A–D with their bays](img/hub-ui-dark.png)

*The hub's page at `http://rack-<id>.local/`; the rows and the bays link
to each bay's own page.  More in
[`firmware/power-hub/README.md`](../firmware/power-hub/README.md).*

## Flashing a node

1. Slide the bay's **SERVICE** switch on (fascia).  The firmware stops its
   USB host and routes the ESP32-S3's PHY to the USB-Serial-JTAG (LED
   yellow).
2. Plug a laptop into the bay's front **PC** port: the USB-Serial-JTAG
   appears (`/dev/ttyACM*`).
3. `west flash` (esptool auto-reset works over USB-Serial-JTAG).  A blank or
   wedged node: hold **BOOT**, tap **RESET** (both within reach once the
   drawer is pulled out: the tray is open above the node) to enter the ROM loader.
4. SERVICE off: the DUT is back on the ESP32's USB OTG.

First boot: set the Wi-Fi credentials and the bay id from the UART test pads
(TP1/TP2), or build the credentials in — see `firmware/README.md`.

## Open items

* **Hardware bring-up** — nothing has run on a bay node yet (board
  definition, INA226 calibration, LED timing, SERVICE PHY handover).
* **Interrupt OUT / isochronous transfers and hubs** in `uhc_dwc2`: needed
  for some debug probes, audio/video class DUTs and boards with an on-board
  hub.
* **Serial console on hardware**: the RFC 2217 server is tested on the host
  against pyserial and the web console against the simulated node; on a
  StampS3 the firmware boots with its listeners up and the UART path works
  in loopback, but the WebSocket and TCP paths have not run over Wi-Fi yet.
* DNS-SD (`_usbip._tcp`, `_http._tcp`, `_rfc2217._tcp`), MCUboot/mcumgr OTA,
  shell on the USB-Serial-JTAG in SERVICE mode, INA226 alert.
* Upstream nits seen while dogfooding: the Prometheus library needs exactly
  one label per metric and rejects negative gauge values; the HTTP server
  shares one WebSocket data buffer per resource (one resource per console
  slot works around it).

## Camera pods

XIAO ESP32S3 Sense, Zephyr board `xiao_esp32s3/esp32s3/procpu/sense`
(OV2640 on the LCD_CAM DVP interface).  `samples/subsys/video/capture` works;
an MJPEG/TCP streamer (cf. `tcpserversink`) is the obvious next step.
