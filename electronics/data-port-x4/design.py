"""DATA ×4 v1.0 — a converted bay's drawer board: one bay node serves up to four small USB boards.

It replaces the DATA port on the drawer's rear-bay floor (docs/multi-dut-node.md): the same PH 8 lead
from the node's J7 brings 5 V, USB and the node's I²C; four USB-C on the port wall feed sub-slots
A1.1–A1.4 (left to right, seen from the front).

* U1, a USB2514B hub (multi-TT: one transaction translator per port), on its straps: no EEPROM, no
  SMBus, off the I²C bus; every strap pin (CFG_SEL0/1, NON_REM0/1) pulled down by 100k.  Hub port n is
  USB-C n (busid 1-1.n).  24 MHz crystal, hand-routed beside the hub with no via.  The upstream pair
  is the node's ESP32-S3 (full speed) or, in classic mode, the laptop on the node's front port.
* Per port, the power chain +5V → PORTn_5V_SW → PORTn_VBUS: a TPS2553-1 switch (≈ 0.50–0.62 A,
  R_ILIM 47k right beside its ILIM pin; it limits for 7.5 ms, then latches off until EN toggles), a
  100 mΩ shunt read by an
  INA226 (the node's own chip, I²C 0x41/0x43/0x44/0x45), a USB-C source with Rp 56k on each CC
  ("default USB power"), USBLC6 ESD in flow-through with 100 nF on its VBUS pin.  The switch's FAULT
  goes to the expander (the hub's OCS_N stay on their internal pull-ups).  PORTn_5V_SW and PORTn_VBUS
  are 0.4 mm tracks (netclass Port); the INA226 reads VBUS on the shunt's load-side sense pad.
* Two TCA6408A expanders in the rear row, each between the two ports it drives, so that only SDA, SCL
  and INT cross the board: U2 (0x20) ports 1–2, U6 (0x21) ports 3–4; per port EN, FAULT_N, RESET, BOOT.
  Their pins come up as inputs and each EN is pulled down: every port stays off until the firmware
  switches it on within the bay's budget (four ports at 0.50–0.62 A would trip the node's 1.34–1.52 A
  switch; the owner's decision, 2026-10-19).
* RESET and BOOT per port: open drain emulated by the expander (output register 0, the pin switched
  between input and output), through 1k to a 1 × 3 2.54 mm header (GND, RESET_N, BOOT_N) for Dupont
  jumpers to the board's own pins.  The header is not fitted (the user's choice, 2026-10-19: decided
  later); the 1k are.  A 100k pull-up on each line keeps the expander's input high with nothing
  plugged in (the TCA6408A has no pull-ups and no interrupt mask: a floating input would raise INT).
* U3, an AP2112K-3.3 (≈ 50 mV dropout at 0.1 A): the hub, the expanders and the INA226s keep running
  down to ≈ 3.4 V in, so the firmware still sees a sagging bay and can shed a port.  Not a smaller LDO:
  the hub alone draws up to 155 mA at high speed with four ports busy (USB2514B tables 6-4/6-5; 84 mA at
  full speed), ≈ 0.31 W in the regulator from 5.24 V: more than a 200 mA SOT-23 part like the XC6206 is
  rated for, and the AP2112K (600 mA) shuts down on overheating.  Its VIN, EN and GND pins sit on
  top-side islands with their own vias to the planes, to spread that heat.
* The lead's SDA, SCL and INT pass through USBLC6s (the node has no ESD on them; their VBUS pin open),
  then through three 2N7002s, gate on this board's +3V3 (NXP AN10441's shifter, 3.3 V both sides):
  BUS_* on the lead's side (the node's pull-ups), SDA/SCL/INT on the board's (4.7k, 4.7k, 10k here).
  With DUT_5V off the FETs open, so the node's pull-ups cannot feed this board's dead +3V3 through the
  INA226 and TCA6408A clamps, and the node's own INA226 bus stays free.

4 layers, JLC04161H-7628: F.Cu signals and the hand-drawn USB pairs · In1 solid GND · In2 power only
(+5V, a +3V3 area under the hub, the expanders, the ports' rear rows and each INA226) · B.Cu signals
and the downstream pairs' long runs.  100 × 37 mm (config/rack.yaml › pcb.data_port_x4; 100 mm long since
2026-10-20, for JLC's 4-layer offer): the PH 8 (J1, side entry) at the rear end of the right edge, its mouth
out of it, pin 1 at the front; its plug and the wires' turn drop into the drawer's side window beside the
board.  J1's lead ESDs face its pins, the LDO sits in the corner behind it, the upstream pair runs ≈ 15 mm
to the hub, diagonally.  Three holes, on the drawer's bosses where they were (no fourth: the v2's lands outside).  KiCad
coordinates: y = 0 is the REAR edge, y = 28 the FRONT edge (the USB-C mouths); x = 0 is drawer x 15.
The layout below is written on the 24 mm board it was drawn on: DY (13 mm) moves it to the 37 mm one,
the extra depth at the rear (P(), the hand-drawn tracks, the zones); the holes come from rack.yaml as
they are.

Schematic: drawn (frames per block, the power chain and the pairs wired, the rest by label), one sheet
for the lead, hub and expanders, one per port.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
sys.path.insert(0, str(HERE.parents[1] / "tools"))

from catalog import C, R, part  # noqa: E402
from eda import Board  # noqa: E402

import rackcfg  # noqa: E402

RACK = rackcfg.load()
CFG = RACK.raw["pcb"]["data_port_x4"]
W, H = CFG["size"]
DY = H - 24                         # the layout's 24 mm frame → the board: everything 13 mm from the rear edge
PH_EDGE = 4.9                       # JST PH side entry: footprint origin from the board edge
J1_X, J1_Y = CFG["lead"][0], CFG["lead"][1] - DY    # J1 (rot 90, mouth +x) in the layout frame
UP_Y = J1_Y - 2.0                                    # the upstream pair's centre line west of J1's vias (pins 6 / 5)
USB_Y = 24 - 3.4                    # the USB4105s' origin (their signal pads at USB_Y − 3.68)
HX, HY = 79.6, 16.6                 # the hub (QFN-36, its downstream pins down the left side)
ESD_DX, ESD_Y = 8.0, 19.6           # each port's USBLC6, right of its receptacle (rot 0, flow-through)

# INA226 address straps (A1, A0) per port: 0x41, 0x43, 0x44, 0x45 (the node's own INA226 is 0x40)
INA_ADDR = [("GND", "+3V3"), ("GND", "SCL"), ("+3V3", "GND"), ("+3V3", "+3V3")]
# the rear row: per pair of ports the left port's header, its expander, the right port's header (mirrored,
# so that each header's BOOT pin is the one nearest the expander); pin 1 (GND) x per port
HDR_X = [8.5, 30.0, 44.5, 66.0]
HDR_Y, RES_Y = 2.9, 5.9             # the headers' pins; the 1k series resistors, in front of them
EXP = [(18.3, "GND"), (54.3, "+3V3")]   # U2 (0x20, ports 1–2) and U6 (0x21, ports 3–4): x, ADDR strap
EXP_Y = 3.2
# each port's four lines on its expander: the left port of a pair on P0–P3, the right one on P4–P7, in the
# order their pins face their targets
EXP_LINES = {"a": {"P0": "RST_IO", "P1": "BOOT_IO", "P2": "EN", "P3": "FLT_N"},
             "b": {"P4": "EN", "P5": "FLT_N", "P6": "BOOT_IO", "P7": "RST_IO"}}


def P(x, y, rot=0, side="top"):
    """A placement in the layout frame (y + DY on the board)."""
    return {"x": x, "y": round(y + DY, 4), "rot": rot, "side": side}


def sh(poly):
    """A polygon from the layout frame to the board."""
    return [(x, round(y + DY, 4)) for x, y in poly]


def at(x, y, rot=0, mirror="", fields=None):
    """Schematic position in 0.1" grid units."""
    d = {"x": x, "y": y, "rot": rot}
    if mirror:
        d["mirror"] = mirror
    if fields is not None:
        d["fields"] = fields
    return d


