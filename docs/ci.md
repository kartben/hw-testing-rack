# Using the rack from CI

Every bay node exposes its DUT over the lab network (see
[`firmware/README.md`](../firmware/README.md)):

| What | How |
|---|---|
| DUT power, RESET, BOOT, data path | HTTP/JSON API, port 80: `/api/power`, `/api/reset`, `/api/boot`, `/api/mode`, `/api/status` |
| The DUT's USB device (debug probe + its virtual COM port) | USB/IP, TCP 3240: `usbip attach -r bay-<id>.local -b 1-1` |
| The DUT's UART on the AUX connector | raw TCP, port 4000 |
| Telemetry | Prometheus, `/metrics` |

[`tools/bayctl.py`](../tools/bayctl.py) wraps all of it for a CI host, and
writes the configuration of three test frameworks: a **Zephyr twister**
hardware map, a **labgrid** environment and a **PDUDaemon** (LAVA)
configuration.  It needs Python 3.10+ and PyYAML; `attach`/`detach` need the
Linux `usbip` tool.

> **Status:** tested against the firmware's simulated node
> (`firmware/bay-node/web/dev_server.py`, `python -m unittest discover -s tools/tests`),
> not yet against a real rack.

## Where the data comes from

1. **`config/rack.yaml`, `population`**: which board family sits in which bay.
2. **`mechanical/boards/boards.yaml`, `zephyr:`**: each family's Zephyr target
   (the `identifier` twister uses), west runner and console.  Families such as
   NUCLEO-64 list their possible targets under `choices`.
3. **`config/lab.yaml`** (per installation, git-ignored; start from
   [`config/lab.example.yaml`](../config/lab.example.yaml)): which exact board a
   family bay holds, probe serial numbers, the console device path on the CI
   host, hosts, and any override (runner, baud, fixtures, `ci: false`).

```console
$ cp config/lab.example.yaml config/lab.yaml
$ python tools/bayctl.py list --probe
A1   nucleo-64          nucleo_f401re                      stm32cubeprogrammer  usb  bay-a1.local  VBUS on 92 mA
A3   nrf52840-dk        nrf52840dk/nrf52840                nrfutil              usb  bay-a3.local  VBUS on 41 mA
B3   rpi-pico2          rpi_pico2/rp2350a/m33_0            uf2                  aux  bay-b3.local  VBUS on 23 mA
...
```

## CI host setup (Linux)

* `usbip` and the client kernel module: `sudo apt install linux-tools-generic`
  (or your distro's `usbip`), `sudo modprobe vhci-hcd`, and add `vhci-hcd` to
  `/etc/modules`.
* `usbip attach` needs root: bayctl runs it through `sudo -n`, so give the CI
  user a NOPASSWD sudoers rule for the `usbip` binary only (or set
  `BAYCTL_USBIP` to another wrapper).
* `bay-<id>.local` names: mDNS resolution (`avahi-daemon` + `libnss-mdns`), or
  `host:` per bay in `config/lab.yaml`.
* The flashing tools of the boards you host (nrfutil, LinkServer, pyOCD,
  STM32CubeProgrammer, ...) and their udev rules, exactly as for boards plugged
  into the host directly: after `usbip attach` the probe is a local USB device.

Then collect each bay's probe serial number and console path once:

```console
$ python tools/bayctl.py attach A3 --show
/dev/serial/by-id/usb-SEGGER_J-Link_001050012345-if00
```

and put them in `config/lab.yaml` (`id:` is the part before `-ifNN`).  Bays
whose board prints its console on a UART rather than on the probe's virtual
COM port (Pico 2, UNO R4 Minima, ...) get `console: aux` and three wires (TX,
RX, GND) to the bay's AUX connector.

## Zephyr twister

```console
$ python tools/bayctl.py hwmap -o rack-map.yaml
wrote rack-map.yaml (12 bays) and pre-scripts in rack-scripts
$ west twister --device-testing --hardware-map rack-map.yaml \
      -p nrf52840dk/nrf52840 -p frdm_mcxn947/mcxn947/cpu0 -T samples/hello_world
```

Each entry of the map is one bay:

```yaml
- connected: true
  platform: nrf52840dk/nrf52840
  product: Nordic nRF52840 DK (bay A3)
  runner: nrfutil
  id: '001050012345'
  serial: /dev/serial/by-id/usb-SEGGER_J-Link_001050012345-if00
  baud: 115200
  pre_script: /ci/rack-scripts/bay-a3-pre.sh
  script_param:
    pre_script_timeout: 90
  fixtures:
  - bay:A3
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
  up as two J-Links at once: without `id:` the runner may flash the wrong one.
  `hwmap` warns about runners shared by bays without an id.  For the `esp32`
  runner the serial port *is* the id, and bayctl fills it in.
* **`fixtures: [bay:<id>]`** lets a test plan pin a test to one bay
  (`--fixture bay:A3`); add your own per bay (`fixtures:` in `config/lab.yaml`).
* Bays without a platform, and `ci: false` bays (e.g. the one kept for a
  laptop in classic mode), stay out of the map; bays without a console path are
  written with `connected: false` until you add one.

## labgrid

```console
$ python tools/bayctl.py export labgrid > rack-env.yaml
```

gives one target per bay with the AUX UART as a raw `NetworkSerialPort` and the
node's power switch as an `ExternalPowerDriver` (`bayctl power <bay> on|off|cycle`).
USB stays with USB/IP: `bayctl attach <bay>` on the machine that runs the
flashing tool.

## LAVA (PDUDaemon)

```console
$ python tools/bayctl.py export pdudaemon > pdudaemon.conf
# PDUDaemon ports: 1=A1, 2=A2, 3=A3, ...
```

declares the rack as one PDU (`hw-testing-rack`) with PDUDaemon's
`localcmdline` driver, one port per bay in bay order (`bayctl power-port <n>`).
A LAVA device then uses the usual
`pduclient --daemon <host> --hostname hw-testing-rack --port <n> --command on|off|reboot`.

## By hand

```console
$ python tools/bayctl.py power B3 cycle --ms 2000
$ python tools/bayctl.py reset B3
$ python tools/bayctl.py boot B3          # ROM bootloader: BOOT held across a RESET pulse
$ python tools/bayctl.py mode C4 classic  # hand the DUT to the laptop on the front port
$ python tools/bayctl.py status B3
```

## Limits

* **No authentication** on the node (API, USB/IP, telnet, AUX port): keep the
  rack on a lab network or behind a VPN.
* **USB/IP through the ESP32-S3** is full speed, and Zephyr's DWC2 host driver
  does control, bulk and interrupt IN only: probes that need interrupt OUT
  (CMSIS-DAP v1, i.e. HID) or isochronous endpoints won't work yet; J-Link,
  ST-LINK, MCU-Link / CMSIS-DAP v2 (bulk) and CP210x / CH34x UART bridges do.
  Boards with an on-board USB hub don't work over USB/IP either.
* The AUX port takes **one client** at a time: while twister's `serial_pty`
  holds it, the web console and `nc` can't connect.
