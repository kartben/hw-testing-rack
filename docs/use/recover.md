# Recover a node or the hub

You can always flash a bay node or the power hub again over USB. A node takes its firmware through its bay's
front port, and the hub through the console USB-C port on the power box. Only the last resort for a node, its
UART pads, needs the node out of the rack.

## Start with the mildest fix

First read what the rack tells you ([Troubleshooting](troubleshooting.md)). Then try these steps in order:

1. Wait. A node that crashes restarts by itself. The reason stays in `bay fault` and in `last_fault` of
   `/api/status`.
2. Restart the node through the hub, which reaches it over the rack bus even without Wi-Fi:
   `python tools/bayctl.py hub node B3 reboot` with the admin key, or `hub node B3 reboot` on the hub's console.
3. Power-cycle its row, from the rack's page or with `bayctl row B cycle`. Every bay of the row restarts.
4. Flash it again over USB ([A node whose firmware is stuck](#a-node-whose-firmware-is-stuck)). It keeps its
   settings.
5. Erase its flash and flash it again ([What a node and a hub remember](#what-a-node-and-a-hub-remember-and-how-to-wipe-it)).
   It forgets its settings.

## A node on the rack bus but not on Wi-Fi

The rack's page shows the bay with no address, and the bay's LED blinks orange. The node tries again every
10 s, so check the access point first ([Wi-Fi for the rack](wifi.md)). If the node has the wrong network name
or password, do one of these:

- build a node image with your network in `wifi.conf`
  ([Put your Wi-Fi in the node's image](../build/get-the-firmware.md#put-your-wi-fi-in-the-nodes-image)) and
  flash it through the front port, as below; or
- type `wifi cred add -s MyLab -k 1 -p secret`, then `wifi cred auto_connect`, in the node's shell on its UART
  pads, with a 3.3 V USB-UART adapter at 115200 8N1. The pads are under the node
  ([Take a node off its tray](service-a-bay.md#take-a-node-off-its-tray)).

## A node whose firmware is stuck

Flash the node through the front port of its bay, with the bay closed
([Flash the hub and the nodes](../build/flash.md)):

1. Slide **SERVICE** on. The bay's LED turns yellow.
2. Plug a laptop into the **PC** port, and run `west flash -d build-bay`.
3. Slide SERVICE off.

If the LED does not turn yellow, the firmware has not let go of the USB port. Start the node's ROM loader by
hand instead:

1. Slide SERVICE on and plug the laptop into the PC port.
2. Hold the node's **BOOT** and tap its **RESET**, with a pin through the two holes in the drawer's floor.
3. Run `west flash -d build-bay`, release BOOT, and slide SERVICE off.

The last resort is the UART pads TX, RX and GND, under the node. Use a 3.3 V USB-UART adapter, and hold BOOT
while the node resets.

```{figure} ../img/pcbs/bay-node-bottom.jpg
:class: bb-screenshot
:alt: KiCad render of the bottom face of the bay node, with the names of its test pads
:width: 55%

KiCad render of the bay node v1.0, bottom face, rear edge up. The UART pads carry their names.
```

## settings unavailable (-45)

A module that ran other firmware before may still hold that firmware's data where the settings go. The boot
log then says:

```text
settings unavailable (-45): defaults only; storage partition not NVS: west flash --erase
```

Until you erase the flash once, the PCB keeps none of your settings. Erase it through the same port you flash
it through. For a hub, use `-d build-hub`. On a PCB you have set up, the erase also wipes everything in the
tables at the end of this page.

```console
$ west flash -d build-bay --erase
```

## A hub that does not answer

A hub without Wi-Fi still powers the rows and runs the rack bus. Only its page and its API are gone.

Plug a laptop into the hub's console USB-C port, in the front wall of the power box. The port carries the hub's
shell at 115200 baud: try `hub status` and `hub events` first.

To flash the hub again, use the same port. You need no button, and the box stays closed:

```console
$ west flash -d build-hub
```

The port also powers the hub's controller, so you can flash a hub with no charger. The rows stay on while the
hub restarts.

If the flash fails, press **BOOT** and **RESET** with a pin through the BOOT and RST holes in the lid. The last
resort is the UART pads under the hub, with the lid off.

## A lost admin key

First look for a browser where a bay's page still says *admin*. There, **Copy key** in *Manage access* gives
you the key back.

Otherwise, clear the key on each PCB by hand, then claim the PCB again
([Claim the hub and the nodes](access.md#claim-the-hub-and-the-nodes)):

| | Clear the key | What else goes |
|---|---|---|
| A bay node | hold BOOT for 10 s, or `bay access reset` on its UART pads | its access rules and reservations |
| The hub | hold BOOT for 10 s, or `hub access reset` on its console USB-C | nothing |

Once the nodes are claimed again, send them their rules with `python tools/bayctl.py access push`.

## A lost signing key

MCUboot boots only images signed with the key it was built with. If you built the rack with your own signing
key and lost it, the PCBs refuse every image you build. A PCB that shows a *test key* tag beside its version
uses MCUboot's public test key, so you have lost nothing.

To recover, make a new key ([Sign with your own key](../build/get-the-firmware.md#sign-with-your-own-key)).
Then flash every PCB once over USB, as above. `west flash` writes MCUboot and the firmware together, and keeps
the settings. Keep the new key outside the repository, and keep a backup of it.

## What a node and a hub remember, and how to wipe it

These settings survive a restart, a power cut and an update.

| A bay node keeps | Set with |
|---|---|
| its id, and so its name `bay-<id>.local` | `bay id b3` |
| classic mode forced | `bay mode classic`, the page |
| the AUX UART's settings | `bay aux 115200 8N1`, the page |
| that a hub gave it a place | the hub |
| the admin key and the access rules | a claim, `bayctl access push`, the page |
| the camera's settings | `bay camera set`, the page |
| each port's board target | the page, `bayctl import lab` |
| its Wi-Fi networks and transmit power | `wifi cred add`, `radio <dBm>` |
| the result of its last update | an update |

| The power hub keeps | Set with |
|---|---|
| its id, and so its name `rack-<id>.local` | `hub id lab1` |
| which rows are on, and the shed order | `hub row B on`, `hub shed DCBA`, the page |
| the budget's margin and cap | `hub budget margin 10`, `hub budget cap 90` |
| the admin key, its Wi-Fi, its last update | as on a node |

In a DATA ×4 bay, the node also keeps the analyzer image ([Logic analyzer](logic-analyzer.md)). A restart
loses the reservations, the ports you switched off, the wires and the hub's events.

There is no factory reset. `west flash --erase` wipes everything in the tables and writes the firmware again.
On a PCB that you have set up, [you cannot undo it](../build/index.md#erase). To clear less, use the commands in
the tables.
