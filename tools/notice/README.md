# Assembly notice (FreeCAD line art → the canvas)

The IKEA-style assembly notice lives on a Design canvas
(`notice.yaml` › `canvas`).  Its drawings — the steps, their detail circles,
the part thumbnails and the hardware icons — are drawn by FreeCAD from the
same OpenSCAD and KiCad sources as the prints and the viewer, and its pages
are generated from one data file.

| File | What |
|---|---|
| `notice.yaml` | the pages: their steps, each step's drawing, parts and hardware with quantities, the parts pages' lists, the cover, the row cable's connectors; the canvas's artboard titles and rows |
| `notice.py` | the drawings: scenes (`STEPS`), thumbnails (`THUMBS`), hardware icons (`hw_shape`) |
| `pages.py` | `notice.yaml` + the drawings' canvas addresses (`assets.json`) → the page files and the canvas index (`canvas.json`) |
| `run.py` | everything up to the drawings, then the list of drawings to upload |
| `pdf.py` | the built pages and the local drawings → one A4 PDF, `mechanical/build/notice/<name>.pdf` (Edge or Chrome, headless) |
| `jobs.py` | on another machine (`NOTICE_REMOTE`): the drawings, within its memory |

## Regenerating

```bash
python tools/notice/run.py                 # every drawing → mechanical/build/notice/out/*.svg, then the upload list
python tools/notice/run.py a3 pin          # some of them
python tools/notice/run.py d1 d2 d3 latch d4   # the documentation's own steps (below)
python tools/notice/run.py --dry           # does it still build? every scene, nothing drawn
```

Whatever the names, every run first remakes the constants, the solids and
the boards (a minute or two), then draws only those.

