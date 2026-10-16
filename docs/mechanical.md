# Mechanical design

Everything is parametric OpenSCAD driven by
[`config/rack.yaml`](../config/rack.yaml) → `mechanical/generated/config.scad`
(`python tools/build.py config`).  Printable STLs: `python tools/build.py stl`
(OpenSCAD from `PATH`, or the `openscad/openscad` Docker image).  Every part
is designed to print **without supports** on a 250 × 210 mm bed (Prusa MK4,
Core One, Bambu …).

## Frame

* **2020 aluminium extrusion**, B-type slot 6 (Motedis, Dold, Misumi HFS5).
  Four corner posts (front ones shorter: it's a stadium), two beams per row,
  a closed base box at the bottom.  Cut list in [`bom/README.md`](../bom/README.md).
* **Tier brackets** (`tier_bracket.scad`, one pair per row and one for the
  roof) hold the row's front and rear beams at `frame.tilt` (20°).  Each bolts
  to the inner slot of the front and rear post (2 × M5 + T-nut each); beams
  butt into 3 mm pockets and are pulled in by an M5 into their tapped core.
  `tilt: 0` gives a classic flat shelf with the same parts.
* Rows are stacked with `rows[].height` of vertical pitch.  Parallel tilted
  rows are staggered by `height·sin(tilt)` along the slope, so the front of
  every bay is open upwards (easy access) and a bay's ceiling starts ~55 mm
  behind its front edge.

![Side view: the 20° stadium rows, bay C2 pulled out](img/side.jpg)

## Bay

| Part | File | Notes |
|---|---|---|
| Carrier base | `carrier_base.scad` | plenum box on the beams; node standoffs, chain anchor, deck pillars, fascia cut-outs, camera inserts underneath, VH notches in both side walls |
| Deck | `carrier_deck.scad` | removable floor; guide screws, chain-foot slot, detent magnet, vents over the buck, window over RESET/BOOT |
| Drawer guides L/R | `drawer_guide.scad` | C-channels; capture the drawer's rear flange (anti-tip at full stroke); an M2.5 screw through the lip is the end stop |
| Drawer | `drawer.scad` | 142 × 196 mm; front panel with label recess (printed `bay_label`, or 12 mm tape) and finger pull; plate pocket with two 180°-symmetric pins; rear bay with the DATA panel port (+ AUX slot), cable window and the foot groove |
| Chain foot / anchor | `chain_parts.scad` | the foot slides into the drawer's rear-open groove and is locked by one M2.5 from inside the rear bay; a printable 7×7 link is included if you'd rather not buy chain |
| Board plates | `board_plate.scad` | one per form factor, generated from [`mechanical/boards/boards.yaml`](../mechanical/boards/boards.yaml) |
| Bridge bars | `bridge_bar.scad` | lock two neighbouring drawers into one double-width drawer |

### Drawer motion

The drawer slides 140 mm along the slope on its bottom (PETG on PETG, with
shallow grooves in the deck to keep dust from skating).  A pair of 6 × 3 mm
magnets (drawer + deck) holds it closed against the slope; pulled out, it
rests on the two stop screws with the flange still under the guide lips.
Want smoother?  Print the guides in a POM-like "igus" filament.

### Plates (form factors)

`boards.yaml` holds each board's outline, holes (in the vendor drawing's
coordinates), debug-USB edge and standoff height (Nucleo morpho pins stick
out ~10 mm underneath!).  The generator rotates the board so its debug USB
faces the drawer's DATA port.  Mounting styles:

* `MODE="insert"` heat-set inserts (M3, M2.5 or M2 picked from the hole size);
* `MODE="snap"` split snap pins — push the board on, pinch to release;
* hole-less boards (or ones not measured yet: `verified: false`) get corner
  fences + support pads;
* `plate_universal` has M3 slots on a 12 mm grid for anything else.

Verified outlines today: UNO R4, NUCLEO-64, NUCLEO-144, Pico/Pico 2,
ESP32-S3/C6-DevKitC, XIAO, micro:bit.  Nordic DKs, FRDM, Discovery and i.MX
EVKs use fences until someone measures them — PRs welcome.

### Double-width bays (big EVKs)

A double bay is two standard units side by side — two carriers, two decks,
four guides, **two standard drawers**, two drag chains, one or two bay nodes.
Two **bridge bars** sit across both drawers (dropping onto their plate pins)
so they slide as one; the EVK goes on M3 standoffs anywhere along the bars'
slots.  The second node gives the EVK its second USB cable (power / OTG).
Bridge bars are 298 mm long: print them diagonally.

## Cameras

`camera_pod.scad`: a mount (4 × M3 into the inserts under the ceiling) and a
tilting cradle for a Seeed XIAO ESP32S3 Sense, lens down.  The insert pattern
is offset from the bay centre (it dodges the node and the chain in the plenum
above), so aim with the ±35° pivot.  Use a ≥ 120° lens: at ~90 mm a stock
66° lens only covers ~94 × 70 mm.  5 V comes from the node in the carrier the
pod hangs from (JST-PH `CAM`, PTC-protected); top-row pods hang under the
roof deck and take 5 V from their own bay through the rear service slot.

## Base

`base.scad`: four floor plates on the bottom beams (M3 grid), two PSU
saddles, the rear inlet panel (Schurter DD11 cut-out, Power-DIN knock-out
for the brick variant), vented front/side panels, the hub mount and the
mains cover.  See [power.md](power.md) for the safety rules.

## Printing

| | |
|---|---|
| Material | PETG (ASA/PC-blend near mains); TPU for feet |
| Layer | 0.2 mm, 3 walls, 15–20 % gyroid (tier brackets: 4 walls, 40 %) |
| Inserts | Ruthex-type M3 × 5.7 (Ø4.0 holes), M2.5, M2 |
| Filament | ≈ 5–6 kg for the default 14-bay build (see the BOM) |

Orientation is baked into the exported STLs (`mechanical/stl/`).
