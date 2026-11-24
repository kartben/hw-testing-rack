# Rack bus checklist: a hub and two nodes

The hub and two nodes on one row: the first time the row cable, the CAN bus and the position
token work together.  Each PCB passed its own checklist first.

:::{status} simulated
The rack bus runs on a simulated rack (native_sim): enumeration, restarts, dead and lost nodes.  No hub
and node have shared a row cable: the CAN transceivers and the position wire have never been powered, and
the expected values below are the design's.  [What exists today](../../plan/status.md#status-rack-bus).
:::

## 1. Wire

Hub row A → node 1's J1 (ROW IN); node 1's J2 (ROW OUT) → node 2's J1.  Row leads are JST PH 6,
"Same direction": a feed and a jumper of [Make the row cables](../row-cables.md), rung out there.
Nothing else plugged into the nodes.

With no power, at the hub: still ≈ 56 Ω between the CANH and CANL pads (the nodes add no
termination).

## 2. Power and enumerate

PD charger on the hub.  On the hub's console:

| Check | Expect |
|---|---|
| `hub status` | a 20 V contract, row A on |
| Two seconds after the row comes on, `hub nodes` | two nodes, A1 and A2, each with its MAC, its IP address and its firmware |
| `bay status` on each node | its position (A1, A2) and the hub's contract |
| `http://bay-a1.local/`, `http://bay-a2.local/` | each node's page |

## 3. Commands

| Check | Expect |
|---|---|
| `hub node A2 identify`, then `hub events` | node 2 shows itself; the answer is in the events |
| `hub row A cycle` | both nodes restart and come back as A1 and A2 |
| Node 2's lead moved to row B, `hub enumerate` | it comes back as B1 |
| `hub status` with both nodes running | the row's current, what two idle nodes draw: write it down |

Every `hub` command: [Power hub shell](../../reference/hub-shell.md).

## 4. If a node is missing from `hub nodes`

- [ ] Its 5V pad: the node must be running (the buck starts above 13.5 V).
- [ ] The lead: pin 1 of one end goes to pin 6 of the other on a "Same direction" lead.
- [ ] CANH and CANL swapped or open on that lead: every node after it is missing too.
- [ ] `hub enumerate` again once the node's page answers.

These checks want every pad in reach; for a bay missing from an assembled rack, see
[Troubleshooting](../../use/troubleshooting.md).  How the bus works: [Rack bus on CAN](../../can.md) and
[Rack bus protocol](../../rack-protocol.md).

With both nodes listed at their places, the PCBs are ready for [their trays](../fit-out-a-tray.md); the
whole rack is enumerated the same way on [Bring the rack online](../bring-the-rack-online.md).  A reading
that does not match: [report it](../../reference/known-limitations.md#report-a-finding).
