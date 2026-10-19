/*
 * The node's link: one vendor-specific USB interface with a bulk OUT and a
 * bulk IN endpoint.  The node is the only client (README.md): it sends a
 * command, the co-processor answers on IN.  On the node's side this needs a
 * single host channel, only while a transfer is pending, where four CDC-ACM
 * ports opened by a host would keep eight busy.
 *
 * Spike protocol (little endian), one command per OUT transfer:
 *
 *	'V'				-> version string
 *	'R' u32 offset u32 length	-> length bytes of the capture buffer
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/drivers/usb/udc.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/usb/usbd.h>
#include <zephyr/version.h>

#include "la_pio.h"

LOG_MODULE_REGISTER(link, LOG_LEVEL_INF);

#define LINK_MPS   64U
#define LINK_CHUNK 1024U

struct link_desc {
	struct usb_if_descriptor if0;
	struct usb_ep_descriptor out_ep;
	struct usb_ep_descriptor in_ep;
	struct usb_desc_header nil_desc;
};

/* Endpoint addresses and the interface number are placeholders: usbd assigns them */
static struct link_desc link_desc = {
	.if0 = {
		.bLength = sizeof(struct usb_if_descriptor),
		.bDescriptorType = USB_DESC_INTERFACE,
		.bNumEndpoints = 2,
		.bInterfaceClass = USB_BCC_VENDOR,
	},
	.out_ep = {
		.bLength = sizeof(struct usb_ep_descriptor),
		.bDescriptorType = USB_DESC_ENDPOINT,
		.bEndpointAddress = 0x01,
		.bmAttributes = USB_EP_TYPE_BULK,
		.wMaxPacketSize = sys_cpu_to_le16(LINK_MPS),
	},
	.in_ep = {
		.bLength = sizeof(struct usb_ep_descriptor),
		.bDescriptorType = USB_DESC_ENDPOINT,
		.bEndpointAddress = 0x81,
		.bmAttributes = USB_EP_TYPE_BULK,
		.wMaxPacketSize = sys_cpu_to_le16(LINK_MPS),
	},
};

static const struct usb_desc_header *const link_fs_desc[] = {
	(struct usb_desc_header *)&link_desc.if0,
	(struct usb_desc_header *)&link_desc.out_ep,
	(struct usb_desc_header *)&link_desc.in_ep,
	(struct usb_desc_header *)&link_desc.nil_desc,
};

static atomic_t link_enabled;
static uint8_t link_cmd[LINK_MPS];
static size_t link_cmd_len;
static K_SEM_DEFINE(link_cmd_sem, 0, 1);
static K_SEM_DEFINE(link_in_sem, 0, 1);

static int link_submit_out(struct usbd_class_data *const c_data)
{
	struct net_buf *buf;
	int err;

	buf = usbd_ep_buf_alloc(c_data, link_desc.out_ep.bEndpointAddress, LINK_MPS);
	if (buf == NULL) {
		return -ENOMEM;
	}

	err = usbd_ep_enqueue(c_data, buf);
	if (err) {
		usbd_ep_buf_free(usbd_class_get_ctx(c_data), buf);
	}

	return err;
}

static int link_request(struct usbd_class_data *const c_data, struct net_buf *buf, int err)
{
	const uint8_t ep = udc_get_buf_info(buf)->ep;

	if (ep == link_desc.out_ep.bEndpointAddress) {
		if (err == 0) {
			link_cmd_len = MIN(buf->len, sizeof(link_cmd));
			memcpy(link_cmd, buf->data, link_cmd_len);
			k_sem_give(&link_cmd_sem);
		}
	} else if (ep == link_desc.in_ep.bEndpointAddress) {
		k_sem_give(&link_in_sem);
	}

	return usbd_ep_buf_free(usbd_class_get_ctx(c_data), buf);
}

static void link_enable(struct usbd_class_data *const c_data)
{
	atomic_set(&link_enabled, 1);
	(void)link_submit_out(c_data);
}

static void link_disable(struct usbd_class_data *const c_data)
{
	ARG_UNUSED(c_data);

	atomic_set(&link_enabled, 0);
	k_sem_give(&link_in_sem);
}

static const void *link_get_desc(struct usbd_class_data *const c_data, const enum usbd_speed speed)
{
	ARG_UNUSED(c_data);
	ARG_UNUSED(speed);

	return link_fs_desc;
}

static int link_init(struct usbd_class_data *const c_data)
{
	ARG_UNUSED(c_data);

	return 0;
}

static const struct usbd_class_api link_api = {
	.request = link_request,
	.enable = link_enable,
	.disable = link_disable,
	.get_desc = link_get_desc,
	.init = link_init,
};

USBD_DEFINE_CLASS(hwtr_link, &link_api, NULL, NULL);

static int link_send(const void *data, size_t len)
{
	struct usbd_class_data *const c_data = &hwtr_link;
	const uint8_t *p = data;

	do {
		const size_t n = MIN(len, LINK_CHUNK);
		struct net_buf *buf;
		int err;

		if (!atomic_get(&link_enabled)) {
			return -ENODEV;
		}

		buf = usbd_ep_buf_alloc(c_data, link_desc.in_ep.bEndpointAddress, n);
		if (buf == NULL) {
			return -ENOMEM;
		}
		net_buf_add_mem(buf, p, n);
		/* A last chunk that fills whole packets ends with a zero-length one */
		if (n > 0 && n == len && (n % LINK_MPS) == 0) {
			udc_ep_buf_set_zlp(buf);
		}

		err = usbd_ep_enqueue(c_data, buf);
		if (err) {
			usbd_ep_buf_free(usbd_class_get_ctx(c_data), buf);
			return err;
		}
		k_sem_take(&link_in_sem, K_FOREVER);

		p += n;
		len -= n;
	} while (len > 0);

	return 0;
}

static void link_handle(const uint8_t *cmd, size_t len)
{
	if (len >= 1 && cmd[0] == 'V') {
		static const char version[] = "coproc-spike zephyr " KERNEL_VERSION_STRING;

		(void)link_send(version, sizeof(version) - 1);
	} else if (len >= 9 && cmd[0] == 'R') {
		const uint32_t offset = sys_get_le32(&cmd[1]);
		const uint32_t length = sys_get_le32(&cmd[5]);

		if (offset <= sizeof(la_buf) && length <= sizeof(la_buf) - offset) {
			(void)link_send(&la_buf[offset], length);
		} else {
			(void)link_send("", 0);
		}
	} else {
		LOG_WRN("unknown command (%zu bytes)", len);
	}
}

static void link_thread(void *a, void *b, void *c)
{
	ARG_UNUSED(a);
	ARG_UNUSED(b);
	ARG_UNUSED(c);

	while (true) {
		k_sem_take(&link_cmd_sem, K_FOREVER);
		link_handle(link_cmd, link_cmd_len);
		if (atomic_get(&link_enabled)) {
			(void)link_submit_out(&hwtr_link);
		}
	}
}

K_THREAD_DEFINE(link_tid, 1024, link_thread, NULL, NULL, NULL, 5, 0, 0);
