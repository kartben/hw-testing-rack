# Licences and credits

BitBunk's hardware design files are under the CERN Open Hardware Licence version 2, permissive
(CERN-OHL-P-2.0), and its software under the Apache License 2.0. The 3D models of development boards that the
viewer shows are their makers', under their makers' licences.

| Files | Licence |
|---|---|
| Hardware design files: `mechanical/`, `electronics/` but `electronics/tools/`, `config/`, `render/`, and the generated manufacturing outputs | CERN-OHL-P-2.0 |
| Software: `tools/`, `electronics/tools/`, `site/` (the viewer's code), `firmware/` | Apache-2.0 |

The repository's SPDX identifier is `CERN-OHL-P-2.0 AND Apache-2.0`; the texts are linked from
[LICENSE](../../LICENSE). The LICENSE file names no licence for the pages under `docs/`.

## The logic analyzer's firmware

The co-processor of a DATA ×4 runs gusmanb's [LogicAnalyzer](https://github.com/gusmanb/logicanalyzer)
firmware, its stock sources built as a RAM image. It is under the GPL-3.0, and the project neither builds nor
ships it: where it comes from and how a node loads it is on [Logic analyzer](../use/logic-analyzer.md). The
analyzer page at [/analyzer/](/analyzer/) and the bay page's analyzer card are Apache-2.0: they only speak the
firmware's protocol.

## 3D models of the development boards

The viewer draws a board with its maker's model only where that model's licence lets the repository publish it;
any other board is a plain stand-in. The models are not kept as sources in the repository: the viewer's copies
are under `site/assets/boards/`, and each bay's panel in the viewer names the model of its board. The XIAO's
model carries no licence of its own and is published under the CC BY-SA 4.0 of the Seeed wiki that links it. The
two Nordic DKs have models for the renders only. How the models are fetched and fitted:
[boards-3d.md](../boards-3d.md).

```{include} ../boards-3d.md
:start-after: <!-- site:credits -->
:end-before: <!-- /site:credits -->
```

## Code, fonts and textures from elsewhere

| What | Where | Licence |
|---|---|---|
| xterm.js 6.0.0 and its fit add-on 0.11.0, the bay page's web console | [firmware/common/web/vendor/xterm](../../firmware/common/web/vendor/xterm/README.md), served from the node's flash with its licence at `/xterm-LICENSE.txt` | MIT |
| LVGL, with its music and widgets demos, built for the screens in the viewer | `site/assets/lvgl/lvgl-demo.wasm`, built by `tools/lvgl_wasm/build.sh` | MIT |
| Archivo, IBM Plex Sans and IBM Plex Mono, the fonts of this site | `docs/_static/fonts/`, from the Fontsource packages | SIL Open Font License 1.1 |
| Poly Haven's "Small Empty Room 1", the viewer's light | `site/assets/env/`, cut to 512 × 256 | CC0 |
| Poly Haven's oak and plaster textures, for the photo renders | fetched by `tools/fetch_render_assets.py`, not committed | CC0 |

The viewer loads three.js 0.170.0 from jsDelivr when it opens; it is not in the repository.
