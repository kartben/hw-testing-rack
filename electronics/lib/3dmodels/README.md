# 3D models

Models that KiCad's own 3D library lacks, for the boards' STEP / GLB exports, the KiCad renders and
the web viewer.  `electronics/tools/catalog.py` (`Cat.model`) attaches one to a part: its file here,
and its offset and rotation on the part's KiCad footprint.  `pcbgen.set_model()` writes it into the
board with a project-relative path (`${KIPRJMOD}/../lib/3dmodels/…`), so it resolves on any machine
and in CI.

| File | Part | Source | Licence |
|---|---|---|---|
| `ESP32-S3-MINI-1.step` | ESP32-S3-MINI-1 module (the boards use KiCad's `RF_Module:ESP32-S2-MINI-1` footprint: same land pattern) | [espressif/kicad-libraries](https://github.com/espressif/kicad-libraries) `3dmodels/espressif.3dshapes/ESP32-S3-MINI-1.STEP`, commit `dd76561812ab300351234ba6e0ec1295641796f0` (2026-07-28) | CC-BY-SA 4.0 with the KiCad libraries' exception (designs using it are not adapted material) |
| `WS2812B-2020.step` | Worldsemi WS2812B-2020 | drawn here, `tools/make_step_models.py` (datasheet dimensions) | this repository's |
| `easyeda/<LCSC>.step` | parts with no free model (JST PH SMD side entry, Kingbright KPA-3010, XKB TS-1187A, …) | LCSC / EasyEDA, fetched by `tools/fetch_pcb_models.py` | not redistributed: **git-ignored**, fetched on demand (the `.json` beside each file records its source) |

The model for the ESP32-S3-MINI-1 sits at offset (−7.7, −10.25, 0) mm on the KiCad footprint:
Espressif's footprint puts the module's bottom-left corner at (−7.7, 7.7) with its pads 2.55 mm
higher than KiCad's.

The EasyEDA models (`python tools/fetch_pcb_models.py`) are placed by their own pins and nails on
the pads of KiCad's footprints, and checked against the footprints' fab outlines:

| LCSC | Part (catalog key) | Offset (mm) | Rotation (°) | Note |
|---|---|---|---|---|
| C265405 | JST S6B-PH-SM4-TB (`ph6`) | 0, −2.9, 0 | 0, 0, 0 | nails on the MP pads, body −3.15…4.55 (fab −3.2…4.4) |
| C295747 | JST S2B-PH-SM4-TB (`ph2`) | 1.0, −2.9, 0 | 0, 0, 0 | the model is 1 mm off-centre in x |
| C318884 | XKB TS-1187A (`button`) | 0, 0, 0 | 0, 0, 0 | |
| C431540 | Shouhan MSK12C02 (`slide`) | 0, 0.1, 0 | 0, 0, 180 | pins 1-2-3 on KiCad's pads, lever towards +y |
| C598310 | Kingbright KPA-3010 (`led_side_g`, `led_side_r`) | 0, −0.5, 0 | −90, 0, 0 | the model lies on its back (KiCad turns a model the other way round: −90 stands it up); body on y 0…1 like the footprint |

No model anywhere for the WS2812B-2020 (`rgb`): `WS2812B-2020.step` (in the repo, our own, same licence as the
repo) is drawn by `tools/make_step_models.py` from the datasheet's 2.0 × 2.0 × 0.84 mm, white body, window on top.

All of them were checked on one test board, rendered by kicad-cli (each footprint with its model, the PH
connector also at 270°, as on the boards' edges).

**Coverage.**  `tools/kicad.sh <board> --fab` writes `electronics/<board>/build/<board>-3d.json`: per
footprint, whether the export gives it a body.  `tools/pcb_glb.py` adds a stand-in (real outline
dimensions, `STANDINS`) for each part still without one, and prints any it can't cover.
`python tools/pcb_glb.py --check` exits 1 if a placed part has no body at all;
`--strict` makes the GLB conversion fail the same way.
