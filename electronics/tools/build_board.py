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


def bom_rows(b):
    """Group parts for JLCPCB (Comment, Designator, Footprint, LCSC) and a detailed BOM."""
    groups: dict[tuple, list] = {}
    for p in sorted(b.parts.values(), key=lambda p: (p.ref.rstrip("0123456789"), int("".join(c for c in p.ref if c.isdigit()) or 0))):
        if not p.in_bom or not p.on_board or p.ref.startswith("#"):
            continue
        k = (p.value, p.footprint, p.fields.get("LCSC", ""), p.fields.get("MPN", ""))
        groups.setdefault(k, []).append(p)
    rows = []
    for (value, fp, lcsc, mpn), parts in groups.items():
        p0 = parts[0]
        rows.append({
            "Designator": ",".join(p.ref for p in parts), "Qty": len(parts), "Value": value,
            "Footprint": fp.split(":")[1], "MPN": mpn, "Manufacturer": p0.fields.get("Manufacturer", ""),
            "LCSC": lcsc, "Description": p0.description, "DNP": "yes" if p0.dnp else "",
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
    "C431540": ("SW_SPDT_Shouhan_MSK12C02", 0, 0.0, -0.25),                   # bay SW3
    "C45262770": ("TSOT-23-6", 270, 0.0, 0.0),                                # bay U1 (LMR51635; FXL0630 L1 needs none)
    "C11355": ("MSOP-10_3x3mm_P0.5mm", 270, 0.0, 0.0),                        # bay U5 U6
    "C49851": ("TSSOP-10_3x3mm_P0.5mm", 270, 0.0, 0.0),                       # bay U10
    "C7519": ("SOT-23-6", 270, 0.0, 0.0),                                     # bay U4 U8
    "C55266": ("SOT-23-6", 180, 0.0, 0.0),                                    # bay U9
    "C10096": ("SOT-23-5", 180, 0.0, 0.0),                                    # bay U7
    "C8545": ("SOT-23", 180, 0.0, 0.0),                                       # bay Q2 Q3
    "C7503186": ("TO-252-2", 0, -1.89, 0.0),                                  # bay Q1, hub Q1
    "C544399": ("HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm_Mask2.66x2.46mm", 270, 0.0, 0.0),  # hub U1–U5
    "C160315": ("JST_VH_B2P-VH_1x02_P3.96mm_Vertical", 0, 1.98, 0.0),         # hub J1 (hand-soldered)
    # rack bus parts, fitted on 2026-10-18 the same way
    "C265405": ("JST_PH_S6B-PH-SM4-TB_1x06-1MP_P2.00mm_Horizontal", 180, 0.0, 0.0),  # bay J1 J2 J5, hub row outputs
    "C3234993": ("SOIC-8_3.9x4.9mm_P1.27mm", 270, 0.0, 0.0),                  # bay U11, hub U6 (TCAN1044AV)
    "C75176": ("SOT-23", 180, 0.0, 0.0),                                      # bay D5, hub D9 (PESD2CAN)
    "C7420333": ("SOT-23", 180, 0.0, 0.0),                                    # bay D6 D7, hub POS clamps (BAT54S)
    "C5184243": ("USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal", 0, 0.0, -1.30),  # bay J3 J4, hub USB-C
}


def jlc_cpl_row(row, lcsc: str):
    """KiCad pos row (anchor, Y up) -> JLC CPL row, with the JLC_CPL_FIX correction applied."""
    x, y, rot = row["PosX"], row["PosY"], row["Rot"]
    fix = JLC_CPL_FIX.get(lcsc)
    if fix:
        fp, drot, dx, dy = fix
        if fp != row["Package"]:
            raise SystemExit(f"{row['Ref']}: JLC_CPL_FIX[{lcsc}] was checked on {fp}, not {row['Package']}")
        if row["Side"] != "top":
            raise SystemExit(f"{row['Ref']}: JLC_CPL_FIX is only worked out for top-side parts")
        a = math.radians(float(rot))
        # offset from footprint axes to board axes (KiCad, Y down), then to the pos file's Y up
        x = f"{float(x) + dx * math.cos(a) + dy * math.sin(a):.6f}"
        y = f"{float(y) + dx * math.sin(a) - dy * math.cos(a):.6f}"
        r = (float(rot) + drot) % 360
        rot = f"{r - 360 if r > 180 else r:.6f}"
    return [row["Ref"], x + "mm", y + "mm", "Top" if row["Side"] == "top" else "Bottom", rot]


def export_fab(outdir: Path, name: str, b):
    fab = outdir / "fab"
    if fab.exists():
        shutil.rmtree(fab)
    fab.mkdir(parents=True)
    pcb = outdir / f"{name}.kicad_pcb"
    sch = outdir / f"{name}.kicad_sch"
    gerb = fab / "gerbers"
    gerb.mkdir()
    layers = "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"
    if b.pcb.get("layers", 2) == 4:
        layers = "F.Cu,In1.Cu,In2.Cu,B.Cu," + layers.split(",", 2)[2]
    run(["kicad-cli", "pcb", "export", "gerbers", "--layers", layers, "--subtract-soldermask",
         "--use-drill-file-origin", "-o", str(gerb) + "/", pcb], check=True, capture_output=True)
    run(["kicad-cli", "pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th",
         "--generate-map", "--map-format", "gerberx2", "-o", str(gerb) + "/", pcb], check=True, capture_output=True)
    with zipfile.ZipFile(fab / f"{name}-gerbers.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(gerb.iterdir()):
            z.write(f, f.name)
    # pick & place (JLCPCB column names), corrected to JLC's own footprints
    raw = fab / "pos-raw.csv"
    run(["kicad-cli", "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both",
         "--exclude-dnp", "-o", raw, pcb], check=True, capture_output=True)
    lcsc = {p.ref: p.fields.get("LCSC", "") for p in b.parts.values()}
    fixed = []
    with raw.open() as fi, (fab / f"{name}-cpl-jlcpcb.csv").open("w", newline="") as fo:
        r = csv.DictReader(fi)
        w = csv.writer(fo)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for row in r:
            if row["Ref"].startswith(("H", "TP")) or lcsc.get(row["Ref"]) in HAND_SOLDER_LCSC:
                continue
            w.writerow(jlc_cpl_row(row, lcsc.get(row["Ref"], "")))
            if lcsc.get(row["Ref"]) in JLC_CPL_FIX:
                fixed.append(row["Ref"])
    raw.unlink()
    print("CPL: JLC footprint corrections on", " ".join(fixed))
    rows = bom_rows(b)
    with (fab / f"{name}-bom-jlcpcb.csv").open("w", newline="") as fo:
        w = csv.writer(fo)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        w.writerows(jlc_bom_rows(rows))
    with (outdir / f"{name}-bom.csv").open("w", newline="", encoding="utf-8") as fo:
        w = csv.DictWriter(fo, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    # the project's own 3D models first: the renders below, the STEP and the GLB all need them
    import pcbgen
    print("3D: project models on", pcbgen.apply_models(pcb), "footprints")
    # documentation outputs
    docs = outdir / "docs"
    docs.mkdir(exist_ok=True)
    run(["kicad-cli", "sch", "export", "pdf", "-o", docs / f"{name}-schematic.pdf", sch], check=True,
        capture_output=True)
    run(["kicad-cli", "sch", "export", "svg", "-o", str(docs / "svg"), sch], check=False, capture_output=True)
    for side, extra in (("top", []), ("bottom", [])):
        run(["kicad-cli", "pcb", "render", "--side", side, "--width", "1600", "--height", "1300", "--quality",
             "high", "--background", "transparent", "-o", docs / f"{name}-{side}.png", *extra, pcb],
            check=False, capture_output=True)
    run(["kicad-cli", "pcb", "render", "--rotate", "-40,0,35", "--zoom", "0.85", "--width", "1600", "--height",
         "1200", "--quality", "high", "--background", "transparent", "-o", docs / f"{name}-iso.png", pcb],
        check=False, capture_output=True)
    run(["kicad-cli", "pcb", "export", "step", "--subst-models", "-f", "-o", fab / f"{name}.step", pcb], check=False,
        capture_output=True)
    # board body + component models only: the layer art goes to the viewer as a texture
    # (tools/pcb_glb.py), from the polygons export_art() writes
    run(["kicad-cli", "pcb", "export", "glb", "--subst-models", "-f", "-o", fab / f"{name}.glb", pcb],
        check=False, capture_output=True)
    export_art(outdir, name)
    export_3d_coverage(outdir, name)


# footprints that have no body by nature: nothing to model
NO_BODY = ("MountingHole:", "TestPoint:", "NetTie:", "Fiducial:", "Symbol:")
MODEL_DIR = Path(os.environ.get("KICAD10_3DMODEL_DIR", "/usr/share/kicad/3dmodels"))


def export_3d_coverage(outdir: Path, name: str) -> Path:
    """Which placed footprints KiCad's STEP / GLB export gives a body, and which it can't:
    build/<board>-3d.json, one entry per footprint: "model" (a STEP/IGES file it resolves, the
    form the GLB export uses; a .wrl is replaced by the STEP of the same name, --subst-models),
    "no-body" (holes, test pads, net ties) or "missing" (no model, or a model file that isn't in
    KiCad's 3D library).  tools/pcb_glb.py adds stand-ins for the missing ones and fails on any
    it has none for."""
    import pcbnew
    board = pcbnew.LoadBoard(str(outdir / f"{name}.kicad_pcb"))
    env = {"KICAD10_3DMODEL_DIR": str(MODEL_DIR), "KICAD9_3DMODEL_DIR": str(MODEL_DIR),
           "KICAD8_3DMODEL_DIR": str(MODEL_DIR), "KICAD7_3DMODEL_DIR": str(MODEL_DIR),
           "KICAD6_3DMODEL_DIR": str(MODEL_DIR), "KIPRJMOD": str(outdir)}

    def resolve(fn: str) -> Path | None:
        for k, v in env.items():
            fn = fn.replace("${" + k + "}", v)
        p = Path(fn) if Path(fn).is_absolute() else outdir / fn
        for cand in (p, p.with_suffix(".step"), p.with_suffix(".stp"), p.with_suffix(".STEP"), p.with_suffix(".igs")):
            if cand.suffix.lower() in (".step", ".stp", ".igs", ".iges") and cand.exists():
                return cand
        return None

    out = []
    for fp in board.GetFootprints():
        fpid = fp.GetFPIDAsString()
        side = "bottom" if fp.IsFlipped() else "top"
        models = [m for m in fp.Models() if m.m_Show]
        hit = next((r for r in (resolve(m.m_Filename) for m in models) if r), None)
        if fpid.startswith(NO_BODY) or fp.GetAttributes() & pcbnew.FP_BOARD_ONLY:
            status = "no-body"
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
    a = ap.parse_args()
    mod = load_design(a.board)
    b = mod.board()
    outdir = REPO / "electronics" / a.board
    if a.check:
        (outdir / "build").mkdir(exist_ok=True)
        e, d = erc(outdir, b.name), drc_readonly(outdir, b.name)
        print(f"ERC: {e['errors']} errors, {e['warnings']} warnings")
        print(f"DRC: {d['violations']}  unconnected={d['unconnected']}  parity={d['parity']}")
        for it in (e["items"] + d["items"])[:80]:
            print("  ", it)
        copper = {k: v for k, v in d["violations"].items() if not k.startswith(("silk", "lib_"))}
        if a.fab:
            export_fab(outdir, b.name, b)
        sys.exit(1 if e["errors"] or copper or d["unconnected"] or d["parity"] else 0)
    import pcbgen  # needs pcbnew
    if a.ses:
        pcbgen.import_session(b, outdir)
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
    summary = {"board": b.name, "parts": len([p for p in b.parts.values() if p.on_board]),
               "nets": len(b.nets()), "erc": {k: e[k] for k in ("errors", "warnings")},
               "drc": {k: d[k] for k in ("violations", "unconnected", "parity")}, "routed": a.ses}
    (outdir / "build" / "summary.json").write_text(json.dumps(summary, indent=1))
    if a.fab:
        export_fab(outdir, b.name, b)


if __name__ == "__main__":
    main()
