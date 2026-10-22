/*
 * USB/IP on native_sim: the service (CONFIG_USBIP, with zephyr/patches.yml)
 * starts by itself on the virtual host controller; this puts a device on the
 * virtual bus, a loopback function and a serial converter (serial_emu.c), and
 * drives them from the shell:
 *
 *   dut off    the device goes (as a board that resets or is unplugged)
 *   dut on     it comes back and enumerates again
 *   ra <mode>  how the service reads ahead from now on: none, stream, ftdi
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
#include <zephyr/usb/usbip.h>

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

static enum usbip_read_ahead ra_mode;

static enum usbip_read_ahead read_ahead(const struct usb_device_descriptor *desc)
{
	ARG_UNUSED(desc);

	return ra_mode;
}

static int cmd_ra(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc);

	if (strcmp(argv[1], "none") == 0) {
		ra_mode = USBIP_READ_AHEAD_NONE;
	} else if (strcmp(argv[1], "stream") == 0) {
		ra_mode = USBIP_READ_AHEAD_STREAM;
	} else if (strcmp(argv[1], "ftdi") == 0) {
		ra_mode = USBIP_READ_AHEAD_FTDI;
	} else {
		shell_error(sh, "usage: ra none|stream|ftdi");
		return -EINVAL;
	}

	shell_print(sh, "SIM: ra %s: 0", argv[1]);

	return 0;
}

SHELL_CMD_ARG_REGISTER(ra, NULL, "none|stream|ftdi: read-ahead of the next session", cmd_ra,
		       2, 0);

int main(void)
{
	int ret;

	usbip_set_read_ahead_cb(read_ahead);

	dut = sample_usbd_init_device(NULL);
	if (dut == NULL) {
		printk("SIM: no device\n");
		return 0;
	}

	ret = usbd_enable(dut);
	printk("SIM: ready (%d)\n", ret);

	return 0;
}
