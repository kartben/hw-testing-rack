# Real 3D models of the dev boards

The viewer and the technical renders draw a dev board as a simple stand-in (PCB outline,
a few blocks, headers) unless its maker publishes a 3D model: the photo renders then use the real
model, and the viewer too where its licence allows.  Those models are **not committed**: `tools/fetch_render_assets.py`
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
Today every board in the rack: the **NUCLEO-64** (A1), **NUCLEO-144** (A2), **BeaglePlay** (A3) and **Wio
Terminal** (A4), the **GIGA R1 WiFi + GIGA Display Shield** in B2, the camera bay, the **UNO R4 WiFi** in B4,
and the **Pico 2**, **XIAO** and **Nano Matter** boards of the converted bays.  The library's **nRF52840 DK**
and **nRF54L15 DK** have models for the photo renders only (they left the rack on 2026-10-21 for boards
whose makers publish an open model).  The Wio Terminal is a whole device: its case lies on the plate,
its model lowered under its "PCB" plane (`model.offset`'s third value), its USB-C at its own height
(`usb.z`), its 2.4" LCD showing LVGL's widgets demo (`screen:`, 320 × 240, turned to read from the rack's
front).  Their 2.54 mm pin headers (soldered pins up, for the Dupont jumpers:
`headers:` in `boards.yaml`) are drawn by the viewer on top of the model.  A board's `screen:`
(active area, pixels, which way its top points) gets a live LVGL demo in the viewer
(`tools/lvgl_wasm/`, LVGL's software renderer built for wasm32).

```bash
python tools/fetch_render_assets.py     # textures + the board models below
python tools/board_models.py            # → render/assets/boards/<board-id>.norm.glb
python tools/assembly_glb.py --hq --with-pc-cable --open-bays B3 --out render/assembly-photo.glb
```

A maker that publishes the board's PCB design but no STEP (Nordic's DKs: an Altium PcbDoc, its parts'
models embedded) gets its model from KiCad: `fetch_render_assets.py` extracts the PcbDoc, and
`board_models.py` hands it to `tools/vendor_pcb.py`, which imports it (`kicad-cli pcb import`), exports
its parts (`kicad-cli pcb export glb`) and paints the board's two faces from its copper, mask openings,
silkscreen and holes (`build_board.export_art`, `pcb_glb.board_body`) in the board's own solder-mask
colour (`model: { mask: "#174a78" }`), its text variables (the product name on the silkscreen) from
`model.vars`.  A part whose model KiCad can't read (a SolidWorks part) gets a black block over its pads.
It needs KiCad 10 (`kicad-cli` and a python with `pcbnew`: `$KICAD_CLI`, `$KICAD_PYTHON`).

`board_models.py` finds the PCB (the two biggest planes of the dominant flat axis), turns the
component side up and lays the outline on the drawing's bottom-left corner.  It turns the model
90° if its aspect says so, and checks the size against `boards.yaml`.  `assembly_glb.py` then
turns it like every board (debug USB towards the drawer's port wall, or its right wall for
`orient: side` boards).  If a model comes out
wrong, add a fix-up to the board in `boards.yaml`:

```yaml
model: { rot: 180, flip: false, offset: [0, 0], recolour: { "#003700": "#f4f4f2" } }
```

(`flip` when the parts under the board outreach those on it: a NUCLEO-64's morpho pins; `recolour` swaps a
STEP's generic PCB colour for the board's real one.)

## Sources (checked 2026-10)

