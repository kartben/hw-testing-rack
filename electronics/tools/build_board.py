#!/usr/bin/env python3
"""Generate, check and export one board (runs inside KiCad's Python).

    python3 electronics/tools/build_board.py bay-node            # schematic + placed PCB + ERC/DRC
    python3 electronics/tools/build_board.py bay-node --route    # … + Freerouting autoroute
    python3 electronics/tools/build_board.py bay-node --fab      # … + gerbers, CPL, BOM, PDF, renders, GLB/STEP

Use tools/kicad.sh to run it in the official kicad/kicad Docker image.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
REPO = HERE.parents[1]

from catalog import HAND_SOLDER_LCSC  # noqa: E402
from fab_dates import undate  # noqa: E402
from eda import generate_schematic  # noqa: E402


def load_design(name: str):
    path = REPO / "electronics" / name / "design.py"
    spec = importlib.util.spec_from_file_location(f"design_{name.replace('-', '_')}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(cmd, **kw):
    print("$", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], **kw)


def erc(outdir: Path, name: str) -> dict:
    rpt = outdir / "build" / "erc.json"
    rpt.parent.mkdir(parents=True, exist_ok=True)
    run(["kicad-cli", "sch", "erc", "--format", "json", "--severity-error", "--severity-warning",
         "-o", rpt, outdir / f"{name}.kicad_sch"], check=False, capture_output=True)
    data = json.loads(rpt.read_text())
    out = {"errors": 0, "warnings": 0, "items": []}
    for sheet in data.get("sheets", []):
        for v in sheet.get("violations", []):
            sev = v.get("severity")
            out["errors" if sev == "error" else "warnings"] += 1
            out["items"].append(f"[{sev}] {v.get('type')}: {v.get('description')} @ {sheet.get('path')} "
                                f"{[i.get('description') for i in v.get('items', [])]}")
    return out


def drc(outdir: Path, name: str) -> dict:
    rpt = outdir / "build" / "drc.json"
    run(["kicad-cli", "pcb", "drc", "--format", "json", "--schematic-parity", "--severity-error",
         "--severity-warning", "--refill-zones", "--save-board", "-o", rpt, outdir / f"{name}.kicad_pcb"],
        check=False, capture_output=True)
    data = json.loads(rpt.read_text())
    out = {"violations": {}, "unconnected": len(data.get("unconnected_items", [])),
           "parity": len(data.get("schematic_parity", [])), "items": []}
    for v in data.get("violations", []):
        out["violations"][v["type"]] = out["violations"].get(v["type"], 0) + 1
        out["items"].append(f"[{v['severity']}] {v['type']}: {v['description']} "
                            f"{[i.get('description') for i in v.get('items', [])][:2]}")
    for v in data.get("schematic_parity", []):
        out["items"].append(f"[parity] {v['type']}: {v['description']} {[i.get('description') for i in v.get('items', [])][:2]}")
    return out


def drc_readonly(outdir: Path, name: str) -> dict:
    """DRC without touching the committed board (zones refilled in memory only)."""
    rpt = outdir / "build" / "drc.json"
    run(["kicad-cli", "pcb", "drc", "--format", "json", "--schematic-parity", "--severity-error",
         "--severity-warning", "--refill-zones", "-o", rpt, outdir / f"{name}.kicad_pcb"], check=False,
        capture_output=True)
    data = json.loads(rpt.read_text())
    out = {"violations": {}, "unconnected": len(data.get("unconnected_items", [])),
           "parity": len(data.get("schematic_parity", [])), "items": []}
    for v in data.get("violations", []):
        out["violations"][v["type"]] = out["violations"].get(v["type"], 0) + 1
        if v["severity"] == "error":
            out["items"].append(f"[{v['severity']}] {v['type']}: {v['description']}")
    return out


def bom_rows(b, dnp=frozenset()):
    """Group parts for JLCPCB (Comment, Designator, Footprint, LCSC) and a detailed BOM.  `dnp`: a variant's
    references left unfitted on top of the parts' own DNP; fitted and unfitted parts never share a line."""
    groups: dict[tuple, list] = {}
    for p in sorted(b.parts.values(), key=lambda p: (p.ref.rstrip("0123456789"), int("".join(c for c in p.ref if c.isdigit()) or 0))):
        if not p.in_bom or not p.on_board or p.ref.startswith("#"):
            continue
        k = (p.value, p.footprint, p.fields.get("LCSC", ""), p.fields.get("MPN", ""), p.dnp or p.ref in dnp)
        groups.setdefault(k, []).append(p)
    rows = []
    for (value, fp, lcsc, mpn, unfitted), parts in groups.items():
        p0 = parts[0]
        rows.append({
            "Designator": ",".join(p.ref for p in parts), "Qty": len(parts), "Value": value,
            "Footprint": fp.split(":")[1], "MPN": mpn, "Manufacturer": p0.fields.get("Manufacturer", ""),
            "LCSC": lcsc, "Description": p0.description, "DNP": "yes" if unfitted else "",
            "Alternative": p0.fields.get("Alternative", ""),
            "Assembly": "hand-solder, buy loose (LCSC)" if lcsc in HAND_SOLDER_LCSC else "",
        })
    return rows


