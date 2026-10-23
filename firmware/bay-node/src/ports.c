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
 *    CONFIG_BAY_PORTS_STAGGER_MS, through the admission rule: what the bay
 *    draws plus CONFIG_BAY_PORTS_RESERVE_MA must stay within
 *    CONFIG_BAY_PORTS_BUDGET_MA.  The bay's draw is the node's own INA226,
 *    on DUT_5V (the board itself, its hub and co-processor, counts too);
 *    without one, the ports' sum plus CONFIG_BAY_PORTS_BOARD_MA.
 *  - Over CONFIG_BAY_PORTS_SHED_MA (the node's INA226 ALERT, or the poll as
 *    a backup), the last port switched on goes off; it stays wanted, and
 *    comes back once the budget has room for what it drew.
 *  - A port's ~FAULT (the TPS2553-1 latches off after 7.5 ms in current
 *    limit) is polled every CONFIG_BAY_PORTS_POLL_MS: the port is marked
 *    latched and goes off; "on" again restarts it.
 *  - RESET and BOOT are open drain, emulated: output register 0, the pin an
 *    output to assert, an input (100k pull-up, reads 1) to release.  A port
 *    that is off holds both asserted (no pull-up feeds an unpowered board);
 *    after EN, BOOT is released, then RESET.
 *  - The ports are sink-only, with no CC detection: a port whose VBUS reads
 *    over CONFIG_BAY_PORTS_VBUS_FOREIGN_MV while off is not switched on (a
 *    board powered from elsewhere); a wanted one comes on once it has gone.
 *    A power cycle waits for the port's VBUS to read under
 *    CONFIG_BAY_PORTS_VBUS_OFF_MV, CONFIG_BAY_PORTS_DISCHARGE_MS at most:
 *    the TPS2553-1 does not discharge its output, a port with nothing on it
 *    keeps 1.5-2 V.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdio.h>

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/byteorder.h>

#include "bay.h"

LOG_MODULE_REGISTER(ports, CONFIG_BAY_LOG_LEVEL);

#if DT_NODE_EXISTS(DT_NODELABEL(dut_port1))

/* TCA6408A registers (the TCA9534A's are the same) */
#define IO_INPUT    0x00
#define IO_OUTPUT   0x01
#define IO_POLARITY 0x02
#define IO_CONFIG   0x03 /* 1: input */

/* INA226 registers */
#define INA_CONFIG 0x00
#define INA_SHUNT  0x01 /* 2.5 uV/LSB, signed */
#define INA_BUS    0x02 /* 1.25 mV/LSB */
#define INA_MASK   0x06
#define INA_LIMIT  0x07
#define INA_SOL    BIT(15) /* ALERT on the shunt over the limit, not latched */
/* Averages 16, 1.1 ms conversions, shunt and bus continuous */
#define INA_CONFIG_VALUE 0x4527

#define IO_MAX       2
#define FAIL_LIMIT   3    /* polls without an answer: the board is gone */
#define REPROBE_MS   2000 /* while DUT_5V is on and no board answers */
#define REFUSED_MS   1000 /* a wanted port the budget refused: try again */
#define RELEASE_MS   5    /* EN to BOOT and RESET released: the port's VBUS is up */
#define SHED_MS      20   /* a port shed to the next reading: the meter averages 8.8 ms */

/* DATA x4 v2: the matrix expander (TCA9534A, not fitted on the base v2), its P7 MARK */
#define MX_MARK 7

/*
 * The node's own INA226 (dut_port's power-monitor) on DUT_5V: what the whole
 * bay draws.  Its driver sets it up (dut.c reads it); this file reads its
 * shunt and sets its ALERT for the shedding.
 */
#define METER     DT_PHANDLE(DT_NODELABEL(dut_port), power_monitor)
#define HAS_METER DT_NODE_HAS_PROP(DT_NODELABEL(dut_port), power_monitor)

static const struct i2c_dt_spec meter = COND_CODE_1(HAS_METER, (I2C_DT_SPEC_GET(METER)), ({0}));
static const struct gpio_dt_spec meter_alert =
	COND_CODE_1(HAS_METER, (GPIO_DT_SPEC_GET_OR(METER, alert_gpios, {0})), ({0}));
#define METER_UOHM COND_CODE_1(HAS_METER, (DT_PROP(METER, rshunt_micro_ohms)), (1))

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
	bool refused; /* the budget, or its VBUS, kept it off: said once */
	uint32_t seq; /* when it went on: the last one goes first when the bay sheds */
	int32_t need; /* shed: what it drew, the room it needs to come back (mA) */
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
static uint32_t admissions;
static int64_t shed_at;
static struct gpio_callback alert_cb;
static K_MUTEX_DEFINE(lock);

