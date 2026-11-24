# Access rules and security

Each bay node decides by itself who may use its bay, and out of the box it is open: anyone on the network
may do anything until the node is claimed and its rules are switched on. The power hub has no rules at all:
anyone reads it, and only the holder of the admin key acts on it.

:::{status} simulated
The rules engine is tested on a PC against Python's `hmac`. Claims, signed requests, rules, kicks and
reservations ran on native_sim and against the simulated node and hub. A claim by a press on BOOT was done on
the XIAO ESP32-S3 stand-in. The packet filter that drops refused USB/IP, telnet and AUX connections is built
and has never run. See [What exists today](../plan/status.md#status-access).
:::

Needs: for the `bayctl` lines, a machine set up as on [Set up bayctl and usbip](set-up-your-machine.md); for
a claim, a hand on each node's BOOT button and on the hub's.

## Open until claimed

A node is open (never claimed), claimed with its rules off, or claimed with its rules on. In the first two
states every address may use everything but the admin actions. With the rules on, an address gets the
services its rules give it, out of six:

| Service | Covers |
|---|---|
| status | the page, `/api/status`, reading `/api/aux`, `/metrics` |
| control | power, reset, boot, mode, the camera's settings; taking a reservation |
| console | the web console, the raw (TCP 4000) and RFC 2217 (TCP 4001) ports, the AUX settings and BREAK |
| usbip | USB/IP, TCP 3240 |
| shell | the telnet shell, TCP 23, which can do everything: admin hosts only |
| camera | the camera's pictures, TCP 8081 |

A node holds up to 8 sources, each a short name (1 to 15 letters, digits, `.`, `_` or `-`) with an IPv4
address or a CIDR, plus a row for everyone else, which gets status only unless you say otherwise. An address
gets what every source it matches allows.

USB/IP, telnet, the AUX ports and the camera sit behind Zephyr's packet filter: a refused client's TCP
connection is dropped before USB/IP or the shell sees it, and the AUX and camera ports check again when they
accept it. The web server checks every request and answers 403 with `reason`, `service` and `you`, the
address the node saw; the web console needs a single-use ticket from an address with the console right.
Connections that new rules no longer allow are closed. mDNS and DNS-SD answer everyone.

An open node takes reservations too: [Reserve a bay](reserve-a-bay.md).

## Claim the hub and the nodes with one key

The admin key is 32 bytes, 64 hex digits. Whoever holds a node's key edits its rules, kicks connections,
breaks reservations and updates its firmware, from any address. A claim gives a node or the hub its first key,
and it may bring a key along, so one key serves the whole rack.

1. Make the rack's key and give it to `bayctl`, which reads it from `BAYCTL_KEY` and from nowhere else
   ([where to keep it](set-up-your-machine.md#the-lab-file-and-the-admin-key)):

   ```console
   $ python tools/bayctl.py access keygen
   $ export BAYCTL_KEY=<the 64 hex digits it printed>
   ```

2. Claim the hub, then, while its CTL LED flickers and within 60 s, press its BOOT button with a pin through
   the lid's BOOT hole, or type `hub access claim` on its console USB-C:

   ```console
   $ python tools/bayctl.py hub claim
   ```

3. Claim the nodes. `bayctl` asks each in turn and waits while you press that node's BOOT, briefly, within
   60 s; the node's LED blinks white meanwhile:

   ```console
   $ python tools/bayctl.py access claim A1 A2
   A1: press BOOT on bay A1 (its LED blinks white) within 60 s
   A1: claimed
   A2: press BOOT on bay A2 (its LED blinks white) within 60 s
   A2: claimed
   ```

   With nobody at the rack, it stops on `bayctl: A1: nobody pressed BOOT in time`. Nobody can claim a node or
   the hub from the network alone.

A node's BOOT is reached with a pin through a hole in the drawer's floor and in the board plate, drawer in
([LEDs, buttons and switches](../reference/leds-and-buttons.md)). Held for a second or more it power-cycles
the bay's DATA lead and every board on it; held for ten seconds it forgets the node's key and rules.

Without the network, `bay access claim` on the node's UART pads confirms a pending claim like a press on BOOT;
it is refused over telnet. A node or a hub already claimed answers 409, `already claimed: unlock with the admin
key, or reset the node` (or `the hub`).

After the claim, admin requests are signed: `X-Bay-Auth: <nonce>:<HMAC-SHA256(key, nonce \n method \n path \n
body)>`, with a nonce from `GET /api/access/nonce` that serves once, within 60 s. `bayctl` and both pages sign
for you; the details are on [Bay node HTTP API](../reference/node-api.md). A node takes a new key from
`POST /api/access/key`, signed with the old one; `bayctl` has no command for it, and the hub has no such route.
A lost key: [Recover a node or a hub](recover.md#a-lost-admin-key).

## Write the rules in the lab file and push them

The rules of a rack live in the `access:` section of `config/lab.yaml`, a git-ignored file
([lab.yaml](../reference/lab-yaml.md)):

```{literalinclude} ../../config/lab.example.yaml
:language: yaml
:caption: config/lab.example.yaml
:start-at: "# Who may use the bays"
:end-before: "# The example rack"
```

A bay's own `access:`, under `bays:`, adds sources for that bay only, replaces a source of the same name, and
may set `everyone` or `enabled`:

```{literalinclude} ../../config/lab.example.yaml
:language: yaml
:caption: config/lab.example.yaml, bay B4
:start-at: "  B4:"
:end-before: "  # Overrides"
```

The CI hosts need status, control, console and usbip. `access push` writes the rules to every claimed node,
signed with the key:

```console
$ python tools/bayctl.py access push
A1   updated
A2   unchanged
B2   not claimed: bayctl access claim B2
```

`access push B3 B4` writes to those bays only. It exits with 1 when a node failed or is not claimed, and stops
at the first bay whose rules hold more than 8 sources or a CIDR that is not IPv4. A bay's page and `bayctl`
write the same rules on the node: the next `access push` overwrites what the page saved.

`access show` prints, for one bay, your address and what you may do, whether the node is claimed and its
rules on, the reservation, the connections and the count of refusals; with `BAYCTL_KEY` set, the rules and
the log of refusals too:

```console
$ python tools/bayctl.py access show B3
```

## On the bay's page

The **Access** card says which address the node sees you at, which source that is, and *admin* when the
browser holds the key; under it, the reservation, the connections and the count of refused attempts. On an
open node its button is **Claim this bay…**: the dialog takes the rack's key, or an empty field for a new
one, then counts down the 60 s for the press on BOOT. Once claimed, the browser keeps the key in its local
storage and shows it, to copy into `BAYCTL_KEY`.

```{figure} ../img/web-ui-access.png
:class: bb-screenshot
:alt: The Access card of bay B2 seen by its admin while a CI job holds the bay, with two connections and Kick buttons

Simulated node, the one-board form of the stand-ins. The admin's view while a CI job holds the bay: the
reservation with its note and time left, the job's USB/IP and RFC 2217 connections, each with **Kick**.
```

**Manage access…** opens the rules: one row per source, a tick per service, a row for everyone else, the
**Rules on** switch and **Save**. Below them come the refused connections, the admin key (**Copy key**,
**Forget it here**) and the firmware with **Update…**.

```{figure} ../img/web-ui-access-rules.png
:class: bb-screenshot
:alt: The Manage access dialog: three sources and everyone else, with a tick per service, then the refused connections and the admin key

Simulated node. The sixth column of ticks is the camera: firmware 0.5's page gives it no heading.
```

From an address without the control right the page is read-only: its buttons are greyed, and a banner says
why. **I'm an admin…** and **Unlock…** take the key, which stays in that browser and signs the requests; the
key itself is never sent.

```{figure} ../img/web-ui-access-readonly.png
:class: bb-screenshot
:alt: Bay B2 from 192.168.1.77: a read-only banner, the power buttons greyed, an Unlock button

Simulated node, seen from 192.168.1.77 while another address holds the bay.
```

## See who is connected, kick a connection

The Access card lists who holds the console, USB/IP and the shell. **Kick**, for an admin, closes a connection
and refuses its address that service for 60 s. From the command line, the connection's id comes from
`access show` (`usbip:51234`, `rfc2217`, `web0`):

```console
$ python tools/bayctl.py access kick B3 usbip:51234
B3: kicked usbip:51234
```

A kicked address gets 403, `kicked by an admin: retry in a minute`, over HTTP. Whether a kick ends a USB/IP
session on a node has not been tried. The node keeps its last 16 kinds of refusal (address, service, reason,
count) for the admin view, and counts them all in the metric `bay_access_refused_total`.

In the node's shell, on its UART pads or over telnet, `bay access` prints the key's state, the rules, the
reservations of the bay and of each port, the connections and the refusals. Telnet refuses `bay access off`
(rules off), `bay access reset` (no key, no rules, no reservation) and `bay access claim`, and allows `bay
access on` and `bay access release`. The full list: [Bay node shell](../reference/node-shell.md).

## On the hub, reading is open and actions are signed

Anyone on the network reads the hub's page, `/api/status`, `/api/events`, `/metrics`, `/api/update` and a
nonce. Everything that acts is an admin request signed with the hub's key: switching a row (`/api/row`), the
contract choice (`/api/pd`), the enumeration (`/api/enumerate`), a command to a bay (`/api/node`) and an update.
Unsigned, they answer 403: `admin only: unlock with the hub's admin key`, or `admin only: claim the hub first
(its BOOT button)`.

The pill in the page's header says *unclaimed · claim*, *read-only · unlock*, or *admin* in a browser that
holds the key. The claim dialog counts down the same 60 s, and the event log keeps `claimed: admin key set
(BOOT pressed)`.

```{figure} ../img/hub-ui-claim.png
:class: bb-screenshot
:alt: The Claim this hub dialog, counting down 0:59 and waiting for the BOOT button

Simulated hub, waiting for its BOOT button.
```

The hub's BOOT, pressed briefly, confirms a claim; held for ten seconds it forgets the key. Its shell is on
the console USB-C only, never on telnet, since it switches rows and has no login. The full list of routes:
[Power hub HTTP API](../reference/hub-api.md).

## What this does not protect

The rules keep mistakes and uninvited hosts off the bays of a lab network. Someone on that network who means
harm gets past them:

- There is no TLS on a node or on the hub. Rights go by source address, so a host that spoofs an allowed
  address gets its rights.
- The admin key crosses the network in clear once, when a node or the hub is claimed. Claim on a network you
  trust.
- A refused TCP connection is dropped, not reset: `usbip attach` from a refused host waits for its own
  timeout.
- A reservation of one port does not keep other hosts off that port's USB/IP; a reservation of the whole bay
  does ([Reserve a bay](reserve-a-bay.md#what-it-stops-and-what-it-does-not)).
- `GET /api/update` (the firmware's version and image id) and `GET /api/coproc` (the analyzer image stored on a
  DATA ×4 bay) answer every address, whatever the rules.
- The telnet shell has no login of its own: the shell right gives everything but the three commands telnet
  refuses.
- IPv6 is off on the nodes and the hub: IPv4 only.

Beyond that, keep the rack behind a VPN or a gateway. Every limit of the network side:
[Known issues, and what will not work](../reference/known-limitations.md#by-design-network-and-access);
every port a node and the hub listen on: [Network ports, names, metrics](../reference/network.md).
