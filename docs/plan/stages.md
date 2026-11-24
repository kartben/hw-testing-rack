# The build, stage by stage

A rack goes together in nine stages, and the order for the PCBs is placed first: a fab takes weeks, and
everything after the printing waits for its parcel.

:::{status} designed
Worked out from constraints in the sources, each given below with its reason; nobody has walked this order.
A builder who finds a stage wrong sees which reason failed. What has been built and tested so far:
[What exists today](status.md).
:::

## What sets the order

1. Order the PCBs and the drag chain on day one. JLCPCB was quoted at 1.5 to 2 weeks door to door and
   NextPCB at 4 to 5, both on 2026-10-20 ([Cost and time](cost-and-time.md#time-what-is-known)). The chain
   goes with them because the tray is drawn round its outer size, its bend radius and its end pieces, and
   its seller publishes only the inner size.
2. Measure a bought part before you print the parts that hold it. The trays and the chain's printed ends
   wait for the chain in your hands, the camera pod for the camera. The ladders, the plates and the braces
   wait for nothing ([Measure before you print](../print/index.md)).
3. Check a bay node on the bench before it is screwed to its tray. Its test pads are on its bottom face, out
   of reach on the tray's standoffs, the last-resort UART pads under the module included. The tray in turn
   is fitted out on the bench before it slides into the frame: once it is in, no screwdriver reaches the
   screws of the guide lips, 5 mm from the side ladder and 2.6 mm from the drawer's wall.

## The stages

| Stage | In your hands | It waits for |
|---|---|---|
| 1. Decide: [a size, and a kind for each bay](choose-your-rack.md); [what it costs](cost-and-time.md) | A browser: the [3D model](/viewer/) shows the default rack | Nothing |
| 2. Order: [the PCBs](order-the-pcbs.md), then [everything else](shopping-list.md), in one sitting | Your size, written into `config/rack.yaml` | Stage 1: a column more changes the number of PCBs, of cables and of screws |
| 3. [Measure and print](../print/index.md) | A printer and PETG; the drag chain and the camera for the parts that hold them | The frame: nothing. The trays and the camera pod: rule 2 |
| 4. [Inserts and square nuts](../print/inserts-and-nuts.md) | The prints, the heat-set inserts, the square nuts, an insert iron | The prints. An insert goes in while its part lies on the bench, before anything is assembled |
| 5. The PCBs on the bench: [solder the connectors](../build/solder-the-connectors.md), then [check each PCB](../build/check-the-pcbs/index.md), which flashes it at its fourth stage | The PCBs and their loose connectors, the two firmware images, a row cable and a DATA lead that ring out, the bench equipment named below | The fab's parcel. Rule 3 puts it before stage 6 |
| 6. Trays, then the frame: [fit out a tray](../build/fit-out-a-tray.md), [screw the rack to the bench](../build/screw-the-rack-to-the-bench.md), [the frame and the first bay](../build/first-bay.md) | Checked bay nodes and DATA boards, the prints with their inserts, the chain, the leads, the row jumpers | Stage 5, tray by tray. The bench screws go in once the base brace is on; later they take a stubby screwdriver |
| 7. [Power box and row feeds](../build/power-box.md) | The checked and flashed power hub, the charger and its 5 A cable, the feeds | The hub's checklist: without firmware its rows stay off |
| 8. [Switch it on](../build/bring-the-rack-online.md) | An access point set up for the rack, a machine with `bayctl` | Every bay in place and the power box on |
| 9. [The first board](../use/first-session.md) | A board, its plate and pegs, its short USB cable | A rack that answers on the network |

After that the rack is used every day ([What a bay can do](../use/index.md)) or by a CI host
([Zephyr twister](../use/twister.md)).

Several steps of stages 4 to 6 cannot be undone: read [their table](../build/index.md#what-cannot-be-undone)
before stage 4. One bay instead of a rack takes the same stages and fewer pages:
[One bay on a desk](../build/one-bay-on-a-desk.md).

## What it asks of you

The build takes through-hole soldering (the fab leaves one lead socket off every DATA board, and the pin
headers off a DATA ×4: [Solder the connectors](../build/solder-the-connectors.md)), crimping (the row feeds
that JST's ready-made leads do not reach, twelve contacts a feed: [Make the row cables](../build/row-cables.md)),
and a Zephyr workspace that builds two images ([Build or download the firmware](../build/get-the-firmware.md)).

Nobody has powered a v1.0 PCB yet, so whoever orders today inspects each one against its checklist
([Check each PCB](../build/check-the-pcbs/index.md)). That takes a bench supply of 0 to 30 V with a current
limit, a multimeter, a 3.3 V USB-UART adapter with probe clips, a USB-C PD charger and a 47 Ω 10 W resistor,
beside a soldering iron and a crimper; the whole list is under
[Tools and bench equipment](shopping-list.md#tools-and-bench-equipment).

Around it the rack needs:

- a bench you may drive wood screws into, two a column, or an MDF base at least 500 mm deep where you may
  not ([Screw the rack to the bench](../build/screw-the-rack-to-the-bench.md));
- a 2.4 GHz access point whose channel you can fix, since the hub and every bay node are Wi-Fi stations
  ([Wi-Fi in the rack](../use/wifi.md));
- a Linux machine, since a board's USB device is attached with the Linux `usbip` tool
  ([Set up bayctl and usbip](../use/set-up-your-machine.md)).

## What can run while you wait

Stage 5 needs the firmware and the row cables, and neither needs the PCBs or the prints. For the firmware,
set up the workspace, write the node's Wi-Fi settings and build the two images
([Build or download the firmware](../build/get-the-firmware.md)). The row cables' leads and housings arrive
before the PCBs, a meter alone tests a cable, and the node's checklist wants a lead on its row socket from
its third stage on ([Make the row cables](../build/row-cables.md)).

The frame can be printed from the first day, and a bay's page and `bayctl` can be tried against a simulated
node with nothing on the desk ([Try it without hardware](try-it-without-hardware.md)).
