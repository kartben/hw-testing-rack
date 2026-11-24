# Power hub

The power hub turns one USB-C PD charger into the rack's supply (VRACK, 20 V) and switches it to four rows,
each behind a 1.6 A eFuse; its ESP32-S3 is the rack controller and the master of the rack's CAN bus.

:::{status} designed
v1.0 has been at the fab since 2026-11-11 and none is on a bench. Every value on this page is the design's, read
from `design.py` and the bill of materials; nothing has been measured.
[What exists today](../../plan/status.md#status-power-hub).
:::

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
| One per | rack, in the [power box](../../build/power-box.md), on four M3 holes |
| Controller | ESP32-S3-MINI-1-N8, antenna on the rear edge |
| Input | USB-C PD through a CH224A sink; no input switch: the charger's VBUS is VRACK |
| Outputs | four rows, A to D, each through a TPS26600 eFuse |
| Fitted by the fab | all 139 parts; nothing to solder by hand |

## Connectors and pinouts

| Connector | Type | Where | Carries |
|---|---|---|---|
| J1, PD IN | USB-C, GCT USB4105-GF-A-120 (5 A) | rear edge | the charger: VBUS and the two CC lines, no data |
| J2 to J5, ROW A to ROW D | JST PH 6, side entry (S6B-PH-SM4-TB) | left edge, 17.5 mm apart, A nearest the front | a row: VRACK, the CAN pair, the POS token |
| J6, USB | USB-C, the same part | front edge, right | the controller's [console](../hub-shell.md) and flashing; its 5 V runs the controller alone, never a row |

```{figure} ../../img/pcbs/power-hub-top.jpg
:class: bb-screenshot
:alt: KiCad render of the top face of the power hub
:width: 55%

KiCad render of the top face, rear edge up. PD IN is at the top right, RESET and BOOT at the top left; the
row sockets run down the left edge from D to A; the ten LEDs and the console USB-C line the front edge.
```

The names are the schematic's; on the PCB each row socket has its letter printed beside it. The four share one pinout:

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

This is a bay node's ROW OUT, so the feed from the hub is the same flat cable as a jumper between two
nodes, pin n to pin 7 − n ([Cables and pinouts](../cables.md)). Every row socket carries the same CAN
pair: the bus is a star with the hub at its centre, and both terminations are on the hub. POS leaves
through 10 kΩ and a clamp, so a wrong cable that puts VRACK on it costs about 2.5 mA at 28 V and breaks
nothing.

## Buttons and LEDs

The charger's plug in J1 is the only power switch. SW1 RESET and SW2 BOOT are two tactile buttons at the
rear left of the top face, RESET nearer the rear edge; in the power box a pin reaches them through two
holes in the lid.

Ten side-view LEDs sit along the front edge and shine through the box's front wall. From the left: ON
(green) and FAULT (red) of row A, then of rows B, C and D, then PD and CTL (both green).

| LED | Driven by |
|---|---|
| ON | the row's own output: lit while there is voltage on the row's socket |
| FAULT | the row's enable line into the eFuse's fault output: lit only for a fault on a row that is switched on |
| PD | the CH224A's power-good pin: on while a PD contract is in place, with no firmware involved |
| CTL | the controller's firmware |

The patterns of each LED, the five of CTL among them, are on
[LEDs, buttons and switches](../leds-and-buttons.md).

## Ratings

| | Design value |
|---|---|
| Charger input | USB PD: 9 V at plug-in, then the 20 V contract the controller asks for; up to 5 A through the receptacle |
| 28 V (EPR) | designed in, but the default firmware build cannot ask for it (`CONFIG_HUB_EPR_ALLOWED` off), and its margins are thin: see the known issues |
| A row | limit 1.6 A (1.52 to 1.68 A), retried by itself; off under 15 V and over 31 to 34 V; soft start about 16 ms at 20 V |
| A row's contacts | JST PH, 2 A per contact |
| Without firmware | every row off; the controller turns them on one after the other once the contract is final |
| Controller's supply | from VRACK (5.24 V buck, running from the charger's first 5 V) or from the console USB-C, whichever is there; under 0.7 A |
| Input clamp | SMAJ30A TVS and 100 µF / 50 V on VRACK |
| Row current reading | each eFuse's IMON, 1.4 V per ampere, to the controller's ADC |
| CAN | TJA1462AT; 56 Ω between CANH and CANL (two split terminations of 2 × 56 Ω) |

