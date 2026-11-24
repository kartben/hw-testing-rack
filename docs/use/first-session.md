# A first session with a bay

One board goes into a drawer, and from then on it is powered, flashed and read from a Linux machine without
being touched again. The board here is a new Raspberry Pi Pico 2 on port 2 of bay B3, a DATA ×4 bay: `B3.2`.

:::{status} simulated
The `bayctl` lines that need no USB were run against the simulated node, and their output is shown as it
came. Attaching and flashing cannot be simulated, and no rack exists to try them on. See
[What exists today](../plan/status.md).
:::

This walk-through is worked out from [tools/bayctl.py](../../tools/bayctl.py) and from the pages it links;
nobody has done it yet.

## What you need

- A rack that answers at `rack.local`, and its bay B3 at `bay-b3.local`. If someone else built it:
  [Take over a rack you did not build](take-over-a-rack.md).
- A Linux machine with a checkout of the repository, `usbip` and its sudo rule:
  [Set up bayctl and usbip](set-up-your-machine.md).
- A Zephyr workspace with `west` on that machine.
- A Pico 2 that has never been flashed, and a short USB-C to micro-B cable with straight plugs.

On a rack you share, hold the bay for the session first: `bayctl lease B3 --for 1h`, and
`bayctl release B3` at the end ([Reserve a bay](reserve-a-bay.md)).

## Put the board in B3, on port 2

Pull the drawer of B3 out; it stays connected on its drag chain. Set the Pico 2 on the plate between its
pegs ([Put a board in a bay](mount-a-board.md)) and plug its cable into port 2 of the DATA ×4: the second
of its four sockets from the left, below the pin header numbered 2. Push the drawer in.

## Power it, and see what the node sees

Every port is switched on when its bay node starts, so the board is powered unless someone has switched it
off or the port is still waiting for power. Switching it on again does no harm:

```console
$ python tools/bayctl.py power B3.2 on
B3.2   port 2  VBUS on 97 mA  no USB device
$ python tools/bayctl.py ports B3
B3.1   port 1  VBUS on 92 mA  303a:1001 USB JTAG/serial debug unit  busid 1-1.1
B3.2   port 2  VBUS on 133 mA  2e8a:0003 RP2 Boot  busid 1-1.2
B3.3   port 3  VBUS on 93 mA  2e8a:0003 RP2 Boot  busid 1-1.3
B3.4   port 4  VBUS on 95 mA  303a:1001 USB JTAG/serial debug unit  busid 1-1.4
```

The first answer comes before the board has enumerated; once it has, `ports` lists it. A blank Pico 2
starts in its USB bootloader, which is what port 2 shows. The simulated node's Pico reports `2e8a:0003`, the
id of the older RP2040; a Pico 2 reports `2e8a:000f`. The busid `1-1.2` is port 2 of a DATA ×4; on a
DATA ×6 port 2 would be `1-1.1` ([Bays, ports and addresses](names.md)). Switching a port, and what a
refusal means: [Power-cycle or reset a board](power-and-reset.md).

## Tell the bay which board it is

Open `http://bay-b3.local/`. In the **USB devices** card, the row of B3.2 says *No board target*. Click
**Set board…**: the dialog proposes the Zephyr targets known for this USB device. Take
`rpi_pico2/rp2350a/m33_0` with the runner `uf2`, set the console to the device's own USB serial, and save.

```{figure} ../img/web-ui-board-target.png
:class: bb-screenshot
:alt: The board target dialog of the bay's page
:width: 480px

Simulated node: the dialog, here for B3.4, a XIAO ESP32-C6. The target is picked from the suggestions for
the device's USB ID.
```

The node keeps the target in flash for this board. `bayctl list` and twister's hardware map read it; a
session by hand works without it ([Board targets](board-targets.md)).

## Attach its USB

In a second terminal, and leave it running:

```console
$ python tools/bayctl.py attach B3.2 --follow
```

`bayctl` asks the node for the port's busid and runs `usbip attach`. The Pico 2's bootloader has no serial
port, so nothing is printed yet; its drive appears on your machine. `--follow` matters at the next step,
when the board comes back as another USB device. The other ways to attach, and what passes through USB/IP:
[USB/IP and flashing](usb-and-flashing.md).

## Flash it with west

In the first terminal, from the `zephyr` directory of your workspace:

```console
$ west build -b rpi_pico2/rp2350a/m33_0 -S cdc-acm-console samples/hello_world
$ west flash --runner uf2
```

The `cdc-acm-console` snippet puts Zephyr's console on the board's own USB: a board on a DATA port has no
UART to the bay node. The `uf2` runner copies the image onto the bootloader's drive, which your desktop
must have mounted. The Pico 2 then restarts into the application, its bootloader device goes away, and the
second terminal reports the new one:

```text
B3.2: attached, /dev/serial/by-id/usb-ZEPHYR_USB-DEV_9F2D3A71B0C4E8D5-if00
```

The name is the example lab file's; yours carries your board's serial number. This is the least certain
step of the page: a UF2 copied onto a bootloader's drive through USB/IP is not recorded as tried.

A Pico 2 that already runs an application does not return to its bootloader by itself. That takes a wire
from the port's BOOT pin to the board, then `bayctl boot B3.2 --power-cycle`
([USB/IP and flashing](usb-and-flashing.md#uf2-boards-and-esp32-boards)).

## Open its console

```console
$ python -m serial.tools.miniterm /dev/serial/by-id/usb-ZEPHYR_USB-DEV_9F2D3A71B0C4E8D5-if00 115200
```

This is the board's own USB serial, attached over USB/IP. The bay's one AUX UART is another thing: the page
shows its **Console** card only on a bay with one board, and `bayctl pty B3` answers that B3 holds several
boards ([Serial console](serial-console.md)).

## Hand the bay back

Stop `attach --follow` with Ctrl-C, then:

```console
$ python tools/bayctl.py detach B3.2
detached 1 device(s)
```

The board stays powered. Switch it off with `power B3.2 off` if it should not run; the port is on again at
the node's next restart.

The same session, command for command, runs today against the simulated node with nothing on the desk:
[Try it without hardware](../plan/try-it-without-hardware.md).
