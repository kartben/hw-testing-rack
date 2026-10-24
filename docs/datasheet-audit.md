# Datasheet audit: the key ICs against their reference circuits

2026-10-24, before the JLC order. The user asked: "pour les circuits intégrés clés des différentes cartes ... a t on tous intégrés en respectant les schémas de référence dans les datasheets." This file covers the bay node, the power hub, the camera pod and the DATA port (1×); the DATA ×4 v2 has its own audit.

**Method.**
- Each board's circuit comes from its `design.py` (parts, pin nets, values, PCB positions), with pad positions read from the generated `.kicad_pcb`.
- Each IC is compared, point by point, with the manufacturer's datasheet and, for the ESP32-S3 modules, Espressif's Hardware Design Guidelines. The points cover:
  - required external parts and their values;
  - straps and unused pins;
  - decoupling;
  - stability;
  - timing parts;
  - the limits we approach;
  - layout.
- Worst cases used throughout:
  - VBUS / VRACK 29.4 V (28 V EPR + 5 %);
  - the bay node's +5V 5.10–5.39 V (5.24 V nominal);
  - +3V3 3.25–3.35 V;
  - a bay ≤ 2.2 A on +5V ([power-distribution-review.md](power-distribution-review.md)).
- Settled decisions of [review-konnect.md](review-konnect.md) and [pcba-review.md](pcba-review.md) are not re-raised without new evidence.

**Verdicts.**
- **OK**.
- **justified**: a deviation from the reference, with its reason.
- **to fix**: a change is proposed below.
- **to check by the user**: ambiguous, read from a figure, from an unofficial source, or an inference. The user reads the datasheet and answers.
- **bring-up**: measure on the first boards.

"Req." marks a datasheet requirement, "rec." a recommendation.

Datasheets used:
- **ESP32-S3:**
  - WROOM-1/1U v1.8, MINI-1/1U v1.7, ESP32-S3 Series v2.2 (espressif.com);
  - Hardware Design Guidelines, master of 2026-10-12, page numbers as printed (docs.espressif.com).
- **TI:**
  - LMR51625 SLUSF64B (Jan 2025);
  - TPS2660 SLVSDG2G (Dec 2019), which covers the TPS26600;
  - TPS2553D SLVSDL7;
  - INA226 SBOS547C;
  - SN74LVC1G32 SCES219W (rev. Aug 2026).
- **Interface and protection:**
  - NXP TJA1462 Rev 3.0 (12 Feb 2025; the node's rows were read on Rev 1, and NXP's change notice CIN 202109014I says later revisions only tighten specs);
  - ST USBLC6-2 DocID 11265 Rev 5;
  - onsemi FSUSB42.
- **Power:**
  - WCH CH224 V2.0 (the repo cites v2.1, which could not be fetched);
  - Diodes AP2114 (BCD Rev 2.2) and AP2112 DS39724 Rev 2-2;
  - AMS AMS1117 (advanced-monolithic.com).
- **Others:**
  - Worldsemi WS2812B-2020-V6;
  - Cjiang FXL inductor catalogue;
  - AOS AO3400A;
  - discretes from their LCSC datasheets.

## Summary

### To fix

