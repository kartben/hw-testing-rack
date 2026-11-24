# Flash the hub and the nodes

You flash each power hub and bay node over USB in step 4 of [its checklist](check-the-pcbs/index.md). Later
updates can go [over the network](../use/update-firmware.md). After the flash, go back to the checklist to give
the PCB its Wi-Fi network, unless the node's image carries it.

Both PCBs flash through the ESP32-S3's own USB port. It shows up as a serial port (`/dev/ttyACM*` on Linux,
`/dev/cu.usbmodem*` on macOS, `COMx` on Windows). esptool puts the chip into its loader by itself, so you do
not press BOOT. Run the commands from `rack-ws`, the workspace where you built `build-hub` and `build-bay`
([Build or download the firmware](get-the-firmware.md)).

## Flash the hub

```{figure} ../img/pcbs/power-hub-top.jpg
:alt: The power hub v1.0 seen from above
:width: 40%

KiCad render of the power hub v1.0. The console USB-C (J6) is at the lower right, at the end of the row of
LEDs. RESET and BOOT are the two buttons at the upper left.
```

1. Plug the laptop into the hub's console USB-C (J6). In the power box, it is the USB-C on the front, above
   the label CTL. This port powers the hub's controller, so the hub needs no charger to be flashed.
2. Flash. West writes MCUboot first, then the signed application.

   ```console
   $ west flash -d build-hub
   ```

   West finds the port by itself. If the machine has several serial ports, name it:

   ```console
   $ west flash -d build-hub --esp-device /dev/ttyACM0
   ```

Every later flash of the hub is the same command. The hub keeps its rows on while its controller resets, so
the rack stays powered.

## Flash a node

A node takes its power only from its row, never from its USB port. On the bench, feed it 20 V with a 0.2 A
limit through [the two-wire bench lead](row-cables.md#a-two-wire-lead-for-the-bench) into J1 (ROW IN). In a
rack, its row must be on. The hub turns the rows on by itself. If a row is off, type `hub row A on` in the
hub's shell, with the letter of that row.

```{figure} ../img/pcbs/bay-node-top.jpg
:alt: The bay node v1.0 seen from above
:width: 40%

KiCad render of the bay node v1.0. The PC port (J3) and the SERVICE switch (SVC) are on the front edge, at the
bottom. ROW IN (J1) is at the lower left, RESET and BOOT at the upper left.
```

1. Slide **SERVICE** on. The PC port now goes to the node's own ESP32-S3, and the bay's boards are
   disconnected from USB. On a node that already runs firmware, the bay LED turns yellow.
2. Plug the laptop into the **PC** port. The node's serial port appears.
3. Flash. The port drops for a second at the reset and comes back.

   ```console
   $ west flash -d build-bay
   ```

4. Slide SERVICE off. The bay's boards come back on USB/IP.

The PC port and SERVICE are on the front of the bay, so you can flash a node in a closed bay the same way.

## Open the shell

| | Hub | Node |
|---|---|---|
| Where | the console USB-C you flashed it through | the TX, RX and GND pads on the bottom face, through a 3.3 V USB-UART adapter |
| Speed | 115200 | 115200, 8N1 |
| Over the network | none | telnet, port 23, once the node is on Wi-Fi ([Control who can use the rack](../use/access.md)) |
| First command | `hub status` | `bay status` |

The node's PC port carries no shell, only flashing and JTAG. That is why you type a node's Wi-Fi network on
its pads ([where they are](../reference/pcbs/bay-node.md)) or build it into its image. All the commands are on
[Power hub shell](../reference/hub-shell.md) and [Bay node shell](../reference/node-shell.md).

## Erase a module that ran other firmware

If the ESP32-S3 module ran other firmware before, its flash may hold other data where BitBunk keeps its
settings. The boot log then says
`settings unavailable (-45): defaults only; storage partition not NVS: west flash --erase`, and the PCB does not
keep anything you set in its shell. Erase the whole flash once, connected as for a flash (`-d build-hub` for a
hub):

```console
$ west flash -d build-bay --erase
```

`--erase` also wipes everything the PCB has saved: its networks, its name and its access key
([what a node and a hub remember](../use/recover.md)). On a PCB already in use,
[you cannot undo it](index.md#erase).

## What west flash writes

| Address | File in the build directory |
|---|---|
| `0x0` | `mcuboot/zephyr/zephyr.bin`, MCUboot |
| `0x20000` | `bay-node/zephyr/zephyr.signed.bin` or `power-hub/zephyr/zephyr.signed.bin`, the signed application |

The images from CI are the same two files, without a build directory. Write them with esptool at these two
addresses.

## The module's one-time fuse

Burn one fuse on each ESP32-S3 module: `DIS_USB_OTG_DOWNLOAD_MODE`. It turns off the chip's USB-OTG download
mode. The rack never uses that mode, and in that mode the chip drives pins that the hub and the node use for
other things. You can still flash over the USB port and over the UART pads afterwards.

:::{warning}
A burnt fuse [cannot be unburnt](index.md#fuse). Burn this one and no other. Never burn `STRAP_JTAG_SEL`.
:::

Burn it in the last step of [the hub's](check-the-pcbs/power-hub.md) or
[the node's](check-the-pcbs/bay-node.md) checklist, connected as for a flash:

```console
$ espefuse.py --port /dev/ttyACM0 burn_efuse DIS_USB_OTG_DOWNLOAD_MODE 1
```

`espefuse.py` comes with esptool, which `west packages pip --install` installed.

## If a PCB no longer answers

If firmware takes over the node's USB port and then crashes, no serial port appears. With SERVICE on and the
laptop plugged in, hold **BOOT** and tap **RESET**: the chip starts its loader on the USB port. Run
`west flash -d build-bay`, then release BOOT. If that fails, flash through the TX and RX pads with a 3.3 V
USB-UART adapter, and hold BOOT while you reset.

The hub's firmware never takes over its USB port. If a hub stops answering, do the same with its BOOT (SW2)
and RESET (SW1) buttons, then with the TX and RX pads on its bottom face. In an assembled rack the buttons are
hard to reach: see [Recover a node or the hub](../use/recover.md).
