/*
 * A mass-storage-like function on the virtual bus, for the large request
 * tests: a bulk IN endpoint that sends a stream of a set length, and a bulk
 * OUT endpoint that checks what it receives.  Both carry the same pattern,
 * byte i being i ^ (i >> 8) ^ (i >> 16), so that a segment lost or sent twice
 * shows.
 *
 *   msd reset              nothing to send, counters at 0, full speed
 *   msd in <len> [zlp]     send a stream of len bytes (a ZLP after it)
 *   msd rate <packets/ms>  at most that many 64-byte packets per ms each way
 *   msd stall <offset>     halt the IN endpoint once offset bytes are sent
 *   msd stats              "SIM: msd in <sent> out <received> bad <bytes>"
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdlib.h>
#include <string.h>

#include <zephyr/drivers/usb/udc.h>
#include <zephyr/kernel.h>
#include <zephyr/shell/shell.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/usb/usbd.h>

#define MSD_MPS		64
#define MSD_BUF_SIZE	512

struct msd_desc {
	struct usb_if_descriptor if0;
	struct usb_ep_descriptor if0_in_ep;
	struct usb_ep_descriptor if0_out_ep;
	struct usb_desc_header nil_desc;
};

static struct msd_desc msd_desc = {
	.if0 = {
		.bLength = sizeof(struct usb_if_descriptor),
		.bDescriptorType = USB_DESC_INTERFACE,
		.bInterfaceNumber = 0,
		.bAlternateSetting = 0,
		.bNumEndpoints = 2,
		/* Mass storage, SCSI, bulk-only: the tests find it by its class */
		.bInterfaceClass = 0x08,
		.bInterfaceSubClass = 0x06,
		.bInterfaceProtocol = 0x50,
		.iInterface = 0,
	},
	.if0_in_ep = {
		.bLength = sizeof(struct usb_ep_descriptor),
		.bDescriptorType = USB_DESC_ENDPOINT,
		.bEndpointAddress = 0x84,
		.bmAttributes = USB_EP_TYPE_BULK,
		.wMaxPacketSize = sys_cpu_to_le16(MSD_MPS),
		.bInterval = 0,
	},
	.if0_out_ep = {
		.bLength = sizeof(struct usb_ep_descriptor),
		.bDescriptorType = USB_DESC_ENDPOINT,
		.bEndpointAddress = 0x04,
		.bmAttributes = USB_EP_TYPE_BULK,
		.wMaxPacketSize = sys_cpu_to_le16(MSD_MPS),
		.bInterval = 0,
	},
};

static const struct usb_desc_header *const msd_fs_desc[] = {
	(struct usb_desc_header *)&msd_desc.if0,
	(struct usb_desc_header *)&msd_desc.if0_in_ep,
	(struct usb_desc_header *)&msd_desc.if0_out_ep,
	(struct usb_desc_header *)&msd_desc.nil_desc,
};

static struct {
	struct k_work_delayable work;
	struct k_spinlock lock;
	struct usbd_class_data *c_data;
	bool enabled;
	bool in_busy;
	bool out_busy;
	/* The IN stream: its length, bytes queued, a ZLP after it */
	uint32_t in_len;
	uint32_t in_sent;
	bool in_zlp;
	uint32_t stall_at;
	uint32_t out_recv;
	uint32_t out_bad;
	/* Packets per ms each way, 0 for no limit, and what is left of it */
	uint32_t rate;
	uint32_t in_budget;
	uint32_t out_budget;
	int64_t refilled;
} msd;

static uint8_t msd_pattern(const uint32_t i)
{
	return i ^ (i >> 8) ^ (i >> 16);
}

static uint8_t msd_ep_in(void)
{
	return msd_desc.if0_in_ep.bEndpointAddress;
}

static uint8_t msd_ep_out(void)
{
	return msd_desc.if0_out_ep.bEndpointAddress;
}

/* Bytes the rate lets through now, in whole packets */
static size_t msd_allowed(uint32_t *const budget, const size_t len)
{
	if (msd.rate == 0) {
		return len;
	}

	return MIN(len, *budget * MSD_MPS);
}

