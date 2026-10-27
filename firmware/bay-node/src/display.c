/*
 * The front display (the front-display snippet): a Waveshare 1.9" touch LCD,
 * an ST7789V2 at 320 x 170 and a CST816 touch controller, with the bay's
 * status in LVGL, refreshed once a second from LVGL's own work queue.
 * "display" in the shell prints how long the refreshes take.  The 3D viewer
 * draws the same screen: keep tools/lvgl_wasm/status.c in step.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdio.h>
#include <string.h>

#include <zephyr/device.h>
#include <zephyr/drivers/display.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/hostname.h>
#include <zephyr/shell/shell.h>

#include <lvgl.h>
#include <lvgl_zephyr.h>

#include <hwtr/net.h>

#include "bay.h"

LOG_MODULE_REGISTER(display, CONFIG_BAY_LOG_LEVEL);

#define REFRESH_MS 1000
#define NPORTS     4

static lv_obj_t *id_label;
static lv_obj_t *addr_label;
static lv_obj_t *dut_label;
static lv_obj_t *fault_label;
static lv_obj_t *port_label[NPORTS];
static lv_obj_t *usb_label;

static struct {
	uint32_t refreshes;
	uint32_t last_us;
	uint32_t max_us;
	uint32_t total_us;
	uint32_t full_us;
} stats;

static lv_obj_t *label_add(const lv_font_t *font, lv_align_t align, int32_t x, int32_t y)
{
	lv_obj_t *label = lv_label_create(lv_screen_active());

	lv_obj_set_style_text_font(label, font, 0);
	lv_obj_align(label, align, x, y);
	lv_label_set_text(label, "");

	return label;
}

/* Setting a label's text or style redraws it, even to the same value */
static void label_set(lv_obj_t *label, const char *text, lv_color_t color)
{
	if (strcmp(lv_label_get_text(label), text) != 0) {
		lv_label_set_text(label, text);
	}
	if (!lv_color_eq(lv_obj_get_style_text_color(label, LV_PART_MAIN), color)) {
		lv_obj_set_style_text_color(label, color, 0);
	}
}

static uint32_t refresh_now(void)
{
	uint32_t start = k_cycle_get_32();

	lv_refr_now(NULL);

	return k_cyc_to_us_floor32(k_cycle_get_32() - start);
}

static void refresh(lv_timer_t *timer)
{
	const char *pos = bay_rack_position();
	struct dut_power_reading r;
	struct port_info pi;
	char text[40];
	uint32_t us;

	ARG_UNUSED(timer);

	if (pos[0] == '\0') {
		pos = bay_id()[0] != '\0' ? bay_id() : net_hostname_get();
	}
	label_set(id_label, pos, lv_color_white());
	label_set(addr_label, hwtr_net_connected() ? hwtr_net_addr() : "no Wi-Fi",
		  hwtr_net_connected() ? lv_color_white() : lv_palette_main(LV_PALETTE_ORANGE));

	if (dut_power_get() && dut_power_read(&r) == 0) {
		snprintf(text, sizeof(text), "%d.%02d V  %d mA", r.bus_mv / 1000,
			 (r.bus_mv % 1000) / 10, r.current_ma);
		label_set(dut_label, text, lv_palette_main(LV_PALETTE_GREEN));
	} else {
		label_set(dut_label, "DUT off", lv_palette_main(LV_PALETTE_GREY));
	}
	label_set(fault_label, dut_fault_active() ? "FAULT" : "",
		  lv_palette_main(LV_PALETTE_RED));

	for (int i = 0; i < NPORTS; i++) {
		if (ports_info(i + 1, &pi) != 0) {
			snprintf(text, sizeof(text), "%d  -", i + 1);
			label_set(port_label[i], text, lv_palette_main(LV_PALETTE_GREY));
		} else if (pi.latched) {
			snprintf(text, sizeof(text), "%d  fault", i + 1);
			label_set(port_label[i], text, lv_palette_main(LV_PALETTE_RED));
		} else if (pi.on) {
			snprintf(text, sizeof(text), "%d  %d mA", i + 1, pi.meter ? pi.ma : 0);
			label_set(port_label[i], text, lv_palette_main(LV_PALETTE_GREEN));
		} else {
			snprintf(text, sizeof(text), "%d  off", i + 1);
			label_set(port_label[i], text, lv_palette_main(LV_PALETTE_GREY));
		}
	}

	snprintf(text, sizeof(text), "USB/IP %d   %s", usb_host_usbip_sessions(),
		 bay_data_path_str(usb_mux_path()));
	label_set(usb_label, text, lv_color_white());

	us = refresh_now();
	stats.refreshes++;
	stats.last_us = us;
	stats.max_us = MAX(stats.max_us, us);
	stats.total_us += us;
}

int display_init(void)
{
	const struct device *dev = DEVICE_DT_GET(DT_CHOSEN(zephyr_display));
	lv_obj_t *screen;

	if (!device_is_ready(dev)) {
		return -ENODEV;
	}

	lvgl_lock();
	screen = lv_screen_active();
	lv_obj_set_style_bg_color(screen, lv_color_black(), 0);
	lv_obj_set_style_text_color(screen, lv_color_white(), 0);

	id_label = label_add(&lv_font_montserrat_28, LV_ALIGN_TOP_LEFT, 10, 8);
	addr_label = label_add(&lv_font_montserrat_14, LV_ALIGN_TOP_RIGHT, -10, 16);
	dut_label = label_add(&lv_font_montserrat_28, LV_ALIGN_LEFT_MID, 10, -6);
	fault_label = label_add(&lv_font_montserrat_14, LV_ALIGN_RIGHT_MID, -10, -6);
	for (int i = 0; i < NPORTS; i++) {
		port_label[i] = label_add(&lv_font_montserrat_14, LV_ALIGN_BOTTOM_LEFT,
					  10 + i * 77, -34);
	}
	usb_label = label_add(&lv_font_montserrat_14, LV_ALIGN_BOTTOM_LEFT, 10, -10);

	refresh(NULL);
	lv_obj_invalidate(screen);
	stats.full_us = refresh_now();
	lv_timer_create(refresh, REFRESH_MS, NULL);
	lvgl_unlock();

	display_blanking_off(dev);
	LOG_INF("first frame in %u us", stats.full_us);

	return 0;
}

static int cmd_display(const struct shell *sh, size_t argc, char **argv)
{
	uint32_t one_us;

	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	lvgl_lock();
	/* The DUT's power, the largest value that changes, redrawn alone */
	lv_obj_invalidate(dut_label);
	one_us = refresh_now();
	shell_print(sh, "full frame %u us; one value %u us; status refreshes %u, last %u us, "
		    "max %u us, mean %u us", stats.full_us, one_us, stats.refreshes, stats.last_us,
		    stats.max_us, stats.refreshes != 0 ? stats.total_us / stats.refreshes : 0);
	lvgl_unlock();

	return 0;
}

SHELL_CMD_REGISTER(display, NULL, "Front display: how long its refreshes take", cmd_display);
