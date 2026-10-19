# Power

**Goal:** "something I can just plug in."  The rack runs from **one USB-C PD
charger**, outside the rack, on one cable: no mains anywhere in the printed
parts.  The cable plugs into the **power box**, a printed box in the base cell
under A1 that holds the **power hub v0.5**:

* a **USB PD 3.1 sink** (Diodes AP33772S) that asks the charger for 20 V, or
  for 28 V EPR when it offers it, and switches the rack bus (VRACK) on once the
  contract is in place;
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

1. **Plug-in.**  VBUS comes up at 5 V.  The AP33772S (the FA01, without VSEL)
   takes the charger's default **5 V** contract and turns its back-to-back NMOS
   switch on: VRACK is 5 V, and every row stays locked out (the eFuses' UV
   lockout is 15 V).  A blank or crashed controller leaves the rack there, safe.
2. **Controller.**  The ESP32-S3 runs from VBUS *ahead of* the switch (a buck
   on from ≈ 4 V, a low-dropout LDO): it is alive from the first 5 V.  It reads
   the charger's offers over I²C, sets the sink's VSELMIN to 15 V (the switch
   opens below it) and asks for **28 V EPR** when the charger and the cable
   offer it, otherwise for **20 V**.  Contracts under 15 V never power the rows.
3. **Rows.**  Every row's eFuse is **off** until the contract is final (each
   eFuse's SHDN is pulled low).  The controller then turns the rows on one
   after the other, so each bay node sees one clean power-up instead of
   5 → 20 → 28 V steps.
4. **Contract drops** (a renegotiation, a hard reset, a multi-port charger
   reallocating power): the AP33772S interrupts the controller, which **sheds
   rows in priority order** and turns them back on once the contract is
   stable again.

The AP33772S keeps the contract, and the EPR keep-alive, by itself: an ESP32
reboot does not drop the rack's power.  The firmware holds the row enables
across a controller reset (GPIO hold).

**Ride-through.**  The 100 µF bulk capacitor is there for millisecond load
steps.  A PD hard reset takes VBUS to 0 V for ≈ 1 s; riding through even
250 ms at 60 W, between 20 V and the nodes' 13.5 V, would need ≈ 0.14 F
(supercapacitors, and the PD spec limits what a sink may present before its
switch).  **The rack restarts in that case**; a dedicated single-port charger
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
The hub knows both sides: the contract (the AP33772S) and each row's current
(the eFuses' IMON).  When the negotiated power is below the worst case, it
budgets: it limits or sheds rows instead of letting the charger trip.

Each row has its own eFuse, set to **1.6 A**: rows are wired with JST PH (2 A
per contact), so the limit protects the connectors and the 24 AWG cables.  A
shorted row sits at its limit while the others carry on.

## Options compared

| Architecture | Cords | Max power | Cost | Verdict |
|---|---|---|---|---|
| **USB-C PD 3.1 EPR (28 V / 5 A), AP33772S sink on the hub** | 1 charger + 5 A cable | 140 W | ≈ €5 of sink parts + ≈ €80 charger and cable | **chosen (hub v0.5)**: nothing to wire, telemetry over I²C |
| Certified 24 V brick inside the power box (GST60A24 / GST90A24) | 1 C13 cord | 60 / 90 W | ≈ €30 | hub v0.4: a bigger box, a cut and crimped DC cord |
| Internal AC-DC (UHP-200-24) + C14 inlet | 1 C13 cord | 201 W | ≈ €80–95 | needs a mains enclosure: DIY mains wiring, PE, fusing |
| PoE++ per row (802.3bt) | 4 Ethernet + PoE++ switch | 51–71 W per row | ≈ €100 modules + switch | not worth it with Wi-Fi nodes |

### Why the AP33772S

* **Negotiates on its own** (20 V from a resistor at power-up) and keeps the
  contract through controller resets.
* **I²C to the controller:** the charger's offers (PDOs), the contract, the
  bus voltage and current (its own 5 mΩ shunt), the temperature (an NTC by the
  switch), and OVP / OCP / UVP / OTP with an interrupt.
* **Drives the NMOS switch itself** (a charge pump on PWR_EN), 28 V EPR.
* **Zephyr:** an AP33772S driver is under review upstream
  ([zephyr#114554](https://github.com/zephyrproject-rtos/zephyr/pull/114554),
  sensor API).  The hub firmware carries it until it lands, preferably reshaped
  as an MFD (a regulator child for the contract, a sensor child for V/I/T).

Sourcing (2026-10-19): the AP33772SDKZ-13-FA02 (VSEL: 20 V by itself) is out of
stock everywhere until ≈ 14/12/2026 (32 weeks from the factory).  The hub takes the
**FA01**: same die, package, pinout and I²C map, pins 7 and 11 NC, so it starts at
5 V and the controller asks for more (step 1).  JLC buys it through Global Sourcing
from DigiKey (365 in stock, LCSC C24374260 at 0); re-check the day of the order.
R7 (the FA02's VSEL resistor) stays on the board: an FA02 drops in later.  If the
FA01 goes too: WCH CH224A/Q or the Hynetek HUSB238A, both a hub respin.

### Bus voltage: VRACK, 20 or 28 V

At 28 V a row draws ≤ 1.6 A (its eFuse limit) and the whole rack ≤ 5 A (the
contract).  The input is a 5 A USB-C receptacle (GCT USB4105) on wide pours,
the rows JST PH (2 A) on 24 AWG.  The bay nodes run from **13.5 to 30 V**
(the buck starts above 13.5 V and stops below 10.8 V; 60 V silicon), so the
same boards run from a 24 V brick too, or on a desk from a 15–30 V supply on J1.

## Protection chain

```
USB PD 3.1 charger → 5 A e-marked cable → hub (in the power box):
  USB4105 (5 A) → SMAJ30A TVS → 5 mΩ shunt (Kelvin, the AP33772S reads it)
  → AP33772S: contract, then back-to-back IRF7842 NMOS switch (OVP / OCP / UVP / OTP) → VRACK, 100 µF
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
* The AP33772S's switch blocks both ways (back-to-back NMOS): VRACK's
  capacitance never back-feeds VBUS during a hard reset.

Sources: Diodes AP33772S datasheet (DS46176 rev. 10-2) and EVB user guide
(rev. 2.0), USB PD 3.1 specification, TI TPS2660 / LMR51635 (SLUSF64B)
datasheets, ADI AN-88 (hot-plug ringing), LCSC listings (Oct 2026).
