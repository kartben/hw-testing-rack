/*
 * An MCUboot image read as it streams in (include/hwtr/mcuboot_img.h).
 *
 *   0                 header: magic, load address, header size, protected
 *                     TLV size, code size, flags, version (32 bytes, then
 *                     padding up to the header size)
 *   hdr_size          the code
 *   + img_size        protected TLVs: info (0x6908, total), then type/length/
 *                     value entries; the image id is one of them (0xa0)
 *   + prot_size       TLVs: info (0x6907, total), hash and signature
 *
 * Little-endian, as imgtool writes it for the ESP32-S3.  Only what the
 * update needs is kept: the header, the protected TLVs (up to
 * HWTR_IMG_PROT_MAX bytes) and the second TLV info, for the image's length.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdio.h>
#include <string.h>

#include <hwtr/mcuboot_img.h>

static uint16_t get16(const uint8_t *p)
{
	return (uint16_t)(p[0] | (p[1] << 8));
}

static uint32_t get32(const uint8_t *p)
{
	return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) |
	       ((uint32_t)p[3] << 24);
}

/* Copy the part of [at, at + len) that falls in [start, start + size) to dst */
static void keep(uint8_t *dst, uint32_t start, uint32_t size, uint32_t at, const uint8_t *data,
		 size_t len)
{
	uint32_t from = at > start ? at : start;
	uint32_t to = at + len < start + size ? at + (uint32_t)len : start + size;

	if (from < to) {
		memcpy(dst + (from - start), data + (from - at), to - from);
	}
}

void hwtr_img_init(struct hwtr_img_parser *p)
{
	memset(p, 0, sizeof(*p));
}

static void parse_header(struct hwtr_img_parser *p)
{
	struct hwtr_img_info *i = &p->info;

	if (get32(p->hdr) != HWTR_IMG_MAGIC) {
		p->err = HWTR_IMG_NOT_MCUBOOT;
		return;
	}
	i->hdr_size = get16(p->hdr + 8);
	p->prot_size = get16(p->hdr + 10);
	i->img_size = get32(p->hdr + 12);
	i->major = p->hdr[20];
	i->minor = p->hdr[21];
	i->revision = get16(p->hdr + 22);
	i->build = get32(p->hdr + 24);
	if (i->hdr_size < HWTR_IMG_HEADER_SIZE || i->img_size == 0 ||
	    i->img_size > 0x1000000U || (p->prot_size != 0 && p->prot_size < 4)) {
		p->err = HWTR_IMG_BAD_HEADER;
		return;
	}
	p->prot_off = i->hdr_size + i->img_size;
	p->tlv_off = p->prot_off + p->prot_size;
}

void hwtr_img_feed(struct hwtr_img_parser *p, const uint8_t *data, size_t len)
{
	uint32_t at = p->pos;

	if (p->err != HWTR_IMG_OK || len == 0) {
		return;
	}
	p->pos += (uint32_t)len;

	if (at < HWTR_IMG_HEADER_SIZE) {
		keep(p->hdr, 0, HWTR_IMG_HEADER_SIZE, at, data, len);
		if (p->pos < HWTR_IMG_HEADER_SIZE) {
			return;
		}
		parse_header(p);
		if (p->err != HWTR_IMG_OK) {
			return;
		}
	}
	keep(p->prot, p->prot_off,
	     p->prot_size < HWTR_IMG_PROT_MAX ? p->prot_size : HWTR_IMG_PROT_MAX, at, data, len);
	keep(p->tlv_info, p->tlv_off, sizeof(p->tlv_info), at, data, len);

	if (p->total == 0 && p->pos >= p->tlv_off + sizeof(p->tlv_info)) {
		if (get16(p->tlv_info) != HWTR_IMG_TLV_INFO || get16(p->tlv_info + 2) < 4) {
			p->err = HWTR_IMG_BAD_TLV;
			return;
		}
		p->total = p->tlv_off + get16(p->tlv_info + 2);
	}
	if (p->total != 0 && p->pos > p->total) {
		p->err = HWTR_IMG_TOO_LONG;
	}
}

