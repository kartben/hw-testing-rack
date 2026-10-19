/*
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef LA_PIO_H_
#define LA_PIO_H_

#include <stdbool.h>
#include <stdint.h>

#include <zephyr/kernel.h>

/* Channels per sample: one byte, CH1-8 = first_pin .. first_pin + 7 */
#define LA_CHANNELS 8

/* Half of the Pico 2's 520 KB; the gusmanb firmware keeps 384 KB */
#define LA_BUF_SAMPLES (256U * 1024U)

struct la_params {
	uint8_t first_pin;
	uint32_t rate_hz;
	uint32_t samples;	/* a multiple of 4 (one 32-bit word per 4 samples) */
	int8_t trigger_pin;	/* -1: start at once */
	bool rising;
	k_timeout_t timeout;	/* for the trigger */
};

extern uint8_t la_buf[LA_BUF_SAMPLES];

/* Capture into la_buf; *rate_hz gets the rate the PIO divider really gives */
int la_capture(const struct la_params *p, uint32_t *rate_hz);

#endif /* LA_PIO_H_ */
