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

> **Status: v0.1 — autorouted, not yet reviewed.**  ERC is clean and DRC
> reports no copper errors and full schematic parity, but the routing is a
> machine's first draft: before ordering, review the USB pairs (length/
> symmetry), the buck's hot loop (C2/C3 – U1 – D3) and the 24 V/5 V widths in
> KiCad, and re-run DRC.  Hand edits to the PCB are fine — just don't re-run
> the generator over them (or move the routed board aside first).

## Bay node (×1 per unit) — 4 layers, 64 × 80 mm

Sheets: **Power · MCU · USB · DUT power & AUX** — see the PDF in
`electronics/bay-node/docs/`.

| Block | Parts | Notes |
|---|---|---|
| 24 V in/out | 2 × JST VH side entry | daisy-chain, 10 A |
| Protection | SUD50P06 P-FET + 12 V zener, SMBJ33A, 100 µF/50 V | reverse polarity, hot-plug clamp < 54 V |
| 5 V | TPS54360B (60 V, 3.5 A) + 10 µH + B560C | TI 5 V reference design, RT 150k ≈ 640 kHz, FB 120k/22k → 5.16 V |
| 3.3 V | AMS1117-3.3 | logic only |
| MCU | ESP32-S3-MINI-1-N8 | antenna at the rear edge, keep-out on all layers |
| DUT power | TPS2553 (RILIM 18k → 1.34–1.52 A), 50 mΩ shunt, INA226 @0x40 | default **on** (also without firmware), fault flag to GPIO |
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

24 V screw terminal → SUD50P06 reverse protection → SMCJ33A → 2 × 220 µF →
5 × TPS26600 eFuse (2.1 A, 4 ms soft start, auto-retry, UV/OV defaults) →
5 × JST VH (rows A–D + AUX), each with ON (green) and FAULT (red) LEDs.
SHDN/FLT/IMON of every channel go to an unpopulated 2 × 8 header for a future
supervisor.

## Sourcing

Every non-generic part carries `MPN`, `Manufacturer` and `LCSC` fields
(verified against JLCPCB's live library on 2026-10-16 through the
`@jlcpcb/mcp` server — see `tools/jlc_mcp.py`).  Generic passives are
resolved to JLC **basic** parts by `electronics/tools/passives.py` (cached in
`electronics/lib/passives.json`); values were nudged to basic-library E-series
where it didn't matter (e.g. 150k RT, 120k/22k FB).

`--fab` writes, per board:

* `fab/<board>-gerbers.zip` (Gerber X2 + Excellon), ready for JLCPCB/PCBWay;
* `fab/<board>-bom-jlcpcb.csv` and `fab/<board>-cpl-jlcpcb.csv` (PCBA);
* `<board>-bom.csv` (detailed: MPN, manufacturer, LCSC, alternatives);
* `docs/<board>-schematic.pdf`, SVGs, top/bottom/iso renders;
* `fab/<board>.step` and `fab/<board>.glb` (the web viewer uses the GLB).

Through-hole parts (JST VH, KF128) need JLC's THT service or a soldering iron.

## Custom library

`electronics/lib/bench.kicad_sym` holds the one symbol the stock library
lacks (TPS2553DBV).  All footprints and 3D models come from KiCad 10's
standard libraries.
