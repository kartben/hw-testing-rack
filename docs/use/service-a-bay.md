# Take out a tray, a node or a DATA board

A bay comes apart in the order it went together: its tray slides out of the frame with the node, the drag
chain, the drawer and the DATA board on it, and the rest is done at the bench. Before any of it, the lead or
the row you unplug must be off.

:::{status} designed
The frame, the tray and the drawer were checked for clashes on exact solids, and the rules for a powered rack
below are calculations of the design review of 2026-11-09, not measurements. No tray has been printed, and no
cable has been plugged into a powered node. [What exists today](../plan/status.md#status-bay).
:::

## What you may plug with the rack powered

:::{warning}
Three things break PCBs, or drop a row, on a running rack:

- The DATA lead under power. Its connector has no early ground pin: plugged or unplugged live, the DATA
  board's input capacitors can charge through the signal lines and destroy the node's I²C pins, its INA226 or
  the DATA board's USB hub.
- A row cable on a live row. A node plugged into a powered row shares its neighbours' charge: a 20 V row
  falls to about 10 V with one node already on it, 13.3 V with two, 15 V with three, and the neighbours' DATA
  boards drop out; a node that was alone on the row probably restarts.
- Anything but a row cable in ROW OUT (J2). AUX (J5) is the same 6-pin socket on the same edge of the
  node, 22 mm away, and pin 6 of ROW OUT carries the row's VRACK, 20 or 28 V, on the last node of a row as well. An AUX lead
  pushed into ROW OUT puts that voltage on its BOOT wire and into the board at its end; a row cable pushed into
  AUX trips the row's eFuse.
:::

Switch the DATA lead off before you touch it, in the node's shell or through the hub:

```console
uart:~$ bay power off
$ python tools/bayctl.py hub node B3 power-off
```

Both cut the lead and every board of the bay with it; the second needs the admin key, and a reserved bay
refuses it. `bay power on`, or `bayctl hub node B3 power-on`, brings the lead back through its checks. A DATA board
that stops answering also makes the node switch the lead off at once, until the next power-on: a lead pulled
by mistake does not come back live by itself.

Switch the row off before a feed or a jumper is plugged or unplugged, from the rack's page
([Rows and the rack's page](rack-page.md)) or the hub's console (`hub row B off`, later `hub row B on`), or with
`python tools/bayctl.py row B off`. A row off takes every bay of the row with it, and with the node off
nothing on it is powered: the camera lead and the AUX lead, for which no source gives a rule, are then safe
too.

Two cables are made to go in and out of a running bay: a board's USB cable into its port of the DATA board
([Put a board in a bay](mount-a-board.md)) and a laptop's into the PC port of the fascia
([A laptop on the front port](front-port.md)).

## Take a tray out

*The order of the unplugging is worked out from [Fit out a tray](../build/fit-out-a-tray.md) and
[Add a bay, then a row](../build/add-a-bay.md); nobody has done it yet.*

1. Switch the row off at the hub.
2. Pull the drawer out to its stop. It stays on its tray, wired through the drag chain.
3. Unplug what crosses the tray's walls. At the node's ROW IN (J1, left edge): the jumper from the left
   neighbour, or the row's feed in a row's first bay. At the right neighbour's ROW IN, with its drawer out too:
   the jumper from this node's ROW OUT, which is tied to this tray and comes back through the windows with it.
   The camera lead at J6 (CAM), and out of the tray's rear slot; an AUX lead at J5; a laptop at the PC port.
4. Press both latch arms inwards, one on each wall of the tray, so that their barbs leave the grooves'
   windows, and slide the tray forwards out of the ladders.

```{figure} ../img/viewer/b3-drawer-out.jpg
:alt: Bay B3 of the 3D model with its drawer pulled out to its stop, the DATA ×4 standing at the back, the neighbours' drawers partly out

The 3D model, bay B3 pulled out to its stop: the drawer rides on its tray, the DATA ×4 stands at the back of
its rear bay, and the tray's runners stay in the ladders' grooves.
```

The DATA lead stays in J7 and in the chain: it leaves the tray only with the node or the DATA board. While the
tray is out, the bays after it in its row have neither power nor rack bus once the row is back on: the row's
power and its bus reach each node through the one before it
([Cables and pinouts](../reference/cables.md#row-cable-jumpers-and-feeds)).

The ladders stay where they are. Each row ladder sits on the ladder below it, ridge into notch, and holds by
two snap hooks; the cap strips on the top ladders hold the same way, with the cap plate slid into their
grooves. To release a hook, push its barb through its window. The caps come off before a new row goes on:
[Add a bay, then a row](../build/add-a-bay.md).

## Take the DATA board out

Take the tray out first and work at the bench: these are the steps of
[Fit out a tray](../build/fit-out-a-tray.md#the-drawers-front-then-the-data-board), backwards.

1. Unplug the boards' USB cables from the DATA board's ports; on a DATA ×4, pull the jumper wires off its
   headers. Lift the rear bay's cover, if fitted, off by its sides.
2. Take the strip off the cradle's comb: its five PT 2.3 × 8, with a screwdriver of 60 mm shaft or more,
   between the port wall and the board.
3. Unplug the DATA lead from the board's rear socket before the board moves. Its plug stands above the
   drawer's 16 mm rear wall; left plugged, the lead would need about 75 mm of slack.
4. Press both latch fingers of the cradle back and lift the board out of its slots.

## Turn a DATA ×6 bay into a DATA ×4 bay

The drawer, the cradle, the strip and the DATA lead take either board, so a bay converts by swapping the
board alone: take the DATA ×6 out as above, and put the DATA ×4 in its place as
[Fit out a tray](../build/fit-out-a-tray.md#the-drawers-front-then-the-data-board) does. The way back is the
same. With the board, these change:

- The node finds out by itself. The same firmware drives both; at each power-on of the lead it reads
  which board answers. The header of the bay's page shows the new badge.
- The ports move. A DATA ×4's four ports stand in slots 2 to 5 of the port wall's six. On either board
  port 1 is the leftmost seen from the board's side, so the cables change slots and the boards change names:
  [Bays, ports and addresses](names.md).
- The board targets stay with the port numbers in the node's flash, each pinned to the device it was saved
  for: check every port on the page afterwards ([Board targets](board-targets.md)).
- A DATA ×4 takes power of its own out of the bay's share, for its hub and its logic:
  [Power budget and queued ports](power-budget.md).
- `config/rack.yaml` says which board a bay holds (`x4: v2` or `x4: base`, with the boards and their
  ports), so that the 3D model, the layout tool and the bill follow it: [rack.yaml](../reference/rack-yaml.md).

The DATA ×4 brings its pin headers, for wires between boards ([Wires between boards](wires.md)); its pinouts
are on [DATA ×4](../reference/pcbs/data-x4.md).

## Take a node off its tray

*Worked out from [Fit out a tray](../build/fit-out-a-tray.md) and from the tray's design; nobody has done it
yet.*

With the tray out and its drawer pulled out, unplug the DATA lead from the node's J7, on its right edge. The
node sits on four standoffs, four M3 × 8. Its two left screws are under the left guide: a hole through the
left ledge and lip, over each, lets the screwdriver and the screw through, on a magnetic bit. Then lift the
node off.

The node's UART test pads, TP1 to TP4, are on its underside: they need the node off its standoffs. A node
that still runs needs none of this to be flashed: SERVICE and the front port reach it with the bay closed
([Recover a node or a hub](recover.md)).

## Put it back

In the reverse order: the board into its cradle, the lead into its rear socket, the strip and its five
screws, then the tray into the ladders' grooves until both barbs click. The cables follow, the row still off:
the jumper or the feed into ROW IN, the jumper from ROW OUT to the right neighbour's ROW IN, red housing at IN,
then the camera lead into J6, not J7. Switch the row on.

The hub enumerates the rack again when a node asks for an address, and the bay takes its name from its place:
nothing to type on the node. A DATA lead that was switched off by hand comes back with `bay power on` or
`bayctl hub node B3 power-on` (the hub's own shell has no `power-on`). If the bay does not come back on the rack's page:
[Troubleshooting](troubleshooting.md#a-bay-is-missing-or-does-not-answer).
