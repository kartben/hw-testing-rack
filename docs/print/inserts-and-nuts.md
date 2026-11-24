# Fit the inserts and nuts

Some printed parts take M3 heat-set inserts, and the ladders take M3 square nuts. Fit them while each part
lies loose on the bench, before you assemble anything onto it.

## Heat-set inserts

Press them in with a soldering iron and a tip for heat-set inserts
([Tools and bench equipment](../plan/shopping-list.md#tools-and-bench-equipment)). Each hole is Ø4.0 mm
and at least 5.7 mm deep, for an M3 insert 5.7 mm long. If an insert splits its boss, check the hole
compensation in [Slicer settings](printer-and-settings.md#slicer-settings).

| Part | Where | Inserts |
|---|---|---|
| `tray` | the bay node's four standoffs, from above | 4 |
| `tray` of a bay on a drag chain | the chain anchor's two bosses, from above | 2 |
| `tray` with a bay under it, and `cap_plate` | the camera square, in the ceiling of the bay below. Fit them from below | 4 |
| `drawer`, or `drawer_block` in a bay without a chain | the three bosses in the rear bay, for the DATA board's cradle | 3 |
| `power_box_base` | the hub's four standoffs, from above | 4 |

Every bay's ceiling takes the four camera inserts, so you can add a camera to any bay later. On a cap plate,
the camera square is four of the bosses in its grid. Lay the plate with its bosses up and its front edge
towards you. The four bosses are where the two right-hand columns of the grid meet its two front rows. That
is the same place as the camera square under a tray.

In the power box, fit the inserts with the box open and the iron straight down. The top of each standoff is
13.6 mm below the top of the walls, and at least 4.7 mm from the nearest wall.

M2.5 and M2 inserts are only for a board's own plate (`plate: boards`,
[Add a board to the library](../use/add-a-board.md)).

## Square nuts in the ladders

Every base ladder and row ladder has four pockets by its rear edge, open on one face. Push an M3 square nut
(DIN 562, 5.5 × 5.5 × 1.8 mm) into each pocket from its open face, past the small rib inside. The rib holds
the nut while the ladder stands. The M3 × 8 screws of the braces go into these nuts. The cap strips take
none.

The pockets sit behind the trays, so you can also fit each nut later, when you screw on its brace
([Build the first bay](../build/first-bay.md)).

## Bosses that stay empty

You cannot take an insert out again. Leave these bosses empty:

- The bosses of the floor plate. Two of them take the wood screws into the bench, and an insert would stop
  the screw ([Screw the rack to the bench](../build/screw-the-rack-to-the-bench.md)). The sockets of the
  power box drop over others.
- The bosses of the cap plate, except the four of the camera square.
- The camera square under a tray of row A: no camera hangs below it.
- The chain anchor's two bosses, in the tray of a bay without a drag chain.

## How many for your rack

For the 4 × 3 example rack:

```{bom-table}
:category: Fasteners
:match: heat-set insert|square nut
:columns: item, qty
```

One bay in its frame takes 17 inserts and 16 square nuts. For any other size, count:

- 13 inserts for each bay on a drag chain, 11 for each bay without one, and 4 for the power box.
- Four square nuts for each ladder under the cap strips. A rack of *c* columns and *r* rows has
  (*c* + 1) × (*r* + 1) of them.