def port(b: Board, n: int):
    cx = CFG["usb"][n - 1]
    hx = HDR_X[n - 1]
    left = n % 2 == 1                   # the left port of its pair: the expander on its right
    k = 100 * n
    p = f"PORT{n}_"
    s = b.sheet(f"Port {n}", f"port{n}.kicad_sch", f"USB-C {n}: switch, current sense, ESD, RESET/BOOT")
    sw, sh, ina, usb, esd = f"U{k + 1}", f"R{k + 6}", f"U{k + 2}", f"J{k + 1}", f"U{k + 3}"
    s.frame(f"Port {n} power: +5V → TPS2553-1 → {p}5V_SW → 100 mΩ shunt → {p}VBUS, the INA226 across the shunt",
            6, 10, 108, 44)
    s.tag("+5V", (20, 18), "up")
    s.wire((20, 18), (20, 21), f"{sw}.IN")
    part(s, sw, "vbus_sw_latch", {"IN": "+5V", "GND": "GND", "EN": p + "EN", "~{FAULT}": p + "FLT_N",
                                  "ILIM": p + "ILIM", "OUT": p + "5V_SW"}, pcb=P(cx - 6.2, 10.45, 0),
         sch=at(30, 22, fields=(-4, -4)))
    C(s, f"C{k + 1}", "1u", "+5V", "GND", pcb=P(cx - 7.5, 7.85, 0), sch=at(15, 24))
    s.wire(f"C{k + 1}.1", (15, 21), (20, 21))
    # R_ILIM (0402) standing between the switch and the shunt, its pad 1 level with ILIM (TI: as close to
    # the pin as possible), its GND pad on a via of its own (local_routes)
    R(s, f"R{k + 1}", "47k", p + "ILIM", "GND", size="0402", pcb=P(cx - 3.66, 10.96, 270), sch=at(22, 28))
    s.wire(f"{sw}.ILIM", (22, 24), f"R{k + 1}.1")
    R(s, f"R{k + 2}", "10k", p + "EN", "GND", pcb=P(cx - 4.5, 7.85, 0), sch=at(14, 36))
    R(s, f"R{k + 3}", "10k", "+3V3", p + "FLT_N", pcb=P(cx - 1.5, 7.85, 0), sch=at(40, 36))
    # Kelvin shunt: pins 1/4 carry the port's current, 2/3 are sense pads at the resistor's own ends
    part(s, sh, "shunt100m", {"1": p + "5V_SW", "4": p + "VBUS", "2": p + "SNS_P", "3": p + "SNS_N"},
         "100m", pcb=P(cx - 0.85, 10.45, 0), sch=at(46, 23))
    s.wire(f"{sw}.OUT", f"{sh}.1")
    a1, a0 = INA_ADDR[n - 1]
    # VBUS read on the load-side sense pad (the same node as PORTn_VBUS): the 0.4 mm Port tracks stay off
    # the INA226's 0.5 mm pitch, its Vbus pin joins Vin− next to it
    part(s, ina, "ina226", {"VS": "+3V3", "GND": "GND", "A1": a1, "A0": a0, "SDA": "SDA", "SCL": "SCL",
                            "~{Alert}": "INT", "Vin+": p + "SNS_P", "Vin-": p + "SNS_N", "Vbus": p + "SNS_N"},
         pcb=P(cx + 4.9, 10.45, 180), sch=at(66, 24, fields=(-9, -7)))
    s.wire(f"{sh}.2", (52, 22), (52, 25), f"{ina}.Vin+")
    s.wire(f"{sh}.3", (50, 24), (50, 26), f"{ina}.Vin-")
    s.wire(f"{sh}.4", (46, 33), (60, 33))
    s.tag(p + "VBUS", (60, 33), "right")
    C(s, f"C{k + 2}", "22u", p + "VBUS", "GND", size="0805", pcb=P(cx - 3.4, 13.9, 0), sch=at(55, 35.5))
    s.wire(f"C{k + 2}.1", (55, 33))
    C(s, f"C{k + 3}", "100n", "+3V3", "GND", pcb=P(cx + 4.5, 7.85, 0), sch=at(80, 18))

    s.frame(f"USB-C {n} (source): Rp 56k on each CC; USBLC6 in flow-through (connector side | hub side)",
            6, 50, 108, 100)
    part(s, usb, "usbc5a", {"VBUS": p + "VBUS", "GND": "GND", "CC1": p + "CC1", "CC2": p + "CC2",
                            "D+": p + "CONN_DP", "D-": p + "CONN_DN", "SBU1": None, "SBU2": None,
                            "SHIELD": "GND"}, f"PORT{n}", pcb=P(cx, USB_Y, 0), sch=at(50, 76, fields=(-8, -11)))
    s.wire(f"{usb}.A7", f"{usb}.B7")
    s.wire(f"{usb}.A6", f"{usb}.B6")
    # VBUS pads towards the 0.4 mm feed, CC pads towards their own pins (local_routes draws both)
    R(s, f"R{k + 4}", "56k", p + "VBUS", p + "CC1", pcb=P(cx - 6.6, ESD_Y, 270), sch=at(62, 64.5))
    R(s, f"R{k + 5}", "56k", p + "VBUS", p + "CC2", pcb=P(cx + 3.4, 13.9, 180), sch=at(66, 64.5))
    s.wire(f"{usb}.CC1", (62, 72), f"R{k + 4}.2")
    s.wire(f"{usb}.CC2", (66, 73), f"R{k + 5}.2")
    # pins 1/3 face the receptacle, 6/4 the hub: each line enters one pin and leaves by the other
    part(s, esd, "esd", {"1": p + "CONN_DN", "6": p + "DN", "3": p + "CONN_DP", "4": p + "DP", "5": "+5V",
                         "2": "GND"}, pcb=P(cx + ESD_DX, ESD_Y, 0), sch=at(84, 76))
    s.wire(f"{usb}.B7", f"{esd}.1")
    s.wire(f"{usb}.A6", f"{esd}.3")
    C(s, f"C{k + 4}", "100n", "+5V", "GND", pcb=P(cx + ESD_DX + 1.6, 22.6, 0), sch=at(98, 62))

    s.frame(f"RESET / BOOT {n}: through 1k to a 1 × 3 2.54 mm header (not fitted)", 112, 10, 162, 56)
    # header pins left to right: GND, RESET_N, BOOT_N (mirrored on the right port of a pair); each 1k
    # in front of its pin, its expander end turned away from the other resistor
    d = 1 if left else -1
    for r, sig, pin, y in ((f"R{k + 7}", "RST", 2.54, 30), (f"R{k + 8}", "BOOT", 5.08, 38)):
        west = (sig == "RST") == left           # pad 1 (the expander's end) on the resistor's west side
        R(s, r, "1k", p + sig + "_IO", p + sig + "_N",
          pcb=P(hx + d * pin + (-0.825 if west else 0.825), RES_Y, 0 if west else 180), sch=at(132, y, rot=90))
        s.wire((124, y), f"{r}.1", net=p + sig + "_IO")
        s.tag(p + sig + "_IO", (124, y), "left")
    part(s, f"J{k + 2}", "hdr3", {"1": "GND", "2": p + "RST_N", "3": p + "BOOT_N"}, f"AUX{n}",
         pcb=P(hx, HDR_Y, 90 if left else 270), dnp=True, sch=at(152, 31, fields=(-1, -4)))
    s.wire(f"R{k + 7}.2", (146, 30), (146, 31), f"J{k + 2}.2")
    s.wire(f"R{k + 8}.2", (148, 38), (148, 32), f"J{k + 2}.3")
    # 100k pull-ups (0402, the only size that fits): RESET's on the expander side, outside its 1k; BOOT's on
    # the header side, standing in the gap between the two 1k (local_routes links both)
    R(s, f"R{k + 9}", "100k", "+3V3", p + "RST_IO", size="0402",
      pcb=P(hx - d * 0.72, RES_Y, 0 if left else 180), sch=at(124, 44, rot=90))
    R(s, f"R{k + 10}", "100k", "+3V3", p + "BOOT_N", size="0402", pcb=P(hx + d * 3.81, RES_Y, 90),
      sch=at(140, 48))
    s.notes_at = (112, 62, 50)
    s.note(f"Port {n} = sub-slot A1.{n} (the bay's position,")
    s.note(f"  then the port), hub port {n}, busid 1-1.{n}.")
    lines = EXP_LINES["a" if left else "b"]
    s.note(f"INA226 at 0x{0x40 + [1, 3, 4, 5][n - 1]:02x}; expander {['U2', 'U6'][(n - 1) // 2]} "
           f"(0x{0x20 + (n - 1) // 2:02x}):")
    s.note("  " + ", ".join(f"{pin} {sig.replace('_IO', '')}" for pin, sig in lines.items()) + ".")
    s.note("ILIM 47k: 0.50–0.62 A (TI's IOS equations).")
    s.note("  The -1 limits for 7.5 ms, then latches off")
    s.note("  until EN toggles; FAULT_N flags it.")
    s.note("EN pulled down: the port is off until the")
    s.note("  firmware enables it within the bay's budget.")
    s.note("RESET/BOOT: output register 0; the pin as an")
    s.note("  output pulls low, as an input the 100k holds it high.")
    s.note("Pigtail: 1 GND, 2 RESET_N, 3 BOOT_N (Dupont")
    s.note("  female jumpers to the board's own pins).")


