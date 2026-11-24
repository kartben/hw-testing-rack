# Power hub

The power hub feeds the rack from one USB-C PD charger. It switches the charger's 20 V, called VRACK, to up
to four rows of bays. Each row has its own 1.6 A eFuse. The hub's ESP32-S3 controls the rows and runs the
rack bus, the CAN bus that links the hub to every bay node.

```{figure} ../../img/pcbs/power-hub-iso.jpg
:class: bb-screenshot
:alt: KiCad render of the power hub v1.0, seen from its front left
:width: 60%

KiCad render.
```

| | |
|---|---|
| Revision | v1.0, printed "POWER HUB v1.0 2026-11" on the bottom face |
| Size | 76 × 100 mm, 1.6 mm, 4 layers, lead-free HASL |
| One per | rack. It sits in the [power box](../../build/power-box.md), held through its four M3 holes |
| Controller | ESP32-S3-MINI-1-N8, antenna on the rear edge |
| Input | USB-C PD through a CH224A sink. There is no input switch: the charger's VBUS is VRACK |
| Outputs | four rows, A to D, each through a TPS26600 eFuse |
| Fitted by the fab | all 139 parts: nothing to solder |

## Connectors

| Connector | Type | Where | Takes |
|---|---|---|---|
| J1, PD IN | USB-C, GCT USB4105-GF-A-120 (5 A) | rear edge | the charger: VBUS and the two CC lines, no data |
| J2 to J5, ROW A to ROW D | JST PH 6, side entry (S6B-PH-SM4-TB) | left edge, 17.5 mm apart, A nearest the front | a row feed: VRACK, the CAN pair, the POS token |
| J6, USB | USB-C, the same part | front edge, right | a laptop, for the [console](../hub-shell.md) and for flashing. Its 5 V runs the controller only, never a row |

```{figure} ../../img/pcbs/power-hub-top.jpg
:class: bb-screenshot
:alt: KiCad render of the top face of the power hub
:width: 55%

KiCad render of the top face, rear edge up. PD IN is at the top right, RESET and BOOT at the top left. The
row sockets run down the left edge from D to A. The ten LEDs and the console USB-C line the front edge.
```

Each row socket has its letter printed beside it. All four have the same pinout:

<!-- site:pins-hub-row -->
| Pin of J2 to J5 | Row output |
|---|---|
| 1 | POS, the addressing token |
| 2 | GND |
| 3 | CAN_L |
| 4 | CAN_H |
| 5 | GND |
| 6 | VRACK |
<!-- /site:pins-hub-row -->

A bay node's ROW OUT has the same pinout. So the feed from the hub to a row is the same cable as a jumper
between two nodes ([Cables and pinouts](../cables.md)). All four row sockets carry the same CAN pair, and
both ends of the bus are terminated on the hub. POS goes out through 10 kΩ and a clamp, so a wrong cable that
puts VRACK on it does no harm.

## Buttons and LEDs

The hub has no power switch: it runs as soon as the charger is plugged in. SW1 RESET and SW2 BOOT are two
buttons at the rear left of the top face, RESET nearer the rear edge. In the power box, you press them with a
pin through two holes in the lid.

Ten side-view LEDs line the front edge and shine through the front wall of the box. From the left: ON (green)
and FAULT (red) of row A, then the same pair for rows B, C and D, then PD and CTL (both green).

| LED | Lit when |
|---|---|
| ON | the row's socket carries voltage |
| FAULT | the row's eFuse reports a fault while the row is switched on |
| PD | the hub holds a PD contract with the charger. It works without firmware |
| CTL | the controller's firmware sets it |

