# Electronics

Two boards, both **schematics as code**: `electronics/<board>/design.py`
describes parts (with MPN, manufacturer, LCSC number), the nets their pins
connect to and PCB placement hints.  From that single description
`electronics/tools/` writes a real hierarchical KiCad 10 project (one sheet
per functional block), builds the matching `.kicad_pcb` (footprints, nets,
outline, zones, keep-outs, mounting holes from `config/rack.yaml`), autoroutes
it with Freerouting, and proves the two views agree with KiCad's own ERC and
DRC (schematic parity).

```console
$ tools/kicad.sh bay-node                  # schematic + placed PCB + ERC/DRC
$ tools/kicad.sh bay-node --route --fab    # + Freerouting + Gerbers/CPL/BOM/PDF/renders/STEP/GLB
$ tools/kicad.sh bay-node --ses --fab      # re-import the last Freerouting session (no re-route)
$ tools/kicad.sh bay-node --check          # ERC + read-only DRC of the PCB as it is (what CI runs)
```

`tools/kicad.sh` runs everything in the official `kicad/kicad:10.0-full`
image (and Freerouting in a JRE image), so the only prerequisite is Docker.
The generated projects open in a local KiCad 10 as normal projects.

**Schematics** are drawn, not just generated: every part in `design.py` has
an `sch=` position on the 0.1" grid and the main paths are real wires
(`Sheet.wire("U1.SW", "L1.1")`), so each sheet reads left to right like a
hand-made schematic — power path, then control, notes with the design maths.
Pins left unwired get a short stub with their net label.  The writer adds the
junctions and refuses any wire that would touch another net's pin or wire, and
KiCad's ERC plus the PCB's schematic-parity check catch the rest.

**Stackup** (bay node, 4 layers, symmetric): F.Cu signals + GND pour · In1 solid
GND · In2 power (+5V pour, +3V3 under the ESP32 and down to the LDO, the 24 V bus
strip; GND fills what they leave) · B.Cu signals + GND pour.  The board declares JLCPCB's standard
JLC04161H-7628 build (0.21 mm prepreg between F.Cu and In1, 1.065 mm core, 0.5 oz
inner copper) and ENIG; the hub declares 2 layers, 1.6 mm, lead-free HASL
(`stackup` / `finish` in `design.py`, written into the board by `pcbgen.py`).  The router may still use In2 for signals; its pours are
added after routing, around them.  A version without the outer pours left
about 25 connections unrouted on 64 × 80 mm (every SMD GND pad then needs its
own via), so they stay.  **Every pour connects pads through thermal reliefs**
(0.3 mm gap, 0.4 mm spokes): a GND pad heats up like the pad at the other end
of its part, so small parts don't tombstone in reflow and hand-soldered pins
take solder.  `<board>.kicad_dru` accepts a single spoke where fine-pitch
neighbours leave no room for two.  The LMR51635's hot loop (CIN – VIN – GND) and
its output capacitors sit on small solid top-side islands, with hand-placed
vias to In1, as TI's layout guide asks; the AMS1117's tab gets a solid +3V3
island with vias to In2.  Hand-soldered through-hole pads always get thermal
reliefs, even on solid pours.  Connectors that overhang the outline on purpose
are listed as `edge_parts`: their silkscreen may cross the board edge (the fab
clips it), every other silkscreen check still applies.

How the routing flow keeps ground honest (`electronics/tools/pcbgen.py`):

1. The router sees the inner GND plane and the outer GND pours, and connects
   every other net with real copper.
2. Freerouting trusts the pours to connect the GND pads, but once KiCad fills
   them with real clearances they can break into pieces.  After the SES is
   imported, `stitch_gnd()` first drops a grid of GND vias tying the pours to
   the plane.  Then every fragment still without a via gets one, at the first
   spot where it fits.
3. A GND pad that no connected fill reaches gets a thin track squeezed out to
   connected GND or to a via spot.
4. Pads the router walls in completely are listed under `fanout` in the
   board's `design.py`: a dog-bone via outside the package is reserved
   before routing (a keep-out) and placed after it.
5. Finally KiCad's own DRC lists the GND pads still unconnected, and each gets
   a short track to a GND via or to a spot where a small via fits.

