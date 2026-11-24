---
myst:
  substitutions:
    clone: |
      ```console
      $ git clone REPO_URL
      $ cd REPO_DIR
      $ python3 -m venv .venv
      $ . .venv/bin/activate
      $ pip install pyyaml
      ```
---

# Try it without hardware

You can try BitBunk on your own computer before you build anything. Look at a rack in the 3D model, then
open the web page of a simulated bay and drive it with `bayctl`, the rack's command-line tool. You need
a browser and Python.

## Explore the 3D model

[The 3D model](/viewer/) opens in your browser, with nothing to install. It loads about 20 MB.

Drag to turn the rack, scroll to zoom, and click a bay. The bay's panel shows its boards, their cables
and the `usbip attach` command for each. The *Controls* panel pulls the drawers out, spreads the parts apart
and hides the side walls, so that you can see the bay nodes and the drag chains. It also shows or hides each
kind of part. *Camera preview* shows what bay B2's camera sees.

The address can name a bay: [`/viewer/?bay=B3&openbay=1&view=bay`](/viewer/?bay=B3&openbay=1&view=bay)
opens the model on bay B3, with its drawer out.

## Start a simulated bay

You need Python 3.10 or later and a copy of the repository. The simulator needs only PyYAML. Install it in a
virtual environment:

{{ clone | replace("REPO_URL", repo_url) | replace("REPO_DIR", repo_url.split("/")[-1]) }}

Start a bay with a DATA ×4, the DATA board with four ports. Leave it running in its terminal:

```console
$ python firmware/bay-node/web/dev_server.py --ports 4
bay node mock on http://localhost:8766 (camera on port 8767), 4 ports
```

Open <http://localhost:8766>. You see the page that a bay node serves, here for bay B3. Four made-up boards
sit on its ports, B3.1 to B3.4, and every button works on them.

For a bay with a DATA ×6, use `--ports 6`. If port 8766 is taken, put another port number before `--ports`,
such as `dev_server.py 8790 --ports 4`, and use that number in the lab file below.

```{figure} ../img/web-ui-ports.png
:class: bb-screenshot
:alt: The USB devices card of the simulated bay: four ports, one attached, one reserved, one queued

Simulated node: the *USB devices* card has one row per port. Here B3.1 is attached, B3.3 is reserved and
B3.4 waits for power.
```

`bayctl` finds the bays through a lab file. In a second terminal, write this one as `sim-lab.yaml` at the top
of the repository. It also says which board sits on port 2:

```{code-block} yaml
:caption: sim-lab.yaml
bays:
  B3: {host: 127.0.0.1, http_port: 8766}
  B3.2: {platform: rpi_pico2/rp2350a/m33_0}
```

Activate the environment in this terminal too. Then point `bayctl` at the lab file and list the ports.
`BAYCTL_HUB=none` stops it from looking for a power hub:

```console
$ . .venv/bin/activate
$ export BAYCTL_LAB=$PWD/sim-lab.yaml BAYCTL_HUB=none
$ python tools/bayctl.py ports B3
B3.1   port 1  VBUS on 95 mA  1fc9:0143 MCU-LINK on-board (r0E7) CMSIS-DAP V3.172  busid 1-1.1
B3.2   port 2  VBUS on 140 mA  0403:6001 FT232R USB UART  busid 1-1.2
B3.3   port 3  VBUS on 93 mA  2e8a:0003 RP2 Boot  busid 1-1.3
B3.4   port 4  VBUS on 93 mA  1a86:7523 None  busid 1-1.4
```

The currents change a little from one call to the next. On a real bay this list shows only the VID and PID,
and `bayctl status B3` gives the product names. To point `bayctl` at a real rack, see
[Set up your machine](../use/set-up-your-machine.md).

## Run a session on B3.2

These steps follow [A first session with a bay](../use/first-session.md), on the simulated bay.

Reserve the port, so that nobody else switches it while you work:

```console
$ python tools/bayctl.py lease B3.2 --for 30m --note "first session"
B3.2 reserved for 127.0.0.1, 1800 s
```

Tell the bay which board is on the port. `import lab` copies the board from the lab file to the bay. Its page
and every other machine then see it:

```console
$ python tools/bayctl.py import lab sim-lab.yaml B3.2
B3.2: rpi_pico2/rp2350a/m33_0, pinned to 0403:6001 S/N A50285BI
```

Power-cycle the board. The port switches off for two seconds. The board is back on the bus a moment after the
command returns:

```console
$ python tools/bayctl.py power B3.2 cycle --ms 2000
B3.2   port 2  VBUS on 93 mA  no USB device
```

Reset the board, or put it into its bootloader. The DATA ×4 has a reset line and a boot line for each port:

```console
$ python tools/bayctl.py reset B3.2
B3.2   port 2  VBUS on 88 mA  no USB device
$ python tools/bayctl.py boot B3.2
B3.2   port 2  VBUS on 86 mA  no USB device
```

