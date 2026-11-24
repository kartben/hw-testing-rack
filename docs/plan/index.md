# How it works

BitBunk is a tilted rack of sliding drawers, printed end to end: twelve bays in its default 4 × 3 layout. Each
bay has a PCB of its own, the bay node, which switches and meters the boards in the drawer and puts their USB
on the network. One USB-C charger feeds the whole rack.

:::{status} designed
The printed frame is at v0.2 and has not been built, the five PCB designs have been at the fab at v1.0 since
2026-11-11, and the firmware has run in simulation and on stand-in boards only:
[What exists today](status.md).
:::

```{figure} ../img/viewer/rack.jpg
:alt: The rack from the front right: three rows of four bays on a base, three drawers pulled out, a laptop wired to one bay's front port

The 3D model: the drawers of B1, B3 and C2 pulled out, the power box under A1 at the bottom left.
[Open the model](/viewer/) to turn it round.
```

"Board" alone is your development board. The rack's own are PCBs of five kinds: the bay node, the power hub,
the DATA ×6, the DATA ×4 and the camera pod ([The five PCBs](../reference/pcbs/index.md)). The project's
other words are in the [glossary](../reference/glossary.md).

## One bay, from the tray up

```{figure} ../img/viewer/b3-drawer-out.jpg
:alt: Bay B3 with its drawer pulled out: a DATA ×4 at the back, four small boards on the plate, a USB cable to each

The 3D model: bay B3, the example bay of these pages, with its drawer out. A DATA ×4 stands behind the port
wall; two XIAOs and two Pico 2s sit on the plate between their pegs, each on its own USB cable; three-wire
ribbons run from the DATA ×4's pin headers to two of them.
```

| From the bottom | What it is |
|---|---|
| Tray | Printed. It slides into the grooves of the two ladders beside the bay and clicks in. Its 23 mm plenum hides the bay node and the drag chain, its front wall carries the front USB-C port, the status LED and the SERVICE switch, and its underside is the ceiling of the bay below |
| Bay node | The PCB in the tray: an ESP32-S3 on Wi-Fi, running Zephyr |
| Drawer | Printed. It slides 140 mm out along the slope while the boards stay powered and connected. A printed spring tab holds it closed; a pair of magnets is the option |
| Board plate | One honeycomb plate for every board. Clip-in pegs hold the boards on it, up to four small ones on a plate |
| DATA board | The PCB that stands in a cradle at the back of the drawer, its USB-C ports through the drawer's port wall. A DATA ×6 has six ports. A DATA ×4 has four, and pin headers, for bays whose boards need wires between them |
| Camera pod | Optional: a camera and its light under the bay's ceiling, looking down at the boards |

Two cables finish the bay. The DATA lead, eight wires, runs from the bay node through the drag chain to the
DATA board, and never needs touching again. Each board then has its own short USB cable to one port.

The same tray takes three other kinds of bay, and a bay converts from one to another. A sled is a drawer
without a drag chain: unplug the board's cable, then pull. A fixed bay is a sled screwed in place. A dense bay
has a slot bin in the plate's place, in which up to six boards stand on edge, one per port of a DATA ×6.

## A row, and the rack

The structure is a panel frame: every part is printed, and its only screws are the braces'. Side walls, the
ladders, stand between the columns, one per row, each shared by the bays on both sides. They snap onto base
ladders and onto each other and are topped by cap strips; floor plates tie the base, cap plates close the top
row. An X brace screwed behind every bay and behind the base keeps the grid square.

Rows are tilted 20°, so that every board, LED and label faces you. The default rack has three rows of four
bays, 165.8 mm from one column to the next: rows A and B, 165 mm high, with board plates, and on top row C,
120 mm high, of dense bays. A larger or a smaller rack: [Choose a size, change the layout](choose-your-rack.md).
Why a printed frame, USB-C, CAN and Wi-Fi: [Why it is built this way](../engineering/index.md).

