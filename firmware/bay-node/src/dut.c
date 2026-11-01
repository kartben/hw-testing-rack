/*
 * DUT power, fault handling, INA226 readout and AUX RESET/BOOT.
 *
 * Node rev A and the stand-ins: a TPS2553 on the DUT's VBUS, on from the
 * start (its EN is pulled up).  Node rev B (dut_port's vin-efuse): a TPS26600
 * eFuse on VIN, out on the DATA lead as DATA_VIN, off until the DATA lead's
 * power-on rule lets it on (docs/firmware.md):
 *  - before: SCL and SDA idle high and the node's INA226 answers;
 *  - on: ~FLT ignored for CONFIG_BAY_DATA_FLT_BLANK_MS, then DATA_VIN must
 *    read CONFIG_BAY_DATA_VIN_MIN_MV and ~FLT be high;
 *  - then the DATA board answers within CONFIG_BAY_DATA_ANSWER_MS (ports.c);
 *  - a ~FLT, or a board that stops answering, switches it off until the
 *    next power on: the eFuse already retries by itself in a hard short.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/byteorder.h>

#include "bay.h"

LOG_MODULE_REGISTER(dut, CONFIG_BAY_LOG_LEVEL);

#define DUT_NODE  DT_NODELABEL(dut_port)
#define EFUSE     DT_PROP(DUT_NODE, vin_efuse)
#define HAS_METER DT_NODE_HAS_PROP(DUT_NODE, power_monitor)

static const struct gpio_dt_spec en = GPIO_DT_SPEC_GET(DUT_NODE, enable_gpios);
static const struct gpio_dt_spec flt = GPIO_DT_SPEC_GET(DUT_NODE, fault_gpios);
static const struct gpio_dt_spec rst = GPIO_DT_SPEC_GET_OR(DUT_NODE, reset_gpios, {0});
static const struct gpio_dt_spec boot = GPIO_DT_SPEC_GET_OR(DUT_NODE, boot_gpios, {0});
static const struct gpio_dt_spec scl = GPIO_DT_SPEC_GET_BY_IDX_OR(DUT_NODE, bus_gpios, 0, {0});
static const struct gpio_dt_spec sda = GPIO_DT_SPEC_GET_BY_IDX_OR(DUT_NODE, bus_gpios, 1, {0});

static const struct device *const meter =
	COND_CODE_1(HAS_METER, (DEVICE_DT_GET(DT_PHANDLE(DUT_NODE, power_monitor))), (NULL));
/* Read raw for the power-on rule: it must answer even if its driver did not start */
static const struct i2c_dt_spec meter_i2c =
	COND_CODE_1(HAS_METER, (I2C_DT_SPEC_GET(DT_PHANDLE(DUT_NODE, power_monitor))), ({0}));

static K_MUTEX_DEFINE(dut_lock);
static bool power_on;
static atomic_t fault_latched;
static atomic_t fault_count;
static atomic_t lead = ATOMIC_INIT(DUT_LEAD_OK);
static atomic_t lead_lost = ATOMIC_INIT(DUT_LEAD_OK);
static int32_t lead_mv;
static struct gpio_callback flt_cb;

const char *dut_lead_str(enum dut_lead why)
{
	switch (why) {
	case DUT_LEAD_BUS:
		return "SCL or SDA held low: DATA lead reversed?";
	case DUT_LEAD_METER:
		return "the node's INA226 does not answer";
	case DUT_LEAD_SHORT:
		return "no DATA_VIN after switching on: a short on the lead (a camera lead in J7?)";
	case DUT_LEAD_FAULT:
		return "the eFuse reported a fault";
	case DUT_LEAD_NO_BOARD:
		return "no DATA board answers: none, or the wrong lead in J7";
	case DUT_LEAD_BOARD_GONE:
		return "the DATA board stopped answering";
	default:
		return NULL;
	}
}

