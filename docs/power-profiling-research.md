# Power profiling: µA current traces for Zephyr low-power tests (research, 2026-10-21)

A study, no design change.  Today the rack reads each DUT's current in milliamps, about once a second
(the node's INA226).  Zephyr low-power work wants a trace like a Nordic PPK2's: microamps in sleep,
hundreds of milliamps when awake, and the wake-ups in between.

## Summary

- **The rack can't do it on VBUS, whatever the sensor.**  A dev board's µA sleep current is hidden
  under its own overhead on 5 V: regulator, power LED (1–5 mA), USB-UART, on-board debugger
  (50–150 mA).  A µA trace needs the MCU's own rail, through the board's current-measurement jumper,
  powered by the instrument.
- **Rev A: no hardware change.**
  1. *Firmware:* run the INA226s that are already there (node and DATA ×4 ports) fast.  That gives
     ≈ 5 kS/s, 50 µA (node) or 25 µA (v2 port) steps, captured into the node's PSRAM and fetched as
     CSV.  It shows mA-class activity on VBUS (radio bursts, wake-ups that last ≥ 1 ms), not sleep.
  2. *A PPK2 as a bay accessory:* plug it into a DATA ×4 port, so the PC reaches it over USB/IP.
     Its output drives the DUT's MCU rail through the board's measurement jumper.  That gives
     0.2 µA–1 A at 100 kS/s with Nordic's own tools, and twister's power harness once PPK2 support
     lands upstream.  ≈ €100 for each bay that needs it.
- **Rev B or an add-on board:** a per-bay source meter.  It supplies 1.8–3.6 V to the DUT's MCU rail,
  takes 3–4 shunt ranges switched automatically, and regulates after the shunt, so the DUT sees no
  burden.  An RP2350 streams it over its own USB, through USB/IP.  ≈ $12–15 of parts a channel; weeks
  of design and calibration.

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
generic ADC monitor are proposed upstream.  A rack profiler fits by implementing the same interface:
start a capture, wait, fetch the samples.

## 2. What the rack measures today

| Where | Sensor | Shunt | Step (LSB) | Full scale | Rate today |
|---|---|---|---|---|---|
| Node, the DUT's VBUS (behind the TPS2553) | INA226 (U10) | 50 mΩ | 50 µA | 1.64 A | ≈ 1 Hz (16 averages of the default 1.1 ms conversions) |
| DATA ×4 v2, each port's VBUS | INA226 (0x41/43/44/45) | 100 mΩ | 25 µA | 0.82 A (switch: 0.62 A) | polled by the node |

The INA226 converts in as little as 140 µs (shunt only, continuous).  Its offset (±10 µV max) is
200 µA on 50 mΩ, so it can't resolve µA, only mA.  The burden is small: 25 mV at 500 mA on the node.

## 3. What is worth measuring: VBUS or the MCU rail

- **On 5 V VBUS** you read the whole board.  A Nucleo's ST-LINK draws ≈ 100 mA, and a power LED alone
  draws 1–5 mA, so the MCU's 1–10 µA sleep disappears.  VBUS profiles are still useful for active
  phases (radio, flash writes, peripherals) and as a gross regression check ("sleep fell back to
  20 mA").
- **On the MCU rail** (1.8–3.3 V) you read what Zephyr's power management controls.  Most boards
  have a jumper or header for it: Nucleo IDD (JP5 / JP6), nRF DK's current-measurement header, the
  FRDM boards' MCU-current jumpers.  The instrument then either sits in series (ammeter, with the
  board's own regulator still supplying) or supplies the rail itself (source mode: the board's
  regulator cut off at the jumper).  Source mode is cleaner: no burden, and the debugger's
  back-feeding is out of the picture.
- So a rack profiler needs a short lead from the bay to the DUT's measurement header.  The DATA ×4
  v2's 2 × 6 headers already carry GND and a VREF per port (Dupont).  The single DATA port has no
  header, so its bay would use a separate lead.

## 4. Where in the rack

| Option | Range on what | Cost now | Verdict |
|---|---|---|---|
| a. The node's INA226, fast | VBUS, 50 µA steps, ≈ 5 kS/s | firmware only | **rev A**: mA-class VBUS traces in every bay |
| b. The v2's per-port INA226s, fast | each port's VBUS, 25 µA steps; the node polls them on the lead's I²C (400 kHz, shared) | firmware only | **rev A**, one port at a time (the I²C bus is the limit) |
| c. A PPK2 per bay, through USB/IP | the MCU rail, 0.2 µA–1 A, 100 kS/s | ≈ €100 a bay; a DATA ×4 port (FS bulk, ≈ 400 kB/s) | **rev A option**: the real tool, today, no design |
| d. A per-bay source meter (rev B, or an add-on beside the DATA board) | the MCU rail, 1 µA–500 mA, 100 kS/s | ≈ $12–15 of parts a channel, 2–4 weeks of design and calibration | **rev B**: if more than a few bays need it, or for twister in CI |
| e. On a v2 rev B, per port | its port's VBUS (or the header's rail) | a current-sense amp per port into the RP2354B's ADC; GPIO40–45 are taken (VREFs, ±5 V) | later, if (d) is built: a shared design |

## 5. Circuits compared

