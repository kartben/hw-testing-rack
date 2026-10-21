/*
 * Firmware updates over the network: the upload into slot 1, the test boot,
 * the trial and the self-confirmation (see hwtr/update.h).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/dfu/flash_img.h>
#include <zephyr/dfu/mcuboot.h>
#include <zephyr/drivers/watchdog.h>
#include <zephyr/random/random.h>
#include <zephyr/settings/settings.h>
#include <zephyr/storage/flash_map.h>
#include <zephyr/sys/reboot.h>
#include <zephyr/logging/log.h>

#include <hwtr/acl.h>
#include <hwtr/update.h>

LOG_MODULE_REGISTER(hwtr_update, CONFIG_HWTR_RACK_LOG_LEVEL);

/* The application's VERSION file, which also versions the signed image */
#if __has_include(<zephyr/app_version.h>)
#include <zephyr/app_version.h>
#else
#define APP_VERSION_STRING "0.0.0"
#endif

#define TICKET_MS 60000
#define REBOOT_MS 1500
#define STABLE_S  5     /* what must work works this long: confirm */
#define WDT_MS    30000 /* trial: stuck this long, reboot (and MCUboot goes back) */

/* Room left in slot 1 for MCUboot (swap-using-offset sector, trailer) */
#define SLOT_SIZE  PARTITION_SIZE(slot1_partition)
#define SLOT_ROOM  (SLOT_SIZE - 32 * 1024)

static struct hwtr_update_cfg cfg;
static K_MUTEX_DEFINE(lock);

/* The upload; the HTTP server delivers it from one thread */
static struct {
	enum hwtr_update_state state;
	uint8_t ticket[HWTR_UPDATE_TICKET_LEN];
	uint32_t ip;
	int64_t until;
	uint32_t size;
	uint32_t received;
	uint8_t sha[32];
	struct acl_sha256 hash;
	struct hwtr_img_parser img;
	struct flash_img_context flash;
	const char *error;
} up;

/* The last update, kept across the reboot (settings upd/...) */
static struct last_update {
	char stage[12]; /* "trial", "ok", "reverted" */
	char to[24];
	char from[24];
	uint8_t need;
} last;

static struct {
	bool on;
	int64_t deadline;
	int stable;
	uint32_t up;
} trial;

static void reboot_handler(struct k_work *work);
static void trial_handler(struct k_work *work);
static K_WORK_DELAYABLE_DEFINE(reboot_work, reboot_handler);
static K_WORK_DELAYABLE_DEFINE(trial_work, trial_handler);

#if defined(CONFIG_WATCHDOG) && DT_NODE_HAS_STATUS_OKAY(DT_ALIAS(watchdog0))
static const struct device *const wdt = DEVICE_DT_GET(DT_ALIAS(watchdog0));
#else
static const struct device *const wdt;
#endif
static int wdt_channel = -1;

const char *hwtr_update_id(void)
{
	return CONFIG_HWTR_UPDATE_ID;
}

static void event(const char *fmt, ...)
{
	char text[96];
	va_list ap;

	va_start(ap, fmt);
	vsnprintf(text, sizeof(text), fmt, ap);
	va_end(ap);
	LOG_INF("%s", text);
	if (cfg.event != NULL) {
		cfg.event(text);
	}
}

/* --- What the last update was --------------------------------------------- */

static int last_set(const char *key, size_t len, settings_read_cb read_cb, void *cb_arg,
		    void *param)
{
	static const struct {
		const char *name;
		size_t off;
		size_t size;
	} fields[] = {
		{"stage", offsetof(struct last_update, stage), sizeof(last.stage)},
		{"to", offsetof(struct last_update, to), sizeof(last.to)},
		{"from", offsetof(struct last_update, from), sizeof(last.from)},
		{"need", offsetof(struct last_update, need), sizeof(last.need)},
	};

	ARG_UNUSED(param);

	for (int i = 0; i < ARRAY_SIZE(fields); i++) {
		uint8_t *dst = (uint8_t *)&last + fields[i].off;

		if (strcmp(key, fields[i].name) != 0) {
			continue;
		}
		memset(dst, 0, fields[i].size);
		if (len > fields[i].size) {
			return 0;
		}
		(void)read_cb(cb_arg, dst, len);
		if (fields[i].size > 1) {
			dst[fields[i].size - 1] = '\0';
		}
	}
	return 0;
}

static void last_save(void)
{
	(void)settings_save_one("upd/stage", last.stage, strlen(last.stage) + 1);
	(void)settings_save_one("upd/to", last.to, strlen(last.to) + 1);
	(void)settings_save_one("upd/from", last.from, strlen(last.from) + 1);
	(void)settings_save_one("upd/need", &last.need, sizeof(last.need));
}

/* --- Trial ------------------------------------------------------------------ */

