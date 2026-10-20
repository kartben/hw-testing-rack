"""Camera pod v1.0 — the board in each bay's camera pod, under the ceiling, beside the Arducam Mega.

It ties the camera and its light to the bay node's J6 with nothing to crimp or solder:

* J1, JST PH 8 (side entry) on the right edge: a ready-made double-ended PH 8 lead ("Same
  direction", pin n to pin 9−n) from the node's J6; its pinout here is J6's mirrored.
* J2, a 1 × 6 2.54 mm header in the Mega's own order (VCC GND SCK MISO MOSI CS, names on the
  silkscreen): the camera's own cable plugs onto it.
* The Mega runs from 3.3 V, an AMS1117 on CAM_5V: its MISO is then a 3.3 V output, whatever the
  camera does with a 5 V supply (the node keeps R35, its divider footprint, unpopulated).
* The light: four white 2835 LEDs along the edge next to the camera (beside the lens, not around
  it), each from CAM_5V through 100 Ω 0805 to LED_K, which the node's AO3400A pulls low: 18–26 mA
  each over the LEDs' Vf spread (≈ 2.65–3.2 V at that current) and CAM_5V 5.0–5.2 V, ≤ 66 mW in a
  125 mW resistor, ≤ 102 mA for the four (the PCBA review's P1: 56 Ω 0603 gave 36–44 mA and up to
  108 mW in 100 mW).  About a third less light than the 32 mA first planned: the Mega's
  auto-exposure takes it (≈ +0.6 EV).  A thin PETG diffuser goes 5–10 mm in front of them, in the pod.

Mounted components down (the LEDs face the bay), screwed into the printed pod with 2 × PT 2.6.
2 layers, 40 × 27 mm, both sides GND pours (config/rack.yaml › pcb.camera_pod).  KiCad
coordinates: y = 0 is the edge beside the camera (the LEDs), x = 40 the lead's edge.

Schematic: automatic layout (blocks).
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
CFG = RACK.raw["pcb"]["camera_pod"]
W, H = CFG["size"]
PH_EDGE = 4.9                       # JST PH side entry: footprint origin from the board edge


def P(x, y, rot=0, side="top"):
    return {"x": x, "y": y, "rot": rot, "side": side}


def board() -> Board:
    b = Board("camera-pod", "Camera pod", "1.0",
              comments=["The bay camera pod's board: lead in, the Arducam Mega's header, its 3.3 V, the light "
                        "(hw-testing-rack)",
                        "Generated from electronics/camera-pod/design.py — edit the Python, then regenerate"])
    b.root_notes = [
        "Camera pod v1.0 — PH 8 lead from the bay node's J6, 1 × 6 header for the Arducam Mega's cable,",
        "  AMS1117 3.3 V for the camera, four white 2835 LEDs switched by the node (LED_K).",
        "Lead pinout here: 1 LED_K · 2 CS · 3 MISO · 4 MOSI · 5 GND · 6 SCK · 7 GND · 8 CAM_5V",
        "  (the node's J6 mirrored: one 'Same direction' PH 8 cable).",
    ]
    s = b.sheet("Pod", "pod.kicad_sch", "Lead, camera header, 3.3 V, light")
    s.block("Lead from the bay node's J6 (JST PH 8, side entry)")
    part(s, "J1", "ph8", {"1": "LED_K", "2": "CS", "3": "MISO", "4": "MOSI", "5": "GND", "6": "SCK", "7": "GND",
                          "8": "CAM_5V"}, "LEAD", pcb=P(W - PH_EDGE, CFG["lead"], 90))
    s.part("#FLG01", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "CAM_5V"}, in_bom=False, on_board=False)
    s.part("#FLG02", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "GND"}, in_bom=False, on_board=False)
    s.block("The Arducam Mega's cable (1 × 6, 2.54 mm, its own order) and its 3.3 V")
    hx, hy = CFG["header"]
    part(s, "J2", "hdr6_smd", {"1": "+3V3", "2": "GND", "3": "SCK", "4": "MISO", "5": "MOSI", "6": "CS"}, "MEGA",
         pcb=P(hx, hy, 90))
    part(s, "U1", "ldo", {"VI": "CAM_5V", "VO": "+3V3", "GND": "GND"}, pcb=P(20.0, 13.0, 0))
    C(s, "C1", "10u", "CAM_5V", "GND", size="0805", pcb=P(26.5, 12.0, 90))
    C(s, "C2", "22u", "+3V3", "GND", size="1206", pcb=P(13.0, 14.0, 90))
    C(s, "C3", "100n", "+3V3", "GND", pcb=P(hx + 9.8, hy - 0.5, 90))
    s.block("Light: four white LEDs, 100 Ω each from CAM_5V, cathodes to LED_K (the node's low side)")
    for i, x in enumerate(CFG["leds"]):
        n = i + 1
        part(s, f"D{n}", "led_w2835", {"K": "LED_K", "A": f"LED_A{n}"}, pcb=P(x, CFG["led_y"], 0))
        R(s, f"R{n}", "100", "CAM_5V", f"LED_A{n}", size="0805", pcb=P(x, CFG["led_y"] + 4.2, 0))
    for i, (x, y) in enumerate(CFG["holes"]):
        part(s, f"H{i + 1}", "hole25", {}, "PT2.6", pcb=P(x, y, 0), in_bom=False)
    s.note("J1 is the bay node's J6 mirrored: a 'Same direction' PH 8 lead (pin n to pin 9−n) joins them.")
    s.note("J2 follows the Mega's own pin order; the names are on the silkscreen, its cable plugs on by name.")
    s.note("The Mega from 3.3 V (U1, ≈ 0.2 W at 120 mA): its MISO is 3.3 V.  LEDs 18–26 mA each (100 Ω 0805, ≤ 66 mW),")
    s.note("  ≤ 102 mA for the four, off unless the node's AO3400A pulls LED_K low (PWM ≥ 20 kHz or on/off).")
    s.note("CAM_5V: the node's 0.5 A PTC, no switch: a hung camera (the Mega has no reset pin) needs a power cycle.")

    b.pcb = {
        "size": (W, H), "layers": CFG["layers"], "corner_radius": 1.5, "passes": 40,
        "finish": "HASL",
        "edge_parts": ["J1"],
        "defer_pours": False,
        # nets carrying power (≳ 0.5 A): their IC, connector and big pads connect solid to the pours, small
        # parts keep reliefs (pcbgen.power_pads); the number is the spokes a relieved pad of theirs keeps
        "power_nets": {"GND": 1, "CAM_5V": 2},
        "zones": [
            {"layer": "F.Cu", "net": "GND"},
            {"layer": "B.Cu", "net": "GND"},
        ],
        "stitch": 3.0,
        "texts": [
            {"text": "VCC GND SCK MISO MOSI CS", "x": hx, "y": hy + 4.3, "size": 0.8},
            {"text": "CAM POD v1.0", "x": 6.0, "y": 9.6, "size": 0.8},
        ],
    }
    return b
