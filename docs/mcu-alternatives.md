# Bay node MCU: alternatives to the ESP32-S3

**Decision (2026-10-16): v1 keeps the ESP32-S3-MINI-1-N8.** An Ai-Thinker
module with a Bouffalo Lab BL616 is the most interesting candidate for a v2:
it is cheaper to assemble at JLC and has a high-speed USB controller. But
Zephyr has no USB host driver for it yet, and USB host is the node's main
job. This note records why, and what a v2 prototype has to prove first.

## What the MCU has to do

The node is a USB/IP host over Wi-Fi ([architecture.md](architecture.md)).
The firmware ([firmware.md](firmware.md)) needs:

* a Zephyr **USB host controller (UHC) driver**, `zephyr_uhc0`. Zephyr's own
  USB/IP service (`CONFIG_USBIP`, `subsys/usb/host/usbip.c`) sits on top of it;
* the Zephyr **Wi-Fi** stack (station mode, mDNS, REST, telnet);
* I²C (INA226), UART (AUX), GPIO, and the WS2812 status LED.

On the ESP32-S3, the DWC2 host driver (`uhc_dwc2`) is upstream
([#102967](https://github.com/zephyrproject-rtos/zephyr/pull/102967)). The
S3's only PHY is full speed, so every board under test enumerates at
12 Mbit/s over USB/IP.

## Why look elsewhere: JLC assembly cost

Every ESP32-S3 and ESP32-S2 module in JLC's library (MINI and WROOM) is
**Standard-PCBA only**. That puts the bay node on Standard fees: the
2026-10-16 quote for 16 nodes had setup $25.75, stencil $8.27, X-ray $13.28,
plus 5 mm edge rails ([bom/README.md](../bom/README.md)). Only the bare
ESP32-S3 chips (for example ESP32-S3FN8, C2913196) can go through Economic
PCBA. A chip-down design means our own RF matching, antenna and certification
work, which is not worth it for 16 boards.

## Candidate: Ai-Thinker Ai-M62-32S (BL616)

| | ESP32-S3-MINI-1-N8 (v1) | Ai-M62-32S / -32S-I |
|---|---|---|
| LCSC | C2913206 | C22365139 / C22365140 |
| Price (JLC, 2026-10-16) | $4.72 | $3.68 / $3.38 |
| Stock (2026-10-16) | ample | **12 / 25** |
| JLC PCBA | Standard only | **Economic and Standard** |
| Size | 15.4 × 20.5 mm | 25.5 × 18 × 3.1 mm, SMD-38 |
| Flash | 8 MB | 4 MB |
| USB | OTG, full-speed PHY (12 Mbit/s) | USB 2.0 **high speed** (480 Mbit/s) |
| Radio | Wi-Fi 4, BLE 5 | Wi-Fi 6, BLE 5.3, 802.15.4 (Thread) |
| Certification | CE-RED, FCC | CE-RED and FCC listed for the Ai-M62 series, SRRC for the module ([Ai-Thinker certificates](https://docs.ai-thinker.com/en/certificate/)) |

The Ai-M61-32S (BL618, C22365152, $5.39) is Economic-capable too, but costs
more than the ESP32-S3 module.

**Gains, if it worked.** For the 16-node order:

* Economic instead of Standard PCBA: setup about $8 instead of $25.75,
  stencil about $1.55 instead of $8.27, no X-ray line, no edge rails;
* about $1.0–1.3 less per module;
* together about **−$55 to −$60 per order**, roughly 15 %. It also needs the
  WS2812C-2020 (C55109522) in place of the Standard-only WS2812B-2020.

Above all, a high-speed host would lift USB/IP from 12 to 480 Mbit/s. Mass
storage, high-speed probes and DFU images would then be as fast as a direct
cable.

## Zephyr status for the BL61x (October 2026)

| Function | Status |
|---|---|
| SoC, UART, SPI, I²C, GPIO, DMA, flash, PSRAM | upstream (`bflb` bindings); boards such as `bl618g0`, `ai_m61_32s_kit` and `ai_m62_12f_kit` exist. The BL618 G0 board page says "not actively maintained". |
| Wi-Fi | upstream `bflb,wifi6` driver over the vendor MAC/PHY blobs, with hostap for WPA2/WPA3 ([#109435](https://github.com/zephyrproject-rtos/zephyr/pull/109435), [#120599](https://github.com/zephyrproject-rtos/zephyr/pull/120599)) |
| 802.15.4 | upstream ([#112921](https://github.com/zephyrproject-rtos/zephyr/pull/112921)) |
| USB device | BL70x full speed only (`udc_bflb_v1`). BL61x high-speed device: [#97750](https://github.com/zephyrproject-rtos/zephyr/pull/97750), **open draft**, changes requested, mixed `testusb` results. Its author notes: "controller does host, this does not do host". |
| **USB host** | **no driver and no open PR** found. Zephyr's UHC drivers today: DWC2, MAX3421E, virtual, NXP (EHCI/KHCI/OHCI/IP3516 on top of the MCUX SDK), Renesas RA. Open PRs add STM32 OTG HS, IT51xxx and a generic OHCI. There is no generic EHCI host driver. |

The BL616 USB controller is EHCI-style on the host side. CherryUSB, the stack
in Bouffalo's own SDK, drives the BL616 host through its `bouffalolab/ehci`
port ([CherryUSB](https://github.com/cherry-embedded/CherryUSB)). A Zephyr
port would therefore be a **new UHC driver**, either BL61x-specific or a
generic EHCI one, with bulk and interrupt transfers at high speed (isochronous
too, for UVC-type devices). That is weeks of driver work, plus upstreaming,
before the node firmware can run. Zephyr's USB host stack is itself still
experimental.

## Other risks

* **Stock:** 12–25 modules at LCSC on 2026-10-16, fewer than one 16–20 node
  order. JLC's parts pre-order or a different variant would be needed.
* **Layout:** the module is about 5 mm wider. It needs the antenna keep-out at
  the rear edge again, a new footprint (Ai-Thinker publishes one), and a full
  re-place and re-route of the node.
* **Flash:** 4 MB instead of 8 MB, so the two 3.75 MB image slots of
  [firmware.md](firmware.md) shrink.
* **Flashing:** Bouffalo boards flash with `BLFlashCommand` or through a
  CK-Link; `west flash` support varies by board. The front port's SERVICE
  path (USB-Serial-JTAG on the S3) has no direct equivalent. Plan on UART0
  pads plus a BOOT strap.
* **Binary blobs** for Wi-Fi and BLE, as on Espressif.

## What a v2 prototype must prove first

On an Ai-M62-32S-Kit (or BL618 G0), before any board change:

1. Zephyr Wi-Fi joins the lab network and holds a TCP throughput test
   (`zperf`) comparable to the ESP32-S3 node.
2. A BL61x UHC driver enumerates and moves bulk data at high speed, through a
   hub, with a CMSIS-DAP probe, a J-Link or ST-LINK, a CDC-ACM UART and a mass
   storage device.
3. The unchanged `CONFIG_USBIP` service exports those devices to a Linux
   `usbip attach` client, at least as reliably as on the S3.

Only then: swap the module and LED in `electronics/bay-node/design.py`, keep
the rest of the node (power, mux, INA226, AUX), and re-quote JLC with Economic
PCBA.

Two things to watch meanwhile: BL61x USB device driver
[#97750](https://github.com/zephyrproject-rtos/zephyr/pull/97750), and any
EHCI host work in Zephyr.
