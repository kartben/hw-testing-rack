"""Load config/rack.yaml and derive every dimension the CAD, PCB and web views share."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "config" / "rack.yaml"
BOARDS = REPO / "mechanical" / "boards" / "boards.yaml"


@dataclass
class Bay:
    id: str
    row: int          # row index (0 = bottom)
    unit: int         # first unit (column) index
    span: int         # 1 = standard, 2 = double width
    index: int        # position within the row (0-based)


@dataclass
class Rack:
    raw: dict

    # ---- frame ---------------------------------------------------------
    @property
    def profile(self) -> float:
        return self.raw["frame"]["profile"]

    @property
    def depth(self) -> float:
        """Outer frame depth (Y)."""
        return self.raw["frame"]["depth"]

    @property
    def bay_depth(self) -> float:
        """Carrier depth along the slope (row Y)."""
        return self.raw["bay"]["depth"]

    @property
    def tilt(self) -> float:
        return float(self.raw["frame"].get("tilt", 0))

    @property
    def row_origin_y(self) -> float:
        return self.raw["frame"].get("row_origin_y", 0)

    @property
    def bracket(self) -> float:
        return self.raw["frame"].get("bracket", 0)

    @property
    def pitch(self) -> float:
        return self.raw["bay"]["pitch"]

    @property
    def rows(self) -> list[dict]:
        return self.raw["rows"]

    def layout(self, i: int) -> list[int]:
        r = self.rows[i]
        return r.get("layout") or [1] * r.get("bays", 4)

    @property
    def units(self) -> int:
        return max(sum(self.layout(i)) for i in range(len(self.rows)))

    @property
    def max_bays(self) -> int:  # kept for older callers: number of units
        return self.units

    @property
    def inner_x0(self) -> float:
        """X where the first carrier unit starts (inside posts + brackets)."""
        return self.profile + self.bracket

    @property
    def width(self) -> float:
        return 2 * self.inner_x0 + self.units * self.pitch

    @property
    def base_height(self) -> float:
        return self.raw["frame"]["base_height"]

    def row_z(self, i: int) -> float:
        """Frame Z of row i's origin (its front-bottom edge); i == len(rows) is the top cap."""
        return self.base_height + sum(r["height"] for r in self.rows[:i])

    @property
    def top_z(self) -> float:
        return self.row_z(len(self.rows))

    def row_matrix(self, i: int) -> tuple[list[float], float]:
        """(origin [x, y, z] in frame coords, tilt in degrees) of row i."""
        return [0.0, self.row_origin_y, self.row_z(i)], self.tilt

    def to_frame(self, i: int, p) -> list[float]:
        """Row-i coordinates → frame coordinates."""
        (ox, oy, oz), t = self.row_matrix(i)
        a = math.radians(t)
        x, y, z = p
        return [ox + x, oy + y * math.cos(a) - z * math.sin(a), oz + y * math.sin(a) + z * math.cos(a)]

    @property
    def row_stack_h(self) -> float:
        """Thickness of a row module below the bay floor: beams + carrier."""
        return self.profile + self.plenum

    @property
    def height(self) -> float:
        top = self.to_frame(len(self.rows), [0, self.bay_depth, self.row_stack_h])[2]
        return max(top, self.top_z + self.row_stack_h)

    # ---- bays -------------------------------------------------------------
    def bays(self):
        for i, r in enumerate(self.rows):
            u = 0
            for k, span in enumerate(self.layout(i)):
                yield Bay(f"{r['id']}{k + 1}", i, u, span, k)
                u += span

    def bay_ids(self):  # (row, index, id) for older callers
        for b in self.bays():
            yield b.row, b.index, b.id

    def unit_x(self, u: int) -> float:
        """X of the left edge of carrier unit u."""
        return self.inner_x0 + u * self.pitch + self.raw["bay"]["gap"] / 2

    def bay_x(self, j: int) -> float:
        return self.unit_x(j)

    # ---- carrier ------------------------------------------------------------
    @property
    def carrier(self) -> dict:
        return self.raw["bay"]["carrier"]

    @property
    def carrier_w(self) -> float:
        return self.pitch - self.raw["bay"]["gap"]

    @property
    def pcb_top(self) -> float:
        """Bay-node PCB top surface, above the carrier bottom."""
        c = self.carrier
        return c["bottom"] + c["standoff"] + self.raw["pcb"]["bay_node"]["thickness"]

    @property
    def plenum(self) -> float:
        """Carrier height: beam top → bay floor surface."""
        return self.pcb_top + self.carrier["pcb_to_floor"]

    @property
    def wall_h(self) -> float:
        return self.plenum - self.carrier["deck"]

    # ---- pcb placement --------------------------------------------------------
    @property
    def node(self) -> dict:
        return self.raw["pcb"]["bay_node"]

    @property
    def node_x0(self) -> float:
        return self.node["x0"]

    @property
    def node_front_y(self) -> float:
        return self.carrier["fascia"] + self.node["front_gap"]

    def node_to_carrier(self, kx: float, ky: float) -> tuple[float, float]:
        """KiCad coords on the bay node (y=0 rear edge) → carrier coords (y=0 front face)."""
        return self.node_x0 + kx, self.node_front_y + (self.node["size"][1] - ky)

    # ---- drawer / chain -------------------------------------------------------
    @property
    def drawer(self) -> dict:
        return self.raw["drawer"]

    @property
    def chain(self) -> dict:
        return self.raw["chain"]

    def drawer_w_span(self, span: int) -> float:
        d = self.drawer
        return span * self.pitch - self.raw["bay"]["gap"] - 2 * d["guide_width"] - 2 * d["clearance"]

    @property
    def drawer_w(self) -> float:
        return self.drawer_w_span(1)

    @property
    def data_port_x(self) -> list[float]:
        """X of the two DATA socket positions on the drawer's port wall (drawer coords)."""
        return [self.drawer_w * f for f in self.drawer["data_ports"]]

    @property
    def aux_port_x(self) -> float:
        return self.drawer_w * self.drawer["aux_port"]

    @property
    def drawer_x0(self) -> float:
        return (self.carrier_w - self.drawer_w) / 2

    def chain_state(self, open_frac: float) -> dict:
        """Geometry of the drag chain for a drawer pulled out by open_frac (0..1)."""
        c = self.chain
        t = self.drawer["travel"] * open_frac
        m = c["foot_y"] - t
        b = c["bend_y"] - t / 2
        return {"fixed": c["fixed"], "moving": [c["moving_x"], m], "bend_y": b, "radius": c["radius"]}


