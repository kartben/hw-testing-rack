# Before you start

This section takes you from the parcels to a rack on the network. The steps are the same for any size of
rack: build the first bay, then add columns and rows, now or later. For a single bay without a frame, see
[One bay on a desk](one-bay-on-a-desk.md).

Build the firmware and make the row cables while the PCBs are on their way. Before you begin, gather the
[tools and the bench equipment](../plan/shopping-list.md#tools-and-bench-equipment), and read the steps you
cannot undo.

## Steps you cannot undo

| Step | Before you do it |
|---|---|
| [Fitting a heat-set insert]{#insert} ([Fit the inserts and nuts](../print/inserts-and-nuts.md#bosses-that-stay-empty)) | Check that the boss takes an insert. Some stay empty: an insert where a bench screw goes blocks the screw. |
| [Soldering a connector on a DATA board]{#solder} ([Solder the connectors](solder-the-connectors.md)) | Check the face and which way round it goes before the first joint. |
| [Crimping a contact]{#crimp} ([Make the row cables](row-cables.md)) | Make a few practice crimps. To redo a bad crimp, you cut it off with its end of the wire. |
| [Gluing the detent magnets]{#magnets}, if you chose them with `drawer.detent: magnet` ([Fit out a tray](fit-out-a-tray.md#glue-the-detent-magnets-if-you-chose-them)) | The two magnets must attract. Stack them and mark both outer faces before you glue. |
| [Burning the ESP32-S3's one-time fuse]{#fuse} ([Flash the hub and the nodes](flash.md#the-modules-one-time-fuse)) | Burn it last, on a PCB that passed its checklist and goes into the rack. Burn no other fuse. |
| [Running `west flash --erase`]{#erase} ([Flash the hub and the nodes](flash.md#erase-a-module-that-ran-other-firmware)) | It wipes the PCB's saved settings, its Wi-Fi network too. Use it once, on a module that ran other firmware. |
| [Putting a bay node on its tray before it has a Wi-Fi network]{#wifi} ([Fit out a tray](fit-out-a-tray.md)) | Give the node its network first. Once the node is on its standoffs, its UART pads are underneath it. |

You can undo the last one, but it takes a while. Either take the tray out and the node off its standoffs, or
build an image with your network in it and flash it through the PC port on the front of the bay
([Build or download the firmware](get-the-firmware.md#put-your-wi-fi-in-the-nodes-image)).
