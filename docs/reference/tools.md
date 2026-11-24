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

# build.py, plate_layout.py, bom.py

Three scripts under `tools/` regenerate what follows from [`config/rack.yaml`](rack-yaml.md): `build.py` the
STL files, `plate_layout.py` the place of every peg, `bom.py` the bill of materials. Each is run from the
root of a checkout.

| Tool | Reads | Writes |
|---|---|---|
| [tools/build.py](../../tools/build.py) | `config/rack.yaml`, the [board library](board-library.md), the OpenSCAD sources under `mechanical/` | `mechanical/generated/*.scad`, then `mechanical/stl/*.stl`; with `web` or `all`, the 3D model's files and the bill of materials as well |
| [tools/plate_layout.py](../../tools/plate_layout.py) | `config/rack.yaml` › `population` and `plate_grid`, the board library | nothing: it prints each bay's pegs |
| [tools/bom.py](../../tools/bom.py) | `config/rack.yaml`, each PCB's `electronics/<pcb>/<pcb>-bom.csv`, the volume of each STL file | `bom/rack-bom.csv`, `bom/README.md`, `bom/jlc-parts.md`, `site/assets/bom.json` |

`bayctl`, which drives a rack, has [its own page](bayctl.md) and needs less than these three:
[Set up bayctl and usbip](../use/set-up-your-machine.md).

## Get a checkout and install what they need

{{ clone | replace("REPO_URL", repo_url) | replace("REPO_DIR", repo_url.split("/")[-1]) }}

Clone the repository; do not unpack a zip of it. `build.py` ends by calling git, and fails at that last step
outside a git checkout.

| Needs | For | Notes |
|---|---|---|
| Python 3.10 or later | all three | CI runs on 3.12: `build.py stl` in the hardware workflow, `bom.py` in the site's build, `plate_layout.py` through the tool tests |
| The packages of [tools/requirements.txt](../../tools/requirements.txt) | all three | seven packages, and two marked optional that only the 3D model and the renders use. `plate_layout.py` alone imports nothing but PyYAML |
| OpenSCAD on the `PATH` (`openscad` or `openscad-nightly`), or Docker | `build.py` | without a local OpenSCAD, `build.py` runs the image `openscad/openscad:latest` |
| The font Liberation Sans Bold | `build.py` | the bay labels and the power box's lettering are set in it; CI installs the package `fonts-liberation` |
| git | `build.py` | its last step |

No source names an OpenSCAD version. The one run on record is CI's, `build.py stl` on every push
([.github/workflows/hardware.yml](../../.github/workflows/hardware.yml)): Ubuntu 24.04, its `openscad`
package, Python 3.12. The Docker route takes whatever `openscad/openscad:latest` is on the day. `build.py`
also looks for OpenSCAD under `C:\Program Files\OpenSCAD\`, but nothing records a run on Windows or on
macOS.

## build.py

```{tool-help} tools/build.py
```

| Target | Does |
|---|---|
| `config` | writes `mechanical/generated/config.scad` and `boards.scad` from `config/rack.yaml` and the board library. Every other target starts with it |
| `stl` | renders every printable part into `mechanical/stl/`, up to eight OpenSCAD processes at a time |
| `web` | `stl`, then the 3D model's files under `site/assets/`, then `bom.py` |
| `all` | the same as `web`: the code makes no difference between the two |

Which STL files exist follows the configuration: one `ladder_<row>` and one `brace_<row>` per row, two label
files per bay, one stop and one cam base per `standoff` height of the board library, a pin per hole
diameter and height, and a `plate_<board>` or `plate_bay_<bay>` for each bay that says `plate: boards`.

`--only` takes the names of the parts to render, without `.stl`, after the target:

```console
$ python tools/build.py stl --only tray chain_anchor chain_foot
```

A name that matches no part renders nothing and reports nothing.

The environment variable `RACK_OPENSCAD_DOCKER`, set to any non-empty value, makes `build.py` use the Docker image
even when OpenSCAD is installed.

`build.py` prints one line for the configuration (`wrote … config.scad and boards.scad`), then one line a
part:

| Line | Means |
|---|---|
| `ok   tray` | the file was written. Any line of OpenSCAD that holds `WARNING` follows it, indented |
| `FAIL tray` | OpenSCAD stopped or wrote no file. The end of its messages follows: an `assert` of the sources shows there, for instance `chain: the U bend reaches the tray's rear wall` |
| `config/rack.yaml › population › B3: …` | a bay with `plate: boards` and several boards has a layout that does not fit; nothing is rendered |

The exit status is 1 when a part failed.

The last step, [tools/keep_unchanged.py](../../tools/keep_unchanged.py), puts back the committed bytes of
every STL file whose triangles did not change: OpenSCAD orders them differently from run to run. After a
rebuild, `git status mechanical/stl` therefore lists the parts your change altered, and those only.

