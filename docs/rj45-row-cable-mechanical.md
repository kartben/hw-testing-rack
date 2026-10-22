# RJ45 row cable: mechanical feasibility (research, 2026-10-22)

The mechanical side of [rj45-row-cable-feasibility.md](rj45-row-cable-feasibility.md), which has the
electrical side and the verdict.  A study, no change to the parts yet.

SolidCraft checked each case on exact solids of today's parts: the tray, the shared ladder, the
drawer, its chain and foot (drawer closed and pulled out), the power box and the base ladder.  The
jacks, plugs and cords are stand-ins at the sizes below.  Pulled out is the tight case; with the
drawer closed everything clears.

## Verdict

- **It fits.**  Low-profile jacks go where J1, J2 and the hub's row connectors are today.  The tray
  and ladder windows don't change.
- **Two other parts change:**
  - the drawer's stroke goes from 140 to 128 mm, so the chain foot stays clear of the bay-to-bay cord;
  - the base ladder's diagonal is reversed, so it clears row A's feed plug.
- **One cable changes route:** the DATA lead's U-turn in front of the open drawer's chain mouth lies
  flat and passes under the cord.
- **The power box** gets four RJ45 cut-outs in its left wall and a notched lid rim.
- **The bay-to-bay cords are made to length, 12 cm.**  A 0.15 m stock cord leaves 28–30 mm of slack,
  and there is nowhere to put it.  The feeds are stock: 0.25 / 0.5 / 0.75 / 0.75 m for rows A–D.
- **Mechanical effort: about 3 days** after the node and hub layouts, regeneration included
  (section 5).  That fits rev B, as the electrical study recommends.

## Model

- **Jack:** at most 11.0 mm above the PCB, plug axis 5.6 mm above it, tab down (latch towards the
  board).  It is modelled 21.3 deep × 15.9 wide, larger than the RJ-064-1 (C7205199, 15.3 × 14.7 ×
  10.75), so the margins below are conservative.
- **Plug:** body 11.7 × 8 mm with the latch 2.5 mm under it.  8 mm of it stands out of the jack, then
  a 15 mm boot (Ø9 → Ø4.6).  The cord starts 23 mm from the jack's mouth.
- **Cord:**
  - slim, Ø3.6, bend radius 14.4 (4 × OD);
  - standard, Ø5.5, bend radius 22, where it changes a margin.

## 1. Height

| Where | Room above the PCB | Jack ≤ 11.0 mm | Standard jack, 13.3 mm |
|---|---|---|---|
| J1, under the tray's left ledge (underside z 20.6) | 11.5 | 0.5 clear | 1.8 into the 2.5 mm ledge: a hole through it |
| J2, under the drawer (z 23.1) | 14.0 | 3.0 clear | 0.7 clear |
| Hub, under the box lid (z 32.6) | 12.0 | 1.0 under the lid, 0.5 beside the notched rim | 1.3 into the lid |

- C1 and the gussets under the ledge are clear in every case.
- **So the jack must be at most ≈ 11 mm high.**  The RJ-064-1 (10.75) fits.  The 12.6 mm THT standard
  doesn't.
- **The latch must be under the plug (tab down).**  The IN plug passes the windows, whose top is the
  ledge's underside at z 20.6.  A tab-up latch reaches z 21.2.
- **Recessed jacks** (in a board cut-out) lower the plug.  Its latch then drops below the windows'
  bottom (z 7.5), so the windows would have to come 2 mm lower.

## 2. Bay to bay

