/*
 * gusmanb's analyzer on the virtual bus, as far as the relay uses it:
 * 1209:3020 with a CDC control interface (its notification endpoint is never
 * used) and a CDC data interface, a bulk OUT and a bulk IN endpoint.  It
 * keeps what the host writes and the DTR/RTS the host sets, answers the
 * protocol's ID request when told to, and sends what the tests give it a
 * buffer at a time, ending on a zero-length packet as TinyUSB does.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/drivers/usb/udc.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/usb/usbd.h>

#include "cdc_emu.h"

#define EMU_MPS	   64
#define EMU_PIECE  512 /* bytes per IN buffer */
#define IN_FLIGHT  2
/* The device stack may renumber the endpoints: their descriptors say where they are */
#define EMU_EP_OUT emu_desc.if1_out_ep.bEndpointAddress
#define EMU_EP_IN  emu_desc.if1_in_ep.bEndpointAddress

#define CDC_SET_CONTROL_LINE_STATE 0x22

/* The analyzer's ID request (cmd 0) and the start of its answer */
static const uint8_t id_request[] = {0x55, 0xaa, 0x00, 0xaa, 0x55};
const char cdc_emu_id[] = "LOGIC_ANALYZER_PICO_2_V6_0\nFREQ:100000000\n";

struct emu_desc {
	struct usb_if_descriptor if0;
	struct usb_ep_descriptor if0_int_ep;
	struct usb_if_descriptor if1;
	struct usb_ep_descriptor if1_out_ep;
	struct usb_ep_descriptor if1_in_ep;
	struct usb_desc_header nil_desc;
};

static struct emu_desc emu_desc = {
	.if0 = {
		.bLength = sizeof(struct usb_if_descriptor),
		.bDescriptorType = USB_DESC_INTERFACE,
		.bInterfaceNumber = 0,
		.bNumEndpoints = 1,
		.bInterfaceClass = USB_BCC_CDC_CONTROL,
		.bInterfaceSubClass = 0x02, /* ACM */
		.bInterfaceProtocol = 0x00,
	},
	.if0_int_ep = {
		.bLength = sizeof(struct usb_ep_descriptor),
		.bDescriptorType = USB_DESC_ENDPOINT,
		.bEndpointAddress = 0x83,
		.bmAttributes = USB_EP_TYPE_INTERRUPT,
		.wMaxPacketSize = sys_cpu_to_le16(16),
		.bInterval = 10,
	},
	.if1 = {
		.bLength = sizeof(struct usb_if_descriptor),
		.bDescriptorType = USB_DESC_INTERFACE,
		.bInterfaceNumber = 1,
		.bNumEndpoints = 2,
		.bInterfaceClass = USB_BCC_CDC_DATA,
	},
	.if1_out_ep = {
		.bLength = sizeof(struct usb_ep_descriptor),
		.bDescriptorType = USB_DESC_ENDPOINT,
		.bEndpointAddress = 0x01,
		.bmAttributes = USB_EP_TYPE_BULK,
		.wMaxPacketSize = sys_cpu_to_le16(EMU_MPS),
	},
	.if1_in_ep = {
		.bLength = sizeof(struct usb_ep_descriptor),
		.bDescriptorType = USB_DESC_ENDPOINT,
		.bEndpointAddress = 0x82,
		.bmAttributes = USB_EP_TYPE_BULK,
		.wMaxPacketSize = sys_cpu_to_le16(EMU_MPS),
	},
};

static const struct usb_desc_header *const emu_fs_desc[] = {
	(struct usb_desc_header *)&emu_desc.if0,
	(struct usb_desc_header *)&emu_desc.if0_int_ep,
	(struct usb_desc_header *)&emu_desc.if1,
	(struct usb_desc_header *)&emu_desc.if1_out_ep,
	(struct usb_desc_header *)&emu_desc.if1_in_ep,
	(struct usb_desc_header *)&emu_desc.nil_desc,
};

struct cdc_emu cdc;

static K_MUTEX_DEFINE(lock);

/* What is being sent to the host */
static struct {
	struct usbd_class_data *c_data;
	const uint8_t *src;
	size_t len;
	size_t off;
	int in_flight;
	bool zlp; /* the zero-length packet that ends a whole number of packets */
} st;

static void arm_out(void)
{
	struct net_buf *buf = usbd_ep_buf_alloc(st.c_data, EMU_EP_OUT, EMU_MPS);

	if (buf != NULL && usbd_ep_enqueue(st.c_data, buf) != 0) {
		net_buf_unref(buf);
	}
}

/* Under lock: the next buffers of what is being sent */
static void feed(void)
{
	while (st.c_data != NULL && st.in_flight < IN_FLIGHT && (st.off < st.len || st.zlp)) {
		size_t n = MIN(EMU_PIECE, st.len - st.off);
		struct net_buf *buf = usbd_ep_buf_alloc(st.c_data, EMU_EP_IN, MAX(n, EMU_MPS));

		if (buf == NULL) {
			return;
		}
		net_buf_add_mem(buf, st.src + st.off, n);
		if (usbd_ep_enqueue(st.c_data, buf) != 0) {
			net_buf_unref(buf);
			return;
		}
		st.in_flight++;
		st.off += n;
		if (n == 0) {
			st.zlp = false;
		} else if (st.off == st.len) {
			st.zlp = st.len % EMU_MPS == 0;
		}
	}
}

