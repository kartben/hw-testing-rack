# Assembly

Order of work for the default build: 12 bays, 4 columns × 3 rows.  Quantities:
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
tray's node standoffs and 2 in its chain anchor, 4 under the ceiling of each
camera bay (the tray above, or the cap plate).

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
2. **Drag chain**: cut ≈ 160 mm (21 links of the common 7×7 R18); fixed end
   to the `chain_anchor` (2 × M3×6 into the tray), moving end to the
   `chain_foot`.  Lay the drawer extension cable in the chain (links snap
   open), plug its male end into the node's DUT port.
3. **24 V**: JST PH jumper to the neighbouring node, through the windows in
   both tray walls and the shared ladder; the row feed goes into the row's
   first bay.
4. **Drawer**: magnet underneath; screw the panel-mount female into the DATA
   port position **farther from the board's debug USB** (left or right; the
   viewer's bay panel says which: *DATA socket*), M3 ears; slide the drawer
   in from the front onto the tray's ledges (its rear flange under the guide
   lips), engage the foot in the rear groove and lock it with the M2.5 from
   inside the rear bay; then the M2.5×8 stop screw through the left guide lip.
5. **Plate + board + short cable**, printed `bay_label` (or 12 mm tape) in the
   front recess.

To take a tray out: pull the drawer out, press both latch arms inwards, slide
the tray forwards.

## 5. Power

The power box ([mechanical.md](mechanical.md#power-box)):

1. Heat-set the inserts: 4 in the hub standoffs and 4 in the wall bosses for the lid.
2. Cut the brick's DC cord to ≈ 25 cm and crimp a JST VHR-2 (SVH-21T-P1.1,
   18–22 AWG), observing the polarity on the brick's label.
3. Brick into its cradle, cradle into the bay, C14 into the rear window.  Hub on
   its standoffs (4 × M3×6), DC cord through the cable-tie loop into the hub's
   VH input.
4. Foam pad on the brick, lid on (4 × M3×8).
5. Lift the box over the floor plate's front lip under A1 and let its sockets
   drop over the bosses.
6. C13 cord out of the back, through the base brace.

Before the rows are plugged in, check 24 V at every hub output and that every
ON LED lights.  Then plug the row feeds through the left base ladder's window,
run them up the left side and into each row's first node.

## 6. Cameras (optional)

Mount under the ceiling (4 × M3 into the tray above, or the cap plate),
cradle on the M3×30 pivot, XIAO in the cradle, PH lead to the node above (or
the bay's own node for the top row).

## 7. Bring-up

Per node: SERVICE on → laptop on the PC port → flash → SERVICE off.  Then
`usbip list -r bay-<id>.local`.  See [firmware.md](firmware.md).
