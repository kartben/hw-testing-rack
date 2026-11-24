---
myst:
  substitutions:
    clone: |
      ```console
      $ git clone REPO_URL
      $ cd REPO_DIR
      $ pip install pyyaml
      ```
---

# Try it without hardware

The 3D model, a simulated bay with its real web page, and `bayctl` run today on a machine with Python and a
browser, with no rack, no PCB and no printer.

:::{status} simulated
Every command below was run on 2026-11-24, and what it printed is shown as it came. The simulated bay and
the simulated hub are models in Python that serve the real pages and answer the real API: they do not run
the firmware ([What exists today](status.md#status-bayctl)).
:::

## Walk round the rack in the 3D model

[The 3D model](/viewer/) opens in a browser, with nothing to install, and loads about 20 MB. It is generated
from `config/rack.yaml` and is the only current picture of the 12-bay rack.

Drag to orbit, scroll to zoom, click a bay. A click selects the bay and opens a panel with its boards, their
cables and its `usbip attach` command. In the *Controls* panel:

- *Drawers* pulls every drawer out along the slope, and *Explode* spreads the parts of the rack apart;
- *Inside view* hides the ladders, so that the bay nodes and the drag chains under the drawers show;
- *Camera preview* opens what the camera of B2 sees, the only bay of the example rack that has one;
- *Layers* switches each kind of part on and off: trays, drawers, board plates, row cables.

Four parameters in the address open the model on a chosen view; the links of this site use them:

| Parameter | Does |
|---|---|
| `bay=B3` | selects a bay and opens its panel. The name is exact: `b3` or a bay that does not exist stops the model from loading |
| `openbay=1` | with `bay`: pulls that bay's drawer out |
| `view=bay` | where the camera starts: `iso`, `front`, `side`, `rear`, `bay` for the selected bay, `camera` to look into a bay that has one |
| `hideui` | hides the panels |

So [`/viewer/?bay=B3&openbay=1&view=bay`](/viewer/?bay=B3&openbay=1&view=bay) is bay B3 with its drawer
out, and [`/viewer/?bay=B2&view=camera&camlight=1&preview=B2`](/viewer/?bay=B2&view=camera&camlight=1&preview=B2)
looks into B2 with its light on and its camera's picture beside it. Every parameter:
[Regenerate the site, the viewer, the renders, the drawings](../engineering/tools.md).

## Start a simulated bay

It takes Python 3.10 or later, PyYAML and a checkout of the repository:

{{ clone | replace("REPO_URL", repo_url) | replace("REPO_DIR", repo_url.split("/")[-1]) }}

Start a bay with a DATA ×4 and leave it running in its terminal:

```console
$ python firmware/bay-node/web/dev_server.py --ports 4
bay node mock on http://localhost:8766 (camera on port 8767), 4 ports
```

Open <http://localhost:8766>: it is the page a bay node serves, here for bay B3. The simulator puts four
made-up boards on its ports, B3.1 to B3.4, and every button acts on them.

```{figure} ../img/web-ui-ports.png
:class: bb-screenshot
:alt: The USB devices card of the simulated bay: four ports, one attached, one reserved, one queued

Simulated node: the *USB devices* card, one row per port, some way into a session. B3.1 is attached, B3.3
is reserved and B3.4 waits for power.
```

In a second terminal, tell `bayctl` where that bay is. It reads `config/lab.yaml`, which git ignores:

```{code-block} yaml
:caption: config/lab.yaml
bays:
  B3: {host: 127.0.0.1, http_port: 8766}
  B3.2: {platform: rpi_pico2/rp2350a/m33_0}
```

```console
$ export BAYCTL_HUB=none
$ python tools/bayctl.py ports B3
B3.1   port 1  VBUS on 95 mA  1fc9:0143 MCU-LINK on-board (r0E7) CMSIS-DAP V3.172  busid 1-1.1
B3.2   port 2  VBUS on 140 mA  0403:6001 FT232R USB UART  busid 1-1.2
B3.3   port 3  VBUS on 93 mA  2e8a:0003 RP2 Boot  busid 1-1.3
B3.4   port 4  VBUS on 93 mA  1a86:7523 None  busid 1-1.4
```

`BAYCTL_HUB=none` stops `bayctl` from looking for a power hub on the network. The currents move a little
from one call to the next. How `bayctl` finds a real rack, and what else a machine needs:
[Set up bayctl and usbip](../use/set-up-your-machine.md).

`--ports 6` is a bay with a DATA ×6. Started without `--ports`, the simulator is a bay node with one board and
the bay's serial console: a made-up Zephyr board that boots, logs in colour and answers a small shell. That
form is the bench stand-ins'; a v1.0 rack has a DATA board in every bay.

## A whole session on B3.2

The session of [A first session with a bay](../use/first-session.md), played on the simulated bay. Its
port 2 holds a made-up USB serial bridge; the lab file above calls it a Pico 2, as in the example rack.

Reserve the port, so that nobody else switches it meanwhile:

```console
$ python tools/bayctl.py lease B3.2 --for 30m --note "first session"
B3.2 reserved for 127.0.0.1, 1800 s
```

Tell the bay which board it is. The lab file names the board; `import lab` writes that to the bay, where
the page and every other machine see it (on the page, the *Set board…* button of the row):

```console
$ python tools/bayctl.py import lab config/lab.yaml B3.2
B3.2: rpi_pico2/rp2350a/m33_0, pinned to 0403:6001 S/N A50285BI
$ python tools/bayctl.py list
B3.1  -                   (no target)                        -                    usb     127.0.0.1
B3.2  rpi-pico2           rpi_pico2/rp2350a/m33_0            uf2                  usb     127.0.0.1
B3.3  -                   (no target)                        -                    usb     127.0.0.1
B3.4  -                   (no target)                        -                    usb     127.0.0.1
```

Power-cycle it. The port goes off for two seconds, and the board is back on the bus a moment after the
command returns:

```console
$ python tools/bayctl.py power B3.2 cycle --ms 2000
B3.2   port 2  VBUS on 93 mA  no USB device
$ python tools/bayctl.py ports B3
B3.1   port 1  VBUS on 91 mA  1fc9:0143 MCU-LINK on-board (r0E7) CMSIS-DAP V3.172  busid 1-1.1
B3.2   port 2  VBUS on 89 mA  0403:6001 FT232R USB UART  busid 1-1.2
B3.3   port 3  VBUS on 129 mA  2e8a:0003 RP2 Boot  busid 1-1.3
B3.4   port 4  VBUS on 84 mA  1a86:7523 None  busid 1-1.4
```

Reset it, or put it into its bootloader, through the DATA ×4's two lines for that port:

```console
$ python tools/bayctl.py reset B3.2
B3.2   port 2  VBUS on 88 mA  no USB device
$ python tools/bayctl.py boot B3.2
B3.2   port 2  VBUS on 86 mA  no USB device
```

On a rack the next three steps are `bayctl attach B3.2`, `west flash` and the board's own serial port on
your machine ([USB/IP and flashing](../use/usb-and-flashing.md)). The simulated bay serves HTTP only: nothing
answers on TCP 3240, so `attach` and `prepare` fail and there is no device to flash or to read. A hook makes
the page show what an attached port looks like, and the same address toggles the fake client off again:

```console
$ curl -s "http://localhost:8766/dev/attach?port=2" > /dev/null
$ python tools/bayctl.py ports B3
B3.1   port 1  VBUS on 125 mA  1fc9:0143 MCU-LINK on-board (r0E7) CMSIS-DAP V3.172  busid 1-1.1
B3.2   port 2  VBUS on 85 mA  0403:6001 FT232R USB UART  busid 1-1.2  USB/IP 192.168.1.41
B3.3   port 3  VBUS on 91 mA  2e8a:0003 RP2 Boot  busid 1-1.3
B3.4   port 4  VBUS on 89 mA  1a86:7523 None  busid 1-1.4
```

Hand the port back:

```console
$ python tools/bayctl.py release B3.2
B3.2 released
```

Every subcommand and option: [bayctl](../reference/bayctl.md).

## Break things on purpose

The simulator has hooks under `/dev/` that a real bay node does not have. Two of them show what a fault and
a full power budget look like, on the page and from `bayctl`.

An over-current on port 2. The port is cut and stays off until someone switches it on again:

```console
$ curl -s "http://localhost:8766/dev/fault?port=2" > /dev/null
$ python tools/bayctl.py ports B3
B3.1   port 1  VBUS on 95 mA  1fc9:0143 MCU-LINK on-board (r0E7) CMSIS-DAP V3.172  busid 1-1.1
B3.2   port 2  VBUS FAULT 0 mA  no USB device
B3.3   port 3  VBUS on 92 mA  2e8a:0003 RP2 Boot  busid 1-1.3
B3.4   port 4  VBUS on 84 mA  1a86:7523 None  busid 1-1.4
$ python tools/bayctl.py power B3.2 on
B3.2   port 2  VBUS on 96 mA  no USB device
```

A bay over its budget. Make the board on port 1 draw 900 mA, switch port 4 off, and ask for it again:

```console
$ curl -s "http://localhost:8766/dev/draw?port=1&ma=900" > /dev/null
$ python tools/bayctl.py power B3.4 off
B3.4   port 4  VBUS off 0 mA  no USB device
$ python tools/bayctl.py power B3.4 on
bayctl: B3.4: /api/ports/4/power: 409 no room in the bay's budget: the bay draws 8687 mW, 600 mW kept for a start, 5400 mW in all (the hub's grant)
$ python tools/bayctl.py power B3.4 on --when available
B3.4: queued, on as soon as the bay's budget has room
```

Give port 1 its usual draw back, and port 4 comes on by itself:

```console
$ curl -s "http://localhost:8766/dev/draw?port=1&ma=0" > /dev/null
$ python tools/bayctl.py ports B3
B3.1   port 1  VBUS on 94 mA  1fc9:0143 MCU-LINK on-board (r0E7) CMSIS-DAP V3.172  busid 1-1.1
B3.2   port 2  VBUS on 129 mA  0403:6001 FT232R USB UART  busid 1-1.2
B3.3   port 3  VBUS on 82 mA  2e8a:0003 RP2 Boot  busid 1-1.3
B3.4   port 4  VBUS on 84 mA  no USB device
```

Why a port waits, and what the 5400 mW are: [Power budget and queued ports](../use/power-budget.md). The
other hooks (another address, a firmware image to send, an update that rolls back, a camera unplugged) are
listed at the top of [dev_server.py](../../firmware/bay-node/web/dev_server.py).

## The rack's page, simulated

The simulated bay's camera sits on port 8767, which is also the simulated hub's default: give the hub
another one.

```console
$ python firmware/power-hub/web/dev_server.py 8770
power hub mock on http://localhost:8770
```

<http://localhost:8770> is the page the power hub serves: the contract with the charger, the rack bus, the
rows with their bays, the events. This hub has eight made-up bays in rows A to C, and row D on with nothing
on it.

```{figure} ../img/hub-ui-dark.png
:class: bb-screenshot
:alt: The rack's page: the USB-C contract, the rack bus, rows A to D with their bays, the events
:width: 80%

Simulated hub: the rack's page. Reading it is open to anyone; its buttons ask for the hub to be claimed
first, and on the simulator `/dev/boot` is the press on BOOT that confirms the claim.
```

`bayctl` reads it the same way, with the hub's address in place of `none`:

```console
$ BAYCTL_HUB=127.0.0.1:8770 python tools/bayctl.py hub
rack  192.168.1.40  PD 20.0 V / 5.00 A (used 29.4 W / 90.0 W budget)  CAN 8 nodes (0 lost)
row A  ON        661 mA   13.2 W  A1(attached 161mA) A2(usbip 138mA) A3(attached 239mA)
row B  ON        398 mA    8.0 W [faults:1]  B1(classic 126mA) B2(off 0mA) B3(enumerated 147mA)
row C  ON        413 mA    8.3 W  C1(attached 184mA) C2(usbip 147mA)
row D  ON          0 mA    0.0 W
```

Make the charger renegotiate down to 20 V and 1.5 A (30 W), and the hub sheds a row to stay inside its
grant:

```console
$ curl -s http://localhost:8770/dev/drop > /dev/null
$ BAYCTL_HUB=127.0.0.1:8770 python tools/bayctl.py hub
rack  192.168.1.40  PD 20.0 V / 1.50 A (used 21.3 W / 27.0 W budget)  SHED:C  CAN 6 nodes (0 lost)
row A  ON        665 mA   13.3 W  A1(attached 162mA) A2(usbip 139mA) A3(attached 241mA)
row B  ON        400 mA    8.0 W [faults:1]  B1(classic 127mA) B2(off 0mA) B3(enumerated 148mA)
row C  SHED        0 mA    0.0 W
row D  ON          0 mA    0.0 W
```

`/dev/restore` brings the first charger back, `/dev/fault?row=B` trips a row's eFuse and
`/dev/lose?node=0x13` silences a bay. The two simulators do not know each other: the hub's bays have made-up
addresses, so keep `BAYCTL_HUB=none` for the commands that talk to the simulated bay. The page itself:
[Rows and the rack's page](../use/rack-page.md).

## A twister hardware map without a rack

The repository's CI builds a hardware map at every push, from the example lab file alone:

```console
$ BAYCTL_HUB=none python tools/bayctl.py --lab config/lab.example.yaml hwmap -o rack-map.yaml --python python3
```

It prints eight warnings about what the example leaves open (A2 has no board target, A4 no console path,
B3.2 no probe, so flashing it takes BOOTSEL), then says that it wrote
`rack-map.yaml` with 7 boards and one pre-script per board in `rack-scripts/`. Git ignores both. The map's
first board:

```{code-block} yaml
:caption: rack-map.yaml, its first board
- connected: true
  platform: nucleo_g474re
  product: ST NUCLEO-64 (MB1136 / MB1367) (bay A1)
  runner: stm32cubeprogrammer
  id: 003A00283133510837363734
  serial: /dev/serial/by-id/usb-STMicroelectronics_STLINK-V3_003A00283133510837363734-if02
  baud: 115200
```

What twister does with it, and what a pre-script runs: [Zephyr twister](../use/twister.md).

## The logic analyzer's demo capture

[The analyzer page](/analyzer/) opens on a capture of made-up signals: a UART line at 1 Mbd and its answer,
an I²C register read at 400 kHz, an SPI flash ID read at 4 MHz and three WS2812B LEDs, sampled at 20 MS/s on
8 channels. Panning, zooming, decoders and the `.vcd` export work on the demo in any browser; a real
analyzer on USB takes Chrome or Edge.

The simulated DATA ×4 bay has the same analyzer behind its co-processor, with a UART on buses A and B. With
Node 22 or later installed, `bayctl` captures and decodes it without a browser:

```console
$ python tools/bayctl.py capture B3 --ch A,B --rate 2M --duration 20ms --decode uart:rx=A,baud=115200 -o run1
armed
B3: 40,000 samples at 2 MS/s, 20.000 ms
  UART 115200 Bd (A), 17: Hello from B3.2\r\n
wrote run1.capture.json, run1.decoded.json
```

The bay's page opens `run1.capture.json` again in its *Logic analyzer* card:
[Logic analyzer](../use/logic-analyzer.md).

The step after the simulators is the firmware itself on a bought ESP32-S3 board, an M5Stack CoreS3 or a XIAO
ESP32-S3, with a real board on its USB: [bench.md](../bench.md) says which of the two tests what.
