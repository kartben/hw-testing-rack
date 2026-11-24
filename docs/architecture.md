# Architecture

This document was split into the pages of the documentation site; its content now lives there:

* the rack, a bay, a row, the data paths, the power and the configuration file:
  [How it works](plan/index.md);
* the three modes of a bay's USB (USB/IP, classic, SERVICE): [A laptop on the front port](use/front-port.md);
* the access point, the channel, the transmit power and where to put the access point:
  [Wi-Fi in the rack](use/wifi.md);
* the bay node's parts and ratings: [Bay node](reference/pcbs/bay-node.md);
* USB/IP from a Linux machine: [Attach a board's USB over USB/IP and flash it](use/usb-and-flashing.md).

## Radio: the nodes' antennas and the rack's Wi-Fi

The settings that follow from this section are on [Wi-Fi in the rack](use/wifi.md).  The review it rests on
stays here, for the notes and the simulation that cite it.

Each node's ESP32-S3-WROOM-1 has its PCB antenna on the node's rear edge, in the tray under the
drawer, flat and pointing to the back of the bay.  On the node, its keep-out holds on every layer
(the rear 6 mm, ±24 mm).  What is around it, in a closed bay (review of 2026-10-21):

| What | From the antenna | Note |
|---|---|---|
| The drawer floor, the plate | 12.5 / 15–20 mm above | PETG |
| The DUT boards | 25–32 mm above.  In 6 of 8 bays within 4 mm sideways, in 2 straight over it | the closest copper, and often a radio of its own (nRF DK, GIGA R1, UNO R4 WiFi) |
| The camera lead (camera bays) | 30 mm beside its right end, routed as in [Add a camera](build/camera.md) | 18 mm if run straight back from J6 |
| The DATA lead | 50 mm (J7), 55 mm (the chain's fixed end) | USB 2.0 high speed on a twisted pair |
| The DATA ×4 v2 | 117 mm to its hub's 24 MHz crystal, 126 mm to the USB2517I; behind and 60–70 mm above | USB 2.0 only.  Its PLL's 5th harmonic is at 2.400 GHz, just under channel 1 |
| The next node | ≈ 166 mm sideways, ≈ 165 mm up or down | |
