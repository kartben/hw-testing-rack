/*
 * Firmware updates on native_sim:
 *
 *   mcuboot_img  the image parser (lib/mcuboot_img.c) on images built here
 *                the way imgtool lays them out, fed in chunks of every size;
 *   update       the update code (lib/update.c) on the flash simulator's
 *                MCUboot partitions: the upload lands in slot 1 one sector
 *                in (swap using offset) with a test boot requested, every
 *                refusal leaves slot 1 alone, tickets are single-owner, and
 *                a test-booted image confirms itself once what worked
 *                before works again, or reboots (and MCUboot goes back).
 *
 * MCUboot itself does not run: the test checks what the application leaves
 * in the trailers for it (mcuboot_swap_type(), boot_is_img_confirmed()).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/ztest.h>
#include <zephyr/dfu/mcuboot.h>
#include <zephyr/settings/settings.h>
#include <zephyr/storage/flash_map.h>

#include <bootutil/bootutil_public.h>

#include <hwtr/acl.h>
#include <hwtr/mcuboot_img.h>
#include <hwtr/update.h>

#define ID       CONFIG_HWTR_UPDATE_ID
#define IP       0x0a000002
#define OTHER_IP 0x0a000003
#define SECTOR   4096

static uint8_t img[24 * 1024];

static void put16(uint8_t *p, uint16_t v)
{
	p[0] = (uint8_t)v;
	p[1] = (uint8_t)(v >> 8);
}

static void put32(uint8_t *p, uint32_t v)
{
	put16(p, (uint16_t)v);
	put16(p + 2, (uint16_t)(v >> 16));
}

/* An image as imgtool lays it out: header, code, protected TLVs (the id), TLVs */
static size_t make_image(uint8_t *buf, uint32_t code, const char *id)
{
	size_t idlen = id != NULL ? strlen(id) : 0;
	uint16_t prot = id != NULL ? (uint16_t)(4 + 4 + idlen) : 0;
	size_t o = HWTR_IMG_HEADER_SIZE;

	memset(buf, 0, HWTR_IMG_HEADER_SIZE);
	put32(buf, HWTR_IMG_MAGIC);
	put16(buf + 8, HWTR_IMG_HEADER_SIZE);
	put16(buf + 10, prot);
	put32(buf + 12, code);
	buf[20] = 1;
	buf[21] = 2;
	put16(buf + 22, 3);
	put32(buf + 24, 4);
	for (uint32_t i = 0; i < code; i++) {
		buf[o++] = (uint8_t)(i * 7 + 1);
	}
	if (id != NULL) {
		put16(buf + o, HWTR_IMG_TLV_PROT_INFO);
		put16(buf + o + 2, prot);
		put16(buf + o + 4, HWTR_IMG_TLV_ID);
		put16(buf + o + 6, (uint16_t)idlen);
		memcpy(buf + o + 8, id, idlen);
		o += prot;
	}
	/* Unprotected: the SHA-256 TLV (its value does not matter here) */
	put16(buf + o, HWTR_IMG_TLV_INFO);
	put16(buf + o + 2, 4 + 4 + 32);
	put16(buf + o + 4, 0x10);
	put16(buf + o + 6, 32);
	memset(buf + o + 8, 0xab, 32);

	return o + 4 + 4 + 32;
}

static enum hwtr_img_err parse(const uint8_t *buf, size_t len, size_t chunk,
			       struct hwtr_img_info *info)
{
	struct hwtr_img_parser p;

	hwtr_img_init(&p);
	for (size_t at = 0; at < len; at += chunk) {
		hwtr_img_feed(&p, buf + at, MIN(chunk, len - at));
	}
	return hwtr_img_finish(&p, info);
}

/* --- The image parser -------------------------------------------------------- */

ZTEST(mcuboot_img, test_any_chunking)
{
	static const size_t chunks[] = {1, 3, 7, 31, 32, 33, 512, 1 << 20};
	size_t len = make_image(img, 1000, ID);
	struct hwtr_img_info info;
	char version[24];

	for (int i = 0; i < ARRAY_SIZE(chunks); i++) {
		memset(&info, 0, sizeof(info));
		zassert_equal(parse(img, len, chunks[i], &info), HWTR_IMG_OK, "chunk %zu",
			      chunks[i]);
		zassert_str_equal(info.id, ID);
		zassert_equal(info.total, len);
		zassert_equal(info.img_size, 1000);
	}
	hwtr_img_version(&info, version, sizeof(version));
	zassert_str_equal(version, "1.2.3+4");
	info.build = 0;
	hwtr_img_version(&info, version, sizeof(version));
	zassert_str_equal(version, "1.2.3");
}

