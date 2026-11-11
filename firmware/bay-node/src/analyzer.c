/*
 * The logic analyzer on the co-processor's hub port (gusmanb's LogicAnalyzer
 * firmware, 1209:3020, a CDC ACM serial port) relayed to the bay page: the
 * page's WebSocket (analyzer_http.c, /analyzer/ws) carries the analyzer's own
 * protocol both ways, byte for byte.  The page speaks it
 * (common/web/analyzer/protocol.mjs); the node only moves the bytes.
 *
 * The analyzer belongs to the page or to USB/IP, never to both.  This host
 * class sorts before usbip_*, takes the device when the page owns it and
 * leaves it to USB/IP otherwise.  Switching owner (POST /api/analyzer) hands
 * the device to the USB host's classes again, as a new plug would, without
 * touching the bus.
 *
 * From the device: 1 KB bulk IN transfers in the host controller's buffers,
 * the next one queued while the last goes to the page and no further.  A slow
 * page slows the analyzer down (its data waits in its own buffer) instead of
 * filling the node's RAM; with no page, the data is dropped.  From the page:
 * each WebSocket message is a bulk OUT transfer.  One work item does both, on
 * a work queue of its own, so a slow page holds up nothing else; its stack is
 * in PSRAM, as the network threads' are (it never touches the flash).  No
 * buffer is the relay's own.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <stdio.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/init.h>
#include <zephyr/drivers/usb/uhc.h>
#include <zephyr/net_buf.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/usb/usb_ch9.h>
#include <zephyr/usb/usbh.h>
#include <zephyr/logging/log.h>

#include <hwtr/acl.h>
#include <usbh_class.h>
#include <usbh_desc.h>
#include <usbh_device.h>

#include "bay.h"

LOG_MODULE_REGISTER(analyzer, CONFIG_BAY_LOG_LEVEL);

BUILD_ASSERT(!IS_ENABLED(CONFIG_SMP), "lock_device() relies on one CPU");

#define HUB_PORT DT_PROP(DT_NODELABEL(coproc), hub_port)
#define VID	 0x1209
#define PID	 0x3020
#define CHUNK	 1024 /* bytes per bulk IN transfer */
#define MSG_MAX	 256  /* bytes per bulk OUT transfer, from the page */
#define OUT_MAX	 2    /* bulk OUT transfers in flight */
#define POLL_MS	 10   /* the page's messages wait at most this */

#define RELAY_STACK_SIZE 3072
#define RELAY_PRIORITY	 K_PRIO_PREEMPT(8)

/* CDC PSTN 1.2, 6.3.12: DTR and RTS set, as a terminal opening the port */
#define CDC_SET_CONTROL_LINE_STATE 0x22
#define CDC_DTR_RTS		   0x0003
#define REQTYPE_CLASS_INTERFACE	   0x21

static void relay_handler(struct k_work *work);
static K_WORK_DELAYABLE_DEFINE(relay_work, relay_handler);
static struct k_work_q relay_q;
static Z_KERNEL_STACK_DEFINE_IN(relay_stack, RELAY_STACK_SIZE, BAY_EXT_RAM);

static void relay_now(void)
{
	(void)k_work_reschedule_for_queue(&relay_q, &relay_work, K_NO_WAIT);
}

static void relay_later(void)
{
	(void)k_work_schedule_for_queue(&relay_q, &relay_work, K_MSEC(POLL_MS));
}

/* The device and its transfers; never held while the page is written to */
static K_MUTEX_DEFINE(lock);
/* The page; held by the relay while it talks to it */
static K_MUTEX_DEFINE(page_lock);

static struct {
	enum analyzer_owner owner;
	struct usb_device *udev;   /* while this class has it */
	uint8_t comm_iface;        /* the CDC control interface */
	uint8_t ep_in;
	uint8_t ep_out;
	bool line_sent;            /* DTR asked for */
	bool reading;              /* DTR set: bulk IN running */
	struct uhc_transfer *in;   /* the bulk IN in flight */
	struct net_buf *ready;     /* read, not passed on yet */
	uint8_t outs;              /* bulk OUT in flight */
	uint32_t page_ip;          /* the page's address, 0 for none */
	int64_t page_since;
	const char *error;
	uint32_t from_device;
	uint32_t to_device;
	uint32_t dropped;          /* from the device, with no page to take it */
} az;

