# Glossary

"Board" alone is always your development board. The rack's own electronics go by their names: the bay node,
the power hub, the DATA board (a DATA ×6 or a DATA ×4) and the camera pod. Together they are "the PCBs".

## "Board" and "PCB"

The firmware, the tools and the design documents were written before that rule. A screen, a command or a file
may use another word for the same thing:

| These pages say | A screen or a file may say | Where |
|---|---|---|
| board | DUT, board under test | the rack's page (`DUT off`, `DUT fault`), the bay's page (`DUT VBUS fault`), the bay node's shell and its metrics (`bay_dut_*`) |
| port, written B3.2 | slot, sub-slot | `bayctl`'s messages, the *Sub-slots* boxes of the bay page's reservation dialog, `"slot"` in `/api/ports` and `/api/boards` |
| reserve, reservation | lease | `bayctl lease`, `POST /api/lease` |
| the PCBs | boards | [electronics/](../../electronics/), the design documents, the fab files |
| DATA ×4 | DATA ×4 v2, the v2, DATA-4x-logic | the design documents, `x4: v2` in [config/rack.yaml](../../config/rack.yaml) |
| the module's one-time fuse | eFuse | `espefuse.py` and Espressif's documents |

Read from [firmware/power-hub/web/index.html](../../firmware/power-hub/web/index.html),
[firmware/bay-node/web/index.html](../../firmware/bay-node/web/index.html),
[firmware/bay-node/src/web.c](../../firmware/bay-node/src/web.c) and [tools/bayctl.py](../../tools/bayctl.py).

## A to Z

The states a page or a command shows (`waiting`, `shed`, `queued`, `device ready` and the others) are on
[States and error messages](states-and-messages.md), each with what it means.