On a real rack you would now attach the board's USB with `bayctl attach B3.2` and flash it with `west flash`
([USB/IP and flashing](../use/usb-and-flashing.md)). The simulated bay has no USB/IP server, so `attach`
fails here. To see how an attached port looks on the page, call this test hook. Call it again to undo it:

```console
$ curl -s "http://localhost:8766/dev/attach?port=2" > /dev/null
```

Hand the port back when you are done:

```console
$ python tools/bayctl.py release B3.2
B3.2 released
```

Every subcommand and option is on [bayctl](../reference/bayctl.md).

## Simulate a fault

The simulator has test hooks under `/dev/` that a real bay node does not have. Two of them cause a fault and
fill the power budget.

Cause an over-current on port 2. The port switches off and stays off until you switch it on again:

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

Now push the bay over its power budget. Make the board on port 1 draw 900 mA, then switch port 4 off and on
again. The bay refuses, and `--when available` queues the port instead:

```console
$ curl -s "http://localhost:8766/dev/draw?port=1&ma=900" > /dev/null
$ python tools/bayctl.py power B3.4 off
B3.4   port 4  VBUS off 0 mA  no USB device
$ python tools/bayctl.py power B3.4 on
bayctl: B3.4: /api/ports/4/power: 409 no room in the bay's budget: the bay draws 8687 mW, 600 mW kept for a start, 5400 mW in all (the hub's grant)
$ python tools/bayctl.py power B3.4 on --when available
B3.4: queued, on as soon as the bay's budget has room
```

Set port 1 back to its usual draw, and port 4 comes on by itself:

```console
$ curl -s "http://localhost:8766/dev/draw?port=1&ma=0" > /dev/null
```

Why a port waits:
[Power budget and queued ports](../use/power-budget.md). The other test hooks are listed at the top of
[dev_server.py](../../firmware/bay-node/web/dev_server.py).

## Open the rack's page

The power hub has a simulator too. Its default port, 8767, is taken by the simulated bay's camera. Start it
on port 8770 in a third terminal, and leave it running:

```console
$ . .venv/bin/activate
$ python firmware/power-hub/web/dev_server.py 8770
power hub mock on http://localhost:8770
```

Open <http://localhost:8770>. This is the rack's page, served by the power hub. It shows the USB PD
contract with the charger, each row with its bays, and the events. The simulated hub has eight made-up bays
in rows A to C. Row D is empty.

```{figure} ../img/hub-ui-dark.png
:class: bb-screenshot
:alt: The rack's page: the USB-C contract, the rack bus, rows A to D with eight bays in rows A to C, the events
:width: 80%

Simulated hub: the rack's page. Anyone can read it. Its buttons work only after you claim the hub. On the
simulator, `/dev/boot` stands in for the press on BOOT that confirms the claim.
```

`bayctl` reads the hub too. Give it the hub's address in `BAYCTL_HUB`:

```console
$ BAYCTL_HUB=127.0.0.1:8770 python tools/bayctl.py hub
rack  192.168.1.40  PD 20.0 V / 5.00 A (used 29.4 W / 90.0 W budget)  CAN 8 nodes (0 lost)
row A  ON        661 mA   13.2 W  A1(attached 161mA) A2(usbip 138mA) A3(attached 239mA)
row B  ON        398 mA    8.0 W [faults:1]  B1(classic 126mA) B2(off 0mA) B3(enumerated 147mA)
row C  ON        413 mA    8.3 W  C1(attached 184mA) C2(usbip 147mA)
row D  ON          0 mA    0.0 W
```

`curl -s http://localhost:8770/dev/drop` makes the charger drop to 30 W. The hub then switches a row off to
stay within it. `/dev/restore` brings the charger back.

The two simulators do not know about each other. Keep `BAYCTL_HUB=none` for the commands to the simulated
bay. What the page shows: [The rack's page](../use/rack-page.md).

(a-twister-hardware-map-without-a-rack)=
## Make a twister hardware map

`bayctl` writes a hardware map for Zephyr's twister from a lab file. Try it on the example lab file:

```console
$ BAYCTL_HUB=none python tools/bayctl.py --lab config/lab.example.yaml hwmap -o rack-map.yaml
```

It warns about what the lab file leaves out, such as a board with no board target. Then it writes
`rack-map.yaml`, and a pre-script for each board in `rack-scripts/`. To run twister with it, see
[Run twister on the rack](../use/twister.md).

(the-logic-analyzers-demo-capture)=
## Try the logic analyzer

[The analyzer page](/analyzer/) opens on a demo capture of made-up signals on 8 channels: a UART at 1 Mbd, an
I²C read, an SPI flash ID read and three WS2812B LEDs. You can pan, zoom, decode and export to `.vcd` in any
browser. To use a real analyzer over USB, you need Chrome or Edge.

The simulated DATA ×4 bay has the same analyzer on its page, with a UART on its buses A and B:
[Logic analyzer](../use/logic-analyzer.md).
