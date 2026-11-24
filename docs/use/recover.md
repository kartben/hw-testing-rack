# Recover a node or a hub that does not answer

A bay node and the power hub can always be flashed again over USB: the node through its bay's front port with
SERVICE on, the hub through the console USB-C on the power box. Only the node's last resort, its UART test
pads, needs the node out of the rack.

:::{status} written
These procedures come from the firmware's design documents and code. None has been run on a v1.0 PCB. On the
bench stand-ins: `settings unavailable (-45)` was met on an M5Stack StampS3, whose reused flash held another
firmware's data (the erase below is the firmware's own advice for it), and a claim was confirmed with the
BOOT button of a XIAO ESP32-S3.
[What exists today](../plan/status.md#firmware-feature-by-feature).
:::

## Start with the least drastic

Read first what the rack says ([Troubleshooting](troubleshooting.md)), then go down this list:

1. Wait. A fatal error restarts a node by itself: the bay must come back on its own. The reason, the
   thread and the warnings before it survive the restart, in `bay fault`, in `bay status` (`restarted: …`) and
   in `last_fault` of `/api/status`, until the node next loses power.
2. Restart it through the hub. A node that is on the rack bus obeys the hub with or without Wi-Fi:
   `hub node B3 reboot` on the hub's console, or `python tools/bayctl.py hub node B3 reboot` with the admin key.
3. Power-cycle its row from the rack's page, `hub row B cycle`, or `bayctl row B cycle`. Every bay of
   the row restarts.
4. Flash it again over USB, which keeps what it has stored: the sections below.
5. Erase it, which forgets everything it has stored: the last section.

## A node that is on the rack bus but not on Wi-Fi

The rack's page shows the bay at its place with no address, and its LED blinks orange, slowly. The hub can
still identify it, reset or power-cycle its boards and restart it ([Rows and the rack's page](rack-page.md));
the node only lacks its page, its USB/IP and its telnet shell. It retries its networks every 10 s, so look at
the access point first ([Wi-Fi in the rack](wifi.md)).

Wrong or missing credentials are mended one of two ways:

- Its shell on the UART test pads, through a 3.3 V USB-UART adapter at 115200 8N1, then
  `wifi cred add -s MyLab -k 1 -p secret` and `wifi cred auto_connect`. The pads are on the node's underside:
  its tray comes out and the node off its standoffs
  ([Take out a tray, a node or a DATA board](service-a-bay.md)).
- A new image with the network built in, `wifi.conf`, flashed through the front port with SERVICE on, as
  below. The bay stays closed, and what the node has stored stays too
  ([Build or download the firmware](../build/get-the-firmware.md#put-your-wi-fi-in-the-nodes-image)).

The front port in SERVICE carries flashing and JTAG only: the node has no shell there.

## A node whose firmware is wedged

The usual flash goes through the bay's fascia, bay closed: slide **SERVICE** on, plug a laptop into the **PC**
port, `west flash -d build-bay`, SERVICE off ([Flash the hub and the nodes](../build/flash.md)). It relies on
the running firmware to hand the ESP32-S3's one USB PHY to the USB-Serial-JTAG; the bay LED turns yellow when
it has.

Firmware that takes the PHY for its USB host and crashes before letting it go never turns the LED yellow. Then
start the ROM loader by hand:

1. SERVICE on, the laptop plugged into the PC port.
2. Hold the node's **BOOT** and tap **RESET**. Both are reached with a pin through the two holes in the
   drawer's floor and the board plate, drawer in; or with the drawer pulled out, where BOOT is clear and RESET
   sits partly under the drawer's left ledge, under a notch in it. Instead of RESET, keep BOOT held while the hub
   power-cycles the row: the row's other bays restart too.
3. `west flash -d build-bay`, then release BOOT, and SERVICE off.

Where the buttons are on the PCB: [LEDs, buttons and switches](../reference/leds-and-buttons.md).

The last resort is the UART: the pads TX, RX and GND on the node's underside, with a 3.3 V USB-UART adapter,
BOOT held at reset. The node comes off its standoffs for it.

```{figure} ../img/pcbs/bay-node-bottom.jpg
:class: bb-screenshot
:alt: KiCad render of the bottom face of the bay node, with the names of its test pads
:width: 55%

KiCad render of the bay node v1.0, bottom face, turned over left to right, rear edge up: the UART pads carry
their names.
```

## settings unavailable (-45)

A module that ran other firmware may hold something else where the settings live. The boot log then says:

```text
settings unavailable (-45): defaults only; storage partition not NVS: west flash --erase
```

and nothing that the shell sets is kept: the bay's id, its networks, its key. Erase the whole flash once,
through the same port and with the same switch as for a flash, `-d build-hub` for a hub:

```console
$ west flash -d build-bay --erase
```

On a PCB that was set up, the erase also wipes everything in the table at the end of this page.

## A hub that does not answer

The hub's console USB-C, in the power box's front wall, is wired straight to the ESP32-S3's USB pins, and the
hub's firmware never takes them for anything else: esptool resets it into its ROM loader whatever the firmware
does, short of firmware that reconfigures IO19 and IO20. No button is needed, and the box stays closed:

```console
$ west flash -d build-hub
```

The same port carries the hub's shell, at 115200: try `hub status` and `hub events` first. It also powers
the controller, not the rows, so a hub with no charger can be flashed too. The rows are held on across the
controller's resets, so a flash should leave the rack powered; this is to be checked on the first hub.

The last resort: **BOOT** and **RESET**, pressed with a pin through the lid's holes BOOT and RST, down a guide
tube onto each button; then the UART pads on the hub's underside, with the lid off (4 × M3 × 8) and the hub off
its spacers.

A hub without Wi-Fi still holds the charger's contract, switches its rows and runs the rack bus: its firmware
starts them before the network. Only its page and its API are gone; its console still works.

## A lost admin key

Each PCB forgets its key only by a hand on it, and is then claimed again:

| | Forget the key | What else goes |
|---|---|---|
| A bay node | hold BOOT for 10 s, or `bay access reset` on its UART pads (refused over telnet) | its access rules and its reservations: the node is open again |
| The hub | hold BOOT for 10 s with a pin through the lid, or `hub access reset` on its console USB-C | nothing: the hub has no rules. Its events keep `admin key forgotten` |

Then claim each again with the rack's key, old or new, and push the rules again from the lab file:
[Access rules and security](access.md#claim-the-hub-and-the-nodes-with-one-key). Before that, look for a
browser where a page still says *admin*: **Copy key** in the bay page's *Manage access* dialog gives the key
back.

## A lost signing key

MCUboot boots only images signed with the key it was built with. If the rack's builder signed with a key of
their own and it left with them, every image you build is refused, whichever admin key you hold. A PCB whose
firmware dialog shows a *test key* tag beside its version has MCUboot's public test key, and nothing is lost.

The way back is one flash over USB of every PCB, with an MCUboot built for your key: the hub through its
console USB-C, each node through its bay's front port with SERVICE on, as above. `west flash` writes MCUboot
and the application together, and without `--erase` the stored settings stay. Build with your new key first
([Sign with your own key](../build/get-the-firmware.md#sign-with-your-own-key)), and keep it, with a backup,
outside the repository. Updates over the network work again from then on
([Update the firmware](update-firmware.md)).

## What a node and a hub remember, and how to wipe it

What each keeps in its flash's settings, read from the firmware (`firmware/bay-node/src/main.c`, `access.c`,
`camera.c`, `boards.c`, `firmware/power-hub/src/main.c`, `firmware/common/lib/net.c` and `update.c`); every
item survives a restart, a power cut and an update:

| A bay node keeps | Set with |
|---|---|
| its id, and so its name `bay-<id>.local` | `bay id b3` |
| classic mode forced | `bay mode classic`, the page's USB card |
| the AUX UART's settings: speed, format, Enter, echo, esptool reset | `bay aux 115200 8N1`, the console card |
| that a hub once gave it a place (an update's trial then waits for the rack bus) | the hub |
| the admin key and the access rules | a claim, `bayctl access push`, the page |
| the camera's settings | `bay camera set`, the camera card |
| each port's board target | the page, `bayctl import lab` ([Board targets](board-targets.md)) |
| its Wi-Fi networks | `wifi cred add` |
| its transmit power | `radio <dBm>` |
| the record of its last update: from, to, confirmed or rolled back | an update |

| The power hub keeps | Set with |
|---|---|
| its id, and so its name `rack-<id>.local` | `hub id lab1` |
| 28 V EPR asked for, or 20 V | `hub pd epr`, `hub pd 20v` |
| which rows are switched on | `hub row B on`, the page |
| the shed order | `hub shed DCBA` |
| the budget's margin and its cap | `hub budget margin 10`, `hub budget cap 90` |
| the admin key | a claim |
| its Wi-Fi networks, its transmit power, its last update | as on a node |

A DATA ×4 bay's node also keeps the co-processor's analyzer image, in a partition of its own
([Logic analyzer](logic-analyzer.md)). A network built into the image with `wifi.conf` is in the firmware, not
in the settings. Nothing else is kept: not the reservations, not which ports were off, not the wires, not the
hub's events ([After a power cut or a restart](power-and-reset.md#after-a-power-cut-or-a-restart)).

There is no single factory reset. `west flash --erase` erases the whole flash, every row of both tables and
the analyzer image with it, and writes the firmware again; on a configured PCB
[it cannot be undone](../build/index.md#erase). For less, each item has its own command above, and
`bay access reset`, or BOOT held for 10 s, clears the access control alone.
