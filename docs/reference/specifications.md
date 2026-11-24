# Specifications

This page gives the sizes, voltages, currents and capacities of a BitBunk rack.

You choose how many rows and columns your rack has. The overall size below is for the example rack of four
columns and three rows. [Choose your rack's size](../plan/choose-your-rack.md) gives other sizes.

## Size

| | Value |
|---|---|
| Example rack, 4 columns × 3 rows | 671 × 225 × 619 mm, width × depth × height |
| Each column you add | 165.8 mm wider |
| Height of a row | 165 mm, or 120 mm for a row of slot bins |
| Height of the base, under the rows | 80 mm |
| Tilt of the shelves | 20°, front edge lower |
| How far a drawer slides out | 140 mm |

[Parts to print](../print/parts-list.md) lists the printed parts and their masses for your size.

A rack that stands free tips forwards under a pull of 8 to 13 N on an open drawer of the top row.
[Screw the rack to the bench](../build/screw-the-rack-to-the-bench.md).

## Chargers and what each feeds

<!-- site:charger-table -->
| Charger | Cable | What the rows get |
|---|---|---|
| The default: a single-port USB PD charger, 100 W (20 V × 5 A) | USB-C to USB-C, 5 A e-marked (rated 100 W or 240 W), 1 to 2 m | 20 V; 4.5 A, 90 W |
| The same charger on a 3 A cable | a cable with no e-marker: a charger offers more than 3 A only through an e-marked 5 A cable | 20 V; 2.7 A, 54 W |
| A single-port 65 W charger (20 V × 3.25 A) | 5 A e-marked | 20 V; 2.9 A, 58 W: for a light rack. The hub sheds rows that ask for more |
| A single-port USB PD 3.1 EPR charger, 140 W (28 V × 5 A) | rated 240 W | the same as the default: the hub does not use 28 V |
| A multi-port charger | | avoid it: it can lower its offer when another device is plugged in, and the rack restarts or loses rows |
| A charger that offers no more than 12 V | | nothing: the rows need a contract of 15 V or more |

What the rows get is the charger's contract less the 10 % the hub keeps free.
<!-- /site:charger-table -->

The bill of materials names the Anker Nano 100 W (A2679) as an example of the default charger.
[Power budget and queued ports](../use/power-budget.md) explains how the hub shares the power.

## Voltages

<!-- site:voltages -->
| Where | Value |
|---|---|
| VRACK, on every row cable | 20 V: the charger's own output |
| At plug-in, and on a hub with no firmware | 9 V, every row off |
| When a row switches on | once a contract of 15 V or more has held for 500 ms. The rows follow each other 300 ms apart |
| What the hub asks the charger for | 20 V. 28 V (EPR) is off in the hub's firmware |
| A row's eFuse and a DATA lead's eFuse | cut out under 15 V and above 31 to 34 V |
| A bay node | runs from 13.5 to 30 V: it starts above 13.5 V and stops below 10.8 V |
| The DATA lead's supply wire | VRACK, switched by the node: 20 V, not 5 V |
| A node's rails | 5.24 V (5.1 to 5.4 V) and 3.3 V (3.2 to 3.4 V) |
| A DATA board's 5 V | 5.08 V (4.94 to 5.22 V) |
| VBUS at a DATA port | 4.94 to 5.08 V on a DATA ×6, 4.82 to 5.22 V on a DATA ×4 |
<!-- /site:voltages -->

Source: the design files of the PCBs, `electronics/<pcb>/design.py`. The
[bench checks](../build/check-the-pcbs/index.md) say where to measure these voltages.

## Current limits

<!-- site:current-limits -->
| Where | Limit |
|---|---|
| One DATA port, 5 V to one board | 0.52 to 0.64 A: count on 0.5 A |
| One DATA lead, a whole bay at VRACK | about 1.76 A (1.67 to 1.85 A): the node's eFuse |
| What the node can measure on that lead | 1.64 A |
| The node's own limits | it sheds a port above 1.5 A on the lead. With no grant from the hub, it keeps the bay under 25 W |
| One row | 1.6 A (1.52 to 1.68 A): the hub's eFuse, about 32 W at 20 V |
| A contact of a row cable | 2 A, on 24 AWG wire |
| The whole rack | the contract's 5 A, of which the hub gives the rows 4.5 A |
| A camera and its light | 0.42 A at 5 V at most, behind a 0.75 A resettable fuse |
| A DATA board with every port at its limit | 1.3 A at 20 V for a DATA ×6, 0.92 A for a DATA ×4 |
<!-- /site:current-limits -->

The hardware cuts off at these limits. In normal use, a bay may draw only its grant from the hub, which the
next section gives. A short on one DATA lead reaches the row's limit first
([Limitations](known-limitations.md#power-and-faults)).

## A bay's share, by number of columns

The more columns your rack has, the less power each bay gets. The hub shares each row's 1.6 A equally
between its bays and keeps 10 % free. From each share it takes off what the node draws itself: 1.8 W, or
4.3 W with a camera. What is left is the bay's {term}`grant`, for its DATA board and its boards.

<!-- site:bay-share -->
| Columns | Each bay's share | For the DATA board and your boards | The same, with a camera |
|---|---|---|---|
| 2 | 14.4 W | 12.6 W | 10.1 W |
| 3 | 9.6 W | 7.8 W | 5.3 W |
| 4, as in the example | 7.2 W | 5.4 W | 2.9 W |
| 5 | 5.8 W | 4.0 W | 1.5 W |

For the default 100 W charger (20 V × 5 A), with one to three rows.

In a 2 × 2 rack, for example, each bay has 12.6 W for its DATA board and your boards. The DATA board takes
2.1 to 3.0 W of it. Your boards get the rest.
<!-- /site:bay-share -->

A DATA ×6 takes 2.1 to 2.6 W of the grant, and a DATA ×4 2.3 to 3.0 W.

The hub also shares the charger's 90 W between all the bays of the rows that are on. It grants the smaller of
the two shares. With one to three rows, the row's share is the smaller. In two cases the charger's share is
the smaller:

- four rows of four on the 100 W charger: 90 W ÷ 16 bays, less 1.8 W, is 3.8 W a bay;
- twelve bays with the charger on a 3 A cable: 54 W ÷ 12, less 1.8 W, is 2.7 W a bay.

Source: `budget_grant_mw()` in [budget.c](../../firmware/power-hub/src/budget.c).

## USB

| | Value |
|---|---|
| Ports in a bay | 6 USB-C on a DATA ×6, 4 on a DATA ×4 |
| Speed over USB/IP | 12 Mbit/s (full speed), shared by the boards of a bay |
| Speed in classic mode, a laptop on the front port | high speed, 480 Mbit/s |
| Supply at a port | 5 V: count on 0.5 A |

[Limitations](known-limitations.md#usb-over-the-network) lists what does not pass over USB/IP.

## Sessions, clients and flashes at once

<!-- site:capacity -->
| What | How many at once |
|---|---|
| Boards in a bay | 6 with a DATA ×6, 4 with a DATA ×4 |
| USB/IP sessions on one bay node | 6, one per device |
| Boards flashing over USB/IP on one Wi-Fi channel | 8. The rack does not enforce it |
| Clients of a bay's camera | 3, at 5 frames a second at most |
| Events the hub keeps | the last 32, in RAM |
| Rows, and bays in a row, on the rack bus | 4 rows, 15 places in each |
<!-- /site:capacity -->

These are the firmware's defaults. [Wi-Fi for the rack](../use/wifi.md) explains the limit of eight flashes.
[Network ports and metrics](network.md) gives the connections each network port takes.

## Logic levels on the DATA ×4 pins

| | Value |
|---|---|
| P1 to P8 of a port | the board's own logic level, 0.95 to 3.6 V, set by the port's VREF pin |
| VREF | the board's I/O supply, 1.8 or 3.3 V. A 5 V board with TTL inputs gives its own 3.3 V pin |
| In series with each pin | 100 Ω |
| The buses A to H inside the DATA ×4, and its analyzer | 3.3 V, each bus pulled up by 10 kΩ |
| RESET and BOOT of a port | open drain through 1 kΩ, against the board's own pull-up of 4.7 kΩ or more |
| A 5 V board with strict CMOS inputs | not guaranteed |
| AUX, on the node's J5 | 3.3 V through 1 kΩ, with no level shifting and no ESD protection |

A DATA ×6 has no pins. [Wires between boards](../use/wires.md) explains what passes through the pin
matrix.

## The largest rack

Your rack can be as large as you like, within these limits.

| Limit | Value |
|---|---|
| Rows | 4: the hub has four row outputs, A to D |
| Bays in a row | 15 places on the rack bus. Power limits you first: at five columns a bay gets 4.0 W, and its DATA board takes 2.1 to 3.0 W of it |
| Height of a row | 165 mm, so that the row's ladder fits a 256 mm print bed |
| Width of a bay | 158 mm, one size |
| Charger | 100 W: a larger one gives no more power at 20 V |
