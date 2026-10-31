"""DATA ×6 v1.0 — the porte-revues bays' drawer board: six ports behind a hub, 48 switchable pins, a logic analyzer.

The DATA ×4 v2 (electronics/data-port-x4-v2) widened to six ports for the bays whose boards stand in a slotted
tray (the density study, 2026-10-31: side-session notes › density-no-camera › DRAFT-data6.md).  Everything the
v2 does, per port and for the board, with:

* six vertical USB-C at a 15 mm pitch (the plug's overmould, not the header, sets it): each with its TPS2553-1,
  its INA226, its USBLC6 in flow-through and Rp 56k on each CC, as the v2's;
* the six 2 × 6 through-hole headers out of the ports' columns, grouped at the top: six blocks standing upright
  (2 columns × 6 rows), one empty pitch between two (the lines leave there: through-hole pins stop every layer),
  each its own colour (MINTRON MTP125-1206S1, port 1 → 6 red, yellow, green, blue, white, black).  Read from the
  front, top to bottom: the left column VREF, P1, P2, P3, P4, BOOT, the right one GND, P5, P6, P7, P8, RESET;
* per port the v2's pin chain under its block: ESD in flow-through, 100 Ω, an LSF0108 (A = the DUT's VREF,
  B = 3.3 V), to its crosspoint's X lines;
* three CH446Q at ±5 V (two ports each, their Y lines joined: the eight buses A–H), the third's STB on the
  TCA9534A's P7 (the matrix keeps one expander: one I²C write a step, the v2's driver);
* two TCA9535 (16 bits, 0x20 / 0x21) for the ports' EN, FAULT_N, RESET and BOOT, three ports each; the mark
  line to the co-processor on a spare bit of the second;
* the RP2354B as the v2's, on the hub's port 7, its ADC full: VREF 1–6 and the ±5 V rails;
* the ports' 5 V made here from the rack's 20 V (VIN, a PH 3 of its own on the rear face, VIN–GND–VIN so either
  pre-crimped lead fits, after the node's protection): two LMR51625, +5V_A for ports 1–3, +5V_B for ports 4–6,
  never in parallel (the power plane's +5V split left / right).  The logic (the hub, the co-processor, the matrix,
  the 3.3 V) keeps the v2's supply, the node's switched 5 V on the PH 8 lead's pin 8 (+5V_L): the node can still
  power-cycle the hub, and the ports stay off while the logic is.  The PH 8 lead is the v2's, pin for pin.

The board stands where the v2 stands (config/rack.yaml › pcb.data_port_x6), 120 × 80 mm (20 mm longer and 10 mm
taller), held at both ends by the cradle; every part JLC places on the front face (Economic, one side), the
headers, the leads and the SWD header soldered by hand.  Functions grouped as the study drew them (the user,
2026-10-31): top, the co-processor and its SWD left, the six blocks in the middle, the hub right; under each block
its pin chain in an 11 mm column; then the three crosspoints, a converter and an expander at either end; a corridor
for the hub's pairs; each port's switch and current sense; at the bottom the USB-C.  One PCB, two assemblies as
the v2: as drawn DATA-6x-logic; "base" leaves the logic off.
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
CORNER = CFG["corner_notch"]        # the bottom-right corner's cut (width, height): the chain foot's boss
USBS = CFG["usb"]                   # board x of the six vertical USB-C
USB_Y = TOP_Z - CFG["usb_z"]        # their axis (z 11, the port wall's openings)
BLK_X = CFG["blocks"]["x"]          # the six header blocks' centres
BLK_Y = TOP_Z - CFG["blocks"]["z"]
LEAD = (CFG["lead"][0], TOP_Z - CFG["lead"][1] - 7.0)      # J1's pin 1, its pins running down
VIN_J = (CFG["vin"][0], TOP_Z - CFG["vin"][1])             # J3's pin 2 (GND), pins 1 and 3 (VIN) either side
# The header's pins (PinHeader_2x06 upright: odd pins the left column, even the right, rows top to bottom).  Read
# from the front (the study, 2026-10-31): the left column VREF, P1, P2, P3, P4, BOOT, the right GND, P5, P6, P7,
# P8, RESET; each row pairs P k with P k + 4, as the v2's columns did
HDR_SIG = {1: "VREF", 2: "GND", 3: "P1", 4: "P5", 5: "P2", 6: "P6", 7: "P3", 8: "P7", 9: "P4", 10: "P8",
           11: "BOOT_N", 12: "RST_N"}
LEGEND = (("VREF", "GND"), ("1", "5"), ("2", "6"), ("3", "7"), ("4", "8"), ("BOOT", "RST"))
# each block's colour (rack.yaml › blocks.colours, R Y G B W K): catalog.py's hdr2x6t_<colour>, MINTRON's one series
# (alike but for the plastic), hand-soldered: out of the JLC BOM and CPL, in the board's
HDR_COLOUR = {"R": "red", "Y": "yellow", "G": "green", "B": "blue", "W": "white", "K": "black"}
# The placement, block by block (KiCad mm), the 120 mm board's (the user, 2026-10-31).  Top to bottom: the six
# blocks, each its pin chain in an 11 mm column under it; the three crosspoints, each between its two ports'
# columns, their X faces free (the TCA9535s out at the board's ends); a corridor where the hub's pairs run west to
# the ports, the lowest dropping off first; the ports' clusters; the USB-C.  The co-processor stands as on the v2,
# 31.1 mm west of it (its drawn copper carries over); the hub, J1, the second TCA9535, the LDO, VIN and converter
# B in the 26 mm right of the blocks; converter A, the first TCA9535 and the matrix's parts left of the chains
CP = (15.9, 12.9)                   # RP2354B, turned 180°: the v2's block
CP_DX = CP[0] - 47.0                # its shift from the v2's (47.0, 12.9)
HX, HY = 103.0, 39.5                # the hub, turned 90°: DN pins south, down into the corridor
XT = (HX - 8.9, HY + 1.75)          # its 24 MHz crystal
CHIP = [(34.0, 39.3), (56.0, 39.3), (78.0, 39.3)]      # the crosspoints: ports 1–2, 3–4, 5–6
EXP = [(10.4, 52.2, "GND"), (108.0, 18.5, "+3V3")]     # the TCA9535s: ports 1–3 at the west end, 4–6 at the east
MX_EXP = (9.6, 30.6)                # the matrix expander (TCA9534A), under J2: by the co-processor's RUN/BOOT
LDO = (107.0, 5.5)                  # U3, the 3.3 V LDO, in the top-right corner, tab east
BULK = (109.7, 52.6)                # VIN's 33 µF (7.7 mm tall: over the port wall's 16 mm), J3 right under it
SWD_HDR = (7.4, 26.0)               # J2, the co-processor's SWD header (1 × 5), pin 1 west, under it
SWD_PINS = (("CP_SWCLK", "SWCLK"), ("GND", "GND"), ("CP_SWDIO", "SWDIO"), ("CP_RUN", "RUN"), ("+3V3", "3V3"))
NINV = (19.5, 30.0)                 # U9, the −5 V inverter, right of it (its ferrite FB1 between the crosspoints)
CL_Y = 56.7                         # each port's power cluster: its frame's top
PWR_SPLIT = 64.6                    # the power plane: +3V3 above, +5V_A / +5V_B under (MID_X between them)
MID_X = 50.0
UP_Y = 66.5                         # over each receptacle: its VBUS 22 µF, CC resistors, LED
CH_Y = 19.3                         # each port's pin chain: its first row (the three ESD), under its block
CH_DX = 0.2                         # the LSF0108's offset east of its column's centre (its A row under the arrays)
# the hub's pairs (hs_pairs()): each port's lane in the corridor over the clusters (its centreline), and, for
# USB-C 2–6, its USBLC6 west of the receptacle and its D− on the way down to it (D+ 0.4 mm east): clear of the
# R(k+2)/R(k+3) pads of the cluster west of it and of its own USBLC6's pin 4 and 5 pads
LANES = {1: 48.5, 2: 49.6, 3: 50.7, 4: 51.8, 5: 52.9, 6: 54.0}
ESD_PX = {n: USBS[n - 1] - (6.9 if n == 2 else 7.4) for n in range(2, 7)}
DROP_DN = {n: 18.44 if n == 2 else USBS[n - 1] - 9.6 for n in range(2, 7)}
# the two 5 V converters: the bay node's LMR51625 block (bay-node/design.py) at an offset, the node's own layout:
# A west of the chains, B in the bottom-right corner (behind the port wall: nothing in it over 3 mm)
BUCKS = {"A": (2.4, -7.0), "B": (92.0, 25.4)}
# their feedback dividers (100k over 18k): B's where the node has them, over its converter; A's beside its
# converter's west side, J2 and the matrix expander taking the strip over it
FB_R = {"A": ((6.9, 35.8, 270), (6.9, 38.8, 270)),
        "B": ((4 + BUCKS["B"][0], 40.6 + BUCKS["B"][1], 0), (4 + BUCKS["B"][0], 42.2 + BUCKS["B"][1], 180))}
J1_ROT = 270


# The two crystals' blocks, the v2's (the layout review, 2026-10-28): each block's lines drawn on F.Cu with no via,
# its keep-out and DRC rule; the hub's and the co-processor's blocks stand as on the v2, so they carry over as
# they are (relative to HX, HY, XT and CP)
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
               ("RBIAS", "F.Cu", 0.127, [p63, (HX - 5.12, p63[1]), (HX - 5.12, HY + 5.2), (r1[0], HY + 5.83), r1])]
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


def xtal2_block():
    """The co-processor's crystal Y2, its lines drawn as they lay, on F.Cu with no via (the layout review,
    2026-10-28): XIN from pin 30 up between the two bottom pads to the top-right one, C48 off it; XOUT from pin 31
    up beside XIN, over C47 (no longer under its body, between its pads) to R22, then XTAL to the bottom-left pad,
    C49 off it.  No other net's track or via on F.Cu over the block (XTAL2_KEEP, XTAL2_RULE); the rear face keeps
    the slow SWD/RUN lines to J2 under it, In1's solid GND between them."""
    x = CP[0]
    pin30, pin31 = (x + 0.2, 7.95), (x - 0.2, 7.95)
    y1, y3, c48, c49, r1, r2 = (x + 2.4, 1.35), (x + 0.2, 3.05), (x + 4.4, 2.08), (x - 1.4, 1.88), (x - 1.6, 3.91), \
        (x - 1.6, 2.89)
    # the GND dog-bones of C48, C49 and Y2's top-left GND pad, where main had them (the block keeps the automatic
    # ones out; its bottom-right GND pad keeps its own, outside)
    gnd = [((x + 4.4, 1.12), (x + 5.09, 0.84), 0.25), ((x - 1.4, 0.92), (x - 2.06, 0.92), 0.25),
           ((x + 0.2, 1.35), (x + 1.24, 0.75), 0.2)]
    return [("CP_XIN", "F.Cu", 0.127, [pin30, (x + 0.2, 7.38), (x + 1.07, 6.51), (x + 1.07, 2.98), (x + 2.05, 2.0),
                                         (x + 2.4, 2.0), y1]),
            ("CP_XIN", "F.Cu", 0.127, [(x + 2.4, 2.0), (x + 2.48, 2.08), c48]),
            ("CP_XOUT", "F.Cu", 0.127, [pin31, (x - 0.2, 7.45), (x + 0.15, 7.1), (x + 0.15, 4.4), (x - 0.2, 4.05),
                                          (x - 1.46, 4.05), r1]),
            ("CP_XTAL", "F.Cu", 0.127, [r2, (x + 0.04, 2.89), y3]),
            ("CP_XTAL", "F.Cu", 0.127, [r2, (x - 1.6, 2.08), c49]),
            # beside XOUT's way up: C47 (+1V1, DVDD pin 32's 4.7 µF) straight down to its pin, and C44's +3V3_CP
            # via moved west off that line (the router had put it on it, and +1V1 round it)
            ("+1V1", "F.Cu", 0.25, [(x - 0.6, 5.98), (x - 0.6, 7.95)]),
            ("+3V3_CP", "F.Cu", 0.25, [(x - 2.2, 5.98), (x - 1.4, 6.78), (x - 1.15, 6.78)])] + \
        [("GND", "F.Cu", w, [a, v]) for a, v, w in gnd], \
        [("GND", *v, 0.5, 0.3) for _, v, _ in gnd] + [("+3V3_CP", x - 1.15, 6.78, 0.5, 0.3)]


# the co-processor crystal's block on F.Cu (xtal2_block()): Y2, C48, C49, R22 and the lines down to pins 30/31
XTAL2_KEEP = [(CP[0] + dx, y) for dx, y in ((-2.15, 0.4), (4.95, 0.4), (4.95, 2.6), (3.5, 2.6), (3.5, 4.1),
                                             (1.35, 4.1), (1.35, 6.7), (0.4, 7.3), (-0.05, 7.3), (-0.05, 4.3),
                                             (-1.05, 4.3), (-1.05, 4.45), (-2.15, 4.45))]
