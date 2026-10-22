"""Bay node — one per bay: ESP32-S3 USB/IP host for the board under test (DUT).

Functions
  * Row cable in/out (JST PH 6, daisy-chained bay to bay, docs/can.md): the row bus VRACK (20 V, or
    28 V EPR, from the hub's USB-C PD supply), the rack's CAN pair and the POS addressing token.
    Reverse-polarity P-FET, TVS, LMR51635 synchronous buck to 5 V / 3.5 A, 3.3 V LDO for the logic.
  * CAN: TJA1462AT on the ESP32-S3 TWAI, tapping the pair that runs J1 → J2 (no termination).
  * POS: token in on J1.6, out on J2.1 (J2 is J1 mirrored), each through 10k + a BAT54S clamp (survives VRACK on it).
  * DUT power: DUT_5V through a TPS2553 current-limited switch (≈1.4 A) and a 50 mΩ shunt read by an
    INA226; the DUT's D+/D- through ESD.
  * DATA (JST PH 8, side entry, right edge): the DUT's USB and power, the node's I²C and an INT line on
    an 8-wire lead to the drawer's DATA port board (electronics/data-port: USB-C, Rp, ESD; it leaves the
    I²C and INT pins open) or a DATA ×4 board.  The node has no DUT receptacle of its own.
  * Two USB 2.0 muxes:
      MUX_DUT: DUT ↔ ESP32-S3 USB-OTG (USB/IP mode, default)
               DUT ↔ front PC port      (classic mode: plug a laptop and the
                                          DUT is yours, even with no firmware)
      MUX_PC : front PC port ↔ DUT path, or ↔ ESP32-S3 USB-Serial-JTAG when the
               SERVICE switch is on (flash/debug the node itself).
    SERVICE also disables MUX_DUT so the ESP32's single USB PHY is never
    connected to two hosts at once.
  * AUX (JST PH 6, vertical): UART TX/RX + open-drain RESET/BOOT lines to the DUT.
  * CAM (JST PH 8, vertical): this bay's Arducam Mega SPI camera and its white LEDs, on a lead to the pod
    under the ceiling: CAM_5V through a 0.5 A PTC, SPI2 (33 Ω series, USBLC6 ESD), the LEDs' low side
    (AO3400A).  The module is the ESP32-S3-WROOM-1-N8R8 (8 MB octal PSRAM) for the camera's frames,
    the bench stand-in's own module, with the DevKitC-1's pin map; the board grew 10 mm at the rear for it.
  * WS2812B status LED behind the fascia, RESET/BOOT buttons, UART test pads.

Net names follow the power path: VRACK (daisy chain) → Q1 → VIN → buck →
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
PWR_Y = CFG["pwr_y"]          # centre of the row cable connectors J1/J2 (left/right edges)
# JST PH side entry, SMD (S*B-PH-SM4-TB): footprint origin 4.9 mm in from the board edge, which puts the
# mouth 0.5 mm inside it so the fitting tabs keep their copper-to-edge clearance; pins 7.75 mm in
PH_EDGE = 4.9
EDGE_X = W - PH_EDGE         # the side-entry PH headers on the right edge (J2, J5, J7): their centre x
DX = W - 64                  # the board grew 10 mm on the right (2026-10-19): what sits on that edge moved by DX
# Draw the USB pairs of the classic-mode path by hand (usb_hs_routes) for High-Speed, or leave them
# to Freerouting (full speed only is designed for; the ESD/mux GND and VBUS escapes stay drawn)
USB_HS_PAIRS = True


def P(x, y, rot=0, side="top", **kw):
    return {"x": x, "y": y, "rot": rot, "side": side, **kw}


def at(x, y, rot=0, mirror="", fields=None):
    """Schematic position in 0.1" grid units."""
    d = {"x": x, "y": y, "rot": rot}
    if mirror:
        d["mirror"] = mirror
    if fields is not None:
        d["fields"] = fields
    return d


def usb_hs_routes():
    """The classic-mode USB path (laptop on J3 ↔ DUT on J7 through U4, U5, U6, U8) carries High-Speed
    (480 Mb/s) whenever the DUT supports it, so it is drawn here instead of by Freerouting: coupled
    pairs on F.Cu over the solid In1 plane, 0.25 mm tracks with a 0.15 mm gap (≈ 90 Ω differential on
    JLC04161H-7628, field-solver estimate in docs/electronics.md), ESD parts in flow-through, lengths
    matched (vias counted as the 1.6 mm they cross).

    J3 → U4 → straight north up the middle → U5 (MUX_PC) → east → U6 (MUX_DUT) → U8 → J7.  The two
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
    t("PC_CONN_DP", (31.75, 82.92), (31.75, 80.9), (31.05, 80.2), (31.05, 78.1375))        # → U4 pin 4
    t("PC_CONN_DN", (32.25, 82.92), (32.25, 80.9), (32.95, 80.2), (32.95, 78.1375))        # → U4 pin 6
    t("PC_CONN_DP", (32.75, 82.92), (32.75, 83.85), (31.75, 83.85), (31.75, 82.92))  # B6 → A6
    t("PC_CONN_DN", (31.25, 82.92), (31.2, 81.35))                                     # B7 → A7
    t("PC_CONN_DN", (31.2, 81.35), (32.3, 81.25), layer="B.Cu")
    via("PC_CONN_DN", 31.2, 81.35)
    via("PC_CONN_DN", 32.3, 81.25)
    # U4's VBUS pin: its via sits in the front +3V3 area of In2, so a B.Cu track takes it past the VRACK
    # strip to the +5V area; its GND pin gets a via between the spread pins
    t("+5V", (32.0, 78.1375), (32.0, 79.55), w=0.3)
    via("+5V", 32.0, 79.55)
    t("+5V", (32.0, 79.55), (33.6, 79.55), (33.6, 64.8), layer="B.Cu", w=0.3)
    via("+5V", 33.6, 64.8)
    t("GND", (32.0, 75.8625), (32.0, 74.55), w=0.3)
    via("GND", 32.0, 74.55)
    # C25 (100 nF on U4's VBUS, the ESD clamp rail): a via on the B.Cu +5V run, right of U4's pads
    via("+5V", 33.6, 76.9)
    t("+5V", (33.6, 76.9), (34.625, 76.9), w=0.3)

    # U4 pins 3/1 → north at x 31.05 / 31.45 → U5 (MUX_PC, rot 0) D+/D− (pins 3/4 at y 37.5/38.0, x 32.5)
    bumps = []
    for y in (55.0, 53.5, 52.0, 50.5):
        bumps += [(31.05, y), (30.25, y - 0.2), (30.25, y - 0.7), (31.05, y - 0.9)]
    t("PC_DP", (31.05, 75.8625), *bumps, (31.05, 37.95), (31.5, 37.5), (32.5, 37.5))
    t("PC_DN", (32.95, 75.8625), (32.95, 74.5), (31.45, 73.0), (31.45, 38.2), (31.65, 38.0), (32.5, 38.0))

    # U5 HSD1 (pins 7/6 at y 38.0/38.5, x 36.7) → U6 HSD2 (rot 180: pins 9/8 at y 35.0/34.5, x 42.4).
    # PCPATH_DN crosses under PCPATH_DP on B.Cu between the two vias.
    t("PCPATH_DP", (36.7, 38.0), (38.9, 38.0), (40.9, 36.0), (40.9, 35.4), (41.3, 35.0), (42.4, 35.0))
    t("PCPATH_DN", (36.7, 38.5), (38.2, 38.5), (38.6, 38.9))
    t("PCPATH_DN", (38.6, 38.9), (40.2, 37.3), (40.2, 34.9), layer="B.Cu")
    t("PCPATH_DN", (40.2, 34.9), (40.6, 34.5), (42.4, 34.5))
    via("PCPATH_DN", 38.6, 38.9)
    via("PCPATH_DN", 40.2, 34.9)
    # U5's ~OE (GND): out of the top of its pad, to a via above the package
    t("GND", (36.7, 36.5), (36.7, 35.35), w=0.25)
    via("GND", 36.7, 35.35)

    # U6 D−/D+ (pins 4/3 at y 34.0/34.5, x 46.6) → U8 (ESD, rot 0: DN through pins 1/6 at y 33.05,
    # DP through 3/4 at y 34.95) → J7 (DATA, PH 8 side entry on the right edge, rot 90: D− pin 4 at y c + 1,
    # D+ pin 3 at c + 3, pads x 64.5–68).  D− lies north on both: a straight pair, one 45° step each past
    # U8's VBUS via (lengths within 0.05 mm)
    t("DUT_DN", (46.6, 34.0), (47.7, 34.0), (48.65, 33.05), (50.16, 33.05))
    t("DUT_DP", (46.6, 34.5), (48.0, 34.5), (48.45, 34.95), (50.16, 34.95))
    c = CFG["right"]["data"]
    jx = EDGE_X - 3.9                                   # into J7's pads (x 64.5–68)
    x1 = 56.0
    t("DUT_CONN_DN", (52.44, 33.05), (x1, 33.05), (x1 + 33.05 - (c + 1), c + 1), (jx, c + 1))
    t("DUT_CONN_DP", (52.44, 34.95), (x1, 34.95), (x1 + 34.95 - (c + 3), c + 3), (jx, c + 3))
    t("GND", (46.6, 33.5), (47.35, 33.5), (47.85, 33.0))                                # U6 pin 5
    via("GND", 47.85, 33.0)
    t("GND", (50.16, 34.0), (49.0, 34.0))                                               # U8 GND
    via("GND", 49.0, 34.0)
    t("+5V", (52.44, 34.0), (53.6, 34.0))                                               # U8 VBUS
    via("+5V", 53.6, 34.0)
    return tracks, vias


def board() -> Board:
    b = Board("bay-node", "Bay node", "0.5",
              comments=["ESP32-S3 USB/IP host for one bay of the hw-testing-rack shelf",
                        "Generated from electronics/bay-node/design.py — edit the Python, then regenerate",
                        "Row bus 20–28 V + CAN + POS in/out · 5 V/1.4 A switched DUT port · USB 2.0 muxes · INA226 · AUX"])
    b.root_notes = [
        "Bay node — one per bay.  Sheets:",
        "  Power: row cable (JST PH 6: bus, GND, CAN_H, CAN_L, GND, POS), reverse protection, LMR51635 buck, AMS1117",
        "  MCU: ESP32-S3-WROOM-1-N8R8 (8 MB flash, 8 MB octal PSRAM), reset/boot, status LED, UART pads",
        "  USB: front PC port, DUT port, two FSUSB42 muxes + OR gate (classic / USB-IP / service modes)",
        "  DUT power & AUX: TPS2553 switch → shunt → DUT_5V, INA226 monitor, AUX UART/RESET/BOOT",
        "  Camera: JST PH 8 to the bay's Arducam Mega (SPI2, 5 V through a PTC) and its LEDs (AO3400A low side)",
        "  Rack bus: TJA1462AT CAN transceiver on the row pair, POS token in/out (docs/can.md)",
        "",
        "Mode truth table:  SERVICE=0, PC unplugged → DUT↔ESP32 (USB/IP)",
        "                   SERVICE=0, PC plugged   → DUT↔PC (classic), ESP32 still controls DUT_5V/AUX",
        "                   SERVICE=1               → PC↔ESP32 (flash/console), DUT data disconnected",
        "GPIO firmware can also force classic mode (MUX_FORCE_PC).",
    ]
    # the row bus on In2: J1 pin 1 (left edge, rear end of the 6-pin connector, y = PWR_Y - 5) straight
    # across to J2 pin 6 (right edge, also its rear end: J2's pinout is J1's mirrored, docs/can.md), a
    # strip above the connectors' other pins.  3.8 mm wide (≈ 1.9 A in 0.5 oz for 10 °C)
    bus = [(0.5, PWR_Y - 7.2), (W - 0.5, PWR_Y - 7.2), (W - 0.5, PWR_Y - 3.4), (0.5, PWR_Y - 3.4)]
    hs_tracks, hs_vias = usb_hs_routes()
    b.pcb = {
        "size": (W, H), "layers": CFG["layers"], "corner_radius": 2.0, "passes": 60,
        # 4 layers: signals + GND / GND only / power only / signals + GND.  In1 is a solid GND plane;
        # In2 carries power planes and nothing else (+3V3, +5V, the VRACK bus strip): no signal is
        # routed on it.  Every GND and supply pin gets its own via to its plane before routing
        # ("fanout_nets"), so none depends on the outer GND pours, which stay as a bonus, tied to
        # In1 by stitching vias.  Every pour connects pads through thermal reliefs (pcbgen.py).
        "inner": [("In1.GND", "power"), ("In2.PWR", "power")],
        # JLC's standard 4-layer build (In1 sits 0.21 mm under F.Cu, In2 0.21 mm over B.Cu), lead-free
        # HASL (the user, 2026-10-19: 10 boards in HASL, $12.60 less than ENIG; no BGA, the finest pitch
        # is 0.5 mm; HASL may dome a little under the WROOM-1's exposed pad)
        "stackup": "JLC04161H-7628", "finish": "HASL",
        "edge_parts": ["J*", "U3"],
        # GCT's USB4105 footprint puts its GND pads 0.19 mm from its own NPTH pegs (the datasheet's land pattern)
        "dru": "".join(f"""
