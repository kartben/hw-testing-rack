# Schematic review, 2026-10-25

A full pass over the schematics on `main` at 3578ee2: bay node, power hub, DATA port (1×), DATA ×4 v2,
camera pod, and the leads between them.  It follows the [datasheet audit](datasheet-audit.md) and
its [DATA ×4 v2 part](datasheet-audit-data-x4-v2.md) and lists only what is new.

**Method.**  Each board went through:
- the `schematic-analyzer` skill: overview, a full query of every part, the I²C and USB patterns, net traces;
- a `kicad-cli` netlist and ERC: 0 violations on every board, and no single-pin nets;
- the `ee-datasheet-master` skill: page-cited reads of the datasheets named below;
- a pin map check of every IC and connector against LCSC's EasyEDA symbols.

The schematics match their `design.py` net by net.  Every cross-board link lands on the right
net with the documented leads: rows pin n ↔ 7−n, PH-8 leads pin n ↔ 9−n.  No I²C address
collides on the node's bus:

| Address | Device |
|---|---|
| 0x40 | the node's INA226 |
| 0x41, 0x43, 0x44, 0x45 | DATA ×4's INA226s |
| 0x20, 0x21 | TCA6408A |
| 0x38 | TCA9534A, logic variant only |

Nothing in this review changes a footprint.

## To fix

