/*
 * Zephyr's USB host hub class with the rack's patches (zephyr/patches.yml,
 * usbh-hub-port-reset.patch) against a made-up hub: usbh_hub.c is built as it
 * is, its class requests, the controller and the devices behind the hub are
 * fakes. A device on the hub either enumerates or keeps failing to, as an
 * MCU-Link behind a full-speed hub did on the bench, where the unpatched class
 * reset the port in a loop.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/kernel.h>
#include <zephyr/ztest.h>
#include <zephyr/net_buf.h>
#include <zephyr/usb/usbh.h>
#include <zephyr/usb/class/usb_hub.h>

/* The hub class settings of the bay node (subsys/usb/host/class/Kconfig.hub) */
#define CONFIG_USBH_HUB_LOG_LEVEL		3
#define CONFIG_USBH_HUB_MAX_LEVELS		5
#define CONFIG_USBH_HUB_PORT_RESET_TIMES	3
#define CONFIG_USBH_HUB_PORT_RESET_DELAY_MS	20
#define CONFIG_USBH_HUB_STACK_SIZE		2048
#define CONFIG_USBH_HUB_ENUM_RETRY_DELAY_MS	500
#define CONFIG_USBH_HUB_ERROR_RECOVERY_DELAY_MS	1000
#define CONFIG_USBH_HUB_INIT_PRIO		89
/* No class instance in the iterable section, the test drives its own */
#define CONFIG_USBH_HUB_INSTANCES_COUNT		0

#include "usbh_hub.c"

#define HUB_PORTS	4
#define DUT_PORT	2

/* What the device on a port does when the hub resets the port */
struct fake_device {
	/* How long the hub drives the reset */
	uint32_t reset_ms;
	/* The port is enabled at the end of the reset */
	bool enabled;
	/* The hub disables the port again after the reset (C_PORT_ENABLE) */
	bool disabled_change;
	/* The device leaves and comes back during the reset (C_PORT_CONNECTION) */
	bool reattaches;
	/* Its enumeration succeeds */
	bool enumerates;
};

static struct fake_port {
	struct fake_device dev;
	bool connected;
	bool enabled;
	bool resetting;
	int64_t reset_end;
	uint16_t change;
	/* Last time the connection changed */
	int64_t connection_at;
	unsigned int resets;
	int64_t first_reset_at;
	/* Shortest time between a connection change and the next reset */
	int64_t min_settle_ms;
	unsigned int enumerations;
} ports[HUB_PORTS + 1];

static struct k_spinlock lock;
static struct uhc_transfer *int_xfer;
static struct k_work int_work;

static struct usbh_context fake_ctx;
static struct usb_device hub_udev = {
	.ctx = &fake_ctx,
	.addr = 1,
	.level = 1,
	.speed = USB_SPEED_SPEED_FS,
};

static struct usbh_hub_data hub;
static struct usbh_class_data c_data = {
	.name = "hub",
	.priv = &hub,
};

/* End the reset the port may be in */
static void port_update(struct fake_port *const p)
{
	if (!p->resetting || k_uptime_get() < p->reset_end) {
		return;
	}

	p->resetting = false;
	p->change |= USB_HUB_PORT_CHANGE_RESET;
	p->enabled = p->connected && p->dev.enabled;

	if (p->dev.disabled_change) {
		p->change |= USB_HUB_PORT_CHANGE_ENABLE;
	}

	if (p->dev.reattaches) {
		p->change |= USB_HUB_PORT_CHANGE_CONNECTION;
		p->connection_at = p->reset_end;
	}
}

/* The hub's status change endpoint answers when a port has a change */
static void int_work_handler(struct k_work *work)
{
	struct uhc_transfer *xfer = NULL;
	uint8_t bitmap = 0;

	K_SPINLOCK(&lock) {
		for (int i = 1; i <= HUB_PORTS; i++) {
			port_update(&ports[i]);
			if (ports[i].change != 0) {
				bitmap |= BIT(i);
			}
		}

		if (int_xfer != NULL && bitmap != 0) {
			xfer = int_xfer;
			int_xfer = NULL;
		}
	}

	if (xfer != NULL) {
		net_buf_add_u8(xfer->buf, bitmap);
		xfer->err = 0;
		((usbh_udev_cb_t)xfer->cb)(xfer->udev, xfer);
	}
}

