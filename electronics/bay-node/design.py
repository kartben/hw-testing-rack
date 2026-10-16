"""Bay node — one per bay: ESP32-S3 USB/IP host for the board under test (DUT).

Functions
  * 24 V bus in/out (JST VH, daisy-chained bay to bay), reverse-polarity
    P-FET, TVS, 60 V buck to 5 V / 3.5 A, 3.3 V LDO for the logic.
  * DUT port (USB-C, source): VBUS through a TPS2553 current-limited switch
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


def P(x, y, rot=0, side="top"):
    return {"x": x, "y": y, "rot": rot, "side": side}


def board() -> Board:
    b = Board("bay-node", "Bay node", "0.1",
              comments=["ESP32-S3 USB/IP host for one bay of the hw-testing-rack shelf",
                        "Generated from electronics/bay-node/design.py — edit the Python, then regenerate",
                        "24 V in · 5 V/1.4 A switched DUT port · USB 2.0 muxes · INA226 · AUX UART/RST/BOOT"])
    b.root_notes = [
        "Bay node — one per bay.  Sheets:",
        "  Power: 24 V bus (daisy-chain), reverse protection, TPS54360B buck to 5 V, AMS1117 3.3 V",
        "  MCU: ESP32-S3-MINI-1, boot/reset, status LED, UART pads",
        "  USB: front PC port, DUT port, two FSUSB42 muxes + OR gate (classic / USB-IP / service modes)",
        "  DUT power & AUX: TPS2553 switch, INA226 monitor, AUX UART/RESET/BOOT, camera 5 V",
        "",
        "Mode truth table:  SERVICE=0, PC unplugged → DUT↔ESP32 (USB/IP)",
        "                   SERVICE=0, PC plugged   → DUT↔PC (classic), ESP32 still controls VBUS/AUX",
        "                   SERVICE=1               → PC↔ESP32 (flash/console), DUT data disconnected",
        "GPIO firmware can also force classic mode (MUX_FORCE_PC).",
    ]
    b.pcb = {
        "size": (W, H), "layers": CFG["layers"], "corner_radius": 2.0, "passes": 60,
        # 4 layers: In1 is a solid GND plane; keeping the outer GND pours in the router's view lets
        # Freerouting finish the board (hiding F.Cu's leaves ~20 nets unrouted: no room to give
        # every top GND pad its own via).  stitch_gnd() then ties the pour fragments to the plane.
        "defer_pours": False,
        "stitch": 2.6,          # GND via-stitching grid pitch (mm) after routing
        # GND pads the router tends to wall in (U9's middle pin, U5's corner pin between the SVC
        # line and the ESP pair): reserve a dog-bone via outside the package before routing
        "fanout": [("U9", "2"), ("U5", "10")],
        "zones": [
            {"layer": "In1.Cu", "net": "GND"},
            {"layer": "B.Cu", "net": "GND"},
            {"layer": "F.Cu", "net": "GND"},
        ],
        # ESP32 antenna: no copper on any layer under/around the antenna (module top 5 mm + edge)
        "keepouts": [
            {"name": "antenna", "poly": [(9.3, -0.1), (54.7, -0.1), (54.7, 5.4), (9.3, 5.4)]},
        ],
        "texts": [
            {"text": "hw-testing-rack · bay node v0.1", "x": 32, "y": 46.5, "size": 1.0},
            {"text": "PC", "x": 32, "y": 71.2, "size": 0.9},
            {"text": "SVC", "x": 50, "y": 73.6, "size": 0.8},
            {"text": "24V IN", "x": 7, "y": 56.5, "size": 0.8},
            {"text": "24V OUT", "x": 57, "y": 56.5, "size": 0.8},
            {"text": "DUT", "x": 57.5, "y": 17, "size": 0.8},
            {"text": "AUX", "x": 57.5, "y": 34.2, "size": 0.8},
            {"text": "CAM", "x": 55.5, "y": 11, "size": 0.8},
        ],
    }

    # ------------------------------------------------------------------ power
    s = b.sheet("Power", "power.kicad_sch", "24 V input, 5 V buck, 3.3 V LDO")
    s.block("24 V bus (daisy-chain) and protection")
    part(s, "J1", "vh_h", {"1": "VBUS24", "2": "GND"}, "24V IN", pcb=P(13.45, 62, 270))
    part(s, "J2", "vh_h", {"1": "VBUS24", "2": "GND"}, "24V OUT", pcb=P(50.5, 66, 90))
    s.part("#FLG01", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "VBUS24"}, in_bom=False, on_board=False)
    s.part("#FLG02", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "GND"}, in_bom=False, on_board=False)
    s.part("#FLG03", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+24V"}, in_bom=False, on_board=False)
    s.part("#FLG04", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+5V"}, in_bom=False, on_board=False)
    part(s, "Q1", "pfet", {"G": "Q1_GATE", "D": "VBUS24", "S": "+24V"}, pcb=P(21, 56, 0))
    part(s, "D1", "zener12", {"K": "+24V", "A": "Q1_GATE"}, pcb=P(22, 61.5, 0))
    R(s, "R1", "100k", "Q1_GATE", "GND", pcb=P(22, 64.5, 0))
    part(s, "D2", "tvs33", {"K": "+24V", "A": "GND"}, pcb=P(21, 48, 0))
    part(s, "C1", "cap100u50", {"1": "+24V", "2": "GND"}, "100u/50V", pcb=P(8, 46, 90))

    s.block("TPS54360B buck, 24 V → 5.16 V, ≈640 kHz")
    C(s, "C2", "10u", "+24V", "GND", size="1206", pcb=P(14, 35, 90))
    C(s, "C3", "10u", "+24V", "GND", size="1206", pcb=P(11, 35, 90))
    part(s, "U1", "buck", {"VIN": "+24V", "EN": None, "RT/CLK": "BUCK_RT", "FB": "BUCK_FB", "COMP": "BUCK_COMP",
                           "GND": "GND", "GNDPAD": "GND", "SW": "BUCK_SW", "BOOT": "BUCK_BOOT"},
         pcb=P(20, 35, 0))
    C(s, "C4", "100n", "BUCK_BOOT", "BUCK_SW", pcb=P(15.5, 30.7, 0))
    R(s, "R2", "150k", "BUCK_RT", "GND", pcb=P(17, 40, 0))
    part(s, "L1", "buck_l", {"1": "BUCK_SW", "2": "+5V"}, "10u", pcb=P(11, 22, 0))
    part(s, "D3", "buck_d", {"K": "BUCK_SW", "A": "GND"}, pcb=P(25, 27, 0))
    R(s, "R3", "120k", "+5V", "BUCK_FB", pcb=P(25, 39, 90))
    R(s, "R4", "22k", "BUCK_FB", "GND", pcb=P(27, 39, 90))
    R(s, "R5", "13k", "BUCK_COMP", "BUCK_COMP_RC", pcb=P(25, 43.5, 90))
    C(s, "C5", "6.8n", "BUCK_COMP_RC", "GND", pcb=P(27, 43.5, 90))
    C(s, "C6", "47p", "BUCK_COMP", "GND", pcb=P(29, 41, 90))
    for i, x in enumerate((6, 9, 12, 15)):
        C(s, f"C{7 + i}", "22u", "+5V", "GND", size="1206", pcb=P(x, 11, 90))
    s.note("Values follow TI's TPS54360B 5 V/3.5 A design example (SNVSB93 §8.2), with basic-library parts:")
    s.note("  RT 150k → ≈640 kHz;  FB 120k/22k → 5.16 V (covers the switch + shunt drop at the DUT);")
    s.note("  type-II compensation 13k + 6.8 nF + 47 pF;  EN left floating = always on (internal UVLO).")
    s.note("Input: SUD50P06 P-FET (reverse polarity, gate clamped by 12 V zener), SMBJ33A clamps < 54 V < 60 V abs max.")

    s.block("3.3 V logic supply")
    part(s, "U2", "ldo", {"VI": "+5V", "VO": "+3V3", "GND": "GND"}, pcb=P(44, 30, 0))
    C(s, "C11", "10u", "+5V", "GND", size="0805", pcb=P(44, 36.5, 0))
    C(s, "C12", "22u", "+3V3", "GND", size="1206", pcb=P(38.5, 36.5, 90))

    # ------------------------------------------------------------------ MCU
    m = b.sheet("MCU", "mcu.kicad_sch", "ESP32-S3 module")
    m.block("ESP32-S3-MINI-1 (antenna at the board's rear edge, keep-out on all layers)")
    part(m, "U3", "esp32s3", {
        "3V3": "+3V3", "GND": "GND", "EN": "EN", "IO0": "BOOT",
        "USB_D-": "ESP_DN", "USB_D+": "ESP_DP",
        "IO4": "PC_DET", "IO5": "SVC", "IO6": "DUT_EN", "IO7": "DUT_FLT_N",
        "IO8": "I2C_SDA", "IO9": "I2C_SCL", "IO10": "MUX_FORCE_PC",
        "IO11": "AUX_RST_CTL", "IO12": "AUX_BOOT_CTL", "IO13": "LED_DIN", "IO14": "INA_ALERT_N",
        "IO17": "AUX_TX", "IO18": "AUX_RX", "TXD0": "U0TX", "RXD0": "U0RX",
    }, pcb=P(32, 10.5, 0))
    C(m, "C13", "22u", "+3V3", "GND", size="1206", pcb=P(21, 9, 90))
    C(m, "C14", "100n", "+3V3", "GND", pcb=P(21, 13.5, 90))

    m.block("Reset, boot, UART test pads")
    R(m, "R6", "10k", "+3V3", "EN", pcb=P(21.5, 17.3, 0))
    C(m, "C15", "1u", "EN", "GND", pcb=P(21.5, 19.3, 0))
    part(m, "SW1", "button", {"1": "EN", "2": "GND"}, "RESET", pcb=P(47, 11, 0))
    R(m, "R7", "10k", "+3V3", "BOOT", pcb=P(42, 12, 90))
    part(m, "SW2", "button", {"1": "BOOT", "2": "GND"}, "BOOT", pcb=P(47, 18, 0))
    for i, (net, x) in enumerate((("U0TX", 33), ("U0RX", 35.5), ("GND", 38), ("+3V3", 40.5))):
        part(m, f"TP{i + 1}", "testpad", {"1": net}, net, pcb=P(x, 24, 0), in_bom=False)

    m.block("Status LED (behind the fascia window)")
    part(m, "D4", "rgb", {"VDD": "+3V3", "VSS": "GND", "DIN": "LED_DIN_R", "DOUT": None}, pcb=P(12, 78.2, 0))
    R(m, "R8", "33", "LED_DIN", "LED_DIN_R", pcb=P(16, 74.5, 0))
    C(m, "C16", "100n", "+3V3", "GND", pcb=P(16, 77.8, 90))
    m.note("GPIO map: IO4 PC_DET · IO5 SVC · IO6 DUT_EN · IO7 DUT_FLT_N · IO8/9 I2C · IO10 MUX_FORCE_PC ·")
    m.note("IO11 AUX_RST · IO12 AUX_BOOT · IO13 LED · IO14 INA_ALERT · IO17/18 UART1 (AUX) · IO19/20 USB (OTG/JTAG).")
    m.note("Strapping pins IO0/IO3/IO45/IO46 are not used for I/O.  USB is full-speed only (one internal PHY).")

    # ------------------------------------------------------------------ USB
    u = b.sheet("USB", "usb.kicad_sch", "USB ports and data-path muxes")
    u.block("Front PC port (classic mode / service) — UFP: Rd on CC, VBUS only sensed")
    part(u, "J3", "usbc", {"VBUS": "PC_VBUS", "GND": "GND", "CC1": "PC_CC1", "CC2": "PC_CC2", "D+": "PC_DP",
                           "D-": "PC_DN", "SBU1": None, "SBU2": None, "SHIELD": "GND"}, "PC", pcb=P(32, 76.6, 0))
    R(u, "R9", "5.1k", "PC_CC1", "GND", pcb=P(24.5, 74.5, 90))
    R(u, "R10", "5.1k", "PC_CC2", "GND", pcb=P(39.5, 74.5, 90))
    part(u, "U4", "esd", {"I/O1": "PC_DP", "I/O2": "PC_DN", "VBUS": "+5V", "GND": "GND"}, pcb=P(32, 69.5, 0))
    R(u, "R11", "10k", "PC_VBUS", "PC_DET", pcb=P(41, 70, 0))
    R(u, "R12", "20k", "PC_DET", "GND", pcb=P(41, 67.6, 0))

    u.block("Muxes: MUX_PC (front port → DUT path or ESP32), MUX_DUT (DUT → ESP32 or PC path)")
    part(u, "U5", "mux", {"VCC": "+3V3", "GND": "GND", "D+": "PC_DP", "D-": "PC_DN", "HSD1+": "PCPATH_DP",
                          "HSD1-": "PCPATH_DN", "HSD2+": "ESP_DP", "HSD2-": "ESP_DN", "SEL": "SVC", "~{OE}": "GND"},
         "MUX_PC", pcb=P(32, 63.5, 0))
    C(u, "C17", "100n", "+3V3", "GND", pcb=P(27.5, 63.5, 90))
    part(u, "U6", "mux", {"VCC": "+3V3", "GND": "GND", "D+": "DUT_DP", "D-": "DUT_DN", "HSD1+": "ESP_DP",
                          "HSD1-": "ESP_DN", "HSD2+": "PCPATH_DP", "HSD2-": "PCPATH_DN", "SEL": "MUX_SEL",
                          "~{OE}": "SVC"}, "MUX_DUT", pcb=P(51, 39, 0))
    C(u, "C18", "100n", "+3V3", "GND", pcb=P(51, 42.8, 0))
    part(u, "U7", "or", {"1": "PC_DET", "2": "MUX_FORCE_PC", "3": "GND", "4": "MUX_SEL", "5": "+3V3"},
         pcb=P(44, 63, 0))
    C(u, "C19", "100n", "+3V3", "GND", pcb=P(45.3, 66.8, 0))
    R(u, "R13", "100k", "MUX_FORCE_PC", "GND", pcb=P(44, 59.6, 0))
    part(u, "SW3", "slide", {"1": "+3V3", "2": "SVC", "3": "GND"}, "SERVICE", pcb=P(50, 77.3, 0))
    u.note("SVC=1 routes the PC port to the ESP32 (flash / console / JTAG) and disables MUX_DUT (~OE high).")
    u.note("MUX_SEL = PC_DET OR MUX_FORCE_PC: a laptop on the front port takes the DUT over automatically.")

    u.block("DUT port (USB-C source, Rp = 22k → advertises 1.5 A)")
    part(u, "J4", "usbc", {"VBUS": "VBUS_DUT", "GND": "GND", "CC1": "DUT_CC1", "CC2": "DUT_CC2", "D+": "DUT_DP",
                           "D-": "DUT_DN", "SBU1": None, "SBU2": None, "SHIELD": "GND"}, "DUT", pcb=P(60.4, CFG["right"]["dut"], 90))
    R(u, "R14", "22k", "VBUS_DUT", "DUT_CC1", pcb=P(53, 27.6, 90))
    R(u, "R15", "22k", "VBUS_DUT", "DUT_CC2", pcb=P(53, 21, 90))
    part(u, "U8", "esd", {"I/O1": "DUT_DP", "I/O2": "DUT_DN", "VBUS": "+5V", "GND": "GND"}, pcb=P(51, 33, 0))

    # ------------------------------------------------------------------ DUT power + AUX
    d = b.sheet("DUT power & AUX", "dut.kicad_sch", "DUT power switch, monitor, AUX and camera power")
    d.block("TPS2553 switch (RILIM 18k → 1.34–1.52 A), default ON")
    part(d, "U9", "vbus_sw", {"IN": "+5V", "GND": "GND", "EN": "DUT_EN", "~{FAULT}": "DUT_FLT_N", "ILIM": "ILIM",
                              "OUT": "VBUS_SW"}, pcb=P(44, 46, 0))
    R(d, "R16", "18k", "ILIM", "GND", pcb=P(40.5, 46.5, 90))
    R(d, "R17", "100k", "+3V3", "DUT_EN", pcb=P(40.5, 50.2, 90))
    R(d, "R18", "10k", "+3V3", "DUT_FLT_N", pcb=P(47.6, 50.2, 90))
    C(d, "C20", "100n", "+5V", "GND", pcb=P(40.5, 43, 90))
    C(d, "C21", "22u", "VBUS_DUT", "GND", size="1206", pcb=P(49, 46, 90))

    d.block("INA226 on the DUT VBUS (50 mΩ shunt → 1.64 A full scale), I2C 0x40")
    part(d, "R19", "shunt50m", {"1": "VBUS_SW", "2": "VBUS_DUT"}, "50m", pcb=P(44, 51, 0))
    part(d, "U10", "ina226", {"VS": "+3V3", "GND": "GND", "A0": "GND", "A1": "GND", "SDA": "I2C_SDA",
                              "SCL": "I2C_SCL", "~{Alert}": "INA_ALERT_N", "Vin+": "VBUS_SW", "Vin-": "VBUS_DUT",
                              "Vbus": "VBUS_DUT"}, pcb=P(44, 56, 0))
    C(d, "C22", "100n", "+3V3", "GND", pcb=P(49, 56, 90))
    R(d, "R20", "10k", "+3V3", "INA_ALERT_N", pcb=P(37.6, 56, 90))
    R(d, "R21", "4.7k", "+3V3", "I2C_SDA", pcb=P(37.6, 48, 90))
    R(d, "R22", "4.7k", "+3V3", "I2C_SCL", pcb=P(37.6, 51.6, 90))

    d.block("AUX: UART + open-drain RESET/BOOT towards the DUT (JST-SH 6)")
    part(d, "J5", "sh6", {"1": "GND", "2": "AUX_VREF", "3": "AUX_TX_R", "4": "AUX_RX_R", "5": "AUX_RST_N",
                          "6": "AUX_BOOT_N", "MP": "GND"}, "AUX", pcb=P(60.8, CFG["right"]["aux"], 90))
    R(d, "R23", "10", "+3V3", "AUX_VREF", pcb=P(57.6, 47.4, 0))
    R(d, "R24", "1k", "AUX_TX", "AUX_TX_R", pcb=P(57, 33.6, 0))
    R(d, "R25", "1k", "AUX_RX", "AUX_RX_R", pcb=P(54.6, 30.8, 90))
    part(d, "Q2", "nfet", {"G": "AUX_RST_CTL", "S": "GND", "D": "AUX_RST_N"}, pcb=P(55, 50.4, 0))
    part(d, "Q3", "nfet", {"G": "AUX_BOOT_CTL", "S": "GND", "D": "AUX_BOOT_N"}, pcb=P(55, 54.2, 0))
    R(d, "R26", "100k", "AUX_RST_CTL", "GND", pcb=P(51.6, 50.4, 90))
    R(d, "R27", "100k", "AUX_BOOT_CTL", "GND", pcb=P(51.6, 54.2, 90))

    d.block("Camera pod 5 V (always on, PTC protected)")
    part(d, "F1", "pptc500", {"1": "+5V", "2": "CAM_5V"}, "0.5A", pcb=P(54.5, 15.5, 90))
    part(d, "J6", "ph2", {"1": "CAM_5V", "2": "GND"}, "CAM", pcb=P(CFG["cam"][0] - 4.9, CFG["cam"][1] + 1, 90))

    d.block("Mounting (M3, matches the carrier standoffs)")
    for i, (x, y) in enumerate(CFG["holes"]):
        part(d, f"H{i + 1}", "hole", {}, "M3", pcb=P(x, y, 0), in_bom=False)
    return b


NETCLASSES = [
    {"name": "Power", "clearance": 0.15, "track_width": 0.6, "via_diameter": 0.8, "via_drill": 0.4,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 1,
     "_patterns": ["*VBUS24", "+24V", "+5V", "*VBUS_SW", "*VBUS_DUT", "*BUCK_SW", "*CAM_5V"]},
    {"name": "USB", "clearance": 0.15, "track_width": 0.2, "via_diameter": 0.6, "via_drill": 0.3,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 2,
     "_patterns": ["*_DP", "*_DN"]},
]
