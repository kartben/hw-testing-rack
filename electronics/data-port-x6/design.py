"""DATA ×6 v1.0 — the porte-revues bays' drawer board: six USB-C behind a hub, each switched and measured.

The power half of the DATA ×4 v2 (electronics/data-port-x4-v2), widened to six ports for the porte-revues bays.
Their boards stand in a slotted tray with no Dupont lead, so this board has no pin header, crosspoint or
co-processor; the DATA ×4 v2 keeps the logic (the user, 2026-10-31: "une carte 4x logic et une 6x purement
power").

* six vertical USB-C at a 15.5 mm pitch (the plug's overmould sets it), standing (their slot upright), each with its
  TPS2553-1, its INA226, its USBLC6 in flow-through and Rp 56k on each CC, as the v2's;
* the USB2517I hub (ports 1–6, the 7th unused) with its crystal and reset, the lead's I²C isolation, a 3.3 V LDO;
* one TCA9535 (0x20) for the six ports' EN and FAULT_N, its four spare pins pulled down;
* all its 5 V made here from the rack's 20 V, which the node switches onto the PH 8 lead's pin 8 (VIN; the user,
  2026-11-01: "20v dans la nappe"): two LMR51625, +5V_A for ports 1–3, +5V_B for ports 4–6 and the 3.3 V LDO (the
  hub, the expander, the INA226s), never in parallel (the power plane's +5V split left / right).  The node
  power-cycles the whole board by switching VIN.  The PH 8 lead is the v2's, pin for pin.

The board stands where the v2 stands (config/rack.yaml › pcb.data_port_x6), held at both ends by the cradle;
every part JLC places on the front face (Economic, one side), the two leads' connectors soldered by hand on the
rear face.
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
sys.path.insert(0, str(HERE.parents[1] / "tools"))

from catalog import C, R, part  # noqa: E402
from eda import Board  # noqa: E402

import rackcfg  # noqa: E402

RACK = rackcfg.load()
CFG = RACK.raw["pcb"]["data_port_x6"]
W, H = CFG["size"]
LAYERS = int(os.environ.get("X6_LAYERS", CFG["layers"]))
TOP_Z = CFG["top_z"]                # KiCad x = drawer x − x0, y = top_z − drawer z (y = 0 the top edge)
CRADLE = CFG["cradle"]              # each end's band in the cradle's slots: no parts on either face
_NW, _ND = CFG["notches"]["size"]
NOTCHES = [(x - CFG["x0"] - _NW / 2, x - CFG["x0"] + _NW / 2, H - _ND) for x in CFG["notches"]["x"]]
CORNER = CFG["corner_notch"]        # the bottom-right corner's cut (width, height): none at 100 mm
USBS = CFG["usb"]                   # board x of the six vertical USB-C
USB_ROT = CFG["usb_rot"]            # each one's turn: all six standing (90), as conn_pairs() draws them
# the receptacles' two pad columns (GCT USB4145's land, turned 90°): ±1.485 mm off its axis, 0.5 mm pitch
USBC_COL = 1.485
assert USB_ROT == [90] * 6, "conn_pairs() draws the six USB-C standing"
# each port's cluster, its USBLC6 and its hub pair's drop: 2.2 mm west of its receptacle.  The receptacles moved east
# so that USB-C 1 stands with its USBLC6 beside it, clear of the cradle's band (2026-11-01); the clusters stayed,
# USB-C 6's pull-ups and INA226 would reach the east band
COLS = [x - 2.2 for x in USBS]
USB_Y = TOP_Z - CFG["usb_z"]        # their axis (z 11, the port wall's openings)
LEAD = (CFG["lead"][0], TOP_Z - CFG["lead"][1] + 7.0)      # J1's pin 1, its pins running up
# The placement (KiCad mm): the six ports along the bottom, each its power cluster over its USB-C; over them the
# corridor the hub's pairs run in; along the top converter A (west), the expander, the hub (middle: its pairs fan
# out both ways), the 3.3 V LDO, converter B (east); the lead's connector at the east end, over the rear cable
# window, J1 under converter B
HX, HY = 50.0, 32.0                 # the hub, turned 90°: DN pins south, down into the corridor; DN3 over USB-C 4
XT = (HX - 8.9, HY + 1.75)          # its 24 MHz crystal
EXP = (30.0, 20.0)                  # the TCA9535 (EN and FAULT_N of the six ports), west of the hub
LDO = (68.8, 4.6)                   # U3, the 3.3 V LDO, between the hub and converter B, near J1.8
BULK = (80.5, 24.0)                 # VIN's 33 µF (7.7 mm tall: over the port wall's 16 mm), west of J1.8
CL_Y = 46.7                         # each port's power cluster: its frame's top
PWR_SPLIT = 54.6                    # the power plane: +3V3 above, +5V_A / +5V_B under (MID_X between them)
MID_X = 50.0
# each USB-C's USBLC6, west of its receptacle on its axis: 2–6 between two clusters (the hub's pair comes straight
# down to it), USB-C 1's between the cradle's band and its receptacle (ESD1)
ESD_PX = {1: USBS[0] - 5.7, **{n: COLS[n - 1] - (6.9 if n == 2 else 7.4) for n in range(2, 7)}}
ESD1 = (ESD_PX[1], USB_Y)
# the hub's pairs (hs_pairs()): each one's lane in the corridor under the hub (its centreline; USB-C 2–3 west,
# 5–6 east, 4 straight down), and its way down between the cluster west of it and its own to its USBLC6 (D−'s
# line; D+ 0.4 mm east): clear of the R(k+2)/R(k+3) pads west of it and of its USBLC6's pin 4 and 5 pads
LANES = {2: HY + 9.0, 3: HY + 10.1, 5: HY + 10.1, 6: HY + 9.0}
DROP_DN = {n: ESD_PX[n] - 2.2 for n in range(2, 7)}
# the two 5 V converters: the bay node's LMR51625 block (bay-node/design.py) at an offset, the node's own layout,
# along the top edge: A in the top-left corner, B in the top-right one (each over its plane tongue, down the
# cradle's band at its end); their feedback dividers (100k over 18k) beside each converter's west side
BUCKS = {"A": (2.4, -39.7), "B": (74.0, -39.7)}
FB_R = {key: ((dx + 4.5, 3.1, 270), (dx + 4.5, 6.1, 270)) for key, (dx, _) in BUCKS.items()}
J1_ROT = 90


# The hub crystal's block, the v2's (the layout review, 2026-10-28): its lines drawn on F.Cu with no via, its
# keep-out and DRC rule; relative to HX, HY and XT, so it carries over as it is
def xtal_block():
    """The hub's crystal Y1, drawn (the layout review, 2026-10-28): XI and XO on F.Cu only, no via, every end on
    its pad's centre.  XI from Y1's south-east pad east through R10 to pin 61; XO from its north-west pad, under the
    case between the east pads (a GND pad above, XI's below, 0.4 mm each), through R10 to pin 60: the two run east
    0.5 mm apart into the pins.  C4 under XI's pad, its GND on Y1's south-west GND via; C5 over XO's, with its own;
    Y1's north-east GND pad with its own; the F.Cu and B.Cu GND pours fill round it all (no other net there:
    XTAL_KEEP).  Also drawn, south-east of it: pin 62's HUB_1V8PLL to C10, its 100 nF right by the pin, and on to
    C8, its 4.7 µF beside it (each its pad 1 up, its GND via below); pin 63's RBIAS down the pins' side, past
    pin 64's via, to R1 (pad 1 up); no via on either (the router gave RBIAS two)."""
    x, y = XT
    xi, xo = (x + 0.85, y + 1.1), (x - 0.85, y - 1.1)          # Y1.1, Y1.3
    r_xo, r_xi = (x + 2.3, y - 0.26), (x + 2.3, y + 0.76)       # R10.1, R10.2 (turned 270°: pad 1 up)
    p60, p61 = (HX - 4.412, HY + 1.75), (HX - 4.412, HY + 2.25)          # U1.60 XO, U1.61 XI
    c4, c5 = (x + 0.85, y + 2.65), (x - 0.85, y - 2.62)         # C4.1, C5.1
    tracks = [("XI", "F.Cu", 0.127, [xi, (r_xi[0] - 0.34, xi[1]), r_xi]),
              ("XI", "F.Cu", 0.127, [r_xi, (r_xi[0] + 0.26, p61[1]), p61]),
              ("XI", "F.Cu", 0.127, [xi, c4]),
              ("XO", "F.Cu", 0.127, [xo, (x + 0.25, y), (r_xo[0] - 0.26, y), r_xo]),
              ("XO", "F.Cu", 0.127, [r_xo, (r_xo[0] + 0.26, p60[1]), p60]),
              ("XO", "F.Cu", 0.127, [xo, c5])]
    gnd = [((x + 0.85, y - 1.1), (x + 0.85, y - 2.25)),        # Y1.2 (north-east), up
           ((x - 0.85, y + 1.1), (x - 0.85, y + 2.25)),        # Y1.4 (south-west), down
           ((x - 0.85, y - 3.58), (x - 0.85, y - 4.35))]        # C5.2, up
    tracks += [("GND", "F.Cu", 0.25, [a, b]) for a, b in gnd]
    tracks.append(("GND", "F.Cu", 0.25, [(x - 0.11, y + 2.65), gnd[1][1]]))     # C4.2 to Y1.4's via
    p62, p63 = (HX - 4.412, HY + 2.75), (HX - 4.412, HY + 3.25)
    c10, c8, r1 = (HX - 5.66, HY + 3.45), (HX - 6.8, HY + 4.38), (HX - 5.75, HY + 6.09)       # their pads 1
    tracks += [("HUB_1V8PLL", "F.Cu", 0.127, [p62, (c10[0] + 0.7, p62[1]), c10]),
               ("HUB_1V8PLL", "F.Cu", 0.127, [c10, (c10[0] - (c8[1] - c10[1]), c8[1]), c8]),
               ("RBIAS", "F.Cu", 0.127, [p63, (HX - 4.92, p63[1]), (HX - 5.12, p63[1] + 0.2), (HX - 5.12, HY + 5.2),
                                         (r1[0], HY + 5.83), r1])]
    # and C10's, C8's and R1's GND dog-bones, down (the automatic ones, kept further from drawn tracks than from
    # routed ones, would not fit)
    gnd += [((c10[0], HY + 4.41), (c10[0], HY + 5.05)), ((c8[0], HY + 5.34), (c8[0], HY + 5.98)),
            ((r1[0], HY + 7.11), (r1[0], HY + 7.73))]
    tracks += [("GND", "F.Cu", 0.25, [a, b]) for a, b in gnd[-3:]]
    return tracks, [("GND", *b, 0.5, 0.3) for _, b in gnd]


# the hub crystal's block (xtal_block()): Y1, its caps, R10 and the two lines to the pins; no other net's track or
# via on F.Cu or B.Cu (the router's "core:" area here, XTAL_RULE for DRC), In1 solid GND under it.  It leaves USB-C
# 1's pair room down its west side, and pins 62-64 (HUB_1V8PLL, RBIAS, +3V3) a way down east of C4
XTAL_KEEP = ([(XT[0] + dx, XT[1] + dy) for dx, dy in
              ((-1.6, -4.65), (-0.1, -4.65), (-0.1, -2.55), (1.85, -2.55), (1.85, -0.75))] +
             [(HX - 4.88, XT[1] - 0.75), (HX - 4.88, XT[1] + 0.85)] +
             [(XT[0] + dx, XT[1] + dy) for dx, dy in
              ((2.85, 0.85), (2.85, 1.2), (1.85, 1.2), (1.85, 2.15), (1.4, 2.15), (1.4, 3.2), (-1.3, 3.2),
               (-1.3, 2.55), (-2.0, 2.55), (-2.0, -2.35), (-1.6, -2.35))])
