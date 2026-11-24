# Power budget and queued ports

One USB-C charger feeds the whole rack. The hub gives each bay a share of its power, and a bay node switches a
port on only if it fits in that share.

```{figure} ../img/web-ui-budget.png
:class: bb-screenshot
:width: 440px
:alt: The power card of a bay: 19.85 V, 0.249 A, 4.96 W, and the line "Granted by the hub 5.4 W · using 5.0 W · 1 port waiting for power"

The Power card of a simulated DATA ×4 bay: three ports on, the fourth waiting for room.
```

## Three limits

| Limit | Set by | When it is reached |
|---|---|---|
| What all the rows draw | the hub: the charger's contract less 10 %, so 90 W on a 100 W charger | the hub switches a whole row off |
| What one bay draws | the hub's grant to each node | the node switches a port off |
| A port's power-on | the node: the bay's draw, plus 0.6 W kept for the board's start, must fit in the grant | the power-on waits, or is refused |

The grant covers the DATA board itself and every board on its ports. The node measures what the bay really
draws, so a board that draws little leaves room for the others.

## How much power a bay gets

The hub shares each row's power equally between its bays. From each share it takes away what the node itself
draws, and the camera if the bay has one. So the number of columns you choose sets each bay's grant:

```{include} ../reference/specifications.md
:start-after: <!-- site:bay-share -->
:end-before: <!-- /site:bay-share -->
```

With four rows of four, or with the charger on a 3 A cable, the charger runs out first, and each bay gets less
([Specifications](../reference/specifications.md#a-bays-share-by-number-of-columns)).

The DATA board itself uses part of the grant: about 2.1 to 2.6 W for a DATA ×6, and 2.3 to 3.0 W for a
DATA ×4. In a rack of four columns and up to three rows, that leaves a DATA ×4 bay enough for:

- four boards of about 105 to 135 mA each, or one board at 500 mA;
- with a camera, one board of about 110 mA.

A node that has heard no grant for 3 s keeps its bay under 25 W by itself. This is the case of a bay on a desk,
with no hub.

To choose the number of columns for your boards: [Choose your rack's size](../plan/choose-your-rack.md).

## Ports that wait for power

A port that finds no room shows one of three states on the bay's page. Each goes on by itself once there is
room.

| The page says | Why |
|---|---|
| "Waiting for power" | the node is starting, and switches the ports on one at a time |
| "Shed for power · back once there is room" | it was on, and the bay went over its grant |
| "Queued · on as soon as the bay has room" | someone asked for it "as soon as possible" |

A plain power-on that finds no room is refused with 409, `no room in the bay's budget`. `bayctl prepare` sends
a plain power-on before each test of a twister run, so in a full bay the test fails
([Run twister on the rack](twister.md)).

## Ask for power as soon as there is room

### In the browser

Tick **As soon as possible** beside a port's **Power on**. A queued port shows **Cancel**.

### With bayctl

```console
$ python tools/bayctl.py power B3.4 on --when available
B3.4: queued, on as soon as the bay's budget has room
$ python tools/bayctl.py power B3.4 on --wait 60
$ python tools/bayctl.py power B3.4 cancel
```

`--when available` queues the port and returns at once. `--wait 60` waits until the port is on. After 60 s it
gives up and cancels the request, so the port does not come on later. Every option:
[bayctl](../reference/bayctl.md#power).

### Over HTTP

```console
$ curl -s -X POST bay-b3.local/api/ports/4/power -d '{"action":"on","when":"available"}'
$ curl -s -X POST bay-b3.local/api/ports/4/power -d '{"action":"cancel"}'
```

The node answers 202 while the port waits. The node's shell cannot queue a power-on.

## When a bay draws more than its grant

The node reads its bay's draw every 20 ms. If the bay is over its grant twice in a row, the node switches off
the port that went on last. It switches off one more every 20 ms until the bay fits. A board's start-up surge
is too short to shed a port. Above 1.5 A on the DATA lead, the node switches the last port off at once. A shed
port comes back by itself once there is room for what it drew.

(when-the-rack-is-over-the-chargers)=
## When the rack draws more than the charger gives

The hub checks the total of the rows every 250 ms against its budget: the charger's contract less 10 %. That is
90 W from a 100 W charger, and 54 W from the same charger on a 3 A cable.

- If the rows stay over the budget for 1 s, the hub switches off one row. It sheds the rows in the order D,
  C, B, A, and skips an empty row.
- A shed row comes back by itself once the budget has had room for it for 10 s. A row shed again soon after
  waits longer each time, up to 10 minutes.
- If the charger renegotiates, every row goes off at once and comes back with the new contract. After a PD
  hard reset, the charger's output drops to 0 V for about a second, and the whole rack restarts.

The hub takes 250 to 500 ms to shed a row. A charger that does not tolerate an overload that long can still
cut out when several rows of bays all jump to their limit at once. On a 100 W charger, this matters only with
more than eight bays at their worst.

```{figure} ../img/hub-ui-shed.png
:class: bb-screenshot
:alt: The rack's page with row C shed after the charger renegotiated down to 30 W

A simulated hub after the charger dropped to 30 W: row C is shed. Row D comes first in the order, but it is
empty, so the hub skipped it.
```

While a row is shed, its bays have no power. The pill at the top of [the rack's page](rack-page.md) reads
`rows shed`, and the CTL LED on the power box double-blinks.

## Change the shedding order or the budget

Three settings change how the hub sheds rows. They are in the hub's shell only, and the hub saves them.

```console
uart:~$ hub shed CDBA
uart:~$ hub budget cap 65
uart:~$ hub budget margin 15
```

- `hub shed` sets the order, first shed first. `CDBA` keeps row A on longest, then row B.
- `hub budget cap <W>` is for a charger that cannot deliver what it advertises. `hub budget cap off` removes
  the cap.
- `hub budget margin` sets the share of the contract kept free, from 0 to 50 %, 10 % by default.

A charger larger than 100 W gives no more power, because the hub's default firmware uses every charger at 20 V
([Specifications](../reference/specifications.md#chargers-and-what-each-feeds)). Every setting:
[Power hub shell](../reference/hub-shell.md#settings-only-the-shell-has).
