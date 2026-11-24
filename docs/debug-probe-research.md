# A debug probe on the DATA-4x-logic (research)

**Status (2026-10-21): research only, nothing designed or changed.**  The user asked for a study of a
built-in SWD probe ("Lance une étude pour 5 et 6", item 5).  The idea: boards without a probe (Pico 2,
most XIAO) have no SWD in the rack today.  The RP2354B of the DATA-4x-logic
([electronics.md](electronics.md) › DATA ×4 v2.0) could run a CMSIS-DAP probe besides the gusmanb
analyzer, and the CH446Q matrix would take SWCLK and SWDIO to the board.  Builds on
[coproc-firmware-research.md](coproc-firmware-research.md) (images swapped through PICOBOOT) and
[data-x4-v2-research.md](data-x4-v2-research.md).  "#n" are pull requests on zephyrproject-rtos/zephyr.

## In short

- **Yes, with no hardware change.**  Raspberry Pi's stock **debugprobe** (v2.3.1, MIT, CMSIS-DAP **v2
  over bulk**) runs on the RP2354B as wired.  Its Pico pinout lands on the buses: SWCLK on A, SWDIO on B,
  and its UART console on C/D.  The matrix takes them to any P pin of any port.
- **Ranked:**
  1. **Day one: stock debugprobe as a third image**, swapped with gusmanb through PICOBOOT (≈ 3 s), one at
     a time.  No firmware of ours.  About 350 lines on the node and in bayctl, about a week with the
     bench.  yapicoprobe is a second choice to bench beside it: faster, with nRESET on a bus, but its
     licence is unclear.
  2. **Later: CMSIS-DAP inside our Zephyr firmware**, next to its consoles and emulated devices.  Zephyr
     has the DAP subsystem and a CMSIS-DAP v2 bulk USB backend, with a sample that already targets the
     Raspberry Pi Debug Probe.  It lacks a fast SWD driver for the RP2xxx: a PIO one, ≈ 300–400 lines,
     upstreamable.
  3. A dedicated probe chip on the hub's spare port 6: only if debugging and capturing at once is a must.
     ≈ $2.5 a board, ≈ $3 an order, and a layout change.
  4. One image merging gusmanb and debugprobe: no, a fork of two upstreams.
- **Signals.**  The LSF0108 passes SWDIO's turnaround with no direction pin.
  - Estimates, to be benched: ≈ 4 MHz SWCLK on 3.3 V boards.  ≈ 1 MHz on 1.8 V boards, whose read edges
    finish on the bus's 10 k pull-up.
  - Default 1 MHz, as debugprobe's own.
- **Who gains:** only boards in a DATA-4x-logic bay, today B3.
  - **The Pico 2 most**: its 3-pin SWD header.  Flashing and `west debug` without the BOOTSEL dance,
    recovery from a crash loop, and a console on the probe's UART.
  - **The XIAO RP2040, RP2350, nRF52840 and SAMD21**, with wires soldered to their underside SWD pads.
  - Nothing to gain on the ESP32 XIAOs (USB-JTAG) or the XIAO MG24, whose own probe is already v2 bulk.
  - The single bays cannot reach the probe.  Among them, the **UNO R4 WiFi's** own probe is HID v1 only,
    so it fails over USB/IP: that one needs a fix of its own.
- **No change to the v2 needed.**  nRESET goes by a software reset over SWD, or by the RESET line the
  node already drives.  With yapicoprobe or our Zephyr probe it can also be a bus pin.  Reset taps, SWO
  and extra pulls were weighed and are not worth it.
- **CI:** one hardware-map entry per SWD-wired sub-slot.
  - `runner: pyocd`, which has a built-in `rp2350` and gets the probe's serial from twister.
  - OpenOCD needs a build newer than its 0.12.0 release.
  - One probe per drawer, so the pre-script takes a lease.
  - Swaps first need the node's DWC2 slot fix.

## The firmware: one image or several