static struct analyzer_page *page;
static atomic_t kick;

/* --- The device ------------------------------------------------------------- */

/* The co-processor's port; a DATA x6's hub port 5 is its USB-C 6, a board under test */
static bool on_port(const struct usb_device *udev)
{
	bool here = HUB_PORT == 0 ? udev->hub == NULL
				  : udev->hub != NULL && udev->hub->hub == NULL &&
					    udev->hub_port == HUB_PORT;

	return here && ports_board() != DATA_X6;
}

static bool is_analyzer(const struct usb_device *udev)
{
	return on_port(udev) && udev->state == USB_STATE_CONFIGURED &&
	       sys_le16_to_cpu(udev->dev_desc.idVendor) == VID &&
	       sys_le16_to_cpu(udev->dev_desc.idProduct) == PID;
}

/* The analyzer in the host's device list, with the scheduler locked */
static struct usb_device *find(void)
{
	STRUCT_SECTION_FOREACH(usbh_context, ctx) {
		struct usb_device *d;

		if (!uhc_is_initialized(ctx->dev)) {
			continue;
		}
		SYS_DLIST_FOR_EACH_CONTAINER(&ctx->udevs, d, node) {
			if (is_analyzer(d)) {
				return d;
			}
		}
	}

	return NULL;
}

static bool present(void)
{
	bool found;

	k_sched_lock();
	found = find() != NULL;
	k_sched_unlock();

	return found;
}

/*
 * The analyzer, with its mutex held.  Found and locked with the scheduler
 * locked, so the hub's thread cannot free it in between (one CPU), and still
 * bound to a class: its removal, which takes that mutex, has not started.
 */
static int lock_device(struct usb_device **out)
{
	struct usb_device *d;

	k_sched_lock();
	d = find();
	if (d != NULL && k_mutex_lock(&d->mutex, K_NO_WAIT) != 0) {
		k_sched_unlock();
		return -EBUSY;
	}
	k_sched_unlock();

	if (d == NULL) {
		return -ENODEV;
	}
	STRUCT_SECTION_FOREACH(usbh_class_node, c_node) {
		if (c_node->state == USBH_CLASS_STATE_BOUND && c_node->c_data->udev == d) {
			*out = d;
			return 0;
		}
	}
	k_mutex_unlock(&d->mutex);

	return -ENODEV;
}

/* Back to the host's classes, which take it by the current owner */
static int rebind(void)
{
	struct usb_device *udev;
	int ret;

	for (int i = 0; i < 50; i++) {
		ret = lock_device(&udev);
		if (ret != -EBUSY) {
			break;
		}
		k_sleep(K_MSEC(10));
	}
	if (ret != 0) {
		/* Not there: the next plug follows the owner */
		return ret == -ENODEV ? 0 : ret;
	}
	usbh_class_remove_all(udev);
	usbh_class_probe_device(udev);
	k_mutex_unlock(&udev->mutex);

	return 0;
}

/* --- Transfers (under lock, with a device) ------------------------------------ */

static int xfer_cb(struct usb_device *const udev, struct uhc_transfer *const xfer)
{
	struct net_buf *buf = xfer->buf;
	const size_t len = buf != NULL ? buf->len : 0;
	bool again = true;

	k_mutex_lock(&lock, K_FOREVER);
	if (xfer == az.in) {
		az.in = NULL;
	}
	if (udev != az.udev) {
		/* A transfer of a device this class let go */
	} else if (USB_EP_GET_IDX(xfer->ep) == 0) {
		az.reading = xfer->err == 0;
		az.error = xfer->err == 0 ? NULL : "the analyzer refused DTR";
	} else if (USB_EP_DIR_IS_IN(xfer->ep)) {
		if (xfer->err == 0 && len > 0) {
			az.ready = buf;
			buf = NULL;
			az.from_device += len;
		} else if (xfer->err != 0 && xfer->err != -ECONNRESET) {
			/* Read again, but not at once: an endpoint that keeps failing */
			az.error = "USB read failed";
			again = false;
		}
	} else {
		az.outs--;
		if (xfer->err != 0) {
			az.error = "USB write failed";
		}
	}
	k_mutex_unlock(&lock);

	if (buf != NULL) {
		net_buf_unref(buf);
	}
	(void)uhc_xfer_unref(xfer);
	if (again) {
		relay_now();
	} else {
		relay_later();
	}

	return 0;
}