def load() -> Rack:
    return Rack(yaml.safe_load(CONFIG.read_text(encoding="utf-8")))


def load_boards() -> dict:
    if BOARDS.exists():
        return yaml.safe_load(BOARDS.read_text(encoding="utf-8"))["boards"]
    return {}


def scad_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return f"{v:g}"
    if isinstance(v, str):
        return '"' + v.replace('"', '\\"') + '"'
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(scad_value(x) for x in v) + "]"
    raise TypeError(v)


def scad_config(rack: Rack) -> str:
    r = rack.raw
    c = rack.carrier
    d = rack.drawer
    ch = rack.chain
    node = rack.node
    hub = r["pcb"]["power_hub"]
    vals = {
        "FRAME_PROFILE": rack.profile,
        "FRAME_W": rack.width,
        "FRAME_D": rack.depth,
        "FRAME_TILT": rack.tilt,
        "FRAME_ROW_Y0": rack.row_origin_y,
        "FRAME_BRACKET": rack.bracket,
        "FRAME_INNER_X0": rack.inner_x0,
        "FRAME_BASE_H": rack.base_height,
        "FRAME_FOOT_H": r["frame"]["foot_height"],
        "FRAME_TOP_Z": rack.top_z,
        "ROW_IDS": [row["id"] for row in rack.rows],
        "ROW_HEIGHTS": [row["height"] for row in rack.rows],
        "ROW_LAYOUTS": [rack.layout(i) for i in range(len(rack.rows))],
        "BAY_PITCH": rack.pitch,
        "BAY_GAP": r["bay"]["gap"],
        "CARRIER_W": rack.carrier_w,
        "CARRIER_D": rack.bay_depth,
        "CARRIER_BOTTOM": c["bottom"],
        "CARRIER_WALL": c["wall"],
        "CARRIER_STANDOFF": c["standoff"],
        "CARRIER_DECK": c["deck"],
        "CARRIER_FASCIA": c["fascia"],
        "CARRIER_WALL_H": rack.wall_h,
        "CARRIER_PLENUM": rack.plenum,
        "PCB_TO_FLOOR": c["pcb_to_floor"],
        "CAM_MOUNT": r["bay"]["camera_mount"],
        "DRAWER_D": d["depth"],
        "DRAWER_W": rack.drawer_w,
        "DRAWER_X0": rack.drawer_x0,
        "DRAWER_TRAVEL": d["travel"],
        "DRAWER_GUIDE_W": d["guide_width"],
        "DRAWER_CLEAR": d["clearance"],
        "DRAWER_BOTTOM": d["bottom"],
        "DRAWER_WALL": d["wall"],
        "DRAWER_WALL_H": d["wall_height"],
        "DRAWER_FRONT_H": d["front_height"],
        "DRAWER_FRONT_T": d["front_thickness"],
        "DRAWER_REAR_BAY": d["rear_bay"],
        "DRAWER_FLANGE": d["flange"],
        "DRAWER_MAGNET": d["magnet"],
        "DATA_PORT_X": [round(x, 3) for x in rack.data_port_x],
        "AUX_PORT_X": round(rack.aux_port_x, 3),
        "PLATE_T": d["plate"],
        "CHAIN_INNER": ch["inner"],
        "CHAIN_OUTER": ch["outer"],
        "CHAIN_R": ch["radius"],
        "CHAIN_FIXED": ch["fixed"],
        "CHAIN_MOVING_X": ch["moving_x"],
        "CHAIN_FOOT_Y": ch["foot_y"],
        "CHAIN_BEND_Y": ch["bend_y"],
        "NODE_SIZE": node["size"],
        "NODE_T": node["thickness"],
        "NODE_HOLES": node["holes"],
        "NODE_X0": rack.node_x0,
        "NODE_FRONT_Y": rack.node_front_y,
        "NODE_PCB_TOP": rack.pcb_top,
        "NODE_FRONT": [node["front"]["pc_port"], node["front"]["led"], node["front"]["svc"]],
        "NODE_VH_Y": node["vh_y"],
        "NODE_RIGHT": [node["right"]["dut"], node["right"]["aux"]],
        "NODE_CAM": node["cam"],
        "HUB_SIZE": hub["size"],
        "HUB_HOLES": hub["holes"],
    }
    lines = ["// GENERATED by tools/build.py from config/rack.yaml — do not edit.", ""]
    for k, v in vals.items():
        lines.append(f"{k} = {scad_value(v)};")
    return "\n".join(lines) + "\n"