bool hwtr_img_header(const struct hwtr_img_parser *p, struct hwtr_img_info *info)
{
	if (p->pos < HWTR_IMG_HEADER_SIZE || p->err == HWTR_IMG_NOT_MCUBOOT ||
	    p->err == HWTR_IMG_BAD_HEADER) {
		return false;
	}
	*info = p->info;
	return true;
}

/* The image id among the protected TLVs */
static enum hwtr_img_err find_id(struct hwtr_img_parser *p)
{
	uint32_t kept = p->prot_size < HWTR_IMG_PROT_MAX ? p->prot_size : HWTR_IMG_PROT_MAX;
	uint32_t off = 4;

	if (p->prot_size == 0) {
		return HWTR_IMG_NO_ID;
	}
	if (get16(p->prot) != HWTR_IMG_TLV_PROT_INFO || get16(p->prot + 2) != p->prot_size) {
		return HWTR_IMG_BAD_TLV;
	}
	while (off + 4 <= kept) {
		uint16_t type = get16(p->prot + off);
		uint16_t len = get16(p->prot + off + 2);

		off += 4;
		if (off + len > p->prot_size) {
			return HWTR_IMG_BAD_TLV;
		}
		if (type == HWTR_IMG_TLV_ID) {
			if (len == 0 || len > HWTR_IMG_ID_MAX || off + len > kept) {
				return HWTR_IMG_BAD_TLV;
			}
			for (uint16_t i = 0; i < len; i++) {
				uint8_t c = p->prot[off + i];

				if (c < 0x20 || c > 0x7e) {
					return HWTR_IMG_BAD_TLV;
				}
			}
			memcpy(p->info.id, p->prot + off, len);
			p->info.id[len] = '\0';
			return HWTR_IMG_OK;
		}
		off += len;
	}

	return HWTR_IMG_NO_ID;
}

enum hwtr_img_err hwtr_img_finish(struct hwtr_img_parser *p, struct hwtr_img_info *info)
{
	if (p->err == HWTR_IMG_OK && p->pos < HWTR_IMG_HEADER_SIZE) {
		/* Too short for a header: say "not an image" when the magic is wrong already */
		uint8_t magic[4] = {0x3d, 0xb8, 0xf3, 0x96};

		p->err = memcmp(p->hdr, magic, p->pos < 4 ? p->pos : 4) != 0 || p->pos == 0
				 ? HWTR_IMG_NOT_MCUBOOT
				 : HWTR_IMG_TRUNCATED;
	}
	if (p->err == HWTR_IMG_OK && (p->total == 0 || p->pos < p->total)) {
		p->err = HWTR_IMG_TRUNCATED;
	}
	if (p->err == HWTR_IMG_OK) {
		p->err = find_id(p);
	}
	p->info.total = p->total;
	if (info != NULL) {
		*info = p->info;
	}
	return p->err;
}

const char *hwtr_img_strerror(enum hwtr_img_err err)
{
	switch (err) {
	case HWTR_IMG_OK:
		return "ok";
	case HWTR_IMG_NOT_MCUBOOT:
		return "not a signed image (upload zephyr.signed.bin from a --sysbuild build)";
	case HWTR_IMG_BAD_HEADER:
		return "bad image header";
	case HWTR_IMG_TRUNCATED:
		return "image truncated";
	case HWTR_IMG_TOO_LONG:
		return "bytes after the end of the image";
	case HWTR_IMG_BAD_TLV:
		return "bad image TLVs";
	case HWTR_IMG_NO_ID:
		return "no image id: not built by this repository (firmware/common/sysbuild.cmake)";
	}
	return "?";
}

void hwtr_img_version(const struct hwtr_img_info *info, char *out, size_t size)
{
	if (info->build != 0) {
		snprintf(out, size, "%u.%u.%u+%u", info->major, info->minor, info->revision,
			 (unsigned int)info->build);
	} else {
		snprintf(out, size, "%u.%u.%u", info->major, info->minor, info->revision);
	}
}
