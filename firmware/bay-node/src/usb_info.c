/*
 * The USB devices the host enumerated, for the status page, /api/usb and the
 * shell: identity, the classes of their interfaces, the strings they give,
 * a name from a table of known IDs when they give no product string, and
 * whether USB/IP reads them ahead.
 *
 * The strings are read once, by a small thread, as soon as a device shows
 * up, and kept in PSRAM.  A device that leaves while its strings are being
 * read can only be caught between two requests (the host frees it without a
 * lock we can take), so each request first checks the device is still
 * there; the reads take a few milliseconds right after the device arrives.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/usb/uhc.h>
#include <zephyr/usb/usbh.h>
#include <zephyr/usb/usb_ch9.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/logging/log.h>

#include <zephyr/usb/usbip.h>
#include <usbh_ch9.h>

#include "bay.h"

LOG_MODULE_REGISTER(usb_info, CONFIG_BAY_LOG_LEVEL);

#define UHC_DEV        DEVICE_DT_GET(DT_NODELABEL(zephyr_uhc0))
#define SCAN_PERIOD    K_SECONDS(1)
#define LANGID_DEFAULT 0x0409
#define BCC_HUB        0x09

/* Names for devices that give no product string, and debug probes */
static const struct {
	uint16_t vid;
	uint16_t pid; /* 0: any */
	uint16_t classes;
	const char *name;
} known[] = {
	{0x0483, 0x3748, USB_CLS_PROBE, "ST-LINK/V2"},
	{0x0483, 0x374b, USB_CLS_PROBE, "ST-LINK/V2-1"},
	{0x0483, 0x374e, USB_CLS_PROBE, "ST-LINK/V3"},
	{0x0483, 0x374f, USB_CLS_PROBE, "ST-LINK/V3"},
	{0x0483, 0x3753, USB_CLS_PROBE, "ST-LINK/V3"},
	{0x0483, 0x3754, USB_CLS_PROBE, "ST-LINK/V3"},
	{0x0483, 0xdf11, 0, "STM32 in DFU mode"},
	{0x1366, 0, USB_CLS_PROBE, "SEGGER J-Link"},
	{0x1fc9, 0x0143, USB_CLS_PROBE, "NXP MCU-Link"},
	{0x1fc9, 0x0090, USB_CLS_PROBE, "NXP LPC-Link2 CMSIS-DAP"},
	{0x0d28, 0x0204, USB_CLS_PROBE, "Arm DAPLink"},
	{0x2e8a, 0x000c, USB_CLS_PROBE, "Raspberry Pi Debug Probe"},
	{0x2e8a, 0x0003, 0, "RP2040 in BOOTSEL"},
	{0x2e8a, 0x000f, 0, "RP2350 in BOOTSEL"},
	{0x303a, 0x1001, USB_CLS_PROBE, "ESP32 USB JTAG/serial"},
	{0x0403, 0x6001, 0, "FT232 serial adapter"},
	{0x0403, 0x6010, 0, "FT2232 serial adapter"},
	{0x0403, 0x6011, 0, "FT4232 serial adapter"},
	{0x0403, 0x6014, 0, "FT232H serial adapter"},
	{0x0403, 0x6015, 0, "FT-X serial adapter"},
	{0x10c4, 0xea60, 0, "CP210x serial adapter"},
	{0x10c4, 0xea70, 0, "CP2105 serial adapter"},
	{0x10c4, 0xea71, 0, "CP2108 serial adapter"},
	{0x067b, 0x2303, 0, "PL2303 serial adapter"},
	{0x1a86, 0x7523, 0, "CH340 serial adapter"},
	{0x1a86, 0x5523, 0, "CH341 serial adapter"},
	{0x1a86, 0x55d3, 0, "CH343 serial adapter"},
	{0x1a86, 0x55d4, 0, "CH9102 serial adapter"},
	{0x0424, 0x2517, 0, "USB2517 hub"},
};

/* Kept across scans, in PSRAM: a device's strings, by address and IDs */
struct strings {
	bool used;
	uint8_t addr;
	uint16_t vid;
	uint16_t pid;
	char manufacturer[USB_STR_LEN];
	char product[USB_STR_LEN];
	char serial[USB_STR_LEN];
};

static BAY_EXT_RAM struct strings cache[USB_INFO_MAX];
static K_MUTEX_DEFINE(cache_lock);

