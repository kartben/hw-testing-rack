/*
 * Capture spike: eight consecutive pins sampled by one PIO state machine at
 * up to clk_sys (150 MS/s on an RP2350), moved to RAM by one DMA channel,
 * after an optional edge on one of them.
 *
 * The PIO program is three instructions, assembled at run time so that the
 * trigger pin and edge are patched in:
 *
 *	wait !edge pin T	; only with a trigger
 *	wait edge pin T
 *   .wrap_target
 *	in pins, 8		; autopush every 32 bits: 4 samples per word
 *   .wrap
 *
 * What a full analyzer adds (README.md): pre-trigger samples (a DMA ring and
 * a second state machine watching the trigger, which Zephyr's DMA driver
 * cannot do: one block, no ring, no chaining), pattern triggers, 16 channels
 * and run-length encoding.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>

#include <zephyr/device.h>
#include <zephyr/drivers/dma.h>
#include <zephyr/drivers/misc/pio_rpi_pico/pio_rpi_pico.h>
#include <zephyr/dt-bindings/dma/rpi-pico-dma-common.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include <hardware/clocks.h>
#include <hardware/gpio.h>
#include <hardware/pio.h>
#include <hardware/pio_instructions.h>

#include "la_pio.h"

LOG_MODULE_REGISTER(la_pio, LOG_LEVEL_INF);

static const struct device *const pio_dev = DEVICE_DT_GET(DT_NODELABEL(coproc_pio));
static const struct device *const dma_dev = DEVICE_DT_GET(DT_NODELABEL(coproc_dma));

uint8_t la_buf[LA_BUF_SAMPLES] __aligned(4);

static K_SEM_DEFINE(la_done, 0, 1);
static int la_dma_status;
static size_t la_sm = SIZE_MAX;
static int la_dma_ch = -1;

static void la_dma_cb(const struct device *dev, void *user_data, uint32_t channel, int status)
{
	ARG_UNUSED(dev);
	ARG_UNUSED(user_data);
	ARG_UNUSED(channel);

	la_dma_status = status;
	k_sem_give(&la_done);
}

/*
 * PIO reads every pin's input whatever its function, so pins that already
 * belong to I2C or the UART are sampled as they are.  The others are made
 * inputs here (on the RP2350 this also lifts the pad isolation).
 */
static void la_prepare_pins(uint8_t first_pin)
{
	for (uint32_t pin = first_pin; pin < first_pin + LA_CHANNELS; pin++) {
		if (gpio_get_function(pin) == GPIO_FUNC_NULL) {
			gpio_init(pin);
		}
		gpio_set_input_enabled(pin, true);
	}
}

int la_capture(const struct la_params *p, uint32_t *rate_hz)
{
	PIO pio = pio_rpi_pico_get_pio(pio_dev);
	const uint32_t sys_hz = clock_get_hz(clk_sys);
	uint16_t insn[3];
	struct pio_program prog = {.instructions = insn, .origin = -1};
	uint32_t wrap_target = 0;
	uint32_t offset;
	pio_sm_config c;
	float div;
	int ret;

	if (p->samples == 0 || p->samples > LA_BUF_SAMPLES || (p->samples % 4) != 0) {
		return -EINVAL;
	}
	if (p->rate_hz == 0 || p->rate_hz > sys_hz || sys_hz / p->rate_hz > 65535) {
		return -EINVAL;
	}
	if (p->first_pin + LA_CHANNELS > 32) {
		return -EINVAL;
	}
	if (p->trigger_pin >= 0 && (p->trigger_pin < p->first_pin ||
				    p->trigger_pin >= p->first_pin + LA_CHANNELS)) {
		return -EINVAL;
	}

	if (la_sm == SIZE_MAX) {
		ret = pio_rpi_pico_allocate_sm(pio_dev, &la_sm);
		if (ret < 0) {
			return ret;
		}
	}
	if (la_dma_ch < 0) {
		la_dma_ch = dma_request_channel(dma_dev, NULL);
		if (la_dma_ch < 0) {
			return -EBUSY;
		}
	}

	if (p->trigger_pin >= 0) {
		const uint32_t idx = p->trigger_pin - p->first_pin; /* relative to IN_BASE */

		insn[0] = pio_encode_wait_pin(!p->rising, idx);
		insn[1] = pio_encode_wait_pin(p->rising, idx);
		wrap_target = 2;
	}
	insn[wrap_target] = pio_encode_in(pio_pins, LA_CHANNELS);
	prog.length = wrap_target + 1;

	if (!pio_can_add_program(pio, &prog)) {
		return -EBUSY;
	}
	offset = pio_add_program(pio, &prog);

	div = (float)sys_hz / (float)p->rate_hz;
	*rate_hz = (uint32_t)((float)sys_hz / div);

	la_prepare_pins(p->first_pin);

	c = pio_get_default_sm_config();
	sm_config_set_in_pins(&c, p->first_pin);
	sm_config_set_in_shift(&c, true, true, 32);
	sm_config_set_fifo_join(&c, PIO_FIFO_JOIN_RX);
	sm_config_set_clkdiv(&c, div);
	sm_config_set_wrap(&c, offset + wrap_target, offset + wrap_target);
	pio_sm_set_consecutive_pindirs(pio, la_sm, p->first_pin, LA_CHANNELS, false);
	pio_sm_init(pio, la_sm, offset, &c);

	struct dma_block_config blk = {
		.source_address = (uint32_t)&pio->rxf[la_sm],
		.source_addr_adj = DMA_ADDR_ADJ_NO_CHANGE,
		.dest_address = (uint32_t)la_buf,
		.dest_addr_adj = DMA_ADDR_ADJ_INCREMENT,
		.block_size = p->samples * LA_CHANNELS / 8,
	};
	struct dma_config cfg = {
		.channel_direction = PERIPHERAL_TO_MEMORY,
		.dma_slot = RPI_PICO_DMA_DREQ_TO_SLOT(pio_get_dreq(pio, la_sm, false)),
		.source_data_size = 4,
		.dest_data_size = 4,
		.source_burst_length = 1,
		.dest_burst_length = 1,
		.channel_priority = 1,
		.block_count = 1,
		.head_block = &blk,
		.dma_callback = la_dma_cb,
	};

	k_sem_reset(&la_done);
	ret = dma_config(dma_dev, la_dma_ch, &cfg);
	if (ret == 0) {
		ret = dma_start(dma_dev, la_dma_ch);
	}
	if (ret == 0) {
		pio_sm_set_enabled(pio, la_sm, true);
		if (k_sem_take(&la_done, p->timeout) != 0) {
			ret = -ETIMEDOUT;
		} else {
			ret = la_dma_status;
		}
	}

	pio_sm_set_enabled(pio, la_sm, false);
	dma_stop(dma_dev, la_dma_ch);
	pio_sm_clear_fifos(pio, la_sm);
	pio_remove_program(pio, &prog, offset);

	return ret;
}