> **Status: v0.2 — autorouted, reviewed against Fabio's v0.1 feedback, not yet
> ordered.**  ERC is clean and DRC reports no copper errors, no unconnected
> items and full schematic parity.  The buck's hot loop and the 24 V bus are
> placed by hand in `design.py`; the rest is still the router's draft: before
> ordering, look at the USB pairs (length/symmetry) and the 5 V widths in
> KiCad, and re-run DRC.  Hand edits to the PCB are fine — just don't re-run
> the generator over them (or move the routed board aside first).

## Bay node (×1 per unit) — 4 layers, 64 × 80 mm

Sheets: **Power · MCU · USB · DUT power & AUX** — see the PDF in
`electronics/bay-node/docs/`.

| Block | Parts | Notes |
|---|---|---|
| 24 V in/out | 2 × JST PH side entry | daisy chain, 2 A per contact; the hub's 1.6 A eFuse protects it |
| Protection | SUD50P06 P-FET + 12 V zener, SMBJ33A, 100 µF/50 V | reverse polarity, hot-plug clamp < 54 V |
| 5 V | LMR51635YDDCR (60 V, 3.5 A, synchronous, 1.1 MHz) + 3.3 µH FXL0630 | TI typical application (SLUSF64B table 8-2): 3 × 22 µF out, 2 × 10 µF + 100 nF in; FB 120k/22k → 5.16 V; EN 1M/100k: on above 13.5 V, off below 10.8 V |
| 3.3 V | AMS1117-3.3 | logic only |
| MCU | ESP32-S3-MINI-1-N8 | antenna at the rear edge, keep-out on all layers |
| DUT power | TPS2553 (RILIM 18k → 1.34–1.52 A), 50 mΩ shunt, INA226 @0x40 | +5V → DUT_5V_SW → shunt → DUT_5V (the DUT's VBUS); the INA226 runs from +3V3; default **on** (also without firmware), fault flag to GPIO |
| USB | 2 × FSUSB42 + 74LVC1G32, 2 × USBLC6-2SC6, 2 × USB-C | modes in [architecture.md](architecture.md) |
| UI | WS2812B-2020, SERVICE slide switch, RESET/BOOT, UART pads | |
| AUX | JST-SH 6: GND, 3V3 (10 Ω), TX/RX (1k), RESET/BOOT open-drain (2N7002) | |
| Camera | JST-PH 2: 5 V via 0.5 A PTC | |

**GPIO map:** IO4 PC_DET · IO5 SVC · IO6 DUT_EN · IO7 DUT_FLT_N · IO8/IO9 I²C ·
IO10 MUX_FORCE_PC · IO11 AUX_RST · IO12 AUX_BOOT · IO13 LED · IO14 INA_ALERT ·
IO17/IO18 UART1 (AUX) · IO19/IO20 USB · TXD0/RXD0 on test pads.

**USB-C roles:** the front PC port is a sink (5.1 k Rd on CC) whose VBUS is
only sensed; the DUT port is a source (22 k Rp → "1.5 A") with switched VBUS.

## Power hub (×1) — 2 layers, 120 × 70 mm

24 V JST VH input (10 A: the whole rack, ≤ 7.3 A) → SUD50P06 reverse
protection → SMCJ33A → 2 × 220 µF → 5 × TPS26600 eFuse (1.6 A, 4 ms soft
start, auto-retry, UV/OV defaults) → 5 × JST PH, top entry (rows A–D + AUX),
each with ON (green) and FAULT (red) LEDs.  1.6 A keeps the PH contacts (2 A)
safe; a row realistically draws ≈ 0.5 A (see [power.md](power.md)).
SHDN/FLT/IMON of every channel go to an unpopulated 2 × 8 header for a future
supervisor.

The 24 V path is copper pours, not tracks (up to 8 A if all five eFuses sit at
their limit): `VIN_RAW` from J1 to Q1's drain tab (also Q1's heat spreader), a
top-side `+24V` pour over Q1's source, D2 and C1/C2, a bottom-side `+24V` strip
under the eFuse row and, per eFuse, a top island on its IN pins with two vias
into the strip.  Those pours exist while routing and are `exclusive`: a
tracks-only keep-out over their core keeps other nets out (Freerouting would
otherwise run tracks through them).  Each eFuse's exposed pad has six tented GND vias to the bottom
GND pour, and its 1 µF input/output caps sit beside its IN/OUT pins.

