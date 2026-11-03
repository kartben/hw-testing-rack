/*
 * An RP2350 in its USB bootloader on the virtual bus, as far as the loader
 * uses it: 2e8a:000f with a vendor interface, a bulk OUT and a bulk IN
 * endpoint (PICOBOOT).  It takes EXCLUSIVE_ACCESS, WRITE into a fake SRAM
 * and REBOOT2, each acknowledged with an empty IN packet, and leaves the bus
 * after a REBOOT2 as the chip does.  The tests read what it got and can make
 * it stall a WRITE or stop answering.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/drivers/usb/udc.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/usb/usbd.h>

#include "picoboot_emu.h"

#define EMU_MPS		64
/* The device stack may renumber the endpoints: their descriptors say where they are */
#define EMU_EP_OUT	emu_desc.if0_out_ep.bEndpointAddress
#define EMU_EP_IN	emu_desc.if0_in_ep.bEndpointAddress
#define PICOBOOT_MAGIC	0x431fd10bU
#define SRAM_BASE	0x20000000U

struct emu_desc {
	struct usb_if_descriptor if0;
	struct usb_ep_descriptor if0_out_ep;
	struct usb_ep_descriptor if0_in_ep;
	struct usb_desc_header nil_desc;
};

static struct emu_desc emu_desc = {
	.if0 = {
		.bLength = sizeof(struct usb_if_descriptor),
		.bDescriptorType = USB_DESC_INTERFACE,
		.bInterfaceNumber = 0,
		.bAlternateSetting = 0,
		.bNumEndpoints = 2,
		.bInterfaceClass = USB_BCC_VENDOR,
		.bInterfaceSubClass = 0,
		.bInterfaceProtocol = 0,
		.iInterface = 0,
	},
	.if0_out_ep = {
		.bLength = sizeof(struct usb_ep_descriptor),
		.bDescriptorType = USB_DESC_ENDPOINT,
		.bEndpointAddress = 0x01,
		.bmAttributes = USB_EP_TYPE_BULK,
		.wMaxPacketSize = sys_cpu_to_le16(EMU_MPS),
		.bInterval = 0,
	},
	.if0_in_ep = {
		.bLength = sizeof(struct usb_ep_descriptor),
		.bDescriptorType = USB_DESC_ENDPOINT,
		.bEndpointAddress = 0x82,
		.bmAttributes = USB_EP_TYPE_BULK,
		.wMaxPacketSize = sys_cpu_to_le16(EMU_MPS),
		.bInterval = 0,
	},
};

static const struct usb_desc_header *const emu_fs_desc[] = {
	(struct usb_desc_header *)&emu_desc.if0,
	(struct usb_desc_header *)&emu_desc.if0_out_ep,
	(struct usb_desc_header *)&emu_desc.if0_in_ep,
	(struct usb_desc_header *)&emu_desc.nil_desc,
};

struct picoboot_emu emu;
K_SEM_DEFINE(picoboot_emu_left, 0, 1);

static struct {
	struct usbd_class_data *c_data;
	uint32_t data_addr;  /* a WRITE's data still to come */
	uint32_t data_left;
	struct k_work_delayable leave;
} st;

/* The next OUT transfer: a command, or exactly what a WRITE still sends */
static void arm_out(void)
{
	size_t n = st.data_left > 0 ? MIN(st.data_left, 512) : EMU_MPS;
	struct net_buf *buf = usbd_ep_buf_alloc(st.c_data, EMU_EP_OUT, n);

	if (buf != NULL && usbd_ep_enqueue(st.c_data, buf) != 0) {
		net_buf_unref(buf);
	}
}

static void ack(void)
{
	struct net_buf *buf;

	if (emu.mute) {
		return;
	}
	/* An empty packet */
	buf = usbd_ep_buf_alloc(st.c_data, EMU_EP_IN, EMU_MPS);
	if (buf != NULL && usbd_ep_enqueue(st.c_data, buf) != 0) {
		net_buf_unref(buf);
	}
}