def jlc_bom_rows(rows):
    """One line per LCSC part: JLC deselects lines that resolve to the same part ("Multiple lines in
    the BOM have been matched to the same part"), so e.g. J3 PC + J4 DUT become one line.  Parts
    soldered by hand stay out."""
    groups: dict[str, list] = {}
    for r in rows:
        if not r["DNP"] and not r["Assembly"]:
            groups.setdefault(r["LCSC"] or f"{r['Value']}|{r['Footprint']}", []).append(r)
    out = []
    for rs in groups.values():
        fps = {r["Footprint"] for r in rs}
        if len(fps) > 1:
            raise SystemExit(f"LCSC {rs[0]['LCSC']} on different footprints {sorted(fps)}")
        values = list(dict.fromkeys(r["Value"] for r in rs))
        comment = values[0] if len(values) == 1 else (rs[0]["MPN"] or " / ".join(values))
        out.append([comment, ",".join(r["Designator"] for r in rs), rs[0]["Footprint"], rs[0]["LCSC"]])
    return out


# JLC places its own footprint for each LCSC part (the EasyEDA one) at the CPL point, turned by
# the CPL rotation.  Where that footprint's 0° or origin differs from KiCad's, correct it here:
# LCSC part -> (KiCad footprint it was checked against, extra rotation in degrees CCW, origin
# offset x, y in mm in the KiCad footprint's own axes, Y down).  The correction belongs to the LCSC
# listing, not the footprint name: C7519 and C55266 share SOT-23-6 but JLC draws them 90° apart.
# Derived on 2026-10-16 by fitting each part's EasyEDA pads onto the KiCad pads, pin by pin; "seen"
# marks the parts JLC's placement preview showed wrong before the fix.  Every entry still has to
# be confirmed in the preview: see "Placement corrections" in docs/electronics.md.  The through-hole
# connectors are hand-soldered now (catalog hand_solder), so they leave the CPL and their rows only
# matter if JLC ever places them again.
JLC_CPL_FIX = {
    "C173752": ("JST_PH_S2B-PH-K_1x02_P2.00mm_Horizontal", 180, 1.0, 0.0),    # bay J1 J2 J6 (seen; hand-soldered)
    "C6186": ("SOT-223-3_TabPin2", 180, 0.0, 0.0),                            # bay U2 (seen)
    "C165948": ("USB_C_Receptacle_HRO_TYPE-C-31-M-12", 0, 0.0, -1.57),        # bay J3 J4 until v0.4
    "C2913206": ("ESP32-S2-MINI-1", 0, 0.0, 2.55),                            # bay U3
    # bay SW3: on its pegs.  KiCad's footprint is Shouhan's land pattern (pads 1.95 mm from the peg holes);
    # JLC's has its pegs 0.55 mm from its origin and its pads drawn 0.13 mm further out.  The pegs go into
    # the 0.85 mm holes, so they set the point (pcba-review N1, 2026-10-19; −0.25 until then, from the pads)
    "C431540": ("SW_SPDT_Shouhan_MSK12C02", 0, 0.0, -0.55),
    "C45262770": ("TSOT-23-6", 270, 0.0, 0.0),                                # LMR51635: both boards' buck until 2026-10-23
    "C44991044": ("TSOT-23-6", 270, 0.0, 0.0),                                # bay U1, hub U2 (LMR51625: drawn as C45262770)
    "C11355": ("MSOP-10_3x3mm_P0.5mm", 270, 0.0, 0.0),                        # bay U5 U6
    "C49851": ("TSSOP-10_3x3mm_P0.5mm", 270, 0.0, 0.0),                       # bay U10
    "C7519": ("SOT-23-6", 270, 0.0, 0.0),                                     # bay U4 U8
    "C42459160": ("SSOP-10-1EP_3.9x4.9mm_P1mm_EP2.1x3.3mm", 270, 0.0, 0.0),   # hub U1 (CH224A), fitted pad by pad
    "C55266": ("SOT-23-6", 180, 0.0, 0.0),                                    # bay U9 until the TPS2553D
    "C521201": ("SOT-23-6", 270, 0.0, 0.0),                                   # bay U9 (TPS2553D: drawn as C7519, not C55266)
    "C10096": ("SOT-23-5", 180, 0.0, 0.0),                                    # bay U7
    "C8545": ("SOT-23", 180, 0.0, 0.0),                                       # bay Q2 Q3
    "C7503186": ("TO-252-2", 0, -1.89, 0.0),                                  # bay Q1, hub Q1
    # hub Q1 Q2 (IRF7842): JLC's SOIC-8 drawn as C3234095's (pin 1 bottom-left, rows horizontal)
    "C495809": ("SOIC-8_3.9x4.9mm_P1.27mm", 270, 0.0, 0.0),
    "C544399": ("HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm_Mask2.66x2.46mm", 270, 0.0, 0.0),  # hub U1–U5
    "C160315": ("JST_VH_B2P-VH_1x02_P3.96mm_Vertical", 0, 1.98, 0.0),         # hub J1 (hand-soldered)
    # rack bus parts, fitted on 2026-10-18 the same way
    "C265405": ("JST_PH_S6B-PH-SM4-TB_1x06-1MP_P2.00mm_Horizontal", 180, 0.0, 0.0),  # bay J1 J2 J5, hub row outputs
    "C7399456": ("SOIC-8_3.9x4.9mm_P1.27mm", 270, 0.0, 0.0),                  # bay U11, hub U6 (TCAN1462V)
    "C3234993": ("SOIC-8_3.9x4.9mm_P1.27mm", 270, 0.0, 0.0),                  # its alternates, same SOIC-8: TCAN1044AV
    "C3234095": ("SOIC-8_3.9x4.9mm_P1.27mm", 270, 0.0, 0.0),                  # and TJA1462AT
    "C75176": ("SOT-23", 180, 0.0, 0.0),                                      # bay D5, hub D9 (PESD2CAN)
    "C7420333": ("SOT-23", 180, 0.0, 0.0),                                    # bay D6 D7, hub POS clamps (BAT54S)
    "C5184243": ("USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal", 0, 0.0, -1.30),  # bay J3 J4, hub USB-C
    # the DATA lead's 5-pin PH pair, fitted on 2026-10-18 the same way
    "C265104": ("JST_PH_S5B-PH-SM4-TB_1x05-1MP_P2.00mm_Horizontal", 180, 0.0, 0.14),  # data port J2
    "C265085": ("JST_PH_B5B-PH-SM4-TB_1x05-1MP_P2.00mm_Vertical", 180, 0.0, -0.62),   # bay J7
    # the camera's parts, fitted the same way
    "C2913201": ("ESP32-S3-WROOM-1_NoEPVias", 0, 0.0, 3.63),                         # bay U3 (WROOM-1-N8R8)
    "C471518": ("JST_PH_B6B-PH-SM4-TB_1x06-1MP_P2.00mm_Vertical", 180, 0.0, -0.63),  # bay J5 (AUX)
    # the camera pod's (C265121, its S8B, needs none: fit 0°, −0.03 mm)
    "C2843876": ("LED_PLCC_2835", 0, 0.24, 0.0),                              # pod D1–D4
    "C41417363": ("PinHeader_1x06_P2.54mm_Vertical_SMD_Pin1Right", 270, 0.0, 0.0),  # pod J2
    "C495548": ("JST_PH_B8B-PH-SM4-TB_1x08-1MP_P2.00mm_Vertical", 0, 0.0, -0.63),    # bay J6
    "C20917": ("SOT-23", 180, 0.0, 0.0),                                      # bay Q4 (AO3400A)
    # the DATA ×4's parts, fitted on 2026-10-19 the same way (the crystal C15643 and the shunt C25334
    # fit as they are; the RESET/BOOT headers are hand-soldered)
    "C16251": ("QFN-36-1EP_6x6mm_P0.5mm_EP3.7x3.7mm", 270, 0.0, 0.0),        # x4 U1 (USB2514B)
    "C111738": ("SOT-23-6", 270, 0.0, 0.0),                                  # x4 U101–U401 (TPS2553-1: drawn as C7519, not C55266)
    "C51118": ("SOT-23-5", 270, 0.0, 0.0),                                   # hub U3, x4 U3 (AP2112K-3.3)
    # the hub's side-view LEDs, from pcba-review H2 (2026-10-19): JLC's KPA-3010 origin is the pads' centre,
    # KiCad's the body's.  Polarity: JLC's green (C598310) names its right pad A, its red (C4555382) marks
    # the same pad "+" (and the left one "−") in its silkscreen: both match KiCad's pads 2 = A, 1 = K
    "C598310": ("LED_Kingbright_KPA-3010_3x2x1mm", 0, 0.0, 0.825),           # hub D3 D8 D11–D14 (green)
    "C4555382": ("LED_Kingbright_KPA-3010_3x2x1mm", 0, 0.0, 0.825),          # hub D21–D24 (red)
    "C181499": ("VQFN-16-1EP_3x3mm_P0.5mm_EP1.45x1.45mm", 270, 0.0, 0.0),    # x4 U2 U6 (TCA6408A)
    # DATA ×4 v2's, fitted on 2026-10-20 the same way (bottom parts un-mirrored first).  RP2354B C39843328,
    # USB2517I C478081, ABM8 C20625731, the inductor C42411119 fit as they are; the LED C2297 too, by
    # function (JLC numbers its anode 1, KiCad its cathode)
    "C109471": ("LQFP-44_10x10mm_P0.8mm", 270, 0.0, 0.0),                    # x4 v2 U7 U8 (CH446Q)
    "C130008": ("DHVQFN-20-1EP_2.5x4.5mm_P0.5mm_EP1x3mm", 270, 0.0, 0.0),    # x4 v2 U107–U407 (LSF0108)
    "C20615800": ("DFN2510-10L_2.5x1.0mm_P0.5mm", 270, 0.0, 0.0),            # x4 v2 U4, U105… (H5VU25UC: its pins
                                                                             # along x, pin 1 on pin 1, 0.005 mm rms)
    "C206010": ("TSSOP-16_4.4x5mm_P0.65mm", 270, 0.0, 0.0),                  # x4 v2 U10 (TCA9534A)
    "C9839": ("SOT-23-5", 180, 0.0, 0.0),                                    # x4 v2 U9 (TPS60400)
    "C150716": ("SOT-223-3_TabPin2", 180, 0.0, 0.0),                         # x4 v2 U3 (AP2114H-3.3, drawn as C6186)
    # 4 × 0402 arrays: JLC's are drawn across (any of 90° / 270°: four equal resistors)
    "C25725": ("R_Array_Convex_4x0402", 90, 0.0, 0.0),                       # x4 v2 RN1–RN3, RN8 RN9 (10k)
    "C48442": ("R_Array_Convex_4x0402", 90, 0.0, 0.0),                       # x4 v2 RN101… (100)
    "C26075": ("R_Array_Convex_4x0402", 90, 0.0, 0.0),                       # x4 v2 RN6 RN7 (2.2k)
}


