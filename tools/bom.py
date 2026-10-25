#!/usr/bin/env python3
"""Full bill of materials for the shelf, derived from config/rack.yaml.

    python tools/bom.py

Writes
  bom/rack-bom.csv          every line item (category, qty, unit price, supplier ref)
  bom/README.md             human summary (cost per category, cut list, print list)
  site/assets/bom.json      data for the BOM page of the web viewer

Electronics come from the per-board BOMs written by the KiCad pipeline
(electronics/<board>/<board>-bom.csv) priced with tools/../electronics
catalogue + cached JLC prices, and add up to a real JLCPCB quote (JLC_QUOTE);
mechanics are counted from the geometry; STL volumes give filament estimates.
Prices are indicative (EUR, ex VAT, small quantities, October 2026) — always
re-quote before ordering.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import plate_layout  # noqa: E402
import rackcfg  # noqa: E402

REPO = rackcfg.REPO
sys.path.insert(0, str(REPO / "electronics" / "tools"))
USD_EUR = 0.92
PETG_DENSITY = 1.27          # g/cm³
PRINT_FILL = 0.55            # walls + 15–20 % gyroid ≈ 55 % of the solid volume
PETG_EUR_PER_KG = 20.0

# Real quote taken on jlcpcb.com on 2026-10-16 (USD, logged-in account), without shipping
# (DHL ≈ $27–40) and import VAT.  Indicative: JLC's prices move, re-quote before ordering.
JLC_QUOTE_DATE = "2026-10-16"
JLC_SHIPPING = "DHL ≈ $27–40"
# Every board goes in one JLC cart (the user, 2026-10-19: "je commanderai tout à la fois"): one
# shipment for the lot, the middle of JLC's DHL range.  It is the only cost the designs share in one
# order: setup, stencil and part-type fees stay per design.
JLC_SHIPPING_USD = 34.00
JLC_QUOTE = {
    # The order the user chose on 2026-10-19 ("10 en HASL"): 10 PCBs, lead-free HASL, all 10 assembled (8 bays
    # and 2 spares).  JLC's real quote, 2026-10-23 (jlcpcb.com, the user's account, main's f9916db Gerbers, JLC
    # BOM and CPL uploaded with the user's OK): green, Standard PCBA (the WROOM-1 takes no Economic), JLC's two
    # 5 mm rails (84 × 90 mm), 40 placed types × $1.55: $266.56.  No X-ray line: the WROOM-1 is castellated (the
    # hub's MINI-1, with pads under it, is X-rayed).  JLC charges the USB4105 (J3) as a special component ($0.03
    # a piece) and flags the WS2812B-2020 (D4) as difficult: reviewed after the order, it may cost an advanced
    # option and adds 2 days.  It replaces the estimate of 2026-10-19 ($319.86, with its adjustments $316.95).
    "bay-node": {
        "pcbs": 10, "assembled": 10, "spares": 2, "service": "Standard", "total": 266.56, "date": "2026-10-23",
        "from_fab": True,
        "spec": "4-layer 74×90 mm (84×90 with JLC's rails), lead-free HASL",
        "pcb": {"special offer": 14.00, "lead-free HASL": 5.40},
        "pcba": {"setup": 25.75, "stencil": 8.27, "components": 143.36, "feeders": 62.00, "SMT": 6.96,
                 "packaging": 0.52, "special components": 0.30},
    },
    # JLC's real quote, 2026-10-23 (jlcpcb.com, the user's account, main's 7ff9a52 Gerbers, JLC BOM and CPL
    # uploaded with the user's OK): 5 PCBs, 2 assembled, green, lead-free HASL, Standard PCBA (the MINI-1), JLC's
    # rails (86 × 100 mm), 33 placed types × $1.55: $145.00.  Rows C and D not fitted (the user, 2026-10-23),
    # the CH224A from LCSC, the 47 nF soft start, the LMR51625.  JLC charges the USB4105 (J1, J6) as a special
    # component and X-rays the MINI-1.  It replaces the quote of 2026-10-19 ($242.52, $150.14 with its
    # adjustments: the 76 × 100 board, merged values, the CH224A, rows C and D).
    "power-hub": {
        "pcbs": 5, "assembled": 2, "service": "Standard", "total": 145.00, "date": "2026-10-23", "from_fab": True,
        "spec": "4-layer 76×100 mm (86×100 with JLC's rails), lead-free HASL",
        "pcb": {"special offer": 8.00, "lead-free HASL": 5.20},
        "pcba": {"setup": 25.75, "stencil": 8.27, "components": 40.41, "feeders": 51.15, "SMT": 2.30,
                 "X-ray": 3.30, "packaging": 0.50, "special components": 0.12},
    },
    # the drawer's DATA port board (v1.0, 2 layers, parts on one side), one per node but the converted bays'
    # (a DATA ×4 instead): six.  JLC's real quote, 2026-10-23 (jlcpcb.com, the user's account, main's d44251a
    # Gerbers, JLC BOM and CPL uploaded with the user's OK): 10 PCBs, all 10 assembled, green, lead-free HASL,
    # Economic PCBA: $40.76.  Economic assembles every PCB of an order, 2 of 5 its one exception
    # (assembled_of()), so the six come with four spares: JLC's form offers 10 of 10 and nothing between (the
    # estimate, 7 of 10, was not orderable).  JLC charges the USB4105 (J1) as a special component ($0.03 a
    # piece), adds its nitrogen reflow, mandatory with Economic PCBA ($0.99), and no deburring with PCBA.
    "data-port": {
        "pcbs": 10, "assembled": 10, "spares": 4, "service": "Economic", "total": 40.76, "date": "2026-10-23",
        "from_fab": True,
        "spec": "2-layer 40×17 mm, lead-free HASL",
        "pcb": {"special offer": 5.00, "lead-free HASL": 1.10},
        "pcba": {"setup": 8.24, "stencil": 1.55, "components": 13.61, "extended parts": 9.27, "SMT": 0.70,
                 "special components": 0.30, "nitrogen reflow": 0.99},
    },
    # the camera pod board (v1.0, 2 layers, one side), one per camera (CAMERA_SETS).  JLC's real quote,
    # 2026-10-23 (as the DATA port's): 5 PCBs, 2 assembled, green, lead-free HASL, Economic PCBA: $27.28, the
    # nitrogen reflow $0.86; three extended types (the S8B, the SMD header, the LED)
    "camera-pod": {
        "pcbs": 5, "assembled": 2, "service": "Economic", "total": 27.28, "date": "2026-10-23", "from_fab": True,
        "spec": "2-layer 40×27 mm, lead-free HASL",
        "pcb": {"special offer": 4.00, "lead-free HASL": 1.10},
        "pcba": {"setup": 8.24, "stencil": 1.55, "components": 2.08, "extended parts": 9.27, "SMT": 0.18,
                 "nitrogen reflow": 0.86},
    },
    # the DATA ×4 (v1.0, 4 layers, parts on one side, no module: Economic PCBA takes 4 layers), NOT ordered for
    # the prototype (the user, 2026-10-20: the converted bays wait for the v2, its base variant below); kept as
    # it was priced: an estimate built like the DATA port's, $3.07 per extended part type (the USB2514B, its
    # crystal, the TPS2553-1, the INA226, the TCA6408A, the AP2112K, the USBLC6, the USB4105, the S8B: 9; the
    # AP2112K stays: the hub burns up to ≈ 0.31 W in it at high speed, above a basic SOT-23 LDO's rating, see
    # docs/electronics.md), components at catalogue prices plus ≈ 3 % attrition, ≈ 430 joints a board, an X-ray of
    # each assembled board (the QFN hub and expanders, $1.64 each).  The bare PCB: 100 mm long since 2026-10-20
    # (100 × 37), so JLC's 4-layer offer with no engineering fee (jlcpcb.com calculator, 2026-10-20: $8.00 +
    # lead-free HASL $5.10, no deburring at 37 mm wide); 108 × 24 cost $31.90 with the $25 fee.  The RESET/BOOT headers are not fitted.
    "data-port-x4": {
        "pcbs": 5, "assembled": 2, "service": "Economic", "total": 85.37, "estimate": True,
        "spec": "4-layer 100×37 mm, JLC04161H-7628, lead-free HASL",
        "pcb": {"special offer": 8.00, "lead-free HASL": 5.10},
        "pcba": {"setup": 8.18, "stencil": 1.53, "components": 30.18, "extended parts": 27.63, "SMT": 1.47,
                 "X-ray": 3.28},
    },
    # the DATA ×4 v2 (electronics/data-port-x4-v2), one PCB in two assemblies.  The logic variant (DATA-4x-logic:
    # the hub and ports plus the CH446Q matrix and the RP2354B analyzer), one per bay showing `x4: v2`, ordered
    # on its own (the rack orders it on the panel below).  The standing board, 100 × 70 mm, 4 layers again
    # (2026-10-23: the Freerouting portfolio routes the High-Speed pairs on F.Cu over GND at 4 layers; the
    # 6-layer build is the alternative), JLC04161H-7628, 0.3 mm vias plugged at no charge, ENIG for the
    # RP2354B's 0.4 mm QFN-80, green (pcb.solder_mask, the user, 2026-10-23: JLC's Economic PCBA takes 4 layers
    # in green only).  An estimate from that day's real quotes (jlcpcb.com, the user's account,
    # the committed Gerbers and the logic's JLC BOM and CPL of 2cd2cc0): the logic's own, in black, so Standard
    # with rails (100 × 80): $193.75 (PCB $33.50 = $8.00 + ENIG $17.50 + black $8.00; setup $25.75, stencil
    # $8.27, 39 types × $1.55 = $60.45, components $60.14, SMT $4.90, packaging $0.50, special components
    # $0.24); its components and joints (SMT × 5.77 / 6.57, the panel's Economic rate over its Standard one)
    # with the panel's green Economic fees ($8.24 setup, $1.55 stencil, $3.09 for each of its 17 extended types,
    # $0.12 special components a board, no packaging); the RP2354B, out of stock at JLC that day, at its $1.52
    # (2 boards, its type among the 17); the board without rails, 100 × 70: $8.00 + ENIG $17.40.  No X-ray
    # line.  L1 (AOTA-B201610S3R3-101-T, the one inductor Raspberry Pi approves for the RP2350's regulator) in
    # stock, bought by 5 (the quote's components carry it: parts_from_quote).  J1 and the four 2 × 6 headers are
    # hand-soldered, out of the JLC BOM.
    "data-port-x4-v2": {
        "pcbs": 5, "assembled": 2, "service": "Economic", "total": 155.45, "estimate": True, "from_fab": True,
        "parts_from_quote": True,
        "spec": "4-layer 100×70 mm, JLC04161H-7628, ENIG",
        "pcb": {"special offer": 8.00, "ENIG": 17.40},
        "pcba": {"setup": 8.24, "stencil": 1.55, "components": 63.19, "extended parts": 52.53, "SMT": 4.30,
                 "special components": 0.24},
    },
    # its base variant (DATA-4x: the logic left off, 91 parts fewer, data-port-x4-v2-base-*), one per other
    # converted bay, ordered on its own: the same green Economic estimate, from its own real quote of 2026-10-23
    # in black, Standard: $128.47 (PCB $21.20 = $8.00 + lead-free HASL $5.20 + black $8.00; setup $25.75,
    # stencil $8.27, 25 types × $1.55 = $38.75, components $31.19, SMT $2.57, packaging $0.50, special components
    # $0.24), every part in stock; 8 extended types among 25 (and C25725, C20615800, preferred).  Lead-free
    # HASL: no part finer than its hub's 0.5 mm QFN.
    "data-port-x4-v2-base": {
        "pcbs": 5, "assembled": 2, "service": "Economic", "total": 81.40, "estimate": True, "from_fab": True,
        "parts_from_quote": True,
        "spec": "4-layer 100×70 mm, JLC04161H-7628, lead-free HASL",
        "pcb": {"special offer": 8.00, "lead-free HASL": 5.20},
        "pcba": {"setup": 8.24, "stencil": 1.55, "components": 31.19, "extended parts": 24.72, "SMT": 2.26,
                 "special components": 0.24},
    },
    # the rack's order for its converted bays (the orchestrator, 2026-10-20): the logic and the base above on
    # one 1 × 2 order panel (electronics/data-port-x4-v2/fab/data-port-x4-v2-panel-*: 100 × 142 mm, the base
    # turned 180°, top edge to top edge on two mouse-bite tabs), one order: one setup and stencil, the logic's
    # part types once (the base's are a subset), both boards' parts bought together at the breaks they reach
    # (panel_order()).  JLC's real quote, 2026-10-23 (jlcpcb.com, the user's account, the panel's committed
    # Gerbers, JLC BOM and CPL of 2cd2cc0 uploaded with the user's OK): 5 panels, 2 assembled, green (the
    # user, 2026-10-23: "Ok, vert", then every board green; pcb.solder_mask), Economic PCBA, no rails: $201.72, 3–4
    # days; the RP2354B (U11, logic) was out of stock at JLC and left unplaced (JLC_SINCE_QUOTE: $207.86 with
    # it, $212.14 with the datasheet audit's fixes of 2026-10-25).  JLC flags the rows that join _L and _B
    # designators ("multiple types of parts?") and leaves them for a tick; no X-ray line.  The alternative, black:
    # Standard PCBA, the only one JLC offers on 4 layers in black, two 5 mm rails (110 × 142 mm): $249.86 (PCB
    # $61.10 = $25 + ENIG $18.40 + black $8.00 + $9.70; setup $25.75, stencil $8.27, 39 types × $1.55 = $60.45,
    # components $86.73, SMT $6.57, packaging $0.51, special components $0.48), $254.46 with the RP2354B: $46.60
    # more an order.
    # One logic and one base per panel; the variants' own estimates above stay for single orders (the BOM
    # page's calculator).
    "data-port-x4-v2-panel": {
        "pcbs": 5, "assembled": 2, "service": "Economic", "total": 201.72, "date": "2026-10-23", "from_fab": True,
        "boards": ("data-port-x4-v2", "data-port-x4-v2-base"),
        "spec": "4-layer 100×142 mm panel of a logic and a base, JLC04161H-7628, ENIG, mouse bites",
        "pcb": {"engineering": 25.00, "ENIG": 18.20, "board": 8.80},
        "pcba": {"setup": 8.24, "stencil": 1.55, "components": 84.24, "extended parts": 49.44, "SMT": 5.77,
                 "special components": 0.48},
    },
}
# A finish the order changes against a board's quote: (finish, USD instead of the quote's ENIG).  None since the
# real quotes of 2026-10-23, which are in the order's finish (the hub's of 2026-10-19 was ENIG).
JLC_FINISH = {}
# What changed on a board after its quote (indicative, not re-quoted): (what, the quote's PCBA or PCB line, USD
# for the quoted order).  The node's and the hub's changes since their estimate and quote of 2026-10-19 lived
# here until their real quotes of 2026-10-23.
JLC_SINCE_QUOTE = {
                   # the v2 panel's quote left the RP2354B (C39843328) unplaced: JLC had none in stock on
                   # 2026-10-23 (2 at its $1.5242 once restocked, a 17th extended type; other users sold theirs
                   # at $2.91)
                   "data-port-x4-v2-panel": [("RP2354B, out of stock at JLC on 2026-10-23: 2 at JLC's price",
                                              "components", 3.05),
                                             ("RP2354B: its extended part type", "extended parts", 3.09),
                                             # the DATA ×4 v2 datasheet audit's fixes (2026-10-25): 12 H5VU25UC
                                             # (preferred, no fee), 2 MAX809S (a new extended type), 1M, 10k,
                                             # 100k, 4.7 µF; the schematic review's D2 (BAT54S) gone again
                                             ("the datasheet audit's fixes: their parts, 2 panels at JLC's price",
                                              "components", 1.19),
                                             ("MAX809S (U5): its extended part type", "extended parts", 3.09)],
                   # the pod's U1 since the quote: the AP2114H-3.3 (C150716, extended, $0.2314) for the AMS1117
                   # (C6186, basic, $0.2048), stable with its ceramic output capacitor (datasheet audit F1)
                   "camera-pod": [("AP2114H-3.3 for the AMS1117 (datasheet audit F1): its extended part type",
                                   "extended parts", 3.09),
                                  ("AP2114H-3.3 for the AMS1117: 2 at JLC's price", "components", 0.05)]}

# JLC's fees, as its real quotes of 2026-10-23 charge them (its help page "PCB Assembly Cost" of 2026-09-09
# still says $25.56 / $8.21 / $1.53 and $8.18 / $1.53 / $3.07) and the jlcpcb.com calculator (2026-10-19,
# 4-layer, 5 PCBs): what a board's part types and size cost per order
JLC_FEES = {
    "Standard": {"setup": 25.75, "stencil": 8.27, "per type": 1.55, "types": "every unique part type"},
    "Economic": {"setup": 8.24, "stencil": 1.55, "per type": 3.09, "types": "extended part types only"},
    "panel": 8.21,              # PCBA of a panel holding more than one design
    "x-ray": 1.64,              # per assembled board with a leadless part (module pad, QFN, LGA), 1-10 boards
    "pcb 4-layer 100x100": 8.00,        # 5 PCBs at JLC's offer: no engineering fee
    "pcb engineering above 100x100": 25.00,     # per order, on any board or panel above 100 × 100 mm ($33 at 6 layers)
    "enig over lf-hasl": 12.40,         # 5 PCBs, 100 × 100 mm: ENIG $17.70, lead-free HASL $5.30
}

# What each order could still save (USD per order, against JLC_QUOTE), kept by the JLC-cost owner.
# "obvious": engineering choices without a trade-off for the user (the board's owner applies them);
# "decision": a trade-off for the user.  A lever applied in a board leaves this list for its quote.
JLC_LEVERS = {
    "power-hub": [
        # rows C and D not fitted: in the real quote of 2026-10-23.  The console USB-C J6 in HRO instead of the GCT
        # saves nothing: the PD input J1 stays GCT, so the HRO is a part type more ($1.55), as much as it saves
        ("JST PH SMD clones instead of JST's S*B / B8B-PH-SM4-TB, no-name ≈ $0.06 (SHOU HAN 2.0-xP WT / LT; "
         "CJT A2001WR / WV at $0.16-0.20 saves about 60 % of this): footprint geometry to check (2 a board, rows "
         "A and B)", 1.33, "decision"),
        ("USBLC6-2SC6 second source (UMW C2687116, same SOT-23-6 and pinout) instead of ST's "
         "C7519", 0.25, "decision"),
    ],
    "bay-node": [
        ("9 assembled instead of 10 (8 bays and 1 spare): eight parts cross back over a price break (the "
         "WROOM-1 alone $0.63 more each), so one board less saves little", 0.84, "decision"),
        ("USB-C J3: HRO TYPE-C-31-M-12 (C165948, 5 A, 20 V) instead of the GCT USB4105: a new footprint, "
         "re-route, mechanical check", 5.37, "decision"),
        ("JST PH SMD clones instead of JST's S*B / B8B-PH-SM4-TB, no-name ≈ $0.06 (SHOU HAN 2.0-xP WT / LT; "
         "CJT A2001WR / WV at $0.16-0.20 saves about 60 % of this): footprint geometry to check (5 a board)", 13.98, "decision"),
        ("USBLC6-2SC6 second source (UMW C2687116, same SOT-23-6 and pinout) instead of ST's C7519 (4 a "
         "board)", 5.04, "decision"),
    ],
    "data-port-x4": [
        ("USB-C J101–J401: HRO TYPE-C-31-M-12 (C165948, 5 A, 20 V) instead of the GCT USB4105: a new "
         "footprint, re-route, mechanical check", 5.88, "decision"),
        ("JST PH SMD clones instead of JST's S*B / B8B-PH-SM4-TB, no-name ≈ $0.06 (SHOU HAN 2.0-xP WT / LT; "
         "CJT A2001WR / WV at $0.16-0.20 saves about 60 % of this): footprint geometry to check", 0.79, "decision"),
        ("USBLC6-2SC6 second source (UMW C2687116, same SOT-23-6 and pinout) instead of ST's C7519 (6 a "
         "board)", 1.51, "decision"),
    ],
    "data-port-x4-v2": [         # declined (2026-10-20, the v2 session): L1 stays the AOTA, the arrays stay
        ("USBLC6-2SC6 second source (UMW C2687116, same SOT-23-6 and pinout) instead of ST's C7519 (4 a "
         "board)", 1.01, "decision"),
    ],
    "data-port-x4-v2-panel": [
        ("USBLC6-2SC6 second source (UMW C2687116, same SOT-23-6 and pinout) instead of ST's C7519 (4 a "
         "board, 8 a panel)", 2.02, "decision"),
    ],
    "data-port-x4-v2-base": [
        ("USBLC6-2SC6 second source (UMW C2687116, same SOT-23-6 and pinout) instead of ST's C7519 (4 a "
         "board)", 1.01, "decision"),
    ],
    "data-port": [
        ("USB-C J1: HRO TYPE-C-31-M-12 (C165948, 5 A, 20 V) instead of the GCT USB4105: a new footprint, "
         "re-route, mechanical check", 5.88, "decision"),
        ("JST PH SMD clones instead of JST's S*B / B8B-PH-SM4-TB, no-name ≈ $0.06 (SHOU HAN 2.0-xP WT / LT; "
         "CJT A2001WR / WV at $0.16-0.20 saves about 60 % of this): footprint geometry to check", 3.16, "decision"),
        ("USBLC6-2SC6 second source (UMW C2687116, same SOT-23-6 and pinout) instead of ST's "
         "C7519", 1.01, "decision"),
    ],
    "camera-pod": [
        ("JST PH SMD clones instead of JST's S*B / B8B-PH-SM4-TB, no-name ≈ $0.06 (SHOU HAN 2.0-xP WT / LT; "
         "CJT A2001WR / WV at $0.16-0.20 saves about 60 % of this): footprint geometry to check", 0.79, "decision"),
    ],
}

# Bare PCB price by quantity (USD, lead-free HASL, JLC's default build), from the jlcpcb.com calculator on
# 2026-10-19.  JLC sells 5, 10, 15, 20, 25, 30, 50, 75, 100… PCBs; in between, interpolated.  The $8 / $4
# offers stop at 10 PCBs, and every size above 100 mm long pays a $25 engineering fee whatever the quantity.
JLC_PCB_PRICE = {
    "bay-node": {5: 13.20, 10: 19.40, 50: 72.80, 100: 108.00},         # 4-layer 74 × 90 mm (10: 84 × 90 with the
                                                                        # rails, the real quote of 2026-10-23)
    "power-hub": {5: 13.20, 10: 19.40, 50: 85.20, 100: 130.70},        # 4-layer 86 × 100 mm with JLC's rails
                                                                        # (2026-10-20): the $25 fee above 10 PCBs
    "data-port-x4": {5: 13.10, 10: 19.20, 50: 53.80, 100: 73.40},      # 4-layer 100 × 37 mm (2026-10-20): the
                                                                        # $25 fee is back above 10 PCBs
    # the DATA ×4 v2, green, Economic: no rails (2026-10-23; in black, Standard, with JLC's rails: 100 × 80 for
    # a single board, $25.50 / $32.40 / $100.30 / $149.70 in ENIG, 110 × 142 for the panel, $53.10 for 5)
    "data-port-x4-v2": {5: 25.40, 10: 32.20, 50: 92.90, 100: 136.20},  # 4-layer 100 × 70 mm, ENIG
    "data-port-x4-v2-base": {5: 13.20, 10: 19.40, 50: 74.90, 100: 111.90},  # the same PCB, lead-free HASL
    # the order panel (electronics/data-port-x4-v2/fab/*-panel-*): a logic and a base on one 100 × 142 mm panel,
    # 4-layer ENIG, mouse bites, one design: no panel fee (2026-10-23, every quantity JLC sells)
    "data-port-x4-v2-panel": {5: 52.00, 10: 62.50, 15: 72.80, 20: 83.30, 25: 93.60, 30: 104.10, 50: 145.60,
                              75: 187.00, 100: 233.50, 125: 280.10, 150: 327.95, 200: 421.15},
    # 2-layer 40 × 17 mm and 40 × 27 mm.  With PCBA, JLC charges no deburring (the real quotes of 2026-10-23:
    # $6.10 for 10 DATA ports, $5.10 for 5 pods): the calculator's $0.10 at 5 and $0.20 at 10 are out; the 50
    # and 100 points still carry it (a few dimes)
    "data-port": {5: 5.10, 10: 6.10, 50: 17.10, 100: 20.90},
    "camera-pod": {5: 5.10, 10: 6.20, 50: 18.80, 100: 24.20},
}
JLC_PCB_QTY = (5, 10, 15, 20, 25, 30, 50, 75, 100, 125, 150, 200)

# Each board's finish in JLC_PCB_PRICE and the other one's bare PCB price (USD, the same sizes, green; jlcpcb.com
# calculator, 2026-10-23), for the BOM page's ENIG / HASL switch.  Only the bare PCB changes, with two limits the
# page shows: Economic PCBA takes 2 layers in black in HASL only (ENIG there wants green, or Standard, which needs
# a panel of 70 × 70 mm or more), and the RP2354B's 0.4 mm QFN-80 wants ENIG (JLC advises against HASL under
# 0.5 mm: solder bridges).
JLC_FINISHES = {
    "bay-node": ("lead-free HASL", "ENIG", {5: 25.40, 10: 32.10, 50: 90.40, 100: 131.70}),
    "power-hub": ("lead-free HASL", "ENIG", {5: 25.60, 10: 32.60, 50: 104.60, 100: 157.90}),
    "data-port": ("lead-free HASL", "ENIG", {5: 20.80, 10: 21.90, 50: 29.30, 100: 33.80}),
    "camera-pod": ("lead-free HASL", "ENIG", {5: 20.80, 10: 22.00, 50: 31.30, 100: 37.80}),
    "data-port-x4-v2": ("ENIG", "lead-free HASL", {5: 13.20, 10: 19.40, 50: 74.90, 100: 111.90}),
    "data-port-x4-v2-base": ("lead-free HASL", "ENIG", {5: 25.40, 10: 32.20, 50: 92.90, 100: 136.20}),
    "data-port-x4-v2-panel": ("ENIG", "lead-free HASL", {5: 39.20, 10: 48.30, 15: 57.40, 20: 66.50, 25: 75.60,
                                                         30: 84.70, 50: 121.10, 75: 156.00, 100: 196.10,
                                                         125: 236.20, 150: 276.60, 200: 357.85}),
}
# X-ray per board with a leadless part (module pad, QFN): by the number of boards assembled
JLC_XRAY = ((10, 1.64), (50, 0.82), (200, 0.49), (500, 0.33))
# the boards JLC X-rays: the hub (the MINI-1's pads under it) and the DATA ×4 v1 (QFNs); the real quotes of
# 2026-10-23 charge the node (the WROOM-1 is castellated) and the v2 none
JLC_XRAY_BOARDS = {"power-hub", "data-port-x4"}
# an assembly variant: its BOM files sit in its PCB's folder, under its own name (electronics/tools/build_board.py)
VARIANT_OF = {"data-port-x4-v2-base": "data-port-x4-v2"}
VOLUME_QTY = (2, 5, 10, 50, 100)            # boards assembled
VOLUME_RACKS = (1, 5, 10)                   # racks built at once, one order
# JLC's catalog for the boards' parts: tier, stock and price breaks (tools/jlc_parts_snapshot.py)
JLC_PARTS_FILE = REPO / "electronics" / "lib" / "jlc_parts.json"
JLC_PARTS = json.loads(JLC_PARTS_FILE.read_text(encoding="utf-8")) if JLC_PARTS_FILE.exists() else {}


# the DATA and camera leads' listing (JST PH 8, "Same direction"); the row cables came from it too until
# 2026-10-21
PH_LEAD_URL = "https://www.aliexpress.com/item/1005008045292937.html"
# The row cables (docs/can.md: one type for feeds and jumpers, pin n ↔ pin 7−n) in 24 AWG since 2026-10-21
# (the user's pick, docs/power-distribution-review.md): JST rates PH's 2 A on 24 AWG only, and no ready-made
# PH 6 cable states 24 AWG in that layout (AliExpress's are 26 AWG or don't say, Pololu's 24 AWG ones are 1:1).
# Built from JST's own pre-crimped leads (SPH-002T-P0.5S at both ends, UL1007 24 AWG, black) clicked into
# PHR-6 housings: no crimping.  They stop at 305 mm, so a longer feed is crimped.  Lead lengths:
ROW_JUMPER_MM = 152                 # bay to bay: 120 mm routed (docs/cabling.md)
ROW_FEED_CM = [30.5, 60, 80]        # power box to rows A, B, C (≈ 0.25 / 0.45 / 0.6 m routed), then D...
# JST's pre-crimped PH leads, by length (mm): part and Digi-Key FR price breaks, EUR (2026-10-21; Mouser FR
# stocks them too).  JST makes 51, 102, 152, 203, 254 and 305 mm, nothing longer.
JST_PH_LEADS = {152: ("ASPHSPH24K152", "455-3082-ND", {1: 0.35, 10: 0.299, 25: 0.2796, 50: 0.266, 100: 0.2533}),
                305: ("ASPHSPH24K305", "455-3083-ND", {1: 0.44, 10: 0.374, 25: 0.35, 50: 0.3334, 100: 0.3175})}


# DUT cables (DATA port → board), per cable type of config/rack.yaml.  Listings found on 2026-10-18;
# AliExpress then asked for a captcha, so variants and the data lines are to be checked on the page.
# A right-angle micro-B or mini-B plug is not reversible, its "up" / "down" naming varies by seller and
# few listings offer both: those boards take a 90° adapter (sold as up / down / left / right sets, keep
# the one whose female faces up) and a cable with a straight micro-B / mini-B plug.
DUT_CABLES = {
    "c-to-c": {"supplier": "AliExpress 1005013255525639 (OLAF, \"double coudé\" C ↔ C, 15 cm)", "unit_eur": 2.5,
               "notes": "both plugs bent across their wide face (up / down, not left / right); USB-C is "
                        "reversible, so either bend works.  Check the listing says data, not charge only"},
    "c-to-micro-b": {"supplier": "AliExpress 2251832791887129 (HOQO, \"to Micro Male\", 25 cm)", "unit_eur": 1.0,
                     "notes": "the micro-B plug stands on the board's 90° adapter; the USB-C end any up / down bend"},
    "c-to-mini-b": {"supplier": "AliExpress 2251832791887129 (HOQO, \"to Mini Male\", 25 cm)", "unit_eur": 1.0,
                    "notes": "the F746G-DISCO's ST-LINK port (CN14) is mini-B, facing the side wall with 49 mm to it: "
                             "the straight mini-B plug fits, no adapter"},
    "c-to-micro-b-straight": {"supplier": "AliExpress (USB-C ↔ micro-B, straight, 15 cm, USB 2.0 data)",
                              "unit_eur": 2.0,
                              "notes": "straight at both ends, a loop over the plate (a converted bay's Pico 2): "
                                       "15 cm takes a seller's ±5 mm, 10 cm would have to be within 3; listing still "
                                       "to pick, check it says data"},
    "c-to-c-straight-20": {"supplier": "AliExpress (USB-C ↔ USB-C, straight, 20 cm, USB 2.0 data)", "unit_eur": 2.0,
                           "notes": "straight at both ends; any short C ↔ C that states data"},
    "c-to-c-straight": {"supplier": "AliExpress (USB-C ↔ USB-C, 15–20 cm, USB 2.0 data, 480 Mbps)", "unit_eur": 2.0,
                        "notes": "straight at both ends; any short C ↔ C that states data (many short ones are "
                                 "charge-only)"},
}


# Cameras bought for a start (the user, 2026-10-18: "initialement je n'inclurai que 2 caméras"),
# whatever the viewer's `cameras` list shows; every bay node keeps J6 and its circuit, so any bay
# can take one later
CAMERA_SETS = 2


def bay_mounts(rack) -> tuple[int, int]:
    """(drawer bays, sled bays): a fixed bay is a sled bay screwed down (config/rack.yaml › population › mount)."""
    ms = [rack.mount(b.id) for b in rack.bays()]
    return ms.count("drawer"), len(ms) - ms.count("drawer")


def _row_cables(rack) -> list[dict]:
    """The row cables (ROW_FEED_CM): a jumper between neighbouring bays, a feed from the power box to each row's
    first bay (row k gets ROW_FEED_CM[k], the last one beyond).  JST's pre-crimped leads where one is long
    enough (JST_PH_LEADS), six a cable; a longer feed crimped; red and black housings (docs/cabling.md)."""
    jumpers = sum(rack.units - 1 for _ in rack.rows)
    feeds = [ROW_FEED_CM[min(k, len(ROW_FEED_CM) - 1)] for k in range(len(rack.rows))]
    rows = [r["id"] for r in rack.rows]
    lead_mm = max(JST_PH_LEADS)
    short = [r for r, cm in zip(rows, feeds) if cm * 10 <= lead_mm]
    long_ = [(r, cm) for r, cm in zip(rows, feeds) if cm * 10 > lead_mm]
    cables = jumpers + len(feeds)

    def lead(mm, n, spares, what):
        part, dk, breaks = JST_PH_LEADS[mm]
        qty = 6 * n + spares
        eur = breaks[max(q for q in breaks if q <= qty)]
        return {"category": "Cables", "item": f"JST PH pre-crimped lead {part}, {mm} mm, 24 AWG UL1007, "
                                              f"SPH-002T-P0.5S at both ends (row cables: {what}, 6 a cable)",
                "supplier": f"Digi-Key FR {dk} (or Mouser FR)", "qty": qty, "unit_eur": eur,
                "notes": f"{n} × 6 and {spares} spares; JST's own leads, so the gauge is right.  Digi-Key FR "
                         f"delivers free from €75: order with something else, or pay its shipping"}

    out = [lead(152, jumpers, 4, f"the {jumpers} bay-to-bay jumpers")]
    if short:
        out.append(lead(305, len(short), 2, f"the feed to row {', '.join(short)}"))
    out += [
        {"category": "Cables", "item": "JST PH 6-pin housing PHR-6-R, red: a row cable's IN end (the node's J1)",
         "supplier": "LCSC C495652", "qty": cables + 2, "unit_eur": round(0.049 * USD_EUR, 4),
         "notes": f"{cables} cables and 2 spares; the cable works either way round, the colours only make it "
                  "readable (docs/cabling.md)"},
        {"category": "Cables", "item": "JST PH 6-pin housing PHR-6-BK, black: a row cable's OUT end (the node's J2, "
                                      "the hub's row outputs)",
         "supplier": "LCSC C495651", "qty": cables + 2, "unit_eur": round(0.043 * USD_EUR, 4),
         "notes": f"{cables} cables and 2 spares"},
    ]
    if long_:                                   # beyond JST's 305 mm: crimped
        wire_m = sum(6 * (cm + 4) / 100 for _, cm in long_)
        feeds_txt = ", ".join(f"row {r} ({cm:g} cm)" for r, cm in long_)
        out += [
            {"category": "Cables", "item": "JST PH crimp contact SPH-002T-P0.5S, 24–30 AWG, insulation Ø 0.8–1.5 mm "
                                          f"(the feeds JST's leads don't reach: {feeds_txt})",
             "supplier": "LCSC C111515", "qty": math.ceil(12 * len(long_) * 2 / 50) * 50,
             "unit_eur": round(0.009 * USD_EUR, 4),
             "notes": "12 a feed, as many again to learn on: the first crimps go wrong"},
            {"category": "Cables", "item": "Wire, 24 AWG stranded, UL1007 (Ø ≈ 1.4 mm, within the contact's 1.5), "
                                          "black, 10 m (the crimped feeds)",
             "supplier": "AliExpress (UL1007 24AWG)", "qty": 1, "unit": "spool", "unit_eur": 4.0,
             "notes": f"≈ {wire_m:.1f} m.  On arrival, strip one end, count the strands and measure one: 24 AWG "
                      "is 7 × 0.20 mm, 11 × 0.16 or 19 × 0.12 (≈ 0.21 mm²); 7 × 0.16 is 26 AWG"},
            {"category": "Cables", "item": "Crimper for open-barrel contacts, 28–18 AWG (the crimped feeds' contacts)",
             "supplier": "IWISS SN-28B (or Engineer PA-09, ≈ €40)", "qty": 1, "unit_eur": 20.0,
             "notes": f"a tool, bought once, for {12 * len(long_)} contacts: the cheap ratchet one does, with a few "
                      "practice crimps; the Engineer makes neater PH crimps if more cables come"},
        ]
    return out


def _tier(lcsc: str, basic: bool) -> str:
    """A part's JLC tier: basic, preferred (preferred extended: Economic PCBA loads it free, as a basic
    part) or extended, from JLC's parts library (jlc_parts.json), else the catalogue's basic flag."""
    return (JLC_PARTS.get("parts", {}).get(lcsc) or {}).get("tier") or ("basic" if basic else "extended")


def _catalog_prices() -> dict:
    """MPN → (unit USD, LCSC, basic, JLC Standard-PCBA only, hand-soldered) from the electronics
    catalogue and passive cache."""
    try:
        import catalog
    except Exception:  # pragma: no cover
        return {}
    out = {c.mpn: (c.price, c.lcsc, c.basic, c.standard_only, c.hand_solder) for c in catalog.CAT.values()}
    cache = REPO / "electronics" / "lib" / "passives.json"
    if cache.exists():
        for hit in json.loads(cache.read_text(encoding="utf-8")).values():
            if hit:
                out[hit["mpn"]] = (hit.get("price") or 0.0, hit["lcsc"], True, False, False)
    return out


def _usd(fees: dict) -> str:
    return ", ".join(f"{k} ${v:.2f}" for k, v in fees.items())


# JLC's price for a solder mask other than green (config/rack.yaml › pcb.solder_mask), by layer count: free on 2
# layers (a day more to build), $8.00 an order on 4 (jlcpcb.com calculator, 2026-10-21, black, 5 PCBs ≤ 100 × 100 mm,
# the same 3–4 days; again on 2026-10-23 for 100 × 70 and the 100 × 142 panel, 5 to 20 PCBs: flat per order),
# $33.10 on 6 (2026-10-22, black, 100 × 70 and 100 × 142 mm, 5 to 20 PCBs: flat per order)
JLC_MASK_COLOUR = {2: 0.00, 4: 8.00, 6: 33.10}


def mask_colour(name: str) -> dict:
    """JLC's line for a board's solder mask on one order of it or its panel (config/rack.yaml ›
    pcb.<board>.solder_mask, else pcb.solder_mask: rackcfg.Rack.solder_mask), paid once per order whatever the
    quantity; none for green or where JLC charges nothing."""
    mask = rackcfg.load().solder_mask(name)
    usd = JLC_MASK_COLOUR.get(_layers(name), 8.00) if mask != "green" else 0.0
    return {f"{mask} solder mask": usd} if usd else {}


def _layers(name: str) -> int:
    """A board's copper layers (config/rack.yaml › pcb), its assembly variants and panel the board's."""
    key = name.removesuffix("-panel").removesuffix("-base").replace("-", "_")
    return int(rackcfg.load().raw["pcb"].get(key, {}).get("layers", 2))


def jlc_order(name: str, ext: set, hand: set) -> tuple[dict, dict, list[str]]:
    """The quoted PCB and PCBA lines of one board, adjusted for JLC_FINISH, for the rack's solder mask colour
    and for the hand-soldered parts (`hand`) among its extended part types (`ext`)."""
    q = JLC_QUOTE[name]
    pcb, pcba, changes = dict(q["pcb"]), dict(q["pcba"]), []
    for line, usd in mask_colour(name).items():
        pcb[line] = usd
        changes.append(f"{line} on {_layers(name)} layers (+${usd:.2f})")
    if name in JLC_FINISH:
        finish, usd = JLC_FINISH[name]
        changes.append(f"{finish} ≈ ${usd:.2f} instead of ENIG ${pcb['ENIG']:.2f}")
        pcb = {(finish if k == "ENIG" else k): (usd if k == "ENIG" else v) for k, v in pcb.items()}
    if hand and not q.get("from_fab"):            # a quote from the fab files already leaves them out
        fee = "feeders" if "feeders" in pcba else "extended parts"
        cut = round(pcba[fee] * len(hand & ext) / len(ext), 2)
        pcba[fee] = round(pcba[fee] - cut, 2)
        changes.append(f"{fee} −${cut:.2f} ({len(hand & ext)} of {len(ext)} extended part types hand-soldered)")
    # the quote's hand-soldering line was for the through-hole connectors: JLC solders none any more
    # (the hub's are hand-soldered, the node's are SMD since rev 0.4)
    if "hand soldering" in pcba:
        changes.append(f"no through-hole part for JLC (hand soldering −${pcba.pop('hand soldering'):.2f})")
    for what, line, usd in JLC_SINCE_QUOTE.get(name, []):
        fees = pcba if line in pcba else pcb           # a PCBA line, or one of the bare PCB's
        fees[line] = round(fees[line] + usd, 2)
        if not fees[line]:
            del fees[line]                             # a line the change took off entirely
        changes.append(f"{what} ({'+' if usd >= 0 else '−'}${abs(usd):.2f} {line})")
    return pcb, pcba, changes


def electronics(rack) -> tuple[list[dict], dict]:
    """Per-part lines at catalogue prices for the boards JLC assembles, plus the quote's PCB and
    PCBA fees as adjusted by jlc_order(); a last line per board brings the parts up to the quote's
    components figure.  Also returns the adjusted order per board."""
    prices = _catalog_prices()
    n_nodes = rack.units * len(rack.rows)          # every carrier unit gets a node (double bays: 2nd is optional)
    n_x4 = sum(1 for b in rack.bays() if rack.is_multi(b.id))     # converted bays: a DATA ×4, no DATA port
    n_v2 = sum(1 for b in rack.bays() if rack.is_multi(b.id)        # those showing the v2 (`x4: v2`) take its
               and (rack.raw.get("population", {}).get(b.id) or {}).get("x4") == "v2")   # logic variant, the
    rows, orders = [], {}                                              # others its base (v1 is not ordered)
    n_panel = min(n_v2, n_x4 - n_v2)                                  # a logic and a base per order panel
    for name, need in (("bay-node", n_nodes), ("power-hub", 1), ("data-port", n_nodes - n_x4),
                       ("camera-pod", CAMERA_SETS), ("data-port-x4-v2-panel", n_panel),
                       ("data-port-x4-v2", n_v2 - n_panel), ("data-port-x4-v2-base", n_x4 - n_v2 - n_panel)):
        if not need:
            continue
        q = JLC_QUOTE[name]
        assert abs(sum(q["pcb"].values()) + sum(q["pcba"].values()) - q["total"]) < 0.005, f"{name}: quote lines ≠ total"
        n = q["assembled"]
        if n < need or n > max(need + q.get("spares", 0), 2):     # JLC assembles at least 2 boards
            print(f"warning: the JLC quote assembles {n} × {name} but the configuration needs {need}: re-quote")
        paths = {b: REPO / "electronics" / VARIANT_OF.get(b, b) / f"{b}-bom.csv" for b in q.get("boards", (name,))}
        if not all(path.exists() for path in paths.values()):
            rows.append({"category": "Electronics", "group": name, "item": f"{name} BOM missing — run tools/kicad.sh {name} --fab",
                         "qty": 0, "unit_eur": 0})
            continue
        mine = []
        for board, path in paths.items():                # an order panel: each board's lines, as many as panels
            for r in csv.DictReader(path.read_text(encoding="utf-8").splitlines()):
                if r.get("DNP"):
                    continue
                usd, lcsc, basic, std_only, hand = prices.get(r["MPN"], (0.0, r.get("LCSC", ""), False, False, False))
                mine.append({"category": "Electronics", "group": board, "item": f"{r['Value']} — {r['Description'] or r['MPN']}",
                             "ref": r["Designator"], "mpn": r["MPN"], "manufacturer": r["Manufacturer"],
                             "supplier": "LCSC (hand-solder, buy loose)" if hand else "LCSC/JLCPCB",
                             "part": r.get("LCSC", "") or lcsc, "qty": int(r["Qty"]) * n,
                             "unit_eur": round(usd * USD_EUR, 4), "basic": basic, "standard_only": std_only,
                             "hand_solder": hand,
                             "notes": f"{r['Qty']} per board × {n} boards" + ("; hand-solder, buy loose (LCSC)" if hand else "")
                                      + (f"; alternative: {r['Alternative']}" if r.get("Alternative") else "")})
        rows += mine
        pcb, pcba, changes = jlc_order(name, {r["mpn"] for r in mine if not r["basic"]},
                                       {r["mpn"] for r in mine if r["hand_solder"]})
        jlc = {r["part"]: _tier(r["part"], r["basic"]) for r in mine if r["part"] and not r["hand_solder"]}
        unit = "panels" if "boards" in q else "boards"
        n_ext = sum(1 for tier in jlc.values() if tier == "extended")   # the types Economic PCBA charges
        orders[name] = {"pcb": pcb, "pcba": pcba, "changes": changes,
                        "total": round(sum(pcb.values()) + sum(pcba.values()), 2),
                        "need": need, "types": len(jlc), "extended": n_ext,
                        "preferred": sum(1 for tier in jlc.values() if tier == "preferred"),
                        "standard_only": sorted({r["mpn"] for r in mine if r.get("standard_only")})}
        if q["service"] == "Economic" and "extended parts" in pcba and \
                abs(pcba["extended parts"] - n_ext * JLC_FEES["Economic"]["per type"]) > 0.01:
            print(f"warning: {name}'s quote charges ${pcba['extended parts']:.2f} for extended types, but its BOM has "
                  f"{n_ext} (${n_ext * JLC_FEES['Economic']['per type']:.2f}): re-quote")
        for lcsc in jlc:                                 # a JLC minimum purchase the quote doesn't carry
            moq = (JLC_PARTS.get("parts", {}).get(lcsc) or {}).get("min_buy", 1)
            if moq > n * sum(_per_board_qty(b, lcsc) for b in q.get("boards", (name,))) and \
                    all(lcsc != l for b in q.get("boards", (name,)) for l, _, _ in JLC_MIN_BUY.get(b, [])):
                print(f"warning: JLC sells {lcsc} ({name}) by {moq} at least: add it to JLC_MIN_BUY")
        src = "estimate, not quoted" if q.get("estimate") else f"JLCPCB quote {q.get('date', JLC_QUOTE_DATE)}"
        pcb_src = src + (", adjusted" if name in JLC_FINISH or pcb != q["pcb"] else "")
        pcba_src = src + (", adjusted" if pcba != q["pcba"] else "")
        spec = q["spec"].replace("ENIG", JLC_FINISH[name][0]) if name in JLC_FINISH else q["spec"]
        rows.append({"category": "Electronics", "group": name, "item": f"Bare PCB {name} ({spec})",
                     "supplier": pcb_src, "qty": q["pcbs"], "unit_eur": round(sum(pcb.values()) * USD_EUR / q["pcbs"], 4),
                     "notes": f"{_usd(pcb)} = ${sum(pcb.values()):.2f} for {q['pcbs']} {'panels' if 'boards' in q else 'PCBs'}, "
                              f"{n} of them assembled"
                              + "".join(f"; {c}" for c in changes if "ENIG" in c)})
        std = sorted({r["mpn"] for r in mine if r.get("standard_only")})
        if std and q["service"] != "Standard":
            print(f"warning: {name} has Standard-only parts ({', '.join(std)}) but was quoted {q['service']} PCBA")
        fees = {k: v for k, v in pcba.items() if k != "components"}
        rows.append({"category": "Electronics", "group": name,
                     "item": f"{q['service']} PCBA, {n} {unit}: {', '.join(fees)}",
                     "supplier": pcba_src, "qty": 1, "unit_eur": round(sum(fees.values()) * USD_EUR, 2),
                     "notes": _usd(fees) + "".join(f"; {c}" for c in changes if "ENIG" not in c)
                              + (f"; Standard because {', '.join(std)} cannot be placed with Economic PCBA" if std else "")})
        # the quoted components include the connectors JLC no longer buys; they reappear above at
        # catalogue prices (bought loose), so the difference stays quote minus all catalogue lines
        parts_eur = sum(round(r["qty"] * r["unit_eur"], 2) for r in mine)
        quoted_eur = pcba["components"] * USD_EUR
        rows.append({"category": "Electronics", "group": name,
                     "item": f"Components {name}: JLC quote minus the catalogue prices above",
                     "supplier": pcba_src, "qty": 1, "unit_eur": round(quoted_eur - parts_eur, 2),
                     "notes": f"quoted components ${q['pcba']['components']:.2f}"
                              + (f" {'+' if d >= 0 else '−'} ${abs(d):.2f} since"
                                 if (d := round(pcba["components"] - q["pcba"]["components"], 2)) else "")
                              + f" (≈ €{quoted_eur:.2f}) for {n} {unit}; catalogue unit prices give €{parts_eur:.2f}"})
    rows.append({"category": "Electronics", "group": "jlc", "item": "JLCPCB shipping: every board in one cart",
                 "supplier": "JLCPCB", "qty": 1, "unit_eur": round(JLC_SHIPPING_USD * USD_EUR, 2),
                 "notes": f"{JLC_SHIPPING} for the whole order (one shipment); import VAT extra"})
    return rows, orders


# PCBA lines that grow with the boards assembled (and Global Sourcing); JLC charges a special component
# (hard to process: the USB4105, the RP2354B) a piece
PER_BOARD = ("components", "SMT", "X-ray", "special components")


def jlc_cost(orders: dict) -> list[dict]:
    """Per board: what its order spends once (PCB, setup, stencil, part types…) against per board
    assembled (parts, joints, X-ray), what its part types cost at today's fees, and the order after
    the obvious levers and after the user's decisions (JLC_LEVERS)."""
    out = []
    for name, o in orders.items():
        q = JLC_QUOTE[name]
        fees = JLC_FEES[q["service"]]
        per_board = sum(v for k, v in o["pcba"].items() if k in PER_BOARD or "sourcing" in k)
        levers = JLC_LEVERS.get(name, [])
        obvious = sum(usd for _, usd, kind in levers if kind == "obvious")
        decided = sum(usd for _, usd, kind in levers if kind == "decision")
        n_fee = o["types"] if q["service"] == "Standard" else o["extended"]
        out.append({"board": name, "service": q["service"], "standard_only": o["standard_only"],
                    "need": o["need"], "assembled": q["assembled"], "pcbs": q["pcbs"],
                    "types": o["types"], "extended": o["extended"], "preferred": o.get("preferred", 0),
                    "type_fee": round(n_fee * fees["per type"], 2),
                    "once": round(o["total"] - per_board, 2), "per_board": round(per_board, 2),
                    "total": o["total"], "after_obvious": round(o["total"] - obvious, 2),
                    "after_decisions": round(o["total"] - obvious - decided, 2),
                    "levers": [{"lever": t, "usd": usd, "kind": kind} for t, usd, kind in levers]})
    return out


