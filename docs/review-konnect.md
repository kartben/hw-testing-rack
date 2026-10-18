# Board review with Konnect (rev 0.2 → 0.3)

Review of the two rev 0.2 boards (`electronics/bay-node`, `electronics/power-hub`, commit
`da40db9`) with the Konnect MCP server (0.13.0, KiCad PCM plugin) against a
live KiCad 10.0.7, in the light of Fabio's review of v0.1.  Done on 2026-10-16; the fixes below
make rev 0.3.

**How it was checked.** Konnect's checks run on the files on disk: `run_erc` / `run_drc`
(kicad-cli, zones refilled, schematic parity), `audit_manufacturing` (JLCPCB DFM),
`score_placement`, `check_schematic_overlaps`, `render_schematic_png`, `get_component_pads`,
`export_svg` per copper layer.  `get_board_stackup` and `query_traces` need the live board (the bay
node was open in KiCad, reloaded from disk first).  Track widths, lengths, USB pair coupling and
zone fills were measured with a read-only pcbnew script on copies of the boards.  Nothing was
edited or saved from KiCad: every fix below is in the generator (`design.py`, `tools/pcbgen.py`)
and the boards were regenerated and re-routed.

Severity: **High** = would fail or overheat in use · **Medium** = works, but below what a
reviewer would accept for a board that gets ordered · **Low** = cosmetic / documentation ·
**OK** = checked, nothing to do.

## Summary

| # | Board | Severity | Finding | Status |
|---|---|---|---|---|
| H1 | hub | High | 24 V input path in 1.5 mm tracks for up to 7.3–8 A | fixed |
| H2 | hub | Medium | eFuse exposed pads without thermal vias | fixed |
| H3 | hub | Medium | eFuse input/output caps 9 mm from their pins | fixed |
| H4 | hub | Medium | no stackup / finish in the board | fixed |
| H5 | hub | Low | B.Cu GND pour voids below the eFuse row | open (optional) |
| B1 | bay | Medium | no stackup / finish in the board (KiCad default 3 × 0.48 mm, "None") | fixed |
| B2 | bay | Medium | AMS1117 tab has no copper to spread up to ~0.7 W | fixed |
| B2b | bay | Low | In2 `+5V` pieces cut off by In2 tracks get removed (copper balance) | fixed |
| B3 | bay | Medium | USB pairs not fit for High-Speed pass-through (classic mode) | fixed (hand-routed) |
| B4 | bay | Medium | INA226 Vin− tapped ≈ 2.8 mm down the load path (≈ 4–5 % gain error) | fixed (Kelvin footprint) |
| B5 | bay | Low | "PC" and "AUX" silkscreen over pads (5 warnings) | fixed |
| B6 | bay | Low | 23 silk-to-edge warnings from connectors that overhang on purpose | fixed (rule) |
| B7 | bay | OK | LMR51635 hot loop, SW node, FB, EN, CB | — |
| B8 | bay | OK | 24 V / 5 V / DUT current paths and widths | — |
| B9 | both | OK | ERC, DRC copper, parity, JLC DFM, schematic readability | — |

## Power hub

### H1 — High — 24 V input path too thin for the rack's current

*Where:* J1 (JST VH) → Q1 drain tab (`VIN_RAW`), Q1 source → D2/C1/C2 → the five TPS26600 IN pins
(`+24V`).

*Why:* the hub input carries the whole rack: ≤ 7.3 A by `docs/power.md`, 8 A if all five eFuses
sit at their 1.6 A limit.  Freerouting drew `VIN_RAW` and the `+24V` trunk as 1.5 mm tracks
(netclass Power; 345 mm of them).  On outer 1 oz copper, IPC-2221 gives ≈ 3.2 A for a 10 °C rise
on 1.5 mm; at 7–8 A the input path would run ≈ 60–80 °C above ambient, and its first 40 mm alone
drop ≈ 0.1 V and burn ≈ 1 W.
Q1 (SUD50P06, ≈ 20 mΩ) also dissipates ≈ 1 W at 7 A with nothing but its own pad.

*Fix (done, `power-hub/design.py`):* copper pours instead of tracks, present while routing:
* F.Cu `VIN_RAW` pour from J1 pin 1 to Q1's tab and down under it (Q1's heat spreader);
* F.Cu `+24V` pour over Q1's source, D2, C1/C2 and a branch towards the eFuse row;
* B.Cu `+24V` strip (4.4 mm) under the eFuse row, tied to the branch by 6 vias (0.8/0.4);
* per eFuse, a top-side `+24V` island on its two IN pins with 2 vias into the strip.
The B.Cu GND pour still covers the rest of the bottom side.  Hand-soldered through-hole pads (J1,
the JST PH rows) always get thermal reliefs, even on these solid pours (`pcbgen.py`).

Two things had to be learnt on the way, both now handled by the generator:
* Freerouting does not treat a copper area on a signal layer as an obstacle: on the first try it
  ran row and signal tracks straight through the new pours and KiCad's fill broke them into
  pieces (11 unconnected items).  A zone marked `exclusive` now gets a tracks-only keep-out over
  its core (inset 0.5–0.6 mm), so other nets go around while the net's own tracks can still reach
  the pour's margin.
