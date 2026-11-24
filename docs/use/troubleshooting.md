# Troubleshooting

Find what you see in the tables below. Each row gives the likely cause and what to do.

## Where to look

| Where | How to reach it |
|---|---|
| The bay's page: a red banner, the Power card, each port's state | `http://bay-b3.local/` |
| The node's status and its last fault | `curl -s bay-b3.local/api/status`, or `bay status` and `bay fault` in its shell |
| The rack's page: a banner, a word under each bay, the events | `http://rack.local/` |
| The hub's last 32 events, lost when the hub restarts | `python tools/bayctl.py hub events` |
| The refused attempts on a node | `python tools/bayctl.py access show B3`, with the admin key |

## What the lights say

[LEDs, buttons and switches](../reference/leds-and-buttons.md) lists every colour and pattern.

The LED at the front of each bay:

| The bay's LED | What it means | What to do |
|---|---|---|
| {led}`off` Dark | The node has no power, or no firmware | [A bay is missing](#a-bay-is-missing-or-does-not-answer) |
| {led}`red blink` Blinks red | A fault switched the DATA lead off | Read the reason in the banner of the bay's page, fix it, then `bay power on` |
| {led}`white dim` Dim white | The DATA lead is off | Read the reason on the Power card ([No power at a port](#no-power-at-a-port)) |
| {led}`orange blink` Blinks orange | No network | [A node not on Wi-Fi](recover.md#a-node-on-the-rack-bus-but-not-on-wi-fi) |
| {led}`yellow` Yellow | SERVICE is on | Slide SERVICE off ([Front port and classic mode](front-port.md)) |
| {led}`magenta` Magenta | Classic mode: the boards' USB goes to the front port | [Front port and classic mode](front-port.md) |
| {led}`white blink` Blinks white | A claim waits for a press on BOOT | Press BOOT briefly, or wait 60 s |
| {led}`white blink` {led}`blue blink` Flashes white and blue | Someone asked the bay to identify itself, from the rack's page or `bayctl` | Nothing: it stops after 10 s |
| {led}`blue dim` Stays dim blue | No board has enumerated | [USB/IP and flashing](usb-and-flashing.md#if-it-does-not-work) |

The LEDs of the power box:

| On the power box | What it means | What to do |
|---|---|---|
| PD stays {led}`off` dark | The charger made no PD contract | Try another charger |
| PD is lit, but no ON LED | No firmware on the hub, or a contract under 15 V | `hub status` on the hub's console |
| CTL blinks once a second | No PD charger, or the contract is not final yet | Wait a second, then check the charger |
| CTL double-blinks | Rows shed for lack of power | [Power budget and queued ports](power-budget.md) |
| CTL flickers | A claim waits for the hub's BOOT | Press the hub's BOOT, or wait 60 s |
| A FAULT LED is {led}`red` red | The row's eFuse is in current limit, or too hot | [No power at a port](#no-power-at-a-port) |

## Messages on a page

[States and messages](../reference/states-and-messages.md) gives every message in full.

| What you read | What it means | What to do |
|---|---|---|
| `DATA lead off: SCL or SDA held low: DATA lead reversed?` | A 1:1 lead between J7 and the DATA board | Fit a "same direction" lead ([DATA lead](../reference/cables.md#data-lead)) |
| `… a short on the lead (a camera lead in J7?)` | The camera lead is in J7, or the lead is shorted | Move the camera lead to J6, marked CAM |
| `… no DATA board answers` | No DATA board, or the lead is not in its rear socket | [Take a bay apart](service-a-bay.md) |
| `… the DATA board stopped answering` | The lead was pulled | Plug the lead back in while it is off, then `bay power on` |
| `… the eFuse reported a fault` | An overload or a short on the lead or the DATA board | Find and fix it, then `bay power on` |
| `… the node's INA226 does not answer` | The node's meter is dead. The node will not power the lead | [Report a problem](../reference/known-limitations.md#report-a-problem) |
| `Over-current on B3.2` | The board on port 2 drew more than its port gives | **Power on** in the banner ([After an over-current](power-and-reset.md#after-an-over-current)) |
| A port *queued*, *waiting* or *shed*; 409 `no room in the bay's budget` | The bay's share of power is used up | [Power budget and queued ports](power-budget.md) |
| 409 `the port's VBUS is up while it is off` | The board has power from a second USB connector | [A board with two USB connectors](mount-a-board.md#a-board-with-two-usb-connectors) |
| 423 `reserved by …` | Someone else holds the bay or the port | [Reserve a bay](reserve-a-bay.md) |
| 403 `not allowed from this address` or `kicked by an admin` | The access rules, or a kick | [Control who can use the rack](access.md) |
| *Unknown DATA board* in the header | Something answers on the DATA lead, but it is neither DATA board | Check the lead and the board in J7 |
| A bay on the rack's page says *no answer*, *no address* or *newer protocol* | The bay went silent, never confirmed its place, or has newer firmware than the hub | [A bay is missing](#a-bay-is-missing-or-does-not-answer) |
| `Row B: eFuse in current limit (1.6 A)` | Too much current or heat on row B | [No power at a port](#no-power-at-a-port) |
| `Rack bus:` and a state other than error-active | CAN errors on a row cable | [A bay is missing](#a-bay-is-missing-or-does-not-answer) |
| Event `contract lost (PG high)` | The charger renegotiated or reset | Nothing: the rows come back with the next contract |
| Event `20 V asked, VBUS stays at … V` | The charger does not give 20 V | Use another charger ([Chargers](../reference/specifications.md#chargers-and-what-each-feeds)) |
| Event `node B3 did not confirm its address` | B3's node, or the cable into it | [A bay is missing](#a-bay-is-missing-or-does-not-answer) |
| `settings unavailable (-45)` in the boot log | The flash holds another firmware's data | [Erase it once](recover.md#settings-unavailable-45) |
| The camera answers 503 | No camera on J6 | Plug the camera lead into J6 ([Camera](camera.md)) |

## What the rack does

| What happens | What it means | What to do |
|---|---|---|
| A row goes off, and comes back later | The hub shed it to stay within the charger's power | [Power budget and queued ports](power-budget.md) |
| Every row goes off at once | The charger's contract was lost | Wait for it to come back, then check the charger |
| Every board of a bay restarts | The node restarted, its row was cycled, BOOT was held, or the DATA lead had a fault | `bay fault`, and the hub's events |
| A port you switched off is on again, a reservation is gone | The node restarted | [After a power cut or a restart](power-and-reset.md#after-a-power-cut-or-a-restart) |
| `usbip attach` hangs, then times out | The node refuses you: access rules, a kick or a reservation | [USB/IP and flashing](usb-and-flashing.md#if-it-does-not-work) |
| Another machine attached the board you reserved | A reservation of one port does not cover USB/IP | Reserve the whole bay |
| `bay-b3.local` does not resolve | Your machine has no mDNS, or is on another subnet | [Without mDNS](set-up-your-machine.md#without-mdns-or-from-another-subnet) |
| A node loses its network now and then | A mesh, a repeater, or a busy channel | [Wi-Fi for the rack](wifi.md) |
| A board's control requests take seconds | The board's own Wi-Fi is on another channel | [Boards that use Wi-Fi](wifi.md#boards-that-use-wi-fi-or-bluetooth-themselves) |
| A wire passes nothing | Its port is off | [Wires between boards](wires.md) |
| A drawer sticks, or comes right out | Its fit, its chain, or a missing stop screw | [If the drawer sticks](../build/first-bay.md#if-the-drawer-sticks) |
| The rack tips forwards when a top drawer is out | It is not screwed to the bench | [Screw the rack to the bench](../build/screw-the-rack-to-the-bench.md) |

## What bayctl and twister print

`bayctl` prints its errors after `bayctl:` and exits with 1.

| What it prints | What it means | What to do |
|---|---|---|
| `warning: hub rack.local: no such host` | The hub has an id, so its name is `rack-<id>.local`. Or your machine has no mDNS | `export BAYCTL_HUB=rack-lab1.local` ([How it finds the rack](set-up-your-machine.md#how-it-finds-the-rack)) |
| `B3: cannot reach http://…` | The node is off the network | [A bay is missing](#a-bay-is-missing-or-does-not-answer) |
| `sudo: a password is required` | The sudo rule for `usbip` is missing | [Set up your machine](set-up-your-machine.md#set-up-usbip-on-linux) |
| `bay B3 holds several boards: say which` | The command acts on one board | Name the port: `B3.2` |
| `set BAYCTL_KEY to the rack's admin key` | An admin command without the key | [The admin key](set-up-your-machine.md#the-lab-file-and-the-admin-key) |
| `not claimed: bayctl access claim B2` | Nobody has claimed this node | [Claim the hub and the nodes](access.md#claim-the-hub-and-the-nodes) |
| `… did not stay: MCUboot went back` | The new firmware failed its trial | [If the new firmware does not stay](update-firmware.md#if-the-new-firmware-does-not-stay) |
| A `warning:` from `hwmap` | A board left out, or in doubt | [Boards that hwmap leaves out](twister.md#boards-that-hwmap-leaves-out) |
| A `bayctl:` line from `prepare` in twister's log | A step of the pre-script failed | [What the pre-script does](twister.md#what-the-pre-script-does-and-when-it-fails) |
| Twister stops the pre-script after 90 s | The node is slow to answer, or the board slow to enumerate | Check the node's network, then the board |

## No power at a port

Power reaches a board in five stages. Check them in this order.

1. The charger. The PD LED on the power box lights with any contract. `hub status` on the hub's console shows the
   contract. A charger that does not give 20 V keeps the rows off
   ([Chargers](../reference/specifications.md#chargers-and-what-each-feeds)).
2. The row. Its green ON LED shows that it has power. A row can be switched off by hand, shed for lack of
   power, or in fault. In fault, its eFuse holds it at 1.6 A: on the rack's page, find the bay that draws more
   than its {term}`grant`. A row with no bays that says "no node answered" is fine.
3. The bay's node. Its power comes through the nodes before it in the row. If its LED is dark with the row on,
   check the jumper into the bay, or the feed of the row's first bay. A 1:1 lead used as a jumper also keeps
   the next node off ([Make the row cables](../build/row-cables.md)).
4. The DATA lead. The node powers it after its checks. If it stays off, the Power card or `bay power` says why.
5. The port. It may be off, latched after an over-current, or waiting for room in the bay's share
   ([Power-cycle or reset a board](power-and-reset.md)).

## A bay is missing or does not answer

The rack's page shows every bay that the hub found on the rack bus, with its IP address once it has one
([The rack's page](rack-page.md)).

### The bay is not on the rack's page

The hub gives the nodes of a row their places one after the other, through the row cables. A node that does
not confirm its place stops the row there. The page says *no address*, and the bays after it are missing.

Look at the first missing bay of the row, and at the jumper into it. After you have taken a tray out, the
likeliest cause is a jumper left unplugged. A dead node, or swapped CANH and CANL wires, also stop the row. A
jumper that put the row's voltage on the CAN wires leaves the whole bus dead until each node's CAN protection
part is replaced.

Once the node's LED is lit, press **Re-enumerate** on the rack's page, or run:

```console
$ python tools/bayctl.py hub enumerate
```

To test a node and its cable with a meter, see
[If a node is missing](../build/check-the-pcbs/rack-bus.md#4-if-a-node-is-missing-from-hub-nodes).

### The bay has no IP address

The bay is on the rack bus but not on Wi-Fi. The hub can still reset its boards and restart it
([A node on the rack bus but not on Wi-Fi](recover.md#a-node-on-the-rack-bus-but-not-on-wi-fi)).

### The bay has an address, but its name does not answer

Open the address that the rack's page shows. If it answers, your machine's mDNS is the problem
([Without mDNS](set-up-your-machine.md#without-mdns-or-from-another-subnet)).

### The bay says no answer or newer protocol

*no answer* means the bay was there but has been silent for 3.5 s. The cause is a power cut, a crash or a
cable. A node that restarts asks for its place again, and comes back by itself.

*newer protocol* means the node's firmware is newer than the hub's: [update the hub](update-firmware.md).

## What to send with a report

If none of this explains it, send:

- the output of `curl -s bay-b3.local/api/status`, and of `bay fault` in the node's shell;
- the output of `python tools/bayctl.py hub events`, before the hub restarts;
- the firmware version of the node and of the hub;
- the DATA board the bay holds, from the badge in its page's header.

Where and how: [Report a problem](../reference/known-limitations.md#report-a-problem).
