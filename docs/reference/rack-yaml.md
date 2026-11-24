# rack.yaml

[config/rack.yaml](../../config/rack.yaml) describes one rack: its frame and rows, its bays and what each one
holds, its cables, its power box and the outlines of its PCBs. Every printed part, the bill of materials and
the 3D model are generated from it; the bay nodes and the power hub never read it. All sizes are in
millimetres.

## What the file drives

| Read by | What it reads | What it makes |
|---|---|---|
| `python tools/build.py config` (and every other `build.py` command first) | every section but `analyzer`, `cameras` and `cables` | `mechanical/generated/config.scad`, the constants every printed part includes, and `boards.scad`, with the plates of the bays that say `plate: boards` |
| `python tools/build.py stl` | the same, through `config.scad`; `rows` and `population` for the list of files | the STL files in `mechanical/stl/` |
| `python tools/build.py web` | the whole file | `site/assets/rack.json` and the models of the 3D model, then the bill of materials |
| [tools/bom.py](../../tools/bom.py) | `rows`, `population`, `drawer.detent`, `drawer.display`, `cables`, `power_box.charger`, the `layers` of `pcb` | `bom/README.md` and `bom/rack-bom.csv`: printed parts, fasteners, cables, PCBs to order |
| [tools/plate_layout.py](../../tools/plate_layout.py) | `population`, `plate_grid`, `drawer`, `pcb.data_port_x6` | where the pegs go, printed, no file written |
| `electronics/<pcb>/design.py` | `pcb` | the PCBs' outlines, holes and connector positions |
| [tools/bayctl.py](../../tools/bayctl.py) | `analyzer` only | the logic analyzer's pinned firmware and USB id |

