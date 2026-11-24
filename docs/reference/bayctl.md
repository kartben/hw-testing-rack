# bayctl

`bayctl` drives the rack from a laptop or a CI host. It is one script,
[tools/bayctl.py](../../tools/bayctl.py), that you run from a checkout of the repository. To install what it
needs and give it the admin key, see [Set up your machine](../use/set-up-your-machine.md).

## Synopsis

```text
python tools/bayctl.py [--lab FILE] COMMAND ...

Look at the rack
  list [--probe]
  status BAY
  ports BAY

Power, reset and mode
  power BAY on|off|cycle [--ms 1000]
  power PORT on --when available | --wait SECONDS
  power PORT cancel
  reset BAY [--ms 100]
  boot BAY [--power-cycle]
  mode BAY usbip|classic

USB/IP, on Linux
  attach BAY [--show] [--follow]
  detach BAY

Reservations
  lease BAY [--for 1h] [--note TEXT]
  release BAY [--force]                             # --force: admin key

Access
  access show BAY
  access push [BAY ...]                             # admin key
  access claim BAY [BAY ...]                        # admin key
  access kick BAY ID                                # admin key
  access keygen

Board targets
  export lab [-o FILE]
  import lab FILE [BAY ...]

Test frameworks
  prepare PORT [--power-cycle] [--timeout 30] [--lease DURATION]
  pty BAY
  hwmap [-o rack-map.yaml] [--scripts DIR] [--python PYTHON]
        [--power-cycle] [--lease DURATION]
  export labgrid|pdudaemon [--python python3] [-o FILE]
  power-port N on|off|cycle

Firmware
  update IMAGE BAY [BAY ...] | --all | --hub        # admin key
         [--force] [--timeout 420]
  coproc load BAY FILE.uf2 [--name NAME]            # admin key
  coproc status BAY

DATA ×4
  wire BAY [BUS=PINS ...] [--name BUS=NAME] [--open-all]
  capture BAY [--ch A,B] [--rate 10M] [--duration all] [--pre 20]
          [--trigger A:fall | --reset PORT] [--decode SPEC ...]
          [--timeout 10] [-o NAME]

Rows and the hub
  row A|B|C|D on|off|cycle [--ms 1000]              # admin key
  hub [status | events]
  hub enumerate | pd epr|20v | claim                # admin key
  hub node TARGET ACTION                            # admin key
```


`BAY` is a bay (`B3`) or one of its ports (`B3.2`). `PORT` must be a single port. The numbers shown are the
defaults. The commands marked `# admin key` read the rack's admin key from the `BAYCTL_KEY` variable.

## Bays and ports

`B3.2` is port 2 of bay B3. The ports are numbered 1 to 4 on a DATA ×4 and 1 to 6 on a DATA ×6
([Bays, ports and addresses](../use/names.md)).

- Given a bay, `power` acts on every port. `reset`, `boot`, `attach` and `detach` act on the bay's boards.
  They skip the empty ports and the analyzer.
