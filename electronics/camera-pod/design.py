"""Camera pod v1.0 — the board in each bay's camera pod, under the ceiling, beside the Arducam Mega.

It ties the camera and its light to the bay node's J6 with nothing to crimp or solder:

* J1, JST PH 8 (side entry) on the right edge: a ready-made double-ended PH 8 lead ("Same
  direction", pin n to pin 9−n) from the node's J6; its pinout here is J6's mirrored, GND on both end
  pins (1 GND · 2 CS · 3 LED_K · 4 MISO · 5 MOSI · 6 CAM_5V · 7 SCK · 8 GND, node v1.0): this lead
  plugged into the node's DATA socket J7 by mistake puts the node's eFused 20 V on this board's GND
  only, between two of its pins, a short the node's eFuse cuts; a 1:1 lead in J6 puts CAM_5V on the
  LEDs' cathodes (pin 3), not on a camera line.
* J2, a 1 × 6 2.54 mm header in the Mega's own order (VCC GND SCK MISO MOSI CS, names on the
  silkscreen): the camera's own cable plugs onto it.
* The Mega runs from 3.3 V, an AP2114H on CAM_5V: its MISO is then a 3.3 V output, whatever the
  camera does with a 5 V supply (the node keeps R35, its divider footprint, unpopulated).  It draws up
  to 317 mA (Arducam): ≈ 0.5 W in U1, so its tab gets a top-side +3V3 pour and, through three vias, a
  bottom-side island: all the copper the routing leaves round it (schematic review S6).
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
from silk import LOGO_W, POD_TITLE_SCALE, SILK_RULE, SILK_TEXT, title_block  # noqa: E402

import rackcfg  # noqa: E402

RACK = rackcfg.load()
CFG = RACK.raw["pcb"]["camera_pod"]
W, H = CFG["size"]
PH_EDGE = 4.9                       # JST PH side entry: footprint origin from the board edge


def P(x, y, rot=0, side="top"):
    return {"x": x, "y": y, "rot": rot, "side": side}


# The DFT test pads, second round (the kicad-happy review's CP-3, 2026-10-27): the camera SPI and the LEDs' switched
# cathode on bare 1.0 mm bottom pads, by J1 where those lines come in, clear of the LDO's +3V3 island on B.Cu.  Each
# on a new drawn via on its net's F.Cu track, so no routing moves.  (net, (x, y), label)
TP_ROUND2 = [
    ("SCK", (29.7886, 11.9593), "SCK"),
    ("MOSI", (28.7148, 14.5445), "MOSI"),
    ("MISO", (25.6824, 18.8196), "MISO"),
    ("CS", (29.493, 19.2218), "CS"),
    ("LED_K", (35.3, 9.0), "LED"),           # on LED_K's new feed east of J1 (node v1.0), 14.3 before
]

# The fiducials: three on the top face, the only one a machine places parts on, as far apart as the board leaves
# room.  This board is too small for the 3 mm of clear board round each that the larger ones keep: here 2.3 mm
# at least (1.15 mm from the centre to any other copper, courtyards apart), and two of them 1.75 mm from an edge.
FIDUCIALS = [(27.5, 3.5), (1.75, 22.5), (38.0, 25.25)]

def board() -> Board:
    b = Board("camera-pod", "Camera pod", "1.0",
              comments=["The bay camera pod's board: lead in, the Arducam Mega's header, its 3.3 V, the light "
                        "(hw-testing-rack)",
                        "Generated from electronics/camera-pod/design.py — edit the Python, then regenerate"])
    b.root_notes = [
        "Camera pod v1.0 — PH 8 lead from the bay node's J6, 1 × 6 header for the Arducam Mega's cable,",
        "  AP2114H 3.3 V for the camera, four white 2835 LEDs switched by the node (LED_K).",
        "Lead pinout here: 1 GND · 2 CS · 3 LED_K · 4 MISO · 5 MOSI · 6 CAM_5V · 7 SCK · 8 GND",
        "  (the node's J6 mirrored: one 'Same direction' PH 8 cable).",
    ]
    s = b.sheet("Pod", "pod.kicad_sch", "Lead, camera header, 3.3 V, light")
    s.block("Lead from the bay node's J6 (JST PH 8, side entry)")
    part(s, "J1", "ph8", {"1": "GND", "2": "CS", "3": "LED_K", "4": "MISO", "5": "MOSI", "6": "CAM_5V", "7": "SCK",
                          "8": "GND"}, "LEAD", pcb=P(W - PH_EDGE, CFG["lead"], 90))
    s.part("#FLG01", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "CAM_5V"}, in_bom=False, on_board=False)
    s.part("#FLG02", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "GND"}, in_bom=False, on_board=False)
    s.block("The Arducam Mega's cable (1 × 6, 2.54 mm, its own order) and its 3.3 V")
    hx, hy = CFG["header"]
    part(s, "J2", "hdr6_smd", {"1": "+3V3", "2": "GND", "3": "SCK", "4": "MISO", "5": "MOSI", "6": "CS"}, "MEGA",
         pcb=P(hx, hy, 90))
    # the AP2114H-3.3 (ldo_1a, the node's U2): stable with the ceramic C2, where the AMS1117 was specified only
    # with 22 µF tantalum; the same SOT-223 pinout (1 GND, 2 VOUT and tab, 3 VIN), copper and CPL correction
    # (datasheet audit F1).  Order the AP2114H, never the HA: the HA's pinout differs
    part(s, "U1", "ldo_1a", {"VI": "CAM_5V", "VO": "+3V3", "GND": "GND"}, pcb=P(20.0, 13.0, 0))
    # each beside its own pin (decoupling check, the layout review): C1 left of VI (pin 3), C2 right of the tab (VOUT),
    # high enough that SCK keeps its F.Cu diagonal below it; each with a GND via beside its GND pad
    C(s, "C1", "10u", "CAM_5V", "GND", size="0805", pcb=P(13.75, 15.3, 180))
    C(s, "C2", "22u", "+3V3", "GND", size="1206", pcb=P(26.6, 11.4, 90))
    # the camera's 100 nF right above its VCC pin (J2.1, at hx − 6.35), its GND via above it
    C(s, "C3", "100n", "+3V3", "GND", pcb=P(hx - 6.35, hy - 5.0, 90))
    s.block("Light: four white LEDs, 100 Ω each from CAM_5V, cathodes to LED_K (the node's low side)")
    for i, x in enumerate(CFG["leds"]):
        n = i + 1
        part(s, f"D{n}", "led_w2835", {"K": "LED_K", "A": f"LED_A{n}"}, pcb=P(x, CFG["led_y"], 0))
        R(s, f"R{n}", "100", "CAM_5V", f"LED_A{n}", size="0805", pcb=P(x, CFG["led_y"] + 4.2, 0))
    for i, (x, y) in enumerate(CFG["holes"]):
        part(s, f"H{i + 1}", "hole25", {}, "PT2.6", pcb=P(x, y, 0), in_bom=False)
    for i, (x, y) in enumerate(FIDUCIALS):
        part(s, f"FID{i + 1}", "fiducial", {}, pcb=P(x, y, 0), in_bom=False)
    s.block("Test pads (bottom side, labelled): no short to GND, then CAM_5V and 3.3 V at power-up")
    # bare 1.5 mm pads, no part, no paste, out of the BOM (the bring-up DFT rule, 2026-10-26)
    for i, net in enumerate(("GND", "CAM_5V", "+3V3")):
        part(s, f"TP{i + 1}", "testpad", {"1": net}, net, pcb=P(6.0 + 3 * i, 21.5, 0, "bottom"), in_bom=False)
    part(s, "TP4", "testpad", {"1": "GND"}, "GND", pcb=P(33.0, 21.5, 0, "bottom"), in_bom=False)    # GND, spread
    for i, (net, xy, _) in enumerate(TP_ROUND2):
        part(s, f"TP{5 + i}", "testpad1", {"1": net}, net, pcb=P(*xy, 0, "bottom"), in_bom=False)
    s.note("J1 is the bay node's J6 mirrored: a 'Same direction' PH 8 lead (pin n to pin 9−n) joins them.")
    s.note("J2 follows the Mega's own pin order; the names are on the silkscreen, its cable plugs on by name.")
    s.note("The Mega from 3.3 V (U1, ≈ 0.5 W at its 317 mA max, Arducam): its MISO is 3.3 V.  LEDs 18–26 mA each (100 Ω 0805, ≤ 66 mW),")
    s.note("  ≤ 102 mA for the four, off unless the node's AO3400A pulls LED_K low (PWM ≥ 20 kHz or on/off).")
    s.note("CAM_5V: the node's 0.75 A PTC, no switch: a hung camera (the Mega has no reset pin) needs a power cycle.")

    b.pcb = {
        "size": (W, H), "layers": CFG["layers"], "corner_radius": 1.5, "passes": 40,
        "finish": "HASL",
        "edge_parts": ["J1"],
        "defer_pours": False,
        # nets carrying power (≳ 0.5 A): their IC, connector and big pads connect solid to the pours, small
        # parts keep reliefs (pcbgen.power_pads); the number is the spokes a relieved pad of theirs keeps
        "power_nets": {"GND": 1, "CAM_5V": 2},
        # no net classes: the default 0.25 mm carries CAM_5V's ≤ 0.42 A (the Mega's 317 mA, the LEDs' 102 mA) and
        # +3V3's ≤ 0.32 A with ≈ 2 °C rise; +3V3's only 0.187 mm stretch is C2's branch
        # each decoupling capacitor and the power pin it serves: within 2 mm of it, its GND within 1 mm of a via
        # (electronics/tools/decoupling.py, the layout review, 2026-10-28).  Bulk, bootstrap and RC capacitors
        # serve no one pin: left out
        "decoupling": {"C1": "U1.VI", "C2": "U1.VO", "C3": "J2.1"},
        "zones": [
            {"layer": "F.Cu", "net": "GND"},
            {"layer": "B.Cu", "net": "GND"},
            # U1's tab (VOUT): up to ≈ 0.5 W with the Mega at 317 mA.  Top-side copper round the tab between
            # the CAM_5V tracks, and a bottom-side island right of SCK, joined by three vias beside the tab
            {"layer": "F.Cu", "net": "+3V3", "connection": "solid", "name": "ldo-tab", "priority": 2, "exclusive": 0.4,
             "poly": [(21.4, 10.95), (25.4, 10.95), (25.4, 16.8), (21.4, 16.8)]},
            {"layer": "B.Cu", "net": "+3V3", "connection": "solid", "name": "ldo-tab-b", "priority": 2, "exclusive": 0.4,
             "poly": [(22.2, 11.8), (27.6, 11.8), (27.6, 17.2), (22.2, 17.2)]},
        ],
        "vias": [("+3V3", 24.75, 12.6), ("+3V3", 24.75, 13.6), ("+3V3", 24.75, 14.6),
                 ("GND", 11.7, 15.3), ("GND", 26.0, 8.75), ("GND", hx - 6.35, hy - 7.0),   # C1, C2, C3's returns
                 *[(net, *xy) for net, xy, _ in TP_ROUND2]],          # the second round's test pads
        # the pin → cap → via rule (the layout review): J2.1 (the camera's VCC) reaches its rail only through C3, the
        # 100 nF right above it.  The rail (no plane on this board) comes in on C3's far side, at the end of its stub
        "tracks": [("+3V3", "F.Cu", 0.4, [(hx - 6.35, hy - 1.66), (hx - 6.35, hy - 4.225)]),
                   ("+3V3", "F.Cu", 0.4, [(hx - 6.35, hy - 4.225), (hx - 5.25, hy - 4.225)]),
                   # J1's lead pins (node v1.0), each one pin up from before: SCK from J1.7 west and down to its
                   # test pad, then its old diagonal; MOSI (J1.5) and MISO (J1.4) straight onto their old diagonals;
                   # CAM_5V (J1.6) and LED_K (J1.3) out of their pads' east ends and north past J1.7–J1.8
                   ("SCK", "F.Cu", 0.25, [(32.25, 8.0), (29.7886, 8.0), (29.7886, 11.9593)]),
                   ("SCK", "F.Cu", 0.25, [(29.7886, 11.9593), (24.6233, 17.1246)]),
                   ("MOSI", "F.Cu", 0.25, [(32.25, 12.0), (31.2593, 12.0), (29.2593, 14.0)]),
                   ("MISO", "F.Cu", 0.25, [(32.25, 14.0), (30.502, 14.0), (28.502, 16.0)]),
                   ("CAM_5V", "F.Cu", 0.4, [(32.25, 10.0), (34.5, 10.0), (34.5, 4.9), (28.5, 4.9)]),
                   # … and on to R4 under its LED_A4 pad, where its feed from J1.8 ran
                   ("CAM_5V", "F.Cu", 0.25, [(28.5, 4.9), (25.0, 8.42), (23.1075, 8.42), (22.0875, 7.4)]),
                   ("LED_K", "F.Cu", 0.3, [(32.25, 16.0), (34.8, 16.0), (35.3, 15.5), (35.3, 9.0)]),
                   ("LED_K", "F.Cu", 0.3, [(35.3, 9.0), (35.3, 4.2), (33.7, 2.6)])],
        "stitch": 3.0,
        # every text at a 0.15 mm stroke at least, as the other boards (NextPCB's least line; SILK_RULE holds it);
        # the pours 0.5 mm from the edge (tracks and pads keep 0.3, J1 over it on purpose): NextPCB assembles the
        # pod in a 1 × 2 panel on mouse-bite tabs, and a bite must not nick or bare a pour
        "dru": SILK_RULE + """
