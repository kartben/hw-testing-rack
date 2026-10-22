"""DATA ×4 v2 on 4 layers (JLC04161H-7628: F · GND · power · B), kept beside the rack's 6-layer build
(electronics/data-port-x4-v2) as its cheaper alternative: the same design, built with X4V2_LAYERS=4.

    tools/kicad.sh data-port-x4-v2-4l --check --fab

Routed by the Freerouting portfolio (docs/autorouting-benchmark.md, "The DATA ×4 v2 on 4 layers"): 0 open,
copper DRC 0, parity 0.  Its only vias in pads are the 8 drawn in the QFNs' thermal pads, fine unfilled: JLC
fills and caps vias for free only from 6 layers, and no via sits in a small part's or a pin's pad."""

import importlib.util
import os
from pathlib import Path

_old = os.environ.get("X4V2_LAYERS")
os.environ["X4V2_LAYERS"] = "4"                 # read once, when the 6-layer design's module loads
try:
    _spec = importlib.util.spec_from_file_location(
        "design_data_port_x4_v2_on_4", Path(__file__).resolve().parents[1] / "data-port-x4-v2" / "design.py")
    _v2 = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_v2)
finally:                                        # the 6-layer design, loaded later in this process, stays on 6
    if _old is None:
        del os.environ["X4V2_LAYERS"]
    else:
        os.environ["X4V2_LAYERS"] = _old

NETCLASSES = _v2.NETCLASSES


def board():
    b = _v2.board()
    b.name, b.title = "data-port-x4-v2-4l", "DATA ×4 v2, 4 layers"
    return b
