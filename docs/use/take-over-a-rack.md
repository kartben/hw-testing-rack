# Take over a rack

Use this page when you start to work with a rack that someone else built. Most of their setup is stored in the
rack, and you can read it back. Three things are not: the admin key, the lab file and the firmware signing key.

The commands on this page use `bayctl`, the rack's command-line tool. Install it first
([Set up your machine](set-up-your-machine.md)).

## Find the rack on the network

From a machine on the rack's network, open `http://rack.local/`. If the builder gave the hub an id, its name is
`rack-<id>.local` instead ([Bays, ports and addresses](names.md#host-names)).

To list the hub and every bay node, whatever their names, look for web servers with mDNS:

```console
$ avahi-browse -rt _http._tcp
```

On macOS, use `dns-sd -B _http._tcp`. The hub is the entry named `rack` or `rack-<id>`. The bays are `bay-a1`,
`bay-a2` and so on ([Network ports and metrics](../reference/network.md)).

If the hub is not `rack.local`, tell `bayctl` its name:

```console
$ export BAYCTL_HUB=rack-lab1.local
```

If nothing answers, check that the Wi-Fi network the rack joined still exists. You can still reach the hub's
shell through its console USB-C port ([Wi-Fi for the rack](wifi.md)).

```{figure} ../img/hub-ui-light.png
:class: bb-screenshot
:alt: The hub's page: the charger's contract, the rack bus, one line per row with a tile per bay, the events
:width: 80%

The rack's page on a simulated hub. Each tile gives a bay's place and address. The pill at the top right says
whether this browser holds the admin key.
```

## Check what the builder set up

| Question | Where to look |
|---|---|
| Does every bay answer, and at which address? | The rack's page: one tile per bay. A bay without an address talks to the hub over the rack bus, but is not on Wi-Fi. |
| Was the rack claimed? | The pill on the rack's page: *unclaimed · claim*, *read-only · unlock*, or *admin* ([Control who can use the rack](access.md)). |
| Do the access rules let you in? | `bayctl access show B3`, below. The rules go by your machine's address. |
| Is a bay reserved or in use? | The `lease:` line of `access show`. `bayctl status B3` gives the address of each port's USB/IP client ([Reserve a bay](reserve-a-bay.md)). |
| Which firmware runs, signed with which key? | The version is at the foot of each bay's page, and in the rack bus card of the rack's page. A *test key* tag in the firmware dialog means MCUboot's public test key ([Update the firmware](update-firmware.md)). |
| Which DATA board is in each bay? | The badge in the header of each bay's page: DATA ×4 or DATA ×6. |
| Which boards have a board target? | `bayctl list` prints each port with its target, or `(no target)` ([Board targets](board-targets.md)). |
| Is the rack screwed to the bench? | Look, before you pull out a drawer of the top row ([Screw the rack to the bench](../build/screw-the-rack-to-the-bench.md)). |

`access show` answers three of these questions for one bay. Here it is on a simulated bay that nobody has
claimed:

```console
$ python tools/bayctl.py access show B3
you 127.0.0.1: all
claimed: no, rules off
lease: none
refused: 0
```

The first line is the address the node sees you at, and what you may do. With the admin key in `BAYCTL_KEY`,
`access show` also prints the rules and the connections it refused.

## Get what the rack does not store

### The admin key

`bayctl` reads the admin key from the `BAYCTL_KEY` environment variable, never from a file. Without the key, you
can use the bays as far as their access rules allow. You cannot switch a row, change the rules, end someone
else's reservation or update the firmware.

Ask the builder for the key. If a browser still shows *admin* on a bay's page, that browser holds it: open
*Manage access* and click **Copy key**. Otherwise, reset the key on each PCB with its BOOT button and claim the
rack again ([Recover a node or the hub](recover.md)).

### The lab file

`config/lab.yaml` holds the access rules and any overrides. Git ignores it, so your checkout has none: ask the
builder for theirs. The board targets are stored in the nodes, and this command writes them out as a lab file:

```console
$ python tools/bayctl.py export lab -o rack-targets.yaml
```

### The signing key

Each PCB boots only firmware signed with the key its bootloader was built with. If the pages show no *test key*
tag, ask the builder for their key file. Without it, the PCBs refuse every image you build, and you must flash
each PCB once over USB ([Recover a node or the hub](recover.md)).
