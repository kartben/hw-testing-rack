# DATA ×4 v2: virtual wires and a logic analyzer (research)

**Status (2026-10-19): research only, nothing designed.**  The user asked for real electrical links
between the four boards of a converted bay, switched from the web UI, and for a built-in logic analyzer
with a web UI, sized "to the maximum we can handle".  No co-processor of our own, no external debugger.
The illustrated version (UI mock, to-scale placement, tables) is the page
[Fils virtuels et analyseur](https://claude.ai/artifact/DeudMxKuwkSjVR6naQZj55) (French, private to the
owner).  v1 ([electronics.md](electronics.md), "DATA ×4 v1.0") is the base: v2 only adds to it.

## Proposal

| Block | Choice | Why |
|---|---|---|
| Pins | 8 per port, 32 in all, on a 2 × 6 2.54 header per port (GND, VREF, P1–P8, RESET, BOOT), Dupont jumpers to the board's pins | the header sets the limit: 2 × 6 is 15.2 mm at the ports' 18 mm pitch, 2 × 8 (20.3 mm) does not fit |
| Matrix | 2 × WCH CH446Q (16 X × 8 Y analog crosspoint, C109471, $1.59, Economic): each chip takes two ports' 16 pins on X, the 8 Y lines of both chips joined are the 8 buses | MAX14661 is 16 × 2 (8 chips, $45, 4 I²C addresses only, the reel Standard-only); ADG2128 $29 needs 8–12 V; MT8816 out of stock |
| Matrix supply | ±5 V: TPS60400 (C9839) makes −5 V | halves the CH446Q's R_on (120 Ω typ. at +5 V); this is what makes I²C at 400 kHz work |
| Levels | 1 × LSF0108 per port (VQFN-20 2.5 × 4.5, C130008): A side = the DUT's VREF, B side = the 3.3 V matrix, Vref_B biased from PORTn_VBUS through 200 k (a switched-off port isolates its pins), 10 k B-side pull-ups | passive FET: I²C, push-pull and the SWDIO turnaround pass without direction control.  **Not TXS010x**: their one-shots retrigger and oscillate behind series R and a switch, and their pull-ups add up on a shared bus |
| Protection | 100 Ω in series (not 330 Ω) and TPD4E05U06 (C138714) at the header, on every pin | 330 Ω + R_on breaks I²C's V_OL (≈ 1 V with 2.2 k); 100 Ω still bounds two outputs fighting to ≈ 10 mA (15 mA per switch) |
| Interlock | VREF measured by an ADS1015 (C193969, 0x48), not just declared; RST of the CH446Qs pulled so the matrix is all-open until the node configures it; no wire to a port without VREF | DUTs up to 3.6 V |
| Bus pull-ups | 2.2 k per bus to 3V3, switched by a second TCA9534A (0x39): a pin driven high = pull-up on, input = off | I²C at 400 kHz on any bus without spending pins (the alternative, 6 pins per port with 8 spare X inputs as service lines, was dropped) |
| Matrix control | TCA9534A (C206010, 0x38): DAT, CK, RST shared, one STB per chip, plus the RP2350's RUN and QSPI_SS (BOOTSEL) and a mark line for the analyzer | the two TCA6408A have no spare line and only two addresses; a crosspoint is ≈ 17 I²C writes (≈ 1 ms at 400 kHz), no readback: the node keeps a shadow table and opens before closing |
| Analyzer | RP2350A (C42411118, A4 stepping) wired exactly like a Pico 2 (12 MHz, QSPI flash, CH1–21 = GPIO2–22, CH22–24 = GPIO26–28, GPIO0→1 link, LED GPIO25), running the **stock** gusmanb LogicAnalyzer `PICO_2` UF2 | 24 channels, 100 MS/s, 384 KB buffer, edge/pattern/burst triggers; the same hardware runs μLA or sigrok-pico if gusmanb stalls |
| Taps | the 8 buses on CH1–8, the 4 RESET lines on CH9–12, the node's mark on CH13 | gusmanb picks the sample width from the highest channel used: CH1–8 = 8 bit = 393,216 samples; no maintained firmware goes past 24 channels with hardware triggers; any unwired pin is watched by putting it alone on a free bus |
| Data path | USB2517I (7 ports, QFN-64 9 × 9, C478081, $4.51) instead of the USB2514B: 4 DUTs + the analyzer + 2 spare | the PH 8 lead has no spare wire, I²C would take 40 s per capture; buffered captures: 384 KB ≈ 0.4 s over FS USB + ≈ 0.8 s over Wi-Fi (Zephyr ESP32-S3 TCP ≈ 4 Mbit/s) |
| UI | the node owns the API (`POST /api/la/captures`, `GET …/{id}`, `GET …/{id}/data`, a WebSocket for state; captures kept in the 8 MB PSRAM); the node's page gets "Wires" and "Analyzer" cards: a canvas viewer and JS decoders (UART, I²C, SPI, then SWD), `.sr` and VCD export | ≈ 30 KB, served from flash, the rack's style, works on a phone; Surfer is 14.9 MB of WASM and has no decoders; no public WASM libsigrokdecode |
| bayctl | `bayctl capture <bay> --ch … --rate … --trigger … --decode …` saves `.sr` + JSON and decodes with sigrok-cli (raw input: `-I binary:numchannels=…:samplerate=…`), also the decoders' CI oracle against sigrok-dumps | one annotation format `{ss, es, pd, cls, text}` for both |

