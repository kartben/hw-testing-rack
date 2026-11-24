# Fit the inserts and the square nuts

The default rack takes 158 M3 heat-set inserts, in the trays, the drawers, the cap plates and the power
box, and 80 M3 square nuts, four in the rear edge of every base and row ladder. No insert goes into a
ladder.

:::{status} designed
Where each insert and nut goes is read from the models and from `tools/bom.py`, which counts them. No
insert has been pressed into a printed part, and no nut into a printed ladder.
[What exists today](../plan/status.md#status-frame).
:::

```{bom-table}
:category: Fasteners
:match: heat-set insert|square nut
:columns: item, qty, notes
```

The inserts go in with an iron and a tip for heat-set inserts ([Shopping list and tools](../plan/shopping-list.md));
no source gives a tip, a temperature or a technique for pressing them into PETG. The holes are Ø4.0 mm and
at least 5.7 mm deep, the insert's nominal size (`INSERT_M3` in
[mechanical/lib/common.scad](../../mechanical/lib/common.scad)). They come out true with the slicer's hole
compensation of 0.1 mm, and 0.1 to 0.2 mm tight without it, which is when PETG splits round an insert
([Slicer settings](printer-and-settings.md#slicer-settings)). Fit each insert while its part lies loose on
the bench, before anything is assembled onto it.

## Where the inserts go

| Part | Where | Each | Default rack |
|---|---|---|---|
| `tray` | the bay node's four standoffs, from above | 4 | 48 |
| `tray` of a drawer bay | the chain anchor's two bosses, from above | 2 | 22 |
| `tray` of rows B and C, `cap_plate` | the camera pod's square underneath, from below: the ceiling of the bay under it | 4 | 48 |
| `drawer`, or a sled bay's `drawer_block` | the three Ø8 floor bosses of the rear bay, for the DATA board's cradle | 3 | 36 |
| `power_box_base` | the hub's four standoffs, from above | 4 | 4 |

Read from `hardware()` in [tools/bom.py](../../tools/bom.py) and from the parts' sources. The pod's square
takes four inserts so that a pod can go into any bay later; a pod holds on two of them, on a diagonal. On a
cap plate the square is the one at x 94 and 124, y 30 and 60 of its 30 mm grid, under the same place as on
a tray.

In the power box the iron goes in from above, the box open: each standoff is 13.6 mm down and at least
4.7 mm from the walls. The box's step at the bench is on [Power box and charger](../build/power-box.md).

```{figure} ../img/notice/c0.svg
:class: bb-lineart
:alt: The power box base, empty, an insert above each of the hub's four standoffs

The power box base before the hub goes in: one insert into each standoff.
```

## Square nuts in the ladders

Every `ladder_base`, `ladder_a`, `ladder_b` and `ladder_c` has four pockets by its rear edge, open to one
face, with 2.2 mm of wall between nut and edge. Push an M3 square nut (DIN 562, 5.5 × 5.5 × 1.8 mm) into
each from the face it opens to, past the 0.4 × 0.4 mm rib inside: the rib holds it while the ladder
stands. The braces' M3 × 8 screw into these nuts. The cap strips take none.

The pockets sit behind the trays, so a nut can also go in at the step that screws on its brace
([The frame and the first bay](../build/first-bay.md)). Four nuts a ladder, one ladder per column boundary
and level: 4 × 5 × 4 = 80 in the default rack.

The assembly drawings of 2026-10-20 still show inserts in the ladders. These nuts replaced them on
2026-10-21: an insert along the 7.4 mm edge would leave 1.7 mm of wall on faces that keep 0.2 mm to the
trays, and its hole, lying in the layer plane, prints oval.

## Bosses that stay empty

A heat-set insert cannot come out again: [the table of steps that cannot be undone](../build/index.md#insert).
These take none in the default rack:

- The floor plate's bosses. Two of each plate take the wood screws into the bench, whose heads bear on the
  boss: an insert would stop the screw ([Screw the rack to the bench](../build/screw-the-rack-to-the-bench.md)).
  The power box's sockets drop over others without screws.
- The cap plate's bosses, but the four of the camera square.
- The camera square under a tray of row A: the bill counts no insert there, as no bay hangs a pod from it.
- The chain anchor's two bosses in the tray of a sled bay: it has no chain.

[The mechanical design document](../mechanical.md#printing) also lists M2.5 and M2 inserts. They are for
the former per-board plates (`plate: boards`); the default rack buys none.

## One bay, and a plain 2 × 2 rack

A drawer bay on its own, a rack of one column and one row, takes 13 inserts (4 for the node, 2 for the chain
anchor, 4 under the cap plate, 3 in the drawer), 4 more in the power box, and 16 square nuts (two base
ladders and two row ladders). A plain 2 × 2 rack:

```{bom-table}
:category: Fasteners
:match: heat-set insert|square nut
:columns: item, qty
:size: 2x2
:plain:
```
