/*
 * The drawer's DATA x4 board: four boards behind a hub, each on its own
 * switch (TPS2553-1), current sense (INA226) and RESET/BOOT lines, on two
 * TCA6408A expanders (docs/multi-dut-node.md).
 *
 * The board runs from DUT_5V and its chips lose their registers with it, so
 * this file drives them itself over I2C, with shadow registers, instead of
 * through the GPIO and sensor drivers (whose cached state would not match a
 * chip that has just been powered up).  The devicetree still describes them
 * (dut_port1-4 on ports_io0/1, port1-4_sense): it gives the addresses and
 * the pins.
 *
 *  - The board is probed after each DUT_5V on: no answer at 0x20, no board,
 *    a one-port node (today's DUT, dut.c).
 *  - No I2C to it while DUT_5V is off.  Before DUT_5V goes off every EN goes
 *    low; after it comes back, CONFIG_BAY_PORTS_SETTLE_MS later, both
 *    expanders and the four INA226 are set up again, every port off.
 *  - Ports come up off (EN pulled down) and go on one at a time, every
 *    CONFIG_BAY_PORTS_STAGGER_MS, through the admission rule: the other
 *    ports' draw plus CONFIG_BAY_PORTS_RESERVE_MA must stay within
 *    CONFIG_BAY_PORTS_BUDGET_MA.
 *  - A port's ~FAULT (the TPS2553-1 latches off after 7.5 ms in current
 *    limit) is polled every CONFIG_BAY_PORTS_POLL_MS: the port is marked
 *    latched and its EN goes low; "on" again restarts it.
 *  - RESET and BOOT are open drain, emulated: output register 0, the pin an
 *    output to assert, an input (100k pull-up, reads 1) to release.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdio.h>

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/byteorder.h>

#include "bay.h"

LOG_MODULE_REGISTER(ports, CONFIG_BAY_LOG_LEVEL);

#if DT_NODE_EXISTS(DT_NODELABEL(dut_port1))

/* TCA6408A registers */
#define IO_INPUT    0x00
#define IO_OUTPUT   0x01
#define IO_POLARITY 0x02
#define IO_CONFIG   0x03 /* 1: input */

/* INA226 registers */
#define INA_CONFIG 0x00
#define INA_SHUNT  0x01 /* 2.5 uV/LSB, signed */
#define INA_BUS    0x02 /* 1.25 mV/LSB */
/* Averages 16, 1.1 ms conversions, shunt and bus continuous */
#define INA_CONFIG_VALUE 0x4527

#define IO_MAX       2
#define FAIL_LIMIT   3    /* polls without an answer: the board is gone */
#define REPROBE_MS   2000 /* while DUT_5V is on and no board answers */
#define REFUSED_MS   1000 /* a wanted port the budget refused: try again */

struct port_cfg {
	uint8_t slot;
	uint8_t hub_port;
	uint8_t io;  /* the expander's I2C address */
	uint8_t en;  /* pins on that expander */
	uint8_t flt;
	uint8_t rst; /* 0xFF: none */
	uint8_t bst;
	uint8_t ina; /* the INA226's I2C address */
	uint32_t rshunt_uohm;
};

#define PIN_OR_NONE(node, prop) COND_CODE_1(DT_NODE_HAS_PROP(node, prop), (DT_GPIO_PIN(node, prop)), (0xFF))

#define PORT_CFG(node)                                                                             \
	IF_ENABLED(DT_NODE_HAS_PROP(node, sub_slot), ({                                            \
		.slot = DT_PROP(node, sub_slot),                                                   \
		.hub_port = DT_PROP(node, hub_port),                                               \
		.io = DT_REG_ADDR(DT_GPIO_CTLR(node, enable_gpios)),                               \
		.en = DT_GPIO_PIN(node, enable_gpios),                                             \
		.flt = DT_GPIO_PIN(node, fault_gpios),                                             \
		.rst = PIN_OR_NONE(node, reset_gpios),                                             \
		.bst = PIN_OR_NONE(node, boot_gpios),                                              \
		.ina = DT_REG_ADDR(DT_PHANDLE(node, power_monitor)),                               \
		.rshunt_uohm = DT_PROP(DT_PHANDLE(node, power_monitor), rshunt_micro_ohms),        \
	},))

