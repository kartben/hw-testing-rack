/*
 * A DATA x4 board on native_sim's emulated I2C bus: two TCA6408A (as
 * "ti,tca9538", register compatible), the matrix expander (TCA9534A) and four INA226,
 * powered from DUT_5V like the real board.  Unpowered they NACK and forget
 * their registers.  The node's own INA226 (0x40) measures the board on
 * DUT_5V: the ports that are on and the board itself, its ALERT on gpio0.
 *
 * Or a DATA x6 (emul_board_kind()): one TCA9535 at 0x20, the same address
 * as the DATA x4's first expander (register pairs, port 0 then port 1),
 * and six INA226, the DATA x4's four and 0x47, 0x4C; no 0x21, no matrix.
 * Or a stray expander at 0x20 alone, neither board.
 *
 * Node v1.0 (dut_port's vin-efuse): the board is powered while the eFuse's
 * enable (dut_port's EN) is high, and the node's INA226 reads DATA_VIN, the
 * board's 5 V converted from it at 88 %.
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

#define EFUSE DT_PROP(DT_NODELABEL(dut_port), vin_efuse)

static const struct gpio_dt_spec lead_en = GPIO_DT_SPEC_GET(DT_NODELABEL(dut_port), enable_gpios);

static bool powered = true;
static bool board_there = true;
static bool lead_short;
static int vin_mv = 20000;
static int offline;
static int kind = 4; /* 4 a DATA x4, 6 a DATA x6, 1 an expander at 0x20 alone */

static void board_update(void);

/* DUT_5V on (the first design), or the eFuse on (v1.0): DATA_VIN */
static bool lead_powered(void)
{
	if (EFUSE) {
		return !lead_short && gpio_emul_output_get(lead_en.port, lead_en.pin) > 0;
	}
	return powered;
}

/* The board's chips have power and are there to answer */
static bool board_up(void)
{
	return lead_powered() && board_there;
}

static void chips_follow(void);

/* --- TCA6408A / TCA9534A ---------------------------------------------------- */

#define DT_DRV_COMPAT ti_tca9538

struct io_data {
	uint8_t addr;
	uint16_t out; /* 8-bit chips use the low byte */
	uint16_t pol;
	uint16_t cfg;
	uint16_t pins; /* what drives the input pins from outside */
	uint16_t cfg_log[64];
	int ncfg;
};

static struct io_data *ios[3]; /* 0x20, 0x21, 0x38 */
/* The matrix expander (0x38): its output register at each CONFIG write of 0x20 and 0x21 */
static uint8_t mx_log[64];
static int nmx;

static int io_index(uint8_t addr)
{
	return addr == 0x38 ? 2 : addr & 1;
}

/* The DATA x6's TCA9535: 16 lines, register pairs */
static bool wide(const struct io_data *d)
{
	return kind == 6 && d->addr == 0x20;
}

/* 0x20 on every board; 0x21 and the matrix expander on a DATA x4 only */
static bool io_there(const struct io_data *d)
{
	return d->addr == 0x20 || kind == 4;
}

/* A register: the 8-bit chips' number, or a TCA9535's pair (reg / 2) and its byte */
static uint16_t *io_reg(struct io_data *d, uint8_t reg)
{
	switch (wide(d) ? reg / 2 : reg) {
	case 1:
		return &d->out;
	case 2:
		return &d->pol;
	case 3:
		return &d->cfg;
	default:
		return NULL;
	}
}

static void io_reset(struct io_data *d)
{
	d->out = 0xFFFF;
	d->pol = 0;
	d->cfg = 0xFFFF;
	d->ncfg = 0;
}

static uint16_t io_input(const struct io_data *d)
{
	/* Inputs from outside, outputs as driven */
	return ((d->pins & d->cfg) | (d->out & ~d->cfg)) ^ d->pol;
}

static uint8_t io_read(struct io_data *d, uint8_t reg)
{
	uint16_t *r = io_reg(d, reg);
	uint16_t v = r != NULL ? *r : io_input(d);

	return (v >> (wide(d) ? (reg & 1) * 8 : 0)) & 0xFF;
}

/* --- The two CH446Q behind 0x38 ---------------------------------------- */

/*
 * P0 DAT, P1 CK, P2 U7's STB, P3 U8's STB, P4 RST, pulled up on the board (an
 * input reads high; the other inputs low).  Both chips shift DAT in on CK's
 * rising edge; the one whose STB goes high sets the switch its 7-bit address
 * names (y * 16 + x) to DAT, which must then hold until STB falls.  DAT
 * must not change in the write that raises CK or STB (TAS, TDS).
 */
#define XP_DAT BIT(0)
#define XP_CK  BIT(1)
#define XP_RST BIT(4)

static const uint8_t xp_stb[2] = {BIT(2), BIT(3)};

static struct {
	uint8_t lines;
	uint8_t addr;
	uint8_t y[2][16];
	struct emul_xp_event log[256];
	int n;
	int resets;
	int glitches; /* DAT or CK moved while a strobe was high */
} xp;

