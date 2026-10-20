# DATA ×4 v2: virtual wires, a co-processor, two assembly variants (research)

**Status (2026-10-19): research only, nothing designed.**  The user asked for real electrical links
between the four boards of a converted bay, switched from the web UI, for a built-in logic analyzer with a
web UI, sized "to the maximum we can handle", then for a co-processor ("pourquoi pas de coprocessor ?")
and for an assembly variant without the analyzer.  The illustrated version (UI mock, to-scale placement,
tables) is the page [Fils virtuels et analyseur](https://claude.ai/artifact/DeudMxKuwkSjVR6naQZj55)
(French, private to the owner).  v1 ([electronics.md](electronics.md), "DATA ×4 v1.0") is the base: v2
only adds to it.

## Proposal

| Block | Choice | Why |
|---|---|---|
| Pins | 8 per port, 32 in all, on a 2 × 6 2.54 header per port (GND, VREF, P1–P8, RESET, BOOT), Dupont jumpers to the board's pins | the header sets the limit: 2 × 6 is 15.2 mm at the ports' 18 mm pitch, 2 × 8 (20.3 mm) does not fit |
| Matrix | 2 × WCH CH446Q (16 X × 8 Y analog crosspoint, C109471, $1.59, Economic): each chip takes two ports' 16 pins on X, the 8 Y lines of both chips joined are the 8 buses | MAX14661 is 16 × 2 (8 chips, $45, 4 I²C addresses only, the reel Standard-only); ADG2128 $29 needs 8–12 V; MT8816 out of stock |
| Matrix supply | ±5 V: TPS60400 (C9839) makes −5 V | halves the CH446Q's R_on (120 Ω typ. at +5 V); this is what makes I²C at 400 kHz work |
| Levels | 1 × LSF0108 per port (VQFN-20 2.5 × 4.5, C130008): A side = the DUT's VREF, B side = the 3.3 V matrix, Vref_B biased from PORTn_VBUS through 200 k (a switched-off port isolates its pins), 10 k B-side pull-ups | passive FET: I²C, push-pull and the SWDIO turnaround pass without direction control.  **Not TXS010x**: their one-shots retrigger and oscillate behind series R and a switch, and their pull-ups add up on a shared bus |
| Protection | 100 Ω in series (not 330 Ω) and TPD4E05U06 (C138714) at the header, on every pin | 330 Ω + R_on breaks I²C's V_OL (≈ 1 V with 2.2 k); 100 Ω still bounds two outputs fighting to ≈ 10 mA (15 mA per switch) |
| Node-owned control (I²C) | port power and control stay on v1's 2 × TCA6408A (EN, FAULT, RESET, BOOT); a TCA9534A (C206010, 0x38) drives the CH446Qs (DAT, CK, RST shared, one STB per chip), the co-processor's RUN and QSPI_SS (BOOTSEL) and a mark line | wires and DUT power survive any co-processor reboot (watchdog, crash, image swap, BOOTSEL resets its pads and would cut all four ports); a crosspoint is ≈ 17 I²C writes, no readback: the node keeps a shadow table and opens before closing; CH446Q RST pulled so the matrix is all-open at power-up |
| Co-processor | RP2354B (RP2350 with 48 GPIO and 2 MB flash in the package, QFN-80 10 × 10, C39843328, $1.53) wired like a Pico 2 (12 MHz, GPIO0→1 link, LED GPIO25); buses on GPIO2–9 (CH1–8), RESET taps on GPIO10–13, the mark on GPIO14, bus pull-up enables on GPIO30–37 (pulled down: off), VREF dividers on ADC GPIO40–43, rails on GPIO44–47 | the same board runs either firmware (next section); every bus pin can be a hardware UART TX or RX, I²C SDA or SCL, PWM A or B |
| Data path | USB2517I (7 ports, QFN-64 9 × 9, C478081, $4.51) instead of the USB2514B: 4 DUTs, the co-processor, 2 spare | the PH 8 lead has no spare wire; buffered captures: 384 KB ≈ 0.4 s over FS USB + ≈ 0.8 s over Wi-Fi (Zephyr ESP32-S3 TCP ≈ 4 Mbit/s).  The ESP32-S3 has 8 host channels for the whole drawer: one multiplexed bulk interface on the co-processor, not 4 CDC ports, and the node never leaves an IN transfer pending on it; see "USB host channels" below: Zephyr's DWC2 driver needs channel sharing, for v1 already |
| UI | the node owns the API (`POST /api/la/captures`, `GET …/{id}`, `GET …/{id}/data`, a WebSocket for state; captures kept in the 8 MB PSRAM); the node's page gets "Wires", "Analyzer" and "Co-processor" cards: a canvas viewer and JS decoders (UART, I²C, SPI, then SWD), `.sr` and VCD export, per-bus roles, console tabs | ≈ 30 KB, served from flash, the rack's style, works on a phone; Surfer is 14.9 MB of WASM and has no decoders; no public WASM libsigrokdecode |
| bayctl | `bayctl capture <bay> --ch … --rate … --trigger … --decode …` saves `.sr` + JSON and decodes with sigrok-cli (raw input: `-I binary:numchannels=…:samplerate=…`), also the decoders' CI oracle against sigrok-dumps; consoles over RFC 2217 like the node's AUX | one annotation format `{ss, es, pd, cls, text}` for both |

Expected speeds pin → bus → pin (Elmore estimate, to be measured): CH446Q ±5 V, 100 Ω, LSF0108: rise
≈ 60 ns, SPI/SWD ≈ 5 MHz, I²C 400 kHz with a 2.2 k bus pull-up (1 MHz no), UART 3 Mbd.  A 1.8 V ↔ 3.3 V
wire relies on the LSF's pull-ups for the top of the edge: ≈ 1–2 MHz.

## The co-processor's firmware: stock or ours

**Settled by [coproc-firmware-research.md](coproc-firmware-research.md) (2026-10-19), which supersedes
this section where they differ:** (c) staged.  The stock gusmanb analyzer on day one; our Zephyr firmware
only when consoles or emulated devices are wanted, and **without its own analyzer** (≈ 2.9 k lines,
≈ 4.5 weeks, node side included); the node switches images by reflashing through the ROM's PICOBOOT
(BOOTSEL held through the TCA9534A, ≈ 3 s); no MCUboot.  The table below is the first pass's view of a
full firmware with its own analyzer, option (b) there.

| | Stock gusmanb LogicAnalyzer UF2 | Our Zephyr firmware |
|---|---|---|
| Analyzer | 100 MS/s, 393,216 samples on CH1–8 (8-bit mode), edge/pattern/burst triggers; gusmanb desktop app | ≈ 75 MS/s with a sample-exact edge trigger in PIO (≈ 37 MS/s on a pattern), ≈ 380 k samples on 8 channels; SUMP protocol: PulseView and sigrok-cli (`ols` driver), also remotely through the node |
| Consoles | none | 4: 2 hardware UARTs + 2 PIO UARTs (or 4 PIO); Zephyr's PIO UART polls today (interrupt PR #118562 open): our own DMA/IRQ code meanwhile |
| Emulation | none | 2 × I²C target (DesignWare target mode; `regset_target_lib` register-map models, ≈ 200–400 lines each), PWM, PIO stimuli to the nanosecond, UART TX |
| Pull-ups, VREF | pull-ups off (the LSF's 10 k: I²C at 100 kHz); VREF declared | switched per bus; VREF measured for the interlock |
| Update | command 4 → BOOTSEL → UF2 | MCUboot (2 MB layout: 64 K + 2 × 832 K + 320 K) + DFU or SMP through the node, revert on a bad image |
| Recovery | the node pulls RUN and QSPI_SS → ROM BOOTSEL → `picotool` from the lab server over USB/IP; no I²C boot in ROM (UART boot exists, the lead has no UART), but the ROM cannot be overwritten | same |
| Licence | GPL-3.0; our node-side client written from scratch | Apache-2.0: Bus Pirate's `sump.c` (MIT), pico-examples' PIO+DMA capture (BSD-3), Jumperless' CH446Q code (MIT) can be reused; linking gusmanb or sigrok-pico code would make the image GPL-3.0 |
| Code | ≈ 300 lines on the node | ≈ 4–6 k lines (DTS + MCUboot 300, USB 400, pull-ups/VREF 300, analyzer + SUMP 1,000, consoles 600, emulation 600, control protocol 500) + ≈ 1 k lines of Python |
| Time | none | ≈ 4 weeks to a first useful version (consoles, pull-ups, VREF, control, MCUboot), 8–12 weeks for all |
| Upkeep | a one-maintainer project whose protocol follows its app | a 4th firmware in the repo; 1–3 days per Zephyr bump (RP2350 support still moving: one core only, polled PIO UART, board targets renamed in Sep 2026) |

Proposed: the co-processor hardware in the full variant, wired for both; the stock UF2 on day one (wires
and analyzer work without firmware of our own), then our Zephyr firmware only when consoles or emulated
devices are wanted, swapped in and out by PICOBOOT; our own analyzer only to capture a bus while emulating
on it, or if gusmanb stalls (coproc-firmware-research.md, option (b)).

Comparison points:

| Option | Analyzer | Emulation · consoles | Update from the node | Own firmware | Cost | Verdict |
|---|---|---|---|---|---|---|
| RP2354B, our Zephyr | ≈ 75 MS/s sample-exact trigger (150 without), ≈ 380 k × 8 | 2 I²C targets, PWM, PIO stimuli · 4 | USB (MCUboot + DFU/SMP), BOOTSEL recovery | 1 | $1.53 + crystal | later |
| RP2354B, stock gusmanb | 100 MS/s, 393 k × 8 | none · none | UF2 | 0 | same | day one |
| RP2350 gusmanb + STM32G0B1 Zephyr | 100 MS/s | G0B1: 3 I²C targets, 6 USART + 2 LPUART · 3 CDC + 1 multiplexed | G0B1 ROM I²C bootloader (≈ 7 s per 64 KB at 100 kHz) or DFU | 1 + upstream | ≈ $5–6 | two chips and two hub ports for what the RP2354B does alone |
| STM32G0B1 alone | ≈ 16 MS/s CPU-polled (USB and I²C frozen meanwhile), ≈ 50 k × 16 | best (3 I²C, 8 UARTs) · 3 CDC + 1 | ROM I²C, USB DFU, USART | 1 | $3.31 | analyzer too weak |
| STM32C071 alone | ≈ 12 MS/s, ≈ 5 k samples (24 KB RAM) | 2 I²C, 2 USART · 2 | ROM DFU, USART, I²C | 1 | $2.5–5 | no |
| FX2 | ≤ 0.5 MS/s streamed behind our FS host | no I²C target · 2 | RAM-loaded by the host each plug-in | 2 | $11 | no |
| iCE40UP5K | ≥ 100 MS/s, 64 k × 16 | all in soft cores (USB, CPU, UARTs) | USB DFU through a soft USB core | 2+ | ≈ $13 | months of work |

What decides it: on STM32G0/C0 the GPIO sit on the CPU-only IOPORT bus and DMA cannot read them (ST
confirms), so the usual timer-DMA analyzer trick (72 MS/s on an F746) does not exist there.  Their real
asset is updating over the lead's I²C through the ROM bootloader; on the RP2354B updates go over USB and
recovery through BOOTSEL, which the node holds.  CH32V307 (no Zephyr USB driver) and SAMD51 (no Zephyr
I²C target) lack drivers; the nRF52840's DMA cannot read GPIO either.

## Two assembly variants, one PCB

Everything optional (matrix, co-processor and their supplies, the TCA9534A) is on the bottom side; the
translators, ESD and arrays on the top side are DNP in the base variant.  Same Gerbers, two BOM + CPL pairs
(`fab/<variant>/`), a `variants` tag per part in `design.py` (it already has `dnp`), a test that the base
variant has nothing on the bottom and that its unconnected lines rest.  About half a day of tooling.

| | Base | Full |
|---|---|---|
| Sides | top only | both |
| JLC | Economic (setup $8, stencil $1.50) | Standard (setup $50, stencil ≈ $16) |
| Functions | v1's: 7-port hub, per-port power and measurement, EN/FAULT/RESET/BOOT, headers | + 32 pins on 8 buses, the co-processor |
| Parts per board | ≈ $18 | ≈ $31 |
| 2 prototypes (5 PCBs) | ≈ $82 | ≈ $195 |

Double-sided assembly costs ≈ $56 per order whatever the quantity (≈ $28 per board on 2 prototypes, ≈ $6
on 10); the ≈ 10 new extended parts (≈ $30) weigh as much.  Two variants in one order are two assembly
orders, so twice the fixed fees.  The node detects the variant (the co-processor answers or not) and hides
the cards.

## Mechanics and board

* **108 × 27 mm** (+3 mm, the most the rear bay takes): SolidCraft gives 1.0 mm to the rear wall; under
  the board 5.3 mm to the floor (an LQFP-44 is 1.6 mm, header pins ≈ 3 mm); the bosses need Ø 8 mm keep-outs.
* Concept placement (courtyards, checked for overlaps per side, not routed): top keeps all of v1 plus the
  headers, LSF0108s, ESD and arrays (52 % of the board); bottom takes the two CH446Q, the charge pump,
  the TCA9534A and the RP2354B block (21 %).  The four holes move, so do the drawer's bosses
  (`DATA_X4_HOLES`, tray session).  Single-sided would need ≈ 108 × 35 mm, which does not fit.
* Fabio's rule "no tracks on inner layers" leaves two routing layers for 32 pins, 8 buses and the
  co-processor's USB: the main design risk.  Each CH446Q under its two ports, a straight via from the
  translator above, buses on the bottom; fallback 6 layers (signal/GND/signal/signal/power/signal).
* The Dupont jumpers leave the rear headers upwards and over the port wall: the headroom above the rear
  bay is to be checked with the tray session.

## Cost of the full variant

Added parts per board ≈ $16: hub +$2.7, co-processor $1.9, matrix + −5 V $4.0, 4 × LSF0108 $4.5, ESD,
pull-ups and dividers $0.8, TCA9534A $1.4, headers and passives $0.5.  To be confirmed by a JLC quote.

## Order v1 now for B3

Recommended: v1 validates everything v2 keeps (hub behind the FS host, per-port power and measurement,
EN/FAULT/RESET/BOOT, USB/IP of 4 DUTs, the rear-bay mechanics, the PH 8 lead), for about the price of the
future base variant; v2 still needs a design session, the bosses moved and, for the full variant, a dearer
Standard order.

## Second pass: checks and findings (2026-10-19)

A second session took the research over and checked what the first left open.  Nothing above changes
except where noted.

### USB host channels (affects v1 too)

Zephyr's `uhc_dwc2.c` (main, Oct 2026) queues transfers and claims one of the S3's 8 host channels
(`OTG_NUM_HOST_CHAN = 8`, Espressif) per transfer in flight, one per endpoint.  A pending **IN** transfer
keeps its channel until data arrives: a bulk IN is retried on NAK by the core (NAK not unmasked), an
interrupt IN halts on NAK and waits for its next interval still claimed (`DO_WAIT_SOF`).  `submit_pending()`
stops when no channel is free, so control and OUT transfers wait behind them.

- Count: the hub's status interrupt IN is always pending (`usbh_hub.c` `hub_start_interrupt`), and each
  CDC console a USB/IP client opens adds two (Linux `cdc_acm` keeps its notification URB and bulk IN
  reads queued).  Hub + 4 open consoles = 9 transfers for 8 channels: one console waits, and a write to
  a quiet board, a SET_LINE_CODING or the enumeration of a re-plugged board waits until some board
  prints.  With 3 open consoles one channel is left for all the rest.
- This is a v1 issue (4 DUTs behind the hub); v2's co-processor adds little if the node only polls it
  (command OUT, reply IN, no IN left pending).
- Fix in the driver, upstreamable: release an interrupt IN's channel when the poll NAKs and claim one
  again at the next interval (its toggle and schedule already live per endpoint in `ch_data`); for bulk
  IN, unmask NAK when transfers are waiting, halt and requeue at the tail (round robin).  A few hundred
  lines plus a bench test: 4 consoles open, a command to a quiet board, a re-plug.
- Per-endpoint state: `ch_data` has 32 slots (`2 × MAX_CHANNELS`) keyed by `usb_device` pointer and
  endpoint, cleared only on a root-port reset.  Devices behind the hub never give theirs back, and
  `usb_device` comes from a slab, so a re-enumerated board can inherit the previous one's data toggle
  (until #121688 resets toggles on SET_CONFIGURATION) and a board switching endpoint sets (BOOTSEL ↔
  application) leaks slots until "No channel data slot".  Hub 2 + 4 composite DUTs ≤ 24 + co-processor
  3 is already close to 32.  Fix: free a device's slots when it goes (a UHC hook from
  `usbh_device_free()`), or key them by address and clear them on SET_ADDRESS.
- `CONFIG_USBH_USB_DEVICE_MAX`: the spike has 6 (hub, 4 DUTs, 1); v2 needs 6 exactly, so 8.

### Matrix: the CH446Q datasheet

WCH CH446 datasheet: VDD − VEE ≤ 13.2 V, VDD > GND + 4 V; +5 / −5 V is one of the recommended supplies.
R_on 120 Ω typical / 185 Ω max at 5 V, 45 / 65 Ω at 12 V (25 °C); no figure at ±5 V: ≈ 55–65 Ω by
interpolation (VDD drops to ≈ 4.55 V at the lead's worst load).  10–25 pF per switch pin, 0.5 pF
feed-through, 50 MHz −3 dB, 15 mA per switch and 100 mA in all, logic VIH 2.0 V at VDD = 5 V (3.3 V
expander outputs are fine).  RST high opens every switch; the power-on state is not specified, hence
RST pulled up until the node configures.  LCSC C109471 $1.59, 1,744 in stock, Economic.  SGM6516
(SG Micro, an MT8816 second source): 0 in stock, $10.9.  The speed estimates above hold: I²C at
400 kHz with 2.2 k gives V_OL ≈ 0.6 V at the far board (limit 0.99 V at 3.3 V).

### Matrix alternatives: CH449F, CH446X (user question, 2026-10-19)

The user asked about WCH's CH449F and CH446X.  Datasheets: CH449DS1 v1.1 (2022-05-23, wch.cn file 350),
CH446DS1.  Prices are the user's LCSC figures at 10 pieces; stock from the JLC parts library the same day.

| | CH446Q × 2 (kept) | CH449F × 8 (same 32 × 8) | CH446X × 4 |
|---|---|---|---|
| Part | 8 × 16 crosspoint, LQFP-44 10 × 10 | two independent 4 × 4 matrices (32 switches), QFN-24 4 × 4 | 5 × 24 crosspoint, LQFP-44 10 × 10 |
| Topology for 32 pins × 8 buses | one chip per two ports, Y lines joined = the 8 buses | one chip per half-port: 4 pins, each tied to A_nX and A_nY; X → buses A–D, Y → E–H | 5 Y lines per chip: two chips per 16 pins for 8 buses (2 Y spare) |
| Cost | 2 × $1.35 + TPS60400 ≈ $3.2 | 8 × $1.07 + an I²C mux ≈ $9.4 | 4 × $1.50 + TPS60400 ≈ $6.5 |
| Bottom-side area (courtyards) | ≈ 335 mm² | ≈ 225 mm² | ≈ 650 mm² |
| Bus connections to route | 16 (each bus on 2 chips) | 64 (each bus under all 8 chips) | 16, and every pin to 2 chips |
| R_on | ≈ 55–65 Ω at ±5 V (interpolated); 120 / 185 Ω at +5 V only | at VDD 5 V: 4 / 7 Ω at 0 V, 6 / 10 Ω at 2 V, 10 / 15 Ω at 3.4 V (typ / max) | as CH446Q |
| C per switch pin | 10–25 pF | on 10–15 pF, off 7–10 pF | as CH446Q |
| Supply, signals | VDD − VEE 4–13.2 V; ±5 V here (−5 V from the TPS60400); signals VEE..VDD | single 2.1–5.5 V, CMOS rail to rail: 5 V here, **no −5 V**; signals −0.3..VDD + 0.3 V | as CH446Q |
| Current per switch / in all | 15 mA / 100 mA | **6.5 mA / 30 mA** | 15 mA / 100 mA |
| Control | serial DAT + CK shared, one STB per chip, no address (the node's TCA9534A, 17 writes per crosspoint); state at power-up unspecified, RST held | I²C-like, write only, one ADDR pin: **2 chips per bus** (0x19–0x1B, 0x29–0x2B; free on the node's bus); 8 chips need a TCA9548A mux; one write sets a whole 4 × 4; power-on and low-voltage reset open everything | as CH446Q |
| JLC (2026-10-19) | C109471, 1,744 in stock, Extended, Economic | C54973457, 377 in stock (≈ 47 boards), Extended, Economic | C3018882, 42 in stock, Extended |

The user's summary is half right: ≈ 5 Ω is typical at 0 V, but the 28 Ω is the CH449F's maximum at
**VDD = 3.3 V** with a 2 V signal (typical 20 Ω).  At VDD = 5 V it stays ≤ 15 Ω over our 0–3.4 V.

Speed, with the same Elmore assumptions as above: the CH449F's low R_on is undone at the board level.
Every bus carries 8 switch pins (56–80 pF, against 20–50 pF for two CH446Q Y pins), and the 6.5 mA
limit wants ≈ 220 Ω instead of 100 Ω in series (two 3.3 V outputs fighting through 100 Ω and the
matrix push ≈ 11 mA).  Rise ≈ 65–80 ns with 220 Ω (≈ 40 ns with 100 Ω, beyond the switch's rating in
a fight) against ≈ 45–60 ns for the CH446Q; SPI/SWD ≈ 5 MHz either way; I²C 400 kHz V_OL ≈ 0.7 V at
the far board (0.6 V with the CH446Q, limit 0.99 V): no gain.  The CH446X has the CH446Q's figures
with fewer buses per chip.

**Kept: the CH446Q × 2.**  The CH449F wins on R_on, a single 5 V supply, its power-on reset and its
size, but for the same 32 × 8 it takes 8 chips plus an I²C mux, ≈ 3 × the cost, 4 × the bus
connections on our two routing layers, 377 in stock and a 6.5 mA switch, for no speed gain.  It would
fit a reduced matrix: 4 pins per port on 8 buses, one chip per port (≈ $5 with the mux, no −5 V, each
bus on 4 chips); the user asked for the maximum.  The CH446X has only 5 Y lines: 8 buses take 4 chips.
The CH448F (dual 8:1 mux, $0.47) joins one input at a time: a probe selector, not wires.  No mix.

### An analyzer without the matrix, single-sided? (user question, 2026-10-19)

A middle variant: base + the RP2354 analyzer tapping the port pins directly through the LSF0108s (P1–P4
of each port = CH1–16, 16-bit mode, ≈ 196 k samples; 24 channels at most with gusmanb), no matrix, all
parts on the top side so that JLC Economic can build it.

- **It does not fit.**  Searching the concept placement (`layout.py`'s courtyards, holes and notch, 0.3 mm
  from the edges), the largest free rectangle on the top side is 5.0 × 13.1 mm; the RP2354A alone needs
  7.6 × 7.6, its block with the 12 MHz crystal, 3.3 µH and decoupling ≈ 11 × 10, the RP2354B's ≈ 14 × 13.
  The top is 1,104 mm² free out of 2,696, all of it in pockets between the port columns (18 mm pitch, set
  by the USB-C) and the routing needs them.  Room for the block means ≈ 108 × 33–35 mm; the rear bay
  stops at 27.
- **The parts are not the obstacle**: RP2354B (C39843328) and RP2354A (C41378174), the 12 MHz crystal
  (C9002, Basic), USB2517I, LSF0108, TPD4E05U06, TCA9534A (C206010) are all Economic-eligible; Economic
  assembles one side only.
- So the middle variant is the full PCB without the matrix: still two sides, JLC Standard.  ≈ $27 of
  parts per board (base ≈ $18 + RP2354B block $1.9 + TCA9534A $1.4 + translators, ESD and arrays
  $5.3), ≈ $185 for 2 prototypes (≈ $205 with the 10 % margin), against ≈ $31 / $195 ($215) for the
  full: the double-sided fixed cost dominates.  And the analyzer would need fixed taps (CH1–16 on
  P1–P4) instead of the buses: different copper, or 16 more traces on the full board.  Lost against
  the full: every virtual wire, any-pin probing through the buses, routed consoles and emulated devices.
  **Not recommended.**
- **The zero-change option**: a Pico 2 with the stock gusmanb UF2 in one sub-slot, Dupont jumpers from
  its GP2–GP22/26–28 to the neighbour's pins.  ≈ $5, works with v1 today: it enumerates on the hub like
  any DUT, the node exports it over USB/IP to a PC running gusmanb's app (sigrok decoders included),
  and the sub-slot's BOOT wire on its BOOTSEL test point plus port power let the node reflash it.  Not
  "built in": it takes one of the four sub-slots, the wiring is by hand per test, there is no level
  translation (1.8 V boards misread at 3.3 V thresholds), no series resistor or ESD, and it cannot
  reach the buses.  **Recommended now**, on B3 with v1: it exercises the node's gusmanb client, the web
  UI and the USB host channel fix before v2, and the same client then drives v2's on-board RP2354B.

### CAN through the matrix? (user question, 2026-10-19)

- **CAN_H / CAN_L: no.**  The CH446Q itself passes VEE..VDD, but the path to a pin goes through the
  LSF0108, which clamps to the port's VREF (≤ 3.6 V): a dominant CAN_H at ≈ 3.5 V is clipped, and the
  10 k B-side pull-ups to 3.3 V load both lines.
- **Logic-level CAN (the MCUs' TX/RX, no transceivers): only with open-drain TX.**  CAN is a wired-AND
  bus and every controller must read its own bits back.  Push-pull TX pins on one bus fight (≈ 9 mA
  through 2 × 100 Ω and the matrix, level undefined); the classic fix, a diode per TX, is not in the matrix.  If each
  DUT sets its CAN TX open-drain (pinctrl `drive-open-drain`, e.g. STM32, ESP32 TWAI through its GPIO
  matrix), TX and RX of every node go on one bus, pulled up by the LSF's 10 k and the switchable 2.2 k:
  500 kbit/s works, 1 Mbit/s is marginal (τ ≈ 150–250 ns), a CAN FD data phase does not.  Two pins
  per DUT, at least two nodes (ACK).
- **The analyzer**: put a TX or RX (or a transceiver's RXD) on a bus and decode with sigrok's `can`
  decoder (gusmanb's app, `bayctl capture --decode can`); CAN_H/CAN_L themselves are differential and
  not readable.
- **A dedicated CAN pair** for DUTs with their own transceivers: CAN_H and CAN_L shared by the four
  ports, bypassing the translators, two 120 Ω terminations on jumpers (DUT boards often carry their
  own), a PESD2CAN TVS (C2687131, $0.04).  ≈ $0.2 of parts plus hand-soldered headers, as in v1.
  Space: four 1 × 2 headers do not fit the rear row (2.8 mm between the 2 × 6 headers), and a 2 × 4
  bay header (10.7 × 5.6 mm) does not fit the current placement either (largest free rectangle 5 × 13 mm):
  it would take P7/P8 of each 2 × 6 header by assembly option (0 Ω instead of the LSF, 8 matrix pins
  fewer) or a re-layout of the right block.  The boards that sit in sub-slots (XIAO, Pico 2) carry no
  transceiver, and RP2040/RP2350 and nRF52/54 have no CAN controller at all.  **Not recommended**: the
  open-drain trick covers logic-level CAN between ESP32 or STM32 boards for free; boards with real
  CAN transceivers sit in single bays with their own cabling.

### Limits to state in the UI and the docs

- **5 V logic boards cannot be wired**: the LSF0108's A side stops at 4.5 V and the buses are 3.3 V.
  The node refuses a VREF above 3.6 V.
- **A missing VREF must isolate the port**: with VREF unconnected the LSF's reference floats up through
  the 200 k bias and the pass FETs let 3.3 V through to a 1.8 V board.  A 100 k pull-down on each VREF
  input keeps an unconnected port at 0 V, which blocks its pins.  Expert-obvious, for the design.
- **A probe is not passive**: the 10 k B-side pull-up and the bus capacitance load the pin; an undriven
  pin reads high.
- **Rising edges from a 1.8 V board reach the analyzer late** (the LSF's pull-up finishes the edge):
  0.1–0.4 µs, so timing between a 1.8 V and a 3.3 V board is only good to ≈ 0.5 µs.
- **8 channels at a time**: only what is on a bus is captured.

### Off-the-shelf analyzer firmware

gusmanb LogicAnalyzer 6.0 (latest release 6.0.0.1, 2025-02-09, GPL-3.0) supports the Pico 2; its README gives ≈ 380 k samples
on the RP2350 as the author's projection; CH1–8 must be the first channels in 8-channel mode (as
wired).  Its desktop app (Windows, Linux, macOS) runs all the sigrok protocol decoders since 6.0.  So
on day one the co-processor can be exported over USB/IP like a DUT and used from a PC with that app,
with no code at all; the node page's analyzer card comes next.  sigrok-rp2350 (c1570, RP2350B, 32
channels, libsigrok's `raspberrypi-pico` driver) is marked work in progress (7 stars): not a base.

### Data path: the other ways, for the record

| Option | Why not |
|---|---|
| USB2514B kept, a second hub cascaded on port 4 | two hubs, two crystals, more area than one USB2517 |
| A USB switch (TS3USB221-class) on port 4: DUT 4 or the co-processor | the fourth board drops off USB during every capture |
| A UART to the node on a PH 10 lead | node respin and new lead; gusmanb speaks USB or Wi-Fi only, so our firmware on day one |
| The lead's I²C at 400 kHz (≈ 2 k pull-ups) | ≈ 10 s per capture, shared with the expanders and INA226 polling |

### Mechanics: headroom for the jumpers

Nothing sits over the rear bay: B3 has no camera (`config/rack.yaml` › `cameras: [B2]`), and in a
camera bay the pod hangs over the plate's middle (lens at bay (64, 84)), far from the rear bay
(drawer y 166–194).  The bay is ≈ 165 mm high; the jumpers need ≈ 25–30 mm above the board.
No change for the tray session beyond moving the bosses.

### JLC cost

No real quote: there are no v2 Gerbers yet, and none are uploaded from research.  The estimates above
stand.  The power hub's real Standard quote (2ab88eb) came ≈ 7 % over its estimate (≈ $243 against
≈ $227), extended-part feeders ($72.85) its largest assembly line: allow ≈ +10 % on the full variant
until the design is quoted.

## Decided (user, 2026-10-19)

The four recommendations, as asked:

1. v1 is ordered now for B3.
2. The co-processor runs the stock gusmanb analyzer on day one; our Zephyr firmware (without its own
   analyzer) comes only when consoles, emulated devices or driven pins are wanted (coproc-firmware-research.md).
3. B3 gets the full variant; bays that only need power and reset get the base.
4. DUT side: Dupont jumpers pin by pin to start; adapter boards per DUT model later, for the models that
   keep coming back.

Meanwhile, a Pico 2 with the gusmanb UF2 in one of B3's sub-slots ("The zero-change option" above):
B3.3, set up in [multi-dut-node.md](multi-dut-node.md#a-logic-analyzer-in-a-sub-slot).

## Decided (user, 2026-10-20)

1. **Two signal layers don't route; v2 goes to 6 layers, for the analyzer bays only** (on the 108 mm
   horizontal board; item 4 replaced that board).  The placed v2
   left about 240 links open after six Freerouting passes (40–46 nets cross each port's area for about
   30–35 tracks of room).  v1 (4 layers) stays the board of the other converted bays; v2 is the full
   board only, on JLC06161H-3313 with every signal layer beside a plane.  JLC: $51.90 against $32.10
   for 5 bare boards (ENIG is forced at 6 layers), 8–9 days instead of 3–4; assembly fees don't depend
   on the layer count.  The "two assembly variants, one PCB" plan above is dropped.
   Stack: first F · GND · signal · +5V · +3V3 · B, which left about 50 links open; then (user, same day)
   F · GND · signal · signal · power (+5V and +3V3 areas) · B, the fallback named above: four signal
   layers, each still beside a plane.
2. **The 2 × 6 headers are SMD, soldered by the user** (out of the JLC BOM and CPL), in the middle of
   the board.  That keeps v1's four holes, so both boards drop into the universal drawer unchanged;
   through-hole tails would have blocked the crosspoints underneath, and a part with locating pegs
   (hanxia TP-D) puts its pegs there too.  Wider pads (1.3 mm) instead.  The standing board of item 4 has
   nothing on its rear face under them, so its headers are through-hole (the user, easier to solder).
3. **Analog output: none** ("Pas de sortie analogique").  Costed for the record, none of it on the board:
   - a DAC7311 (12-bit SPI, buffered, about $1.7, 9 µs settling, so sine waves to about 10 kHz) on bus H,
     the matrix taking it to any pin, with a 0 Ω option across each port's LSF on P8 (that pin then loses
     its level translation) and the RP2354B's spare ADC (GPIO46) reading it back: about $1.8 a board plus a
     $3 feeder, about 25 mm² on the bottom, 0–3.3 V capped in software at the port's measured VREF;
   - cheaper: PWM + RC + op-amp (about $0.3, about 5 kHz), or an 8-bit R-2R on PIO (about $0.6, up to
     about 500 kHz, 8 spare GPIOs).
   Driven pins stay digital (forced levels, PWM) from our Zephyr firmware.
4. **v2 stands behind the port wall, 100 × 70 mm, one face assembled** ("v2 en 100 × 60–70 oui").
   This is option B of [data-x4-v2-layout-options.md](data-x4-v2-layout-options.md).
   - Why: at 108 × 37 mm with parts on both faces, the 6-layer board still left about 30 links open.
   - Mounting: vertical USB-C receptacles through the port wall's openings, and a printed slotted cradle on
     the drawer's DATA ×4 bosses.  The board has no holes.
   - Assembly: every JLC part on the front face (Economic PCBA); the lead's PH 8 alone on the rear,
     soldered by hand.
   - Placement: the parts in blocks around the pins they use (electronics.md › DATA ×4 v2).
   - Layers: 4 ("si on peut repasser à 4 couches ce serait top").  Every signal routes at 4 layers on the
     standing board, as at 6.
