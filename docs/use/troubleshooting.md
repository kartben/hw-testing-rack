# Troubleshooting

Each row below goes from what you see to its likely cause and to the page that holds the cure. *Every row is
worked out from the error paths, LED states and messages in the code of the bay node, the power hub and
`bayctl`, and from the design, as they stood on 2026-11-24; nobody has done it yet.* None comes from a fault
met on a rack: no rack has run yet.

:::{status} simulated
The messages and states quoted here appear on native_sim, on the simulated node and hub, and some on the bench
stand-ins. None has been seen on a v1.0 PCB. [What exists today](../plan/status.md#firmware-feature-by-feature).
:::

## Where the rack tells you things

| Where | What it says | How to reach it |
|---|---|---|
| The bay's page | a red banner (an over-current on a port, `DATA lead off:` and the reason), the Power card, each port's state, the Access card's refusals | `http://bay-b3.local/` |
| A node's status | `last_fault`, the error that last restarted the node; `budget.lead_off`, why the DATA lead is off; each port's `power.state` | `curl -s bay-b3.local/api/status`; in the shell `bay status`, `bay fault`, `bay port` |
| The rack's page | a red banner, a pill in the header, a word under each bay, the events | `http://rack.local/` |
| The hub's events | the last 32, newest first, kept in RAM: a restart of the hub loses them | `python tools/bayctl.py hub events`, `hub events` on its console, `GET /api/events` |
| A node's refusal log | the last 16 kinds of refusal: address, service, reason, count | `python tools/bayctl.py access show B3`, with the admin key |
| Metrics | faults, sheds, waiting ports, refusals, lost nodes, CAN errors | `/metrics` of each node and of the hub ([Network ports, names, metrics](../reference/network.md)) |
| The shells | everything above, and the boot log | a node: its UART pads, or telnet once on Wi-Fi; the hub: its console USB-C only |

## What the lights say

The bay's LED is on the left of its fascia; the power box's LEDs are on its front wall. Every colour and
pattern: [LEDs, buttons and switches](../reference/leds-and-buttons.md).

| What you see | The likely cause | What to do |
|---|---|---|
| The bay's LED is dark | The node has no power, or no firmware | [A bay is missing or does not answer](#a-bay-is-missing-or-does-not-answer) |
| It blinks red | The DATA lead's eFuse is in current limit, or a fault switched the lead off: a short, the eFuse's fault, a DATA board that stopped answering | The reason is in the bay page's banner; once it is mended, `bay power on` ([After an over-current](power-and-reset.md#after-an-over-current)) |
| It is dim white | The DATA lead is off: switched off by hand, or a check failed before it went on | The Power card or `bay power` gives the reason: [No power](#no-power-from-the-charger-to-the-port) |
| It blinks orange, slowly | No network | [Recover a node or a hub](recover.md#a-node-that-is-on-the-rack-bus-but-not-on-wi-fi) |
| It is yellow | SERVICE is on: the front port goes to the node itself | Slide SERVICE off ([Front port and classic mode](front-port.md)) |
| It is magenta | Classic mode: a laptop on the PC port, or `bay mode classic` | [Front port and classic mode](front-port.md) |
| It blinks white | A claim waits for a press on BOOT | Press BOOT briefly, or let the 60 s run out ([Access rules and security](access.md)) |
| It flashes white and blue | The rack's page asked "which one is it?" | Nothing: it stops after 10 s |
| It stays dim blue | No board has enumerated on any port | [USB/IP and flashing](usb-and-flashing.md) |
| PD, on the power box, stays dark | The charger made no PD contract | Try another charger before suspecting the hub ([Power box and charger](../build/power-box.md)) |
| PD on, no ON LED | The rows stay off without firmware, and with a contract under 15 V | `hub status` and `hub pd` on the hub's console |
| CTL blinks once a second | No PD charger, the hub on its console USB-C alone; or the contract is not final yet | Wait a second; then the charger |
| CTL blinks twice a second, a FAULT LED is red | A row's eFuse is in current limit or too hot; the hub leaves the row on and the eFuse holds it at 1.6 A | [No power](#no-power-from-the-charger-to-the-port) |
| CTL double-blinks | Rows shed for lack of power | [Power budget and queued ports](power-budget.md) |
| CTL flickers | A claim waits for the hub's BOOT | [Access rules and security](access.md#on-the-hub-reading-is-open-and-actions-are-signed) |

## Words on a page

The refusals of the node's API and their codes, in full: [States and error messages](../reference/states-and-messages.md).

| What you read | The likely cause | What to do |
|---|---|---|
| `DATA lead off: SCL or SDA held low: DATA lead reversed?` | A 1:1 lead between J7 and the DATA board, where it must be "same direction" | Switch the lead off, change it ([Cables and pinouts](../reference/cables.md#data-lead)) |
| `… a short on the lead (a camera lead in J7?)` | The camera's lead in the DATA socket, J7, or a short on the lead | The camera lead goes in J6, marked CAM |
| `… no DATA board answers: none, or the wrong lead in J7` | No DATA board, the lead not in its rear socket, or the wrong lead | [Take out a tray, a node or a DATA board](service-a-bay.md) |
| `… the DATA board stopped answering` | The lead was pulled, or the board lost | Plug it back with the lead off, then `bay power on` |
| `… the eFuse reported a fault` | An overload or a short on the DATA lead or the DATA board | The lead and the board, then `bay power on` |
| `… the node's INA226 does not answer` | The node's own meter is gone: a DATA lead shorted under power can destroy it, and the node then never powers the lead | [Report a finding](../reference/known-limitations.md#report-a-finding) |
| `Over-current on B3.2: the port's 5 V was switched off.` | The board on port 2 drew more than its port gives | **Power on** in the banner ([After an over-current](power-and-reset.md#after-an-over-current)) |
| A port *Queued*, *waiting* or *shed*; 409 `no room in the bay's budget` | The bay's share of the charger is used | [Power budget and queued ports](power-budget.md) |
| 409 `the port's VBUS is up while it is off` | The board is fed through a second USB connector | [A board with two USB connectors](mount-a-board.md#a-board-with-two-usb-connectors) |
| 423 `reserved by …, N min left` | Another address holds the bay or the port | [Reserve a bay](reserve-a-bay.md) |
| 403 `not allowed from this address`, or `kicked by an admin: retry in a minute` | The access rules, or a kick | [Access rules and security](access.md) |
| The header badge says *Unknown DATA board* | Something answers at the DATA board's first address and is neither board: the node leaves it alone | The lead and the board in J7 |
| A bay on the rack's page says *no answer*, *no address* or *newer protocol* | Silent for 3.5 s; never confirmed its address; a newer rack bus protocol than the hub's | [A bay is missing or does not answer](#a-bay-is-missing-or-does-not-answer) |
| Banner `Row B: eFuse in current limit (1.6 A)` | The row's eFuse reports a fault; the page says 1.6 A whatever the cause, current or heat | [No power](#no-power-from-the-charger-to-the-port) |
| Banner `Rack bus:` and a state other than error-active | CAN errors on a row cable | [A bay is missing or does not answer](#a-bay-is-missing-or-does-not-answer) |
| Event `contract lost (PG high): rows off until it is back` | The charger renegotiated or reset | The rows come back with the next contract, one after the other |
| Event `20 V asked, VBUS stays at … V: the rows stay off` | The charger does not give 20 V | Another charger ([Specifications](../reference/specifications.md#chargers-and-what-each-feeds)) |
| Event `node B3 did not confirm its address: row B stops there` | B3's node, or the cable into it | [A bay is missing or does not answer](#a-bay-is-missing-or-does-not-answer) |
| Event `node B3: no answer to command …` | The hub tried three times, 100 ms apart, and the node never answered | [A bay is missing or does not answer](#a-bay-is-missing-or-does-not-answer) |
| `settings unavailable (-45)` in the boot log | The flash holds another firmware's data where the settings live | [Recover a node or a hub](recover.md#settings-unavailable-45) |
| The camera's address answers 503, `/api/camera` says `"present": false` | No camera answered on J6: its lead in J7, or not plugged | The camera lead goes in J6 ([Camera](camera.md)) |

## What the rack does

| What happens | The likely cause | What to do |
|---|---|---|
| A row goes off, and comes back by itself later | The hub shed it to stay inside the charger's contract | [Power budget and queued ports](power-budget.md) |
| Every row goes off at once | The contract was lost | It comes back by itself with the next one; if not, the charger |
| Every board of a bay restarts at once | BOOT held for a second or more, a restart of the node, a row cycled, or the DATA lead cut by a fault | `bay fault`, and the hub's events |
| A port switched off on purpose is on again, a reservation is gone | The node restarted: an update, a fatal error, its RESET | [After a power cut or a restart](power-and-reset.md#after-a-power-cut-or-a-restart) |
| A port will not switch on, and the board is powered anyway | It has 5 V from a second USB connector | [A board with two USB connectors](mount-a-board.md#a-board-with-two-usb-connectors) |
| `usbip attach` hangs, then times out | The node drops the connection without answering: no usbip right, a kick, or a reservation | [USB/IP and flashing](usb-and-flashing.md#if-it-does-not-work) |
| Another machine attached the board you had reserved | A reservation of one port does not cover USB/IP | Reserve the whole bay ([Reserve a bay](reserve-a-bay.md#what-it-stops-and-what-it-does-not)) |
| `bay-b3.local` does not resolve, and the rack's page shows the bay with an address | Your machine has no mDNS, or is on another subnet | [Without mDNS, or from another subnet](set-up-your-machine.md#without-mdns-or-from-another-subnet) |
| A node loses its network now and then; `bay fault` lists `Link lost, reason N` | A mesh or a repeater, or a busy channel | [Wi-Fi in the rack](wifi.md) |
| A board's control requests take seconds | Its own Wi-Fi is on the other channel, 3 cm from its node | [Wi-Fi in the rack](wifi.md#boards-that-use-bluetooth-or-wi-fi-themselves) |
| A wire passes nothing | Its pins stay open while their port is off | [Wires between boards](wires.md) |
| A drawer sticks, or comes right out | Its fit in the tray, its chain, or the missing stop screw | [If the drawer sticks](../build/first-bay.md#if-the-drawer-sticks) |
| The rack leans forwards when a top drawer is pulled | It is not screwed to the bench | [Screw the rack to the bench](../build/screw-the-rack-to-the-bench.md) |

## What bayctl and twister print

`bayctl` prints its errors on stderr after `bayctl:` and exits with 1; `capture` exits with 3 when its trigger
does not come in time ([bayctl](../reference/bayctl.md#exit-codes)).

| What it prints | The likely cause | What to do |
|---|---|---|
| `warning: hub rack.local: no such host (…)` | The hub has an id, so it is `rack-<id>.local`; or your machine has no mDNS | `export BAYCTL_HUB=rack-lab1.local`, or its address ([How it finds the rack](set-up-your-machine.md#how-it-finds-the-rack)) |
| `B3: cannot reach http://…` | The node is off the network, or its name does not resolve | [A bay is missing or does not answer](#a-bay-is-missing-or-does-not-answer) |
| `sudo: a password is required` | `bayctl` runs `sudo -n usbip`, and the sudo rule is missing | [Set up bayctl and usbip](set-up-your-machine.md#usbip-a-sudo-rule-and-flashing-tools-on-linux) |
| `bay B3 holds several boards: say which (B3.1, …)` | The command acts on one board | Name the port: `B3.2` ([Bays, ports and addresses](names.md)) |
| `set BAYCTL_KEY to the rack's admin key …` | An admin command without the key | [Set up bayctl and usbip](set-up-your-machine.md#the-lab-file-and-the-admin-key) |
| `B2   not claimed: bayctl access claim B2` | `access push` met a node nobody claimed | [Access rules and security](access.md#claim-the-hub-and-the-nodes-with-one-key) |
| `… did not stay: MCUboot went back …` | The new firmware failed its trial | [Update the firmware](update-firmware.md#if-the-new-firmware-does-not-stay) |
| `hwmap`: `no board target`, `connected: false`, `not the board its target was saved for`, `without a probe id` | A port with a device and no target; a board with no console path; a board swapped; two boards with one runner and no probe id | [Boards left out of the map, and why](twister.md#boards-left-out-of-the-map-and-why) |
| A `prepare` line in twister's log | A step of the pre-script failed | [What the pre-script does, and when it fails](twister.md#what-the-pre-script-does-and-when-it-fails) |
| twister stops the pre-script | It ran past twister's 90 s. `prepare` waits 30 s at most for the board to enumerate and 30 s more for its console, and each request to a node may take 15 s | The node's network, then the board ([Zephyr twister](twister.md)) |

## No power, from the charger to the port

Power reaches a board through five stages; look at them in this order.

1. The charger. PD on the power box lights with any PD contract. `hub status` and `hub pd`, on the hub's
   console, give the contract and what the charger offers. A charger that holds 5 V or 9 V, or does not give
   20 V, keeps the rows off. A 3 A cable changes no LED: the contract is then 20 V × 3 A, and the budget is
   smaller ([Specifications](../reference/specifications.md#chargers-and-what-each-feeds)).
2. The row. Its green ON LED is lit when the row has power. A row is off by hand (`hub row B on`; it is
   saved), shed for lack of power, or in fault: the hub leaves a faulty row on and its eFuse holds it at 1.6 A,
   so look for the bay that draws, on the rack's page, where each bay shows what it draws against its grant
   ([Rows and the rack's page](rack-page.md)). Row D, on and with "no node answered", is harmless.
3. The bay's node. It takes its power from the row through the nodes before it, and its buck starts above
   13.5 V. A dark LED with the row on: the jumper into that bay, or the feed in a row's first bay, or a 1:1
   lead, with which the next node stays off ([Make the row cables](../build/row-cables.md)).
4. The DATA lead. The node powers it only after its checks: the reason is in the Power card,
   `budget.lead_off` and `bay power`. The six reasons are in the table above.
5. The port. Off, latched after an over-current, waiting or shed for the bay's share, or refused because
   its VBUS is already up: the tables above, and [Power-cycle or reset a board](power-and-reset.md).

## A bay is missing or does not answer

The rack's page lists every bay that the hub has found on the rack bus, at its place, with its address once
it has one ([Rows and the rack's page](rack-page.md)).

**The bay is not on the rack's page**, nor in `hub nodes`. The hub gives the nodes of a row their places one
after the other, each node passing the turn to the next through the row cable. A node that never confirms its
address stops its row there: the page then says *no address*, the events `node B3 did not confirm its
address: row B stops there`, and every bay after it in the row gets no place. A dead node, or one without
rack-bus firmware, stops its row the same way. So look at the first missing bay of the row, and at the jumper
into it: in a rack in service, the likeliest cause is a jumper left unplugged after a tray was out. A jumper
whose CANH and CANL are swapped or open loses every node after it too; one that put the row's voltage on CAN
leaves the bus dead until each node's CAN protection part is replaced ([Rack bus on CAN](../can.md)). Once
the node's LED is lit, ask for a new enumeration: **Re-enumerate** on the rack's page, `hub enumerate`, or
`python tools/bayctl.py hub enumerate`. The meter checks of a node and its cable are those of stage 4 of
[the rack bus checklist](../build/check-the-pcbs/rack-bus.md#4-if-a-node-is-missing-from-hub-nodes).

**The bay is on the page with no address.** It is on the rack bus and not on Wi-Fi. The hub can still identify
it, reset or power-cycle its boards and restart it:
[Recover a node or a hub](recover.md#a-node-that-is-on-the-rack-bus-but-not-on-wi-fi).

**The bay is on the page with an address, and `bay-b3.local` does not answer.** Open the address the page
shows. If it answers, the name is your machine's mDNS, not the bay:
[Without mDNS, or from another subnet](set-up-your-machine.md#without-mdns-or-from-another-subnet).

A bay that was there and goes silent for 3.5 s is shown lost, *no answer*, dashed on the page, and the events
keep `node B3 (0x13) lost: no STATUS for 3 s`: a power cut, a crash or a cable. A node that restarts asks for
an address again and the hub enumerates the whole rack, well under a second. *newer protocol* means the node
speaks a newer version of the rack bus protocol than the hub's firmware: update the hub ([Update the firmware](update-firmware.md)).

## What to send with a report

When none of this explains it, send:

- the bay's status: `curl -s bay-b3.local/api/status`, and `bay fault` from its shell;
- the hub's events: `python tools/bayctl.py hub events`, before the hub restarts;
- the firmware's version of the node and of the hub, and whether they show *test key*;
- which DATA board the bay holds, from the badge in its page's header.

Where and how: [Report a finding](../reference/known-limitations.md#report-a-finding).
