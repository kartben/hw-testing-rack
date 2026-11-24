# DATA ×4

The DATA ×4 is the drawer board of a bay with wires: four switched and measured USB-C ports behind a hub, a
2 × 6 pin header per port, a switch matrix that joins any of the 32 pins on eight buses, and an RP2350B
co-processor that captures those buses as a logic analyzer.

:::{status} designed
v1.0 has been at the fab since 2026-11-11 and none is on a bench. The node's firmware for it is tested on
native_sim against an emulated PCB, and the analyzer on a XIAO ESP32-S3 with a Pico 2 in the
co-processor's place. Every value on this page is the design's; nothing has been measured. [What exists today](../../plan/status.md#status-data-x4).
:::

```{figure} ../../img/pcbs/data-port-x4-iso.jpg
:class: bb-screenshot
:alt: KiCad render of the DATA ×4 v1.0 with its logic, the four pin headers standing over the four USB-C receptacles
:width: 60%

KiCad render of the front face, with the logic fitted and the headers soldered.
```

| | |
|---|---|
| Revision | v1.0, printed "DATA ×4 v1.0 2026-11" on the rear face. Older text and its KiCad title call it "the v2", after a first design that was never built |
| Size | 100 × 70 mm, 1.6 mm, 4 layers, ENIG |
| One per | drawer of a bay with wires; the other drawers take a [DATA ×6](data-x6.md) |
| Held by | the printed cradle, as the DATA ×6: one cradle, one drawer and one lead for both |
| Supply | the node's DATA lead: 20 V on J1 pin 8; the PCB makes its own 5 V and 3.3 V |
| Fitted by the fab | 237 parts with the logic, 138 on the base, all on the front face |
| Soldered by hand | J1, four 2 × 6 headers and, with the logic, the SWD header ([Solder the connectors](../../build/solder-the-connectors.md)) |

## Two assemblies of one PCB

| | DATA-4x-logic | DATA-4x, the base |
|---|---|---|
| Hub, four ports with switch, meter and ESD | fitted | fitted |
| RESET and BOOT of each header | live | live |
| P1 to P8 and VREF of each header | through the matrix | end on empty pads |
| Matrix, co-processor, each port's pin chain | fitted | left off: 99 parts |
| SWD header J2 | soldered by hand | not fitted |
| JLCPCB's BOM and placement file | the two with no suffix | the two marked `-base-` |

The PCBs sent to the fab on 2026-11-11 were assembled with the logic. No signal of the base runs through a
part of the logic, so the base needs no jumper; a host sees the same 7-port hub on both. ENIG is there for
the RP2350B's 0.4 mm pitch. One of each on a 100 × 142 mm order panel is the third set of fab files
(`-panel-`); parting it is on [Solder the connectors](../../build/solder-the-connectors.md#part-a-data-4-panel).

## Ports and busids

Four standing USB-C receptacles (GCT USB4145-03-0170-C), 15.5 mm apart at the DATA ×6's positions 2 to 5,
each numbered in print beside it and again at its header.

| Port | Receptacle, header | Hub port | Meter, expander |
|---|---|---|---|
| 1 | J101, J102 | 1 | 0x41, 0x20 |
| 2 | J201, J202 | 2 | 0x43, 0x20 |
| 3 | J301, J302 | 3 | 0x44, 0x21 |
| 4 | J401, J402 | 4 | 0x45, 0x21 |

The hub's port 5 goes to the co-processor; ports 6 and 7 are not wired. The node names a device by its
hub port ([Bays, ports and addresses](../../use/names.md)):

```{include} ../../use/names.md
:start-after: <!-- site:port-busid -->
:end-before: <!-- /site:port-busid -->
```

Behind each receptacle, as on the DATA ×6: a TPS2553-1 switch, a 100 mΩ shunt and its INA226, a USBLC6, 56 kΩ to each CC line. A port is
off until the node switches it on.

## The pin header and VREF

One 2 × 6 header per port (2.54 mm, through-hole), on the front face over its port, pins forward. Its
names are printed above it in two lines, stacked like its two rows:

```text
VREF  1  2  3  4  BOOT
GND   5  6  7  8  RST
```

The numbers are the pins P1 to P8, and RST is RESET.

Each of the eight P pins runs through an ESD array, 100 Ω and a level translator (LSF0108) to a crosspoint
switch (CH446Q, on ±5 V), which can join it to any of eight buses, A to H
([Wires between boards](../../use/wires.md)). A bus is pulled up to 3.3 V by 10 kΩ and is one channel of
the [logic analyzer](../../use/logic-analyzer.md). The translator takes your board's side from VREF: a port's eight
pins are one voltage domain, whichever USB port the board is on.

- Wire VREF to the board's I/O supply. Wires and analyzer are specified for 0.95 to 3.6 V logic.
- A 5 V board whose inputs are TTL-compatible (most 5 V Arduinos) works with VREF on its own 3.3 V pin:
  it receives 3.3 V highs, which it reads, and the bus stays at 3.3 V.
- With VREF at 5 V the bus rises to about 4.0 to 4.2 V: outside the translator's recommended conditions,
  though nothing breaks. Strict CMOS 5 V inputs are not guaranteed.
- A P pin or VREF stands 5.5 V. 12 V destroys its ESD array, and a negative voltage is clamped with
  nothing to limit the current.

RESET and BOOT come from the port's expander through 1 kΩ, on both assemblies. Your board's own pull-ups
on those lines should be 4.7 kΩ or more: against a 1 kΩ pull-up, the 1 kΩ in series stops an asserted
line at about 1.65 V. Tie the jumpers down so that they do not pull on the header.

## The lead's connector

J1 is the DATA ×6's, pin for pin and at the same place: a JST PH 8, vertical, through-hole (B8B-PH-K-S) on
the rear face, pin 1 lowest, the names printed beside it (from the top VIN, GND, D+, D−, GND, SDA, SCL,
NC).

```{include} ../cables.md
:start-after: <!-- site:data-lead-pinout -->
:end-before: <!-- /site:data-lead-pinout -->
```

Pin 8 is the node's switched 20 V and pin 1 is not connected. The design log still describes a 5 V lead
with an interrupt line on pin 1: that was before v1.0 ([Cables and pinouts](../cables.md#data-lead)).

## The SWD header

J2, a 1 × 5 header (2.54 mm) on the top edge of the front face, on a PCB with its logic only, is the
co-processor's debug port, reachable from above with the PCB in its cradle. Its names are printed at the
header, pin 1 on the left as you face the front.

| Pin of J2 | Signal |
|---|---|
| 1 | SWCLK |
| 2 | GND |
| 3 | SWDIO |
| 4 | RUN |
| 5 | 3V3 |

Pins 1 to 3 follow the Pico 2's debug header: a Raspberry Pi Debug Probe's 3-pin lead plugs straight on.
RUN and 3V3 (the PCB's own 3.3 V, as the probe's reference) serve a J-Link or an ST-Link on Dupont wires.
The same nets are on test pads of the rear face.

## I²C addresses

```{include} ../cables.md
:start-after: <!-- site:i2c-addresses -->
:end-before: <!-- /site:i2c-addresses -->
```

The two TCA6408A carry each port's enable, fault flag, RESET and BOOT: 0x20 for ports 1 and 2, 0x21 for
ports 3 and 4. The TCA9534A at 0x38 writes the two crosspoint switches and holds the co-processor's RUN
and BOOTSEL; its reset line keeps every switch open until the node writes it. The node tells this PCB from
a DATA ×6 by the expander at 0x21.

## Ratings

| | Design value |
|---|---|
| VIN, J1 pin 8 | 20 V; the 5 V converter starts above 13.5 V (15.1 V at worst); 28 V at most |
| Drawn from the lead | 0.92 A at 20 V at most, 1.22 A at 15 V |
| 5 V | one converter: 5.08 V (4.94 to 5.22 V), 3.09 A at most with every port at its limit |
| A port's limit | 0.52 to 0.64 A; the switch latches off and raises its fault flag |
| A port's VBUS | 4.82 to 5.22 V |
| 3.3 V | AP2114H, 0.51 A at most |
| Pins P1 to P8 | 0.95 to 3.6 V logic as specified; 100 Ω in series |
| USB | USB2517I hub, USB 2.0 High-Speed: ports 1 to 4, the co-processor on port 5 |
| Co-processor | RP2350B with no flash: at each power-up it waits in its USB bootloader for the analyzer's image |

A rack's limits and the pins' logic levels: [Specifications](../specifications.md).

## Test pads

Bare pads on the rear face, each with its name printed under it. Those marked LOGIC ONLY in print float on
a base.

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

KiCad render of the rear face, drawn with J1 and the headers soldered. Port 1 is now on the right.
```

The first power is on the VIN and GND pads, from a bench supply limited to 0.3 A
([the DATA ×4's checklist](../../build/check-the-pcbs/data-x4.md)).

## Files

| | |
|---|---|
| Schematic | [data-port-x4-schematic.pdf](../../../electronics/data-port-x4/docs/data-port-x4-schematic.pdf) |
| Source and KiCad project | [electronics/data-port-x4/](../../../electronics/data-port-x4/), generated from [design.py](../../../electronics/data-port-x4/design.py) |
| Bill of materials | [data-port-x4-bom.csv](../../../electronics/data-port-x4/data-port-x4-bom.csv) and [data-port-x4-base-bom.csv](../../../electronics/data-port-x4/data-port-x4-base-bom.csv) |
| Fabrication files | [data-port-x4-fab.zip](/downloads/data-port-x4-fab.zip): Gerbers, and JLCPCB's BOM and placement file for the logic, the base and the panel; the content of [electronics/data-port-x4/fab/](../../../electronics/data-port-x4/fab/) |
| Positions the drawer and the cradle are drawn around | `pcb.data_port_x4_v2` in [config/rack.yaml](../../../config/rack.yaml) |
| Reasons | [Why the DATA ×4 is built this way](../../data-x4-v2-research.md) and the design log, [electronics.md](../../electronics.md), which also maps each P pin to its crosspoint line |

## Known issues of v1.0

From the [design review of 2026-11-09](../../pcb-review-2026-11-09.md) (in French; its finding numbers are
in brackets), calculated or read from the layout, none measured. Margins that change nothing in use stay
in the review. One finding was fixed before fabrication: ground vias under the co-processor.

<!-- site:known-issues -->
On both assemblies:

- J1's pin 8 (VIN, 20 to 28 V) is soldered by hand 0.58 mm from an open pad of the resistor array RN3
  and 0.30 mm from a track of port 4's D+. A solder bridge puts the lead's voltage on a hub pin and,
  through port 4, on a board's D+. Solder pin 8 last, RN3 under Kapton tape, and check before the first
  power. [X4A-01]
- Plugging or unplugging the DATA lead while it is powered can send its 20 to 28 V through the signal
  wires. It can destroy the node's I²C pins, its meter or this PCB's upstream USB port. Switch the bay's
  power off first. [X6-04]
- After a power cut shorter than 2 to 10 s the expanders may keep their state: ports that were on come
  back on by themselves, or the enable, RESET and BOOT lines sit anywhere until the node rewrites them. A
  board can see a reset pulse or a brief VBUS. [X4A-03]
- A port that is switched off keeps its VBUS near 2.5 V for many seconds (a time constant of 10 to 18 s).
  A board with no brown-out detection may start badly after a power cycle. [X4A-07]
- At the declared maximum, 3.09 A, the 5 V converter dissipates 1.45 to 1.75 W, 5 mm from a slot of the
  PETG cradle: the PCB is reckoned at 80 to 110 °C there, and PETG softens near 70 to 80 °C. The usual
  loads, about 2 A in all or less, are far from it. [X4A-02]
- The VIN test pad is 1.45 mm from SDA's: a probe tip across both puts 20 to 28 V on the I²C bus, on four
  meters rated 6 V, the expanders and, through a FET's body diode, the node. [X4A-06]
- Nothing clamps the 5 V rail: one failure in the converter puts VIN on the hub, on the port switches and
  on your boards. [X4A-09]
- The receptacles' peg holes follow an older GCT drawing, as on the DATA ×6: a receptacle may not go down
  flat. [X6-09]

With the logic:

- A port whose VREF is not wired is not isolated. The rule "under 0.65 V the node keeps that port's
  switches open" needs a VREF reading that v1.0 does not give the node: lows pass, highs are clamped near
  0.4 V. No danger. [X4B-09]
- An idle bus sits at 2.1 to 2.8 V, not 3.3 V, from each power-up until an image on the co-processor
  removes its reset pull-downs. A wire whose only pull-up is the bus's reaches a 3.3 V board under its
  CMOS high threshold (2.31 V) in the lower half of that range. Push-pull signals, and I²C with pull-ups
  on the boards, are not affected. [X4B-02]
- I²C at 1.8 V over a wire does not hold its low level if the 2.2 kΩ pull-ups of the bus are switched on
  (0.55 to 0.65 V for a limit of 0.54 V). With the 10 kΩ alone it does. [X4B-06]
- Nobody has confirmed which way round the fab's reel presents L1, the co-processor's core inductor: on
  the first PCB its dot must be on the pad nearer C33, and the +1V1 pad must read 1.1 V ± 3 %. [X4B-05]
- D1, the LED above the mark CP on the top edge, is driven by the co-processor: what it shows depends on
  the image loaded, and no source says.

Not settled: the headers of a base. The design log has it take two 2 × 1 pieces per port (GND and VREF,
RESET and BOOT); its bill of materials lists the 2 × 6.
<!-- /site:known-issues -->