static struct usbh_context *host_ctx(void)
{
	STRUCT_SECTION_FOREACH(usbh_context, ctx) {
		if (ctx->dev == UHC_DEV) {
			return ctx;
		}
	}

	return NULL;
}

static struct strings *cache_find(uint8_t addr, uint16_t vid, uint16_t pid)
{
	for (int i = 0; i < ARRAY_SIZE(cache); i++) {
		if (cache[i].used && cache[i].addr == addr && cache[i].vid == vid &&
		    cache[i].pid == pid) {
			return &cache[i];
		}
	}

	return NULL;
}

/* UTF-16LE from a string descriptor to UTF-8, control characters dropped */
static void utf16_to_utf8(const uint8_t *in, size_t in_len, char *out, size_t size)
{
	size_t n = 0;

	for (size_t i = 0; i + 1 < in_len; i += 2) {
		uint16_t c = sys_get_le16(&in[i]);
		uint8_t enc[3];
		size_t len;

		if (c < 0x20 || c == 0x7f) {
			continue;
		}
		if (c < 0x80) {
			enc[0] = c;
			len = 1;
		} else if (c < 0x800) {
			enc[0] = 0xc0 | (c >> 6);
			enc[1] = 0x80 | (c & 0x3f);
			len = 2;
		} else if (c >= 0xd800 && c < 0xe000) {
			enc[0] = '?';
			len = 1;
		} else {
			enc[0] = 0xe0 | (c >> 12);
			enc[1] = 0x80 | ((c >> 6) & 0x3f);
			enc[2] = 0x80 | (c & 0x3f);
			len = 3;
		}
		if (n + len >= size) {
			break;
		}
		memcpy(&out[n], enc, len);
		n += len;
	}
	/* Some devices pad their strings with spaces */
	while (n > 0 && out[n - 1] == ' ') {
		n--;
	}
	out[n] = '\0';
}

/* The device is still the one we saw: same pointer, address and IDs */
static bool still_there(struct usbh_context *ctx, struct usb_device *udev, uint8_t addr,
			uint16_t vid, uint16_t pid)
{
	struct usb_device *d;
	bool found = false;

	if (k_mutex_lock(&ctx->mutex, K_MSEC(100)) != 0) {
		return false;
	}
	SYS_DLIST_FOR_EACH_CONTAINER(&ctx->udevs, d, node) {
		if (d == udev && d->addr == addr && d->dev_desc.idVendor == vid &&
		    d->dev_desc.idProduct == pid && d->state == USB_STATE_CONFIGURED) {
			found = true;
			break;
		}
	}
	k_mutex_unlock(&ctx->mutex);

	return found;
}

static int read_string(struct usbh_context *ctx, struct usb_device *udev, uint8_t index,
		       uint16_t langid, char *out, size_t size)
{
	struct net_buf *buf;
	int ret;

	out[0] = '\0';
	if (index == 0) {
		return 0;
	}
	buf = uhc_xfer_buf_alloc(ctx->dev, UINT8_MAX);
	if (buf == NULL) {
		return -ENOMEM;
	}
	ret = usbh_req_desc(udev, USB_DESC_STRING, index, langid, UINT8_MAX, buf);
	if (ret == 0 && buf->len >= 2) {
		utf16_to_utf8(&buf->data[2], MIN(buf->data[0], buf->len) - 2, out, size);
	}
	uhc_xfer_buf_free(ctx->dev, buf);

	return ret;
}

struct pending {
	struct usb_device *udev;
	uint8_t addr;
	uint16_t vid;
	uint16_t pid;
	uint8_t i_manufacturer;
	uint8_t i_product;
	uint8_t i_serial;
};

