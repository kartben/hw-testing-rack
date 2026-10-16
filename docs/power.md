# Power

**Goal:** "something I can just plug in, ideally without an external power
supply."  → One standard IEC mains cord into the shelf; a certified,
fanless 24 V supply lives inside the printed base.

## Budget

| | per bay | 16 units |
|---|---|---|
| DUT (TPS2553 limit 1.34–1.52 A @ 5 V) | ≤ 7.6 W | — |
| node (ESP32-S3 Wi-Fi peaks, LED, buck/LDO losses) | ≈ 1.5–2 W | — |
| **worst case** (every board at its current limit) | ≈ 11 W at 24 V | ≈ 175 W |
| **realistic** (dev boards idle/running firmware) | 2–4 W | 40–60 W |

Per row: worst case ≈ 1.9 A at 24 V, realistic ≈ 0.5 A.  Each row has its own
eFuse, set to **1.6 A**: rows are wired with JST PH (2 A per contact), so the
limit protects the connectors and the 24 AWG jumpers.  Four DUTs at their own
1.5 A limit at the same time would trip it (it retries on its own).

## Options compared

| Architecture | Cords | Max power | Cost | Verdict |
|---|---|---|---|---|
| **Internal AC-DC (UHP-200-24) + C14 inlet** | 1 standard C13 cord | 201 W | ≈ €80–95 power path | **primary** |
| External 24 V brick (GST160A24 / GST220A24) | brick + cord | 160 / 220 W | ≈ €70–95 | fallback, no mains inside |
| USB-C PD 3.1 EPR (28 V / 5 A) | 1 laptop charger | 140 W | ≈ €5 sink parts + charger + 5 A e-marked cable | 1–3 rows, or whole rack with power budgeting |
| PoE++ per row (802.3bt) | 4 Ethernet + PoE++ switch | 51–71 W per row | ≈ €100 modules + switch | not worth it with Wi-Fi nodes |

### Why the Mean Well UHP-200-24

* **PFC** (PF ≥ 0.94): EN 61000-3-2 harmonic limits apply above 75 W; Mean Well
  itself excludes the cheaper LRS-200 for that case.
* **Universal input, no 115/230 V selector** (a wrong LRS switch position kills it).
* **Fanless at full load up to 50 °C**, 94 % efficient, slim (194 × 55 × 26 mm)
  — it fits flat in the 40 mm-high base with room to spare.
* ≈ €48–54 at TME/RS/Mouser.

### Bus voltage: 24 V

At 24 V a row draws ≤ 1.9 A and the whole rack ≤ 7.3 A: the hub input is a
JST VH (10 A) on 16 AWG, the rows JST PH (2 A, eFuse-limited to 1.6 A) on
24 AWG, and every bay's 24→5 V buck runs at ~21 % duty.  One connector family
for everything inside the shelf (PH), VH only where the whole rack's current
comes in, no screw terminals.
12 V would double the currents and exclude 28 V PD; 48 V would need 100 V
converters.  The bay nodes accept **9–30 V** with 60 V-rated silicon, so the
same boards also run from 20 V / 28 V USB-PD or 24 V PoE modules.

## Protection chain

```
mains → DD11 inlet (2-pole switch, T3.15 A) → UHP-200-24 → hub:
  JST VH → SUD50P06 P-FET (reverse polarity) → SMCJ33A TVS → 2 × 220 µF
  → 5 × TPS26600 eFuse (1.6 A limit, 4 ms soft start, UV 15 V / OV 33 V, auto-retry)
  → JST PH → row daisy chain → each bay node:
     SUD50P06 P-FET → SMBJ33A TVS → 100 µF → LMR51635 (60 V, on above 13.5 V) → 5 V
     → TPS2553 → 50 mΩ shunt (INA226) → DUT
```

* Hot-plugging a bay node into a live 24 V bus rings up to ~2× the bus on
  ceramic caps: the bay buck is a **60 V** LMR51635 (not a 36 V part) and the
  TVS clamps below 54 V; the electrolytic damps the ringing.
* The hub eFuses soft-start each row, so plugging a row never browns out the
  others, and a shorted bay only trips its own row.

## Safety (DIY mains)

* **Protective earth:** inlet PE → PSU FG terminal (green/yellow ≥ 1.0 mm²)
  *and* → the aluminium frame.  Anodising insulates: use a serrated washer /
  scrape the bonding point.  Check ≤ 0.1 Ω PE-to-frame.
* French/Schuko plugs are reversible: the inlet's **2-pole switch** matters.
* Fuse: **T3.15 A H** (ceramic, high breaking capacity).  UHP inrush is 80 A cold.
* The mains compartment closes with screws only; print the `base_mains_cover`
  over the PSU's AC terminals and the inlet tabs.  Use V-0 PETG/ASA/PC — never
  PLA — around mains parts.  Route mains and 24 V wiring apart and tie them down.
* A personal build is not "placed on the market"; selling kits or units means
  CE (LVD, EMC, RoHS, EN 62368-1, EN 61000-3-2) on the finished product.

Not comfortable with mains wiring?  Use the **external brick variant**: a
Mean Well GST160A24-R7B (160 W, Power-DIN plug) into the Kycon KPJX-PM-4S
panel jack pre-cut (knock-out) on the base's rear panel, wired to the same
hub input.  Nothing above 24 V then enters the shelf.

## Mini BOM — base power path

| Item | Part | Source | € |
|---|---|---|---:|
| PSU | Mean Well UHP-200-24 | TME / RS / Mouser | 48–54 |
| Inlet | Schurter DD11.0111.1111 (C14, 2-pole switch, fuse) | Mouser / Farnell | 8–12 |
| Fuses | Schurter 0001.2509 T3.15 A H × 2 | Mouser | 1.6 |
| Cord | C13 → Schuko/FR, 1.0 mm² | any | 5 |
| Wiring | H05V-K 1.0 mm² + 4.8 mm insulated receptacles + ferrules | any | 8 |
| DC | 1.5 mm² PSU → hub; 0.75 mm² row feeds | any | 4 |
| Hub | see `electronics/power-hub` (5 × TPS26600, SMCJ33A, …); JLC quote 2026-10-16: $74.13 for 5 PCBs, 2 assembled, ≈ $49.51 in lead-free HASL with the connectors hand-soldered; shipping and VAT extra | JLCPCB | ≈ 46 |

Sources: Mean Well LRS-150/LRS-200/RSP-200/UHP-200/GST160A datasheets,
Schurter DD11 datasheet, TI TPS2660 / LMR51635 (SLUSF64B) datasheets, ADI AN-88
(hot-plug ringing), TME/RS/Mouser listings (Oct 2026).
