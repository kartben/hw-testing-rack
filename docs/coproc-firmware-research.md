# DATA ×4 v2 co-processor: the firmware question (research)

**Status (2026-10-19): research and a build-only spike, nothing designed.**  The user asked for the
co-processor's firmware to be studied on its own ("recherche le fw zephyr dans une session indépendante"),
apart from the board research in [data-x4-v2-research.md](data-x4-v2-research.md).  That note puts an
RP2354B on the DATA ×4 v2, on its own port of a 7-port hub behind the node, with the stock gusmanb
analyzer first and a Zephyr firmware of ours later, estimated at 4–6 k lines and 8–12 weeks.  This note
checks that estimate against Zephyr upstream main (f78c4de, 2026-10-19) and a spike
([`firmware/spikes/coproc`](../firmware/spikes/coproc/README.md)) built for the Pico 2.  "#n" below
are pull requests on zephyrproject-rtos/zephyr.

## In short

- **Recommended: (c) staged, switched by reflashing.**  Day one, the stock gusmanb analyzer: no
  firmware of ours.  Our Zephyr firmware comes only when consoles or emulated devices are really
  wanted, and **without its own analyzer**: about 2.9 k lines and 4.5 weeks, node side included.  The
  node switches between the two images by reflashing through the ROM's PICOBOOT, about 3 s.  First, the
  node's DWC2 driver must give back the per-endpoint slots of a device that leaves (the v2 note's second
  pass); DUT reflashing needs that fix anyway.  Writing our
  own analyzer, (b), is worth it only to capture a bus while emulating a device on it, or if gusmanb
  stalls: about 1 k more lines and 3 more weeks plus bench time, then gusmanb can go.
- **Most of "our firmware" is already upstream.**  Consoles (CDC-ACM and `zephyr,uart-bridge`) and the
  two emulated I²C devices (DesignWare target, `regset_target_lib`) are devicetree only in the spike.
  What is really ours: the link to the node, the control protocol, the glue that changes things at run
  time, sensor models, and the analyzer.
- **The co-processor must stay on USB.**  Its ROM has no I²C boot.  Its UART boot uses the QSPI pins
  at 1 Mbaud, with no free wire for it on the lead.  BOOTSEL (QSPI_SS and RUN through the node's
  TCA9534A) followed by PICOBOOT updates and recovers both firmwares, and the ROM cannot be overwritten.
  **Drop MCUboot**: it adds nothing here.
- **Node side, needed by every option:** BOOTSEL control, a flasher, a USB host class and a protocol
  client, about 1.2 k lines.  Day one can do without the last three: the node exports the boot device or
  the analyzer over USB/IP and the lab server runs picotool or gusmanb's app.
- **Honest upkeep.**  (a): nothing on the co-processor; re-check our gusmanb client whenever we change
  the pinned release (last release Feb 2025).  (b) and (c): a 4th Zephyr app.  Built in the node's
  workspace and CI, it costs about half a day per Zephyr bump on average, and 2–3 days when the RP2350
  port renames things, as it did in Aug–Sep 2026.  Plus the protocol, versioned against the node.  The
  RP2350 port is moving: 36 commits on its own files in 6 months.
- **The v2 estimate holds:** 4–6 k lines, 4 weeks to a first useful version, 8–12 weeks for everything.
  Recounted below for everything, (b): about 4.7 k lines, node included, and ≈ 9 weeks plus ≈ 2 weeks of
  bench.  The bench is the uncertain part.

## What Zephyr supports today

Checked in the tree at f78c4de (2026-10-19) and on GitHub, not from memory.