static void read_strings(struct usbh_context *ctx, const struct pending *p)
{
	static BAY_EXT_RAM struct strings s;
	uint16_t langid = LANGID_DEFAULT;
	struct net_buf *buf;

	memset(&s, 0, sizeof(s));
	s.used = true;
	s.addr = p->addr;
	s.vid = p->vid;
	s.pid = p->pid;

	/* String 0: the languages; the first is used */
	if ((p->i_manufacturer || p->i_product || p->i_serial) &&
	    still_there(ctx, p->udev, p->addr, p->vid, p->pid)) {
		buf = uhc_xfer_buf_alloc(ctx->dev, 4);
		if (buf != NULL) {
			if (usbh_req_desc(p->udev, USB_DESC_STRING, 0, 0, 4, buf) == 0 &&
			    buf->len >= 4) {
				langid = sys_get_le16(&buf->data[2]);
			}
			uhc_xfer_buf_free(ctx->dev, buf);
		}
	}
	if (still_there(ctx, p->udev, p->addr, p->vid, p->pid)) {
		(void)read_string(ctx, p->udev, p->i_manufacturer, langid, s.manufacturer,
				  sizeof(s.manufacturer));
	}
	if (still_there(ctx, p->udev, p->addr, p->vid, p->pid)) {
		(void)read_string(ctx, p->udev, p->i_product, langid, s.product,
				  sizeof(s.product));
	}
	if (still_there(ctx, p->udev, p->addr, p->vid, p->pid)) {
		(void)read_string(ctx, p->udev, p->i_serial, langid, s.serial, sizeof(s.serial));
	}

	k_mutex_lock(&cache_lock, K_FOREVER);
	for (int i = 0; i < ARRAY_SIZE(cache); i++) {
		if (!cache[i].used) {
			cache[i] = s;
			break;
		}
	}
	k_mutex_unlock(&cache_lock);
	LOG_INF("USB %04x:%04x: %s %s", p->vid, p->pid, s.manufacturer, s.product);
}

/* Drop the strings of the devices that left */
static void cache_prune(struct usbh_context *ctx)
{
	struct usb_device *d;

	k_mutex_lock(&cache_lock, K_FOREVER);
	for (int i = 0; i < ARRAY_SIZE(cache); i++) {
		bool present = false;

		if (!cache[i].used) {
			continue;
		}
		SYS_DLIST_FOR_EACH_CONTAINER(&ctx->udevs, d, node) {
			if (d->addr == cache[i].addr && d->dev_desc.idVendor == cache[i].vid &&
			    d->dev_desc.idProduct == cache[i].pid) {
				present = true;
				break;
			}
		}
		if (!present) {
			cache[i].used = false;
		}
	}
	k_mutex_unlock(&cache_lock);
}

static void scan(void)
{
	struct usbh_context *ctx = host_ctx();
	struct pending todo[USB_INFO_MAX];
	struct usb_device *d;
	int n = 0;

	if (ctx == NULL || !uhc_is_initialized(ctx->dev) ||
	    k_mutex_lock(&ctx->mutex, K_MSEC(100)) != 0) {
		return;
	}
	cache_prune(ctx);
	SYS_DLIST_FOR_EACH_CONTAINER(&ctx->udevs, d, node) {
		if (n == ARRAY_SIZE(todo) || d->state != USB_STATE_CONFIGURED) {
			continue;
		}
		k_mutex_lock(&cache_lock, K_FOREVER);
		bool known_strings = cache_find(d->addr, d->dev_desc.idVendor,
						d->dev_desc.idProduct) != NULL;
		k_mutex_unlock(&cache_lock);
		if (!known_strings) {
			todo[n++] = (struct pending){
				.udev = d, .addr = d->addr, .vid = d->dev_desc.idVendor,
				.pid = d->dev_desc.idProduct,
				.i_manufacturer = d->dev_desc.iManufacturer,
				.i_product = d->dev_desc.iProduct,
				.i_serial = d->dev_desc.iSerialNumber};
		}
	}
	k_mutex_unlock(&ctx->mutex);

	for (int i = 0; i < n; i++) {
		read_strings(ctx, &todo[i]);
	}
}

static void usb_info_thread(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	while (true) {
		k_sleep(SCAN_PERIOD);
		scan();
	}
}

K_THREAD_DEFINE(usb_info_tid, CONFIG_BAY_USB_INFO_STACK_SIZE, usb_info_thread, NULL, NULL, NULL,
		K_LOWEST_APPLICATION_THREAD_PRIO, 0, 0);