XTAL_RULE = """
(rule "crystal Y1: XI, XO and GND only over its parts"
	(condition "(A.Type == 'Track' || A.Type == 'Via') && A.NetName != '/Hub/XI' && A.NetName != '/Hub/XO' && A.NetName != 'GND' && (A.intersectsCourtyard('Y1') || A.intersectsCourtyard('C4') || A.intersectsCourtyard('C5') || A.intersectsCourtyard('R10'))")
	(constraint disallow track via))
"""

# The layout review's checks as rules (2026-11-01), generated from NETCLASSES (electronics/tools/netrules.py): the
# supplies' widths (Supply, Power, Port: "_min_width"), the hub's fine-pitch fan-out aside (MIN_WIDTH_EXCEPT: its
# 1.8 V pins' lines neck down at the pads, and HUB_1V8PLL's whole 3 mm, drawn in the crystal's block from pin 62 to
# C10 and C8 between XI and RBIAS, is 0.127); and the enables, faults and resets (the Sensitive class) kept 3 × the
# USB lines' width off them, against a coupled spike that would switch a port off or reset the hub
MIN_WIDTH_EXCEPT = {"courtyards": ["U1"], "nets": ["HUB_1V8PLL"], "why": "in the hub's fan-out"}

# Where the printed cradle (mechanical/parts/x4_cradle.scad) holds the board, no part, its courtyard included (DRC:
# footprint keep-outs, pcbgen's "parts:" rule areas, copper free to pass): each end's band in the slots on both
# faces, and on the front face each T-head's bar, 0.3 mm round it: from notches.tee off its notch's centre, up to
# 0.5 mm under the notch's depth (the cradle's own numbers)
_TEE = (CFG["notches"]["tee"][0] - 0.3, CFG["notches"]["tee"][1] + 0.3)
CRADLE_KEEPOUTS = [
    {"name": f"cradle-{end}", "footprints": True, "layers": ["F.Cu", "B.Cu"],
     "poly": [(x0, 0), (x0 + CRADLE, 0), (x0 + CRADLE, H), (x0, H)]}
    for end, x0 in (("w", 0.0), ("e", W - CRADLE))] + [
    {"name": f"t-head-{i}", "footprints": True, "layers": ["F.Cu"],
     "poly": [(xc + _TEE[0], H - _ND + 0.2), (xc + _TEE[1], H - _ND + 0.2), (xc + _TEE[1], H), (xc + _TEE[0], H)]}
    for i, xc in enumerate((x0 + x1) / 2 for x0, x1, _ in NOTCHES)]

def P(x, y, rot=0, side="top"):
    """A placement on the board (KiCad: y = 0 the top edge); the front face is the top side."""
    return {"x": x, "y": y, "rot": rot, "side": side}


def at(x, y, rot=0, mirror="", fields=None):
    """Schematic position in 0.1" grid units."""
    d = {"x": x, "y": y, "rot": rot}
    if mirror:
        d["mirror"] = mirror
    if fields is not None:
        d["fields"] = fields
    return d


# INA226 address straps (A1, A0) per port: 0x41, 0x43, 0x44, 0x45, 0x47, 0x4C (the node's own is 0x40; no SDA
# strap, as the v2)
INA_ADDR = [("GND", "+3V3"), ("GND", "SCL"), ("+3V3", "GND"), ("+3V3", "+3V3"), ("+3V3", "SCL"), ("SCL", "GND")]
INA_HEX = [0x41, 0x43, 0x44, 0x45, 0x47, 0x4C]
# the TCA9535's 16 lines: each port's EN and FAULT_N, ports 1–4 on P00–P07, 5–6 on P10–P13; P14–P17 spare (pulled
# down, the firmware sets them as outputs, low)
EXP_LINES = {f"P{(2 * (n - 1)) // 8}{(2 * (n - 1)) % 8 + i}": f"PORT{n}_{sig}"
             for n in range(1, 7) for i, sig in enumerate(("EN", "FLT_N"))}
ARRAYS = {"10k": ("4D02WGJ0103TCE", "C25725")}
# The bring-up test points (the DFT rule): bare pads on the rear face, named on B.SilkS under each; 1.5 mm on GND and
# the rails, 1.0 mm on signals; each > 2 mm from the THT pads, clear of the cradle's ends and the push band.
# ref: (net, name, pad Ø, x, y); each sheet places its own (testpoints())
# each port's VBUS test pad on one of its vias between its cluster and its USB-C (drawn: drawn()), USB-C 2's on a via
# of its own at its VBUS line's corner (the design review, 2026-11-01)
VBUS_TP = {1: (7.594, 53.602), 2: (19.045, 55.75), 3: (37.458, 53.602), 4: (52.334, 51.945), 5: (68.844, 53.602),
           6: (85.281, 53.67)}
TPS = {
    # the supplies: VIN, +5V_A, +5V_B, +3V3, with GND
    "TP7": ("+3V3", "+3V3", 1.5, LDO[0], 10.6), "TP8": ("GND", "GND", 1.5, 17.0, 15.6),
    "TP9": ("+5V_A", "+5V_A", 1.5, 20.0, 10.9), "TP41": ("+5V_B", "+5V_B", 1.5, 90.5, 10.6),
    "TP42": ("VIN", "VIN", 1.5, 78.6, 22.6), "TP43": ("GND", "GND", 1.5, 81.6, 22.6),
    # the hub's reset and core rail, with a GND
    "TP20": ("HUB_RST_N", "HUB RST", 1.0, HX - 0.5, HY - 14.0), "TP21": ("GND", "GND", 1.5, HX + 3.5, HY - 14.9),
    "TP22": ("HUB_1V8", "1V8", 1.5, HX + 5.0, HY + 4.25),
    # the board side of the lead's I²C, with a GND: a row under J1, 2 mm clear of its housing (rear face)
    "TP24": ("SDA", "SDA", 1.0, LEAD[0] - 0.5, LEAD[1] + 5.5),
    # (its GND under SDA's: at the row's east end its courtyard reached 0.29 mm into the east cradle band, and the
    # row's tracks and vias leave no nearer spot)
    "TP25": ("SCL", "SCL", 1.0, LEAD[0] + 2.0, LEAD[1] + 5.5), "TP26": ("GND", "GND", 1.5, LEAD[0] - 0.5, LEAD[1] + 8.55),
    # GND by the expander
    "TP27": ("GND", "GND", 1.5, EXP[0] - 4.0, EXP[1] + 2.6),
    # each port's FAULT_N (port(): TP{k + 1}) by its switch
    **{f"TP{100 * n + 1}": (f"PORT{n}_FLT_N", f"FLT{n}", 1.0, COLS[n - 1] + 4.0, CL_Y + 6.5) for n in range(1, 7)},
    # its VBUS (port(): TP{k + 2})
    **{f"TP{100 * n + 2}": (f"PORT{n}_VBUS", f"VBUS{n}", 1.5, *VBUS_TP[n]) for n in range(1, 7)},
    # GND along the ports (the others all sit at y 44 or above): a probe's ground for the VBUS and FAULT_N pads, each
    # clear of the clusters' fan-out vias
    "TP45": ("GND", "GND", 1.5, 21.9, 54.4), "TP46": ("GND", "GND", 1.5, 49.4, 54.9),
    "TP47": ("GND", "GND", 1.5, 80.4, 53.9),
}