(rule "pours 0.5 mm from the board edge (mouse bites)"
	(condition "A.Type == 'Zone'")
	(constraint edge_clearance (min 0.5mm)))
""",
        "texts": [{**t, "thickness": max(SILK_TEXT, 0.15 * t["size"])} for t in [
            {"text": "VCC GND SCK MISO MOSI CS", "x": hx, "y": hy + 4.3, "size": 0.8},
            *({"text": t, "x": 6.0 + 3 * i, "y": 19.6, "size": 0.8, "layer": "B.SilkS"}
              for i, t in enumerate(("GND", "5V", "3V3"))),
            {"text": "GND", "x": 33.0, "y": 19.6, "size": 0.8, "layer": "B.SilkS"},
            *({"text": lab, "x": x, "y": y + 1.35, "size": 0.8, "layer": "B.SilkS"} for _, (x, y), lab in TP_ROUND2),
        ]] + [
            # the title block, as on every board (silk.title_block()): in the rear face's top-right corner as read
            # from below, against the rear edge and 3 mm in, between H1 and the SCK test pad (the board's one band
            # free for it; its 0.6 mm logo-to-line gap is set by this band).  Scaled to POD_TITLE_SCALE, the
            # largest that keeps H1's screw head clear (its courtyard + 0.5 mm), 1 mm of other silk (TP5's ring,
            # the LED and SCK names), 0.3 mm of pads and holes (silkair.py); its line 0.07 mm past the logo
            *title_block("CAM POD v1.0", 1 + 3 + 0.07 + LOGO_W * POD_TITLE_SCALE, 1, scale=POD_TITLE_SCALE),
        ],
    }
    return b
