"""DATA ×4 v1.0 (data-port-x4) — the analyzer bays' drawer board, v1 plus virtual wires and a logic analyzer.

docs/data-x4-v2-research.md is the why; electronics.md › "DATA ×4 v1.0" the what.  v1 (the first DATA ×4,
retired unbuilt on 2026-10-26; this folder held it) was to stay the board of the other converted bays (decided
2026-10-20).  v2 keeps everything v1 does and adds:

* per port, 8 pins P1–P8 and the board's VREF on a 2 × 6 through-hole header, soldered by hand (GND,
  VREF, P1–P8, RESET_N, BOOT_N): each pin through H5VU25UC ESD and 100 Ω to an LSF0108 (A side = the DUT's VREF, B side =
  3.3 V; Vref_B and EN biased from +5V_MX through 200k, so a group is a voltage domain of its own; a VREF left
  unconnected is held ≈ 0.4 V by the ADC divider, and the firmware keeps that port's crosspoint switches open);
  VREF, RESET_N and BOOT_N through H5VU25UC ESD too.  Specified for
  0.95–3.6 V logic; a 5 V board with TTL inputs takes VREF from its own 3.3 V pin (electronics.md › "The
  VREF rule");
* two CH446Q 8 × 16 crosspoints at ±5 V (TPS60400 for −5 V), each taking two ports' 16 pins on X; their
  Y lines joined are the eight buses A–H, each pulled up to 3.3 V by 10k (the B-side pull-up of
  whatever pins it joins).  The node writes them through a TCA9534A (0x38: DAT, CK, one
  STB per chip, RST held high until the node writes it: all switches open at power-up);
* an RP2350B co-processor wired like a Pico 2 less its flash (12 MHz ABM8-272-T3, its core regulator as
  Raspberry Pi lays it out), on hub port 5.  With no flash it comes up in the USB bootloader at each power-up
  and runs what is loaded into its SRAM (picotool load -x over USB/IP from the lab server, later the node);
  an RP2354B is a drop-in that boots from its in-package flash instead.  gusmanb's LogicAnalyzer (its PICO_2
  build, as a RAM image) sees the buses on CH1–8 (GPIO2–9, GPIO0 → 1 bridged for its triggers); our firmware later switches 2.2k pull-ups per bus (GPIO10–13,
  16–19) and reads the VREFs (GPIO40–43, through 100k) and the ±5 V rails (GPIO44–45).  The node holds its RUN
  and   BOOTSEL (QSPI_SS through 1k) on the TCA9534A, and the mark line (GPIO14) for triggers.  Its 3.3 V from the
  board's, through a ferrite.

Its 5 V from the rack's 20 V (VIN), which the node switches onto the lead's pin 8 through its eFuse (the user,
2026-11-01, as the DATA ×6): one LMR51635 (3.5 A), the DATA ×6's block with the family's 3.5 A part, in the
top-left corner, its
output down the cradle's band on the power plane.  The lead's pin 1 is open: INT left it (the node polls).

v1's PCBA-review fixes (docs/pcba-review.md, X1–X11) carried over: the lead's SDA and SCL through two 2N7002
(gate on +3V3) with 4.7k / 4.7k on this side, so the node's pull-ups cannot feed the board with VIN off; ports
off by default (EN pulled down, the node switches them on); R_ILIM right
beside its pin and the INA226's Vbus on the shunt's sense pad; 100k pull-ups on the RESET/BOOT expander
lines; the hub's strap pins all pulled; 100 nF at each USBLC6 VBUS pin; netclass patterns with a `*`.

The board STANDS in the drawer's rear bay, behind the port wall (the layout study's option B, decided
2026-10-20; config/rack.yaml › pcb.data_port_x4_v2): 100 × 70 mm, held at both ends by a printed cradle
(its slots take each end's 5.5 mm, two T-heads come through notches in its bottom edge), its bottom edge on
the drawer floor.  KiCad x = drawer x − 4, y = 72.5 − z
(y = 0 the top edge).  Every part JLC places sits on the front face (F.Cu, towards the port wall): JLC's
Economic assembly, one side.  The lead's PH 8 (J1) stands on the rear face, soldered by hand.  Bands, top
to bottom: the co-processor in the middle with its pull-ups, the matrix expander and the two crosspoints
either side; the hub in the top-right corner; per port its pin chain (LSF0108, 100 Ω, ESD) above its
header; the headers; per port its power cluster; the vertical USB-C with their ESD and CC resistors.

One PCB, two assemblies (b.pcb["variants"], build_board writes each one's BOM and CPL): as drawn, DATA-4x-logic;
"base", DATA-4x, the converted bays' board (the user, 2026-10-20: v1 is not ordered, the base board is this one
with the logic left off).  The base leaves unfitted the matrix sheet (crosspoints, −5 V, TCA9534A, FB1), the
co-processor sheet and each port's pin chain (H5VU25UC, 100 Ω, LSF0108, its VREF parts): what stays is v1's
board, the hub and its reset supervisor, the four ports with their switch, INA226, ESD and CC, the expanders
with RESET/BOOT (and their ESD), the lead's isolation and ESD, the 5 V converter, the 3.3 V.  No base signal runs through a logic part: the
header's GND, RESET and BOOT stay live, its P pins and VREF end on empty pads, hub port 5 ends on R23/R24's empty pads.
4 layers (pcb.layers, JLC04161H-7628): F (the High-Speed pairs, drawn) · In1 GND · In2 +3V3 above, +5V below · B,
again since 2026-10-23: the routing portfolio and its fixes route it clean.  6 layers (X4V2_LAYERS=6: F · GND ·
sig · sig · power · B, the HS review's of 2026-10-22) still builds, for a comparison.
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
from silk import LOGO_W, SILK_RULE, SILK_TEXT, lead_pin_names, port_mark, title_block  # noqa: E402

RACK = rackcfg.load()
CFG = RACK.raw["pcb"]["data_port_x4_v2"]
W, H = CFG["size"]
# 4 or 6 layers (pcb.data_port_x4_v2.layers; X4V2_LAYERS overrides it for a comparison run)
LAYERS = int(os.environ.get("X4V2_LAYERS", CFG["layers"]))
# rack.yaml gives drawer x and z (the viewer's and the cradle's frame): KiCad x = drawer x − x0, y = top_z − z
TOP_Z = CFG["top_z"]
CRADLE = CFG["cradle"]              # each end's band in the cradle's slots: no parts on either face
_NW, _ND = CFG["notches"]["size"]
NOTCHES = [(x - CFG["x0"] - _NW / 2, x - CFG["x0"] + _NW / 2, H - _ND)   # (x0, x1, top y) of the bottom-edge notches
           for x in CFG["notches"]["x"]]
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
USB_Y = TOP_Z - CFG["usb_z"]        # the vertical USB-C's axis (z 11)
HDR_Y = TOP_Z - CFG["header"]["z"]  # the 2 × 6 headers' centre: odd pins (GND, P5, P6…) on the lower row
# Layout B (2026-11-01): the headers and their pin chains on their own 18 mm pitch (HDRS), the four USB-C standing
# on the DATA ×6's 15.5 mm grid, its positions 2–5 (USBS), so one drawer takes either board.  Between them, each
# port's power cluster (its frame's west corner, CLX), between the hub's pairs coming down through the header gaps
# (hs_centrelines()).  Each USBLC6 on its receptacle's axis, ESD_DX east of it, its hub pins east, all four alike:
# its pair comes down east of it and in from the east, the DATA ×6's cell turned east to west (conn_pairs())
HDRS = CFG["header"]["x"]
USBS = CFG["usb"]
# the receptacles' two pad columns (GCT USB4145's land, turned 90°): ±1.485 mm off its axis, 0.5 mm pitch
USBC_COL = 1.485
assert CFG["usb_rot"] == [90] * 4, "conn_pairs() draws the four USB-C standing"
CLX = [20.9, 38.4, 52.9, 71.9]
ESD_DX = 5.55
# J1's pin 1: the lead's centre (board x, drawer z) less half its 8 pins' 14 mm span, pins running up (the ×6's)
LEAD = (CFG["lead"][0], TOP_Z - CFG["lead"][1] + 7.0)
# The header's pins as the user reads them (2026-10-20): the upper row VREF, P1, P2, P3, P4, BOOT, the lower
# row GND, P5, P6, P7, P8, RESET.  Header pin k (IDC numbering: odd pins on the lower row, column by column)
# → its signal, and the names on the silkscreen under it, in two lines stacked like the rows
HDR_SIG = {1: "GND", 2: "VREF", 3: "P5", 4: "P1", 5: "P6", 6: "P2", 7: "P7", 8: "P3", 9: "P8", 10: "P4",
           11: "RST_N", 12: "BOOT_N"}
HDR_PINS = ("GND", "VREF", "5", "1", "6", "2", "7", "3", "8", "4", "RST", "BOOT")
# the power plane (In2 / In4): +3V3 above this y (the power clusters too), +5V below it (the USB-C, their ESD,
# J1's pin 8, the 3.3 V LDO); each port switch's IN gets its +5V by a track down to a via under the split
PWR_SPLIT = 55.7
CHIP = [(30.0, 18.8), (68.0, 18.8)]  # the crosspoints, between their two ports, above the pin chains
CP = (47.0, 12.9)                   # the co-processor, top centre, turned 180°: its buses at the south-east corner
HX, HY = 87.5, 15.0                 # the hub, top-right corner, turned 90°: its DN pins face down, to the ports
XT = (HX - 8.9, HY + 1.75)          # its 24 MHz crystal Y1, 2 mm west of XTAL1/XTAL2 (pins 61/60, y 17.25 / 16.75)
MX_EXP = (19.3, 17.6)               # the matrix expander (TCA9534A), turned 90°: under the 5 V converter, by U7
# the 5 V converter (power_sheet()): the DATA ×6's converter A block (an LMR51635 here), at an offset in the top-left
# corner (U13's centre); its output's plane tongue (TA wide, TB deep) runs down the cradle's band to the +5V area.
# VIN's 33 µF under it, between the band and the matrix expander (7.7 mm tall: over the strip on the comb)
BUCK = (11.0, 4.6)
BULK = (10.35, 17.6)
TA, TB = 23.4, 12.9
# the pin chain's rows: H5VU25UC × 2 under the header's pins, the 100 Ω arrays, the LSF0108 (A side down)
TPD_Y, RN_Y, LSF_Y = 36.4, 34.2, 29.6
PWR_Y = 48.4                        # each port's power cluster (switch, shunt, INA226): its frame's top
# U3, the 3.3 V LDO (SOT-223, turned 90°: its tab up over the +3V3 area, its pins down over +5V), in the
# left-hand column across the power plane's split
LDO = (9.7, 55.7)
LDO_WEST = 1.6                      # its +3V3 copper's west edge, inside the edge fence's GND vias (x 0.9)
# The order's panel (electronics/tools/panelize.py, tools/panel.sh): this board as drawn (DATA-4x-logic) and,
# turned 180°, the base (DATA-4x), top edge to top edge 2 mm apart, so the bottom edges and the slot ends stay
# milled.  Two mouse-bite tabs join them where both top edges are bare: at x 9 and 91 (each the other's mirror,
# so they meet), clear of the cradle's 5.5 mm ends; no copper within 1.2 mm of the edge there
TABS, TAB_W = (9.0, 91.0), 6.0
# The bring-up test points (the DFT rule, 2026-10-26): bare pads on the rear face (B.Cu, mask open, no
# paste, out of the BOM and CPL), each named on B.SilkS under it; 1.5 mm on GND and the rails, 1.0 mm on signals.
# GND spread over the board, the supplies, the resets, the faults, SWD and the buses a header or J1 doesn't already
# bring out, never a USB pair; each > 2 mm from the THT pads and J1, clear of the cradle's 5.5 mm ends, the push
# band and the notches, and kept from one revision to the next.  ref: (net, name, pad Ø, x, y); each sheet places
# its own (testpoint())
# GND vias filling the stitching grid's gaps (as on the DATA ×6): the outer pours' point farthest from a GND via
# first, a via where it fits inside both outer pours; 7.05 mm at worst before (by port 4's lane at (85, 41)),
# 5.4 mm after, in the pairs' bundle under the hub, where no via fits
GND_FILL = [(89.07, 31.7), (22.2, 46.2), (88.7, 41.7), (80.65, 44.09), (27.27, 44.22), (62.09, 7.15), (28.43, 33.7),
            (25.2, 6.2), (33.57, 44.2), (60.68, 46.13), (44.31, 31.75), (63.7, 17.2), (9.2, 2.7), (30.61, 22.11),
            (74.61, 13.29), (51.2, 55.2), (88.83, 47.72), (48.7, 29.7)]
# each port's VBUS test pad (TPS): a via on its VBUS line where the rear face has room for the pad
VBUS_TP = {1: (21.715, 60.25), 2: (39.695, 63.545), 3: (55.067, 67.777), 4: (70.567, 67.777)}
TPS = {
    # the co-processor's row along the top edge: BOOTSEL, RUN, SWD, a GND and its 3.3 V; its core rail under it, on
    # that rail's own rear track
    "TP1": ("CP_SWCLK", "SWCLK", 1.0, 30.0, 3.6), "TP2": ("CP_SWDIO", "SWDIO", 1.0, 25.5, 3.6),
    "TP3": ("GND", "GND", 1.5, 33.75, 3.0), "TP10": ("+3V3_CP", "+3V3_CP", 1.5, 38.25, 3.25),
    "TP11": ("+1V1", "+1V1", 1.5, 43.12, 15.4),
    # RUN and BOOTSEL in a second row, off the 5 V converter's tongue (no rear track crosses its edge)
    "TP12": ("CP_RUN", "RUN", 1.0, 28.25, 9.0), "TP13": ("CP_BOOT_N", "BOOT", 1.0, 24.75, 9.0),
    # the left-hand column: the matrix (its bus, its two rails by the TPS60400; STB1 and RST on their own rear
    # tracks, RST under the co-processor's row), +3V3 and +5V by the AP2114H, a GND with each group
    "TP4": ("-5V", "−5V", 1.5, 11.0, 20.5), "TP5": ("+5V_MX", "+5V_MX", 1.5, 11.0, 23.7),
    "TP6": ("GND", "GND", 1.5, 11.0, 26.9), "TP7": ("+3V3", "+3V3", 1.5, 11.0, 47.5),
    "TP8": ("GND", "GND", 1.5, 11.0, 50.7), "TP9": ("+5V", "+5V", 1.5, 11.0, 57.9),
    "TP14": ("MX_DAT", "DAT", 1.0, 8.0, 14.3), "TP15": ("MX_CK", "CK", 1.0, 11.0, 14.3),
    "TP16": ("MX_STB1", "STB1", 1.0, 16.0, 23.2), "TP17": ("MX_STB2", "STB2", 1.0, 7.75, 17.5),
    "TP18": ("MX_RST", "MX RST", 1.0, 31.5, 8.705), "TP19": ("GND", "GND", 1.5, 14.25, 17.5),
    # the hub's reset and core rail, with a GND
    "TP20": ("HUB_RST_N", "HUB RST", 1.0, 81.5, 4.5), "TP21": ("GND", "GND", 1.5, 77.0, 5.0),
    "TP22": ("HUB_1V8", "1V8", 1.5, 92.5, 19.25),
    # the lead's VIN and the board side of its I²C, below J1, with a GND
    "TP40": ("VIN", "VIN", 1.5, 91.0, 50.5), "TP24": ("SDA", "SDA", 1.0, 91.0, 53.2),
    # (SCL's off the power plane's split, whose rear band no track may cross: west of SDA's, above GND's)
    "TP25": ("SCL", "SCL", 1.0, 88.4, 53.9), "TP26": ("GND", "GND", 1.5, 88.0, 56.5),
    # each port's FAULT_N on its own rear track between its expander and its switch (port(): TP{k + 1}), a GND by
    # each pair's expander
    "TP27": ("GND", "GND", 1.5, 24.4, 56.15), "TP28": ("GND", "GND", 1.5, 71.5, 56.15),
    "TP101": ("PORT1_FLT_N", "FLT1", 1.0, 24.3, 50.64), "TP201": ("PORT2_FLT_N", "FLT2", 1.0, 39.75, 53.76),
    "TP301": ("PORT3_FLT_N", "FLT3", 1.0, 56.68, 49.3), "TP401": ("PORT4_FLT_N", "FLT4", 1.0, 74.75, 49.9),
    # and its VBUS (port(): TP{k + 2}), on a via of its own on its VBUS line between its cluster and its USB-C
    # (drawn: VBUS_TP), each > 2 mm from the receptacle's stakes (the design review, 2026-11-02, as on the DATA ×6)
    **{f"TP{100 * n + 2}": (f"PORT{n}_VBUS", f"VBUS{n}", 1.5, *VBUS_TP[n]) for n in range(1, 5)},
    # the crosspoints' eight buses (the co-processor's GPIO2–9), behind its east side where they all pass: A, B, E
    # and F on a rear track of their own, C, D, G and H beside one (H, front only, through a via), with a GND
    # (the design review, 2026-10-27)
    "TP29": ("BUS_A", "A", 1.0, 56.68, 9.92), "TP30": ("BUS_B", "B", 1.0, 51.79, 15.67),
    "TP31": ("BUS_C", "C", 1.0, 52.3, 19.1), "TP32": ("BUS_D", "D", 1.0, 57.3, 17.2),
    "TP33": ("BUS_E", "E", 1.0, 57.16, 14.51), "TP34": ("BUS_F", "F", 1.0, 54.74, 11.99),
    "TP35": ("BUS_G", "G", 1.0, 59.95, 19.6), "TP36": ("BUS_H", "H", 1.0, 55.25, 19.0),
    "TP37": ("GND", "GND", 1.5, 59.75, 11.25),
    # each expander's RESET, by its pull-up's via
    "TP38": ("EXP1_RST_N", "EXP1 RST", 1.0, 15.05, 50.25), "TP39": ("EXP2_RST_N", "EXP2 RST", 1.0, 63.85, 50.05),
}
# The co-processor's SWD header (the user, 2026-10-27, after the design review): 1 × 5 through-hole on the front face's top
# edge, right of the co-processor, where both faces are free and a probe reaches it from above with the board in its
# cradle (a box4 cover lifts off first).  Pins 1–3 in the Pico 2's debug order, so the Raspberry Pi Debug Probe's
# 3-pin lead plugs straight on; RUN and VTref for a J-Link or an ST-Link on Dupont wires.  VTref is the board's
# +3V3, on the power plane there (+3V3_CP is the same rail through FB2, its island ends at x 53).  Pin 1 (x, y), east
SWD_HDR = (59.2, 4.0)
SWD_PINS = (("CP_SWCLK", "SWCLK"), ("GND", "GND"), ("CP_SWDIO", "SWDIO"), ("CP_RUN", "RUN"), ("+3V3", "3V3"))
J1_ROT = 90                         # J1 on the rear face: its pins run up (−y) from pin 1, as the DATA ×6's


# INA226 address straps (A1, A0) per port: 0x41, 0x43, 0x44, 0x45 (the node's own INA226 is 0x40)
INA_ADDR = [("GND", "+3V3"), ("GND", "SCL"), ("+3V3", "GND"), ("+3V3", "+3V3")]
# the two TCA6408A, one per pair of ports, between their power clusters: x, y, ADDR strap
EXP = [(16.5, 51.5, "GND"), (66.0, 51.5, "+3V3")]     # U2 west of port 1's cluster, U6 between 3's and the drop
EXP_LINES = {"a": {"P0": "RST_IO", "P1": "BOOT_IO", "P2": "EN", "P3": "FLT_N"},
             "b": {"P4": "EN", "P5": "FLT_N", "P6": "BOOT_IO", "P7": "RST_IO"}}
BUSES = "ABCDEFGH"
# the CH446Q's Y lines: Y0–Y3 leave by its north side (and its north-east corner), Y4–Y7 by its south side
Y_BUS = "DCBAEFGH"
# the 2.2k pull-up enables on the RP2350B's east face, either side of its 3.3 V pin 15 (A at GPIO19 … D at
# GPIO16, E at GPIO13 … H at GPIO10), the arrays RN6/RN7 right beside them in the same order
PU_GPIO = {"A": 19, "B": 18, "C": 17, "D": 16, "E": 13, "F": 12, "G": 11, "H": 10}
# The pin chain of a port, straight up from its header: header → H5VU25UC → 100 Ω → LSF0108 (A face down,
# B face up) → crosspoint X.  The header's lines leave it west → east VREF and eight lines, a lower-row
# pin's just west of its upper-row neighbour's: P5 P1 P6 P2 P7 P3 P8 P4 (LANE).  The LSF's channels 1–8
# take those lanes in that order (its A face, west → east: VREF, A1 … A7, A8 round its east end), so
# nothing crosses; its B lines turn into the crosspoint's face: west of the chip (port a) lane 1 at the top,
# east of it (port b) lane 8 at the top.
LANE = (5, 1, 6, 2, 7, 3, 8, 4)     # the P pin in lane 1 … 8, west → east
TPD_SIG = (1, 2, 4, 5)              # the ESD array's signal pins west → east, turned 90° (pins 1–5 down, 6–10 up)
TPD_THRU = {1: 10, 2: 9, 4: 7, 5: 6}  # the pad across from each: the line runs through both (flow-through)


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
    p60, p61 = (HX - 4.412, 16.75), (HX - 4.412, 17.25)          # U1.60 XO, U1.61 XI
    c4, c5 = (x + 0.85, y + 2.65), (x - 0.85, y - 2.62)         # C4.1, C5.1
    tracks = [("XI", "F.Cu", 0.127, [xi, (r_xi[0] - 0.34, xi[1]), r_xi]),
              ("XI", "F.Cu", 0.127, [r_xi, (r_xi[0] + 0.26, p61[1]), p61]),
              ("XI", "F.Cu", 0.127, [xi, c4]),
              ("XO", "F.Cu", 0.127, [xo, (x + 0.25, y), (r_xo[0] - 0.26, y), r_xo]),
              ("XO", "F.Cu", 0.127, [r_xo, (r_xo[0] + 0.26, r_xo[1]), (r_xo[0] + 0.52, p60[1]), p60]),
              ("XO", "F.Cu", 0.127, [xo, c5])]
    gnd = [((x + 0.85, y - 1.1), (x + 0.85, y - 2.25)),        # Y1.2 (north-east), up
           ((x - 0.85, y + 1.1), (x - 0.85, y + 2.25)),        # Y1.4 (south-west), down
           ((x - 0.85, y - 3.58), (x - 0.85, y - 4.35))]        # C5.2, up
    tracks += [("GND", "F.Cu", 0.25, [a, b]) for a, b in gnd]
    tracks.append(("GND", "F.Cu", 0.25, [(x - 0.11, y + 2.65), gnd[1][1]]))     # C4.2 to Y1.4's via
    p62, p63 = (HX - 4.412, 17.75), (HX - 4.412, 18.25)
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
# via on F.Cu or B.Cu (the router's "core:" area here, XTAL_RULE for DRC), In1 solid GND under it.  It leaves the
# crosspoint U8's port-4 lines 2.5 mm west of it, and pins 62-64 (HUB_1V8PLL, RBIAS, +3V3) a way down east of C4
XTAL_KEEP = [(XT[0] + dx, XT[1] + dy) for dx, dy in
             ((-1.6, -4.65), (-0.1, -4.65), (-0.1, -2.55), (1.85, -2.55), (1.85, -0.75))] +             [(HX - 4.88, XT[1] - 0.75), (HX - 4.88, XT[1] + 0.85)] +             [(XT[0] + dx, XT[1] + dy) for dx, dy in
             ((2.85, 0.85), (2.85, 1.2), (1.85, 1.2), (1.85, 2.15), (1.4, 2.15), (1.4, 3.2), (-1.3, 3.2),
              (-1.3, 2.55), (-2.0, 2.55), (-2.0, -2.35), (-1.6, -2.35))]
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
    y1, y3, c48, c49, r1, r2 = (x + 2.4, 1.35), (x + 0.2, 3.05), (x + 4.4, 2.08), (x - 1.4, 1.88), (x - 1.6, 3.91),         (x - 1.6, 2.89)
    # the GND dog-bones of C48, C49 and Y2's top-left GND pad, where main had them (the block keeps the automatic
    # ones out; its bottom-right GND pad keeps its own, outside)
    gnd = [((x + 4.4, 1.12), (x + 5.09, 0.84), 0.25), ((x - 1.4, 0.92), (x - 2.06, 0.92), 0.25),
           ((x + 0.2, 1.35), (x + 1.24, 0.75), 0.2)]
    return [("CP_XIN", "F.Cu", 0.127, [pin30, (x + 0.2, 7.38), (x + 1.07, 6.51), (x + 1.07, 2.98), (x + 2.05, 2.0),
                                         y1]),
            ("CP_XIN", "F.Cu", 0.127, [y1, (x + 3.2, 1.35), (x + 3.93, 2.08), c48]),
            ("CP_XOUT", "F.Cu", 0.127, [pin31, (x - 0.2, 7.45), (x + 0.15, 7.1), (x + 0.15, 4.4), (x - 0.2, 4.05),
                                          (x - 1.46, 4.05), r1]),
            ("CP_XTAL", "F.Cu", 0.127, [r2, (x + 0.04, 2.89), y3]),
            ("CP_XTAL", "F.Cu", 0.127, [r2, (x - 1.6, 2.08), c49]),
            # beside XOUT's way up: C47 (+1V1, DVDD pin 32's 4.7 µF) straight down to its pin, and C44's +3V3_CP
            # via moved west off that line (the router had put it on it, and +1V1 round it)
            ("+1V1", "F.Cu", 0.25, [(x - 0.6, 5.98), (x - 0.6, 7.95)]),
            ("+3V3_CP", "F.Cu", 0.25, [(x - 2.2, 5.98), (x - 1.4, 6.78), (x - 1.15, 6.78)])] +         [("GND", "F.Cu", w, [a, v]) for a, v, w in gnd],         [("GND", *v, 0.5, 0.3) for _, v, _ in gnd] + [("+3V3_CP", x - 1.15, 6.78, 0.5, 0.3)]


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
# the layout review (2026-11-01): no corner sharper than 45° on the USB pairs and the crystals' lines (KiCad takes
# the minimum in whole degrees, and a drawn 45° turn measures 134.9999°: hence 134)
ANGLE_RULE = """
(rule "USB pairs and crystal lines: no corner sharper than 45 degrees"
	(severity error)
	(condition "A.Type == 'Track' && (A.hasNetclass('USB') || A.NetName == '/Hub/XI' || A.NetName == '/Hub/XO' || A.NetName == '/Co-processor/CP_XIN' || A.NetName == '/Co-processor/CP_XOUT' || A.NetName == '/Co-processor/CP_XTAL')")
	(constraint track_angle (min 134)))
