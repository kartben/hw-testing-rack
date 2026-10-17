"""Power hub v0.4 — one per rack, in the power box under A1 (mechanical/parts/power_box.scad).

24 V from the brick in the box (Mean Well GST60A24, its DC cord crimped into a JST VH) goes
through a reverse-polarity P-FET and a 1.5 kW TVS, then fans out to four rows (A–D).  Each row has
its own TPS26600 eFuse:
  * current limit ≈ 1.6 A (RILIM 7.5k): it protects the JST PH (2 A) row cable;
  * slow start (dVdT 22 nF ≈ 4 ms at 24 V), so hot-plugging a row never browns out the others;
  * internal UV 15 V / OV 33 V defaults, auto-retry;
  * ON (green, on the row's own 24 V) and FAULT (red, from the open-drain FLT) side-view LEDs in the
    box's front wall.
The rack controller sits on the same board: an ESP32-S3-MINI-1 (Wi-Fi, the CAN master) powered
by a 24 → 5 V buck and a 3.3 V LDO (or from its own USB-C when 24 V is off, through a diode OR).  It reads each
row's FLT and IMON, can switch a row off (an NFET pulls the eFuse's SHDN low; a divider from 24 V
keeps SHDN high, so every row is on without firmware), and runs the rack's CAN bus and the POS
addressing token (docs/can.md).  The row outputs are 6-pin JST PH: 24 V, GND, CAN_H, CAN_L, GND,
POS.  The bus is a star: every port carries the same CAN pair, both terminations are here.

2 layers, 76 × 140 mm (config/rack.yaml › pcb.power_hub: outline, holes, connector and LED
positions, which the box is drawn around).  KiCad coordinates: y = 0 is the REAR edge (the ESP32's
antenna), y = 140 the FRONT edge (LEDs, USB-C); the row connectors sit on the left edge.

Schematic: automatic layout (blocks), not drawn yet.
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
ROWS = ["A", "B", "C", "D"]
ROW_Y = CFG["rows"]                 # KiCad y of each row connector (left edge)
LED_X = CFG["front"]["leds"]        # ON/FAULT pair centres A–D, then 24V, CTL
USB_X = CFG["front"]["usb"]
PH_EDGE = 4.9                       # JST PH side entry: footprint origin from the board edge (as the bay node)
LED_Y = H - 1.25                    # side-view LED, lens at the front edge (rot 180)
EF_X = 26.0                         # eFuse centre (rot 0: IN on the left, OUT on the right, both at the top)
TRUNK_X = (19.0, 22.5)              # B.Cu +24V trunk along the eFuse column
CAN_X = (10.6, 11.6)                # B.Cu CAN_H / CAN_L along the connector column


def P(x, y, rot=0, side="top"):
    return {"x": x, "y": y, "rot": rot, "side": side}


def ef_y(k):
    return ROW_Y[k] - 0.5


def board() -> Board:
    b = Board("power-hub", "Power hub", "0.4",
              comments=["24 V distribution + rack controller (ESP32-S3, CAN master) for the hw-testing-rack",
                        "Generated from electronics/power-hub/design.py — edit the Python, then regenerate"])
    b.root_notes = [
        "Power hub v0.4 — 24 V in (JST VH) → reverse protection + TVS → 4 × TPS26600 eFuse (1.6 A) → 6-pin JST PH rows A–D.",
        "Rack controller: ESP32-S3-MINI-1, TCAN1044AV (CAN master, star bus, both terminations here), POS token per row.",
        "Every row is on without firmware: a 1M/150k divider from 24 V holds SHDN high; the controller's NFET pulls it low.",
    ]

    # ------------------------------------------------------------------ PCB
    # B.Cu: down the eFuse column, and across to the input strip at y ≈ 100
    trunk = [(TRUNK_X[0], ef_y(3) - 5.5), (TRUNK_X[1], ef_y(3) - 5.5), (TRUNK_X[1], 98.2), (60.0, 98.2),
             (60.0, 101.8), (TRUNK_X[1], 101.8), (TRUNK_X[1], ef_y(0) + 1.0), (TRUNK_X[0], ef_y(0) + 1.0)]
    in_islands = [{"layer": "F.Cu", "net": "+24V", "name": f"24v-in-{ch}", "priority": 2, "exclusive": 0.4,
                   "connection": "solid",
                   "poly": [(19.6, ef_y(k) - 2.65), (23.85, ef_y(k) - 2.65), (23.85, ef_y(k) - 1.35), (19.6, ef_y(k) - 1.35)]}
                  for k, ch in enumerate(ROWS)]
    row_tracks = []
    for k, ch in enumerate(ROWS):
        yc = ef_y(k)
        # OUT (pins 15/16, x = EF_X + 2.9) → up over the eFuse → left to the connector's pin 1 (rear pad)
        row_tracks.append((f"ROW_{ch}", "F.Cu", 0.8, [(EF_X + 2.9, yc - 1.95), (EF_X + 4.6, yc - 1.95),
                                                    (EF_X + 4.6, yc - 4.5), (9.4, yc - 4.5)]))
        # … and a branch to the output capacitor C3x
        row_tracks.append((f"ROW_{ch}", "F.Cu", 0.8, [(EF_X + 4.6, yc - 2.6), (33.05, yc - 2.6)]))
    b.pcb = {
        "size": (W, H), "layers": CFG["layers"], "corner_radius": 3.0, "passes": 60,
        "stackup": "2L-1.6", "finish": "ENIG",       # the ESP32 module's LGA pads want a flat finish
        "edge_parts": ["J*", "U4", "D1*", "D2*", "D3", "D8"],
        "zones": [
            {"layer": "B.Cu", "net": "GND"},
            {"layer": "F.Cu", "net": "GND"},
            # +24V: the input pour (Q1's source, the TVS, the bulk caps) on F.Cu, a B.Cu trunk across the
            # board and down the eFuse column, and per eFuse a top island on its IN pins with two vias
            {"layer": "F.Cu", "net": "+24V", "name": "24v-input", "priority": 2, "defer": False, "connection": "solid",
             "exclusive": 0.6, "poly": [(52.0, 61.5), (64.6, 61.5), (64.6, 101.0), (52.0, 101.0)]},
            {"layer": "B.Cu", "net": "+24V", "name": "24v-trunk", "priority": 1, "defer": False, "connection": "solid",
             "exclusive": 0.6, "poly": trunk},
            *in_islands,
            # J1 → Q1's drain tab: the brick's whole current
            {"layer": "F.Cu", "net": "VIN_RAW", "name": "vin-raw", "priority": 3, "defer": False, "connection": "solid",
             "exclusive": 0.6, "poly": [(60.0, 121.0), (75.0, 121.0), (75.0, 101.4), (62.6, 101.4), (62.6, 111.6),
                                        (64.4, 111.6), (64.4, 116.2), (60.0, 116.2)]},
            # buck hot loop (as the bay node, TI SLUSF64B §8.4)
            {"layer": "F.Cu", "net": "GND", "connection": "solid", "name": "buck-gnd", "priority": 3,
             "poly": [(58.05, 12.5), (60.1, 12.5), (60.1, 14.2), (61.9, 14.2), (61.9, 18.3), (70.6, 18.3), (70.6, 22.4),
                      (58.05, 22.4)]},
            {"layer": "F.Cu", "net": "+5V_BUCK", "connection": "solid", "name": "buck-5v", "priority": 3,
             "poly": [(62.8, 16.1), (67.3, 16.1), (67.3, 8.6), (71.0, 8.6), (71.0, 17.9), (62.8, 17.9)]},
            {"layer": "F.Cu", "net": "+24V", "connection": "solid", "name": "buck-vin", "priority": 3,
             "poly": [(55.6, 12.5), (57.8, 12.5), (57.8, 20.7), (55.6, 20.7)]},
        ],
        "vias": [
            ("GND", 61.0, 14.9), ("GND", 61.0, 17.4), ("GND", 61.2, 21.4), ("GND", 63.0, 21.6), ("GND", 65.25, 21.6),
            ("GND", 67.75, 21.6), ("GND", 70.0, 21.6),
            # eFuse IN islands down to the trunk; exposed pads: six tented GND vias each
            *[v for k in range(4) for v in (("+24V", 20.9, ef_y(k) - 2.0, 0.8, 0.4), ("+24V", 22.1, ef_y(k) - 2.0, 0.8, 0.4),
                                            *[("GND", EF_X + dx, ef_y(k) + dy) for dx in (-0.9, 0.9) for dy in (-0.9, 0.0, 0.9)])],
            # the F.Cu input strip down to the B.Cu trunk
            *[("+24V", x, y, 0.8, 0.4) for x in (53.5, 55.0, 56.5, 58.0) for y in (99.0, 100.3)],
        ],
        "tracks": row_tracks,
        # ESP32 antenna: no copper on any layer under/around it (module top 5 mm + the rear edge)
        "keepouts": [{"name": "antenna", "poly": [(21.3, -0.1), (38.7, -0.1), (38.7, 5.6), (21.3, 5.6)]}],
        "texts": [
            {"text": "hw-testing-rack · power hub v0.4", "x": 44, "y": 60, "size": 1.0},
            {"text": "24V IN", "x": 57.0, "y": 122.5, "size": 0.9},
            *[{"text": ch, "x": 12.5, "y": ROW_Y[k] + 7.6, "size": 1.2} for k, ch in enumerate(ROWS)],
        ],
    }

    # ------------------------------------------------------------------ input
    s = b.sheet("Input", "input.kicad_sch", "24 V input and protection")
    s.block("24 V input (the brick's DC cord on a JST VH), reverse-polarity P-FET, TVS, bulk")
    part(s, "J1", "vh_h", {"1": "VIN_RAW", "2": "GND"}, "24V IN", pcb=P(62.5, 118.0, 90))
    s.part("#FLG01", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "VIN_RAW"}, in_bom=False, on_board=False)
    s.part("#FLG02", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "GND"}, in_bom=False, on_board=False)
    s.part("#FLG03", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+24V"}, in_bom=False, on_board=False)
    # Q1 rot 270: the drain tab towards J1 (VIN_RAW pour), source and gate towards the rear
    part(s, "Q1", "pfet", {"G": "Q1_GATE", "D": "VIN_RAW", "S": "+24V"}, pcb=P(66.0, 104.0, 270))
    part(s, "D1", "zener12", {"K": "+24V", "A": "Q1_GATE"}, pcb=P(69.0, 95.0, 0))
    R(s, "R1", "100k", "Q1_GATE", "GND", pcb=P(72.6, 97.6, 90))
    # their + pads on the F.Cu input strip's right edge, GND pads outside it
    part(s, "D2", "tvs33c", {"K": "+24V", "A": "GND"}, pcb=P(67.8, 64.0, 0))
    part(s, "C1", "cap220u50", {"1": "+24V", "2": "GND"}, "220u/50V", pcb=P(68.5, 86.0, 0))
    part(s, "C2", "cap220u50", {"1": "+24V", "2": "GND"}, "220u/50V", pcb=P(68.5, 74.0, 0))
    s.block("24 V present (front LED) and bus voltage for the controller's ADC")
    R(s, "R2", "10k", "+24V", "PWR_LED", size="0805", pcb=P(LED_X[4], H - 5.0, 90))
    part(s, "D3", "led_side_g", {"A": "PWR_LED", "K": "GND"}, "24V", pcb=P(LED_X[4], LED_Y, 180))
    R(s, "R3", "100k", "+24V", "VSENSE", pcb=P(48.0, 95.6, 90))
    R(s, "R4", "10k", "VSENSE", "GND", pcb=P(46.5, 95.6, 90))
    C(s, "C3", "100n", "VSENSE", "GND", pcb=P(45.0, 95.6, 90))
    s.note("Q1: drain to the connector, source to the load; the 12 V zener keeps |Vgs| inside ±20 V.")
    s.note("SMCJ33A: 33 V stand-off, ≤ 53 V clamp — below the TPS26600's 60 V rating.")
    s.note("VSENSE: 100k/10k → 2.18 V at 24 V (3.0 V at the 33 V OVP threshold) for the ESP32's ADC.")

    # ------------------------------------------------------------------ outputs
    o = b.sheet("Outputs", "outputs.kicad_sch", "Four eFused row outputs (6-pin JST PH)")
    for k, ch in enumerate(ROWS):
        n = k + 1
        yc, yj = ef_y(k), ROW_Y[k]
        o.block(f"Row {ch}: TPS26600 eFuse 1.6 A, ON / FAULT LEDs, controller interface, 6-pin JST PH")
        part(o, f"U{10 + n}", "efuse", {"IN": "+24V", "GND": "GND", "RTN": "GND", "UVLO": "GND", "OVP": "GND",
                                        "MODE": "GND", "~{SHDN}": f"SHDN_{ch}", "ILIM": f"ILIM_{ch}",
                                        "dVdT": f"DVDT_{ch}", "IMON": f"IMON_{ch}", "~{FLT}": f"FLT_{ch}",
                                        "OUT": f"ROW_{ch}"}, pcb=P(EF_X, yc, 0))
        C(o, f"C{10 + n}", "1u", "+24V", "GND", size="0805", pcb=P(20.3, yc + 2.4, 0))
        C(o, f"C{30 + n}", "1u", f"ROW_{ch}", "GND", size="0805", pcb=P(34.0, yc - 2.6, 0))
        R(o, f"R{20 + n}", "7.5k", f"ILIM_{ch}", "GND", pcb=P(34.0, yc + 1.0, 0))
        C(o, f"C{20 + n}", "22n", f"DVDT_{ch}", "GND", pcb=P(34.0, yc + 2.6, 0))
        R(o, f"R{30 + n}", "18k", f"IMON_{ch}", "GND", pcb=P(34.0, yc + 4.2, 0))
        R(o, f"R{60 + n}", "1k", f"IMON_{ch}", f"ADC_IMON_{ch}", pcb=P(37.4, yc + 4.2, 0))
        C(o, f"C{60 + n}", "10n", f"ADC_IMON_{ch}", "GND", pcb=P(40.4, yc + 4.2, 0))
        # SHDN: on by default (divider from 24 V, ≤ 4 V per the datasheet); the controller pulls it low
        R(o, f"R{10 + n}", "1M", "+24V", f"SHDN_{ch}", pcb=P(18.4, yc + 5.4, 90))
        R(o, f"R{70 + n}", "150k", f"SHDN_{ch}", "GND", pcb=P(20.2, yc + 5.4, 90))
        part(o, f"Q{n + 1}", "nfet", {"G": f"ROW_OFF_{ch}", "S": "GND", "D": f"SHDN_{ch}"}, pcb=P(24.0, yc + 5.6, 0))
        R(o, f"R{80 + n}", "100k", f"ROW_OFF_{ch}", "GND", pcb=P(28.4, yc + 5.6, 0))
        # FLT: open drain, pulled up to 3.3 V for the controller; red LED from 3.3 V
        R(o, f"R{90 + n}", "100k", "+3V3", f"FLT_{ch}", pcb=P(34.0, yc - 0.6, 0))
        R(o, f"R{50 + n}", "680", "+3V3", f"FLTLED_{ch}", pcb=P(LED_X[k] + 3.0, H - 5.0, 90))
        part(o, f"D{20 + n}", "led_side_r", {"A": f"FLTLED_{ch}", "K": f"FLT_{ch}"}, "FAULT",
             pcb=P(LED_X[k] + 3.0, LED_Y, 180))
        # ON: green LED on the row's own 24 V
        R(o, f"R{40 + n}", "10k", f"ROW_{ch}", f"ON_{ch}", pcb=P(LED_X[k] - 3.0, H - 5.0, 90))
        part(o, f"D{10 + n}", "led_side_g", {"A": f"ON_{ch}", "K": "GND"}, "ON", pcb=P(LED_X[k] - 3.0, LED_Y, 180))
        # the row cable: 24 V, GND, CAN_H, CAN_L, GND, POS (docs/can.md); POS through 10k + a clamp to
        # GND / 3.3 V, so a reversed cable (+24 V on pin 6) costs ≈ 2 mA
        part(o, f"J{1 + n}", "ph6", {"1": f"ROW_{ch}", "2": "GND", "3": "CAN_H", "4": "CAN_L", "5": "GND",
                                    "6": f"POS_{ch}_CONN"}, f"ROW {ch}", pcb=P(PH_EDGE, yj, 270))
        R(o, f"R{100 + n}", "10k", f"POS_{ch}", f"POS_{ch}_CONN", pcb=P(14.0, yj + 5.0, 0))
        part(o, f"D{30 + n}", "bat54s", {"A": "GND", "K": "+3V3", "COM": f"POS_{ch}"}, pcb=P(16.6, yj + 7.6, 0))
    o.note("TPS26600: I_LIM ≈ 12 A·kΩ / R_ILIM → 7.5k ≈ 1.6 A (JST PH: 2 A per contact).")
    o.note("t_dVdT = 8e3 · V_IN · C_dVdT → 22 nF ≈ 4.2 ms at 24 V.")
    o.note("IMON: 78 µA/A into 18k → 1.4 V/A (2.2 V at the limit), 1k + 10 nF to the ESP32's ADC.")
    o.note("SHDN: 1M/150k from 24 V → 3.1 V (the datasheet's SHDN range is 0–4 V); Q pulls it low to switch a row off.")
    o.note("FLT: open drain, 100k to 3.3 V for the controller; the red LED (680 Ω) lights while it is low.")
    o.note("UVLO / OVP / MODE to GND: internal 15 V / 33 V thresholds, current-limit mode, auto-retry.")

    # ------------------------------------------------------------------ controller
    c = b.sheet("Controller", "controller.kicad_sch", "Rack controller: supplies, ESP32-S3, USB-C, CAN")
    c.block("5 V buck: LMR51635, as the bay node (TI SLUSF64B table 8-2)")
    part(c, "U2", "buck", {"VIN": "+24V", "EN": "BUCK_EN", "CB": "BUCK_CB", "SW": "BUCK_SW", "FB": "BUCK_FB",
                           "GND": "GND"}, pcb=P(58.00, 12.0, 0))
    C(c, "C104", "10u", "+24V", "GND", size="1206", pcb=P(58.00, 16.8, 0))
    C(c, "C105", "10u", "+24V", "GND", size="1206", pcb=P(58.00, 19.4, 0))
    C(c, "C106", "100n", "+24V", "GND", pcb=P(58.00, 14.6, 0))
    R(c, "R205", "1M", "+24V", "BUCK_EN", pcb=P(54.78, 14.3, 90))
    R(c, "R206", "100k", "BUCK_EN", "GND", pcb=P(54.00, 12.0, 180))
    C(c, "C107", "100n", "BUCK_CB", "BUCK_SW", pcb=P(59.60, 9.5, 0))
    part(c, "L1", "buck_l", {"1": "BUCK_SW", "2": "+5V_BUCK"}, "3.3u", pcb=P(65.70, 12.0, 0))
    for i in range(3):
        C(c, f"C{108 + i}", "22u", "+5V_BUCK", "GND", size="1206", pcb=P(64.0 + 2.5 * i, 18.5, 270))
    R(c, "R207", "120k", "+5V_BUCK", "BUCK_FB", pcb=P(54.00, 8.6, 0))
    R(c, "R208", "22k", "BUCK_FB", "GND", pcb=P(54.00, 10.2, 180))
    c.part("#FLG04", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+5V_BUCK"}, in_bom=False, on_board=False)
    c.block("5 V for the controller: the buck or the USB-C (diode OR), 3.3 V LDO")
    part(c, "D4", "schottky", {"A": "+5V_BUCK", "K": "+5V"}, pcb=P(73.2, 13.0, 90))
    part(c, "D5", "schottky", {"A": "VBUS", "K": "+5V"}, pcb=P(56.0, 130.5, 180))
    c.part("#FLG05", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+5V"}, in_bom=False, on_board=False)
    c.part("#FLG06", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "VBUS"}, in_bom=False, on_board=False)
    part(c, "U3", "ldo", {"VI": "+5V", "VO": "+3V3", "GND": "GND"}, pcb=P(66.0, 28.5, 0))
    C(c, "C111", "10u", "+5V", "GND", size="0805", pcb=P(59.5, 28.5, 90))
    C(c, "C112", "22u", "+3V3", "GND", size="1206", pcb=P(72.0, 28.5, 90))

    c.block("ESP32-S3-MINI-1 (antenna at the board's rear edge: no copper under it, either layer)")
    part(c, "U4", "esp32s3", {
        "3V3": "+3V3", "GND": "GND", "EN": "EN", "IO0": "BOOT", "USB_D-": "USB_DN", "USB_D+": "USB_DP",
        "IO1": "ADC_IMON_A", "IO2": "ADC_IMON_B", "IO4": "ADC_IMON_C", "IO5": "ADC_IMON_D", "IO6": "VSENSE",
        "IO7": "FLT_A", "IO8": "FLT_B", "IO9": "FLT_C", "IO10": "FLT_D",
        "IO11": "ROW_OFF_A", "IO12": "ROW_OFF_B", "IO13": "ROW_OFF_C", "IO14": "ROW_OFF_D",
        "IO15": "POS_A", "IO16": "POS_B", "IO17": "POS_C", "IO18": "POS_D",
        "IO39": "CAN_TXD", "IO40": "CAN_RXD", "IO41": "CTL_LED", "IO42": "CAN_STB",
        "TXD0": "U0TX", "RXD0": "U0RX",
    }, pcb=P(30.0, 10.5, 0))
    C(c, "C113", "22u", "+3V3", "GND", size="1206", pcb=P(19.8, 10.5, 90))
    C(c, "C114", "100n", "+3V3", "GND", pcb=P(19.8, 14.6, 90))
    part(c, "SW1", "button", {"1": "EN", "2": "GND"}, "RESET", pcb=P(11.5, 10.0, 0))
    R(c, "R209", "10k", "+3V3", "EN", pcb=P(17.0, 9.5, 90))
    C(c, "C115", "1u", "EN", "GND", pcb=P(17.0, 13.0, 90))
    part(c, "SW2", "button", {"1": "BOOT", "2": "GND"}, "BOOT", pcb=P(11.5, 16.5, 0))
    R(c, "R210", "10k", "+3V3", "BOOT", pcb=P(17.0, 16.5, 90))
    part(c, "D8", "led_side_g", {"A": "CTL_LED_A", "K": "GND"}, "CTL", pcb=P(LED_X[5], LED_Y, 180))
    R(c, "R211", "330", "CTL_LED", "CTL_LED_A", pcb=P(LED_X[5], H - 5.0, 90))
    for i, (net, xy) in enumerate((("U0TX", (30.0, 16.5)), ("U0RX", (32.6, 16.5)), ("GND", (30.0, 19.1)),
                                   ("+3V3", (32.6, 19.1)), ("+5V", (46.0, 30.0)), ("+24V", (48.6, 30.0)),
                                   ("GND", (51.2, 30.0)))):
        part(c, f"TP{i + 1}", "testpad", {"1": net}, net, pcb=P(*xy, 0, "bottom"), in_bom=False)

    c.block("USB-C: the controller's console / firmware (native USB), and its 5 V when 24 V is off")
    part(c, "J6", "usbc", {"VBUS": "VBUS", "GND": "GND", "CC1": "USB_CC1", "CC2": "USB_CC2", "D+": "USB_CONN_DP",
                           "D-": "USB_CONN_DN", "SBU1": None, "SBU2": None, "SHIELD": "GND"}, "USB",
         pcb=P(USB_X, H - 3.4, 0))
    R(c, "R212", "5.1k", "USB_CC1", "GND", pcb=P(64.0, H - 10.2, 90))
    R(c, "R213", "5.1k", "USB_CC2", "GND", pcb=P(65.6, H - 10.2, 90))
    part(c, "U5", "esd", {"6": "USB_CONN_DN", "1": "USB_DN", "4": "USB_CONN_DP", "3": "USB_DP", "5": "VBUS", "2": "GND"},
         pcb=P(60.5, H - 12.5, 270))
    C(c, "C120", "1u", "VBUS", "GND", pcb=P(60.5, H - 16.4, 0))

    c.block("CAN: TCAN1044AV, star bus (all row ports in parallel), both terminations here")
    part(c, "U6", "can_xcvr", {"TXD": "CAN_TXD", "VSS": "GND", "VDD": "+5V", "RXD": "CAN_RXD", "Vio": "+3V3",
                               "CANL": "CAN_L", "CANH": "CAN_H", "STBY": "CAN_STB"}, "TCAN1044AV", pcb=P(14.0, 32.0, 0))
    C(c, "C116", "100n", "+5V", "GND", pcb=P(8.6, 29.6, 0))
    C(c, "C117", "100n", "+3V3", "GND", pcb=P(8.6, 34.4, 0))
    R(c, "R214", "10k", "CAN_STB", "GND", pcb=P(20.0, 29.4, 0))
    for i, (r1, r2, cc, mid, y) in enumerate((("R215", "R216", "C118", "CAN_TERM1", 36.0), ("R217", "R218", "C119", "CAN_TERM2", 38.6))):
        R(c, r1, "56", "CAN_H", mid, pcb=P(19.0, y, 0))
        R(c, r2, "56", mid, "CAN_L", pcb=P(22.4, y, 0))
        C(c, cc, "4.7n", mid, "GND", pcb=P(25.6, y, 0))
    part(c, "D9", "can_esd", {"1": "CAN_H", "2": "CAN_L", "3": "GND"}, pcb=P(14.5, 37.5, 0))

    c.block("Mounting (M3, on the power box's standoffs)")
    for i, (x, y) in enumerate(CFG["holes"]):
        part(c, f"H{i + 1}", "hole", {}, "M3", pcb=P(x, y, 0), in_bom=False)
    c.note("GPIO: IO1/2/4/5 IMON A–D (ADC1) · IO6 VSENSE · IO7–10 FLT A–D · IO11–14 ROW_OFF A–D · IO15–18 POS A–D ·")
    c.note("  IO39/40 CAN TX/RX (TWAI) · IO41 CTL LED · IO42 CAN STB · IO19/20 USB.  Strapping IO3/45/46 unused.")
    c.note("Termination: two split 2 × 56 Ω + 4.7 nF (56 Ω in all) at the star centre; nodes carry none.")
    c.note("+5V: buck (5.16 V) or USB VBUS through B5819W Schottkys: ≈ 4.8 V for the TCAN1044 (4.5–5.5 V) and the LDO.")
    return b


NETCLASSES = [
    {"name": "Power", "clearance": 0.2, "track_width": 0.8, "via_diameter": 1.0, "via_drill": 0.5,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 1,
     # +24V carries its current in pours (see b.pcb["zones"]); its tracks only feed pull-ups and LEDs
     "_patterns": ["*VIN_RAW", "*ROW_?", "*+5V_BUCK", "*BUCK_SW"]},
    {"name": "USB", "clearance": 0.15, "track_width": 0.2, "via_diameter": 0.6, "via_drill": 0.3,
     "diff_pair_width": 0.25, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 2,
     "_patterns": ["*_DP", "*_DN"]},
]