Without OpenSCAD installed, put on the path a script named `openscad`
(say `~/bin/openscad-docker/openscad`, executable) that runs the
`openscad/openscad` image with the repository mounted at its own path (`run.py` hands OpenSCAD absolute paths, so the `/work` mount of
`tools/build.py`'s Docker fallback does not do here):

```sh
#!/bin/sh
R=/path/to/hw-testing-rack
exec docker run --rm -v "$R:$R" -w "$PWD" openscad/openscad:latest openscad "$@"
```

```bash
PATH=~/bin/openscad-docker:$PATH FREECADCMD=~/claude-scratch/notice/env/bin/freecadcmd python tools/notice/run.py d1
```

A full run takes about 40 minutes (four FreeCAD processes); it ends with
`pages.py plan`: the drawings whose SVG is new or changed since it was
uploaded (`assets.json` keeps each one's SHA-256).  The notice is redrawn
when the design is frozen (an order, a release) or on request, not on every
change; in between, `--dry` (a few minutes) checks that it still builds on
the current state: every step's and part's scene, and a job for every
drawing `notice.yaml` names.

### The documentation's drawings

The documentation site (`docs/`) shows the notice's drawings beside its
build steps: `docs/img/notice/<key>.svg`, named by `:drawing:` and
`:detail:` in the `build-step` blocks of `docs/build/*.md` (and
`docs/use/mount-a-board.md`), with the parts' chips and the hardware icons
(`chip_<part>`, `hw_<fastener>`) that `docs/_ext/bitbunk.py` puts beside
each step.

Five drawings are the documentation's own: the drawer at the bench, one
action a drawing, where the notice's step 9 (`a12s`) shows them all in one
frame.

| Drawing | What |
|---|---|
| `d1` | the drawer's front onto the walls' ends, a PT 2.3 × 8 either side from inside, through the post into its boss |
| `d2` | the cradle onto the rear bay's three bosses, 3 × M3 × 8 into their inserts |
| `d3` | the DATA lead up through the window into J1, then the DATA ×6 down into the cradle until both latches click |
| `latch` | `d3`'s detail: a cut through the left latch's hook over the board's top edge |
| `d4` | the strip on the comb, 5 × PT 2.3 × 8 from above, the long screwdriver |

They are `run.py`'s `DOCS`: a full run draws them and `--dry` builds them
like every other, but they are on no page of the notice, so `notice.yaml`
does not name them and `pages.py plan` never lists them for the canvas.
Their numbers (the front's screws, the latch) are OpenSCAD's own, read from
`drawer.scad` and `x4_cradle.scad` by echo probes; without them `notice.py`
has no such steps and `--dry` fails on them.

From `out/` to the site, each drawing minified as the others are (one
decimal; `svgo` from npm):

```bash
cp mechanical/build/notice/out/d1.svg docs/img/notice/ && npx --yes svgo -p 1 docs/img/notice/d1.svg
```

Redraw and copy the ones a page uses (`grep -rn -e ':drawing:' -e ':detail:'
-e 'img/notice/' docs`) and the chips and icons of the parts and hardware
its steps name, whenever the notice is redrawn; the site does not read the
canvas.  Run `python tools/fetch_pcb_models.py` first: without its cache
the boards' LCSC parts (the node's and the hub's connectors) are drawn as
plain boxes.

### The drawings on another machine

With `NOTICE_REMOTE` set, `run.py` prepares the solids here (OpenSCAD,
KiCad), draws on another machine over ssh (Linux or macOS) and brings the
SVGs back:

```bash
NOTICE_REMOTE="ssh -o BatchMode=yes mac" python tools/notice/run.py
NOTICE_REMOTE="ssh -o BatchMode=yes jump ssh -o BatchMode=yes box" python tools/notice/run.py   # through a jump host
```

The machine needs, in `~/claude-scratch/notice` (`NOTICE_REMOTE_DIR`), a
conda-forge FreeCAD with the Fasteners workbench in its `Mod` (≈ 3–4 GB;
`osx-arm64` for an Apple-silicon Mac, `linux-64` for a PC):

```bash
cd ~/claude-scratch/notice
curl -fsSL https://micro.mamba.pm/api/micromamba/osx-arm64/latest | tar -xj bin/micromamba
MAMBA_ROOT_PREFIX=$PWD/mamba bin/micromamba create -y -p $PWD/env -c conda-forge --override-channels \
  freecad=1.1.3 python=3.12 shapely numpy scipy pyyaml && rm -rf mamba/pkgs
git clone https://github.com/shaise/FreeCAD_FastenersWB.git env/Mod/fasteners
```

`jobs.py` runs the drawings there, one FreeCAD process each, as many at
once as the machine's free memory holds: a whole-rack drawing peaks at
≈ 5 GB, a parts card at ≈ 1 GB; it keeps each drawing's measured peak in
`peaks.json` beside `env/` for the next run.  Memory sets the pace: on a
14 GB Linux box a full run took ≈ 35 minutes, about as long as four local
processes, but this PC stays free.  The machine's FreeCAD (OpenCASCADE
7.9.3, arm64 or x86) rounds a little differently from the Windows build,
so the first run there changes most SVGs by a few bytes.

### Publishing (Claude, with the Artifact tool)

Uploading and publishing go through Claude's Artifact tool, not a command
line.  After `run.py`:

1. **Upload** each group of files `plan` printed (≤ 25 per call):
   Artifact `publish` with `url` = the canvas, `asset: true`,
   `file_paths` = the list.  Save the result's file → address pairs as JSON,
   `{"a3.svg": "/_blob/…", …}`, and run
   `python tools/notice/pages.py record that.json`.
2. **Build** the pages: `python tools/notice/pages.py build`
   → `mechanical/build/notice/canvas/project/*.dc.html` and `canvas.json`.
3. **Publish** them: read the canvas first (Artifact `read`, its
   `project/*.dc.html` and `project/canvas.json`), then Artifact `publish`
   with `url` = the canvas, `root` = `mechanical/build/notice/canvas`,
   `file_path` = its `project/Main.dc.html`, `files` = the other pages by
   their `project/…` paths, plus `project/canvas.json` when pages were added,
   removed or retitled.  The pages are generated: an edit made by hand on the
   canvas is overwritten, so port it into `notice.yaml` or `pages.py` first
   (`pages.py check <dir of the read copy>` shows the differences).
4. Commit `assets.json`.
5. The PDF: `python tools/notice/pdf.py` builds the pages again and prints
   them, with the drawings of `out/`, one A4 page per artboard in the
   canvas's order (the canvas's own Export PDF gives the same pages).

## How the drawings are made

* **Exact solids, no meshes.**  OpenSCAD exports each part's evaluated tree
  (`openscad -o part.csg`); `csg2part.py` rebuilds it with OpenCASCADE: real
  circles and cylinders, exact hulls of circles, polygons only where the part
  has them (the hexagon reliefs).  Volumes match the STLs to 0.1 %.
* **Real fasteners.**  ISO 7045 pan-head Phillips screws and heat-set inserts
  from FreeCAD's Fasteners workbench, threads included.
* **The boards as the viewer has them** (the bay node, the power hub, the
  DATA ×6 standing in its cradle at the back of the drawer, `x4_cradle.scad`
  with its strip; the camera pod's board is `camera_pod.scad`'s stand-in).  KiCad's STEP export of each board,
  its 3D models resolved from KiCad's library and `electronics/lib/3dmodels`
  (`${KIPRJMOD}`), in the `kicad/kicad:10.0-full` image.  Where
  `electronics/tools/build_board.py` has `export_3d_coverage`, the same run
  writes KiCad's 3D coverage report, and `node.py` adds a simple body only
  for the parts it lists as missing (the stand-in table and dimensions of
  `tools/pcb_glb.py`, as exact solids), placed from the `.kicad_pcb`.  It
  logs any part left without a body.  Without the report: a stand-in for
  every footprint the table knows.  Run `python tools/fetch_pcb_models.py`
  first: the LCSC models the boards use are not in the repo.
* **The drawer with its front** (`drawer.scad`, `PART="front_in_place"`),
  screwed on from inside, a PT 2.3 × 8 either side: it rides with the
  drawer, so every drawing with a drawer shows it.
* **The power box** where `config/rack.yaml` › `power_box` puts it (under
  A1), the hub on its standoffs; the charger, its USB-C cable and the row
  feed are simple bodies (`notice.py`, `charger_shape`, `pd_cable_shape`,
  `feed_shape`).
* **Bought parts in the bay**: the drag chain (Olimex 7 × 7) is drawn with
  `chain_parts.scad`'s link and removable bar at its size, pinned along the
  centre line `config/rack.yaml` › `chain` gives between its two rigid end
  pieces (closed, open, or its bars pulled out); the PH 8 DATA lead from
  the node's vertical J7 through the chain into the DATA ×6's J1 on its rear
  face, along the viewer's route (`chain_shape`, `chain_ends_shape`,
  `data_lead_shape`).  Cables are swept splines (`pipe`:
  one sweep, or a few fused end to end where OpenCASCADE refuses the whole).
* **The row cable from the board.**  `notice.yaml` › `row_cable` names the two
  connectors (node 0's out, node 1's in); their pin count and position come
  from the `.kicad_pcb`, for the step drawing and the icon.
* **One hidden-line projection per drawing.**  `notice.py` places the parts as
  in the rack (the step's new parts at their approach position), projects the
  whole compound once with TechDraw (`projectEx`: visible sharp edges and
  outlines, no hidden or tangent lines), then gives each visible edge back to
  the part it lies on, so parts already in place are drawn light grey, new
  ones black, fasteners thinner.  Dashed screw axes go through the same
  projection.  Each drawing is fitted to its slot on the A4 page, clear of the
  page's detail circle and "click!" bubble.

`fit_check.py` writes one assembled bay as a STEP for an interference check
(`inspect.interference` in SolidCraft found the drawer magnet boss hitting the
tray's guide lip; fixed).

Needs FreeCAD 1.x with the Fasteners workbench (`FREECADCMD=` if `freecadcmd`
is not on the path), OpenSCAD (or the Docker script under Regenerating), and
Docker (or kicad-cli, without the coverage report) for the boards.  Projections are cached in
`mechanical/build/notice/out/cache/`; `run.py` always recomputes them.
