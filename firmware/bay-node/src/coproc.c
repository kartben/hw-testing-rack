/*
 * The DATA x4 co-processor's image (U11, an RP2350B with no flash): kept in
 * the coproc flash partition, uploaded with the admin key (coproc_http.c,
 * bayctl coproc load) and loaded into the co-processor's SRAM whenever it
 * shows up in its ROM's USB bootloader.
 *
 * The partition holds a 64-byte header (struct coproc_hdr), then the bytes
 * that go to SRAM at the header's address.  bayctl makes both from the UF2 of
 * a no_flash build.  The header is written last, so a partition with a valid
 * header holds a whole image.  The image is not part of this firmware:
 * gusmanb's analyzer is GPL-3.0, the lab uploads the build config/rack.yaml
 * pins.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <stdio.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/drivers/flash.h>
#include <zephyr/init.h>
#include <zephyr/random/random.h>
#include <zephyr/storage/flash_map.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/logging/log.h>

#include <hwtr/acl.h>

#include "bay.h"

/* The loader, where the devicetree names the co-processor's hub port */
#if DT_NODE_HAS_STATUS_OKAY(DT_NODELABEL(coproc)) && defined(CONFIG_USB_HOST_STACK)
#define COPROC_LOADER 1
#include <zephyr/drivers/usb/uhc.h>
#include <zephyr/usb/usbh.h>
#include <usbh_class.h>
#include <usbh_desc.h>
#include <usbh_device.h>
#endif

LOG_MODULE_REGISTER(coproc, CONFIG_BAY_LOG_LEVEL);

#define AREA_ID    PARTITION_ID(coproc_partition)
#define AREA_SIZE  PARTITION_SIZE(coproc_partition)
#define TICKET_MS  60000
#define SRAM_START 0x20000000U
#define SRAM_END   0x20082000U /* the RP2350's 520 KB */

static K_MUTEX_DEFINE(lock);

/* The stored image's header, checked; magic 0 if there is none */
static struct coproc_hdr image;

/* The upload; the HTTP server delivers it from one thread */
static struct {
	enum coproc_upload_state state;
	uint8_t ticket[COPROC_TICKET_LEN];
	uint32_t ip;
	int64_t until;
	uint32_t size;
	uint32_t received;
	uint8_t sha[32];
	struct acl_sha256 hash;      /* of the whole upload */
	struct acl_sha256 body_hash; /* of the bytes after the header */
	struct coproc_hdr hdr;
	const struct flash_area *fa;
	uint32_t off;                /* where the next whole block goes */
	uint32_t erased;             /* the partition is erased below this */
	uint32_t sector;
	uint8_t tail[8];             /* bytes short of a whole write block */
	uint8_t tail_len;
	const char *error;
} up;

#if defined(COPROC_LOADER)

enum load_state {
	LD_IDLE,     /* not seen in its bootloader yet */
	LD_LOADING,
	LD_STARTED,  /* told to run the image: loaded unless it comes back at once */
	LD_LOADED,
	LD_FAILED,
	LD_LEFT,     /* failed too often: left to USB/IP (picotool from the lab) */
};

enum load_phase {
	PH_CMD,      /* the 32-byte command */
	PH_DATA,     /* what a WRITE writes */
	PH_ACK,      /* the bootloader's empty answer */
};

/* The load, driven by its transfers' completions */
static struct {
	enum load_state state;
	enum load_phase phase;
	struct usb_device *udev;
	struct uhc_transfer *xfer;   /* the one in flight */
	const struct flash_area *fa;
	struct acl_sha256 hash;      /* of what was sent, against the header's */
	uint8_t ep_out;
	uint8_t ep_in;
	uint8_t cmd;
	uint8_t fails;               /* in a row */
	uint32_t token;
	uint32_t off;
	uint32_t chunk;
	int64_t start;
	uint32_t loads;
	uint32_t failures;
	uint32_t last_ms;
	const char *error;
} ld;

