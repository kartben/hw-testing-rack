/*
 * A USB serial converter on the virtual bus, for the read-ahead tests.  A
 * counter (one byte, +1 each) comes in at a set rate into a 256-byte receive
 * FIFO, as from a UART; the bytes that find it full are dropped.  The FIFO goes
 * out on a bulk IN endpoint as an FTDI converter sends it: two status bytes
 * then up to 62 bytes per packet, a packet as soon as 62 bytes are there, or
 * when the latency timer expires (status bytes alone if there is no data).  In
 * raw mode, packets of plain data, a short one when the timer expires.
 *
 *   emu reset [raw]      idle, FIFO empty, latency 16 ms, FTDI framing or raw
 *   emu rate <bytes/s>   the incoming rate (0 stops it)
 *   emu status <s0>      the modem status byte
 *   emu lsr <bits>       line status bits of the next packet (an error)
 *   emu stats            "SIM: emu made <n> dropped <n> purged <n>"
 *
 * The FTDI vendor requests the read-ahead looks at: reset (0) with wValue 0
 * (reset) or 1 (purge receive) empties the FIFO; set latency timer (9).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdlib.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/shell/shell.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/usb/usbd.h>

#define EMU_FIFO_SIZE		256
#define EMU_MPS			64
#define EMU_LSR_IDLE		0x60	/* THRE, TEMT */
#define EMU_REQ_RESET		0x00
#define EMU_REQ_SET_LATENCY	0x09

struct emu_desc {
	struct usb_if_descriptor if0;
	struct usb_ep_descriptor if0_in_ep;
	struct usb_desc_header nil_desc;
};

static struct emu_desc emu_desc = {
	.if0 = {
		.bLength = sizeof(struct usb_if_descriptor),
		.bDescriptorType = USB_DESC_INTERFACE,
		.bInterfaceNumber = 0,
		.bAlternateSetting = 0,
		.bNumEndpoints = 1,
		/* As an FTDI converter: the tests find it by its subclass */
		.bInterfaceClass = USB_BCC_VENDOR,
		.bInterfaceSubClass = 0xFF,
		.bInterfaceProtocol = 0xFF,
		.iInterface = 0,
	},
	.if0_in_ep = {
		.bLength = sizeof(struct usb_ep_descriptor),
		.bDescriptorType = USB_DESC_ENDPOINT,
		.bEndpointAddress = 0x83,
		.bmAttributes = USB_EP_TYPE_BULK,
		.wMaxPacketSize = sys_cpu_to_le16(EMU_MPS),
		.bInterval = 0,
	},
};

static const struct usb_desc_header *const emu_fs_desc[] = {
	(struct usb_desc_header *)&emu_desc.if0,
	(struct usb_desc_header *)&emu_desc.if0_in_ep,
	(struct usb_desc_header *)&emu_desc.nil_desc,
};

static struct {
	struct k_work_delayable work;
	struct k_spinlock lock;
	struct usbd_class_data *c_data;
	bool enabled;
	/* A packet is queued on the endpoint */
	bool busy;
	bool raw;
	uint8_t fifo[EMU_FIFO_SIZE];
	size_t head;
	size_t count;
	/* The next byte of the counter */
	uint8_t next;
	uint32_t rate;
	int64_t rate_start;
	uint64_t rate_made;
	uint64_t made;
	uint64_t dropped;
	uint64_t purged;
	uint8_t latency;
	int64_t last_tx;
	uint8_t s0;
	uint8_t lsr;
} emu;

