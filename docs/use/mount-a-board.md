# Put a board in a bay

A board lies on its bay's honeycomb plate, held at its edges by clip-in pegs. A short USB cable joins it to a
port of the DATA board at the back of the drawer.

To put a new board in a bay, name it in `config/rack.yaml` and run the layout tool to find where its pegs go.
Then print the pegs and clip them in.

## No battery on a board in the rack

Take the battery off a board, or out of its case, before it goes into the rack. A board charging its LiPo draws
0.6 to 1.2 A, more than a port's 0.5 A. A LiPo charging in a closed drawer is also a fire risk
([Power budget and queued ports](power-budget.md)).

## The pegs

```{figure} ../img/viewer/a2-plate-from-above.jpg
:alt: Bay A2 of the 3D model from above: a NUCLEO-144 on the plate, two orange cams on its right edge, a white bobbin on its left
:width: 70%

The 3D model: bay A2 from above, the port wall at the top. Two orange cams hold the board's right edge, a pin
under the board goes through one of its holes, and the cable loops round the white bobbin.
```

| Peg | STL file | What it does |
|---|---|---|
| Stop | `peg_stop_h<H>` | Places the board. An arrow on its flange shows which way its off-centre post faces. |
| Cam on its base | `peg_base_h<H>` and `peg_cam` | Turn it clockwise: it pushes the board onto its stops and holds it down. |
| Pin | `peg_pin_d<hole>_h<H>` | Goes through a mounting hole, for a board whose edges are lined with headers. |
| Bobbin | `peg_bobbin` | Takes the cable's spare length. |

`<H>` is the height of the board's underside above the plate, in millimetres, from the
[board library](../reference/board-library.md).

## Say which board is in which bay

Each bay of your rack has an entry under `population` in [config/rack.yaml](../../config/rack.yaml). The entry
names the bay's board and its cable:

```{literalinclude} ../../config/rack.yaml
:language: yaml
:caption: config/rack.yaml › population
:start-at: "  A1: {"
:end-before: "  A3: {"
:dedent: 2
```

