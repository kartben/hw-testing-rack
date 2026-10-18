/*
 * An MCUboot image read as it streams in: its header (version, sizes) and
 * the protected TLV that says which application and board it is for.
 *
 * Plain C, no Zephyr: the update code feeds it the upload chunk by chunk
 * (firmware/common/lib/update.c) and the host test feeds it built images.
 *
 * The image id is a custom TLV (0xa0, in the vendor range) that the build
 * adds to the signed image, "<application>/<board>" (bay-node/bay_node,
 * power-hub/power_hub; firmware/common/sysbuild.cmake).  It sits in the
 * protected TLV area, so MCUboot's signature covers it.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef HWTR_MCUBOOT_IMG_H_
#define HWTR_MCUBOOT_IMG_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define HWTR_IMG_MAGIC          0x96f3b83dU
#define HWTR_IMG_TLV_INFO       0x6907U
#define HWTR_IMG_TLV_PROT_INFO  0x6908U
#define HWTR_IMG_HEADER_SIZE    32U

/* The custom TLV with the image id */
#define HWTR_IMG_TLV_ID         0x00a0U
#define HWTR_IMG_ID_MAX         47

/* Protected TLVs kept for parsing (the id, a security counter...) */
#define HWTR_IMG_PROT_MAX       128U

struct hwtr_img_info {
	uint8_t major;
	uint8_t minor;
	uint16_t revision;
	uint32_t build;
	uint32_t hdr_size;
	uint32_t img_size;
	uint32_t total;                  /* header, code and both TLV areas */
	char id[HWTR_IMG_ID_MAX + 1];    /* "" when the image has none */
};

enum hwtr_img_err {
	HWTR_IMG_OK = 0,
	HWTR_IMG_NOT_MCUBOOT,            /* no image magic: not a signed image */
	HWTR_IMG_BAD_HEADER,
	HWTR_IMG_TRUNCATED,
	HWTR_IMG_TOO_LONG,               /* bytes after the TLVs */
	HWTR_IMG_BAD_TLV,
	HWTR_IMG_NO_ID,                  /* signed, but not by this repository's build */
};

struct hwtr_img_parser {
	uint32_t pos;
	uint8_t hdr[HWTR_IMG_HEADER_SIZE];
	uint8_t prot[HWTR_IMG_PROT_MAX];
	uint8_t tlv_info[4];
	uint32_t prot_off;               /* offset of the protected TLV area */
	uint32_t prot_size;
	uint32_t tlv_off;                /* offset of the unprotected TLV area */
	uint32_t total;                  /* known once the TLV info has passed */
	enum hwtr_img_err err;
	struct hwtr_img_info info;
};

void hwtr_img_init(struct hwtr_img_parser *p);

/* The next bytes of the image, in order */
void hwtr_img_feed(struct hwtr_img_parser *p, const uint8_t *data, size_t len);

/* After the last byte: HWTR_IMG_OK and *info, or the first problem met */
enum hwtr_img_err hwtr_img_finish(struct hwtr_img_parser *p, struct hwtr_img_info *info);

/* The header alone is enough for the version and sizes: true once it has passed */
bool hwtr_img_header(const struct hwtr_img_parser *p, struct hwtr_img_info *info);

const char *hwtr_img_strerror(enum hwtr_img_err err);

/* "0.6.0" or "0.6.0+3" */
void hwtr_img_version(const struct hwtr_img_info *info, char *out, size_t size);

#endif /* HWTR_MCUBOOT_IMG_H_ */