static void command(const uint8_t *c, size_t len)
{
	uint32_t magic = sys_get_le32(c), transfer_len = sys_get_le32(c + 12);
	const uint8_t *args = c + 16;

	if (len != 32 || magic != PICOBOOT_MAGIC) {
		emu.bad++;
		return;
	}
	emu.cmds++;
	switch (c[8]) {
	case 0x01: /* EXCLUSIVE_ACCESS */
		emu.exclusive = args[0];
		ack();
		break;
	case 0x05: /* WRITE */
		if (emu.stall_write) {
			(void)usbd_ep_set_halt(usbd_class_get_ctx(st.c_data), EMU_EP_OUT);
			return;
		}
		st.data_addr = sys_get_le32(args);
		st.data_left = transfer_len;
		if (sys_get_le32(args + 4) != transfer_len || !emu.exclusive) {
			emu.bad++;
		}
		break;
	case 0x0a: /* REBOOT2 */
		emu.reboot_flags = sys_get_le32(args);
		emu.reboot_delay = sys_get_le32(args + 4);
		emu.reboot_p0 = sys_get_le32(args + 8);
		emu.reboot_p1 = sys_get_le32(args + 12);
		emu.reboots++;
		ack();
		/* It leaves the bus, as the chip restarting */
		k_work_schedule(&st.leave, K_MSEC(20));
		break;
	default:
		emu.bad++;
		break;
	}
}

static int emu_request(struct usbd_class_data *const c_data, struct net_buf *const buf,
		       const int err)
{
	struct udc_buf_info *const bi = udc_get_buf_info(buf);

	ARG_UNUSED(c_data);

	if (bi->ep == EMU_EP_OUT && err == 0) {
		if (st.data_left > 0) {
			uint32_t off = st.data_addr - SRAM_BASE;

			if (st.data_addr >= SRAM_BASE && off + buf->len <= sizeof(emu.sram)) {
				memcpy(&emu.sram[off], buf->data, buf->len);
			} else {
				emu.bad++;
			}
			emu.written += buf->len;
			st.data_addr += buf->len;
			st.data_left -= MIN(st.data_left, buf->len);
			if (st.data_left == 0) {
				ack();
			}
		} else {
			command(buf->data, buf->len);
		}
		net_buf_unref(buf);
		arm_out();
		return 0;
	}
	net_buf_unref(buf);

	return 0;
}

static void leave_handler(struct k_work *work)
{
	ARG_UNUSED(work);

	picoboot_emu_unplug();
	k_sem_give(&picoboot_emu_left);
}

static const void *emu_get_desc(struct usbd_class_data *const c_data, const enum usbd_speed speed)
{
	ARG_UNUSED(c_data);
	ARG_UNUSED(speed);

	return emu_fs_desc;
}

static void emu_enable(struct usbd_class_data *const c_data)
{
	st.c_data = c_data;
	st.data_left = 0;
	arm_out();
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
	.get_desc = emu_get_desc,
	.enable = emu_enable,
	.disable = emu_disable,
	.init = emu_init,
};

USBD_DEFINE_CLASS(picoboot_emu, &emu_api, NULL, NULL);

USBD_DEVICE_DEFINE(emu_usbd, DEVICE_DT_GET(DT_NODELABEL(zephyr_udc0)), 0x2e8a, 0x000f);
USBD_DESC_LANG_DEFINE(emu_lang);
USBD_DESC_CONFIG_DEFINE(emu_cfg_desc, "FS Configuration");
USBD_CONFIGURATION_DEFINE(emu_config, 0, 50, &emu_cfg_desc);

int picoboot_emu_init(void)
{
	int ret;

	k_work_init_delayable(&st.leave, leave_handler);
	ret = usbd_add_descriptor(&emu_usbd, &emu_lang);
	if (ret == 0) {
		ret = usbd_add_configuration(&emu_usbd, USBD_SPEED_FS, &emu_config);
	}
	if (ret == 0) {
		ret = usbd_register_class(&emu_usbd, "picoboot_emu", USBD_SPEED_FS, 1);
	}
	if (ret == 0) {
		ret = usbd_init(&emu_usbd);
	}

	return ret;
}

void picoboot_emu_reset(void)
{
	memset(&emu, 0, sizeof(emu));
	k_sem_reset(&picoboot_emu_left);
}

int picoboot_emu_plug(void)
{
	return usbd_enable(&emu_usbd);
}

int picoboot_emu_unplug(void)
{
	st.data_left = 0;
	return usbd_disable(&emu_usbd);
}
