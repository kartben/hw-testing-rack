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
* Per bay: `tray`, `drawer`, `chain_foot`, `chain_anchor`, the board `plate`
  and the pegs its boards need (`python tools/plate_layout.py <bay>`), its label
  (`bay_label_<bay>` and `bay_label_<bay>_inlay`, one object in two colours:
  [mechanical.md](mechanical.md), Bay label).

Heat-set inserts (M3 × 5.7) while the parts are on the bench: 4 in each
tray's node standoffs and 2 in its chain anchor, 4 under the ceiling of every
bay (the tray above, or the cap plate: a camera pod's mount, so a pod can go
in any bay later).

## 2. The first bay

1. Two **base ladders** upright; the **floor plate** slides in from the front,
   into their bottom grooves.
2. **Base brace** at the back: first push an M3 square nut (DIN 562) into each
   pocket by the ladders' rear edges, from the face it opens to (a small rib
   holds it while the ladder stands; the pockets are behind the trays, so they
   stay reachable from the back at every level), then 4 × M3×8 pan head
   through the brace into the nuts (the 1st and 3rd on the left ladder, the
   2nd and 4th on the right one).
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
right and floor plate; base brace into the free nuts of the shared ladder
(its 1st and 3rd); then row ladders, trays and braces; cap strip and cap plate.

## 4. Inside each bay

Fit each bay's tray at the bench, out of the frame (steps 1, 2, 4 and 5), then
slide it into its place and do step 3.  Once the tray is in, no screwdriver
reaches the guide lips' screws (the stop screw, a sled bay's locks): they sit
5 mm from the side ladder and 2.6 mm from the drawer's wall.  To convert a bay
later, take its tray out first.

1. **Node** onto the tray standoffs (4 × M3×8).  Its two left screws sit under
   the left guide: feed each one through the guide's hole above it on a
   magnetic PH bit (shaft Ø ≤ 5 mm) and drive it there, the drawer still out.
2. **Drag chain**: cut ≈ 180 mm including the two end pieces (Olimex
   DRAG-CHAIN-7X7).  At the bench, screw the fixed end piece to the
   `chain_anchor` and the moving one to the `chain_foot`'s fin, each with
   2 × PT 2.3×8 and washers, tab against the part's flat face.  Check the
   DATA lead with a meter first: pin n to pin 9−n on all 8 ("Same direction";
   a 1:1 lead puts the node's SCL on GND; the camera's PH 8 lead the same, its
   MOSI and CS).  Open the links, lay the lead in ([cabling.md](cabling.md))
   and close them.
   Anchor onto the tray: 2 × M3×8 into its inserts; plug the lead into the
   node's DATA header (J7, on its right edge).
