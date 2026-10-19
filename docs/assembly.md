# Assembly

Order of work for the default build: 8 bays, 4 columns × 2 rows.  Quantities:
[`bom/README.md`](../bom/README.md).  An illustrated, IKEA-style notice (one bay,
then adding the next one) is drawn from the same models by
[`tools/notice/`](../tools/notice/README.md).

## 1. Print and prepare

`python tools/build.py stl` → `mechanical/stl/` (or grab the STL bundle from
the latest CI run).

* Per column boundary: `ladder_base`, one ladder per row (`ladder_a`,
  `ladder_b`, `ladder_c`: their heights differ) and a `ladder_cap`.
* Per column: `floor_plate`, `cap_plate`, one brace per level (`brace_base`,
  `brace_a` …).
* Per bay: `tray`, `drawer`, `chain_foot`, `chain_anchor`, one board plate,
  `bay_label`.

Heat-set inserts (M3 × 5.7) while the parts are on the bench: 4 in the rear
edge of every base and row ladder (the braces screw into them), 4 in each
tray's node standoffs and 2 in its chain anchor, 4 under the ceiling of every
bay (the tray above, or the cap plate: a camera pod's mount, so a pod can go
in any bay later).

## 2. The first bay

1. Two **base ladders** upright; the **floor plate** slides in from the front,
   into their bottom grooves.
2. **Base brace** at the back: 4 × M3×8 pan head into the rear-edge inserts
   (the 1st and 3rd on the left ladder, the 2nd and 4th on the right one).
   Each diagonal is 0.25 mm short: the X is taut once the fourth screw is in.
3. **Row ladders** onto the base ladders: ridge into notch, the two snap hooks
   click.  (Release a hook by pushing its barb through the window.)
4. **Tray** from the front: its runners slide into the ladder grooves until
   the barbs click into the groove windows.
5. **Row brace**: 4 × M3×8, as in step 2.
6. More rows: steps 3–5 again.
7. **Cap strips** on the top ladders; the **cap plate** slides into their grooves.

## 3. The next bay

It shares the middle ladder: one more ladder per level.  Base ladder on the
right and floor plate; base brace into the free inserts of the shared ladder
(its 1st and 3rd); then row ladders, trays and braces; cap strip and cap plate.

## 4. Inside each bay

1. **Node** onto the tray standoffs (4 × M3×6).
2. **Drag chain**: cut ≈ 180 mm including the two end pieces (Olimex
   DRAG-CHAIN-7X7).  At the bench, screw the fixed end piece to the
   `chain_anchor` and the moving one to the `chain_foot`'s fin, each with
   2 × PT 2.6×8 and washers, tab against the part's flat face.  Open the links,
   lay the drawer extension cable in ([cabling.md](cabling.md)) and close them.
   Anchor onto the tray: 2 × M3×8 into its inserts; plug the cable's male end
   into the node's DUT port.
3. **Row power (VRACK)**: JST PH jumper to the neighbouring node, through the windows in
   both tray walls and the shared ladder; the row feed goes into the row's
   first bay.
4. **Drawer**: magnets first, one under the drawer and one in the tray's left
   ledge: stack the pair, mark both outer faces, glue each magnet marked face
   down into its pocket with a drop of CA, and let it set before the drawer
   goes in.  The DATA port board goes on the two bosses in the rear bay,
   components up, its USB-C edge against the port wall (the receptacle
   behind the wall's U), 2 × PT 2.6×8 from above; plug the DATA lead into
   its PH from the rear, the wires down through the cable window behind it;
   slide the drawer
   in from the front onto the tray's ledges (its rear flange under the guide
   lips), engage the foot in the rear groove and lock it with the M2.5 from
   inside the rear bay (PT 2.6×8); then the PT 2.6×8 stop screw through the left guide lip.
5. **Plate + board + short cable**, printed `bay_label` (or 12 mm tape) in the
   front recess.

A **sled or fixed bay** (`mount: sled` / `fixed`) skips steps 2 and 4: no chain,
anchor (nor its two inserts), foot or magnets.  The DATA board goes into the
`drawer_block` as into a drawer's rear bay; the DATA lead (the same 50 cm PH 8)
runs from J7 back along the plenum and up through the block's window into its
PH, its slack coiled in the plenum.  Slide the
block in onto the ledges to the rear (its flanges under the guide lips) and lock
it: 2 × PT 2.6×8 down through the guide lips and its flanges into the ledges,
at the holes level with them.  Then the `drawer_sled`, and the stop screw; for a
fixed bay, 2 × PT 2.6×8 more through the lips into the sled's flanges.

To take a tray out: pull the drawer out, press both latch arms inwards, slide
the tray forwards.

## 5. Power

The power box ([mechanical.md](mechanical.md#power-box)):

1. Heat-set the 4 inserts in the hub standoffs, from above (the box is open: the iron reaches
   each standoff, 13.6 mm down, ≥ 4.7 mm from the walls).
2. Lower the hub straight in, its USB-C PD input towards the rear wall, and screw the 4 M3×12
   male-female hex spacers through its holes into the inserts (by hand or with pliers: the row
   connector next to the front-left hole leaves no room for a 5.5 mm socket).
3. Lid on: its rim inside the walls, 4 × M3×6 into the spacers.
4. Lift the box over the floor plate's front lip under A1 and let its sockets
   drop over the bosses.
5. The charger's 5 A e-marked USB-C cable into the rear port, out of the back
   through the base brace, to a dedicated USB PD 3.1 charger (140 W EPR
   recommended, [power.md](power.md#the-charger)).

On first power-up, check the front **PD** LED: breathing = contract in place,
steady = the charger can't give what was asked, flicker = a fault.  Rows stay
off until the controller's firmware turns them on; with it running, check that
every row's ON LED lights.  Then plug the row feeds through the left base
ladder's window, run them up the left side and into each row's first node.

## 6. Cameras (optional)

At the bench: the pod board on its two standoffs behind the sleeve, LEDs
down, against the baffle, and the diffuser under it (2 × PT 2.6×14 up through
its posts and the board); the XH → Dupont cable into the Mega's side and onto
J2 by name.  Pod under the ceiling, 4 × M3×6 into the camera inserts (the tray
above, or the cap plate); push the Mega's case up into the sleeve until the
lips click, lens down, its XH on the open side.  The lead
([cabling.md](cabling.md)) into the bay's own node (J6), back through the
plenum and the tray's rear slot, straight up behind the tray, forwards under
the ceiling (a cable tie every ~5 cm) and into the board's J1.

## 7. Bring-up

Per node: SERVICE on → laptop on the PC port → flash → SERVICE off.  Then
`usbip list -r bay-<id>.local`.  See [firmware.md](firmware.md).  With a
camera: focus its lens on the plate from the bay page's live view, then
lock the nut ([firmware/README.md › Camera](../firmware/README.md#camera)).
