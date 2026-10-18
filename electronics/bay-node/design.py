"""Bay node — one per bay: ESP32-S3 USB/IP host for the board under test (DUT).

Functions
  * Row cable in/out (JST PH 6, daisy-chained bay to bay, docs/can.md): the row bus (24 V nominal,
    20–28 V from a USB-C PD supply), the rack's CAN pair and the POS addressing token.
    Reverse-polarity P-FET, TVS, LMR51635 synchronous buck to 5 V / 3.5 A, 3.3 V LDO for the logic.
  * CAN: TCAN1044AV on the ESP32-S3 TWAI, tapping the pair that runs J1 → J2 (no termination).
  * POS: token in on J1.6, out on J2.6, each through 10k + a BAT54S clamp (survives +24 V).
  * DUT port (USB-C, source): DUT_5V through a TPS2553 current-limited switch
    (≈1.4 A) and a 50 mΩ shunt read by an INA226; D+/D- through ESD.
  * Two USB 2.0 muxes:
      MUX_DUT: DUT ↔ ESP32-S3 USB-OTG (USB/IP mode, default)
               DUT ↔ front PC port      (classic mode: plug a laptop and the
                                          DUT is yours, even with no firmware)
      MUX_PC : front PC port ↔ DUT path, or ↔ ESP32-S3 USB-Serial-JTAG when the
               SERVICE switch is on (flash/debug the node itself).
    SERVICE also disables MUX_DUT so the ESP32's single USB PHY is never
    connected to two hosts at once.
  * AUX (JST PH 6): UART TX/RX + open-drain RESET/BOOT lines to the DUT.
  * CAM (JST-PH 2): 5 V for the camera pod hanging under this carrier.
  * WS2812B status LED behind the fascia, RESET/BOOT buttons, UART test pads.

Net names follow the power path: 24V_BUS (daisy chain) → Q1 → +24V → buck →
+5V → TPS2553 → DUT_5V_SW → 50 mΩ shunt → DUT_5V (the DUT's VBUS).  The
INA226 itself runs from +3V3 and reads the drop across the shunt.

Schematic: every part has an `sch=` position (0.1" grid units, see
electronics/tools/eda.py) and the main paths are drawn as wires.
KiCad coordinates for `pcb` hints: board origin top-left, y = 0 is the REAR
edge, y = 80 the FRONT (fascia) edge; see config/rack.yaml → pcb.bay_node.
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
CFG = RACK.raw["pcb"]["bay_node"]
W, H = CFG["size"]
PWR_Y = CFG["pwr_y"]          # centre of the 24 V in/out connectors (left/right edges)
# JST PH side entry, SMD (S*B-PH-SM4-TB): footprint origin 4.9 mm in from the board edge, which puts the
# mouth 0.5 mm inside it so the fitting tabs keep their copper-to-edge clearance; pins 7.75 mm in
PH_EDGE = 4.9
# Draw the USB pairs of the classic-mode path by hand (usb_hs_routes) for High-Speed, or leave them
# to Freerouting (full speed only is designed for; the ESD/mux GND and VBUS escapes stay drawn)
USB_HS_PAIRS = True


def P(x, y, rot=0, side="top"):
    return {"x": x, "y": y, "rot": rot, "side": side}


def at(x, y, rot=0, mirror="", fields=None):
    """Schematic position in 0.1" grid units."""
    d = {"x": x, "y": y, "rot": rot}
    if mirror:
        d["mirror"] = mirror
    if fields is not None:
        d["fields"] = fields
    return d


def usb_hs_routes():
    """The classic-mode USB path (laptop on J3 ↔ DUT on J4 through U4, U5, U6, U8) carries High-Speed
    (480 Mb/s) whenever the DUT supports it, so it is drawn here instead of by Freerouting: coupled
    pairs on F.Cu over the solid In1 plane, 0.25 mm tracks with a 0.15 mm gap (≈ 90 Ω differential on
    JLC04161H-7628, field-solver estimate in docs/electronics.md), ESD parts in flow-through, lengths
    matched (vias counted as the 1.6 mm they cross).

    J3 → U4 → straight north up the middle → U5 (MUX_PC) → east → U6 (MUX_DUT) → U8 → J4.  The two
    FSUSB42s number their pins the same way round, so PCPATH must cross over once: PCPATH_DN hops
    under PCPATH_DP on B.Cu, and small bumps on PC_DP, on the straight run, make up the two vias.  U4/U8
    pass each line through the part (connector-side and protected-side pins are separate nets); their
    GND and VBUS pins get a via between the spread tracks.  On each USB-C receptacle the A-side pins
    (A6/A7) are the through path; B6 joins A6 by a loop around the pad row, B7 joins A7 through B.Cu.
    With USB_HS_PAIRS off, the pairs are left to Freerouting (full speed).  Returns (tracks, vias)."""
    tracks, vias = [], []

    def pair(net):
        return net.endswith(("_DP", "_DN")) and not USB_HS_PAIRS

    def t(net, *pts, layer="F.Cu", w=0.25):
        if not pair(net):
            tracks.append((net, layer, w, list(pts)))

    def via(net, x, y, d=0.5, drill=0.3):
        if not pair(net):
            vias.append((net, x, y, d, drill))

    # J3 (front PC port) → U4 (ESD, rot 270: D+ through pins 4/3 at x 31.05, D− through 6/1 at 32.95)
    t("PC_CONN_DP", (31.75, 72.555), (31.75, 70.9), (31.05, 70.2), (31.05, 68.1375))        # → U4 pin 4
    t("PC_CONN_DN", (32.25, 72.555), (32.25, 70.9), (32.95, 70.2), (32.95, 68.1375))        # → U4 pin 6
    t("PC_CONN_DP", (32.75, 72.555), (32.75, 73.85), (31.75, 73.85), (31.75, 72.555))  # B6 → A6
    t("PC_CONN_DN", (31.25, 72.555), (31.2, 71.35))                                     # B7 → A7
    t("PC_CONN_DN", (31.2, 71.35), (32.3, 71.25), layer="B.Cu")
    via("PC_CONN_DN", 31.2, 71.35)
    via("PC_CONN_DN", 32.3, 71.25)
    # U4's VBUS pin: its via sits in the front +3V3 area of In2, so a B.Cu track takes it past the 24 V
    # strip to the +5V area; its GND pin gets a via between the spread pins
    t("+5V", (32.0, 68.1375), (32.0, 69.55), w=0.3)
    via("+5V", 32.0, 69.55)
    t("+5V", (32.0, 69.55), (33.6, 69.55), (33.6, 54.8), layer="B.Cu", w=0.3)
    via("+5V", 33.6, 54.8)
    t("GND", (32.0, 65.8625), (32.0, 64.55), w=0.3)
    via("GND", 32.0, 64.55)

    # U4 pins 3/1 → north at x 31.05 / 31.45 → U5 (MUX_PC, rot 0) D+/D− (pins 3/4 at y 27.5/28.0, x 32.5)
    bumps = []
    for y in (45.0, 43.5, 42.0, 40.5):
        bumps += [(31.05, y), (30.25, y - 0.2), (30.25, y - 0.7), (31.05, y - 0.9)]
    t("PC_DP", (31.05, 65.8625), *bumps, (31.05, 27.95), (31.5, 27.5), (32.5, 27.5))
    t("PC_DN", (32.95, 65.8625), (32.95, 64.5), (31.45, 63.0), (31.45, 28.2), (31.65, 28.0), (32.5, 28.0))

    # U5 HSD1 (pins 7/6 at y 28.0/28.5, x 36.7) → U6 HSD2 (rot 180: pins 9/8 at y 25.0/24.5, x 42.4).
    # PCPATH_DN crosses under PCPATH_DP on B.Cu between the two vias.
    t("PCPATH_DP", (36.7, 28.0), (38.9, 28.0), (40.9, 26.0), (40.9, 25.4), (41.3, 25.0), (42.4, 25.0))
    t("PCPATH_DN", (36.7, 28.5), (38.2, 28.5), (38.6, 28.9))
    t("PCPATH_DN", (38.6, 28.9), (40.2, 27.3), (40.2, 24.9), layer="B.Cu")
    t("PCPATH_DN", (40.2, 24.9), (40.6, 24.5), (42.4, 24.5))
    via("PCPATH_DN", 38.6, 28.9)
    via("PCPATH_DN", 40.2, 24.9)
    # U5's ~OE (GND): out of the top of its pad, to a via above the package
    t("GND", (36.7, 26.5), (36.7, 25.35), w=0.25)
    via("GND", 36.7, 25.35)

    # U6 D−/D+ (pins 4/3 at y 24.0/24.5, x 46.6) → U8 (ESD, rot 0: DN through pins 1/6 at y 23.05,
    # DP through 3/4 at y 24.95) → J4 (DUT port) A7/A6
    t("DUT_DN", (46.6, 24.0), (47.7, 24.0), (48.65, 23.05), (50.16, 23.05))
    t("DUT_DP", (46.6, 24.5), (48.0, 24.5), (48.45, 24.95), (50.16, 24.95))
    t("DUT_CONN_DN", (52.44, 23.05), (54.35, 23.05), (55.05, 23.75), (56.35, 23.75))
    t("DUT_CONN_DP", (52.44, 24.95), (54.1, 24.95), (54.8, 24.25), (56.35, 24.25))
    t("DUT_CONN_DP", (56.35, 23.25), (57.45, 23.25), (57.45, 24.25), (56.35, 24.25))    # B6 → A6
    t("DUT_CONN_DN", (56.35, 24.75), (55.05, 24.78))                                    # B7 → A7
    t("DUT_CONN_DN", (55.05, 24.78), (54.95, 23.65), layer="B.Cu")
    via("DUT_CONN_DN", 55.05, 24.78)
    via("DUT_CONN_DN", 54.95, 23.65)
    t("GND", (46.6, 23.5), (47.35, 23.5), (47.85, 23.0))                                # U6 pin 5
    via("GND", 47.85, 23.0)
    t("GND", (50.16, 24.0), (49.0, 24.0))                                               # U8 GND
    via("GND", 49.0, 24.0)
    t("+5V", (52.44, 24.0), (53.6, 24.0))                                               # U8 VBUS
    via("+5V", 53.6, 24.0)
    # J4's CC1 pin sits below the pair: out to the west, down to R14
    t("DUT_CC1", (56.35, 25.3), (54.95, 25.3), (54.3, 25.95), (54.3, 27.58), w=0.2)
    # J4's two VBUS pads sit behind the pair: a via each, DUT_5V joins them on B.Cu; R14 up to the via
    t("DUT_5V", (56.35, 26.45), (55.2, 26.45), w=0.6)
    via("DUT_5V", 55.2, 26.45, 0.8, 0.4)
    t("DUT_5V", (56.35, 21.55), (55.2, 21.55), w=0.6)
    via("DUT_5V", 55.2, 21.55, 0.8, 0.4)
    t("DUT_5V", (55.2, 26.45), (56.0, 25.65), (56.0, 22.35), (55.2, 21.55), layer="B.Cu", w=0.6)
    t("DUT_5V", (54.3, 29.22), (55.2, 28.32), (55.2, 26.45), w=0.3)
    return tracks, vias


