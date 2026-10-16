"""Bay node — one per bay: ESP32-S3 USB/IP host for the board under test (DUT).

Functions
  * 24 V bus in/out (JST PH, daisy-chained bay to bay), reverse-polarity
    P-FET, TVS, LMR51635 synchronous buck to 5 V / 3.5 A, 3.3 V LDO for the logic.
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
  * AUX (JST-SH 6): UART TX/RX + open-drain RESET/BOOT lines to the DUT.
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
PH_MOUTH = 4.9                # JST PH side-entry: pin row → mouth (the board edge)


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


def board() -> Board:
    b = Board("bay-node", "Bay node", "0.2",
              comments=["ESP32-S3 USB/IP host for one bay of the hw-testing-rack shelf",
                        "Generated from electronics/bay-node/design.py — edit the Python, then regenerate",
                        "24 V in · 5 V/1.4 A switched DUT port · USB 2.0 muxes · INA226 · AUX UART/RST/BOOT"])
    b.root_notes = [
        "Bay node — one per bay.  Sheets:",
        "  Power: 24 V bus (JST PH daisy chain), reverse protection, LMR51635 buck to 5 V, AMS1117 3.3 V",
        "  MCU: ESP32-S3-MINI-1, reset/boot, status LED, UART pads",
        "  USB: front PC port, DUT port, two FSUSB42 muxes + OR gate (classic / USB-IP / service modes)",
        "  DUT power & AUX: TPS2553 switch → shunt → DUT_5V, INA226 monitor, AUX UART/RESET/BOOT, camera 5 V",
        "",
        "Mode truth table:  SERVICE=0, PC unplugged → DUT↔ESP32 (USB/IP)",
        "                   SERVICE=0, PC plugged   → DUT↔PC (classic), ESP32 still controls DUT_5V/AUX",
        "                   SERVICE=1               → PC↔ESP32 (flash/console), DUT data disconnected",
        "GPIO firmware can also force classic mode (MUX_FORCE_PC).",
    ]
    pw = 2 * PWR_Y - 1          # J1/J2 pin 1 sits 1 mm off the connector centre
    # the 24 V daisy chain on In2: J1 pin 1 → J2 pin 1 through both connectors' through-holes, with a
    # bump under Q1 where two vias at the edge of its drain tab drop into it
    bus = [(0.5, PWR_Y - 3.2), (13.0, PWR_Y - 3.2), (13.0, 57.4), (17.0, 57.4), (17.0, PWR_Y - 3.2),
           (63.5, PWR_Y - 3.2), (63.5, PWR_Y + 2.6), (0.5, PWR_Y + 2.6)]
    b.pcb = {
        "size": (W, H), "layers": CFG["layers"], "corner_radius": 2.0, "passes": 60,
        # 4 layers, symmetric: S+GND / GND / PWR / S+GND.  In1 is a solid GND plane, In2 the power
        # layer (+5V pour, +3V3 under the module, the 24 V bus strip); the router may still use In2
        # for signals, its pours are added after routing.  Every pour connects pads through thermal
        # reliefs (pcbgen.py), so no GND pad out-heats its partner in reflow.  The outer GND pours
        # stay: without them every SMD GND pad needs its own via, and on 64 × 80 mm Freerouting then
        # leaves ~25 connections unrouted.  stitch_gnd() ties the outer pours to In1.
        "inner": [("In1.GND", "power"), ("In2.PWR", "mixed")],
        "defer_pours": ["In2.Cu"],
        "stitch": 4.0,
        # GND pads the router tends to wall in (U9's middle pin, U5's corner pin between the SVC
        # line and the ESP pair): reserve a dog-bone via outside the package before routing
        "fanout": [("U9", "2"), ("U5", "10"), ("U6", "5")],
        "zones": [
            {"layer": "In1.Cu", "net": "GND"},
            {"layer": "F.Cu", "net": "GND"},
            {"layer": "B.Cu", "net": "GND"},
            {"layer": "In2.Cu", "net": "+5V"},
            {"layer": "In2.Cu", "net": "+3V3", "priority": 1, "poly": [(18, 0.5), (46, 0.5), (46, 23), (18, 23)]},
            {"layer": "In2.Cu", "net": "24V_BUS", "priority": 2, "defer": False, "poly": bus},
            # buck hot loop (TI SLUSF64B §8.4): top-side islands joining CIN, U1 and COUT
            {"layer": "F.Cu", "net": "GND", "connection": "solid", "name": "buck-gnd", "priority": 3,
             "poly": [(8.05, 34.5), (10.1, 34.5), (10.1, 36.2), (11.9, 36.2), (11.9, 40.3), (20.6, 40.3), (20.6, 44.4),
                      (8.05, 44.4)]},
            {"layer": "F.Cu", "net": "+5V", "connection": "solid", "name": "buck-5v", "priority": 3,
             "poly": [(12.8, 38.1), (17.3, 38.1), (17.3, 30.6), (21.0, 30.6), (21.0, 39.9), (12.8, 39.9)]},
            {"layer": "F.Cu", "net": "+24V", "connection": "solid", "name": "buck-vin", "priority": 3,
             "poly": [(5.6, 34.5), (7.8, 34.5), (7.8, 42.7), (5.6, 42.7)]},
            # under the ESP32 module (Espressif's layout guide): its centre pads and GND pins on one
            # top-side island, stitched to In1 around the centre pads
            {"layer": "F.Cu", "net": "GND", "name": "esp-gnd", "priority": 3,
             "poly": [(24.7, 5.6), (39.3, 5.6), (39.3, 16.4), (24.7, 16.4)]},
        ],
        # GND vias from the hot-loop island down to the In1 plane, next to the capacitors' GND ends
        "vias": [("GND", 11.0, 36.9), ("GND", 11.0, 39.4), ("GND", 11.2, 43.4), ("GND", 13.0, 43.6),
                 ("GND", 15.25, 43.6), ("GND", 17.75, 43.6), ("GND", 20.0, 43.6),
                 *[("GND", x, 8.6) for x in (28, 30, 32, 34, 36)],
                 *[("GND", x, y) for x in (28.6, 35.4) for y in (12.2, 14.2)],
                 ("GND", 30.35, 16.0), ("GND", 33.65, 16.0),
                 ("24V_BUS", 14.0, 58.1), ("24V_BUS", 16.0, 58.1)],
        # ESP32 antenna: no copper on any layer under/around the antenna (module top 5 mm + edge)
        "keepouts": [
            {"name": "antenna", "poly": [(9.3, -0.1), (54.7, -0.1), (54.7, 5.4), (9.3, 5.4)]},
            # the 24 V bus strip on In2 carries the daisy chain: no other net's track may cut it
            # (vias may cross it), and the router counts on it to join J1 and J2
            {"name": "bus-strip", "layers": ["In2.Cu"], "tracks_only": True, "poly": bus},
        ],
        "texts": [
            {"text": "hw-testing-rack · bay node v0.2", "x": 29, "y": 26.6, "size": 0.8},
            {"text": "PC", "x": 32, "y": 71.2, "size": 0.9},
            {"text": "SVC", "x": 50, "y": 73.6, "size": 0.8},
            {"text": "24V IN", "x": 5.5, "y": PWR_Y - 5.0, "size": 0.8},
            {"text": "24V OUT", "x": 58.0, "y": PWR_Y - 5.0, "size": 0.8},
            {"text": "DUT", "x": 57.5, "y": 17, "size": 0.8},
            {"text": "AUX", "x": 57.5, "y": 34.2, "size": 0.8},
            {"text": "CAM", "x": 55.5, "y": 11, "size": 0.8},
        ],
    }

    # ------------------------------------------------------------------ power
    s = b.sheet("Power", "power.kicad_sch", "24 V input, 5 V buck, 3.3 V LDO")
    s.frame("24 V bus in / out (daisy chain, JST PH) and input protection", 6, 6, 52, 27)
    part(s, "J1", "ph2", {"1": "24V_BUS", "2": "GND"}, "24V IN", pcb=P(PH_MOUTH, pw - PWR_Y, 270),
         sch=at(10, 12, mirror="y", fields="left"))
    part(s, "J2", "ph2", {"1": "24V_BUS", "2": "GND"}, "24V OUT", pcb=P(W - PH_MOUTH, PWR_Y + 1, 90),
         sch=at(10, 20, mirror="y", fields="left"))
    s.part("#FLG01", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "24V_BUS"}, in_bom=False, on_board=False, sch=at(21, 12, fields=(-3.8, -2.6)))
    s.part("#FLG02", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "GND"}, in_bom=False, on_board=False, sch=at(16, 21, fields=(0.6, -2.6)))
    s.part("#FLG03", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+24V"}, in_bom=False, on_board=False, sch=at(45, 12, fields=(-3.8, -2.6)))
    s.part("#FLG04", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+5V"}, in_bom=False, on_board=False, sch=at(77, 46, fields=(-3.8, -2.6)))
    part(s, "Q1", "pfet", {"G": "Q1_GATE", "D": "24V_BUS", "S": "+24V"}, pcb=P(15, 56, 90),
         sch=at(24, 13, rot=90, fields=(-6.5, 3)))
    part(s, "D1", "zener12", {"K": "+24V", "A": "Q1_GATE"}, pcb=P(15, 64.5, 180), sch=at(29, 16.5, rot=270))
    R(s, "R1", "100k", "Q1_GATE", "GND", pcb=P(15, 67.3, 0), sch=at(24, 20.5))
    part(s, "D2", "tvs33", {"K": "+24V", "A": "GND"}, pcb=P(22, 58, 90), sch=at(35, 16.5, rot=270))
    part(s, "C1", "cap100u50", {"1": "+24V", "2": "GND"}, "100u/50V", pcb=P(6, 49, 90), sch=at(41, 16.5))
    s.wire("J1.1", (16, 12), "Q1.D")
    s.wire("J2.1", (16, 20), (16, 12))
    s.wire("J1.2", (14, 13))
    s.tag("GND", (14, 13), "down")
    s.wire("J2.2", (16, 21))
    s.tag("GND", (14, 21), "down")
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
    part(s, "U2", "ldo", {"VI": "+5V", "VO": "+3V3", "GND": "GND"}, pcb=P(44, 30, 0), sch=at(102, 42, fields=(-3, -3.5)))
    C(s, "C11", "10u", "+5V", "GND", size="0805", pcb=P(44, 36.5, 0), sch=at(95, 43.5))
    C(s, "C12", "22u", "+3V3", "GND", size="1206", pcb=P(38.5, 36.5, 90), sch=at(109, 43.5))
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

    # ------------------------------------------------------------------ MCU
    m = b.sheet("MCU", "mcu.kicad_sch", "ESP32-S3 module")
    m.frame("Reset and boot", 6, 6, 40, 30)
    part(m, "SW1", "button", {"1": "EN", "2": "GND"}, "RESET", pcb=P(47, 11, 0), sch=at(14, 15, rot=270))
    R(m, "R6", "10k", "+3V3", "EN", pcb=P(21.5, 17.3, 0), sch=at(22, 10.5))
    C(m, "C15", "1u", "EN", "GND", pcb=P(21.5, 19.3, 0), sch=at(27, 14.5))
    m.wire("SW1.1", (32, 13))
    m.wire("R6.2", (22, 13))
    m.tag("EN", (32, 13), "right")
    part(m, "SW2", "button", {"1": "BOOT", "2": "GND"}, "BOOT", pcb=P(47, 18, 0), sch=at(14, 24, rot=270))
    R(m, "R7", "10k", "+3V3", "BOOT", pcb=P(42, 12, 90), sch=at(22, 19.5))
    m.wire("SW2.1", (32, 22))
    m.wire("R7.2", (22, 22))
    m.tag("BOOT", (32, 22), "right")

    m.frame("UART test pads", 6, 31, 40, 45)
    for i, (net, y) in enumerate((("U0TX", 35), ("U0RX", 37), ("GND", 39), ("+3V3", 42))):
        part(m, f"TP{i + 1}", "testpad", {"1": net}, net, pcb=P(33 + 2.5 * i, 24, 0), in_bom=False,
             sch=at(12, y, rot=90, fields="left"))
    m.wire("TP3.1", (15, 39), (15, 40))
    m.tag("GND", (15, 40), "down")
    m.wire("TP4.1", (18, 42), (18, 41))
    m.tag("+3V3", (18, 41), "up")

    m.frame("ESP32-S3-MINI-1 (PCB antenna at the board's rear edge: no copper under it, any layer)", 46, 6, 112, 56)
    part(m, "U3", "esp32s3", {
        "3V3": "+3V3", "GND": "GND", "EN": "EN", "IO0": "BOOT",
        "USB_D-": "ESP_DN", "USB_D+": "ESP_DP",
        "IO4": "PC_DET", "IO5": "SVC", "IO6": "DUT_EN", "IO7": "DUT_FLT_N",
        "IO8": "I2C_SDA", "IO9": "I2C_SCL", "IO10": "MUX_FORCE_PC",
        "IO11": "AUX_RST_CTL", "IO12": "AUX_BOOT_CTL", "IO13": "LED_DIN", "IO14": "INA_ALERT_N",
        "IO17": "AUX_TX", "IO18": "AUX_RX", "TXD0": "U0TX", "RXD0": "U0RX",
    }, pcb=P(32, 10.5, 0), sch=at(80, 38, fields=(-14, -14)))
    C(m, "C13", "22u", "+3V3", "GND", size="1206", pcb=P(21, 9, 90), sch=at(96, 23.5))
    C(m, "C14", "100n", "+3V3", "GND", pcb=P(21, 13.5, 90), sch=at(100, 23.5))
    m.wire("U3.3V3", (80, 22), "C14.1")
    m.wire("U3.IO13", (66, 43))
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
    m.note("GPIO map: IO4 PC_DET · IO5 SVC · IO6 DUT_EN · IO7 DUT_FLT_N · IO8/9 I2C · IO10 MUX_FORCE_PC ·")
    m.note("IO11 AUX_RST · IO12 AUX_BOOT · IO13 LED · IO14 INA_ALERT · IO17/18 UART1 (AUX) · IO19/20 USB (OTG/JTAG).")
    m.note("Strapping pins IO0/IO3/IO45/IO46 are not used for I/O.  USB is full-speed only (one internal PHY).")

    # ------------------------------------------------------------------ USB
    u = b.sheet("USB", "usb.kicad_sch", "USB ports and data-path muxes")
    u.frame("Front PC port: USB-C sink (Rd 5.1k on CC), VBUS only sensed", 6, 6, 56, 52)
    part(u, "J3", "usbc", {"VBUS": "PC_VBUS", "GND": "GND", "CC1": "PC_CC1", "CC2": "PC_CC2", "D+": "PC_DP",
                           "D-": "PC_DN", "SBU1": None, "SBU2": None, "SHIELD": "GND"}, "PC", pcb=P(32, 76.6, 0),
         sch=at(14, 28, fields=(-4, -9)))
    u.wire("J3.A7", (22, 27), (22, 28), "J3.B7")
    u.wire("J3.A6", (23, 29), (23, 30), "J3.B6")
    part(u, "U4", "esd", {"I/O1": "PC_DN", "I/O2": "PC_DP", "VBUS": "+5V", "GND": "GND"}, pcb=P(32, 69.5, 0),
         sch=at(30, 28, fields=(1.5, 3.5)))
    u.wire((22, 28), "U4.1")
    u.wire((23, 29), "U4.3")
    R(u, "R11", "10k", "PC_VBUS", "PC_DET", pcb=P(41, 70, 0), sch=at(37.5, 22, rot=90))
    R(u, "R12", "20k", "PC_DET", "GND", pcb=P(41, 67.6, 0), sch=at(42, 23.5))
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
         "MUX_PC", pcb=P(32, 63.5, 0), sch=at(76, 26, fields=(1.5, 4.5)))
    C(u, "C17", "100n", "+3V3", "GND", pcb=P(27.5, 63.5, 90), sch=at(68, 17.5))
    u.wire("U5.VCC", (76, 16), "C17.1")
    u.tag("+3V3", (76, 16), "up")
    part(u, "U6", "mux", {"VCC": "+3V3", "GND": "GND", "D+": "DUT_DP", "D-": "DUT_DN", "HSD1+": "ESP_DP",
                          "HSD1-": "ESP_DN", "HSD2+": "PCPATH_DP", "HSD2-": "PCPATH_DN", "SEL": "MUX_SEL",
                          "~{OE}": "SVC"}, "MUX_DUT", pcb=P(51, 39, 0), sch=at(104, 26, mirror="y", fields=(1.5, 4.5)))
    C(u, "C18", "100n", "+3V3", "GND", pcb=P(51, 42.8, 0), sch=at(112, 17.5))
    u.wire("U6.VCC", (104, 16), "C18.1")
    u.wire("U6.SEL", (115, 28))
    u.tag("MUX_SEL", (115, 28), "right")
    u.tag("+3V3", (104, 16), "up")

    u.frame("DUT port: USB-C source (Rp 22k → 1.5 A); DUT_5V comes switched from the DUT power sheet", 106, 40, 160, 72)
    part(u, "J4", "usbc", {"VBUS": "DUT_5V", "GND": "GND", "CC1": "DUT_CC1", "CC2": "DUT_CC2", "D+": "DUT_DP",
                           "D-": "DUT_DN", "SBU1": None, "SBU2": None, "SHIELD": "GND"}, "DUT",
         pcb=P(60.4, CFG["right"]["dut"], 90), sch=at(150, 58, mirror="y", fields=(1, -9)))
    u.wire("J4.A7", (142, 57), (142, 58), "J4.B7")
    u.wire("J4.A6", (141, 59), (141, 60), "J4.B6")
    part(u, "U8", "esd", {"I/O1": "DUT_DN", "I/O2": "DUT_DP", "VBUS": "+5V", "GND": "GND"}, pcb=P(51, 33, 0),
         sch=at(134, 58, fields=(1.5, 3.5)))
    u.wire("U8.6", (142, 58))
    u.wire("U8.4", (141, 59))
    R(u, "R14", "22k", "DUT_5V", "DUT_CC1", pcb=P(53, 27.6, 90), sch=at(117.5, 50, rot=90))
    R(u, "R15", "22k", "DUT_5V", "DUT_CC2", pcb=P(53, 21, 90), sch=at(117.5, 53, rot=90))
    u.wire((112, 50), "R14.1")
    u.wire((114, 50), (114, 53), "R15.1")
    u.tag("DUT_5V", (112, 50), "left")

    u.frame("Mode logic: MUX_SEL = PC_DET OR MUX_FORCE_PC; SERVICE switch", 6, 58, 84, 86)
    part(u, "U7", "or", {"1": "PC_DET", "2": "MUX_FORCE_PC", "3": "GND", "4": "MUX_SEL", "5": "+3V3"},
         pcb=P(44, 63, 0), sch=at(40, 74, fields=(-6, -5)))
    C(u, "C19", "100n", "+3V3", "GND", pcb=P(45.3, 66.8, 0), sch=at(46, 67.5))
    u.wire("U7.5", (40, 66), "C19.1")
    u.tag("+3V3", (40, 66), "up")
    R(u, "R13", "100k", "MUX_FORCE_PC", "GND", pcb=P(44, 59.6, 0), sch=at(28, 77.5))
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
    C(d, "C20", "100n", "+5V", "GND", pcb=P(40.5, 43, 90), sch=at(22, 30.5))
    part(d, "U9", "vbus_sw", {"IN": "+5V", "GND": "GND", "EN": "DUT_EN", "~{FAULT}": "DUT_FLT_N", "ILIM": "DUT_ILIM",
                              "OUT": "DUT_5V_SW"}, pcb=P(44, 46, 0), sch=at(40, 30, fields=(-4, -4)))
    R(d, "R16", "18k", "DUT_ILIM", "GND", pcb=P(40.5, 46.5, 90), sch=at(31, 33.5))
    d.wire("U9.ILIM", "R16.1")
    R(d, "R17", "100k", "+3V3", "DUT_EN", pcb=P(40.5, 50.2, 90), sch=at(26, 35.5))
    d.wire("U9.EN", (28, 31), (28, 38), (16, 38))
    d.wire("R17.2", (26, 38))
    d.tag("DUT_EN", (16, 38), "left")
    R(d, "R18", "10k", "+3V3", "DUT_FLT_N", pcb=P(47.6, 50.2, 90), sch=at(52, 35.5))
    d.wire("U9.~{FAULT}", (48, 31), (48, 38), (55, 38))
    d.wire("R18.2", (52, 38))
    d.tag("DUT_FLT_N", (55, 38), "right")
    part(d, "R19", "shunt50m", {"1": "DUT_5V_SW", "2": "DUT_5V"}, "50m", pcb=P(44, 51, 0), sch=at(62, 33.5))
    d.wire("U9.OUT", (62, 29), "R19.1")
    d.wire("R19.2", (62, 40), (100, 40))
    d.tag("DUT_5V", (100, 40), "right")
    C(d, "C21", "22u", "DUT_5V", "GND", size="1206", pcb=P(49, 46, 90), sch=at(96, 41.5))
    part(d, "U10", "ina226", {"VS": "+3V3", "GND": "GND", "A0": "GND", "A1": "GND", "SDA": "I2C_SDA",
                              "SCL": "I2C_SCL", "~{Alert}": "INA_ALERT_N", "Vin+": "DUT_5V_SW", "Vin-": "DUT_5V",
                              "Vbus": "DUT_5V"}, pcb=P(44, 56, 0), sch=at(74, 31, fields=(-10, -7)))
    d.wire((62, 30), (66, 30), (66, 32), "U10.Vin+")
    d.wire((62, 37), (67, 37), (67, 33), "U10.Vin-")
    d.wire("U10.A1", (80, 28), (80, 29), "U10.A0")
    d.tag("GND", (80, 29), "right")
    C(d, "C22", "100n", "+3V3", "GND", pcb=P(49, 56, 90), sch=at(84, 25.5))
    d.wire("U10.VS", (74, 24), "C22.1")
    d.tag("+3V3", (74, 24), "up")
    d.text("I2C pull-ups", 103, 16.2, 1.27, True)
    d.tag("+3V3", (100, 18), "up")
    d.wire((100, 18), (116, 18), net="+3V3")
    for ref, val, x, net, xy in (("R21", "4.7k", 100, "I2C_SDA", (37.6, 48)), ("R22", "4.7k", 108, "I2C_SCL", (37.6, 51.6)),
                                 ("R20", "10k", 116, "INA_ALERT_N", (37.6, 56))):
        R(d, ref, val, "+3V3", net, pcb=P(*xy, 90), sch=at(x, 20.5))
        d.wire((x, 18), f"{ref}.1")
        d.wire(f"{ref}.2", (x, 23), (x + 1, 23))
        d.tag(net, (x + 1, 23), "right")

    d.frame("AUX: UART + open-drain RESET / BOOT towards the DUT (JST SH 6)", 68, 48, 112, 86)
    part(d, "J5", "sh6", {"1": "GND", "2": "AUX_VREF", "3": "AUX_TX_R", "4": "AUX_RX_R", "5": "AUX_RST_N",
                          "6": "AUX_BOOT_N", "MP": "GND"}, "AUX", pcb=P(60.8, CFG["right"]["aux"], 90),
         sch=at(106, 64, fields=(1, -5)))
    R(d, "R23", "10", "+3V3", "AUX_VREF", pcb=P(57.6, 47.4, 0), sch=at(90.5, 54, rot=90))
    R(d, "R24", "1k", "AUX_TX", "AUX_TX_R", pcb=P(57, 33.6, 0), sch=at(90.5, 58, rot=90))
    R(d, "R25", "1k", "AUX_RX", "AUX_RX_R", pcb=P(54.6, 30.8, 90), sch=at(90.5, 62, rot=90))
    d.wire("J5.2", (98, 63), (98, 54), "R23.2")
    d.wire("R23.1", (87, 54), (87, 52))
    d.tag("+3V3", (87, 52), "up")
    d.wire("J5.3", (97, 64), (97, 58), "R24.2")
    d.wire("J5.4", (96, 65), (96, 62), "R25.2")
    part(d, "Q2", "nfet", {"G": "AUX_RST_CTL", "S": "GND", "D": "AUX_RST_N"}, pcb=P(55, 50.4, 0), sch=at(86, 69))
    part(d, "Q3", "nfet", {"G": "AUX_BOOT_CTL", "S": "GND", "D": "AUX_BOOT_N"}, pcb=P(55, 54.2, 0), sch=at(86, 79))
    R(d, "R26", "100k", "AUX_RST_CTL", "GND", pcb=P(51.6, 50.4, 90), sch=at(81, 70.5))
    R(d, "R27", "100k", "AUX_BOOT_CTL", "GND", pcb=P(51.6, 54.2, 90), sch=at(81, 80.5))
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
    part(d, "F1", "pptc500", {"1": "+5V", "2": "CAM_5V"}, "0.5A", pcb=P(54.5, 15.5, 90), sch=at(126, 54, rot=90))
    part(d, "J6", "ph2", {"1": "CAM_5V", "2": "GND"}, "CAM", pcb=P(CFG["cam"][0] - PH_MOUTH, CFG["cam"][1] + 1, 90),
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
    d.note("  R19 (50 mΩ → 1.64 A full scale) and DUT_5V on Vbus.")
    d.note("AUX: TX/RX through 1k, VREF = +3V3 through 10 Ω (level hint),")
    d.note("  RESET/BOOT open-drain (2N7002, 100k gate pull-downs).")
    return b


NETCLASSES = [
    {"name": "Power", "clearance": 0.15, "track_width": 0.6, "via_diameter": 0.8, "via_drill": 0.4,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 1,
     "_patterns": ["*24V_BUS", "+24V", "+5V", "*DUT_5V_SW", "*DUT_5V", "*BUCK_SW", "*CAM_5V"]},
    {"name": "USB", "clearance": 0.15, "track_width": 0.2, "via_diameter": 0.6, "via_drill": 0.3,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 2,
     "_patterns": ["*_DP", "*_DN"]},
]
