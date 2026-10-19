/*
 * USB/IP on native_sim: the service (CONFIG_USBIP, with zephyr/patches.yml)
 * starts by itself on the virtual host controller; this puts a loopback
 * device on the virtual bus and unplugs or plugs it from the shell:
 *
 *   dut off    the device goes (as a board that resets or is unplugged)
 *   dut on     it comes back and enumerates again
 *
 * The client is test_usbip.py.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/shell/shell.h>
#include <zephyr/sys/printk.h>
#include <zephyr/usb/usbd.h>

#include <sample_usbd.h>

static struct usbd_context *dut;

static int cmd_dut(const struct shell *sh, size_t argc, char **argv)
{
	int ret;

	ARG_UNUSED(argc);

	if (strcmp(argv[1], "on") == 0) {
		ret = usbd_enable(dut);
	} else if (strcmp(argv[1], "off") == 0) {
		ret = usbd_disable(dut);
	} else {
		shell_error(sh, "usage: dut on|off");
		return -EINVAL;
	}

	shell_print(sh, "SIM: dut %s: %d", argv[1], ret);

	return ret;
}

SHELL_CMD_ARG_REGISTER(dut, NULL, "on|off: plug or unplug the device", cmd_dut, 2, 0);

int main(void)
{
	int ret;

	dut = sample_usbd_init_device(NULL);
	if (dut == NULL) {
		printk("SIM: no device\n");
		return 0;
	}

	ret = usbd_enable(dut);
	printk("SIM: ready (%d)\n", ret);

	return 0;
}
