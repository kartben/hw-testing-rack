# Sourcing notes (2026-10-19)

A snapshot for the first order of the 8-bay rack, to read beside [`README.md`](README.md) (generated).  Stock and
prices change: check them again on the day of the order.

## AP33772S (power hub U1)

| Part | LCSC / JLC | DigiKey FR | Others |
|---|---|---|---|
| AP33772SDKZ-13-**FA02** (VSEL firmware, the BOM's part, C50341643) | 0 | 0, 2 689 due 14/12/2026, factory lead 32 weeks | Avnet 0, not listed at Farnell |
| AP33772SDKZ-13-**FA01** (first firmware, C24374260) | 0 | **365 in stock**, €2.09 (1), €1.54 (10) HT | |

Same die, package (W-QFN4040-24), pinout and I2C register map.  FA02 adds VSEL (pin 11), GPIO (pin 7) and Data
Role Swap.  On FA01 both pins are NC (datasheet DS46176 Rev. 5-2), so R7 (VSEL, 39 k) does nothing there.
Without VSEL, FA01 first asks for 5 V (VSELMIN defaults to 5 V: VRACK = 5 V, the row eFuses stay off), and the
controller asks for 20 V or 28 V over I2C.  FA01 fits the v0.5 hub as drawn, but the firmware then has to request
the contract.  To get it onto the JLC boards: JLC Global Sourcing, or consigned parts.

If neither variant can be had, the hub needs a new design.  These EPR sinks with I2C are in stock at LCSC:
WCH CH224A / CH224Q (C42459160 / C46061833: 28 V, no switch driver, no V/I telemetry) and Hynetek HUSB238A-BB001
(C24833806: 28 V, gate driver, EPR registers not in the public datasheet).  ST's STUSB4500 (C2678061) stops at 20 V,
which covers 8 bays ([docs/power.md](../docs/power.md)).

## Camera lens

The Mega 3MP has a 1/4" sensor, and its stock 2.8 mm lens gives 90° diagonally (75° × 56°).  The worst board needs
90° × 67°.  **Arducam LN006** (M40180H10, 1/4", 1.8 mm, 650 nm IR-cut) has a published 125° / 100° / 75°
(D / H / V) on a 1/4" sensor.  It is end-of-life.  **Arducam LN005** (M27210H08, 2.1 mm) gives ≈ 106–115° D, scaled
from the stock lens.  A shorter focal length can need a shorter holder to focus: try it on the first camera.

## Outside AliExpress

| Item | Source | Price (2026-10-19) |
|---|---|---|
| Arducam Mega 3MP M12 (B0434) ×2, LN006 lens ×2 | Welectron | €33.90 + €8.90 each, VAT incl. |
| Arduino GIGA R1 WiFi + GIGA Display Shield | DigiKey FR (Arduino Store: €77.90 + €73.20) | €61.11 + €55.84 HT |
| USB PD 3.1 EPR charger, single port, 28 V × 5 A | Apple 140 W USB-C adapter (Amazon.fr) | €78.37 |
| USB-C cable, 240 W e-marked | UGREEN 240 W PD 3.1, 1 or 2 m (Amazon.fr) | €10.82 |
| Drag chain 7×7, 2 m | Olimex DRAG-CHAIN-7X7 | €4.00/m + VAT |
| PETG, 3 kg | Bambu Lab EU store (PETG HF: discontinued, stock left) | €15.99–19.99/kg |
