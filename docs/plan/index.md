# How it works

A BitBunk rack is a stack of bays. Each bay holds your boards in a drawer, switches their power and puts
their USB on the network. This page shows how the parts fit together.

## A bay

```{figure} ../img/viewer/b3-drawer-out.jpg
:alt: Bay B3 with its drawer pulled out: a DATA ×4 standing at the back, four small boards on the plate, a USB cable to each

The 3D model: bay B3 with its drawer out. The DATA ×4 stands at the back, and each board has its own USB
cable to one of its ports. [Open the model](/viewer/?bay=B3&openbay=1&view=bay) to turn it round.
```

From the bottom up, a bay is made of these parts:

| Part | What it is |
|---|---|
| Tray | The printed floor of the bay. It slides into the side walls and clicks in. Its front has a USB-C port, a status LED and a SERVICE switch |
| Bay node | The PCB inside the tray that runs the bay: an ESP32-S3 on Wi-Fi, with Zephyr firmware |
| Drawer | It slides out 140 mm. The boards stay powered and connected while it is open |
| Board plate | A honeycomb plate. Clip-in pegs hold your boards on it, up to four small ones |
| DATA board | The PCB at the back of the drawer, with a USB-C port for each board. A DATA ×6 has six ports. A DATA ×4 has four, and pin headers for wires between the boards |
| Camera pod | Optional: a camera and a light under the bay's ceiling, looking down at the boards |

A cable of eight wires, the DATA lead, runs from the bay node to the DATA board through a drag chain under
the drawer. Each board plugs into the DATA board with its own short USB cable.

In place of the plate, a bay can have a slot bin, which holds up to six boards standing on edge. In place of
the drawer, a bay can have a sled, with no drag chain. You unplug the board before you pull the sled out.

## From a bay to a rack

You choose how many bays your rack has: one bay on a desk, or up to four rows of as many columns as the power
allows. You can add bays later. See [Choose your rack's size](choose-your-rack.md).

Neighbouring bays share their side walls, called ladders, so you can add a column or a row. The rows are
tilted by 20° so that the boards and the bay labels face you.

Each bay is named after its place: the row letter, counting from the bottom, then the column number. The third
bay of row B is B3. Its bay node answers on the network as `bay-b3.local`, with nothing to configure. See
[Bays, ports and addresses](../use/names.md).

The power box sits under bay A1. It holds the power hub, which switches each row on and off. A row cable
carries power and a CAN bus from the power box to each bay node of the row in turn. The hub has four row
outputs, so a rack has at most four rows.

## Where a board's USB goes

The DATA board has a USB hub that joins its ports. The DATA lead carries the hub's USB to the bay node. There,
two USB switches decide which host gets the boards.

```{raw} html
:file: ../img/diagrams/usb-path.svg
```

By default the bay node's ESP32-S3 is the boards' USB host. It shares each board over the network with
USB/IP. On a Linux machine, `usbip attach` makes the board's debug probe and serial port appear as local
devices. See [USB/IP and flashing](../use/usb-and-flashing.md).

Over USB/IP, the boards of a bay share one full-speed USB link, 12 Mbit/s. That is enough for a debug probe, a
serial console or DFU. A large image sent to a mass-storage bootloader is slower.

In classic mode, a laptop plugged into the bay's front port takes the boards instead. It sees them at
high speed, as if they were on your desk. The bay node still controls their power. See
[Front port and classic mode](../use/front-port.md).

Some USB devices do not work through the rack: see [Limitations](../reference/known-limitations.md).

## Where the power comes from

The whole rack runs from one 100 W USB-C PD charger on a 5 A cable. It plugs into the power box. No mains
voltage enters the rack.

The power hub asks the charger for 20 V and passes it to the rows. Each bay node passes it on to its DATA
board. The DATA board makes 5 V for your boards, and switches and measures each port. A port gives a board
about 0.5 A. No power reaches a drawer until the bay node's firmware switches it on.

The hub shares the charger's power between the bays, so the more columns you have, the less each bay gets.
With four bays in a row, each bay gets 5.4 W for its DATA board and its boards. A port that would go over the
bay's share waits until there is room. See [Power budget and queued ports](../use/power-budget.md).

## One file describes your rack

[config/rack.yaml](../../config/rack.yaml) describes your rack: its rows and columns, its dimensions, which
bays have a camera and which board sits in each bay. `tools/build.py` makes the printed parts, the 3D model
and the bill of materials from it. When you change a row or a column, run the tool again and every part
follows. See [Choose your rack's size](choose-your-rack.md#edit-config-rack-yaml-and-regenerate).

The file comes with an example: a rack of 12 bays, four columns by three rows. [The 3D model](/viewer/) shows
this example. Most pages of this site use its bay B3, a DATA ×4 bay with four small boards.
