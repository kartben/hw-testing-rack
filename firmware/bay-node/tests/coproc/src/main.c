/*
 * The co-processor's image (src/coproc.c): uploads into the coproc
 * partition, whole and refused, on the flash simulator.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/storage/flash_map.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/ztest.h>

#include <hwtr/acl.h>

#include "bay.h"

#define IP	  0x0a000001U
#define BODY_SIZE 6001 /* not a whole number of write blocks */

static uint8_t image[sizeof(struct coproc_hdr) + BODY_SIZE];

/* A header and a body for SRAM at addr; the body's hash in the header */
static size_t make_image(uint32_t addr, uint32_t body_size)
{
	struct coproc_hdr *h = (struct coproc_hdr *)image;
	struct acl_sha256 c;

	memset(h, 0, sizeof(*h));
	for (uint32_t i = 0; i < body_size; i++) {
		image[sizeof(*h) + i] = (uint8_t)(i * 7 + (i >> 8));
	}
	h->magic = sys_cpu_to_le32(COPROC_MAGIC);
	h->version = sys_cpu_to_le16(1);
	h->hdr_size = sys_cpu_to_le16(sizeof(*h));
	h->family = sys_cpu_to_le32(COPROC_FAMILY_RP2350_ARM_S);
	h->addr = sys_cpu_to_le32(addr);
	h->size = sys_cpu_to_le32(body_size);
	memcpy(h->name, "test 1.0", 8);
	acl_sha256_init(&c);
	acl_sha256_update(&c, image + sizeof(*h), body_size);
	acl_sha256_final(&c, h->sha256);

	return sizeof(*h) + body_size;
}

static void sha_of(const uint8_t *data, size_t len, uint8_t out[32])
{
	struct acl_sha256 c;

	acl_sha256_init(&c);
	acl_sha256_update(&c, data, len);
	acl_sha256_final(&c, out);
}

/* The whole upload in uneven pieces; the finish's result */
static int upload(const uint8_t *data, size_t len, const uint8_t sha[32], const char **why)
{
	static const size_t pieces[] = {1, 63, 3, 700, 1460};
	char ticket[COPROC_TICKET_HEX];
	size_t off = 0;
	int ret;

	ret = coproc_begin(IP, len, sha, ticket, why);
	zassert_ok(ret, "begin: %s", *why);
	for (int i = 0; off < len; i++) {
		size_t n = MIN(pieces[i % ARRAY_SIZE(pieces)], len - off);

		ret = coproc_write(IP, ticket, data + off, n, why);
		if (ret != 0) {
			return ret;
		}
		off += n;
	}
	return coproc_finish(why);
}

ZTEST(coproc, test_stored)
{
	size_t len = make_image(0x20000000, BODY_SIZE);
	const struct flash_area *fa;
	static uint8_t back[BODY_SIZE];
	uint8_t sha[32];
	const char *why = NULL;
	char name[16];
	char json[384];
	uint32_t size, addr;

	sha_of(image, len, sha);
	zassert_ok(upload(image, len, sha, &why), "%s", why);
	zassert_ok(coproc_image_info(name, sizeof(name), &size, &addr));
	zassert_str_equal(name, "test 1.0");
	zassert_equal(size, BODY_SIZE);
	zassert_equal(addr, 0x20000000);

	/* In flash: the header, then the body */
	zassert_ok(flash_area_open(PARTITION_ID(coproc_partition), &fa));
	zassert_ok(flash_area_read(fa, sizeof(struct coproc_hdr), back, sizeof(back)));
	zassert_mem_equal(back, image + sizeof(struct coproc_hdr), sizeof(back));
	zassert_ok(flash_area_read(fa, 0, back, sizeof(struct coproc_hdr)));
	zassert_mem_equal(back, image, sizeof(struct coproc_hdr));
	flash_area_close(fa);

	zassert_true(coproc_json(json, sizeof(json)) > 0);
	zassert_not_null(strstr(json, "\"name\":\"test 1.0\""), "%s", json);
	zassert_not_null(strstr(json, "\"upload\":\"idle\",\"error\":null"), "%s", json);
}

ZTEST(coproc, test_refused)
{
	size_t len = make_image(0x20000000, BODY_SIZE);
	struct coproc_hdr *h = (struct coproc_hdr *)image;
	char ticket[COPROC_TICKET_HEX];
	uint8_t sha[32];
	const char *why = NULL;
	char name[16];
	uint32_t size, addr;

	/* Not the announced hash: the old image is gone too */
	memset(sha, 0x5a, sizeof(sha));
	zassert_not_ok(upload(image, len, sha, &why));
	zassert_str_equal(why, "SHA-256 does not match");
	zassert_equal(coproc_image_info(name, sizeof(name), &size, &addr), -ENOENT);

	/* A flash build (XIP addresses): refused at the header */
	len = make_image(0x10000000, BODY_SIZE);
	sha_of(image, len, sha);
	zassert_not_ok(upload(image, len, sha, &why));
	zassert_not_null(strstr(why, "SRAM"), "%s", why);

	/* Past the SRAM's end */
	len = make_image(0x20082000 - 4000, BODY_SIZE);
	sha_of(image, len, sha);
	zassert_not_ok(upload(image, len, sha, &why));
	zassert_not_null(strstr(why, "SRAM"), "%s", why);

	/* Another chip's UF2 family */
	len = make_image(0x20000000, BODY_SIZE);
	h->family = sys_cpu_to_le32(0xe48bff56); /* RP2040 */
	sha_of(image, len, sha);
	zassert_not_ok(upload(image, len, sha, &why));
	zassert_str_equal(why, "not an RP2350 Arm image");

	/* A body altered after the header was made */
	len = make_image(0x20000000, BODY_SIZE);
	image[len - 1] ^= 1;
	sha_of(image, len, sha);
	zassert_not_ok(upload(image, len, sha, &why));
	zassert_str_equal(why, "the header's SHA-256 is not the image's");

	/* Too large for the partition: refused before any byte */
	zassert_equal(coproc_begin(IP, PARTITION_SIZE(coproc_partition) + 1, sha, ticket, &why),
		      -EFBIG);
}

ZTEST(coproc, test_ticket)
{
	size_t len = make_image(0x20000000, BODY_SIZE);
	char ticket[COPROC_TICKET_HEX];
	char other[COPROC_TICKET_HEX];
	uint8_t sha[32];
	const char *why = NULL;

	sha_of(image, len, sha);
	zassert_ok(coproc_begin(IP, len, sha, ticket, &why));
	/* From another address, or another ticket */
	zassert_equal(coproc_write(IP + 1, ticket, image, 64, &why), -EPERM);
	memcpy(other, ticket, sizeof(other));
	other[0] = other[0] == '0' ? '1' : '0';
	zassert_equal(coproc_write(IP, other, image, 64, &why), -EPERM);
	/* Another begin from elsewhere while this one is pending */
	zassert_equal(coproc_begin(IP + 1, len, sha, other, &why), -EBUSY);
	/* More bytes than announced */
	zassert_ok(coproc_write(IP, ticket, image, len, &why));
	zassert_not_ok(coproc_write(IP, ticket, image, 1, &why));
	zassert_equal(coproc_finish(&why), -EPERM);
}

ZTEST_SUITE(coproc, NULL, NULL, NULL, NULL, NULL);
