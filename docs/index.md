---
layout: home
description: BitBunk is a 3D-printed, tilted rack that keeps development boards in sliding drawers, switches and meters each one, and puts its USB, its console, its pins and a camera on the network.
---

# BitBunk

:::::{div} bb-hero
::::{div} bb-hero-text
[A 3D-printed, tilted rack that keeps development boards in sliding drawers, switches and meters each one, and puts its USB, its console, its pins and a camera on the network.]{.bb-lede}

:::{div} bb-now
[What exists today]{.bb-label}

- The printed frame is at v0.2 and has not been built.
- Five PCB designs went to fabrication on 2026-11-11, at v1.0. None is on a bench.
- The firmware builds, and runs in simulation and on stand-in boards.

You can print the frame and order the PCBs today. Nobody has finished a rack. [What exists, line by line](plan/status.md).
:::
::::
::::{div} bb-hero-art
![The rack: three rows of four bays on a base, the drawers of B1, B3 and C2 pulled out, a laptop on the front port of B4](img/viewer/rack.jpg)

[The 3D model of the rack as it is designed today. Not a photograph: no rack has been built.]{.bb-cap}

```{div} bb-actions
[Open the 3D model](/viewer/)
```
::::
:::::

::::{div} bb-figures
Twelve bays in [four columns and three rows](plan/choose-your-rack.md), 671 × 225 × 619 mm, for [about €1,500 in parts](plan/cost-and-time.md) at JLCPCB's prices of October 2026, before VAT.

[243 printed parts](print/parts-list.md), about 4.8 kg of PETG by the slicer's figures, the largest 204 × 239 mm on the bed. Five kinds of PCB, 27 boards for this rack, two kinds with connectors to solder. One 100 W USB-C charger feeds the rack and grants each bay 5.4 W at four columns.
::::

::::{div} bb-ways
[Build one](plan/stages.md)
: Nine stages from the first order to the first board in a bay. The PCBs are ordered first: the fab takes weeks, and everything after the printing waits for its parcel.

[Use one](use/index.md)
: What a bay does with a board: power and reset, USB over the network, the serial console, wires between boards, a logic analyzer, a camera. A rack someone else built starts with [Take over a rack you did not build](use/take-over-a-rack.md).

[Put it in CI](use/ci-host.md)
: `bayctl` writes the hardware map that [Zephyr twister](use/twister.md) reads, and the exports for [labgrid and LAVA](use/labgrid-and-lava.md). No rack has run a CI job yet.

[Try it now, without hardware](plan/try-it-without-hardware.md)
: A simulated bay serves the page and the API of the firmware. From a checkout of the repository:

  ```console
  $ python3 -m venv .venv
  $ . .venv/bin/activate
  $ pip install pyyaml
  $ python firmware/bay-node/web/dev_server.py --ports 4
  ```

  Then open `http://localhost:8766`.
::::

:::{div} bb-home-foot
[Why it is built this way](engineering/index.md) · [Licences and credits](engineering/licences-and-credits.md) · [The repository on GitHub](../)
:::
