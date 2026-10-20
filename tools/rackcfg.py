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


# ---- the boards under test in a bay (config/rack.yaml › population) ------------------------------------
MAX_SLOTS = 4           # a DATA ×4 board in the drawer: four DUTs on one bay node (docs/multi-dut-node.md)
ROLES = ("analyzer",)   # a sub-slot's board that is no board under test: gusmanb's logic analyzer on a Pico 2
                        # (config/rack.yaml › analyzer, docs/multi-dut-node.md › "A logic analyzer in a sub-slot")
PLATE_KINDS = ("pegs", "boards")   # a bay's plate: "pegs" (default), the one honeycomb plate for every board,
                            # the boards held by clip-in pegs (tools/plate_layout.py); "boards", a converted bay's
                            # own plate with each board's standoffs or fences at its `at` (board_plate.scad › BAY)
NODE_BUTTONS = ((7.5, 21.5), (15.5, 21.5))   # the node's RESET and BOOT (KiCad), lib/carrier.scad NODE_RESET, NODE_BOOT
BUTTON_HOLE_R = 1.6     # the plate's pin holes over them (Ø3.2)
BUTTON_CLEAR = 3.0      # a board's footprint stays this far from those holes: a pin must reach the buttons
BOARD_PAD = 2.5         # a board's footprint beyond its outline: fences (2.3), standoffs over edge holes
BOARD_GAP = 7.0         # packing: between two boards' outlines
REAR_GAP_MAX = 26.0     # board_plate.scad: room for the USB plug and the cable's bend behind a board


@dataclass
class Slot:
    """One board under test.  A bay with one board (`board:`, today's form) is one Slot named like the bay;
    a converted bay (`boards:`) has up to four, named <bay>.<n>, n the DATA ×4 port it is plugged into."""
    id: str                   # "A1", or "A1.2"
    bay: str                  # "A1"
    slot: int | None          # the DATA ×4 port (1-4); None: a one-board bay
    board: str                # boards.yaml id
    cable: str | None = None  # config/rack.yaml › cables id
    at: list | None = None    # its front-left corner on the bay's plate (mm, turned like the board), or packed
    orient: str | None = None # a converted bay's board: USB to the port wall ("rear", the default) or "side"
    role: str | None = None   # None: a board under test; "analyzer": the bay's logic analyzer (ROLES)


def dut_slots(bay_id: str, entry: dict | None) -> list[Slot]:
    """The boards a population entry puts in a bay, in port order; [] for an empty bay.  ValueError when the
    entry mixes `board` and `boards`, has more than four boards, or reuses or overflows a port."""
    e = entry or {}
    if "boards" in e:
        if e.get("board"):
            raise ValueError(f"{bay_id}: `board` and `boards` both set: one or the other")
        items = e.get("boards") or []
        if not 1 <= len(items) <= MAX_SLOTS:
            raise ValueError(f"{bay_id}: `boards` holds 1 to {MAX_SLOTS} boards, not {len(items)}")
        out = {}
        for k, it in enumerate(items, 1):
            n = int((it or {}).get("slot", k))
            if not 1 <= n <= MAX_SLOTS:
                raise ValueError(f"{bay_id}: slot {n}: DATA ×4 ports are 1 to {MAX_SLOTS}")
            if n in out:
                raise ValueError(f"{bay_id}: two boards on slot {n}")
            if not (it or {}).get("board"):
                raise ValueError(f"{bay_id}.{n}: no `board`")
            at = it.get("at")
            if at is not None and (not isinstance(at, (list, tuple)) or len(at) != 2):
                raise ValueError(f"{bay_id}.{n}: `at` is [x, y] on the plate (mm)")
            orient = it.get("orient")
            if orient not in (None, "rear", "side"):
                raise ValueError(f"{bay_id}.{n}: orient {orient!r}: rear or side")
            role = it.get("role")
            if role not in (None, *ROLES):
                raise ValueError(f"{bay_id}.{n}: role {role!r}: {', '.join(ROLES)} (or none: a board under test)")
            out[n] = Slot(f"{bay_id}.{n}", bay_id, n, it["board"], it.get("cable"),
                          [float(v) for v in at] if at else None, orient, role)
        return [out[n] for n in sorted(out)]
    if e.get("board"):
        if e.get("role"):
            raise ValueError(f"{bay_id}: `role` is a sub-slot's (`boards:`): an analyzer watches its neighbours")
        return [Slot(bay_id, bay_id, None, e["board"], e.get("cable"))]
    return []


