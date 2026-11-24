# lab.yaml

`config/lab.yaml` holds what one installation knows and its rack cannot say: where the hub is, the address
of a node the hub does not list, overrides of a board target, the access rules. The file is optional and
git-ignored, and `bayctl` reads it at every run.

:::{status} simulated
`bayctl`'s tests read these keys against the simulated node and from the example file alone. No lab file
has described a v1.0 rack. See [What exists today](../plan/status.md#status-bayctl).
:::

Copy [config/lab.example.yaml](../../config/lab.example.yaml) to `config/lab.yaml` to start one.
`--lab FILE`, before the command, or the `BAYCTL_LAB` environment variable names another file
([Set up bayctl and usbip](../use/set-up-your-machine.md#the-lab-file-and-the-admin-key)). Keep in it only
what the nodes cannot know: every board key is an override of what a node reports. An entry also stands in
for a node that does not answer, or for a whole rack when no hub does; it then has to say everything, as
the example does.

## Top-level keys

| Key | Default | Holds |
|---|---|---|
| `domain` | `local` | the suffix of the two default names, `rack.<domain>` and `bay-<id>.<domain>` |
| `hub` | `rack.<domain>` | the power hub, `host` or `host:port`; `false`: no hub. `BAYCTL_HUB` wins over it |
| `http_port` | 80 | the nodes' web and API port |
| `aux_port` | 4000 | the nodes' AUX UART as raw bytes |
| `rfc2217_port` | 4001 | the nodes' AUX UART over RFC 2217 |
| `access` | none | the access rules of every node: see [access](#access) |
| `bays` | none | one entry per bay or per port |

The three ports follow the firmware's build options; change them only for a node built with others, or for
the simulated node.

## Per bay and per port

An entry of `bays:` is named like a bay, `B3`, or like a port of its DATA board, `B3.2`, the port from 1
to 6. On a v1.0 rack every board is on a port: the board's keys go under `B3.2`, and `B3` holds what
belongs to the node. A port's entry inherits its bay's `host` and ports.

| Key | On | Holds |
|---|---|---|
| `host` | bay | the node's name or address |
| `http_port`, `aux_port`, `rfc2217_port` | bay | this node's ports, over the top-level ones |
| `access` | bay | sources added to the rack's rules, for this bay only |
| `platform` | port | the Zephyr board, as twister names it |
| `board` | port | a family of the [board library](board-library.md), whose defaults then apply: for a port whose node gives no target |
| `runner` | port | the west runner |
| `id` | port | the probe id, what `west flash --dev-id` gets. Quote it |
| `console` | port | `usb`, `usb:NN` (the serial port on interface `NN`), `aux` or `none` |
| `serial` | port | the console's path on the host, when the name `bayctl` derives will not do |
| `baud` | port | the console's speed |
| `ci` | port | `false`: the board stays out of twister's map |
| `fixtures` | port | twister fixtures the board provides, added to `bay:` and `node:` |
| `product` | port | twister's `product` string, for a runner that picks its probe by it |
| `role` | port | `analyzer`: the port holds the bay's logic analyzer, never in the map. Only this file says so |
| `pin` | port | `{vid, pid, serial}`: the device a target is pinned to. `export lab` writes it and only `import lab` reads it |

What the keys of a board target mean, and the four consoles: [Board targets](../use/board-targets.md).

`bayctl` stops on an entry it cannot read:

| Entry | Message |
|---|---|
| a port outside 1 to 6 | `a sub-slot is <bay>.<1-6>, a DATA board's port` |
| a `console` that is none of the four | `console must be usb, usb:<interface, 2 hex digits>, aux or none` |
| `console: aux` on a port | `a sub-slot has no AUX UART: its console is the board's own USB` |
| a `role` other than `analyzer` | `role '…': analyzer (or none: a board under test)` |
| `role` on a bay | `` `role` is a sub-slot's: an analyzer watches its neighbours `` |

It only warns, and ignores the keys, when a bay's entry carries board keys while its node reports several
boards (`its platform belong under bays.B3.<port>`), and when a port's entry names a port the node does
not have (`left out`). A node with one board and no DATA board, which only the stand-ins and the simulator
have, takes the port keys on its bay's entry.

## access

```{code-block} yaml
:caption: config/lab.yaml
access:
  everyone: [status]
  sources:
    ci-runners: {cidr: 192.168.1.40/30, allow: [status, control, console, usbip]}
    admin-laptop: {cidr: 192.168.1.23, allow: [all]}
bays:
  B4:
    access:
      sources:
        lab-desk: {cidr: 192.168.1.66, allow: [all]}
```

| Key | Default | Holds |
|---|---|---|
| `enabled` | `true` | `false`: the node's rules are off, and every address may use everything |
| `everyone` | `[status]` | the services of an address that matches no source |
| `sources` | none | a name, then `cidr` and `allow` |

- A service is `status`, `control`, `console`, `usbip`, `shell` or `camera`; `all` stands for the six.
- A source's name is 1 to 15 letters, digits, `.`, `_` or `-`. Its `cidr` is IPv4: `a.b.c.d` or
  `a.b.c.d/n`.
- An address gets what every source it matches allows, plus `everyone`.
- A bay's own `access:` adds sources to the rack's, replaces one of the same name, and may set `everyone`
  or `enabled` for that bay.
- A node holds 8 sources, the bay's own included: `bayctl` refuses a ninth.

`bayctl access push` writes the rules to the nodes, signed with the admin key from `BAYCTL_KEY`. The key
never goes in this file, and the rules are never read back into it. What each service covers and how a
node enforces it: [Access rules and security](../use/access.md).

## Which source wins

For a board, a key of the lab file wins over what the node holds, which wins over the defaults of the
board's family.

| Value | Taken from, in this order |
|---|---|
| the hub's address | `BAYCTL_HUB`; `hub:`; `rack.<domain>` |
| a node's address | `host:` of its bay; the address the hub lists for that place; `bay-<id>.<domain>` |
| the Zephyr board | `platform:`; the node's target; the `platform` of the family that `board:` names, when it has only one |
| the family | `board:`; else the family that lists the Zephyr board, and among several the one whose USB ids the device shows |
| the runner | `runner:`; the node's target; the family's runner for that Zephyr board; the family's default |
| the probe id | `id:`; the node's target |
| the console | `console:`; the node's target; `usb` (on a node with one board, the family's, else `usb`) |
| the console's path | `serial:`; else the name derived from the USB strings of the device on the port |
| the speed | `baud:`; the family's; 115200 |
| in the map or not | `ci:`; the node's switch. An analyzer is never in it |
| twister's product | `product:`; the family's |
| fixtures | `fixtures:` only |

For a node that does not answer, the middle source is missing: the lab file and the family's defaults are
all there is. Where each source is read, and how the console's name is derived:
[bayctl](bayctl.md#where-the-data-comes-from).

## The commented example

The example file was written before the DATA ×6. It says "DATA ×4 port" where a port of either DATA board
is meant. Its bays `A1` to `A4`, `B2` and `B4` hold one board on the node itself: on a v1.0 rack each of
those boards is on a port, `A1.1` for instance, and `console: aux` is refused there. It stops at row B. The
keys and the rules are current.

```{literalinclude} ../../config/lab.example.yaml
:language: yaml
:caption: config/lab.example.yaml
```