What these add up to for a rack, and which chargers fit: [Specifications](../specifications.md).

## Test pads

Bare pads on the bottom face, each with its name printed beside or under it: 1.5 mm for the supplies, GND
and the controller's TX and RX, 1.0 mm for the other signals.

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

KiCad render of the bottom face, the PCB turned over left to right: the row sockets are now on the right.
```

The value each pad should show with no power, on the console USB alone and on a charger is in
[the power hub's checklist](../../build/check-the-pcbs/power-hub.md).

## Pin map

The controller's pins, from the firmware's README, where
[check_pinmap.py](../../../firmware/tools/check_pinmap.py) holds the table against
[design.py](../../../electronics/power-hub/design.py) and the devicetree, pin by pin and net by net.

```{include} ../../../firmware/power-hub/README.md
:start-after: <!-- site:pin-map -->
:end-before: <!-- /site:pin-map -->
```

The check covers the pin and the net, not the Use column, and four of its cells are older than v1.0. In
`design.py` the pull-down of each row's enable is 10 kΩ, IMON's filter is 1 kΩ and 47 nF, CAN_STB's
pull-down is 5.1 kΩ and the CTL LED's resistor is 1 kΩ.

## Files

| | |
|---|---|
| Schematic | [power-hub-schematic.pdf](../../../electronics/power-hub/docs/power-hub-schematic.pdf) |
| Source and KiCad project | [electronics/power-hub/](../../../electronics/power-hub/), generated from [design.py](../../../electronics/power-hub/design.py) |
| Bill of materials | [power-hub-bom.csv](../../../electronics/power-hub/power-hub-bom.csv) |
| Fabrication files | [power-hub-fab.zip](/downloads/power-hub-fab.zip): Gerbers, JLCPCB's BOM and placement file, the content of [electronics/power-hub/fab/](../../../electronics/power-hub/fab/) |
| Positions the power box is drawn around | `pcb.power_hub` in [config/rack.yaml](../../../config/rack.yaml) |
| Reasons | [power.md](../../power.md) and the design log, [electronics.md](../../electronics.md) |

## Known issues of v1.0

From the [design review of 2026-11-09](../../pcb-review-2026-11-09.md) (in French; its finding numbers are
in brackets), calculated or read from the layout, none measured. Margins that change nothing in use stay
in the review.

<!-- site:known-issues -->
- A track of row A's ON LED passes under the standoff of the front-left mounting hole, with only the
  solder mask between them. A standoff that scratches the mask as it is turned grounds that line: row A's
  ON LED then stays dark while the row is powered. Nothing is damaged. [PH-03]
- Nothing discharges the 140 µF or so on VRACK. After the charger is unplugged the rail takes 2 to 6 s to
  fall to 0.8 V, and a charger plugged back within those seconds finds 1 to 3 V on VBUS. USB PD expects
  about 10 µF at insertion: a charger with a fast short-circuit detection may refuse the hub. [PH-05]
- 28 V has no margin. A 28 V contract may sit at 29.4 V; the CH224A is rated 30 V in service and 32 V at
  most, and the TVS starts to conduct at 33.3 V, so it never protects that chip. A row's eFuse tripped by
  an over-voltage closes again only under 28.5 to 31.5 V. At 20 V the margin is 11 V. [PH-06]
- Plugging the console USB-C into a live USB-A port can take the controller's 3.3 V regulator to its
  absolute maximum for some tens of microseconds (6.0 to 6.5 V estimated, 6.5 V allowed). A USB-C to
  USB-C cable does not. [PH-04]
- On the console USB alone the CAN transceiver, fed through a diode, can sit under its under-voltage
  threshold: the rack bus may or may not run until VRACK is up. [PH-07]
- The green LEDs get about 1 mA (about 3 mcd). Whether they show in daylight through the box's wall is
  for the first PCB to tell. [PH-12]
- At JLCPCB only: the committed placement file sets the four row diodes D41 to D44 0.34 mm off their
  pads [PH-01], and JLCPCB lists the buck's inductor (C48009678) without a footprint: C553961 is the same
  part on another reel [PH-10]. Neither applies to an assembler that reads KiCad's own position file.
- Open until a hub is on a bench: the CH224A's I²C address (the datasheet says 0x22 or 0x23; the firmware
  uses 0x22), and whether it reports a 100 W charger's offers.
<!-- /site:known-issues -->
