/*
 * A DATA x4 board on native_sim's emulated I2C bus: two TCA6408A (as
 * "ti,tca9538", register compatible) and four INA226, powered from DUT_5V
 * like the real board.  Unpowered they NACK and forget their registers.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/device.h>
#include <zephyr/drivers/emul.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/i2c_emul.h>

#include "emul.h"

static bool powered = true;
static int offline;

/* --- TCA6408A --------------------------------------------------------------- */

#define DT_DRV_COMPAT ti_tca9538

struct io_data {
	uint8_t addr;
	uint8_t out;
	uint8_t pol;
	uint8_t cfg;
	uint8_t pins; /* what drives the input pins from outside */
	uint8_t cfg_log[64];
	int ncfg;
};

static struct io_data *ios[2];

static void io_reset(struct io_data *d)
{
	d->out = 0xFF;
	d->pol = 0;
	d->cfg = 0xFF;
	d->ncfg = 0;
}

static uint8_t io_read(const struct io_data *d, uint8_t reg)
{
	switch (reg) {
	case 0:
		/* Inputs from outside, outputs as driven */
		return ((d->pins & d->cfg) | (d->out & ~d->cfg)) ^ d->pol;
	case 1:
		return d->out;
	case 2:
		return d->pol;
	default:
		return d->cfg;
	}
}

static void io_write(struct io_data *d, uint8_t reg, uint8_t val)
{
	switch (reg) {
	case 1:
		d->out = val;
		break;
	case 2:
		d->pol = val;
		break;
	case 3:
		d->cfg = val;
		if (d->ncfg < (int)ARRAY_SIZE(d->cfg_log)) {
			d->cfg_log[d->ncfg++] = val;
		}
		break;
	default:
		break;
	}
}

static int io_transfer(const struct emul *target, struct i2c_msg *msgs, int num_msgs, int addr)
{
	struct io_data *d = target->data;

	ARG_UNUSED(addr);

	if (!powered) {
		offline++;
		return -EIO;
	}
	if (num_msgs == 1 && !(msgs[0].flags & I2C_MSG_READ) && msgs[0].len == 2) {
		io_write(d, msgs[0].buf[0], msgs[0].buf[1]);
		return 0;
	}
	if (num_msgs == 2 && !(msgs[0].flags & I2C_MSG_READ) && (msgs[1].flags & I2C_MSG_READ)) {
		for (uint32_t i = 0; i < msgs[1].len; i++) {
			msgs[1].buf[i] = io_read(d, msgs[0].buf[0] + i);
		}
		return 0;
	}
	return -EIO;
}

static const struct i2c_emul_api io_api = {.transfer = io_transfer};

static int io_init(const struct emul *target, const struct device *parent)
{
	struct io_data *d = target->data;

	ARG_UNUSED(parent);
	d->addr = target->bus.i2c->addr;
	io_reset(d);
	d->pins = 0xFF; /* FAULT_N pulled up, RESET and BOOT on 100k pull-ups */
	ios[d->addr & 1] = d;
	return 0;
}

#define IO_EMUL(n)                                                                                 \
	static struct io_data io_data_##n;                                                         \
	EMUL_DT_INST_DEFINE(n, io_init, &io_data_##n, NULL, &io_api, NULL)

DT_INST_FOREACH_STATUS_OKAY(IO_EMUL)

#undef DT_DRV_COMPAT

/* --- INA226 ---------------------------------------------------------------- */

#define DT_DRV_COMPAT ti_ina226

struct ina_data {
	uint8_t addr;
	uint8_t ptr;
	uint16_t config;
	int ma;
	int mv;
};

static struct ina_data *inas[6]; /* by address - 0x40 */

static int ina_transfer(const struct emul *target, struct i2c_msg *msgs, int num_msgs, int addr)
{
	struct ina_data *d = target->data;
	uint16_t v;

	ARG_UNUSED(addr);

	if (!powered && d->addr != 0x40) {
		offline++;
		return -EIO;
	}
	if (num_msgs == 1 && !(msgs[0].flags & I2C_MSG_READ) && msgs[0].len == 3) {
		if (msgs[0].buf[0] == 0x00) {
			d->config = (msgs[0].buf[1] << 8) | msgs[0].buf[2];
		}
		return 0;
	}
	if (num_msgs == 2 && (msgs[1].flags & I2C_MSG_READ) && msgs[1].len == 2) {
		switch (msgs[0].buf[0]) {
		case 0x00:
			v = d->config;
			break;
		case 0x01: /* 2.5 uV/LSB across 100 mOhm: 40 LSB per mA, saturated at 81.92 mV */
			v = (uint16_t)(int16_t)CLAMP(d->ma * 40, INT16_MIN, INT16_MAX);
			break;
		case 0x02: /* 1.25 mV/LSB */
			v = d->mv * 4 / 5;
			break;
		default:
			v = 0;
			break;
		}
		msgs[1].buf[0] = v >> 8;
		msgs[1].buf[1] = v & 0xFF;
		return 0;
	}
	return -EIO;
}

static const struct i2c_emul_api ina_api = {.transfer = ina_transfer};

static int ina_init(const struct emul *target, const struct device *parent)
{
	struct ina_data *d = target->data;

	ARG_UNUSED(parent);
	d->addr = target->bus.i2c->addr;
	d->config = 0x4127;
	d->mv = 5050;
	inas[d->addr - 0x40] = d;
	return 0;
}

#define INA_EMUL(n)                                                                                \
	static struct ina_data ina_data_##n;                                                       \
	EMUL_DT_INST_DEFINE(n, ina_init, &ina_data_##n, NULL, &ina_api, NULL)

DT_INST_FOREACH_STATUS_OKAY(INA_EMUL)

/* --- For the test --------------------------------------------------------------- */

void emul_power(bool on)
{
	if (on && !powered) {
		/* Power-on defaults */
		for (int i = 0; i < 2; i++) {
			io_reset(ios[i]);
		}
		for (int i = 1; i < (int)ARRAY_SIZE(inas); i++) {
			if (inas[i] != NULL) {
				inas[i]->config = 0x4127;
			}
		}
	}
	powered = on;
}

int emul_offline(void)
{
	return offline;
}

uint8_t emul_io_reg(int io, uint8_t reg)
{
	return io_read(ios[io], reg);
}

void emul_io_pin(int io, uint8_t pin, bool level)
{
	WRITE_BIT(ios[io]->pins, pin, level);
}

int emul_io_cfg_log(int io, uint8_t *out, int max)
{
	int n = MIN(ios[io]->ncfg, max);

	memcpy(out, ios[io]->cfg_log, n);
	ios[io]->ncfg = 0;
	return n;
}

void emul_ina_ma(uint8_t addr, int ma)
{
	inas[addr - 0x40]->ma = ma;
}

uint16_t emul_ina_config(uint8_t addr)
{
	return inas[addr - 0x40]->config;
}
