# Zephyr twister

`bayctl hwmap` writes a twister hardware map from what the rack holds: one entry per board, each with a
pre-script that powers the board, attaches its USB device and waits for its console before every test.

:::{status} simulated
The map and its scripts are generated in `bayctl`'s tests against the simulated node, and in the
repository's CI from the example lab file. Twister has never run with such a map, against a rack or against
a stand-in. See [What exists today](../plan/status.md#status-twister).
:::

Needs: a Linux machine set up as on [Set up bayctl and usbip](set-up-your-machine.md), the sudo rule
included, because the pre-script runs `sudo -n usbip`; and a [board target](board-targets.md) on each
port.

## Generate the hardware map

```console
$ python tools/bayctl.py hwmap -o rack-map.yaml
```

`hwmap` asks the hub for the nodes and each node for its ports, then writes the map and, in a folder
`rack-scripts` beside it, one script per board: `bay-b3-2-pre.sh` for B3.2. It ends with
`wrote rack-map.yaml (N boards) and pre-scripts in <folder>`. Each board it left out or has a doubt about
is a line `warning:` on stderr; the exit code stays 0. Make the map again when a board moves or changes,
rather than editing it.

| Option | Effect |
|---|---|
| `-o FILE` | the map; `rack-map.yaml` in the current directory by default |
| `--scripts DIR` | where the scripts go, instead of `rack-scripts` beside the map |
| `--python PYTHON` | the interpreter the scripts call; by default the one that runs `hwmap`, by its full path |
| `--power-cycle` | the pre-script power-cycles the board before every test, for a clean state each time |
| `--lease DURATION` | each test reserves its board: see the last section |

The map and the scripts hold absolute paths to that Python, to `bayctl`, to the lab file when there is one
and to the scripts: make them on the machine that runs twister.

With no hub and no node in reach, the map comes from the lab file's entries alone. The repository's CI
does this with the example lab file, which gives 7 boards and 8 warnings; the command is on
[Try it without hardware](../plan/try-it-without-hardware.md). That file predates the DATA ×6: its A1 to
A4, B2 and B4 hold one board on the node, a form a v1.0 rack does not have, so its map begins with `A1`
where a v1.0 rack's would begin with `A1.1`. The Pico 2's warning in it, `AUX BOOT to TP6, AUX RESET to
RUN`, is the wiring of a one-board bay: on a DATA ×4 port it means the port's own BOOT line to TP6 and its
RESET line to RUN ([USB/IP and flashing](usb-and-flashing.md#uf2-boards-and-esp32-boards)).

## Run twister, and what a run leaves behind

```console
$ west twister --device-testing --hardware-map rack-map.yaml -p xiao_esp32c3 -T samples/hello_world
```

Twister then handles the rack's boards as boards plugged into the machine: before each test it runs the
entry's pre-script, then flashes with west and reads the console. Which probes and bootloaders work
through USB/IP, at full speed, decides what may go in the map: [USB/IP and flashing](usb-and-flashing.md)
lists them. A board flashed with `uf2`, such as a Pico 2, also needs its bootloader's drive mounted on this
machine and its BOOT line wired; keep it out of the map until a flash by hand works.

When the run ends, every board it tested is still attached to your machine and powered, after a run from a
laptop as after a CI job ([What a job leaves behind](ci-host.md#what-a-job-leaves-behind)).

## One entry, field by field

```{code-block} yaml
:caption: rack-map.yaml, the entry of B3.1 from the example lab file, the map made in /ci
- connected: true
  platform: xiao_esp32c3
  product: Seeed Studio XIAO (any) (bay B3.1)
  runner: esp32
  id: /dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_34:85:18:9A:3C:10-if00
  serial: /dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_34:85:18:9A:3C:10-if00
  baud: 115200
  pre_script: /ci/rack-scripts/bay-b3-1-pre.sh
  script_param:
    pre_script_timeout: 90
  fixtures:
  - bay:B3.1
  - node:B3
```

| Field | Where it comes from |
|---|---|
| `connected` | `true`; `false` for a board with no console path, which keeps it out of the tests. `true` says only that a path is known: a lab file's `serial:` gives one with the node off |
| `platform` | the Zephyr board of the port's target |
| `product` | `product` in the lab file or in the board's family, else the family's name and the port's |
| `runner` | the target's runner, else the default of its family |
| `id` | the target's probe id; else, for the `esp32` runner, the console's path; else the USB serial number of the device on the port, or of the device the target is pinned to |
| `serial` | the console's path under `/dev/serial/by-id`, worked out from the device's USB strings, or `serial:` in the lab file |
| `baud` | `baud` in the lab file, else the family's, else 115200 |
| `pre_script` | the script that prepares this board; with `--lease`, a `post_script` follows it |
| `script_param` | twister stops the pre-script after 90 s |
| `fixtures` | `bay:` and the port's name; `node:` and the bay, for a port of a DATA board; then `fixtures:` of the lab file |

Every board of the run is attached to the same machine, so two boards with the same kind of probe show up
as two probes at once and the runner picks its board by `id`. An empty probe id on the target stands for
the device's USB serial number. For the `esp32` runner the serial port is the id,
and `bayctl` fills it in. `hwmap` warns when two or more boards with the same runner end up without an id.

`serial` is the name udev will give the console once the board is attached; `bayctl` computes it without
attaching anything ([Where the data comes from](../reference/bayctl.md#where-the-data-comes-from)).

A board whose console is `aux` gets `serial_pty` in place of `serial`: the command `bayctl pty <bay>`,
which joins the pty twister gives it to the node's raw AUX port. Only a node with one board can have that
console, so no entry of a v1.0 rack carries it ([Board targets](board-targets.md#which-console)). Twister
splits the command on spaces and commas: keep the paths of Python and of the checkout free of both.
`bayctl pty` sets no baud rate and uses the AUX settings saved on the node: set the baud rate once, on the
web console or with `bay aux <baud>` ([Serial console](serial-console.md)).

## What the pre-script does, and when it fails

```{code-block} sh
:caption: rack-scripts/bay-b3-1-pre.sh, made with --python python3 from a checkout in /ci/rack
#!/bin/sh
# Generated by tools/bayctl.py hwmap: bay B3.1 (Seeed Studio XIAO (any)) before each test.
exec python3 /ci/rack/tools/bayctl.py prepare B3.1
```

With a lab file, `--lab` and its full path come before `prepare`. `prepare B3.1` does this, in order:

1. With `--lease`, it reserves the port for this machine, or renews the reservation.
2. It switches the bay to USB/IP mode if the bay is in classic mode.
3. It powers the port on if the port is off or latched after an over-current. With `--power-cycle` it
   detaches the board and cycles the port for 1000 ms instead.
4. It waits until the node has enumerated a USB device on the port, 30 s at most.
5. It runs `usbip attach`, unless the device is already attached.
6. It waits for the console's path to exist, 30 s at most.

The script carries its paths and none of the environment: it finds the hub the way the `hwmap` run did
only if `BAYCTL_HUB`, and `BAYCTL_USBIP`, are the same when twister runs.

Step 3 sends a plain power-on, never a queued one. A port that was shed, or that waits for its turn,
answers 409 while the bay has no room: `prepare` exits with 1 and the test has no board to flash. On the
default grant four boards may not all be on in a DATA ×4 bay, and ports 5 and 6 of a DATA ×6 cannot be
switched at all on firmware 0.5 ([How many boards a bay gives a job](ci-host.md#how-many-boards-a-bay-gives-a-job-on-firmware-05)).

When a step fails, `prepare` exits with 1 and prints one line on stderr: `bayctl:`, the port, and one of
these, after the API path when it is the node that refused:

| Message | The step that failed |
|---|---|
| `409 no room in the bay's budget: the bay draws …` | 3: the bay's share is used up |
| `423 …` | 1 or 3: another address has reserved the port or the bay |
| `no USB device enumerated on the DUT port after 30 s` | 4: the node saw no device on the port |
| `<busid> is not exported (is the board powered and enumerated?)` | 5: the node does not export the port's device |
| `sudo -n usbip …`, then sudo's or usbip's own message | 5: the sudo rule, or `usbip` itself |
| `/dev/serial/by-id/… did not appear` | 6: the console's path never showed up on this machine |

A pre-script that runs into twister's 90 s, and what to look at for each of these:
[Troubleshooting](troubleshooting.md).

## Boards left out of the map, and why

`hwmap` writes no entry for:

- a port whose target is out of the map: the page's switch, or `ci: false` in the lab file;
- the port of the bay's logic analyzer, whatever its switch says;
- an empty port of a DATA board;
- a port with a device and no target. This one is warned about, with the address of the page to set it on.

It writes the entry with `connected: false`, and a warning, for a board that has no console path: it was
powered off or still enumerating when the map was made, it has no serial port on the interface its console
names, or its console is `none`. `serial:` in the lab file gives a path by hand. Twister passes over such an
entry, and `hwmap` still exits 0: a job checks the map itself
([A whole job](ci-host.md#a-whole-job-from-checkout-to-results)).

It writes the entry as it is, and warns, when the device on the port is not the one the target was saved
for ([Board targets](board-targets.md#pinned-to-the-device-on-the-port)). Some families of the board
library carry a note that `hwmap` prints as a warning at every run: the Pico 2's says that it has no
on-board probe and that `uf2` needs BOOTSEL.

## Pin a test to a bay, reserve the bays for the run

`--fixture bay:B3.2` pins a test to one board. `node:B3` names any board of
bay B3. Add your own per port, under `fixtures:` in the [lab file](../reference/lab-yaml.md).

```console
$ python tools/bayctl.py hwmap -o rack-map.yaml --lease 30m
```

With `--lease`, the pre-script reserves the board before each test (`prepare B3.2 --lease 30m`) and the
entry gains a `post_script`, which runs `bayctl release B3.2`. Every test renews the reservation, so the
duration needs to cover one test, however long the run. A reservation of one port does not keep another
host off the board's USB/IP: a job that shares the rack reserves the whole bay instead, before `hwmap`, and
makes the map without `--lease` ([Two hosts on one rack](ci-host.md#two-hosts-on-one-rack)). How to end a
reservation that a dead job left: [Reserve a bay](reserve-a-bay.md).
