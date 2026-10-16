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
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
REPO = HERE.parents[1]

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
        })
    return rows


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
    # pick & place (JLCPCB column names)
    raw = fab / "pos-raw.csv"
    run(["kicad-cli", "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both",
         "--exclude-dnp", "-o", raw, pcb], check=True, capture_output=True)
    with raw.open() as fi, (fab / f"{name}-cpl-jlcpcb.csv").open("w", newline="") as fo:
        r = csv.DictReader(fi)
        w = csv.writer(fo)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for row in r:
            if row["Ref"].startswith(("H", "TP")):
                continue
            w.writerow([row["Ref"], row["PosX"] + "mm", row["PosY"] + "mm",
                        "Top" if row["Side"] == "top" else "Bottom", row["Rot"]])
    raw.unlink()
    rows = bom_rows(b)
    with (fab / f"{name}-bom-jlcpcb.csv").open("w", newline="") as fo:
        w = csv.writer(fo)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for r in rows:
            if r["DNP"]:
                continue
            w.writerow([r["Value"], r["Designator"], r["Footprint"], r["LCSC"]])
    with (outdir / f"{name}-bom.csv").open("w", newline="", encoding="utf-8") as fo:
        w = csv.DictWriter(fo, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
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