static const struct port_cfg cfg[] = {DT_FOREACH_STATUS_OKAY(hwtr_dut_port, PORT_CFG)};

#define NPORTS ARRAY_SIZE(cfg)

static const struct device *const bus = DEVICE_DT_GET(DT_BUS(DT_NODELABEL(ports_io0)));

struct port {
	bool wanted;  /* to be on: at boot, and after each DUT_5V on */
	bool on;
	bool latched; /* off after a fault, until switched on again */
	bool refused; /* the budget had no room: said once */
	uint32_t faults;
};

/* An expander's shadow registers: the chip loses them with DUT_5V */
struct io {
	uint8_t addr;
	uint8_t out;
	uint8_t cfg;
};

static struct port ports[NPORTS];
static struct io io[IO_MAX];
static int nio;
static bool present;  /* the board answered at the last probe */
static bool chips_up; /* DUT_5V on and the chips set up */
static int failures;
static K_MUTEX_DEFINE(lock);

static void setup_handler(struct k_work *work);
static void admit_handler(struct k_work *work);
static void poll_handler(struct k_work *work);
static K_WORK_DELAYABLE_DEFINE(setup_work, setup_handler);
static K_WORK_DELAYABLE_DEFINE(admit_work, admit_handler);
static K_WORK_DELAYABLE_DEFINE(poll_work, poll_handler);

static struct io *io_of(const struct port_cfg *c)
{
	for (int i = 0; i < nio; i++) {
		if (io[i].addr == c->io) {
			return &io[i];
		}
	}
	return NULL;
}

static int io_write(const struct io *x, uint8_t reg, uint8_t val)
{
	return i2c_reg_write_byte(bus, x->addr, reg, val);
}

static int ina_read(uint8_t addr, uint8_t reg, uint16_t *val)
{
	uint8_t buf[2];
	int ret = i2c_write_read(bus, addr, &reg, 1, buf, sizeof(buf));

	if (ret == 0) {
		*val = sys_get_be16(buf);
	}
	return ret;
}

static int ina_write(uint8_t addr, uint8_t reg, uint16_t val)
{
	uint8_t buf[3] = {reg, val >> 8, val & 0xFF};

	return i2c_write(bus, buf, sizeof(buf), addr);
}

/* A port's VBUS and current (lock held, chips up) */
static int read_meter(int i, int32_t *mv, int32_t *ma)
{
	uint16_t shunt, vbus;
	int ret = ina_read(cfg[i].ina, INA_SHUNT, &shunt);

	if (ret == 0) {
		ret = ina_read(cfg[i].ina, INA_BUS, &vbus);
	}
	if (ret != 0) {
		return ret;
	}
	/* 2.5 uV/LSB across the shunt; 1.25 mV/LSB on the bus */
	*ma = (int32_t)((int64_t)(int16_t)shunt * 2500 / cfg[i].rshunt_uohm);
	*mv = vbus * 5 / 4;

	return 0;
}

/* What the ports other than skip draw (lock held) */
static int32_t others_ma(int skip)
{
	int32_t total = 0, mv, ma;

	for (int i = 0; i < NPORTS; i++) {
		if (i != skip && ports[i].on && read_meter(i, &mv, &ma) == 0) {
			total += MAX(ma, 0);
		}
	}
	return total;
}

static int en_write(int i, bool on)
{
	struct io *x = io_of(&cfg[i]);

	WRITE_BIT(x->out, cfg[i].en, on);
	return io_write(x, IO_OUTPUT, x->out);
}

/* RESET or BOOT: an output (its register bit is 0) asserts it, an input releases it */
static int line_write(int i, uint8_t pin, bool asserted)
{
	struct io *x = io_of(&cfg[i]);

	if (pin == 0xFF) {
		return -ENOTSUP;
	}
	WRITE_BIT(x->cfg, pin, !asserted);
	return io_write(x, IO_CONFIG, x->cfg);
}