ZTEST(mcuboot_img, test_truncated_and_too_long)
{
	size_t len = make_image(img, 1000, ID);
	struct hwtr_img_info info;

	zassert_equal(parse(img, len - 1, 64, &info), HWTR_IMG_TRUNCATED);
	zassert_equal(parse(img, 1032, 64, &info), HWTR_IMG_TRUNCATED);
	zassert_equal(parse(img, 20, 64, &info), HWTR_IMG_TRUNCATED);
	img[len] = 0;
	zassert_equal(parse(img, len + 1, 64, &info), HWTR_IMG_TOO_LONG);
	zassert_equal(parse(img, len + 1, 1, &info), HWTR_IMG_TOO_LONG);
}

ZTEST(mcuboot_img, test_not_an_image)
{
	static const uint8_t text[] = "PK\x03\x04 a zip file, say";
	size_t len = make_image(img, 1000, ID);
	struct hwtr_img_parser p;
	struct hwtr_img_info info;

	/* The first 32 bytes are enough to say so */
	img[0] ^= 0xff;
	hwtr_img_init(&p);
	hwtr_img_feed(&p, img, HWTR_IMG_HEADER_SIZE);
	zassert_equal(p.err, HWTR_IMG_NOT_MCUBOOT);
	zassert_false(hwtr_img_header(&p, &info));
	zassert_equal(parse(img, len, 100, &info), HWTR_IMG_NOT_MCUBOOT);

	zassert_equal(parse(text, 3, 1, &info), HWTR_IMG_NOT_MCUBOOT);
	zassert_equal(parse(text, 0, 1, &info), HWTR_IMG_NOT_MCUBOOT);
}

ZTEST(mcuboot_img, test_no_id)
{
	size_t len = make_image(img, 1000, NULL);
	struct hwtr_img_info info;

	zassert_equal(parse(img, len, 64, &info), HWTR_IMG_NO_ID);

	/* A protected TLV, not ours */
	len = make_image(img, 1000, ID);
	put16(img + 32 + 1000 + 4, 0x00a1);
	zassert_equal(parse(img, len, 64, &info), HWTR_IMG_NO_ID);

	/* A broken protected area */
	len = make_image(img, 1000, ID);
	put16(img + 32 + 1000, 0x1234);
	zassert_equal(parse(img, len, 64, &info), HWTR_IMG_BAD_TLV);

	/* A broken TLV info after it */
	len = make_image(img, 1000, ID);
	put16(img + 32 + 1000 + 8 + strlen(ID), 0x1234);
	zassert_equal(parse(img, len, 64, &info), HWTR_IMG_BAD_TLV);
}

ZTEST_SUITE(mcuboot_img, NULL, NULL, NULL, NULL, NULL);

/* --- The update ---------------------------------------------------------------- */

static uint32_t health;
static const char *busy;
static int reboots;

static uint32_t health_cb(void)
{
	return health;
}

static const char *busy_cb(void)
{
	return busy;
}

static void reboot_cb(void)
{
	reboots++;
}

static const struct hwtr_update_cfg cfg = {
	.health = health_cb,
	.busy = busy_cb,
	.reboot = reboot_cb,
};

static void erase_trailer(uint8_t id)
{
	const struct flash_area *fa;

	zassert_ok(flash_area_open(id, &fa));
	zassert_ok(flash_area_erase(fa, fa->fa_size - 2 * SECTOR, 2 * SECTOR));
	flash_area_close(fa);
}

/* As MCUboot leaves slot 0 after a test swap: magic, image not confirmed */
static void slot0_test_booted(void)
{
	const struct flash_area *fa;

	erase_trailer(PARTITION_ID(slot0_partition));
	zassert_ok(flash_area_open(PARTITION_ID(slot0_partition), &fa));
	zassert_ok(boot_set_next(fa, false, false));
	flash_area_close(fa);
	zassert_false(boot_is_img_confirmed());
}

static void record(const char *stage, uint8_t need)
{
	zassert_ok(settings_save_one("upd/stage", stage, strlen(stage) + 1));
	zassert_ok(settings_save_one("upd/to", "0.5.0", sizeof("0.5.0")));
	zassert_ok(settings_save_one("upd/from", "0.4.0", sizeof("0.4.0")));
	zassert_ok(settings_save_one("upd/need", &need, 1));
}

static int upload_as(uint32_t ip, const uint8_t *buf, size_t len, const uint8_t *hashed,
		     size_t hashed_len, const char **why)
{
	char ticket[HWTR_UPDATE_TICKET_HEX];
	struct hwtr_img_info info;
	struct acl_sha256 c;
	uint8_t sha[32];
	int ret;

	acl_sha256_init(&c);
	acl_sha256_update(&c, hashed, hashed_len);
	acl_sha256_final(&c, sha);

	ret = hwtr_update_begin(ip, len, sha, false, ticket, why);
	for (size_t at = 0; ret == 0 && at < len; at += 512) {
		ret = hwtr_update_write(ip, ticket, buf + at, MIN(512, len - at), why);
	}
	return ret != 0 ? ret : hwtr_update_finish(&info, why);
}

