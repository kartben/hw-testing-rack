# Bays, ports and addresses

Each board in the rack is named after where it is plugged in: `B3.2` is the board on port 2 of bay B3. The
tools use these names and addresses:

| Name | Example | Used by |
|---|---|---|
| Bay | `B3` | the drawer's label, the rack's page, `bayctl` |
| Port | `B3.2` | the bay's page, `bayctl`, reservations, board targets |
| Bay node's host name | `bay-b3.local` | a browser, `curl`, `usbip`, telnet |
| USB/IP busid | `1-1.2` on a DATA ×4 | `usbip attach -b` |
| Node id on the rack bus | `0x13` (19) | the hub's shell and HTTP API |
| The hub | `rack.local` | a browser, `bayctl` |

## Bay names

A bay's name is its row letter and its place in the row. Rows are lettered from the bottom: A, then B, C and D.
Your rack has one to four rows, with as many bays in each as you chose to build.

The number is the bay's place along its row cable, counted from the node where the cable from the hub plugs in.
That is usually the left-hand bay of the row.

The hub gives each node its place over the rack bus, the link that the row cables carry from the hub to the
nodes. It does this each time it switches a row on or a node restarts. So a bay's name goes with its place in
the rack: move a node from B3 to C1 and it becomes C1. A dead node stops the count for the bays after it in its
row ([Troubleshooting](troubleshooting.md)).

On the rack bus, a node is a number: 16 times its row, plus its place, counting row A as 0. B3 is `0x13` (19)
and C3 is `0x23` (35). The hub's HTTP API takes the number. Its shell and `bayctl hub node` take `C3` or `0x23`
([The rack's page](rack-page.md)).

## Port numbers

Each port is a USB-C socket of the bay's DATA board: `B3.1` to `B3.4` on a DATA ×4, `B3.1` to `B3.6` on a
DATA ×6. The pages say "port". The API and `bayctl` also say "slot" or "sub-slot".

Port 1 is the leftmost socket, seen from the front with the drawer pulled out. Both DATA boards print each
port's number in a filled disc: the DATA ×6 above each socket, the DATA ×4 to the left of it.

The port wall at the back of the drawer has six slots for the plugs. A DATA ×6 uses all six. A DATA ×4 stands
behind slots 2 to 5.

A board with two USB connectors, one for its probe and one for its own USB, takes two ports and has two names.

A port given `role: analyzer` in the lab file holds a logic analyzer, not a board under test. Commands that name
the whole bay skip it, except `power` ([Logic analyzer](logic-analyzer.md)).

## A bay that holds one board

Every bay has a DATA board, because the node does not switch its DATA lead on without one. So a board alone in
bay A2 is still on a port: `A2.1` if its cable is in the first socket. `config/rack.yaml` and the example lab
file call such a bay `A2`.

When you name the bay instead of the port:

| You run | What happens |
|---|---|
| `bayctl power A2 cycle` | switches every port of the bay, the empty ones too (on a DATA ×6, ports 1 to 4 only: [Limitations](../reference/known-limitations.md#the-firmware)) |
| `bayctl attach A2`, `detach A2`, `reset A2`, `boot A2` | acts on the ports that hold a board |
| `bayctl prepare A2` | refuses: `bay A2 holds several boards: say which` |

Name the port, `A2.1`, to act on that board alone.

## Host names

A node in a rack is `bay-a1.local`, `bay-b3.local` and so on, in lower case. It changes its name when it changes
place. A node that has never been in a rack is `bay` followed by its MAC address.

A bay on its own, outside a rack, can have a fixed name: run `bay id b3` in the node's shell. The name has 1 to
15 letters, digits and hyphens. In a rack, leave it unset.

The hub is `rack.local` until you give it an id: `hub id lab1` in its shell renames it `rack-lab1.local`. Give
the hub an id only when two racks share a network. Then tell `bayctl` the new name with `BAYCTL_HUB` or `hub:` in
the lab file ([Set up your machine](set-up-your-machine.md#how-it-finds-the-rack)).

These are mDNS names ([Network ports and metrics](../reference/network.md)). For a network without
mDNS, see [Set up your machine](set-up-your-machine.md#without-mdns-or-from-another-subnet).

## USB/IP busids

USB/IP names a USB device by its busid, the path to it through the USB hubs, as Linux does. On a bay it is
`1-1.<hub port>`, where the hub is the one on the DATA board. A board keeps its busid through resets and
replugs. The hub port is not always the port's number:

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

So a busid copied from another bay can attach the wrong board. You rarely need to type one. The bay's page shows
each port's busid, `bayctl ports B3` prints them, and `bayctl attach B3.2` looks it up for you
([USB/IP and flashing](usb-and-flashing.md)).