How to run them, and what each prints: [build.py, plate_layout.py, bom.py](tools.md). The order to follow
after an edit: [Edit config/rack.yaml and regenerate](../plan/choose-your-rack.md#edit-config-rack-yaml-and-regenerate).
The per-installation settings (host names, board targets, access) are in another file:
[lab.yaml](lab-yaml.md).

## frame, rows, bay

```{literalinclude} ../../config/rack.yaml
:language: yaml
:caption: config/rack.yaml
:start-at: "frame:"
:end-before: "drawer:"
```

```{literalinclude} ../../config/rack.yaml
:language: yaml
:caption: config/rack.yaml
:start-at: "rows:"
:end-before: "cameras:"
```

| Key | What it sets |
|---|---|
| `frame.tilt` | the shelves' tilt, front edge lower: 20°. `0` gives flat shelves, which nobody has tried: the slot bin relies on the tilt, and `bay.camera_lens` is a fixed offset worked out for 20° |
| `frame.base_height` | floor to row A: the base ladders, the cell the power box sits in |
| `frame.panel_thickness`, `panel_clearance` | a ladder, and the play of a tray between two: with `bay.width` they make the column pitch, 165.8 mm |
| `rows` | one entry per row, bottom to top. `id` is the row's letter, which is also the hub's output that feeds it; four rows at most, the hub's four outputs |
| `rows[].height` | the row's pitch: 165 for a row of plates, 120 for row C, whose slot bins take boards up to 82 mm tall. 165 at most: a 185 mm row takes a 258.8 mm ladder, too long for a 256 mm bed |
| `rows[].layout` | one `1` per column. Every entry is `1`: a double-width bay (`2`) is not designed |
| `bay.width`, `bay.depth` | the tray, 158 × 210 |
| `bay.carrier` | the tray's floor, walls and plenum, and where the bay node sits in it |
| `bay.camera_mount`, `bay.camera_lens` | the four inserts under every bay's ceiling that a camera pod screws into, and where its lens looks down on the bay below |

What a size changes, and what nobody has tried: [Choose a size and a kind for each bay](../plan/choose-your-rack.md).

## drawer, plate_grid, chain

Most values here are the design; three are yours to measure or to choose.

| Key | What it sets | Yours to change |
|---|---|---|
| `drawer.depth`, `travel`, `wall*`, `front_*`, `flange`, `guide_width`, `clearance` | the drawer, its separate front and the tray's guides | no |
| `drawer.display` | the node's front display on the drawer's front; `seat` (8.6) and `screw` (M2) are assumed | measure the display when it arrives ([Measure before you print](../print/index.md)) |
| `drawer.rear_bay`, `port_mouth`, `port_recess` | the rear bay where the DATA board stands, its port wall, and the recesses under the port wall's slots in the plate | no |
| `drawer.detent` | what holds the closed drawer against the slope: `printed`, a spring tab (no parts, about 3 N), or `magnet`, two 6 × 3 mm magnets glued in (about 10 N), which the bill of materials then lists with the glue | yes |
| `drawer.plate`, `plate_gap` | the plate's thickness and its gaps to the drawer's walls | no |
| `drawer.slot_bin` | the slot bin: its floor, front stop and dividers; six lanes of 21.0 mm. A board up to 19.8 mm thick in all, 86.5 long and 82 tall | no |
| `plate_grid` | the honeycomb: 10 mm pitch, 7.2 mm holes, the stop's eccentricity (3.55) and the cam's spiral | no |
| `chain` | the drag chain's outer size, bend radius, end pieces, and where it runs in the tray | measure `outer`, `radius`, `end_holes`, `end_length` ([Enter your measurements](../print/index.md#enter-your-measurements)) |

```{literalinclude} ../../config/rack.yaml
:language: yaml
:caption: config/rack.yaml › drawer
:start-at: "  detent: printed"
:end-before: "  plate: 5.0"
```

Two comments in this section of the file are out of date. The port wall does not have "the DATA ×4's four
U's": it has six identical standing slots, one per port of a DATA ×6, and a DATA ×4 stands behind slots 2 to 5.
The single DATA port board it names was retired from the rack on 2026-10-31.

(population-one-entry-per-bay)=
## population

The file calls its `population` an example, "used by the docs, the BOM roll-up and the 3D viewer". Each key is
a bay; a bay left out is empty.

```{literalinclude} ../../config/rack.yaml
:language: yaml
:caption: config/rack.yaml › population
:start-at: "population:"
:end-before: "  A4:"
```

```{literalinclude} ../../config/rack.yaml
:language: yaml
:caption: config/rack.yaml › population › C4
:start-at: "  C4:"
:end-before: "# A sub-slot's board"
```

| Key | Values | What it does |
|---|---|---|
| `board` | an id of the [board library](board-library.md) | one board in the bay |
| `boards` | a list of up to four boards, or six with `plate: slots`; each item takes `board`, `cable`, `slot`, `at`, `orient`, `role` | several boards in the bay: on a plate with a DATA ×4, or on edge in a slot bin with a DATA ×6. `board` and `boards` exclude each other |
| `cable` | an id of `cables` | the board's cable to its DATA port |
| `slot` | 1 to 4 on a DATA ×4, 1 to 6 in a slot bin | the port the board is on, and in a slot bin its lane; without it, the board's rank in the list |
| `at` | `[x, y]`, plate coordinates | where a board's front-left corner goes on a plate of several boards; the layout tool moves it up to 10 mm to reach its pegs. Without it the boards are packed in a row. Not in a slot bin |
| `orient` | `rear` (the default) or `side` | a board's USB towards the port wall, or towards the drawer's right wall. Not in a slot bin |
| `role` | `analyzer` | the board is the bay's logic analyzer, not a board under test: `bayctl` keeps it out of twister's map, the bill adds its Pico 2 and its jumper wires |
| `mount` | `drawer` (the default), `sled`, `fixed` | a drawer on a drag chain; a sled without a chain, with a port block behind it; a sled screwed in place |
| `plate` | `pegs` (the default), `boards`, `slots` | the honeycomb plate and its pegs; the board's own plate (`plate_<board>`, or `plate_bay_<bay>` for several boards); a slot bin |
| `x4` | `v2` or `base` | which assembly of the DATA ×4 the 3D model shows and the bill prices: with its logic, or without. A bay with `boards` and no `x4` is priced as `base` |
| `jumpers` | per port, header pin: board pin | the Dupont wires the 3D model draws and the bill counts |
| `open` | `true` | the 3D model shows the drawer pulled out |
| `pc_cable` | `true` | the 3D model draws a laptop on the bay's front port |

A bay with `boards` and no `plate: slots` is counted with a DATA ×4, every other bay with a DATA ×6. The
build stops on an entry it cannot use, with a message such as `B3: two boards on slot 2` or
`` B1: `board` and `boards` both set: one or the other ``. For a plain rack, with no board in any bay, write
`population: {}`: a bare `population:` is read as nothing at all, which the tools do not accept.

The layout tool, the bill of materials and the 3D model read this section; the bay node and `bayctl` do not.
The bay learns a board's Zephyr target from its page or from `lab.yaml`
([Board targets](../use/board-targets.md)). How a board goes in, step by step:
[Put a board in a bay](../use/mount-a-board.md).

The comment above `population` in the file says that the boards of a bay with a DATA ×4 "share one plate
(`plate_bay_<id>`, `plate: boards`)". That was the former kind; since the honeycomb plate they are on pegs
like every other bay, unless the entry says `plate: boards`, as the next lines of the same comment say.

## cameras, cables, power_box, standalone

| Key | What it sets |
|---|---|
| `cameras` | the bays the 3D model draws with a camera pod. The bill counts two pods whatever the list holds (`CAMERA_SETS` in `tools/bom.py`), and every bay has the inserts for one |
| `cables` | each cable by id: `label`, as the bill lists it; `a` and `b`, its two ends; `length`; `style`, how the 3D model lays it (`right`, `adapter`, `side`, `straight`). A cable of style `adapter` adds two 90° adapters per board to the bill |
| `cables.data-lead`, `row-jumper`, `row-feed` | a description of the rack's own leads, which no tool reads today. The bill counts the row cables from the size of the rack, and its feeds' lengths are in `tools/bom.py` (`ROW_FEED_CM`) |
| `power_box` | the power box: the base cell it sits in (`column`), its place in it, its size and wall |
| `power_box.charger` | the charger and cable lines of the bill |
| `standalone` | one bay on a desk: the PD trigger module's size (the largest the seller's photos allow: measure the one you buy) and the rubber feet |

