# A board that is not in the library

A board the library does not know takes one entry in
[mechanical/boards/boards.yaml](../../mechanical/boards/boards.yaml): its outline, its mounting holes, where
its USB socket is and how high it stands over the plate. From that entry the layout tool places the board,
the build makes its pegs, and the bay's page suggests its Zephyr target.

:::{status} designed
Each of the 20 boards of the library is such an entry, and the layout tool's tests run in CI on the boards of
the example rack. No board has been held by pegs, in or out of the library. [What exists today](../plan/status.md#status-plate).
:::

The steps below are worked out from the header of `boards.yaml` and from
[tools/plate_layout.py](../../tools/plate_layout.py); no source holds them and nobody has followed them yet.

## Measure the board

Check first that the board fits a bay at all:
[What fits in a bay](../reference/board-library.md#what-fits-in-a-bay). Then work from the vendor's mechanical
drawing or Gerber files, or from the board and a calliper. Every position is in millimetres from the bottom-left corner of the
outline, as the drawing shows the board.

| Measure | It becomes | Why it matters |
|---|---|---|
| The outline, width and length | `size` | the pegs touch the edges: an outline that is 1 mm out puts every peg in the wrong place |
| Each mounting hole and its diameter | `holes`, `hole_d` | a board with headers along its edges is held by a pin through a hole |
| The edge its debug USB socket is on, the socket's centre along that edge, its type | `usb` | the board is turned so that this socket faces the port wall, and its plug's way is kept clear of pegs |
| The gap the board needs under it: the longest pin or part under the PCB | `standoff` | it is the height of its pegs. A Nucleo's morpho pins take 12 mm |
| The tallest part over the PCB | `height` | the 3D model draws it, and a slot bin counts it when `on_edge` is not given |
| The stretches of each edge a peg must not touch: a header or a connector at the edge, pins under it | `pegs.keepout` | the tool places no stop and no cam there |
| For a slot bin, how far the board reaches under its PCB and over it, a plug in its USB socket included | `on_edge` | the two add up to the thickness a lane must take, 19.8 mm at most |

No source states how tall a board on a plate may be. The cables' arches stay under about 105 mm above the row,
and a camera pod hangs down to 120 mm.

## Write its entry in boards.yaml

An entry is a key, the id that `config/rack.yaml` will name, and its fields. The micro:bit's is among the
shortest:

```{literalinclude} ../../mechanical/boards/boards.yaml
:language: yaml
:caption: mechanical/boards/boards.yaml
:start-at: "  microbit-v2:"
:end-before: "  frdm-mcxn947:"
:dedent: 2
```

`name` and `size` are required; `usb` defaults to the middle of the top edge and `standoff` to 6 mm. Add
`orient: side` for a small board, so that its USB faces the drawer's right wall and a straight cable lies flat
into it. Set `verified: true` once the outline and the holes are measured or come from the vendor's own
drawing or Gerbers. Every field: [The fields of boards.yaml](../reference/board-library.md#the-fields-of-boards-yaml).

Eight boards of the library still have approximate outlines
([Unverified outlines](../reference/board-library.md#unverified-outlines)): a measured entry for one of them, or
for a board the library lacks, is worth proposing ([Contribute](../engineering/contribute.md)).

## Put it in a bay and run the layout tool

Name the board in a bay's entry of `config/rack.yaml` ([Put a board in a bay](mount-a-board.md)), then:

```console
$ python tools/plate_layout.py A2
```

The lines it prints are the pegs, and a `note:` at the end says when the board leans on the drawer or the pegs
do not hold it fully. To check the new entry the way CI does, run the layout tool's tests:

```console
$ python -m unittest discover -s tools/tests -p "test_plate_layout.py"
```

They fail when a board of the configured rack is left with `no peg fits`, with fewer than two pegs, or with
neither a cam nor a pin.

## What the notes mean

Read from `realise()`, `pin_layout()` and `solve()` in `tools/plate_layout.py`:

| Note | The board | In the code |
|---|---|---|
| `against the drawer's left wall`, `right wall`, `front panel` | leans on the drawer on that side and takes no stops there. The side walls only serve a board whose `standoff` is 6.4 mm or less | a full layout |
| `no cam on its B edge` (or `L`, `R`, `F`) | sits against stops on the opposite edge, and no cam pushes it onto them | accepted, ranked below a layout with the cam |
| `one cam only` | is on a pin with one cam where the tool looks for two | accepted, ranked below |
| `held along one axis by friction only` | has neither stop, cam nor wall along one axis | what is left when nothing fits on that axis |
| `no peg fits: placed at its hint, unheld` | is not held | no layout |

The example rack lives with the two middle notes: B1 and B3 carry them, on their Pico 2s, XIAOs and Nano
Matter. Nobody has tried whether a board with such a note stays put when its cable is pulled. The last two
are failures: the board needs [another way to be held](#if-pegs-cannot-hold-it).

A layout moves when the entry moves. If a cam lands on a part of your board, add that stretch of the edge to
`pegs.keepout` and run the tool again.

## A peg height that does not exist yet

The build makes one stop and one cam base for each `standoff` of the library, and one pin for each pair of
hole diameter and `standoff` among the boards that have holes. The committed files cover standoffs of 5, 6, 9,
10, 11 and 12 mm, and pins for 2.1 mm holes at 9 mm and 3.2 mm holes at 6 and 12 mm. A board with another
standoff or another hole needs its own; for a standoff of 8 mm:

```console
$ python tools/build.py stl --only peg_stop_h8 peg_base_h8
```

A pin's file is named for the hole, in tenths of a millimetre:
`peg_pin_d25_h8` for a 2.5 mm hole. The build needs OpenSCAD or Docker
([Get the STL files](../print/stl-files.md#rebuild-them)).

## If pegs cannot hold it

Four boards of the library get no peg layout when the tool is run on each alone in a bay. The two ESP32
DevKitC boards have headers along both long edges, both USB sockets on a short one and no hole: they are held
by friction only. The F746G-DISCO, 154 mm long, cannot clear what hangs over the plate's front (the display's
frame and the front's joints), and the MIMXRT1170-EVKB is 165 mm wide: for both, `no peg fits`. The example
rack stands its DevKitC boards in slot bins.

| Way out | When | What to do |
|---|---|---|
| A lane of a slot bin | the board is at most 19.8 mm thick, 86.5 mm long and 82 mm tall, and needs no wires | [On edge in a slot bin](mount-a-board.md#on-edge-in-a-slot-bin-with-a-data-6) |
| Its own plate | it fits the plate but no peg layout holds it | say `plate: boards` in the bay's entry and run `python tools/build.py stl`: it renders `plate_<board>.stl` (a bay of several boards: `plate_bay_<bay>.stl`), with heat-set inserts under the board's holes or, for a board without holes or with `fence: true` in its entry, corner fences and support pads. B2 of the example holds its GIGA R1 and display this way, the shield hiding the GIGA's edges |
| None | it is wider than the drawer, as the MIMXRT1170-EVKB is | it would take a double-width bay, which is not designed |

The own plate is the earlier way of holding boards, kept for these cases.

## Tell twister what it is

The `zephyr` field of the entry carries the board's defaults for CI: its target as twister names it
(`platform`, or `choices` for a family), its west `runner`, its `console` and the USB ids (`usb`) its debug
socket shows. `bayctl` takes the runner from it, and the bay's page suggests the target when a device with
one of those ids is on a port. The page's list is compiled into the node's firmware: a new entry shows there
after the firmware is built and updated again. Until then, type the target on the page
([Board targets](board-targets.md#set-it-on-the-bays-page)).