| Circuit | Range, rate | Parts (LCSC, 2026-10-21) | Area | Notes |
|---|---|---|---|---|
| INA226, continuous, shunt only, 140 µs | ≈ 7 kS/s raw, ≈ 5 kS/s read at 400 kHz I²C; steps of 2.5 µV over the shunt | C49851, extended, 39 674 in stock, $0.75: **already on both boards** | none | conversion-ready on ALERT (the node's IO39; the v2's ALERTs are wired-OR into INT) |
| INA228 / INA229 (20-bit, 50 µs conversions; INA229 on SPI) | ≈ 20 kS/s, 78 nV steps: a few µA on a 50 mΩ shunt, still not 1 µA | C2887910 / C2846803, extended, **0 in stock**, $4.3–6.3 | VSSOP-10 | a drop-in for the INA226 if stock comes back.  Better steps; no µA without ranging |
| MAX40080 (12-bit, 64-sample FIFO, I²C) | 12-bit steps over a ±10 / ±50 mV input: mA, not µA | C4371034, 0 in stock, WLP-12 | tiny | not for this |
| Zero-drift amp INA190A3 (100 V/V, 35 kHz, 500 pA input bias) into an MCU ADC | 1 µA–500 mA with 3 ranges, 100 kS/s | C2058578, extended, 4 885 in stock, $1.52 (SC-70); the ADC: an RP2350's (12-bit, 500 kS/s) or an ADS7042 (C701642, 1 MS/s, $2.25) | ≈ 15 × 20 mm a channel | the core of option d.  The INA186 (C2058238, $0.86) is cheaper, but its 50 µV offset is too much for µA |
| Range switching | 3–4 shunts (e.g. 0.05 Ω, 2 Ω, 100 Ω, 2 kΩ), MOSFET-switched, comparator-driven | AO3400A-class FETs (basic), a dual comparator, ≈ $1 | | see below |
| The node's ESP32-S3 ADC | 12-bit, noisy and non-linear; continuous DMA mode | | | no: Wi-Fi and USB/IP already load the CPU and the DRAM |

**Range switching without glitching the DUT:**
- In source mode, put the regulator's feedback after the shunt (remote sense).  The DUT's rail then
  stays put whatever the shunt drops, so the high-value range costs no burden.
- Make before break: close the next lower range first, then open the higher one.  A comparator (not
  firmware) switches down within ≈ 1 µs when the voltage over the shunt passes the range's top, with
  hysteresis.
- Clamp across each high-value shunt (a Schottky, or the next range's FET body diode), so a fast
  wake-up never drops more than ≈ 0.3 V while the switch catches up.
- Flag the few samples around each switch and interpolate them (what the JS220 calls suppression).
- Calibrate each range's offset and gain at production.  Store the coefficients in the profiler's
  flash.

## 6. Getting the data out (firmware)

- **Rev A capture (options a, b):**
  - ALERT as conversion-ready drives a GPIO interrupt.  The interrupt reads the shunt register over
    I²C into a ring buffer in the node's 8 MB PSRAM: 60 s at 5 kS/s is 600 kB.  Internal DRAM
    (≈ 1.7 KB free) only holds a small I²C transfer and an HTTP chunk.
  - Commands: `bay power trace start|stop`.  `GET /api/power/trace` returns CSV (time µs, current µA,
    bus mV); there's no live streaming.
  - While a capture runs, the I²C bus is busy: the DATA ×4's expanders and the other ports wait.
  - ≈ 2–3 days of firmware, plus a pytest `PowerMonitor` for twister that drives this API
    (≈ 2 days).
- **PPK2 through USB/IP (option c):** the PPK2 is a USB full-speed CDC device.  At 100 kS/s it streams
  4 bytes a sample, 400 kB/s, about a third of what full-speed bulk carries.  Through the node's USB/IP
  over Wi-Fi that is ≈ 3.2 Mbit/s.  Test it before relying on it: the node's USB/IP buffer pool is
  48 KB of tight DRAM, and other bays share the channel.  Nordic's Power Profiler app and the
  ppk2-api-python library then work on the PC unchanged.
- **Option d's own MCU** (an RP2350, ≈ $1, or the v2's RP2354B on a future revision):
  - it samples with DMA and does the ranging and calibration;
  - it streams over its own USB, through the DATA ×4's hub and USB/IP, so the node only forwards
    packets;
  - speaking the PPK2's serial protocol (the one ppk2-api-python documents) would reuse Nordic's app
    and twister's PPK2 monitor once it lands; a plain CSV / sigrok stream is the fallback.

## 7. Recommendation

1. **Rev A, now:** no board change.  Firmware: the INA226 fast capture (option a, then b) into PSRAM,
   CSV over HTTP, and a twister `PowerMonitor` that drives it.  It answers "did the active current
   regress", not "what is the sleep current".
2. **Rev A, for real µA work:** a PPK2 on the bays that need it, plugged into a DATA ×4 port, its
   output on the DUT's MCU-rail header (document the wiring per board).  First check that a 100 kS/s
   stream holds through USB/IP alongside the bay's other traffic.
3. **Rev B, or an add-on board** if several bays or CI need it: the source meter of option d, one
   channel per bay.  It is a design of its own (ranging, calibration, PPK2-compatible protocol); size
   it once the PPK2 trials show what users actually measure.
4. **Not now:** INA228/229 (no stock at LCSC, and still no µA without ranging), the ESP32-S3's ADC,
   and µA work on VBUS.
