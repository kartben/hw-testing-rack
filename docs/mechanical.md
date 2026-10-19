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
| Floor / cap plate | `tray.scad` (`PART="floor_plate"`, `"cap_plate"`) | the tie between the base ladders and the top row's ceiling: a regular 30 mm grid (the camera pod's pitch) with an M3-insert boss at every crossing: the top row's pods take the same square as under a tray (x 94/124, y 30/60), anything else any square |
| Rear brace | `brace.scad` (`ROW=k`, `-1` for the base) | an X behind each bay and level, screwed (4 × M3×8 pan head, Phillips) into the inserts in the rear edges of its two ladders; left and right holes at different heights, so neighbouring braces share a ladder.  No slack: snug 3.1 mm holes, and each diagonal is 0.25 mm short, so the X is taut once the fourth screw is in |

The column pitch is 165.8 mm: a 158 mm tray, a 7.4 mm ladder and 0.2 mm of
clearance on each side (`frame.panel_thickness`, `frame.panel_clearance`).
Rows are stacked with `rows[].height` of vertical pitch and tilted by
`frame.tilt` (20°, a stadium: every board, LED and label faces you).  The
default 4 × 3 rack is 671 × 225 × 664 mm.

![Side view: the 20° stadium rows, bay B3 pulled out](img/side.jpg)

`python tools/panel_frame_fea.py` models the grid from the front (ladder
sections from the meshes, runner play as a dead band, tension-only braces with
pin slack).  Slack decides: a 4 × 4 sways ≈ 8 mm without braces, ≈ 2 mm with
braces on loose pins, and ≈ 0.16 mm under 2 N with taut braces, whatever the
runner play.  (`python tools/panel_proto.py` renders the parts and the
constants it reads.)

## Bay