static void msd_work_handler(struct k_work *work)
{
	struct net_buf *in = NULL;
	struct net_buf *out = NULL;
	bool halt = false;
	k_spinlock_key_t key;
	size_t n;

	ARG_UNUSED(work);

	key = k_spin_lock(&msd.lock);
	if (!msd.enabled) {
		k_spin_unlock(&msd.lock, key);
		return;
	}

	if (msd.rate != 0 && k_uptime_get() > msd.refilled) {
		msd.refilled = k_uptime_get();
		msd.in_budget = MIN(msd.in_budget + msd.rate, 2 * msd.rate);
		msd.out_budget = MIN(msd.out_budget + msd.rate, 2 * msd.rate);
	}

	if (!msd.in_busy && msd.stall_at != 0 && msd.in_sent >= msd.stall_at) {
		msd.stall_at = 0;
		msd.in_len = msd.in_sent;
		halt = true;
	} else if (!msd.in_busy && msd.in_sent < msd.in_len) {
		n = MIN(msd.in_len - msd.in_sent, MSD_BUF_SIZE);
		if (msd.stall_at > msd.in_sent) {
			n = MIN(n, msd.stall_at - msd.in_sent);
		}

		n = msd_allowed(&msd.in_budget, n);
		if (n != 0) {
			in = usbd_ep_buf_alloc(msd.c_data, msd_ep_in(), n);
		}

		if (in != NULL) {
			for (size_t i = 0; i < n; i++) {
				net_buf_add_u8(in, msd_pattern(msd.in_sent + i));
			}

			msd.in_sent += n;
			msd.in_budget -= DIV_ROUND_UP(n, MSD_MPS) * (msd.rate != 0);
			msd.in_busy = true;
			if (msd.in_zlp && msd.in_sent == msd.in_len && n % MSD_MPS == 0) {
				udc_ep_buf_set_zlp(in);
			}
		}
	}

	if (!msd.out_busy) {
		n = msd_allowed(&msd.out_budget, MSD_BUF_SIZE);
		if (n != 0) {
			out = usbd_ep_buf_alloc(msd.c_data, msd_ep_out(), n);
		}

		if (out != NULL) {
			msd.out_budget -= DIV_ROUND_UP(n, MSD_MPS) * (msd.rate != 0);
			msd.out_busy = true;
		}
	}

	k_spin_unlock(&msd.lock, key);

	if (halt) {
		(void)usbd_ep_set_halt(usbd_class_get_ctx(msd.c_data), msd_ep_in());
	}

	if (in != NULL && usbd_ep_enqueue(msd.c_data, in) != 0) {
		net_buf_unref(in);
		msd.in_busy = false;
	}

	if (out != NULL && usbd_ep_enqueue(msd.c_data, out) != 0) {
		net_buf_unref(out);
		msd.out_busy = false;
	}

	k_work_reschedule(&msd.work, K_MSEC(1));
}

static int msd_request(struct usbd_class_data *const c_data, struct net_buf *const buf,
		       const int err)
{
	struct udc_buf_info *const bi = udc_get_buf_info(buf);
	k_spinlock_key_t key = k_spin_lock(&msd.lock);

	ARG_UNUSED(c_data);

	if (bi->ep == msd_ep_in()) {
		msd.in_busy = false;
	} else {
		if (err == 0) {
			for (size_t i = 0; i < buf->len; i++) {
				msd.out_bad += buf->data[i] != msd_pattern(msd.out_recv + i);
			}

			msd.out_recv += buf->len;
		}

		msd.out_busy = false;
	}

	k_spin_unlock(&msd.lock, key);
	net_buf_unref(buf);

	k_work_reschedule(&msd.work, K_NO_WAIT);

	return 0;
}

static const void *msd_get_desc(struct usbd_class_data *const c_data, const enum usbd_speed speed)
{
	ARG_UNUSED(c_data);
	ARG_UNUSED(speed);

	return msd_fs_desc;
}

static void msd_enable(struct usbd_class_data *const c_data)
{
	k_spinlock_key_t key = k_spin_lock(&msd.lock);

	msd.c_data = c_data;
	msd.enabled = true;
	msd.in_busy = false;
	msd.out_busy = false;
	k_spin_unlock(&msd.lock, key);

	k_work_reschedule(&msd.work, K_MSEC(1));
}

static void msd_disable(struct usbd_class_data *const c_data)
{
	k_spinlock_key_t key = k_spin_lock(&msd.lock);

	ARG_UNUSED(c_data);

	msd.enabled = false;
	k_spin_unlock(&msd.lock, key);
}