static void plug(const int port, const bool connected)
{
	K_SPINLOCK(&lock) {
		ports[port].connected = connected;
		ports[port].enabled = false;
		ports[port].change |= USB_HUB_PORT_CHANGE_CONNECTION;
		ports[port].connection_at = k_uptime_get();
	}

	k_work_submit(&int_work);
}

static void plug_device(const struct fake_device *const dev)
{
	K_SPINLOCK(&lock) {
		ports[DUT_PORT].dev = *dev;
	}

	plug(DUT_PORT, true);
}

/* Class requests to the hub (usbh_ch11.c) */

int usbh_req_desc_hub(struct usb_device *const udev, uint8_t *const buffer, const uint16_t len)
{
	const struct usb_hub_descriptor desc = {
		.bDescLength = 9,
		.bDescriptorType = USB_HUB_DESCRIPTOR_TYPE,
		.bNbrPorts = HUB_PORTS,
		.bPwrOn2PwrGood = 50,
	};

	memcpy(buffer, &desc, MIN(len, sizeof(desc)));

	return 0;
}

int usbh_req_set_hcfs_port_power(struct usb_device *const udev, const uint8_t port)
{
	return 0;
}

int usbh_req_set_hcfs_port_reset(struct usb_device *const udev, const uint8_t port)
{
	K_SPINLOCK(&lock) {
		struct fake_port *const p = &ports[port];
		const int64_t now = k_uptime_get();

		if (p->resets == 0) {
			p->first_reset_at = now;
		}

		p->resets++;
		p->min_settle_ms = MIN(p->min_settle_ms, now - p->connection_at);
		p->enabled = false;
		if (p->connected) {
			p->resetting = true;
			p->reset_end = now + p->dev.reset_ms;
		}
	}

	return 0;
}

int usbh_req_get_port_status(struct usb_device *const udev, const uint8_t port,
			     uint16_t *const status, uint16_t *const change)
{
	K_SPINLOCK(&lock) {
		struct fake_port *const p = &ports[port];

		port_update(p);
		*status = USB_HUB_PORT_STATUS_POWER |
			  (p->connected ? USB_HUB_PORT_STATUS_CONNECTION : 0) |
			  (p->enabled ? USB_HUB_PORT_STATUS_ENABLE : 0) |
			  (p->resetting ? USB_HUB_PORT_STATUS_RESET : 0);
		*change = p->change;
	}

	return 0;
}

static int clear_change(const uint8_t port, const uint16_t bit)
{
	K_SPINLOCK(&lock) {
		ports[port].change &= ~bit;
	}

	return 0;
}

int usbh_req_clear_hcfs_c_port_connection(struct usb_device *const udev, const uint8_t port)
{
	return clear_change(port, USB_HUB_PORT_CHANGE_CONNECTION);
}

int usbh_req_clear_hcfs_c_port_enable(struct usb_device *const udev, const uint8_t port)
{
	return clear_change(port, USB_HUB_PORT_CHANGE_ENABLE);
}

int usbh_req_clear_hcfs_c_port_suspend(struct usb_device *const udev, const uint8_t port)
{
	return clear_change(port, USB_HUB_PORT_CHANGE_SUSPEND);
}

int usbh_req_clear_hcfs_c_port_reset(struct usb_device *const udev, const uint8_t port)
{
	return clear_change(port, USB_HUB_PORT_CHANGE_RESET);
}

int usbh_req_clear_hcfs_c_port_over_current(struct usb_device *const udev, const uint8_t port)
{
	return clear_change(port, USB_HUB_PORT_CHANGE_OVER_CURRENT);
}

int usbh_req_get_hub_status(struct usb_device *const udev,
			    uint16_t *const status, uint16_t *const change)
{
	*status = 0;
	*change = 0;

	return 0;
}

int usbh_req_clear_hcfs_c_hub_local_power(struct usb_device *const udev)
{
	return 0;
}

int usbh_req_clear_hcfs_c_hub_over_current(struct usb_device *const udev)
{
	return 0;
}

/* The devices behind the hub (usbh_device.c) */

static struct usb_device devices[4];
static bool device_used[ARRAY_SIZE(devices)];

struct usb_device *usbh_device_alloc(struct usbh_context *const uhs_ctx)
{
	for (size_t i = 0; i < ARRAY_SIZE(devices); i++) {
		if (!device_used[i]) {
			device_used[i] = true;
			memset(&devices[i], 0, sizeof(devices[i]));
			devices[i].ctx = uhs_ctx;
			return &devices[i];
		}
	}

