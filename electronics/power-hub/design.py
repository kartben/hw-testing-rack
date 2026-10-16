"""Power hub — one per shelf, in the base next to the PSU.

24 V from the Mean Well UHP-200-24 (or the external-brick variant) comes in
on a JST VH connector (10 A: the whole rack's ≤ 7.3 A), goes through a
reverse-polarity P-FET and a 1.5 kW TVS, then fans out to five outputs
(rows A–D + AUX: roof accessories, top-row cameras…).  Each output has its
own TPS26600 eFuse:
  * current limit ≈ 1.6 A (RILIM 7.5k): it protects the JST PH (2 A) row
    connector and the daisy chain, whose worst case (four DUTs at their own
    1.5 A limit at once) is ≈ 1.9 A; a realistic row draws ≈ 0.5 A;
  * slow start (dVdT 22 nF ≈ 4 ms at 24 V) so hot-plugging a row of bay
    nodes never browns out the others;
  * internal UV 15 V / OV 33 V defaults;
  * green "ON" and red "FAULT" LEDs per row;
  * SHDN / FLT / IMON brought to an (unpopulated) 2×8 header for a future
    supervisor (row power-cycling, current telemetry).
2 layers, 120 × 70 mm, screwed to the base hub mount.

Schematic: every part has an `sch=` position (0.1" grid units, see
electronics/tools/eda.py); the five outputs are one drawing, repeated.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
sys.path.insert(0, str(HERE.parents[1] / "tools"))

from catalog import C, R, part  # noqa: E402
from eda import Board  # noqa: E402

import rackcfg  # noqa: E402

RACK = rackcfg.load()
CFG = RACK.raw["pcb"]["power_hub"]
W, H = CFG["size"]
CHANNELS = ["A", "B", "C", "D", "AUX"]


def P(x, y, rot=0):
    return {"x": x, "y": y, "rot": rot}


def at(x, y, rot=0, mirror="", fields=None):
    """Schematic position in 0.1" grid units."""
    d = {"x": x, "y": y, "rot": rot}
    if mirror:
        d["mirror"] = mirror
    if fields is not None:
        d["fields"] = fields
    return d


