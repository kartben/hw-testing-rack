# DATA ×4

The DATA ×4 is the DATA board for a bay that needs wires between boards. It has four USB-C ports behind a
hub, each one switched and measured, and a 2 × 6 pin header for each port. In its full assembly, a switch
matrix joins those pins on eight buses, and an RP2350B records the buses as a logic analyzer.

```{figure} ../../img/pcbs/data-port-x4-iso.jpg
:class: bb-screenshot
:alt: KiCad render of the DATA ×4 v1.0 with its logic, the four pin headers standing over the four USB-C receptacles
:width: 60%

KiCad render of the front face, with the logic fitted and the headers soldered.
```

| | |
|---|---|
| Revision | v1.0, printed "DATA ×4 v1.0 2026-11" on the rear face. Its KiCad title block says "v2" |
| Size | 100 × 70 mm, 1.6 mm, 4 layers, ENIG |
| One per | drawer of a bay with wires. The other drawers take a [DATA ×6](data-x6.md) |
| Held by | the printed cradle. The DATA ×4 and the DATA ×6 take the same cradle, drawer and lead |
| Supply | the node's DATA lead: 20 V on J1 pin 8. The PCB makes its own 5 V and 3.3 V |
| Fitted by the fab | 237 parts with the logic, 138 on the base, all on the front face |
| Soldered by hand | J1, the four 2 × 6 headers and, with the logic, the SWD header ([Solder the connectors](../../build/solder-the-connectors.md)) |

## The two assemblies: logic and base

The same PCB is assembled in two ways. DATA-4x-logic has everything. DATA-4x, the base, leaves off the matrix
and the analyzer: its ports work, but its pin headers carry only GND, RESET and BOOT.

| | DATA-4x-logic | DATA-4x, the base |
|---|---|---|
| Hub, four ports with switch, meter and ESD | fitted | fitted |
| RESET and BOOT of each header | live | live |
| P1 to P8 and VREF of each header | through the matrix | not connected |
| Matrix, co-processor, the pin circuit of each port | fitted | left off: 99 parts |
| SWD header J2 | soldered by hand | not fitted |
| JLCPCB's BOM and placement file | the two with no suffix | the two marked `-base-` |

A host sees the same 7-port hub on both assemblies, and both take the same 2 × 6 headers.

## Ports

The four standing USB-C receptacles (GCT USB4145-03-0170-C) are 15.5 mm apart, in the same places as ports
2 to 5 of the DATA ×6. Each port's number is printed beside its receptacle and again at its header.

| Port | Receptacle, header | Hub port | Meter, expander |
|---|---|---|---|
| 1 | J101, J102 | 1 | 0x41, 0x20 |
| 2 | J201, J202 | 2 | 0x43, 0x20 |
| 3 | J301, J302 | 3 | 0x44, 0x21 |
| 4 | J401, J402 | 4 | 0x45, 0x21 |

Port 5 of the hub goes to the co-processor. Ports 6 and 7 are not wired. The node names each USB device by
the hub port it is on ([Bays, ports and addresses](../../use/names.md)):

```{include} ../../use/names.md
:start-after: <!-- site:port-busid -->
:end-before: <!-- /site:port-busid -->
```

Each port has the same parts as on the DATA ×6: a TPS2553-1 switch, a 100 mΩ shunt and its INA226, a
USBLC6, and 56 kΩ to each CC line. A port is off until the node switches it on. Its green LED sits over the
left end of its pin header.

## The pin header and VREF

Each port has a 2 × 6 header (2.54 mm, through-hole) on the front face, above the port, with its pins
pointing forward. The pin names are printed above it, in two lines that match its two rows:

```text
VREF  1  2  3  4  BOOT
GND   5  6  7  8  RST
```

The numbers are the pins P1 to P8. RST is RESET.

Each P pin runs through an ESD array, 100 Ω and a level translator (LSF0108) to a crosspoint switch
(CH446Q). The switch can join the pin to any of eight buses, A to H ([Wires between boards](../../use/wires.md)).
Each bus is pulled up to 3.3 V by 10 kΩ and is one channel of the
[logic analyzer](../../use/logic-analyzer.md). The translator takes the board's voltage from VREF, so all
eight pins of a port work at one voltage.

- Wire VREF to the board's I/O supply. The pins work with 0.95 to 3.6 V logic.
- A 5 V board whose inputs are TTL-compatible (most 5 V Arduinos) works with VREF on its own 3.3 V pin. It
  receives 3.3 V highs, which it reads, and the bus stays at 3.3 V.
