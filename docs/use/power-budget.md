# Power budget and queued ports

One charger feeds the whole rack, and two limits share it out. The hub grants each bay a few watts on its DATA
lead, and the bay node switches its ports on only within that grant. Over the bays, the hub switches whole rows
off when the rack draws more than the charger agreed to give.

:::{status} simulated
Both sides are tested on native_sim, the hub's with made-up contracts and the bay's against emulated DATA
boards. No charger and no real load have been tried, and no hub has sent a grant to a real node. See
[What exists today](../plan/status.md#status-budget).
:::

```{figure} ../img/web-ui-budget.png
:class: bb-screenshot
:alt: The power card of a bay: 19.85 V, 0.249 A, 4.96 W, and the line "Granted by the hub 5.4 W · using 5.0 W · 1 port waiting for power"

The power card of a simulated v1.0 bay with a DATA ×4: three ports on, the fourth waiting for room in the
hub's 5.4 W.
```

## Who decides how much

| Limit | Set by | On the default rack | Over it |
|---|---|---|---|
| What the rows draw together | the hub, from the contract less 10 % | 90 W on the 100 W charger | a whole row goes off |
| What a bay's DATA lead draws | the hub's grant, sent every second | 5.4 W | the bay node sheds a port |
| A port's power-on | the bay node: what the bay draws, plus 0.6 W kept for a start, must fit in the grant | the bay under 4.8 W | the power-on waits, or is refused |

The grant is power on the DATA lead, at VRACK: the DATA board's own draw and every board on its ports come out of
it. The node measures it on the lead, so a board that draws less than its port allows leaves room for the others.

## What 5.4 W per bay buys

The hub gives each bay an equal share of its row's eFuse, less the margin, at the contract's voltage, less
what the node draws itself. On the default rack, four bays a row on a 100 W charger:

1.6 A × 90 % × 20 V ÷ 4 = 7.2 W a bay, less 1.8 W for the node: **5.4 W** on the DATA lead.

A bay with a camera gets 2.5 W less, **2.9 W**. A DATA ×4 takes 2.3 to 3.0 W of it itself, its hub, its
co-processor and its pin matrix, so its four ports share what is left:

- one port at its full 500 mA, only with the board at its typical draw;
- four ports at about 105 mA each, with the board at its worst (about 135 mA at typical);
- in a bay with a camera, a port goes on only with the board near its typical draw, at 110 mA or less.

A DATA ×6 takes 2.1 to 2.6 W for itself. None of these figures has been measured: they are worked out from
estimates of the boards' draw in [One node, several boards](../multi-dut-node.md#power-budget) and
[Power](../power.md#budget). Fewer columns give each bay more:

```{include} ../reference/specifications.md
:start-after: <!-- site:bay-share -->
:end-before: <!-- /site:bay-share -->
```

The hub takes the smaller of this share and the contract's 90 W divided among the bays of the rows that are on.
With three rows of four the row's share is the smaller; four rows of four, or a 3 A cable, turn it round
([Specifications](../reference/specifications.md#a-bays-share-by-number-of-columns)).

A node that has heard no grant for 3 s, with no hub or an older one, keeps to a limit of its own, 25 W: then
all four ports of a DATA ×4 run at 500 mA.

## A port that waits, a port that is queued

A port that finds no room goes into one of three states, named on the bay's page:

| The page | What happened | When it goes on |
|---|---|---|
| "Waiting for power" | it is wanted on: at the node's start, every port is, and they go on one at a time, 300 ms apart, as long as there is room | by itself, in turn, once there is room |
| "Shed for power · back once there is room" | it was on, and the bay went over its grant | by itself, once there is room for what it drew |
| "Queued · on as soon as the bay has room" | someone asked for it with "as soon as possible" | by itself, in turn with the waiting ports |

A plain power-on that finds no room is refused, not queued: 409,
`no room in the bay's budget: the bay draws <n> mW, <r> mW kept for a start, <l> mW in all (the hub's grant)`.
`bayctl prepare`, which runs before each test of a twister run, sends a plain power-on and does not wait: on a
full DATA ×4 bay it fails here, and the test with it ([Zephyr twister](twister.md)).

The power card counts the waiting ports ("1 port waiting for power") and the sheds since the node started; the
rack's page shows the same count on the bay's tile. Every state:
[States and error messages](../reference/states-and-messages.md#a-ports-states).

## Ask for power as soon as there is room

On the bay's page, tick **As soon as possible** beside a port's **Power on**; a queued port shows **Cancel**.
From a script:

```console
$ python tools/bayctl.py power B3.4 on --when available
B3.4: queued, on as soon as the bay's budget has room
$ python tools/bayctl.py power B3.4 on --wait 60
$ python tools/bayctl.py power B3.4 cancel
```

`--when available` returns at once, with exit code 0. `--wait 60` queues the same way, then blocks until the
port is on; after 60 s it cancels the request, so that the port does not come on later behind the script's
back, and fails. Over HTTP the request is `{"action": "on", "when": "available"}`, answered 202 while the port
waits:

```console
$ curl -s -X POST bay-b3.local/api/ports/4/power -d '{"action":"on","when":"available"}'
$ curl -s -X POST bay-b3.local/api/ports/4/power -d '{"action":"cancel"}'
```

A `cancel` with nothing queued answers 409, `no queued request on this port`; an `off` withdraws the request too.
The node's shell has no queue. Every option: [bayctl](../reference/bayctl.md#power),
[Bay node HTTP API](../reference/node-api.md).

## When a bay is over its share

The node reads its DATA lead every 20 ms. Over the grant for two readings in a row, it switches off the port
switched on last, then one more every 20 ms until the bay fits. A start's surge, shorter than that, is not
shed. Above 1.5 A on the lead the node's meter raises an alert and the last port goes off at once, before the
lead's eFuse, at about 1.76 A, would cut the whole bay.

A shed port stays wanted. It comes back by itself, in turn, once the grant has room for what it drew or the
0.6 W kept for a start, whichever is more.

## When the rack is over the charger's

The hub sums the rows' currents every 250 ms and compares them with its budget: the current the charger grants,
less the 10 % margin. 20 V × 5 A gives 4.5 A, 90 W; the same charger on a 3 A cable, 2.7 A, 54 W.

- Over the budget for 1 s, or over the contract itself for 250 ms, the hub switches off the next row in the shed
  order, D, C, B, then A. It sheds one row at a time, each time waiting to see what the others draw without it.
- The hub passes over a row with no bay on the rack bus and under 100 mA: switching off row D on a three-row rack
  would free nothing.
- A shed row comes back, the last shed first, once the budget has room for the most it drew plus 0.2 A, for
  10 s, and only with a final contract. Shed again within 60 s of coming back, it waits twice as long the next
  time, up to 10 min.
- When the contract is lost (the charger renegotiates, or a PD hard reset), every row goes off at once, not in
  the shed order; they come back 300 ms apart with the next final contract. A hard reset takes VBUS to 0 V for
  about a second: the whole rack restarts.

```{figure} ../img/hub-ui-shed.png
:class: bb-screenshot
:alt: The rack's page with row C shed after the charger renegotiated down to 30 W

The simulated hub after the charger renegotiated down to 30 W: row C is shed until there is room again. Row D,
first in the order, was passed over: it is empty.
```

A shed row's bays lose power as on a switched-off row
([Power-cycle or reset a board](power-and-reset.md#after-a-power-cut-or-a-restart)). The hub logs each shed and
each return, `row C shed: <a> A > <b> A budget` (or `contract`) and `row C back: the budget has room for it
again`; its CTL LED double-blinks, two short flashes a second, while a row is shed; the pill of the rack's page reads `rows shed`.

The hub cannot catch a step faster than its 250 to 500 ms that the charger does not tolerate that long: rows of
bays all jumping to their limit at once. On the 100 W charger that matters only past eight bays at their worst.

## Protect a row, cap a weak charger

Three settings change the hub's side, all saved, and only the hub's shell has them, on its console USB-C: the
page, the HTTP API and `bayctl` cannot set them.

```console
uart:~$ hub shed CDBA
uart:~$ hub budget cap 65
uart:~$ hub budget margin 15
uart:~$ hub budget
```

- `hub shed` sets the order, first shed first: `CDBA` keeps row A, then B, on longest. The default `DCBA` already
  sheds row A last.
- `hub budget cap <W>` is for a charger that advertises more than it delivers: the budget follows the cap
  wherever it is lower than the contract. `hub budget cap off` removes it.
- `hub budget margin` is the share of the contract kept free, 0 to 50 %, 10 by default.

A larger charger buys nothing today: 28 V, which a 140 W charger offers, is locked out in the hub's default
build, so every charger is used at 20 V ([Specifications](../reference/specifications.md#chargers-and-what-each-feeds)).
The thresholds of the shedding are build options of the hub (`CONFIG_HUB_SHED_*`, `CONFIG_HUB_RESTORE_*` in
[its Kconfig](../../firmware/power-hub/Kconfig)). The rule and its reasons: [Power](../power.md#keeping-the-rows-inside-the-contract).