def board() -> Board:
    b = Board("bay-node", "Bay node", "0.5",
              comments=["ESP32-S3 USB/IP host for one bay of the hw-testing-rack shelf",
                        "Generated from electronics/bay-node/design.py — edit the Python, then regenerate",
                        "Row bus 20–28 V + CAN + POS in/out · 5 V/1.4 A switched DUT port · USB 2.0 muxes · INA226 · AUX"])
    b.root_notes = [
        "Bay node — one per bay.  Sheets:",
        "  Power: row cable (JST PH 6: bus, GND, CAN_H, CAN_L, GND, POS), reverse protection, LMR51635 buck, AMS1117",
        "  MCU: ESP32-S3-MINI-1, reset/boot, status LED, UART pads",
        "  USB: front PC port, DUT port, two FSUSB42 muxes + OR gate (classic / USB-IP / service modes)",
        "  DUT power & AUX: TPS2553 switch → shunt → DUT_5V, INA226 monitor, AUX UART/RESET/BOOT, camera 5 V",
        "  Rack bus: TCAN1044AV CAN transceiver on the row pair, POS token in/out (docs/can.md)",
        "",
        "Mode truth table:  SERVICE=0, PC unplugged → DUT↔ESP32 (USB/IP)",
        "                   SERVICE=0, PC plugged   → DUT↔PC (classic), ESP32 still controls DUT_5V/AUX",
        "                   SERVICE=1               → PC↔ESP32 (flash/console), DUT data disconnected",
        "GPIO firmware can also force classic mode (MUX_FORCE_PC).",
    ]
    # the row bus on In2: J1 pin 1 (left edge, rear end of the 6-pin connector, y = PWR_Y - 5) to J2 pin 1
    # (right edge, front end, y = PWR_Y + 5): a strip across the board above the connectors' other pins,
    # then down the right edge under J2's housing.  3.8 mm wide (≈ 1.9 A in 0.5 oz for 10 °C)
    bus = [(0.5, PWR_Y - 7.2), (63.5, PWR_Y - 7.2), (63.5, PWR_Y + 6.4), (58.2, PWR_Y + 6.4), (58.2, PWR_Y - 3.4),
           (0.5, PWR_Y - 3.4)]
    hs_tracks, hs_vias = usb_hs_routes()
    b.pcb = {
        "size": (W, H), "layers": CFG["layers"], "corner_radius": 2.0, "passes": 60,
        # 4 layers: signals + GND / GND only / power only / signals + GND.  In1 is a solid GND plane;
        # In2 carries power planes and nothing else (+3V3, +5V, the 24 V bus strip): no signal is
        # routed on it.  Every GND and supply pin gets its own via to its plane before routing
        # ("fanout_nets"), so none depends on the outer GND pours, which stay as a bonus, tied to
        # In1 by stitching vias.  Every pour connects pads through thermal reliefs (pcbgen.py).
        "inner": [("In1.GND", "power"), ("In2.PWR", "power")],
        # JLC's standard 4-layer build (In1 sits 0.21 mm under F.Cu, In2 0.21 mm over B.Cu), ENIG for
        # the ESP32 module's LGA pads and the USB-C receptacles
        "stackup": "JLC04161H-7628", "finish": "ENIG",
        "edge_parts": ["J*", "U3"],
        "defer_pours": False,
        # net: (plane, via Ø, drill, track width)
        "fanout_nets": {"GND": ("In1.Cu", 0.5, 0.3, 0.25), "+3V3": ("In2.Cu", 0.6, 0.3, 0.25),
                        "+5V": ("In2.Cu", 0.6, 0.3, 0.4)},
        # supply pins still left without a via to their In2 area after routing get one (pcbgen.py)
        "plane_nets": {"+5V": "In2.Cu", "+3V3": "In2.Cu"},
        "stitch": 4.0,
        "zones": [
            {"layer": "In1.Cu", "net": "GND"},
            {"layer": "F.Cu", "net": "GND"},
            {"layer": "B.Cu", "net": "GND"},
            # In2 areas with exact outlines that don't overlap (the router takes each outline as copper
            # of its net).  +3V3 under the module, the LDO and the logic around it (mux cluster, INA226);
            # +5V from the buck to the LDO input, the DUT switch, the camera fuse and U8; the 24 V strip
            # between J1 and J2; +3V3 again under the front edge (LED, SERVICE switch)
            {"layer": "In2.Cu", "net": "+3V3", "priority": 1,
             "poly": [(0.4, 0.4), (51.85, 0.4), (51.85, 20.0), (47.85, 20.0), (47.85, 34.0), (22.0, 34.0),
                      (22.0, 24.0), (0.4, 24.0)]},
            {"layer": "In2.Cu", "net": "+5V", "priority": 1,
             "poly": [(52.15, 0.4), (63.6, 0.4), (63.6, PWR_Y - 7.5), (0.4, PWR_Y - 7.5), (0.4, 24.3), (22.3, 24.3),
                      (22.3, 34.3), (48.15, 34.3), (48.15, 20.3), (52.15, 20.3)]},
            {"layer": "In2.Cu", "net": "+3V3", "priority": 1,
             "poly": [(0.4, PWR_Y - 3.1), (57.9, PWR_Y - 3.1), (57.9, PWR_Y + 6.7), (63.6, PWR_Y + 6.7), (63.6, 79.6),
                      (0.4, 79.6)]},
            {"layer": "In2.Cu", "net": "24V_BUS", "priority": 3, "poly": bus},
            # buck hot loop (TI SLUSF64B §8.4): top-side islands joining CIN, U1 and COUT
            {"layer": "F.Cu", "net": "GND", "connection": "solid", "name": "buck-gnd", "priority": 3,
             "poly": [(8.05, 34.5), (10.1, 34.5), (10.1, 36.2), (11.9, 36.2), (11.9, 40.3), (20.6, 40.3), (20.6, 44.4),
                      (8.05, 44.4)]},
            {"layer": "F.Cu", "net": "+5V", "connection": "solid", "name": "buck-5v", "priority": 3,
             "poly": [(12.8, 38.1), (17.3, 38.1), (17.3, 30.6), (21.0, 30.6), (21.0, 39.9), (12.8, 39.9)]},
            {"layer": "F.Cu", "net": "+24V", "connection": "solid", "name": "buck-vin", "priority": 3,
             "poly": [(5.6, 34.5), (7.8, 34.5), (7.8, 42.7), (5.6, 42.7)]},
            # J1/J2 (6-pin SMD, docs/can.md): the whole row's supply and its return pass through pins 1 and
            # 2/5 (up to the hub's 1.6 A eFuse limit), so each of them sits on a solid island with two vias
            # to its plane.  Pins 3/4 (CAN) and 6 (POS) are ordinary signals.
            *[{"layer": "F.Cu", "net": n, "connection": "solid", "name": nm, "priority": 3,
               "poly": [(x0, y - 0.7), (x1, y - 0.7), (x1, y + 0.7), (x0, y + 0.7)]}
              for n, nm, x0, x1, y in (("24V_BUS", "j1-bus", 5.8, 11.0, PWR_Y - 5), ("GND", "j1-gnd2", 5.8, 11.0, PWR_Y - 3),
                                       ("GND", "j1-gnd5", 5.8, 11.6, PWR_Y + 3),
                                       ("24V_BUS", "j2-bus", 54.3, 61.0, PWR_Y + 5), ("GND", "j2-gnd2", 52.7, 58.2, PWR_Y + 3),
                                       ("GND", "j2-gnd5", 52.7, 58.2, PWR_Y - 3))],
            # under the ESP32 module (Espressif's layout guide): its centre pads and GND pins on one
            # top-side island, stitched to In1 around the centre pads
            {"layer": "F.Cu", "net": "GND", "name": "esp-gnd", "priority": 3,
             "poly": [(24.7, 5.6), (39.3, 5.6), (39.3, 16.4), (24.7, 16.4)]},
            # AMS1117 tab: up to ~0.7 W at Wi-Fi peaks (1.7 V × 0.4 A); top-side copper on the tab and
            # C12, vias down to the +3V3 area on In2
            {"layer": "F.Cu", "net": "+3V3", "connection": "solid", "name": "ldo-tab", "priority": 3,
             "poly": [(8.4, 16.0), (17.2, 16.0), (17.2, 22.2), (8.4, 22.2)]},
        ],
        "vias": [("GND", 11.0, 36.9), ("GND", 11.0, 39.4), ("GND", 11.2, 43.4), ("GND", 13.0, 43.6),
                 ("GND", 15.25, 43.6), ("GND", 17.75, 43.6), ("GND", 20.0, 43.6),
                 *[("GND", x, 8.6) for x in (28, 30, 32, 34, 36)],
                 *[("GND", x, y) for x in (28.6, 35.4) for y in (12.2, 14.2)],
                 ("GND", 30.35, 16.0), ("GND", 33.65, 16.0),
                 ("24V_BUS", 14.0, 58.1), ("24V_BUS", 16.0, 58.1),
                 *[(n, x, PWR_Y + dy) for n, dy in (("24V_BUS", -5), ("GND", -3), ("GND", 3)) for x in (10.05, 10.75)],
                 *[(n, x, PWR_Y + dy) for n, dy in (("GND", -3), ("GND", 3)) for x in (53.2, 53.9)],
                 *[("24V_BUS", x, PWR_Y + 5) for x in (59.3, 60.1)],
                 # buck output island down to the +5V area, LDO tab down to the +3V3 area
                 *[("+5V", x, y) for x, y in ((17.9, 31.2), (20.4, 31.2), (20.5, 35.0), (20.5, 37.2))],
                 *[("+3V3", x, y) for x, y in ((9.2, 16.8), (10.6, 16.8), (12.0, 16.8), (13.4, 16.8),
                                               (14.8, 16.8), (15.2, 18.4), (9.0, 19.8), (9.0, 21.5))],
                 ("+3V3", 46.4, 33.0), ("+3V3", 46.4, PWR_Y - 1.5),
                 *hs_vias],
        # the front +3V3 area of In2 (LED, SERVICE switch) is cut off by the 24 V strip: fed from the
        # main +3V3 area by a B.Cu track
        "tracks": [*hs_tracks, ("+3V3", "B.Cu", 0.4, [(46.4, 33.0), (46.4, PWR_Y - 1.5)]),
                   # INA226 Vbus (pin 8, between the sense and GND pins) to C21's DUT_5V end
                   ("DUT_5V", "F.Cu", 0.25, [(49.85, 15.9), (51.0, 15.9), (51.78, 16.68), (51.78, 17.4)])],
        # ESP32 antenna: no copper on any layer under/around the antenna (module top 5 mm + edge)
        "keepouts": [
            {"name": "antenna", "poly": [(9.3, -0.1), (54.7, -0.1), (54.7, 5.4), (9.3, 5.4)]},
        ],
        "texts": [
            {"text": "hw-testing-rack · bay node v0.5", "x": 42, "y": 51, "size": 0.8},
            {"text": "PC", "x": 37.0, "y": 70.2, "size": 0.9},
            {"text": "SVC", "x": 50, "y": 73.6, "size": 0.8},
            {"text": "ROW IN", "x": 5.2, "y": PWR_Y + 9.6, "size": 0.8},
            {"text": "ROW OUT", "x": 58.4, "y": PWR_Y - 10.4, "size": 0.8},
            {"text": "DUT", "x": 60.0, "y": 30.9, "size": 0.8},
            {"text": "AUX", "x": 61.0, "y": 49.6, "size": 0.8},
            {"text": "CAM", "x": 58.0, "y": 6.2, "size": 0.8},
            {"text": "RESET", "x": 7.5, "y": 15.4, "size": 0.8},
            {"text": "BOOT", "x": 15.5, "y": 15.4, "size": 0.8},
        ],
    }

    # ------------------------------------------------------------------ power
    s = b.sheet("Power", "power.kicad_sch", "24 V input, 5 V buck, 3.3 V LDO")
    s.frame("Row cable in / out (JST PH 6, daisy chain: bus, GND, CAN_H, CAN_L, GND, POS) and input protection",
            6, 6, 52, 30)
    # J1 on the left edge (pin 1 towards the rear), J2 on the right edge (pin 1 towards the front): with a 1:1
    # cable J2 of one bay faces J1 of the next (docs/can.md).  CAN_H/CAN_L pass straight through, POS is cut
    # here: J1.6 is this node's token input, J2.6 its output (Rack bus sheet)
    for ref, val, y, rot, x, pos in (("J1", "ROW IN", 14, 270, PH_EDGE, "POS_IN_CONN"),
                                     ("J2", "ROW OUT", 24, 90, W - PH_EDGE, "POS_OUT_CONN")):
        part(s, ref, "ph6", {"1": "24V_BUS", "2": "GND", "3": "CAN_H", "4": "CAN_L", "5": "GND", "6": pos}, val,
             pcb=P(x, PWR_Y, rot), sch=at(10, y, mirror="y", fields="left"))
        for pin, dy in (("2", -1), ("5", 2)):
            s.wire(f"{ref}.{pin}", (13, y + dy))
            s.tag("GND", (13, y + dy), "right")
        for pin, dy, net in (("3", 0, "CAN_H"), ("4", 1, "CAN_L"), ("6", 3, pos)):
            s.wire(f"{ref}.{pin}", (13, y + dy))
            s.tag(net, (13, y + dy), "right")
    s.part("#FLG01", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "24V_BUS"}, in_bom=False, on_board=False, sch=at(21, 12, fields=(-3.8, -2.6)))
    s.part("#FLG02", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "GND"}, in_bom=False, on_board=False, sch=at(30, 24, fields=(0.6, -2.6)))
    s.part("#FLG03", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+24V"}, in_bom=False, on_board=False, sch=at(45, 12, fields=(-3.8, -2.6)))
    s.part("#FLG04", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+5V"}, in_bom=False, on_board=False, sch=at(77, 46, fields=(-3.8, -2.6)))
    part(s, "Q1", "pfet", {"G": "Q1_GATE", "D": "24V_BUS", "S": "+24V"}, pcb=P(15, 56, 90),
         sch=at(24, 13, rot=90, fields=(3.5, -3.8)))
    part(s, "D1", "zener12", {"K": "+24V", "A": "Q1_GATE"}, pcb=P(15, 64.5, 180), sch=at(29, 16.5, rot=270))
    R(s, "R1", "100k", "Q1_GATE", "GND", pcb=P(15, 67.3, 0), sch=at(24, 20.5))
    part(s, "D2", "tvs33", {"K": "+24V", "A": "GND"}, pcb=P(22, 58, 90), sch=at(35, 16.5, rot=270))
    part(s, "C1", "cap100u50", {"1": "+24V", "2": "GND"}, "100u/50V", pcb=P(6, 48.4, 90), sch=at(41, 16.5))
    s.wire("J1.1", (19, 12), "Q1.D")
    s.wire("J2.1", (19, 22), (19, 12))
    s.wire("#FLG02.1", (30, 25))
    s.tag("GND", (30, 25), "down")
    s.wire("Q1.G", "R1.1")
    s.wire((24, 18), "D1.A")
    s.wire((29, 12), "D1.K")
    s.wire((35, 12), "D2.K")
    s.wire((41, 12), "C1.1")
    s.wire("Q1.S", (48, 12))
    s.tag("+24V", (48, 12), "up")

    s.frame("5 V buck: LMR51635, synchronous, 1.1 MHz, 3.5 A (TI SLUSF64B typical application)", 6, 32, 84, 60)
    s.tag("+24V", (12, 38), "up")
    s.wire((12, 38), (35, 38), (35, 45), "U1.VIN")
    C(s, "C2", "10u", "+24V", "GND", size="1206", pcb=P(8, 38.8, 0), sch=at(16, 41.5))
    C(s, "C3", "10u", "+24V", "GND", size="1206", pcb=P(8, 41.4, 0), sch=at(20, 41.5))
    C(s, "C4", "100n", "+24V", "GND", pcb=P(8, 36.6, 0), sch=at(24, 41.5))
    for c_, x in (("C2", 16), ("C3", 20), ("C4", 24)):
        s.wire((x, 38), f"{c_}.1")
    R(s, "R2", "1M", "+24V", "BUCK_EN", pcb=P(4.78, 36.3, 90), sch=at(29, 41.5))
    R(s, "R3", "100k", "BUCK_EN", "GND", pcb=P(4, 34.0, 180), sch=at(29, 48.5))
    s.wire((29, 38), "R2.1")
    s.wire("R2.2", "R3.1")
    s.wire((29, 44), (33, 44), (33, 47), "U1.EN")
    part(s, "U1", "buck", {"VIN": "+24V", "EN": "BUCK_EN", "CB": "BUCK_CB", "SW": "BUCK_SW", "FB": "BUCK_FB",
                           "GND": "GND"}, pcb=P(8, 34, 0), sch=at(40, 46, fields=(-4, -4)))
    C(s, "C5", "100n", "BUCK_CB", "BUCK_SW", pcb=P(9.6, 31.5, 0), sch=at(51.5, 41, rot=90))
    s.wire("U1.CB", (46, 45), (46, 41), "C5.1")
    s.wire("C5.2", (53, 46))
    part(s, "L1", "buck_l", {"1": "BUCK_SW", "2": "+5V"}, "3.3u", pcb=P(15.7, 34, 0), sch=at(57.5, 46, rot=90))
    s.wire("U1.SW", (53, 46), "L1.1")
    s.wire("L1.2", (80, 46))
    s.tag("+5V", (80, 46), "up")
    for i, x in enumerate((62, 66, 70)):
        C(s, f"C{7 + i}", "22u", "+5V", "GND", size="1206", pcb=P(14 + 2.5 * i, 40.5, 270), sch=at(x, 47.5))
    R(s, "R4", "120k", "+5V", "BUCK_FB", pcb=P(4, 30.6, 0), sch=at(74, 48.5))
    R(s, "R5", "22k", "BUCK_FB", "GND", pcb=P(4, 32.2, 180), sch=at(74, 55.5))
    s.wire((74, 46), "R4.1")
    s.wire("R4.2", "R5.1")
    s.wire((74, 53), (46, 53), (46, 47), "U1.FB")

    s.frame("3.3 V logic supply", 88, 32, 116, 50)
    part(s, "U2", "ldo", {"VI": "+5V", "VO": "+3V3", "GND": "GND"}, pcb=P(12, 23, 90), sch=at(102, 42, fields=(-3, -3.5)))
    C(s, "C11", "10u", "+5V", "GND", size="0805", pcb=P(17.4, 26.15, 0), sch=at(95, 43.5))
    C(s, "C12", "22u", "+3V3", "GND", size="1206", pcb=P(18.0, 20.6, 0), sch=at(109, 43.5))
    s.tag("+5V", (92, 42), "up")
    s.wire((92, 42), "U2.VI")
    s.wire("U2.VO", (112, 42))
    s.tag("+3V3", (112, 42), "up")
    s.notes_at = (6, 64, 110)
    s.note("LMR51635YDDCR: 1.1 MHz, PFM at light load with spread spectrum.  Values from TI SLUSF64B table 8-2 (5 V, 1.1 MHz):")
    s.note("  L 3.3 µH (FXL0630, 9.5 A sat);  COUT 3 × 22 µF/25 V (≥ 33 µF left after DC-bias derating);  CIN 2 × 10 µF/50 V + 100 nF;  CB 100 nF.")
    s.note("FB 120k/22k: VOUT = 0.8 V × (1 + 120/22) = 5.16 V, which covers the DUT switch + shunt drop.")
    s.note("EN 1M/100k: the buck starts above 13.5 V and stops below 10.8 V (VEN 1.226 V, 0.241 V hysteresis), so no node")
    s.note("  draws its low-voltage inrush while the hub's eFuse is soft-starting the row.")
    s.note("Layout: C4/C2/C3 straddle U1's VIN and GND pins on the top layer; CIN, U1 and COUT share one top-side GND island")
    s.note("  with vias to the In1 plane; the FB divider sits at the FB pin, its +5V sense comes from COUT on another layer.")
    s.note("Input: SUD50P06 P-FET (reverse polarity, Vgs clamped by the 12 V zener); SMBJ33A clamps hot-plug ringing below 54 V (U1: 63 V abs max).")
    s.note("Row bus 24 V nominal, or 20 / 28 V from a USB-C PD (EPR) supply: SMBJ33A stands off 33 V (28 V + 5 % = 29.4 V), the buck runs")
    s.note("  4.3–60 V and starts above 13.5 V, the P-FET and the zener clamp are rated 60 V / 12 V.  At 20 V a row draws more current: ≤ 1.6 A.")

    # ------------------------------------------------------------------ MCU
    m = b.sheet("MCU", "mcu.kicad_sch", "ESP32-S3 module")
    m.frame("Reset and boot", 6, 6, 40, 30)
    part(m, "SW1", "button", {"1": "EN", "2": "GND"}, "RESET", pcb=P(7.5, 11.5, 0), sch=at(14, 15, rot=270))
    R(m, "R6", "10k", "+3V3", "EN", pcb=P(41.6, 8.7, 180), sch=at(22, 10.5))
    C(m, "C15", "1u", "EN", "GND", pcb=P(41.6, 7.1, 0), sch=at(27, 14.5))
    m.wire("SW1.1", (32, 13))
    m.wire("R6.2", (22, 13))
    m.tag("EN", (32, 13), "right")
    part(m, "SW2", "button", {"1": "BOOT", "2": "GND"}, "BOOT", pcb=P(15.5, 11.5, 0), sch=at(14, 24, rot=270))
    R(m, "R7", "10k", "+3V3", "BOOT", pcb=P(22.9, 12.2, 90), sch=at(22, 19.5))
    m.wire("SW2.1", (32, 22))
    m.wire("R7.2", (22, 22))
    m.tag("BOOT", (32, 22), "right")

    m.frame("UART test pads", 6, 31, 40, 45)
    # a 2 × 2 block on the bottom side, under the TXD0/RXD0 pins' corner of the module
    tp_xy = ((44.0, 9.4), (41.4, 9.4), (41.4, 12.0), (44.0, 12.0))
    for i, (net, y) in enumerate((("U0TX", 35), ("U0RX", 37), ("GND", 39), ("+3V3", 42))):
        part(m, f"TP{i + 1}", "testpad", {"1": net}, net, pcb=P(*tp_xy[i], 0, "bottom"), in_bom=False,
             sch=at(12, y, rot=90, fields="left"))
    m.wire("TP3.1", (15, 39), (15, 40))
    m.tag("GND", (15, 40), "down")
    m.wire("TP4.1", (18, 42), (18, 41))
    m.tag("+3V3", (18, 41), "up")

    m.frame("ESP32-S3-MINI-1 (PCB antenna at the board's rear edge: no copper under it, any layer)", 46, 6, 112, 56)
    part(m, "U3", "esp32s3", {
        "3V3": "+3V3", "GND": "GND", "EN": "EN", "IO0": "BOOT",
        "USB_D-": "ESP_DN", "USB_D+": "ESP_DP",
        # each signal on the module edge that faces where it goes (docs/electronics.md, GPIO map):
        # right column → DUT power block (top right), bottom right → AUX, bottom left → mode logic, LED
        "IO41": "DUT_EN", "IO40": "DUT_FLT_N", "IO39": "INA_ALERT_N", "IO38": "I2C_SDA", "IO37": "I2C_SCL",
        "IO48": "AUX_BOOT_CTL", "IO34": "AUX_RST_CTL", "IO33": "AUX_RX", "IO47": "AUX_TX",
        "IO12": "LED_DIN", "IO13": "PC_DET", "IO14": "MUX_FORCE_PC", "IO15": "SVC",
        # bottom row, left of the USB pins → the rack bus block under the module (POS_OUT from the right
        # column, towards J2)
        "IO16": "POS_IN", "IO17": "CAN_RXD", "IO18": "CAN_TXD", "IO35": "POS_OUT",
        "TXD0": "U0TX", "RXD0": "U0RX",
    }, pcb=P(32, 10.5, 0), sch=at(80, 38, fields=(-14, -14)))
    C(m, "C13", "22u", "+3V3", "GND", size="1206", pcb=P(21, 9, 90), sch=at(96, 23.5))
    C(m, "C14", "100n", "+3V3", "GND", pcb=P(21, 13.5, 90), sch=at(100, 23.5))
    m.wire("U3.3V3", (80, 22), "C14.1")
    m.wire("U3.IO12", (66, 43))
    m.tag("LED_DIN", (66, 43), "left")
    m.tag("+3V3", (80, 22), "up")

    m.frame("Status LED (behind the fascia window)", 6, 48, 40, 66)
    part(m, "D4", "rgb", {"VDD": "+3V3", "VSS": "GND", "DIN": "LED_DIN_R", "DOUT": None}, pcb=P(12, 78.2, 0),
         sch=at(31, 57, fields=(4, 1)))
    R(m, "R8", "33", "LED_DIN", "LED_DIN_R", pcb=P(16, 74.5, 0), sch=at(19.5, 57, rot=90))
    C(m, "C16", "100n", "+3V3", "GND", pcb=P(16, 77.8, 90), sch=at(37, 53.5))
    m.wire("R8.2", "D4.DIN")
    m.wire("D4.VDD", (31, 52), "C16.1")
    m.tag("+3V3", (31, 52), "up")
    m.notes_at = (6, 70, 106)
    m.note("GPIO map: IO41 DUT_EN · IO40 DUT_FLT_N · IO39 INA_ALERT · IO38/37 I2C SDA/SCL · IO47/33 UART1 TX/RX (AUX) ·")
    m.note("IO34 AUX_RST · IO48 AUX_BOOT · IO12 LED · IO13 PC_DET · IO14 MUX_FORCE_PC · IO15 SVC · IO19/20 USB (OTG/JTAG) ·")
    m.note("IO18/17 CAN TX/RX (TWAI) · IO16 POS_IN · IO35 POS_OUT.")
    m.note("Strapping pins IO0/IO3/IO45/IO46 are not used for I/O.  USB is full-speed only (one internal PHY).")

    # ------------------------------------------------------------------ USB
    u = b.sheet("USB", "usb.kicad_sch", "USB ports and data-path muxes")
    u.frame("Front PC port: USB-C sink (Rd 5.1k on CC), VBUS only sensed", 6, 6, 56, 52)
    part(u, "J3", "usbc", {"VBUS": "PC_VBUS", "GND": "GND", "CC1": "PC_CC1", "CC2": "PC_CC2", "D+": "PC_CONN_DP",
                           "D-": "PC_CONN_DN", "SBU1": None, "SBU2": None, "SHIELD": "GND"}, "PC", pcb=P(32, 76.6, 0),
         sch=at(14, 28, fields=(-4, -9)))
    u.wire("J3.A7", (22, 27), (22, 28), "J3.B7")
    u.wire("J3.A6", (23, 29), (23, 30), "J3.B6")
    # USBLC6 flow-through: the connector side (pins 6/4) and the protected side (1/3) are separate nets,
    # so the only path from J3 to the mux runs through the part (drawn mirrored: connector side left)
    part(u, "U4", "esd", {"6": "PC_CONN_DN", "1": "PC_DN", "4": "PC_CONN_DP", "3": "PC_DP", "5": "+5V", "2": "GND"},
         pcb=P(32.0, 67.0, 270), sch=at(33, 28, mirror="y", fields=(1.5, 3.5)))
    u.wire((22, 28), "U4.6")
    u.wire((23, 29), "U4.4")
    R(u, "R11", "10k", "PC_VBUS", "PC_DET", pcb=P(27.0, 69.0, 90), sch=at(37.5, 22, rot=90))
    R(u, "R12", "20k", "PC_DET", "GND", pcb=P(27.0, 66.0, 90), sch=at(42, 23.5))
    u.wire("J3.VBUS", "R11.1")
    u.wire("R11.2", (46, 22))
    u.tag("PC_DET", (46, 22), "right")
    R(u, "R9", "5.1k", "PC_CC1", "GND", pcb=P(24.5, 74.5, 90), sch=at(24.5, 44, rot=90))
    R(u, "R10", "5.1k", "PC_CC2", "GND", pcb=P(39.5, 74.5, 90), sch=at(24.5, 47, rot=90))
    u.wire("R9.2", (28, 44), (28, 48))
    u.wire("R10.2", (28, 47))
    u.tag("GND", (28, 48), "down")

    u.frame("USB 2.0 data muxes (FSUSB42): MUX_PC → DUT path or ESP32, MUX_DUT → ESP32 or PC path", 58, 6, 124, 36)
    part(u, "U5", "mux", {"VCC": "+3V3", "GND": "GND", "D+": "PC_DP", "D-": "PC_DN", "HSD1+": "PCPATH_DP",
                          "HSD1-": "PCPATH_DN", "HSD2+": "ESP_DP", "HSD2-": "ESP_DN", "SEL": "SVC", "~{OE}": "GND"},
         "MUX_PC", pcb=P(34.6, 27.5, 0), sch=at(76, 26, fields=(1.5, 4.5)))
    C(u, "C17", "100n", "+3V3", "GND", pcb=P(31.2, 24.2, 180), sch=at(68, 17.5))
    u.wire("U5.VCC", (76, 16), "C17.1")
    u.tag("+3V3", (76, 16), "up")
    part(u, "U6", "mux", {"VCC": "+3V3", "GND": "GND", "D+": "DUT_DP", "D-": "DUT_DN", "HSD1+": "ESP_DP",
                          "HSD1-": "ESP_DN", "HSD2+": "PCPATH_DP", "HSD2-": "PCPATH_DN", "SEL": "MUX_SEL",
                          "~{OE}": "SVC"}, "MUX_DUT", pcb=P(44.5, 24.5, 180), sch=at(104, 26, mirror="y", fields=(1.5, 4.5)))
    C(u, "C18", "100n", "+3V3", "GND", pcb=P(47.6, 28.0, 270), sch=at(112, 17.5))
    u.wire("U6.VCC", (104, 16), "C18.1")
    u.wire("U6.SEL", (115, 28))
    u.tag("MUX_SEL", (115, 28), "right")
    u.tag("+3V3", (104, 16), "up")

    u.frame("DUT port: USB-C source (Rp 22k → 1.5 A); DUT_5V comes switched from the DUT power sheet", 106, 40, 160, 72)
    part(u, "J4", "usbc", {"VBUS": "DUT_5V", "GND": "GND", "CC1": "DUT_CC1", "CC2": "DUT_CC2", "D+": "DUT_CONN_DP",
                           "D-": "DUT_CONN_DN", "SBU1": None, "SBU2": None, "SHIELD": "GND"}, "DUT",
         pcb=P(60.4, CFG["right"]["dut"], 90), sch=at(150, 58, mirror="y", fields=(1, -9)))
    u.wire("J4.A7", (142, 57), (142, 58), "J4.B7")
    u.wire("J4.A6", (141, 59), (141, 60), "J4.B6")
    part(u, "U8", "esd", {"6": "DUT_CONN_DN", "1": "DUT_DN", "4": "DUT_CONN_DP", "3": "DUT_DP", "5": "+5V",
                          "2": "GND"}, pcb=P(51.3, 24.0, 0), sch=at(134, 58, fields=(1.5, 3.5)))
    u.wire("U8.6", (142, 58))
    u.wire("U8.4", (141, 59))
    R(u, "R14", "22k", "DUT_5V", "DUT_CC1", pcb=P(54.3, 28.4, 90), sch=at(117.5, 50, rot=90))
    R(u, "R15", "22k", "DUT_5V", "DUT_CC2", pcb=P(54.2, 21.5, 270), sch=at(117.5, 53, rot=90))
    u.wire((112, 50), "R14.1")
    u.wire((114, 50), (114, 53), "R15.1")
    u.tag("DUT_5V", (112, 50), "left")

    u.frame("Mode logic: MUX_SEL = PC_DET OR MUX_FORCE_PC; SERVICE switch", 6, 58, 84, 86)
    part(u, "U7", "or", {"1": "PC_DET", "2": "MUX_FORCE_PC", "3": "GND", "4": "MUX_SEL", "5": "+3V3"},
         pcb=P(27.5, 31.5, 0), sch=at(40, 74, fields=(-6, -5)))
    C(u, "C19", "100n", "+3V3", "GND", pcb=P(27.5, 28.6, 180), sch=at(46, 67.5))
    u.wire("U7.5", (40, 66), "C19.1")
    u.tag("+3V3", (40, 66), "up")
    R(u, "R13", "100k", "MUX_FORCE_PC", "GND", pcb=P(27.5, 34.6, 0), sch=at(28, 77.5))
    u.wire("U7.2", (24, 75))
    u.wire("R13.1", (28, 75))
    u.tag("MUX_FORCE_PC", (24, 75), "left")
    u.wire("U7.4", (52, 74))
    u.tag("MUX_SEL", (52, 74), "right")
    part(u, "SW3", "slide", {"1": "+3V3", "2": "SVC", "3": "GND"}, "SERVICE", pcb=P(50, 77.3, 0),
         sch=at(70, 74, mirror="y", fields=(-2, 3)))
    u.wire("SW3.1", (66, 73), (66, 71))
    u.tag("+3V3", (66, 71), "up")
    u.wire("SW3.3", (66, 75), (66, 77))
    u.tag("GND", (66, 77), "down")
    u.notes_at = (6, 90, 100)
    u.note("SVC=1 routes the PC port to the ESP32 (flash / console / JTAG) and disables MUX_DUT (~OE high).")
    u.note("MUX_SEL = PC_DET OR MUX_FORCE_PC: a laptop on the front port takes the DUT over automatically.")

    # ------------------------------------------------------------------ DUT power + AUX
    d = b.sheet("DUT power & AUX", "dut.kicad_sch", "DUT power switch, monitor, AUX and camera power")
    d.frame("DUT power path: +5V → TPS2553 switch → 50 mΩ shunt → DUT_5V (DUT port VBUS), INA226 across the shunt",
            6, 12, 124, 46)
    d.tag("+5V", (18, 29), "up")
    d.wire((18, 29), "U9.IN")
    C(d, "C20", "100n", "+5V", "GND", pcb=P(53.15, 7.35, 90), sch=at(22, 30.5))
    part(d, "U9", "vbus_sw", {"IN": "+5V", "GND": "GND", "EN": "DUT_EN", "~{FAULT}": "DUT_FLT_N", "ILIM": "DUT_ILIM",
                              "OUT": "DUT_5V_SW"}, pcb=P(50.6, 8.45, 270), sch=at(40, 30, fields=(-4, -4)))
    R(d, "R16", "18k", "DUT_ILIM", "GND", pcb=P(50.6, 12.1, 270), sch=at(31, 33.5))
    d.wire("U9.ILIM", "R16.1")
    R(d, "R17", "100k", "+3V3", "DUT_EN", pcb=P(47.3, 12.1, 90), sch=at(26, 35.5))
    d.wire("U9.EN", (28, 31), (28, 38), (16, 38))
    d.wire("R17.2", (26, 38))
    d.tag("DUT_EN", (16, 38), "left")
    R(d, "R18", "10k", "+3V3", "DUT_FLT_N", pcb=P(48.9, 12.1, 90), sch=at(52, 35.5))
    d.wire("U9.~{FAULT}", (48, 31), (48, 38), (55, 38))
    d.wire("R18.2", (52, 38))
    d.tag("DUT_FLT_N", (55, 38), "right")
    # Kelvin shunt: pins 1/4 carry the DUT current, pins 2/3 are sense pads on the inner edge of each
    # terminal (bench:R_1206_3216Metric_Kelvin), so the INA226 reads the resistor, not the load copper
    part(d, "R19", "shunt50m", {"1": "DUT_5V_SW", "4": "DUT_5V", "2": "SHUNT_P", "3": "SHUNT_N"}, "50m",
         pcb=P(52.75, 13.0, 270), sch=at(62, 33.5))
    d.wire("U9.OUT", (62, 29), "R19.1")
    d.wire("R19.4", (62, 40), (100, 40))
    d.tag("DUT_5V", (100, 40), "right")
    C(d, "C21", "22u", "DUT_5V", "GND", size="1206", pcb=P(53.25, 17.4, 0), sch=at(96, 41.5))
    part(d, "U10", "ina226", {"VS": "+3V3", "GND": "GND", "A0": "GND", "A1": "GND", "SDA": "I2C_SDA",
                              "SCL": "I2C_SCL", "~{Alert}": "INA_ALERT_N", "Vin+": "SHUNT_P", "Vin-": "SHUNT_N",
                              "Vbus": "DUT_5V"}, pcb=P(47.7, 15.9, 0), sch=at(74, 31, fields=(-10, -7)))
    d.wire("R19.2", (66, 32.5), (66, 32), "U10.Vin+")
    d.wire("R19.3", (67, 34.5), (67, 33), "U10.Vin-")
    d.wire("U10.A1", (80, 28), (80, 29), "U10.A0")
    d.tag("GND", (80, 29), "right")
    C(d, "C22", "100n", "+3V3", "GND", pcb=P(48.0, 18.6, 180), sch=at(84, 25.5))
    d.wire("U10.VS", (74, 24), "C22.1")
    d.tag("+3V3", (74, 24), "up")
    d.text("I2C pull-ups", 103, 16.2, 1.27, True)
    d.tag("+3V3", (100, 18), "up")
    d.wire((100, 18), (116, 18), net="+3V3")
    for ref, val, x, net, xy in (("R21", "4.7k", 100, "I2C_SDA", (42.8, 19.3)), ("R22", "4.7k", 108, "I2C_SCL", (44.4, 19.3)),
                                 ("R20", "10k", 116, "INA_ALERT_N", (41.2, 19.3))):
        R(d, ref, val, "+3V3", net, pcb=P(*xy, 90), sch=at(x, 20.5))
        d.wire((x, 18), f"{ref}.1")
        d.wire(f"{ref}.2", (x, 23), (x + 1, 23))
        d.tag(net, (x + 1, 23), "right")

    d.frame("AUX: UART + open-drain RESET / BOOT towards the DUT (JST PH 6)", 68, 48, 112, 86)
    # JST PH like every other connector here (SH is 1 mm pitch: fiddly to crimp and to plug blind);
    # side entry on the right edge, pins 1 → 6 from y aux + 5 down to aux − 5
    part(d, "J5", "ph6", {"1": "GND", "2": "AUX_VREF", "3": "AUX_TX_R", "4": "AUX_RX_R", "5": "AUX_RST_N",
                          "6": "AUX_BOOT_N"}, "AUX", pcb=P(W - PH_EDGE, CFG["right"]["aux"], 90),
         sch=at(106, 64, fields=(1, -5)))
    R(d, "R23", "10", "+3V3", "AUX_VREF", pcb=P(44.0, 31.8, 0), sch=at(90.5, 54, rot=90))
    R(d, "R24", "1k", "AUX_TX", "AUX_TX_R", pcb=P(52.45, 42.6, 0), sch=at(90.5, 58, rot=90))
    R(d, "R25", "1k", "AUX_RX", "AUX_RX_R", pcb=P(52.45, 40.8, 0), sch=at(90.5, 62, rot=90))
    d.wire("J5.2", (98, 63), (98, 54), "R23.2")
    d.wire("R23.1", (87, 54), (87, 52))
    d.tag("+3V3", (87, 52), "up")
    d.wire("J5.3", (97, 64), (97, 58), "R24.2")
    d.wire("J5.4", (96, 65), (96, 62), "R25.2")
    part(d, "Q2", "nfet", {"G": "AUX_RST_CTL", "S": "GND", "D": "AUX_RST_N"}, pcb=P(52.0, 38.0, 0), sch=at(86, 69))
    part(d, "Q3", "nfet", {"G": "AUX_BOOT_CTL", "S": "GND", "D": "AUX_BOOT_N"}, pcb=P(52.0, 34.4, 0), sch=at(86, 79))
    R(d, "R26", "100k", "AUX_RST_CTL", "GND", pcb=P(48.9, 39.6, 270), sch=at(81, 70.5))
    R(d, "R27", "100k", "AUX_BOOT_CTL", "GND", pcb=P(48.9, 35.2, 270), sch=at(81, 80.5))
    d.wire("J5.5", (87, 66), "Q2.D")
    d.wire("Q2.G", (78, 69))
    d.tag("AUX_RST_CTL", (78, 69), "left")
    d.wire("J5.6", (95, 67), (95, 76), (87, 76), "Q3.D")
    d.wire("Q3.G", (78, 79))
    d.tag("AUX_BOOT_CTL", (78, 79), "left")
    for net, xy in (("AUX_VREF", (93, 54)), ("AUX_TX_R", (93, 58)), ("AUX_RX_R", (93, 62)), ("AUX_RST_N", (89, 66)),
                    ("AUX_BOOT_N", (88, 76))):
        d.tag(net, xy, "right")

    d.frame("Camera pod 5 V (always on, PTC protected, JST PH)", 116, 48, 160, 62)
    part(d, "F1", "pptc500", {"1": "+5V", "2": "CAM_5V"}, "0.5A", pcb=P(60.0, 17.42, 180), sch=at(126, 54, rot=90))
    part(d, "J6", "ph2", {"1": "CAM_5V", "2": "GND"}, "CAM", pcb=P(CFG["cam"][0] - PH_EDGE, CFG["cam"][1] + 0.65, 90),
         sch=at(138, 54))
    d.tag("+5V", (120, 54), "up")
    d.wire((120, 54), "F1.1")
    d.wire("F1.2", "J6.1")
    d.wire("J6.2", (134, 55), (134, 57))
    d.tag("GND", (134, 57), "down")

    d.frame("Mounting (M3, matches the carrier standoffs)", 116, 66, 160, 80)
    for i, (x, y) in enumerate(CFG["holes"]):
        part(d, f"H{i + 1}", "hole", {}, "M3", pcb=P(x, y, 0), in_bom=False, sch=at(122 + 9 * i, 73))
    d.notes_at = (6, 52, 60)
    d.note("TPS2553: ILIM 18k → 1.34–1.52 A.  EN is pulled up: DUT_5V is on")
    d.note("  even with no firmware; ~FAULT flags current limit / over-temperature.")
    d.note("INA226 (I2C 0x40) runs from +3V3: it measures the drop across")
    d.note("  R19 (50 mΩ → 1.64 A full scale, Kelvin sense pads) and DUT_5V on Vbus.")
    d.note("AUX: TX/RX through 1k, VREF = +3V3 through 10 Ω (level hint),")
    d.note("  RESET/BOOT open-drain (2N7002, 100k gate pull-downs).")

    # ------------------------------------------------------------------ rack bus: CAN + POS (docs/can.md)
    k = b.sheet("Rack bus", "bus.kicad_sch", "Rack bus: CAN transceiver and POS addressing token")
    k.frame("CAN: TCAN1044AV on the row pair (J1.3/4 ↔ J2.3/4, Power sheet); stub ≤ 20 mm, no termination", 6, 6, 70, 32)
    # straddles the In2 24 V strip: VCC (+5V) and the TXD/RXD pins on the rear side, VIO (+3V3), CANH/CANL and
    # STB on the front side, right above the pair
    part(k, "U11", "can_xcvr", {"TXD": "CAN_TXD", "VSS": "GND", "VDD": "+5V", "RXD": "CAN_RXD", "Vio": "+3V3",
                                "CANL": "CAN_L", "CANH": "CAN_H", "STBY": "GND"}, "TCAN1044AV",
         pcb=P(27.5, PWR_Y - 5.0, 270), sch=at(36, 18, fields=(-4, -5.5)))
    k.wire("U11.TXD", (24, 16))
    k.tag("CAN_TXD", (24, 16), "left")
    k.wire("U11.RXD", (24, 17))
    k.tag("CAN_RXD", (24, 17), "left")
    C(k, "C24", "100n", "+3V3", "GND", pcb=P(24.7, PWR_Y + 0.9, 0), sch=at(27, 23.5))
    k.wire("U11.Vio", (27, 19), "C24.1")
    k.tag("+3V3", (27, 19), "left")
    k.wire("U11.STBY", (30, 20))
    k.tag("GND", (30, 20), "down")
    C(k, "C23", "100n", "+5V", "GND", pcb=P(24.0, PWR_Y - 10.4, 0), sch=at(46, 11.5))
    k.wire("U11.VDD", (36, 10), "C23.1")
    k.tag("+5V", (36, 10), "up")
    k.wire("U11.CANH", (52, 17))
    k.tag("CAN_H", (52, 17), "right")
    k.wire("U11.CANL", (52, 19))
    k.tag("CAN_L", (52, 19), "right")
    part(k, "D5", "can_esd", {"1": "CAN_H", "2": "CAN_L", "3": "GND"}, "PESD2CAN", pcb=P(21.0, PWR_Y + 1.5, 0),
         sch=at(62, 22))
    k.text("STB low: always in normal mode (TXD dominant time-out guards the bus).", 8, 29, 1.27)

    k.frame("POS token: in from J1.6, out to J2.6; 10k series + BAT54S clamp on each (+24 V on pin 6 costs ≈ 2 mA)",
            6, 36, 70, 66)
    R(k, "R28", "10k", "POS_IN_CONN", "POS_IN", pcb=P(11.7, PWR_Y + 5.6, 0), sch=at(20, 42, rot=90))
    k.wire((14, 42), "R28.1")
    k.tag("POS_IN_CONN", (14, 42), "left")
    k.wire("R28.2", (40, 42))
    k.tag("POS_IN", (40, 42), "right")
    part(k, "D6", "bat54s", {"A": "GND", "K": "+3V3", "COM": "POS_IN"}, pcb=P(15.4, PWR_Y + 7.4, 0),
         sch=at(28, 46, rot=180))
    k.wire("D6.COM", (28, 42))
    R(k, "R29", "100k", "POS_IN", "GND", pcb=P(19.0, PWR_Y + 7.4, 90), sch=at(35, 44.5))
    k.wire("R29.1", (35, 42))
    R(k, "R30", "10k", "POS_OUT", "POS_OUT_CONN", pcb=P(51.8, PWR_Y - 5.0, 0), sch=at(30, 56, rot=90))
    k.wire((14, 56), "R30.1")
    k.tag("POS_OUT", (14, 56), "left")
    k.wire("R30.2", (40, 56))
    k.tag("POS_OUT_CONN", (40, 56), "right")
    # the output clamp sits by the module (In2 +3V3 there); electrically anywhere on POS_OUT
    part(k, "D7", "bat54s", {"A": "GND", "K": "+3V3", "COM": "POS_OUT"}, pcb=P(42.5, 13.0, 0),
         sch=at(22, 60, rot=180))
    k.wire("D7.COM", (22, 56))
    k.notes_at = (6, 70, 64)
    k.note("CAN (docs/can.md): one bus for the rack, a star from the hub; both terminations sit in the hub.")
    k.note("  250 kbit/s (125 kbit/s fallback).  TCAN1044AV: VCC 5 V, VIO 3.3 V, bus pins ±58 V, passive unpowered.")
    k.note("POS: active-high 3.3 V token.  From reset the node holds POS_OUT low; when POS_IN goes high and it has")
    k.note("  no address yet, it answers with its MAC, takes (row, position) from the hub, then raises POS_OUT.")
    k.note("  R29 keeps POS_IN low with no cable; the next node's 100k keeps POS_OUT low before firmware.")
    return b


NETCLASSES = [
    {"name": "Power", "clearance": 0.15, "track_width": 0.6, "via_diameter": 0.8, "via_drill": 0.4,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 1,
     "_patterns": ["*24V_BUS", "+24V", "+5V", "*DUT_5V_SW", "*DUT_5V", "*BUCK_SW", "*CAM_5V"]},
    {"name": "USB", "clearance": 0.15, "track_width": 0.2, "via_diameter": 0.6, "via_drill": 0.3,
     "diff_pair_width": 0.25, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 2,
     "_patterns": ["*_DP", "*_DN"]},
]
