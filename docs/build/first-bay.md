# The frame and the first bay

The frame goes up around a fitted tray: two base ladders and a floor plate, a brace behind them, two row
ladders, the tray, a second brace, then the cap strips and the cap plate.  Besides the two bench screws, the
frame's only screws are the braces': eight M3 × 8 for one bay.  Everything else slides into a groove or clicks.

:::{status} designed
The frame's parts were checked for clashes on exact solids, and the forces of their hooks and latches are
calculated.  No ladder, tray or brace has been printed and put together.
[What exists today](../plan/status.md#status-frame).
:::

Steps 1 to 5 need no tray: the base, the bench screws and the row ladders can go up while the PCBs are on
their way, and the fitted tray slides in from the front at step 6.  A single bay in the frame is a rack of
one: it still takes the power hub in [its box](power-box.md), under this bay, and row A's feed.

You need a tray from [Fit out a tray](fit-out-a-tray.md), and for one bay:

* printed, with the four square nuts of each base and row ladder in their pockets and the four inserts under
  the cap plate ([Inserts and square nuts](../print/inserts-and-nuts.md)): two base ladders (`ladder_base`),
  two row ladders (`ladder_a`), two cap strips (`ladder_cap`), a floor plate (`floor_plate`), a cap plate
  (`cap_plate`), a base brace (`brace_base`) and a row brace (`brace_a`).  The cap strip has the same shape on
  every row ([mechanical/parts/ladder.scad](../../mechanical/parts/ladder.scad) only moves it up), so the
  committed `ladder_cap` fits a frame of one row;
* 8 M3 × 8;
* two wood screws for the bench, and a place for the rack: read
  [Screw the rack to the bench](screw-the-rack-to-the-bench.md) before step 1.

## The base ladders, the floor plate and their brace

:::{build-step} 1
:drawing: a1
:alt: Two base ladders standing upright, side by side
:parts: lb=2

Two **base ladders** (`ladder_base`) on their long straight edge, the low end at the front, the nut pockets
along the tall rear edge.  Hold them, or lean them on a box, until the floor plate is in.
:::

:::{build-step} 2
:drawing: a2
:alt: The floor plate sliding between the two base ladders from the front
:parts: fp=1
:click:

The **floor plate** slides in from the front, into their bottom grooves, until the barb of each of its latch
arms clicks into the groove's window, as a tray's does.
:::

:::{build-step} 3
:drawing: a3
:alt: Rear view: the X-shaped brace and its four screws going into the rear edges of the two ladders
:parts: bb=1
:hardware: m3x8=4

**Base brace** (`brace_base`) at the back: four M3 × 8 through the brace into the square nuts in the ladders'
rear edges.  Count the nuts from the bottom: the 1st and 3rd on the left ladder, the 2nd and 4th on the right
one, left and right as the rack is seen from the front.  Each diagonal is 0.25 mm short: the X is taut once
the fourth screw is in.
:::

A nut that fell out goes back from the face its pocket opens to; a small rib holds it while the ladder stands.
The pockets are behind the trays, so they stay in reach from the back at every level.

:::{build-step} 4
:hardware: Wood screw 3.5 × 16 pan head=2, M4 washer=2

**Bench screws**, now: one through the floor plate's front boss and one through its rear boss, into the
bench.  Which bosses, and what to do when the bench cannot be drilled:
[Screw the rack to the bench](screw-the-rack-to-the-bench.md).  Once row A's tray is in, only a stubby
screwdriver reaches them.
:::

## The row ladders

:::{build-step} 5
:drawing: a4
:detail: hook
:alt: Two row ladders coming down onto the base ladders
:parts: la=2
:click:

**Row ladders** (`ladder_a`) onto the base ladders: ridge into notch, then push down with the palm until both
snap hooks of each ladder click (about 40 N for the two, by calculation).  A row ladder carries its row's
letter on its front post and the word FRONT, with an arrow, on its top band.  To release a hook, push its barb
through the window.
:::

## The tray goes in

:::{build-step} 6
:drawing: t4
:alt: The fitted tray, its drawer in it, sliding into the grooves of the row ladders from the front
:parts: tr=1
:click:

The fitted **tray** from the front: its runners slide into the row ladders' grooves until the barb of each
latch arm clicks into the groove's window (about 14 N a side, a thumb's push, by calculation).

The drawing shows the drawer of 2026-10-20 and a board on its plate.  Your boards stay on the shelf until the rack answers:
[A first session with a bay](../use/first-session.md) starts with them.
:::

:::{build-step} 7
:drawing: a6
:alt: Rear view: the row's brace and its four screws, above the base brace
:parts: bb=1
:hardware: m3x8=4

**Row brace** (`brace_a`): four M3 × 8 into the row ladders' nuts, as in step 3.
:::

