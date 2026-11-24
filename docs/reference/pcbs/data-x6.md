# DATA ×6

The DATA ×6 stands at the back of a drawer and gives it six USB-C ports behind a USB 2.0 hub. The bay node
switches and measures each port. The DATA ×6 has no pin headers: for a bay that needs wires between boards,
use a [DATA ×4](data-x4.md) instead.

```{figure} ../../img/pcbs/data-port-x6-iso.jpg
:class: bb-screenshot
:alt: KiCad render of the DATA ×6 v1.0, its six standing USB-C receptacles along the bottom edge
:width: 60%

KiCad render of the front face, the one that faces the port wall of the drawer.
```

| | |
|---|---|
| Revision | v1.0, printed "DATA ×6 v1.0 2026-11" on the rear face |
| Size | 100 × 70 mm, 1.6 mm, 4 layers, ENIG |
| One per | drawer, unless the bay takes a DATA ×4 |
| Held by | the printed cradle, with no screws. Each end sits 5.5 mm deep in a slot, and two T-heads go through the notches in the bottom edge. The DATA ×4 has the same outline, cradle and lead |
| Supply | the node's DATA lead: 20 V on J1 pin 8. The PCB makes its own 5 V and 3.3 V |
| Fitted by the fab | 158 parts, all on the front face |
| Soldered by hand | J1, the socket of the DATA lead, on the rear face ([Solder the connectors](../../build/solder-the-connectors.md)) |

## Ports

The six standing USB-C receptacles (GCT USB4145-03-0170-C, 7.46 mm tall) are 15.5 mm apart, with their
openings towards the port wall. Each has its number printed above it. Port 1 is on the left as you face the
front.

| Port | Hub port | 5 V rail | Meter (INA226) |
|---|---|---|---|
| 1, J101 | 6 | +5V_A | 0x41 |
| 2, J201 | 1 | +5V_A | 0x43 |
| 3, J301 | 2 | +5V_A | 0x44 |
| 4, J401 | 3 | +5V_B | 0x45 |
| 5, J501 | 4 | +5V_B | 0x47 |
| 6, J601 | 5 | +5V_B | 0x4C |

From [design.py](../../../electronics/data-port-x6/design.py). The node names each USB device by the hub port
it is on ([Bays, ports and addresses](../../use/names.md)):

```{include} ../../use/names.md
:start-after: <!-- site:port-busid -->
:end-before: <!-- /site:port-busid -->
```

Each port has a TPS2553-1 power switch, a 100 mΩ shunt read by its INA226, a USBLC6 ESD array, and 56 kΩ
from the switched 5 V to each CC line. A port gives default USB power and nothing more. There is no USB PD,
and no detection of what is plugged in. Every port is off until the node switches it on.

Each port has one green LED (D101 to D601), lit while the port is on. It sits right above its receptacle.
The bar of the cradle hides it from the front, so look from above. The PCB has no other LED.

## The DATA lead socket, J1

J1 is a JST PH 8, vertical, through-hole (B8B-PH-K-S). It sits on the rear face, at the end behind port 6.
Its pins run up the PCB, pin 1 lowest. Their names are printed beside it, from the top: VIN, GND, D+, D−,
GND, SDA, SCL, NC. "LEAD 20 V" is printed under them.

```{include} ../cables.md
:start-after: <!-- site:data-lead-pinout -->
:end-before: <!-- /site:data-lead-pinout -->
```

