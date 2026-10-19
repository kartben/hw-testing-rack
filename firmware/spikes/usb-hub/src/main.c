/*
 * USB hub spike: several DUTs behind one hub, exported over USB/IP by an
 * ESP32-S3 (README.md).  The host stack, its hub class and the USB/IP
 * service are Zephyr's, the last with the rack's patches (zephyr/patches.yml:
 * bus IDs by port, device removal); this adds a look at what they see and
 * the hub's per-port power, on the shell:
 *
 *   spike devs                     devices: address, busid, hub port, speed, VID:PID
 *   spike port <n> on|off|cycle [ms]   ClearPortFeature/SetPortFeature(PORT_POWER)
 *   spike port <n>                 the port's wPortStatus
 *   spike hub                      the hub: ports, power switching, over-current
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/drivers/usb/uhc.h>
#include <zephyr/logging/log.h>
#include <zephyr/settings/settings.h>
#include <zephyr/shell/shell.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/usb/class/usb_hub.h>
#include <zephyr/usb/usbh.h>

#include <hwtr/net.h>

/* The host stack's own hub requests (subsys/usb/host, not public API yet) */
#include "usbh_ch11.h"

LOG_MODULE_REGISTER(spike, LOG_LEVEL_INF);

/* The USB/IP service's host context (subsys/usb/host/usbip.c): the only one */
static struct usbh_context *host(void)
{
	STRUCT_SECTION_FOREACH(usbh_context, ctx) {
		return ctx;
	}
	return NULL;
}

#define HUB_CLASS 0x09

static const char *speed_str(enum usb_device_speed speed)
{
	switch (speed) {
	case USB_SPEED_SPEED_LS:
		return "low";
	case USB_SPEED_SPEED_FS:
		return "full";
	case USB_SPEED_SPEED_HS:
		return "high";
	default:
		return "?";
	}
}

/* The first hub on the bus (the spike's) */
static struct usb_device *find_hub(void)
{
	struct usb_device *udev;

	SYS_DLIST_FOR_EACH_CONTAINER(&host()->udevs, udev, node) {
		if (udev->dev_desc.bDeviceClass == HUB_CLASS) {
			return udev;
		}
	}
	return NULL;
}

/* The USB/IP bus ID, as the patched usbip.c names it: by the port */
static void busid(const struct usb_device *udev, char *buf, size_t len)
{
	uint8_t ports[5];
	size_t n = 0;
	int pos;

	for (; udev->hub != NULL && n < ARRAY_SIZE(ports); udev = udev->hub) {
		ports[n++] = udev->hub_port;
	}
	pos = snprintf(buf, len, "1-1");
	while (n > 0 && pos > 0 && (size_t)pos < len) {
		pos += snprintf(buf + pos, len - pos, ".%u", ports[--n]);
	}
}

static int cmd_devs(const struct shell *sh, size_t argc, char **argv)
{
	struct usb_device *udev;
	char id[24];
	int n = 0;

	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	k_mutex_lock(&host()->mutex, K_FOREVER);
	SYS_DLIST_FOR_EACH_CONTAINER(&host()->udevs, udev, node) {
		busid(udev, id, sizeof(id));
		shell_print(sh, "addr %3u  busid %-8s  %s port %u, level %u  %-4s  %04x:%04x  class %02x%s",
			    udev->addr, udev->dev_desc.bDeviceClass == HUB_CLASS ? "-" : id,
			    udev->hub ? "hub" : "root",
			    udev->hub ? udev->hub_port : 0, udev->level, speed_str(udev->speed),
			    udev->dev_desc.idVendor, udev->dev_desc.idProduct,
			    udev->dev_desc.bDeviceClass,
			    udev->dev_desc.bDeviceClass == HUB_CLASS ? " (the hub)" : "");
		n++;
	}
	k_mutex_unlock(&host()->mutex);
	shell_print(sh, "%d device(s)", n);
	return 0;
}

