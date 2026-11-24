# Choose your rack's size

Your rack can be a single bay or up to four rows of bays, and each bay can hold one board or several. This
page helps you choose. You then describe your rack in [config/rack.yaml](../../config/rack.yaml), and the
tools make the printed parts, the bill of materials and the 3D model to match. You can add bays later.

## Rack sizes

The smallest BitBunk is one bay on a desk: a bay node and a DATA ×4 in a printed box, fed by a USB-C PD
trigger module. It needs no frame, no power hub and no row cable. See
[One bay on a desk](../build/one-bay-on-a-desk.md).

A rack puts bays side by side in a printed frame, in one to four rows. Neighbouring bays share a side wall,
the ladder. Some sizes:

| Columns × rows | Bays | Width × depth × height |
|---|---|---|
| 1 × 1 | 1 | 173 × 225 × 334 mm |
| 2 × 2 | 4 | 339 × 225 × 499 mm |
| 4 × 2 | 8 | 671 × 225 × 499 mm |
| 4 × 3 | 12 | 671 × 225 × 664 mm |
| 4 × 3, the example, with a top row of slot bins | 12 | 671 × 225 × 619 mm |

Computed by `tools/rackcfg.py`. Each column adds 165.8 mm of width, and each row 165 mm of height. A row that
holds only slot bins can be 120 mm high.

## What limits the number of columns

The power hub shares the charger's power between the bays. Each bay of a row gets an equal share, so the
more columns you have, the less each bay gets:

```{include} ../reference/specifications.md
:start-after: <!-- site:bay-share -->
:end-before: <!-- /site:bay-share -->
```

A typical board (a Nucleo, an nRF DK, a Pico) draws 0.2 to 0.7 W. A big one, such as an ESP32-S3 on Wi-Fi
or a board with an LCD, draws 1.5 to 2.5 W. So at four columns, a bay can feed one big board or a few small
ones. A port that does not fit waits until there is room:
[Power budget and queued ports](../use/power-budget.md).

Other limits:

- A rack has four rows at most, because the hub has four row outputs. With four rows of four columns, each
  bay has 3.8 W for its DATA board and your boards.
- A row is 165 mm high at most, so that its ladder fits a 256 mm print bed.
- All bays have the same width: every entry of a row's `layout` is `1`.
- A bigger charger does not help. The hub uses 20 V, so a 140 W charger gives the same as a 100 W one.

A single bay on a desk has no hub to share with. Its bay node keeps it under 25 W.

## Choose what each bay holds

You set each bay in its entry under `population` in `config/rack.yaml`. Every key is on
[rack.yaml](../reference/rack-yaml.md). You can change a bay later: the same tray and drawer take either
DATA board.

| Choice | The default | The other |
|---|---|---|
| DATA board | DATA ×6: six ports, each switched and measured | DATA ×4: four ports, with a pin header beside each for [wires between boards](../use/wires.md), the [logic analyzer](../use/logic-analyzer.md) and the RESET and BOOT lines. The base version of the DATA ×4 has the RESET and BOOT lines only |
| What holds the boards | A honeycomb plate with clip-in pegs, the boards lying flat | A slot bin: up to six boards on edge, one per port of a DATA ×6, no wires. Or a plate made for one board, when pegs cannot hold it |
| How the bay opens | A drawer on a drag chain: the boards stay plugged in while it slides out | A sled, with no chain: unplug the boards, then pull it out |
| Camera | None | A camera pod under the bay's ceiling ([Camera](../use/camera.md)). You can add one to any bay later |

In the file, a bay that lists several boards on its plate (`boards:`) gets a DATA ×4. Every other bay,
including a slot-bin bay, gets a DATA ×6.

A plate holds up to four small boards, so eight small boards need two DATA ×4 bays, or a slot bin and a
second bay. Boards that share a bay also share its power.

Before you choose, check each of your boards:

- It fits. A plate is 134.5 × 159.4 mm. A lane of a slot bin takes a board up to 19.8 mm thick, 86.5 mm
  long and 82 mm tall. See [Board library](../reference/board-library.md).
