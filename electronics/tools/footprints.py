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


def usb_c_hro_31d06() -> pcbnew.FOOTPRINT:
    """HRO TYPE-C-31-D-06 (LCSC C2689964), a vertical (top-mount) USB 2.0 receptacle: its mouth points away
    from the board.  Built from JLC's own land (EasyEDA "USB-C-SMD_TYPE-C-31-D-06", 2026-10-20): 16 pads
    0.3 × 0.9 mm at 0.5 mm in two rows 1.7 mm apart (A at −y, B at +y, each row's GND at its ends), four
    plated shell legs (Ø0.6 mm) and two locating pegs (Ø0.52 / Ø0.72 mm, unplated).  Pin numbers as
    Connector:USB_C_Receptacle_USB2.0_16P, the shell SH."""
    name = "USB_C_Receptacle_HRO_TYPE-C-31-D-06_Vertical"
    fp = pcbnew.FOOTPRINT(None)
    pins = {"A1": -2.75, "A4": -1.25, "A5": -0.75, "A6": -0.25, "A7": 0.25, "A8": 0.75, "A9": 1.25, "A12": 2.75,
            "B1": 2.75, "B4": 1.25, "B5": 0.75, "B6": 0.25, "B7": -0.25, "B8": -0.75, "B9": -1.25, "B12": -2.75}
    for num, x in pins.items():
        pad = pcbnew.PAD(fp)
        pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
        pad.SetShape(pcbnew.F_Cu, pcbnew.PAD_SHAPE_RECT)
        pad.SetSize(pcbnew.F_Cu, pcbnew.VECTOR2I(MM(0.3), MM(0.9)))
        pad.SetLayerSet(pcbnew.PAD.SMDMask())
        pad.SetNumber(num)
        pad.SetFPRelativePosition(pcbnew.VECTOR2I(MM(x), MM(-0.85 if num[0] == "A" else 0.85)))
        fp.Add(pad)
    for x, y in ((2.4, 2.15), (2.4, -2.15), (-2.4, -2.15), (-2.4, 2.15)):
        pad = pcbnew.PAD(fp)
        pad.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
        pad.SetShape(pcbnew.F_Cu, pcbnew.PAD_SHAPE_OVAL)
        pad.SetSize(pcbnew.F_Cu, pcbnew.VECTOR2I(MM(1.35), MM(1.1)))
        pad.SetDrillSize(pcbnew.VECTOR2I(MM(0.6), MM(0.6)))
        pad.SetLayerSet(pcbnew.PAD.PTHMask())
        pad.SetNumber("SH")
        pad.SetFPRelativePosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        fp.Add(pad)
    for x, d in ((-3.75, 0.52), (3.75, 0.72)):
        pad = pcbnew.PAD(fp)
        pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
        pad.SetShape(pcbnew.F_Cu, pcbnew.PAD_SHAPE_CIRCLE)
        pad.SetSize(pcbnew.F_Cu, pcbnew.VECTOR2I(MM(d), MM(d)))
        pad.SetDrillSize(pcbnew.VECTOR2I(MM(d), MM(d)))
        pad.SetLayerSet(pcbnew.PAD.UnplatedHoleMask())
        pad.SetFPRelativePosition(pcbnew.VECTOR2I(MM(x), 0))
        fp.Add(pad)
    for layer, w, hw, hh in ((pcbnew.F_CrtYd, 0.05, 4.75, 3.0), (pcbnew.F_Fab, 0.1, 4.47, 1.63)):
        rect = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_RECT)
        rect.SetLayer(layer)
        rect.SetWidth(MM(w))
        rect.SetStart(pcbnew.VECTOR2I(MM(-hw), MM(-hh)))
        rect.SetEnd(pcbnew.VECTOR2I(MM(hw), MM(hh)))
        fp.Add(rect)
    for y in (-2.95, 2.95):                     # silkscreen: the long sides, clear of the legs' pads
        line = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_SEGMENT)
        line.SetLayer(pcbnew.F_SilkS)
        line.SetWidth(MM(0.12))
        line.SetStart(pcbnew.VECTOR2I(MM(-1.5), MM(y)))
        line.SetEnd(pcbnew.VECTOR2I(MM(1.5), MM(y)))
        fp.Add(line)
    fp.SetAttributes(pcbnew.FP_SMD)
    fp.SetFPID(pcbnew.LIB_ID("bench", name))
    fp.Value().SetText(name)
    fp.Reference().SetText("REF**")
    fp.SetLibDescription("USB-C receptacle, USB 2.0, 16 pins, vertical (top mount, mouth away from the board): HRO "
                         "TYPE-C-31-D-06 (LCSC C2689964), land from JLC's EasyEDA footprint")
    fp.SetKeywords("usb c type-c receptacle vertical top mount hro 16p")
    return fp


MAKERS = {"R_1206_3216Metric_Kelvin": kelvin_1206, "ESP32-S3-WROOM-1_NoEPVias": wroom_no_ep_vias,
          "PinHeader_2x06_P2.54mm_Vertical_SMD_Tight": header_2x6_smd_tight,
          "USB_C_Receptacle_HRO_TYPE-C-31-D-06_Vertical": usb_c_hro_31d06}


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
