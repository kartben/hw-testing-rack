# Take over a rack you did not build

A rack carries most of what its builder knew: the hub lists the bays by place and address, each bay node
holds the targets of its boards, and all of them announce themselves on the network. Three things are not in
the rack and leave with a person: the admin key, the lab file and the key that signs the firmware.

:::{status} simulated
Every command and screen named here exists and is tested against the simulated node and hub. The page is
worked out from them: nobody has taken over a rack yet. See [What exists today](../plan/status.md#status-rack-page).
:::

## Find the rack on the network

From a machine on the rack's network, open `http://rack.local/`. That name holds only while nobody has given
the hub an id; after `hub id lab1` it is `rack-lab1.local` ([Bays, ports and addresses](names.md)). The
hub and every bay node announce their page over DNS-SD, so a browse finds them whatever they are called:

```console
$ avahi-browse -rt _http._tcp
```

On macOS, `dns-sd -B _http._tcp`. The hub is the entry named `rack` or `rack-<id>`; the bays are
`bay-a1`, `bay-a2` and so on. Each record carries the firmware version (`fw`), and a bay's also its place
(`pos`) and its number of ports (`slots`); the full list is on
[Network ports, names, metrics](../reference/network.md).

When nothing answers, check that the Wi-Fi network the rack was set up for still exists. The rack powers its
bays without it and the hub's shell on its console USB-C still answers;
[Wi-Fi in the rack](wifi.md) moves a rack to another network.

```{figure} ../img/hub-ui-light.png
:class: bb-screenshot
:alt: The hub's page: the charger's contract, the rack bus, one line per row with a tile per bay, the events
:width: 80%

Simulated hub, with eight bays where the default rack has twelve. The pill at the top right says whether
this browser holds the admin key; each bay's tile gives its place and its address.
```

## What the builder knew, and where to read it

| The question | Where to look | Page |
|---|---|---|
| What is the hub called? | The browse above. Then `export BAYCTL_HUB=rack-lab1.local`, or `bayctl` keeps looking for `rack.local`. | [Set up bayctl and usbip](set-up-your-machine.md) |
| Which network is it on, and does every bay answer there? | The hub's page gives its own address in its header and one tile per bay, with the bay's place and address. A bay with no address is on the rack bus and not on Wi-Fi. | [Rows and the rack's page](rack-page.md), [Wi-Fi in the rack](wifi.md) |
| Was the rack claimed, and who has the admin key? | The pill on the hub's page: *unclaimed · claim*, *read-only · unlock*, or *admin* in a browser that holds the key. For a bay, the second line of `access show`, below. | [Access rules and security](access.md) |
| Are access rules on, and is your address in them? | The first two lines of `access show`: the address the node sees you at, what it may do, and whether the rules are on. The rules go by source address, and your laptop is not the builder's. | [Access rules and security](access.md) |
| Is a bay still reserved, or attached by someone else's runner? | The `lease:` line of `access show` and the connections under it. `python tools/bayctl.py status B3` ends each port's line with the address of its USB/IP client. | [Reserve a bay](reserve-a-bay.md) |
| Which firmware runs, and signed with which key? | The hub's page, in its Rack bus card, and the foot of each bay's page give the version. A *test key* tag in the firmware dialog (*Update firmware…* on the hub's page), or `"test_key": true` in the `firmware` object of `/api/status`, means MCUboot's public test key; no tag means a key of the builder's. | [Update the firmware](update-firmware.md) |
| Which DATA board is in each bay, and which boards have a target? | The badge in the header of each bay's page: DATA ×4 or DATA ×6. `python tools/bayctl.py list` prints every port with its board target, or `(no target)`. | [Board targets](board-targets.md) |
| Is the rack screwed to the bench? | Look, before you pull a drawer of the top row. | [Screw the rack to the bench](../build/screw-the-rack-to-the-bench.md) |

`access show` answers three of these for one bay. Against the simulated node, which nobody has claimed:

```console
$ python tools/bayctl.py access show B3
you 127.0.0.1: all
claimed: no, rules off
lease: none
refused: 0
```

With the admin key in `BAYCTL_KEY` it also prints the rules and the connections it refused. The rules for
pulling the first drawer are under *Before you touch it* on [What a bay can do](index.md#before-you-touch-it).

## What left with the builder

`bayctl` reads the admin key from the `BAYCTL_KEY` environment variable and never from a file, so the key is
with the builder's other secrets, not in the repository. Without it you can read everything and use the bays
as far as their rules allow, but you cannot switch a row, change the rules, end someone else's reservation
or update the firmware. A browser in which a page still says *admin* holds the key: the bay page's *Manage
access* dialog has **Copy key**. Otherwise the key is forgotten at the PCB, with its BOOT button, and the
rack claimed again: [Recover a node or a hub](recover.md).

The lab file, `config/lab.yaml`, is ignored by git, so a fresh checkout has none. It held overrides and
the list of who may use the bays. The board targets are in the nodes, and one command writes them out
in the lab file's form:

```console
$ python tools/bayctl.py export lab -o rack-targets.yaml
```

What that file holds and what it leaves out: [Board targets](board-targets.md).

The signing key decides which firmware a PCB accepts: it boots only images signed with the key its
bootloader was built with. If the pages show no *test key* tag and you do not have the builder's key file,
every image you build is refused, and the way back is one flash over USB for each PCB
([Recover a node or a hub](recover.md)).
