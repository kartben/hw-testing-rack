# Cables and pinouts

Every lead between two PCBs of the rack is a JST PH lead wired "Same direction" (some sellers say "same side",
同向): pin n at one end meets pin N + 1 − n at the other (7 − n on six pins, 9 − n on eight), and both plugs
show the same face when the lead lies flat on a table. A 1:1 lead, which sellers often call "reverse", fits the same sockets and works in none
of them.

:::{status} designed
The pinouts are those of the routed v1.0 PCBs, as the design review of 2026-11-09 read them pad by pad. The
lengths come from the 3D model. No cable has been made or plugged yet.
[What exists today](../plan/status.md).
:::

| Cable | Connector | Between | Length |
|---|---|---|---|
| [Row cable](#row-cable-jumpers-and-feeds), jumper | JST PH 6, on 24 AWG | a node's J2 (ROW OUT) and the next node's J1 (ROW IN) | 152 mm leads, 120 mm routed |
| Row cable, feed | the same | a row output of the hub and the J1 of the row's first node | 305 mm, 60 cm and 80 cm leads for rows A, B and C |
| [DATA lead](#data-lead) | JST PH 8 | the node's J7 and the DATA board's J1 | 50 cm, ≈ 38 cm routed |
| [Camera lead](#camera-lead) | JST PH 8, the same lead | the node's J6 and the camera pod's J1 | 50 cm, ≈ 45 cm routed |
| [The cable to your board](#the-cable-to-your-board) | USB-C, and what the board takes | a DATA port and the board | 15 to 25 cm |
| [AUX lead](#aux-lead) | JST PH 6 | the node's J5 and the board's pins | in no source |
| [Jumper wires](#jumper-wires-on-a-data-4) | Dupont, female to female | a DATA ×4's pin header and the board's pins | 20 cm, 30 cm where that does not reach |
| [Charger cable](#charger-cable) | USB-C to USB-C, 5 A e-marked | the charger and the power box's PD IN | 1 to 2 m |

Three rules drove the design: no loose cable spans between bays, a board stays connected while you work on
it, and each cable is as short as it can be without ever being taut.

## Row cable, jumpers and feeds

```{figure} ../img/notice/hw_jumper.svg
:class: bb-lineart
:alt: Line drawing of a six-wire lead, a plug at each end, both plugs the same face up
:width: 260px

A row cable lies flat, each wire on its own side, both plugs the same face up.
```

JST PH, 2.0 mm pitch, 6 pins. The socket is the side-entry S6B-PH-SM4-TB: J1 (ROW IN) on a node's left edge,
J2 (ROW OUT) on its right edge, and the hub's four row outputs (J2 to J5, rows A to D) on its left edge, behind
the windows of the power box's left wall.

Every output has the input's pinout mirrored: a node's J2 and the hub's row outputs carry, on pin n, the net of
J1's pin 7 − n. Every link runs from an output to an input, so every row cable is the same, jumper or feed.

```{include} ../can.md
:start-after: <!-- site:row-pinout -->
:end-before: <!-- /site:row-pinout -->
```

The table is included from [Rack bus on CAN](../can.md), which also holds the bus and the addressing. VRACK is
the charger's voltage itself: 20 V today ([Specifications](specifications.md#voltages)).

<!-- site:row-cable-lengths -->
| Cable | Its six leads | Routed |
|---|---|---|
| Jumper, node to node | 152 mm, pre-crimped (ASPHSPH24K152) | 120 mm |
| Feed to row A | 305 mm, pre-crimped (ASPHSPH24K305) | ≈ 0.25 m |
| Feed to row B | 60 cm, crimped by hand | ≈ 0.45 m |
| Feed to row C | 80 cm, crimped by hand | ≈ 0.6 m |
| Feed to row D | no measured length: `tools/bom.py` counts row C's 80 cm | |
<!-- /site:row-cable-lengths -->

Read from [tools/bom.py](../../tools/bom.py) (`ROW_JUMPER_MM`, `ROW_FEED_CM`); the routed lengths are the 3D
model's.

Each cable is six single leads of UL1007 24 AWG in two housings, a red PHR-6-R at the IN end (a node's J1) and
a black PHR-6-BK at the OUT end (a node's J2 or a hub output). The cable works either way round: the colours
only make it readable. The cables are made by hand because JST rates the PH contact's 2 A on 24 AWG only, and
no ready-made 6-pin cable states 24 AWG with this wiring
([the decision of 2026-10-21](../power-distribution-review.md#decision-real-awg-24-leads)).

A rack of c columns and r rows takes r × (c − 1) jumpers and r feeds: nine and three for the default 4 × 3.
A row needs no plug at its end. Both terminations of the bus are in the hub, and the last node's J2 stays
empty; it is live all the same ([What a wrong cable does](#what-a-wrong-cable-does)). A row output with no row
behind it, row D on the default rack, stays empty too.

```{bom-table}
:category: Cables
:match: row cable|crimp contact|crimped feeds
:columns: item, qty, source
```

[Make the row cables](../build/row-cables.md) builds and tests them. The jumper's route is on
[Add a bay, then a row](../build/add-a-bay.md), the feeds' on
[Power box and charger](../build/power-box.md#now-the-row-feeds).

## DATA lead

A ready-made JST PH 8 lead, 50 cm, "Same direction". It runs from the node's J7 (DATA, side entry on the node's
right edge) through the drag chain to J1 on the rear face of the drawer's DATA board, a DATA ×6 or a DATA ×4.

<!-- site:data-lead-pinout -->
| Node J7 | Signal | DATA board J1 |
|---|---|---|
| 1 | DATA_VIN: VRACK through the node's eFuse, 20 V (28 V with an EPR contract), ≈ 1.76 A | 8 |
| 2 | GND | 7 |
| 3 | D+ | 6 |
| 4 | D− | 5 |
| 5 | GND | 4 |
| 6 | SDA | 3 |
| 7 | SCL | 2 |
| 8 | GND | 1, not connected on the DATA board |
<!-- /site:data-lead-pinout -->

Read from J7 in [the node's design.py](../../electronics/bay-node/design.py) and J1 in
[the DATA ×6's](../../electronics/data-port-x6/design.py) and
[the DATA ×4's](../../electronics/data-port-x4/design.py); the
[review of 2026-11-09](../pcb-review-2026-11-09.md) found the same on the routed PCBs.

Pin 1 is not 5 V. It carries the row's voltage, switched by the node and off until its firmware turns it on,
and the DATA board makes its own 5 V from it. The USB pair is on pins 3 and 4 at the node: twist those two
wires by hand. The I²C pair is the node's own bus ([I²C addresses](#i2c-addresses-on-the-data-lead)).

The route is ≈ 38 cm, plugs included, and does not change over the drawer's stroke. Buy the 50 cm length: the
spare goes in a wider bend between the node and the chain's fixed end, where nothing moves, never in front of
the chain's moving end. A sled bay has no chain: its route is ≈ 22 cm and the slack is coiled in the plenum.
[Fit out a tray](../build/fit-out-a-tray.md) lays the lead in.

The lead has eight pins so that a 6-pin row cable does not go into J7; whether a 6-pin plug enters an 8-pin
socket has not been tried (item R9 of the [schematic review](../schematic-review-2026-10-25.md)). The listing
states no wire gauge, and JST gives the PH contact's 2 A on 24 AWG only: measure a conductor when the leads
arrive (24 AWG ≈ 0.51 mm, 26 AWG ≈ 0.40 mm; item R8 of the same review, still open).

```{bom-table}
:category: Cables
:match: 8-pin lead
:columns: item, qty
```

The bill's listing is [AliExpress 1005008045292937](https://www.aliexpress.com/item/1005008045292937.html),
options "Same direction", 8P, Length50CM. Its price was interpolated from the 6-pin lots, not read.

## Camera lead

The same 50 cm lead, ≈ 45 cm routed between the plugs: from the node's J6 (CAM, vertical, at the node's rear
right) to J1 on the camera pod's PCB.

<!-- site:camera-lead-pinout -->
| Node J6 | Signal | Pod J1 |
|---|---|---|
| 1 | GND | 8 |
| 2 | SCK | 7 |
| 3 | CAM_5V: the node's 5 V through a 0.75 A resettable fuse | 6 |
| 4 | MOSI | 5 |
| 5 | MISO | 4 |
| 6 | LED_K: the cathode side of the pod's four LEDs, switched by the node | 3 |
| 7 | CS | 2 |
| 8 | GND | 1 |
<!-- /site:camera-lead-pinout -->

Read from J6 in [the node's design.py](../../electronics/bay-node/design.py) and J1 in
[the pod's](../../electronics/camera-pod/design.py); the review of 2026-11-09 found the same on the routed
PCBs.

From the pod's PCB to the camera runs a 6-pin cable, JST XH 2.54 at the camera and Dupont sockets at the pod's
J2 (the Arducam Mega's own cable does if it ends in Dupont sockets). J2's pins are named on the PCB (VCC, GND,
SCK, MISO, MOSI, CS): the wires go on by name. [Add a camera](../build/camera.md) routes both.

```{bom-table}
:category: Cameras
:match: XH 2.54
:columns: item, qty, source
```

## The cable to your board

A short USB cable that belongs to the board. At the drawer it is USB-C, a straight plug standing in one of the
port wall's slots (an angled one only if its cable leaves upwards); at the board it is whatever the board takes:
USB-C, micro-B or mini-B; 15 to 25 cm long.

Pick cables that state data (USB 2.0, 480 Mbps): many short ones are charge-only. A micro-B or mini-B port that
faces the port wall takes a 90° adapter, male to female, with the cable's straight plug standing on it. A
right-angle micro-B plug is not reversible and sellers name "up" and "down" either way: the adapters come in
sets, keep the one whose female faces up.

Which cable a board takes, and how it lies on the plate, is on
[Put a board in a bay](../use/mount-a-board.md). The bill counts the cables of the example rack's boards; yours
need their own:

```{bom-table}
:category: Cables
:match: DUT cable|Micro-B 90
:columns: item, qty, source
```

## AUX lead

The node's J5: JST PH 6, side entry, on the node's right edge between ROW OUT and DATA. It carries a UART and
the RESET and BOOT lines, for a board with no USB serial port of its own.

<!-- site:aux-pinout -->
| J5 | Signal | |
|---|---|---|
| 1 | GND | |
| 2 | 3V3 | through 1 kΩ: a reference for the board's levels, not a supply |
| 3 | TX | the node's output, through 1 kΩ |
| 4 | RX | the node's input, through 1 kΩ |
| 5 | RESET | open drain: the node pulls it low |
| 6 | BOOT | open drain |
<!-- /site:aux-pinout -->

Read from J5 in [the node's design.py](../../electronics/bay-node/design.py).

The levels are 3.3 V, and J5 has no ESD or level protection (finding S5 of the
[schematic review](../schematic-review-2026-10-25.md)). The bill holds no AUX lead and no source gives it a
length. The design routes a 6-wire PH lead through the drag chain beside the DATA lead, ending in flying leads
at the board; no source checks that both leads fit the chain's 7 × 7 mm channel
([Serial console](../use/serial-console.md)).

:::{warning}
J5 takes the same plug as ROW OUT (J2), 22 mm away on the same edge of the node. On the last node of a row J2
is empty and live: its pin 6 is VRACK. An AUX lead pushed into J2 puts 20 V on its BOOT wire, and into your
board. Nothing but a row cable goes into ROW OUT.
:::

## Jumper wires on a DATA ×4

Female to female Dupont wires, 20 cm (30 cm where that does not reach), torn off a 40-wire strip as a small
ribbon. They join a port's 2 × 6 pin header on the DATA ×4 (GND, VREF, P1 to P8, RESET, BOOT; the names are on
the silkscreen) to the board's own pins. No GND wire: the USB cable carries it. On the base assembly (DATA-4x)
only GND, RESET and BOOT are connected.

The viewer uses one colour code: GND black, VREF red, RESET brown, BOOT green (the bill names the same colours
for GND, RESET and BOOT).
[Wires between boards](../use/wires.md) says which wire a board needs and what VREF must be.

```{bom-table}
:category: Cables
:match: Dupont
:columns: item, qty, source
```

## Charger cable

USB-C to USB-C, 5 A, e-marked (rated 100 W or 240 W), 1 to 2 m, from the charger to PD IN on the power box's
rear wall. The e-marker is required: above 3 A a charger only offers its full current through an e-marked 5 A
cable, and a 3 A one gives 60 W. A cable shipped with the charger and rated 100 W or more is one. The chargers
are on [Specifications](specifications.md#chargers-and-what-each-feeds).

(i2c-addresses-on-the-data-lead)=
## I²C addresses on the DATA lead

Pins 6 and 7 of the DATA lead carry the node's own I²C bus to the DATA board.

<!-- site:i2c-addresses -->
| PCB | Chips | Addresses |
|---|---|---|
| Bay node | the INA226 that meters the DATA lead | 0x40 |
| DATA ×6 | a TCA9535 port expander, six INA226 | 0x20; 0x41, 0x43, 0x44, 0x45, 0x47, 0x4C |
| DATA ×4 | two TCA6408A, a TCA9534A (DATA-4x-logic only), four INA226 | 0x20, 0x21; 0x38; 0x41, 0x43, 0x44, 0x45 |
<!-- /site:i2c-addresses -->

From the [review of 2026-11-09](../pcb-review-2026-11-09.md) and the notes of each PCB's `design.py`.

No two collide: a bay takes one DATA board at a time, and neither uses the node's 0x40. One address tells the
node which board it has: a DATA ×4 answers at 0x21, a DATA ×6 at 0x4C.

## What a wrong cable does

Worked out from the schematics and the firmware's own messages. None of these has been tried.

<!-- site:wrong-cable -->
| The mistake | What happens | Harm |
|---|---|---|
| A 1:1 lead used as a row cable | VRACK lands on the POS pins, behind 10 kΩ and a clamp (≈ 2.5 mA at 28 V); CAN_H and CAN_L swap. The next node stays off, and the bays after it | none |
| A row cable with CAN_H and CAN_L swapped or open | every node after it is missing from the hub's list | none |
| A row cable wired with VRACK on a CAN wire | the PESD2CAN of every tap conducts and fails short: the bus stops until they are replaced | the PESD2CAN of the hub and of every node; the transceivers survive |
| A 1:1 lead used as a DATA lead | the node keeps the lead off and says `SCL or SDA held low: DATA lead reversed?` | none |
| A camera lead in J7 (DATA) | J7's pin 1 lands on a GND pin of the pod. The eFuse limits, the node switches off and says `no DATA_VIN after switching on: a short on the lead (a camera lead in J7?)` | none; the camera does not work there |
| A DATA lead in J6 (CAM) | both end pins of J6 are GND: the DATA board gets no supply | none |
| A 1:1 lead used as a camera lead | CAM_5V lands on the cathodes of the pod's LEDs, not on a camera line | none, by the choice of the pinout |
| An AUX lead in ROW OUT (J2) | its BOOT wire carries VRACK | the board at the end of the lead |
| A row cable in AUX (J5) | the row's eFuse trips | not assessed |
| A 3 A cable on the charger | the charger offers 3 A: 60 W, of which the hub gives the rows 54 W | none |
| A charge-only USB cable to a board | the board is powered and never shows up on USB | none |
<!-- /site:wrong-cable -->

The row cable's cases are reasoned in [Rack bus on CAN](../can.md#row-cable), the AUX lead's in finding S3 of
the [schematic review](../schematic-review-2026-10-25.md). The node's messages are those of
[dut.c](../../firmware/bay-node/src/dut.c).
