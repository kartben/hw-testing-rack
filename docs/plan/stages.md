# Stages of the build

A rack goes together in nine stages, whatever its size. Order the PCBs first: they take weeks to arrive, and
most of the build waits for them. [How it works](index.md) shows the parts of a bay that these stages name.

For a single bay without a frame, fed by a USB-C PD trigger module, follow
[One bay on a desk](../build/one-bay-on-a-desk.md) instead. It takes fewer stages.

1. Decide how many bays you want and what each one holds: [Choose your rack's size](choose-your-rack.md).
   Check what it costs: [Cost and time](cost-and-time.md).
2. Order [the PCBs](order-the-pcbs.md) and [everything else](shopping-list.md) on the same day. You need the
   drag chain and the camera early, because you measure them before you print the parts that hold them.
3. [Print the parts](../print/index.md). You can print the frame straight away. The trays
   wait for the drag chain, and the camera pod waits for the camera.
4. Fit the inserts and the square nuts into the printed parts before you assemble anything:
   [Fit the inserts and nuts](../print/inserts-and-nuts.md).
5. [Solder the connectors](../build/solder-the-connectors.md) of the DATA boards, then
   [check each PCB](../build/check-the-pcbs/index.md) on the bench and [flash it](../build/flash.md). Do this
   before a bay node goes into its tray, because its test pads are on its underside.
6. [Fit out each tray](../build/fit-out-a-tray.md) on the bench before it goes into the frame. Once a tray is
   in, a screwdriver cannot reach the screws of its guides. Then build
   [the frame and the first bay](../build/first-bay.md) and [add the other bays](../build/add-a-bay.md).
   [Screw the rack to the bench](../build/screw-the-rack-to-the-bench.md) as you go: each column's two screws
   go in once its base brace is on, before its bottom tray.
7. Fit the power box and the row feeds, the cables from the power box to each row:
   [Power box and charger](../build/power-box.md).
8. Switch the rack on and put it on your network: [Bring the rack online](../build/bring-the-rack-online.md).
9. Put your first board in a bay and use it: [A first session with a bay](../use/first-session.md).

Some steps of stages 4 to 6 cannot be undone, such as soldering a connector or burning a fuse. Read
[Steps you cannot undo](../build/index.md#steps-you-cannot-undo) before you fit the first insert.

## While you wait for the PCBs

None of these needs a PCB:

- Set up the Zephyr workspace and build the two firmware images:
  [Build or download the firmware](../build/get-the-firmware.md).
- Make the row cables and test them with a meter: [Make the row cables](../build/row-cables.md). You need one
  to check the bay nodes.
- Print the frame and put up its base and its ladders. They do not need the trays.
- Try a bay's page and `bayctl` on a simulated bay: [Try it without hardware](try-it-without-hardware.md).

## What you need

You will solder through-hole connectors, crimp contacts and build two Zephyr firmware images.

To check the PCBs you need bench equipment, such as a bench supply of 0 to 30 V with a current limit and a
3.3 V USB-UART adapter. The full list is under
[Tools and bench equipment](shopping-list.md#tools-and-bench-equipment).

Around the rack you need:

- a bench you may drive screws into, two per column, or an MDF base at least 500 mm deep;
- a 2.4 GHz Wi-Fi access point whose channel you can fix, for the hub and every bay node
  ([Wi-Fi for the rack](../use/wifi.md));
- a Linux machine, to attach the boards' USB with `usbip`
  ([Set up your machine](../use/set-up-your-machine.md)).