(rule "USB4105 {r}: GND pads beside its own pegs"
	(condition "A.memberOfFootprint('{r}') && B.memberOfFootprint('{r}')")
	(constraint hole_clearance (min 0.19mm)))
""" for r in ("J3",)),
        "defer_pours": False,
        # net: (plane, via Ø, drill, track width)
        "fanout_nets": {"GND": ("In1.Cu", 0.5, 0.3, 0.25), "+3V3": ("In2.Cu", 0.6, 0.3, 0.25),
                        "+5V": ("In2.Cu", 0.6, 0.3, 0.4)},
        # supply pins still left without a via to their In2 area after routing get one (pcbgen.py)
        "plane_nets": {"+5V": "In2.Cu", "+3V3": "In2.Cu"},
        # nets carrying power (≳ 0.5 A): their IC, connector and big pads connect solid to the pours, small
        # parts keep reliefs (pcbgen.power_pads); the number is the spokes a relieved pad of theirs keeps
        "power_nets": {"GND": 1, "VRACK": 2, "VIN": 2, "+5V": 2, "DUT_5V*": 2, "CAM_5V": 2},
        "stitch": 4.0,
        "zones": [
            {"layer": "In1.Cu", "net": "GND"},
            {"layer": "F.Cu", "net": "GND"},
            {"layer": "B.Cu", "net": "GND"},
            # In2 areas with exact outlines that don't overlap (the router takes each outline as copper
            # of its net).  +3V3 under the module, the LDO and the logic around it (mux cluster, INA226);
            # +5V from the buck to the LDO input, the DUT switch, the camera fuse and U8; the VRACK strip
            # between J1 and J2; +3V3 again under the front edge (LED, SERVICE switch)
            {"layer": "In2.Cu", "net": "+3V3", "priority": 1,
             "poly": [(0.4, 0.4), (51.85, 0.4), (51.85, 30.0), (47.85, 30.0), (47.85, 44.0), (22.0, 44.0),
                      (22.0, 34.0), (0.4, 34.0)]},
            {"layer": "In2.Cu", "net": "+5V", "priority": 1,
             "poly": [(52.15, 0.4), (W - 0.4, 0.4), (W - 0.4, PWR_Y - 7.5), (0.4, PWR_Y - 7.5), (0.4, 34.3), (21.7, 34.3),
                      (21.7, 44.3), (48.15, 44.3), (48.15, 30.3), (52.15, 30.3)]},
            {"layer": "In2.Cu", "net": "+3V3", "priority": 1,
             "poly": [(0.4, PWR_Y - 3.1), (W - 0.4, PWR_Y - 3.1), (W - 0.4, 89.6), (0.4, 89.6)]},
            {"layer": "In2.Cu", "net": "VRACK", "priority": 3, "poly": bus},
            # buck hot loop (TI SLUSF64B §8.4): top-side islands joining CIN, U1 and COUT.  GND and
            # +5V are exclusive (other nets' tracks stay out of their cores: Freerouting once cut buck-5v in two
            # between C8 and C9); the narrow VIN island is not, its feed from C1 comes in along its edge
            {"layer": "F.Cu", "net": "GND", "connection": "solid", "name": "buck-gnd", "priority": 3, "exclusive": 0.5,
             "poly": [(8.05, 44.5), (10.1, 44.5), (10.1, 46.2), (11.9, 46.2), (11.9, 50.3), (20.6, 50.3), (20.6, 54.4),
                      (8.05, 54.4)]},
            {"layer": "F.Cu", "net": "+5V", "connection": "solid", "name": "buck-5v", "priority": 3, "exclusive": 0.5,
             "poly": [(12.8, 48.1), (17.3, 48.1), (17.3, 40.6), (21.0, 40.6), (21.0, 49.9), (12.8, 49.9)]},
            {"layer": "F.Cu", "net": "VIN", "connection": "solid", "name": "buck-vin", "priority": 3,
             "poly": [(5.6, 44.5), (7.8, 44.5), (7.8, 52.7), (5.6, 52.7)]},
            # J1/J2 (6-pin SMD, docs/can.md): the whole row's supply and its return pass through J1.1 / J2.6
            # and the GND pins 2/5 (up to the hub's 1.6 A eFuse limit), so each of them sits on a solid
            # island with two vias to its plane.  CAN (3/4) and POS (J1.6, J2.1) are ordinary signals.
            *[{"layer": "F.Cu", "net": n, "connection": "solid", "name": nm, "priority": 3,
               "poly": [(x0, y - 0.7), (x1, y - 0.7), (x1, y + 0.7), (x0, y + 0.7)]}
              for n, nm, x0, x1, y in (("VRACK", "j1-bus", 5.8, 11.0, PWR_Y - 5), ("GND", "j1-gnd2", 5.8, 11.0, PWR_Y - 3),
                                       ("GND", "j1-gnd5", 5.8, 11.6, PWR_Y + 3),
                                       ("VRACK", "j2-bus", W - 9.7, W - 4.2, PWR_Y - 5),
                                       ("GND", "j2-gnd2", W - 11.3, W - 5.8, PWR_Y + 3),
                                       ("GND", "j2-gnd5", W - 11.3, W - 5.8, PWR_Y - 3))],
            # under the ESP32 module (Espressif's layout guide): its exposed GND pad on a top-side island,
            # stitched to In1 around the pad (no via in the pad)
            {"layer": "F.Cu", "net": "GND", "name": "esp-gnd", "priority": 3,
             "poly": [(27.3, 12.0), (33.7, 12.0), (33.7, 18.4), (27.3, 18.4)]},
            # AMS1117 tab: up to ~0.7 W at Wi-Fi peaks (1.7 V × 0.4 A); top-side copper on the tab and
            # C12, vias down to the +3V3 area on In2; exclusive, as the buck's (a track once cut C12 off it)
            {"layer": "F.Cu", "net": "+3V3", "connection": "solid", "name": "ldo-tab", "priority": 3, "exclusive": 0.5,
             "poly": [(8.4, 26.0), (17.2, 26.0), (17.2, 32.2), (8.4, 32.2)]},
            # the DUT switch's input (up to its ≈ 1.5 A limit): U9.IN and C20 on a top-side island, three vias
            # down to In2's +5V (one 0.3 mm via and a 0.4 mm track before: pcba-review N4)
            {"layer": "F.Cu", "net": "+5V", "name": "dutsw-in", "priority": 3, "connection": "solid",
             "poly": [(51.9, 37.75), (53.4, 37.75), (53.4, 39.3), (54.9, 39.3), (54.9, 40.6), (53.55, 40.6),
                      (53.55, 41.45), (52.55, 41.45), (52.55, 39.6), (51.9, 39.6)]},
        ],
        "vias": [("GND", 11.0, 46.9), ("GND", 11.0, 49.4), ("GND", 11.2, 53.4), ("GND", 13.0, 53.6),
                 ("GND", 15.25, 53.6), ("GND", 17.75, 53.6), ("GND", 20.0, 53.6),
                 *[("GND", x, y) for x in (27.8, 30.5, 33.2) for y in (12.5, 17.9)],
                 ("GND", 27.8, 15.2), ("GND", 33.2, 15.2),
                 ("VRACK", 14.0, 68.1), ("VRACK", 16.0, 68.1),
                 *[(n, x, PWR_Y + dy) for n, dy in (("VRACK", -5), ("GND", -3), ("GND", 3)) for x in (10.05, 10.75)],
                 *[(n, x, PWR_Y + dy) for n, dy in (("GND", -3), ("GND", 3)) for x in (W - 10.8, W - 10.1)],
                 # J2.6 (VRACK): its vias right at the pad's end, as J1.1's, so no track passes between them
                 *[("VRACK", x, PWR_Y - 5) for x in (W - 5.45, W - 4.75)],
                 # buck output island down to the +5V area, LDO tab down to the +3V3 area
                 *[("+5V", x, y) for x, y in ((17.9, 41.2), (20.4, 41.2), (20.5, 45.0), (20.5, 47.2))],
                 *[("+3V3", x, y) for x, y in ((9.2, 26.8), (10.6, 26.8), (12.0, 26.8), (13.4, 26.8),
                                               (14.8, 26.8), (15.2, 28.4), (9.0, 29.8), (9.0, 31.5))],
                 ("+3V3", 41.5, 43.0), ("+3V3", 41.5, PWR_Y - 1.5),
                 *[("+5V", x, y) for x, y in ((53.0, 39.85), (54.0, 39.95), (54.6, 39.95))],        # U9's input island
                 *hs_vias],
        # the front +3V3 area of In2 (LED, SERVICE switch) is cut off by the VRACK strip: fed from the
        # main +3V3 area by a B.Cu track
        "tracks": [*hs_tracks, ("+3V3", "B.Cu", 0.4, [(41.5, 43.0), (41.5, PWR_Y - 1.5)])],
        # ESP32 antenna: no copper on any layer under/around the antenna (the WROOM-1's rear 6 mm, ±24 mm)
        "keepouts": [
            {"name": "antenna", "poly": [(8.0, -0.1), (56.0, -0.1), (56.0, 6.0), (8.0, 6.0)]},
        ],
        "texts": [
            {"text": "hw-testing-rack · bay node v0.5", "x": 32, "y": 56, "size": 0.8, "layer": "B.SilkS"},
            {"text": "PC", "x": 37.0, "y": 80.2, "size": 0.9},
            {"text": "SVC", "x": 50, "y": 83.6, "size": 0.8},
            {"text": "ROW IN", "x": 5.2, "y": PWR_Y + 9.6, "size": 0.8},
            {"text": "ROW OUT", "x": W - 5.2, "y": PWR_Y + 9.6, "size": 0.8},
            # the side-entry mouths' names inside the edge, between them; the camera's over J6's rear end
            {"text": "DATA", "x": EDGE_X - 2.6, "y": CFG["right"]["data"] - 11.6, "size": 0.8},
            {"text": "AUX", "x": EDGE_X - 2.6, "y": (CFG["right"]["data"] + CFG["aux"][1]) / 2 + 1.0, "size": 0.8},
            {"text": "CAM", "x": CFG["cam"][0], "y": CFG["cam"][1] - 11.6, "size": 0.8},
            {"text": "RESET", "x": 7.5, "y": 25.4, "size": 0.8},
            {"text": "BOOT", "x": 15.5, "y": 25.4, "size": 0.8},
        ],
    }

    # ------------------------------------------------------------------ power
    s = b.sheet("Power", "power.kicad_sch", "VRACK input (20–28 V), 5 V buck, 3.3 V LDO")
    s.frame("Row cable in / out (JST PH 6, daisy chain: bus, GND, CAN_H, CAN_L, GND, POS) and input protection",
            6, 6, 52, 30)
    # J1 on the left edge (pin 1 towards the rear), J2 on the right edge (the same footprint turned 180°:
    # its pin 1 towards the front).  J2's pinout is J1's mirrored (J2.n = J1.(7-n)), so every net crosses
    # the board straight and J2 of one bay meets J1 of the next through a flat cable with no twist: both
    # plugs the same face up, wire 1 to pin 6 (docs/can.md).  CAN_H/CAN_L pass straight through, POS is
    # cut here: J1.6 is this node's token input, J2.1 its output (Rack bus sheet)
    for ref, val, y, rot, x, nets in (
            ("J1", "ROW IN", 14, 270, PH_EDGE,
             {"1": "VRACK", "2": "GND", "3": "CAN_H", "4": "CAN_L", "5": "GND", "6": "POS_IN_CONN"}),
            ("J2", "ROW OUT", 24, 90, W - PH_EDGE,
             {"1": "POS_OUT_CONN", "2": "GND", "3": "CAN_L", "4": "CAN_H", "5": "GND", "6": "VRACK"})):
        part(s, ref, "ph6", nets, val, pcb=P(x, PWR_Y, rot), sch=at(10, y, mirror="y", fields="left"))
        for pin, dy in (("2", -1), ("5", 2)):
            s.wire(f"{ref}.{pin}", (13, y + dy))
            s.tag("GND", (13, y + dy), "right")
        for pin, dy in (("3", 0), ("4", 1), ("6", 3)) + ((("1", -2),) if ref == "J2" else ()):
            s.wire(f"{ref}.{pin}", (13, y + dy))
            s.tag(nets[pin], (13, y + dy), "right")
    s.part("#FLG01", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "VRACK"}, in_bom=False, on_board=False, sch=at(21, 12, fields=(-3.8, -2.6)))
    s.part("#FLG02", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "GND"}, in_bom=False, on_board=False, sch=at(30, 24, fields=(0.6, -2.6)))
    s.part("#FLG03", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "VIN"}, in_bom=False, on_board=False, sch=at(45, 12, fields=(-3.8, -2.6)))
    s.part("#FLG04", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+5V"}, in_bom=False, on_board=False, sch=at(77, 46, fields=(-3.8, -2.6)))
    part(s, "Q1", "pfet", {"G": "Q1_GATE", "D": "VRACK", "S": "VIN"}, pcb=P(15, 66, 90),
         sch=at(24, 13, rot=90, fields=(3.5, -3.8)))
    part(s, "D1", "zener12", {"K": "VIN", "A": "Q1_GATE"}, pcb=P(15, 74.5, 180), sch=at(29, 16.5, rot=270))
    R(s, "R1", "100k", "Q1_GATE", "GND", pcb=P(15, 77.3, 0), sch=at(24, 20.5))
    part(s, "D2", "tvs33", {"K": "VIN", "A": "GND"}, pcb=P(22, 68, 90), sch=at(35, 16.5, rot=270))
    part(s, "C1", "cap100u50", {"1": "VIN", "2": "GND"}, "100u/50V", pcb=P(6, 58.4, 90), sch=at(41, 16.5))
    s.wire("J1.1", (19, 12), "Q1.D")
    s.wire("#FLG02.1", (30, 25))
    s.tag("GND", (30, 25), "down")
    s.wire("Q1.G", "R1.1")
    s.wire((24, 18), "D1.A")
    s.wire((29, 12), "D1.K")
    s.wire((35, 12), "D2.K")
    s.wire((41, 12), "C1.1")
    s.wire("Q1.S", (48, 12))
    s.tag("VIN", (48, 12), "up")

    s.frame("5 V buck: LMR51635, synchronous, 1.1 MHz, 3.5 A (TI SLUSF64B typical application)", 6, 32, 84, 60)
    s.tag("VIN", (12, 38), "up")
    s.wire((12, 38), (35, 38), (35, 45), "U1.VIN")
    C(s, "C2", "10u", "VIN", "GND", size="1206", pcb=P(8, 48.8, 0), sch=at(16, 41.5))
    C(s, "C3", "10u", "VIN", "GND", size="1206", pcb=P(8, 51.4, 0), sch=at(20, 41.5))
    C(s, "C4", "100n", "VIN", "GND", pcb=P(8, 46.6, 0), sch=at(24, 41.5))
    for c_, x in (("C2", 16), ("C3", 20), ("C4", 24)):
        s.wire((x, 38), f"{c_}.1")
    # EN 100k/10k: on above 13.5 V, off below 10.8 V (values the board already has; 0.25 mA at 28 V)
    R(s, "R2", "100k", "VIN", "BUCK_EN", pcb=P(4.78, 46.3, 90), sch=at(29, 41.5))
    R(s, "R3", "10k", "BUCK_EN", "GND", pcb=P(4, 44.0, 180), sch=at(29, 48.5))
    s.wire((29, 38), "R2.1")
    s.wire("R2.2", "R3.1")
    s.wire((29, 44), (33, 44), (33, 47), "U1.EN")
    part(s, "U1", "buck", {"VIN": "VIN", "EN": "BUCK_EN", "CB": "BUCK_CB", "SW": "BUCK_SW", "FB": "BUCK_FB",
                           "GND": "GND"}, pcb=P(8, 44, 0), sch=at(40, 46, fields=(-4, -4)))
    C(s, "C5", "100n", "BUCK_CB", "BUCK_SW", pcb=P(9.6, 41.5, 0), sch=at(51.5, 41, rot=90))
    s.wire("U1.CB", (46, 45), (46, 41), "C5.1")
    s.wire("C5.2", (53, 46))
    part(s, "L1", "buck_l", {"1": "BUCK_SW", "2": "+5V"}, "3.3u", pcb=P(15.7, 44, 0), sch=at(57.5, 46, rot=90))
    s.wire("U1.SW", (53, 46), "L1.1")
    s.wire("L1.2", (80, 46))
    s.tag("+5V", (80, 46), "up")
    for i, x in enumerate((62, 66, 70)):
        C(s, f"C{7 + i}", "22u", "+5V", "GND", size="1206", pcb=P(14 + 2.5 * i, 50.5, 270), sch=at(x, 47.5))
    R(s, "R4", "100k", "+5V", "BUCK_FB", pcb=P(4, 40.6, 0), sch=at(74, 48.5))
    R(s, "R5", "18k", "BUCK_FB", "GND", pcb=P(4, 42.2, 180), sch=at(74, 55.5))
    s.wire((74, 46), "R4.1")
    s.wire("R4.2", "R5.1")
    s.wire((74, 53), (46, 53), (46, 47), "U1.FB")

    s.frame("3.3 V logic supply", 88, 32, 116, 50)
    part(s, "U2", "ldo", {"VI": "+5V", "VO": "+3V3", "GND": "GND"}, pcb=P(12, 33, 90), sch=at(102, 42, fields=(-3, -3.5)))
    # the LDO's input; a 1206 (C2/C3's 10 µF, one part type less) overlaps U2 and its neighbours here
    C(s, "C11", "10u", "+5V", "GND", size="0805", pcb=P(17.4, 36.15, 0), sch=at(95, 43.5))
    C(s, "C12", "22u", "+3V3", "GND", size="1206", pcb=P(18.0, 30.6, 0), sch=at(109, 43.5))
    s.tag("+5V", (92, 42), "up")
    s.wire((92, 42), "U2.VI")
    s.wire("U2.VO", (112, 42))
    s.tag("+3V3", (112, 42), "up")
    s.notes_at = (6, 64, 110)
    s.note("LMR51635YDDCR: 1.1 MHz, PFM at light load with spread spectrum.  Values from TI SLUSF64B table 8-2 (5 V, 1.1 MHz):")
    s.note("  L 3.3 µH (FXL0630, 9.5 A sat);  COUT 3 × 22 µF/25 V (≥ 33 µF left after DC-bias derating);  CIN 2 × 10 µF/50 V + 100 nF;  CB 100 nF.")
    s.note("FB 100k/18k: VOUT = 0.8 V × (1 + 100/18) = 5.24 V: ≈ 4.75 V still reaches the DATA board at 1.4 A over 50 cm")
    s.note("  of PH lead (switch, shunt, one PH pin each way); everything on +5V takes it (TJA1462AT ≤ 5.5 V).")
    s.note("EN 100k/10k: the buck starts above 13.5 V and stops below 10.8 V (VEN 1.226 V, 0.241 V hysteresis), so no node")
    s.note("  draws its low-voltage inrush while the hub's eFuse is soft-starting the row.")
    s.note("Layout: C4/C2/C3 straddle U1's VIN and GND pins on the top layer; CIN, U1 and COUT share one top-side GND island")
    s.note("  with vias to the In1 plane; the FB divider sits at the FB pin, its +5V sense comes from COUT on another layer.")
    s.note("Input: SUD50P06 P-FET (reverse polarity, Vgs clamped by the 12 V zener); SMBJ33A clamps hot-plug ringing below 54 V (U1: 63 V abs max).")
    s.note("VRACK is 20 V, or 28 V (EPR), from the hub's USB-C PD supply: SMBJ33A stands off 33 V (28 V + 5 % = 29.4 V), the buck runs")
    s.note("  4.3–60 V and starts above 13.5 V, the P-FET and the zener clamp are rated 60 V / 12 V.  At 20 V a row draws more current: ≤ 1.6 A.")

    # ------------------------------------------------------------------ MCU
    m = b.sheet("MCU", "mcu.kicad_sch", "ESP32-S3 module")
    m.frame("Reset and boot", 6, 6, 40, 30)
    part(m, "SW1", "button", {"1": "EN", "2": "GND"}, "RESET", pcb=P(7.5, 21.5, 0), sch=at(14, 15, rot=270))
    R(m, "R6", "10k", "+3V3", "EN", pcb=P(18.6, 9.5, 90), sch=at(22, 10.5))
    C(m, "C15", "1u", "EN", "GND", pcb=P(18.6, 13.2, 90), sch=at(27, 14.5))
    m.wire("SW1.1", (32, 13))
    m.wire("R6.2", (22, 13))
    m.tag("EN", (32, 13), "right")
    part(m, "SW2", "button", {"1": "BOOT", "2": "GND"}, "BOOT", pcb=P(15.5, 21.5, 0), sch=at(14, 24, rot=270))
    R(m, "R7", "10k", "+3V3", "BOOT", pcb=P(43.2, 24.9, 90), sch=at(22, 19.5))
    m.wire("SW2.1", (32, 22))
    m.wire("R7.2", (22, 22))
    m.tag("BOOT", (32, 22), "right")

    m.frame("UART test pads", 6, 31, 40, 45)
    # a 2 × 2 block on the bottom side, beside the WROOM's TXD0/RXD0 pins (right column, rear half)
    tp_xy = ((45.8, 10.2), (43.2, 10.2), (43.2, 12.8), (45.8, 12.8))
    for i, (net, y) in enumerate((("U0TX", 35), ("U0RX", 37), ("GND", 39), ("+3V3", 42))):
        part(m, f"TP{i + 1}", "testpad", {"1": net}, net, pcb=P(*tp_xy[i], 0, "bottom"), in_bom=False,
             sch=at(12, y, rot=90, fields="left"))
    m.wire("TP3.1", (15, 39), (15, 40))
    m.tag("GND", (15, 40), "down")
    m.wire("TP4.1", (18, 42), (18, 41))
    m.tag("+3V3", (18, 41), "up")

    m.frame("ESP32-S3-WROOM-1-N8R8 (PCB antenna at the board's rear edge: no copper under it, any layer)", 46, 6, 112, 56)
    # the module's top edge on the board's rear edge; its footprint carries the antenna keep-out (±24 mm)
    part(m, "U3", "esp32s3wr8", {
        "3V3": "+3V3", "GND": "GND", "EN": "EN", "IO0": "BOOT",
        "USB_D-": "ESP_DN", "USB_D+": "ESP_DP",
        # each signal on the module edge that faces where it goes (docs/electronics.md, GPIO map), and
        # the whole map the ESP32-S3-DevKitC-1 v1.1 (N8R8) can take as is: none on IO35-IO37 (octal
        # PSRAM), none on a strapping pin (IO3/IO45/IO46), the status LED on the devkit's IO38.
        # right column -> DUT power block (rear right), I2C at its rear end, POS_OUT towards J2
        "IO41": "DUT_EN", "IO40": "DUT_FLT_N", "IO39": "INA_ALERT_N", "IO2": "I2C_SDA", "IO1": "I2C_SCL",
        "IO42": "POS_OUT", "IO38": "LED_DIN",
        # bottom row -> AUX (right half), mode logic, the camera's SPI (left half)
        "IO48": "AUX_BOOT_CTL", "IO47": "AUX_TX", "IO21": "AUX_RX", "IO12": "AUX_RST_CTL",
        "IO13": "PC_DET", "IO14": "MUX_FORCE_PC",
        "IO11": "CAM_SCK", "IO10": "CAM_MOSI", "IO9": "CAM_MISO",
        # left column -> the rack bus block (CAN, POS_IN), SERVICE, the camera's CS and light
        "IO15": "SVC", "IO16": "POS_IN", "IO17": "CAN_RXD", "IO18": "CAN_TXD",
        "IO8": "CAM_CS", "IO7": "CAM_LED", "IO4": "DATA_INT",
        "TXD0": "U0TX", "RXD0": "U0RX",
    }, pcb=P(32, 12.75, 0), sch=at(80, 38, fields=(-14, -14)))
    # 3V3 (pin 2) and EN (pin 3) sit at the left column's rear end
    C(m, "C13", "22u", "+3V3", "GND", size="1206", pcb=P(21.0, 9.5, 90), sch=at(96, 23.5))
    C(m, "C14", "100n", "+3V3", "GND", pcb=P(21.0, 13.4, 90), sch=at(100, 23.5))
    m.wire("U3.3V3", (80, 22), "C14.1")
    m.tag("+3V3", (80, 22), "up")

    m.frame("Status LED (behind the fascia window)", 6, 48, 40, 66)
    part(m, "D4", "rgb", {"VDD": "+3V3", "VSS": "GND", "DIN": "LED_DIN_R", "DOUT": None}, pcb=P(12, 88.2, 0),
         sch=at(31, 57, fields=(4, 1)))
    R(m, "R8", "33", "LED_DIN", "LED_DIN_R", pcb=P(16, 84.5, 0), sch=at(19.5, 57, rot=90))
    C(m, "C16", "100n", "+3V3", "GND", pcb=P(16, 87.8, 90), sch=at(37, 53.5))
    m.wire("R8.2", "D4.DIN")
    m.wire("D4.VDD", (31, 52), "C16.1")
    m.tag("+3V3", (31, 52), "up")
    m.notes_at = (6, 70, 106)
    m.note("GPIO map: IO41 DUT_EN · IO40 DUT_FLT_N · IO39 INA_ALERT · IO2/1 I2C SDA/SCL · IO47/21 UART1 TX/RX (AUX) ·")
    m.note("IO12 AUX_RST · IO48 AUX_BOOT · IO38 LED · IO13 PC_DET · IO14 MUX_FORCE_PC · IO15 SVC · IO19/20 USB (OTG/JTAG) ·")
    m.note("IO18/17 CAN TX/RX (TWAI) · IO16 POS_IN · IO42 POS_OUT · camera SPI2: IO11 SCK · IO10 MOSI · IO9 MISO · IO8 CS ·")
    m.note("IO7 light · IO4 DATA_INT (J7.8, open drain, active low).  Free: IO5, IO6.  IO35–IO37 are the octal PSRAM's;")
    m.note("the WROOM-1 has no IO26/IO33/IO34.  The I²C bus (IO1/IO2) also goes out on J7.6/7 to the drawer's DATA board.")
    m.note("The map is the ESP32-S3-DevKitC-1 v1.1's (N8R8) as is: the bench stand-in needs no remap.")
    m.note("Strapping pins IO0/IO3/IO45/IO46 are not used for I/O.  USB is full-speed only (one internal PHY).")

    # ------------------------------------------------------------------ USB
    u = b.sheet("USB", "usb.kicad_sch", "USB ports and data-path muxes")
    u.frame("Front PC port: USB-C sink (Rd 5.1k on CC), VBUS only sensed", 6, 6, 56, 52)
    part(u, "J3", "usbc5a", {"VBUS": "PC_VBUS", "GND": "GND", "CC1": "PC_CC1", "CC2": "PC_CC2", "D+": "PC_CONN_DP",
                           "D-": "PC_CONN_DN", "SBU1": None, "SBU2": None, "SHIELD": "GND"}, "PC", pcb=P(32, 86.6, 0),
         sch=at(14, 28, fields=(-4, -9)))
    u.wire("J3.A7", (22, 27), (22, 28), "J3.B7")
    u.wire("J3.A6", (23, 29), (23, 30), "J3.B6")
    # USBLC6 flow-through: the connector side (pins 6/4) and the protected side (1/3) are separate nets,
    # so the only path from J3 to the mux runs through the part (drawn mirrored: connector side left)
    part(u, "U4", "esd", {"6": "PC_CONN_DN", "1": "PC_DN", "4": "PC_CONN_DP", "3": "PC_DP", "5": "+5V", "2": "GND"},
         pcb=P(32.0, 77.0, 270), sch=at(33, 28, mirror="y", fields=(1.5, 3.5)))
    u.wire((22, 28), "U4.6")
    u.wire((23, 29), "U4.4")
    # the USBLC6 clamps to its VBUS pin: a local 100 nF keeps that rail stiff during a discharge
    C(u, "C25", "100n", "+5V", "GND", pcb=P(35.4, 76.9, 0), sch=at(48, 30))
    R(u, "R11", "10k", "PC_VBUS", "PC_DET", pcb=P(27.0, 79.0, 90), sch=at(37.5, 22, rot=90))
    R(u, "R12", "18k", "PC_DET", "GND", pcb=P(27.0, 76.0, 90), sch=at(42, 23.5))     # 5 V → 3.2 V
    u.wire("J3.VBUS", "R11.1")
    u.wire("R11.2", (46, 22))
    u.tag("PC_DET", (46, 22), "right")
    R(u, "R9", "5.1k", "PC_CC1", "GND", pcb=P(24.5, 84.5, 90), sch=at(24.5, 44, rot=90))
    R(u, "R10", "5.1k", "PC_CC2", "GND", pcb=P(39.5, 84.5, 90), sch=at(24.5, 47, rot=90))
    u.wire("R9.2", (28, 44), (28, 48))
    u.wire("R10.2", (28, 47))
    u.tag("GND", (28, 48), "down")

    u.frame("USB 2.0 data muxes (FSUSB42): MUX_PC → DUT path or ESP32, MUX_DUT → ESP32 or PC path", 58, 6, 124, 36)
    part(u, "U5", "mux", {"VCC": "+3V3", "GND": "GND", "D+": "PC_DP", "D-": "PC_DN", "HSD1+": "PCPATH_DP",
                          "HSD1-": "PCPATH_DN", "HSD2+": "ESP_DP", "HSD2-": "ESP_DN", "SEL": "SVC", "~{OE}": "GND"},
         "MUX_PC", pcb=P(34.6, 37.5, 0), sch=at(76, 26, fields=(1.5, 4.5)))
    C(u, "C17", "100n", "+3V3", "GND", pcb=P(31.2, 34.2, 180), sch=at(68, 17.5))
    u.wire("U5.VCC", (76, 16), "C17.1")
    u.tag("+3V3", (76, 16), "up")
    part(u, "U6", "mux", {"VCC": "+3V3", "GND": "GND", "D+": "DUT_DP", "D-": "DUT_DN", "HSD1+": "ESP_DP",
                          "HSD1-": "ESP_DN", "HSD2+": "PCPATH_DP", "HSD2-": "PCPATH_DN", "SEL": "MUX_SEL",
                          "~{OE}": "SVC"}, "MUX_DUT", pcb=P(44.5, 34.5, 180), sch=at(104, 26, mirror="y", fields=(1.5, 4.5)))
    C(u, "C18", "100n", "+3V3", "GND", pcb=P(47.6, 38.0, 270), sch=at(112, 17.5))
    u.wire("U6.VCC", (104, 16), "C18.1")
    u.wire("U6.SEL", (115, 28))
    u.tag("MUX_SEL", (115, 28), "right")
    u.tag("+3V3", (104, 16), "up")

    # the DUT's USB leaves on J7 only (the node has no DUT receptacle since 2026-10-19: in the rack it sat under
    # the drawer and only hung a stub on the pair; a bench node takes a DATA port board on a J7 lead): U8 is the
    # ESD at the lead's node end, flow-through between U6 and J7
    u.frame("DUT USB: ESD at the DATA lead's node end (flow-through), towards J7", 106, 40, 160, 72)
    part(u, "U8", "esd", {"6": "DUT_CONN_DN", "1": "DUT_DN", "4": "DUT_CONN_DP", "3": "DUT_DP", "5": "+5V",
                          "2": "GND"}, pcb=P(51.3, 34.0, 0), sch=at(134, 58, fields=(1.5, 3.5)))
    C(u, "C26", "100n", "+5V", "GND", pcb=P(51.6, 36.9, 0), sch=at(124, 64))       # U8's VBUS, via In2 +5V

    # the drawer's DATA board on an 8-wire PH lead (the camera's lead type, 'Same direction'): VBUS, GND,
    # D−, D+, GND as before, then the node's I²C (the INA226's bus, 2.2k pull-ups on this board) and an
    # open-drain, active-low INT (10k pull-up here, 1k in series at the connector).  The single DATA port
    # board leaves pins 6–8 open; a later DATA ×4 board uses them (its I²C devices must keep off 0x40).
    # Side entry on the right edge (like J2: pin 1 towards the front), its mouth towards the drag chain's fixed
    # end; the pair from U8 is drawn in usb_hs_routes.  DUT_5V comes after the shunt.
    u.frame("DATA: the DUT's USB, I²C and INT on an 8-wire PH lead to the drawer's DATA board", 106, 75, 160, 100)
    part(u, "J7", "ph8", {"1": "DUT_5V", "2": "GND", "3": "DUT_CONN_DP", "4": "DUT_CONN_DN", "5": "GND", "6": "I2C_SDA",
                           "7": "I2C_SCL", "8": "DATA_INT_C"}, "DATA",
         pcb=P(EDGE_X, CFG["right"]["data"], 90), sch=at(152, 86, fields=(1, -7)))
    for pin, dy, net in (("1", -3, "DUT_5V"), ("2", -2, "GND"), ("3", -1, "DUT_CONN_DP"), ("4", 0, "DUT_CONN_DN"),
                         ("5", 1, "GND"), ("6", 2, "I2C_SDA"), ("7", 3, "I2C_SCL"), ("8", 4, "DATA_INT_C")):
        u.wire(f"J7.{pin}", (143, 86 + dy))
        u.tag(net, (143, 86 + dy), "left")
    R(u, "R41", "1k", "DATA_INT", "DATA_INT_C", pcb=P(58.0, 29.4, 0), sch=at(124, 92, rot=90))
    # the INT pull-up beside the module (over In2 +3V3; J7 sits over +5V)
    R(u, "R38", "10k", "DATA_INT", "+3V3", pcb=P(20.9, 16.9, 90), sch=at(116, 95))

    u.frame("Mode logic: MUX_SEL = PC_DET OR MUX_FORCE_PC; SERVICE switch", 6, 58, 84, 86)
    part(u, "U7", "or", {"1": "PC_DET", "2": "MUX_FORCE_PC", "3": "GND", "4": "MUX_SEL", "5": "+3V3"},
         pcb=P(27.5, 41.5, 0), sch=at(40, 74, fields=(-6, -5)))
    C(u, "C19", "100n", "+3V3", "GND", pcb=P(27.5, 38.6, 180), sch=at(46, 67.5))
    u.wire("U7.5", (40, 66), "C19.1")
    u.tag("+3V3", (40, 66), "up")
    R(u, "R13", "100k", "MUX_FORCE_PC", "GND", pcb=P(27.5, 44.6, 0), sch=at(28, 77.5))
    u.wire("U7.2", (24, 75))
    u.wire("R13.1", (28, 75))
    u.tag("MUX_FORCE_PC", (24, 75), "left")
    u.wire("U7.4", (52, 74))
    u.tag("MUX_SEL", (52, 74), "right")
    part(u, "SW3", "slide", {"1": "+3V3", "2": "SVC", "3": "GND"}, "SERVICE", pcb=P(50, 87.3, 0),
         sch=at(70, 74, mirror="y", fields=(-2, 3)))
    u.wire("SW3.1", (66, 73), (66, 71))
    u.tag("+3V3", (66, 71), "up")
    u.wire("SW3.3", (66, 75), (66, 77))
    u.tag("GND", (66, 77), "down")
    # SW3 is SVC's only driver: 100k holds it low (normal mode) while the slider travels between its contacts
    R(u, "R39", "100k", "SVC", "GND", pcb=P(54.5, 83.0, 0), sch=at(78, 80))
    u.notes_at = (6, 90, 100)
    u.note("SVC=1 routes the PC port to the ESP32 (flash / console / JTAG) and disables MUX_DUT (~OE high).")
    u.note("MUX_SEL = PC_DET OR MUX_FORCE_PC: a laptop on the front port takes the DUT over automatically.")

    # ------------------------------------------------------------------ DUT power + AUX
    d = b.sheet("DUT power & AUX", "dut.kicad_sch", "DUT power switch, monitor and AUX")
    d.frame("DUT power path: +5V → TPS2553 switch → 50 mΩ shunt → DUT_5V (J7.1), INA226 across the shunt",
            6, 12, 124, 46)
    d.tag("+5V", (18, 29), "up")
    d.wire((18, 29), "U9.IN")
    # the switch, its resistors, the shunt and the DUT_5V cap between U8 and J5, by J7.1; R17 / R18 over the
    # In2 +3V3 area west of them, the INA226 by the module (its sense pair runs ≈ 18 mm, Kelvin)
    C(d, "C20", "100n", "+5V", "GND", pcb=P(53.35, 38.5, 0), sch=at(22, 30.5))     # at U9.IN, on its island
    part(d, "U9", "vbus_sw", {"IN": "+5V", "GND": "GND", "EN": "DUT_EN", "~{FAULT}": "DUT_FLT_N", "ILIM": "DUT_ILIM",
                              "OUT": "DUT_5V_SW"}, pcb=P(52.0, 42.0, 270), sch=at(40, 30, fields=(-4, -4)))
    R(d, "R16", "18k", "DUT_ILIM", "GND", pcb=P(52.0, 46.0, 0), sch=at(31, 33.5))
    d.wire("U9.ILIM", "R16.1")
    R(d, "R17", "100k", "+3V3", "DUT_EN", pcb=P(45.2, 41.2, 0), sch=at(26, 35.5))
    d.wire("U9.EN", (28, 31), (28, 38), (16, 38))
    d.wire("R17.2", (26, 38))
    d.tag("DUT_EN", (16, 38), "left")
    R(d, "R18", "10k", "+3V3", "DUT_FLT_N", pcb=P(45.2, 43.0, 0), sch=at(52, 35.5))
    d.wire("U9.~{FAULT}", (48, 31), (48, 38), (55, 38))
    d.wire("R18.2", (52, 38))
    d.tag("DUT_FLT_N", (55, 38), "right")
    # Kelvin shunt: pins 1/4 carry the DUT current, pins 2/3 are sense pads on the inner edge of each
    # terminal (bench:R_1206_3216Metric_Kelvin), so the INA226 reads the resistor, not the load copper
    part(d, "R19", "shunt50m", {"1": "DUT_5V_SW", "4": "DUT_5V", "2": "SHUNT_P", "3": "SHUNT_N"}, "50m",
         pcb=P(55.6, 43.0, 270), sch=at(62, 33.5))
    d.wire("U9.OUT", (62, 29), "R19.1")
    d.wire("R19.4", (62, 40), (100, 40))
    d.tag("DUT_5V", (100, 40), "right")
    C(d, "C21", "22u", "DUT_5V", "GND", size="1206", pcb=P(57.2, 38.6, 0), sch=at(96, 41.5))
    part(d, "U10", "ina226", {"VS": "+3V3", "GND": "GND", "A0": "GND", "A1": "GND", "SDA": "I2C_SDA",
                              "SCL": "I2C_SCL", "~{Alert}": "INA_ALERT_N", "Vin+": "SHUNT_P", "Vin-": "SHUNT_N",
                              # Vbus on Vin- (the shunt's load-side Kelvin pad: DUT_5V), joined at the pins (8, 9)
                              "Vbus": "SHUNT_N"}, pcb=P(47.7, 25.9, 0), sch=at(74, 31, fields=(-10, -7)))
    d.wire("R19.2", (66, 32.5), (66, 32), "U10.Vin+")
    d.wire("R19.3", (67, 34.5), (67, 33), "U10.Vin-")
    d.wire("U10.A1", (80, 28), (80, 29), "U10.A0")
    d.tag("GND", (80, 29), "right")
    C(d, "C22", "100n", "+3V3", "GND", pcb=P(48.0, 28.6, 180), sch=at(84, 25.5))
    d.wire("U10.VS", (74, 24), "C22.1")
    d.tag("+3V3", (74, 24), "up")
    d.text("I2C pull-ups", 103, 16.2, 1.27, True)
    d.tag("+3V3", (100, 18), "up")
    d.wire((100, 18), (116, 18), net="+3V3")
    # 2.2k: the bus runs ≈ 50 cm out to a DATA ×4 board (≈ 100–150 pF): ≈ 0.2 µs rise time at 400 kHz, 1.5 mA
    # (5.1k gave 0.35–0.5 µs: pcba-review N2)
    for ref, val, x, net, xy in (("R21", "2.2k", 100, "I2C_SDA", (42.8, 29.3)), ("R22", "2.2k", 108, "I2C_SCL", (44.4, 29.3)),
                                 ("R20", "10k", 116, "INA_ALERT_N", (41.2, 29.3))):
        R(d, ref, val, "+3V3", net, pcb=P(*xy, 90), sch=at(x, 20.5))
        d.wire((x, 18), f"{ref}.1")
        d.wire(f"{ref}.2", (x, 23), (x + 1, 23))
        d.tag(net, (x + 1, 23), "right")

    d.frame("AUX: UART + open-drain RESET / BOOT towards the DUT (JST PH 6)", 68, 48, 112, 86)
    # JST PH like every other connector here (SH is 1 mm pitch: fiddly to crimp and to plug blind);
    # side entry on the right edge under J7 (like J2: pin 1 towards the front), its mouth towards the drag chain
    # like J7's; its transistors and resistors in a column right beside it; R23 (from +3V3) over the In2 +3V3 area
    part(d, "J5", "ph6", {"1": "GND", "2": "AUX_VREF", "3": "AUX_TX_R", "4": "AUX_RX_R", "5": "AUX_RST_N",
                          "6": "AUX_BOOT_N"}, "AUX", pcb=P(EDGE_X, CFG["aux"][1], 90),
         sch=at(106, 64, fields=(1, -5)))
    ax = EDGE_X - 7.6                  # the column, between the DUT power block and J5's pads
    # AUX_VREF is a reference for the DUT's levels, not a supply: 1k (33 Ω until pcba-review N7: a short on the
    # lead was 0.33 W in an 0603, and a DUT's 3.3 V back-powered through it with DUT_5V off)
    R(d, "R23", "1k", "+3V3", "AUX_VREF", pcb=P(45.2, 39.4, 0), sch=at(90.5, 54, rot=90))
    R(d, "R24", "1k", "AUX_TX", "AUX_TX_R", pcb=P(ax, 43.6, 0), sch=at(90.5, 58, rot=90))
    R(d, "R25", "1k", "AUX_RX", "AUX_RX_R", pcb=P(ax, 45.4, 0), sch=at(90.5, 62, rot=90))
    d.wire("J5.2", (98, 63), (98, 54), "R23.2")
    d.wire("R23.1", (87, 54), (87, 52))
    d.tag("+3V3", (87, 52), "up")
    d.wire("J5.3", (97, 64), (97, 58), "R24.2")
    d.wire("J5.4", (96, 65), (96, 62), "R25.2")
    part(d, "Q2", "nfet", {"G": "AUX_RST_CTL", "S": "GND", "D": "AUX_RST_N"}, pcb=P(ax, 50.0, 90), sch=at(86, 69))
    part(d, "Q3", "nfet", {"G": "AUX_BOOT_CTL", "S": "GND", "D": "AUX_BOOT_N"}, pcb=P(ax, 55.6, 90), sch=at(86, 79))
    R(d, "R26", "100k", "AUX_RST_CTL", "GND", pcb=P(ax, 47.2, 0), sch=at(81, 70.5))
    R(d, "R27", "100k", "AUX_BOOT_CTL", "GND", pcb=P(ax, 52.8, 0), sch=at(81, 80.5))
    d.wire("J5.5", (87, 66), "Q2.D")
    d.wire("Q2.G", (78, 69))
    d.tag("AUX_RST_CTL", (78, 69), "left")
    d.wire("J5.6", (95, 67), (95, 76), (87, 76), "Q3.D")
    d.wire("Q3.G", (78, 79))
    d.tag("AUX_BOOT_CTL", (78, 79), "left")
    for net, xy in (("AUX_VREF", (93, 54)), ("AUX_TX_R", (93, 58)), ("AUX_RX_R", (93, 62)), ("AUX_RST_N", (89, 66)),
                    ("AUX_BOOT_N", (88, 76))):
        d.tag(net, xy, "right")

    d.frame("Mounting (M3, matches the carrier standoffs)", 116, 66, 160, 80)
    for i, (x, y) in enumerate(CFG["holes"]):
        part(d, f"H{i + 1}", "hole", {}, "M3", pcb=P(x, y, 0), in_bom=False, sch=at(122 + 9 * i, 73))
    d.notes_at = (6, 52, 60)
    d.note("TPS2553: ILIM 18k → 1.34–1.52 A.  EN is pulled up: DUT_5V is on")
    d.note("  even with no firmware; ~FAULT flags current limit / over-temperature.")
    d.note("INA226 (I2C 0x40) runs from +3V3: it measures the drop across")
    d.note("  R19 (50 mΩ → 1.64 A full scale, Kelvin sense pads); Vbus on Vin-: DUT_5V at the shunt.")
    d.note("AUX: TX/RX through 1k, VREF = +3V3 through 33 Ω (level hint),")
    d.note("  RESET/BOOT open-drain (2N7002, 100k gate pull-downs).")

    # ------------------------------------------------------------------ rack bus: CAN + POS (docs/can.md)
    k = b.sheet("Rack bus", "bus.kicad_sch", "Rack bus: CAN transceiver and POS addressing token")
    k.frame("CAN: TJA1462AT on the row pair (J1.3/4 ↔ J2.4/3, Power sheet); stub ≤ 20 mm, no termination", 6, 6, 70, 32)
    # straddles the In2 VRACK strip: VCC (+5V) and the TXD/RXD pins on the rear side, VIO (+3V3), CANH/CANL and
    # STB on the front side, right above the pair
    part(k, "U11", "can_xcvr", {"TXD": "CAN_TXD", "VSS": "GND", "VDD": "+5V", "RXD": "CAN_RXD", "Vio": "+3V3",
                                "CANL": "CAN_L", "CANH": "CAN_H", "STBY": "GND"}, "TJA1462AT",
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

    k.frame("POS token: in from J1.6, out to J2.1; 10k series + BAT54S clamp on each (VRACK on it costs ≈ 2.5 mA at 28 V)",
            6, 36, 70, 66)
    R(k, "R28", "10k", "POS_IN_CONN", "POS_IN", pcb=P(11.7, PWR_Y + 5.6, 0), sch=at(20, 42, rot=90))
    k.wire((14, 42), "R28.1")
    k.tag("POS_IN_CONN", (14, 42), "left")
    k.wire("R28.2", (40, 42))
    k.tag("POS_IN", (40, 42), "right")
    part(k, "D6", "bat54s", {"A": "GND", "K": "+3V3", "COM": "POS_IN"}, pcb=P(15.4, PWR_Y + 7.4, 0),
         sch=at(28, 46, rot=180))
    k.wire("D6.COM", (28, 42))
    # 470k: driven through the hub's (or the previous node's) 10k and R28, POS_IN reaches 3.17 V (2.75 V with
    # 100k, against the ESP32-S3's 2.475 V VIH: pcba-review N3); undriven, the BAT54S leakage stays below VIL
    R(k, "R29", "470k", "POS_IN", "GND", pcb=P(19.0, PWR_Y + 7.4, 90), sch=at(35, 44.5))
    k.wire("R29.1", (35, 42))
    R(k, "R30", "10k", "POS_OUT", "POS_OUT_CONN", pcb=P(51.8 + DX, PWR_Y + 5.0, 0), sch=at(30, 56, rot=90))
    k.wire((14, 56), "R30.1")
    k.tag("POS_OUT", (14, 56), "left")
    k.wire("R30.2", (40, 56))
    k.tag("POS_OUT_CONN", (40, 56), "right")
    # the output clamp sits by the module (In2 +3V3 there); electrically anywhere on POS_OUT
    part(k, "D7", "bat54s", {"A": "GND", "K": "+3V3", "COM": "POS_OUT"}, pcb=P(44.4, 21.2, 0),
         sch=at(22, 60, rot=180))
    k.wire("D7.COM", (22, 56))
    k.notes_at = (6, 70, 64)
    k.note("CAN (docs/can.md): one bus for the rack, a star from the hub; both terminations sit in the hub.")
    k.note("  250 kbit/s (125 kbit/s fallback).  TJA1462AT (SIC): VCC 5 V, VIO 3.3 V, bus pins −36/+40 V, passive unpowered.")
    k.note("POS: active-high 3.3 V token.  From reset the node holds POS_OUT low; when POS_IN goes high and it has")
    k.note("  no address yet, it answers with its MAC, takes (row, position) from the hub, then raises POS_OUT.")
    k.note("  R29 keeps POS_IN low with no cable; the next node's 100k keeps POS_OUT low before firmware.")

    # ------------------------------------------------------------------ camera (Arducam Mega SPI) and its light
    # J6 stands vertical at the rear right (pin 1 at the rear), east of the antenna band: its lead leaves straight
    # back, ≥ 15 mm beside the module.  Its parts between it and the module: the 33 Ω resistors in a column by the
    # module's side, the PTC, the ESD and the light's FET in a column beside J6's pads
    c = b.sheet("Camera", "cam.kicad_sch", "Camera lead: Arducam Mega SPI and its LEDs")
    c.frame("J6: JST PH 8 to the bay's camera pod (Arducam Mega 3MP SPI + white LEDs), ≈ 50 cm", 6, 6, 120, 60)
    cx, cy = CFG["cam"]
    part(c, "J6", "ph8v", {"1": "CAM_5V", "2": "GND", "3": "CAM_SCK_C", "4": "GND", "5": "CAM_MOSI_C",
                           "6": "CAM_MISO_C", "7": "CAM_CS_C", "8": "LED_K"}, "CAM",
         pcb=P(cx, cy, 270), sch=at(100, 30, fields=(1, -7)))
    for n, net in ((1, "CAM_5V"), (3, "CAM_SCK_C"), (5, "CAM_MOSI_C"), (6, "CAM_MISO_C"), (7, "CAM_CS_C"), (8, "LED_K")):
        c.wire(f"J6.{n}", (92, 26 + n))
        c.tag(net, (92, 26 + n), "left")
    c.wire("J6.2", (84, 28))
    c.wire("J6.4", (84, 30))
    c.wire((84, 28), (84, 31), net="GND")
    c.tag("GND", (84, 31), "down")
    part(c, "F1", "pptc500", {"1": "+5V", "2": "CAM_5V"}, "0.5A", pcb=P(cx - 5.5, cy - 7.2, 90), sch=at(20, 14, rot=90))
    C(c, "C27", "100n", "CAM_5V", "GND", pcb=P(cx - 8.0, cy - 7.2, 90), sch=at(30, 16))
    # SPI: 33 Ω in series at the node end of the lead (a few cm of track from U3: the source, for a 50 cm lead)
    rx, ry = cx - 11.5, cy - 8.2
    R(c, "R31", "33", "CAM_SCK", "CAM_SCK_C", pcb=P(rx, ry, 0), sch=at(50, 24, rot=90))
    R(c, "R32", "33", "CAM_MOSI", "CAM_MOSI_C", pcb=P(rx, ry + 1.8, 0), sch=at(50, 30, rot=90))
    R(c, "R33", "33", "CAM_MISO_C", "CAM_MISO", pcb=P(rx, ry + 3.6, 0), sch=at(50, 36, rot=90))
    R(c, "R34", "33", "CAM_CS", "CAM_CS_C", pcb=P(rx, ry + 5.4, 0), sch=at(50, 42, rot=90))
    # the camera pod (electronics/camera-pod) runs the Mega from 3.3 V, so MISO is 3.3 V; R35 stays a fallback
    # divider for a camera fed 5 V: R33 → 330 and fit R35 (3.37 V)
    R(c, "R35", "680", "CAM_MISO", "GND", pcb=P(rx, ry + 7.2, 0), sch=at(40, 40), dnp=True)
    # CS pull-up over the In2 +3V3 area under the module's corner (the resistor row sits over +5V)
    R(c, "R37", "10k", "CAM_CS", "+3V3", pcb=P(36.6, 40.2, 0), sch=at(40, 54))
    part(c, "U12", "esd", {"1": "CAM_SCK_C", "6": "CAM_SCK_C", "3": "CAM_MOSI_C", "4": "CAM_MOSI_C",
                           "5": "CAM_5V", "2": "GND"}, pcb=P(cx - 6.4, cy - 1.4, 0), sch=at(76, 22))
    part(c, "U13", "esd", {"1": "CAM_MISO_C", "6": "CAM_MISO_C", "3": "CAM_CS_C", "4": "CAM_CS_C",
                           "5": "CAM_5V", "2": "GND"}, pcb=P(cx - 6.4, cy + 3.4, 0), sch=at(76, 38))
    # the light: 2–4 white 5 V LEDs (a strip segment, its own resistors) from CAM_5V to LED_K, ≤ 150 mA
    part(c, "Q4", "nfet_ll", {"G": "CAM_LED", "S": "GND", "D": "LED_K"}, pcb=P(cx - 6.0, cy + 7.8, 0), sch=at(80, 52))
    R(c, "R36", "100k", "CAM_LED", "GND", pcb=P(cx - 6.0, cy + 11.2, 0), sch=at(70, 54))
    c.notes_at = (6, 64, 114)
    c.note("Lead pinout: 1 CAM_5V · 2 GND · 3 SCK · 4 GND · 5 MOSI · 6 MISO · 7 CS · 8 LED_K (the LEDs' cathode side).")
    c.note("SPI2 through the GPIO matrix, mode 0, 4 MHz (2 MHz fallback): IO11 SCK, IO10 MOSI, IO9 MISO, IO8 CS (10k")
    c.note("  pull-up: deselected before firmware), IO7 the light (R36 holds it off at boot; LEDC PWM ≥ 20 kHz or on/off).")
    c.note("CAM_5V through F1 (0.5 A PTC): the camera ≈ 120 mA + the LEDs ≤ 150 mA.  USBLC6s on the lead side of the 33 Ω.")
    c.note("The camera pod board runs the Mega from 3.3 V (its own AMS1117): MISO is 3.3 V and R35 stays unpopulated.")
    c.note("  For a camera fed 5 V that drives MISO at 5 V instead: R33 → 330 Ω and fit R35 (680 Ω): 3.37 V.")
    return b


NETCLASSES = [
    {"name": "Power", "clearance": 0.15, "track_width": 0.6, "via_diameter": 0.8, "via_drill": 0.4,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 1,
     "_patterns": ["*VRACK", "*VIN", "+5V", "*DUT_5V_SW", "*DUT_5V", "*BUCK_SW", "*CAM_5V"]},
    {"name": "USB", "clearance": 0.15, "track_width": 0.2, "via_diameter": 0.6, "via_drill": 0.3,
     "diff_pair_width": 0.25, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 2,
     "_patterns": ["*_DP", "*_DN"]},
]
