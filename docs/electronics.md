# Electronics

Four boards (the bay node, the power hub, the drawer's DATA port, the camera pod), all **schematics as code**: `electronics/<board>/design.py`
describes parts (with MPN, manufacturer, LCSC number), the nets their pins
connect to and PCB placement hints.  From that single description
`electronics/tools/` writes a real hierarchical KiCad 10 project (one sheet
per functional block), builds the matching `.kicad_pcb` (footprints, nets,
outline, zones, keep-outs, mounting holes from `config/rack.yaml`), autoroutes
it with Freerouting, and proves the two views agree with KiCad's own ERC and
DRC (schematic parity).

```console
$ tools/kicad.sh bay-node                  # schematic + placed PCB + ERC/DRC
$ tools/kicad.sh bay-node --route --fab    # + Freerouting + Gerbers/CPL/BOM/PDF/renders/STEP/GLB
$ tools/kicad.sh bay-node --ses --fab      # re-import the last Freerouting session (no re-route)
$ tools/kicad.sh bay-node --check          # ERC + read-only DRC of the PCB as it is (what CI runs)
```

`tools/kicad.sh` runs everything in the official `kicad/kicad:10.0-full`
image (and Freerouting in a JRE image), so the only prerequisite is Docker.
The generated projects open in a local KiCad 10 as normal projects.

**Schematics** are drawn, not just generated: every part in `design.py` has
an `sch=` position on the 0.1" grid and the main paths are real wires
(`Sheet.wire("U1.SW", "L1.1")`), so each sheet reads left to right like a
hand-made schematic — power path, then control, notes with the design maths.
Pins left unwired get a short stub with their net label.  The writer adds the
junctions and refuses any wire that would touch another net's pin or wire, and
KiCad's ERC plus the PCB's schematic-parity check catch the rest.

**Stackup** (bay node, 4 layers, symmetric): F.Cu signals + GND pour · In1 solid
GND · In2 power only (+3V3 under the module, the LDO and the logic around them; +5V from the buck
to the LDO input, the DUT switch, the camera fuse and the DUT-side ESD part; the VRACK bus strip
between J1 and J2; +3V3 again under the front edge, fed by a B.Cu track) · B.Cu signals + GND
pour.  No signal is routed on In2.  The board declares JLCPCB's standard
JLC04161H-7628 build (0.21 mm prepreg between F.Cu and In1, 1.065 mm core, 0.5 oz
inner copper) and ENIG; the hub declares 2 layers, 1.6 mm, lead-free HASL
(`stackup` / `finish` in `design.py`, written into the board by `pcbgen.py`).  Before routing,
every GND and supply pin gets a short track to a via of its own on its plane (`fanout_nets` in
`design.py`, `fanout_pads()` in `pcbgen.py`), locked so Freerouting keeps it: no pin depends on
the outer GND pours, which stay as a bonus, stitched to In1.  **No drill under 0.3 mm**: JLCPCB's
0.25 mm option costs ≈ $40 more on a 20-board order (it forces a 4-wire Kelvin test and FR4 Tg155), so
the smallest via is 0.5/0.3 mm (`SMALL_VIA` in `pcbgen.py`, also written into `<board>.kicad_pro` as
the DRC minimum); most vias are 0.6/0.3 mm.  **Every pour connects pads through thermal reliefs**
(0.3 mm gap, 0.4 mm spokes): a GND pad heats up like the pad at the other end
of its part, so small parts don't tombstone in reflow and hand-soldered pins
take solder.  `<board>.kicad_dru` accepts a single spoke where fine-pitch
neighbours leave no room for two.  The LMR51635's hot loop (CIN – VIN – GND) and
its output capacitors sit on small solid top-side islands, with hand-placed
vias to In1, as TI's layout guide asks; the AMS1117's tab gets a solid +3V3
island with vias to In2.  Hand-soldered through-hole pads always get thermal
reliefs, even on solid pours.  Connectors that overhang the outline on purpose
are listed as `edge_parts`: their silkscreen may cross the board edge (the fab
clips it), every other silkscreen check still applies.

How the routing flow keeps ground honest (`electronics/tools/pcbgen.py`):

1. The router sees the inner GND plane and the outer GND pours, and connects
   every other net with real copper.
2. Freerouting trusts the pours to connect the GND pads, but once KiCad fills
   them with real clearances they can break into pieces.  After the SES is
   imported, `stitch_gnd()` first drops a grid of GND vias tying the pours to
   the plane.  Then every fragment still without a via gets one, at the first
   spot where it fits.
3. A GND pad that no connected fill reaches gets a thin track squeezed out to
   connected GND or to a via spot.
4. Pads the router walls in completely are listed under `fanout` in the
   board's `design.py`: a dog-bone via outside the package is reserved
   before routing (a keep-out) and placed after it.  The bay node needs none: its
   `fanout_nets` give every GND and supply pin its via before routing.
5. Finally KiCad's own DRC lists the GND pads still unconnected, and each gets
   a short track to a GND via or to a spot where a small via fits.

> **Status: bay node v0.5 — the row cable becomes 6-pin (VRACK 20 / 28 V, CAN, POS:
> [can.md](can.md)), CAN transceiver and POS token added, GCT USB4105 receptacles, the bay's camera on
> J6 (Arducam Mega SPI + LEDs, PH 8) with the WROOM-1-N8R8 module (octal PSRAM; the board 10 mm longer at the rear), autorouted, checked with Konnect ([review-konnect.md](review-konnect.md)), not yet ordered.  Power hub v0.5 —
> USB-C PD input (AP33772S), 4 layers, rows off until the controller enables them, autorouted,
> checked with Konnect, not yet ordered or quoted.  Camera pod v1.0 — lead, the camera's header and 3.3 V, the
> light, autorouted, not yet ordered or quoted.  DATA port v1.0 — the drawer's USB-C port on a
> 5-wire lead to the node's new J7, autorouted, not yet ordered or quoted.**  On all three boards ERC is clean and DRC reports
> no copper errors, no unconnected items and full schematic parity.  The buck's hot loop, the
> VRACK bus, the hub's input and VRACK pours, its Kelvin sense pair and the USB High-Speed pairs are placed or
> drawn by hand in `design.py`; the rest is the router's draft: before
> ordering, look at it in KiCad and re-run DRC.  Hand edits to the PCB are
> fine — just don't re-run the generator over them (or move the routed board
> aside first).

