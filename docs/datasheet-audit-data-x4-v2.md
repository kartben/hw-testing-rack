# Datasheet conformance audit: DATA ×4 v2

2026-10-24, before the JLC order (the cart waits on it).  The user's question: "pour les circuits intégrés clés …
a-t-on tout intégré en respectant les schémas de référence des datasheets ?"  This file covers the DATA ×4 v2
(electronics/data-port-x4-v2): the logic assembly (DATA-4x-logic, as drawn) and, where it differs, the base one
(DATA-4x).  docs/datasheet-audit.md covers the node, the hub box, the camera pod and the DATA port.

**Method.**
- Each key IC's typical application, design guide or reference board was compared with ours, point by point.
  The checks cover external parts and values, straps and unused pins, decoupling, stability, crystal load,
  series resistors, the limits we approach, and the layout rules that can be judged from design.py's
  placement.
- Our side is design.py (the schematic as generated) and the fab BOM.
- Datasheets and guides come from the makers, or from LCSC mirrors for the Chinese parts; each section lists them.
- Each "to fix" rests on a quote that was re-read in the source itself.
- Nothing on the board was changed; this file proposes.
- The user, 2026-10-24: "S'il y a le moindre doute laisse moi, humain, vérifier manuellement les datasheets pour
  te donner une réponse définitive".  So any point that is ambiguous, read from a figure only, taken from an
  unofficial or uncertain source, or resting on an inference is marked **to check by the user**, not decided
  here.  The questions are listed below.

**Verdicts.**
- **OK**: as the datasheet asks.
- **justified deviation**: we differ, for a reason that holds.
- **to fix**: a datasheet requirement is not met; the quote is given.
- **check**: a bench measurement settles it.
- **to check by the user (Un)**: a human reads the datasheet and answers question Un below.

## Summary

The schematic follows the datasheets almost everywhere:
- every symbol's pin map was checked;
- straps, addresses, current limits, crystal loads, the LSF0108 bias and the TPS60400's capacitors are all
  right;
- of about 240 rows, 176 are OK and 18 are justified deviations, each with its reason;
- the rest wait on bench measurements or on the user's reading.

**Nine items to fix.**
- Five are on the RP2354B and its core regulator, the worst: L1's footprint carries no polarity mark, and the
  regulator's placement departs from Raspberry Pi's layout.
- One is on the USB2517I: a silicon erratum asks for a reset supervisor.
- One adds ESD to each header's VREF pin.
- Two are wording, docs and firmware only.

