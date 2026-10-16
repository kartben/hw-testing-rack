/*
 * USB data path: PC_DET / SERVICE sensing and MUX_FORCE_PC.
 *
 * The muxes switch in hardware (MUX_SEL = PC_DET OR MUX_FORCE_PC, SVC
 * disables the DUT mux): the firmware only forces classic mode and, in
 * SERVICE mode, frees the ESP32-S3 USB PHY for the USB-Serial-JTAG.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/kernel.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/logging/log.h>

#include "bay.h"

LOG_MODULE_REGISTER(usb_mux, CONFIG_BAY_LOG_LEVEL);

#define MUX_NODE DT_NODELABEL(usb_mux)

static const struct gpio_dt_spec force_pc_gpio = GPIO_DT_SPEC_GET(MUX_NODE, force_pc_gpios);
static const struct gpio_dt_spec pc_det_gpio = GPIO_DT_SPEC_GET(MUX_NODE, pc_detect_gpios);
static const struct gpio_dt_spec svc_gpio = GPIO_DT_SPEC_GET(MUX_NODE, service_gpios);

static bool force_pc;
static bool service_on;
static struct gpio_callback svc_cb;

static void svc_work_handler(struct k_work *work)
{
	bool now = gpio_pin_get_dt(&svc_gpio) > 0;
	int ret = 0;

	ARG_UNUSED(work);

	if (now == service_on) {
		return;
	}
	service_on = now;

	LOG_INF("SERVICE switch %s", now ? "on: front port -> node" : "off");

	if (!IS_ENABLED(CONFIG_BAY_SERVICE_PHY_HANDOVER)) {
		return;
	}

	ret = now ? usb_host_release_phy() : usb_host_claim_phy();
	if (ret != 0) {
		LOG_ERR("USB PHY handover failed: %d", ret);
	}
}

static K_WORK_DELAYABLE_DEFINE(svc_work, svc_work_handler);

static void svc_isr(const struct device *port, struct gpio_callback *cb, gpio_port_pins_t pins)
{
	ARG_UNUSED(port);
	ARG_UNUSED(cb);
	ARG_UNUSED(pins);

	/* Debounce the slide switch */
	k_work_reschedule(&svc_work, K_MSEC(50));
}

int usb_mux_init(bool force)
{
	int ret;

	if (!gpio_is_ready_dt(&force_pc_gpio) || !gpio_is_ready_dt(&pc_det_gpio) ||
	    !gpio_is_ready_dt(&svc_gpio)) {
		return -ENODEV;
	}

	force_pc = force;
	ret = gpio_pin_configure_dt(&force_pc_gpio,
				    force ? GPIO_OUTPUT_ACTIVE : GPIO_OUTPUT_INACTIVE);
	if (ret != 0) {
		return ret;
	}

	ret = gpio_pin_configure_dt(&pc_det_gpio, GPIO_INPUT);
	if (ret != 0) {
		return ret;
	}

	ret = gpio_pin_configure_dt(&svc_gpio, GPIO_INPUT);
	if (ret != 0) {
		return ret;
	}
	gpio_init_callback(&svc_cb, svc_isr, BIT(svc_gpio.pin));
	ret = gpio_add_callback_dt(&svc_gpio, &svc_cb);
	if (ret != 0) {
		return ret;
	}
	ret = gpio_pin_interrupt_configure_dt(&svc_gpio, GPIO_INT_EDGE_BOTH);
	if (ret != 0) {
		return ret;
	}

	/* The USB/IP service started the host before main(): release it now if
	 * the node booted with SERVICE on.
	 */
	k_work_reschedule(&svc_work, K_NO_WAIT);

	LOG_INF("data path: %s%s", bay_data_path_str(usb_mux_path()),
		force ? " (forced)" : "");

	return 0;
}

bool usb_mux_service(void)
{
	return gpio_pin_get_dt(&svc_gpio) > 0;
}

bool usb_mux_pc_detected(void)
{
	return gpio_pin_get_dt(&pc_det_gpio) > 0;
}

bool usb_mux_force_pc_get(void)
{
	return force_pc;
}

int usb_mux_force_pc_set(bool force)
{
	int ret = gpio_pin_set_dt(&force_pc_gpio, force);

	if (ret != 0) {
		return ret;
	}
	force_pc = force;
	LOG_INF("classic mode %s", force ? "forced" : "released (USB/IP unless a PC is plugged)");

	return bay_settings_save_force_pc(force);
}

enum bay_data_path usb_mux_path(void)
{
	if (usb_mux_service()) {
		return BAY_PATH_SERVICE;
	}
	if (force_pc || usb_mux_pc_detected()) {
		return BAY_PATH_CLASSIC;
	}

	return BAY_PATH_USBIP;
}

const char *bay_data_path_str(enum bay_data_path path)
{
	switch (path) {
	case BAY_PATH_USBIP:
		return "usbip";
	case BAY_PATH_CLASSIC:
		return "classic";
	case BAY_PATH_SERVICE:
		return "service";
	default:
		return "?";
	}
}