static int cmd_hub(const struct shell *sh, size_t argc, char **argv)
{
	struct usb_device *hub = find_hub();
	uint8_t buf[16] __aligned(4);
	const struct usb_hub_descriptor *desc = (const void *)buf;
	uint16_t chars;
	int ret;

	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	if (hub == NULL) {
		shell_error(sh, "no hub");
		return -ENODEV;
	}
	ret = usbh_req_desc_hub(hub, buf, sizeof(struct usb_hub_descriptor));
	if (ret != 0) {
		shell_error(sh, "hub descriptor: %d", ret);
		return ret;
	}
	chars = sys_le16_to_cpu(desc->wHubCharacteristics);
	/* wHubCharacteristics bits 1:0 power switching, 4:3 over-current (USB 2.0, 11.23.2.1) */
	shell_print(sh, "hub %04x:%04x at address %u, %u ports, power switching %s, "
		    "over-current %s, power-on to good %u ms",
		    hub->dev_desc.idVendor, hub->dev_desc.idProduct, hub->addr, desc->bNbrPorts,
		    (chars & 0x3) == 0 ? "ganged" : (chars & 0x3) == 1 ? "PER PORT" : "none",
		    ((chars >> 3) & 0x3) == 0 ? "global" : ((chars >> 3) & 0x3) == 1 ? "per port"
										   : "none",
		    desc->bPwrOn2PwrGood * 2);
	return 0;
}

static int port_status(const struct shell *sh, struct usb_device *hub, uint8_t port)
{
	uint16_t status = 0;
	uint16_t change = 0;
	int ret = usbh_req_get_port_status(hub, port, &status, &change);

	if (ret != 0) {
		shell_error(sh, "port %u status: %d", port, ret);
		return ret;
	}
	shell_print(sh, "port %u: status 0x%04x (%s%s%s%s), change 0x%04x", port, status,
		    status & USB_HUB_PORT_STATUS_POWER ? "power" : "no power",
		    status & USB_HUB_PORT_STATUS_CONNECTION ? ", connected" : "",
		    status & USB_HUB_PORT_STATUS_ENABLE ? ", enabled" : "",
		    status & USB_HUB_PORT_STATUS_OVER_CURRENT ? ", OVER-CURRENT" : "", change);
	return 0;
}

static int cmd_port(const struct shell *sh, size_t argc, char **argv)
{
	struct usb_device *hub = find_hub();
	uint8_t port = strtoul(argv[1], NULL, 10);
	int ret = 0;

	if (hub == NULL) {
		shell_error(sh, "no hub");
		return -ENODEV;
	}
	if (port == 0) {
		shell_error(sh, "ports count from 1");
		return -EINVAL;
	}
	if (argc == 2) {
		return port_status(sh, hub, port);
	}

	if (strcmp(argv[2], "off") == 0 || strcmp(argv[2], "cycle") == 0) {
		ret = usbh_req_clear_hcfs_port_power(hub, port);
		shell_print(sh, "port %u power off: %d", port, ret);
	}
	if (ret == 0 && strcmp(argv[2], "cycle") == 0) {
		k_msleep(argc > 3 ? strtoul(argv[3], NULL, 10) : 1000);
	}
	if (ret == 0 && (strcmp(argv[2], "on") == 0 || strcmp(argv[2], "cycle") == 0)) {
		ret = usbh_req_set_hcfs_port_power(hub, port);
		shell_print(sh, "port %u power on: %d", port, ret);
	}
	if (ret == 0) {
		k_msleep(100);
		(void)port_status(sh, hub, port);
	}
	return ret;
}

SHELL_STATIC_SUBCMD_SET_CREATE(sub_spike,
	SHELL_CMD_ARG(devs, NULL, "Devices on the bus: address, USB/IP busid, hub port",
		      cmd_devs, 1, 0),
	SHELL_CMD_ARG(hub, NULL, "The hub: ports, power switching, over-current", cmd_hub, 1, 0),
	SHELL_CMD_ARG(port, NULL, "<n> [on|off|cycle [ms]]: a hub port's status or power",
		      cmd_port, 2, 2),
	SHELL_SUBCMD_SET_END
);

SHELL_CMD_REGISTER(spike, &sub_spike, "USB hub spike", NULL);

static void on_addr(const char *addr)
{
	LOG_INF("network up: usbip list -r %s", addr);
}

int main(void)
{
	int ret;

	LOG_INF("USB hub spike: %d USB/IP sessions, %d USB devices", CONFIG_USBIP_DEVICES_COUNT,
		CONFIG_USBH_USB_DEVICE_MAX);

	ret = settings_subsys_init();
	if (ret == 0) {
		ret = settings_load();
	}
	if (ret != 0) {
		LOG_WRN("settings: %d (Wi-Fi credentials from the build only)", ret);
	}

	ret = hwtr_net_init("usbspike", "", on_addr);
	if (ret != 0) {
		LOG_ERR("network: %d", ret);
	}
	return 0;
}
