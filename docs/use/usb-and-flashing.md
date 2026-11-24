# Attach a board's USB over USB/IP and flash it

Each bay node exports the USB devices of its boards over USB/IP, on TCP port 3240. A Linux machine attaches
one, and from then on the board's probe and its serial port are local USB devices: `west flash` runs as it
does with the board on the desk.

:::{status} bench
USB/IP ran on a XIAO ESP32-S3 stand-in, with one board and then with several behind a bench hub (October
and November 2026); the results are quoted below. The M5Stack CoreS3 build has a bench plan and no recorded
result. The busid by port and the session that ends with its board are tested on native_sim. Nothing has
gone through a DATA ×6 or a DATA ×4 on a v1.0 node. See [What exists today](../plan/status.md#status-usbip).
:::

Needs: a Linux machine with `usbip`, the `vhci-hcd` module and a sudo rule
([Set up bayctl and usbip](set-up-your-machine.md)), and the flashing tools of your boards with their udev
rules, exactly as for boards plugged into that machine.

## In the browser

A browser cannot attach a USB device; the bay's page shows what there is to attach and gives the line that
does it.

```{figure} ../img/web-ui-ports-attach.png
:class: bb-screenshot
:alt: Two port rows: B3.1, an MCU-Link attached by 192.168.1.41 for 12 min; B3.2, an FT232R ready to attach

Simulated node, ports 1 and 2 of a DATA ×4 bay. Under each port's name is its busid, then whether the board
is ready to attach or who has attached it, and for how long.
```

Each row of the **USB devices** card names the device the node enumerated on that port: product, maker,
USB ID, serial number, and its interfaces (CMSIS-DAP, CDC ACM, mass storage). **Copy attach**
copies the `sudo usbip attach` line for that board. A device marked *Not exported* is beyond the six that a
node serves at once.

## With bayctl

```console
$ python tools/bayctl.py attach B3.2 --show
B3.2: /dev/serial/by-id/usb-ZEPHYR_USB-DEV_9F2D3A71B0C4E8D5-if00
```

`attach` asks the node for the port's busid, runs `usbip attach` through `sudo -n`, and waits up to 10 s
for the board's serial ports; `--show` prints them (the name above is the example lab file's for a Pico 2
running a Zephyr USB console). A board that is already attached is left alone.

- `attach B3.2 --follow` stays in the foreground and attaches the board again after each reset, until
  Ctrl-C. A board that disconnects or re-enumerates ends its session and comes back under the same busid.
- `attach B3` attaches every board of the bay, passing by its analyzer and its empty ports.
- `detach B3.2` drops it.
- `prepare B3.2` is what a test runner calls before flashing: data path to USB/IP, port on (a latched
  over-current is cleared), wait until the board has enumerated, attach, wait for its console
  ([Zephyr twister](twister.md)).

`attach`, `detach` and `prepare` run on Linux only. Every option: [bayctl](../reference/bayctl.md).

## With usbip itself

```console
$ usbip list -r bay-b3.local
$ sudo usbip attach -r bay-b3.local -b 1-1.2
```

`usbip list` shows one line per board; the DATA board's hub is never offered. `sudo usbip port` lists what
this machine has attached, and `sudo usbip detach -p` with a port number from that list drops one.

The busid depends on the DATA board in the bay:

| In the bay | busid of USB-C n | B3.2 is |
|---|---|---|
| a DATA ×4 | `1-1.n` | `1-1.2` |
| a DATA ×6 | `1-1.6` for USB-C 1, then `1-1.(n − 1)` | `1-1.1` |

