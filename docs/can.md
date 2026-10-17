# Rack bus (CAN)

> **Status: decided.**  The power hub v0.4 (rack controller, CAN master) is laid out and
> routed (`electronics/power-hub`); the bay node v0.5 (transceiver, POS) is next.  The
> v0.4 nodes in `electronics/bay-node` still have 2-pin 24 V connectors.

The 24 V row cables also carry a CAN bus and an addressing line, so the rack
controller in the power box can find every node and tell it where it sits, without Wi-Fi
or configuration.  It can also power-cycle a hung row and read row currents
(the hub's eFuse `SHDN` / `FLT` / `IMON`).

## Row cable

JST PH 2.0 mm, **6 pins**, side entry: **S6B-PH-SM4-TB**, the part the node
already uses for AUX.  On the node, J1 (IN) is on the left edge and J2 (OUT)
on the right edge.  The hub's row outputs A–D are on its left edge, in the power box's left
wall.  Cables are wired 1:1 (pin n ↔ pin n), 24 AWG.  A connector on a left
edge has its pin 1 towards the rear, one on a right edge towards the front.  So
between neighbouring nodes (J2 facing J1), the 1:1 cable's bundle makes a half
twist, as today's 2-pin jumpers already do.  When buying pre-crimped cables,
check "pin 1 ↔ pin 1": vendors name the "same" and "reverse" types
inconsistently.

| Pin | Net | |
|---|---|---|
| 1 | +24 V | row power, ≤ 1.6 A (the hub's eFuse; PH contact 2 A) |
| 2 | GND | |
| 3 | CAN_H | through every node (J1.3 ↔ J2.3), tapped by its transceiver (stub ≤ 20 mm) |
| 4 | CAN_L | likewise; pins 3 and 4 run side by side |
| 5 | GND | |
| 6 | POS | addressing token: J1.6 → node input, node output → J2.6 |

* Bay-to-bay jumpers: 120 mm.
* Feeds from the power box: ≈ 0.25 / 0.45 / 0.6 m for rows A / B / C.  Give
  the CAN pair 2–3 twists per 10 cm on the feeds; the jumpers don't need it.

## Bus

A **star**: the hub's transceiver is the centre and every row port carries the
same CAN_H / CAN_L.  Each row is one branch of ≤ ~1.5 m (feed + three
jumpers); an unused port is left open.  Both terminations (split, 2 × 56 Ω +
4.7 nF each, 56 Ω in all, JLC basic parts) sit in the hub.  The nodes have none, and no plug is
needed at a row's end.  At these lengths the lines are electrically short: the
round trip on 1.5 m is ≈ 15 ns, against ~50 ns edges and a 4 µs bit at
250 kbit/s (the default; 125 kbit/s as a fallback).

Transceiver, on the hub and on every node: **TCAN1044AV** (LCSC C3234993),
with VCC 5 V and VIO 3.3 V.  Its bus pins take ±58 V, and the 24 V sits two
pins away on the same connector.  It is passive when unpowered, so a row whose
eFuse is off doesn't load the bus.  Each tap gets a PESD2CAN.

## Addressing (POS)

POS is a 3.3 V, active-high token.  Each driver and each input has 10 kΩ in series and a clamp
behind it, a BAT54S to GND and 3.3 V on the hub.  A cable plugged in reversed (+24 V on pin 6) then
costs ≈ 2 mA instead of a GPIO.
Each input has a 100 kΩ pull-down.

1. From reset, a node holds POS_OUT low until it has an address.
2. The controller raises POS on row *k*.
3. The node that sees POS_IN high and has no address answers with its MAC.
4. The controller assigns its (row, position): node id = row × 16 + position,
   so C3 → 0x23.
5. The node raises POS_OUT, and the next node in the row answers in turn.

A dead node stops the enumeration of the nodes after it in its row.