/* Switch a port on through the admission rule (lock held) */
static int port_on(int i)
{
	int32_t others;
	int ret;

	if (!chips_up) {
		return -EAGAIN;
	}
	others = others_ma(i);
	if (others + CONFIG_BAY_PORTS_RESERVE_MA > CONFIG_BAY_PORTS_BUDGET_MA) {
		return -EBUSY;
	}
	/* A latched TPS2553-1 restarts on an EN low-to-high edge */
	if (ports[i].latched) {
		(void)en_write(i, false);
	}
	ret = en_write(i, true);
	if (ret == 0) {
		ports[i].on = true;
		ports[i].latched = false;
		ports[i].refused = false;
	}
	return ret;
}

static int port_off(int i)
{
	ports[i].on = false;
	return chips_up ? en_write(i, false) : 0;
}

/* Probe and set up the board, every port off (lock held) */
static int setup_chips(void)
{
	uint8_t in;
	int ret = i2c_reg_read_byte(bus, io[0].addr, IO_INPUT, &in);

	present = ret == 0;
	if (!present) {
		return -ENODEV;
	}

	for (int k = 0; k < nio && ret == 0; k++) {
		struct io *x = &io[k];

		/* RESET and BOOT drive low once outputs, EN low; every pin an input but EN */
		x->out = 0;
		x->cfg = 0xFF;
		for (int i = 0; i < NPORTS; i++) {
			if (cfg[i].io == x->addr) {
				x->cfg &= ~BIT(cfg[i].en);
			}
		}
		ret = io_write(x, IO_OUTPUT, x->out);
		if (ret == 0) {
			ret = io_write(x, IO_POLARITY, 0);
		}
		if (ret == 0) {
			ret = io_write(x, IO_CONFIG, x->cfg);
		}
	}
	for (int i = 0; i < NPORTS && ret == 0; i++) {
		ret = ina_write(cfg[i].ina, INA_CONFIG, INA_CONFIG_VALUE);
		ports[i].on = false;
	}
	if (ret != 0) {
		LOG_ERR("DATA x4 set-up failed (%d)", ret);
		return ret;
	}

	chips_up = true;
	failures = 0;
	return 0;
}

static void setup_handler(struct k_work *work)
{
	bool had = present;
	int ret;

	ARG_UNUSED(work);

	if (!dut_power_get()) {
		return;
	}

	k_mutex_lock(&lock, K_FOREVER);
	ret = setup_chips();
	k_mutex_unlock(&lock);

	if (ret == 0) {
		LOG_INF("DATA x4: %d ports, every port off; switching on the wanted ones", NPORTS);
		k_work_reschedule(&admit_work, K_NO_WAIT);
		k_work_reschedule(&poll_work, K_MSEC(CONFIG_BAY_PORTS_POLL_MS));
	} else {
		if (had) {
			LOG_WRN("DATA x4 not answering: a one-port node until it does");
		}
		k_work_reschedule(&setup_work, K_MSEC(REPROBE_MS));
	}
}

/* The wanted ports on, one per CONFIG_BAY_PORTS_STAGGER_MS */
static void admit_handler(struct k_work *work)
{
	int next = -1, ret = 0;
	bool more = false;
	int32_t others = 0;

	ARG_UNUSED(work);

	k_mutex_lock(&lock, K_FOREVER);
	for (int i = 0; i < NPORTS && chips_up; i++) {
		if (ports[i].wanted && !ports[i].on && !ports[i].latched) {
			if (next < 0) {
				next = i;
			} else {
				more = true;
			}
		}
	}
	if (next >= 0) {
		ret = port_on(next);
		if (ret == -EBUSY && !ports[next].refused) {
			ports[next].refused = true;
			others = others_ma(next);
		}
	}
	k_mutex_unlock(&lock);

	if (next < 0) {
		return;
	}
	if (ret == 0) {
		LOG_INF("port %u on", cfg[next].slot);
	} else if (others != 0) {
		LOG_WRN("port %u waits: the other ports draw %d mA (budget %d mA)", cfg[next].slot,
			others, CONFIG_BAY_PORTS_BUDGET_MA);
	}
	if (ret != 0 || more) {
		k_work_reschedule(&admit_work, K_MSEC(ret == -EBUSY ? REFUSED_MS
								     : CONFIG_BAY_PORTS_STAGGER_MS));
	}
}

