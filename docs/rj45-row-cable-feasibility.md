# RJ45 row cable: feasibility (research, 2026-10-22)

The user's idea: carry the row bus on Ethernet Cat5e patch cords instead of the 6-pin JST PH cables.
The row bus is VRACK, GND, CAN_H, CAN_L, GND and POS (docs/can.md).  A study, no change yet.  This
document covers the electrical side and the verdict; the mechanical side is Mechanics'
([rj45-row-cable-mechanical.md](rj45-row-cable-mechanical.md)).

## Verdict

- **Electrically it works.**
  - 1.6 A a row is 0.8 A a conductor on VRACK's pair.
  - The CAN pair is a real twisted pair.
  - POS goes through a straight cord when IN and OUT share one pinout.
  - Drop and heating are small, and the cords cost less than the JST leads with no crimping.
- **What stops it for rev A is misplugging.**  20–28 V on an Ethernet port burns the port's
  termination resistors (1.3–2.6 W each) within seconds.
  - Every free OUT jack in the rack is live: there is always one, on the last node of each row.
  - The hub can probe its own outputs before switching them on.  Real protection also needs a
    switched, probed VRACK pass-through on every node.
  - That redesigns the node, the hub and the power box's wall, and shortens the drawer's stroke, about 1–2 weeks,
    right before the rev A order.
- **Recommendation: no-go for rev A.**  Keep PH 6 and JST's 24 AWG leads, which were just decided.
  **Go for rev B**, with hub probing, a switched OUT on each node and the pinout below.  Possibly add
  10BASE-T1S on the CAN pair (section 5).

## 1. Pinout (straight cord, T568A or B: the pairs are the same)

| Pin | Draft | Kept? | Why |
|---|---|---|---|
| 1, 2 (a pair) | VRACK | yes | two conductors share 1.6 A: 0.8 A each |
| 3, 6 (a pair) | GND | yes | VRACK's return, the PoE "mode A" layout |
| 4, 5 (the centre pair) | CAN_H, CAN_L | yes | a twisted pair in every cord and in both wiring standards |
| 7 | POS (POS_OUT on the OUT jack, POS_IN on the IN jack) | yes | the same pin on both jacks, so a straight cord carries the token |
| 8 | GND | yes | a third return, 0.53 A each with 3 and 6.  Paired with POS: a NIC's winding shorts 7 to 8, a free misplug test (section 4) |

The draft holds.  Notes:
- Buy 4-pair cords.  A 2-pair cord (pins 1, 2, 3, 6 only) powers the row but carries no CAN or POS.
  The nodes then come up unaddressed: visible, and harmless.
- A crossover cord swaps VRACK and GND.  The node's reverse-polarity P-FET and the BAT54S clamps
  take that, and the row stays dark.
- OUT↔OUT or IN↔IN cords are harmless.  POS outputs drive each other through 10k, and each eFuse
  blocks reverse current.

## 2. Connector