static struct uhc_transfer *submit(uint8_t ep, struct net_buf *buf)
{
	struct uhc_transfer *xfer = usbh_xfer_alloc(az.udev, ep, xfer_cb, NULL);

	if (xfer != NULL && usbh_xfer_buf_add(az.udev, xfer, buf) == 0 &&
	    usbh_xfer_enqueue(az.udev, xfer) == 0) {
		return xfer;
	}
	if (xfer != NULL) {
		(void)uhc_xfer_unref(xfer);
	}
	net_buf_unref(buf);
	az.error = "USB transfer refused";

	return NULL;
}

/* TinyUSB's CDC (the analyzer's) counts the port as open once DTR is set */
static void set_line_state(void)
{
	const struct usb_setup_packet req = {
		.bmRequestType = REQTYPE_CLASS_INTERFACE,
		.bRequest = CDC_SET_CONTROL_LINE_STATE,
		.wValue = sys_cpu_to_le16(CDC_DTR_RTS),
		.wIndex = sys_cpu_to_le16(az.comm_iface),
	};
	struct uhc_transfer *xfer = usbh_xfer_alloc(az.udev, USB_CONTROL_EP_OUT, xfer_cb, NULL);

	az.line_sent = true;
	if (xfer == NULL) {
		az.error = "no USB transfer free";
		return;
	}
	memcpy(xfer->setup_pkt, &req, sizeof(req));
	if (usbh_xfer_enqueue(az.udev, xfer) != 0) {
		(void)uhc_xfer_unref(xfer);
		az.error = "USB transfer refused";
	}
}

static void read_next(void)
{
	struct net_buf *buf = usbh_xfer_buf_alloc(az.udev, CHUNK);

	if (buf == NULL) {
		/* The pool is busy: next time */
		relay_later();
		return;
	}
	az.in = submit(az.ep_in, buf);
}

/* --- The page (under page_lock) ----------------------------------------------- */

static void page_close(const char *why)
{
	page->close(page);
	page = NULL;
	k_mutex_lock(&lock, K_FOREVER);
	az.page_ip = 0;
	k_mutex_unlock(&lock);
	LOG_INF("page closed: %s", why);
}

/* The page's messages, each a bulk OUT transfer */
static void from_page(void)
{
	while (page != NULL) {
		struct usb_device *udev;
		struct net_buf *buf = NULL;
		int n;

		k_mutex_lock(&lock, K_FOREVER);
		udev = az.reading && az.outs < OUT_MAX ? az.udev : NULL;
		if (udev != NULL) {
			buf = usbh_xfer_buf_alloc(udev, MSG_MAX);
		}
		k_mutex_unlock(&lock);
		if (buf == NULL) {
			return;
		}

		n = page->recv(page, buf->data, MSG_MAX);
		if (n <= 0) {
			net_buf_unref(buf);
			if (n < 0) {
				page_close("it left");
			}
			return;
		}
		net_buf_add(buf, n);

		k_mutex_lock(&lock, K_FOREVER);
		if (az.udev != udev) {
			net_buf_unref(buf);
		} else if (submit(az.ep_out, buf) != NULL) {
			az.outs++;
			az.to_device += n;
		}
		k_mutex_unlock(&lock);
	}
}

