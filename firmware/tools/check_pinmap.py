#!/usr/bin/env python3
"""Check the bay node pin map: schematic vs. README vs. devicetree.

The U3 (ESP32-S3-MINI-1) pin dictionary in electronics/bay-node/design.py is
the source of truth.  This checks that

  * every row of the "Pin map" table in firmware/README.md names the same
    net on the same pin as design.py, and that no U3 GPIO is missing there;
  * the board devicetree (firmware/boards/hwtr/bay_node/) puts each net's
    GPIO property or pinmux on that same pin.

Stdlib only (design.py is parsed, not imported), so it runs anywhere:

    python3 firmware/tools/check_pinmap.py
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "electronics/bay-node/design.py"
README = ROOT / "firmware/README.md"
BOARD = ROOT / "firmware/boards/hwtr/bay_node"
DTS_FILES = ("bay_node_procpu.dts", "bay_node.dtsi", "bay_node-pinctrl.dtsi")

# U3 pin names that are not "IO<n>", as the GPIO they are.
PIN_ALIASES = {"TXD0": 43, "RXD0": 44, "USB_D-": 19, "USB_D+": 20}
# U3 pins that are not GPIOs.
NON_GPIO = {"3V3", "GND", "EN"}

# How each net shows up in the devicetree: a "*-gpios" / "gpios" property
# (<&gpioN pin ...>) or a pinmux macro prefix (<PREFIX_GPIO<pin>>).
NET_TO_DT = {
    "BOOT": ("gpio", "gpios"),
    "PC_DET": ("gpio", "pc-detect-gpios"),
    "SVC": ("gpio", "service-gpios"),
    "DUT_EN": ("gpio", "enable-gpios"),
    "DUT_FLT_N": ("gpio", "fault-gpios"),
    "MUX_FORCE_PC": ("gpio", "force-pc-gpios"),
    "AUX_RST_CTL": ("gpio", "reset-gpios"),
    "AUX_BOOT_CTL": ("gpio", "boot-gpios"),
    "INA_ALERT_N": ("gpio", "alert-gpios"),
    "I2C_SDA": ("pinmux", "I2C0_SDA"),
    "I2C_SCL": ("pinmux", "I2C0_SCL"),
    "LED_DIN": ("pinmux", "RMT_OUT0"),
    "AUX_TX": ("pinmux", "UART1_TX"),
    "AUX_RX": ("pinmux", "UART1_RX"),
    "U0TX": ("pinmux", "UART0_TX"),
    "U0RX": ("pinmux", "UART0_RX"),
    "CAN_TXD": ("pinmux", "TWAI_TX"),
    "CAN_RXD": ("pinmux", "TWAI_RX"),
    "POS_IN": ("gpio", "pos-in-gpios"),
    "POS_OUT": ("gpio", "pos-out-gpios"),
}
# Nets that also appear a second way (checked like NET_TO_DT).
NET_ALSO_DT = {
    "AUX_TX": [("gpio", "tx-gpios")],  # dut-port: the TX pin as a GPIO (idle, BREAK)
}
# Nets on fixed-function pins: nothing to check in the devicetree.
DT_FIXED = {"ESP_DN", "ESP_DP"}  # IO19/IO20, the internal USB PHY (&usb_otg)


def gpio_number(pin: str) -> int | None:
    if pin in PIN_ALIASES:
        return PIN_ALIASES[pin]
    m = re.fullmatch(r"IO(\d+)", pin)
    return int(m.group(1)) if m else None


def design_pins() -> dict[int, str]:
    """GPIO number -> net, from the part(m, "U3", ..., {pin: net}) call."""
    tree = ast.parse(DESIGN.read_text(encoding="utf-8"), str(DESIGN))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "part"
                and len(node.args) >= 4 and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == "U3"):
            pins = ast.literal_eval(node.args[3])
            break
    else:
        sys.exit(f"{DESIGN}: no part(..., \"U3\", ...) call found")

    gpios = {}
    for pin, net in pins.items():
        if pin in NON_GPIO or net is None:
            continue
        n = gpio_number(pin)
        if n is None:
            sys.exit(f"{DESIGN}: U3 pin {pin!r} is not a known GPIO, add it to PIN_ALIASES")
        gpios[n] = net
    return gpios


def readme_pins(errors: list[str]) -> dict[int, str]:
    """GPIO number -> net, from the README "Pin map" table."""
    text = README.read_text(encoding="utf-8")
    m = re.search(r"^## Pin map\n(.*?)(?=^## )", text, re.M | re.S)
    if not m:
        sys.exit(f"{README}: no '## Pin map' section")
    pins = {}
    for line in m.group(1).splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or not line.startswith("|"):
            continue
        pin, net = cells[0], cells[1]
        g = re.fullmatch(r"(?:IO(\d+)|\w+ \(IO(\d+)\))", pin)
        if not g:
            continue  # header, separator, EN
        n = int(g.group(1) or g.group(2))
        if n in pins:
            errors.append(f"README: IO{n} listed twice")
        pins[n] = net
    return pins


def dt_pins() -> tuple[dict[str, set[int]], dict[str, set[int]]]:
    """(gpio property -> pins, pinmux prefix -> pins) over the board's DTS files."""
    props: dict[str, set[int]] = {}
    pinmux: dict[str, set[int]] = {}
    for name in DTS_FILES:
        text = (BOARD / name).read_text(encoding="utf-8")
        text = re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)
        for prop, port, pin in re.findall(r"([\w-]*gpios)\s*=\s*<\s*&gpio([01])\s+(\d+)", text):
            props.setdefault(prop, set()).add(int(pin) + 32 * int(port))
        for prefix, pin in re.findall(r"\b([A-Z0-9]+_[A-Z0-9_]+?)_GPIO(\d+)\b", text):
            pinmux.setdefault(prefix, set()).add(int(pin))
    return props, pinmux


def main() -> int:
    errors: list[str] = []
    design = design_pins()
    readme = readme_pins(errors)
    props, pinmux = dt_pins()

    for n, net in sorted(design.items()):
        if n not in readme:
            errors.append(f"README: IO{n} ({net}) missing from the pin map")
        elif readme[n] != net:
            errors.append(f"README: IO{n} is {readme[n]!r}, design.py says {net!r}")
    for n, net in sorted(readme.items()):
        if n not in design:
            errors.append(f"README: IO{n} ({net}) is not connected on U3 in design.py")

    for n, net in sorted(design.items()):
        if net in DT_FIXED:
            continue
        if net not in NET_TO_DT:
            errors.append(f"devicetree: no rule for net {net!r} (IO{n}), add it to NET_TO_DT")
            continue
        for kind, key in [NET_TO_DT[net], *NET_ALSO_DT.get(net, [])]:
            found = (props if kind == "gpio" else pinmux).get(key, set())
            what = f"{key}" if kind == "gpio" else f"{key}_GPIO<n>"
            if not found:
                errors.append(f"devicetree: {what} for {net} (IO{n}) not found")
            elif found != {n}:
                pins = ", ".join(f"IO{p}" for p in sorted(found))
                errors.append(f"devicetree: {what} for {net} is on {pins}, design.py says IO{n}")

    for e in errors:
        print(f"error: {e}")
    if errors:
        return 1
    print(f"pin map OK: {len(design)} U3 GPIOs match README.md and the bay_node devicetree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
