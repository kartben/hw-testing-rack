# A wired bay node: which MCU (research)

**Status (2026-10-24): research only, no board or firmware changed.**  The user's idea, verbatim: "On
faisait du Ethernet classique sur chaque port. Chaque contrôleur se connecterait sur un switch qu'on
pourrait avoir en bas de la baie. Et du coup, peut-être on pourrait regarder un microcontrôleur qui ne
soit pas le ESP32 mais pour lequel il y aurait un Ethernet qui est plus facile et plus économique.
Peut-être un STM32 ou autre."

So: 10/100 Ethernet on every bay node (RJ45, no PoE), and a switch at the bottom of the rack.  This
note picks the node's MCU for that.  It builds on:
- [mcu-alternatives.md](mcu-alternatives.md), the Wi-Fi-era comparison (BL616);
- [esp32-s31-research.md](esp32-s31-research.md): the S31 has a HS host, an Ethernet MAC and CAN FD,
  but its Zephyr support is two draft PRs and its modules are out of stock;
- the RJ45 row-cable study, for the tray's mechanics;
- the Wi-Fi capacity study
([wifi-capacity-ns3.md](wifi-capacity-ns3.md)), which put one channel's limit at about 8 simultaneous
flashes.  "#n" are pull requests on zephyrproject-rtos/zephyr.

## In short

- **No MCU meets both the ≤ S3 budget and a working Zephyr USB host through the hub.**
  - **Under $5.03** (the WROOM-1-N8R8 at JLC), the only MCUs with Ethernet are WCH's CH32V208, CH32V307
    and CH32V317, at $1.7–3.4 with a PHY on chip.  But they have 64–192 KB of SRAM, against the
    ≈ 440 KB the node needs.  Zephyr also has no WCH USB driver (host or device) and no WCH CAN driver.
  - **Parts whose Zephyr USB host works, or nearly, through a hub** cost a node more, with PHY,
    flash and magjack ($7.5–15): NXP RT10xx (EHCI), ESP32-P4, and STM32H7 once its glue lands.
- **The cheapest wired node that works now: keep the S3 and add a W5500.**
  - The W5500 is a 10/100 MAC + PHY on SPI: $2.82, and Zephyr main drives it (`eth_w5500`).
  - It goes on the camera's SPI2, with the free IO5 and IO6 as CS and INT.
  - $8.90 a node against $5.03 today (+$3.87).
  - The USB host stays as it is, and CAN is unchanged.  The port is `net.c` and the DTS: days, not
    weeks.
- **For a cheaper node later**, watch the CH32H417 and the ESP32-S31.  The CH32H417 is $3.3–3.9, with
  ≈ 700 KB of SRAM in Zephyr's DTS, but Zephyr only has GPIO and UART for it.
