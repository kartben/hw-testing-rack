/*
 * A DATA x4 board on native_sim's emulated I2C bus: two TCA6408A (as
 * "ti,tca9538", register compatible), the v2's TCA9534A and four INA226,
 * powered from DUT_5V like the real board.  Unpowered they NACK and forget
 * their registers.  The node's own INA226 (0x40) measures the board on
 * DUT_5V: the ports that are on and the board itself, its ALERT on gpio0.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/emul.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/gpio/gpio_emul.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/i2c_emul.h>

#include "emul.h"

static bool powered = true;
static int offline;

static void board_update(void);

/* --- TCA6408A / TCA9534A ---------------------------------------------------- */

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

static struct io_data *ios[3]; /* 0x20, 0x21, 0x38 */

static int io_index(uint8_t addr)
{
	return addr == 0x38 ? 2 : addr & 1;
}

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
		board_update();
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
	ios[io_index(d->addr)] = d;
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
	uint16_t config;
	uint16_t mask;
	uint16_t limit;
	int ma;
};

static struct ina_data *inas[6]; /* by address - 0x40 */
static bool meter_present = true;
static bool alert_wired = true;
static int board_ma = 300;

/* Port n: its expander, EN pin and INA226 (data-x4.dtsi) */
static const struct {
	uint8_t io, en, ina;
} wiring[4] = {{0, 2, 0x41}, {0, 4, 0x43}, {1, 2, 0x44}, {1, 4, 0x45}};

static bool en_was[4];
static int64_t off_at[4];
static int discharge_ms[4];
static int ext_mv[4];

static bool port_en(int n)
{
	const struct io_data *d = ios[wiring[n].io];

	return powered && !(d->cfg & BIT(wiring[n].en)) && (d->out & BIT(wiring[n].en));
}

static int port_mv(int n)
{
	int64_t t = k_uptime_get() - off_at[n];
	int mv = 0;

	if (port_en(n)) {
		return 5050;
	}
	if (discharge_ms[n] > 0 && t < discharge_ms[n]) {
		mv = (int)(5050 - t * 5050 / discharge_ms[n]);
	}
	return MAX(mv, ext_mv[n]);
}

/* The node's shunt: 2.5 uV/LSB across 50 mOhm, 20 LSB per mA */
static int16_t meter_shunt(void)
{
	int ma = board_ma;

	for (int n = 0; n < 4; n++) {
		if (port_en(n) && inas[wiring[n].ina - 0x40] != NULL) {
			ma += inas[wiring[n].ina - 0x40]->ma;
		}
	}
	return (int16_t)CLAMP(ma * 20, INT16_MIN, INT16_MAX);
}

static int port_of(uint8_t addr)
{
	for (int n = 0; n < 4; n++) {
		if (wiring[n].ina == addr) {
			return n;
		}
	}
	return -1;
}

static int ina_transfer(const struct emul *target, struct i2c_msg *msgs, int num_msgs, int addr)
{
	struct ina_data *d = target->data;
	int n = port_of(d->addr);
	uint16_t v;

	ARG_UNUSED(addr);

	if ((!powered && n >= 0) || (n < 0 && !meter_present)) {
		offline += n >= 0;
		return -EIO;
	}
	if (num_msgs == 1 && !(msgs[0].flags & I2C_MSG_READ) && msgs[0].len == 3) {
		v = (msgs[0].buf[1] << 8) | msgs[0].buf[2];
		switch (msgs[0].buf[0]) {
		case 0x00:
			d->config = v;
			break;
		case 0x06:
			d->mask = v;
			break;
		case 0x07:
			d->limit = v;
			break;
		default:
			break;
		}
		board_update();
		return 0;
	}
	if (num_msgs == 2 && (msgs[1].flags & I2C_MSG_READ) && msgs[1].len == 2) {
		switch (msgs[0].buf[0]) {
		case 0x00:
			v = d->config;
			break;
		case 0x01: /* 2.5 uV/LSB across 100 mOhm: 40 LSB per mA, saturated at 81.92 mV */
			v = n < 0 ? meter_shunt()
				  : (uint16_t)(int16_t)CLAMP(port_en(n) ? d->ma * 40 : 0, INT16_MIN,
								 INT16_MAX);
			break;
		case 0x02: /* 1.25 mV/LSB */
			v = (n < 0 ? 5000 : port_mv(n)) * 4 / 5;
			break;
		case 0x06:
			v = d->mask;
			break;
		case 0x07:
			v = d->limit;
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
	inas[d->addr - 0x40] = d;
	return 0;
}

#define INA_EMUL(n)                                                                                \
	static struct ina_data ina_data_##n;                                                       \
	EMUL_DT_INST_DEFINE(n, ina_init, &ina_data_##n, NULL, &ina_api, NULL)

DT_INST_FOREACH_STATUS_OKAY(INA_EMUL)

/* --- The board as a whole ---------------------------------------------------- */

static const struct gpio_dt_spec alert = GPIO_DT_SPEC_GET(DT_NODELABEL(node_meter), alert_gpios);

/* A port's EN edges, and the node's ALERT (SOL, not latched: it follows the shunt) */
static void board_update(void)
{
	const struct ina_data *m = inas[0];
	bool fire;

	for (int n = 0; n < 4; n++) {
		bool en = port_en(n);

		if (en_was[n] && !en) {
			off_at[n] = k_uptime_get();
		}
		en_was[n] = en;
	}
	fire = alert_wired && meter_present && (m->mask & BIT(15)) && meter_shunt() > (int16_t)m->limit;
	(void)gpio_emul_input_set(alert.port, alert.pin, !fire);
}

/* --- For the test --------------------------------------------------------------- */

void emul_power(bool on)
{
	if (on && !powered) {
		/* Power-on defaults */
		for (int i = 0; i < (int)ARRAY_SIZE(ios); i++) {
			io_reset(ios[i]);
		}
		for (int i = 1; i < (int)ARRAY_SIZE(inas); i++) {
			if (inas[i] != NULL) {
				inas[i]->config = 0x4127;
			}
		}
	}
	powered = on;
	board_update();
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
	board_update();
}

uint16_t emul_ina_config(uint8_t addr)
{
	return inas[addr - 0x40]->config;
}

uint16_t emul_ina_reg(uint8_t addr, uint8_t reg)
{
	const struct ina_data *d = inas[addr - 0x40];

	return reg == 0x06 ? d->mask : reg == 0x07 ? d->limit : d->config;
}

void emul_board_ma(int ma)
{
	board_ma = ma;
	board_update();
}

void emul_meter(bool present)
{
	meter_present = present;
	board_update();
}

void emul_alert(bool wired)
{
	alert_wired = wired;
	board_update();
}

void emul_port_vbus(int port, int ext, int discharge)
{
	ext_mv[port - 1] = ext;
	discharge_ms[port - 1] = discharge;
}
