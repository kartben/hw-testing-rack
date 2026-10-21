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
    # The order the user chose on 2026-10-19 ("10 en HASL"): 10 PCBs, lead-free HASL, all 10 assembled
    # (8 bays and 2 spares; JLC adds its $25 engineering fee only above 10 PCBs).  NOT re-quoted: the
    # quote of 2026-10-16 (20 PCBs ENIG, 16 assembled, $367.71) priced the board before rev 0.5 and the
    # full PCBA quote needs the user's sign-in.  Built from JLC's fees (help page of 2026-09-09) and the
    # live bare-PCB price of 2026-10-19: 74 × 90 mm 4-layer lead-free HASL $19.30 for 10 (as at 64 × 90: JLC's
    # offer covers up to 100 × 100 mm) + $0.20 for the 5 mm rails Standard PCBA may add; setup $25.56, stencil $8.21, $1.53 per unique part type (38, basic
    # or extended alike; J4 and its 22k Rp went with the 74 × 90 re-layout, then four values were merged onto
    # values the board has: EN 100k/10k, PC_DET 10k/18k, I²C 5.1k, AUX VREF 33 Ω), SMT $0.0016 a joint (369 a board), X-ray $1.64 a board (the WROOM-1, mandatory),
    # packaging $0.52; components at catalogue prices × 1.12 (JLC's prices and attrition).  The page
    # also lists a Standard handling fee (≥ $14.93) that the 2026-10-16 quote didn't carry: to confirm.
    "bay-node": {
        "pcbs": 10, "assembled": 10, "spares": 2, "service": "Standard", "total": 318.85, "estimate": True,
        "spec": "4-layer 74×90 mm, lead-free HASL, 5 mm edge rails if JLC adds them for Standard PCBA",
        "pcb": {"board": 19.50},
        "pcba": {"setup": 25.56, "stencil": 8.21, "components": 184.62, "feeders": 58.14, "SMT": 5.90,
                 "X-ray": 16.40, "packaging": 0.52},
    },
    # v0.5, quoted on jlcpcb.com on 2026-10-19 (the user's account), from main's fab files: the gerbers,
    # the JLC BOM and CPL, which leave the hand-soldered connectors out (`from_fab`: no further cut for
    # them).  5 PCBs 4-layer ENIG (JLC adds two 5 mm rails for Standard PCBA: 86 × 140 mm), 2 assembled,
    # Standard, X-ray.  JLC flags the USB4105 (J1, J6) as hard to process ($0.03 a piece).  Two parts were
    # out of stock: the TCAN1462V (U6), quoted as its documented alternate TJA1462AT/0Z (C3234095, same
    # SOIC-8 pinout, signal improvement; both boards take it since), and the AP33772S FA01 (U1, LCSC 0),
    # left out of the quote.  U1
    # comes through JLC Global Sourcing from DigiKey (estimate): 5 at €2.09 with JLC's reported ≈ 50 %
    # markup ≈ $17.04, plus its loading fee ≈ $3, and ≈ 2 weeks for the parts to clear into JLC.  The board
    # is 76 × 100 since 2026-10-20 (JLC_SINCE_QUOTE): the spec below is the board's, the lines the quote's.
    "power-hub": {
        "pcbs": 5, "assembled": 2, "service": "Standard", "total": 242.52, "date": "2026-10-19", "from_fab": True,
        "spec": "4-layer 76×100 mm (86×100 with JLC's rails), ENIG",
        "pcb": {"engineering": 25.00, "ENIG": 18.00, "board": 7.50},
        "pcba": {"setup": 25.75, "stencil": 8.27, "components": 57.89, "feeders": 72.85, "SMT": 3.30,
                 "X-ray": 3.30, "packaging": 0.50, "special components": 0.12, "U1 global sourcing (est.)": 20.04},
        "gs_parts": 3,          # AP33772S bought through Global Sourcing since JLC_SINCE_QUOTE (5 in the quote)
    },
    # the drawer's DATA port board (v1.0, 2 layers, parts on one side) is NOT quoted either: Economic
    # PCBA (setup $8.18, stencil $1.53, $3.07 per extended part type: the USB4105, the S8B-PH and the
    # USBLC6), components at catalogue prices plus ≈ 3 % attrition, ≈ 32 joints a board.  The
    # USB4105's four shell stakes are through-hole, as on the node: JLC may add a small fee for them.
    # One per node but the converted bays' (a DATA ×4 instead): six, and a seventh as a spare.  An
    # eighth would cost $1.62 more (7 and 8 boards reach the same price breaks); the USB4105's and the
    # S8B's 10-piece breaks make all ten PCBs $2.18 more than seven.
    "data-port": {
        "pcbs": 10, "assembled": 7, "spares": 1, "service": "Economic", "total": 37.16, "estimate": True,
        "spec": "2-layer 40×17 mm, lead-free HASL",
        "pcb": {"board": 6.30},                 # jlcpcb.com calculator, 2026-10-19 (JLC_PCB_PRICE)
        "pcba": {"setup": 8.18, "stencil": 1.53, "components": 11.56, "extended parts": 9.21, "SMT": 0.38},
    },
    # the camera pod board (v1.0, 2 layers, one side), one per camera (CAMERA_SETS): an estimate built like
    # the DATA port's, Economic PCBA, $3.07 per extended part type (the S8B, the SMD header, the LED)
    "camera-pod": {
        "pcbs": 5, "assembled": 2, "service": "Economic", "total": 26.38, "estimate": True,
        "spec": "2-layer 40×27 mm, lead-free HASL",
        "pcb": {"board": 5.20},                 # jlcpcb.com calculator, 2026-10-19 (JLC_PCB_PRICE)
        "pcba": {"setup": 8.18, "stencil": 1.53, "components": 2.06, "extended parts": 9.21, "SMT": 0.20},
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
    # the hub and ports plus the CH446Q matrix and the RP2354B analyzer), one per bay showing `x4: v2`: an
    # estimate from its fab JLC BOM.  The standing board, 100 × 70 mm, so JLC's 4-layer offer (jlcpcb.com
    # calculator, 2026-10-20: $8.00 + ENIG $17.40; ENIG for the RP2354B's 0.4 mm QFN-80, Economic's pitch
    # limit).  Every JLC part on its front face: Economic PCBA, $3.07 for each of its 17 extended types among 40
    # (the 10k array C25725 and the H5VU25UC ESD C20615800 are preferred extended: no fee; R23/R24 22 Ω basic,
    # since 2026-10-20, in place of an extended 27 Ω; since 2026-10-21 the co-processor's AP2112K is gone, its
    # 3.3 V from the board's through a ferrite, and each port has a VBUS LED: the usability review).
    # Components at the snapshot's breaks (electronics/lib/jlc_parts.json) × 1.12 (JLC's prices and attrition,
    # as the node's); 1,120 joints a board at $0.0017; an X-ray of each board (the QFN hub, MCU and expanders).
    # L1 (AOTA-B201610S3R3-101-T, the one inductor Raspberry Pi approves for the RP2350's regulator) sells at
    # JLC by 32 at least, 4 in stock on 2026-10-20 (a pre-order): the 30 spare are paid once per order.  J1 and
    # the four 2 × 6 headers are hand-soldered, out of the JLC BOM.
    "data-port-x4-v2": {
        "pcbs": 5, "assembled": 2, "service": "Economic", "total": 165.27, "estimate": True, "from_fab": True,
        "spec": "4-layer 100×70 mm, JLC04161H-7628, ENIG",
        "pcb": {"special offer": 8.00, "ENIG": 17.40},
        "pcba": {"setup": 8.18, "stencil": 1.53, "components": 61.34, "extended parts": 52.19, "SMT": 3.81,
                 "X-ray": 3.28, "L1 minimum purchase (32)": 9.54},
    },
    # its base variant (DATA-4x: the logic left off, 91 parts fewer, data-port-x4-v2-base-*), one per other
    # converted bay: the same estimate, 8 extended types among 25 (and C25725, C20615800, preferred), 527 joints.  Ordered on its own it takes
    # lead-free HASL, as v1: no part finer than its hub's 0.5 mm QFN ($12.20 less than ENIG for 5 PCBs).
    "data-port-x4-v2-base": {
        "pcbs": 5, "assembled": 2, "service": "Economic", "total": 84.73, "estimate": True, "from_fab": True,
        "spec": "4-layer 100×70 mm, JLC04161H-7628, lead-free HASL",
        "pcb": {"special offer": 8.00, "lead-free HASL": 5.20},
        "pcba": {"setup": 8.18, "stencil": 1.53, "components": 32.19, "extended parts": 24.56, "SMT": 1.79,
                 "X-ray": 3.28},
    },
    # the rack's order for its converted bays (the orchestrator, 2026-10-20): the logic and the base above on
    # one 1 × 2 order panel (electronics/data-port-x4-v2/fab/data-port-x4-v2-panel-*: 100 × 142 mm, the base
    # turned 180°, top edge to top edge on two mouse-bite tabs), one Economic order: one setup and stencil,
    # the logic's part types once (the base's are a subset), both boards' parts bought together at the
    # breaks they reach, each board's joints and X-ray (panel_order() at 2 panels), the panels in ENIG
    # (jlcpcb.com calculator, 2026-10-20).  One logic and one base per panel; the variants' own estimates
    # above stay for single orders (the BOM page's calculator).
    "data-port-x4-v2-panel": {
        "pcbs": 5, "assembled": 2, "service": "Economic", "total": 226.88, "estimate": True, "from_fab": True,
        "boards": ("data-port-x4-v2", "data-port-x4-v2-base"),
        "spec": "4-layer 100×142 mm panel of a logic and a base, JLC04161H-7628, ENIG, mouse bites",
        "pcb": {"engineering": 25.00, "ENIG": 18.20, "board": 8.80},
        "pcba": {"setup": 8.18, "stencil": 1.53, "components": 91.28, "extended parts": 52.19, "SMT": 5.60,
                 "X-ray": 6.56, "L1 minimum purchase (32)": 9.54},
    },
}
# What the order changes against that quote (indicative, not re-quoted): the hub in lead-free HASL
# instead of ENIG, as the node (2026-10-20: $5.20 on JLC's calculator for 5 × 86 × 100 mm 4-layer, $5.30 at
# 86 × 140, against the quote's $18.00 ENIG; nothing on the hub needs ENIG: 0.5 mm QFN and the MINI-1's pads are assembled
# on HASL like the node's WROOM-1, INA226 and FSUSB42); the hub's
# through-hole connectors soldered by hand (catalog hand_solder), bought loose from LCSC, so their
# extended part types no longer need loading; and no JLC hand-soldering fee on either board (the
# node's JST PH are SMD since rev 0.4, JLC places them).
JLC_FINISH = {"power-hub": ("lead-free HASL", 5.20)}
# Parts added to a board after its quote (indicative, not re-quoted): (what, PCBA line, USD for the
# quoted order).  Bay node rev 0.5: the rack bus (TCAN1044AV, PESD2CAN, 2 × BAT54S, 3 resistors, 2
# capacitors, the 6-pin J1/J2), GCT USB4105 receptacles instead of the HRO ones and 2 × 100 nF on
# the USBLC6s: +$2.38 of parts per board at catalogue prices; four new extended part types and one
# gone (the HRO), ≈ $3 loading each.  Then the TCAN1462V (signal improvement) instead of the
# TCAN1044AV: +$0.54 per board.  Then J7, the DATA header (B5B-PH-SM4-TB): +$0.30 per board and
# one more extended part type.
# (The bay node's rev 0.5 changes against the 2026-10-16 quote lived here until its estimate of
# 2026-10-19 above, which prices the board as it is.)
# Power hub, after its quote of 2026-10-19: eleven values merged onto values the board already has, no
# footprint moved: FB 100k/18k as the node, EN 39k/18k, INT divider 10k/18k, I²C pull-ups 5.1k, every
# front LED on 1k, the IMON filters and the CAN split caps on the dVdT caps' 22n, the LDO input on the
# eFuses' 1u 0805.  Eleven part types fewer at the quote's $1.55 a type in Standard PCBA feeders (47 → 36
# placed types).  Then 3 AP33772S through Global Sourcing (2 boards, a spare) instead of 5: 2 × $3.41.
# Then the WCH CH224A (C42459160, in stock at LCSC) instead of the AP33772S, and no input switch: no Global
# Sourcing for U1 at all; out the 2 × IRF7842, the 5 mΩ shunt, the NTC, the 6.2k, 200 Ω and the AP33772S's
# passives, in the CH224A (2 × $0.43), its 56 Ω and 6.8k: −$2.79 of parts for the 2 boards at LCSC's prices,
# and 36 → 33 placed types (the CH224A loads like any LCSC part).  Then the board at 76 × 100 (2026-10-20, option
# B1 of docs/power-distribution-review.md): 86 × 100 with the rails, so JLC's 4-layer offer ($8.00 for 5) and no
# $25 engineering fee (jlcpcb.com calculator, 2026-10-20); the parts don't change.
JLC_SINCE_QUOTE = {"power-hub": [("76 × 100 mm: JLC's 4-layer offer, no engineering fee", "engineering", -25.00),
                                  ("76 × 100 mm: the offer's $8.00 for the 5 boards", "board", 0.50),
                                  ("11 part types fewer (values merged)", "feeders", -17.05),
                                  # 3 AP33772S through Global Sourcing (2 boards, a spare) instead of 5: 2 × $3.41
                                  ("3 AP33772S bought instead of 5", "U1 global sourcing (est.)", -6.82),
                                  ("CH224A from LCSC instead of the AP33772S", "U1 global sourcing (est.)", -13.22),
                                  ("no input switch (CH224A, its parts in, the switch's out)", "components", -2.79),
                                  ("3 part types fewer (CH224A)", "feeders", -4.65),
                                  # the PCBA review's fixes (2026-10-20) that apply with the CH224A: a B5819W at
                                  # each row output (the board's type, 4 a board); the gate clamp went with the switch
                                  ("PCBA review: 4 × B5819W a board", "components", 0.24)],
                   # the bay node, after its estimate: 2.2k I2C pull-ups (N2) and a 470k POS pull-down (N3),
                   # two part types more at Standard PCBA's $1.53 (R23 1k and R39 100k are values it has)
                   "bay-node": [("PCBA review: 2.2k and 470k, two part types more", "feeders", 3.06)]}

