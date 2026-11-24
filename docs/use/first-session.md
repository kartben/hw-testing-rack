# A first session with a bay

This page takes one board from the drawer to its serial console on your Linux machine. The example is a Seeed
Studio XIAO ESP32-C3 on port 1 of bay B3, which has a DATA ×4. Its name in the rack is `B3.1`. With your own
bay, port and board, the steps are the same.

To rehearse the session with no hardware, run a simulated bay first
([Try it without hardware](../plan/try-it-without-hardware.md)).

## What you need

- A rack whose hub answers at `rack.local`. If someone else built it, see
  [Take over a rack](take-over-a-rack.md).
- A Linux machine with a checkout of the repository, `usbip` and its sudo rule
  ([Set up your machine](set-up-your-machine.md)).
- A Zephyr workspace with `west` on that machine. Run every command below with its virtual environment active.
- A XIAO ESP32-C3, and a short USB-C to USB-C cable with straight plugs.

If you share the rack, reserve the bay first. Other machines then cannot use its boards
([Reserve a bay](reserve-a-bay.md)):

```console
$ python tools/bayctl.py lease B3 --for 1h
```

The reservation belongs to your Linux machine's address. Open the bay's page from that machine too: from any
other, its buttons are greyed out. On a machine without a browser, set the board target below with `curl`
([Set it over HTTP](board-targets.md#set-it-over-http)).

## Put the board in the drawer

1. Pull out the drawer of B3. The drag chain keeps it connected.
2. Set the XIAO on the plate between its pegs ([Put a board in a bay](mount-a-board.md)).
3. Plug its cable into port 1 of the DATA ×4. The port number is printed in a filled disc to the left of
   each socket.
4. Push the drawer back in.

## Check that it is powered

Every port switches on when the bay node starts. List the bay's ports:

```console
$ python tools/bayctl.py ports B3
```

The line for `B3.1` shows `VBUS on`, the current, the USB id `303a:1001` and the busid `1-1.1`, the board's
address for USB/IP. If the port is off, switch it on with `python tools/bayctl.py power B3.1 on`
([Power-cycle or reset a board](power-and-reset.md)).

## Tell the bay which board it is

Open `http://bay-b3.local/`. In the **USB devices** card, the row of B3.1 says *No board target*. Click
**Set board…** and choose `xiao_esp32c3`. Leave the runner on the board's default, `esp32`, and the console on
the device's own USB serial. Then click **Save**.

```{figure} ../img/web-ui-board-target.png
:class: bb-screenshot
:alt: The board target dialog of the bay's page
:width: 480px

The board target dialog on a simulated bay, here for a XIAO ESP32-C6 on B3.4. Pick the target from the
suggestions for the device's USB id.
```

The node keeps this target for the board. `bayctl list` and twister read it ([Board targets](board-targets.md)).

## Attach its USB

In a second terminal, run this and leave it running:

```console
$ python tools/bayctl.py attach B3.1 --show --follow
B3.1: /dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_34:85:18:9A:3C:10-if00
```

`bayctl` looks up the port's busid, runs `usbip attach` and prints the name of the board's serial port. Yours
ends in your board's MAC address. With `--follow`, `bayctl` attaches the board again each time its USB device
comes back after a reset ([USB/IP and flashing](usb-and-flashing.md)).

## Flash it with west

In the first terminal, from the `zephyr` directory of your workspace:

```console
$ west build -b xiao_esp32c3 samples/subsys/shell/shell_module
$ west flash --esp-device /dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_34:85:18:9A:3C:10-if00
```

The XIAO ESP32-C3 has USB in its chip. esptool puts it in its loader over that USB, with no wire, and Zephyr
uses the same USB serial for its console.

## Open its console

```console
$ python -m serial.tools.miniterm /dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_34:85:18:9A:3C:10-if00 115200
```

Press Enter: the board's shell answers with its `uart:~$` prompt. Type `kernel version`. This is the board's
own USB serial, reaching your machine over USB/IP ([Serial console](serial-console.md)). Ctrl-] quits miniterm.

## Hand the bay back

Stop `attach --follow` with Ctrl-C, then:

```console
$ python tools/bayctl.py detach B3.1
detached 1 device(s)
$ python tools/bayctl.py release B3
B3 released
```

The board stays powered. To switch it off, run `python tools/bayctl.py power B3.1 off`. The port comes on again
the next time the node restarts.

To run the same board under twister, see [Run twister on the rack](twister.md). A Pico 2 or another UF2 board
takes a few more steps ([UF2 boards and ESP32 boards](usb-and-flashing.md#uf2-boards-and-esp32-boards)).