* `+24V` left the Power netclass (1.5 mm tracks): its current flows in the pours, and its remaining
  tracks only feed the SHDN pull-ups, the FAULT LEDs and Q1's gate zener (mA) — 1.5 mm tracks
  could not even reach a pour through a 0.6 mm margin.

### H2 — Medium — eFuse exposed pads without thermal vias

*Where:* U1–U5 (TPS26600PWP, HTSSOP-16 PowerPAD = GND).

*Why:* 150 mΩ RON × (1.6 A)² ≈ 0.38 W per channel at the limit, more while it limits.  The pad
had no via and there is no top-side GND pour on the hub: the pad only reached GND through 0.25 mm
tracks to its GND pins.

*Fix (done):* six GND vias per pad (0.6/0.3) to the B.Cu GND pour, placed in the pad's copper but
outside its 2.46 × 2.66 mm solder-mask opening, so they are tented and no solder wicks down.

### H3 — Medium — eFuse decoupling far from the pins

*Where:* C11–C15 (input 1 µF) sat at the OUT side, ≈ 9 mm from the IN pins; C31–C35 (output) on
the far side of the package.

*Fix (done):* each input cap now sits beside the IN pins, its +24V pad on the IN island; each
output cap beside the OUT pins.

### H4 — Medium — no stackup in the board

KiCad showed its default stackup.  The hub is now declared as a 2-layer 1.6 mm FR4 board, 1 oz,
lead-free HASL (as ordered, see `tools/bom.py` `JLC_FINISH`).

### H5 — Low — GND pour voids — open

With every GND pad routed by Freerouting (the pour is added afterwards), the B.Cu GND pour has
voids below the eFuse row, wherever signal and row tracks enclose an area with no GND via in it.
The return path that matters (row connectors along the top edge → J1) runs through the solid top
half, so this is about copper balance, not function.  A 2-layer board can't be stitched like the
bay node without a top-side GND pour; adding one (deferred, with `stitch`) is the option if you
want it.

## Bay node

### B1 — Medium — no stackup in the board

`get_board_stackup` (live) returned KiCad's default: three 0.48 mm dielectrics, finish "None", no
impedance control.  The board is now declared as JLCPCB's JLC04161H-7628 (F.Cu 1 oz · 0.21 mm 7628
prepreg · In1 0.5 oz · 1.065 mm core · In2 0.5 oz · 0.21 mm prepreg · B.Cu 1 oz), ENIG.  That puts
In1 (solid GND) 0.21 mm under the top signals: F.Cu traces have a tight return path.  In2 (+5V pour)
is 0.21 mm above B.Cu, so bottom-side and In2 traces return through the +5V pour and the B.Cu GND
pour; fine for this board's speeds, see B3 for USB.

`pcbgen.py` writes the `(stackup …)` block into the saved board (pcbnew's Python API has no
stackup bindings, and Konnect can't set it either: KiCad 10 does not implement
`UpdateBoardStackup`).

### B2 — Medium — LDO without heat spreading

*Where:* U2 AMS1117-3.3 (SOT-223), tab = +3V3.

*Why:* (5 − 3.3) V × 0.15–0.4 A (ESP32-S3 Wi-Fi average to peak) = 0.25–0.7 W.  The tab had only
its own pad on a top layer otherwise poured with GND: SOT-223 is ≈ 100+ °C/W like that.

*Fix (done):* a solid F.Cu `+3V3` island around the tab (≈ 6 × 6 mm), 8 vias to In2, where the
`+3V3` area under the module now extends down to the LDO.

### B2b — Low — In2 copper lost to removed +5V islands

Seen after the first re-route: wherever In2 signal tracks close a loop, the `+5V` pour inside has no
`+5V` via, KiCad removes it as an island, and In2 ended up with 1900 mm² of `+5V` instead of
3100 mm² (the whole strip under the USB-C ports went bare).  Nothing depended on it electrically
(every `+5V` connection is a track: the In2 pours are added after routing), but it unbalances the
copper between In1 and In2 and leaves bottom-side traces without a near reference.  *Fix (done):*
a lowest-priority GND "fill" zone on In2 takes the area the power pours leave, tied down by the
GND stitching vias (`stitch_gnd()` doesn't count it as a GND layer, so the stitching grid is
unchanged).

### B3 — Medium — USB pairs and High-Speed pass-through — fixed (hand-routed)

*Where:* `PC_DP/DN` (J3 → U4 → U5), `PCPATH_DP/DN` (U5 → U6), `DUT_DP/DN` (U6 → U8 → J4),
`ESP_DP/DN`.

*Why:* the ESP32-S3 is full-speed only, but in **classic mode** a laptop talks to the DUT through
both FSUSB42s, and a High-Speed DUT will negotiate 480 Mb/s.  Freerouting has no differential-pair
support; measured on its routing (da40db9 → first re-route of this review):

