/*
 * DATA ×4 v2 co-processor spike (README.md): what Zephyr gives an RP2350
 * today for the co-processor's jobs, built for a Pico 2, not yet run.
 *
 *   USB      4 CDC-ACM (shell, con1 bridged to UART1, con2, con3) and the
 *            node's vendor bulk link (link.c)
 *   I2C      two emulated devices, devicetree only (app.overlay)
 *   capture  8 channels by PIO + DMA (la_pio.c), on the shell:
 *
 *   la cap <rate_hz> <samples> [<trigger pin> rise|fall [timeout_ms]]
 *   la dump [offset] [count]
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdlib.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/shell/shell.h>
#include <zephyr/usb/usbd.h>

#include "la_pio.h"

LOG_MODULE_REGISTER(coproc, LOG_LEVEL_INF);

/* The first bus pin: CH1 = GPIO2 */
#define LA_FIRST_PIN 2

/* Zephyr's test VID/PID: a spike only */
USBD_DEVICE_DEFINE(coproc_usbd, DEVICE_DT_GET(DT_NODELABEL(zephyr_udc0)), 0x2fe3, 0x0005);
USBD_DESC_LANG_DEFINE(coproc_lang);
USBD_DESC_MANUFACTURER_DEFINE(coproc_mfr, "hw-testing-rack");
USBD_DESC_PRODUCT_DEFINE(coproc_product, "DATA x4 co-processor spike");
USBD_DESC_CONFIG_DEFINE(coproc_fs_cfg_desc, "FS Configuration");
USBD_CONFIGURATION_DEFINE(coproc_fs_config, 0, 100, &coproc_fs_cfg_desc);

static int coproc_usb_init(void)
{
	int err;

	err = usbd_add_descriptor(&coproc_usbd, &coproc_lang);
	err = err ?: usbd_add_descriptor(&coproc_usbd, &coproc_mfr);
	err = err ?: usbd_add_descriptor(&coproc_usbd, &coproc_product);
	err = err ?: usbd_add_configuration(&coproc_usbd, USBD_SPEED_FS, &coproc_fs_config);
	err = err ?: usbd_register_all_classes(&coproc_usbd, USBD_SPEED_FS, 1, NULL);
	if (err) {
		return err;
	}

	/* CDC-ACM uses interface association descriptors */
	usbd_device_set_code_triple(&coproc_usbd, USBD_SPEED_FS, USB_BCC_MISCELLANEOUS, 0x02, 0x01);

	err = usbd_init(&coproc_usbd);

	return err ?: usbd_enable(&coproc_usbd);
}

static int cmd_la_cap(const struct shell *sh, size_t argc, char **argv)
{
	struct la_params p = {
		.first_pin = LA_FIRST_PIN,
		.rate_hz = strtoul(argv[1], NULL, 0),
		.samples = strtoul(argv[2], NULL, 0),
		.trigger_pin = -1,
	};
	uint32_t trigger_ms = 5000;
	uint32_t rate;
	int64_t t0;
	int ret;

	if (argc >= 4) {
		p.trigger_pin = strtol(argv[3], NULL, 0);
		p.rising = argc < 5 || strcmp(argv[4], "fall") != 0;
	}
	if (argc >= 6) {
		trigger_ms = strtoul(argv[5], NULL, 0);
	}
	p.timeout = K_MSEC(trigger_ms + (uint64_t)p.samples * 1000U / MAX(p.rate_hz, 1U) + 10U);

	t0 = k_uptime_get();
	ret = la_capture(&p, &rate);
	if (ret < 0) {
		shell_error(sh, "capture failed: %d", ret);
		return ret;
	}
	shell_print(sh, "%u samples at %u Hz on GPIO%u-%u in %lld ms", p.samples, rate,
		    p.first_pin, p.first_pin + LA_CHANNELS - 1, k_uptime_get() - t0);

	return 0;
}

static int cmd_la_dump(const struct shell *sh, size_t argc, char **argv)
{
	const size_t offset = argc > 1 ? strtoul(argv[1], NULL, 0) : 0;
	size_t count = argc > 2 ? strtoul(argv[2], NULL, 0) : 64;

	if (offset >= sizeof(la_buf)) {
		return -EINVAL;
	}
	count = MIN(count, sizeof(la_buf) - offset);
	shell_hexdump(sh, &la_buf[offset], count);

	return 0;
}

SHELL_STATIC_SUBCMD_SET_CREATE(la_cmds,
	SHELL_CMD_ARG(cap, NULL, "<rate_hz> <samples> [<pin> rise|fall [timeout_ms]]",
		      cmd_la_cap, 3, 3),
	SHELL_CMD_ARG(dump, NULL, "[offset] [count]", cmd_la_dump, 1, 2),
	SHELL_SUBCMD_SET_END);
SHELL_CMD_REGISTER(la, &la_cmds, "PIO capture of CH1-8", NULL);

int main(void)
{
	int err = coproc_usb_init();

	if (err) {
		LOG_ERR("USB init failed: %d", err);
		return err;
	}
	LOG_INF("co-processor spike up");

	return 0;
}
