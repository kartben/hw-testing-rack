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
* the ports' 5 V made here from the rack's 20 V (VIN, a PH 2 of its own on the rear face, after the node's
  protection): two LMR51625, +5V_A for ports 1–3 and the logic, +5V_B for ports 4–6, never in parallel (the
  power plane's +5V split left / right).  The PH 8 lead is the v2's, pin for pin.

The board stands where the v2 stands (config/rack.yaml › pcb.data_port_x6), 100 × 80 mm, 10 mm taller, held at
both ends by the cradle; every part JLC places on the front face (Economic, one side), the headers, the leads and
the SWD header soldered by hand.  Functions grouped as the study drew them (the user, 2026-10-31): top, the
co-processor and its SWD left, the six blocks in the middle, the hub right; under the blocks the pin chains; then
a row with a converter, the three crosspoints and the expanders; then each port's switch and current sense; at the
bottom the USB-C.  One PCB, two assemblies as the v2: as drawn DATA-6x-logic; "base" leaves the logic off.
"""

from __future__ import annotations

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
USBS = CFG["usb"]                   # board x of the six vertical USB-C
USB_Y = TOP_Z - CFG["usb_z"]        # their axis (z 11, the port wall's openings)
BLK_X = CFG["blocks"]["x"]          # the six header blocks' centres
BLK_Y = TOP_Z - CFG["blocks"]["z"]
LEAD = (CFG["lead"][0], TOP_Z - CFG["lead"][1] - 7.0)      # J1's pin 1, its pins running down
VIN_J = (CFG["vin"][0], TOP_Z - CFG["vin"][1] - 1.0)       # J3's pin 1 (VIN), pin 2 (GND) 2 mm under it
# The header's pins (PinHeader_2x06 upright: odd pins the left column, even the right, rows top to bottom).  Read
# from the front (the study, 2026-10-31): the left column VREF, P1, P2, P3, P4, BOOT, the right GND, P5, P6, P7,
# P8, RESET; each row pairs P k with P k + 4, as the v2's columns did
HDR_SIG = {1: "VREF", 2: "GND", 3: "P1", 4: "P5", 5: "P2", 6: "P6", 7: "P3", 8: "P7", 9: "P4", 10: "P8",
           11: "BOOT_N", 12: "RST_N"}
LEGEND = (("VREF", "GND"), ("1", "5"), ("2", "6"), ("3", "7"), ("4", "8"), ("BOOT", "RST"))
# each block's colour (rack.yaml › blocks.colours, R Y G B W K): catalog.py's hdr2x6t_<colour>, MINTRON's one series
# (alike but for the plastic), hand-soldered: out of the JLC BOM and CPL, in the board's
HDR_COLOUR = {"R": "red", "Y": "yellow", "G": "green", "B": "blue", "W": "white", "K": "black"}
# The placement, block by block (KiCad mm).  The co-processor and the hub stand as on the v2, the hub at the
# v2's x one row lower (its pairs nearer the ports), the co-processor 31.1 mm west of the v2's, at its y: their
# drawn copper carries over with them
CP = (15.9, 12.9)                   # RP2354B, turned 180°: the v2's block
CP_DX = CP[0] - 47.0                # its shift from the v2's (47.0, 12.9)
HX, HY = 87.5, 31.0                 # the hub, turned 90°, DN pins south
XT = (HX - 8.9, HY + 1.75)          # its 24 MHz crystal
CHIP = [(29.4, 41.3), (48.26, 41.3), (67.12, 41.3)]    # the crosspoints: ports 1–2, 3–4, 5–6
EXP = [(38.83, 41.3, "GND"), (57.69, 41.3, "+3V3")]    # the TCA9535s between them: ports 1–3, 4–6
MX_EXP = (76.85, 41.3)              # the matrix expander (TCA9534A), right of the third crosspoint
LDO = (10.4, 53.5)                  # U3, the 3.3 V LDO, under converter A (+5V_A), tab up
BULK = (72.85, 22.3)                # VIN's 33 µF, under the blocks' legend; J3 right under it
SWD_HDR = (7.2, 26.2)               # J2, the co-processor's SWD header (1 × 5), pin 1 west, under it
SWD_PINS = (("CP_SWCLK", "SWCLK"), ("GND", "GND"), ("CP_SWDIO", "SWDIO"), ("CP_RUN", "RUN"), ("+3V3", "3V3"))
NINV = (10.5, 30.6)                 # U9, the −5 V inverter, under J2
CL_Y = 56.7                         # each port's power cluster: its frame's top
UP_Y = 66.5                         # over each receptacle: its VBUS 22 µF, CC resistors, LED
CH_Y = 18.8                         # each port's pin chain: its first row (the ESD), under its block
# the two 5 V converters: the bay node's LMR51625 block (bay-node/design.py) at an offset, the node's own layout
BUCKS = {"A": (2.4, -5.0), "B": (73.8, -39.2)}
J1_ROT = 270


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
LANE = (5, 1, 6, 2, 7, 3, 8, 4)     # the LSF0108's channels 1–8 → P pins (the v2's)
TPD_SIG = (1, 2, 4, 5)
TPD_THRU = {1: 10, 2: 9, 4: 7, 5: 6}
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
    "TP1": ("CP_SWCLK", "SWCLK", 1.0, 8.0, 2.4), "TP2": ("CP_SWDIO", "SWDIO", 1.0, 10.6, 2.4),
    "TP3": ("GND", "GND", 1.5, 13.4, 2.6), "TP10": ("+3V3_CP", "+3V3_CP", 1.5, 7.6, 8.6),
    "TP11": ("+1V1", "+1V1", 1.5, 12.0, 15.4), "TP12": ("CP_RUN", "RUN", 1.0, 7.4, 13.0),
    "TP13": ("CP_BOOT_N", "BOOT", 1.0, 7.4, 16.0),
    # the matrix: ±5 V, the expander's bus, STB1–3 and RST, a GND
    "TP4": ("-5V", "−5V", 1.5, 15.5, 30.0), "TP5": ("+5V_MX", "+5V_MX", 1.5, 18.5, 30.0),
    "TP6": ("GND", "GND", 1.5, 21.5, 30.0), "TP14": ("MX_DAT", "DAT", 1.0, 73.5, 38.0),
    "TP15": ("MX_CK", "CK", 1.0, 76.0, 38.0), "TP16": ("MX_STB1", "STB1", 1.0, 73.5, 50.5),
    "TP17": ("MX_STB2", "STB2", 1.0, 76.0, 50.5), "TP40": ("MX_STB3", "STB3", 1.0, 78.5, 50.5),
    "TP18": ("MX_RST", "MX RST", 1.0, 78.5, 38.0), "TP19": ("GND", "GND", 1.5, 81.0, 50.5),
    # the supplies: VIN, +5V_A, +5V_B, +3V3, with GND
    "TP7": ("+3V3", "+3V3", 1.5, 13.5, 49.0), "TP8": ("GND", "GND", 1.5, 10.5, 49.0),
    "TP9": ("+5V_A", "+5V_A", 1.5, 7.5, 49.0), "TP41": ("+5V_B", "+5V_B", 1.5, 84.0, 16.0),
    "TP42": ("VIN", "VIN", 1.5, 80.0, 16.0), "TP43": ("GND", "GND", 1.5, 88.0, 16.0),
    # the hub's reset and core rail, with a GND
    "TP20": ("HUB_RST_N", "HUB RST", 1.0, 81.5, 20.5), "TP21": ("GND", "GND", 1.5, 77.0, 21.0),
    "TP22": ("HUB_1V8", "1V8", 1.5, 92.5, 35.25),
    # the board side of the lead's I²C and INT, with a GND
    "TP23": ("INT", "INT", 1.0, 85.5, 42.5), "TP24": ("SDA", "SDA", 1.0, 85.5, 45.0),
    "TP25": ("SCL", "SCL", 1.0, 85.5, 47.5), "TP26": ("GND", "GND", 1.5, 85.5, 50.0),
    # GND by each expander
    "TP27": ("GND", "GND", 1.5, 38.85, 51.0), "TP28": ("GND", "GND", 1.5, 57.35, 51.0),
    # the crosspoints' eight buses (the co-processor's GPIO2–9), on their way between the chips, with a GND
    **{f"TP{29 + i}": (f"BUS_{b}", b, 1.0, 37.0 + 2.2 * (i % 4), 31.0 + 2.2 * (i // 4)) for i, b in enumerate(BUSES)},
    "TP37": ("GND", "GND", 1.5, 46.5, 32.1),
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


def supply(n: int) -> str:
    """Port n's 5 V: +5V_A for ports 1–3 (and the logic), +5V_B for ports 4–6"""
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
    # the cluster in a 12 × 8 mm frame over the port's USB-C (x0, y0 its corner), the v2's
    x0, y0 = cx - 5.0, CL_Y
    part(s, sw, "vbus_sw_latch", {"IN": v5, "GND": "GND", "EN": p + "EN", "~{FAULT}": p + "FLT_N",
                                  "ILIM": p + "ILIM", "OUT": p + "5V_SW"}, pcb=P(x0 + 2.45, y0 + 2.2, 180),
         sch=at(30, 22, fields=(-4, -4)))
    C(s, f"C{k + 1}", "1u", v5, "GND", size="0402", pcb=P(x0 + 5.13, y0 + 2.9, 90), sch=at(15, 24))
    s.wire(f"C{k + 1}.1", (15, 21), (20, 21))
    R(s, f"R{k + 1}", "47k", p + "ILIM", "GND", size="0402", pcb=P(x0 - 0.97, y0 + 2.2, 180), sch=at(22, 28))
    s.wire(f"{sw}.ILIM", (22, 24), f"R{k + 1}.1")
    # the port is off until the node switches it on
    R(s, f"R{k + 2}", "10k", p + "EN", "GND", size="0402", pcb=P(x0 + 9.9, y0 + 3.65, 90), sch=at(14, 36))
    R(s, f"R{k + 3}", "10k", "+3V3", p + "FLT_N", size="0402", pcb=P(x0 + 9.9, y0 + 5.6, 90), sch=at(40, 36))
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
    # beside it): its pair comes down the board's west edge.  Its VBUS 100 nF right over its pin 5
    ex_ = (cx - 7.5, USB_Y, 180) if n > 1 else (cx - 4.2, UP_Y - 0.25, 180)
    part(s, esd, "esd", {"1": p + "CONN_DN", "6": p + "DN", "3": p + "CONN_DP", "4": p + "DP", "5": v5,
                         "2": "GND"}, pcb=P(*ex_), sch=at(84, 76))
    s.wire(f"{usb}.B7", f"{esd}.1")
    s.wire(f"{usb}.A6", f"{esd}.3")
    cap = (ex_[0] + 1.0, ex_[1] - 2.6) if n > 1 else (ex_[0], ex_[1] - 2.35)
    C(s, f"C{k + 4}", "100n", v5, "GND", size="0402", pcb=P(*cap, 0), sch=at(96, 76))

    key = CFG["blocks"]["colours"][n - 1]
    s.frame(f"Header {n} (2 × 6 through-hole, {HDR_COLOUR[key]}): GND, VREF, P1–P8, "
            "RESET_N, BOOT_N; ESD on VREF (in flow-through to the LSF0108 and the divider) and on RESET/BOOT (to the 1k), "
            "their expander lines pulled up", 112, 10, 228, 56)
    hdr = {str(q): (sig if sig == "GND" else p + sig) for q, sig in HDR_SIG.items()}
    colour = HDR_COLOUR[key]
    # through-hole, soldered by hand, upright: the footprint's origin is pin 1 (the left column's top)
    part(s, f"J{k + 2}", f"hdr2x6t_{key}", hdr, f"PINS{n}", pcb=P(bx - 1.27, BLK_Y - 6.35, 0),
         sch=at(184, 30, fields=(-1, -5)))
    # RESET/BOOT through an H5VU25UC (flow-through) and 1k; the expander lines' pull-ups by the expander
    part(s, f"U{k + 9}", "esd4", {"GND": "GND", "2": p + "BOOT_N", "9": p + "BOOT_N", "5": p + "RST_N",
                                  "6": p + "RST_N", "1": None, "10": None, "4": None, "7": None},
         pcb=P(bx + 1.6, CH_Y + 2.3, 90), sch=at(214, 44, fields=(-3, -7)))
    for r, sig, dx, sy in ((f"R{k + 7}", "RST", 0.0, 34), (f"R{k + 8}", "BOOT", 1.1, 44)):
        R(s, r, "1k", p + sig + "_IO", p + sig + "_N", size="0402", pcb=P(bx + dx, CH_Y + 12.75, 90),
          sch=at(150, sy, rot=90))
    ex, ey = EXP[(n - 1) // 3][:2]
    j = (n - 1) % 3
    for r, sig, i, rot in ((f"R{k + 9}", "RST", 0, 270), (f"R{k + 10}", "BOOT", 1, 90)):
        R(s, r, "100k", "+3V3", p + sig + "_IO", size="0402", pcb=P(ex - 1.6 + 1.6 * j, ey + 3.6 + 1.9 * i, rot),
          sch=at(138, (34, 44)[i] - 5))
        s.wire(f"{r}.2", (138, (34, 44)[i]), f"R{k + 7 + i}.1")
        s.wire((128, (34, 44)[i]), (138, (34, 44)[i]), net=p + sig + "_IO")
        s.tag(p + sig + "_IO", (128, (34, 44)[i]), "left")

    part(s, f"U{k + 8}", "esd4", {"GND": "GND", "5": p + "VREF", "6": p + "VREF", "1": None, "10": None,
                                  "2": None, "9": None, "4": None, "7": None},
         pcb=P(bx - 1.6, CH_Y + 2.3, 90), sch=at(214, 22, fields=(-3, -7)))

    chip = (n - 1) // 2
    s.frame(f"Pins {n}: ESD in flow-through, 100 Ω, LSF0108 (A = the DUT's VREF, "
            f"B = 3.3 V) to crosspoint {('U7', 'U8', 'U12')[chip]}'s X lines", 6, 104, 228, 146)
    for j, colx in enumerate((bx - 1.6, bx + 1.6)):
        pins = [LANE[4 * j + i] for i in range(4)]
        tpd = {"GND": "GND"}
        for pin, q in zip(TPD_SIG, pins):
            tpd[str(pin)] = tpd[str(TPD_THRU[pin])] = f"{p}P{q}"
        part(s, f"U{k + 5 + j}", "esd4", tpd, pcb=P(colx, CH_Y, 90), sch=at(28 + 36 * j, 128, fields=(-3, -7)))
        rarray(s, f"RN{k + 1 + j}", "100", [(f"{p}P{q}", f"{p}A{q}") for q in pins],
               P(bx - 1.4 + 2.8 * j, CH_Y + 4.7, 0), sch=at(50 + 36 * j, 128))
    lsf = {"GND": "GND", "RefA": p + "VREF", "RefB": p + "VREFB", "EN": p + "VREFB", "EPAD": "GND"}
    for c in range(1, 9):
        lsf[f"A{c}"] = f"{p}A{LANE[c - 1]}"
        lsf[f"B{c}"] = f"{p}B{LANE[c - 1]}"
    part(s, f"U{k + 7}", "lsf0108", lsf, pcb=P(bx, CH_Y + 7.95, 90), sch=at(132, 128, fields=(-10, -8)))
    rail(s, "GND", [f"U{k + 7}.GND", f"U{k + 7}.EPAD"], 2, "down")
    # Vref_B and EN from +5V_MX through 200k (the v2's: each group a voltage domain of its own)
    ry = CH_Y + 10.8                    # two rows of 0402 under the LSF0108, 1.1 mm apart
    R(s, f"R{k + 11}", "200k", "+5V_MX", p + "VREFB", size="0402", pcb=P(bx - 1.65, ry, 90), sch=at(162, 122))
    C(s, f"C{k + 5}", "100n", p + "VREFB", "GND", size="0402", pcb=P(bx - 0.55, ry, 90), sch=at(162, 130))
    s.wire(f"R{k + 11}.2", f"C{k + 5}.1")
    # VREF / 2 to the co-processor's ADC through 100k (the v2's divider: an unwired VREF stays ≈ 0.4 V)
    R(s, f"R{k + 12}", "10k", p + "VREF", f"CP_VREF{n}", size="0402", pcb=P(bx + 0.55, ry, 90), sch=at(180, 122))
    R(s, f"R{k + 13}", "10k", f"CP_VREF{n}", "GND", size="0402", pcb=P(bx + 1.65, ry, 90), sch=at(180, 130))
    s.wire(f"R{k + 12}.2", f"R{k + 13}.1")
    R(s, f"R{k + 15}", "100k", f"CP_VREF{n}", f"CP_ADC{n}", size="0402", pcb=P(bx - 1.1, ry + 1.95, 90),
      sch=at(196, 136, rot=90))
    s.part(f"#FLG{k + 1}", "power:PWR_FLAG", "PWR_FLAG", "", {"1": p + "VREF"}, in_bom=False, on_board=False,
           sch=at(200, 120))
    s.part(f"#FLG{k + 2}", "power:PWR_FLAG", "PWR_FLAG", "", {"1": p + "VREFB"}, in_bom=False, on_board=False,
           sch=at(212, 120))

    e = (n - 1) // 3
    s.notes_at = (112, 62, 116)
    s.notes = [f"Port {n} = hub port {n}, busid 1-1.{n}; supplied by {v5}.",
               f"INA226 at 0x{INA_HEX[n - 1]:02x}; expander {('U2', 'U6')[e]} (TCA9535, 0x{0x20 + e:02x}).",
               "ILIM 47k: 0.50–0.62 A; the -1 latches off after 7.5 ms in limit, FAULT_N flags it.",
               "INA226 Vbus on the shunt's load-side sense pad (= VBUS).",
               "EN pulled down: the port stays off until the node switches it on.",
               "Pins: P1–P8 → crosspoint X lines (as the DATA ×4 v2's map, a third chip for ports 5–6);",
               "  an unwired VREF stays ≈ 0.4 V, under the LSF0108's 0.65 V: the firmware keeps the port's",
               "  crosspoint switches open while its VREF reads under 0.65 V.",
               f"ESD: VREF through U{k + 8}, RESET_N / BOOT_N through U{k + 9} (flow-through).",
               "VREF: the board's I/O supply, 0.95–3.6 V; a 5 V board with TTL inputs: its own 3.3 V pin.",
               "Source only (Rp from the switched VBUS); a back-feeding source trips the TPS2553 (latched).",
               "The DUT's RESET/BOOT pull-ups ≥ 4.7k: against 1k, the 1k in series stops at ≈ 1.65 V.",
               f"Header: {colour}; left column VREF 1 2 3 4 BOOT, right GND 5 6 7 8 RESET."]


# ------------------------------------------------------------------------------------------ 20 V → 5 V
def power_sheet(b: Board):
    s = b.sheet("Power", "power.kicad_sch", "20 V input, two 5 V converters")
    s.paper = "A2"
    s.frame("VIN: the rack's 20 V from the node (after its reverse protection), a PH 2 on the rear face", 6, 10, 62, 50)
    # through-hole on the rear face, soldered by hand, as J1; its lead comes up behind the board
    part(s, "J3", "ph2v", {"1": "VIN", "2": "GND"}, "VIN", pcb={**P(*VIN_J, 270, "bottom"), "solid": ["1", "2"]},
         sch=at(16, 30, mirror="y", fields=(-2, -6)))
    s.part("#FLG08", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "VIN"}, in_bom=False, on_board=False, sch=at(28, 18))
    # the input's bulk against a hot plug's overshoot (the node's lead is ≈ 50 cm, the converters' ceramics alone ring)
    part(s, "C60", "cap33u50", {"1": "VIN", "2": "GND"}, "33u", pcb=P(*BULK, 90),
         sch=at(40, 30))
    # EN 100k/10k, as the node's: both converters start above 13.5 V and stop below 10.8 V
    R(s, "R50", "100k", "VIN", "BUCK_EN", size="0402", pcb=P(BULK[0] - 2.65, BULK[1] + 7.2, 90), sch=at(29, 41.5))
    R(s, "R51", "10k", "BUCK_EN", "GND", size="0402", pcb=P(BULK[0] - 1.55, BULK[1] + 7.2, 90), sch=at(29, 48.5))
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
        R(s, f"R{r0}", "100k", out, fb, pcb=P(4 + dx, 40.6 + dy, 0), sch=at(x0 + 62, 30))
        R(s, f"R{r0 + 1}", "18k", fb, "GND", pcb=P(4 + dx, 42.2 + dy, 180), sch=at(x0 + 62, 37))
        s.wire(f"R{r0}.2", f"R{r0 + 1}.1")
        s.wire((x0 + 62, 33.5), (x0 + 36, 33.5), (x0 + 36, 25), f"{u}.FB")
        s.part(f"#FLG{9 + i}", "power:PWR_FLAG", "PWR_FLAG", "", {"1": out}, in_bom=False, on_board=False,
               sch=at(x0 + 58, 14))
    testpoints(s, ["TP9", "TP41", "TP42", "TP43"], "Test points (rear face): +5V_A, +5V_B, VIN, GND", 6, 78)
    s.notes_at = (6, 56, 200)
    s.notes = [
        "Two LMR51625 as the bay node's (TI SLUSF64B table 8-1: 4.7 µH FXL0630, 2 × 10 µF + 100 nF in, 3 × 22 µF out).",
        "+5V_A: ports 1–3 and the logic (hub, co-processor, matrix, 3.3 V LDO); +5V_B: ports 4–6.  Never in parallel:",
        "  the power plane's +5V split left / right.  Load: 6 × 0.5 A + 0.25 A logic = 3.25 A; 4 A at the TPS2553s'",
        "  0.62 A limit (A ≤ 2.1 A, B ≤ 1.9 A).",
        "FB 100k/18k: 5.24 V, as the node's.  EN 100k/10k: on above 13.5 V, off below 10.8 V.",
        "VIN from the node's VRACK after its reverse-protection P-FET (node rev. B): no second protection here.",
        "  ≈ 0.95 A at 20 V, 0.7 A at 28 V; a PH contact carries 2 A.",
    ]


# ----------------------------------------------------------------------------------- hub, lead, 3.3 V
def hub_sheet(b: Board):
    s = b.sheet("Hub", "hub.kicad_sch", "Lead, hub, expanders, 3.3 V")
    s.paper = "A2"
    s.frame("Lead from the node's J7 (PH 8, rear face): I²C and INT through an H5VU25UC; pin 8 open", 6, 10, 70, 50)
    # the v2's J1, pin for pin, where the v2 has it; its pin 8 (the node's DUT_5V) is left open: this board makes
    # its own 5 V from VIN (power_sheet())
    part(s, "J1", "ph8t", {"1": "LEAD_INT", "2": "LEAD_SCL", "3": "LEAD_SDA", "4": "GND", "5": "UP_DN",
                           "6": "UP_DP", "7": "GND", "8": None}, "LEAD",
         pcb=P(*LEAD, J1_ROT, "bottom"), sch=at(16, 30, mirror="y", fields=(-2, -6)))
    s.part("#FLG02", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "GND"}, in_bom=False, on_board=False, sch=at(34, 16))
    part(s, "U4", "esd4", {"D1+": "LEAD_SDA", "D1-": "LEAD_SCL", "D2+": "LEAD_INT", "D2-": None, "GND": "GND"},
         pcb=P(LEAD[0] + 2.75, LEAD[1] - 0.6, 90), sch=at(48, 30, fields=(-3, -6)))

    s.frame("3.3 V for the hub, the expanders, the INA226s and the co-processor (AP2114H, SOT-223 on copper)",
            6, 56, 70, 86)
    s.tag("+5V_A", (24, 66), "up")
    s.wire((24, 66), (24, 69), "U3.VI")
    part(s, "U3", "ldo_1a", {"VI": "+5V_A", "VO": "+3V3", "GND": "GND"}, pcb=P(*LDO, 0),
         sch=at(34, 69, fields=(-3, -4)))
    C(s, "C2", "22u", "+5V_A", "GND", size="0805", pcb=P(LDO[0] + 5.6, LDO[1] + 1.8, 90), sch=at(20, 72))
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
    for n in range(1, 7):
        hub[f"USBDN{n}_DP/PRT_DIS_P{n}"] = f"PORT{n}_DP"
        hub[f"USBDN{n}_DM/PRT_DIS_M{n}"] = f"PORT{n}_DN"
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
                                        ("C16", (HX + 0.95, HY + 6.7), 270), ("C14", (HX + 6.05, HY + 0.95), 270),
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
        rarray(s, f"RN{10 + i}", "10k", [(f"EXP{i + 1}_{pin}", "GND") for pin in spare] + [(None, None)] * (4 - len(spare)),
               P(x, y + 7.7, 90), sch=at(224, sy + 16))
        rail(s, "GND", [f"RN{10 + i}.{9 - q}" for q in range(1, len(spare) + 1)], 2, "down")

    s.frame("I²C isolation: open with the board's 3.3 V off (the node's pull-ups can't feed it)", 172, 106, 232, 148)
    for i, (q, r, line, val) in enumerate((("Q1", "R6", "SDA", "4.7k"), ("Q2", "R7", "SCL", "4.7k"),
                                           ("Q3", "R8", "INT", "10k"))):
        y = LEAD[1] + 2.5 + 4.0 * i
        part(s, q, "nfet", {"G": "+3V3", "S": line, "D": "LEAD_" + line}, pcb=P(LEAD[0] + 2.75, y, 90),
             sch=at(186, 118 + 12 * i))
        R(s, r, val, "+3V3", line, size="0402", pcb=P(LEAD[0] + 2.75, LEAD[1] + 13.1 + 1.0 * i, 0),
          sch=at(212, 116 + 12 * i))
    testpoints(s, ["TP7", "TP8", "TP20", "TP21", "TP22", "TP23", "TP24", "TP25", "TP26", "TP27", "TP28"],
               "Test points (rear face, bare pads, not in the BOM): +3V3, the hub's reset and 1.8 V, the lead's "
               "I²C and INT, GND", 6, 136, per_row=11)
    s.notes_at = (6, 108, 160)
    s.notes = [
        "Hub reset: U5 (MAX809S, 2.93 V, ≥ 150 ms, push-pull) on RESET_N (errata DS80000628A, Module 2).",
        "Hub: CFG_SEL[2:0] = 110 (internal default configuration, strap options disabled: DS00001598C Table 5-2),",
        "  as the DATA ×4 v2's; all seven downstream ports used.",
        "Hub port n = USB-C n (busid 1-1.n) for n = 1–6; port 7 = the co-processor.",
        "Expanders: TCA9535 U2 0x20 (ports 1–3), U6 0x21 (ports 4–6, the mark on P14).  Each port: RESET, BOOT, EN,",
        "  FAULT_N (port 1 on P00–P03, 2 on P04–P07, 3 on P10–P13).  Inputs at power-up: the EN pull-downs keep every",
        "  port off until the node writes; the spare pins set as outputs, low, by the firmware.",
        "INT (J1.1 → the node's IO4): both expanders' INT and the six INA226 ALERTs, open drain, wired-OR, through Q3.",
        "I²C: TCA9535 0x20 / 0x21, INA226 0x41 / 0x43 / 0x44 / 0x45 / 0x47 / 0x4C, TCA9534A 0x38; the node's INA226 0x40.",
        "J1 pin 8 (the node's switched +5V) is open: the ports and the logic take their 5 V from VIN (sheet Power).",
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
    part(s, "FB1", "fb600", {"1": "+5V_A", "2": "+5V_MX"}, pcb=P(NINV[0] + 5.0, NINV[1] + 0.5, 0), sch=at(124, 18))
    s.wire("FB1.1", ("FB1.1", -3, 0))
    s.tag("+5V_A", ("FB1.1", -3, 0), "left")
    s.wire("FB1.2", ("FB1.2", 3, 0))
    s.tag("+5V_MX", ("FB1.2", 3, 0), "right")
    s.part("#FLG06", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+5V_MX"}, in_bom=False, on_board=False,
           sch=at(132, 14))
    part(s, "U9", "tps60400", {"IN": "+5V_MX", "OUT": "-5V", "C_{FLY+}": "CP_FLYP", "C_{FLY-}": "CP_FLYN", "GND": "GND"},
         pcb=P(*NINV, 0), sch=at(150, 30, fields=(-4, -6)))
    C(s, "C26", "1u", "CP_FLYP", "CP_FLYN", size="0402", pcb=P(NINV[0], NINV[1] + 2.8, 0), sch=at(170, 36))
    C(s, "C27", "1u", "+5V_MX", "GND", size="0402", pcb=P(NINV[0] - 3.05, NINV[1] + 0.05, 180), sch=at(132, 34))
    C(s, "C28", "1u", "-5V", "GND", size="0402", pcb=P(NINV[0] - 3.05, NINV[1] - 1.0, 180), sch=at(186, 36))

    s.frame("The node's matrix expander (TCA9534A, 0x38): the crosspoints and the co-processor's RUN / BOOTSEL",
            114, 58, 228, 100)
    part(s, "U10", "tca9534", {"VDD": "+3V3", "GND": "GND", "A0": "GND", "A1": "GND", "A2": "GND", "SCL": "SCL",
                               "SDA": "SDA", "~{INT}": None, "P0": "MX_DAT", "P1": "MX_CK", "P2": "MX_STB1",
                               "P3": "MX_STB2", "P4": "MX_RST", "P5": "CP_RUN", "P6": "CP_BOOT_N", "P7": "MX_STB3"},
         pcb=P(*MX_EXP, 90), sch=at(160, 84, fields=(-10, -8)))
    rail_v(s, "GND", ["U10.A0", "U10.A1", "U10.A2"], -2, "down")
    C(s, "C29", "100n", "+3V3", "GND", size="0402", pcb=P(MX_EXP[0], MX_EXP[1] - 4.9, 0), sch=at(140, 74))
    R(s, "R20", "10k", "+3V3", "MX_RST", size="0402", pcb=P(MX_EXP[0], MX_EXP[1] + 4.9, 0), sch=at(190, 76))
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
    # VREF 1–6 / 2 on GPIO40–45 (ADC0–5), the ±5 V rails on GPIO46–47: the ADC full
    for n in range(1, 7):
        gp[f"GPIO{39 + n}/ADC{n - 1}"] = f"CP_ADC{n}"
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
               P(cx + 7.4, cy + 9.5 + 2.6 * j, 0), sch=at(134 + 12 * j, 124))
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
               "GPIO40–45 = VREF 1–6 / 2 (through 100k); GPIO46 = +5V_MX × 47/147;",
               "  GPIO47 = 3.3 V − (3.3 + 5) × 10/110 from −5 V (2.55 V nominal).  The ADC's eight inputs all used.",
               "RUN pulled up, BOOTSEL (QSPI_SS) through 1k: both held by the node (TCA9534A), open drain.",
               "USB on the hub's port 7 (Full Speed, 22 Ω).",
               "Core regulator: Raspberry Pi's Minimal R4 block turned 180°; L1's dot (pad 1) on +1V1, not VREG_LX.",
               "C47 (DVDD pin 32, furthest from the regulator) 4.7 µF; no copper under LX / L1 (In1, In2, B.Cu)."]