/* DATA_VIN as the node's INA226 reads it (1.25 mV/LSB) */
static int meter_bus_mv(int32_t *mv)
{
	uint8_t reg = 0x02, buf[2];
	int ret;

	if (meter_i2c.bus == NULL) {
		return -ENODEV;
	}
	ret = i2c_write_read_dt(&meter_i2c, &reg, 1, buf, sizeof(buf));
	if (ret == 0) {
		*mv = sys_get_be16(buf) * 5 / 4;
	}
	return ret;
}

static int lead_refuse(enum dut_lead why, int32_t mv)
{
	atomic_set(&lead, why);
	lead_mv = mv;
	if (why == DUT_LEAD_SHORT) {
		atomic_set(&fault_latched, 1);
		atomic_inc(&fault_count);
		LOG_ERR("DATA_VIN off: %s (%d mV)", dut_lead_str(why), mv);
	} else {
		LOG_ERR("DATA_VIN stays off: %s", dut_lead_str(why));
	}
	return why == DUT_LEAD_METER ? -ENODEV : -EIO;
}

/* The power-on rule's checks around the eFuse going on (dut_lock held) */
static int efuse_on(void)
{
	int32_t mv = 0;

	/* The pins stay the I2C controller's; its input stage reads them */
	if ((scl.port != NULL && gpio_pin_get_raw(scl.port, scl.pin) == 0) ||
	    (sda.port != NULL && gpio_pin_get_raw(sda.port, sda.pin) == 0)) {
		return lead_refuse(DUT_LEAD_BUS, 0);
	}
	if (meter_bus_mv(&mv) != 0) {
		return lead_refuse(DUT_LEAD_METER, 0);
	}

	gpio_pin_set_dt(&en, 1);
	k_sleep(K_MSEC(CONFIG_BAY_DATA_FLT_BLANK_MS));
	if (meter_bus_mv(&mv) != 0 || mv < CONFIG_BAY_DATA_VIN_MIN_MV || gpio_pin_get_dt(&flt) > 0) {
		gpio_pin_set_dt(&en, 0);
		return lead_refuse(DUT_LEAD_SHORT, mv);
	}
	atomic_set(&lead, DUT_LEAD_OK);
	return 0;
}

static void fault_check(void);

static int power_write(bool on)
{
	int ret;

	/*
	 * No AUX TX into an unpowered board: release the pin before cutting
	 * VBUS.  A DATA x4 turns its ports off while its chips still answer, and
	 * is set up again once VBUS is back.
	 */
	if (!EFUSE) {
		if (!on) {
			aux_dut_power(false);
			ports_dut_power(false);
		}
		gpio_pin_set_dt(&en, on);
		power_on = on;
		if (on) {
			aux_dut_power(true);
			ports_dut_power(true);
		}
		return 0;
	}

	if (!on) {
		if (power_on) {
			aux_dut_power(false);
			ports_dut_power(false);
		}
		gpio_pin_set_dt(&en, 0);
		power_on = false;
		return 0;
	}
	if (power_on) {
		return 0;
	}
	ret = efuse_on();
	if (ret != 0) {
		return ret;
	}
	power_on = true;
	/* A ~FLT edge between the check and now went unheeded */
	fault_check();
	aux_dut_power(true);
	ports_dut_power(true);
	return 0;
}

static void fault_work_handler(struct k_work *work)
{
	ARG_UNUSED(work);

	/* Rev A: the TPS2553 limits by itself, act only on a persistent FAULT */
	if (!EFUSE && gpio_pin_get_dt(&flt) <= 0) {
		return;
	}

	k_mutex_lock(&dut_lock, K_FOREVER);
	if (EFUSE && !power_on) {
		/* Off already, or still ramping (efuse_on() checks it then) */
		k_mutex_unlock(&dut_lock);
		return;
	}
	(void)power_write(false);
	atomic_set(&fault_latched, 1);
	if (EFUSE) {
		atomic_set(&lead, DUT_LEAD_FAULT);
	}
	k_mutex_unlock(&dut_lock);

	if (EFUSE) {
		LOG_ERR("DATA_VIN eFuse fault: switched off (\"bay power on\" to retry)");
	} else {
		LOG_ERR("DUT in current limit for %d ms: VBUS switched off (\"bay power on\" to retry)",
			CONFIG_BAY_DUT_FAULT_OFF_MS);
	}
}