static void wdt_start(void)
{
	struct wdt_timeout_cfg c = {
		.window.max = WDT_MS,
		.flags = WDT_FLAG_RESET_SOC,
	};

	if (wdt == NULL || !device_is_ready(wdt)) {
		return;
	}
	wdt_channel = wdt_install_timeout(wdt, &c);
	if (wdt_channel < 0 || wdt_setup(wdt, 0) != 0) {
		LOG_WRN("no watchdog for the trial (%d)", wdt_channel);
		wdt_channel = -1;
	}
}

static void wdt_stop(void)
{
	if (wdt_channel >= 0) {
		(void)wdt_disable(wdt);
		wdt_channel = -1;
	}
}

static void do_reboot(void)
{
	if (cfg.reboot != NULL) {
		cfg.reboot();
		return;
	}
	sys_reboot(SYS_REBOOT_COLD);
}

static void trial_handler(struct k_work *work)
{
	int64_t now = k_uptime_get();
	uint32_t need;

	ARG_UNUSED(work);

	if (wdt_channel >= 0) {
		(void)wdt_feed(wdt, wdt_channel);
	}

	k_mutex_lock(&lock, K_FOREVER);
	need = last.need;
	trial.up = cfg.health != NULL ? cfg.health() : 0;
	trial.stable = (trial.up & need) == need ? trial.stable + 1 : 0;

	if (trial.stable >= STABLE_S) {
		if (boot_write_img_confirmed() != 0) {
			LOG_ERR("could not confirm the image");
			k_mutex_unlock(&lock);
			k_work_schedule(&trial_work, K_SECONDS(1));
			return;
		}
		trial.on = false;
		strcpy(last.stage, "ok");
		last_save();
		k_mutex_unlock(&lock);
		wdt_stop();
		event("firmware %s confirmed itself", APP_VERSION_STRING);
		return;
	}
	if (now >= trial.deadline) {
		k_mutex_unlock(&lock);
		event("firmware %s not healthy after %d s: rebooting into %s", APP_VERSION_STRING,
		      CONFIG_HWTR_UPDATE_TRIAL_S, last.from[0] ? last.from : "the previous one");
		k_sleep(K_MSEC(200)); /* the log line */
		do_reboot();
		return;
	}
	k_mutex_unlock(&lock);
	k_work_schedule(&trial_work, K_SECONDS(1));
}

int hwtr_update_init(const struct hwtr_update_cfg *c)
{
	bool confirmed;

	(void)k_work_cancel_delayable(&trial_work);
	cfg = *c;
	memset(&last, 0, sizeof(last));
	memset(&trial, 0, sizeof(trial));
	(void)settings_load_subtree_direct("upd", last_set, NULL);
	confirmed = boot_is_img_confirmed();

	if (!confirmed) {
		/* A test boot: what worked before the update must work again */
		if (strcmp(last.stage, "trial") != 0) {
			/* Not ours (no record): what this device has, or everything */
			last.need = (cfg.expected != NULL ? cfg.expected()
							   : HWTR_UP_WIFI | HWTR_UP_BUS) &
				    (HWTR_UP_WIFI | HWTR_UP_BUS);
			strcpy(last.stage, "trial");
			strcpy(last.from, "");
			snprintf(last.to, sizeof(last.to), "%s", APP_VERSION_STRING);
		}
		trial.on = true;
		trial.deadline = k_uptime_get() + CONFIG_HWTR_UPDATE_TRIAL_S * MSEC_PER_SEC;
		wdt_start();
		LOG_WRN("firmware %s on trial for %d s (Wi-Fi %s, rack bus %s), else back to %s",
			APP_VERSION_STRING, CONFIG_HWTR_UPDATE_TRIAL_S,
			(last.need & HWTR_UP_WIFI) ? "needed" : "not needed",
			(last.need & HWTR_UP_BUS) ? "needed" : "not needed",
			last.from[0] ? last.from : "the previous firmware");
		k_work_schedule(&trial_work, K_SECONDS(1));
	} else if (strcmp(last.stage, "trial") == 0) {
		/* Was on trial, is not any more, and never confirmed itself: MCUboot went back */
		strcpy(last.stage, "reverted");
		last_save();
		event("update to %s rolled back: running %s", last.to, APP_VERSION_STRING);
	}

	return 0;
}

/* --- Upload ----------------------------------------------------------------- */

static void reset_upload(enum hwtr_update_state state)
{
	up.state = state;
	up.received = 0;
	up.size = 0;
	up.until = 0;
	up.flash.flash_area = NULL;
}

static void reboot_handler(struct k_work *work)
{
	ARG_UNUSED(work);
	do_reboot();

	/* Only a test's reboot hook returns: nothing rebooted, ready for the next */
	k_mutex_lock(&lock, K_FOREVER);
	reset_upload(HWTR_UPDATE_IDLE);
	k_mutex_unlock(&lock);
}

