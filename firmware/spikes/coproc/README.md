# Co-processor spike: what Zephyr gives an RP2350 today

A build-only spike for the DATA ×4 v2 co-processor (an RP2354B behind the
drawer's hub, [docs/data-x4-v2-research.md](../../../docs/data-x4-v2-research.md)).
It answers "how much of our own firmware would be ours?" with code, not
guesses; the findings are in
[docs/coproc-firmware-research.md](../../../docs/coproc-firmware-research.md).
**Built, never run**: there is no RP2350 board on hand.

It is not the bay node and not a product: a Pico 2 (RP2350A), the buses of
the v2 research on GPIO2–9 (CH1–8), and a shell on USB.

| Piece | How | Our code |
|---|---|---|
| 4 CDC-ACM ports (shell, con1–con3) | Zephyr's `device_next` stack, devicetree nodes | 0 (the USB device setup in `main.c`: 25 lines) |
| con1 = UART1 on GPIO8/9 | `zephyr,uart-bridge` (devicetree only), line coding passed through | 0 |
| con2 = a PIO UART on GPIO2/3 | `pio-uart.overlay`: same bridge, **needs PR #118562** | 0 |
| Emulated TMP103 at 0x70 on I2C0 (GPIO4/5) | `zephyr,i2c-target-tmp103`, fed by the die temperature | 0 |
| Emulated 256-byte EEPROM at 0x50 on I2C1 (GPIO6/7) | `zephyr,i2c-target-eeprom` | 0 |
| The node's link: a vendor bulk interface | `src/link.c`, a `usbd` class of our own | 169 |
| 8-channel capture, edge trigger, up to clk_sys (150 MS/s) | `src/la_pio.c`: a 3-instruction PIO program assembled at run time, one DMA channel | 133 |

Shell commands (on the "coproc shell" CDC-ACM port; never run):

```console
uart:~$ la cap 150000000 262144 4 rise     # 256 Ki samples at 150 MS/s after a rising edge on GPIO4
uart:~$ la dump 0 32                       # hex: one byte per sample, bit 0 = CH1 (GPIO2)
```

## Build

Zephyr main f78c4de (2026-10-19), Zephyr SDK 1.0.1, warnings as errors.  Not in the rack's workspace
(`firmware/west.yml` only takes the ESP32 modules) nor in CI: use an upstream workspace with
`hal_rpi_pico`, `cmsis_6` and `cmsis` (`west update hal_rpi_pico cmsis_6 cmsis`).

```bash
west build -b rpi_pico2/rp2350a/m33_0 firmware/spikes/coproc -- -DCONFIG_COMPILER_WARNINGS_AS_ERRORS=y
```

| Target | FLASH | RAM (256 KB of it is the capture buffer) |
|---|---|---|
| `rpi_pico2/rp2350a/m33_0` | 100,320 B | 301,880 B |
| `rpi_pico2/rp2350a/hazard3_0` (RISC-V) | 123,160 B | 302,280 B |
| `rp2350b_core/rp2350b/m33_0` (48-GPIO package, like the RP2354B) | 102,284 B | 305,776 B |
| m33_0 + `pio-uart.overlay`, main | 101,760 B | 302,440 B: builds, but the bridge would stay silent |
| m33_0 + `pio-uart.overlay`, PR #118562 (21deb77) | 102,728 B | 301,096 B |

Unmodified code on both cores: the Hazard3 build is the same source.

## What building it found

1. **TMP103 target vs its sensor.**  `zephyr,i2c-target-tmp103` with a
   `sensor` initialises at `CONFIG_I2C_TARGET_INIT_PRIORITY` (60), before the
   sensor (`CONFIG_SENSOR_INIT_PRIORITY`, 90): the build's init-order check
   fails.  `prj.conf` sets the target priority to 91.  Upstream fix: a
   draft, if the user wants it.
2. **`zephyr,uart-bridge` ignores a peer without the interrupt API.**  On
   main the PIO UART only polls, yet a bridge to it builds and would never
   move a byte: `uart_bridge_pm_action()` does not check the return of
   `uart_irq_callback_user_data_set()`.  Upstream fix: fail the bridge's init
   with `-ENOTSUP` (draft).
3. **`pio0` is a pico-sdk macro.**  `DT_NODELABEL(pio0)` breaks as soon as
   `hardware/pio.h` is included; the overlay adds its own labels
   (`coproc_pio`, `coproc_dma`).
4. **Zephyr's DMA API has one block, no ring, no chaining** (`dma_rpi_pico.c`):
   a capture with pre-trigger samples needs a DMA ring, so it programs
   pico-sdk's `hardware_dma` directly on channels reserved with
   `dma_request_channel()`, as PR #118562 does for the PIO UART's RX ring.
5. **Pins stay owned by their function.**  PIO reads every pin's input, so
   the capture samples the I2C and UART pins as they are; the others only
   need their input enabled (and, on the RP2350, the pad isolation lifted).
   A PIO pinmux in the devicetree would take the pin away from I2C.

## Not covered

- No vendor-protocol client: the node's host side of `link.c` (a `usbh`
  class on the ESP32-S3) is the other half and is not written.
- No pre-trigger, no pattern trigger, no 16 channels, no RLE, no SUMP.
- Nothing measured: DMA throughput at 150 MS/s, I2C target timing and USB
  throughput need a board.