static bool loading(void)
{
	return ld.state == LD_LOADING;
}

#else

static bool loading(void)
{
	return false;
}

#endif /* COPROC_LOADER */

/* A header's fields; its hash is checked against the bytes, elsewhere */
static const char *hdr_check(const struct coproc_hdr *h)
{
	uint32_t addr = sys_le32_to_cpu(h->addr), size = sys_le32_to_cpu(h->size);

	if (sys_le32_to_cpu(h->magic) != COPROC_MAGIC || sys_le16_to_cpu(h->version) != 1 ||
	    sys_le16_to_cpu(h->hdr_size) != sizeof(*h)) {
		return "not a co-processor image (make it with bayctl coproc load)";
	}
	if (sys_le32_to_cpu(h->family) != COPROC_FAMILY_RP2350_ARM_S) {
		return "not an RP2350 Arm image";
	}
	if (size == 0 || size > AREA_SIZE - sizeof(*h)) {
		return "image larger than the coproc partition";
	}
	if (addr % 4 != 0 || addr < SRAM_START || addr > SRAM_END - size) {
		return "image outside the RP2350's SRAM (a no_flash build is needed)";
	}

	return NULL;
}

static int coproc_init(void)
{
	const struct flash_area *fa;
	struct coproc_hdr h;

	if (flash_area_open(AREA_ID, &fa) != 0) {
		LOG_ERR("no coproc partition");
		return 0;
	}
	if (flash_area_read(fa, 0, &h, sizeof(h)) == 0 && hdr_check(&h) == NULL) {
		image = h;
		LOG_INF("co-processor image: %.*s, %u bytes at 0x%08x", (int)sizeof(h.name), h.name,
			sys_le32_to_cpu(h.size), sys_le32_to_cpu(h.addr));
	}
	flash_area_close(fa);

	return 0;
}

SYS_INIT(coproc_init, APPLICATION, 90);

/* --- Upload ----------------------------------------------------------------- */

static void reset_upload(enum coproc_upload_state state)
{
	if (up.fa != NULL) {
		flash_area_close(up.fa);
	}
	up.state = state;
	up.fa = NULL;
	up.received = 0;
	up.size = 0;
	up.until = 0;
	up.tail_len = 0;
}

int coproc_begin(uint32_t ip, uint32_t size, const uint8_t sha256[32],
		 char ticket_hex[COPROC_TICKET_HEX], const char **why)
{
	int64_t now = k_uptime_get();
	int ret = 0;

	k_mutex_lock(&lock, K_FOREVER);
	if (up.state == COPROC_UPLOAD_RECEIVING ||
	    (up.state == COPROC_UPLOAD_READY && up.until > now && up.ip != ip)) {
		*why = "another upload is on its way";
		ret = -EBUSY;
	} else if (loading()) {
		*why = "the co-processor is being loaded: try again in a few seconds";
		ret = -EBUSY;
	} else if (size <= sizeof(struct coproc_hdr) || size > AREA_SIZE) {
		*why = "size: larger than the coproc partition";
		ret = -EFBIG;
	}
	if (ret == 0) {
		if (sys_csrand_get(up.ticket, sizeof(up.ticket)) != 0) {
			sys_rand_get(up.ticket, sizeof(up.ticket));
		}
		reset_upload(COPROC_UPLOAD_READY);
		up.ip = ip;
		up.until = now + TICKET_MS;
		up.size = size;
		up.error = NULL;
		memcpy(up.sha, sha256, sizeof(up.sha));
		acl_hex_encode(up.ticket, sizeof(up.ticket), ticket_hex);
	}
	k_mutex_unlock(&lock);

	return ret;
}

static int fail(const char *why, const char **out)
{
	up.error = why;
	*out = why;
	reset_upload(COPROC_UPLOAD_IDLE);
	LOG_WRN("co-processor image refused: %s", why);
	return -EINVAL;
}

