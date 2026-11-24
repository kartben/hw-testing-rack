# Serial console

A board on a DATA port has no wire to the bay node's UART: its console is its own USB serial port, which
reaches your machine over USB/IP with the rest of the board's USB device.

:::{status} simulated
The board's USB serial over USB/IP ran on a XIAO ESP32-S3 stand-in, never through a DATA board. The bay's
AUX UART: the RFC 2217 server against pyserial on a PC, the web console on native_sim with a Zephyr board as
the target, and the web console connecting on the XIAO over Wi-Fi. RFC 2217 and raw TCP over Wi-Fi have no
recorded result. See [What exists today](../plan/status.md#status-console).
:::

Needs: for a board on a DATA port, a Linux machine set up for USB/IP
([Set up bayctl and usbip](set-up-your-machine.md)); for the AUX UART, a lead that you make yourself.

## Which console a board has

| The board | Its console | Reached by |
|---|---|---|
| On a DATA ×6 or DATA ×4 port, with a USB serial of its own (a probe's virtual COM port, a CDC ACM console, a UART bridge) | its own USB serial | `usbip attach`, then `/dev/serial/by-id/…` on your machine |
| Without a USB serial of its own | the bay's AUX UART, one per bay, wired by hand | the bay's page, RFC 2217 on TCP 4001, raw TCP on TCP 4000, the node's shell |

The Pico 2 in B3.2 has a USB serial only if its Zephyr application makes one: the example lab file's B3.2 is a
build with the `cdc-acm-console` snippet. Most screenshots show a bay with one board whose console is the AUX
UART, the form of the bench stand-ins and of the simulated node started without `--ports`
([Bays, ports and addresses](names.md#a-bay-that-holds-one-board)).

## Your board's own USB serial

Attach the board and read the names its serial ports get:

```console
$ python tools/bayctl.py attach B3.2 --show
B3.2: /dev/serial/by-id/usb-ZEPHYR_USB-DEV_9F2D3A71B0C4E8D5-if00
$ python -m serial.tools.miniterm /dev/serial/by-id/usb-ZEPHYR_USB-DEV_9F2D3A71B0C4E8D5-if00 115200
```

The name is the example lab file's; yours carries your board's serial number. It is built the way udev
names `/dev/serial/by-id`: `usb-<vendor>_<product>_<serial>-if<NN>`, plus `-port<P>` for a USB-serial bridge (FTDI, CP210x, CH34x,
PL2303). A probe with several serial ports gives one name per interface, and the board target's console
`usb:NN` picks interface `NN` for twister ([Board targets](board-targets.md#which-console)). Twister reads the
same path, written into the hardware map as `serial` ([Zephyr twister](twister.md)).

A board that resets or re-enumerates ends its USB/IP session, and its tty goes with it. It comes back under
the same busid: keep `python tools/bayctl.py attach B3.2 --follow` running in another terminal, and reopen the
terminal program once the name is back.

Serial bridges (FTDI, CP210x, PL2303, CH340 to CH343, CH9102) have a small receive FIFO, so the node reads
them ahead of the client. That carries 115200 to 230400 baud; a continuous 921600 baud stream (92 KB/s) still
overflows over Wi-Fi. A board with native USB (CDC ACM) holds its data until it is polled and is not affected.
The figures come from the XIAO stand-in ([bench.md](../bench.md)).

These boards have no browser console, no RFC 2217 and no raw TCP port: the bay's page shows their USB
devices, not their output.

## The bay's AUX UART

The node's J5 (AUX) carries a UART (UART1 of its ESP32-S3) and two open-drain lines, RESET and BOOT. A DATA
board has no AUX line per port, but the node's own AUX can still go to one board of the bay by hand. No source
describes that wiring on a v1.0 rack, and the node refuses the console `aux` in a port's board target ("console:
a DATA x4 port has no AUX UART: its board's USB, or none"), so twister cannot use it there.

The board's output goes to every client and every client's input to the board, so two people typing at once
interleave their keystrokes. The settings default to 115200 8N1, Enter sending CR, no local echo, and are saved
for the bay: 300 to 5,000,000 baud, 5 to 8 data bits, parity none, odd or even, 1 or 2 stop bits.

While the board's power is off the node releases its TX pin, so it does not feed the unpowered board
through its RX pin; the pin goes back to the UART when the power returns.

### In the browser

```{figure} ../img/web-ui-console.png
:class: bb-screenshot
:alt: The Console card: Reset, Bootloader and Break on the left; Timestamps, Copy, Clear, Download and the 115200 8N1 settings on the right; a coloured Zephyr log; the miniterm command for RFC 2217 at the bottom

Simulated node, bay B2 with one board. The line at the foot is the RFC 2217 command to paste; beside it, the
clients connected.
```

The **Console** card of `http://bay-b3.local/` is a terminal (xterm.js over a WebSocket) for two browsers at
once: raw bytes both ways, so VT100 escape sequences and UTF-8 work. The node keeps the last 16 KB received
and replays them to a browser that connects, so a page opened after a crash still shows it; a page that
reconnects after a Wi-Fi drop skips what it already shows, and marks a restart of the node. A browser slower
than 200 ms per send is dropped.

**Break** holds the board's RX line low for 250 ms. **Timestamps** adds the browser's time to each line,
**Download** saves everything received since the page opened. The settings button (`115200 8N1 ⚙`) sets the
baud rate, the format, what Enter sends (CR, LF, CR LF), local echo, and whether RFC 2217's DTR and RTS
drive BOOT and RESET; a change applies at once and is saved.

**Reset** and **Bootloader** call `/api/reset` and `/api/boot` without a port, which a node with a DATA board
refuses (409, `this node serves 4 boards: say which`, 6 behind a DATA ×6). Pulse the AUX lead's RESET and BOOT
from the node's shell instead.

### With bayctl

`bayctl pty <bay>` copies its stdin to the raw TCP port and the port to its stdout; twister's `serial_pty`
runs it. It serves a node with one board, a stand-in or the simulator: a port (`B3.2`) is refused with `a
sub-slot has no AUX UART: its console is the board's own USB` ([bayctl](../reference/bayctl.md#pty)).

### Over HTTP

```console
$ curl -s bay-b3.local/api/aux
$ curl -s -X POST bay-b3.local/api/aux -d '{"baud": 921600}'
$ curl -s -X POST bay-b3.local/api/aux/break -d '{"ms": 250}'
```

`POST /api/aux` takes any of `baud`, `data_bits`, `parity`, `stop_bits`, `enter`, `echo` and
`esptool_reset`, applies them and saves them. Every field and status code:
[Bay node HTTP API](../reference/node-api.md).

### In the node's shell

```console
uart:~$ bay aux 921600 8N1
uart:~$ bay aux send "help"
uart:~$ bay aux break
uart:~$ bay reset
uart:~$ bay boot
```

`bay aux` alone prints the settings, the consoles connected and the byte counters; `bay aux send` sends one
argument, then the configured Enter. `bay reset` pulses the AUX RESET line low for 100 ms; `bay boot` holds
BOOT across a RESET pulse and releases it 200 ms later. The shell is on telnet (TCP 23) and on the node's
UART pads ([Bay node shell](../reference/node-shell.md)).

### Over RFC 2217 and raw TCP

RFC 2217 takes one client on TCP 4001. Its settings last for its session, and the saved ones come back when it
disconnects; mark and space parity, 1.5 stop bits and flow control are refused.

```console
$ python -m serial.tools.miniterm rfc2217://bay-b3.local:4001 115200
$ esptool --port 'rfc2217://bay-b3.local:4001' chip-id    # with "DTR/RTS drive BOOT/RESET" on
```

```{code-block} yaml
:caption: a labgrid environment
NetworkSerialPort:
  host: bay-b3.local
  port: 4001
  speed: 115200
  protocol: rfc2217
```

With *DTR/RTS drive BOOT/RESET* on (it is off by default), the two lines act as the two-transistor auto-reset
circuit of ESP32 boards: RESET while RTS and not DTR, BOOT while DTR and not RTS. esptool then resets an ESP32
board into its ROM loader, and a terminal that raises both lines leaves the board alone.

Raw TCP takes one client on TCP 4000, `socat` or `nc`, at the saved settings:

```console
$ nc bay-b3.local 4000
```

A client that connects while another holds the port takes it over and the one before is disconnected; the
web console still shows the traffic.

## Wire the AUX lead

:::{warning}
J5 (AUX) takes the same plug as J2 (ROW OUT), 22 mm away on the same edge of the node. On the last node of a
row J2 is empty and live: its pin 6 is VRACK. An AUX lead pushed into J2 puts 20 to 28 V on its BOOT wire,
and into your board. Nothing but a row cable goes into ROW OUT ([Add a bay, then a row](../build/add-a-bay.md)).
:::

```{include} ../reference/cables.md
:start-after: <!-- site:aux-pinout -->
:end-before: <!-- /site:aux-pinout -->
```

The levels are 3.3 V, and J5 has no ESD or level protection (finding S5 of the
[schematic review](../schematic-review-2026-10-25.md)): a 5 V board's UART pushes about 1.1 mA into the node
through the 1 kΩ. Wire GND, the node's TX to the board's RX and its RX to the board's TX; RESET and BOOT only
where the board breaks them out.

The lead is a JST PH 6 ending in flying leads. The bill of materials has no line for it and no source gives
its length. The design runs it beside the DATA lead through the drag chain, up the drawer's cable window and
over the port wall; nobody has checked that both leads fit the chain ([Cables and pinouts](../reference/cables.md#aux-lead)).
J5 is on the node, in the tray: [Take out a tray, a node or a DATA board](service-a-bay.md) says how to
reach it and what to unplug first.

## If it does not work

| What you see | Why, and what to do |
|---|---|
| The board's `/dev/serial/by-id` name is gone after a reset | Its USB/IP session ended with the device. Run `attach --follow` and reopen the terminal. |
| Bytes lost at 921600 baud through an FTDI, CP210x or CH34x board | The bridge's FIFO overflows over Wi-Fi even with the node's read-ahead. Lower the baud rate. |
| `bayctl: … a sub-slot has no AUX UART: its console is the board's own USB` | `bayctl pty` named a port. Use the board's USB serial. |
| The board target dialog refuses the console `aux` | A port of a DATA board has no AUX line: choose `usb`, `usb:NN` or `none`. |
| `nc` or miniterm is disconnected, the web console still shows traffic | A newcomer took the port over; twister's `serial_pty` may be the other client on 4000. |
| A connection to 4000 or 4001 hangs, then times out | The access rules do not give your address the console right, or another address has reserved the bay: a refused client is dropped, not answered ([Access rules and security](access.md)). |
| Break answers `the DUT is powered off` | BREAK needs the board powered. |
| The Console card's Reset answers `this node serves 4 boards: say which` | The node has a DATA board. Pulse the AUX lines with `bay reset` in the shell, or reset the board on its port ([Power-cycle or reset a board](power-and-reset.md)). |

Anything else: [Troubleshooting](troubleshooting.md).
