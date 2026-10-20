# JLC parts audit (2026-10-19, updated 2026-10-20 after every board's PCBA review fixes)

Every LCSC part on the five boards' JLC BOMs (`electronics/<board>/fab/<board>-bom-jlcpcb.csv`),
checked with the [jlcpcb-parts](https://github.com/hulryung/jlcpcb-skill-mcp) MCP server, for series
production: tier, stock and price at the quantity 1, 5 and 10 racks reach.  The per-line tables are
generated: [`bom/jlc-parts.md`](../bom/jlc-parts.md).  The costs per board and per rack are in
[`bom/README.md`](../bom/README.md#jlc-cost) ("At volume").

**Sources.**
- `tools/jlc_parts_snapshot.py` asks the server for each part. The server reads a local snapshot of
  JLC's catalog (2026-10-18, 7.1 M parts) because its live API was down.
- The snapshot has no prices for 30 of the 70 parts. Those take LCSC's public product data: price
  breaks, plus LCSC's own stock as `lcsc_stock`. It is not JLC's assembly stock.
- The result is `electronics/lib/jlc_parts.json`, which `tools/bom.py` reads.
- The local catalog tells basic from extended only. A preferred-extended part may hide among the
  *extended* ones (tier to confirm).
- Re-run the snapshot, then `tools/bom.py`, right before an order.

**Quantities.**
- One rack takes 8 nodes, 1 hub, 6 DATA ports, 2 DATA ×4 and 2 camera pods: the configuration's
  converted bays B1 and B3 take a DATA ×4 each, priced as v1.
- JLC assembles at least 2 boards per design.
- Each design is its own PCBA order, so its parts reach their price breaks on their own, even in one
  cart.

## What a rack costs

The parts are at JLC's price breaks: the quoted components scaled by the snapshot's prices. The
fees per order are spread over the boards, plus one $34 shipment (USD).

| Racks in one order | Node ×8 | Hub ×1 | DATA ports ×6 | Pods ×2 | DATA ×4 ×2 | **Per rack** |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 297.79 | 185.51 | 35.45 | 26.38 | 104.17 | **683.30** |
| 5 | 177.29 | 53.65 | 13.81 | 7.15 | 42.89 | **301.59** |
| 10 | 156.91 | 39.34 | 11.23 | 4.92 | 33.67 | **249.47** |

Floor per board, once the fees per order no longer count (100-board breaks): node $16.68, hub
$22.17, DATA ×4 $11.49, DATA port $1.30, pod $1.13.  Holding the parts at the prototype price gave
$20.85 and $36.04 for the node and the hub; the hub's CH224A (1590b7a) took another ≈ $4 off its
floor.

Where a board's parts money goes, at 10 racks:

| Board | Parts per board | Biggest lines |
|---|---:|---|
| hub | $19.07 | TPS26600 ×4 $4.58 · ESP32-S3-MINI-1-N8 $4.16 · LMR51635 $1.59 · USB4105 ×2 $1.45 · S6B ×4 $1.15 · KPA-3010 ×10 $1.85 · TJA1462 $0.83 · CH224A $0.34 |
| node | $12.55 | ESP32-S3-WROOM-1-N8R8 $4.08 · LMR51635 $1.43 · S6B ×3 $0.74 · TJA1462 $0.74 · USB4105 $0.63 · INA226 $0.52 · USBLC6 ×4 $0.47 · B8B $0.42 |
| DATA ×4 | $11.22 | USB4105 ×4 $2.51 · INA226 ×4 $2.09 · USB2514B $1.54 · TCA6408A ×2 $1.25 · TPS2553-1 ×4 $0.94 · USBLC6 ×6 $0.83 |
| DATA port | $1.16 | USB4105 $0.63 · S8B $0.33 · USBLC6 $0.14 |
| pod | $0.89 | S8B $0.37 · header $0.08 |

## Stock and sourcing risk

The threshold is JLC's assembly stock against 10 racks' need, summed over the boards.

| Part | Boards | JLC stock | 10 racks need | Risk |
|---|---|---:|---:|---|
| CH224A (C42459160) | hub | 12,997 | 10 | none: in stock since 1590b7a replaced the out-of-stock AP33772S (and its Global Sourcing); WCH only |
| USB4105-GF-A-120 (C5184243) | node, hub, DATA ×4, DATA port | 3,748 | 240 | JLC holds 16×, but **LCSC has 0**: when JLC's stock runs out, it can't refill from LCSC |
| S6B-PH-SM4-TB (C265405) | node, hub | 4,931 | 280 | 18×; genuine JST only |
| LMR51635YDDCR (C45262770) | node, hub | 2,770 | 90 | 31×, TI only |
| KPA-3010CGCK (C598310) | hub | 2,203 | 60 | 37×, Kingbright only |

Single-source parts with no drop-in at JLC:
- ESP32-S3 modules (Espressif);
- TPS26600 eFuse and LMR51635 buck (TI);
- CH224A PD sink (WCH);
- TJA1462 CAN SIC transceiver (NXP; the TI TCAN1462 is out of stock);
- USB2514B USB hub (Microchip);
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
| **USB-C where 5 A at 48 V isn't needed**: USB4105 ($0.52 at 100) → HRO TYPE-C-31-M-12 (C165948, 5 A, 20 V, $0.15 at 100; 331k stock, the node's part before v0.5) | node J3, hub J6 (console), DATA port J1, DATA ×4 J101–J401 (23 a rack) | ≈ $109 | decision | Each port draws ≤ 1.5 A (5 A rating) at ≤ 5.25 V (20 V rating). The hub's PD input J1 keeps the GCT for the 48 V that 28 V EPR needs. Needs new footprints, a re-route (the node's USB HS pair) and a mechanical check; it also moves 23 of the 24 per rack off a part LCSC holds none of |
| **JST PH SMD second source**: S6B / S8B / B8B-PH-SM4-TB ($0.25–0.42) → PH 2.0 SMD clones ≈ $0.04–0.07 (e.g. SHOU HAN 2.0-xP WT / LT, WAFER-PH2.0-6PWB C3029444), or CJT's A2001WR-S-6P C225237 / A2001WR-S-8P C225239 / A2001WV-S-8P C225232 (vertical) at $0.16–0.20 @ 100 (phosphor bronze, LCP, −40…105 °C) | node (5), hub (4), DATA ports, DATA ×4, pods (54 a rack) | ≈ $133 no-name, ≈ $70 CJT | decision (open) | Same 2 A rating; mates with PHR housings. Check the footprint geometry against each clone's drawing. Genuine JST holds up better on cables that are re-plugged |
| **USBLC6-2SC6 second source**: ST C7519 ($0.12–0.18) → UMW C2687116 ($0.042 at 100) or TECH PUBLIC C2827654 ($0.036) | node (4), hub, DATA ports, DATA ×4 (6) (51 a rack) | ≈ $42 | decision | Same SOT-23-6 and pinout, so pins 1 / 6 and 3 / 4 still join inside and the flow-through layout holds. Check the clamp voltage and capacitance against ST's (0.35 pF line-to-line on the UMW) |
| **DATA ×4 USB hub**: USB2514B ($1.54) + 24 MHz crystal (extended) → CH334R (C4154405, QSOP-16, $0.32 at 100, I²C) or FE1.1s (C9359, $0.40) + 12 MHz crystal C9002 (basic) | DATA ×4 | ≈ $24, plus $3.07 per order (one extended type fewer) | owner (v2) | Per-port power stays on the TPS2553s and the TCA6408A. Check MTT, the USB-IF strapping and the 3.3 V load (CH334 85 mA, same as the USB2514B's budget) |
| **PD sink**: AP33772S (Global Sourcing, stock 0) → CH224A | hub | the hub order went from $205.95 to $185.29 | **applied** (1590b7a) | No input switch any more. The CH224Q (C46061833) and the HUSB238A-BB001-QN16R (C24833806, PD 3.x EPR to 28 / 48 V, $0.40 at 100) remain as second sources; the HUSB238 (non-A) and the CH224K stop at 20–25 V |
| **Hub rows C and D not fitted** (already in `JLC_LEVERS`) | hub | ≈ $35 | decision | 2 × TPS26600, 2 × S6B, 4 LEDs and their passives per hub |

An external BOM review (2026-10-19) was checked against the catalog by the orchestrator. Most of its LCSC codes were wrong, and its fee premise doesn't hold on Standard PCBA (every unique type is charged). Its valid levers (the HRO USB-C, the PH clones, the USBLC6 second source) are in the table above; the fourth, the TPS2553DDBVR on the node's U9, is applied (4ebe8f1: $0.19 against $0.54, same pinout and I_LIM).

Checked and rejected:
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

## Promotions (checked 2026-10-20)

JLC's public coupon center and help pages, read without an account. The user claims and applies coupons
at checkout. None is counted in the cost totals above.

**Rules.**
- Each coupon is used once, and only one coupon applies to an order. Every board in the cart is its
  own order, so the five boards can take up to five coupons. JLC's checkout decides how they combine.
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

Up to ≈ $45 if all five stack, one per board. Programs:
- **Brand Advocate Program** (help center, 2026-08-26): free or discounted prototyping, coupons and
  payments for builders who publish their work on YouTube, Instagram, TikTok or X. Free to apply. The
  amount is JLC's decision.
- **Free PCBs for university teams**: not our case.
- **No program for open-source projects as such** was found. The 2024 "free 6-layer PCBs" creator
  sponsorship seems to have given way to the Brand Advocate Program.

**Seasonal.** Black Friday 2025 ran from November 18 to December 8, with "$650 in coupons" across JLC's
four brands (PCB, 3D printing, CNC, mechatronics) and flash coupons; the PCBA coupon amounts were not
published. A 2026 edition is likely but not announced.