int cdc_emu_send(const uint8_t *data, size_t len)
{
	int ret = 0;

	k_mutex_lock(&lock, K_FOREVER);
	if (st.off < st.len || st.in_flight > 0) {
		ret = -EBUSY;
	} else {
		st.src = data;
		st.len = len;
		st.off = 0;
		st.zlp = false;
		feed();
	}
	k_mutex_unlock(&lock);

	return ret;
}

bool cdc_emu_sent(void)
{
	bool sent;

	k_mutex_lock(&lock, K_FOREVER);
	sent = st.off == st.len && !st.zlp && st.in_flight == 0;
	k_mutex_unlock(&lock);

	return sent;
}

static int emu_request(struct usbd_class_data *const c_data, struct net_buf *const buf,
		       const int err)
{
	struct udc_buf_info *const bi = udc_get_buf_info(buf);

	ARG_UNUSED(c_data);

	k_mutex_lock(&lock, K_FOREVER);
	if (bi->ep == EMU_EP_IN) {
		st.in_flight--;
		if (err == 0) {
			feed();
		}
	} else if (bi->ep == EMU_EP_OUT && err == 0) {
		size_t n = MIN(buf->len, sizeof(cdc.got) - cdc.got_len);

		memcpy(&cdc.got[cdc.got_len], buf->data, n);
		cdc.got_len += n;
		if (cdc.answer_id && cdc.got_len >= sizeof(id_request) &&
		    memcmp(&cdc.got[cdc.got_len - sizeof(id_request)], id_request,
			   sizeof(id_request)) == 0 &&
		    st.off == st.len && st.in_flight == 0) {
			st.src = (const uint8_t *)cdc_emu_id;
			st.len = strlen(cdc_emu_id);
			st.off = 0;
			feed();
		}
		arm_out();
	}
	k_mutex_unlock(&lock);
	net_buf_unref(buf);

	return 0;
}

static int emu_control_to_dev(struct usbd_class_data *const c_data,
			      const struct usb_setup_packet *const setup,
			      const struct net_buf *const buf)
{
	ARG_UNUSED(c_data);
	ARG_UNUSED(buf);

	if (setup->bRequest != CDC_SET_CONTROL_LINE_STATE) {
		errno = -ENOTSUP;
		return 0;
	}
	cdc.line_state = sys_le16_to_cpu(setup->wValue);
	cdc.line_sets++;

	return 0;
}

static const void *emu_get_desc(struct usbd_class_data *const c_data, const enum usbd_speed speed)
{
	ARG_UNUSED(c_data);
	ARG_UNUSED(speed);

	return emu_fs_desc;
}

static void emu_enable(struct usbd_class_data *const c_data)
{
	k_mutex_lock(&lock, K_FOREVER);
	st.c_data = c_data;
	st.in_flight = 0;
	arm_out();
	feed();
	k_mutex_unlock(&lock);
}

static void emu_disable(struct usbd_class_data *const c_data)
{
	ARG_UNUSED(c_data);
}

static int emu_init(struct usbd_class_data *const c_data)
{
	ARG_UNUSED(c_data);

	return 0;
}

static const struct usbd_class_api emu_api = {
	.request = emu_request,
	.control_to_dev = emu_control_to_dev,
	.get_desc = emu_get_desc,
	.enable = emu_enable,
	.disable = emu_disable,
	.init = emu_init,
};

USBD_DEFINE_CLASS(cdc_emu, &emu_api, NULL, NULL);

USBD_DEVICE_DEFINE(emu_usbd, DEVICE_DT_GET(DT_NODELABEL(zephyr_udc0)), 0x1209, 0x3020);
USBD_DESC_LANG_DEFINE(emu_lang);
USBD_DESC_CONFIG_DEFINE(emu_cfg_desc, "FS Configuration");
USBD_CONFIGURATION_DEFINE(emu_config, 0, 50, &emu_cfg_desc);

int cdc_emu_init(void)
{
	int ret;

	ret = usbd_add_descriptor(&emu_usbd, &emu_lang);
	if (ret == 0) {
		ret = usbd_add_configuration(&emu_usbd, USBD_SPEED_FS, &emu_config);
	}
	if (ret == 0) {
		ret = usbd_register_class(&emu_usbd, "cdc_emu", USBD_SPEED_FS, 1);
	}
	if (ret == 0) {
		ret = usbd_init(&emu_usbd);
	}

	return ret;
}

void cdc_emu_reset(void)
{
	k_mutex_lock(&lock, K_FOREVER);
	memset(&cdc, 0, sizeof(cdc));
	st.src = NULL;
	st.len = 0;
	st.off = 0;
	st.zlp = false;
	st.in_flight = 0;
	k_mutex_unlock(&lock);
}

int cdc_emu_plug(void)
{
	return usbd_enable(&emu_usbd);
}

int cdc_emu_unplug(void)
{
	k_mutex_lock(&lock, K_FOREVER);
	st.c_data = NULL;
	k_mutex_unlock(&lock);

	return usbd_disable(&emu_usbd);
}
