# Flash the hub and the nodes

A PCB comes here from stage 4 of its checklist: its rails are measured and its module is blank.  The hub and
the node are both flashed over USB through the ESP32-S3's own USB-Serial-JTAG.  It shows up as a serial port
(`/dev/ttyACM*` on Linux, `/dev/cu.usbmodem*` on macOS, `COMx` on Windows) and resets the chip into its ROM
loader when esptool asks: neither PCB needs a BOOT press.

:::{status} bench
`west flash` over the USB-Serial-JTAG, with MCUboot and a signed application, has been used on the stand-in
boards (an M5Stack CoreS3, a XIAO ESP32-S3).  No v1.0 PCB has been flashed.  On the stand-ins SERVICE was a
jumper: the node's switch and the USB path it routes have never run.
[What exists today](../plan/status.md#firmware-feature-by-feature).
:::

The commands are typed in the workspace `rack-ws`, and flash its two builds, `build-hub` and `build-bay`
([Build or download the firmware](get-the-firmware.md)).

## Flash the hub

```{figure} ../img/pcbs/power-hub-top.jpg
:alt: The power hub v1.0 seen from above
:width: 55%

KiCad render of the power hub v1.0.  The console USB-C (J6) is at the lower right, at the end of the row of
LEDs; the charger's input (J1) is at the upper right; the two buttons at the upper left are RESET, then BOOT
below it.
```

1. Plug the laptop into the hub's console USB-C (J6).  In the power box it is the USB-C of the front wall,
   over the label CTL.  This port powers the controller, not the rows: a hub on a desk with no charger is
   flashed the same way.
2. Flash.  MCUboot goes on first, then the signed application.

   ```console
   $ west flash -d build-hub
   ```

   West finds the port by itself.  With several serial ports on the machine, name it:

   ```console
   $ west flash -d build-hub --esp-device /dev/ttyACM0
   ```

The console USB-C goes straight to the ESP32's USB pins, and the hub's firmware never takes them for anything
else: esptool gets the ROM loader whatever the firmware does, and every later flash is the same command.

The hub holds its row enables across the controller's resets, so flashing a hub whose rows are on should
leave the rack powered.  Nobody has tried it:
[stage 4 of the hub's checklist](check-the-pcbs/power-hub.md#4-flash-and-ask) asks for the result.

## Flash a node

A node runs from its row, never from its USB port.  On the bench that is 15 to 30 V on J1 (ROW IN): pin 1 is
+, pins 2 and 5 are GND, and the 5 V buck starts above 13.5 V.  The node's checklist feeds it 20 V with a
0.2 A limit through [the two-wire bench lead](row-cables.md#a-two-wire-lead-for-the-bench).  In a rack its row
must be on: the hub turns the rows on by itself, `hub row <A–D> on` otherwise.

```{figure} ../img/pcbs/bay-node-top.jpg
:alt: The bay node v1.0 seen from above
:width: 55%

KiCad render of the bay node v1.0.  The PC port (J3) and the SERVICE switch (SW3, marked SVC) are on the front
edge, at the bottom; ROW IN (J1) is at the lower left; RESET and BOOT are at the upper left.
```

1. Slide **SERVICE** on and plug the laptop into the **PC** port.  SERVICE routes the PC port to the
   ESP32's USB pins in hardware.  A blank module shows its serial port at once.  Firmware that is running
   stops its USB host first and gives the ESP32-S3's single USB PHY to the USB-Serial-JTAG: the bay LED turns
   yellow.
2. Flash.  The port drops for a second at the reset, comes back, and the node picks SERVICE up again.

   ```console
   $ west flash -d build-bay
   ```

3. Slide SERVICE off.  The USB host restarts and the bay's boards are back on USB/IP.

The PC port and SERVICE are on the bay's fascia, so a node in a closed bay is flashed the same way once
[the rack is online](bring-the-rack-online.md).  Every PCB needs this one flash over USB, with MCUboot, before
its first [update over the network](../use/update-firmware.md).

## First words in the shell

| | Hub | Node |
|---|---|---|
| The shell is on | the console USB-C, the port that flashed it | the pads TX, RX and GND of the bottom face, through a 3.3 V USB-UART adapter |
| Speed | 115200 | 115200, 8N1 |
| Over the network | no telnet: this shell switches rows and has no login | telnet on port 23 once the node is on Wi-Fi.  It has no login of its own: [Access rules and security](../use/access.md) |
| First command | `hub status` | `bay status` |

The node has no shell through its PC port: in SERVICE the USB-Serial-JTAG carries flashing, and JTAG for
OpenOCD, and nothing else.  Its Wi-Fi network is therefore typed on the pads, or built into the image.  The
render in [stage 2 of the node's checklist](check-the-pcbs/bay-node.md#2-no-power) shows the pads by the names
printed beside them; [the bay node's PCB page](../reference/pcbs/bay-node.md) lists them.

Every command of the two shells: [Power hub shell](../reference/hub-shell.md),
[Bay node shell](../reference/node-shell.md).

## A module that ran other firmware

Such a module may hold something else where the settings live.  The boot log then says
`settings unavailable (-45): defaults only; storage partition not NVS: west flash --erase`, and nothing the
shell sets is kept.  Erase the whole flash once, with the same port and switch as for a flash (`-d build-hub`
for a hub):

```console
$ west flash -d build-bay --erase
```

`--erase` also wipes what a configured node or hub had stored: its networks, its name, its access key and the
rest of [what it remembers](../use/recover.md#what-a-node-and-a-hub-remember-and-how-to-wipe-it).  On a PCB
that is already set up, [that cannot be undone](index.md#erase).

## What west flash writes

| Address | File of the build directory |
|---|---|
| `0x0` | `mcuboot/zephyr/zephyr.bin`: MCUboot |
| `0x20000` | `bay-node/zephyr/zephyr.signed.bin` or `power-hub/zephyr/zephyr.signed.bin`: the signed application, in slot 0 |

An image flashed over USB has no trial: MCUboot takes it as confirmed.  A build made without `--sysbuild` is
the application alone, written at `0x0`, and takes no update over the network.

CI's artefacts hold the same two files and no build directory, so `west flash` cannot write them: they go on
with esptool at these two addresses.  The repository gives the addresses and no complete esptool command, and
nobody has flashed a PCB that way.

## The module's one-time fuse

Each ESP32-S3 module has one fuse to burn, `DIS_USB_OTG_DOWNLOAD_MODE`.  It switches off the ROM's USB-OTG
download mode, which the rack never uses.  In that boot mode the ROM drives IO40 high and IO39 and IO38 low:

- on the node, IO40 reads the fault output of the DATA lead's eFuse, which is held low whenever that eFuse is
  off, so the ROM drives against it;
- on the hub, IO40 is the PD controller's SCL, and the ROM would back-feed an unpowered controller through it.

The two ways in that the rack uses, the USB-Serial-JTAG and the UART pads, stay open.

:::{warning}
A burnt fuse [cannot be unburnt](index.md#fuse).  Burn this one and no other.  Never burn `STRAP_JTAG_SEL`:
GPIO3 floats on these PCBs.
:::

With the PCB connected as for a flash (the hub's console USB-C; the node's PC port, SERVICE on):

```console
$ espefuse.py --port /dev/ttyACM0 burn_efuse DIS_USB_OTG_DOWNLOAD_MODE 1
```

`espefuse.py` comes with esptool, which `west packages pip --install` installed.  The moment to burn it is
the last stage of [the hub's](check-the-pcbs/power-hub.md#6-last) and of
[the node's](check-the-pcbs/bay-node.md#6-last) checklist.

A node whose fuse is never burnt is not harmed: R43, 1 kΩ in series with IO40, holds the current to 3.3 mA
at each flash, under the 10 mA the eFuse's output allows.  On the hub what remains is the back-feed into an
unpowered PD controller, when a hub with no charger is flashed.

## If a PCB no longer answers

A node can be wedged: firmware that takes the USB PHY for its host and crashes before letting it go.  With
SERVICE on and the laptop plugged, hold **BOOT** and tap **RESET**: the ROM loader starts with the PHY on the
USB-Serial-JTAG.  Run `west flash -d build-bay`, then release BOOT.  The last resort is the pads TX and RX
with a 3.3 V USB-UART adapter, BOOT held at reset.

A hub does not get into that state: its firmware never takes the USB pins, short of firmware that
reconfigures IO19 and IO20.  Its last resort is the same pair of buttons, BOOT (SW2) and RESET (SW1), and
the pads TX and RX of its bottom face.

In an assembled rack the buttons are harder to reach, and a row can stand in for RESET:
[Recover a node or a hub](../use/recover.md).  A v1.0 PCB that still does not answer is a finding:
[report it](../reference/known-limitations.md#report-a-finding).

Back to stage 4 of your checklist, which sets the Wi-Fi network next (a node's only if its image carries
none): [the hub's](check-the-pcbs/power-hub.md#4-flash-and-ask), [the node's](check-the-pcbs/bay-node.md#4-flash-and-ask).
