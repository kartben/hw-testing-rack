# Contributing

Everything is generated from sources you can diff:

| Change | Edit | Regenerate |
|---|---|---|
| Shelf geometry, rows, tilt, population | `config/rack.yaml` | `python tools/build.py all` |
| A printed part | `mechanical/parts/*.scad`, `mechanical/lib/*.scad` | `python tools/build.py stl` |
| A dev board's plate | `mechanical/boards/boards.yaml` | `python tools/build.py stl` |
| A schematic / PCB | `electronics/<board>/design.py` | `tools/kicad.sh <board> --route --fab` |
| Part sourcing | `electronics/tools/catalog.py`, `electronics/tools/passives.py` | `python electronics/tools/passives.py`, then the board |
| BOM roll-up | `tools/bom.py` | `python tools/bom.py` |
| Viewer | `site/*.html`, `site/app.js` | `python tools/build.py web` |
| Renders | `render/render.py` (headless), `render/live_scene.py` + `render/live_render.py` (technical), `render/live_photo.py` (photo set) in a running Blender | `python tools/assembly_glb.py`, then `tools/render.sh` or `tools/blender_live.py exec …` |

## Toolchain

* Python ≥ 3.10: `pip install -r tools/requirements.txt`
* OpenSCAD (local, or Docker image `openscad/openscad`)
* Docker for KiCad 10 (`kicad/kicad:10.0-full`), Freerouting (`eclipse-temurin:25-jre`)
  and Blender (`render/Dockerfile`).  A local KiCad 10 opens the generated projects directly.
* Optional: a local Blender ≥ 4.2 with the Blender MCP add-on listening on
  `127.0.0.1:9876` — `tools/blender_live.py` sends the render scripts to it, so
  renders use your GPU and you can tweak the scene interactively before a shot.

## PCB edits by hand

The generator rebuilds the PCB from scratch.  Once you start hand-routing in
KiCad, stop running `tools/kicad.sh <board>` on that board (or keep the
routed `.kicad_pcb` aside) and use `--check --fab` in CI to verify and export.

## Measuring a board

Boards marked `verified: false` in `boards.yaml` have approximate outlines and
get a fence plate.  If you own one, measure (or take the vendor's Gerbers),
add `holes:`/`hole_d:` and set `verified: true`.

## Looking up JLC parts

`tools/jlc_mcp.py "<query>"` runs the `@jlcpcb/mcp` server in Docker and
prints LCSC ids, stock, price and basic/extended status.  The same server is
configured for Claude Code in `.mcp.json` (local, not committed).