"""
# and the layout review's (2026-11-01) silkscreen text a 0.15 mm stroke at least (the 0.8 mm names' 15 % was
# 0.12): silk.SILK_RULE, shared with the DATA ×6


def p_lines(n: int):
    """Port n's eight P lines, drawn (the kicad-happy review's X2-1, 2026-10-27: Freerouting had run six of them
    from the header straight to the 100 Ω array, their ESD on a stub).  Every port alike: header pin → B.Cu → a
    via → its H5VU25UC pad → across to the partner pad → the 100 Ω array.  B.Cu under the upper ports' USB pairs,
    which cross the band between the header and the ESD on F.Cu (y 38.95–41.35); the vias in two staggered rows
    between the pairs and the ESD pads (the lanes are 0.5 mm apart).  The lower row's pins pass between two of the
    upper row's (P5 west of pin 4).  The array pads: outer lanes bend late, inner ones early.  The array's GND
    pads, walled in by the middle lanes, go down to a via of their own between the lanes' vias.  Returns (tracks,
    vias)."""
    cx = HDRS[n - 1]
    up, lo = HDR_Y - 1.27, HDR_Y + 1.27                 # the header's rows: P1-P4 up, P5-P8 down
    e_y, p_y, rn_y = TPD_Y + 0.4375, TPD_Y - 0.4375, RN_Y + 0.5
    col = [cx - 6.35 + 2.54 * c for c in range(6)]      # the header's columns
    tracks, vias = [], []
    for j in range(2):
        x0 = cx + (2.54 if j else -2.54)
        # the array's GND pads (3 and 8, between the middle lanes) down to a via between the lanes' vias
        tracks.append(("GND", "F.Cu", 0.25, [(x0, p_y), (x0, TPD_Y), (x0, e_y), (x0, e_y + 1.11)]))
        vias.append(("GND", x0, e_y + 1.11, 0.5, 0.3))
        for i in range(4):
            net = f"PORT{n}_P{LANE[4 * j + i]}"
            xe = x0 + (-1.0, -0.5, 0.5, 1.0)[i]          # TPD_SIG's pads
            xr = x0 + (-0.75, -0.25, 0.25, 0.75)[i]      # the array's pins
            vy = e_y + (1.46 if i in (0, 2) else 0.76)   # the via rows: 38.3, 37.6
            down = [(xe, vy), (xe, e_y), (xe, p_y)] + ([(xe, rn_y + 0.25), (xr, rn_y)] if i in (0, 3) else
                                                       [(xe, rn_y + 0.667), (xr, rn_y + 0.417), (xr, rn_y)])
            if i in (1, 3):                             # P1 P2 P3 P4: the upper row, up to the lane
                hx = col[1 + 2 * j + i // 2]
                d = abs(hx - xe)
                b = [(hx, up), (xe, up - d), (xe, vy)]
            else:                                       # P5 P6 P7 P8: the lower row, between two upper pins
                hx = col[1 + 2 * j + i // 2]
                gap = hx - 1.27                         # west of its column's upper pin
                b = [(hx, lo), (gap, lo - 1.27), (gap, vy + 0.66 + abs(xe - gap)), (xe, vy + 0.66), (xe, vy)]
            tracks += [(net, "B.Cu", 0.127, b), (net, "F.Cu", 0.127, down)]
            vias.append((net, xe, vy, 0.5, 0.3))
    return tracks, vias
# lane → crosspoint X line: port a on the chip's west face (pins 1–8, north → south X14 X15 X6 … X11), port
# b on its east face (pins 31–24, north → south X0 X1 … X5 X12 X13)
XMAP = {True: {1: 14, 2: 15, 3: 6, 4: 7, 5: 8, 6: 9, 7: 10, 8: 11},
        False: {8: 0, 7: 1, 6: 2, 5: 3, 4: 4, 3: 5, 2: 12, 1: 13}}
# LCSC parts of the 0402 × 4 arrays (UNI-ROYAL 4D02, checked 2026-10-19)
ARRAYS = {"100": ("4D02WGJ0101TCE", "C48442"), "10k": ("4D02WGJ0103TCE", "C25725"),
          "2.2k": ("4D02WGJ0222TCE", "C26075")}


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


def offset(poly, d):
    """A polyline (mm) shifted d mm sideways, mitred at its corners: to the west when it heads down the board (+y),
    to the north when it heads west.  A differential pair's two lines from its centreline."""
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


def bumps(poly, seg, n, h, top=0.15, gap=0.15, tail=None):
    """n bumps h mm deep on the polyline's segment `seg`, centred on it (or ending `tail` mm before its end),
    towards offset()'s side (away from the pair's other line), their flanks at 45° (ANGLE_RULE), `top` mm across and
    `gap` mm apart: each adds (2√2 − 2) h mm of length to the shorter line of a pair."""
    (ax, ay), (bx, by) = poly[seg], poly[seg + 1]
    L = math.dist((ax, ay), (bx, by))
    ux, uy = (bx - ax) / L, (by - ay) / L
    span = n * (2 * h + top) + (n - 1) * gap
    assert span < L - 0.1, (span, L)
    s, pts = (L - span) / 2 if tail is None else L - span - tail, []
    for _ in range(n):
        for d, o in ((0, 0), (h, h), (h + top, h), (2 * h + top, 0)):
            pts.append((round(ax + ux * (s + d) - uy * o, 4), round(ay + uy * (s + d) + ux * o, 4)))
        s += 2 * h + top + gap
    return poly[:seg + 1] + pts + poly[seg + 1:]


def plen(poly):
    return sum(math.dist(a, b) for a, b in zip(poly, poly[1:]))