def testpoints(s, refs, title, x0, y0, per_row=7, pitch=12):
    """The sheet's bring-up test points (TPS) in a frame of their own at (x0, y0), per_row to a row: inside the
    sheet's paper (the layout review: the DATA ×4 v2's sat off its A2 page)"""
    rows = (len(refs) + per_row - 1) // per_row
    s.frame(title, x0, y0, x0 + 10 + pitch * min(per_row, len(refs)), y0 + 6 + 14 * rows)
    for i, ref in enumerate(refs):
        net, _, d, x, y = TPS[ref]
        part(s, ref, "testpad" if d > 1.2 else "testpad1", {"1": net}, pcb=P(x, y, 0, "bottom"), in_bom=False,
             sch=at(x0 + 8 + pitch * (i % per_row), y0 + 14 + 14 * (i // per_row)))


def rail(s, net, pins, dy, d="up"):
    """Pins in one row ("REF.PIN") wired dy units out to a common line, tagged once at its first end."""
    for pin in pins:
        s.wire(pin, (pin, 0, dy))
    if len(pins) > 1:
        s.wire((pins[0], 0, dy), (pins[-1], 0, dy), net=net)
    s.tag(net, (pins[0], 0, dy), d)


def rarray(s, ref, value, pairs, pcb, sch=None):
    """A 4 × 0402 array: pairs = [(a, b)] × 4, resistor k between pins k and 9 − k."""
    mpn, lcsc = ARRAYS[value]
    conns = {}
    for k, (a, b) in enumerate(pairs, 1):
        conns[str(k)], conns[str(9 - k)] = a, b
    return part(s, ref, "rarray", conns, value, pcb=pcb, fields={"MPN": mpn, "LCSC": lcsc}, sch=sch)


def ina_x(n: int) -> float:
    """Port n's INA226 (board x), its 100 nF over it and its EN and FAULT_N pull-ups 2.24 mm east of it: those stand
    0.77 mm from the next pair's D− line (the Sensitive class 0.75 mm off USB: netrules.py); port 1's cluster sits
    0.1 mm nearer its drop than the others to theirs"""
    return COLS[n - 1] - (4.4 if n == 1 else 5.0) + 7.51 - (0.16 if n == 1 else 0.07)


def supply(n: int) -> str:
    """Port n's 5 V: +5V_A for ports 1–3, +5V_B for ports 4–6 (and the 3.3 V LDO: the hub's)"""
    return "+5V_A" if n <= 3 else "+5V_B"


# ----------------------------------------------------------------------------------------------- ports
def low_parts(n: int) -> dict:
    """Each port's parts by its receptacle, {name: (x, y, rot)}: the VBUS LED and its 1k lying over the receptacle,
    under the shunt and the INA226; its VBUS 22 µF and the CC1 and CC2 56k in a row under it, over the board's
    edge, ending 2 mm east of its axis: the front face stays free of parts 7 wide × 6 tall round each comb notch,
    where the cradle's T-heads come up (east of USB-C 2 and 4: their rows stop 0.06 mm short of it).  Nothing else
    east of a receptacle: the next port's hub pair comes down there."""
    cx = USBS[n - 1]
    return {"r1k": (cx - 1.9, USB_Y - 5.85, 0), "led": (cx + 1.2, USB_Y - 5.9, 180),
            "c22": (cx + 0.25, USB_Y + 6.1, 0), "cc1": (cx - 4.55, USB_Y + 6.1, 0), "cc2": (cx - 2.5, USB_Y + 6.1, 0)}


def port(b: Board, n: int):
    cx = USBS[n - 1]
    k = 100 * n
    p = f"PORT{n}_"
    s = b.sheet(f"Port {n}", f"port{n}.kicad_sch", f"USB-C {n}: switch, current sense, ESD")
    s.paper = "A3"
    sw, sh, ina, usb, esd = f"U{k + 1}", f"R{k + 6}", f"U{k + 2}", f"J{k + 1}", f"U{k + 3}"
    v5 = supply(n)
    s.frame(f"Port {n} power: {v5} → TPS2553-1 → {p}5V_SW → 100 mΩ shunt → {p}VBUS, the INA226 across the shunt",
            6, 10, 104, 44)
    s.tag(v5, (20, 18), "up")
    s.wire((20, 18), (20, 21), f"{sw}.IN")
    # the cluster in a 12 × 8 mm frame over the port's USB-C (x0, y0 its corner), the v2's; port 1's 0.6 mm east, its
    # pair coming down the west edge past its ILIM resistor (upright there: clear of the cradle's band)
    x0, y0 = COLS[n - 1] - (4.4 if n == 1 else 5.0), CL_Y
    part(s, sw, "vbus_sw_latch", {"IN": v5, "GND": "GND", "EN": p + "EN", "~{FAULT}": p + "FLT_N",
                                  "ILIM": p + "ILIM", "OUT": p + "5V_SW"}, pcb=P(x0 + 2.45, y0 + 2.2, 180),
         sch=at(30, 22, fields=(-4, -4)))
    C(s, f"C{k + 1}", "1u", v5, "GND", size="0402", pcb=P(x0 + 5.13, y0 + 2.9, 90), sch=at(15, 24))
    s.wire(f"C{k + 1}.1", (15, 21), (20, 21))
    # 45.3k: 524 mA at the least, so a DUT drawing its full 500 mA never trips it (47k's 505 mA fell to 499.7 with
    # its 1 %); no JLC basic part between 39k and 47k, so an extended one
    R(s, f"R{k + 1}", "45.3k", p + "ILIM", "GND", size="0402",
      pcb=P(x0 - 0.97, y0 + 2.2, 180) if n > 1 else P(x0 - 0.5, y0 + 2.2, 90), sch=at(22, 28),
      fields={"LCSC": "C2933099", "MPN": "FRC0402F4532TS", "Manufacturer": "FOJAN"})
    s.wire(f"{sw}.ILIM", (22, 24), f"R{k + 1}.1")
    # the port is off until the node switches it on
    R(s, f"R{k + 2}", "10k", p + "EN", "GND", size="0402", pcb=P(ina_x(n) + 2.24, y0 + 3.65, 90), sch=at(14, 36))
    R(s, f"R{k + 3}", "10k", "+3V3", p + "FLT_N", size="0402", pcb=P(ina_x(n) + 2.24, y0 + 5.6, 90),
      sch=at(40, 36))
    testpoints(s, [f"TP{k + 1}", f"TP{k + 2}"], "Test points (rear face): FAULT_N, VBUS", 108, 62)
    part(s, sh, "shunt100m", {"1": p + "5V_SW", "4": p + "VBUS", "2": p + "SNS_P", "3": p + "SNS_N"},
         "100m", pcb=P(x0 + 2.77, y0 + 5.4, 0), sch=at(46, 23))
    s.wire(f"{sw}.OUT", f"{sh}.1")
    a1, a0 = INA_ADDR[n - 1]
    part(s, ina, "ina226", {"VS": "+3V3", "GND": "GND", "A1": a1, "A0": a0, "SDA": "SDA", "SCL": "SCL",
                            "~{Alert}": None, "Vin+": p + "SNS_P", "Vin-": p + "SNS_N", "Vbus": p + "SNS_N"},
         pcb=P(ina_x(n), y0 + 4.6, 90), sch=at(66, 24, fields=(-9, -7)))
    s.wire(f"{sh}.2", (52, 22), (52, 25), f"{ina}.Vin+")
    s.wire(f"{sh}.3", (50, 24), (50, 26), f"{ina}.Vin-")
    s.wire(f"{sh}.4", (46, 33), (60, 33))
    s.tag(p + "VBUS", (60, 33), "right")
    # By the receptacle: VBUS's bulk capacitor, the CC resistors, the VBUS LED and its 1k (on the switched 5 V before
    # the shunt: the INA226 doesn't count it): low_parts()
    lp = low_parts(n)
    C(s, f"C{k + 2}", "22u", p + "VBUS", "GND", size="0805", pcb=P(*lp["c22"]), sch=at(55, 35.5))
    s.wire(f"C{k + 2}.1", (55, 33))
    C(s, f"C{k + 3}", "100n", "+3V3", "GND", size="0402", pcb=P(ina_x(n) + 0.52, y0 + 0.9, 180), sch=at(80, 18))
    R(s, f"R{k + 14}", "1k", p + "5V_SW", p + "LED_A", size="0402", pcb=P(*lp["r1k"]),
      sch=at(84, 30, rot=90))
    part(s, f"D{k + 1}", "led_g", {"A": p + "LED_A", "K": "GND"}, pcb=P(*lp["led"]),
         sch=at(94, 30, rot=180))
    s.wire(f"R{k + 14}.2", f"D{k + 1}.A")

    s.frame(f"USB-C {n} (source): Rp 56k on each CC; USBLC6 in flow-through (connector side | hub side)",
            6, 50, 104, 100)
    part(s, usb, "usbc_vg", {"VBUS": p + "VBUS", "GND": "GND", "CC1": p + "CC1", "CC2": p + "CC2",
                             "D+": p + "CONN_DP", "D-": p + "CONN_DN", "SBU1": None, "SBU2": None,
                             "SHIELD": "GND"}, f"PORT{n}", pcb=P(cx, USB_Y, USB_ROT[n - 1]),
         sch=at(50, 76, fields=(-8, -11)))
    s.wire(f"{usb}.A7", f"{usb}.B7")
    s.wire(f"{usb}.A6", f"{usb}.B6")
    R(s, f"R{k + 4}", "56k", p + "VBUS", p + "CC1", size="0402", pcb=P(*lp["cc1"]), sch=at(62, 64.5))
    R(s, f"R{k + 5}", "56k", p + "VBUS", p + "CC2", size="0402", pcb=P(*lp["cc2"]), sch=at(66, 64.5))
    s.wire(f"{usb}.CC1", (62, 72), f"R{k + 4}.2")
    s.wire(f"{usb}.CC2", (66, 73), f"R{k + 5}.2")
    # The USBLC6 west of the receptacle, turned 180°: pins 1/3 east to it, 6/4 west, where the hub's pair comes
    # straight down between two clusters (USB-C 1's down the board's west edge).  Its VBUS 100 nF right over its pin
    # 5.  ESD_PX: each pair's way down between its pins' pads and the cluster west of it
    ex_ = (ESD_PX[n], USB_Y, 180)
    part(s, esd, "esd", {"1": p + "CONN_DN", "6": p + "DN", "3": p + "CONN_DP", "4": p + "DP", "5": v5,
                         "2": "GND"}, pcb=P(*ex_), sch=at(84, 76))
    s.wire(f"{usb}.B7", f"{esd}.1")
    s.wire(f"{usb}.A6", f"{esd}.3")
    # its VBUS 100 nF over it, its supply pad on the body's centre line: VBUS (pin 5) runs under the body and up
    # between the pin rows into it (drawn in drawn())
    cap = (ex_[0] + 0.48, ex_[1] - 2.3)
    C(s, f"C{k + 4}", "100n", v5, "GND", size="0402", pcb=P(*cap, 0), sch=at(96, 76))

    s.notes_at = (108, 50, 50)
    hp = n - 1 if n > 1 else 6
    s.notes = [f"Port {n} = hub port {hp}, busid 1-1.{hp}; supplied by {v5}.",
               f"INA226 at 0x{INA_HEX[n - 1]:02x}; EN and FAULT_N on the TCA9535 U2 (0x20).",
               "ILIM 45.3k: 524 / 577 / 638 mA min / typ / max (TI SLVS841G §8.5.1 eq. 1–3), 519–644 mA with the",
               "  resistor's 1 %; the -1 latches off after 7.5 ms in limit, FAULT_N flags it.",
               "INA226 Vbus on the shunt's load-side sense pad (= VBUS).",
               "EN pulled down: the port stays off until the node switches it on.",
               "Source only (Rp from the switched VBUS); a back-feeding source trips the TPS2553 (latched)."]


# ------------------------------------------------------------------------------------------ 20 V → 5 V
def power_sheet(b: Board):
    s = b.sheet("Power", "power.kicad_sch", "20 V input, two 5 V converters")
    s.paper = "A2"
    s.frame("VIN: the rack's 20 V, switched by the node (its eFuse), from the PH 8 lead's pin 8 (J1, sheet Hub)",
            6, 10, 62, 50)
    s.part("#FLG08", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "VIN"}, in_bom=False, on_board=False, sch=at(28, 18))
    # the input's bulk against a hot plug's overshoot (the node's lead is ≈ 50 cm, the converters' ceramics alone
    # ring), right by J1.8, before either converter's 10 µF
    part(s, "C60", "cap33u50", {"1": "VIN", "2": "GND"}, "33u", pcb=P(*BULK, 0),
         sch=at(40, 30))
    # EN 100k/10k, as the node's: both converters start above 13.5 V typ. (15.1 V at worst) and stop below 10.8 V;
    # by converter B
    R(s, "R50", "100k", "VIN", "BUCK_EN", size="0402", pcb=P(76.4, 10.6, 90), sch=at(29, 41.5))
    R(s, "R51", "10k", "BUCK_EN", "GND", size="0402", pcb=P(77.5, 10.6, 90), sch=at(29, 48.5))
    s.wire("R50.2", "R51.1")
    for i, (key, out, x0) in enumerate((("A", "+5V_A", 70), ("B", "+5V_B", 140))):
        dx, dy = BUCKS[key]
        u, cb, lx, fb = f"U{13 + i}", f"BUCK{key}_CB", f"BUCK{key}_SW", f"BUCK{key}_FB"
        c0, r0 = 61 + 10 * i, 52 + 2 * i
        s.frame(f"{out}: LMR51625, synchronous, 1.1 MHz, 2.5 A (the bay node's block; TI SLUSF64B)",
                x0 - 4, 10, x0 + 64, 50)
        s.tag("VIN", (x0 + 2, 16), "up")
        s.wire((x0 + 2, 16), (x0 + 25, 16), (x0 + 25, 23), f"{u}.VIN")
        C(s, f"C{c0}", "10u", "VIN", "GND", size="1206", pcb=P(8 + dx, 48.8 + dy, 0), sch=at(x0 + 6, 19.5))
        C(s, f"C{c0 + 1}", "10u", "VIN", "GND", size="1206", pcb=P(8 + dx, 51.4 + dy, 0), sch=at(x0 + 10, 19.5))
        C(s, f"C{c0 + 2}", "100n", "VIN", "GND", pcb=P(8 + dx, 46.6 + dy, 0), sch=at(x0 + 14, 19.5))
        for c_, x in ((f"C{c0}", 6), (f"C{c0 + 1}", 10), (f"C{c0 + 2}", 14)):
            s.wire((x0 + x, 16), f"{c_}.1")
        s.tag("BUCK_EN", (x0 + 19, 22), "left")
        s.wire((x0 + 19, 22), (x0 + 23, 22), (x0 + 23, 25), f"{u}.EN")
        part(s, u, "buck25", {"VIN": "VIN", "EN": "BUCK_EN", "CB": cb, "SW": lx, "FB": fb, "GND": "GND"},
             pcb=P(8 + dx, 44 + dy, 0), sch=at(x0 + 30, 24, fields=(-4, -4)))
        C(s, f"C{c0 + 3}", "100n", cb, lx, pcb=P(9.6 + dx, 41.5 + dy, 0), sch=at(x0 + 41.5, 19, rot=90))
        s.wire(f"{u}.CB", (x0 + 36, 23), (x0 + 36, 19), f"C{c0 + 3}.1")
        s.wire(f"C{c0 + 3}.2", (x0 + 43, 24))
        # 4.7 µH rated 75 V (the 28 V EPR rail ahead; the FXL0630's 30 V would not do), on the same footprint
        part(s, f"L{2 + i}", "buck_l47_75v", {"1": lx, "2": out}, "4.7u", pcb=P(15.7 + dx, 44 + dy, 0),
             sch=at(x0 + 47.5, 24, rot=90))
        s.wire(f"{u}.SW", (x0 + 43, 24), f"L{2 + i}.1")
        s.wire(f"L{2 + i}.2", (x0 + 62, 24))
        s.tag(out, (x0 + 62, 24), "up")
        for j, x in enumerate((50, 54, 58)):
            C(s, f"C{c0 + 4 + j}", "22u", out, "GND", size="1206", pcb=P(14 + 2.5 * j + dx, 50.5 + dy, 270),
              sch=at(x0 + x, 25.5))
        R(s, f"R{r0}", "100k", out, fb, pcb=P(*FB_R[key][0]), sch=at(x0 + 62, 30))
        R(s, f"R{r0 + 1}", "18k", fb, "GND", pcb=P(*FB_R[key][1]), sch=at(x0 + 62, 37))
        s.wire(f"R{r0}.2", f"R{r0 + 1}.1")
        s.wire((x0 + 62, 33.5), (x0 + 36, 33.5), (x0 + 36, 25), f"{u}.FB")
        s.part(f"#FLG{9 + i}", "power:PWR_FLAG", "PWR_FLAG", "", {"1": out}, in_bom=False, on_board=False,
               sch=at(x0 + 58, 14))
    testpoints(s, ["TP9", "TP41", "TP42", "TP43", "TP45", "TP46", "TP47"],
               "Test points (rear face): +5V_A, +5V_B, VIN, GND", 6, 78)
    s.notes_at = (6, 56, 200)
    s.notes = [
        "Two LMR51625 as the bay node's (TI SLUSF64B table 8-1: 4.7 µH FXL0630, 2 × 10 µF + 100 nF in, 3 × 22 µF out).",
        "+5V_A: ports 1–3; +5V_B: ports 4–6 and the 3.3 V LDO (≤ 0.46 A).  Never in parallel: the power plane's +5V",
        "  split left / right.  +5V_A 1.5 A at 0.5 A a port, 1.93 A at the TPS2553s' 0.644 A limit (45.3k, 1 %);",
        "  +5V_B 0.46 A more: 2.39 A at the limit, under the LMR51625's 2.5 A.",
        "FB 100k/18k: 5.24 V, as the node's.",
        "EN 100k/10k: on above 13.5 V typ., up to 14.8 V on the EN threshold's 1.103–1.349 V (SLUSF64B §6.5) and",
        "  15.1 V with the 1 % resistors: the rack's 20 V clears it.  Off below 10.8 V typ.",
        "VIN on J1.8, the node's VRACK through its eFuse (TPS26600, ≈ 1.5 A, off by default): no second protection here.",
        "  ≈ 1.0 A at 20 V (1.3 A at the ports' limit), 1.5 A at 13.5 V, 0.75 A at 28 V; a PH contact carries 2 A.",
    ]


def buck_copper(sw: str, out: str, bx: float, by: float, tag: str) -> tuple[list, list]:
    """The converter's switch node and output as pours on F.Cu, the output's with vias down to its power plane: the
    layout review (2026-11-01) found the inductor's output reaching the plane through one via and a 0.4 mm track,
    the switch node through 0.45 mm tracks.  (bx, by): U13's centre, each block's offsets as power_sheet()'s.
    Returns (zones, vias)."""
    def at_(pts):
        return [(round(bx + x, 3), round(by + y, 3)) for x, y in pts]
    zones = [
        # the switch node: U13's SW pin, C64's pad and L2's input pad, as small as it can be
        {"layer": "F.Cu", "net": sw, "name": f"{tag}-sw", "priority": 3, "exclusive": 0.3, "connection": "solid",
         "poly": at_([(1.0, -0.3), (1.95, -0.3), (1.95, -3.1), (5.95, -3.1), (5.95, 1.85), (3.3, 1.85), (3.3, 0.3),
                      (1.0, 0.3)])},
        # the output: L2's pad and the three 22 µF's, round L2's body
        {"layer": "F.Cu", "net": out, "name": f"{tag}-out", "priority": 3, "exclusive": 0.3, "connection": "solid",
         "poly": at_([(9.25, -3.0), (12.8, -3.0), (12.8, 5.85), (4.85, 5.85), (4.85, 3.7), (9.25, 3.7)])},
    ]
    # five vias: two between the 22 µF, three round L2's output pad (two north, one south at its body's edge), all
    # within the power plane (the v2's +5V tongue ends 0.5 mm east of the pad)
    vias = [(out, round(bx + x, 3), round(by + y, 3), 0.6, 0.3)
            for x, y in ((7.25, 4.05), (9.75, 4.05), (11.0, 2.6), (10.0, -2.35), (11.4, -2.35))]
    return zones, vias


# ----------------------------------------------------------------------------------- hub, lead, 3.3 V
def hub_sheet(b: Board):
    s = b.sheet("Hub", "hub.kicad_sch", "Lead, hub, expander, 3.3 V")
    s.paper = "A2"
    s.frame("Lead from the node's J7 (PH 8, rear face): I²C through an H5VU25UC; pin 8 VIN (sheet Power), pin 1 open",
            6, 10, 70, 50)
    # the v2's J1, pin for pin, where the v2 has it.  Its pin 8 the rack's 20 V, which the node switches (its eFuse):
    # VIN, the converters' (power_sheet()), so the node power-cycles the whole board.  Solid to its pad.  Its pin 1
    # open (2026-11-01): a camera lead plugged in by mistake puts nothing on it, and the node polls instead of INT
    part(s, "J1", "ph8t", {"1": None, "2": "LEAD_SCL", "3": "LEAD_SDA", "4": "GND", "5": "UP_DN",
                           "6": "UP_DP", "7": "GND", "8": "VIN"}, "LEAD",
         pcb={**P(*LEAD, J1_ROT, "bottom"), "solid": ["8"]}, sch=at(16, 30, mirror="y", fields=(-2, -6)))
    s.part("#FLG02", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "GND"}, in_bom=False, on_board=False, sch=at(34, 16))
    part(s, "U4", "esd4", {"D1+": "LEAD_SDA", "D1-": "LEAD_SCL", "D2+": None, "D2-": None, "GND": "GND"},
         pcb=P(LEAD[0] + 3.25, LEAD[1] + 0.9, 90), sch=at(48, 30, fields=(-3, -6)))

    s.frame("3.3 V for the hub, the expander and the INA226s (AP2114H, SOT-223 on copper)",
            6, 56, 70, 86)
    s.tag("+5V_B", (24, 66), "up")
    s.wire((24, 66), (24, 69), "U3.VI")
    part(s, "U3", "ldo_1a", {"VI": "+5V_B", "VO": "+3V3", "GND": "GND"}, pcb=P(*LDO, 0),
         sch=at(34, 69, fields=(-3, -4)))
    # its input 22 µF west of it, by VI (pin 3); its output one east, by the tab (VO)
    C(s, "C2", "22u", "+5V_B", "GND", size="0805", pcb=P(LDO[0] - 6.2, LDO[1] + 2.3, 180), sch=at(20, 72))
    s.wire("C2.1", (20, 69), (24, 69))
    C(s, "C3", "22u", "+3V3", "GND", size="0805", pcb=P(LDO[0] + 5.6, LDO[1] - 1.8, 90), sch=at(44, 72))
    s.wire("U3.VO", (44, 69), "C3.1")
    s.wire((44, 69), (50, 69), net="+3V3")
    s.tag("+3V3", (50, 69), "up")

    s.frame("USB2517I hub, CFG_SEL 110 (internal default configuration, straps disabled), 24 MHz crystal",
            74, 10, 168, 104)
    hub = {"USBUP_DM": "UP_DN", "USBUP_DP": "UP_DP", "VDD33": "+3V3", "VDD33PLL": "+3V3", "VDD33CR": "+3V3",
           "VDDA33": "+3V3", "VDD18": "HUB_1V8", "VDD18PLL": "HUB_1V8PLL", "VSS": "GND", "TEST": "GND",
           "VBUS_DET": "+3V3", "RESET_N": "HUB_RST_N", "XTAL1/CLKIN": "XI", "XTAL2": "XO", "RBIAS": "RBIAS",
           "SCL/SMBCLK/CFG_SEL0": "HUB_CFG0", "HS_IND/CFG_SEL1": "HUB_CFG1", "CFG_SEL2": "HUB_CFG2",
           "SDA/SMBDATA/NON_REM1": "HUB_NONREM1", "SUSP_IND/LOCAL_PWR/NON_REM0": "HUB_NONREM0",
           "LED_B3_N/GANG_EN": "HUB_GANG", "LED_B1_N/BOOST0": "HUB_BOOST0", "LED_B2_N/BOOST1": "HUB_BOOST1"}
    for n in range(1, 8):
        hub[f"LED_A{n}_N/PRT_SWP{n}"] = f"HUB_SWP{n}"
        hub[f"PRTPWR{n}"] = None
        hub[f"OCS{n}_N"] = None
    for n in range(4, 8):
        hub[f"LED_B{n}_N"] = None
    # its south face's DN1–5 to USB-C 2–6: the pairs come down into the corridor over the clusters, DN3 straight on
    # down to USB-C 4, DN1–2 turning west and DN4–5 east in lanes, none crossing.  Its west face's DN6 to USB-C 1:
    # west over the crystal's keep-out and down the board's west edge.  DN7 declared but unused, left enabled with
    # nothing on it (the v2's ports 6 and 7)
    for dn in range(1, 7):
        n = dn + 1 if dn <= 5 else 1
        hub[f"USBDN{dn}_DP/PRT_DIS_P{dn}"] = f"PORT{n}_DP"
        hub[f"USBDN{dn}_DM/PRT_DIS_M{dn}"] = f"PORT{n}_DN"
    hub["USBDN7_DP/PRT_DIS_P7"], hub["USBDN7_DM/PRT_DIS_M7"] = None, None
    part(s, "U1", "usb2517", hub, pcb=P(HX, HY, 90), sch=at(124, 62, fields=(-11, -20)))
    rail(s, "+3V3", [f"U1.{n}" for n in (46, 64, 24, 5, 10, 52, 57)], -3)
    part(s, "Y1", "xtal24", {"1": "XI", "3": "XO", "2": "GND", "4": "GND"}, pcb=P(*XT, 90),
         sch=at(94, 64, fields=(-2, -4)))
    C(s, "C4", "33p", "XI", "GND", size="0402", pcb=P(XT[0] + 0.37, XT[1] + 2.65, 180), sch=at(88, 68))
    C(s, "C5", "33p", "XO", "GND", size="0402", pcb=P(XT[0] - 0.85, XT[1] - 3.1, 90), sch=at(100, 68))
    s.wire("Y1.1", (88, 64), "C4.1")
    s.wire("Y1.3", (100, 64), "C5.1")
    R(s, "R10", "1M", "XO", "XI", size="0402", pcb=P(XT[0] + 2.3, XT[1] + 0.25, 270), sch=at(94, 56, rot=90))
    for i, (ref, xy, rot) in enumerate((("C11", (HX - 4.7, HY + 6.2), 270), ("C13", (HX - 6.2, HY + 0.25), 180),
                                        ("C12", (HX - 6.2, HY - 2.25), 180), ("C15", (HX - 1.75, HY + 6.4), 270),
                                        ("C16", (HX + 0.75, HY + 6.4), 270), ("C14", (HX + 6.05, HY + 0.95), 270),
                                        ("C17", (HX - 2.85, HY - 6.4), 90))):
        C(s, ref, "100n", "+3V3", "GND", size="0402", pcb=P(*xy, rot), sch=at(80 + 6 * i, 24))
    C(s, "C8", "4.7u", "HUB_1V8PLL", "GND", size="0402", pcb=P(HX - 6.8, HY + 4.86, 270), sch=at(128, 24))
    C(s, "C10", "100n", "HUB_1V8PLL", "GND", size="0402", pcb=P(HX - 5.66, HY + 3.93, 270), sch=at(134, 24))
    C(s, "C7", "4.7u", "HUB_1V8", "GND", size="0402", pcb=P(HX + 6.05, HY - 3.0, 90), sch=at(146, 24))
    C(s, "C9", "100n", "HUB_1V8", "GND", size="0402", pcb=P(HX + 6.05, HY - 0.9, 90), sch=at(152, 24))
    R(s, "R1", "12k", "RBIAS", "GND", size="0402", pcb=P(HX - 5.75, HY + 6.6, 270), sch=at(84, 92))
    part(s, "U5", "max809s", {"GND": "GND", "~{RESET}": "HUB_RST_N", "VCC": "+3V3"},
         pcb=P(HX - 2.2, HY - 10.1, 90), sch=at(90, 80, fields=(-4, -5)))
    C(s, "C6", "100n", "+3V3", "GND", size="0402", pcb=P(HX - 2.68, HY - 12.7, 180), sch=at(78, 84))
    R(s, "R3", "10k", "HUB_SWP3", "GND", size="0402", pcb=P(HX - 5.3, HY - 9.05, 180), sch=at(100, 92))
    R(s, "R4", "10k", "HUB_NONREM0", "GND", size="0402", pcb=P(HX - 1.8, HY - 7.1, 90), sch=at(106, 92))
    R(s, "R5", "10k", "HUB_SWP4", "GND", size="0402", pcb=P(HX + 3.6, HY - 7.1, 90), sch=at(112, 92))
    R(s, "R9", "10k", "HUB_SWP5", "GND", size="0402", pcb=P(HX + 4.7, HY - 7.1, 90), sch=at(118, 92))
    for i, (nets, x, y, rot) in enumerate(((["HUB_SWP1", "HUB_BOOST0", "HUB_SWP2", "HUB_BOOST1"], HX - 4.8, HY - 7.1, 270),
                                           (["HUB_CFG1", "HUB_CFG0", "HUB_NONREM1", "HUB_GANG"], HX + 0.8, HY - 9.4, 90),
                                           ([None, "HUB_SWP6", "HUB_SWP7", "HUB_CFG2"], HX + 3.5, HY + 6.85, 270))):
        # RN3 under the hub's south-east corner, its signal pads up to the pins (pin 4 under CFG_SEL2, pin 3 under
        # SWP7), its rail pads down: the USB-C 5–6 pairs' lanes run right under it
        up = ("HUB_CFG1", "HUB_CFG2")
        rarray(s, f"RN{1 + i}", "10k", [(net, ("+3V3" if net in up else "GND") if net else None) for net in nets],
               P(x, y, rot), sch=at(126 + 12 * i, 92, rot=180, fields=(3, 0)))
        rail(s, "GND", [f"RN{1 + i}.{9 - q}" for q in range(1, 5) if nets[q - 1] and nets[q - 1] not in up], 2, "down")
        if any(net in up for net in nets):
            rail(s, "+3V3", [f"RN{1 + i}.{9 - q}" for q in range(1, 5) if nets[q - 1] in up], 2, "down")

    s.frame("TCA9535 expander (0x20): each port's EN and FAULT_N; its spare pins pulled down", 169, 10, 229, 60)
    # no RESET pin (the TCA6408A's): power-on reset only.  Its 100 nF right over VCC
    x, y = EXP
    exp = {"VCC": "+3V3", "GND": "GND", "EPAD": "GND", "A0": "GND", "A1": "GND", "A2": "GND", "SCL": "SCL",
           "SDA": "SDA", "~{INT}": None, **EXP_LINES}
    # the spare pins pulled down by 10k (an array east of it, each resistor on its pin's row: pins 17 … 14 down the
    # east face, the array's 1 … 4): an input reads 0 rather than float until the firmware sets it as an output, and
    # an output set high by mistake drives 0.33 mA
    spare = [pin for pin in ("P14", "P15", "P16", "P17") if pin not in exp]
    for pin in spare:
        exp[pin] = f"EXP_{pin}"
    part(s, "U2", "tca9535", exp, pcb=P(x, y, 0), sch=at(199, 34, fields=(-4, -12)))
    C(s, "C18", "100n", "+3V3", "GND", size="0402", pcb=P(x + 0.25, y - 3.6, 90), sch=at(181, 24))
    pairs = [(f"EXP_{pin}", "GND") for pin in reversed(spare)]
    rarray(s, "RN10", "10k", pairs, P(x + 3.7, y, 0), sch=at(221, 50))
    rail(s, "GND", [f"RN10.{9 - q}" for q in range(1, 5)], 2, "down")

    s.frame("I²C isolation: open with the board's 3.3 V off (the node's pull-ups can't feed it)", 169, 106, 229, 148)
    for i, (q, r, line, val) in enumerate((("Q1", "R6", "SDA", "4.7k"), ("Q2", "R7", "SCL", "4.7k"))):
        y = LEAD[1] - 10.4 + 4.0 * i
        part(s, q, "nfet", {"G": "+3V3", "S": line, "D": "LEAD_" + line}, pcb=P(LEAD[0] + 3.25, y, 90),
             sch=at(183, 118 + 12 * i))
        R(s, r, val, "+3V3", line, size="0402", pcb=P(LEAD[0] + 3.25, LEAD[1] - 15.4 + 1.0 * i, 0),
          sch=at(209, 116 + 12 * i))
    testpoints(s, ["TP7", "TP8", "TP20", "TP21", "TP22", "TP24", "TP25", "TP26", "TP27"],
               "Test points (rear face, bare pads, not in the BOM): +3V3, the hub's reset and 1.8 V, the lead's "
               "I²C, GND", 6, 136, per_row=12)
    s.notes_at = (6, 108, 160)
    s.notes = [
        "Hub reset: U5 (MAX809S, 2.93 V, ≥ 150 ms, push-pull) on RESET_N (errata DS80000628A, Module 2).",
        "Hub: CFG_SEL[2:0] = 110 (internal default configuration, strap options disabled: DS00001598C Table 5-2),",
        "  as the DATA ×4 v2's; ports 1–6 used, port 7 enabled with nothing on it (cosmetic).",
        "Hub ports: 1–5 = USB-C 2–6 (busid 1-1.1 … 1-1.5), 6 = USB-C 1 (1-1.6).",
        "Expander: TCA9535 U2 0x20.  Port n's EN on P0/P1(2n − 2), FAULT_N on the next bit (ports 1–4 on P00–P07,",
        "  5–6 on P10–P13).  Inputs at power-up: the EN pull-downs keep every port off until the node writes; the",
        "  spare pins P14–P17 set as outputs, low, by the firmware.",
        "No INT on the lead (J1.1 open, 2026-11-01): the node polls the expander and the INA226s every 10–20 ms.",
        "  The INA226 alerts stay transparent (Mask/Enable LEN = 0), or the node reads Mask/Enable on each poll; the",
        "  expander's INT and the INA226 ALERT pins are left open.  A port's fault needs no node: its TPS2553 latches off.",
        "I²C: TCA9535 0x20, INA226 0x41 / 0x43 / 0x44 / 0x45 / 0x47 / 0x4C; the node's INA226 0x40.",
        "J1 pin 8: VIN, the node's switched 20 V, to the converters (sheet Power); the hub's 3.3 V (U3) from +5V_B.",
        "  With VIN off the whole board is off; the EN pull-downs keep every port off until the node writes.",
        "J1 (through-hole) stands on the rear face: soldered by hand (the PCBA places the front face only).",
    ]


# GND vias filling the stitching grid's gaps (drawn()): where no grid via fits, the farthest pour point first; the
# second ties the rear pour's long strip at x 25.9 (one via held it).  Left: 4.84 mm at most, by USB-C 3's cluster
GND_FILL = [(34.02, 43.48), (25.9, 33.9), (89.9, 6.9), (78.28, 25.75), (53.75, 55.81), (28.9, 39.9), (18.4, 7.27),
            (20.9, 55.63), (25.95, 29.52), (63.9, 39.9), (11.9, 26.9), (23.9, 38.9), (30.18, 27.27), (49.55, 53.05),
            (74.18, 56.8), (80.65, 14.7), (83.67, 50.4), (21.71, 50.95)]


# ---------------------------------------------------------------------------------------- drawn copper
def offset(poly, d):
    """A polyline (mm) shifted d mm sideways, mitred at its corners: to the west when it heads down the board (+y),
    to the north when it heads west, to the south when it heads east, to the east when it heads up.  A
    differential pair's two lines from its centreline (the v2's)."""
    out = []
    for i, (x, y) in enumerate(poly):
        ns = []
        segs = ([(poly[i - 1], poly[i])] if i else []) + ([(poly[i], poly[i + 1])] if i < len(poly) - 1 else [])
        for (ax, ay), (bx, by) in segs:
            L = math.hypot(bx - ax, by - ay)
            ns.append((-(by - ay) / L, (bx - ax) / L))
        (n1x, n1y), (n2x, n2y) = ns[0], ns[-1]
        k = 1 + n1x * n2x + n1y * n2y
        out.append((round(x + d * (n1x + n2x) / k, 4), round(y + d * (n1y + n2y) / k, 4)))
    return out


HS_BAND = 1.075     # each pair's band: its centreline ± (0.2 + 0.125 to its lines' outer edges + 0.75, 3 × their width)


def pair_centrelines():
    """Each USB pair's centreline (hs_pairs()), and the part of it the band keeps other tracks off: its runs in
    the corridor over the clusters and its drop between two of them (from the lane's corner, or 1 mm under the
    hub's row for USB-C 4, down to 2.6 mm over its USBLC6: the EN and FAULT_N pull-ups of the cluster west of the
    drop stand 0.15–0.25 mm clear of the band, their lines leave them west), and USB-C 1's long ones (from its turn
    west over the crystal down the west edge to 2.4 mm over its USBLC6).  {n: (centreline, band)}"""
    c, hp = 0.8, (USB_W + 0.15) / 2
    top = HY + 4.9
    out = {}
    for n, (pin, d) in {2: (1, 0.0), 3: (3, -0.05), 4: (6, 0.05), 5: (8, -0.05), 6: (11, 0.05)}.items():
        x, xd = HX - 3.5 + 0.5 * (pin - 1) + d, DROP_DN[n] + hp
        end = USB_Y - 0.95 - 0.4                        # over its USBLC6's pin 4
        if n == 4:
            y = HY + 9.0
            cl = [(x, top + 0.4), (x, y), (xd, y + x - xd), (xd, end)]
            band = [(x, HY + 8.0), (x, y), (xd, y + x - xd), (xd, USB_Y - 2.6)]
        else:
            y, e = LANES[n], -1 if xd < x else 1
            cl = [(x, top + 0.4), (x, y - c), (x + e * c, y), (xd - e * c, y), (xd, y + c), (xd, end)]
            band = cl[1:-1] + [(xd, USB_Y - 2.6)]
        out[n] = (cl, band)
    xn, yw, xe = HX - 8.0, HY - 3.6, 5.2
    cl = [(HX - 4.9, HY - 1.45), (xn + c, HY - 1.45), (xn, HY - 1.45 - c), (xn, yw + c), (xn - c, yw), (xe + c, yw),
          (xe, yw + c), (xe, ESD1[1] - 0.95 - 0.4)]
    out[1] = (cl, cl[3:-1] + [(xe, ESD1[1] - 2.4)])
    return out


def hs_pairs():
    """The USB pairs, drawn (the v2's HS review, 2026-10-22: over a continuous GND reference, F.Cu above In1;
    Freerouting puts them on B.Cu, each line its own way).  D− and D+ either side of each pair's centreline
    (offset(), D− on its right-hand side), USB_W lines 0.15 mm apart (≈ 90 Ω: the USB netclass); they leave the
    hub's pins at their 0.5 mm pitch and close up.  No length-matching bumps (the layout review: on USB they make it
    worse).
    * USB-C 2–6 (the south face, DN1–5): down side by side under the hub (ports 3 and 4, 5 and 6 each 50 µm out
      from their pins' centre: C15 and C16, pins 5 and 10's 100 nF, between them); 2 and 3 turn west in the
      corridor's lanes (LANES), 5 and 6 east, the outer pin's pair first, none crossing; 4 steps 0.9 mm west and
      goes on down.  Each down between two clusters (DROP_DN) to its USBLC6: D+ into pin 4, D− on past it to pin 6.
    * USB-C 1 (the west face, DN6): west between C12 and the crystal's keep-out, north round it, west over the
      expander's lines and down the board's west edge to its USBLC6 over its receptacle.
    The upstream pair: up_pair().  Returns (tracks, vias)."""
    tracks = []
    hp = (USB_W + 0.15) / 2
    sy, top = HY + 4.4125, HY + 4.9             # the hub's south row, the pairs' start under it

    def keep(pts):
        """no point within 0.1 mm of the last one kept (a sliver otherwise)"""
        out = [pts[0]]
        for q in pts[1:-1]:
            if math.dist(q, out[-1]) >= 0.1:
                out.append(q)
        return out + [pts[-1]]

    def esd_pins(x, y):
        """a USBLC6's pin 4 (D+) and pin 6 (D−), turned 180°: its hub side, west"""
        return (x - 1.138, y - 0.95), (x - 1.138, y + 0.95)

    cls = pair_centrelines()
    for n, pin in {2: 1, 3: 3, 4: 6, 5: 8, 6: 11}.items():
        px = HX - 3.5 + 0.5 * (pin - 1)                 # its pins' centre
        p4, p6 = esd_pins(ESD_PX[n], USB_Y)
        # each line straight out of its pin, then in to the pair's pitch by y top + 0.4 (C15/C16 just under)
        cl = cls[n][0]
        xd = cl[-1][0]
        dn = keep([(px - 0.25, sy), (px - 0.25, top)] + offset(cl, hp) +
                  [(xd - hp, p6[1] - 0.5), (xd - hp + 0.5, p6[1]), p6])
        dp = keep([(px + 0.25, sy), (px + 0.25, top)] + offset(cl, -hp) + [(xd + hp + 0.4, p4[1]), p4])
        tracks += [(f"PORT{n}_DN", "F.Cu", USB_W, dn), (f"PORT{n}_DP", "F.Cu", USB_W, dp)]

    # USB-C 1: west from the pins, north round the keep-out at x HX − 8, west at y HY − 3.6, down the west edge at
    # x 5.2 (in the cradle's band, which only parts must keep clear of), past R101
    p4, p6 = esd_pins(*ESD1)
    cl, xe = cls[1][0], cls[1][0][-1][0]
    # D+ straight out of pin 54 (its line on the pin's row), D− in from pin 53 by 0.1 mm: clear of C12's pad
    dn = keep([(HX - 4.4125, HY - 1.75), (HX - 4.8, HY - 1.75)] + offset(cl, hp) +
              [(xe - hp, p6[1] - 0.5), (xe - hp + 0.5, p6[1]), p6])
    dp = keep([(HX - 4.4125, HY - 1.25), (HX - 4.9, HY - 1.25)] + offset(cl, -hp) + [(xe + hp + 0.4, p4[1]), p4])
    tracks += [("PORT1_DN", "F.Cu", USB_W, dn), ("PORT1_DP", "F.Cu", USB_W, dp)]
    return tracks, []


def up_pair():
    """The upstream pair, drawn: J1's pins 5 (D−) and 6 (D+) to the hub's pins 58 and 59 on its west face (the
    router's weaved 0.5–2.3 mm apart between the exposed pad's vias, faults and enables beside it).  Boxed in on F.Cu
    by USB-C 1's pair, C13 and the crystal (hs_pairs()), it dives by its pins under the hub's body to B.Cu and runs
    east under the exposed pad (its last row of vias moved down 0.85 mm to let it by) and the 1.8 V and 3.3 V
    capacitors east of the hub; past them it comes up to F.Cu and crosses over there (the hub has D− north of D+, J1
    has D− south of D+), then runs east to J1, opening to J1's 2 mm pitch at its end.  Its lines 0.4 mm apart
    throughout, the B.Cu run over the +3V3 plane, the F.Cu one over GND; both as long within 0.3 mm.  Returns
    (tracks, vias, the B.Cu run's centreline, the F.Cu run's) for the bands (board())."""
    hp = (USB_W + 0.15) / 2
    p58, p59 = (HX - 4.4125, HY + 0.75), (HX - 4.4125, HY + 1.25)        # U1 pins 58 (D−), 59 (D+)
    j5, j6 = (LEAD[0], LEAD[1] - 8.0), (LEAD[0], LEAD[1] - 10.0)        # J1 pins 5 (D−), 6 (D+)
    yb = HY + 1.25                                                        # the B.Cu run's centreline
    hn, hd = (HX - 3.25, HY + 0.6), (HX - 3.25, yb + hp)                 # the vias by the pins, under the body
    cn, cd = (HX + 9.3, yb - hp), (HX + 8.4, yb + hp + 0.25)              # where it comes up, east of C14
    fcl = [(HX + 8.6, yb - 0.4), (HX + 8.6, j5[1] - 0.2), (HX + 9.4, j5[1] - 1.0), (j5[0] - 1.3, j5[1] - 1.0)]
    dn = [cn, (HX + 8.8, yb - hp - 0.5)] + offset(fcl, hp)[1:] + [(j5[0] - 0.5, j5[1]), j5]
    dp = [cd] + offset(fcl, -hp) + [(j6[0] - 0.5, j6[1]), j6]
    tracks = [("UP_DN", "F.Cu", USB_W, [p58, (hn[0] - 0.15, p58[1]), hn]),
              ("UP_DP", "F.Cu", USB_W, [p59, (hd[0] - 0.45, p59[1]), (hd[0] - 0.25, hd[1]), hd]),
              ("UP_DN", "B.Cu", USB_W, [hn, (hn[0] + 0.45, yb - hp), cn]),
              ("UP_DP", "B.Cu", USB_W, [hd, (cd[0] - 0.25, yb + hp), cd]),
              ("UP_DN", "F.Cu", USB_W, dn), ("UP_DP", "F.Cu", USB_W, dp)]
    vias = [(net, *v, 0.5, 0.3) for net, v in (("UP_DN", hn), ("UP_DP", hd), ("UP_DN", cn), ("UP_DP", cd))]
    # the bands (board()) take in the vias at both ends of the B.Cu run, and 0.75 mm past them
    return tracks, vias, [(hn[0] - 1.1, yb), (cn[0] + 1.1, yb)], [(fcl[0][0], yb + 0.65)] + fcl[1:]


def conn_pairs():
    """Each USBLC6's pair on to its receptacle, drawn (the router took D+ round the receptacle: 41 mm and six vias on
    USB-C 1).  The receptacles stand, their A column (A12 … A1, north to south) facing the USBLC6 west of them, A7
    (D−) north of A6 (D+); the USBLC6 keeps its lines' order, pin 3 (D+) north of pin 1 (D−).  So one line crosses
    under the other, and the receptacle's own crossover (D+ on A6 and B6, D− on A7 and B7, one column turned against
    the other) takes no more vias:
    * D+ on F.Cu, no via: east, down 1.2 mm past the USBLC6's GND via, into A6, then diagonally between the two
      columns to B6;
    * D− down to B.Cu by its pin, under D+, up north of D+'s line by A7 and into it; on from that via on B.Cu, under
      the A column, to a via between the columns, up into B7.
    D− runs 0.1–0.4 mm short of D+ into either column, whichever way the plug goes in; no length-matching bump (the
    layout review: on USB they make it worse).  Also drawn: each USBLC6's GND pin to its via, and VBUS across the
    columns, A9 to B4 and A4 to B9.  Returns (tracks, vias)."""
    tracks, vias = [], []
    for n, cx in enumerate(USBS, 1):
        p = f"PORT{n}_"
        ex, ey = ESD_PX[n], USB_Y
        e3, e1 = (ex + 1.1375, ey - 0.95), (ex + 1.1375, ey + 0.95)         # its pins 3 (D+) and 1 (D−), turned 180°
        # USB-C 1's USBLC6 stands 5.7 mm off its receptacle, the others 9.1–9.6: its GND via under its body (south of
        # the VBUS pin's line to C104), out of the way of D+'s diagonal, which starts 0.4 mm earlier (cx − 3.8),
        # clear of D−'s via by A7
        gv = (ex, ey + 0.55) if n == 1 else (ex + 2.15, ey)
        dx0 = cx - 3.8 if n == 1 else ex + 2.3
        tracks.append(("GND", "F.Cu", 0.25, [(ex + 1.1375, ey), gv]))
        vias.append(("GND", *gv, 0.5, 0.3))

        def c(dx, dy):
            return cx + dx, USB_Y + dy
        a9, a7, a6, a4 = (c(-USBC_COL, d) for d in (-1.25, -0.25, 0.25, 1.25))
        b4, b6, b7, b9 = (c(USBC_COL, d) for d in (-1.25, -0.25, 0.25, 1.25))
        v1, vn, vs = (ex + 2.15, e1[1]), c(-2.35, -0.3), c(0.0, 0.6)       # D−'s vias: by its pin, by A7, between
        tracks += [(p + "CONN_DP", "F.Cu", USB_W, [e3, (dx0, e3[1]), (dx0 + 1.2, a6[1]), a6]),
                   (p + "CONN_DP", "F.Cu", USB_W, [a6, c(-0.4, 0.25), c(0.4, -0.25), b6]),
                   (p + "CONN_DN", "F.Cu", USB_W, [e1, v1]),
                   (p + "CONN_DN", "B.Cu", USB_W, [v1, vn, vs]),
                   (p + "CONN_DN", "F.Cu", USB_W, [vn, a7]),
                   (p + "CONN_DN", "F.Cu", USB_W, [vs, c(0.4, 0.25), b7]),
                   (p + "VBUS", "F.Cu", 0.3, [a9, b4]), (p + "VBUS", "F.Cu", 0.3, [a4, b9])]
        vias += [(p + "CONN_DN", *v, 0.5, 0.3) for v in (v1, vn, vs)]
        # and the two VBUS crossings joined under the B column on B.Cu, clear of D−'s way to its via between the
        # columns: on the GCT's longer pads the router no longer found a way round, and CC1 / CC2 leave the
        # columns' outer ends free
        vbn, vbs = c(0.0, -1.25), c(0.6, 1.25)
        tracks.append((p + "VBUS", "B.Cu", 0.3, [vbn, c(0.9, -0.35), c(0.9, 0.95), vbs]))
        vias += [(p + "VBUS", *v, 0.6, 0.3) for v in (vbn, vbs)]
    return tracks, vias


def drawn():
    """The copper drawn before the routing that the v2 already had round its hub, which stands here as on the v2
    (in the middle of the top edge): the crystal's block, each 100 nF in the pin → cap → via order, the exposed
    pad's vias, the USB pairs.  Returns (tracks, vias)."""
    hand_tracks, hand_vias = [], []
    # the hub's reset supervisor in the pin → cap → via order: VCC (U5 pin 3) straight up to C6, C6 on east to
    # its via
    hand_tracks.append(("+3V3", "F.Cu", 0.25, [(HX - 2.2, HY - 11.038), (HX - 2.2, HY - 12.7), (HX - 1.5, HY - 12.7)]))
    hand_vias.append(("+3V3", HX - 1.5, HY - 12.7, 0.5, 0.3))
    # the exposed pad's GND vias, 3 × 3, the south row 2.05 mm under its centre: the upstream pair runs between it
    # and the middle row (up_pair())
    hand_vias += [("GND", HX + 1.2 * i, HY + j, 0.5, 0.3) for i in (-1, 0, 1) for j in (-1.2, 0.0, 2.05)]
    hand_tracks += [("GND", "F.Cu", 0.2, [(HX + 4.4125, HY + 2.75), (HX + 2.95, HY + 2.75), (HX + 2.25, HY + 2.05),
                                          (HX, HY)]),
                    ("GND", "F.Cu", 0.2, [(HX + 3.75, HY + 7.35), (HX + 3.25, HY + 7.35)]),
                    # its via under pads 6 / 7, between them and USB-C 6's lane, away from pad 5 (CFG_SEL2's pull-up,
                    # +3V3 since CFG_SEL 110)
                    ("GND", "F.Cu", 0.2, [(HX + 3.25, HY + 7.35), (HX + 3.5, HY + 7.6), (HX + 3.5, HY + 8.15)]),
                    # pad 5 (CFG_SEL2's pull-up) straight down to its +3V3 via, west of the GND one, clear of USB-C
                    # 6's pair turning east and of its band
                    ("+3V3", "F.Cu", 0.25, [(HX + 2.75, HY + 7.35), (HX + 2.75, HY + 8.15)])]
    hand_vias += [("GND", HX + 3.5, HY + 8.15, 0.5, 0.3), ("+3V3", HX + 2.75, HY + 8.15, 0.5, 0.3)]
    t, v = xtal_block()
    hand_tracks += t
    hand_vias += v
    # C17 (pin 46's 100 nF) in the pin → cap → via order: right over the pin, the pin straight up into it (its
    # last 0.1 mm step inside the pad) and C17 on west to its via (the via used to sit between them; east, it
    # would cut pin 45's HUB_NONREM0 off from R4).  Pin 47's HUB_SWP3 dives to B.Cu right above its pin, under
    # C17's line, and RN1's GND pad 8 keeps its dog-bone east
    p46 = (HX - 2.75, HY - 4.4125)                                      # U1 pin 46, turned 90°
    hand_tracks += [("+3V3", "F.Cu", 0.25, [p46, (p46[0], HY - 5.82), (HX - 2.85, HY - 5.92),
                                            (HX - 3.7, HY - 5.92)]),
                    ("HUB_SWP3", "F.Cu", 0.127, [(HX - 3.25, HY - 4.4125), (HX - 3.25, HY - 5.25)]),
                    ("GND", "F.Cu", 0.25, [(HX - 4.05, HY - 6.6), (HX - 3.5, HY - 6.6)])]
    hand_vias += [("+3V3", HX - 3.7, HY - 5.92, 0.5, 0.3), ("HUB_SWP3", HX - 3.25, HY - 5.25, 0.5, 0.3),
                  ("GND", HX - 3.5, HY - 6.6, 0.5, 0.3)]
    # C12 (pin 52's 100 nF) in the pin → cap → via order: the pin straight west to it, on its line, C12 on up to
    # its via (the pin's own fan-out via, under the case, gone)
    p52 = (HX - 4.4125, HY - 2.25)                                      # U1 pin 52
    hand_tracks.append(("+3V3", "F.Cu", 0.25, [p52, (HX - 5.72, p52[1]), (HX - 5.72, HY - 3.05)]))
    hand_vias.append(("+3V3", HX - 5.72, HY - 3.05, 0.5, 0.3))
    # C18 (the expander's 100 nF) in the pin → cap → via order: VCC (U2 pin 21) straight up into it, C18 on east to
    # its via
    p21 = (EXP[0] + 0.25, EXP[1] - 1.9375)                              # U2 pin 21
    hand_tracks.append(("+3V3", "F.Cu", 0.25, [p21, (p21[0], EXP[1] - 3.09), (p21[0] + 0.95, EXP[1] - 3.09)]))
    hand_vias.append(("+3V3", p21[0] + 0.95, EXP[1] - 3.09, 0.5, 0.3))
    # each port's INA226: VS (pin 6, turned 90°) straight up into its 100 nF, then on to its via (the v2's).  Its
    # USBLC6: VBUS (pin 5) under the body to its centre line and up between the pin rows into its 100 nF, then on
    # to a via in its 5 V area
    for n in range(1, 7):
        vs = (ina_x(n) + 1.0, CL_Y + 2.45)
        hand_tracks.append(("+3V3", "F.Cu", 0.25, [vs, (vs[0], CL_Y + 0.15)]))
        hand_vias.append(("+3V3", vs[0], CL_Y + 0.15, 0.5, 0.3))
        # the via under its VBUS test pad (TPS), kept where the router had it
        hand_vias.append((f"PORT{n}_VBUS", *VBUS_TP[n], 0.6, 0.3))
        ex, ey = ESD_PX[n], USB_Y
        v5 = "+5V_A" if n <= 3 else "+5V_B"
        top = ey - 2.9
        hand_tracks.append((v5, "F.Cu", 0.25, [(ex - 1.138, ey), (ex - 0.3, ey), (ex, ey - 0.3), (ex, top)]))
        hand_vias.append((v5, ex, top, 0.5, 0.3))
    # C13 (pin 57's 100 nF) likewise, on pin 57's line: the pin west to it, C13 on down to its via
    p57 = (HX - 4.4125, HY + 0.25)                                      # U1 pin 57
    hand_tracks.append(("+3V3", "F.Cu", 0.25, [p57, (HX - 5.72, p57[1]), (HX - 5.72, HY + 0.95)]))
    hand_vias.append(("+3V3", HX - 5.72, HY + 0.95, 0.5, 0.3))
    # C14 (pin 24's 100 nF) turned so its +3V3 pad faces the pin: the pin east to it (a jog down past C9's pad),
    # C14 on east to its via
    p24 = (HX + 4.4125, HY + 0.25)                                      # U1 pin 24
    hand_tracks.append(("+3V3", "F.Cu", 0.25, [p24, (HX + 5.83, p24[1]), (HX + 6.05, HY + 0.47),
                                               (HX + 6.7, HY + 0.47)]))
    hand_vias.append(("+3V3", HX + 6.7, HY + 0.47, 0.5, 0.3))
    # the hub's south VDD33 pin 5 takes its via inwards, under its body (between the pads and the UP pair): its
    # automatic fan-out via sat right below the row, between the downstream pairs, and boxed port 2's D− in
    # (Freerouting left it unrouted).  Its line goes on down to C15, its 100 nF, between USB-C 3 and 4's pairs.
    # Pin 10 likewise, C16 between USB-C 5 and 6's (the v2's C16 took its via east, where USB-C 6's pair runs here).
    # Each capacitor's GND pad down to a via of its own between the pairs
    for x in (HX - 1.75, HX + 0.75):
        hand_tracks += [("+3V3", "F.Cu", 0.25, [(x, HY + 4.4125), (x, HY + 3.75)]),
                        ("+3V3", "F.Cu", 0.25, [(x, HY + 4.4125), (x, HY + 5.92)]),
                        ("GND", "F.Cu", 0.25, [(x, HY + 6.88), (x, HY + 7.6)])]
        hand_vias += [("+3V3", x, HY + 3.75, 0.5, 0.3), ("GND", x, HY + 7.6, 0.5, 0.3)]
    t, v = hs_pairs()
    hand_tracks += t
    hand_vias += v
    t, v, _, _ = up_pair()
    hand_tracks += t
    hand_vias += v
    t, v = conn_pairs()
    hand_tracks += t
    hand_vias += v
    # pin 64's: the pin down to C11 (its 100 nF) right below the corner, and its via inwards, under the hub's
    # body, off that line (it sat on it, between the pin and C11).  C11 is an exception to the pin → cap → via
    # order: no via fits past its +3V3 pad, between R1's RBIAS pad west and port 1's D− east
    p64 = (HX - 4.4125, HY + 3.75)                                      # U1 pin 64
    hand_tracks += [("+3V3", "F.Cu", 0.25, [p64, (HX - 4.7, p64[1] + 0.2875), (HX - 4.7, HY + 5.72)]),
                    ("+3V3", "F.Cu", 0.25, [p64, (HX - 3.6, HY + 3.6)])]
    hand_vias.append(("+3V3", HX - 3.6, HY + 3.6, 0.5, 0.3))
    # GND vias where the 4 mm stitching grid leaves the outer pours more than 4.5 mm from one (the layout review,
    # 2026-11-01: its grid is 4–5 mm), each inside both pours' fill: farthest gap first
    hand_vias += [("GND", x, y, 0.6, 0.3) for x, y in GND_FILL]
    return hand_tracks, hand_vias


# ---------------------------------------------------------------------------------------------- board
def board() -> Board:
    b = Board("data-port-x6", "DATA ×6", "1.0",
              comments=["A porte-revues drawer board: six switched, measured USB-C behind a hub "
                        "(hw-testing-rack)",
                        "Generated from electronics/data-port-x6/design.py — edit the Python, then regenerate"])
    b.root_paper, b.root_buses = "A2", True
    b.root_notes = [
        "DATA ×6 v1.0 — USB2517I hub (7 ports, 6 used), six USB-C each with a TPS2553-1, an INA226 and ESD, a",
        "  TCA9535 for their EN and FAULT_N, an AP2114H 3.3 V; two LMR51625 make all its 5 V from VIN (20 V,",
        "  J1.8, switched by the node).  No pin header: the porte-revues bays' boards take no Dupont lead (the",
        "  DATA ×4 v2 keeps the logic).  One face assembled.",
        "Lead pinout here: 1 NC · 2 SCL · 3 SDA · 4 GND · 5 D− · 6 D+ · 7 GND · 8 VIN — the DATA ×4 v2's lead.",
        "I²C: TCA9535 0x20, INA226 0x41 / 0x43 / 0x44 / 0x45 / 0x47 / 0x4C; the node's 0x40.",
        "Rails: VIN 20 V (on above 13.5 V typ., 15.1 V at worst; ≤ 28 V), ≤ 1.3 A at 20 V ·",
        "  +5V_A / +5V_B 5.24 V, ≤ 1.93 A / 2.39 A",
        "  (ports 1–3 / 4–6 at the 0.644 A limit, +5V_B with the 3.3 V LDO's 0.46 A) ·",
        "  PORTn_VBUS 5.1–5.24 V, 0.52–0.64 A limit ·",
        "  +3V3 3.3 V (AP2114H), ≤ 0.5 A (the hub 0.42 A at most) · HUB_1V8 / HUB_1V8PLL 1.8 V (the hub's own",
        "  regulators).",
    ]
    hub_sheet(b)
    power_sheet(b)
    for n in range(1, 7):
        port(b, n)

    cw, ch = CORNER
    corner = [(W, H - ch, 0.5), (W - cw, H - ch, 0.5), (W - cw, H, 0)] if cw else [(W, H, 1.0)]
    outline = [(0, 0, 1.0), (W, 0, 1.0), *corner]
    for x0, x1, top in reversed(NOTCHES):
        outline += [(x1, H, 0), (x1, top, 0.5), (x0, top, 0.5), (x0, H, 0)]
    outline += [(0, H, 1.0)]
    # The power plane (In2): +3V3 over the top of the board, down to the split under the clusters (PWR_SPLIT); under
    # it, +5V_A west of x 50 (ports 1–3) and +5V_B east (ports 4–6), 0.2 mm apart, never joined.  Each converter
    # stands on a tongue of its own output in a top corner, and the tongue runs down the cradle's band at its end
    # (nothing else uses it, either face) to its area.  Each port switch's IN takes its 5 V by a track down past the
    # split, as the v2's.  All 1.4 mm from the edge, notches included
    E = 1.4
    bottom = [pt for x0, x1, top in reversed(NOTCHES)
              for pt in ((x1 + E, H - E), (x1 + E, top - E), (x0 - E, top - E), (x0 - E, H - E))]
    TA, TBX, TB = 23.4, 77.0, 13.8      # converter A's tongue's east edge, B's west edge, their bottom
    IN_5VA = [(E, E), (TA, E), (TA, TB), (5.4, TB), (5.4, PWR_SPLIT + 0.1), (MID_X - 0.1, PWR_SPLIT + 0.1),
              (MID_X - 0.1, H - E), *[pt for pt in bottom if pt[0] < MID_X], (E, H - E)]
    IN_5VB = [(TBX, E), (W - E, E), (W - E, H - ch - E), (W - cw - E, H - ch - E), (W - cw - E, H - E),
              *[pt for pt in bottom if pt[0] > MID_X], (MID_X + 0.1, H - E), (MID_X + 0.1, PWR_SPLIT + 0.1),
              (W - 5.4, PWR_SPLIT + 0.1), (W - 5.4, TB), (TBX, TB)]
    IN_3V3 = [(TA + 0.2, E), (TBX - 0.2, E), (TBX - 0.2, TB + 0.2), (W - 5.6, TB + 0.2), (W - 5.6, PWR_SPLIT - 0.1),
              (5.6, PWR_SPLIT - 0.1), (5.6, TB + 0.2), (TA + 0.2, TB + 0.2)]
    hand_tracks, hand_vias = drawn()
    buck_zones = []
    for key, (dx, dy) in BUCKS.items():
        z, v = buck_copper(f"BUCK{key}_SW", f"+5V_{key}", 8 + dx, 44 + dy, f"buck{key.lower()}")
        buck_zones += z
        hand_vias += v
    six = LAYERS == 6                   # X6_LAYERS=6: F · GND · sig · sig · power · B (the v2's 6-layer stack)
    pwr = "In4.Cu" if six else "In2.Cu"
    b.pcb = {
        "size": (W, H), "layers": LAYERS, "outline": outline, "passes": 80,
        "min_track": 0.09, "min_clearance": 0.1, "hole_clearance": 0.2,
        "inner": ([("In1.GND", "power"), ("In2.SIG", "signal"), ("In3.SIG", "signal"), ("In4.PWR", "power")]
                  if six else [("In1.GND", "power"), ("In2.PWR", "power")]),
        "stackup": "JLC06161H-3313" if six else "JLC04161H-7628", "finish": "ENIG",
        "edge_parts": [],
        "defer_pours": False,
        "fanout_nets": {"GND": ("In1.Cu", 0.5, 0.3, 0.25), "+5V_A": (pwr, 0.6, 0.3, 0.4), "+5V_B": (pwr, 0.6, 0.3, 0.4),
                        "+3V3": (pwr, 0.5, 0.3, 0.25)},
        "plane_nets": {"+5V_A": pwr, "+5V_B": pwr, "+3V3": pwr},
        "power_nets": {"GND": 1, "VIN": 2, "+5V_A": 2, "+5V_B": 2, "+3V3": 2, "PORT?_VBUS": 2,
                       "PORT?_5V_SW": 2},
        # each decoupling capacitor's pin (electronics/tools/decoupling.py: its pad ≤ 2 mm from the pin, its GND pad
        # ≤ 1 mm from a GND via; 100 nF and less in the pin → cap → via order).  As the v2's round the hub; C8 and
        # C7, VDD18PLL's and VDD18's 4.7 µF, are their 100 nF's stores, behind them: their own 2.5 mm limit.  Each
        # converter's first 10 µF its own 3 mm, as the bay node's.  Not declared: bulk (C60, VIN's; each
        # port's VBUS 22 µF; the converters' second 10 µF and their 22 µF outputs), the crystal's load capacitors,
        # the converters' bootstrap capacitors
        "decoupling": {
            "C2": "U3.3", "C3": "U3.2", "C6": "U5.3",                                   # the LDO in and out, MAX809S
            "C7": ("U1.25", 2.5), "C9": "U1.25", "C8": ("U1.62", 2.5), "C10": "U1.62",  # the hub's VDD18, PLL
            "C11": "U1.64", "C12": "U1.52", "C13": "U1.57", "C14": "U1.24", "C15": "U1.5", "C16": "U1.10",
            "C17": "U1.46",                                                               # its seven 3.3 V pins
            "C18": "U2.21",                                                               # the expander
            "C61": ("U13.VIN", 3.0), "C63": "U13.VIN", "C71": ("U14.VIN", 3.0), "C73": "U14.VIN",  # the converters
            **{f"C{k + 1}": f"U{k + 1}.1" for k in range(100, 700, 100)},             # each port's switch IN
            **{f"C{k + 3}": f"U{k + 2}.6" for k in range(100, 700, 100)},             # its INA226
            **{f"C{k + 4}": f"U{k + 3}.5" for k in range(100, 700, 100)}},            # its USBLC6's VBUS
        "stitch": 4.0,
        "edge_fence": {"pitch": 5.0, "inset": 0.9},
        # each High-Speed link, chip pin to far pin (tools/tests/test_pair_skew.py): the upstream pair within 1 mm;
        # the ports' links not compensated yet (D− 2.9–4.0 mm longer), held where they stand until they are
        "skew": {"tol": 1.0, "links": {"UP": (("UP_DP",), ("UP_DN",)),
                                       **{f"PORT{n}": ((f"PORT{n}_DP", f"PORT{n}_CONN_DP"),
                                                       (f"PORT{n}_DN", f"PORT{n}_CONN_DN")) for n in range(1, 7)}},
                 "loose": {"PORT1": (4.05, "as routed 2026-11-02, not compensated yet"),
                           **{f"PORT{n}": (2.95, "as routed 2026-11-02, not compensated yet") for n in range(2, 7)}}},
        "zones": [{"layer": "In1.Cu", "net": "GND"},
                  {"layer": pwr, "net": "+3V3", "name": "pwr-3v3", "poly": IN_3V3},
                  {"layer": pwr, "net": "+5V_A", "name": "pwr-5va", "poly": IN_5VA},
                  {"layer": pwr, "net": "+5V_B", "name": "pwr-5vb", "poly": IN_5VB},
                  *buck_zones,
                  {"layer": "F.Cu", "net": "GND"}, {"layer": "B.Cu", "net": "GND"}],
        "tracks": hand_tracks, "vias": hand_vias,
        # the 100 nF that cannot keep the pin → cap → via order where they sit (decoupling.py), with the measures
        "decoupling_order_exempt": {
            "C11": "U1 pin 64's via under the case, beyond the pin; none fits past C11's pad: R1's RBIAS pad west "
                   "and USB-C 2's D- east, 0.42 and 0.57 mm from it (a via takes 0.7)",
            "C15": "U1 pin 5's via under the case, beyond the pin; none fits past C15's pad between USB-C 3 and 4's "
                   "pairs: 0.17 mm to each",
            "C16": "U1 pin 10's via under the case, beyond the pin; none fits past C16's pad between USB-C 5 and "
                   "6's pairs: 0.17 mm to each"},
        "dru": XTAL_RULE,
        "min_width_except": MIN_WIDTH_EXCEPT,
        "keepouts": CRADLE_KEEPOUTS + [
            # the crystal's block (dropped once routed), as the v2's
            {"name": "core:xtal-y1", "layers": ["F.Cu", "B.Cu"], "poly": XTAL_KEEP},
            # no rear pour in the 0.7 mm strip by USB-C 6's cluster (x 91.5) that one via alone held: no room for a second
            {"name": "gnd-strip-6", "layers": ["B.Cu"], "fills_only": True,
             "poly": [(91.0, 47.0), (92.0, 47.0), (92.0, 51.6), (91.0, 51.6)]}] + [
            # each USB pair's band on F.Cu (the layout review: 3 × the track width between a fast bus and other
            # nets' lines, the enables and faults first): no other track along it, vias in (dropped once routed)
            {"name": f"core:usb{n}", "layers": ["F.Cu"], "tracks_only": True,
             "poly": offset(band, HS_BAND) + offset(band, -HS_BAND)[::-1]}
            for n, (_, band) in sorted(pair_centrelines().items())] + [
            {"name": f"core:up-{layer[0]}", "layers": [layer], "tracks_only": True,
             "poly": offset(band, HS_BAND) + offset(band, -HS_BAND)[::-1]}
            for layer, band in (("B.Cu", up_pair()[2]), ("F.Cu", up_pair()[3]))] + [
            # round the upstream pair's vias (on B.Cu only by the hub's pins, whose fan-out it would bar) and J1's
            # pins 5 and 6 (D−, D+), 0.75 mm past their copper: no other track there (dropped once routed)
            {"name": f"core:up-v{i}", "layers": ["B.Cu"] if x < HX else ["F.Cu", "B.Cu"], "tracks_only": True,
             "poly": [(x - 1.05, y - 1.05), (x + 1.05, y - 1.05), (x + 1.05, y + 1.05), (x - 1.05, y + 1.05)]}
            for i, (_, x, y, *_) in enumerate(up_pair()[1])] + [
            {"name": "core:j1-usb", "layers": ["F.Cu", "B.Cu"], "tracks_only": True,
             "poly": [(LEAD[0] - 1.7, LEAD[1] - 11.4), (LEAD[0] + 1.7, LEAD[1] - 11.4), (LEAD[0] + 1.7, LEAD[1] - 6.6),
                      (LEAD[0] - 1.7, LEAD[1] - 6.6)]}] + [
            {"name": f"edge{i}", "poly": [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]}
                     for i, (x0, y0, x1, y1) in enumerate((
                         (0, 0, W, 0.35), (W - 0.35, 0, W, H), (0, H - 0.35, W, H), (0, 0, 0.35, H),
                         *([(W - cw - 0.35, H - ch - 0.35, W, H)] if cw else []),
                         *((x0 - 0.35, top - 0.35, x1 + 0.35, H) for x0, x1, top in NOTCHES)))] + [
            # B.Cu runs over the power plane: no B.Cu track crosses its splits (+3V3 / +5V, +5V_A / +5V_B, the
            # tongues' edges), so a signal that does crosses on F.Cu over the GND plane (the v2's RF review)
            {"name": name, "layers": ["B.Cu", "In3.Cu"] if six else ["B.Cu"], "tracks_only": True,
             "poly": [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]}
            for name, (x0, y0, x1, y1) in (
                ("split", (0.35, PWR_SPLIT - 0.5, W - 0.35, PWR_SPLIT + 0.5)),
                ("split-ab", (MID_X - 0.5, PWR_SPLIT, MID_X + 0.5, H - 0.35)),
                ("split-5va-east", (TA - 0.4, 0.35, TA + 0.6, TB + 0.6)),
                ("split-5va-foot", (5.0, TB - 0.4, TA + 0.6, TB + 0.6)),
                ("split-5va-band", (5.0, TB - 0.4, 6.0, PWR_SPLIT)),
                ("split-5vb-west", (TBX - 0.6, 0.35, TBX + 0.4, TB + 0.6)),
                ("split-5vb-foot", (TBX - 0.6, TB - 0.4, W - 5.0, TB + 0.6)),
                ("split-5vb-band", (W - 6.0, TB - 0.4, W - 5.0, PWR_SPLIT)))],
        # 0.8 mm text in 0.15 mm strokes (the layout review: 0.15 at least; 15 % of 0.8 would give 0.12)
        "texts": [
            {"text": "DATA ×6 v1.0", "x": 50.4, "y": H - 2.5, "size": 0.8, "thickness": 0.15},   # by USB-C 3 and 4
            *({"text": name, "x": x, "y": y + d / 2 + 0.75, "size": 0.8, "thickness": 0.15, "layer": "B.SilkS"}
              for net, name, d, x, y in TPS.values()),
            # the lead's connector, named on the rear face where it plugs in: it brings the 20 V
            {"text": "LEAD 20 V", "x": LEAD[0], "y": LEAD[1] + 3.6, "size": 0.8, "thickness": 0.15,
             "layer": "B.SilkS"},
        ],
    }
    return b


USB_W = 0.15 if LAYERS == 6 else 0.25    # ≈ 90 Ω over 0.1 mm of 3313 prepreg on 6 layers, 0.2 mm of 7628 on 4
NETCLASSES = [
    {"name": "Default", "clearance": 0.1, "track_width": 0.127, "via_diameter": 0.5, "via_drill": 0.3},
    {"name": "Supply", "clearance": 0.1, "track_width": 0.25, "via_diameter": 0.5, "via_drill": 0.3,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 5,
     "_patterns": ["+3V3", "*HUB_1V8", "*HUB_1V8PLL"], "_min_width": 0.25},
    {"name": "Power", "clearance": 0.15, "track_width": 0.6, "via_diameter": 0.6, "via_drill": 0.3,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 1,
     "_patterns": ["+5V_A", "+5V_B", "*VIN", "*BUCK?_SW"], "_min_width": 0.25},
    {"name": "Port", "clearance": 0.1, "track_width": 0.3, "via_diameter": 0.6, "via_drill": 0.3,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 2,
     "_patterns": ["*PORT?_5V_SW", "*PORT?_VBUS"], "_min_width": 0.25},
    # the enables, faults and resets: Default's widths, kept 3 × USB_W off the USB pairs (netrules.py)
    {"name": "Sensitive", "clearance": 0.1, "track_width": 0.127, "via_diameter": 0.5, "via_drill": 0.3,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 6,
     "_patterns": ["*PORT?_EN", "*PORT?_FLT_N", "*HUB_RST_N", "*BUCK_EN"]},
    {"name": "USB", "clearance": 0.127, "track_width": USB_W, "via_diameter": 0.5, "via_drill": 0.3,
     "diff_pair_width": USB_W, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 3,
     "_patterns": ["*_DP", "*_DN"]},
]
