# Get the STL files

Each printed part has its own STL file, already lying the way it prints. Download them as they are, or
rebuild them when your rack or your bought parts differ from the example.

## Download them

- [The STL files in one archive](/downloads/bitbunk-stl.zip): a folder `stl/` with every part's file.
- [mechanical/stl/](../../mechanical/stl/) on GitHub, one file at a time. The tables on
  [Parts to print](parts-list.md) link each part to its file.

The files are binary STL, in millimetres, under the CERN-OHL-P-2.0 licence
([Licences and credits](../reference/licences-and-credits.md)). There is no 3MF or slicer project: load the
STL files and set up your slicer as [Printer, filament and settings](printer-and-settings.md) says.

## When you need to rebuild them

The files are built for the example rack in `config/rack.yaml`: 4 columns and 3 rows. Your rack can be
smaller or larger. A rack with fewer columns or fewer rows uses the same files: you print fewer copies.
Rebuild them in these cases:

| When | Files that change |
|---|---|
| Your drag chain or camera differs from the assumed size ([Parts to measure before you print](index.md#parts-to-measure-before-you-print)) | `tray`, `chain_anchor`, `chain_foot`; `camera_pod` |
| You add a bay beyond A1 to C4: a fifth column, or a fourth row | the bay's two label files |
| You add a fourth row | its `ladder_d` and `brace_d` |
| You change the height of a row, or the tilt | at least the ladders and the braces |
| A bay has its board's own plate (`plate: boards`) | that plate |
| A board needs a peg that is not among the 17 in the folder | the new peg |

[Choose your rack's size](../plan/choose-your-rack.md) says how to set the size of your rack.
[Add a board to the library](../use/add-a-board.md) covers the plate or pegs for a new board.

## Rebuild them

You need a checkout of the repository, Python with the project's packages, and OpenSCAD or Docker.
[Install what the scripts need](../reference/tools.md#install-what-the-scripts-need) says how to install
them. Then, from the root of the checkout:

```console
$ python tools/build.py stl
```

The command reads `config/rack.yaml` and renders every part into `mechanical/stl/`. It prints `ok` or
`FAIL` for each part. A part that fails keeps its old file: do not print that one. A part whose shape did
not change keeps its file byte for byte, so `git status mechanical/stl` lists only the parts you need to
print again.

To render some parts only, name them:

```console
$ python tools/build.py stl --only tray chain_anchor chain_foot
```

If OpenSCAD is not on your `PATH`, `build.py` runs it in the Docker image `openscad/openscad:latest`.

The bay labels and the lettering on the power box use the font Liberation Sans Bold. Install it before you
build. On Debian or Ubuntu, it is in the package `fonts-liberation`.
