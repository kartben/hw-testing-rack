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
    # v0.5 (USB-C PD input, eFuses, rack controller; 4 layers) is NOT quoted yet: an estimate built
    # like the bay node's Standard quote (the ESP32 module needs Standard PCBA and X-ray), its 4-layer
    # engineering fee, components at catalogue prices, $3 per extended part type (19).  The
    # AP33772SDKZ-13-FA02 was out of stock at LCSC on 2026-10-18: global sourcing would add to it.
    "power-hub": {
        "pcbs": 5, "assembled": 2, "service": "Standard", "total": 213.74, "estimate": True,
        "spec": "4-layer 76×140 mm, ENIG",
        "pcb": {"engineering": 25.00, "ENIG": 17.60, "board": 12.00},
        "pcba": {"setup": 25.75, "stencil": 8.27, "components": 52.32, "feeders": 57.00, "SMT": 2.00,
                 "X-ray": 13.28, "packaging": 0.52},
    },
}
# What the order changes against that quote (indicative, not re-quoted): the hub in lead-free HASL
# instead of ENIG (≈ $0–2 for 5 PCBs; the node keeps ENIG for the ESP32 module and USB-C); the hub's
# through-hole connectors soldered by hand (catalog hand_solder), bought loose from LCSC, so their
# extended part types no longer need loading; and no JLC hand-soldering fee on either board (the
# node's JST PH are SMD since rev 0.4, JLC places them).
JLC_FINISH = {}
# Parts added to a board after its quote (indicative, not re-quoted): (what, PCBA line, USD for the
# quoted order).  Bay node rev 0.5: the rack bus (TCAN1044AV, PESD2CAN, 2 × BAT54S, 3 resistors, 2
# capacitors, the 6-pin J1/J2), GCT USB4105 receptacles instead of the HRO ones and 2 × 100 nF on
# the USBLC6s: +$2.38 of parts per board at catalogue prices; four new extended part types and one
# gone (the HRO), ≈ $3 loading each.  Then the TCAN1462V (signal improvement) instead of the
# TCAN1044AV: +$0.54 per board.
JLC_SINCE_QUOTE = {
    "bay-node": [("rev 0.5 parts (rack bus, GCT USB-C)", "components", 38.10),
                 ("rev 0.5: 3 more extended part types", "feeders", 9.00),
                 ("rev 0.5: TCAN1462V instead of the TCAN1044AV", "components", 8.64)],
}


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
    # the quote's hand-soldering line was for the through-hole connectors: JLC solders none any more
    # (the hub's are hand-soldered, the node's are SMD since rev 0.4)
    if "hand soldering" in pcba:
        changes.append(f"no through-hole part for JLC (hand soldering −${pcba.pop('hand soldering'):.2f})")
    for what, line, usd in JLC_SINCE_QUOTE.get(name, []):
        pcba[line] = round(pcba[line] + usd, 2)
        changes.append(f"{what} (+${usd:.2f} {line})")
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
                         "notes": f"{r['Qty']} per board × {n} boards" + ("; hand-solder, buy loose (LCSC)" if hand else "")
                                  + (f"; alternative: {r['Alternative']}" if r.get("Alternative") else "")})
        rows += mine
        pcb, pcba, changes = jlc_order(name, {r["mpn"] for r in mine if not r["basic"]},
                                       {r["mpn"] for r in mine if r["hand_solder"]})
        orders[name] = {"pcb": pcb, "pcba": pcba, "changes": changes,
                        "total": round(sum(pcb.values()) + sum(pcba.values()), 2)}
        src = "estimate, not quoted (v0.5)" if q.get("estimate") else f"JLCPCB quote {JLC_QUOTE_DATE}"
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
        quoted_eur = pcba["components"] * USD_EUR
        rows.append({"category": "Electronics", "group": name,
                     "item": f"Components {name}: JLC quote minus the catalogue prices above",
                     "supplier": pcba_src, "qty": 1, "unit_eur": round(quoted_eur - parts_eur, 2),
                     "notes": f"quoted components ${q['pcba']['components']:.2f}"
                              + (f" + ${pcba['components'] - q['pcba']['components']:.2f} since"
                                 if pcba["components"] != q["pcba"]["components"] else "")
                              + f" (≈ €{quoted_eur:.2f}) for {n} boards; catalogue unit prices give €{parts_eur:.2f}"})
    return rows, orders


