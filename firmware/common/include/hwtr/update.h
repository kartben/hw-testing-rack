/*
 * Firmware updates over the network, for the bay nodes and the power hub.
 *
 * Both boards boot through MCUboot (sysbuild), which checks the image's
 * signature and swaps it in.  This side receives the image and decides
 * whether the new firmware stays:
 *
 *   1. begin: an admin request (signed with the device's admin key) gives
 *      the size and SHA-256 of the image and gets a single-use ticket;
 *   2. the upload, with that ticket, is written to slot 1 as it streams in,
 *      hashed and parsed on the way (hwtr/mcuboot_img.h);
 *   3. the right size, hash and image id (the application and board it was
 *      built for): MCUboot is asked for a test boot, and the device reboots;
 *   4. the new firmware runs on trial: it confirms itself once what worked
 *      before the update works again (Wi-Fi, the rack bus) for a few
 *      seconds.  Not within CONFIG_HWTR_UPDATE_TRIAL_S, or stuck long
 *      enough for the watchdog: it reboots unconfirmed and MCUboot puts
 *      the previous firmware back.
 *
 * The HTTP side is firmware/common/web/update_http.c (hwtr_web_update()).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef HWTR_UPDATE_H_
#define HWTR_UPDATE_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include <zephyr/sys/util.h>

#include <hwtr/mcuboot_img.h>

/* What works, for the trial: what worked before the update must work again */
#define HWTR_UP_WIFI BIT(0)
#define HWTR_UP_BUS  BIT(1)

#define HWTR_UPDATE_TICKET_LEN 8
#define HWTR_UPDATE_TICKET_HEX (2 * HWTR_UPDATE_TICKET_LEN + 1)

struct hwtr_update_cfg {
	/* HWTR_UP_* bits for what works right now */
	uint32_t (*health)(void);
	/*
	 * HWTR_UP_* bits a test boot with no update record (an image flashed
	 * or tested by other means) must see work: what this device has; NULL,
	 * all of them.  A node that never had a rack bus does not ask for it.
	 */
	uint32_t (*expected)(void);
	/* NULL, or why an update should wait (the bay is reserved); "force" overrides */
	const char *(*busy)(void);
	/* A line for the device's event log (confirmed, rolled back), or NULL */
	void (*event)(const char *text);
	/* Test hook: instead of sys_reboot() */
	void (*reboot)(void);
};

enum hwtr_update_state {
	HWTR_UPDATE_IDLE,
	HWTR_UPDATE_READY,       /* a ticket was given, the upload has not started */
	HWTR_UPDATE_RECEIVING,
	HWTR_UPDATE_REBOOTING,   /* checked, test boot asked for, rebooting */
};

struct hwtr_update_status {
	enum hwtr_update_state state;
	uint32_t received;
	uint32_t size;
	uint32_t slot_size;
	bool trial;              /* the running firmware has not confirmed itself yet */
	int trial_left_s;
	uint32_t need;           /* trial: HWTR_UP_* that must work */
	uint32_t up;             /* trial: HWTR_UP_* that work */
	const char *last;        /* the last update: "", "on trial", "confirmed", "rolled back" */
	char last_to[24];        /* its version */
	char last_from[24];      /* the version it replaced */
	const char *error;       /* why the last upload was refused, or NULL */
};

/* After settings_subsys_init(): reads the trial state, starts the trial if any */
int hwtr_update_init(const struct hwtr_update_cfg *cfg);

/*
 * An update of `size` bytes with this SHA-256, from `ip` (the caller checked
 * the admin signature).  0 and the ticket, or -EBUSY / -EFBIG / -EAGAIN with
 * *why.
 */
int hwtr_update_begin(uint32_t ip, uint32_t size, const uint8_t sha256[32], bool force,
		      char ticket_hex[HWTR_UPDATE_TICKET_HEX], const char **why);

/* The next bytes of the upload; the first call checks the ticket */
int hwtr_update_write(uint32_t ip, const char *ticket_hex, const uint8_t *data, size_t len,
		      const char **why);

/* The upload is complete: check it, ask MCUboot for a test boot, reboot shortly */
int hwtr_update_finish(struct hwtr_img_info *info, const char **why);

/* The upload stopped half-way (connection lost, refused) */
void hwtr_update_abort(const char *why);

void hwtr_update_status(struct hwtr_update_status *st);

/* The "firmware" object of /api/status and GET /api/update */
int hwtr_update_json(char *buf, size_t size);

/* "<application>/<board>", what the image id must say */
const char *hwtr_update_id(void);

#endif /* HWTR_UPDATE_H_ */