| Board | Model | Licence | Login |
|---|---|---|---|
| Raspberry Pi Pico 2 | [official STEP](https://pip.raspberrypi.com/documents/RP-009061-CA) (Raspberry Pi Ltd) | MIT — the viewer's copy `site/assets/boards/rpi-pico2.glb` is published | no — **fetched** |
| Arduino UNO R4 WiFi | [official STEP](https://docs.arduino.cc/resources/models/ABX00087-step.zip) (Arduino), its navy PCB recoloured Arduino teal | CC BY-SA 4.0 — the viewer's copy `site/assets/boards/arduino-uno-r4.glb` is published | no — **fetched** |
| Arduino Nano Matter | [official STEP](https://docs.arduino.cc/resources/models/ABX00112-step.zip) (Arduino), recoloured teal | CC BY-SA 4.0 (the CAD files' `License.txt`) — `arduino-nano-matter.glb` published | no — **fetched** |
| ST NUCLEO-64 (`nucleo-64`: a NUCLEO-G474RE, MB1367 rev D) | STEP in ST's [board manufacturing specification](https://www.st.com/resource/en/board_manufacturing_specification/mb1367_manufacturing.zip) (the board page's CAD resources), its generic green PCB recoloured white | ST's Open Platform License Agreement: distribution "for the purpose of evaluating, testing, and developing application boards based on ST products"; this rack tests ST boards, so `nucleo-64.glb` is published (the user's call, 2026-10-21) | no — **fetched** (st.com answers only a browser's headers) |
| ST NUCLEO-144 (`nucleo-144`: a NUCLEO-U575ZI-Q, MB1549 rev C, its ST-LINK on micro-B) | STEP in ST's [MB1549 manufacturing specification](https://www.st.com/resource/en/board_manufacturing_specification/mb1549-manufacturing.zip) | as the NUCLEO-64's — `nucleo-144.glb` published | no — **fetched** |
| BeaglePlay (rev A2) | [the makers' STEP](https://git.beagleboard.org/beagleplay/beagleplay/-/tree/main/Design) (BeagleBoard.org, Seeed), its grey PCB recoloured black | CC BY 4.0 — `beagleplay.glb` published | no — **fetched** (through git.beagleboard.org's API: its web pages ask a browser check) |
| Seeed Wio Terminal | [Seeed's STEP of the whole device](https://github.com/Seeed-Studio/OSHW-WioTerminal) (OSHW-WioTerminal, `Wio Terminal 3D.stp`), its design colours → white case, black glass, blue joystick | Apache License 2.0 — `wio-terminal.glb` published | no — **fetched** |
| Nordic nRF52840 DK (PCA10056 3.0.3) | Altium PCB in Nordic's [hardware files](https://nsscprodmedia.blob.core.windows.net/prod/software-and-other-downloads/dev-kits/nrf52840-dk/nrf52840-development-kit---hardware-files-3_0_3.zip), its parts' models embedded: populated through KiCad (`tools/vendor_pcb.py`), painted Nordic blue; the interface MCU (a SolidWorks part) a block | Nordic's 5-clause licence (BSD-style, "must only be used with a Nordic Semiconductor ASA integrated circuit") — the renders only | no — **fetched** |
| Nordic nRF54L15 DK (PCA10156 1.0.0) | Altium PCB in Nordic's [hardware files](https://nsscprodmedia.blob.core.windows.net/prod/software-and-other-downloads/dev-kits/nrf54l15-dk/pca10156-nrf54l15-dk-1_0_0.zip), as the nRF52840 DK's, slate blue | no licence stated (the schematic: "All rights reserved") — the renders only | no — **fetched** |
| Arduino GIGA R1 WiFi + GIGA Display Shield (`giga-r1-display`) | official STEP files [ABX00063](https://docs.arduino.cc/resources/models/ABX00063-step.zip) and [ASX00039](https://docs.arduino.cc/resources/models/ASX00039-step.zip) (Arduino), stacked on their Samtec strips and HLE sockets by `board_models.py` (`model.stack`), PCBs recoloured Arduino teal | CC BY-SA 4.0 — the viewer's copy `site/assets/boards/giga-r1-display.glb` is a derivative under the same licence | no — **fetched** |
| Seeed XIAO ESP32S3 (`xiao`: every XIAO on a plate) | [official STEP](https://files.seeedstudio.com/wiki/SeeedStudio-XIAO-ESP32S3/res/seeed-studio-xiao-esp32s3-3d_model.zip) (Seeed Studio), the plain board (the Sense adds its camera board); the outline and pins checked against Seeed's XIAO ESP32C3 v1.3 KiCad project | CC BY-SA 4.0: the Seeed wiki's licence for its content, which links the model (the user's call, 2026-10-20: no licence is written on the model itself) — the viewer's copy `site/assets/boards/xiao.glb` is published | no — **fetched** |
| Arduino UNO R4 Minima | [official CAD zip](https://docs.arduino.cc/hardware/uno-r4-minima) (STEP inside) | CC BY-SA 4.0 | no |
| ESP32-S3 / C6-DevKitC-1 | no board model; official DXF outline and module STEP ([espressif/kicad-libraries](https://github.com/espressif/kicad-libraries)) | CC BY-SA 4.0 + KiCad exception | no |
| nRF5340 DK | Altium hardware files on nordicsemi.com, as the other DKs (`tools/vendor_pcb.py`) | Nordic (BSD-style) | no |
| NUCLEO-64 MB1136 (F401RE …), STM32F746G-DISCO | no STEP in ST's files (MB1136: an empty `Mechanical/` folder) | — | — |
| FRDM-MCXN947, MIMXRT1060/1170-EVKB | design files on nxp.com (Allegro), no 3D model | NXP | yes |
| Infineon kits, TI LaunchPads, Renesas EK-RA, ADI MAX32 / APARD boards | design files without a STEP (Allegro, PADS, ODB++, Gerbers, Altium without its models), or behind a login (checked 2026-10-21) | — | — |
| M5Stack (Core2, CoreS3, AtomS3, StickC Plus …) | [M5_Hardware](https://github.com/m5stack/M5_Hardware): outer-shell STLs only, no colour, no PCB | MIT | no |
| Alif Ensemble E8 DevKit | Altium files with the parts' models embedded (`tools/vendor_pcb.py` would populate it) | Alif's terms of use: no derivative works without their written consent | no |

To add one by hand, put its STEP (or GLB/WRL) at `render/assets/boards/<board-id>.step`, using
the ids from `boards.yaml`, and re-run `tools/board_models.py`.

Credits for the photo renders: BeaglePlay model © Seeed Technology Co., Ltd and BeagleBoard.org Foundation
(CC BY 4.0); Wio Terminal model © Seeed Studio (Apache 2.0); Raspberry Pi Pico 2 model © Raspberry Pi Ltd (MIT); Arduino
UNO R4 WiFi and Nano Matter models © Arduino S.r.l. (CC BY-SA 4.0); XIAO ESP32S3 model © Seeed Studio;
NUCLEO-G474RE and NUCLEO-U575ZI-Q models © STMicroelectronics (Open Platform License Agreement);
nRF52840 DK and nRF54L15 DK models made from Nordic Semiconductor's hardware files (Copyright (c) 2010 -
2024, Nordic Semiconductor ASA, all rights reserved; the nRF52840 DK's under Nordic's 5-clause licence).
Credits for the viewer: Arduino GIGA R1 WiFi and GIGA Display Shield models © Arduino S.r.l.,
CC BY-SA 4.0, stacked and recoloured (`site/assets/boards/giga-r1-display.glb`, same
licence); Raspberry Pi Pico 2 model © Raspberry Pi Ltd, MIT (`rpi-pico2.glb`); XIAO ESP32S3
model © Seeed Studio, CC BY-SA 4.0 (`xiao.glb`, same licence); Arduino UNO R4 WiFi and Nano Matter
models © Arduino S.r.l., CC BY-SA 4.0, recoloured (`arduino-uno-r4.glb`, `arduino-nano-matter.glb`, same
licence); NUCLEO-G474RE and NUCLEO-U575ZI-Q models © STMicroelectronics, under ST's Open Platform License
Agreement (`nucleo-64.glb`, `nucleo-144.glb`); BeaglePlay model © Seeed Technology Co., Ltd and
BeagleBoard.org Foundation, CC BY 4.0, recoloured (`beagleplay.glb`); Wio Terminal model © Seeed Studio,
Apache 2.0, recoloured (`wio-terminal.glb`); the screens run LVGL's music and widgets demos (LVGL, MIT).
