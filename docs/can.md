# Rack bus (CAN)

> **Status: decided.**  The power hub v0.5 (USB-C PD in, rack controller, CAN master) is
> laid out and routed (`electronics/power-hub`); so is the bay node v0.5 (`electronics/bay-node`:
> 6-pin J1/J2, TJA1462AT + PESD2CAN on the pair, POS in and out).  Both firmwares speak the
> rack bus ([rack-protocol.md](rack-protocol.md)): the hub as the master
> (`firmware/power-hub`), each node as a client (`firmware/bay-node/src/rack.c`); tested on a
> simulated rack, not yet on hardware.

The row power cables (VRACK: 20 or 28 V, [power.md](power.md)) also carry a CAN bus and an addressing line, so the rack
controller in the power box can find every node and tell it where it sits, without Wi-Fi
or configuration.  It can also power-cycle a hung row and read row currents
(the hub's eFuse `SHDN` / `FLT` / `IMON`).  Rows are off until the controller
turns them on, once the PD contract is final.

## Row cable

JST PH 2.0 mm, **6 pins**, side entry: **S6B-PH-SM4-TB**, the part the node
already uses for AUX.  On the node, J1 (IN) is on the left edge and J2 (OUT)
on the right edge: the same footprint turned 180°, so J1's pin 1 is towards
the rear and J2's towards the front.  The hub's row outputs A–D are on its
left edge (pin 1 towards the rear), in the power box's left wall.

**Every output has the input's pinout mirrored**: a node's J2 and the hub's
row outputs carry, on pin n, J1's pin (7−n) net.  So every link runs from an
output to an input, and **every row cable is the same**: **pin n ↔ pin 7−n**,
a cable whose two plugs show the **same face** when it lies flat on a table.

* **Jumper, node to node** (J2 facing the next node's J1): it lies flat, each
  wire on its own side, no twist.  Every net also crosses the node straight.
* **Feed, hub to a row's first node**: the same cable, longer.  Both of its
  connectors face left (it loops out of the box, up the rack's side and back
  in), so it takes a half turn somewhere along its 25–60 cm, tied along the
  ladder.  The bundle turns as one: the CAN pair stays together, between its
  GND pins.

Sellers usually call this type **"same direction"** or "same side" (同向),
and the 1:1 one "reverse"; not all of them do, so check that both plugs show
the same face, and that pin 1 rings through to pin 6.  The BOM names a listing
that offers every length (checked 2026-10-18).  A 1:1 cable
(plugs on opposite faces, e.g. Pololu's) burns nothing if used by mistake:
VRACK lands on the POS pins (10k + BAT54S, ≈ 2.5 mA at 28 V), CAN_H and CAN_L
swap, and the next node simply stays off.

| Pin | J1 (IN) | J2 (OUT), hub row outputs | |
|---|---|---|---|
| 1 | VRACK | POS out | VRACK: row power, 20 or 28 V, ≤ 1.6 A (the hub's eFuse; PH contact 2 A) |
| 2 | GND | GND | |
| 3 | CAN_H | CAN_L | the pair runs through every node (J1.3 ↔ J2.4, J1.4 ↔ J2.3), tapped by its transceiver (stub ≤ 20 mm) |
| 4 | CAN_L | CAN_H | |
| 5 | GND | GND | |
| 6 | POS in | VRACK | POS: addressing token, into a node on J1.6, out of it (or of the hub) on pin 1 |

* Bay-to-bay jumpers: 120 mm.
* Feeds from the power box: ≈ 0.25 / 0.45 / 0.6 m for rows A / B / C.  Give
  the CAN pair 2–3 twists per 10 cm on the feeds; the jumpers don't need it.

## Bus

A **star**: the hub's transceiver is the centre and every row port carries the
same CAN_H / CAN_L.  Each row is one branch of ≤ ~1.5 m (feed + three
jumpers); an unused port is left open.  Both terminations (split, 2 × 56 Ω +
10 nF each, 56 Ω in all, JLC basic parts) sit in the hub.  The nodes have none, and no plug is
needed at a row's end.  At these lengths the lines are electrically short: the
round trip on 1.5 m is ≈ 15 ns, against ~50 ns edges and a 4 µs bit at
250 kbit/s (the default; 125 kbit/s as a fallback).

Transceiver, on the hub and on every node: NXP's **TJA1462AT** (LCSC C3234095),
with VCC 5 V and VIO 3.3 V: a CAN FD transceiver with **signal improvement**
(SIC: CiA 601-4, now ISO 11898-2:2024 set C).  Its bus pins take −36 / +40 V; VRACK (28 V)
sits two pins away on the same connector.  It is passive when unpowered, so a row whose
eFuse is off doesn't load the bus.  Each tap gets a PESD2CAN.  TI's TCAN1462V (C7399456,
SIC, bus pins ±58 V) was the first choice; LCSC had none on 2026-10-18 and 19, so both
boards switched (the user, 2026-10-19).  It stays an alternate, with the TCAN1044AV (no SIC,
±58 V): the same SOIC-8 pinout, VIO on pin 5, STB on pin 8.

**Why a star is fine here.**  ISO 11898-2 describes a line terminated at both
ends.  A star is not that: its open branch ends reflect, and the bus rings
after each edge.  What matters is that the ringing has died out by the sample
point (87.5 % of the bit).  A branch here is ≤ 1.5 m, a round trip ≈ 15 ns;
the sample point comes 3.5 µs after the edge at 250 kbit/s.  CiA's CANopen
bit-timing table allows 11 m per stub and 55 m in all at 250 kbit/s; our four
branches (≤ 1.5 m each, ≤ 6 m in all) would even pass its 1 Mbit/s limits
(1.5 m, 7.5 m).

Signal improvement is what makes star and hybrid networks work at CAN FD data
rates (2–5 Mbit/s): after a dominant-to-recessive edge the transmitter keeps
driving the recessive state at ≈ 100 Ω for up to 530 ns, instead of letting go
(≈ 60 kΩ), so the reflections meet a matched end and die out.  At 250 kbit/s it is
margin, and it leaves room for a CAN FD data phase later.  It acts only when
the transmitting node has it: a node fitted with the TCAN1044AV still works,
without that margin.  The termination does not change: 56 Ω at the centre is
within the 50–65 Ω bus load the transceivers are specified for.

Sources: TI TCAN1462-Q1 datasheet (SLLSFF2B, §8.1.1, §6.9 t<sub>SIC_TX_base</sub>,
§9.2); TI white paper SLLA581A, *How Signal Improvement Capability Unlocks the
Real Potential of CAN FD Transceivers* (§2, §3); CiA, *CANopen lower layers*
(bit-timing table); NXP TJA1462 datasheet rev. 3.0.

## Addressing (POS)

POS is a 3.3 V, active-high token.  Each driver and each input has 10 kΩ in series and a clamp
behind it, a BAT54S to GND and 3.3 V on the hub.  A wrong cable (VRACK on a POS pin) then
costs ≈ 3 mA at 28 V instead of a GPIO.
Each input has a 100 kΩ pull-down.

1. From reset, a node holds POS_OUT low until it has an address.
2. The controller raises POS on row *k*.
3. The node that sees POS_IN high and has no address answers with its MAC.
4. The controller assigns its (row, position): node id = row × 16 + position,
   so C3 → 0x23.
5. The node raises POS_OUT, and the next node in the row answers in turn.

A dead node stops the enumeration of the nodes after it in its row.

The messages, their timing and the error cases are the firmware contract in
[rack-protocol.md](rack-protocol.md).
