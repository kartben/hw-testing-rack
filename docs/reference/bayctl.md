# bayctl

`bayctl` is one script, [tools/bayctl.py](../../tools/bayctl.py), run from a checkout of the repository. It
speaks HTTP to the hub and to the bay nodes, calls `usbip` for `attach`, `detach` and `prepare`, and writes
the configuration of twister, labgrid and PDUDaemon.

:::{status} simulated
81 tests check it, most of them against the simulated node, as a node with one board and as a DATA ×4 bay; none runs it
against a DATA ×6. `update`, `access claim`, `capture` and `coproc load` have each run against a XIAO
ESP32-S3 stand-in; no command has run against a v1.0 rack. The help texts below are printed by the tool
itself when the site is built. See [What exists today](../plan/status.md#status-bayctl).
:::

What it needs installed, the sudo rule, how it finds the hub and where the admin key goes:
[Set up bayctl and usbip](../use/set-up-your-machine.md).

## Synopsis

```text
python tools/bayctl.py [--lab FILE] COMMAND ...

Look at the rack
  list [--probe]
  status BAY
  ports BAY

Power and lines
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

`BAY` is a bay, `B3`, or one of its ports, `B3.2`. `PORT` must be one port. The numbers are the defaults.

## Naming a bay or a port

- `B3` is the bay in row B, place 3. `B3.2` is port 2 of its DATA board: 1 to 4 on a DATA ×4, 1 to 6 on a
  DATA ×6. How a bay gets its name, and which busid a port has:
  [Bays, ports and addresses](../use/names.md).
- A command given a port acts on that board. Given a bay, `power` acts on every port, the analyzer's and
  the empty ones included, while `reset`, `boot`, `attach` and `detach` act on its boards and pass by the
  analyzer and the empty ports. `status`, `ports`, `mode`, `access`, `update`, `coproc`, `wire` and
  `capture` address the node, whichever is named. `prepare` and `pty` take one board and answer
  `bay B3 holds several boards: say which (B3.1, B3.2, …)` to a bay.
- `power`, `reset`, `boot` and `import lab` go through the node's per-port routes, which firmware 0.5
  registers for ports 1 to 4: on a DATA ×6 they do not reach ports 5 and 6
  ([Known issues, and what will not work](known-limitations.md)).

In the help texts, which use the tool's own words, a *sub-slot* is a port of a DATA board, a *slot* is
what holds one board and the *DUT* is the board ([Glossary](glossary.md)).

## Look at the rack

### list

One line per board, in rack order, for the whole rack: every node the hub lists and every bay the lab
file names. The columns are the name, the family in the board library, the Zephyr
target, the runner, the console and the node's address. The target reads `(no target)`, `(empty port)`
or `analyzer: gusmanb <version>` where there is none. The tags are `[not in CI]`, `[analyzer]` and
`[not the board its target was saved for]`. With `--probe` each line ends with `VBUS on|off <n> mA`, or
`unreachable`, and for an analyzer with what its port holds: `LogicAnalyzer`, `BOOTSEL`, `no USB device`,
or a USB id that is not the analyzer's firmware.

```{tool-help} tools/bayctl.py list
```

### status and ports

`ports` prints one line per port: its name, `VBUS on`, `off` or `FAULT`, its current, the USB device and
its busid, and `USB/IP <address>` when a machine has it attached. `status` prints the node's line first
(host name, address, data path, the bay's supply, the counts of USB devices and USB/IP sessions), then
the port lines, then every USB device with its maker, serial number and classes.

```{tool-help} tools/bayctl.py status
```

```{tool-help} tools/bayctl.py ports
```

```console
$ python tools/bayctl.py list --probe
$ python tools/bayctl.py ports B3
```

## Power and lines

### power

`--ms` is how long a `cycle` stays off, 1000 ms by default. Once the action is done the command prints the
port as the node reports it.

A power-on that the bay's power budget has no room for is refused: 409, exit code 1. `--when available`
queues it instead: `queued, on as soon as the bay's budget has room`, exit code 0, and the port goes on by
itself. `--wait SECONDS` queues it the same way and blocks until the port is on; after `SECONDS` it
cancels the request, so that the port does not come on later behind the script's back, and exits with 1.
`cancel`, or `off`, withdraws a queued request. The three work on the ports of a DATA board; a node with
one board refuses them ([Power budget and queued ports](../use/power-budget.md)).

```{tool-help} tools/bayctl.py power
```

### reset and boot

`reset` pulses the board's RESET line for 100 ms, or `--ms`. `boot` holds BOOT across a
RESET pulse: the ROM bootloader on most MCUs. Only a DATA ×4 has the two lines; a port of a DATA ×6
answers `this port has no such line` ([Power-cycle or reset a board](../use/power-and-reset.md)).

```{tool-help} tools/bayctl.py reset
```

```{tool-help} tools/bayctl.py boot
```

### mode

`usbip` or `classic`: the bay's data path, for the whole bay whichever port is named. The node saves it
([Front port and classic mode](../use/front-port.md)).

```{tool-help} tools/bayctl.py mode
```

```console
$ python tools/bayctl.py power B3.2 cycle --ms 2000
$ python tools/bayctl.py power B3.4 on --wait 600
$ python tools/bayctl.py boot B3.3 --power-cycle
```

## USB/IP

### attach and detach

Linux only: both call `usbip` through `sudo -n`. `attach` does nothing for a device that is already
attached. Otherwise it attaches the port's device by its busid, waits up to 10 s for a new name under
`/dev/serial/by-id`, then 1 s more, because a composite probe brings its interfaces up one by one.
`--show` prints the new names, or `no new /dev/serial/by-id entry (already attached, or no tty)`.
`--follow` stays and tries again every 2 s, so a board that a reset or a power cycle took off the bus is
attached again when it comes back; Ctrl-C ends it. `detach` prints `detached <n> device(s)`
([USB/IP and flashing](../use/usb-and-flashing.md)).

```{tool-help} tools/bayctl.py attach
```

```{tool-help} tools/bayctl.py detach
```

```console
$ python tools/bayctl.py attach B3.2 --show
$ python tools/bayctl.py attach B3 --follow
```

## Reservations

### lease and release

The pages say *reserve*; the tool and the API say `lease`. `lease B3` reserves the whole bay for this
machine's address, `lease B3.2` one port. `--for` takes seconds, or `90s`, `15m`, `2h`, and defaults to one
hour; the node accepts 10 s to 24 h. Running it again renews the reservation. It prints
`B3.2 reserved for <address>, <n> s`. Another machine that tries gets 423
([Reserve a bay](../use/reserve-a-bay.md)).

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
| `access show B3` | prints this machine's address and rights, whether the node is claimed, the reservation and the connections; with `BAYCTL_KEY` set, the rules and the log of refusals as well |
| `access push` | writes the `access:` rules of the lab file to every bay, or to those named. One line per node: `updated`, `unchanged`, or `not claimed: bayctl access claim <bay>`. Exit code 1 if a node failed or is not claimed |
| `access claim B3` | gives each node named, in turn, the key of `BAYCTL_KEY`. Someone presses the node's BOOT button while its LED blinks white; `bayctl` waits 70 s for the press |
| `access kick B3 usbip:51234` | closes that connection and refuses its address that service for a minute |
| `access keygen` | prints a new random key, 64 hex digits |

The rules, the claim and what they do not protect: [Access rules and security](../use/access.md).

```{tool-help} tools/bayctl.py access
```

```{tool-help} tools/bayctl.py access push
```

```{tool-help} tools/bayctl.py access kick
```

`access show` takes one bay, `access claim` one or more, `access keygen` nothing; none has an option.

```console
$ python tools/bayctl.py access push
$ python tools/bayctl.py access show B3
```

## Board targets

### export lab and import lab

`export lab` writes the board targets the nodes hold as entries of a lab file, each with the device it is
pinned to: on stdout, or in `-o FILE`. `import lab FILE` writes such entries back to the nodes: every
entry that has a `platform:`, or only the ports and bays named
([Board targets](../use/board-targets.md#back-up-and-restore-with-bayctl)).

```{tool-help} tools/bayctl.py export
```

```{tool-help} tools/bayctl.py import
```

```console
$ python tools/bayctl.py export lab -o rack-targets.yaml
$ python tools/bayctl.py import lab rack-targets.yaml B3
```

## Test frameworks

### prepare

What a test runner needs before it flashes one board: the reservation if `--lease` asks for one, the bay
in USB/IP mode, the port powered (cycled for 1000 ms with `--power-cycle`), the USB device enumerated and
attached, the console's path present. `--timeout` is each of the two waits, 30 s by default. Twister's
pre-scripts call it ([Zephyr twister](../use/twister.md#what-the-pre-script-does-and-when-it-fails)).

```{tool-help} tools/bayctl.py prepare
```

### pty

Copies stdin to the node's raw AUX port, TCP 4000, and the port to stdout: twister's `serial_pty` runs
it. It is for a node with one board. Given a port it stops with `a sub-slot has no AUX UART: its console
is the board's own USB`, and every node of a v1.0 rack has ports.

```{tool-help} tools/bayctl.py pty
```

### hwmap

Writes a twister hardware map and one pre-script per board. By default `-o` is `rack-map.yaml` in the
current directory, `--scripts` a folder `rack-scripts` beside the map, `--python` the interpreter that runs
`hwmap`, by its full path ([Zephyr twister](../use/twister.md)).

```{tool-help} tools/bayctl.py hwmap
```

### export labgrid and export pdudaemon

`export labgrid` prints a labgrid environment, `export pdudaemon` a PDUDaemon configuration, and the
numbering of its ports on stderr. Here `--python` defaults to the plain word `python3`, where `hwmap`
takes the running interpreter ([labgrid and LAVA](../use/labgrid-and-lava.md)). The help is that of `export`,
above.

### power-port

`power-port N on|off|cycle` switches the board that PDUDaemon calls port `N`: the `N`th board in rack
order, counted from 1, the empty ports of a DATA board left out. The order is read from the rack at each
call. The command is hidden from the tool's list of commands, where it shows as `==SUPPRESS==`.

```{tool-help} tools/bayctl.py power-port
```

```console
$ python tools/bayctl.py hwmap -o rack-map.yaml --lease 30m
$ python tools/bayctl.py export labgrid -o rack-env.yaml
```

## Firmware

### update

Sends a signed image, `zephyr.signed.bin` from a `west build --sysbuild`, to the bays named, to every
node the hub lists (`--all`, one after the other, the hub not included) or to the hub (`--hub`). An image
built for the other kind of device is refused before anything is sent. A bay reserved as a whole is skipped
unless `--force`; a reservation of one port does not stop the update. `--timeout` is what each device gets
to restart and confirm its new firmware, 420 s by default. A firmware that does not stay on one device, or a device that does not come back, stops the run
there; any other refusal is reported and the run goes on. Exit code 1 if a device was skipped or failed
([Update the firmware](../use/update-firmware.md)).

```{tool-help} tools/bayctl.py update
```

### coproc

`coproc load` stores the image of a DATA ×4's co-processor on the node, from a UF2 of an RP2350 `no_flash`
build, one that loads into SRAM. `--name` is what the node shows, 12 printable ASCII characters at most;
without it, the file's name less its extension, cut to 12. `coproc status` prints the stored image. There
is no `coproc reload`, though one note names it ([Logic analyzer](../use/logic-analyzer.md)).

```{tool-help} tools/bayctl.py coproc
```

```{tool-help} tools/bayctl.py coproc load
```

```console
$ python tools/bayctl.py update build-bay/bay-node/zephyr/zephyr.signed.bin B3
$ python tools/bayctl.py update build-hub/power-hub/zephyr/zephyr.signed.bin --hub
```

## DATA ×4

### wire

The pin matrix of a DATA ×4. With no argument it prints the buses and their pins. `A=2:P1,3:P2` puts pin
P1 of port 2 and pin P2 of port 3 on bus A; the buses are A to H, the ports 1 to 4, the pins P1 to P8.
The pins named are the whole assignment from then on: every other pin goes off the buses. `--name
A=UART` names a bus and may be repeated. `--open-all` takes every pin off, and cannot be given with pins
([Wires between boards](../use/wires.md)).

```{tool-help} tools/bayctl.py wire
```

### capture

One capture of the DATA ×4's logic analyzer, saved as `<name>.capture.json` and `<name>.decoded.json`;
without `-o` the name is the bay and the time, `b3-20261124-153000`. A channel is a bus A to H, `mark`
or `CH1` to `CH24`; MARK is CH13. `--reset B3.2` triggers as that board leaves reset and cannot be given
with `--trigger`. `--decode` may be repeated. The command prints `armed` once the analyzer waits, and
exits with 3 if the trigger has not come after `--timeout`, 10 s by default. It needs Node 22 or later
([Logic analyzer](../use/logic-analyzer.md)).

```{tool-help} tools/bayctl.py capture
```

```console
$ python tools/bayctl.py wire B3 A=2:P1,3:P2 --name A=UART
$ python tools/bayctl.py capture B3 --ch A --rate 10M --duration 20ms --trigger A:fall --decode uart:rx=A,baud=115200 -o run1
```

## Rows and the hub

### row

Switches or power-cycles a whole row on the power hub. `--ms` is how long a `cycle` stays off, 1000 ms by
default, where the hub's own shell cycles for 2000 ms. It prints the row's line
([Rows and the rack's page](../use/rack-page.md)).

```{tool-help} tools/bayctl.py row
```

### hub

`hub`, or `hub status`, prints the hub's name and address, the charger's contract, the budget and one
line per row with its bays. `hub events` prints the recent events. The others are signed: `hub enumerate`
numbers the rack bus again, `hub pd epr` or `hub pd 20v` sets what the hub asks of the charger,
`hub claim` gives the hub the key of `BAYCTL_KEY` after a press on its BOOT button, and `hub node`
sends a command to a node over the rack bus. Its target is a place, `A1` to `D15`, or a node id, `0x01`
to `0x3f`.

```{tool-help} tools/bayctl.py hub
```

```{tool-help} tools/bayctl.py hub node
```

```console
$ python tools/bayctl.py row B cycle --ms 2000
$ python tools/bayctl.py hub node C3 identify
```

## Global options

`--lab FILE` goes before the command. Two more options are hidden, `--rack` and `--boards`, which name
other copies of `config/rack.yaml` and of `mechanical/boards/boards.yaml`. There is no `--version`.

```console
$ python tools/bayctl.py --lab config/lab.example.yaml list
```

The tool's own list of commands describes 7 of them and leaves the 16 others to the usage line:

```{tool-help} tools/bayctl.py
```

## Environment variables

| Variable | Holds |
|---|---|
| `BAYCTL_HUB` | the power hub, `host` or `host:port`; `none` or `off`: no hub. It wins over `hub:` of the lab file |
| `BAYCTL_KEY` | the rack's admin key, 64 hex digits. Read from here only, never from a file |
| `BAYCTL_USBIP` | a command to run in place of `usbip`; `sudo -n` goes in front unless `bayctl` runs as root or the command starts with `sudo` |
| `BAYCTL_LAB` | the lab file, when `--lab` is not given; `config/lab.yaml` otherwise |

## Exit codes

| Code | When |
|---|---|
| 0 | done. Also for a power-on that `--when available` queued |
| 1 | an error, printed on stderr as `bayctl: <message>`; `update` when a device was skipped or its firmware did not stay; `access push` when a node failed or is not claimed; `import lab` when an entry failed; `power --wait` at the end of its time |
| 2 | a command line the tool cannot read: the usage and the error on stderr |
| 3 | `capture`: the trigger did not come within `--timeout` |

A warning is a line `warning: …` on stderr and does not change the exit code. `bayctl` prints text, never
JSON: a script that needs a value calls the [bay node's HTTP API](node-api.md).

## Where the data comes from

`bayctl` reads these at each run:

1. The power hub lists the nodes on its rack bus by place and address (`GET /api/status`). Where
   `bayctl` looks for the hub: [How it finds the rack](../use/set-up-your-machine.md#how-it-finds-the-rack).
   The lookup gives up after 3 s for the name and 3 s for the answer. A node counts when it has an IP
   address and the hub does not show it lost, failed or incompatible.
2. Each node gives its ports (`GET /api/boards`, 5 s at most). A port carries its
   [board target](../use/board-targets.md), the USB device there now with its descriptor strings and its
   serial ports, and the device the target was saved for. A node that does not answer is a warning, and
   the lab file's entries stand for it.
3. `config/lab.yaml` overrides what the nodes say, key by key, and holds the access rules
   ([lab.yaml](lab-yaml.md)).
4. `mechanical/boards/boards.yaml`, under `zephyr:`, gives the defaults of a board's family: the
   runner, twister's `product`, a note. The family is found from the Zephyr board, or named by `board:` in
   the lab file ([Board library](board-library.md)).
5. `config/rack.yaml` is read for its `analyzer:` section only, by `list`, when a port holds an
   analyzer.

Most other requests to a node or to the hub give up after 15 s; the upload of a firmware image after
120 s, of a co-processor image after 60 s.

The console's path on the host is derived from the device's USB strings the way udev names
`/dev/serial/by-id` (systemd's `60-serial.rules` and its `usb_id` builtin):
`usb-<vendor>_<product>_<serial>-if<NN>`, plus `-port<P>` for a USB serial bridge (FTDI, CP210x, CH34x,
PL2303). A missing manufacturer or product string gives the VID or the PID instead, and characters udev
does not keep become `_`. That is how `hwmap` writes a board's `serial` without attaching it. When the node
has not yet read the strings of a device that has only now enumerated, `bayctl` looks once more a second
later, then warns: run the command again.
