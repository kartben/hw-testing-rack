# Contribute

A change to BitBunk is a change to a source file and to the outputs regenerated from it, committed together.
Three GitHub workflows check every push and pull request; a fourth builds this site. Hardware design files are
under CERN-OHL-P-2.0, software under Apache-2.0: [Licences and credits](licences-and-credits.md).

## Where is what

| Path | What it holds |
|---|---|
| `config/rack.yaml` | the one source of the rack: rows, bays, tilt, dimensions, which board sits where |
| `config/lab.example.yaml` | the template of the lab file of an installation, `config/lab.yaml`, which git ignores |
| `mechanical/` | OpenSCAD: `lib/`, `parts/`, `boards/boards.yaml` (the board library), `generated/` (from the config), `stl/` (every printed part, committed), `review/` |
| `electronics/<pcb>/` | for each of `power-hub`, `bay-node`, `camera-pod`, `data-port-x6` and `data-port-x4`: `design.py`, the generated KiCad project, `fab/`, `docs/` (renders, schematic PDF) |
| `electronics/data-port/` | the one-port DATA board, retired from the rack, kept for the standalone Solo box |
| `electronics/tools/` | schematic as code (`eda.py`), the PCB builder (`pcbgen.py`), the checks, the parts catalogue |
| `electronics/released.json` | the revisions sent to a fab, with the SHA-256 of their files |
| `firmware/` | Zephyr: `bay-node/`, `power-hub/`, `common/`, the boards, `west.yml` |
| `zephyr/` | `module.yml` (the repository is a Zephyr module), and the patches carried on Zephyr |
| `tools/` | `bayctl.py` (drives a rack), `build.py`, `plate_layout.py`, `bom.py`, `kicad.sh`, `notice/` (the assembly drawings), `tests/`, and the other scripts |
| `bom/` | the bill of materials: `rack-bom.csv` and `README.md` (generated), `sourcing.md` |
| `site/` | the 3D viewer and its BOM page, published under `/viewer/` |
| `render/` | the Blender scenes of the renders |
| `docs/` | this site, the design documents and the dated notes |
| `.github/workflows/` | `firmware.yml`, `hardware.yml`, `tools.yml`, `pages.yml` |

What each script does and needs: [Regenerate the site, the viewer, the renders, the drawings](tools.md); the
three that a builder runs: [build.py, plate_layout.py, bom.py](../reference/tools.md). A board marked
`verified: false` in `mechanical/boards/boards.yaml` has an approximate outline; to
measure it and write its entry: [A board that is not in the library](../use/add-a-board.md).

## Change a source, run its generator

```{include} ../../CONTRIBUTING.md
:start-after: <!-- site:contributing-table -->
:end-before: <!-- /site:contributing-table -->
```

`tools/kicad.sh <board>`, with or without `--route`, builds the PCB again from `design.py` and drops the
routing it had: never run it on one of the five v1.0 PCBs, which are frozen. What to run on a routed or
released PCB: [Change a PCB](change-a-pcb.md).

The generators need Python 3.10 or later (`pip install -r tools/requirements.txt`), OpenSCAD, local or in the
Docker image `openscad/openscad`, and Docker for KiCad 10 (`kicad/kicad:10.0-full`), Freerouting
(`eclipse-temurin:25-jre`) and Blender (`render/Dockerfile`). A local Blender 4.2 or later with the Blender MCP
add-on listening on `127.0.0.1:9876` lets `tools/blender_live.py` render on your GPU.

```{include} ../../CONTRIBUTING.md
:start-after: <!-- site:jlc-parts -->
:end-before: <!-- /site:jlc-parts -->
```

## Outputs go in with the change that alters them

STL files, Gerbers, renders, PDFs, GLB files and the bill of materials are committed with the change that
alters them, never for a date. A regenerated binary often has new bytes for the same content (a date in a zip,
a member's timestamp, a raytracer's noise); `tools/keep_unchanged.py` puts back the committed bytes of every
tracked file whose content did not change:

```console
$ python tools/keep_unchanged.py --dry-run
$ python tools/keep_unchanged.py
```

Without a path it looks at the whole repository. It compares a zip by its members, a PDF without its dates, an
image by its pixels (with Pillow; without it, images are skipped), a GLB or an STL by its triangles.
`tools/kicad.sh <pcb> --fab` runs it on the PCB's folder, and `build.py stl`, `web` and `all` end with it. Which
outputs are committed:
[build.py, plate_layout.py, bom.py › What is generated](../reference/tools.md#what-is-generated-and-what-is-committed).

## What CI checks

| Workflow | Runs on | What it checks |
|---|---|---|
| [Firmware](../../.github/workflows/firmware.yml) | every push and pull request | the two pin maps against `design.py` and the devicetree; three host tests (the RFC 2217 server against pyserial, the access rules, the camera's JPEG end finder); 21 Zephyr builds with warnings as errors: 8 for the ESP32-S3 (the node and the hub on their PCBs and on the two stand-ins, the node on an ESP32-S3-DevKitC and an M5Stack StampS3) and 13 on native_sim, all of which it then runs |
| [Hardware](../../.github/workflows/hardware.yml) | every push and pull request | every printed part through OpenSCAD; for each of six PCB designs, ERC and a read-only DRC with schematic parity, then its fabrication files |
| [Tools](../../.github/workflows/tools.yml) | every push and pull request | the tool tests (`tools/tests`, against the simulated node); a twister hardware map from the example lab file, with no rack; the logic analyzer page's tests under Node 22 |
| [Pages](../../.github/workflows/pages.yml) | a push to `main`; a pull request that touches the site's sources | this site, every Sphinx warning an error; the viewer's assets; the analyzer page; the downloads. Only a push to `main` publishes |

How to run the firmware's tests and checks before you push: [Work on the firmware](work-on-the-firmware.md). The
tool tests run from the top of a checkout:

```console
$ python -m unittest discover -s tools/tests -v
```

They need PyYAML and shapely, and Node 22 for the capture tests. Among them,
`tools/tests/test_released_boards.py` fails when a released PCB's fabrication files change:
[Change a PCB](change-a-pcb.md).
