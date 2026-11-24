# Get the STL files

The 78 STL files of the structure are committed in the repository, each in the orientation it prints in:
[the STL files in one archive](/downloads/bitbunk-stl.zip), 13 MB unpacked.

:::{status} designed
Every file is rendered again by CI on each push. The 30 parts that existed on 2026-10-21 were sliced; no part
has been printed. [What exists today](../plan/status.md#status-frame).
:::

You need OpenSCAD only to rebuild them, in the three cases of the table [below](#when-you-must-rebuild-them).
The committed tray, chain anchor and chain foot carry the drag chain's assumed dimensions, which nobody has
checked against a chain: [Measure before you print](index.md).

## Download them

| From | What you get |
|---|---|
| [the STL files in one archive](/downloads/bitbunk-stl.zip) | a folder `stl/` with the 78 files, as the main branch has them |
| [mechanical/stl/](../../mechanical/stl/) on GitHub | the same files one by one; [Parts and quantities](parts-list.md) links each part to its file |
| The artefact `stl` of the *Hardware* workflow | the files CI rendered for one commit or pull request. It needs a GitHub login and it expires |

{{ 'The workflow\'s runs are under [the repository\'s Actions]({}/actions/workflows/hardware.yml).'.format(repo_url) }}

The files are binary STL in millimetres. There is no 3MF, slicer project or profile file: load the STL files
into your slicer, set it as [Printer, filament, settings](printer-and-settings.md) says, and keep each part
the way up its file has it. They are published under CERN-OHL-P-2.0, as the rest of the hardware:
[Licences and credits](../engineering/licences-and-credits.md).

## When you must rebuild them

| You rebuild when | Which files change | Start from |
|---|---|---|
| A bought part does not measure what the model assumes | The drag chain: `tray`, `chain_anchor`, `chain_foot`. The camera: `camera_pod` | [Measure before you print](index.md) |
| The layout is not the default 4 × 3 | A row more: a `ladder_<row>` and a `brace_<row>` of its own. Another row height or tilt: the ladders and the braces at least. A bay the default does not have: its two label files. A bay that says `plate: boards`: its own plate | [Choose a size, change the layout](../plan/choose-your-rack.md) |
| A board needs a peg that is not among the 17 committed ones | A `peg_stop_h<H>` and a `peg_base_h<H>` for its standoff, a `peg_pin_d<hole>_h<H>` for its hole | [A board that is not in the library](../use/add-a-board.md) |

By `part_jobs()` in [tools/build.py](../../tools/build.py), no part file depends on the number of columns:
a rack with fewer columns is fewer copies of the same files, and one with more columns needs the two label
files of each new bay. Rows are different: the cap strip is rendered for the row it sits on, so a rack with
fewer rows is rebuilt, and `git status` then says which files changed.

## What is in the folder

| Files | Count | Where they go |
|---|---|---|
| `ladder_base`, `ladder_a`, `ladder_b`, `ladder_c`, `ladder_cap` | 5 | the side walls, one file per level |
| `brace_base`, `brace_a`, `brace_b`, `brace_c` | 4 | the X behind each bay, one file per level |
| `floor_plate`, `cap_plate` | 2 | |
| `tray`, `drawer`, `drawer_front`, `x4_cradle`, `x4_strip` | 5 | every bay |
| `chain_anchor`, `chain_foot` | 2 | a bay whose drawer is on a drag chain |
| `drawer_sled`, `drawer_block` | 2 | a bay without a chain (`mount: sled` or `fixed`) |
| `plate`, `slot_bin`, `plate_giga-r1-display` | 3 | the board plate, a dense bay's bin, and the own plate of the example's bay B2 |
| `peg_stop_h<H>`, `peg_base_h<H>`, `peg_cam`, `peg_pin_d<hole>_h<H>`, `peg_bobbin` | 17 | one stop and one cam base per standoff height of the board library, three pins; the default rack uses 12 of them |
| `bay_label_<bay>`, `bay_label_<bay>_inlay` | 24 | two per bay, A1 to C4 |
| `camera_pod`, `camera_diffuser` | 2 | |
| `power_box_base`, `power_box_lid`, `power_box_labels` | 3 | |
| `cover_box4`, `chain_link`, `chain_bar` | 3 | optional: a cover for a drawer's rear bay, a printable chain link and its bar |
| `standalone_solo_base`, `_solo_lid`, `_quad_base`, `_quad_shelf`, `_quad_lid`, `_desk_frame` | 6 | [one bay on a desk](../build/one-bay-on-a-desk.md), outside the rack |

## Rebuild them

You need a git checkout, Python and its packages, and OpenSCAD or Docker:
[Get a checkout and install what they need](../reference/tools.md#get-a-checkout-and-install-what-they-need).
Then, from the root of the checkout:

```console
$ python tools/build.py stl
```

It rewrites `mechanical/generated/config.scad` from `config/rack.yaml`, renders every part into
`mechanical/stl/` and prints `ok` or `FAIL` for each. A part whose `assert` fails (a drag chain that does
not fit, for instance) is a `FAIL` with the assert's text, and its file is not rewritten: the old one is
still in the folder, and it is not the part to print. At the end, a file whose shape did not change goes back
to its committed bytes, so `git status mechanical/stl` lists the parts to print again and no others.

To render some parts only, name them after the target:

```console
$ python tools/build.py stl --only tray chain_anchor chain_foot
```

Without OpenSCAD on the `PATH`, `build.py` runs the Docker image `openscad/openscad:latest`. The bay labels
and the power box's lettering are set in Liberation Sans Bold: install that font, as CI does with the
package `fonts-liberation`. The other options, and what each line of the output means:
[build.py](../reference/tools.md#build-py).

The header of each file under `mechanical/parts/` gives the OpenSCAD command for its part, to run from
`mechanical/` once `python tools/build.py config` has written the configuration:

```console
$ cd mechanical
$ openscad -D 'PART="row"' -D ROW=0 -o ladder_a.stl parts/ladder.scad
```