static void emu_work_handler(struct k_work *work)
{
	const uint8_t ep = emu_desc.if0_in_ep.bEndpointAddress;
	struct net_buf *buf = NULL;
	k_spinlock_key_t key;
	uint64_t target;
	size_t payload;
	int64_t now;
	size_t n;

	ARG_UNUSED(work);

	key = k_spin_lock(&emu.lock);
	if (!emu.enabled) {
		k_spin_unlock(&emu.lock, key);
		return;
	}

	now = k_uptime_get();
	target = (uint64_t)emu.rate * (uint64_t)(now - emu.rate_start) / 1000U;
	while (emu.rate_made < target) {
		if (emu.count < EMU_FIFO_SIZE) {
			emu.fifo[(emu.head + emu.count) % EMU_FIFO_SIZE] = emu.next;
			emu.count++;
		} else {
			emu.dropped++;
		}

		emu.next++;
		emu.rate_made++;
		emu.made++;
	}

	payload = emu.raw ? EMU_MPS : EMU_MPS - 2;
	if (!emu.busy && (emu.count >= payload ||
			  (now - emu.last_tx >= emu.latency && (!emu.raw || emu.count > 0)))) {
		buf = usbd_ep_buf_alloc(emu.c_data, ep, EMU_MPS);
	}

	if (buf != NULL) {
		if (!emu.raw) {
			net_buf_add_u8(buf, emu.s0);
			net_buf_add_u8(buf, EMU_LSR_IDLE | emu.lsr);
			emu.lsr = 0;
		}

		for (n = MIN(emu.count, payload); n > 0; n--) {
			net_buf_add_u8(buf, emu.fifo[emu.head]);
			emu.head = (emu.head + 1) % EMU_FIFO_SIZE;
			emu.count--;
		}

		emu.busy = true;
	}

	k_spin_unlock(&emu.lock, key);

	if (buf != NULL && usbd_ep_enqueue(emu.c_data, buf) != 0) {
		net_buf_unref(buf);
		key = k_spin_lock(&emu.lock);
		emu.busy = false;
		k_spin_unlock(&emu.lock, key);
	}

	k_work_reschedule(&emu.work, K_MSEC(1));
}

static int emu_request(struct usbd_class_data *const c_data, struct net_buf *const buf,
		       const int err)
{
	k_spinlock_key_t key;

	ARG_UNUSED(c_data);
	ARG_UNUSED(err);

	net_buf_unref(buf);

	key = k_spin_lock(&emu.lock);
	emu.busy = false;
	/* The timer starts again once a packet is out */
	emu.last_tx = k_uptime_get();
	k_spin_unlock(&emu.lock, key);

	/* A full packet goes out at once */
	k_work_reschedule(&emu.work, K_NO_WAIT);

	return 0;
}

static int emu_control_to_dev(struct usbd_class_data *const c_data,
			      const struct usb_setup_packet *const setup,
			      const struct net_buf *const buf)
{
	const uint16_t value = sys_le16_to_cpu(setup->wValue);
	k_spinlock_key_t key;
	int ret = 0;

	ARG_UNUSED(c_data);
	ARG_UNUSED(buf);

	if (setup->RequestType.recipient != USB_REQTYPE_RECIPIENT_DEVICE || setup->wLength != 0) {
		return -ENOTSUP;
	}

	key = k_spin_lock(&emu.lock);
	if (setup->bRequest == EMU_REQ_RESET) {
		if (value <= 1) {
			emu.purged += emu.count;
			emu.count = 0;
		}
	} else if (setup->bRequest == EMU_REQ_SET_LATENCY) {
		emu.latency = MAX(value & 0xFF, 1);
	} else {
		ret = -ENOTSUP;
	}
	k_spin_unlock(&emu.lock, key);

	return ret;
}

static const void *emu_get_desc(struct usbd_class_data *const c_data, const enum usbd_speed speed)
{
	ARG_UNUSED(c_data);
	ARG_UNUSED(speed);

	return emu_fs_desc;
}

static void emu_enable(struct usbd_class_data *const c_data)
{
	k_spinlock_key_t key = k_spin_lock(&emu.lock);

	emu.c_data = c_data;
	emu.enabled = true;
	emu.busy = false;
	emu.last_tx = k_uptime_get();
	k_spin_unlock(&emu.lock, key);

	k_work_reschedule(&emu.work, K_MSEC(1));
}

static void emu_disable(struct usbd_class_data *const c_data)
{
	k_spinlock_key_t key = k_spin_lock(&emu.lock);

	ARG_UNUSED(c_data);

	emu.enabled = false;
	k_spin_unlock(&emu.lock, key);
}

