# Real 3D models of the dev boards

The viewer and the technical renders draw every dev board as a simple stand-in (PCB outline,
a few blocks, headers).  The photo renders can use the boards' real 3D models instead, where
their makers publish one.  Those models are **not committed**: `tools/fetch_render_assets.py`
downloads the ones that need no login into `render/assets/` (git-ignored), and
`tools/board_models.py` normalises them into the frame of `mechanical/boards/boards.yaml`.

The viewer uses a maker's model only where its licence lets the repository publish it
(`model: { web: true }` in `boards.yaml`): `board_models.py` then also writes a copy to
`site/assets/boards/<board-id>.glb`, which the viewer draws instead of the stand-in.  The copy keeps
every part as the maker drew it (decimating CAD meshes tears boards and chips), with one material per
colour.  Gold and bright grey parts read as metal, and the solder mask lets the copper show through.
A STEP solid painted face by face (a XIAO's black mask, gold pads and FR4 edges) is split by colour.
gltfpack (meshoptimizer: `npm i -g gltfpack`, or its command in `$GLTFPACK`) quantises and
meshopt-compresses the copy: the Pico 2 shrinks to 334 kB for 131 k triangles.  Without gltfpack the copy
is written plain.
Today: the **GIGA R1 WiFi + GIGA Display Shield** in B2, the camera bay, and the **Pico 2** and **XIAO**
boards of the converted bays.  Their 2.54 mm pin headers (soldered pins up, for the Dupont jumpers:
`headers:` in `boards.yaml`) are drawn by the viewer on top of the model.  A board's `screen:`
(active area, pixels, which way its top points) gets a live LVGL demo in the viewer
(`tools/lvgl_wasm/`, LVGL's software renderer built for wasm32).

```bash
python tools/fetch_render_assets.py     # textures + the board models below
python tools/board_models.py            # → render/assets/boards/<board-id>.norm.glb
python tools/assembly_glb.py --hq --with-pc-cable --open-bays B3 --out render/assembly-photo.glb
```

`board_models.py` finds the PCB (the two biggest planes of the dominant flat axis), turns the
component side up and lays the outline on the drawing's bottom-left corner.  It turns the model
90° if its aspect says so, and checks the size against `boards.yaml`.  `assembly_glb.py` then
turns it like every board (debug USB towards the drawer's port wall, or its right wall for
`orient: side` boards).  If a model comes out
wrong, add a fix-up to the board in `boards.yaml`:

```yaml
model: { rot: 180, flip: false, offset: [0, 0] }
```

## Sources (checked 2026-10)

| Board | Model | Licence | Login |
|---|---|---|---|
| Raspberry Pi Pico 2 | [official STEP](https://pip.raspberrypi.com/documents/RP-009061-CA) (Raspberry Pi Ltd) | MIT — the viewer's copy `site/assets/boards/rpi-pico2.glb` is published | no — **fetched** |
| Arduino UNO R4 WiFi | [official STEP](https://docs.arduino.cc/resources/models/ABX00087-step.zip) (Arduino) | CC BY-SA 4.0 | no — **fetched** |
| Arduino GIGA R1 WiFi + GIGA Display Shield (`giga-r1-display`) | official STEP files [ABX00063](https://docs.arduino.cc/resources/models/ABX00063-step.zip) and [ASX00039](https://docs.arduino.cc/resources/models/ASX00039-step.zip) (Arduino), stacked on their Samtec strips and HLE sockets by `board_models.py` (`model.stack`), PCBs recoloured Arduino teal | CC BY-SA 4.0 — the viewer's copy `site/assets/boards/giga-r1-display.glb` is a derivative under the same licence | no — **fetched** |
| Seeed XIAO ESP32S3 (`xiao`: every XIAO on a plate) | [official STEP](https://files.seeedstudio.com/wiki/SeeedStudio-XIAO-ESP32S3/res/seeed-studio-xiao-esp32s3-3d_model.zip) (Seeed Studio), the plain board (the Sense adds its camera board); the outline and pins checked against Seeed's XIAO ESP32C3 v1.3 KiCad project | CC BY-SA 4.0: the Seeed wiki's licence for its content, which links the model (the user's call, 2026-10-20: no licence is written on the model itself) — the viewer's copy `site/assets/boards/xiao.glb` is published | no — **fetched** |
| Arduino UNO R4 Minima | [official CAD zip](https://docs.arduino.cc/hardware/uno-r4-minima) (STEP inside) | CC BY-SA 4.0 | no |
| ESP32-S3 / C6-DevKitC-1 | no board model; official DXF outline and module STEP ([espressif/kicad-libraries](https://github.com/espressif/kicad-libraries)) | CC BY-SA 4.0 + KiCad exception | no |
| nRF52840 / nRF5340 / nRF54L15 DK | Altium hardware files on nordicsemi.com (KiCad can import them and export STEP; untested) | Nordic (BSD-style) | no |
| NUCLEO-64 / -144, STM32F746G-DISCO | ST publishes no STEP; community models on GrabCAD / SnapEDA | varies | yes |
| FRDM-MCXN947, MIMXRT1060/1170-EVKB | design files on nxp.com, no 3D model listed | NXP | yes |

To add one by hand, put its STEP (or GLB/WRL) at `render/assets/boards/<board-id>.step`, using
the ids from `boards.yaml`, and re-run `tools/board_models.py`.

Credits for the photo renders: Raspberry Pi Pico 2 model © Raspberry Pi Ltd (MIT); Arduino
UNO R4 WiFi model © Arduino S.r.l. (CC BY-SA 4.0); XIAO ESP32S3 model © Seeed Studio.
Credits for the viewer: Arduino GIGA R1 WiFi and GIGA Display Shield models © Arduino S.r.l.,
CC BY-SA 4.0, stacked and recoloured (`site/assets/boards/giga-r1-display.glb`, same
licence); Raspberry Pi Pico 2 model © Raspberry Pi Ltd, MIT (`rpi-pico2.glb`); XIAO ESP32S3
model © Seeed Studio, CC BY-SA 4.0 (`xiao.glb`, same licence); the screen runs LVGL's music
demo (LVGL, MIT).