	return NULL;
}

static void device_free(struct usb_device *const udev)
{
	device_used[udev - devices] = false;
}

/* As the real one, a device that fails to enumerate is freed */
int usbh_device_connect(struct usbh_context *const ctx, struct usb_device *const udev)
{
	struct fake_port *const p = &ports[udev->hub_port];

	if (!p->dev.enumerates) {
		device_free(udev);
		return -EIO;
	}

	p->enumerations++;

	return 0;
}

void usbh_device_disconnect(struct usbh_context *ctx, struct usb_device *udev)
{
	device_free(udev);
}

/* The hub's interrupt IN transfer (uhc_common.c) */

NET_BUF_POOL_FIXED_DEFINE(test_pool, 4, 8, 0, NULL);
static struct uhc_transfer xfers[2];
static bool xfer_used[ARRAY_SIZE(xfers)];

struct uhc_transfer *uhc_xfer_alloc(const struct device *dev, const uint8_t ep,
				    struct usb_device *const udev,
				    void *const cb, void *const cb_priv)
{
	for (size_t i = 0; i < ARRAY_SIZE(xfers); i++) {
		if (!xfer_used[i]) {
			xfer_used[i] = true;
			xfers[i] = (struct uhc_transfer) {
				.ep = ep,
				.udev = udev,
				.cb = cb,
				.priv = cb_priv,
			};
			return &xfers[i];
		}
	}

	return NULL;
}

bool uhc_xfer_unref(struct uhc_transfer *const xfer)
{
	xfer_used[xfer - xfers] = false;

	return true;
}

struct net_buf *uhc_xfer_buf_alloc(const struct device *dev, const size_t size)
{
	return net_buf_alloc(&test_pool, K_NO_WAIT);
}

void uhc_xfer_buf_free(const struct device *dev, struct net_buf *const buf)
{
	net_buf_unref(buf);
}

int uhc_ep_enqueue(const struct device *dev, struct uhc_transfer *const xfer)
{
	K_SPINLOCK(&lock) {
		int_xfer = xfer;
	}

	k_work_submit(&int_work);

	return 0;
}

int uhc_ep_dequeue(const struct device *dev, struct uhc_transfer *const xfer)
{
	bool queued = false;

	K_SPINLOCK(&lock) {
		if (int_xfer == xfer) {
			int_xfer = NULL;
			queued = true;
		}
	}

	if (queued) {
		xfer->err = -ECONNRESET;
		((usbh_udev_cb_t)xfer->cb)(xfer->udev, xfer);
	}

	return 0;
}

/* The hub's descriptors (usbh_desc.c): one interface, its interrupt IN endpoint */

static const struct {
	struct usb_if_descriptor iface;
	struct usb_ep_descriptor ep;
} __packed hub_descs = {
	.iface = {
		.bLength = sizeof(struct usb_if_descriptor),
		.bDescriptorType = USB_DESC_INTERFACE,
		.bNumEndpoints = 1,
		.bInterfaceClass = USB_HUB_CLASS_CODE,
	},
	.ep = {
		.bLength = sizeof(struct usb_ep_descriptor),
		.bDescriptorType = USB_DESC_ENDPOINT,
		.bEndpointAddress = 0x81,
		.bmAttributes = USB_EP_TYPE_INTERRUPT,
		.wMaxPacketSize = sys_cpu_to_le16(1),
		.bInterval = 12,
	},
};

const void *usbh_desc_get_iface(const struct usb_device *const udev, const uint8_t iface)
{
	return &hub_descs.iface;
}

const void *usbh_desc_get_next_function(const void *const desc)
{
	return NULL;
}

const void *usbh_desc_get_next(const void *const desc)
{
	return desc == (const void *)&hub_descs.iface ? (const void *)&hub_descs.ep : NULL;
}

bool usbh_desc_is_valid_endpoint(const void *const desc)
{
	return ((const struct usb_desc_header *)desc)->bDescriptorType == USB_DESC_ENDPOINT;
}

