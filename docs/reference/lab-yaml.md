# lab.yaml

`config/lab.yaml` holds the settings that `bayctl` cannot get from the rack, such as where the hub is and
who may use the bays. The file is optional. Git ignores it, and `bayctl` reads it each time it runs.

To start one, copy the example file:

```console
$ cp config/lab.example.yaml config/lab.yaml
```

Then delete its `bays:` entries: they describe the example rack. Add only the entries your rack needs, as
[A short lab file](#a-short-lab-file) shows.

To use another file, give `--lab FILE` before the command, or set `BAYCTL_LAB`
([The lab file and the admin key](../use/set-up-your-machine.md#the-lab-file-and-the-admin-key)).

Put in it only what the nodes cannot report: a board key in this file overrides what the node says. An entry
can also stand in for a node that does not answer, or for the whole rack when no hub answers. It must then
give everything `bayctl` needs.

## Top-level keys

| Key | Default | Holds |
|---|---|---|
| `domain` | `local` | the suffix of the default names, `rack.<domain>` and `bay-<id>.<domain>` |
| `hub` | `rack.<domain>` | the power hub, as `host` or `host:port`. `false`: no hub. `BAYCTL_HUB` overrides it |
| `http_port` | 80 | the nodes' web and API port |
| `aux_port` | 4000 | the nodes' AUX UART, raw bytes |
| `rfc2217_port` | 4001 | the nodes' AUX UART over RFC 2217 |
| `access` | none | the [access rules](#access-rules) of every node |
| `bays` | none | one entry per bay or per port |

Change the three ports only for nodes built with other ports, or for the simulated node.

## Bays and ports

Each entry under `bays:` is either a bay, such as `B3`, or a port of the bay's DATA board, such as `B3.2`.
Ports run from 1 to 6. In a rack every board sits on a port, so put a board's keys under its port. The bay's
entry holds the node's keys. A port's entry inherits the bay's `host` and network ports.

| Key | On | Holds |
|---|---|---|
| `host` | bay | the node's name or address |
| `http_port`, `aux_port`, `rfc2217_port` | bay | this node's network ports, in place of the top-level ones |
| `access` | bay | sources added to the rack's rules, for this bay only |
| `platform` | port | the Zephyr board, as twister names it |
| `board` | port | a board family from the [board library](board-library.md), such as `nucleo-64`. Its defaults apply when the node gives no target |
| `runner` | port | the west runner |
| `id` | port | the probe id, passed to `west flash --dev-id`. Put it in quotes |
| `console` | port | `usb`, `usb:NN` (the serial port on USB interface `NN`) or `none` |
| `serial` | port | the console's path on the host, when the name `bayctl` builds will not do |
| `baud` | port | the console's speed |
| `ci` | port | `false` keeps the board out of twister's map |
| `fixtures` | port | twister fixtures the board provides, added to the `bay:` and `node:` fixtures `bayctl` writes itself |
| `product` | port | twister's `product` string, for a runner that picks its probe by it |
| `role` | port | `analyzer`: the port holds the bay's logic analyzer, which never goes in the map. `bayctl` learns this only from this file |
| `pin` | port | `{vid, pid, serial}`: the device a target is pinned to. `export lab` writes it, and only `import lab` reads it |

[Board targets](../use/board-targets.md) explains the keys of a board target.

`bayctl` stops on an entry it cannot read:

| Entry | Message |
|---|---|
| a port outside 1 to 6 | `a sub-slot is <bay>.<1-6>, a DATA board's port` |
| a `console` other than `usb`, `usb:NN`, `aux` or `none` | `console must be usb, usb:<interface, 2 hex digits>, aux or none` |
| `console: aux` on a port | `a sub-slot has no AUX UART: its console is the board's own USB` |
| a `role` other than `analyzer` | `role '…': analyzer (or none: a board under test)` |
| `role` on a bay | `` `role` is a sub-slot's: an analyzer watches its neighbours `` |

In two cases it prints a warning and ignores the keys:

- board keys on a bay's entry when the node reports several boards: `… belong under bays.B3.<port>`;
- a port the node does not have: `… left out`.

## Access rules

`access` says which addresses may use which services of the bay nodes.

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
| `enabled` | `true` | `false` turns the node's rules off: every address may use everything |
| `everyone` | `[status]` | the services an address gets when it matches no source |
| `sources` | none | a name for each source, then its `cidr` and `allow` |

- A service is `status`, `control`, `console`, `usbip`, `shell` or `camera`. `all` stands for the six.
- A source's name is 1 to 15 letters, digits, `.`, `_` or `-`. Its `cidr` is IPv4: `a.b.c.d` or
  `a.b.c.d/n`.
- An address gets what every source it matches allows, plus `everyone`.
- A bay's own `access:` adds sources to the rack's and replaces a source of the same name. It may also set
  `everyone` or `enabled` for that bay.
- A node holds 8 sources, the bay's own included. `bayctl` refuses a ninth.

`bayctl access push` writes the rules to the nodes, signed with the admin key from `BAYCTL_KEY`. The key never
goes in this file, and `bayctl` never copies the rules back into it.
[Control who can use the rack](../use/access.md) says what each service covers.

## Where each value comes from

`bayctl` looks for each value in the order below and takes the first it finds. For a board, this file comes
first, then the node, then the defaults of the board's family.

| Value | Where `bayctl` looks, in order |
|---|---|
| the hub's address | `BAYCTL_HUB`; `hub:`; `rack.<domain>` |
| a node's address | `host:` of its bay; the address the hub lists for that place; `bay-<id>.<domain>` |
| the Zephyr board | `platform:`; the node's target; the `platform` of the family that `board:` names, when it has only one |
| the family | `board:`; else the family that lists the Zephyr board, and among several, the one whose USB ids the device shows |
| the runner | `runner:`; the node's target; the family's runner for that Zephyr board; the family's default |
| the probe id | `id:`; the node's target |
| the console | `console:`; the node's target; `usb` |
| the console's path | `serial:`; else a name made from the USB strings of the device on the port |
| the speed | `baud:`; the family's; 115200 |
| in the map or not | `ci:`; the node's setting. An analyzer is never in it |
| twister's product | `product:`; the family's |
| fixtures | `fixtures:` only |

When a node does not answer, only this file and the family's defaults are left.
[Where the data comes from](bayctl.md#where-the-data-comes-from) explains how `bayctl` names a console.

## A short lab file

This file keeps only what the nodes of a rack cannot report. It names the hub, marks the logic analyzer on
port 3 of bay B3, keeps port 4 out of twister's map and gives bay B4 a fixed address. Add the `access`
section of [Access rules](#access-rules) to it if you use access rules.

```{code-block} yaml
:caption: config/lab.yaml
hub: rack-lab1.local
bays:
  B3.3:
    role: analyzer
  B3.4:
    ci: false
  B4:
    host: 192.168.1.71
```

A board's keys go under its port, such as `B3.3`, even when the bay holds one board. A bay's entry, such as
`B4`, holds only the node's keys: `host`, the network ports and `access`.
