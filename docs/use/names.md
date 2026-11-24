# Bays, ports and addresses

A board in the rack is named by where it is plugged: `B3.2` is port 2 of the DATA board in bay B3, the third
bay of row B. The same board answers to other names, and each interface wants its own.

| Name | Example | Who uses it |
|---|---|---|
| Bay | `B3` | the drawer's label, the rack's page, `bayctl` |
| Port | `B3.2` | the bay's page, `bayctl`, reservations, board targets |
| Host name of the bay node | `bay-b3.local` | a browser, `curl`, `usbip`, telnet |
| USB/IP busid | `1-1.2` on a DATA ×4, `1-1.1` on a DATA ×6 | `usbip attach -b` |
| Node id on the rack bus | `0x13`, or 19 | the hub's shell and its HTTP API |
| A board alone in its bay | a port all the same: `A2.1`, not `A2` | see [A bay that holds one board](#a-bay-that-holds-one-board) |
| The hub | `rack.local` | a browser, and `bayctl` unless told otherwise |

:::{status} simulated
The busids by port are tested on native_sim with Zephyr's virtual USB bus, the enumeration on a simulated
rack, and `bayctl` against the simulated node. The mDNS names were used on the bench stand-ins. Nothing here
has run behind a DATA ×6 or a DATA ×4. See [What exists today](../plan/status.md#status-names).
:::

## A bay is a row letter and a place

Rows are lettered from the bottom, A first; the letter is the hub's output that feeds the row. The number is
the bay's place along the row cable, counted from the node the hub's feed plugs into: in the default rack
that is the left-hand bay, above the power box.

A node does not know its place. The hub hands it out over the rack bus each time a row is switched on or a
node restarts: it raises the row's position wire, the first node without an address answers with its MAC,
takes its row and place, and passes the wire on to the next. A node keeps nothing of this in flash, so the
name belongs to the place in the rack and not to the PCB: a node moved from B3 to C1 is C1. A dead node
stops the count for the bays after it in its row ([Troubleshooting](troubleshooting.md)).

On the rack bus a node is a number: its row times 16, plus its place, row A counting as 0. B3 is `0x13`
(19), C3 is `0x23` (35). The hub's HTTP API takes the number (`{"id": 35, …}`); its shell and
`bayctl hub node` take `C3` or `0x23` ([Rows and the rack's page](rack-page.md)).

## A port is the bay and a socket's number

`B3.1` to `B3.4` on a DATA ×4, `B3.1` to `B3.6` on a DATA ×6: the number is that of a USB-C socket of the
bay's DATA board. The screens say port, the API and `bayctl` say slot or sub-slot
([Glossary](../reference/glossary.md)).

Port 1 is the leftmost socket seen from the boards' side, from the front of the pulled-out drawer; the
others follow left to right. The drawer's port wall has six slots and no numbers: a DATA ×6 fills all six, a
DATA ×4 stands behind slots 2 to 5. Both boards print each port's number in a filled disc of silkscreen:
the DATA ×6 above each USB-C, where it shows over the port wall, the DATA ×4 just left of each socket.

A bay holds up to four boards flat on its plate with a DATA ×4, up to six on edge in a slot bin with a
DATA ×6, lane k on port k ([Put a board in a bay](mount-a-board.md)). A board with two USB connectors, one
for its probe and one for its own USB, takes two ports and so has two names. In the example rack, B3.3 is
a stock Pico 2 used as a stand-alone analyzer, chosen before the DATA ×4's co-processor, which is the bay's
own analyzer ([A Pico 2 on a port instead](logic-analyzer.md#a-pico-2-on-a-port-instead)). It is not a
board under test: commands that name the whole bay pass it by, except power.

## A bay that holds one board

A v1.0 node keeps its DATA lead off unless a DATA ×6 or a DATA ×4 answers on it
([ports.c](../../firmware/bay-node/src/ports.c)). So a bay with a single board still has a DATA board, and
the board is on one of its ports: the Nucleo-144 alone in A2 is `A2.1` if its cable is in the first socket.

`config/rack.yaml`, the example lab file and older text write such bays `A2`. That is the form of the bench
stand-ins and of the simulated node started without `--ports`, where the node switches one board itself,
its busid is `1-1` and its console is the bay's AUX UART. On a node with a DATA board the code answers the
bay's name like this:

| You send | The node with a DATA board |
|---|---|
| `bayctl power A2 cycle` | switches every port of the bay, the empty ones too; on a DATA ×6 it stops with an error at port 5, since firmware 0.5 gives per-port routes to ports 1 to 4 only ([Power-cycle or reset a board](power-and-reset.md#with-bayctl)) |
| `bayctl attach A2`, `detach A2`, `reset A2`, `boot A2` | act on the ports that hold something, here the one board |
| `bayctl prepare A2`, `bayctl pty A2`, the console `aux` in a port's board target | refused: `bay A2 holds several boards: say which`, and a port has no AUX UART |
| `/api/power` without `"port"` | 409, `this node serves 6 boards: say which` |

On a DATA ×6 with the cable in socket 1, the lone board's busid is `1-1.6`. Which DATA board and which
socket a lone board should take is not settled in the sources: it is an open question listed on
[Known issues, and what will not work](../reference/known-limitations.md).

## Host names, and how a bay gets its own

A node that has never been in a rack announces itself as `bay` followed by its MAC address. Once the hub
has given it a place it is `bay-a1.local`, in lower case, and it changes name when it changes place.
`bay id b3` in the node's shell fixes a name instead (1 to 15 letters, digits and hyphens, stored): that is
for a bay outside a rack, which no hub will ever name. In a rack, leave it unset.

The hub is `rack.local` as long as it has no id, and `hub id lab1` in its shell renames it
`rack-lab1.local`. `bayctl` looks for the hub at `rack.local` unless told otherwise, so after `hub id lab1`
every command warns `hub rack.local: no such host` and goes on with the lab file alone. Give the hub an id
only when two racks share a network, then name it to `bayctl`: `BAYCTL_HUB=rack-lab1.local`, or `hub:` in
the lab file ([Set up bayctl and usbip](set-up-your-machine.md)).

These are mDNS names. The DNS-SD records behind them are on
[Network ports, names, metrics](../reference/network.md); a network without mDNS is dealt with on the
set-up page.

## USB/IP busids on a DATA ×6 and on a DATA ×4

The node names a USB device by where it is plugged, as Linux does: `1-1.<hub port>`, the hub being the one
on the DATA board. A board keeps its busid through resets and re-plugs, and the hub itself is never offered.
The hub port is not always the port's number:

<!-- site:port-busid -->
| Port (USB-C socket) | busid on a DATA ×4 | busid on a DATA ×6 |
|---|---|---|
| 1 | `1-1.1` | `1-1.6` |
| 2 | `1-1.2` | `1-1.1` |
| 3 | `1-1.3` | `1-1.2` |
| 4 | `1-1.4` | `1-1.3` |
| 5 | no such port | `1-1.4` |
| 6 | no such port | `1-1.5` |
| the co-processor (logic analyzer) | `1-1.5` | no co-processor |
<!-- /site:port-busid -->

The DATA ×6 wires its port 1 to the hub's port 6 and port n to the hub's port n − 1
([design.py](../../electronics/data-port-x6/design.py)). So `1-1.2` is port 2 on a DATA ×4 and port 3 on a
DATA ×6, and a busid copied from another bay attaches the wrong board. Do not work it out: each row of the
bay's page shows it, `bayctl ports B3` prints it, and `bayctl attach B3.2` looks it up by itself
([USB/IP and flashing](usb-and-flashing.md)).
