#!/usr/bin/env python3
"""Check the boards' pin maps: schematic vs. README vs. devicetree.

For each board (the bay node, the power hub), the ESP32-S3 module's pin
dictionary in its electronics/<board>/design.py is the source of truth.
This checks that

  * every row of the "Pin map" table in the board's firmware README names
    the same net on the same pin as design.py, and that no module GPIO is
    missing there;
  * the board devicetree (firmware/boards/hwtr/<board>/) puts each net's
    GPIO property, pinmux or ADC channel on that same pin.

Stdlib only (design.py is parsed, not imported), so it runs anywhere:

    python3 firmware/tools/check_pinmap.py
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Module pin names that are not "IO<n>", as the GPIO they are.
PIN_ALIASES = {"TXD0": 43, "RXD0": 44, "USB_D-": 19, "USB_D+": 20}
# Module pins that are not GPIOs.
NON_GPIO = {"3V3", "GND", "EN"}

# How a net shows up in the devicetree:
#   ("gpio", prop[, node])  a "*-gpios" property, in any node or in the node
#                           with that label or name
#   ("pinmux", prefix)      a pinmux macro <PREFIX_GPIO<pin>>
#   ("adc", node)           io-channels = <&adc0 N> in that node: ADC1 channel
#                           N is IO(N + 1) on the ESP32-S3
BOARDS = {
    "bay_node": {
        "design": "electronics/bay-node/design.py",
        "ref": "U3",
        "readme": "firmware/README.md",
        "dts": ["bay_node_procpu.dts", "bay_node.dtsi", "bay_node-pinctrl.dtsi"],
        "nets": {
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
            "CAM_SCK": ("pinmux", "SPIM2_SCLK"),
            "CAM_MOSI": ("pinmux", "SPIM2_MOSI"),
            "CAM_MISO": ("pinmux", "SPIM2_MISO"),
            "CAM_CS": ("gpio", "cs-gpios"),
            "CAM_LED": ("pinmux", "LEDC_CH0"),
        },
        # Nets that also appear a second way
        "also": {"AUX_TX": [("gpio", "tx-gpios")]},  # dut-port: the TX pin as a GPIO
        # Nets on fixed-function pins: nothing to check in the devicetree
        "fixed": {"ESP_DN", "ESP_DP"},  # IO19/IO20, the internal USB PHY (&usb_otg)
        # Nets wired on the board that no devicetree node uses yet (README says so): skipped
        "reserved": {"DATA_INT"},  # IO4, J7.8: the INT of a later DATA ×4 board
    },
    "power_hub": {
        "design": "electronics/power-hub/design.py",
        "ref": "U4",
        "readme": "firmware/power-hub/README.md",
        "dts": ["power_hub_procpu.dts", "power_hub.dtsi", "power_hub-pinctrl.dtsi"],
        "nets": {
            "BOOT": ("gpio", "gpios", "boot_button"),
            **{f"ADC_IMON_{r}": ("adc", f"imon_{r.lower()}") for r in "ABCD"},
            "VBUS_SENSE": ("adc", "vbus_sense"),
            "CAN_TXD": ("pinmux", "TWAI_TX"),
            "CAN_RXD": ("pinmux", "TWAI_RX"),
            "CAN_STB": ("gpio", "standby-gpios", "can_phy"),
            **{f"POS_{r}": ("gpio", "pos-gpios", f"row_{r.lower()}") for r in "ABCD"},
            **{f"ROW_EN_{r}": ("gpio", "enable-gpios", f"row_{r.lower()}") for r in "ABCD"},
            **{f"FLT_{r}": ("gpio", "fault-gpios", f"row_{r.lower()}") for r in "ABCD"},
            "CTL_LED": ("gpio", "gpios", "ctl_led"),
            "PD_INT": ("gpio", "pg-gpios", "pd_sink"),
            "PD_SCL": ("pinmux", "I2C0_SCL"),
            "PD_SDA": ("pinmux", "I2C0_SDA"),
            "I2C_PU": ("gpio", "i2c-pullup-gpios", "power_hub"),
            "U0TX": ("pinmux", "UART0_TX"),
            "U0RX": ("pinmux", "UART0_RX"),
        },
        "also": {},
        "fixed": {"USB_DN", "USB_DP"},  # IO19/IO20: the console USB-C (USB-Serial-JTAG)
    },
}


def gpio_number(pin: str) -> int | None:
    if pin in PIN_ALIASES:
        return PIN_ALIASES[pin]
    m = re.fullmatch(r"IO(\d+)", pin)
    return int(m.group(1)) if m else None


def design_pins(design: Path, ref: str) -> dict[int, str]:
    """GPIO number -> net, from the part(..., ref, ..., {pin: net}) call."""
    tree = ast.parse(design.read_text(encoding="utf-8"), str(design))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "part"
                and len(node.args) >= 4 and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == ref):
            pins = ast.literal_eval(node.args[3])
            break
    else:
        sys.exit(f"{design}: no part(..., {ref!r}, ...) call found")

    gpios = {}
    for pin, net in pins.items():
        if pin in NON_GPIO or net is None:
            continue
        n = gpio_number(pin)
        if n is None:
            sys.exit(f"{design}: {ref} pin {pin!r} is not a known GPIO, add it to PIN_ALIASES")
        gpios[n] = net
    return gpios


def readme_pins(readme: Path, errors: list[str]) -> dict[int, str]:
    """GPIO number -> net, from the README "Pin map" table."""
    text = readme.read_text(encoding="utf-8")
    m = re.search(r"^## Pin map\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        sys.exit(f"{readme}: no '## Pin map' section")
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
            errors.append(f"{readme.name}: IO{n} listed twice")
        pins[n] = net
    return pins


def dt_statements(text: str) -> list[tuple[set[str], str, str]]:
    """(labels and names of the enclosing node, property, value) for every property."""
    text = re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)
    text = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    out: list[tuple[set[str], str, str]] = []
    stack: list[set[str]] = []
    for m in re.finditer(r"([^{};]*)\{|\}|([^{};]+);", text):
        if m.group(0) == "}":
            if stack:
                stack.pop()
        elif m.group(1) is not None:
            names = {part.strip().split("@")[0].lstrip("&") for part in m.group(1).split(":")}
            stack.append({n for n in names if n})
        elif "=" in m.group(2):
            prop, value = m.group(2).split("=", 1)
            out.append((stack[-1] if stack else set(), prop.strip(), value))
    return out


def dt_pins(board_dir: Path, files: list[str]):
    """gpio: (prop, node names) -> pins; pinmux prefix -> pins; adc: node names -> pins."""
    gpio: list[tuple[str, set[str], set[int]]] = []
    pinmux: dict[str, set[int]] = {}
    adc: list[tuple[set[str], set[int]]] = []
    for name in files:
        text = (board_dir / name).read_text(encoding="utf-8")
        for names, prop, value in dt_statements(text):
            if prop.endswith("gpios"):
                pins = {int(pin) + 32 * int(port)
                        for port, pin in re.findall(r"&gpio([01])\s+(\d+)", value)}
                gpio.append((prop, names, pins))
            elif prop == "io-channels":
                adc.append((names, {int(ch) + 1 for ch in re.findall(r"&adc0\s+(\d+)", value)}))
        clean = re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)
        for prefix, pin in re.findall(r"\b([A-Z0-9]+_[A-Z0-9_]+?)_GPIO(\d+)\b", clean):
            pinmux.setdefault(prefix, set()).add(int(pin))
    return gpio, pinmux, adc


def found_pins(rule: tuple, gpio, pinmux, adc) -> tuple[str, set[int]]:
    kind = rule[0]
    if kind == "pinmux":
        return f"{rule[1]}_GPIO<n>", pinmux.get(rule[1], set())
    if kind == "adc":
        pins = set().union(*[p for names, p in adc if rule[1] in names] or [set()])
        return f"io-channels of {rule[1]}", pins
    prop, node = rule[1], rule[2] if len(rule) > 2 else None
    pins = set().union(*[p for pr, names, p in gpio if pr == prop and (node is None or node in names)]
                       or [set()])
    return f"{prop}" + (f" of {node}" if node else ""), pins


def check(board: str, spec: dict) -> tuple[list[str], int]:
    errors: list[str] = []
    design = design_pins(ROOT / spec["design"], spec["ref"])
    readme_path = ROOT / spec["readme"]
    readme = readme_pins(readme_path, errors)
    gpio, pinmux, adc = dt_pins(ROOT / "firmware/boards/hwtr" / board, spec["dts"])
    where = readme_path.relative_to(ROOT).as_posix()

    for n, net in sorted(design.items()):
        if n not in readme:
            errors.append(f"{where}: IO{n} ({net}) missing from the pin map")
        elif readme[n] != net:
            errors.append(f"{where}: IO{n} is {readme[n]!r}, design.py says {net!r}")
    for n, net in sorted(readme.items()):
        if n not in design:
            errors.append(f"{where}: IO{n} ({net}) is not connected on {spec['ref']} in design.py")

    for n, net in sorted(design.items()):
        if net in spec["fixed"] or net in spec.get("reserved", ()):
            continue
        if net not in spec["nets"]:
            errors.append(f"{board} devicetree: no rule for net {net!r} (IO{n}), add it to BOARDS")
            continue
        for rule in [spec["nets"][net], *spec["also"].get(net, [])]:
            what, found = found_pins(rule, gpio, pinmux, adc)
            if not found:
                errors.append(f"{board} devicetree: {what} for {net} (IO{n}) not found")
            elif found != {n}:
                pins = ", ".join(f"IO{p}" for p in sorted(found))
                errors.append(f"{board} devicetree: {what} for {net} is on {pins}, design.py says IO{n}")
    return errors, len(design)


def main() -> int:
    failed = False
    for board, spec in BOARDS.items():
        errors, count = check(board, spec)
        for e in errors:
            print(f"error: {e}")
        if errors:
            failed = True
        else:
            print(f"pin map OK: {count} {spec['ref']} GPIOs match {spec['readme']} and the {board} devicetree")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