| pair | P / N length | skew | coupled | layers, vias |
|---|---|---|---|---|
| PC | 25.7 / 15.8 → 26.2 / 16.1 mm | 9.9 → 10.1 mm | 22 → 50 % | F.Cu; D+ loops under J3 to join A6/B6 |
| PCPATH | 40.6 / 40.2 → 38.9 / 44.4 mm | 0.4 → 5.5 mm | 95 → 51 % | F.Cu + In2 (+ B.Cu), 2–3 vias each |
| DUT | 27.3 / 28.7 → 29.2 / 28.6 mm | 1.4 → 0.6 mm | 80 → 34 % | F.Cu + In2 / B.Cu, 0–2 vias |
| ESP | 69.8 / 70.4 → 86.5 / 82.0 mm | 0.7 → 4.6 mm | 44 → 4 % | three layers, 3 vias each |

Fine for full speed; for High-Speed, 10 mm of skew, the stub loop and the In2 / B.Cu segments
(referenced to the +5V pour, not the In1 plane) are out of any guideline, and the numbers moved a
lot from one re-route to the next.

*Fix (done, at your request):* the classic-mode chain is routed by hand in `design.py`
(`usb_hs_routes()`), drawn before Freerouting runs and locked, so the router works around it
(`b.pcb["tracks"]`, new in `pcbgen.py`):
* coupled pairs on F.Cu over the solid In1 plane: 0.25 mm tracks, 0.15 mm gap (≈ 90 Ω on
  JLC04161H-7628 by closed-form estimate — check in JLC's impedance calculator if you order the board
  impedance-controlled; USB allows ±15 %), 0.5 mm pitch only where the pairs meet 0.5 mm pins;
* parts re-placed for a straight path: U4 (ESD) in line under J3, U5 (MUX_PC) right above it
  (rot 90, D± facing J3), U6 (MUX_DUT, rot 180) and U8 (ESD, rot 90) on the way to J4;
* the USBLC6s are used in flow-through: the connector side and the protected side are separate nets
  (`PC_CONN_DP/DN`, `DUT_CONN_DP/DN` on the connector side), so the signal can only go through the
  part (pin 6 → 1, 4 → 3) and DRC would flag any copper bridging its pins outside.  The first
  version of this routing ran one net through both pins and a track under the package — Fabio's
  remark: the part is meant to be passed through, not bridged.  Their GND/VBUS pins get a short
  track to a via between the two lines;
* the two FSUSB42s number their pins the same way round, so a single-layer PCPATH would have to
  cross itself: `PCPATH_DN` hops under `PCPATH_DP` on B.Cu between two vias, and three bumps on
  `PCPATH_DP` (the zig-zag) make up for the extra length;
* on each USB-C receptacle the A-side pins (A6/A7) are the through path; B6 joins A6 with a loop
  around the pad row, B7 joins A7 through B.Cu (two vias, ≈ 1 mm stub);
* the full-speed ESP pair (U3 → U5 / U6) stays with Freerouting.

Result (pad to pad, vias counted as the 1.6 mm they cross):

| segment | D+ | D− | skew |
|---|---|---|---|
| PC (J3 → U4 → U5) | 4.71 + 4.45 mm | 4.71 + 4.45 mm | 0.00 mm |
| PCPATH (U5 → U6) | 36.69 mm | 38.32 mm | 1.63 mm |
| DUT (U6 → U8 → J4) | 7.45 + 8.74 mm | 6.79 + 9.58 mm | 0.18 mm (−0.66 / +0.84 on each side of U8) |
| J3 → J4, traces only | 62.0 mm | 63.9 mm | 1.8 mm ≈ 12 ps |

What it can't fix: two FSUSB42s and two USBLC6s in series still add a few pF each, so the eye has
less margin than a direct connection; check with a High-Speed DUT on the first boards.  The new
U4/U5/U6/U8 orientations go through the existing `JLC_CPL_FIX` rotations: confirm them in JLC's
placement preview like the others.

### B4 — Medium — INA226 sense not fully Kelvin — fixed

*Where:* R19 (50 mΩ 1206) and U10 (INA226).

*Why:* Vin+ left R19 pin 1 from the pad itself, but Vin− joined `DUT_5V` ≈ 2.8 mm down the 0.6 mm
load track, so ≈ 2.3 mΩ of copper was in the measured drop: ≈ 4–5 % high readings, plus copper's
0.39 %/°C.  The router can't tell sense from load: both were the same net.

*Fix (done, at your request):* R19 is now `Device:R_Shunt` on a new footprint,
`bench:R_1206_3216Metric_Kelvin` (generated from the stock 1206 by `electronics/tools/footprints.py`):
the two current pads (1, 4) as before, plus a sense pad (2, 3) on the inner edge of each, tied to
its current pad by KiCad net-tie pad groups, copper only (tented, no paste) under the resistor
body.  U10's Vin+ / Vin− get their own nets, `SHUNT_P` / `SHUNT_N`, which leave from those sense
pads only; Vbus stays on `DUT_5V`.  Same part (C601102), same BOM line.

### B5 / B6 — Low — silkscreen

"PC" overlapped U4's pads and "AUX" R24's (3 silk-over-copper, 2 overlap warnings): both labels
moved.  The 23 silk-to-edge warnings came from footprints that sit on the outline on purpose (JST
PH side-entry mouths, the USB-C receptacles, the ESP32 antenna edge): `<board>.kicad_dru` now lets
only those footprints' silkscreen cross the Edge.Cuts line (`edge_parts` in `design.py`); every
other silkscreen check still runs.

