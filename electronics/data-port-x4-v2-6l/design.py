"""DATA ×4 v2 on 6 layers (JLC06161H-3313: F · GND · sig · sig · power · B), kept beside the rack's 4-layer build
(electronics/data-port-x4-v2) as its alternative: the same design, built with X4V2_LAYERS=6.

    tools/kicad.sh data-port-x4-v2-6l --check --fab

It was the rack's board from the HS review (2026-10-22) until the 4-layer one routed clean (2026-10-23): its
routing is that board's, unchanged.  In2 and In3 carry signals over GND and the power plane; JLC fills and caps
its vias for free, those in small parts' pads included (17, routed before the pipeline kept vias off SMD pads)."""

import importlib.util
import os
from pathlib import Path

_old = os.environ.get("X4V2_LAYERS")
os.environ["X4V2_LAYERS"] = "6"                 # read once, when the design's module loads
try:
    _spec = importlib.util.spec_from_file_location(
        "design_data_port_x4_v2_on_6", Path(__file__).resolve().parents[1] / "data-port-x4-v2" / "design.py")
    _v2 = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_v2)
finally:                                        # the rack's design, loaded later in this process, stays on 4
    if _old is None:
        del os.environ["X4V2_LAYERS"]
    else:
        os.environ["X4V2_LAYERS"] = _old

NETCLASSES = _v2.NETCLASSES


def board():
    b = _v2.board()
    b.name, b.title = "data-port-x4-v2-6l", "DATA ×4 v2, 6 layers"
    return b