/* ~FAULT of the ports that are on, and whether the board still answers */
static void poll_handler(struct k_work *work)
{
	uint8_t in[IO_MAX];
	int ret = 0;
	bool gone = false;
	uint32_t tripped = 0;

	ARG_UNUSED(work);

	k_mutex_lock(&lock, K_FOREVER);
	if (!chips_up) {
		k_mutex_unlock(&lock);
		return;
	}
	for (int k = 0; k < nio && ret == 0; k++) {
		ret = i2c_reg_read_byte(bus, io[k].addr, IO_INPUT, &in[k]);
	}
	if (ret != 0) {
		gone = ++failures >= FAIL_LIMIT;
		if (gone) {
			chips_up = false;
			present = false;
			for (int i = 0; i < NPORTS; i++) {
				ports[i].on = false;
			}
		}
	} else {
		failures = 0;
		for (int i = 0; i < NPORTS; i++) {
			const struct io *x = io_of(&cfg[i]);
			bool flt = (in[x - io] & BIT(cfg[i].flt)) == 0; /* ~FAULT, active low */

			if (ports[i].on && flt) {
				(void)en_write(i, false);
				ports[i].on = false;
				ports[i].latched = true;
				ports[i].faults++;
				tripped |= BIT(i);
			}
		}
	}
	k_mutex_unlock(&lock);

	for (int i = 0; i < NPORTS; i++) {
		if (tripped & BIT(i)) {
			LOG_ERR("port %u in current limit: off (\"on\" again to retry)", cfg[i].slot);
		}
	}
	if (gone) {
		LOG_ERR("DATA x4 stopped answering: its ports are off");
		k_work_reschedule(&setup_work, K_MSEC(REPROBE_MS));
		return;
	}
	k_work_reschedule(&poll_work, K_MSEC(CONFIG_BAY_PORTS_POLL_MS));
}

void ports_dut_power(bool on)
{
	if (on) {
		k_work_reschedule(&setup_work, K_MSEC(CONFIG_BAY_PORTS_SETTLE_MS));
		return;
	}

	/* DUT_5V goes off: every EN low while the chips still answer, then hands off */
	k_work_cancel_delayable(&setup_work);
	k_work_cancel_delayable(&admit_work);
	k_mutex_lock(&lock, K_FOREVER);
	if (chips_up) {
		for (int k = 0; k < nio; k++) {
			io[k].out = 0;
			(void)io_write(&io[k], IO_OUTPUT, 0);
		}
	}
	for (int i = 0; i < NPORTS; i++) {
		ports[i].on = false;
	}
	chips_up = false;
	k_mutex_unlock(&lock);
}

int ports_init(void)
{
	if (!device_is_ready(bus)) {
		return -ENODEV;
	}

	for (int i = 0; i < NPORTS; i++) {
		if (io_of(&cfg[i]) == NULL) {
			if (nio == IO_MAX) {
				return -EINVAL;
			}
			io[nio++].addr = cfg[i].io;
		}
		ports[i].wanted = IS_ENABLED(CONFIG_BAY_PORTS_ON_AT_BOOT);
	}
	/* DUT_5V is on (dut_init keeps it so): look for the board */
	k_work_reschedule(&setup_work, K_MSEC(CONFIG_BAY_PORTS_SETTLE_MS));

	return 0;
}

int ports_count(void)
{
	return present ? NPORTS : 0;
}

static int index_of(int slot)
{
	for (int i = 0; i < NPORTS; i++) {
		if (cfg[i].slot == slot) {
			return present ? i : -ENODEV;
		}
	}
	return -ENOENT;
}

