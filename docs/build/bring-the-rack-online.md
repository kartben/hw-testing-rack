# Bring the rack online

A rack is online when the hub lists every bay at its place and each bay's page answers by the name of that
place: `bay-a1.local` to `bay-c4.local` for the default rack.

:::{status} simulated
The hub finds and names its nodes on a simulated rack, and its page and `bayctl` run against a simulated hub.
The only written procedure is [the checklist for a hub and two nodes](check-the-pcbs/rack-bus.md): what
follows extends it to a full rack, which nobody has powered. No expected value exists for twelve bays: write
down the ones you read. [What exists today](../plan/status.md#status-rack-bus).
:::

Every bay is in place with its jumper, and the power box is in with its feeds
([Power box and charger](power-box.md)). On the bench, the hub and the nodes were flashed, given their Wi-Fi
network at stage 4 of their checklists, and had their module's one-time fuse burnt at the last stage.

Check the access point before twelve nodes look for it: one access point, its 2.4 GHz channel fixed on 6 or
11, 20 MHz wide ([Wi-Fi in the rack](../use/wifi.md)). The first section takes a USB-C cable to the hub's
console and a terminal at 115200 Bd; the rest, a machine on the rack's network with `bayctl`
([Set up bayctl and usbip](../use/set-up-your-machine.md)).

## Rows on, every bay listed by its place

*Worked out from the checklist for a hub and two nodes and from the hub's shell. Nobody has done it on a
full rack.*

With the charger plugged, the hub turns the rows on one after the other. Two seconds after the last one,
when the nodes have booted, it walks each row and gives every node its place. On the hub's console:

```console
uart:~$ hub status
uart:~$ hub nodes
```

| Check | Expect |
|---|---|
| `hub status`, the `PD:` line | 20.0 V / 5.00 A, without the word `settling` |
| `hub status`, the row lines | rows A, B and C `on` with `4 node(s)` each; row D `on` with `0 node(s)`: the default rack leaves it empty |
| `hub status`, the last line | `rack bus:  12 node(s), 0 lost` |
| `hub nodes` | twelve lines, A1 to C4, each with its id, its MAC address, its IP address and its firmware version |
| `hub node C4 identify` | the LED of the top right bay blinks for 10 s; the answer is in `hub events` |
| `hub status`, every bay idle | each row's current: write it down, there is no figure to compare it with |

A bay's name is its place: the row's letter, then its rank along the row cable, counted from the bay the feed
enters. The hub hands the places out again each time a row starts, so nobody types a name into a node of a
rack ([Bays, ports and addresses](../use/names.md)).

A node that takes no address stops its row there: the bays after it are missing too. Look at the first
missing bay and at the cable into it. The checks of the bench are at the end of
[the hub and two nodes](check-the-pcbs/rack-bus.md#4-if-a-node-is-missing-from-hub-nodes); those of an
assembled rack are on [Troubleshooting](../use/troubleshooting.md), under a bay that is missing or does not
answer. Every `hub` command is on [Power hub shell](../reference/hub-shell.md).

## The hub and the nodes on Wi-Fi

| Check | Expect |
|---|---|
| `hub status`, the first line | `rack.local` and the hub's address; `network down` means it has not joined |
| `hub nodes`, the address of each bay | an address of your network; `0.0.0.0` means that node has not joined |
| `http://rack.local/` from your machine | the rack's page: every row, every bay at its place |
| `http://bay-a1.local/` | bay A1's own page; the same for each bay |

```{figure} ../img/hub-ui-light.png
:class: bb-screenshot
:alt: The rack's page: the USB-C PD contract, the rack bus, rows A to D with their bays, the events
:width: 80%

The rack's page, from the simulated hub: eight bays in rows A to C, not the default twelve, and row D on with
nothing on it. Each bay shows its place and its address; a click on one opens its actions.
```

A node without Wi-Fi is still listed by the hub and still obeys it: identify, power and reset go over the row
cable ([Rows and the rack's page](../use/rack-page.md)). It only lacks its own page, its USB/IP and its
console.

The credentials are not typed here. The hub's were typed on its console at stage 4 of
[its checklist](check-the-pcbs/power-hub.md), a node's came with its image or were typed on its pads at stage 4
of [its own](check-the-pcbs/bay-node.md). A hub or a node that has none, or the wrong ones:
[Recover a node or a hub](../use/recover.md). A name that does not resolve while the rack's page shows the
bay with an address is the network's mDNS, not the bay: [Set up bayctl and usbip](../use/set-up-your-machine.md).

From here on, `bayctl` shows the same from your machine:

```console
$ python tools/bayctl.py hub
```

## Take ownership

Until it is claimed, a node serves anyone on the network: its page says "Open: anyone on this network can use
this bay." An unclaimed hub shows its page to anyone and switches nothing from the network. One key claims
them all, and each claim is confirmed by a press on a BOOT button: nobody claims a rack from the network
alone.

1. Make the key and give it to `bayctl`:

   ```console
   $ python tools/bayctl.py access keygen
   $ export BAYCTL_KEY=<the key it printed>
   ```

2. Claim the hub. Its CTL LED flickers: within 60 s, press BOOT with a pin through the lid's hole, or type
   `hub access claim` on its console.

   ```console
   $ python tools/bayctl.py hub claim
   ```

3. Claim the nodes, a row at a time. `bayctl` asks each node in turn; its LED blinks white, and you have 60 s
   to press its BOOT button, on the node's top face: clear with the drawer pulled out, or reached with a pin
   through the hole in the drawer floor and the board plate.

   ```console
   $ python tools/bayctl.py access claim A1 A2 A3 A4
   ```

Where the key is kept, who may then use which bay, and what all this does not protect against:
[Access rules and security](../use/access.md). Where each button is:
[LEDs, buttons and switches](../reference/leds-and-buttons.md).

## One check per bay

| Check | Expect |
|---|---|
| The bay's page, `http://bay-a1.local/` | the badge in its header says DATA ×6 or DATA ×4; a red "Unknown DATA board" means the node did not recognise the board on its DATA lead |
| A USB device in one of the bay's ports: a memory stick, a development board | it shows on the page's USB devices card with the port it is in |
| On a Linux machine, `usbip list -r bay-a1.local` | the same device, ready to attach |
| A bay with a camera, its page's Camera card, **Snapshot** | a picture of the plate |

A bay that cannot power its DATA board says why on its page. The messages, and the wrong lead behind each, are
in [What a wrong cable does](../reference/cables.md#what-a-wrong-cable-does).

### Focus the camera

The camera's M12 lens has no autofocus: it is focused once, by hand, at the real distance (lens tip to board
≈ 75 to 80 mm). No lens has been focused in a bay yet: the figures are the design's.

1. Pod mounted, drawer in, a board on the plate (or a printed target: small text, a ruler) at its working
   height.
2. Bay page › Camera: resolution 1600 × 1200 (the Picture button), light on, **Live view**. Each frame takes
   about half a second.
3. Loosen the lock nut on the lens barrel and turn the lens in small steps, waiting a frame each time, until
   the silkscreen text is sharpest. Take a **Snapshot** and zoom in the browser to judge. Boards stand 36 to
   42 mm high: focus on a board of middle height and the others stay sharp enough.
4. Hold the lens still and tighten the nut finger-tight; check with one more snapshot, then set the resolution
   back (640 × 480 for the stream).

Found a step that is wrong? [Report a finding](../reference/known-limitations.md#report-a-finding).

The rack is ready for [a first session with a bay](../use/first-session.md).