| Need | Today | Where |
|---|---|---|
| SoC and board | RP2350A and RP2350B, 14 boards (5 on the B package). Each build runs one core type: `m33_0` or `hazard3_0`. RP2354A/B appear only in a comment: the in-package flash is the ordinary QSPI flash on CS0, so our board is an RP2350B board with the 2 MB partition files | `soc/raspberrypi/rpi_pico/rp2350`, `soc.c`; `dts/vendor/raspberrypi/partitions_2M_*.dtsi`; targets renamed `m33` → `m33_0` in #117192 (merged 2026-09-23) |
| Second core | Not used: one core, no SMP. M33 + M33 AMP is in review (#109953, open), heterogeneous AMP was closed (#117844); the SIO mailbox driver is in (#94502) | `boards/raspberrypi/rpi_pico2` |
| M33 or Hazard3 | Both build the spike unchanged; M33 is smaller (100 KB vs 123 KB, it has an FPU) and has the MCUboot variants and probe-rs/J-Link targets | spike builds |
| PIO | A thin driver: clock, reset, state-machine allocation, `gpio-base` for GP32–47 (82 lines). Programs are pioasm output pasted as hex (`RPI_PICO_PIO_DEFINE_PROGRAM`), or built at run time with the pico-sdk encoders, as the spike does. No dispatch of the two PIO interrupt lines | `drivers/misc/pio_rpi_pico`, `include/zephyr/drivers/misc/pio_rpi_pico/pio_rpi_pico.h` |
| PIO drivers | UART (poll only, 201 lines), SPI, WS2812 (with DMA, #101518), MIPI-DBI. An interrupt-driven PIO UART (RX through a self-reloading DMA ring, a service thread every 2 ms) is #118562, open, one review | `drivers/serial/uart_rpi_pico_pio.c` |
| Custom PIO program | Easy: the pico-sdk `hardware_pio` API is there; the spike's capture is 133 lines | spike `la_pio.c` |
| I²C target | DesignWare target mode, **one address per controller** (one `target_cfg` in `i2c_dw.c`, one IC_SAR in the hardware): two controllers, so two emulated devices at most, on fixed pairs (I2C0 on GPIO4/5 or 8/9, I2C1 on GPIO2/3 or 6/7). Register-map models: `regset_target_lib` with TMP103 and EEPROM targets (Jul–Aug 2026). Target-mode fixes in 2025–26 (#95657, #111414) | `drivers/i2c/i2c_dw.c`, `drivers/i2c/target/` |
| More addresses | A PIO I²C target: nothing upstream, nor in pico-sdk | — |
| USB device | `device_next` UDC driver, 16 bidirectional endpoints: 4 CDC-ACM (8 IN + 4 OUT) plus a bulk pair fit. CDC-ACM instances come from the devicetree; `zephyr,uart-bridge` joins one to a UART with no code. No generic vendor-bulk class (`loopback.c` is a test class): ours is 169 lines in the spike | `drivers/usb/udc/udc_rpi_pico.c`, `subsys/usb/device_next/class/`, `drivers/serial/uart_bridge.c` |
| DMA | 16 channels. Zephyr's API: one block, no chaining, no ring. Rings (a pre-trigger buffer, the PIO UART's RX) program pico-sdk `hardware_dma` on channels reserved with `dma_request_channel()`. Fixes in Sep 2026 (#119824, #119681), #121058 open | `drivers/dma/dma_rpi_pico.c` |
| PWM | 12 slices, 24 channels: every bus pin GPIO2–9 is a PWM output | `drivers/pwm/pwm_rpi_pico.c` |
| ADC | RP2350B: 8 inputs on GPIO40–47 and the temperature sensor (channel 8) | `drivers/adc/adc_rpi_pico.c`, `rp2350b.dtsi` |
| Counter / timer | The two 64-bit TIMER blocks as counters with alarms | `drivers/counter/counter_rpi_pico_timer.c` |
| Reboot to BOOTSEL | `RPI_PICO_ROM_BOOTLOADER` with the retention boot mode calls the ROM's `reset_usb_boot` | `soc/raspberrypi/rpi_pico/common/rom_bootloader.c` |
| picotool's reset interface | Not implemented | — |
| MCUboot | `rpi_pico2/rp2350a/m33_0/mcuboot` variants; 2 MB sysbuild partitions exist | `dts/vendor/raspberrypi/partitions_2M_sysbuild.dtsi` |
| Logic analyzer | Nothing: no PIO capture driver or sample, no SUMP, no sigrok | — |

On the node's side (ESP32-S3, the USB host):

| Need | Today | Where |
|---|---|---|
| A class for the co-processor | The `usbh` class API exists (hub and UVC classes only): no CDC-ACM host class, no vendor-bulk one | `subsys/usb/host/class/`, `include/zephyr/usb/usbh.h` |
| Host channels | DWC2 claims one channel per transfer in flight (`ch_claim()`), at most one per endpoint; an IN transfer waiting for data holds its channel. The S3 has 8 for the whole drawer | `drivers/usb/uhc/uhc_dwc2.c` |
| Updating the co-processor | MCUmgr's SMP client has only a Bluetooth transport (`smp_client_transport_register()` in `smp_bt.c`); no PICOBOOT client exists | `subsys/mgmt/mcumgr/transport/src/` |

How fast it moves (2026-04-19 → 2026-10-19, no merges): 36 commits on the RP2xxx-specific files, 33 on
`i2c_dw.c`, 46 on `device_next`, 36 on the USB host; `hal_rpi_pico` moved to pico-sdk 2.3.0 (Jul) and
again in Sep; the board targets were renamed in Aug–Sep.  Zephyr 4.5 is at rc2.

## The spike

[`firmware/spikes/coproc`](../firmware/spikes/coproc/README.md), built (warnings as errors) for
`rpi_pico2/rp2350a/m33_0`, `rpi_pico2/rp2350a/hazard3_0` and `rp2350b_core/rp2350b/m33_0`; never run.

| | Our code |
|---|---|
| 4 CDC-ACM ports, con1 bridged to UART1 | 0 (devicetree), plus 25 lines of USB device setup |
| con2 on a PIO UART | 0, but only with #118562: on main it builds and stays silent |
| Emulated TMP103 (I2C0) and EEPROM (I2C1) | 0 (devicetree) |
| The node's vendor bulk link | 169 lines |
| 8-channel PIO + DMA capture, edge trigger, up to 150 MS/s | 133 lines |

M33: 100 KB of flash, 46 KB of RAM besides a 256 KB capture buffer.  Two small upstream bugs found
(details in the spike's README): the TMP103 target starts before the sensor it reads, and
`zephyr,uart-bridge` accepts a peer that has no interrupt API.

## Logic-analyzer firmwares

Checked on GitHub on 2026-10-19.

| | gusmanb LogicAnalyzer | sigrok-pico | Bus Pirate 6 SUMP mode | dotcypress uLA |
|---|---|---|---|---|
| Licence | GPL-3.0 | GPL-3.0 | MIT (some LGPL-3/BSD-3 parts) | MIT or Apache-2.0 |
| Last release, activity | v6.0.0.1, published 2025-02-09 (GitHub API); three commits in 2026 (Feb, Aug); a 6.5 beta outside GitHub | no releases; commits Jan–Aug 2026 | firmware active (Oct 2026) | Feb 2025; RP2040 only |
| RP2350 | yes (`BUILD_PICO_2`) | yes, 476 KB buffer | it runs on an RP2350B | no |
| Rate, depth at 8 ch | 100 MS/s (200 "blast"; turbo build 200/400), 393,216 bytes = 393 k samples | 120 MS/s on ≤ 4 ch, ≤ 60 MS/s reliable at ≥ 8 ch | 62.5 MS/s, 131 k samples | 100 MS/s, 16 ch, 200 KB |
| Triggers | edge, pattern (fast on 5 ch, complex on 16 bits), burst; in hardware | level, edges, in software on the host: triggered captures stream, so they are slow | one pin, high or low | SUMP stages |
| Host protocol | own binary frames over USB CDC (Wi-Fi TCP on Pico W), documented only in the source | ASCII over USB CDC, documented (`TECHNICAL.md`) | SUMP on its second CDC port | SUMP over CDC |
| Host software | own .NET app, `CLCapture` CLI, a C# library; no libsigrok driver | libsigrok `raspberrypi-pico` driver, in master since Sep 2023 but in no release (nightly builds only) | PulseView / sigrok-cli `ols` | PulseView `ols` |
| Streaming | no, buffered | yes, 400–800 KB/s | no | no |
| Reboot to BOOTSEL | command 4 → `reset_usb_boot()` | the string `bootsel` | — | — |

Verified in gusmanb's source: the Pico 2 build reads its 24 inputs from GPIO2, loops the complex trigger
from GPIO0 to GPIO1 and drives the LED on GPIO25.  The v2 board is "wired like a Pico 2" for exactly this
reason: CH1–8 are GPIO2–9, and the RESET taps (GPIO10–13) and the mark line (GPIO14) come out as
channels 9–13.

What sigrok's side gives an analyzer of our own (SUMP, the `ols` driver):
- **Rate:** 100 MHz / (div + 1), up to 200 MHz in demux mode.
- **Channels:** 4 groups of 8.
- **Depth:** capped at 262,144 samples by the 16-bit count fields, unless the device announces more
  memory.  Then the driver uses the "Pepino" 32-bit commands.
- **Triggers:** 4 stages of mask/value, levels only.  An edge is two stages, 0 then 1 (not tried with
  PulseView).
- **Capture:** buffered only, with optional RLE.
- **Releases:** PulseView 0.4.2 and sigrok-cli 0.7.2 have `ols`.  `conn=tcp-raw/<host>/<port>` lets any
  serial driver reach a TCP port, the node's relay for instance, but it is only in nightly builds
  (libsigrok's last release is 0.5.2, Dec 2019).  With a release build, use `socat` to make a pty on the
  lab server.

Nothing fx2lafw-compatible exists for the RP2040/RP2350.  So:
- gusmanb is the best stock analyzer here: hardware triggers at 100 MS/s.
- sigrok-pico fits the sigrok toolchain better, but its triggers live on the host.
- If we write our own, SUMP gets us PulseView and sigrok-cli with release builds.

## Architecture options

In every option the node is the co-processor's USB host, owns the API and the web UI, and keeps the wires
and DUT power through its own expanders, as in the v2 note.  So a co-processor reboot or a firmware swap
never drops a DUT.

### (a) gusmanb only

| | |
|---|---|
| Reused | The UF2 (pinned release) and its app and CLI on the lab server through USB/IP. |
| Written | On the co-processor: nothing.  On the node: BOOTSEL control, a USB host class for its CDC data interface, and a gusmanb protocol client for the web UI, written from a protocol description of our own (GPL code is not copied).  Day one can skip the class and the client: USB/IP and gusmanb's app only, no captures in the web UI.  A middle way: the node relays a TCP port to the CDC interface, and the app or `CLCapture` connects to it as to a Pico W.  The firmware answers Wi-Fi and USB with the same frames (untested). |
| Gives | 8 bus channels plus the RESET taps; 100 MS/s; 393 k samples; hardware triggers. |
| Lacks | Consoles, emulated devices, PWM and stimuli.  The pull-up switches stay off (the LSF's 10 k: I²C at 100 kHz), and VREF is declared, not measured. |
| Risks | A one-maintainer project, slow in 2026, whose protocol follows its app (pin the release).  Redistributing the UF2 means GPL source obligations: point at the exact upstream tag. |

### (b) our Zephyr firmware only

| | |
|---|---|
| Reused | The Zephyr drivers above: CDC-ACM, `uart-bridge`, the DW target and `regset_target_lib`, PIO, DMA, PWM, ADC.  The SUMP protocol, with Bus Pirate's MIT `sump.c` as a reference.  PulseView, sigrok-cli and the sigrok decoders on the lab server. |
| Written | The board; the vendor link and its protocol; consoles multiplexed on the link; pull-ups and VREF; the run-time glue for the I²C targets, plus models; stimuli; the analyzer (a pre-trigger ring on raw `hardware_dma`, triggers in PIO, 8/16 channels) and a SUMP server.  On the node: the host class, our protocol client, a SUMP TCP relay and consoles over RFC 2217. |
| Gives | Everything at once, including capturing a bus while emulating a device on it: PIO samples pins that I2C owns, as the spike does.  Apache-2.0. |
| Risks | The analyzer has to match gusmanb (an exact trigger position, 150 MS/s while USB is busy): weeks of bench time against a reference analyzer.  The DW target's corner cases.  Zephyr churn on a young port.  The largest code to maintain. |

### (c) both

| | |
|---|---|
| Switch by reflashing (recommended) | The node puts the co-processor in BOOTSEL and writes the other image over PICOBOOT.  About 100–200 KB, 4 KB erases and 256-byte writes: ≈ 2–4 s at full speed.  Deterministic, no boot magic.  Flash wear is negligible at one swap per job. |
| Both resident (later, bench first) | The ROM's partitions plus address translation let an unmodified image run from any partition.  But a `FLASH_UPDATE` reboot is not a toggle: booting the lower version marks the other image for erase.  The documented route is a chooser in slot 0 that calls the ROM's `chain_image()`: our Zephyr image could be that chooser.  It boots gusmanb's partition on command, and a RUN pulse comes back to Zephyr.  Unverified: whether gusmanb's UF2 carries an `IMAGE_DEF`, and how chaining from a running app behaves. |
| Reused / written | (a)'s node client plus (b) without the analyzer. |
| Risks | Two protocols on the node.  No capture while emulating.  Swaps need the DWC2 slot fix first (next section). |

## The link to the node

| Path | Verdict |
|---|---|
| **USB, behind the hub (v2: the USB2517I's 5th port)** | Recommended.  The node is the only client of one vendor bulk interface: its IN transfer is queued only while a reply is due, so it holds **one host channel, briefly**.  CDC-ACM ports exported to a lab server over USB/IP each hold **two** channels while open: Linux keeps the bulk IN and the notification IN pending, and DWC2 keeps a claimed channel per pending endpoint.  The hub's status IN holds one more, always.  So three open consoles leave one channel for everything else (v2 note, "USB host channels").  Consoles therefore go multiplexed on the link, and the node serves them over RFC 2217 like the AUX.  The CDC ports stay optional, for debugging.  gusmanb is CDC-ACM: two channels while a capture runs or its app is attached. |
| The existing I²C (100 kHz, ≈ 10 kB/s) | Control only, and not needed: the TCA9534A already gives the node RUN and BOOTSEL.  A capture (393 KB) would take ≈ 40 s.  As a target, the link would take one of the two DW controllers (one emulated device left) or need a PIO target.  It cannot update the co-processor (no I²C boot), so USB is needed anyway. |
| SWD from the node | No: the lead has no spare wire.  Bit-banging through the TCA9534A at 100 kHz would toggle ≈ 1–2 k bits/s, hours for an image.  SWD pads stay for bench bring-up with a probe. |
| The ROM's UART boot | On the QSPI SD2/SD3 pins at 1 Mbaud, RAM images only.  The lead has no UART, and the TCA9534A cannot make 1 Mbaud.  No. |

**Update and recovery: one path, the ROM's.**
1. The node gets the co-processor into BOOTSEL in one of two ways:
   - it asks the running firmware: ours calls `reset_usb_boot()`, gusmanb has command 4;
   - or, whatever runs, it holds QSPI_SS low and pulses RUN through the TCA9534A.
2. The RP2350 enumerates as 2e8a:000f with a drive and PICOBOOT.  The node uses EXCLUSIVE_ACCESS,
   FLASH_ERASE (4 KB), WRITE (256 B), READ to verify, then REBOOT2 to run the new image.
   picotool's libusb client for this is ≈ 600 lines; ours is ≈ 350 with UF2 parsing.
3. The image comes from the lab server, e.g. `POST /api/coproc/firmware`.  The node reflashes when the
   version the firmware reports differs from the expected one.

The ROM cannot be overwritten, so a bad image is always recoverable.  Rollback means flashing the previous
image.

**A prerequisite on the node.**  Every swap re-enumerates the co-processor twice, application → BOOTSEL →
application, each time with other endpoints.  DWC2 keeps per-endpoint state in 32 slots (`ch_data`),
cleared only on a root-port reset (`memset` in `uhc_dwc2.c`).  So each swap leaks about 4–6 slots, and a
few swaps exhaust them ("No channel data slot").  The fix the v2 note's second pass proposes, freeing a
device's slots when it goes, comes first.  DUTs that reflash through BOOTSEL need it anyway.  MCUboot and an SMP-over-USB client (which Zephyr does not have: SMP's client has only a Bluetooth
transport) are not needed.  Day one needs no flasher on the node: it holds BOOTSEL, exports the boot
device over USB/IP, and the lab server runs `picotool load -x`.

So the co-processor needs its own hub port, which v2 gives it: the USB2517I is in both variants.  Without
that port, nothing on the node could update or recover it.

## Effort, module by module

Our code only, in lines of C (and devicetree for the board).  The time is focused work by someone who knows
Zephyr, before bench time.  The spike calibrates the sizes: the link class is 169 lines and the capture 133.

**Co-processor (Zephyr)**

| Module | Upstream already | Ours | Time | Needed by |
|---|---|---|---|---|
| Board: RP2354B, 2 MB, pins | RP2350B boards, `partitions_2M_*` | 150 | 0.5 d | b, c |
| USB composite and the vendor link | UDC, `device_next` | 400 | 2 d | b, c |
| Control protocol, versioning, reboot to BOOTSEL | `reset_usb_boot()` | 500 | 3 d | b, c |
| Consoles: 2 hardware UARTs and 2 PIO UARTs, multiplexed on the link (CDC optional) | UART drivers, `uart-bridge`; #118562, carried as a west patch until merged | 300 | 2 d | b, c |
| Bus pull-ups (GPIO30–37), VREF and rails (ADC) | GPIO, ADC | 150 | 1 d | b, c |
| I²C emulation: 2 targets, pin pair, address and model chosen at run time | DW target, `regset_target_lib`, TMP103 and EEPROM | 300, plus ≈ 120 per new model | 4–5 d | b, c |
| PWM and PIO stimuli (patterns from RAM) | PWM, PIO | 250 | 2–3 d | b, c |
| Tests (protocol on native_sim) and a CI build | twister | 400 | 3 d | b, c |
| **Subtotal without the analyzer** | | **≈ 2.4 k** | **≈ 3.5 weeks** | c |
| Analyzer: pre-trigger ring, edge and pattern triggers, 8/16 channels | PIO, DMA (raw for the ring) | 700 | 2 weeks | b |
| SUMP server, with the 32-bit counts | none (Bus Pirate `sump.c`, MIT, as a reference) | 300 | 3 d | b |
| **Subtotal (b)** | | **≈ 3.4 k** | **≈ 6.5 weeks** | b |

**Node (ESP32-S3)**

| Module | Upstream already | Ours | Time | Needed by |
|---|---|---|---|---|
| RUN and BOOTSEL through the TCA9534A | GPIO expander driver | 80 | 0.5 d | all |
| USB host bulk class (binds gusmanb's CDC data interface or our vendor interface) | `usbh` class API, still moving | 350 | 4 d | all, except day one |
| PICOBOOT flasher with UF2 parsing | none | 350 | 3 d | all, except day one (picotool over USB/IP) |
| gusmanb client | none | 400 | 4 d | a, c |
| Our protocol client, consoles over RFC 2217, SUMP TCP relay | the node's RFC 2217 code | 500 | 4 d | b, c |

The web UI and the API (v2: ≈ 30 KB of JS, `/api/la/…`) are counted in the v2 note, not here.

**Totals**

| | Code | Time | Bench |
|---|---|---|---|
| (a) | ≈ 1.2 k lines on the node | ≈ 2.5 weeks | days |
| (c), on top of (a): our firmware without the analyzer | ≈ 2.4 k co-processor + ≈ 0.5 k node | ≈ 4.5 weeks | ≈ 1 week (I²C timing, consoles) |
| (b) | ≈ 3.4 k co-processor + ≈ 1.3 k node | ≈ 9 weeks | ≈ 2 weeks, against a reference analyzer |

**Upkeep per year**, if the co-processor app is built in the node's workspace (one Zephyr pin, one CI):
- about half a day per Zephyr bump;
- 2–3 days when the RP2350 port moves its names or files (Aug–Sep 2026: CPU clusters and board targets
  renamed, partitions moved to `zephyr,mapped-partition` in Apr);
- whenever the protocol changes: the node and the co-processor in the same commit, the version checked
  at enumeration.

Pinning the co-processor on a Zephyr release in its own manifest would cut the bumps to one a year.  It
has no network exposure, so no security reason to follow main.  The price is a second workspace in the
repo.

## What could go upstream (drafts only, with the user's OK)

None filed.  In order of size:

| What | Size | Why |
|---|---|---|
| TMP103 target: start after the sensor it reads | a few lines | found by the spike: with `sensor`, the default priorities fail the init-order check |
| `zephyr,uart-bridge`: fail init when a peer has no interrupt API | a few lines | found by the spike: a bridge to today's PIO UART builds and never moves a byte |
| Review #118562 (interrupt-driven PIO UART) | review | our consoles 3 and 4 need it; until it lands, a west patch ([zephyr/patches.yml](../zephyr/patches.yml)) |
| A PIO capture sample (`samples/boards/raspberrypi/rpi_pico/pio_capture`) | ≈ 250 lines | the spike's `la_pio.c` and its shell, with pre-trigger once written; nothing like it in tree |
| picotool's reset interface as a `usbd` class, so `picotool reboot -f` works on Zephyr apps | ≈ 150 lines | coordinate with #105519 (open), which uses a shell command and a 1200-baud touch instead |
| Ring and chaining in `dma_rpi_pico` | larger | drivers (#118562, our capture) program `hardware_dma` behind Zephyr's back today |
| A USB host CDC-ACM class for `usbh` | larger | the node would talk to gusmanb and to any CDC DUT without its own class |

The user asked for drafts only: the first two can be draft PRs as soon as they are wanted, the rest after
the bench.