static void emu_reset(const bool raw)
{
	k_spinlock_key_t key = k_spin_lock(&emu.lock);
	bool busy = emu.busy;

	emu.rate = 0;
	emu.rate_start = k_uptime_get();
	emu.rate_made = 0;
	emu.made = 0;
	emu.dropped = 0;
	emu.purged = 0;
	emu.count = 0;
	emu.raw = raw;
	emu.latency = 16;
	emu.s0 = 0x01;
	emu.lsr = 0;
	k_spin_unlock(&emu.lock, key);

	/* The packet waiting for the host goes too */
	if (busy) {
		(void)usbd_ep_dequeue(usbd_class_get_ctx(emu.c_data),
				      emu_desc.if0_in_ep.bEndpointAddress);
	}
}

static int emu_init(struct usbd_class_data *const c_data)
{
	ARG_UNUSED(c_data);

	k_work_init_delayable(&emu.work, emu_work_handler);
	emu_reset(false);

	return 0;
}

static const struct usbd_class_api emu_api = {
	.control_to_dev = emu_control_to_dev,
	.request = emu_request,
	.get_desc = emu_get_desc,
	.enable = emu_enable,
	.disable = emu_disable,
	.init = emu_init,
};

static const struct usbd_cctx_vendor_req emu_vregs =
	USBD_VENDOR_REQ(EMU_REQ_RESET, EMU_REQ_SET_LATENCY);

/* Named to come after the loopback class: it keeps interface 0 and ep 0x81 */
USBD_DEFINE_CLASS(serial_emu, &emu_api, NULL, &emu_vregs);

static int emu_done(const struct shell *sh, size_t argc, char **argv, int ret)
{
	shell_fprintf(sh, SHELL_NORMAL, "SIM: emu");
	for (size_t i = 0; i < argc; i++) {
		shell_fprintf(sh, SHELL_NORMAL, " %s", argv[i]);
	}
	shell_fprintf(sh, SHELL_NORMAL, ": %d\n", ret);

	return ret;
}

static int cmd_emu_reset(const struct shell *sh, size_t argc, char **argv)
{
	emu_reset(argc > 1 && strcmp(argv[1], "raw") == 0);

	return emu_done(sh, argc, argv, 0);
}

static int cmd_emu_rate(const struct shell *sh, size_t argc, char **argv)
{
	k_spinlock_key_t key = k_spin_lock(&emu.lock);

	emu.rate = strtoul(argv[1], NULL, 0);
	emu.rate_start = k_uptime_get();
	emu.rate_made = 0;
	k_spin_unlock(&emu.lock, key);

	return emu_done(sh, argc, argv, 0);
}

static int cmd_emu_status(const struct shell *sh, size_t argc, char **argv)
{
	emu.s0 = strtoul(argv[1], NULL, 0);

	return emu_done(sh, argc, argv, 0);
}

static int cmd_emu_lsr(const struct shell *sh, size_t argc, char **argv)
{
	emu.lsr = strtoul(argv[1], NULL, 0);

	return emu_done(sh, argc, argv, 0);
}

static int cmd_emu_stats(const struct shell *sh, size_t argc, char **argv)
{
	k_spinlock_key_t key = k_spin_lock(&emu.lock);
	uint64_t made = emu.made;
	uint64_t dropped = emu.dropped;
	uint64_t purged = emu.purged;

	k_spin_unlock(&emu.lock, key);

	shell_print(sh, "SIM: emu made %llu dropped %llu purged %llu", made, dropped, purged);

	return emu_done(sh, argc, argv, 0);
}

SHELL_STATIC_SUBCMD_SET_CREATE(emu_cmds,
	SHELL_CMD_ARG(reset, NULL, "[raw]: idle, FIFO empty", cmd_emu_reset, 1, 1),
	SHELL_CMD_ARG(rate, NULL, "<bytes/s>: incoming rate", cmd_emu_rate, 2, 0),
	SHELL_CMD_ARG(status, NULL, "<s0>: modem status", cmd_emu_status, 2, 0),
	SHELL_CMD_ARG(lsr, NULL, "<bits>: line status of the next packet", cmd_emu_lsr, 2, 0),
	SHELL_CMD_ARG(stats, NULL, "bytes made, dropped, purged", cmd_emu_stats, 1, 0),
	SHELL_SUBCMD_SET_END
);

SHELL_CMD_REGISTER(emu, &emu_cmds, "serial converter on the virtual bus", NULL);
