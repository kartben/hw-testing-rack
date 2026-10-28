"""Power hub v0.5 — one per rack, in the power box under A1 (mechanical/parts/power_box.scad).

USB-C PD in, from a dedicated USB PD charger (100 W at 20 V by default, 140 W EPR at 28 V as an option)
on a 5 A e-marked cable.
A CH224A sink controller (WCH, PD 3.2) negotiates the PD contract: 9 V at plug-in (its CFG1
resistor), then the rack controller asks it over I2C for 28 V EPR when the charger offers it, 20 V
otherwise; the chip keeps the contract, and the EPR keep-alive, through ESP32 reboots.  VBUS is the
rack bus (VRACK, 20 or 28 V): no input switch, the four eFuses are the switches (UV 15 V, off until
the controller has a contract, reverse current blocked).
VRACK fans out to four rows (A–D), each with its own TPS26600 eFuse:
  * current limit ≈ 1.6 A (RILIM 7.5k): it protects the JST PH (2 A) row cable;
  * slow start (dVdT 100 nF ≈ 16 ms at 20 V, 22 ms at 28 V): a row of four nodes (≈ 450 µF) charges at
    ≈ 0.56 A, under the limit even at the corners; the eFuse then takes ≈ 7–9 W typically, ≈ 14 W at the
    worst corner, for 19–24 ms, within its thermal-shutdown time with TI's margin (47 nF wasn't, at 28 V);
  * internal UV 15 V / OV 31–34 V (typ 32.6 V) defaults, auto-retry;
  * OFF until the controller turns it on: SHDN is pulled low, the ESP32 drives it high once the PD
    contract is final (row by row, staggered) and sheds rows when the contract drops;
  * ON (green, on the row's own output) and FAULT (red, from the open-drain FLT) side-view LEDs in
    the box's front wall.
The rack controller is an ESP32-S3-MINI-1 (Wi-Fi, the CAN master) on a buck and an LDO fed from
VBUS, so it runs from the first 5 V of a contract (or from its own USB-C console port).  It drives
the CH224A over I2C, reads each row's FLT and IMON, drives each row's enable,
and runs the rack's CAN bus and the POS addressing token (docs/can.md).  The row outputs are 6-pin
JST PH with the bay nodes' OUT pinout (J1's mirrored): POS, GND, CAN_L, CAN_H, GND, VRACK, so
every row cable is the same flat one (pin n to pin 7-n).  The bus is a star: every port carries
the same CAN pair, both terminations are here.

4 layers, 76 × 100 mm, the bay node's stackup and rules: In1 a solid GND plane, In2 power only
(a VRACK area under the eFuse column and the input, +3V3 around it), signals on the outer layers,
a via of its own to its plane for every GND and supply pin, GND pours stitched to In1
(config/rack.yaml › pcb.power_hub: outline, holes, connector and LED positions, which the box is
drawn around).  KiCad coordinates: y = 0 is the REAR edge (the ESP32's antenna, the PD input),
y = 100 the FRONT edge (LEDs, console USB-C); the four row connectors sit on the left edge, 17.5 mm apart.

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
# Rows fitted on this build: the rack has two rows (the user, 2026-10-23).  The others keep their footprints and
# routing; their eFuse, connector and LEDs are DNP, their passives stay (FLT pulled up, IMON at 0 V)
FITTED = ["A", "B"]
ROW_Y = CFG["rows"]                 # KiCad y of each row connector (left edge)
LED_X = CFG["front"]["leds"]        # ON/FAULT pair centres A–D, then PD, CTL
USB_X = CFG["front"]["usb"]
PD_X = CFG["rear"]["pd"]            # the USB-C PD input on the rear edge
PH_EDGE = 4.9                       # JST PH side entry: footprint origin from the board edge (as the bay node)
LED_Y = H - 1.25                    # side-view LED, lens at the front edge (rot 180)
EF_X = 26.0                         # eFuse centre (rot 0: IN on the left, OUT on the right, both at the top)
BY = 22.0                           # the buck block, moved down from the rear right (v0.4) by this much


def P(x, y, rot=0, side="top", **kw):
    return {"x": x, "y": y, "rot": rot, "side": side, **kw}


def offset(path, d):
    """A polyline offset by d towards (−uy, ux) of its direction u (KiCad axes: heading +y, that is −x),
    mitred at the corners: one wire of a pair drawn around its centreline."""
    def seg(i):
        (x0, y0), (x1, y1) = path[i], path[i + 1]
        n = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
        return (x1 - x0) / n, (y1 - y0) / n
    out = []
    for i, (x, y) in enumerate(path):
        u0 = seg(max(i - 1, 0))
        u1 = seg(min(i, len(path) - 2))
        nx, ny = -(u0[1] + u1[1]), u0[0] + u1[0]          # bisector of the two left normals
        k = d / (nx * -u1[1] + ny * u1[0])                 # mitre length along it
        out.append((round(x + nx * k, 4), round(y + ny * k, 4)))
    return out


def ef_y(k):
    return ROW_Y[k] - 0.5


# Eve's test pads, second round (the kicad-happy review's PH-2, 2026-10-27): the supplies the first round left out on
# 1.5 mm, the row and CAN signals on 1.0 mm, a GND by the CAN pads.  Each sits on a via of its net: a new one drawn
# here, the row outputs' own, or one the router had put there, drawn here too so it stays; or on a B.Cu track's end.
# No new via on In2's VRACK band.  (net, sheet, Ø, (x, y), drawn via, label)
TP_ROUND2 = [
    ("+5V_BUCK", "c", 1.5, (67.8, 31.6), True, "5V BUCK"),
    ("USB_VBUS", "c", 1.5, (68.5289, 89.256), True, "USB 5V"),
    ("PD_VHV", "s", 1.5, (51.5222, 7.3), True, "VHV"),
    *(((f"ROW_{ch}", "o", 1.5, (14.3, ROW_Y[k] + 5.0), False, f"ROW {ch}") for k, ch in enumerate(ROWS))),
    ("PD_INT", "c", 1.0, (54.7937, 56.8983), True, "PD PG"),
    ("CAN_H", "c", 1.0, (60.1612, 70.23), True, "CANH"),
    ("CAN_L", "c", 1.0, (56.8962, 68.078), False, "CANL"),
    ("CAN_TXD", "c", 1.0, (50.6741, 55.2441), True, "TXD"),
    ("CAN_RXD", "c", 1.0, (50.476, 61.4457), True, "RXD"),
    ("ROW_EN_A", "c", 1.0, (13.0284, 96.6659), True, "EN A"),
    ("ROW_EN_B", "c", 1.0, (16.1067, 59.6979), True, "EN B"),
    ("ROW_EN_C", "c", 1.0, (20.6796, 57.3601), True, "EN C"),
    ("ROW_EN_D", "c", 1.0, (29.6951, 24.4507), True, "EN D"),
    ("VBUS_SENSE", "c", 1.0, (33.1723, 10.0181), False, "VSNS"),
    ("GND", "c", 1.5, (55.95, 71.95), True, "GND"),
]


def board() -> Board:
    b = Board("power-hub", "Power hub", "0.5",
              comments=["USB-C PD distribution + rack controller (ESP32-S3, CAN master) for the hw-testing-rack",
                        "Generated from electronics/power-hub/design.py — edit the Python, then regenerate"])
    b.root_notes = [
        "Power hub v0.5 — USB-C PD in (CH224A: 9 V, then 20 V or 28 V EPR as the controller asks) = VRACK → 4 × TPS26600 "
        "eFuse (1.6 A) → 6-pin JST PH rows A–D.",
        "Rack controller: ESP32-S3-MINI-1 on VBUS, TJA1462AT (CAN master, star bus, both "
        "terminations here), POS token per row.",
        "Rows are OFF without firmware: SHDN is pulled low; the controller turns each row on once the PD contract is final.",
    ]

    # ------------------------------------------------------------------ PCB
    # In2 (power only): VRACK under the input, along the band at y ≈ 37.5 (8 mm wide: up to 5 A towards
    # the four rows; 5 mm before pcba-review H12) and down the eFuse column;
    # +3V3 everywhere else, one piece wrapping around it.  Outlines don't overlap: the router takes
    # each as copper of its net.
    in2 = [
        # priority 2: VRACK wins where the +3V3 tongue into its notch overlaps it (4.6 mm²), every build; at
        # equal priorities KiCad's tie-break is the zones' UUIDs, new at each build, and the split moved
        {"layer": "In2.Cu", "net": "VRACK", "priority": 2,
         # a notch over row D's FLT pull-up (R94): its +3V3 pin gets the +3V3 area under it
         "poly": [(16.2, 21.6), (45.6, 21.6), (45.6, 0.4), (75.6, 0.4), (75.6, 29.6), (35.5, 29.6), (35.5, 26.2),
                  (31.5, 26.2), (31.5, 29.6), (24.6, 29.6), (24.6, 84.0), (16.2, 84.0)]},
        {"layer": "In2.Cu", "net": "+3V3", "priority": 1,
         "poly": [(0.4, 0.4), (45.2, 0.4), (45.2, 21.2), (15.8, 21.2), (15.8, 84.4),
                  (25.0, 84.4), (25.0, 30.0), (31.1, 30.0), (31.1, 25.8), (35.9, 25.8), (35.9, 30.0), (75.6, 30.0),
                  (75.6, H - 0.4), (0.4, H - 0.4)]},
    ]
    # per eFuse: a top-side VRACK island on its IN pins and the input capacitor, three vias to In2 at its far end
    in_islands = [{"layer": "F.Cu", "net": "VRACK", "name": f"vrack-in-{ch}", "priority": 2, "exclusive": 0.4,
                   "connection": "solid",
                   "poly": [(17.2, ef_y(k) - 2.65), (23.85, ef_y(k) - 2.65), (23.85, ef_y(k) - 1.35), (17.2, ef_y(k) - 1.35)]}
                  for k, ch in enumerate(ROWS)]
    tracks = []
    for k, ch in enumerate(ROWS):
        yc = ef_y(k)
        # OUT (pins 15/16, x = EF_X + 2.9) → up over the eFuse → left, short of the connector's rear pin
        # (POS) → down on B.Cu beside the connector (three vias at each end) → its pin 6, the front pad.
        # The row outputs have the bay nodes' OUT pinout (docs/can.md); the top side beside the
        # connector stays free for the CAN pair.
        yj = ROW_Y[k]
        tracks.append((f"ROW_{ch}", "F.Cu", 0.8, [(EF_X + 2.9, yc - 1.95), (EF_X + 4.6, yc - 1.95),
                                                (EF_X + 4.6, yj - 5.0), (13.2, yj - 5.0)]))
        tracks.append((f"ROW_{ch}", "B.Cu", 0.8, [(15.4, yj - 5.0), (13.2, yj - 5.0), (13.2, yj + 5.0), (15.4, yj + 5.0)]))
        tracks.append((f"ROW_{ch}", "F.Cu", 0.8, [(15.4, yj + 5.0), (9.4, yj + 5.0)]))
        # … a branch to the output capacitor C3x, and one to the ON LED's resistor R4x
        tracks.append((f"ROW_{ch}", "F.Cu", 0.8, [(EF_X + 4.6, yc - 2.6), (33.05, yc - 2.6)]))
        tracks.append((f"ROW_{ch}", "F.Cu", 0.4, [(EF_X + 4.6, yc - 4.5), (36.0, yc - 4.5)]))
        # UVLO, OVP, MODE and RTN (left), GND (right): straight onto the exposed pad, no via of their own
        for dy in (-0.975, 0.325, 0.975, 2.275):
            tracks.append(("GND", "F.Cu", 0.25, [(EF_X - 2.8625, yc + dy), (EF_X - 1.4, yc + dy)]))
        tracks.append(("GND", "F.Cu", 0.25, [(EF_X + 2.8625, yc + 2.275), (EF_X + 1.4, yc + 2.275)]))
        # SHDN (pin 7) → left, down to its pull-down R7x, across to the series resistor R8x
        tracks.append((f"SHDN_{ch}", "F.Cu", 0.25, [(EF_X - 2.8625, yc + 1.625), (21.4, yc + 1.625),
                                                   (21.4, yc + 3.675), (19.825, yc + 3.675)]))
    # PD input: CC1 straight down to a via (routed underneath to the CH224A; CC2 leaves behind the
    # receptacle, the router's way); VBUS reaches the buck in a 0.8 mm bottom track from the input block
    tracks += [
        ("PD_CC1", "F.Cu", 0.2, [(PD_X + 1.25, 7.08), (PD_X + 1.25, 8.15)]),
        ("GND", "F.Cu", 0.25, [(PD_X + 3.2, 6.9), (PD_X + 4.2, 6.9)]),
        ("VRACK", "B.Cu", 0.8, [(55.8, 14.55), (55.8, 30.0), (56.7, 31.0), (56.7, 13.5 + BY)]),
    ]
    # the console's USB pair (full speed), U4 pins 23/24 → U5: coupled on F.Cu over In1's GND (0.25 mm,
    # 0.2 mm apart), straight down the free column at x ≈ 45 between the eFuse parts and the buck, into
    # U5's protected side (D− on pin 3, D+ on pin 1: the pair's order, no crossing)
    usb = [(30.425, 21.1), (30.425, 21.4), (31.125, 22.1), (44.725, 22.1), (45.425, 22.8), (45.425, H - 32.0),
           (60.5, H - 16.925), (60.5, H - 16.0)]
    tracks += [
        ("USB_DN", "F.Cu", 0.25, [(30.0, 20.05), (30.0, 20.9), *offset(usb, 0.225), (59.55, H - 15.275), (59.55, H - 13.64)]),
        ("USB_DP", "F.Cu", 0.25, [(30.85, 20.05), (30.85, 20.9), *offset(usb, -0.225), (61.45, H - 15.275), (61.45, H - 13.64)]),
        # U5's GND pin (2) between them: its via straight out, between the two wires
        ("GND", "F.Cu", 0.25, [(60.5, H - 13.64), (60.5, H - 15.05)]),
        # EN's RC at the module's pin 45 (pcba-review H13): C115 beside it, below the module's antenna keep-out
        ("EN", "F.Cu", 0.25, [(37.0, 7.1), (38.275, 7.1), (39.225, 6.15)]),
    ]
    b.pcb = {
        "size": (W, H), "layers": CFG["layers"], "corner_radius": 3.0, "passes": 60,
        # the bay node's build: JLC's standard 4-layer stackup and lead-free HASL.  ENIG until 2026-10-19, for
        # the module's LGA pads; HASL saves ≈ $12.70 on 5 boards, and JLC X-rays the module either way
        "inner": [("In1.GND", "power"), ("In2.PWR", "power")],
        "stackup": "JLC04161H-7628", "finish": "HASL",
        "edge_parts": ["J*", "U4", "D1*", "D2*", "D3", "D8"],
        "defer_pours": False,
        # net: (plane, via Ø, drill, track width); pins over another net's area are routed instead
        "fanout_nets": {"GND": ("In1.Cu", 0.5, 0.3, 0.25), "VRACK": ("In2.Cu", 0.6, 0.3, 0.4),
                        "+3V3": ("In2.Cu", 0.6, 0.3, 0.3)},
        "plane_nets": {"VRACK": "In2.Cu", "+3V3": "In2.Cu"},
        # nets carrying power (≳ 0.5 A): their IC, connector and big pads connect solid to the pours, small
        # parts keep reliefs (pcbgen.power_pads); the number is the spokes a relieved pad of theirs keeps
        "power_nets": {"GND": 1, "VRACK": 2, "ROW_?": 2, "+5V_BUCK": 2, "+5V": 2, "USB_VBUS": 2},
        # each decoupling capacitor and the power pin it serves: within 2 mm of it, its GND within 1 mm of a via
        # (electronics/tools/decoupling.py, Eve's layout review, 2026-10-28).  Bulk, bootstrap, timing, filter and
        # RC capacitors serve no one pin: left out
        "decoupling": {"C4": "U1.VDD", **{f"C{10 + n}": f"U{10 + n}.IN" for n in range(1, 5)},
                       "C104": "U2.VIN", "C105": "U2.VIN", "C106": "U2.VIN", "C111": "U3.VIN", "C112": "U3.VOUT",
                       "C113": "U4.3V3", "C114": "U4.3V3", "C120": "U5.5", "C116": "U6.VDD", "C117": "U6.Vio"},
        "stitch": 4.0,
        # GCT's USB4105 footprint puts its GND pads 0.19 mm from its own NPTH pegs (the datasheet's land pattern)
        "dru": "".join(f"""