### B7 — OK — LMR51635 buck

* Pinout checked against TI SLUSF64B (1 FB, 2 EN, 3 VIN, 4 GND, 5 SW, 6 CB) = board.
* Hot loop: C4 (100 nF 0603) 1.6 mm below the VIN/GND pins, C2/C3 (10 µF 1206) right behind it on
  the `buck-vin` / `buck-gnd` islands; the GND island also takes C7–C9's returns and has 7 vias to
  In1.  The high-frequency loop is ≈ 2.3 × 1.7 mm.
* SW node: 3.5 mm from pin 5 to L1, 0.45–0.6 mm wide, over solid In1.  Could be a short pour at
  pad width; not worth a change.
* FB: R4/R5 at the FB pin (4 mm of 0.25 mm track), away from SW and L1; the +5V sense comes from
  the COUT side.  EN divider and CB cap at their pins.

### B8 — OK — current paths

`+24V` 0.6 mm (≤ 0.6 A per node), `+5V` 0.6 mm plus the In2 pour, `DUT_5V_SW`/`DUT_5V` 0.6 mm
with 0.3–0.45 mm necks only at SOT-23 pins (1.5 A), `24V_BUS` daisy chain in a 5.8 mm In2 strip
(0.5 oz: ≈ 11 mΩ, 28 mW at 1.6 A).

### B9 — OK — checks

* ERC 0 / 0 on both boards; DRC 0 errors, 0 unconnected, schematic parity 0.
* JLCPCB DFM audit: 0 findings on both boards.
* Schematics: drawn sheets read left to right, no overlapping symbols or labels
  (`check_schematic_overlaps` on every sheet).
* `score_placement` reports courtyard overlaps between U3 and nearby parts: false positives, it
  compares bounding boxes and the ESP32 footprint's courtyard is T-shaped around the antenna;
  KiCad's own courtyard check passes.

## Fabio's v0.1 points, where they stand

| Point | Rev 0.2 + this review |
|---|---|
| Unreadable schematic | drawn sheets, checked readable |
| Asymmetric 4-layer stackup | S+GND / GND / PWR / S+GND, now declared as JLC04161H-7628 |
| No thermal reliefs (tombstoning) | reliefs on every pour; solid only on the buck islands, the LDO tab and the hub's power pours; hand-soldered pads always relieved |
| Power-monitor net names | 24V_BUS → +24V → +5V → DUT_5V_SW → DUT_5V |
| TPS54360B overkill / hot loop | LMR51635, hot loop checked (B7) |
| JST PH everywhere, no screw terminals | done (hub input JST VH for 10 A) |
| S/PWR/PWR/S without outer floods | not adopted: without the outer GND pours ~25 connections stay unrouted on 64 × 80 mm |

## Results after the fixes

Both boards regenerated and re-routed with `tools/kicad.sh <board> --route --fab` (the bay node's
last pass re-imported its Freerouting session with `--ses`), then checked again with Konnect on the
saved files:

| | bay node | power hub |
|---|---|---|
| ERC | 0 errors, 0 warnings | 0 errors, 0 warnings |
| DRC (zones refilled) | 0 errors, **0 warnings** (was 28) | 0 errors, 0 warnings |
| unconnected / schematic parity | 0 / 0 | 0 / 0 |
| JLCPCB DFM audit | 0 findings | 0 findings |
| stackup / finish | JLC04161H-7628, ENIG | 2-layer 1.6 mm, HAL lead-free |
| 24 V copper | (unchanged) | VIN_RAW pour 229 mm², +24V pours 394 mm² (top) + 321 mm² (bottom strip) + 5 IN islands, 16 vias 0.8/0.4 |
| USB / shunt | HS pairs hand-routed, USBLC6s in true flow-through, 1.8 mm skew J3 → J4; Kelvin sense pads on R19 | — |
| other | LDO tab island + 8 vias; In2: +5V 3020, +3V3 566, GND fill 112, 24V bus 351 mm² (In1: 4582 mm²) | 30 tented thermal vias under the eFuse pads; input/output caps at the pins |

`pcbgen.py` also drops the pass-through vias Freerouting sometimes leaves (a via whose tracks all
stay on one layer: two such vias showed up as DRC warnings on the bay node), and ties GND pads
sitting in a pour fragment without a via (KiCad reports those against the zone, not the pad).
Freerouting doesn't give the same result twice: the spots it left unrouted on some runs are now
drawn in `design.py` too — a via on J4's VBUS pads and DUT_5V's run from C21 to them on B.Cu, and a
short GND escape for U10 and C20.

The fab outputs (`fab/*`, BOMs, renders, schematic PDF) are regenerated.  CPL changes: the hub's
C11–C15 / C31–C35, the bay node's U4, U5, U6, U8, C17, C18, R24, R25 (new positions and
orientations); R19's BOM footprint is now `R_1206_3216Metric_Kelvin` (same LCSC part).

**Before ordering:** reload both boards in KiCad (File → Revert) and look at them, check the new
orientations in JLC's placement preview, and optionally decide H5.

