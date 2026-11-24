# Set up your machine

`bayctl` is the rack's command-line tool. It is a Python script that runs from a checkout of
[the repository](../../README.md), with nothing to install on your PATH. Most of its commands talk to the rack
over HTTP and work on any system. Using a board's USB on your machine needs Linux.

## Install Python and PyYAML

`bayctl` needs Python 3.10 or later and PyYAML. Its `capture` command also needs Node 22 or later. Install
PyYAML in a virtual environment, from your checkout:

```console
$ python3 -m venv .venv
$ . .venv/bin/activate
$ pip install pyyaml pyserial
$ python tools/bayctl.py --help
```

pyserial gives you `miniterm`, the terminal program this site uses for a board's console. If you already have a
Zephyr workspace, its virtual environment has both packages: activate it instead.

Activate the environment in every shell that runs `bayctl`. `hwmap` writes that Python's full path into the
scripts it makes, so twister does not need the environment active.

The script reads files from the checkout it sits in, so it does not work if you copy it elsewhere. When this
site writes `bayctl power B3.2 cycle`, type `python tools/bayctl.py power B3.2 cycle`.

`bayctl` prints text for people to read. A script that needs values should call the
[bay node's HTTP API](../reference/node-api.md) instead.

## Check that it works

```console
$ python tools/bayctl.py list --probe
```

`list` prints one line per board. Here is its output on the simulated bay of
[Try it without hardware](../plan/try-it-without-hardware.md), with `BAYCTL_HUB=none` and this lab file in
`BAYCTL_LAB`:

```{code-block} yaml
:caption: sim-lab.yaml
bays:
  B3: {host: 127.0.0.1, http_port: 8766}
  B3.1: {platform: xiao_esp32c3, runner: esp32}
  B3.2: {board: rpi-pico2}
  B3.3: {role: analyzer}
  B3.4: {platform: xiao_ble, ci: false}
```

```text
B3.1  xiao                xiao_esp32c3                       esp32                usb     127.0.0.1  VBUS on 83 mA
B3.2  rpi-pico2           rpi_pico2/rp2350a/m33_0            uf2                  usb     127.0.0.1  VBUS on 82 mA
B3.3  -                   analyzer: gusmanb 6.0.0.1          -                    usb     127.0.0.1  [analyzer]  VBUS on 90 mA  BOOTSEL
B3.4  xiao                xiao_ble                           uf2                  usb     127.0.0.1  [not in CI]  VBUS on 91 mA
```

Each line gives the port, the board's family, its Zephyr target, the west runner, the console and the node's
address ([Board targets](board-targets.md)). Tags such as `[not in CI]` follow. `--probe` adds each port's power
and current, or `unreachable` for a node that does not answer. Every command and option is on
[bayctl](../reference/bayctl.md).

If `bayctl` warns that it cannot find the hub, read [How it finds the rack](#how-it-finds-the-rack).

## Set up usbip on Linux

`attach`, `detach` and `prepare` call the Linux `usbip` tool, which makes a board's USB device appear on your
machine ([USB/IP and flashing](usb-and-flashing.md)). Install it and load its client module:

```console
$ sudo apt install linux-tools-generic
$ sudo modprobe vhci-hcd
```

If your distribution has no `linux-tools-generic`, install its `usbip` package. Add `vhci-hcd` to
`/etc/modules` so that the module loads at each start.

`usbip attach` needs root. When you are not root, `bayctl` runs `sudo -n usbip`, which never asks for a
password. So give your user, or the CI user, a sudo rule for `usbip` without a password. Find the path of
`usbip`, then open a new sudoers file:

```console
$ command -v usbip
$ sudo visudo -f /etc/sudoers.d/usbip
```

Add one line, with the user's name and the path that `command -v usbip` printed:

```{code-block} text
:caption: /etc/sudoers.d/usbip
ci ALL=(root) NOPASSWD: /usr/sbin/usbip
```

Check it with `sudo -n usbip port`: it must print the list of attached devices, empty or not, without asking for
a password. Without the rule, the first `bayctl attach` stops at `sudo -n usbip list` with sudo's own message.
To run a wrapper of your own in place of `usbip`, set `BAYCTL_USBIP`.

Once attached, a board's probe is a local USB device. Install your boards' flashing tools and their udev rules
as you would for a board on your desk: nrfutil, LinkServer, pyOCD, STM32CubeProgrammer and so on. For a CI
runner, see also [Set up a CI host](ci-host.md).

`attach`, `detach` and `prepare` work on Linux only, because they call `usbip` and look for the new device under
`/dev/serial/by-id`. On Windows, run them in WSL2 with the `vhci_hcd` module loaded. macOS has no USB/IP client
([USB/IP and flashing](usb-and-flashing.md#on-macos-or-windows)).

## How it finds the rack

At every run, `bayctl` asks the power hub which bay nodes the rack holds and at which addresses. It looks for
the hub in this order:

1. the `BAYCTL_HUB` environment variable, `host` or `host:port`;
2. `hub:` in the [lab file](../reference/lab-yaml.md);
3. `rack.local`, or `rack.<domain>` when the lab file sets `domain:`.

If the hub has an id, its name is `rack-<id>.local` and the default misses it. Name it:

```console
$ export BAYCTL_HUB=rack-lab1.local
```

The lookup waits 3 s for the name and 3 s for the answer. If no hub answers, `bayctl` warns and uses only the
bays in the lab file:

```text
warning: hub rack.local: no such host (BAYCTL_HUB=host[:port] names it, BAYCTL_HUB=none skips it): config/lab.yaml's bays only
```

`BAYCTL_HUB=none`, or `hub: false` in the lab file, skips the lookup.

One run of `bayctl` talks to one hub. With several racks on one network, give each hub an id and choose the rack
with `BAYCTL_HUB`. Each rack also needs its own lab file, which you name with `--lab FILE` or `BAYCTL_LAB`.

## Without mDNS, or from another subnet

The `.local` names need an mDNS resolver on your machine: on Linux, `avahi-daemon` and `libnss-mdns`. They also
do not cross a router. Give `bayctl` the hub's IP address and it needs neither, because the hub tells it the
nodes' addresses:

```{code-block} yaml
:caption: config/lab.yaml
hub: 192.168.1.60
```

`export BAYCTL_HUB=192.168.1.60` does the same for one shell. For a node that the hub does not list, such as a
single bay on a desk with no hub, give its address in the lab file:

```{code-block} yaml
:caption: config/lab.yaml
bays:
  B3:
    host: 192.168.1.79
```

With `domain: lab.example` in the lab file, `bayctl` looks for `rack.lab.example` and `bay-b3.lab.example` on
your network's DNS.

Through a firewall, `bayctl` needs TCP port 80 of the hub and of the nodes, and TCP 3240 of a node for `usbip`.
The AUX UART uses TCP 4000 and 4001. Every port is listed on
[Network ports and metrics](../reference/network.md).

## The lab file and the admin key

`config/lab.yaml` is optional, and git ignores it. When you need one, copy
[config/lab.example.yaml](../../config/lab.example.yaml). It holds what the rack cannot know: addresses,
overrides of a board target and the access rules. To use another file, put `--lab FILE` before the command or
set `BAYCTL_LAB`. Every key is on [lab.yaml](../reference/lab-yaml.md).

The admin key is 64 hex digits. `bayctl` reads it from the `BAYCTL_KEY` environment variable and from nowhere
else. Keep it with your CI's secrets, and export it only in the shell that runs admin commands. Never write it
into the lab file or any other file of the checkout.

The commands that change the rack need it: `access push`, `access claim`, `access kick`, `release --force`,
`update`, `coproc load`, `row`, and the `hub` commands `enumerate`, `pd`, `node` and `claim`. Without it they
stop with `set BAYCTL_KEY to the rack's admin key (a new one: bayctl access keygen)`. A test job does not need
the key. To make a key and give it to the rack, see [Control who can use the rack](access.md).
