/*
 * USB host state for the status LED and the shell, and the SERVICE-mode PHY
 * handover.
 *
 * The USB/IP service (subsys/usb/host/usbip.c) owns the host: it defines the
 * usbh context on zephyr_uhc0, starts it at boot and serves port 3240.  We
 * only look at that context and stop/start it around SERVICE mode.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/kernel.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/usb/uhc.h>
#include <zephyr/usb/usbh.h>
#include <zephyr/net/net_context.h>
#include <zephyr/net/net_ip.h>
#include <zephyr/logging/log.h>

#if defined(CONFIG_BAY_SERVICE_PHY_HANDOVER)
#include <hal/usb_serial_jtag_ll.h>
#endif

#include "bay.h"

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
