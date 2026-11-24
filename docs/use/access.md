# Control who can use the rack

Out of the box, every bay node is open: anyone on the network may use its bay. To control this, claim the
nodes and the power hub with one admin key. Then write rules that say which addresses may do what.

## What the rules control

Until a node is claimed and its rules are on, every address may use everything except the admin actions. With
the rules on, an address gets only the services its rules give it:

| Service | Covers |
|---|---|
| status | the page, `/api/status`, reading `/api/aux`, `/metrics` |
| control | power, reset, boot, mode, the camera's settings, reservations |
| console | the AUX UART, over raw TCP (port 4000) and RFC 2217 (port 4001) |
| usbip | USB/IP, TCP 3240 |
| shell | the telnet shell, TCP 23, which can do almost everything: admin hosts only |
| camera | the camera's pictures, TCP 8081 |

A rule gives services to a source. A source is a name (1 to 15 letters, digits, `.`, `_` or `-`) and an IPv4
address or range. A node holds up to 8 sources. An address that matches several sources gets the services of
all of them. Every other address gets status only, unless you change it.

A refused request over HTTP gets 403, with the reason. A refused TCP connection is dropped without an answer.

## Claim the hub and the nodes

The admin key is 64 hex digits. Whoever holds it can edit the rules, kick connections, end reservations and
update the firmware, from any address. Each claim waits for you to press a BOOT button, so you must be at the
rack.

1. Make the key and give it to `bayctl`, which reads it from `BAYCTL_KEY`
   ([where to keep it](set-up-your-machine.md#the-lab-file-and-the-admin-key)):

   ```console
   $ python tools/bayctl.py access keygen
   $ export BAYCTL_KEY=<the 64 hex digits it printed>
   ```

2. Claim the hub. Run the command below. While the hub's CTL LED flickers, press its BOOT button within 60 s,
   with a pin through the BOOT hole in the lid.

   ```console
   $ python tools/bayctl.py hub claim
   ```

3. Claim the nodes. Run the command below. When a node's LED blinks white, press its BOOT button briefly
   within 60 s.

   ```console
   $ python tools/bayctl.py access claim A1 A2
   A1: press BOOT on bay A1 (its LED blinks white) within 60 s
   A1: claimed
   A2: press BOOT on bay A2 (its LED blinks white) within 60 s
   A2: claimed
   ```

A node's BOOT button is under the drawer. Reach it with a pin through the holes in the floor of the drawer
and in the board plate ([LEDs, buttons and switches](../reference/leds-and-buttons.md)). Do not hold it down.
Held for a second, it power-cycles the bay's boards. Held for 10 s, it clears the node's key and rules.

`bayctl` and the web pages sign the admin requests with the key for you
([The admin signature](../reference/node-api.md#the-admin-signature)). If you lose the key, see
[A lost admin key](recover.md#a-lost-admin-key).

## Write the rules and push them

Keep the rules in the `access:` section of `config/lab.yaml` ([lab.yaml](../reference/lab-yaml.md)):

```{literalinclude} ../../config/lab.example.yaml
:language: yaml
:caption: config/lab.example.yaml
:start-at: "# Who may use the bays"
:end-before: "# The example rack"
```

Give the CI hosts status, control, console and usbip. A bay's own `access:`, under `bays:`, adds sources for
that bay only:

```{literalinclude} ../../config/lab.example.yaml
:language: yaml
:caption: config/lab.example.yaml, bay B4
:start-at: "  B4:"
:end-before: "  # Overrides"
```

Then send the rules to every claimed node, or to the bays you name:

```console
$ python tools/bayctl.py access push
A1   updated
A2   unchanged
B2   not claimed: bayctl access claim B2
```

`access push` overwrites any rules saved on a bay's page.

`access show` tells you what you may do on a bay, and shows its reservation and its connections. With
`BAYCTL_KEY` set, it also prints the rules and the refused attempts.

```console
$ python tools/bayctl.py access show B3
```

## Manage access from the bay's page

The **Access** card shows the address the node sees you at, and *admin* when the browser holds the key. Below
that are the reservation, the connections and the number of refused attempts.

To claim an open node from its page, press **Claim this bay…** in the card. Paste the rack's key, or leave the
field empty to make a new one. Then press the node's BOOT button within 60 s.

```{figure} ../img/web-ui-access.png
:class: bb-screenshot
:alt: The Access card of bay B2 seen by its admin while a CI job holds the bay, with two connections and Kick buttons

Simulated node. The admin's view while a CI job holds the bay: the reservation, and the job's two connections,
each with **Kick**.
```

**Manage access…** opens the rules: a row per source and a tick per service, with the **Rules on** switch and
**Save**. Below the rules are the refused connections, the admin key with **Copy key**, and the firmware.

```{figure} ../img/web-ui-access-rules.png
:class: bb-screenshot
:alt: The Manage access dialog: three sources and everyone else, with a tick per service, then the refused connections and the admin key

Simulated node. The sixth column of ticks, with no heading, is the camera.
```

From an address without the control service, the page is read-only. To act as admin, press **Unlock…** and
paste the key. The key stays in that browser and signs the requests. It is never sent.

## Kick a connection

As an admin, press **Kick** beside a connection in the Access card. The node closes the connection and
refuses that address the service for 60 s. From the command line, take the connection's id from `access show`:

```console
$ python tools/bayctl.py access kick B3 usbip:51234
B3: kicked usbip:51234
```

## Access to the hub

Anyone on the network can read the hub's page and API. Every action, such as switching a row or updating the
firmware, needs the admin key. The label in the header of the hub's page says *unclaimed*, *read-only* or
*admin*. To clear the hub's key, hold its BOOT button for 10 s ([Power hub HTTP API](../reference/hub-api.md)).

## What the rules do not protect

The rules keep mistakes and uninvited hosts off the bays. They do not stop an attacker on your network:

- There is no TLS. Rights go by source address, so a host that spoofs an allowed address gets its rights.
- The admin key crosses the network in clear once, at the claim. Claim on a network you trust.
- The telnet shell has no login.
- `GET /api/update` and `GET /api/coproc` answer every address.

Keep the rack behind a VPN or a gateway. [Network ports and metrics](../reference/network.md) lists
every port the nodes and the hub listen on.