# ----------------------------------------------------------------------------------------- USB pairs
# Coupled pairs, 0.25 mm tracks with a 0.15 mm gap (≈ 90 Ω differential on JLC04161H-7628, as the bay
# node's), drawn here instead of by Freerouting.  Downstream ports 1–3: hub pins → vias left of the hub
# → B.Cu (over the In2 +5V plane) west along the band behind the receptacles → down beside each port's
# ESD → vias → the ESD's hub-side pins; port 4 sits next to the hub and stays on F.Cu.  Each ESD passes
# both lines through (pins 6 → 1, 4 → 3); its connector side runs under the receptacle into A7 (D−)
# and A6 (D+) from the front; B6 joins A6 by a loop behind the pad row, B7 joins the D− line through
# B.Cu.  The upstream pair goes J1 → B.Cu round the hub's east side → its top pins without a crossover.
# Near the pins the tracks neck down to 0.2 mm.
PAIR_W, PAIR_S = 0.25, 0.2          # track width, half the centre spacing (0.4 mm: 0.15 mm gap)
NECK = 0.2
SMALL = (0.5, 0.3)


def offset_path(pts, s, k=0.6):
    """A track parallel to the axis-aligned centre path `pts`, s mm to its left (screen coordinates,
    y down), with 45° chamfers: the centre line's chamfer is k mm each side of a corner."""
    t = math.tan(math.pi / 8)

    def unit(a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        d = math.hypot(dx, dy)
        return dx / d, dy / d

    def left(u):
        return u[1], -u[0]

    u = unit(pts[0], pts[1])
    out = [(pts[0][0] + s * left(u)[0], pts[0][1] + s * left(u)[1])]
    for i in range(1, len(pts) - 1):
        u1, u2 = unit(pts[i - 1], pts[i]), unit(pts[i], pts[i + 1])
        l1, l2 = left(u1), left(u2)
        sigma = 1 if abs(u2[0] - l1[0]) < 1e-9 and abs(u2[1] - l1[1]) < 1e-9 else -1
        m = (pts[i][0] + s * (l1[0] + l2[0]), pts[i][1] + s * (l1[1] + l2[1]))
        ko = k - sigma * s * (1 - t)
        out += [(m[0] - ko * u1[0], m[1] - ko * u1[1]), (m[0] + ko * u2[0], m[1] + ko * u2[1])]
    u = unit(pts[-2], pts[-1])
    out.append((pts[-1][0] + s * left(u)[0], pts[-1][1] + s * left(u)[1]))
    return [(round(x, 4), round(y, 4)) for x, y in out]


def usb_routes():
    tracks, vias = [], []

    def t(net, *pts, layer="F.Cu", w=PAIR_W):
        tracks.append((net, layer, w, [(round(x, 4), round(y + DY, 4)) for x, y in pts]))

    def via(net, x, y):
        vias.append((net, round(x, 4), round(y + DY, 4), *SMALL))

    def pair(left_net, right_net, centre, layer, head=None, tail=None, k=0.6):
        """head/tail: {net: [points]} prepended / appended to that net's line."""
        for net, s in ((left_net, PAIR_S), (right_net, -PAIR_S)):
            pts = offset_path(centre, s, k)
            pts = (head or {}).get(net, []) + pts + (tail or {}).get(net, [])
            t(net, *pts, layer=layer)

    hub_pin = lambda pin: (HX - 2.9375, HY - 2.0 + 0.5 * (pin - 1))       # left side, pins 1–9

    for n in range(1, 5):
        cx = CFG["usb"][n - 1]
        ex = cx + ESD_DX
        p = f"PORT{n}_"
        # connector side: ESD pins 1 (D−) / 3 (D+) → between the receptacle's shell tabs → A7 / A6
        t(p + "CONN_DN", (ex - 1.1375, ESD_Y - 0.95), (ex - 1.8, ESD_Y - 0.95), (ex - 2.55, ESD_Y - 0.2),
          (cx + 0.65, ESD_Y - 0.2), (cx + 0.25, ESD_Y - 0.6), (cx + 0.25, USB_Y - 3.68))
        t(p + "CONN_DP", (ex - 1.1375, ESD_Y + 0.95), (ex - 1.8, ESD_Y + 0.95), (ex - 2.55, ESD_Y + 0.2),
          (cx + 0.25, ESD_Y + 0.2), (cx - 0.25, ESD_Y - 0.3), (cx - 0.25, USB_Y - 3.68))
        # B6 → A6: a loop behind the pad row; B7 → a via, B.Cu under the receptacle, a via on the D− line
        pr = USB_Y - 3.68
        t(p + "CONN_DP", (cx + 0.75, pr), (cx + 0.75, 15.3), (cx - 0.25, 15.3), (cx - 0.25, pr), w=NECK)
        t(p + "CONN_DN", (cx - 0.75, pr), (cx - 0.75, 16.0), (cx - 1.0, 15.75), w=NECK)
        via(p + "CONN_DN", cx - 1.0, 15.75)
        t(p + "CONN_DN", (cx - 1.0, 15.75), (cx - 1.0, 17.0), (cx + 0.95, 18.95), (cx + 3.3, 18.95), layer="B.Cu",
          w=NECK)
        via(p + "CONN_DN", cx + 3.3, 18.95)                     # clear of the receptacle's peg keep-out
        t(p + "CONN_DN", (cx + 3.3, 18.95), (cx + 3.3, ESD_Y - 0.2), w=NECK)
        if n == 4:
            # port 4: hub pins 8 (D−) / 9 (D+) straight to the ESD's hub-side pins 6 / 4, on F.Cu
            (hx8, hy8), (_, hy9) = hub_pin(8), hub_pin(9)
            t(p + "DN", (hx8, hy8), (75.3, hy8), (74.8, ESD_Y - 0.95), (ex + 1.1375, ESD_Y - 0.95))
            t(p + "DP", (hx8, hy9), (75.8, hy9), (75.8, ESD_Y + 0.55), (75.4, ESD_Y + 0.95),
              (ex + 1.1375, ESD_Y + 0.95))
            t("+5V", (ex + 1.1375, ESD_Y), (75.0, ESD_Y), w=0.3)
            via("+5V", 75.0, ESD_Y)
            continue
        # hub side of the ESD: pins 6 / 4 / 5 out to vias in a column right of the part
        vx = ex + 2.25
        t(p + "DN", (ex + 1.1375, ESD_Y - 0.95), (vx, ESD_Y - 0.95))
        t(p + "DP", (ex + 1.1375, ESD_Y + 0.95), (vx, ESD_Y + 0.95))
        t("+5V", (ex + 1.1375, ESD_Y), (vx, ESD_Y), w=0.3)
        for net, dy in ((p + "DN", -0.95), (p + "DP", 0.95), ("+5V", 0.0)):
            via(net, vx, ESD_Y + dy)

    # ports 1–3: hub pins → F.Cu stubs (0.2 mm) → vias → B.Cu pairs: north, west along their lane, south
    # beside their ESD.  Going north the D+ line is on the left (west); west, D− is on the north; south, D−
    # is on the west — the order the ESD's via column wants.
    lanes = {   # port: (D− via, D+ via, F.Cu stubs D−, D+, B.Cu start (centre), lane y)
        1: ((75.9, 13.95), (75.0, 13.95), [(76.2, 14.6), (75.9, 14.3)], [(75.6, 15.1), (75.0, 14.5)],
            (75.45, 13.45), 12.6),
        2: ((74.55, 15.45), (73.65, 16.1), [(74.7, 15.6)], [], (74.1, 14.95), 13.6),
        3: ((73.6, 17.1), (72.7, 17.6), [], [], (72.85, 16.55), 14.6),
    }
    for n, (vm, vp, stub_m, stub_p, (sx, sy), ly) in lanes.items():
        p = f"PORT{n}_"
        pm, pp = hub_pin({1: 1, 2: 3, 3: 6}[n]), hub_pin({1: 2, 2: 4, 3: 7}[n])
        t(p + "DN", pm, *stub_m, vm, w=NECK)
        t(p + "DP", pp, *stub_p, vp, w=NECK)
        via(p + "DN", *vm)
        via(p + "DP", *vp)
        cx = CFG["usb"][n - 1]
        xt = cx + ESD_DX + 3.05                       # the descent's centre line
        vx = cx + ESD_DX + 2.25                       # the ESD's via column
        centre = [(sx, sy), (sx, ly), (xt, ly), (xt, ESD_Y - 1.2)]
        pair(p + "DP", p + "DN", centre, "B.Cu",
             head={p + "DN": [vm], p + "DP": [vp]},
             tail={p + "DN": [(xt - PAIR_S, ESD_Y - 1.15), (xt - PAIR_S - 0.2, ESD_Y - 0.95), (vx, ESD_Y - 0.95)],
                   p + "DP": [(xt + PAIR_S, ESD_Y + 0.75), (xt + PAIR_S - 0.2, ESD_Y + 0.95), (vx, ESD_Y + 0.95)]})
    # VDDA33 (pin 5) between ports 2 and 3's stubs: its own via to the +3V3 area of In2
    t("+3V3", hub_pin(5), (75.6, HY), w=NECK)
    via("+3V3", 75.6, HY)

    # upstream: J1 (right edge, pins along y) pins 6 (D+) / 5 (D−), the node's J7 pins 3 / 4 mirrored →
    # two vias just inside its pads, D+ north of D− → B.Cu west, then 45° south-west past the lead's ESDs
    # (over In2's +5V, the +3V3 area's edge following it) into the area's notch, west and down → vias → the
    # hub's top pins 31 (D+) / 30 (D−).  Every turn keeps D+ on the pair's right, west of D− going south, as
    # the hub wants, with no crossover: ≈ 15 mm in all.
    pad = lambda pin: (J1_X - 2.85, J1_Y + 9 - 2 * pin)                   # J1's pad centres (rot 90)
    jp, jm = pad(6), pad(5)
    vp, vm = (89.5, UP_Y - 0.35), (89.5, UP_Y + 0.35)
    t("UP_DP", (jp[0] - 1.65, jp[1]), (89.8, jp[1]), vp)
    t("UP_DN", (jm[0] - 1.65, jm[1]), (89.9, jm[1]), (89.5, jm[1] - 0.4), vm)
    via("UP_DP", *vp)
    via("UP_DN", *vm)
    um, up = (HX + 1.0, HY - 2.9375), (HX + 0.5, HY - 2.9375)              # hub pins 30 / 31
    hm, hp = (81.2, 12.35), (80.3, 12.35)
    t("UP_DN", um, (um[0], 12.95), hm, w=NECK)
    t("UP_DP", up, (up[0], 12.55), hp, w=NECK)
    via("UP_DN", *hm)
    via("UP_DP", *hp)
    centre = [(89.0, UP_Y), (88.0, UP_Y), (88.0 - (11.0 - UP_Y), 11.0), (80.75, 11.0), (80.75, 11.9)]
    pair("UP_DN", "UP_DP", centre, "B.Cu", k=0.5,
         head={"UP_DN": [vm], "UP_DP": [vp]},
         tail={"UP_DN": [(81.2, 12.15), hm], "UP_DP": [(80.3, 12.15), hp]})
    return tracks, vias


def local_routes():
    """The few short links Freerouting tangles: per left port of a pair, its header pins to their 1k and
    the expander's RESET (under the header, through B.Cu) and BOOT lines (EN and FAULT are routed), and
    per port the RESET/BOOT pull-ups; round the hub, its right-side straps, VDDA33 pin 29 (boxed in by the
    upstream pair's vias) to its decoupling cap and a via of its own, the crystal with PLLFILT and RBIAS,
    and its bottom row's +3V3 and GND."""
    tracks, vias = [], []

    def t(net, *pts, layer="F.Cu", w=0.25):
        tracks.append((net, layer, w, [(round(x, 4), round(y + DY, 4)) for x, y in pts]))

    def via(net, x, y):
        vias.append((net, round(x, 4), round(y + DY, 4), *SMALL))

    for i, (xe, _) in enumerate(EXP):
        n = 2 * i + 1
        p, hx = f"PORT{n}_", HDR_X[n - 1]
        pin = lambda k: (xe - 1.456, EXP_Y - 0.75 + 0.5 * (k - 1))         # left side, pins 1–4
        t(p + "RST_N", (hx + 2.54, HDR_Y), (hx + 2.54, RES_Y))
        t(p + "BOOT_N", (hx + 5.08, HDR_Y), (hx + 5.08, RES_Y))
        # BOOT (P1, pin 3) left and down into its 1k's pad 1, clear of EN's way down beside the part
        t(p + "BOOT_IO", pin(3), (xe - 2.7, pin(3)[1]), (hx + 6.73, pin(3)[1] + 0.37), (hx + 6.73, RES_Y))
        # RESET (P0, pin 2): a via left of the part, B.Cu under the header pins, a via above its 1k
        xv = xe - 3.3
        t(p + "RST_IO", pin(2), (xv, pin(2)[1]))
        via(p + "RST_IO", xv, pin(2)[1])
        t(p + "RST_IO", (xv, pin(2)[1]), (xv, 4.3), (xv - 0.4, 4.7), (hx + 0.89, 4.7), layer="B.Cu")
        via(p + "RST_IO", hx + 0.89, 4.7)
        t(p + "RST_IO", (hx + 0.89, 4.7), (hx + 0.89, RES_Y))
    # the hub's right side: RESET_N up to C13 and R2 north of R5 (clear of the lead's ESDs), the CFG straps
    # down the side to R3 / R4 under the corner, VDD33 (pin 23) to a via between them
    rp = lambda pin: (HX + 2.9375, HY + 2.0 - 0.5 * (pin - 19))       # right side, pins 19–27
    t("HUB_RST_N", rp(26), (85.05, rp(26)[1]), (85.55, 14.6), (85.55, 9.6), (85.18, 9.225), (83.4, 9.225),
      w=0.2)
    t("CFG_SEL1", rp(25), (84.3, rp(25)[1]), (84.3, 20.4), (85.0, 21.1), w=0.2)
    t("CFG_SEL0", rp(24), (83.85, rp(24)[1]), (83.85, 20.4), (83.4, 20.85), w=0.2)
    t("+3V3", rp(23), (83.15, rp(23)[1]), (83.3, 16.75))
    via("+3V3", 83.3, 16.75)
    # NON_REM1 (pin 22) shares CFG_SEL0's 100k (R3): 0.15 mm inside the pin row, between the pins' inner
    # ends and the exposed pad, out by the corner between pins 19 and 18, into R3's pad beside CFG_SEL0
    t("CFG_SEL0", rp(22), (81.7875, rp(22)[1]), (81.7875, 18.7875), (83.4, 20.4), (83.4, 20.9), w=0.15)
    # hub pin 29 (VDDA33, top side) → over pin 28 → a via → C9's pad 1
    t("+3V3", (HX + 1.5, HY - 2.9375), (HX + 1.5, 13.15), (HX + 1.75, 12.9), (82.45, 12.9), (82.6, 13.05))
    via("+3V3", 82.6, 13.05)
    t("+3V3", (82.6, 13.05), (82.6, 12.275))
    # NON_REM0 (pin 28) east under that link into its 100k (R5); pin 27 (VBUS_DET, +3V3) to a via below it
    t("NON_REM0", (HX + 2.0, HY - 2.9375), (HX + 2.0, 13.9), (83.7, 13.9), (84.1, 13.5), (84.1, 12.9), w=0.15)
    t("+3V3", rp(27), (83.2, rp(27)[1]), (83.3, 14.5))
    via("+3V3", 83.3, 14.5)
    # the crystal: XI (pin 33) and XO (pin 32) north side by side, no via; XI west between R1's GND pad and
    # Y1's GND pad 2 into Y1.1, then on to C4; XO east round pad 2 into Y1.3, a stub to C5.  PLLFILT (pin
    # 34) down beside XI and between R1's pads to C6, RBIAS (pin 35) straight into R1.
    t("XI", (HX - 0.5, HY - 2.9375), (79.1, 10.3), (78.6, 9.8), (77.35, 9.8), (76.9, 9.35), w=0.15)
    t("XI", (76.9, 8.85), (75.12, 8.85), (74.9, 9.07))
    t("XO", (HX, HY - 2.9375), (79.6, 10.5), (80.25, 9.85), (80.25, 9.225), (80.25, 7.6), (79.8, 7.15),
      (79.1, 7.15), w=0.2)
    t("XO", (80.25, 9.225), (81.4, 9.225), w=0.2)
    t("PLLFILT", (HX - 1.0, HY - 2.9375), (78.6, 13.0), (78.75, 12.85), (78.75, 11.6), (78.6, 11.45),
      (77.0, 11.45), (76.5, 11.95), w=0.2)
    t("RBIAS", (HX - 1.5, HY - 2.9375), (78.1, 12.6), w=0.2)
    # GND: R1, C6 and C8's rear pads along one track to a via; Y1's pads 2 and 4 under its body to another
    t("GND", (78.0, 10.65), (76.5, 10.65), (75.71, 10.65), (75.0, 10.65))
    t("GND", (75.71, 10.65), (75.71, 9.97))
    via("GND", 75.71, 9.97)
    t("GND", (79.1, 8.85), (76.9, 7.15), (75.77, 6.68))
    via("GND", 75.77, 6.68)
    # the bottom row: pin 15 (VDD33) and C12 on one via inside the (shallow) +3V3 tab; the GND pads of C11,
    # C7, C12 and C10 on a bus along the front edge to a via at each end: no via in the +5V neck below the tab
    t("+3V3", (HX + 0.5, HY + 2.9375), (80.1, 20.3), (80.2, 20.43), w=0.3)
    for x in (77.0, 80.2, 81.8):                                    # C11, C12, C10
        t("+3V3", (x, 21.225), (x, 20.43), w=0.3)
        via("+3V3", x, 20.43)
    row = [77.0, 78.6, 80.2, 81.8]
    t("GND", (75.9, 23.35), *[(x, 23.35) for x in row], (82.95, 23.35), w=0.3)
    for x in row:
        t("GND", (x, 22.775), (x, 23.35), w=0.3)
    via("GND", 75.9, 23.35)
    via("GND", 82.95, 23.35)
    # per port: the RESET pull-up onto its 1k's expander end, the BOOT pull-up's rear pad onto its 1k's
    # header end
    for n in range(1, 5):
        p, hx, d = f"PORT{n}_", HDR_X[n - 1], 1 if n % 2 else -1
        if n % 2 == 0:                  # the right port's header pins straight down to their 1k too
            t(p + "RST_N", (hx - 2.54, HDR_Y), (hx - 2.54, RES_Y))
            t(p + "BOOT_N", (hx - 5.08, HDR_Y), (hx - 5.08, RES_Y))
        t(p + "RST_IO", (hx - d * 0.21, RES_Y), (hx + d * 0.89, RES_Y), w=0.2)
        t(p + "BOOT_N", (hx + d * 3.81, RES_Y - 0.51), (hx + d * 5.08, RES_Y - 0.51), (hx + d * 5.08, RES_Y),
          w=0.2)
    # per port, VBUS at 0.4 mm from the shunt's load end (pin 4): east under the INA226 to the CC2 Rp's
    # VBUS pad and down into A9/B4 from the east, west under the shunt to the 22 µF and down into A4/B9;
    # a thin branch to the CC1 Rp.  CC2 drops straight into B5 inside the VBUS run, CC1 leaves A5 south
    # under the receptacle (between its pegs and shell tabs) to its Rp: no via on either CC line.
    pr = USB_Y - 3.68                                                # the receptacles' pad row
    for n in range(1, 5):
        p, cx = f"PORT{n}_", CFG["usb"][n - 1]
        sh = (cx + 0.61, 10.45)                                      # shunt pin 4
        # the switch's OUT (pin 6) east over R_ILIM into the shunt's pin 1; ILIM (pin 5) straight into
        # R_ILIM, its GND end down to a via
        t(p + "5V_SW", (cx - 5.0625, 9.5), (cx - 2.55, 9.5), (cx - 2.31, 9.74), w=0.4)
        t(p + "ILIM", (cx - 5.0625, 10.45), (cx - 3.66, 10.45))
        t("GND", (cx - 3.66, 11.47), (cx - 3.38, 11.75), (cx - 3.0, 11.75))     # above the B.Cu lanes
        via("GND", cx - 3.0, 11.75)
        t(p + "VBUS", sh, (cx + 0.61, 11.82), (cx + 1.39, 12.6), (cx + 4.225, 12.6), (cx + 4.225, 14.6),
          (cx + 2.4, 16.425), (cx + 2.4, pr), w=0.4)
        t(p + "VBUS", (cx + 0.61, 11.82), (cx - 2.16, 11.82), (cx - 4.24, 13.9), (cx - 4.35, 13.9),
          (cx - 4.35, 14.97), (cx - 3.68, 14.97), (cx - 2.4, 16.25), (cx - 2.4, pr), w=0.4)
        t(p + "VBUS", (cx - 4.35, 14.97), (cx - 5.17, 14.97), (cx - 5.17, 17.2), (cx - 6.6, 18.63), w=0.3)
        t(p + "CC2", (cx + 2.575, 13.9), (cx + 2.575, 14.4), (cx + 1.75, 15.225), (cx + 1.75, pr))
        t(p + "CC1", (cx - 1.25, pr), (cx - 1.25, 19.6), (cx - 5.9, 19.6), (cx - 6.6, 20.3))
    # port 3's INA226 A1 strap (pin 1, +3V3) sits at the bottom of its +3V3 tab, too close to its edge for a
    # fan-out via: its own via just inside the tab, east of the part
    a1 = (CFG["usb"][2] + 4.9 + 2.15, 11.45)
    t("+3V3", a1, (a1[0] + 0.9, 11.45), (a1[0] + 1.3, 11.05))
    via("+3V3", a1[0] + 1.3, 11.05)
    # the lead's SDA, SCL and INT from J1's pads straight into their USBLC6s' lead-side pins (U4 level with
    # pins 3 and 2, U5 with pin 1): flow-through, no crossing
    jx = J1_X - 2.85 - 1.65                                         # just inside J1's pads, at their west end
    t("LEAD_SDA", (jx, J1_Y + 3), (89.04, J1_Y + 3.05), w=0.2)
    t("LEAD_SCL", (jx, J1_Y + 5), (89.04, J1_Y + 4.95), w=0.2)
    t("LEAD_INT", (jx, J1_Y + 7), (89.04, J1_Y + 7), w=0.2)
    return tracks, vias


# U3 (AP2112K) in the corner behind J1, turned 180° so that VIN, EN and GND face the +5V side and VOUT the
# +3V3 area: its top-side islands (b.pcb["zones"] "ldo-*") and their vias, +5V to In2 (VIN, then EN and C2),
# GND to In1, laid out as before the turn (the same shapes, rotated)
LDO = (89.2, J1_Y - 12.4)                                           # U3, layout frame
ldo = lambda ox, oy: (round(LDO[0] - ox, 4), round(LDO[1] - oy, 4))  # an offset of the unturned layout
LDO_VIAS = [(net, *ldo(ox, oy), *SMALL) for net, ox, oy in (("+5V", -2.45, -1.1), ("GND", -2.45, 0.0),
                                                            ("+5V", -2.45, 1.1), ("+5V", -2.45, 2.3))]


def board() -> Board:
    b = Board("data-port-x4", "DATA ×4", "1.0",
              comments=["A converted bay's drawer board: four USB-C behind a hub, switched and measured per port "
                        "(hw-testing-rack)",
                        "Generated from electronics/data-port-x4/design.py — edit the Python, then regenerate"])
    b.root_notes = [
        "DATA ×4 v1.0 — USB2514B hub, four USB-C (sub-slots A1.1–A1.4) each with a TPS2553-1 switch, an INA226",
        "  and ESD, two TCA6408A for EN/FAULT/RESET/BOOT, an AP2112K 3.3 V; the PH 8 lead from the bay node's J7",
        "  into J1 at the rear end of the right edge.  100 × 37 mm.",
        "Lead pinout here: 1 INT · 2 SCL · 3 SDA · 4 GND · 5 D− · 6 D+ · 7 GND · 8 +5V",
        "  (the node's J7 mirrored: one 'Same direction' PH 8 cable).",
        "I²C: TCA6408A 0x20 (ports 1–2) / 0x21 (ports 3–4), INA226 0x41 / 0x43 / 0x44 / 0x45 (A1.1–A1.4); the",
        "  node's INA226 stays alone at 0x40.",
    ]
    s = b.sheet("Hub", "hub.kicad_sch", "Lead, hub, expanders, 3.3 V")
    s.paper = "A2"
    s.frame("Lead from the bay node's J7 (JST PH 8, side entry): SDA, SCL and INT through USBLC6s", 6, 10, 70, 56)
    # side entry at the rear end of the right edge, its mouth out of it (rot 90): pin 1 at the front, pin 8 at
    # the rear
    part(s, "J1", "ph8", {"1": "LEAD_INT", "2": "LEAD_SCL", "3": "LEAD_SDA", "4": "GND", "5": "UP_DN", "6": "UP_DP",
                          "7": "GND", "8": "+5V"}, "LEAD", pcb=P(J1_X, J1_Y, 90),
         sch=at(14, 30, mirror="y", fields=(-2, -6)))
    s.part("#FLG01", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "+5V"}, in_bom=False, on_board=False, sch=at(24, 14))
    s.part("#FLG02", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "GND"}, in_bom=False, on_board=False, sch=at(30, 14))
    # pins 6/4 face the lead, 1/3 the board: each line enters one pin and leaves by the other.  VBUS (pin 5)
    # open: tied to this board's rails it would let the node's pull-ups feed them with DUT_5V off (ST allows
    # it open; the diodes then clamp through the part's own zener)
    # inside J1's pads: U4 level with its pins 3 and 2, U5 with pin 1 (their lead side facing J1); C1, J1's
    # bulk, by its +5V pin
    part(s, "U4", "esd", {"6": "LEAD_SDA", "1": "BUS_SDA", "4": "LEAD_SCL", "3": "BUS_SCL", "5": None, "2": "GND"},
         pcb=P(87.9, J1_Y + 4.0, 0), sch=at(44, 24, rot=180))
    s.wire("J1.2", (30, 28), (30, 23), "U4.4")
    s.wire("J1.3", (32, 29), (32, 24), "U4.6")
    part(s, "U5", "esd", {"6": "LEAD_INT", "1": "BUS_INT", "4": None, "3": None, "5": None, "2": "GND"},
         pcb=P(87.9, J1_Y + 7.95, 0), sch=at(44, 40, rot=180))
    C(s, "C1", "22u", "+5V", "GND", size="1206", pcb=P(88.0, J1_Y - 7.0, 90), sch=at(24, 48))

    s.frame("3.3 V for the hub, the expanders and the INA226s (AP2112K, ≈ 50 mV dropout at 0.1 A)", 6, 60, 70, 86)
    s.tag("+5V", (24, 66), "up")
    s.wire((24, 66), (24, 69), "U3.VIN")
    part(s, "U3", "ldo_lp", {"VIN": "+5V", "EN": "+5V", "GND": "GND", "NC": None, "VOUT": "+3V3"},
         pcb=P(*LDO, 180), sch=at(34, 70, fields=(-3, -4)))
    C(s, "C2", "1u", "+5V", "GND", pcb=P(*ldo(-0.9, 3.4), 180), sch=at(20, 72))
    s.wire("C2.1", (20, 69), (24, 69))
    s.wire("U3.EN", (28, 70), (28, 69))
    C(s, "C3", "4.7u", "+3V3", "GND", size="0805", pcb=P(*ldo(2.6, 3.4), 180), sch=at(44, 72))
    s.wire("U3.VOUT", (44, 69), "C3.1")
    s.wire((44, 69), (50, 69), net="+3V3")
    s.tag("+3V3", (50, 69), "up")

    s.frame("USB2514B hub on its straps (CFG_SEL 00: self-powered, one transaction translator per port), 24 MHz "
            "crystal", 74, 10, 168, 100)
    hub = {"USBDM_UP": "UP_DN", "USBDP_UP": "UP_DP", "VDDA33": "+3V3", "VDD33": "+3V3", "VSS": "GND",
           "TEST": "GND", "VBUS_DET": "+3V3", "RESET_N": "HUB_RST_N", "XTALIN/CLKIN": "XI", "XTALOUT": "XO",
           "RBIAS": "RBIAS", "CRFILT": "CRFILT", "PLLFILT": "PLLFILT",
           "SCL/SMBCLK/CFG_SEL0": "CFG_SEL0", "HS_IND/CFG_SEL1": "CFG_SEL1",
           # NON_REM1 on CFG_SEL0's pull-down: both straps 0, and in this mode both pins stay unused inputs
           "SDA/SMBDATA/NON_REM1": "CFG_SEL0", "SUSP_IND/LOCAL_PWR/NON_REM0": "NON_REM0"}
    for n in range(1, 5):
        hub[f"USBDM_DN{n}/PRT_DIS_M{n}"] = f"PORT{n}_DN"
        hub[f"USBDP_DN{n}/PRT_DIS_P{n}"] = f"PORT{n}_DP"
        hub[f"PRTPWR{n}/BC_EN{n}"] = None
        hub[f"OCS_N{n}"] = None              # internal pull-ups: the expander reads FAULT, not the hub
    part(s, "U1", "usb2514b", hub, pcb=P(HX, HY, 0), sch=at(130, 50, fields=(-6, -18)))
    # the six 3.3 V pins on one rail, its decoupling above
    s.wire((124, 32), (133, 32), net="+3V3")
    s.tag("+3V3", (124, 32), "up")
    for pin, x in (("5", 127), ("10", 128), ("29", 129), ("36", 130), ("15", 132), ("23", 133)):
        s.wire(f"U1.{pin}", (x, 32))
    part(s, "Y1", "xtal24", {"1": "XI", "3": "XO", "G": "GND"}, pcb=P(78.0, 8.0, 0), sch=at(104, 53))
    s.wire("Y1.1", (102.5, 51), "U1.XTALIN/CLKIN")
    s.wire("Y1.3", (110, 53), (110, 52), "U1.XTALOUT")
    C(s, "C4", "33p", "XI", "GND", pcb=P(74.9, 8.3, 90), sch=at(98, 56))
    s.wire("C4.1", (98, 51), (102.5, 51))
    C(s, "C5", "33p", "XO", "GND", pcb=P(81.4, 8.4, 90), sch=at(110, 56))
    s.wire("C5.1", (110, 53))
    for i, (kind, ref, val, net, xy, rot) in enumerate((
            ("R", "R1", "12k", "RBIAS", (78.0, 11.45), 90), ("C", "C6", "100n", "PLLFILT", (76.5, 11.45), 90),
            ("C", "C7", "100n", "CRFILT", (78.6, 22.0), 270), ("R", "R3", "100k", "CFG_SEL0", (83.4, 22.0), 270),
            ("R", "R4", "100k", "CFG_SEL1", (85.0, 22.0), 270), ("C", "C13", "1u", "HUB_RST_N", (84.9, 8.4), 90))):
        (R if kind == "R" else C)(s, ref, val, net, "GND", pcb=P(*xy, rot), sch=at(84 + 8 * i, 80))
    R(s, "R2", "10k", "+3V3", "HUB_RST_N", pcb=P(83.4, 8.4, 270), sch=at(132, 80))
    # NON_REM0 (SUSP_IND after reset, an output): its own 100k, not shared with CFG_SEL1 (HS_IND, an output too)
    R(s, "R5", "100k", "NON_REM0", "GND", pcb=P(84.1, 11.8, 90), sch=at(140, 80))
    for i, (ref, (x, y, rot)) in enumerate((("C8", (75.0, 11.45, 90)), ("C9", (82.6, 11.45, 90)),
                                            ("C10", (81.8, 22.0, 270)), ("C11", (77.0, 22.0, 270)),
                                            ("C12", (80.2, 22.0, 270)))):
        C(s, ref, "100n", "+3V3", "GND", pcb=P(x, y, rot), sch=at(80 + 6 * i, 22))

    s.frame("Two TCA6408A expanders, one per pair of ports: EN, FAULT_N, RESET, BOOT", 172, 10, 228, 70)
    for i, (ref, cref, (x, addr), sy) in enumerate((("U2", "C14", EXP[0], 24), ("U6", "C15", EXP[1], 52))):
        exp = {"V_{CCI}": "+3V3", "V_{CCP}": "+3V3", "~{RESET}": "+3V3", "GND": "GND", "EPAD": "GND",
               "ADDR": addr, "SCL": "SCL", "SDA": "SDA", "~{INT}": "INT"}
        for half, n in (("a", 2 * i + 1), ("b", 2 * i + 2)):
            for pin, sig in EXP_LINES[half].items():
                exp[pin] = f"PORT{n}_{sig}"
        part(s, ref, "tca6408", exp, pcb=P(x, EXP_Y, 0), sch=at(200, sy, fields=(-4, -9)))
        C(s, cref, "100n", "+3V3", "GND", pcb=P(x + 3.4, EXP_Y, 270), sch=at(184, sy - 4))
    s.frame("Mounting: PT 2.6 × 8 into the drawer's floor bosses", 172, 76, 228, 92)
    for i, (x, y) in enumerate(CFG["holes"]):
        part(s, f"H{i + 1}", "hole25", {}, "PT2.6", pcb=P(x, y - DY, 0), in_bom=False, sch=at(180 + 12 * i, 85))
    # the lead's bus (BUS_*, the node's pull-ups) and this board's (SDA/SCL/INT, pulled up here): a 2N7002
    # per line, gate on +3V3 (NXP AN10441).  Either side pulling low turns the FET on (the body diode starts
    # it from the lead's side); with this board unpowered it stays off.  In the rear row's free corner.
    s.frame("I²C isolation: open with DUT_5V off, so the node's pull-ups cannot feed this board", 172, 96, 228, 150)
    for i, (q, r, line, val) in enumerate((("Q1", "R6", "SDA", "4.7k"), ("Q2", "R7", "SCL", "4.7k"),
                                           ("Q3", "R8", "INT", "10k"))):
        x = 69.55 + 3.45 * i
        part(s, q, "nfet", {"G": "+3V3", "S": line, "D": "BUS_" + line}, pcb=P(x, 2.6, 90),
             sch=at(190, 108 + 14 * i))
        R(s, r, val, "+3V3", line, size="0402", pcb=P(x, 5.5, 0), sch=at(210, 106 + 14 * i))
    s.notes_at = (6, 104, 160)
    s.note("Hub on its straps: CFG_SEL[1:0] = 00 and NON_REM[1:0] = 00, every strap pin on a 100k to GND (NON_REM1")
    s.note("  shares CFG_SEL0's): self-powered, one TT per port; OCS_N left on their pull-ups (the expander reads")
    s.note("  each FAULT).  PRTPWR unused: the switches follow the expander.  VBUS_DET on 3.3 V (host always attached).")
    s.note("Expander pins are inputs at power-up: EN pulled down (every port off until the firmware enables it within")
    s.note("  the bay's budget), RESET/BOOT pulled up (released).")
    s.note("INT (J1.1 → the node's IO4): both expanders' INT and the four INA226 ALERTs, open drain, wired-OR, through Q3.")
    s.note("I²C and INT: the node's pull-ups on BUS_*, 4.7k / 4.7k / 10k here; with DUT_5V off the chips here lose their")
    s.note("  registers: the firmware sets them up again after each DUT_5V on, and leaves 0x20/0x21/0x41–0x45 alone while off.")
    s.note("Lead: the node's J7 mirrored, one 'Same direction' PH 8 cable.  The upstream pair has no ESD here: the")
    s.note("  lead stays plugged inside the drawer, the node protects its own end.")
    for n in range(1, 5):
        port(b, n)

    usb_tracks, usb_vias = usb_routes()
    loc_tracks, loc_vias = local_routes()
    # J1's mouth corner (front right) is rounded tighter: its mounting pad comes within 0.3–0.5 mm of both edges
    outline = [(0, 0, 1.5), (W, 0, 1.5), (W, H, 0.5), (0, H, 1.5)]
    # In2: +5V everywhere but a +3V3 area under the ports' rear rows (from the rear edge), the expanders and
    # the hub, with a tab under each INA226 (its VS and address straps), 0.6 mm short of the B.Cu pairs' lane
    # at y 12.4, a shallow one under the hub's bottom row of capacitors (their +3V3 vias), and a bump behind
    # J1 under U3's output side; +5V passes beneath the hub (a 2.5 mm neck with no via, b.pcb["keepouts"]
    # "in2-5v-neck") and right of it, to J1 and under U3's VIN side.  Two notches give the B.Cu pairs one
    # reference all along: the upstream pair's run west and down to the hub, PORT1's start by its vias.
    tabs = [(CFG["usb"][n] + 1.2, min(CFG["usb"][n] + 9.4, 75.3)) for n in range(4)]
    slant = lambda y: 75.3 - (75.3 - tabs[-1][1]) * (19.5 - y) / (19.5 - 9.2)   # the area's west edge
    edge = 88.0 + UP_Y - 1.31       # x + y on the +3V3 side of the diagonal: the pair's half width + 0.6 mm, × √2
    v33 = [(0.4, 0.4 - DY), (89.0, 0.4 - DY), (89.0, LDO[1] + 1.9), (85.6, LDO[1] + 1.9), (85.6, round(edge - 85.6, 3)),
           (round(edge - 9.9, 3), 9.9), (79.9, 9.9), (79.9, 12.6),
           (85.6, 12.6), (85.6, 19.5), (82.6, 19.5), (82.6, 20.9), (76.2, 20.9), (76.2, 19.5), (75.3, 19.5),
           (round(slant(14.4), 3), 14.4), (76.1, 14.4), (76.1, 12.05), (round(slant(12.05), 3), 12.05)]
    for x0, x1 in reversed(tabs):
        v33 += [(x1, 9.2), (x1, 11.8), (x0, 11.8), (x0, 9.2)]
    v33 += [(0.4, 9.2)]
    isle = lambda pts: sh([ldo(ox, oy) for ox, oy in pts])         # an island of the unturned LDO layout
    b.pcb = {
        "size": (W, H), "layers": CFG["layers"], "outline": outline, "passes": 60,
        "inner": [("In1.GND", "power"), ("In2.PWR", "power")],
        "stackup": "JLC04161H-7628", "finish": "HASL",
        "edge_parts": ["J*"],
        "defer_pours": False,
        # nets carrying power (≳ 0.5 A): their IC, connector and big pads connect solid to the pours, small
        # parts keep reliefs (pcbgen.power_pads); the number is the spokes a relieved pad of theirs keeps
        "power_nets": {"GND": 1, "+5V": 2, "PORT?_5V_SW": 2, "PORT?_VBUS": 2},
        # net: (plane, via Ø, drill, track width); pins over another net's area are routed instead
        "fanout_nets": {"GND": ("In1.Cu", 0.5, 0.3, 0.25), "+5V": ("In2.Cu", 0.6, 0.3, 0.4),
                        "+3V3": ("In2.Cu", 0.5, 0.3, 0.3)},
        "plane_nets": {"+5V": "In2.Cu", "+3V3": "In2.Cu"},
        "stitch": 4.0,
        "zones": [
            {"layer": "In1.Cu", "net": "GND"},
            {"layer": "In2.Cu", "net": "+5V"},
            {"layer": "In2.Cu", "net": "+3V3", "poly": sh(v33), "priority": 1, "name": "in2-3v3"},
            {"layer": "F.Cu", "net": "GND"},
            {"layer": "B.Cu", "net": "GND"},
            # U3 (AP2112K, up to ≈ 0.31 W): top-side copper on VIN (pin 1), EN (pin 3, with C2's +5V pad)
            # and GND (pin 2, a finger between them and under the body), each with vias to its plane
            # (LDO_VIAS); exclusive, so the router keeps its tracks off them
            {"layer": "F.Cu", "net": "+5V", "name": "ldo-vin", "priority": 3, "exclusive": 0.3,
             "poly": isle([(-2.9, -1.65), (-0.35, -1.65), (-0.35, -0.55), (-2.9, -0.55)])},
            {"layer": "F.Cu", "net": "+5V", "name": "ldo-en", "priority": 3, "exclusive": 0.3,
             "poly": isle([(-2.9, 0.55), (-0.35, 0.55), (-0.35, 1.55), (-1.05, 1.55), (-1.05, 4.05), (-2.9, 4.05)])},
            {"layer": "F.Cu", "net": "GND", "name": "ldo-gnd", "priority": 4, "exclusive": 0.3,
             "poly": isle([(-2.9, -0.25), (0.1, -0.25), (0.1, 0.25), (-2.9, 0.25)])},
        ],
        # Freerouting keeps only its 0.15 mm clearance from the outline: a 0.35 mm band inside every edge
        "keepouts": [{"name": f"edge{i}", "poly": [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]}
                     for i, (x0, y0, x1, y1) in enumerate((
                         (0, 0, W, 0.35), (W - 0.35, 0, W, H), (0, H - 0.35, W, H), (0, 0, 0.35, H)))] + [
            # under the hub's caps the +5V plane's only link between its two halves (all the ports' current)
            # is the neck below the +3V3 tab: no via in it, down to the edge band (the caps' GND pads take a
            # bus to vias beyond it, local_routes)
            {"name": "in2-5v-neck", "poly": sh([(76.2, 21.1), (82.6, 21.1), (82.6, 23.65), (76.2, 23.65)]),
             "vias_only": True}],
        "tracks": usb_tracks + loc_tracks,
        "vias": usb_vias + loc_vias + [(n, x, round(y + DY, 4), d, dr) for n, x, y, d, dr in LDO_VIAS],
        # GCT's USB4105 footprint puts its GND pads 0.19 mm from its own NPTH pegs (the datasheet's land pattern)
        "dru": "".join(f"""
(rule "USB4105 {r}: GND pads beside its own pegs"
	(condition "A.memberOfFootprint('{r}') && B.memberOfFootprint('{r}')")
	(constraint hole_clearance (min 0.19mm)))
""" for r in ("J101", "J201", "J301", "J401")),
        "texts": [
            {"text": "DATA ×4 v1.0", "x": 1.6, "y": 17.6 + DY, "size": 0.8, "rot": 90},
            *({"text": str(n), "x": CFG["usb"][n - 1] - 4.4, "y": 15.6 + DY, "size": 1.0} for n in range(1, 5)),
        ],
    }
    return b


NETCLASSES = [
    {"name": "Power", "clearance": 0.15, "track_width": 0.6, "via_diameter": 0.8, "via_drill": 0.4,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 1,
     "_patterns": ["+5V"]},
    {"name": "Port", "clearance": 0.15, "track_width": 0.4, "via_diameter": 0.6, "via_drill": 0.3,
     "diff_pair_width": 0.2, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 2,
     "_patterns": ["*PORT?_5V_SW", "*PORT?_VBUS"]},
    {"name": "USB", "clearance": 0.15, "track_width": 0.25, "via_diameter": 0.5, "via_drill": 0.3,
     "diff_pair_width": 0.25, "diff_pair_gap": 0.15, "wire_width": 6, "bus_width": 12, "line_style": 0,
     "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 3,
     "_patterns": ["*_DP", "*_DN"]},
]