## Bay node (×1 per unit) — 4 layers, 64 × 90 mm

Sheets: **Power · MCU · USB · DUT power & AUX · Rack bus** — see the PDF in
`electronics/bay-node/docs/`.

| Block | Parts | Notes |
|---|---|---|
| Row cable in/out | 2 × JST PH 6, side entry, SMD (S6B-PH-SM4-TB).  J1 (IN): 1 VRACK · 2 GND · 3 CAN_H · 4 CAN_L · 5 GND · 6 POS in; J2 (OUT) mirrored: 1 POS out · 3 CAN_L · 4 CAN_H · 6 VRACK ([can.md](can.md)) | daisy chain, 2 A per contact; the hub's 1.6 A eFuse protects it; each power pin on a solid island with vias to its plane; every net runs straight across (J1.1 → J2.6, J1.3/4 → J2.4/3): the jumper between nodes lies flat, no twist |
| Rack bus | TCAN1462V, signal improvement (VCC 5 V, VIO 3.3 V, STB tied low) + PESD2CAN on the tap; POS in: 10k + BAT54S + 100k pull-down; POS out: 10k + BAT54S | transceiver right on the pair (stubs 1.8 / 2.3 mm routed, ≤ 20 mm asked), no termination (both are in the hub); a wrong cable (VRACK on a POS pin) costs ≈ 2.5 mA at 28 V |
| Protection | SUD50P06 P-FET + 12 V zener, SMBJ33A, 100 µF/50 V | reverse polarity, hot-plug clamp < 54 V |
| 5 V | LMR51635YDDCR (60 V, 3.5 A, synchronous, 1.1 MHz) + 3.3 µH FXL0630 | TI typical application (SLUSF64B table 8-2): 3 × 22 µF out, 2 × 10 µF + 100 nF in; FB 120k/22k → 5.16 V; EN 1M/100k: on above 13.5 V, off below 10.8 V |
| 3.3 V | AMS1117-3.3 | logic only |
| MCU | ESP32-S3-WROOM-1-N8R8 (8 MB flash, 8 MB octal PSRAM for the camera's frames; the DevKitC-1-N8R8's module), C2913201 | antenna on the rear edge, keep-out on all layers (the footprint's own ±24 mm band); `bench:ESP32-S3-WROOM-1_NoEPVias` (no 0.2 mm vias in the exposed pad: a GND island stitched around it); rated −40…+65 °C |
| DUT power | TPS2553 (RILIM 18k → 1.34–1.52 A), 50 mΩ Kelvin shunt, INA226 @0x40 | +5V → DUT_5V_SW → shunt → DUT_5V (the DUT's VBUS); the INA226 runs from +3V3 and reads the shunt's own sense pads (SHUNT_P/N); default **on** (also without firmware), fault flag to GPIO |
| USB | 2 × FSUSB42 + 74LVC1G32, 2 × USBLC6-2SC6 (100 nF on each VBUS pin: C25, C26), 2 × USB-C GCT USB4105-GF-A-120 | modes in [architecture.md](architecture.md); the classic-mode path (J3 → J4) is hand-routed for High-Speed, see below |
| UI | WS2812B-2020, SERVICE slide switch, RESET/BOOT, UART pads | |
| AUX | J5, JST PH 6, vertical, SMD (B6B-PH-SM4-TB): GND, 3V3 (10 Ω), TX/RX (1k), RESET/BOOT open-drain (2N7002) | by the right edge, plugged from above like J6 and J7 |
| DATA | J7, JST PH 5, vertical, SMD (B5B-PH-SM4-TB): 1 DUT_5V · 2 GND · 3 D− · 4 D+ · 5 GND, in parallel with the DUT receptacle J4 | the lead to the drawer's [DATA port board](#data-port-v10--2-layers-40--17-mm); **one of J4 / J7 at a time** (below) |
| Camera | J6, JST PH 8, vertical, SMD (B8B-PH-SM4-TB): 1 CAM_5V · 2 GND · 3 SCK · 4 GND · 5 MOSI · 6 MISO · 7 CS · 8 LED_K; 33 Ω series on the SPI lines, 2 × USBLC6 on the lead side, AO3400A low side for the LEDs (100k gate pull-down), CAM_5V through a 0.5 A PTC | this bay's Arducam Mega SPI camera and white LEDs (below); `pcb.bay_node.cam` in `config/rack.yaml` is J6's centre |

**USB High-Speed path.** In classic mode a laptop on the front port talks to the DUT through both
muxes, at 480 Mb/s if the DUT can.  Freerouting can't route differential pairs, so that chain (J3 →
U4 → U5 → U6 → U8 → J4) is drawn by `usb_hs_routes()` in `design.py` and locked before routing
(`b.pcb["tracks"]`): coupled pairs on F.Cu over In1, 0.25 mm / 0.15 mm gap (≈ 90 Ω, field-solver
estimate), ESD parts in flow-through (the connector side is its own net, `PC_CONN_*` /
`DUT_CONN_*`, so the signal can only pass through the USBLC6).  Since v0.4 the PC pair runs
straight up the middle of the board from U4 to U5, right under the module; U5 → U6 → U8 → J4 then
runs east.  The two FSUSB42s need one crossover between them (PCPATH_DN hops under PCPATH_DP on
B.Cu); four small bumps on PC_DP, on the straight run, make up the two vias, and J3 → J4 is matched
to 0.1 mm (vias counted as the 1.6 mm they cross).  Moving U4–U8 or the connectors means
re-drawing those tracks.

**Kelvin shunt.** R19 uses `bench:R_1206_3216Metric_Kelvin`
(generated by `electronics/tools/footprints.py` from the stock 1206): sense pads on the inner edge of
each terminal, tied to it by net-tie pad groups, so the INA226 reads the resistor and not the load
copper.

**GPIO map** (v0.5: each signal leaves the module on the edge that faces where it goes): right
column IO41 DUT_EN · IO40 DUT_FLT_N · IO39 INA_ALERT · IO2/IO1 I²C SDA/SCL (the DUT power block
sits in the rear-right corner) · IO42 POS_OUT towards J2 · IO38 LED; bottom row IO47/IO21 UART1
TX/RX · IO12 AUX_RST · IO48 AUX_BOOT · IO13 PC_DET · IO14 MUX_FORCE_PC and the camera on SPI2
through the GPIO matrix, IO11 SCK · IO10 MOSI · IO9 MISO; left column IO15 SVC · IO16 POS_IN ·
IO17/IO18 CAN RX/TX (TWAI) · IO8 the camera's CS · IO7 its light; IO19/IO20 USB; TXD0/RXD0 on test
pads (bottom side).  IO4–IO6 are free.  The WROOM-1's octal PSRAM takes IO35–IO37 and it has no
IO26/IO33/IO34; IO3, IO45 and IO46 (strapping) stay unused.  The map is the one an
ESP32-S3-DevKitC-1 v1.1 (N8R8, the same module) can take as is: every pin on its headers, the
status LED on its own RGB LED's IO38, so the bench stand-in needs no remap.  `firmware/README.md` has the full table, checked against the schematic by
`firmware/tools/check_pinmap.py`.

**Row power VRACK, 20 or 28 V.** The hub negotiates 20 V, or 28 V (EPR), from a USB-C PD charger
and passes it to the rows as VRACK (pin 1 of the row cable; the node's net `VRACK`, then `VIN`
after the reverse-polarity P-FET).  The input stage takes both: the SMBJ33A stands off 33 V
(28 V + 5 % = 29.4 V), the LMR51635 runs from 4.3 to 60 V and its EN divider (1M/100k) starts it
above 13.5 V, and the P-FET and its 12 V gate zener are rated 60 V.  At 20 V a row draws more
current for the same load; the hub's eFuse still caps it at 1.6 A.  The hub keeps every row off
until the PD contract is final, so a node sees one clean power-up.

**USB-C roles:** the front PC port is a sink (5.1 k Rd on CC) whose VBUS is
only sensed; the DUT port is a source (22 k Rp → "1.5 A") with switched VBUS.

**Camera (J6).**  Each bay's camera, an Arducam Mega 3MP SPI (M12 version B0434, ≈ 120° lens) in
the pod under the bay's ceiling, and its 2–4 white 5 V LEDs hang on one ≈ 50 cm PH 8 lead from the
bay's own node.  SPI2 runs in mode 0 at 4 MHz (2 MHz fallback); the 33 Ω series resistors sit at
J6, 45–55 mm of track from the module, i.e. at the source as far as the 50 cm lead is concerned;
GND on pins 2 and 4 keeps a return next to SCK.  CS has a 10k pull-up (deselected before
firmware); the light's AO3400A (5.7 A, 48 mΩ at 2.5 V gate; the 2N7002 is rated 115 mA with a 2.5 V threshold, short of
the LEDs' 150 mA) is held off by its 100k gate pull-down, PWM ≥ 20 kHz (LEDC) or plain on/off, as
slow PWM bands a rolling shutter.  CAM_5V stays behind the 0.5 A PTC: the camera ≈ 120 mA, the
LEDs ≤ 150 mA.  The camera and the LEDs sit on the [camera pod board](#camera-pod-v10--2-layers-40--27-mm),
which runs the Mega from 3.3 V: its MISO is a 3.3 V output.  R35 (680 Ω, footprint fitted, not
populated) stays a fallback for a camera fed 5 V that drives MISO at 5 V: R33 becomes 330 Ω and
R35 goes on, 3.37 V.  No edge had room for a side-entry PH 8 (≈ 21 mm), so J6 is vertical, right of the PC
pair and under J7; the lead rises from it (mated height 8 mm, 14 mm to the drawer).

**WROOM-1 and the longer board.**  The camera's frames want PSRAM: U3 is the ESP32-S3-WROOM-1-N8R8
(8 MB flash, 8 MB octal PSRAM), the bench stand-in's own module, 18 × 25.5 mm instead of the
MINI-1's 15.4 × 20.5.  The board grew 10 mm at the rear (64 × 90, the only side with room in the
plenum): the whole layout moved 10 mm along KiCad's y, so the front edge, the four M3 holes (the
tray's standoffs) and every part keep their place in the tray, and the module's top edge sits on
the new rear edge with its antenna band (the rear 6 mm, ±24 mm around the module: no copper, no
part).  The stock footprint's 0.2 mm vias in the exposed pad are below the boards' 0.3 mm minimum
hole and wick the pad's solder: `bench:ESP32-S3-WROOM-1_NoEPVias` drops them, and the pad sits on a
top-side GND island with eight vias to In1 around it.  AUX (J5) became a vertical PH 6 like J6 and
J7.  The power hub keeps the MINI-1-N8.

**J4 or J7, not both.**  J7 taps the DUT pair on the mux side of U8 (the port board has its own
ESD) and DUT_5V after the switch and shunt.  Both in use at once breaks nothing: the TPS2553 still
caps the sum at ≈ 1.4 A (the INA226 then reads both boards), and two devices on one pair just fail
to enumerate.  But the unused one hangs on the pair as a stub: J4's ≈ 13 mm of track is harmless,
a DATA lead left in J7 while a board runs on J4 is ≈ 40 cm of open cable (Full Speed works, High
Speed likely not).  In the rack the lead stays in J7 and J4 is the bench port: unplug the lead
from J7 to use J4.

## Power hub v0.5 — 4 layers, 76 × 140 mm

One per rack.  It lives in the power box ([mechanical.md](mechanical.md#power-box)); its outline,
holes, row connectors, front LEDs and rear PD input are set in `config/rack.yaml` ›
`pcb.power_hub`, and the box is drawn around them.  KiCad y = 0 is the rear edge (the module's
antenna, the USB-C PD input), y = 140 the front (LEDs, console USB-C).  Why USB-C PD, the charger
and the sequencing: [power.md](power.md).

| Block | Parts | Notes |
|---|---|---|
| USB-C PD in | GCT USB4105 (5 A) → SMAJ30A → 5 mΩ Kelvin shunt → back-to-back IRF7842 NMOS → VRACK, 100 µF / 50 V | the whole rack's current, ≤ 5 A |
| PD sink | AP33772S: VSEL 39 k (asks for 20 V by itself), Rd 5.1 k on CC1/CC2, NTC 10 k by the switch, I²C + INT to the controller, its own LED in the front wall (PD) | the controller asks for 28 V EPR; the chip keeps the contract through controller resets |
| Rows A–D | 4 × TPS26600 (1.6 A, ≈ 5 ms soft start, UV 15 V / OV 33 V, current-limit mode, auto-retry) → 6-pin JST PH S6B-PH-SM4-TB on the left edge | pinout and bus in [can.md](can.md) |
| Row control | SHDN pulled low by 100 k; the controller drives ROW_EN high through 10 k (3.0 V; the datasheet's SHDN range is 0–4 V) | **rows are off without firmware**; on once the contract is final, one after the other |
| Per row | ON (green, from the row's own output through 10 k by the eFuse); FAULT (red) from 3.3 V into the open-drain FLT; FLT also to the controller (100 k pull-up) | Kingbright KPA-3010 side-view LEDs in the box's front wall |
| Row current | IMON 18 k → 1.4 V/A, 1 k + 10 nF to the ESP32's ADC | |
| Controller supply | LMR51635 from VBUS *ahead of* the switch (EN from ≈ 3.9 V; the bay node's layout), B5819W diode OR with the console USB-C's VBUS → +5V, AP2112K (250 mV dropout) → 3.3 V | alive from a contract's first 5 V; runs on the console USB alone for flashing |
| Controller | ESP32-S3-MINI-1 (antenna at the rear edge), RESET / BOOT, native USB on a USB4105 (USBLC6), CTL LED | GPIO map in the controller sheet's notes |
| PD interface | SDA / SCL with 4.7 k pull-ups fed from a GPIO (I2C_PU), INT (a 5 V output) through 15 k / 27 k, VBUS_SENSE 100 k / 10 k to an ADC | the pull-ups come on only once VBUS is up: a USB-powered controller never back-feeds an unpowered AP33772S |
| CAN | TCAN1462V, signal improvement (VCC 5 V, VIO 3.3 V, ±58 V bus pins), two split terminations 2 × 56 Ω + 4.7 nF (56 Ω in all), PESD2CAN | the star centre; nodes carry no termination |
| POS | 4 GPIOs → 10 k → pin 1 of each row output (the outputs have the bay nodes' OUT pinout: 1 POS · 2 GND · 3 CAN_L · 4 CAN_H · 5 GND · 6 VRACK), BAT54S clamp to GND / 3.3 V | survives a wrong cable (VRACK on POS) |

**Layout**, with the bay node's practices: JLC's 4-layer stackup (JLC04161H-7628), ENIG.

* **In1** is a solid GND plane.  **In2** carries power only: VRACK under the input block, along a
  band at y ≈ 39 and down the eFuse column; +3V3 everywhere else, in one piece wrapping around it.
  +5V and the PD nets run on the outer layers.
* Every GND and supply pin gets a via of its own to its plane before routing (fan-out).  The
  eFuses' UVLO / OVP / MODE / RTN / GND pins go straight onto the exposed pad, which has six tented
  GND vias.  The outer GND pours are stitched to In1.
* The input's current runs in top-side pours, kept free of other tracks (`exclusive`): PD_VBUS
  (connector → TVS → shunt), PD_VCC (shunt → Q1, and a 0.8 mm bottom track to the buck), the NMOS
  common source, VRACK (Q2 → bulk capacitor → vias to In2).
* **Kelvin:** the AP33772S's ISENP and VCC leave the shunt's own sense pads and run straight to the
  chip's corner, a few millimetres; VCC's 1 µF sits on its trace.  The NMOS gates share one track
  under both bodies.
* Each eFuse has a top VRACK island on its IN pins and input capacitor, with three vias to In2.
  Each row's output runs in a hand-drawn 0.8 mm track to its connector, its output capacitor and
  its ON LED's resistor.  The SHDN pull-down and series resistor sit just below the eFuse.

The schematic uses the generator's automatic layout (blocks with labelled stubs); it is not drawn
like the bay node's yet.

## DATA port v1.0 — 2 layers, 40 × 17 mm

The drawer's USB-C port for the board under test (×1 per drawer): a small board screwed
components up to the floor of the drawer's rear bay (2 × PT 2.6×8 from above, one each end), the
receptacle's mouth behind a U in the port wall, a 5-wire JST PH lead from its rear edge to
the node's J7 through the drag chain ([cabling.md](cabling.md)).  It replaces the USB-C coupler
and the 90° extension.  Geometry in `config/rack.yaml` › `pcb.data_port`.

| Block | Parts | Notes |
|---|---|---|
| USB-C | GCT USB4105-GF-A-120 (J1) on the front edge at x 30.5, the board's right edge 9.5 mm from it (clear of the chain foot's lock screw); its centre 1.63 mm below the component face, 3.23 mm below the back face | a source, as the node's DUT port: 22 k Rp on CC1 and CC2 ("1.5 A"); the shell to GND |
| ESD | USBLC6-2SC6 (U1) flow-through, 100 nF on VBUS (C1) | right at the receptacle, where the plugs go in |
| Lead | JST PH 5, side entry, SMD (S5B-PH-SM4-TB, J2), rear edge at x 17.5 (its courtyard clear of the USB4105's on a 17 mm deep board): 1 GND · 2 D+ · 3 D− · 4 GND · 5 VBUS | the node's J7 mirrored: the rack's one PH cable type (pin n ↔ pin 6−n) joins them; 5 pins, so a 6-pin row cable (VRACK) cannot go in |

USB 2.0 only: High Speed PC ↔ board in classic mode, Full Speed to the node's ESP32 otherwise.
Both sides are GND pours; routed by Freerouting like the other boards.  JLC: Economic PCBA (one
side, no Standard-only part), ≈ $41 for 15 PCBs with 12 assembled (estimate in `tools/bom.py`).

A review of both boards with the Konnect MCP server (findings, fixes, what is
still open) is in [review-konnect.md](review-konnect.md).

## Camera pod v1.0 — 2 layers, 40 × 27 mm

The board in each camera pod, under the bay's ceiling beside the Arducam Mega (×1 per camera; 2 to
start), so that nothing is crimped or soldered by hand.  Mounted components down (the LEDs face
the bay), 2 × PT 2.6 into the printed pod.  Geometry in `config/rack.yaml` › `pcb.camera_pod`
(KiCad y = 0 is the edge beside the camera).

| Block | Parts | Notes |
|---|---|---|
| Lead | J1, JST PH 8, side entry, SMD (S8B-PH-SM4-TB), mouth out of the right edge: 1 LED_K · 2 CS · 3 MISO · 4 MOSI · 5 GND · 6 SCK · 7 GND · 8 CAM_5V | the node's J6 mirrored: a ready-made "Same direction" PH 8 lead (pin n ↔ pin 9−n) |
| Camera | J2, 1 × 6 pin header, 2.54 mm, SMD (staggered pins), in the Mega's own order VCC · GND · SCK · MISO · MOSI · CS, the names on the silkscreen | an XH 2.54 6-pin → Dupont cable from the Mega's side connector (its own, if it ends in Dupont sockets), plugged on by name |
| 3.3 V | AMS1117-3.3 (U1) from CAM_5V, 10 µF in, 22 µF + 100 nF out | the Mega at 3.3 V (≈ 0.2 W in U1 at 120 mA): MISO at 3.3 V, the node's R35 stays unpopulated |
| Light | 4 × XL-2835UWC-02 (white, 2835, 20–33 lm at 60 mA), each from CAM_5V through 56 Ω to LED_K | ≈ 32 mA each (Vf ≈ 3.2 V), 128 mA; along the edge next to the camera, beside the lens, not around it; the node's AO3400A pulls LED_K low; a thin PETG diffuser 5–10 mm in front, in the pod |

Both sides are GND pours; routed by Freerouting.  JLC: Economic PCBA, ≈ $23 for 5 PCBs with 2
assembled (estimate in `tools/bom.py`).

## Sourcing

Every non-generic part carries `MPN`, `Manufacturer` and `LCSC` fields
(verified against JLCPCB's live library on 2026-10-16 through the
`@jlcpcb/mcp` server — see `tools/jlc_mcp.py`).  Generic passives are
resolved to JLC **basic** parts by `electronics/tools/passives.py` (cached in
`electronics/lib/passives.json`); values were nudged to basic-library E-series
where it didn't matter (e.g. 150k RT, 120k/22k FB).

`--fab` writes, per board:

* `fab/<board>-gerbers.zip` (Gerber X2 + Excellon), ready for JLCPCB/PCBWay;
* `fab/<board>-bom-jlcpcb.csv` (one line per LCSC part) and
  `fab/<board>-cpl-jlcpcb.csv` (placement, corrected to JLC's footprints: see
  [Placement corrections](#placement-corrections));
* `<board>-bom.csv` (detailed, one line per value: MPN, manufacturer, LCSC,
  alternatives);
* `docs/<board>-schematic.pdf`, SVGs, top/bottom/iso renders;
* `fab/<board>.step` and `fab/<board>.glb` (the web viewer uses the GLB);
* `build/<board>-3d.json`: which placed parts the 3D export gives a body.

**3D models.**  Some parts have no model in KiCad's 3D library: the ESP32-S3 module, the JST PH SMD
side-entry connectors, the side-view LEDs, the buttons.  A footprint whose model file is missing
just vanishes from the STEP, the GLB and the renders, without an error.  So the catalog attaches a
vendor model to each of them (`Cat.model`, files in `electronics/lib/3dmodels`, see its README):
Espressif's own STEP for the module, kept in the repo, and LCSC / EasyEDA models for the rest,
fetched by `python tools/fetch_pcb_models.py` into a git-ignored cache.  Run it before `--fab`.
`python tools/pcb_glb.py --check` then lists any placed part still without a body and exits 1;
the viewer conversion falls back to a stand-in of the part's real outline (or fails, `--strict`).

The bay node has no through-hole part since v0.4, and the hub none since v0.5: their JST PH
connectors are the SMD S*B-PH-SM4-TB, and the USB-C receptacles' shield tabs go through
pin-in-paste, all placed by JLC in the same reflow pass.  A part marked `hand_solder=True` in
`electronics/tools/catalog.py` would be kept out of the JLC BOM and CPL, and flagged
"hand-solder, buy loose (LCSC)" in the detailed BOM's `Assembly` column.

## Assembly at JLCPCB

Real quote taken on jlcpcb.com on 2026-10-16 from the `fab/` files (USD,
indicative; shipping, DHL ≈ $27–40, and import VAT come on top).  The full
breakdown is in [`bom/README.md`](../bom/README.md), and `tools/bom.py`
(`JLC_QUOTE`) carries the same figures:

| Board | Order | PCB | PCBA | Total |
|---|---|---:|---:|---:|
| bay node | 20 PCBs, 4-layer ENIG (JLC adds 5 mm edge rails for Standard PCBA), 16 assembled, Standard | $58.90 | $308.81, of which components $181.21 and feeders $65.10 | **$367.71** |
| power hub v0.3 (replaced by v0.4) | 5 PCBs, 2-layer ENIG, 2 assembled, Economic | $25.70 | $48.43, of which components $17.56 and extended parts $15.45 | **$74.13** |

**Power hub v0.5 is not quoted yet.**  It carries the ESP32-S3 module, so it needs Standard PCBA,
X-ray and ENIG, like the bay node.  `tools/bom.py` carries an estimate built the same way: ≈ $213
for 5 four-layer PCBs with 2 assembled.  That is ≈ $55 of PCB (the 4-layer engineering fee),
$52 of components at catalogue prices, and $3 per extended part type (19).  The AP33772SDKZ-13-FA02
was out of stock at LCSC on 2026-10-18: check JLC's global sourcing, or consign a reel.  Re-quote
before ordering.

Two changes were made after that quote and are not re-quoted (`JLC_FINISH`
and `jlc_order()` in `tools/bom.py` apply them, indicatively):

* (v0.3 only) **Power hub in lead-free HASL** instead of ENIG.  v0.4 has the
  ESP32 module and goes back to ENIG.
* **Through-hole connectors soldered by hand**: node J1 J2 J6 (JST PH),
  hub J1 (JST VH) and J2–J6 (JST PH).  JLC's hand-soldering fee ($3.61 per board
  order) goes, and so do the loading fees of these extended part types (pro
  rata of the quoted fee: one type on the node, −$3.43; two on the hub,
  −$4.41).  The connectors cost the same bought loose from LCSC, plus LCSC's
  shipping.

That brings the order to ≈ **$360.67** for the nodes and ≈ **$49.51** for
the hub.  The quote's "manual assembly" lines are kept: re-quote to see
whether they go too.

Rev 0.2 came after the quote as well and is not re-quoted: on the node the
LMR51635 + FXL0630 replace the TPS54360B, its B560C Schottky, the FXL1040 and
the compensation network (≈ +$0.70 of parts per board, one extended part type
fewer), and the JST PH connectors cost less than the VH ones.  Rev 0.3 (the
Konnect review) adds no part type: the hub's power pours and thermal vias are
copper only, and the node's Kelvin shunt is the same LCSC part on a new
footprint.  Rev 0.4 puts the node's JST PH connectors back in JLC's hands, as SMD parts: two
extended part types (C295747, C265405, ≈ $3 loading fee each per order), ≈ +$0.86 of parts per
board over the through-hole ones, and nothing left to solder by hand on the node.  Rev 0.5 (the rack
bus) turns J1/J2 into the 6-pin S6B (C265405, already the AUX connector: no new type) and adds three
extended part types, the CAN transceiver (TCAN1462V, C7399456; alternate TCAN1044AV, C3234993), the PESD2CAN (C75176) and the BAT54S (C7420333).
Its USB-C receptacles become the GCT USB4105-GF-A-120 (C5184243, the part the user chose for the
hub: 5 A on VBUS), one extended type for another.  In all ≈ +$9 of loading fees per order and
≈ +$2.38 of parts per board, $1.44 of it for the two GCT receptacles.  `JLC_SINCE_QUOTE` in
`tools/bom.py` adds both to the node's order: ≈ **$387.73** for 16 assembled nodes, against
$364.10 for v0.4.  Re-quote before ordering.

* **Bay node: Standard PCBA.** JLC can only place the ESP32-S3-MINI-1 module
  (C2913206; the node's WROOM-1-N8R8 since the camera, C2913201) and the WS2812B-2020 LED with its Standard PCBA service, not
  Economic, so the node pays Standard fees (setup $25.75, stencil $8.27, X-ray
  $13.28 in the quote above).  These parts are flagged `standard_only` in
  `electronics/tools/catalog.py`, which `tools/bom.py` reads.  The WS2812C-2020-V6
  (C55109522) is Economic-capable, but the module keeps the board on Standard
  anyway.  Check the WS2812C pinout against the WS2812B-2020 footprint before
  swapping it in.  Every ESP32-S3/S2 module at JLC is Standard-only; the
  Economic-capable Ai-M62-32S (BL616) is evaluated, and kept for a v2, in
  [mcu-alternatives.md](mcu-alternatives.md).
* **Power hub: Standard PCBA since v0.4** (the ESP32 module).  Its 100 µF bulk capacitor uses
  C3352, the Economic-capable listing of RVT1H101M0810, like the node's.
* **No Basic drop-ins.** Every extended part was checked against JLC's Basic
  library (October 2026): none has a Basic equivalent with the same ratings
  and footprint, so the extended-part loading fees stay (the node's $65.10 of
  feeders, the hub's $15.45).  Near misses were rejected:
  * SS54 Schottky: 40 V, below the buck's 60 V input rating;
  * AO3401A P-FET: 30 V, on a 24 V bus with transients up to 53 V;
  * 100 mΩ / 250 mW 1206 shunt: INA226 full scale would drop to 0.82 A, below
    the 1.5 A DUT limit.
* **One BOM line per LCSC part.** JLC refuses several lines that resolve to
  the same part ("Multiple lines in the BOM have been matched to the same
  part") and deselects them, so the JLC BOM merges them: J3/J4 USB-C,
  SW1/SW2, U5/U6 on the node; D3 + D11–D15 on the hub.  Merged lines carry
  the MPN as comment.

### Placement corrections

JLC does not place KiCad's footprint: for each LCSC part it takes its own
(EasyEDA) footprint, puts that footprint's origin on the CPL's Mid X/Y and
turns it by the CPL rotation.  Where JLC's footprint has a different 0° or a
different origin from KiCad's (connectors anchored on pin 1, SOT-23 drawn the
other way round, ICs drawn with pin 1 at the bottom), the part lands rotated
or shifted.  `JLC_CPL_FIX` in `electronics/tools/build_board.py` corrects the
CPL per LCSC part: an extra rotation (degrees, counter-clockwise) and an
origin offset in the KiCad footprint's own axes, both turned with the part.
The export stops if a part listed there changes footprint or moves to the
bottom side.

The values were worked out on 2026-10-16 by fitting each part's EasyEDA
footprint pads (`https://easyeda.com/api/products/<LCSC>/components`) onto
the KiCad pads, pin by pin, then checking that the bodies overlap and that
diodes, LEDs and electrolytics keep their cathode or + side.  JLC's
placement preview had shown the first three rows wrong before the fix; the
others come from the fit alone.  The through-hole connectors are soldered by
hand now and are no longer in the CPL, so their rows (JST PH/VH) don't
matter for JLC: they stay in the table for an order where JLC places them.

| LCSC part | Refs | Correction | Status |
|---|---|---|---|
| C173752 JST S2B-PH-K | node J1 J2 J6 | 180°, +1.00 mm x | was wrong in the preview; hand-soldered now, not in the CPL |
| C6186 AMS1117 SOT-223 | node U2 | 180° | looked wrong in the preview; confirm the fix |
| C165948 HRO TYPE-C-31-M-12 | node J3 J4 until v0.4 | −1.57 mm y | not on the boards since v0.5 |
| C2913206 ESP32-S3-MINI-1 | hub U4 (node U3 until the camera) | +2.55 mm y | to confirm |
| C2913201 ESP32-S3-WROOM-1-N8R8 | node U3 | +3.63 mm y | to confirm |
| C471518 JST B6B-PH-SM4-TB | node J5 | 180°, −0.63 mm y | to confirm |
| C431540 MSK12C02 | node SW3 | −0.25 mm y (lines up the pins; JLC's body outline then sits 0.25 mm off KiCad's) | to confirm |
| C45262770 LMR51635 TSOT-23-6 | node U1 | 270° (same EasyEDA footprint as C7519) | to confirm |
| C11355 FSUSB42 MSOP-10 | node U5 U6 | 270° | to confirm |
| C49851 INA226 VSSOP-10 | node U10 | 270° | to confirm |
| C7519 USBLC6-2SC6 SOT-23-6 | node U4 U8 U12 U13, data port U1 | 270° | to confirm |
| C55266 TPS2553 SOT-23-6 | node U9 | 180° | to confirm |
| C10096 74LVC1G32 SOT-23-5 | node U7 | 180° | to confirm |
| C8545 2N7002 SOT-23 | node Q2 Q3 | 180° | to confirm |
| C7503186 SUD50P06 TO-252 | node Q1, hub Q1 | −1.89 mm x | to confirm |
| C544399 TPS26600 HTSSOP-16 | hub U1–U5 | 270° | to confirm |
| C160315 JST B2P-VH | hub J1 | +1.98 mm x | hand-soldered, not in the CPL |
| C295747 JST S2B-PH-SM4-TB | node J6 until the camera | none (fit: +0.08 mm y, left alone) | not on the node since the camera |
| C495548 JST B8B-PH-SM4-TB | node J6 | −0.63 mm y | to confirm |
| C20917 AO3400A SOT-23 | node Q4 | 180° | to confirm |
| C265405 JST S6B-PH-SM4-TB | node J1 J2 J5, hub row outputs | 180° | to confirm |
| C7399456 TCAN1462V SOIC-8 (alternates C3234993 TCAN1044AV, C3234095 TJA1462AT) | node U11, hub U6 | 270° | to confirm |
| C75176 PESD2CAN SOT-23 | node D5, hub D9 | 180° | to confirm |
| C7420333 BAT54S SOT-23 | node D6 D7, hub POS clamps | 180° | to confirm |
| C5184243 GCT USB4105-GF-A-120 | node J3 J4, hub USB-C, data port J1 | −1.30 mm y | to confirm |
| C265104 JST S5B-PH-SM4-TB | data port J2 | 180°, +0.14 mm y | to confirm |
| C265085 JST B5B-PH-SM4-TB | node J7 | 180°, −0.62 mm y | to confirm |
| C265121 JST S8B-PH-SM4-TB | camera pod J1 | none (fit: −0.03 mm y) | to confirm |
| C2843876 XL-2835UWC-02 | camera pod D1–D4 | +0.24 mm x | to confirm |
| C41417363 HX PZ2.54-1x6P TP-YQ | camera pod J2 | 270° | to confirm |

Checked by the fit and left alone: resistors, capacitors and the PTC (0603,
0805, 1206), the electrolytics (+ pad), the diodes and LEDs (cathode side),
the WS2812B-2020, the FXL0630 inductor (C167219) and the TS-1187A buttons.  The green
LED C2297 numbers its pads the other way round (pad 2 is the cathode), but
its cathode sits where KiCad's pad 1 is at 0°: don't "fix" it from the pad
numbers.

To confirm a part, upload the Gerber zip, BOM and CPL at jlcpcb.com, and in
the "Component Placement" step look at it in JLC's 2D and 3D preview:

1. The body sits over its pads, centred (a shift of half a pin pitch means
   an origin offset is wrong).
2. Pin 1, the cathode bar or the + side lines up with the board's silkscreen
   mark.
3. Side-entry connectors (SH, USB-C) open towards the board edge.

If a part is off, rotate or move it in JLC's editor until it fits, then copy
that change into `JLC_CPL_FIX` (add the extra degrees; an offset measured on
the board has to be turned back into the footprint's axes) and re-export with
`tools/kicad.sh <board> --check --fab`, so the next order needs no hand
correction.  Mark the row confirmed here once a preview shows it right.  A new
LCSC part needs the same check: until it is in the table it is placed exactly
as KiCad has it.

## Custom library

`electronics/lib/bench.kicad_sym` holds the two symbols the stock library
lacks: TPS2553DBV, and LMR51635 (KiCad's LMR51430 has another pinout).  All footprints and 3D models come from KiCad 10's
standard libraries.

## Future: chip-down ESP32-S3 (v2)

Every ESP32-S3 *module* (MINI-1, MINI-1U, WROOM-1, all memory variants) is
Standard-PCBA-only at JLC, which is what keeps the bay node off Economic
PCBA.  The bare **ESP32-S3FH4R2** (C3013940, ≈ $3.67, QFN-56 7 × 7 mm, 4 MB
flash + 2 MB PSRAM in package) is Economic-capable and is the same SoC, so the
Zephyr firmware (Wi-Fi, `uhc_dwc2` USB host) carries over unchanged.

* Saves ≈ $35–45 per 16-node order: about $1 per chip, plus Economic instead
  of Standard setup and stencil fees, and no added edge rails.  That is ≈ €2.5
  per node, more for larger runs.
* Costs: 40 MHz crystal, antenna (PCB trace or ceramic chip) with a matching
  network to tune on a VNA, extra decoupling, and the loss of the module's
  radio certification.  4 MB flash is enough for the USB/IP firmware with
  dual-slot updates.
* Not worth the RF risk at 16 nodes; worth revisiting for ≥ 50.

Alternatives considered:
* ESP32-S2FN4R2: cheaper, Economic, Zephyr Wi-Fi, but `uhc_dwc2` is not yet
  validated on the S2.
* ESP32-C3/C5/C6: no USB OTG, so no USB host.
* nRF54LM20 + nRF7002, or ESP32-P4 + C6: USB host supported, but two chips and
  more cost.
* NXP RW612: good Zephyr support, but no module stocked at LCSC.