A review of both boards with the Konnect MCP server (findings, fixes, what is
still open) is in [review-konnect.md](review-konnect.md).

## Sourcing

Every non-generic part carries `MPN`, `Manufacturer` and `LCSC` fields
(verified against JLCPCB's live library on 2026-10-16 through the
`@jlcpcb/mcp` server — see `tools/jlc_mcp.py`).  Generic passives are
resolved to JLC **basic** parts by `electronics/tools/passives.py` (cached in
`electronics/lib/passives.json`); values were nudged to basic-library E-series
where it didn't matter (e.g. 150k RT, 120k/22k FB).

`--fab` writes, per board:

* `fab/<board>-gerbers.zip` (Gerber X2 + Excellon), ready for JLCPCB/PCBWay;
* `fab/<board>-bom-jlcpcb.csv` (one line per LCSC part) and
  `fab/<board>-cpl-jlcpcb.csv` (placement, corrected to JLC's footprints: see
  [Placement corrections](#placement-corrections));
* `<board>-bom.csv` (detailed, one line per value: MPN, manufacturer, LCSC,
  alternatives);
* `docs/<board>-schematic.pdf`, SVGs, top/bottom/iso renders;
* `fab/<board>.step` and `fab/<board>.glb` (the web viewer uses the GLB).

The through-hole connectors (JST PH, and the hub's JST VH input) are soldered by hand, from
loose LCSC parts: `hand_solder=True` in `electronics/tools/catalog.py` keeps
them out of the JLC BOM and CPL, and the detailed BOM flags them "hand-solder,
buy loose (LCSC)" in its `Assembly` column.

## Assembly at JLCPCB

Real quote taken on jlcpcb.com on 2026-10-16 from the `fab/` files (USD,
indicative; shipping, DHL ≈ $27–40, and import VAT come on top).  The full
breakdown is in [`bom/README.md`](../bom/README.md), and `tools/bom.py`
(`JLC_QUOTE`) carries the same figures:

| Board | Order | PCB | PCBA | Total |
|---|---|---:|---:|---:|
| bay node | 20 PCBs, 4-layer ENIG (JLC adds 5 mm edge rails for Standard PCBA), 16 assembled, Standard | $58.90 | $308.81, of which components $181.21 and feeders $65.10 | **$367.71** |
| power hub | 5 PCBs, 2-layer ENIG, 2 assembled, Economic | $25.70 | $48.43, of which components $17.56 and extended parts $15.45 | **$74.13** |

Two changes were made after that quote and are not re-quoted (`JLC_FINISH`
and `jlc_order()` in `tools/bom.py` apply them, indicatively):

* **Power hub in lead-free HASL** instead of ENIG: ≈ $1 instead of $17.60
  for the 5 PCBs.  The hub has no fine-pitch part that needs a flat finish;
  the bay node stays ENIG for the ESP32 module and the USB-C receptacles.
* **Through-hole connectors soldered by hand**: node J1 J2 J6 (JST PH),
  hub J1 (JST VH) and J2–J6 (JST PH).  JLC's hand-soldering fee ($3.61 per board
  order) goes, and so do the loading fees of these extended part types (pro
  rata of the quoted fee: one type on the node, −$3.43; two on the hub,
  −$4.41).  The connectors cost the same bought loose from LCSC, plus LCSC's
  shipping.

That brings the order to ≈ **$360.67** for the nodes and ≈ **$49.51** for
the hub.  The quote's "manual assembly" lines are kept: re-quote to see
whether they go too.

Rev 0.2 came after the quote as well and is not re-quoted: on the node the
LMR51635 + FXL0630 replace the TPS54360B, its B560C Schottky, the FXL1040 and
the compensation network (≈ +$0.70 of parts per board, one extended part type
fewer), and the JST PH connectors cost less than the VH ones.  Re-quote before
ordering.

* **Bay node: Standard PCBA.** JLC can only place the ESP32-S3-MINI-1 module
  (C2913206) and the WS2812B-2020 LED with its Standard PCBA service, not
  Economic, so the node pays Standard fees (setup $25.75, stencil $8.27, X-ray
  $13.28 in the quote above).  These parts are flagged `standard_only` in
  `electronics/tools/catalog.py`, which `tools/bom.py` reads.  The WS2812C-2020-V6
  (C55109522) is Economic-capable, but the module keeps the board on Standard
  anyway.  Check the WS2812C pinout against the WS2812B-2020 footprint before
  swapping it in.  Every ESP32-S3/S2 module at JLC is Standard-only; the
  Economic-capable Ai-M62-32S (BL616) is evaluated, and kept for a v2, in
  [mcu-alternatives.md](mcu-alternatives.md).
* **Power hub: Economic PCBA.** Its 220 µF bulk capacitors use C3358, the
  Economic-capable LCSC listing of the same RVT1H221M1010 part.  The node's
  100 µF moved to C3352 the same way.
* **No Basic drop-ins.** Every extended part was checked against JLC's Basic
  library (October 2026): none has a Basic equivalent with the same ratings
  and footprint, so the extended-part loading fees stay (the node's $65.10 of
  feeders, the hub's $15.45).  Near misses were rejected:
  * SS54 Schottky: 40 V, below the buck's 60 V input rating;
  * AO3401A P-FET: 30 V, on a 24 V bus with transients up to 53 V;
  * 100 mΩ / 250 mW 1206 shunt: INA226 full scale would drop to 0.82 A, below
    the 1.5 A DUT limit.
* **One BOM line per LCSC part.** JLC refuses several lines that resolve to
  the same part ("Multiple lines in the BOM have been matched to the same
  part") and deselects them, so the JLC BOM merges them: J3/J4 USB-C,
  SW1/SW2, U5/U6 on the node; D3 + D11–D15 on the hub.  Merged lines carry
  the MPN as comment.

### Placement corrections

JLC does not place KiCad's footprint: for each LCSC part it takes its own
(EasyEDA) footprint, puts that footprint's origin on the CPL's Mid X/Y and
turns it by the CPL rotation.  Where JLC's footprint has a different 0° or a
different origin from KiCad's (connectors anchored on pin 1, SOT-23 drawn the
other way round, ICs drawn with pin 1 at the bottom), the part lands rotated
or shifted.  `JLC_CPL_FIX` in `electronics/tools/build_board.py` corrects the
CPL per LCSC part: an extra rotation (degrees, counter-clockwise) and an
origin offset in the KiCad footprint's own axes, both turned with the part.
The export stops if a part listed there changes footprint or moves to the
bottom side.

The values were worked out on 2026-10-16 by fitting each part's EasyEDA
footprint pads (`https://easyeda.com/api/products/<LCSC>/components`) onto
the KiCad pads, pin by pin, then checking that the bodies overlap and that
diodes, LEDs and electrolytics keep their cathode or + side.  JLC's
placement preview had shown the first three rows wrong before the fix; the
others come from the fit alone.  The through-hole connectors are soldered by
hand now and are no longer in the CPL, so their rows (JST PH/VH) don't
matter for JLC: they stay in the table for an order where JLC places them.

| LCSC part | Refs | Correction | Status |
|---|---|---|---|
| C173752 JST S2B-PH-K | node J1 J2 J6 | 180°, +1.00 mm x | was wrong in the preview; hand-soldered now, not in the CPL |
| C6186 AMS1117 SOT-223 | node U2 | 180° | looked wrong in the preview; confirm the fix |
| C165948 HRO TYPE-C-31-M-12 | node J3 J4 | −1.57 mm y | to confirm |
| C2913206 ESP32-S3-MINI-1 | node U3 | +2.55 mm y | to confirm |
| C431540 MSK12C02 | node SW3 | −0.25 mm y (lines up the pins; JLC's body outline then sits 0.25 mm off KiCad's) | to confirm |
| C45262770 LMR51635 TSOT-23-6 | node U1 | 270° (same EasyEDA footprint as C7519) | to confirm |
| C11355 FSUSB42 MSOP-10 | node U5 U6 | 270° | to confirm |
| C49851 INA226 VSSOP-10 | node U10 | 270° | to confirm |
| C7519 USBLC6-2SC6 SOT-23-6 | node U4 U8 | 270° | to confirm |
| C55266 TPS2553 SOT-23-6 | node U9 | 180° | to confirm |
| C10096 74LVC1G32 SOT-23-5 | node U7 | 180° | to confirm |
| C8545 2N7002 SOT-23 | node Q2 Q3 | 180° | to confirm |
| C7503186 SUD50P06 TO-252 | node Q1, hub Q1 | −1.89 mm x | to confirm |
| C544399 TPS26600 HTSSOP-16 | hub U1–U5 | 270° | to confirm |
| C160315 JST B2P-VH | hub J1 | +1.98 mm x | hand-soldered, not in the CPL |
| C56123098 XYECONN SM06B-SRSS-TB | node J5 | none: JLC's footprint could not be read (the JST original, C160405, needs none) | to confirm |

Checked by the fit and left alone: resistors, capacitors and the PTC (0603,
0805, 1206), the electrolytics (+ pad), the diodes and LEDs (cathode side),
the WS2812B-2020, the FXL0630 inductor (C167219) and the TS-1187A buttons.  The green
LED C2297 numbers its pads the other way round (pad 2 is the cathode), but
its cathode sits where KiCad's pad 1 is at 0°: don't "fix" it from the pad
numbers.

To confirm a part, upload the Gerber zip, BOM and CPL at jlcpcb.com, and in
the "Component Placement" step look at it in JLC's 2D and 3D preview:

1. The body sits over its pads, centred (a shift of half a pin pitch means
   an origin offset is wrong).
2. Pin 1, the cathode bar or the + side lines up with the board's silkscreen
   mark.
3. Side-entry connectors (SH, USB-C) open towards the board edge.

If a part is off, rotate or move it in JLC's editor until it fits, then copy
that change into `JLC_CPL_FIX` (add the extra degrees; an offset measured on
the board has to be turned back into the footprint's axes) and re-export with
`tools/kicad.sh <board> --check --fab`, so the next order needs no hand
correction.  Mark the row confirmed here once a preview shows it right.  A new
LCSC part needs the same check: until it is in the table it is placed exactly
as KiCad has it.

## Custom library

`electronics/lib/bench.kicad_sym` holds the two symbols the stock library
lacks: TPS2553DBV, and LMR51635 (KiCad's LMR51430 has another pinout).  All footprints and 3D models come from KiCad 10's
standard libraries.

## Future: chip-down ESP32-S3 (v2)

Every ESP32-S3 *module* (MINI-1, MINI-1U, WROOM-1, all memory variants) is
Standard-PCBA-only at JLC, which is what keeps the bay node off Economic
PCBA.  The bare **ESP32-S3FH4R2** (C3013940, ≈ $3.67, QFN-56 7 × 7 mm, 4 MB
flash + 2 MB PSRAM in package) is Economic-capable and is the same SoC, so the
Zephyr firmware (Wi-Fi, `uhc_dwc2` USB host) carries over unchanged.

* Saves ≈ $35–45 per 16-node order: about $1 per chip, plus Economic instead
  of Standard setup and stencil fees, and no added edge rails.  That is ≈ €2.5
  per node, more for larger runs.
* Costs: 40 MHz crystal, antenna (PCB trace or ceramic chip) with a matching
  network to tune on a VNA, extra decoupling, and the loss of the module's
  radio certification.  4 MB flash is enough for the USB/IP firmware with
  dual-slot updates.
* Not worth the RF risk at 16 nodes; worth revisiting for ≥ 50.

Alternatives considered:
* ESP32-S2FN4R2: cheaper, Economic, Zephyr Wi-Fi, but `uhc_dwc2` is not yet
  validated on the S2.
* ESP32-C3/C5/C6: no USB OTG, so no USB host.
* nRF54LM20 + nRF7002, or ESP32-P4 + C6: USB host supported, but two chips and
  more cost.
* NXP RW612: good Zephyr support, but no module stocked at LCSC.