def jlc_cost_md(cost: list[dict]) -> list[str]:
    std, eco = JLC_FEES["Standard"], JLC_FEES["Economic"]
    v2_pcb = JLC_QUOTE["data-port-x4-v2-panel"]["pcb"]   # the order above 100 × 100 mm
    md = ["## JLC cost", "",
          "What each order pays once, whatever the number of boards, against what grows with the boards "
          "assembled (USD, the orders above).  JLC's fees (help page of 2026-09-09): **Standard** PCBA "
          f"${std['setup']:.2f} setup + ${std['stencil']:.2f} stencil + ${std['per type']:.2f} per unique part type, "
          f"basic or extended; **Economic** PCBA ${eco['setup']:.2f} + ${eco['stencil']:.2f} + ${eco['per type']:.2f} per "
          f"*extended* type (basic and preferred-extended types are free); X-ray ${JLC_FEES['x-ray']:.2f} per board with a leadless part.  A "
          "board takes Standard when one of its parts is Standard-only (every ESP32-S3 module, the WS2812B-2020), "
          "or when its mask is not green on 4 layers or more: Economic takes black on 2 layers only, in HASL "
          "(jlcpcb.com/capabilities/pcb-assembly-capabilities, 2026-10-23).  "
          f"A 4-layer board within 100 × 100 mm costs ${JLC_FEES['pcb 4-layer 100x100']:.2f} for 5 PCBs; above "
          f"100 × 100 mm, a ${JLC_FEES['pcb engineering above 100x100']:.0f} engineering fee comes on top: the v2 "
          f"order panel (100 × 142 mm) pays ${v2_pcb['engineering']:.2f} + ${v2_pcb['board']:.2f} "
          f"for 5, before its finish.  ENIG adds "
          f"${JLC_FEES['enig over lf-hasl']:.2f} over lead-free HASL.  A panel of different designs pays "
          f"${JLC_FEES['panel']:.2f} more at PCBA and a fee at PCB.  "
          "Every board goes in one cart: one shipment for the lot "
          f"(${JLC_SHIPPING_USD:.0f}), the only cost the designs share.  With one cart, a DATA port + camera pod "
          "panel would save at most ≈ $6: one setup, one stencil, the S8B's feeder and one bare-PCB line "
          "(≈ $15) less the $8.21 panel fee, before JLC's different-design fee at PCB; not worth a panel that "
          "must carry 7 ports for 2 pods.", "",
          "| Board | PCBA | Needed / assembled | Part types (extended) | Type fees | Once per order | With the boards | Today "
          "| After obvious levers | After decisions |",
          "|---|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for c in cost:
        why = f" ({', '.join(c['standard_only'])})" if c["service"] == "Standard" and c["standard_only"] else ""
        md.append(f"| {c['board']} | {c['service']}{why} | {c['need']} / {c['assembled']} | "
                  f"{c['types']} ({c['extended']}{' + ' + str(c['preferred']) + ' pref.' if c['preferred'] else ''}) | {c['type_fee']:.2f} | {c['once']:.2f} | {c['per_board']:.2f} | "
                  f"**{c['total']:.2f}** | {c['after_obvious']:.2f} | {c['after_decisions']:.2f} |")
    t = {k: sum(c[k] for c in cost) + JLC_SHIPPING_USD for k in ("total", "after_obvious", "after_decisions")}
    md.append(f"| shipping | one cart, DHL | | | | {JLC_SHIPPING_USD:.2f} | | {JLC_SHIPPING_USD:.2f} | "
              f"{JLC_SHIPPING_USD:.2f} | {JLC_SHIPPING_USD:.2f} |")
    md.append(f"| **All** | | | | | | | **{t['total']:.2f}** | **{t['after_obvious']:.2f}** | "
              f"**{t['after_decisions']:.2f}** |")
    md += ["", "Levers (*obvious*: an engineering choice the board's owner applies; *decision*: the user's):", "",
           "| Board | Lever | USD | Kind |", "|---|---|---:|---|"]
    md += [f"| {c['board']} | {lv['lever']} | {lv['usd']:.2f} | {lv['kind']} |" for c in cost for lv in c["levers"]]
    return md


def pcb_price(name: str, n: int, table: dict | None = None) -> tuple[int, float]:
    """(PCBs bought, USD) for n boards: JLC's next quantity, priced from JLC_PCB_PRICE (or `table`,
    another finish's prices), interpolated."""
    q = next(x for x in JLC_PCB_QTY if x >= max(n, 5))
    pts = sorted((table or JLC_PCB_PRICE[name]).items())
    for (q0, p0), (q1, p1) in zip(pts, pts[1:]):
        if q <= q1:
            return q, round(p0 + (p1 - p0) * (q - q0) / (q1 - q0), 2)
    (q0, p0), (q1, p1) = pts[-2], pts[-1]                # beyond 100: the last slope
    return q, round(p1 + (p1 - p0) * (q - q1) / (q1 - q0), 2)


def xray(n: int) -> float:
    return next(usd for top, usd in JLC_XRAY if n <= top)


def part_price(lcsc: str, qty: int) -> float | None:
    """Unit price at the break `qty` reaches (below the first break: the first, with its MOQ)."""
    breaks = (JLC_PARTS.get("parts", {}).get(lcsc) or {}).get("priceBreaks") or []
    for b in breaks:
        if b["qFrom"] <= qty and (b["qTo"] is None or qty <= b["qTo"]):
            return b["price"]
    return breaks[0]["price"] if breaks else None


def parts_scale(name: str, n: int) -> float:
    """How the parts of n boards cost against the quoted order's, at JLC's price breaks: the quote's
    components figure (JLC's markup and attrition included) scales by this ratio.  Parts JLC holds no
    stock of (Global Sourcing) and parts without prices keep today's price."""
    rows = JLC_PARTS.get("boards", {}).get(name)
    if not rows:
        return 1.0
    k = JLC_QUOTE[name]["assembled"]
    now = then = 0.0
    for lcsc, q, _ in rows:
        if not (JLC_PARTS["parts"].get(lcsc) or {}).get("stock"):
            continue
        p0, p1 = part_price(lcsc, q * k), part_price(lcsc, q * n)
        if p0 is None or p1 is None:
            continue
        now, then = now + q * p0, then + q * p1
    return then / now if now else 1.0


JLC_PARTS_MARKUP = 1.12                     # JLC's part prices and attrition against the catalogue's (the node's quote)
# parts JLC sells by a minimum quantity: what the boards don't use is bought once per order (board → LCSC,
# minimum, the PCBA line it lands on)
# L1 (C42411119): JLC's PCBA quote of 2026-10-23 buys 5 for 2 boards (its library lists 26 to buy into a
# parts library; 32 and a pre-order on 2026-10-20, 197 in stock on 2026-10-23)
JLC_MIN_BUY = {"data-port-x4-v2": [("C42411119", 5, "L1 minimum purchase (5)")]}
# an order panel: one PCB carrying one board of each design, one PCBA order (panel_order)
PANELS = {"data-port-x4-v2-panel": ("data-port-x4-v2", "data-port-x4-v2-base")}


def _pcba(name: str, orders: dict) -> dict:
    """A board's PCBA lines: as adjusted for the rack's order, or its quote's when it is not in it (an
    order panel's boards), with what JLC_SINCE_QUOTE changes on them (a part the quote left unplaced)."""
    if name in orders:
        return orders[name]["pcba"]
    pcba = dict(JLC_QUOTE[name]["pcba"])
    for _, line, usd in JLC_SINCE_QUOTE.get(name, []):
        if line in pcba:
            pcba[line] = round(pcba[line] + usd, 2)
    return pcba


def _per_board_qty(name: str, lcsc: str) -> int:
    return sum(q for l, q, _ in JLC_PARTS.get("boards", {}).get(name, []) if l == lcsc)


def _min_buy(lcsc: str, moq: int, used: int) -> float:
    """USD for the parts of a minimum purchase the boards don't use."""
    return round(max(0, moq - used) * (part_price(lcsc, used) or 0.0) * JLC_PARTS_MARKUP, 2)


def assembled_of(service: str, n: int, pcbs: int) -> int:
    """Boards JLC assembles when n are wanted out of `pcbs` PCBs: at least 2, and Economic PCBA assembles every
    PCB of the order, 2 of 5 its one exception (jlcpcb.com's form, 2026-10-23: 5 PCBs offer 5 or 2, 10 only
    10, 15 only 15).  Standard takes any number (the node's 16 of 20, 2026-10-16)."""
    m = max(n, 2)
    return m if service != "Economic" or (pcbs == 5 and m == 2) else pcbs


def order_cost(name: str, n: int, orders: dict) -> dict:
    """One JLC order of n boards of one design (JLC assembles at least 2), from its quote as adjusted
    (`orders`, electronics()): the PCBA lines paid once (setup, stencil, part types, packaging, a
    minimum purchase's spares, Global Sourcing's $3, the rack's mask colour), per board its parts (the quote's, scaled to JLC's
    price breaks at that quantity, parts_scale), joints, X-ray and Global Sourcing, and the bare PCBs
    at JLC's price for that quantity (the engineering fee is in it)."""
    if name in PANELS:
        return panel_order(n, orders, name)
    q, pcba = JLC_QUOTE[name], _pcba(name, orders)
    pcbs, pcb = pcb_price(name, max(n, 2))
    k, m = q["assembled"], assembled_of(q["service"], n, pcbs)
    once = {key: v for key, v in pcba.items() if key not in PER_BOARD and "sourcing" not in key}
    from_snapshot = q.get("estimate", False) and not q.get("parts_from_quote")
    for lcsc, moq, line in JLC_MIN_BUY.get(name, []) if from_snapshot else ():
        once[line] = _min_buy(lcsc, moq, _per_board_qty(name, lcsc) * m)    # a real quote's parts carry them
    once.update(mask_colour(name))
    sourcing = sum(v for key, v in pcba.items() if "sourcing" in key)
    if sourcing:
        once["Global Sourcing"] = 3.0                   # ≈ $3 once, the rest per part bought
    each = {"parts": pcba["components"] / k * parts_scale(name, m), "joints": pcba.get("SMT", 0) / k,
            "x-ray": xray(m) if name in JLC_XRAY_BOARDS else 0.0}
    if pcba.get("special components"):
        each["special components"] = pcba["special components"] / k
    if sourcing:
        each["sourcing"] = (sourcing - 3.0) / q.get("gs_parts", q["pcbs"])
    total = sum(once.values()) + m * sum(each.values()) + pcb
    return {"board": name, "boards": n, "assembled": m, "pcbs": pcbs, "pcb": pcb,
            "once": round(sum(once.values()), 2), "once_lines": {key: round(v, 2) for key, v in once.items()},
            "per_board": {key: round(v, 4) for key, v in each.items()}, "total": round(total, 2)}


def panel_order(n: int, orders: dict, panel: str = "data-port-x4-v2-panel") -> dict:
    """One JLC order of n order panels (PANELS: one board of each design per panel, n of each; JLC
    assembles at least 2 panels): the panel quote's lines paid once (setup, stencil, part types loaded
    once, packaging), the parts of both boards bought together at the breaks they reach, the panel's
    joints, X-ray where JLC charges it (at the tier of all the boards assembled), the bare panels."""
    first, second = PANELS[panel]
    q = JLC_QUOTE[panel]
    pcbs, pcb = pcb_price(panel, max(n, 2))
    m = assembled_of(q["service"], n, pcbs)
    lines = {line for b in (first, second) for _, _, line in JLC_MIN_BUY.get(b, [])}
    once = {key: v for key, v in _pcba(panel, orders).items() if key not in PER_BOARD and key not in lines}
    per_panel = Counter()
    for name in (first, second):
        for lcsc, k, _ in JLC_PARTS.get("boards", {}).get(name, []):
            per_panel[lcsc] += k

    def snapshot(k: int) -> float:                  # the parts of k panels at the snapshot's breaks
        return JLC_PARTS_MARKUP * sum(v * k * (part_price(lcsc, v * k) or 0.0) for lcsc, v in per_panel.items())

    if q.get("estimate", False):                    # an estimate: the snapshot's prices, the minimum buys added
        parts = snapshot(m)
        for name in (first, second):
            for lcsc, moq, line in JLC_MIN_BUY.get(name, []):
                once[line] = _min_buy(lcsc, moq, per_panel[lcsc] * m)
    else:                                           # a real quote: its components (JLC's own purchase, minimum
        parts = _pcba(panel, orders)["components"] * snapshot(m) / snapshot(q["assembled"])   # buys in), scaled
    once.update(mask_colour(panel))
    joints = _pcba(panel, orders).get("SMT", 0) / JLC_QUOTE[panel]["assembled"] * m      # the panel's own quote
    special = _pcba(panel, orders).get("special components", 0) / JLC_QUOTE[panel]["assembled"] * m
    xr = xray(2 * m) * 2 * m if {first, second} & JLC_XRAY_BOARDS else 0.0
    total = sum(once.values()) + parts + joints + special + xr + pcb
    return {"board": panel, "boards": n, "assembled": m, "pcbs": pcbs, "pcb": pcb,
            "once": round(sum(once.values()), 2), "once_lines": {key: round(v, 2) for key, v in once.items()},
            "parts": round(parts, 2), "joints": round(joints, 2), "special components": round(special, 2),
            "x-ray": round(xr, 2),
            "per_board": {"parts": round(parts / m, 4), "joints": round(joints / m, 4), "x-ray": round(xr / m, 4)},
            "total": round(total, 2)}


CALC_N = tuple(range(1, 101)) + (150, 200)


def calculator(orders: dict) -> dict:
    """The order total of every orderable board and order panel for n = CALC_N boards or panels
    (site/assets/bom.json › calculator, the BOM page's quantity calculator), without shipping.
    `design`: the orders made on the same PCB, so the page can warn when a panel and single orders of
    its boards are mixed."""
    names = list(orders) + [b for p in PANELS if p in orders for b in PANELS[p] if b not in orders]
    names += [p for p, boards in PANELS.items() if p not in orders and all(b in orders for b in boards)]
    out = {name: [order_cost(name, n, orders) for n in CALC_N] for name in names}
    design = defaultdict(list)
    for name in out:
        design[VARIANT_OF.get(name, PANELS.get(name, (name,))[0])].append(name)
    finish = {name: {"now": JLC_FINISHES[name][0], "alt": JLC_FINISHES[name][1],
                     "total": [round(o["total"] - o["pcb"] + pcb_price(name, o["assembled"], JLC_FINISHES[name][2])[1], 2)
                               for o in os]}
              for name, os in out.items() if name in JLC_FINISHES}
    return {"currency": "USD", "usd_eur": USD_EUR, "shipping_usd": JLC_SHIPPING_USD, "n": list(CALC_N),
            "min_assembled": 2,
            # per n: the order's total, the PCBs bought and the boards JLC assembles (Economic: the whole lot,
            # 2 of 5 its one exception; assembled_of())
            "orders": {name: {"total": [o["total"] for o in os], "pcbs": [o["pcbs"] for o in os],
                              "assembled": [o["assembled"] for o in os]}
                       for name, os in out.items()},
            "finish": finish,
            "panels": {panel: list(boards) for panel, boards in PANELS.items() if panel in out},
            "design": {d: names for d, names in design.items() if len(names) > 1}}


def volume(orders: dict) -> dict:
    """The order of n boards of each design (order_cost) at VOLUME_QTY, the floor per board, and the
    rack's orders at VOLUME_RACKS."""
    def order(name: str, n: int) -> float:
        return order_cost(name, n, orders)["total"]

    unit = {name: {n: round(order(name, n) / n, 2) for n in VOLUME_QTY} for name in orders}
    # what a board costs once the fees per order are spread thin: its parts at the 100-board breaks,
    # joints, X-ray and PCB per board
    floor = {name: round(sum(order_cost(name, 100, orders)["per_board"].values())
                         + JLC_PCB_PRICE[name][100] / 100, 2) for name in orders}
    racks = {}
    for r in VOLUME_RACKS:
        lines = {name: round(order(name, o["need"] * r), 2) for name, o in orders.items()}
        racks[r] = {"boards": lines, "shipping": JLC_SHIPPING_USD,
                    "per_rack": round((sum(lines.values()) + JLC_SHIPPING_USD) / r, 2)}
    return {"unit": unit, "floor": floor, "racks": racks}


def volume_md(vol: dict, orders: dict) -> list[str]:
    md = ["### At volume", "",
          "Unit cost (USD) of a board for n assembled in one order: the fees per order spread over n; the "
          "parts at JLC's price breaks for that quantity (the quoted components scaled by "
          f"[`jlc-parts.md`](jlc-parts.md)'s prices, catalog of {JLC_PARTS.get('date', '?')}); X-ray per board "
          "by JLC's tiers; the bare PCBs at JLC's price for that quantity (`JLC_PCB_PRICE`, measured on the "
          "calculator).  *Floor*: parts at the 100-board breaks, joints, X-ray and PCB per board, once the "
          "fees per order no longer count.", "",
          "| Board | " + " | ".join(f"{n}" for n in VOLUME_QTY) + " | Floor |",
          "|---|" + "---:|" * (len(VOLUME_QTY) + 1)]
    for name, u in vol["unit"].items():
        md.append(f"| {name} | " + " | ".join(f"{u[n]:.2f}" for n in VOLUME_QTY) + f" | {vol['floor'][name]:.2f} |")
    need = ", ".join(f"{o['need']} {name}" for name, o in orders.items())
    md += ["", f"One rack ({need}) when building several in one order, one shipment "
           f"(${JLC_SHIPPING_USD:.0f}, held: it grows with the weight):", "",
           "| Racks | " + " | ".join(orders) + " | Per rack |", "|---|" + "---:|" * (len(orders) + 1)]
    for r, v in vol["racks"].items():
        md.append(f"| {r} | " + " | ".join(f"{v['boards'][name] / r:.2f}" for name in orders)
                  + f" | **{v['per_rack']:.2f}** |")
    return md



def jlc_parts_md(orders: dict) -> list[str]:
    """Per board and line: tier, JLC stock against 10 racks' need, unit price at the break 1 / 5 / 10
    racks reach (one order per design and per rack count, a rack's boards as the configuration needs
    them; JLC assembles at least 2 boards)."""
    if not JLC_PARTS:
        return []
    carried = Counter({b: orders[p]["need"] for p in PANELS if p in orders for b in PANELS[p]})
    ordered = {name: rows for name, rows in JLC_PARTS["boards"].items() if name in orders or name in carried}
    per_rack = {name: (orders[name]["need"] if name in orders else 0) + carried[name] for name in ordered}
    boards = {name: {r: max(2, per_rack[name] * r) for r in VOLUME_RACKS} for name in ordered}
    need10 = defaultdict(int)
    for name, rows in ordered.items():
        for lcsc, q, _ in rows:
            need10[lcsc] += q * boards[name][10]
    md = ["# JLC parts: tier, stock and price at volume", "",
          f"Generated by `python tools/bom.py` from `electronics/lib/jlc_parts.json` (JLC's catalog of "
          f"{JLC_PARTS['date']}, `tools/jlc_parts_snapshot.py`; prices LCSC's where the catalog has none).  "
          "Per rack: " + ", ".join(f"{n} {b}" for b, n in per_rack.items()) + "; JLC assembles at least 2 boards.  "
          "*Stock*: JLC's assembly stock against 10 racks' need of that part on every board (×: times over).  "
          "*Unit $*: at the break 1 / 5 / 10 racks reach.  *Tier*: JLC's parts library's (basic, preferred "
          "extended, extended); Economic PCBA loads basic and preferred parts free.", ""]
    for name, rows in ordered.items():
        b = boards[name]
        total = {r: sum(q * (part_price(lcsc, q * b[r]) or 0) for lcsc, q, _ in rows) for r in VOLUME_RACKS}
        md += [f"## {name}", "",
               f"Parts per board at 1 / 5 / 10 racks ({b[1]} / {b[5]} / {b[10]} boards): "
               + " / ".join(f"${total[r]:.2f}" for r in VOLUME_RACKS) + ".", "",
               "| LCSC | Part | Qty | Tier | Stock (× 10 racks) | Unit $ 1 / 5 / 10 racks | Line $ at 10 |",
               "|---|---|---:|---|---:|---|---:|"]
        lines = []
        for lcsc, q, comment in rows:
            p = JLC_PARTS["parts"].get(lcsc) or {}
            pr = [part_price(lcsc, q * b[r]) for r in VOLUME_RACKS]
            stock = p.get("stock") or 0
            ratio = stock / need10[lcsc] if need10[lcsc] else 0
            risk = " **⚠**" if ratio < 5 else ""
            lines.append((q * (pr[2] or 0), f"| {lcsc} | {str(p.get('mfr') or comment)[:28]} | {q} | {p.get('tier', '?')} | "
                          f"{stock:,} ({ratio:,.0f}×){risk} | "
                          + " / ".join("–" if x is None else f"{x:.3f}" for x in pr) + f" | {q * (pr[2] or 0):.2f} |"))
        md += [row for _, row in sorted(lines, reverse=True)] + [""]
    return md


def printed(rack) -> tuple[list[dict], list[dict]]:
    """Printed parts with counts per assembly and filament estimate from the STL volume."""
    import trimesh
    n_bays = sum(1 for _ in rack.bays())
    cols, n_rows = rack.units, len(rack.rows)
    cams = CAMERA_SETS                      # pods printed (config cameras: the bays shown with one)
    n_drawer, n_sled = bay_mounts(rack)
    counts = Counter({
        # the panel frame: a ladder per column boundary and level, a floor plate, a cap plate and
        # an X brace per column and level
        "ladder_base": cols + 1, "ladder_cap": cols + 1, "floor_plate": cols, "cap_plate": cols, "brace_base": cols,
        "tray": n_bays, "drawer": n_drawer, "chain_foot": n_drawer, "chain_anchor": n_drawer,
        "drawer_sled": n_sled, "drawer_block": n_sled,
        "camera_pod": cams, "camera_diffuser": cams,
        # each bay's label: its body and its ID's inlay (the H2D's second filament), printed as one object
        **{f"bay_label_{b.id.lower()}{s}": 1 for b in rack.bays() for s in ("", "_inlay")},
        # a converted bay's DATA ×4 (v2, logic or base) stands in its printed cradle at the drawer's back
        "x4_cradle": sum(1 for b in rack.bays() if rack.is_multi(b.id)),
        # the power box: base and lid, and the walls' optional label inlays (a second, light filament)
        "power_box_base": 1, "power_box_lid": 1, "power_box_labels": 1,
    })
    for row in rack.rows:
        counts[f"ladder_{row['id'].lower()}"] += cols + 1
        counts[f"brace_{row['id'].lower()}"] += cols
    for bay in rack.bays():
        duts = rack.duts(bay.id)
        if not duts or rack.plate_kind(bay.id) == "pegs":
            counts["plate"] += 1            # the honeycomb plate, and the pegs that hold its boards
            if duts:
                for peg in plate_layout.layout_bay(rack, bay.id).pegs:
                    for name, _ in peg.parts:
                        counts[name] += 1
        elif rack.is_multi(bay.id):         # `plate: boards`: the former plates
            counts[f"plate_bay_{bay.id.lower()}"] += 1
        else:
            counts[f"plate_{duts[0].board}"] += 1
    stl_dir = REPO / "mechanical" / "stl"
    rows, prints = [], []
    total_g = 0.0
    for name, qty in sorted(counts.items()):
        if qty == 0:
            continue
        stl = stl_dir / f"{name}.stl"
        grams = None
        if stl.exists():
            m = trimesh.load(stl, force="mesh")
            vol = abs(m.volume) / 1000.0          # cm³
            grams = vol * PETG_DENSITY * PRINT_FILL
            total_g += grams * qty
        prints.append({"part": name, "qty": qty, "grams_each": round(grams, 1) if grams else None,
                       "grams_total": round(grams * qty, 1) if grams else None, "stl": f"mechanical/stl/{name}.stl"})
    rows.append({"category": "Printed parts", "group": "filament", "item": "PETG filament",
                 "supplier": "any", "qty": math.ceil(total_g / 1000 * 1.1 * 10) / 10, "unit": "kg",
                 "unit_eur": PETG_EUR_PER_KG, "notes": f"≈{total_g / 1000:.1f} kg estimated + 10 % waste, "
                                                    f"{sum(counts.values())} parts"})
    # optional, outside the totals: the rear bays' covers, printed once a bay is validated (a lid over a one-board
    # bay, a box over a DATA ×4 standing in its cradle)
    n_multi = sum(1 for b in rack.bays() if rack.is_multi(b.id))
    opt_g = 0.0
    for name, qty in (("cover_lid1", n_bays - n_multi), ("cover_box4", n_multi)):
        stl = stl_dir / f"{name}.stl"
        if qty == 0 or not stl.exists():
            continue
        grams = abs(trimesh.load(stl, force="mesh").volume) / 1000.0 * PETG_DENSITY * PRINT_FILL
        opt_g += grams * qty
        prints.append({"part": name, "qty": qty, "grams_each": round(grams, 1), "grams_total": round(grams * qty, 1),
                       "stl": f"mechanical/stl/{name}.stl", "optional": True})
    if opt_g:
        rows.append({"category": "Printed parts", "group": "covers", "item": "Rear bay covers (optional)",
                     "supplier": "printed", "qty": n_bays, "unit_eur": 0,
                     "notes": f"one per bay: cover_lid1 over a one-board bay, cover_box4 over a DATA ×4; "
                              f"≈{opt_g:.0f} g more PETG, not in the filament line"})
    return rows, prints


def hardware(rack) -> list[dict]:
    r = rack.raw
    n_rows = len(rack.rows)
    cols = rack.units
    n_bays = sum(1 for _ in rack.bays())
    cams = CAMERA_SETS                      # camera pods bought, wherever they go
    braces = cols * (n_rows + 1)
    n_drawer, n_sled = bay_mounts(rack)     # sled bays: no chain, foot, anchor or magnets
    n_fixed = sum(1 for b in rack.bays() if rack.mount(b.id) == "fixed")
    n_multi = sum(1 for b in rack.bays() if rack.is_multi(b.id))   # DATA ×4 bays: the cradle on 3 inserts
    chain_m = math.ceil(0.19 * n_drawer + 0.3) if n_drawer else 0   # sold by the metre, one pair of end pieces with each
    charger = r["power_box"]["charger"]
    rows = [
        {"category": "Fasteners", "item": "M3 heat-set insert, 5.7 mm (generic brass, Ruthex-compatible holes)",
         "supplier": "AliExpress (bulk) / Ruthex", "qty": 4 * n_bays + 2 * n_drawer + 4 * n_bays + 4 + 3 * n_multi,
         "unit_eur": 0.03,
         "notes": "per tray 4 node standoffs + 2 chain anchor (drawer bays); 4 under every bay's ceiling (a camera "
                  "pod's mount); a DATA ×4 bay's drawer: 3 in its bosses, for the cradle; power box: 4 hub standoffs"},
        {"category": "Fasteners", "item": "M3 square nut, DIN 562 (5.5 × 5.5 × 1.8)",
         "supplier": "AliExpress (bulk)", "qty": 4 * (cols + 1) * (n_rows + 1), "unit_eur": 0.02,
         "notes": "4 in the rear edge of every base and row ladder, in pockets open to its face (the braces "
                  "screw into them)"},
        {"category": "Fasteners", "item": "M3×8 pan head, Phillips (ISO 7045): rear braces, chain anchor, node PCB, "
                                         "power box lid, camera pods, the DATA ×4 cradle",
         "supplier": "AliExpress (bulk)", "qty": 4 * braces + 2 * n_drawer + 4 * n_bays + 4 + 2 * cams + 3 * n_multi, "unit_eur": 0.02,
         "notes": "one M3 length everywhere: where it goes deeper than an insert, the insert's hole runs on past it "
                  "(lib/common.scad › insert_hole(runout))"},
        {"category": "Fasteners", "item": "M3 male-female hex spacer, 12 mm + 6 mm thread, brass (≤ 5.5 mm AF)",
         "supplier": "AliExpress (bulk)", "qty": 4, "unit_eur": 0.10,
         "notes": "power box: through the hub's holes into the standoff inserts; the lid's M3×8 goes 5.6 mm into "
                  "their tops (a female thread ≥ 6 mm deep)"},
        {"category": "Fasteners", "item": "PT 2.3×8 pan head, thread-forming for plastics (M2.3×8 \"ST\", head ≤ Ø4.5): "
                                         "every printed pilot.  A drawer bay: the foot lock, 4 for the chain's end pieces, "
                                         "2 for the DATA port board, the guide lip's stop; a sled bay: 2 DATA, its stop and "
                                         "2 port-block locks (and 2 sled locks if fixed); a DATA ×4 bay: no DATA board (its "
                                         "cradle takes M3 × 8 into inserts)",
         "supplier": "AliExpress (bulk, HZYUEGOU: M2.3×8 self-tapping pan head, stainless, ≈ €2.13 / 100)",
         "qty": 8 * n_drawer + 5 * n_sled + 2 * n_fixed - 2 * n_multi,
         "unit_eur": 0.02,
         "notes": "pilots Ø1.9 (lib/common.scad › PT_PILOT), clearance Ø2.6; a PT 2.6's Ø5 head would rub the "
                  "drawer's wall at the guide lips (lib/carrier.scad › LIP_SCREW, checked in SolidCraft)"},
        {"category": "Fasteners", "item": "M2.5 washer, DIN 125 (chain end pieces: their tab holes can be 4.3 mm)",
         "supplier": "AliExpress (bulk)", "qty": 4 * n_drawer, "unit_eur": 0.01},
        {"category": "Motion", "item": "Drag chain 7×7 mm, links open on both sides (outer 13.5 × 10.2 mm, R18), "
                                      "≈ 180 mm per drawer with its two end pieces",
         "supplier": "Olimex DRAG-CHAIN-7X7", "qty": chain_m, "unit": "m", "unit_eur": 4.0,
         "notes": "open the links to lay the DATA lead in (its PH plugs, 12 mm wide, do not pass a 7×7 channel); "
                  "Olimex publishes only the inner size: outer size and end holes from Electrokit 41017996, "
                  "measure the bend radius and the end pieces on arrival (config/rack.yaml › chain)"},
        {"category": "Motion", "item": "End pieces for 7×7 chain (pair: tab with 2 holes 8 mm apart), the drawers "
                                      "beyond one pair per metre of chain",
         "supplier": "AliExpress 1005003181041939, \"7x7mm\" (or one more metre of chain per pair)",
         "qty": max(0, n_drawer - chain_m), "unit_eur": 2.17,
         "notes": "Olimex does not sell them alone; this generic chain ships with one pair per metre.  The listing "
                  "is for the non-opening 7×7 type: check one on the open links before buying the lot"},
        # the drawer's DATA port: our own small board (electronics/data-port, in the Electronics lines)
        # on the rear-bay floor, on an 8-wire PH lead from the node's J7 through the drag chain (USB, the
        # node's I²C and INT for a later DATA ×4 board): the camera's lead too, one type for both
        # (pin n ↔ pin 9−n); 8 pins, so a 6-pin row cable cannot go in
        {"category": "Cables", "item": "JST PH 8-pin lead, pin n ↔ pin 9−n (flat, no twist), 50 cm, lot of 5 "
                                      "(DATA leads: node J7 → drag chain → DATA port board; camera leads: node J6 → "
                                      "pod J1)",
         "supplier": f"AliExpress {PH_LEAD_URL}, \"Same direction\", 8P, Length50CM",
         "qty": math.ceil((n_bays + CAMERA_SETS) / 5), "unit": "lot", "unit_eur": 4.5,
         "notes": f"{n_bays} DATA + {CAMERA_SETS} camera leads; price interpolated from the 6-pin lots, not read: "
                  "check the 8P lengths on the listing (45–50 cm).  The DATA route is ≈ 38 cm plugs included "
                  "(constant over the stroke); the spare goes in a wider bend between the node and the chain's fixed "
                  "end (nothing moves there), never in front of the chain's moving end.  A sled bay's route is "
                  "≈ 22 cm (no chain): the slack coiled in the plenum.  On arrival: both plugs show "
                  "the same face, pin 1 rings to pin 8; twist D+/D− (pins 3-4 at the node) by hand.  Or crimp them: "
                  "PHR-8 + 16 × SPH-002T-P0.5S, 24 AWG"},
        # the row cables, one type (docs/can.md): pin n ↔ pin 7−n, both plugs the same face up, from 24 AWG
        # leads (ROW_FEED_CM)
        *_row_cables(rack),
        {"category": "Cables", "item": "Cable tie 2.5 × 100 mm: the row jumpers, 2 each, through the tray's two tie "
                                      "anchors at its front right (docs/cabling.md)",
         "supplier": "AliExpress (bulk)", "qty": 2 * sum(cols - 1 for _ in rack.rows), "unit_eur": 0.02},
    ]
    if r["drawer"].get("detent", "printed") == "magnet":     # drawer.detent (printed by default: no parts)
        rows += [
            {"category": "Fasteners", "item": "Neodymium disc magnet 6×3 mm N35, lot of 50 (drawer detent: one in the "
                                             "drawer, one in the tray ledge)",
             "supplier": "AliExpress 1005010074888189, \"6x3mm-50 pièces\"", "qty": math.ceil(2 * n_drawer / 50),
             "unit": "lot", "unit_eur": 3.99,
             "notes": "glued (a drop of CA in the slip-fit pocket): the other magnet pulls each one out of its pocket's "
                      "mouth.  Polarity: stack the pair, mark both outer faces; marked faces into the pockets"},
            {"category": "Fasteners", "item": "Cyanoacrylate glue, gel (detent magnets)", "supplier": "any",
             "qty": 1, "unit_eur": 3.0},
        ]
    duts = [d for b in rack.bays() for d in rack.duts(b.id) if d.cable]   # one cable per board under test
    cab = Counter(d.cable for d in duts)
    lib = rackcfg.load_boards()
    for k, n in sorted(cab.items()):
        src = DUT_CABLES.get(k, {"supplier": "AliExpress", "unit_eur": 3.0})
        boards = ", ".join(sorted({lib[d.board].get("short", d.board) for d in duts if d.cable == k}))
        rows.append({"category": "Cables", "item": f"{r['cables'][k]['label']} (DUT cable: {boards})",
                     "supplier": src["supplier"], "qty": n, "unit_eur": src["unit_eur"],
                     "notes": src.get("notes", "")})
    # 90° adapters for the micro-B / mini-B boards whose USB faces the port wall (cable style adapter): one
    # bent up and one bent down per board, the socket's orientation deciding which one serves
    ada = Counter(r["cables"][d.cable]["b"] for d in duts if r["cables"][d.cable].get("style") == "adapter")
    for t, n in sorted(ada.items()):
        name = {"micro-b": "Micro-B", "mini-b": "Mini-B"}[t]
        rows.append({"category": "Cables", "item": f"{name} 90° adapter, male → female, up and down, one of each "
                                                   f"per board",
                     "supplier": "AliExpress (DIY-018, \"UP\" and \"DOWN\")" if t == "micro-b" else "AliExpress",
                     "qty": 2 * n, "unit_eur": 1.0,
                     "notes": "keep the one whose female faces up once plugged into the board (the cable's straight "
                              "plug stands on it, its cable leaves upwards); the other is a spare"})
    # a sub-slot's logic analyzer (population › boards › role: analyzer): rack equipment, unlike the boards
    # under test; gusmanb's firmware on it, its channels on Dupont jumpers (docs/multi-dut-node.md)
    analyzers = [d for b in rack.bays() for d in rack.duts(b.id) if d.role == "analyzer"]
    if analyzers:
        where = ", ".join(d.id for d in analyzers)
        rows += [
            {"category": "Analyzer", "item": f"Raspberry Pi Pico 2 (RP2350), the logic analyzer in {where}",
             "supplier": "Raspberry Pi approved reseller (Kubii, The Pi Hut, Pimoroni)", "qty": len(analyzers),
             "unit_eur": 5.5,
             "notes": "an RP2350 A4 (marked on the chip): A2 has erratum E9 (an input released from high can stay "
                      "at ≈ 2.1 V).  gusmanb's LogicAnalyzer UF2, pinned in config/rack.yaml › analyzer"},
            {"category": "Analyzer", "item": "Dupont jumper wires, female–female, 10 cm, a 40-wire strip",
             "supplier": "AliExpress", "qty": len(analyzers), "unit_eur": 1.5,
             "notes": "its channels to the neighbours' pins, a GND beside each group; one wire, its far end cut, "
                      "soldered to the Pico 2's BOOTSEL pad (TP6) for the port's BOOT pin"},
        ]
    # Dupont jumpers from a DATA ×4 v1's RESET/BOOT headers to the boards' pins (population › jumpers); a bay showing
    # the planned v2 (`x4: v2`) keeps v1 here, its jumpers come with v2's headers
    n_jump = sum(len(pins) for b in rack.bays() if (e := r["population"].get(b.id) or {}).get("x4") != "v2"
                 for pins in (e.get("jumpers") or {}).values())
    if n_jump:
        rows.append({"category": "Cables", "item": "Dupont jumper wires, female–female, 20 cm, a 40-wire strip "
                                                    f"(DATA ×4 RESET/BOOT headers → the boards' pins: {n_jump} wire{'s' * (n_jump > 1)})",
                     "supplier": "AliExpress", "qty": 1, "unit_eur": 2.0,
                     "notes": "the usual rainbow; GND black, RESET brown, BOOT green.  The DATA ×4's 1 × 3 headers and "
                              "the boards' pin headers are soldered by hand, pins up"})
    rows += [
        # the rack's supply: a USB PD charger outside it, into the power box's rear wall (the hub's
        # CH224A sink asks for 28 V EPR when offered, else 20 V), so no mains wiring anywhere in the rack.
        # 100 W at 20 V by default since 2026-10-21 (the user); 140 W EPR is the option (config/rack.yaml)
        {"category": "Power", "item": charger["part"], "supplier": "Anker (anker.com/fr) / UGREEN / any PD 100 W",
         "qty": 1, "unit_eur": float(charger.get("price", 46)),
         "notes": "dedicated to the rack: a multi-port charger may withdraw its full offer when something else "
                  "is plugged in.  Realistic load ≈ 35–40 W.  At 20 V a row is capped at ≈ 32 W (its eFuse's "
                  "1.6 A), and the hub budgets the rows against the contract: it sheds rows before the charger "
                  "trips.  For racks full of hungry DUTs, a 140 W PD 3.1 EPR charger (28 V): no hardware change"},
        {"category": "Power", "item": charger["cable"], "supplier": "any (check the 5 A e-marker)", "qty": 1,
         "unit_eur": 12.0, "notes": "required for 100 W: above 3 A a charger only offers its full current through "
                                   "an e-marked 5 A cable (a 3 A one gives 60 W).  A cable shipped with the charger "
                                   "and rated 100 W or more is one; 240 W rated for the 140 W EPR option"},
    ]
    if CAMERA_SETS:
        cams = CAMERA_SETS
        rows += [
            # the bay's own node drives its camera (SPI) and light (docs/electronics.md, Camera)
            {"category": "Cameras", "item": "Arducam Mega 3MP SPI camera, M12 version (B0434), 33 × 33 mm",
             "supplier": "Welectron (33.90 € TTC) / Arducam (≈ $30) / DigiKey", "qty": cams, "unit_eur": 28.25,
             "notes": "on arrival: its header's order (VCC GND SCK MISO MOSI CS) and its MISO high level when fed 5 V "
                      "(≤ 3.6 V, or change R33 and fit R35 on the node)"},
            {"category": "Cameras", "item": "M12 lens, 1/4\", ≈ 120° diagonal (the stock 90° is too narrow for a "
                                           "NUCLEO-144 / nRF DK)", "supplier": "AliExpress", "qty": cams, "unit_eur": 3.0},
            # the pod board (electronics/camera-pod, in the Electronics lines) carries the light and the
            # Mega's 3.3 V: nothing to crimp or solder
            # (the camera lead, node J6 → pod J1, is the DATA lead's type: in the Cables lines)
            {"category": "Cameras", "item": "Cable JST XH 2.54 6-pin → Dupont female, one 6-pin housing, 10–20 cm "
                                           "(the Mega → pod J2, VCC GND SCK MISO MOSI CS in order)",
             "supplier": "AliExpress", "qty": cams, "unit_eur": 0.5,
             "notes": "the Mega's own 6-pin cable does if it ends in Dupont sockets; J2's pins are named on the "
                      "board, so the wires go on by name"},
            {"category": "Cameras", "item": "Pod hardware: 2 × PT 2.6×14 (the pod board, through the diffuser's "
                                           "posts), cable ties 2.5 × 100 (the lead: 1 at the tray's rear slot, 3 "
                                           "under the ceiling)",
             "supplier": "AliExpress (bulk)", "qty": cams, "unit": "set", "unit_eur": 0.3},
        ]
    return rows


def standalone(rack) -> dict:
    """The standalone bays (docs/standalone.md): what one Solo or one Quad takes beyond its boards (the node, the
    single DATA port board or the DATA ×4 v2, from the rack's order), and the honeycomb plate's desk frame.
    Optional: outside the rack's totals."""
    import trimesh
    stl_dir = REPO / "mechanical" / "stl"

    def printed_line(name, qty=1):
        stl = stl_dir / f"{name}.stl"
        g = abs(trimesh.load(stl, force="mesh").volume) / 1000.0 * PETG_DENSITY * PRINT_FILL if stl.exists() else 0.0
        return {"item": f"{name} (printed)", "qty": qty, "grams": round(g * qty, 1),
                "unit_eur": round(g * PETG_EUR_PER_KG / 1000, 2), "stl": f"mechanical/stl/{name}.stl"}

    pd = {"item": "USB-C PD trigger module, CH224K with a DIP switch set to 20 V (a \"decoy\" board, ≤ 30 × 21 mm): "
                  "feeds the node's J1 in place of the power hub, from any PD charger offering 20 V, ≥ 30 W "
                  "(docs/cabling.md)",
          "supplier": "AliExpress 3256811726090162; its size goes in config/rack.yaml › standalone.pd_module",
          "qty": 1, "unit_eur": 2.0}
    foam = {"item": "Double-sided foam pad, 1 mm, ≈ 20 × 10 mm (the PD module against its wall)", "supplier": "any",
            "qty": 1, "unit_eur": 0.05}
    pd_lead = {"item": "PD lead: JST PHR-6 housing, 2 × SPH-002T-P0.5S, 2 × 15 cm 24 AWG (red VRACK on pin 1, black GND "
                       "on pin 2), soldered to the module's output pads", "supplier": "LCSC / AliExpress",
               "qty": 1, "unit_eur": 0.3}
    data_lead = {"item": "JST PH 8-pin lead, pin n ↔ pin 9−n, 15 cm (node J7 → the DATA board): the rack's DATA lead, "
                         "shorter", "supplier": f"AliExpress {PH_LEAD_URL}, \"Same direction\", 8P", "qty": 1,
                 "unit_eur": 0.9}
    feet = {"item": "Rubber bumper, self-adhesive, Ø10 × 3 mm", "supplier": "AliExpress (bulk)", "qty": 4,
            "unit_eur": 0.05}

    def hw(item, n, eur):
        return {"item": item, "supplier": "AliExpress (bulk)", "qty": n, "unit_eur": eur}

    units = {
        "solo": {"title": "Solo (the node + the single DATA port board)",
                 "lines": [printed_line("standalone_solo_base"), printed_line("standalone_solo_lid"), pd, foam, pd_lead,
                           data_lead, hw("M3 heat-set insert, 5.7 mm", 8, 0.03), hw("M3×8 pan head (ISO 7045)", 8, 0.02),
                           hw("PT 2.3×8 pan head, thread-forming", 2, 0.02), feet]},
        "quad": {"title": "Quad (the node + the DATA ×4 v2)",
                 "lines": [printed_line("standalone_quad_base"), printed_line("standalone_quad_shelf"),
                           printed_line("standalone_quad_lid"), pd, foam, pd_lead, data_lead,
                           hw("M3 heat-set insert, 5.7 mm", 8, 0.03), hw("M3×8 pan head (ISO 7045)", 8, 0.02), feet]},
        "desk_frame": {"title": "Desk frame, for either (the rack's honeycomb plate in it: the DUTs held by its pegs)",
                       "lines": [printed_line("standalone_desk_frame"), printed_line("plate")]},
    }
    for u in units.values():
        for line in u["lines"]:
            line["ext_eur"] = round(line["qty"] * line["unit_eur"], 2)
        u["total_eur"] = round(sum(line["ext_eur"] for line in u["lines"]), 2)
        u["grams"] = round(sum(line.get("grams", 0) for line in u["lines"]), 1)
    return units


def standalone_md(units) -> list[str]:
    md = ["", "## Standalone bays (optional, outside the totals above)", "",
          "One bay out of the rack, on a desk ([docs/standalone.md](../docs/standalone.md)): what a unit takes beyond "
          "its boards (the node and its DATA board, from the boards' order above) and a USB-C PD charger offering "
          "20 V.  The printed parts at the estimate above (PETG, from the STL's volume)."]
    for u in units.values():
        md += ["", f"**{u['title']}**: ≈ €{u['total_eur']:.2f}, {u['grams']:.0f} g of PETG", "",
               "| Item | Qty | Unit € | Total € | Source |", "|---|---:|---:|---:|---|"]
        md += [f"| {line['item']} | {line['qty']} | {line['unit_eur']:.2f} | {line['ext_eur']:.2f} | "
               f"{line.get('supplier') or '`' + line['stl'] + '`'} |" for line in u["lines"]]
    return md


def main():
    rack = rackcfg.load()
    elec, orders = electronics(rack)
    cost = jlc_cost(orders)
    vol = volume(orders)
    prt, prints = printed(rack)
    hw = hardware(rack)
    rows = elec + prt + hw
    for r in rows:
        r.setdefault("unit", "pcs")
        r["ext_eur"] = round(float(r["qty"]) * float(r.get("unit_eur") or 0), 2)
    out = REPO / "bom"
    out.mkdir(exist_ok=True)
    fields = ["category", "group", "item", "qty", "unit", "unit_eur", "ext_eur", "supplier", "part", "mpn",
              "manufacturer", "ref", "notes"]
    with (out / "rack-bom.csv").open("w", newline="", encoding="utf-8") as fo:
        w = csv.DictWriter(fo, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    by_cat = defaultdict(float)
    for r in rows:
        by_cat[r["category"]] += r["ext_eur"]
    total = sum(by_cat.values())
    n_bays = sum(1 for _ in rack.bays())
    data = {"rows": rows, "by_category": dict(by_cat), "total_eur": round(total, 2),
            "prints": prints, "bays": n_bays, "rows_n": len(rack.rows),
            "jlc_quote": {"date": JLC_QUOTE_DATE, "currency": "USD", "shipping": JLC_SHIPPING, "boards": JLC_QUOTE,
                          "order": orders, "cost": cost, "fees": JLC_FEES, "volume": vol},
            "calculator": calculator(orders), "standalone": (sa := standalone(rack))}
    (REPO / "site" / "assets").mkdir(parents=True, exist_ok=True)
    (REPO / "site" / "assets" / "bom.json").write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")

    md = ["# Bill of materials", "",
          "Generated by `python tools/bom.py` from `config/rack.yaml`, the KiCad BOMs and the STL volumes.",
          f"Configuration: **{n_bays} bays** ({rack.units} columns × {len(rack.rows)} rows) in the panel frame. "
          "Prices are indicative (EUR excl. VAT, small quantities, October 2026); re-quote before ordering. "
          f"The boards follow a real JLCPCB quote of {JLC_QUOTE_DATE}, adjusted for the changes since (below, "
          f"converted at $1 = €{USD_EUR:.2f}); every board goes in one cart, so one shipment ({JLC_SHIPPING}, "
          f"${JLC_SHIPPING_USD:.0f} counted); import VAT is extra.", "",
          "| Category | Cost (€) |", "|---|---:|"]
    md += [f"| {k} | {v:,.0f} |" for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1])]
    md += [f"| **Total** | **{total:,.0f}** |", "", f"≈ **€{total / n_bays:,.0f} per bay** all-in.", "",
           "Full line-item list: [`rack-bom.csv`](rack-bom.csv) · per-board JLCPCB files: "
           "`electronics/<board>/fab/` · interactive table: the viewer's BOM page.", "",
           "## JLCPCB orders (estimates)", "",
           f"USD, without the one shipment ({JLC_SHIPPING}, a line of its own) and import VAT.  The power hub is a real quote (jlcpcb.com, "
           "2026-10-19, from the fab files, with the AP33772S then: out of stock, a Global Sourcing estimate on top; the "
           "CH224A since, from LCSC).  "
           "Every other board is an **estimate** built from JLC's fees and catalogue prices: the node's last real "
           f"quote ({JLC_QUOTE_DATE}: 20 PCBs ENIG, 16 assembled, $367.71) priced it before rev 0.5.  The "
           "bay node is the order the user chose on 2026-10-19: 10 PCBs, lead-free HASL, 10 assembled (8 bays, "
           "2 spares).  The per-part lines below use catalogue prices; a *Components* line per board brings them "
           "up to the estimated components figure.  *Order* applies what changed since: the through-hole "
           "connectors hand-soldered from loose LCSC parts (LCSC shipping extra).  The DATA ×4 v2's two "
          "variants go on one order panel (data-port-x4-v2-panel: one logic and one base per panel, one Economic "
          "order); their own estimates stay for single orders.  Re-quote before ordering (the "
           "full PCBA quote needs the user's JLC sign-in).", "",
           "| Board | Order | Line | USD |", "|---|---|---|---:|"]
    for name, q in JLC_QUOTE.items():
        order = (f"{q['pcbs']} panels ({q['spec']}), {q['assembled']} assembled: {q['assembled']} of each board, "
                 f"{q['service']} PCBA" if "boards" in q else
                 f"{q['pcbs']} PCBs ({q['spec']}), {q['assembled']} assembled, {q['service']} PCBA")
        md.append(f"| {name} | {order} | PCB: {_usd(q['pcb'])} | {sum(q['pcb'].values()):.2f} |")
        md.append(f"| | | PCBA: {_usd(q['pcba'])} | {sum(q['pcba'].values()):.2f} |")
        md.append(f"| | | **{'Estimated' if q.get('estimate') else 'Quoted'} total** | **{q['total']:.2f}** |")
        if name in orders:
            o = orders[name]
            md.append(f"| | | Order (indicative): {'; '.join(o['changes']) or 'as quoted'} | {o['total']:.2f} |")
        elif panel := next((p for p in PANELS if p in orders and name in PANELS[p]), None):
            md.append(f"| | | In the rack's order on the {panel} (one per panel) | |")
        else:
            md.append("| | | Not in the rack's order | |")
    md += [""] + jlc_cost_md(cost) + [""] + volume_md(vol, orders)
    md += ["", "## Printed parts", "", "| Part | Qty | g each (est.) | STL |", "|---|---:|---:|---|"]
    md += [f"| {p['part']}{' (optional)' if p.get('optional') else ''} | {p['qty']} | {p['grams_each'] or '–'} | "
           f"`{p['stl']}` |" for p in prints]
    md += ["", "## Line items", "", "| Category | Item | Qty | Unit € | Total € | Source |", "|---|---|---:|---:|---:|---|"]
    for r in rows:
        src = " ".join(x for x in (r.get("supplier", ""), r.get("part", "")) if x)
        md.append(f"| {r['category']} | {r['item']} | {r['qty']} {'' if r['unit'] == 'pcs' else r['unit']} | "
                  f"{float(r.get('unit_eur') or 0):.2f} | {r['ext_eur']:.2f} | {src} |")
    md += standalone_md(sa)
    (out / "README.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    if JLC_PARTS:
        (out / "jlc-parts.md").write_text("\n".join(jlc_parts_md(orders)) + "\n", encoding="utf-8")
    print(f"BOM: {len(rows)} lines, total ~ EUR {total:,.0f} (EUR {total / n_bays:,.0f}/bay)")
    for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1]):
        print(f"  {k:15s} EUR {v:8.0f}")


if __name__ == "__main__":
    main()
