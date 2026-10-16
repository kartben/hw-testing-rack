#!/usr/bin/env python3
"""Full bill of materials for the shelf, derived from config/rack.yaml.

    python tools/bom.py

Writes
  bom/rack-bom.csv          every line item (category, qty, unit price, supplier ref)
  bom/README.md             human summary (cost per category, cut list, print list)
  site/assets/bom.json      data for the BOM page of the web viewer

Electronics come from the per-board BOMs written by the KiCad pipeline
(electronics/<board>/<board>-bom.csv) priced with tools/../electronics
catalogue + cached JLC prices, and add up to a real JLCPCB quote (JLC_QUOTE);
mechanics are counted from the geometry; STL volumes give filament estimates.
Prices are indicative (EUR, ex VAT, small quantities, October 2026) — always
re-quote before ordering.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import rackcfg  # noqa: E402

REPO = rackcfg.REPO
sys.path.insert(0, str(REPO / "electronics" / "tools"))
USD_EUR = 0.92
PETG_DENSITY = 1.27          # g/cm³
PRINT_FILL = 0.55            # walls + 15–20 % gyroid ≈ 55 % of the solid volume
PETG_EUR_PER_KG = 20.0

# Real quote taken on jlcpcb.com on 2026-10-16 (USD, logged-in account), without shipping
# (DHL ≈ $27–40) and import VAT.  Indicative: JLC's prices move, re-quote before ordering.
JLC_QUOTE_DATE = "2026-10-16"
JLC_SHIPPING = "DHL ≈ $27–40"
JLC_QUOTE = {
    "bay-node": {
        "pcbs": 20, "assembled": 16, "service": "Standard", "total": 367.71,
        "spec": "4-layer 64×80 mm, ENIG, 5 mm edge rails added by JLC for Standard PCBA",
        "pcb": {"engineering": 25.00, "ENIG": 19.30, "board": 14.60},
        "pcba": {"setup": 25.75, "stencil": 8.27, "components": 181.21, "feeders": 65.10, "SMT": 9.45,
                 "hand soldering": 3.61, "manual assembly": 1.62, "X-ray": 13.28, "packaging": 0.52},
    },
    "power-hub": {
        "pcbs": 5, "assembled": 2, "service": "Economic", "total": 74.13,
        "spec": "2-layer 120×70 mm, ENIG",
        "pcb": {"engineering": 4.00, "ENIG": 17.60, "board": 4.10},
        "pcba": {"setup": 8.24, "stencil": 1.55, "components": 17.56, "extended parts": 15.45, "SMT": 0.73,
                 "hand soldering": 3.61, "manual assembly": 0.43, "nitrogen reflow": 0.86},
    },
}
# What the order changes against that quote (indicative, not re-quoted): the hub in lead-free HASL
# instead of ENIG (≈ $0–2 for 5 PCBs; the node keeps ENIG for the ESP32 module and USB-C), and the
# through-hole connectors soldered by hand (catalog hand_solder), bought loose from LCSC: no JLC
# hand-soldering fee, and their extended part types no longer need loading.
JLC_FINISH = {"power-hub": ("HASL lead-free", 1.00)}


def _catalog_prices() -> dict:
    """MPN → (unit USD, LCSC, basic, JLC Standard-PCBA only, hand-soldered) from the electronics
    catalogue and passive cache."""
    try:
        import catalog
    except Exception:  # pragma: no cover
        return {}
    out = {c.mpn: (c.price, c.lcsc, c.basic, c.standard_only, c.hand_solder) for c in catalog.CAT.values()}
    cache = REPO / "electronics" / "lib" / "passives.json"
    if cache.exists():
        for hit in json.loads(cache.read_text(encoding="utf-8")).values():
            if hit:
                out[hit["mpn"]] = (hit.get("price") or 0.0, hit["lcsc"], True, False, False)
    return out


def _usd(fees: dict) -> str:
    return ", ".join(f"{k} ${v:.2f}" for k, v in fees.items())


def jlc_order(name: str, ext: set, hand: set) -> tuple[dict, dict, list[str]]:
    """The quoted PCB and PCBA lines of one board, adjusted for JLC_FINISH and for the hand-soldered
    parts (`hand`) among its extended part types (`ext`)."""
    q = JLC_QUOTE[name]
    pcb, pcba, changes = dict(q["pcb"]), dict(q["pcba"]), []
    if name in JLC_FINISH:
        finish, usd = JLC_FINISH[name]
        changes.append(f"{finish} ≈ ${usd:.2f} instead of ENIG ${pcb['ENIG']:.2f}")
        pcb = {(finish if k == "ENIG" else k): (usd if k == "ENIG" else v) for k, v in pcb.items()}
    if hand:
        fee = "feeders" if "feeders" in pcba else "extended parts"
        cut = round(pcba[fee] * len(hand & ext) / len(ext), 2)
        pcba[fee] = round(pcba[fee] - cut, 2)
        changes.append(f"{fee} −${cut:.2f} ({len(hand & ext)} of {len(ext)} extended part types hand-soldered)")
        changes.append(f"no hand soldering (−${pcba.pop('hand soldering'):.2f})")
    return pcb, pcba, changes


def electronics(rack) -> tuple[list[dict], dict]:
    """Per-part lines at catalogue prices for the boards JLC assembles, plus the quote's PCB and
    PCBA fees as adjusted by jlc_order(); a last line per board brings the parts up to the quote's
    components figure.  Also returns the adjusted order per board."""
    prices = _catalog_prices()
    n_nodes = rack.units * len(rack.rows)          # every carrier unit gets a node (double bays: 2nd is optional)
    rows, orders = [], {}
    for name, need in (("bay-node", n_nodes), ("power-hub", 1)):
        q = JLC_QUOTE[name]
        assert abs(sum(q["pcb"].values()) + sum(q["pcba"].values()) - q["total"]) < 0.005, f"{name}: quote lines ≠ total"
        n = q["assembled"]
        if n < need or n > max(need, 2):           # JLC assembles at least 2 boards
            print(f"warning: the JLC quote assembles {n} × {name} but the configuration needs {need}: re-quote")
        path = REPO / "electronics" / name / f"{name}-bom.csv"
        if not path.exists():
            rows.append({"category": "Electronics", "group": name, "item": f"{name} BOM missing — run tools/kicad.sh {name} --fab",
                         "qty": 0, "unit_eur": 0})
            continue
        mine = []
        for r in csv.DictReader(path.open(encoding="utf-8")):
            if r.get("DNP"):
                continue
            usd, lcsc, basic, std_only, hand = prices.get(r["MPN"], (0.0, r.get("LCSC", ""), False, False, False))
            mine.append({"category": "Electronics", "group": name, "item": f"{r['Value']} — {r['Description'] or r['MPN']}",
                         "ref": r["Designator"], "mpn": r["MPN"], "manufacturer": r["Manufacturer"],
                         "supplier": "LCSC (hand-solder, buy loose)" if hand else "LCSC/JLCPCB",
                         "part": r.get("LCSC", "") or lcsc, "qty": int(r["Qty"]) * n,
                         "unit_eur": round(usd * USD_EUR, 4), "basic": basic, "standard_only": std_only,
                         "hand_solder": hand,
                         "notes": f"{r['Qty']} per board × {n} boards" + ("; hand-solder, buy loose (LCSC)" if hand else "")})
        rows += mine
        pcb, pcba, changes = jlc_order(name, {r["mpn"] for r in mine if not r["basic"]},
                                       {r["mpn"] for r in mine if r["hand_solder"]})
        orders[name] = {"pcb": pcb, "pcba": pcba, "changes": changes,
                        "total": round(sum(pcb.values()) + sum(pcba.values()), 2)}
        src = f"JLCPCB quote {JLC_QUOTE_DATE}"
        pcb_src = src + (", adjusted" if name in JLC_FINISH else "")
        pcba_src = src + (", adjusted" if pcba != q["pcba"] else "")
        spec = q["spec"].replace("ENIG", JLC_FINISH[name][0]) if name in JLC_FINISH else q["spec"]
        rows.append({"category": "Electronics", "group": name, "item": f"Bare PCB {name} ({spec})",
                     "supplier": pcb_src, "qty": q["pcbs"], "unit_eur": round(sum(pcb.values()) * USD_EUR / q["pcbs"], 4),
                     "notes": f"{_usd(pcb)} = ${sum(pcb.values()):.2f} for {q['pcbs']} PCBs, {n} of them assembled"
                              + "".join(f"; {c}" for c in changes if "ENIG" in c)})
        std = sorted({r["mpn"] for r in mine if r.get("standard_only")})
        if std and q["service"] != "Standard":
            print(f"warning: {name} has Standard-only parts ({', '.join(std)}) but was quoted {q['service']} PCBA")
        fees = {k: v for k, v in pcba.items() if k != "components"}
        rows.append({"category": "Electronics", "group": name,
                     "item": f"{q['service']} PCBA, {n} boards: {', '.join(fees)}",
                     "supplier": pcba_src, "qty": 1, "unit_eur": round(sum(fees.values()) * USD_EUR, 2),
                     "notes": _usd(fees) + "".join(f"; {c}" for c in changes if "ENIG" not in c)
                              + (f"; Standard because {', '.join(std)} cannot be placed with Economic PCBA" if std else "")})
        # the quoted components include the connectors JLC no longer buys; they reappear above at
        # catalogue prices (bought loose), so the difference stays quote minus all catalogue lines
        parts_eur = sum(round(r["qty"] * r["unit_eur"], 2) for r in mine)
        quoted_eur = q["pcba"]["components"] * USD_EUR
        rows.append({"category": "Electronics", "group": name,
                     "item": f"Components {name}: JLC quote minus the catalogue prices above",
                     "supplier": src, "qty": 1, "unit_eur": round(quoted_eur - parts_eur, 2),
                     "notes": f"quoted components ${q['pcba']['components']:.2f} (≈ €{quoted_eur:.2f}) for {n} boards; "
                              f"catalogue unit prices give €{parts_eur:.2f}"})
    return rows, orders


def printed(rack) -> tuple[list[dict], list[dict]]:
    """Printed parts with counts per assembly and filament estimate from the STL volume."""
    import trimesh
    pop = rack.raw.get("population", {})
    n_units = rack.units * len(rack.rows)
    n_rows = len(rack.rows) + (1 if rack.raw["frame"].get("top_cap", True) else 0)
    cams = len(rack.raw.get("cameras", []))
    wide = sum(1 for b in rack.bays() if b.span == 2)
    counts = Counter({
        "carrier_base": n_units, "carrier_deck": n_units, "drawer": n_units,
        "drawer_guide_left": n_units, "drawer_guide_right": n_units,
        "chain_foot": n_units, "chain_anchor": n_units,
        "tier_bracket_left": n_rows, "tier_bracket_right": n_rows,
        "roof_deck": rack.units, "camera_pod_mount": cams, "camera_pod_cradle": cams,
        "bridge_bar": 2 * wide, "base_plate": rack.units, "base_psu_saddle": 2, "base_inlet_panel": 1,
        "base_front_panel": 2 * rack.units - 1, "base_side_panel": 2, "base_hub_mount": 1, "base_mains_cover": 1,
        "foot": 4, "slot_cable_clip": 12, "bay_label": sum(1 for _ in rack.bays()),
    })
    for bay in rack.bays():
        info = pop.get(bay.id)
        if info and bay.span == 1:
            counts[f"plate_{info['board']}"] += 1
        elif not info and bay.span == 1:
            counts["plate_universal"] += 1
    stl_dir = REPO / "mechanical" / "stl"
    rows, prints = [], []
    total_g = 0.0
    for name, qty in sorted(counts.items()):
        if qty == 0:
            continue
        stl = stl_dir / f"{name}.stl"
        grams = None
        if stl.exists():
            m = trimesh.load(stl, force="mesh")
            vol = abs(m.volume) / 1000.0          # cm³
            grams = vol * PETG_DENSITY * PRINT_FILL
            total_g += grams * qty
        prints.append({"part": name, "qty": qty, "grams_each": round(grams, 1) if grams else None,
                       "grams_total": round(grams * qty, 1) if grams else None, "stl": f"mechanical/stl/{name}.stl"})
    rows.append({"category": "Printed parts", "group": "filament", "item": "PETG filament (ASA/PC-blend near mains)",
                 "supplier": "any", "qty": math.ceil(total_g / 1000 * 1.1 * 10) / 10, "unit": "kg",
                 "unit_eur": PETG_EUR_PER_KG, "notes": f"≈{total_g / 1000:.1f} kg estimated + 10 % waste, "
                                                    f"{sum(counts.values())} parts"})
    return rows, prints


def hardware(rack) -> tuple[list[dict], list[dict]]:
    r = rack.raw
    P = rack.profile
    W, D = rack.width, rack.depth
    n_rows = len(rack.rows)
    n_levels = n_rows + (1 if r["frame"].get("top_cap", True) else 0)
    n_units = rack.units * n_rows
    pop = r.get("population", {})
    cams = len(r.get("cameras", []))
    front_h = rack.to_frame(n_rows, [0, P / 2, P / 2])[2] + 26
    rear_h = rack.to_frame(n_rows, [0, rack.bay_depth - P / 2, P / 2])[2] + 26
    beam_len = W - 2 * rack.inner_x0
    cut = [
        {"part": "front post", "length_mm": round(front_h), "qty": 2},
        {"part": "rear post", "length_mm": round(rear_h), "qty": 2},
        {"part": "row / roof beam (M5 tapped both ends)", "length_mm": round(beam_len), "qty": 2 * n_levels},
        {"part": "base beam X", "length_mm": round(W - 2 * P), "qty": 4},
        {"part": "base beam Y", "length_mm": round(D - 2 * P), "qty": 4},
    ]
    metres = sum(c["length_mm"] * c["qty"] for c in cut) / 1000
    m5_tnuts = 8 * n_levels + 4 * n_units + 4 * rack.units + 16 * 2 + 4 * rack.units + 10 * 4
    rows = [
        {"category": "Frame", "item": "2020 aluminium extrusion, B-type slot 6, black anodised, cut to length",
         "supplier": "Motedis / Dold / Misumi HFS5-2020", "qty": round(metres, 2), "unit": "m", "unit_eur": 4.1,
         "notes": "see cut list; ≈ €1.5 per cut extra"},
        # hardware at bulk prices (packs of 50–100 from AliExpress-type sellers)
        {"category": "Frame", "item": "Inside corner bracket, slot 6, with screws (base frame)",
         "supplier": "AliExpress (bulk) / Motedis", "qty": 16, "unit_eur": 0.5},
        {"category": "Frame", "item": "M5 drop-in T-nut, slot 6", "supplier": "AliExpress (bulk)", "qty": m5_tnuts,
         "unit_eur": 0.05},
        {"category": "Frame", "item": "M5×12 button head (ISO 7380)", "supplier": "AliExpress (bulk)", "qty": m5_tnuts,
         "unit_eur": 0.03},
        {"category": "Frame", "item": "M5×16 screw into post core (feet) + beam-end screws",
         "supplier": "AliExpress (bulk)", "qty": 4 + 4 * n_levels, "unit_eur": 0.04},
        {"category": "Fasteners", "item": "M3 heat-set insert, 5.7 mm (generic brass, Ruthex-compatible holes)",
         "supplier": "AliExpress (bulk) / Ruthex", "qty": n_units * (4 + 9 + 2) + 4 * cams + 4 + 2 * n_units,
         "unit_eur": 0.03,
         "notes": "per carrier: 4 node + 9 deck/guide + 2 chain; 4 per camera pod (only where a camera hangs); "
                  "hub mount; plates"},
        {"category": "Fasteners", "item": "M3×12 button head (guide → deck → carrier)", "supplier": "AliExpress (bulk)",
         "qty": 6 * n_units, "unit_eur": 0.02},
        {"category": "Fasteners", "item": "M3×8 countersunk (deck pillars, wide-bay seams)", "supplier": "AliExpress (bulk)",
         "qty": 3 * n_units + 6, "unit_eur": 0.02},
        {"category": "Fasteners", "item": "M3×6 (node PCB, chain anchor, hub)", "supplier": "AliExpress (bulk)",
         "qty": 6 * n_units + 4, "unit_eur": 0.02},
        {"category": "Fasteners", "item": "M2.5×8 self-tapping (drawer stops, foot lock) + M2.5×6 (chain ends)",
         "supplier": "AliExpress (bulk)", "qty": 3 * n_units + 4 * n_units, "unit_eur": 0.02},
        {"category": "Fasteners", "item": "Neodymium disc magnet 6×3 mm (drawer detent: one in drawer, one in deck)",
         "supplier": "supermagnete S-06-03-N", "qty": 2 * n_units, "unit_eur": 0.30},
        {"category": "Motion", "item": "Drag chain 7×7 mm, R18, plastic, cut to ≈ 160 mm per drawer",
         "supplier": "AliExpress / igus E2 micro", "qty": round(0.17 * n_units + 0.3, 1), "unit": "m", "unit_eur": 4.0},
        {"category": "Cables", "item": "USB-C male → USB-C female panel-mount extension, 30 cm, M3 ears (drawer DATA port)",
         "supplier": "AliExpress (generic, USB 2.0 is enough)", "qty": n_units, "unit_eur": 1.5},
        {"category": "Cables", "item": "JST PH 2-pin jumper, 24 AWG, 120 mm, both ends PHR-2 (bay → bay, 24 V)",
         "supplier": "pre-crimped (AliExpress) or DIY", "qty": sum(rack.units - 1 for _ in rack.rows), "unit_eur": 0.3},
        {"category": "Cables", "item": "JST PH 2-pin feed, 24 AWG, ≈1 m, PHR-2 + 2 × SPH-002T-P0.5S (hub → first bay of each row)",
         "supplier": "DIY", "qty": n_rows + 1, "unit_eur": 0.8,
         "notes": "PH: 2 A per contact; each row's eFuse limits it to 1.6 A"},
    ]
    cab = Counter(info["cable"] for info in pop.values())
    for b in rack.bays():
        info = pop.get(b.id)
        if info and b.span == 2:
            cab["c-to-c"] += 1          # second cable for the EVK (second node)
    for k, n in sorted(cab.items()):
        price = {"c-to-c": 4.5, "c-to-micro-b": 2.9, "c-to-mini-b": 6.0}.get(k, 4.0)
        rows.append({"category": "Cables", "item": r["cables"][k]["label"] + " (DUT cable, short / right-angle)",
                     "supplier": "Adafruit / Delock / AliExpress", "qty": n, "unit_eur": price})
    rows += [
        {"category": "Power", "item": "Mean Well UHP-200-24 (24 V 8.4 A, fanless, PFC)", "supplier": "TME / RS / Mouser",
         "qty": 1, "unit_eur": 51.0},
        {"category": "Power", "item": "Schurter DD11.0111.1111 C14 inlet, fuse holder + 2-pole switch", "supplier": "Mouser",
         "qty": 1, "unit_eur": 10.0},
        {"category": "Power", "item": "Fuse 5×20 T3.15 A H 250 V (Schurter 0001.2509) + spare", "supplier": "Mouser",
         "qty": 2, "unit_eur": 0.8},
        {"category": "Power", "item": "IEC C13 mains cord, 1.0 mm²", "supplier": "any", "qty": 1, "unit_eur": 5.0},
        {"category": "Power", "item": "H05V-K 1.0 mm² wire (brown, blue, green/yellow) + 4.8 mm insulated receptacles",
         "supplier": "any", "qty": 1, "unit": "set", "unit_eur": 5.0},
        {"category": "Power", "item": "16 AWG (1.3 mm²) DC wire PSU → hub, JST VHR-2N + 2 × SVH-41T-P1.1 "
                                       "(16–20 AWG), ferrules (PSU side), M5 ring lug + serrated washer (PE bond)",
         "supplier": "any / LCSC", "qty": 1, "unit": "set", "unit_eur": 4.5},
        {"category": "Power", "item": "(variant) Mean Well GST160A24-R7B brick + Kycon KPJX-PM-4S panel jack",
         "supplier": "RS / Mouser", "qty": 0, "unit_eur": 70.0, "notes": "instead of the UHP + inlet if you skip mains wiring"},
    ]
    if cams:
        rows += [
            {"category": "Cameras", "item": "Seeed XIAO ESP32S3 Sense (camera pod)", "supplier": "Seeed",
             "qty": cams, "unit_eur": 13.5},
            {"category": "Cameras", "item": "OV2640 wide-angle (120–160°) 24-pin DVP module (check FPC fit)",
             "supplier": "AliExpress", "qty": cams, "unit_eur": 4.0},
            {"category": "Cameras", "item": "JST-PH 2-pin lead to the XIAO 5 V pads + M3×30 pivot screw",
             "supplier": "any", "qty": cams, "unit_eur": 0.6},
        ]
    return rows, cut


def main():
    rack = rackcfg.load()
    elec, orders = electronics(rack)
    prt, prints = printed(rack)
    hw, cut = hardware(rack)
    rows = elec + prt + hw
    for r in rows:
        r.setdefault("unit", "pcs")
        r["ext_eur"] = round(float(r["qty"]) * float(r.get("unit_eur") or 0), 2)
    out = REPO / "bom"
    out.mkdir(exist_ok=True)
    fields = ["category", "group", "item", "qty", "unit", "unit_eur", "ext_eur", "supplier", "part", "mpn",
              "manufacturer", "ref", "notes"]
    with (out / "rack-bom.csv").open("w", newline="", encoding="utf-8") as fo:
        w = csv.DictWriter(fo, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    by_cat = defaultdict(float)
    for r in rows:
        by_cat[r["category"]] += r["ext_eur"]
    total = sum(by_cat.values())
    n_bays = sum(1 for _ in rack.bays())
    data = {"rows": rows, "by_category": dict(by_cat), "total_eur": round(total, 2), "cut_list": cut,
            "prints": prints, "bays": n_bays, "units": rack.units * len(rack.rows),
            "jlc_quote": {"date": JLC_QUOTE_DATE, "currency": "USD", "shipping": JLC_SHIPPING, "boards": JLC_QUOTE,
                          "order": orders}}
    (REPO / "site" / "assets").mkdir(parents=True, exist_ok=True)
    (REPO / "site" / "assets" / "bom.json").write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")

    md = ["# Bill of materials", "",
          "Generated by `python tools/bom.py` from `config/rack.yaml`, the KiCad BOMs and the STL volumes.",
          f"Configuration: **{n_bays} bays** ({rack.units * len(rack.rows)} carrier units) in {len(rack.rows)} rows. "
          "Prices are indicative (EUR excl. VAT, small quantities, October 2026); re-quote before ordering. "
          f"The boards follow a real JLCPCB quote of {JLC_QUOTE_DATE}, adjusted for the changes since (below, "
          f"converted at $1 = €{USD_EUR:.2f}); shipping ({JLC_SHIPPING}) and import VAT are extra.", "",
          "| Category | Cost (€) |", "|---|---:|"]
    md += [f"| {k} | {v:,.0f} |" for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1])]
    md += [f"| **Total** | **{total:,.0f}** |", "", f"≈ **€{total / n_bays:,.0f} per bay** all-in.", "",
           "Full line-item list: [`rack-bom.csv`](rack-bom.csv) · per-board JLCPCB files: "
           "`electronics/<board>/fab/` · interactive table: the viewer's BOM page.", "",
           f"## JLCPCB quote ({JLC_QUOTE_DATE})", "",
           f"Taken on jlcpcb.com from the files in `electronics/<board>/fab/`; USD, without shipping ({JLC_SHIPPING}) "
           "and import VAT.  The per-part lines below use catalogue prices; a *Components* line per board brings "
           "them up to the quoted components figure.  *Order* applies what changed since, not re-quoted: the hub "
           "in lead-free HASL, and the through-hole connectors hand-soldered from loose LCSC parts (LCSC shipping "
           "extra).", "",
           "| Board | Order | Line | USD |", "|---|---|---|---:|"]
    for name, q in JLC_QUOTE.items():
        order = f"{q['pcbs']} PCBs ({q['spec']}), {q['assembled']} assembled, {q['service']} PCBA"
        md.append(f"| {name} | {order} | PCB: {_usd(q['pcb'])} | {sum(q['pcb'].values()):.2f} |")
        md.append(f"| | | PCBA: {_usd(q['pcba'])} | {sum(q['pcba'].values()):.2f} |")
        md.append(f"| | | **Quoted total** | **{q['total']:.2f}** |")
        if name in orders:
            o = orders[name]
            md.append(f"| | | Order (indicative): {'; '.join(o['changes']) or 'as quoted'} | {o['total']:.2f} |")
    md += ["", "## Aluminium cut list (2020, B-type slot 6)", "", "| Part | Length (mm) | Qty |", "|---|---:|---:|"]
    md += [f"| {c['part']} | {c['length_mm']} | {c['qty']} |" for c in cut]
    md += ["", "## Printed parts", "", "| Part | Qty | g each (est.) | STL |", "|---|---:|---:|---|"]
    md += [f"| {p['part']} | {p['qty']} | {p['grams_each'] or '–'} | `{p['stl']}` |" for p in prints]
    md += ["", "## Line items", "", "| Category | Item | Qty | Unit € | Total € | Source |", "|---|---|---:|---:|---:|---|"]
    for r in rows:
        src = " ".join(x for x in (r.get("supplier", ""), r.get("part", "")) if x)
        md.append(f"| {r['category']} | {r['item']} | {r['qty']} {'' if r['unit'] == 'pcs' else r['unit']} | "
                  f"{float(r.get('unit_eur') or 0):.2f} | {r['ext_eur']:.2f} | {src} |")
    (out / "README.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"BOM: {len(rows)} lines, total ~ EUR {total:,.0f} (EUR {total / n_bays:,.0f}/bay)")
    for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1]):
        print(f"  {k:15s} EUR {v:8.0f}")


if __name__ == "__main__":
    main()