static bool ticket_ok(uint32_t ip, const char *ticket_hex)
{
	uint8_t ticket[COPROC_TICKET_LEN];

	return ticket_hex != NULL && acl_hex_decode(ticket_hex, ticket, sizeof(ticket)) == 0 &&
	       acl_equal(ticket, up.ticket, sizeof(ticket)) && up.ip == ip;
}

/* Whole write blocks at up.off, erasing the sectors ahead of them */
static int area_write(const uint8_t *data, size_t len)
{
	while (up.erased < up.off + len) {
		if (flash_area_erase(up.fa, up.erased, up.sector) != 0) {
			return -EIO;
		}
		up.erased += up.sector;
	}
	if (flash_area_write(up.fa, up.off, data, len) != 0) {
		return -EIO;
	}
	up.off += len;

	return 0;
}

/* The bytes after the header: whole blocks to flash, the rest kept for the next call */
static int body_write(const uint8_t *data, size_t len)
{
	size_t align = flash_area_align(up.fa);
	size_t n;

	acl_sha256_update(&up.body_hash, data, len);
	if (up.tail_len > 0) {
		n = MIN(len, align - up.tail_len);
		memcpy(up.tail + up.tail_len, data, n);
		up.tail_len += n;
		data += n;
		len -= n;
		if (up.tail_len < align) {
			return 0;
		}
		if (area_write(up.tail, align) != 0) {
			return -EIO;
		}
		up.tail_len = 0;
	}
	n = len - len % align;
	if (n > 0 && area_write(data, n) != 0) {
		return -EIO;
	}
	memcpy(up.tail, data + n, len - n);
	up.tail_len = len - n;

	return 0;
}

int coproc_write(uint32_t ip, const char *ticket_hex, const uint8_t *data, size_t len,
		 const char **why)
{
	struct flash_pages_info page;
	size_t n;
	int ret = 0;

	k_mutex_lock(&lock, K_FOREVER);
	if ((up.state != COPROC_UPLOAD_READY && up.state != COPROC_UPLOAD_RECEIVING) ||
	    !ticket_ok(ip, ticket_hex) ||
	    (up.state == COPROC_UPLOAD_READY && k_uptime_get() > up.until)) {
		*why = "no such ticket: begin again";
		k_mutex_unlock(&lock);
		return -EPERM;
	}
	/* A load started after the ticket: it reads the partition, the ticket waits */
	if (up.state == COPROC_UPLOAD_READY && loading()) {
		*why = "the co-processor is being loaded: try again in a few seconds";
		k_mutex_unlock(&lock);
		return -EBUSY;
	}
	if (up.state == COPROC_UPLOAD_READY) {
		if (flash_area_open(AREA_ID, &up.fa) != 0 ||
		    flash_get_page_info_by_offs(flash_area_get_device(up.fa), up.fa->fa_off,
						&page) != 0 ||
		    flash_area_align(up.fa) > sizeof(up.tail)) {
			ret = fail("cannot open the coproc partition", why);
			k_mutex_unlock(&lock);
			return ret;
		}
		/* The old image goes now, from RAM and flash: its header is in the first sector */
		up.sector = page.size;
		up.erased = 0;
		up.off = sizeof(struct coproc_hdr);
		image.magic = 0;
		if (flash_area_erase(up.fa, 0, up.sector) != 0) {
			ret = fail("flash erase failed", why);
			k_mutex_unlock(&lock);
			return ret;
		}
		up.erased = up.sector;
		acl_sha256_init(&up.hash);
		acl_sha256_init(&up.body_hash);
		up.state = COPROC_UPLOAD_RECEIVING;
		LOG_INF("receiving a co-processor image, %u bytes", up.size);
	}

	if (up.received + len > up.size) {
		ret = fail("more bytes than announced", why);
		goto out;
	}
	acl_sha256_update(&up.hash, data, len);
	/* The header stays in RAM until the image is whole */
	if (up.received < sizeof(up.hdr)) {
		n = MIN(len, sizeof(up.hdr) - up.received);
		memcpy((uint8_t *)&up.hdr + up.received, data, n);
		up.received += n;
		data += n;
		len -= n;
		if (up.received == sizeof(up.hdr) && hdr_check(&up.hdr) != NULL) {
			ret = fail(hdr_check(&up.hdr), why);
			goto out;
		}
	}
	if (len > 0) {
		if (body_write(data, len) != 0) {
			ret = fail("flash write failed", why);
			goto out;
		}
		up.received += len;
	}
out:
	k_mutex_unlock(&lock);

	return ret;
}

