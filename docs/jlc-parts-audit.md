# JLC parts audit (2026-10-19, updated 2026-10-20: the PCBA review fixes, the DATA ×4 v2 and its base)

Every LCSC part on the boards' JLC BOMs (`electronics/<board>/fab/<board>-bom-jlcpcb.csv`),
checked with the [jlcpcb-parts](https://github.com/hulryung/jlcpcb-skill-mcp) MCP server, for series
production: tier, stock and price at the quantity 1, 5 and 10 racks reach.  The per-line tables are
generated: [`bom/jlc-parts.md`](../bom/jlc-parts.md).  The costs per board and per rack are in
[`bom/README.md`](../bom/README.md#jlc-cost) ("At volume").

**Sources.**
- `tools/jlc_parts_snapshot.py` asks the server for each part. The server reads a local snapshot of
  JLC's catalog (2026-10-18, 7.1 M parts) because its live API was down.
- The snapshot has no prices for 39 of the 97 parts. Those take LCSC's public product data: price
  breaks, plus LCSC's own stock as `lcsc_stock`. It is not JLC's assembly stock.
- The result is `electronics/lib/jlc_parts.json`, which `tools/bom.py` reads.
- JLC's own parts library (the search jlcpcb.com/parts runs, public) then gives each part's tier, JLC's
  stock today and its minimum purchase:
  - the tiers are basic, preferred extended and extended;
  - Economic PCBA loads basic and preferred parts free; Standard charges every type;
  - three parts are preferred (C25725 on the v2, BAT54S, 56 Ω C25196);
  - three sell by more than 1: L1 by 32, the two ESP32-S3 modules by 2.
- Re-run the snapshot, then `tools/bom.py`, right before an order.

**Quantities.**
- One rack takes 8 nodes, 1 hub, 6 DATA ports, 2 camera pods and a DATA ×4 for each converted bay:
  - B3 (`x4: v2`) takes the v2 logic variant: 100 × 70, ENIG, every JLC part on one face, Economic.
  - B1 takes the v2's base variant: the same PCB with the logic left off.
  - Both are ordered together, one of each on a 1 × 2 order panel (`data-port-x4-v2-panel`, ENIG,
    mouse bites, one Economic order): one panel per rack. Their own single-order estimates stay for
    the BOM page's calculator.
  - The v1 (100 × 37) is not ordered for the prototype (the user, 2026-10-20).
- JLC assembles at least 2 boards per design.
- Each design is its own PCBA order, so its parts reach their price breaks on their own, even in one
  cart.

## What a rack costs

The parts are at JLC's price breaks: the quoted components scaled by the snapshot's prices. The
fees per order are spread over the boards, plus one $34 shipment (USD).

| Racks in one order | Node ×8 | Hub ×1 | DATA ports ×6 | Pods ×2 | v2 panel ×1 (logic + base) | **Per rack** |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 297.81 | 185.51 | 35.45 | 26.38 | 237.21 | **816.36** |
| 5 | 177.35 | 53.65 | 13.81 | 7.15 | 73.76 | **332.52** |
| 10 | 156.97 | 39.34 | 11.23 | 4.92 | 56.90 | **272.77** |

Floor per board, once the fees per order no longer count (100-board breaks): node $16.69, hub
$22.18, the v2 panel $37.30 (a logic and a base), DATA port $1.30, pod $1.13.  Holding the parts at the prototype price gave
$20.85 and $36.04 for the node and the hub; the hub's CH224A (1590b7a) took another ≈ $4 off its
floor.

Where a board's parts money goes, at 10 racks:

| Board | Parts per board | Biggest lines |
|---|---:|---|
| hub | $19.12 | TPS26600 ×4 $4.58 · ESP32-S3-MINI-1-N8 $4.16 · LMR51635 $1.59 · USB4105 ×2 $1.45 · S6B ×4 $1.15 · KPA-3010 ×10 $1.85 · TJA1462 $0.83 · CH224A $0.34 |
| node | $12.58 | ESP32-S3-WROOM-1-N8R8 $4.08 · LMR51635 $1.43 · S6B ×3 $0.74 · TJA1462 $0.74 · USB4105 $0.63 · INA226 $0.52 · USBLC6 ×4 $0.47 · B8B $0.42 |
| DATA ×4 v2 | $23.57 | USB2517I $3.80 · LSF0108 ×4 $3.35 · CH446Q ×2 $2.71 · INA226 ×4 $2.07 · RP2354B $1.46 · TCA6408A ×2 $1.43 · TPS2553-1 ×4 $1.18 · TYPE-C-31-D-06 ×4 $1.14 · TCA9534 $1.13 |
| v2 base | $12.40 | USB2517I $3.80 · INA226 ×4 $2.07 · TCA6408A ×2 $1.43 · TPS2553-1 ×4 $1.18 · TYPE-C-31-D-06 ×4 $1.14 · USBLC6 ×4 $0.71 · AP2114H $0.23 |
| DATA port | $1.16 | USB4105 $0.63 · S8B $0.33 · USBLC6 $0.14 |
| pod | $0.90 | S8B $0.37 · header $0.08 |

## Stock and sourcing risk

The threshold is JLC's assembly stock against 10 racks' need, summed over the boards.

| Part | Boards | JLC stock | 10 racks need | Risk |
|---|---|---:|---:|---|
| **AOTA-B201610S3R3-101-T** (C42411119, L1) | DATA ×4 v2 (logic) | 3 (2026-10-20) | 10 | **a pre-order**: JLC sells it by 32 at least, so the logic order waits for it and pays for 30 spares ($9.54 per order). It stays: Raspberry Pi approves no other inductor for the RP2350's regulator (below) |
| CH224A (C42459160) | hub | 12,463 | 10 | none: in stock since 1590b7a replaced the out-of-stock AP33772S (and its Global Sourcing); WCH only |
| USB4105-GF-A-120 (C5184243) | node, hub, DATA port | 3,562 | 160 | JLC holds 22×, but **LCSC has 0**: when JLC's stock runs out, it can't refill from LCSC (the v2 has the HRO TYPE-C-31-D-06) |
| S6B-PH-SM4-TB (C265405) | node, hub | 4,813 | 280 | 17×; genuine JST only |
| LMR51635YDDCR (C45262770) | node, hub | 2,500 | 90 | 28×, TI only |
| KPA-3010CGCK (C598310) | hub | 2,203 | 60 | 37×, Kingbright only |
| CH446Q (C109471) | DATA ×4 v2 | 1,744 | 20 | 87×, WCH only |

Single-source parts with no drop-in at JLC:
- ESP32-S3 modules (Espressif);
- TPS26600 eFuse and LMR51635 buck (TI);
- CH224A PD sink (WCH);
- TJA1462 CAN SIC transceiver (NXP; the TI TCAN1462 is out of stock);
- USB2514B and USB2517I USB hubs (Microchip);
- RP2354B MCU (Raspberry Pi) and CH446Q crosspoint (WCH), on the v2;
- INA226 current monitor (TI);
- FSUSB42 USB switch (onsemi);
- USB4105 USB-C (GCT);
- KPA-3010 LEDs (Kingbright).
Everything else is a basic part, with ≥ 100× the need, or has many makers.

## Levers for series production

The USD figures are at 10 racks, at the snapshot's prices. None of these is applied: each needs its
board's owner, and the trade-off ones need the user.

| Lever | Boards | Saves (10 racks) | Kind | Check done / to do |
|---|---|---:|---|---|
| **USB-C where 5 A at 48 V isn't needed**: USB4105 ($0.52 at 100) → HRO TYPE-C-31-M-12 (C165948, 5 A, 20 V, $0.15 at 100; 331k stock, the node's part before v0.5) | node J3, hub J6 (console), DATA port J1 (15 a rack; the v2 has HRO already) | ≈ $71 | decision | Each port draws ≤ 1.5 A (5 A rating) at ≤ 5.25 V (20 V rating). The hub's PD input J1 keeps the GCT for the 48 V that 28 V EPR needs. Needs new footprints, a re-route (the node's USB HS pair) and a mechanical check; it also moves 15 of the 16 per rack off a part LCSC holds none of |
| **JST PH SMD second source**: S6B / S8B / B8B-PH-SM4-TB ($0.25–0.42) → PH 2.0 SMD clones ≈ $0.04–0.07 (e.g. SHOU HAN 2.0-xP WT / LT, WAFER-PH2.0-6PWB C3029444), or CJT's A2001WR-S-6P C225237 / A2001WR-S-8P C225239 / A2001WV-S-8P C225232 (vertical) at $0.16–0.20 @ 100 (phosphor bronze, LCP, −40…105 °C) | node (5), hub (4), DATA ports, DATA ×4, pods (52 a rack; the v2's J1 is hand-soldered) | ≈ $129 no-name, ≈ $68 CJT | decision (open) | Same 2 A rating; mates with PHR housings. Check the footprint geometry against each clone's drawing. Genuine JST holds up better on cables that are re-plugged |
| **USBLC6-2SC6 second source**: ST C7519 ($0.12–0.18) → UMW C2687116 ($0.042 at 100) or TECH PUBLIC C2827654 ($0.036) | node (4), hub, DATA ports, DATA ×4 v2 and its base (4 each) (47 a rack) | ≈ $38 | decision | Same SOT-23-6 and pinout, so pins 1 / 6 and 3 / 4 still join inside and the flow-through layout holds. Check the clamp voltage and capacitance against ST's (0.35 pF line-to-line on the UMW) |
| **DATA ×4 USB hub**: USB2514B → CH334R or FE1.1s | DATA ×4 v1 | — | moot | v1 is not ordered; the v2's USB2517I serves 7 ports (the four, the analyzer, two spare) |
| **DATA ×4 at most 100 mm long**: 108 × 24 → 100 × 37 mm | DATA ×4 | the 5-board order went from $104.17 to $85.37 (bare PCB $31.90 → $13.10, JLC's 4-layer offer; no deburring line at 37 mm) | **applied** (2b84f26, a860935) | The offer stops at 10 PCBs: above that JLC's $25 engineering fee is back, so at 50 and 100 PCBs the board costs $53.80 and $73.40, $6–11 more than at 108 × 24 (calculator, 2026-10-20). v1 is not ordered for the prototype since: the converted bays take the v2 |
| **DATA ×4 v2 logic and base on one 1 × 2 panel** (the same PCB twice, one CPL, ENIG, one Economic order) | DATA ×4 v2 | ≈ $26 for the rack's 2 + 2 ($237.21 against $263.40), ≈ $37 at 5 + 5, ≈ $61 at 10 + 10 | **applied** (the orchestrator; bom.py's `data-port-x4-v2-panel`) | 100 × 142 with a 2 mm mouse-bite gap: one setup and stencil, each type loaded once, no panel fee (one design). The tabs join along the 100 mm edges, away from the ends: the ends sit in the cradle's slots with 0.5 mm to spare. The nubs on the bottom edge (floor, notches at x 31 / 67) and the top edge (latch hooks) are sanded flush. The base goes ENIG; as many bases as logics. A V-cut joint is below |
| **The same panel, V-cut** instead of mouse bites | DATA ×4 v2 | nothing for the rack's 2 + 2 ($263.70 against $263.40), ≈ $11 at 5 + 5, ≈ $34 at 10 + 10: $26–27 more than mouse bites | decision | JLC's Economic panels take mouse bites only, so a V-cut panel is Standard PCBA: $25.56 setup, $8.21 stencil, $1.53 for each of 41 types. It needs 5 mm rails with fiducials (100 × 150, $52.60 for 5) and ≥ 0.4 mm of copper from both V-cut 100 mm edges; the board keeps 0.3. The 1 mm corner radii at those edges come out square. In return: a clean straight edge, and Standard's SPI and adjustable reflow under the 0.4 mm QFN-80 |
| **DATA ×4 v2 base in lead-free HASL** when ordered alone | v2 base | $12.20 per order | single orders only | Its finest pitch is the hub's 0.5 mm QFN, which v1 put on HASL. The rack's base is on the ENIG panel; the HASL estimate stays for a single base order (the BOM page's calculator) |
| **DATA ×4 v2 resistor arrays** → basic 0402 resistors | DATA ×4 v2 (logic) | $9.21 per order (3 extended types at Economic's $3.07) | **declined** (the v2 session, 2026-10-20) | They stay: 60 resistors in place of 15 arrays means re-placing and re-routing the pin chains. In the base, RN1–RN3 sit over the hub's 0.5 mm strap pins, where a row of 0402s doesn't fit |
| **PD sink**: AP33772S (Global Sourcing, stock 0) → CH224A | hub | the hub order went from $205.95 to $185.29 | **applied** (1590b7a) | No input switch any more. The CH224Q (C46061833) and the HUSB238A-BB001-QN16R (C24833806, PD 3.x EPR to 28 / 48 V, $0.40 at 100) remain as second sources; the HUSB238 (non-A) and the CH224K stop at 20–25 V |
| **Hub rows C and D not fitted** (already in `JLC_LEVERS`) | hub | ≈ $35 | decision | 2 × TPS26600, 2 × S6B, 4 LEDs and their passives per hub |

An external BOM review (2026-10-19) was checked against the catalog by the orchestrator. Most of its LCSC codes were wrong, and its fee premise doesn't hold on Standard PCBA (every unique type is charged). Its valid levers (the HRO USB-C, the PH clones, the USBLC6 second source) are in the table above; the fourth, the TPS2553DDBVR on the node's U9, is applied (4ebe8f1: $0.19 against $0.54, same pinout and I_LIM).

Checked and rejected:
- **DATA ×4 v2 L1**: declined by the v2 session, 2026-10-20.
  - The candidates: FTC201612S3R3MBCA (C18724415) or AFE201610S3R3MBT (C22459316), in stock and sold
    by 1 (≈ $10 per order).
  - The AOTA-B201610S3R3-101-T stays because Raspberry Pi qualifies it and it is polarity-marked. The
    inductor's leakage field couples into the VREG_LX loop, so its orientation matters, and neither
    candidate has a guaranteed mark.
  - Only the logic order pays the 32-piece pre-order. The base doesn't fit L1.
- **ESP32-S3-MINI-1-N4R2** costs more than the N8 at 100 ($3.66 against $3.36). The node's
  WROOM-1-N8R8 stays for the camera's octal PSRAM.
- **Cheaper CAN transceivers without signal improvement**: TCAN1044AV (C3234993), TJA1051T/3 (C38695,
  $0.39), SIT1042AT/3 (C5382545, $0.31), SIT1044T/3 (C2922538, $0.28). Each saves $0.35–0.45 a board but
  loses signal improvement on the star bus (docs/can.md). The TJA1462 stays.
- **TPS26600, INA226, TCA6408A**: no drop-in in JLC's catalog. find_alternatives returned none; a
  cheaper part means a new footprint for cents.
- **LMR51635**: already cheap for a 60 V, 3.5 A synchronous buck. The input needs ≥ 40 V (VRACK 28 V,
  33 V TVS), which rules out the basic 30 V bucks.
- **Regulators** (AMS1117, AP2112K, XC6206): none proposed. The DATA ×4's USB2514B draws ≈ 0.16 A on
  3.3 V, and the XC6206's SOT-23 can't shed ≈ 0.31 W.
- **IRF7842 second source**: the VBsemi clone (C5438941) has 30 in stock.  Moot since 1590b7a: the
  CH224A hub has no input switch.
- **Hub Q1 / Q2 at 60 V**: the AP33772S drives the gate at most 4 V above VCC. The 60 V SO-8 parts in
  stock are ≥ 28 mΩ at 4.5 V, against the IRF7842's 5.9 mΩ (docs/electronics.md). They stayed at 40 V, and
  then went with the input switch (1590b7a).
- **Node C11 10u 0805 → 1206**: the larger footprint overlaps U2 and its neighbours.
- **From the external review**:
  - removing the C1 bulk cap;
  - TJA1462 → SIT1044 / TJA1051, which have no signal improvement for the star bus;
  - LMR51635 → TPS54302 (C311983, 28 V max) / LMR51410 (C32347484, 42 V max), both below the TVS clamp;
    a 3.3 µH SWPA4020S3R3MT (C83424, Isat 3.2 A) for the FXL0630 has too little margin, and the
    FXL0630-4R7-M (C167220) is extended too;
  - TPS26600 → TPS2595x / TPS25921, ≤ 24 V parts;
  - INA226 and FSUSB42 clones: none verified (the catalog has no UMW / HXY INA226 and no UMW TPS2553),
    and the CH442E needs a 4–5.5 V supply;
  - merging the hub's resistor values further: they set functions;
  - C7519, BAT54S and BZT52C12 as basic parts: no basic version exists. The basic BAV99 (C2500) is
    silicon, and Standard PCBA charges every type alike anyway. The 1 µF 50 V X7R 0603 (C5199872) is
    extended;
  - ESP32-S3 N8R8 → N8: saves $0.23 at 100, and loses the camera's PSRAM.

## Surface finish: HASL or ENIG (2026-10-20)

Every board is in lead-free HASL except the DATA ×4 v2's PCB. That one is ENIG for its logic
variant's RP2354B (QFN-80, 0.4 mm pitch).

**JLC's rules.**
- The PCBA capabilities page's Economic table gives 4-layer, 1.6 mm, green boards lead-free HASL,
  leaded HASL or ENIG, for 2–50 boards. 6 layers is ENIG only, 2–30 boards.
- It ties no finish to a pitch. Economic's minimum IC pitch is 0.4 mm, Standard's 0.35 mm.
- JLC X-rays every QFN, LGA and BGA automatically.
- So a 0.4 mm QFN on lead-free HASL is not refused. JLC still advises against it:
  - its surface-finish article says lead-free HASL "does not provide sufficient surface planarity and
    is unsuitable for fine-pitch components";
  - its HASL blog keeps HASL for 0.65 mm and coarser, and warns that below 0.5 mm the unevenness may
    bridge;
  - its blog FAQ sends fine-pitch BGAs to ENIG.
- Fabricators' guides put HASL's pad-height spread at ±5–15 µm against < 0.5 µm for ENIG. They draw
  the practical line between 0.5 and 0.65 mm. These are rules of thumb, not an IPC limit.

**What the v2's parts face on HASL.**
- RP2354B: 80 pads at 0.4 mm, at Economic's limit, plus a 3.4 mm exposed pad. A domed pad shifts the
  stencil's print and the package's seat. Bridges and opens are the likely failures. A 0.4 mm QFN-80
  is hard to rework by hand.
- USB2517I: QFN-64 at 0.5 mm with a 4.7 mm exposed pad. The large dome under it is the risk: the
  package floats or tilts, and voids form.
- LSF0108 (DHVQFN-20), TCA6408A (VQFN-16) and TPD4E05U06 (USON-10): 0.5 mm, small exposed pads.
- The vertical USB-C: 0.3 mm pads at 0.5 mm.
- The 0.5 mm parts are the class v1 had on HASL: USB2514B QFN-36, TCA6408A, USB4105.

**What ENIG buys.**
- Flat pads, so the stencil prints evenly on the 0.4 / 0.5 mm parts and their exposed pads.
- A longer shelf life before assembly. JLC gives no figure; guides say about 12 months.
- Its weak point is black pad, which is rare at JLC's volumes.
- For the user's hand soldering of J1 and the 2 × 6 headers, both finishes wet well. HASL comes
  pre-tinned.

**Cost (USD, PCB difference only; the PCBA is the same).**

| Option for the rack's 2 + 2 | Order | 5 + 5 | 10 + 10 |
|---|---:|---:|---:|
| Two orders, logic ENIG + base HASL | 263.40 | 405.94 | 630.18 |
| Two orders, both ENIG | 275.60 | 418.14 | 642.98 |
| Two orders, both HASL | 251.20 | 393.74 | 617.38 |
| One 1 × 2 panel, mouse bites, Economic, ENIG (the rack's order) | 237.21 | 368.79 | 569.02 |
| One 1 × 2 panel, mouse bites, Economic, HASL | 224.41 | 355.99 | 554.92 |
| One 1 × 2 panel, V-cut, Standard, ENIG | 263.70 | 395.27 | 596.00 |

- HASL instead of ENIG saves $12.20–12.80 per 100 × 70 order and $12.80–14.10 per panel order.
- That is $2.44 a rack at 5 racks and $1.28 at 10.

**Base and logic on one PCB.**
- A HASL base and an ENIG logic can't share a panel: one panel has one finish.
- The panel saves $26 for the rack's 2 + 2, more than HASL saves on the base ($12.20). So if the user
  takes the panel, the base goes ENIG with the logic.
- A panel in HASL ($224.41) is only for those who accept HASL under the 0.4 mm QFN-80.
- A V-cut panel ($263.70) takes Standard PCBA: Economic panels have mouse bites only.

**Recommendation.**

| Board | Finish | Saving | Risk |
|---|---|---:|---|
| DATA ×4 v2 logic | **ENIG** | 0 (HASL would save $12.20) | HASL under the 0.4 mm QFN-80 and its exposed pad risks bridges and opens on the most expensive board (≈ $31 of parts) |
| DATA ×4 v2 base, ordered alone | **lead-free HASL** | $12.20 per order | Low: 0.5 mm parts as on v1. Watch the USB2517I's 4.7 mm exposed pad in JLC's X-ray report |
| DATA ×4 v2, logic + base on one panel | **ENIG** for both | $26 against two orders | The panel's own trade-offs (`JLC_LEVERS`) |
| bay node | lead-free HASL, kept | – | INA226 TSSOP-10, FSUSB42 MSOP-10 and USB4105 at 0.5 mm, leaded. The WROOM-1 at 1.27 mm with a 3.9 mm GND pad. Fine |
| power hub | lead-free HASL, kept | – | Finest is the TPS26600 at 0.65 mm with its exposed pad, the MINI-1 LGA at 0.85 mm, the USB4105 at 0.5 mm. Fine |
| DATA port | lead-free HASL, kept | – | The USB4105's 0.3 mm pads at 0.5 mm are its finest. Fine |
| camera pod | lead-free HASL, kept | – | Nothing finer than the PH's 2 mm and 0603 parts. Fine |

Sources:
- [JLC PCBA capabilities](https://jlcpcb.com/capabilities/pcb-assembly-capabilities): the Economic
  finish table, the minimum pitch, the X-ray FAQ;
- [JLC surface finish article](https://jlcpcb.com/help/article/jlcpcb-surface-finish);
- [JLC HASL blog](https://jlcpcb.com/blog/hasl-surface-finish-pcb);
- [PCBSync surface finish guide](https://pcbsync.com/pcb-surface-finish/);
- [PCBCart, ENIG vs immersion silver vs HASL](https://www.pcbcart.com/article/content/enig-vs-immersion-silver-vs-hasl).

## AISLER against JLC (2026-10-20)

AISLER (aisler.net, Germany) priced for the rack's order: 8 nodes, 1 hub, 6 DATA ports, 2 pods, and
the v2 as one 1 × 2 panel. Public pages only: no account, no upload, no quote, no cart. AISLER's own
assembly calculator shows its price only once the files are uploaded.

**AISLER's prices** (net, VAT added for a consumer).
- **Bare PCBs** ("Beautiful Boards", Budget): job fee plus area × rate × quantity, in sets of 3.
  Shipping is in the job fee.
  - 2-layer 1.6 mm HASL: €12 + €0.067/cm².
  - 4-layer 1.6 mm ENIG: €14 + €0.13/cm². There is no 4-layer HASL.
  - This table (AISLER's "Our simple pricing", 2023) still matches a third-party quote of 7 October 2026:
    4-layer 100 × 80 ENIG, €165.46 for 12 with German VAT (computed €165.17).
- **Stencil:** €5 + €0.095/cm².
- **Assembly** ("Amazing Assembly", from 1 board). Two published sets of figures:
  - **A**, AISLER's own (2022), with no job fee, as an October 2026 comparison confirms: €7.50 per unique
    part, €0.04 per placement, €0.01/cm² handling.
  - **B**, a third party's (April 2026): €75 setup, €4.50 per unique part, €0.05 per placement.
  - They land within 1 % of each other for this order.
- **Parts:** AISLER buys them from distributors with live BOM integration: Würth, TI, Mouser,
  Digi-Key, Farnell, Arrow and **LCSC**. Leftovers come back with the boards. Customer-supplied parts
  cost €15 per unique part.
- **Lead time:** Blitz assembly 9–12 business days (4-layer 11–12), standard 18 business days.

**Order cost** (€; JLC from bom.py at $1 = €0.92, one DHL shipment included).
- AISLER's parts are priced at LCSC's price breaks with no markup, which flatters it: Mouser or
  Digi-Key cost more.
- TTC adds French VAT, 20 %. For JLC that is import VAT on goods and shipping; JLC's DHL DDP option
  collects it at checkout. Otherwise DHL bills it with a clearance fee of roughly €15–20.

| Racks in one order | AISLER per rack, net (A–B) | AISLER TTC | JLC per rack, net | JLC TTC | AISLER / JLC |
|---:|---:|---:|---:|---:|---:|
| 1 | 1,513–1,508 | ≈ 1,812 | 751 | ≈ 901 | 2.0× |
| 5 | 553–555 | ≈ 665 | 306 | ≈ 367 | 1.8× |
| 10 | 433–436 | ≈ 521 | 251 | ≈ 301 | 1.7× |

**Per board, at 1 rack** (€ net):

| Board | AISLER (A / B) | JLC | Ratio |
|---|---:|---:|---:|
| node ×8 | 559 / 516 | 274 | 1.9–2.0× |
| hub ×1 | 346 / 322 | 171 (2 assembled) | 1.9–2.0× |
| DATA port ×6 | 76 / 133 | 33 | 2.3–4× |
| pod ×2 | 83 / 134 | 24 | 3.4–5.6× |
| v2 panel ×1 | 448 / 402 | 218 (2 panels) | 1.8–2.1× |

**What drives the gap.**
- Area: €0.13/cm² against JLC's flat $8 / $14 offer within 100 × 100 mm.
- Every unique part costs €4.50–7.50 at AISLER. JLC's Economic charges $3.07 per extended type and
  nothing for basic ones; its Standard charges $1.53 for every type.
- The small 2-layer boards suffer most: AISLER's per-design fees against JLC's $8.18 Economic setup.

**Sourcing our parts there.**
- LCSC is integrated, so the LCSC-only parts can be bought by AISLER, LCSC's stock permitting:
  - CH446Q, CH224A, RP2354B;
  - the HRO TYPE-C-31-D-06, the WS2812B-2020, FXL0630, MSK12C02, the UMW SUD50P06-15;
  - the XL-2835UWC LED, the hanxia headers, the YXC crystal.
- Two parts are better off at AISLER:
  - the GCT USB4105, which LCSC holds none of, is at Mouser and Digi-Key;
  - the Abracon L1 sells by 1 at Mouser, against JLC's 32-piece pre-order.
- No gap is known. Anything LCSC runs out of would be a consigned part at €15 per unique part, or an
  alternate.

**Lead time.** JLC is about 1.5–2 weeks door to door: 3–4 days 4-layer PCB, then Economic assembly in
1–3 days or Standard in ≥ 4, then DHL in 2–4 days. AISLER is 2–3.5 weeks.

**Verdict.** JLC on every board and for the whole order. AISLER costs 1.7–2× as much at 1–10 racks,
and 2–5× on the small 2-layer boards. Its strengths:
- an EU supply chain with no customs step;
- a single assembled board when that is all one needs;
- the Abracon L1 by the piece.
None of these closes the gap.

**A real AISLER quote** would mean uploading, for each design, the Gerbers, the BOM and the
pick-and-place: the node, the hub, the DATA port, the pod and the v2 panel (or the KiCad projects).
It would replace three estimates with real figures: each part at AISLER's distributor price, its
exact assembly fee, and its panel handling. It needs an AISLER account and the user's OK.

Sources:
- [AISLER, Our simple pricing](https://community.aisler.net/t/our-simple-pricing/102);
- [Amazing Assembly price cuts](https://community.aisler.net/t/amazing-assembly-gets-radical-price-cuts/905);
- [component sourcing](https://community.aisler.net/t/component-sourcing-for-assembly/2464);
- [Amazing Assembly](https://aisler.net/products/assembly);
- [DeltaProto, EMS vs Aisler vs JLCPCB](https://deltaproto.com/pcb-assembly-netherlands-compared);
- [Dilder, PCB assembly and prototyping](https://dilder.dev/docs/design/pcb-assembly-and-prototyping/).

## Promotions (checked 2026-10-20)

JLC's public coupon center and help pages, read without an account. The user claims and applies coupons
at checkout. None is counted in the cost totals above.

**Rules.**
- Each coupon is used once, and only one coupon applies to an order. Every board in the cart is its
  own order, so the six boards can take up to six coupons. JLC's checkout decides how they combine.
- "JLCONE" coupons need the order placed from the JLCONE desktop app. The calculator also shows "Order
  on JLCONE Desktop: save $1–$20 per order", without a breakdown.
- EasyEDA coupons ($10 PCB, $10 PCBA) are for designs made in EasyEDA. Ours are KiCad's, so they don't
  apply.

| Coupon | Off our cart | Conditions | Valid |
|---|---:|---|---|
| JLCONE 4-Layer PCB | $5 | a 4-layer PCB order above $5, through JLCONE | until 2035-03-23 (durable) |
| PCBA Special Offer | $9 | a PCBA order above $1, excluding freight | until 2026-10-30 |
| PCBA Special Offer | $6 | a PCBA order above $1, excluding freight | until 2026-10-30 |
| JLCONE PCBA | $20 | a PCBA order above $100 (the node or the hub), through JLCONE | 30 days after claiming |
| JLCONE PCB | $5 | a PCB order above $2, through JLCONE | 30 days after claiming |
| Social follow | $5 | follow JLC's channels and send the account ID through JLC's form ([sales-promotion](https://jlcpcb.com/sales-promotion)) | while the page offers it |

Up to ≈ $45 if they all stack, one per board. Economic orders (the DATA boards, the pod) are the ones a $9 or $6 SMT coupon covers best: it takes Economic's $8.18 setup off (JLC's "free assembly for 1–6 layer PCBs"). Programs:
- **Brand Advocate Program** (help center, 2026-08-26): free or discounted prototyping, coupons and
  payments for builders who publish their work on YouTube, Instagram, TikTok or X. Free to apply. The
  amount is JLC's decision.
- **Free PCBs for university teams**: not our case.
- **No program for open-source projects as such** was found. The 2024 "free 6-layer PCBs" creator
  sponsorship seems to have given way to the Brand Advocate Program.

**Seasonal.** Black Friday 2025 ran from November 18 to December 8, with "$650 in coupons" across JLC's
four brands (PCB, 3D printing, CNC, mechatronics) and flash coupons; the PCBA coupon amounts were not
published. A 2026 edition is likely but not announced.

