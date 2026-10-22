#!/usr/bin/env python3
"""The order panel of a board assembled two ways: its copies side by side, each with its own assembly variant.

    tools/panel.sh <board>                 (KiCad 10 + KiKit, in Docker: the usual image plus `pip install kikit`)
    python3 electronics/tools/panelize.py <board>
    python3 electronics/tools/panelize.py <board> --check     (the halves against the variants only, no KiCad)

The board declares it in design.py, b.pcb["panel"]:
    {"gap": mm between the copies, "tabs": [x of each mouse-bite tab on the joint], "tab_width": mm,
     "bite": {"drill", "pitch", "offset"} (mm; offset: the holes' centres inside each board's edge),
     "boards": [{"tag": "L", "variant": None, "rot": 0}, {"tag": "B", "variant": "base", "rot": 180}]}
The first copy stays where the board is drawn (KiCad x 0–W, y 0–H); each next one is turned by its "rot" about
its centre and placed above the previous one, `gap` mm away, so a copy turned 180° meets the first top edge to
top edge.  Its parts become <ref>_<tag>, its nets and netclasses <tag>_<name> (each copy's own connectivity;
not <tag>-: KiCad reads a netclass pattern as a regular expression too, and "L-+5V" would take "L--5V"); a copy's variant
leaves its parts DNP (b.pcb["variants"]).  The copies meet only through the tabs: a bridge of board `tab_width`
wide and a line of `drill` holes along each board's edge (JLC: 0.6 mm holes, 0.35–0.4 mm apart, 5–8 a set).

Writes, beside the board:
    <board>-panel.kicad_pcb / .kicad_pro / .kicad_dru       the panel (zones refilled with the board's rules)
    fab/<board>-panel-gerbers.zip                             its Gerbers and drill files
    fab/<board>-panel-bom-jlcpcb.csv, -panel-cpl-jlcpcb.csv   one BOM and CPL for both assemblies
    docs/<board>-panel-top.png                                a render
and checks: DRC (no schematic: no parity), every footprint's 3D model, the mouse bites' clearance to copper and
to parts, and that each copy's rows in the panel's CPL and BOM are its variant's own (<board>[-<variant>]-…),
moved and turned with it.
"""

from __future__ import annotations

import csv
import json
import math
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

MM = 1_000_000                      # KiCad's internal unit: nm
COPPER_TO_HOLE = 0.5                # mm, from a mouse-bite hole's edge to any copper (JLC gives no figure: ours)
COURTYARD_TO_HOLE = 1.0             # mm, to any part's courtyard
TAG_SUFFIXES: tuple = ()            # "_L", "_B": the copies' references (set by build())


def placement(spec: dict, size: tuple[float, float]):
    """Per copy: (tag, variant, rot, f) with f(x, y) → panel (x, y), KiCad axes (Y down)."""
    w, h = size
    out, top = [], 0.0
    for i, c in enumerate(spec["boards"]):
        rot = c.get("rot", 0) % 360
        if i == 0:
            cx, cy = w / 2, h / 2
        else:
            top -= spec["gap"] + h                      # the next copy above: its bottom `gap` under the last's top
            cx, cy = w / 2, top + h / 2
        a = math.radians(rot)

        def f(x, y, cx=cx, cy=cy, a=a):
            dx, dy = x - w / 2, y - h / 2
            # KiCad turns counter-clockwise as seen, Y down
            return (cx + dx * math.cos(a) + dy * math.sin(a), cy - dx * math.sin(a) + dy * math.cos(a))
        out.append((c["tag"], c.get("variant"), rot, f))
    return out


def variant_files(fab: Path, name: str, variant: str | None) -> tuple[Path, Path]:
    tag = f"-{variant}" if variant else ""
    return fab / f"{name}{tag}-bom-jlcpcb.csv", fab / f"{name}{tag}-cpl-jlcpcb.csv"


