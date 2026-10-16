# Board review with Konnect (rev 0.2)

Review of the two rev 0.2 boards (`electronics/bay-node`, `electronics/power-hub`, commit
`da40db9`) with the Konnect MCP server (0.13.0, KiCad PCM plugin) against a
live KiCad 10.0.7, in the light of Fabio's review of v0.1.  Done on 2026-10-16.

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
| B3 | bay | Medium | USB pairs not fit for High-Speed pass-through (classic mode) | **open — your call** |
| B4 | bay | Medium | INA226 Vin− tapped ≈ 2.8 mm down the load path (≈ 4–5 % gain error) | **open — your call** |
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

### B3 — Medium — USB pairs and High-Speed pass-through — open

*Where:* `PC_DP/DN` (J3 → U4 → U5), `PCPATH_DP/DN` (U5 → U6), `DUT_DP/DN` (U6 → U8 → J4),
`ESP_DP/DN`.

*Why:* the ESP32-S3 is full-speed only, but in **classic mode** a laptop talks to the DUT through
both FSUSB42s, and a High-Speed DUT will negotiate 480 Mb/s.  Measured on the routed board
(da40db9 → after this review's re-route):

| pair | P / N length | skew | coupled | layers, vias |
|---|---|---|---|---|
| PC | 25.7 / 15.8 → 26.2 / 16.1 mm | 9.9 → 10.1 mm | 22 → 50 % | F.Cu; D+ loops under J3 to join A6/B6 |
| PCPATH | 40.6 / 40.2 → 38.9 / 44.4 mm | 0.4 → 5.5 mm | 95 → 51 % | F.Cu + In2 (+ B.Cu), 2–3 vias each |
| DUT | 27.3 / 28.7 → 29.2 / 28.6 mm | 1.4 → 0.6 mm | 80 → 34 % | F.Cu + In2 / B.Cu, 0–2 vias |
| ESP | 69.8 / 70.4 → 86.5 / 82.0 mm | 0.7 → 4.6 mm | 44 → 4 % | three layers, 3 vias each |

For full speed this is all fine.  For High-Speed, 10 mm of skew and the D+ loop on the PC pair are
out of any guideline (≈ 1 mm), and the In2 / B.Cu segments are referenced to the +5V pour rather
than the In1 plane.  The numbers also move a lot from one re-route to the next: nothing constrains
them, Freerouting has no differential-pair support.

*Proposed:* decide whether classic mode must carry High-Speed.  If yes: route the PC → PCPATH →
DUT chain by hand on F.Cu over In1, as coupled 90 Ω pairs (check width/gap for JLC04161H-7628 in
JLC's impedance calculator; 0.2/0.15 mm today), matched, no stubs, and move U5 next to U6 to
shorten PCPATH.  Hand routing is overwritten by the next regeneration, so it needs a way to keep
pre-routed tracks in `design.py` (or a frozen board) — not done without your go-ahead.  If no:
document classic mode as full-speed only.

### B4 — Medium — INA226 sense not fully Kelvin — open

*Where:* R19 (50 mΩ 1206) and U10 (INA226).

*Why:* Vin+ leaves R19 pin 1 from the pad itself, but Vin− joins `DUT_5V` ≈ 2.8 mm down the 0.6 mm
load track, so ≈ 2.3 mΩ of copper is in the measured drop: ≈ 4–5 % high readings, plus copper's
0.39 %/°C.  The router can't tell sense from load: both are the same net.

*Proposed:* a 4-terminal shunt footprint (KiCad net-tie pad groups: two current pads, two sense
pads) with `R_Shunt`-style sense nets to the INA226, or calibrate the gain once in firmware
against a known load.  Not done: it needs a new footprint in `electronics/lib/bench.pretty`.

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

Both boards regenerated and re-routed with `tools/kicad.sh <board> --route --fab`, then checked
again with Konnect on the saved files:

| | bay node | power hub |
|---|---|---|
| ERC | 0 errors, 0 warnings | 0 errors, 0 warnings |
| DRC (zones refilled) | 0 errors, **0 warnings** (was 28) | 0 errors, 0 warnings |
| unconnected / schematic parity | 0 / 0 | 0 / 0 |
| JLCPCB DFM audit | 0 findings | 0 findings |
| stackup / finish | JLC04161H-7628, ENIG | 2-layer 1.6 mm, HAL lead-free |
| 24 V copper | (unchanged) | VIN_RAW pour 229 mm², +24V pours 394 mm² (top) + 321 mm² (bottom strip) + 5 IN islands, 16 vias 0.8/0.4 |
| other | LDO tab island 33 mm² + 8 vias; In2: +5V 2306, +3V3 516, GND fill 849, 24V bus 352 mm² (In1: 4587 mm²) | 30 tented thermal vias under the eFuse pads; input/output caps at the pins |

The fab outputs (`fab/*-gerbers.zip`, `power-hub-cpl-jlcpcb.csv`, renders) are regenerated; the
hub's CPL changed for C11–C15 / C31–C35 (new positions), the BOMs did not change.

**Before ordering:** reload both boards in KiCad (File → Revert) and look at them; decide B3
(High-Speed in classic mode) and B4 (Kelvin shunt), and optionally H5.
