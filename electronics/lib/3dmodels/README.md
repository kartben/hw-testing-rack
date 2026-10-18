# 3D models

Models that KiCad's own 3D library lacks, for the boards' STEP / GLB exports, the KiCad renders and
the web viewer.  `electronics/tools/catalog.py` (`Cat.model`) attaches one to a part: its file here,
and its offset and rotation on the part's KiCad footprint.  `pcbgen.set_model()` writes it into the
board with a project-relative path (`${KIPRJMOD}/../lib/3dmodels/…`), so it resolves on any machine
and in CI.

| File | Part | Source | Licence |
|---|---|---|---|
| `ESP32-S3-MINI-1.step` | ESP32-S3-MINI-1 module (the boards use KiCad's `RF_Module:ESP32-S2-MINI-1` footprint: same land pattern) | [espressif/kicad-libraries](https://github.com/espressif/kicad-libraries) `3dmodels/espressif.3dshapes/ESP32-S3-MINI-1.STEP`, commit `dd76561812ab300351234ba6e0ec1295641796f0` (2026-07-28) | CC-BY-SA 4.0 with the KiCad libraries' exception (designs using it are not adapted material) |
| `easyeda/<LCSC>.step` | parts with no free model (JST PH SMD side entry, Kingbright KPA-3010, XKB TS-1187A, …) | LCSC / EasyEDA, fetched by `tools/fetch_pcb_models.py` | not redistributed: **git-ignored**, fetched on demand (the `.json` beside each file records its source) |

The model for the ESP32-S3-MINI-1 sits at offset (−7.7, −10.25, 0) mm on the KiCad footprint:
Espressif's footprint puts the module's bottom-left corner at (−7.7, 7.7) with its pads 2.55 mm
higher than KiCad's.

**Coverage.**  `tools/kicad.sh <board> --fab` writes `electronics/<board>/build/<board>-3d.json`: per
footprint, whether the export gives it a body.  `tools/pcb_glb.py` adds a stand-in (real outline
dimensions, `STANDINS`) for each part still without one, and prints any it can't cover.
`python tools/pcb_glb.py --check` exits 1 if a placed part has no body at all;
`--strict` makes the GLB conversion fail the same way.