(rule "USB4105 {r}: GND pads beside its own pegs"
	(condition "A.memberOfFootprint('{r}') && B.memberOfFootprint('{r}')")
	(constraint hole_clearance (min 0.19mm)))
""" for r in ("J1", "J6")),
        "zones": [
            {"layer": "In1.Cu", "net": "GND"},
            {"layer": "F.Cu", "net": "GND"},
            {"layer": "B.Cu", "net": "GND"},
            *in2,
            # PD input, on top where the current flows: VBUS = VRACK from the connector's pads, the TVS and
            # the input capacitors, vias down to In2 (VRACK under the whole input block)
            {"layer": "F.Cu", "net": "VRACK", "name": "pd-vbus", "priority": 3, "defer": False, "connection": "solid",
             "exclusive": 0.6, "poly": [(56.0, 7.6), (58.3, 7.6), (58.3, 6.6), (59.95, 6.6), (59.95, 8.8), (63.65, 8.8),
                                        (63.65, 6.6), (68.2, 6.6), (68.2, 10.6), (56.0, 10.6)]},
            *in_islands,
            # buck hot loop (as the bay node, TI SLUSF64B §8.4)
            {"layer": "F.Cu", "net": "GND", "connection": "solid", "name": "buck-gnd", "priority": 3,
             "poly": [(58.05, 12.5 + BY), (60.1, 12.5 + BY), (60.1, 14.2 + BY), (61.9, 14.2 + BY), (61.9, 18.3 + BY),
                      (70.6, 18.3 + BY), (70.6, 22.4 + BY), (58.05, 22.4 + BY)]},
            {"layer": "F.Cu", "net": "+5V_BUCK", "connection": "solid", "name": "buck-5v", "priority": 3,
             "poly": [(62.8, 16.1 + BY), (67.3, 16.1 + BY), (67.3, 8.6 + BY), (71.0, 8.6 + BY), (71.0, 17.9 + BY),
                      (62.8, 17.9 + BY)]},
            # exclusive: another net's track cut it in two in 15 of 17 routings (docs/autorouting-benchmark.md)
            {"layer": "F.Cu", "net": "VRACK", "connection": "solid", "name": "buck-vin", "priority": 3, "exclusive": 0.3,
             "poly": [(55.6, 12.5 + BY), (57.8, 12.5 + BY), (57.8, 20.7 + BY), (55.6, 20.7 + BY)]},
        ],
        "vias": [
            *[("GND", x, y + BY) for x, y in ((61.0, 14.9), (61.0, 17.4), (61.2, 21.4), (63.0, 21.6), (65.25, 21.6),
                                              (67.75, 21.6), (70.0, 21.6))],
            # eFuse IN islands down to In2 (VRACK); exposed pads: six tented GND vias each, to In1
            *[v for k in range(4) for v in (*[("VRACK", x, ef_y(k) - 2.0, 0.8, 0.4) for x in (17.65, 18.5, 19.3)],
                                            *[("GND", EF_X + dx, ef_y(k) + dy) for dx in (-0.9, 0.9) for dy in (-0.9, 0.0, 0.9)])],
            # each row's output: F.Cu → B.Cu beside the connector → F.Cu at its pin 6
            *[(f"ROW_{ch}", x, ROW_Y[k] + dy, 0.8, 0.4) for k, ch in enumerate(ROWS) for dy in (-5.0, 5.0)
              for x in (13.2, 14.3, 15.4)],
            # the input pour down to In2 (VRACK), beside the connector's left VBUS pads
            *[("VRACK", 57.0, y, 0.8, 0.4) for y in (8.2, 9.8)],
            # CC1 under the VBUS pour, on B.Cu
            ("PD_CC1", PD_X + 1.25, 8.15, 0.5, 0.3),
            ("GND", 60.5, H - 15.05, 0.5, 0.3),         # U5's GND pin, between the USB pair's wires
            ("VRACK", 55.8, 14.55, 0.8, 0.4), ("VRACK", 56.7, 13.5 + BY, 0.8, 0.4),
            # J1's left GND pads (A12/B1, one spot): their via, drawn, north of them under the receptacle,
            # between the shell leg and the peg.  Not in the pad (its solder would drain down the hole:
            # kicad-happy review, PH-1), not south of it, where vias cut the input pour off the left VBUS pads
            # (A9/B4); the router's own fan-out of these pads goes at the import (pcbgen.drop_redundant_fanouts)
            ("GND", 58.35, 5.3, 0.5, 0.3),
            *[(net, *xy) for net, _, _, xy, via, _ in TP_ROUND2 if via],      # the second round's test pads
        ],
        "tracks": tracks + [("GND", "F.Cu", 0.3, [(58.8, 7.08), (58.35, 6.63), (58.35, 5.3)])],
        # ESP32 antenna: no copper on any layer under/around it (module top 5 mm + the rear edge)
        "keepouts": [{"name": "antenna", "poly": [(21.3, -0.1), (38.7, -0.1), (38.7, 5.6), (21.3, 5.6)]}],
        "texts": [
            {"text": "hw-testing-rack · power hub v0.5", "x": 58, "y": 74, "size": 1.0},
            *[{"text": ch, "x": 13.8, "y": ROW_Y[k] + 8.3, "size": 1.2} for k, ch in enumerate(ROWS)],
            # the bottom-side test pads' names (TP1–TP7, the controller sheet): bring-up probes (Eve's rule, 2026-10-26)
            *({"text": t, "x": x, "y": y, "size": 0.8, "layer": "B.SilkS"}
              for t, x, y in (("TX", 27.8, 16.5), ("GND", 27.6, 19.1), ("RX", 34.8, 16.5), ("3V3", 35.0, 19.1),
                              ("EN", 27.8, 13.9), ("IO0", 34.8, 13.9),
                              ("5V", 70.0, 55.9), ("VRACK", 66.0, 21.9), ("GND", 70.0, 31.9),
                              ("PD", 45.3, 7.2), ("SDA", 44.0, 10.8), ("SCL", 46.6, 10.8), ("GND", 46.6, 54.0))),
            *({"text": t, "x": 47.6, "y": max(ef_y(k) - 1.3, 31.6) + dy, "size": 0.8, "layer": "B.SilkS"}
              for k, ch in enumerate(ROWS) for t, dy in ((f"FLT {ch}", 0.0), (f"IMON {ch}", 2.6))),
            *({"text": lab, "x": xy[0], "y": xy[1] + d / 2 + 0.85, "size": 0.8, "layer": "B.SilkS"}
              for _, _, d, xy, _, lab in TP_ROUND2),
        ],
    }

    # ------------------------------------------------------------------ input
    s = b.sheet("Input", "input.kicad_sch", "USB-C PD input")
    s.block("USB-C PD input (5 A receptacle, CC to the sink controller), TVS; VBUS is VRACK (no input switch)")
    part(s, "J1", "usbc5a", {"VBUS": "VRACK", "GND": "GND", "CC1": "PD_CC1", "CC2": "PD_CC2", "SHIELD": "GND"},
         "PD IN", pcb=P(PD_X, 3.4, 180))
    for i, net in enumerate(("VRACK", "PD_VHV", "GND"), start=1):
        s.part(f"#FLG0{i}", "power:PWR_FLAG", "PWR_FLAG", "", {"1": net}, in_bom=False, on_board=False)
    part(s, "D1", "tvs30", {"K": "VRACK", "A": "GND"}, pcb=P(67.4, 12.6, 270))
    C(s, "C1", "10u", "VRACK", "GND", size="1206", pcb=P(61.0, 11.4, 270))
    C(s, "C2", "100n", "VRACK", "GND", pcb=P(63.0, 11.2, 270))

    s.block("CH224A USB PD 3.2 sink: 9 V at plug-in (CFG1 6.8k), then 20 V / 28 V EPR as the controller asks over I2C")
    # KiCad's CH224K symbol: the CH224A has its pinout (WCH), pin 1 (VDD there) is VHV, rated 32 V.  CC1/CC2 carry
    # its own Rd (no resistors); DP/DM (BC 1.2 / QC) are left open: PD only
    part(s, "U1", "pd_sink", {"VDD": "PD_VHV", "VBUS": "PD_VHV", "CC1": "PD_CC1", "CC2": "PD_CC2",
                              "CFG1": "PD_CFG1", "CFG2": "PD_SCL", "CFG3": "PD_SDA", "DP": None, "DM": None,
                              "PG": "PD_INT", "GND": "GND"}, pcb=P(50.0, 11.0, 0))
    # VHV and VBUS (tied, as WCH asks) through 56 Ω + 1 µF 50 V: the pins are rated 32 V, a few volts over a
    # 28 V contract, and the SMAJ30A starts at 33.3 V; the RC takes the fast edges off (ICC ≤ 12 mA: ≤ 0.7 V)
    R(s, "R5", "56", "VRACK", "PD_VHV", pcb=P(53.6, 7.3, 180))
    C(s, "C4", "1u", "PD_VHV", "GND", size="0805", pcb=P(47.6, 7.0, 0))
    # CFG1 to GND: the single-resistor mode, which also turns I2C on; 6.8k asks for 9 V at plug-in, below the
    # eFuses' 15 V UV, until the controller asks for more
    R(s, "R6", "6.8k", "PD_CFG1", "GND", pcb=P(54.6, 13.8, 270))
    part(s, "C8", "cap100u50", {"1": "VRACK", "2": "GND"}, "100u/50V", pcb=P(70.0, 23.0, 270))
    C(s, "C9", "10u", "VRACK", "GND", size="1206", pcb=P(62.5, 18.5, 0))
    C(s, "C10", "100n", "VRACK", "GND", pcb=P(62.5, 20.8, 0))
    s.block("I2C to the controller, VBUS sense")
    # PG: open drain, low once the contract is in place; IO39 (the net keeps its name PD_INT for the
    # firmware's pin map) and the front LED both hang on it
    R(s, "R11", "10k", "+3V3", "PD_INT", pcb=P(41.0, 11.2, 0))
    # pull-ups from a GPIO (I2C_PU): on only once VBUS is up, so a USB-powered controller never back-feeds an
    # unpowered CH224A through SDA/SCL (they also have the chip's own 10k pull-ups)
    R(s, "R13", "5.1k", "I2C_PU", "PD_SDA", pcb=P(41.0, 8.0, 0))
    R(s, "R14", "5.1k", "I2C_PU", "PD_SCL", pcb=P(41.0, 9.6, 0))
    R(s, "R3", "100k", "VRACK", "VBUS_SENSE", pcb=P(64.6, 11.4, 270))
    R(s, "R4", "10k", "VBUS_SENSE", "GND", pcb=P(19.0, 20.4, 0))
    C(s, "C3", "100n", "VBUS_SENSE", "GND", pcb=P(19.0, 22.0, 0))
    s.block("PD status (front LED): on while the CH224A reports power good (PG low)")
    R(s, "R2", "1k", "+3V3", "PD_LED_A", pcb=P(LED_X[4], H - 5.0, 90))
    part(s, "D3", "led_side_g", {"A": "PD_LED_A", "K": "PD_INT"}, "PD", pcb=P(LED_X[4], LED_Y, 180))
    s.note("U1 is the CH224A (WCH, PD 3.2): CFG1 6.8k asks for 9 V at plug-in and turns its I2C on (0x22); the")
    s.note("  controller writes 0x0A: 5 = 28 V EPR when offered, else 4 = 20 V (single-byte I2C transfers).  CH224 V2.1")
    s.note("  lists the source's PDOs (0x60-0x8F) for both parts, readable under 100 W (p. 7): with our 100 W charger,")
    s.note("  still to check (schematic review R3); without them the firmware tries 28 V and checks VBUS.")
    s.note("No input switch: VBUS is VRACK.  The eFuses (UV 15 V, off until enabled, reverse current blocked) are the")
    s.note("  switches; the controller turns the rows on once 0x09 says PD (and EPR) and VBUS_SENSE reads the voltage.")
    s.note("SMAJ30A: 30 V stand-off, above a 28 V EPR contract; the eFuses (60 V) and the TPS26600 OVP (31–34 V) follow.")
    s.note("R5/C4: the CH224A's VHV/VBUS pins are rated 32 V; the RC filters the fast edges the TVS can't reach.")
    s.note("VBUS_SENSE: 100k/10k from VBUS → 2.5 V at 28 V for the ESP32's ADC; also tells the firmware when to enable I2C_PU.")

    # ------------------------------------------------------------------ outputs
    o = b.sheet("Outputs", "outputs.kicad_sch", "Four eFused row outputs (6-pin JST PH)", paper="A2")
    for k, ch in enumerate(ROWS):
        n = k + 1
        yc, yj = ef_y(k), ROW_Y[k]
        o.block(f"Row {ch}: TPS26600 eFuse 1.6 A, enable, ON / FAULT LEDs, 6-pin JST PH")
        dnp = ch not in FITTED
        part(o, f"U{10 + n}", "efuse", {"IN": "VRACK", "GND": "GND", "RTN": "GND", "UVLO": "GND", "OVP": "GND",
                                        "MODE": "GND", "~{SHDN}": f"SHDN_{ch}", "ILIM": f"ILIM_{ch}",
                                        "dVdT": f"DVDT_{ch}", "IMON": f"IMON_{ch}", "~{FLT}": f"FLT_{ch}",
                                        "OUT": f"ROW_{ch}"}, pcb=P(EF_X, yc, 0), dnp=dnp)
        # the input capacitor at the IN pins' end of the island, its GND pad below it beside the GND pins, clear
        # of the eFuse's pin-1 mark
        # (decoupling check, Eve's review: at the island's far end it was 4.0 mm from IN)
        C(o, f"C{10 + n}", "1u", "VRACK", "GND", size="0805", pcb=P(20.6, yc - 1.05, 270))
        C(o, f"C{30 + n}", "1u", f"ROW_{ch}", "GND", size="0805", pcb=P(34.0, yc - 2.6, 0))
        R(o, f"R{20 + n}", "7.5k", f"ILIM_{ch}", "GND", pcb=P(34.0, yc + 1.0, 0))
        # 100 nF: at 28 V and 85 °C a 47 nF start (≈ 21 W for 12 ms at the worst corner) met the TPS2660's thermal
        # shutdown time (Fig. 55: ≈ 8–10 ms at 21 W); 100 nF halves the power for twice the time (datasheet audit U1)
        C(o, f"C{20 + n}", "100n", f"DVDT_{ch}", "GND", pcb=P(34.0, yc + 2.6, 0))
        R(o, f"R{30 + n}", "18k", f"IMON_{ch}", "GND", pcb=P(34.0, yc + 4.2, 0))
        R(o, f"R{60 + n}", "1k", f"IMON_{ch}", f"ADC_IMON_{ch}", pcb=P(37.4, yc + 4.2, 0))
        C(o, f"C{60 + n}", "47n", f"ADC_IMON_{ch}", "GND", pcb=P(40.4, yc + 4.2, 0))
        # SHDN: off by default (10k to GND: the pin sources up to 10 µA, 0.1 V, under the 0.55 V threshold;
        # 100k gave 1 V, on without firmware: pcba-review H3); the controller drives ROW_EN high, through 10k
        # (1.65 V), to turn it on
        R(o, f"R{70 + n}", "10k", f"SHDN_{ch}", "GND", pcb=P(21.4, yc + 4.5, 270))
        R(o, f"R{80 + n}", "10k", f"ROW_EN_{ch}", f"SHDN_{ch}", pcb=P(19.0, yc + 3.675, 0))
        # FLT: open drain, pulled up to 3.3 V for the controller.  The red LED (1k: ≈ 1.4 mA, every front LED
        # on the board's 1k) hangs from the row's own ROW_EN: the TPS26600 also pulls FLT low while the row
        # is off or starting (§9.3.5.3), so from 3.3 V all four would light whenever the rows are off
        R(o, f"R{90 + n}", "100k", "+3V3", f"FLT_{ch}", pcb=P(34.0, yc - 0.6, 0))
        R(o, f"R{50 + n}", "1k", f"ROW_EN_{ch}", f"FLTLED_{ch}", pcb=P(LED_X[k] + 3.0, H - 5.0, 90))
        part(o, f"D{20 + n}", "led_side_r", {"A": f"FLTLED_{ch}", "K": f"FLT_{ch}"}, "FAULT",
             pcb=P(LED_X[k] + 3.0, LED_Y, 180), dnp=dnp)
        # ON: green LED on the row's own output
        # 18k: 1.4 mA and 37 mW at 28 V (10k ran at 75 % of its 0603 rating at 29.4 V: schematic review S4)
        R(o, f"R{40 + n}", "18k", f"ROW_{ch}", f"ON_{ch}", pcb=P(36.825, yc - 4.5, 0))
        part(o, f"D{10 + n}", "led_side_g", {"A": f"ON_{ch}", "K": "GND"}, "ON", pcb=P(LED_X[k] - 3.0, LED_Y, 180),
             dnp=dnp)
        # the row cable, with the bay nodes' OUT pinout (J1's mirrored, docs/can.md): POS, GND, CAN_L,
        # CAN_H, GND, VRACK, so the feed is the same flat cable as the node-to-node jumpers.  POS through
        # 10k (behind pin 1) + a clamp to GND / 3.3 V, so VRACK on it from a wrong cable costs ≈ 3 mA
        part(o, f"J{1 + n}", "ph6", {"1": f"POS_{ch}_CONN", "2": "GND", "3": "CAN_L", "4": "CAN_H", "5": "GND",
                                    "6": f"ROW_{ch}"}, f"ROW {ch}", pcb=P(PH_EDGE, yj, 270), dnp=dnp)
        R(o, f"R{100 + n}", "10k", f"POS_{ch}", f"POS_{ch}_CONN", pcb=P(11.0, yj - 6.9, 90))
        # the row cable's inductive kick when the eFuse cuts a short: a Schottky to GND at the connector, its
        # cathode on the output track (TPS2660 §12.1; OUT ≥ −0.3 V)
        part(o, f"D{40 + n}", "schottky", {"A": "GND", "K": f"ROW_{ch}"}, pcb=P(11.5, yj + 6.635, 270))
        part(o, f"D{30 + n}", "bat54s", {"A": "GND", "K": "+3V3", "COM": f"POS_{ch}"}, pcb=P(16.6, yj + 7.6, 0))
    o.note("TPS26600: I_LIM ≈ 12 A·kΩ / R_ILIM → 7.5k ≈ 1.6 A (JST PH: 2 A per contact).")
    o.note("t_dVdT = 8e3 · V_IN · C_dVdT → 100 nF ≈ 16 ms at 20 V, 22 ms at 28 V.  A row of four nodes (≈ 450 µF) then")
    o.note("  charges at C / (8e3 · C_dVdT) ≈ 0.56 A (≤ 1.3 A at the corners with the nodes' load), under the 1.6 A limit.")
    o.note("  The eFuse takes ≈ 7–9 W typically, ≈ 14 W worst, for 19–24 ms: TI Fig. 55 with its 30 % margin (47 nF: ≈ 21 W, 12 ms).")
    o.note("IMON: 78 µA/A into 18k → 1.4 V/A (2.2 V at the limit), 1k + 47 nF to the ESP32's ADC: the pin is a current")
    o.note("  source, so τ = (18k + 1k) × 47 nF ≈ 0.9 ms, against the firmware's 250 ms polling.")
    o.note("SHDN: 10k to GND (row off: ≤ 10 µA from the pin, 0.1 V), ROW_EN through 10k → 1.65 V (TI: ≥ 1 V to turn on, p. 26).")
    o.note("The firmware holds ROW_EN with the ESP32's GPIO hold, so a controller reset leaves the rows as they were.")
    o.note("FLT: open drain, 100k to 3.3 V for the controller; the red LED (1k) is fed from ROW_EN: it lights only for")
    o.note("  a fault on an enabled row (FLT is also low while a row is off or starting).")
    o.note("D41–D44 B5819W: GND → each row's output at its connector, for the cable's kick when the eFuse cuts a short.")
    o.note("UVLO / OVP / MODE to GND: internal 15 V / 31–34 V (typ 32.6 V) thresholds, current-limit mode, auto-retry.")

    # ------------------------------------------------------------------ controller
    c = b.sheet("Controller", "controller.kicad_sch", "Rack controller: supplies, ESP32-S3, USB-C, CAN", paper="A2")
    c.block("5 V buck: LMR51625 (2.5 A; the controller takes < 0.7 A) and 4.7 µH, as the bay node (TI SLUSF64B table 8-1), from VRACK")
    part(c, "U2", "buck25", {"VIN": "VRACK", "EN": "BUCK_EN", "CB": "BUCK_CB", "SW": "BUCK_SW", "FB": "BUCK_FB",
                             "GND": "GND"}, pcb=P(58.00, 12.0 + BY, 0))
    C(c, "C104", "10u", "VRACK", "GND", size="1206", pcb=P(58.00, 16.8 + BY, 0))
    C(c, "C105", "10u", "VRACK", "GND", size="1206", pcb=P(58.00, 19.4 + BY, 0))
    C(c, "C106", "100n", "VRACK", "GND", pcb=P(58.00, 14.6 + BY, 0))
    # EN: on from ≈ 3.9 V, so the controller runs on a contract's first 5 V; the internal UVLO dominates, on at
    # 4.0-4.25 V, off below ≈ 3.8 V (the divider alone would let go at ≈ 3.1 V); 39k/18k,
    # values the board already has (one part type less in JLC's feeders)
    R(c, "R205", "39k", "VRACK", "BUCK_EN", pcb=P(54.78, 14.3 + BY, 90))
    R(c, "R206", "18k", "BUCK_EN", "GND", pcb=P(54.00, 12.0 + BY, 180))
    C(c, "C107", "100n", "BUCK_CB", "BUCK_SW", pcb=P(59.60, 9.5 + BY, 0))
    part(c, "L1", "buck_l47", {"1": "BUCK_SW", "2": "+5V_BUCK"}, "4.7u", pcb=P(65.70, 12.0 + BY, 0))
    for i in range(3):
        C(c, f"C{108 + i}", "22u", "+5V_BUCK", "GND", size="1206", pcb=P(64.0 + 2.5 * i, 18.5 + BY, 270))
    # FB 100k/18k: 0.8 V × (1 + 100/18) = 5.24 V, as the bay node; ≈ 4.9 V after D4 for the TJA1462AT (4.5–5.5 V)
    R(c, "R207", "100k", "+5V_BUCK", "BUCK_FB", pcb=P(54.00, 8.6 + BY, 0))
    R(c, "R208", "18k", "BUCK_FB", "GND", pcb=P(54.00, 10.2 + BY, 180))
    c.part("#FLG06", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+5V_BUCK"}, in_bom=False, on_board=False)
    c.block("5 V for the controller: the buck or the console USB-C (diode OR), 3.3 V low-dropout LDO")
    part(c, "D4", "schottky", {"A": "+5V_BUCK", "K": "+5V"}, pcb=P(73.2, 13.0 + BY, 90))
    part(c, "D5", "schottky", {"A": "USB_VBUS", "K": "+5V"}, pcb=P(56.0, H - 9.5, 180))
    c.part("#FLG07", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+5V"}, in_bom=False, on_board=False)
    c.part("#FLG08", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "USB_VBUS"}, in_bom=False, on_board=False)
    part(c, "U3", "ldo_lp", {"VIN": "+5V", "EN": "+5V", "GND": "GND", "VOUT": "+3V3"}, pcb=P(66.0, 49.0, 0))
    # the LDO's input cap (AP2112K: ≥ 1 µF); the buck's 3 × 22 µF sit just before D4.  The eFuses' 1 µF 0805
    C(c, "C111", "1u", "+5V", "GND", size="0805", pcb=P(62.4, 49.0, 90))
    C(c, "C112", "22u", "+3V3", "GND", size="1206", pcb=P(69.8, 49.0, 90))

    c.block("ESP32-S3-MINI-1 (antenna at the board's rear edge: no copper under it, either layer)")
    part(c, "U4", "esp32s3", {
        "3V3": "+3V3", "GND": "GND", "EN": "EN", "IO0": "BOOT", "USB_D-": "USB_DN", "USB_D+": "USB_DP",
        "IO1": "ADC_IMON_A", "IO2": "ADC_IMON_B", "IO4": "ADC_IMON_C", "IO5": "ADC_IMON_D", "IO6": "VBUS_SENSE",
        "IO7": "CAN_TXD", "IO8": "CAN_RXD", "IO9": "CAN_STB",
        "IO10": "POS_A", "IO11": "POS_B", "IO12": "POS_C", "IO13": "POS_D",
        "IO14": "ROW_EN_A", "IO15": "ROW_EN_B", "IO16": "ROW_EN_C", "IO17": "ROW_EN_D",
        "IO18": "FLT_A", "IO21": "FLT_B", "IO47": "FLT_C", "IO33": "FLT_D",
        "IO35": "CTL_LED", "IO39": "PD_INT", "IO40": "PD_SCL", "IO41": "PD_SDA", "IO42": "I2C_PU",
        "TXD0": "U0TX", "RXD0": "U0RX",
    }, pcb=P(30.0, 10.5, 0))
    C(c, "C113", "22u", "+3V3", "GND", size="1206", pcb=P(19.8, 10.5, 90))
    C(c, "C114", "100n", "+3V3", "GND", pcb=P(19.8, 14.6, 90))
    part(c, "SW1", "button", {"1": "EN", "2": "GND"}, "RESET", pcb=P(11.5, 10.0, 0))
    R(c, "R209", "10k", "+3V3", "EN", pcb=P(17.0, 9.5, 90))
    C(c, "C115", "1u", "EN", "GND", pcb=P(40.0, 6.15, 0))           # at EN (pin 45); R209 by the RESET button
    part(c, "SW2", "button", {"1": "BOOT", "2": "GND"}, "BOOT", pcb=P(11.5, 16.5, 0))
    R(c, "R210", "10k", "+3V3", "BOOT", pcb=P(17.0, 16.5, 90))
    part(c, "D8", "led_side_g", {"A": "CTL_LED_A", "K": "GND"}, "CTL", pcb=P(LED_X[5], LED_Y, 180))
    R(c, "R211", "1k", "CTL_LED", "CTL_LED_A", pcb=P(LED_X[5], H - 5.0, 90))
    for i, (net, xy, side) in enumerate((("U0TX", (30.0, 16.5), "bottom"), ("U0RX", (32.6, 16.5), "bottom"),
                                         ("GND", (30.0, 19.1), "bottom"), ("+3V3", (32.6, 19.1), "bottom"),
                                         ("+5V", (70.0, 54.0), "bottom"), ("VRACK", (66.0, 20.0), "bottom"),
                                         ("GND", (70.0, 30.0), "bottom"))):
        part(c, f"TP{i + 1}", "testpad", {"1": net}, net, pcb=P(*xy, 0, side), in_bom=False)
    # Eve's DFT rules (2026-10-26): the resets, the faults, the flashing pins, the analog IMON and the CH224A's I²C
    # on bare 1.0 mm bottom pads, > 2 mm from THT pads, in positions kept from revision to revision; a third GND
    # none on In2's VRACK band (y 21.6–29.6 under the module): their vias would cut it from the eFuse column
    sig = [("EN", (30.0, 13.9)), ("BOOT", (32.6, 13.9)), ("PD_SDA", (44.0, 9.0)), ("PD_SCL", (46.6, 9.0))]
    for k, ch in enumerate(ROWS):           # each row's FLT and IMON, at its eFuse cluster (row D's below the band)
        y0 = max(ef_y(k) - 1.3, 31.6)
        sig += [(f"FLT_{ch}", (44.0, y0)), (f"ADC_IMON_{ch}", (44.0, y0 + 2.6))]
    for i, (net, xy) in enumerate(sig):
        part(c, f"TP{8 + i}", "testpad1", {"1": net}, net, pcb=P(*xy, 0, "bottom"), in_bom=False)
    part(c, f"TP{8 + len(sig)}", "testpad", {"1": "GND"}, "GND", pcb=P(44.0, 54.0, 0, "bottom"), in_bom=False)
    for i, (net, sheet, d, xy, _, _) in enumerate(TP_ROUND2):     # each in the sheet its net belongs to
        part({"c": c, "o": o, "s": s}[sheet], f"TP{21 + i}", "testpad" if d > 1.2 else "testpad1", {"1": net}, net,
             pcb=P(*xy, 0, "bottom"), in_bom=False)

    c.block("USB-C: the controller's console / firmware (native USB), and its 5 V without a PD charger")
    part(c, "J6", "usbc5a", {"VBUS": "USB_VBUS", "GND": "GND", "CC1": "USB_CC1", "CC2": "USB_CC2",
                             "D+": "USB_CONN_DP", "D-": "USB_CONN_DN", "SBU1": None, "SBU2": None, "SHIELD": "GND"},
         "USB", pcb=P(USB_X, H - 3.4, 0))
    R(c, "R212", "5.1k", "USB_CC1", "GND", pcb=P(64.0, H - 10.2, 90))
    R(c, "R213", "5.1k", "USB_CC2", "GND", pcb=P(65.6, H - 10.2, 90))
    # flow-through, D+ on the 1–6 channel and D− on 3–4: the hand-routed pair arrives in that order
    part(c, "U5", "esd", {"6": "USB_CONN_DP", "1": "USB_DP", "4": "USB_CONN_DN", "3": "USB_DN", "5": "USB_VBUS",
                          "2": "GND"}, pcb=P(60.5, H - 12.5, 270))
    C(c, "C120", "1u", "USB_VBUS", "GND", pcb=P(63.6, H - 13.4, 90))

    c.block("CAN: TJA1462AT, star bus (all row ports in parallel), both terminations here")
    part(c, "U6", "can_xcvr", {"TXD": "CAN_TXD", "VSS": "GND", "VDD": "+5V", "RXD": "CAN_RXD", "Vio": "+3V3",
                               "CANL": "CAN_L", "CANH": "CAN_H", "STBY": "CAN_STB"}, "TJA1462AT", pcb=P(56.0, 60.0, 0))
    C(c, "C116", "100n", "+5V", "GND", pcb=P(50.6, 57.6, 0))
    C(c, "C117", "100n", "+3V3", "GND", pcb=P(50.6, 62.4, 0))
    # 5.1k: STB's internal pull-up can be 20 kΩ, so with IO9 floating 10k left STB at up to 1.10 V, above VIL
    # 0.99 V; 5.1k holds it ≤ 0.67 V (NXP TJA1462 §7.3.2, Table 8: datasheet audit F2)
    R(c, "R214", "5.1k", "CAN_STB", "GND", pcb=P(62.0, 57.4, 0))
    for i, (r1, r2, cc, mid, y) in enumerate((("R215", "R216", "C118", "CAN_TERM1", 64.0), ("R217", "R218", "C119", "CAN_TERM2", 66.6))):
        R(c, r1, "56", "CAN_H", mid, pcb=P(61.0, y, 0))
        R(c, r2, "56", mid, "CAN_L", pcb=P(64.4, y, 0))
        C(c, cc, "47n", mid, "GND", pcb=P(67.6, y, 0))      # split cap: the IMON filters' 47n, one type
    part(c, "D9", "can_esd", {"1": "CAN_H", "2": "CAN_L", "3": "GND"}, pcb=P(55.5, 66.0, 0))

    c.block("Mounting (M3, on the power box's standoffs)")
    for i, (x, y) in enumerate(CFG["holes"]):
        part(c, f"H{i + 1}", "hole", {}, "M3", pcb=P(x, y, 0), in_bom=False)
    c.note("GPIO: IO1/2/4/5 IMON A–D, IO6 VBUS_SENSE (ADC1) · IO7/8/9 CAN TX/RX/STB · IO10–13 POS A–D ·")
    c.note("  IO14–17 ROW_EN A–D · IO18/21/47/33 FLT A–D · IO39 PD_INT, IO40/41 PD_SCL/SDA, IO42 I2C_PU · IO35 CTL LED ·")
    c.note("  IO19/20 USB.  Strapping IO3/45/46 unused.")
    c.note("Termination: two split 2 × 56 Ω + 47 nF (56 Ω in all) at the star centre; nodes carry none.")
    c.note("+5V: buck (5.24 V; ≈ 4.8 V in dropout on a 5 V contract) or USB VBUS through B5819W Schottkys;")
    c.note("  AP2112K (250 mV dropout) keeps 3.3 V down to a 5 V contract.  The TJA1462AT wants 4.5–5.5 V: CAN runs once VRACK is up.")
    return b


NETCLASSES = [
    {"name": "Power", "clearance": 0.2, "track_width": 0.8, "via_diameter": 1.0, "via_drill": 0.5,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 1,
     # VRACK carries its current in pours and In2 (see b.pcb["zones"]); its tracks only feed LEDs and sense
     # VRACK reaches the buck in a hand-drawn 0.8 mm track: the router only adds thin sense / EN taps
     "_patterns": ["*ROW_?", "*+5V_BUCK", "*BUCK_SW"]},
    {"name": "USB", "clearance": 0.15, "track_width": 0.2, "via_diameter": 0.6, "via_drill": 0.3,
     "diff_pair_width": 0.25, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 2,
     "_patterns": ["*_DP", "*_DN"]},
]