Expected speeds pin → bus → pin (Elmore estimate, to be measured): CH446Q ±5 V, 100 Ω, LSF0108: rise
≈ 60 ns, SPI/SWD ≈ 5 MHz, I²C 400 kHz (1 MHz no), UART 3 Mbd.  A 1.8 V ↔ 3.3 V wire relies on the LSF's
pull-ups for the top of the edge: ≈ 1–2 MHz.

## Firmware to keep

* RP2350A: none.  Command 4 reboots it to BOOTSEL; the node (or `picotool` over USB/IP) loads a new UF2;
  RUN and QSPI_SS on the TCA9534A recover a bricked chip.
* Node: the matrix driver (≈ 200 lines), an analyzer client next to the USB/IP service (gusmanb's framed
  protocol, `55 AA … AA 55` with `F0` escaping, ≈ 300 lines, written from scratch: their C# is GPL), the
  HTTP endpoints and the two cards (≈ 1,000 lines of JS; lassebm/web-logic-analyzer's MIT decoders can be
  borrowed, sigrok's GPL decoders must not be translated into the page).
* Risk: gusmanb has one maintainer and moves slowly; its protocol is small and stable.

## Mechanics and board

* **108 × 27 mm** (+3 mm, the most the rear bay takes): SolidCraft gives 1.0 mm to the rear wall; under
  the board 5.3 mm to the floor (an LQFP-44 is 1.6 mm, header pins ≈ 3 mm); the bosses need Ø 8 mm keep-outs.
* Concept placement (courtyards, checked for overlaps per side, not routed): top keeps all of v1 plus the
  headers, LSF0108s, ESD and arrays (52 % of the board); bottom takes the two CH446Q, the charge pump,
  the ADS1015, both TCA9534A and the analyzer (21 %).  The four holes move, so do the drawer's bosses
  (`DATA_X4_HOLES`, tray session).  Single-sided would need ≈ 108 × 35 mm, which does not fit.
* Double-sided assembly means JLC **Standard** PCBA (setup $50 instead of $8, stencil ≈ $16 instead of
  $1.50).
* Fabio's rule "no tracks on inner layers" leaves two routing layers for 32 pins, 8 buses and the
  analyzer's USB: the main design risk.  Each CH446Q under its two ports, a straight via from the
  translator above, buses on the bottom; fallback 6 layers (signal/GND/signal/signal/power/signal).
* The Dupont jumpers leave the rear headers upwards and over the port wall: the headroom above the rear
  bay is to be checked with the tray session.

## Cost

Added parts per board ≈ $20 (hub +$2.7, analyzer $3.1, matrix + −5 V $4.0, 4 × LSF0108 $4.5, ESD and
arrays $0.8, 2 × TCA9534A $2.7, ADS1015 $1.9, headers and passives $0.5): components ≈ $15 → ≈ $35 per
board.  Prototype order (5 PCBs, 2 assembled): v1 $76.74 Economic; v2 ≈ $210 Standard (setup +$42,
stencil +$14, ≈ 12 new extended parts ≈ +$36, components +$40), to be confirmed by a JLC quote.

## Order v1 now for B3

Recommended: v1 validates everything v2 keeps (hub behind the FS host, per-port power and measurement,
EN/FAULT/RESET/BOOT, USB/IP of 4 DUTs, the rear-bay mechanics, the PH 8 lead); v2 still needs a design
session, the bosses moved and a dearer Standard order.

## Open, for the user

1. Order v1 now for B3 (recommended: yes)?
2. v2 budget ≈ $210 for two prototypes, ≈ $35 of parts per board: the full version, or the reduced one
   (4 pins × 8 buses, one CH446Q at +5 V, no translators so only same-VREF ports joined, ≈ +$11 per
   board, maybe single-sided Economic; SPI ≈ 3 MHz, I²C 100 kHz)?
3. DUT side: Dupont jumpers pin by pin (recommended to start), or a small adapter board per DUT model on a
   2 × 6 ribbon?
