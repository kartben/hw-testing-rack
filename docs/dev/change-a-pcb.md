<!-- Contributor documentation, kept in the repository: it is not part of the published site, which is the
     user's manual (docs/STYLE.md). -->

# Change a PCB

Each of the five PCBs is one Python file, `electronics/<pcb>/design.py`: its parts with their MPN, maker and LCSC
number, the nets their pins join, and where each part goes. The KiCad project beside it is generated from that
file. v1.0 of all five is frozen since it went to fabrication on 2026-11-11.

## A PCB is a design.py

| PCB | Folder |
|---|---|
| Power hub | [electronics/power-hub](../../electronics/power-hub) |
| Bay node | [electronics/bay-node](../../electronics/bay-node) |
| Camera pod | [electronics/camera-pod](../../electronics/camera-pod) |
| DATA ×6 | [electronics/data-port-x6](../../electronics/data-port-x6) |
| DATA ×4 | [electronics/data-port-x4](../../electronics/data-port-x4) |

From `design.py`, `electronics/tools/` writes a hierarchical KiCad 10 project, one sheet per functional block,
and builds the matching `.kicad_pcb`: footprints, nets, outline, zones, keep-outs, and mounting holes from
`config/rack.yaml`. It autoroutes the PCB with Freerouting and proves the two views agree with KiCad's own ERC
and DRC (schematic parity). Every part has an `sch=` position on the 0.1" grid and the main paths are real
wires, so the schematics read as drawn ones. A local KiCad 10 opens the generated projects as ordinary projects.

## Rebuild one

`tools/kicad.sh` runs everything in the image `kicad/kicad:10.0-full`, and Freerouting 2.5.0 in
`eclipse-temurin:25-jre`: Docker is the only thing to install. It takes the PCB's folder name, then its options;
an unknown option exits with status 2.

```console
$ tools/kicad.sh bay-node --check --fab
```

| Options | What the run does |
|---|---|
| none | schematic, placed PCB, ERC and DRC: the PCB is rebuilt from `design.py` |
| `--route` | the same, then Freerouting |
| `--route --fab` | the same, then the fabrication files |
| `--ses`, `--ses --fab` | imports the last Freerouting session again, no re-route |
| `--tidy`, `--tidy --fab` | straightens the router's tracks of the PCB as it is, no re-route |
| `--clean`, `--clean --fab` | takes the routed PCB's antennas off: dead ends, doubles, slivers |
| `--rules` | rewrites the PCB's rules, DRC settings and footprint keep-outs from the design, then runs DRC, without touching its copper |
| `--dsn` | placed PCB and `build/<pcb>.dsn`, no routing (for `tools/route_farm.py`) |
| `--check`, `--check --fab` | ERC and a read-only DRC of the PCB as it is, what CI runs; with `--fab`, the fabrication files too |
| `--fab` | the same as `--check --fab` |

`PASSES` sets Freerouting's passes (60 by default). `FR_OPT_THREADS=1` keeps its optimizer on one thread, so the
same board comes out every time; by default it takes every core, faster but not repeatable. The session that
`--ses` imports is in `build/`, which git ignores: it exists only after a `--route` on the same machine.