```{literalinclude} ../../config/rack.yaml
:language: yaml
:caption: config/rack.yaml › cables
:start-at: "  c-to-c:       {"
:end-before: "  data-lead:"
```

The `data-lead` label still says "node J7 → DATA port board": the lead goes to a DATA ×6 or a DATA ×4.

## pcb

```{literalinclude} ../../config/rack.yaml
:language: yaml
:caption: config/rack.yaml › pcb
:start-at: "  bay_node:"
:end-before: "  power_hub:"
```

`pcb` holds the outline, the holes and the connectors of each of the rack's PCBs, in KiCad coordinates, so that
the printed parts and the PCBs agree: `bay_node`, `power_hub`, `data_port_x4_v2` (the DATA ×4), `data_port_x6`,
`camera_pod`, and two boards that are not ordered: `data_port`, the single-port board kept for the Solo, and
`data_port_x4`, the first DATA ×4, whose values still place the drawer's bosses and the cradle. `solder_mask`
is the colour to order, green.

The five PCBs went to fabrication as v1.0 on 2026-11-11 and that revision is frozen: a change here changes a PCB
too, and `tools/released.py`, which the tool tests run, fails when a released revision's files differ from
what was sent ([Change a PCB](../engineering/change-a-pcb.md)).

## Which key changes what

Every printed part includes the same `mechanical/generated/config.scad`, so `python tools/build.py stl`
renders all of them after any edit, and puts back the committed bytes of the files whose geometry did not
change. Read from `part_jobs()` in [tools/build.py](../../tools/build.py), `scad_config()` in
[tools/rackcfg.py](../../tools/rackcfg.py), the `include` lines of `mechanical/parts/` and `printed()` and
`hardware()` in [tools/bom.py](../../tools/bom.py):

| Key | Printed parts | Counts in the bill |
|---|---|---|
| `frame` | ladders, braces, the tray, the power box | |
| the number of `rows` | a `ladder_<row>` and a `brace_<row>` per row, a label pair per bay | ladders, braces, square nuts, row feeds and jumpers, bay nodes, DATA boards, everything per bay |
| the length of a `layout` | a label pair per bay | the same, by column |
| `rows[].height` | that row's ladder and brace | |
| `bay` | the tray and everything that fits in it; `camera_mount`, `camera_lens`: the tray's inserts and the camera pod | |
| `drawer` | the drawer, its front, the sled and port block, the plate, the slot bin, the cradle and cover | `detent: magnet`: magnets and glue |
| `plate_grid` | the plate and the pegs | the pegs, through the layout |
| `chain` | the tray, the chain's anchor and foot, the printable link | |
| `population` | which plate each bay gets (honeycomb, own plate, slot bin), drawer or sled | pegs, plates, slot bins, sleds, DATA ×6 against DATA ×4, the boards' cables and adapters, Dupont wires, the analyzer |
| `cameras` | | |
| `cables` | | the boards' cables, by label |
| `power_box` | the power box | the charger and its cable |
| `standalone` | the standalone boxes | the standalone section |
| `pcb` | the cradle and strip, the drawer, the tray, the plate and the slot bin (the holes over the node's buttons), the power box, the pod, the standalone boxes | |

`cameras` changes only the 3D model. The PCBs to order follow the rows and `population`:
[Order the PCBs](../plan/order-the-pcbs.md).

## Frames of reference

```{literalinclude} ../../config/rack.yaml
:language: yaml
:caption: config/rack.yaml
:start-at: "# Everything is in millimetres."
:end-at: "one bay's tray."
```

| Frame | Origin and axes | Used by |
|---|---|---|
| Frame | the front-left-bottom corner of the leftmost base ladder; X to the right, Y to the back, Z up | `frame` |
| Row | a row's front-bottom edge, tilted by `frame.tilt`: Y along the slope, Z square to the shelf | `rows` |
| Carrier | a row's frame moved to the front-left corner of one bay's tray | `bay`, `chain` |
| Drawer | the drawer's left side and its front face | `drawer`, `pcb.data_port_x4_v2.x0` and the other DATA boards' |
| Plate | the plate's front-left corner; x to the right, y towards the port wall | `population` › `at`, the layout tool's output |
| KiCad | each PCB's own; on the bay node and the hub, y = 0 is the rear edge | `pcb` |

A board's own outline, holes and USB position in [boards.yaml](board-library.md#the-fields-of-boards-yaml) are
in a fourth frame: the vendor's drawing, from its bottom-left corner.
