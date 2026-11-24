# rack.yaml

[config/rack.yaml](../../config/rack.yaml) describes your rack. The build tools read it to make the printed
parts, the bill of materials and the 3D model. The bay nodes and the power hub never read it. All sizes are
in millimetres.

The file comes with an example rack of four columns and three rows. Change it to the rack you want, then
regenerate the outputs as [Edit config/rack.yaml and regenerate](../plan/choose-your-rack.md#edit-config-rack-yaml-and-regenerate)
explains. The settings of your installation, such as host names and access rules, go in another file,
[lab.yaml](lab-yaml.md).

## rows

`rows` sets the size of your rack. Give one entry per row, from the bottom up, with one `1` per column. You
can have one to four rows. The number of columns is up to you, within what the power allows:
[Choose your rack's size](../plan/choose-your-rack.md) helps you decide.

```{code-block} yaml
:caption: config/rack.yaml, the example's three rows of four
rows:
  - id: A
    height: 165
    layout: [1, 1, 1, 1]
  - id: B
    height: 165
    layout: [1, 1, 1, 1]
  - id: C
    height: 120
    layout: [1, 1, 1, 1]
```

| Key | What it sets |
|---|---|
| `id` | the row's letter, A to D. Each letter is also the hub output that feeds the row, so a rack has four rows at most |
| `height` | 165 for a row of bays with plates, 120 for a row of {term}`slot bins <slot bin>`. 165 is the most, so that the row's {term}`ladder` fits a 256 mm print bed |
| `layout` | one `1` per column. Every entry is `1`: there is no double-width bay |

## population

`population` says what each bay holds. Each key is a bay, such as `B3`, and a bay you leave out is empty. For
a plain rack, with no board in any bay, write `population: {}`. Do not leave a bare `population:`: YAML reads
it as nothing at all, and the tools refuse it.

```{code-block} yaml
:caption: config/rack.yaml, a bay of each kind
population:
  A1: { board: nucleo-64, cable: c-to-micro-b }
  A3: { board: beagleplay, cable: c-to-c, mount: sled }
  B2: { board: giga-r1-display, cable: c-to-c, plate: boards }
  B3:
    x4: v2
    boards:
      - { board: xiao, cable: c-to-c-straight, at: [8.7, 30.0] }
      - { board: rpi-pico2, cable: c-to-micro-b-straight,
          at: [74.7, 16.0], role: analyzer }
    jumpers:
      B3.1: { VREF: 3V3, P1: D7, P2: D6 }
  C1:
    plate: slots
    boards:
      - { board: nucleo-64, cable: c-to-micro-b-straight, slot: 1 }
      - { board: xiao, cable: c-to-c-straight, slot: 2 }
```

| Key | Values | What it does |
|---|---|---|
| `board` | an id from the [board library](board-library.md) | one board in the bay |
| `boards` | a list of up to four boards, or six with `plate: slots`. Each item takes `board`, `cable`, `slot`, `at`, `orient` and `role` | several boards: on a plate with a {term}`DATA ×4`, or standing on edge in a slot bin with a {term}`DATA ×6`. Use `board` or `boards`, not both |
| `cable` | an id from `cables` (below) | the cable from the board to its DATA port |
| `slot` | 1 to 4 on a DATA ×4, 1 to 6 in a slot bin | the board's port, and in a slot bin its lane. By default, the board's place in the list |
| `at` | `[x, y]` in [plate coordinates](#frames-of-reference) | where the board's front-left corner goes, on a plate with several boards. The layout tool, `tools/plate_layout.py`, moves it up to 10 mm to reach its pegs. Without `at`, the boards are packed in a row. Not in a slot bin |
| `orient` | `rear` (the default) or `side` | which way the board's USB faces: towards the port wall, or towards the drawer's right wall. Not in a slot bin |
| `role` | `analyzer` | the board is the bay's logic analyzer, not a board under test. The bill adds its Pico 2 and jumper wires. To keep it out of twister's map, give it `role: analyzer` in [lab.yaml](lab-yaml.md) too |
| `mount` | `drawer` (the default), `sled` or `fixed` | `drawer`: a drawer on a drag chain. `sled`: a {term}`sled` with no chain, and a port block behind it. `fixed`: a sled screwed in place |
| `plate` | `pegs` (the default), `boards` or `slots` | `pegs`: the honeycomb plate with pegs. `boards`: a plate made for the bay's boards, `plate_<board>`, or `plate_bay_<bay>` for several. `slots`: a slot bin, for boards up to 19.8 mm thick, 86.5 mm long and 82 mm tall ([What fits in a bay](board-library.md#what-fits-in-a-bay)) |
| `x4` | `v2` or `base` | which DATA ×4 the 3D model shows and the bill prices. `v2` has the pin matrix and the {term}`co-processor`. `base` leaves them off. A bay with `boards` and no `x4` is priced as `base` |
| `jumpers` | for each port, header pin: board pin | the Dupont wires the 3D model draws and the bill counts |
| `open` | `true` | the 3D model shows the drawer pulled out |
| `pc_cable` | `true` | the 3D model draws a laptop plugged into the bay's front port |

A bay with `boards` and no `plate: slots` gets a DATA ×4. Every other bay gets a DATA ×6. If the build cannot
use an entry, it stops with a message such as `B3: two boards on slot 2` or
`` B1: `board` and `boards` both set: one or the other ``.

The bay node and `bayctl` do not read `population`. You set a board's Zephyr target on the bay's page or in
`lab.yaml` ([Board targets](../use/board-targets.md)). [Put a board in a bay](../use/mount-a-board.md) takes
you through mounting a board.

## frame and bay

`frame` sets the frame, and `bay` the trays.

| Key | What it sets |
|---|---|
| `frame.tilt` | how far the shelves tilt, front edge lower: 20°. Keep 20° if any bay has a slot bin or a camera. A slot bin needs the slope, and the camera is placed for 20° |
| `frame.base_height` | the height from the floor to row A. The power box sits in this base |
| `frame.panel_thickness`, `panel_clearance` | the thickness of a ladder, and the play of a tray between two ladders. With `bay.width` they give the column pitch, 165.8 mm |
| `bay.width`, `bay.depth` | the size of the tray, 158 × 210 |
| `bay.carrier` | the tray's floor, walls and {term}`fascia`, and where the bay node sits in the tray |
| `bay.camera_mount`, `bay.camera_lens` | the four inserts under each bay's ceiling that a camera pod screws into, and where its lens looks down on the bay below |

## drawer, plate_grid and chain

These sections hold the design of the drawer, the board plate and the drag chain. Leave them as they are,
with two exceptions:

- `drawer.detent` sets what holds a closed drawer on the slope. `printed` is a spring tab with no extra parts,
  about 3 N. `magnet` uses two 6 × 3 mm magnets glued in, about 10 N, and adds the magnets and the glue to the
  bill.
- `chain.outer`, `radius`, `end_holes` and `end_length` set the size, the bend radius and the end pieces of
  the drag chain. Measure your own chain and enter its sizes, as
  [Enter your measurements](../print/index.md#enter-your-measurements) explains.

For reference, `drawer` also sets the drawer's front, its rear bay and port wall, the plate's thickness and
the slot bin's six 21.0 mm lanes. `plate_grid` sets the honeycomb, with its 10 mm pitch and 7.2 mm holes, and
the stops and cams of the pegs.

## cameras, cables, power_box, standalone, analyzer

| Key | What it sets |
|---|---|
| `cameras` | the bays the 3D model draws with a camera pod. Every bay has the inserts for one. The bill of materials always counts two pods |
| `cables` | each cable by id: `label`, as the bill lists it; `a` and `b`, its two ends; `length`; `style`, how the 3D model lays it (`right`, `adapter`, `side`, `straight`). A cable of style `adapter` adds two 90° adapters per board to the bill |
| `power_box` | the power box: the base cell it sits in (`column`), its place in the cell, its size and its wall |
| `power_box.charger` | the charger and cable lines of the bill |
| `standalone` | one bay on a desk: the largest PD trigger module its boxes take, 30 × 21 mm, and the rubber feet. Enter a larger module's size here ([Parts to measure before you print](../print/index.md#parts-to-measure-before-you-print)) |
| `analyzer` | the logic analyzer's firmware: its release, file, checksum and USB id. This is the only section `bayctl` reads |

## pcb

`pcb` holds the outline, the holes and the connectors of each of the rack's PCBs, so that the printed parts
fit them. Its main entries are `bay_node`, `power_hub`, `data_port_x4_v2` (the DATA ×4), `data_port_x6` and
`camera_pod`. `solder_mask` is the colour to order: green.

Leave `pcb` as it is: it describes the PCBs you order.

## After you edit the file

Run the build:

```console
$ python tools/build.py all
```

It renders every printed part again, then rebuilds the 3D model and the bill of materials. A part whose shape
did not change keeps its committed file, so git shows you which STL files to print again
([Get the STL files](../print/stl-files.md)). [Build scripts](tools.md) lists what each tool reads and writes.

`rows` and `population` decide which PCBs you order ([Order the PCBs](../plan/order-the-pcbs.md)). `cameras`
changes only the 3D model.

## Frames of reference

Each section measures its positions from one of these origins.

| Name | Origin and axes | Used by |
|---|---|---|
| Frame | the front-left-bottom corner of the leftmost base ladder. X to the right, Y to the back, Z up | `frame` |
| Row | a row's front-bottom edge, tilted by `frame.tilt`: Y along the slope, Z square to the shelf | `rows` |
| Carrier | a row's frame, moved to the front-left corner of one bay's tray | `bay`, `chain` |
| Drawer | the drawer's left side and its front face | `drawer`, the DATA boards' `x0` under `pcb` |
| Plate | the plate's front-left corner. x to the right, y towards the port wall | `population` › `at`, the layout tool's output |
| KiCad | each PCB's own. On the bay node and the hub, y = 0 is the rear edge | `pcb` |

A board's outline, holes and USB in [boards.yaml](board-library.md#the-fields-of-boards-yaml) are measured from
the bottom-left corner of the vendor's drawing.