- With VREF at 5 V, the bus rises to about 4.0 to 4.2 V. Nothing breaks, but this is outside the ratings of
  the translator, and strict CMOS 5 V inputs may not read it.
- Each P pin and VREF withstands up to 5.5 V. 12 V destroys the pin's ESD array. A negative voltage is
  clamped, with nothing to limit the current.

RESET and BOOT come from the port's expander through 1 kΩ, on both assemblies. Your board's own pull-ups on
those lines should be 4.7 kΩ or more. Against a 1 kΩ pull-up, an asserted line only falls to about 1.65 V.
Tie the jumper wires down so that they do not pull on the header.

## The DATA lead socket, J1

J1 is the same socket as on the DATA ×6, pin for pin and in the same place: a JST PH 8, vertical,
through-hole (B8B-PH-K-S) on the rear face, pin 1 lowest. Its names are printed beside it, from the top: VIN,
GND, D+, D−, GND, SDA, SCL, NC.

```{include} ../cables.md
:start-after: <!-- site:data-lead-pinout -->
:end-before: <!-- /site:data-lead-pinout -->
```

Pin 8 is the node's switched 20 V, and pin 1 is not connected ([DATA lead](../cables.md#data-lead)).

## The SWD header

J2 is the debug port of the co-processor. It is a 1 × 5 header (2.54 mm) on the top edge of the front face,
fitted on DATA-4x-logic only. With the PCB in its cradle, you can reach it from above once the rear cover of
the drawer is off. Its names are printed at the header, pin 1 on the left as you face the front.

| Pin of J2 | Signal |
|---|---|
| 1 | SWCLK |
| 2 | GND |
| 3 | SWDIO |
| 4 | RUN |
| 5 | 3V3 |

Pins 1 to 3 match the debug header of the Pico 2, so the 3-pin lead of a Raspberry Pi Debug Probe plugs
straight on. With a J-Link or an ST-Link on Dupont wires, use RUN as the reset. 3V3 is the PCB's own 3.3 V,
for the probe's reference. The same signals are on test pads of the rear face.

The co-processor's firmware drives the LED D1, above the mark CP on the top edge.

## I²C addresses

```{include} ../cables.md
:start-after: <!-- site:i2c-addresses -->
:end-before: <!-- /site:i2c-addresses -->
```

The two TCA6408A carry each port's enable, fault flag, RESET and BOOT: 0x20 for ports 1 and 2, 0x21 for
ports 3 and 4. The TCA9534A at 0x38 writes the two crosspoint switches and holds the RUN and BOOTSEL lines
of the co-processor. Every switch stays open until the node writes it. The node tells this PCB from a
DATA ×6 by the expander at 0x21.

## Ratings

| | Design value |
|---|---|
| VIN, J1 pin 8 | 20 V, 28 V at most. The 5 V converter starts above 13.5 V (15.1 V at worst) |
| Drawn from the lead | 0.92 A at 20 V at most, 1.22 A at 15 V |
| 5 V | one converter: 5.08 V (4.94 to 5.22 V), 3.09 A at most with every port at its limit |
| Current limit of a port | 0.52 to 0.64 A. The switch then latches off and raises its fault flag |
| Back-feeding | a port is a source only: a board that feeds its VBUS from outside trips the switch, which latches off |
| VBUS of a port | 4.82 to 5.22 V |
| 3.3 V | AP2114H, 0.51 A at most |
| Pins P1 to P8 | 0.95 to 3.6 V logic, 100 Ω in series |
| USB | USB2517I hub, USB 2.0 High-Speed: ports 1 to 4, the co-processor on port 5 |
| Co-processor | RP2350B with no flash. At each power-up it waits in its USB bootloader for the analyzer's firmware |

The limits of a whole rack: [Specifications](../specifications.md).

## Test pads

The test pads are bare pads on the rear face, each with its name printed under it. The pads marked LOGIC
ONLY are not connected on a base.

