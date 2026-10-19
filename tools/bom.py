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
import plate_layout  # noqa: E402
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
    # The order the user chose on 2026-10-19 ("10 en HASL"): 10 PCBs, lead-free HASL, all 10 assembled
    # (8 bays and 2 spares; JLC adds its $25 engineering fee only above 10 PCBs).  NOT re-quoted: the
    # quote of 2026-10-16 (20 PCBs ENIG, 16 assembled, $367.71) priced the board before rev 0.5 and the
    # full PCBA quote needs the user's sign-in.  Built from JLC's fees (help page of 2026-09-09) and the
    # live bare-PCB price of 2026-10-19: 74 × 90 mm 4-layer lead-free HASL $19.30 for 10 (as at 64 × 90: JLC's
    # offer covers up to 100 × 100 mm) + $0.20 for the 5 mm rails Standard PCBA may add; setup $25.56, stencil $8.21, $1.53 per unique part type (42, basic
    # or extended alike; J4 and its 22k Rp went with the 74 × 90 re-layout), SMT $0.0016 a joint (369 a board), X-ray $1.64 a board (the WROOM-1, mandatory),
    # packaging $0.52; components at catalogue prices × 1.12 (JLC's prices and attrition).  The page
    # also lists a Standard handling fee (≥ $14.93) that the 2026-10-16 quote didn't carry: to confirm.
    "bay-node": {
        "pcbs": 10, "assembled": 10, "spares": 2, "service": "Standard", "total": 328.40, "estimate": True,
        "spec": "4-layer 74×90 mm, lead-free HASL, 5 mm edge rails if JLC adds them for Standard PCBA",
        "pcb": {"board": 19.50},
        "pcba": {"setup": 25.56, "stencil": 8.21, "components": 188.05, "feeders": 64.26, "SMT": 5.90,
                 "X-ray": 16.40, "packaging": 0.52},
    },
    # v0.5, quoted on jlcpcb.com on 2026-10-19 (the user's account), from main's fab files: the gerbers,
    # the JLC BOM and CPL, which leave the hand-soldered connectors out (`from_fab`: no further cut for
    # them).  5 PCBs 4-layer ENIG (JLC adds two 5 mm rails for Standard PCBA: 86 × 140 mm), 2 assembled,
    # Standard, X-ray.  JLC flags the USB4105 (J1, J6) as hard to process ($0.03 a piece).  Two parts were
    # out of stock: the TCAN1462V (U6), quoted as its documented alternate TJA1462AT/0Z (C3234095, same
    # SOIC-8 pinout, signal improvement; both boards take it since), and the AP33772S FA01 (U1, LCSC 0),
    # left out of the quote.  U1
    # comes through JLC Global Sourcing from DigiKey (estimate): 5 at €2.09 with JLC's reported ≈ 50 %
    # markup ≈ $17.04, plus its loading fee ≈ $3, and ≈ 2 weeks for the parts to clear into JLC.
    "power-hub": {
        "pcbs": 5, "assembled": 2, "service": "Standard", "total": 242.52, "date": "2026-10-19", "from_fab": True,
        "spec": "4-layer 76×140 mm (86×140 with JLC's rails), ENIG",
        "pcb": {"engineering": 25.00, "ENIG": 18.00, "board": 7.50},
        "pcba": {"setup": 25.75, "stencil": 8.27, "components": 57.89, "feeders": 72.85, "SMT": 3.30,
                 "X-ray": 3.30, "packaging": 0.50, "special components": 0.12, "U1 global sourcing (est.)": 20.04},
    },
    # the drawer's DATA port board (v1.0, 2 layers, parts on one side) is NOT quoted either: Economic
    # PCBA (setup $8, stencil $1.50, $3 per extended part type: the USB4105, the S8B-PH and the
    # USBLC6), components at catalogue prices plus ≈ 3 % attrition, ≈ 30 joints a board.  The
    # USB4105's four shell stakes are through-hole, as on the node: JLC may add a small fee for them.
    # One per node but the converted bays' (a DATA ×4 instead): the eighth is a spare.
    "data-port": {
        "pcbs": 10, "assembled": 8, "spares": 1, "service": "Economic", "total": 34.80, "estimate": True,
        "spec": "2-layer 40×17 mm, lead-free HASL",
        "pcb": {"board": 3.00},
        "pcba": {"setup": 8.00, "stencil": 1.50, "components": 12.90, "extended parts": 9.00, "SMT": 0.40},
    },
    # the camera pod board (v1.0, 2 layers, one side), one per camera (CAMERA_SETS): an estimate built like
    # the DATA port's, Economic PCBA, $3 per extended part type (the S8B, the SMD header, the LED)
    "camera-pod": {
        "pcbs": 5, "assembled": 2, "service": "Economic", "total": 22.75, "estimate": True,
        "spec": "2-layer 40×27 mm, lead-free HASL",
        "pcb": {"board": 2.00},
        "pcba": {"setup": 8.00, "stencil": 1.50, "components": 2.05, "extended parts": 9.00, "SMT": 0.20},
    },
    # the DATA ×4 (v1.0, 4 layers, parts on one side, no module: Economic PCBA takes 4 layers), one per
    # converted bay: an estimate built like the DATA port's, $3 per extended part type (the USB2514B, its
    # crystal, the TPS2553-1, the INA226, the TCA6408A, the AP2112K, the USBLC6, the USB4105, the S8B: 9),
    # components at catalogue prices plus ≈ 3 % attrition, ≈ 390 joints a board.  The bare PCB scaled from the
    # bay node's live 4-layer price (64 × 90 mm, $19.30 for 10).  The RESET/BOOT headers are not fitted.
    "data-port-x4": {
        "pcbs": 5, "assembled": 2, "service": "Economic", "total": 76.74, "estimate": True,
        "spec": "4-layer 108×24 mm, JLC04161H-7628, lead-free HASL",
        "pcb": {"board": 9.00},
        "pcba": {"setup": 8.00, "stencil": 1.50, "components": 29.92, "extended parts": 27.00, "SMT": 1.32},
    },
}
# What the order changes against that quote (indicative, not re-quoted): the hub in lead-free HASL
# instead of ENIG, as the node (2026-10-19: $5.30 on JLC's calculator for 5 × 86 × 140 mm 4-layer, against
# the quote's $18.00 ENIG; nothing on the hub needs ENIG: 0.5 mm QFN and the MINI-1's pads are assembled
# on HASL like the node's WROOM-1, INA226 and FSUSB42); the hub's
# through-hole connectors soldered by hand (catalog hand_solder), bought loose from LCSC, so their
# extended part types no longer need loading; and no JLC hand-soldering fee on either board (the
# node's JST PH are SMD since rev 0.4, JLC places them).
JLC_FINISH = {"power-hub": ("lead-free HASL", 5.30)}
# Parts added to a board after its quote (indicative, not re-quoted): (what, PCBA line, USD for the
# quoted order).  Bay node rev 0.5: the rack bus (TCAN1044AV, PESD2CAN, 2 × BAT54S, 3 resistors, 2
# capacitors, the 6-pin J1/J2), GCT USB4105 receptacles instead of the HRO ones and 2 × 100 nF on
# the USBLC6s: +$2.38 of parts per board at catalogue prices; four new extended part types and one
# gone (the HRO), ≈ $3 loading each.  Then the TCAN1462V (signal improvement) instead of the
# TCAN1044AV: +$0.54 per board.  Then J7, the DATA header (B5B-PH-SM4-TB): +$0.30 per board and
# one more extended part type.
# (The bay node's rev 0.5 changes against the 2026-10-16 quote lived here until its estimate of
# 2026-10-19 above, which prices the board as it is.)
# Power hub, after its quote of 2026-10-19: six resistor values merged onto values the board already
# has (FB 100k/18k as the node, EN 39k/18k, INT divider 10k/18k, I²C pull-ups 5.1k), so six part types
# fewer at the quote's $1.55 a type in Standard PCBA feeders (47 → 41 placed types).
JLC_SINCE_QUOTE = {"power-hub": [("6 part types fewer (resistor values merged)", "feeders", -9.30)]}


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
    "c-to-micro-b-straight": {"supplier": "AliExpress (USB-C ↔ micro-B, straight, 15 cm, USB 2.0 data)",
                              "unit_eur": 2.0,
                              "notes": "straight at both ends, a loop over the plate (a converted bay's Pico 2): "
                                       "15 cm takes a seller's ±5 mm, 10 cm would have to be within 3; listing still "
                                       "to pick, check it says data"},
    "c-to-c-straight": {"supplier": "AliExpress (USB-C ↔ USB-C, 15–20 cm, USB 2.0 data, 480 Mbps)", "unit_eur": 2.0,
                        "notes": "straight at both ends; any short C ↔ C that states data (many short ones are "
                                 "charge-only)"},
}


