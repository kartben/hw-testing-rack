"""DATA port v1.0 — the drawer's USB-C port for the board under test.

A small board screwed, components down, under a shelf of the drawer's port wall: a USB-C
receptacle whose mouth looks out of the wall towards the board's plate, a 5-wire JST PH lead
to the bay node's DATA header (J7) through the drag chain.  It replaces the USB-C coupler and
the 90° extension cable.

* USB-C source: CC1 and CC2 each pulled up to VBUS through 22k (Rp, 1.5 A at 5 V), as the
  node's own DUT port; VBUS is the node's DUT_5V (TPS2553 switch, INA226 shunt).
* USBLC6 ESD on D+/D− right at the receptacle, where the plugs go in.
* The lead: VBUS, GND, D−, D+, GND (the pair between two grounds).  Its pinout here is the node
  header's mirrored, so the lead is the rack's one PH cable type ("Same direction": pin n to
  pin 6−n); 5 pins, so a 6-pin row cable cannot go in.
* USB 2.0 only: HS (480 Mb/s) PC ↔ board in classic mode, FS to the node's ESP32 otherwise.

2 layers, 40 × 20 mm, both sides GND pours (config/rack.yaml › pcb.data_port).  KiCad
coordinates: y = 0 is the REAR edge (the PH lead), y = 20 the FRONT edge (the USB-C mouth).

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
CFG = RACK.raw["pcb"]["data_port"]
W, H = CFG["size"]
PH_EDGE = 4.9                       # JST PH side entry: footprint origin from the board edge


def P(x, y, rot=0, side="top"):
    return {"x": x, "y": y, "rot": rot, "side": side}


def board() -> Board:
    b = Board("data-port", "DATA port", "1.0",
              comments=["The drawer's USB-C port for the board under test, wired to the bay node (hw-testing-rack)",
                        "Generated from electronics/data-port/design.py — edit the Python, then regenerate"])
    b.root_notes = [
        "DATA port v1.0 — USB-C source (Rp 22k on CC1/CC2), USBLC6 ESD, 5-pin JST PH lead to the bay node's J7.",
        "Lead pinout here: 1 GND, 2 D+, 3 D−, 4 GND, 5 VBUS (the node's J7 mirrored: one 'Same direction' PH cable).",
    ]
    s = b.sheet("Port", "port.kicad_sch", "USB-C source, ESD, lead")
    s.block("USB-C receptacle (source): Rp 22k on each CC, the shell to GND")
    part(s, "J1", "usbc5a", {"VBUS": "VBUS", "GND": "GND", "CC1": "CC1", "CC2": "CC2", "D+": "CONN_DP",
                             "D-": "CONN_DN", "SBU1": None, "SBU2": None, "SHIELD": "GND"},
         "DATA", pcb=P(CFG["usb"], H - 3.4, 0))
    R(s, "R1", "22k", "VBUS", "CC1", pcb=P(CFG["usb"] - 7.0, H - 5.6, 90))
    R(s, "R2", "22k", "VBUS", "CC2", pcb=P(CFG["usb"] + 7.0, H - 5.6, 90))
    s.block("ESD on the pair, at the receptacle")
    part(s, "U1", "esd", {"6": "CONN_DN", "1": "LEAD_DN", "4": "CONN_DP", "3": "LEAD_DP", "5": "VBUS", "2": "GND"},
         pcb=P(CFG["usb"] + 9.5, 10.2, 90))
    C(s, "C1", "100n", "VBUS", "GND", pcb=P(CFG["usb"] - 9.5, 10.2, 90))
    s.block("Lead to the bay node's DATA header (J7): 1 GND, 2 D+, 3 D−, 4 GND, 5 VBUS")
    part(s, "J2", "ph5", {"1": "GND", "2": "LEAD_DP", "3": "LEAD_DN", "4": "GND", "5": "VBUS"}, "LEAD",
         pcb=P(CFG["ph"], PH_EDGE, 180))
    s.part("#FLG01", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "VBUS"}, in_bom=False, on_board=False)
    s.part("#FLG02", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "GND"}, in_bom=False, on_board=False)
    for i, (x, y) in enumerate(CFG["holes"]):
        part(s, f"H{i + 1}", "hole25", {}, "PT2.6", pcb=P(x, y, 0), in_bom=False)
    s.note("Rp 22k to VBUS on CC1 and CC2: a USB-C source advertising 1.5 A, as the bay node's own DUT port;")
    s.note("  VBUS comes from the node's TPS2553 switch (DUT_5V), so the node turns the board under test on and off.")
    s.note("The lead's pinout is the node's J7 mirrored: a 'Same direction' PH cable (pin n to pin 6−n) joins them.")

    b.pcb = {
        "size": (W, H), "layers": CFG["layers"], "corner_radius": 1.5, "passes": 40,
        "finish": "HASL",
        "edge_parts": ["J*"],
        "defer_pours": False,
        "zones": [
            {"layer": "F.Cu", "net": "GND"},
            {"layer": "B.Cu", "net": "GND"},
        ],
        "stitch": 3.0,
        # GCT's USB4105 footprint puts its GND pads 0.19 mm from its own NPTH pegs (the datasheet's land pattern)
        "dru": """
(rule "USB4105 J1: GND pads beside its own pegs"
	(condition "A.memberOfFootprint('J1') && B.memberOfFootprint('J1')")
	(constraint hole_clearance (min 0.19mm)))
""",
        "texts": [
            {"text": "DATA v1.0", "x": 7.0, "y": 16.2, "size": 0.8},
            {"text": "VBUS GND D− D+ GND", "x": CFG["ph"], "y": 10.5, "size": 0.8},
        ],
    }
    return b
