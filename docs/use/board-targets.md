# Board targets

A board target tells a bay which Zephyr board is on a port, how to flash it and where to read its console. The
bay node stores it. `bayctl list` and twister's hardware map read it. `bayctl hwmap` leaves a port without a
target out of the map ([Run twister on the rack](twister.md)).

## What a board target holds

| On the page | In the API and the lab file | Holds |
|---|---|---|
| Zephyr board | `board`, `platform` | the target as twister names it, such as `rpi_pico2/rp2350a/m33_0` |
| Runner | `runner` | the west runner; empty: the board's default |
| Probe id | `probe_id`, `id` | what `west flash --dev-id` gets; empty: the device's USB serial number |
| Console | `console` | where twister reads the board: `usb`, `usb:NN` or `none` |
| In twister's hardware map | `map`, `ci` | off: `hwmap` leaves the board out |

A target belongs to a port, such as `B3.2`. The node keeps one per port, across restarts and firmware updates.
Set it once for each board, and again when another board takes the port.

The node keeps targets for ports 1 to 4. Give ports 5 and 6 of a DATA ×6 their targets in the lab file
([Limitations](../reference/known-limitations.md#the-firmware)).

## Set it on the bay's page

In the **USB devices** card of `http://bay-b3.local/`, each port's row shows its target under the device: the
Zephyr board, the runner and **Edit**. A port without one shows *No board target* and **Set board…**.

```{figure} ../img/web-ui-ports-attach.png
:class: bb-screenshot
:alt: Two port rows: B3.1 with the target frdm_mcxn947/mcxn947/cpu0, runner linkserver and Edit; B3.2 with No board target and Set board

Ports 1 and 2 of a DATA ×4 bay on a simulated node. B3.1 has a target; B3.2 has none yet.
```

1. Click **Set board…** or **Edit**. When access rules are on, your machine needs the `control` service
   ([Control who can use the rack](access.md)). The button is greyed out while another machine has reserved
   the port.
2. Under **Zephyr board**, pick a suggestion or type the target. The suggestions are the targets that the
   [board library](../reference/board-library.md) lists for the device's USB id. One USB id can belong to
   several boards, as Espressif's `303a:1001` does below: choose the one on the port. For a device the library
   does not list, type the target.
3. Leave **Runner** on the board's default, or choose another west runner.
4. Leave **Probe id** empty. West then uses the device's USB serial number, so it flashes this board and not its
   neighbour. For a device without a serial number, enter the probe's own id.
5. Choose the **Console**, tick or untick **In twister's hardware map**, then click **Save**. **Clear** removes
   the target.

```{figure} ../img/web-ui-board-target.png
:class: bb-screenshot
:alt: The board target dialog of B3.4: five suggested Zephyr boards, runner, probe id, console, a tick box and Save
:width: 480px

The dialog for a XIAO ESP32-C6 on B3.4, on a simulated node. Its USB id, `303a:1001`, matches five targets.
```

## When you change the board on a port

A target is saved for the device that is on the port at that moment, by its USB id and serial number. If you put
another board on the port, its row shows *Another board in the slot* until you save a target for it. Meanwhile,
`bayctl list` tags the line `[not the board its target was saved for]`. `hwmap` still writes the entry, with a
warning.

The node compares serial numbers when the saved device had one, and USB ids otherwise. So it tells two boards of
the same model apart only if they have serial numbers. An empty port is not flagged.

## Choose the console

| Value | Twister reads |
|---|---|
| `usb` | the device's first serial port, under `/dev/serial/by-id/` on the host once the board is attached |
| `usb:NN` | the serial port on interface `NN`, two hex digits, for a probe with several serial ports |
| `none` | nothing: `hwmap` writes the board with `connected: false` |

To find the interface number, attach the board and read the names of its serial ports. They end in `-ifNN`:

```console
$ python tools/bayctl.py attach B3.2 --show
```

A fourth value, `aux`, is the bay's AUX UART. The node refuses it on a DATA board's port, with "console: a DATA
x4 port has no AUX UART: its board's USB, or none" ([Serial console](serial-console.md)).

## Keep a board out of twister's map

Untick **In twister's hardware map** for a board that CI must not flash. For example, a board kept for someone
at the bench, or a bay left in classic mode for a laptop on its front port ([Front port and classic mode](front-port.md)). Its
row then shows *not in CI*, and `bayctl list` tags its line `[not in CI]`. `ci: false` in the lab file does the
same without touching the node. A port that holds the bay's logic analyzer is never in the map.

A board with two USB connectors has two ports. Give the target to the port of its debug probe, and give the
other port `ci: false` in the lab file. Otherwise `hwmap` warns about that port at every run.

## Back up and restore with bayctl

```console
$ python tools/bayctl.py export lab -o rack-targets.yaml
$ python tools/bayctl.py import lab rack-targets.yaml
$ python tools/bayctl.py import lab rack-targets.yaml B3.2 A1
```

`export lab` writes every target the nodes hold as a lab file, each with the device it was saved for. From a
simulated node with a XIAO on B3.1:

```{code-block} yaml
:caption: rack-targets.yaml
# bayctl export lab, 2026-11-24 04:20: the board targets the rack's nodes hold.
# Put them back with: python tools/bayctl.py import lab FILE [BAY ...]
bays:
  B3.1:
    platform: xiao_esp32c3
    runner: esp32
    pin:
      vid: 303a
      pid: '1001'
      serial: 34:85:18:9A:3C:10
```

`import lab` writes the entries back to the nodes. An entry without a `pin` is saved for the device on the port
now. With no names, it imports every entry that has a `platform:`. With names, as in the third command, it
imports only those ports or bays. It needs the `control` service, and it is refused on a port that another
machine has reserved. It prints one line per port and exits with 1 if an entry failed.

Any lab file with `platform:` entries works. You can write one to set the targets of a whole rack at once.

The file holds the board targets and nothing else. It does not save bay ids, Wi-Fi credentials or camera
settings ([Recover a node or the hub](recover.md)).

## Set it over HTTP

```console
$ curl -s bay-b3.local/api/boards
$ curl -s -X PUT bay-b3.local/api/ports/2/board -d '{"board":"rpi_pico2/rp2350a/m33_0","runner":"uf2","console":"usb","map":true}'
```

`GET /api/boards` gives every port's target, the device it was saved for and the device on the port now. `PUT`
saves a target for the device on the port now. A body without `board` clears it. `PUT` needs the `control`
service, and answers 423 while another machine has reserved the port ([Bay node HTTP API](../reference/node-api.md)).

## Override in the lab file

An entry under `bays.B3.2` in `config/lab.yaml` changes what `bayctl` uses, without touching the node:

```{code-block} yaml
:caption: config/lab.yaml
bays:
  B3.2:
    runner: openocd          # another runner than the node's
    serial: /dev/ttyACM0     # another path than the name bayctl derives
```

For each key, the lab file wins over the node, and the node wins over the defaults of the board's family in the
board library. `serial`, `baud`, `fixtures`, `product`, `board` and `role: analyzer` exist only in the lab file.
An entry also stands in for a node that does not answer. Every key is on [lab.yaml](../reference/lab-yaml.md).