def testpoints(s, refs, title, x0=232):
    """The sheet's bring-up test points (TPS) in a frame of their own, top right (x0: the frame's left side, inside
    the sheet's paper: A1 for the sheets with a full right-hand column), seven to a row"""
    s.frame(title, x0, 10, x0 + 90, 30 + 14 * ((len(refs) + 6) // 7))
    for i, ref in enumerate(refs):
        net, _, d, x, y = TPS[ref]
        part(s, ref, "testpad" if d > 1.2 else "testpad1", {"1": net}, pcb=P(x, y, 0, "bottom"), in_bom=False,
             sch=at(x0 + 8 + 12 * (i % 7), 30 + 14 * (i // 7)))


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
    fields = {"MPN": mpn, "LCSC": lcsc}
    return part(s, ref, "rarray", conns, value, pcb=pcb, fields=fields, sch=sch)


# ----------------------------------------------------------------------------------------------- ports
def port(b: Board, n: int):
    cx, hx = USBS[n - 1], HDRS[n - 1]       # its USB-C's x, its header's
    k = 100 * n
    p = f"PORT{n}_"
    a = n % 2 == 1                      # the left port of its pair: its crosspoint is to its right (east)
    s = b.sheet(f"Port {n}", f"port{n}.kicad_sch", f"USB-C {n}: switch, current sense, ESD, header; pins")
    s.paper = "A1"
    sw, sh, ina, usb, esd = f"U{k + 1}", f"R{k + 6}", f"U{k + 2}", f"J{k + 1}", f"U{k + 3}"
    s.frame(f"Port {n} power: +5V → TPS2553-1 → {p}5V_SW → 100 mΩ shunt → {p}VBUS, the INA226 across the shunt",
            6, 10, 108, 44)
    s.tag("+5V", (20, 18), "up")
    s.wire((20, 18), (20, 21), f"{sw}.IN")
    # the cluster in a 12 × 7 mm frame over the port's USB-C, between the hub pairs' drops (x0, y0 its corner)
    x0, y0 = CLX[n - 1], PWR_Y
    # the switch turned 180°: OUT (pin 6) straight down into the shunt's pin 1, ILIM (pin 5) level with
    # R_ILIM's pad right beside it (TI: as close to the pin as possible), IN and GND east by their 1 µF
    part(s, sw, "vbus_sw_latch", {"IN": "+5V", "GND": "GND", "EN": p + "EN", "~{FAULT}": p + "FLT_N",
                                  "ILIM": p + "ILIM", "OUT": p + "5V_SW"}, pcb=P(x0 + 2.45, y0 + 2.2, 180),
         sch=at(30, 22, fields=(-4, -4)))
    C(s, f"C{k + 1}", "1u", "+5V", "GND", size="0402", pcb=P(x0 + 5.13, y0 + 2.9, 90), sch=at(15, 24))
    s.wire(f"C{k + 1}.1", (15, 21), (20, 21))
    # 45.3k, as the DATA ×6's: 524 mA at the least, so a DUT drawing its full 500 mA never trips it (47k's 505 mA
    # fell to 499.7 with its 1 %); no JLC basic part between 39k and 47k, so an extended one
    R(s, f"R{k + 1}", "45.3k", p + "ILIM", "GND", size="0402", pcb=P(x0 - 0.97, y0 + 2.2, 180), sch=at(22, 28),
      fields={"LCSC": "C2933099", "MPN": "FRC0402F4532TS", "Manufacturer": "FOJAN"})
    s.wire(f"{sw}.ILIM", (22, 24), f"R{k + 1}.1")
    # X3: the port is off until the node switches it on
    R(s, f"R{k + 2}", "10k", p + "EN", "GND", size="0402", pcb=P(x0 + 9.9, y0 + 3.65, 90), sch=at(14, 36))
    R(s, f"R{k + 3}", "10k", "+3V3", p + "FLT_N", size="0402", pcb=P(x0 + 9.9, y0 + 5.6, 90), sch=at(40, 36))
    testpoints(s, [f"TP{k + 1}", f"TP{k + 2}"], "Bring-up test points on the rear face (B.Cu): FAULT_N, VBUS")
    # Kelvin shunt: pins 1/4 carry the port's current, 2/3 are sense pads at the resistor's own ends; pin 1
    # under the switch's OUT
    part(s, sh, "shunt100m", {"1": p + "5V_SW", "4": p + "VBUS", "2": p + "SNS_P", "3": p + "SNS_N"},
         "100m", pcb=P(x0 + 2.77, y0 + 5.4, 0), sch=at(46, 23))
    s.wire(f"{sw}.OUT", f"{sh}.1")
    a1, a0 = INA_ADDR[n - 1]
    # X4: Vbus read on the shunt's load-side sense pad (the same node as PORTn_VBUS), its pin beside Vin−
    part(s, ina, "ina226", {"VS": "+3V3", "GND": "GND", "A1": a1, "A0": a0, "SDA": "SDA", "SCL": "SCL",
                            "~{Alert}": None, "Vin+": p + "SNS_P", "Vin-": p + "SNS_N", "Vbus": p + "SNS_N"},
         pcb=P(x0 + 7.51, y0 + 4.6, 90), sch=at(66, 24, fields=(-9, -7)))
    s.wire(f"{sh}.2", (52, 22), (52, 25), f"{ina}.Vin+")
    s.wire(f"{sh}.3", (50, 24), (50, 26), f"{ina}.Vin-")
    s.wire(f"{sh}.4", (46, 33), (60, 33))
    s.tag(p + "VBUS", (60, 33), "right")
    # VBUS's bulk capacitor in the row under the receptacle (the DATA ×6's: CC1 and CC2's 56k west of it, all west
    # of the receptacle's axis, clear of the cradle's T-heads round the notches)
    C(s, f"C{k + 2}", "22u", p + "VBUS", "GND", size="0805", pcb=P(cx + 0.25, USB_Y + 6.1, 0), sch=at(55, 35.5))
    s.wire(f"C{k + 2}.1", (55, 33))
    # the INA226's 100 nF right over its VS pin (6), its +3V3 pad in line with it (drawn in board())
    C(s, f"C{k + 3}", "100n", "+3V3", "GND", size="0402", pcb=P(x0 + 8.03, y0 + 0.9, 180), sch=at(80, 18))
    # the port's VBUS LED (the user, 2026-10-21): green, on the switched 5 V before the shunt, so the INA226
    # doesn't count its ≈ 3 mA; by its port's number over the header's west end, its 1k above it
    R(s, f"R{k + 14}", "1k", p + "5V_SW", p + "LED_A", size="0402", pcb=P(hx - 5.2, HDR_Y - 9.8, 270),
      sch=at(84, 30, rot=90))
    part(s, f"D{k + 1}", "led_g", {"A": p + "LED_A", "K": "GND"}, pcb=P(hx - 5.2, HDR_Y - 7.0, 90),
         sch=at(94, 30, rot=180))
    s.wire(f"R{k + 14}.2", f"D{k + 1}.A")

    s.frame(f"USB-C {n} (source): Rp 56k on each CC; USBLC6 in flow-through (connector side | hub side)",
            6, 50, 108, 100)
    # vertical receptacle, standing (its slot upright, as the DATA ×6's), its mouth through the port wall's opening
    part(s, usb, "usbc_vg", {"VBUS": p + "VBUS", "GND": "GND", "CC1": p + "CC1", "CC2": p + "CC2",
                             "D+": p + "CONN_DP", "D-": p + "CONN_DN", "SBU1": None, "SBU2": None,
                             "SHIELD": "GND"}, f"PORT{n}", pcb=P(cx, USB_Y, 90), sch=at(50, 76, fields=(-8, -11)))
    s.wire(f"{usb}.A7", f"{usb}.B7")
    s.wire(f"{usb}.A6", f"{usb}.B6")
    # the CC resistors in the row under the receptacle, west of its 22 µF.  Source only: Rp from the switched VBUS,
    # no CC detection; a source that back-feeds the port trips the TPS2553 (≈ 4 ms, latched, FAULT_N), and the
    # node refuses EN while Vbus is already there
    R(s, f"R{k + 4}", "56k", p + "VBUS", p + "CC1", size="0402", pcb=P(cx - 4.55, USB_Y + 6.1, 0), sch=at(62, 64.5))
    R(s, f"R{k + 5}", "56k", p + "VBUS", p + "CC2", size="0402", pcb=P(cx - 2.5, USB_Y + 6.1, 0), sch=at(66, 64.5))
    s.wire(f"{usb}.CC1", (62, 72), f"R{k + 4}.2")
    s.wire(f"{usb}.CC2", (66, 73), f"R{k + 5}.2")
    # right of the receptacle, on its axis: pins 1/3 face it, 6/4 the hub (to the right): each line enters one pin
    # and leaves by the other
    ex, ey = cx + ESD_DX, USB_Y
    part(s, esd, "esd", {"1": p + "CONN_DN", "6": p + "DN", "3": p + "CONN_DP", "4": p + "DP", "5": "+5V",
                         "2": "GND"}, pcb=P(ex, ey, 0), sch=at(84, 76))
    s.wire(f"{usb}.B7", f"{esd}.1")
    s.wire(f"{usb}.A6", f"{esd}.3")
    # its VBUS 100 nF (X9) right over it, its +5V pad over the gap between the ESD's pin rows: VBUS (pin 5) runs
    # under the body and up that gap to it, then on to its via (conn_pairs(); the pair walls pin 5 in on its east)
    C(s, f"C{k + 4}", "100n", "+5V", "GND", size="0402", pcb=P(ex - 0.48, ey - 2.3, 180), sch=at(96, 76))

    s.frame(f"Header {n} (2 × 6 through-hole): GND, VREF, P1–P8, RESET_N, BOOT_N; RESET/BOOT through 1k, "
            "their expander lines pulled up", 112, 10, 228, 56)
    hdr = {str(k): (sig if sig == "GND" else p + sig) for k, sig in HDR_SIG.items()}
    # through-hole, soldered by hand (the user's call, 2026-10-20: easier than SMD; the rear face has room for
    # the tails), pins forward over the drawer's plate.  The footprint's origin is pin 1 (lower row, west end)
    part(s, f"J{k + 2}", "hdr2x6t", hdr, f"PINS{n}", pcb=P(hx - 6.35, HDR_Y + 1.27, 90),
         sch=at(184, 30, fields=(-1, -5)))
    # RESET/BOOT through 1k and an H5VU25UC, the expander lines' pull-ups in a column right of the header, by
    # its pins 12 (upper row) and 11 (lower row).  The DUT's own pull-ups should be ≥ 4.7k: against 1k, the 1k in
    # series stops an asserted line at ≈ 1.65 V.  Ports 1–3's pull-ups: 1.85 mm lower and 1.9 mm apart (down to just
    # over the expander), so the band over the headers stays free for the USB pairs' trunk on F.Cu (the HS review,
    # 2026-10-22); port 4's stay, Q1 right under them and no pair passing them
    ys = ((HDR_Y - 3.4, HDR_Y - 1.45, HDR_Y + 0.5, HDR_Y + 2.45) if n == 4 else
          (HDR_Y - 1.55, HDR_Y + 0.35, HDR_Y + 2.25, HDR_Y + 4.15))
    # The ESD (the audit's fix 7 and the schematic review's N4; fitted on the base too): RESET_N and BOOT_N
    # each through a pair of its pads in flow-through, header → ESD → 1k, so the 1k sit right behind it, over
    # the header's east end, clear of the pairs' trunk (ports 1–3); port 4's over its LSF0108's east end, where
    # the three pairs coming down from the hub leave room.  BOOT on pins 2 / 9, RESET on 5 / 6
    ex, ey = (hx + 5.6, 33.0) if n == 4 else (hx + 6.0, 37.2)
    part(s, f"U{k + 9}", "esd4", {"GND": "GND", "2": p + "BOOT_N", "9": p + "BOOT_N", "5": p + "RST_N",
                                  "6": p + "RST_N", "1": None, "10": None, "4": None, "7": None},
         pcb=P(ex, ey, 90), sch=at(80, 172, fields=(-3, -7)))
    for r, sig, dx, sy in ((f"R{k + 7}", "RST", 1.0, 34), (f"R{k + 8}", "BOOT", -0.5, 44)):
        R(s, r, "1k", p + sig + "_IO", p + sig + "_N", size="0402", pcb=P(ex + dx, ey - 2.2, 270),
          sch=at(150, sy, rot=90))
    # X6: the expander's RESET/BOOT inputs pulled up (they float with nothing plugged in), against the header's
    # courtyard: 0.75 mm off the USB pair coming down the gap east of them (the Sensitive class)
    for r, sig, j, y, rot in ((f"R{k + 9}", "RST", 0, ys[2], 270), (f"R{k + 10}", "BOOT", 1, ys[1], 90)):
        R(s, r, "100k", "+3V3", p + sig + "_IO", size="0402", pcb=P(hx + 8.7, y, rot),
          sch=at(138, (34, 44)[j] - 5))
        s.wire(f"{r}.2", (138, (34, 44)[j]), f"R{k + 7 + j}.1")
        s.wire((128, (34, 44)[j]), (138, (34, 44)[j]), net=p + sig + "_IO")
        s.tag(p + sig + "_IO", (128, (34, 44)[j]), "left")

    # ---- the pins: ESD, 100 Ω, LSF0108, to the crosspoint
    s.frame(f"ESD on the header's VREF (U{k + 8}, in flow-through: header → ESD → LSF0108 and divider) and on "
            f"RESET_N / BOOT_N (U{k + 9}: header → ESD → 1k)", 6, 150, 120, 196)
    # VREF biases all eight of the LSF0108's pass gates and its Vref_A is rated ±2 kV HBM only: an H5VU25UC of its
    # own (the audit's fix 7), one line in flow-through, west of the port's LED, over the header's west end
    # (VREF, its pin 2).  The header's VREF and its RESET/BOOT are 12.7 mm apart with the pairs' trunk over them:
    # one ESD apiece.  Logic only (on the base VREF ends on empty pads)
    part(s, f"U{k + 8}", "esd4", {"GND": "GND", "5": p + "VREF", "6": p + "VREF", "1": None, "10": None,
                                  "2": None, "9": None, "4": None, "7": None},
         pcb=P(hx - 8.0, 34.8, 90), sch=at(30, 172, fields=(-3, -7)))

    s.frame(f"Pins {n}: ESD in flow-through, 100 Ω, LSF0108 (A = the DUT's VREF, "
            f"B = 3.3 V) to crosspoint {'U7' if n <= 2 else 'U8'}'s X lines", 6, 104, 228, 146)
    lx = hx - 0.5                       # the LSF, its A face over the two slot columns
    for j, colx in enumerate((hx - 2.54, hx + 2.54)):
        pins = [LANE[4 * j + i] for i in range(4)]   # this column's P pins, west → east
        tpd = {"GND": "GND"}
        for pin, q in zip(TPD_SIG, pins):
            tpd[str(pin)] = tpd[str(TPD_THRU[pin])] = f"{p}P{q}"
        part(s, f"U{k + 5 + j}", "esd4", tpd, pcb=P(colx, TPD_Y, 90),
             sch=at(28 + 36 * j, 128, fields=(-3, -7)))
        # resistor k west → east, its pin k down (the ESD's side)
        rarray(s, f"RN{k + 1 + j}", "100", [(f"{p}P{q}", f"{p}A{q}") for q in pins],
               P(colx, RN_Y, 90), sch=at(50 + 36 * j, 128))
    lsf = {"GND": "GND", "RefA": p + "VREF", "RefB": p + "VREFB", "EN": p + "VREFB", "EPAD": "GND"}
    for c in range(1, 9):
        lsf[f"A{c}"] = f"{p}A{LANE[c - 1]}"
        lsf[f"B{c}"] = f"{p}B{LANE[c - 1]}"
    # turned 90°: A face down (VREF, A1 … A7, A8 round its east end), B face up, the references at the west end
    part(s, f"U{k + 7}", "lsf0108", lsf, pcb=P(lx, LSF_Y, 90), sch=at(132, 128, fields=(-10, -8)))
    rail(s, "GND", [f"U{k + 7}.GND", f"U{k + 7}.EPAD"], 2, "down")
    # its references' parts in a column left of it (port b: under the crosspoint's south-east corner)
    bx, by = lx - 4.0, LSF_Y - 1.0
    # Vref_B and EN from the board's +5V_MX through 200k (the usability review's finding 2, 2026-10-21): not the
    # port's VBUS, so a group is a voltage domain of its own, any board on any group.  TI requires Vref_B ≥
    # Vref_A + 0.8 V and recommends 1.0 V: with +5V_MX at 4.75 V, VREF up to ≈ 3.9 V translates as specified.  A 5 V
    # board with TTL inputs takes VREF from its own 3.3 V pin; at a 5 V VREF the bus rises to ≈ 4.0–4.2 V (outside
    # TI's conditions, harmless: the other ports clamp to their VREF, the RP2350B's GPIO tolerate 5 V powered)
    R(s, f"R{k + 11}", "200k", "+5V_MX", p + "VREFB", size="0402", pcb=P(bx, by, 0), sch=at(162, 122))
    # 0.15 mm west of the column: its GND pad clear of the LSF0108's pin-1 mark (silk over a pad otherwise)
    C(s, f"C{k + 5}", "100n", p + "VREFB", "GND", size="0402", pcb=P(bx - 0.15, by + 1.1, 0), sch=at(162, 130))
    s.wire(f"R{k + 11}.2", f"C{k + 5}.1")
    # VREF / 2 to the co-processor's ADC, and the pull-down that holds an unwired VREF low.  The bias current
    # (≈ 20 µA) leaves the LSF0108 by Vref_A: through 100k + 100k an unwired VREF would float up to ≈ 2.1 V and
    # the group would translate; through 10k + 10k it stays ≈ 0.4 V, under the 0.65 V minimum TI specifies.
    # That does not open the group: TI guarantees the off state only with EN low (SDLS966M §8.3.2), and below
    # Vref_A + VTH its pass gates still conduct, so lows pass both ways and highs into A clamp at ≈ 0.4 V.  The
    # isolation is the crosspoint's: the firmware keeps a port's switches open while its VREF reads under 0.65 V
    # (the audit's fix 8).  A wired VREF supplies VREF / 20k (165 µA at 3.3 V)
    R(s, f"R{k + 12}", "10k", p + "VREF", f"CP_VREF{n}", size="0402", pcb=P(bx, by + 2.2, 0), sch=at(180, 122))
    R(s, f"R{k + 13}", "10k", f"CP_VREF{n}", "GND", size="0402", pcb=P(bx, by + 3.3, 0), sch=at(180, 130))
    s.wire(f"R{k + 12}.2", f"R{k + 13}.1")
    # 100k in series to the ADC pin (the audit's U8, its conservative option): with the board off and a
    # self-powered DUT's VREF wired, the co-processor's unpowered GPIO40–43 would take VREF / 2 through 5k; through
    # 105k it is ≤ 20 µA.  The RP2350's ADC reads DC through it (§12.4.3); north of the divider, on the way up
    R(s, f"R{k + 15}", "100k", f"CP_VREF{n}", f"CP_ADC{n}", size="0402", pcb=P(bx, by - 2.1, 0),
      sch=at(196, 136, rot=90))
    # VREF comes from the DUT through the header, Vref_B from +5V_MX through 200k: no power output drives them
    s.part(f"#FLG{k + 1}", "power:PWR_FLAG", "PWR_FLAG", "", {"1": p + "VREF"}, in_bom=False, on_board=False,
           sch=at(200, 120))
    s.part(f"#FLG{k + 2}", "power:PWR_FLAG", "PWR_FLAG", "", {"1": p + "VREFB"}, in_bom=False, on_board=False,
           sch=at(212, 120))

    s.notes_at = (112, 62, 116)
    s.notes = [f"Port {n} = sub-slot A1.{n}, hub port {n}, busid 1-1.{n}.",
               f"INA226 at 0x{0x40 + [1, 3, 4, 5][n - 1]:02x}; expander {['U2', 'U6'][(n - 1) // 2]} "
               f"(0x{0x20 + (n - 1) // 2:02x}).",
               "ILIM 45.3k: 524 / 577 / 638 mA min / typ / max (TI SLVS841G §8.5.1 eq. 1–3), 519–644 mA with the",
               "  resistor's 1 %; the -1 latches off after 7.5 ms in limit, FAULT_N flags it.",
               "INA226 Vbus on the shunt's load-side sense pad (= VBUS).",
               "EN pulled down: the port stays off until the node switches it on.",
               "Pins: P1–P8 → crosspoint X lines (docs/electronics.md › DATA ×4 v2 map);",
               "  an unwired VREF stays ≈ 0.4 V, under the LSF0108's 0.65 V: the firmware keeps the port's",
               "  crosspoint switches open while its VREF reads under 0.65 V (GPIO40–43 under 0.33 V).",
               "ESD: VREF through U" + str(k + 8) + ", RESET_N / BOOT_N through U" + str(k + 9) + " (flow-through).",
               "VREF: the board's I/O supply, 0.95–3.6 V; a 5 V board with TTL inputs: its own 3.3 V pin.",
               "Source only (Rp from the switched VBUS); a back-feeding source trips the TPS2553 (latched).",
               "The DUT's RESET/BOOT pull-ups ≥ 4.7k: against 1k, the 1k in series stops at ≈ 1.65 V.",
               "VBUS LED: on while the port's switch is on (5V_SW, before the shunt)."]


# ----------------------------------------------------------------------------------- hub, lead, power
def hub_sheet(b: Board):
    s = b.sheet("Hub", "hub.kicad_sch", "Lead, hub, expanders, 3.3 V")
    s.paper = "A1"
    s.frame("Lead from the bay node's J7 (JST PH 8, vertical, on the rear face): SDA and SCL through a H5VU25UC; "
            "pin 8 VIN (sheet Power), pin 1 open", 6, 10, 70, 50)
    # through-hole on the rear face, soldered by hand (JLC's Economic assembly places the front face only), where
    # the lead comes up from the cable window (the cradle's interface), where the DATA ×6 has it (one lead, one
    # window): a vertical row at x 89 from pin 1 (open, the bottom) up to pin 8 (VIN, the top), the USB pair (5, 6)
    # under the hub.  Pin 8 the rack's 20 V, which the
    # node switches (its eFuse): VIN, the converter's (power_sheet()), so the node power-cycles the whole board;
    # solid to its pad.  Pin 1 open (2026-11-01, as the DATA ×6): the node polls instead of INT
    part(s, "J1", "ph8t", {"1": None, "2": "LEAD_SCL", "3": "LEAD_SDA", "4": "GND", "5": "UP_DN",
                           "6": "UP_DP", "7": "GND", "8": "VIN"}, "LEAD",
         pcb={**P(*LEAD, J1_ROT, "bottom"), "solid": ["8"]},
         sch=at(16, 30, mirror="y", fields=(-2, -6)))
    s.part("#FLG02", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "GND"}, in_bom=False, on_board=False, sch=at(34, 16))
    # the lead's I²C: one 4-line TVS array by J1's pin 1, where the DATA ×6 has it (front face, where J1's pins are
    # soldered by hand: clear of their pads)
    part(s, "U4", "esd4", {"D1+": "LEAD_SDA", "D1-": "LEAD_SCL", "D2+": None, "D2-": None, "GND": "GND"},
         pcb=P(LEAD[0] + 3.25, LEAD[1] + 0.9, 90), sch=at(48, 30, fields=(-3, -6)))
    # one part per value where the size allows (JLC bills each part type): 22 µF 0805 as the ports' VBUS (and
    # the 3.3 V LDO's), 1 µF and 4.7 µF in 0402

    s.frame("3.3 V for the hub, the expanders and the INA226s (AP2114H, SOT-223 on copper)", 6, 56, 70, 86)
    s.tag("+5V", (24, 66), "up")
    s.wire((24, 66), (24, 69), "U3.VI")
    # The USB2517I draws 330 mA with four High-Speed ports busy (DS00001598C Table 8-2, all supplies, typical;
    # 460 mA at most, with seven), the co-processor ≤ 45 mA, the expanders, the INA226s and the pull-ups the rest:
    # 0.51 A at worst, ≈ 0.9 W in the LDO from the +5V's 5.08 V (1.0 W from 5.22 V), 0.74 W typical.  Too much
    # for v1's AP2112K in SOT-23-5, so an AP2114H: the same low dropout (the hub keeps running while the ports sag
    # the +5V, as v1 wants), 1 A, in SOT-223, thermal shutdown at 160 °C (p.12).  Diodes gives 128 °C/W bare
    # (p.7): ≤ 125 °C at 40 °C takes ≤ 86 °C/W, so its tab sits on a top-side +3V3 island that runs west to the
    # edge band, doubled by a rear one, with fifteen vias (six into the +3V3 plane) and the In1 GND plane under
    # it all; the bring-up measures it.  Its VIN pin on a +5V island with two vias
    part(s, "U3", "ldo_1a", {"VI": "+5V", "VO": "+3V3", "GND": "GND"}, pcb=P(*LDO, 90),
         sch=at(34, 69, fields=(-3, -4)))
    C(s, "C2", "22u", "+5V", "GND", size="0805", pcb=P(LDO[0] + 2.9, LDO[1] + 6.9, 270), sch=at(20, 72))
    s.wire("C2.1", (20, 69), (24, 69))
    C(s, "C3", "22u", "+3V3", "GND", size="0805", pcb=P(LDO[0], LDO[1] - 6.3, 90), sch=at(44, 72))
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
        hub[f"OCS{n}_N"] = None             # on purpose: internal pull-ups, the node reads FAULT through the expanders
    for n in range(4, 8):
        hub[f"LED_B{n}_N"] = None
    for n in range(1, 5):
        hub[f"USBDN{n}_DP/PRT_DIS_P{n}"] = f"PORT{n}_DP"
        hub[f"USBDN{n}_DM/PRT_DIS_M{n}"] = f"PORT{n}_DN"
    hub["USBDN5_DP/PRT_DIS_P5"], hub["USBDN5_DM/PRT_DIS_M5"] = "CP_HUB_DP", "CP_HUB_DN"
    for n in (6, 7):                        # declared but unused, left enabled with nothing on them (cosmetic)
        hub[f"USBDN{n}_DP/PRT_DIS_P{n}"], hub[f"USBDN{n}_DM/PRT_DIS_M{n}"] = None, None
    # turned 90°: DN1–DN5 on its south face (down the column to the ports), the upstream pair, the crystal,
    # RBIAS and 1V8PLL on its west face, the straps north
    part(s, "U1", "usb2517", hub, pcb=P(HX, HY, 90), sch=at(124, 62, fields=(-11, -20)))
    # the seven 3.3 V pins on one rail
    rail(s, "+3V3", [f"U1.{n}" for n in (46, 64, 24, 5, 10, 52, 57)], -3)
    # the crystal right west of XTAL1/XTAL2 (west face pins 61/60), drawn on F.Cu with no via (the layout review,
    # 2026-10-28: "les pistes restent en top et routé au plus proche des pins, avec du GND autour"; xtal_block()).
    # Turned 90°: XI (pin 61, the lower) leaves its south-east pad straight east, XO (pin 60) its north-west one,
    # under the case between the two east pads (its own net only) and east too; each load capacitor on its pad
    part(s, "Y1", "xtal24", {"1": "XI", "3": "XO", "2": "GND", "4": "GND"}, pcb=P(*XT, 90),
         sch=at(94, 64, fields=(-2, -4)))
    C(s, "C4", "33p", "XI", "GND", size="0402", pcb=P(XT[0] + 0.37, XT[1] + 2.65, 180), sch=at(88, 68))
    C(s, "C5", "33p", "XO", "GND", size="0402", pcb=P(XT[0] - 0.85, XT[1] - 3.1, 90), sch=at(100, 68))
    s.wire("Y1.1", (88, 64), "C4.1")
    s.wire("Y1.3", (100, 64), "C5.1")
    # 1 MΩ across XTAL1–XTAL2 as the datasheet's Fig. 9-1 draws it (and Microchip's EVB fits it, R19): DS00001598C
    # never says it is inside (the audit's U2, its conservative option); right east of the crystal, across XO and XI
    R(s, "R10", "1M", "XO", "XI", size="0402", pcb=P(XT[0] + 2.3, XT[1] + 0.25, 270), sch=at(94, 56, rot=90))
    # decoupling, by pin: west 64 (C11 below the corner, its +3V3 pad up), 57 and 52; south 5 (C15 right under
    # it, between ports 2 and 3's pairs) and 10 (C16 right under it, by port 4's pair); east 24; north 46 (C17 right over it, in
    # the straps' row, its +3V3 pad down: R3 gave it the spot)
    for i, (ref, xy, rot) in enumerate((("C11", (HX - 4.7, HY + 6.2), 270), ("C13", (HX - 6.2, HY + 0.25), 180),
                                        ("C12", (HX - 6.2, HY - 2.25), 180), ("C15", (HX - 1.75, HY + 6.4), 270),
                                        ("C16", (HX + 0.95, HY + 6.7), 270), ("C14", (HX + 6.05, HY + 0.95), 270),
                                        ("C17", (HX - 2.85, HY - 6.4), 90))):
        C(s, ref, "100n", "+3V3", "GND", size="0402", pcb=P(*xy, rot), sch=at(80 + 6 * i, 24))
    # VDD18 / VDD18PLL: the datasheet's 1.0 µF ± 20 % has no margin left once a 0402's DC bias and temperature
    # are counted (the audit's U10): 4.7 µF, the board's 4.7 µF line
    C(s, "C8", "4.7u", "HUB_1V8PLL", "GND", size="0402", pcb=P(HX - 6.8, HY + 4.86, 270), sch=at(128, 24))
    C(s, "C10", "100n", "HUB_1V8PLL", "GND", size="0402", pcb=P(HX - 5.66, HY + 3.93, 270), sch=at(134, 24))
    # VDD18's 100 nF (C9) right at its pin (25), its 4.7 µF (C7) behind it: the store may sit further
    C(s, "C7", "4.7u", "HUB_1V8", "GND", size="0402", pcb=P(HX + 6.05, HY - 3.0, 90), sch=at(146, 24))
    C(s, "C9", "100n", "HUB_1V8", "GND", size="0402", pcb=P(HX + 6.05, HY - 0.9, 90), sch=at(152, 24))
    # RBIAS and the reset: a MAX809S supervisor drives RESET_N (the audit's fix 6).  The hub's errata
    # (DS80000628A, Module 2): "The internal POR does not generate reset when power drops below the threshold
    # … Use external power on reset circuit (for example … MAX809S (V2.9V) voltage supervisor)": an RC resets a
    # clean ramp only, and a +5V sag (a DUT's inrush, a short) could leave the hub hung.  RESET low below
    # 2.93 V (2.78–3.08 V over temperature) and for 150–560 ms after +3V3 is back, push-pull; its 100 nF (C6) right
    # over its VCC pin (3), its +3V3 pad in line with it (drawn in board()).  Over the north face, its RESET pad right above RESET_N (pin 43).  RESET_N is the hub's alone
    # (the schematic review's S2 tied the co-processor's RUN to it through D2 until CFG_SEL 110)
    R(s, "R1", "12k", "RBIAS", "GND", size="0402", pcb=P(HX - 5.75, HY + 6.6, 270), sch=at(84, 92))
    part(s, "U5", "max809s", {"GND": "GND", "~{RESET}": "HUB_RST_N", "VCC": "+3V3"},
         pcb=P(HX - 2.2, HY - 10.1, 90), sch=at(90, 80, fields=(-4, -5)))
    C(s, "C6", "100n", "+3V3", "GND", size="0402", pcb=P(HX - 2.68, HY - 12.7, 180), sch=at(78, 84))
    # CFG_SEL[2:0] = 110 since 2026-10-25: "Internal Default Configuration, Strap Options are Disabled" (DS00001598C
    # Table 5-2 p. 16, the user's reading).  The hub loads Table 7-1's defaults (§7.4 p. 41), which are what our
    # straps set (CFG1 9Bh: self-powered, individual port switching and over-current sensing; NRD, BOOST, PRT_SWP
    # 00h; CFG2 20h, CFG3 00h), and no longer samples D+ / D− as port-disable straps (PDS = PDB = 00h: every port
    # enabled): a self-powered DUT present at the hub's reset keeps its port, and the co-processor's D+ pull-up
    # races nothing (the schematic review's S2 and its D2 are gone).  CFG_SEL1 (HS_IND, pin 42) and CFG_SEL2 up
    # through 10k, CFG_SEL0 (SCL) down, all static at RESET_N's rise.  HS_IND drives after reset (I/O12, 12 mA):
    # 0.33 mA into its 10k, and it lights no LED here (CFG_SEL1 high makes it active low).  The other strap
    # pins keep their pull-downs (X8; no longer read, but they bias the LED outputs and SUSP_IND, I/O12 buffers
    # that may float tri-stated, their input receiver not said to be off: the user's call, 2026-10-27): over
    # the north face in two rows (the pins at 0.5 mm leave no room for one row), a resistor over its pin, the
    # west face's three round the corner into RN1; CFG2, SWP7 and SWP6 round the south-east corner into RN3.
    # R3 (SWP3, pin 47) over RN1, its pin's spot C17's (pin 46's 100 nF)
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
        rail(s, "GND", [f"RN{1 + i}.{9 - k}" for k in range(1, 5) if nets[k - 1] and nets[k - 1] not in up], 2, "down")
        if nets[0] in up:
            rail(s, "+3V3", [f"RN{1 + i}.8"], 2, "down")

    s.frame("Two TCA6408A expanders, one per pair of ports: EN, FAULT_N, RESET, BOOT", 172, 10, 228, 70)
    # each RESET through 10k to +3V3 (TI: "connect to VCCI through a pull-up resistor, if no active connection
    # is used"; the audit's U9, its conservative option), the resistor by pin 1.  Its 100 nF (C18, C19) stands
    # right over VCCI (pin 15), its +3V3 pad down (drawn in board())
    for i, (ref, cref, (x, y, addr), sy) in enumerate((("U2", "C18", EXP[0], 24), ("U6", "C19", EXP[1], 52))):
        exp = {"V_{CCI}": "+3V3", "V_{CCP}": "+3V3", "~{RESET}": f"EXP{i + 1}_RST_N", "GND": "GND", "EPAD": "GND",
               "ADDR": addr, "SCL": "SCL", "SDA": "SDA", "~{INT}": None}
        for half, n in (("a", 2 * i + 1), ("b", 2 * i + 2)):
            for pin, sig in EXP_LINES[half].items():
                exp[pin] = f"PORT{n}_{sig}"
        part(s, ref, "tca6408", exp, pcb=P(x, y, 0), sch=at(200, sy, fields=(-4, -9)))
        C(s, cref, "100n", "+3V3", "GND", size="0402", pcb=P(x - 0.25, y - 3.25, 90), sch=at(184, sy - 4))
        R(s, f"R{11 + i}", "10k", "+3V3", f"EXP{i + 1}_RST_N", size="0402", pcb=P(x - 3.1, y - 1.7, 270),
          sch=at(178, sy + 8))

    # X2 (as v1): the lead's bus (LEAD_*, the node's pull-ups) and this board's (SDA/SCL, pulled up here),
    # a 2N7002 per line, gate on +3V3 (NXP AN10441).  Either side pulling low turns the FET on (the body
    # diode starts it from the lead's side); with VIN off it stays off, so the node's pull-ups cannot feed
    # this board's dead +3V3 through the chips' clamps.  Under J1, in the right-hand column.
    s.frame("I²C isolation: open with VIN off, so the node's pull-ups cannot feed this board", 172, 76, 228, 130)
    for i, (q, r, line, val) in enumerate((("Q1", "R6", "SDA", "4.7k"), ("Q2", "R7", "SCL", "4.7k"))):
        y = 49.6 + 3.7 * i
        part(s, q, "nfet", {"G": "+3V3", "S": line, "D": "LEAD_" + line}, pcb=P(86.5, y, 0),
             sch=at(190, 88 + 14 * i))
        R(s, r, val, "+3V3", line, size="0402", pcb=P(83.0, y, 90), sch=at(210, 86 + 14 * i))
    testpoints(s, ["TP7", "TP8", "TP9", "TP20", "TP21", "TP22", "TP24", "TP25", "TP26", "TP27", "TP28",
                   "TP38", "TP39"],
               "Bring-up test points on the rear face (B.Cu, bare pads, not in the BOM): +3V3, +5V, the hub's "
               "reset and 1.8 V, the lead's I²C, the expanders' RESET, GND")
    s.notes_at = (6, 110, 220)
    s.notes = [
        "Hub reset: U5 (MAX809S, 2.93 V, ≥ 150 ms, push-pull) on RESET_N (errata DS80000628A, Module 2).",
        "Hub: CFG_SEL[2:0] = 110 (internal default configuration, strap options disabled: DS00001598C Table 5-2):",
        "  self-powered, ports switched and sensed one by one (here by the expanders), no port disabled, D+ / D− not",
        "  sampled at reset; the other strap pins keep their pull-downs, unread.  Ports 6 and 7 enabled, unused",
        "  (cosmetic).  On purpose: PRTPWR unused and OCS_N on their pull-ups (the node switches each port and reads",
        "  its FAULT_N through the expanders); VBUS_DET on 3.3 V (self-powered hub).",
        "Hub port n = USB-C n (busid 1-1.n) for n = 1–4; port 5 = the co-processor.",
        "Expander pins are inputs at power-up; the EN pull-downs keep every port off until the node writes.",
        "No INT on the lead (J1.1 open): the node polls the expanders and the INA226s every 10–20 ms.",
        "I²C: the node's pull-ups on LEAD_*, 4.7k / 4.7k here; with VIN off the chips here lose their registers:",
        "  the node sets them up again after each VIN on, and leaves this board's addresses alone while off.",
        "J1 (through-hole) stands on the rear face: soldered by hand (the PCBA places the front face only).",
    ]


# ------------------------------------------------------------------------------------------- 20 V → 5 V
def power_sheet(b: Board):
    s = b.sheet("Power", "power.kicad_sch", "20 V input, the 5 V converter")
    s.paper = "A2"
    s.frame("VIN: the rack's 20 V, switched by the node (its eFuse), from the PH 8 lead's pin 8 (J1, sheet Hub)",
            6, 10, 62, 50)
    s.part("#FLG01", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "VIN"}, in_bom=False, on_board=False, sch=at(28, 18))
    # the input's bulk against a hot plug's overshoot (the node's lead is ≈ 50 cm, the converter's ceramics alone
    # ring), the DATA ×6's: right under the converter's 10 µF, where its 7.7 mm clear the strip on the cradle's comb
    part(s, "C60", "cap33u50", {"1": "VIN", "2": "GND"}, "33u", pcb=P(*BULK, 0), sch=at(40, 30))
    # EN 100k/10k, as the node's: the converter starts above 13.5 V typ. (15.1 V at worst) and stops below 10.8 V;
    # west of its 10 µF
    bx, by = BUCK
    R(s, "R50", "100k", "VIN", "BUCK_EN", size="0402", pcb=P(bx - 4.7, by + 4.7, 90), sch=at(29, 41.5))
    R(s, "R51", "10k", "BUCK_EN", "GND", size="0402", pcb=P(bx - 3.6, by + 4.7, 90), sch=at(29, 48.5))
    s.wire("R50.2", "R51.1")
    # the DATA ×6's converter A, part for part and at the same offsets from U13
    x0 = 70
    s.frame("+5V: LMR51635, synchronous, 1.1 MHz, 3.5 A (the DATA ×6's block, TI SLUSF64B table 8-2)",
            x0 - 4, 10, x0 + 64, 50)
    s.tag("VIN", (x0 + 2, 16), "up")
    s.wire((x0 + 2, 16), (x0 + 25, 16), (x0 + 25, 23), "U13.VIN")
    C(s, "C61", "10u", "VIN", "GND", size="1206", pcb=P(bx, by + 4.8, 0), sch=at(x0 + 6, 19.5))
    C(s, "C62", "10u", "VIN", "GND", size="1206", pcb=P(bx, by + 7.4, 0), sch=at(x0 + 10, 19.5))
    C(s, "C63", "100n", "VIN", "GND", pcb=P(bx, by + 2.6, 0), sch=at(x0 + 14, 19.5))
    for c_, x in (("C61", 6), ("C62", 10), ("C63", 14)):
        s.wire((x0 + x, 16), f"{c_}.1")
    s.tag("BUCK_EN", (x0 + 19, 22), "left")
    s.wire((x0 + 19, 22), (x0 + 23, 22), (x0 + 23, 25), "U13.EN")
    part(s, "U13", "buck", {"VIN": "VIN", "EN": "BUCK_EN", "CB": "BUCK_CB", "SW": "BUCK_SW", "FB": "BUCK_FB",
                              "GND": "GND"}, pcb=P(bx, by, 0), sch=at(x0 + 30, 24, fields=(-4, -4)))
    C(s, "C64", "100n", "BUCK_CB", "BUCK_SW", pcb=P(bx + 1.6, by - 2.5, 0), sch=at(x0 + 41.5, 19, rot=90))
    s.wire("U13.CB", (x0 + 36, 23), (x0 + 36, 19), "C64.1")
    s.wire("C64.2", (x0 + 43, 24))
    # 3.3 µH rated 75 V (the 28 V EPR rail ahead; the FXL0630's 30 V would not do), on the FXL0630's footprint
    part(s, "L2", "buck_l_75v", {"1": "BUCK_SW", "2": "+5V"}, "3.3u", pcb=P(bx + 7.7, by, 0),
         sch=at(x0 + 47.5, 24, rot=90))
    s.wire("U13.SW", (x0 + 43, 24), "L2.1")
    s.wire("L2.2", (x0 + 62, 24))
    s.tag("+5V", (x0 + 62, 24), "up")
    for j, x in enumerate((50, 54, 58)):
        C(s, f"C{65 + j}", "22u", "+5V", "GND", size="1206", pcb=P(bx + 6 + 2.5 * j, by + 6.5, 270),
          sch=at(x0 + x, 25.5))
    R(s, "R52", "100k", "+5V", "BUCK_FB", pcb=P(bx - 3.5, by - 1.2, 270), sch=at(x0 + 62, 30))
    # 18.7k, not the node's 18k: 5.08 V, under the TPS60400's 5.25 V (U9, the matrix's −5 V) at the worst corner
    R(s, "R53", "18.7k", "BUCK_FB", "GND", pcb=P(bx - 3.5, by + 1.8, 270), sch=at(x0 + 62, 37),
      fields={"LCSC": "C22893", "MPN": "0603WAF1872T5E", "Manufacturer": "UNI-ROYAL(Uniroyal Elec)"})
    s.wire("R52.2", "R53.1")
    s.wire((x0 + 62, 33.5), (x0 + 36, 33.5), (x0 + 36, 25), "U13.FB")
    s.part("#FLG03", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+5V"}, in_bom=False, on_board=False,
           sch=at(x0 + 58, 14))
    testpoints(s, ["TP40"], "Bring-up test point on the rear face (B.Cu): VIN", x0=138)
    s.notes_at = (6, 56, 200)
    s.notes = [
        "The DATA ×6's converter with the family's 3.5 A part (TI SLUSF64B table 8-2, LMR51635, 5 V, 1.1 MHz: 3.3 µH",
        "  Vishay IHLP2525CZ, 75 V, 13.5 A sat; 2 × 10 µF + 100 nF in, 3 × 22 µF out), PFM and spread spectrum as the",
        "  ×6's LMR51625.",
        "+5V: the four ports, the 3.3 V LDO (≤ 0.51 A) and the matrix: 2.51 A at 0.5 A a port; at worst, all four at",
        "  the TPS2553s' 0.644 A limit, 3.09 A, under the LMR51635's 3.5 A with no help from the node's firmware.",
        "  The inductor then peaks at 3.68 A from 28 V (1.17 A ripple), 3.98 A at the worst corner (L −20 %, 0.99 MHz),"
        "  under the LMR51635's 4.2 A minimum peak limit (SLUSF64B §6.5: 4.2 / 5.1 / 6.0 A; valley 3.2 / 4.0 / 4.8 A);",
        "  from 13.5 V: peak 3.53 A, valley 2.65 A.  No frequency foldback (tON 170 ns ≥ 70, tOFF 556 ns ≥ 200).",
        "FB 100k/18.7k: 5.08 V, 4.94–5.22 V with VFB 0.792–0.808 V (SLUSF64B §6.5) and the 1 % resistors: under",
        "  the TPS60400's 5.25 V (U9, sheet Matrix), which the node's 18k (5.10–5.39 V) was not.",
        "EN 100k/10k: on above 13.5 V typ., up to 14.8 V on the EN threshold's 1.103–1.349 V (SLUSF64B §6.5) and",
        "  15.1 V with the 1 % resistors: the rack's 20 V clears it.  Off below 10.8 V typ.",
        "VIN on J1.8, the node's VRACK through its eFuse (TPS26600, off by default): no second protection here.",
        "  At the 3.09 A worst case from 5.22 V (η ≈ 88 %): 0.92 A at 20 V, 1.22 A at 15 V, 1.36 A at 13.5 V, 0.65 A",
        "  at 28 V; the converter's full 3.5 A: 1.38 A at 15 V.  Under the node eFuse's 1.76 A; a PH contact carries 2 A.",
    ]


def buck_copper(sw: str, out: str, bx: float, by: float, tag: str) -> tuple[list, list]:
    """The converter's switch node and output as pours on F.Cu, the output's with vias down to its power plane: the
    layout review (2026-11-01) found the inductor's output reaching the plane through one via and a 0.4 mm track,
    the switch node through 0.45 mm tracks.  (bx, by): U13's centre, the block's offsets as power_sheet()'s.
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


# ------------------------------------------------------------------------------------ matrix (full)
def matrix_sheet(b: Board):
    s = b.sheet("Matrix", "matrix.kicad_sch", "Crosspoints, −5 V, the node's matrix expander")
    s.paper = "A1"
    for c, (chx, chy) in enumerate(CHIP):
        na, nb = 2 * c + 1, 2 * c + 2
        u, y0 = f"U{7 + c}", 10 + 74 * c
        s.frame(f"Crosspoint {u} (CH446Q at ±5 V, serial addressing): X = ports {na}–{nb}'s pins, Y0–Y7 = buses {Y_BUS}",
                6, y0, 110, y0 + 68)
        conns = {"VDD": "+5V_MX", "VEE": "-5V", "GND": "GND", "DAT": "MX_DAT", "CS/CK": "MX_CK", "STB": f"MX_STB{c + 1}",
                 "RST": "MX_RST", "P/~{S}": "GND", **{f"AX{i}": "GND" for i in range(4)},
                 **{f"AY{i}": "GND" for i in range(3)}}
        for i in range(8):
            conns[f"Y{i}"] = f"BUS_{Y_BUS[i]}"
        # each port's LSF channels land on the X lines beside them (XMAP; the map in docs/electronics.md)
        for port_n, west in ((na, True), (nb, False)):
            for lane, x in XMAP[west].items():
                conns[f"X{x}"] = f"PORT{port_n}_B{LANE[lane - 1]}"
        part(s, u, "ch446q", conns, pcb=P(chx, chy), sch=at(54, y0 + 32, fields=(-8, -14)))
        # GND and the address pins (parallel address, unused in serial mode) on one rail
        rail(s, "GND", [f"{u}.{n}" for n in (40, 21, 20, 42, 19, 18, 43, 12)], 2, "down")
        # each supply's decoupling on the face of its pin: VDD (+5V, pin 38) north, VEE (−5V, pin 16) south,
        # between the bus lines leaving those faces
        C(s, f"C{20 + 3 * c}", "100n", "+5V_MX", "GND", size="0402", pcb=P(chx + 0.8, chy - 7.75, 90),
          sch=at(78, y0 + 14))
        C(s, f"C{21 + 3 * c}", "1u", "+5V_MX", "GND", size="0402", pcb=P(chx + 0.8, chy - 9.8, 90),
          sch=at(84, y0 + 14))
        C(s, f"C{22 + 3 * c}", "100n", "-5V", "GND", size="0402", pcb=P(chx - 0.8, chy + 7.75, 270),
          sch=at(30, y0 + 54))

    s.frame("+5V_MX through a ferrite (the crosspoints, the inverter, the LSF0108s' bias); −5 V for the "
            "crosspoints' VEE (TPS60400 inverter)", 114, 10, 228, 52)
    # The −5 V on purpose: at a single 5 V the CH446Q's R_on is 120–225 Ω, and a 1.8 V board's I²C low would fail.
    # The matrix's +5V: the crosspoints' VDD, the −5 V inverter, the LSF0108s' bias and the +5V sense divider
    # (≈ 1–4 mA in all) behind a 600 Ω ferrite (≈ 1 µH low down: little filtering at the pump's 50–250 kHz, a
    # DC path of its own).  In the left-hand column under the power plane's split: its +5V end over the +5V
    # area; +5V_MX is routed up to the loads (Supply)
    part(s, "FB1", "fb600", {"1": "+5V", "2": "+5V_MX"}, pcb=P(8.6, 63.4, 270), sch=at(124, 18))
    s.wire("FB1.1", ("FB1.1", -3, 0))
    s.tag("+5V", ("FB1.1", -3, 0), "left")
    s.wire("FB1.2", ("FB1.2", 3, 0))
    s.tag("+5V_MX", ("FB1.2", 3, 0), "right")
    s.part("#FLG06", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+5V_MX"}, in_bom=False, on_board=False,
           sch=at(132, 14))
    # in the left-hand column beside the left crosspoint; −5 V on to the right one is a low-current line.  Its
    # input and output capacitors (C27, C28) right west of IN and OUT (pins 2, 1), on lines of their own
    part(s, "U9", "tps60400", {"IN": "+5V_MX", "OUT": "-5V", "C_{FLY+}": "CP_FLYP", "C_{FLY-}": "CP_FLYN", "GND": "GND"},
         pcb=P(10.0, 24.0, 0), sch=at(150, 30, fields=(-4, -6)))
    C(s, "C26", "1u", "CP_FLYP", "CP_FLYN", size="0402", pcb=P(10.0, 26.8, 0), sch=at(170, 36))
    C(s, "C27", "1u", "+5V_MX", "GND", size="0402", pcb=P(6.95, 24.05, 180), sch=at(132, 34))
    C(s, "C28", "1u", "-5V", "GND", size="0402", pcb=P(6.95, 23.0, 180), sch=at(186, 36))

    s.frame("The node's matrix expander (TCA9534A, 0x38): the crosspoints and the co-processor's RUN / BOOTSEL",
            114, 58, 228, 110)
    # under the 5 V converter, right beside the left crosspoint (U7)
    part(s, "U10", "tca9534", {"VDD": "+3V3", "GND": "GND", "A0": "GND", "A1": "GND", "A2": "GND", "SCL": "SCL",
                               "SDA": "SDA", "~{INT}": None, "P0": "MX_DAT", "P1": "MX_CK", "P2": "MX_STB1",
                               "P3": "MX_STB2", "P4": "MX_RST", "P5": "CP_RUN", "P6": "CP_BOOT_N", "P7": "MARK"},
         pcb=P(*MX_EXP, 90), sch=at(160, 84, fields=(-10, -8)))
    rail_v(s, "GND", ["U10.A0", "U10.A1", "U10.A2"], -2, "down")
    # its 100 nF (C29) right west of VDD (pin 16, top left), its +3V3 pad up (drawn in board())
    C(s, "C29", "100n", "+3V3", "GND", size="0402", pcb=P(MX_EXP[0] - 3.45, MX_EXP[1] - 1.7, 270), sch=at(140, 74))
    # RST held high (all switches open) until the node writes the expander; TCA9534A pins are inputs at reset.  East
    # of the package, between it and U7
    R(s, "R20", "10k", "+3V3", "MX_RST", size="0402", pcb=P(MX_EXP[0] + 3.45, MX_EXP[1] - 1.6, 90),
      sch=at(190, 76))
    s.notes_at = (114, 116, 110)
    s.notes = ["CH446Q serial mode (P/S low): 7 address bits on CK, data on DAT, latched by STB; RST high = all open.",
               "TCA9534A 0x38: P0 DAT, P1 CK, P2 STB U7, P3 STB U8, P4 RST, P5 RUN, P6 BOOTSEL, P7 mark.",
               "RUN and BOOTSEL are open drain emulated (output register 0, the pin switched to output).",
               "±5 V on purpose: at a single 5 V R_on is 120–225 Ω, and a 1.8 V board's I²C low would fail."]
    testpoints(s, ["TP4", "TP5", "TP6", "TP14", "TP15", "TP16", "TP17", "TP18", "TP19", "TP29", "TP30", "TP31",
                   "TP32", "TP33", "TP34", "TP35", "TP36", "TP37"],
               "Bring-up test points on the rear face (B.Cu): ±5 V, the expander's bus and RST, buses A–H, GND "
               "(logic only)")


# -------------------------------------------------------------------------------- co-processor (full)
def coproc_sheet(b: Board):
    s = b.sheet("Co-processor", "coproc.kicad_sch", "RP2350B analyzer / co-processor on hub port 5")
    cx, cy = CP
    s.paper = "A1"
    s.frame("RP2350B, wired like a Pico 2 less its flash (the analyzer loaded into SRAM at power-up); its decoupling",
            6, 10, 120, 118)
    gp = {"GPIO0": "CP_TRIG", "GPIO1": "CP_TRIG", "GPIO14": "MARK", "GPIO25": "CP_LED",
          "GPIO44/ADC4": "CP_SNS_5V", "GPIO45/ADC5": "CP_SNS_N5V"}
    for i, bus in enumerate(BUSES):
        gp[f"GPIO{2 + i}"] = f"BUS_{bus}"
        gp[f"GPIO{PU_GPIO[bus]}"] = f"CP_PU_{bus}"
    # VREF 1–4 on GPIO40, 43, 42, 41 (pins 49, 54, 53, 52): ports 2 and 4 swapped (2026-10-28) so their lines
    # leave pins 52 and 54 for B.Cu without crossing, round C45 at DVDD pin 51
    for n, g in enumerate((40, 43, 42, 41)):
        gp[f"GPIO{g}/ADC{g - 40}"] = f"CP_ADC{n + 1}"
    for g in [15] + list(range(20, 25)) + list(range(26, 40)) + [46, 47]:
        gp[f"GPIO{g}" if g < 40 else f"GPIO{g}/ADC{g - 40}"] = None
    rp = {"IOVDD": "+3V3_CP", "QSPI_IOVDD": "+3V3_CP", "USB_OTP_VDD": "+3V3_CP", "ADC_AVDD": "+3V3_CP",
          "VREG_VIN": "+3V3_CP", "VREG_AVDD": "CP_VREG_AVDD", "VREG_PGND": "GND", "VREG_LX": "CP_VREG_LX",
          "VREG_FB": "+1V1", "DVDD": "+1V1", "GND": "GND", "XIN": "CP_XIN", "XOUT": "CP_XOUT",
          "USB_DP": "CP_DP", "USB_DM": "CP_DN", "RUN": "CP_RUN", "~{QSPI_SS}": "CP_QSPI_SS",
          "SWCLK": "CP_SWCLK", "SWDIO": "CP_SWDIO", "QSPI_SCLK": None, "QSPI_SD0": None, "QSPI_SD1": None,
          "QSPI_SD2": None, "QSPI_SD3": None, **gp}
    # turned 180°: GPIO2–9 at the south-east corner (the buses, A and B on the south face), the pull-up
    # enables up the east face, the ADC west (the ports' VREFs), the core regulator and USB south-west,
    # XIN/XOUT, SWD, RUN and the LED north (the top edge)
    # the RP2350B (2026-11-03: NextPCB had no RP2354B): QSPI_SS still selects BOOTSEL, SCLK and SD0–SD3 stay
    # open.  An RP2354B fits as it is and boots from its own flash (RP2350 datasheet §14.3)
    part(s, "U11", "rp2350b", rp, pcb=P(cx, cy, 180), sch=at(60, 70, fields=(-10, -27)))
    rail(s, "+3V3_CP", ["U11.USB_OTP_VDD", "U11.ADC_AVDD", "U11.QSPI_IOVDD", "U11.IOVDD", "U11.VREG_VIN"], -3)
    rail(s, "+1V1", ["U11.VREG_FB", "U11.DVDD"], -5)
    rail(s, "GND", ["U11.VREG_PGND", "U11.GND"], 2, "down")
    rail_v(s, "CP_TRIG", ["U11.GPIO0", "U11.GPIO1"], 2, "right")
    s.part("#FLG04", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+1V1"}, in_bom=False, on_board=False, sch=at(196, 38))
    s.frame("Its 3.3 V from +3V3 through a ferrite, the core regulator as Raspberry Pi lays it out (3.3 µH, 3 × 4.7 µF, 33 Ω)",
            124, 10, 228, 52)
    # +3V3_CP: the board's +3V3 through a 600 Ω ferrite (the usability review's finding 4, 2026-10-21: no LDO of
    # its own, an extended part type less; U3 takes its ≈ 15–45 mA), in place of the AP2112K above the
    # co-processor's north-west corner; its 4.7 µF on the island side
    s.tag("+3V3", (140, 22), "up")
    part(s, "FB2", "fb600", {"1": "+3V3", "2": "+3V3_CP"}, pcb=P(cx - 8.5, 4.6, 0), sch=at(150, 25, rot=90))
    s.wire((140, 22), (140, 25), "FB2.1")
    s.part("#FLG07", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+3V3_CP"}, in_bom=False, on_board=False,
           sch=at(166, 20))
    C(s, "C31", "4.7u", "+3V3_CP", "GND", size="0402", pcb=P(cx - 5.4, 4.6, 90), sch=at(160, 28))
    s.wire("FB2.2", (160, 25), "C31.1")
    s.wire((160, 25), (168, 25), net="+3V3_CP")
    s.tag("+3V3_CP", (168, 25), "right")
    # The core regulator as Raspberry Pi lays it out (the audit's fix 2: "Designers should follow … Figure 26 as
    # closely as possible"): their RP2350B Minimal R4 block, turned 180° with U11, so VREG pins 61–65 (AVDD, PGND,
    # LX, VIN, FB, west → east) face south.  CIN straddles VIN and PGND 1.16 mm out from the pin row, COUT right
    # behind it, L1 behind COUT with its axis along the chip's edge, the +1V1 pad (its dot, pad 1) on the FB
    # side; RFILT / CFILT west of them.  LX runs between CIN's and COUT's pads to L1, on F.Cu; the copper is
    # drawn in board() (PGND, VIN, LX, +1V1, FB, AVDD, the vias), the planes cut under LX and L1 (fix 3)
    part(s, "L1", "l3u3_vreg", {"1": "+1V1", "2": "CP_VREG_LX"}, pcb=P(cx - 3.0, cy + 8.65, 180),
         sch=at(136, 42, rot=90))
    # CIN and COUT on Raspberry Pi's own 0402 land (pads 0.56 mm apart): LX passes between them 0.3 mm wide
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
    # 100 nF round the package, one per IOVDD pin group (at 180°: west 41, 50, 59/60; south 68/69, 76;
    # east 5, 15; north 24, 29), and per DVDD pin (+1V1: west 51, east 10, north 32; south 65 on C33)
    decap = [(cx - 6.7, cy - 3.8, 180), (cx - 6.7, cy - 1.8, 180), (cx - 6.7, cy + 3.6, 180),
             (cx + 0.7, cy + 7.4, 270), (cx + 3.0, cy + 7.4, 270), (cx + 6.4, cy + 5.6, 0),
             (cx + 6.6, cy - 5.9, 0), (cx + 4.45, cy - 7.4, 90), (cx + 3.0, cy - 7.4, 90),
             (cx - 2.2, cy - 7.4, 90)]
    for i, (x, y, rot) in enumerate(decap):
        C(s, f"C{35 + i}", "100n", "+3V3_CP", "GND", size="0402", pcb=P(x, y, rot), sch=at(12 + 5 * i, 24))
    rail(s, "+3V3_CP", [f"C{35 + i}.1" for i in range(10)], -1)
    rail(s, "GND", [f"C{35 + i}.2" for i in range(10)], 1, "down")
    # pin 32, the DVDD pin furthest from the regulator: 4.7 µF (DS §6.1.3, the audit's fix 4).  C45 right west of
    # pin 51, on its line (drawn in board())
    for i, (x, y, rot) in enumerate(((cx - 6.62, cy + 0.2, 180), (cx + 7.0, cy + 4.4, 0), (cx - 0.6, cy - 7.4, 90))):
        C(s, f"C{45 + i}", "4.7u" if i == 2 else "100n", "+1V1", "GND", size="0402", pcb=P(x, y, rot),
          sch=at(70 + 5 * i, 24))
    rail(s, "+1V1", [f"C{45 + i}.1" for i in range(3)], -1)
    rail(s, "GND", [f"C{45 + i}.2" for i in range(3)], 1, "down")
    s.frame("12 MHz crystal (ABM8-272-T3, 15 pF, 1k on XOUT), USB on hub port 5 (27 Ω), RUN, BOOTSEL, LED, SWD",
            124, 56, 228, 98)
    # over the north face's XIN (pin 30) and XOUT (31): XIN to its pin 1 (right), XOUT through R22 to pin 3 (left);
    # the lines drawn, the block kept clear on F.Cu (xtal2_block())
    part(s, "Y2", "xtal12", {"1": "CP_XIN", "3": "CP_XTAL", "2": "GND", "4": "GND"}, pcb=P(cx + 1.3, 2.2, 180),
         sch=at(140, 68, fields=(-2, -4)))
    C(s, "C48", "15p", "CP_XIN", "GND", size="0402", pcb=P(cx + 4.4, 1.6, 90), sch=at(134, 72))
    C(s, "C49", "15p", "CP_XTAL", "GND", size="0402", pcb=P(cx - 1.4, 1.4, 90), sch=at(146, 72))
    s.wire("Y2.1", (134, 68), "C48.1")
    s.wire("Y2.3", (146, 68), "C49.1")
    R(s, "R22", "1k", "CP_XOUT", "CP_XTAL", size="0402", pcb=P(cx - 1.6, 3.4, 90),
      sch=at(156, 68, rot=270))
    s.wire("C49.1", (146, 68), "R22.2")
    # The USB series resistors: 27 Ω, the only value Raspberry Pi specifies (RP2350 datasheet §1.2.2 Table 2 and
    # Table 1673; Hardware design with RP2350 §5.1), which publishes no figure for the driver's own impedance to
    # justify another.  No JLC basic part: the basic resistors' UNI-ROYAL series, extended
    usb27 = {"LCSC": "C25100", "MPN": "0402WGF270JTCE", "Manufacturer": "UNI-ROYAL(Uniroyal Elec)"}
    R(s, "R23", "27", "CP_DP", "CP_HUB_DP", size="0402", pcb=P(cx + 2.4, cy + 10.4, 270), fields=usb27,
      sch=at(140, 84, rot=90))
    R(s, "R24", "27", "CP_DN", "CP_HUB_DN", size="0402", pcb=P(cx + 1.3, cy + 10.4, 270), fields=usb27,
      sch=at(140, 90, rot=90))
    R(s, "R25", "10k", "+3V3_CP", "CP_RUN", size="0402", pcb=P(cx - 3.8, 5.4, 0),
      sch=at(166, 84))
    R(s, "R26", "1k", "CP_BOOT_N", "CP_QSPI_SS", size="0402", pcb=P(cx + 3.85, cy + 9.4, 270),
      sch=at(178, 86, rot=90))
    R(s, "R27", "1k", "CP_LED", "CP_LED_A", size="0402", pcb=P(cx + 6.4, 5.4, 0),
      sch=at(178, 68, rot=90))
    part(s, "D1", "led_g", {"A": "CP_LED_A", "K": "GND"}, pcb=P(cx + 8.4, 2.4, 0),
         sch=at(188, 68, rot=180))
    s.wire("R27.2", "D1.A")
    testpoints(s, ["TP1", "TP2", "TP3", "TP10", "TP11", "TP12", "TP13"],
               "Bring-up test points on the rear face (B.Cu): SWD, RUN, BOOTSEL, its rails, GND (logic only)")
    s.frame("SWD header (J2, 1 × 5 through-hole, fitted by hand): the Debug Probe on 1–3, RUN and VTref for others",
            232, 50, 322, 84)
    part(s, "J2", "hdr5", {str(i + 1): net for i, (net, _) in enumerate(SWD_PINS)}, "SWD", pcb=P(*SWD_HDR, 90),
         sch=at(262, 68))
    s.frame("Bus pull-ups: 10k to 3.3 V always (the LSFs' B side), 2.2k switched by the co-processor "
            "(GPIO10–13, 16–19); the ±5 V rails into the ADC", 124, 102, 228, 144)
    # right of the east face: the 2.2k arrays by the enables (A at the top), the 10k arrays right of them,
    # bus pad to bus pad
    for j in range(2):
        rarray(s, f"RN{8 + j}", "10k", [(f"BUS_{BUSES[i]}", "+3V3") for i in range(4 * j, 4 * j + 4)],
               P(cx + 10.4, cy - 2.8 + 3.0 * j, 0), sch=at(134 + 12 * j, 124))
        rail(s, "+3V3", [f"RN{8 + j}.{k}" for k in (8, 7, 6, 5)], -2)
    for j in range(2):
        rarray(s, f"RN{6 + j}", "2.2k", [(f"CP_PU_{BUSES[i]}", f"BUS_{BUSES[i]}") for i in range(4 * j, 4 * j + 4)],
               P(cx + 7.4, cy - 2.8 + 3.0 * j, 0), sch=at(162 + 12 * j, 124))
    # the ±5 V dividers left of the west face, by GPIO44/45 (pins 55/56).  −5 V's: 10k up to +3V3_CP (the audit's
    # fix 5; 47k before), so GPIO45 stays ≥ −0.48 V (VPIN min −0.5 V) even with −5 V up and +3V3_CP at 0:
    # nominal 3.3 − 8.3 × 10/110 = 2.55 V, ≈ 9 mV of the −5 V rail per LSB
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
    s.notes_at = (6, 124, 112)
    s.notes = ["GPIO2–9 = buses A–H (gusmanb CH1–8, 8-bit mode); GPIO0 → GPIO1 bridged (its trigger path).",
               "GPIO14 = the node's mark (TCA9534A P7); GPIO25 = LED; GPIO19…16, 13…10 = pull-up enables A…H (2.2k);",
               "GPIO40, 43, 42, 41 = VREF 1–4 / 2 (through 100k); GPIO44 = +5V × 47/147;",
               "  GPIO45 = 3.3 V − (3.3 + 5) × 10/110 from −5 V (2.55 V nominal).",
               "RUN pulled up, BOOTSEL (QSPI_SS) through 1k: both held by the node (TCA9534A), open drain.",
               "Core regulator: Raspberry Pi's Minimal R4 block turned 180°; L1's dot (pad 1) on +1V1, not VREG_LX.",
               "C47 (DVDD pin 32, furthest from the regulator) 4.7 µF; no copper under LX / L1 (In1, In2, B.Cu)."]


# ---------------------------------------------------------------------------------------------- the USB pairs
HS_PIN = {1: 1, 2: 3, 3: 6, 4: 8}                     # each port's D− pin, on the hub's south row
HS_BAND = 0.45      # each pair's band: 0.45 mm past its lines' outer edges (3 × their 0.15 mm gap)
# the depth of the 45° bump on each port's D− (hs_lines()): as deep as ports 1–2's drop allows; port 3's 1 mm, under
# SCL's via by U6 (its drop's west side holds SCL's drawn line)
LINK_BUMP = {1: 1.3, 2: 1.3, 3: 1.0, 4: 1.3}


def hs_centrelines():
    """Each hub pair's centreline, corner by corner, from under the hub's south row (hs_pairs()), and the part of it
    its band keeps other tracks off on F.Cu: from 8 mm under the hub (clear of its pins and C15) to its end by its
    USBLC6.  Each comes down 2.65 mm east of its USBLC6's hub pins (ports 1 and 2 past their cluster first, east
    under the next one), turns west 0.8 mm over its axis and ends 1.45 mm east of them, where its lines open out to
    them.  Every turn 45° (ANGLE_RULE).  Ports 1–3 down their header gap 10.1 mm east of the header's centre: 0.75 mm
    off its RESET/BOOT pull-ups; lanes 1 and 2 0.35 mm lower west of port 3's drop (lane 3 gone): 0.75 mm off the
    ESDs' RESET_N and BOOT_N vias above them (the Sensitive class).  {n: (centreline, band)}"""
    def end(n, *down):
        xe = USBS[n - 1] + ESD_DX + 2.6                   # where the lines open out
        return [*down, (xe + 1.2, USB_Y - 0.8), (xe + 0.4, USB_Y), (xe, USB_Y)]

    x1, x2 = (USBS[n - 1] + ESD_DX + 3.8 for n in (1, 2))
    cl = {1: [(84.0, 20.55), (84.0, 35.15), (80.0, 39.15), (67.35, 39.15), (67.0, 39.5), (32.9, 39.5), (32.1, 40.3),
              (32.1, 48.1), (33.8, 49.8),
              *end(1, (33.8, 55.9), (34.6, 56.7), (x1 - 0.8, 56.7), (x1, 57.5))],
          2: [(84.975, 20.55), (84.975, 35.585), (80.41, 40.15), (67.8, 40.15), (67.45, 40.5), (50.9, 40.5),
              (50.1, 41.3), *end(2, (50.1, 56.05), (50.75, 56.7), (x2 - 0.8, 56.7), (x2, 57.5))],
          3: [(86.525, 20.55), (86.525, 35.455), (80.83, 41.15), (68.9, 41.15), (68.1, 41.95), (68.1, 49.7),
              (68.85, 50.45),
              *end(3, (68.85, 50.85), (69.75, 51.75), (69.75, 59.85), (69.3, 60.3))],
          4: [(87.5, 20.55), (87.5, 47.65), (88.9, 49.05), (88.9, USB_Y - 0.8), (88.1, USB_Y), end(4)[-1]]}
    assert abs(cl[3][-4][0] - cl[3][-3][0]) < 1e-9, "USB-C 3's drop (past U6) straight down to its turn"
    return {n: (c, [(c[0][0], HY + 8.0)] + c[1:]) for n, c in cl.items()}


def hs_pairs():
    """The High-Speed pairs on F.Cu over the GND plane, drawn (the HS review, 2026-10-22, the user's rule: "keep
    them over a continuous GND reference, preferably on F.Cu above In1"; Freerouting had put them mostly on B.Cu,
    over the split power plane, each line its own way).  Each port's centreline (hs_centrelines()) from under the
    hub's south row: ports 1–3 down side by side under the hub, west in three lanes over the headers (the band
    their RESET/BOOT columns leave free), each down its header gap's east side to its USBLC6; port 4's down the
    board's east side, past Q1 and Q2.  Each turns west into its USBLC6's hub pins, east of it.  D− and D+ either side
    (offset(), D− on its right-hand side), USB_W lines 0.15 mm apart (≈ 90 Ω: the USB netclass); they leave the
    hub's pins at its 0.5 mm pitch and close up, ports 2 and 3 each 25 µm out from their pins' centre (C15, pin 5's
    100 nF, fits between them), and open out at 45° round pin 5 to the USBLC6's pins 6 and 4, both alike.  No
    length-matching bumps (the layout review: on USB they make it worse) but one: D− ends 0.5–0.7 mm short of D+,
    and the USBLC6's crossover to the receptacle 1 mm more (conn_pairs()), so each link (hub pin to receptacle pin) is
    made up by one 45° bump, LINK_BUMP deep, on D−'s last run down to its USBLC6, 0.12 mm before its end (1.08 mm,
    port 3's 0.83: each link within 1 mm, tools/tests/test_pair_skew.py).  Returns the tracks."""
    return [t for n, (dn, dp, _) in hs_lines().items()
            for t in ((f"PORT{n}_DN", "F.Cu", USB_W, dn), (f"PORT{n}_DP", "F.Cu", USB_W, dp))]


def hs_lines():
    """{n: (D− line, D+ line, D−'s bump: its four corners)} for hs_pairs()."""
    out = {}
    hp = (USB_W + 0.15) / 2
    for n, (c, _) in hs_centrelines().items():
        px = HX - 3.5 + 0.5 * (HS_PIN[n] - 1)                       # its two pins' centre
        ex, xe = USBS[n - 1] + ESD_DX, c[-1][0]
        p6, p4 = (ex + 1.1375, USB_Y - 0.95), (ex + 1.1375, USB_Y + 0.95)  # its USBLC6's pins 6 (D−), 4 (D+)
        dn = [(px - 0.25, HY + 4.4125), (px - 0.25, HY + 4.9)] + offset(c, hp) + [(xe - 0.95 + hp, p6[1]), p6]
        dp = [(px + 0.25, HY + 4.4125), (px + 0.25, HY + 4.9)] + offset(c, -hp) + [(xe - 0.95 + hp, p4[1]), p4]
        # no point within 0.1 mm of the last one kept (a sliver otherwise)
        dn, dp = ([q for i, q in enumerate(pts) if i in (0, len(pts) - 1) or math.dist(q, pts[i - 1]) >= 0.1]
                  for pts in (dn, dp))
        k = max(i for i in range(len(dn) - 1) if abs(dn[i][0] - dn[i + 1][0]) < 1e-6        # D−'s last run down
                and abs(dn[i][1] - dn[i + 1][1]) > 2 * LINK_BUMP[n] + 0.35)
        dn = bumps(dn, k, 1, LINK_BUMP[n], tail=0.12)
        out[n] = (dn, dp, dn[k + 1:k + 5])
    return out


def conn_pairs():
    """Each USBLC6's pair on to its receptacle, drawn: the DATA ×6's cell turned east to west, D+ and D− swapped.
    The receptacles stand, their B column (B1 … B12, north to south) facing the USBLC6 east of them, B6 (D+) north of
    B7 (D−); the USBLC6 keeps its lines' order, pin 1 (D−) north of pin 3 (D+).  So one line crosses under the other,
    and the receptacle's own crossover (D+ on A6 and B6, D− on A7 and B7, one column turned against the other) takes
    no more vias:
    * D− on F.Cu, no via: west, down 1.2 mm past the USBLC6's GND via, into B7, then diagonally between the two
      columns to A7;
    * D+ down to B.Cu by its pin, under D−, up north of D−'s line by B6 and into it; on from that via on B.Cu, under
      the B column, to a via between the columns, up into A6.
    Also drawn: each USBLC6's GND pin to its via, its VBUS (pin 5, which its hub pair walls in) under the body and
    up between its pin rows into its 100 nF (C104–C404), then on to its via in the +5V area, and VBUS across the
    columns, A9 to B4 and A4 to B9.  Returns (tracks, vias)."""
    tracks, vias = [], []
    for n, cx in enumerate(USBS, 1):
        p = f"PORT{n}_"
        ex, ey = cx + ESD_DX, USB_Y

        def c(dx, dy):
            return cx + dx, USB_Y + dy
        a9, a7, a6, a4 = (c(-USBC_COL, d) for d in (-1.25, -0.25, 0.25, 1.25))
        b4, b6, b7, b9 = (c(USBC_COL, d) for d in (-1.25, -0.25, 0.25, 1.25))
        e1, e2, e3 = ((ex - 1.1375, ey + d) for d in (-0.95, 0.0, 0.95))         # pins 1 (D−), 2 (GND), 3 (D+)
        # the USBLC6 5.55 mm off its receptacle: its GND via under its body (south of the +5V line from its pin 5),
        # out of the way of D−'s diagonal, which starts at cx + 3.8, clear of D+'s via by B6
        gv = (ex, ey + 0.55)
        v1, vn, vs = (ex - 2.15, e3[1]), c(2.35, -0.3), c(0.0, 0.6)          # D+'s vias: by its pin, by B6, between
        # D+ (longer: the crossing) through its via by B6 within 45° either way, the shortest such way; D− 0.25 mm north
        # off pin 1 first (0.2 mm longer): the two within 1 mm (test_pair_skew)
        tracks += [(p + "CONN_DN", "F.Cu", USB_W, [e1, c(4.1625, -1.2), c(4.05, -1.2), c(2.6, 0.25), b7]),
                   (p + "CONN_DN", "F.Cu", USB_W, [b7, c(0.4, 0.25), c(-0.4, -0.25), a7]),
                   (p + "CONN_DP", "F.Cu", USB_W, [e3, v1]),
                   (p + "CONN_DP", "B.Cu", USB_W, [v1, c(3.4, 0.66), c(2.5, -0.24), vn, vs]),
                   (p + "CONN_DP", "F.Cu", USB_W, [vn, b6]),
                   (p + "CONN_DP", "F.Cu", USB_W, [vs, c(-0.4, 0.25), a6]),
                   ("GND", "F.Cu", 0.25, [e2, gv]),
                   ("+5V", "F.Cu", 0.25, [(ex + 1.1375, ey), (ex, ey), (ex, ey - 2.9)]),
                   (p + "VBUS", "F.Cu", 0.3, [a9, b4]), (p + "VBUS", "F.Cu", 0.3, [a4, b9])]
        vias += [(p + "CONN_DP", *v, 0.5, 0.3) for v in (v1, vn, vs)] + [("GND", *gv, 0.5, 0.3),
                                                                          ("+5V", ex, ey - 2.9, 0.5, 0.3)]
        # and the two VBUS crossings joined under the A column on B.Cu, clear of D+'s way to its via between the
        # columns (the DATA ×6's, mirrored): CC1 / CC2 leave the columns' outer ends free
        vbn, vbs = c(0.0, -1.25), c(-0.6, 1.25)
        tracks.append((p + "VBUS", "B.Cu", 0.3, [vbn, c(-0.9, -0.35), c(-0.9, 0.95), vbs]))
        vias += [(p + "VBUS", *v, 0.6, 0.3) for v in (vbn, vbs)]
    return tracks, vias


# ---------------------------------------------------------------------------------------------- board
def logic_only(b: Board) -> list[str]:
    """The parts the base DATA-4x leaves off: the matrix and co-processor sheets whole, and per port its pin
    chain (the three H5VU25UC on P1–P8 and VREF, the 100 Ω arrays, the LSF0108, its Vref_B 200k and 100 nF, the
    VREF divider and its 100k to the ADC).  The RESET/BOOT ESD stays."""
    refs = [p.ref for p in b.parts.values() if p.sheet and p.sheet.name in ("Matrix", "Co-processor")]
    for n in range(1, 5):
        k = 100 * n
        refs += [f"U{k + 5}", f"U{k + 6}", f"RN{k + 1}", f"RN{k + 2}", f"U{k + 7}", f"R{k + 11}", f"C{k + 5}",
                 f"R{k + 12}", f"R{k + 13}", f"U{k + 8}", f"R{k + 15}"]
    return sorted(r for r in refs if r in b.parts and b.parts[r].in_bom and not r.startswith("#"))


def board() -> Board:
    b = Board("data-port-x4", "DATA ×4 v2", "1.0",
              comments=["A converted bay's drawer board: four USB-C behind a hub, 32 switchable pins on 8 buses, "
                        "a logic analyzer (hw-testing-rack)",
                        "Generated from electronics/data-port-x4/design.py — edit the Python, then regenerate"])
    b.root_paper, b.root_buses = "A2", True
    b.root_notes = [
        "DATA ×4 v1.0 — USB2517I hub (7 ports), four USB-C (sub-slots A1.1–A1.4) each with a TPS2553-1, an INA226",
        "  and ESD, two TCA6408A for EN/FAULT/RESET/BOOT, an LMR51635 5 V from the lead's 20 V, an AP2114H 3.3 V;",
        "  the PH 8 lead from the node's J7.",
        "Pins: 32 on two CH446Q (±5 V), LSF0108 per port, an RP2350B analyzer on hub port 5, a TCA9534A for",
        "  the matrix and the co-processor's RUN/BOOTSEL.  Standing behind the port wall, one face assembled;",
        "  v1 stays the other bays' board.",
        "Lead pinout here: 1 NC · 2 SCL · 3 SDA · 4 GND · 5 D− · 6 D+ · 7 GND · 8 VIN — the DATA ×6's lead.",
        "Rails: VIN 20 V (on above 13.5 V typ., 15.1 V at worst; ≤ 28 V), ≤ 0.92 A at 20 V (1.22 A at 15 V) ·",
        "  +5V 5.08 V (4.94–5.22 V), ≤ 3.09 A (the",
        "  ports at their 0.644 A limit + 0.51 A; the LMR51635's 3.5 A) ·",
        "  PORTn_VBUS 4.82–5.22 V, 0.52–0.64 A limit · +3V3 3.3 V (AP2114H), ≤ 0.51 A · +5V_MX, −5V (sheet Matrix) ·",
        "  +3V3_CP, +1V1 (sheet Co-processor) · HUB_1V8 / HUB_1V8PLL 1.8 V (the hub's own regulators).",
        "I²C: TCA6408A 0x20 / 0x21, INA226 0x41 / 0x43 / 0x44 / 0x45, TCA9534A 0x38; the node's INA226 0x40.",
        "Assembled as DATA-4x-logic (as drawn) or DATA-4x (BOM/CPL '-base': the matrix, the co-processor and the",
        "  ports' pin chains not fitted).",
    ]
    hub_sheet(b)
    power_sheet(b)
    for n in range(1, 5):
        port(b, n)
    matrix_sheet(b)
    coproc_sheet(b)

    # the cradle's T-heads come up through two notches in the bottom edge (rounded inner corners: the mill)
    outline = [(0, 0, 1.0), (W, 0, 1.0), (W, H, 1.0)]
    for x0, x1, top in reversed(NOTCHES):
        outline += [(x1, H, 0), (x1, top, 0.5), (x0, top, 0.5), (x0, H, 0)]
    outline += [(0, H, 1.0)]
    # The power plane (In2 on 4 layers, In4 on 6): +3V3 above PWR_SPLIT (the chains, the crosspoints, the
    # co-processor, the hub, the expanders' and INA226s' side), +5V below it (the power clusters, the USB-C's
    # ESD), 0.2 mm apart.  The few +5V_MX pins above the split (the crosspoints' VDD, the −5 V inverter, the
    # LSF0108s' bias, the co-processor's sense divider) are routed.  The co-processor's +3V3_CP island under its
    # package is poured after the routing and joins the +3V3_CP vias that land in it.  The 5 V converter stands on
    # a tongue of its own output in the top-left corner (TA × TB), and the tongue runs down the cradle's band
    # (nothing else uses it, either face) to the +5V area, as the DATA ×6's converter A.
    # Both held 1.4 mm from the edge, notches included, 1 mm further than the other copper (the RF review,
    # 2026-10-21): with the edge fence (below) the GND plane and the outer pours close the cavity's edge
    E = 1.4
    IN_3V3 = [(TA + 0.2, E), (W - E, E), (W - E, PWR_SPLIT - 0.1), (5.6, PWR_SPLIT - 0.1), (5.6, TB + 0.2),
              (TA + 0.2, TB + 0.2)]
    bottom = [pt for x0, x1, top in reversed(NOTCHES)
              for pt in ((x1 + E, H - E), (x1 + E, top - E), (x0 - E, top - E), (x0 - E, H - E))]
    IN_5V = [(E, E), (TA, E), (TA, TB), (5.4, TB), (5.4, PWR_SPLIT + 0.1), (W - E, PWR_SPLIT + 0.1),
             (W - E, H - E), *bottom, (E, H - E)]
    # the co-processor's +3V3_CP island: U11 and its 100 nF ring west, north and south, so that each capacitor's
    # via, past its +3V3_CP pad, lands in it (no +3V3 or +5V via in the ring)
    ISLAND = [(CP[0] - 6.65, CP[1] - 8.15), (CP[0] + 6.1, CP[1] - 8.15), (CP[0] + 6.1, CP[1] + 8.1),
              (CP[0] - 6.65, CP[1] + 8.1)]
    # Drawn before the routing (Freerouting routes round them): each port switch's IN and its 1 µF over the
    # +3V3 area, by a 0.6 mm track down past the INA226 to a via into the +5V area
    hand_tracks, hand_vias = [], []
    for n, x0 in enumerate(CLX, 1):
        y0 = PWR_Y
        pin_in = (x0 + 2.45 + 1.1375, y0 + 2.2 + 0.95)        # the switch's IN (pin 1, turned 180°): its centre
        c1 = (x0 + 5.13, y0 + 2.9 + 0.48)                     # its 1 µF's +5V pad
        x5 = c1[0] + 0.5                                       # right of the shunt's VBUS pad, left of the INA226
        # its via into the +5V area 2.5 mm off its USB-C's axis, clear of the GCT's north stakes and post: USB-C 1's
        # straight down, 3's and 4's by a diagonal under the INA226, 2's along the split band, over its shunt's pad
        cx = USBS[n - 1]
        vx = (cx - 2.5 if x5 < cx else cx + 2.5) if abs(x5 - cx) < 2.5 else x5
        via, d = (vx, PWR_SPLIT + 1.1), abs(vx - x5)
        s = 1 if vx > x5 else -1
        if d <= 0.3:
            path = [(vx, c1[1] + 0.5), via]
        elif d <= 1.2:
            path = [(x5, c1[1] + 0.5), (x5, via[1] - d), via]
        else:
            path = [(x5, c1[1] + 0.5), (x5, PWR_SPLIT + 0.2), (x5 + 0.3 * s, PWR_SPLIT + 0.5),
                    (vx - 0.3 * s, PWR_SPLIT + 0.5), (vx, PWR_SPLIT + 0.8), via]
        hand_tracks.append(("+5V", "F.Cu", 0.6, [pin_in, c1, *path]))
        hand_vias.append(("+5V", *via, 0.6, 0.3))
        # the INA226's VS (pin 6, turned 90°) straight up to its 100 nF (C103-C403), then its via: the pin → cap →
        # via order.  The via north of it on ports 1 and 3, east of it on 2 and 4, where the port's EN line (and
        # SDA, on 4) passes north
        vs = (x0 + 8.51, y0 + 2.45)
        via = (vs[0], y0 + 0.15) if n % 2 else (vs[0] + 0.63, y0 + 0.9)
        hand_tracks.append(("+3V3", "F.Cu", 0.25, [vs, (vs[0], y0 + 0.9), via]))
        hand_vias.append(("+3V3", *via, 0.5, 0.3))
    # U3's islands' vias: six from the tab's +3V3 island into the +3V3 plane, either side of the tab; two from
    # the VIN island into the +5V plane, between the VIN pin and C2
    lx, ly = LDO
    hand_vias += [("+3V3", x, y, 0.5, 0.3) for x in (lx - 3.05, lx + 3.05) for y in (ly - 5.1, ly - 3.5, ly - 1.9)]
    # three more through the island's west part, which a B.Cu +3V3 area doubles (LDO_WEST): over the In2 +5V band's
    # edge there, they tie the two faces' copper only.  No more further west: two columns at x 2.5 and 3.85 left the
    # band 1.3 mm of copper across, under all of the +5V's 3.09 A (2026-11-02)
    hand_vias += [("+3V3", 5.2, y, 0.5, 0.3) for y in (ly - 5.1, ly - 3.5, ly - 1.9)]
    hand_vias += [("+5V", lx + dx, ly + 4.8, 0.6, 0.3) for dx in (1.9, 3.15)]
    buck_zones, v = buck_copper("BUCK_SW", "+5V", *BUCK, "buck")
    hand_vias += v
    # The links only the pours used to make, drawn: with one open Freerouting skips its optimizer, and its routes
    # stay as first found (micro-jogs leaving the pads, the user's find, 2026-10-22).  A drawn track joins its pad
    # for Freerouting only on the pad's very centre (2.5 µm off, the HS pairs and the switches' IN stayed open):
    # every drawn end lands on its pad's centre.  U3's tab to C3 and to an island via, its VIN to a +5V via and the
    # other one to C2 (inside the islands' cores: pcbgen drops the cores once routed); the expanders' and
    # LSF0108s' exposed pads to a via in the pad (from 6 layers JLC fills and caps every via for free); the hub's,
    # 4.7 mm, to nine (3 × 3 at 1.2 mm, its paste cut between them: bench:…_Paste4x4), the hub's heat and its
    # GND return into In1; the hub's GND pin 19, which has no room for a via, onto its exposed pad; RN3's spare GND pad onto its neighbour, whose
    # dog-bone is drawn with it (a pad a drawn track reaches gets no automatic one)
    hand_tracks += [("+3V3", "F.Cu", 0.6, [(lx, ly - 5.35), (lx, ly - 3.5), (lx + 3.05, ly - 3.5)]),
                    ("+5V", "F.Cu", 0.6, [(lx + 2.3, ly + 3.15), (lx + 1.9, ly + 4.8)]),
                    ("+5V", "F.Cu", 0.6, [(lx + 3.15, ly + 4.8), (lx + 2.9, ly + 5.95)])]
    # the charge pump's OUT and IN (U9's pins 1, 2) straight west to C28 and C27
    hand_tracks += [("-5V", "F.Cu", 0.25, [(8.8625, 23.05), (7.43, 23.0)]),
                    ("+5V_MX", "F.Cu", 0.25, [(8.8625, 24.0), (7.43, 24.05)])]
    # and OUT along U9's north side to where its −5 V line splits, as the router had it (to the crosspoints east
    # and TP4 north; the router, left to it, joined neither once C28 had moved)
    hand_tracks.append(("-5V", "F.Cu", 0.25, [(8.8625, 23.05), (9.41, 22.502), (11.841, 22.502)]))
    # C22 (the left crosspoint's VEE 100 nF, U7 pin 16) in the pin → cap → via order: the pin down to C22, C22 on
    # east to a via, and B.Cu from there up to where the −5 V runs to U8 and R41 meet (they left from the pin, by a
    # via there)
    cx7, cy7 = CHIP[0]
    vee = (cx7 - 0.1, cy7 + 7.27)                                       # C22's via
    meet = (31.2027, 22.8324)                                           # the B.Cu runs' junction, as routed
    hand_tracks += [("-5V", "F.Cu", 0.25, [(cx7 - 0.8, cy7 + 5.6625), (cx7 - 0.8, vee[1]), vee]),
                    ("-5V", "B.Cu", 0.25, [vee, (vee[0], meet[1] + meet[0] - vee[0]), meet])]
    hand_vias.append(("-5V", *vee, 0.5, 0.3))
    # each port's USBLC6 and its receptacle: conn_pairs()
    t, v = conn_pairs()
    hand_tracks += t
    hand_vias += v
    # the via under each port's VBUS test pad (TPS), on the router's VBUS line
    hand_vias += [(f"PORT{n}_VBUS", *VBUS_TP[n], 0.6, 0.3) for n in range(1, 5)]
    # and the stitching's gaps filled (GND_FILL)
    hand_vias += [("GND", x, y, 0.6, 0.3) for x, y in GND_FILL]
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
    v37 = (40.7998, 17.3915)                                            # its via, as routed (its B.Cu run to R21)
    hand_tracks += [("+3V3_CP", "F.Cu", 0.25, [(CP[0] - 4.95, CP[1] + 3.4), (CP[0] - 4.95, CP[1] + 3.8)]),
                    ("+3V3_CP", "F.Cu", 0.25, [(CP[0] - 4.95, c37[1]), c37, (40.3442, 16.9358), v37])]
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
    hand_tracks += [("CP_DP", "F.Cu", 0.15, [(CP[0] - 1.4, CP[1] + 4.95), (CP[0] - 1.4, CP[1] + 4.42),
                                             (CP[0] - 1.3, CP[1] + 4.32), (CP[0] - 0.12, CP[1] + 4.32),
                                             (CP[0] + 0.1, CP[1] + 4.1)]),
                    ("CP_DP", "B.Cu", 0.25, [(CP[0] + 0.1, CP[1] + 4.1), (CP[0] + 0.1, CP[1] + 5.7), (48.379, 19.879),
                                             (48.379, 22.134)]),
                    ("CP_DP", "F.Cu", 0.25, [(48.379, 22.134), (48.744, 22.134), (49.4, 22.79)])]
    hand_vias += [("CP_DP", CP[0] + 0.1, CP[1] + 4.1, 0.5, 0.3), ("CP_DP", 48.379, 22.134, 0.5, 0.3)]
    # the co-processor's west face round C45 (DVDD pin 51's 100 nF, right west of it): pin 51 to C45, C45's GND
    # down to its via; VREF4 (pin 52) and VREF2 (pin 54) to B.Cu right by their pins, 4's via east, 2's west (their
    # GPIOs swapped so that the two runs south do not cross); BUS_C's dive to B.Cu moved west of C45.  Pin 51 keeps
    # its own via under the case into the +1V1 network: no room for one after C45 (between C36's +3V3_CP line north
    # and the VREF vias south), so C45 is the order rule's one exception (pin → via before the capacitor)
    ux, uy = CP[0] - 4.95, CP[1]                                       # U11's west pad column
    hand_tracks += [("+1V1", "F.Cu", 0.2, [(ux, uy + 0.2), (CP[0] - 6.14, uy + 0.2)]),
                    ("GND", "F.Cu", 0.25, [(CP[0] - 7.1, uy + 0.2), (CP[0] - 7.1, uy + 0.85)]),
                    ("CP_ADC4", "F.Cu", 0.127, [(ux, uy + 0.6), (ux - 0.55, uy + 0.6), (ux - 0.8, uy + 0.85)]),
                    ("CP_ADC2", "F.Cu", 0.127, [(ux, uy + 1.4), (ux - 1.13, uy + 1.4), (ux - 1.35, uy + 1.18)]),
                    ("BUS_C", "F.Cu", 0.127, [(39.031, 12.252), (39.031, 12.68), (39.2, 12.85)]),
                    ("BUS_C", "B.Cu", 0.127, [(39.2, 12.85), (39.395, 12.655), (40.603, 12.655)]),
                    # and R39's GND via where its fan-out had it (BUS_C's via now pushes the automatic one onto
                    # CP_SNS_5V)
                    ("GND", "F.Cu", 0.25, [(38.31, 13.4), (38.93, 13.4)])]
    hand_vias += [("GND", CP[0] - 7.1, uy + 0.85, 0.5, 0.3), ("CP_ADC4", ux - 0.8, uy + 0.85, 0.5, 0.3),
                  ("CP_ADC2", ux - 1.35, uy + 1.18, 0.5, 0.3), ("BUS_C", 39.2, 12.85, 0.5, 0.3),
                  ("GND", 38.93, 13.4, 0.5, 0.3)]
    # the hub's reset supervisor in the pin → cap → via order: VCC (U5 pin 3) straight up to C6, C6 on east to
    # its via
    hand_tracks.append(("+3V3", "F.Cu", 0.25, [(HX - 2.2, HY - 11.038), (HX - 2.2, HY - 12.7), (HX - 1.5, HY - 12.7)]))
    hand_vias.append(("+3V3", HX - 1.5, HY - 12.7, 0.5, 0.3))
    # the matrix expander's VDD (U10 pin 16) to C29, then its via
    mx, my = MX_EXP
    hand_tracks.append(("+3V3", "F.Cu", 0.25, [(mx - 2.275, my - 2.8625), (mx - 2.9575, my - 2.18),
                                               (mx - 3.45, my - 2.18), (mx - 4.1, my - 2.18)]))
    hand_vias.append(("+3V3", mx - 4.1, my - 2.18, 0.5, 0.3))
    # C18, C19 (the expanders' 100 nF), in the pin → cap → via order: VCCP (pin 14) bridged to VCCI (pin 15),
    # VCCI straight up to the capacitor, the capacitor on to its via west of it; its GND pad's via east of it (the
    # automatic one went up onto PORT1_RST_IO's via)
    for ux, uy, _ in EXP:
        hand_tracks += [("+3V3", "F.Cu", 0.25, [(ux + 0.25, uy - 1.4375), (ux - 0.25, uy - 1.4375),
                                                (ux - 0.25, uy - 2.77), (ux - 0.85, uy - 3.25)]),
                        ("GND", "F.Cu", 0.25, [(ux - 0.25, uy - 3.73), (ux + 0.4, uy - 3.73)])]
        hand_vias += [("+3V3", ux - 0.85, uy - 3.25, 0.5, 0.3), ("GND", ux + 0.4, uy - 3.73, 0.5, 0.3)]
    for x_, y_ in [(ex_, ey_) for ex_, ey_, _ in EXP] + [(c - 0.5, LSF_Y) for c in HDRS]:
        hand_tracks.append(("GND", "F.Cu", 0.25, [(x_, y_), (x_ + 0.3, y_)]))
        hand_vias.append(("GND", x_ + 0.3, y_, 0.5, 0.3))
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
    # CP_RUN, from the matrix expander's P5 (pin 10, its north row) to the co-processor's RUN pull-up R25: north
    # between its pins and the converter's 22 µF, east past the converter's tongue (no rear track crosses its edge),
    # up on F.Cu, then along the top edge on B.Cu above the co-processor's test points (Freerouting left it open)
    rx, ry = MX_EXP[0] + 2.5 * 0.65, MX_EXP[1] - 2.8625                # U10 pin 10, turned 90°
    r25 = (CP[0] - 3.8 + 0.51, 5.4)                                     # R25's CP_RUN pad
    run_y = 1.85                                                        # SWDIO's line to J2 runs 0.6 under it
    ux = TA + 1.0                                                       # its way up, east of the tongue's edge
    hand_tracks += [("CP_RUN", "F.Cu", 0.127, [(rx, ry), (rx, TB + 0.75), (ux, TB + 0.75), (ux, 2.4)]),
                    ("CP_RUN", "B.Cu", 0.127, [(ux, 2.4), (ux + 2.4 - run_y, run_y), (r25[0], run_y)]),
                    ("CP_RUN", "F.Cu", 0.127, [(r25[0], run_y), r25])]
    hand_vias += [("CP_RUN", ux, 2.4, 0.5, 0.3), ("CP_RUN", r25[0], run_y, 0.5, 0.3)]
    # the two test points Freerouting left open (TPS): RUN up onto that track, +3V3_CP through a via to FB2's
    # output pad
    tp12, tp10, fb2 = TPS["TP12"][3:], TPS["TP10"][3:], (CP[0] - 8.5 + 1.0625, 4.6)
    hand_tracks += [("CP_RUN", "B.Cu", 0.127, [tp12, (tp12[0], run_y)]),
                    ("+3V3_CP", "B.Cu", 0.25, [tp10, (38.8, 3.8), (38.8, 4.55)]),
                    ("+3V3_CP", "F.Cu", 0.25, [(38.8, 4.55), (fb2[0], 4.55)])]            # into its pad, level
    hand_vias.append(("+3V3_CP", 38.8, 4.55, 0.5, 0.3))
    # J2's SWDIO (Freerouting left it open): on the rear face between RUN's and SWCLK's lines to the header (gaps
    # too narrow for a GND sliver), then up through a via onto the co-processor's SWDIO track to TP2
    j2_dio = (SWD_HDR[0] + 2 * 2.54, SWD_HDR[1])
    hand_tracks += [("CP_SWDIO", "B.Cu", 0.127, [j2_dio, (j2_dio[0] - 1.55, 2.45), (44.6, 2.45)]),
                    ("CP_SWDIO", "F.Cu", 0.127, [(44.6, 2.45), (44.106, 2.45)])]
    hand_vias.append(("CP_SWDIO", 44.6, 2.45, 0.5, 0.3))
    # and its SWCLK (left open too): under SWDIO's line (y 2.95 keeps the crystal's and C43's GND fan-outs where they
    # were), then up through a via onto SWCLK's node beside R25
    hand_tracks.append(("CP_SWCLK", "B.Cu", 0.127,
                        [SWD_HDR, (SWD_HDR[0] - 1.05, 2.95), (44.799, 2.95), (43.226, 4.523)]))
    hand_vias.append(("CP_SWCLK", 43.226, 4.523, 0.5, 0.3))
    # and its RUN: CP_RUN's line along the top edge carried on east, straight down to pin 4
    j2_run = (SWD_HDR[0] + 3 * 2.54, SWD_HDR[1])
    hand_tracks.append(("CP_RUN", "B.Cu", 0.127, [(r25[0], run_y), (j2_run[0] - (j2_run[1] - run_y), run_y), j2_run]))
    # D1's GND fan-out drawn straight down from its cathode, clear of the SWD lines over and under it
    d1k = (CP[0] + 8.4 - 0.9375, 2.4)
    hand_tracks.append(("GND", "F.Cu", 0.25, [d1k, (d1k[0], 3.8)]))
    hand_vias.append(("GND", d1k[0], 3.8, 0.5, 0.3))
    for n in range(1, 5):                               # the 32 P lines, locked (p_lines())
        t, v = p_lines(n)
        hand_tracks += t
        hand_vias += v
    # the bus test pads' two drawn links (TPS): H, front only, down a via beside its track; the GND pad to a via
    # of its own east of it (the automatic one went west and pushed RN8's +3V3 dog-bones about)
    (hx, hy), (gx, gy) = TPS["TP36"][3:], TPS["TP37"][3:]
    hand_tracks += [("BUS_H", "B.Cu", 0.127, [(hx + 0.48, 17.13), (hx + 0.48, hy - 0.48), (hx, hy)]),
                    ("GND", "B.Cu", 0.25, [(gx, gy), (gx + 1.0, gy)])]
    hand_vias += [("BUS_H", hx + 0.48, 17.13, 0.5, 0.3), ("GND", gx + 1.0, gy, 0.5, 0.3)]
    # RN8's pin 5 (+3V3) on pin 6's via, with no via of its own: the only way out for BUS_D from its pull-ups (RN6,
    # RN8 pin 4) to its line east of the arrays runs between RN8's two columns, under pin 5
    rx, ry = CP[0] + 10.4, CP[1] - 2.8
    hand_tracks.append(("+3V3", "F.Cu", 0.25, [(rx + 0.5, ry + 0.75), (rx + 0.5, ry + 0.25), (rx + 1.1, ry + 0.25)]))
    hand_vias.append(("+3V3", rx + 1.1, ry + 0.25, 0.5, 0.3))
    # C27 and C28's GND vias right west of their pads: the fan-out put them 0.6 mm further, past the decoupling rule's
    # 1 mm (electronics/tools/decoupling.py)
    for y in (23.0, 24.05):
        hand_tracks.append(("GND", "F.Cu", 0.25, [(6.47, y), (5.84, y)]))
        hand_vias.append(("GND", 5.84, y, 0.5, 0.3))
    # ports 1 and 4's 5V_SW, from the switch up to the VBUS LED's resistor, drawn: their old way past the header
    # (B.Cu between two of its pins) now carries P6 / P5.  Port 1 crosses the header on F.Cu west of pin 4; port 4,
    # under three USB pairs there, on B.Cu west of the header.  Their cluster end relative to the cluster's x0, their
    # header end to the header's x, a B.Cu diagonal between (the clusters left the headers' x, layout B)
    for n, x0 in ((1, CLX[0]), (4, CLX[3])):
        hx = HDRS[n - 1]
        if n == 1:
            v1, v2 = (x0 + 0.65, 52.4), (hx - 4.35, 46.39)
            runs = [("F.Cu", [(x0 + 1.3075, 53.8), (x0 + 1.3075, 52.4), v1]),
                    ("F.Cu", [v1, (x0 + 1.3125, 51.7375), (x0 + 1.3125, 51.55)]),
                    ("B.Cu", [v1, (v1[0], v2[1] + v1[0] - v2[0]), v2]),
                    ("F.Cu", [v2, (hx - 4.95, 45.79), (hx - 4.95, 39.54), (hx - 4.2, 38.79), (hx - 4.2, 34.69),
                              (hx - 5.2, 33.69)])]
        else:
            v1, v2 = (x0 + 0.243, 50.948), (hx - 5.85, 34.34)
            runs = [("F.Cu", [(x0 + 1.3075, 53.8), (x0 + 1.3075, 51.55)]),
                    ("F.Cu", [(x0 + 1.3125, 51.55), (x0 + 0.845, 51.55), v1]),
                    ("B.Cu", [v1, (v1[0], 46.59 + v1[0] - (hx - 7.5)), (hx - 7.5, 46.59), (hx - 7.5, 35.99), v2]),
                    ("F.Cu", [v2, (hx - 5.2, 33.69)])]
        hand_tracks += [(f"PORT{n}_5V_SW", layer, 0.3, pts) for layer, pts in runs]
        hand_vias += [(f"PORT{n}_5V_SW", *v, 0.5, 0.3) for v in (v1, v2)]
    # and the crystal's and C43's GND fan-outs kept where the routing expects them (the auto fan-out moves them
    # once the SWD lines pass under the crystal)
    y2g, c43g = (CP[0] + 1.3 + 1.1, 3.05), (CP[0] + 3.0, 5.02)
    hand_tracks += [("GND", "F.Cu", 0.25, [y2g, (50.533, 3.519)]), ("GND", "F.Cu", 0.25, [c43g, (c43g[0], 4.39)])]
    hand_vias += [("GND", 50.533, 3.519, 0.5, 0.3), ("GND", c43g[0], 4.39, 0.5, 0.3)]
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
    # and the exposed pad down to the GND plane: vias between its paste windows, drawn (Freerouting doesn't
    # always fan the pad out).  Three of the four crossings (the PCB review's X4B-03, 2026-11-09: the pad is the
    # chip's only ground but VREG_PGND, and one via left it no spare): the south-east one it had, and the two
    # west ones, which stand between the buses that pass under the pad on B.Cu (BUS_B 0.31 mm from the north one,
    # BUS_A 0.108 mm from the south one, for the board's 0.1 mm).  BUS_B runs through the north-east crossing
    hand_vias += [("GND", ux + 0.565, uy + 0.565, 0.5, 0.3), ("GND", ux - 0.565, uy - 0.565, 0.5, 0.3),
                  ("GND", ux - 0.565, uy + 0.565, 0.5, 0.3)]
    # the hub's pairs on F.Cu (hs_pairs())
    hand_tracks += hs_pairs()
    # Port 3's pair comes down just east of U6, whose east pins (SCL, port 4's RST_IO and BOOT_IO; INT unconnected) leave
    # that way: the pair keeps clear of R401 above, then steps 1.7 mm east, so the gap holds two tracks.  RST_IO
    # (pin 10, boxed in between INT and BOOT_IO) is drawn: down the gap's west side to a via south of the package.
    # U2's likewise.  U6's SCL (pin 12) is drawn too, down the gap's east side to the SCL trunk's rear run under it:
    # its only other way out, a via off the pin's corner, is walled in on B.Cu by SDA and port 4's EN
    for ex_, ey_, _ in EXP:
        net = f"PORT{2 if ex_ < 50 else 4}_RST_IO"
        hand_tracks.append((net, "F.Cu", 0.127, [(ex_ + 1.4375, ey_ + 0.25), (ex_ + 2.05, ey_ + 0.25),
                                                 (ex_ + 2.05, ey_ + 1.5), (ex_ + 2.25, ey_ + 1.7)]))
        hand_vias.append((net, ex_ + 2.25, ey_ + 1.7, 0.5, 0.3))
    ex_, ey_, _ = EXP[1]
    scl = [(ex_ + 1.4375, ey_ - 0.75), (ex_ + 2.3, ey_ - 0.75), (ex_ + 2.3, ey_ + 0.9), (ex_ + 2.8, ey_ + 1.4),
           (ex_ + 2.8, 57.07)]
    hand_tracks.append(("SCL", "F.Cu", 0.127, scl))
    hand_vias.append(("SCL", *scl[-1], 0.5, 0.3))
    # The upstream pair (the RF review, 2026-10-21; on F.Cu since the HS review): its pins sit between the hub's
    # straps and its crystal, and the downstream pairs wall J1 off on F.Cu, so it dives under the hub's body to
    # B.Cu (between its exposed pad, left free for vias, and its south pins; ≈ 11 mm over the +3V3 plane, among
    # the hub's decoupling), comes up past its east side and runs down the board's east side on F.Cu to J1's
    # pins 6 (D+, the upper since J1 stands as the DATA ×6's) and 5 (D−), from the east.  D+ the inner line of
    # both its turns: it comes up first, west of D− (D− runs on to its via east of it).  D− goes 2 mm further, to
    # pin 5, and round the outside: a High-Speed pair, so D+ makes it up (within 1 mm: tools/tests/test_pair_skew.py)
    # by 45° bumps, three west of its run down the east side, as deep as RN3 leaves room for, two north of its run
    # into pin 6 for the rest
    jx, j5, j6 = LEAD[0], LEAD[1] - 8.0, LEAD[1] - 10.0
    up_dn_b = [(HX - 2.75, HY + 0.6), (HX - 2.75, HY + 2.15), (HX - 2.3, HY + 2.6), (HX + 7.35, HY + 2.6)]
    up_dp_b = [(HX - 3.3, HY + 1.4), (HX - 3.3, HY + 2.55), (HX - 2.85, HY + 3.0), (HX + 6.15, HY + 3.0),
               (HX + 6.55, HY + 3.4)]
    up_dn_f = [up_dn_b[-1], (HX + 7.35, HY + 3.9), (HX + 7.15, HY + 4.1), (HX + 7.15, j5 - 0.5), (HX + 6.65, j5),
               (jx, j5)]
    up_dp_f = [up_dp_b[-1], (HX + 6.75, HY + 3.6), (HX + 6.75, j6 - 0.5), (HX + 6.25, j6), (jx, j6)]
    up_dn_esc = [(HX - 4.4125, HY + 0.75), up_dn_b[0]]
    up_dp_esc = [(HX - 4.4125, HY + 1.25), up_dp_b[0]]
    gap = plen(up_dn_esc) + plen(up_dn_b) + plen(up_dn_f) - plen(up_dp_esc) - plen(up_dp_b) - plen(up_dp_f)
    k = 2 * math.sqrt(2) - 2
    hh = (gap - 3 * k * 1.4) / (2 * k)
    assert 0 < hh <= 0.6, hh
    up_dp_f = bumps(bumps(up_dp_f, 3, 2, hh), 1, 3, 1.4)
    hand_tracks += [("UP_DN", "F.Cu", USB_W, up_dn_esc), ("UP_DN", "B.Cu", USB_W, up_dn_b),
                    ("UP_DN", "F.Cu", USB_W, up_dn_f), ("UP_DP", "F.Cu", USB_W, up_dp_esc),
                    ("UP_DP", "B.Cu", USB_W, up_dp_b), ("UP_DP", "F.Cu", USB_W, up_dp_f)]
    hand_vias += [("UP_DN", *up_dn_b[0], 0.5, 0.3), ("UP_DP", *up_dp_b[0], 0.5, 0.3),
                  ("UP_DN", *up_dn_b[-1], 0.5, 0.3), ("UP_DP", *up_dp_b[-1], 0.5, 0.3)]
    # Each port's VREF through its ESD (U108–U408) in flow-through, drawn (the router joined the header to the divider
    # directly and left the ESD on a stub): header pin 2 up on B.Cu, under the pairs' trunk, to a via, then F.Cu into
    # the ESD's pin 5, over to pin 6 and on to the divider's R112–R412
    for cx in HDRS:
        k = 100 * (HDRS.index(cx) + 1)
        net = f"PORT{k // 100}_VREF"
        p5, p6 = (cx - 7.0, 34.8 + 0.4375), (cx - 7.0, 34.8 - 0.4375)     # U(k+8) at (cx − 8.0, 34.8), turned 90°
        hdr, via, r12 = (cx - 6.35, HDR_Y - 1.27), (cx - 6.35, 38.2), (cx - 4.5 - 0.51, LSF_Y + 1.2)
        hand_tracks += [(net, "B.Cu", 0.15, [hdr, via]),
                        (net, "F.Cu", 0.15, [via, (via[0], 36.0), (p5[0], 36.0 - (via[0] - p5[0])), p5]),
                        (net, "F.Cu", 0.15, [p5, p6]),
                        (net, "F.Cu", 0.15, [p6, (p6[0], r12[1] + 1.0), (p6[0] + 1.0, r12[1]), r12]),
                        # and on to the LSF0108's Vref_A (pin 2, its south row's west end), between C(k+5) and R(k+12)
                        (net, "F.Cu", 0.127, [r12, (r12[0], r12[1] - 0.55), (cx - 2.25, r12[1] - 0.55),
                                              (cx - 2.25, LSF_Y + 1.1875)])]
        hand_vias.append((net, *via, 0.5, 0.3))
    # Ports 1–3's RESET_N likewise, drawn into its ESD's (U109–U309) pin 5 (the router joined it between pins 5 and
    # 6 on port 2): header pin 11 up on B.Cu, east of pin 12 and under the pairs' trunk, to a via east of pin 5 (not
    # under it: 0.75 mm off port 1's lane, the Sensitive class), then pin 5, pin 6 and the 1k R(k+7) in a line (port
    # 4's ESD stands elsewhere: the router's is right)
    for cx in HDRS[:3]:
        net = f"PORT{HDRS.index(cx) + 1}_RST_N"
        p5, p6, r7 = (cx + 7.0, 37.2 + 0.4375), (cx + 7.0, 37.2 - 0.4375), (cx + 7.0, 35.0 + 0.51)
        hdr, via = (cx + 6.35, HDR_Y + 1.27), (cx + 7.75, p5[1])
        hand_tracks += [(net, "B.Cu", 0.127, [hdr, (cx + 7.4, hdr[1] - 1.05), (cx + 7.4, via[1] + 0.35), via]),
                        (net, "F.Cu", 0.127, [via, p5]), (net, "F.Cu", 0.127, [p5, p6, r7])]
        hand_vias.append((net, *via, 0.5, 0.3))
    # and BOOT_N: header pin 12 up on B.Cu to a via west of the ESD's pin 1 (0.75 mm off port 1's lane), on F.Cu
    # under pin 1 (no connect) into pin 2 from below, pin 9 and the 1k R(k+8): flow-through as RESET_N
    for cx in HDRS[:3]:
        net = f"PORT{HDRS.index(cx) + 1}_BOOT_N"
        p2, p9, r8 = (cx + 5.5, 37.2 + 0.4375), (cx + 5.5, 37.2 - 0.4375), (cx + 5.5, 35.0 + 0.51)
        hdr, via = (cx + 6.35, HDR_Y - 1.27), (cx + 4.5, 38.15)
        hand_tracks += [(net, "B.Cu", 0.127, [hdr, (cx + 6.35, 40.3), (cx + 4.5, 38.45), via]),
                        (net, "F.Cu", 0.127, [via, (cx + 5.35, via[1]), (cx + 5.5, via[1] - 0.15), p2]),
                        (net, "F.Cu", 0.127, [p2, p9, r8])]
        hand_vias.append((net, *via, 0.5, 0.3))
    # the hub's south VDD33 pin 5 takes its via inwards, under its body (between the pads and the UP pair): its
    # automatic fan-out via sat right below the row, between the downstream pairs, and boxed port 2's D− in
    # (Freerouting left it unrouted).  Its line goes on down to C15, its 100 nF, between ports 2 and 3's pairs.
    # Pin 10's runs down to C16, between port 4's D+ and the co-processor's D− via (0.2 mm wide, 0.139 mm from
    # that via), and C16 on east to its via: the pin → cap → via order (its via under the body gone)
    hand_tracks.append(("+3V3", "F.Cu", 0.25, [(HX - 1.75, HY + 4.4125), (HX - 1.75, HY + 3.75)]))
    hand_vias.append(("+3V3", HX - 1.75, HY + 3.75, 0.5, 0.3))
    hand_tracks.append(("+3V3", "F.Cu", 0.25, [(HX - 1.75, HY + 4.4125), (HX - 1.75, HY + 5.92)]))
    hand_tracks.append(("+3V3", "F.Cu", 0.2, [(HX + 0.75, HY + 4.4125), (HX + 0.7, HY + 4.9), (HX + 0.7, HY + 5.97),
                                             (HX + 0.95, HY + 6.22)]))
    hand_tracks.append(("+3V3", "F.Cu", 0.25, [(HX + 0.95, HY + 6.22), (HX + 1.6, HY + 6.22)]))
    hand_vias.append(("+3V3", HX + 1.6, HY + 6.22, 0.5, 0.3))
    # pin 64's: the pin down to C11 (its 100 nF) right below the corner, and its via inwards, under the hub's
    # body, off that line (it sat on it, between the pin and C11).  C11 is an exception to the pin → cap → via
    # order: no via fits past its +3V3 pad, between R1's RBIAS pad west and port 1's D− east
    p64 = (HX - 4.4125, HY + 3.75)                                      # U1 pin 64
    hand_tracks += [("+3V3", "F.Cu", 0.25, [p64, (HX - 4.7, p64[1] + 0.2875), (HX - 4.7, HY + 5.72)]),
                    ("+3V3", "F.Cu", 0.25, [p64, (HX - 3.6, HY + 3.6)])]
    hand_vias.append(("+3V3", HX - 3.6, HY + 3.6, 0.5, 0.3))
    six = LAYERS == 6
    pwr = "In4.Cu" if six else "In2.Cu"
    b.pcb = {
        "size": (W, H), "layers": LAYERS, "outline": outline, "passes": 80,
        # dense: JLC's multilayer floor (0.09 mm tracks and spaces, 0.2 mm from a via hole to a track); 0.1 mm
        # clearance and the 0.5 / 0.3 mm via keep the hole 0.2 mm from any track
        "min_track": 0.09, "min_clearance": 0.1, "hole_clearance": 0.2,
        # every signal layer beside a plane: F over GND (the USB pairs), B over the power plane; on 6 layers
        # In2 over GND, In3 over the power plane
        "inner": ([("In1.GND", "power"), ("In2.SIG", "signal"), ("In3.SIG", "signal"), ("In4.PWR", "power")]
                  if six else [("In1.GND", "power"), ("In2.PWR", "power")]),
        "stackup": "JLC06161H-3313" if six else "JLC04161H-7628", "finish": "ENIG",   # flat for the RP2350B's 0.4 mm QFN-80
        "edge_parts": [],
        "defer_pours": False,
        # net: (plane, via Ø, drill, track width); pins over another net's area are routed instead
        "fanout_nets": {"GND": ("In1.Cu", 0.5, 0.3, 0.25), "+5V": (pwr, 0.6, 0.3, 0.4),
                        "+3V3": (pwr, 0.5, 0.3, 0.25)},
        "plane_nets": {"+5V": pwr, "+3V3": pwr},
        # power pads connect solid, no thin relief where they carry current (pcbgen power_pads(); the user,
        # 2026-10-20: VBUS per port, +5V, ±5 V, +3V3_CP and the lead's +5V are power nets)
        "power_nets": {"GND": 1, "VIN": 2, "+5V": 2, "+5V_MX": 2, "-5V": 2, "+3V3": 2, "+3V3_CP": 2, "+1V1": 2,
                       "PORT?_VBUS": 2, "PORT?_5V_SW": 2},
        "stitch": 4.0,
        # the RF review (2026-10-21): GND vias every 5 mm round the edge, 0.9 mm in, drawn before the routing; and
        # each High-Speed pair's lines matched within 1 mm (tools/tests/test_pair_skew.py): all drawn, so the router's
        # meanders (tune_pairs()) find nothing to lengthen; the co-processor's Full-Speed pair (CP_HUB) not listed
        "edge_fence": {"pitch": 5.0, "inset": 0.9},
        "match": {"tol": 1.0, "pairs": [("UP_DP", "UP_DN"), *((f"PORT{n}_DP", f"PORT{n}_DN") for n in range(1, 5)),
                                        *((f"PORT{n}_CONN_DP", f"PORT{n}_CONN_DN") for n in range(1, 5))]},
        # each High-Speed link as the signal sees it, chip pin to far pin, within 1 mm (tools/tests/test_pair_skew.py):
        # the hub's upstream pair; each port's hub pair on through its USBLC6 to the receptacle
        "skew": {"tol": 1.0, "links": {"UP": (("UP_DP",), ("UP_DN",)),
                                       **{f"PORT{n}": ((f"PORT{n}_DP", f"PORT{n}_CONN_DP"),
                                                       (f"PORT{n}_DN", f"PORT{n}_CONN_DN")) for n in range(1, 5)}}},
        "zones": [
            {"layer": "In1.Cu", "net": "GND"},
            # +3V3 over +5V: their outlines 0.2 mm apart, under the planes' clearance, so one pulls back 0.1 mm
            # along the split; with equal priorities KiCad picks by the zones' UUIDs, new in each of the panel's
            # copies (its halves flipped at random).  The board had +3V3 win: now by priority
            {"layer": pwr, "net": "+3V3", "name": "pwr-3v3", "priority": 1, "poly": IN_3V3},
            {"layer": pwr, "net": "+5V", "name": "pwr-5v", "poly": IN_5V},
            # the co-processor's island in the DSN with the planes, not added after the routing: deferred,
            # Freerouting saw its vias as unconnected and joined the IOVDD pins by tracks under U11
            {"layer": pwr, "net": "+3V3_CP", "name": "pwr-3v3cp", "priority": 2, "poly": ISLAND},
            # U3 (AP2114H, ≈ 0.65 W): top-side copper on its tab with C3's +3V3 pad, and on VIN with C2's +5V
            # pad, each with its vias to its plane; exclusive, so the router keeps its tracks off them
            {"layer": "F.Cu", "net": "+3V3", "name": "ldo-vout", "priority": 3, "exclusive": 0.3,
             "poly": [(LDO_WEST, LDO[1] - 5.8), (LDO[0] + 3.6, LDO[1] - 5.8), (LDO[0] + 3.6, LDO[1] - 1.3),
                      (LDO_WEST, LDO[1] - 1.3)]},
            # and under it on the rear face, as far as the +5V_MX line at x 8.3
            {"layer": "B.Cu", "net": "+3V3", "name": "ldo-back", "priority": 3, "exclusive": 0.3,
             "poly": [(LDO_WEST, LDO[1] - 5.8), (7.9, LDO[1] - 5.8), (7.9, LDO[1] - 1.3), (LDO_WEST, LDO[1] - 1.3)]},
            {"layer": "F.Cu", "net": "+5V", "name": "ldo-vin", "priority": 3, "exclusive": 0.3,
             "poly": [(LDO[0] + 1.3, LDO[1] + 2.0), (LDO[0] + 3.75, LDO[1] + 2.0), (LDO[0] + 3.75, LDO[1] + 6.5),
                      (LDO[0] + 1.3, LDO[1] + 6.5)]},
            *buck_zones,
            {"layer": "F.Cu", "net": "GND", "holes": [VREG_HOLE]},
            {"layer": "B.Cu", "net": "GND"},
            *vreg_zones,
        ],
        "tracks": hand_tracks, "vias": hand_vias,
        # each decoupling capacitor's pin (electronics/tools/decoupling.py: its pad ≤ 2 mm from the pin, its GND pad
        # ≤ 1 mm from a GND via).  Not declared: bulk (C60, VIN's; C31, the co-processor's island; each port's VBUS
        # 22 µF; the converter's second 10 µF and its 22 µF outputs), the crystals' load capacitors, the charge
        # pump's flying capacitor and the converter's bootstrap capacitor.  The converter's first 10 µF its own 3 mm,
        # as the bay node's and the DATA ×6's.  C8, VDD18PLL's 4.7 µF, is
        # its store, behind C10 (the 100 nF at the pin), right under the crystal: its own 2.5 mm limit (no spot
        # nearer clears Y1's courtyard); so is C7, VDD18's 4.7 µF, behind C9.  C21 and C24, each crosspoint's VDD 1 µF, are its store too, stacked
        # right behind the 100 nF at the pin (C20, C23): their own 3 mm limit.  Round the co-processor, C40, C41
        # (IOVDD pins 5, 15) and C46 (DVDD pin 10) keep their places with their own limits: the pull-up and bus lines
        # frame those pins on its east face (a GPIO reassignment was tried on 2026-10-29, and three routing passes
        # did not close the east face's bus fan-out); C46's +1V1 also has C47 (4.7 µF) 2.0 mm from pin 32, no via.
        # C44 (IOVDD pin 29) too: over the pin lies the crystal Y2's F.Cu keep-out
        "decoupling": {
            "C2": "U3.3", "C3": "U3.2", "C6": "U5.3",                                   # the LDO in and out, MAX809S
            "C61": ("U13.VIN", 3.0), "C63": "U13.VIN",                                   # the 5 V converter
            "C7": ("U1.25", 2.5), "C9": "U1.25", "C8": ("U1.62", 2.5), "C10": "U1.62",  # the hub's VDD18, PLL
            "C11": "U1.64", "C12": "U1.52", "C13": "U1.57", "C14": "U1.24", "C15": "U1.5", "C16": "U1.10",
            "C17": "U1.46",                                                               # its seven 3.3 V pins
            "C18": "U2.15", "C19": "U6.15", "C29": "U10.16",                             # the expanders
            "C20": "U7.38", "C21": ("U7.38", 3.0), "C22": "U7.16", "C23": "U8.38", "C24": ("U8.38", 3.0),
            "C25": "U8.16",
            "C27": "U9.2", "C28": "U9.1",                                                 # crosspoints, charge pump
            "C32": "U11.64", "C33": "U11.65", "C34": "U11.61",                           # the core regulator
            "C35": "U11.41", "C36": "U11.50", "C37": "U11.59", "C38": "U11.69", "C39": "U11.76",
            "C40": ("U11.5", 3.1), "C41": ("U11.15", 3.8), "C42": "U11.24", "C43": "U11.24",       # IOVDD
            "C44": ("U11.29", 3.0),
            "C45": "U11.51", "C46": ("U11.10", 4.0), "C47": "U11.32",                    # DVDD
            **{f"C{k + 1}": f"U{k + 1}.1" for k in (100, 200, 300, 400)},              # each port's switch IN
            **{f"C{k + 3}": f"U{k + 2}.6" for k in (100, 200, 300, 400)},              # its INA226
            **{f"C{k + 4}": f"U{k + 3}.5" for k in (100, 200, 300, 400)},              # its USBLC6's VBUS
            **{f"C{k + 5}": f"U{k + 7}.20" for k in (100, 200, 300, 400)}},            # its LSF0108's VREF_B
        # the 100 nF that cannot keep the pin → cap → via order where they sit (decoupling.py), with the measures
        # (2026-10-29): each still beside its pin, no via between pin and capacitor but where noted
        "decoupling_order_exempt": {
            "C11": "U1 pin 64's via under the case, beyond the pin; none fits past C11's pad: R1's RBIAS pad 0.12 mm "
                   "into one west of it, port 1's D- 0.03 mm into one east",
            "C15": "U1 pin 5's via under the case, beyond the pin; none fits past C15's pad between ports 2 and 3's "
                   "pairs: each 0.30 mm into one either side",
            "C23": "U8's VDD (pin 38): +5V_MX comes in at the pin from its via (67.47, 16.36) under the case; to "
                   "reach C23's far side it would cross every north pin's line on F.Cu or the buses on B.Cu.  C23 "
                   "0.59 mm from the pin, no via",
            "C40": "U11 pin 5 (east face, framed by the pull-up and bus lines): C40 3.0 mm away, the pin on to the "
                   "island's via first",
            "C41": "U11 pin 15 (east face, likewise): C41 3.7 mm away, the two meet through the island",
            "C44": "U11 pin 29: the crystal Y2's keep-out over the pin; C44 2.7 mm away, the two meet through vias",
            "C45": "U11 pin 51 (DVDD) keeps its via under the case into +1V1: no room past C45 between C36's +3V3_CP "
                   "line north and the VREF vias south.  C45 0.51 mm west of the pin",
            "C46": "U11 pin 10 (DVDD, east face): C46 3.9 mm away, the two meet through vias; C47 (4.7 uF) 2.0 mm "
                   "from pin 32, no via"},
        "dru": XTAL_RULE + XTAL2_RULE + SILK_RULE + ANGLE_RULE,
        "min_width_except": MIN_WIDTH_EXCEPT,
        "keepouts": CRADLE_KEEPOUTS + [
            # the hub crystal's block: no other net's track or via on either face (dropped once routed)
            {"name": "core:xtal-y1", "layers": ["F.Cu", "B.Cu"], "poly": XTAL_KEEP},
            {"name": "core:xtal-y2", "layers": ["F.Cu"], "poly": XTAL2_KEEP},
            # each hub pair's band on F.Cu (the layout review: 3 × the track gap between a fast bus and other nets'
            # lines, the enables and faults first): no other track along it, vias in (dropped once routed)
            *({"name": f"core:usb{n}", "layers": ["F.Cu"], "tracks_only": True,
               "poly": offset(band, bw) + offset(band, -bw)[::-1]}
              for bw in [(USB_W + 0.15) / 2 + USB_W / 2 + HS_BAND] for n, (_, band) in sorted(hs_centrelines().items())),
            # and round each D−'s bump, which leaves the pair's band
            *({"name": f"core:usb{n}b", "layers": ["F.Cu"], "tracks_only": True,
               "poly": [(min(x for x, _ in bp) - d, bp[0][1] - d), (bp[0][0], bp[0][1] - d),
                        (bp[0][0], bp[-1][1] + d), (min(x for x, _ in bp) - d, bp[-1][1] + d)]}
              for d in [USB_W / 2 + HS_BAND] for n, (_, _, bp) in sorted(hs_lines().items())),
            # no via round the SWD header's hand-soldered pins (a GND stitching via landed 0.4 mm from pin 1's pad):
            # a bridge on the rear face would ground SWCLK
            {"name": "swd-hdr", "layers": ["F.Cu", "B.Cu"], "vias_only": True,
             "poly": [(SWD_HDR[0] - 1.6, SWD_HDR[1] - 1.6), (SWD_HDR[0] + 4 * 2.54 + 1.6, SWD_HDR[1] - 1.6),
                      (SWD_HDR[0] + 4 * 2.54 + 1.6, SWD_HDR[1] + 1.6), (SWD_HDR[0] - 1.6, SWD_HDR[1] + 1.6)]},
            # no via in the +5V band (the tongue's run down the cradle's band, 4 mm wide, all of the +5V's 3.09 A):
            # a GND stitching via there took 1.1 mm of it at every 4 mm (2026-11-02).  The edge fence's GND vias
            # (x 0.9) tie the outer pours there; LDO_WEST's vias at x 5.2 stay, on the band's edge
            {"name": "5v-band", "layers": [pwr], "vias_only": True,
             "poly": [(1.3, TB), (4.65, TB), (4.65, PWR_SPLIT + 1.5), (1.3, PWR_SPLIT + 1.5)]},
            # the core regulator (the audit's fixes 2 and 3, RP2350 DS §6.3.8.1 and Fig. 27): the router's tracks
            # off the block below the VREG pins (a "core:" area, dropped once routed: +1V1 leaves by its two V_OUT
            # vias, +3V3_CP by VREG_VIN's inner end), up to the V_OUT vias, so USB_DM / USB_DP (pins 66, 67) leave
            # straight past their east side as on Raspberry Pi's board; and no copper at all under LX (pin 63 to
            # L1's LX pad) and L1 on the planes and B.Cu
            {"name": "core:vreg-block", "layers": ["F.Cu"], "tracks_only": True,
             "poly": [(CP[0] - 4.55, CP[1] + 5.4), (CP[0] - 1.95, CP[1] + 5.4), (CP[0] - 1.95, CP[1] + 9.75),
                      (CP[0] - 4.55, CP[1] + 9.75)]},
            {"name": "lx-under", "layers": ["In1.Cu", "In2.Cu", "B.Cu"] if not six else ["In1.Cu", "In2.Cu", "In3.Cu",
                                                                                     "In4.Cu", "B.Cu"],
             "poly": [(CP[0] - 3.3, CP[1] + 4.95), (CP[0] - 2.7, CP[1] + 4.95), (CP[0] - 2.7, CP[1] + 7.62),
                      (CP[0] - 1.9, CP[1] + 7.62), (CP[0] - 1.9, CP[1] + 9.82), (CP[0] - 4.2, CP[1] + 9.82),
                      (CP[0] - 4.2, CP[1] + 7.62), (CP[0] - 3.3, CP[1] + 7.62)]}] + [
            {"name": f"edge{i}", "poly": [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]}
                     for i, (x0, y0, x1, y1) in enumerate((
                         (0, 0, W, 0.35), (W - 0.35, 0, W, H), (0, H - 0.35, W, H), (0, 0, 0.35, H),
                         *((x0 - 0.35, top - 0.35, x1 + 0.35, H) for x0, x1, top in NOTCHES)))] + [
            # the panel's mouse bites (0.6 mm holes, 0.2 mm into the edge): copper at least 0.7 mm from them
            {"name": f"tab{i}", "poly": [(x - TAB_W / 2 - 0.5, 0), (x + TAB_W / 2 + 0.5, 0), (x + TAB_W / 2 + 0.5, 1.2),
                                         (x - TAB_W / 2 - 0.5, 1.2)]} for i, x in enumerate(TABS)] + [
            # B.Cu runs over the power plane: no B.Cu track crosses its split (+3V3 / +5V, and the converter's
            # tongue's edges), so every signal that does, the USB pairs included, crosses it on F.Cu over the GND
            # plane (the RF review, 2026-10-21: no plane change for the return current)
            {"name": name, "layers": ["B.Cu", "In3.Cu"] if six else ["B.Cu"], "tracks_only": True,
             "poly": [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]}
            for name, (x0, y0, x1, y1) in (
                ("split", (0.35, PWR_SPLIT - 0.5, W - 0.35, PWR_SPLIT + 0.5)),
                ("split-5v-east", (TA - 0.4, 0.35, TA + 0.6, TB + 0.6)),
                ("split-5v-foot", (5.0, TB - 0.4, TA + 0.6, TB + 0.6)),
                ("split-5v-band", (5.0, TB - 0.4, 6.0, PWR_SPLIT)))],
        "panel": {"gap": 2.0, "tabs": TABS, "tab_width": TAB_W, "bite": {"drill": 0.6, "pitch": 1.0, "offset": 0.2},
                  "boards": [{"tag": "L", "variant": None, "rot": 0}, {"tag": "B", "variant": "base", "rot": 180}]},
        # the base DATA-4x: this PCB with the logic left off (module docstring)
        "variants": {"base": {"dnp": logic_only(b)}},
        "texts": [{**t, "thickness": max(SILK_TEXT, 0.15 * t["size"])} for t in [
            # layout B (the usability review, the user's "oui je valide", 2026-10-21): each header's pin names in
            # two lines over it, read with the jumpers in, stacked as its rows (the even, upper row's over the odd,
            # lower row's), and a big port number by it, beside the port's VBUS LED
            *({"text": str(n), "x": HDRS[n - 1] - 7.4, "y": HDR_Y - 7.0, "size": 2.0} for n in range(1, 5)),
            *({"text": HDR_PINS[i], "x": HDRS[n] - 6.35 + 2.54 * (i // 2),
               "y": HDR_Y - (4.58 if i % 2 == 1 else 3.38), "size": 0.9}
              for n in range(4) for i in range(12)),
            # the bring-up test points' names, on the rear face under each pad (mirrored, read from behind), and
            # what the base doesn't have (only GND is live there): the co-processor's row and core rail, the matrix.
            # TP25's (SCL) over its pad: under it, at a 0.15 mm stroke, it touched TP26's ring; ports 3 and 4's
            # VBUS over theirs, by the bottom edge's fence
            *({"text": name, "x": x, "y": y + (-1 if ref in ("TP25", "TP302", "TP402") else 1) * (d / 2 + 0.75),
               "size": 0.8,
               "layer": "B.SilkS"} for ref, (net, name, d, x, y) in TPS.items()),
            # the SWD header's pin names, read on the front face, alternately over and under it from pin 1 (west)
            *({"text": name, "x": SWD_HDR[0] + 2.54 * i, "y": SWD_HDR[1] + (-2.1 if i % 2 == 0 else 2.1), "size": 0.8}
              for i, (_, name) in enumerate(SWD_PINS)),
            {"text": "CP", "x": SWD_HDR[0] - 3.8, "y": SWD_HDR[1] + 0.25, "size": 1.0},   # whose SWD: the co-processor's
            # the lead's connector, named on the rear face where it plugs in (it brings the 20 V), and each of its
            # pins beside the housing, pin 1 lowest: as the DATA ×6's (the silkscreen plan, 2026-11-02)
            {"text": "LEAD 20 V", "x": LEAD[0], "y": LEAD[1] + 3.6, "size": 1.0, "layer": "B.SilkS"},
            *lead_pin_names(LEAD[0] + 2.75, LEAD[1], ["NC", "SCL", "SDA", "GND", "D-", "D+", "GND", "VIN"]),
            {"text": "LOGIC ONLY", "x": 28.0, "y": 6.6, "size": 0.8, "layer": "B.SilkS"},
            {"text": "LOGIC ONLY", "x": 9.5, "y": 12.9, "size": 0.8, "layer": "B.SilkS"},
            {"text": "LOGIC ONLY", "x": 43.12, "y": 18.4, "size": 0.8, "layer": "B.SilkS"},
            {"text": "LOGIC ONLY", "x": 55.0, "y": 21.75, "size": 0.8, "layer": "B.SilkS"},
        ]] + [
            # the title block, as on every board (silk.title_block(), its own strokes, not the rule above): in the
            # rear face's top-right corner as read from below, slid 17 mm in and 19 mm down: the nearest spot 1 mm
            # clear of other silk (LOGIC ONLY, STB1), 0.3 mm of pads and holes, 4 mm of the connectors (J2, the
            # headers; silkair.py); this board has no free edge for it
            *title_block("DATA ×4 v1.0", 1 + 17 + LOGO_W, 1 + 19),
            # each USB-C's port number (silk.port_mark(), as the DATA ×6's; its own stroke, not the rule above),
            # left of its body: the band over the receptacles holds the headers and the clusters, so this one
            # shows on the bench, not over the wall (the silkscreen plan, 2026-11-02)
            *(port_mark(n, x - 4.3, 64.3) for n, x in enumerate(USBS, 1)),
        ],
    }
    return b


USB_W = 0.15 if LAYERS == 6 else 0.25
# The layout review's checks as rules (2026-11-01, the DATA ×6's), generated from NETCLASSES (electronics/tools/
# netrules.py): the supplies' widths (Supply, Power, Port: "_min_width"), the fine-pitch fan-outs aside
# (MIN_WIDTH_EXCEPT: the hub's 0.5 mm and the co-processor's 0.4 mm pins, whose lines neck down at the pads; the
# hub's pin 10 to C16, 0.2 mm between two pairs; the core regulator's +1V1 sense line, 0.15 mm on purpose; the
# matrix's ±5 V, a few mA, necked by the router between the crosspoints' and the LSF0108s' pins); and the
# board's enables, faults, resets, boot lines and selects (the Sensitive class) kept 3 × the USB lines' width off
# them, against a coupled spike that would switch a port off, reset or boot a DUT, reset the hub, an expander, the
# crosspoints or the co-processor, or latch a crosspoint (its STB) or the co-processor's flash (its QSPI SS)
MIN_WIDTH_EXCEPT = {"courtyards": ["U1", "U11", "C16"], "nets": ["+1V1", "+5V_MX", "-5V"],
                    "why": "in the hub's and the co-processor's fan-out, and the matrix's few-mA ±5 V"}
# X4: KiCad names a sheet's local nets "/Port n/PORTn_…": the patterns need their leading "*"
NETCLASSES = [
    # dense board: 0.127 mm signal tracks, 0.1 mm clearance (JLC's multilayer minimum is 0.09) and the 0.5 /
    # 0.3 mm via (JLC's recommended ring, no extra cost) wherever the current allows
    {"name": "Default", "clearance": 0.1, "track_width": 0.127, "via_diameter": 0.5, "via_drill": 0.3},
    {"name": "Supply", "clearance": 0.1, "track_width": 0.25, "via_diameter": 0.5, "via_drill": 0.3,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 5,
     "_patterns": ["+3V3", "*+3V3_CP", "*+1V1", "-5V", "+5V_MX"], "_min_width": 0.25},
    # +5V: the plane carries the ports' current; its routed stretches feed the few loads above the split, at v1's
    # 0.6 mm; VIN and the converter's switch node likewise.  The ports' 5V_SW and VBUS stay at 0.3 mm: the vertical USB-C's VBUS pads are 0.3 mm wide at a
    # 0.5 mm pitch, so a wider track can't reach them, and at the 0.64 A limit 15 mm of it drops ≈ 16 mV
    {"name": "Power", "clearance": 0.15, "track_width": 0.6, "via_diameter": 0.6, "via_drill": 0.3,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 1,
     "_patterns": ["+5V", "*VIN", "*BUCK_SW"], "_min_width": 0.25},
    {"name": "Port", "clearance": 0.1, "track_width": 0.3, "via_diameter": 0.6, "via_drill": 0.3,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 2,
     "_patterns": ["*PORT?_5V_SW", "*PORT?_VBUS"], "_min_width": 0.25},
    {"name": "Sensitive", "clearance": 0.1, "track_width": 0.127, "via_diameter": 0.5, "via_drill": 0.3,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 6,
     "_patterns": ["*PORT?_EN", "*PORT?_FLT_N", "*HUB_RST_N", "*BUCK_EN", "*EXP?_RST_N", "*MX_RST", "*CP_RUN",
                   "*PORT?_RST_IO", "*PORT?_BOOT_IO", "*PORT?_RST_N", "*PORT?_BOOT_N", "*CP_BOOT_N", "*CP_QSPI_SS",
                   "*MX_STB?"]},
    # ≈ 90 Ω differential on the outer layers: over 0.1 mm of 3313 prepreg on 6 layers, 0.2 mm of 7628 on 4
    {"name": "USB", "clearance": 0.127, "track_width": USB_W, "via_diameter": 0.5, "via_drill": 0.3,
     "diff_pair_width": USB_W, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 3,
     "_patterns": ["*_DP", "*_DN"]},
    # the two I²C buses, this board's (SCL/SDA: the expanders, the INA226s, the crosspoints' control) and the lead's
    # (LEAD_SCL/LEAD_SDA, to the node, behind Q1/Q2): a class of their own, as slow as Default (the layout review:
    # every signal in a class)
    {"name": "I2C", "clearance": 0.1, "track_width": 0.127, "via_diameter": 0.5, "via_drill": 0.3,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 7,
     "_patterns": ["SCL", "SDA", "*LEAD_SCL", "*LEAD_SDA"]},
    {"name": "Pins", "clearance": 0.1, "track_width": 0.127, "via_diameter": 0.5, "via_drill": 0.3,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 4,
     "_patterns": ["*PORT?_P?", "*PORT?_A?", "*PORT?_B?", "BUS_?"]},
]