| # | Board | What | Evidence | Change |
|---|---|---|---|---|
| S1 | bay node (and every POS link) | **POS_IN can float high.** <ul><li>The upstream node's POS_OUT (IO42) and the hub's POS outputs (IO10–13) have no pull at reset (ESP32-S3 Series v2.2 Table 2-1 p. 17). They float until the firmware drives them: ROM, bootloader, download mode, an early crash.</li><li>POS_IN is then held only by R29, 470k.</li><li>Against it, the reverse leakage of the BAT54S clamps' upper diodes (D6 here, D7 or the hub's upstream) works partly against their lower diodes.</li><li>The hongjiacheng BAT54S guarantees IR only at 25 V, 25 °C: 2 µA (Rev 2.0 p. 2).</li><li>Fig. 2 (typical) gives ≈ 0.2 µA at 25 °C and ≈ 25 µA at 100 °C, which interpolates to ≈ 2–3 µA at 65 °C.</li><li>Net of the opposing diodes, that is roughly 0.5–1 V on POS_IN. VIL is 0.25 × VDD ≈ 0.81 V (Table 5-4 p. 65), so there is no margin.</li></ul> | BAT54S Rev 2.0 p. 2, ESP32-S3 Series v2.2 pp. 17, 65 | **R29 470k → 150k.** <ul><li>Driven high through R30 + R28 (20k): 3.25 × 150/170 = 2.87 V, above VIH (0.75 × VDD).</li><li>It then holds POS_IN under VIL with ≈ 5 µA net.</li><li>Same part type as audit F3 (C22807).</li><li>The `design.py` note "the next node's 470k keeps POS_OUT low before firmware" changes with it.</li></ul> |
| S2 | DATA ×4 v2 | **Port 5 against the co-processor's D+ pull-up at hub reset.** <ul><li>The USB2517I samples PRT_DIS_P5 (pin 12, = the RP2354B's D+) when RESET_N rises (DS00001598C Table 5-1 p. 10).</li><li>The RP2354B shares +3V3 and is not held in reset, so TinyUSB's pull-up can come up before RESET_N does (R2/C6, τ 10 ms).</li><li>Audit fix 6 (a 140 ms supervisor) makes that certain.</li><li>If one high line disables the port (audit U3), the co-processor is lost at every power-up.</li></ul> | USB2517 DS00001598C p. 10; RP2350 DS Table 1683 p. 1336 | Depends on **R1** below. If yes: a 1N4148WS (C2128) from CP_RUN (anode) to HUB_RST_N (cathode), so the RP2354B is held in reset while the hub is (RUN ≈ 0.55–0.6 V < VIL 0.8 V). Land it with fix 6. |
| S3 | bay node | **AUX J5 and ROW OUT J2 take the same plug.** <ul><li>Both are S6B-PH-SM4-TB, on the same edge, 22 mm apart.</li><li>On a row's last node J2 is empty but live: J2.6 = VRACK.</li><li>An AUX lead pushed into J2 puts 20/28 V on its BOOT wire to the DUT.</li><li>The reverse (a row jumper in J5) trips the row's eFuse.</li></ul> | `rack.yaml` aux / pwr_y; `design.py:60` | Next revision: give AUX another pin count or series. Until then: a warning in the assembly notes and a blanking plug on each row's last J2. |
| S4 | power hub | **ON LED resistors R41–R44 run at 75 % of their rating.** 10k 0603 (1/10 W) on the row output: at 29.4 V that is ≈ 2.7 mA and ≈ 75 mW, twice every other front LED's current. | BOM; VRACK 29.4 V worst | **10k → 18k** (C25810, already on the board): 1.4 mA, 37 mW at 28 V. Value only. |
| S5 | bay node | **AUX J5 has no ESD and no level protection**, though it ends in flying leads to the DUT. It is the only hand-plugged connector without an array. The ESP32-S3 is rated HBM ±2 kV (p. 69). A 5 V DUT UART injects ≈ 1.1 mA through 1k. | ESP32-S3 Series v2.2 pp. 65, 69 | **Question Q1** below: 2 × USBLC6-2SC6 (already on the board) on TX, RX, RST, BOOT, or a documented "3.3 V DUTs only". |
| S6 | bay node, camera pod | **The Mega draws up to 317 mA, not the ≈ 120 mA the notes assume** (Arducam's spec, R7). <ul><li>CAM_5V then carries ≈ 317 + 115 mA (LEDs) ≈ 0.43 A through F1, a 0.5 A PTC (C20799) whose hold current falls to ≈ 0.31 A at 70 °C: it can trip warm.</li><li>The pod's LDO drops ≈ 1.6 V at 317 mA: ≈ 0.5 W, ≈ +65 °C over the pod's air in SOT-223 (AP2114H θJA 128 °C/W, thermal shutdown 160 °C): ≈ 100 °C at a 35 °C ceiling, inside its rating but warm.</li></ul> | Arducam spec (user); RUILON SMD1206P050TF / P075TF; AP2114 datasheet p. 7 | **F1 0.5 A → 0.75 A** (SMD1206P075TF, C20987, same 1206 footprint, 1.5 A trip).  Pod LDO: keep it, with all the copper its tab can get; bench-measure the tab at full capture.  The notes' "≈ 120 mA" (node and pod `design.py`, `electronics.md`) go to 317 mA max. |

Firmware:
- **EPR status bit.** The CH224A's EPR status is register 0x09 **bit 4** (V2.1 p. 6). The driver already uses BIT(4); the audit said bit 5, fixed here.
- **DUT_5V discharge.** The TPS2553D has no output discharge (SLVSDL7), so DUT_5V decays through the load only. Check that the node's `bay power off/on` waits, as `ports.c` does for the DATA ×4 ports.

## To check by the user

Each row names the page and the question; the answer settles the change.

| # | Datasheet | Where | Question | What the answer changes |
|---|---|---|---|---|
| R1 | Microchip USB2517 DS00001598C, https://ww1.microchip.com/downloads/en/DeviceDoc/00001598C.pdf | Table 5-1 p. 10 (PRT_DIS_Px) | Is a downstream port disabled when **only D+** is high as RESET_N rises? (Extends the v2 audit's U3.) | Yes: S2's diode. No: nothing. |
| R2 | H5VU25UC, LCSC Rev 2.0 | function diagram p. 1 | Is pin 3 internally **unconnected**? The diagram shows 1, 2, 4, 5 to the steering diodes and 8 to the TVS anode. | Yes: our GND on pin 3 is harmless. Only the "tied inside to 5, 4, 2, 1" wording in `catalog.py` and `electronics.md` goes. |
| R3 | WCH CH224 **V2.1** (Chinese), https://www.wch-ic.com/downloads/CH224DS1_PDF.html | §5.2.3 pp. 6–7, Table 5-3 | (a) Does the CH224A fill 0x60–0x8F (source PDOs)? V2.1 no longer marks them "Only CH224Q". (b) p. 7 says SRCCAP is readable when the adapter is "less than 100 W". Is it readable with our default **100 W** charger? | (a) + (b) yes: reword audit F6 and keep the firmware. (b) no: the 28 V fallback is the normal path; test it at bring-up. |
| R4 | WCH CH224 V2.1 | §5.2.3 p. 5 | The 7-bit address is "0x22 or 0x23", with no selection rule. Which one does a CH224A in single-resistor mode use? | 0x22: nothing (`power_hub.dtsi:203`). 0x23 or either: change the reg or probe both. An I²C scan at bring-up also settles it. |
| R5 | WCH CH224 V2.1, or ask WCH | §8.1.1 p. 13 (CC −0.5 to 32 V; no ESD rating anywhere) | What is the CC pins' HBM / IEC 61000-4-2 rating? | ≥ 2 kV HBM: nothing (J1 sits at the box's rear, rarely plugged). Lower or unknown: a low-capacitance TVS on CC1/CC2, ≥ 32 V working. |
| R6 | XINGLIGHT XL-2835UWC-02, https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/2402181507_XINGLIGHT-XL-2835UWC-02_C2843876.pdf | p. 5 (derating), p. 7 (pad drawing) | (a) Will the camera pod's ambient stay ≤ 75 °C? Derating is ≈ 25 mA at 85 °C, and a low-Vf bin draws up to ≈ 28 mA. (b) Is the large 2.2 mm pad the cathode? | (a) Yes: keep 100 Ω and fix the docs (≤ 115 mA for four). No: 120 Ω. (b) No: swap the footprint's pads. Answers audit U5. |
| R7 | Arducam Mega (B0434) | — | **Answered 2026-10-25 by the user:** VCC 3.3 or 5 V; current max 69 mA idle, **317 mA working** (1.58 W: the figure is at 5 V).  Still open: what it draws on **3.3 V** while capturing (a bench reading). | Same ≈ 317 mA (internal linear regulators): S6 as written.  ≈ 480 mA (an internal buck, constant power): the pod's LDO goes to ≈ 0.75 W, too hot in SOT-223; feed the Mega from CAM_5V instead (R35 fitted, LDO DNP). |
| R8 | — (measure) | DATA lead from the BOM (AliExpress, `rack-bom.csv:205`) | Conductor gauge: 24 AWG ≈ 0.51 mm, 26 ≈ 0.40 mm? J7.1 carries up to 1.5 A, and JST PH's 2 A is for #24 only. | 26/28: crimp our own PHR-8 leads in 24 AWG, or lower the TPS2553 limit. |
| R9 | — (try) | `electronics.md` claims a PH-6 plug cannot enter an S8B | Does a PHR-6 enter a spare S8B-PH-SM4? | Yes: add it to S3's warning. |
| R10 | hongjiacheng BAT54S Rev 2.0 (LCSC C7420333), https://www.lcsc.com/datasheet/lcsc_datasheet_2310171613_hongjiacheng-BAT54S_C7420333.pdf | p. 1 function diagram (BAT54, A, C, S side by side) | Is the BAT54S a series pair, pin 1 anode, pin 2 cathode, pin 3 the junction? That is our reading of the figure, and LCSC says "Series Connection"; its EasyEDA symbol names the pins "K1, K2, A" instead. | Yes: nothing (our symbol on the hub and the node's D6/D7). No: the clamps short every POS line to GND; another series BAT54S. |

