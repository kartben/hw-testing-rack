# Add a board to the library

To use a board that the [board library](../reference/board-library.md) does not list, give it an entry in
[mechanical/boards/boards.yaml](../../mechanical/boards/boards.yaml). The layout tool reads this entry to place
the board and its pegs. The bay's page reads it to suggest the board's Zephyr target.

## Measure the board

First check that the board fits a bay ([What fits in a bay](../reference/board-library.md#what-fits-in-a-bay)).
Then measure it from the vendor's mechanical drawing or Gerber files, or with a calliper. Give every position in
millimetres from the bottom-left corner of the outline, with the board turned as in the vendor's drawing.

| Measure | Field |
|---|---|
| The outline, width and length. An error of 1 mm puts every peg in the wrong place. | `size` |
| Each mounting hole, and their diameter | `holes`, `hole_d` |
| The edge the debug USB socket is on, the socket's centre along that edge, and its type | `usb` |
| The longest pin or part under the PCB. A Nucleo's morpho pins need 12 mm. | `standoff` |
| The tallest part on top of the PCB | `height` |
| The stretches of each edge that no peg may touch: headers, connectors, pins under the edge | `pegs.keepout` |
| For a slot bin: how far the board reaches under its PCB and over it, a plug in its USB included | `on_edge` |

## Write its entry

An entry starts with the board's id, the name you will use in `config/rack.yaml`. Here is the micro:bit's
entry, one of the shortest:

```{literalinclude} ../../mechanical/boards/boards.yaml
:language: yaml
:caption: mechanical/boards/boards.yaml
:start-at: "  microbit-v2:"
:end-before: "  frdm-mcxn947:"
:dedent: 2
```

- `name` and `size` are required. `usb` defaults to the middle of the top edge, and `standoff` to 6 mm.
- Add `orient: side` for a small board. Its USB then faces the drawer's right wall, and a straight cable lies
  flat into it.
- Set `verified: true` once you have measured the outline and the holes, or taken them from the vendor's
  drawing.

Every field is on [Board library](../reference/board-library.md#the-fields-of-boards-yaml). If you measured a
board, send its entry in a pull request so that others can use it ([CONTRIBUTING.md](../../CONTRIBUTING.md)).

## Run the layout tool

Name the board in a bay's entry of `config/rack.yaml` ([Put a board in a bay](mount-a-board.md)). Then run the
layout tool and its tests:

```console
$ python tools/plate_layout.py A2
$ python -m unittest discover -s tools/tests -p "test_plate_layout.py"
```

The tests fail when a board of your rack is left with `no peg fits`, with fewer than two pegs, or with neither a
cam nor a pin. If a cam lands on a part of your board, add that stretch of the edge to `pegs.keepout` and run
the tool again.

## What the notes mean

| Note | The board |
|---|---|
| `against the drawer's left wall`, `right wall` or `front panel` | leans on the drawer on that side. A side wall can hold only a board whose `standoff` is 6.4 mm or less. |
| `no cam on its B edge` (or `L`, `R`, `F`) | sits against stops, with no cam to push it onto them |
| `one cam only` | sits on a pin, with one cam where the tool looks for two |
| `held along one axis by friction only` | has nothing to hold it along one axis |
| `no peg fits: placed at its hint, unheld` | is not held at all |

The tool accepts the first three: several boards of the example rack have them. The last two mean the board needs
[another way to be held](#if-pegs-cannot-hold-it).

## Make pegs for a new height

The STL files in the repository have pegs for these heights:

- stops and cam bases: 5, 6, 9, 10, 11 and 12 mm;
- pins for 2.1 mm holes: 9 mm;
- pins for 3.2 mm holes: 6 and 12 mm.

For another height, build the pegs it needs. For 8 mm:

```console
$ python tools/build.py stl --only peg_stop_h8 peg_base_h8
```

A pin's file is named after the hole, in tenths of a millimetre: `peg_pin_d25_h8` for a 2.5 mm hole. The build
needs OpenSCAD or Docker ([Get the STL files](../print/stl-files.md)).

## If pegs cannot hold it

Some boards get no peg layout. The ESP32 DevKitC boards have headers along both long edges and no hole, so
nothing but friction holds them. The F746G-DISCO (154 mm long) and the MIMXRT1170-EVKB (165 mm wide) get
`no peg fits`.

| What to do | When |
|---|---|
| Use a lane of a slot bin ([Stand boards on edge in a slot bin](mount-a-board.md#on-edge-in-a-slot-bin-with-a-data-6)) | The board is at most 19.8 mm thick, 86.5 mm long and 82 mm tall, and needs no wires. The example rack holds its DevKitC boards this way. |
| Print a plate made for the board | It fits on the plate, but no peg layout holds it. |
| Nothing | It is wider than the drawer. |

For a plate made for the board, set `plate: boards` in the bay's entry and run `python tools/build.py stl`. It
makes `plate_<board>.stl`, or `plate_bay_<bay>.stl` for a bay of several boards. The plate has heat-set inserts
under the board's holes. For a board without holes, or with `fence: true`, it has corner fences instead.

## Give it a Zephyr target

The `zephyr` field holds the board's defaults for CI:

| Key | Holds |
|---|---|
| `platform`, or `choices` for a family of boards | its target, as twister names it |
| `runner` | its west runner |
| `console` | where twister reads its console |
| `usb` | the USB ids of its debug socket |

The bay's page suggests the target when a device with one of those USB ids is on a port. These suggestions are
built into the node's firmware. A new entry shows there only after you rebuild the firmware and update the
nodes ([Update the firmware](update-firmware.md)). Until then, type the target in the board target dialog
([Board targets](board-targets.md#set-it-on-the-bays-page)).