Take the busid from the bay's page or from `bayctl ports B3`, never from another bay's command line
([Bays, ports and addresses](names.md#usbip-busids-on-a-data-6-and-on-a-data-4)).

## Flash with west

```console
$ python tools/bayctl.py prepare B3.2
$ west flash
```

With several bays attached, two boards of a kind show up as two identical probes, and the runner must be
told which: `west flash --dev-id` with the probe's serial number, which is what the bay's
[board target](board-targets.md) keeps for twister. Keep `attach --follow` running in another terminal
when the board's USB device goes away at each reset.

`west debug`, GDB and RTT through an attached probe have not been tried: nothing is recorded, and the same
transfer limits apply to a debug session as to a flash.

## UF2 boards and ESP32 boards

A UF2 board, such as a Pico 2 with the runner `uf2`, is flashed by copying a file onto the drive of its
bootloader, so the board must be in its bootloader and the drive mounted on your machine. A blank Pico 2
comes up there by itself. Afterwards it takes the BOOT line of a DATA ×4 port, wired to the Pico 2's TP6 pad:
`bayctl boot B3.2 --power-cycle` ([Power-cycle or reset a board](power-and-reset.md#reset-and-bootloader)).
A DATA ×6 has no such line. After the copy the board restarts as another USB device: `attach --follow`
picks it up. On the XIAO stand-in `picotool load` took 1.4 to 1.7 s for a RAM image over USB/IP
(2026-11-03); copying a UF2 onto the drive this way is not recorded as tried.

An ESP32 board with USB in the chip, such as a XIAO ESP32-C3 with the runner `esp32`, needs no wire: the
chip enters its loader when esptool asks. The runner picks the board by its serial port,
`west flash --esp-device /dev/serial/by-id/…`.

An ESP32 board behind a UART bridge goes through the node's read-ahead for serial converters (FTDI,
CP210x, PL2303, CH34x). On the XIAO stand-in `esptool read_flash` at 115200 baud passed three times out of
three through an FTDI look-alike, at about 80 kbit/s (2026-10-22). That covers 115200 and 230400 baud; a
continuous 921600 stream still overflows the converter over Wi-Fi.

## Which probes and devices work

No list of tested boards exists; the table holds every device the sources mention. The limits have their
home on [Known issues, and what will not work](../reference/known-limitations.md).

| Device | Over USB/IP | How it is known |
|---|---|---|
| ST-LINK, J-Link | expected to pass: bulk endpoints | read from the sources, no run recorded |
| CMSIS-DAP v2 (bulk), such as an MCU-Link | expected to pass | an MCU-Link was attached on the XIAO stand-in, nothing opened on it |
| CMSIS-DAP v1 (HID), such as the UNO R4 WiFi's probe | fails | it needs interrupt OUT transfers, which the node's USB host does not do |
| FTDI, CP210x, PL2303, CH34x serial bridges | pass | an FTDI look-alike measured on the XIAO stand-in; the others by their USB IDs in the code |
| A board's own USB serial (CDC ACM) | passes | stated in the bench notes; such a device holds its data until polled |
| A Pico 2 in BOOTSEL | `picotool load` passes | run on the XIAO stand-in |
| Mass storage | reads pass | a streamed read measured on the XIAO stand-in |
| Audio and video devices | fail | no isochronous transfers |
| Low-speed devices behind the DATA board | fail | the USB host driver does not handle low speed behind a hub |

Older text says that boards with an on-board USB hub do not work; that predates the hub support, and every
board now sits behind the DATA board's hub. A board with a hub of its own behind that one has not been
tried.

## How fast, how many at once

The node's USB controller is full speed: 12 Mbit/s for the whole bay, shared by its boards, whatever the
board could do on a desk. On the XIAO stand-in a streamed mass-storage read reached 820 to 840 kB/s.

A node serves six devices at once: the six boards of a DATA ×6, or the four of a DATA ×4, its co-processor
and a spare. Each device takes one client; a second machine that tries to attach it is refused.

Across the rack the limit is the Wi-Fi channel: at most 8 flashes at once, a figure from a simulation, not
from a measurement ([Specifications](../reference/specifications.md), and the reason on
[Wi-Fi in the rack](wifi.md)).

## On macOS or Windows

The commands that go over HTTP (`power`, `reset`, `ports`, `status`) run anywhere Python does. Attaching
needs a USB/IP client in the kernel. On Windows the bench PC attached through WSL2, with `vhci_hcd` loaded
there as a module. A native Windows client, usbip-win2, with the busid from `bayctl ports B3`, is untested.
For macOS the sources name no client.

Without a client, plug the laptop into the bay's front port:
[Front port and classic mode](front-port.md).

## If it does not work

| What you see | Why |
|---|---|
| `usbip attach` hangs, then times out | The node dropped the connection without answering: its access rules do not give your address the usbip right, an admin kicked you for a minute, or someone has reserved the bay ([Access rules and security](access.md)). |
| `bayctl: B3.2: 1-1.2 is not exported (is the board powered and enumerated?)` | The port is off, the board has not enumerated, or the bay is in classic or SERVICE mode ([Front port and classic mode](front-port.md)). |
| `sudo: a password is required` | `bayctl` calls `sudo -n usbip`: the sudo rule is missing ([Set up bayctl and usbip](set-up-your-machine.md)). |
| The device vanishes at each reset | Its session ended with it. Run `attach --follow`. |
| Another machine attached the board you had reserved | A reservation of one port guards its power and its wires, not its USB/IP. Reserve the whole bay ([Reserve a bay](reserve-a-bay.md)). |
| `Invalid SLIP escape` or `Corrupt data` from esptool through a UART bridge | The bridge's buffer overflowed between two reads over Wi-Fi. Lower the baud rate; a wired client loses less than one on Wi-Fi. |
| A probe never shows up, and the node's log repeats `Port 2 not enabled after reset` | Seen on the bench on 2026-10-21 with an MCU-Link behind a hub: Zephyr's hub class reset its port in a loop. A fix is carried as a patch; the MCU-Link attached in a later session. |

Anything else: [Troubleshooting](troubleshooting.md).
