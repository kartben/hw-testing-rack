# Licences and credits

BitBunk's hardware design files are under the CERN Open Hardware Licence version 2, permissive variant. Its
software is under the Apache License 2.0. The 3D models of development boards in the viewer belong to their
makers.

| Files | Licence |
|---|---|
| Hardware design files: `mechanical/`, `electronics/` except `electronics/tools/`, `config/`, `render/`, and the generated manufacturing files | CERN-OHL-P-2.0 |
| Software: `tools/`, `electronics/tools/`, `site/` (the viewer's code), `firmware/` | Apache-2.0 |

The repository's SPDX identifier is `CERN-OHL-P-2.0 AND Apache-2.0`. The licence texts are linked from
[LICENSE](../../LICENSE).

## The logic analyzer's firmware

The co-processor of a DATA ×4 runs the [LogicAnalyzer](https://github.com/gusmanb/logicanalyzer) firmware by
gusmanb. The firmware is under the GPL-3.0. BitBunk does not build or ship it: you build it yourself from
gusmanb's sources, as an image that runs from RAM ([Logic analyzer](../use/logic-analyzer.md)).

The [analyzer page](/analyzer/) and the analyzer card of the bay's page are under Apache-2.0. They only talk
to the firmware through its protocol.

## 3D models of the development boards

The viewer draws a board with its maker's 3D model where the model's licence allows it. Every other board is
a plain stand-in. The viewer's copies are in `site/assets/boards/`, and each bay's panel in the viewer names
the model of its board.

| Board | Model | Licence |
|---|---|---|
| Arduino UNO R4 | UNO R4 WiFi model © Arduino S.r.l., recoloured | CC BY-SA 4.0 |
| Arduino GIGA R1 WiFi with the GIGA Display Shield | © Arduino S.r.l., stacked and recoloured | CC BY-SA 4.0 |
| Arduino Nano Matter | © Arduino S.r.l., recoloured | CC BY-SA 4.0 |
| ST NUCLEO-64 | NUCLEO-G474RE (MB1367) model © STMicroelectronics | ST's Open Platform License Agreement |
| ST NUCLEO-144 | NUCLEO-U575ZI-Q (MB1549) model © STMicroelectronics | ST's Open Platform License Agreement |
| Raspberry Pi Pico 2 | © Raspberry Pi Ltd | MIT |
| Seeed Studio XIAO | XIAO ESP32S3 model © Seeed Studio | CC BY-SA 4.0 |
| BeagleBoard.org BeaglePlay | © Seeed Technology Co., Ltd and BeagleBoard.org Foundation, recoloured | CC BY 4.0 |
| Seeed Wio Terminal | © Seeed Studio, recoloured | Apache-2.0 |

Source: the `model` › `credit` field of each board in
[mechanical/boards/boards.yaml](../../mechanical/boards/boards.yaml). The XIAO's model carries no licence of
its own: it is published under the CC BY-SA 4.0 of the Seeed wiki that links to it.

The renders on this site also show the nRF52840 DK and the nRF54L15 DK. Their models are made from Nordic
Semiconductor's hardware files, © Nordic Semiconductor ASA. The files of the nRF52840 DK are under Nordic's
5-clause licence.

## Code, fonts and textures from elsewhere

| What | Where | Licence |
|---|---|---|
| xterm.js 6.0.0 and its fit add-on 0.11.0, the bay page's console | [firmware/common/web/vendor/xterm](../../firmware/common/web/vendor/xterm/README.md), served by the node with its licence at `/xterm-LICENSE.txt` | MIT |
| LVGL and its music and widgets demos, on the screens in the viewer | `site/assets/lvgl/lvgl-demo.wasm`, built by `tools/lvgl_wasm/build.sh` | MIT |
| Archivo, IBM Plex Sans and IBM Plex Mono, the fonts of this site | `docs/_static/fonts/`, from the Fontsource packages | SIL Open Font License 1.1 |
| Poly Haven's "Small Empty Room 1", the viewer's lighting | `site/assets/env/`, reduced to 512 × 256 | CC0 |
| Poly Haven's oak and plaster textures, for the renders | fetched by `tools/fetch_render_assets.py`, not in the repository | CC0 |

The viewer loads three.js 0.170.0 from jsDelivr when it opens.