# JLC's fees, from its help page "PCB Assembly Cost" (updated 2026-09-09) and the jlcpcb.com
# calculator (2026-10-19, 4-layer, 5 PCBs): what a board's part types and size cost per order
JLC_FEES = {
    "Standard": {"setup": 25.56, "stencil": 8.21, "per type": 1.53, "types": "every unique part type"},
    "Economic": {"setup": 8.18, "stencil": 1.53, "per type": 3.07, "types": "extended part types only"},
    "panel": 8.21,              # PCBA of a panel holding more than one design
    "x-ray": 1.64,              # per assembled board with a leadless part (module pad, QFN, LGA), 1-10 boards
    "pcb 4-layer 100x100": 8.00,        # 5 PCBs at JLC's offer: no engineering fee
    "pcb engineering above 100x100": 25.00,     # per order, on any board or panel above 100 × 100 mm
    "enig over lf-hasl": 12.40,         # 5 PCBs, 100 × 100 mm: ENIG $17.70, lead-free HASL $5.30
}

# What each order could still save (USD per order, against JLC_QUOTE), kept by the JLC-cost owner.
# "obvious": engineering choices without a trade-off for the user (the board's owner applies them);
# "decision": a trade-off for the user.  A lever applied in a board leaves this list for its quote.
JLC_LEVERS = {
    "power-hub": [
        ("rows C and D not fitted (DNP, footprints kept): the rack has 2 rows", 9.68, "decision"),
        ("USB-C J6 (the console; the PD input J1 stays GCT for 48 V): HRO TYPE-C-31-M-12 (C165948, 5 A, 20 V) "
         "instead of the GCT USB4105: a new footprint, re-route, mechanical check", 1.47, "decision"),
        ("JST PH SMD clones instead of JST's S*B / B8B-PH-SM4-TB, no-name ≈ $0.06 (SHOU HAN 2.0-xP WT / LT; "
         "CJT A2001WR / WV at $0.16-0.20 saves about 60 % of this): footprint geometry to check (4 a board)", 2.66, "decision"),
        ("USBLC6-2SC6 second source (UMW C2687116, same SOT-23-6 and pinout) instead of ST's "
         "C7519", 0.25, "decision"),
    ],
    "bay-node": [
        ("9 assembled instead of 10 (8 bays and 1 spare)", 21.08, "decision"),
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
    "bay-node": {5: 13.20, 10: 19.30, 50: 72.80, 100: 108.00},         # 4-layer 74 × 90 mm
    "power-hub": {5: 13.20, 10: 19.40, 50: 85.20, 100: 130.70},        # 4-layer 86 × 100 mm with JLC's rails
                                                                        # (2026-10-20): the $25 fee above 10 PCBs
    "data-port-x4": {5: 13.10, 10: 19.20, 50: 53.80, 100: 73.40},      # 4-layer 100 × 37 mm (2026-10-20): the
                                                                        # $25 fee is back above 10 PCBs
    "data-port-x4-v2": {5: 25.40, 10: 32.20, 50: 92.90, 100: 136.20},  # 4-layer 100 × 70 mm, ENIG (2026-10-20)
    "data-port-x4-v2-base": {5: 13.20, 10: 19.40, 50: 74.90, 100: 111.90},  # the same PCB, lead-free HASL
    # the order panel (electronics/data-port-x4-v2/fab/*-panel-*): a logic and a base on one 100 × 142 mm panel,
    # 4-layer ENIG, mouse bites, one design: no panel fee (2026-10-20, every quantity JLC sells)
    "data-port-x4-v2-panel": {5: 52.00, 10: 62.50, 15: 72.80, 20: 83.30, 25: 93.60, 30: 104.10, 50: 145.60,
                              75: 187.00, 100: 233.50, 125: 280.10, 150: 326.90, 200: 421.15},
    "data-port": {5: 5.20, 10: 6.30, 50: 17.10, 100: 20.90},           # 2-layer 40 × 17 mm
    "camera-pod": {5: 5.20, 10: 6.40, 50: 18.80, 100: 24.20},          # 2-layer 40 × 27 mm
}
JLC_PCB_QTY = (5, 10, 15, 20, 25, 30, 50, 75, 100, 125, 150, 200)
# X-ray per board with a leadless part (module pad, QFN): by the number of boards assembled
JLC_XRAY = ((10, 1.64), (50, 0.82), (200, 0.49), (500, 0.33))
JLC_XRAY_BOARDS = {"bay-node", "power-hub", "data-port-x4", "data-port-x4-v2", "data-port-x4-v2-base"}
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


def jlc_order(name: str, ext: set, hand: set) -> tuple[dict, dict, list[str]]:
    """The quoted PCB and PCBA lines of one board, adjusted for JLC_FINISH and for the hand-soldered
    parts (`hand`) among its extended part types (`ext`)."""
    q = JLC_QUOTE[name]
    pcb, pcba, changes = dict(q["pcb"]), dict(q["pcba"]), []
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
            for r in csv.DictReader(path.open(encoding="utf-8")):
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
                              + (f" + ${pcba['components'] - q['pcba']['components']:.2f} since"
                                 if pcba["components"] != q["pcba"]["components"] else "")
                              + f" (≈ €{quoted_eur:.2f}) for {n} {unit}; catalogue unit prices give €{parts_eur:.2f}"})
    rows.append({"category": "Electronics", "group": "jlc", "item": "JLCPCB shipping: every board in one cart",
                 "supplier": "JLCPCB", "qty": 1, "unit_eur": round(JLC_SHIPPING_USD * USD_EUR, 2),
                 "notes": f"{JLC_SHIPPING} for the whole order (one shipment); import VAT extra"})
    return rows, orders


