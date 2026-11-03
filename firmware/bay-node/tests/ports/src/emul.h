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
/* io 0: 0x20 (ports 1-2), 1: 0x21 (ports 3-4), 2: 0x38 (the matrix expander) */
uint8_t emul_io_reg(int io, uint8_t reg);
/* What drives an input pin from outside (FAULT_N: 0 = fault) */
void emul_io_pin(int io, uint8_t pin, bool level);
/* The CONFIG register values written since the last call */
int emul_io_cfg_log(int io, uint8_t *out, int max);
/* The matrix expander's output register (0x38, MARK on P7) at each of those writes on 0x20 and 0x21 */
int emul_mx_log(uint8_t *out, int max);
/* The two crosspoints behind 0x38: a switch write, chip 0 U7, 1 U8 */
struct emul_xp_event {
	uint8_t chip;
	uint8_t x;
	uint8_t y;
	bool on;
};
/* The Y lines chip's X line x is joined to */
uint8_t emul_xp_y(int chip, int x);
/* The switch writes since the last call, in order */
int emul_xp_log(struct emul_xp_event *out, int max);
/* RST pulses seen; DAT or CK moving while a strobe was high, DAT moving with a CK or STB edge */
int emul_xp_resets(void);
int emul_xp_glitches(void);
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

/* Node v1.0 (the eFuse's EN powers the board): the rack's VIN, 20 V by default */
void emul_vin(int mv);
/* A short on the lead: DATA_VIN stays at 0 with the eFuse on */
void emul_lead_short(bool shorted);
/* A DATA board on the lead or not (none: nothing answers, nothing draws) */
void emul_board(bool there);

#endif
