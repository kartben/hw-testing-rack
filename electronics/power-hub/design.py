"""Power hub v0.5 — one per rack, in the power box under A1 (mechanical/parts/power_box.scad).

USB-C PD in, from a dedicated USB PD 3.1 charger (140 W EPR recommended) on a 5 A e-marked cable.
An AP33772S sink controller (the FA01: the charger's 5 V first) negotiates the PD contract: the rack
controller asks it for 28 V EPR when the charger offers it, 20 V otherwise; the chip keeps the
contract, and the EPR keep-alive, through ESP32 reboots.  Its back-to-back NMOS switch connects VBUS to the rack bus
(VRACK, 20 or 28 V) once a contract is in place; a 5 mΩ Kelvin shunt gives it the input current.
VRACK fans out to four rows (A–D), each with its own TPS26600 eFuse:
  * current limit ≈ 1.6 A (RILIM 7.5k): it protects the JST PH (2 A) row cable;
  * slow start (dVdT 22 nF ≈ 5 ms at 28 V);
  * internal UV 15 V / OV 33 V defaults, auto-retry;
  * OFF until the controller turns it on: SHDN is pulled low, the ESP32 drives it high once the PD
    contract is final (row by row, staggered) and sheds rows when the contract drops;
  * ON (green, on the row's own output) and FAULT (red, from the open-drain FLT) side-view LEDs in
    the box's front wall.
The rack controller is an ESP32-S3-MINI-1 (Wi-Fi, the CAN master) on a buck and an LDO fed from
VBUS ahead of the switch, so it runs from the first 5 V of a contract (or from its own USB-C console
port).  It drives the AP33772S over I2C, reads each row's FLT and IMON, drives each row's enable,
and runs the rack's CAN bus and the POS addressing token (docs/can.md).  The row outputs are 6-pin
JST PH with the bay nodes' OUT pinout (J1's mirrored): POS, GND, CAN_L, CAN_H, GND, VRACK, so
every row cable is the same flat one (pin n to pin 7-n).  The bus is a star: every port carries
the same CAN pair, both terminations are here.

4 layers, 76 × 140 mm, the bay node's stackup and rules: In1 a solid GND plane, In2 power only
(a VRACK area under the eFuse column and the input, +3V3 around it), signals on the outer layers,
a via of its own to its plane for every GND and supply pin, GND pours stitched to In1
(config/rack.yaml › pcb.power_hub: outline, holes, connector and LED positions, which the box is
drawn around).  KiCad coordinates: y = 0 is the REAR edge (the ESP32's antenna, the PD input),
y = 140 the FRONT edge (LEDs, console USB-C); the row connectors sit on the left edge.

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
LED_X = CFG["front"]["leds"]        # ON/FAULT pair centres A–D, then PD, CTL
USB_X = CFG["front"]["usb"]
PD_X = CFG["rear"]["pd"]            # the USB-C PD input on the rear edge
PH_EDGE = 4.9                       # JST PH side entry: footprint origin from the board edge (as the bay node)
LED_Y = H - 1.25                    # side-view LED, lens at the front edge (rot 180)
EF_X = 26.0                         # eFuse centre (rot 0: IN on the left, OUT on the right, both at the top)
BY = 34.0                           # the buck block, moved down from the rear right (v0.4) by this much


def P(x, y, rot=0, side="top"):
    return {"x": x, "y": y, "rot": rot, "side": side}


def ef_y(k):
    return ROW_Y[k] - 0.5


def board() -> Board:
    b = Board("power-hub", "Power hub", "0.5",
              comments=["USB-C PD distribution + rack controller (ESP32-S3, CAN master) for the hw-testing-rack",
                        "Generated from electronics/power-hub/design.py — edit the Python, then regenerate"])
    b.root_notes = [
        "Power hub v0.5 — USB-C PD in (AP33772S: 20 V or 28 V EPR, as the controller asks) → NMOS switch → VRACK → 4 × TPS26600 "
        "eFuse (1.6 A) → 6-pin JST PH rows A–D.",
        "Rack controller: ESP32-S3-MINI-1 on VBUS (ahead of the switch), TJA1462AT (CAN master, star bus, both "
        "terminations here), POS token per row.",
        "Rows are OFF without firmware: SHDN is pulled low; the controller turns each row on once the PD contract is final.",
    ]

    # ------------------------------------------------------------------ PCB
    # In2 (power only): VRACK under the input, along the band at y ≈ 39 and down the eFuse column;
    # +3V3 everywhere else, one piece wrapping around it.  Outlines don't overlap: the router takes
    # each as copper of its net.
    in2 = [
        {"layer": "In2.Cu", "net": "VRACK", "priority": 1,
         "poly": [(16.2, 36.5), (45.6, 36.5), (45.6, 13.6), (75.6, 13.6), (75.6, 41.5), (24.6, 41.5),
                  (24.6, 117.0), (16.2, 117.0)]},
        {"layer": "In2.Cu", "net": "+3V3", "priority": 1,
         "poly": [(0.4, 0.4), (75.6, 0.4), (75.6, 13.2), (45.2, 13.2), (45.2, 36.1), (15.8, 36.1), (15.8, 117.4),
                  (25.0, 117.4), (25.0, 41.9), (75.6, 41.9), (75.6, 139.6), (0.4, 139.6)]},
    ]
    # per eFuse: a top-side VRACK island on its IN pins and the input capacitor, three vias to In2
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
    # PD input: CC1 straight down to a via (routed underneath to the AP33772S; CC2 leaves behind the
    # receptacle, the router's way), the Kelvin sense pair
    # from the shunt's own sense pads, the NMOS gates tied around the common-source pour
    tracks += [
        ("PD_CC1", "F.Cu", 0.2, [(PD_X + 1.25, 7.08), (PD_X + 1.25, 8.15)]),
        # Kelvin: R1's sense pads (2: VBUS side, 3: load side) straight to ISENP and VCC, a pad corner
        # each; VCC's own decoupling capacitor C4 sits on its trace
        ("PD_ISENP", "F.Cu", 0.15, [(55.8, 10.9), (52.475, 10.85)]),
        ("PD_VCCS", "F.Cu", 0.15, [(55.8, 12.1), (54.5, 12.1), (53.6, 12.825), (51.75, 12.825), (51.75, 11.575)]),
        # IFB's filter capacitor C7, right beside the pin (the left side of the chip is crowded)
        ("PD_IFB", "F.Cu", 0.15, [(48.525, 9.35), (47.55, 9.35), (47.0, 9.025)]),
        # gates: from R8 under both NMOS bodies, a stub down to each gate pin
        ("PD_GATE", "F.Cu", 0.3, [(51.4, 16.825), (51.4, 19.0), (62.905, 19.0), (62.905, 21.475)]),
        ("PD_GATE", "F.Cu", 0.3, [(57.405, 19.0), (57.405, 21.475)]),
        ("GND", "F.Cu", 0.25, [(PD_X + 3.2, 6.9), (PD_X + 4.2, 6.9)]),
        ("PD_VCC", "B.Cu", 0.8, [(55.8, 14.55), (55.8, 30.0), (56.7, 31.0), (56.7, 47.5)]),
        # I2C from the AP33772S's crowded right side to the pull-ups and the ESP32: Freerouting's routes
        # of v0.5's first layout, fixed here (the region is packed; left to the router, one of the two
        # can end up without a way out)
        ("PD_SDA", "F.Cu", 0.15, [(52.4625, 9.35), (52.5924, 9.2201), (53.394, 9.2201)]),
        ("PD_SDA", "F.Cu", 0.25, [(53.394, 9.2201), (53.4741, 9.3002), (53.7, 9.3002)]),
        ("PD_SDA", "B.Cu", 0.25, [(53.7, 9.3002), (52.8227, 8.4229), (43.8842, 8.4229), (42.7, 9.6071),
                                   (39.0359, 13.2712), (38.2063, 13.2712)]),
        ("PD_SDA", "F.Cu", 0.25, [(42.7, 9.6071), (42.8416, 9.4655)]),
        ("PD_SDA", "F.Cu", 0.1874, [(42.8416, 9.4655), (42.3585, 8.9824), (42.3585, 8.9308)]),
        ("PD_SDA", "F.Cu", 0.25, [(42.3585, 8.9308), (41.825, 8.3973), (41.825, 8.0)]),
        ("PD_SDA", "F.Cu", 0.25, [(38.2063, 13.2712), (37.6787, 13.7988), (37.6787, 13.9), (37.0, 13.9)]),
        ("PD_SCL", "F.Cu", 0.25, [(52.4625, 8.85), (52.8707, 8.85), (53.1869, 8.5338), (53.1869, 8.1028),
                                   (52.7457, 7.6616)]),
        ("PD_SCL", "B.Cu", 0.25, [(52.7457, 7.6616), (55.2461, 7.6616), (56.7093, 9.1248)]),
        ("PD_SCL", "B.Cu", 0.1874, [(56.7093, 9.1248), (58.2407, 7.5934), (59.924, 7.5934)]),
        ("PD_SCL", "B.Cu", 0.25, [(59.924, 7.5934), (60.4947, 7.5934), (60.8652, 7.9639), (60.8652, 8.3549),
                                   (58.3451, 10.875), (43.7069, 10.875), (43.2006, 11.3813), (39.966, 14.6159),
                                   (37.8651, 14.6159)]),
        ("PD_SCL", "F.Cu", 0.25, [(43.2006, 11.3813), (43.2006, 10.9756), (41.825, 9.6)]),
        ("PD_SCL", "F.Cu", 0.25, [(37.8651, 14.6159), (37.8128, 14.6159), (37.6787, 14.75), (37.0, 14.75)]),
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
            # PD input, on top where the current flows: VBUS (connector → TVS → shunt), the shunt's
            # load side (→ Q1's drain, the controller's buck), the common source, VRACK (Q2's drain,
            # the bulk capacitor, vias down to In2)
            {"layer": "F.Cu", "net": "PD_VBUS", "name": "pd-vbus", "priority": 3, "defer": False, "connection": "solid",
             "exclusive": 0.6, "poly": [(54.6, 7.6), (58.3, 7.6), (58.3, 6.6), (59.95, 6.6), (59.95, 8.8), (63.65, 8.8),
                                        (63.65, 6.6), (68.2, 6.6), (68.2, 10.6), (54.6, 10.6)]},
            {"layer": "F.Cu", "net": "PD_VCC", "name": "pd-vcc", "priority": 3, "defer": False, "connection": "solid",
             "exclusive": 0.6, "poly": [(54.6, 12.4), (57.0, 12.4), (57.0, 15.3), (57.9, 15.3), (57.9, 17.7), (53.2, 17.7),
                                        (53.2, 15.3), (54.6, 15.3)]},
            {"layer": "F.Cu", "net": "PD_SRC", "name": "pd-src", "priority": 3, "defer": False, "connection": "solid",
             "exclusive": 0.6, "poly": [(53.2, 20.3), (56.8, 20.3), (56.8, 22.9), (58.0, 22.9), (58.0, 20.3), (62.2, 20.3),
                                        (62.2, 25.2), (53.2, 25.2)]},
            {"layer": "F.Cu", "net": "VRACK", "name": "vrack-out", "priority": 3, "defer": False, "connection": "solid",
             "exclusive": 0.6, "poly": [(58.6, 15.2), (65.6, 15.2), (65.6, 16.3), (72.0, 16.3), (72.0, 26.0), (63.6, 26.0),
                                        (63.6, 18.1), (58.6, 18.1)]},
            *in_islands,
            # buck hot loop (as the bay node, TI SLUSF64B §8.4)
            {"layer": "F.Cu", "net": "GND", "connection": "solid", "name": "buck-gnd", "priority": 3,
             "poly": [(58.05, 12.5 + BY), (60.1, 12.5 + BY), (60.1, 14.2 + BY), (61.9, 14.2 + BY), (61.9, 18.3 + BY),
                      (70.6, 18.3 + BY), (70.6, 22.4 + BY), (58.05, 22.4 + BY)]},
            {"layer": "F.Cu", "net": "+5V_BUCK", "connection": "solid", "name": "buck-5v", "priority": 3,
             "poly": [(62.8, 16.1 + BY), (67.3, 16.1 + BY), (67.3, 8.6 + BY), (71.0, 8.6 + BY), (71.0, 17.9 + BY),
                      (62.8, 17.9 + BY)]},
            {"layer": "F.Cu", "net": "PD_VCC", "connection": "solid", "name": "buck-vin", "priority": 3,
             "poly": [(55.6, 12.5 + BY), (57.8, 12.5 + BY), (57.8, 20.7 + BY), (55.6, 20.7 + BY)]},
        ],
        "vias": [
            *[("GND", x, y + BY) for x, y in ((61.0, 14.9), (61.0, 17.4), (61.2, 21.4), (63.0, 21.6), (65.25, 21.6),
                                              (67.75, 21.6), (70.0, 21.6))],
            # eFuse IN islands down to In2 (VRACK); exposed pads: six tented GND vias each, to In1
            *[v for k in range(4) for v in (*[("VRACK", x, ef_y(k) - 2.0, 0.8, 0.4) for x in (19.4, 20.9, 22.4)],
                                            *[("GND", EF_X + dx, ef_y(k) + dy) for dx in (-0.9, 0.9) for dy in (-0.9, 0.0, 0.9)])],
            # each row's output: F.Cu → B.Cu beside the connector → F.Cu at its pin 6
            *[(f"ROW_{ch}", x, ROW_Y[k] + dy, 0.8, 0.4) for k, ch in enumerate(ROWS) for dy in (-5.0, 5.0)
              for x in (13.2, 14.3, 15.4)],
            # Q2's drain pour down to In2 (VRACK)
            *[("VRACK", x, y, 0.8, 0.4) for x, y in ((64.4, 18.6), (64.4, 20.4), (64.4, 22.2), (64.4, 24.0),
                                                     (70.6, 18.0), (70.6, 19.8), (66.6, 22.0), (68.4, 22.0), (63.2, 16.0))],
            # the AP33772S's exposed pad: four tented GND vias
            *[("GND", 50.5 + dx, 9.6 + dy, 0.5, 0.3) for dx in (-0.6, 0.6) for dy in (-0.6, 0.6)],
            # CC1 under the VBUS pour, on B.Cu
            ("PD_CC1", PD_X + 1.25, 8.15, 0.5, 0.3),
            ("PD_VCC", 55.8, 14.55, 0.8, 0.4), ("PD_VCC", 56.7, 47.5, 0.8, 0.4),
            # the fixed I2C routes' vias
            *[("PD_SDA", x, y, 0.6, 0.3) for x, y in ((53.7, 9.3002), (42.7, 9.6071), (38.2063, 13.2712))],
            *[("PD_SCL", x, y, 0.6, 0.3) for x, y in ((52.7457, 7.6616), (43.2006, 11.3813), (37.8651, 14.6159))],
        ],
        "tracks": tracks,
        # ESP32 antenna: no copper on any layer under/around it (module top 5 mm + the rear edge)
        "keepouts": [{"name": "antenna", "poly": [(21.3, -0.1), (38.7, -0.1), (38.7, 5.6), (21.3, 5.6)]}],
        "texts": [
            {"text": "hw-testing-rack · power hub v0.5", "x": 46, "y": 80, "size": 1.0},
            *[{"text": ch, "x": 12.5, "y": ROW_Y[k] + 7.6, "size": 1.2} for k, ch in enumerate(ROWS)],
        ],
    }

    # ------------------------------------------------------------------ input
    s = b.sheet("Input", "input.kicad_sch", "USB-C PD input")
    s.block("USB-C PD input (5 A receptacle, CC to the sink controller), TVS, 5 mΩ Kelvin shunt")
    part(s, "J1", "usbc5a", {"VBUS": "PD_VBUS", "GND": "GND", "CC1": "PD_CC1", "CC2": "PD_CC2", "SHIELD": "GND"},
         "PD IN", pcb=P(PD_X, 3.4, 180))
    for i, net in enumerate(("PD_VBUS", "PD_VCC", "PD_VCCS", "VRACK", "GND"), start=1):
        s.part(f"#FLG0{i}", "power:PWR_FLAG", "PWR_FLAG", "", {"1": net}, in_bom=False, on_board=False)
    part(s, "D1", "tvs30", {"K": "PD_VBUS", "A": "GND"}, pcb=P(67.4, 12.6, 270))
    C(s, "C1", "10u", "PD_VBUS", "GND", size="1206", pcb=P(61.0, 11.4, 270))
    C(s, "C2", "100n", "PD_VBUS", "GND", pcb=P(63.0, 11.2, 270))
    # current pads 1/4, sense pads 2/3 (net-tied to 1/4 inside the footprint)
    part(s, "R1", "shunt5m", {"1": "PD_VBUS", "2": "PD_ISENP", "3": "PD_VCCS", "4": "PD_VCC"}, "5m",
         pcb=P(55.8, 11.5, 270))

    s.block("AP33772S USB PD 3.1 sink (FA01): the charger's 5 V first, then 20 V / 28 V EPR as the controller asks over I2C;")
    s.block("drives the NMOS pair")
    part(s, "U1", "pd_sink", {"VCC": "PD_VCCS", "ISENP": "PD_ISENP", "PWR_EN": "PD_PWREN", "VOUT": "PD_VOUT",
                              "CC1": "PD_CC1", "CC2": "PD_CC2", "VSEL": "PD_VSEL", "OTP": "PD_OTP", "IFB": "PD_IFB",
                              "V5V": "PD_V5V", "V18": "PD_V18", "SDA": "PD_SDA", "SCL": "PD_SCL", "INT": "PD_INT5",
                              "LED": "PD_LED", "GND": "GND"}, pcb=P(50.5, 9.6, 180))
    C(s, "C4", "1u", "PD_VCCS", "GND", pcb=P(53.6, 13.6, 270))
    C(s, "C5", "1u", "PD_V5V", "GND", pcb=P(48.4, 14.0, 270))
    C(s, "C6", "100n", "PD_V18", "GND", pcb=P(44.4, 7.0, 180))
    C(s, "C7", "100n", "PD_IFB", "GND", pcb=P(47.0, 8.25, 90))
    R(s, "R5", "5.1k", "PD_CC1", "GND", pcb=P(46.0, 11.8, 180))
    R(s, "R6", "5.1k", "PD_CC2", "GND", pcb=P(46.0, 13.4, 180))
    # VSEL on an FA02 (20 V by itself); an NC pin on the FA01 fitted now: kept, so an FA02 drops in
    R(s, "R7", "39k", "PD_VSEL", "GND", pcb=P(44.4, 8.6, 180))
    part(s, "TH1", "ntc10k", {"1": "PD_OTP", "2": "GND"}, "10k NTC", pcb=P(60.4, 26.8, 0))
    R(s, "R8", "6.2k", "PD_PWREN", "PD_GATE", pcb=P(51.4, 16.0, 270))
    R(s, "R9", "200", "PD_VOUT", "VRACK", pcb=P(49.9, 14.0, 270))
    # both rot 90 (drains up, sources and gate down), side by side: common source along the bottom
    part(s, "Q1", "nfet_pwr", {"D": "PD_VCC", "S": "PD_SRC", "G": "PD_GATE"}, pcb=P(55.5, 19.0, 90))
    part(s, "Q2", "nfet_pwr", {"D": "VRACK", "S": "PD_SRC", "G": "PD_GATE"}, pcb=P(61.0, 19.0, 90))
    part(s, "C8", "cap100u50", {"1": "VRACK", "2": "GND"}, "100u/50V", pcb=P(70.0, 28.0, 270))
    C(s, "C9", "10u", "VRACK", "GND", size="1206", pcb=P(73.3, 19.6, 0))
    C(s, "C10", "100n", "VRACK", "GND", pcb=P(73.0, 22.2, 0))
    s.block("I2C to the controller, VBUS sense")
    # INT is a 5 V push-pull output: divided down for the ESP32 (10k/18k: 3.2 V; values the board already has)
    R(s, "R11", "10k", "PD_INT5", "PD_INT", pcb=P(41.0, 11.2, 0))
    R(s, "R12", "18k", "PD_INT", "GND", pcb=P(41.0, 12.8, 0))
    # pull-ups from a GPIO (I2C_PU): on only once VBUS is up, so a USB-powered controller never
    # back-feeds an unpowered AP33772S through SDA/SCL (Diodes' EVB guide: the sink powers up first)
    R(s, "R13", "5.1k", "I2C_PU", "PD_SDA", pcb=P(41.0, 8.0, 0))
    R(s, "R14", "5.1k", "I2C_PU", "PD_SCL", pcb=P(41.0, 9.6, 0))
    R(s, "R3", "100k", "PD_VBUS", "VBUS_SENSE", pcb=P(64.6, 11.4, 270))
    R(s, "R4", "10k", "VBUS_SENSE", "GND", pcb=P(19.0, 20.4, 0))
    C(s, "C3", "100n", "VBUS_SENSE", "GND", pcb=P(19.0, 22.0, 0))
    s.block("PD status (front LED), driven by the AP33772S: breathing = contract and VRACK on, steady = the charger")
    s.block("can't give what the controller asked for, flicker = fault (OVP, OCP, UVP, OTP)")
    R(s, "R2", "1k", "PD_LED", "PD_LED_A", pcb=P(LED_X[4], H - 5.0, 90))
    part(s, "D3", "led_side_g", {"A": "PD_LED_A", "K": "GND"}, "PD", pcb=P(LED_X[4], LED_Y, 180))
    s.note("U1 is the FA01 (the FA02 was out of stock): it takes the charger's 5 V and waits; the controller sets VSELMIN to")
    s.note("  15 V (the switch opens below it) and asks for 20 V or 28 V EPR.  Rows stay locked out below 15 V (eFuse UV).")
    s.note("R7 39 kΩ: VSEL on an FA02 (20 V by itself at power-up), NC on the FA01; kept so that an FA02 drops in.")
    s.note("The chip turns the NMOS pair on once a contract is in place and VREQ ≥ VSELMIN, and off on OVP/OCP/UVP/OTP.")
    s.note("SMAJ30A: 30 V stand-off, above a 28 V EPR contract; the eFuses (60 V) and the TPS26600 OVP (33 V) follow.")
    s.note("R1 5 mΩ: ISENP and VCC leave from its own sense pads (Kelvin), the AP33772S reads the input current.")
    s.note("VBUS_SENSE: 100k/10k from VBUS → 2.5 V at 28 V for the ESP32's ADC; also tells the firmware when to enable I2C_PU.")

    # ------------------------------------------------------------------ outputs
    o = b.sheet("Outputs", "outputs.kicad_sch", "Four eFused row outputs (6-pin JST PH)")
    for k, ch in enumerate(ROWS):
        n = k + 1
        yc, yj = ef_y(k), ROW_Y[k]
        o.block(f"Row {ch}: TPS26600 eFuse 1.6 A, enable, ON / FAULT LEDs, 6-pin JST PH")
        part(o, f"U{10 + n}", "efuse", {"IN": "VRACK", "GND": "GND", "RTN": "GND", "UVLO": "GND", "OVP": "GND",
                                        "MODE": "GND", "~{SHDN}": f"SHDN_{ch}", "ILIM": f"ILIM_{ch}",
                                        "dVdT": f"DVDT_{ch}", "IMON": f"IMON_{ch}", "~{FLT}": f"FLT_{ch}",
                                        "OUT": f"ROW_{ch}"}, pcb=P(EF_X, yc, 0))
        C(o, f"C{10 + n}", "1u", "VRACK", "GND", size="0805", pcb=P(16.9, yc - 2.0, 180))
        C(o, f"C{30 + n}", "1u", f"ROW_{ch}", "GND", size="0805", pcb=P(34.0, yc - 2.6, 0))
        R(o, f"R{20 + n}", "7.5k", f"ILIM_{ch}", "GND", pcb=P(34.0, yc + 1.0, 0))
        C(o, f"C{20 + n}", "22n", f"DVDT_{ch}", "GND", pcb=P(34.0, yc + 2.6, 0))
        R(o, f"R{30 + n}", "18k", f"IMON_{ch}", "GND", pcb=P(34.0, yc + 4.2, 0))
        R(o, f"R{60 + n}", "1k", f"IMON_{ch}", f"ADC_IMON_{ch}", pcb=P(37.4, yc + 4.2, 0))
        C(o, f"C{60 + n}", "22n", f"ADC_IMON_{ch}", "GND", pcb=P(40.4, yc + 4.2, 0))
        # SHDN: off by default (100k to GND); the controller drives ROW_EN high, through 10k, to turn it on
        R(o, f"R{70 + n}", "100k", f"SHDN_{ch}", "GND", pcb=P(21.4, yc + 4.5, 270))
        R(o, f"R{80 + n}", "10k", f"ROW_EN_{ch}", f"SHDN_{ch}", pcb=P(19.0, yc + 3.675, 0))
        # FLT: open drain, pulled up to 3.3 V for the controller; red LED from 3.3 V (1k: ≈ 1.4 mA, every
        # front LED on the board's 1k, one part type for all)
        R(o, f"R{90 + n}", "100k", "+3V3", f"FLT_{ch}", pcb=P(34.0, yc - 0.6, 0))
        R(o, f"R{50 + n}", "1k", "+3V3", f"FLTLED_{ch}", pcb=P(LED_X[k] + 3.0, H - 5.0, 90))
        part(o, f"D{20 + n}", "led_side_r", {"A": f"FLTLED_{ch}", "K": f"FLT_{ch}"}, "FAULT",
             pcb=P(LED_X[k] + 3.0, LED_Y, 180))
        # ON: green LED on the row's own output
        R(o, f"R{40 + n}", "10k", f"ROW_{ch}", f"ON_{ch}", pcb=P(36.825, yc - 4.5, 0))
        part(o, f"D{10 + n}", "led_side_g", {"A": f"ON_{ch}", "K": "GND"}, "ON", pcb=P(LED_X[k] - 3.0, LED_Y, 180))
        # the row cable, with the bay nodes' OUT pinout (J1's mirrored, docs/can.md): POS, GND, CAN_L,
        # CAN_H, GND, VRACK, so the feed is the same flat cable as the node-to-node jumpers.  POS through
        # 10k (behind pin 1) + a clamp to GND / 3.3 V, so VRACK on it from a wrong cable costs ≈ 3 mA
        part(o, f"J{1 + n}", "ph6", {"1": f"POS_{ch}_CONN", "2": "GND", "3": "CAN_L", "4": "CAN_H", "5": "GND",
                                    "6": f"ROW_{ch}"}, f"ROW {ch}", pcb=P(PH_EDGE, yj, 270))
        R(o, f"R{100 + n}", "10k", f"POS_{ch}", f"POS_{ch}_CONN", pcb=P(11.0, yj - 7.2, 90))
        part(o, f"D{30 + n}", "bat54s", {"A": "GND", "K": "+3V3", "COM": f"POS_{ch}"}, pcb=P(16.6, yj + 7.6, 0))
    o.note("TPS26600: I_LIM ≈ 12 A·kΩ / R_ILIM → 7.5k ≈ 1.6 A (JST PH: 2 A per contact).")
    o.note("t_dVdT = 8e3 · V_IN · C_dVdT → 22 nF ≈ 3.5 ms at 20 V, 4.9 ms at 28 V.")
    o.note("IMON: 78 µA/A into 18k → 1.4 V/A (2.2 V at the limit), 1k + 10 nF to the ESP32's ADC.")
    o.note("SHDN: 100k to GND (row off), ROW_EN through 10k → 3.0 V (the datasheet's SHDN range is 0–4 V).")
    o.note("The firmware holds ROW_EN with the ESP32's GPIO hold, so a controller reset leaves the rows as they were.")
    o.note("FLT: open drain, 100k to 3.3 V for the controller; the red LED (680 Ω) lights while it is low.")
    o.note("UVLO / OVP / MODE to GND: internal 15 V / 33 V thresholds, current-limit mode, auto-retry.")

    # ------------------------------------------------------------------ controller
    c = b.sheet("Controller", "controller.kicad_sch", "Rack controller: supplies, ESP32-S3, USB-C, CAN")
    c.block("5 V buck: LMR51635, as the bay node (TI SLUSF64B table 8-2), from VBUS ahead of the switch")
    part(c, "U2", "buck", {"VIN": "PD_VCC", "EN": "BUCK_EN", "CB": "BUCK_CB", "SW": "BUCK_SW", "FB": "BUCK_FB",
                           "GND": "GND"}, pcb=P(58.00, 12.0 + BY, 0))
    C(c, "C104", "10u", "PD_VCC", "GND", size="1206", pcb=P(58.00, 16.8 + BY, 0))
    C(c, "C105", "10u", "PD_VCC", "GND", size="1206", pcb=P(58.00, 19.4 + BY, 0))
    C(c, "C106", "100n", "PD_VCC", "GND", pcb=P(58.00, 14.6 + BY, 0))
    # EN: on from ≈ 3.9 V (off below ≈ 3.1 V), so the controller runs on a contract's first 5 V; 39k/18k,
    # values the board already has (one part type less in JLC's feeders)
    R(c, "R205", "39k", "PD_VCC", "BUCK_EN", pcb=P(54.78, 14.3 + BY, 90))
    R(c, "R206", "18k", "BUCK_EN", "GND", pcb=P(54.00, 12.0 + BY, 180))
    C(c, "C107", "100n", "BUCK_CB", "BUCK_SW", pcb=P(59.60, 9.5 + BY, 0))
    part(c, "L1", "buck_l", {"1": "BUCK_SW", "2": "+5V_BUCK"}, "3.3u", pcb=P(65.70, 12.0 + BY, 0))
    for i in range(3):
        C(c, f"C{108 + i}", "22u", "+5V_BUCK", "GND", size="1206", pcb=P(64.0 + 2.5 * i, 18.5 + BY, 270))
    # FB 100k/18k: 0.8 V × (1 + 100/18) = 5.24 V, as the bay node; ≈ 4.9 V after D4 for the TJA1462AT (4.5–5.5 V)
    R(c, "R207", "100k", "+5V_BUCK", "BUCK_FB", pcb=P(54.00, 8.6 + BY, 0))
    R(c, "R208", "18k", "BUCK_FB", "GND", pcb=P(54.00, 10.2 + BY, 180))
    c.part("#FLG06", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+5V_BUCK"}, in_bom=False, on_board=False)
    c.block("5 V for the controller: the buck or the console USB-C (diode OR), 3.3 V low-dropout LDO")
    part(c, "D4", "schottky", {"A": "+5V_BUCK", "K": "+5V"}, pcb=P(73.2, 13.0 + BY, 90))
    part(c, "D5", "schottky", {"A": "USB_VBUS", "K": "+5V"}, pcb=P(56.0, 130.5, 180))
    c.part("#FLG07", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+5V"}, in_bom=False, on_board=False)
    c.part("#FLG08", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "USB_VBUS"}, in_bom=False, on_board=False)
    part(c, "U3", "ldo_lp", {"VIN": "+5V", "EN": "+5V", "GND": "GND", "VOUT": "+3V3"}, pcb=P(66.0, 61.0, 0))
    # the LDO's input cap (AP2112K: ≥ 1 µF); the buck's 3 × 22 µF sit just before D4.  The eFuses' 1 µF 0805
    C(c, "C111", "1u", "+5V", "GND", size="0805", pcb=P(62.4, 61.0, 90))
    C(c, "C112", "22u", "+3V3", "GND", size="1206", pcb=P(69.8, 61.0, 90))

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
    C(c, "C115", "1u", "EN", "GND", pcb=P(17.0, 13.0, 90))
    part(c, "SW2", "button", {"1": "BOOT", "2": "GND"}, "BOOT", pcb=P(11.5, 16.5, 0))
    R(c, "R210", "10k", "+3V3", "BOOT", pcb=P(17.0, 16.5, 90))
    part(c, "D8", "led_side_g", {"A": "CTL_LED_A", "K": "GND"}, "CTL", pcb=P(LED_X[5], LED_Y, 180))
    R(c, "R211", "1k", "CTL_LED", "CTL_LED_A", pcb=P(LED_X[5], H - 5.0, 90))
    for i, (net, xy, side) in enumerate((("U0TX", (30.0, 16.5), "bottom"), ("U0RX", (32.6, 16.5), "bottom"),
                                         ("GND", (30.0, 19.1), "bottom"), ("+3V3", (32.6, 19.1), "bottom"),
                                         ("+5V", (70.0, 66.0), "bottom"), ("VRACK", (66.0, 20.0), "bottom"),
                                         ("GND", (70.0, 30.0), "bottom"), ("PD_VCC", (55.5, 14.0), "bottom"))):
        part(c, f"TP{i + 1}", "testpad", {"1": net}, net, pcb=P(*xy, 0, side), in_bom=False)

    c.block("USB-C: the controller's console / firmware (native USB), and its 5 V without a PD charger")
    part(c, "J6", "usbc5a", {"VBUS": "USB_VBUS", "GND": "GND", "CC1": "USB_CC1", "CC2": "USB_CC2",
                             "D+": "USB_CONN_DP", "D-": "USB_CONN_DN", "SBU1": None, "SBU2": None, "SHIELD": "GND"},
         "USB", pcb=P(USB_X, H - 3.4, 0))
    R(c, "R212", "5.1k", "USB_CC1", "GND", pcb=P(64.0, H - 10.2, 90))
    R(c, "R213", "5.1k", "USB_CC2", "GND", pcb=P(65.6, H - 10.2, 90))
    part(c, "U5", "esd", {"6": "USB_CONN_DN", "1": "USB_DN", "4": "USB_CONN_DP", "3": "USB_DP", "5": "USB_VBUS",
                          "2": "GND"}, pcb=P(60.5, H - 12.5, 270))
    C(c, "C120", "1u", "USB_VBUS", "GND", pcb=P(60.5, H - 16.4, 0))

    c.block("CAN: TJA1462AT, star bus (all row ports in parallel), both terminations here")
    part(c, "U6", "can_xcvr", {"TXD": "CAN_TXD", "VSS": "GND", "VDD": "+5V", "RXD": "CAN_RXD", "Vio": "+3V3",
                               "CANL": "CAN_L", "CANH": "CAN_H", "STBY": "CAN_STB"}, "TJA1462AT", pcb=P(14.0, 32.0, 0))
    C(c, "C116", "100n", "+5V", "GND", pcb=P(8.6, 29.6, 0))
    C(c, "C117", "100n", "+3V3", "GND", pcb=P(8.6, 34.4, 0))
    R(c, "R214", "10k", "CAN_STB", "GND", pcb=P(20.0, 29.4, 0))
    for i, (r1, r2, cc, mid, y) in enumerate((("R215", "R216", "C118", "CAN_TERM1", 36.0), ("R217", "R218", "C119", "CAN_TERM2", 38.6))):
        R(c, r1, "56", "CAN_H", mid, pcb=P(19.0, y, 0))
        R(c, r2, "56", mid, "CAN_L", pcb=P(22.4, y, 0))
        C(c, cc, "22n", mid, "GND", pcb=P(25.6, y, 0))      # split cap: the eFuses' 22n (dVdT, IMON filter), one type
    part(c, "D9", "can_esd", {"1": "CAN_H", "2": "CAN_L", "3": "GND"}, pcb=P(14.5, 37.5, 0))

    c.block("Mounting (M3, on the power box's standoffs)")
    for i, (x, y) in enumerate(CFG["holes"]):
        part(c, f"H{i + 1}", "hole", {}, "M3", pcb=P(x, y, 0), in_bom=False)
    c.note("GPIO: IO1/2/4/5 IMON A–D, IO6 VBUS_SENSE (ADC1) · IO7/8/9 CAN TX/RX/STB · IO10–13 POS A–D ·")
    c.note("  IO14–17 ROW_EN A–D · IO18/21/47/33 FLT A–D · IO39 PD_INT, IO40/41 PD_SCL/SDA, IO42 I2C_PU · IO35 CTL LED ·")
    c.note("  IO19/20 USB.  Strapping IO3/45/46 unused.")
    c.note("Termination: two split 2 × 56 Ω + 4.7 nF (56 Ω in all) at the star centre; nodes carry none.")
    c.note("+5V: buck (5.24 V; ≈ 4.8 V in dropout on a 5 V contract) or USB VBUS through B5819W Schottkys;")
    c.note("  AP2112K (250 mV dropout) keeps 3.3 V down to a 5 V contract.  The TJA1462AT wants 4.5–5.5 V: CAN runs once VRACK is up.")
    return b


NETCLASSES = [
    {"name": "Power", "clearance": 0.2, "track_width": 0.8, "via_diameter": 1.0, "via_drill": 0.5,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 1,
     # VRACK carries its current in pours and In2 (see b.pcb["zones"]); its tracks only feed LEDs and sense
     # PD_VCC reaches the buck in a hand-drawn 0.8 mm track: the router only adds thin sense / EN taps
     "_patterns": ["*PD_VBUS", "*PD_SRC", "*ROW_?", "*+5V_BUCK", "*BUCK_SW"]},
    {"name": "USB", "clearance": 0.15, "track_width": 0.2, "via_diameter": 0.6, "via_drill": 0.3,
     "diff_pair_width": 0.25, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 2,
     "_patterns": ["*_DP", "*_DN"]},
]