XTAL2_RULE = """
(rule "crystal Y2: CP_XIN, CP_XOUT, CP_XTAL and GND only over its parts on F.Cu"
	(layer F.Cu)
	(condition "(A.Type == 'Track' || A.Type == 'Via') && A.NetName != '/Co-processor/CP_XIN' && A.NetName != '/Co-processor/CP_XOUT' && A.NetName != '/Co-processor/CP_XTAL' && A.NetName != 'GND' && (A.intersectsCourtyard('Y2') || A.intersectsCourtyard('C48') || A.intersectsCourtyard('C49') || A.intersectsCourtyard('R22'))")
	(constraint disallow track via))
"""




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
# each TCA9535's 16 lines: three ports a nibble each (the v2's two halves, then a third), the mark on the second's
# P14; P14–P17 of the first and P15–P17 of the second spare (the firmware sets them as outputs, low)
EXP_LINES = [{"P00": "RST_IO", "P01": "BOOT_IO", "P02": "EN", "P03": "FLT_N"},
             {"P04": "EN", "P05": "FLT_N", "P06": "BOOT_IO", "P07": "RST_IO"},
             {"P10": "RST_IO", "P11": "BOOT_IO", "P12": "EN", "P13": "FLT_N"}]
BUSES = "ABCDEFGH"
Y_BUS = "DCBAEFGH"                  # the CH446Q's Y0–Y7 → buses (the v2's)
PU_GPIO = {"A": 19, "B": 18, "C": 17, "D": 16, "E": 13, "F": 12, "G": 11, "H": 10}
# the LSF0108's channels 1–8 → P pins.  Turned 270° (A row up), its A pins read ch8 … ch1, RefA left to right; the
# 100 Ω lines come down P1 P2 P3 P4 (the left ESD) then P8 P7 P6 P5 (the right one), so none crosses.  Its B row
# reads the same, and XMAP (the v2's) takes it round the crosspoint's face in order
LANE = (5, 6, 7, 8, 4, 3, 2, 1)
TPD_SIG = (1, 2, 4, 5)
TPD_THRU = {1: 10, 2: 9, 4: 7, 5: 6}
# the three H5VU25UC under each header, left to right (each in flow-through, its pins 1/10, 2/9, 4/7, 5/6 west to
# east): a the left column's P1–P4 (round its outside), c BOOT (the left column's foot), VREF (down the channel
# between the columns), RESET (the right column's foot), b the right column's P8–P5
ESD_X = {"a": -3.2, "c": 0.0, "b": 3.0}
# lane → crosspoint X line: port a (odd) on the chip's west face, port b on its east face (the v2's)
XMAP = {True: {1: 14, 2: 15, 3: 6, 4: 7, 5: 8, 6: 9, 7: 10, 8: 11},
        False: {8: 0, 7: 1, 6: 2, 5: 3, 4: 4, 3: 5, 2: 12, 1: 13}}
ARRAYS = {"100": ("4D02WGJ0101TCE", "C48442"), "10k": ("4D02WGJ0103TCE", "C25725"),
          "2.2k": ("4D02WGJ0222TCE", "C26075")}
