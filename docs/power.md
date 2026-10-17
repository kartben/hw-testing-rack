# Power

**Goal:** "something I can just plug in."  The printed panel frame has no closed
base for a mains supply, so the rack's power lives in a **power box**: a
printed box in the base cell under A1, standing on the floor plate.  Inside it:

* a **certified 24 V desktop brick**, Mean Well GST60A24 (60 W), unmodified.
  Its IEC C14 inlet looks out of a window in the box's rear wall, so the only
  mains part in the rack is the brick's own closed case: one standard C13 cord
  plugs into it;
* the **power hub v0.4**: an eFuse per row, plus the rack controller (an
  ESP32-S3, CAN master; see [can.md](can.md)).  Its layout is still in progress;
  the box is drawn around the outline and connector positions in
  `config/rack.yaml` › `pcb.power_hub`.

One 6-pin JST PH feed per row (24 V, CAN, POS) runs from the box's left wall to
the row's first node.  Box, cradle and lid: [mechanical.md](mechanical.md#power-box).

![The power box under A1: the brick in its cradle, the hub, the row feeds up the rack's left side](img/power-box.jpg)

*Left: under A1, its row feeds climbing the rack's left side.  Right: lid off, the GST60A24 in its cradle; the hub is a stand-in until its v0.4 layout exists.*

## Budget

| | per bay | 12 bays |
|---|---|---|
| node (ESP32-S3 with Wi-Fi on for USB/IP, LED, buck + LDO losses) | ≈ 0.7–1 W | ≈ 10 W |
| typical dev board (Nucleo, nRF DK, FRDM, Pico, C6 …) | ≈ 0.2–0.7 W | ≈ 6 W |
| big board (F746G-DISCO with its LCD, ESP32-S3 on Wi-Fi) | ≈ 1.5–2.5 W | — |
| camera pod (XIAO streaming) | ≈ 1–1.5 W | 2 pods ≈ 2.5 W |
| **realistic, whole rack** | | **≈ 20–30 W** |
| **worst case** (every DUT at its 1.5 A switch limit) | ≈ 11 W at 24 V | ≈ 132 W |

Wi-Fi transmit peaks last milliseconds and don't line up; the bulk capacitors
take them.  The **GST60A24** (60 W, 2.5 A) gives 2–3× the realistic draw.  A
single fault can't overload it: a shorted row sits at its eFuse limit
(1.6 A) while the others draw ≈ 0.4 A each, ≈ 2.4 A in all.  Only many boards
at their own limits at once would exceed 60 W: the brick then folds back, every
row restarts, and the rack controller can shed a row on its current reading
before that happens.  The box's bay takes a **GST90A24** (90 W, 145 × 60 mm)
too, for a fourth row or hungry EVKs: print its cradle, nothing else changes.

Each row has its own eFuse, set to **1.6 A**: rows are wired with JST PH (2 A
per contact), so the limit protects the connectors and the 24 AWG cables.
Four DUTs at their own 1.5 A limit at the same time would trip it (it retries
on its own).

## Options compared

| Architecture | Cords | Max power | Cost | Verdict |
|---|---|---|---|---|
| Internal AC-DC (UHP-200-24) + C14 inlet | 1 standard C13 cord | 201 W | ≈ €80–95 power path | variant: needs a mains enclosure; 194 mm long, it doesn't fit the box under A1 |
| **Certified 24 V brick inside the power box (GST60A24, or GST90A24)** | 1 standard C13 cord | 60 / 90 W | ≈ €30 | **chosen**: no mains wiring anywhere in the rack |
| USB-C PD 3.1 EPR (28 V / 5 A) | 1 laptop charger | 140 W | ≈ €5 sink parts + charger + 5 A e-marked cable | 1–3 rows, or whole rack with power budgeting |
| PoE++ per row (802.3bt) | 4 Ethernet + PoE++ switch | 51–71 W per row | ≈ €100 modules + switch | not worth it with Wi-Fi nodes |

### Why the Mean Well UHP-200-24

* **PFC** (PF ≥ 0.94): EN 61000-3-2 harmonic limits apply above 75 W; Mean Well
  itself excludes the cheaper LRS-200 for that case.
* **Universal input, no 115/230 V selector** (a wrong LRS switch position kills it).
* **Fanless at full load up to 50 °C**, 94 % efficient, slim (194 × 55 × 26 mm).
* ≈ €48–54 at TME/RS/Mouser.

### Bus voltage: 24 V

At 24 V a row draws ≤ 1.9 A and three rows ≤ 5.7 A: the hub input is a
JST VH (10 A) on 16 AWG, the rows JST PH (2 A, eFuse-limited to 1.6 A) on
24 AWG, and every bay's 24→5 V buck runs at ~21 % duty.  One connector family
for everything inside the shelf (PH), VH only where the whole rack's current
comes in, no screw terminals.
12 V would double the currents and exclude 28 V PD; 48 V would need 100 V
converters.  The bay nodes accept **9–30 V** with 60 V-rated silicon, so the
same boards also run from 20 V / 28 V USB-PD or 24 V PoE modules.

## Protection chain

```
mains → C13 cord → GST60A24 (certified, in the power box) → DC cord cut to ≈ 25 cm → hub:
  JST VH → SUD50P06 P-FET (reverse polarity) → SMCJ33A TVS → bulk caps
  → 4 × TPS26600 eFuse (rows A–D, 1.6 A limit, 4 ms soft start, UV 15 V / OV 33 V, auto-retry)
  → 6-pin JST PH → row daisy chain → each bay node:
     SUD50P06 P-FET → SMBJ33A TVS → 100 µF → LMR51635 (60 V, on above 13.5 V) → 5 V
     → TPS2553 → 50 mΩ shunt (INA226) → DUT
```

* Hot-plugging a bay node into a live 24 V bus rings up to ~2× the bus on
  ceramic caps: the bay buck is a **60 V** LMR51635 (not a 36 V part) and the
  TVS clamps below 54 V; the electrolytic damps the ringing.
* The hub eFuses soft-start each row, so plugging a row never browns out the
  others, and a shorted bay only trips its own row.

## Safety (DIY mains, internal-supply variant only)

* **Protective earth:** inlet PE → PSU FG terminal (green/yellow ≥ 1.0 mm²)
  and any exposed metal of the box.  Check ≤ 0.1 Ω PE-to-metal.
* French/Schuko plugs are reversible: the inlet's **2-pole switch** matters.
* Fuse: **T3.15 A H** (ceramic, high breaking capacity).  UHP inrush is 80 A cold.
* The mains compartment closes with screws only, with a cover over the PSU's
  AC terminals and the inlet tabs.  Use V-0 PETG/ASA/PC — never PLA — around
  mains parts.  Route mains and 24 V wiring apart and tie them down.
* A personal build is not "placed on the market"; selling kits or units means
  CE (LVD, EMC, RoHS, EN 62368-1, EN 61000-3-2) on the finished product.

The brick in the power box avoids all of this: it stays closed and certified,
its C14 inlet faces out of the box's rear wall, and its DC cord is cut and
crimped into a JST VH for the hub (the DC side only, SELV).  Nothing above
24 V enters the printed parts.

## Mini BOM — internal-supply variant

| Item | Part | Source | € |
|---|---|---|---:|
| PSU | Mean Well UHP-200-24 | TME / RS / Mouser | 48–54 |
| Inlet | Schurter DD11.0111.1111 (C14, 2-pole switch, fuse) | Mouser / Farnell | 8–12 |
| Fuses | Schurter 0001.2509 T3.15 A H × 2 | Mouser | 1.6 |
| Cord | C13 → Schuko/FR, 1.0 mm² | any | 5 |
| Wiring | H05V-K 1.0 mm² + 4.8 mm insulated receptacles + ferrules | any | 8 |
| DC | 1.5 mm² PSU → hub; 0.75 mm² row feeds | any | 4 |
| Hub | see `electronics/power-hub` (5 × TPS26600, SMCJ33A, …); JLC quote 2026-10-16: $74.13 for 5 PCBs, 2 assembled, ≈ $49.51 in lead-free HASL with the connectors hand-soldered; shipping and VAT extra | JLCPCB | ≈ 46 |

Sources: Mean Well LRS-150/LRS-200/RSP-200/UHP-200/GST60A/GST90A/GST160A datasheets,
Schurter DD11 datasheet, TI TPS2660 / LMR51635 (SLUSF64B) datasheets, ADI AN-88
(hot-plug ringing), TME/RS/Mouser listings (Oct 2026).