| # | Board | Change | BOM / cost | PCB | JLC cart |
|---|---|---|---|---|---|
| F1 | camera pod | U1 AMS1117-3.3 → **AP2114H-3.3TRG1** (C150716, the node's U2). The AMS1117 is only specified stable with 22 µF *tantalum*; ours is a 22 µF ceramic | +$0.03 a board; one more extended type on the pod's Economic order: +$3.09 | none: same SOT-223 pinout (1 GND, 2 VOUT/tab, 3 VIN), same CPL correction (180°, as C6186). Catalog key `ldo` → `ldo_1a` | BOM re-upload |
| F2 | power hub | R214 (TJA1462 STB pull-down) **10k → 5.1k**. STB's internal pull-up can be 20 kΩ: with 10k a floating GPIO leaves STB at up to 1.10 V, above VIL 0.99 V | C23186, basic, already on the board: $0 | none | BOM re-upload |
| F3 | bay node | **U7 SN74LVC1G32: hysteresis on PC_DET.** The laptop's VBUS rises in ≥ 0.2 ms through 10k/18k (≈ 50 µs/V), against the gate's 10 ns/V input limit; the datasheet warns of oscillation, so MUX_SEL can chatter on plug and unplug. 150k from MUX_SEL (U7.4) to PC_DET (U7.1): ≈ 0.14 V of hysteresis | +1 basic type (C22807, 150k 0603): +$1.55 (Standard PCBA counts every type) | one 0603 added, re-route | Gerbers + BOM + CPL |
| F4 | bay node | **U12/U13 (the camera SPI's USBLC6): 100 nF on their VBUS pin**, which now reaches +3V3 through 5–11 mm of thin track and no capacitor (ST recommends 100 nF) | C14663, basic, already on the board: ≈ $0 | one 0603 added | Gerbers + BOM + CPL (with F3) |
| F5 | node and hub | **Burn the eFuse `DIS_USB_OTG_DOWNLOAD_MODE`** at first flash. In USB-OTG download boot the ROM drives IO40 high and IO39/IO38 low. On the node, IO40 is DUT_FLT_N: it fights the TPS2553's open drain if the DUT faults then. On the hub it is PD_SCL: it back-feeds an unpowered CH224A, which I2C_PU exists to avoid. We flash over UART0 and USB-Serial-JTAG, which stay | none | none | none (provisioning step, irreversible) |
| F6 | hub, node | **Notes that are wrong or stale** (comments, schematic notes, docs; no BOM). Hub: see the list after this table. Node: see the second list | none | none | none |

F6, the hub's notes:
- The IMON filter is τ = (18k + 1k) × 47 nF ≈ **0.9 ms, not 47 µs**: the IMON pin is a current source into 18k.
- The CH224A has no source-PDO registers: 0x60–0x8F and AVS/PPS 0x51–0x53 are "Only CH224Q", and the CH224A takes single-byte transfers only. design.py, power.md and the catalog say the controller reads the PDOs and that the CH224Q is "the same die".
- The buck stops at ≈ 3.8 V (its internal UVLO), not 3.1 V.
- SHDN turns on at ≥ 1 V (TI p. 26), not "above 0.94 V".
- The soft start stays under the current limit only typically: at the corners a row starts in current limit.

F6, the node's notes:
- "1.7 V × 0.4 A" (the LDO) is 1.94 V × 0.4 A ≈ 0.8 W, ≈ 1 W at Espressif's 0.5 A.
- "9 A sat" (L1) is typical; 7.5 A is guaranteed.
- The camera's "≤ 150 mA" is now ≤ 102 mA.
- "TPS2553" is the TPS2553D.
- The old "DUT port" text.
- electronics.md's "5.1k" I²C pull-ups are now 2.2k.
- bay_node.dtsi's "100k" POS_IN pull-down is now 470k.

Optional, recommended by the datasheets (no defect):
- 0 Ω + an unfitted capacitor footprint on each USB pair at the ESP32 (Espressif).
- A notch in the rear edge so each module's antenna sits over air: Espressif "strongly recommends" it, and the links have ≥ 30 dB of margin ([architecture.md](architecture.md)).
- The hub's IMON 47 nF moved next to the ADC pins.
- The 100 nF nearest each 3V3 pin.
- The hub's C117 next to the TJA1462's VIO pin.

Firmware, no hardware change:
- **Hub budget margin:** 10 % → 15 %, or a per-row IMON calibration at bring-up. The TPS26600's IMON gain is 72–85 µA/A, so the error alone reaches −8 %, ≈ −11 % with the resistor and ADC.
- **EPR detection:** decide on EPR from the CH224A's register 0x09 bit 5.
- **28 V fallback:** on a row's FLT stuck at 28 V, fall back to 20 V. The eFuse's OV falling threshold is 28.5–31.5 V, so a row tripped by a surge can stay off at 28.5–29.4 V.
- **Unused inputs:** enable pulls on the floating ones (node IO3; hub IO3, IO34, IO36–38, IO48).
- **JTAG strap:** never burn `STRAP_JTAG_SEL`, because GPIO3 floats.

### To check by the user

| # | Datasheet | Where | Question | Now | What the answer changes |
|---|---|---|---|---|---|
| U1 | TI TPS2660 SLVSDG2G, https://www.ti.com/lit/ds/symlink/tps2660.pdf | Fig. 55 "Thermal Shutdown Time vs Power Dissipation", p. 32 (also Fig. 26), with §10.2.2 (TI asks a ≥ 30 % margin) | At TA = 85 °C, is the thermal-shutdown time **≥ 15 ms at 17 W** and **≥ 16 ms at 21 W**? | C21–C24 dVdT 47 nF. A 28 V EPR start of four nodes (≈ 450 µF) dissipates ≈ 15.5–16.8 W for 11.4 ms typically, ≈ 21 W for 12 ms at the worst corner (29.4 V, +20 % capacitance, fast dVdT, node load, I_LIM minimum). Read by eye: ≈ 35 ms and ≈ 13 ms | Yes: keep 47 nF. No: **100 nF** (C14663, basic, already on the board, value only), the start drops to ≈ 7–9 W typical, ≈ 14 W worst for 19–24 ms; `HUB_ROW_FLT_BLANK_MS` 25 → 50 ms. Only the 28 V option is concerned: at 20 V (default) the margin is ≈ 15× |
| U2 | Cjiang FXL series catalogue (www.cjiang.com.cn; LCSC C167220) | FXL0630 table, p. 14, column "VW (V) Withstand Voltage": 30 for FXL0630-4R7-M, 75 for -4R7-MV75 | Is VW a limit on the voltage applied across the winding (or at the SW node) in operation, or an insulation test value? | L1 FXL0630-4R7-M on the node and the hub. At 20 V the inductor sees ≈ 15 V, at 28 V EPR ≈ 24 V each cycle plus the SW ringing, ≈ 48 V for microseconds during a TVS-clamped surge | Insulation value: nothing. Operating limit: fine at 20 V; for the 28 V option a 4.7 µH ≥ 60 V part (the -MV75 has the same footprint but isn't listed at LCSC or JLC: consigned, or another part). Field change only |
| U3 | Espressif ESP32-S3 Hardware Design Guidelines, https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/ | §1.3.13 USB, Table 12 "IO Pad Status After Chip Initialization in the USB-OTG Download Boot Mode", printed p. 19 | Does the ROM drive MTDO (IO40) high and MTCK (IO39) / GPIO38 low **only in download boot** (IO0 low), or **at every start-up** while the eFuse is not burned? | eFuse not burned. Node IO40 = DUT_FLT_N, hub IO40 = PD_SCL | Either way F5 removes it. "Every start-up" makes F5 urgent before the first power-up with a DUT or without a charger |
| U4 | WCH CH224 datasheet **v2.1**, https://www.wch-ic.com/downloads/CH224DS1_PDF.html (the repo's reference; we read V2.0) | Table 5-3 (I²C registers); §7.1 vs §8.1.1 | (a) Are 0x60–0x8F (source PDOs) still "Only CH224Q" in v2.1? (b) Is the CH224A's VBUS pin rated 32 V (§8.1.1, as VHV) and not 3.8 V (V2.0's §7.1, which looks like CFG1's figure)? | (a) the firmware reads PDOs and falls back to trying 28 V when none show; the notes say they are read. (b) VBUS tied to VHV as Table 4-1 requires | (a) Yes: F6's note fix stands, and the firmware uses 0x09 bit 5. No: the notes stay. (b) 32 V: nothing. 3.8 V: ask WCH, since Table 4-1 requires the tie |
| U5 | XINGLIGHT XL-2835UWC-02 datasheet (LCSC C2843876; the PDF didn't download, we used the catalogue: 60 mA test current, 200 mW) | absolute maximum ratings, IF derating curve | Is the continuous forward current at 85 °C **≥ 26 mA**? | 18–26 mA per LED (100 Ω 0805 from CAM_5V) | Yes: nothing. No: R1–R4 100 → 120 Ω (value only) |

### Bring-up checks

| Board | Check | Why | If it fails |
|---|---|---|---|
| node | **Temperatures at the worst bay load:** U1 (≈ 1.1–1.3 W), U9 (TPS2553D: ≤ 105 °C junction above 1.2 A, RθJA 183 °C/W), U2 (0.3 W average, ≈ 1 W Wi-Fi peaks) | datasheet limits from θJA only | more copper, or a lower DUT limit |
| node | **The WROOM-1-N8R8's ambient ≤ 65 °C** in a closed bay | the R8's rating (85 °C with PSRAM ECC, which costs 1/16 of the PSRAM) | PSRAM ECC |
| node | **INA226 against a meter** at 0, 0.1 and 1 A with the buck in PWM | the 1.1 MHz buck sits in the INA226's 2nd-harmonic band (§6.4.2) | 2 × 10 Ω + 100 nF input filter (layout change) |
| node | **AP2114 start-up** into ≈ 50 µF against its 50 mA short-circuit foldback | slower start, should not block | — |
| node | **D4 WS2812B colour and brightness at +3V3** | VDD 3.3–5.3 V, and +3V3 can sit at 3.25 V | VDD from +5V through a B5819W |
| hub | **AP2112K temperature** under sustained Wi-Fi | ≈ +88 °C at 0.3 A sustained (H11) | — |
| hub | **A row's OUT on a scope during a hard short at 28 V** | the output Schottky sits at the connector, ≈ 35 mm from OUT (TI wants it close) | a Schottky at OUT |
| hub | **+5V_BUCK load step** | COUT's effective capacitance is an estimate | — |
| both | **RSSI with the antenna over bare FR4** | Espressif's antenna placement | the edge notch |

## Bay node

### U3 ESP32-S3-WROOM-1-N8R8

| Reference element | Ours | Verdict | Source |
|---|---|---|---|
| Land pattern, pin map (req.) | 40 pads at 1.27, EP 3.9 mm; all 41 pads carry design.py's nets; IO3/5/6/35/36/37/45/46 open | OK | WROOM-1 Tab 3-1 p. 11–12, Fig 11-1 p. 45 |
| Supply 3.0–3.6 V, ≥ 0.5 A (req.) | AP2114H-3.3 (1 A); 0.5 A for the module + ≈ 25 mA | OK | WROOM-1 Tab 6-2 p. 27; HDG §1.3.2 p. 5 |
| 3V3 decoupling 22 µF + 0.1 µF (rec.) | C13 22 µF 3.2 mm from pin 2, C14 100 nF 5.9 mm, a via to In2 at the pin | OK | WROOM-1 Fig 9-1 p. 41 |
| EN RC 10k + 1 µF (rec.), never floating (req.) | R6 10k + C15 1 µF: 0.75 VDD after 13.9 ms ≫ 50 µs | OK | WROOM-1 Tab 4-6 p. 16; HDG §1.3.3 p. 8 |
| GPIO0 pull-up (rec.), no large C (req.) | R7 10k, SW2, no capacitor | OK | HDG §1.3.9 p. 15 |
| Straps GPIO46 / 45 / 3 | open: SPI boot (IO0 = 1) or Joint Download (IO0 = 0); VDD_SPI 3.3 V; JTAG strap ignored while STRAP_JTAG_SEL = 0 | OK | WROOM-1 Tab 4-1..4-5 p. 13–16 |
| Octal PSRAM pins GPIO33–37 (req.) | IO35–37 open; IO33/34 not brought out | OK | WROOM-1 Tab 3-1 note b p. 12 |
| IO47/IO48 domain | 3.3 V on R8 | OK | Tab 3-1 note c |
| JTAG pins IO39–42 | INA_ALERT_N, DUT_FLT_N, DUT_EN, POS_OUT: debugging over USB-Serial-JTAG; reset states held by R17/R18/R20 | OK | S3 Tab 2-1 note 7 p. 17 |
| Pins in USB-OTG download boot | IO40 driven high, IO39/38 low | **to fix** (F5), **to check** (U3) | HDG Tab 12 p. 19 |
| USB series R / C reserved (rec.) | none; full speed through the FSUSB42 and USBLC6 | justified (electrically 0 Ω, no C) | HDG §1.3.13 p. 18–19 |
| UART0 499 Ω (rec.) | test pads only | justified | HDG §1.3.7 p. 13 |
| SPI series R + C at the module (rec.) | 33 Ω at J6 (source termination of the 50 cm lead), 4 MHz | justified | HDG §1.3.8 p. 13–14 |
| Power-up glitches | IO18 CAN_TXD 60 µs (N13); IO1/2, IO7–14 60 µs low, harmless | OK | S3 Tab 2-2 p. 18 |
| Antenna keep-out (req.) | x 8–56 × y 0–6, every layer copper-free | OK | Fig 11-1; HDG Fig 26 p. 31 |
| Antenna over air (rec.) | bare FR4 | justified (optional notch) | HDG §1.4.7 p. 30–31 |
| EPAD | 48 % paste, solid to a GND island with 8 vias outside the pad | justified | WROOM-1 §9, Fig 11-1 |
| Ambient (req.) | R8: −40…65 °C | bring-up | WROOM-1 §1.2 p. 3 |

### U1 LMR51625YDDCR (5 V buck) and L1

| Reference element | Ours | Verdict | Source |
|---|---|---|---|
| VIN, SW abs max 63 V | 29.4 V; the SMBJ33A clamps at 53.3 V (11.3 A) | OK | §6.1, §6.3 p. 4 |
| EN never floating, ≤ VIN + 0.3 V | VIN/11 (100k/10k): on 11.9–15.1 V (13.5 typ), off 9.8–11.9 V | OK | Table 5-1 p. 3; §6.5 p. 5 |
| FB: RFBT 10–100k, 1 % | 100k/18k → 5.24 V (5.10–5.39 V), no CFF (Table 8-1) | OK | §7.3.2 p. 11–12; Table 8-1 p. 16 |
| L 4.7 µH for 1.1 MHz, 5 V; Isat > 4.5 A peak limit | FXL0630-4R7-M: 7.5 A guaranteed, DCR 33 mΩ | OK | Table 8-1; §8.2.2.4 p. 18 |
| Inductor voltage rating | VW 30 V (-M grade) | **to check** (U2) | Cjiang catalogue p. 14 |
| Ripple 20–60 % | 33 % nominal at 29.4 V, 50 % at the worst corner | OK | Eq 8–9 p. 18 |
| Peak current vs IHS_PK(OC) min 2.9 A | 2.62 A typical, ≈ 2.8 A worst at 2.2 A | OK (thin at the all-worst corner) | §6.5 p. 6 |
| tON-min 70 ns | 136 ns at 29.4 V | OK | §7.3.4 p. 12–13 |
| COUT 22 µF after derating (req.) | 3 × 22 µF 25 V X5R 1206 (≈ 33–40 µF effective, estimate) | OK | Table 8-1 note 1 |
| CIN ≥ 2.2 µF + 0.1 µF at the pins, rated 2 × VIN (rec.) | 2 × 10 µF 50 V + 100 nF 2.6 mm away; 1.7 × VIN, the derated value still ≫ 2.2 µF | justified | §8.2.2.6 p. 19 |
| Bulk 10–22 µF | C1 100 µF / 50 V | OK | §8.3 p. 22 |
| CB 0.1 µF ≥ 16 V | 100 nF 50 V X7R, 3 mm | OK | §7.3.5 p. 13 |
| Layout | islands, In1 GND, FB at the pin (review B7) | OK | §8.4.1 p. 22–23 |
| Thermal | ≈ 1.1–1.3 W at 2.2 A, +55–65 °C | bring-up | §6.4 p. 5 |

### U2 AP2114H-3.3

| Reference element | Ours | Verdict | Source |
|---|---|---|---|
| Pinout SOT-223 (H): 1 GND, 2 VOUT/tab, 3 VIN | as the AMS1117's copper | OK | p. 3 |
| VIN 2.5–6.0 V | 5.10–5.39 V | OK | p. 7 |
| CIN / COUT 4.7 µF ceramic, stable | C11 10 µF; C12 22 µF at the tab, C13 22 µF | OK | p. 1; Fig 47 p. 25 |
| Dropout 450 mV at 1 A | 1.94 V headroom | OK | p. 12 |
| Dissipation (θJA 128 °C/W bare) | 0.3–0.4 W average, 0.9 W at a 0.45 A Wi-Fi peak; tab island + 8 vias | OK (bring-up) | p. 7, p. 22 |
| Foldback 50 mA at VOUT = 0 | ≈ 50 µF to charge | bring-up | p. 8 note 2 |

### U9 TPS2553DDBVR (DUT switch), R19 + U10 INA226

| Reference element | Ours | Verdict | Source |
|---|---|---|---|
| RILIM 15–232 kΩ | 18k → 1338 / 1422 / 1518 mA (min / typ / max) | OK | TPS2553D §9.5.1 Eq 1 p. 15 |
| Continuous IOUT ≤ 1.2 A at TJ ≤ 125 °C, ≤ 1.5 A at TJ ≤ 105 °C | 0.2–0.3 W at 1.4–1.5 A, +37–55 °C | justified (bring-up) | §7.3–7.5 p. 5–7 |
| IN ≥ 0.1 µF close (req.) | C20 100 nF 3.8 mm | OK | §10.2.1.2.4 p. 20 |
| OUT 100 nF + bulk (rec.) | C21 22 µF behind the shunt | justified | §12.1 p. 26 |
| EN, FAULT | R17 100k pull-up (on without firmware); FAULT R18 10k, 7.5 ms deglitch | OK | §7.3; §9.3.3 p. 14 |
| INA226 VS 2.7–5.5 V, 0.1 µF close | +3V3, C22 2.7 mm | OK | INA226 §5.5, §8.4.1 |
| Address, common mode 0–36 V | 0x40; 5.24 V | OK | Table 6-2 p. 18 |
| Full scale ±81.92 mV | 1.638 A on 50 mΩ; the switch's max is 93 % of it; shunt 0.12 W of 1 W | OK | §5.5 |
| Input filter (conditional: transients near 500 kHz harmonics) | none; 1.1 MHz buck ripple ≈ 1 mV p-p (estimate) | bring-up | §6.4.2 p. 14 |
| I²C pull-ups | 2.2k (1.5 mA ≤ 3 mA); SCL abs max VS + 0.3 V: a far board on J7 must pull up to 3.3 V only | OK | §5.1, §5.5 |

### U11 TJA1462AT, D5 PESD2CAN

| Reference element | Ours | Verdict | Source |
|---|---|---|---|
| VCC 4.5–5.5 V, abs max 6 V; VIO variant | +5V 5.10–5.39 V; VIO +3V3 | OK | Table 1 p. 3, Table 5 p. 12 |
| STB low = Normal | tied to GND | OK | Table 4 p. 6 |
| VCC / VIO 100 nF | C23 / C24, 3–4 mm | OK | Fig 12 p. 22 |
| Termination | none (both in the hub, by design) | justified | Fig 12 |
| Bus ±36/+40 V vs PESD2CAN | H7 | justified | Table 5; PESD2CAN p. 5 |

### U5/U6 FSUSB42MUX, U7 SN74LVC1G32

| Reference element | Ours | Verdict | Source |
|---|---|---|---|
| VCC 3.0–4.4 V; control inputs never floating | +3V3; SVC with R39, /OE on GND, SEL from U7 | OK | FSUSB42 p. 3 note 2 |
| Switch I/O ≤ 4.5 V; bandwidth | full speed 3.3 V, HS 0.4 V (B3) | OK | p. 1–5 |
| Truth table vs the modes | matches | OK | p. 2 |
| LVC1G32 5.5 V-tolerant inputs, 0.1 µF | PC_DET 3.2–3.54 V; C19 2.9 mm | OK | SCES219W Table 4-1, §8.3 |
| Δt/Δv ≤ 10 ns/V at 3.3 V | PC_DET ≈ 50 µs/V | **to fix** (F3) | §5.3 p. 6; §7.3.3 p. 11 |

### USBLC6-2SC6 (U4, U8, U12, U13)

| Reference element | Ours | Verdict | Source |
|---|---|---|---|
| VBUS–GND ≥ 6 V breakdown; IRM at 5.25 V | +5V (U4/U8), +3V3 (U12/U13, the lines' level) | OK | Table 2 p. 2; §2.1 p. 4 |
| CBUS 100 nF, short VBUS track (rec.) | C25 3.4 mm, C26 2.9 mm; **U12/U13 none** | OK / **to fix** (F4) | §2.3 p. 5; Fig 18 p. 9 |
| Capacitance 3.5 pF max | SPI 4 MHz behind 33 Ω: negligible | OK | Table 2 |
| Near the connector, flow-through | U4 at J3, U8 at J7, U12/U13 6–7 mm from J6 | OK | §2.3 p. 6 |

### D4 WS2812B-2020-V6, Q4 AO3400A, Q2/Q3 2N7002

| Reference element | Ours | Verdict | Source |
|---|---|---|---|
| WS2812 VDD 3.3–5.3 V | +3V3, 3.25–3.35 V: at the bottom edge | justified (bring-up) | WS2812B-2020 p. 1, p. 3 |
| VIH 0.55 VDD; DIN ≤ VDD + 0.7 V | same rail as the ESP32 | OK | p. 3 |
| 100 nF per LED | C16 4.0 mm | OK | p. 6 |
| DIN series R | R8 33 Ω at the LED end of ≈ 80 mm | justified | p. 6 |
| Reset ≥ 280 µs | 300 µs (DTS) | OK | p. 5 |
| AO3400A VGS(th) 0.65–1.45 V, < 48 mΩ at 2.5 V | ≈ 35–40 mΩ at 3.3 V, ≤ 102 mA; R36 keeps it off at reset | OK | AOS p. 1–2 |
| 2N7002 60 V, ≤ 7 Ω at 5 V | open drain ≪ 1 mA; 100k pull-downs | OK | p. 1–2 |

### Input protection, F1, D6/D7

| Reference element | Ours | Verdict | Source |
|---|---|---|---|
| Q1 SUD50P06: −60 V, ±20 V VGS | 6 mW at 0.64 A; blocks −29.4 V | OK | UMW p. 1, p. 3 |
| D1 BZT52C12 gate clamp | 0.16 mA: VGS −10…−12 V | OK | BZT52 table |
| D2 SMBJ33A: VC 53.3 V at 11.3 A | under U1's 63 V; briefly above C1–C4's 50 V | OK (note) | p. 3 |
| C1 100 µF / 50 V, 105 °C | 56 % of its rating | OK | p. 1 |
| F1 PTC: Ihold 0.50 / 0.35 / 0.31 A at 25 / 60 / 70 °C | ≈ 0.22–0.28 A (pod LEDs ≤ 102 mA + Mega 120 mA): holds to 60–70 °C | OK (N5 resolved) | Ruilon p. 2, p. 4 |
| BAT54S | 2.6 mA fault current, IR ≤ 2 µA | OK (N3) | p. 1–2 |

## Power hub

### U4 ESP32-S3-MINI-1-N8

| Reference element | Ours | Verdict | Source |
|---|---|---|---|
| Land pattern (req.) | KiCad's S2-MINI-1 footprint: the same land as the S3-MINI-1 (60 pads at 0.85, ±7.0 mm, 3 × 3 EP) | OK | MINI-1 Fig 10-1 p. 42, Fig 11-1 p. 45 |
| Symbol pin numbers vs the S3 table (req.) | pads 1–65 follow the S3-MINI-1 table (23/24 USB, 45 EN, 61 EP), net by net | OK | MINI-1 Fig 3-1 p. 10, Tab 3-1 p. 11–12 |
| Supply ≥ 0.5 A (req.) | AP2112K-3.3, 600 mA: 0.51 A = 85 %; input ≈ 4.9 V (4.6 V on console USB) | OK, small margin (H11) | Tab 6-2 p. 27 |
| 3V3 decoupling | C113 22 µF 4.5 mm, C114 100 nF 7.3 mm | OK | Fig 9-1 p. 41 |
| EN RC | R209 10k + C115 1 µF at pin 45 | OK (H13) | HDG §1.3.3 |
| Straps, flash pins | IO3/45/46 open; quad flash internal; IO33/IO35 free on the N8 and used | OK | Tab 3-1 notes a/b, Tab 4-1..4-4 |
| JTAG pins IO39–42 | PD_INT, PD_SCL, PD_SDA, I2C_PU | OK | S3 Tab 2-1 note 7 |
| Pins in USB-OTG download boot | IO40 = PD_SCL driven high | **to fix** (F5), **to check** (U3) | HDG Tab 12 p. 19 |
| ADC1 only (req.: ADC2 not with Wi-Fi) | IMON A–D on IO1/2/4/5, VBUS_SENSE on IO6 | OK | S3 §4.2.2.1 p. 59 |
| ADC range at 12 dB (0–2.9 V calibrated) | IMON 1.40 V/A: 2.25 V at 1.6 A (full scale 2.07 A); VBUS_SENSE ÷11: 2.55 V at 28 V | OK | S3 Tab 5-6 p. 66 |
| ADC filter 0.1 µF at the pin (rec.) | IMON's 47 nF at the eFuse end, 29–99 mm of track | justified (optional move) | HDG §1.3.11 p. 18 |
| USB series R/C (rec.), antenna over air (rec.) | none; bare FR4 | justified | HDG §1.3.13, §1.4.7 |
| Antenna keep-out (req.) | x 7.3–52.7 × y 0–5.25, all layers | OK | Fig 11-1; HDG Fig 26 |

### U1 CH224A, D1, C8

| Reference element | Ours | Verdict | Source |
|---|---|---|---|
| Pinout ESSOP-10 | pads match | OK | V2.0 Table 4-1 p. 3 |
| VHV 3.3–30 V operating, 32 V abs max | 20 V; 28 V EPR: 29.4 V steady, 29.9 V on a vSrcValid transient, 0.1–0.6 V under 30 V | OK; thin but inside at 28 V (settled, power.md) | §8.1.1 p. 14, §8.2.1 p. 15 |
| VBUS shorted to VHV (req.) | tied, behind R5 | OK | Table 4-1 |
| VBUS rating 3.8 V (§7.1) vs 32 V (§8.1.1) | — | **to check** (U4b) | §7.1 p. 12 |
| VHV/VBUS straight to the supply (WCH's guide shorts the series R) | R5 56 Ω + C4 1 µF: the surge filter; 0.1 V typical drop | justified | §6.1.1 p. 9, §7.2.1 p. 12 |
| CFG1 6.8k: 9 V, single-resistor mode with I²C | R6 6.8k 1 % | OK | Table 5-1 p. 5, §5.2.3 p. 6 |
| CC1/CC2 direct, no Rd | direct | OK | §6.1.1 |
| DP/DM to D+/D− (BC1.2 / QC) | open: PD only | justified | §6.1.1 |
| SCL/SDA internal 7–15k pull-ups, VIH 1.5 V | 5.1k to I2C_PU | OK | Table 4-1, §8 |
| Registers: PDOs 0x60–0x8F and AVS/PPS "Only CH224Q"; the CH224A is single-byte only | the notes say the PDOs are read; the firmware reads one byte and falls back | **to fix** (F6 notes), **to check** (U4a) | §5.2.3 Table 5-3 p. 6–7 |
| PG open drain | 10k + the LED: ≈ 1.7 mA (no IOL given) | OK | Table 4-1 |
| D1 SMAJ30A (VRWM 30, VC 48.4 V) | stands off 29.4 V; clamps under the eFuses' 62 V and the buck's 63 V | OK (settled) | MDD p. 2 |

### U11–U14 TPS26600

| Reference element | Ours | Verdict | Source |
|---|---|---|---|
| IN abs max 62 V | 29.4 V | OK | §7.1 |
| I_LIM = 12 / R_ILIM ± 5 % | 7.5k → 1.50–1.70 A | OK | Eq 3 p. 22, EC p. 7 |
| MODE to RTN: active current limit, auto-retry | MODE = GND | OK | Table 1 p. 21–22 |
| RTN to GND (no reverse-polarity protection: allowed) | RTN = GND = PowerPAD | justified (TI p. 26, p. 39) | p. 26, p. 39 |
| UVLO / OVP internal: UV 14.25–15.75 V; OV 31–34 V rising, 28.5–31.5 V falling | to GND | OK (firmware: fall back to 20 V on a stuck FLT at 28 V) | EC p. 7 |
| C_dVdT ≥ 10 nF; t = 8e3 · V · C | 47 nF: 7.5 ms at 20 V, 10.5 ms at 28 V | OK | Eq 1–2 p. 21 |
| Inrush into ≈ 450 µF | 1.11 A typical; at the corners a row starts in current limit | OK (F6 note) | computed |
| Start-up dissipation vs thermal shutdown, ≥ 30 % margin | 20 V ≈ ×15; 28 V ≈ ×3 typical, ≈ ×1.1 at the worst corner and 85 °C | OK at 20 V; **to check** (U1) at 28 V | §10.2.2 Eq 16–18 p. 30–31; Fig 55 p. 32 |
| FLT released after the ramp + PGOOD deglitch (875 + 20 × C[nF] µs) | ≈ 10–13 ms typical, ≤ 19 ms worst, against the firmware's 25 ms blank | OK | p. 9, p. 24 |
| SHDN: pull-down sinks ≥ 10 µA at 0.4 V; pull up to ≥ 1 V | 10k → 0.1 V off; 1.65 V on | OK (F6 note) | EC p. 7, p. 26 |
| R_IMON ≤ 4 V / (I_LIM · gain) | 18k: ≤ 2.6 V worst | OK | Eq 5, 13 |
| IMON "must not have a bypass capacitor" (delay) | 1k + 47 nF: τ ≈ 0.9 ms, against 250 ms polling | justified (F6 note) | p. 25 |
| IMON gain 72–85 µA/A | the budget's 10 % margin | firmware (15 %) | EC p. 8 |
| FLT open drain ≤ 10 mA, 10–100k | 100k; LED from ROW_EN | OK | p. 8, p. 24 |
| C_IN 0.1–1 µF close; OUT ≥ 0.1 µF | 1 µF 50 V 0805 each side, ≈ 4 mm | OK | p. 32, p. 39 |
| Output Schottky close to OUT (rec.) | at the connector, ≈ 35 mm away | justified (bring-up scope) | p. 38–39 |
| PowerPAD vias | 6 tented vias; mask 2.66 × 2.46 vs land 3.3 × 3.3 | OK (minor) | p. 39, p. 52–53 |

### U2 LMR51625YDDCR, L1, D4/D5

| Reference element | Ours | Verdict | Source |
|---|---|---|---|
| VIN 4.3–60 V; EN ≤ VIN + 0.3 V | ≤ 29.4 V; EN 9.3 V | OK | §6.1, §6.3 p. 4 |
| EN 39k/18k vs the internal UVLO 4.0–4.25 V rising, 3.8 V falling | the UVLO dominates | OK (F6 note: off at ≈ 3.8 V) | EC p. 5; §7.4.1 p. 15 |
| FB, L, ripple, COUT, CIN, CB | as the node: 5.24 V, 4.7 µH (30–33 %), 3 × 22 µF, 2 × 10 µF + 100 nF, 100 nF | OK | Table 8-1, §8.2.2 |
| L1 voltage rating | VW 30 V | **to check** (U2) | Cjiang p. 14 |
| tON-min, 96 % max duty | 162 ns; 4.5–4.75 V out on a 5 V contract | OK | EC p. 6 |
| B5819W diode-OR | +5V ≈ 4.75–4.9 V | OK | CJ p. 1 |

### U3 AP2112K-3.3

| Reference element | Ours | Verdict | Source |
|---|---|---|---|
| VIN 2.5–6.0 V; EN tied to VIN | ≤ 5.35 V | OK | p. 3, p. 8 |
| CIN / COUT ≥ 1 µF ceramic | C111 1 µF; C112 22 µF | OK | p. 1–2 note 4 |
| 600 mA; dropout 200 mV at 300 mA | Wi-Fi peaks 0.35–0.5 A | OK | p. 8 |
| θJA 184 °C/W | 0.19 W average; 0.48 W sustained TX → +88 °C | justified (H11, bring-up) | p. 3–4 |

### U6 TJA1462AT, D9, the terminations

| Reference element | Ours | Verdict | Source |
|---|---|---|---|
| VCC 4.5–5.5 V (timing at 4.75–5.25 V) | after D4: ≈ 4.75–4.9 V, 4.65 V at a 0.6 A peak | OK (≈ 0–0.15 V of timing margin, irrelevant at 250 kbit/s) | Table 8 p. 15, Table 9 p. 19 |
| VIO 2.95–5.5 V | +3V3 | OK | Table 8 |
| STB internal pull-up 20–80 kΩ; VIL ≤ 0.3 VIO | R214 10k: up to 1.10 V with the GPIO floating | **to fix** (F2) | §7.3.2 p. 11; Table 8 p. 16 |
| VCC / VIO decoupling | C116 4.8 mm; C117 8.7 mm from VIO | OK (optional move) | Fig 10 p. 22 |
| Bus load 50–65 Ω | 2 × (2 × 56 Ω + 47 nF) = 56 Ω | OK | Table 8; Fig 13 p. 23 |
| D9 PESD2CAN | one at the transceiver | OK (H7) | p. 2 |

### U5 USBLC6-2SC6, J6, D31–D34, VBUS_SENSE

| Reference element | Ours | Verdict | Source |
|---|---|---|---|
| Flow-through; VBUS with 100 nF | C120 1 µF 3.3 mm | OK | Fig 1 p. 1; Fig 18 p. 9 |
| Near the connector (rec.) | 9–10 mm | OK | §2.3 p. 5–6 |
| J6 Rd 5.1k | R212/R213 | OK | USB Type-C |
| BAT54S POS clamps | 2.6 mA, 67 mW in R101–R104 | OK | — |
| VBUS_SENSE 100k/10k + 100 nF | 2.67 V at 29.4 V | OK | — |

## Camera pod

### U1 AMS1117-3.3

| Reference element | Ours | Verdict | Source |
|---|---|---|---|
| Output capacitor: part of the frequency compensation; "22 µF solid tantalum will ensure stability for all operating conditions" | C2 22 µF X5R 1206 ceramic (≈ 15 µF at 3.3 V, a few mΩ of ESR) + C3 100 nF: outside what the datasheet specifies | **to fix** (F1) | AMS1117 p. 4, *Stability* |
| Input capacitor (10 µF tantalum in the typical application) | C1 10 µF X5R 0805 | OK | p. 1 |
| Minimum load 10 mA | the Mega ≈ 120 mA | OK | p. 3 note 5 |
| Dropout ≤ 1.3 V | ≈ 5.0 V in: 1.7 V | OK | p. 1 |
| Dissipation | ≈ 0.23 W | OK | p. 2 |

The AP2114H (F1) is "stable with 4.7 µF flexible cap: ceramic, tantalum and aluminium electrolytic" (AP2114 p. 1), with the same SOT-223 pinout (p. 3, "SOT-223 (H)"); VIN ≤ 6 V. The node made the same change for the same reason (design.py, U2).

### D1–D4 XL-2835UWC-02, R1–R4

| Reference element | Ours | Verdict | Source |
|---|---|---|---|
| 60 mA test current, 200 mW | 18–26 mA each (100 Ω 0805 from CAM_5V, ≤ 66 mW in 125 mW) | OK on the catalogue's figures, **to check** (U5) | LCSC C2843876 |
| Switch | the node's AO3400A, ≤ 102 mA | OK | — |

### J2 (the Arducam Mega)
- The Mega gets 3.3 V, so its MISO is 3.3 V.
- There is no ESD on the pod: the node's U12/U13 sit at the lead's other end, and the lead only plugs in at assembly.

Verdict: justified.

## DATA port (1×)

### U1 USBLC6-2SC6

| Reference element | Ours | Verdict | Source |
|---|---|---|---|
| Flow-through: I/O1 on pins 1/6, I/O2 on 3/4 | D+ 6 → 1, D− 4 → 3 | OK | ST Fig 1 p. 1, layout p. 9 |
| VBUS pin to the supply with a short track; short GND | VBUS with C1 100 nF 4.5 mm away; GND to the pour | OK | §2.3 p. 5, Fig 18 p. 9 |

### J1 USB-C receptacle (the DUT's source)

| Reference element | Ours | Verdict | Source |
|---|---|---|---|
| Rp 56 kΩ to 5 V on CC1/CC2: "Default USB Power" | R1/R2 56k to VBUS | OK | USB Type-C, Rp values |
| Cold socket: VBUS only after a sink attaches | VBUS follows the node's TPS2553, enabled by the firmware; no CC detection | justified: the DUT cable stays plugged in the drawer, and the switch limits a short to ≈ 1.5 A | USB Type-C spec, source VBUS on attach |
| ≥ 120 µF on a downstream port (USB 2.0, hot plug) | 10 µF + 100 nF here, 22 µF on the node's DUT_5V | justified: the droop stays behind the current-limited switch | USB 2.0 spec, downstream port VBUS capacitance |
| SBU, shield | SBU open, shield to GND | OK | — |