/* The hub is plugged in and initialized, its ports empty */
static void before(void *fixture)
{
	K_SPINLOCK(&lock) {
		memset(ports, 0, sizeof(ports));
		for (int i = 0; i <= HUB_PORTS; i++) {
			ports[i].min_settle_ms = INT64_MAX;
		}

		int_xfer = NULL;
	}

	zassert_ok(usbh_hub_class_api.probe(&c_data, &hub_udev, USBH_CLASS_IFNUM_DEVICE));
	k_msleep(500);
	zassert_equal(hub.state, HUB_STATE_OPERATIONAL);
}

static void after(void *fixture)
{
	zassert_ok(usbh_hub_class_api.removed(&c_data));
	k_msleep(100);
}

/* The hub drives the reset for longer than the 20 ms the host first waits */
ZTEST(usbh_hub, test_slow_reset)
{
	const struct fake_device dev = {
		.reset_ms = 60,
		.enabled = true,
		.enumerates = true,
	};

	plug_device(&dev);
	k_msleep(3000);

	zassert_equal(ports[DUT_PORT].resets, 1, "%u resets", ports[DUT_PORT].resets);
	zassert_true(ports[DUT_PORT].min_settle_ms >= 100,
		     "reset %lld ms after the connection", ports[DUT_PORT].min_settle_ms);
	zassert_equal(ports[DUT_PORT].enumerations, 1);
	zassert_equal(hub.port_list[DUT_PORT - 1].state, PORT_STATE_ENABLED);
}

/* The connection makes and breaks while the device is plugged in */
ZTEST(usbh_hub, test_bouncing_connection)
{
	const struct fake_device dev = {
		.reset_ms = 15,
		.enabled = true,
		.enumerates = true,
	};

	plug_device(&dev);
	for (int i = 0; i < 10; i++) {
		k_msleep(30);
		plug(DUT_PORT, i % 2 != 0);
	}

	k_msleep(3000);

	zassert_equal(ports[DUT_PORT].resets, 1, "%u resets", ports[DUT_PORT].resets);
	zassert_true(ports[DUT_PORT].min_settle_ms >= 100,
		     "reset %lld ms after a connection change", ports[DUT_PORT].min_settle_ms);
	zassert_equal(ports[DUT_PORT].enumerations, 1);
}

/* The hub disables the port after each reset: the resets are not started over */
ZTEST(usbh_hub, test_disabled_port)
{
	const struct fake_device dev = {
		.reset_ms = 15,
		.disabled_change = true,
	};

	plug_device(&dev);
	k_msleep(10000);

	zassert_equal(ports[DUT_PORT].resets, CONFIG_USBH_HUB_PORT_RESET_TIMES,
		      "%u resets", ports[DUT_PORT].resets);
	zassert_equal(ports[DUT_PORT].enumerations, 0);
}

/* The device comes back during each reset: each reset waits for it to settle */
ZTEST(usbh_hub, test_reattaching_device)
{
	const struct fake_device dev = {
		.reset_ms = 15,
		.reattaches = true,
	};

	plug_device(&dev);
	k_msleep(10000);

	TC_PRINT("%u resets, at least %lld ms after a connection change\n",
		 ports[DUT_PORT].resets, ports[DUT_PORT].min_settle_ms);
	zassert_true(ports[DUT_PORT].resets > CONFIG_USBH_HUB_PORT_RESET_TIMES);
	zassert_true(ports[DUT_PORT].min_settle_ms >= 100);
	zassert_equal(ports[DUT_PORT].enumerations, 0);
}

/* A port that failed takes the next device plugged in */
ZTEST(usbh_hub, test_replug_after_failure)
{
	const struct fake_device bad = {
		.reset_ms = 15,
		.disabled_change = true,
	};
	const struct fake_device good = {
		.reset_ms = 15,
		.enabled = true,
		.enumerates = true,
	};

	plug_device(&bad);
	k_msleep(3000);
	plug(DUT_PORT, false);
	k_msleep(500);
	plug_device(&good);
	k_msleep(1000);

	zassert_equal(ports[DUT_PORT].resets, CONFIG_USBH_HUB_PORT_RESET_TIMES + 1);
	zassert_equal(ports[DUT_PORT].enumerations, 1);
}

static void *setup(void)
{
	k_work_init(&int_work, int_work_handler);

	zassert_equal(hub_filters[0].class, USB_HUB_CLASS_CODE);
	zassert_ok(usbh_hub_class_api.init(&c_data));

	return NULL;
}

ZTEST_SUITE(usbh_hub, NULL, setup, before, after, NULL);
