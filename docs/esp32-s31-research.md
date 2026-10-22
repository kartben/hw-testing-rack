# ESP32-S31 for the bay node rev B? (research)

**Status (2026-10-22): research only, nothing changed.**  The user asked for a feasibility check of
Espressif's ESP32-S31, "puisqu'il y a déjà des draft PRs pour ajouter le support dans Zephyr".  The question
is whether a rev B bay node (and maybe the power hub) should move from the ESP32-S3-WROOM-1-N8R8 to an S31
module.  It follows [mcu-alternatives.md](mcu-alternatives.md), which looked at the BL616 for the same
reasons: a high-speed USB host, and cheaper assembly.

**Answer: not for rev B now; prototype first.**
- The chip fixes the node's real limits: a high-speed host with 16 channels whose DMA reaches PSRAM, an
  Ethernet MAC, 802.15.4 and CAN FD.
- But in Zephyr it is two untouched draft PRs, with no Wi-Fi and no Ethernet.
- Its modules are at zero stock at LCSC, have no published certification, and run on chip revision v0.0.
- And HS USB/IP pays only once the network beats 12 Mbit/s, which today's Zephyr Wi-Fi path does not
  (≈ 4 Mbit/s).

## The chip, against today's

Facts from Espressif's pre-release documents (chip datasheet v0.5, 2026-07-13; module datasheets
WROOM-1 v0.5, WROOM-3 v0.7) and ESP-IDF's `soc_caps.h` for the S31 (master, read 2026-10-22).

| | ESP32-S3 (WROOM-1-N8R8, today) | ESP32-S31 (WROOM-1-N16R16V) |
|---|---|---|
| CPU | 2 × Xtensa LX7, 240 MHz | 2 × RISC-V (RV32IMAFC + Zc/Zb), 320 MHz; an LP RISC-V core |
| Internal SRAM | 512 KB | 512 KB HP + 32 KB LP |
| PSRAM | 8 MB octal, in the module | 16 MB in the package (1.8 V, 8 lines, DDR); 32 MB variant sampling |
| Flash | 8 MB quad | 16 MB quad, off-package |
| USB host | OTG **full speed**, DWC2, **8 host channels**, its DMA **cannot reach PSRAM** | OTG **high speed** with an integrated UTMI PHY, DWC_otg v4.30a, **16 host channels**, 3.5–4 KB of FIFO; `SOC_USB_OTG_PSRAM_DMA_CAPABLE` |
| USB Serial/JTAG | shares the one PHY with the OTG (IO19/20) | its own full-speed PHY (GPIO33/34) |
| Ethernet | none | 10/100/1000 MAC, MII / RMII / RGMII, IEEE 1588 |
| Wi-Fi | 802.11b/g/n, 2.4 GHz | 802.11ax, **2.4 GHz only**, 20 MHz in HE |
| Bluetooth | LE 5 | LE 5.4 and BR/EDR |
| 802.15.4 | none | Thread 1.4, Zigbee 3.0 |
| CAN | 1 × TWAI, CAN 2.0 | 2 × TWAI, CAN FD |
| GPIO on the module | 36 (33 with the octal PSRAM) | 54 |
| Camera | DVP, SPI | DVP, SPI (no MIPI CSI) |
| Module | 18 × 25.5 mm, 41 pads | 18 × 25.5 mm, 61 pads: the same outline and edge rows, but **not pin-compatible**.  20 inner pads carry USB HS (54/55) and the RGMII pins; a GND grid replaces the S3's single pad |
| Temperature | −40…65 °C | −40…85 °C |
| Status | mass production | in mass production since 2026-07-27 (the 16 MB-PSRAM chip and the WROOM-1/-3-N16R16V); the other variants are sampling.  Chip revision v0.0 only, with two errata (flash boot at 1.8 V VDD_SPI; ECDSA) |
| Certifications | CE-RED, FCC | **none published yet** |
| LCSC / JLC | C2913201, $4.62, in stock; Standard PCBA only | chip C55601453 ($5.84 at 1, $4.15 at 100), WROOM-3-N16R16V C55371223 ($6.11): **0 stock**, extended, Standard PCBA only.  The WROOM-1 has **no LCSC listing** (JLC shows placeholders).  DigiKey: WROOM-1 $8.43, WROOM-3 $8.22, both at 0 |
| ESP-IDF | stable | **preview** target in v6.1 (2026-08-27) |

