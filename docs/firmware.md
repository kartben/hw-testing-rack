# Firmware

The bay nodes run **Zephyr** — the shelf doubles as a dogfooding rig for
Zephyr's new USB host stack.  The firmware lives in [`firmware/`](../firmware/)
(build, flashing, shell, pin map: [`firmware/README.md`](../firmware/README.md)).

> **Status:** the board definition and the application build against Zephyr
> main (pinned in `firmware/west.yml`); hardware bring-up has not started.

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
| Application | `firmware/bay-node/` |
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
| AUX | written | UART1 (IO47/IO33) ↔ raw TCP port 4000; RESET/BOOT pulses on IO34/IO48 (`bay reset`, `bay boot`) |
| Status LED | written | WS2812B on IO13 (RMT): fault / service / classic / power off / no network / USB/IP idle / enumerated / attached |
| Identity | written | `bay id <id>` (settings) → hostname `bay-<id>.local` over mDNS |
| Control interface | written | `bay …` shell on the UART test pads and over telnet; status page and JSON API on `http://bay-<id>.local/` (`/api/power`, `/api/reset`, `/api/boot`, `/api/mode`) |
| Updates | not yet | MCUboot + mcumgr over UDP; for now `west flash` through the front port in SERVICE mode |

![The node's status page (simulated node): live V/I/P, power and reset actions, USB/IP state](img/web-ui-dark.png)

*The status page at `http://bay-<id>.local/`, here with a USB/IP client
attached.  More states and the API in
[`firmware/README.md`](../firmware/README.md#web-page-and-api).*

## Flashing a node

1. Slide the bay's **SERVICE** switch on (fascia).  The firmware stops its
   USB host and routes the ESP32-S3's PHY to the USB-Serial-JTAG (LED
   yellow).
2. Plug a laptop into the bay's front **PC** port: the USB-Serial-JTAG
   appears (`/dev/ttyACM*`).
3. `west flash` (esptool auto-reset works over USB-Serial-JTAG).  A blank or
   wedged node: hold **BOOT**, tap **RESET** (both reachable through the
   deck window) to enter the ROM loader.
4. SERVICE off: the DUT is back on the ESP32's USB OTG.

First boot: set the Wi-Fi credentials and the bay id from the UART test pads
(TP1/TP2), or build the credentials in — see `firmware/README.md`.

## Open items

* **Hardware bring-up** — nothing has run on a bay node yet (board
  definition, INA226 calibration, LED timing, SERVICE PHY handover).
* **Interrupt OUT / isochronous transfers and hubs** in `uhc_dwc2`: needed
  for some debug probes, audio/video class DUTs and boards with an on-board
  hub.
* DUT console in the web page (WebSocket), DNS-SD (`_usbip._tcp`,
  `_http._tcp`), MCUboot/mcumgr OTA, shell on the USB-Serial-JTAG in SERVICE
  mode, INA226 alert.
* Upstream nits seen while dogfooding: the Prometheus library needs exactly
  one label per metric and rejects negative gauge values.

## Camera pods

XIAO ESP32S3 Sense, Zephyr board `xiao_esp32s3/esp32s3/procpu/sense`
(OV2640 on the LCD_CAM DVP interface).  `samples/subsys/video/capture` works;
an MJPEG/TCP streamer (cf. `tcpserversink`) is the obvious next step.
