# Power

**Goal:** "something I can just plug in."  The rack runs from **one USB-C PD
charger**, outside the rack, on one cable: no mains anywhere in the printed
parts.  The cable plugs into the **power box**, a printed box in the base cell
under A1 that holds the **power hub v0.5**:

* a **USB PD 3.2 sink** (WCH CH224A) that asks the charger for 9 V at
  plug-in, then for 28 V EPR (or 20 V) when the controller asks over I²C.
  VBUS is the rack bus (VRACK): there is no input switch, the eFuses keep the
  rows off until the contract is final;
* an **eFuse per row** (TPS26600, 1.6 A), off until the controller turns it on;
* the **rack controller** (an ESP32-S3, CAN master; see [can.md](can.md) and
  [electronics.md](electronics.md#power-hub-v05--4-layers-76--140-mm)).  The box is
  drawn around its outline and connector positions in `config/rack.yaml` ›
  `pcb.power_hub`.

One 6-pin JST PH feed per row (VRACK, CAN, POS) runs from the box's left wall to
the row's first node.  Box and lid: [mechanical.md](mechanical.md#power-box).

![The power box, lid off: the hub v0.5, the charger's USB-C cable at the rear, the status LEDs at the front](img/power-box.jpg)

*Lid off, labels inlaid in white.  Left: from the rear, the charger's USB-C cable (PD IN) and the row outputs' windows (A–D).  Right: from the front, the status LEDs (ON / FAULT per row, PD, CTL) and the console USB-C.*

## The charger

| | |
|---|---|
| **Recommended** | a **dedicated, single-port USB PD 3.1 EPR charger, 140 W** (28 V × 5 A) |
| **Cable** | USB-C to USB-C, **5 A e-marked** (EPR, 240 W rated), 1–2 m.  Above 3 A a charger only offers its full current through an e-marked 5 A cable |
| **Also works** | a 100 W charger (20 V × 5 A): normal use, with power budgeting.  A 65 W one (20 V × 3.25 A): a light rack |
| **Avoid** | sharing the charger: a multi-port charger can withdraw its 28 V / 5 A offer when another device is plugged in, and renegotiate the rack down |

The hub never accepts 36 V or 48 V (EPR goes up to 48 V): the bay nodes' TVS
stands off 33 V and the eFuses cut out at 33 V.  20 V and 28 V are both fine,
the nodes start above 13.5 V.

## Negotiation and sequencing

1. **Plug-in.**  VBUS comes up at 5 V, and the CH224A asks for **9 V** (its
   CFG1 resistor, 6.8 k): VRACK is 9 V, and every row stays locked out (the
   eFuses' UV lockout is 15 V).  A blank or crashed controller leaves the rack
   there, safe.
2. **Controller.**  The ESP32-S3 runs from VRACK (a buck on from ≈ 4 V, a
   low-dropout LDO): it is alive from the first 5 V.  It reads the charger's
   offers over I²C and asks for **28 V EPR** when the charger and the cable
   offer it, otherwise for **20 V**, then checks VRACK on its ADC.  Contracts
   under 15 V never power the rows (the eFuses' UV).
3. **Rows.**  Every row's eFuse is **off** until the contract is final (each
   eFuse's SHDN is pulled low).  The controller then turns the rows on one
   after the other, so each bay node sees one clean power-up instead of
   5 → 20 → 28 V steps.
4. **Contract drops** (a renegotiation, a hard reset, a multi-port charger
   reallocating power): the CH224A's PG goes high (an interrupt on the
   controller), which **sheds rows in priority order** and turns them back on
   once the contract is stable again.

The CH224A keeps the contract, and the EPR keep-alive, by itself: an ESP32
reboot does not drop the rack's power.  The firmware holds the row enables
across a controller reset (GPIO hold).

**Ride-through.**  The 100 µF bulk capacitor is there for millisecond load
steps.  A PD hard reset takes VBUS to 0 V for ≈ 1 s; riding through even
250 ms at 60 W, between 20 V and the nodes' 13.5 V, would need ≈ 0.14 F
(supercapacitors, and the PD spec limits a sink's bulk capacitance).  **The rack restarts in that case**; a dedicated single-port charger
doesn't renegotiate in normal use.

## Budget

Two rows of four to start (2026-10-18), two of the bays with a camera:

| | per bay | 8 bays |
|---|---|---|
| node (ESP32-S3-WROOM-1 with Wi-Fi on for USB/IP, LED, buck + LDO losses) | ≈ 0.7–1 W | ≈ 7 W |
| typical dev board (Nucleo, nRF DK, FRDM, Pico, C6 …) | ≈ 0.2–0.7 W | ≈ 4 W |
| big board (F746G-DISCO with its LCD, ESP32-S3 on Wi-Fi) | ≈ 1.5–2.5 W | — |
| camera (Arducam Mega streaming, from its 3.3 V on the pod board) | ≈ 0.6 W | 2 cameras ≈ 1.2 W |
| its light (4 white LEDs, 128 mA from CAM_5V, while lit) | ≈ 0.65 W | 2 pods ≈ 1.3 W |
| **realistic, whole rack** (a couple of big boards, lights on) | | **≈ 20–25 W** |
| **worst case** (every DUT at its 1.5 A switch limit, cameras lit) | ≈ 11 W | ≈ 90 W |

The camera and its light are fed by the bay's own node (CAM_5V, behind its 0.5 A PTC), so they
count in that bay's row.  The 140 W charger covers even the worst case with room for a third
row (≈ 130 W worst case for 12 bays); a 100 W one covers 8 bays' worst case.
The hub knows both sides: the contract (the CH224A: the charger's offers and
the current granted) and each row's current (the eFuses' IMON).  When the negotiated power is below the worst case, it
budgets: it limits or sheds rows instead of letting the charger trip.

Each row has its own eFuse, set to **1.6 A**: rows are wired with JST PH (2 A
per contact, on 24 AWG: the row cables are crimped in 24 AWG), so the limit protects the connectors and the cables
(their gauge: [power-distribution-review.md](power-distribution-review.md)).  A
shorted row sits at its limit while the others carry on.

**No batteries on rack DUTs.**  Each bay's DUT side is limited to ≈ 1.4 A (the
node's TPS2553), and a DATA ×4 board's ports to 0.5 A each.  Four small boards
without batteries take 0.3–0.8 A between them, with millisecond radio peaks of
0.27–0.4 A each; a board charging its LiPo takes 0.6–1.2 A on its own (a Wio
Terminal on its battery chassis ≈ 1.0–1.2 A, a XIAO ESP32-C3 with a cell
≈ 0.73 A), and a LiPo charging unattended in a closed drawer is a fire risk.
Take the battery off (or out of the chassis) before a board goes into the rack.
The node's +5V is set to 5.24 V (FB 100k/18k), so ≈ 4.75 V still reaches the
DATA board at 1.4 A through the switch, the shunt and ≈ 50 cm of PH lead.

## Options compared

| Architecture | Cords | Max power | Cost | Verdict |
|---|---|---|---|---|
| **USB-C PD 3.1 EPR (28 V / 5 A), CH224A sink on the hub** | 1 charger + 5 A cable | 140 W | ≈ €1 of sink parts + ≈ €80 charger and cable | **chosen (hub v0.5)**: nothing to wire, the contract over I²C |
| Certified 24 V brick inside the power box (GST60A24 / GST90A24) | 1 C13 cord | 60 / 90 W | ≈ €30 | hub v0.4: a bigger box, a cut and crimped DC cord |
| Internal AC-DC (UHP-200-24) + C14 inlet | 1 C13 cord | 201 W | ≈ €80–95 | needs a mains enclosure: DIY mains wiring, PE, fusing |
| PoE++ per row (802.3bt) | 4 Ethernet + PoE++ switch | 51–71 W per row | ≈ €100 modules + switch | not worth it with Wi-Fi nodes |

### Why the CH224A

* **Negotiates on its own** (9 V from one resistor at power-up) and keeps the
  contract, and EPR's keep-alive, through controller resets.
* **I²C to the controller** (address 0x22, on in the one-resistor mode): the
  charger's offers (PDOs, EPR's too), the contract's state (PD, EPR), the
  voltage request (5 to 28 V, PPS, AVS) and the current granted.  PG (open
  drain) goes low once the contract is in place.
* **In stock at LCSC** (12 739 on 2026-10-19, $0.43), one extended part type
  and three passives.  Its pins are rated 32 V: its supply runs through
  56 Ω + 1 µF.
* **What it does not do:** no switch driver and no V / I / T telemetry.  The
  eFuses do the switching (off until enabled, reverse blocking), VRACK is on
  the controller's ADC, each row's current on its IMON.

The AP33772S (FA01, hub v0.5 until this change) had all that, but LCSC had none
(the FA02 is out until ≈ 14/12/2026): JLC would have bought it through Global
Sourcing from DigiKey (≈ $20 for 5).  The Hynetek HUSB238A (C24833806, 2 919 in
stock, $0.64) would also fit, but its EPR registers are not in the public
datasheet.

### Bus voltage: VRACK, 20 or 28 V

At 28 V a row draws ≤ 1.6 A (its eFuse limit) and the whole rack ≤ 5 A (the
contract).  The input is a 5 A USB-C receptacle (GCT USB4105) on wide pours,
the rows JST PH (2 A on 24 AWG leads, crimped since 2026-10-21:
[power-distribution-review.md](power-distribution-review.md)).  The bay nodes run from **13.5 to 30 V**
(the buck starts above 13.5 V and stops below 10.8 V; 60 V silicon), so the
same boards run from a 24 V brick too, or on a desk from a 15–30 V supply on J1.

## Protection chain

```
USB PD 3.1 charger → 5 A e-marked cable → hub (in the power box):
  USB4105 (5 A) → SMAJ30A TVS → VRACK (VBUS itself, no input switch), 100 µF
     CH224A on VBUS through 56 Ω + 1 µF: the contract (9 V, then 28 / 20 V as the controller asks)
  → 4 × TPS26600 eFuse (rows A–D, 1.6 A limit, ≈ 5 ms soft start, UV 15 V / OV 33 V, auto-retry, off until enabled)
  → 6-pin JST PH → each bay node:
     SUD50P06 P-FET → SMBJ33A TVS → 100 µF → LMR51635 (60 V, on above 13.5 V) → 5 V
     → TPS2553 → 50 mΩ shunt (INA226) → DUT
```

* Hot-plugging a bay node into a live bus rings up to ~2× the bus on ceramic
  caps: the bay buck is a **60 V** LMR51635 and its TVS clamps below 54 V; the
  electrolytic damps the ringing.
* The hub eFuses soft-start each row, so plugging a row never browns out the
  others, and a shorted bay only trips its own row.
* No input switch: the eFuses block reverse current (back-to-back FETs), so
  the rows' capacitance never back-feeds VBUS during a hard reset.  What stays
  on VBUS is the hub's own ≈ 150 µF (the 100 µF bulk, the buck's and the
  eFuses' inputs) and the controller, as with the AP33772S's switch on; only at
  plug-in, before the 9 V contract, does the charger now see it too.
* **The 150 µF at plug-in stays** (decided 2026-10-20).  USB PD expects about
  10 µF on a sink at attach; the AP33772S hub connected the same bulk at its
  first 5 V contract.  At 5 V it is ≈ 0.75 mC, which a charger's current limit
  charges in well under a millisecond.  And the 100 µF electrolytic (C8) is
  what holds VBUS down when the eFuses cut a load: the ceramics alone keep only
  ≈ 15 µF at 28 V (DC bias), and the charger cable's ≈ 1 µH would ring VBUS
  ≈ 1.3 V up at a 5 A cut, toward the CH224A's 32 V; with C8, ≈ 0.5 V and
  damped.  Bring-up checks it on two or three chargers (assembly.md); a charger
  that refuses it gets C8 left off.
* A short on VRACK itself, ahead of the eFuses, is the charger's to catch
  (every PD source has its own OCP).  Above 28 V: the eFuses cut out at 33 V,
  and the CH224A resets above 32 V; its supply's RC rides through a surge's
  fast edge, but the SMAJ30A only starts at 33.3 V.
* **No clamp on the CH224A's supply.**  A zener there would have to stay off
  up to 29.4 V (28 V + 5 %) and hold under 32 V: no stocked zener fits that
  window, and behind 56 Ω it would carry tens of milliamps, watts, before the
  SMAJ30A takes over at 33.3 V.  A PD charger regulates VBUS to ±5 % and has
  its own OVP; the RC and C8 take fast edges and load dumps off.  What is left,
  a faulty charger holding VBUS between 32 and 33.3 V, costs U1 (a $0.43
  ESSOP-10, replaceable by hand).  For more margin the firmware can ask for
  20 V whenever the charger's 20 V offer covers the budget (5 A: 100 W, the
  worst case of 8 bays): the pins then sit 11 V under their rating.

Sources: WCH CH224 datasheet (v2.1), USB PD 3.1 specification, TI TPS2660 / LMR51635 (SLUSF64B)
datasheets, ADI AN-88 (hot-plug ringing), LCSC listings (Oct 2026).