PER_BOARD = ("components", "SMT", "X-ray")      # PCBA lines that grow with the boards assembled (and Global Sourcing)


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
          "board takes Standard when one of its parts is Standard-only (every ESP32-S3 module, the WS2812B-2020).  "
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


def pcb_price(name: str, n: int) -> tuple[int, float]:
    """(PCBs bought, USD) for n boards: JLC's next quantity, priced from JLC_PCB_PRICE (interpolated)."""
    q = next(x for x in JLC_PCB_QTY if x >= max(n, 5))
    pts = sorted(JLC_PCB_PRICE[name].items())
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
JLC_MIN_BUY = {"data-port-x4-v2": [("C42411119", 32, "L1 minimum purchase (32)")]}
# an order panel: one PCB carrying one board of each design, one PCBA order (panel_order)
PANELS = {"data-port-x4-v2-panel": ("data-port-x4-v2", "data-port-x4-v2-base")}


def _pcba(name: str, orders: dict) -> dict:
    """A board's PCBA lines: as adjusted for the rack's order, or its quote's when it is not in it (an
    order panel's boards: their estimates come from the fab files, nothing to adjust)."""
    return orders[name]["pcba"] if name in orders else JLC_QUOTE[name]["pcba"]


def _per_board_qty(name: str, lcsc: str) -> int:
    return sum(q for l, q, _ in JLC_PARTS.get("boards", {}).get(name, []) if l == lcsc)


