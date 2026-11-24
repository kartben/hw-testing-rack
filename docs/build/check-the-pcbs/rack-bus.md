# Check the rack bus

The rack bus is the CAN bus and the position wire in the row cables. The hub uses it to find the nodes and give
each one its position. Check it with the hub and two nodes on one row, once each has passed its own checklist.
A single bay on a desk has no hub: skip this page.

## 1. Wire two nodes to the hub

Take a feed and a jumper from [Make the row cables](../row-cables.md), both rung out. Run the feed from row A
of the hub to J1 (ROW IN) on the first node. Run the jumper from J2 (ROW OUT) on the first node to J1 on the
second. Plug nothing else into the nodes.

With no power, measure between the CANH and CANL pads of the hub. It still reads about 56 Ω, because the nodes
add no termination.

## 2. Power the row and list the nodes

Plug the PD charger into the hub. Open the hub's console on J6 and run these checks:

| Check | Expect |
|---|---|
| `hub status` | a 20 V contract, row A on |
| `hub nodes`, two seconds after the row comes on | two nodes, A1 and A2, each with its MAC, its IP address and its firmware |
| `bay status` on each node | its position (A1 or A2) and the hub's contract |
| `http://bay-a1.local/` and `http://bay-a2.local/` | the page of each node |

## 3. Send commands over the bus

| Check | Expect |
|---|---|
| `hub node A2 identify`, then `hub events` | the LED of the second node blinks white and blue for 10 s, and its answer is in the events |
| `hub row A cycle` | both nodes restart and come back as A1 and A2 |
| The second node's cable moved to row B, then `hub enumerate` | it comes back as B1 |
| `hub status` with both nodes running | the current on row A, which is what two idle nodes draw: write it down |

[Power hub shell](../../reference/hub-shell.md) lists every `hub` command.

## 4. If a node is missing from `hub nodes`

- [ ] Its 5V pad: the node must be running. Its buck starts above 13.5 V.
- [ ] The cable: on a "Same direction" cable, pin 1 of one end goes to pin 6 of the other.
- [ ] CANH and CANL swapped or open on that cable: every node after it is missing too.
- [ ] `hub enumerate` again, once the node's page answers.

These checks need the pads within reach. For a bay missing from an assembled rack, see
[Troubleshooting](../../use/troubleshooting.md).

When both nodes are listed in their places, the PCBs are ready for [their trays](../fit-out-a-tray.md).
[Bring the rack online](../bring-the-rack-online.md) lists the nodes of the whole rack the same way.
