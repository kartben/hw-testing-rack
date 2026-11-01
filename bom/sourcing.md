# Sourcing notes (2026-10-19)

A snapshot for the first order of the 8-bay rack, to read beside [`README.md`](README.md) (generated).  Stock and
prices change: check them again on the day of the order.

## CH224A (power hub U1, since 2026-10-19)

| Part | LCSC / JLC | Price (LCSC) | Notes |
|---|---|---|---|
| WCH **CH224A** (ESSOP-10, C42459160: the BOM's part) | **12 739** | $0.43 | 1 mm pitch, pin-compatible with the CH224K |
| WCH CH224Q (DFN-10 2 × 2, C46061833) | 11 650 | $0.45 | same chip and I2C map, a smaller leadless package |
| Hynetek HUSB238A-BB001-QN16R (QFN-16 3 × 3, C24833806) | 2 919 | $0.64 | gate driver; EPR registers not in the public datasheet |

The CH224A replaced the AP33772S below: LCSC had none, and JLC would have bought it through Global Sourcing
(≈ $20 for 5).  It drives no switch: the hub's VBUS is VRACK, and the eFuses keep the rows off.

## AP33772S (power hub U1 until 2026-10-19)

| Part | LCSC / JLC | DigiKey FR | Others |
|---|---|---|---|
| AP33772SDKZ-13-**FA02** (VSEL firmware, the BOM's part until 2026-10-19, C50341643) | 0 | 0, 2 689 due 14/12/2026, factory lead 32 weeks | Avnet 0, not listed at Farnell |
| AP33772SDKZ-13-**FA01** (first firmware, C24374260: the BOM's part since 2026-10-19) | 0 | **365 in stock**, €2.09 (1), €1.54 (10) HT | |

Same die, package (W-QFN4040-24), pinout and I2C register map.  FA02 adds VSEL (pin 11), GPIO (pin 7) and Data
Role Swap.  On FA01 both pins are NC (datasheet DS46176 Rev. 5-2), so R7 (VSEL, 39 k) does nothing there.
Without VSEL, FA01 first asks for 5 V (VSELMIN defaults to 5 V: VRACK = 5 V, the row eFuses stay off), and the
controller asks for 20 V or 28 V over I2C.  FA01 fits the v0.5 hub as drawn, but the firmware then has to request
the contract.  To get it onto the JLC boards: JLC Global Sourcing, or consigned parts.

Chosen (2026-10-19, the user): the FA01, through JLC Global Sourcing from DigiKey (5 parts).  The hub firmware sets
VSELMIN to 15 V and asks for the contract; R7 stays fitted, so an FA02 drops in once it is back.

If neither variant can be had, the hub needs a new design (done: the CH224A above).  These EPR sinks with I2C are in stock at LCSC:
WCH CH224A / CH224Q (C42459160 / C46061833: 28 V, no switch driver, no V/I telemetry) and Hynetek HUSB238A-BB001
(C24833806: 28 V, gate driver, EPR registers not in the public datasheet).  ST's STUSB4500 (C2678061) stops at 20 V,
which covers 8 bays ([docs/power.md](../docs/power.md)).

## TCAN1462V (hub U6, node U11)

At the hub's JLC quote (2026-10-19) the TCAN1462VDRQ1 (C7399456) had no stock at LCSC (0, as on 2026-10-18).
JLC asks for another part.  Both alternates in the catalogue keep the SOIC-8 footprint and pinout (VIO on
pin 5, STB on pin 8), so nothing is re-routed:

| Part | LCSC stock | Price | Against the TCAN1462V |
|---|---|---|---|
| NXP TJA1462AT/0Z (C3234095) | 10 500 | $0.83 (10+) | keeps signal improvement; bus pins −36 / +40 V instead of ±58 V (VRACK, 28 V, sits two pins away) |
| TI TCAN1044AVDRQ1 (C3234993) | 23 540 | $0.43 | ±58 V; no signal improvement (the star bus at 250 kbit/s works without it) |

The hub quote used the TJA1462AT/0Z, and both boards take it since (hub U6, node U11; the user, 2026-10-19).
The TCAN1462V stays the alternate.

## USB4105 (node J3, hub J1 / J6, data port J1)

LCSC has stock (3 685 on 2026-10-19), but JLC flags the GCT USB4105-GF-A-120 (C5184243) as hard to process
(its four shell stakes are through-hole).  It adds $0.03 a piece, and its BOM page leaves the line unticked
(quantity 0).  **Tick it again at every order**, or the board comes without its USB-C.  The part stays: it is
rated 5 A (the hub's PD input carries up to 5 A at 28 V), and the stakes hold it against plug forces.

## Camera lens

The Mega 3MP has a 1/4" sensor, and its stock 2.8 mm lens gives 90° diagonally (75° × 56°).  The worst board needs
90° × 67°.  **Arducam LN006** (M40180H10, 1/4", 1.8 mm, 650 nm IR-cut) has a published 125° / 100° / 75°
(D / H / V) on a 1/4" sensor.  It is end-of-life.  **Arducam LN005** (M27210H08, 2.1 mm) gives ≈ 106–115° D, scaled
from the stock lens.  A shorter focal length can need a shorter holder to focus: try it on the first camera.

## DUT cables at the standing port wall (2026-11-01)

The DATA ×6 (and v2) receptacles stand, 15.5 mm apart: the drawer end of a DUT cable is a straight USB-C (an angled
one only if its cable leaves upwards), its overmold within the USB-IF 12.35 × 6.5 mm ([docs/cabling.md](../docs/cabling.md)).
No listing gives the overmold: the ends below were sized on the photos.  Measure the first cable on arrival.

| Cable (config/rack.yaml) | Before | After (prices for one, VAT incl.) | Alternative |
|---|---|---|---|
| `c-to-c`, 15 cm: straight in the drawer, 90° at the board (BeaglePlay, Wio Terminal, GIGA) | OLAF 1005013255525639, "Dual Elbow" (both ends bent) | HDR Store 1005009683032517, "Type-C-bend-straight", 15 cm, €3.69: flat 4-wire USB 2.0, heat-shrunk ends ≈ 10 × 4 mm | BESTAR 1005001325015941 (ADT-Link FPC), "T1-T2", 15 cm, €6.79: sleeved board end ≈ 10.5–12 × 4 mm |
| `c-to-micro-b`, 25 cm, on the 90° adapter (NUCLEO-64, NUCLEO-144) | HOQO 2251832791887129: no longer sold in France, USB-C end bent | Waveshare 1005007989121951, "Straight-Straight", 25 cm, €4.39: same flat cable as above | BESTAR 1005002786476442 (ADT-Link FPC), "T1B-W1", 25 cm, €8.06 |
| `c-to-mini-b`, 25 cm (no board in the population) | HOQO 2251832791887129: no longer sold in France | to pick when a mini-B board returns: neither family has a mini-B end | |
| `c-to-micro-b-straight`, 15 cm (Pico 2) | listing to pick (the 2026-10-19 cart: BESTAR "T1B-W1") | Waveshare 1005007989121951, "Straight-Straight", 15 cm, €3.69 | BESTAR 1005002786476442, "T1B-W1", 15 cm, €6.99 |
| `c-to-c-straight`, 15–20 cm (Nano Matter, XIAO) | listing to pick | HDR Store 1005009683032517, "straight-straight", 15 cm, €3.69 | BESTAR 1005001325015941, "T1-T1", 15 cm, €6.79 |
| `c-to-c-straight-20`, 20 cm (UNO R4) | listing to pick (the 2026-10-19 cart: a USB 3.2 cable, 1005006804935384, overmold not given) | HDR Store 1005009683032517, "straight-straight", 20 cm, €4.09 | BESTAR 1005001325015941, "T1-T1", 20 cm, €7.49 |

The HDR and Waveshare cables look like one maker's flat 4-wire USB 2.0 cable (the same heat-shrunk ends,
straight, bent or side-bent on order).  Its "bend" is across the plug's wide face, as the board ends need.  A flat
cable or FPC bends across its face only: at a standing slot its face stands too, so the arch over a board's rear
edge takes a quarter twist along the cable.  Rejected: OLAF's "Elbow Straight C-C" (€2.65; its straight end is a
round aluminium barrel, thicker than 6.5 mm by the photos) and the DJI-remote "15 cm" cables (both plugs L-shaped).

To check on arrival: each USB-C end within 12.35 × 6.5 mm; BESTAR 1005001325015941 is titled USB 3.1 (10 Gbit/s)
but its photos show ADT-Link's USB 2.0 boards (UT1B), so check its end width too.

## Outside AliExpress

| Item | Source | Price (2026-10-19) |
|---|---|---|
| Arducam Mega 3MP M12 (B0434) ×2, LN006 lens ×2 | Welectron | €33.90 + €8.90 each, VAT incl. |
| Arduino GIGA R1 WiFi + GIGA Display Shield | DigiKey FR (Arduino Store: €77.90 + €73.20) | €61.11 + €55.84 HT |
| USB PD 3.1 EPR charger, single port, 28 V × 5 A | Apple 140 W USB-C adapter (Amazon.fr) | €78.37 |
| USB-C cable, 240 W e-marked | UGREEN 240 W PD 3.1, 1 or 2 m (Amazon.fr) | €10.82 |
| Drag chain 7×7, 2 m | Olimex DRAG-CHAIN-7X7 | €4.00/m + VAT |
| PETG, 3 kg | Bambu Lab EU store (PETG HF: discontinued, stock left) | €15.99–19.99/kg |