When to rebuild the STL files, and how to rebuild one part by hand:
[Get the STL files](../print/stl-files.md). The whole sequence after a change of size or layout:
[Choose a size, change the layout](../plan/choose-your-rack.md).

## plate_layout.py

```console
$ python tools/plate_layout.py
$ python tools/plate_layout.py B3 A1
```

Without an argument it goes through every bay of `config/rack.yaml` › `population`; with bay names, through
those. It takes no option. It prints the bays that hold boards on the honeycomb plate
(`plate: pegs`, the default) and is silent about the others: a bay with `plate: boards` or `plate: slots`,
an empty bay, a name that is no bay. It writes no file; `build.py` and `bom.py` call the same code for the
peg files and their counts.

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

How to read it, worked out from `describe()` and `clock()` in `tools/plate_layout.py`; nobody has placed a
peg from this output yet:

| In the output | Means |
|---|---|
| `front-left corner at (8.6, 29.1)` | where the board sits, in millimetres from the plate's front-left corner: x to the right, y towards the port wall |
| `0.9 mm from its hint` | how far the tool moved the board from its usual place (centred, USB towards the port wall, or the bay's `at`) so that the pegs fall on holes: up to 10 mm, 30 mm along its USB edge when it is alone in the bay |
| `row 3` | the row of holes, row 1 at the front; the plate's rims carry the numbers of the odd rows |
| `hole 2` | the place in that row, counted from the left. It counts the places of the grid, the ones left without a hole included (beside a locating pin, a finger slot, a RESET or BOOT pin hole, a port's recess) |
| `stop H6` | a stop for a 6 mm standoff: `peg_stop_h6.stl` |
| `cam on base H6` | `peg_base_h6.stl` with a `peg_cam.stl` on it |
| `pin d1.8 H9` | a pin of 1.8 mm for a 2.1 mm hole (the hole less 0.3 mm), for a 9 mm standoff: `peg_pin_d21_h9.stl`, named for the hole |
| `arrow at 8:30` | the turn of a stop or a pin in its hole: the hour its flange's arrow points to, seen from above, 12 o'clock towards the port wall. Six turns: 12:30, 2:30, 4:30, 6:30, 8:30, 10:30 |
| `F edge` | the edge of the board the peg holds: `L` left, `R` right, `F` front, `B` back, the port wall's side |
| `bobbin: row 16, hole 13` | the post for the cable's spare length; only in a bay with one board |
| `note: … against the drawer's left wall` (or `right wall`, `front panel`) | the board leans on the drawer on that side and takes no stops there |
| `note: … no cam on its B edge`, `one cam only` | a layout the tool accepts and ranks below a full one |
| `note: … held along one axis by friction only` | nothing clamps the board along one axis |
| `note: … no peg fits: placed at its hint, unheld` | no layout: the bay needs another way to hold that board |

What to do with a layout, and with a board the pegs cannot hold: [Put a board in a bay](../use/mount-a-board.md)
and [A board that is not in the library](../use/add-a-board.md).

## bom.py

```console
$ python tools/bom.py
warning: the JLC quote assembles 10 × bay-node but the configuration needs 12: re-quote
warning: JLC sells C22893 (data-port-x6) by 1 at least: add it to JLC_MIN_BUY
BOM: 292 lines, total ~ EUR 1,452 (EUR 121/bay)
  Electronics     EUR     1016
  Cables          EUR      177
  Printed parts   EUR       86
  Cameras         EUR       64
  Power           EUR       58
  Motion          EUR       29
  Fasteners       EUR       15
  Analyzer        EUR        7
```

It takes no argument: it counts the rack of `config/rack.yaml` and rewrites its four files. The output
above is that of the committed configuration, 12 bays. The two `warning` lines concern the JLCPCB estimate
the bill carries, and no count: the quote on record assembles 10 bay nodes where 12 bays take 12, and one
part's minimum order is missing from the script's table. A printed part's mass is an estimate: the volume of
its STL file, PETG at 1.27 g/cm³, 55 % of the solid volume. Prices are indicative (EUR before VAT, small
quantities, October 2026).

`bom/README.md` and `bom/rack-bom.csv` are rewritten whole on each run: an edit by hand is lost. The lines
themselves are on [Bill of materials](bill-of-materials.md).

## What is generated, and what is committed

| File | Written by | In the repository |
|---|---|---|
| `mechanical/generated/config.scad`, `boards.scad` | `build.py`, any target | committed; their first line says not to edit them |
| `mechanical/stl/*.stl` | `build.py stl` | committed, in print orientation |
| `site/assets/rack.json`, `parts.glb` | `build.py web` | committed |
| `bom/rack-bom.csv`, `bom/README.md`, `bom/jlc-parts.md`, `site/assets/bom.json` | `bom.py`, and `build.py web` through it | committed |

A generated file is committed with the change that alters it; the last step of `build.py` keeps that
change to the files that really differ. The scripts behind the 3D model, the renders, the assembly drawings and this site are on
[Regenerate the site, the viewer, the renders, the drawings](../engineering/tools.md).