## Second round (Fabio, after v0.3) → bay node v0.4

| Remark | Answer |
|---|---|
| The USBLC6s were bridged outside the part (pins 1–6 and 3–4 tied by copper) instead of passing the signal through | Fixed in v0.3 already: connector side and protected side are separate nets (`*_CONN_*`), the line enters on one pin and leaves on the other. |
| How was the pair's impedance estimated? | 2-D field solver on the JLC04161H-7628 cross-section (0.2104 mm 7628 prepreg, εr 4.4, 35 µm copper): 0.25 mm tracks / 0.15 mm gap give Zdiff ≈ 93.5 Ω bare, ≈ 90 Ω under 15 µm of solder mask (εr 3.8). |
| "The stackup is still a disaster": L3 was called power but carried signals; wants signals / GND only / power only / signals | v0.4: In2 carries power planes only (+3V3, +5V, 24 V strip), no track.  That needed a new placement (below). |
| J5 used a JST SH, very small: pick a PH | J5 is a JST PH 6 since v0.3; in v0.4 every PH on the node is the SMD S*B-PH-SM4-TB, placed by JLC. |
| INA226 Vbus should be tied to IN+ | Withdrawn by Fabio. |

**Why a new placement.** With In2 for power only, Freerouting has two signal layers, and v0.3's
placement left 13–18 connections unrouted whatever the passes.  The cause was the GPIO map: most
module pins left from the left column and went to the DUT power block and the AUX connector on the
right, crossing everything else.  v0.4 keeps every connector and the module where the mechanics
put them and moves the rest.  The DUT power block (TPS2553, shunt, INA226) goes to the top right,
next to the module's right column and J4, and the LDO and the two buttons go to the top left.  The
muxes now sit just under the module, so the front port's pair runs straight up the middle.  Each
GPIO sits on the module edge that faces its destination (map in [electronics.md](electronics.md),
firmware updated).  `pcbgen.py` also gives every GND and supply pin its own via to its plane before
routing (`fanout_nets`), so no pin depends on the outer pours.

| | bay node v0.4 |
|---|---|
| ERC (Konnect) | 0 errors, 0 warnings |
| DRC (Konnect, zones refilled) | 0 errors, 0 warnings, 0 unconnected, schematic parity 0 |
| Copper on In1 / In2 | GND plane only / power planes only, no track on either |
| USB HS | hand-drawn again for the new geometry; J3 → J4 D+ 64.5 mm, D− 64.6 mm (0.1 mm skew, vias as 1.6 mm) |
| JLCPCB DFM audit (Konnect) | 2 notes: the UART test pads are on the bottom side (copper only, not in the BOM or CPL, so no bottom-side assembly), and R6 / TP2 sit 0.73 mm apart, on opposite sides |

Konnect's full design review on v0.4 (`run_design_review`, `score_placement`, saved files) adds
findings that are all known false positives, plus one optional improvement:

| Finding | Reading |
|---|---|
| `score_placement`: hard fail, 9 parts overlap U3's courtyard | Bounding-box test: the ESP32 footprint's courtyard is a T (wide antenna keep-out at the rear), so its bbox covers the parts beside the module. KiCad's polygon check (DRC) finds no courtyard overlap. |
| U10 Vin+ / Vin− "no decoupling" | They are the INA226's sense inputs, not supply pins. |
| +3V3 / +5V "no bulk" or "no decoupling" on the USB and DUT sheets | Checked sheet by sheet: the bulk caps sit on the Power and MCU sheets (C7–C9 3 × 22 µF on +5V, C12 and C13 22 µF on +3V3). |
| R6 / TP2 0.73 mm apart, parts on both sides | Opposite sides; the bottom-side parts are bare-copper test pads, not assembled. |
| No test point on +24V / +5V / +3V3 | Info only.  TP4 is +3V3; the others can be probed on C1, C7. |
| U4 / U8 VBUS (+5V) without a local 100 nF | Optional: they reach the +5V plane through a via, and the buck's output caps are far away. A 100 nF next to each USBLC6 would lower the clamp rail's impedance during ESD. Added in v0.5 (C25, C26). |

## Bay node v0.5 (2026-10-18)

The row cable becomes 6-pin (VRACK 20 / 28 V, CAN, POS, [can.md](can.md)) and a Rack bus sheet adds the
TCAN1044AV, its PESD2CAN and the POS in/out clamps.  Konnect checked the saved files after
Freerouting:

| | bay node v0.5 |
|---|---|
| ERC (Konnect) | 0 errors, 0 warnings |
| DRC (Konnect) | 0 errors, 0 warnings, 0 unconnected, schematic parity 0 |
| `audit_connections`, `check_bom_health` | 0 findings |
| Copper on In1 / In2 | no track on either (checked in the saved board with pcbnew) |
| CAN pair | J1 → J2 straight through: CAN_H 52 mm, CAN_L 60 mm; stub to U11 1.8 / 2.3 mm, to D5 11 / 2.3 mm (≤ 20 mm asked) |
| Pin nets | U11 1 TXD · 2 GND · 3 +5V · 4 RXD · 5 +3V3 (VIO) · 6 CAN_L · 7 CAN_H · 8 GND (STB); D5 1 CAN_H · 2 CAN_L · 3 GND; D6 / D7 1 GND · 2 +3V3 · 3 the POS line |
| `run_design_review` | "NOT READY", from the same per-sheet false positives as v0.4 (above), plus +3V3 / +5V "no bulk" on the new Rack bus sheet: the bulk caps are on the Power and MCU sheets |

