"""Silkscreen marks the boards share: b.pcb["texts"] entries for design.py, drawn by pcbgen.PcbBuilder.texts().

The silkscreen plan (2026-11-02): every DATA port numbered the same way, a digit knocked out of a filled disc; the
lead's pins named where it plugs in; a title block.  JLC's limits (jlcpcb.com/capabilities/pcb-capabilities and its
character-design guide): a 0.15 mm line and text 1.0 mm tall (0.8 in its high-precision class); a hollow character
0.2 mm in stroke, 1.5 mm tall, 0.2 mm (0.25 recommended) from the ink round it.
"""
from __future__ import annotations

SILK_TEXT = 0.15        # mm: the least text stroke (the layout review, 2026-11-01)
SILK_RULE = f"""
(rule "silkscreen text: a {SILK_TEXT} mm stroke at least"
	(severity error)
	(layer "?.Silkscreen")
	(constraint text_thickness (min {SILK_TEXT}mm)))
"""

# a port's number: a 1.7 mm digit, 0.28 mm stroke, knocked out of a 3.0 mm disc
MARK_D, MARK_SIZE, MARK_STROKE = 3.0, 1.7, 0.28


def port_mark(n, x: float, y: float, layer: str = "F.SilkS", d: float = MARK_D, size: float = MARK_SIZE,
              stroke: float = MARK_STROKE) -> dict:
    """Port n's number at (x, y): the digit (or letter) knocked out of a filled silk disc d mm across."""
    assert stroke >= 0.2 and size >= 1.5, "a hollow character: 0.2 mm stroke and 1.5 mm tall at least (JLC)"
    assert (d - size) / 2 >= 0.25, "0.25 mm of disc at least round the character"
    return {"text": str(n), "x": x, "y": y, "size": size, "thickness": stroke, "layer": layer, "style": "disc",
            "d": d}


def lead_pin_names(x: float, y_pin1: float, names, pitch: float = 2.0, layer: str = "B.SilkS") -> list[dict]:
    """A PH lead's pin names, 1.0 mm tall, pin 1 at y_pin1 and the pins `pitch` apart up the board (−y), each at
    the same x and right-justified there (on B.SilkS, read from behind, that is against the housing)."""
    return [{"text": nm, "x": x, "y": y_pin1 - pitch * k, "size": 1.0, "thickness": SILK_TEXT, "layer": layer,
             "just": "right"} for k, nm in enumerate(names)]


def title_block(name: str, x: float, y: float, line2: str | None = None, layer: str = "F.SilkS",
                dx2: float = 0.0, dy2: float = 2.0) -> list[dict]:
    """The board's name and revision at 1.5 mm, and a second line (the project, the date, fixed per revision:
    never the build's) at 1.0 mm, dx2 / dy2 mm from it."""
    out = [{"text": name, "x": x, "y": y, "size": 1.5, "thickness": 0.25, "layer": layer}]
    if line2:
        out.append({"text": line2, "x": x + dx2, "y": y + dy2, "size": 1.0, "thickness": SILK_TEXT, "layer": layer})
    return out