int coproc_finish(const char **why)
{
	uint8_t sha[32];
	int ret = 0;

	k_mutex_lock(&lock, K_FOREVER);
	if (up.state != COPROC_UPLOAD_RECEIVING) {
		*why = "no upload";
		k_mutex_unlock(&lock);
		return -EPERM;
	}
	if (up.received != up.size) {
		ret = fail("fewer bytes than announced", why);
		goto out;
	}
	acl_sha256_final(&up.hash, sha);
	if (!acl_equal(sha, up.sha, sizeof(sha))) {
		ret = fail("SHA-256 does not match", why);
		goto out;
	}
	if (up.size - sizeof(up.hdr) != sys_le32_to_cpu(up.hdr.size)) {
		ret = fail("the header's size is not the image's", why);
		goto out;
	}
	acl_sha256_final(&up.body_hash, sha);
	if (!acl_equal(sha, up.hdr.sha256, sizeof(sha))) {
		ret = fail("the header's SHA-256 is not the image's", why);
		goto out;
	}
	/* The last partial block, padded as erased flash, then the header */
	if (up.tail_len > 0) {
		memset(up.tail + up.tail_len, 0xff, sizeof(up.tail) - up.tail_len);
		if (area_write(up.tail, flash_area_align(up.fa)) != 0) {
			ret = fail("flash write failed", why);
			goto out;
		}
	}
	if (flash_area_write(up.fa, 0, &up.hdr, sizeof(up.hdr)) != 0) {
		ret = fail("flash write failed", why);
		goto out;
	}
	image = up.hdr;
	up.error = NULL;
	reset_upload(COPROC_UPLOAD_IDLE);
#if defined(COPROC_LOADER)
	/* A new image gets its tries again */
	ld.fails = 0;
#endif
	LOG_INF("co-processor image stored: %.*s, %u bytes", (int)sizeof(image.name), image.name,
		sys_le32_to_cpu(image.size));
out:
	k_mutex_unlock(&lock);

	return ret;
}

void coproc_abort(const char *why)
{
	k_mutex_lock(&lock, K_FOREVER);
	if (up.state == COPROC_UPLOAD_RECEIVING) {
		up.error = why;
		reset_upload(COPROC_UPLOAD_IDLE);
		LOG_WRN("co-processor upload stopped: %s", why);
	}
	k_mutex_unlock(&lock);
}

#if defined(COPROC_LOADER)

/* --- Loader ----------------------------------------------------------------- */

/*
 * The co-processor's ROM shows up as 2e8a:000f with a PICOBOOT interface (a
 * vendor interface with a bulk OUT and a bulk IN endpoint, RP2350 datasheet
 * 5.6).  The node does what picotool load -x does for an image in SRAM:
 * EXCLUSIVE_ACCESS, WRITE the image in chunks, then REBOOT2 into the RAM
 * image.  Each command is 32 bytes OUT, then its data OUT, then an empty IN
 * as the bootloader's acknowledgment.  The chunks come from the host
 * controller's own buffers, read from flash as they go: no buffer of our own.
 * This class sorts before USB/IP's, so the device is not exported while it
 * is loaded; a device it leaves (no image, too many failures) is.
 */

#define HUB_PORT	   DT_PROP(DT_NODELABEL(coproc), hub_port)
#define CHUNK		   1024
#define REBOOT_DELAY_MS	   500
#define MAX_FAILS	   2
/* Tests shorten these */
#ifndef COPROC_LOAD_TIMEOUT_MS
#define COPROC_LOAD_TIMEOUT_MS 10000
#endif
/* Back in its bootloader within this after a load: the image did not start */
#ifndef COPROC_SETTLE_MS
#define COPROC_SETTLE_MS 10000
#endif