static K_WORK_DELAYABLE_DEFINE(fault_work, fault_work_handler);

/* ports.c: the DATA board never answered, or stopped answering */
static void lost_work_handler(struct k_work *work)
{
	enum dut_lead why = (enum dut_lead)atomic_get(&lead_lost);
	bool was_on;

	ARG_UNUSED(work);

	k_mutex_lock(&dut_lock, K_FOREVER);
	was_on = power_on;
	if (was_on) {
		(void)power_write(false);
		atomic_set(&lead, why);
		if (why == DUT_LEAD_BOARD_GONE) {
			atomic_set(&fault_latched, 1);
			atomic_inc(&fault_count);
		}
	}
	k_mutex_unlock(&dut_lock);

	if (was_on) {
		LOG_ERR("DATA_VIN off: %s (\"bay power on\" to try again)", dut_lead_str(why));
	}
}

static K_WORK_DEFINE(lost_work, lost_work_handler);

void dut_lead_lost(enum dut_lead why)
{
	if (EFUSE) {
		atomic_set(&lead_lost, why);
		k_work_submit(&lost_work);
	}
}

static void fault_check(void)
{
	if (gpio_pin_get_dt(&flt) > 0) {
		if (EFUSE) {
			/* Low while off or ramping: only a fault once on */
			if (power_on) {
				atomic_inc(&fault_count);
				k_work_reschedule(&fault_work, K_NO_WAIT);
			}
			return;
		}
		atomic_inc(&fault_count);
		LOG_WRN("DUT VBUS fault (over-current or over-temperature)");
		if (CONFIG_BAY_DUT_FAULT_OFF_MS > 0) {
			k_work_reschedule(&fault_work, K_MSEC(CONFIG_BAY_DUT_FAULT_OFF_MS));
		}
	} else if (!EFUSE) {
		k_work_cancel_delayable(&fault_work);
	}
}

static void flt_isr(const struct device *port, struct gpio_callback *cb, gpio_port_pins_t pins)
{
	ARG_UNUSED(port);
	ARG_UNUSED(cb);
	ARG_UNUSED(pins);

	fault_check();
}

int dut_init(void)
{
	int ret;

	if (!gpio_is_ready_dt(&en) || !gpio_is_ready_dt(&flt)) {
		return -ENODEV;
	}

	/*
	 * Rev A: EN is pulled up on the board, the DUT is already powered: keep
	 * it so.  Rev B: the eFuse is off until the power-on rule lets it on.
	 */
	ret = gpio_pin_configure_dt(&en, EFUSE ? GPIO_OUTPUT_INACTIVE : GPIO_OUTPUT_ACTIVE);
	if (ret != 0) {
		return ret;
	}
	power_on = !EFUSE;

	ret = gpio_pin_configure_dt(&flt, GPIO_INPUT);
	if (ret != 0) {
		return ret;
	}
	gpio_init_callback(&flt_cb, flt_isr, BIT(flt.pin));
	ret = gpio_add_callback_dt(&flt, &flt_cb);
	if (ret != 0) {
		return ret;
	}
	ret = gpio_pin_interrupt_configure_dt(&flt, GPIO_INT_EDGE_BOTH);
	if (ret != 0) {
		return ret;
	}

	if (rst.port != NULL) {
		ret = gpio_pin_configure_dt(&rst, GPIO_OUTPUT_INACTIVE);
		if (ret != 0) {
			return ret;
		}
	}
	if (boot.port != NULL) {
		ret = gpio_pin_configure_dt(&boot, GPIO_OUTPUT_INACTIVE);
		if (ret != 0) {
			return ret;
		}
	}

	if (meter == NULL || !device_is_ready(meter)) {
		LOG_WRN("power monitor not ready: no V/I readings");
	}

	/* A DUT that was already shorted at boot */
	fault_check();

	return 0;
}