def jlc_cpl_row(row, lcsc: str):
    """KiCad pos row (anchor, Y up) -> JLC CPL row, with the JLC_CPL_FIX correction applied.

    Bottom side: JLC wants the position as seen from the top (the pos file's) and the rotation as seen
    from above the part, i.e. from below the board: 180° − KiCad's, plus the part's own correction
    (KiCad draws a bottom footprint at θ as its library footprint mirrored top-bottom, then turned θ)."""
    x, y, rot = row["PosX"], row["PosY"], float(row["Rot"])
    bottom = row["Side"] != "top"
    fp, drot, dx, dy = JLC_CPL_FIX.get(lcsc, (row["Package"], 0, 0.0, 0.0))
    if fp != row["Package"]:
        raise SystemExit(f"{row['Ref']}: JLC_CPL_FIX[{lcsc}] was checked on {fp}, not {row['Package']}")
    if dx or dy:
        a = math.radians(rot)
        # offset from footprint axes to board axes (KiCad, Y down; mirrored on the bottom), then to Y up
        s = -1 if bottom else 1
        x = f"{float(x) + dx * math.cos(a) + s * dy * math.sin(a):.6f}"
        y = f"{float(y) + dx * math.sin(a) - s * dy * math.cos(a):.6f}"
    r = ((180 - rot if bottom else rot) + drot) % 360
    return [row["Ref"], x + "mm", y + "mm", "Bottom" if bottom else "Top", f"{r - 360 if r > 180 else r:.6f}"]


