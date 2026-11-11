/*
 * The co-processor's image (src/coproc.c): uploads into the coproc
 * partition, whole and refused, on the flash simulator; then its load into
 * the RP2350 bootloader on the virtual USB bus (picoboot_emu.c), and what
 * the loader does when the bootloader stalls, goes silent or comes back.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/storage/flash_map.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/usb/usbh.h>
#include <zephyr/ztest.h>

#include <hwtr/acl.h>

#include "bay.h"
#include "picoboot_emu.h"

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

/* The partition holds no header: no image after a reboot either */
static bool header_erased(void)
{
	const struct flash_area *fa;
	uint32_t word = 0;

	zassert_ok(flash_area_open(PARTITION_ID(coproc_partition), &fa));
	zassert_ok(flash_area_read(fa, 0, &word, sizeof(word)));
	flash_area_close(fa);

	return word == 0xffffffffU;
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

	/* A flash build (XIP addresses): refused at the header, before any byte
	 * of the body; the old header is erased from flash all the same
	 */
	len = make_image(0x20000000, BODY_SIZE);
	sha_of(image, len, sha);
	zassert_ok(upload(image, len, sha, &why), "%s", why);
	len = make_image(0x10000000, BODY_SIZE);
	sha_of(image, len, sha);
	zassert_not_ok(upload(image, len, sha, &why));
	zassert_not_null(strstr(why, "SRAM"), "%s", why);
	zassert_true(header_erased());

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

/* --- The loader --------------------------------------------------------------- */

/* --- The DATA board (src/ports.c, not in this test): a DATA x4 unless a test says - */

static enum data_board board = DATA_X4;

enum data_board ports_board(void)
{
	return board;
}

USBH_CONTROLLER_DEFINE(test_uhs_ctx, DEVICE_DT_GET(DT_NODELABEL(zephyr_uhc0)));

/* A fresh image of BODY_SIZE bytes at 0x20000000: the loader's tries start again */
static void store(void)
{
	size_t len = make_image(0x20000000, BODY_SIZE);
	const char *why = NULL;
	uint8_t sha[32];

	sha_of(image, len, sha);
	zassert_ok(upload(image, len, sha, &why), "%s", why);
}

/* coproc_json() says this within ms */
static bool json_soon(const char *what, int ms)
{
	static char json[512];

	for (int64_t end = k_uptime_get() + ms; k_uptime_get() <= end; k_msleep(10)) {
		zassert_true(coproc_json(json, sizeof(json)) > 0);
		if (strstr(json, what) != NULL) {
			return true;
		}
	}
	printk("JSON: %s\n", json);
	return false;
}

static void unplug(void)
{
	(void)picoboot_emu_unplug();
	k_msleep(100);
}

static void *loader_setup(void)
{
	zassert_ok(usbh_init(&test_uhs_ctx));
	zassert_ok(usbh_enable(&test_uhs_ctx));
	zassert_ok(picoboot_emu_init());

	return NULL;
}

static void loader_before(void *fixture)
{
	ARG_UNUSED(fixture);

	/* Whatever the last test left plugged in goes */
	(void)picoboot_emu_unplug();
	k_msleep(100);
	picoboot_emu_reset();
	board = DATA_X4;
	store();
}

ZTEST(loader, test_1_loads)
{
	zassert_ok(picoboot_emu_plug());
	zassert_ok(k_sem_take(&picoboot_emu_left, K_SECONDS(5)), "never told to run the image");

	/* What picotool load -x sends for an image in SRAM */
	zassert_equal(emu.bad, 0);
	zassert_equal(emu.exclusive, 1);
	zassert_equal(emu.written, BODY_SIZE);
	zassert_mem_equal(emu.sram, image + sizeof(struct coproc_hdr), BODY_SIZE);
	zassert_equal(emu.reboots, 1);
	zassert_equal(emu.reboot_flags, 0x3, "RAM image");
	zassert_equal(emu.reboot_delay, 500);
	zassert_equal(emu.reboot_p0, 0x20000000);
	zassert_equal(emu.reboot_p1, 0x82000, "from the image to the SRAM's end");

	/* Not back in its bootloader: loaded */
	zassert_true(json_soon("\"load\":{\"state\":\"loaded\"", 2000));
	zassert_true(json_soon("\"error\":null}", 10));
}

ZTEST(loader, test_2_not_started)
{
	uint32_t cmds;

	/* Back in its bootloader at once after each load: the image does not run */
	for (int i = 0; i < 2; i++) {
		zassert_ok(picoboot_emu_plug());
		zassert_ok(k_sem_take(&picoboot_emu_left, K_SECONDS(5)), "load %d", i);
	}

	/* After two such loads it is left to USB/IP: nothing more is sent */
	cmds = emu.cmds;
	zassert_ok(picoboot_emu_plug());
	zassert_true(json_soon("\"state\":\"left to USB/IP\"", 2000));
	zassert_true(json_soon("the image did not start", 10));
	k_msleep(300);
	zassert_equal(emu.cmds, cmds);
	unplug();
}

ZTEST(loader, test_3_stall)
{
	emu.stall_write = true;
	zassert_ok(picoboot_emu_plug());
	zassert_true(json_soon("\"state\":\"failed\"", 3000));
	zassert_true(json_soon("(stall)", 10));
	zassert_equal(emu.reboots, 0);
	unplug();
}

ZTEST(loader, test_4_silent)
{
	emu.mute = true;
	zassert_ok(picoboot_emu_plug());
	/* COPROC_LOAD_TIMEOUT_MS: 1 s here */
	zassert_true(json_soon("the bootloader stopped answering", 3000));
	zassert_equal(emu.reboots, 0);
	unplug();

	/* Answering again: loaded */
	emu.mute = false;
	zassert_ok(picoboot_emu_plug());
	zassert_ok(k_sem_take(&picoboot_emu_left, K_SECONDS(5)));
	zassert_true(json_soon("\"state\":\"loaded\"", 2000));
}

ZTEST(loader, test_5_no_image)
{
	char ticket[COPROC_TICKET_HEX];
	const char *why = NULL;
	uint8_t sha[32] = {0};

	/* An upload that starts and stops: no image any more */
	zassert_ok(coproc_begin(IP, 1000, sha, ticket, &why));
	zassert_ok(coproc_write(IP, ticket, image, 10, &why));
	coproc_abort("test");
	zassert_true(header_erased());

	zassert_ok(picoboot_emu_plug());
	k_msleep(300);
	zassert_equal(emu.cmds, 0, "nothing to load: left to USB/IP");
	zassert_true(json_soon("\"image\":null", 10));
	unplug();
}

ZTEST(loader, test_6_upload_while_loading)
{
	size_t len = make_image(0x20000000, BODY_SIZE);
	char ticket[COPROC_TICKET_HEX];
	const char *why = NULL;
	uint8_t sha[32];

	/* A ticket, then a load that takes its time, then the upload's bytes */
	sha_of(image, len, sha);
	zassert_ok(coproc_begin(IP, len, sha, ticket, &why));
	emu.mute = true;
	zassert_ok(picoboot_emu_plug());
	zassert_true(json_soon("\"state\":\"loading\"", 1000));
	zassert_equal(coproc_write(IP, ticket, image, 64, &why), -EBUSY);
	zassert_true(json_soon("\"name\":\"test 1.0\"", 10), "the image stays");
	zassert_false(header_erased());

	/* Once the load is over the same ticket goes on */
	zassert_true(json_soon("the bootloader stopped answering", 3000));
	zassert_ok(coproc_write(IP, ticket, image, len, &why), "%s", why);
	zassert_ok(coproc_finish(&why), "%s", why);
	unplug();
}

ZTEST(loader, test_7_data_x6)
{
	/* On a DATA x6 the co-processor's hub port is its USB-C 6: a board under test, never loaded */
	board = DATA_X6;
	zassert_ok(picoboot_emu_plug());
	k_msleep(500);
	zassert_equal(emu.cmds, 0, "%u commands to a board under test", emu.cmds);
	zassert_equal(emu.written, 0);
	unplug();

	/* Nor on a board the node does not know */
	board = DATA_UNKNOWN;
	zassert_ok(picoboot_emu_plug());
	k_msleep(500);
	zassert_equal(emu.cmds, 0, "%u commands behind an unknown board", emu.cmds);
	unplug();
}

ZTEST_SUITE(loader, NULL, loader_setup, loader_before, NULL, NULL);