def orient_board(b: dict) -> dict:
    """Rotate a library board so its debug USB edge faces the drawer rear (+Y), or, for boards
    marked `orient: side` (too long for a plug behind them), the drawer's right wall (+X).

    Returns a dict with w, l, holes, usb_side (False: rear, True: right), usb_x (centre of the
    USB along its edge: X on the rear edge, Y on the right edge) and, if present, usb2_x for a
    second connector on the same edge.
    """
    w, l = b["size"]
    edge = b.get("usb", {}).get("edge", "top")

    def tf(x, y):
        if edge == "top":
            return x, y
        if edge == "bottom":
            return w - x, l - y
        if edge == "left":
            return y, w - x
        if edge == "right":
            return l - y, x
        raise ValueError(edge)

    def along(pos, e):
        # position along the USB edge → oriented X
        if e == "top":
            return tf(pos, l)[0]
        if e == "bottom":
            return tf(pos, 0)[0]
        if e == "left":
            return tf(0, pos)[0]
        return tf(w, pos)[0]

    W, L = (w, l) if edge in ("top", "bottom") else (l, w)
    out = {
        "w": W, "l": L,
        "holes": [list(tf(x, y)) for x, y in b.get("holes", [])],
        "usb_x": along(b.get("usb", {}).get("pos", w / 2), edge),
    }
    if "second_usb" in b and b["second_usb"].get("edge", edge) == edge:
        out["usb2_x"] = along(b["second_usb"]["pos"], edge)
    out["usb_side"] = b.get("orient") == "side"
    if out["usb_side"]:
        # quarter turn clockwise (seen from above): the rear edge becomes the right edge
        out["holes"] = [[y, W - x] for x, y in out["holes"]]
        out["usb_x"] = W - out["usb_x"]
        if "usb2_x" in out:
            out["usb2_x"] = W - out["usb2_x"]
        out["w"], out["l"] = L, W
    return out