**Stock debugprobe fits the board as wired.**  Checked in the source of
[raspberrypi/debugprobe](https://github.com/raspberrypi/debugprobe):
- **Release:** v2.3.1 (2026-05-29) ships `debugprobe_on_pico2.uf2`; commits up to Sep 2026.
- **Pins:** its Pico build (`include/board_pico_config.h`) puts SWCLK on GP2 and SWDIO on GP3.  It drives
  its SWD with PIO (`probe.pio`).  The CDC UART (uart1) is TX on GP4 and RX on GP5, the LED on GP25, and
  the target reset on GP1.
- **USB:** 2e8a:000c, product "Debugprobe on Pico (CMSIS-DAP)".  It exposes CMSIS-DAP **v2 over bulk**
  (`PROBE_DEBUG_PROTOCOL` defaults to `PROTO_DAP_V2`; v1 HID is a build option), a CDC UART, and
  Raspberry Pi's reset interface.  So `picotool reboot -f -u` sends it to BOOTSEL, with no wire.
- **DAP:** 64-byte packets, 8 of them queued, 1 MHz by default (`DAP_config.h`).  No SWO (`SWO_UART 0`,
  `SWO_MANCHESTER 0`).
- **Licence:** MIT-style (GitHub shows "NOASSERTION").

On the DATA-4x-logic, GPIO2–9 are buses A–H.  So the stock UF2 gives:
- **SWCLK on bus A**, **SWDIO on bus B**;
- a **UART console on buses C (probe TX) and D (probe RX)**;
- the LED as on a Pico 2.

GP1 is bridged to GP0, which is gusmanb's trigger loop.  debugprobe drives its reset there open-drain and
leaves GP0 an input: no fight, but that reset reaches no board.  GPIO10–13 and 16–19, the 2.2 k enables,
stay inputs, pulled down, so those pull-ups stay off.  debugprobe is SWD only (`DAP_JTAG 0`).

**An alternative stock image: yapicoprobe** ([rgrr/yapicoprobe](https://github.com/rgrr/yapicoprobe)):
- **Release:** v2.02.06 (2026-08-24), with a `-pico2-` UF2.
- **Faster:** 8 MHz by default for RP2040/RP2350 targets, 24 MHz at most.
- **nRESET on GP6, which is bus E:** a board's reset through the matrix, with the stock image.
- **More:** RTT, and an optional sigrok analyzer in the same image.
- **Against it:**
  - its licence is unclear (MIT headers, no LICENSE file);
  - an RP2350 as the probe is marked experimental;
  - it adds a v1 HID fallback interface, so if Linux binds it, an interrupt IN stays pending and holds
    a host channel;
  - it drives SWDIR on GP1, harmless while GP0 stays an input (to check);
  - its UART is the reverse of debugprobe's, RX on GP4 and TX on GP5.

Second choice: bench it next to debugprobe.

| Option | One image or two | Reused | Written | Verdict |
|---|---|---|---|---|
| **1. Stock debugprobe as a third image**, swapped with gusmanb by PICOBOOT (or `picotool reboot -u`) | two (or three with ours), one at a time | the UF2, as is; the node's PICOBOOT flasher and crosspoint control, already planned | node: an image choice, a "probe on port n" routing preset, a probe lease; bayctl: `prepare --probe`, the map entries | **day one** |
| **2. CMSIS-DAP inside our Zephyr firmware** (consoles and emulation, coproc-firmware-research.md) | ours: probe, consoles and emulation; gusmanb still swapped in for captures | Zephyr's `subsys/dap` (CMSIS-DAP, SWD only) and its USB bulk backend on `device_next` (`DAP_BACKEND_USB`, 2024); `samples/subsys/dap` already has a Raspberry Pi Debug Probe (RP2040) overlay (2025-09) | DT and config ≈ 30 lines; a fast SWD driver (below); nRESET and the UART on any bus pin by devicetree | **when our firmware comes** |
| 3. A second, dedicated probe chip (RP2354A) on the hub's spare port 6, tapping buses A/B directly | two chips, both at once | stock debugprobe on it | a design change: an RP2354A block (≈ 11 × 10 mm), port 6's pair routed, two bus taps | only if capturing and debugging at once is a must |
| 4. gusmanb and debugprobe merged in one image | one | both pico-sdk / TinyUSB code bases | a fork of two upstreams (GPL-3.0 as a whole), FreeRTOS and bare metal to reconcile | **no**: the opposite of "un truc en moins à maintenir" |

Zephyr's probe today:
- **Speed:** the bit-bang driver `drivers/dp/swdp_bitbang.c` has fast-pin paths for nRF, STM32 and MCX
  only.  On an RP2xxx it falls back to the generic GPIO calls (`FAST_BITBANG_HW_SUPPORT 0`): it works, but
  slowly.  Two fixes, both upstreamable:
  - an RP2xxx fast-pin header on the SIO registers, ≈ 40 lines;
  - a PIO SWD driver behind `swdp.h`, ≈ 300–400 lines, from debugprobe's MIT `probe.pio`, as fast as
    debugprobe.
- **Missing:** JTAG and SWO are "unsupported" in `cmsis_dap.c`, and the subsystem is marked
  EXPERIMENTAL.

**Does it need its own USB device on the hub?**
- No, for options 1 and 2: the probe is the co-processor's own device on hub port 5, under another image.
- Only option 3 needs a port.  The USB2517I has two spare ones, 6 and 7, unrouted today.

**Interfaces and channels over USB/IP:**
- The CMSIS-DAP v2 interface is bulk, so the node's DWC2 host carries it ([ci.md](ci.md): HID v1 fails).
- A debug session keeps at most the DAP's IN endpoint pending: one host channel, while OpenOCD or pyOCD
  is connected.
- debugprobe's CDC UART holds two host channels only while a client keeps it open.

## The signal path: matrix and translators

One SWD line, board to probe.  The DUT pin is followed by:
1. a 20 cm Dupont jumper;
2. the header's P pin;
3. the H5VU25UC (flow-through ESD);
4. 100 Ω;
5. the LSF0108: A side at the board's VREF, B side at 3.3 V;
6. a CH446Q switch, X pin to Y pin: ≈ 55–65 Ω at ±5 V (interpolated from the datasheet, 120 / 185 Ω at +5 V
   only), 10–25 pF per switch pin;
7. the bus, which is the Y line joined across both chips.  It carries a 10 k pull-up to 3.3 V, a 2.2 k one
   that the co-processor switches, and the RP2354B's GPIO.

Figures from the v2 note's second pass.

| | 3.3 V board | 1.8 V board |
|---|---|---|
| Probe → board (SWCLK, SWDIO writes, nRESET) | rise ≈ 45–60 ns, the v2 note's Elmore estimate; the matrix passes push-pull both ways | down-translation: the LSF passes the low and stops the high at VREF; as fast |
| Board → probe (SWDIO reads) | as fast | up-translation: the LSF lifts the bus to ≈ VREF, then the B-side pull-up does the rest, about 0.1–0.4 µs with the 10 k alone (v2 note, "Limits").  Several times faster with the 2.2 k switched on, but only our own firmware drives those enables: under debugprobe they stay off |
| Read loop (SWCLK out, the board's output delay, SWDIO back) | ≈ 70–100 ns | ≈ 0.2–0.5 µs |
| SWCLK that should work | **≈ 4 MHz**; 1–2 MHz as the default | **≈ 1 MHz** (2 MHz with the 2.2 k on) |

The v2 note estimated "SPI/SWD ≈ 5 MHz": same order.  All of these are estimates, to be measured on the
bench.  For comparison, debugprobe's default SWCLK is 1 MHz, and 1–4 MHz is the usual range over 20 cm
leads anyway.

**SWDIO through the LSF0108: fine.**
- It is a pass FET with no direction pin, so either side may drive.
- During the turnaround cycle, when nobody drives, the line rests on the pull-ups: the bus's 10 k and the
  board's own SWDIO pull-up.
- The 100 Ω bounds a collision at the turnaround.
- This is why v2 rejected the TXS010x: their one-shots would have been the problem here.

The SWD signals only ever see the board's VREF, and a 5 V board follows the rule of every virtual wire
(electronics.md › DATA ×4 v2, "The VREF rule"): only with TTL inputs, VREF on its own 3.3 V pin.

**Which buses.**
- The probe's signals sit on fixed RP2354B pins, so on fixed buses.
- The matrix takes any P pin of any port to any bus.  So the user jumpers the board's SWCLK and SWDIO to
  any P pins, plus VREF and GND.  Without VREF the group passes nothing, by design.
- The jumpers are declared where B3's are today, in `config/rack.yaml` › `population` › `jumpers`, e.g.
  `B3.2: { VREF: 3V3, P3: SWCLK, P4: SWDIO }`.  The board's pin names come from `boards.yaml` ›
  `headers`: the Pico 2's SWD header is there, the XIAO's underside pads are not yet.
- When the probe is "on" a port, the node closes those P pins onto the probe's buses.

With debugprobe's Pico pinout:
- SWCLK is bus A, SWDIO bus B;
- the UART is bus C (probe TX → the board's RX) and bus D (the board's TX → probe RX).

Buses A–D are Y3–Y0, the ones that leave the crosspoints' north side towards the co-processor.  The probe
image is not the analyzer, so only virtual wires between the boards could also want those buses.  The node
keeps A–D for the probe while it runs: 2 of the 8 for SWD, 4 with the UART.

Multi-drop: RP2040 and RP2350 targets speak SWD multi-drop (DPv2 TARGETSEL), so two of them on the same
pair would be possible in theory.  The plan is one board at a time, the node switching the crosspoints.

## Which boards gain

**Only boards in a DATA-4x-logic bay can reach the probe.**  Today that is B3: two XIAO and two Pico 2,
one of which is the stand-in analyzer until v2.
- B1's DATA-4x is the base assembly: no matrix, no co-processor.
- The single bays (A1–A4, B2, B4) wire their board to the node directly: no matrix, no probe from the
  drawer.

| Board | In the rack | On-board probe | Its SWD | Gain from the drawer's probe |
|---|---|---|---|---|
| **Pico 2** (RP2350A) | B3.2, B3.3 (the stand-in analyzer until v2); B1.2 (base: no) | none: runner `uf2`, BOOTSEL through the port's BOOT wire | the 3-pin debug header (SWCLK, GND, SWDIO), already in `boards.yaml` | **the most.**  Flashing and `west debug` without BOOTSEL, recovery from a crash loop, and a console on debugprobe's UART (its GP0/GP1 to buses C/D) |
| XIAO RP2040 / RP2350 | possible in B3.1, B3.4 | none (UF2, BOOTSEL) | bonding pads on the underside (Zephyr's board docs) | as the Pico 2, with wires soldered to the pads |
| XIAO nRF52840 (`xiao_ble`) | possible | none: Adafruit UF2 bootloader | underside pads; Zephyr's doc says "solder an SWD" or use Seeed's expansion board | real: flashing without the bootloader, recovering a locked or bricked chip, debugging |
| XIAO SAMD21 | possible | none (UF2, double-tap reset) | underside pads | as the nRF52840 |
| XIAO MG24 | possible | a SAMD11 CMSIS-DAP on the USB-C, **v2 over bulk** (2886:0062, "CMSIS-DAPv2" in a user's OpenOCD log) | — | none: its own probe already passes USB/IP |
| XIAO nRF54L15 | possible | the same SAMD11 CMSIS-DAP (Zephyr's board docs); v1 or v2 unverified | — | none if v2; if v1 only, the drawer's probe through its pads |
| XIAO ESP32-C3/C6/S3 (B3.1 and B3.4 today) | B3.1, B3.4 | USB-Serial-JTAG in the chip (Espressif's JTAG, openocd-esp32) | no SWD | none |
| Arduino Nano Matter (MGM240) | B1.4, a base DATA-4x | a SAMD11 CMSIS-DAP on the USB-C; which firmware, v1 or v2, unverified: `lsusb -v` on the board settles it | test pads (Arduino's datasheet: "JTAG/SWD debug port, accessible through the board's test pads") | none in B1 (no co-processor); in a logic bay, through its pads, if its probe turns out v1-only |
| UNO R4 WiFi | B4, single bay | its ESP32-S3 runs a free-dap probe over **HID only (v1)**: 2341:1002 "UNO WiFi R4 CMSIS-DAP" (Arduino's `uno-r4-wifi-usb-bridge`) | no RA4M1 SWD header (SJ1 bypasses the bridge) | **its probe fails over USB/IP**, and the drawer's cannot reach it: a single bay.  A separate fix (a probe on its pads, or the RA4M1's USB bootloader through SJ1) |
| UNO R4 Minima, GIGA R1, Wio Terminal | single bays | none | Minima: J2 SWD/JTAG; GIGA: a JTAG connector; Wio: SWD pins to solder | none from the drawer |
| BeaglePlay's CC1352P7 | A3, single bay | none: flashed from its Linux | a Tag-Connect header, JTAG / cJTAG | none: an SWD-only probe (debugprobe's `DAP_JTAG 0`, Zephyr's DAP) cannot drive cJTAG anyway |
| NUCLEO-64/144 | A1, A2 | ST-LINK/V2-1 or V3 (bulk) | — | none: already works over USB/IP |

## Hardware: no change needed

**Nothing is required for SWD.**
- SWCLK and SWDIO go through any two P pins.
- GND and VREF are on every header.

**nRESET**, three routes, none needing copper:
1. **A software reset over SWD** (SYSRESETREQ / AIRCR).  It is OpenOCD's and pyOCD's usual reset on
   Cortex-M and covers most flashing and test runs.
2. **The header's RESET pin**, which the node already drives through its expander and which a board
   jumpers anyway for BOOTSEL and reset (B1.2: `RESET: RUN`).  It is driven from the pre-script
   (`bayctl reset`).  From the debugger: a pyOCD user script (`will_reset` → the node's API), or an
   OpenOCD `reset-assert` event calling the node.  Slow (HTTP, milliseconds) but timing-free; not tried.
3. **A bus pin**, through the matrix to a P pin jumpered to the board's reset: true connect-under-reset,
   for one P pin.  Two probes can do it: yapicoprobe as it is (its nRESET is GP6, bus E), and our Zephyr
   probe (`reset-gpios` on any of buses E–H).  Stock debugprobe cannot: its reset is GP1, which is not a
   bus.

**Considered, not recommended:**
- **RESET taps**: one RP2354B GPIO per port onto that port's RESET net through 1k, as the first v2 pass
  had on GPIO10–13 before the pull-up enables took those pins.  The parts are free: four 0402 1k, a basic
  part already on the board, and free GPIOs remain (15, 20–24, 26–39).  But it takes four more traces
  from the co-processor band down between the power clusters, on a board just routed at 4 layers.  And
  only our own firmware could use the taps: debugprobe's reset is one fixed pin, but the taps are four.
  Route 3 gives the same for one jumper.
- **SWO**: any P pin can take it to any bus, but neither stock debugprobe (`SWO_UART 0`) nor Zephyr's
  CMSIS-DAP ("unsupported" in `cmsis_dap.c`) would read it.
- **A pull on SWCLK or SWDIO**: the buses already carry 10 k to 3.3 V, which suits SWDIO.  SWCLK is
  always driven while the probe runs.
- **A second, dedicated probe chip** (option 3 above): ≈ $2.5 of parts per board.  RP2354A (C41378174,
  ≈ $1.26), its own 12 MHz crystal and core-regulator inductor (the same part types as U11's), about ten
  basic capacitors and resistors.  Plus one extended part type (≈ $3 per order) and a block of
  ≈ 11 × 10 mm.  Hub port 6 routed, two bus taps.  Only if capturing and debugging at once is a must.

## West and twister

The probe is just another USB device behind the node: the co-processor's busid (`1-1.5`) exported over
USB/IP, as the rack does for DUT probes today ([ci.md](ci.md)).  The flow:

1. `bayctl prepare B3.2 --probe`.  This step is new: today's `prepare` attaches the DUT's own device.
   - It makes sure the co-processor runs the probe image (a PICOBOOT swap if not, ≈ 3 s).
   - It closes B3.2's SWD pins onto the probe's buses.
   - It takes the drawer's probe lease.
   - It runs `usbip attach` on the co-processor.
2. `west flash -r pyocd`, or `-r openocd`.
   - pyOCD has the RP2350 built in.  OpenOCD needs a build newer than 0.12.0 (see Risks).
   - `rpi_pico2`'s `board.cmake` sets up both: OpenOCD with `interface/cmsis-dap.cfg` by default,
     pyOCD with `--target=rp2350`.
   - Other boards use their own target, through the same probe.
3. The console: debugprobe's CDC UART if the board's UART is jumpered to buses C/D, or the board's own
   USB.

Hardware map entry (twister), one per sub-slot that is wired for SWD:

```yaml
- connected: true
  platform: rpi_pico2/rp2350a/m33_0
  product: Debugprobe on Pico (CMSIS-DAP) (bay B3.2)
  runner: pyocd                            # twister adds --dev-id <id>
  id: E6614C311B1C7D2F                     # the probe's USB serial number (illustrative)
  serial: /dev/serial/by-id/usb-Raspberry_Pi_Debugprobe_on_Pico__CMSIS-DAP__E6614C311B1C7D2F-if01
  pre_script: /ci/rack-scripts/b3-2-pre.sh # bayctl prepare B3.2 --probe
  fixtures: [bay:B3.2]
```

The serial number and path above are illustrative.  `serial` is the console: debugprobe's CDC UART on
buses C/D.

How twister passes the probe's serial to the runner:
- **pyOCD:** twister passes `--dev-id <id>` itself.
- **OpenOCD:** twister adds `cmsis_dap_serial <id>` by itself only when `product` is exactly "Raspberry Pi
  Debug Probe (CMSIS-DAP)" (`scripts/pylib/twister/twisterlib/handlers.py`).  Otherwise bayctl writes
  `runner_params: [--cmd-pre-init, "cmsis_dap_serial <id>"]`, which the hardware-map schema accepts.

Twister reads the probe's serial from `probe_id`, and from `id` when there is none
(`board_id = hardware.probe_id or hardware.id`).  bayctl already has both fields, and `product`.

**One probe per drawer.**  Twister treats every map entry as its own device, and would run B3.1 and B3.2
at once on the same probe.
- Fix: the pre-script waits for the drawer's probe lease, and the post-script releases it.  The node
  already has per-bay leases ([ci.md](ci.md) › Access control).
- Or list one SWD sub-slot per drawer in the map.

**USB/IP latency.**
- CMSIS-DAP is chatty: every packet is a USB round trip, here over USB/IP, TCP and Wi-Fi (milliseconds).
- debugprobe queues several packets, and OpenOCD and pyOCD pipeline them.  Flashing 100–200 KB should
  take seconds, as with the ST-LINK and J-Link probes the rack already exports this way.  To be measured.

## Effort and cost

Counted on top of what the v2 and co-processor plans already contain: the node's crosspoint control
(virtual wires), its PICOBOOT flasher and image choice, and the DWC2 slot fix.

| Piece | Option 1 (stock debugprobe) | Option 2 (in our Zephyr firmware) |
|---|---|---|
| Co-processor firmware | 0 lines: the release UF2 | DT and config ≈ 30 lines; the RP2xxx fast-pin header ≈ 40 lines, or a PIO SWD driver ≈ 300–400 lines (2–4 days); nRESET on a bus by DT |
| Node | the probe as a third image (≈ 50 lines); "probe on port n": SWCLK/SWDIO (and the UART) onto buses A–D from the jumpers (≈ 100 lines); the drawer's probe lease (≈ 50 lines) | the same |
| bayctl and its tests | `prepare --probe`; SWD sub-slots in `hwmap` (`runner`, `runner_params`, `probe_id`); the routing read from each sub-slot's jumpers (≈ 150 lines) | the same |
| Bench | SWCLK at 1 / 2 / 4 MHz on a 3.3 V and a 1.8 V board, through the matrix; flashing time over USB/IP; a twister run | the same, plus the driver against debugprobe |
| **Total** | **≈ 350 lines, about a week with the bench** | **+ 0.5–1 week** |

| Cost | Option 1 or 2 | Option 3 (second chip) |
|---|---|---|
| Parts per board | $0 | ≈ $2.5 |
| JLC per order | $0 | ≈ $3 (one extended part type) |
| Layout | none | an ≈ 11 × 10 mm block, hub port 6, two bus taps: a design-session item |

Upkeep:
- Option 1: none of ours.  Pin the debugprobe release in `config/rack.yaml`, as gusmanb is pinned.
- Option 2: part of our firmware.  The DAP subsystem is EXPERIMENTAL upstream, so expect API churn at
  Zephyr bumps.

## Risks

- **The probe and the analyzer never run at once** (options 1 and 2): a swap takes ≈ 3 s, and a capture
  of the SWD traffic itself needs option 3, or our own analyzer next to our probe.
- **Swaps need the DWC2 slot fix first** (coproc-firmware-research.md, "A prerequisite on the node").
  Each BOOTSEL round trip leaks per-endpoint slots on the node.
- **Speeds are estimates.**  The 1.8 V read path depends on the 10 k pull-up while debugprobe runs.  Bench
  it before promising more than 1 MHz.
- **20 cm Dupont jumpers** on SWD: fine at 1–4 MHz with a GND jumper beside the pair; above that,
  ringing and crosstalk.
- **One probe per drawer**: four boards, one debug session at a time.  The lease serialises CI jobs; a
  human session holds it too.
- **Bus sharing**: a virtual wire on buses A–D would collide with the probe.  The node must refuse one
  while the probe image runs.
- **Host tools**:
  - **OpenOCD's last tagged release is 0.12.0 (Jan 2023).**  `tcl/target/rp2350.cfg` is on upstream's
    master (touched 2025–26) and in openocd-org's rolling "latest" build (2026-10-19), not in distro
    packages.  The CI host needs that build or Raspberry Pi's fork.  Zephyr's `rpi_pico2` `board.cmake`
    notes that `west debug` relies on the fork's `reset init`.
  - **pyOCD** has a built-in `rp2350` target (since Aug 2024; v0.46.0, 2026-10-19), and `rpi_pico2`'s
    `board.cmake` already passes `--target=rp2350`.  So `west flash -r pyocd` with a pip-installed
    pyOCD is the simplest CI path for Pico 2 boards.
