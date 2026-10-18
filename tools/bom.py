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
    # the drawer's DATA port board (v1.0, 2 layers, parts on one side) is NOT quoted either: Economic
    # PCBA (setup $8, stencil $1.50, $3 per extended part type: the USB4105, the S5B-PH and the
    # USBLC6), components at catalogue prices plus ≈ 3 % attrition, ≈ 30 joints a board.  The
    # USB4105's four shell stakes are through-hole, as on the node: JLC may add a small fee for them.
    "data-port": {
        "pcbs": 15, "assembled": 12, "service": "Economic", "total": 41.00, "estimate": True,
        "spec": "2-layer 40×17 mm, lead-free HASL",
        "pcb": {"board": 4.00},
        "pcba": {"setup": 8.00, "stencil": 1.50, "components": 17.90, "extended parts": 9.00, "SMT": 0.60},
    },
    # the camera pod board (v1.0, 2 layers, one side), one per camera (CAMERA_SETS): an estimate built like
    # the DATA port's, Economic PCBA, $3 per extended part type (the S8B, the SMD header, the LED)
    "camera-pod": {
        "pcbs": 5, "assembled": 2, "service": "Economic", "total": 22.75, "estimate": True,
        "spec": "2-layer 40×27 mm, lead-free HASL",
        "pcb": {"board": 2.00},
        "pcba": {"setup": 8.00, "stencil": 1.50, "components": 2.05, "extended parts": 9.00, "SMT": 0.20},
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
# TCAN1044AV: +$0.54 per board.  Then J7, the DATA header (B5B-PH-SM4-TB): +$0.30 per board and
# one more extended part type.
JLC_SINCE_QUOTE = {
    "bay-node": [("rev 0.5 parts (rack bus, GCT USB-C)", "components", 38.10),
                 ("rev 0.5: 3 more extended part types", "feeders", 9.00),
                 ("rev 0.5: TCAN1462V instead of the TCAN1044AV", "components", 8.64),
                 ("rev 0.5: J7 DATA header", "components", 4.80),
                 ("rev 0.5: J7, one more extended part type", "feeders", 3.00),
                 # the camera: the WROOM-1-N8R8 (+$0.30), the PH 8 J6 (+$0.35) and the vertical PH 6 J5 (+$0.04)
                 # take the N8's, the PH 2's and the side-entry PH 6's places; 2 × USBLC6, the AO3400A and
                 # 8 passives (basic): ≈ +$1.18 per board.  The B6B is one more extended part type
                 ("rev 0.5: camera (WROOM-1-N8R8, PH 8 J6, vertical AUX, ESD, light FET)", "components", 18.91),
                 ("rev 0.5: the vertical AUX connector, one more extended part type", "feeders", 3.00),
                 # the WROOM-1 grew the board 10 mm at the rear: 64 × 90 mm, +12.5 % of the quoted area
                 ("rev 0.5: the board 64 × 90 mm (quoted 64 × 80)", "board", 1.83)],
}


# the row cables' listing (docs/can.md: one type for feeds and jumpers)
ROW_CABLE_URL = "https://www.aliexpress.com/item/1005008045292937.html"
ROW_FEED_CM = [(30, 3.19), (60, 4.69), (80, 5.29)]      # rows A, B, C (≈ 0.25 / 0.45 / 0.6 m), then D...


# DUT cables (DATA port → board), per cable type of config/rack.yaml.  Listings found on 2026-10-18;
# AliExpress then asked for a captcha, so variants and the data lines are to be checked on the page.
# A right-angle micro-B or mini-B plug is not reversible, its "up" / "down" naming varies by seller and
# few listings offer both: those boards take a 90° adapter (sold as up / down / left / right sets, keep
# the one whose female faces up) and a cable with a straight micro-B / mini-B plug.
DUT_CABLES = {
    "c-to-c": {"supplier": "AliExpress 1005013255525639 (OLAF, \"double coudé\" C ↔ C, 15 cm)", "unit_eur": 2.5,
               "notes": "both plugs bent across their wide face (up / down, not left / right); USB-C is "
                        "reversible, so either bend works.  Check the listing says data, not charge only"},
    "c-to-micro-b": {"supplier": "AliExpress 2251832791887129 (HOQO, \"to Micro Male\", 25 cm)", "unit_eur": 1.0,
                     "notes": "the micro-B plug stands on the board's 90° adapter; the USB-C end any up / down bend"},
    "c-to-mini-b": {"supplier": "AliExpress 2251832791887129 (HOQO, \"to Mini Male\", 25 cm)", "unit_eur": 1.0,
                    "notes": "the F746G-DISCO's ST-LINK port (CN14) is mini-B, facing the side wall with 49 mm to it: "
                             "the straight mini-B plug fits, no adapter"},
    "c-to-micro-b-straight": {"supplier": "AliExpress 1005010391943574 (CableCreation USB-C → micro-B, 0.2 m, "
                                          "480 Mbps)", "unit_eur": 2.5,
                              "notes": "straight at both ends, lies flat with one bend (board turned to the side)"},
    "c-to-c-straight": {"supplier": "AliExpress (USB-C ↔ USB-C, 15–20 cm, USB 2.0 data, 480 Mbps)", "unit_eur": 2.0,
                        "notes": "straight at both ends; any short C ↔ C that states data (many short ones are "
                                 "charge-only)"},
}


# Cameras bought for a start (the user, 2026-10-18: "initialement je n'inclurai que 2 caméras"),
# whatever the viewer's `cameras` list shows; every bay node keeps J6 and its circuit, so any bay
# can take one later
CAMERA_SETS = 2


def _feed_lots(rack):
    """(length cm, EUR per lot of 5, [row ids]) for the feeds: row k gets ROW_FEED_CM[k] (the last one beyond)."""
    lots = {}
    for k, row in enumerate(rack.rows):
        cm, price = ROW_FEED_CM[min(k, len(ROW_FEED_CM) - 1)]
        lots.setdefault((cm, price), []).append(row["id"])
    return [(cm, price, ids) for (cm, price), ids in lots.items()]


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
        fees = pcba if line in pcba else pcb           # a PCBA line, or one of the bare PCB's
        fees[line] = round(fees[line] + usd, 2)
        changes.append(f"{what} (+${usd:.2f} {line})")
    return pcb, pcba, changes


def electronics(rack) -> tuple[list[dict], dict]:
    """Per-part lines at catalogue prices for the boards JLC assembles, plus the quote's PCB and
    PCBA fees as adjusted by jlc_order(); a last line per board brings the parts up to the quote's
    components figure.  Also returns the adjusted order per board."""
    prices = _catalog_prices()
    n_nodes = rack.units * len(rack.rows)          # every carrier unit gets a node (double bays: 2nd is optional)
    rows, orders = [], {}
    for name, need in (("bay-node", n_nodes), ("power-hub", 1), ("data-port", n_nodes), ("camera-pod", CAMERA_SETS)):
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
        src = "estimate, not quoted" if q.get("estimate") else f"JLCPCB quote {JLC_QUOTE_DATE}"
        pcb_src = src + (", adjusted" if name in JLC_FINISH or pcb != q["pcb"] else "")
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
    chain_m = math.ceil(0.19 * n_bays + 0.3)      # sold by the metre, one pair of end pieces with each
    charger = r["power_box"]["charger"]
    rows = [
        {"category": "Fasteners", "item": "M3 heat-set insert, 5.7 mm (generic brass, Ruthex-compatible holes)",
         "supplier": "AliExpress (bulk) / Ruthex", "qty": 4 * (cols + 1) * (n_rows + 1) + 6 * n_bays + 4 * cams + 4,
         "unit_eur": 0.03,
         "notes": "4 in the rear edge of every base and row ladder (the braces screw in); per tray 4 node "
                  "standoffs + 2 chain anchor; 4 under the ceiling of every camera bay; power box: 4 hub "
                  "standoffs"},
        {"category": "Fasteners", "item": "M3×8 pan head, Phillips (ISO 7045): rear braces, chain anchor",
         "supplier": "AliExpress (bulk)", "qty": 4 * braces + 2 * n_bays, "unit_eur": 0.02},
        {"category": "Fasteners", "item": "M3×6 (node PCB, power box lid)", "supplier": "AliExpress (bulk)",
         "qty": 4 * n_bays + 4, "unit_eur": 0.02},
        {"category": "Fasteners", "item": "M3 male-female hex spacer, 12 mm + 6 mm thread, brass (≤ 5.5 mm AF)",
         "supplier": "AliExpress (bulk)", "qty": 4, "unit_eur": 0.10,
         "notes": "power box: through the hub's holes into the standoff inserts; the lid screws into their tops"},
        {"category": "Fasteners", "item": "PT 2.6×8 pan head, thread-forming for plastics (or M2.5×8 self-tapping): "
                                         "drawer stop, foot lock, 4 for the chain's end pieces, 2 for the DATA port board",
         "supplier": "AliExpress (bulk, e.g. HZYUEGOU)", "qty": 8 * n_bays, "unit_eur": 0.02,
         "notes": "every printed pilot for them is 2.1–2.2 mm (≈ 0.8 × d)"},
        {"category": "Fasteners", "item": "M2.5 washer, DIN 125 (chain end pieces: their tab holes can be 4.3 mm)",
         "supplier": "AliExpress (bulk)", "qty": 4 * n_bays, "unit_eur": 0.01},
        {"category": "Fasteners", "item": "Neodymium disc magnet 6×3 mm N35, lot of 50 (drawer detent: one in the "
                                         "drawer, one in the tray ledge)",
         "supplier": "AliExpress 1005010074888189, \"6x3mm-50 pièces\"", "qty": math.ceil(2 * n_bays / 50),
         "unit": "lot", "unit_eur": 3.99,
         "notes": "glued (a drop of CA in the slip-fit pocket): the other magnet pulls each one out of its pocket's "
                  "mouth.  Polarity: stack the pair, mark both outer faces; marked faces into the pockets"},
        {"category": "Fasteners", "item": "Cyanoacrylate glue, gel (detent magnets)", "supplier": "any",
         "qty": 1, "unit_eur": 3.0},
        {"category": "Motion", "item": "Drag chain 7×7 mm, links open on both sides (outer 13.5 × 10.2 mm, R18), "
                                      "≈ 180 mm per drawer with its two end pieces",
         "supplier": "Olimex DRAG-CHAIN-7X7", "qty": chain_m, "unit": "m", "unit_eur": 4.0,
         "notes": "open the links to lay the DATA lead in (its PH plugs, 12 mm wide, do not pass a 7×7 channel); "
                  "Olimex publishes only the inner size: outer size and end holes from Electrokit 41017996, "
                  "measure the bend radius and the end pieces on arrival (config/rack.yaml › chain)"},
        {"category": "Motion", "item": "End pieces for 7×7 chain (pair: tab with 2 holes 8 mm apart), the drawers "
                                      "beyond one pair per metre of chain",
         "supplier": "AliExpress 1005003181041939, \"7x7mm\" (or one more metre of chain per pair)",
         "qty": max(0, n_bays - chain_m), "unit_eur": 2.17,
         "notes": "Olimex does not sell them alone; this generic chain ships with one pair per metre.  The listing "
                  "is for the non-opening 7×7 type: check one on the open links before buying the lot"},
        # the drawer's DATA port: our own small board (electronics/data-port, in the Electronics lines)
        # on the rear-bay floor, on a 5-wire PH lead from the node's J7 through the drag chain:
        # the rack's PH cable type (pin n ↔ pin 6−n), 5 pins so a 6-pin row cable cannot go in
        {"category": "Cables", "item": "JST PH 5-pin lead, pin n ↔ pin 6−n (flat, no twist), 50 cm, lot of 5 "
                                      "(DATA lead: node J7 → drag chain → DATA port board; VBUS, GND, D−, D+, GND)",
         "supplier": f"AliExpress {ROW_CABLE_URL}, \"Same direction\", 5P, Length50CM",
         "qty": math.ceil(n_bays / 5), "unit": "lot", "unit_eur": 4.2,
         "notes": "price interpolated from the 6-pin lots, not read: check the 5P lengths on the listing (≥ 40 cm).  The route is ≈ 38 cm plugs "
                  "included (constant over the stroke); the spare goes in a wider bend between the node and the "
                  "chain's fixed end (nothing moves there), never in front of the chain's moving end.  On arrival: "
                  "both plugs show the same face, pin 1 rings to pin 5; twist D−/D+ (pins 3-4) by hand.  Or crimp "
                  "them: PHR-5 + 10 × SPH-002T-P0.5S, 24 AWG"},
        # the row cables, one type (docs/can.md): pin n ↔ pin 7−n, both plugs the same face up.  Bought in
        # lots of 5 from one AliExpress listing (checked 2026-10-18: its "Same direction" photo shows both
        # plugs on the same face, its "Reverse direction" the 1:1 type); 6 pins
        {"category": "Cables", "item": "JST PH 6-pin jumper, pin n ↔ pin 7−n (flat, no twist), 200 mm, lot of 5 "
                                      "(bay → bay through the ladder: row bus, CAN, POS; 120 mm needed, fold the rest "
                                      "flat at the front of the plenum)",
         "supplier": f"AliExpress {ROW_CABLE_URL}, \"Same direction\", 6P, Length20CM",
         "qty": math.ceil(sum(cols - 1 for _ in rack.rows) / 5), "unit": "lot", "unit_eur": 2.85,
         "notes": f"{sum(cols - 1 for _ in rack.rows)} needed; on arrival: both plugs show the same face, pin 1 rings "
                  "to pin 6.  Or crimp them: PHR-6 + 12 × SPH-002T-P0.5S, 24 AWG"},
        *[{"category": "Cables", "item": f"JST PH 6-pin feed, the jumpers' type, {cm} cm, lot of 5 (power box → first "
                                         f"bay of row {', '.join(rows_)}: VRACK, CAN, POS)",
           "supplier": f"AliExpress {ROW_CABLE_URL}, \"Same direction\", 6P, Length{cm}CM",
           "qty": math.ceil(len(rows_) / 5), "unit": "lot", "unit_eur": price,
           "notes": "checked as the jumpers; the listing doesn't give the gauge (26 AWG is usual): fine for a row's "
                    "≈ 0.4 A, warm at the eFuse's 1.6 A limit; twist the CAN pair (pins 3-4) by hand"}
          for cm, price, rows_ in _feed_lots(rack)],
    ]
    cab = Counter(info["cable"] for info in pop.values())
    lib = rackcfg.load_boards()
    for k, n in sorted(cab.items()):
        src = DUT_CABLES.get(k, {"supplier": "AliExpress", "unit_eur": 3.0})
        boards = ", ".join(sorted({lib[info["board"]].get("short", info["board"])
                                   for info in pop.values() if info["cable"] == k}))
        rows.append({"category": "Cables", "item": f"{r['cables'][k]['label']} (DUT cable: {boards})",
                     "supplier": src["supplier"], "qty": n, "unit_eur": src["unit_eur"],
                     "notes": src.get("notes", "")})
    # 90° adapters for the micro-B / mini-B boards whose USB faces the port wall (cable style adapter): one
    # bent up and one bent down per board, the socket's orientation deciding which one serves
    ada = Counter(r["cables"][info["cable"]]["b"] for info in pop.values()
                  if r["cables"][info["cable"]].get("style") == "adapter")
    for t, n in sorted(ada.items()):
        name = {"micro-b": "Micro-B", "mini-b": "Mini-B"}[t]
        rows.append({"category": "Cables", "item": f"{name} 90° adapter, male → female, up and down, one of each "
                                                   f"per board",
                     "supplier": "AliExpress (DIY-018, \"UP\" and \"DOWN\")" if t == "micro-b" else "AliExpress",
                     "qty": 2 * n, "unit_eur": 1.0,
                     "notes": "keep the one whose female faces up once plugged into the board (the cable's straight "
                              "plug stands on it, its cable leaves upwards); the other is a spare"})
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
    if CAMERA_SETS:
        cams = CAMERA_SETS
        rows += [
            # the bay's own node drives its camera (SPI) and light (docs/electronics.md, Camera)
            {"category": "Cameras", "item": "Arducam Mega 3MP SPI camera, M12 version (B0434), 33 × 33 mm",
             "supplier": "Welectron (33.90 € TTC) / Arducam (≈ $30) / DigiKey", "qty": cams, "unit_eur": 28.25,
             "notes": "on arrival: its header's order (VCC GND SCK MISO MOSI CS) and its MISO high level when fed 5 V "
                      "(≤ 3.6 V, or change R33 and fit R35 on the node)"},
            {"category": "Cameras", "item": "M12 lens, 1/4\", ≈ 120° diagonal (the stock 90° is too narrow for a "
                                           "NUCLEO-144 / nRF DK)", "supplier": "AliExpress", "qty": cams, "unit_eur": 3.0},
            # the pod board (electronics/camera-pod, in the Electronics lines) carries the light and the
            # Mega's 3.3 V: nothing to crimp or solder
            {"category": "Cameras", "item": "JST PH 8-pin lead, pin n ↔ pin 9−n (flat, no twist), 50 cm, lot of 5 "
                                           "(camera lead: node J6 → pod J1)",
             "supplier": f"AliExpress {ROW_CABLE_URL}, \"Same direction\", 8P, Length50CM",
             "qty": math.ceil(cams / 5), "unit": "lot", "unit_eur": 4.5,
             "notes": f"{cams} needed; price interpolated from the 6-pin lots, not read: check the 8P lengths "
                      "(45–50 cm).  On arrival: both plugs show the same face, pin 1 rings to pin 8"},
            {"category": "Cameras", "item": "Cable JST XH 2.54 6-pin → Dupont female, one 6-pin housing, 10–20 cm "
                                           "(the Mega → pod J2, VCC GND SCK MISO MOSI CS in order)",
             "supplier": "AliExpress", "qty": cams, "unit_eur": 0.5,
             "notes": "the Mega's own 6-pin cable does if it ends in Dupont sockets; J2's pins are named on the "
                      "board, so the wires go on by name"},
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
           "(USB-C PD input, eFuses, rack controller; 4 layers), the DATA port and the camera pod boards are **estimates**, not "
           "quotes: re-quote them before ordering, and check the AP33772S's sourcing (out of stock at LCSC on "
           "2026-10-18).", "",
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
