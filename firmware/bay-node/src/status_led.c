/*
 * WS2812B status LED behind the fascia.
 *
 *   white/blue, fast  identify: the hub's page asked "which one is it?"
 *   white, blinking   access claim pending: press BOOT to confirm
 *   red, blinking     DUT VBUS fault (current limit), or switched off by it
 *   yellow            SERVICE: front port -> node (flash / debug the node)
 *   magenta           classic: DUT -> front port (laptop plugged, or forced)
 *   dim white         DUT power switched off
 *   orange, blinking  USB/IP mode but no network
 *   dim blue          USB/IP ready, nothing enumerated on the DUT port
 *   blue              USB/IP, DUT enumerated and exportable
 *   green             USB/IP, a client is attached
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/led_strip.h>
#include <zephyr/logging/log.h>

#include "bay.h"

LOG_MODULE_REGISTER(status_led, CONFIG_BAY_LOG_LEVEL);

static const struct device *const strip = DEVICE_DT_GET(DT_ALIAS(led_strip));

#define RGB(_r, _g, _b) ((struct led_rgb){.r = (_r), .g = (_g), .b = (_b)})

static const struct led_rgb off = RGB(0, 0, 0);
static const struct led_rgb red = RGB(255, 0, 0);
static const struct led_rgb yellow = RGB(255, 160, 0);
static const struct led_rgb magenta = RGB(200, 0, 255);
static const struct led_rgb dim_white = RGB(60, 60, 60);
static const struct led_rgb orange = RGB(255, 60, 0);
static const struct led_rgb dim_blue = RGB(0, 0, 60);
static const struct led_rgb blue = RGB(0, 40, 255);
static const struct led_rgb green = RGB(0, 255, 40);
static const struct led_rgb white = RGB(255, 255, 255);

static struct led_rgb shown;
static uint32_t tick;
static bool ready;

static struct led_rgb scale(struct led_rgb c)
{
	return RGB(c.r * CONFIG_BAY_LED_BRIGHTNESS / 255, c.g * CONFIG_BAY_LED_BRIGHTNESS / 255,
		   c.b * CONFIG_BAY_LED_BRIGHTNESS / 255);
}

static struct led_rgb pick(void)
{
	/* status_led_update() runs every 250 ms */
	bool blink_fast = (tick & 1U) != 0U;
	bool blink_slow = (tick & 4U) != 0U;

	/* "Which one is it?" from the hub's page */
	if (bay_rack_identifying()) {
		return blink_fast ? white : blue;
	}
	/* Which node wants the BOOT press */
	if (access_claim_pending()) {
		return blink_fast ? white : off;
	}
	if (dut_fault_latched() || dut_fault_active()) {
		return blink_fast ? red : off;
	}

	switch (usb_mux_path()) {
	case BAY_PATH_SERVICE:
		return yellow;
	case BAY_PATH_CLASSIC:
		return magenta;
	default:
		break;
	}

	if (!dut_power_get()) {
		return dim_white;
	}
	if (!bay_net_connected()) {
		return blink_slow ? orange : off;
	}
	if (usb_host_usbip_sessions() > 0) {
		return green;
	}
	if (usb_host_device_count() > 0) {
		return blue;
	}

	return dim_blue;
}

int status_led_init(void)
{
	if (!device_is_ready(strip)) {
		LOG_WRN("status LED not ready");
		return -ENODEV;
	}
	ready = true;

	return 0;
}

void status_led_update(void)
{
	struct led_rgb c;

	if (!ready) {
		return;
	}

	tick++;
	c = scale(pick());
	if (memcmp(&c, &shown, sizeof(c)) == 0) {
		return;
	}

	if (led_strip_update_rgb(strip, &c, 1) == 0) {
		shown = c;
	}
}
