# Rows and the rack's page (the hub)

The power hub serves the rack's page at `http://rack.local/`: the charger's contract, the rack bus, one shelf
per row with a tile for every bay by its place, and the hub's last events. From it you switch a row, blink a
bay's LED to find it, and act on a bay that is not on Wi-Fi.

:::{status} simulated
The page and `bayctl` have run against the simulated hub, and the rack bus on native_sim with simulated nodes.
The page also loads whole from a XIAO ESP32-S3 running the hub's firmware. No hub has been on a bench. See
[What exists today](../plan/status.md#status-rack-page).
:::

Needs: the hub on your network, at `rack.local` until it is given a rack id, `rack-<id>.local` after
([Bays, ports and addresses](names.md)). Reading is open to anyone; switching and commands ask for the hub's
admin key ([Access rules and security](access.md)).

## The page, card by card

```{figure} ../img/hub-ui-light.png
:class: bb-screenshot
:alt: The rack's page: the header, the USB-C PD and rack bus cards, four rows of bays, the events

The simulated hub: eight bays in rows A to C, row D on with nothing on it. A rack of the default layout shows
twelve.
```

The header gives the hub's name, address and number of bays, and two pills on the right. The access pill reads
`admin`, `read-only · unlock` or `unclaimed · claim`; click it to unlock or claim. The state pill reads `20 V`
once the contract is final, else `contract settling`, `rows shed`, `row fault`, `no PD charger`, or `offline`
when the page lost the hub ([what each means](../reference/states-and-messages.md#the-contracts-states)). A red
banner under the header names a row in fault, a bay that stopped answering, or a rack bus that is not
error-active.

The **USB-C PD** card shows the volts, amps and watts the rows draw, the last two minutes of their power, and
the charger's offers, the one in use highlighted. Its switch chooses between `20 V` and `28 V EPR when offered`;
on a default build 28 V is locked out, so the switch changes nothing and the hub stays at 20 V
([Power hub shell](../reference/hub-shell.md#notes)).

**Rack bus** counts the bays, the frames per second and the bus's error counters as they stand now, not a
total. It says when the bus was last numbered and how many bays were lost, and holds **Re-enumerate** and, on a
build with updates over the network, **Update firmware…** ([Update the firmware](update-firmware.md)).

**Rows** draws what each row takes from the charger, with a mark at the budget, then one shelf per row: its
letter, its state and current, its bays, and two buttons. A tile names the bay by its place (`B3`), its
address, what it is doing (`USB/IP attached`, `device ready`, `no device`, `DUT off`, `no answer`…) and, on a
v1.0 bay, `<x> of <y> W`: what its DATA lead draws against the hub's grant. A camera icon marks a bay with a
camera, red while someone watches. Every label is on
[States and error messages](../reference/states-and-messages.md#a-bays-states-on-the-racks-page).

Under the rows come the last eight events, and **Show all** for the rest. The foot counts the faults and sheds
since the hub started and links `/api/status` and `/metrics`. The page reads `/api/status` every 2 s and the
events every 5 s.

## Switch or cycle a row

Each shelf has **Cycle** and **Off** (**On** for a row that is off). The page asks before it switches off or
cycles a row that is on, since every board of the row loses power. **Cycle** is greyed while the row is off. A
cycle keeps the row off 2000 ms from the page, the hub's shell and the API without `ms`; `bayctl row` keeps it
off 1000 ms unless given `--ms`.

A row's on and off is saved and comes back after a restart of the hub; a cycle is not, and ends with the row
on. Switching a row off drops its bays from the page. When a row comes on, the hub numbers every powered row
again 2 s later, once the nodes have started, and the bays reappear at their places. What each bay and board
goes through, and what it loses: [Power-cycle or reset a board](power-and-reset.md#after-a-power-cut-or-a-restart).

Power and the rack bus do not need the hub's Wi-Fi: the rows come on and the bays get their places with the hub
off the network.

## Act on a bay through the hub

Click a tile. Its menu shows the bay's place, its node id (`0x23` for C3), its address, MAC and firmware, and
holds **Open the bay's page ↗**, **Camera: live view ↗** on a bay with a camera, and the commands below.
Ctrl-click (Cmd-click on a Mac) opens the bay's page straight away.

The commands travel on the rack bus, not over Wi-Fi, so they reach a bay that has no address. The page asks
before **Power off**, **Power-cycle** and **Reboot**. On a v1.0 bay:

| Command | What the bay does |
|---|---|
| Identify | its status LED blinks white and blue for 10 s ([the bay's LED](../reference/leds-and-buttons.md#the-bays-led)) |
| Reset the board | pulses the node's AUX RESET line low for 100 ms |
| Board into its bootloader | holds the node's AUX BOOT line across a RESET pulse, then releases it 200 ms later |
| Power on, power off | switches the DATA lead: every board of the bay |
| Power-cycle the board | the DATA lead off for 1 s, then on; the ports come back one at a time, 300 ms apart |
| Reboot the bay node | restarts the node itself, 200 ms later; its USB/IP and console sessions drop |

Reset and bootloader act on the node's AUX lines, not on a port of a DATA ×4: a port's reset is on the bay's
own page ([Power-cycle or reset a board](power-and-reset.md#reset-and-bootloader)).

The page only sends the command. The bay's answer comes as an event, `node B3: command 0x02 done`, or
`refused`, or `no answer to command 0x02` after three tries 100 ms apart. A reserved bay refuses everything
but Identify ([Reserve a bay](reserve-a-bay.md)). A power-on comes back `failed` when the DATA lead's checks
keep the lead off; the bay's page then says why
([States and error messages](../reference/states-and-messages.md#why-the-data-lead-stays-off)).

## Read the events

The hub keeps its last 32 events in RAM and loses them when it restarts. Each has a kind: `pd` for the charger
and the contract, `row`, `fault`, `can` for the rack bus, `node` for a bay's answers, `firmware` for an update.
The page turns each event's age into a time of day. The firmware's texts are listed on
[States and error messages](../reference/states-and-messages.md#the-hubs-events).

```{figure} ../img/hub-ui-fault.png
:class: bb-screenshot
:alt: The rack's page with a red banner, row B in fault and bay B3 dashed, and the events under it

The simulated hub with row B's eFuse in current limit and bay B3 silent: the banner and the dashed tile are as
the firmware's page draws them, the event texts are the simulator's own.
```

## With bayctl

`bayctl` finds the hub at `BAYCTL_HUB`, else at `hub:` in the lab file, else at `rack.local`
([Set up bayctl and usbip](set-up-your-machine.md#how-it-finds-the-rack)). Reading needs nothing more; every
other command needs the admin key in `BAYCTL_KEY`.

```console
$ python tools/bayctl.py hub
$ python tools/bayctl.py row B cycle --ms 2000
$ python tools/bayctl.py hub node B3 identify
$ python tools/bayctl.py hub node B3 power-cycle
$ python tools/bayctl.py hub events
```

`hub` prints the contract and the budget, then a line per row with its bays. Against the simulated hub:

```console
$ python tools/bayctl.py hub
rack  192.168.1.40  PD 20.0 V / 5.00 A (used 29.2 W / 90.0 W budget)  CAN 8 nodes (0 lost)
row A  ON        647 mA   12.9 W  A1(attached 165mA) A2(usbip 137mA) A3(attached 222mA)
row B  ON        404 mA    8.1 W [faults:1]  B1(classic 126mA) B2(off 0mA) B3(enumerated 153mA)
row C  ON        409 mA    8.2 W  C1(attached 185mA) C2(usbip 142mA)
row D  ON          0 mA    0.0 W
```

`hub node` takes the menu's seven commands, `identify`, `reset`, `bootloader`, `power-on`, `power-off`,
`power-cycle`, `reboot`, and a place (`B3`) or a node id (`0x13`). `row` prints the row's line. Every option:
[bayctl](../reference/bayctl.md#rows-and-the-hub).

## Over HTTP

```console
$ curl -s rack.local/api/status
$ curl -s rack.local/api/events
```

Actions are signed requests: `POST /api/row` with `{"row": "B", "action": "cycle"}`, `POST /api/node` with the
bay as a number, `{"id": 19, "action": "identify"}` for B3 (the row's index, A being 0, times 16, plus the
place). How to sign them, and every field: [Power hub HTTP API](../reference/hub-api.md).

## In the hub's shell

The shell is on the hub's console USB-C, in the power box's front wall, and nowhere else. It has five of the
seven commands: `power-on` and `power-off` are not in it.

```console
uart:~$ hub status
uart:~$ hub row B cycle
uart:~$ hub node B3 identify
uart:~$ hub events
```

Every command: [Power hub shell](../reference/hub-shell.md).

## Row D says no node answered

The hub has four row outputs and switches all four on; the default rack fills A to C. Row D is on, empty, and
its shelf reads "no node answered". It costs nothing: the shedding passes over a row with no node that draws
under 100 mA. `hub row D off` switches it off for good (the choice is saved), and the shelf then reads "row off".

On a row that should have bays, the same words mean that none got an address: look at the row's feed, and at
the first node, which stops the row there if it has no firmware. A node that asked and never confirmed its address shows as
"no address", and the bays after it are missing. What to check: [Troubleshooting](troubleshooting.md).