No 8P8C without magnetics is a JLC basic part.  The candidates (sizes from JLC's part pages):

| LCSC | Part | Mount | L × W × H (mm) | Price | Stock |
|---|---|---|---|---|---|
| **C7205199** | RJ-064-1 | SMD, right angle, shielded | 15.3 × 14.7 × 10.75 | $0.34 | 13 636 |
| C3000212 | HCTL HC-RJ45-055-6 | SMD, recessed (sits in a board cut-out), unshielded | 13.8 × 12.8 × 11.3 (body) | $0.19 | 13 816 |
| C3097717 | 5301-8P8C | THT, right angle | 18.1 × 15.2 × 11.45 | $0.115 | 3 159 |
| C385834 | R-RJ45R08P-A004 | THT, right angle | 15.9 × 15.1 × 12.6 | $0.23 | 118 747 |

- **Contacts:** ≈ 1.5 A per contact is the usual IEC 60603-7 rating; these generic parts don't
  state it, so check the drawing.  The row's 0.8 A (VRACK) and 0.53 A (GND) leave margin.  For
  comparison, a PH 6 contact runs at 1.6 A, 80 % of its 2 A.
- **Pick:** C7205199.  It is SMD, so JLC places it, and at 10.75 mm it fits both the node (14 mm under
  the drawer) and the hub (12 mm under the box lid).
- **Node:** J1/J2 sit on the left and right edges at KiCad y 73.  A jack is 14.7 mm along the edge and
  15.3 mm deep, where a PH 6 is 17.2 × 10.2.  It takes 5 mm more of the board at each edge, beside the
  input protection (Q1, D1) on the left and J5 / J7 on the right.  ≈ 1 day of re-placement, re-route
  and checks, plus the switched OUT (section 4).
- **Hub B1:** four jacks at 17.5 mm pitch down the left edge fit (14.7 mm each).  The re-placement and
  the probe circuit take ≈ 1 day.
- **Mechanics** ([their study](rj45-row-cable-mechanical.md)): the RJ-064-1 fits, tab down.
  - Today's tray and ladder windows (26 × 13.1 and 26 × 20) already pass the plug, with 0.7–1.9 mm to
    spare; the cord runs straight between the boots.  Only the power box's left wall needs new
    13 × 11.5 cut-outs.
  - J1/J2 stay at KiCad y 73: the front-left corner is ruled out (the M3 hole at (3.5, 86.5), and D4).
  - **The cost is the drawer's stroke: 128 mm instead of 140**, so the chain foot clears the cord.

## 3. Current and cable

VRACK runs on 2 conductors and GND on 3.  Contacts are 20 mΩ each (two mated connectors per cord).

| At 1.6 A | 24 AWG | 26 AWG | 28 AWG (slim) |
|---|---|---|---|
| Loop resistance | 70 mΩ/m | 112 mΩ/m | 177 mΩ/m |
| Drop, 0.15 m cord | 70 mV | 80 mV | 96 mV |
| Drop, 0.5 m | 109 mV | 143 mV | 195 mV |
| Drop, 1 m | 166 mV | 232 mV | 337 mV |
| Heat in the cord | 0.18 W/m | 0.29 W/m | 0.45 W/m |

The nodes run from 13.5 V, so the drop is irrelevant.  The heating is a few degrees in a single cord.
At 0.8 A a conductor this runs above PoE++'s ≈ 0.5 A, but the rack has short, single, unbundled cords.

**Cable spec:**
- **Type:** Cat5e or Cat6 patch cord, U/UTP, 4 pairs, wired straight.
- **Copper:** stranded pure copper ("CU", "BC").  Never CCA (copper-clad aluminium): ≈ 1.6× the
  resistance and brittle.  On arrival, a magnet test or a scratch shows silver.
- **Gauge:** 24 or 26 AWG.  28 AWG slim cords are fine for the ≤ 0.25 m jumpers, and they route more
  easily.
- **Lengths ([Mechanics](rj45-row-cable-mechanical.md)):** 12 cm jumpers, made to length: a 0.15 m cord's slack has nowhere to go,
  and stock 0.1 m cords are likely too short for the 92 mm between the mouths.  So the jumpers need
  RJ45 plugs crimped on (a crimper and plugs, ≈ €20), or a cord maker's custom length.  The feeds are
  0.25 / 0.5 / 0.75 / 0.75 m for rows A–D, stock lengths (≈ €1.5–3 each from EU shops that state pure
  copper).

## 4. CAN, and misplug safety

**CAN:**
- The topology stays as today: a star from the hub, a daisy chain through each row, both
  terminations in the hub.
- The node's IN-to-OUT pass-through is the same 74 mm pair across the board, and the transceiver's
  stub stays ≤ 20 mm.
- Cat5e is 100 Ω against CAN's 120 Ω: no issue at a few metres.
- The PESD2CAN stays on the node, and the hub keeps its own.

**Misplug.**  A laptop's or switch's port has its pairs' centre taps tied by 75 Ω resistors to a
common point (Bob Smith).  VRACK on pair 1-2 and GND on pair 3-6 see 150 Ω through them: 133 mA at
20 V, 187 mA at 28 V.  That is 1.3–2.6 W in a 1/16–1/10 W resistor, far below the eFuse's 1.6 A, so
nothing trips.  Protection levels:

| Level | What | Parts | Firmware | Covers |
|---|---|---|---|---|
| 0 | labels on every jack ("RACK BUS · 28 V · NOT ETHERNET"), coloured cords, dust caps on free OUT jacks | ≈ €2 | — | people who read |
| 1 | **hub probe before each row's eFuse turns on** (below) | per row: an AO3401A, a 2N7002, 2.2 kΩ and a divider, ≈ $0.04; a GPIO each (the MINI-1 has spares) | ≈ 1–2 days | the hub's jacks, and anything plugged in before the row is on |
| 1b | the last node watches its free OUT jack: a NIC's winding shorts POS_OUT (pin 7) to GND (pin 8), its read-back drops, and it asks the hub over CAN to cut the row | none | ≈ 1 day | a NIC plugged into a live row, after ≈ 10–50 ms of 1.3–2.6 W: the NIC's resistor probably survives, not guaranteed |
| 2 | **a switched, probed VRACK pass-through on every node**: a P-FET on OUT's VRACK, the same probe as the hub's, closed only for a node | per node ≈ $0.15 (P-FET rated 2 A, 12 V gate clamp, probe FET, divider); two GPIOs or an expander pin | ≈ 2 days | every jack, all the time |

The probe, with no change at the node's input:
1. The hub feeds 5 V through 2.2 kΩ (2.3 mA at most) behind the off eFuse, and times the row's voltage
   against a threshold.
   - A node row is ≥ 100 µF (C1, through the P-FET's body diode) in parallel with ≥ 27 kΩ (the bucks'
     EN dividers): a rise of 0.2–1 s up to ≥ 4.6 V.
   - A NIC sits at ≈ 0.3 V and a short at 0 V.  An open jack rises within tens of ms (only the hub's
     own output capacitor and ON LED).
2. The hub also reads POS back through its pull-up.  A NIC's winding shorts it to pin 8 (GND); a node
   reads high through its 470k pull-down.
3. The eFuse turns on only for "slow rise, high end, POS high".

PoE-style signature resistors don't work here: the node's bulk capacitor is on its input.  Level 2 is
what makes RJ45 safe in a lab full of laptops.

## 5. Future: 10BASE-T1S

- 10BASE-T1S is 10 Mbit/s on one pair, multidrop.  A segment needs a bus with 100 Ω at both ends
  (≤ 25 m, short stubs), not a star.
- **On RJ45 it can replace CAN on pair 4-5.**  Each row is then its own segment: one PHY per row at the
  hub (4 × LAN867x class, ≈ $2–3 each), a 100 Ω end on the row's last node, switched by firmware.
  POS stays on pin 7.
- **Keeping CAN and adding T1S** would take pair 7-8: POS and the third GND go, and position would
  need another mechanism.  Not recommended.
- The S31 study (local_a06aa80a) owns the MAC and PHY side.

## 6. BOM delta per rack (12 nodes, 1 hub)

| | PH 6 today | RJ45 (level 2) |
|---|---|---|
| Jacks (24 on the nodes, 4 on the hub) | 28 × S6B-PH-SM4-TB, ≈ $9 | 28 × C7205199, ≈ $9.5 |
| Part types | — | +1 on the node (PH 6 stays for AUX): +$1.53 an order (Standard PCBA) |
| Protection | — | hub ≈ $0.2, nodes ≈ $1.8 |
| Cables (9 jumpers, 3 feeds) | JST leads, housings, crimped long feeds, the crimper: ≈ €45 | 3 stock feeds and 9 jumpers made to length (12 cm): ≈ €25–35 with an RJ45 crimper |
| Assembly | 72 leads clicked in, 12 contacts crimped | none |
| **Net** | | ≈ −€10 to −€20 a rack; the 72 leads aren't clicked in, but 9 jumpers get crimped plugs |

**Schedule:** about 1–2 weeks before the rev A order.
- Node: J1/J2 and the switched OUT, ≈ 2 days.
- Hub: jacks and the probe, ≈ 1–2 days.
- Firmware: the probes and 1b, ≈ 3 days.
- Mechanics: the power box's cut-outs, and the drawer's stroke and chain at 128 mm (their estimate).
- Then the reviews and the CPL audit.

## 7. Go / no-go

**No-go for rev A.**  The gain is convenience (stock feed cords, latching plugs) and ≈ €10–20 a rack;
the 12 cm jumpers still have to be made to length.  The cost:
- a node and hub redesign;
- a mechanical round, and 12 mm of drawer stroke (128 mm instead of 140);
- a live-jack hazard that labels alone don't remove.

PH 6 with JST's 24 AWG leads meets the electrical need today.

**Go for rev B,** as one change:
- the RJ45 pinout above;
- the C7205199 jack;
- hub probing (level 1);
- a switched, probed pass-through on each node (level 2);
- possibly 10BASE-T1S on pair 4-5.
