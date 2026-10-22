/*
 * USB host state for the status LED and the shell, and the SERVICE-mode PHY
 * handover.
 *
 * The USB/IP service (subsys/usb/host/usbip.c) owns the host: it defines the
 * usbh context on zephyr_uhc0, starts it at boot and serves port 3240.  We
 * only look at that context, stop/start it around SERVICE mode, and tell the
 * service which devices it reads ahead.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/kernel.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/usb/uhc.h>
#include <zephyr/usb/usbh.h>
#include <zephyr/usb/usbip.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/net/net_context.h>
#include <zephyr/net/net_ip.h>
#include <zephyr/logging/log.h>

#if defined(CONFIG_BAY_SERVICE_PHY_HANDOVER)
#include <hal/usb_serial_jtag_ll.h>
#endif

#include "bay.h"

#if defined(CONFIG_USBIP)

LOG_MODULE_REGISTER(usb_host, CONFIG_BAY_LOG_LEVEL);

#define UHC_DEV DEVICE_DT_GET(DT_NODELABEL(zephyr_uhc0))

static bool phy_released;

static struct usbh_context *host_ctx(void)
{
	STRUCT_SECTION_FOREACH(usbh_context, ctx) {
		if (ctx->dev == UHC_DEV) {
			return ctx;
		}
	}

	return NULL;
}

bool usb_host_running(void)
{
	struct usbh_context *ctx = host_ctx();

	return ctx != NULL && uhc_is_enabled(ctx->dev);
}

int usb_host_device_count(void)
{
	struct usbh_context *ctx = host_ctx();
	sys_dnode_t *node;
	int n = 0;

	/* The device list is only set up once the host is initialized */
	if (ctx == NULL || !uhc_is_initialized(ctx->dev)) {
		return 0;
	}

	if (k_mutex_lock(&ctx->mutex, K_MSEC(20)) != 0) {
		return -EBUSY;
	}
	SYS_DLIST_FOR_EACH_NODE(&ctx->udevs, node) {
		n++;
	}
	k_mutex_unlock(&ctx->mutex);

	return n;
}

int usb_host_port_device(uint8_t hub_port, uint16_t *vid, uint16_t *pid)
{
	struct usbh_context *ctx = host_ctx();
	struct usb_device *udev;
	int ret = -ENODEV;

	if (ctx == NULL || !uhc_is_initialized(ctx->dev)) {
		return -ENODEV;
	}
	if (k_mutex_lock(&ctx->mutex, K_MSEC(20)) != 0) {
		return -EBUSY;
	}
	/* Behind the hub on the root port: its hub is a root device */
	SYS_DLIST_FOR_EACH_CONTAINER(&ctx->udevs, udev, node) {
		if (udev->hub != NULL && udev->hub->hub == NULL && udev->hub_port == hub_port) {
			*vid = sys_le16_to_cpu(udev->dev_desc.idVendor);
			*pid = sys_le16_to_cpu(udev->dev_desc.idProduct);
			ret = 0;
			break;
		}
	}
	k_mutex_unlock(&ctx->mutex);

	return ret;
}

static void count_usbip_session(struct net_context *context, void *user_data)
{
	int *n = user_data;

	if (net_context_get_proto(context) != NET_IPPROTO_TCP ||
	    net_context_get_state(context) != NET_CONTEXT_CONNECTED) {
		return;
	}

	if (net_sin(&context->local)->sin_port == net_htons(CONFIG_USBIP_SERVICE_PORT)) {
		(*n)++;
	}
}

int usb_host_usbip_sessions(void)
{
	int n = 0;

	net_context_foreach(count_usbip_session, &n);

	return n;
}

#if defined(CONFIG_USBIP_READ_AHEAD)

/*
 * USB serial converters are read ahead: their small receive FIFO overflows
 * while the client's next read crosses the network.  An FTDI converter frames
 * each packet with two status bytes; the others send plain data.  Only these
 * chips: the same vendors make mass storage bridges and debug probes, whose
 * replies are messages that must not be merged.
 */
