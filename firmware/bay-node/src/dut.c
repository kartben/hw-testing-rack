/*
 * DUT power (TPS2553), fault handling, INA226 readout and AUX RESET/BOOT.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/logging/log.h>

#include "bay.h"

LOG_MODULE_REGISTER(dut, CONFIG_BAY_LOG_LEVEL);

#define DUT_NODE DT_NODELABEL(dut_port)

static const struct gpio_dt_spec en = GPIO_DT_SPEC_GET(DUT_NODE, enable_gpios);
static const struct gpio_dt_spec flt = GPIO_DT_SPEC_GET(DUT_NODE, fault_gpios);
static const struct gpio_dt_spec rst = GPIO_DT_SPEC_GET_OR(DUT_NODE, reset_gpios, {0});
static const struct gpio_dt_spec boot = GPIO_DT_SPEC_GET_OR(DUT_NODE, boot_gpios, {0});

static const struct device *const meter =
	COND_CODE_1(DT_NODE_HAS_PROP(DUT_NODE, power_monitor),
		    (DEVICE_DT_GET(DT_PHANDLE(DUT_NODE, power_monitor))), (NULL));

static K_MUTEX_DEFINE(dut_lock);
static bool power_on;
static atomic_t fault_latched;
static atomic_t fault_count;
static struct gpio_callback flt_cb;

static void power_write(bool on)
{
	/*
	 * No AUX TX into an unpowered board: release the pin before cutting
	 * VBUS.  A DATA x4 turns its ports off while its chips still answer, and
	 * is set up again once VBUS is back.
	 */
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
}

static void fault_work_handler(struct k_work *work)
{
	ARG_UNUSED(work);

	if (gpio_pin_get_dt(&flt) <= 0) {
		return;
	}

	k_mutex_lock(&dut_lock, K_FOREVER);
	power_write(false);
	atomic_set(&fault_latched, 1);
	k_mutex_unlock(&dut_lock);

	LOG_ERR("DUT in current limit for %d ms: VBUS switched off (\"bay power on\" to retry)",
		CONFIG_BAY_DUT_FAULT_OFF_MS);
}

static K_WORK_DELAYABLE_DEFINE(fault_work, fault_work_handler);

static void fault_check(void)
{
	if (gpio_pin_get_dt(&flt) > 0) {
		atomic_inc(&fault_count);
		LOG_WRN("DUT VBUS fault (over-current or over-temperature)");
		if (CONFIG_BAY_DUT_FAULT_OFF_MS > 0) {
			k_work_reschedule(&fault_work, K_MSEC(CONFIG_BAY_DUT_FAULT_OFF_MS));
		}
	} else {
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

	/* EN is pulled up on the board: the DUT is already powered, keep it so */
	ret = gpio_pin_configure_dt(&en, GPIO_OUTPUT_ACTIVE);
	if (ret != 0) {
		return ret;
	}
	power_on = true;

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

int dut_power_set(bool on)
{
	k_mutex_lock(&dut_lock, K_FOREVER);
	if (on) {
		atomic_set(&fault_latched, 0);
	}
	power_write(on);
	k_mutex_unlock(&dut_lock);

	LOG_INF("DUT VBUS %s", on ? "on" : "off");

	return 0;
}

bool dut_power_get(void)
{
	return power_on;
}

int dut_power_cycle(k_timeout_t off_time)
{
	dut_power_set(false);
	k_sleep(off_time);

	return dut_power_set(true);
}

bool dut_fault_active(void)
{
	return gpio_pin_get_dt(&flt) > 0;
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
