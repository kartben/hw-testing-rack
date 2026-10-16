/*
 * hw-testing-rack bay node.
 *
 * The USB/IP service (CONFIG_USBIP) starts by itself before main() and
 * exports whatever enumerates on the DUT port.  main() brings up the rest:
 * DUT power and fault handling, the data-path muxes, the AUX UART bridge,
 * Wi-Fi, and then drives the status LED.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/input/input.h>
#include <zephyr/settings/settings.h>
#include <zephyr/logging/log.h>

#include "bay.h"

LOG_MODULE_REGISTER(bay, CONFIG_BAY_LOG_LEVEL);

/* --- Persistent settings: "bay/id", "bay/force_pc" -------------------------- */

static char stored_id[BAY_ID_MAX_LEN + 1];
static bool stored_force_pc;

static int bay_settings_set(const char *key, size_t len, settings_read_cb read_cb, void *cb_arg)
{
	ssize_t n;

	if (settings_name_steq(key, "id", NULL)) {
		if (len > BAY_ID_MAX_LEN) {
			return -EINVAL;
		}
		n = read_cb(cb_arg, stored_id, len);
		if (n < 0) {
			return (int)n;
		}
		stored_id[n] = '\0';
		return 0;
	}

	if (settings_name_steq(key, "force_pc", NULL)) {
		n = read_cb(cb_arg, &stored_force_pc, sizeof(stored_force_pc));
		return n < 0 ? (int)n : 0;
	}

	return -ENOENT;
}

SETTINGS_STATIC_HANDLER_DEFINE(bay, "bay", NULL, bay_settings_set, NULL, NULL);

int bay_settings_save_force_pc(bool force)
{
	return settings_save_one("bay/force_pc", &force, sizeof(force));
}

int bay_settings_save_id(const char *id)
{
	return settings_save_one("bay/id", id, strlen(id));
}

/* --- BOOT button: a press of 1 s or more power-cycles the DUT -------------- */

#define LONG_PRESS_MS 1000

static void power_cycle_handler(struct k_work *work)
{
	ARG_UNUSED(work);
	LOG_INF("BOOT button: DUT power cycle");
	dut_power_cycle(K_MSEC(CONFIG_BAY_POWER_CYCLE_MS));
}

static K_WORK_DEFINE(power_cycle_work, power_cycle_handler);

static void button_cb(struct input_event *evt, void *user_data)
{
	static int64_t pressed_at;

	ARG_UNUSED(user_data);

	if (evt->type != INPUT_EV_KEY || evt->code != INPUT_KEY_0) {
		return;
	}

	if (evt->value != 0) {
		pressed_at = k_uptime_get();
	} else if (k_uptime_get() - pressed_at >= LONG_PRESS_MS) {
		k_work_submit(&power_cycle_work);
	}
}

INPUT_CALLBACK_DEFINE(NULL, button_cb, NULL);

int main(void)
{
	int ret;

	LOG_INF("hw-testing-rack bay node");

	ret = settings_subsys_init();
	if (ret == 0) {
		ret = settings_load();
	}
	if (ret != 0) {
		LOG_ERR("settings unavailable (%d): defaults only", ret);
	}

	ret = dut_init();
	if (ret != 0) {
		LOG_ERR("DUT control init failed: %d", ret);
	}

	ret = usb_mux_init(stored_force_pc);
	if (ret != 0) {
		LOG_ERR("USB mux init failed: %d", ret);
	}

	(void)status_led_init();

	ret = aux_bridge_init();
	if (ret != 0) {
		LOG_ERR("AUX UART init failed: %d", ret);
	}

	ret = bay_net_init(stored_id);
	if (ret != 0) {
		LOG_ERR("network init failed: %d", ret);
	}

	while (true) {
		status_led_update();
		k_sleep(K_MSEC(250));
	}

	return 0;
}