3. **Row power (VRACK)**: JST PH jumper (24 AWG leads, red housing into J1, rung first:
   [cabling.md](cabling.md#row-power)) to the neighbouring node, through the windows in
   both tray walls and the shared ladder; along the tray's front, tied to the
   two anchors at its front right (a cable tie through each one's tunnel),
   clear of the chain foot's reach ([cabling.md](cabling.md)); the row feed
   goes into the row's first bay.
4. **Drawer**: the detent is printed (a tab in the tray's left ledge, a notch
   under the drawer): nothing to fit.  With `drawer.detent: magnet` instead,
   magnets first, one under the drawer and one in the tray's left ledge: stack
   the pair, mark both outer faces, glue each magnet marked face down into its
   pocket with a drop of CA, and let it set before the drawer goes in.  The rear bay takes either DATA board, components up, its USB-C
   edge against the port wall (each receptacle behind a U), PT 2.3×8 from
   above: the DATA port board on its two Ø5 bosses, its USB-C behind the
   fourth U (the rightmost), or a DATA ×4 on its three Ø6 bosses.  The DATA
   lead comes up through the cable window at the rear right: beside a
   DATA ×4's right edge into its PH, or along the rear wall into the DATA
   port board's PH from the rear.  The standing DATA ×4 v2 goes in its
   printed `x4_cradle` instead: cradle onto the same three bosses
   (3 × PT 2.3×8), the lead up the window and into the board's rear PH, then
   the board slid down into the cradle's slots, receptacles towards the wall,
   until both latches click.  To take it out, unplug the lead from its PH
   first (the plug stands above the drawer's 16 mm rear wall; left plugged,
   the lead needs ≈ 75 mm of slack), then press both latches back and lift
   the board.  To convert a bay, swap the board; the drawer stays.  Slide the drawer
   in from the front onto the tray's ledges (its rear flange under the guide
   lips), engage the foot in the rear groove and lock it with the M2.5 from
   inside the rear bay (PT 2.3×8); then the stop screw (PT 2.3×8) through the left guide lip.
5. **Plate + board + short cable**; the bay's printed label (or 12 mm tape) in
   the front recess.

A **sled or fixed bay** (`mount: sled` / `fixed`) skips steps 2 and 4: no chain,
anchor (nor its two inserts), foot or magnets.  The DATA board goes into the
`drawer_block` as into a drawer's rear bay; the DATA lead (the same 50 cm PH 8)
runs from J7 back along the plenum and up through the block's window into its
PH, its slack coiled in the plenum.  Slide the
block in onto the ledges to the rear (its flanges under the guide lips) and lock
it: 2 × PT 2.3×8 down through the guide lips and its flanges into the ledges,
at the holes level with them.  Then the `drawer_sled`, and the stop screw; for a
fixed bay, 2 × PT 2.3×8 more through the lips into the sled's flanges.

To take a tray out: pull the drawer out, press both latch arms inwards, slide
the tray forwards.

## 5. Power

The power box ([mechanical.md](mechanical.md#power-box)):

1. Heat-set the 4 inserts in the hub standoffs, from above (the box is open: the iron reaches
   each standoff, 13.6 mm down, ≥ 4.7 mm from the walls).
2. Lower the hub straight in, its USB-C PD input towards the rear wall, and screw the 4 M3×12
   male-female hex spacers through its holes into the inserts (by hand or with pliers: the row
   connector next to the front-left hole leaves no room for a 5.5 mm socket).
3. Lid on: its rim inside the walls, 4 × M3×8 into the spacers.
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
its posts and the board).  Pod under the ceiling, 2 × M3×8 on a diagonal into the camera
inserts (the tray above, or the cap plate), the bay's drawer pulled out (a
closed drawer and its DUT cable leave no room for the hand).  Then the XH →
Dupont cable onto J2 by name and into the Mega's side (only now: the XH plug
sits right under the front-left screw), and push the Mega's case up into the
sleeve until the lips click, lens down, the XH and its plug up through the
open side.  The lead
([cabling.md](cabling.md)) into the bay's own node (J6), back through the
plenum and the tray's rear slot, straight up behind the tray, forwards under
the ceiling (a cable tie every ~5 cm) and into the board's J1, only once the
pod is screwed: its plug covers the rear-left screw.

## 7. Bring-up

Per node: SERVICE on → laptop on the PC port → flash → SERVICE off.  Then
`usbip list -r bay-<id>.local`.  See [firmware.md](firmware.md).  With a
camera: focus its lens on the plate from the bay page's live view, then
lock the nut ([firmware/README.md › Camera](../firmware/README.md#camera)).

**First boards: measure** (from the PCBA review, [pcba-review.md](pcba-review.md)):
- JLC's placement preview, before paying: the side LEDs and U1 (CH224A) on the hub, SW3's pegs in
  their holes on the node (drills shown).
- Hub, on two or three PD chargers (a 140 W EPR one, a 100 W, a 65 W): it negotiates at plug-in with
  the hub's 150 µF on VBUS (C8 left off if one refuses); the CH224A's VHV pin (rated 32 V) at plug-in,
  through the 9 V → 28 V step and when a loaded row is cut (stay at 20 V if it passes 31 V); the AP2112K's temperature through a long Wi-Fi transfer in the closed box; the In2
  VRACK band's temperature at the full 5 A (a thermal camera on the board's bottom); a row shorted
  at the end of its lead: OUT not below −0.3 V (D4x), the other rows unaffected.
- Node: F1's margin in a warm rack, camera and light on; the +3V3 load step (the AMS1117 on
  ceramics only); the I²C rise time with a DATA ×4 on the lead (under 300 ns at 400 kHz).
