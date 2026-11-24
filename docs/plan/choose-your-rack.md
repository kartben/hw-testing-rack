# Choose a size and a kind for each bay

A rack is one to four rows of bays, and each bay is of one kind: one board on a plate, up to four on a plate
with wires between them, or up to six on edge in a slot bin. [config/rack.yaml](../../config/rack.yaml) holds
that choice, and the printed parts, the PCBs and the cables are counted from it.

:::{status} designed
The CAD and slicer checks were made on the parts of the default rack, four columns by three rows, with the
example's boards; the slicer figures, of 2026-10-21, predate several of those parts. Nothing has been printed
and no rack of any size has been built. The counts for other sizes on this page are computed by the code that
writes the bill of materials. [What exists today](status.md#the-printed-frame).
:::

## Three tests for your boards

| Test | What the rack offers | Check your board on |
|---|---|---|
| It fits a bay | a plate of 134.5 × 159.4 mm, or a lane of a slot bin for a board up to 19.8 mm thick, 86.5 mm long and 82 mm tall | [What fits in a bay](../reference/board-library.md#what-fits-in-a-bay) |
| Its USB passes | every board's USB goes over the network at full speed, 12 Mbit/s shared by the bay; a few kinds of device do not pass | [Which probes and devices work](../use/usb-and-flashing.md#which-probes-and-devices-work) |
| A bay can feed it | 5 V and about 0.5 A a port, within about 5.4 W for the whole bay at four columns | [What a bay's share of the charger buys](#what-a-bays-share-of-the-charger-buys) |

A board with a battery stays out of the rack
([No battery on a board in the rack](../use/mount-a-board.md#no-battery-on-a-board-in-the-rack)).

## One bay on a desk, 2 × 2, or 4 × 3

The smallest BitBunk is one bay on a desk: a bay node and a DATA ×4 in a printed box, fed by a USB-C PD
trigger module in place of the power hub, with no frame and no row cable
([One bay on a desk](../build/one-bay-on-a-desk.md)).

A rack is that bay repeated in a printed frame. Its side walls, the ladders, stand between the columns and are
shared by both neighbours, so the frame grows by a column or by a row.

| Rack | Bays | Width × depth × height |
|---|---|---|
| 2 × 2 | 4 | 339 × 225 × 499 mm |
| 4 × 2 | 8 | 671 × 225 × 499 mm |
| 4 × 3, the default | 12 | 671 × 225 × 619 mm |

Columns × rows, computed by `tools/rackcfg.py` from the rows of `config/rack.yaml`: a column is 165.8 mm wide,
rows A and B are 165 mm high and row C, the row of slot bins, 120 mm. The shelves are tilted by 20°, front
edge lower, and the rack is screwed to the bench whatever its size
([Screw the rack to the bench](../build/screw-the-rack-to-the-bench.md)).

A rack can start small and grow: a column added beside the last one shares its ladder, and the hub has its
four row outputs fitted from the start. A column more lowers the power share of every bay already in its row
([below](#what-a-bays-share-of-the-charger-buys)). Adding a bay to a rack that runs:
[Add a bay, then a row](../build/add-a-bay.md#on-a-rack-that-is-already-running).

## A plain rack, and the example rack

`config/rack.yaml` calls its `population` an example, "used by the docs, the BOM roll-up and the 3D viewer". It
puts a bay of every kind in one rack:

```{figure} ../img/viewer/rack.jpg
:alt: The twelve bays of the example rack, each with its label, three drawers pulled out

The 3D model of the example rack. Three drawers are pulled out: B1 and B3, each with a DATA ×4 standing at
its back, and C2, a slot bin. The laptop is on B4's front port.
```

| | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| **C** | slot bin, 6 boards | slot bin, 4 boards | slot bin, 5 boards | slot bin, 3 boards |
| **B** | DATA ×4, base: 2 boards and a RESET wire | a GIGA R1 with its display on its own plate, under the camera | DATA ×4 with its logic: 3 boards, wires, and a Pico 2 as a stand-alone analyzer | an UNO R4, a laptop on the front port |
| **A** | a NUCLEO-64 | a NUCLEO-144 | a BeaglePlay on a sled, no drag chain | a Wio Terminal |

A plain rack is what the same file gives with an empty `population`: every bay a drawer on a drag chain with a
honeycomb plate and a DATA ×6, one board to a bay. Nobody has written that file out; the right-hand column
below comes from running the bill's own functions on it.

| For 4 × 3 | The example | A plain rack |
|---|---|---|
| Kinds of PCB to order | 5 | 3: bay node, power hub, DATA ×6 |
| DATA ×6, DATA ×4 | 10, 2 | 12, 0 |
| Soldered by hand ([Solder the connectors](../build/solder-the-connectors.md)) | the lead's socket on each DATA ×6; the same socket and the pin headers on each DATA ×4 | the lead's socket on each DATA ×6 |
| Drawers on a chain, sleds | 11, 1 | 12, 0 |
| Honeycomb plates, slot bins, own plates | 7, 4, 1 | 12, 0, 0 |
| Cameras | 1, over B2 | 0 |
| Printed parts, cameras left out | 239, of which 68 pegs | 172, and the pegs of your boards |
| Boards it holds | 29, and an analyzer | 12, one a bay |

Computed with `printed()` and `electronics()` of [tools/bom.py](../../tools/bom.py). The bill counts two camera
sets whatever `cameras` lists (a constant, `CAMERA_SETS`): its count of printed parts is four higher than this
table's, 243 for the example, and it lists two camera pod PCBs even for a plain rack.

The pages of Build are written for the example and say which sections a plain rack skips.

## DATA ×6 or DATA ×4, a slot bin, a camera

Each choice is made bay by bay, in the bay's entry of `population`
([rack.yaml](../reference/rack-yaml.md#population-one-entry-per-bay)), and a bay converts later: one tray, one
drawer and one cradle take either DATA board.

| Choice | The default | The other |
|---|---|---|
| DATA board | DATA ×6: six ports, each switched and metered. No pin header: no wires between boards, no logic analyzer, no RESET or BOOT line | DATA ×4: four ports and a pin header beside each, for [wires between boards](../use/wires.md), the bay's [logic analyzer](../use/logic-analyzer.md) and [RESET and BOOT](../use/power-and-reset.md). Its base assembly keeps RESET and BOOT only |
| What holds the boards | a honeycomb plate and clip-in pegs, the boards lying flat | a slot bin: up to six boards on edge, one per port of a DATA ×6, no wires. Or a board's own plate, when pegs cannot hold it |
| How the bay opens | a drawer on a drag chain: the board stays plugged while it slides out | a sled, without a chain: unplug the board's cable, then pull |
| Camera | none | a pod under the bay's ceiling ([Camera](../use/camera.md)); any bay can take one later |

In the file, a bay that lists several boards on a plate (`boards:`) gets a DATA ×4, every other bay a DATA ×6.
Which feature needs which DATA board, and how far each has been tested:
[What a bay can do](../use/index.md#with-a-data-6-with-a-data-4).

Eight small boards are two bays, not eight: four on the plate of each of two DATA ×4 bays, as B3 holds two
XIAOs and two Pico 2s (one of them a stand-alone analyzer), or six on edge in one slot bin and two more in a
second bay. Four on a plate is the most, and B1 holds two: beside its Pico 2 and its Nano Matter, a third board leaves no
room for its pegs' cams. Which boards fit a lane of a slot bin is the fit table of the
[board library](../reference/board-library.md#how-each-is-held). Boards that share a bay also share its power.

## What a bay's share of the charger buys

The hub grants each bay an equal share of its row's 1.6 A, less a 10 % margin, at the charger's 20 V, less the
1.8 W the bay node draws itself. The grant is for the bay's DATA lead: the DATA board and its boards.

```{include} ../reference/specifications.md
:start-after: <!-- site:bay-share -->
:end-before: <!-- /site:bay-share -->
```

Up to three rows, a bay's share follows the width of the rack alone. A fourth row of four lowers it to 3.8 W
a bay ([The largest rack](../reference/specifications.md#the-largest-rack)). The 140 W, 28 V charger would
raise every figure, and the default firmware locks it out
([Chargers and what each feeds](../reference/specifications.md#chargers-and-what-each-feeds)).

The DATA board's own draw comes out of the grant first. At four columns, on design estimates:

| In the bay | Grant | The DATA board takes | Left for the boards, at 5 V |
|---|---|---|---|
| DATA ×6 | 5.4 W | 2.1 to 2.6 W | 0.49 to 0.58 A between its six ports |
| DATA ×4 | 5.4 W | 2.3 to 3.0 W | 0.42 to 0.55 A between its four ports |
| Either, under a camera | 2.9 W | the same | 0.11 to 0.14 A with the DATA board at its lowest; at its highest, 0.05 A on a DATA ×6 and nothing on a DATA ×4 |

The draws are those of [power.md](../power.md#budget) and
[One node, several boards](../multi-dut-node.md#power-budget). The DATA ×6's line and the camera's are worked
out here the way the second note works the DATA ×4's: the watts left, through the DATA board's converters at
88 %, divided by 5 V. Nothing has been measured.

A typical board (a Nucleo, an nRF DK, a FRDM, a Pico) draws 0.2 to 0.7 W, 40 to 140 mA, and a big one (an
F746G-DISCO with its LCD, an ESP32-S3 on Wi-Fi) 1.5 to 2.5 W. A bay of a four-column rack feeds one hungry
board or a few light ones. Six boards in a slot bin can ask for more than their bay's share: the ports that
find no room wait their turn ([Power budget and queued ports](../use/power-budget.md)). A bay on a desk has no
hub and no grant: its node keeps it under 25 W.

## PCBs, cables and parts for a size

```{include} order-the-pcbs.md
:start-after: <!-- site:pcbs-per-size -->
:end-before: <!-- /site:pcbs-per-size -->
```

The frame and the cables, for plain racks:

| | 2 × 2 | 4 × 2 | 4 × 3 |
|---|---|---|---|
| Ladders: base, one per row, cap | 12 | 20 | 25 |
| Rear braces | 6 | 12 | 16 |
| Floor plates, cap plates | 2, 2 | 4, 4 | 4, 4 |
| Trays, each with its drawer, front, plate, cradle and strip | 4 | 8 | 12 |
| Row jumpers, bay to bay | 2 | 6 | 9 |
| Row feeds, power box to a row | 2 | 2 | 3 |
| DATA leads | 4 | 8 | 12 |
| Printed parts, cameras left out | 65 | 123 | 172 |

Computed with `printed()` and `hardware()` of `tools/bom.py` for racks of rows A and B, then A to C, with an
empty `population`. The rule behind it, read from the same functions:

| One more | Printed | PCBs | Cables |
|---|---|---|---|
| Column | a ladder and a brace per level (the base and each row), a cap strip, a floor plate, a cap plate, and a bay per row | | |
| Row | a ladder per column and one more, a brace and a bay per column; its ladder and its brace are STL files of their own, `ladder_<row>` and `brace_<row>` | | a feed |
| Bay | a tray, a drawer with its chain anchor and foot (or a sled and a port block), a front, a cradle and its strip, a plate or a slot bin, a label | a bay node, a DATA board | a DATA lead, and a jumper to its neighbour |
| Rack | the power box | a power hub | the charger and its cable |

The parts for each size, with their files and filament, are on [Parts and quantities](../print/parts-list.md);
what to buy is on the [shopping list](shopping-list.md).

The frame stops at four rows, because the hub has four row outputs, and at rows 165 mm high: a 185 mm row
makes a 258.8 mm ladder, longer than a 256 mm bed. A double-width bay is not designed, so every entry of a row's
`layout` is `1` ([The largest rack](../reference/specifications.md#the-largest-rack)).

Row C's 120 mm are sized for slot bins: 85 mm from the bin's floor to the ceiling. In the 165 mm rows the
cable of a board on a plate arches up to about 105 mm, and no source says what a plate bay holds in a 120 mm
row. With `height: 165` on row C as on the two others, the rack is 664 mm high.

## Edit config/rack.yaml and regenerate

The tools need a git checkout, Python with the packages of `tools/requirements.txt`, and OpenSCAD or Docker:
[Get a checkout and install what they need](../reference/tools.md#get-a-checkout-and-install-what-they-need).

1. Set the rows. Each entry of `rows` is a row, bottom to top; each `1` of its `layout` is a column.

   ```{literalinclude} ../../config/rack.yaml
   :language: yaml
   :caption: config/rack.yaml
   :start-at: "rows:"
   :end-before: "cameras:"
   ```

2. Rewrite `population` for the bays that are left, or write `population: {}` for a plain rack, and list in
   `cameras` the bays that get a pod. Every key: [rack.yaml](../reference/rack-yaml.md).

3. Ask where the pegs of each bay go. A `note:` at the end of a bay's lines says when a board leans on the
   drawer or is not fully held ([Put a board in a bay](../use/mount-a-board.md)).

   ```console
   $ python tools/plate_layout.py
   ```

4. Regenerate.

   ```console
   $ python tools/build.py all
   ```

   It rewrites the constants of the printed parts (`mechanical/generated/`), renders every STL file into
   `mechanical/stl/`, rebuilds the files of the 3D model under `site/assets/` and the bill of materials under
   `bom/`. `python tools/build.py stl` stops after the STL files; `web` does the same as `all` today. A part
   that OpenSCAD refuses (a drag chain that does not fit, for one) prints `FAIL` with its message and writes
   no file ([build.py](../reference/tools.md#build-py)). Which STL files changed and how to print them:
   [Get the STL files](../print/stl-files.md).

5. Serve the 3D model and open `http://localhost:8000` to look at the rack you described:

   ```console
   $ python -m http.server -d site 8000
   ```

6. Read the counts of printed parts, fasteners and cables in `bom/README.md`. Its Electronics lines follow the
   JLCPCB quotes on record, not your size; when the two differ, step 4 prints, for a 2 × 2 rack:

   ```text
   warning: the JLC quote assembles 10 × bay-node but the configuration needs 4: re-quote
   ```

   The PCBs to order are those of the table above ([Order the PCBs](order-the-pcbs.md)).

## What nobody has tried

`config/rack.yaml` or the code allows each of these, and no source records a run:

- Flat shelves. `frame.tilt: 0` "gives flat shelves", says the file. The slot bin relies on the tilt to slide
  its boards to the front stop, and the camera's place over the bay below (`bay.camera_lens`) is a fixed
  offset worked out for 20°.
- Rows of different lengths. The frame's parts are counted for the longest row.
- A plate bay in the 120 mm row.
- A fourth row of four, or a fifth column: the first leaves a bay 3.8 W and the second 4.0 W, where a DATA
  board alone takes 2.1 to 3.0 W.
- `build.py` outside a git checkout: its last step calls git.

If you try one, [report what you find](../reference/known-limitations.md#report-a-finding).