# Cameras bought for a start (the user, 2026-10-18: "initialement je n'inclurai que 2 caméras"),
# whatever the viewer's `cameras` list shows; every bay node keeps J6 and its circuit, so any bay
# can take one later
CAMERA_SETS = 2


def bay_mounts(rack) -> tuple[int, int]:
    """(drawer bays, sled bays): a fixed bay is a sled bay screwed down (config/rack.yaml › population › mount)."""
    ms = [rack.mount(b.id) for b in rack.bays()]
    return ms.count("drawer"), len(ms) - ms.count("drawer")


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
    if hand and not q.get("from_fab"):            # a quote from the fab files already leaves them out
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
        changes.append(f"{what} ({'+' if usd >= 0 else '−'}${abs(usd):.2f} {line})")
    return pcb, pcba, changes


def electronics(rack) -> tuple[list[dict], dict]:
    """Per-part lines at catalogue prices for the boards JLC assembles, plus the quote's PCB and
    PCBA fees as adjusted by jlc_order(); a last line per board brings the parts up to the quote's
    components figure.  Also returns the adjusted order per board."""
    prices = _catalog_prices()
    n_nodes = rack.units * len(rack.rows)          # every carrier unit gets a node (double bays: 2nd is optional)
    n_x4 = sum(1 for b in rack.bays() if rack.is_multi(b.id))     # converted bays: a DATA ×4, no DATA port
    rows, orders = [], {}
    for name, need in (("bay-node", n_nodes), ("power-hub", 1), ("data-port", n_nodes - n_x4),
                       ("camera-pod", CAMERA_SETS), ("data-port-x4", n_x4)):
        q = JLC_QUOTE[name]
        assert abs(sum(q["pcb"].values()) + sum(q["pcba"].values()) - q["total"]) < 0.005, f"{name}: quote lines ≠ total"
        n = q["assembled"]
        if n < need or n > max(need + q.get("spares", 0), 2):     # JLC assembles at least 2 boards
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
        src = "estimate, not quoted" if q.get("estimate") else f"JLCPCB quote {q.get('date', JLC_QUOTE_DATE)}"
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
    n_bays = sum(1 for _ in rack.bays())
    cols, n_rows = rack.units, len(rack.rows)
    cams = CAMERA_SETS                      # pods printed (config cameras: the bays shown with one)
    n_drawer, n_sled = bay_mounts(rack)
    counts = Counter({
        # the panel frame: a ladder per column boundary and level, a floor plate, a cap plate and
        # an X brace per column and level
        "ladder_base": cols + 1, "ladder_cap": cols + 1, "floor_plate": cols, "cap_plate": cols, "brace_base": cols,
        "tray": n_bays, "drawer": n_drawer, "chain_foot": n_drawer, "chain_anchor": n_drawer,
        "drawer_sled": n_sled, "drawer_block": n_sled,
        "camera_pod": cams, "camera_diffuser": cams, "bay_label": n_bays,
        # the power box: base and lid, and their optional label inlays (a second, light filament)
        "power_box_base": 1, "power_box_lid": 1, "power_box_labels": 1, "power_box_lid_labels": 1,
    })
    for row in rack.rows:
        counts[f"ladder_{row['id'].lower()}"] += cols + 1
        counts[f"brace_{row['id'].lower()}"] += cols
    for bay in rack.bays():
        duts = rack.duts(bay.id)
        if rack.is_multi(bay.id):           # a converted bay: a DATA ×4 drawer / block
            part = "drawer" if rack.mount(bay.id) == "drawer" else "drawer_block"
            counts[part] -= 1
            counts[f"{part}_x4"] += 1
        if not duts or rack.plate_kind(bay.id) == "pegs":
            counts["plate"] += 1            # the honeycomb plate, and the pegs that hold its boards
            if duts:
                for peg in plate_layout.layout_bay(rack, bay.id).pegs:
                    for name, _ in peg.parts:
                        counts[name] += 1
        elif rack.is_multi(bay.id):         # `plate: boards`: the former plates
            counts[f"plate_bay_{bay.id.lower()}"] += 1
        else:
            counts[f"plate_{duts[0].board}"] += 1
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
    cams = CAMERA_SETS                      # camera pods bought, wherever they go
    braces = cols * (n_rows + 1)
    n_drawer, n_sled = bay_mounts(rack)     # sled bays: no chain, foot, anchor or magnets
    n_fixed = sum(1 for b in rack.bays() if rack.mount(b.id) == "fixed")
    chain_m = math.ceil(0.19 * n_drawer + 0.3) if n_drawer else 0   # sold by the metre, one pair of end pieces with each
    charger = r["power_box"]["charger"]
    rows = [
        {"category": "Fasteners", "item": "M3 heat-set insert, 5.7 mm (generic brass, Ruthex-compatible holes)",
         "supplier": "AliExpress (bulk) / Ruthex", "qty": 4 * (cols + 1) * (n_rows + 1) + 4 * n_bays + 2 * n_drawer + 4 * n_bays + 4,
         "unit_eur": 0.03,
         "notes": "4 in the rear edge of every base and row ladder (the braces screw in); per tray 4 node "
                  "standoffs + 2 chain anchor (drawer bays); 4 under every bay's ceiling (a camera pod's mount); power box: 4 hub "
                  "standoffs"},
        {"category": "Fasteners", "item": "M3×8 pan head, Phillips (ISO 7045): rear braces, chain anchor",
         "supplier": "AliExpress (bulk)", "qty": 4 * braces + 2 * n_drawer, "unit_eur": 0.02},
        {"category": "Fasteners", "item": "M3×6 (node PCB, power box lid, camera pods)", "supplier": "AliExpress (bulk)",
         "qty": 4 * n_bays + 4 + 4 * cams, "unit_eur": 0.02},
        {"category": "Fasteners", "item": "M3 male-female hex spacer, 12 mm + 6 mm thread, brass (≤ 5.5 mm AF)",
         "supplier": "AliExpress (bulk)", "qty": 4, "unit_eur": 0.10,
         "notes": "power box: through the hub's holes into the standoff inserts; the lid screws into their tops"},
        {"category": "Fasteners", "item": "PT 2.6×8 pan head, thread-forming for plastics (or M2.5×8 self-tapping): "
                                         "foot lock, 4 for the chain's end pieces, 2 for the DATA port board; a sled bay: 2 DATA; "
                                         "a DATA ×4: 2 more",
         "supplier": "AliExpress (bulk, e.g. HZYUEGOU)",
         "qty": 7 * n_drawer + 2 * n_sled + 2 * sum(1 for b in rack.bays() if rack.is_multi(b.id)), "unit_eur": 0.02,
         "notes": "every printed pilot for them is 2.1–2.2 mm (≈ 0.8 × d)"},
        {"category": "Fasteners", "item": "PT 2.3×8 pan head, self-tapping (M2.3×8 \"ST\", head ≤ Ø4.5): the guide lips' "
                                         "screws: a drawer bay's stop; a sled bay's stop and 2 port-block locks (and 2 sled "
                                         "locks if fixed)",
         "supplier": "AliExpress (bulk, HZYUEGOU: M2.3×8 self-tapping pan head, stainless, ≈ €2.13 / 100)",
         "qty": n_drawer + 3 * n_sled + 2 * n_fixed, "unit_eur": 0.02,
         "notes": "pilots Ø1.9 in the ledges, Ø2.6 in the lips; a Ø5 PT 2.6 head would rub the drawer's wall "
                  "(lib/carrier.scad › LIP_SCREW, checked in SolidCraft)"},
        {"category": "Fasteners", "item": "M2.5 washer, DIN 125 (chain end pieces: their tab holes can be 4.3 mm)",
         "supplier": "AliExpress (bulk)", "qty": 4 * n_drawer, "unit_eur": 0.01},
        {"category": "Fasteners", "item": "Neodymium disc magnet 6×3 mm N35, lot of 50 (drawer detent: one in the "
                                         "drawer, one in the tray ledge)",
         "supplier": "AliExpress 1005010074888189, \"6x3mm-50 pièces\"", "qty": math.ceil(2 * n_drawer / 50),
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
         "qty": max(0, n_drawer - chain_m), "unit_eur": 2.17,
         "notes": "Olimex does not sell them alone; this generic chain ships with one pair per metre.  The listing "
                  "is for the non-opening 7×7 type: check one on the open links before buying the lot"},
        # the drawer's DATA port: our own small board (electronics/data-port, in the Electronics lines)
        # on the rear-bay floor, on an 8-wire PH lead from the node's J7 through the drag chain (USB, the
        # node's I²C and INT for a later DATA ×4 board): the camera's lead too, one type for both
        # (pin n ↔ pin 9−n); 8 pins, so a 6-pin row cable cannot go in
        {"category": "Cables", "item": "JST PH 8-pin lead, pin n ↔ pin 9−n (flat, no twist), 50 cm, lot of 5 "
                                      "(DATA leads: node J7 → drag chain → DATA port board; camera leads: node J6 → "
                                      "pod J1)",
         "supplier": f"AliExpress {ROW_CABLE_URL}, \"Same direction\", 8P, Length50CM",
         "qty": math.ceil((n_bays + CAMERA_SETS) / 5), "unit": "lot", "unit_eur": 4.5,
         "notes": f"{n_bays} DATA + {CAMERA_SETS} camera leads; price interpolated from the 6-pin lots, not read: "
                  "check the 8P lengths on the listing (45–50 cm).  The DATA route is ≈ 38 cm plugs included "
                  "(constant over the stroke); the spare goes in a wider bend between the node and the chain's fixed "
                  "end (nothing moves there), never in front of the chain's moving end.  A sled bay's route is "
                  "≈ 22 cm (no chain): the slack coiled in the plenum.  On arrival: both plugs show "
                  "the same face, pin 1 rings to pin 8; twist D+/D− (pins 3-4 at the node) by hand.  Or crimp them: "
                  "PHR-8 + 16 × SPH-002T-P0.5S, 24 AWG"},
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
        {"category": "Cables", "item": "Cable tie 2.5 × 100 mm: the row jumpers, 2 each, through the tray's two tie "
                                      "anchors at its front right (docs/cabling.md)",
         "supplier": "AliExpress (bulk)", "qty": 2 * sum(cols - 1 for _ in rack.rows), "unit_eur": 0.02},
        *[{"category": "Cables", "item": f"JST PH 6-pin feed, the jumpers' type, {cm} cm, lot of 5 (power box → first "
                                         f"bay of row {', '.join(rows_)}: VRACK, CAN, POS)",
           "supplier": f"AliExpress {ROW_CABLE_URL}, \"Same direction\", 6P, Length{cm}CM",
           "qty": math.ceil(len(rows_) / 5), "unit": "lot", "unit_eur": price,
           "notes": "checked as the jumpers; the listing doesn't give the gauge (26 AWG is usual): fine for a row's "
                    "≈ 0.4 A, warm at the eFuse's 1.6 A limit; twist the CAN pair (pins 3-4) by hand"}
          for cm, price, rows_ in _feed_lots(rack)],
    ]
    duts = [d for b in rack.bays() for d in rack.duts(b.id) if d.cable]   # one cable per board under test
    cab = Counter(d.cable for d in duts)
    lib = rackcfg.load_boards()
    for k, n in sorted(cab.items()):
        src = DUT_CABLES.get(k, {"supplier": "AliExpress", "unit_eur": 3.0})
        boards = ", ".join(sorted({lib[d.board].get("short", d.board) for d in duts if d.cable == k}))
        rows.append({"category": "Cables", "item": f"{r['cables'][k]['label']} (DUT cable: {boards})",
                     "supplier": src["supplier"], "qty": n, "unit_eur": src["unit_eur"],
                     "notes": src.get("notes", "")})
    # 90° adapters for the micro-B / mini-B boards whose USB faces the port wall (cable style adapter): one
    # bent up and one bent down per board, the socket's orientation deciding which one serves
    ada = Counter(r["cables"][d.cable]["b"] for d in duts if r["cables"][d.cable].get("style") == "adapter")
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
            # (the camera lead, node J6 → pod J1, is the DATA lead's type: in the Cables lines)
            {"category": "Cameras", "item": "Cable JST XH 2.54 6-pin → Dupont female, one 6-pin housing, 10–20 cm "
                                           "(the Mega → pod J2, VCC GND SCK MISO MOSI CS in order)",
             "supplier": "AliExpress", "qty": cams, "unit_eur": 0.5,
             "notes": "the Mega's own 6-pin cable does if it ends in Dupont sockets; J2's pins are named on the "
                      "board, so the wires go on by name"},
            {"category": "Cameras", "item": "Pod hardware: 2 × PT 2.6×14 (the pod board, through the diffuser's "
                                           "posts), cable ties 2.5 × 100 (the lead: 1 at the tray's rear slot, 3 "
                                           "under the ceiling)",
             "supplier": "AliExpress (bulk)", "qty": cams, "unit": "set", "unit_eur": 0.3},
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
           "## JLCPCB orders (estimates)", "",
           f"USD, without shipping ({JLC_SHIPPING}) and import VAT.  The power hub is a real quote (jlcpcb.com, "
           "2026-10-19, from the fab files; its AP33772S, out of stock, is a Global Sourcing estimate on top).  "
           "Every other board is an **estimate** built from JLC's fees and catalogue prices: the node's last real "
           f"quote ({JLC_QUOTE_DATE}: 20 PCBs ENIG, 16 assembled, $367.71) priced it before rev 0.5.  The "
           "bay node is the order the user chose on 2026-10-19: 10 PCBs, lead-free HASL, 10 assembled (8 bays, "
           "2 spares).  The per-part lines below use catalogue prices; a *Components* line per board brings them "
           "up to the estimated components figure.  *Order* applies what changed since: the through-hole "
           "connectors hand-soldered from loose LCSC parts (LCSC shipping extra).  Re-quote before ordering (the "
           "full PCBA quote needs the user's JLC sign-in), and check the AP33772S's sourcing (out of stock at LCSC "
           "on 2026-10-18).", "",
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
