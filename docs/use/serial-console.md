# Serial console

On every bay, a board's serial port reaches your machine through USB/IP. It appears there as a USB serial
device of its own, and you open it with your usual terminal program.

A board with no USB serial can use the bay's AUX UART instead, through a lead that you make. Each bay has one
AUX UART, for one board.

## Open your board's USB serial

Most boards have a USB serial port: a probe's virtual COM port, a USB-serial bridge, or Zephyr's console on the
board's own USB. Attach the board from a Linux machine set up for USB/IP
([Set up your machine](set-up-your-machine.md)), and open the name it prints:

```console
$ python tools/bayctl.py attach B3.1 --show
B3.1: /dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_34:85:18:9A:3C:10-if00
$ python -m serial.tools.miniterm /dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_34:85:18:9A:3C:10-if00 115200
```

The name comes from the device's USB strings. A Zephyr application built with the `cdc-acm-console` snippet is
`usb-Zephyr_Project_CDC_ACM_serial_backend_<serial number>-if00`.

A probe with several serial ports gets one name per interface, ending in `-if00`, `-if01` and so on. The
board target's console `usb:NN` tells twister which one to read
([Choose the console](board-targets.md#choose-the-console)).

When the board resets, its serial port goes away and comes back. Keep `bayctl attach B3.1 --follow` running in
another terminal, and reopen your terminal program.

Through a USB-serial bridge (FTDI, CP210x, PL2303, CH34x), use 230400 baud at most. A faster continuous
stream overflows the bridge over Wi-Fi. A board with native USB loses nothing.

## Use the bay's AUX UART

The node's J5 socket, marked AUX, carries a UART and two open-drain lines, RESET and BOOT. You reach the UART
over the network. Every client sees the board's output, and what any client types goes to the board. The UART
starts at 115200 8N1, with Enter sending CR. The node saves the settings you change.

Twister cannot read a board on the AUX UART: the board target of a DATA board's port cannot have `aux` as its
console.

### Over RFC 2217 or raw TCP

RFC 2217 takes one client, on TCP port 4001. The settings that client sets last until it disconnects.

```console
$ python -m serial.tools.miniterm rfc2217://bay-b3.local:4001 115200
```

```{code-block} yaml
:caption: a labgrid environment
NetworkSerialPort:
  host: bay-b3.local
  port: 4001
  speed: 115200
  protocol: rfc2217
```

Raw TCP takes one client, on TCP port 4000, at the saved settings: `nc bay-b3.local 4000`. On both ports, a
new client takes over from the one before.

To flash an ESP32 board on the AUX UART, set `"esptool_reset": true` with `POST /api/aux`. DTR and RTS then
work like an ESP32 board's auto-reset circuit:

```console
$ esptool --port 'rfc2217://bay-b3.local:4001' chip-id
```

### Over HTTP

```console
$ curl -s bay-b3.local/api/aux
$ curl -s -X POST bay-b3.local/api/aux -d '{"baud": 921600}'
$ curl -s -X POST bay-b3.local/api/aux/break -d '{"ms": 250}'
```

`POST /api/aux` sets and saves the baud rate, the format, what Enter sends and the local echo. Every field:
[Bay node HTTP API](../reference/node-api.md).

### In the node's shell

```console
uart:~$ bay aux 921600 8N1
uart:~$ bay aux send "help"
uart:~$ bay reset
uart:~$ bay boot
```

`bay aux` alone prints the settings and the clients. `bay reset` and `bay boot` pulse the AUX RESET and BOOT
lines ([Bay node shell](../reference/node-shell.md)).

## Wire the AUX lead

Make the lead from a 6-way JST PH housing and flying leads. These are J5's pins:

```{include} ../reference/cables.md
:start-after: <!-- site:aux-pinout -->
:end-before: <!-- /site:aux-pinout -->
```

The levels are 3.3 V, with no protection. A 5 V board's TX pushes about 1.1 mA into the node through the 1 kΩ
resistor. Wire GND, the node's TX to the board's RX, and the node's RX to the board's TX. Wire RESET and BOOT
if the board has those pins.

J5 is on the node, in the tray ([Take a bay apart](service-a-bay.md)). Route the lead beside the DATA lead,
through the drag chain ([Cables and pinouts](../reference/cables.md#aux-lead)).

:::{warning}
J5 (AUX) takes the same plug as J2 (ROW OUT), 22 mm away. On the last node of a row, J2 is empty and carries
the rack's 20 V on pin 6. An AUX lead pushed into J2 puts that voltage into your board.
:::

## If it does not work

| What you see | What to do |
|---|---|
| `no new /dev/serial/by-id entry (already attached, or no tty)` | The board was already attached, or it has no USB serial. `sudo usbip port` lists what you have attached. |
| The serial port vanishes at each reset | Keep `bayctl attach --follow` running. |
| Bytes lost through a serial bridge at high baud rates | Lower the baud rate. |
| `nc` or miniterm on port 4000 or 4001 is disconnected | Another client took the port over. |
| A connection to port 4000 or 4001 hangs, then times out | Your address does not have the console right, or someone has reserved the bay ([Control who can use the rack](access.md)). |
| Break answers `the DUT is powered off` | Power the board first. |

Anything else: [Troubleshooting](troubleshooting.md).