#define PICOBOOT_MAGIC	    0x431fd10bU
#define PC_EXCLUSIVE_ACCESS 0x01
#define PC_WRITE	    0x05
#define PC_REBOOT2	    0x0a
#define EXCLUSIVE	    1
#define REBOOT2_RAM_IMAGE   0x3

struct picoboot_cmd {
	uint32_t magic;
	uint32_t token;
	uint8_t id;
	uint8_t args_len;
	uint16_t unused;
	uint32_t transfer_len;
	uint8_t args[16];
} __packed;

BUILD_ASSERT(sizeof(struct picoboot_cmd) == 32);

static void start_handler(struct k_work *work);
static void timeout_handler(struct k_work *work);
static void settle_handler(struct k_work *work);
static K_WORK_DEFINE(start_work, start_handler);
static K_WORK_DELAYABLE_DEFINE(timeout_work, timeout_handler);
static K_WORK_DELAYABLE_DEFINE(settle_work, settle_handler);

static void load_fail(const char *why)
{
	ld.state = LD_FAILED;
	ld.error = why;
	ld.failures++;
	ld.fails++;
	if (ld.fa != NULL) {
		flash_area_close(ld.fa);
		ld.fa = NULL;
	}
	(void)k_work_cancel_delayable(&timeout_work);
	LOG_ERR("co-processor not loaded: %s", why);
}

static int xfer_cb(struct usb_device *const udev, struct uhc_transfer *const xfer);

static void submit(uint8_t ep, struct net_buf *buf, enum load_phase phase)
{
	struct uhc_transfer *xfer;

	if (buf == NULL) {
		load_fail("no USB buffer free");
		return;
	}
	xfer = usbh_xfer_alloc(ld.udev, ep, xfer_cb, NULL);
	if (xfer == NULL) {
		net_buf_unref(buf);
		load_fail("no USB transfer free");
		return;
	}
	if (usbh_xfer_buf_add(ld.udev, xfer, buf) != 0 || usbh_xfer_enqueue(ld.udev, xfer) != 0) {
		net_buf_unref(buf);
		(void)uhc_xfer_unref(xfer);
		load_fail("USB transfer refused");
		return;
	}
	ld.phase = phase;
	ld.xfer = xfer;
}

static void send_cmd(uint8_t id, const void *args, uint8_t args_len, uint32_t transfer_len)
{
	struct net_buf *buf = usbh_xfer_buf_alloc(ld.udev, sizeof(struct picoboot_cmd));
	struct picoboot_cmd *c;

	if (buf != NULL) {
		c = net_buf_add(buf, sizeof(*c));
		memset(c, 0, sizeof(*c));
		c->magic = sys_cpu_to_le32(PICOBOOT_MAGIC);
		c->token = sys_cpu_to_le32(++ld.token);
		c->id = id;
		c->args_len = args_len;
		c->transfer_len = sys_cpu_to_le32(transfer_len);
		memcpy(c->args, args, args_len);
	}
	ld.cmd = id;
	submit(ld.ep_out, buf, PH_CMD);
}

static void send_write(void)
{
	uint32_t args[2];

	ld.chunk = MIN(CHUNK, sys_le32_to_cpu(image.size) - ld.off);
	args[0] = sys_cpu_to_le32(sys_le32_to_cpu(image.addr) + ld.off);
	args[1] = sys_cpu_to_le32(ld.chunk);
	send_cmd(PC_WRITE, args, sizeof(args), ld.chunk);
}