```{glossary}
AUX
  The bay node's connector J5: a UART, a RESET line and a BOOT line at 3.3 V levels, wired by hand to one
  board that has no USB serial of its own. A DATA board has no AUX UART of its own: a board on a DATA
  port uses its own USB as its console, and the bay node's AUX can still be wired by hand to one of them.
  ([Bay node › J5, AUX](pcbs/bay-node.md#j5-aux), [tools/bayctl.py](../../tools/bayctl.py))

bay
  One place of the grid, named by its row letter and its column number: B3 is row B, third column from the
  left. It holds a tray, a bay node, a drawer and a DATA board. How every name is formed:
  [Bays, ports and addresses](../use/names.md). ([config/rack.yaml](../../config/rack.yaml))

bay node
node
  The rack's PCB in each tray, one per bay: an ESP32-S3 that switches and meters the DATA lead's supply,
  exports the boards' USB over USB/IP and serves the bay's page. In the hub's output a "node" is a bay.
  ([electronics/bay-node/design.py](../../electronics/bay-node/design.py))

bayctl
  The command-line tool that drives the rack from a laptop or a CI host. It is run from a checkout, as
  `python tools/bayctl.py`. ([tools/bayctl.py](../../tools/bayctl.py))

board
  Alone, your development board: what the rack holds and tests. The rack's own are {term}`PCBs <PCB>`.

board plate
plate
  The printed honeycomb plate in a drawer, 134.5 × 159.4 mm with 177 hexagonal holes, on which pegs hold
  any board. ([mechanical.md](../mechanical.md))

board target
  What a bay node remembers about the board on a port, for twister: its Zephyr target, its west runner, its
  probe id and its console. Set on the bay's page: [Board targets](../use/board-targets.md).
  ([firmware.md](../firmware.md))

brace
  The printed X screwed behind every bay and behind the base. Each diagonal is 0.25 mm short, so the X is
  taut once its fourth screw is in. ([mechanical.md](../mechanical.md))

busid
  USB/IP's name for a device on a bay node: `1-1.` and the port of the DATA board's USB hub. On a DATA ×4
  that port is the USB-C's number; on a DATA ×6 it is not. ([Bays, ports and addresses](../use/names.md#usbip-busids-on-a-data-6-and-on-a-data-4))

camera pod
  The printed holder under a bay's ceiling with an Arducam Mega, four white LEDs and the pod's own PCB.
  ([electronics/camera-pod/design.py](../../electronics/camera-pod/design.py))

claim
  To give a bay node or the power hub its admin key, the 32-byte key that signs every admin request
  afterwards. A press on the PCB's BOOT button confirms it. ([Access rules and security](../use/access.md))

classic mode
  The boards' USB handed to a laptop on the bay's front port, as on a desk, in place of USB/IP. The bay node
  still switches and meters their power. ([electronics/bay-node/design.py](../../electronics/bay-node/design.py))

co-processor
  The RP2350B on a DATA ×4. It has no flash: the bay node loads an image into its RAM at each power-up,
  today the logic analyzer. ([firmware.md](../firmware.md))

cradle
  The printed holder in which a DATA board stands at the back of a drawer, its USB-C in the port wall's slots.
  ([mechanical.md](../mechanical.md))

DATA board
  The rack's PCB that stands at the back of a drawer and carries the USB-C ports the boards plug into: a
  DATA ×6 or a DATA ×4. ([config/rack.yaml](../../config/rack.yaml))

DATA lead
  The 8-wire JST PH lead from a bay node (J7) through the drag chain to the DATA board: 20 to 28 V, USB and
  I²C. A "same direction" lead; its pins are on [Cables and pinouts](cables.md).
  ([config/rack.yaml](../../config/rack.yaml), [firmware.md](../firmware.md))

DATA ×4
  The DATA board for bays whose boards need wires between them: four USB-C ports, a pin header beside
  each, a pin matrix and a co-processor. One PCB, two assemblies: with the matrix and the co-processor
  (DATA-4x-logic), or without them (the base, DATA-4x).
  ([electronics/data-port-x4/design.py](../../electronics/data-port-x4/design.py))

DATA ×6
  The default DATA board: six USB-C ports, each switched and metered, and nothing else.
  ([electronics/data-port-x6/design.py](../../electronics/data-port-x6/design.py))

dense bay
  A bay whose boards stand on edge in a slot bin, up to six on a DATA ×6. Row C of the default rack.
  ([config/rack.yaml](../../config/rack.yaml))

drag chain
  The 7 × 7 mm cable chain that lies flat in the plenum and carries the DATA lead, so that a board stays
  connected while its drawer slides out. ([mechanical.md](../mechanical.md))

drawer
  The printed part that slides 140 mm out of its tray along the slope, with the board plate in front and
  the DATA board behind the port wall. ([mechanical.md](../mechanical.md))

DUT
  Device under test: the firmware's word for a {term}`board`. The rack's page shows `DUT off` and
  `DUT fault`, the metrics are named `bay_dut_*`.
  ([firmware/power-hub/web/index.html](../../firmware/power-hub/web/index.html))

eFuse
  The protection chip (TPS26600) that switches a supply and limits its current: one per row on the power
  hub, at 1.6 A, and one on each bay node's DATA lead, at about 1.76 A. Never the ESP32's: that one is the
  {term}`one-time fuse`. ([power.md](../power.md), [firmware.md](../firmware.md))

(empty port)
  In `bayctl list`, a DATA board's port with no board target, no USB device and no entry in the lab file.
  ([tools/bayctl.py](../../tools/bayctl.py))

fascia
  The tray's front wall, under the drawer: the front USB-C port, the status LED's window and the SERVICE
  switch. ([mechanical.md](../mechanical.md))

feed
  The row cable from the power box to the first bay node of a row. ([Cables and pinouts](cables.md#row-cable-jumpers-and-feeds))

grant
  The power the hub allows a bay on its DATA lead, sent every second over the rack bus: 5.4 W a bay with
  twelve bays on a 100 W charger. A port goes on only if the bay stays inside it.
  ([rack-protocol.md](../rack-protocol.md), [Power budget](../use/power-budget.md#who-decides-how-much))

hub
  Alone, the {term}`power hub`. The chip that fans USB out on a DATA board is always written
  {term}`USB hub`.

jumper
  A short row cable, 120 mm, from one bay node to the next. Jumper wires are something else: the Dupont
  leads from a DATA ×4's pin header to a board's pins. ([Cables and pinouts](cables.md#row-cable-jumpers-and-feeds))

ladder
  A printed side wall between two columns, one per row, shared by the bays on both sides. The trays slide
  into its grooves. ([mechanical.md](../mechanical.md))

lease
  The API's and `bayctl`'s word for a reservation: one address holds a bay or some of its ports for 10 s to
  24 h. These pages say "reserve". ([Reserve a bay](../use/reserve-a-bay.md))

native_sim
  Zephyr's build for a PC. The firmware's tests run on it, against emulated PCBs.
  ([firmware.md](../firmware.md))

not in CI
  In `bayctl list`, a board kept out of twister's hardware map: `ci: false` in the lab file, or the map
  switch off on the bay's page. ([tools/bayctl.py](../../tools/bayctl.py))

not the board its target was saved for
  In `bayctl list` and `bayctl hwmap`, a port whose USB device is another one than the device its board
  target was saved for. ([tools/bayctl.py](../../tools/bayctl.py))

one-time fuse
  The ESP32-S3 module's `DIS_USB_OTG_DOWNLOAD_MODE` bit, burnt once on each bay node and power hub that
  goes into a rack. It cannot be unburnt. Espressif calls it an eFuse; these pages keep that word for the
  protection chip.
  ([Flash the hub and the nodes](../build/flash.md#the-modules-one-time-fuse))

PCB
  One of the rack's own five: the power hub, the bay node, the camera pod, the DATA ×6 and the DATA ×4.
  ([The five PCBs](pcbs/index.md))

peg
  A printed part that clips into a hole of the board plate to hold a board: a stop, a cam on its base, a
  pin through a mounting hole, or a bobbin for spare cable. ([mechanical.md](../mechanical.md))

plenum
  The 23 mm space inside a tray, under the drawer, that hides the bay node and the drag chain.
  ([mechanical.md](../mechanical.md), [tools/rackcfg.py](../../tools/rackcfg.py))

port
  One USB-C of a DATA board, with its own power switch and current meter, numbered from 1 at the left as
  seen from the boards. With its bay: B3.2. ([mechanical.md](../mechanical.md))

port block
  In a sled bay, the back of the drawer as a separate part locked into the tray: the port wall and the
  DATA board stay behind when the sled comes out. ([mechanical.md](../mechanical.md))

POS
  The position wire of the row cable. The hub raises it on a row and each bay node passes it on once it
  has its address: that is how a bay learns it is C3. ([can.md](../can.md))

power box
  The printed box in the base, under bay A1, that holds the power hub. ([power.md](../power.md))

power hub
  The rack's one PCB in the power box: it negotiates with the USB-C charger, switches each row through an
  eFuse and runs the rack bus. It is not a USB hub. ([power.md](../power.md))

queued
  A port asked to switch on "when available": it waits its turn and goes on by itself once the bay's
  grant has room. ([Power budget](../use/power-budget.md#a-port-that-waits-a-port-that-is-queued))

rack bus
  The CAN bus and the POS wire that run in the row cables, between the power hub and the bay nodes.
  ([can.md](../can.md))

reserve
  To hold a bay, or some of its ports, for one address for a while: [Reserve a bay](../use/reserve-a-bay.md).
  The API and `bayctl` say {term}`lease`.

row
  A line of bays, lettered from the bottom (A, B, C), fed by one of the hub's four outputs and switched as
  one. ([config/rack.yaml](../../config/rack.yaml))

row cable
  The 6-wire JST PH cable that carries VRACK, CAN and POS from the hub along a row, bay node to bay node:
  a feed, then jumpers. ([can.md](../can.md))

same direction
  Sellers' name for a ready-made JST PH lead whose two plugs show the same face when it lies flat: pin n
  at one end is pin N + 1 − n at the other. The row cable, the DATA lead and the camera lead are all of
  that kind. Not every seller uses the name that way: ring each lead out. ([Cables and pinouts](cables.md),
  [Make the row cables](../build/row-cables.md#ring-every-cable-out-the-bought-leads-too))

SERVICE
  The slide switch on the fascia that hands the front USB-C port to the bay node itself, to flash it.
  ([electronics/bay-node/design.py](../../electronics/bay-node/design.py))

shed
  To switch off, for lack of power, something that comes back by itself. The hub sheds a row when the rows
  draw more than the charger's contract leaves them; a bay node sheds the port it switched on last when
  the bay goes over its grant. ([power.md](../power.md), [Power budget](../use/power-budget.md#when-a-bay-is-over-its-share))

simulated node
  `dev_server.py`: the bay's real web page and API on a model of the bay node in Python, with no hardware.
  The power hub has one too. ([firmware/bay-node/web/dev_server.py](../../firmware/bay-node/web/dev_server.py))

sled
  A drawer without a drag chain: unplug the board's cable, then pull. A fixed bay is a sled bay with the
  sled screwed in place. ([mechanical.md](../mechanical.md))

slot
  In `bayctl` and in the API, what holds one board: a port of a DATA board, or the bay itself on a node
  that serves a single board. ([tools/bayctl.py](../../tools/bayctl.py))

slot bin
  The printed bin that takes the plate's place in a dense bay: six lanes, lane k for the DATA ×6's port
  k, in which boards stand on edge. The sources also call it the "porte-revues".
  ([mechanical.md](../mechanical.md))

stand-in
  A bought ESP32-S3 board that runs the bay node's or the hub's firmware on the bench in place of a PCB:
  for most of what has been run, an M5Stack CoreS3 or a XIAO ESP32-S3. ([bench.md](../bench.md))

sub-slot
  `bayctl`'s and the firmware's word for a port named with its bay: B3.2 is bay B3, port 2.
  ([tools/bayctl.py](../../tools/bayctl.py))

tray
  The printed part that slides into the ladders' grooves and clicks in, one per bay. It carries the bay
  node, the drag chain and the drawer, and its underside is the ceiling of the bay below.
  ([mechanical.md](../mechanical.md))

USB hub
  The USB2517I chip on a DATA board, between the bay node's one USB port and the board's ports.
  `usbip list` never shows it. ([Bays, ports and addresses](../use/names.md#usbip-busids-on-a-data-6-and-on-a-data-4))

v2
  In the design documents, "DATA ×4 v2" is the DATA ×4 these pages describe: its silkscreen reads v1.0.
  The "v1" it replaced was never made. ([electronics.md](../electronics.md))

VRACK
  The rack's supply rail on the row cables: the charger's own output, 20 V with the default charger.
  ([power.md](../power.md))

VREF
  The pin of a DATA ×4 port's header that you wire to the board's I/O voltage. It sets the level of that
  port's eight pins. ([DATA ×4](pcbs/data-x4.md#the-pin-header-and-vref))

waiting (port)
  A port that is wanted on and kept off until its bay's grant has room, or that was shed. It comes back
  in its turn. ([Power budget](../use/power-budget.md#a-port-that-waits-a-port-that-is-queued))

waiting (row)
  A row that is wanted on and waits for the charger's contract: `waiting for PD` on the rack's page.
  ([firmware/power-hub/web/index.html](../../firmware/power-hub/web/index.html))

wires
  Links between pins of the boards of a DATA ×4 bay, closed by the pin matrix from the bay's page or with
  `bayctl wire`: any of a port's pins P1 to P8 on one of eight shared buses, A to H.
  ([firmware.md](../firmware.md))
```
