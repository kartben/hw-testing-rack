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
	if (up.state == COPROC_UPLOAD_READY) {
		if (flash_area_open(AREA_ID, &up.fa) != 0 ||
		    flash_get_page_info_by_offs(flash_area_get_device(up.fa), up.fa->fa_off,
						&page) != 0 ||
		    flash_area_align(up.fa) > sizeof(up.tail)) {
			ret = fail("cannot open the coproc partition", why);
			k_mutex_unlock(&lock);
			return ret;
		}
		/* The old image goes now: its header is in the first sector */
		up.sector = page.size;
		up.erased = 0;
		up.off = sizeof(struct coproc_hdr);
		image.magic = 0;
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
		n += snprintf(buf + n, size - n, ",\"upload\":\"%s\",\"error\":%s%s%s}",
			      upload_str[up.state], up.error != NULL ? "\"" : "",
			      up.error != NULL ? up.error : "null", up.error != NULL ? "\"" : "");
	}
	k_mutex_unlock(&lock);

	return n >= 0 && (size_t)n < size ? n : -ENOMEM;
}
