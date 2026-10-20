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

ESP32-S3-WROOM-1_NoEPVias: the stock ESP32-S3-WROOM-1 without the 0.2 mm thermal vias in its exposed
pad (the bay node's U3).
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


def wroom_no_ep_vias() -> pcbnew.FOOTPRINT:
    """The stock ESP32-S3-WROOM-1 without the 0.2 mm thermal vias in its exposed pad (below the 0.3 mm
    minimum hole the boards keep for JLC's standard price, and open vias wick the pad's solder away):
    the bay node puts the pad on a top-side GND island stitched to In1 around it instead."""
    name = "ESP32-S3-WROOM-1_NoEPVias"
    fp = pcbnew.FootprintLoad(str(STOCK / "RF_Module.pretty"), "ESP32-S3-WROOM-1")
    for pad in list(fp.Pads()):
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and pad.GetNumber() == "41":
            fp.Remove(pad)
    fp.SetFPID(pcbnew.LIB_ID("bench", name))
    fp.SetValue(name)
    fp.SetLibDescription("ESP32-S3-WROOM-1 as RF_Module:ESP32-S3-WROOM-1, without the thermal vias in the exposed "
                         "pad (pad 41): stitch the pad's copper island around it instead")
    return fp


def header_2x6_smd_tight() -> pcbnew.FOOTPRINT:
    """The stock 2 × 6 SMD pin header, wider pads, its courtyard drawn round the pads (±4.35 mm across the rows)
    instead of KiCad's ±5.92 mm: the DATA ×4 v2's four headers sit in a row 18 mm apart with their
    translators right in front of them.  The lead span of the part (hanxia HX PZ2.54-2x6P TP, 7.5 mm)
    lands inside the pads."""
    name = "PinHeader_2x06_P2.54mm_Vertical_SMD_Tight"
    fp = pcbnew.FootprintLoad(str(STOCK / "Connector_PinHeader_2.54mm.pretty"), "PinHeader_2x06_P2.54mm_Vertical_SMD")
    # hand-soldered and plugged often: pads 1.3 mm wide instead of 1.0 (30 % more copper to hold the pin,
    # 1.24 mm between neighbours), as long as the stock ones
    for pad in fp.Pads():
        pad.SetSize(pcbnew.VECTOR2I(pad.GetSize().x, MM(1.3)))
    for item in list(fp.GraphicalItems()):
        if item.GetLayer() == pcbnew.F_CrtYd:
            fp.Remove(item)
    rect = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_RECT)
    rect.SetLayer(pcbnew.F_CrtYd)
    rect.SetWidth(MM(0.05))
    rect.SetStart(pcbnew.VECTOR2I(MM(-4.35), MM(-7.87)))
    rect.SetEnd(pcbnew.VECTOR2I(MM(4.35), MM(7.87)))
    fp.Add(rect)
    fp.SetFPID(pcbnew.LIB_ID("bench", name))
    fp.SetValue(name)
    fp.SetLibDescription("Pin header 2 × 6, 2.54 mm, SMD, as Connector_PinHeader_2.54mm:PinHeader_2x06_P2.54mm_Vertical_SMD "
                         "with a courtyard round the pads only")
    return fp


MAKERS = {"R_1206_3216Metric_Kelvin": kelvin_1206, "ESP32-S3-WROOM-1_NoEPVias": wroom_no_ep_vias,
          "PinHeader_2x06_P2.54mm_Vertical_SMD_Tight": header_2x6_smd_tight}


def main():
    """`footprints.py [name ...]`: the named footprints, or all of them.  Each one in its own process:
    KiCad's SWIG proxies get lost once a few loaded footprints have been alive (the third load fails)."""
    import subprocess
    import sys
    OUT.mkdir(parents=True, exist_ok=True)
    names = sys.argv[1:] or list(MAKERS)
    if len(names) > 1:
        for name in names:
            subprocess.run([sys.executable, __file__, name], check=True)
        return
    pcbnew.PCB_IO_KICAD_SEXPR().FootprintSave(OUT.as_posix(), MAKERS[names[0]]())
    print("wrote", OUT / f"{names[0]}.kicad_mod")


if __name__ == "__main__":
    main()