static const struct {
	uint16_t vid;
	uint16_t pid; /* 0: any */
	enum usbip_read_ahead mode;
} read_ahead_devices[] = {
	{0x0403, 0, USBIP_READ_AHEAD_FTDI},		/* FTDI */
	{0x10c4, 0xea60, USBIP_READ_AHEAD_STREAM},	/* CP2102, CP2104, CP2109 */
	{0x10c4, 0xea70, USBIP_READ_AHEAD_STREAM},	/* CP2105 */
	{0x10c4, 0xea71, USBIP_READ_AHEAD_STREAM},	/* CP2108 */
	{0x067b, 0x2303, USBIP_READ_AHEAD_STREAM},	/* PL2303 */
	{0x067b, 0x23a3, USBIP_READ_AHEAD_STREAM},	/* PL2303G */
	{0x067b, 0x23b3, USBIP_READ_AHEAD_STREAM},
	{0x067b, 0x23c3, USBIP_READ_AHEAD_STREAM},
	{0x067b, 0x23d3, USBIP_READ_AHEAD_STREAM},
	{0x067b, 0x23e3, USBIP_READ_AHEAD_STREAM},
	{0x067b, 0x23f3, USBIP_READ_AHEAD_STREAM},
	{0x1a86, 0x7523, USBIP_READ_AHEAD_STREAM},	/* CH340 */
	{0x1a86, 0x5523, USBIP_READ_AHEAD_STREAM},	/* CH341 */
	{0x1a86, 0x55d2, USBIP_READ_AHEAD_STREAM},	/* CH342 */
	{0x1a86, 0x55d3, USBIP_READ_AHEAD_STREAM},	/* CH343 */
	{0x1a86, 0x55d4, USBIP_READ_AHEAD_STREAM},	/* CH9102 */
};

static enum usbip_read_ahead read_ahead_policy(const struct usb_device_descriptor *desc)
{
	ARRAY_FOR_EACH_PTR(read_ahead_devices, d) {
		if (d->vid == desc->idVendor && (d->pid == 0 || d->pid == desc->idProduct)) {
			return d->mode;
		}
	}

	return USBIP_READ_AHEAD_NONE;
}

static int read_ahead_init(void)
{
	usbip_set_read_ahead_cb(read_ahead_policy);

	return 0;
}

SYS_INIT(read_ahead_init, APPLICATION, 0);

#endif /* CONFIG_USBIP_READ_AHEAD */

#if defined(CONFIG_BAY_SERVICE_PHY_HANDOVER)

int usb_host_release_phy(void)
{
	struct usbh_context *ctx = host_ctx();
	int ret;

	if (ctx == NULL) {
		return -ENODEV;
	}
	if (phy_released) {
		return 0;
	}

	(void)usbh_disable(ctx);
	/* Let the bus thread process the device removal before the shutdown */
	k_sleep(K_MSEC(100));

	if (uhc_is_initialized(ctx->dev)) {
		ret = usbh_shutdown(ctx);
		if (ret != 0) {
			return ret;
		}
	}

	/* Internal FS PHY -> USB-Serial-JTAG (the OTG controller had it) */
	usb_serial_jtag_ll_phy_enable_external(false);
	phy_released = true;

	LOG_INF("USB host stopped, PHY handed to USB-Serial-JTAG");

	return 0;
}

int usb_host_claim_phy(void)
{
	struct usbh_context *ctx = host_ctx();
	int ret;

	if (ctx == NULL) {
		return -ENODEV;
	}
	if (!phy_released) {
		return 0;
	}

	/* uhc init routes the internal PHY back to the OTG controller */
	ret = usbh_init(ctx);
	if (ret != 0 && ret != -EALREADY) {
		return ret;
	}

	ret = usbh_enable(ctx);
	if (ret != 0 && ret != -EALREADY) {
		return ret;
	}

	ret = uhc_sof_enable(ctx->dev);
	if (ret != 0) {
		return ret;
	}

	phy_released = false;
	LOG_INF("USB host running again");

	return 0;
}

#else

int usb_host_release_phy(void)
{
	return -ENOTSUP;
}

int usb_host_claim_phy(void)
{
	return -ENOTSUP;
}

#endif /* CONFIG_BAY_SERVICE_PHY_HANDOVER */

#else /* !CONFIG_USBIP */

/*
 * No USB host: a stand-in board whose only USB PHY carries its console
 * (m5stack_stamps3).  Nothing enumerates, nothing to hand over.
 */

bool usb_host_running(void)
{
	return false;
}

int usb_host_device_count(void)
{
	return 0;
}

int usb_host_usbip_sessions(void)
{
	return 0;
}

int usb_host_release_phy(void)
{
	return -ENOTSUP;
}

int usb_host_claim_phy(void)
{
	return -ENOTSUP;
}

int usb_host_port_device(uint8_t hub_port, uint16_t *vid, uint16_t *pid)
{
	ARG_UNUSED(hub_port);
	ARG_UNUSED(vid);
	ARG_UNUSED(pid);
	return -ENODEV;
}

#endif /* CONFIG_USBIP */