static void setup_handler(struct k_work *work);
static void admit_handler(struct k_work *work);
static void poll_handler(struct k_work *work);
static void shed_handler(struct k_work *work);
static K_WORK_DELAYABLE_DEFINE(setup_work, setup_handler);
static K_WORK_DELAYABLE_DEFINE(admit_work, admit_handler);
static K_WORK_DELAYABLE_DEFINE(poll_work, poll_handler);
static K_WORK_DELAYABLE_DEFINE(shed_work, shed_handler);

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

/* What the ports that are on draw (lock held) */
static int32_t ports_ma(void)
{
	int32_t total = 0, mv, ma;

	for (int i = 0; i < NPORTS; i++) {
		if (ports[i].on && read_meter(i, &mv, &ma) == 0) {
			total += MAX(ma, 0);
		}
	}
	return total;
}

/*
 * What the bay draws from DUT_5V (lock held): the node's INA226, or without
 * one (a stand-in, or it does not answer) the ports' sum plus
 * CONFIG_BAY_PORTS_BOARD_MA for the board itself.
 */
static int32_t bay_ma(void)
{
	uint8_t reg = INA_SHUNT, buf[2];

	if (meter.bus != NULL && i2c_write_read_dt(&meter, &reg, 1, buf, sizeof(buf)) == 0) {
		return MAX((int32_t)((int64_t)(int16_t)sys_get_be16(buf) * 2500 / METER_UOHM), 0);
	}
	return ports_ma() + CONFIG_BAY_PORTS_BOARD_MA;
}

