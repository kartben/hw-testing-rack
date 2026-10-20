/*
 * The emulated DATA x4 board (emul.c), for the test.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PORTS_TEST_EMUL_H_
#define PORTS_TEST_EMUL_H_

#include <stdbool.h>
#include <stdint.h>

/* DUT_5V to the board: off, its chips NACK; back on, they start from their defaults */
void emul_power(bool on);
/* Transfers the unpowered board was sent */
int emul_offline(void);
/* io 0: 0x20 (ports 1-2), 1: 0x21 (ports 3-4) */
uint8_t emul_io_reg(int io, uint8_t reg);
/* What drives an input pin from outside (FAULT_N: 0 = fault) */
void emul_io_pin(int io, uint8_t pin, bool level);
/* The CONFIG register values written since the last call */
int emul_io_cfg_log(int io, uint8_t *out, int max);
void emul_ina_ma(uint8_t addr, int ma);
uint16_t emul_ina_config(uint8_t addr);

#endif
