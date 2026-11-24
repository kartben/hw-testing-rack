# DATA ×6

The DATA ×6 stands at the back of a drawer and gives it six USB-C ports behind a USB 2.0 hub, each one
switched and measured by the bay node. It carries power and USB only: no pin header, no RESET or BOOT
line, no matrix.

:::{status} designed
v1.0 has been at the fab since 2026-11-11 and none is on a bench. The node's firmware drives it since
2026-11-11, tested on native_sim against an emulated PCB only. Every value on this page is the design's;
nothing has been measured. [What exists today](../../plan/status.md#status-data-x6).
:::

```{figure} ../../img/pcbs/data-port-x6-iso.jpg
:class: bb-screenshot
:alt: KiCad render of the DATA ×6 v1.0, its six standing USB-C receptacles along the bottom edge
:width: 60%

KiCad render of the front face, the one that faces the drawer's port wall.
```

| | |
|---|---|
| Revision | v1.0, printed "DATA ×6 v1.0 2026-11" on the rear face |
| Size | 100 × 70 mm, 1.6 mm, 4 layers, ENIG |
| One per | drawer, unless the bay needs wires and takes a [DATA ×4](data-x4.md) |
| Held by | the printed cradle, with no screw: 5.5 mm at each end in its slots, two T-heads through the notches of the bottom edge. Outline, cradle and lead are the DATA ×4's |
| Supply | the node's DATA lead: 20 V on J1 pin 8; the PCB makes its own 5 V and 3.3 V |
| Fitted by the fab | 158 parts, all on the front face |
| Soldered by hand | J1, the lead's socket, on the rear face ([Solder the connectors](../../build/solder-the-connectors.md)) |

## Ports and busids

Six standing USB-C receptacles (GCT USB4145-03-0170-C, 7.46 mm tall) 15.5 mm apart, their mouths towards
the port wall. Each has its number printed above it, port 1 on the left as you face the front.

| Port | Hub port | 5 V rail | Meter (INA226) |
|---|---|---|---|
| 1, J101 | 6 | +5V_A | 0x41 |
| 2, J201 | 1 | +5V_A | 0x43 |
| 3, J301 | 2 | +5V_A | 0x44 |
| 4, J401 | 3 | +5V_B | 0x45 |
| 5, J501 | 4 | +5V_B | 0x47 |
| 6, J601 | 5 | +5V_B | 0x4C |

Read from the port and hub sheets of [design.py](../../../electronics/data-port-x6/design.py). Port 1 is on
the hub's port 6 and port n on its port n − 1, and the node names a device by the hub port it hangs on
([Bays, ports and addresses](../../use/names.md)):

```{include} ../../use/names.md
:start-after: <!-- site:port-busid -->
:end-before: <!-- /site:port-busid -->
```

Behind each receptacle: a TPS2553-1 power switch, a 100 mΩ shunt read by the port's INA226, a USBLC6 ESD
array, and 56 kΩ from the switched 5 V to each CC line. A port is a source of "default USB power" and
nothing more: no USB PD, no detection of what is plugged. Every port is off until the node switches it on.

Each port has one green LED (D101 to D601) on its switched 5 V, lit while the port is on. It sits right
above its receptacle, and the review of the layout expects the cradle's bar to hide it from the front: it
shows from above only. The PCB has no other LED.

## The lead's connector

J1 is a JST PH 8, vertical, through-hole (B8B-PH-K-S), on the rear face at the end behind port 6. Its pins
run up the PCB, pin 1 lowest, and their names are printed beside it: from the top VIN, GND, D+, D−, GND,
SDA, SCL, NC, with "LEAD 20 V" under them.

```{include} ../cables.md
:start-after: <!-- site:data-lead-pinout -->
:end-before: <!-- /site:data-lead-pinout -->
```

The lead is a ready-made "Same direction" one ([Cables and pinouts](../cables.md#data-lead)). VIN has no
protection of its own on this PCB: the node's eFuse is the only one. The lead's SDA and SCL pass through
two FETs, so the node's pull-ups cannot feed the PCB while VIN is off.

## I²C addresses

```{include} ../cables.md
:start-after: <!-- site:i2c-addresses -->
:end-before: <!-- /site:i2c-addresses -->
```

The TCA9535 at 0x20 holds the ports' controls: port n's enable on its line 2n − 2 and its fault flag on
line 2n − 1; the four spare lines are pulled down. The node tells this PCB from a DATA ×4 by the meter at
0x4C, which only a DATA ×6 has.

## Ratings

| | Design value |
|---|---|
| VIN, J1 pin 8 | 20 V; the 5 V converters start above 13.5 V (15.1 V at worst) and stop below 10.8 V; 28 V at most |
| Drawn from the lead | about 1.0 A at 20 V with 0.5 A on every port, 1.3 A with every port at its limit |
| 5 V | two converters, never in parallel: +5V_A for ports 1 to 3, +5V_B for ports 4 to 6 and the 3.3 V regulator; 5.08 V (4.94 to 5.22 V) |
| A port's limit | 0.52 to 0.64 A; in limit for 7.5 ms, the switch latches off and raises its fault flag |
| A port's VBUS | 4.94 to 5.08 V |
| Back-feeding | a source that feeds a port from outside trips its switch, which latches off |
| 3.3 V | AP2114H, for the hub, the expander and the meters: 0.5 A at most |
| USB | USB2517I hub, USB 2.0 High-Speed, seven ports of which six are wired |
| Without the node | every port off |

Per port, per bay and per row in a rack: [Specifications](../specifications.md).

## Test pads

Bare pads on the rear face, each with its name printed under it: 1.5 mm for the supplies and GND, 1.0 mm
for signals.

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

KiCad render of the rear face, drawn with J1 soldered. Port 1's pads are now on the right.
```

The first power is on the VIN and GND pads, from a bench supply limited to 0.3 A
([the DATA ×6's checklist](../../build/check-the-pcbs/data-x6.md)). The VIN pad is 1.5 mm from a GND pad.

## Files

| | |
|---|---|
| Schematic | [data-port-x6-schematic.pdf](../../../electronics/data-port-x6/docs/data-port-x6-schematic.pdf) |
| Source and KiCad project | [electronics/data-port-x6/](../../../electronics/data-port-x6/), generated from [design.py](../../../electronics/data-port-x6/design.py) |
| Bill of materials | [data-port-x6-bom.csv](../../../electronics/data-port-x6/data-port-x6-bom.csv) |
| Fabrication files | [data-port-x6-fab.zip](/downloads/data-port-x6-fab.zip): Gerbers, JLCPCB's BOM and placement file, the content of [electronics/data-port-x6/fab/](../../../electronics/data-port-x6/fab/) |
| Positions the drawer and the cradle are drawn around | `pcb.data_port_x6` in [config/rack.yaml](../../../config/rack.yaml) |
| How the node drives it | [One node, several boards](../../multi-dut-node.md) |
| Reasons | the design log, [electronics.md](../../electronics.md), has no section on this PCB; this page is read from `design.py`, `config/rack.yaml` and the checklist |

## Known issues of v1.0

From the [design review of 2026-11-09](../../pcb-review-2026-11-09.md) (in French; its finding numbers are
in brackets), calculated or read from the layout, none measured. Margins that change nothing in use stay
in the review. Two of its findings were fixed before fabrication: copper under the 3.3 V regulator, and
the 5 V set to 5.08 V.

<!-- site:known-issues -->
- At JLCPCB only: the committed placement file, `data-port-x6-cpl-jlcpcb.csv`, has no rotation correction
  for U2, the TCA9535. Placed as that file says, U2 is a quarter turn off: no port can be switched on, on
  every assembled PCB, until U2 is lifted and turned with hot air. Nothing is destroyed. An assembler that
  reads KiCad's own position file, as NextPCB did for the order of 2026-11-11, places it right. [X6-01]
- Plugging or unplugging the DATA lead while it is powered can send its 20 to 28 V through the signal
  wires: the PH connector has no ground contact that mates first. It can destroy the node's I²C pins, its
  meter or this PCB's upstream USB port. Switch the bay's power off first. [X6-04]
- Ports 1 to 3 and ports 4 to 6 are on two 5 V rails that can differ by 0.28 V. A board with two USB
  sockets, one cable in each group, joins the rails: the switch on the lower one sees its output above
  its input and latches off. Put both cables in the same group. [X6-12]
- After a power cut of a few seconds or less the port expander may keep its state (it resets under
  0.75 V only, and nothing discharges the rails): ports that were on come back on as the 3.3 V returns,
  before the node has written anything. [X6-08]
- With ports 4 to 6 at their limit, converter B runs at 96 % of its rating and dissipates 1.0 to 1.3 W in
  a SOT-23-6. Boards that draw a few hundred milliamps are far from it; at the documented maximum on a 28 V
  rack it can limit or cycle, and the hub, on the same rail, drops with it. [X6-05]
- The converters' enable line runs 83 mm at high impedance past a switching node: converter A may stop
  and restart by itself, mostly with VIN close to its 13.5 V threshold. [X6-06]
- Nothing clamps the 5 V rails: one failure in a converter (an open joint on its feedback divider, a
  shorted switch) puts VIN on the hub, on the port switches and on your boards. [X4A-09: the review files it under the DATA ×4 and finds the same design here]
- The receptacles' peg holes follow an older GCT drawing (0.66 mm where the current one asks 0.71 mm, for
  pegs of 0.56 ± 0.05 mm): a receptacle may not go down flat, and one that sits askew also fouls the
  cradle's comb. Look at the six at stage 1 of the checklist. [X6-09]
- "LEAD 20 V" is printed under J1: on a rack with a 28 V contract the same lead carries 28 V. [X6-13]
- At JLCPCB, check in the placement preview the polarity of C60 (an electrolytic on VIN), the way the six
  receptacles stand, and the crystal; the port switch TPS2553DBVR-1 was down to one piece in JLCPCB's
  stock on 2026-11-09, and its pin-compatible TPS2553DBVR does not latch. [X6-11, SYS-6]
<!-- /site:known-issues -->