static void relay_handler(struct k_work *work)
{
	struct net_buf *buf;

	ARG_UNUSED(work);

	k_mutex_lock(&page_lock, K_FOREVER);
	if (atomic_clear(&kick) && page != NULL) {
		page_close("the analyzer went to USB/IP or away");
	}

	k_mutex_lock(&lock, K_FOREVER);
	if (az.udev != NULL && !az.line_sent) {
		set_line_state();
	}
	buf = az.ready;
	az.ready = NULL;
	if (buf != NULL && page == NULL) {
		az.dropped += buf->len;
	}
	/* The next read fills while this one goes to the page */
	if (az.udev != NULL && az.reading && az.in == NULL) {
		read_next();
	}
	k_mutex_unlock(&lock);

	if (buf != NULL) {
		if (page != NULL && page->send(page, buf->data, buf->len) < 0) {
			page_close("it did not keep up");
		}
		net_buf_unref(buf);
	}
	from_page();

	if (page != NULL) {
		relay_later();
	}
	k_mutex_unlock(&page_lock);
}

/* --- Host class --------------------------------------------------------------- */

/* The CDC control interface, and the data interface's bulk endpoints */
static bool find_cdc(struct usb_device *const udev)
{
	const struct usb_desc_header *h = udev->cfg_desc;
	bool data = false;
	bool comm = false;

	az.ep_in = 0;
	az.ep_out = 0;
	while ((h = usbh_desc_get_next(h)) != NULL) {
		if (h->bDescriptorType == USB_DESC_INTERFACE && usbh_desc_is_valid_interface(h)) {
			const struct usb_if_descriptor *i = (const struct usb_if_descriptor *)h;

			data = i->bInterfaceClass == USB_BCC_CDC_DATA;
			if (i->bInterfaceClass == USB_BCC_CDC_CONTROL) {
				az.comm_iface = i->bInterfaceNumber;
				comm = true;
			}
		} else if (data && h->bDescriptorType == USB_DESC_ENDPOINT &&
			   usbh_desc_is_valid_endpoint(h)) {
			const struct usb_ep_descriptor *e = (const struct usb_ep_descriptor *)h;

			if ((e->bmAttributes & USB_EP_TRANSFER_TYPE_MASK) != USB_EP_TYPE_BULK) {
				continue;
			}
			if (USB_EP_DIR_IS_IN(e->bEndpointAddress)) {
				az.ep_in = e->bEndpointAddress;
			} else {
				az.ep_out = e->bEndpointAddress;
			}
		}
	}

	return comm && az.ep_in != 0 && az.ep_out != 0;
}

static int analyzer_class_init(struct usbh_class_data *const c_data)
{
	ARG_UNUSED(c_data);

	return 0;
}

static int analyzer_class_probe(struct usbh_class_data *const c_data,
				struct usb_device *const udev, const uint8_t iface)
{
	int ret = -ENOTSUP;

	ARG_UNUSED(c_data);

	/* Only on the co-processor's port: an analyzer under test is USB/IP's */
	if (iface != USBH_CLASS_IFNUM_DEVICE || !on_port(udev)) {
		return -ENOTSUP;
	}

	k_mutex_lock(&lock, K_FOREVER);
	if (az.owner != ANALYZER_PAGE) {
		LOG_INF("left to USB/IP");
	} else if (!find_cdc(udev)) {
		az.error = "no CDC interfaces";
	} else {
		az.udev = udev;
		az.line_sent = false;
		az.reading = false;
		az.outs = 0;
		az.error = NULL;
		ret = 0;
		LOG_INF("relayed to the bay page");
	}
	k_mutex_unlock(&lock);

	if (ret == 0) {
		relay_now();
	}

	return ret;
}

static int analyzer_class_removed(struct usbh_class_data *const c_data)
{
	k_mutex_lock(&lock, K_FOREVER);
	if (c_data->udev == az.udev) {
		/* Its completion comes back through the host's thread, not ours */
		if (az.in != NULL) {
			(void)usbh_xfer_dequeue(az.udev, az.in);
			az.in = NULL;
		}
		az.udev = NULL;
		az.reading = false;
	}
	k_mutex_unlock(&lock);

	/* The page has nothing left to talk to */
	atomic_set(&kick, 1);
	relay_now();

	return 0;
}