def printed(rack) -> tuple[list[dict], list[dict]]:
    """Printed parts with counts per assembly and filament estimate from the STL volume."""
    import trimesh
    pop = rack.raw.get("population", {})
    n_bays = sum(1 for _ in rack.bays())
    cols, n_rows = rack.units, len(rack.rows)
    cams = len(rack.raw.get("cameras", []))
    counts = Counter({
        # the panel frame: a ladder per column boundary and level, a floor plate, a cap plate and
        # an X brace per column and level
        "ladder_base": cols + 1, "ladder_cap": cols + 1, "floor_plate": cols, "cap_plate": cols, "brace_base": cols,
        "tray": n_bays, "drawer": n_bays, "chain_foot": n_bays, "chain_anchor": n_bays,
        "camera_pod_mount": cams, "camera_pod_cradle": cams, "bay_label": n_bays,
        # the power box: base and lid, and their optional label inlays (a second, light filament)
        "power_box_base": 1, "power_box_lid": 1, "power_box_labels": 1, "power_box_lid_labels": 1,
    })
    for row in rack.rows:
        counts[f"ladder_{row['id'].lower()}"] += cols + 1
        counts[f"brace_{row['id'].lower()}"] += cols
    for bay in rack.bays():
        info = pop.get(bay.id)
        counts[f"plate_{info['board']}" if info else "plate_universal"] += 1
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
    rows.append({"category": "Printed parts", "group": "filament", "item": "PETG filament",
                 "supplier": "any", "qty": math.ceil(total_g / 1000 * 1.1 * 10) / 10, "unit": "kg",
                 "unit_eur": PETG_EUR_PER_KG, "notes": f"≈{total_g / 1000:.1f} kg estimated + 10 % waste, "
                                                    f"{sum(counts.values())} parts"})
    return rows, prints