# ---------------------------------------------------------------------------------------------- board
def logic_only(b: Board) -> list[str]:
    """The parts the base DATA-6x leaves off: the matrix and co-processor sheets whole, and per port its pin
    chain (the three H5VU25UC on P1–P8 and VREF, the 100 Ω arrays, the LSF0108, its Vref_B 200k and 100 nF, the
    VREF divider and its 100k to the ADC).  The RESET/BOOT ESD stays."""
    refs = [p.ref for p in b.parts.values() if p.sheet and p.sheet.name in ("Matrix", "Co-processor")]
    for n in range(1, 7):
        k = 100 * n
        refs += [f"U{k + 5}", f"U{k + 6}", f"RN{k + 1}", f"RN{k + 2}", f"U{k + 7}", f"R{k + 11}", f"C{k + 5}",
                 f"R{k + 12}", f"R{k + 13}", f"U{k + 8}", f"R{k + 15}"]
    return sorted(r for r in refs if r in b.parts and b.parts[r].in_bom and not r.startswith("#"))


def board() -> Board:
    b = Board("data-port-x6", "DATA ×6", "1.0",
              comments=["A porte-revues bay's drawer board: six USB-C behind a hub, 48 switchable pins on 8 buses, "
                        "a logic analyzer (hw-testing-rack)",
                        "Generated from electronics/data-port-x6/design.py — edit the Python, then regenerate"])
    b.root_paper, b.root_buses = "A2", True
    b.root_notes = [
        "DATA ×6 v1.0 — USB2517I hub (7 ports), six USB-C each with a TPS2553-1, an INA226 and ESD, two TCA9535",
        "  for EN/FAULT/RESET/BOOT, an AP2114H 3.3 V; two LMR51625 make the ports' 5 V from VIN (20 V, PH 2).",
        "Pins: 48 on three CH446Q (±5 V), LSF0108 per port, an RP2354B analyzer on hub port 7, a TCA9534A for the",
        "  matrix and the co-processor's RUN/BOOTSEL.  Standing behind the port wall, one face assembled.",
        "Headers: six 2 × 6 blocks at the top, one colour per port (red, yellow, green, blue, white, black).",
        "Lead pinout here: 1 INT · 2 SCL · 3 SDA · 4 GND · 5 D− · 6 D+ · 7 GND · 8 (open) — the DATA ×4 v2's lead.",
        "I²C: TCA9535 0x20 / 0x21, INA226 0x41 / 0x43 / 0x44 / 0x45 / 0x47 / 0x4C, TCA9534A 0x38; the node's 0x40.",
        "Assembled as DATA-6x-logic (as drawn) or DATA-6x (BOM/CPL '-base': the matrix, the co-processor and the",
        "  ports' pin chains not fitted).",
        "Rails: VIN 20 V (13.5–28 V; on above 13.5 V), ≤ 0.95 A at 20 V · +5V_A 5.24 V, ≤ 2.1 A (ports 1–3 at their",
        "  0.62 A limit and the logic) · +5V_B 5.24 V, ≤ 1.9 A (ports 4–6) · PORTn_VBUS 5.1–5.24 V, 0.50–0.62 A limit ·",
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

    outline = [(0, 0, 1.0), (W, 0, 1.0), (W, H, 1.0)]
    for x0, x1, top in reversed(NOTCHES):
        outline += [(x1, H, 0), (x1, top, 0.5), (x0, top, 0.5), (x0, H, 0)]
    outline += [(0, H, 1.0)]
    pwr = "In2.Cu"
    b.pcb = {
        "size": (W, H), "layers": LAYERS, "outline": outline, "passes": 80,
        "min_track": 0.09, "min_clearance": 0.1, "hole_clearance": 0.2,
        "inner": [("In1.GND", "power"), ("In2.PWR", "power")],
        "stackup": "JLC04161H-7628", "finish": "ENIG",
        "edge_parts": [],
        "defer_pours": False,
        "fanout_nets": {"GND": ("In1.Cu", 0.5, 0.3, 0.25)},
        "plane_nets": {},
        "power_nets": {"GND": 1, "VIN": 2, "+5V_A": 2, "+5V_B": 2, "+5V_MX": 2, "-5V": 2, "+3V3": 2, "+3V3_CP": 2,
                       "+1V1": 2, "PORT?_VBUS": 2, "PORT?_5V_SW": 2},
        "stitch": 4.0,
        "edge_fence": {"pitch": 5.0, "inset": 0.9},
        "zones": [{"layer": "In1.Cu", "net": "GND"}],
        "tracks": [], "vias": [],
        "keepouts": [{"name": f"edge{i}", "poly": [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]}
                     for i, (x0, y0, x1, y1) in enumerate((
                         (0, 0, W, 0.35), (W - 0.35, 0, W, H), (0, H - 0.35, W, H), (0, 0, 0.35, H),
                         *((x0 - 0.35, top - 0.35, x1 + 0.35, H) for x0, x1, top in NOTCHES)))],
        "variants": {"base": {"dnp": logic_only(b)}},
        "texts": [
            {"text": "DATA ×6 v1.0", "x": 50.0, "y": 78.0, "size": 0.8},
            # each block's port number under it, and the columns' names once, right of the six (read with the
            # jumpers in: the left column's name, then the right's)
            *({"text": str(n), "x": BLK_X[n - 1], "y": BLK_Y + 8.9, "size": 1.2} for n in range(1, 7)),
            *({"text": f"{a} {c}", "x": BLK_X[-1] + 6.6, "y": BLK_Y - 6.35 + 2.54 * i, "size": 0.8}
              for i, (a, c) in enumerate(LEGEND)),
            *({"text": name, "x": x, "y": y + d / 2 + 0.75, "size": 0.8, "layer": "B.SilkS"}
              for net, name, d, x, y in TPS.values()),
            *({"text": name, "x": SWD_HDR[0] + 2.54 * i, "y": SWD_HDR[1] + (-2.1 if i % 2 == 0 else 2.1), "size": 0.8}
              for i, (_, name) in enumerate(SWD_PINS)),
        ],
    }
    return b


USB_W = 0.25
NETCLASSES = [
    {"name": "Default", "clearance": 0.1, "track_width": 0.127, "via_diameter": 0.5, "via_drill": 0.3},
    {"name": "Supply", "clearance": 0.1, "track_width": 0.25, "via_diameter": 0.5, "via_drill": 0.3,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 5,
     "_patterns": ["*+3V3_CP", "*+1V1", "-5V", "+5V_MX", "+3V3", "*HUB_1V8", "*HUB_1V8PLL", "*CP_VREG_AVDD"]},
    {"name": "Power", "clearance": 0.15, "track_width": 0.6, "via_diameter": 0.6, "via_drill": 0.3,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 1,
     "_patterns": ["+5V_A", "+5V_B", "VIN", "*BUCK?_SW"]},
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