static void send_data(void)
{
	struct net_buf *buf = usbh_xfer_buf_alloc(ld.udev, ld.chunk);
	uint8_t *p;

	if (buf != NULL) {
		p = net_buf_add(buf, ld.chunk);
		if (flash_area_read(ld.fa, sizeof(struct coproc_hdr) + ld.off, p, ld.chunk) != 0) {
			net_buf_unref(buf);
			load_fail("flash read failed");
			return;
		}
		acl_sha256_update(&ld.hash, p, ld.chunk);
	}
	submit(ld.ep_out, buf, PH_DATA);
}

static void send_ack(void)
{
	submit(ld.ep_in, usbh_xfer_buf_alloc(ld.udev, 64), PH_ACK);
}

/* The bootloader acknowledged ld.cmd: the next one */
static void next_cmd(void)
{
	uint32_t addr = sys_le32_to_cpu(image.addr);
	uint32_t args[4];
	uint8_t sha[32];

	switch (ld.cmd) {
	case PC_EXCLUSIVE_ACCESS:
		send_write();
		break;
	case PC_WRITE:
		ld.off += ld.chunk;
		if (ld.off < sys_le32_to_cpu(image.size)) {
			send_write();
			break;
		}
		acl_sha256_final(&ld.hash, sha);
		if (!acl_equal(sha, image.sha256, sizeof(sha))) {
			load_fail("the image in flash is not the one stored (SHA-256)");
			break;
		}
		/* Run what is in SRAM from addr to its end (picotool's region) */
		args[0] = sys_cpu_to_le32(REBOOT2_RAM_IMAGE);
		args[1] = sys_cpu_to_le32(REBOOT_DELAY_MS);
		args[2] = sys_cpu_to_le32(addr);
		args[3] = sys_cpu_to_le32(SRAM_END - addr);
		send_cmd(PC_REBOOT2, args, sizeof(args), 0);
		break;
	default:
		ld.state = LD_STARTED;
		ld.error = NULL;
		ld.last_ms = k_uptime_get() - ld.start;
		ld.loads++;
		flash_area_close(ld.fa);
		ld.fa = NULL;
		(void)k_work_cancel_delayable(&timeout_work);
		k_work_schedule(&settle_work, K_MSEC(COPROC_SETTLE_MS));
		LOG_INF("co-processor loaded: %u bytes in %u ms", sys_le32_to_cpu(image.size),
			ld.last_ms);
		break;
	}
}

static int xfer_cb(struct usb_device *const udev, struct uhc_transfer *const xfer)
{
	struct net_buf *const buf = xfer->buf;
	const int err = xfer->err;
	const size_t len = buf != NULL ? buf->len : 0;

	k_mutex_lock(&lock, K_FOREVER);
	if (ld.xfer == xfer) {
		ld.xfer = NULL;
	}
	if (udev == ld.udev && ld.state == LD_LOADING) {
		if (err != 0) {
			load_fail(err == -EPIPE ? "the bootloader refused a command (stall)"
						: "USB transfer failed");
		} else if (ld.phase == PH_CMD) {
			if (ld.cmd == PC_WRITE) {
				send_data();
			} else {
				send_ack();
			}
		} else if (ld.phase == PH_DATA) {
			send_ack();
		} else if (len != 0) {
			load_fail("the bootloader answered with data");
		} else {
			next_cmd();
		}
	}
	k_mutex_unlock(&lock);

	if (buf != NULL) {
		net_buf_unref(buf);
	}
	(void)uhc_xfer_unref(xfer);

	return 0;
}

static void start_handler(struct k_work *work)
{
	const uint8_t exclusive = EXCLUSIVE;

	ARG_UNUSED(work);

	k_mutex_lock(&lock, K_FOREVER);
	if (ld.state == LD_LOADING && ld.udev != NULL) {
		if (flash_area_open(AREA_ID, &ld.fa) != 0) {
			load_fail("no coproc partition");
		} else {
			acl_sha256_init(&ld.hash);
			ld.off = 0;
			k_work_schedule(&timeout_work, K_MSEC(COPROC_LOAD_TIMEOUT_MS));
			send_cmd(PC_EXCLUSIVE_ACCESS, &exclusive, sizeof(exclusive), 0);
		}
	}
	k_mutex_unlock(&lock);
}