Sources:
- [chip datasheet](https://documentation.espressif.com/esp32-s31_datasheet_en.pdf);
- [WROOM-1/1U](https://documentation.espressif.com/esp32-s31-wroom-1_wroom-1u_datasheet_en.pdf) and
  [WROOM-3/3U](https://documentation.espressif.com/esp32-s31-wroom-3_wroom-3u_datasheet_en.pdf);
- [`soc_caps.h`](https://github.com/espressif/esp-idf/blob/master/components/soc/esp32s31/include/soc/soc_caps.h);
- [mass-production news](https://www.espressif.com/en/news/ESP32_S31_Mass_Production) and the
  [product selector](https://products.espressif.com/en/product-selector);
- [errata](https://documentation.espressif.com/esp-chip-errata/en/latest/esp32s31/index.html);
- [ESP-IDF v6.1](https://github.com/espressif/esp-idf/releases/tag/v6.1);
- LCSC [C55601453](https://www.lcsc.com/product-detail/C55601453.html) and
  [C55371223](https://www.lcsc.com/product-detail/C55371223.html);
- the S3: [datasheet](https://documentation.espressif.com/esp32-s3_datasheet_en.pdf) and
  [WROOM-1](https://documentation.espressif.com/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf).

Not found anywhere:
- FCC/CE grants for S31 modules;
- when a chip revision after v0.0 ships;
- whether the EMAC's DMA reaches PSRAM;
- real LCSC lead times.

## Zephyr support (read 2026-10-22)

Nothing for the S31 is on Zephyr main.  All the work is one pair of Espressif draft PRs, opened 2026-09-21,
with no review and no activity since 23–25 September.

| PR | State | What it covers |
|---|---|---|
| [zephyr 119851](https://github.com/zephyrproject-rtos/zephyr/pull/119851), "soc: espressif: add esp32s31 initial support" | draft, DNM, conflicts with main, CI not run; 106 files, +17.9k (12.5k of it the pinctrl header) | SoC, DTS, clocks, pinctrl/GPIO, UART console, flash/cache/PSRAM, I²C, SPI + DMA, GDMA, **TWAI-FD** (twai0 only), ADC, PWM, PCNT, WDT, TRNG, AES, sleep, the MCUboot linker script.  Board: ESP32-S31-Function-CoreBoard-1.  Its own table marks **WIP: Wi-Fi, BLE, 802.15.4, Ethernet, USB OTG, USB Serial/JTAG, SMP** |
| [hal_espressif 657](https://github.com/zephyrproject-rtos/hal_espressif/pull/657) | draft, DNM; 41 files | the Zephyr port layer for the S31.  **No S31 Wi-Fi, PHY or BT blob entries** in `module.yml`, though Espressif's blob repositories have S31 builds |
| [mcuboot 2809](https://github.com/mcu-tools/mcuboot/pull/2809) | merged 2026-08-13, in Zephyr since 2026-09-08 | MCUboot's S31 config |
| [zephyr 118563](https://github.com/zephyrproject-rtos/zephyr/pull/118563) | merged 2026-09-17 | the ESP32-P4's HS host quirk in `uhc_dwc2` (UTMI PHY bring-up).  The S31's OTG node uses the same compatible (`espressif,esp32-usb-otg-hs`), so it should apply |
| [zephyr 120876](https://github.com/zephyrproject-rtos/zephyr/pull/120876), "[WIP] drivers: usb: uhc_dwc2: add SPLIT transactions" | draft, last change 2026-10-13 | full- and low-speed devices behind a high-speed hub.  On main, `uhc_dwc2.c` still has "TODO: Configure split transaction if needed" |

Our firmware's needs (`firmware/bay-node`, `firmware/common`), against what exists for the S31:

| Need | S3 today | S31 |
|---|---|---|
| USB host (`uhc_dwc2`) | upstream, plus our two patch sets (`zephyr/patches.yml`) | The OTG node is in the draft DTSI, labelled as a device.  Relabelling it `zephyr_uhc0` and the P4 quirk should do; **untested by anyone**.  FS DUTs behind the DATA ×4's hub need split transactions (120876, draft).  No isochronous, as on the S3 |
| USB/IP, HTTP, WebSocket, telnet, mDNS, settings | generic | generic |
| Wi-Fi (station, hostap) | upstream | **missing**: no blobs in hal_espressif, no driver or DT enablement, **no PR anywhere** |
| MCUboot OTA (sysbuild) | upstream | MCUboot side merged; the SoC side is in 119851 |
| CAN (TWAI) | upstream | in 119851 (CAN FD controller, classic frames fine) |
| I²C (INA226), SPI (camera), ADC, PWM (camera light), GPIO, PSRAM | upstream | in 119851 |
| WS2812 status LED (RMT, `ws2812-pulse-io`) | upstream | RMT not in 119851: an RMT driver, or WS2812 over SPI |
| Ethernet MAC | — | `eth_esp32.c` supports the ESP32 and the P4 only, RMII/MII only.  The S31 needs its glue and DT nodes; **no PR** |
| 802.15.4 | — | `ieee802154_esp32.c` runs on C5/C6/H2.  The S31 needs a DT node and the blobs; **no PR** |

**HS host on the S31 is plausible** with Zephyr's DWC2 driver: it already brings up the P4's UTMI PHY,
sizes FIFOs for HS and handles up to 16 channels.  What it lacks is split transactions (draft) and
isochronous.  Our channel-sharing patch matters less with 16 channels, but stays useful.

## What it would buy us

**HS USB/IP, but only behind a faster network.**
- The node's USB/IP runs at Zephyr's ESP32-S3 Wi-Fi TCP speed today, ≈ 4 Mbit/s
  ([data-x4-v2-research.md](data-x4-v2-research.md)).  HTTP downloads measure 53–61 KB/s
  ([bench.md](bench.md)).  Full-speed bulk is ≈ 9.7 Mbit/s, so today the network, not the USB, is the
  limit.
- The S31's Wi-Fi 6 (1 stream, HE20) has more air rate, but the S3's radio is not what limits us either:
  measure Zephyr's path on the S31 before counting on it.
- Even over Wi-Fi, an HS host still helps:
  - each of a DATA ×4's DUTs gets its own transaction translator in the USB2517I (MultiTRAK), instead of
    four boards sharing one 12 Mbit/s bus;
  - HS devices run at their own speed;
  - the S3's 8-channel starvation goes away with 16 ([multi-dut-node.md](multi-dut-node.md)).
- The limits in [ci.md](ci.md) (no interrupt OUT, no isochronous, on-board hubs) are the driver's, not the
  chip's, and stay.

**Wired networking through the MAC.**
- **100BASE-TX** on RMII: LAN8720AI (C17146, $1.02, 14k in stock, Economic) plus a MagJack.  ≈ 90 Mbit/s
  per node, so HS USB/IP becomes worthwhile.  But it is a star: a switch port and a cable per bay.
- **10BASE-T1S** (LAN8670, C20901523, $7.36, 109 in stock): 10 Mbit/s **shared** by a row's nodes
  (PLCA multidrop).  It suits the RJ45 row cable's spare pair for control and consoles.  It is not a bulk
  USB/IP path: four nodes share what one Wi-Fi link gives today.
- **None of this needs the S31.**  Zephyr main has the LAN865x T1S MAC-PHY over SPI (`eth_lan865x.c` +
  `oa_tc6.c`; LAN8651B1, C22386973, $10.02, 52 in stock) and the W5500 (100BASE-TX over SPI).  On the S3
  node, SPI2 (the camera's) takes one with its own CS and IRQ: IO5 and IO6 are free.

**RAM.**
- The S3 node has 1.7–2.6 KB of internal DRAM left with six USB/IP sessions ([bench.md](bench.md)).  The
  USB/IP pool (48 KB) and the UHC buffers must stay internal, because the S3's OTG DMA cannot reach PSRAM.
- On the S31 they can go to PSRAM (`SOC_USB_OTG_PSRAM_DMA_CAPABLE`).  That frees ≈ 50 KB of the same
  512 KB, the biggest practical gain after HS.  Zephyr's DWC2 driver and `usbip.c` would need to allocate
  from PSRAM; neither does today.

**802.15.4.**  Thread and Zigbee DUT tests (sniffer, RCP or border router for the bay) from the node itself.
It shares the 2.4 GHz radio with Wi-Fi by time slicing, so it works best with a wired uplink.

**Radio.**  Still 2.4 GHz only: [architecture.md](architecture.md) › Radio stays as it is.  Wi-Fi 6's
OFDMA and target wake time help in a crowded rack only with a Wi-Fi 6 access point.

## What it would cost

**The node (rev B)**, `electronics/bay-node`:
- **Module.**  Same 18 × 25.5 outline, new pin map: the 27 signals in `design.py` move.  The HS pair leaves
  from inner pads 54/55, under the module: via-in-pad or vias next to the pads, 90 Ω to the FSUSB42.
- **USB.**  The service mode moves to USB Serial/JTAG's own pins (33/34).  The PC port's mux then switches
  between the OTG and the laptop only.
- **Camera PSRAM pins.**  On the S31 the PSRAM is in the package: the S3's IO35–37 rule goes away.
- **Ethernet.**  100BASE-TX: LAN8720AI + MagJack + 25 MHz crystal, ≈ $3–4 and 9–10 GPIOs.  T1S: LAN8670
  + choke + termination, ≈ $9.
- **Assembly.**  Standard PCBA either way, since the S31 modules are Standard-only like the S3's.  No
  assembly-fee change.

**The power hub.**  It is not a USB host.  The S31 would give it a MAC (a wired uplink for the rack) and a
second CAN-FD controller, nothing it needs today.  It stays on the ESP32-S3-MINI-1-N8.

**BOM, per node** (10 nodes):

| | Today | S31 | Δ per node | Δ for 10 |
|---|---:|---:|---:|---:|
| Module | $4.62 (C2913201) | $6.0–6.1 (LCSC list, 0 stock) to $8.43 (DigiKey) | +$1.4 to +$3.8 | +$14 to +$38 |
| 100BASE-TX, if wanted | — | ≈ $3.5 | +$3.5 | +$35 |
| T1S, if wanted | — | ≈ $9 (S3: LAN8651 ≈ $11) | +$9 | +$90 |

**Firmware port, our side**, once Espressif lands the SoC and Wi-Fi:

| Item | Estimate |
|---|---|
| Board definition, pin map, MCUboot flash layout (16 MB) | 2–3 days |
| USB host bring-up at HS: relabel, P4 quirk, our patches rebased, split transactions (120876 or our own) | 1–2 weeks |
| WS2812 without RMT, or an RMT driver | 1–2 days |
| Ethernet glue for `eth_esp32` on the S31 (RMII), if wanted | 1–2 weeks |
| USB/IP pool and UHC buffers in PSRAM | 2–3 days, measured against throughput |
| Total | ≈ 3–5 weeks, Ethernet included |

**Schedule risk.**  Wi-Fi is the node's only network.  Its S31 support needs Espressif's blobs and driver
in Zephyr, with no PR anywhere today.  Until it lands, an S31 node cannot even boot into the rack.  The SoC
PR itself is a month-old draft.

## Recommendation

**Rev B stays on the ESP32-S3.**  Revisit the S31 once all of these hold:
1. the SoC PR (119851) and its hal_espressif PR are on Zephyr main;
2. S31 Wi-Fi works in Zephyr (blobs in hal_espressif, the driver enabled);
3. split transactions (120876 or a successor) are merged, or proven by us on the S31;
4. a WROOM module is in stock at LCSC/JLC, with its CE/FCC certification published;
5. a chip revision after v0.0 ships, or the two errata are confirmed harmless for us.

**Prototype first, in three steps:**
1. **USB host on an ESP32-S31-Function-CoreBoard-1**, with Zephyr from 119851, `zephyr_uhc0` relabelled
   and 120876 applied.  Enumerate a USB2517I-based hub with an MCU-Link and a CP210x behind it.  Measure
   local HS bulk throughput (a USB stick at HS) and the 16-channel behaviour with six devices.  No network
   yet.
2. **When Wi-Fi lands:** USB/IP over Wi-Fi against the S3 on the same access point.  `iperf` TCP, a 1 MB
   image flashed through J-Link and MCU-Link, a 10 MB read from a stick.  Repeat with the USB/IP pool in
   PSRAM.
3. **Ethernet:** the same tests over RMII 100BASE-TX (a LAN8720 board), to see whether HS USB/IP reaches
   tens of Mbit/s.

**Meanwhile, for rev B on the S3:**
- If the RJ45 row cable comes, its T1S pair can be served by a LAN8651 on the camera's SPI bus
  (`eth_lan865x`, upstream).  That needs no new MCU.
- The DRAM squeeze stays the node's main risk: the next lever is `CONFIG_ESP32_WIFI_NET_ALLOC_SPIRAM`
  ([firmware.md](firmware.md)).
