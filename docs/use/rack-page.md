# The rack's page

The power hub serves a page for the whole rack at `http://rack.local/`. Use it to switch rows of bays on and
off, to find a bay, and to send a command to a bay that is not on Wi-Fi.

If you gave the hub an id, the address is `rack-<id>.local` ([Bays, ports and addresses](names.md)). Anyone
on the network can read the page. To switch a row or send a command, you need the hub's admin key
([Control who can use the rack](access.md)).

## What the page shows

```{figure} ../img/hub-ui-light.png
:class: bb-screenshot
:alt: The rack's page: the header, the USB-C PD and rack bus cards, four rows of bays, the events

A simulated hub with eight bays in rows A to C. Row D is on, with no bay on it.
```

The **USB-C PD** card at the top shows what the rows draw from the charger. The **Rack bus** card counts the
bays. Below them, each row has a shelf with a tile for each of its bays. The hub's last events come last.

A tile shows the bay's place (`B3`), its address and what it is doing: `device ready`, `USB/IP attached`,
`DUT off` and so on. It also reads `<x> of <y> W`: the bay draws x watts, and the hub grants it y
([Power budget and queued ports](power-budget.md)). A camera icon marks a bay with a camera. The icon turns red
while someone watches. Every label is explained on
[States and messages](../reference/states-and-messages.md#a-bays-states-on-the-racks-page).

The pill at the top right reads `20 V` once the USB-C PD contract with the charger is settled. The rack always
runs at 20 V: leave the `28 V EPR when offered` switch alone. A red banner under the pill names a row in fault
or a bay that stopped answering.

## Switch or cycle a row

Each shelf has a **Cycle** and an **Off** button, or **On** when the row is off. The page asks you to confirm,
because every board in the row loses power. **Cycle** keeps the row off for 2 s, then switches it back on.

The hub remembers which rows are on and which are off, and keeps them that way after a restart. When a row
comes back on, its bays reappear in their places after a few seconds. This works even when the hub has no
Wi-Fi.

What each board loses when its row goes off:
[After a power cut or a restart](power-and-reset.md#after-a-power-cut-or-a-restart).

## Send a command to a bay

Click a tile to open its menu. It shows the bay's address, MAC and firmware version, a link to the bay's page,
and the commands below. Ctrl-click (Cmd-click on a Mac) opens the bay's page directly.

The commands go over the rack bus, the wired bus between the hub and the bay nodes. They reach a bay even when
it has no network address.

| Command | What the bay does |
|---|---|
| Identify | its status LED blinks white and blue for 10 s |
| Reset the board | pulls the node's AUX RESET line low for 100 ms |
| Board into its bootloader | holds AUX BOOT low through a RESET pulse |
| Power on, Power off | switches the DATA lead: the DATA board and every board on it |
| Power-cycle the board | switches the DATA lead off for 1 s, then on |
| Reboot the bay node | restarts the node; its USB/IP and console sessions drop |

Reset and bootloader use the RESET and BOOT lines of the node's AUX socket
([Use the bay's AUX UART](serial-console.md#use-the-bays-aux-uart)). To reset a board on a port of a DATA ×4, use the bay's
own page instead ([Reset and bootloader](power-and-reset.md#reset-and-bootloader)).

The bay's answer appears in the events: `node B3: command 0x02 done`, `refused`, or `no answer to command
0x02`. A reserved bay refuses every command except Identify ([Reserve a bay](reserve-a-bay.md)). A power-on
comes back `failed` when the DATA lead's checks keep the lead off. The bay's page then says why
([Why the DATA lead stays off](../reference/states-and-messages.md#why-the-data-lead-stays-off)).

## Read the events

The hub keeps its last 32 events until it restarts. The page shows the last eight, and **Show all** shows the
rest. [The hub's events](../reference/states-and-messages.md#the-hubs-events) lists every message.

```{figure} ../img/hub-ui-fault.png
:class: bb-screenshot
:alt: The rack's page with a red banner, row B in fault and bay B3 dashed, and the events under it

A simulated hub with row B in current limit and bay B3 not answering. Look at the red banner, the red shelf
and the dashed tile.
```

## With bayctl

`bayctl` finds the hub as [Set up your machine](set-up-your-machine.md#how-it-finds-the-rack) describes. A
command that changes something needs the admin key in `BAYCTL_KEY`.

```console
$ python tools/bayctl.py hub
rack  192.168.1.40  PD 20.0 V / 5.00 A (used 29.2 W / 90.0 W budget)  CAN 8 nodes (0 lost)
row A  ON        647 mA   12.9 W  A1(attached 165mA) A2(usbip 137mA) A3(attached 222mA)
row B  ON        404 mA    8.1 W [faults:1]  B1(classic 126mA) B2(off 0mA) B3(enumerated 153mA)
row C  ON        409 mA    8.2 W  C1(attached 185mA) C2(usbip 142mA)
row D  ON          0 mA    0.0 W
$ python tools/bayctl.py row B cycle
$ python tools/bayctl.py hub node B3 identify
$ python tools/bayctl.py hub events
```

`bayctl row` keeps the row off for 1000 ms. `--ms` sets another time. `hub node` takes `identify`,
`reset`, `bootloader`, `power-on`, `power-off`, `power-cycle` or `reboot`. Every option:
[bayctl](../reference/bayctl.md#rows-and-the-hub).

## Over HTTP

```console
$ curl -s rack.local/api/status
$ curl -s rack.local/api/events
```

To switch a row or send a command, sign a `POST` to `/api/row` or `/api/node`:
[Power hub HTTP API](../reference/hub-api.md).

## In the hub's shell

The hub's shell is on its console USB-C port, in the front wall of the power box. It has every command above
except `power-on` and `power-off`.

```console
uart:~$ hub status
uart:~$ hub row B cycle
uart:~$ hub node B3 identify
uart:~$ hub events
```

Every command: [Power hub shell](../reference/hub-shell.md).

## Row D says no node answered

The hub always has four row outputs. If your rack has fewer than four rows, the spare rows are on with nothing
on them, and their shelves read "no node answered". This does no harm. To switch a spare row off for good,
run `hub row <letter> off` in the hub's shell, for example `hub row D off`.

On a row that should have bays, "no node answered" means that none of its bays got an address on the rack
bus. Check the row's feed, then its first node: a node with no firmware stops the row there. See
[Troubleshooting](troubleshooting.md).