**Ten questions for the user (U1–U10)**, and two more since (U11–U12, the hub's straps, 2026-10-25).  The weightiest:
- **U1, L1's orientation.**  Our design.py puts L1's dot on the VREG_LX pad.  Raspberry Pi's figures, as read
  here, put it on +1V1.
- **U4, the CH446Q.**  Its only manual is a Chinese one from an LCSC mirror; the ±5 V supply and the logic
  levels rest on that reading.
- **U5, the H5VU25UC pinout.**  The datasheet is a Chinese maker's, from LCSC; a wrong pinout would short lines.

**Cost.**
- No to-fix item adds a new part type, except the supervisor.
- C47 costs ≈ $0.014 a board.
- The VREF ESD costs ≈ $0.12 a board.
- The supervisor costs $3.07 an order plus ≈ $0.05 a board; a fee-free partial alternative is given.
- Depending on the answers: U2 adds ≈ $0.002 a board; U7 could cost $3.07 an order; U8 and U9 cost nothing
  (resistors already in the BOM).

**Sourcing.**
- JLC's live stock on 2026-10-24: the approved inductor AOTA-B201610S3R3-101-T is back (202 pieces).
- No in-stock 2016 alternative meets Raspberry Pi's requirement: none carries the mandatory polarity mark.
- The RP2354B (C39843328) shows 0 at JLC.

## To fix

| # | What | Why (source) | Change | BOM and cost | Variant |
|---|---|---|---|---|---|
| 1 | **L1's footprint has no polarity mark** (and its pin-1 pad depends on U1) | The inductor "must be marked for polarity … and placed on the layout as indicated in Figure 26"; the orientation matters, "especially at higher output currents and for higher load transients" (RP2350 DS §6.3.8.2–3, p.412–413). L_Murata_DFE201610P has no mark, so JLC's placement is undetermined | A footprint with a pin-1 dot, pin 1 on the pad U1's answer names (Raspberry Pi's AOTA land: 0.7 × 1.7 mm pads at ±0.7 mm); correct the notes in design.py and catalog.py; check JLC's placement preview | none | logic |
| 2 | **Core-regulator placement is not Raspberry Pi's layout** | "Designers should follow … Figure 26 as closely as possible"; keep the switching loops small (DS §6.3.8, §6.3.8.1, p.409–412). Ours is one row 2.5 mm out with L1 turned 90°. CIN (C32) sits beyond the LX pin from VIN, so its loop needs vias. PGND goes to the exposed pad, not to CIN/COUT's GND | Copy the Minimal R4 block, turned 180° with U11 (coordinates in the RP2354B section). Draw its copper in design.py: PGND to the CIN/COUT GND with 2 adjacent vias, CFILT on its own GND via, VREG_FB taken from COUT away from LX | none | logic |
| 3 | **No copper cut-out under LX / L1** | "cut away any extra copper underneath the inductor"; on 4+ layers "cut away any copper immediately underneath LX/VREG_LX" (DS §6.3.8.1 and Fig. 27, p.411–412) | Pour keep-outs on F.Cu under L1 and on In1 (and In2) under the LX pad and trace | none | logic |
| 4 | **DVDD pin 32 has 100 nF where 4.7 µF is asked** | "The DVDD pin furthest from the regulator should be decoupled with a 4.7 µF capacitor close to the pin" (DS §6.1.3 p.400; again §6.3.8.1) | C47 100 nF → 4.7 µF | C23733 (basic, already a line); +$0.014/board | logic |
| 5 | **GPIO45 (−5 V sense) can go below −0.5 V** | VPIN min −0.5 V (DS Table 1680 p.1335). With −5 V up and +3V3_CP below 1.6 V (start-up after the TPS60400, −5 V lingering at power-down), the 47k/100k divider takes the pin to −1.6 V. The timing is inferred; the fix holds whatever it is | R40 47k → 10k: the pin stays ≥ −0.48 V even with +3V3_CP at 0 (nominal 2.55 V, ≈ 9 mV of the −5 V rail per LSB); update the formula in design.py's note and the firmware | C25744 (basic, already a line); ±$0 | logic |
| 6 | **The hub's reset: the RC doesn't cover a brown-out** | Errata DS80000628A Module 2: "The internal POR does not generate reset when power drops below the threshold. For a supply that has non-monotonous ramp reset may be lost … Device might not enumerate. Solution: Use external power on reset circuit (for example … MAX809S (V2.9V) voltage supervisor)". R2/C6 reset a clean ramp only. A DUT_5V sag (the node's 1.34 A limit) can leave the hub hung | MAX809S (2.93 V, 140 ms, push-pull) driving RESET_N in place of R2/C6. **Fee-free partial alternative:** keep the RC, add a 1N4148WS (C2128, basic) from RESET_N to +3V3 for a fast discharge, and have the node cycle DUT_5V when the hub doesn't enumerate | +1 extended type: C347371 (MAX809S, 216k in stock) $0.05/board + **$3.07 per order** | both |
| 7 | **The headers' VREF pins have no ESD** | Vref_A biases all eight pass gates and is rated ±2 kV HBM / ±1 kV CDM only (LSF0108 SDLS966M §6.2 p.5). P1–P8 on the same hand-wired header get IEC 61000-4-2 ±8 kV H5VU25UC. A design judgment, not a datasheet requirement | One more H5VU25UC per port, VREF through one line in flow-through.  Its spare lines could take RESET_N/BOOT_N too (then it is fitted on the base as well) | +4 × C20615800 (already a line, no new type), ≈ $0.12/board + 4 placements | logic (or both) |
| 8 | **The docs claim an unwired VREF isolates its group** | TI guarantees the off state only with EN low (SDLS966M §8.3.2 p.11), and 0.65 V is only the minimum Vref_A for specified translation. So "the group passes nothing" (design.py, electronics.md) is not backed. What happens at ≈ 0.4 V is a bench check | Correct the wording.  The firmware keeps a port's crosspoint switches open while its VREF reads under 0.65 V (GPIO40–43 < 0.33 V).  "DUT off" and "board off" do hold (SLVA675B §5.6; EN low with +5V_MX off) | none | logic |
| 9 | **Stale doc lines** | (a) +5V_MX carries ≈ 1–4 mA, not "≈ 70 mA": two CH446Q, the pump's IQ, the LSF bias, R38/R39. (b) FB1 does little at the pump's 50–250 kHz (≈ 1 µH): the "250 kHz apart" comment overstates it. (c) U3's "60–70 °C/W" is not a Diodes figure | Correct design.py, catalog.py and electronics.md | none | both |

Optional, no new part type and no fee:
- hub C7/C8 1 µF → 4.7 µF (C23733): VDD18 / VDD18PLL meet "1.0 µF ±20 %" with no margin once DC bias and
  temperature are counted (see U10);
- a 4.7 µF local bulk on +3V3 beside U1 (the EVB has 4.7 µF + 10 µF);
- 10k to +3V3 on the D± of the hub's unused ports 6/7, to hide them from the host (cosmetic).

## To check by the user

Each answer is yes / no or a value.  "Now" is what the board has; the last column says what each answer
changes.

| # | Datasheet (maker URL, revision) | Where | Question | Now | If yes / if no |
|---|---|---|---|---|---|
| U1 | RP2350 datasheet, https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf, build 2026-10-01 (80d627281ed5). Also Abracon's AOTA-B201610S3R3-101-T datasheet Rev A (2024-09-13), via https://www.lcsc.com/datasheet/lcsc_datasheet_2412101620_Abracon-LLC-AOTA-B201610S3R3-101-T_C42411119.pdf | §6.3.8 Fig. 26 (p.411), §6.3.8.2 (p.412), Fig. 28 (p.413); Abracon p.4 (marking) | In Fig. 26, is the inductor's orientation dot on the pad joined to COUT / VOUT (+1V1), and not on the pad joined to VREG_LX? Fig. 28 draws the dot at the "−" end of the current arrow; Abracon's p.4 labels the dotted end "+", the opposite | L1 pin 1 = CP_VREG_LX; design.py and catalog.py say "dot towards VREG_LX"; the footprint has no mark | **Yes:** L1 pin 1 = +1V1 and the notes swap. **No:** the pins stay. Either way, the marked footprint of fix 1 **Answered 2026-10-25 by the user:** in Fig. 26 the dot is on the pad joined to VOUT / COUT (+1V1), not VREG_LX.  So L1 pin 1 (the dot) = +1V1: the notes swap, and fix 1's marked footprint puts its dot there. |
| U2 | Microchip USB2517/USB2517I, https://ww1.microchip.com/downloads/en/DeviceDoc/00001598C.pdf (it opens in a browser; Microchip refuses scripted downloads), DS00001598C | §9.1, Fig. 9-1 "Typical crystal circuit" (p.52) | Is the 1 Meg across XTAL1–XTAL2 in Fig. 9-1 an external part? Unlike the USB251xB's, this datasheet never says one is inside | None.  Microchip's EVB-USB2517 fits one (R19 1Meg) | **Yes:** add 1 MΩ 0402 across XI–XO beside Y1, C26083 (basic), $0.002/board, both variants. **No:** optional (harmless in parallel) |
| U3 | Same datasheet DS00001598C | Table 5-1, the USBDNx_DP/PRT_DIS_Px and USBDNx_DM/PRT_DIS_Mx rows (p.10) | Is a downstream port disabled when only **one** of its D+ / D− lines is high at RESET_N's release? (The USB251xB datasheet asks for both) | Ports 1–4 are off at the hub's reset, but a self-powered DUT pulls D+ (FS) or D− (LS) up through 1.5k by itself | **Yes:** a self-powered DUT present at the hub's reset disables its port. The node must reset the hub before enabling such DUTs, or the docs warn. **No:** nothing to do **Answered 2026-10-25 by the user: yes**, one line is enough (with the straps on, CFG_SEL 000 or 010). Port 5 gets the schematic review's S2; for ports 1–4, a self-powered DUT present at the hub's reset loses its port until the next one. |
| U4 | WCH CH446 manual, https://www.wch-ic.com/downloads/CH446DS1_PDF.html (read here: version 1C, Chinese, LCSC mirror of 2017-05-15) | §4.1 pin table (p.2), §5 (p.3), §6.2–6.3 (p.6) | (a) Is VDD = +5 V with VEE = −5 V an allowed supply? (b) At VDD − GND = 5 V, is VIH ≤ 2.0 V (3.3 V logic a valid high)? (c) In serial mode (P/S low), must AX0–3 / AY0–2 be tied to GND? (d) Does RST high hold every switch open? (e) Is there any R_on figure for a 10 V span (VDD − VEE)? | (a) +5V_MX / −5 V; (b) DAT/CK/STB from a 3.3 V TCA9534A; (c) all on GND; (d) R20 pulls RST high until the node writes; (e) none assumed | (a) **No:** the supplies change (a single 5 V gives R_on 120–225 Ω). (b) **No:** level-shift DAT/CK/STB. (c, d) **No:** straps or firmware change. (e) The value decides whether a 1.8 V board's I²C low passes (≲ 120 Ω needed) **Partly answered 2026-10-25 by the user** (English datasheet §6.1–6.3, pp. 7–8): (a) **yes**: recommended VDD 4–13.2 V, VEE −8.8–0 V, VDD − VEE < 13.2 V, so ±5 V (10 V) is allowed; (b) **yes**: VIH ≥ 2.0 V, VIL ≤ 0.8 V at VDD − GND = 5 V, so the TCA9534A's 3.3 V drives it; (e) **no 10 V figure**, only RON12 45/65 Ω (25 °C), 55/80 Ω (85 °C) and RON5 120/185, 150/225 Ω: it stays a bench measurement. Also: 15 mA continuous per switch, 100 mA for all. (c) **yes** (§4.1 p. 3: AX0–3 / AY0–2 "unused pins in serial address mode, GND must be directly connected"; ours are on GND); (d) **yes** (§5: "when RST inputs high level, ACT signal will be ignored and all latches will always be reset to 0", every switch off; R20 holds RST high until the node writes). NC 9, 22, 23, 32, 44 "do not connect": ours are open. Only (e) is left, a bench measurement. |
| U5 | hongjiacheng H5VU25UC, Rev 2.0; no maker URL found, only https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/2401261524_hongjiacheng-H5VU25UC_C20615800.pdf | Function diagram (p.1), recommended land pattern (p.3) | (a) Are pins 1, 2, 4, 5 the I/O lines and pins 3 and 8 GND? (b) Are pins 6, 7, 9, 10 unconnected inside, or tied to 5, 4, 2, 1? | (a) I/O on 1, 2, 4, 5; GND on 3 and 8, one bar. (b) Each line runs through both pads of its pair, on one net | **Answered 2026-10-25 by the user** (the p. 1 function diagram): (a) I/O on 1, 2, 4, 5; GND on 8 (the TVS anode and the lower diodes' anodes); pin 3 has no internal connection, so our GND on it (and the land pattern's 3/8 bar) is harmless; the footprint and symbol stand. (b) 6, 7, 9, 10 are unconnected inside: flow-through works because our copper joins each pad pair; only the "tied inside" wording goes |
| U6 | TI LSF0108, https://www.ti.com/lit/ds/symlink/lsf0108.pdf, SDLS966M (May 2023) | §9.2, Table 9-2 and its note (p.14) | May Vref_A (the DUT's VREF) exceed the B side's pull-up voltage (3.3 V), e.g. VREF 3.4–3.6 V, given the note "Vref_A is required to be the lowest voltage level across all inputs and outputs"? | The VREF rule allows 0.95–3.6 V; the bus pull-ups are at 3.3 V | **No:** the VREF rule stops at 3.3 V (docs, and the firmware's warning). **Yes:** nothing |
| U7 | Raspberry Pi "Hardware design with RP2350", https://datasheets.raspberrypi.com/rp2350/hardware-design-with-rp2350.pdf, Release 3; RP2350 datasheet (as U1) | Hardware design §5.1 (p.15); datasheet Table 1678 (p.1334) | Do Raspberry Pi give a tolerance or range for the "27 Ω series termination resistors"? Would 22 Ω 1 % do for Full Speed? | R23/R24 22 Ω (basic); no basic 27 Ω exists | **27 Ω strict:** 27 Ω 0402 (extended, +$3.07 an order). **22 Ω allowed:** nothing |
| U8 | RP2350 datasheet (as U1) | Table 1680 (p.1335), VPIN −0.5 … IOVDD + 0.5 V; §12.4 (ADC) | Does the datasheet allow any injection current into a GPIO / ADC pin while IOVDD = 0? If so, how much? | Board off and a self-powered DUT's VREF wired: GPIO40–43 get VREF / 2 through 5 kΩ, ≤ 0.26 mA each | **No allowance:** 100k in series with each ADC input (4 × C25741, basic, already a line; fine for DC per §12.4.3), or a note to keep the board powered while DUTs are. **Allowed and ≥ 0.3 mA:** nothing |
| U9 | TI TCA6408A, https://www.ti.com/lit/ds/symlink/tca6408a.pdf, SCPS192E (Jan 2023) | Table 5-1, RESET row (p.4); §8.3.4 (p.20–21) | May RESET be tied directly to VCCI, or is the pull-up resistor required ("connect to VCCI through a pull-up resistor, if no active connection is used")? | Tied directly to +3V3 on U2 and U6 | **Resistor required:** 10k per expander (C25744, basic, already a line, $0). **Direct allowed:** nothing |
| U10 | Samsung Electro-Mechanics CL05A105KA5NQNC (C52923): its product page or MLCC simulator on product.samsungsem.com (search the part number; the direct link didn't answer on 2026-10-24); TPS60400, https://www.ti.com/lit/ds/symlink/tps60400.pdf, SLVS324C, §7.3 (p.4) | The part's DC-bias characteristic | What is its capacitance at 5 V DC and at 1.8 V DC? | TPS60400 C26–C28 at ≈ 5 V; hub VDD18 / VDD18PLL C7, C8 at 1.8 V | **Under ≈ 0.5 µF at 5 V:** C28 (−5 V out) to a larger part. **Under ≈ 0.8 µF at 1.8 V:** C7/C8 to 4.7 µF (C23733, basic, already a line) |
| U11 | Microchip USB2517/USB2517I, https://ww1.microchip.com/downloads/en/DeviceDoc/00001598C.pdf (it opens in a browser), DS00001598C | Table 5-2, "SMBus or EEPROM interface behavior" (p.15–16) | Which CFG_SEL[2:0] value gives "Internal Default Configuration, Strap Options are Disabled" with nothing else (no dynamic power switching, no ganged switching or sensing, no bus-power operation)? Our reading of the table: 110 | CFG_SEL 000 (pulled down): internal defaults, straps on | **110 (or another value):** that value is the way out in electronics.md › "Port-disable straps" (two strap resistors to +3V3). **None:** the straps stay on, and with them the self-powered DUT warning and D2 |
| U12 | Same datasheet | Table 5-1, PRT_DIS rows (p.10: "If the strap is enabled by package and configuration settings (see Table 5-2)"); Table 7-1 (p.19–20); §7.5 (p.41) | With the strap options disabled (U11's value): (a) are D+ / D− no longer sampled as PRT_DIS? (b) Are the internal defaults the values our straps set today (self-powered, NON_REM 00, individual port power switching and sensing, BOOST 00, PRT_SWP 0, no port disabled)? | Straps on: a self-powered DUT present at the hub's reset disables its port, and D2 keeps the co-processor's D+ low | **(a) and (b) yes:** U11's mode removes the self-powered DUT case and S2's reason for D2. **Either no:** stay on 000 |

## Sourcing

- **L1.** JLC's live stock on 2026-10-24: AOTA-B201610S3R3-101-T, 202 pieces, $0.36, extended. The local parts
  snapshot still said 3.  Mouser, Future and Farnell stock it too, for global sourcing or consignment.
  - Eleven in-stock 2016 parts of 3.3 µH were checked; none carries a polarity mark and none is approved by
    Raspberry Pi.  The table is in the RP2354B section.
  - The closest electrical fit, FTC201610S3R3MBCA (C5832345, 140 mΩ, 2.3 A, 1.0 mm), is "at your own risk" in
    Raspberry Pi's words (Hardware design with RP2350 §2.1): each board's winding direction is then a coin flip.
  - **Keep the AOTA and reserve it with the order.**
- **U11 RP2354B** (C39843328): 0 in stock at JLC on 2026-10-24.  Settle U11's supply route before ordering.

## Base variant (DATA-4x)

The base leaves 91 parts off: the matrix and co-processor sheets, and each port's pin chain.  Nothing it keeps
depends on them.
- It shares fix 6, U2, U3, U9, U10 (the hub's capacitors) and the U3 LDO checks; its 3.3 V load is about the
  same (the hub dominates).
- Hub port 5 ends on R23/R24's empty pads: ≈ 43 mm open D± stubs.  That is harmless: nothing attaches, and the
  port stays enabled and empty.
- The headers' P pins and VREF end on empty pads; VREF's divider and LSF are off, so the pin floats, unused.

## Main checks at bring-up

Each section lists its own; the ones that matter most:
1. **U3 AP2114H thermal.**
   - It dissipates 0.60–0.76 W.  Diodes gives 128 °C/W bare and asks for ≥ 30 % thermal margin.
   - Measure the tab temperature in the closed drawer, with four High-Speed ports streaming and the RP2354B
     capturing.  Pass: θJA ≤ ≈ 100 °C/W.
   - If it fails: more copper, or 1 Ω in series with VIN.
2. **RP2354B DVDD.**  1.1 V ±3 %, transients within ±100 mV under load.  Check L1's dot before power-up.
3. **Hub.**
   - Twenty cold and warm starts, all enumerating.
   - DUT_5V cycled at 10–500 ms and dragged to ≈ 3 V and back: the hub must re-enumerate every time (erratum
     Module 2).
   - XTAL2 amplitude (drive level).
4. **CH446Q R_on at ±5 V** (no figure for a 10 V span, U4e): it needs ≲ 120 Ω for a 1.8 V board's I²C low with
   the 2.2k on.  Also the −5 V rail and its ripple, and the crosspoints' VEE current.
5. **+5V_MX at no load ≤ 5.25 V** (TPS60400 VI max; 10 mV of margin at the node's 5.24 V).
6. **VBUS under 0.5 A ≥ 4.75 V.**  This needs +5V ≥ 4.87 V at the board.
7. **An empty port's VBUS decays with τ ≈ 18 s** (INA226 830 kΩ, 22 µF): the node's "refuse EN while VBUS is
   there" rule must allow for it.
8. **The TCA9534A → CH446Q writes.**  DAT, CK↑ and STB each in their own I²C write; rewrite the switch map every
   few seconds (CH446 manual §7.1).
9. **Q1–Q3 (CJ 2N7002, Vth up to 2.5 V)** on SDA/SCL/INT: VOL ≤ 0.4 V and the fall times, both directions.
10. **An unwired VREF** (fix 8): with header n open, drive a bus low and high from the co-processor and watch
    the P pins.

## How to read the sections

Each section below is one group of ICs, with its own sources.  The source tags ([DS], [TPS], …) are scoped to
their section.  Coordinates are KiCad mm from design.py.

## RP2354B co-processor (U11, Y2, L1)

Sources:
- **[DS]** RP2350 Datasheet, Release 8 (build 2026-10-01, 80d627281ed5).
- **[HW]** Hardware design with RP2350, Release 3 (build 06a7f75e58a1, history entry 2026-08-24).
- **[MIN]** RP2350B Minimal KiCad design R4-S1 (RP-010329-CA, files of 2026-07-08): `.kicad_pcb` read as text for L1's footprint, pad nets and the regulator parts' coordinates.
- **[AOTA]** Abracon AOTA-B201610S3R3-101-T datasheet, Rev A, 2024-09-13.
- **[ABM8]** Abracon ABM8-272-T3 datasheet, Rev B, 2024-09-16.
- Live JLC part data: the `jlc` MCP component search, 2026-10-24 (the `jlcpcb-parts` local DB is an older snapshot).

Our coordinates are KiCad mm from design.py. U11 is at (47.0, 12.9), turned 180°. So VREG pins 61–65 sit on its south edge (y ≈ 17.8): AVDD 61 x 43.2 · PGND 62 x 43.6 · LX 63 x 44.0 · VIN 64 x 44.4 · FB 65 x 44.8 (pad positions from [MIN], with the same 180° turn).

### U11 RP2354B (QFN-80): supplies, decoupling, core regulator

| Reference element | Datasheet / guide | Ours | Verdict | Source |
|---|---|---|---|---|
| IOVDD, QSPI_IOVDD, USB_OTP_VDD, ADC_AVDD | IOVDD 1.62–3.63 V; QSPI_IOVDD on the RP2354 must be 3.3 V (in-package flash); USB_OTP_VDD 3.135–3.63 V; ADC_AVDD 1.62–3.63 V (≥ 2.97 V for full ADC performance) | All on +3V3_CP = AP2114H 3.3 V through FB2. FB2 is GZ2012D601TF, 0.3 Ω max (LCSC), ≈ 45 mA, so it drops ≈ 14 mV; the rail is ≈ 3.24–3.35 V | OK | [DS] Table 1688 + Note, §14.9.5 p.1340–1341 |
| VREG_VIN, VREG_AVDD supply | VREG_VIN 2.7–5.5 V, VREG_AVDD 3.135–3.63 V. "If VREG_VIN is limited to 3.135–3.63 V, a single combined supply can be used" (Fig. 22). VIN and AVDD "should be powered up together" | Combined on +3V3_CP (Fig. 22 topology), with AVDD through R21 33 Ω | OK | [DS] §6.3.7 Fig. 22 p.407–408; §6.1.8 p.401 |
| Ferrite FB2 + C31 4.7 µF before VREG_VIN | Not in RP's circuit: [MIN] feeds +3V3 from an NCP1117 with 10 µF out | 600 Ω bead (low-frequency L ≲ 1 µH) with ≈ 9.4 µF nominal: Z0 ≈ 0.3 Ω, far below the buck's \|Rin\| ≈ V²/P ≈ 70 Ω (≈ 0.15 W), so no input-filter instability. C32 still supplies the 3 MHz pulses | justified deviation | [DS] Table 1689 (fsw 3 MHz) p.1342; [HW] §2.2 p.7 |
| CIN (C32) value / type | "CIN should be at least 4.7 µF and have a maximum parasitic resistance of 50 mΩ". [MIN] C6 = GRM155R60J475ME47D, 4.7 µF 0402 6.3 V X5R ±20 % | C23733 CL05A475MP5NRNC, 4.7 µF 0402 10 V X5R ±20 % (basic). Same class; with the 10 V rating the DC-bias loss at 3.3 V is no worse than RP's 6.3 V part; ESR of a 0402 MLCC at 3 MHz ≪ 50 mΩ | OK | [DS] §6.3.8.2 p.412; [HW] §2.1 p.7; [MIN] C6 |
| COUT (C33) value / type | "COUT must be 4.7 µF ±20 % with a maximum parasitic resistance of 250 mΩ and a maximum inductance of 6 nH" | C23733 4.7 µF ±20 % 0402 (ESL ≈ 0.3–0.5 nH); at 1.1 V the DC-bias loss is small | OK | [DS] §6.3.8.2 p.412 |
| RFILT / CFILT (R21 / C34) | 33 Ω + 4.7 µF on VREG_AVDD ("draws around 200 µA") | 33 Ω C25105 + C23733 4.7 µF | OK | [HW] §2.1 p.7; [DS] Fig. 22 p.408 |
| L1 part | Must be shielded, 3.3 µH ±20 %, DCR ≤ 250 mΩ, Isat ≥ 1.5 A, polarity-marked; AOTA-B201610S3R3-101-T recommended | AOTA-B201610S3R3-101-T (C42411119). See the L1 table | OK (part) | [DS] §6.3.8.2 p.412 |
| **L1 orientation (polarity dot)** | Fig. 26 (Pico 2 layout) puts the orientation indicator on the inductor pad tied to V_OUT/COUT; VREG_LX goes to the other pad. Fig. 28: current enters at "+" and leaves at "−", the dot being at "−". [MIN]'s own footprint: pad 1 = **+1V1**, with the silk and fab dot at pad 1, and pad 2 = VREG_LX. "The inductor must be marked for polarity and placed on the layout as indicated in Figure 26" | design.py and catalog.py both say "**dot towards VREG_LX**". L1 pin 1 = CP_VREG_LX, and the footprint (L_Murata_DFE201610P) has no polarity mark, so nothing tells JLC where the dot goes | **to check by the user (U1)** for the pad; the missing footprint mark: **to fix** | [DS] §6.3.8 Fig. 26 p.411, §6.3.8.2 p.412, Fig. 28 p.413; [MIN] L1 footprint |
| **Regulator placement (CIN, COUT, L1)** | "Designers should follow the above schematic Figure 25 and layout Figure 26 as closely as possible"; "these guidelines must be strictly followed". [MIN]/Fig. 26: CIN straddles VIN/PGND 1.16 mm from the pin row, COUT right behind it (2.1 mm), L1 behind COUT (3.75 mm), its axis parallel to the chip edge, with the +1V1 pad on the FB side. "It is critical to keep the loop area … as small … as possible" | All in one row 2.5 mm out (y 20.3): R21 x 40.0, C34 41.2, **C32 (CIN) 42.4**, **L1 44.1 turned 270°** (axis perpendicular to the edge), **C33 (COUT) 45.8**. CIN lies west of LX (pin 63, x 44.0), while VIN (pin 64, x 44.4) is east of it. So the VIN→CIN→PGND loop cannot close on F.Cu without crossing LX: it goes through vias and planes. COUT's GND likewise sits east of LX, away from PGND. PGND is hand-routed inwards to the exposed pad (design.py l.822) rather than to the CIN/COUT GND | **to fix** | [DS] §6.3.8 p.409–411, §6.3.8.1 p.411–412; [HW] §2.1 p.6–7; [MIN] C6/C7/L1/R3/C9 |
| Copper under LX / L1 | "On the top layer … cut away any extra copper underneath the inductor"; "For a multi-layer board (4 or more layers) please cut away any copper immediately underneath LX/VREG_LX node" (Fig. 27, layer 2) | design.py `keepouts` holds only the edge, tab and split areas. The F.Cu GND pour, In1 GND and In2 +3V3 all run under L1 and LX | **to fix** | [DS] §6.3.8.1 p.411–412, Fig. 27 p.412 |
| GND vias / CFILT GND | High-current GND back to the QFN pad "at one single point (using 2 adjacent vias)"; "CFILT must also have a low impedance … path back to the QFN GND pad (don't share any GND vias with the CIN/COUT high current GND)"; "CIN needs its own separate GND via" | Freerouting decides; not visible in design.py | check | [DS] §6.3.8.1 p.411–412 |
| VREG_FB | "Should be fed from the output of COUT, avoiding routing directly underneath LX" | Net +1V1, routing not drawn | check | [DS] §6.3.8.1 p.412 |
| All regulator parts on one side | "Don't place any of CIN/LX/COUT on the opposite side" | All on F.Cu | OK | [DS] §6.3.8.1 p.411 |
| DVDD decoupling | "The two DVDD pins closest to the regulator should be decoupled with a 100 nF … The DVDD pin furthest from the regulator should be decoupled with a **4.7 µF** capacitor close to the pin". §6.3.8.1 also recommends a second 4.7 µF on V_OUT on the far edge ("DVDD pin 23 on the QFN-60", i.e. pin 32 on the QFN-80) | C45 / C46 / C47 = 100 nF on pins 51 / 10 / 32. Pin 32 is the farthest from pins 61–65. C45 (40.3, 18.3) sits ≈ 5.5 mm from pin 51 (42.1, 13.1) and C46 (54.0, 17.3) ≈ 4.7 mm from pin 10 (51.9, 13.1); [MIN] has ≈ 3.1 mm | **to fix** (C47 → 4.7 µF); check (C45/C46 distance) | [DS] §6.1.3 p.400; §6.3.8.1 p.412; [MIN] C8/C10/C11 (all 100 nF) |
| IOVDD / QSPI / USB_OTP / ADC_AVDD decoupling | 100 nF per power pin; RP shares 68/69 with one capacitor. USB_OTP_VDD and ADC_AVDD each "100 nF close to the pin" | C35–C44: 10 × 100 nF, with 68/69 and 59/60 shared (as [MIN] C12, C20), 1.8–4.4 mm from the pins | OK | [HW] §2.2.1 p.8–9; [DS] §6.1.4–6.1.5 p.400–401 |
| DVDD limits | 1.05–1.16 V; "short term transients should be within ±100 mV"; regulator ±3 % in normal mode | Default 1.1 V | check (bring-up) | [DS] Table 1688 note b p.1341; Table 1689 p.1341 |
| Supply sequencing | Any order except VREG_VIN/VREG_AVDD together | Single rail | OK | [DS] §6.1.8 p.401 |

Notes
- **Polarity conflict between the documents.** Abracon's own marking drawing ([AOTA] p.4) labels the dotted terminal "+" (current in). RP's Fig. 28 puts the dot at "−" (current out). The verified layouts settle it: Pico 2 (Fig. 26) and RP's Minimal R4 footprint both put the dot on the **+1V1 / V_OUT** pad, and the requirement is "placed on the layout as indicated in Figure 26". If so, our note is reversed: question U1 asks the user to confirm it from the figures.
- With L1 turned 90° from Fig. 26 and its loop closed through vias, even the "right" dot side is not the verified field geometry. RP's own words: "if you choose not to use our example, then you do so at your own risk" ([HW] §2.1 p.7).

### Y2 ABM8-272-T3 (12 MHz) with U11 XIN/XOUT

| Reference element | Datasheet / guide | Ours | Verdict | Source |
|---|---|---|---|---|
| Crystal | ABM8-272-T3 "highly recommend"; 12 MHz fundamental, ±30 ppm, ±30 ppm, ESR ≤ 50 Ω, C0 ≤ 3 pF, CL 10 pF, drive 10 µW typ, 200 µW max | ABM8-272-T3, C20625731 (4009 in stock, extended) | OK | [HW] §4 p.13, §4.1 p.14; [ABM8] p.2 |
| Load capacitors | 15 pF each: 7.5 pF + ≈ 3 pF stray = 10.5 pF | C48/C49 15 pF C0G 0402 (C1548). With Cstray 3–5 pF, CL = 10.5–12.5 pF, so the frequency sits ≈ −10…−40 ppm, far inside USB FS's ±2500 ppm | OK | [HW] §4 p.13 |
| Series R on XOUT | 1 kΩ, so a ≤ 50 Ω ESR crystal is not over-driven at IOVDD 3.3 V; "tuned for 3.3 V operation" | R22 1k (C11702), IOVDD 3.3 V | OK | [HW] §4 p.13, §4.1 p.14 |
| Pins | Pad 1 XIN, pad 3 via R to XOUT, pads 2/4 GND ([MIN] X1) | Y2 1 = CP_XIN, 3 = CP_XTAL (through R22), 2/4 = GND | OK | [MIN] X1/R2 |
| Layout | "Keep the layout as short as possible" | Y2 ≈ 6 mm from XIN/XOUT (pins 30/31 at (47.2/46.8, 8.0)), C48/C49 at its pads, R22 4.8 mm from XOUT ([MIN]: X1 ≈ 9 mm, R2 3.4 mm) | OK | [HW] §4 p.13 |

### L1 AOTA-B201610S3R3-101-T

| Reference element | Datasheet / guide | Ours | Verdict | Source |
|---|---|---|---|---|
| Inductance | 3.3 µH ±20 % | AOTA: 3.3 µH, M (±20 %) at 1 MHz / 1 V | OK | [DS] §6.3.8.2 p.412; [AOTA] p.1 |
| Isat | ≥ 1.5 A ("the higher the better"; regulator current limit up to 800 mA) | 2.8 A typ / 2.4 A (30 % drop); Irms 2.3 / 2.1 A | OK | [DS] §6.3.8.2–3 p.412–413, Table 1689 p.1341; [AOTA] p.1 |
| DCR | ≤ 250 mΩ | 115 typ / 140 max mΩ | OK | [AOTA] p.1 |
| Shielding | Fully shielded | Molded, "shielded construction" | OK | [AOTA] p.1 |
| Polarity mark | Required; parts aligned on the reel | White ink dot, "approved for use with Raspberry Pi's RP235x" | OK | [DS] §6.3.8.2 p.412; [AOTA] p.1, p.4 |
| Land pattern | Abracon: 1.0 × 1.6 mm pads, 1.0 mm gap. RP [MIN]: 0.7 × 1.7 mm at ±0.7 mm, silk dot by pad 1 (+1V1) | KiCad L_Murata_DFE201610P: 0.55 × 1.6 mm at ±0.725 mm (covers the 0.6 ±0.2 mm terminals), **no polarity mark** | to fix (the mark); the pad: U1 | [AOTA] p.4; [MIN] L1 |
| Availability | — | JLC live search 2026-10-24: **202 in stock**, $0.361, extended. The local `jlcpcb-parts` snapshot shows 3. Also stocked by Mouser/Future/Farnell (global sourcing or consignment) | check (order early) | `jlc` MCP C42411119 |

#### L1 sourcing: in-stock 2016 (0806) alternatives at JLC/LCSC

Raspberry Pi's requirement ([DS] §6.3.8.2 p.412): fully shielded, 3.3 µH ±20 %, DCR ≤ 250 mΩ, Isat ≥ 1.5 A, **"must be marked for polarity"**. [HW] §2.1 p.6–7 adds: "we could find no suitable ones in the 0806 (2016 metric) case size". Unmarked parts sit with their winding "randomly distributed along a reel".

Stock and price come from the live JLC search on 2026-10-24. All candidates are JLC *extended* (+$3.07 per order on Economic, the same as the AOTA). Isat/Irms/DCR are LCSC's figures unless a datasheet is cited.

| LCSC | MPN | Maker | L | Isat / Irms | DCR | L×W×H mm | Shielded | Polarity mark | Stock | $/pc | Verdict vs RP |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C5832345 | FTC201610S3R3MBCA | CJiang | 3.3 µH ±20 % | 2.3 / 1.7 A | 140 mΩ | 2.0×1.6×1.0 | molded, closed magnetic circuit | **none** (blank body in datasheet photos; ordering code has no marking option) | 1382 | 0.049 | meets L/Isat/DCR/shield/height; **fails polarity**; not approved |
| C49190102 | HCTC-201610-3R3-M | YOUCHI | 3.3 µH ±20 % | 2.3 / 1.7 A | 140 mΩ | 2.0×1.6×1.0 | molded | none known (no datasheet on LCSC) | 1920 | 0.039 | same as above; datasheet unverified |
| C45385191 | PSTMAA201610-3R3MB | PROD Tech | 3.3 µH ±20 % | 2.3 / 1.7 A | 170 mΩ | 2.0×1.6×1.0 | flat-wire molded | none found | 2752 | 0.044 | fails polarity; not approved |
| C49435043 | MHT201610SG-3R3M H | CND-tek | 3.3 µH ±20 % | 2.0 / 1.5 A | 145 mΩ | 2.0×1.6×1.0 | molded (per LCSC class) | none known (no datasheet) | 2596 | 0.040 | fails polarity; Isat margin smaller; datasheet unverified |
| C55109803 | PCT201610-3R3-M | jieerrui | 3.3 µH ±20 % | 2.1 / 1.6 A | 190 mΩ | 2.0×1.6×1.0 | molded | none known (no datasheet) | 3022 | 0.046 | fails polarity |
| C41405891 | YSMC201612H-3R3MB | YJYCOIN | 3.3 µH ±20 % | 2.3 / 2.0 A | 135 mΩ | 2.0×1.6×1.2 | molded | none (catalog.py already notes "unmarked polarity") | 2572 | 0.060 | fails polarity; 0.2 mm taller |
| C17701150 | MTQH201612S3R3MBT | MetalLions | 3.3 µH ±20 % | 2.7 typ, 2.3 rated / 2.4 typ, 2.0 rated A | 135 typ / 165 max mΩ | 2.0×1.6×1.2 | molded, "closed magnetic circuit" | none (ordering code: coating colour only) | 1659 | 0.045 | fails polarity; best Isat of the datasheet-verified ones |
| C18724415 | FTC201612S3R3MBCA | CJiang | 3.3 µH ±20 % | 2.7 / 2.4 A | 165 mΩ | 2.0×1.6×1.2 | molded | none | 3140 | 0.049 | fails polarity |
| C53281610 | FTC201612S3R3MBCD | CJiang | 3.3 µH ±20 % | 2.7 / 2.6 A | 130 mΩ | 2.0×1.6×1.2 | molded | none | 2020 | 0.047 | fails polarity |
| C48783272 | APS201610M3R3F | COILANK | 3.3 µH ±20 % | 3.2 / 1.9 A | 250 mΩ | 2.0×1.6×1.0 | unknown (no datasheet) | none known | 11119 | 0.031 | DCR at RP's limit, shielding unverified; reject |
| C2042572 | VLS201612HBX-3R3M-1 | TDK | 3.3 µH ±20 % | Isat 1.38 rated / 1.60 typ; Itemp 1.33 / 1.57 A | 174 typ / 209 max mΩ | 2.0×1.6×1.2 | wound metal, magnetic shield | none | 761 | 0.089 | **fails Isat ≥ 1.5 A** (rated 1.38 A) and polarity |

Verdict: **none of these is approved by Raspberry Pi**, and none carries a polarity mark. The AOTA-B201610S3R3-101-T is the only approved part ([DS] §6.3.8.3 p.413; [AOTA] p.1). Murata DFE201610E-3R3M and TDK TFM201610ALM-3R3 are not in JLC's library.

With JLC showing 202 AOTA in stock today, keep the AOTA and reserve it (JLC parts pre-order / private stock), or consign it from Mouser/Farnell.

If one must substitute, the closest electrical fit at 1.0 mm height is FTC201610S3R3MBCA (C5832345), but only "at your own risk" ([HW] §2.1 p.7): each board's winding direction is then a coin flip, to be screened at bring-up (DVDD under load, see Checks).

Also from the same search: **RP2354B C39843328 shows 0 in stock at JLC** (2026-10-24).

### U11 RP2354B: USB, RUN, BOOTSEL, SWD, LED, GPIO and ADC inputs

| Reference element | Datasheet / guide | Ours | Verdict | Source |
|---|---|---|---|---|
| USB series resistors | "These I/Os do require 27 Ω series termination resistors placed close to the chip"; Table 1678: "27 Ω series resistor required for USB operation" | R23/R24 **22 Ω** (C25092, basic). No basic 27 Ω exists: C25100 and others are extended, +$3.07 per order. ≈ 6 mm from pins 66/67 ([MIN] 3.9 mm). Link: a few cm, on board, to the USB2517I's DN5, Full Speed. The USB FS window 28–44 Ω cannot be checked: RP doesn't publish its driver impedance | **to check by the user (U7)** | [HW] §5.1 p.15; [DS] Table 1678 p.1334 |
| USB pull-ups / pull-downs | Built in, no external parts | None | OK | [HW] §5.1 p.15 |
| RUN | Digital In (FT), internal pull-up; "If RUN is not used, it should be tied high"; can be "driven from an external source" | R25 10k to +3V3_CP; TCA9534A P5 (on +3V3) open-drain emulation, input (high-Z) at reset, so the chip runs at power-up | OK | [DS] §7.3.3 p.452; Table 1677 p.1334 |
| BOOTSEL | QSPI_SS strap through 1 kΩ (R6) so the chip can over-drive it; keep it on RP2354; no external pull-up needed (R1 DNF) | R26 1k to CP_BOOT_N (TCA9534A P6, high-Z at reset); QSPI_SD0–3/SCLK unconnected (in-package flash) | OK | [HW] §3.1 p.10–11 |
| SWD | SWCLK/SWDIO FT with pull-ups; probe GND direct | TP1 SWCLK, TP2 SWDIO, TP3 GND on the top edge | OK | [DS] Table 1677 p.1334, Table 1687 note p.1339 |
| LED GPIO25 | 4 mA default drive; VOH ≥ 2.62 V | R27 1k + KT-0805G (Vf 2.6–3.1 V at 5 mA) ≈ 0.4–0.8 mA: dim but visible | OK | [DS] Table 1683 p.1336; LCSC C2297 |
| GPIO2–9 (buses A–H) | GPIO0–39 are FT: "tolerate voltages up to 5.5 V, provided IOVDD is powered to 3.3 V"; with IOVDD = 0 V, ≤ 3.63 V with little current | Buses: 10k to +3V3 (same supply as +3V3_CP), driven through LSF0108 B sides / CH446Q, ≤ 3.6 V in spec (≈ 4.0–4.2 V with an out-of-spec 5 V VREF, still ≤ 5.5 V). With the board off, the LSF EN and the CH446Q are unpowered, so the buses are isolated | OK | [DS] Table 1673 p.1331, Table 1680 p.1335, Table 1683 p.1336 |
| GPIO reset state vs bus pull-ups | GPIOs reset to pull-down, 36–113 kΩ at 3.3 V | 10k pull-up vs internal pull-down: idle bus ≥ 2.58 V (> VIH 2.0 V) if firmware keeps the pull-downs | check | [DS] Table 1674 p.1332, Table 1683 p.1337 |
| GPIO10–13/16–19 (2.2k enables) | Standard FT outputs | 2.2k from a driven-high GPIO onto a bus; with a 5 V VREF (outside the 0.95–3.6 V spec) ≈ 0.4 mA flows back into the GPIO | OK in spec | [DS] Table 1683 p.1336 |
| ADC pins type / range | GPIO40–47 are "Digital IO / Analogue" (standard, **not FT**): VPIN −0.5 … IOVDD + 0.5 V; ADC input 0 … ADC_AVDD; "voltage on the ADC inputs must not exceed IOVDD" | — | — | [DS] Table 1673 p.1331, Table 1680 p.1335, Table 1685 p.1338, §6.1.5 p.401 |
| GPIO40–43 = VREF n / 2 | ≤ IOVDD | 10k/10k from VREF ≤ 3.6 V gives ≤ 1.8 V; 5 kΩ source | OK powered | [DS] §12.4 p.965–966 |
| GPIO40–43, board off | IOVDD = 0 means VPIN ≤ 0.5 V | Self-powered DUT with this board unpowered (DUT_5V off): 1.8 V behind 10k, so ≤ 0.26 mA per pin (≤ 1 mA for four) flows through the ESD diodes into +3V3_CP. RP specifies no injection current | **to check by the user (U8)** | [DS] Table 1680 p.1335 |
| GPIO44 = +5V_MX × 47/147 | ≤ IOVDD | ≤ 1.68 V at 5.24 V; 32 kΩ source. +5V_MX is up before the AP2114H output, so during start-up the pin is > IOVDD + 0.5 with ≤ 40 µA injected (transient) | OK (transient check) | [DS] Table 1680 p.1335 |
| **GPIO45 = −5 V sense** | VPIN ≥ −0.5 V | 47k to +3V3_CP, 100k to −5V: nominally 0.65 V. **If +3V3_CP < 1.6 V while −5 V is present, the pin goes below −0.5 V** (−1.6 V open circuit with +3V3_CP = 0; clamped by the ESD diode, ≈ 35 µA). This happens while the AP2114H starts after the TPS60400, and at power-down, where −5 V on C28 (light load) can outlive +3V3 | **to fix** (free) | [DS] Table 1680 p.1335 |
| −5 V absent, +3V3_CP present | ≤ ADC_AVDD | 3.3 × 100/147 = 2.24 V | OK | [DS] Table 1685 p.1338 |
| ADC source impedance | "The ADC input is capacitive … about 1 pF … effective impedance, even when sampling at 500 kS/s, is over 100 kΩ. DC measurements have no need to buffer" | 5 kΩ (VREF), 32 kΩ (±5 V); no pin capacitor | OK for DC / slow sampling; check round-robin at full rate | [DS] §12.4.3 p.967 |
| ADC reference | Input range 0 … ADC_AVDD | ADC_AVDD = +3V3_CP (AP2114H ±1.5–2 % less FB2's drop). The −5 V reading is partly ratiometric; VREF and +5V_MX readings carry the rail's error | check (calibrate) | [DS] Table 1685 p.1338 |


## USB hub (U1 USB2517I, Y1, USBLC6-2SC6)

Scope: design.py `hub_sheet()` (U1, Y1, the straps, RESET, RBIAS, decoupling) and the USBLC6 in `port()`.
U3 (the LDO), J1 and the lead are in other sections. Here they are only touched where the hub depends on them.

Sources:
- **DS**: Microchip USB2517/USB2517I datasheet, DS00001598C (2013–2018), LCSC mirror of C478081. Rev C is the current revision on microchip.com's product page (checked 2026-10-24).
- **ERR**: Microchip USB2517/17i Silicon Errata, DS80000628A (10/28/2014), silicon A2. Listed on the product page.
- **EVB**: Microchip EVB-USB2517 Rev A: schematic `evb2517sch.pdf` (sheet 2 of 3, 2008-09-29) and BOM `evb2517bom.pdf` (Rev A, 20080929).
- **AN26.21**: Microchip "USB Device Design Checklist", DS00001863B (2015).
- **AN26.2**: Microchip "Implementation Guidelines for … USB Hub … Devices", DS00001876D (2024).
- **AN15.17**: SMSC "PCB Layout Guide for USB Hubs" (USB251x/xB), Rev 1.0 (10-13-11).
- **251xB**: Microchip USB251xB/xBi datasheet, DS00001692A (2014). Used for comparison only.
- **XT**: YXC YSX321SL crystal datasheet. This is the LCSC mirror for C15643 (X322524MSB4SI), one undated page.
- **ST**: ST USBLC6-2 datasheet, Doc ID 11265 Rev 5 (Oct 2011), LCSC mirror of C7519. ST's site blocks scripted download, so it was not compared with ST's latest revision.

### U1 Microchip USB2517I-JZX (7-port USB 2.0 hub, QFN-64)

| Reference element | Datasheet / guide | Ours | Verdict | Source |
|---|---|---|---|---|
| Symbol pin map | Fig. 3-1 / Table 5-1 pin numbers | All 64 pins and EP 65 in `symbols.py usb2517()` match. The duplicate VDDA33 name binds all four pins (eda.py matches by name) | OK | DS Fig. 3-1 p7, Table 5-1 p10–15; AN26.21 §1.1 A p2 |
| 3.3 V supply range | VDD33/VDDA33/VDD33PLL/VDD33CR 3.0–3.6 V (abs. 4.6 V) | +3V3 from AP2114H-3.3 | OK | DS §8.2 p48, §8.1 p47 |
| 3.3 V decoupling | Datasheet gives no value. Caps close to pins, low-inductance connections; EVB: 0.1 µF per pin plus 4.7 µF and 2 × 10 µF bulk | 100 nF on each of pins 46, 64, 24, 5, 10, 52, 57 (C11–C17). Nearest bulk is C3 22 µF at the LDO, ≈ 78 mm away through the In2 plane | OK (values). Placement: check (see notes) | AN26.21 §2.1 A/D p4; AN26.2 §3.1 p6, §3.6.3 p14; EVB BOM items 1, 5, 6 |
| VDD18 (pin 25), internal core regulator output | "must have a 1.0 µF (or greater) ±20% (ESR < 0.1 Ω) capacitor to VSS" | C7 1 µF 0402 25 V X5R ±10% (C52923) + C9 100 nF | OK, thin margin; DC bias: **to check by the user (U10)** | DS Table 5-1 p15 |
| VDD18PLL (pin 62), internal PLL regulator output | Same 1.0 µF (or greater) ±20%, ESR < 0.1 Ω | C8 1 µF + C10 100 nF | OK, thin margin; DC bias: U10; C8 ≈ 5 mm from pin 62 (check) | DS Table 5-1 p15; AN26.2 §3.1 p6 |
| Nothing driven onto regulator outputs | No external voltage on internal regulator outputs | HUB_1V8 and HUB_1V8PLL carry only their caps | OK | AN26.21 §1.1 H p2 |
| RBIAS (pin 63) | 12.0 kΩ ±1 % to ground; return to the GND nearest the pin, via not shared | R1 12k 1 % (C25752, 0402WGF1202TCE), ≈ 3.5 mm from the pin | OK. Return path: check in layout | DS Table 5-1 p12; AN26.21 §1.1 K p2, §2.1 F p4; AN26.2 §3.6.4 p15 |
| RESET_N (pin 43): internal POR | Datasheet: tie RESET_N to VDD33 and the internal POR handles reset. **Errata Module 2: "Internal POR circuit does not function"**; the reset may be lost on a drop or a non-monotonic ramp ("Device might not enumerate"). Fix: an external POR such as a MAX809S (2.93 V) supervisor | R2 10k up, C6 1 µF down (τ ≈ 10 ms, the EVB's τ: 100k / 0.1 µF). Handles a clean ramp; does not reset on a brown-out | **to fix** (supervisor) | DS Table 5-1 p14; ERR Module 2 p2; AN26.2 §2.4 p3 ("simple RC … not recommended"); AN26.21 §1.1 D p2 |
| 3.3 V rise time | tRT ≤ 400 µs, or up to 100 ms "if RESET_N is controlled low during the 3.3V rise time" | +3V3 follows the node's switched DUT_5V (soft turn-on, order of 1 ms): over 400 µs. With the RC, RESET_N ≈ 0.16 V at the end of a 1 ms ramp (VIL 0.8 V), released ≈ 3–9 ms later (Schmitt 0.8–2.0 V) | OK as long as RESET_N is held low (the RC does it, so does the supervisor) | DS §8.2 Note 8-1 p48, Table 8-2 p49 |
| RESET_N timing | ≥ 1 µs low after supplies are valid; hub operational 500 µs after release; supplies valid before or with RESET_N assertion | ≈ 10 ms RC | OK | DS §7.6.2 p42, Table 7-6 p43 |
| VBUS_DET (pin 44) | "For self-powered applications with a permanently attached host, this pin must be connected to 3.3V or 5.0V (typically VDD33)". AN26.2: allowed for always-on applications, "not usually recommended"; embedded designs should drive it from a 3.3 V signal | Tied to +3V3. The board's only supply arrives on the same lead as the upstream pair (J1.8 = the node's DUT_5V), so it is powered only while the host side is up | justified deviation | DS Table 5-1 p10; AN26.2 §2.5 p4; AN26.21 §1.1 J p2 |
| Self- vs bus-powered | CFG_SEL 000 loads CFG1 = 9Bh: SELF_BUS_PWR = 1 (self-powered, each port may draw 500 mA), MTT on, individual sensing and switching. CFG2 = 20h: DYNAMIC = 0, so LOCAL_PWR is ignored; OC timer 8 ms. (010 would select bus power) | Self-powered from +5V; LOCAL_PWR (pin 45) pulled down | OK. Self-powered is the right choice: as a bus-powered hub, the host would budget 100 mA per port | DS Table 5-2 p15–16, Table 7-1 p20, §7.2.1.7–8 p23–24 |
| CFG_SEL[2:0] straps | 000 = "Internal Default Configuration, Strap Options are Enabled". SMBus/EEPROM unused, so SCL and SDA are free as straps | 10k pull-downs on SCL/CFG_SEL0 (41), HS_IND/CFG_SEL1 (42), CFG_SEL2 (13) | OK | DS Table 5-1 p13, Table 5-2 p15 |
| NON_REM[1:0] | 00 = all ports removable (the straps cover ports 1–3 only) | SDA/NON_REM1 (40) and SUSP_IND/NON_REM0 (45) pulled down. Port 5 (hard-wired RP2354B) is reported removable | OK (cosmetic) | DS Table 5-1 p13–14, §7.2.1.10 p26 |
| GANG_EN, BOOST[1:0], PRT_SWP[7:1] | 0 = individual; 00 = normal drive; 0 = normal D+/D− polarity | All pulled down (RN1–RN3, R3, R5, R9) | OK | DS Table 5-1 p11–12 |
| LED/strap pull value | Fig. 7-3 recommends 100k. A pin strapped low drives active-high and sources the LED current | 10k: each such pin sources ≈ 0.33 mA when its indicator is on (USB LED mode: LED_A/B, HS_IND, SUSP_IND), ≤ ≈ 4 mA in all | justified deviation (firmer straps, small current) | DS §7.5 p41, Fig. 7-3 p42, Table 7-1 (CFG3 00h) |
| Strap timing | Sampled at RESET_N rise; setup/hold 16.7 µs | Static resistors | OK | DS Table 7-6 p43 |
| TEST (pin 19) | IPD, test mode only; the EVB ties it to GND | GND | OK | DS Table 5-1 p15; EVB sch. sheet 2 |
| EP (pin 65) | "Thermal Slug (must be connected to VSS)"; fill the flag with vias | GND | OK. Via fill: check in layout | DS Fig. 3-1 p7; AN26.21 §2.1 E p4 |
| USBUP_DP/DM (59/58) series parts | "Fully integrated USB termination and Pull-up/Pull-down resistors". No series R or external pull-up in the datasheet or on the EVB (J0 straight to the pins) | Straight to J1.6/J1.5 | OK, none needed | DS p1, Table 5-1 p10; EVB sch. sheet 2 |
| Upstream ESD and VBUS cap | ESD near exposed USB connectors; 2.2 µF on the upstream VBUS of a stand-alone hub | J1 is an internal PH lead to the node: no ESD on UP_D± here (the hub is rated 4 kV HBM); no upstream VBUS pin (+5V is the supply, C1 22 µF) | justified deviation (internal harness) | AN26.2 §3.1 p6, §2.5 p4; AN26.21 §1.1 I p2; DS §8.1 p47 |
| Upstream impedance | 90 Ω ±15 % differential | Board traces controlled; the PH lead is not | check (HS when a PC is the host through the node's mux; the ESP32-S3 host is FS) | AN26.21 §2.1.2 C p7 |
| PRTPWR1–7 / OCS1–7_N | Checklist: PRT_PWR should drive a port power switch with an open-drain OC flag (exposed ports). OCS_N are IPU (35–90 µA) | Unconnected on purpose: each TPS2553 is switched by the node through the TCA6408A, and its FAULT_N is read the same way | justified deviation. The host's port-power requests and over-current reports have no physical effect | AN26.21 §1.2 A p3; DS Table 5-1 p10, p12; Table 8-2 p49 |
| LED_B4–7_N (14, 16, 18, 32) | Outputs only, no strap function | NC | OK | DS Table 5-1 p11 |
| Unused ports 6 and 7 | PRT_DIS strap: "To disable, pull up with 10K resistor to 3.3V". The USB251xB datasheet requires both D+ and D− high to disable | D± left open, so the ports stay enabled; the host sees 7 ports, 6 and 7 always empty | justified deviation (cosmetic) | DS Table 5-1 p10; 251xB Table 3.2 p17 |
| PRT_DIS on used ports | Every DN D± is a strap at RESET_N rise | Ports off at reset, so a bus-powered DUT has no pull-up then. A self-powered DUT that ignores VBUS and pulls D+ through 1.5k could read as "disable" if the USB2517 needs only one line high (not stated) | **to check by the user (U3)** | DS Table 5-1 p10; 251xB Table 3.2 p17 |
| Ports 1–4 → USB-C | DNn_DP → PORTn_DP → USBLC6 4/3 → CONN_DP → A6/B6; D− via 6/1 → A7/B7 | As listed | OK (PRT_SWP = 0) | DS Table 5-1 p10 |
| Port 5 → RP2354B | Integrated termination; no hub-side parts | CP_HUB_DP/DN, 22 Ω at the RP2354B (the RP2354B section). Base variant: R23/R24 not fitted, so ≈ 43 mm open stubs | OK | DS p1 |
| Downstream VBUS bulk | Checklist: 150 µF on each exposed port's VBUS (USB-IF droop) | 22 µF after each port's own current-limited TPS2553 | see the ports section. Per-port limiting already keeps ports from loading each other | AN26.21 §1.2 C p3; AN15.17 p6 |
| Thermal | θJA 27 °C/W (2S2P, still air), θJC 2.3 | ≈ 1.15 W with 4 HS + 1 FS ports (HS host): ≈ +31 °C; 7 HS max 1.52 W: +41 °C; FS host ≈ 0.75–0.9 W: +20–24 °C | OK (industrial part, Ta ≤ 85 °C) | DS Table 8-1 p49, Table 8-2 p50 |
| Silicon errata 1, 3, 4 | Suspend timing; HS termination ≈ 41 Ω (in spec); an FS device may be detected as LS after a reset early in the frame, with the hub at HS | No hardware action possible | check (FS DUTs behind a HS host) | ERR p2–3 |

Notes:
- **Hub 3.3 V current** (DS Table 8-2 p50, all supplies combined, single 3.3 V input):
  - Unconfigured: 95 mA.
  - FS host (the bay node's ESP32-S3): 205 / 210 / 215 / 220 mA typ for 1–4 ports; 235 typ / 270 max with 7 ports.
  - HS host (a PC through the node's mux): 1 HS + 1 FS 230 mA, 2 HS 270 mA, 4 HS 330 mA, 7 HS 420 typ / 460 max mA.
  - Suspend 0.36 / 0.61 mA; held in reset 0.11 / 0.40 mA.
  - For us, 4 HS ports plus the FS RP2354B is ≈ 330–350 mA typ: budget 460 mA, plus ≤ 4 mA into the 10k straps. The max figures are DS Note 8-6's worst case (ICH10 EHCI, VDD + 20 %).
- **VDD18 / VDD18PLL margin**: C52923 is ±10 %. At 1.8 V DC bias it loses roughly 5–15 %, and X5R at 85 °C another ≤ 15 %. With the 100 nF beside it the total is ≈ 0.8–0.9 µF, against the datasheet's "1.0 µF ±20 %" (≥ 0.8 µF). It is compliant, with no margin.
  - Optional, free: C7 and C8 → 4.7 µF 0402 C23733 (basic, already in the logic BOM). The datasheet says "or greater".
- **Placement, judged from design.py coordinates (U1 at 90°: pins 1–16 south W→E, 17–32 east S→N, 33–48 north E→W, 49–64 west N→S)**:
  - C17, the only cap for VDD33 pin 46, is ≈ 7.5 mm north of the pin, beyond the strap rows.
  - C15 sits ≈ 7 mm from the nearest VDDA33 pin (5).
  - C8 is ≈ 5 mm from VDD18PLL pin 62.
  - The crystal is ≈ 9 mm from pins 60/61, so XI/XO must pass the C15–C8–C10–R1–C11 row (RBIAS and VDD18PLL), which AN15.17 p7 and AN26.21 §2.1 I/K say to keep 5× spacing from.
  - AN26.2 §3.1 p6: "Place the bypass capacitors as close as possible", the 1 µF regulator caps included.
  - Check these in the PCB review: each pin's own cap and vias, crystal-trace spacing, the RBIAS GND via not shared.

### Y1 YXC X322524MSB4SI (24 MHz, 3225, CL 20 pF, ±10 ppm)

| Reference element | Datasheet / guide | Ours | Verdict | Source |
|---|---|---|---|---|
| Crystal type | Hub: parallel resonant, fundamental, 24 MHz ±350 ppm. YSX321SL: AT-cut fundamental | 24 MHz AT fundamental | OK | DS §9.1 p52; XT p1 |
| Frequency budget | ±350 ppm (hub); USB HS ±500 ppm | ±10 ppm tol, ±20 ppm over −40…85 °C, ±3 ppm/yr, + ≈ 5–10 ppm load pull ⇒ < ±50 ppm | OK | DS §9.1 p52; XT p1 |
| Pinout | Pads 1–3 are the crystal, 2 and 4 GND | 1 = XI, 3 = XO, 2/4 = GND | OK | XT p1 ("Top View Crystal Connection") |
| Load capacitance | CL = (C1+CS1)(C2+CS2)/(C1+CS1+C2+CS2), CS = CB + CXTAL; CXTAL = 2 pF. The EVB uses 33 pF with an 18 pF crystal | C4 = C5 = 33 pF C0G (C1562). CB ≈ 1.5–3 pF ⇒ CL ≈ 18.3–19.0 pF, + ≈ 0.5 pF XI–XO shunt ≈ 18.8–19.5 pF vs 20 pF. The simple formula: 16.5 + 3–5 = 19.5–21.5 pF | OK (≈ −1 pF ⇒ ≈ +5 ppm, at an estimated 5 ppm/pF) | DS Fig. 9-1/9-2 p52, Table 8-3 p51; EVB BOM items 4, 32 |
| Parallel 1 MΩ | Fig. 9-1 "Typical crystal circuit" shows a 1 Meg across XTAL1–XTAL2. The EVB populates R19 1Meg across Y1; AN15.17 places a "parallel resistor". The USB251xB states an internal 1 MΩ; the USB2517 datasheet does not | None | **to check by the user (U2)**; fitting it anyway is harmless | DS Fig. 9-1 p52; EVB sch. sheet 2, BOM item 21; AN15.17 p6; 251xB §7.1 p53 |
| ESR | Hub gives no limit; crystal ESR ≤ 50 Ω (16–31 MHz) | 50 Ω max | OK (same class as the EVB's HC-49) | XT p1 |
| Drive level | Crystal 10–200 µW (100 typ). Hub drive not specified; XTAL2 ≤ VDD18 (1.8 V) | Estimate DL = ESR·(2πf·(C0+CL)·Vpp/2√2)²: 54–108 µW at 1.2 Vpp, 122–243 µW at 1.8 Vpp (ESR 25–50 Ω, C0+CL 23 pF) | check (XTAL2 amplitude) | XT p1; DS §8.2 p48 |
| C0 | ≤ 3 pF | n/a | OK | XT p1 |
| Layout | Crystal parts near the pins, foreign traces ≥ 5× spacing, short cap grounds | ≈ 9 mm from the pins (U1 west face), C4/C5 at the pads | check (see U1 notes) | AN26.2 §3.6.7 p22; AN15.17 p6 |

### U103/U203/U303/U403 ST USBLC6-2SC6 (ports 1–4 D± ESD)

| Reference element | Datasheet / guide | Ours | Verdict | Source |
|---|---|---|---|---|
| Pinout / flow-through | I/O1 = 1↔6, I/O2 = 3↔4, GND 2, VBUS 5. Fig. 18: line in on 1/3, out on 6/4 | Connector side on 1 (D−) and 3 (D+), hub side on 6 and 4; the lines run through the pads | OK | ST Fig. 1 p1, Fig. 18 p9 |
| VBUS pin | To the bus supply, with CBUS = 100 nF | Pin 5 on +5V (always on with the board), C104/204/304/404 100 nF at ≈ 3 mm | OK. +5V rather than the switched PORTn_VBUS keeps the upper diodes on a live rail when a port is off | ST Fig. 14 p8, Fig. 18 p9 |
| Stand-off | IRM ≤ 150 nA at VRM 5.25 V; VBR ≥ 6 V | +5V 5.0–5.24 V | OK (at the edge of VRM) | ST Table 2 p2 |
| HS loading | Ci/o-GND 2.5 typ / 3.5 max pF, matching 0.015 pF; for USB 2.0 up to 480 Mb/s | One per port, D± only | OK | ST Table 2 p2, p1, p7 |
| ESD rating | IEC 61000-4-2 level 4: 15 kV air, 8 kV contact (15 kV contact absolute) | n/a | OK | ST p1, Table 1 p2 |
| Placement | "as close as possible to the disturbance source (generally the connector)"; short GND and VBUS tracks | 7 mm from the receptacle axis (cx + 7.0), 100 nF at pin 5 | OK. GND via length: check in layout | ST §2.3 p5–6; AN26.2 §3.1 p6 |
| Receptacle VBUS pin | The USBLC6 protects its VBUS pin only | PORTn_VBUS is not on the USBLC6; an ESD hit there lands on C102 22 µF and the TPS2553 OUT (8 kV / 150 pF ⇒ ≈ 55 mV on 22 µF) | OK | ST Fig. 14 p8 |
| Unpowered board | Upper diodes conduct into VBUS | With DUT_5V off, a self-powered DUT's 1.5k D+ pull-up feeds ≤ ≈ 2 mA into the dead +5V through the diode | OK (harmless) | ST Fig. 16 p9 |


## Crosspoints and pin chain (CH446Q, TPS60400, TCA9534A, LSF0108, H5VU25UC)

Scope: design.py `matrix_sheet()`, the pin chain in `port()`, the bus pull-ups in `coproc_sheet()`, and docs/electronics.md › "The VREF rule".

Sources:
- **CH446**: WCH "CH446 中文手册", version 1C. This is the LCSC mirror (atta.szlcsc.com, 2017-05-15). WCH's own download page is a JS app, no newer or English copy was found, and the PDF has 9 pages.
- **LSF**: TI LSF0108 datasheet, SDLS966M (May 2023).
- **SLVA675**: TI "Voltage-Level Translation With the LSF Family", SLVA675B (Mar 2015).
- **TPS**: TI TPS6040x datasheet, SLVS324C (Oct 2020).
- **TCA**: TI TCA9534A datasheet, SCPS198C (Feb 2017).
- **H5V**: hongjiacheng H5VU25UC, Rev 2.0 (LCSC C20615800).
- **RP2350**: Raspberry Pi RP2350 datasheet, build 80d627281ed5.

### U7/U8 WCH CH446Q (8 × 16 crosspoint)

The manual read here is WCH's Chinese one, version 1C, from an LCSC mirror; WCH's own page (https://www.wch-ic.com/downloads/CH446DS1_PDF.html) gave no newer or English copy.  The rows marked U4 rest on that reading: see "To check by the user".

| Reference element | Datasheet / guide | Ours | Verdict | Source |
|---|---|---|---|---|
| VDD (single-supply range) | VDD 4–13.2 V (GND = 0), with VDD > GND + 4 V | +5V_MX 4.75–5.24 V | OK (0.75 V margin over GND + 4 V) | CH446 §6.2 p6 |
| VEE and VDD − VEE | VEE −8.8 to 0 V, VDD − VEE < 13.2 V; "VDD=5V & VEE=−5V (VDD−VEE=10V)" is one of the recommended combinations | VEE −4.7 to −5.24 V, span 9.5–10.5 V | OK as read; **to check by the user (U4a)** | CH446 §6.2 p6 |
| Absolute maximum supply | VDD ≤ 16 V (VEE = GND), VEE ≥ −16 V (VDD = GND) | span ≤ 10.5 V | OK | CH446 §6.1 p6 |
| Supply polarity and sequencing | Pin table: VDD "必须大于等于 GND", VEE "必须小于等于 GND". No other sequencing or latch-up clause in v1C | VEE starts at 0 V and goes negative as the pump starts; the TPS60400's active Schottky stops OUT going positive (R40/R41 push ≈ 22 µA in until then) | OK | CH446 §4.1 p2; TPS §8.4.1 p12 |
| Analog pin range | Recommended VEE…VDD; absolute VEE − 0.5…VDD + 0.5 | Bus 0–3.3 V (≈ 3.6–4.2 V with a 5 V VREF). +3V3 is derived from the same +5V through the LDO, so the pull-ups never exceed VDD while it ramps | OK | CH446 §6.1–6.2 p6 |
| Switch current | Isw ≤ 15 mA per switch, Iall ≤ 100 mA total (absolute) | Pull-up ≤ 1.8 mA. Push-pull contention between two DUTs: ≈ 6–12 mA, limited by 2 × 100 Ω | OK; the 100 Ω arrays are what keep this in range | CH446 §6.1 p6 |
| Logic levels at 5 V | VIL ≤ 0.8 V, VIH ≥ 2.0 V at VDD − GND = 5 V | TCA9534A push-pull outputs at 3.3 V | OK as read; **to check by the user (U4b)** | CH446 §6.3 p6 |
| Static current with logic-high inputs | ICC5 0.4 typ / 1.5 max mA (VDD 5 V, inputs at 2.4 V). ICC0 ≤ 100 µA with inputs at rails | RST/DAT/CK/STB sit at 3.3 V when high | OK. Keep DAT/CK/STB low when idle (firmware) | CH446 §6.3 p6 |
| Decoupling | "VDD 和 VEE 引脚必须外接退耦电容"; the reference circuits show 0.1 µF on each | VDD: 100 nF + 1 µF (C20/C21, C23/C24). VEE: 100 nF (C22, C25). Each sits on the face of its pin, about 1.75 mm past the pin tips | OK | CH446 §7.1 p7, Fig. §7.2 p8 |
| Serial mode select | P/S: high = parallel, low = serial | P/S (pin 10) on GND | OK | CH446 §4.1 p2 |
| AX0–AX3, AY0–AY2 in serial mode | "串行地址方式下，为未用引脚，必须直接连接 GND"; the §7.2 reference circuit ties them all to GND | Pins 43, 18, 19, 42, 20, 21, 40 on GND | OK as read; **to check by the user (U4c)** | CH446 §4.1 p2, §7.2 p8 |
| NC pins 9, 22, 23, 32, 44 | "未用引脚，禁止连接" (unused, do not connect) | Not in `conns`, so left open | OK | CH446 §4.1 p2 |
| RST | Active high. While RST is high, ACT is ignored and every latch is held at 0 (all switches open) | MX_RST: R20 10k to +3V3, driven by TCA9534A P4 | OK as read; **to check by the user (U4d)** | CH446 §4.1 p2, §5 p3 |
| Power-up latch state | Not specified | RST is high once +3V3 is up. During the ≈ 1 ms before that, the LSF0108s are still off: their EN = Vref_B ramps with 200k × 100 nF = 20 ms | OK | CH446 §5 p3; LSF §8.3.2 p11 |
| Serial protocol | 7 rising CK edges shift ADDR6…0 (AY2…AX0), then DAT = on/off and a high STB pulse. Setup times: TAS ≥ 7 ns, TDS ≥ 8 ns, TCS ≥ 10 ns | One TCA9534A drives DAT/CK shared and STB1/STB2 separately. The expander changes all 8 pins at once | Check: firmware must put DAT, CK↑ and STB in separate writes (see Checks) | CH446 §5 p3, Fig. p4, §6.5 p7 |
| Edge rate and refresh | Recommends slowing the digital edges and the transfer rate (VDD is shared between analog and digital); in noisy environments, rewrite the switches every few seconds | Fast push-pull edges from the TCA9534A, no RC; changes at I²C pace | Justified deviation (low rate, RST masks power-up). Firmware: periodic refresh | CH446 §7.1 p7 |
| R_on at ±5 V | 45/65 Ω at VDD − VEE = 12 V (25 °C); 120/185 Ω at 5 V span (25 °C), 150/225 Ω at 85 °C. Nothing given for a 10 V span | ±5 V, chosen to get the low R_on | **to check by the user (U4e)**, then measure | CH446 §6.3 p6 |
| Switch capacitance | CSW 10 typ / 25 max pF per port pin; −3 dB bandwidth 50 MHz (3 kΩ load) | Two Y pins per bus, plus the X pins that are on | OK; this sets the bus speed (see the LSF notes) | CH446 §6.4 p7 |
| VEE current | Not specified | Taken as µA-level (CMOS) | Check: measure it | CH446 §6.3 p6 |
| Pin numbers (bench symbol) | §4.1 table and package drawing | X0–X5 = 31–26, X6–X11 = 3–8, X12/13 = 25/24, X14/15 = 1/2, Y0–Y3 = 33/35/37/39, Y4–Y7 = 17/15/13/11, VDD 38, VEE 16, GND 12, RST 41, DAT 36, CK 34, STB 14, P/S 10 | OK: they match | CH446 §3–4.1 p2 |

Notes:
- **Power-up and supplies:** nothing in the power-up or supply ranges is out of spec. The design's three safeguards each match the datasheet:
  - RST is pulled high.
  - VEE comes up after VDD, from 0 V.
  - The LSFs start off.
- **Supply current in the docs:** electronics.md says +5V_MX carries "about 70 mA". That figure is stale. The real load is ≈ 1–4 mA:
  - two CH446 at ≤ 0.1–1.5 mA each;
  - the TPS60400's IQ, 125–270 µA, plus 2 × IO;
  - the LSF bias, 4 × ≤ 21 µA;
  - R38/R39, 34 µA.
- **Ferrite comment:** design.py says the ferrite "keeps … the charge pump's 250 kHz apart". A 600 Ω-at-100 MHz bead is only a few Ω at 30–250 kHz. This is harmless only because the pump draws < 1 mA.

### U9 TI TPS60400DBVR (charge-pump inverter)

| Reference element | Datasheet / guide | Ours | Verdict | Source |
|---|---|---|---|---|
| Input voltage | Recommended 1.8–5.25 V; absolute 5.5 V | +5V_MX 5.0–5.24 V | OK. Only 10 mV of margin at the top: check the no-load +5V | TPS §7.3 p4, §7.1 p4 |
| Output voltage limit | OUT absolute −5.5 V; VO ≈ −(VI − RO·IO), RO ≈ 12–15 Ω | ≈ −VI = −5.0 to −5.24 V | OK | TPS §7.1 p4, §8.3.1 p11, §7.5 p5 |
| Output current | ≤ 60 mA | R41 path (3.3 + 5.24)/147k ≈ 58 µA, plus 2 × CH446 VEE (not specified, µA) | OK, < 1 % of rating | TPS §7.3 p4 |
| Capacitor values for the -400 | Table 9-1: TPS60400 CI = C(fly) = CO = 1 µF (-401 10 µF, -402 3.3 µF, -403 1 µF); ceramic X5R/X7R | C26 fly, C27 in, C28 out: all 1 µF 0402 25 V X5R (C52923) | OK | TPS Table 9-1 p14, Table 9-3 p14 |
| CO minimum after DC bias | ROC: CO ≥ 1 µF. §9.2.1.2.4: "Smaller capacitance values can be used with light loads if higher output ripple can be tolerated" | All three caps see ≈ 5 V. A 0402 1 µF X5R typically keeps ≈ 40–60 % at 5 V, so ≈ 0.4–0.6 µF | **to check by the user (U10)** | TPS §7.3 p4, §9.2.1.2.4 p14. Samsung DC-bias curve not retrieved (product page has no data) |
| IN bypass | "Bypass IN to GND with a capacitor that has the same value as the flying capacitor" | C27 1 µF = C26 | OK | TPS Pin Functions p3 |
| Output ripple | V = IO/(fosc·CO) + 2·IO·ESR; fosc (VCO version) 30 min, 50–250 typ, 350 max kHz | Worst case ≈ 0.5 mA / (30 kHz × 0.45 µF) ≈ 37 mV p-p; typical ≈ 0.1 mA at 50 kHz ≈ 4 mV | OK | TPS eq. 6 p14, §7.5 p5 |
| Start-up into a load | Integrated active Schottky keeps OUT from being pulled above GND | +3V3_CP pushes ≈ 22 µA in through R40/R41 until the pump runs | OK | TPS §8.4.1 p12 |
| Quiescent current, dissipation | IQ 125 typ / 270 max µA; PD trivial | n/a | OK | TPS §7.5 p5, §9.2.1.2.5 p15 |
| Layout | "All capacitors should be soldered as close as possible to the IC" | C26/C27 2.8 mm and C28 3.4 mm from U9 centre | OK | TPS §11.1 p21 |
| Variant choice | -400 (VCO, 1 µF) vs -401/-402 (larger caps) vs -403 (fixed 250 kHz, IQ 425–700 µA) | -400 | OK (lowest IQ with 1 µF caps) | TPS Device Comparison p3, §7.5 p5 |

Notes:
- −5 V ripple only moves the switches' gate-drive rail, and R_on barely depends on it. Fit 4.7 µF (C23733, already a BOM line) at C28 only if bring-up shows ripple trouble; nothing points to that.

### U10 TI TCA9534APWR (matrix expander)

| Reference element | Datasheet / guide | Ours | Verdict | Source |
|---|---|---|---|---|
| Supply | VCC 1.65–5.5 V | +3V3 | OK | TCA p1, §6.3 p5 |
| Address | A2 A1 A0 = L L L → 0x38 (range 0x38–0x3F) | A0–A2 on GND, 0x38. No clash with 0x20/0x21 or 0x40–0x45 | OK | TCA Table 2 p19 |
| Reset pin | None: 16 pins (A0–A2, P0–P7, GND, INT, SCL, SDA, VCC). Reset only by power-on reset | n/a | OK (confirmed) | TCA Pin Functions p4, §8.4.1 p17 |
| Power-on state | Every Px is an input at power-on. Output register default 0xFF, configuration 0xFF | Relied on: MX_RST high via R20, RUN high via R25, BOOTSEL released | OK | TCA Pin Functions p4, Tables 5/7 p20 |
| Internal pull-ups | None: "identical to the TCA9554 except for the removal of the internal I/O pull-up resistors" | DAT, CK, STB1, STB2 and MARK float until the node configures the expander | Justified deviation: while RST is high the CH446 ignores ACT (CH446 §5), so floating inputs cannot close a switch | TCA §8.1 p15 |
| Unused/floating P-port | TI's example: unused pins "must be configured as outputs"; ICC rises as an input sits below VCC | All 8 used; firmware sets them as outputs | OK, firmware | TCA Fig. 33 p24, §9.2.1.2 p25 |
| INT | Open-drain output | Not connected | OK (an output may be left open) | TCA Pin Functions p4, §8.3.2 p17 |
| SCL/SDA | Must not be above VCC; pull-ups to VCC | Board-side SDA/SCL pulled to +3V3 (R6/R7), the same rail | OK | TCA §6.3 note (1) p5, Fig. 33 p24 |
| Decoupling | Bypass capacitor as close as possible | C29 100 nF, 4 mm from U10 | OK | TCA §11.1 p29 |
| Output level into CH446 / RP2354B | Push-pull, VOH ≈ VCC at µA load | 3.3 V into VIH 2.0 V (CH446) | OK | TCA §6.5 p6; CH446 §6.3 p6 |
| RUN / BOOTSEL as emulated open drain | Configuration register switches a pin between input (Hi-Z) and output | Output register bit = 0; the configuration bit toggles. R25 10k pull-up on RUN, 1k series to QSPI_SS | OK. P5/P6 must never be outputs driving 1 (P6 = 1 would fight QSPI_SS through 1k) | TCA §8.6 p20 |

### U107/U207/U307/U407 TI LSF0108RKSR, its bias, and the bus pull-ups

| Reference element | Datasheet / guide | Ours | Verdict | Source |
|---|---|---|---|---|
| EN and Vref_B wiring | "EN input should be tied directly to Vref_B … pulled up to the HIGH side (VCCB) through a bias resistor (typically 200 kΩ) … a filter capacitor on Vref_B is recommended" (0.1 µF in the figures) | EN = Vref_B, R111 200k to +5V_MX, C105 100 nF | OK | LSF §8.3.2 p11, §9.2.1.1.2 p14 |
| Headroom | VCCB ≥ Vref_A + 0.8 V (Table 9-2); "recommended to be 1.0 V higher … for best signal integrity". ROC footnote (rev M) relaxes translation to ≥ Vref_A + 0.6 V | VCCB = +5V_MX ≥ 4.75 V: VREF ≤ 3.95 V (0.8 V rule), ≤ 3.75 V (1.0 V rule). Spec is 0.95–3.6 V | OK; design.py and electronics.md quote this correctly | LSF Table 9-2 p14, §9.2.1.1.2 p14, §6.3 note (1) p5 |
| Vref_A range | ROC footnote: translation from Vref_A 0.65 V (rev M); §8.3.1 says 0.95–5.5 V | VREF 0.95–3.6 V | OK | LSF §6.3 p5, §8.3.1 p10 |
| "Vref_A is the lowest voltage" | Table 9-2 note: "Vref_A is required to be the lowest voltage level across all inputs and outputs" | B pull-ups are at 3.3 V, so VREF 3.3–3.6 V breaks this | **to check by the user (U6)** | LSF Table 9-2 p14 |
| Bias current sink | "Current does flow into the A-side voltage supply … not all voltage sources can sink current" | 10k + 10k (R112/R113) to GND sink it (≤ 21 µA) | OK; a good choice | LSF §9.2.1.1.2 p14 |
| B-side pull-ups | "Pull-up resistors are always required on the high side" | Each bus: 10k to +3V3 (RN8/RN9) always, plus 2.2k switchable (RN6/RN7). An X line that no switch connects floats on its B side, which is harmless because it carries nothing | OK | LSF §8.4.1 p12 |
| Pull-up sizing | Keep current through the pass FET ≈ ≤ 15 mA | 10k‖2.2k = 1.8k → ≤ 1.8 mA | OK | LSF §9.2.1.2.2 p15 |
| A-side pull-ups | Needed "if the low side … output is open drain or its input has a leakage greater than 1 µA"; down-translation without pull-ups gives a "weak 1" at Vref_A | None on our side | Justified deviation: the FET path from the B pull-up gives A its weak 1 at Vref_A, and DUT I²C buses carry their own pull-ups | LSF §8.4.1 p12; SLVA675 §1 p2, §5.2 p6 |
| Pass current / I/O voltage | IPASS ≤ 64 mA (ROC); VI/O ≤ 7 V absolute, ≤ 5.5 V recommended | ≤ 12 mA (contention case); pins ≤ 5.25 V | OK | LSF §6.3 p5, §6.1 p5 |
| On-resistance | 3–5 Ω (Vref_A 1–3.3 V); 15 Ω at Vref_A 0.65 V | n/a | OK; small next to 100 Ω + CH446 R_on | LSF §6.5 p6 |
| I/O capacitance | CIO(on) 10.5/12.5 pF, CIO(off) 4/6 pF | Adds to the bus C (see notes) | OK | LSF §6.5 p6 |
| Series resistors | Not part of TI's circuit | 100 Ω (RN, C48442) between the ESD and the A pins | OK: limits ESD residual current and DUT-to-DUT contention (< CH446's 15 mA) | LSF §9.2 p13–15 |
| Thermal pad | "Designed to be soldered to a thermal pad"; no net given | EPAD on GND | OK | LSF RKS0020A board-layout note 3 p33 |
| Hi-Z condition | "To ensure the high impedance state during power-up, power-down, or during operation, the EN pin must be LOW." Table 8-1: EN L → Hi-Z | EN never driven low; it sits at Vref_A + VGS ≥ ≈ 0.7 V | See the next two rows | LSF §8.3.2 p11, Table 8-1 p11 |
| DUT off: VREF held at 0 V by its rail | SLVA675 §5.6: "If either Vref_A or Vref_B are grounded, the switch behaves as an open circuit" | VREF at 0 V through the DUT's dead rail | OK: highs are clamped at ≈ 0 V on the DUT side, so no back-powering | SLVA675B §5.6 p6 |
| Board off, DUT powered | EN low → Hi-Z | Vref_B = EN discharges through 200k into the dead +5V_MX → Hi-Z | OK. The CH446 is shielded while unpowered (the VREF divider does feed GPIO40–43, see notes) | LSF Table 8-1 p11 |
| VREF unwired (≈ 0.39 V via 10k + 10k) | Behaviour below the 0.65 V minimum is not specified. The FET conducts while either side is below ≈ Vref_A (gate = Vref_A + VTH; "acts as a passive switch when the input signal is below Vref_A − 0.5 V"); EN is not low | Docs say "under the 0.65 V the LSF needs to translate … the group passes nothing" | **To fix** (docs and firmware, no BOM): lows still pass both ways, highs into A clamp at ≈ 0.4 V. Harmless, but the "isolated" claim is not backed | LSF §6.3 p5, §8.3.2 p11; SLVA675 §1 p2 |
| VREF at 5 V | Vref_B < Vref_A + 0.8 V is outside spec. §9.2.4 allows it with A-side pull-ups, but it needs Vref_B > Vref_A | Vref_B = +5V_MX (4.75–5.24 V) ≤ VREF: the reference FET is off, the gate sits at +5V_MX, and the bus rises to +5V_MX − VTH (with body effect) ≈ 3.6–4.2 V | Justified deviation, as the docs say. The docs' "≈ 4.0–4.2 V" is a bit high at +5V_MX 4.75 V: check | LSF §9.2.4 p19, Table 9-2 p14 |
| ESD on the Vref_A pin | ±2000 V HBM / ±1000 V CDM only (JEP155 note: a manufacturing-control level) | Header pin 2 (VREF) runs straight to Vref_A, which biases all eight pass gates. P1–P8 on the same header get the IEC ±8 kV H5VU25UC | **To fix** | LSF §6.2 p5; H5V p1 |

Notes:
- **Bus capacitance and speed:**
  - A 2-pin virtual wire carries ≈ 75 pF typical and ≈ 140 pF worst case:
    - two Y pins, 20/50 pF;
    - two X pins, 20/50 pF;
    - two LSF B pins, 21/25 pF;
    - RP2354B pad and trace, ≈ 15 pF.
  - 10k alone: τ = 0.75–1.4 µs and 10–90 % rise ≈ 1.7–3.1 µs, so ≈ 0.1–0.2 MHz square wave. UART at 115200 works, with the rise taking up to ≈ 36 % of a bit.
  - With the 2.2k on (1.8k): τ = 0.14–0.25 µs, so ≈ 0.6–1.2 MHz. I²C fast mode fits: 30–70 % ≈ 0.12–0.21 µs < 300 ns.
  - Firmware should switch the 2.2k on for I²C and anything faster than UART. SPI at MHz rates won't pass.
- **Low-level budget (driver to bus, 2.2k on, ≈ 1.7 mA):**
  - Drop = 1.7 mA × (100 Ω + LSF 5–15 Ω + CH446 R_on).
  - R_on 65 Ω: ≈ 0.30 V. R_on 185 Ω (the 5 V-span maximum): ≈ 0.50 V. Add the driver's VOL on top.
  - A 1.8 V I²C bus needs VIL ≤ 0.54 V, so R_on must be ≲ 120 Ω. That is the reason for ±5 V, but the CH446 gives no 10 V-span figure, hence the R_on check.
- **2.2k enable GPIOs:** they must be input (off) or output-high (on), never output-low: that would put a 2.2k pull-down on the bus.
- **RP2350-E9 (A2 stepping, fixed in A3):** the faulty pad *sources* ≈ 120 µA toward 2.2 V. It cannot fight the 10k pull-ups, so there is no conflict on the buses (RP2350 App. D.5.1 p1358). GPIO2–9 are FT, 5.5 V-tolerant while IOVDD is powered (RP2350 §14.8.2.1 p1331), as the VREF rule says.
- **VREF divider with the board off:** the R112/R113 divider feeds GPIO40–43, which are not FT, at VREF/2 through 5k. With the board off and a self-powered DUT, ≈ 0.25 mA flows into an unpowered ADC pad. That is small; see the RP2354B section.

### H5VU25UC (U105/U106 … U405/U406 flow-through; U4 on the lead's SDA/SCL/INT)

| Reference element | Datasheet / guide | Ours | Verdict | Source |
|---|---|---|---|---|
| Stand-off | VRWM 5 V max | P lines ≤ VREF (0.95–3.6 V specified, 5 V tolerated); lead lines 3.3 V | OK. A 5 V VREF sits right at VRWM; a 5.25 V USB-fed DUT is 0.25 V over it, still under VBR (justified) | H5V p2 Electrical Characteristics |
| Breakdown | VBR 6 min / 10 max V at IT = 1 mA | n/a | OK (catalog "6 V at least" is correct) | H5V p2 |
| Leakage | IR ≤ 1.0 µA at 5 V | Adds to A-side input leakage (LSF's 1 µA rule); far below that at ≤ 3.6 V | OK | H5V p2; LSF §8.4.1 p12 |
| Clamping | VC ≤ 10 V at 1 A, ≤ 15 V at 5 A (8/20 µs) | Residual reaches the LSF A pins (7 V absolute) through 100 Ω | OK (100 Ω limits the current) | H5V p2, Fig. 4 |
| ESD / surge | IEC 61000-4-2 ±8 kV contact, ±15 kV air; IEC 61000-4-5 5 A | Header P1–P8, lead I²C/INT | OK | H5V p1 |
| Capacitance | ≤ 0.8 pF I/O–GND, ≤ 0.4 pF I/O–I/O | n/a | OK (negligible) | H5V p2 |
| Pinout: I/O and GND | Function diagram: steering diodes on pins 1, 2, 4, 5, zener anode on pin 8. Recommended land joins the centre pads 3/8 into one bar | I/O 1, 2, 4, 5; GND 3 and 8 (footprint: pad 3 runs into pad 8) | OK as read; **to check by the user (U5a)** | H5V Function Diagram p1, land pattern p3 |
| Pins 6/7/9/10 "tied inside to 5/4/2/1" (catalog.py, electronics.md) | The function diagram draws 6, 7, 9, 10 with **no** internal connection | Each line routed through both pads of its pair. The pads are distinct (footprint `duplicate_pad_numbers_are_jumpers no`) and on the same net, so DRC's 0 unconnected means copper joins them | **to check by the user (U5b)** | docs wording: the user confirmed (U5, 2026-10-25) that they are unconnected inside |
| Polarity | Uni-directional: negative excursions clamp at −VF | Signals ≥ 0 V | OK | H5V p1 |
| Placement | (general) ESD first at the connector | Header → ESD (TPD_Y 36.4) → 100 Ω (RN_Y 34.2) → LSF (29.6) | OK | design.py port() |
| U4 spare line | n/a | D2− (pin 5) unused, partner pads open | OK | — |


## Ports and power (TPS2553-1, INA226, TCA6408A, AP2114H, 2N7002, ferrites, USB-C CC)

Sources:
- **[TPS]** TI SLVS841F, TPS2552/53/-1, rev. F, Aug 2016
- **[INA]** TI SBOS547C, INA226, rev. C, Aug 2026
- **[TCA]** TI SCPS192E, TCA6408A, rev. E, Jan 2023
- **[AP]** Diodes (BCD) AP2114 Data Sheet, Rev. 2.2, Jan 2013 (diodes.com/assets/Datasheets/AP2114.pdf)
- **[CJ]** JSCJ 2N7002 SOT-23, rev. "J, Sep 2016" (LCSC C8545 mirror)
- **[AN]** Philips AN97055, *Bi-directional level shifter for I²C-bus and other systems* (1997). nxp.com refused the AN10441 download ("Page not available"), so AN97055 is cited instead: AN10441 summarises this note, with the same circuit and MOSFET requirements.
- **[GZ]** Sunlord *Multilayer Chip Ferrite Bead – GZ Series* catalogue, revised 2024-06-19 (JLC copy for C1017)
- **[TC]** USB Type-C Cable and Connector Specification, Release 2.0, Aug 2019

Every symbol pin map was checked against the datasheet pinout in the generated schematics. All of them match: bench:TPS2553DBV, Sensor_Energy:INA226, TCA6408ARGT, the AMS1117-3.3 symbol used for the AP2114H, and 2N7002.

### U101–U401 TPS2553DBVR-1 (port switch, latch-off)

| Reference element | Datasheet / guide | Ours | Verdict | Source |
|---|---|---|---|---|
| Pinout DBV | 1 IN, 2 GND, 3 EN, 4 FAULT, 5 ILIM, 6 OUT | The symbol has the same pins 1–6 | OK | [TPS] §6 Pin Functions p.5 |
| Latch-off (-1) | Latches off after the FAULT deglitch. It stays off until EN is toggled or power is cycled (UVLO 2.35/2.45 V) | The node toggles EN through the TCA6408A | OK | [TPS] §9.3.3 p.14, §10.1.1 p.17, §7.5 p.7 |
| VIN | ROC 2.5–6.5 V, abs max 7 V | +5V, 5.0–5.24 V | OK | [TPS] §7.1 p.5, §7.3 p.6 |
| R_ILIM range | 15–232 kΩ, 1 % | 47k 1 % 0402 (C25792) | OK | [TPS] §7.3 p.6 |
| Current limit | Eq. 1: IOSmin = 25230/R^1.016, IOSnom = 23950/R^0.977, IOSmax = 22980/R^0.94 (temperature and process included, resistor tolerance not) | 47k gives 505 / 557 / 616 mA; ±1 % on the resistor gives 500–622 mA. design.py's "0.50–0.62 A" is right | OK | [TPS] Eq. 1 p.15, §10.2.1.2.3 p.19 |
| Limit vs USB load | "the minimum current-limit threshold … exceed the maximum current-limit draw"; a high-power function takes 500 mA | IOSmin is 500–505 mA. It meets 500 mA with no margin at the worst corner. The 3 mA VBUS LED (on 5V_SW) is also counted | OK | [TPS] §10.2.3.2.1 p.23 |
| R_ILIM placement | Traces to R_ILIM as short as possible; ILIM never driven | R101's pad is ≈ 1.8 mm from pin 5 and nothing drives ILIM | OK | [TPS] §12.1 p.25, §10.2.1 p.17 |
| IN bypass | ≥ 0.1 µF ceramic, close to IN/GND, low-inductance trace | 1 µF 0402 X5R 25 V (≈ 0.5 µF at 5 V), ≈ 1.5 mm from pins 1 and 2. +5V arrives from the plane by a 0.6 mm, ≈ 6 mm track | OK | [TPS] §7.3 p.6, §10.2.1.2.4 p.20, §12.1 p.25 |
| Input overshoot | Extra input C when long, inductive supply leads | 45 cm lead. Bulk on the board +5V: C1 22 µF 1206, C2 22 µF, 4 × 1 µF (≈ 30 µF effective). Cutting 0.62 A into ≈ 0.4 µH gives ≈ +0.07 V; abs max is 7 V | OK | [TPS] §10.2.1.2.4 p.20 |
| OUT capacitance | Typical USB application: 120 µF ("USB requirement … at least 120 µF per hub"). "High-value electrolytic … when large transient currents are expected" | 22 µF 0805 X5R after the shunt (≈ 11–13 µF at 5 V), plus the DUT's ≤ 10 µF | justified deviation | [TPS] p.1, Fig. 29 p.22, §12.1 p.25 |
| Start-up into C vs latch | Latches if in current limit longer than the FAULT deglitch (5 / 7.5 / 10 ms); tr = 1.1 / 1.5 ms | 32 µF on the soft-start ramp draws ≈ 0.12 A of inrush. Even at IOS, charging takes 0.32 ms. The port only latches if the DUT has more than ≈ 450 µF | OK | [TPS] §7.5 p.7 |
| EN | Threshold 0.66–1.1 V, IEN ±0.5 µA, ≤ 6.5 V | TCA6408A push-pull at 3.3 V (VOH ≥ 2.6 V); 10k pull-down keeps the port off while the expander pin is an input | OK | [TPS] §7.3 p.6, §7.5 p.7 |
| FAULT | Open drain; VOL ≤ 180 mV at 1 mA; sink ≤ 10 mA | 10k to +3V3 (0.33 mA), read by the TCA6408A (VIL 0.99 V) | OK | [TPS] §7.3 p.6, §7.5 p.7 |
| Reverse voltage | VOUT − VIN > 95–190 mV for 3–7 ms turns it off; the -1 stays latched; FAULT after 2/4/6 ms | A DUT that back-feeds trips the port and latches it. design.py's "≈ 4 ms" is the typical FAULT deglitch | OK | [TPS] §7.5 p.7, §9.3.2 p.14 |
| Thermal | RθJA 182.6 °C/W (DBV); PD = rDS(on)·I² | 0.62² × 0.135 Ω = 52 mW, a rise of ≈ 9.5 °C | OK | [TPS] §7.4 p.6, §11.3 p.24 |
| VBUS level | A self-powered hub must supply 4.75–5.25 V at full load | VBUS = +5V − I·(rDS(on) ≤ 0.135 + 0.1 Ω shunt), i.e. ≈ −0.12 V at 0.5 A. Holding 4.75 V needs +5V ≥ 4.87 V at the board | check | [TPS] §11.1 p.24 |

The 22 µF on OUT is justified because every port has its own limiter. A hot-plug on one port cannot pull down the others' VBUS, and the DUTs are wired before the node switches a port on. The "120 µF per hub" rule is for ports that share one supply. There is no output discharge: an empty port's VBUS decays only through the INA226 Vbus input (830 kΩ), so τ ≈ 18 s (see Checks).

### U102–U402 INA226AIDGSR and R106–R406 (100 mΩ 1206 Kelvin)

| Reference element | Datasheet / guide | Ours | Verdict | Source |
|---|---|---|---|---|
| Pinout DGS | A1 1, A0 2, Alert 3, SDA 4, SCL 5, VS 6, GND 7, VBUS 8, IN− 9, IN+ 10 | Same in the KiCad symbol | OK | [INA] §4 p.3 |
| VS and bypass | VS 2.7–5.5 V; typically 0.1 µF placed close | +3V3; C103 100 nF ≈ 2–3 mm away | OK | [INA] §5.3 p.4, §8.3 p.31 |
| Address straps | Table 6-2 (A1, A0): GND,VS = 1000001 (0x41); GND,SCL = 1000011 (0x43); VS,GND = 1000100 (0x44); VS,VS = 1000101 (0x45). Pins are sampled on every transaction | Ports 1–4 are 0x41, 0x43, 0x44, 0x45. A0 = SCL is a valid table entry. No clash with the node's 0x40, TCA6408A 0x20/0x21 or TCA9534A 0x38 | OK | [INA] Table 6-2 p.18 |
| Shunt range | ±81.92 mV full scale; 2.5 µV/LSB | 100 mΩ gives 819 mA full scale (25 µA/LSB). IOS max 0.62 A is 62 mV, 76 % of full scale | OK | [INA] §5.5 p.5 |
| Shunt power | — (0.25 W part) | 0.62² × 0.1 Ω = 38 mW, 15 % of rating | OK | catalog C25334 |
| Kelvin | IN+/IN− by a Kelvin or 4-wire connection | Kelvin 1206 footprint (net-tie 1-2, 3-4). IN+ on SNS_P (switch side), IN− on SNS_N (load side) | OK | [INA] §8.4.1 p.31 |
| VBUS pin | 0–36 V, 830 kΩ; the example ties VBUS to IN− (load side) | Load-side sense pad (= PORTn_VBUS) | OK | [INA] §5.5 p.5, §6.5.1 p.15 |
| Common mode | 0–36 V regardless of VS; 40 V across the inputs | 0–5.24 V. An unpowered board with a back-feeding DUT stays inside these limits | OK | [INA] p.1, §6.4.2 p.14 |
| Input filter | Only needed for transients at harmonics of 500 kHz (> 1 MHz): ≤ 10 Ω and 0.1–1 µF | None | OK | [INA] §6.4.2 p.14 |
| dV/dt protection | 10 Ω in series with each input against hard-short dV/dt "in systems where large currents are available" | None | justified deviation | [INA] §6.4.2 p.14 |
| Alert | Open drain, VOL ≤ 0.4 V at 3 mA; may float when unused; off at reset (Mask/Enable = 0) | Wired-OR on INT with 10k to +3V3 (R8), plus the node's pull-up through Q3 | OK | [INA] §6.3.1.2 p.12, §5.5 p.6 |
| SDA/SCL | ≤ 6 V abs max | 3.3 V, 4.7k | OK | [INA] §5.1 p.4 |

The 10 Ω input resistors are left out deliberately. Upstream is 5 V limited to 0.62 A, and at most 22 µF (≈ 0.3 mJ) is stored on the load side, so the "large currents available" condition does not apply. Two 10 Ω 0402 per port remain an option if a VBUS hard short ever kills an INA226.

### U2, U6 TCA6408ARGTR (EN, FAULT_N, RESET, BOOT)

| Reference element | Datasheet / guide | Ours | Verdict | Source |
|---|---|---|---|---|
| Pinout RGT | 1 RESET, 2–5 P0–P3, 6 GND, 7–10 P4–P7, 11 INT, 12 SCL, 13 SDA, 14 VCCP, 15 VCCI, 16 ADDR, exposed pad | Same in the KiCad symbol; EPAD (17) on GND | OK | [TCA] Table 5-1 p.3–4 |
| VCCI / VCCP | 1.65–5.5 V; VCCP up before VCCI recommended (SDA stuck low otherwise) | Both on +3V3, so they rise together | OK | [TCA] §6.3 p.5, §10.1 p.31 |
| Decoupling | Caps as close as possible to the device | One 100 nF per expander, 3.1 mm south of its centre (the supply pins are on the north edge) | OK | [TCA] §11.1 p.33 |
| ADDR | Connect directly to VCCP or GND; L = 0x20, H = 0x21 | U2 on GND (0x20), U6 on +3V3 (0x21) | OK | [TCA] Table 5-1 p.3, Table 8-3 p.25 |
| RESET | "Connect to VCCI through a pull-up resistor, if no active connection is used"; VIH 0.7·VCCI to 5.5 V | Tied directly to +3V3 | **to check by the user (U9)** | [TCA] Table 5-1 p.4, §8.3.4 p.20–21 |
| Power-on reset | Reset is released at VPORR ≤ 1.4 V. Re-arming needs VCCP < VPORF (0.7 V min) for ≥ 1 µs; ramp 0.1–2000 ms; at power-on every P port is an input | +3V3 follows DUT_5V. At reset the EN pull-downs keep every port off | OK | [TCA] §8.4.1 p.21, Table 10-1 p.31, Table 5-1 p.3 |
| INT | Open drain, pulled up to VCCI or VCCP | R8 10k to +3V3, wired-OR with the INA226 alerts, through Q3 | OK | [TCA] §8.3.3 p.20 |
| P port driving EN | IOH ≤ 10 mA; VOH ≥ 2.6 V at −8 mA (VCCP 3 V) | 0.33 mA into the 10k pull-down | OK | [TCA] §6.3 p.5, §6.5 p.7 |
| P port inputs | Resistors needed on inputs that may float (Fig. 9-1 note D) | FLT_N has 10k up; RST_IO/BOOT_IO have 100k up; EN has 10k down | OK | [TCA] Fig. 9-1 p.28 |
| RST_IO / BOOT_IO levels | VIH = 0.7 × VCCP = 2.31 V, VIL = 0.99 V | 1k from the header. A DUT with 1.8 V I/O holds the pin at ≈ 1.85 V, which reads as indeterminate. The TCA6408A has no interrupt mask, so a noisy pin can raise INT | check | [TCA] §6.3 p.5, §8.3.3 p.20 |

Tying RESET directly to +3V3 gives the same static level as a pull-up, and the pin draws ≤ 1 µA. The only thing lost is a hardware reset path. Recovery still works by bus clear or by cycling DUT_5V (POR), and a POR leaves every port off.

### U3 AP2114H-3.3TRG1 (1 A LDO, SOT-223)

| Reference element | Datasheet / guide | Ours | Verdict | Source |
|---|---|---|---|---|
| Pinout SOT-223 (H) | 1 GND, 2 VOUT (tab), 3 VIN; the fixed SOT-223 part has no EN | AMS1117-3.3 symbol (1 GND, 2 VO, 3 VI) on SOT-223-3_TabPin2. Not to be confused with HA: 1 VIN, 2 GND, 3 VOUT | OK | [AP] Fig. 2 p.2, Pin Descriptions p.3 |
| VIN | ROC 2.5–6.0 V, abs max 6.5 V | 5.0–5.24 V | OK | [AP] p.7 |
| CIN | 4.7 µF (typical application) | C2 22 µF 0805 X5R 25 V (≈ 10–13 µF at 5 V), ≈ 3 mm from VIN, on a +5V island with 2 vias | OK | [AP] Fig. 47 p.25, p.12 |
| COUT | "Stable with 4.7 µF flexible cap: ceramic, tantalum and aluminum electrolytic"; no ESR window, no maximum | C3 22 µF 0805 X5R (≈ 13–16 µF at 3.3 V) at the tab, plus ≈ 40 × 100 nF and the FB2 branch | OK | [AP] p.1, Fig. 47 p.25 |
| Dropout | 450 mV typ / 750 mV max at 1 A; Fig. 32 shows ≈ 0.15–0.18 V at 0.4 A | At 0.39 A: ≈ 0.18 V typ, 0.29 V max. It regulates down to +5V ≈ 3.6 V | OK | [AP] p.12, Fig. 32 p.21 |
| Output current | IOUT(MAX) ≥ 1 A | 0.35–0.39 A | OK | [AP] p.12 |
| Dissipation | — | (5.0–5.24 − 3.3 V) × 0.35–0.39 A = **0.60–0.76 W** | — | — |
| Thermal resistance | θJA 128 °C/W ("no heatsink"); θJC 50.9 °C/W. Fig. 37 (TO-252, θJC 35, 100 mm² copper, still air) works out to ≈ 70–90 °C/W | design.py claims 60–70 °C/W from a 7.2 × 4.5 mm F.Cu island with 6 vias into the In2 +3V3 plane. Diodes gives no such figure for SOT-223 | check | [AP] p.7, p.12, Fig. 37 p.22 |
| Junction temperature | Abs max TJ 150 °C; OTSD 160 °C typ (no minimum, 25 °C hysteresis); TA ROC −40 to 85 °C; Note 4 asks for ≥ 30 % thermal margin | At 40 °C local air: 116–137 °C at 128 °C/W, 100–116 °C at 100 °C/W, 82–93 °C at 70 °C/W. Note 4's margin needs θJA ≤ 109 °C/W at 0.76 W | check | [AP] p.7, p.12, Note 4 p.22 |
| Start-up | Note 2: "the input voltage must be applied before a current source load is applied" (fold-back limit 50 mA at VOUT = 0); ts 20 µs | +3V3 ramps with its loads already connected (hub, RP2354B, about 30 µF in total) | check | [AP] p.12 Note 2 |

The datasheet allows this design only if the copper brings θJA under ≈ 100–110 °C/W. On bare copper (128 °C/W) the worst case reaches 137 °C at 40 °C local air. That is inside the 150 °C abs max but fails Note 4's margin and comes within reach of an untoleranced 160 °C shutdown. A shutdown would drop +3V3, reset the expanders and turn every port off. The hub's own ≈ 1.1 W sits on the same board and raises the local air. Each extra 50 mA of 3.3 V load adds ≈ 0.1 W in U3.

### Q1–Q3 2N7002 (JSCJ) as I²C isolation and level shifters

| Reference element | Datasheet / guide | Ours | Verdict | Source |
|---|---|---|---|---|
| Pinout | 1 G, 2 S, 3 D | KiCad 2N7002: 1 G, 2 S, 3 D | OK | [CJ] p.1 |
| Topology | Gate to the lowest supply VDD1, source to the lower-voltage section, drain to the higher. VDD1 = VDD2 is allowed (isolation only) | G on the board's +3V3; S on the board side (SDA, SCL, INT with 4.7k / 4.7k / 10k); D on the lead side (the node's pull-ups) | OK | [AN] §2.3 p.10, §2.3.4 p.11 |
| Body diode | The drain–substrate diode pulls the source side low first ("State 3") | The source (board) side is the anode and the drain (lead) side the cathode. A low on the lead conducts to the board. With the board off (S at 0 V, D at 3.3 V) the diode is reverse-biased, so it blocks | OK | [AN] p.10–11 |
| Vth vs gate drive | "a threshold voltage of about 1 Volt below the lowest VDD1"; requirement table: VGS(th) 0.1–2 V, RDS(on) ≤ 100 Ω at 3 mA and VGS = 2.5 V | CJ: Vth 1.0 / 1.6 / 2.5 V; RDS(on) specified only at 5 V (7 Ω) and 10 V (5 Ω). With VDD1 at 3.25–3.35 V the rule allows ≤ 2.25 V | check | [AN] p.11, p.13; [CJ] p.2 |
| Off-state isolation | Vth min about 0.4 V with VDD1 ≈ 0 | Vth min 1.0 V; +3V3 falls to 0 V with DUT_5V off | OK | [AN] §2.3.4 p.11 |
| Capacitance | Ciss ≤ 100 pF | Ciss ≤ 50 pF, Coss ≤ 25 pF | OK | [AN] p.13; [CJ] p.2 |
| Current | ID ≥ 10 mA | ID 115 mA; typical saturation ≈ 0.15 A at VGS 3 V | OK | [AN] p.13; [CJ] p.1, p.3 |

At the worst-case Vth of 2.5 V the circuit still closes. When the node pulls low, the body diode drags the source to ≈ 0.6 V, so VGS ≈ 2.65 V turns the channel on and it pulls the source lower. When the board pulls low (VOL 0.4 V), VGS ≈ 2.9 V. With the typical gain, either case leaves a few mV across the FET at ≤ 2 mA. No guaranteed figure exists, so this is a check rather than a fix. All BSS138 sources at JLC are extended parts (C82045 BSS138LT1G: 5.6 Ω at 2.75 V, +$3.07 per order). The basic AO3400A (C20917) has about 600 pF of Ciss, above AN97055's 100 pF.

### FB1, FB2 GZ2012D601TF (Sunlord, 0805)

| Reference element | Datasheet / guide | Ours | Verdict | Source |
|---|---|---|---|---|
| Ratings | 600 Ω ±25 % at 100 MHz; DCR ≤ 0.30 Ω; Ir 500 mA. Derating above 85 °C applies only to parts rated ≥ 1000 mA | FB1 (+5V_MX) ≈ 1–4 mA (the crosspoints section; the old ≈ 70 mA estimate is stale); FB2 (+3V3_CP) 15–45 mA (≤ 9 %) | OK | [GZ] GZ2012 table p.3, rated-current note p.5 |
| DC drop | DCR max 0.30 Ω | FB1 ≤ 1 mV; FB2 ≤ 14 mV (+3V3_CP ≥ 3.24 V with U3 at −1.5 %) | OK | [GZ] p.3 |
| DC-bias Z drop | Not published for the GZ series | At ≤ 14 % of Ir the drop is modest, and the bead's job is attenuation above about 10 MHz | OK | [GZ] p.3, p.10 |
| Low-frequency impedance | Curve: Z ≈ 10 Ω at 1 MHz, X peak ≈ 350 Ω at about 60 MHz, so L ≈ 1 µH below 10 MHz | At the TPS60400's 50–250 kHz FB1 is only ≈ 0.3–1.6 Ω. The isolation design.py claims from "the charge pump's 250 kHz" is small: about 6–10 dB against C27 | justified deviation | [GZ] GZ2012D601TF curve p.10 |
| LC peak, FB2 | — | L ≈ 1 µH with C31 + C32 (4.7 µF 0402 10 V, ≈ 2 µF each at 3.3 V) and 10 × 100 nF, ≈ 5.4 µF in all: f0 ≈ 70 kHz, Z0 ≈ 0.43 Ω, Q ≈ 1.4–2.2. A 30 mA step rings ≤ 20 mV | OK | [GZ] p.10 |
| LC peak, FB1 | — | ≈ 2 µF effective (C21, C24, C27 1 µF; C20, C23 100 nF): f0 ≈ 110 kHz, inside the pump's 50–250 kHz range, Q ≈ 2.4–3.5. The pump's input ripple is small because its −5 V load is µA to mA | check | [GZ] p.10 |

The ferrite on FB1 still isolates +5V_MX from the ports' HF edges and from USB noise; only the "250 kHz" claim in the comment is overstated.

### J101–J401 USB-C CC: R104/R105 … R404/R405, 56k to PORTn_VBUS

| Reference element | Datasheet / guide | Ours | Verdict | Source |
|---|---|---|---|---|
| Rp value | Default USB Power: 56 kΩ ±20 % pulled up to 4.75–5.5 V (or 36 kΩ to 3.3 V, or 80 µA) | 56k 1 % 0603 (C23206) | OK | [TC] §4.11.1 Table 4-24 p.235 |
| Rp pull-up voltage | 4.75–5.5 V. Other voltages are allowed if < 5.5 V and the CC voltage stays in the sink's ranges | PORTn_VBUS ≈ +5V − ≤ 0.12 V. CC across Rd 5.1k ±10 % is 0.36–0.48 V for VBUS 4.75–5.24 V, inside vRd-USB (0.25–0.61 V) | OK | [TC] Table 4-24 p.235, Table 4-36 p.241 |
| One Rp per CC | Separate Rp on CC1 and CC2 | One on each | OK | [TC] §4.5.2.2.7.1 p.175 |
| Source behaviour | Unattached.SRC: "The port shall not drive VBUS" until a sink (Rd) is detected | VBUS, and Rp with it, is on whenever the node enables the port. There is no Rd detection | justified deviation | [TC] §4.5.2.2.7.1 p.175 |
| Advertisement vs limit | Default power is 500 mA for USB 2.0 | IOS min 500–505 mA | OK | [TPS] §10.2.3.2.1 p.23 |

Turning VBUS on without detecting a sink is justified here. The DUTs are wired permanently and the node enables a port only for a known DUT. With the port off, a sink sees neither VBUS nor Rp. With it on, the port behaves like a legacy C-to-A assembly, which Table 4-24 note 1 allows (Rp 56k to VBUS). A DRP DUT sees Rp and takes the sink role. A pure source plugged in back-feeds the port, and the TPS2553-1 reverse comparator latches it off.

Board budget (outside these datasheets): the node limits +5V at ≈ 1.34 A. This board takes ≈ 0.40 A itself (U3 0.39 A, FB1 ≈ 1–4 mA, LEDs), which leaves ≈ 0.94 A for DUTs. Each port's 0.5–0.62 A limit does not protect the node's limit: two DUTs at 0.45 A each would trip the node and drop the whole board. This is the firmware power budget's job.