**Answered here:**
- **Audit U4(b).** The CH224A's VBUS is rated 32 V (V2.1 §7.1 p. 11, §8.1.1 p. 13); V2.0's 3.8 V was CFG1's.
- **The audit's reset-state row** is now cited: GPIO7/12/14/41/42/48 have no weak pull at reset (Table 2-1 pp. 16–17), so the node's 100k pulls are uncontested.
- **Audit F3, F4, F5** are confirmed against the netlist.

## Justified

| Board | Point | Why it stands |
|---|---|---|
| hub | CH224A over-voltage reset at 32–34 V on VHV (§8.2.1 p. 14) | A surge past R5/C4 restarts the rack, not just stresses the part. The 29.9 V worst steady case keeps the margin. |
| hub | CH224A I²C high level listed as 1.5–3.3 V, +3V3 up to 3.35 V | CFG2/3 accept 3.3 or 5 V levels (§5.2.2 p. 5), 6.5 V absolute (p. 13). |
| hub | CAN split terminations: 2 × 47 nF at one point | NXP characterises 4.7 nF (TJA1462 Rev 3.0 Table 9) and gives no limit. A scope look at bring-up. |
| hub | LMR51625 input caps, 2 × 10 µF 50 V for 29.4 V (TI suggests ≈ 2 × VIN, p. 19) | Two of them stay well above the 2.2 µF minimum after DC bias. |
| node | PC_DET into IO13: 3.54 V at a 5.5 V VBUS, limit VDD + 0.3 = 3.55 V (p. 65) | Within. With the node off and a laptop plugged in, ≈ 0.4 mA flows into the dead rail. |
| DATA ×4 v2 | No ESD on CC; RESET_N/BOOT_N on the header without ESD | CC sees only 56k to the port's VBUS. If audit fix 7 takes RESET_N/BOOT_N, the base variant keeps that H5VU25UC fitted. |
| DATA port, node | USBLC6's VBUS pin on switched 5 V | A self-powered DUT pulling D+ high can back-feed ≈ 1–2 mA into DUT_5V when it is off. This matters only if the firmware reads DUT_5V to judge "off". |
| camera pod | AP2114H (audit F1) | <ul><li>Order the **AP2114H**, never the HA: the HA's SOT-223 pinout differs (p. 3).</li><li>Its input is rated 6.5 V absolute against the AMS1117's 15 V.</li><li>See bring-up.</li></ul> |