int ports_info(int slot, struct port_info *pi)
{
	int i = index_of(slot);

	if (i < 0) {
		return i;
	}

	*pi = (struct port_info){.slot = cfg[i].slot, .hub_port = cfg[i].hub_port};
	k_mutex_lock(&lock, K_FOREVER);
	pi->on = ports[i].on;
	pi->wanted = ports[i].wanted;
	pi->latched = ports[i].latched;
	pi->faults = ports[i].faults;
	pi->meter = ports[i].on && read_meter(i, &pi->mv, &pi->ma) == 0;
	k_mutex_unlock(&lock);
	pi->mw = pi->meter ? pi->mv * pi->ma / 1000 : 0;
	pi->usb = usb_host_port_device(cfg[i].hub_port, &pi->vid, &pi->pid) == 0;

	return 0;
}

int ports_power(int slot, bool on, int32_t *others)
{
	int i = index_of(slot);
	int ret;

	if (i < 0) {
		return i;
	}

	k_mutex_lock(&lock, K_FOREVER);
	if (on) {
		ret = ports[i].on ? 0 : port_on(i);
		/* Refused: not wanted either, it would come on behind the caller's back */
		ports[i].wanted = ret == 0;
		if (ret == -EBUSY && others != NULL) {
			*others = others_ma(i);
		}
	} else {
		ports[i].wanted = false;
		ret = port_off(i);
	}
	k_mutex_unlock(&lock);

	LOG_INF("port %d %s%s", slot, on ? "on" : "off", ret == 0 ? "" : ": refused");
	return ret;
}

int ports_power_cycle(int slot, k_timeout_t off_time, int32_t *others)
{
	int ret = ports_power(slot, false, NULL);

	if (ret != 0) {
		return ret;
	}
	k_sleep(off_time);

	return ports_power(slot, true, others);
}

static int line_set(int slot, bool reset, bool asserted)
{
	int i = index_of(slot);
	int ret;

	if (i < 0) {
		return i;
	}
	k_mutex_lock(&lock, K_FOREVER);
	ret = chips_up ? line_write(i, reset ? cfg[i].rst : cfg[i].bst, asserted) : -EAGAIN;
	k_mutex_unlock(&lock);

	return ret;
}

int ports_reset_pulse(int slot, k_timeout_t width)
{
	int ret = line_set(slot, true, true);

	if (ret != 0) {
		return ret;
	}
	k_sleep(width);

	return line_set(slot, true, false);
}

int ports_boot(int slot, bool power_cycle, int32_t *others)
{
	int ret = line_set(slot, false, true);

	if (ret != 0) {
		return ret;
	}

	/* BOOT held across a RESET pulse, or across a power cycle of the port */
	if (power_cycle) {
		ret = ports_power_cycle(slot, K_MSEC(CONFIG_BAY_POWER_CYCLE_MS), others);
	} else {
		ret = ports_reset_pulse(slot, K_MSEC(CONFIG_BAY_RESET_PULSE_MS));
	}
	k_sleep(K_MSEC(CONFIG_BAY_BOOTLOADER_HOLD_MS));
	(void)line_set(slot, false, false);

	return ret;
}

#else /* no DATA x4 in the devicetree: a one-port node */

void ports_dut_power(bool on)
{
	ARG_UNUSED(on);
}

int ports_init(void)
{
	return 0;
}

int ports_count(void)
{
	return 0;
}

int ports_info(int slot, struct port_info *pi)
{
	ARG_UNUSED(slot);
	ARG_UNUSED(pi);
	return -ENOENT;
}

int ports_power(int slot, bool on, int32_t *others)
{
	ARG_UNUSED(slot);
	ARG_UNUSED(on);
	ARG_UNUSED(others);
	return -ENOENT;
}

int ports_power_cycle(int slot, k_timeout_t off_time, int32_t *others)
{
	ARG_UNUSED(slot);
	ARG_UNUSED(off_time);
	ARG_UNUSED(others);
	return -ENOENT;
}

int ports_reset_pulse(int slot, k_timeout_t width)
{
	ARG_UNUSED(slot);
	ARG_UNUSED(width);
	return -ENOENT;
}

int ports_boot(int slot, bool power_cycle, int32_t *others)
{
	ARG_UNUSED(slot);
	ARG_UNUSED(power_cycle);
	ARG_UNUSED(others);
	return -ENOENT;
}

#endif