| Group | Names as printed |
|---|---|
| Supplies | VIN, +5V, +3V3, 1V8 (the hub's core rail), and nine GND |
| Each port | VBUS1 to VBUS4, FLT1 to FLT4 |
| Hub and expanders | HUB RST, EXP1 RST, EXP2 RST |
| I²C, on the PCB's side of the lead's FETs | SDA, SCL |
| Co-processor (logic only) | SWCLK, SWDIO, RUN, BOOT, +3V3_CP, +1V1 |
| Matrix (logic only) | −5V, +5V_MX, DAT, CK, STB1, STB2, MX RST |
| Buses (logic only) | A, B, C, D, E, F, G, H |

```{figure} ../../img/pcbs/data-port-x4-bottom.jpg
:class: bb-screenshot
:alt: KiCad render of the rear face of the DATA ×4: J1 with its pin names, the headers' tails, the test pads
:width: 70%

KiCad render of the rear face, with J1 and the headers soldered. Port 1 is now on the right.
```

Power the PCB for the first time on the VIN and GND pads, from a bench supply limited to 0.3 A
([Check a DATA ×4](../../build/check-the-pcbs/data-x4.md)).

## Files

| | |
|---|---|
| Schematic | [data-port-x4-schematic.pdf](../../../electronics/data-port-x4/docs/data-port-x4-schematic.pdf) |
| Source and KiCad project | [electronics/data-port-x4/](../../../electronics/data-port-x4/), generated from [design.py](../../../electronics/data-port-x4/design.py) |
| Bill of materials | [data-port-x4-bom.csv](../../../electronics/data-port-x4/data-port-x4-bom.csv) (with the logic) and [data-port-x4-base-bom.csv](../../../electronics/data-port-x4/data-port-x4-base-bom.csv) (the base) |
| Fabrication files | [data-port-x4-fab.zip](/downloads/data-port-x4-fab.zip): Gerbers, and JLCPCB's BOM and placement file for the logic, the base and the panel |
| Outline and positions for the drawer and the cradle | `pcb.data_port_x4_v2` in [config/rack.yaml](../../../config/rack.yaml) |

The panel files (`-panel-`) put one of each assembly on a 100 × 142 mm panel.
[Solder the connectors](../../build/solder-the-connectors.md#part-a-data-4-panel) shows how to break it
apart.

## Known issues

<!-- site:known-issues -->
On both assemblies:

- J1's pin 8 (VIN, 20 to 28 V) is 0.58 mm from an open pad of the resistor array RN3, and 0.30 mm from a
  track of port 4's D+. A solder bridge there puts the lead's voltage on the hub and on a board's D+. Cover
  RN3 with Kapton tape, solder pin 8 last, and check for bridges before the first power-up.
- Do not plug or unplug the DATA lead while it is powered. Its 20 to 28 V can reach the signal wires first
  and destroy the node's I²C pins, its meter or the USB hub of this PCB. Switch the bay off first.
- After a power cut shorter than 2 to 10 s, the expanders can keep their state. Ports that were on come back
  on by themselves, or the enable, RESET and BOOT lines sit anywhere until the node sets them. A board can
  see a reset pulse or a brief VBUS.
- A port that is switched off keeps its VBUS near 2.5 V for many seconds. A board with no brown-out
  detection may start badly after a power cycle.
- At its full 3.09 A, the 5 V converter heats the PCB to 80 to 110 °C near a slot of the PETG cradle. PETG
  softens near 70 to 80 °C. Usual loads, about 2 A in all or less, are far from this.
- The VIN test pad is 1.45 mm from the SDA pad. A probe tip across both puts 20 to 28 V on the I²C bus and
  can destroy the meters, the expanders and the node's I²C pins.
- Nothing clamps the 5 V rail. If the converter fails, VIN can reach the hub, the port switches and your
  boards.
- The peg holes for the receptacles are a little small, as on the DATA ×6, so a receptacle may not sit flat.

With the logic:

- A port whose VREF is not wired is not isolated: lows pass, and highs are clamped near 0.4 V. This does no
  harm.
- From power-up until the analyzer's firmware is loaded, an idle bus sits at 2.1 to 2.8 V instead of 3.3 V.
  A wire whose only pull-up is the bus's may then stay under a 3.3 V board's high threshold. Push-pull
  signals, and I²C with pull-ups on the boards, are not affected.
- I²C at 1.8 V over a wire does not hold its low level with the bus's 2.2 kΩ pull-ups switched on. With the
  10 kΩ pull-ups alone, it does.
- Check L1, the co-processor's core inductor. Its dot must be on the pad nearer C33, and the +1V1 pad must
  read 1.1 V ± 3 %.
<!-- /site:known-issues -->