# The bring-up test points (the DFT rule): bare pads on the rear face, named on B.SilkS under each; 1.5 mm on GND and
# the rails, 1.0 mm on signals; each > 2 mm from the THT pads, clear of the cradle's ends and the push band.
# ref: (net, name, pad Ø, x, y); each sheet places its own (testpoints())
TPS = {
    # the co-processor: SWD, RUN, BOOTSEL, its rails, a GND
    "TP1": ("CP_SWCLK", "SWCLK", 1.0, 7.4, 2.4), "TP2": ("CP_SWDIO", "SWDIO", 1.0, 11.6, 2.4),
    "TP3": ("GND", "GND", 1.5, 15.2, 2.6), "TP10": ("+3V3_CP", "+3V3_CP", 1.5, 7.6, 8.6),
    "TP11": ("+1V1", "+1V1", 1.5, 12.0, 15.4), "TP12": ("CP_RUN", "RUN", 1.0, 7.4, 13.0),
    "TP13": ("CP_BOOT_N", "BOOT", 1.0, 7.4, 16.0),
    # the matrix: ±5 V, the expander's bus, STB1–3 and RST, a GND
    "TP4": ("-5V", "−5V", 1.5, 19.6, 30.4), "TP5": ("+5V_MX", "+5V_MX", 1.5, 67.0, 30.4),
    "TP6": ("GND", "GND", 1.5, 21.6, 32.6), "TP14": ("MX_DAT", "DAT", 1.0, 7.2, 29.8),
    "TP15": ("MX_CK", "CK", 1.0, 11.0, 29.8), "TP16": ("MX_STB1", "STB1", 1.0, 7.2, 33.4),
    "TP17": ("MX_STB2", "STB2", 1.0, 11.0, 33.4), "TP40": ("MX_STB3", "STB3", 1.0, 14.8, 33.4),
    "TP18": ("MX_RST", "MX RST", 1.0, 15.2, 29.8), "TP19": ("GND", "GND", 1.5, 23.6, 29.6),
    # the supplies: VIN, +5V_A, +5V_B, +3V3, with GND
    "TP7": ("+3V3", "+3V3", 1.5, 13.5, 47.0), "TP8": ("GND", "GND", 1.5, 10.5, 47.0),
    "TP9": ("+5V_A", "+5V_A", 1.5, 7.5, 47.0), "TP41": ("+5V_B", "+5V_B", 1.5, 112.5, 69.5),
    "TP42": ("VIN", "VIN", 1.5, 100.0, 62.5), "TP43": ("GND", "GND", 1.5, 103.0, 62.5),
    "TP44": ("+5V_L", "+5V_L", 1.5, 88.6, 34.0),
    # the hub's reset and core rail, with a GND
    "TP20": ("HUB_RST_N", "HUB RST", 1.0, HX - 0.5, HY - 14.0), "TP21": ("GND", "GND", 1.5, HX + 3.5, HY - 14.9),
    "TP22": ("HUB_1V8", "1V8", 1.5, HX + 5.0, HY + 4.25),
    # the board side of the lead's I²C and INT, with a GND
    "TP23": ("INT", "INT", 1.0, LEAD[0] + 5.8, LEAD[1] - 0.5), "TP24": ("SDA", "SDA", 1.0, LEAD[0] + 5.8, LEAD[1] + 2.0),
    "TP25": ("SCL", "SCL", 1.0, LEAD[0] + 5.8, LEAD[1] + 4.5), "TP26": ("GND", "GND", 1.5, LEAD[0] + 5.8, LEAD[1] + 7.3),
    # GND by each expander
    "TP27": ("GND", "GND", 1.5, 16.0, 46.6), "TP28": ("GND", "GND", 1.5, 110.0, 24.6),
    # the crosspoints' eight buses (the co-processor's GPIO2–9), between the first two chips, with a GND
    **{f"TP{29 + i}": (f"BUS_{b}", b, 1.0, 44.0 + 2.2 * (i % 2), 32.5 + 2.5 * (i // 2)) for i, b in enumerate(BUSES)},
    "TP37": ("GND", "GND", 1.5, 45.1, 42.9),
    # each port's FAULT_N (port(): TP{k + 1}) by its switch
    **{f"TP{100 * n + 1}": (f"PORT{n}_FLT_N", f"FLT{n}", 1.0, USBS[n - 1] + 4.0, CL_Y + 8.0) for n in range(1, 7)},
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


def rail_v(s, net, pins, dx, d="down"):
    """Pins in one column wired dx units out to a common vertical line, tagged once at its last end."""
    for pin in pins:
        s.wire(pin, (pin, dx, 0))
    if len(pins) > 1:
        s.wire((pins[0], dx, 0), (pins[-1], dx, 0), net=net)
    s.tag(net, (pins[-1], dx, 0), d)


def rarray(s, ref, value, pairs, pcb, sch=None):
    """A 4 × 0402 array: pairs = [(a, b)] × 4, resistor k between pins k and 9 − k."""
    mpn, lcsc = ARRAYS[value]
    conns = {}
    for k, (a, b) in enumerate(pairs, 1):
        conns[str(k)], conns[str(9 - k)] = a, b
    return part(s, ref, "rarray", conns, value, pcb=pcb, fields={"MPN": mpn, "LCSC": lcsc}, sch=sch)


def exp_res(n: int, i: int):
    """Where port n's RESET / BOOT pull-ups (i 0, 1) and 1k (i 2, 3) stand, by its TCA9535: U2's (ports 1–3) in two
    columns east of it, the pull-ups then the 1k, a port to two rows; U6's (ports 4–6) in one column east of it"""
    j = (n - 1) % 3
    if n <= 3:
        return (14.4 + 2.1 * (i // 2), 48.6 + 1.15 * (2 * j + i % 2), 0)
    return (112.55, 12.6 + 1.0 * (4 * j + i), 0)


def supply(n: int) -> str:
    """Port n's 5 V: +5V_A for ports 1–3, +5V_B for ports 4–6 (the logic takes +5V_L, the lead's)"""
    return "+5V_A" if n <= 3 else "+5V_B"


# ----------------------------------------------------------------------------------------------- ports
def port(b: Board, n: int):
    cx, bx = USBS[n - 1], BLK_X[n - 1]
    k = 100 * n
    p = f"PORT{n}_"
    s = b.sheet(f"Port {n}", f"port{n}.kicad_sch", f"USB-C {n}: switch, current sense, ESD, header; pins")
    s.paper = "A2"
    sw, sh, ina, usb, esd = f"U{k + 1}", f"R{k + 6}", f"U{k + 2}", f"J{k + 1}", f"U{k + 3}"
    v5 = supply(n)
    s.frame(f"Port {n} power: {v5} → TPS2553-1 → {p}5V_SW → 100 mΩ shunt → {p}VBUS, the INA226 across the shunt",
            6, 10, 108, 44)
    s.tag(v5, (20, 18), "up")
    s.wire((20, 18), (20, 21), f"{sw}.IN")
    # the cluster in a 12 × 8 mm frame over the port's USB-C (x0, y0 its corner), the v2's; port 1's 0.6 mm east, its
    # pair coming down the west edge past its ILIM resistor
    x0, y0 = cx - (4.4 if n == 1 else 5.0), CL_Y
    part(s, sw, "vbus_sw_latch", {"IN": v5, "GND": "GND", "EN": p + "EN", "~{FAULT}": p + "FLT_N",
                                  "ILIM": p + "ILIM", "OUT": p + "5V_SW"}, pcb=P(x0 + 2.45, y0 + 2.2, 180),
         sch=at(30, 22, fields=(-4, -4)))
    C(s, f"C{k + 1}", "1u", v5, "GND", size="0402", pcb=P(x0 + 5.13, y0 + 2.9, 90), sch=at(15, 24))
    s.wire(f"C{k + 1}.1", (15, 21), (20, 21))
    R(s, f"R{k + 1}", "47k", p + "ILIM", "GND", size="0402", pcb=P(x0 - 0.97, y0 + 2.2, 180), sch=at(22, 28))
    s.wire(f"{sw}.ILIM", (22, 24), f"R{k + 1}.1")
    # the port is off until the node switches it on
    R(s, f"R{k + 2}", "10k", p + "EN", "GND", size="0402", pcb=P(x0 + 9.75, y0 + 3.65, 90), sch=at(14, 36))
    R(s, f"R{k + 3}", "10k", "+3V3", p + "FLT_N", size="0402", pcb=P(x0 + 9.75, y0 + 5.6, 90), sch=at(40, 36))
    testpoints(s, [f"TP{k + 1}"], "Test point (rear face): FAULT_N", 112, 80)
    part(s, sh, "shunt100m", {"1": p + "5V_SW", "4": p + "VBUS", "2": p + "SNS_P", "3": p + "SNS_N"},
         "100m", pcb=P(x0 + 2.77, y0 + 5.4, 0), sch=at(46, 23))
    s.wire(f"{sw}.OUT", f"{sh}.1")
    a1, a0 = INA_ADDR[n - 1]
    part(s, ina, "ina226", {"VS": "+3V3", "GND": "GND", "A1": a1, "A0": a0, "SDA": "SDA", "SCL": "SCL",
                            "~{Alert}": "INT", "Vin+": p + "SNS_P", "Vin-": p + "SNS_N", "Vbus": p + "SNS_N"},
         pcb=P(x0 + 7.51, y0 + 4.6, 90), sch=at(66, 24, fields=(-9, -7)))
    s.wire(f"{sh}.2", (52, 22), (52, 25), f"{ina}.Vin+")
    s.wire(f"{sh}.3", (50, 24), (50, 26), f"{ina}.Vin-")
    s.wire(f"{sh}.4", (46, 33), (60, 33))
    s.tag(p + "VBUS", (60, 33), "right")
    # Over the receptacle, between the cluster and it: VBUS's bulk capacitor, the CC resistors, the VBUS LED and
    # its 1k (on the switched 5 V before the shunt: the INA226 doesn't count it).  Port 1, whose USBLC6 stands
    # here too (the cradle's band leaves it no room beside its receptacle), has them shifted east of it
    ux = [cx - 2.6, cx - 0.55, cx + 0.55, cx + 2.4, cx + 4.0] if n > 1 else [cx - 0.9, cx + 0.75, cx + 1.85, cx + 3.7,
                                                                            cx + 5.3]
    C(s, f"C{k + 2}", "22u", p + "VBUS", "GND", size="0805", pcb=P(ux[0], UP_Y, 90), sch=at(55, 35.5))
    s.wire(f"C{k + 2}.1", (55, 33))
    C(s, f"C{k + 3}", "100n", "+3V3", "GND", size="0402", pcb=P(x0 + 8.03, y0 + 0.9, 180), sch=at(80, 18))
    R(s, f"R{k + 14}", "1k", p + "5V_SW", p + "LED_A", size="0402", pcb=P(ux[4], UP_Y, 90),
      sch=at(84, 30, rot=90))
    part(s, f"D{k + 1}", "led_g", {"A": p + "LED_A", "K": "GND"}, pcb=P(ux[3], UP_Y, 90),
         sch=at(94, 30, rot=180))
    s.wire(f"R{k + 14}.2", f"D{k + 1}.A")

    s.frame(f"USB-C {n} (source): Rp 56k on each CC; USBLC6 in flow-through (connector side | hub side)",
            6, 50, 108, 100)
    part(s, usb, "usbc_v", {"VBUS": p + "VBUS", "GND": "GND", "CC1": p + "CC1", "CC2": p + "CC2",
                            "D+": p + "CONN_DP", "D-": p + "CONN_DN", "SBU1": None, "SBU2": None,
                            "SHIELD": "GND"}, f"PORT{n}", pcb=P(cx, USB_Y, 0), sch=at(50, 76, fields=(-8, -11)))
    s.wire(f"{usb}.A7", f"{usb}.B7")
    s.wire(f"{usb}.A6", f"{usb}.B6")
    R(s, f"R{k + 4}", "56k", p + "VBUS", p + "CC1", size="0402", pcb=P(ux[1], UP_Y, 90), sch=at(62, 64.5))
    R(s, f"R{k + 5}", "56k", p + "VBUS", p + "CC2", size="0402", pcb=P(ux[2], UP_Y, 90), sch=at(66, 64.5))
    s.wire(f"{usb}.CC1", (62, 72), f"R{k + 4}.2")
    s.wire(f"{usb}.CC2", (66, 73), f"R{k + 5}.2")
    # The USBLC6 in the gap left of the receptacle, turned 180°: pins 1/3 east to it, 6/4 west, where the hub's
    # pair comes straight down between two clusters.  Port 1's west of its receptacle, over it (the cradle's band
    # beside it): its pair comes down the board's west edge.  Its VBUS 100 nF right over its pin 5.  ESD_PX: each
    # pair's way down between its pins' pads and the cluster west of it
    ex_ = (ESD_PX[n], USB_Y, 180) if n > 1 else (cx - 4.2, UP_Y - 0.25, 180)
    part(s, esd, "esd", {"1": p + "CONN_DN", "6": p + "DN", "3": p + "CONN_DP", "4": p + "DP", "5": v5,
                         "2": "GND"}, pcb=P(*ex_), sch=at(84, 76))
    s.wire(f"{usb}.B7", f"{esd}.1")
    s.wire(f"{usb}.A6", f"{esd}.3")
    cap = (ex_[0] + 1.0, ex_[1] - 2.6) if n > 1 else (ex_[0], ex_[1] - 2.35)
    C(s, f"C{k + 4}", "100n", v5, "GND", size="0402", pcb=P(*cap, 0), sch=at(96, 76))

    key = CFG["blocks"]["colours"][n - 1]
    s.frame(f"Header {n} (2 × 6 through-hole, {HDR_COLOUR[key]}): GND, VREF, P1–P8, "
            "RESET_N, BOOT_N; one H5VU25UC on BOOT, VREF and RESET (flow-through: VREF on to the LSF0108 and the "
            "divider, RESET/BOOT to the 1k by the expander, their expander lines pulled up)", 112, 10, 228, 56)
    hdr = {str(q): (sig if sig == "GND" else p + sig) for q, sig in HDR_SIG.items()}
    colour = HDR_COLOUR[key]
    # through-hole, soldered by hand, upright: the footprint's origin is pin 1 (the left column's top)
    part(s, f"J{k + 2}", f"hdr2x6t_{key}", hdr, f"PINS{n}", pcb=P(bx - 1.27, BLK_Y - 6.35, 0),
         sch=at(184, 30, fields=(-1, -5)))
    # BOOT, VREF and RESET through the middle H5VU25UC under the header (ESD_X); fitted on the base DATA-6x too
    part(s, f"U{k + 9}", "esd4", {"GND": "GND", "1": p + "BOOT_N", "10": p + "BOOT_N", "2": p + "VREF",
                                  "9": p + "VREF", "5": p + "RST_N", "6": p + "RST_N", "4": None, "7": None},
         pcb=P(bx + ESD_X["c"], CH_Y, 90), sch=at(214, 36, fields=(-3, -7)))
    # the 1k and the expander lines' pull-ups by the expander (exp_res())
    for i, (r, sig, sy) in enumerate(((f"R{k + 7}", "RST", 34), (f"R{k + 8}", "BOOT", 44))):
        R(s, r, "1k", p + sig + "_IO", p + sig + "_N", size="0402", pcb=P(*exp_res(n, 2 + i)),
          sch=at(150, sy, rot=90))
    for i, (r, sig) in enumerate(((f"R{k + 9}", "RST"), (f"R{k + 10}", "BOOT"))):
        R(s, r, "100k", "+3V3", p + sig + "_IO", size="0402", pcb=P(*exp_res(n, i)), sch=at(138, (34, 44)[i] - 5))
        s.wire(f"{r}.2", (138, (34, 44)[i]), f"R{k + 7 + i}.1")
        s.wire((128, (34, 44)[i]), (138, (34, 44)[i]), net=p + sig + "_IO")
        s.tag(p + sig + "_IO", (128, (34, 44)[i]), "left")

    chip = (n - 1) // 2
    s.frame(f"Pins {n}: ESD in flow-through, 100 Ω, LSF0108 (A = the DUT's VREF, "
            f"B = 3.3 V) to crosspoint {('U7', 'U8', 'U12')[chip]}'s X lines", 6, 104, 228, 146)
    # the P lines' two H5VU25UC either side of the middle one: a P1–P4, b P8–P5, west to east
    for j, (side, qs) in enumerate((("a", (1, 2, 3, 4)), ("b", (8, 7, 6, 5)))):
        tpd = {"GND": "GND"}
        for pin, q in zip(TPD_SIG, qs):
            tpd[str(pin)] = tpd[str(TPD_THRU[pin])] = f"{p}P{q}"
        part(s, f"U{k + 5 + j}", "esd4", tpd, pcb=P(bx + ESD_X[side], CH_Y, 90),
             sch=at(28 + 36 * j, 128, fields=(-3, -7)))
    # the 100 Ω arrays right under them, turned 270° (each resistor upright, its P end up; pins 4 … 1 west to east):
    # the a array 0.2 mm west of its ESD, the b array 0.6 mm east of the middle, their lines straight into the A row
    rarray(s, f"RN{k + 1}", "100", [(f"{p}P{q}", f"{p}A{q}") for q in (4, 3, 2, 1)],
           P(bx - 3.0, CH_Y + 2.35, 270), sch=at(50, 128))
    rarray(s, f"RN{k + 2}", "100", [(f"{p}P{q}", f"{p}A{q}") for q in (5, 6, 7, 8)],
           P(bx + 2.4, CH_Y + 2.35, 270), sch=at(86, 128))
    lsf = {"GND": "GND", "RefA": p + "VREF", "RefB": p + "VREFB", "EN": p + "VREFB", "EPAD": "GND"}
    for c in range(1, 9):
        lsf[f"A{c}"] = f"{p}A{LANE[c - 1]}"
        lsf[f"B{c}"] = f"{p}B{LANE[c - 1]}"
    # turned 270°: A row up (ch8 … ch1, RefA), B row down in the same order, RefB and EN at its east end
    part(s, f"U{k + 7}", "lsf0108", lsf, pcb=P(bx + CH_DX, CH_Y + 6.7, 270), sch=at(132, 128, fields=(-10, -8)))
    rail(s, "GND", [f"U{k + 7}.GND", f"U{k + 7}.EPAD"], 2, "down")
    # Vref_B and EN from +5V_MX through 200k (the v2's: each group a voltage domain of its own), east of the LSF0108
    # by its RefB/EN end
    R(s, f"R{k + 11}", "200k", "+5V_MX", p + "VREFB", size="0402", pcb=P(bx + 4.2, CH_Y + 5.4, 180),
      sch=at(162, 122))
    C(s, f"C{k + 5}", "100n", p + "VREFB", "GND", size="0402", pcb=P(bx + 4.2, CH_Y + 7.3, 0), sch=at(162, 130))
    s.wire(f"R{k + 11}.2", f"C{k + 5}.1")
    # VREF / 2 to the co-processor's ADC through 100k (the v2's divider: an unwired VREF stays ≈ 0.4 V), on the
    # side its B lines leave free: under R/C east for a port west of its crosspoint (odd), west for the other
    dvx, dvy = (bx + 4.2, CH_Y + 8.3) if n % 2 else (bx - 4.0, CH_Y + 5.3)
    R(s, f"R{k + 12}", "10k", p + "VREF", f"CP_VREF{n}", size="0402", pcb=P(dvx, dvy, 0), sch=at(180, 122))
    R(s, f"R{k + 13}", "10k", f"CP_VREF{n}", "GND", size="0402", pcb=P(dvx, dvy + 1.0, 180), sch=at(180, 130))
    s.wire(f"R{k + 12}.2", f"R{k + 13}.1")
    R(s, f"R{k + 15}", "100k", f"CP_VREF{n}", f"CP_ADC{n}", size="0402", pcb=P(dvx, dvy + 2.0, 180),
      sch=at(196, 136, rot=90))
    s.part(f"#FLG{k + 1}", "power:PWR_FLAG", "PWR_FLAG", "", {"1": p + "VREF"}, in_bom=False, on_board=False,
           sch=at(200, 120))
    s.part(f"#FLG{k + 2}", "power:PWR_FLAG", "PWR_FLAG", "", {"1": p + "VREFB"}, in_bom=False, on_board=False,
           sch=at(212, 120))

    e = (n - 1) // 3
    s.notes_at = (112, 62, 116)
    hp = n - 1 if n > 1 else 6
    s.notes = [f"Port {n} = hub port {hp}, busid 1-1.{hp}; supplied by {v5}.",
               f"INA226 at 0x{INA_HEX[n - 1]:02x}; expander {('U2', 'U6')[e]} (TCA9535, 0x{0x20 + e:02x}).",
               "ILIM 47k: 0.50–0.62 A; the -1 latches off after 7.5 ms in limit, FAULT_N flags it.",
               "INA226 Vbus on the shunt's load-side sense pad (= VBUS).",
               "EN pulled down: the port stays off until the node switches it on.",
               "Pins: P1–P8 → LSF0108 ch5 6 7 8 4 3 2 1 (LANE) → crosspoint X lines (XMAP, the DATA ×4 v2's;",
               "  a third chip for ports 5–6).  An unwired VREF stays ≈ 0.4 V, under the LSF0108's 0.65 V: the",
               "  firmware keeps the port's crosspoint switches open while its VREF reads under 0.65 V.",
               f"ESD (flow-through): P1–P4 U{k + 5}, P5–P8 U{k + 6}, BOOT_N / VREF / RESET_N U{k + 9}.",
               "VREF: the board's I/O supply, 0.95–3.6 V; a 5 V board with TTL inputs: its own 3.3 V pin.",
               "Source only (Rp from the switched VBUS); a back-feeding source trips the TPS2553 (latched).",
               "The DUT's RESET/BOOT pull-ups ≥ 4.7k: against 1k, the 1k in series stops at ≈ 1.65 V.",
               f"Header: {colour}; left column VREF 1 2 3 4 BOOT, right GND 5 6 7 8 RESET."]


# ------------------------------------------------------------------------------------------ 20 V → 5 V
def power_sheet(b: Board):
    s = b.sheet("Power", "power.kicad_sch", "20 V input, two 5 V converters")
    s.paper = "A2"
    s.frame("VIN: the rack's 20 V from the node (after its reverse protection), a PH 3 VIN–GND–VIN on the rear face",
            6, 10, 62, 50)
    # through-hole on the rear face, soldered by hand, as J1; its lead comes up behind the board.  VIN on both outer
    # pins, GND in the middle: a pre-crimped PH lead "same direction" or "reversed" fits either way (on a PH 2 a reversed
    # one would swap VIN and GND, the grounds already joined through the PH 8: the node's VIN short to GND); ≈ 0.85 A
    # at 20 V for six ports at 0.5 A, on two contacts
    # lying, its pins along the board (pin 1 west), its lead from the drag chain's foot right under it
    part(s, "J3", "ph3v", {"1": "VIN", "2": "GND", "3": "VIN"}, "VIN",
         pcb={**P(VIN_J[0] - 2.0, VIN_J[1], 0, "bottom"), "solid": ["1", "2", "3"]},
         sch=at(16, 30, mirror="y", fields=(-2, -6)))
    s.part("#FLG08", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "VIN"}, in_bom=False, on_board=False, sch=at(28, 18))
    # the input's bulk against a hot plug's overshoot (the node's lead is ≈ 50 cm, the converters' ceramics alone
    # ring), right over J3, before either converter's 10 µF
    part(s, "C60", "cap33u50", {"1": "VIN", "2": "GND"}, "33u", pcb=P(*BULK, 0),
         sch=at(40, 30))
    # EN 100k/10k, as the node's: both converters start above 13.5 V and stop below 10.8 V; by converter B
    R(s, "R50", "100k", "VIN", "BUCK_EN", size="0402", pcb=P(97.1, 61.6, 90), sch=at(29, 41.5))
    R(s, "R51", "10k", "BUCK_EN", "GND", size="0402", pcb=P(98.2, 61.6, 90), sch=at(29, 48.5))
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
        part(s, f"L{2 + i}", "buck_l47", {"1": lx, "2": out}, "4.7u", pcb=P(15.7 + dx, 44 + dy, 0),
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
    testpoints(s, ["TP9", "TP41", "TP42", "TP43"], "Test points (rear face): +5V_A, +5V_B, VIN, GND", 6, 78)
    s.notes_at = (6, 56, 200)
    s.notes = [
        "Two LMR51625 as the bay node's (TI SLUSF64B table 8-1: 4.7 µH FXL0630, 2 × 10 µF + 100 nF in, 3 × 22 µF out).",
        "+5V_A: ports 1–3; +5V_B: ports 4–6 (the logic takes +5V_L, J1.8).  Never in parallel: the power plane's +5V",
        "  split left / right.  Each 1.5 A at 0.5 A a port, 1.86 A at the TPS2553s' 0.62 A limit (≈ 1 W lost each).",
        "VIN on J3 (PH 3: 1 VIN, 2 GND, 3 VIN): either pre-crimped lead direction fits.",
        "FB 100k/18k: 5.24 V, as the node's.  EN 100k/10k: on above 13.5 V, off below 10.8 V.",
        "VIN from the node's VRACK after its reverse-protection P-FET (node rev. B): no second protection here.",
        "  ≈ 0.95 A at 20 V, 0.7 A at 28 V; a PH contact carries 2 A.",
    ]


# ----------------------------------------------------------------------------------- hub, lead, 3.3 V
def hub_sheet(b: Board):
    s = b.sheet("Hub", "hub.kicad_sch", "Lead, hub, expanders, 3.3 V")
    s.paper = "A2"
    s.frame("Lead from the node's J7 (PH 8, rear face): I²C and INT through an H5VU25UC; pin 8 the logic's 5 V",
            6, 10, 70, 50)
    # the v2's J1, pin for pin, where the v2 has it.  Its pin 8, the node's switched 5 V (DUT_5V, its TPS2553: 1.34 A),
    # feeds the logic as on the v2 (+5V_L: the 3.3 V LDO, the matrix's +5V_MX): the node still power-cycles the hub,
    # and with the logic off the expanders' pins float and the EN pull-downs keep every port off.  The ports' 5 V
    # comes from VIN (power_sheet()).  Solid to its pad, as the v2's J1.8
    part(s, "J1", "ph8t", {"1": "LEAD_INT", "2": "LEAD_SCL", "3": "LEAD_SDA", "4": "GND", "5": "UP_DN",
                           "6": "UP_DP", "7": "GND", "8": "+5V_L"}, "LEAD",
         pcb={**P(*LEAD, J1_ROT, "bottom"), "solid": ["8"]}, sch=at(16, 30, mirror="y", fields=(-2, -6)))
    s.part("#FLG01", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+5V_L"}, in_bom=False, on_board=False, sch=at(28, 16))
    s.part("#FLG02", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "GND"}, in_bom=False, on_board=False, sch=at(34, 16))
    # the lead's bulk, the v2's C1 (22 µF 1206), by pin 8
    C(s, "C1", "22u", "+5V_L", "GND", size="1206", pcb=P(LEAD[0] - 3.4, LEAD[1] + 12.5, 90), sch=at(64, 30))
    part(s, "U4", "esd4", {"D1+": "LEAD_SDA", "D1-": "LEAD_SCL", "D2+": "LEAD_INT", "D2-": None, "GND": "GND"},
         pcb=P(LEAD[0] + 2.75, LEAD[1] - 0.6, 90), sch=at(48, 30, fields=(-3, -6)))

    s.frame("3.3 V for the hub, the expanders, the INA226s and the co-processor (AP2114H, SOT-223 on copper)",
            6, 56, 70, 86)
    s.tag("+5V_L", (24, 66), "up")
    s.wire((24, 66), (24, 69), "U3.VI")
    part(s, "U3", "ldo_1a", {"VI": "+5V_L", "VO": "+3V3", "GND": "GND"}, pcb=P(*LDO, 0),
         sch=at(34, 69, fields=(-3, -4)))
    C(s, "C2", "22u", "+5V_L", "GND", size="0805", pcb=P(LDO[0] + 5.6, LDO[1] + 1.8, 90), sch=at(20, 72))
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
    # its south face's DN1–5 to USB-C 2–6: the pairs come down into the corridor over the clusters and turn west in
    # lanes, the lowest dropping off first, none crossing (drawn: hs_pairs()).  Its west face's DN6 to USB-C 1: west
    # over the crystal's keep-out, north round it and down its west side into the corridor's top lane; DN7 under
    # it to the co-processor, down to B.Cu under the hub's body
    for dn in range(1, 7):
        n = dn + 1 if dn <= 5 else 1
        hub[f"USBDN{dn}_DP/PRT_DIS_P{dn}"] = f"PORT{n}_DP"
        hub[f"USBDN{dn}_DM/PRT_DIS_M{dn}"] = f"PORT{n}_DN"
    hub["USBDN7_DP/PRT_DIS_P7"], hub["USBDN7_DM/PRT_DIS_M7"] = "CP_HUB_DP", "CP_HUB_DN"
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
                                           (["HUB_CFG2", "HUB_SWP7", "HUB_SWP6", None], HX + 3.5, HY + 7.6, 90))):
        up = ("HUB_CFG1", "HUB_CFG2")
        rarray(s, f"RN{1 + i}", "10k", [(net, ("+3V3" if net in up else "GND") if net else None) for net in nets],
               P(x, y, rot), sch=at(126 + 12 * i, 92, rot=180, fields=(3, 0)))
        rail(s, "GND", [f"RN{1 + i}.{9 - q}" for q in range(1, 5) if nets[q - 1] and nets[q - 1] not in up], 2, "down")
        if nets[0] in up:
            rail(s, "+3V3", [f"RN{1 + i}.8"], 2, "down")

    s.frame("Two TCA9535 expanders, three ports each: EN, FAULT_N, RESET, BOOT; the mark on U6's P14", 172, 10, 232, 104)
    # no RESET pin (the TCA6408A's): power-on reset only.  Its 100 nF right over VCC
    for i, (ref, cref, (x, y, addr), sy) in enumerate((("U2", "C18", EXP[0], 30), ("U6", "C19", EXP[1], 74))):
        exp = {"VCC": "+3V3", "GND": "GND", "EPAD": "GND", "A0": addr, "A1": "GND", "A2": "GND", "SCL": "SCL",
               "SDA": "SDA", "~{INT}": "INT"}
        for j in range(3):
            for pin, sig in EXP_LINES[j].items():
                exp[pin] = f"PORT{3 * i + j + 1}_{sig}"
        if i == 1:
            exp["P14"] = "MARK"
        # the spare pins pulled down by 10k (an array under the pull-ups): an input reads 0 rather than float until
        # the firmware sets it as an output, and an output set high by mistake drives 0.33 mA
        spare = [pin for pin in ("P14", "P15", "P16", "P17") if pin not in exp]
        for pin in spare:
            exp[pin] = f"EXP{i + 1}_{pin}"
        part(s, ref, "tca9535", exp, pcb=P(x, y, 0), sch=at(202, sy, fields=(-4, -12)))
        C(s, cref, "100n", "+3V3", "GND", size="0402", pcb=P(x, y - 3.6, 90), sch=at(184, sy - 10))
        # the spares' array: U2's under it, U6's west of it
        rarray(s, f"RN{10 + i}", "10k", [(f"EXP{i + 1}_{pin}", "GND") for pin in spare] + [(None, None)] * (4 - len(spare)),
               P(x, y + 3.75, 90) if i == 0 else P(x - 4.0, y, 0), sch=at(224, sy + 16))
        rail(s, "GND", [f"RN{10 + i}.{9 - q}" for q in range(1, len(spare) + 1)], 2, "down")

    s.frame("I²C isolation: open with the board's 3.3 V off (the node's pull-ups can't feed it)", 172, 106, 232, 148)
    for i, (q, r, line, val) in enumerate((("Q1", "R6", "SDA", "4.7k"), ("Q2", "R7", "SCL", "4.7k"),
                                           ("Q3", "R8", "INT", "10k"))):
        y = LEAD[1] + 2.5 + 4.0 * i
        part(s, q, "nfet", {"G": "+3V3", "S": line, "D": "LEAD_" + line}, pcb=P(LEAD[0] + 2.75, y, 90),
             sch=at(186, 118 + 12 * i))
        R(s, r, val, "+3V3", line, size="0402", pcb=P(LEAD[0] + 2.75, LEAD[1] + 13.1 + 1.0 * i, 0),
          sch=at(212, 116 + 12 * i))
    testpoints(s, ["TP7", "TP8", "TP44", "TP20", "TP21", "TP22", "TP23", "TP24", "TP25", "TP26", "TP27", "TP28"],
               "Test points (rear face, bare pads, not in the BOM): +3V3, the hub's reset and 1.8 V, the lead's "
               "I²C and INT, GND", 6, 136, per_row=12)
    s.notes_at = (6, 108, 160)
    s.notes = [
        "Hub reset: U5 (MAX809S, 2.93 V, ≥ 150 ms, push-pull) on RESET_N (errata DS80000628A, Module 2).",
        "Hub: CFG_SEL[2:0] = 110 (internal default configuration, strap options disabled: DS00001598C Table 5-2),",
        "  as the DATA ×4 v2's; all seven downstream ports used.",
        "Hub ports: 1–5 = USB-C 2–6 (busid 1-1.1 … 1-1.5), 6 = USB-C 1 (1-1.6), 7 = the co-processor (1-1.7).",
        "Expanders: TCA9535 U2 0x20 (ports 1–3), U6 0x21 (ports 4–6, the mark on P14).  Each port: RESET, BOOT, EN,",
        "  FAULT_N (port 1 on P00–P03, 2 on P04–P07, 3 on P10–P13).  Inputs at power-up: the EN pull-downs keep every",
        "  port off until the node writes; the spare pins set as outputs, low, by the firmware.",
        "INT (J1.1 → the node's IO4): both expanders' INT and the six INA226 ALERTs, open drain, wired-OR, through Q3.",
        "I²C: TCA9535 0x20 / 0x21, INA226 0x41 / 0x43 / 0x44 / 0x45 / 0x47 / 0x4C, TCA9534A 0x38; the node's INA226 0x40.",
        "J1 pin 8 (the node's switched +5V, ≤ 1.34 A) feeds the logic (+5V_L: U3, +5V_MX); the ports take theirs",
        "  from VIN (sheet Power).  With +5V_L off, the expanders' pins float and the EN pull-downs keep the ports off.",
        "J1 (through-hole) stands on the rear face: soldered by hand (the PCBA places the front face only).",
    ]


# ------------------------------------------------------------------------------------ matrix (full)
def matrix_sheet(b: Board):
    s = b.sheet("Matrix", "matrix.kicad_sch", "Crosspoints, −5 V, the node's matrix expander")
    s.paper = "A2"
    for c, (chx, chy) in enumerate(CHIP):
        na, nb = 2 * c + 1, 2 * c + 2
        u = ("U7", "U8", "U12")[c]
        x0, y0 = (6, 10 + 52 * c)
        s.frame(f"Crosspoint {u} (CH446Q at ±5 V, serial addressing): X = ports {na}–{nb}'s pins, Y0–Y7 = buses {Y_BUS}",
                x0, y0, x0 + 104, y0 + 48)
        conns = {"VDD": "+5V_MX", "VEE": "-5V", "GND": "GND", "DAT": "MX_DAT", "CS/CK": "MX_CK", "STB": f"MX_STB{c + 1}",
                 "RST": "MX_RST", "P/~{S}": "GND", **{f"AX{i}": "GND" for i in range(4)},
                 **{f"AY{i}": "GND" for i in range(3)}}
        for i in range(8):
            conns[f"Y{i}"] = f"BUS_{Y_BUS[i]}"
        for port_n, west in ((na, True), (nb, False)):
            for lane, x in XMAP[west].items():
                conns[f"X{x}"] = f"PORT{port_n}_B{LANE[lane - 1]}"
        part(s, u, "ch446q", conns, pcb=P(chx, chy), sch=at(x0 + 48, y0 + 24, fields=(-8, -14)))
        rail(s, "GND", [f"{u}.{q}" for q in (40, 21, 20, 42, 19, 18, 43, 12)], 2, "down")
        c0 = (20, 23, 56)[c]
        C(s, f"C{c0}", "100n", "+5V_MX", "GND", size="0402", pcb=P(chx + 0.8, chy - 7.75, 90),
          sch=at(x0 + 72, y0 + 8))
        C(s, f"C{c0 + 1}", "1u", "+5V_MX", "GND", size="0402", pcb=P(chx + 2.0, chy - 7.75, 90),
          sch=at(x0 + 78, y0 + 8))
        C(s, f"C{c0 + 2}", "100n", "-5V", "GND", size="0402", pcb=P(chx - 0.8, chy + 7.75, 270),
          sch=at(x0 + 24, y0 + 40))

    s.frame("+5V_MX through a ferrite (the crosspoints, the inverter, the LSF0108s' bias); −5 V for the "
            "crosspoints' VEE (TPS60400 inverter)", 114, 10, 228, 52)
    part(s, "FB1", "fb600", {"1": "+5V_L", "2": "+5V_MX"}, pcb=P(67.0, 34.0, 90), sch=at(124, 18))
    s.wire("FB1.1", ("FB1.1", -3, 0))
    s.tag("+5V_L", ("FB1.1", -3, 0), "left")
    s.wire("FB1.2", ("FB1.2", 3, 0))
    s.tag("+5V_MX", ("FB1.2", 3, 0), "right")
    s.part("#FLG06", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+5V_MX"}, in_bom=False, on_board=False,
           sch=at(132, 14))
    part(s, "U9", "tps60400", {"IN": "+5V_MX", "OUT": "-5V", "C_{FLY+}": "CP_FLYP", "C_{FLY-}": "CP_FLYN", "GND": "GND"},
         pcb=P(*NINV, 0), sch=at(150, 30, fields=(-4, -6)))
    C(s, "C26", "1u", "CP_FLYP", "CP_FLYN", size="0402", pcb=P(NINV[0], NINV[1] + 2.8, 0), sch=at(170, 36))
    C(s, "C27", "1u", "+5V_MX", "GND", size="0402", pcb=P(NINV[0] - 3.1, NINV[1] + 0.05, 180), sch=at(132, 34))
    C(s, "C28", "1u", "-5V", "GND", size="0402", pcb=P(NINV[0] - 3.1, NINV[1] - 1.0, 180), sch=at(186, 36))

    s.frame("The node's matrix expander (TCA9534A, 0x38): the crosspoints and the co-processor's RUN / BOOTSEL",
            114, 58, 228, 100)
    part(s, "U10", "tca9534", {"VDD": "+3V3", "GND": "GND", "A0": "GND", "A1": "GND", "A2": "GND", "SCL": "SCL",
                               "SDA": "SDA", "~{INT}": None, "P0": "MX_DAT", "P1": "MX_CK", "P2": "MX_STB1",
                               "P3": "MX_STB2", "P4": "MX_RST", "P5": "CP_RUN", "P6": "CP_BOOT_N", "P7": "MX_STB3"},
         pcb=P(*MX_EXP, 0), sch=at(160, 84, fields=(-10, -8)))
    rail_v(s, "GND", ["U10.A0", "U10.A1", "U10.A2"], -2, "down")
    C(s, "C29", "100n", "+3V3", "GND", size="0402", pcb=P(MX_EXP[0] + 4.5, MX_EXP[1] - 1.6, 90), sch=at(140, 74))
    R(s, "R20", "10k", "+3V3", "MX_RST", size="0402", pcb=P(MX_EXP[0] + 4.5, MX_EXP[1] + 2.0, 90), sch=at(190, 76))
    s.notes_at = (114, 102, 110)
    s.notes = ["CH446Q serial mode (P/S low): 7 address bits on CK, data on DAT, latched by STB; RST high = all open.",
               "TCA9534A 0x38: P0 DAT, P1 CK, P2 STB U7, P3 STB U8, P4 RST, P5 RUN, P6 BOOTSEL, P7 STB U12.",
               "  The mark (co-processor GPIO14) moved to the TCA9535 U6's P14.",
               "RUN and BOOTSEL are open drain emulated (output register 0, the pin switched to output).",
               "±5 V on purpose: at a single 5 V R_on is 120–225 Ω, and a 1.8 V board's I²C low would fail."]
    testpoints(s, ["TP4", "TP5", "TP6", "TP14", "TP15", "TP16", "TP17", "TP40", "TP18", "TP19", "TP29", "TP30",
                   "TP31", "TP32", "TP33", "TP34", "TP35", "TP36", "TP37"],
               "Test points (rear face, logic only): ±5 V, the expander's bus, STB1–3 and RST, buses A–H, GND",
               114, 114, per_row=10, pitch=10)


# -------------------------------------------------------------------------------- co-processor (full)
def coproc_sheet(b: Board):
    s = b.sheet("Co-processor", "coproc.kicad_sch", "RP2354B analyzer / co-processor on hub port 7")
    cx, cy = CP
    s.paper = "A2"
    s.frame("RP2354B, wired like a Pico 2 (gusmanb's PICO_2 UF2 runs as it is); its decoupling", 6, 10, 120, 118)
    gp = {"GPIO0": "CP_TRIG", "GPIO1": "CP_TRIG", "GPIO14": "MARK", "GPIO25": "CP_LED",
          "GPIO46/ADC6": "CP_SNS_5V", "GPIO47/ADC7": "CP_SNS_N5V"}
    for i, bus in enumerate(BUSES):
        gp[f"GPIO{2 + i}"] = f"BUS_{bus}"
        gp[f"GPIO{PU_GPIO[bus]}"] = f"CP_PU_{bus}"
    # VREF 1–6 / 2 on GPIO40, 43, 42, 41, 44, 45 (1–4 the v2's: ports 2 and 4 swapped so their lines leave pins 52 and
    # 54 for B.Cu without crossing, round C45), the ±5 V rails on GPIO46–47: the ADC full
    for n, g in enumerate((40, 43, 42, 41, 44, 45)):
        gp[f"GPIO{g}/ADC{g - 40}"] = f"CP_ADC{n + 1}"
    for g in [15] + list(range(20, 25)) + list(range(26, 40)):
        gp[f"GPIO{g}"] = None
    rp = {"IOVDD": "+3V3_CP", "QSPI_IOVDD": "+3V3_CP", "USB_OTP_VDD": "+3V3_CP", "ADC_AVDD": "+3V3_CP",
          "VREG_VIN": "+3V3_CP", "VREG_AVDD": "CP_VREG_AVDD", "VREG_PGND": "GND", "VREG_LX": "CP_VREG_LX",
          "VREG_FB": "+1V1", "DVDD": "+1V1", "GND": "GND", "XIN": "CP_XIN", "XOUT": "CP_XOUT",
          "USB_DP": "CP_DP", "USB_DM": "CP_DN", "RUN": "CP_RUN", "~{QSPI_SS}": "CP_QSPI_SS",
          "SWCLK": "CP_SWCLK", "SWDIO": "CP_SWDIO", "QSPI_SCLK": None, "QSPI_SD0": None, "QSPI_SD1": None,
          "QSPI_SD2": None, "QSPI_SD3": None, **gp}
    part(s, "U11", "rp2354b", rp, pcb=P(cx, cy, 180), sch=at(60, 70, fields=(-10, -27)))
    rail(s, "+3V3_CP", ["U11.USB_OTP_VDD", "U11.ADC_AVDD", "U11.QSPI_IOVDD", "U11.IOVDD", "U11.VREG_VIN"], -3)
    rail(s, "+1V1", ["U11.VREG_FB", "U11.DVDD"], -5)
    rail(s, "GND", ["U11.VREG_PGND", "U11.GND"], 2, "down")
    rail_v(s, "CP_TRIG", ["U11.GPIO0", "U11.GPIO1"], 2, "right")
    s.part("#FLG04", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+1V1"}, in_bom=False, on_board=False, sch=at(196, 38))
    s.frame("Its 3.3 V from +3V3 through a ferrite, the core regulator as Raspberry Pi lays it out (3.3 µH, 3 × 4.7 µF, 33 Ω)",
            124, 10, 228, 52)
    s.tag("+3V3", (140, 22), "up")
    part(s, "FB2", "fb600", {"1": "+3V3", "2": "+3V3_CP"}, pcb=P(cx - 8.5, 4.6, 0), sch=at(150, 25, rot=90))
    s.wire((140, 22), (140, 25), "FB2.1")
    s.part("#FLG07", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+3V3_CP"}, in_bom=False, on_board=False,
           sch=at(166, 20))
    C(s, "C31", "4.7u", "+3V3_CP", "GND", size="0402", pcb=P(cx - 5.4, 4.6, 90), sch=at(160, 28))
    s.wire("FB2.2", (160, 25), "C31.1")
    s.wire((160, 25), (168, 25), net="+3V3_CP")
    s.tag("+3V3_CP", (168, 25), "right")
    part(s, "L1", "l3u3_vreg", {"1": "+1V1", "2": "CP_VREG_LX"}, pcb=P(cx - 3.0, cy + 8.65, 180),
         sch=at(136, 42, rot=90))
    for ref, net, dy, sx in (("C32", "+3V3_CP", 6.06, 180), ("C33", "+1V1", 7.0, 146)):      # CIN, COUT
        C(s, ref, "4.7u", net, "GND", size="0402", pcb=P(cx - 3.0, cy + dy, 180),
          sch=at(sx, 44)).footprint = "bench:C_0402_1005Metric_RP"
    R(s, "R21", "33", "+3V3_CP", "CP_VREG_AVDD", size="0402", pcb=P(cx - 5.2, cy + 8.45, 90),
      sch=at(160, 42, rot=90))
    C(s, "C34", "4.7u", "CP_VREG_AVDD", "GND", size="0402", pcb=P(cx - 5.2, cy + 6.5, 90),
      sch=at(168, 44))
    s.wire("R21.2", (168, 42), "C34.1")
    s.part("#FLG05", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "CP_VREG_AVDD"}, in_bom=False, on_board=False,
           sch=at(208, 38))
    decap = [(cx - 6.7, cy - 3.8, 180), (cx - 6.7, cy - 1.8, 180), (cx - 6.7, cy + 3.6, 180),
             (cx + 0.7, cy + 7.4, 270), (cx + 3.0, cy + 7.4, 270), (cx + 6.4, cy + 5.6, 0),
             (cx + 6.6, cy - 5.9, 0), (cx + 4.45, cy - 7.4, 90), (cx + 3.0, cy - 7.4, 90),
             (cx - 2.2, cy - 7.4, 90)]
    for i, (x, y, rot) in enumerate(decap):
        C(s, f"C{35 + i}", "100n", "+3V3_CP", "GND", size="0402", pcb=P(x, y, rot), sch=at(12 + 5 * i, 24))
    rail(s, "+3V3_CP", [f"C{35 + i}.1" for i in range(10)], -1)
    rail(s, "GND", [f"C{35 + i}.2" for i in range(10)], 1, "down")
    for i, (x, y, rot) in enumerate(((cx - 6.62, cy + 0.2, 180), (cx + 7.0, cy + 4.4, 0), (cx - 0.6, cy - 7.4, 90))):
        C(s, f"C{45 + i}", "4.7u" if i == 2 else "100n", "+1V1", "GND", size="0402", pcb=P(x, y, rot),
          sch=at(70 + 5 * i, 24))
    rail(s, "+1V1", [f"C{45 + i}.1" for i in range(3)], -1)
    rail(s, "GND", [f"C{45 + i}.2" for i in range(3)], 1, "down")
    s.frame("12 MHz crystal (ABM8-272-T3, 15 pF, 1k on XOUT), USB on hub port 7 (22 Ω), RUN, BOOTSEL, LED, SWD",
            124, 56, 228, 98)
    part(s, "Y2", "xtal12", {"1": "CP_XIN", "3": "CP_XTAL", "2": "GND", "4": "GND"}, pcb=P(cx + 1.3, 2.2, 180),
         sch=at(140, 68, fields=(-2, -4)))
    C(s, "C48", "15p", "CP_XIN", "GND", size="0402", pcb=P(cx + 4.4, 1.6, 90), sch=at(134, 72))
    C(s, "C49", "15p", "CP_XTAL", "GND", size="0402", pcb=P(cx - 1.4, 1.4, 90), sch=at(146, 72))
    s.wire("Y2.1", (134, 68), "C48.1")
    s.wire("Y2.3", (146, 68), "C49.1")
    R(s, "R22", "1k", "CP_XOUT", "CP_XTAL", size="0402", pcb=P(cx - 1.6, 3.4, 90),
      sch=at(156, 68, rot=270))
    s.wire("C49.1", (146, 68), "R22.2")
    usb22 = {"LCSC": "C25092", "MPN": "0402WGF220JTCE", "Manufacturer": "UNI-ROYAL(Uniroyal Elec)"}
    R(s, "R23", "22", "CP_DP", "CP_HUB_DP", size="0402", pcb=P(cx + 2.4, cy + 10.4, 270), fields=usb22,
      sch=at(140, 84, rot=90))
    R(s, "R24", "22", "CP_DN", "CP_HUB_DN", size="0402", pcb=P(cx + 1.3, cy + 10.4, 270), fields=usb22,
      sch=at(140, 90, rot=90))
    R(s, "R25", "10k", "+3V3_CP", "CP_RUN", size="0402", pcb=P(cx - 3.8, 5.4, 0),
      sch=at(166, 84))
    R(s, "R26", "1k", "CP_BOOT_N", "CP_QSPI_SS", size="0402", pcb=P(cx + 3.5, cy + 10.4, 270),
      sch=at(178, 86, rot=90))
    R(s, "R27", "1k", "CP_LED", "CP_LED_A", size="0402", pcb=P(cx - 8.7, cy + 9.8, 90),
      sch=at(178, 68, rot=90))
    part(s, "D1", "led_g", {"A": "CP_LED_A", "K": "GND"}, pcb=P(cx - 8.7, cy + 6.9, 90),
         sch=at(188, 68, rot=180))
    s.wire("R27.2", "D1.A")
    testpoints(s, ["TP1", "TP2", "TP3", "TP10", "TP11", "TP12", "TP13"],
               "Test points (rear face, logic only): SWD, RUN, BOOTSEL, rails, GND", 54, 140)
    s.frame("SWD header (J2, 1 × 5, by hand): Debug Probe 1–3", 6, 140, 50, 162)
    part(s, "J2", "hdr5", {str(i + 1): net for i, (net, _) in enumerate(SWD_PINS)}, "SWD", pcb=P(*SWD_HDR, 90),
         sch=at(28, 150))
    s.frame("Bus pull-ups: 10k to 3.3 V always (the LSFs' B side), 2.2k switched by the co-processor "
            "(GPIO10–13, 16–19); the ±5 V rails into the ADC", 124, 102, 228, 144)
    # the 2.2k arrays right of the east face by the enables (A at the top), the 10k arrays under them
    for j in range(2):
        rarray(s, f"RN{8 + j}", "10k", [(f"BUS_{BUSES[i]}", "+3V3") for i in range(4 * j, 4 * j + 4)],
               P(cx + 7.1, cy + 9.5 + 2.6 * j, 0), sch=at(134 + 12 * j, 124))
        rail(s, "+3V3", [f"RN{8 + j}.{q}" for q in (8, 7, 6, 5)], -2)
    for j in range(2):
        rarray(s, f"RN{6 + j}", "2.2k", [(f"CP_PU_{BUSES[i]}", f"BUS_{BUSES[i]}") for i in range(4 * j, 4 * j + 4)],
               P(cx + 7.4, cy - 2.8 + 3.0 * j, 0), sch=at(162 + 12 * j, 124))
    R(s, "R38", "100k", "+5V_MX", "CP_SNS_5V", size="0402", pcb=P(cx - 9.2, cy - 0.6, 0),
      sch=at(196, 118))
    R(s, "R39", "47k", "CP_SNS_5V", "GND", size="0402", pcb=P(cx - 9.2, cy + 0.5, 0),
      sch=at(196, 128))
    s.wire("R38.2", "R39.1")
    R(s, "R40", "10k", "+3V3_CP", "CP_SNS_N5V", size="0402", pcb=P(cx - 9.2, cy + 1.6, 0),
      sch=at(212, 118))
    R(s, "R41", "100k", "CP_SNS_N5V", "-5V", size="0402", pcb=P(cx - 9.2, cy + 2.7, 0),
      sch=at(212, 128))
    s.wire("R40.2", "R41.1")
    s.notes_at = (6, 122, 112)
    s.notes = ["GPIO2–9 = buses A–H (gusmanb CH1–8, 8-bit mode); GPIO0 → GPIO1 bridged (its trigger path).",
               "GPIO14 = the node's mark (TCA9535 U6 P14); GPIO25 = LED; GPIO19…16, 13…10 = pull-up enables A…H (2.2k);",
               "GPIO40, 43, 42, 41, 44, 45 = VREF 1–6 / 2 (through 100k); GPIO46 = +5V_MX × 47/147;",
               "  GPIO47 = 3.3 V − (3.3 + 5) × 10/110 from −5 V (2.55 V nominal).  The ADC's eight inputs all used.",
               "RUN pulled up, BOOTSEL (QSPI_SS) through 1k: both held by the node (TCA9534A), open drain.",
               "USB on the hub's port 7 (Full Speed, 22 Ω).",
               "Core regulator: Raspberry Pi's Minimal R4 block turned 180°; L1's dot (pad 1) on +1V1, not VREG_LX.",
               "C47 (DVDD pin 32, furthest from the regulator) 4.7 µF; no copper under LX / L1 (In1, In2, B.Cu)."]


# ---------------------------------------------------------------------------------------- drawn copper
def offset(poly, d):
    """A polyline (mm) shifted d mm sideways, mitred at its corners: to the west when it heads down the board (+y),
    to the north when it heads west, to the east when it heads up.  A differential pair's two lines from its
    centreline (the v2's)."""
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


def hs_pairs():
    """The USB pairs, drawn (the v2's HS review, 2026-10-22: over a continuous GND reference, F.Cu above In1;
    Freerouting puts them on B.Cu, each line its own way).  D− and D+ either side of each pair's centreline
    (offset(), D− on its right-hand side), USB_W lines 0.15 mm apart (≈ 90 Ω: the USB netclass); they leave the
    hub's pins at their 0.5 mm pitch and close up.  No length-matching bumps (the layout review: on USB they make it
    worse).
    * USB-C 2–6 (the south face, DN1–5): down side by side under the hub (ports 3 and 4, 5 and 6 each 50 µm out
      from their pins' centre: C15 and C16, pins 5 and 10's 100 nF, between them), west in the corridor's lanes
      (LANES), the lowest dropping off first, each down past the cluster west of it (DROP_DN) to its USBLC6: D+
      into pin 4, D− on past it to pin 6.
    * USB-C 1 (the west face, DN6): west between C12 and the crystal's keep-out, north round it, west, down its
      west side into the top lane, west under the crosspoints, up over converter A's outputs and down the board's
      west edge to its USBLC6 over its receptacle.
    The upstream pair and the co-processor's (pins 58/59, 55/56: boxed in by USB-C 1's pair, C13 and the crystal's
    keep-out, they leave under the hub's body) are left to the router for now.  Returns (tracks, vias)."""
    tracks, vias = [], []
    hp, c = (USB_W + 0.15) / 2, 0.8
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

    for n, (pin, d) in {2: (1, 0.0), 3: (3, -0.05), 4: (6, 0.05), 5: (8, -0.05), 6: (11, 0.05)}.items():
        px = HX - 3.5 + 0.5 * (pin - 1)                 # its pins' centre
        x, y, xd = px + d, LANES[n], DROP_DN[n] + hp
        p4, p6 = esd_pins(ESD_PX[n], USB_Y)
        # each line straight out of its pin, then in to the pair's pitch by y top + 0.4 (C15/C16 just under)
        cl = [(x, top + 0.4), (x, y - c), (x - c, y), (xd + c, y), (xd, y + c), (xd, p4[1] - 0.4)]
        dn = keep([(px - 0.25, sy), (px - 0.25, top)] + offset(cl, hp) +
                  [(xd - hp, p6[1] - 0.5), (xd - hp + 0.5, p6[1]), p6])
        dp = keep([(px + 0.25, sy), (px + 0.25, top)] + offset(cl, -hp) + [(xd + hp + 0.4, p4[1]), p4])
        tracks += [(f"PORT{n}_DN", "F.Cu", USB_W, dn), (f"PORT{n}_DP", "F.Cu", USB_W, dp)]

    # USB-C 1: north round the keep-out at x 95, west at y 35.9, down at x 90.7; up over converter A from x 26.5,
    # down the west edge at x 5.9
    p4, p6 = esd_pins(USBS[0] - 4.2, UP_Y - 0.25)
    y1, xe, ye = LANES[1], 5.85, 46.6
    cl = [(HX - 4.9, HY - 1.45), (95.0 + c, HY - 1.45), (95.0, HY - 1.45 - c), (95.0, 35.9 + c), (95.0 - c, 35.9),
          (90.7 + c, 35.9), (90.7, 35.9 + c), (90.7, y1 - c), (90.7 - c, y1), (26.5, y1), (26.5 - (y1 - ye), ye),
          (xe + c, ye), (xe, ye + c), (xe, p4[1] - 0.4)]
    # D+ straight out of pin 54 (its line on the pin's row), D− in from pin 53 by 0.1 mm: clear of C12's pad
    dn = keep([(HX - 4.4125, HY - 1.75), (HX - 4.8, HY - 1.75)] + offset(cl, hp) +
              [(xe - hp, p6[1] - 0.5), (xe - hp + 0.5, p6[1]), p6])
    dp = keep([(HX - 4.4125, HY - 1.25), (HX - 4.9, HY - 1.25)] + offset(cl, -hp) + [(xe + hp + 0.4, p4[1]), p4])
    tracks += [("PORT1_DN", "F.Cu", USB_W, dn), ("PORT1_DP", "F.Cu", USB_W, dp)]

    return tracks, vias


def drawn():
    """The copper drawn before the routing that the v2 already had round its co-processor and its hub, which
    stand here as on the v2 (the co-processor CP_DX west of it, the hub one row lower): the core regulator as
    Raspberry Pi lays it out, the crystals' blocks, each 100 nF in the pin → cap → via order, the exposed pads'
    vias.  Returns (tracks, vias, the regulator's F.Cu zones, the hole they need in the F.Cu GND pour)."""
    hand_tracks, hand_vias = [], []
    # the co-processor's 3.3 V (+3V3_CP) into its In2 island right past FB2, C31 and R25: from R25's pad down to
    # a via in the island (the feed used to reach the island through IOVDD pin 41, under the case), so that each
    # IOVDD pin can reach the rail through its own 100 nF alone
    r25 = (CP[0] - 4.31, 5.4)                                           # R25's +3V3_CP pad
    hand_tracks.append(("+3V3_CP", "F.Cu", 0.25, [r25, (CP[0] - 4.485, 5.575), (CP[0] - 4.485, 7.4)]))
    hand_vias.append(("+3V3_CP", CP[0] - 4.485, 7.4, 0.5, 0.3))
    # C35 (IOVDD pin 41's 100 nF) in the pin → cap → via order: the pin straight west into it, C35 on north-east
    # to its via in the island (the pin's line under the case to the island's via gone)
    c35 = (CP[0] - 6.22, CP[1] - 3.8)                                   # C35's +3V3_CP pad
    hand_tracks.append(("+3V3_CP", "F.Cu", 0.25, [(CP[0] - 4.95, c35[1]), c35, (c35[0], c35[1] - 0.18),
                                                  (CP[0] - 5.75, CP[1] - 4.45)]))
    hand_vias.append(("+3V3_CP", CP[0] - 5.75, CP[1] - 4.45, 0.5, 0.3))
    # C37 (IOVDD pins 59 and 60's 100 nF) likewise: the two pins bridged and west into it, C37 on south-east to
    # its via in the island, where the router had it (the pins' line under the case to pin 64's via gone)
    c37 = (CP[0] - 6.22, CP[1] + 3.6)                                   # C37's +3V3_CP pad
    v37 = (40.7998 + CP_DX, 17.3915)                                            # its via, as routed (its B.Cu run to R21)
    hand_tracks += [("+3V3_CP", "F.Cu", 0.25, [(CP[0] - 4.95, CP[1] + 3.4), (CP[0] - 4.95, CP[1] + 3.8)]),
                    ("+3V3_CP", "F.Cu", 0.25, [(CP[0] - 4.95, c37[1]), c37, (40.3442 + CP_DX, 16.9358), v37])]
    hand_vias.append(("+3V3_CP", *v37, 0.5, 0.3))
    # C38 (IOVDD pins 68 and 69's 100 nF) likewise: the two pins bridged, pin 69 down-east into C38, C38 on west
    # to its via in the island (pin 69's via under the case and its line on to pin 76 gone; CP_DP, which ran
    # between the pins and C38, left to the router)
    c38 = (CP[0] + 0.7, CP[1] + 6.92)                                   # C38's +3V3_CP pad
    hand_tracks += [("+3V3_CP", "F.Cu", 0.25, [(CP[0] - 1.0, CP[1] + 4.95), (CP[0] - 0.6, CP[1] + 4.95)]),
                    ("+3V3_CP", "F.Cu", 0.25, [(CP[0] - 0.6, CP[1] + 4.95), (CP[0] - 0.6, CP[1] + 5.62), c38,
                                               (c38[0] - 0.65, c38[1])])]
    hand_vias.append(("+3V3_CP", c38[0] - 0.65, c38[1], 0.5, 0.3))
    # C39 (IOVDD pin 76's 100 nF): the pin down into it, C39 on east to its own via in the island (its nearest
    # via was past C40 and pin 5), the line going on to C40 as the router had it
    c39 = (CP[0] + 3.0, CP[1] + 6.92)                                   # C39's +3V3_CP pad
    hand_tracks.append(("+3V3_CP", "F.Cu", 0.25, [(CP[0] + 2.2, CP[1] + 4.95), (CP[0] + 2.2, CP[1] + 6.12), c39,
                                                  (c39[0] + 1.6, c39[1]), (CP[0] + 5.92, CP[1] + 5.6)]))
    hand_vias.append(("+3V3_CP", c39[0] + 0.6, c39[1], 0.5, 0.3))
    # C43 and C42 (IOVDD pin 24's two 100 nF): the pin up into C43, C43 on into C42, C42 down to its via in the
    # island, south of it (MX_DAT, MX_CK and MX_RST run along the north side on B.Cu); the pin's line under the
    # case (to its via, pin 29 and pin 15) gone
    c43, c42 = (CP[0] + 3.0, CP[1] - 6.92), (CP[0] + 4.45, CP[1] - 6.92)     # their +3V3_CP pads
    hand_tracks.append(("+3V3_CP", "F.Cu", 0.25, [(CP[0] + 2.6, CP[1] - 4.95), (CP[0] + 2.6, CP[1] - 6.52), c43, c42,
                                                  (c42[0], CP[1] - 6.25)]))
    hand_vias.append(("+3V3_CP", c42[0], CP[1] - 6.25, 0.5, 0.3))
    # CP_DP (the co-processor's USB D+, Full Speed) from pin 67 up along the south pad row's inner edge, under the
    # case (0.15 mm there, its netclass's 0.127 mm from CP_DN and from the pads), to B.Cu east of CP_ADC3's line,
    # and on down to R23: it ran between pins 68-69 and C38, where pin 69 now goes down to its capacitor
    hand_tracks += [("CP_DP", "F.Cu", 0.15, [(CP[0] - 1.4, CP[1] + 4.95), (CP[0] - 1.4, CP[1] + 4.32),
                                             (CP[0] - 0.12, CP[1] + 4.32), (CP[0] + 0.1, CP[1] + 4.1)]),
                    ("CP_DP", "B.Cu", 0.25, [(CP[0] + 0.1, CP[1] + 4.1), (CP[0] + 0.1, CP[1] + 5.7), (48.379 + CP_DX, 19.879),
                                             (48.379 + CP_DX, 22.134)]),
                    ("CP_DP", "F.Cu", 0.25, [(48.379 + CP_DX, 22.134), (48.744 + CP_DX, 22.134), (49.4 + CP_DX, 22.79)])]
    hand_vias += [("CP_DP", CP[0] + 0.1, CP[1] + 4.1, 0.5, 0.3), ("CP_DP", 48.379 + CP_DX, 22.134, 0.5, 0.3)]
    # the co-processor's west face round C45 (DVDD pin 51's 100 nF, right west of it): pin 51 to C45, C45's GND
    # down to its via; VREF4 (pin 52) and VREF2 (pin 54) to B.Cu right by their pins, 4's via east, 2's west (the
    # v2's).  C45 is the order rule's one exception there (pin 51's via under the case into +1V1, as the v2's)
    ux, uy = CP[0] - 4.95, CP[1]                                       # U11's west pad column
    hand_tracks += [("+1V1", "F.Cu", 0.2, [(ux, uy + 0.2), (CP[0] - 6.14, uy + 0.2)]),
                    ("GND", "F.Cu", 0.25, [(CP[0] - 7.1, uy + 0.2), (CP[0] - 7.1, uy + 0.85)]),
                    ("CP_ADC4", "F.Cu", 0.127, [(ux, uy + 0.6), (ux - 0.55, uy + 0.6), (ux - 0.8, uy + 0.85)]),
                    ("CP_ADC2", "F.Cu", 0.127, [(ux, uy + 1.4), (ux - 1.13, uy + 1.4), (ux - 1.35, uy + 1.18)])]
    hand_vias += [("GND", CP[0] - 7.1, uy + 0.85, 0.5, 0.3), ("CP_ADC4", ux - 0.8, uy + 0.85, 0.5, 0.3),
                  ("CP_ADC2", ux - 1.35, uy + 1.18, 0.5, 0.3)]
    # the hub's reset supervisor in the pin → cap → via order: VCC (U5 pin 3) straight up to C6, C6 on east to
    # its via
    hand_tracks.append(("+3V3", "F.Cu", 0.25, [(HX - 2.2, HY - 11.038), (HX - 2.2, HY - 12.7), (HX - 1.5, HY - 12.7)]))
    hand_vias.append(("+3V3", HX - 1.5, HY - 12.7, 0.5, 0.3))
    hand_vias += [("GND", HX + 1.2 * i, HY + 1.2 * j, 0.5, 0.3) for i in (-1, 0, 1) for j in (-1, 0, 1)]
    hand_tracks += [("GND", "F.Cu", 0.2, [(HX + 4.4125, HY + 2.75), (HX + 2.95, HY + 2.75), (HX + 2.25, HY + 2.05),
                                          (HX, HY)]),
                    ("GND", "F.Cu", 0.2, [(HX + 3.75, HY + 7.1), (HX + 3.25, HY + 7.1)]),
                    # its via over pads 6 / 7, away from pad 8 (CFG_SEL2's pull-up, +3V3 since CFG_SEL 110)
                    ("GND", "F.Cu", 0.2, [(HX + 3.25, HY + 7.1), (HX + 3.5, HY + 6.85), (HX + 3.5, HY + 6.45)])]
    hand_vias.append(("GND", HX + 3.5, HY + 6.45, 0.5, 0.3))
    t, v = xtal_block()
    hand_tracks += t
    hand_vias += v
    t, v = xtal2_block()
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
    # and the crystal's and C43's GND fan-outs kept where the routing expects them (the auto fan-out moves them
    # once the SWD lines pass under the crystal)
    y2g, c43g = (CP[0] + 1.3 + 1.1, 3.05), (CP[0] + 3.0, 5.02)
    hand_tracks += [("GND", "F.Cu", 0.25, [y2g, (50.533 + CP_DX, 3.519)]), ("GND", "F.Cu", 0.25, [c43g, (c43g[0], 4.39)])]
    hand_vias += [("GND", 50.533 + CP_DX, 3.519, 0.5, 0.3), ("GND", c43g[0], 4.39, 0.5, 0.3)]
    # The core regulator's copper as Raspberry Pi draws it (the datasheet's Fig. 26, their RP2350B Minimal R4-S1
    # file), turned 180° with U11 (the audit's fix 2; coproc_sheet() places the parts at their coordinates).  VREG
    # pins 61 AVDD, 62 PGND, 63 LX, 64 VIN, 65 FB at x − 3.8 … − 2.2 on the south row (y + 4.9); CIN (C32) and
    # COUT (C33) at x − 3.0, their GND pads west.  Their copper areas (VREG below): LX between CIN's and COUT's
    # pads to L1's LX pad; +1V1 from COUT to L1's dotted pad and the two V_OUT vias; PGND from its pin over CIN's
    # and COUT's GND to its two adjacent vias, the one point where the regulator's current meets the GND plane.
    # CFILT (C34) on its own GND via; VREG_FB taken at the V_OUT vias, away from LX.  The tracks under the areas
    # are what the router sees (it knows no copper areas): pin to pad centres, straight and 45° only
    ux, uy = CP
    pin = {n: (ux - 3.8 + 0.4 * (n - 61), uy + 4.9) for n in range(61, 66)}
    cin_v, cin_g = (ux - 2.485, uy + 6.06), (ux - 3.515, uy + 6.06)     # C32: +3V3_CP, GND (RP's land, ±0.515)
    cout_v, cout_g = (ux - 2.485, uy + 7.0), (ux - 3.515, uy + 7.0)     # C33: +1V1, GND
    l_out, l_lx = (ux - 2.3, uy + 8.65), (ux - 3.7, uy + 8.65)          # L1: pad 1 +1V1 (the dot), pad 2 LX
    pg_vias = [(ux - 4.1, uy + 6.35), (ux - 4.1, uy + 6.95)]
    out_vias = [(ux - 1.7, uy + 6.6), (ux - 1.7, uy + 7.2)]
    cfilt_v, cfilt_g, rfilt = (ux - 5.2, uy + 6.98), (ux - 5.2, uy + 6.02), (ux - 5.2, uy + 7.94)
    cfilt_via = (ux - 4.8, uy + 5.3)
    vin_via = (ux - 2.6, uy + 3.85)
    hand_tracks += [("+3V3_CP", "F.Cu", 0.25, [pin[64], (pin[64][0], cin_v[1]), cin_v]),
                    ("GND", "F.Cu", 0.25, [pin[62], (pin[62][0], cin_g[1]), cin_g]),
                    ("GND", "F.Cu", 0.3, [cin_g, cout_g]),
                    *(("GND", "F.Cu", 0.3, [v, g]) for v, g in zip(pg_vias, (cin_g, cout_g))),
                    ("CP_VREG_LX", "F.Cu", 0.3, [pin[63], (ux - 3.0, uy + 7.5), (ux - 3.7, uy + 8.2), l_lx]),
                    ("+1V1", "F.Cu", 0.3, [cout_v, (cout_v[0], l_out[1]), l_out]),
                    ("+1V1", "F.Cu", 0.3, [cout_v, (ux - 2.1, uy + 7.0), (ux - 1.9, uy + 7.2), out_vias[1]]),
                    ("+1V1", "F.Cu", 0.3, [out_vias[1], out_vias[0]]),
                    ("+1V1", "F.Cu", 0.15, [pin[65], (ux - 2.2, uy + 5.5), (ux - 1.9, uy + 5.8), (ux - 1.9, uy + 6.4),
                                            out_vias[0]]),
                    ("CP_VREG_AVDD", "F.Cu", 0.2, [pin[61], (ux - 3.8, uy + 5.05), (ux - 4.64, uy + 5.89),
                                                   (ux - 4.64, uy + 6.42), cfilt_v]),
                    ("CP_VREG_AVDD", "F.Cu", 0.2, [cfilt_v, rfilt]),
                    ("GND", "F.Cu", 0.25, [cfilt_g, (ux - 5.2, uy + 5.7), cfilt_via]),
                    # the V_OUT vias joined on B.Cu too (Raspberry Pi's +1V1 trunk starts there); VREG_VIN inwards from
                    # its pin to a via into the +3V3_CP island (In2) under the package: the block's +3V3_CP way out
                    ("+1V1", "B.Cu", 0.3, [out_vias[0], out_vias[1]]),
                    ("+3V3_CP", "F.Cu", 0.25, [pin[64], vin_via])]
    hand_vias += ([("GND", *v, 0.6, 0.3) for v in pg_vias] + [("+1V1", *v, 0.6, 0.3) for v in out_vias] +   # RP's
                  [("GND", *cfilt_via, 0.6, 0.3), ("+3V3_CP", *vin_via, 0.5, 0.3)])                     # 0.6 mm vias
    # Raspberry Pi's copper areas (Minimal R4-S1's F.Cu zones, x and y turned about U11) with their settings (solid
    # on their pads, 0.15 mm from the other nets, 0.15 mm wide at least), inside a hole of the F.Cu GND pour
    # (VREG_HOLE): the PGND area meets the main GND only through its two vias, and no copper lies under L1's body
    # or beside LX
    VREG = [("+1V1", "vreg-out", [(-2.65, 6.75), (-2.65, 9.5), (-1.95, 9.5), (-1.95, 7.7), (-2.25, 7.4),
                                  (-2.25, 7.25), (-2.05, 7.25), (-1.85, 7.45), (-1.65, 7.45), (-1.4, 7.2), (-1.4, 6.55),
                                  (-1.6, 6.35)]),
            ("CP_VREG_LX", "vreg-lx", [(-2.9, 4.6), (-2.9, 5.4), (-2.85, 5.45), (-2.85, 7.6), (-3.35, 8.1),
                                       (-3.35, 9.5), (-4.05, 9.5), (-4.05, 7.8), (-3.75, 7.5), (-3.3, 7.5),
                                       (-3.15, 7.35), (-3.15, 5.45)]),
            ("GND", "vreg-pgnd", [(-3.3, 4.6), (-3.3, 6.3), (-3.45, 6.3), (-3.45, 6.75), (-3.3, 6.75), (-3.3, 7.25),
                                  (-4.1, 7.25), (-4.4, 6.95), (-4.4, 6.2), (-3.5, 5.3)]),
            ("+3V3_CP", "vreg-vin", [(-2.5, 4.15), (-2.5, 5.55), (-2.25, 5.8), (-2.25, 6.3), (-2.7, 6.3)])]
    vreg_zones = [{"layer": "F.Cu", "net": net, "name": name, "priority": 3, "connection": "solid", "clearance": 0.15,
                   "min_width": 0.15, "poly": [(ux + x, uy + y) for x, y in poly]} for net, name, poly in VREG]
    VREG_HOLE = [(ux - 4.55, uy + 3.9), (ux - 1.25, uy + 3.9), (ux - 1.25, uy + 9.75), (ux - 4.55, uy + 9.75)]
    # and the exposed pad down to the GND plane: a via between its paste windows, drawn (Freerouting doesn't
    # always fan the pad out); more of them, and its buses can't pass under the pad on B.Cu
    hand_vias.append(("GND", ux + 0.565, uy + 0.565, 0.5, 0.3))
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
    # pin 64's: the pin down to C11 (its 100 nF) right below the corner, and its via inwards, under the hub's
    # body, off that line (it sat on it, between the pin and C11).  C11 is an exception to the pin → cap → via
    # order: no via fits past its +3V3 pad, between R1's RBIAS pad west and port 1's D− east
    p64 = (HX - 4.4125, HY + 3.75)                                      # U1 pin 64
    hand_tracks += [("+3V3", "F.Cu", 0.25, [p64, (HX - 4.7, p64[1] + 0.2875), (HX - 4.7, HY + 5.72)]),
                    ("+3V3", "F.Cu", 0.25, [p64, (HX - 3.6, HY + 3.6)])]
    hand_vias.append(("+3V3", HX - 3.6, HY + 3.6, 0.5, 0.3))
    return hand_tracks, hand_vias, vreg_zones, VREG_HOLE


# ---------------------------------------------------------------------------------------------- board
def logic_only(b: Board) -> list[str]:
    """The parts the base DATA-6x leaves off: the matrix and co-processor sheets whole, and per port its pin
    chain (the two H5VU25UC on P1–P8, the 100 Ω arrays, the LSF0108, its Vref_B 200k and 100 nF, the VREF divider
    and its 100k to the ADC).  The BOOT/VREF/RESET ESD stays."""
    refs = [p.ref for p in b.parts.values() if p.sheet and p.sheet.name in ("Matrix", "Co-processor")]
    for n in range(1, 7):
        k = 100 * n
        refs += [f"U{k + 5}", f"U{k + 6}", f"RN{k + 1}", f"RN{k + 2}", f"U{k + 7}", f"R{k + 11}", f"C{k + 5}",
                 f"R{k + 12}", f"R{k + 13}", f"R{k + 15}"]
    return sorted(r for r in refs if r in b.parts and b.parts[r].in_bom and not r.startswith("#"))


def board() -> Board:
    b = Board("data-port-x6", "DATA ×6", "1.0",
              comments=["A porte-revues bay's drawer board: six USB-C behind a hub, 48 switchable pins on 8 buses, "
                        "a logic analyzer (hw-testing-rack)",
                        "Generated from electronics/data-port-x6/design.py — edit the Python, then regenerate"])
    b.root_paper, b.root_buses = "A2", True
    b.root_notes = [
        "DATA ×6 v1.0 — USB2517I hub (7 ports), six USB-C each with a TPS2553-1, an INA226 and ESD, two TCA9535",
        "  for EN/FAULT/RESET/BOOT, an AP2114H 3.3 V; two LMR51625 make the ports' 5 V from VIN (20 V, PH 3);",
        "  the logic runs on the lead's switched 5 V (J1.8), as the v2's.",
        "Pins: 48 on three CH446Q (±5 V), LSF0108 per port, an RP2354B analyzer on hub port 7, a TCA9534A for the",
        "  matrix and the co-processor's RUN/BOOTSEL.  Standing behind the port wall, one face assembled.",
        "Headers: six 2 × 6 blocks at the top, one colour per port (red, yellow, green, blue, white, black).",
        "Lead pinout here: 1 INT · 2 SCL · 3 SDA · 4 GND · 5 D− · 6 D+ · 7 GND · 8 +5V — the DATA ×4 v2's lead.",
        "I²C: TCA9535 0x20 / 0x21, INA226 0x41 / 0x43 / 0x44 / 0x45 / 0x47 / 0x4C, TCA9534A 0x38; the node's 0x40.",
        "Assembled as DATA-6x-logic (as drawn) or DATA-6x (BOM/CPL '-base': the matrix, the co-processor and the",
        "  ports' pin chains not fitted).",
        "Rails: VIN 20 V (13.5–28 V; on above 13.5 V), ≤ 0.85 A at 20 V · +5V_A / +5V_B 5.24 V, ≤ 1.86 A each (ports",
        "  1–3 / 4–6 at the 0.62 A limit) · +5V_L 4.75–5.24 V (the node's switched 5 V over the lead), ≤ 0.46 A ·",
        "  PORTn_VBUS 5.1–5.24 V, 0.50–0.62 A limit ·",
        "  +3V3 3.3 V (AP2114H), ≤ 0.5 A (the hub 0.42 A at most) · +3V3_CP 3.3 V (FB2), ≤ 60 mA · +1V1 1.1 V (the",
        "  RP2354B's regulator), ≤ 0.1 A · +5V_MX 5.2 V (FB1), ≤ 10 mA · −5V −4.9 to −5.2 V (TPS60400), ≤ 1 mA ·",
        "  HUB_1V8 / HUB_1V8PLL 1.8 V (the hub's own regulators).",
    ]
    hub_sheet(b)
    power_sheet(b)
    for n in range(1, 7):
        port(b, n)
    matrix_sheet(b)
    coproc_sheet(b)

    cw, ch = CORNER
    outline = [(0, 0, 1.0), (W, 0, 1.0), (W, H - ch, 0.5), (W - cw, H - ch, 0.5), (W - cw, H, 0)]
    for x0, x1, top in reversed(NOTCHES):
        outline += [(x1, H, 0), (x1, top, 0.5), (x0, top, 0.5), (x0, H, 0)]
    outline += [(0, H, 1.0)]
    # The power plane (In2): +3V3 over the top of the board, down to the split under the clusters (PWR_SPLIT); under
    # it, +5V_A west of x 50 (ports 1–3) and +5V_B east (ports 4–6), 0.2 mm apart, never joined.  +5V_A reaches its
    # area from under converter A (west, middle) down the cradle's west band (nothing else uses it, either face);
    # converter B stands in its own, the bottom-right corner.  Each port switch's IN takes its 5 V by a track down
    # past the split, as the v2's.  All 1.4 mm from the edge, notches included
    E = 1.4
    bottom = [pt for x0, x1, top in reversed(NOTCHES)
              for pt in ((x1 + E, H - E), (x1 + E, top - E), (x0 - E, top - E), (x0 - E, H - E))]
    TONGUE = (31.5, 23.0, 46.2)         # +5V_A under converter A: top, east edge, bottom (the west band below it)
    IN_5VA = [(E, TONGUE[0]), (TONGUE[1], TONGUE[0]), (TONGUE[1], TONGUE[2]), (5.4, TONGUE[2]),
              (5.4, PWR_SPLIT + 0.1), (MID_X - 0.1, PWR_SPLIT + 0.1),
              *[pt for pt in bottom if pt[0] < MID_X], (MID_X - 0.1, H - E), (E, H - E)]
    IN_5VB = [(MID_X + 0.1, PWR_SPLIT + 0.1), (W - E, PWR_SPLIT + 0.1), (W - E, H - ch - E), (W - cw - E, H - ch - E),
              (W - cw - E, H - E), *[pt for pt in bottom if pt[0] > MID_X], (MID_X + 0.1, H - E)]
    IN_3V3 = [(E, E), (W - E, E), (W - E, PWR_SPLIT - 0.1), (5.6, PWR_SPLIT - 0.1), (5.6, TONGUE[2] + 0.2),
              (TONGUE[1] + 0.2, TONGUE[2] + 0.2), (TONGUE[1] + 0.2, TONGUE[0] - 0.2), (E, TONGUE[0] - 0.2)]
    # the co-processor's +3V3_CP island on In2 under its package and 100 nF ring (the v2's: each capacitor's via, past
    # its +3V3_CP pad, lands in it)
    ISLAND = [(CP[0] - 6.65, CP[1] - 8.15), (CP[0] + 6.1, CP[1] - 8.15), (CP[0] + 6.1, CP[1] + 8.1),
              (CP[0] - 6.65, CP[1] + 8.1)]
    hand_tracks, hand_vias, vreg_zones, VREG_HOLE = drawn()
    ux, uy = CP
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
        "power_nets": {"GND": 1, "VIN": 2, "+5V_A": 2, "+5V_B": 2, "+5V_L": 2, "+5V_MX": 2, "-5V": 2, "+3V3": 2, "+3V3_CP": 2,
                       "+1V1": 2, "PORT?_VBUS": 2, "PORT?_5V_SW": 2},
        "stitch": 4.0,
        "edge_fence": {"pitch": 5.0, "inset": 0.9},
        "zones": [{"layer": "In1.Cu", "net": "GND"},
                  {"layer": pwr, "net": "+3V3", "name": "pwr-3v3", "poly": IN_3V3},
                  {"layer": pwr, "net": "+5V_A", "name": "pwr-5va", "poly": IN_5VA},
                  {"layer": pwr, "net": "+5V_B", "name": "pwr-5vb", "poly": IN_5VB},
                  {"layer": pwr, "net": "+3V3_CP", "name": "pwr-3v3cp", "priority": 1, "poly": ISLAND},
                  {"layer": "F.Cu", "net": "GND", "holes": [VREG_HOLE]}, {"layer": "B.Cu", "net": "GND"},
                  *vreg_zones],
        "tracks": hand_tracks, "vias": hand_vias,
        "dru": XTAL_RULE + XTAL2_RULE,
        "keepouts": [
            # the crystals' blocks (dropped once routed) and the core regulator's, as the v2's
            {"name": "core:xtal-y1", "layers": ["F.Cu", "B.Cu"], "poly": XTAL_KEEP},
            {"name": "core:xtal-y2", "layers": ["F.Cu"], "poly": XTAL2_KEEP},
            {"name": "core:vreg-block", "layers": ["F.Cu"], "tracks_only": True,
             "poly": [(ux - 4.55, uy + 5.4), (ux - 1.95, uy + 5.4), (ux - 1.95, uy + 9.75), (ux - 4.55, uy + 9.75)]},
            {"name": "lx-under", "layers": ["In1.Cu", "In2.Cu", "B.Cu"] + (["In3.Cu", "In4.Cu"] if six else []),
             "poly": [(ux - 3.3, uy + 4.95), (ux - 2.7, uy + 4.95), (ux - 2.7, uy + 7.62), (ux - 1.9, uy + 7.62),
                      (ux - 1.9, uy + 9.82), (ux - 4.2, uy + 9.82), (ux - 4.2, uy + 7.62), (ux - 3.3, uy + 7.62)]}] + [
            {"name": f"edge{i}", "poly": [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]}
                     for i, (x0, y0, x1, y1) in enumerate((
                         (0, 0, W, 0.35), (W - 0.35, 0, W, H), (0, H - 0.35, W, H), (0, 0, 0.35, H),
                         (W - cw - 0.35, H - ch - 0.35, W, H),
                         *((x0 - 0.35, top - 0.35, x1 + 0.35, H) for x0, x1, top in NOTCHES)))] + [
            # B.Cu runs over the power plane: no B.Cu track crosses its splits (+3V3 / +5V, +5V_A / +5V_B, the +5V_A
            # tongue's edges), so a signal that does crosses on F.Cu over the GND plane (the v2's RF review)
            {"name": name, "layers": ["B.Cu", "In3.Cu"] if six else ["B.Cu"], "tracks_only": True,
             "poly": [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]}
            for name, (x0, y0, x1, y1) in (
                ("split", (0.35, PWR_SPLIT - 0.5, W - 0.35, PWR_SPLIT + 0.5)),
                ("split-ab", (MID_X - 0.5, PWR_SPLIT, MID_X + 0.5, H - 0.35)),
                ("split-5va-top", (0.35, TONGUE[0] - 0.6, TONGUE[1] + 0.6, TONGUE[0] + 0.4)),
                ("split-5va-east", (TONGUE[1] - 0.4, TONGUE[0] - 0.6, TONGUE[1] + 0.6, TONGUE[2] + 0.6)),
                ("split-5va-foot", (5.0, TONGUE[2] - 0.4, TONGUE[1] + 0.6, TONGUE[2] + 0.6)),
                ("split-5va-band", (5.0, TONGUE[2] - 0.4, 6.0, PWR_SPLIT)))],
        "variants": {"base": {"dnp": logic_only(b)}},
        "texts": [
            {"text": "DATA ×6 v1.0", "x": 50.0, "y": 78.0, "size": 0.8},
            # each block's port number over it (its chain's ESD right under it), and the columns' names once, right of
            # the six (read with the jumpers in: the left column's name, then the right's)
            *({"text": str(n), "x": BLK_X[n - 1], "y": 0.95, "size": 0.8} for n in range(1, 7)),
            *({"text": f"{a} {c}", "x": BLK_X[-1] + 6.6, "y": BLK_Y - 6.35 + 2.54 * i, "size": 0.8}
              for i, (a, c) in enumerate(LEGEND)),
            *({"text": name, "x": x, "y": y + d / 2 + 0.75, "size": 0.8, "layer": "B.SilkS"}
              for net, name, d, x, y in TPS.values()),
            # J2's pin names over it on the rear face (the front has the co-processor's parts right over it)
            *({"text": name, "x": SWD_HDR[0] + 2.54 * i, "y": SWD_HDR[1] - (2.2 if i % 2 == 0 else 3.3), "size": 0.8,
               "layer": "B.SilkS"} for i, (_, name) in enumerate(SWD_PINS[:4])),
            {"text": SWD_PINS[4][1], "x": SWD_HDR[0] + 4 * 2.54 + 3.0, "y": SWD_HDR[1], "size": 0.8},
            # the two leads' connectors, named on the rear face where they plug in
            {"text": "LEAD", "x": LEAD[0], "y": LEAD[1] - 3.6, "size": 0.8, "layer": "B.SilkS"},
            {"text": "VIN 20 V", "x": VIN_J[0], "y": VIN_J[1] + 4.0, "size": 0.8, "layer": "B.SilkS"},
        ],
    }
    return b


USB_W = 0.15 if LAYERS == 6 else 0.25    # ≈ 90 Ω over 0.1 mm of 3313 prepreg on 6 layers, 0.2 mm of 7628 on 4
NETCLASSES = [
    {"name": "Default", "clearance": 0.1, "track_width": 0.127, "via_diameter": 0.5, "via_drill": 0.3},
    {"name": "Supply", "clearance": 0.1, "track_width": 0.25, "via_diameter": 0.5, "via_drill": 0.3,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 5,
     "_patterns": ["*+3V3_CP", "*+1V1", "-5V", "+5V_MX", "+3V3", "*HUB_1V8", "*HUB_1V8PLL", "*CP_VREG_AVDD"]},
    {"name": "Power", "clearance": 0.15, "track_width": 0.6, "via_diameter": 0.6, "via_drill": 0.3,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 1,
     "_patterns": ["+5V_A", "+5V_B", "+5V_L", "VIN", "*BUCK?_SW"]},
    {"name": "Port", "clearance": 0.1, "track_width": 0.3, "via_diameter": 0.6, "via_drill": 0.3,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 2,
     "_patterns": ["*PORT?_5V_SW", "*PORT?_VBUS"]},
    {"name": "USB", "clearance": 0.127, "track_width": USB_W, "via_diameter": 0.5, "via_drill": 0.3,
     "diff_pair_width": USB_W, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 3,
     "_patterns": ["*_DP", "*_DN"]},
    {"name": "Pins", "clearance": 0.1, "track_width": 0.127, "via_diameter": 0.5, "via_drill": 0.3,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 4,
     "_patterns": ["*PORT?_P?", "*PORT?_A?", "*PORT?_B?", "BUS_?"]},
]