def check_halves(outdir: Path, name: str, spec: dict, size: tuple[float, float]) -> list[str]:
    """Each copy's rows of the panel's CPL and BOM against its variant's own files: the same parts, each moved
    and turned with its copy (CPL in JLC's frame: Y up, mm), the same LCSC parts in the same numbers."""
    fab = outdir / "fab"
    rows = list(csv.DictReader((fab / f"{name}-panel-cpl-jlcpcb.csv").read_text(encoding="utf-8").splitlines()))
    bom = list(csv.DictReader((fab / f"{name}-panel-bom-jlcpcb.csv").read_text(encoding="utf-8").splitlines()))
    errors = []
    num = lambda s: float(s.removesuffix("mm"))
    for tag, variant, rot, f in placement(spec, size):
        bom_f, cpl_f = variant_files(fab, name, variant)
        want = {}
        for r in csv.DictReader(cpl_f.read_text(encoding="utf-8").splitlines()):
            x, y = f(num(r["Mid X"]), -num(r["Mid Y"]))
            want[f"{r['Designator']}_{tag}"] = (x, -y, r["Layer"], (float(r["Rotation"]) + rot) % 360)
        got = {r["Designator"]: (num(r["Mid X"]), num(r["Mid Y"]), r["Layer"], float(r["Rotation"]) % 360)
               for r in rows if r["Designator"].endswith(f"_{tag}")}
        if set(want) != set(got):
            errors.append(f"{tag}: CPL parts differ: only in the variant {sorted(set(want) - set(got))[:8]}, "
                          f"only in the panel {sorted(set(got) - set(want))[:8]}")
        for ref in set(want) & set(got):
            (x0, y0, l0, r0), (x1, y1, l1, r1) = want[ref], got[ref]
            dr = abs((r0 - r1 + 180) % 360 - 180)
            if math.hypot(x1 - x0, y1 - y0) > 0.01 or l0 != l1 or dr > 0.01:
                errors.append(f"{ref}: panel ({x1:.3f}, {y1:.3f}) {l1} {r1:.2f}° ≠ variant moved "
                              f"({x0:.3f}, {y0:.3f}) {l0} {r0:.2f}°")
        need = Counter()
        for r in csv.DictReader(bom_f.read_text(encoding="utf-8").splitlines()):
            need[r["LCSC Part #"]] += len([d for d in r["Designator"].split(",") if d])
        have = Counter()
        for r in bom:
            have[r["LCSC Part #"]] += len([d for d in r["Designator"].split(",") if d.endswith(f"_{tag}")])
        have = +have
        if need != have:
            errors.append(f"{tag}: BOM counts differ: {dict(need - have)} missing, {dict(have - need)} extra")
    return errors


