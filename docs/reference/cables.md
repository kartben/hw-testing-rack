# Cables and pinouts

This page lists every cable in a rack, with its pinout and its length.

| Cable | Connector | Between | Length |
|---|---|---|---|
| [Row cable](#row-cable-jumpers-and-feeds), jumper | JST PH 6 | a node's J2 (ROW OUT) and the next node's J1 (ROW IN) | 152 mm |
| [Row cable](#row-cable-jumpers-and-feeds), feed | JST PH 6 | a row output of the hub and the J1 of the row's first node | 305 mm to 80 cm |
| [DATA lead](#data-lead) | JST PH 8 | the node's J7 and the DATA board's J1 | 50 cm |
| [Camera lead](#camera-lead) | JST PH 8 | the node's J6 and the camera pod's J1 | 50 cm |
| [The cable to your board](#the-cable-to-your-board) | USB-C, and what the board takes | a DATA port and the board | 15 to 25 cm |
| [AUX lead](#aux-lead) | JST PH 6 | the node's J5 and the board's pins | as you need |
| [Jumper wires](#jumper-wires-on-a-data-4) | Dupont, female to female | a DATA ×4's pin header and the board's pins | 20 or 30 cm |
| [Charger cable](#charger-cable) | USB-C to USB-C, 5 A, e-marked | the charger and the power box's PD IN | 1 to 2 m |

## Same-direction leads

Every lead between two PCBs of the rack is a JST PH lead wired "Same direction". Some sellers say "same
side" (同向). On a 6-pin lead, pin n at one end meets pin 7 − n at the other. On an 8-pin lead, it meets
pin 9 − n. Laid flat on a table, both plugs show the same face.

A 1:1 lead, which sellers often call "reverse", fits the same sockets but works in none of them.

## Row cable: jumpers and feeds

```{figure} ../img/notice/hw_jumper.svg
:class: bb-lineart
:alt: Line drawing of a six-wire lead, a plug at each end, both plugs the same face up
:width: 260px

Laid straight, a row cable shows both plugs the same face up. Heat-shrink bands hold its six leads in a
round bundle.
```

A row cable carries the row's power and the rack bus. It is a 6-pin JST PH lead, 2.0 mm pitch. It runs
from an output (a node's ROW OUT or a row output of the hub) to the next node's ROW IN. A jumper joins two
nodes of a row. A feed joins the hub to the first node of a row. The outputs carry the input's pinout
mirrored, so jumpers and feeds are wired the same way.

```{include} ../can.md
:start-after: <!-- site:row-pinout -->
:end-before: <!-- /site:row-pinout -->
```

VRACK is the charger's voltage: 20 V by default ([Specifications](specifications.md#voltages)).

<!-- site:row-cable-lengths -->
| Cable | Its six leads | Routed |
|---|---|---|
| Jumper, node to node | 152 mm, pre-crimped (ASPHSPH24K152) | 120 mm |
| Feed to row A | 305 mm, pre-crimped (ASPHSPH24K305) | ≈ 0.25 m |
| Feed to row B | 60 cm, crimped by hand | ≈ 0.45 m |
| Feed to row C | 80 cm, crimped by hand | ≈ 0.6 m |
| Feed to row D | 80 cm, crimped by hand | |
<!-- /site:row-cable-lengths -->

Lead lengths from [tools/bom.py](../../tools/bom.py). Routed lengths measured on the 3D model.

Each cable is six single UL1007 24 AWG leads in two housings. The red PHR-6-R goes at the IN end (a node's
J1). The black PHR-6-BK goes at the OUT end (a node's J2 or a hub output). The cable works either way round:
the colours only make it easier to follow.

How many you need depends on the size of your rack. A rack of c columns and r rows takes r × (c − 1)
jumpers and r feeds. A row needs no plug at its end, because both terminations of the bus are in the hub.
The J2 of the last node stays empty, and it is live. A hub output with no row behind it stays empty too.

[Make the row cables](../build/row-cables.md) lists the parts and shows how to make the cables. You fit the
jumpers in [Add a column or a row](../build/add-a-bay.md) and the feeds in
[Power box and charger](../build/power-box.md#connect-the-row-feeds).

## DATA lead

The DATA lead is a ready-made JST PH 8 lead, 50 cm, "Same direction". It runs from J7 (DATA) on the right
edge of the node, through the drag chain, to J1 on the rear face of the DATA board in the drawer.

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

From the `design.py` of the [bay node](../../electronics/bay-node/design.py), the
[DATA ×6](../../electronics/data-port-x6/design.py) and the [DATA ×4](../../electronics/data-port-x4/design.py).

Pin 1 is not 5 V. It carries the row's voltage, switched by the node, and stays off until the node's
firmware turns it on. The DATA board makes its own 5 V from it. Twist the USB pair (pins 3 and 4) by hand.
The I²C pair is the node's own bus ([I²C addresses](#i2c-addresses-on-the-data-lead)).

The lead's route is about 38 cm long, plugs included, and stays the same as the drawer slides. Put the
spare length in a wider bend between the node and the fixed end of the drag chain, never in front of its
moving end. A [sled](glossary.md) bay has no drag chain. Its route is about 22 cm, and the slack is coiled in
the [plenum](glossary.md), the space under the drawer. [Fit out a tray](../build/fit-out-a-tray.md) shows how
to lay the lead.

The bill of materials lists
[AliExpress 1005008045292937](https://www.aliexpress.com/item/1005008045292937.html), with the options
"Same direction", 8P, Length50CM. The listing does not give the wire gauge. JST rates the PH contact at 2 A
with 24 AWG wire only, so measure a conductor when the leads arrive. 24 AWG is about 0.51 mm across, 26 AWG
about 0.40 mm.

## Camera lead

The camera lead is the same 50 cm lead, about 45 cm routed. It runs from J6 (CAM), a vertical socket at the
rear right of the node, to J1 on the camera pod.

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

From the `design.py` of the [bay node](../../electronics/bay-node/design.py) and the
[camera pod](../../electronics/camera-pod/design.py).

A 6-pin cable joins the pod to the camera. It has a JST XH plug (2.54 mm) at the camera and Dupont sockets
at J2 on the pod. The cable that comes with the Arducam Mega works if it ends in Dupont sockets. The pins of
J2 are named on the PCB (VCC, GND, SCK, MISO, MOSI, CS): plug the wires by name.
[Add a camera](../build/camera.md) shows how to route both cables.

## The cable to your board

Each board needs a short USB cable, 15 to 25 cm. The board end is whatever the board takes: USB-C, micro-B
or mini-B. The drawer end is a straight USB-C plug that stands in a slot of the port wall. Use an angled plug
only if its cable leaves upwards.

- The receptacles of a DATA board stand 15.5 mm apart. The plug's overmould must fit within
  12.35 × 6.5 mm.
- Choose cables that state data (USB 2.0, 480 Mbps). Many short cables are charge-only.
- A micro-B or mini-B port that faces the port wall takes a 90° adapter, male to female. Plug the cable's
  straight plug into it. Right-angle micro-B adapters come in sets, and sellers name "up" and "down" either
  way: keep the one whose female socket faces up.

Which cable a board takes, and how it lies on the plate: [Put a board in a bay](../use/mount-a-board.md).

## AUX lead

J5 on the node is a JST PH 6, side entry, on the right edge between ROW OUT and DATA. It carries a UART and
the RESET and BOOT lines, for a board that has no USB serial port of its own.

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

From the [bay node's design.py](../../electronics/bay-node/design.py).

The levels are 3.3 V, and J5 has no ESD or level protection. The bill of materials has no AUX lead. Make one
from a 6-way JST PH housing and flying leads, as [Serial console](../use/serial-console.md) describes.

:::{warning}
J5 takes the same plug as ROW OUT (J2), 22 mm away on the same edge of the node. On the last node of a row,
J2 is empty and live: its pin 6 is VRACK. An AUX lead pushed into J2 puts VRACK on its BOOT wire, and into
your board. Only a row cable goes into ROW OUT.
:::

## Jumper wires on a DATA ×4

Female to female Dupont wires join a port's 2 × 6 pin header to the board's own pins. Use 20 cm wires, or
30 cm where 20 cm does not reach. Tear them off a 40-wire strip as a small ribbon. Do not wire GND: the USB
cable carries it. On the base assembly of the DATA ×4, only GND, RESET and BOOT are connected.

The 3D model colours them GND black, VREF red, RESET brown and BOOT green. Which wires a board needs, and
what VREF must be: [Wires between boards](../use/wires.md).

## Charger cable

Use a USB-C to USB-C cable, 5 A, e-marked (rated 100 W or 240 W), 1 to 2 m long. It runs from the charger
to PD IN on the rear wall of the power box. The e-marker matters: without it, a charger offers 3 A at most,
which is 60 W. A cable that came with the charger and is rated 100 W or more is e-marked. Which chargers to
use: [Specifications](specifications.md#chargers-and-what-each-feeds).

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

From each PCB's `design.py`.

No two addresses collide: a bay has one DATA board, and neither DATA board uses the node's 0x40. The node
tells the two DATA boards apart by one address. A DATA ×4 answers at 0x21, a DATA ×6 at 0x4C.

## What a wrong cable does

<!-- site:wrong-cable -->
| The mistake | What happens | Harm |
|---|---|---|
| A 1:1 lead used as a row cable | VRACK lands on the POS pins, behind 10 kΩ and a clamp (≈ 2.5 mA at 28 V); CAN_H and CAN_L swap. The next node stays off, and the bays after it | none |
| A row cable with CAN_H and CAN_L swapped or open | every node after it is missing from the hub's list | none |
| A row cable wired with VRACK on a CAN wire | the PESD2CAN of every tap conducts and fails short: the bus stops until they are replaced | the PESD2CAN of the hub and of every node; the transceivers survive |
| A 1:1 lead used as a DATA lead | the node keeps the lead off and says `SCL or SDA held low: DATA lead reversed?` | none |
| A camera lead in J7 (DATA) | J7's pin 1 lands on a GND pin of the pod. The eFuse limits, the node switches off and says `no DATA_VIN after switching on: a short on the lead (a camera lead in J7?)` | none; the camera does not work there |
| A DATA lead in J6 (CAM) | both end pins of J6 are GND: the DATA board gets no supply | none |
| A 1:1 lead used as a camera lead | CAM_5V lands on the cathodes of the pod's LEDs, not on a camera line | none |
| An AUX lead in ROW OUT (J2) | its BOOT wire carries VRACK | the board at the end of the lead |
| A row cable in AUX (J5) | the row's eFuse trips | not known |
| A 3 A cable on the charger | the charger offers 3 A: 60 W, of which the hub gives the rows 54 W | none |
| A charge-only USB cable to a board | the board is powered and never shows up on USB | none |
<!-- /site:wrong-cable -->
