#!/usr/bin/env python3
"""Simple STEP models, from datasheet dimensions, for parts nobody publishes a model of.

    python tools/make_step_models.py        # needs FreeCAD's freecadcmd (FREECADCMD=… if not found)

FreeCAD builds the solids; this script then adds AP214 colours (STYLED_ITEM / COLOUR_RGB, which
KiCad's STEP reader shows), as FreeCAD's console mode exports none.  Output: electronics/lib/3dmodels.

* WS2812B-2020.step: Worldsemi WS2812B-2020, 2.0 × 2.0 × 0.84 mm, white body, a 1.5 × 1.5 mm
  window on top.  Origin at the body's centre, on the board: it sits on KiCad's
  LED_WS2812B-2020_PLCC4_2.0x2.0mm footprint without an offset.
* QFN-80_10x10x0.85mm, QFN-64_9x9x0.9mm, DHVQFN-20_2.5x4.5x0.85mm: the leadless packages
  KiCad's 3D library has no model for (RP2354B, USB2517I, LSF0108 RKS): a black
  body at the datasheet's size and a pin-1 dot at the footprints' pin 1 corner (KiCad −x, −y).  Origin at
  the body's centre, on the board.
"""

from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "electronics" / "lib" / "3dmodels"

# name → (FreeCAD solids script body, [colour per solid in creation order])
MODELS = {
    "WS2812B-2020": ("""
body = Part.makeBox(2.0, 2.0, 0.84, App.Vector(-1.0, -1.0, 0)).cut(Part.makeBox(1.5, 1.5, 0.2, App.Vector(-0.75, -0.75, 0.64)))
window = Part.makeBox(1.5, 1.5, 0.19, App.Vector(-0.75, -0.75, 0.64))
solids = [body, window]
""", [(0.93, 0.93, 0.91), (0.86, 0.88, 0.82)]),
}
# leadless ICs: body w × l × h (KiCad x × y), pin 1 at KiCad (−x, −y), i.e. STEP (−x, +y)
for _name, (_w, _l, _h) in {"QFN-80_10x10x0.85mm": (10.0, 10.0, 0.85), "QFN-64_9x9x0.9mm": (9.0, 9.0, 0.9),
                            "DHVQFN-20_2.5x4.5x0.85mm": (2.5, 4.5, 0.85)}.items():
    _r = max(0.15, min(_w, _l) * 0.06)
    _d = 2 * _r + 0.25
    MODELS[_name] = (f"""
body = Part.makeBox({_w}, {_l}, {_h}, App.Vector({-_w / 2}, {-_l / 2}, 0))
dot = Part.makeCylinder({_r}, 0.02, App.Vector({-_w / 2 + _d}, {_l / 2 - _d}, {_h}))
solids = [body, dot]
""", [(0.13, 0.13, 0.14), (0.62, 0.62, 0.62)])

FC_SCRIPT = """
import FreeCAD as App, Part, Import
{body}
doc = App.newDocument("m")
objs = []
for i, s in enumerate(solids):
    o = doc.addObject("Part::Feature", "s%d" % i)
    o.Shape = s
    objs.append(o)
doc.recompute()
Import.export(objs, r"{out}")
"""


def freecadcmd() -> str:
    exe = os.environ.get("FREECADCMD") or shutil.which("freecadcmd") or shutil.which("FreeCADCmd")
    if not exe:
        found = sorted(glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Programs\FreeCAD*\bin\freecadcmd.exe"))
                       + glob.glob(r"C:\Program Files\FreeCAD*\bin\freecadcmd.exe"))
        exe = found[-1] if found else None
    if not exe:
        sys.exit("freecadcmd not found: set FREECADCMD")
    return exe


def add_colours(text: str, colours: list) -> str:
    """Style each MANIFOLD_SOLID_BREP (in file order) with a colour, the way OCC reads it."""
    solids = re.findall(r"^#(\d+)\s*=\s*MANIFOLD_SOLID_BREP", text, re.M)
    ctx = re.search(r"^#(\d+)\s*=\s*\(\s*GEOMETRIC_REPRESENTATION_CONTEXT", text, re.M)
    if len(solids) != len(colours) or ctx is None:
        raise SystemExit(f"unexpected STEP: {len(solids)} solids, context {'found' if ctx else 'missing'}")
    n = max(int(i) for i in re.findall(r"^#(\d+)\s*=", text, re.M)) + 1
    lines, styled = [], []
    for sid, (r, g, b) in zip(solids, colours):
        c, fac, fa, sfa, ss, su, psa, si = range(n, n + 8)
        n += 8
        lines += [f"#{c} = COLOUR_RGB('',{r},{g},{b});",
                  f"#{fac} = FILL_AREA_STYLE_COLOUR('',#{c});",
                  f"#{fa} = FILL_AREA_STYLE('',(#{fac}));",
                  f"#{sfa} = SURFACE_STYLE_FILL_AREA(#{fa});",
                  f"#{ss} = SURFACE_SIDE_STYLE('',(#{sfa}));",
                  f"#{su} = SURFACE_STYLE_USAGE(.BOTH.,#{ss});",
                  f"#{psa} = PRESENTATION_STYLE_ASSIGNMENT((#{su}));",
                  f"#{si} = STYLED_ITEM('color',(#{psa}),#{sid});"]
        styled.append(f"#{si}")
    lines.append(f"#{n} = MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('',({','.join(styled)}),#{ctx.group(1)});")
    head, sep, tail = text.rpartition("ENDSEC;")      # the DATA section's end
    return head + "\n".join(lines) + "\n" + sep + tail


def main() -> int:
    fc = freecadcmd()
    for name, (body, colours) in MODELS.items():
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / f"{name}.step"
            script = Path(tmp) / "make.py"
            script.write_text(FC_SCRIPT.format(body=body, out=str(raw)), encoding="utf-8")
            subprocess.run([fc, str(script)], check=True, capture_output=True)
            text = add_colours(raw.read_text(encoding="utf-8"), colours)
        dst = OUT / f"{name}.step"
        dst.write_text(text, encoding="utf-8", newline="\n")
        print("wrote", dst.relative_to(REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