static void timeout_handler(struct k_work *work)
{
	ARG_UNUSED(work);

	/* Under the lock the transfer is still ours: its completion waits for it */
	k_mutex_lock(&lock, K_FOREVER);
	if (ld.state == LD_LOADING) {
		load_fail("the bootloader stopped answering");
		if (ld.xfer != NULL && ld.udev != NULL) {
			(void)usbh_xfer_dequeue(ld.udev, ld.xfer);
		}
	}
	k_mutex_unlock(&lock);
}

static void settle_handler(struct k_work *work)
{
	ARG_UNUSED(work);

	k_mutex_lock(&lock, K_FOREVER);
	if (ld.state == LD_STARTED) {
		ld.state = LD_LOADED;
		ld.fails = 0;
	}
	k_mutex_unlock(&lock);
}

/* The PICOBOOT interface's bulk endpoints */
static bool find_endpoints(struct usb_device *const udev)
{
	const struct usb_desc_header *h = udev->cfg_desc;
	bool vendor = false;

	ld.ep_out = 0;
	ld.ep_in = 0;
	while ((h = usbh_desc_get_next(h)) != NULL) {
		if (h->bDescriptorType == USB_DESC_INTERFACE && usbh_desc_is_valid_interface(h)) {
			vendor = ((const struct usb_if_descriptor *)h)->bInterfaceClass ==
				 USB_BCC_VENDOR;
		} else if (vendor && h->bDescriptorType == USB_DESC_ENDPOINT &&
			   usbh_desc_is_valid_endpoint(h)) {
			const struct usb_ep_descriptor *e = (const struct usb_ep_descriptor *)h;

			if ((e->bmAttributes & USB_EP_TRANSFER_TYPE_MASK) != USB_EP_TYPE_BULK) {
				continue;
			}
			if (USB_EP_DIR_IS_IN(e->bEndpointAddress)) {
				ld.ep_in = e->bEndpointAddress;
			} else {
				ld.ep_out = e->bEndpointAddress;
			}
		}
	}

	return ld.ep_in != 0 && ld.ep_out != 0;
}

static int coproc_class_init(struct usbh_class_data *const c_data)
{
	ARG_UNUSED(c_data);

	return 0;
}

static int coproc_class_probe(struct usbh_class_data *const c_data, struct usb_device *const udev,
			      const uint8_t iface)
{
	bool here;
	int ret = -ENOTSUP;

	ARG_UNUSED(c_data);

	/* Only the co-processor: an RP2350 board under test in BOOTSEL is USB/IP's */
	here = HUB_PORT == 0 ? udev->hub == NULL
			     : udev->hub != NULL && udev->hub->hub == NULL &&
				       udev->hub_port == HUB_PORT;
	if (iface != USBH_CLASS_IFNUM_DEVICE || !here) {
		return -ENOTSUP;
	}

	k_mutex_lock(&lock, K_FOREVER);
	if (ld.state == LD_STARTED) {
		(void)k_work_cancel_delayable(&settle_work);
		load_fail("back in its bootloader right after the load: the image did not start");
	}
	if (image.magic == 0) {
		LOG_INF("co-processor in its bootloader, no image: left to USB/IP");
	} else if (ld.fails >= MAX_FAILS) {
		ld.state = LD_LEFT;
		LOG_WRN("co-processor: %u loads failed in a row, left to USB/IP", ld.fails);
	} else if (!find_endpoints(udev)) {
		load_fail("no PICOBOOT interface");
	} else {
		ld.udev = udev;
		ld.state = LD_LOADING;
		ld.start = k_uptime_get();
		k_work_submit(&start_work);
		ret = 0;
	}
	k_mutex_unlock(&lock);

	return ret;
}

