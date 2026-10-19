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
| Node-owned control (I²C) | port power and control stay on v1's 2 × TCA6408A (EN, FAULT, RESET, BOOT); a TCA9534A (C206010, 0x38) drives the CH446Qs (DAT, CK, RST shared, one STB per chip), the co-processor's RUN and QSPI_SS (BOOTSEL) and a mark line | wires and DUT power survive any co-processor reboot (watchdog, crash, MCUboot swap, BOOTSEL resets its pads and would cut all four ports); a crosspoint is ≈ 17 I²C writes, no readback: the node keeps a shadow table and opens before closing; CH446Q RST pulled so the matrix is all-open at power-up |
| Co-processor | RP2354B (RP2350 with 48 GPIO and 2 MB flash in the package, QFN-80 10 × 10, C39843328, $1.53) wired like a Pico 2 (12 MHz, GPIO0→1 link, LED GPIO25); buses on GPIO2–9 (CH1–8), RESET taps on GPIO10–13, the mark on GPIO14, bus pull-up enables on GPIO30–37 (pulled down: off), VREF dividers on ADC GPIO40–43, rails on GPIO44–47 | the same board runs either firmware (next section); every bus pin can be a hardware UART TX or RX, I²C SDA or SCL, PWM A or B |
| Data path | USB2517I (7 ports, QFN-64 9 × 9, C478081, $4.51) instead of the USB2514B: 4 DUTs, the co-processor, 2 spare | the PH 8 lead has no spare wire; buffered captures: 384 KB ≈ 0.4 s over FS USB + ≈ 0.8 s over Wi-Fi (Zephyr ESP32-S3 TCP ≈ 4 Mbit/s).  The ESP32-S3 has 8 host channels for the whole drawer: one multiplexed bulk interface on the co-processor, not 4 CDC ports; to be checked on the bench |
| UI | the node owns the API (`POST /api/la/captures`, `GET …/{id}`, `GET …/{id}/data`, a WebSocket for state; captures kept in the 8 MB PSRAM); the node's page gets "Wires", "Analyzer" and "Co-processor" cards: a canvas viewer and JS decoders (UART, I²C, SPI, then SWD), `.sr` and VCD export, per-bus roles, console tabs | ≈ 30 KB, served from flash, the rack's style, works on a phone; Surfer is 14.9 MB of WASM and has no decoders; no public WASM libsigrokdecode |
| bayctl | `bayctl capture <bay> --ch … --rate … --trigger … --decode …` saves `.sr` + JSON and decodes with sigrok-cli (raw input: `-I binary:numchannels=…:samplerate=…`), also the decoders' CI oracle against sigrok-dumps; consoles over RFC 2217 like the node's AUX | one annotation format `{ss, es, pd, cls, text}` for both |

Expected speeds pin → bus → pin (Elmore estimate, to be measured): CH446Q ±5 V, 100 Ω, LSF0108: rise
≈ 60 ns, SPI/SWD ≈ 5 MHz, I²C 400 kHz with a 2.2 k bus pull-up (1 MHz no), UART 3 Mbd.  A 1.8 V ↔ 3.3 V
wire relies on the LSF's pull-ups for the top of the edge: ≈ 1–2 MHz.

## The co-processor's firmware: stock or ours

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
and analyzer work without firmware of our own), then our Zephyr firmware in steps: consoles and pull-ups,
the SUMP analyzer, emulation.

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

## Open, for the user

1. Order v1 now for B3 (recommended: yes)?
2. The co-processor: our Zephyr firmware, or the stock analyzer only (recommended: stock on day one, ours
   in steps, consoles first)?
3. Which bays get the full variant (recommended: B3 full, the bays that only need power and reset base)?
4. DUT side: Dupont jumpers pin by pin (recommended to start), or a small adapter board per DUT model on a
   2 × 6 ribbon?
