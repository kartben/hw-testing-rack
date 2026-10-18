/*
 * The admin key of a bay node or of the power hub, shared code.
 *
 * Admin: whoever holds the device's key.  The first key comes from a claim
 * confirmed by physical presence (a short press on BOOT, or the local
 * shell); after that, admin requests carry
 *
 *     X-Bay-Auth: <nonce>:<HMAC-SHA256(key, nonce \n method \n path \n body)>
 *
 * with a single-use nonce from GET /api/access/nonce, so the key itself
 * crosses the network once, at claim time.  A claim may bring a key along
 * (the rack's key: one key for every bay and the hub).
 *
 * The application stores the key where it likes (its settings): it loads it
 * with hwtr_admin_load() and gets it back through the save callback.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef HWTR_ADMIN_H_
#define HWTR_ADMIN_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include <hwtr/acl.h>

#define HWTR_ADMIN_NONCE_LEN  8
#define HWTR_ADMIN_TICKET_LEN 8
/* Hex strings, with their terminating NUL */
#define HWTR_ADMIN_NONCE_HEX  (2 * HWTR_ADMIN_NONCE_LEN + 1)
#define HWTR_ADMIN_TICKET_HEX (2 * HWTR_ADMIN_TICKET_LEN + 1)
#define HWTR_ADMIN_KEY_HEX    (2 * ACL_KEY_LEN + 1)

struct hwtr_admin_cfg {
	/* How long a claim waits for the button press, ms (0: CONFIG_HWTR_ADMIN_CLAIM_S) */
	uint32_t claim_ms;
	/* Store the key, or forget it (NULL) */
	int (*save)(const uint8_t *key);
	/* "press BOOT on ..." in the log when a claim starts (optional) */
	const char *how_to_confirm;
};

void hwtr_admin_init(const struct hwtr_admin_cfg *cfg);
/* The key from the settings (before or after init) */
void hwtr_admin_load(const uint8_t key[ACL_KEY_LEN]);
bool hwtr_admin_claimed(void);

/* A single-use nonce, valid one minute (out: HWTR_ADMIN_NONCE_HEX) */
int hwtr_admin_nonce(char *out);
/* Is this X-Bay-Auth a valid signature of this request?  Uses up the nonce */
bool hwtr_admin_check(const char *auth, const char *method, const char *path,
		      const uint8_t *body, size_t len);
int hwtr_admin_set_key(const uint8_t *key);
/* Unclaimed again: the local recovery */
int hwtr_admin_forget(void);

/* A claim from ip (offered: a key to adopt, or NULL for a new one); -EALREADY if claimed */
int hwtr_admin_claim_start(uint32_t ip, const uint8_t *offered, char *ticket_hex);
/* The button (or the local shell) should confirm now */
bool hwtr_admin_claim_pending(void);
/* The press: the key is set; -ENOENT without a pending claim */
int hwtr_admin_claim_confirm(void);
/*
 * The claimer asks how it goes: -EINPROGRESS (remaining_s), 0 and the key
 * (key_hex: HWTR_ADMIN_KEY_HEX) once confirmed, -ETIMEDOUT, -ENOENT.
 */
int hwtr_admin_claim_poll(uint32_t ip, const char *ticket_hex, char *key_hex, int *remaining_s);

#endif /* HWTR_ADMIN_H_ */
