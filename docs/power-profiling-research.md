# Power profiling: µA current traces for Zephyr low-power tests (research, 2026-10-21)

A study, no design change.  Today the rack reads each DUT's current in milliamps, about once a second
(the node's INA226, on the DUT's 5 V VBUS).  Zephyr low-power work wants a trace like a Nordic PPK2's:
microamps in sleep, hundreds of milliamps when awake, and the wake-ups in between.

## Summary

- **Measure the MCU's own power domain, not the dev kit.**  On VBUS the INA226 sees the whole kit:
  - the on-board debugger (ST-LINK, MCU-Link, Nordic's interface MCU): tens of mA;
  - the regulator's quiescent current, the power LED (1–5 mA), USB-UART bridges, sensors.

  An MCU sleeping at 1–10 µA disappears under that.  A useful trace comes from the board's own
  current-measurement point, as a PPK2 does it:
  - *Ammeter mode:* in series with the board's IDD jumper or header; the board's regulator still
    supplies the MCU.
  - *Source mode:* the instrument supplies the MCU domain directly at 1.8–3.6 V, bypassing the
    board's regulator.
- **The VBUS INA226 keeps its job:** the bay's power budget, faults and board-level regressions
  ("sleep went from 30 mA back to 60 mA").
- **Per board** (section 3), each needs a one-time preparation:
  - Nucleos, Nordic DKs, FRDM-MCXN947 and ESP32-C6-DevKitC: a jumper or header made for it.
  - Pico 2: source mode on 3V3, with 3V3_EN tied low.
  - Nano Matter: source mode on 3V3, its LED jumper cut.
  - XIAO: source mode on the battery pads.
  - UNO R4, GIGA R1, Wio Terminal, BeaglePlay: no MCU-only point, so board level only.
- **Rev A:** a PPK2 on each low-power bay, on a DATA ×4 port (the PC reaches it over USB/IP), wired
  to the DUT's measurement point by a short 2-wire lead.  That gives 0.2 µA–1 A at 100 kS/s, Nordic's
  app, and twister's power harness once its PPK2 support lands.  No design work, ≈ €100 a bay.
- **Rev B, if many bays or CI need it:** a "rack profiler" module (section 5).  It is a cheap PPK2
  equivalent that sits on the plate beside its DUT, on a DATA ×4 port, with a fail-safe bypass so the
  DUT keeps its power when the profiler is off.  ≈ $15 of parts and an RP2350, weeks of design and
  calibration.

## 1. What a Zephyr low-power test needs

| | Target | PPK2 | Joulescope JS220 | STM32 PowerShield (X-NUCLEO-LPM01A) |
|---|---|---|---|---|
| Range | ≈ 1 µA sleep to ≈ 500 mA awake | 200 nA–1 A, resolution 100 nA–1 mA by range | nA to 3 A (10 A pulses), 0.5 nA resolution | 100 nA–50 mA live; 1 nA–200 mA static |
| Rate | ≥ 10–100 kS/s, to see wake-ups | 100 kS/s | ≈ 2 MS/s, 300 kHz bandwidth | 3.2 MS/s, 100 kHz bandwidth |
| Burden | small, or none: the DUT must not brown out on a wake-up | none in source mode (0.8–5 V, regulated after the shunt) | 25 mV typical at 1 A | none (it is the supply, 1.8–3.3 V) |
| Ranging | automatic, glitch-free | 5 ranges, automatic | a shunt chain, 0.01 Ω up to 1.1 kΩ, fast switching | automatic |
| Price | | ≈ €100 | ≈ €950 + VAT | ≈ €70 |

Zephyr's twister has a power harness (pytest).  A `PowerMonitor` interface starts a capture, then the
test splits the trace into phases at its peaks and compares each phase's RMS current with the expected
value, within a tolerance.  The STM32 PowerShield is its implemented monitor; PPK2 support and a
generic ADC monitor are proposed upstream.  A rack profiler fits by implementing the same interface.

## 2. What the rack measures today (board level)

| Where | Sensor | Shunt | Step (LSB) | Full scale | Rate today |
|---|---|---|---|---|---|
| Node, the DUT's VBUS (behind the TPS2553) | INA226 (U10) | 50 mΩ | 50 µA | 1.64 A | ≈ 1 Hz (16 averages of the default 1.1 ms conversions) |
| DATA ×4 v2, each port's VBUS | INA226 (0x41/43/44/45) | 100 mΩ | 25 µA | 0.82 A (switch: 0.62 A) | polled by the node |

The INA226 converts in as little as 140 µs.  Its offset (±10 µV max) is 200 µA on 50 mΩ, so it reads mA,
never µA, and on VBUS it reads the whole kit anyway.

## 3. The MCU's measurement point, per board (config/rack.yaml's population and its library)

| Board (bays) | Measurement point | Mode | Preparation | During the measurement |
|---|---|---|---|---|
| NUCLEO-64 MB1136 / MB1367 (A1) | IDD jumper **JP6** (MB2046: JP5) | ammeter across JP6; or source 3.3 V into its MCU side | remove JP6 (MB1367: JP8 on 2–3, VREF+ on VDD) | the ST-LINK stays on USB.  End the debug session (an attached SWD session keeps STOP / Standby from happening) and reset.  For a clean µA floor on MB1136, remove CN2's two jumpers (SWD) |
| NUCLEO-144 MB1137 (A2) | IDD jumper **JP5** (MB1364: JP4; check MB1404's manual) | ammeter across it | remove the jumper; without the meter the MCU is unpowered | as the Nucleo-64 |
| nRF52840 DK, nRF5340 DK (library) | header **P22** (VDD:nRF) | ammeter, Nordic's documented PPK2 setup | cut **SB40** once (solder it back to undo) | the interface MCU stays on.  SW6 "nRF ONLY" disconnects it (a manual switch, so pick one setting per bay) |
| nRF54L15 DK (library) | header **P6** (VDD:nRF) | ammeter | check the DK guide for its revision's bridge.  The external flash moves onto VDD:nRF only if SB9 / SB10 are swapped | as above |
| FRDM-MCXN947 (B1's DATA ×4, library) | **J24** (P3V3_MCU, rev 2.0) and the board's per-rail jumpers / 0 Ω links | ammeter in J24 | remove J24's shunt.  The rails' table (UM12018) tells which 0 Ω link feeds which rail | MCU-Link stays on USB; end the debug session |
| ESP32-C6-DevKitC-1 (library) | header **J5** (the module's 3.3 V; check the board's user guide) | ammeter | remove J5's jumper | the USB-UART bridge stays on; it is outside J5 |
| Raspberry Pi Pico 2 (W) (B1, B3) | the **3V3** pin | source 3.3 V | tie **3V3_EN** (pin 37) to GND, which stops the board's buck | the DATA port turns VBUS off, so USB detaches.  On the W, check in the schematic which rail feeds the radio |
| Arduino Nano Matter (B1) | the **3V3** pin | source 3.3 V (Arduino's own low-power advice) | cut the power LED jumper | VBUS off: the USB bridge is then unpowered |
| XIAO (any) (B3) | the **battery pads** (BAT+ / BAT−) | source 3.7–4.2 V | none (solder two wires, or a JST lead) | VBUS off.  The reading includes the board's LDO (a few µA), as Seeed's own deep-sleep figures do |
| UNO R4 Minima / WiFi (B4) | none: the RA4M1 runs at 5 V | board level (VBUS INA226) | — | the R4 WiFi's ESP32-S3 USB bridge alone is tens of mA |
| GIGA R1 + display (B2), Wio Terminal (A4), BeaglePlay (A3) | none worth it | board level | — | a display, a second radio SoC, a Linux SoC: not low-power targets |

General rules for every board:
- **Debugger.**  An on-board debugger stays powered from USB.  Its SWD and UART lines can feed µA back
  into an MCU that is sleeping or unpowered.  An attached debug session also blocks the deep sleep
  modes.  So flash, end the session, reset, then measure; disconnect SWD where the board allows it.
- **USB.**  The board's own USB keeps its PHY and pull-up alive.  In source mode the rack turns the
  DUT's VBUS off (the DATA port's switch) during the measurement.
- **Wiring.**  The preparation is manual and done once, when a DUT goes into a "low-power bay".  The
  lead is two wires (in and out, or out and GND) from the profiler to the point above.  On a Pico,
  3V3_EN is a Dupont jumper to GND on the board itself.

## 4. Where in the rack

| Option | What it reads | Cost | Verdict |
|---|---|---|---|
| a. The node's INA226, fast (140 µs, ≈ 5 kS/s, captured into PSRAM) | VBUS, the whole kit, 50 µA steps | firmware only | board level: regressions, active phases.  Worth doing, but not "low power" |
| b. The v2's per-port INA226s, fast | each port's VBUS, 25 µA steps | firmware only | as a, one port at a time (the shared I²C bus) |
| c. **A PPK2 per low-power bay**, on a DATA ×4 port, through USB/IP | the MCU domain (section 3), 0.2 µA–1 A, 100 kS/s | ≈ €100 a bay; a DATA ×4 port | **rev A** |
| d. **A rack profiler module** (section 5) on a DATA ×4 port, on the plate | the MCU domain, 1 µA–500 mA, 100 kS/s | ≈ $15 of parts + PCB and assembly, 2–4 weeks of design | **rev B**, if more than a few bays or CI need it |
| e. Inside a node or a DATA board | — | — | no: the lead has to reach the DUT's jumper anyway, and the node has no spare ADC or DRAM |

A bay with a single DATA port has no free USB port for a profiler.  Low-power bays take a DATA ×4
(one port for the DUT, one for the profiler), or a bench PPK2 on the PC.

## 5. A rack profiler, designed for the MCU domain

- **Modes:** ammeter (in series with the board's jumper) and source (supplies the MCU domain), set
  from the PC.
- **Range:** 1 µA to 500 mA (1 A peaks) in four ranges, e.g. 0.05 Ω, 2 Ω, 100 Ω and 2 kΩ.  Steps from
  ≈ 50 nA (top of the 2 kΩ range's resolution) to 0.5 mA.
- **Rate:** 100 kS/s.  The amplifier's bandwidth (≈ 35 kHz) sets what a wake-up edge looks like.
- **Burden:**
  - Source mode: none.  The regulator's feedback is taken after the shunt (remote sense), so the DUT
    sees its set voltage whatever the range.  Output 1.8–3.6 V, and 4.2 V for XIAO batteries, from a
    small LDO whose feedback a DAC trims.
  - Ammeter mode: ≤ 50 mV at full scale on each range.  A Schottky across each high-value shunt caps
    the drop during a range switch at ≈ 0.3 V.
- **Ranging:**
  - comparators switch down within ≈ 1 µs, make before break, with hysteresis;
  - the MCU switches back up;
  - the samples around a switch are flagged and interpolated;
  - each range's offset and gain are calibrated at production and kept in flash.
- **Fail-safe:** a low-resistance bypass (a P-FET held on when the profiler is unpowered), so in
  ammeter mode the DUT keeps its power when the profiler is off or reset.
- **Parts (LCSC, 2026-10-21):**
  - an INA190A3 zero-drift amp (C2058578, $1.52, extended, 4 885 in stock: 100 V/V, 500 pA input
    bias, 2 µV offset);
  - an RP2350A (12-bit ADC at 500 kS/s, DMA, USB);
  - AO3400A-class FETs (basic), a dual comparator, the LDO and DAC;
  - ≈ $15 a unit before PCB and assembly.
  - Not INA186: its 50 µV offset is too much for µA.  Not INA228 / INA229 (0 in stock at LCSC, and
    no µA without ranging), MAX40080 or the ESP32-S3's ADC.
- **Form:** about 40 × 30 mm, pegged on the plate beside its DUT.  A USB-C to a DATA ×4 port, and a
  2-pin lead to the DUT's point.
- **Data:** USB full speed through the DATA ×4's hub and the node's USB/IP; the node only forwards
  packets.  It speaks the PPK2's serial protocol (as ppk2-api-python documents it), so Nordic's app
  and twister's PPK2 monitor work unchanged; a plain CSV stream is the fallback.

## 6. Firmware

- **PPK2 or profiler through USB/IP:** a 100 kS/s stream is 400 kB/s, a third of full-speed bulk and
  ≈ 3.2 Mbit/s over Wi-Fi.  Check it holds before relying on it: the node's USB/IP buffer pool is
  48 KB of tight DRAM, and other bays share the channel.
- **Option a / b:**
  - The INA226's ALERT, set as conversion-ready, drives a GPIO interrupt (the node's IO39; the v2's
    ALERTs are wired-OR on INT).  It reads over I²C at 400 kHz into a PSRAM ring: 60 s is 600 kB.
  - The trace comes out as CSV over HTTP (`bay power trace`).
  - ≈ 2–3 days of firmware.
- **twister:** a pytest `PowerMonitor` that drives the profiler (or a USB/IP-attached PPK2) for a
  bay, ≈ 2 days.  It records which bays are prepared for low-power work, and how (section 3).

## 7. Recommendation

1. **Rev A:** a PPK2 on each low-power bay (a DATA ×4 bay), wired to the DUT's MCU point after that
   board's one-time preparation (section 3).  Document the wiring per board.  Check that the 100 kS/s
   stream holds through USB/IP.
2. **Rev A, firmware:** a twister `PowerMonitor` for those bays.  Later, the INA226 fast capture for
   board-level traces (option a).
3. **Rev B:** the rack profiler module (section 5) once the PPK2 bays show how many units are needed;
   below about five, PPK2s cost less than the design time.
4. **Not:** µA on VBUS, a profiler inside the node, INA228/229 while LCSC has none.