def board() -> Board:
    b = Board("power-hub", "Power hub", "0.2",
              comments=["24 V distribution for the hw-testing-rack shelf: 5 eFused outputs",
                        "Generated from electronics/power-hub/design.py — edit the Python, then regenerate"])
    b.root_notes = [
        "Power hub — 24 V in (JST VH) → reverse protection + TVS → 5 × TPS26600 eFuse (1.6 A) → JST PH outputs.",
        "Outputs: rows A, B, C, D (one feed per row, daisy-chained bay to bay) and AUX.",
        "RTN is tied to GND: reverse polarity is handled by Q1, so the eFuses' own reverse blocking is not needed.",
    ]
    xs = [40 + i * 16 for i in range(len(CHANNELS))]         # eFuse centres (y = 30, IN pins at the bottom)
    b.pcb = {
        "size": (W, H), "layers": CFG["layers"], "corner_radius": 3.0, "passes": 40,
        "stackup": "2L-1.6", "finish": "HAL lead-free",
        # The input carries the whole rack (≤ 7.3 A, 8 A if all five eFuses sit at their limit): the
        # 24 V path is copper pours, not 1.5 mm tracks.  VIN_RAW: J1 → Q1's drain tab (also Q1's heat
        # spreader, ~1 W at 7 A).  +24V: Q1's source, D2, C1/C2 and a top-side branch, vias down to a
        # bottom-side strip under the eFuse row, and per eFuse a top island on its IN pins with two
        # vias into that strip.  The rest of B.Cu stays the GND pour (added after routing).  The pours
        # are there while routing, and "exclusive" keeps other nets' tracks out of them.
        "zones": [
            {"layer": "B.Cu", "net": "GND"},
            {"layer": "F.Cu", "net": "VIN_RAW", "name": "vin-raw", "priority": 2, "defer": False, "connection": "solid",
             "exclusive": 0.6,
             "poly": [(3.6, 32.6), (9.5, 32.6), (9.5, 42.3), (22.3, 42.3), (22.3, 56.0), (7.3, 56.0), (7.3, 37.0),
                      (3.6, 37.0)]},
            {"layer": "F.Cu", "net": "+24V", "name": "24v-trunk", "priority": 2, "defer": False, "connection": "solid",
             "exclusive": 0.6,
             "poly": [(8.0, 9.6), (13.4, 9.6), (13.4, 14.4), (20.9, 14.4), (20.9, 9.6), (26.4, 9.6), (26.4, 17.4),
                      (17.6, 17.4), (17.6, 31.0), (33.6, 31.0), (33.6, 37.6), (17.6, 37.6), (17.6, 41.8), (9.8, 41.8),
                      (9.8, 14.4), (8.0, 14.4)]},
            {"layer": "B.Cu", "net": "+24V", "name": "24v-strip", "priority": 1, "defer": False, "connection": "solid",
             "exclusive": 0.6,
             "poly": [(30.4, 33.8), (106.6, 33.8), (106.6, 38.2), (30.4, 38.2)]},
            *[{"layer": "F.Cu", "net": "+24V", "name": f"24v-in-{ch}", "priority": 2, "defer": False, "exclusive": 0.5,
               "poly": [(x - 4.25, 32.15), (x - 1.42, 32.15), (x - 1.42, 35.5), (x - 4.25, 35.5)]}
              for x, ch in zip(xs, CHANNELS)],
        ],
        "vias": [
            # trunk branch → bottom strip
            *[("+24V", x, y, 0.8, 0.4) for x in (31.0, 32.1, 33.0) for y in (34.6, 36.8)],
            # each eFuse: IN island → strip, and six GND vias in the exposed pad's copper, outside its
            # 2.46 × 2.66 mm solder-mask opening (tented: no solder wicks down) to the B.Cu GND pour
            *[v for x in xs for v in (("+24V", x - 3.55, 34.85, 0.8, 0.4), ("+24V", x - 2.3, 34.85, 0.8, 0.4),
                                      *[("GND", x + dx, y) for dx in (-1.85, 1.85) for y in (29.1, 30.0, 30.9)])],
        ],
        "keepouts": [],
        "texts": [
            {"text": "hw-testing-rack · power hub v0.2", "x": 60, "y": 66.5, "size": 1.2},
            {"text": "24V IN", "x": 5.5, "y": 45, "size": 1.0},
            *[{"text": ch, "x": 40 + i * 16, "y": 12.5, "size": 1.2} for i, ch in enumerate(CHANNELS)],
        ],
    }

    s = b.sheet("Input", "input.kicad_sch", "24 V input and protection")
    s.frame("24 V input (Mean Well PSU or brick, JST VH), reverse-polarity P-FET, TVS, bulk", 6, 6, 60, 27)
    part(s, "J1", "vh_v", {"1": "VIN_RAW", "2": "GND"}, "24V IN", pcb=P(5.6, 35, 270),
         sch=at(10, 12, mirror="y", fields="left"))
    s.part("#FLG01", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "VIN_RAW"}, in_bom=False, on_board=False,
           sch=at(17, 12, fields=(-3.8, -2.6)))
    s.part("#FLG02", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "GND"}, in_bom=False, on_board=False,
           sch=at(15, 13, fields=(0.6, 1.0)))
    s.part("#FLG03", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+24V"}, in_bom=False, on_board=False,
           sch=at(55, 12, fields=(-3.8, -2.6)))
    part(s, "Q1", "pfet", {"G": "Q1_GATE", "D": "VIN_RAW", "S": "+24V"}, pcb=P(18, 45, 270),
         sch=at(22, 13, rot=90, fields=(-8.5, 4)))
    part(s, "D1", "zener12", {"K": "+24V", "A": "Q1_GATE"}, pcb=P(26, 52, 0), sch=at(27, 15.5, rot=270))
    R(s, "R1", "100k", "Q1_GATE", "GND", pcb=P(26, 55.5, 0), sch=at(22, 19.5))
    part(s, "D2", "tvs33c", {"K": "+24V", "A": "GND"}, pcb=P(18, 27, 0), sch=at(33, 15.5, rot=270))
    part(s, "C1", "cap220u50", {"1": "+24V", "2": "GND"}, "220u/50V", pcb=P(14.5, 12, 0), sch=at(39, 15.5))
    part(s, "C2", "cap220u50", {"1": "+24V", "2": "GND"}, "220u/50V", pcb=P(27.5, 12, 0), sch=at(45, 15.5))
    R(s, "R2", "10k", "+24V", "PWR_LED", size="0805", pcb=P(19, 64, 0), sch=at(51, 13.5))
    part(s, "D3", "led_g", {"A": "PWR_LED", "K": "GND"}, "24V", pcb=P(14, 64, 0), sch=at(51, 18.5, rot=90))
    s.wire("J1.1", "Q1.D")
    s.wire("J1.2", (15, 13))
    s.tag("GND", (14, 13), "down")
    s.wire("Q1.G", "R1.1")
    s.wire((22, 17), "D1.A")
    for ref, x in (("D1.K", 27), ("D2.K", 33), ("C1.1", 39), ("C2.1", 45), ("R2.1", 51)):
        s.wire((x, 12), ref)
    s.wire("R2.2", "D3.A")
    s.tag("PWR_LED", (51, 16), "right")
    s.wire("Q1.S", (57, 12))
    s.tag("+24V", (57, 12), "up")
    s.notes_at = (6, 31, 100)
    s.note("Q1: drain to the connector, source to the load; the 12 V zener keeps |Vgs| inside ±20 V.")
    s.note("SMCJ33A: 33 V stand-off, ≤ 53 V clamp — below the TPS26600's 60 V rating.")
    s.note("J1 is a JST VH (10 A per contact): the hub input carries the whole rack, ≤ 7.3 A at 24 V.")

    o = b.sheet("Outputs", "outputs.kicad_sch", "Five eFused row outputs")
    hdr = {}
    for i, ch in enumerate(CHANNELS):
        n = i + 1
        x = 40 + i * 16
        ox, oy = 2 + 52 * (i % 3), 2 + 30 * (i // 3)

        def g(dx, dy):
            return ox + dx, oy + dy
        o.frame(f"Output {ch}: TPS26600 eFuse, 1.6 A", ox + 3, oy + 4, ox + 52, oy + 28)
        part(o, f"U{n}", "efuse", {"IN": "+24V", "GND": "GND", "RTN": "GND", "UVLO": "GND", "OVP": "GND",
                                   "MODE": "GND", "~{SHDN}": f"SHDN_{ch}", "ILIM": f"ILIM_{ch}", "dVdT": f"DVDT_{ch}",
                                   "IMON": f"IMON_{ch}", "~{FLT}": f"FLT_{ch}", "OUT": f"ROW_{ch}"},
             pcb=P(x, 30, 90), sch=at(*g(24, 16), fields=(-4, -9.5)))
        u = f"U{n}"
        # input: +24V, decoupling (right next to the IN pins, on their +24V island), SHDN pull-up (the
        # supervisor header may pull it low)
        o.tag("+24V", g(6, 8), "up")
        o.wire(g(6, 8), g(17, 8), g(17, 11), f"{u}.IN")
        C(o, f"C{10 + n}", "1u", "+24V", "GND", size="0805", pcb=P(x - 4.6, 33.3, 180), sch=at(*g(10, 9.5)))
        o.wire(g(10, 8), f"C{10 + n}.1")
        R(o, f"R{10 + n}", "470k", "+24V", f"SHDN_{ch}", pcb=P(x - 5, 36, 90), sch=at(*g(14, 11.5)))
        o.wire(g(14, 8), f"R{10 + n}.1")
        o.wire(f"R{10 + n}.2", g(14, 21), f"{u}.~{{SHDN}}")
        o.tag(f"SHDN_{ch}", g(14, 21), "left")
        # output: ROW_x to the JST PH, output cap, ON LED
        part(o, f"J{1 + n}", "ph2v", {"1": f"ROW_{ch}", "2": "GND"}, f"ROW {ch}", pcb=P(x - 1, 6, 0),
             sch=at(*g(49, 8), fields=(-2.5, -2.6)))
        o.wire(f"{u}.OUT", g(31, 11), g(31, 8), f"J{1 + n}.1")
        o.wire(f"J{1 + n}.2", g(45, 9), g(45, 11))
        o.tag("GND", g(45, 11), "down")
        C(o, f"C{30 + n}", "1u", f"ROW_{ch}", "GND", size="0805", pcb=P(x - 4.6, 26.6, 180), sch=at(*g(35, 9.5)))
        o.wire(g(35, 8), f"C{30 + n}.1")
        R(o, f"R{40 + n}", "10k", f"ROW_{ch}", f"ON_{ch}", size="0805", pcb=P(x - 3, 52, 90), sch=at(*g(40, 9.5)))
        o.wire(g(40, 8), f"R{40 + n}.1")
        part(o, f"D{10 + n}", "led_g", {"A": f"ON_{ch}", "K": "GND"}, "ON", pcb=P(x - 3, 47, 90),
             sch=at(*g(40, 14.5), rot=90))
        o.wire(f"R{40 + n}.2", f"D{10 + n}.A")
        # current limit, soft start, current monitor
        R(o, f"R{20 + n}", "7.5k", f"ILIM_{ch}", "GND", pcb=P(x + 5, 36, 90), sch=at(*g(33, 21.5)))
        o.wire(f"{u}.ILIM", f"R{20 + n}.1")
        C(o, f"C{20 + n}", "22n", f"DVDT_{ch}", "GND", pcb=P(x + 5, 39.5, 90), sch=at(*g(31, 22.5)))
        o.wire(f"{u}.dVdT", f"C{20 + n}.1")
        R(o, f"R{30 + n}", "18k", f"IMON_{ch}", "GND", pcb=P(x - 5, 39.5, 90), sch=at(*g(38, 18.5), fields="left"))
        o.wire(f"{u}.IMON", f"R{30 + n}.1")
        # FAULT LED: +24V → R → LED → ~FLT (open drain)
        R(o, f"R{50 + n}", "10k", "+24V", f"FLTLED_{ch}", size="0805", pcb=P(x + 3, 52, 90), sch=at(*g(48, 14.5)))
        part(o, f"D{20 + n}", "led_r", {"A": f"FLTLED_{ch}", "K": f"FLT_{ch}"}, "FAULT", pcb=P(x + 3, 47, 90),
             sch=at(*g(48, 20.5), rot=90))
        o.wire(f"R{50 + n}.2", f"D{20 + n}.A")
        o.wire(f"D{20 + n}.K", g(48, 23), g(46, 23))
        o.tag(f"FLT_{ch}", g(46, 23), "left")
        hdr[ch] = (f"SHDN_{ch}", f"FLT_{ch}", f"IMON_{ch}")
    o.notes_at = (110, 36, 50)
    o.note("TPS26600: I_LIM ≈ 12 A·kΩ / R_ILIM")
    o.note("  → 7.5k ≈ 1.6 A (JST PH: 2 A per contact).")
    o.note("t_dVdT = 8e3 · V_IN · C_dVdT")
    o.note("  → 22 nF ≈ 4.2 ms at 24 V.")
    o.note("IMON: 78 µA/A into 18k → 1.4 V/A")
    o.note("  (2.2 V at the limit), for a future")
    o.note("  supervisor's ADC.")
    o.note("UVLO / OVP / MODE to GND: internal")
    o.note("  15 V / 33 V thresholds, auto-retry.")

    c = b.sheet("Control", "control.kicad_sch", "Supervisor header and mounting")
    c.frame("Supervisor header (DNP): SHDN pulls a row off, FLT open-drain, IMON analog", 6, 6, 70, 34)
    pins = {}
    k = 1
    for kind in range(3):
        for ch in CHANNELS:
            pins[str(k)] = hdr[ch][kind]
            k += 1
    pins["16"] = "GND"
    part(c, "J7", "hdr2x8", pins, "SUPERVISOR", pcb=P(84, 62, 90), dnp=True, sch=at(36, 20, fields=(-2, -6)))
    c.frame("Mounting (M3)", 6, 38, 50, 50)
    for i, (x, y) in enumerate(CFG["holes"]):
        part(c, f"H{i + 1}", "hole", {}, "M3", pcb=P(x, y, 0), in_bom=False, sch=at(12 + 9 * i, 44))
    return b


NETCLASSES = [
    {"name": "Power", "clearance": 0.2, "track_width": 1.5, "via_diameter": 1.0, "via_drill": 0.5,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 1,
     # +24V carries its current in pours (see b.pcb["zones"]); its tracks only feed pull-ups and LEDs
     "_patterns": ["*VIN_RAW", "*ROW_*"]},
]
