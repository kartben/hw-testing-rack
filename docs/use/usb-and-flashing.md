# USB/IP and flashing

Each bay node shares its boards' USB over the network with USB/IP. Attach a board from a Linux machine, and
its probe and serial port appear there as local USB devices: `west flash` works as it does on your desk.

You need a Linux machine with `usbip`, the `vhci-hcd` module and a sudo rule for `usbip`
([Set up your machine](set-up-your-machine.md)),
and your boards' usual flashing tools and udev rules. From macOS or Windows, see
[On macOS or Windows](#on-macos-or-windows).

## In the browser

A browser cannot attach a USB device, but the bay's page gives you the command.

```{figure} ../img/web-ui-ports-attach.png
:class: bb-screenshot
:alt: Two port rows: B3.1, an MCU-Link attached by 192.168.1.41 for 12 min; B3.2, an FT232R ready to attach

A simulated node. Under each port's name: its busid, and who has attached the board.
```

Each row of the **USB devices** card names the device on that port. **Copy attach** copies the
`sudo usbip attach` command for it.

## With bayctl

```console
$ python tools/bayctl.py attach B3.1 --show
B3.1: /dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_34:85:18:9A:3C:10-if00
$ python tools/bayctl.py detach B3.1
```

`attach` finds the port's busid, runs `usbip attach` and waits for the board's serial ports. `--show` prints
their names.

- `attach B3.2 --follow` stays running and attaches the board again each time it resets.
- `attach B3` attaches every board in the bay.
- `prepare B3.2` gets a board ready for a test runner: it powers the port, waits for the board, attaches it
  and waits for its console ([Run twister on the rack](twister.md)).

These commands run on Linux only. Every option: [bayctl](../reference/bayctl.md#attach-and-detach).

## With usbip

```console
$ usbip list -r bay-b3.local
$ sudo usbip attach -r bay-b3.local -b 1-1.2
```

The busid depends on the DATA board in the bay:

| In the bay | busid of port n | B3.2 is |
|---|---|---|
| a DATA ×4 | `1-1.n` | `1-1.2` |
| a DATA ×6 | `1-1.6` for port 1, then `1-1.(n − 1)` | `1-1.1` |

`sudo usbip port` lists what you have attached, and `sudo usbip detach -p <port>` drops one.

## Flash with west

Get the board ready with `prepare`, then flash as you would on your desk:

```console
$ python tools/bayctl.py prepare B3.2
$ west flash
```

With several boards of the same kind attached, tell the runner which probe to use: `west flash --dev-id` with
the probe's serial number. The bay's [board target](board-targets.md) keeps that number for twister.

If the board's USB device goes away at each reset, keep `bayctl attach --follow` running in another terminal.

## UF2 boards and ESP32 boards

You flash a UF2 board, such as a Pico 2 on B3.2, by copying a file onto its bootloader's USB drive. West's `uf2`
runner does the copy, so the drive must be mounted on your machine.

1. Put the board in its bootloader. A blank Pico 2 starts there. For a Pico 2 that runs an application, wire
   its BOOTSEL test pad, TP6, to the BOOT pin of its DATA ×4 port, then run
   `python tools/bayctl.py boot B3.2 --power-cycle`
   ([Reset and bootloader](power-and-reset.md#reset-and-bootloader)).
2. In a second terminal, run `python tools/bayctl.py attach B3.2 --follow` and leave it running.
3. If your desktop does not mount the drive, mount it yourself. A Pico 2's drive is named `RP2350`:

   ```console
   $ sudo mkdir -p /mnt/rp2350
   $ sudo mount -o uid=$(id -u) /dev/disk/by-label/RP2350 /mnt/rp2350
   ```

4. Build and flash. The `cdc-acm-console` snippet puts Zephyr's console on the board's own USB:

   ```console
   $ west build -b rpi_pico2/rp2350a/m33_0 -S cdc-acm-console samples/hello_world
   $ west flash --runner uf2
   ```

The board then restarts into the application as another USB device. `attach --follow` attaches it and prints
its serial port, `usb-Zephyr_Project_CDC_ACM_serial_backend_<serial number>-if00`.

An ESP32 board with USB in the chip, such as a XIAO ESP32-C3, needs no wire: esptool puts it in its loader.
Name it by its serial port: `west flash --esp-device /dev/serial/by-id/…`
([A first session with a bay](first-session.md)).

An ESP32 board behind a USB-serial bridge flashes at 115200 or 230400 baud. Faster rates overflow the bridge
over Wi-Fi.

## Which probes and devices work

| Device | Over USB/IP |
|---|---|
| ST-LINK, J-Link, CMSIS-DAP v2 (such as an MCU-Link) | yes |
| CMSIS-DAP v1 (HID), such as the UNO R4 WiFi's probe | no |
| FTDI, CP210x, PL2303 and CH34x serial bridges | yes, up to 230400 baud |
| A board's own USB serial (CDC ACM), mass storage | yes |
| Audio, video and low-speed devices | no |

## Speed and limits

A bay's USB runs at full speed, 12 Mbit/s, shared by all its boards. A node serves six devices at once, and
each device takes one client. Across the rack, plan on at most eight flashes at once
([Wi-Fi for the rack](wifi.md#how-many-boards-may-flash-at-once)).

## On macOS or Windows

The power, reset and status commands of `bayctl` work wherever Python runs. To attach a board, you need a
USB/IP client. On Windows, use WSL2 with the `vhci_hcd` module. macOS has no USB/IP client: plug your laptop
into the bay's front port instead ([Front port and classic mode](front-port.md)).

## If it does not work

| What you see | Why |
|---|---|
| `usbip attach` hangs, then times out | Your address does not have the usbip right, or someone has reserved the bay ([Control who can use the rack](access.md)). |
| `bayctl: B3.2: 1-1.2 is not exported …` | The port is off, the board has not enumerated, or the bay is in classic or SERVICE mode ([Front port and classic mode](front-port.md)). |
| `sudo: a password is required` | The sudo rule for `usbip` is missing ([Set up your machine](set-up-your-machine.md)). |
| The device vanishes at each reset | Run `attach --follow`. |
| Another machine attached a board you reserved | A reservation of one port does not cover USB/IP. Reserve the whole bay ([Reserve a bay](reserve-a-bay.md)). |
| `Invalid SLIP escape` or `Corrupt data` from esptool | The serial bridge overflowed. Lower the baud rate. |

Anything else: [Troubleshooting](troubleshooting.md).
