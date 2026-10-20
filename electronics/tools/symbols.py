#!/usr/bin/env python3
"""Project symbols that KiCad's library lacks, written into electronics/lib/bench.kicad_sym:

    python electronics/tools/symbols.py

Each symbol below replaces the entry of the same name in bench.kicad_sym (the hand-drawn ones there
stay as they are).  Pin numbers and names follow the part's datasheet, as JLC's own EasyEDA symbol
lists them (checked 2026-10-19).

* CH446Q (WCH, LQFP-44): 8 × 16 analog crosspoint; X0–X15 left, Y0–Y7 right, the serial/parallel
  control and the address pins below, supplies above.
* USB2517I (Microchip, QFN-64): 7-port USB 2.0 hub; upstream, crystal and straps left, the seven
  downstream pairs and their PRTPWR / OCS_N right, LED / strap pins below, supplies above.
"""

from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB = HERE.parent / "lib" / "bench.kicad_sym"
G = 2.54


def pin(kind: str, x: float, y: float, rot: int, name: str, num: str, length: float = G, hidden: bool = False) -> str:
    h = "\t\t\t\t(hide yes)\n" if hidden else ""
    return (f'\t\t\t(pin {kind} line\n\t\t\t\t(at {x:g} {y:g} {rot})\n\t\t\t\t(length {length:g})\n{h}'
            f'\t\t\t\t(name "{name}"\n\t\t\t\t\t(effects\n\t\t\t\t\t\t(font\n\t\t\t\t\t\t\t(size 1.27 1.27)\n'
            f'\t\t\t\t\t\t)\n\t\t\t\t\t)\n\t\t\t\t)\n\t\t\t\t(number "{num}"\n\t\t\t\t\t(effects\n\t\t\t\t\t\t(font\n'
            f'\t\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t\t)\n\t\t\t\t\t)\n\t\t\t\t)\n\t\t\t)\n')


def prop(key: str, val: str, x: float, y: float, hide: bool = False, justify: str = "") -> str:
    j = f"\n\t\t\t\t(justify {justify})" if justify else ""
    hd = "\n\t\t\t(hide yes)" if hide else ""
    return (f'\t\t(property "{key}" "{val}"\n\t\t\t(at {x:g} {y:g} 0){hd}\n\t\t\t(effects\n\t\t\t\t(font\n'
            f'\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t){j}\n\t\t\t)\n\t\t)\n')


def symbol(name: str, ref: str, fp: str, ds: str, desc: str, kw: str, box: tuple, pins: list) -> str:
    x0, y0, x1, y1 = box
    out = [f'\t(symbol "{name}"\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n',
           prop("Reference", ref, x0, y0 + 1.27, justify="left"), prop("Value", name, x1, y0 + 1.27, justify="right"),
           prop("Footprint", fp, 0, y1 - 2.54, hide=True), prop("Datasheet", ds, 0, 0, hide=True),
           prop("Description", desc, 0, 0, hide=True), prop("ki_keywords", kw, 0, 0, hide=True),
           f'\t\t(symbol "{name}_0_1"\n\t\t\t(rectangle\n\t\t\t\t(start {x0:g} {y0:g})\n\t\t\t\t(end {x1:g} {y1:g})\n'
           '\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n\t\t\t\t\t(type default)\n\t\t\t\t)\n\t\t\t\t(fill\n'
           '\t\t\t\t\t(type background)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n',
           f'\t\t(symbol "{name}_1_1"\n']
    out += pins
    out.append('\t\t)\n\t\t(embedded_fonts no)\n\t)\n')
    return "".join(out)


def column(names: list, x: float, y_top: float, side: str, kinds: dict, hidden=()) -> list:
    """Pins down one side of the box (KiCad symbol coordinates, y up): side 'L' points right into the
    box from x, 'R' points left, 'T' points down, 'B' points up.  `names` = [(number, name) | None]."""
    out = []
    for i, item in enumerate(names):
        if item is None:
            continue
        num, nm = item
        k = kinds.get(nm, "passive")
        if side in "LR":
            y = y_top - i * G
            out.append(pin(k, x, y, 0 if side == "L" else 180, nm, num, hidden=num in hidden))
        else:
            xx = x + i * G
            out.append(pin(k, xx, y_top, 270 if side == "T" else 90, nm, num, hidden=num in hidden))
    return out


def ch446q() -> str:
    W, Hh = 12.7, 25.4
    xl, xr = -W - G, W + G
    left = [(n, f"X{i}") for i, n in enumerate(["31", "30", "29", "28", "27", "26", "3", "4", "5", "6", "7", "8",
                                                "25", "24", "1", "2"])]
    right = [(n, f"Y{i}") for i, n in enumerate(["33", "35", "37", "39", "17", "15", "13", "11"])]
    right += [None, ("36", "DAT"), ("34", "CS/CK"), ("14", "STB"), ("41", "RST"), ("10", "P/~{S}")]
    top = [("38", "VDD")]
    bottom = [("16", "VEE"), ("12", "GND"), ("43", "AX0"), ("18", "AX1"), ("19", "AX2"), ("42", "AX3"),
              ("20", "AY0"), ("21", "AY1"), ("40", "AY2")]
    nc = [("9", "NC"), ("22", "NC"), ("23", "NC"), ("32", "NC"), ("44", "NC")]
    kinds = {"VDD": "power_in", "VEE": "power_in", "GND": "power_in", "DAT": "input", "CS/CK": "input",
             "STB": "input", "RST": "input", "P/~{S}": "input", "NC": "no_connect",
             **{f"AX{i}": "input" for i in range(4)}, **{f"AY{i}": "input" for i in range(3)}}
    pins = column(left, xl, Hh - G, "L", kinds) + column(right, xr, Hh - G, "R", kinds)
    pins += column(top, 0, Hh + G, "T", kinds)
    pins += column(bottom, -10.16, -Hh - G, "B", kinds)
    pins += [pin("no_connect", 0, 0, 0, "NC", n, hidden=True) for n, _ in nc]
    return symbol("CH446Q", "U", "Package_QFP:LQFP-44_10x10mm_P0.8mm",
                  "https://www.wch-ic.com/downloads/CH446DS1_PDF.html",
                  "8 × 16 analog crosspoint switch matrix (128 switches), serial or parallel addressing, LQFP-44",
                  "analog crosspoint matrix switch CH446", (-W, Hh, W, -Hh), pins)


