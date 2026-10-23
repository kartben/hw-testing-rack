# Using the rack from CI

Every bay node exposes its DUT over the lab network (see
[`firmware/README.md`](../firmware/README.md)):

| What | How |
|---|---|
| DUT power, RESET, BOOT, data path | HTTP/JSON API, port 80: `/api/power`, `/api/reset`, `/api/boot`, `/api/mode`, `/api/status` |
| The DUT's USB device (debug probe + its virtual COM port) | USB/IP, TCP 3240: `usbip attach -r bay-<id>.local -b 1-1` |
| The DUT's UART on the AUX connector | RFC 2217 on TCP 4001 (baud set by the client), raw TCP on 4000, and the web page's console |
| Telemetry | Prometheus, `/metrics` |
| Who may use the bay | access rules per node, a reservation (lease) per CI job: [Access control](#access-control) |

[`tools/bayctl.py`](../tools/bayctl.py) wraps all of it for a CI host, and
writes the configuration of three test frameworks: a **Zephyr twister**
hardware map, a **labgrid** environment and a **PDUDaemon** (LAVA)
configuration.  It needs Python 3.10+ and PyYAML; `attach`/`detach` need the
Linux `usbip` tool.

> **Status:** tested against the firmware's simulated node
> (`firmware/bay-node/web/dev_server.py`, `python -m unittest discover -s tools/tests`),
> not yet against a real rack.

## Where the data comes from

The rack itself says what it holds; bayctl reads it at each run:

1. **The power hub** lists the nodes on its rack bus by position and address
   (`GET /api/status`).  bayctl finds the hub at `BAYCTL_HUB` (`host` or
   `host:port`), else `hub:` in `config/lab.yaml`, else `rack.<domain>`
   (`rack.local`).  `BAYCTL_HUB=none` skips it.  The lookup gives up within a
   few seconds: with no hub, bayctl warns and goes on with the lab file alone.
2. **Each node** gives its slots (`GET /api/boards`): a one-board bay has one,
   named like the bay (`A1`), a DATA ×4 bay one per port (`B3.1` to `B3.4`, the
   node's port *n*).  A slot carries its **board target**, set on the node's
   page (or by `bayctl import lab`, below) and kept in the node's flash: the
   Zephyr target (the `identifier` twister uses), the west runner, the probe
   id, the console (`usb`, `usb:NN`, `aux` or `none`) and whether it goes in
   the map.  It also carries the USB device in the slot now, its descriptor
   strings and its serial ports, and the device the target was saved for: a
   different board in the slot is flagged, and `hwmap` warns about it.
3. **`config/lab.yaml`** (per installation, git-ignored, optional; start from
   [`config/lab.example.yaml`](../config/lab.example.yaml)): overrides.  Per
   slot, `bays.<slot>.platform`, `runner`, `id`, `serial`, `console`, `ci`,
   `fixtures`, `product`, `baud` win over what the node says, and `role:
   analyzer` marks a DATA ×4 port that holds the bay's logic analyzer (kept out
   of the map).  Per node, `host:` (else the hub's address for that position,
   else `bay-<id>.<domain>`) and the ports.  Entries for slots the rack does not
   report (a node offline, or no hub) stand alone, as the example file does.
4. **`mechanical/boards/boards.yaml`, `zephyr:`**: defaults per board family
   (runner, twister `product`, notes), the family found from the target, or
   named by a lab entry's `board:`.

The console's path on the CI host is derived from the device's strings the
way udev names `/dev/serial/by-id` (systemd's `60-serial.rules` and its
`usb_id` builtin): `usb-<vendor>_<product>_<serial>-if<NN>`, plus `-port<P>`
for a USB-serial bridge (FTDI, CP210x, CH34x, PL2303); a missing manufacturer
or product string gives the VID or the PID instead, and characters udev does not
keep become `_`.  `console: usb` is the device's first serial port, `usb:02`
the one on interface 2.  The probe id is the slot's own, else the device's USB
serial number (for the `esp32` runner: the console's path).

```console
$ export BAYCTL_HUB=rack.local
$ python tools/bayctl.py list --probe
A1    nucleo-64           nucleo_g474re                      stm32cubeprogrammer  usb     192.168.1.61  VBUS on 92 mA
A2    nucleo-144          (no target)                        stm32cubeprogrammer  usb     192.168.1.62  VBUS on 88 mA
B2    giga-r1-display     arduino_giga_r1/stm32h747xx/m7     dfu-util             aux     192.168.1.78  VBUS on 210 mA
B3.1  xiao                xiao_esp32c3                       esp32                usb     192.168.1.79  VBUS on 41 mA
B3.3  -                   analyzer: gusmanb 6.0.0.1          -                    usb     192.168.1.79  [analyzer]  VBUS on 23 mA
...
```

## CI host setup (Linux)

* `usbip` and the client kernel module: `sudo apt install linux-tools-generic`
  (or your distro's `usbip`), `sudo modprobe vhci-hcd`, and add `vhci-hcd` to
  `/etc/modules`.
* `usbip attach` needs root: bayctl runs it through `sudo -n`, so give the CI
  user a NOPASSWD sudoers rule for the `usbip` binary only (or set
  `BAYCTL_USBIP` to another wrapper).
* The hub: `BAYCTL_HUB=<its address>` in the CI job's environment (or `hub:`
  in `config/lab.yaml`), unless `rack.local` resolves there.  The nodes are
  then reached by the addresses the hub gives; `bay-<id>.local` names (mDNS:
  `avahi-daemon` + `libnss-mdns`) or `host:` per bay only without a hub.
* The flashing tools of the boards you host (nrfutil, LinkServer, pyOCD,
  STM32CubeProgrammer, ...) and their udev rules, exactly as for boards plugged
  into the host directly: after `usbip attach` the probe is a local USB device.

Then give each slot its board target, once, on its node's page (the USB
devices card: Set board… or Edit under the device, for the target, the
runner, the probe id and the console; the dialog suggests targets from the
device's USB id, [firmware/README.md › Board targets](../firmware/README.md#board-targets)).  The node keeps it across
restarts and firmware updates.  Bays whose board prints its console on a UART
rather than on the probe's virtual COM port (Pico 2, UNO R4 Minima, ...) get
console `aux` and three wires (TX, RX, GND) to the bay's AUX connector.  A
probe with several serial ports takes `usb:NN`, its interface number: the
by-id names after an attach show it.

```console
$ python tools/bayctl.py attach A3 --show
/dev/serial/by-id/usb-SEGGER_J-Link_001050012345-if00
```

## Backups: export and import

```console
$ python tools/bayctl.py export lab -o rack-targets.yaml
wrote rack-targets.yaml (9 slots)
$ python tools/bayctl.py import lab rack-targets.yaml          # every slot in the file
$ python tools/bayctl.py import lab rack-targets.yaml B3.2 A1  # or only these (B3: all of B3's)
```

`export lab` writes every slot's target as the nodes hold it, in the form of
`config/lab.yaml` (`platform`, `runner`, `id`, `console`, `ci: false` for a
slot out of the map) plus the device it is pinned to (`pin: {vid, pid,
serial}`).  `import lab` writes them back (`PUT /api/ports/<n>/board`, the
control right; refused while another host holds the port's lease), with that
pin: a restored slot still flags another board in it.  An entry without a pin
is pinned to the device in the slot now.  Any lab file with `platform:`
entries can be imported, a hand-written `config/lab.yaml` included.

## Zephyr twister

```console
$ python tools/bayctl.py hwmap -o rack-map.yaml
wrote rack-map.yaml (8 boards) and pre-scripts in rack-scripts
$ west twister --device-testing --hardware-map rack-map.yaml \
      -p nucleo_g474re -p wio_terminal -T samples/hello_world
```

Each entry of the map is one board (a bay's, or a DATA ×4 port's):

```yaml
- connected: true
  platform: nucleo_g474re
  product: ST NUCLEO-64 (MB1136 / MB1367) (bay A1)
  runner: stm32cubeprogrammer
  id: 003A00283133510837363734
  serial: /dev/serial/by-id/usb-STMicroelectronics_STLINK-V3_003A00283133510837363734-if02
  baud: 115200
  pre_script: /ci/rack-scripts/bay-a1-pre.sh
  script_param:
    pre_script_timeout: 90
  fixtures:
  - bay:A1
```

* **`pre_script`** runs `bayctl prepare <bay>` before every test: data path to
  USB/IP, DUT powered (a latched over-current is cleared), wait until the node
  has enumerated the DUT, `usbip attach` if needed, wait for the console tty.
  `hwmap --power-cycle` makes it power-cycle the DUT first, for a clean state
  every time.
* **AUX consoles** use twister's `serial_pty`: `bayctl pty <bay>` bridges the
  pty twister gives it to the node's raw AUX port.  Twister splits that command
  on spaces and commas, so keep the Python and repository paths free of both.
* **Probe ids.**  Every bay gets attached to the CI host, so two nRF DKs show
  up as two J-Links at once: the runner must pick its board.  The id is the
  slot's probe id, else the USB serial number of the device in the slot; for
  the `esp32` runner the serial port *is* the id, and bayctl fills it in.
  `hwmap` warns about runners shared by boards without an id.
* **`fixtures: [bay:<id>]`** lets a test plan pin a test to one bay
  (`--fixture bay:A3`; a DATA ×4 port's also has `node:<bay>`); add your own
  per slot (`fixtures:` in `config/lab.yaml`).
* Slots without a target (warned, with the node's page to set it on), slots
  out of the map (the page's switch, or `ci: false`: e.g. the bay kept for a
  laptop in classic mode), analyzers and empty DATA ×4 ports stay out of the
  map.  A board without a console path (powered off when the map was made, no
  serial port on that interface, console `none`) is written with
  `connected: false` and a warning; `serial:` in `config/lab.yaml` gives one by
  hand.  A board that is not the one its target was saved for is written as it
  is, with a warning.
* **Offline**: with no hub and no node reachable, the map comes from the lab
  file's entries alone (the repository's CI job does this with
  `config/lab.example.yaml`).

## labgrid

```console
$ python tools/bayctl.py export labgrid > rack-env.yaml
```

gives one target per bay with the AUX UART as an RFC 2217 `NetworkSerialPort`
(port 4001: labgrid sets the baud rate) and the node's power switch as an
`ExternalPowerDriver` (`bayctl power <bay> on|off|cycle`).
USB stays with USB/IP: `bayctl attach <bay>` on the machine that runs the
flashing tool.

## LAVA (PDUDaemon)

```console
$ python tools/bayctl.py export pdudaemon > pdudaemon.conf
# PDUDaemon ports: 1=A1, 2=A2, 3=A3, ...
```

declares the rack as one PDU (`hw-testing-rack`) with PDUDaemon's
`localcmdline` driver, one port per board in rack order, as the rack reports
them (empty DATA ×4 ports left out; `bayctl power-port <n>`): regenerate it
when boards move.
A LAVA device then uses the usual
`pduclient --daemon <host> --hostname hw-testing-rack --port <n> --command on|off|reboot`.

## Access control

Each node only serves the addresses its rules allow
([`firmware/README.md`](../firmware/README.md#access-control)); an unclaimed
node is open.  For a rack used by CI:

1. **A rack key.**  `python tools/bayctl.py access keygen` prints a random
   key; keep it where your CI keeps secrets and export it as `BAYCTL_KEY`
   wherever you run admin commands.  It never goes in `config/lab.yaml`.
2. **Claim the nodes** with it, once: `bayctl access claim A1 A2 ...` asks
   each node in turn and waits while someone presses its BOOT button (the
   node's LED blinks white).
3. **Write the rules** in the `access:` section of `config/lab.yaml` (see
   [`config/lab.example.yaml`](../config/lab.example.yaml)) and push them:

```console
$ python tools/bayctl.py access push
A1   updated
A2   unchanged
B2   not claimed: bayctl access claim B2
...
$ python tools/bayctl.py access show B3      # with BAYCTL_KEY: the rules and the refusal log too
```

The CI hosts need status, control, console and USB/IP; telnet (shell) is
for admin hosts.  A bay's own `access:` adds sources for that bay only.

**Reservations.**  A job that holds a bay keeps the others off it: power,
reset, the console and USB/IP answer only the holder until it releases the
bay or the reservation lapses.

```console
$ python tools/bayctl.py lease B3 --for 30m --note "twister job $CI_JOB_ID"
$ python tools/bayctl.py release B3
$ python tools/bayctl.py release B3 --force   # someone else's, with BAYCTL_KEY
```

`bayctl hwmap --lease 30m` makes each test reserve its bay in the
pre-script (`prepare --lease`, renewed by every test) and release it in a
twister `post_script`.  For labgrid, take the reservation in the job
before acquiring the places.

`bayctl access kick B3 usbip:51234` closes a connection (ids from
`access show`) and refuses its address that service for a minute.

## By hand

```console
$ python tools/bayctl.py power B3 cycle --ms 2000
$ python tools/bayctl.py reset B3
$ python tools/bayctl.py boot B3          # ROM bootloader: BOOT held across a RESET pulse
$ python tools/bayctl.py mode B4 classic  # hand the DUT to the laptop on the front port
$ python tools/bayctl.py status B3
```

## Limits

* **Access control is address based, without TLS.**  The rules keep
  uninvited hosts and other jobs off a bay; they do not stop someone who
  spoofs an allowed address on the same network, and a node's key crosses
  the network in clear once, when it is claimed.  Keep the rack on a lab
  network or behind a VPN.  A refused `usbip attach` times out (the node
  drops the connection) rather than failing at once.
* **USB/IP through the ESP32-S3** is full speed, and Zephyr's DWC2 host driver
  does control, bulk and interrupt IN only: probes that need interrupt OUT
  (CMSIS-DAP v1, i.e. HID) or isochronous endpoints won't work yet; J-Link,
  ST-LINK, MCU-Link / CMSIS-DAP v2 (bulk) and CP210x / CH34x UART bridges do.
  Boards with an on-board USB hub don't work over USB/IP either.
* The raw (4000) and RFC 2217 (4001) AUX ports take **one client** each: while
  twister's `serial_pty` holds the raw port, `nc` can't connect to it (the web
  console still shows the traffic).  `bayctl pty` uses the node's saved AUX
  settings: set the baud rate once from the web console or `bay aux <baud>`.