# ------------------------------------------------------------------------------------------- the panel
def build(name: str) -> int:
    import pcbnew
    from shapely.geometry import LineString, box
    from kikit.panelize import Origin, Panel

    import build_board
    from catalog import HAND_SOLDER_LCSC

    b = build_board.load_design(name).board()
    spec = b.pcb["panel"]
    size = b.pcb["size"]
    w, h = size
    outdir = REPO / "electronics" / name
    src = outdir / f"{name}.kicad_pcb"
    pname = f"{name}-panel"
    out = outdir / f"{pname}.kicad_pcb"
    copies = placement(spec, size)
    tags = [t for t, *_ in copies]
    global TAG_SUFFIXES
    TAG_SUFFIXES = tuple(f"_{t}" for t in tags)

    board = pcbnew.LoadBoard(str(src))
    panel = Panel(str(out))
    panel.inheritDesignSettings(board)
    panel.inheritProperties(board)
    panel.inheritTitleBlock(board)
    panel.inheritCopperLayers(board)
    for tag, variant, rot, f in copies:
        cx, cy = f(w / 2, h / 2)
        panel.appendBoard(str(src), pcbnew.VECTOR2I(round(cx * MM), round(cy * MM)), origin=Origin.Center,
                          rotationAngle=pcbnew.EDA_ANGLE(rot, pcbnew.DEGREES_T),
                          netRenamer=lambda n, orig, t=tag: f"{t}_{orig}" if orig else orig,
                          refRenamer=lambda n, orig, t=tag: f"{orig}_{t}")
    # the tabs: a bridge across each gap at each tab's x (the first copy's frame), a line of holes on each side
    bite = spec["bite"]
    cuts = []
    for k in range(len(copies) - 1):
        y_low = -k * (spec["gap"] + h)              # copy k's upper edge
        y_high = y_low - spec["gap"]                # copy k + 1's lower edge
        for x in spec["tabs"]:
            x0, x1 = x - spec["tab_width"] / 2, x + spec["tab_width"] / 2
            panel.appendSubstrate(box(x0 * MM, (y_high - 0.01) * MM, x1 * MM, (y_low + 0.01) * MM))
            # each cut runs so that the holes' offset goes into the board beside it
            cuts += [LineString([(x1 * MM, y_low * MM), (x0 * MM, y_low * MM)]),
                     LineString([(x0 * MM, y_high * MM), (x1 * MM, y_high * MM)])]
    panel.makeMouseBites(cuts, diameter=round(bite["drill"] * MM), spacing=round(bite["pitch"] * MM),
                         offset=round(bite["offset"] * MM), prolongation=0)
    panel.save(reconstructArcs=True, refillAllZones=False)

    # the copies' DNP parts, and the board's custom rules for the renamed nets (KiKit renames the netclasses
    # itself): then the zones are filled as on the board
    pb = pcbnew.LoadBoard(str(out))
    dnp = {tag: set(b.pcb.get("variants", {}).get(variant, {}).get("dnp", ())) if variant else set()
           for tag, variant, *_ in copies}
    for fp in pb.GetFootprints():
        ref = fp.GetReference()
        base, _, tag = ref.rpartition("_")
        if tag in dnp and base in dnp[tag]:
            fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_DNP)
    pcbnew.SaveBoard(str(out), pb)
    dru = outdir / f"{pname}.kicad_dru"
    src_dru = outdir / f"{name}.kicad_dru"
    if src_dru.exists():
        text = src_dru.read_text(encoding="utf-8")
        text = re.sub(r"A\.NetName == '([^']*)'",
                      lambda m: "(" + " || ".join(f"A.NetName == '{t}_{m.group(1)}'" for t in tags) + ")", text)
        dru.write_text(text, encoding="utf-8")
    pb = pcbnew.LoadBoard(str(out))
    filler = pcbnew.ZONE_FILLER(pb)
    filler.Fill(pb.Zones())
    pcbnew.SaveBoard(str(out), pb)

    ok = True
    # DRC: the panel has no schematic, so no parity
    (outdir / "build").mkdir(exist_ok=True)
    rpt = outdir / "build" / "panel-drc.json"
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-error", "--severity-warning",
                    "-o", rpt, out], check=False, capture_output=True)
    d = json.loads(rpt.read_text())
    viol = Counter(v["type"] for v in d.get("violations", []))
    errs = [v for v in d.get("violations", []) if v["severity"] == "error"]
    print(f"panel DRC: {dict(viol)}  unconnected={len(d.get('unconnected_items', []))}")
    for v in errs[:20]:
        print("  ", v["type"], v["description"], [i.get("description") for i in v.get("items", [])][:2])
    copper = {k for k in viol if not k.startswith(("silk", "lib_"))}
    ok &= not copper and not d.get("unconnected_items")

    # every footprint's 3D model (the mouse bites' holes have no body by nature)
    m = build_board.check_models(outdir, pname, b.pcb.get("no_model", ()))
    ok &= not m["problems"]

    # the mouse bites against copper and parts
    ok &= check_bites(pcbnew.LoadBoard(str(out)))

    # Gerbers, then one CPL and one BOM for both assemblies
    fab = outdir / "fab"
    build_board.export_gerbers(out, outdir / "build" / "panel-gerbers", fab / f"{pname}-gerbers.zip",
                               b.pcb.get("layers", 2))
    raw = outdir / "build" / "panel-pos.csv"
    subprocess.run(["kicad-cli", "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both",
                    "--exclude-dnp", "-o", raw, out], check=True, capture_output=True)
    lcsc = {p.ref: p.fields.get("LCSC", "") for p in b.parts.values()}
    with raw.open() as fi, (fab / f"{pname}-cpl-jlcpcb.csv").open("w", newline="") as fo:
        wr = csv.writer(fo)
        wr.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for row in csv.DictReader(fi):
            base = row["Ref"].rpartition("_")[0]
            if base.startswith(("H", "TP")) or lcsc.get(base) in HAND_SOLDER_LCSC or base not in lcsc:
                continue
            wr.writerow(build_board.jlc_cpl_row(row, lcsc[base]))
    rows = []
    for tag, variant, *_ in copies:
        for r in build_board.bom_rows(b, frozenset(dnp[tag])):
            rows.append({**r, "Designator": ",".join(f"{d}_{tag}" for d in r["Designator"].split(","))})
    with (fab / f"{pname}-bom-jlcpcb.csv").open("w", newline="") as fo:
        wr = csv.writer(fo)
        wr.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        wr.writerows(build_board.jlc_bom_rows(rows))
    errors = check_halves(outdir, name, spec, size)
    for e in errors[:20]:
        print("  halves:", e)
    print(f"halves: {'each copy matches its variant' if not errors else f'{len(errors)} differences'}")
    ok &= not errors

    docs = outdir / "docs"
    subprocess.run(["kicad-cli", "pcb", "render", "--side", "top", "--width", "1400", "--height", "2000",
                    "--quality", "high", "--background", "transparent", "-o", docs / f"{pname}-top.png", out],
                   check=False, capture_output=True)
    shutil.rmtree(outdir / "build" / "panel-gerbers", ignore_errors=True)
    return 0 if ok else 1