static int upload(const uint8_t *buf, size_t len, const char **why)
{
	return upload_as(IP, buf, len, buf, len, why);
}

static void *update_setup(void)
{
	zassert_ok(settings_subsys_init());
	return NULL;
}

static void update_before(void *fixture)
{
	ARG_UNUSED(fixture);

	/* Nothing in slot 1, the running image confirmed, no record */
	zassert_ok(boot_erase_img_bank(PARTITION_ID(slot1_partition)));
	erase_trailer(PARTITION_ID(slot0_partition));
	(void)settings_delete("upd/stage");
	(void)settings_delete("upd/to");
	(void)settings_delete("upd/from");
	(void)settings_delete("upd/need");
	health = HWTR_UP_WIFI | HWTR_UP_BUS;
	busy = NULL;
	reboots = 0;
	zassert_ok(hwtr_update_init(&cfg));
}

ZTEST(update, test_upload_test_boot_confirm)
{
	size_t len = make_image(img, 20000, ID);
	struct hwtr_update_status st;
	const struct flash_area *fa;
	uint8_t head[64];
	const char *why = "";

	/* On a desk: Wi-Fi, no rack bus */
	health = HWTR_UP_WIFI;
	zassert_ok(upload(img, len, &why), "%s", why);
	zassert_equal(mcuboot_swap_type(), BOOT_SWAP_TYPE_TEST);

	/* In slot 1, one sector in (swap using offset) */
	zassert_ok(flash_area_open(PARTITION_ID(slot1_partition), &fa));
	zassert_ok(flash_area_read(fa, SECTOR, head, sizeof(head)));
	flash_area_close(fa);
	zassert_mem_equal(head, img, sizeof(head));

	hwtr_update_status(&st);
	zassert_equal(st.state, HWTR_UPDATE_REBOOTING);
	zassert_equal(reboots, 0);
	k_sleep(K_SECONDS(2));
	zassert_equal(reboots, 1);

	/* MCUboot swapped it in: on trial, with what worked at the upload (Wi-Fi only) */
	slot0_test_booted();
	zassert_ok(hwtr_update_init(&cfg));
	hwtr_update_status(&st);
	zassert_true(st.trial);
	zassert_equal(st.need, HWTR_UP_WIFI);
	zassert_str_equal(st.last, "on trial");
	zassert_str_equal(st.last_to, "1.2.3+4");

	/* Wi-Fi for 5 s: confirmed, nothing rebooted */
	k_sleep(K_SECONDS(7));
	hwtr_update_status(&st);
	zassert_false(st.trial);
	zassert_true(boot_is_img_confirmed());
	zassert_str_equal(st.last, "confirmed");
	zassert_equal(reboots, 1);

	/* Confirmed stays confirmed across a reboot */
	zassert_ok(hwtr_update_init(&cfg));
	hwtr_update_status(&st);
	zassert_str_equal(st.last, "confirmed");
}

ZTEST(update, test_refusals_leave_slot1_alone)
{
	static const struct {
		const char *id;
		const char *why;
	} wrong[] = {
		{"power-hub/power_hub", "image for power-hub/power_hub, this is " ID},
		{NULL, "no image id"},
	};
	struct hwtr_update_status st;
	const char *why = "";
	size_t len;

	/* Hash of something else */
	len = make_image(img, 3000, ID);
	zassert_equal(upload_as(IP, img, len, img, len - 1, &why), -EINVAL);
	zassert_str_equal(why, "SHA-256 does not match");

	/* Another application or board, or not from this repository */
	for (int i = 0; i < ARRAY_SIZE(wrong); i++) {
		len = make_image(img, 3000, wrong[i].id);
		zassert_equal(upload(img, len, &why), -EINVAL);
		zassert_true(strncmp(why, wrong[i].why, strlen(wrong[i].why)) == 0, "%s", why);
	}

	/* Not an image: refused on the first chunk */
	memset(img, 'x', 3000);
	zassert_equal(upload(img, 3000, &why), -EINVAL);
	zassert_true(strncmp(why, "not a signed image", 18) == 0, "%s", why);
	hwtr_update_status(&st);
	zassert_equal(st.received, 0);
	zassert_str_equal(st.error, why);

	zassert_equal(mcuboot_swap_type(), BOOT_SWAP_TYPE_NONE);
	k_sleep(K_SECONDS(2));
	zassert_equal(reboots, 0);
}