static int coproc_class_removed(struct usbh_class_data *const c_data)
{
	k_mutex_lock(&lock, K_FOREVER);
	if (c_data->udev == ld.udev) {
		if (ld.state == LD_LOADING) {
			load_fail("the co-processor went away while loading");
		}
		ld.udev = NULL;
		ld.xfer = NULL;
	}
	k_mutex_unlock(&lock);

	return 0;
}

static struct usbh_class_api coproc_class_api = {
	.init = coproc_class_init,
	.probe = coproc_class_probe,
	.removed = coproc_class_removed,
};

static const struct usbh_class_filter coproc_filters[] = {
	{.vid = 0x2e8a, .pid = 0x000f, .flags = USBH_CLASS_MATCH_VID_PID},
	{0},
};

/* Named to sort before usbip_*: the first class that takes a device keeps it */
USBH_DEFINE_CLASS(coproc, &coproc_class_api, NULL, coproc_filters);

#endif /* COPROC_LOADER */

/* --- State ------------------------------------------------------------------ */

/* The stored image's name, printable, NUL-terminated */
static void image_name(const struct coproc_hdr *h, char out[sizeof(h->name) + 1])
{
	size_t i;

	for (i = 0; i < sizeof(h->name) && h->name[i] != '\0'; i++) {
		out[i] = h->name[i] >= ' ' && h->name[i] < 0x7f && h->name[i] != '"' &&
				 h->name[i] != '\\' ? h->name[i] : '?';
	}
	out[i] = '\0';
}

int coproc_image_info(char *name, size_t name_len, uint32_t *size, uint32_t *addr)
{
	char n[sizeof(image.name) + 1];
	int ret = -ENOENT;

	k_mutex_lock(&lock, K_FOREVER);
	if (image.magic != 0) {
		image_name(&image, n);
		snprintf(name, name_len, "%s", n);
		*size = sys_le32_to_cpu(image.size);
		*addr = sys_le32_to_cpu(image.addr);
		ret = 0;
	}
	k_mutex_unlock(&lock);

	return ret;
}

int coproc_json(char *buf, size_t size)
{
	static const char *const upload_str[] = {"idle", "ready", "receiving"};
	char name[sizeof(image.name) + 1];
	char sha[2 * 32 + 1];
	int n;

	k_mutex_lock(&lock, K_FOREVER);
	if (image.magic != 0) {
		image_name(&image, name);
		acl_hex_encode(image.sha256, sizeof(image.sha256), sha);
		n = snprintf(buf, size,
			     "{\"image\":{\"name\":\"%s\",\"size\":%u,\"addr\":\"0x%08x\","
			     "\"sha256\":\"%s\"}",
			     name, sys_le32_to_cpu(image.size), sys_le32_to_cpu(image.addr), sha);
	} else {
		n = snprintf(buf, size, "{\"image\":null");
	}
	if (n >= 0 && (size_t)n < size) {
		n += snprintf(buf + n, size - n, ",\"upload\":\"%s\",\"error\":%s%s%s",
			      upload_str[up.state], up.error != NULL ? "\"" : "",
			      up.error != NULL ? up.error : "null", up.error != NULL ? "\"" : "");
	}
#if defined(COPROC_LOADER)
	static const char *const load_str[] = {"idle",   "loading", "started",
					       "loaded", "failed",  "left to USB/IP"};

	if (n >= 0 && (size_t)n < size) {
		n += snprintf(buf + n, size - n,
			      ",\"load\":{\"state\":\"%s\",\"loads\":%u,\"failures\":%u,"
			      "\"last_ms\":%u,\"error\":%s%s%s}",
			      load_str[ld.state], ld.loads, ld.failures, ld.last_ms,
			      ld.error != NULL ? "\"" : "", ld.error != NULL ? ld.error : "null",
			      ld.error != NULL ? "\"" : "");
	}
#endif
	if (n >= 0 && (size_t)n < size) {
		n += snprintf(buf + n, size - n, "}");
	}
	k_mutex_unlock(&lock);

	return n >= 0 && (size_t)n < size ? n : -ENOMEM;
}