A row is also the electrical unit. One row cable (six wires: the supply, a CAN bus and a position wire)
leaves the power box under A1, reaches the row's first bay node and goes on from node to node through the
ladders. The power hub switches a row as one, and has four outputs: four rows at most. The hub walks a row
with the position wire and each bay node takes its place in turn, so the third bay of row B answers as
`bay-b3.local` without anyone configuring it: [Bays, ports and addresses](../use/names.md).

## Where a board's USB goes

The DATA board gathers its ports on a USB hub, and the DATA lead takes them to the bay node, where two analog
USB switches decide who gets them.

```{raw} html
:file: ../img/diagrams/usb-path.svg
```

By default the boards go to the bay node's ESP32-S3, which is their USB host and exports each of them over
USB/IP: on a Linux machine `usbip attach` makes a board's probe and its serial port local devices. A laptop
plugged into the bay's front port takes the boards instead, as on a desk (classic mode), and the SERVICE
switch gives the front port to the bay node itself ([Front port and classic mode](../use/front-port.md)).
In every mode the bay node keeps the boards' power, so classic mode needs its firmware too: the supply on the
DATA lead is off until the firmware has switched it on.

The ESP32-S3 has one full-speed USB port: over USB/IP every board enumerates at 12 Mbit/s, and the boards of
a bay share it. That is plenty for a debug probe, a serial console or DFU; a large image dragged onto a
mass-storage bootloader takes longer. Classic mode is a plain analog path and a laptop gets high speed,
480 Mbit/s. What does not pass at all:
[Known issues, and what will not work](../reference/known-limitations.md#by-design-usb).

The reset lines, the serial console, the wires between pins, the logic analyzer and the camera are on
[What a bay can do](../use/index.md), with how far each has been tested.

## Where the power comes from

One USB-C PD charger outside the rack, 100 W at 20 V on a 5 A cable, is the only supply: no mains voltage
enters the printed parts. Its cable plugs into the power box under A1.

The power hub in the box asks the charger for 20 V, and the charger's output is the rack's supply rail,
VRACK. An eFuse per row, 1.6 A, keeps the row off until the contract with the charger is final. Each bay node
passes VRACK on to its DATA board through an eFuse of its own, about 1.76 A, and the DATA board makes the
boards' 5 V and switches and meters each port, about 0.5 A a port. Nothing reaches a drawer until the
firmware turns the bay node's eFuse on, and it stays on only if a DATA board answers on the lead within 1 s.
Every figure: [Specifications](../reference/specifications.md#voltages).

A 100 W charger does not feed twelve bays at their worst. The hub shares what the charger grants: with twelve
bays each DATA lead may draw 5.4 W, a port that does not fit waits its turn, and the hub switches a row off
before the charger cuts the whole rack:
[Power budget and queued ports](../use/power-budget.md).

## One file describes the rack

[config/rack.yaml](../../config/rack.yaml) holds the rack: its rows and columns, the tilt, every dimension,
the bays that have a camera, and an example population that says which board sits in which bay.
`tools/build.py` turns it into the constants of the printed parts and into the scene of the 3D model. The PCB
generators read its `pcb:` section, so that outlines, mounting holes and connector positions match the prints,
and `tools/bom.py` counts the bill of materials from it. Change a row or a column there, run
`tools/build.py`, and everything that depends on it is regenerated.

The 3D model is that file, drawn. [Bay B3 with its drawer out](/viewer/?bay=B3&openbay=1&view=bay) is the
example of these pages: a DATA ×4 bay with a XIAO on port 1 (B3.1), a Pico 2 on port 2 (B3.2), a stock
Pico 2 used as a stand-alone analyzer on port 3 (B3.3) and another XIAO on port 4. The bay's own analyzer is
the DATA ×4's co-processor; B3.3 was chosen before it
([A Pico 2 on a port instead](../use/logic-analyzer.md#a-pico-2-on-a-port-instead)).
