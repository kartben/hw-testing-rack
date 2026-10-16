#!/usr/bin/env python3
"""Project footprints derived from stock KiCad ones (run with KiCad's Python, e.g. inside
tools/kicad.sh's image or a local KiCad 10 install):

    python electronics/tools/footprints.py        # → electronics/lib/bench.pretty/*.kicad_mod

R_1206_3216Metric_Kelvin: the stock 1206 resistor plus a sense pad on the inner edge of each
terminal, for a 2-terminal current shunt read by an amplifier (the bay node's INA226).  The sense
pads (2, 3) are tied to the current pads (1, 4) by net-tie pad groups, so the sense nets leave from
where the shunt's own terminations end instead of somewhere along the load current's copper.  They
are copper only (tented, no paste) under the resistor body.  Pin numbers follow Device:R_Shunt:
1/4 current, 2/3 sense.
"""

from __future__ import annotations

import os
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "lib" / "bench.pretty"
STOCK = Path(os.environ.get("KICAD_FOOTPRINT_DIR", "/usr/share/kicad/footprints"))
if not STOCK.exists():
    STOCK = Path("C:/Program Files/KiCad/10.0/share/kicad/footprints")

MM = pcbnew.FromMM


def kelvin_1206() -> pcbnew.FOOTPRINT:
    name = "R_1206_3216Metric_Kelvin"
    fp = pcbnew.FootprintLoad(str(STOCK / "Resistor_SMD.pretty"), "R_1206_3216Metric")
    for pad in fp.Pads():
        if pad.GetNumber() == "2":
            pad.SetNumber("4")
    # the stock pads end 0.9 mm from the centre; each sense pad overlaps that inner edge by 0.1 mm
    # and keeps its own centre 0.3 mm inside, so a 0.2 mm track can leave it with clearance
    for num, x in (("2", -0.6), ("3", 0.6)):
        pad = pcbnew.PAD(fp)
        pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
        pad.SetShape(pcbnew.F_Cu, pcbnew.PAD_SHAPE_RECT)
        pad.SetSize(pcbnew.F_Cu, pcbnew.VECTOR2I(MM(0.8), MM(0.5)))
        ls = pcbnew.LSET()
        ls.AddLayer(pcbnew.F_Cu)
        pad.SetLayerSet(ls)
        pad.SetNumber(num)
        pad.SetFPRelativePosition(pcbnew.VECTOR2I(MM(x), 0))
        fp.Add(pad)
    fp.AddNetTiePadGroup("1,2")
    fp.AddNetTiePadGroup("3,4")
    fp.SetFPID(pcbnew.LIB_ID("bench", name))
    fp.Value().SetText(name)
    fp.SetLibDescription("Resistor SMD 1206 (3216 Metric) for a 2-terminal current shunt, with Kelvin sense pads "
                         "on the inner edge of each terminal (net-tie pad groups 1-2 and 3-4); pads as "
                         "R_1206_3216Metric, pin numbers as Device:R_Shunt")
    fp.SetKeywords("resistor shunt kelvin 4-wire sense net-tie")
    return fp


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for fp in (kelvin_1206(),):
        pcbnew.PCB_IO_KICAD_SEXPR().FootprintSave(OUT.as_posix(), fp)
        print("wrote", OUT / f"{fp.GetFPID().GetLibItemName()}.kicad_mod")


if __name__ == "__main__":
    main()