The OUT plug (B2's J2) sits in B2's plenum, x 78–101.  The IN plug (B3's J1) crosses B2's right
wall, the shared ladder and B3's left wall: its body sits in the windows and its boot in B2's
plenum, x 147–162.  Between the boots the cord runs 46 mm straight, at y 20, z 14.7.

- **Windows: no change.**  With its latch the plug is 11.7 × 10.5.  The tray windows are 26 × 13.1
  (y 3.5–29.5, z 7.5–20.6) and the ladder's 26 × 20.  Clearances:
  - 0.7 mm from the latch to a tray window's bottom;
  - 1.2 mm to the ladder;
  - 1.9 mm to a window's top.
- **The chain foot with the drawer pulled out.**
  - It reaches y 12 at x 133–145, and the IN boot ends at x 146.8.
  - A cord leaving the boot at y 20 runs into it (40 mm³ of overlap).
  - The cord can't dodge it: there are 1.8 mm between the boot and the foot.

  | Option | Change | Result |
  |---|---|---|
  | **A. J1 / J2 where they are (KiCad y 73), stroke 128** | `drawer.travel` 140 → 128 | **the foot stops at y 24: 2.2 mm from the cord** |
  | B. stroke 132, the foot's fin 4 mm shorter | `travel` and `chain_parts.scad` (FIN_Y[0] −5 → −1; the end piece's first hole stays 5 mm behind) | 2.2 mm, 4 mm more stroke than A, one more change |
  | C. IN at the node's front-left corner (KiCad y 82) | node | rejected: the jack lands on the front-left M3 hole (3.5, 86.5) and on D4, and the cord still clips the foot unless its fin is cut |
  | D. stroke kept, the cord dropped to today's PH corridor (y ≤ 9.4, z ≤ 10.8) | none | rejected: from the boot it must drop 5.7 mm and come 12 mm forward in the 5.8 mm before the foot |

  **A is the pick: one number.**  The drawer gives up 12 mm of stroke.  That is less sweep under the
  camera pod, so no new conflict.  A standard Ø5.5 cord keeps 1.25 mm from the foot.
- **The DATA lead.**
  - Today its U-turn in front of the open drawer's chain mouth rises 4 mm, to pass over the PH cable on
    its tie anchors.
  - Raised like that, it hits the RJ45 cord (−1.4 mm).  Laid flat (`lead_to_board` lift 0), it passes
    2.35 mm under the cord (1.4 mm under a Ø5.5 one).  Only the viewer and the cabling notes change.
- **Tie anchors** (`tray.scad` JUMPER_TIES): no longer needed.  Drop them, or leave them: they are clear.
- **Cord length.**
  - Tip to tip, the hop takes 120 mm: 91.8 mm mouth to mouth, plus 2 × 14 mm inside the jacks.
  - A stock 0.15 m cord leaves 28–30 mm of slack, and the free space can't take it.  With the drawer out
    that space is x 101–147, y 3–23, z 10–21.  An S-bend or a hump at R 14.4 absorbs under 6 mm; a
    loop needs 90 mm.
  - The cord can bow towards the rear between x 101 and 130, which is free in every drawer position.
    An 8 mm bow takes about 5 mm more, and that is the most.
  - **So order 12 cm cords made to length**, or crimp them: 26 AWG stranded patch cable,
    pass-through plugs.

## 3. Feeds from the power box

- **Hub:** four jacks on its left edge at the 17.5 mm row pitch, 2.8 mm apart.
- **Box, left wall:**
  - four 13 × 11.5 cut-outs.  Each starts 1.4 mm below the PCB top, because the plug's latch hangs
    below it, outside the board.  That leaves 1.9 mm of wall above;
  - the row letters engraved there have no room left.  They move to the lid's top face, debossed over
    each jack;
  - the lid's rim is notched over each jack, 0.5 mm all round.
- **Plugs:** they leave through the base ladder's window, 1.28 mm above its bottom band (z 22).  The
  boots end 8.8 mm outside the rack's left face.
- **Base ladder:**
  - Its diagonal runs from the window's front-bottom to its rear-top, through row A's plug (150 mm³).
  - **Reversed** (front-top to rear-bottom, in `windows_2d` for the base), it clears all four plugs.
    It is the same triangulation.
  - The other way out would be moving the hub's jacks at least 12 mm back.  Row D's jack would then hit
    the RST / BOOT guide tubes, so the buttons would move too.
- **Route:**
  - Each cord turns up at R 14.4 into its own lane, 26–38 mm off the left face, 4 mm apart.
  - It climbs the rack's left side and turns in to the first bay's IN plug.  That boot ends 11.4 mm
    outside the left face.
  - Standard Ø5.5 cords (R 22) need lanes about 40–50 mm off the face.
- **Lengths**, tip to tip on that route:

  | Row | Route | Stock cord | Slack |
  |---|---|---|---|
  | A | 174 mm | 0.25 m | 76 mm |
  | B | 344 mm | 0.5 m | 156 mm |
  | C | 517 mm | 0.75 m | 233 mm |
  | D | 689 mm | 0.75 m (or 1 m) | 61 mm (311) |

- **Slack:** one loop per cord, Ø 40–60 (above the bend radius).  Strap it to the left ladder's
  front post in the base cell, or clip it with a small printed clip on that post.

## 4. Plugging and unplugging

- **Fit the cords with the drawers removed**, as with today's PH jumper.  Pulled out, a drawer still
  covers the front of its plenum, where the plugs are.  The neighbouring bays stay in place.
- **OUT plug (J2):** its latch is under the plug, at the node's right edge.  With the drawer removed
  it is reached from above.
- **IN plug (J1):** its latch sits inside the ladder's window.  Press it with a small screwdriver from
  the bay on the left.  Cords with pull-tab or snagless boots make that easier.
- **Feeds:** the hub's plugs are reached through the base ladder's window, from the rack's left side.
  The first bay's IN plug is reached from the left side too: its boot stands out of the face.

## 5. Changes and effort (mechanical, rev B)

| Part | Change | Effort |
|---|---|---|
| `config/rack.yaml` | `drawer.travel` 140 → 128.  The tray's stop pin and deck slot follow; docs/mechanical.md and architecture.md mention 140 | 0.5 h |
| `tray.scad` | drop the tie anchors (optional) | 0.5 h |
| `ladder.scad` | the base ladder's diagonal reversed | 1–2 h with the checks |
| `power_box.scad` | four RJ45 cut-outs, the row letters on the lid, rim notches | 2–3 h |
| `tools/webscene.py` | RJ45 jumpers (straight, 12 cm), feeds in their lanes with their loops, jacks and plugs, the DATA lead's U-turn flat | ≈ 1 day |
| `tools/bom.py` | the cords: 12 cm jumpers, one per hop; feeds of 0.25 / 0.5 / 0.75 / 0.75 m.  Drop the PH leads | 2 h |
| docs | cabling.md, mechanical.md; the assembly notice goes in its backlog | 0.5 day |
| regeneration and checks | STLs (tray, base ladder, power box), the viewer, the tests, SolidCraft | 0.5 day |

**About 3 days in all.**  It starts once the node's and the hub's RJ45 footprints are placed
(`pcb.bay_node`, `pcb.power_hub` in config/rack.yaml, Electronics).
