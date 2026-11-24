# Take a bay apart

To swap a DATA board or to reach a bay node, take the bay out of the rack. Its {term}`tray` slides out of the
frame with the node, the drag chain, the drawer and the DATA board on it. You take the rest apart at the bench.
Switch off the row first.

## What you can plug in while the rack is on

:::{warning}
On a running rack, three mistakes can break PCBs or bring a row down:

- Plugging or unplugging the DATA lead under power. It can destroy the node's I²C pins, its INA226 or the DATA
  board's USB hub.
- Plugging a node into a live row. The row's voltage drops, the neighbours' DATA boards drop out, and a node
  alone on the row may restart.
- Plugging an AUX lead into ROW OUT (J2). AUX (J5) is the same 6-pin socket, 22 mm away on the same edge.
  Pin 6 of ROW OUT carries the row's 20 V into your board. The other way round, a row cable in AUX
  trips the row's eFuse.
:::

Only two cables are made to go in and out of a running bay:

- a board's USB cable, in its port on the DATA board ([Put a board in a bay](mount-a-board.md));
- a laptop's cable, in the PC port at the front of the bay, under the drawer
  ([Front port and classic mode](front-port.md)).

To switch a whole row off, use the rack's page ([The rack's page](rack-page.md)) or:

```console
$ python tools/bayctl.py row B off
```

To switch off only the DATA lead and the bay's boards, run `bay power off` in the node's shell. Or, with the
admin key, on a bay that nobody has reserved:

```console
$ python tools/bayctl.py hub node B3 power-off
```

`bay power on`, or `bayctl hub node B3 power-on`, switches the lead back on. If the DATA board stops
answering, the node switches the lead off by itself and keeps it off.

## Take a tray out

1. Switch the row off.
2. Pull the drawer out to its stop. It stays on its tray, wired through the drag chain.
3. Unplug the cables that cross the tray's walls:
   - the {term}`jumper` or the {term}`feed` in the node's ROW IN (J1, left edge);
   - the jumper from this node's ROW OUT, in the right neighbour's ROW IN (pull that drawer out too);
   - the camera lead at J6 (CAM), an AUX lead at J5, and a laptop at the PC port.
4. Press both latch arms inwards, one on each wall of the tray, and slide the tray forwards out of the ladders.

```{figure} ../img/viewer/b3-drawer-out.jpg
:alt: Bay B3 of the 3D model with its drawer pulled out to its stop, the DATA ×4 standing at the back, the neighbours' drawers partly out

The 3D model: the drawer of bay B3 pulled out to its stop. The drawer rides on its tray, and the tray stays in
the grooves of the ladders.
```

The DATA lead stays plugged in J7 and in the drag chain. While the tray is out, the bays after it in the row
have no power and no rack bus, because each node passes both on to the next.

## Take the DATA board out

Take the tray out first. These are the steps of
[Fit out a tray](../build/fit-out-a-tray.md#the-drawers-front-then-the-data-board), backwards.

1. Unplug the boards' USB cables from the DATA board. On a DATA ×4, pull the jumper wires off its headers. If
   the drawer has a cover over the DATA board, lift it off by its sides.
2. Take the strip off the cradle's comb: five PT 2.3 × 8 screws, with a screwdriver whose shaft is 60 mm or
   longer.
3. Unplug the DATA lead from the board's rear socket.
4. Press both latch fingers of the cradle back, and lift the board out.

## Swap a DATA ×6 for a DATA ×4

Both boards fit the same drawer, cradle, strip and lead. Take one out and fit the other as on
[Fit out a tray](../build/fit-out-a-tray.md#the-drawers-front-then-the-data-board). After the swap:

- The node detects the new board. The bay's page shows its badge.
- The four ports of a DATA ×4 stand in slots 2 to 5 of the six. So the cables move, and the boards change
  names ([Bays, ports and addresses](names.md)).
- The board targets stay with the port numbers: check every port on the bay's page ([Board targets](board-targets.md)).
- A DATA ×4 uses some of the bay's power itself ([Power budget and queued ports](power-budget.md)).
- Change the bay in `config/rack.yaml`, so that the 3D model and the bill of materials follow
  ([rack.yaml](../reference/rack-yaml.md)).

## Take a node off its tray

You need this only to reach the node's UART pads. You can flash a node that runs with the bay closed
([Recover a node or the hub](recover.md)).

With the tray out and its drawer pulled out, unplug the DATA lead from J7, on the node's right edge. Take out the
four M3 × 8 screws. The two on the left are under the left guide: reach each through the hole above it, with
the screw on a magnetic bit. Lift the node off.

## Put it back

Work in the reverse order, with the row off. Slide the tray in until both latches click. Then plug:

- the jumper or the feed into ROW IN;
- the jumper from ROW OUT into the right neighbour's ROW IN, red housing at IN;
- the camera lead into J6, not J7.

Switch the row on. The bay takes its name from its place in the rack, so there is nothing to set on the node.
If the bay does not come back on the rack's page, see
[A bay is missing or does not answer](troubleshooting.md#a-bay-is-missing-or-does-not-answer).
