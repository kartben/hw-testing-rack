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
- Five PCBs went to fabrication on 2026-11-11, at v1.0. None is on a bench.
- The firmware builds, and runs in simulation and on stand-in boards.

You can print the frame and order the PCBs today. Nobody has finished a rack. [What exists, line by line](plan/status.md).
:::
::::
::::{div} bb-hero-art
![The rack: three rows of four bays on a base, the drawers of B1, B3 and C2 pulled out](img/viewer/rack.jpg)

[The 3D model of the rack as it is designed today. Not a photograph: no rack has been built.]{.bb-cap}

```{div} bb-actions
[Open the 3D model](/viewer/)
```
::::
:::::

::::{div} bb-figures
[The rack in figures]{.bb-label}

Twelve bays in [four columns and three rows](plan/choose-your-rack.md), [671 × 225 × 619 mm](reference/specifications.md), from about [€1,450 in parts](plan/cost-and-time.md) before VAT, an estimate of October 2026.

[243 printed parts](print/parts-list.md), 4.3 kg of PETG by the bill's estimate, the largest 204 × 239 mm on the bed ([printer, filament, settings](print/printer-and-settings.md)). [Five PCBs to order](plan/order-the-pcbs.md), two of them with connectors to solder. One 100 W USB-C charger feeds the lot, [about 5 W a bay](plan/choose-your-rack.md) at four columns.
::::

::::{div} bb-ways
[Four ways in]{.bb-label}

[Build one](plan/stages.md)
: The build, stage by stage, from the first order to the first board in a bay: what to buy before anything is printed, what to do while the PCBs travel, and what each stage asks of you.

[Use one](use/index.md)
: What a bay does with a board: power and reset, USB over the network, the serial console, wires between boards, a logic analyzer, a camera. For a rack you built, and for one you did not.

[Put it in CI](use/ci-host.md)
: A runner drives the rack with `bayctl`: [Zephyr twister](use/twister.md) gets its hardware map from it, [labgrid and LAVA](use/labgrid-and-lava.md) their exports.

[Try it now, without hardware](plan/try-it-without-hardware.md)
: A simulated bay serves the page and the API of the firmware. From a checkout of the repository:

  ```console
  $ pip install -r tools/requirements.txt
  $ python firmware/bay-node/web/dev_server.py --ports 4
  ```

  Then open `http://localhost:8766`.
::::

:::{div} bb-home-foot
[Why it is built this way](engineering/index.md) · [Licences and credits](engineering/licences-and-credits.md) · [The repository on GitHub](../)
:::