static void xp_update(const struct io_data *d)
{
	uint8_t now = ((d->out & ~d->cfg) | (d->cfg & XP_RST)) & 0x1F;
	uint8_t rose = now & ~xp.lines;

	if (now & XP_RST) {
		xp.resets += (rose & XP_RST) != 0;
		memset(xp.y, 0, sizeof(xp.y));
	} else {
		if ((xp.lines & (xp_stb[0] | xp_stb[1])) && ((now ^ xp.lines) & (XP_DAT | XP_CK))) {
			xp.glitches++;
		}
		if ((rose & (XP_CK | xp_stb[0] | xp_stb[1])) && ((now ^ xp.lines) & XP_DAT)) {
			xp.glitches++;
		}
		if (rose & XP_CK) {
			xp.addr = ((xp.addr << 1) | ((now & XP_DAT) ? 1 : 0)) & 0x7F;
		}
		for (int c = 0; c < 2; c++) {
			if (rose & xp_stb[c]) {
				uint8_t x = xp.addr & 0xF, y = xp.addr >> 4;
				bool on = now & XP_DAT;

				WRITE_BIT(xp.y[c][x], y, on);
				if (xp.n < (int)ARRAY_SIZE(xp.log)) {
					xp.log[xp.n++] = (struct emul_xp_event){c, x, y, on};
				}
			}
		}
	}
	xp.lines = now;
}

uint8_t emul_xp_y(int chip, int x)
{
	return xp.y[chip][x];
}

int emul_xp_log(struct emul_xp_event *out, int max)
{
	int n = MIN(xp.n, max);

	memcpy(out, xp.log, n * sizeof(*out));
	xp.n = 0;
	return n;
}

int emul_xp_resets(void)
{
	return xp.resets;
}

int emul_xp_glitches(void)
{
	return xp.glitches;
}

static void io_write(struct io_data *d, uint8_t reg, uint8_t val)
{
	uint16_t *r = io_reg(d, reg);
	int shift = wide(d) ? (reg & 1) * 8 : 0;

	if (r != NULL) {
		*r = (*r & ~(0xFF << shift)) | (val << shift);
	}
	if (d == ios[2]) {
		xp_update(d);
	}
}

/* After a write that set the CONFIG register(s): logged, with the matrix expander's outputs */
static void io_cfg_written(struct io_data *d)
{
	if (d->ncfg < (int)ARRAY_SIZE(d->cfg_log)) {
		d->cfg_log[d->ncfg++] = d->cfg;
	}
	if (d != ios[2] && ios[2] != NULL && nmx < (int)ARRAY_SIZE(mx_log)) {
		mx_log[nmx++] = ios[2]->out;
	}
}