- Its USB works over the network: [USB/IP and flashing](../use/usb-and-flashing.md).
- It draws less than its share of the bay's power (above).
- It has no battery: [Put a board in a bay](../use/mount-a-board.md).

Use 165 mm rows for bays with a plate, because the USB cable of a board on a plate arches up to about
105 mm. Use the 120 mm row for slot bins only.

## The example rack

`config/rack.yaml` comes with an example: a 4 × 3 rack with a bay of every kind. The 3D model and the pages
of this site use it.

| | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| **C** | slot bin, 6 boards | slot bin, 4 boards | slot bin, 5 boards | slot bin, 3 boards |
| **B** | DATA ×4 base, 2 boards | a GIGA R1 on its own plate, a camera | DATA ×4, 4 boards and wires | a UNO R4, a laptop on the front port |
| **A** | a NUCLEO-64 | a NUCLEO-144 | a BeaglePlay, on a sled | a Wio Terminal |

For a plain rack, write `population: {}`. Every bay then gets a drawer, a honeycomb plate and a DATA ×6, for
one board each. A plain rack needs only three kinds of PCB: the bay node, the DATA ×6 and the power hub.

## Edit config/rack.yaml and regenerate

A plain rack of one or two 165 mm rows and up to four columns prints from the STL files as they are. Only a
drag chain of another size makes you rebuild the trays
([Parts to measure before you print](../print/index.md#parts-to-measure-before-you-print)).
[Parts to print](../print/parts-list.md) and [Order the PCBs](order-the-pcbs.md) give the counts. Edit
`config/rack.yaml` when you want a bay that is not plain, or the 3D model and the bill of materials of your
own rack.

You need a git checkout of the repository, and OpenSCAD or Docker:
[Install the tools](../reference/tools.md). Install the Python packages in a virtual environment, at the top of
the repository:

```console
$ python3 -m venv .venv
$ . .venv/bin/activate
$ pip install -r tools/requirements.txt
```

1. Set the rows. Each entry of `rows` is a row, from the bottom up. Each `1` in its `layout` is a column.
   For a 2 × 2 rack:

   ```{code-block} yaml
   :caption: config/rack.yaml
   rows:
     - id: A
       height: 165
       layout: [1, 1]
     - id: B
       height: 165
       layout: [1, 1]
   ```

2. Describe what each bay holds under `population`, or write `population: {}` for a plain rack. List the
   bays that get a camera under `cameras`. Every key is on [rack.yaml](../reference/rack-yaml.md).

   If a bay has a slot bin or a camera, keep `frame.tilt` at 20. A slot bin needs the slope to slide its
   boards to the front, and the camera is placed for 20°.

3. Find where the pegs go on each plate:

   ```console
   $ python tools/plate_layout.py
   ```

   A `note:` after a bay's lines warns you when a board leans on the drawer or is not fully held
   ([Put a board in a bay](../use/mount-a-board.md)).

4. Regenerate everything:

   ```console
   $ python tools/build.py all
   ```

   It renders the STL files into `mechanical/stl/` and rebuilds the 3D model and the bill of materials. If
   OpenSCAD cannot make a part, the tool prints `FAIL` with OpenSCAD's message. To see which STL files
   changed: [Get the STL files](../print/stl-files.md).

5. Check your rack in the 3D model. Serve it, then open <http://localhost:8000>:

   ```console
   $ python -m http.server -d site 8000
   ```

6. Read the counts of printed parts, screws and cables in `bom/README.md`. Count the PCBs on
   [Order the PCBs](order-the-pcbs.md#how-many-of-each).

## Add bays later

You can add a column or a row to a rack you have built. A new column shares the ladder of the last one. A new
row plugs into a free output of the hub with a row feed of its own: the hub has all four outputs fitted. Each
column you add lowers the power share of every bay. To add a bay to a rack that is running, see
[Add a column or a row](../build/add-a-bay.md).