int hwtr_update_begin(uint32_t ip, uint32_t size, const uint8_t sha256[32], bool force,
		      char ticket_hex[HWTR_UPDATE_TICKET_HEX], const char **why)
{
	const char *busy = cfg.busy != NULL ? cfg.busy() : NULL;
	int64_t now = k_uptime_get();
	int ret = 0;

	k_mutex_lock(&lock, K_FOREVER);
	if (up.state == HWTR_UPDATE_REBOOTING) {
		*why = "rebooting into the new firmware";
		ret = -EBUSY;
	} else if (up.state == HWTR_UPDATE_RECEIVING ||
		   (up.state == HWTR_UPDATE_READY && up.until > now && up.ip != ip)) {
		*why = "another update is on its way";
		ret = -EBUSY;
	} else if (trial.on) {
		*why = "the running firmware is on trial: wait until it confirms itself";
		ret = -EAGAIN;
	} else if (busy != NULL && !force) {
		*why = busy;
		ret = -EBUSY;
	} else if (size < HWTR_IMG_HEADER_SIZE || size > SLOT_ROOM) {
		*why = "size: larger than the update slot";
		ret = -EFBIG;
	}
	if (ret == 0) {
		if (sys_csrand_get(up.ticket, sizeof(up.ticket)) != 0) {
			sys_rand_get(up.ticket, sizeof(up.ticket));
		}
		reset_upload(HWTR_UPDATE_READY);
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
	reset_upload(HWTR_UPDATE_IDLE);
	LOG_WRN("update refused: %s", why);
	return -EINVAL;
}

static bool ticket_ok(uint32_t ip, const char *ticket_hex)
{
	uint8_t ticket[HWTR_UPDATE_TICKET_LEN];

	return ticket_hex != NULL && acl_hex_decode(ticket_hex, ticket, sizeof(ticket)) == 0 &&
	       acl_equal(ticket, up.ticket, sizeof(ticket)) && up.ip == ip;
}

int hwtr_update_write(uint32_t ip, const char *ticket_hex, const uint8_t *data, size_t len,
		      const char **why)
{
	int ret = 0;

	k_mutex_lock(&lock, K_FOREVER);
	if ((up.state != HWTR_UPDATE_READY && up.state != HWTR_UPDATE_RECEIVING) ||
	    !ticket_ok(ip, ticket_hex) ||
	    (up.state == HWTR_UPDATE_READY && k_uptime_get() > up.until)) {
		*why = "no such ticket: begin again";
		k_mutex_unlock(&lock);
		return -EPERM;
	}
	if (up.state == HWTR_UPDATE_READY) {
		ret = flash_img_init(&up.flash);
		if (ret != 0) {
			ret = fail("cannot open the update slot", why);
			k_mutex_unlock(&lock);
			return ret;
		}
		acl_sha256_init(&up.hash);
		hwtr_img_init(&up.img);
		up.state = HWTR_UPDATE_RECEIVING;
		LOG_INF("receiving %u bytes", up.size);
	}

	if (up.received + len > up.size) {
		ret = fail("more bytes than announced", why);
	} else {
		acl_sha256_update(&up.hash, data, len);
		hwtr_img_feed(&up.img, data, len);
		up.received += len;
		if (up.img.err == HWTR_IMG_NOT_MCUBOOT || up.img.err == HWTR_IMG_BAD_HEADER) {
			/* Not worth writing the rest */
			ret = fail(hwtr_img_strerror(up.img.err), why);
		} else if (flash_img_buffered_write(&up.flash, data, len, false) != 0) {
			ret = fail("flash write failed", why);
		}
	}
	k_mutex_unlock(&lock);

	return ret;
}

int hwtr_update_finish(struct hwtr_img_info *info, const char **why)
{
	char version[24];
	uint8_t sha[32];
	enum hwtr_img_err err;
	int ret = 0;

	k_mutex_lock(&lock, K_FOREVER);
	if (up.state != HWTR_UPDATE_RECEIVING) {
		*why = "no upload";
		k_mutex_unlock(&lock);
		return -EPERM;
	}
	if (flash_img_buffered_write(&up.flash, NULL, 0, true) != 0) {
		ret = fail("flash write failed", why);
		goto out;
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
	err = hwtr_img_finish(&up.img, info);
	if (err != HWTR_IMG_OK) {
		ret = fail(hwtr_img_strerror(err), why);
		goto out;
	}
	if (strcmp(info->id, hwtr_update_id()) != 0) {
		static char wrong[96];

		snprintf(wrong, sizeof(wrong), "image for %s, this is %s", info->id,
			 hwtr_update_id());
		ret = fail(wrong, why);
		goto out;
	}

	/* What works now must work again in the new firmware */
	hwtr_img_version(info, version, sizeof(version));
	strcpy(last.stage, "trial");
	snprintf(last.to, sizeof(last.to), "%s", version);
	snprintf(last.from, sizeof(last.from), "%s", APP_VERSION_STRING);
	last.need = (cfg.health != NULL ? cfg.health() : 0) & (HWTR_UP_WIFI | HWTR_UP_BUS);
	last_save();

	if (boot_request_upgrade(BOOT_UPGRADE_TEST) != 0) {
		strcpy(last.stage, "");
		last_save();
		ret = fail("could not mark the image for a test boot", why);
		goto out;
	}
	up.state = HWTR_UPDATE_REBOOTING;
	up.error = NULL;
	LOG_INF("firmware %s in slot 1, test boot in %d ms", version, REBOOT_MS);
	k_work_schedule(&reboot_work, K_MSEC(REBOOT_MS));
out:
	k_mutex_unlock(&lock);
	return ret;
}

void hwtr_update_abort(const char *why)
{
	k_mutex_lock(&lock, K_FOREVER);
	if (up.state == HWTR_UPDATE_RECEIVING) {
		up.error = why;
		reset_upload(HWTR_UPDATE_IDLE);
		LOG_WRN("upload stopped: %s", why);
	}
	k_mutex_unlock(&lock);
}

/* --- Status ------------------------------------------------------------------- */

void hwtr_update_status(struct hwtr_update_status *st)
{
	int64_t now = k_uptime_get();

	k_mutex_lock(&lock, K_FOREVER);
	memset(st, 0, sizeof(*st));
	st->state = up.state;
	if (st->state == HWTR_UPDATE_READY && up.until <= now) {
		st->state = HWTR_UPDATE_IDLE;
	}
	st->received = up.received;
	st->size = up.size;
	st->slot_size = SLOT_ROOM;
	st->trial = trial.on;
	st->trial_left_s = trial.on ? (int)MAX(0, (trial.deadline - now) / 1000) : -1;
	st->need = last.need;
	st->up = trial.up;
	st->last = strcmp(last.stage, "trial") == 0      ? "on trial"
		   : strcmp(last.stage, "ok") == 0       ? "confirmed"
		   : strcmp(last.stage, "reverted") == 0 ? "rolled back"
							 : "";
	strcpy(st->last_to, last.to);
	strcpy(st->last_from, last.from);
	st->error = up.error;
	k_mutex_unlock(&lock);
}

static const char *const states[] = {"idle", "ready", "receiving", "rebooting"};

struct out {
	char *buf;
	size_t size;
	size_t len;
	bool overflow;
};

static void put(struct out *o, const char *fmt, ...)
{
	va_list ap;
	int n;

	if (o->overflow) {
		return;
	}
	va_start(ap, fmt);
	n = vsnprintf(o->buf + o->len, o->size - o->len, fmt, ap);
	va_end(ap);
	if (n < 0 || (size_t)n >= o->size - o->len) {
		o->overflow = true;
		return;
	}
	o->len += n;
}

static void put_up(struct out *o, uint32_t bits)
{
	put(o, "[%s%s%s]", (bits & HWTR_UP_WIFI) ? "\"wifi\"" : "",
	    (bits & HWTR_UP_WIFI) && (bits & HWTR_UP_BUS) ? "," : "",
	    (bits & HWTR_UP_BUS) ? "\"bus\"" : "");
}

int hwtr_update_json(char *buf, size_t size)
{
	struct out o = {buf, size};
	struct hwtr_update_status st;

	hwtr_update_status(&st);

	put(&o, "{\"version\":\"%s\",\"id\":\"%s\",\"test_key\":%s,\"slot_kb\":%u,"
		"\"state\":\"%s\",\"received\":%u,\"size\":%u,",
	    APP_VERSION_STRING, hwtr_update_id(),
	    IS_ENABLED(CONFIG_HWTR_UPDATE_TEST_KEY) ? "true" : "false",
	    (unsigned int)(st.slot_size / 1024), states[st.state], st.received, st.size);
	if (st.trial) {
		put(&o, "\"trial\":{\"left_s\":%d,\"need\":", st.trial_left_s);
		put_up(&o, st.need);
		put(&o, ",\"up\":");
		put_up(&o, st.up);
		put(&o, "},");
	} else {
		put(&o, "\"trial\":null,");
	}
	if (st.last[0] != '\0') {
		put(&o, "\"last\":{\"result\":\"%s\",\"to\":\"%s\",\"from\":\"%s\"},", st.last,
		    st.last_to, st.last_from);
	} else {
		put(&o, "\"last\":null,");
	}
	if (st.error != NULL) {
		put(&o, "\"error\":\"%s\"}", st.error);
	} else {
		put(&o, "\"error\":null}");
	}

	return o.overflow ? -ENOMEM : (int)o.len;
}