def check_bites(board) -> bool:
    """The mouse bites' holes (KiKit's bare NPTH footprints) against the copies' copper (pads, tracks, vias,
    filled zones: none within COPPER_TO_HOLE of a hole's edge) and parts (no courtyard within
    COURTYARD_TO_HOLE).  Nearest pad, track and courtyard reported."""
    import pcbnew
    holes = [(p.GetPosition(), p.GetDrillSize().x / 2) for fp in board.GetFootprints() for p in fp.Pads()
             if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH and not fp.GetReference().endswith(TAG_SUFFIXES)]
    cu, cy, near_cu, near_cy = [], [], (1e9, ""), (1e9, "")

    def seg_dist(p, a, b):
        ax, ay, bx, by, px, py = a.x, a.y, b.x, b.y, p.x, p.y
        L = (bx - ax) ** 2 + (by - ay) ** 2
        u = 0 if L == 0 else max(0, min(1, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / L))
        return math.hypot(px - ax - u * (bx - ax), py - ay - u * (by - ay))

    def box_dist(p, bb):
        dx = max(bb.GetLeft() - p.x, 0, p.x - bb.GetRight())
        dy = max(bb.GetTop() - p.y, 0, p.y - bb.GetBottom())
        return math.hypot(dx, dy)
    for pos, r in holes:
        for fp in board.GetFootprints():
            if not fp.GetReference().endswith(TAG_SUFFIXES):
                continue
            for pad in fp.Pads():
                d = (box_dist(pos, pad.GetBoundingBox()) - r) / MM
                if d < near_cu[0]:
                    near_cu = (d, f"{fp.GetReference()}.{pad.GetNumber()}")
            d = (box_dist(pos, fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd).BBox()) - r) / MM
            if d < near_cy[0]:
                near_cy = (d, fp.GetReference())
        for tr in board.GetTracks():
            if tr.GetClass() == "PCB_VIA":
                d = (math.hypot(pos.x - tr.GetPosition().x, pos.y - tr.GetPosition().y) - tr.GetWidth(pcbnew.F_Cu) / 2 - r) / MM
            else:
                d = (seg_dist(pos, tr.GetStart(), tr.GetEnd()) - tr.GetWidth() / 2 - r) / MM
            if d < near_cu[0]:
                near_cu = (d, f"{tr.GetClass()} {tr.GetNetname()}")
        for z in board.Zones():
            if z.GetIsRuleArea():
                continue
            for l in z.GetLayerSet().CuStack():
                if z.GetFilledPolysList(l).Collide(pcbnew.VECTOR2I(pos.x, pos.y), round(r + COPPER_TO_HOLE * MM)):
                    cu.append(f"zone {z.GetNetname()} on {board.GetLayerName(l)} near ({pos.x / MM:.2f}, {pos.y / MM:.2f})")
    ok = bool(holes) and near_cu[0] >= COPPER_TO_HOLE and near_cy[0] >= COURTYARD_TO_HOLE and not cu
    print(f"mouse bites: {len(holes)} holes; nearest pad/track/via {near_cu[0]:.2f} mm ({near_cu[1]}), "
          f"nearest courtyard {near_cy[0]:.2f} mm ({near_cy[1]}); zones within {COPPER_TO_HOLE} mm: {len(cu)}")
    for it in cu[:10]:
        print("  ", it)
    return ok


def main() -> int:
    name = sys.argv[1]
    if "--check" in sys.argv[2:]:
        import build_board
        b = build_board.load_design(name).board()
        errors = check_halves(REPO / "electronics" / name, name, b.pcb["panel"], b.pcb["size"])
        for e in errors:
            print(e)
        print("each copy matches its variant" if not errors else f"{len(errors)} differences")
        return 1 if errors else 0
    return build(name)


if __name__ == "__main__":
    sys.exit(main())