def hardware(rack) -> list[dict]:
    r = rack.raw
    n_rows = len(rack.rows)
    cols = rack.units
    n_bays = sum(1 for _ in rack.bays())
    pop = r.get("population", {})
    cams = len(r.get("cameras", []))
    braces = cols * (n_rows + 1)
    charger = r["power_box"]["charger"]
    rows = [
        {"category": "Fasteners", "item": "M3 heat-set insert, 5.7 mm (generic brass, Ruthex-compatible holes)",
         "supplier": "AliExpress (bulk) / Ruthex", "qty": 4 * (cols + 1) * (n_rows + 1) + 6 * n_bays + 4 * cams + 4,
         "unit_eur": 0.03,
         "notes": "4 in the rear edge of every base and row ladder (the braces screw in); per tray 4 node "
                  "standoffs + 2 chain anchor; 4 under the ceiling of every camera bay; power box: 4 hub "
                  "standoffs"},
        {"category": "Fasteners", "item": "M3×8 pan head, Phillips (ISO 7045): rear braces",
         "supplier": "AliExpress (bulk)", "qty": 4 * braces, "unit_eur": 0.02},
        {"category": "Fasteners", "item": "M3×6 (node PCB, chain anchor, power box lid)", "supplier": "AliExpress (bulk)",
         "qty": 6 * n_bays + 4, "unit_eur": 0.02},
        {"category": "Fasteners", "item": "M3 male-female hex spacer, 12 mm + 6 mm thread, brass (≤ 5.5 mm AF)",
         "supplier": "AliExpress (bulk)", "qty": 4, "unit_eur": 0.10,
         "notes": "power box: through the hub's holes into the standoff inserts; the lid screws into their tops"},
        {"category": "Fasteners", "item": "M2.5×8 self-tapping (drawer stop, chain-foot lock) + M2.5×6 (chain ends)",
         "supplier": "AliExpress (bulk)", "qty": 6 * n_bays, "unit_eur": 0.02},
        {"category": "Fasteners", "item": "Neodymium disc magnet 6×3 mm (drawer detent: one in the drawer, one in the tray ledge)",
         "supplier": "supermagnete S-06-03-N", "qty": 2 * n_bays, "unit_eur": 0.30},
        {"category": "Motion", "item": "Drag chain 7×7 mm, R18, plastic, cut to ≈ 160 mm per drawer",
         "supplier": "AliExpress / igus E2 micro", "qty": round(0.17 * n_bays + 0.3, 1), "unit": "m", "unit_eur": 4.0},
        {"category": "Cables", "item": "USB-C male → USB-C female panel-mount extension, 30 cm, M3 ears (drawer DATA port)",
         "supplier": "AliExpress (generic, USB 2.0 is enough)", "qty": n_bays, "unit_eur": 1.5},
        {"category": "Cables", "item": "JST PH 6-pin jumper, 1:1, 24 AWG, 120 mm, both ends PHR-6 "
                                      "(bay → bay through the ladder: row bus, CAN, POS)",
         "supplier": "pre-crimped PH 6-pin, \"same direction\" (AliExpress) or PHR-6 + 12 × SPH-002T-P0.5S",
         "qty": sum(cols - 1 for _ in rack.rows), "unit_eur": 0.6,
         "notes": "check pin 1 ↔ pin 1: vendors name the same/reverse types inconsistently (docs/can.md)"},
        {"category": "Cables", "item": "JST PH 6-pin feed, 1:1, 24 AWG, ≈ 0.25 / 0.45 / 0.6 m for rows A / B / C "
                                      "(power box → first bay of each row: VRACK, CAN, POS)",
         "supplier": "pre-crimped PH 6-pin (AliExpress) or PHR-6 + 12 × SPH-002T-P0.5S", "qty": n_rows, "unit_eur": 0.8,
         "notes": "PH: 2 A per contact, each row's eFuse limits it to 1.6 A; twist the CAN pair (pins 3-4) by hand"},
    ]
    cab = Counter(info["cable"] for info in pop.values())
    for k, n in sorted(cab.items()):
        price = {"c-to-c": 4.5, "c-to-micro-b": 2.9, "c-to-mini-b": 6.0}.get(k, 4.0)
        rows.append({"category": "Cables", "item": r["cables"][k]["label"] + " (DUT cable, short / right-angle)",
                     "supplier": "Adafruit / Delock / AliExpress", "qty": n, "unit_eur": price})
    rows += [
        # the rack's supply: a USB PD charger outside it, into the power box's rear wall (the hub's
        # AP33772S sink asks for 28 V EPR, or 20 V), so no mains wiring anywhere in the rack
        {"category": "Power", "item": charger["part"], "supplier": "Anker / UGREEN / Satechi (any PD 3.1 EPR)",
         "qty": 1, "unit_eur": 70.0,
         "notes": "dedicated to the rack: a multi-port charger may withdraw its 28 V / 5 A offer when something else "
                  "is plugged in.  Realistic load ≈ 35–40 W, worst case ≈ 130 W; a 100 W (20 V × 5 A) charger "
                  "covers normal use, the hub budgets rows against the contract"},
        {"category": "Power", "item": charger["cable"], "supplier": "any (check the 5 A / EPR e-marker)", "qty": 1,
         "unit_eur": 12.0, "notes": "above 3 A the charger only offers its full current through an e-marked 5 A cable"},
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
    return rows


def main():
    rack = rackcfg.load()
    elec, orders = electronics(rack)
    prt, prints = printed(rack)
    hw = hardware(rack)
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
    data = {"rows": rows, "by_category": dict(by_cat), "total_eur": round(total, 2),
            "prints": prints, "bays": n_bays, "rows_n": len(rack.rows),
            "jlc_quote": {"date": JLC_QUOTE_DATE, "currency": "USD", "shipping": JLC_SHIPPING, "boards": JLC_QUOTE,
                          "order": orders}}
    (REPO / "site" / "assets").mkdir(parents=True, exist_ok=True)
    (REPO / "site" / "assets" / "bom.json").write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")

    md = ["# Bill of materials", "",
          "Generated by `python tools/bom.py` from `config/rack.yaml`, the KiCad BOMs and the STL volumes.",
          f"Configuration: **{n_bays} bays** ({rack.units} columns × {len(rack.rows)} rows) in the panel frame. "
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
           "them up to the quoted components figure.  *Order* applies what changed since, not re-quoted: the "
           "through-hole connectors hand-soldered from loose LCSC parts (LCSC shipping extra).  The power hub v0.5 "
           "(USB-C PD input, eFuses, rack controller; 4 layers) is an **estimate**, not a quote: re-quote it before "
           "ordering, and check the AP33772S's sourcing (out of stock at LCSC on 2026-10-18).", "",
           "| Board | Order | Line | USD |", "|---|---|---|---:|"]
    for name, q in JLC_QUOTE.items():
        order = f"{q['pcbs']} PCBs ({q['spec']}), {q['assembled']} assembled, {q['service']} PCBA"
        md.append(f"| {name} | {order} | PCB: {_usd(q['pcb'])} | {sum(q['pcb'].values()):.2f} |")
        md.append(f"| | | PCBA: {_usd(q['pcba'])} | {sum(q['pcba'].values()):.2f} |")
        md.append(f"| | | **{'Estimated' if q.get('estimate') else 'Quoted'} total** | **{q['total']:.2f}** |")
        if name in orders:
            o = orders[name]
            md.append(f"| | | Order (indicative): {'; '.join(o['changes']) or 'as quoted'} | {o['total']:.2f} |")
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