def _min_buy(lcsc: str, moq: int, used: int) -> float:
    """USD for the parts of a minimum purchase the boards don't use."""
    return round(max(0, moq - used) * (part_price(lcsc, used) or 0.0) * JLC_PARTS_MARKUP, 2)


def order_cost(name: str, n: int, orders: dict) -> dict:
    """One JLC order of n boards of one design (JLC assembles at least 2), from its quote as adjusted
    (`orders`, electronics()): the PCBA lines paid once (setup, stencil, part types, packaging, a
    minimum purchase's spares, Global Sourcing's $3), per board its parts (the quote's, scaled to JLC's
    price breaks at that quantity, parts_scale), joints, X-ray and Global Sourcing, and the bare PCBs
    at JLC's price for that quantity (the engineering fee is in it)."""
    if name in PANELS:
        return panel_order(n, orders, name)
    q, pcba = JLC_QUOTE[name], _pcba(name, orders)
    k, m = q["assembled"], max(n, 2)
    once = {key: v for key, v in pcba.items() if key not in PER_BOARD and "sourcing" not in key}
    for lcsc, moq, line in JLC_MIN_BUY.get(name, []):
        once[line] = _min_buy(lcsc, moq, _per_board_qty(name, lcsc) * m)
    sourcing = sum(v for key, v in pcba.items() if "sourcing" in key)
    if sourcing:
        once["Global Sourcing"] = 3.0                   # ≈ $3 once, the rest per part bought
    each = {"parts": pcba["components"] / k * parts_scale(name, m), "joints": pcba.get("SMT", 0) / k,
            "x-ray": xray(m) if name in JLC_XRAY_BOARDS else 0.0}
    if sourcing:
        each["sourcing"] = (sourcing - 3.0) / q.get("gs_parts", q["pcbs"])
    pcbs, pcb = pcb_price(name, m)
    total = sum(once.values()) + m * sum(each.values()) + pcb
    return {"board": name, "boards": n, "assembled": m, "pcbs": pcbs, "pcb": pcb,
            "once": round(sum(once.values()), 2), "once_lines": {key: round(v, 2) for key, v in once.items()},
            "per_board": {key: round(v, 4) for key, v in each.items()}, "total": round(total, 2)}