void dut_start(void)
{
	if (EFUSE && IS_ENABLED(CONFIG_BAY_DATA_POWER_AT_BOOT)) {
		(void)dut_power_set(true);
	}
}

int dut_power_set(bool on)
{
	int ret;

	k_mutex_lock(&dut_lock, K_FOREVER);
	if (on) {
		atomic_set(&fault_latched, 0);
	} else {
		atomic_set(&lead, DUT_LEAD_OK);
	}
	ret = power_write(on);
	k_mutex_unlock(&dut_lock);

	if (ret == 0) {
		LOG_INF("%s %s", EFUSE ? "DATA_VIN" : "DUT VBUS", on ? "on" : "off");
	}
	return ret;
}

bool dut_power_get(void)
{
	return power_on;
}

enum dut_lead dut_lead_state(int32_t *mv)
{
	if (mv != NULL) {
		*mv = lead_mv;
	}
	return (enum dut_lead)atomic_get(&lead);
}

int dut_power_cycle(k_timeout_t off_time)
{
	dut_power_set(false);
	k_sleep(off_time);

	return dut_power_set(true);
}

bool dut_fault_active(void)
{
	/* Rev B: ~FLT is low whenever the eFuse is off */
	return (!EFUSE || power_on) && gpio_pin_get_dt(&flt) > 0;
}

bool dut_fault_latched(void)
{
	return atomic_get(&fault_latched) != 0;
}

uint32_t dut_fault_count(void)
{
	return (uint32_t)atomic_get(&fault_count);
}

int dut_reset_set(bool asserted)
{
	if (rst.port == NULL) {
		return -ENOTSUP;
	}

	return gpio_pin_set_dt(&rst, asserted);
}

int dut_reset_pulse(k_timeout_t width)
{
	int ret = dut_reset_set(true);

	if (ret != 0) {
		return ret;
	}
	k_sleep(width);

	return dut_reset_set(false);
}

int dut_boot_set(bool asserted)
{
	if (boot.port == NULL) {
		return -ENOTSUP;
	}

	return gpio_pin_set_dt(&boot, asserted);
}

int dut_enter_bootloader(void)
{
	int ret = dut_boot_set(true);

	if (ret != 0) {
		return ret;
	}

	ret = dut_reset_pulse(K_MSEC(CONFIG_BAY_RESET_PULSE_MS));
	k_sleep(K_MSEC(CONFIG_BAY_BOOTLOADER_HOLD_MS));
	(void)dut_boot_set(false);

	return ret;
}

int dut_power_read(struct dut_power_reading *r)
{
	struct sensor_value v;
	int ret;

	if (meter == NULL || !device_is_ready(meter)) {
		return -ENODEV;
	}

	ret = sensor_sample_fetch(meter);
	if (ret != 0) {
		return ret;
	}

	ret = sensor_channel_get(meter, SENSOR_CHAN_VOLTAGE, &v);
	if (ret != 0) {
		return ret;
	}
	r->bus_mv = (int32_t)sensor_value_to_milli(&v);

	ret = sensor_channel_get(meter, SENSOR_CHAN_CURRENT, &v);
	if (ret != 0) {
		return ret;
	}
	r->current_ma = (int32_t)sensor_value_to_milli(&v);

	ret = sensor_channel_get(meter, SENSOR_CHAN_POWER, &v);
	if (ret != 0) {
		return ret;
	}
	r->power_mw = (int32_t)sensor_value_to_milli(&v);

	return 0;
}