`--fab` writes, per PCB: `fab/<pcb>-gerbers.zip`, `fab/<pcb>-bom-jlcpcb.csv` and `fab/<pcb>-cpl-jlcpcb.csv` (the
placement, corrected to JLCPCB's footprints), the detailed `<pcb>-bom.csv`, and under `docs/` the schematic as a
PDF and the top, bottom and iso renders; the STEP and GLB models stay uncommitted. It then runs
`tools/keep_unchanged.py` on the PCB's folder, when it finds a Python with Pillow (`PYTHON=` names one).

:::{warning}
With no option, or with `--route`, the generator rebuilds the PCB from `design.py`: every track routed or edited
since is gone. On a hand-edited PCB, and on the five released ones, use the options that work on the PCB as it
is (`--check`, `--fab`, `--rules`, `--tidy`, `--clean`), or move the routed `.kicad_pcb` aside first.
:::

Hand-routing in KiCad is fine: verify and export the result with `--check --fab`, as CI does. The routed DATA ×6
and DATA ×4 are exported this way, without a re-route.

## A released revision is frozen

v1.0 of the five PCBs went to NextPCB on 2026-11-11, from commit `125c4ece`: 5 PCBs and 2 assembled boards of
each. Their Gerbers, BOM and placement file stay as they were sent, so the repository always shows the PCBs on
the bench. [electronics/released.json](../../electronics/released.json) lists each revision sent to a fab, with
the SHA-256 of `fab/<pcb>-gerbers.zip`, `<pcb>-bom.csv` and `fab/<pcb>-cpl-jlcpcb.csv` as sent. This compares
the list with the tree:

```console
$ python tools/released.py
```

`tools/tests/test_released_boards.py` runs it with the other tool tests: a commit that changes a v1.0 PCB's
fabrication files without a new revision fails there. Firmware, documentation,
3D models and renders are not in the list and change freely. What the bench finds on v1.0 is fixed in the next
revision, never in v1.0: [Known issues, and what will not work](../reference/known-limitations.md#known-issues-of-the-v10-pcbs).

## Start a new revision

Any change to a released PCB goes into a new revision, however small: a silkscreen text, a part value, one
track.

1. In the PCB's `design.py`, raise the revision in `Board(…, "1.0")` and in its title block
   (`title_block("… v1.0", …)`), then make the change.
2. Regenerate the PCB, and update the headings of [electronics.md](../electronics.md).
3. Leave the released entry alone. When the new revision is ordered, print its entry and add it to
   `electronics/released.json`:

   ```console
   $ python tools/released.py --record bay-node --date 2026-11-11 \
       --fab NextPCB --pcbs 5 --assembled 2
   ```

   with that order's date, fab and counts.

For step 2, `electronics.md` gives `tools/kicad.sh <pcb> --fab`, with `--route` only if the PCB needs a new
routing. But `--fab` alone checks and exports the PCB file as it is: a change in `design.py`, the revision in
its title block included, reaches the PCB only when the generator rebuilds it, and the rebuild drops the routing
(worked out from `electronics/tools/build_board.py`; nobody has made a second revision yet).

## The layout rules and their tests

Each PCB declares in `design.py` what the generator and its checks hold it to, and the tool tests check every
PCB on every push.

- No antennas: no track end that meets nothing of its net, no via on one layer only, no sliver. Checked by
  `electronics/tools/antennas.py` and `tools/tests/test_antennas.py`; the exceptions still allowed are in
  `electronics/antennas.json`.
- No two pours of different nets, closer than their clearance, at one priority, or the fill can change between
  builds while DRC stays clean. Checked by `electronics/tools/zoneprio.py`, by `--check`, and by
  `tools/tests/test_zone_priorities.py`.
- Each decoupling capacitor within 2 mm of the power pin it serves and 1 mm of a GND via, in the order pin,
  capacitor, via. Declared in `b.pcb["decoupling"]` (exemptions with their reasons in
  `b.pcb["decoupling_order_exempt"]`); checked by `electronics/tools/decoupling.py` and
  `tools/tests/test_decoupling.py`, with the exceptions of `electronics/decoupling.json`.
- Netclass widths, a sensitive line kept three USB track widths off a USB pair, DRC severities, keep-outs where a
  printed part holds the PCB. Declared in `NETCLASSES`, `b.pcb["min_width_except"]`, `b.pcb["severities"]` and
  `b.pcb["keepouts"]`; written into the rules by `electronics/tools/netrules.py` and checked by DRC.
- Power pins connected solid to their pour, and at least two spokes on the bus and the supplies. Declared in
  `power_nets`; written into `<pcb>.kicad_dru` and checked by DRC.
- A 3D model for every footprint, unless it has no body by nature or is listed in `b.pcb["no_model"]`. Checked by
  `build_board.py` on every run; `--check` fails on a missing one.

No drill is under 0.3 mm: the smallest via is 0.5/0.3 mm (`SMALL_VIA` in `electronics/tools/pcbgen.py`). How the
routing flow ties every GND pad to its plane, the stackups and the reasons for each rule:
[electronics.md](../electronics.md). How Freerouting was tuned, and `tools/route_farm.py`, which routes one
placement many ways and keeps the best: [autorouting-benchmark.md](../autorouting-benchmark.md).

## Parts, 3D models, the order panel

Every part that is not a generic passive carries its MPN, maker and LCSC number; generic passives are resolved
to JLCPCB basic parts by `electronics/tools/passives.py` and cached in `electronics/lib/passives.json`. A part
marked `hand_solder=True` in `electronics/tools/catalog.py` stays out of the fab's BOM and placement file.

A part whose 3D model file is missing vanishes from the STEP, the GLB and the renders without an error. Fetch the
LCSC / EasyEDA models into their git-ignored cache before a `--fab`, then list what still has no body:

```console
$ python tools/fetch_pcb_models.py
$ tools/kicad.sh bay-node --fab
$ python tools/pcb_glb.py --check
```

`tools/make_step_models.py` draws a body at the datasheet's size where KiCad has no near package; it needs
FreeCAD's `freecadcmd`.

The DATA ×4 is ordered as a panel of its two assemblies, with and without its logic. `tools/panel.sh` builds
the panel with KiKit 1.8.1 in the KiCad image, after the PCB's own `--fab`, and `--check` compares the panel's
BOM and placement halves with each assembly's files:

```console
$ tools/kicad.sh data-port-x4 --fab
$ tools/panel.sh data-port-x4
$ tools/panel.sh data-port-x4 --check
```

The placement files are corrected for JLCPCB's footprints; another assembler needs KiCad's own position file.
Which files went to the fab, and which options: [Order the PCBs](../plan/order-the-pcbs.md). The PCBs' pages, with
their schematics: [The five PCBs](../reference/pcbs/index.md).
