# Update the firmware

A bay node and the power hub take a new firmware over Wi-Fi: the signed image goes into the PCB's second
flash slot, the PCB restarts into it on trial, and keeps it only once Wi-Fi and the rack bus work again;
otherwise MCUboot puts the previous firmware back.

:::{status} bench
The upload, the test boot, the trial and the rollback are tested on native_sim and against the simulated
node and hub. On the XIAO ESP32-S3 stand-in, on 2026-11-03, `bayctl` sent 1053 KB in 21 to 23 s; the XIAO was
back 58 to 59 s after the start and confirmed itself 6 s later. A build that never passes its health check
was rolled back and running again 143 s after the start. Not run on a bay node or a hub: their larger slots,
the rack bus in the trial and a power cut during the swap are still to check.
[What exists today](../plan/status.md#status-update).
:::

Needs: each PCB flashed once over USB with MCUboot ([Flash the hub and the nodes](../build/flash.md)); the
rack's admin key ([Access rules and security](access.md)); the file `zephyr.signed.bin` of a
`west build --sysbuild` ([Build or download the firmware](../build/get-the-firmware.md)). The node's is
`build-bay/bay-node/zephyr/zephyr.signed.bin`, the hub's `build-hub/power-hub/zephyr/zephyr.signed.bin`.

## In the browser

On a bay's page, as admin: **Manage access…**, then **Update…** beside *Firmware*. On the rack's page:
**Update firmware…** in the *Rack bus* card. Both open the same dialog. Choose `zephyr.signed.bin`: the
page reads its version and its image id before anything is sent, and refuses a file that is not a signed
image or that was built for the other application. **Update** then walks through four steps: *Send*,
*Restart*, *Trial*, *Confirmed*.

```{figure} ../img/hub-ui-update.png
:class: bb-screenshot
:alt: The firmware dialog of the hub: 0.5.0 to 0.6.0 sent, the hub back after a restart, on trial until the rack bus answers

Simulated hub. The image is sent and the hub is back; it stays on trial until the rack bus answers. The bay
page's dialog is the same; no picture of it exists.
```

## With bayctl

With the key in `BAYCTL_KEY`, one node, every node, the hub:

```console
$ python tools/bayctl.py update build-bay/bay-node/zephyr/zephyr.signed.bin B3
$ python tools/bayctl.py update build-bay/bay-node/zephyr/zephyr.signed.bin --all
$ python tools/bayctl.py update build-hub/power-hub/zephyr/zephyr.signed.bin --hub
```

`bayctl` prints the image's id and version and the PCBs it will update, then a line per step for each:
`B3: 0.5.0 -> 0.6.0: sent … KB in … s, restarting`, `B3: back after … s, running 0.6.0`, `on trial, waiting
for` Wi-Fi or the rack bus, and `B3: 0.6.0 confirmed itself`. It waits 420 s at most for each PCB to come back
and confirm (`--timeout`).

`--all` takes every bay node the hub lists, one after the other, never the hub itself. It stops at the first
node whose new firmware does not stay and names the nodes it did not reach, so a firmware that fails on one
node never goes to the next. The hub and the nodes take two commands; which should go first is not known.

Before it sends anything, `bayctl` refuses an image built for another PCB (`this image is for
power-hub/power_hub; B3 runs bay-node/bay_node`) and a PCB whose running firmware is still on trial (`0.6.0 is
on trial: wait until it confirms itself`). Every option: [bayctl](../reference/bayctl.md#update).

## Over HTTP

Three requests, the first signed with the key: `POST /api/update/begin` with the image's size and SHA-256
gives a single-use ticket, valid one minute for that address; `POST /api/update?ticket=…` carries the image;
`GET /api/update` follows the trial. The bodies and the answers: [Bay node HTTP API](../reference/node-api.md)
and [Power hub HTTP API](../reference/hub-api.md). The rack bus cannot carry an update: one from the hub to
every node over CAN is planned, not written.

## What happens during an update

| Step | What happens |
|---|---|
| Begin | Refused while the running firmware is on trial, and on a reserved bay unless forced |
| Upload | Written into slot 1 as it streams in, hashed on the way. Refused at the first bytes if it is not an MCUboot image, at the end if the size, the SHA-256 or the image id differ |
| Test boot | The PCB restarts 1.5 s later. MCUboot checks the signature, swaps the slots and boots the new firmware |
| Trial | The new firmware must get back, for 5 s in a row and within 180 s, what worked before: Wi-Fi, and the rack bus. A 30 s watchdog runs meanwhile |
| Confirmed, or rolled back | It confirms itself and stays; otherwise it restarts unconfirmed and MCUboot swaps the previous firmware back |

The rack bus counts for a node that a hub has addressed before: it must get its address back and hear the
hub. A node on a desk, which never had a hub, needs only Wi-Fi. For the hub, the CAN controller must be
error-active or error-warning with at least one node answering, if one answered before. An image flashed over
USB has no trial: it is confirmed as it is.

The image id is `<application>/<board>`, written into the signed image: `bay-node/bay_node` or
`power-hub/power_hub`. A node refuses the hub's image, and the hub a node's.

A reserved bay refuses the update: `reserved by 192.168.1.41 for 25 min more: force to update anyway`. The
dialog asks whether to go on; `bayctl update` skips the bay, says so and exits with 1, unless `--force` is
given. Only a reservation of the whole bay counts: one of a single port does not stop an update, and the
restart ends it like every other reservation ([Reserve a bay](reserve-a-bay.md)).

A node that restarts cuts its DATA lead until its firmware has checked the lead again: the bay's boards lose
power, their USB/IP sessions end, and every port is switched on again afterwards. The hub holds its rows on
through its own restart, by design; this is to be checked on the first hub. What comes back by itself:
[After a power cut or a restart](power-and-reset.md#after-a-power-cut-or-a-restart). The stored settings,
from the bay's id to the board targets, survive an update:
[What a node and a hub remember](recover.md#what-a-node-and-a-hub-remember-and-how-to-wipe-it).

## If the new firmware does not stay

MCUboot puts the previous firmware back by itself. The dialog ends on *Rolled back*, `GET /api/update` gives
`rolled back` as the last result, and the hub's events keep `update to 0.6.0 rolled back: running 0.5.0`.
`bayctl` stops with `bayctl: B3: 0.6.0 did not stay: MCUboot went back, running 0.5.0` and exits with 1.

```{figure} ../img/hub-ui-rollback.png
:class: bb-screenshot
:alt: The firmware dialog after a rollback: Send and Restart done, Trial and Rolled back in red, running 0.6.0 again

Simulated hub, with made-up version numbers: 0.7.0 came back after the restart, did not confirm itself, and
MCUboot went back to 0.6.0. The text above uses 0.6.0 over 0.5.0, the firmware's version today.
```

The trial waits for what worked when the image arrived, so a node whose Wi-Fi or rack bus was already failing
cannot pass it: mend that first ([Troubleshooting](troubleshooting.md)). A PCB that is not back after 420 s
ends `bayctl` with `not back after 420 s: check it (USB console, or the hub's page)`:
[Recover a node or a hub](recover.md).

## Test key or your own key

MCUboot boots only images signed with the key it was built with. A PCB whose bootloader has MCUboot's public
test key shows a *test key* tag beside its firmware version in the firmware dialog, on the bay's page and on
the rack's page alike; `GET /api/update` gives `"test_key": true`. Anyone can sign an image such a PCB boots,
though sending it still needs the admin key. The images CI builds are signed with the test key.

No tag means a key of the builder's: images you build are then accepted only if you sign them with that same
key (`HWTR_SIGNING_KEY`, [Build or download the firmware](../build/get-the-firmware.md#sign-with-your-own-key)).
Moving from the test key to your own, and a lost key, both take a flash over USB of every PCB:
[A lost signing key](recover.md#a-lost-signing-key).
