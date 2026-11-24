# Update the firmware

You update the bay nodes and the power hub over Wi-Fi. Each PCB restarts and runs the new firmware on trial.
It keeps the new firmware only once Wi-Fi and the rack bus work again. If they do not, the bootloader (MCUboot)
puts the previous firmware back.

You need:

- each PCB flashed once over USB, with MCUboot ([Flash the hub and the nodes](../build/flash.md));
- the rack's admin key ([Control who can use the rack](access.md));
- the `zephyr.signed.bin` file from a `west build --sysbuild`
  ([Build or download the firmware](../build/get-the-firmware.md)). For a node, it is
  `build-bay/bay-node/zephyr/zephyr.signed.bin`. For the hub, it is
  `build-hub/power-hub/zephyr/zephyr.signed.bin`.

## In the browser

For a node, open its bay's page as admin. Open **Manage access…** and press **Update…** beside *Firmware*. For
the hub, press **Update firmware…** in the *Rack bus* card of the rack's page.

Choose `zephyr.signed.bin`. The page checks the file before it sends anything. Press **Update**: the dialog goes
through *Send*, *Restart*, *Trial* and *Confirmed*.

```{figure} ../img/hub-ui-update.png
:class: bb-screenshot
:alt: The firmware dialog of the hub: 0.5.0 to 0.6.0 sent, the hub back after a restart, on trial until the rack bus answers

Simulated hub. The image is sent and the hub is back. It stays on trial until the rack bus answers.
```

## With bayctl

With the key in `BAYCTL_KEY`, update one node, every node, or the hub:

```console
$ python tools/bayctl.py update build-bay/bay-node/zephyr/zephyr.signed.bin B3
$ python tools/bayctl.py update build-bay/bay-node/zephyr/zephyr.signed.bin --all
$ python tools/bayctl.py update build-hub/power-hub/zephyr/zephyr.signed.bin --hub
```

`bayctl` first prints the image's id and version, and the PCBs it will update. Then it prints one line per step
for each PCB:

```text
B3: 0.5.0 -> 0.6.0: sent … KB in … s, restarting
B3: back after … s, running 0.6.0
B3: on trial, waiting for … (… s left)
B3: 0.6.0 confirmed itself (… s)
```

It waits up to 420 s for each PCB to come back and confirm. `--timeout` changes the wait.

`--all` updates every bay node, one after the other, but not the hub. It stops at the first node whose new
firmware does not stay. `bayctl` refuses a node image for the hub and a hub image for a node. It also refuses to
update a PCB whose firmware is still on trial. The [bayctl reference](../reference/bayctl.md#update) lists every
option.

## Over HTTP

An update takes three requests: `POST /api/update/begin`, signed with the key, for a ticket;
`POST /api/update?ticket=…` with the image; and `GET /api/update` to follow the trial
([Bay node HTTP API](../reference/node-api.md#firmware-update),
[Power hub HTTP API](../reference/hub-api.md#firmware-update)).

## What happens during an update

1. The image goes into the PCB's second flash slot.
2. The PCB restarts. MCUboot checks the signature, swaps the slots and boots the new firmware.
3. Within 180 s, the new firmware must have Wi-Fi and the rack bus working for 5 s in a row. A node on a
   desk, without a hub, needs only Wi-Fi.
4. The firmware confirms itself and stays. Otherwise it restarts, and MCUboot puts the previous firmware back.

A bay reserved as a whole refuses the update. The dialog asks whether to go on. `bayctl update` skips the bay
unless you add `--force`. If you go on, the restart ends the reservation.

While a node restarts, its bay's boards lose power and their USB/IP sessions end. The ports come back on
afterwards. The hub keeps its rows on while it restarts. The settings survive an update
([What a node and a hub remember](recover.md#what-a-node-and-a-hub-remember-and-how-to-wipe-it)).

## If the new firmware does not stay

MCUboot puts the previous firmware back by itself. The dialog ends on *Rolled back*, and `bayctl` stops with
`bayctl: B3: 0.6.0 did not stay: MCUboot went back, running 0.5.0`.

```{figure} ../img/hub-ui-rollback.png
:class: bb-screenshot
:alt: The firmware dialog after a rollback: Send and Restart done, Trial and Rolled back in red, running 0.6.0 again

Simulated hub: 0.7.0 came back after the restart, did not confirm itself, and MCUboot went back to 0.6.0.
```

A node whose Wi-Fi or rack bus was already failing cannot pass the trial. Fix that first
([Troubleshooting](troubleshooting.md)). If a PCB is not back after 420 s, see
[Recover a node or the hub](recover.md).

## The test key and your own key

MCUboot boots only images signed with the key it was built with. The images from CI are signed with MCUboot's
public test key. A PCB that runs one shows a *test key* tag beside its firmware version. Anyone can sign an
image for such a PCB, but sending it still takes the admin key.

To use your own key, see [Sign with your own key](../build/get-the-firmware.md#sign-with-your-own-key). To move
from the test key to your own, flash every PCB once over USB, as for
[a lost signing key](recover.md#a-lost-signing-key).
