# Bring the rack online

Switch the rack on and check that every bay answers, first on the hub's console, then on your network. Then
claim the rack with your own key and focus the cameras.

## Before you start

- Every bay in place and the power box connected ([Power box and charger](power-box.md)).
- The hub and every node flashed and on your Wi-Fi network: step 4 of
  [the hub's checklist](check-the-pcbs/power-hub.md#4-flash-and-check) and of
  [the node's](check-the-pcbs/bay-node.md#4-flash-and-check).
- One access point for the rack, set to a fixed 2.4 GHz channel, 6 or 11, 20 MHz wide
  ([Wi-Fi for the rack](../use/wifi.md)).
- A terminal on the hub's console USB-C, at 115200 baud.
- A computer on the same network, with `bayctl` ([Set up your machine](../use/set-up-your-machine.md)).

## Check that the hub finds every bay

Plug the charger in. The hub turns the rows on and waits two seconds for their nodes to boot. Then it gives
each node its name. On the hub's console, type:

```console
uart:~$ hub status
uart:~$ hub nodes
uart:~$ hub node A1 identify
```

| Check | Expect |
|---|---|
| `hub status`, `PD:` line | `20.0 V / 5.00 A` with the default charger, no `settling` |
| `hub status`, `row` lines | each row `on`, one node per bay; an unused row has `0 node(s)` |
| `hub status`, `rack bus:` line | one node per bay in your rack, `0 lost` |
| `hub nodes` | one line per bay, from A1, with its IP address |
| `hub node A1 identify` | bay A1's LED blinks for 10 s |

A bay's name is its place: the row letter, then its number along the row. Bays are counted from the one the
feed goes into. The hub gives out the names, so you never type one into a node in a rack
([Bays, ports and addresses](../use/names.md)).

If a node does not answer, the bays after it on the same row are missing too. Check the first missing bay
and the cable into it ([Troubleshooting](../use/troubleshooting.md#a-bay-is-missing-or-does-not-answer)).

## Check the network

| Check | Expect |
|---|---|
| `hub status`, first line | `rack.local` and an address, not `network down` |
| `hub nodes` | an address for each bay, not `0.0.0.0` |
| `http://rack.local/` | the rack's page, every bay at its place |
| `http://bay-a1.local/` and so on | each bay's own page |

```{figure} ../img/hub-ui-light.png
:class: bb-screenshot
:alt: The rack's page: the USB-C PD contract, the rack bus, rows A to D with their bays, the events
:width: 80%

The rack's page, here from a simulated hub with eight bays. Click a bay for its actions.
```

A node with no address is not on Wi-Fi: see [Recover a node or the hub](../use/recover.md). If a name does not
answer but the rack's page shows the bay's address, check mDNS on your network
([Without mDNS, or from another subnet](../use/set-up-your-machine.md#without-mdns-or-from-another-subnet)).

From your computer, `bayctl` now shows the same:

```console
$ python tools/bayctl.py hub
```

## Claim the hub and the nodes

Until you claim them, anyone on the network can use the bays. One key claims the hub and every node. Each
claim waits for a press on a BOOT button, so nobody can claim the rack from the network alone.

1. Make the key and give it to `bayctl`:

   ```console
   $ python tools/bayctl.py access keygen
   $ export BAYCTL_KEY=<the key it printed>
   ```

2. Claim the hub. When its CTL LED flickers, you have 60 s to press BOOT with a pin through the lid.

   ```console
   $ python tools/bayctl.py hub claim
   ```

3. Claim the nodes one row at a time. The example claims row A of a rack four columns wide: list the bays of
   your own row. The LED of each node blinks white in turn, and you have 60 s to press its BOOT button. Pull
   the drawer out to reach it, or push a pin through the hole in the drawer floor and the board plate.

   ```console
   $ python tools/bayctl.py access claim A1 A2 A3 A4
   ```

[Control who can use the rack](../use/access.md) says where to keep the key and how to share the bays.

## Check each bay

| Check | Expect |
|---|---|
| The bay's page | DATA ×6 or DATA ×4 in its header, not "Unknown DATA board" |
| A USB device in one of the bay's ports | it shows on the USB devices card, with its port |
| On Linux, `usbip list -r bay-a1.local` | the same device |
| A bay with a camera: **Snapshot** | a picture of the plate |

If a bay cannot power its DATA board, its page says why.
[What a wrong cable does](../reference/cables.md#what-a-wrong-cable-does) lists the messages that a wrong
cable causes.

## Focus the camera

The camera's lens has no autofocus. Focus it once, by hand, with a board in the bay.

1. Put a board on the plate and close the drawer. If you have no board, use a printed sheet of small text.
2. On the bay's page, in the Camera card, click the **Picture** line and set 1600 × 1200. Set the light to
   **On**, and start **Live view**.
3. Loosen the lock nut on the lens. Turn the lens in small steps, and wait for a new frame each time. Stop
   when the text on the board is sharpest. With several boards, focus on one of middle height.
4. Tighten the nut finger-tight and take a **Snapshot** to check. Set the resolution back to 640 × 480.

If no position gives a sharp picture, the lens may need a shorter holder.

The rack is ready for [a first session with a bay](../use/first-session.md).