static struct usbh_class_api analyzer_class_api = {
	.init = analyzer_class_init,
	.probe = analyzer_class_probe,
	.removed = analyzer_class_removed,
};

static const struct usbh_class_filter analyzer_filters[] = {
	{.vid = VID, .pid = PID, .flags = USBH_CLASS_MATCH_VID_PID},
	{0},
};

/* Named to sort before usbip_*: the first class that takes a device keeps it */
USBH_DEFINE_CLASS(analyzer, &analyzer_class_api, NULL, analyzer_filters);

/* --- API ---------------------------------------------------------------------- */

static int analyzer_init(void)
{
	const struct k_work_queue_config cfg = {.name = "analyzer"};

	k_work_queue_start(&relay_q, relay_stack, K_KERNEL_STACK_SIZEOF(relay_stack),
			   RELAY_PRIORITY, &cfg);

	return 0;
}

SYS_INIT(analyzer_init, APPLICATION, CONFIG_APPLICATION_INIT_PRIORITY);

int analyzer_attach(struct analyzer_page *p, uint32_t ip)
{
	int ret = 0;

	k_mutex_lock(&page_lock, K_FOREVER);
	k_mutex_lock(&lock, K_FOREVER);
	if (az.udev == NULL) {
		ret = az.owner == ANALYZER_PAGE ? -ENODEV : -EACCES;
	} else if (page != NULL && az.page_ip != ip) {
		/* Another address has it; the same one is a page reloaded */
		ret = -EBUSY;
	} else {
		/* Under lock: a removal from now on still closes this page */
		atomic_clear(&kick);
	}
	k_mutex_unlock(&lock);

	if (ret == 0) {
		if (page != NULL) {
			page_close("the same address opened it again");
		}
		page = p;
		k_mutex_lock(&lock, K_FOREVER);
		az.page_ip = ip;
		az.page_since = k_uptime_get();
		k_mutex_unlock(&lock);
		LOG_INF("page connected");
	}
	k_mutex_unlock(&page_lock);

	if (ret == 0) {
		relay_now();
	}

	return ret;
}

int analyzer_set_owner(enum analyzer_owner owner)
{
	bool changed;

	k_mutex_lock(&lock, K_FOREVER);
	changed = az.owner != owner;
	az.owner = owner;
	k_mutex_unlock(&lock);

	if (!changed) {
		return 0;
	}
	LOG_INF("owner: %s", owner == ANALYZER_PAGE ? "the bay page" : "USB/IP");

	return rebind();
}

int analyzer_json(char *buf, size_t size)
{
	const bool here = present();
	char page_json[64] = "null";
	char busid[12];
	int n;

	snprintf(busid, sizeof(busid), "1-1%s%.0u", HUB_PORT > 0 ? "." : "", HUB_PORT);

	k_mutex_lock(&lock, K_FOREVER);
	if (az.page_ip != 0) {
		char ip[ACL_IP_STR_LEN];

		acl_format_ip(az.page_ip, ip);
		snprintf(page_json, sizeof(page_json), "{\"ip\":\"%s\",\"since_s\":%u}", ip,
			 (uint32_t)((k_uptime_get() - az.page_since) / MSEC_PER_SEC));
	}
	n = snprintf(buf, size,
		     "{\"owner\":\"%s\",\"present\":%s,\"busid\":\"%s\",\"page\":%s,"
		     "\"from_device\":%u,\"to_device\":%u,\"dropped\":%u,\"error\":%s%s%s}",
		     az.owner == ANALYZER_PAGE ? "page" : "usbip", here ? "true" : "false", busid,
		     page_json, az.from_device, az.to_device, az.dropped,
		     az.error != NULL ? "\"" : "", az.error != NULL ? az.error : "null",
		     az.error != NULL ? "\"" : "");
	k_mutex_unlock(&lock);

	return n >= 0 && (size_t)n < size ? n : -ENOMEM;
}
