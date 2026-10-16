# Firmware (plan)

The bay nodes are meant to run **Zephyr** — the shelf doubles as a dogfooding
rig for Zephyr's new USB host stack.

## What exists upstream (Zephyr main, Oct 2026)

* **USB/IP host service** — `subsys/usb/host/usbip.c`: exports a device
  attached to a host controller to a Linux `usbip` client.  Still marked
  under development, one device per controller (exactly our 1-board-per-node
  topology).  Docs: *Services → USB → USB/IP protocol support*.
* **DWC2 host controller driver** — `drivers/usb/uhc/uhc_dwc2.c` with the
  ESP32-S3 full-speed OTG quirk (`espressif,esp32-usb-otg-fs`), merged via
  zephyrproject-rtos/zephyr#102967 and follow-ups (tracking issue #102931).
  Control and bulk transfers today; interrupt/isochronous and split
  transactions are follow-ups — check them before relying on CDC-ACM
  notifications or HID-class probes.
* Wi-Fi, mDNS, HTTP server, shell, `ti,ina226` sensor driver, `worldsemi,ws2812-*`
  LED strip, MCUboot + mcumgr OTA: all available for ESP32-S3.

## Node application (to write: `firmware/bay-node/`)

| Feature | How |
|---|---|
| USB/IP export of the DUT | `CONFIG_USBIP=y`, `zephyr_uhc0` → OTG controller; client: `usbip attach -r bay-<id>.local -b 1-1` |
| Power control | GPIO IO6 → TPS2553 EN (pull-up: board is on even before boot); FAULT on IO7 |
| Telemetry | INA226 (0x40, 50 mΩ) → V, I, P; REST `GET /api/power`, Prometheus `/metrics` |
| Modes | read PC_DET (IO4) and SVC (IO5); `POST /api/mode {classic|usbip}` drives MUX_FORCE_PC (IO10) |
| AUX | UART1 (IO17/18) ↔ TCP (RFC 2217-ish raw socket), RESET/BOOT pulses on IO11/IO12 |
| Status LED | WS2812B on IO13: off / USB/IP idle / attached / classic / fault |
| Identity | bay id from the carrier (stored in settings on first boot), `bay-<id>.local` via mDNS |
| Updates | MCUboot + mcumgr over UDP; first flash through the front port in SERVICE mode |

Suggested `west.yml`-based app layout and a board overlay for the node will
come with the first firmware PR.

## Flashing a node the first time

1. Slide the bay's **SERVICE** switch on (fascia).
2. Plug a laptop into the bay's front **PC** port: the ESP32-S3's
   USB-Serial-JTAG appears (`/dev/ttyACM*`).
3. `west flash` (esptool auto-reset works over USB-Serial-JTAG; the BOOT and
   RESET buttons are reachable through the deck window if needed).
4. SERVICE off: the DUT is back on the ESP32's USB OTG.

## Camera pods

XIAO ESP32S3 Sense, Zephyr board `xiao_esp32s3/esp32s3/procpu/sense`
(OV2640 on the LCD_CAM DVP interface).  `samples/subsys/video/capture` works;
an MJPEG/TCP streamer (cf. `tcpserversink`) is the obvious next step.
