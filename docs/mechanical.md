# Mechanical design

Everything is parametric OpenSCAD driven by
[`config/rack.yaml`](../config/rack.yaml) → `mechanical/generated/config.scad`
(`python tools/build.py config`).  Printable STLs: `python tools/build.py stl`
(OpenSCAD from `PATH`, or the `openscad/openscad` Docker image).  Every part
prints **without supports**; the row ladders (203 × 241 mm) need a 256 × 256 mm
bed (Bambu X1/P1/A1, H2D …), everything else fits 250 × 210.

## Frame: the panel frame

Every part is printed: no aluminium, no screws in the structure except the rear
braces', and the grid grows in both directions.  Side walls ("ladders") stand
between the bays and are shared by both neighbours; trays slide into their
grooves; an X brace behind every bay and row keeps the grid square.

| Part | File | Notes |
|---|---|---|
| Ladder | `ladder.scad` (`PART="row"`, `ROW=k`) | side wall between two bays, one per row: front and rear posts, a bottom band with the tray grooves (both faces), a top band, one brace; stacks on the ladder below with a ridge/notch joint and two in-plane snap hooks (release through the window); 4 heat-set inserts in the rear edge |
| Base ladder / cap strip | `ladder.scad` (`"base"`, `"cap"`) | floor → row A (holds a floor plate); the strip on top holds the cap plate |
| Floor / cap plate | `tray.scad` (`PART="floor_plate"`, `"cap_plate"`) | the tie between the base ladders and the top row's ceiling: a regular 30 mm grid (the camera pod's pitch) with an M3-insert boss at every crossing, so a pod (or anything else) mounts on any square of crossings |
| Rear brace | `brace.scad` (`ROW=k`, `-1` for the base) | an X behind each bay and level, screwed (4 × M3×8 pan head, Phillips) into the inserts in the rear edges of its two ladders; left and right holes at different heights, so neighbouring braces share a ladder.  No slack: snug 3.1 mm holes, and each diagonal is 0.25 mm short, so the X is taut once the fourth screw is in |

The column pitch is 165.8 mm: a 158 mm tray, a 7.4 mm ladder and 0.2 mm of
clearance on each side (`frame.panel_thickness`, `frame.panel_clearance`).
Rows are stacked with `rows[].height` of vertical pitch and tilted by
`frame.tilt` (20°, a stadium: every board, LED and label faces you).  The
default 4 × 3 rack is 671 × 225 × 664 mm.

![Side view: the 20° stadium rows, bay C2 pulled out](img/side.jpg)

`python tools/panel_frame_fea.py` models the grid from the front (ladder
sections from the meshes, runner play as a dead band, tension-only braces with
pin slack).  Slack decides: a 4 × 4 sways ≈ 8 mm without braces, ≈ 2 mm with
braces on loose pins, and ≈ 0.16 mm under 2 N with taut braces, whatever the
runner play.  (`python tools/panel_proto.py` renders the parts and the
constants it reads.)

## Bay

![Bay C2's drawer pulled out, still wired through its drag chain](img/drawer.jpg)

| Part | File | Notes |
|---|---|---|
| Tray | `tray.scad` | the plenum under the drawer: node standoffs, chain anchor and rails, fascia with the PC port / LED / SERVICE switch, camera inserts underneath.  The drawer rides on two side ledges under C-channel lips; runners on both walls slide into the ladder grooves from the front, and a flex arm per wall clicks a barb into the groove's window (pull the drawer out, press both arms to remove the tray) |
| Drawer | `drawer.scad` | 142 × 196 mm; front panel with label recess (printed `bay_label`, or 12 mm tape) and finger pull; plate pocket with two 180°-symmetric pins; open floor under the plate; rear bay with two DATA panel-socket positions (left/right, the socket goes in the one farther from the board's USB) and the AUX slot, cable window and the foot groove |
| Chain foot / anchor | `chain_parts.scad` | the foot slides into the drawer's rear-open groove and is locked by one M2.5 from inside the rear bay; a printable 7×7 link is included if you'd rather not buy chain |
| Board plates | `board_plate.scad` | one per form factor, generated from [`mechanical/boards/boards.yaml`](../mechanical/boards/boards.yaml) |
| Bay label | `label.scad` | 12 × 100 mm blank for the drawer front's recess |

![One bay pulled apart: tray with the node and the drag chain, drawer, board plate, board, camera pod](img/exploded.jpg)

### Drawer motion

The drawer slides 140 mm along the slope on the tray's two ledges (PETG on
PETG); its rear flange segments run under the lips, so it cannot tip at full
stroke.  A pair of 6 × 3 mm magnets (one in the drawer, one in the left ledge,
on a pad) holds it closed against the slope; pulled out, it rests on an M2.5
stop screw through the left lip, the flange still under the lips.  Want
smoother?  Print the trays in a POM-like "igus" filament.

### Plates (form factors)

`boards.yaml` holds each board's outline, holes (in the vendor drawing's
coordinates), debug-USB edge and standoff height (Nucleo morpho pins stick
out ~10 mm underneath!).  The generator rotates the board so its debug USB
faces the drawer's port wall; a board too long for a plug behind it
(`orient: side`, e.g. the F746G-DISCO) turns its USB towards the right wall
and sits to the left of its plate.  Mounting styles:

* `MODE="insert"` heat-set inserts (M3, M2.5 or M2 picked from the hole size);
* `MODE="snap"` split snap pins — push the board on, pinch to release;
* hole-less boards (or ones not measured yet: `verified: false`) get corner
  fences + support pads;
* `plate_universal` has M3 slots on a 12 mm grid for anything else.

Verified outlines today: UNO R4, NUCLEO-64, NUCLEO-144, Pico/Pico 2,
ESP32-S3/C6-DevKitC, XIAO, micro:bit.  Nordic DKs, FRDM, Discovery and i.MX
EVKs use fences until someone measures them — PRs welcome.

## Cameras

`camera_pod.scad`: a mount (4 × M3 into the inserts under the ceiling: the
bottom of the tray above, or the cap plate) and a tilting cradle for a Seeed
XIAO ESP32S3 Sense, lens down.  The insert pattern is offset from the bay
centre (it dodges the node and the chain in the plenum above), so aim with the
±35° pivot.  Use a ≥ 120° lens: at ~90 mm a stock 66° lens only covers
~94 × 70 mm.  5 V comes from the node in the tray the pod hangs from (JST-PH
`CAM`, PTC-protected); top-row pods hang under the cap plate and take 5 V from
their own bay through the tray's rear service slot.

## Power box

The base cell under A1 is otherwise dead space: 154 mm between the floor
plate's walls, ≈ 196 mm deep, ≈ 70 mm high at the front, rising with the 20°
slope.  `power_box.scad` puts the power hub there, in a box against the
cell's left side; the rack's supply is a USB-C PD charger outside the rack.
Placement and sizes: `config/rack.yaml` › `power_box`; the charger, the
negotiation and the budget: [power.md](power.md).

![The power box under A1](img/power-box.jpg)

*Lid off.  Left: from the rear, the charger's USB-C cable and the row outputs' cut-outs.  Right: from the front, the status LEDs (ON / FAULT per row, PD, CTL) and the console USB-C.*

| Part | File | Notes |
|---|---|---|
| Base | `power_box.scad` (`PART="base"`) | 84 × 148 × 33 mm, against the cell's left side. Under the floor are sockets that drop over the floor plate's insert bosses beneath it: it locates without screws, and an M3 through each socket screws it down if wanted. Lift it over the plate's front lip to put it in. **Left wall:** cut-outs for the hub's four 6-pin JST PH row outputs (A–D, engraved), reached from the rack's left side through the base ladder's window. **Front wall:** windows for the hub's ON / FAULT LEDs per row, PD and CTL, and the controller's console USB-C. **Rear wall:** the USB-C PD input (the charger's cable) and vents. Inside: four standoffs with M3 inserts for the hub, and four corner lugs with M3 inserts for the lid, hanging above the hub with 45° undersides |
| Lid | `power_box.scad` (`PART="lid"`) | printed top face down. A rim locates it inside the walls, and 4 × M3×8 go into the corner lugs. Vents over the PD input and the buck, the name engraved in the top face |

Both print without supports (PETG, 3 walls).  VRACK reaches the first node
of each row through one 6-pin JST PH feed ([cabling.md](cabling.md#row-power)); 6-pin
jumpers carry it, and the CAN bus, from node to node through the windows in
the tray walls and the shared ladder.

## Not designed yet

* Double-width bays for i.MX-class EVKs (the aluminium frame had them): a
  324 mm tray and drawer, no ladder in between.
* Rows taller than 165 mm: a 185 mm row makes a 261 mm ladder (an H2D-class bed).

## Checks

An interference check of one assembled bay (exact solids from the OpenSCAD
sources, SolidCraft's `inspect.interference`) finds no overlaps; it caught the
drawer's magnet boss hitting the tray's guide lip in the last 10 mm before the
fix.  Contacts between the ladders, plates, trays and braces are the designed
bearing faces.

## Printing

| | |
|---|---|
| Material | PETG |
| Layer | 0.2 mm, 3 walls, 15 % gyroid (braces: 100 %, they are mostly perimeter) |
| Inserts | Ruthex-type M3 × 5.7 (Ø4.0 holes), M2.5, M2 |
| Filament | see the BOM.  Sliced (Bambu Studio, H2D, 0.20 mm Standard, PETG): a bay on its own ≈ 480 g, each bay added beside it ≈ 375 g, each extra cell in a large grid ≈ 210 g (tray 100 g, drawer 56 g, ladder 44 g, brace 8 g) |

Orientation is baked into the exported STLs (`mechanical/stl/`).