v0.4's open point is fixed: C25 and C26 (100 nF) sit on U4's and U8's VBUS pins.  A POS line driven high into a
node whose 3.3 V is off would feed its rail through the two 10k and D6 (≈ 0.15 mA); every node of a row
shares the row's VRACK, so this only happens if a neighbour's own regulator is dead.

## Power hub v0.4 (2026-10-18)

This is a new board for the power box: 4 eFused rows on 6-pin PH, and the rack controller (ESP32-S3,
TCAN1044AV CAN master).  Konnect checked the saved files after Freerouting:

| | power hub v0.4 |
|---|---|
| ERC (Konnect) | 0 errors, 0 warnings |
| DRC (Konnect, zones refilled) | 0 errors, 0 warnings, 0 unconnected, schematic parity 0 |
| `audit_connections` | 0 findings |
| `audit_decoupling` | VBUS on the USBLC6 had no capacitor: **fixed** (C120, 1 µF; USB caps VBUS at 10 µF) |
| JLCPCB DFM audit | 1 note: 7 bottom-side footprints.  They are bare test pads, not in the BOM or CPL, so no bottom-side assembly |
| `run_design_review` | "NOT READY", driven by per-sheet false positives (below) |

| Finding | Reading |
|---|---|
| +3V3 "no decoupling" on the Outputs sheet | The rail's caps sit on the Controller sheet (C113 22 µF, C114 / C117 100 nF, C112 22 µF at the LDO); the Outputs sheet only has the FLT pull-ups and LED resistors on it |
| +24V "no bulk" on the Outputs sheet | C1 / C2 (2 × 220 µF) are on the Input sheet |
| VBUS "no bulk (≥ 10 µF)" | On purpose: a USB device may present at most 10 µF on VBUS |
| No test point on +24V / +5V / +3V3 / VBUS | TP5 (+5V), TP6 (+24V) and TP4 (+3V3) were added on the bottom side |

Open, for a later revision:
* The bottom GND pour is cut into pieces by the signals that run from the rows to the module.  The
  signals are slow (I/O, CAN at 250 kbit/s, USB full speed), but a hand placement of the signal
  bundle, or a 4-layer board, would keep it whole.
* The schematic uses the automatic block layout; it is not drawn like the bay node's.

## Power hub v0.5 (2026-10-18)

The input becomes USB-C PD (AP33772S sink, back-to-back NMOS, 5 mΩ Kelvin shunt), the board goes
to 4 layers, and the rows are off until the controller turns them on.  Konnect checked the saved
files after Freerouting:

| | power hub v0.5 |
|---|---|
| ERC (Konnect) | 0 errors, 0 warnings |
| DRC (Konnect, zones refilled) | 0 errors, 0 unconnected, schematic parity 0; warnings below |
| `audit_connections` | 2 findings, both expected (below) |
| `audit_decoupling` | 1 finding, a false positive (below) |
| JLCPCB DFM audit | 8 bottom-side footprints: the bare test pads, not in the BOM or CPL |
| 3D coverage (`tools/pcb_glb.py --check`) | 146 parts with a model, 0 stand-ins, 0 without a body |

