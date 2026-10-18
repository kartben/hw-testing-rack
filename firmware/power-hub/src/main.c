/*
 * hw-testing-rack power hub: the rack controller.
 *
 * USB-C PD input (pd.c), the four eFused rows (rows.c), the rack bus master
 * (bus.c), Wi-Fi and the web page (web.c), the "hub" shell (shell.c).
 * main() brings them up in that order and then drives the CTL LED.  Built
 * with MCUboot (sysbuild), it also takes firmware updates over the network
 * (firmware/common/lib/update.c).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/led.h>
#include <zephyr/input/input.h>
#include <zephyr/settings/settings.h>
#include <zephyr/logging/log.h>

#include <hwtr/admin.h>
#include <hwtr/net.h>
#include <hwtr/update.h>

#include "hub.h"

LOG_MODULE_REGISTER(hub, CONFIG_HUB_LOG_LEVEL);

/* --- Settings: "hub/id", "hub/epr", "hub/rows", "hub/shed", "hub/key" -------- */

static char stored_id[HWTR_ID_MAX_LEN + 1];
static bool stored_epr = IS_ENABLED(CONFIG_HUB_PD_EPR);
static uint8_t stored_rows = BIT_MASK(HUB_ROWS);
static char stored_shed[HUB_ROWS + 1];

static int hub_settings_set(const char *key, size_t len, settings_read_cb read_cb, void *cb_arg)
{
	ssize_t n;

	if (settings_name_steq(key, "id", NULL)) {
		if (len > HWTR_ID_MAX_LEN) {
			return -EINVAL;
		}
		n = read_cb(cb_arg, stored_id, len);
		if (n >= 0) {
			stored_id[n] = '\0';
		}
		return n < 0 ? (int)n : 0;
	}
	if (settings_name_steq(key, "epr", NULL)) {
		n = read_cb(cb_arg, &stored_epr, sizeof(stored_epr));
		return n < 0 ? (int)n : 0;
	}
	if (settings_name_steq(key, "rows", NULL)) {
		n = read_cb(cb_arg, &stored_rows, sizeof(stored_rows));
		return n < 0 ? (int)n : 0;
	}
	if (settings_name_steq(key, "shed", NULL)) {
		if (len != HUB_ROWS) {
			return 0;
		}
		n = read_cb(cb_arg, stored_shed, HUB_ROWS);
		return n < 0 ? (int)n : 0;
	}
	if (settings_name_steq(key, "key", NULL)) {
		uint8_t k[ACL_KEY_LEN];

		if (len != sizeof(k)) {
			return 0;
		}
		n = read_cb(cb_arg, k, sizeof(k));
		if (n == sizeof(k)) {
			hwtr_admin_load(k);
		}
		return n < 0 ? (int)n : 0;
	}

	return -ENOENT;
}

SETTINGS_STATIC_HANDLER_DEFINE(hub, "hub", NULL, hub_settings_set, NULL, NULL);

int hub_settings_save_id(const char *id)
{
	return settings_save_one("hub/id", id, strlen(id));
}

int hub_settings_save_epr(bool epr)
{
	return settings_save_one("hub/epr", &epr, sizeof(epr));
}

int hub_settings_save_rows(uint8_t wanted)
{
	return settings_save_one("hub/rows", &wanted, sizeof(wanted));
}

int hub_settings_save_shed(const char *order)
{
	return settings_save_one("hub/shed", order, HUB_ROWS);
}

/* The admin key (firmware/common/lib/admin.c), or NULL to forget it */
static int save_key(const uint8_t *k)
{
	return k != NULL ? settings_save_one("hub/key", k, ACL_KEY_LEN) : settings_delete("hub/key");
}

/* --- BOOT button: a short press confirms a claim, 10 s forgets the key -------- */

#define RESET_HOLD_MS 10000

static void boot_handler(struct k_work *work)
{
	ARG_UNUSED(work);

	if (hwtr_admin_claim_confirm() == 0) {
		hub_event(HUB_EV_PD, "claimed: admin key set (BOOT pressed)");
	}
}

static void reset_handler(struct k_work *work)
{
	ARG_UNUSED(work);

	(void)hwtr_admin_forget();
	hub_event(HUB_EV_FAULT, "admin key forgotten (BOOT held 10 s): the hub can be claimed again");
}

