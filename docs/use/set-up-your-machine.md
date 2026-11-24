# Set up your machine

`bayctl`, the rack's command-line tool, is one Python script that runs from a checkout of the repository:
there is no package to install and no `bayctl` command on the PATH. What it does over HTTP works on any
system; bringing a board's USB device onto your machine needs Linux, a kernel module and a sudo rule.

:::{status} simulated
81 tests check `bayctl`, most of them against the simulated node. `update`, `access claim`, `capture` and `coproc load` have
each run against a XIAO ESP32-S3 stand-in. Nothing has run against a v1.0 rack, and nobody has done the Linux
set-up below on a CI host. See [What exists today](../plan/status.md#status-bayctl).
:::

## Python, PyYAML and the checkout

```console
$ pip install pyyaml
$ python tools/bayctl.py --help
```

It needs Python 3.10 or later and PyYAML: without PyYAML even `--help` fails, on `import yaml`. `capture`
alone also needs Node 22 or later. [tools/requirements.txt](../../tools/requirements.txt) lists PyYAML among
what [build.py, plate_layout.py, bom.py](../reference/tools.md) need; `bayctl` uses nothing else of that
file.

The script finds `config/rack.yaml`, `mechanical/boards/boards.yaml`, `config/lab.yaml` and
`tools/rackcfg.py` beside itself. It runs from any directory, as long as it sits in a checkout of
[the repository](../../README.md): a copy of the one file does not work.

Where this site writes `bayctl power B3.2 cycle`, type `python tools/bayctl.py power B3.2 cycle`, on every
page.

`bayctl` prints text, never JSON: a script that needs a value calls the
[bay node's HTTP API](../reference/node-api.md). An error goes to stderr as `bayctl: <message>` with exit
code 1 ([exit codes](../reference/bayctl.md#exit-codes)). The tool has no `--version`, and nothing records
which revision of it works with which firmware: both live in the same repository.

## usbip, a sudo rule and flashing tools on Linux

`attach`, `detach` and `prepare` call the Linux `usbip` tool, which makes a board's USB device appear on
your machine ([USB/IP and flashing](usb-and-flashing.md)). A laptop needs it as much as a runner does:
[twister](twister.md)'s pre-script calls `prepare`. What a runner needs on top is on
[Set up a CI host](ci-host.md).

```console
$ sudo apt install linux-tools-generic
$ sudo modprobe vhci-hcd
```

Where `linux-tools-generic` does not exist, take your distribution's `usbip` package. Add `vhci-hcd` to
`/etc/modules` so that the client module loads at each start.

`usbip attach` needs root. Unless it runs as root, `bayctl` puts `sudo -n` in front of every `usbip` call,
and `sudo -n` never asks for a password. Give your user, or the CI user, a NOPASSWD sudoers rule for the
`usbip` binary only, one that lets these four calls through:

```text
sudo -n usbip list -r <node>
sudo -n usbip attach -r <node> -b <busid>
sudo -n usbip port
sudo -n usbip detach -p <port>
```

Without the rule the first `bayctl attach` stops at `sudo -n usbip list`, with sudo's own message after
`bayctl:`. `BAYCTL_USBIP` names a command to run in place of `usbip`, a wrapper of your own for instance;
when it starts with `sudo`, `bayctl` adds nothing in front.

Install the flashing tools of the boards you host (nrfutil, LinkServer, pyOCD, STM32CubeProgrammer, ...)
and their udev rules as for boards plugged into the machine directly: after `usbip attach` the probe is a
local USB device.

## How it finds the rack

`bayctl` asks the rack what it holds at every run, starting from one address, the power hub's, looked up in
this order:

1. the `BAYCTL_HUB` environment variable, `host` or `host:port`;
2. `hub:` in the [lab file](../reference/lab-yaml.md);
3. `rack.<domain>`, which is `rack.local` unless the lab file sets `domain:`.

The hub lists the bay nodes on its rack bus by place and IP address, `bayctl` reaches each node at that
address, and each node says which boards it holds.

The lookup waits 3 s for the name and 3 s for the answer. With no hub, `bayctl` warns and goes on with the
lab file's entries alone; for a name that does not resolve:

```text
warning: hub rack.local: no such host (BAYCTL_HUB=host[:port] names it, BAYCTL_HUB=none skips it): config/lab.yaml's bays only
```

`BAYCTL_HUB=none`, or `hub: false` in the lab file, skips the lookup. A hub that is not found, and sudo
asking for a password, are on [Troubleshooting](troubleshooting.md).

`rack.local` is the name of a hub that was given no id. After `hub id lab1` on its console the hub answers
as `rack-lab1.local`, and the default misses it ([Bays, ports and addresses](names.md)):

```console
$ export BAYCTL_HUB=rack-lab1.local
```

Several racks on one network have a hub each, and one run of `bayctl` talks to one hub: give each hub an id
and choose the rack with `BAYCTL_HUB`. A lab file holds one `hub:` and names its bays `B3`, as every rack
does, so a second rack takes a second file, named with `--lab` or `BAYCTL_LAB`. This is worked out from
[tools/bayctl.py](../../tools/bayctl.py); nobody has run two racks. Both racks have a `bay-b3.local`, and no
source says what mDNS makes of the second one: go through each hub and the addresses it lists.

## Without mDNS, or from another subnet

The `.local` names need an mDNS resolver on your machine (on Linux, `avahi-daemon` and `libnss-mdns`) and
do not cross a router. `bayctl` needs neither once it has the hub's IP address, because the nodes'
addresses come from the hub:

```{code-block} yaml
:caption: config/lab.yaml, for a hub at 192.168.1.60
hub: 192.168.1.60
```

`export BAYCTL_HUB=192.168.1.60` does the same for one shell. A node the hub does not list (a bay on a desk
with no hub, a node that has not joined the rack bus) takes its address per bay; without one `bayctl` tries
`bay-<id>.<domain>`:

```{code-block} yaml
:caption: config/lab.yaml
bays:
  B3:
    host: 192.168.1.79
```

`domain:` replaces `local` in the two default names: with `domain: lab.example`, `bayctl` looks for
`rack.lab.example` and `bay-b3.lab.example`, on a network whose DNS serves them.

Through a firewall, `bayctl` speaks HTTP to port 80 of the hub and of the nodes, `usbip` connects to TCP
3240 of a node, and `bayctl pty` to its TCP 4000. Every port a node and the hub listen on:
[Network ports, names and metrics](../reference/network.md).

## The lab file and the admin key

`config/lab.yaml` is optional and git-ignored: copy [config/lab.example.yaml](../../config/lab.example.yaml)
when you need one. It holds what the rack cannot know: addresses, overrides of a board target, the access
rules. Every key is on [lab.yaml](../reference/lab-yaml.md). `--lab FILE`, before the command, or
`BAYCTL_LAB` names another file.

The admin commands are signed with the rack's admin key, 64 hex digits, read from the `BAYCTL_KEY`
environment variable and from nowhere else. Keep it with your CI's secrets and export it in the shell that
runs admin commands; never write it into the lab file or any other file of the checkout.

`access push`, `access claim`, `access kick`, `release --force`, `update`, `coproc load`, `row`,
`hub enumerate`, `hub pd`, `hub node` and `hub claim` need it, and without it stop with
`set BAYCTL_KEY to the rack's admin key (a new one: bayctl access keygen)`. A test job runs without it.
`access show` prints the rules and the log of refusals as well when it is set.

Making a key and giving it to the hub and the nodes: [Access rules and security](access.md). A lost key:
[Recover a node or a hub](recover.md).

## A first look with list, status and ports

```console
$ python tools/bayctl.py list --probe
A1    nucleo-64           nucleo_g474re                      stm32cubeprogrammer  usb     192.168.1.61  VBUS on 92 mA
A2    nucleo-144          (no target)                        stm32cubeprogrammer  usb     192.168.1.62  VBUS on 88 mA
B2    giga-r1-display     arduino_giga_r1/stm32h747xx/m7     dfu-util             aux     192.168.1.78  VBUS on 210 mA
B3.1  xiao                xiao_esp32c3                       esp32                usb     192.168.1.79  VBUS on 41 mA
B3.3  -                   analyzer: gusmanb 6.0.0.1          -                    usb     192.168.1.79  [analyzer]  VBUS on 23 mA  LogicAnalyzer
...
```

No rack exists to print this listing: it is an illustration, with the made-up addresses and currents of
the 3D model, drawn before the DATA ×6. Its `A1`, `A2` and `B2` hold one board on the node itself, the form
of the bench stand-ins and of the simulator. A v1.0 node lists the ports of its DATA board instead, `A1.1`
for instance, with a line `(empty port)` for each port that holds nothing.

Each line is a board: its name, its family in the [board library](../reference/board-library.md), its
Zephyr target, the west runner, the console and the node's address, from its
[board target](board-targets.md) and the lab file. A tag follows where it applies: `[not in CI]`,
`[analyzer]`, `[not the board its target was saved for]`. `--probe` asks every node for the board's power
and current, prints `unreachable` for a node that does not answer, and says what an analyzer's port holds.

```console
$ python tools/bayctl.py ports B3
B3.1   port 1  VBUS on 133 mA  1fc9:0143 MCU-LINK on-board (r0E7) CMSIS-DAP V3.172  busid 1-1.1
B3.2   port 2  VBUS on 98 mA  0403:6001 FT232R USB UART  busid 1-1.2
B3.3   port 3  VBUS on 94 mA  2e8a:0003 RP2 Boot  busid 1-1.3
B3.4   port 4  VBUS off 0 mA  no USB device
```

This one is real output, from the simulated node: a DATA ×4 bay with made-up boards
([Try it without hardware](../plan/try-it-without-hardware.md)). Each line is a port: its power and
current, the USB device on it, the busid USB/IP exports it under, and `USB/IP <address>` when a machine has
it attached. `status B3` prints the node's own line first (its name, its address, the data path, the supply
of the bay, the count of USB devices and USB/IP sessions), then the same port lines, then each USB device
with its maker, its serial number and its classes. Every command and option: [bayctl](../reference/bayctl.md).

## On macOS and Windows

The commands that only speak HTTP work on any system with Python: `list`, `status`, `ports`, `power`,
`reset`, `boot`, `mode`, `lease`, `release`, `access`, `export`, `import`, `update`, `coproc`, `wire`,
`row`, `hub`, and `capture` with Node. `attach`, `detach` and `prepare` are Linux only: they call `usbip`
and look for the new device under `/dev/serial/by-id`. `pty` is POSIX.

On Windows the bench PC attached boards from WSL2, which is Linux with `vhci_hcd` loaded as a module. A
native Windows client is untested, and the sources name none for macOS. What those systems can do with a
board's USB today is on [USB/IP and flashing](usb-and-flashing.md#on-macos-or-windows).
