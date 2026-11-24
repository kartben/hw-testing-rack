---
myst:
  substitutions:
    clone: |
      ```console
      $ git clone REPO_URL
      $ cd REPO_DIR
      $ pip install -r tools/requirements.txt
      ```
---

# Build scripts

Three scripts regenerate the rack's files from [`config/rack.yaml`](rack-yaml.md): `build.py`,
`plate_layout.py` and `bom.py`. Run them from the root of a checkout after you change the size or the layout
of your rack.

| Script | Reads | Writes |
|---|---|---|
| [tools/build.py](../../tools/build.py) | `config/rack.yaml`, the [board library](board-library.md), the OpenSCAD sources under `mechanical/` | `mechanical/generated/*.scad`, then the STL files in `mechanical/stl/`. With `web` or `all`, also the 3D model's files and the bill of materials |
| [tools/plate_layout.py](../../tools/plate_layout.py) | `population` and `plate_grid` in `config/rack.yaml`, the board library | nothing: it prints each bay's pegs |
| [tools/bom.py](../../tools/bom.py) | `config/rack.yaml`, each PCB's `electronics/<pcb>/<pcb>-bom.csv`, the volume of each STL file | `bom/rack-bom.csv`, `bom/README.md`, `bom/jlc-parts.md`, `site/assets/bom.json` |

## Install what the scripts need

{{ clone | replace("REPO_URL", repo_url) | replace("REPO_DIR", repo_url.split("/")[-1]) }}

Use a git clone. `build.py` calls git at its last step, so it fails in a folder unpacked from a zip.

| You need | For |
|---|---|
| Python 3.10 or later | all three |
| The packages of [tools/requirements.txt](../../tools/requirements.txt) | all three. `plate_layout.py` needs only PyYAML. The two packages marked optional are for the 3D model |
| OpenSCAD on the `PATH` (`openscad` or `openscad-nightly`), or Docker | `build.py`. Without a local OpenSCAD, it runs the Docker image `openscad/openscad:latest`. On Windows it also looks in `C:\Program Files\OpenSCAD\` |
| The font Liberation Sans Bold | `build.py`: the bay labels and the power box's lettering use it. On Debian and Ubuntu it is the package `fonts-liberation` |
| git | `build.py`, for its last step |

## build.py

```{tool-help} tools/build.py
```

| Target | What it does |
|---|---|
| `config` | writes `mechanical/generated/config.scad` and `boards.scad` from `config/rack.yaml` and the board library. Every other target starts with it |
| `stl` | renders every printable part into `mechanical/stl/`, up to eight OpenSCAD processes at a time |
| `web` | `stl`, then the 3D model's files under `site/assets/`, then `bom.py` |
| `all` | the same as `web` |

Which STL files you get depends on your configuration. For example, there is one `ladder_<row>` per row, and
one stop and one cam base for each standoff height in the board library.

To render some parts only, list them after `--only`, without `.stl`. A name that matches no part renders
nothing, and `build.py` does not warn you.

```console
$ python tools/build.py stl --only tray chain_anchor chain_foot
```

Set `RACK_OPENSCAD_DOCKER` to any value to use the Docker image even when OpenSCAD is installed.

`build.py` prints one line per part:

| Line | Means |
|---|---|
| `ok   tray` | the file was written. Any OpenSCAD line that holds `WARNING` follows, indented |
| `FAIL tray` | OpenSCAD stopped or wrote no file. The end of its messages follows, for instance a failed check of the sources: `chain: the U bend reaches the tray's rear wall` |
| `config/rack.yaml › population › B3: …` | a bay with `plate: boards` and several boards has a layout that does not fit. Nothing is rendered |

The exit status is 1 when a part failed.

After a rebuild, `git status mechanical/stl` lists only the parts your change altered. The last step restores
every STL file whose shape did not change. [Get the STL files](../print/stl-files.md) says when to rebuild.

## plate_layout.py

Prints where the pegs go in each bay whose boards sit on the honeycomb plate (`plate: pegs`, the default).
It covers every bay, or only the bays you name. It writes no file.