| Finding | Reading |
|---|---|
| "I2C SDA / SCL on U1 have no pull-up" | They do: R13 / R14 (4.7k), fed from a GPIO (I2C_PU), so a controller running from its console USB alone never back-feeds an unpowered AP33772S through SDA / SCL (Diodes' EVB guide asks that the sink powers up first) |
| "PWR_EN has no decoupling capacitor" | PWR_EN is the AP33772S's NMOS gate drive (a charge pump through R8), not a supply pin |
| DRC: silkscreen clipped by the mask (C8's outline at C10) | Cosmetic: the fab clips silkscreen off pads |
| DRC: U1 "does not match the library copy" | Only in a local KiCad run: its QFN-24 footprint differs between the local library and the Docker image's.  The build's own DRC (Docker) doesn't report it |

What changed for routing, from the v0.4 → 4-layer attempt that left 18 connections:
* In2 is split once: VRACK under the input, along a band at y ≈ 39 and down the eFuse column;
  +3V3 everywhere else, in one piece around it (no pin is left over another net's area).
* Each eFuse's SHDN leaves through a hand-drawn track to its pull-down and series resistor, just
  below the eFuse; its GND pins go straight onto the exposed pad.
* The ON LED's resistor sits by its eFuse: only the LED's milliamps go to the front.
* PD_VCC reaches the buck in a hand-drawn 0.8 mm bottom track; the input's pours are exclusive.
* The Kelvin pair, the NMOS gates and IFB's capacitor are drawn by hand.

Open, for a later revision:
* The schematic uses the automatic block layout; it is not drawn like the bay node's.
* Re-quote at JLCPCB (the cost is an estimate) and check the AP33772S's sourcing.

## CAN transceiver → TCAN1462V (2026-10-18)

Both boards swap the TCAN1044AV for the TCAN1462V: the same SOIC-8 pinout (TXD, GND, VCC, RXD, VIO,
CANL, CANH, STB), plus signal improvement for the star bus ([can.md](can.md#bus)).  The footprint,
placement and routing are unchanged: the regenerated PCBs carry every track and via of the previous
ones, and only U6 / U11's value and fields differ.  Konnect, on the saved files:

| | power hub (U6) | bay node (U11) |
|---|---|---|
| Pin nets (`get_component_nets`) | TXD CAN_TXD, VCC +5V, RXD CAN_RXD, VIO +3V3, CANL / CANH, STB CAN_STB (a GPIO) | the same, STB on GND (always on) |
| ERC | 0 errors, 0 warnings | 0 errors, 0 warnings |
| DRC | 0 errors, 0 unconnected, parity 0; the two warnings above | 0 errors, 0 warnings, 0 unconnected, parity 0 |
| 3D coverage (`tools/pcb_glb.py --check`) | 146 parts with a model, 0 stand-ins | 85 parts with a model, 0 stand-ins |

Sourcing: the TCAN1462VDRQ1 (C7399456) had no LCSC stock on 2026-10-18.  The board BOMs list two
alternates for the same footprint: the TCAN1044AVDRQ1 (C3234993, no signal improvement) and NXP's
TJA1462AT/0Z (C3234095, signal improvement, bus pins −36 / +40 V instead of ±58 V).  The TCAN1462
without the V (C22445414, in stock) does not fit: with no VIO pin its RXD swings to 5 V, too much for
the ESP32-S3.

## Bay node: J2 mirrored, the row cable flat (2026-10-18)

J2 (ROW OUT) now carries J1's pinout mirrored (1 POS out · 2 GND · 3 CAN_L · 4 CAN_H · 5 GND · 6 VRACK), so
the jumper between two nodes lies flat with no twist ([can.md](can.md#row-cable)).  Every net crosses the
board straight: the VRACK strip on In2 runs from J1.1 to J2.6 at the same height, and R30 moved next to
J2.1.  The node was re-routed (Freerouting).  Konnect, on the saved files:

| | bay node |
|---|---|
| J1 / J2 pin nets (`get_component_nets`) | J1: VRACK, GND, CAN_H, CAN_L, GND, POS_IN_CONN; J2: POS_OUT_CONN, GND, CAN_L, CAN_H, GND, VRACK |
| ERC | 0 errors, 0 warnings |
| DRC | 0 errors, 0 warnings, 0 unconnected, schematic parity 0 |
| CAN pair | J1 → J2: CAN_H 55 mm, CAN_L 59 mm; stubs to U11 3.7 / 8.2 mm, to D5 3.5 / 1.3 mm (≤ 20 mm asked) |
| 3D coverage (`tools/pcb_glb.py --check`) | 85 parts with a model, 0 stand-ins |

The hub's row outputs get the same OUT pinout (below), so the feeds are the same cable.

## Power hub: row outputs with the OUT pinout (2026-10-18)

The hub's row outputs (J2–J5) now carry the bay nodes' OUT pinout (1 POS · 2 GND · 3 CAN_L · 4 CAN_H ·
5 GND · 6 VRACK), so every row cable, feed or jumper, is the same flat one ([can.md](can.md#row-cable)).
Each row's 0.8 mm ROW track leaves its eFuse as before, stops short of the connector's rear pin (POS),
drops to B.Cu beside the connector (three vias) and comes back up at pin 6, so the top side beside
the pads stays free for the CAN pair; R10x (POS, 10k) sits behind pin 1.  The AP33772S's I2C routes
of the first layout are now fixed in design.py (a re-route left SDA without a way out once).
Konnect, on the saved files:

| | power hub |
|---|---|
| Row output pin nets (`get_component_nets`, J4) | POS_C_CONN, GND, CAN_L, CAN_H, GND, ROW_C |
| ERC | 0 errors, 0 warnings |
| DRC | 0 errors, 0 unconnected, parity 0; the two warnings above (C8's silkscreen, U1's local library copy) |
| CAN pair, U6 → rows A / B / C / D | CAN_H 102 / 77 / 48 / 24 mm, CAN_L 97 / 68 / 43 / 18 mm (before: 99 / 72 / 51 / 22 and 106 / 82 / 56 / 27); H − L 4.2–8.3 mm (before 4.6–10.4); totals 115 / 118 mm (before 117 / 124) |
| CAN pair coupling | 41 % of CAN_H within 1 mm of CAN_L on the same layer, median gap 1.45 mm (before: 41 %, 1.39 mm) |
| 3D coverage (`tools/pcb_glb.py --check`) | 146 parts with a model, 0 stand-ins |

## DATA port board and the node's J7 (2026-10-18)

The drawer's USB-C coupler and its 90° extension become our own board, `electronics/data-port`
(40 × 17 mm, 2 layers: USB4105 source with Rp 22k on CC1/CC2, USBLC6 at the receptacle, JST PH 5
side entry), on a 5-wire PH lead from the node's new J7 (B5B-PH-SM4-TB, vertical) through the drag
chain ([electronics.md](electronics.md#data-port-v10--2-layers-40--17-mm)).  J7 sits in parallel
with J4 (one of the two in use).  Both boards were routed by Freerouting; on the node the first
route ran POS_OUT between J2.6 and its two VRACK vias and cut that pad off its island, so the vias
now sit at the pad's end, as J1.1's.  Konnect, on the saved files:

| | data port | bay node |
|---|---|---|
| Pin nets (`get_component_nets`) | J2: GND, LEAD_DP, LEAD_DN, GND, VBUS; J1: CC1/CC2 on their own nets, SBU open, shell GND | J7: DUT_5V, GND, DUT_DN, DUT_DP, GND (J2's mirror: one "Same direction" lead) |
| ERC | 0 errors, 0 warnings | 0 errors, 0 warnings |
| DRC (zones refilled) | 0 errors, 0 warnings, 0 unconnected, parity 0 | 0 errors, 0 warnings, 0 unconnected, parity 0 |
| JLC DFM (`audit_manufacturing`) | 0 findings, 8 parts on the top | as before: 4 parts on the bottom (test pads), R6 / TP2 0.73 mm apart (opposite sides) |
| J7 branch | — | DUT_DP 15.9 mm, DUT_DN 17.5 mm on F.Cu over In1 from U8's mux side, no via; an open stub of that length when J4 is used with J7 empty |
| 3D coverage (`tools/pcb_glb.py --check`) | 6 parts with a model, 0 stand-ins | 86 parts with a model, 0 stand-ins |

JLC placement corrections for the two new PH parts were fitted the same way as the others
(EasyEDA pads onto KiCad pads, pin by pin): C265104 180°, +0.14 mm y; C265085 180°, −0.62 mm y.

Reworked the same day to the drawer's constraints (`config/rack.yaml` › `pcb.data_port`): 40 × 17 mm,
the USB-C at x 30.5 (the right edge 9.5 mm from the mouth, clear of the chain foot's lock screw), the
PH at x 17.5 (on a 17 mm board its courtyard and the USB4105's overlap in depth, so they must not in
x), holes (3, 8.5) and (37.5, 4) over the drawer's cable window.  Re-routed (0 unrouted, 0
violations); Konnect on the saved files: ERC 0, DRC 0 / 0 unconnected / parity 0 (zones refilled),
JLC DFM 0 findings, 6 parts with a model.

## Bay node: the bay's camera on J6, the WROOM-1-N8R8, 64 × 90 mm (2026-10-18)

The user chose a camera per bay wired to the bay's own node: an Arducam Mega 3MP SPI (M12, ≈ 120°)
and white LEDs on one PH 8 lead, and the ESP32-S3-WROOM-1-N8R8 for its 8 MB octal PSRAM
([electronics.md](electronics.md#bay-node-1-per-unit--4-layers-64--90-mm), Camera, WROOM-1 and
the longer board).  The board grew 10 mm at the rear (the whole layout moved with it, holes
included); the module's top edge is the new rear edge.  Its octal PSRAM takes IO35–IO37 and the
WROOM-1 has no IO26/IO33/IO34: AUX_RX, AUX_RST_CTL, POS_OUT and I²C moved, and the whole map is now
the ESP32-S3-DevKitC-1 v1.1's.  J6 (B8B, vertical) sits right of the PC pair, under J7; J5 (AUX)
became a vertical B6B.  The stock WROOM-1 footprint's 0.2 mm vias in the exposed pad (below the
0.3 mm minimum hole) are dropped by a project footprint, the pad stitched to In1 around it.
Re-routed (Freerouting); the session import now also removes a via left at the end of a dead
branch and the branch (here IO12's: 1 via, 3 segments).  Konnect, on the saved files:

| | bay node |
|---|---|
| U3 pin nets (`get_component_nets`) | as `design.py`: IO1/IO2 I²C, IO7–IO11 camera, IO12 AUX_RST, IO21 AUX_RX, IO38 LED, IO42 POS_OUT; IO4–IO6 and IO35–IO37 open |
| J6 pin nets | CAM_5V, GND, CAM_SCK_C, GND, CAM_MOSI_C, CAM_MISO_C, CAM_CS_C, LED_K |
| ERC | 0 errors, 0 warnings |
| DRC (zones refilled) | 0 errors, 0 warnings, 0 unconnected, parity 0 |
| JLC DFM | 4 parts on the bottom (test pads); the R6 / TP2 proximity is gone (R6 moved to the module's EN pin) |
| Camera tracks, U3 → the 33 Ω row | SCK 45.7 mm, MOSI 44.9, MISO 53.9, CS 52.8; the light 82.5 mm |
| 3D coverage | 97 parts with a model, 0 stand-ins |
| `check_pinmap.py` | README rows match design.py; the moved and camera nets wait for the firmware's devicetree |

JLC placement corrections, fitted as before: C2913201 (WROOM-1-N8R8) +3.63 mm y, C495548 (B8B)
−0.63 mm y, C471518 (B6B) 180° −0.63 mm y, C20917 (AO3400A) 180°.