`board` is the board's id in the [board library](../reference/board-library.md). For a board that is not in
it, see [Add a board to the library](add-a-board.md). `cable` is one of the cables
[listed below](#the-cable-to-the-data-board). The other keys are on [rack.yaml](../reference/rack-yaml.md).

The bay node does not read this file. To tell the bay which Zephyr board it holds, set a
[board target](board-targets.md) on the bay's page.

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

The tool needs Python and PyYAML ([plate_layout.py](../reference/tools.md)). Read its output like this:

- The first line is where the board goes. It gives the board's front-left corner, in millimetres from the
  plate's front-left corner: x to the right, y towards the port wall at the back of the drawer.
- `row 4, hole 9` is the ninth place from the left in row 4, counting rows from the front. The odd rows are
  numbered on the plate's rim. An odd row has 12 places and an even row 13. Some places have no hole, so count
  places, not holes.
- `arrow at 12:30` is the hour the peg's arrow points to, seen from above, with 12 o'clock at the port wall.
- `R edge` is the edge of the board that the peg holds: `L` left, `R` right, `F` front, `B` back.
- `bobbin` appears only for a bay with one board.

A `note:` line at the end means the board leans on the drawer or is not fully held
([What the notes mean](add-a-board.md#what-the-notes-mean)). To check the layout, open the 3D model: it shows
every peg in its hole, turned as the tool says ([bay A2, drawer out](/viewer/?bay=A2&openbay=1&view=bay)).

## Print the pegs

| The output says | Print |
|---|---|
| `stop H12` | `peg_stop_h12` |
| `cam on base H12` | `peg_base_h12` and `peg_cam` |
| `pin d2.9 H12` | `peg_pin_d32_h12` |
| `bobbin` | `peg_bobbin` |

The output gives the pin's own diameter, 2.9 mm here. Its file is named after the board's hole, which is
0.3 mm wider: `d32` for 3.2 mm.

The pegs of every board in the library are among the STL files ([Get the STL files](../print/stl-files.md)).
Print them upright, flange down, in PETG at 0.2 mm, without supports.

## Clip the pegs and set the board

:::{build-step} 1
:drawing: p1
:detail: clip
:alt: A honeycomb plate with stops, cams and a bobbin clipped in
:parts: hx=1, ps, pc, pp, po
:click:

With the plate on the bench, clip each peg into the hole the layout names. Turn a stop or a pin so that its
arrow points to the hour given. Put each cam on its base, turned open. Push until the flange sits on the plate.
:::

:::{build-step} 2
:drawing: p2
:alt: A board on the plate against its stops, three cams around it

Set the board on the pegs, against its stops or over its pin. Turn each cam clockwise until it grips.
:::

:::{build-step} 3
:drawing: p3
:alt: The plate, with its board, lowered into the drawer

Lower the plate into the drawer over its two pins, row 1 at the front.
:::

To take a board out, keep turning its cams clockwise until they fall open, and lift it.

## The cable to the DATA board

```{figure} ../img/viewer/a2-board-cable.jpg
:alt: The 3D model: a USB-C plug in the port wall, its cable arching over the rear edge of a NUCLEO-144 to a 90° adapter
:width: 80%

The 3D model, bay A2: the cable arches from the port wall over the board's rear edge to a 90° adapter in its
micro-B socket.
```

The drawer end of the cable is a straight USB-C plug that stands in a slot of the port wall. An angled plug fits
only if its cable leaves upwards.

A board alone in its bay takes port 1, the leftmost. If its cable does not lie clear from there, use the next
port ([Bays, ports and addresses](names.md#a-bay-that-holds-one-board)).

- A small board, such as a Pico or an UNO R4, turns its USB towards the drawer's right wall. A straight cable of
  15 to 20 cm bends once, with a radius of 10 mm or more, and lies flat on the plate.
- A long board, such as a Nucleo, an nRF DK or a FRDM, faces its USB towards the port wall. The cable arches over
  the board's rear edge. A USB-C socket takes a right-angle plug. A micro-B or mini-B socket takes a 90° adapter,
  female side up, with the cable's straight plug standing on it.
- Keep the arch below about 105 mm above the plate, because a camera pod hangs down to 120 mm. Loop the spare
  length round the bobbin, beside the board, where the camera can still see the board.

The `cable` of a bay's entry is one of these, from the `cables` section of `config/rack.yaml`:

| `cable` | The cable |
|---|---|
| `c-to-c` | USB-C straight to USB-C 90°, 15 cm |
| `c-to-micro-b` | USB-C straight to micro-B straight, 25 cm, on a micro-B 90° adapter |
| `c-to-mini-b` | USB-C straight to mini-B straight, 25 cm |
| `c-to-c-straight` | USB-C to USB-C, straight, 15 to 20 cm |
| `c-to-c-straight-20` | USB-C to USB-C, straight, 20 cm |
| `c-to-micro-b-straight` | USB-C to micro-B, straight, 15 cm |

Many short cables are charge-only. [Cables and pinouts](../reference/cables.md) says which ones to buy.

## Several boards on one plate

A bay with a DATA ×4 holds up to four boards on its plate, listed under `boards:`. Here is bay B3 of the example
rack, without its other keys:

```{code-block} yaml
:caption: config/rack.yaml › population › B3
B3:
  boards:
    - { board: xiao,      cable: c-to-c-straight,       at: [8.7, 30.0] }
    - { board: rpi-pico2, cable: c-to-micro-b-straight, at: [41.7, 16.0] }
    - { board: rpi-pico2, cable: c-to-micro-b-straight, at: [74.7, 16.0] }
    - { board: xiao,      cable: c-to-c-straight,       at: [107.7, 30.0] }
```

The first board in the list goes on port 1, the second on port 2, and so on, unless `slot` gives its port. `at`
is where the board's front-left corner goes on the plate, in millimetres. The layout tool may move it by up to
10 mm to reach its pegs. Each cable has straight plugs at both ends and lies in an S. Large boards may not fit
four to a plate. To wire the DATA ×4's pin headers to the boards, see [Wires between boards](wires.md).

(on-edge-in-a-slot-bin-with-a-data-6)=
## Stand boards on edge in a slot bin

```{figure} ../img/viewer/c2-slot-bin.jpg
:alt: The 3D model: a drawer pulled out, four boards standing on edge in a slot bin, each cabled to the DATA ×6 behind
:width: 80%

The 3D model, bay C2: boards in lanes 1, 3, 4 and 5, each cabled to the port behind its lane.
```

A bay with a DATA ×6 can hold up to six boards standing on edge. It has a slot bin in place of the plate, and
`plate: slots` in its entry ([Fit out a tray](../build/fit-out-a-tray.md)):

```{literalinclude} ../../config/rack.yaml
:language: yaml
:caption: config/rack.yaml › population › C3
:start-at: "  C3:"
:end-before: "  C4:"
:dedent: 2
```

`slot: k` puts the board in lane k from the left, cabled to port k of the DATA ×6. Stand the board on the edge
nearer its USB socket, with the socket towards the port wall. The rack's tilt slides it forward to the front
stop. Use a straight 15 cm cable. A board in a slot bin takes no jumper wires.

A lane takes a board up to 19.8 mm thick, 86.5 mm long and 82 mm tall. When you build the 3D model with
`python tools/build.py web`, a board too big for its lane shows as a warning.

## A board with two USB connectors

A board with one USB socket for its probe and another for its own USB takes two ports, with two cables and two
names, such as `A2.1` and `A2.2`. A bay's entry names only one cable, so buy the second one yourself.

- A port that is off does not switch on while its VBUS reads more than 3.5 V. If the board passes power from one
  connector to the other, the second port waits until the first is off.
- Cycling one port does not power the board down. Switch both ports off
  ([Power-cycle or reset a board](power-and-reset.md)).

Give the board target to the probe's port, and keep the other port out of twister's map
([Board targets](board-targets.md#keep-a-board-out-of-twisters-map)).
