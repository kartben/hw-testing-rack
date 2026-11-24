# Glossary

This page explains the words used across the BitBunk pages.

"Board" alone always means your development board. The rack's own electronics are "the PCBs": the bay node,
the power hub, the DATA ×6, the DATA ×4 and the camera pod.

## Other words on screens and in files

The firmware, the tools and the design files sometimes use a different word for the same thing:

| These pages say | A screen, a command or a file may say | Where |
|---|---|---|
| board | DUT, device under test | the rack's page (`DUT off`), the bay's page, the node's shell, the metrics (`bay_dut_*`) |
| port, written B3.2 | sub-slot, slot | `bayctl`'s messages, the bay page's reservation dialog, `"slot"` in the API |
| reserve, reservation | lease | `bayctl lease`, `POST /api/lease` |
| the PCBs | boards | [electronics/](../../electronics/) and the fabrication files |
| the module's one-time fuse | eFuse | `espefuse.py` and Espressif's documents |
| BitBunk | `hw-testing-rack` | the boot log and the shell's `help` of a bay node and of the hub, and the name of the PDU that `bayctl export pdudaemon` writes |

[States and messages](states-and-messages.md) explains the states that a page or a command
shows, such as `waiting`, `shed` and `queued`.

## A to Z

```{glossary}
AUX
  The bay node's connector J5: a UART, a RESET line and a BOOT line at 3.3 V, wired by hand to one board.
  See [Serial console](../use/serial-console.md).

bay
  One place in the rack, named by its row letter and column number: B3 is row B, third from the left. It
  holds a tray, a bay node, a drawer and a DATA board. Your rack has as many bays as you set in
  `config/rack.yaml`. See [Bays, ports and addresses](../use/names.md).

bay node
node
  The PCB in each tray. It switches and meters the bay's power, shares the boards' USB over the network and
  serves the bay's page.

bayctl
  The command-line tool that drives the rack: [bayctl](bayctl.md).

board
  Alone, your development board. The rack's own are {term}`PCBs <PCB>`.

board plate
plate
  The printed honeycomb plate in a drawer. Pegs clip into its holes to hold a board.

board target
  What a bay node remembers about the board on a port, for twister: its Zephyr target, runner, probe and
  console. See [Board targets](../use/board-targets.md).

brace
  The printed X screwed to the back of every bay and of the base. It keeps the frame square.

busid
  USB/IP's name for a device on a bay node, such as `1-1.2`. See [Bays, ports and addresses](../use/names.md).

camera pod
  The camera, its four white LEDs and its small PCB, in a printed holder under a bay's ceiling.

claim
  To give a bay node or the power hub its admin key. A press on the PCB's BOOT button confirms it. See
  [Control who can use the rack](../use/access.md).

classic mode
  A mode in which the boards' USB goes to a laptop plugged into the bay's front port, instead of over the
  network. See [Front port and classic mode](../use/front-port.md).

co-processor
  The RP2350B on a DATA ×4. At each power-up, the bay node loads an image into it, for example the logic
  analyzer.

cradle
  The printed holder in which a DATA board stands at the back of a drawer.

DATA board
  The PCB at the back of a drawer, with the USB-C ports your boards plug into: a DATA ×6 or a DATA ×4.

DATA lead
  The 8-wire lead from the bay node to the DATA board, through the drag chain. It carries power, USB and
  I²C. See [Cables and pinouts](cables.md).

DATA ×4
  A DATA board with four USB-C ports, a pin header beside each, a pin matrix and a co-processor. In
  `config/rack.yaml`, `x4: v2` is this board and `x4: base` the same board without the matrix and the
  co-processor.

DATA ×6
  A DATA board with six USB-C ports, each switched and metered.

dense bay
  A bay whose boards stand on edge in a slot bin, up to six on a DATA ×6.

drag chain
  The cable chain under the drawer that carries the DATA lead, so the boards stay connected while the drawer
  is out.

drawer
  The printed part that slides 140 mm out of its tray. It holds the board plate in front and the DATA board
  at the back.

DUT
  Device under test: the firmware's word for a {term}`board`.

eFuse
  The protection chip that switches a supply and limits its current: one per row on the power hub, one on
  each bay node. Not the ESP32-S3's {term}`one-time fuse`.

fascia
  The tray's front wall, under the drawer, with the front USB-C port, the status LED and the SERVICE switch.

feed
  The row cable from the power box to the first bay of a row.

grant
  The power that the hub allows each bay. It depends on the charger and on the number of bays. See
  [Power budget and queued ports](../use/power-budget.md).

hub
  Alone, the {term}`power hub`. The chip on a DATA board is the {term}`USB hub`.

jumper
  A short row cable from one bay node to the next. Jumper wires are the Dupont leads from a DATA ×4's pin
  header to a board.

ladder
  A printed side wall between two columns, one per row. The trays slide into its grooves.

lease
  The word that the API and `bayctl` use for a reservation.

one-time fuse
  A bit of the ESP32-S3 module that you burn once on each bay node and power hub. It cannot be undone. See
  [Flash the hub and the nodes](../build/flash.md).

PCB
  One of the rack's own five: the power hub, the bay node, the camera pod, the DATA ×6 and the DATA ×4. See
  [The five PCBs](pcbs/index.md).

peg
  A printed part that clips into the board plate to hold a board: a stop, a cam on its base, a pin, or a
  bobbin for spare cable.

plenum
  The space inside a tray, under the drawer, for the bay node and the drag chain.

port
  One USB-C socket of a DATA board, with its own power switch and meter, numbered from 1 at the left. With
  its bay: B3.2.

port block
  In a sled bay, the back of the drawer, which stays in the tray with the DATA board when the sled comes
  out.

POS
  The position wire of the row cable. It tells each bay node its place in the row.

power box
  The printed box under bay A1 that holds the power hub.

power hub
  The PCB that takes power from the USB-C charger, switches each row and runs the rack bus.

queued
  A port asked to switch on "when available". It goes on by itself when there is power for it.

rack bus
  The CAN bus and the POS wire in the row cables, between the power hub and the bay nodes.

reserve
  To hold a bay, or some of its ports, for your machine for a while. See [Reserve a bay](../use/reserve-a-bay.md).

row
  A line of bays, lettered from the bottom: A to D. A rack has one to four rows. The hub switches each row
  as one.

row cable
  The 6-wire cable that carries power, CAN and POS along a row, from bay node to bay node.

same direction
  A ready-made JST PH lead whose pin 1 at one end is the last pin at the other end. Sellers do not all use
  the name the same way, so check each lead with a meter. See [Make the row cables](../build/row-cables.md).

SERVICE
  The switch on the fascia that hands the front USB-C port to the bay node, to flash it.

shed
  Switched off for lack of power, and switched back on when there is room. The hub sheds rows. A bay node
  sheds ports.

simulated node
  The bay's page and API running on your computer with no hardware. See
  [Try it without hardware](../plan/try-it-without-hardware.md).

sled
  A drawer without a drag chain. Unplug the board's cable before you pull it out.

slot
  In `bayctl` and the API, what holds one board.

slot bin
  The printed bin that replaces the plate in a dense bay. Boards stand on edge in its six lanes.

sub-slot
  `bayctl`'s word for a port: B3.2.

tray
  The printed part that clicks into the ladders, one per bay. It carries the bay node, the drag chain and
  the drawer.

USB hub
  The chip on a DATA board that shares the bay node's USB between the ports.

VRACK
  The rack's supply on the row cables, normally 20 V.

VREF
  The pin of a DATA ×4 port's header that you wire to the board's I/O voltage. See [DATA ×4](pcbs/data-x4.md).

wires
  Links between the pins of boards in a DATA ×4 bay, closed by its pin matrix. See
  [Wires between boards](../use/wires.md).
```