- `status`, `ports`, `mode`, `access`, `update`, `coproc`, `wire` and `capture` act on the whole node.
- `prepare` and `pty` need one board.
- `power`, `reset`, `boot` and `import lab` do not reach ports 5 and 6 of a DATA ×6
  ([Limitations](known-limitations.md#the-firmware)).

In the help texts, a *sub-slot* is a port and the *DUT* is the board.

## Look at the rack

### list

Prints one line per board, in rack order. It covers every node the hub knows and every bay in the lab file.
Each line gives the board's name, family, Zephyr target, runner and console, and the node's address.

| Tag | Means |
|---|---|
| `[not in CI]` | kept out of twister's map (`ci: false` in the lab file, or the map switch off on the bay's page) |
| `[analyzer]` | the port holds the logic analyzer |
| `[not the board its target was saved for]` | another USB device is on the port |

`--probe` adds `VBUS on|off <n> mA`, or `unreachable`, to each line.

### status and ports

`ports` prints one line per port: its power, its current, its USB device (VID:PID and busid) and the machine
that has the device attached. `status` prints the same lines, with a line about the node before them. After
them it lists every USB device with its name, maker, serial number and classes.

```console
$ python tools/bayctl.py list --probe
$ python tools/bayctl.py ports B3
```

## Power, reset and mode

### power

`cycle` switches the power off for `--ms`. It then waits until VBUS falls under 1 V, for 2 s at most, before
it switches the power back on.

A power-on fails (HTTP 409, exit code 1) when the bay's power budget has no room. On a port of a DATA board
you can queue it instead:

- `--when available` queues it and exits with 0. The port goes on by itself when there is room.
- `--wait SECONDS` queues it and waits for the port to come on. After `SECONDS` it cancels the request and
  exits with 1.
- `cancel` or `off` withdraws a queued request.

See [Power budget and queued ports](../use/power-budget.md).

```{tool-help} tools/bayctl.py power
```

```console
$ python tools/bayctl.py power B3.2 cycle --ms 2000
$ python tools/bayctl.py power B3.4 on --wait 600
```

### reset and boot

`reset` pulses the board's RESET line for 100 ms, or for `--ms`. `boot` holds BOOT across a RESET pulse. This
starts the ROM bootloader of most MCUs. Only the ports of a DATA ×4 have these lines. On a DATA ×6 port, the
command answers `this port has no such line`.

```{tool-help} tools/bayctl.py boot
```

```console
$ python tools/bayctl.py boot B3.3 --power-cycle
```

### mode

Sets the whole bay to `usbip` or `classic`. The node keeps this setting after a restart
([Front port and classic mode](../use/front-port.md)).

## USB/IP

### attach and detach

Both commands work on Linux only. They run `usbip` through `sudo -n`.

`attach` attaches the port's device by its busid. It then waits up to 10 s for a new name to appear under
`/dev/serial/by-id`. It leaves a device that is already attached alone. With `--follow`, it tries again every
2 s, so a board that drops off the bus after a reset comes back. Stop it with Ctrl-C. See
[USB/IP and flashing](../use/usb-and-flashing.md).

```{tool-help} tools/bayctl.py attach
```

```console
$ python tools/bayctl.py attach B3.2 --show
$ python tools/bayctl.py attach B3 --follow
```

## Reservations

### lease and release

`lease B3` reserves the whole bay for your machine's address. `lease B3.2` reserves one port. `--for` takes
a number of seconds, or a duration such as `90s`, `15m` or `2h`, from 10 s to 24 h. Run the command again to
renew the reservation. While it lasts, another machine gets HTTP 423. See
[Reserve a bay](../use/reserve-a-bay.md).

```{tool-help} tools/bayctl.py lease
```

```{tool-help} tools/bayctl.py release
```

```console
$ python tools/bayctl.py lease B3.2 --for 30m --note "twister job 8812"
$ python tools/bayctl.py release B3.2
```

## Access

### access

| Command | What it does |
|---|---|
| `access show B3` | Prints your machine's address and rights, the claim, the reservation and the connections. With `BAYCTL_KEY` set, it also prints the rules and the refusals |
| `access push [BAY ...]` | Writes the `access:` rules of the lab file to every bay, or to the bays you name |
| `access claim B3 [BAY ...]` | Gives each node the key in `BAYCTL_KEY`. Press the node's BOOT button within 60 s, while its LED blinks white |
| `access kick B3 ID` | Closes a connection. That address cannot use the same service again for a minute |
| `access keygen` | Prints a new random key of 64 hex digits |

See [Control who can use the rack](../use/access.md).

```console
$ python tools/bayctl.py access push
$ python tools/bayctl.py access kick B3 usbip:51234
```

## Board targets

### export lab and import lab

`export lab` reads the board targets saved on the nodes. It writes them as lab file entries, to stdout or to
`-o FILE`. `import lab FILE` writes them back to the nodes: every entry that has a `platform:`, or only the
bays and ports you name.
See [Board targets](../use/board-targets.md).

```console
$ python tools/bayctl.py export lab -o rack-targets.yaml
$ python tools/bayctl.py import lab rack-targets.yaml B3
```

## Test frameworks

### prepare

Gets one board ready to flash. It reserves the board if you give `--lease`, sets the bay to USB/IP, powers
the port, attaches the USB device and waits for its console. `--timeout` applies to each wait. Twister's
pre-scripts call it ([Run twister on the rack](../use/twister.md)).

```{tool-help} tools/bayctl.py prepare
```

### pty

Connects stdin and stdout to the node's AUX UART (raw TCP, port 4000), for twister's `serial_pty`. It works
only on a node with no DATA board, such as a simulated node started without `--ports`. Every bay of a rack
has a DATA board, so `pty` does not work there: `pty B3` answers `bay B3 holds several boards: say which`,
and `pty B3.2` answers `a sub-slot has no AUX UART`. A board's console is a serial port on its own USB.

### hwmap

Writes a twister hardware map, `rack-map.yaml`, and one pre-script per board in `rack-scripts/` beside it
([Run twister on the rack](../use/twister.md)). `hwmap` does not check the value of `--lease`. If it is
wrong, every test fails, so check it yourself.

```{tool-help} tools/bayctl.py hwmap
```

### export labgrid and export pdudaemon

`export labgrid` prints a labgrid environment. `export pdudaemon` prints a PDUDaemon configuration with one
PDU for the whole rack, named `hw-testing-rack`, and the numbers of its ports on stderr. See
[Use labgrid or LAVA](../use/labgrid-and-lava.md).

```{tool-help} tools/bayctl.py export
```

### power-port

`power-port N on|off|cycle` switches the `N`th board in rack order, counted from 1, skipping the empty
ports. PDUDaemon calls it.

```console
$ python tools/bayctl.py hwmap -o rack-map.yaml --lease 30m
$ python tools/bayctl.py export labgrid -o rack-env.yaml
```

## Firmware

### update

Sends a signed firmware image, `zephyr.signed.bin`, to the bays you name. `--all` updates every node, one
after the other, but not the hub. `--hub` updates the power hub.

- It skips a bay reserved as a whole, unless you give `--force`.
- `--timeout` is the time each device has to restart and confirm its new firmware.
- A device that does not come back stops the run. The exit code is 1 if a device was skipped or failed.

See [Update the firmware](../use/update-firmware.md).

```{tool-help} tools/bayctl.py update
```

```console
$ python tools/bayctl.py update build-bay/bay-node/zephyr/zephyr.signed.bin B3
$ python tools/bayctl.py update build-hub/power-hub/zephyr/zephyr.signed.bin --hub
```

### coproc

`coproc load` stores an image for the DATA ×4's co-processor on the node. The image is the UF2 file of an
RP2350 `no_flash` build. `--name` sets the name the node shows, 12 characters at most. `coproc status`
prints the stored image. See [Logic analyzer](../use/logic-analyzer.md).

## DATA ×4

### wire

Sets the pin matrix of a DATA ×4, or prints it when you give no pins. `A=2:P1,3:P2` puts pin P1 of port 2
and pin P2 of port 3 on bus A. The pins you give replace the whole assignment. Buses are A to H, ports 1 to
4, pins P1 to P8. See [Wires between boards](../use/wires.md).

```{tool-help} tools/bayctl.py wire
```

### capture

Makes one capture with the logic analyzer of a DATA ×4. It saves `<name>.capture.json` and
`<name>.decoded.json`. Without `-o`, the name is made of the bay and the time. A channel is a bus (A to H),
`mark`, or `CH1` to `CH24`. The command prints `armed` while the analyzer waits for its trigger. It exits
with 3 if the trigger does not come. It needs Node.js 22 or later. See [Logic analyzer](../use/logic-analyzer.md).

```{tool-help} tools/bayctl.py capture
```

```console
$ python tools/bayctl.py wire B3 A=2:P1,3:P2 --name A=UART
$ python tools/bayctl.py capture B3 --ch A --rate 10M --duration 20ms --trigger A:fall --decode uart:rx=A,baud=115200 -o run1
```

## Rows and the hub

### row

Switches a row of the power hub on or off, or power-cycles it. See
[The rack's page](../use/rack-page.md).

### hub

| Command | What it does |
|---|---|
| `hub`, `hub status` | Prints the charger's contract, the power budget, and one line per row with its bays |
| `hub events` | Prints the recent events |
| `hub enumerate` | Renumbers the bays on the rack bus |
| `hub pd 20v` | Asks the charger for 20 V. `hub pd epr` changes nothing: the hub stays at 20 V |
| `hub claim` | Gives the hub the key in `BAYCTL_KEY`. Press the hub's BOOT button to confirm |
| `hub node TARGET ACTION` | Sends a command to a bay over the rack bus. `TARGET` is a bay (`C3`) or a node id (`0x23`) |

```{tool-help} tools/bayctl.py hub node
```

```console
$ python tools/bayctl.py row B cycle --ms 2000
$ python tools/bayctl.py hub node C3 identify
```

## Global options

Put `--lab FILE` before the command. Two options do not appear in the help: `--rack` and `--boards`. They
point to another copy of `config/rack.yaml` and of `mechanical/boards/boards.yaml`.

## Environment variables

| Variable | Holds |
|---|---|
| `BAYCTL_HUB` | the power hub, `host` or `host:port`, or `none`. It wins over `hub:` in the lab file |
| `BAYCTL_KEY` | the rack's admin key, 64 hex digits. `bayctl` never reads it from a file |
| `BAYCTL_USBIP` | a command to run in place of `usbip`. `sudo -n` goes in front unless `bayctl` runs as root or the command starts with `sudo` |
| `BAYCTL_LAB` | the lab file when `--lab` is not given. The default is `config/lab.yaml` |

## Exit codes

| Code | When |
|---|---|
| 0 | done, including a power-on that `--when available` queued |
| 1 | an error, printed on stderr as `bayctl: <message>`, or one of several bays or nodes failed |
| 2 | a command line the tool cannot read |
| 3 | `capture`: the trigger did not come within `--timeout` |

A `warning: …` line on stderr does not change the exit code. `bayctl` prints text, never JSON. A script that
needs a value should call the [bay node's HTTP API](node-api.md).

## Where the data comes from

At each run, `bayctl` reads, in order:

1. The power hub's list of nodes, with their places and addresses.
   [Set up your machine](../use/set-up-your-machine.md) explains how `bayctl` finds the hub.
2. Each node's [board targets](../use/board-targets.md) and USB devices. If a node does not answer, the lab
   file's entries stand in for it.
3. `config/lab.yaml`, which overrides what the nodes say and holds the access rules
   ([lab.yaml](lab-yaml.md)).
4. `mechanical/boards/boards.yaml`, for the defaults of each board family: the runner and twister's
   `product` ([Board library](board-library.md)).

`bayctl` works out each board's console path from the device's USB strings, the same way udev names the
links in `/dev/serial/by-id`. That is how `hwmap` can write a board's `serial` without attaching it.