The lead is a ready-made "Same direction" lead ([DATA lead](../cables.md#data-lead)). VIN has no protection
on this PCB: the node's eFuse is the only one. SDA and SCL pass through two FETs, so the node's pull-ups
cannot feed the PCB while VIN is off.

## I²C addresses

```{include} ../cables.md
:start-after: <!-- site:i2c-addresses -->
:end-before: <!-- /site:i2c-addresses -->
```

The TCA9535 at 0x20 holds the controls of the ports. Port n has its enable on line 2n − 2 and its fault flag
on line 2n − 1. The four spare lines are pulled down. Only a DATA ×6 has a meter at 0x4C: that is how the
node tells it from a DATA ×4.

## Ratings

| | Design value |
|---|---|
| VIN, J1 pin 8 | 20 V, 28 V at most. The 5 V converters start above 13.5 V (15.1 V at worst) and stop below 10.8 V |
| Drawn from the lead | about 1.0 A at 20 V with 0.5 A on every port, 1.3 A with every port at its limit |
| 5 V | two converters, never in parallel: +5V_A for ports 1 to 3, +5V_B for ports 4 to 6 and the 3.3 V regulator; 5.08 V (4.94 to 5.22 V) |
| Current limit of a port | 0.52 to 0.64 A. After 7.5 ms at the limit, the switch latches off and raises its fault flag |
| VBUS of a port | 4.94 to 5.08 V |
| Back-feeding | a board that feeds a port from outside trips its switch, which latches off |
| 3.3 V | AP2114H, for the hub, the expander and the meters: 0.5 A at most |
| USB | USB2517I hub, USB 2.0 High-Speed, seven ports of which six are wired |
| Without the node | every port off |

Per port, per bay and per row in your rack: [Specifications](../specifications.md).

## Test pads

The test pads are bare pads on the rear face, each with its name printed under it. They are 1.5 mm for the
supplies and GND, 1.0 mm for the signals.

| Group | Names as printed |
|---|---|
| Supplies | VIN, +5V_A, +5V_B, +3V3, 1V8 (the hub's core rail), and eight GND |
| Each port | VBUS1 to VBUS6, FLT1 to FLT6 |
| Hub | HUB RST |
| I²C, on the PCB's side of the two FETs | SDA, SCL |

```{figure} ../../img/pcbs/data-port-x6-bottom.jpg
:class: bb-screenshot
:alt: KiCad render of the rear face of the DATA ×6: J1 with its pin names, and the test pads
:width: 70%

KiCad render of the rear face, with J1 soldered. Port 1's pads are now on the right.
```

Power the PCB for the first time on the VIN and GND pads, from a bench supply limited to 0.3 A
([Check a DATA ×6](../../build/check-the-pcbs/data-x6.md)). The VIN pad is 1.5 mm from a GND pad.

## Files

| | |
|---|---|
| Schematic | [data-port-x6-schematic.pdf](../../../electronics/data-port-x6/docs/data-port-x6-schematic.pdf) |
| Source and KiCad project | [electronics/data-port-x6/](../../../electronics/data-port-x6/), generated from [design.py](../../../electronics/data-port-x6/design.py) |
| Bill of materials | [data-port-x6-bom.csv](../../../electronics/data-port-x6/data-port-x6-bom.csv) |
| Fabrication files | [data-port-x6-fab.zip](/downloads/data-port-x6-fab.zip): Gerbers, JLCPCB's BOM and placement file |
| Outline and positions for the drawer and the cradle | `pcb.data_port_x6` in [config/rack.yaml](../../../config/rack.yaml) |

:::{warning}
At JLCPCB, the placement file turns U2, the port expander, a quarter turn off, and no port would switch on.
Make the corrections listed on [Order the PCBs](../../plan/order-the-pcbs.md#four-corrections-before-you-pay)
before you order. In the placement preview, check the + side of C60, the electrolytic capacitor on VIN.
:::

## Known issues

<!-- site:known-issues -->
- Do not plug or unplug the DATA lead while it is powered. Its 20 to 28 V can reach the signal wires first
  and destroy the node's I²C pins, its meter or the USB hub of this PCB. Switch the bay off first.
- Ports 1 to 3 and ports 4 to 6 are on two 5 V rails that can differ by 0.28 V. A board with two USB
  sockets, with one cable in each group, joins the rails, and the switch on the lower rail latches off. Put
  both cables in the same group.
- After a power cut of a few seconds or less, the port expander can keep its state. Ports that were on then
  come back on before the node has set them.
- With ports 4 to 6 all at their limit, converter B runs near its rating. On a 28 V rack it can then limit
  or cycle. The hub is on the same rail and drops with it. Boards that draw a few hundred milliamps are far from this.
- Converter A can stop and restart by itself, mostly when VIN is close to its 13.5 V threshold.
- Nothing clamps the 5 V rails. If a converter fails, VIN can reach the hub, the port switches and your
  boards.
- The peg holes for the receptacles are a little small, so a receptacle may not sit flat. A receptacle that
  sits askew also fouls the comb of the cradle. Look at all six before the first power-up.
- "LEAD 20 V" is printed under J1. On a rack with a 28 V contract, the lead carries 28 V.
- The port switch is the TPS2553DBVR-1. Do not replace it with the TPS2553DBVR, which does not latch off.
<!-- /site:known-issues -->