def usb2517() -> str:
    W, Hh = 27.94, 43.18                # wide enough for the strap names, the sides clear of the top names
    xl, xr = -W - G, W + G
    left = [("59", "USBUP_DP"), ("58", "USBUP_DM"), None, ("61", "XTAL1/CLKIN"), ("60", "XTAL2"), None,
            ("63", "RBIAS"), ("43", "RESET_N"), ("44", "VBUS_DET"), ("19", "TEST"), None,
            ("41", "SCL/SMBCLK/CFG_SEL0"), ("42", "HS_IND/CFG_SEL1"), ("13", "CFG_SEL2"),
            ("40", "SDA/SMBDATA/NON_REM1"), ("45", "SUSP_IND/LOCAL_PWR/NON_REM0"), None,
            ("34", "LED_B3_N/GANG_EN"), ("50", "LED_B1_N/BOOST0"), ("48", "LED_B2_N/BOOST1")]
    right = []
    pairs = {1: ("2", "1"), 2: ("4", "3"), 3: ("7", "6"), 4: ("9", "8"), 5: ("12", "11"), 6: ("54", "53"),
             7: ("56", "55")}
    for n, (dp, dm) in pairs.items():
        right += [(dp, f"USBDN{n}_DP/PRT_DIS_P{n}"), (dm, f"USBDN{n}_DM/PRT_DIS_M{n}")]
    right.append(None)
    for n, (pp, oc) in {1: ("29", "28"), 2: ("26", "27"), 3: ("23", "22"), 4: ("20", "21"), 5: ("30", "35"),
                        6: ("39", "38"), 7: ("36", "37")}.items():
        right += [(pp, f"PRTPWR{n}"), (oc, f"OCS{n}_N")]
    top = [("46", "VDD33"), ("64", "VDD33PLL"), ("24", "VDD33CR"), ("5", "VDDA33"), ("10", "VDDA33"),
           ("52", "VDDA33"), ("57", "VDDA33"), None, ("25", "VDD18"), ("62", "VDD18PLL")]
    bottom = [("65", "VSS"), None, ("51", "LED_A1_N/PRT_SWP1"), ("49", "LED_A2_N/PRT_SWP2"),
              ("47", "LED_A3_N/PRT_SWP3"), ("33", "LED_A4_N/PRT_SWP4"), ("31", "LED_A5_N/PRT_SWP5"),
              ("17", "LED_A6_N/PRT_SWP6"), ("15", "LED_A7_N/PRT_SWP7"), ("32", "LED_B4_N"), ("18", "LED_B5_N"),
              ("16", "LED_B6_N"), ("14", "LED_B7_N")]
    kinds = {"VDD33": "power_in", "VDD33PLL": "power_in", "VDD33CR": "power_in", "VDDA33": "power_in",
             "VDD18": "power_out", "VDD18PLL": "power_out", "VSS": "power_in", "RESET_N": "input",
             "VBUS_DET": "input", "TEST": "input", "RBIAS": "passive", "XTAL1/CLKIN": "input", "XTAL2": "output"}
    pins = column(left, xl, Hh - 5 * G, "L", kinds) + column(right, xr, Hh - 5 * G, "R", kinds)
    pins += column(top, -11.43, Hh + G, "T", kinds)
    pins += column(bottom, -15.24, -Hh - G, "B", kinds)
    return symbol("USB2517I", "U", "Package_DFN_QFN:QFN-64-1EP_9x9mm_P0.5mm_EP4.7x4.7mm",
                  "https://ww1.microchip.com/downloads/en/DeviceDoc/00001598C.pdf",
                  "USB 2.0 hub controller, 7 downstream ports, multi-TT, SMBus or strap configuration, QFN-64",
                  "USB hub 7 port USB2517", (-W, Hh, W, -Hh), pins)


def main():
    text = LIB.read_text(encoding="utf-8")
    for body in (ch446q(), usb2517()):
        name = re.match(r'\t\(symbol "([^"]+)"', body).group(1)
        # drop an existing entry of that name (top-level symbols start with one tab)
        m = re.search(rf'\n\t\(symbol "{re.escape(name)}"\n.*?\n\t\)\n', text, re.S)
        if m:
            text = text[:m.start() + 1] + text[m.end():]
        i = text.rstrip().rfind(")")
        text = text[:i] + body + text[i:]
        print("wrote", name)
    LIB.write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