static K_WORK_DEFINE(boot_work, boot_handler);
static K_WORK_DEFINE(reset_work, reset_handler);

static void button_cb(struct input_event *evt, void *user_data)
{
	static int64_t pressed_at;
	int64_t held;

	ARG_UNUSED(user_data);

	if (evt->type != INPUT_EV_KEY || evt->code != INPUT_KEY_0) {
		return;
	}
	if (evt->value != 0) {
		pressed_at = k_uptime_get();
		return;
	}
	held = k_uptime_get() - pressed_at;
	k_work_submit(held >= RESET_HOLD_MS ? &reset_work : &boot_work);
}

INPUT_CALLBACK_DEFINE(NULL, button_cb, NULL);

static const struct hwtr_admin_cfg admin_cfg = {
	.save = save_key,
	.how_to_confirm = "press the hub's BOOT button (short) or run \"hub access claim\"",
};

/* --- CTL LED -------------------------------------------------------------- */

static const struct led_dt_spec ctl = LED_DT_SPEC_GET(DT_NODELABEL(ctl_led));

/*
 * on                 contract, rows as wanted, no fault
 * slow blink         no PD charger (console USB only), or contract not final yet
 * double blink       rows shed for lack of power
 * fast blink         a row in fault
 * flicker            a claim waits for a press on BOOT
 */
static bool led_level(uint32_t tick)
{
	struct hub_pd_status pd;

	pd_status(&pd);
	if (hwtr_admin_claim_pending()) {
		return tick & 1;
	}
	if (rows_fault_mask() != 0) {
		return tick & 2;
	}
	if (rows_shed_mask() != 0 && pd.final) {
		return (tick % 8) == 0 || (tick % 8) == 2;
	}
	if (!pd.final) {
		return (tick & 4) != 0;
	}
	return true;
}

#if defined(CONFIG_HWTR_UPDATE)
/* A new firmware on trial confirms itself once these work as they did before */
static uint32_t update_health(void)
{
	struct hub_bus_status bus;

	bus_status(&bus);
	return (hwtr_net_connected() ? HWTR_UP_WIFI : 0) |
	       ((bus.state == CAN_STATE_ERROR_ACTIVE || bus.state == CAN_STATE_ERROR_WARNING) &&
				bus.nodes > 0
			? HWTR_UP_BUS
			: 0);
}

static void update_event(const char *text)
{
	hub_event(HUB_EV_FW, "%s", text);
}

static const struct hwtr_update_cfg update_cfg = {
	.health = update_health,
	.event = update_event,
};
#endif

int main(void)
{
	uint32_t tick = 0;
	int ret;

	LOG_INF("hw-testing-rack power hub");

	hwtr_admin_init(&admin_cfg);

	ret = settings_subsys_init();
	if (ret == 0) {
		ret = settings_load();
	}
	if (ret != 0) {
		LOG_ERR("settings unavailable (%d): defaults only%s", ret,
			ret == -EDEADLK ? "; storage partition not NVS: west flash --erase" : "");
	}

#if defined(CONFIG_HWTR_UPDATE)
	/* A test boot after an update: on trial (and the watchdog on) from here
	 * until Wi-Fi and the rack bus work again
	 */
	(void)hwtr_update_init(&update_cfg);
#endif

	/* First: the rows keep what they were doing across a controller reset */
	ret = rows_init(stored_rows, stored_shed[0] ? stored_shed : NULL);
	if (ret != 0) {
		LOG_ERR("rows init failed: %d", ret);
	}

	ret = bus_init();
	if (ret != 0) {
		LOG_ERR("rack bus init failed: %d", ret);
	} else if (rows_on_mask() != 0) {
		bus_enumerate(0);
	}

	ret = pd_init(stored_epr);
	if (ret != 0) {
		LOG_ERR("PD init failed: %d", ret);
	}

	ret = hwtr_net_init("rack", stored_id, NULL);
	if (ret != 0) {
		LOG_ERR("network init failed: %d", ret);
	}

	ret = web_init();
	if (ret != 0) {
		LOG_ERR("web server init failed: %d", ret);
	}

	while (true) {
		if (led_is_ready_dt(&ctl)) {
			(void)(led_level(tick) ? led_on_dt(&ctl) : led_off_dt(&ctl));
		}
		tick++;
		k_sleep(K_MSEC(125));
	}

	return 0;
}
