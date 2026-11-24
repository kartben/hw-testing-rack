# Regenerate the site, the 3D viewer, the renders and the drawings

Each of this site, the 3D viewer, the screenshots, the renders and the assembly drawings is rebuilt by a script
of the repository, from the same sources as the printed parts and the PCBs. An output is committed with the
change that alters it, never on a schedule ([Contribute](contribute.md#outputs-go-in-with-the-change-that-alters-them)).

## Scripts and what they need

`bayctl`, which drives a rack, is on [its own page](../reference/bayctl.md); `build.py`, `plate_layout.py` and
`bom.py`, which a builder runs, on [build.py, plate_layout.py, bom.py](../reference/tools.md). The others:

| Script | What it does, and what it needs |
|---|---|
| `tools/kicad.sh` | generates, routes, checks and exports one PCB ([Change a PCB](change-a-pcb.md)). Needs Docker, bash, curl |
| `electronics/tools/build_board.py` | the generator itself, run by `kicad.sh` inside KiCad's image. Needs KiCad 10's Python (`pcbnew`) |
| `tools/panel.sh` | the DATA ×4's order panel, with KiKit 1.8.1. Needs Docker |
| `tools/route_farm.py` | routes one placement many ways with Freerouting and keeps the best. Needs Docker or a JRE; ssh hosts, optional |
| `tools/released.py` | checks the released PCBs against `electronics/released.json`; `--record` prints a new entry. Needs Python only |
| `tools/keep_unchanged.py` | puts back the committed bytes of regenerated outputs whose content did not change. Needs git; Pillow for images, trimesh for GLB and STL |
| `tools/fetch_pcb_models.py` | fetches the LCSC / EasyEDA 3D models of the PCBs' parts into a git-ignored cache. Needs network access |
| `tools/make_step_models.py` | draws STEP models at a datasheet's size where KiCad has none. Needs FreeCAD's `freecadcmd` |
| `tools/pcb_glb.py` | turns each PCB's KiCad GLB into the viewer's model; `--check` lists parts without a body. Needs numpy, trimesh, Pillow |
| `tools/webscene.py` | the viewer's `parts.glb` and `rack.json`, called by `build.py web`. Needs numpy, scipy, trimesh |
| `tools/assembly_glb.py` | bakes the rack into one GLB for the renders. Needs `tools/requirements.txt` |
| `tools/render.sh`, `tools/blender_live.py` | renders in Blender, headless in Docker or in a running Blender. Needs Docker, or Blender 4.2 or later with the Blender MCP add-on |
| `tools/fetch_render_assets.py`, `tools/board_models.py`, `tools/vendor_pcb.py` | the makers' 3D models of the development boards, for the renders and the viewer. Needs network access; KiCad 10 for boards published as Altium PCBs |
| `tools/lvgl_frame.mjs`, `tools/lvgl_wasm/build.sh` | one frame of an LVGL screen as a PNG; the viewer's LVGL screens built for wasm32. Needs Node; the `zephyr-build:v0.29.4` image |
| `tools/jlc_mcp.py`, `tools/jlc_parts_snapshot.py`, `electronics/tools/passives.py` | LCSC part lookups, the parts snapshot behind the bill's prices, the passives resolver. Needs network access; Docker (`node:22-alpine`) for the lookups and the resolver, Node and a checkout of the jlcpcb-skill-mcp server (`JLC_CALL`) for the snapshot |
| `tools/panel_proto.py`, `tools/panel_frame_fea.py` | the printed frame's prototype parts, and its stiffness model. Needs OpenSCAD, numpy, trimesh; shapely for the stiffness model, matplotlib for its plot |
| `tools/notice/run.py` | the assembly drawings (below). Needs FreeCAD 1.x and its Fasteners workbench (1.1.3 on a remote machine), OpenSCAD, `kicad-cli` or Docker |
| `tools/ns3-wifi-capacity/`, `tools/bsim-wifi-coex/` | the two Wi-Fi studies, each with its README. Needs ns-3.49; BabbleSim in the `zephyr-build` image |
| `firmware/tools/check_pinmap.py` | the pin maps against `design.py` and the devicetree ([Work on the firmware](work-on-the-firmware.md#the-pin-map-check)). Needs Python only |
| `firmware/bay-node/web/dev_server.py`, `firmware/power-hub/web/dev_server.py` | the simulated node and hub. Needs Python; PyYAML for the node's; Pillow, optional |
| `tools/analyzer_capture.mjs` | the other half of `bayctl capture`: the bay page's decoders run on a capture. Needs Node 22 or later |
| `electronics/tools/antennas.py`, `decoupling.py`, `zoneprio.py` and the other checks | layout checks, each runnable alone, run by the tool tests. Needs Python or KiCad's Python |
| `tools/tests/` | the tool tests: `python -m unittest discover -s tools/tests -v`. Needs PyYAML, shapely; Node 22 for the capture tests |

Read from each script's docstring or header comment.

## This site

The sources are under `docs/`: Markdown read by Sphinx with MyST, in the Shibuya theme. Build it from the top of
a checkout:

```console
$ pip install -r tools/requirements.txt -r docs/requirements.txt
$ sphinx-build -W --keep-going -b html docs docs/_build/html
```

Every warning is an error: a broken link or a missing drawing stops the build. The site's own extensions are
in `docs/_ext/`:

| Extension | What it does |
|---|---|
| `bitbunk.py` | turns a relative link to a repository file into a link to GitHub; the `build-step`, `status` and `tool-help` directives, the last of which runs a tool's `--help` while the site is built |
| `bitbunk_nav.py` | the top bar, the sidebars, the breadcrumbs and the Next links, from `docs/_toc.yml`; and the banner of each design document and dated note, from its entry under `notes:` in the same file, where `search: false` keeps a note out of the search |
| `bitbunk_bom.py` | the `bom-table` and `printed-parts` directives, read from `bom/rack-bom.csv` and computed by `tools/bom.py` |

The repository's name and the site's address come from the environment when GitHub Actions builds the site
(`GITHUB_REPOSITORY`, `DOCS_BASEURL`): renaming the repository takes no edit of `docs/conf.py`.

The [Pages workflow](../../.github/workflows/pages.yml) builds the site, then the viewer's assets
(`python tools/build.py web`, with OpenSCAD), and adds what Sphinx does not build: `site/` copied to `/viewer/`,
the analyzer page to `/analyzer/`, and under `/downloads/` every committed STL file in `bitbunk-stl.zip` and one
`<pcb>-fab.zip` per PCB with the content of `electronics/<pcb>/fab/`. The old address `/bom.html` forwards to
`/viewer/bom.html`. A pull request that touches the site's sources builds it; only a push to `main` publishes it.

## The 3D viewer

The viewer is the `site/` directory, as it is: three.js 0.170.0 from jsDelivr, about 20 MB of committed assets.
`site/` is copied to `/viewer/` when the site is built, never moved: files across the repository name it.

| Asset under `site/assets/` | Made by |
|---|---|
| `rack.json`, `parts.glb` | `python tools/build.py web`, through `tools/webscene.py`, from `config/rack.yaml` and the parts |
| `bom.json` | `python tools/bom.py` |
| `pcb/<pcb>.glb` | `python tools/pcb_glb.py`, from each PCB's export; not rebuilt in CI |
| `boards/<board>.glb` | `python tools/board_models.py`, for the boards whose model's licence allows it ([Licences and credits](licences-and-credits.md)) |
| `lvgl/lvgl-demo.wasm` | `tools/lvgl_wasm/build.sh` |

It is lit as the photo renders are: a real room, Poly Haven's "Small Empty Room 1" cut to 512 × 256 in
`site/assets/env/`, and AgX with Blender's "Medium High Contrast" look. Its *High quality* box adds ambient
occlusion (GTAO), a glow on the status LEDs and the camera lights, 4× MSAA through the post-processing and
4096² sun shadows instead of 2048². The box is on by default, off on a phone, a tablet or a small GPU, drops
by itself to low when the first seconds run under 25 fps, and the browser remembers a choice made in it.

To look at it locally, serve the directory and open <http://localhost:8000>; opening `index.html` from the disk
does not work:

```console
$ python -m http.server -d site 8000
```

### Its URL parameters

The viewer reads them once, at load; the address bar never changes as you move.

| Parameter | Effect |
|---|---|
| `view=iso`, `front`, `side`, `rear`, `bay` | the starting camera, `iso` by default; `bay` frames the selected bay, B2 if none is |
| `view=camera` | looks into the selected bay's camera from the front |
| `view=dut`, `view=jumpers` | a close-up of the selected bay's USB cable, or of its jumper wires |
| `view=custom&eye=x,y,z&look=x,y,z` | any camera, in millimetres of the rack's frame, Z up |
| `bay=<id>` | selects the bay and opens its panel |
| `openbay`, `openbay=0..1` | with `bay`: that drawer pulled out, all the way when no value is given |
| `open=0..1` | every drawer pulled out to that fraction |
| `explode=0..1` | the parts spread apart |
| `xray` | ladders and braces hidden, drawers and plates seen through |
| `camlight` | every camera's light on |
| `preview`, `preview=<bay>` | opens a bay camera's preview: an Arducam Mega behind its ~120° lens, with fisheye, noise, auto-exposure and JPEG, 640 × 480 at 5 fps |
| `hideui` | no top bar, controls, hint, panel or selection outline |
| `quality=high`, `quality=low` | forces the rendering quality |
| `debug`, `capture` | `window.__viewer` for scripts; a drawing buffer kept for screenshots |

Read from `site/app.js`. A bay name is case-sensitive and must exist, A1 to C4 in the default rack: `?bay=b3`
or `?bay=D1` ends in "Could not load the model", and so does `view=custom` without `eye` and `look`. Only B2 has a
camera. `hideui` leaves the camera preview and the bay labels. Three links that work:

- [/viewer/?bay=B3&openbay=1&view=bay](/viewer/?bay=B3&openbay=1&view=bay): bay B3, its drawer out
- [/viewer/?bay=B4&openbay=1&view=dut&hideui](/viewer/?bay=B4&openbay=1&view=dut&hideui): B4's USB cable, no UI
- [/viewer/?bay=B2&view=camera&camlight=1&preview=B2](/viewer/?bay=B2&view=camera&camlight=1&preview=B2): what
  B2's camera sees, its light on

The stills of the model on this site are under `docs/img/viewer/`, taken with `python tools/viewer_still.py <picture> "<query>"` on the site's paper colour; with `--dark` it takes the twin that the dark theme shows, kept under `docs/_static/viewer-dark/` by the same name.

## Screenshots and the console screencast

Every screenshot of a bay's or the hub's page on this site is of the simulated node or hub, made by a script:

| Command | Writes | Needs |
|---|---|---|
| `python firmware/bay-node/web/screenshots.py` | `docs/img/web-ui-*.png` | Playwright, Pillow, an installed Chrome or Edge |
| `python firmware/power-hub/web/screenshots.py` | `docs/img/hub-ui-*.png` | Playwright, Pillow, an installed Chrome or Edge |
| `python firmware/bay-node/web/screencast.py --workspace <west workspace>` | `docs/img/web-console.webp` | Playwright, Docker, ffmpeg, a west workspace made from `firmware/west.yml` |
| `python firmware/bay-node/web/grab_camera.py` | `firmware/bay-node/web/camera/*.jpg`, the simulated camera's frames | Playwright, Chrome |

```console
$ pip install playwright pillow
```

`--channel msedge` takes Edge, and `--channel chromium` the Chromium of `playwright install chromium`. The
screenshot scripts run the development server in-process; the screencast runs the real console code on
native_sim in the `zephyr-build:v0.29.4` image, with a Zephyr shell as the board. In the pictures the node is
B2, `bay-b2.local` at 192.168.1.78, held by a CI host for "twister job 8812"; the simulated hub has a 140 W EPR
charger and eight bays in rows A to C, not the default twelve. Element shots at 2×, quantised to 256 colours,
come from `firmware/common/web/shots.py`, which all of them share.

## Renders

The large renders of `docs/img/` (`hero`, `side`, `drawer`, `exploded`, and `photo-desk`, `photo-drawer`,
`photo-boards`, `photo-detail`) were made on 2026-10-27 and show the earlier rack of two rows of four bays; they
need making again. `power-box.jpg` shows hub v0.5. Every render starts from a GLB of the whole scene, baked by
`tools/assembly_glb.py` from the viewer's scene (`--hq`: the parts' full meshes).

Headless, in Docker (Blender 4.5.14, Cycles on the CPU, an image built from `render/Dockerfile` on the first run):

```console
$ tools/render.sh
$ SAMPLES=256 tools/render.sh hero
```

With no argument it renders `hero`, `side`, `drawer` and `exploded` into `docs/img/`. Its exploded bay is C3;
the committed `exploded.jpg` explodes B2, with the commands of the next block.

In a Blender you already have open, with its GPU, through the Blender MCP add-on listening on `127.0.0.1:9876`:

```console
$ python tools/blender_live.py exec render/live_scene.py
$ python tools/blender_live.py exec render/live_render.py hero
$ python tools/blender_live.py exec render/live_render.py drawer:B3 docs/img/drawer.jpg
```

One bay laid flat, its layers pulled apart (`--gap`, 45 mm by default):

```console
$ python tools/assembly_glb.py --hq --explode-bay B2 --out render/bay-exploded.glb
$ python tools/blender_live.py exec render/live_scene.py render/bay-exploded.glb
$ python tools/blender_live.py exec render/live_render.py exploded
```

The photo set, a small office lit through a window: an oak desk against a plaster wall, PETG with 0.2 mm
layer lines, a laptop wired to bay B4 by a USB-C cable that hangs as a catenary, depth of field, bloom and a
vignette, rendered at 2× and averaged down:

```console
$ python tools/fetch_render_assets.py
$ python tools/board_models.py
$ python render/screen_terminal.py
$ node tools/lvgl_frame.mjs music 480 800
$ python tools/assembly_glb.py --hq --with-pc-cable --open-bays B3 --out render/assembly-photo.glb
$ python tools/blender_live.py exec render/live_photo.py build
$ python tools/blender_live.py exec render/live_photo.py shot desk
```

`shot` takes `desk`, `drawer`, `boards` or `detail`, written to `docs/img/photo-<shot>.jpg`. `lvgl_frame.mjs`
draws the GIGA's screen in B2; the drawer fronts' status screens are drawn by `assembly_glb.py`. The textures and the
board models that `fetch_render_assets.py` downloads stay in `render/assets/`, which git ignores; how the board
models are normalised: [boards-3d.md](../boards-3d.md). The KiCad renders of the PCBs are written by
`tools/kicad.sh <pcb> --fab`.

`docs/img/` is where the screenshot, screencast and render scripts write by default, and two of its files are
test fixtures: `firmware/bay-node/tests/jpeg/test_jpeg.py` opens `hero.jpg` and `photo-boards.jpg`. Do not
rename or move them without changing the test.

## The assembly drawings, step by step

The line drawings of the Build pages are the assembly notice's, drawn by FreeCAD from the same OpenSCAD and
KiCad sources as the prints, with the pages and their steps in `tools/notice/notice.yaml`:

```console
$ python tools/notice/run.py
$ python tools/notice/run.py a3 pin
$ python tools/notice/run.py --dry
```

The first draws every drawing into `mechanical/build/notice/out/`, about 40 minutes with four FreeCAD processes;
the second draws the ones named; the third checks in a few minutes that every scene still builds. Drawing on another
machine over ssh, and what it needs: [tools/notice/README.md](../../tools/notice/README.md). The site's copies
are `docs/img/notice/<key>.svg`.

The drawings date from 2026-10-20. Of the notice's 33 steps, 22 still show the current design; 8 show it but
name the wrong screw or nut, and the Build pages use them with the hardware of `bom/rack-bom.csv`; 3 show a
design that is gone, and the Build pages go without them. Redraw the 3 first, then the 8.

| Step | Drawing | Standing | What differs today |
|---|---|---|---|
| A1 two base ladders | `a1` | current | |
| A2 floor plate | `a2` | current | |
| A3 base brace | `a3`, `pin` | hardware | square nuts pushed into pockets, not inserts |
| A4 row ladders snap on | `a4`, `hook` | current | |
| A5 node onto the tray | `t1` | hardware | M3 × 8, not M3 × 6 |
| A6 drag chain's end pieces | `a9b` | hardware | PT 2.3 × 8, not PT 2.6 × 8 |
| A7 the DATA lead into the chain | `a10o` | current | |
| A8 chain anchor, lead into J7 | `t2` | current | |
| A9 the DATA board | `a12s` | gone | the one-port board, retired; now a cradle on three inserts and a DATA ×6 or ×4 slid into it |
| A10 drawer onto the ledges | `t3` | hardware | PT 2.3 × 8; the drawer drawn without its separate front |
| A11 stops, cams, bobbin | `p1`, `clip` | current | |
| A12 board against the stops | `p2` | current | |
| A13 plate into the drawer | `p3` | current | |
| A14 the board's cable | `p4` | gone | its caption's right-angle plug: the plug is straight, standing in the port wall |
| A15 tray slides in | `t4` | current | |
| A16 row brace | `a6` | hardware | as A3 |
| A17 cap strips, cap plate | `a7` | current | |
| B1 base ladder, floor plate | `b1` | current | |
| B2 base brace on the shared ladder | `b2`, `pin_b` | hardware | square nuts, not inserts |
| B3 row ladder | `b3r` | current | |
| B4 its tray slides in | `b3t` | hardware | the hardware of A5 to A10 |
| B5 the jumper between two nodes | `b4` | current | |
| B6 brace, cap strip, cap plate | `b5a` | current | |
| C1 inserts into the hub's standoffs | `c0` | current | |
| C2 hub and spacers | `c1` | current | |
| C3 lid | `c2` | hardware | M3 × 8, not M3 × 6 |
| C4 power box under A1 | `c3` | current | |
| C5 charger cable | `c4` | current | |
| C6 one feed per row | `c5` | current | three rows, not two |
| D1 pod board and diffuser | `k1` | current | |
| D2 pod under the ceiling | `k2` | gone | two M3 × 8 on a diagonal, not four screws; the pod's lip changed |
| D3 camera into its sleeve | `k2m` | current | |
| D4 camera lead's route | `k3` | current | |

Sections A to D are one bay, the next bay, the power box and the camera. The standings were read on 2026-11-24,
against `bom/rack-bom.csv` and the parts' sources. Nothing in the notice shows the square nuts, the drawer front,
the cradle and its strip, a dense bay's slot bin, a sled bay or a third row. The printed parts the notice has no
card for have a still of the 3D model instead, under `docs/img/viewer/`: `part-tray.jpg`, `part-drawer.jpg`,
`part-drawer-front.jpg`, `part-drawer-block.jpg` (the drawer's port block), `part-drawer-sled.jpg`,
`part-x4-cradle.jpg`, `part-x4-strip.jpg`, `part-slot-bin.jpg`.

## Docker images

| Image | Used by |
|---|---|
| `kicad/kicad:10.0-full` | `tools/kicad.sh`, the Hardware workflow, `tools/notice/run.py` |
| `eclipse-temurin:25-jre` | Freerouting, in `tools/kicad.sh --route` and `tools/route_farm.py` |
| `hw-testing-rack/kicad-kikit:10.0-1.8.1`, built once from the KiCad image | `tools/panel.sh` |
| `openscad/openscad:latest` | `tools/build.py`, when no OpenSCAD is on the `PATH` |
| `hw-testing-rack/blender`, built from `render/Dockerfile` | `tools/render.sh` |
| `node:22-alpine` | `tools/jlc_mcp.py` |
| `ghcr.io/zephyrproject-rtos/zephyr-build:v0.29.4` | `screencast.py`, `tools/lvgl_wasm/build.sh`, `tools/bsim-wifi-coex/` |