/* The classes of the configuration's interfaces */
static uint16_t iface_classes(const struct usb_device *d)
{
	const struct usb_cfg_descriptor *cfg = d->cfg_desc;
	const uint8_t *p = d->cfg_desc;
	uint16_t classes = 0;
	size_t total;

	if (d->dev_desc.bDeviceClass == BCC_HUB) {
		classes |= USB_CLS_HUB;
	}
	if (cfg == NULL) {
		return classes;
	}
	total = sys_le16_to_cpu(cfg->wTotalLength);
	for (size_t off = 0; off + 2 <= total && p[off] >= 2; off += p[off]) {
		const struct usb_if_descriptor *ifd = (const void *)&p[off];

		if (ifd->bDescriptorType != USB_DESC_INTERFACE || off + sizeof(*ifd) > total) {
			continue;
		}
		switch (ifd->bInterfaceClass) {
		case USB_BCC_CDC_CONTROL:
			classes |= ifd->bInterfaceSubClass == 0x02 ? USB_CLS_CDC_ACM : USB_CLS_OTHER;
			break;
		case USB_BCC_CDC_DATA:
			break;
		case USB_BCC_HID:
			classes |= USB_CLS_HID;
			break;
		case USB_BCC_MASS_STORAGE:
			classes |= USB_CLS_MSC;
			break;
		case BCC_HUB:
			classes |= USB_CLS_HUB;
			break;
		case USB_BCC_AUDIO:
			classes |= USB_CLS_AUDIO;
			break;
		case USB_BCC_VIDEO:
			classes |= USB_CLS_VIDEO;
			break;
		case USB_BCC_APPLICATION:
			classes |= ifd->bInterfaceSubClass == 0x01 ? USB_CLS_DFU : USB_CLS_OTHER;
			break;
		case USB_BCC_VENDOR:
			classes |= USB_CLS_VENDOR;
			break;
		default:
			classes |= USB_CLS_OTHER;
			break;
		}
	}

	return classes;
}

/* The bus id the USB/IP service gives the device: 1-1, 1-1.<port>, ... */
static void busid_of(const struct usb_device *d, char *busid, size_t len)
{
	uint8_t ports[4];
	size_t n = 0;
	int pos;

	for (; d->hub != NULL && n < ARRAY_SIZE(ports); d = d->hub) {
		ports[n++] = d->hub_port;
	}
	pos = snprintf(busid, len, "1-1");
	while (n > 0 && pos > 0 && (size_t)pos < len) {
		pos += snprintf(busid + pos, len - pos, ".%u", ports[--n]);
	}
}

int usb_info_list(struct usb_dev_info *out, int max)
{
	struct usbh_context *ctx = host_ctx();
	struct usb_device *udevs[USB_INFO_MAX];
	struct usb_device *d;
	int n = 0;

	if (ctx == NULL || !uhc_is_initialized(ctx->dev)) {
		return 0;
	}
	if (k_mutex_lock(&ctx->mutex, K_MSEC(100)) != 0) {
		return -EBUSY;
	}
	SYS_DLIST_FOR_EACH_CONTAINER(&ctx->udevs, d, node) {
		struct usb_dev_info *u;
		const struct strings *s;

		if (n == max || n == ARRAY_SIZE(udevs) || d->state != USB_STATE_CONFIGURED) {
			continue;
		}
		udevs[n] = d;
		u = &out[n++];
		memset(u, 0, sizeof(*u));
		busid_of(d, u->busid, sizeof(u->busid));
		u->addr = d->addr;
		u->level = d->level;
		u->root_port = d->hub != NULL && d->hub->hub == NULL ? d->hub_port : 0;
		u->speed = d->speed;
		u->vid = sys_le16_to_cpu(d->dev_desc.idVendor);
		u->pid = sys_le16_to_cpu(d->dev_desc.idProduct);
		u->classes = iface_classes(d);
		u->read_ahead = usb_host_read_ahead(&d->dev_desc);

		ARRAY_FOR_EACH_PTR(known, k) {
			if (k->vid == u->vid && (k->pid == 0 || k->pid == u->pid)) {
				u->known = k->name;
				u->classes |= k->classes;
				break;
			}
		}

		k_mutex_lock(&cache_lock, K_FOREVER);
		s = cache_find(d->addr, d->dev_desc.idVendor, d->dev_desc.idProduct);
		if (s != NULL) {
			u->strings = true;
			strcpy(u->manufacturer, s->manufacturer);
			strcpy(u->product, s->product);
			strcpy(u->serial, s->serial);
		}
		k_mutex_unlock(&cache_lock);
		/* CMSIS-DAP probes say so in their product string */
		if (strstr(u->product, "CMSIS-DAP") != NULL) {
			u->classes |= USB_CLS_CMSIS_DAP | USB_CLS_PROBE;
		}
	}
	k_mutex_unlock(&ctx->mutex);

	/* Outside the host's lock: the service takes its own; it only compares the pointers */
	for (int i = 0; i < n; i++) {
		out[i].offered = usbip_device_offered(udevs[i]);
	}

	return n;
}