static int io_transfer(const struct emul *target, struct i2c_msg *msgs, int num_msgs, int addr)
{
	struct io_data *d = target->data;

	ARG_UNUSED(addr);

	chips_follow();
	if (!board_up() || !io_there(d)) {
		offline += !lead_powered();
		return -EIO;
	}
	/* One register, or a TCA9535's pair: its bytes alternate, port 0 then port 1 */
	if (num_msgs == 1 && !(msgs[0].flags & I2C_MSG_READ) &&
	    (msgs[0].len == 2 || (wide(d) && msgs[0].len == 3))) {
		uint8_t cmd = msgs[0].buf[0];

		for (uint32_t i = 1; i < msgs[0].len; i++) {
			io_write(d, wide(d) ? (cmd & ~1) | ((cmd + i - 1) & 1) : cmd, msgs[0].buf[i]);
		}
		if (io_reg(d, cmd) == &d->cfg) {
			io_cfg_written(d);
		}
		board_update();
		return 0;
	}
	if (num_msgs == 2 && !(msgs[0].flags & I2C_MSG_READ) && (msgs[1].flags & I2C_MSG_READ)) {
		uint8_t cmd = msgs[0].buf[0];

		for (uint32_t i = 0; i < msgs[1].len; i++) {
			msgs[1].buf[i] = io_read(d, wide(d) ? (cmd & ~1) | ((cmd + i) & 1) : cmd + i);
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
	d->pins = 0xFFFF; /* FAULT_N pulled up, RESET and BOOT on 100k pull-ups */
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

static struct ina_data *inas[16]; /* by address - 0x40 */
static bool meter_present = true;
static bool alert_wired = true;
static int board_ma = 300;

/* Port n: its expander, EN pin and INA226 (data-x4.dtsi, data-x6.dtsi) */
struct wire {
	uint8_t io, en, ina;
};

static const struct wire x4_wiring[4] = {{0, 2, 0x41}, {0, 4, 0x43}, {1, 2, 0x44}, {1, 4, 0x45}};
static const struct wire x6_wiring[6] = {{0, 0, 0x41}, {0, 2, 0x43}, {0, 4, 0x44},
					 {0, 6, 0x45}, {0, 8, 0x47}, {0, 10, 0x4C}};

static int nports(void)
{
	return kind == 6 ? 6 : kind == 4 ? 4 : 0;
}

static const struct wire *wiring(int n)
{
	return kind == 6 ? &x6_wiring[n] : &x4_wiring[n];
}

static bool en_was[6];
static int64_t off_at[6];
static int discharge_ms[6];
static int ext_mv[6];

static bool port_en(int n)
{
	const struct io_data *d = ios[wiring(n)->io];
	uint16_t en = BIT(wiring(n)->en);

	return board_up() && !(d->cfg & en) && (d->out & en);
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

/* What the node's INA226 measures, mA: DUT_5V (the first design), or DATA_VIN (v1.0) */
static int meter_ma(void)
{
	int ma = board_ma;

	for (int n = 0; n < nports(); n++) {
		if (port_en(n) && inas[wiring(n)->ina - 0x40] != NULL) {
			ma += inas[wiring(n)->ina - 0x40]->ma;
		}
	}
	if (EFUSE) {
		/* The board's 5 V from DATA_VIN at 88 % */
		return board_up() ? ma * 5000 * 100 / (vin_mv * 88) : 0;
	}
	return ma;
}

static int meter_mv(void)
{
	if (EFUSE) {
		return lead_powered() ? vin_mv : 0;
	}
	return 5000;
}

/* The node's shunt: 2.5 uV/LSB across 50 mOhm, 20 LSB per mA */
static int16_t meter_shunt(void)
{
	return (int16_t)CLAMP(meter_ma() * 20, INT16_MIN, INT16_MAX);
}

/* The port an INA226 measures on the board there now, -1 none (the node's, or not on it) */
static int port_of(uint8_t addr)
{
	for (int n = 0; n < nports(); n++) {
		if (wiring(n)->ina == addr) {
			return n;
		}
	}
	return -1;
}

static int ina_transfer(const struct emul *target, struct i2c_msg *msgs, int num_msgs, int addr)
{
	struct ina_data *d = target->data;
	int n = port_of(d->addr);
	bool node = d->addr == 0x40;
	uint16_t v;

	ARG_UNUSED(addr);

	chips_follow();
	if (node ? !meter_present : !board_up() || n < 0) {
		offline += !node && !lead_powered();
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
	if (num_msgs == 2 && (msgs[1].flags & I2C_MSG_READ) && msgs[1].len >= 1 && msgs[1].len <= 2) {
		switch (msgs[0].buf[0]) {
		case 0x00:
			v = d->config;
			break;
		case 0x01: /* 2.5 uV/LSB across 100 mOhm: 40 LSB per mA, saturated at 81.92 mV */
			v = node ? meter_shunt()
				 : (uint16_t)(int16_t)CLAMP(port_en(n) ? d->ma * 40 : 0, INT16_MIN,
								INT16_MAX);
			break;
		case 0x02: /* 1.25 mV/LSB */
			v = (node ? meter_mv() : port_mv(n)) * 4 / 5;
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
		if (msgs[1].len == 2) {
			msgs[1].buf[1] = v & 0xFF;
		}
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

	for (int n = 0; n < nports(); n++) {
		bool en = port_en(n);

		if (en_was[n] && !en) {
			off_at[n] = k_uptime_get();
		}
		en_was[n] = en;
	}
	fire = alert_wired && meter_present && (m->mask & BIT(15)) && meter_shunt() > (int16_t)m->limit;
	(void)gpio_emul_input_set(alert.port, alert.pin, !fire);
}

/* Power-on defaults of the board's chips (not the node's INA226) */
static void chips_reset(void)
{
	for (int i = 0; i < (int)ARRAY_SIZE(ios); i++) {
		io_reset(ios[i]);
	}
	/* The crosspoints with them: held in reset until the expander drives RST */
	if (ios[2] != NULL) {
		xp_update(ios[2]);
	}
	for (int i = 1; i < (int)ARRAY_SIZE(inas); i++) {
		if (inas[i] != NULL) {
			inas[i]->config = 0x4127;
		}
	}
}

/* v1.0: the chips start from their defaults each time DATA_VIN comes back */
static void chips_follow(void)
{
	static bool was_up = true;
	bool up = board_up();

	if (EFUSE && up && !was_up) {
		chips_reset();
	}
	was_up = up;
}

/* --- For the test --------------------------------------------------------------- */

void emul_power(bool on)
{
	if (on && !powered) {
		chips_reset();
	}
	powered = on;
	board_update();
}

void emul_vin(int mv)
{
	vin_mv = mv;
	board_update();
}

void emul_lead_short(bool shorted)
{
	lead_short = shorted;
	board_update();
}

void emul_board(bool there)
{
	board_there = there;
	board_update();
}

void emul_board_kind(int k)
{
	kind = k;
	memset(en_was, 0, sizeof(en_was));
	board_update();
}

uint16_t emul_x6_reg(int pair)
{
	struct io_data *d = ios[0];

	return pair == 0 ? io_input(d) : *io_reg(d, pair * 2);
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

	for (int i = 0; i < n; i++) {
		out[i] = ios[io]->cfg_log[i] & 0xFF;
	}
	ios[io]->ncfg = 0;
	return n;
}

int emul_mx_log(uint8_t *out, int max)
{
	int n = MIN(nmx, max);

	memcpy(out, mx_log, n);
	nmx = 0;
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