## Bring-up, added

- **DATA ×4 v2:** cold-start 20 times and check that the co-processor enumerates every time (S2).
- **Camera pod:**
  - Hot-plug its lead and scope CAM_5V: it must stay under 6.0 V for the AP2114H.
  - Check that the pod starts with its LEDs and the Mega on.
  - Scope MISO at the node's U3. If it rings, add 33–47 Ω at the pod's driver next revision.
- **Hub:** run an I²C scan for the CH224A's address (R4).
- **I²C rise time:** measure on a DATA ×4 at the end of its 45–50 cm lead. Above 300 ns, run the bus at 100 kHz.
- **CAN:** a scope look at the common mode with the split terminations.

## Docs fixed with this review

- `datasheet-audit.md`:
  - EPR is bit 4, not bit 5;
  - U4(b) answered;
  - the DATA port's VBUS is on from power-up, not "enabled by the firmware".
- `electronics.md`:
  - the node's I²C pull-ups are 2.2k;
  - J7 has two GND pins, not three;
  - a camera lead in J7 meets D− with GND and D+ with SCK;
  - the v2 co-processor no longer has an LDO.
- `rack.yaml`: the row cable labels say pin n ↔ 7−n, not 1:1.

**Still open, with their boards' next change:**
- `bay-node/design.py`:
  - the docstring calls J5 vertical, but it is side entry;
  - the camera note says "its own AMS1117" (update with audit F1);
  - the POS note changes with S1.
- `data-port-x4-v2/catalog.py` says "SMD pin header"; the headers are THT.
- `electronics.md`:
  - the bay node's cost paragraph still names the merged values "I²C 5.1k, AUX VREF 33 Ω";
  - "22 k Rp → 1.5 A" for the DUT port.
- `data-port-x4-v2-6l`: the folder is still in the hardware CI matrix (`hardware.yml:35`), `rack.yaml:286` and two docs.

## Not checked

**Datasheets not read:**
- PESD2CAN: Nexperia blocked the download.
- SMAJ30A, KPA-3010, AP2112, FSUSB42, LVC1G32, TPS60400, TCA9534A: their audit readings are kept.
- The CH446 manual: its pin map was checked through EasyEDA only.
- Espressif's Hardware Design Guidelines Table 12 (audit U3).
- Samsung's DC-bias curves.

**Other:**
- Layout: ESD placement, decoupling distances, L1 cut-outs.
- Live JLC stock.
- The physical leads' mapping and capacitance.
- USB HS integrity through the node's muxes and the PH lead.