def split_slot(name: str) -> tuple[str, int | None]:
    """"B3.2" -> ("B3", 2); "B3" -> ("B3", None)."""
    bay, dot, n = name.upper().partition(".")
    if not dot:
        return bay, None
    if not n.isdigit():
        raise ValueError(f"{name}: a sub-slot is <bay>.<1-{MAX_SLOTS}>")
    return bay, int(n)


@dataclass
class Rack:
    raw: dict

    # ---- frame (the panel frame: ladders, trays, braces) ----------------
    @property
    def panel_t(self) -> float:
        """Ladder thickness (X)."""
        return self.raw["frame"]["panel_thickness"]

    @property
    def panel_clear(self) -> float:
        """Tray wall ↔ ladder face, per side."""
        return self.raw["frame"]["panel_clearance"]

    @property
    def bay_depth(self) -> float:
        """Tray depth along the slope (row Y)."""
        return self.raw["bay"]["depth"]

    @property
    def tilt(self) -> float:
        return float(self.raw["frame"].get("tilt", 0))

    @property
    def row_origin_y(self) -> float:
        return self.raw["frame"].get("row_origin_y", 0)

    @property
    def pitch(self) -> float:
        """Column pitch: a tray, a ladder and two clearances."""
        return self.carrier_w + self.panel_t + 2 * self.panel_clear

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
        """X where the first tray starts (right of the leftmost ladder)."""
        return self.panel_t + self.panel_clear

    @property
    def width(self) -> float:
        return self.units * self.pitch + self.panel_t

    @property
    def rear_y(self) -> float:
        """Frame Y of the ladders' rear edges (the braces sit behind them)."""
        return self.row_origin_y + self.bay_depth * math.cos(math.radians(self.tilt))

    @property
    def depth(self) -> float:
        """Overall depth (Y): ladders and the 3 mm braces behind them."""
        return self.rear_y + 3.0

    @property
    def base_height(self) -> float:
        return self.raw["frame"]["base_height"]

    def row_z(self, i: int) -> float:
        """Frame Z of row i's origin (its front-bottom edge); i == len(rows) is the cap strip."""
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
    def height(self) -> float:
        """Top of the cap strips (an 18 mm band on the top row's line), at the rear."""
        return self.to_frame(len(self.rows), [0, self.bay_depth, 18])[2]

    # ---- bays -------------------------------------------------------------
    def bays(self):
        for i, r in enumerate(self.rows):
            u = 0
            for k, span in enumerate(self.layout(i)):
                yield Bay(f"{r['id']}{k + 1}", i, u, span, k)
                u += span

    MOUNTS = ("drawer", "sled", "fixed")

    def mount(self, bay_id: str) -> str:
        """How a bay holds its board (population › mount): a drawer on a drag chain (the default), or a sled
        (the drawer's front, no chain) with a port block locked behind it, its own sled locked too if fixed."""
        m = self.raw.get("population", {}).get(bay_id, {}).get("mount", "drawer")
        if m not in self.MOUNTS:
            raise ValueError(f"{bay_id}: mount {m!r}, not one of {self.MOUNTS}")
        return m

    def duts(self, bay_id: str) -> list[Slot]:
        """The boards under test in a bay (see dut_slots)."""
        return dut_slots(bay_id, self.raw.get("population", {}).get(bay_id))

    def is_multi(self, bay_id: str) -> bool:
        """A converted bay: its drawer holds a DATA ×4 board and up to four boards (`boards:`)."""
        return "boards" in (self.raw.get("population", {}).get(bay_id) or {})

    def plate_kind(self, bay_id: str) -> str:
        """A bay's plate (population › plate): "pegs", the honeycomb plate and its pegs (every bay unless it says
        otherwise), or "boards", a converted bay's own plate with its boards' standoffs or fences."""
        k = (self.raw.get("population", {}).get(bay_id) or {}).get("plate", "pegs")
        if k not in PLATE_KINDS:
            raise ValueError(f"{bay_id}: plate {k!r}, not one of {PLATE_KINDS}")
        return k

    # ---- the board plate (lib/carrier.scad: plate coords, origin at its front-left, y to the port wall) --
    @property
    def plate_origin(self) -> tuple[float, float]:
        """The plate's front-left corner in drawer coords (PLATE_X0, PLATE_Y0)."""
        d = self.drawer
        return d["wall"] + 0.3, d["front_thickness"] + 0.3

    @property
    def plate_size(self) -> tuple[float, float]:
        """PLATE_W × PLATE_D: the drawer's inside, from its front panel up to the port wall."""
        d = self.drawer
        return (self.drawer_w - 2 * d["wall"] - 0.6,
                d["depth"] - d["rear_bay"] - d["wall"] - d["front_thickness"] - 0.6)

    def plate_buttons(self) -> list[tuple[float, float]]:
        """The pin holes over the node's RESET and BOOT, in plate coords (board_plate.scad › plate_body)."""
        px, py = self.plate_origin
        n = self.node
        return [(self.node_x0 + kx - self.drawer_x0 - px, self.node_front_y + n["size"][1] - ky - py)
                for kx, ky in NODE_BUTTONS]

    def plate_keepouts(self) -> list[tuple[str, tuple[float, float, float, float]]]:
        """What a board may not cover, as (name, (x0, y0, x1, y1)) in plate coords: the locating pins, the
        finger slots and the label (board_plate.scad › plate_body).  The RESET/BOOT holes: plate_buttons."""
        w, d = self.plate_size
        return [("locating pin", (10 - 2.1, 10 - 2.1, 10 + 2.1, 10 + 2.1)),
                ("locating pin", (w - 10 - 2.1, d - 10 - 2.1, w - 10 + 2.1, d - 10 + 2.1)),
                ("finger slot", (12 - 7, d / 2 - 4.5, 12 + 7, d / 2 + 4.5)),
                ("finger slot", (w - 12 - 7, d / 2 - 4.5, w - 12 + 7, d / 2 + 4.5)),
                ("label", (w / 2 - 25, 2, w / 2 + 25, 12))]

    @property
    def plate_grid(self) -> dict:
        """config/rack.yaml › plate_grid, with the row pitch."""
        g = dict(self.raw["plate_grid"])
        g["row"] = g["pitch"] * math.sqrt(3) / 2
        return g

    def plate_holes(self) -> list[tuple[int, int, float, float]]:
        """The honeycomb's holes, (row, col, x, y) in plate coords: rows along X from the front (row 1), the
        long rows (odd) one hole longer than the short ones, each row centred; none within `margin` of the
        plate's edge, the locating pins, the finger slots or the RESET/BOOT pin holes (lib/hexgrid.scad
        reads them from generated/config.scad, tools/plate_layout.py from here)."""
        g = self.plate_grid
        w, d = self.plate_size
        p, af, u, m = g["pitch"], g["hole"], g["undercut"], g["margin"]
        half_x = af / 2 + u                      # the undercut hex: flats facing ±X, corners ±Y
        half_y = (af + 2 * u) / math.sqrt(3)
        n_rows = int((d - 2 * (m + half_y)) / g["row"] + 1e-9) + 1
        y0 = (d - (n_rows - 1) * g["row"]) / 2
        n_long = int((w - 2 * (m + half_x)) / p + 1e-9) + 1
        slots = [(x, d / 2) for x in (12.0, w - 12.0)]            # finger slots: 14 × 9 along X (plate_keepouts)
        out = []
        for j in range(n_rows):
            n = n_long if j % 2 else n_long - 1
            y = y0 + j * g["row"]
            for i in range(n):
                x = w / 2 + p * (i - (n - 1) / 2)
                if any(math.hypot(x - px, y - py) < 2.1 + half_y + m for px, py in ((10, 10), (w - 10, d - 10))):
                    continue
                if any(math.hypot(max(abs(x - sx) - 2.5, 0), y - sy) < 4.5 + half_y + m for sx, sy in slots):
                    continue
                if any(math.hypot(x - bx, y - by) < BUTTON_HOLE_R + half_y + m for bx, by in self.plate_buttons()):
                    continue
                out.append((j + 1, i + 1, round(x, 3), round(y, 3)))
        return out

    def bay_layout(self, bay_id: str, boards: dict | None = None) -> list[dict]:
        """A converted bay's boards on its plate, in port order: {slot, board, at: (x, y), o} with o the board
        turned as on the plate (orient_board: w, l, holes, usb_x, usb_side).  Boards without `at` are packed
        left to right, centred, BOARD_GAP apart, their rear edges REAR_GAP_MAX from the port wall."""
        lib = boards if boards is not None else load_boards()
        out = []
        for sl in self.duts(bay_id):
            if sl.board not in lib:
                raise ValueError(f"{sl.id}: no board {sl.board!r} in mechanical/boards/boards.yaml")
            out.append({"slot": sl, "board": sl.board, "at": tuple(sl.at) if sl.at else None,
                        "o": orient_board({**lib[sl.board], "orient": sl.orient or "rear"})})
        loose = [e for e in out if e["at"] is None]
        if loose:
            w, d = self.plate_size
            x = (w - sum(e["o"]["w"] for e in loose) - BOARD_GAP * (len(loose) - 1)) / 2
            for e in loose:
                e["at"] = (round(x, 3), round(d - REAR_GAP_MAX - e["o"]["l"], 3))
                x += e["o"]["w"] + BOARD_GAP
        return out

    def bay_boards(self, bay_id: str, boards: dict | None = None) -> list[tuple[str, tuple[float, float]]]:
        """[(board id, (x, y))]: each board's front-left corner on the bay's plate, in port order, turned USB to
        the port wall unless `orient: side` (bay_layout has the turned outlines)."""
        return [(e["board"], e["at"]) for e in self.bay_layout(bay_id, boards)]

    def check_bay_plate(self, bay_id: str, boards: dict | None = None) -> list[str]:
        """What is wrong with a converted bay's layout: a board off the plate, over another, a pin, a finger slot
        or the label, or within BUTTON_CLEAR of the RESET/BOOT pin holes.  [] when it can be printed."""
        w, d = self.plate_size
        boxes = []
        for e in self.bay_layout(bay_id, boards):
            x, y = e["at"]
            o = e["o"]
            boxes.append((e["slot"].id, (x - BOARD_PAD, y - BOARD_PAD, x + o["w"] + BOARD_PAD, y + o["l"] + BOARD_PAD)))
        problems = []
        for name, (x0, y0, x1, y1) in boxes:
            if x0 < 0 or y0 < 0 or x1 > w or y1 > d:
                problems.append(f"{name}: off the plate ({w:g} × {d:g} mm)")
            for what, (a0, b0, a1, b1) in self.plate_keepouts():
                if x0 < a1 and a0 < x1 and y0 < b1 and b0 < y1:
                    problems.append(f"{name}: over the plate's {what}")
            for bx, by in self.plate_buttons():
                gap = math.hypot(max(x0 - bx, 0, bx - x1), max(y0 - by, 0, by - y1)) - BUTTON_HOLE_R
                if gap < BUTTON_CLEAR:
                    problems.append(f"{name}: {gap:.1f} mm from a RESET/BOOT pin hole (keep {BUTTON_CLEAR:g})")
        for i, (n1, (x0, y0, x1, y1)) in enumerate(boxes):
            for n2, (a0, b0, a1, b1) in boxes[i + 1:]:
                if x0 < a1 and a0 < x1 and y0 < b1 and b0 < y1:
                    problems.append(f"{n1} and {n2} overlap")
        return problems

    def multi_bays(self) -> list[str]:
        """The converted bays, in rack order."""
        return [b.id for b in self.bays() if self.is_multi(b.id)]

    def bay_ids(self):  # (row, index, id) for older callers
        for b in self.bays():
            yield b.row, b.index, b.id

    def unit_x(self, u: int) -> float:
        """X of the left edge of tray (unit) u."""
        return self.inner_x0 + u * self.pitch

    def bay_x(self, j: int) -> float:
        return self.unit_x(j)

    # ---- carrier ------------------------------------------------------------
    @property
    def carrier(self) -> dict:
        return self.raw["bay"]["carrier"]

    @property
    def carrier_w(self) -> float:
        """Tray outer width (X)."""
        return self.raw["bay"]["width"]

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

    # ---- power box (mirrors mechanical/parts/power_box.scad) --------------------
    def power_box(self) -> dict:
        """Frame placement of the power box and of what it holds: origin (front-left-bottom
        outer corner), the hub PCB (pos = its KiCad origin, the rear-left corner, at the PCB
        bottom), the row connector mouths on the left wall, the front LEDs and the USB-C PD input
        in the rear wall."""
        pb = self.raw["power_box"]
        hub = self.raw["pcb"]["power_hub"]
        w, d, _h = pb["size"]
        t = pb["wall"]
        socket = 3.2
        x0 = self.inner_x0 + pb["column"] * self.pitch + pb["x"]
        y0 = self.row_origin_y
        z0 = self.carrier["bottom"] + 4 - socket                          # sockets on the floor plate bosses
        hw, hl = hub["size"]
        front = t + hub["front_gap"]
        top = hub["z"] + hub["thickness"]
        leds = []
        for i, kx in enumerate(hub["front"]["leds"]):
            for k, dx in enumerate((-3.0, 3.0) if i < 4 else (0,)):
                leds.append({"x": x0 + hub["x0"] + kx + dx, "kind": ("on", "fault")[k] if i < 4 else ("pd", "ctl")[i - 4],
                             "row": i if i < 4 else None})
        return {
            "origin": [x0, y0, z0], "size": pb["size"], "wall": t,
            "hub": [x0 + hub["x0"], y0 + front + hl, z0 + hub["z"]],
            "rows": [[x0, y0 + front + hl - ky, z0 + top + 3] for ky in hub["rows"]],
            "leds": [{**l, "pos": [l["x"], y0, z0 + top + 0.8]} for l in leds],
            "pd": [x0 + hub["x0"] + hub["rear"]["pd"], y0 + d, z0 + top + 1.6],
        }

    # ---- drawer / chain -------------------------------------------------------
    @property
    def drawer(self) -> dict:
        return self.raw["drawer"]

    @property
    def chain(self) -> dict:
        return self.raw["chain"]

    @property
    def drawer_w(self) -> float:
        d = self.drawer
        return self.carrier_w - 2 * d["guide_width"] - 2 * d["clearance"]

    @property
    def data_port_x(self) -> list[float]:
        """X of the single DATA board's socket on the drawer's port wall (drawer coords): the DATA ×4's fourth
        port, so one drawer takes either board."""
        x4 = self.raw["pcb"]["data_port_x4"]
        return [x4["x0"] + x4["usb"][-1]]

    @property
    def drawer_x0(self) -> float:
        return (self.carrier_w - self.drawer_w) / 2

    def chain_state(self, open_frac: float) -> dict:
        """Geometry of the drag chain for a drawer pulled out by open_frac (0..1)."""
        c = self.chain
        t = self.drawer["travel"] * open_frac
        m = c["moving_y"] - t
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
    pbox = r["power_box"]
    vals = {
        "FRAME_W": round(rack.width, 3),
        "FRAME_D": round(rack.depth, 3),
        "FRAME_TILT": rack.tilt,
        "FRAME_ROW_Y0": rack.row_origin_y,
        "FRAME_BASE_H": rack.base_height,
        "FRAME_TOP_Z": rack.top_z,
        "FRAME_PANEL_T": rack.panel_t,
        "FRAME_PANEL_CLEAR": rack.panel_clear,
        "ROW_IDS": [row["id"] for row in rack.rows],
        "ROW_HEIGHTS": [row["height"] for row in rack.rows],
        "ROW_LAYOUTS": [rack.layout(i) for i in range(len(rack.rows))],
        "BAY_PITCH": round(rack.pitch, 3),
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
        "CAM_LENS": r["bay"]["camera_lens"],
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
        "PLATE_T": d["plate"],
        "HEX_PITCH": rack.plate_grid["pitch"],
        "HEX_AF": rack.plate_grid["hole"],
        "HEX_U": rack.plate_grid["undercut"],
        "HEX_CLEAR": rack.plate_grid["clear"],
        "HEX_HOLES": [[x, y] for _, _, x, y in rack.plate_holes()],
        "HEX_ROWS": sorted({(r, y) for r, _, _, y in rack.plate_holes()}),
        "PEG_STOP": [rack.plate_grid["stop"][k] for k in ("offset", "angle", "neck", "ledge", "lip")],
        "PEG_CAM": [rack.plate_grid["cam"][k] for k in ("r0", "r1", "arc", "under")],
        "CHAIN_INNER": ch["inner"],
        "CHAIN_OUTER": ch["outer"],
        "CHAIN_R": ch["radius"],
        "CHAIN_PITCH": ch["pitch"],
        "CHAIN_END_HOLES": ch["end_holes"],
        "CHAIN_FIXED": ch["fixed"],
        "CHAIN_MOVING_X": ch["moving_x"],
        "CHAIN_FOOT_Y": ch["foot_y"],
        "CHAIN_MOVING_Y": ch["moving_y"],
        "CHAIN_END_LENGTH": ch["end_length"],
        "CHAIN_BEND_Y": ch["bend_y"],
        "NODE_SIZE": node["size"],
        "NODE_T": node["thickness"],
        "NODE_HOLES": node["holes"],
        "NODE_X0": rack.node_x0,
        "NODE_FRONT_Y": rack.node_front_y,
        "NODE_PCB_TOP": rack.pcb_top,
        "NODE_FRONT": [node["front"]["pc_port"], node["front"]["led"], node["front"]["svc"]],
        "NODE_PWR_Y": node["pwr_y"],
        "NODE_DATA_Y": node["right"]["data"],
        "NODE_AUX": node["aux"],
        "NODE_CAM": node["cam"],
        "DATA_PCB_SIZE": r["pcb"]["data_port"]["size"],
        "DATA_PCB_T": r["pcb"]["data_port"]["thickness"],
        "DATA_PCB_HOLES": r["pcb"]["data_port"]["holes"],
        "DATA_PCB_USB": r["pcb"]["data_port"]["usb"],
        "DATA_PCB_PH": r["pcb"]["data_port"]["ph"],
        "DATA_X4_SIZE": r["pcb"]["data_port_x4"]["size"],
        "DATA_X4_X0": r["pcb"]["data_port_x4"]["x0"],
        "DATA_X4_HOLES": r["pcb"]["data_port_x4"]["holes"],
        "DATA_X4_USB": r["pcb"]["data_port_x4"]["usb"],
        "DATA_X4_LEAD": r["pcb"]["data_port_x4"]["lead"],
        "POD_PCB_SIZE": r["pcb"]["camera_pod"]["size"],
        "POD_PCB_T": r["pcb"]["camera_pod"]["thickness"],
        "POD_PCB_HOLES": r["pcb"]["camera_pod"]["holes"],
        "POD_LEDS": r["pcb"]["camera_pod"]["leds"],
        "POD_LED_Y": r["pcb"]["camera_pod"]["led_y"],
        "POD_LEAD_Y": r["pcb"]["camera_pod"]["lead"],
        "POD_HEADER": r["pcb"]["camera_pod"]["header"],
        "HUB_SIZE": hub["size"],
        "HUB_HOLES": hub["holes"],
        "HUB_T": hub["thickness"],
        "HUB_X0": hub["x0"],
        "HUB_FRONT_GAP": hub["front_gap"],
        "HUB_Z": hub["z"],
        "HUB_ROWS": hub["rows"],
        "HUB_LEDS": hub["front"]["leds"],
        "HUB_USB": hub["front"]["usb"],
        "HUB_PD": hub["rear"]["pd"],
        "HUB_BUTTONS": hub["buttons"],
        "PBOX_COLUMN": pbox["column"],
        "PBOX_SIZE": pbox["size"],
        "PBOX_WALL": pbox["wall"],
        "PBOX_X": pbox["x"],
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
