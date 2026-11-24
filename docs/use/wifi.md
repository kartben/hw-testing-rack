# Wi-Fi for the rack

The bay nodes and the power hub join your network over 2.4 GHz Wi-Fi, through one access point. That access
point's channel carries the USB/IP traffic of every board in the rack, so set it up as below.

## Set up the access point

- Use one access point, without mesh nodes or repeaters. A mesh moves the nodes between access points and
  channels, and drops them now and then.
- Set the channel to 6 or 11. Never use 1 or automatic: the USB hub of a DATA ×4 radiates at 2.400 GHz, at
  the bottom of channel 1. Of 6 and 11, pick the one your neighbours do not use. If your boards use
  Bluetooth, 11 is slightly better.
- Set the channel width to 20 MHz. A 40 MHz channel spills onto the next one.
- Turn 802.11b off, and set the lowest basic rate to 6 Mbit/s.
- If you can, keep the access point for the rack alone, so that other people's traffic stays off its channel.

Put the access point 1 to 3 m from the rack, behind it or beside it, at mid-height. Do not put it on top of
the rack or in front of the drawers. If your boards use Bluetooth, 2 to 3 m is better than 1 m.

Each node's antenna is under the drawer, at the back of the bay. If the pegs allow it, keep a large board off
the area above the antenna: from 70 to 100 mm behind the front edge of the board plate, and within 50 mm of its
left edge.

You give the rack the network's name and password when you build it: in the nodes' image, or in the shell of
each node and of the hub ([Build or download the firmware](../build/get-the-firmware.md)).

## How the nodes stay connected

The nodes and the hub keep their radio awake, with power save off, so that they answer without delay. This
costs about 0.2 W per node.

A short loss of the access point does not drop the connections. A node counts the link as lost only after 15 s
without beacons. `bay fault` lists each loss with its reason (`Link lost, reason N`). A node that has lost its
network tries again every 10 s, and its LED blinks orange meanwhile. The hub can still restart it through the
rack bus ([The rack's page](rack-page.md)).

## How many boards may flash at once

Up to 8 boards on one Wi-Fi channel can flash at once over USB/IP, each at full speed. Past that, the channel
is full: every flash slows down, and so does every request to a node. A camera stream takes about 4 % of the
channel's airtime. One to three streams fit beside 8 flashes.

The rack does not enforce this limit. Limit the number of parallel jobs in your CI, or use reservations
([Reserve a bay](reserve-a-bay.md)). [Specifications](../reference/specifications.md#sessions-clients-and-flashes-at-once)
gives the rack's other limits.

## Boards that use Wi-Fi or Bluetooth themselves

If a board in the rack uses Wi-Fi, put its network on the rack's channel. The board sits 3 cm from its node.
On another channel, the node hears the board louder than the access point, and the node's control requests
take seconds. Use the other channel only for boards away from the rack.

The rack's Wi-Fi lowers the throughput of a board's Bluetooth Low Energy link. To get the full throughput back,
mark the Bluetooth data channels that overlap the rack's Wi-Fi channel as bad in the board's firmware, with
`bt_le_set_chan_map()` in Zephyr. The rack does not tell the board which channel it uses, so your test must know
it.

## Move the rack to another network

The nodes and the hub keep their networks in flash. Change the network on each node and on the hub, one after
the other.

If the old network still works, add the new one to each node over telnet:

```console
$ telnet bay-b3.local
uart:~$ wifi cred add -s NewLab -k 1 -p secret
```

The hub's shell is only on its console USB-C port, in the front wall of the power box. Plug a laptop in and
type the same line there. Then switch the access points. Each PCB keeps trying every 10 s, and joins the new
network once the old one has gone.

If the old network is gone, you cannot reach the nodes over the network. For each node, do one of these:

- Build a node image with the new network in `wifi.conf` and flash it through the bay's front port with
  SERVICE on, as for a first flash ([Flash the hub and the nodes](../build/flash.md)). The bay stays closed, and
  the stored settings stay.
- Type the line above, then `wifi cred auto_connect`, in the node's shell on its UART test pads. The node has
  to come off its tray for this ([Take a bay apart](service-a-bay.md#take-a-node-off-its-tray)).

For the hub, use its console USB-C port as above. On a large rack, it is quicker to bring the old network
back for the move. Set up an access point with the old name and password, then add the new network over
telnet as above.

## Change the transmit power

The nodes and the hub transmit at 11 dBm, although the radio can give 20. With the access point 1 to 3 m away,
that leaves about 30 dB of margin, and the boards nearby hear less of the nodes.

```console
uart:~$ radio
uart:~$ radio 8
```

`radio` shows the power in use. `radio <dBm>`, from 2 to 20, sets it and saves it. Type it on a node over
telnet, or on the hub's console. A lower power helps the boards' Bluetooth. To change the default, set
`CONFIG_HWTR_NET_TX_POWER_DBM` when you build the firmware.