```console
$ python tools/plate_layout.py B3
B3:
  B3.1 xiao: front-left corner at (8.6, 29.1), 0.9 mm from its hint
    row  3, hole  2: stop H6, arrow at 8:30, F edge
    row  4, hole  1: stop H6, arrow at 6:30, L edge
    row  5, hole  3: cam on base H6, R edge
  B3.2 rpi-pico2: front-left corner at (43.5, 15.9), 1.8 mm from its hint
    row  1, hole  5: cam on base H9, F edge
    row  7, hole  6: pin d1.8 H9, arrow at 10:30
  B3.3 rpi-pico2: front-left corner at (74.5, 23.0), 7.0 mm from its hint
    row  2, hole  9: cam on base H9, F edge
    row  8, hole  9: pin d1.8 H9, arrow at 2:30
  B3.4 xiao: front-left corner at (105.5, 31.0), 2.4 mm from its hint
    row  3, hole 11: stop H6, arrow at 2:30, F edge
    row  4, hole 13: cam on base H6, R edge
    row  5, hole 10: stop H6, arrow at 12:30, L edge
  note: B3.1: no cam on its B edge
  note: B3.2: one cam only
  note: B3.3: one cam only
  note: B3.4: no cam on its B edge
```

| In the output | Means |
|---|---|
| `front-left corner at (8.6, 29.1)` | where the board sits, in millimetres from the plate's front-left corner: x to the right, y towards the port wall |
| `0.9 mm from its hint` | how far the tool moved the board from its usual place so that the pegs fall on holes. The usual place is centred with the USB towards the port wall, or the bay's `at`. The tool moves it up to 10 mm, or 30 mm along its USB edge when it is alone in the bay |
| `row 3` | the row of holes, row 1 at the front. The plate's rims carry the numbers of the odd rows |
| `hole 2` | the place in that row, counted from the left. The count includes the places left without a hole: beside a locating pin, a finger slot, a RESET or BOOT pin hole, a port's recess |
| `stop H6` | a stop for a 6 mm standoff: `peg_stop_h6.stl` |
| `cam on base H6` | `peg_base_h6.stl` with a `peg_cam.stl` on it |
| `pin d1.8 H9` | a 1.8 mm pin for a 2.1 mm hole, for a 9 mm standoff: `peg_pin_d21_h9.stl`, named for the hole |
| `arrow at 8:30` | how to turn a stop or a pin in its hole: the hour its flange's arrow points to, seen from above, with 12 o'clock towards the port wall. There are six turns: 12:30, 2:30, 4:30, 6:30, 8:30, 10:30 |
| `F edge` | the edge of the board the peg holds: `L` left, `R` right, `F` front, `B` back (the port wall's side) |
| `bobbin: row 16, hole 13` | the post for the cable's spare length, only in a bay with one board |
| `note: … against the drawer's left wall` (or `right wall`, `front panel`) | the board leans on the drawer on that side and takes no stops there |
| `note: … no cam on its B edge`, `one cam only` | a layout the tool accepts, though it is weaker than a full one |
| `note: … held along one axis by friction only` | nothing clamps the board along one axis |
| `note: … no peg fits: placed at its hint, unheld` | no layout works: the bay needs another way to hold that board |

What to do with a layout, and with a board the pegs cannot hold:
[Put a board in a bay](../use/mount-a-board.md) and [A board that is not in the library](../use/add-a-board.md).

## bom.py

`bom.py` counts the parts of the rack described in `config/rack.yaml` and rewrites its four output files.
The counts and prices follow the size of your rack, except the PCB lines
([Get the bill for your rack](bill-of-materials.md#get-the-bill-for-your-rack)).

```console
$ python tools/bom.py
```

It prints the number of lines, the total price and the total of each category. A line that starts with
`warning:` is about the PCB lines.

All prices are estimates. The mass of a printed part assumes that PETG fills 55 % of its volume. `bom.py`
rewrites its output files whole, so do not edit them by hand. [Bill of materials](bill-of-materials.md)
lists the lines.

## Generated files

| File | Written by |
|---|---|
| `mechanical/generated/config.scad`, `boards.scad` | `build.py`, any target. Their first line says not to edit them |
| `mechanical/stl/*.stl` | `build.py stl`, in print orientation |
| `site/assets/rack.json`, `parts.glb` | `build.py web` |
| `bom/rack-bom.csv`, `bom/README.md`, `bom/jlc-parts.md`, `site/assets/bom.json` | `bom.py`, and `build.py web` through it |

These files are all in the repository. After you change `config/rack.yaml`, run
`python tools/build.py web` and commit the regenerated files with it.