- **Rack side:**
  - a 16- or 24-port switch at the bottom;
  - star home runs of slim Cat6;
  - a standard 13.5 mm magjack (the user accepts adapting the tray's height);
  - keep CAN.

## What the node needs, in order

1. **A Zephyr USB host controller (UHC) driver** doing control, bulk and interrupt transfers, **through
   a USB hub**.  The DATA ×4 puts 4 DUTs behind a USB2517I.  This is the node's job: USB/IP on
   Zephyr's `subsys/usb/host/usbip.c` with the rack's patches (`zephyr/patches.yml`).  High speed is a
   plus.
2. **A Zephyr Ethernet MAC driver**, a cheap RMII PHY and a magjack.
3. **RAM**, sized below.
4. **CAN** (CAN-FD is fine) with a Zephyr driver, for the rack bus, unless it goes (see "CAN").
5. **JLC assembly**: QFP rather than BGA; stock and price.

A note on hubs, because it decides more than the list shows:
- Today the S3's DWC2 is a full-speed root.  With a full-speed root, the USB2517I runs as a
  full-speed hub, and no split transactions are needed.
- A high-speed root (EHCI, DWC2 with a ULPI PHY) runs the hub at high speed.  Every full-speed DUT
  behind it (XIAO, Pico 2, most probes) then needs split transactions through the hub's transaction
  translator.  The UHC driver has to support them, or those DUTs do not work.
- A high-speed root behind a high-speed hub is the only way to get more than 12 Mbit/s to a
  high-speed DUT (an MCU-Link or a J-Link).  The DUTs the rack hosts today are full speed.

## The candidates, cheapest first

Zephyr main as of 2026-10-24.  JLC prices are at 10 pieces, with stock, on the same day.  "Node cost"
counts the MCU, the Ethernet PHY, the crystals, the magjack and any external flash:
- PHY: DP83825I, C783599, $0.35 (RTL8201F, C45044, $0.33, also fits);
- magjack: HR913550A, C163507, $0.95;
- crystal: 25 MHz, C9006 (basic), $0.10 each;
- QSPI flash: W25Q64, C179171, $1.71, where the MCU has no internal flash.

The WROOM-1 module already holds flash, PSRAM, a crystal and an antenna.

| MCU, package, LCSC, price, stock | SRAM | Ethernet in Zephyr | USB host in Zephyr, through the hub | CAN in Zephyr | Node cost | ≤ $5.03 |
|---|---|---|---|---|---|---|
| **CH32V208RBT6**, LQFP64, C5448615, $1.74, 173 | 64 KB | MAC + 10BASE-T PHY on chip, `eth_wch.c` | **none**: no WCH USB driver; FS USB only | **none** | $2.79 | yes |
| **CH32V317WCU6**, QFN68 0.4 mm, C49188393, $2.96, 923 (the LQFP100 is out of stock) | as the V307 (to check) | MAC + PHY on chip, `eth_wch.c` (PHY speed: to check) | **none** | **none** | $4.01 | yes |
| **CH32V307VCT6**, LQFP100, C2943979, $3.40, 719 | 32–192 KB, split with flash by option bytes; Zephyr's board variants go to 192 KB | MAC + 10BASE-T PHY on chip, `eth_wch.c`; `netif:eth` on `ch32v307v_evt_r1` | **none**.  Its USBHS port has a HS PHY, so a new UHC driver would also need splits | **none** | $4.45 | yes |
| **CH32H417**, QFN68 C52196060 $3.32 (1,290) or QFN128 C49363240 $3.92 (1,395) | ≈ 700 KB (Zephyr DTS: 255 KB for the V5F core + 447 KB for the V3F) | none in Zephyr (to check what the chip has) | none | none | not costed | — |
| **ESP32-S3-WROOM-1-N8R8 + W5500** (LQFP48, C32843, $2.82, 22 k) | 512 KB + 8 MB PSRAM | W5500 on SPI, `eth_w5500` | **today's**: DWC2 as a FS root, works through the USB2517I with the rack's patches | TWAI | **$8.90** | no (+$3.87) |
| **RT1021CAG4BR**, LQFP144, C5194827, $4.27, 118 | 256 KB | ENET 10/100 RMII, `eth_nxp_enet` | EHCI (`uhc_mcux_ehci`), splits supported.  But 16 pipes, never released (hub + 4 CDC DUTs need 18) | FlexCAN, classic | $7.48 | no |
| **ESP32-P4NRW32**, QFN104, C22387510, $5.36, **0**, "Standard only" | 768 KB + 32 MB PSRAM | EMAC RMII, `eth_esp32` | DWC2.  Its FS OTG port is a FS root like today, so no splits are needed.  The HS port has no splits | TWAI | ≈ $8.6 + a core buck | no |
| **STM32H723VET6**, LQFP100, C730141, $9.18, 589 | 564 KB in banks | ETH, mature | DWC2 with an internal FS PHY, so no splits needed.  But **no STM32 UHC glue in main** (#112648 F7, #112858 U5, #120811 N6 open) | FDCAN | $10.68 | no |
| **STM32H743VIT6**, LQFP100, C114409, $9.40, 823 | 1 MB in 5 banks | ETH, mature | as the H723 | FDCAN | $10.90 | no |
| **RT1062CVL5B**, BGA196 0.65 mm, C2990557, $10.52, 1,379 | 1 MB | ENET | EHCI ×2, enabled on `mimxrt1060_evk`, splits supported, 16 pipes | FlexCAN3, FD | $13.73 | no |
| **MCXN947VKLT**, HLQFP100, C47023717, $13.27, **0** | 512 KB (Zephyr gives cpu0 320–384 KB) | ENET QoS | EHCI, but no `nxp,uhc-ehci` node yet (#121225 open) | FlexCAN-FD | $14.77 | no |
| **TM4C1294NCPDT**, TQFP128, C913855, $13.84, 2,008 | 256 KB | MAC + 10/100 PHY on chip, but **Zephyr has no TM4C129** (Tiva-C: TM4C123 only; `eth_stellaris` is the LM3S6965) | none | none | $14.89 | no |

Also looked at and dropped:
- **Renesas RA6M5** (no LQFP stock, no Zephyr CAN driver) and **RA8M1** ($16.78):
  `uhc_renesas_ra` does splits, but it has 4 interrupt pipes.
- **W7500P** ($5.87): a Cortex-M0 at 48 MHz with a hardwired TCP/IP stack and a PHY, but no USB and
  no Zephyr SoC.
- **MAX3421E** ($8.21, a FS host on SPI): it would add a USB host to a cheap Ethernet MCU, but it alone
  costs more than the S3.
- **ENC28J60** ($4.52, 10BASE-T only) and **W6100** ($4.47, IPv6 offload the node does not need):
  both cost more than the W5500 and do less.

**Plainly: nothing meets both the budget and the USB host through the hub.**
- Every part under $5.03 fails on RAM, and on Zephyr USB and CAN.
- Every part with a Zephyr USB host that works through a hub costs 1.5–3× the S3.  The one exception
  is the S3 itself.

## RAM: how much

Today the node puts its big buffers in the WROOM-1's 8 MB PSRAM (`BAY_EXT_RAM`).  Without Wi-Fi and
PSRAM, sized from `firmware/bay-node/Kconfig` and `prj.conf`:

| Item | Today | Wired node |
|---|---|---|
| Camera frames (Arducam Mega, two buffers) | 2 × 512 KB in PSRAM | 2 × 64 KB: a 640 × 480 JPEG is 30–60 KB; a larger frame comes in pieces (`BAY_CAMERA_FRAME_KB`) |
| USB/IP buffer pool, segments | 48 KB + 16 KB (`USBIP_BUF_POOL_SIZE`, `USBIP_SEGMENT_SIZE`) | the same, 64 KB |
| USB host buffers | 32 × up to 4 KB (`UHC_BUF_COUNT`) | 16 KB |
| Network buffers | 512 TX + 96 RX × 128 B, plus packets (`NET_BUF_TX_COUNT`…) | about 80 KB, plus the MAC's DMA rings (≈ 16 × 1.5 KB = 24 KB) |
| AUX console replay | 16 KB (`BAY_AUX_LOG_SIZE`) | 16 KB |
| Thread stacks | HTTP 4 KB, main 4, work queue 4, USB host 2, USB/IP 6 × 1.8, camera, AUX, rack, shell, net | ≈ 50 KB |
| Heap, kernel, static data, web buffers | | ≈ 60 KB |
| **Total** | | **≈ 440 KB** |

So **512 KB of contiguous SRAM fits with little margin** (camera buffers cut to 64 KB, no room for a
second large feature).  **1 MB is comfortable.**  256 KB does not fit with the camera, and a
fragmented 512 KB (several small banks, DMA-capable only in some) fits only with placement work.

## Porting the node firmware

What is ESP32-specific today (13.7 k lines in `firmware/bay-node/src` and `common/lib`):

| Piece | Where | On another MCU |
|---|---|---|
| Wi-Fi: credentials, connect, TX power, HT20 (`esp_wifi_*`) | `common/lib/net.c` (≈ 150 of its 358 lines) | goes; Ethernet comes up with DHCP and the same mDNS / DNS-SD (`common/lib/dnssd.c` is generic).  The `radio` shell command and the Wi-Fi settings page go |
| Rack bus CAN (TWAI) | board DTS `can = <&twai>`; `bay-node/src/rack.c` uses the generic CAN API | DTS only |
| Status LED WS2812 (RMT) | `worldsemi,ws2812-pulse-io` on `&rmt`; `status_led.c` uses the generic LED strip API | DTS: the SPI or PWM WS2812 driver, or I2S where the MCU has it |
| LED dimming (LEDC PWM) | `pwm-leds` on `&ledc0` | DTS: the MCU's PWM |
| ADC | DTS channels | DTS |
| AUX UART loopback (`uart_ll_set_loop_back`) | `aux_console.c`, behind `CONFIG_SOC_FAMILY_ESPRESSIF_ESP32` | -ENOTSUP already; a pinctrl loopback where the UART has one |
| Fault record kept across a restart (`.rtc_noinit`) | `fault.c` | a `__noinit` RAM section (most Cortex-M keep RAM across a warm reset) or retained memory (`zephyr,retained-ram`) |
| PSRAM placement (`BAY_EXT_RAM`) | `bay.h` and 8 buffers | empty macro; buffers shrink as above |
| SERVICE mode: hands the S3's USB PHY to its USB-Serial-JTAG (`usb_serial_jtag_ll_*`) | `usb_host.c`, `usb_mux.c` | goes.  SERVICE mode becomes a SWD header (or the MCU's ROM bootloader) |
| MCUboot layout (`partitions_0x0_default_8M.dtsi`), the update over Wi-Fi | board DTS, `common/lib/update.c` (generic) | new partitions; MCUboot runs on all the candidates |
| The DWC2 patches (`uhc-dwc2-channels.patch`: 8 channels, parked endpoints, counter limits) | `zephyr/patches.yml` | carry over only to DWC2 (ESP32-P4, STM32H7).  The USB/IP, hub-reset and TCP_NODELAY patches are generic and carry over everywhere |
| Board definition | `firmware/boards/hwtr/bay_node/` | a new board |

The rest (USB/IP service and its patches, web server and pages, camera over SPI, AUX console and
RFC 2217, INA226, expanders, access control, update, rack protocol) is plain Zephyr API.  **The port
is about 1.5–2.5 weeks** before bench time, most of it the board, the network bring-up and the
SERVICE path, if the UHC works through the hub.  If it does not, writing that is the bulk of the
work (below, per candidate).

## The S3 + W5500 node

**BOM added to today's node**, at 10 pieces:

| Part | LCSC | $ |
|---|---|---|
| W5500, LQFP-48 0.5 mm | C32843 | 2.82 |
| 25 MHz crystal (load capacitance: see "To check") | C9006, basic | 0.10 |
| Magjack HR913550A, THT, with LEDs | C163507 | 0.95 |
| *or* RJ-064-1 + H1102NLT, both SMD, 10.75 mm tall | C7205199 + C18584 | 0.75 |
| 12.4 kΩ 1 % on EXRES1, terminations, decoupling | basic | ≈ 0.10 |
| **Added** | | **≈ $3.97**, so ≈ $9.0 with the WROOM-1 |

Two extended part types are added: the W5500 and the jack.  The node is already JLC Standard, because
of the WROOM-1.

**Wiring** (W5500 datasheet v1.1.0, page numbers given):
- On SPI2 with the camera: SCK IO11, MOSI IO10, MISO IO9.  CS on IO5 and INT on IO6, the node's two
  free GPIOs.
- The bus can be shared in variable-length mode (p. 12).  Zephyr's driver uses that mode: its control
  byte has OM = 00.
- RSTn has an internal 50–112 kΩ pull-up (p. 59) and needs ≥ 500 µs low (p. 10, p. 60).  An RC, or the
  S3's EN net, does it, with no GPIO left to spare.
- PMODE[2:0] left open (internal pull-ups) means auto-negotiation, all modes (p. 10).
- LINKLED and ACTLED drive the jack's LEDs.
- It draws 128–132 mA at 3.3 V on a 100 Mbit/s link (p. 60).  The S3 draws less with Wi-Fi off.  The
  power-budget session checks the 3V3 regulator's margin.

**Firmware:**
- `net.c` brings up the Ethernet interface with DHCP and the same mDNS / DNS-SD.
- A `w5500` node goes under `&spi2`, with `int-gpios`.
- `CONFIG_WIFI=n` gives back the internal DRAM the Wi-Fi driver holds.  The node is short of internal
  DRAM ([bench.md](bench.md)).
- The Wi-Fi page and the `radio` command go, or stay behind a Kconfig option as a fallback.
- Nothing else changes: USB host, USB/IP, TWAI, the camera and SERVICE mode stay as they are.

**Throughput:**
- The W5500 guarantees 33.3 MHz SCLK (p. 61).  At 20–33 MHz that is ≈ 10–15 Mbit/s a node
  ([wifi-capacity-ns3.md](wifi-capacity-ns3.md)).  That is 3–5× the 3 Mbit/s a full-speed flash needs.
- The camera and Ethernet share the bus transaction by transaction.  Camera frames are read in pieces
  (≤ 4 KB), so an Ethernet frame waits at most one piece.
- The bench measures this, flash and camera at once.

**Cost of a wired 16-bay rack**, against Wi-Fi:
- 16 × $3.97 ≈ $64 of node parts;
- a $25–60 switch;
- 16 slim patch cords;
- so ≈ $110–150, against a second AP for rows C–D.

## The rack side

**Switch.**  8 nodes today, 16 with rows C and D, plus the power hub and the uplink: 10 or 18 ports.
- **Unmanaged** 16- or 24-port 10/100 or gigabit desktop switches are $25–60, with an internal mains
  supply or a 12 V brick.  The simplest.
- **Managed (smart)** adds port-based VLANs, IGMP snooping, mirroring and LLDP/SNMP.  The lab server
  can then read which switch port a node sits on, which can stand in for the CAN position chain.
  $50–120 for 16+ ports.
- **Fed from the rack**: DIN-rail industrial switches take 12–48 V DC, so the hub's 20/28 V could feed
  them, but they cost $80–200 for 16 ports.  Two cheap 8-port 5 V or 12 V switches behind a buck from
  VRACK is the low-cost version (≈ $30 in all), at the price of a cascade and a second box.
- 10/100 is enough: a node feeds at most the USB full-speed bus, ≈ 1.2 MB/s (10 Mbit/s; 820 kB/s
  measured over Wi-Fi).  The uplink to the lab is the only link that sums them (16 × 10 =
  160 Mbit/s, so gigabit there).

**Cable path.**  A home run per tray, star-wired, unlike the row cables' daisy chain.
- Slim Cat6 patch cables (28 AWG, ≈ 3.8 mm) of 0.3–1 m, up the rack's left side tied to the ladders
  like the row feeds, into each tray.
- 16 of them make a bundle of ≈ 18 mm.
- They plug into the node from above, through the tray's rear service slot.
- They stay out of the drag chain: the node is fixed to the tray, and only the drawer moves.

**RJ45 height in the tray.**  The RJ45 row-cable study already measured the tray
([rj45-row-cable-feasibility.md](rj45-row-cable-feasibility.md),
[its mechanical half](rj45-row-cable-mechanical.md)):
- The RJ-064-1 (C7205199, SMD, shielded, 15.3 × 14.7 × 10.75 mm, $0.34) fits at J1/J2's place.  It
  clears the drawer by 3 mm and the left ledge by 0.5 mm.
- A 13.3–13.5 mm jack hits the ledge.  That is a standard magjack such as the HR911105A or the
  HR913550A.  **The user accepts adapting the tray's height where needed** (2026-10-24).  So a standard
  magjack (HR913550A, C163507, THT with LEDs, ≈ $0.95) is the default.
- Without touching the tray: the RJ-064-1 has no magnetics, so a discrete transformer goes beside it.
  The H1102NLT (C18584, Pulse, SMD 12.7 × 7.1 mm, $0.41, 55 k in stock) makes $0.75 for the pair,
  cheaper than the magjack.  A low-profile magjack (Bel L829-1J1T-43, C5271177, ≈ 11.3 mm) costs
  $6.90.
- Where: the rear edge, where the antenna keep-out (6 mm × ±24 mm) frees room once Wi-Fi goes, or
  J1/J2's side.  It is a design-session item, and the tray session checks the plug's path.

**A star, no RJ45 daisy chain** (the user, 2026-10-24).  Each node has one RJ45, wired to the switch.
The row cable (VRACK, CAN, POS) stays today's daisy-chained PH 6.
- That also keeps the one hazard the RJ45 row-cable study found out of the rack: VRACK on an RJ45 that a
  laptop's cord can reach.
- The same study's other idea, 10BASE-T1S on the row cable, would share 10 Mbit/s (about 1 MB/s of
  TCP) between a row's 4 nodes.  That is less than 4 simultaneous flashes feed (1.45 MB/s): not for
  bulk USB/IP.

## CAN: keep it or drop it

Wired Ethernet carries everything the node reports.  What CAN still does, and what dropping it costs:

| CAN does | Without CAN |
|---|---|
| **Position chain**: the row cable's POS line tells each node where it sits (`docs/can.md`), so a node that is moved gets its new `bay-<pos>` name by itself | a managed switch's port map (LLDP / SNMP), or a static map in the lab file |
| **Out-of-band power control**: the hub switches a row's power whatever the node's network or firmware does | the hub on Ethernet too (it is an ESP32-S3-MINI with Wi-Fi today), and only row-level power cycling |
| Works before the network: during boot, a DHCP failure or a hung TCP stack | nothing equivalent |
| Costs: a TJA1462 (≈ $1) and the 6-pin row cable, already designed and in the BOM | saves ≈ $1.5 a node, a driver and `rack_*` code |

**Recommendation: keep CAN** for the first wired nodes.  It is cheap, already routed in the row cable,
and the only path that works when a node's network does not.  Revisit once the wired nodes have run
on the bench: if the position chain is the only thing left, a managed switch can take it over.

## Recommendation

1. **No new MCU now.**  No MCU on the market fits the ≤ S3 budget and has a Zephyr USB host through the
   hub, the node's main job.
2. **For wired Ethernet: S3 + W5500.**
   - Bench first: an ESP32-S3-DevKitC-1 (the bench stand-in) with a W5500 board, on the node's pins.
     Measure USB/IP flashing and the camera at the same time.
   - Then a node revision in the design session: the W5500 and its jack, and the Wi-Fi antenna
     keep-out either kept (Wi-Fi fallback) or freed.
3. **If a new MCU is wanted later**, in this order:
   1. **ESP32-P4**, once in stock.
      - Its FS OTG port is a FS root like today's.
      - Same vendor HAL, same TWAI driver, and the DWC2 patches carry over.
      - ≈ $8.6 or more: no saving, but 768 KB + 32 MB PSRAM and a native MAC.
   2. **STM32H743 or STM32H723**: ETH and FDCAN are mature, and the root is FS.
      - It needs the STM32 DWC2 host glue.  The open F7, U5 and N6 PRs show the pattern: about 1–2
        weeks with the bench.
      - $10.7–10.9.
   3. **RT1062**: EHCI does splits today.
      - The 16-pipe limit needs the pipe-release fix, about a week.
      - It is BGA and $13.7.  The RT1021 ($7.5) has too little RAM (256 KB).
   4. **WCH CH32V3**: the cheapest, but no.  It needs a new UHC with splits and a CAN driver, and it
      still lacks the RAM.
4. **Watch:**
   - the CH32H417: about 700 KB of SRAM at $3.3–3.9, if Zephyr gains its USB and Ethernet;
   - the ESP32-S31: HS host, MAC and CAN FD, but Zephyr support is two draft PRs;
   - the MCXN947's EHCI node (#121225).

## Dev kits

JLC/LCSC prices, 2026-10-24.

| For | Board | Price | Notes |
|---|---|---|---|
| **S3 + W5500** (recommended) | ESP32-S3-DevKitC-1 v1.1 N8R8 (on hand), plus a W5500 board (WIZnet WIZ850io or a generic module) | W5500 board not priced | wired to SPI2, IO5 and IO6 as on the node; no remap |
| ESP32-P4 | ESP32-P4X-Function-EV-Board | $63.52 | Ethernet PHY on board; Zephyr board `esp32p4x_function_ev_board` |
| STM32H7 | NUCLEO-H753ZI or NUCLEO-H723ZG | $40.81 each | Ethernet and USB OTG FS on board |
| RT1062 | MIMXRT1064-EVK (the 1060-EVKB is obsolete) | $176.54 | |
| RT102x | MIMXRT1024-EVK | $94.43 | |
| MCXN947 | FRDM-MCXN947 | $26.25, 0 in stock (13 weeks) | |
| CH32V307 | CH32V307V-EVT-R1 | not priced | Zephyr board, `netif:eth` |

## To check by the user

1. **W5500 crystal load capacitance.**
   - Datasheet v1.1.0, <https://docs.wiznet.io/img/products/w5500/W5500_ds_v110e.pdf>.
   - §5.5.3, p. 60, lists "Load Capacitance 18 pF".  The reference schematic (Figure 3, p. 11) puts
     2 × 18 pF on the crystal, which suits a crystal of about 12 pF.
   - Question: is 18 pF the crystal's CL?  Then C9006, a 12 pF part, is wrong.  Or is it the load
     caps' value?  Then C9006 with 2 × 18 pF is right.
2. **CH32H417**, only if it becomes a candidate.
   - <https://www.wch-ic.com/products/CH32H417.html>.
   - How much SRAM can one core use?
   - What speed are its Ethernet MAC and PHY?
   - Does its USB HS controller have a host mode that reaches FS devices behind a HS hub (splits)?
3. **CH32V317 PHY speed**, only if a WCH part comes back.
   - <https://www.wch-ic.com/products/CH32V317.html>.
   - Is the on-chip PHY 10BASE-T or 100BASE-TX?  How much SRAM, against the V307?

The W5500 facts used above are read off the datasheet, with page numbers.
