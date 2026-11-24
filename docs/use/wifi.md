# Wi-Fi in the rack

Every bay node and the power hub reach the network over 2.4 GHz Wi-Fi, through one access point that you set
up for the rack: one channel, 6 or 11, fixed, 20 MHz wide. That channel carries the USB/IP traffic of every
board in the rack, and it is shared with the boards' own radios a few centimetres away.

:::{status} simulated
The nodes' radio settings ran on the XIAO ESP32-S3 and M5Stack CoreS3 stand-ins, with a home access point.
The capacity and Bluetooth figures come from two simulations, an ns-3 model and a BabbleSim model, of racks of
8 and 16 bays with four boards a bay; the default rack has 12 bays, most of them with a DATA ×6. No rack has
been on the air. [What exists today](../plan/status.md#status-wifi).
:::

## One access point, one fixed channel

- One channel for the whole rack, 6 or 11, never 1. A DATA ×4's USB hub runs a 480 MHz PLL whose fifth
  harmonic is 2.400 GHz, at the bottom of channel 1. Pick the one where no neighbour is heard. For the boards'
  Bluetooth, 11 is slightly better: it leaves the three advertising channels clear.
- Fixed, not chosen automatically.
- One access point, without mesh nodes or repeaters. On the bench a home mesh dropped its stations now and
  then (reason 200, beacons missing; reason 6, sent away at an RSSI of −46 dBm), the node and a PC on another
  of its access points at the same second, and moved the node from channel 6 to 2.
- 20 MHz wide on 2.4 GHz: a 40 MHz channel spills onto the next one.
- 11b off, basic rates from 6 Mbit/s: its beacons cost 2 to 3 % of the air, and broadcasts go faster.
- Dedicated to the rack, if you can: it keeps other people's traffic off the rack's channel.

Nodes 17 cm apart on neighbouring channels block each other; on one channel they take turns. The network's
name and password go into the nodes' image or their shell, and into the hub's shell, during the build
([Build or download the firmware](../build/get-the-firmware.md)); to change them later, see
[Move the rack to another network](#move-the-rack-to-another-network).

## Where to put it

1 to 3 m from the rack, behind it or beside it, at mid-height: not on top of the rack, not in front of the
drawers. Each node's antenna is on the PCB's rear edge, in the tray under the drawer, flat and pointing to the
back of the bay: a node looks out through the back and the sides of its bay, and above it are its drawer and
its boards.

For the boards' Bluetooth, 2 to 3 m is better than 1 m: in the BabbleSim model, the boards of a bay being
flashed kept 79 % of their throughput with the access point 1 m away, 88 % at 2 or 3 m.

Keep a large board off the left-rear part of the plate when its pegs allow, 70 to 100 mm from the plate's
front edge and within its left 50 mm: that is right over the antenna.

## What the nodes do by themselves

Each node, and the hub, sets its radio before every connection:

- No power save: the radio stays awake. In modem sleep the access point holds every frame for the node
  until the next DTIM beacon: the bench XIAO answered a ping from a wired PC in 174 ms on average, up to
  350 ms, against 13 to 16 ms awake. It costs about 0.2 W a node.
- 20 MHz channels (HT20).
- 11 dBm of transmit power instead of the radio's 20 dBm ([Transmit power](#transmit-power)).
- A lost link is held: 15 s without the access point's beacons before the link counts as lost, then up to
  30 s with the address kept while the station reconnects. The connections stay open; a transfer in flight
  still has to end within its client's timeout. `bay fault` lists each loss with its reason
  (`Link lost, reason N`).

A node that loses its network tries again every 10 s. Meanwhile its LED blinks orange, and the rack bus
still carries it: the rack's page shows the bay with no address, and the hub can still power-cycle, reset or
restart it ([Rows and the rack's page](rack-page.md)).

A XIAO stand-in needs its antenna clipped on: without it the node sees the access point at about −90 dBm and
every connection fails with `Connection timeout`. Keep it 30 to 50 cm from a USB 3 hub, next to which it kept
losing its network (`AP not found`).

## How many boards may flash at once

Eight per channel. In the ns-3 model of one channel:

- 8 boards flashed at once over USB/IP each get their full 362 kB/s, with the air 70 % busy and control
  requests under 15 ms;
- between 8 and 12 the channel saturates, at about 3.2 MB/s of USB/IP in all: 268 kB/s a node at 12, 166 kB/s
  at 16, with control requests 10 to 15 times slower;
- with four boards' own Wi-Fi and a neighbour on the channel, 18 Mbit/s in all, 8 flashes get 160 kB/s each.

Contention fills the channel: every flashing node keeps acknowledgements, USB replies and console bytes
queued. A camera stream takes about 4 % of the air; one to three fit beside 8 flashes. Transmit
power and the access point's distance change nothing here, within 1 to 3 m.

Nothing in the rack enforces the eight: whatever schedules the jobs must, with a semaphore in the CI or with
reservations ([Reserve a bay](reserve-a-bay.md)). The figure sits with the rack's other limits in
[Specifications](../reference/specifications.md#sessions-clients-and-flashes-at-once). Past eight, the study
proposes a second access point on the other channel for half the rack (two channels of 8), or nodes on a
cable, which no PCB offers ([A wired node](../wired-node-mcu.md)). Single flashes and their speed are on
[USB/IP and flashing](usb-and-flashing.md), the whole study on
[How much one Wi-Fi channel carries](../wifi-capacity-ns3.md).

## Boards that use Bluetooth or Wi-Fi themselves

A board's own Wi-Fi inside a bay goes on the rack's channel. On the other channel, 3 cm from its node, it
leaks more into the node than the access point's signal does, neither defers, and the node's control requests
take seconds; on the same channel they take turns. A board's network away from the rack, the lab's access
point for the boards or another bench, goes on the other channel.

Bluetooth Low Energy, in the BabbleSim model of the rack:

- A busy rack costs throughput, not the link: no connection dropped and none failed to set up. Throughput fell
  by up to 9 % with the rack idle, 10 to 13 % while the boards' own node was being flashed, 16 to 30 % under
  stress.
- The node's transmit power is what counts when the rack is idle: 92 % of the throughput at 20 dBm, 95 % at
  11, 97 to 98 % at 8, 100 % at 2. The Wi-Fi channel and the number of nodes hardly matter.
- The lever that works is in the board's firmware: its host's channel classification, `bt_le_set_chan_map()`
  in Zephyr. With the data channels under the rack's Wi-Fi channel marked bad, the link went back to its
  throughput without Wi-Fi in every case.

A test that needs the full link marks those channels itself; the rack does not tell it which Wi-Fi channel it
uses today. A *radio-quiet* mode, `radio quiet <s>`, which would drop a node to 2 dBm and hold its other
boards' USB/IP traffic for the length of a test, is planned and not written. The whole study:
[Rack Wi-Fi and the boards' Bluetooth](../wifi-coexistence.md).

## Move the rack to another network

*Worked out from the two firmware READMEs and the shells' commands; nobody has done it yet.*

Each node and the hub keep their networks in flash, and an image built with `wifi.conf` adds the one it
carries. Either way, every node of the rack and the hub need the change, one after the other.

**The old network still answers.** Add the new one to each node from your machine, over telnet:

```console
$ telnet bay-b3.local
uart:~$ wifi cred add -s NewLab -k 1 -p secret
```

The hub's shell is on its console USB-C only, the one place its Wi-Fi can be set: plug a laptop into the
power box's front wall and type the same line there. Then switch the access points. Each PCB keeps trying,
every 10 s, and joins the new network when the old one has gone.

**The old network is gone.** A node can no longer be reached over the network, and its shell is on its UART
test pads, under the node: its tray comes out to reach them
([Take out a tray, a node or a DATA board](service-a-bay.md)). The other way needs no tray: build a node image
with the new network in `wifi.conf` and flash it through the bay's front port with SERVICE on, as for a first
flash ([Flash the hub and the nodes](../build/flash.md)). A flash over USB leaves the stored settings in place.
The hub's console USB-C still works as above. For twelve bays, either way is twelve bays of work; an access
point that takes the old network's name and password for the time of the move gets you back to the first case.

## Transmit power

11 dBm by default, for the nodes and the hub, where the radio could give 20: with the access point 1 to 3 m
away that still leaves about 30 dB of margin, and the boards a few centimetres away hear much less of the
nodes. On the bench XIAO, at an RSSI of −49 dBm, the status page loaded no slower at 11 or 8 dBm than at 20.

```console
uart:~$ radio
uart:~$ radio 8
```

`radio` shows the power the radio really uses; `radio <dBm>`, from 2 to 20, sets it and saves it, on a node
over telnet or on the hub's console. `CONFIG_HWTR_NET_TX_POWER_DBM` sets the default at build time. The
Bluetooth study proposes 8 dBm as the default; the firmware has not taken it. The full command list:
[Bay node shell](../reference/node-shell.md).