The tray takes no cable yet.  A row's first bay gets the row's feed from the power box
([Power box and charger](power-box.md)); a jumper comes with the bay beside it
([Add a bay, then a row](add-a-bay.md)).

## The caps, on the top row only

Stop here if another row follows, and leave this bay open: the next row's ladders snap onto these as in
step 5, then its tray and its brace as in steps 6 and 7, from the row's own files.  The order for a whole rack
is on [Add a bay, then a row](add-a-bay.md#the-order-for-twelve-bays).

:::{build-step} 8
:drawing: a7
:alt: Two cap strips coming down onto the top ladders, the cap plate sliding into them from the front
:parts: lc=2, cp=1
:click:

**Cap strips** (`ladder_cap`) on the top ladders, their hooks clicking as a row ladder's do, then the **cap
plate** slides into their grooves from the front.  Its four inserts are the mount of a camera for the top row
([Add a camera](camera.md)).
:::

## A rear cover and detent magnets, both optional

Once the bay works, a printed box (`cover_box4`) closes the drawer's rear bay from above, over either DATA
board.  Press it on: its lips over the port wall's front face first, then the rear edge down until both tabs
click.  Lift it by its sides.  It has a notch over each slot of the port wall and along a DATA ×4's headers, so
it comes off with the boards' cables and wires plugged.  The bill counts one per bay as an option, outside its
filament line: 51 g each in the slicer
([Printer, filament, settings](../print/printer-and-settings.md#filament)).

The printed tab in the tray's left ledge holds a closed drawer against the slope with about 3 N.  If it does
not suit after a test print, `drawer.detent: magnet` in [config/rack.yaml](../../config/rack.yaml) replaces it
with two magnets of 6 × 3 mm, one under the drawer and one in the ledge, about 10 N.  The key changes the tray
and the drawer: regenerate their STL files ([Get the STL files](../print/stl-files.md)) and print both again.
The pockets are a slip fit, so the magnets are glued, and [glue cannot be undone](index.md#magnets).  Stack
the pair, mark both outer faces, then glue each magnet marked face down into its pocket with a drop of CA gel,
so that the two bare faces attract.  Let it set before the drawer goes onto its tray
([step 9 of Fit out a tray](fit-out-a-tray.md#the-drawer-onto-the-tray)).

## Check before you go on

- [ ] Each brace is taut on its four screws.
- [ ] Both hooks of each row ladder, and of each cap strip, are in their windows.
- [ ] Both barbs of the tray, and of the floor plate, are in the grooves' windows.
- [ ] The drawer runs its 140 mm in the frame as it did on the bench, and its detent holds it closed.
- [ ] The floor plate's two bench screws are in.

## If the drawer sticks

*Worked out from the clearances of the 3D model and from the
[slicer review of 2026-10-21](../printed-parts-fdm-review.md).  No drawer has run in a tray, so none of this
is a fault somebody met.*

| What you see | What the design says to look at |
|---|---|
| The tray does not enter the ladders' grooves | The runners fit their grooves with 0.15 mm a side.  An elephant's foot on a first layer takes that away: the profile compensates 0.15 mm ([Printer, filament, settings](../print/printer-and-settings.md)).  Try one tray in one ladder before printing twelve ([Measure before you print](../print/index.md)). |
| The drawer drags along its whole stroke | It has 0.5 mm a side between the guides (`drawer.clearance`) and rides on the two ledges, PETG on PETG: look at the ledges and under the guide lips.  For a smoother run the design names trays printed in a POM-like "igus" filament. |
| It stops before 140 mm, or pulls on the lead | The chain.  Its end pieces cannot bend and must stay in a straight run over the whole stroke: the model assumes about 180 mm of chain, the moving end's mouth 26 mm in front of the bend, and the U-bend 1.9 mm clear of the tray's rear wall.  A chain cut to another length, one whose measurements are not those of `config/rack.yaml` › `chain`, or the lead's spare left in front of the moving end, is in the way. |
| It moves, the chain does not | The chain foot is not locked in the drawer's groove: the PT 2.3 × 8 of [step 9 of Fit out a tray](fit-out-a-tray.md#the-drawer-onto-the-tray). |
| It comes right out | The stop screw through the left guide lip is missing.  The tray comes out again to fit it ([Take out a tray, a node or a DATA board](../use/service-a-bay.md)). |
| It does not stay closed on the slope | The detent's tab carries a bump of 0.6 mm that drops into a notch under the drawer's left wall.  If the tab does not hold, the magnets above are the way out. |
| With a neighbour's jumper in, it stops near the end of its stroke | The jumper is not tied to the two anchors at the tray's front right: pulled out, the drawer brings its chain foot to 12 mm from the front ([the jumper's route](add-a-bay.md#the-jumper-between-two-nodes)). |

A step that is wrong: [report it](../reference/known-limitations.md#report-a-finding).
