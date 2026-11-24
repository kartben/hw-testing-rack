# Board targets

A board target is what a bay node remembers about the board on one of its ports: its Zephyr board, the west
runner that flashes it, its probe id, the console twister reads, and whether it goes in twister's hardware
map. `bayctl hwmap` builds the map from the targets of every node, and leaves out a port that has none
([Zephyr twister](twister.md)).

:::{status} simulated
The node's code runs on native_sim in its access test, as a node with one board. `bayctl`'s export and
import are tested against the simulated node, and the dialog below is the simulated node's. No target has
been saved on a v1.0 node. See [What exists today](../plan/status.md#status-board-targets).
:::

## What a board target holds

| On the page | API, lab file | Holds |
|---|---|---|
| Zephyr board | `board`, `platform` | the target as twister names it: `rpi_pico2/rp2350a/m33_0` |
| Runner | `runner` | the west runner; none: the board's default |
| Probe id | `probe_id`, `id` | what `west flash --dev-id` gets; none: the device's USB serial number |
| Console | `console` | where twister reads the board: `usb`, `usb:NN`, `aux`, `none` |
| In twister's hardware map | `map`, `ci` | off: `hwmap` leaves the board out |

The node keeps one target per port in its flash, across restarts and firmware updates, with the USB
identity of the device it was saved for. Set it once for each board, and again when another board takes
the port.

On a v1.0 rack every board sits on a port of a DATA board, so a target belongs to `B3.2`, never to `B3`. A
bench stand-in or the simulator can be a node with one board and no DATA board, whose one target is named
like the bay.

## Set it on the bay's page

In the **USB devices** card of `http://bay-b3.local/`, each port's row carries its target under the
device: the Zephyr board, the runner and **Edit**, or "No board target" and **Set board…**.

```{figure} ../img/web-ui-ports.png
:class: bb-screenshot
:alt: The USB devices card of bay B3, four port rows; B3.1 has a target and an Edit button, B3.2 a Set board button

Simulated node, a DATA ×4 bay. B3.1 has a target (`frdm_mcxn947/mcxn947/cpu0`, runner linkserver); B3.2 has
none yet. B3.3 is reserved by another address, so its **Edit** is greyed.
```

1. Click **Set board…** or **Edit**. The button needs the control right, and it is greyed while another
   address has reserved the port.
2. Under **Zephyr board**, pick one of the suggestions or type the target. The suggestions are the
   targets that the [board library](../reference/board-library.md) lists for the device's USB id, the
   exact id first, then the maker's wildcard (any J-Link is `1366:*`). One USB id can belong to several
   boards, as Espressif's 303a:1001 does below: say which one is on the port.
3. Leave **Runner** on the board's default, or choose another west runner.
4. Leave **Probe id** empty: it then stands for the device's USB serial number, so west flashes this
   board and not its neighbour. A device with no serial number needs the probe's own here.
5. Choose the **Console**, tick or untick **In twister's hardware map**, then **Save**. **Clear** removes
   the target.

```{figure} ../img/web-ui-board-target.png
:class: bb-screenshot
:alt: The board target dialog of B3.4: five suggested Zephyr boards, runner, probe id, console, a tick box and Save
:width: 480px

Simulated node. B3.4 holds a XIAO ESP32-C6 (USB id 303a:1001): five targets are suggested for that id, the
runner is the board's default, and the empty probe id shows the serial number it stands for.
```

The suggestions are compiled into the firmware from `mechanical/boards/boards.yaml`. For a device that no
family lists, the dialog says so and you type the target.

## Pinned to the device on the port

A target is saved for the device on the port at that moment: its USB id and its serial number. Put
another board on the port and the row shows "Another board in the slot" until that board's target is
saved; the dialog says which device the target was set for and which one is there now. `bayctl list` tags
the line `[not the board its target was saved for]`, and `hwmap` writes the entry as it is, with a warning.

The node compares serial numbers when the saved device had one, and USB ids otherwise
([boards.c](../../firmware/bay-node/src/boards.c)). Two boards of one model that carry serial numbers are
told apart; two that carry none are not. An empty port is not flagged.

## Which console

| Value | Twister reads |
|---|---|
| `usb` | the device's first serial port, `/dev/serial/by-id/usb-…-if02` on the host once the board is attached |
| `usb:NN` | the serial port on interface `NN`, two hex digits: for a probe with several serial ports |
| `aux` | the bay's AUX UART |
| `none` | nothing: `hwmap` writes the board with `connected: false` |

To find the interface number of a probe with several serial ports, attach the board and read the names:

```console
$ python tools/bayctl.py attach B3.2 --show
```

The names end in `-ifNN`. `bayctl` works the name out from the device's USB strings without attaching
anything: [Where the data comes from](../reference/bayctl.md#where-the-data-comes-from).

`aux` is refused on a port of a DATA board, which has no AUX line: the node answers "a DATA x4 port has no
AUX UART: its board's USB, or none", for a DATA ×6 as well. Only a node with one board, a stand-in or the
simulator, offers it. The dialog labels it "The bay's AUX UART (RFC 2217)", but twister reads the raw port
through `bayctl pty` ([Serial console](serial-console.md)).

## Keep a board out of twister's map

Untick **In twister's hardware map** for a board that CI must not flash: one kept for a person at the
bench, a bay left in classic mode for a laptop on its front port, a board flashed from its own Linux. The
row then shows "not in CI" and `bayctl list` tags the line `[not in CI]`. `ci: false` in the
lab file does the same without touching the node. A port that holds the bay's logic analyzer is never in
the map, whatever its switch says.

A board with two USB connectors, both plugged in, has two port names
([Put a board in a bay](mount-a-board.md)). Give the target to the port of its debug probe. The other port
must stay out of the map: with a device and no target it makes `hwmap` warn at every run, and with a
second target the board is in the map twice. Give that port `ci: false` in the lab file, or the same target
with the box unticked. This is worked out from [tools/bayctl.py](../../tools/bayctl.py); nobody has done it
yet.

## Back up and restore with bayctl

```console
$ python tools/bayctl.py export lab -o rack-targets.yaml
$ python tools/bayctl.py import lab rack-targets.yaml
$ python tools/bayctl.py import lab rack-targets.yaml B3.2 A1
```

`export lab` writes every target as the nodes hold it, in the form of the lab file, with the device it is
pinned to. From the simulated node, with a XIAO on B3.1:

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

`console` is written when it is not `usb`, and `ci: false` for a board out of the map. When no node
answered, or none holds a target, the command stops with "no board target read from the rack".

`import lab` writes the entries back, each with its pin, so a restored port still flags another board on
it. An entry without a pin is pinned to the device on the port now. Without names it takes every entry
that has a `platform:`; with names, those ports, or every port of a bay named whole. It needs the control
right and is refused while another host has reserved the port. It prints one line per port and exits with
1 if an entry failed:

```text
B3.1: xiao_esp32c3 (runner esp32), pinned to 303a:1001 S/N 34:85:18:9A:3C:10
```

Any lab file with `platform:` entries can be imported, a hand-written one included, which sets the
targets of a whole rack from a file.

The backup holds the board targets and nothing else: no bay ids, no Wi-Fi credentials, no camera settings.
The access rules live in the lab file, from which they are pushed and never read back. What else a node
keeps, and how to wipe it: [Recover a node or a hub](recover.md).

## Over HTTP

```console
$ curl -s bay-b3.local/api/boards
$ curl -s bay-b3.local/api/ports/2/board
$ curl -s -X PUT bay-b3.local/api/ports/2/board -d '{"board":"rpi_pico2/rp2350a/m33_0","runner":"uf2","console":"usb","map":true}'
```

`GET /api/boards` gives every port of the node: its target, the device it is pinned to, the device there
now with its USB strings and serial ports, and `mismatch`. `PUT` saves a target for the device on the port
now, or for the device named by `"pin": {"vid", "pid", "serial"}`; a body without `board` clears it. `PUT`
needs the control right and answers 423 while another address has reserved the port.

Firmware 0.5 keeps four targets per node and registers `/api/ports/<n>/board` for ports 1 to 4
([bay.h](../../firmware/bay-node/src/bay.h), [web.c](../../firmware/bay-node/src/web.c)). Ports 5 and 6 of
a DATA ×6 cannot hold a target on the node: give them one in the lab file. That reading comes from the
code alone, since the simulated node of a DATA ×6 takes a target on ports 5 and 6 and `bayctl`'s tests stop
at four ports. Every field and status code: [Bay node HTTP API](../reference/node-api.md).

## Override in the lab file

For each key the lab file wins, then what the node holds, then the defaults of the board's family in the
board library. An entry under `bays.B3.2` changes what `bayctl` uses without touching the node:

```{code-block} yaml
:caption: config/lab.yaml
bays:
  B3.2:
    runner: openocd          # another runner than the node's
    serial: /dev/ttyACM0     # another path than the name bayctl derives
```

`serial`, `baud`, `fixtures`, `product`, `board` and `role: analyzer` (the port that holds the bay's logic
analyzer) exist only there. An entry also stands in for a node that does not answer. Every key, and the
order for each: [lab.yaml](../reference/lab-yaml.md#which-source-wins).