What each pattern of CTL means: [LEDs, buttons and switches](../leds-and-buttons.md#the-power-boxs-leds).

## Ratings

| | Design value |
|---|---|
| Charger input | USB PD: 9 V at plug-in, then the 20 V the controller asks for; up to 5 A through J1 |
| 28 V (EPR) | off in the firmware: the hub asks for 20 V |
| Current limit of a row | 1.6 A (1.52 to 1.68 A). The eFuse retries by itself |
| Voltage range of a row | off under 15 V and over 31 to 34 V |
| Soft start of a row | about 16 ms at 20 V |
| Row socket contacts | JST PH, 2 A per contact |
| Without firmware | every row off. The controller turns them on one after the other once the PD contract is final |
| Controller supply | from VRACK through a 5.24 V buck, or from the console USB-C, whichever is there; under 0.7 A |
| Input clamp | SMAJ30A TVS and 100 µF / 50 V on VRACK |
| Row current reading | each eFuse's IMON, 1.4 V per ampere, to the controller's ADC |
| CAN | TJA1462AT transceiver; 56 Ω between CANH and CANL (two split terminations of 2 × 56 Ω) |

What these add up to for your rack, and which chargers to use: [Specifications](../specifications.md).

## Test pads

The test pads are bare pads on the bottom face, each with its name printed beside or under it. The pads for
the supplies, GND and the controller's TX and RX are 1.5 mm. The others are 1.0 mm.

| Group | Names as printed |
|---|---|
| Supplies | VRACK, VHV (the CH224A's supply pin), 5V BUCK, 5V, USB 5V, 3V3, and four GND |
| Each row | ROW A to D (the output), EN A to D, FLT A to D, IMON A to D |
| PD | SDA and SCL under the word PD, PD PG, VSNS (VBUS through 100 kΩ / 10 kΩ) |
| Controller | TX, RX, EN, IO0 |
| CAN | CANH, CANL, TXD, RXD |

```{figure} ../../img/pcbs/power-hub-bottom.jpg
:class: bb-screenshot
:alt: KiCad render of the bottom face of the power hub, with the names of its test pads
:width: 55%

KiCad render of the bottom face, turned over left to right: the row sockets are now on the right.
```

What each pad should read: [Check the power hub](../../build/check-the-pcbs/power-hub.md).

## Pin map

The pin map of the controller, with the net, use and devicetree node of each pin, is in
[firmware/power-hub/README.md](../../../firmware/power-hub/README.md#pin-map). On the hub v1.0, four values in
its Use column are different:

- each row's enable has a 10 kΩ pull-down
- the IMON filter is 1 kΩ and 47 nF
- the pull-down on CAN_STB is 5.1 kΩ
- the resistor of the CTL LED is 1 kΩ

## Files

| | |
|---|---|
| Schematic | [power-hub-schematic.pdf](../../../electronics/power-hub/docs/power-hub-schematic.pdf) |
| Source and KiCad project | [electronics/power-hub/](../../../electronics/power-hub/), generated from [design.py](../../../electronics/power-hub/design.py) |
| Bill of materials | [power-hub-bom.csv](../../../electronics/power-hub/power-hub-bom.csv) |
| Fabrication files | [power-hub-fab.zip](/downloads/power-hub-fab.zip): Gerbers, JLCPCB's BOM and placement file |
| Outline and positions for the power box | `pcb.power_hub` in [config/rack.yaml](../../../config/rack.yaml) |

At JLCPCB, the order needs two corrections before you pay: D41 to D44 in the placement file, and the buck
inductor in the bill. They are listed on
[Order the PCBs](../../plan/order-the-pcbs.md#four-corrections-before-you-pay).

## Known issues

<!-- site:known-issues -->
- The track to row A's ON LED passes under the standoff of the front-left mounting hole, with only the
  solder mask between them. Turn that standoff gently. If it scratches through the mask, the LED stays dark
  while the row is powered. Nothing is damaged.
- After you unplug the charger, wait 6 s or more before you plug it back in. VRACK takes 2 to 6 s to fall.
  A charger with fast short-circuit detection may refuse a hub that still holds a few volts.
- Connect the console with a USB-C to USB-C cable. A cable from a live USB-A port can push the controller's
  3.3 V regulator to its absolute maximum for a moment.
- With only the console USB plugged in, the rack bus may not run: the CAN transceiver can stay below its
  supply threshold. Plug in the charger.
- The green LEDs run at about 1 mA and may be hard to see in daylight.
<!-- /site:known-issues -->