static void msd_reset(void)
{
	k_spinlock_key_t key = k_spin_lock(&msd.lock);
	const bool enabled = msd.enabled;

	msd.in_len = 0;
	msd.in_sent = 0;
	msd.in_zlp = false;
	msd.stall_at = 0;
	msd.out_recv = 0;
	msd.out_bad = 0;
	msd.rate = 0;
	k_spin_unlock(&msd.lock, key);

	/* What waits for the host goes too: the OUT buffer comes back */
	if (enabled) {
		struct usbd_context *const ctx = usbd_class_get_ctx(msd.c_data);

		(void)usbd_ep_dequeue(ctx, msd_ep_in());
		(void)usbd_ep_dequeue(ctx, msd_ep_out());
		(void)usbd_ep_clear_halt(ctx, msd_ep_in());
	}
}

static int msd_init(struct usbd_class_data *const c_data)
{
	ARG_UNUSED(c_data);

	k_work_init_delayable(&msd.work, msd_work_handler);

	return 0;
}

static const struct usbd_class_api msd_api = {
	.request = msd_request,
	.get_desc = msd_get_desc,
	.enable = msd_enable,
	.disable = msd_disable,
	.init = msd_init,
};

/* Named to come after the loopback and serial classes: its interface is the last */
USBD_DEFINE_CLASS(storage_emu, &msd_api, NULL, NULL);

static int msd_done(const struct shell *sh, size_t argc, char **argv, int ret)
{
	shell_fprintf(sh, SHELL_NORMAL, "SIM: msd");
	for (size_t i = 0; i < argc; i++) {
		shell_fprintf(sh, SHELL_NORMAL, " %s", argv[i]);
	}
	shell_fprintf(sh, SHELL_NORMAL, ": %d\n", ret);

	return ret;
}

static int cmd_msd_reset(const struct shell *sh, size_t argc, char **argv)
{
	msd_reset();

	return msd_done(sh, argc, argv, 0);
}

static int cmd_msd_in(const struct shell *sh, size_t argc, char **argv)
{
	k_spinlock_key_t key = k_spin_lock(&msd.lock);

	msd.in_len = strtoul(argv[1], NULL, 0);
	msd.in_sent = 0;
	msd.in_zlp = argc > 2 && strcmp(argv[2], "zlp") == 0;
	k_spin_unlock(&msd.lock, key);

	return msd_done(sh, argc, argv, 0);
}

static int cmd_msd_rate(const struct shell *sh, size_t argc, char **argv)
{
	msd.rate = strtoul(argv[1], NULL, 0);

	return msd_done(sh, argc, argv, 0);
}

static int cmd_msd_stall(const struct shell *sh, size_t argc, char **argv)
{
	msd.stall_at = strtoul(argv[1], NULL, 0);

	return msd_done(sh, argc, argv, 0);
}

static int cmd_msd_stats(const struct shell *sh, size_t argc, char **argv)
{
	k_spinlock_key_t key = k_spin_lock(&msd.lock);
	const uint32_t sent = msd.in_sent;
	const uint32_t recv = msd.out_recv;
	const uint32_t bad = msd.out_bad;

	k_spin_unlock(&msd.lock, key);

	shell_print(sh, "SIM: msd in %u out %u bad %u", sent, recv, bad);

	return msd_done(sh, argc, argv, 0);
}

SHELL_STATIC_SUBCMD_SET_CREATE(msd_cmds,
	SHELL_CMD_ARG(reset, NULL, "nothing to send, counters at 0", cmd_msd_reset, 1, 0),
	SHELL_CMD_ARG(in, NULL, "<len> [zlp]: an IN stream", cmd_msd_in, 2, 1),
	SHELL_CMD_ARG(rate, NULL, "<packets/ms>: 0 for no limit", cmd_msd_rate, 2, 0),
	SHELL_CMD_ARG(stall, NULL, "<offset>: halt IN there", cmd_msd_stall, 2, 0),
	SHELL_CMD_ARG(stats, NULL, "bytes sent, received, bad", cmd_msd_stats, 1, 0),
	SHELL_SUBCMD_SET_END
);

SHELL_CMD_REGISTER(msd, &msd_cmds, "mass-storage-like function on the virtual bus", NULL);
