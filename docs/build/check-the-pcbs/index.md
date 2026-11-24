# Check the PCBs

Check each PCB on the bench when it arrives, before you screw it to a tray. Each kind of PCB has its own
checklist.

Do it now, while you can reach the test pads. They are on the bottom face of the hub and the node, and on the
rear face of a DATA board. Once a node is on its tray, its pads are underneath it.

## Check them in this order

| Order | PCB | You need |
|---|---|---|
| 1 | [Power hub](power-hub.md) | a USB-C PD charger |
| 2 | [Bay node](bay-node.md) | a bench supply, then the hub |
| 3 | [Camera pod](camera-pod.md) | a working node and an Arducam Mega |
| 4 | [DATA ×6](data-x6.md) | a bench supply and a working node |
| 5 | [DATA ×4](data-x4.md) | a bench supply and a working node |
| 6 | [Rack bus](rack-bus.md) | the hub and two working nodes |

Each checklist uses the PCBs you checked before it. Skip the PCBs your rack does not use. A bay on a desk has
no hub: check its node up to step 4, then its DATA ×4 ([One bay on a desk](../one-bay-on-a-desk.md)).

## The steps of a checklist

| Step | What you do |
|---|---|
| 0. Solder | DATA boards only. They arrive without their through-hole connectors, so you solder those first. |
| 1. Look it over | Compare the PCB with the render on its page. Check the pin-1 mark of every IC, and which way round the electrolytic capacitor, the LEDs and the diodes are. Start with the QFN and SOT-23-6 parts. |
| 2. Measure for shorts | With no power, measure the resistance from GND to each supply pad. A reading that starts low and climbs is a capacitor charging. A steady reading under 10 Ω is a short. Write the readings down. |
| 3. Power it on its own | Power the PCB with nothing plugged into it. Measure each rail on its pad. Each page gives the supply and its current limit. |
| 4. Flash and check, or plug it into a node | Hub and node: flash the firmware, give the PCB your Wi-Fi network, and check it from its shell. Camera pod and DATA boards: plug the PCB into a checked node, and check it from the node's shell. |
| 5. Last checks | Hub: put a load on each row. Node: run it from the hub. DATA ×4 with its logic: check the matrix and the logic analyzer. |
| 6. Burn the fuse | Hub and node only. Burn the ESP32-S3's one-time fuse, on a PCB that goes into the rack. It [cannot be undone](../index.md#fuse). |

Step 4 of the hub and the node needs the firmware: [build or download it](../get-the-firmware.md) first.
[Flash the hub and the nodes](../flash.md) shows how to write it.

## What you need

```{include} ../../plan/shopping-list.md
:start-after: <!-- site:bench-equipment -->
:end-before: <!-- /site:bench-equipment -->
```

You make the row cable and the two-wire lead for the bench supply yourself: see
[Make the row cables](../row-cables.md). The DATA lead and the camera lead are bought. Check every lead with
the meter, as [Ring out every cable](../row-cables.md#ring-out-every-cable) shows, before you plug it into a
PCB.

## Finish one PCB before you power the next

Run the whole checklist on the first PCB of a kind before you power the second. If you also ordered bare
PCBs, keep one at hand. You can compare a doubtful reading with a PCB that has no parts on it.

## If a check fails

Stop at the first thing that does not match: a part the wrong way round, a short, a rail out of its range. Do
not go on to the next step, and leave the other PCBs of that kind in their bags. Then
[report it](../../reference/known-limitations.md#report-a-problem), and say what you changed on the PCB, if
anything.