![Bay B3's drawer pulled out, still wired through its drag chain](img/drawer.jpg)

| Part | File | Notes |
|---|---|---|
| Tray | `tray.scad` | the plenum under the drawer: node standoffs, chain anchor and rails, two pairs of lock-screw holes through the guide lips (a sled bay's port block and sled; in a drawer bay the first pair locks the drawer shut for carrying), fascia with the PC port / LED / SERVICE switch (the PC port is the USB-C stadium scaled up to 13.4 × 7.8 mm, so a plug's overmold passes: the node's receptacle sits 2.7 mm behind the fascia's face), camera inserts underneath; a notch in the left ledge over the node's RESET button (drawer pulled out, press it with a pin).  The drawer rides on two side ledges under C-channel lips; runners on both walls slide into the ladder grooves from the front, and a flex arm per wall clicks a barb into the groove's window (pull the drawer out, press both arms to remove the tray) |
| Drawer | `drawer.scad` | 142 × 196 mm; front panel with label recess (printed `bay_label`, or 12 mm tape) and finger pull; plate pocket with two 180°-symmetric pins; open floor under the plate; rear bay with the DATA port: our board (electronics/data-port) components up on two floor bosses, 2 × PT 2.6×8 from above, its front edge against the port wall (a ledge under it either side of the USB-C's pegs); its USB-C, 8.5 mm above the drawer bottom and 1.7 mm behind the wall's front face, in a U cut down through the wall's top (the USB-C plug cut's 13.4 mm, open upwards): a straight plug's overmold or a right-angle plug's body goes in until the plug seats.  The board stops left of the chain foot's lock screw (driven from above).  The cable window behind it, up to the rear wall, the AUX slot and the foot groove.  Pin holes over the node's RESET and BOOT, as in every plate: press them with the drawer in |
| Sled / port block | `drawer.scad` (`PART="sled"`, `"block"`) | a bay without a drag chain (`population` › `mount: sled` or `fixed`, same tray): the drawer cut 1 mm in front of its port wall.  The **sled** (its front and two flange segments at its rear; its floor ends open under the plate) slides on the same ledges, the stop screw limiting it (≈ 110 mm); unplug the DUT cable, then pull it.  The **port block** (the drawer's rear bay: port wall, DATA board, cable window) stays behind it, locked by 2 × PT 2.6×8 through the guide lips and its flanges into the ledges; its DATA lead comes straight from J7 (≈ 22 cm).  A **fixed** bay is a sled bay with 2 × PT 2.6×8 more through the sled's flanges.  `-D PORTS=4` gives a block with four USB-C at a 16 mm pitch for a DATA ×4 board (placeholder: no board yet).  No chain, foot, anchor or magnets: ≈ €2–3.5 and the chain steps saved per bay; back to a drawer at any time |
| Chain foot / anchor | `chain_parts.scad` | take the chain's end pieces (tab with 2 holes 8 mm apart, PT 2.6×8 + washers).  The anchor is a block outside the fixed run, on two M3 inserts in the tray; the foot carries the moving end on a fin outside the moving run and slides into the drawer's rear-open groove, locked by one PT 2.6×8 from inside the rear bay.  A printable link (and its removable bar, so the cable can be laid in) is included if you'd rather not buy chain |
| Board plates | `board_plate.scad` | one per form factor, generated from [`mechanical/boards/boards.yaml`](../mechanical/boards/boards.yaml) |
| Bay label | `label.scad` | 12 × 100 mm blank for the drawer front's recess |

![One bay pulled apart: tray with the node and the drag chain, drawer, board plate, board, camera pod](img/exploded.jpg)

### Drawer motion

The drawer slides 140 mm along the slope on the tray's two ledges (PETG on
PETG); its rear flange segments run under the lips, so it cannot tip at full
stroke.  A pair of 6 × 3 mm magnets (one in the drawer, one in the left ledge,
on a pad) holds it closed against the slope; pulled out, it rests on a PT 2.6
stop screw through the left lip, the flange still under the lips.  Want
smoother?  Print the trays in a POM-like "igus" filament.

The magnet pockets are a slip fit (Ø + 0.25 mm): **glue the magnets**, a drop
of CA gel in each pocket.  The other magnet pulls each one out through its
pocket's mouth, and the drawer's boss leaves a 0.9 mm wall around its pocket,
too thin to press-fit into.  **Check the polarity first**: stack the pair, mark both outer
faces, and glue the marked faces into the pockets, so the two bare faces
attract.

### Drag chain

The reference is Olimex's DRAG-CHAIN-7X7 (€4/m): 7 × 7 mm inside, links
that open on both sides, so the DATA lead can be laid in (its PH plugs,
12 mm wide, do not pass through).  Olimex publishes only the inner size;
the model takes the outer size (13.5 × 10.2 mm) and the end pieces (a tab
with 2 holes 8 mm apart) from Electrokit's listing of the same generic chain
(41017996).  The bend radius is not published anywhere: the model keeps
R18.  **Measure the chain on arrival** and set `config/rack.yaml › chain`:
`outer`, `radius`, `end_holes` and `end_length`, the rigid length of an end
piece from its mouth to its pivot on the chain.  Olimex sells it by the metre
and, like every seller of this generic chain, with one pair of end pieces per
metre; it does not sell them alone, so the other drawers' pairs come from
AliExpress (see the BOM).

The chain lies flat in the plenum, its side plates horizontal, so the end
pieces' tabs stand vertical on the outer faces of the U: the fixed one
against the anchor block, the moving one against the foot's fin (2 × PT 2.6×8
and washers each).  The runs are 36 mm apart (2 × R), 13.5 mm tall from 3 mm
above the tray floor, under the drawer with 6.5 mm to spare; low rails keep
them straight.  An end piece cannot bend, so it must stay in a straight run
over the whole stroke: the moving end with the drawer closed, the fixed end
with it open.  That sets the moving end's mouth 26 mm in front of the bend
(157 mm from the drawer front), and the U still clears the tray's rear wall
by 1.9 mm.  `lib/carrier.scad` asserts all three, so a measured chain that
does not fit stops the build instead of printing parts that clash.  Checked
in Blender over the 140 mm stroke: the chain, the anchor, the foot, the
drawer, the node and the DUT plug never overlap.

### Plates (form factors)

`boards.yaml` holds each board's outline, holes (in the vendor drawing's
coordinates), debug-USB edge and standoff height (Nucleo morpho pins stick
out ~10 mm underneath!).  The generator rotates the board so its debug USB
faces the drawer's port wall.  `orient: side` turns it towards the right wall
instead, the board 2.5 mm from the plate's left edge: for a board too long for
a plug behind it (the F746G-DISCO), and for the small ones (Pico, ESP32
DevKitC, UNO R4), whose cable from the DATA port is then straight at
both ends and lies flat ([cabling.md](cabling.md)).  Mounting styles:

* `MODE="insert"` heat-set inserts (M3, M2.5 or M2 picked from the hole size);
* `MODE="snap"` split snap pins — push the board on, pinch to release;
* hole-less boards (or ones not measured yet: `verified: false`) get corner
  fences + support pads;
* `plate_universal` has M3 slots on a 12 mm grid for anything else.

Verified outlines today: UNO R4, NUCLEO-64, NUCLEO-144, Pico/Pico 2,
ESP32-S3/C6-DevKitC, XIAO, micro:bit.  Nordic DKs, FRDM, Discovery and i.MX
EVKs use fences until someone measures them — PRs welcome.

