# Put a board in a bay: plate, pegs, slot bin

A board lies on its bay's honeycomb plate, held at its edges by clip-in pegs, or stands on edge in a slot bin;
one short USB cable joins it to a port of the bay's DATA board. No screw holds it and no plate is made for it,
so the same four moves serve every time a board changes: write the board into `config/rack.yaml`, ask the
layout tool where its pegs go, print the pegs it names, clip them in.

:::{status} designed
`tools/plate_layout.py` places every board of the example rack, and its tests run in CI. The layouts of B3,
B4 and A1 that the tool gave on 2026-10-19 were checked on exact solids: no clash, every stop, cam and pin
touching its board. The tool has changed since (B4's UNO R4 then leaned on the drawer's wall; it now gets a
pin). No peg has been clipped into a plate and no board has been put in a bay.
[What exists today](../plan/status.md#status-plate).
:::

## The plate and its four kinds of peg

```{figure} ../img/plate-pegs.jpg
:alt: Two honeycomb plates seen from above, one with four small boards between white stops and orange cams, one with an UNO R4 and a bobbin

Render of 2026-10-19. Left, four small boards on one plate (B3): white stops, orange cams. Right, an UNO R4
against the drawer's left wall, two cams on its right edge (B4), the bobbin at the rear; today the layout tool
gives B4 a pin and two cams. The rims carry the numbers of the odd rows.
```

One plate takes every board: 134.5 × 159.4 mm, 5 mm thick, a honeycomb of 177 hexagonal holes 10 mm apart,
in 17 rows. The odd rows are numbered on both rims, row 1 at the front. The plate drops into the drawer over
two locating pins and lifts out by its two finger holes; the recesses of its rear edge go under the port
wall's slots.

A peg clips into any hole and stays inside the plate. Its hexagonal plug has three spring skins whose nubs
snap under a ledge in the hole; there they rest unloaded, so a peg does not loosen however often it moves.
Nothing comes out under the plate, and the hexagon keeps a peg from turning.

| Peg | STL file | What it does |
|---|---|---|
| Stop | `peg_stop_h<H>` | Places the board. An eccentric post: its ledge carries the board's edge, its neck touches the edge and a 45° lip holds it down. The post sits 3.55 mm off the plug's axis, so the six ways the plug goes in are six places in each hole; an arrow on the flange points to the post |
| Cam on its base | `peg_base_h<H>` and `peg_cam` | Clamps the board. The base's split pin carries a cam with a spiral band, 3 mm of travel: turned clockwise it pushes the board onto its stops and presses its top edge down; turned on, it falls open |
| Pin | `peg_pin_d<hole>_h<H>` | Holds a board whose long edges are lined with headers: an eccentric pin through one of its mounting holes, 0.3 mm thinner than the hole. Cams on the other edges push the board onto it |
| Bobbin | `peg_bobbin` | Takes the loop of the cable's spare length |

`<H>` is the board's standoff in millimetres, from the plate's top to the board's underside, as the
[board library](../reference/board-library.md) gives it.

## Say which board is in which bay

The bay's entry in `population` of [config/rack.yaml](../../config/rack.yaml) names the board and its cable:

```{literalinclude} ../../config/rack.yaml
:language: yaml
:caption: config/rack.yaml › population
:start-at: "  A1: {"
:end-before: "  A3: {"
:dedent: 2
```

`board` is an id of the [board library](../reference/board-library.md#the-boards); for a board that is not in
it, start at [A board that is not in the library](add-a-board.md). `cable` is one of the cables
[below](#the-cable-to-the-data-board). The other keys of an entry are on
[rack.yaml](../reference/rack-yaml.md#population-one-entry-per-bay).

The layout tool, the bill of materials and the 3D model read this entry. The bay node and `bayctl` do not:
which Zephyr target the board is, you tell the bay on its page ([Board targets](board-targets.md)).

## Ask the tool where the pegs go

```console
$ python tools/plate_layout.py A2
A2:
  A2 nucleo-144: front-left corner at (30.3, 10.6), 6.9 mm from its hint
    row  2, hole 11: cam on base H12, R edge
    row  4, hole  9: pin d2.9 H12, arrow at 12:30
    row 16, hole 11: cam on base H12, R edge
  bobbin: row 14, hole 1
```

It needs only Python and PyYAML
([plate_layout.py](../reference/tools.md#plate-layout-py)). The tool holds a board the way a fixture holds a
part: on each axis stops on one edge, or the drawer's wall, and cams on the opposite edge. It keeps every peg
clear of the board's headers and connectors, of its USB plug and of the other boards. A NUCLEO-144 has header
pins under both long edges, so it gets a pin through a mounting hole and two cams.

*The reading that follows is worked out from `describe()` and `clock()` in
[tools/plate_layout.py](../../tools/plate_layout.py); nobody has placed a peg from this output yet.*

```{figure} ../img/viewer/a2-plate-from-above.jpg
:alt: Bay A2 of the 3D model from above: a NUCLEO-144 on the honeycomb plate, two orange cams on its right edge, a white bobbin on the left, its cable to the leftmost port
:width: 70%

The 3D model, bay A2 from above, the port wall at the top. The two cams are in rows 16 and 2, on the board's
right edge; the bobbin in row 14, on the left. The pin of row 4 is under the board.
```

- The first line is where the board ends up: its front-left corner, in millimetres from the plate's
  front-left corner, x to the right and y towards the port wall. The tool moved it 6.9 mm from its usual
  place, centred with room behind for its plug, so that the pegs fall on holes.
- `row 4, hole 9` is row 4 from the front, ninth place from the left. The count is of places, with or without
  a hole: an odd row has 12, an even row 13, and the plate has no hole beside a locating pin, a finger hole,
  the two pin holes over the node's buttons or a recess of the rear edge. Row 16 has holes at places 11, 12
  and 13 only: `row 16, hole 11` is the first hole there is.
- `arrow at 12:30` is the turn of a pin or a stop in its hole: the hour its flange's arrow points to, seen
  from above with 12 o'clock at the port wall. A plug goes in six ways: 12:30, 2:30, 4:30, 6:30, 8:30, 10:30.
- `R edge` is the edge of the board the peg holds: `L` and `R`, left and right from the drawer's front, `F`
  the front, `B` the back, at the port wall.
- `bobbin` appears only for a bay with one board.

A `note:` line at the end of a bay says a board leans on the drawer, or is held by less than a full set of
pegs, or not at all:
[What the notes mean](add-a-board.md#what-the-notes-mean). The tool prints nothing for a bay without boards
on pegs: an empty bay, a slot bin (C1 to C4 of the example), a board on its own plate (B2). Every term of
the output, in one table: [plate_layout.py](../reference/tools.md#plate-layout-py).

The 3D model shows every peg in its hole, turned as the layout says, the cams in orange:
[bay A2, drawer out](/viewer/?bay=A2&openbay=1&view=bay).

## Print the pegs it names

| The output says | Print |
|---|---|
| `stop H12` | `peg_stop_h12` |
| `cam on base H12` | `peg_base_h12` and `peg_cam` |
| `pin d2.9 H12` | `peg_pin_d32_h12`: the file is named for the board's 3.2 mm hole, the output for the pin, 0.3 mm thinner |
| `bobbin` | `peg_bobbin` |

The NUCLEO-144 of A2 takes one `peg_pin_d32_h12`, two `peg_base_h12`, two `peg_cam` and one `peg_bobbin`.
The pegs of every board of the library, 17 files, are among the committed STL files
([Get the STL files](../print/stl-files.md)). Print pegs upright, flange down, and cams flange down, in PETG
at 0.2 mm, without supports.

## Clip the pegs, set the board, turn the cams

:::{build-step} 1
:drawing: p1
:detail: clip
:alt: A honeycomb plate with stops, cams and a bobbin clipped in
:parts: hx=1, ps, pc, pp, po
:click:

With the plate on the bench, clip each peg into the hole the layout names: a stop or a pin with its arrow at
the hour given, a cam on its base, turned open. Push until the flange sits on the plate.
:::

:::{build-step} 2
:drawing: p2
:alt: A board on the plate against its stops, three cams around it

Set the board on the pegs, against its stops or over its pin. Turn each cam clockwise until it bites.
:::

:::{build-step} 3
:drawing: p3
:alt: The plate, with its board, lowered into the drawer

Lower the plate into the drawer over its two pins, row 1 at the front.
:::

To take a board out, turn its cams on until they fall open and lift it.

## The cable to the DATA board

```{figure} ../img/viewer/a2-board-cable.jpg
:alt: Close view of the 3D model: a straight USB-C plug standing in the leftmost slot of the port wall, its cable arching over the rear edge of a NUCLEO-144 to a plug standing on a 90° adapter
:width: 80%

The 3D model, bay A2. A straight USB-C plug stands in the port wall's first slot; the cable arches over the
board's rear edge to its micro-B socket, where the plug stands on a 90° adapter. The bobbin waits on the left.
```

A short USB cable belongs to the board. Its drawer end is USB-C, a straight plug standing in one of the port
wall's slots; an angled plug fits only if its cable leaves upwards. A board alone in its bay takes port 1 of
the DATA ×6, the leftmost seen from the board, or the next one where the cable does not lie clear from port 1
(A3 and B4 of the example take port 2). The port gives the board its number: in the first socket, the
NUCLEO-144 of A2 is `A2.1` ([A bay that holds one board](names.md#a-bay-that-holds-one-board)).

How the cable lies follows the board:

- A small board turns its USB to the drawer's right wall (`orient: side` in the board library: a Pico, an
  UNO R4). A plain straight cable of 15 to 20 cm leaves the port forwards, bends once, with a radius of 10 mm
  or more, and lies flat on the plate into the board's side.
- A long board (a Nucleo, an nRF DK, a FRDM) faces its USB to the port wall, 17 to 23 mm away. The cable
  leaves the port forwards and makes a small arch over the board's rear edge. A USB-C socket on the board
  takes a right-angle plug; a micro-B or mini-B socket takes a 90° adapter, its female side up, with the
  cable's straight plug standing on it.
- The arch stays under about 105 mm above the plate's row; a camera pod hangs down to 120. Loop the spare
  length round the bobbin, beside the board and not over it: the camera looks at the board.

The `cable` of a bay's entry is one of these:

```{literalinclude} ../../config/rack.yaml
:language: yaml
:caption: config/rack.yaml › cables
:start-at: "  c-to-c:       {"
:end-before: "  data-lead:"
:dedent: 2
```

Many short cables are charge-only; what to buy is on
[Cables and pinouts](../reference/cables.md#the-cable-to-your-board).

## A board with two USB connectors

*Worked out from the port rules of [One node, several boards](../multi-dut-node.md#power-budget) and
[ports.c](../../firmware/bay-node/src/ports.c); nobody has done it yet.*

A board with one USB socket for its probe and another for its own USB takes two ports of the bay's DATA board,
and so two cables and two names, such as `A2.1` and `A2.2`. An entry of `population` holds one cable: the
second one is in neither the file nor the bill of materials.

Such a board is fed through both ports, and the ports are built for one supply each:

- A port that is off and reads more than 3.5 V on its VBUS does not switch on. If the board carries the
  supply of one connector to the other, then once one port feeds it the other is refused with a 409, "the
  port's VBUS is up while it is off (a board powered from elsewhere): it comes on once that has gone", and
  waits.
- Cycling one port does not power the board down: the other still feeds it. To power the board down, switch
  both ports off ([Power-cycle or reset a board](power-and-reset.md)).

## Several boards on one plate, or on edge in a slot bin

### On one plate, with a DATA ×4

A bay with a DATA ×4 holds up to four boards on its plate. Its entry lists them under `boards:`, as B3 of
the example does:

```{literalinclude} ../../config/rack.yaml
:language: yaml
:caption: config/rack.yaml › population › B3
:start-at: "- { board: xiao,      cable: c-to-c-straight,       at: [8.7, 30.0] }"
:end-at: "at: [107.7, 30.0] }"
:dedent: 6
```

Each board is on the DATA ×4 port of its rank in the list, or of its `slot`. `at` is where its front-left
corner goes on the plate, in millimetres from the plate's front-left corner; the layout tool moves it by up to
10 mm to reach its pegs. Without `at` the boards are packed in a row. Such a bay gets no bobbin: each cable is
straight at both ends and lies in an S between its port and its board. Four is the most, and fewer may fit: on
B1, beside a Pico 2 and a Nano Matter, a third board leaves no room for its pegs' cams. The wires from the
DATA ×4's pin headers to the boards: [Wires between boards](wires.md).

### On edge in a slot bin, with a DATA ×6

*Worked out from `drawer.slot_bin` in `config/rack.yaml` and `dense_layout()` in
[tools/rackcfg.py](../../tools/rackcfg.py); nobody has done it yet.*

```{figure} ../img/viewer/c2-slot-bin.jpg
:alt: A drawer of the 3D model pulled out, four boards standing on edge between the dividers of a slot bin, a cable from each to the DATA ×6 behind
:width: 80%

The 3D model, bay C2: boards in lanes 1, 3, 4 and 5, each on the port behind its lane.
```

A bay with `plate: slots` has a slot bin where the plate goes
([Fit out a tray](../build/fit-out-a-tray.md#a-slot-bin-in-the-plates-place)) and takes up to six boards:

```{literalinclude} ../../config/rack.yaml
:language: yaml
:caption: config/rack.yaml › population › C2
:start-at: "  C2:"
:end-before: "  C3:"
:dedent: 2
```

`slot: k` is lane k, counted from the left, and port k of the DATA ×6 behind it. Stand the board in its lane
on the edge nearer its USB socket, the socket towards the port wall; the rack's tilt slides it forwards to the
front stop, and a thin board leans on a divider. One straight 15 cm cable joins it to its port. These bays
take no jumper wires: a board that needs wires goes to a bay with a plate.

A lane takes a board up to 19.8 mm thick in all, 86.5 mm long and 82 mm tall
([which boards of the library fit](../reference/board-library.md#how-each-is-held)). No peg is involved and
`plate_layout.py` prints nothing for the bay. A board too big for its lane is reported only when the 3D model's files are
built (`python tools/build.py web`), as a warning: a BeaglePlay in lane 1 of C1 gives
`warning: C1.1: 21.6 mm thick, its lane takes 19.8`.

## No battery on a board in the rack

Take the battery off a board, or out of its chassis, before it goes into the rack. Each bay's DATA lead is
limited to about 1.76 A and each port to 0.5 A. Four small boards without batteries take 0.3 to 0.8 A between
them; a board charging its LiPo takes 0.6 to 1.2 A on its own (a Wio Terminal on its battery chassis about 1.0
to 1.2 A, a XIAO ESP32-C3 with a cell about 0.73 A), and a LiPo charging unattended in a closed drawer is a
fire risk.
