"""Power hub — one per shelf, in the base next to the PSU.

24 V from the Mean Well UHP-200-24 (or the external-brick variant) comes in
on a screw terminal, goes through a reverse-polarity P-FET and a 1.5 kW TVS,
then fans out to five outputs (rows A–D + AUX: roof accessories, top-row
cameras…).  Each output has its own TPS26600 eFuse:
  * current limit ≈ 2.1 A (RILIM 5.6k), auto-retry;
  * slow start (dVdT 22 nF ≈ 4 ms at 24 V) so hot-plugging a row of bay
    nodes never browns out the others;
  * internal UV 15 V / OV 33 V defaults;
  * green "ON" and red "FAULT" LEDs per row;
  * SHDN / FLT / IMON brought to an (unpopulated) 2×8 header for a future
    supervisor (row power-cycling, current telemetry).
2 layers, 120 × 70 mm, screwed to the base hub mount.
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


def board() -> Board:
    b = Board("power-hub", "Power hub", "0.1",
              comments=["24 V distribution for the hw-testing-rack shelf: 5 eFused outputs",
                        "Generated from electronics/power-hub/design.py — edit the Python, then regenerate"])
    b.root_notes = [
        "Power hub — 24 V in (screw terminal) → reverse protection + TVS → 5 × TPS26600 eFuse → JST VH outputs.",
        "Outputs: rows A, B, C, D (one feed per row, daisy-chained bay to bay) and AUX.",
        "RTN is tied to GND: reverse polarity is handled by Q1, so the eFuses' own reverse blocking is not needed.",
    ]
    b.pcb = {
        "size": (W, H), "layers": CFG["layers"], "corner_radius": 3.0, "passes": 40,
        "zones": [{"layer": "B.Cu", "net": "GND"}],
        "keepouts": [],
        "texts": [
            {"text": "hw-testing-rack · power hub v0.1", "x": 60, "y": 66.5, "size": 1.2},
            {"text": "24V IN", "x": 5, "y": 46, "size": 1.0},
            *[{"text": ch, "x": 40 + i * 16, "y": 13.5, "size": 1.2} for i, ch in enumerate(CHANNELS)],
        ],
    }

    s = b.sheet("Input", "input.kicad_sch", "24 V input and protection")
    s.block("24 V input (PSU or brick), reverse-polarity P-FET, TVS, bulk")
    part(s, "J1", "terminal", {"1": "VIN_RAW", "2": "GND"}, "24V IN", pcb=P(5, 35, 270))
    s.part("#FLG01", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "VIN_RAW"}, in_bom=False, on_board=False)
    s.part("#FLG02", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "GND"}, in_bom=False, on_board=False)
    s.part("#FLG03", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+24V"}, in_bom=False, on_board=False)
    part(s, "Q1", "pfet", {"G": "Q1_GATE", "D": "VIN_RAW", "S": "+24V"}, pcb=P(18, 45, 270))
    part(s, "D1", "zener12", {"K": "+24V", "A": "Q1_GATE"}, pcb=P(26, 52, 0))
    R(s, "R1", "100k", "Q1_GATE", "GND", pcb=P(26, 55.5, 0))
    part(s, "D2", "tvs33c", {"K": "+24V", "A": "GND"}, pcb=P(18, 27, 0))
    part(s, "C1", "cap220u50", {"1": "+24V", "2": "GND"}, "220u/50V", pcb=P(14.5, 12, 0))
    part(s, "C2", "cap220u50", {"1": "+24V", "2": "GND"}, "220u/50V", pcb=P(27.5, 12, 0))
    part(s, "D3", "led_g", {"A": "PWR_LED", "K": "GND"}, "24V", pcb=P(14, 64, 0))
    R(s, "R2", "10k", "+24V", "PWR_LED", size="0805", pcb=P(19, 64, 0))
    s.note("Q1: drain to the terminal, source to the load; the 12 V zener keeps |Vgs| inside ±20 V.")
    s.note("SMCJ33A: 33 V stand-off, ≤ 53 V clamp — below the TPS26600's 60 V rating.")

    o = b.sheet("Outputs", "outputs.kicad_sch", "Five eFused row outputs")
    hdr = {}
    for i, ch in enumerate(CHANNELS):
        n = i + 1
        x = 40 + i * 16
        o.block(f"Output {ch}")
        part(o, f"U{n}", "efuse", {"IN": "+24V", "GND": "GND", "RTN": "GND", "UVLO": "GND", "OVP": "GND",
                                   "MODE": "GND", "~{SHDN}": f"SHDN_{ch}", "ILIM": f"ILIM_{ch}", "dVdT": f"DVDT_{ch}",
                                   "IMON": f"IMON_{ch}", "~{FLT}": f"FLT_{ch}", "OUT": f"ROW_{ch}"},
             pcb=P(x, 30, 90))
        C(o, f"C{10 + n}", "1u", "+24V", "GND", size="0805", pcb=P(x - 5, 24, 90))
        R(o, f"R{10 + n}", "470k", "+24V", f"SHDN_{ch}", pcb=P(x - 5, 36, 90))
        R(o, f"R{20 + n}", "5.6k", f"ILIM_{ch}", "GND", pcb=P(x + 5, 36, 90))
        C(o, f"C{20 + n}", "22n", f"DVDT_{ch}", "GND", pcb=P(x + 5, 39.5, 90))
        R(o, f"R{30 + n}", "18k", f"IMON_{ch}", "GND", pcb=P(x - 5, 39.5, 90))
        part(o, f"J{1 + n}", "vh_v", {"1": f"ROW_{ch}", "2": "GND"}, f"ROW {ch}", pcb=P(x - 2, 6, 0))
        C(o, f"C{30 + n}", "1u", f"ROW_{ch}", "GND", size="0805", pcb=P(x + 5, 24, 90))
        part(o, f"D{10 + n}", "led_g", {"A": f"ON_{ch}", "K": "GND"}, "ON", pcb=P(x - 3, 47, 90))
        R(o, f"R{40 + n}", "10k", f"ROW_{ch}", f"ON_{ch}", size="0805", pcb=P(x - 3, 52, 90))
        part(o, f"D{20 + n}", "led_r", {"A": f"FLTLED_{ch}", "K": f"FLT_{ch}"}, "FAULT", pcb=P(x + 3, 47, 90))
        R(o, f"R{50 + n}", "10k", "+24V", f"FLTLED_{ch}", size="0805", pcb=P(x + 3, 52, 90))
        hdr[ch] = (f"SHDN_{ch}", f"FLT_{ch}", f"IMON_{ch}")
    o.note("TPS26600: I_LIM ≈ 12 A·kΩ / R_ILIM → 5.6k ≈ 2.1 A;  t_dVdT = 8e3 · V_IN · C_dVdT → 22 nF ≈ 4.2 ms at 24 V.")
    o.note("IMON: 78 µA/A into 18k → 1.4 V/A (3.0 V at the limit), for a future supervisor's ADC.")

    c = b.sheet("Control", "control.kicad_sch", "Supervisor header and mounting")
    c.block("Supervisor header (DNP): SHDN pull-low to switch a row off, FLT open-drain, IMON analog")
    pins = {}
    k = 1
    for kind in range(3):
        for ch in CHANNELS:
            pins[str(k)] = hdr[ch][kind]
            k += 1
    pins["16"] = "GND"
    part(c, "J7", "hdr2x8", pins, "SUPERVISOR", pcb=P(84, 62, 90), dnp=True)
    for i, (x, y) in enumerate(CFG["holes"]):
        part(c, f"H{i + 1}", "hole", {}, "M3", pcb=P(x, y, 0), in_bom=False)
    return b


NETCLASSES = [
    {"name": "Power", "clearance": 0.2, "track_width": 1.5, "via_diameter": 1.0, "via_drill": 0.5,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 1,
     "_patterns": ["*VIN_RAW", "+24V", "*ROW_*"]},
]