def panel_order(n: int, orders: dict, panel: str = "data-port-x4-v2-panel") -> dict:
    """One JLC order of n order panels (PANELS: one board of each design per panel, n of each; JLC
    assembles at least 2 panels): one setup and stencil, the part types loaded once (the first
    board's: the second's are a subset), the parts of both boards bought together at the breaks they
    reach, each board's joints and X-ray (at the tier of all the boards assembled), the bare panels."""
    first, second = PANELS[panel]
    m = max(n, 2)
    lines = {line for b in (first, second) for _, _, line in JLC_MIN_BUY.get(b, [])}
    once = {key: v for key, v in _pcba(first, orders).items() if key not in PER_BOARD and key not in lines}
    qty = Counter()
    for name in (first, second):
        for lcsc, q, _ in JLC_PARTS.get("boards", {}).get(name, []):
            qty[lcsc] += q * m
    for name in (first, second):
        for lcsc, moq, line in JLC_MIN_BUY.get(name, []):
            once[line] = _min_buy(lcsc, moq, qty[lcsc])
    parts = JLC_PARTS_MARKUP * sum(v * (part_price(lcsc, v) or 0.0) for lcsc, v in qty.items())
    joints = sum(_pcba(b, orders).get("SMT", 0) / JLC_QUOTE[b]["assembled"] for b in (first, second)) * m
    xr = xray(2 * m) * 2 * m
    pcbs, pcb = pcb_price(panel, m)
    total = sum(once.values()) + parts + joints + xr + pcb
    return {"board": panel, "boards": n, "assembled": m, "pcbs": pcbs, "pcb": pcb,
            "once": round(sum(once.values()), 2), "once_lines": {key: round(v, 2) for key, v in once.items()},
            "parts": round(parts, 2), "joints": round(joints, 2), "x-ray": round(xr, 2),
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
    return {"currency": "USD", "usd_eur": USD_EUR, "shipping_usd": JLC_SHIPPING_USD, "n": list(CALC_N),
            "min_assembled": 2,
            "orders": {name: {"total": [o["total"] for o in os], "pcbs": [o["pcbs"] for o in os]}
                       for name, os in out.items()},
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
            "calculator": calculator(orders)}
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
    (out / "README.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    if JLC_PARTS:
        (out / "jlc-parts.md").write_text("\n".join(jlc_parts_md(orders)) + "\n", encoding="utf-8")
    print(f"BOM: {len(rows)} lines, total ~ EUR {total:,.0f} (EUR {total / n_bays:,.0f}/bay)")
    for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1]):
        print(f"  {k:15s} EUR {v:8.0f}")


if __name__ == "__main__":
    main()