/* The node's INA226 ALERT while its shunt reads over CONFIG_BAY_PORTS_SHED_MA */
static void meter_setup(void)
{
	uint16_t limit = MIN((uint64_t)CONFIG_BAY_PORTS_SHED_MA * METER_UOHM / 2500, INT16_MAX);
	uint8_t lim[3] = {INA_LIMIT, limit >> 8, limit & 0xFF};
	uint8_t mask[3] = {INA_MASK, INA_SOL >> 8, INA_SOL & 0xFF};

	if (meter.bus == NULL || i2c_write_dt(&meter, lim, sizeof(lim)) != 0 ||
	    i2c_write_dt(&meter, mask, sizeof(mask)) != 0) {
		LOG_WRN("no ALERT from the node's INA226: the poll sheds");
	}
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

/* Switch a port on (lock held): the admission rule, its VBUS, then BOOT and RESET released */
static int port_on(int i, bool keep_boot)
{
	int32_t mv, ma;
	int ret;

	if (!chips_up) {
		return -EAGAIN;
	}
	if (bay_ma() + MAX(CONFIG_BAY_PORTS_RESERVE_MA, ports[i].need) > CONFIG_BAY_PORTS_BUDGET_MA) {
		return -EBUSY;
	}
	/* Sink-only, no CC detection: a VBUS already there is not ours to meet */
	ret = read_meter(i, &mv, &ma);
	if (ret != 0) {
		return ret;
	}
	if (mv > CONFIG_BAY_PORTS_VBUS_FOREIGN_MV) {
		if (!ports[i].refused) {
			LOG_WRN("port %u: VBUS %d mV while off, not switched on", cfg[i].slot, mv);
		}
		return -EALREADY;
	}
	/* A latched TPS2553-1 restarts on an EN low-to-high edge */
	if (ports[i].latched) {
		(void)en_write(i, false);
	}
	ret = en_write(i, true);
	if (ret != 0) {
		return ret;
	}
	ports[i].on = true;
	ports[i].latched = false;
	ports[i].refused = false;
	ports[i].need = 0;
	ports[i].seq = ++admissions;

	k_sleep(K_MSEC(RELEASE_MS));
	if (!keep_boot && cfg[i].bst != 0xFF) {
		ret = line_write(i, cfg[i].bst, false);
	}
	if (ret == 0 && cfg[i].rst != 0xFF) {
		ret = line_write(i, cfg[i].rst, false);
	}
	return ret;
}

/* A port off: RESET and BOOT asserted, then EN low (lock held) */
static int port_off(int i)
{
	struct io *x = io_of(&cfg[i]);
	int ret;

	ports[i].on = false;
	if (!chips_up) {
		return 0;
	}
	if (cfg[i].rst != 0xFF) {
		WRITE_BIT(x->cfg, cfg[i].rst, 0);
	}
	if (cfg[i].bst != 0xFF) {
		WRITE_BIT(x->cfg, cfg[i].bst, 0);
	}
	ret = io_write(x, IO_CONFIG, x->cfg);
	if (ret == 0) {
		ret = en_write(i, false);
	}
	return ret;
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

		/* Output register 0, then EN, RESET and BOOT outputs: off, both lines asserted */
		x->out = 0;
		x->cfg = 0xFF;
		for (int i = 0; i < NPORTS; i++) {
			if (cfg[i].io == x->addr) {
				x->cfg &= ~BIT(cfg[i].en);
				x->cfg &= cfg[i].rst != 0xFF ? ~BIT(cfg[i].rst) : 0xFF;
				x->cfg &= cfg[i].bst != 0xFF ? ~BIT(cfg[i].bst) : 0xFF;
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
#if DT_NODE_EXISTS(DT_NODELABEL(ports_mx))
	/* MARK an output, low (its register first); the rest of the expander is the co-processor's */
	if (i2c_reg_write_byte(bus, DT_REG_ADDR(DT_NODELABEL(ports_mx)), IO_OUTPUT,
			       (uint8_t)~BIT(MX_MARK)) == 0) {
		(void)i2c_reg_write_byte(bus, DT_REG_ADDR(DT_NODELABEL(ports_mx)), IO_CONFIG,
					 (uint8_t)~BIT(MX_MARK));
	}
#endif
	meter_setup();

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
	bool more = false, said = false;
	int32_t bay = 0;

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
		ret = port_on(next, false);
		if ((ret == -EBUSY || ret == -EALREADY) && !ports[next].refused) {
			ports[next].refused = true;
			said = ret == -EBUSY;
			bay = bay_ma();
		}
	}
	k_mutex_unlock(&lock);

	if (next < 0) {
		return;
	}
	if (ret == 0) {
		LOG_INF("port %u on", cfg[next].slot);
	} else if (said) {
		LOG_WRN("port %u waits: the bay draws %d mA (budget %d mA)", cfg[next].slot, bay,
			CONFIG_BAY_PORTS_BUDGET_MA);
	}
	if (ret != 0 || more) {
		k_work_reschedule(&admit_work,
				  K_MSEC(ret == -EBUSY || ret == -EALREADY ? REFUSED_MS
									 : CONFIG_BAY_PORTS_STAGGER_MS));
	}
}

/*
 * The bay over CONFIG_BAY_PORTS_SHED_MA: the last port switched on goes off,
 * still wanted (it comes back once the budget has room for what it drew),
 * and the bay is read again once the meter has a new average.
 */
static void shed_handler(struct k_work *work)
{
	int32_t bay = 0, mv, ma = 0;
	int64_t wait;
	int last = -1;

	ARG_UNUSED(work);

	k_mutex_lock(&lock, K_FOREVER);
	wait = shed_at + SHED_MS - k_uptime_get();
	if (wait > 0) {
		k_mutex_unlock(&lock);
		k_work_reschedule(&shed_work, K_MSEC(wait));
		return;
	}
	if (chips_up) {
		bay = bay_ma();
	}
	for (int i = 0; i < NPORTS && bay > CONFIG_BAY_PORTS_SHED_MA; i++) {
		if (ports[i].on && (last < 0 || ports[i].seq > ports[last].seq)) {
			last = i;
		}
	}
	if (last >= 0) {
		if (read_meter(last, &mv, &ma) != 0) {
			ma = 0;
		}
		(void)port_off(last);
		ports[last].need = MAX(ma, 0);
		ports[last].refused = false;
		shed_at = k_uptime_get();
	}
	k_mutex_unlock(&lock);

	if (last < 0) {
		return;
	}
	LOG_WRN("the bay draws %d mA, over %d mA: port %u off (it drew %d mA) until there is room",
		bay, CONFIG_BAY_PORTS_SHED_MA, cfg[last].slot, ma);
	k_work_reschedule(&shed_work, K_MSEC(SHED_MS));
	k_work_reschedule(&admit_work, K_MSEC(REFUSED_MS));
}

static void alert_isr(const struct device *dev, struct gpio_callback *cb, uint32_t pins)
{
	ARG_UNUSED(dev);
	ARG_UNUSED(cb);
	ARG_UNUSED(pins);

	k_work_reschedule(&shed_work, K_NO_WAIT);
}

/* ~FAULT of the ports that are on, whether the board still answers, the bay's draw */
static void poll_handler(struct k_work *work)
{
	uint8_t in[IO_MAX];
	int ret = 0;
	bool gone = false, over = false;
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
				(void)port_off(i);
				ports[i].latched = true;
				ports[i].faults++;
				tripped |= BIT(i);
			}
		}
		over = bay_ma() > CONFIG_BAY_PORTS_SHED_MA;
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
	if (over) {
		k_work_reschedule(&shed_work, K_NO_WAIT);
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
	k_work_cancel_delayable(&shed_work);
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
	/* The node's INA226 ALERT (IO39): the bay over CONFIG_BAY_PORTS_SHED_MA */
	if (meter_alert.port != NULL && gpio_is_ready_dt(&meter_alert) &&
	    gpio_pin_configure_dt(&meter_alert, GPIO_INPUT) == 0) {
		gpio_init_callback(&alert_cb, alert_isr, BIT(meter_alert.pin));
		if (gpio_add_callback_dt(&meter_alert, &alert_cb) == 0) {
			(void)gpio_pin_interrupt_configure_dt(&meter_alert, GPIO_INT_EDGE_TO_ACTIVE);
		}
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

static int power_on(int slot, int32_t *others, bool keep_boot)
{
	int i = index_of(slot);
	int ret;

	if (i < 0) {
		return i;
	}

	k_mutex_lock(&lock, K_FOREVER);
	ret = ports[i].on ? 0 : port_on(i, keep_boot);
	/*
	 * Refused by the budget: not wanted either, it would come on behind the
	 * caller's back.  VBUS still up: wanted, on once it has dropped.
	 */
	ports[i].wanted = ret == 0 || ret == -EALREADY;
	ports[i].refused = ret == -EALREADY;
	if (ret == -EBUSY && others != NULL) {
		*others = bay_ma();
	}
	k_mutex_unlock(&lock);

	if (ret == -EALREADY) {
		k_work_reschedule(&admit_work, K_MSEC(REFUSED_MS));
	}
	LOG_INF("port %d on%s", slot, ret == 0 ? "" : ": refused");
	return ret;
}

int ports_power(int slot, bool on, int32_t *others)
{
	int i = index_of(slot);
	int ret;

	if (on) {
		return power_on(slot, others, false);
	}
	if (i < 0) {
		return i;
	}

	k_mutex_lock(&lock, K_FOREVER);
	ports[i].wanted = false;
	ports[i].need = 0;
	ret = port_off(i);
	k_mutex_unlock(&lock);

	LOG_INF("port %d off", slot);
	return ret;
}

/* Off for off_time, then until its VBUS reads under CONFIG_BAY_PORTS_VBUS_OFF_MV (or the timeout) */
static int power_cycle(int slot, k_timeout_t off_time, int32_t *others, bool keep_boot)
{
	int i = index_of(slot);
	int64_t until;
	int32_t mv = 0, ma;
	int ret = ports_power(slot, false, NULL);

	if (ret != 0) {
		return ret;
	}
	k_sleep(off_time);

	until = k_uptime_get() + CONFIG_BAY_PORTS_DISCHARGE_MS;
	do {
		k_mutex_lock(&lock, K_FOREVER);
		ret = chips_up ? read_meter(i, &mv, &ma) : -EAGAIN;
		k_mutex_unlock(&lock);
		if (ret != 0 || mv < CONFIG_BAY_PORTS_VBUS_OFF_MV) {
			break;
		}
		k_sleep(K_MSEC(10));
	} while (k_uptime_get() < until);
	if (ret == 0 && mv >= CONFIG_BAY_PORTS_VBUS_OFF_MV) {
		LOG_INF("port %d: VBUS still %d mV after %d ms off (nothing on it?)", slot, mv,
			CONFIG_BAY_PORTS_DISCHARGE_MS);
	}

	return power_on(slot, others, keep_boot);
}

int ports_power_cycle(int slot, k_timeout_t off_time, int32_t *others)
{
	return power_cycle(slot, off_time, others, false);
}

/* RESET or BOOT of a port that is on: an off port holds both asserted */
static int line_set(int slot, bool reset, bool asserted)
{
	int i = index_of(slot);
	int ret;

	if (i < 0) {
		return i;
	}
	k_mutex_lock(&lock, K_FOREVER);
	ret = chips_up && ports[i].on ? line_write(i, reset ? cfg[i].rst : cfg[i].bst, asserted)
				      : -EAGAIN;
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

int ports_boot(int slot, bool power_cycle_it, int32_t *others)
{
	int ret;

	/* BOOT held across a power cycle of the port (off asserts it), or across a RESET pulse */
	if (power_cycle_it) {
		ret = power_cycle(slot, K_NO_WAIT, others, true);
	} else {
		ret = line_set(slot, false, true);
		if (ret != 0) {
			return ret;
		}
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