ZTEST(update, test_tickets)
{
	size_t len = make_image(img, 3000, ID);
	char ticket[HWTR_UPDATE_TICKET_HEX];
	char other[HWTR_UPDATE_TICKET_HEX];
	struct hwtr_update_status st;
	uint8_t sha[32] = {0};
	const char *why = "";

	zassert_ok(hwtr_update_begin(IP, len, sha, false, ticket, &why));

	/* Someone else: no ticket of their own while this one is valid, not this one */
	zassert_equal(hwtr_update_begin(OTHER_IP, len, sha, false, other, &why), -EBUSY);
	zassert_equal(hwtr_update_write(OTHER_IP, ticket, img, 64, &why), -EPERM);
	zassert_equal(hwtr_update_write(IP, "0011223344556677", img, 64, &why), -EPERM);
	zassert_equal(hwtr_update_write(IP, NULL, img, 64, &why), -EPERM);

	/* Begun, never sent: the ticket lapses after a minute */
	k_sleep(K_SECONDS(61));
	zassert_equal(hwtr_update_write(IP, ticket, img, 64, &why), -EPERM);
	zassert_ok(hwtr_update_begin(OTHER_IP, len, sha, false, other, &why));

	/* Cut off half-way */
	zassert_ok(hwtr_update_write(OTHER_IP, other, img, 1024, &why));
	zassert_equal(hwtr_update_begin(IP, len, sha, false, ticket, &why), -EBUSY);
	hwtr_update_abort("upload interrupted");
	hwtr_update_status(&st);
	zassert_equal(st.state, HWTR_UPDATE_IDLE);
	zassert_str_equal(st.error, "upload interrupted");
	zassert_equal(hwtr_update_write(OTHER_IP, other, img, 64, &why), -EPERM);

	/* Too large for the slot */
	zassert_equal(hwtr_update_begin(IP, 16 * 1024 * 1024, sha, false, ticket, &why), -EFBIG);

	/* A reserved bay: only with force */
	busy = "reserved by 10.0.0.9 for 12 min more: force to update anyway";
	zassert_equal(hwtr_update_begin(IP, len, sha, false, ticket, &why), -EBUSY);
	zassert_equal(why, busy);
	zassert_ok(hwtr_update_begin(IP, len, sha, true, ticket, &why));
}

ZTEST(update, test_trial_rolls_back)
{
	struct hwtr_update_status st;
	uint8_t sha[32] = {0};
	char ticket[HWTR_UPDATE_TICKET_HEX];
	const char *why = "";

	/* Test-booted; the rack bus worked before the update, not any more */
	record("trial", HWTR_UP_WIFI | HWTR_UP_BUS);
	slot0_test_booted();
	health = HWTR_UP_WIFI;
	zassert_ok(hwtr_update_init(&cfg));
	hwtr_update_status(&st);
	zassert_true(st.trial);
	zassert_true(st.trial_left_s >= CONFIG_HWTR_UPDATE_TRIAL_S - 1);
	zassert_str_equal(st.last_from, "0.4.0");

	/* No update on top of a firmware on trial */
	zassert_equal(hwtr_update_begin(IP, 4096, sha, false, ticket, &why), -EAGAIN);

	/* Never healthy: reboots unconfirmed when the trial runs out */
	k_sleep(K_SECONDS(CONFIG_HWTR_UPDATE_TRIAL_S - 2));
	zassert_equal(reboots, 0);
	k_sleep(K_SECONDS(4));
	zassert_equal(reboots, 1);
	zassert_false(boot_is_img_confirmed());

	/* MCUboot puts the previous firmware back (confirmed, no trailer of its own) */
	erase_trailer(PARTITION_ID(slot0_partition));
	zassert_ok(hwtr_update_init(&cfg));
	hwtr_update_status(&st);
	zassert_false(st.trial);
	zassert_str_equal(st.last, "rolled back");
	zassert_str_equal(st.last_to, "0.5.0");
}

ZTEST(update, test_usb_flash_is_no_trial)
{
	struct hwtr_update_status st;

	/* An image flashed over USB has no trailer: confirmed, no trial, no reboot */
	hwtr_update_status(&st);
	zassert_false(st.trial);
	zassert_str_equal(st.last, "");
	k_sleep(K_SECONDS(CONFIG_HWTR_UPDATE_TRIAL_S + 5));
	zassert_equal(reboots, 0);
}

ZTEST(update, test_status_json)
{
	static char buf[640];

	zassert_true(hwtr_update_json(buf, sizeof(buf)) > 0);
	zassert_not_null(strstr(buf, "\"id\":\"" ID "\""), "%s", buf);
	zassert_not_null(strstr(buf, "\"trial\":null"), "%s", buf);
	zassert_not_null(strstr(buf, "\"state\":\"idle\""), "%s", buf);
	zassert_equal(hwtr_update_json(buf, 40), -ENOMEM);
}

ZTEST_SUITE(update, NULL, update_setup, update_before, NULL, NULL);
