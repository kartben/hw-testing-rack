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
/* io 0: 0x20 (ports 1-2), 1: 0x21 (ports 3-4), 2: 0x38 (the v2's matrix expander) */
uint8_t emul_io_reg(int io, uint8_t reg);
/* What drives an input pin from outside (FAULT_N: 0 = fault) */
void emul_io_pin(int io, uint8_t pin, bool level);
/* The CONFIG register values written since the last call */
int emul_io_cfg_log(int io, uint8_t *out, int max);
/* A port's draw while it is on (0x41, 0x43-0x45) */
void emul_ina_ma(uint8_t addr, int ma);
uint16_t emul_ina_config(uint8_t addr);
uint16_t emul_ina_reg(uint8_t addr, uint8_t reg);
/* The node's INA226 (0x40): the board's own draw on top of the ports', and whether it answers */
void emul_board_ma(int ma);
void emul_meter(bool present);
/* Its ALERT wired to the node (a stand-in has none: the poll sheds) */
void emul_alert(bool wired);
/* Port 1-4 while off: its VBUS falls from 5 V to 0 in discharge_ms, or a board holds it at ext_mv */
void emul_port_vbus(int port, int ext_mv, int discharge_ms);

#endif
