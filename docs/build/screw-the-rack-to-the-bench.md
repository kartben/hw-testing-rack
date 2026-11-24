# Screw the rack to the bench

A rack that stands loose tips forwards: a pull of 8 to 13 N at a top drawer's front is enough, and unplugging a
USB-C cable takes 8 to 20 N.  Screw the four floor plates to the bench, two wood screws each.  Choose the
rack's place before the first ladder goes up.

:::{status} designed
A calculation of 2026-10-25 on the 3D model, for racks of two and of four rows of 165 mm
([Can the rack tip over?](../stability.md)).  The default rack, three rows of 165, 165 and 120 mm, was not
computed, and no rack has been built to try any of it.  [What exists today](../plan/status.md#status-stability).
:::

## Why it tips

The rack stands on the base ladders' bottom edges and on the floor plates, 201 mm from front to back, its
centre of gravity 91 mm behind the front edge.  The front of an open top drawer is 145 mm ahead of that edge.

| | 2 rows | 4 rows |
|---|---|---|
| Mass, with today's boards in the drawers | 3.7 kg | 6.6 kg |
| A pull at a top drawer's front tips it forwards at | 8 to 13 N | 8 to 11 N |
| A push down on the front of an open top drawer tips it at | 16 to 24 N | 35 to 45 N |
| A push at the top tips it backwards at | 13 to 24 N | 11 to 19 N |
| Sideways, at the top | 38 N | 33 N |

The ranges run from all drawers closed to all four top drawers open, and from today's boards to 160 g of
boards in every drawer, the most the study loaded; a slot-bin drawer of row C holds six boards.  Printed mass
is counted at 55 % of solid PETG; at 80 % every force rises by about 35 % and the verdict stands.  The push on
an open drawer is the likely accident: leaning on it, or pushing a plug into a board that lies on it.

```{figure} ../img/viewer/rack-side-drawers-out.jpg
:alt: The default rack seen from its right side, every drawer pulled out ahead of the base
:width: 55%

The 3D model of the default rack from its right side, every drawer pulled out: the open drawers hang ahead of
the base's front edge, the edge it tips over.  This three-row rack is not one of the two cases computed.
```

## Eight screws through the floor plates

Eight wood screws 3.5 × 16, pan head, each on an M4 washer: one at the front and one at the rear of each
floor plate.  About €1.  They are not in the bill of materials
([Shopping list and tools](../plan/shopping-list.md)).

The bosses stand on the plate's 30 mm grid, four across and six deep.  The front screw goes in the front
row, third boss from the left; under A1 it lands 3.5 mm to the right of the power box.  The rear screw goes in
the rear row, second boss from the left.

Each boss has a Ø4 hole through it, so the screw's head bears on the boss.  The floor plates' runners sit in
the base ladders' grooves: held down, the plates hold the whole rack.  Use bosses that have no insert:
[an insert stops the screw](index.md#insert).

Screwed down, a four-row rack holds 120 N at its top and a two-row one 245 N, counting 100 N a screw, a
conservative pull-out from particle board.  The target was 40 N, twice a 20 N pull.  On exact solids the
screws clear the plates and the power box.

Each column's two screws go in once its base brace is on and before row A's tray: step 4 of
[The frame and the first bay](first-bay.md), then step 2 of each further column
([Add a bay, then a row](add-a-bay.md)).  With row A's tray in place, 78 mm remain above the front screws
and 133 mm above the rear ones: room for a stubby screwdriver only.

## If you cannot drill the bench

* An MDF board under the rack, 18 mm thick, 670 mm wide and at least 500 mm deep, the floor plates screwed to
  it the same way.  At 500 mm it holds 63 N with two rows and 41 N with four; at 600 mm, 86 and 54 N.  At
  400 mm a four-row rack holds 29 N, under the target.
* Two furniture anti-tip straps from the rear posts of the top ladders to the wall, when there is a wall
  behind the rack.

Three other ideas do not hold.  Printed outrigger feet would have to reach 266 to 311 mm ahead of the rack.
Ballast in the base cells would take 9.7 kg for two rows and 20.3 kg for four.  Two racks joined side by side hold 15 to 16 N: the force at
one bay stays what it was.

A step that is wrong: [report it](../reference/known-limitations.md#report-a-finding).