## Cameras

`camera_pod.scad`: two printed parts under the ceiling (the bottom of the tray
above, or the cap plate) for an Arducam Mega 3MP SPI camera in its case (B0434,
a ~120° M12 lens) and the pod board right behind it
([electronics/camera-pod](../electronics/camera-pod/): the PH-8 lead's J1, the
Mega's header J2, four white LEDs along the edge beside the camera: nothing to
solder).  The **pod** (dark PETG, opaque) takes 4 × M3×6 into the camera
inserts (`bay.camera_mount`: a 30 mm square right of the node above, clear of
its drag chain, on the cap plate's grid, so one pod fits every row) and reaches
45 mm left to the lens spot (`bay.camera_lens`, bay (64, 84) below): a sleeve
the Mega's case snaps into from below (two lips, its XH side open), lens down,
the lens tip ≈ 30 mm under the ceiling (Z ≈ 125, well over the DUT cables'
≤ 105 mm arches).  The sleeve's rear wall goes on down as the baffle between the
LEDs and the lens; the pod board sits behind it, components down, its LED edge
against it (`pcb.camera_pod`).  The **diffuser** (white PETG) is a 1 mm floor
7 mm under the LEDs (glare on screens and glossy boards) on two posts that clamp
the board to its standoffs (2 × PT 2.6×14 through both), open round J2's Dupont
housing.  The Mega's case is a placeholder (`MEGA_*`: Arducam gives 33 × 33 mm,
35 mm with the stock M12, no drawing): measure the first one before printing.
The camera runs from the bay's **own** node (J6, JST-PH 8), its lead through
the tray's rear slot and up under the ceiling ([cabling.md](cabling.md)).  Print
the pod upside down, the diffuser floor down; no supports.

## Power box

The base cell under A1 is otherwise dead space: 154 mm between the floor
plate's walls, ≈ 196 mm deep, ≈ 70 mm high at the front, rising with the 20°
slope.  `power_box.scad` puts the power hub there, in a box against the
cell's left side; the rack's supply is a USB-C PD charger outside the rack.
Placement and sizes: `config/rack.yaml` › `power_box`; the charger, the
negotiation and the budget: [power.md](power.md).

![The power box under A1](img/power-box.jpg)

*Lid off, labels inlaid in white.  Left: from the rear, the charger's USB-C cable (PD IN) and the row outputs' windows (A–D).  Right: from the front, the status LEDs (ON / FAULT per row, PD, CTL) and the console USB-C.*

| Part | File | Notes |
|---|---|---|
| Base | `power_box.scad` (`PART="base"`) | 84 × 148 × 33 mm, against the cell's left side. Under the floor are sockets that drop over the floor plate's insert bosses beneath it: it locates without screws, and an M3 through each socket screws it down if wanted. Lift it over the plate's front lip to put it in. **Left wall:** windows for the hub's four 6-pin JST PH row outputs, each with its row letter (A–D) above it, reached from the rack's left side through the base ladder's window. **Front wall:** holes for the hub's ON / FAULT LEDs per row (A–D under them), the PD LED (PD over it) and the controller's LED and console USB-C (CTL under them). **Rear wall:** the USB-C PD input (PD IN) and vents. Both USB-C openings take the plug's overmold (12.4 × 7 mm), as the receptacles sit 3.3 / 4.1 mm behind the walls' outer faces. Labels are engraved 0.8 mm deep, 5.25 mm capitals with 1.1 mm strokes. Inside: four standoffs (Ø8) with M3 inserts for the hub; nothing overhangs the hub, which drops straight in |
| Lid | `power_box.scad` (`PART="lid"`) | printed top face down. A rim locates it inside the walls, and 4 × M3×6 go into the M3×12 male-female hex spacers that hold the hub down (their tops are flush with the walls). Vents over the PD input and the buck, the name engraved in the top face. Two pin holes (RESET, BOOT, engraved beside them) with guide tubes down to 1 mm above the hub's buttons: recover the controller with the box closed |
| Label inlays (optional) | `power_box.scad` (`PART="labels"`, `"lid_labels"`) | exactly the engravings' volume: load each with its part as one object (two parts) and give it the second nozzle's filament. White letters flush in a black box read at a glance; engraved in one colour, the labels only show under grazing light |

Both print without supports (PETG, 3 walls).  Print the base at 0.12–0.16 mm layers: its
labels stand on vertical walls, where the layer height sets their vertical definition (a 5.25 mm
capital is 33–44 layers instead of 26 at 0.2 mm).  VRACK reaches the first node
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
