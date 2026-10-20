"""DATA port v1.0 — the drawer's USB-C port for the board under test.

A small board screwed, components up, to the floor of the drawer's rear bay: a USB-C
receptacle whose mouth looks through the port wall towards the board's plate, an 8-wire JST PH lead
to the bay node's DATA header (J7) through the drag chain.  It replaces the USB-C coupler and
the 90° extension cable.

* USB-C source: CC1 and CC2 each pulled up to VBUS through 56k (Rp, "default USB power"), as on
  the DATA ×4: VBUS is the node's DUT_5V (TPS2553D switch, INA226 shunt), limited at 1.34–1.52 A, so
  advertising 1.5 A (22k) would promise more than the switch's low end delivers (the PCBA review's D3,
  decided 2026-10-19).
* VBUS from the lead to the receptacle on 0.8 mm F.Cu drawn here (netclass Power), round the PH's
  pads under its housing and into J1's VBUS pads from behind, necked to 0.5 mm at the pad row: ≈ 15 mΩ
  instead of the routed 0.25 mm's ≈ 0.13 Ω (D1).  10 µF at the receptacle (C2), 100 nF at the lead's
  end (C1); thin tracks feed the Rp and the ESD's VBUS pin.
* USBLC6 ESD on D+/D− right at the receptacle, where the plugs go in.
* The lead: VBUS, GND, D+, D−, GND (the pair between two grounds), then the node's I²C and INT,
  which this board leaves open (a later DATA ×4 board uses them).  Its pinout here is the node
  header's mirrored, so the lead is the rack's one PH cable type ("Same direction": pin n to
  pin 9−n), the camera's 8-wire lead; 8 pins, so a 6-pin row cable cannot go in.
* USB 2.0 only: HS (480 Mb/s) PC ↔ board in classic mode, FS to the node's ESP32 otherwise.

2 layers, 40 × 17 mm, both sides GND pours (config/rack.yaml › pcb.data_port, set with the
drawer: the receptacle off-centre to the right, clear of the chain foot's lock screw; 17 mm deep for
the PH plug and the wires' turn in the rear bay).  KiCad coordinates: y = 0 is the REAR edge (the PH
lead), y = 17 the FRONT edge (the USB-C mouth).

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


def vbus_tracks():
    """VBUS, all of it drawn (Freerouting has none to do): J2.8 north under the PH's housing (between its
    pads and its mounting tabs), east, then down into J1's two VBUS pad pairs from behind, 0.8 mm necked to
    0.5 mm at the pad row (A4/B9 between GND and SBU2, A9/B4 between CC2 and GND); C2 on that run; thin
    tracks to the ESD's VBUS pin (between J2's pins 4 and 3), to C1 at the lead and on to the Rp."""
    tracks = []

    def t(w, *pts):
        tracks.append(("VBUS", "F.Cu", w, [(round(x, 4), round(y, 4)) for x, y in pts]))

    j8, ux = CFG["ph"] - 7.0, CFG["usb"]               # J2 pin 8 (rot 180: pin n at x = ph + 9 − 2n), J1
    a4, a9, row = ux - 2.4, ux + 2.4, 8.7              # J1's VBUS pad columns; the neck starts above the row
    t(0.8, (j8, 7.0), (j8, 4.7), (a4 - 1.5, 4.7), (a4, 6.2), (a4, row))
    t(0.5, (a4, row), (a4, 9.75))
    t(0.8, (a4, 7.2), (a9 - 0.5, 7.2), (a9, 7.7), (a9, row))
    t(0.5, (a9, row), (a9, 9.75))
    t(0.6, (ux - 0.95, 5.8), (ux - 0.95, 7.2))                                 # C2
    t(0.3, (CFG["ph"] + 2.0, H - 4.64), (CFG["ph"] + 2.0, 4.7))                # U1.5 (the ESD's VBUS)
    t(0.4, (j8, 9.0), (j8, 9.78), (j8 + 4.5, 14.28))                          # C1, by the lead
    t(0.3, (j8 + 4.5, 14.28), (j8 + 5.97, 15.75), (20.6, 15.75), (21.0, 15.35), (21.0, 13.72), (21.4, 13.32),
      (ux + 7.0, 13.32))                                                     # R1, R2 (under J1)
    return tracks


def board() -> Board:
    b = Board("data-port", "DATA port", "1.0",
              comments=["The drawer's USB-C port for the board under test, wired to the bay node (hw-testing-rack)",
                        "Generated from electronics/data-port/design.py — edit the Python, then regenerate"])
    b.root_notes = [
        "DATA port v1.0 — USB-C source (Rp 56k on CC1/CC2), USBLC6 ESD, 8-pin JST PH lead to the bay node's J7.",
        "Lead pinout here: 1 INT, 2 SCL, 3 SDA (all three open), 4 GND, 5 D−, 6 D+, 7 GND, 8 VBUS",
        "  (the node's J7 mirrored: one 'Same direction' PH 8 cable).",
    ]
    s = b.sheet("Port", "port.kicad_sch", "USB-C source, ESD, lead")
    s.block("USB-C receptacle (source): Rp 56k on each CC, the shell to GND, 10 µF on VBUS")
    part(s, "J1", "usbc5a", {"VBUS": "VBUS", "GND": "GND", "CC1": "CC1", "CC2": "CC2", "D+": "CONN_DP",
                             "D-": "CONN_DN", "SBU1": None, "SBU2": None, "SHIELD": "GND"},
         "DATA", pcb=P(CFG["usb"], H - 3.4, 0))
    R(s, "R1", "56k", "VBUS", "CC1", pcb=P(CFG["usb"] - 7.0, H - 4.5, 90))
    R(s, "R2", "56k", "VBUS", "CC2", pcb=P(CFG["usb"] + 7.0, H - 4.5, 90))
    # the bulk at the receptacle: the node's own is 45 cm away up the lead
    C(s, "C2", "10u", "VBUS", "GND", size="0805", pcb=P(CFG["usb"], 5.8, 0))
    s.block("ESD on the pair, at the receptacle")
    # D+ through 1/6, D− through 3/4: J2 has D+ west of D− (x 11.4 / 13.4), so the lead side runs straight
    part(s, "U1", "esd", {"6": "CONN_DP", "1": "LEAD_DP", "4": "CONN_DN", "3": "LEAD_DN", "5": "VBUS", "2": "GND"},
         pcb=P(CFG["ph"] + 2.0, H - 3.5, 90))
    C(s, "C1", "100n", "VBUS", "GND", pcb=P(CFG["ph"] - 2.5, H - 3.5, 90))
    s.block("Lead to the bay node's DATA header (J7): 4 GND, 5 D−, 6 D+, 7 GND, 8 VBUS; 1–3 (INT, I²C) open")
    part(s, "J2", "ph8", {"1": None, "2": None, "3": None, "4": "GND", "5": "LEAD_DN", "6": "LEAD_DP", "7": "GND",
                          "8": "VBUS"}, "LEAD",
         pcb=P(CFG["ph"], PH_EDGE, 180))
    s.part("#FLG01", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "VBUS"}, in_bom=False, on_board=False)
    s.part("#FLG02", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "GND"}, in_bom=False, on_board=False)
    for i, (x, y) in enumerate(CFG["holes"]):
        part(s, f"H{i + 1}", "hole25", {}, "PT2.6", pcb=P(x, y, 0), in_bom=False)
    s.note("Rp 56k to VBUS on CC1 and CC2: 'default USB power', as on the DATA ×4; not 22k (1.5 A): the node's")
    s.note("  TPS2553D switch (DUT_5V) limits at 1.34–1.52 A.  The node turns the board under test on and off.")
    s.note("The lead's pinout is the node's J7 mirrored: a 'Same direction' PH 8 cable (pin n to pin 9−n) joins them;")
    s.note("  pins 1–3 (the node's INT and I²C) stay open here.")

    b.pcb = {
        "size": (W, H), "layers": CFG["layers"], "corner_radius": 1.5, "passes": 40,
        "finish": "HASL",
        "edge_parts": ["J*"],
        "defer_pours": False,
        # nets carrying power (≳ 0.5 A): their IC, connector and big pads connect solid to the pours, small
        # parts keep reliefs (pcbgen.power_pads); the number is the spokes a relieved pad of theirs keeps
        "power_nets": {"GND": 1, "VBUS": 2},
        "zones": [
            {"layer": "F.Cu", "net": "GND"},
            {"layer": "B.Cu", "net": "GND"},
        ],
        "stitch": 3.0,
        "tracks": vbus_tracks(),
        # GCT's USB4105 footprint puts its GND pads 0.19 mm from its own NPTH pegs (the datasheet's land pattern)
        "dru": """
(rule "USB4105 J1: GND pads beside its own pegs"
	(condition "A.memberOfFootprint('J1') && B.memberOfFootprint('J1')")
	(constraint hole_clearance (min 0.19mm)))
""",
        "texts": [
            {"text": "DATA v1.0", "x": 7.0, "y": H - 3.0, "size": 0.8},
            # one label per pin, under it (rot 180: pin n at x = ph + 9 − 2n); 1–3 (INT, I²C) open
            *({"text": s, "x": CFG["ph"] + 9 - 2 * n, "y": 10.6, "size": 0.8}
              for n, s in ((8, "5V"), (7, "G"), (6, "D+"), (5, "D−"), (4, "G"), (3, "·"), (2, "·"), (1, "·"))),
        ],
    }
    return b


NETCLASSES = [
    {"name": "Power", "clearance": 0.2, "track_width": 0.8, "via_diameter": 0.8, "via_drill": 0.4,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 1,
     "_patterns": ["*VBUS"]},
]