def export_gerbers(pcb: Path, gerb: Path, zip_path: Path, n_layers: int) -> None:
    """Gerbers and drill files of a board (or a panel) into gerb/, zipped for JLC."""
    gerb.mkdir(parents=True, exist_ok=True)
    layers = "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"
    if n_layers > 2:
        layers = ",".join(["F.Cu"] + [f"In{i}.Cu" for i in range(1, n_layers - 1)] + ["B.Cu"]) + "," + layers.split(",", 2)[2]
    run(["kicad-cli", "pcb", "export", "gerbers", "--layers", layers, "--subtract-soldermask",
         "--use-drill-file-origin", "-o", str(gerb) + "/", pcb], check=True, capture_output=True)
    run(["kicad-cli", "pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th",
         "--generate-map", "--map-format", "gerberx2", "-o", str(gerb) + "/", pcb], check=True, capture_output=True)
    write_zip(zip_path, sorted(gerb.iterdir()))


def write_zip(zip_path: Path, files) -> None:
    """A zip that is the same bytes for the same files: no creation dates in them (fab_dates), members in name
    order, one fixed timestamp and mode, so a run that changes nothing leaves the committed zip as it was."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(files, key=lambda f: f.name):
            zi = zipfile.ZipInfo(f.name, date_time=(1980, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            z.writestr(zi, undate(f.name, f.read_bytes()))


JPEG_QUALITY = 85         # the doc renders: ≈ a third of the PNGs' size, silkscreen text still sharp


def render(pcb: Path, jpg: Path, *opts) -> None:
    """A kicad-cli 3D render as a JPEG on white (PNG renders were 2–4× bigger, and every regenerated one stays
    in the repository's history).  The PNG kicad-cli writes goes through the board's build/ folder."""
    tmp = jpg.parent.parent / "build" / f"{jpg.stem}-render.png"
    tmp.parent.mkdir(exist_ok=True)
    run(["kicad-cli", "pcb", "render", *opts, "--background", "transparent", "-o", tmp, pcb], check=False,
        capture_output=True)
    if not tmp.exists():
        return
    from PIL import Image
    im = Image.open(tmp).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    bg.convert("RGB").save(jpg, "JPEG", quality=JPEG_QUALITY, optimize=True)
    tmp.unlink()
    old = jpg.with_suffix(".png")           # the render's PNG from before 2026-10-23
    if old.exists():
        old.unlink()


def export_fab(outdir: Path, name: str, b):
    fab = outdir / "fab"
    # start clean, but keep the order panel's outputs (electronics/tools/panelize.py, run after this)
    if fab.exists():
        for f in fab.iterdir():
            if f.name.startswith(f"{name}-panel"):
                continue
            shutil.rmtree(f) if f.is_dir() else f.unlink()
    fab.mkdir(parents=True, exist_ok=True)
    pcb = outdir / f"{name}.kicad_pcb"
    sch = outdir / f"{name}.kicad_sch"
    export_gerbers(pcb, fab / "gerbers", fab / f"{name}-gerbers.zip", b.pcb.get("layers", 2))
    # pick & place (JLCPCB column names), corrected to JLC's own footprints
    raw = fab / "pos-raw.csv"
    run(["kicad-cli", "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both",
         "--exclude-dnp", "-o", raw, pcb], check=True, capture_output=True)
    lcsc = {p.ref: p.fields.get("LCSC", "") for p in b.parts.values()}
    fixed, cpl = [], []
    with raw.open() as fi:
        for row in csv.DictReader(fi):
            if row["Ref"].startswith(("H", "TP")) or lcsc.get(row["Ref"]) in HAND_SOLDER_LCSC:
                continue
            cpl.append(jlc_cpl_row(row, lcsc.get(row["Ref"], "")))
            if lcsc.get(row["Ref"]) in JLC_CPL_FIX:
                fixed.append(row["Ref"])
    raw.unlink()
    print("CPL: JLC footprint corrections on", " ".join(fixed))
    # the board as drawn, then each assembly variant of the same PCB (b.pcb["variants"]: name → {"dnp":
    # [references left unfitted]}), as <board>-<variant>-…: its own BOM and CPL, the same Gerbers
    for tag, dnp in [("", frozenset())] + [(f"-{v}", frozenset(spec["dnp"]))
                                           for v, spec in b.pcb.get("variants", {}).items()]:
        with (fab / f"{name}{tag}-cpl-jlcpcb.csv").open("w", newline="") as fo:
            w = csv.writer(fo)
            w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
            w.writerows(r for r in cpl if r[0] not in dnp)
        rows = bom_rows(b, dnp)
        with (fab / f"{name}{tag}-bom-jlcpcb.csv").open("w", newline="") as fo:
            w = csv.writer(fo)
            w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
            w.writerows(jlc_bom_rows(rows))
        with (outdir / f"{name}{tag}-bom.csv").open("w", newline="", encoding="utf-8") as fo:
            w = csv.DictWriter(fo, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        if tag:
            print(f"variant {tag[1:]}: {len(dnp)} parts not fitted, {sum(1 for r in cpl if r[0] not in dnp)} placed")
    # the project's own 3D models first: the renders below, the STEP and the GLB all need them
    import pcbgen
    print("3D: project models on", pcbgen.apply_models(pcb), "footprints")
    # documentation outputs
    docs = outdir / "docs"
    docs.mkdir(exist_ok=True)
    run(["kicad-cli", "sch", "export", "pdf", "-o", docs / f"{name}-schematic.pdf", sch], check=True,
        capture_output=True)
    run(["kicad-cli", "sch", "export", "svg", "-o", str(docs / "svg"), sch], check=False, capture_output=True)
    for side in ("top", "bottom"):
        render(pcb, docs / f"{name}-{side}.jpg", "--side", side, "--width", "1600", "--height", "1300", "--quality", "high")
    render(pcb, docs / f"{name}-iso.jpg", "--rotate", "-40,0,35", "--zoom", "0.85", "--width", "1600", "--height", "1200",
           "--quality", "high")
    run(["kicad-cli", "pcb", "export", "step", "--subst-models", "-f", "-o", fab / f"{name}.step", pcb], check=False,
        capture_output=True)
    # board body + component models only: the layer art goes to the viewer as a texture
    # (tools/pcb_glb.py), from the polygons export_art() writes.  The viewer shows the board as built: no DNP
    # parts (the STEP keeps them, the envelope a fit check needs if they are fitted later)
    run(["kicad-cli", "pcb", "export", "glb", "--subst-models", "--no-dnp", "-f", "-o", fab / f"{name}.glb", pcb],
        check=False, capture_output=True)
    export_art(outdir, name)
    export_3d_coverage(outdir, name)


# footprints that have no body by nature: nothing to model
NO_BODY = ("MountingHole:", "TestPoint:", "NetTie:", "Fiducial:", "Symbol:")
MODEL_DIR = Path(os.environ.get("KICAD10_3DMODEL_DIR", "/usr/share/kicad/3dmodels"))


# the LCSC / EasyEDA models tools/fetch_pcb_models.py fetches on demand (git-ignored)
EASYEDA_DIR = REPO / "electronics" / "lib" / "3dmodels" / "easyeda"


def resolve_model(fn: str, outdir: Path) -> Path | None:
    """The STEP / IGES file a footprint's (model …) path resolves to, the form KiCad's STEP and GLB
    exports use (--subst-models replaces a .wrl with the STEP of the same name); None if none exists."""
    env = {"KICAD10_3DMODEL_DIR": str(MODEL_DIR), "KICAD9_3DMODEL_DIR": str(MODEL_DIR),
           "KICAD8_3DMODEL_DIR": str(MODEL_DIR), "KICAD7_3DMODEL_DIR": str(MODEL_DIR),
           "KICAD6_3DMODEL_DIR": str(MODEL_DIR), "KIPRJMOD": str(outdir)}
    for k, v in env.items():
        fn = fn.replace("${" + k + "}", v)
    p = Path(fn) if Path(fn).is_absolute() else outdir / fn
    for cand in (p, p.with_suffix(".step"), p.with_suffix(".stp"), p.with_suffix(".STEP"), p.with_suffix(".igs")):
        if cand.suffix.lower() in (".step", ".stp", ".igs", ".iges") and cand.exists():
            return cand
    return None


def check_models(outdir: Path, name: str, allowed=()) -> dict:
    """Every footprint gets a body in the renders, the STEP and the viewer: each shown (model …) must
    resolve to a file (KiCad's 3D library, electronics/lib/3dmodels, or the EasyEDA cache), and a
    footprint with none must be allowed: no body by nature (NO_BODY, board-only) or listed in the
    board's b.pcb["no_model"] (references or footprint-id prefixes).  An EasyEDA model is only
    reported "not fetched" while its cache file is absent (tools/fetch_pcb_models.py fetches it)."""
    import pcbnew
    board = pcbnew.LoadBoard(str(outdir / f"{name}.kicad_pcb"))
    res = {"ok": 0, "no-body": 0, "not fetched": [], "problems": []}
    for fp in board.GetFootprints():
        ref, fpid = fp.GetReference(), fp.GetFPIDAsString()
        if fpid.startswith(NO_BODY) or fp.GetAttributes() & pcbnew.FP_BOARD_ONLY or                 ref in allowed or fpid.startswith(tuple(a for a in allowed if ":" in a)):
            res["no-body"] += 1
            continue
        models = [m.m_Filename for m in fp.Models() if m.m_Show]
        if not models:
            res["problems"].append(f"{ref} {fpid}: no 3D model")
            continue
        bad = [m for m in models if not resolve_model(m, outdir)]
        fetchable = [m for m in bad if "/easyeda/" in m and not (EASYEDA_DIR / Path(m).name).exists()]
        res["not fetched"] += [f"{ref} {Path(m).name}" for m in fetchable]
        res["problems"] += [f"{ref} {fpid}: {m} not found" for m in bad if m not in fetchable]
        res["ok"] += not bad
    print(f"3D models: {res['ok']} resolve, {res['no-body']} without a body by nature, "
          f"{len(res['not fetched'])} EasyEDA not fetched, {len(res['problems'])} problems")
    for it in res["problems"][:40]:
        print("  ", it)
    return res


def export_3d_coverage(outdir: Path, name: str) -> Path:
    """Which placed footprints KiCad's STEP / GLB export gives a body, and which it can't:
    build/<board>-3d.json, one entry per footprint: "model" (a STEP/IGES file it resolves, the
    form the GLB export uses; a .wrl is replaced by the STEP of the same name, --subst-models),
    "no-body" (holes, test pads, net ties), "dnp" (not fitted: left out of the GLB) or "missing" (no
    model, or a model file that isn't in KiCad's 3D library).  tools/pcb_glb.py adds stand-ins for the
    missing ones and fails on any it has none for."""
    import pcbnew
    board = pcbnew.LoadBoard(str(outdir / f"{name}.kicad_pcb"))
    resolve = lambda fn: resolve_model(fn, outdir)
    out = []
    for fp in board.GetFootprints():
        fpid = fp.GetFPIDAsString()
        side = "bottom" if fp.IsFlipped() else "top"
        models = [m for m in fp.Models() if m.m_Show]
        hit = next((r for r in (resolve(m.m_Filename) for m in models) if r), None)
        if fpid.startswith(NO_BODY) or fp.GetAttributes() & pcbnew.FP_BOARD_ONLY:
            status = "no-body"
        elif fp.GetAttributes() & pcbnew.FP_DNP:
            status = "dnp"
        else:
            status = "model" if hit else "missing"
        out.append({"ref": fp.GetReference(), "footprint": fpid, "side": side, "status": status,
                    "model": str(hit.relative_to(MODEL_DIR) if hit and MODEL_DIR in hit.parents else hit or
                                 (models[0].m_Filename if models else ""))})
    out.sort(key=lambda e: (e["status"], e["footprint"], e["ref"]))
    dst = outdir / "build" / f"{name}-3d.json"
    dst.parent.mkdir(exist_ok=True)
    dst.write_text(json.dumps(out, indent=1) + "\n")
    miss = [e for e in out if e["status"] == "missing"]
    print(f"3D: {sum(e['status'] == 'model' for e in out)} with a model, {len(miss)} without "
          f"({', '.join(sorted({e['footprint'] for e in miss})) or 'none'})")
    return dst


ART_LAYERS = ("F.Cu", "B.Cu", "F.Mask", "B.Mask", "F.SilkS", "B.SilkS")


def export_art(outdir: Path, name: str) -> Path:
    """Copper, mask-opening and silkscreen layers as simple polygons (mm, KiCad axes) plus the
    drill holes, for tools/pcb_glb.py to paint the board's top and bottom textures."""
    import pcbnew
    board = pcbnew.LoadBoard(str(outdir / f"{name}.kicad_pcb"))
    bb = board.GetBoardEdgesBoundingBox()
    mm = pcbnew.ToMM
    art = {"origin": [mm(bb.GetX()), mm(bb.GetY())], "size": [mm(bb.GetWidth()), mm(bb.GetHeight())],
           "layers": {}, "holes": []}
    for lname in ART_LAYERS:
        ps = pcbnew.SHAPE_POLY_SET()
        board.ConvertBrdLayerToPolygonalContours(board.GetLayerID(lname), ps)
        ps.Fracture()
        polys = []
        for i in range(ps.OutlineCount()):
            ol = ps.Outline(i)
            polys.append([[round(mm(ol.CPoint(k).x), 4), round(mm(ol.CPoint(k).y), 4)] for k in range(ol.PointCount())])
        art["layers"][lname] = polys
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            q = t.GetPosition()
            art["holes"].append([mm(q.x), mm(q.y), mm(t.GetDrillValue())])
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            d = pad.GetDrillSize()
            if d.x > 0:
                q = pad.GetPosition()
                art["holes"].append([mm(q.x), mm(q.y), mm(min(d.x, d.y))])
    dst = outdir / "build" / f"{name}-art.json"
    dst.parent.mkdir(exist_ok=True)
    dst.write_text(json.dumps(art, separators=(",", ":")))
    print("wrote", dst, {k: len(v) for k, v in art["layers"].items()}, "holes", len(art["holes"]))
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--dsn", action="store_true", help="build, then export build/<board>.dsn for Freerouting")
    ap.add_argument("--ses", action="store_true", help="import build/<board>.ses into the existing PCB")
    ap.add_argument("--fab", action="store_true")
    ap.add_argument("--sch-only", action="store_true")
    ap.add_argument("--check", action="store_true", help="ERC + DRC of the committed project only (CI)")
    ap.add_argument("--outdir", help="work on a copy of the project in this folder (tools/route_farm.py's candidates)")
    ap.add_argument("--routed", help="with --ses: a board another router routed, imported instead of the session")
    ap.add_argument("--tidy", action="store_true", help="straighten the router's tracks of the PCB as it is "
                    "(pcbgen.tidy_board, as after --ses), no re-route")
    a = ap.parse_args()
    mod = load_design(a.board)
    b = mod.board()
    outdir = REPO / "electronics" / a.board
    if a.outdir:
        outdir = Path(a.outdir) if Path(a.outdir).is_absolute() else REPO / a.outdir
    if a.check:
        (outdir / "build").mkdir(exist_ok=True)
        e, d = erc(outdir, b.name), drc_readonly(outdir, b.name)
        print(f"ERC: {e['errors']} errors, {e['warnings']} warnings")
        print(f"DRC: {d['violations']}  unconnected={d['unconnected']}  parity={d['parity']}")
        for it in (e["items"] + d["items"])[:80]:
            print("  ", it)
        copper = {k: v for k, v in d["violations"].items() if not k.startswith(("silk", "lib_"))}
        if a.fab:
            export_fab(outdir, b.name, b)       # gives catalog models to the board first (apply_models)
        m = check_models(outdir, b.name, b.pcb.get("no_model", ()))
        sys.exit(1 if e["errors"] or copper or d["unconnected"] or d["parity"] or m["problems"] else 0)
    import pcbgen  # needs pcbnew
    if a.ses or a.tidy:
        if a.ses:
            pcbgen.import_session(b, outdir, Path(a.routed) if a.routed else None)
        else:
            pcbgen.tidy_board(b, outdir / f"{b.name}.kicad_pcb")
        e = json.loads((outdir / "build" / "erc-summary.json").read_text()) if (outdir / "build" / "erc-summary.json").exists() else {"errors": -1, "warnings": -1}
    else:
        generate_schematic(b, outdir, getattr(mod, "NETCLASSES", None))
        e = erc(outdir, b.name)
        (outdir / "build" / "erc-summary.json").write_text(json.dumps({k: e[k] for k in ("errors", "warnings")}))
        print(f"ERC: {e['errors']} errors, {e['warnings']} warnings")
        for it in e["items"][:60]:
            print("  ", it)
        if a.sch_only:
            return
        pb = pcbgen.PcbBuilder(b, outdir)
        pb.build(route=False, defer_pours=a.dsn)
        if a.dsn:
            pcbgen.export_dsn(b, outdir)
    d = drc(outdir, b.name)
    print(f"DRC: {d['violations']}  unconnected={d['unconnected']}  parity={d['parity']}")
    for it in d["items"][:80]:
        print("  ", it)
    m = check_models(outdir, b.name, b.pcb.get("no_model", ()))
    summary = {"board": b.name, "parts": len([p for p in b.parts.values() if p.on_board]),
               "nets": len(b.nets()), "erc": {k: e[k] for k in ("errors", "warnings")},
               "drc": {k: d[k] for k in ("violations", "unconnected", "parity")}, "routed": a.ses or a.tidy,
               "models": {"problems": m["problems"], "not fetched": m["not fetched"]}}
    if a.ses or a.tidy:
        import pcbnew
        from route_metrics import routing_metrics
        summary["routing"] = routing_metrics(pcbnew.LoadBoard(str(outdir / f"{b.name}.kicad_pcb")), b)
        summary["drc"]["copper"] = {k: v for k, v in d["violations"].items() if not k.startswith(("silk", "lib_"))}
    (outdir / "build" / "summary.json").write_text(json.dumps(summary, indent=1))
    if a.fab:
        export_fab(outdir, b.name, b)


if __name__ == "__main__":
    main()
