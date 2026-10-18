/*
 * The admin key: nonces, signatures, the claim by physical presence (see
 * hwtr/admin.h).  Moved out of the bay node's access.c so the power hub
 * signs its admin requests the same way.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/random/random.h>
#include <zephyr/logging/log.h>

#include <hwtr/admin.h>

LOG_MODULE_REGISTER(hwtr_admin, CONFIG_HWTR_RACK_LOG_LEVEL);

#define NONCE_MS 60000
#define NONCES   8

static struct hwtr_admin_cfg cfg;
static struct k_spinlock lock;
static uint8_t key[ACL_KEY_LEN];
static bool have_key;

static struct {
	uint8_t value[HWTR_ADMIN_NONCE_LEN];
	int64_t until;
} nonces[NONCES];
static unsigned int nonce_next;

static struct {
	bool pending;
	bool done;
	bool offered; /* the claimer brought its own key (one key for the rack) */
	uint8_t ticket[HWTR_ADMIN_TICKET_LEN];
	uint32_t ip;
	int64_t until;
	uint8_t key[ACL_KEY_LEN];
} claim;
static K_MUTEX_DEFINE(claim_lock);

static void random_fill(void *buf, size_t len)
{
	if (sys_csrand_get(buf, len) != 0) {
		sys_rand_get(buf, len);
	}
}

static uint32_t claim_ms(void)
{
	return cfg.claim_ms ? cfg.claim_ms : CONFIG_HWTR_ADMIN_CLAIM_S * MSEC_PER_SEC;
}

void hwtr_admin_init(const struct hwtr_admin_cfg *c)
{
	cfg = *c;
}

void hwtr_admin_load(const uint8_t k[ACL_KEY_LEN])
{
	memcpy(key, k, sizeof(key));
	have_key = true;
}

bool hwtr_admin_claimed(void)
{
	return have_key;
}

int hwtr_admin_nonce(char *out)
{
	uint8_t v[HWTR_ADMIN_NONCE_LEN];
	k_spinlock_key_t k;

	random_fill(v, sizeof(v));

	k = k_spin_lock(&lock);
	memcpy(nonces[nonce_next].value, v, sizeof(v));
	nonces[nonce_next].until = k_uptime_get() + NONCE_MS;
	nonce_next = (nonce_next + 1) % NONCES;
	k_spin_unlock(&lock, k);

	acl_hex_encode(v, sizeof(v), out);

	return 0;
}

/* A live nonce is used up by this call, whatever the signature says */
static bool nonce_take(const uint8_t *v)
{
	k_spinlock_key_t k = k_spin_lock(&lock);
	int64_t now = k_uptime_get();
	bool found = false;

	for (int i = 0; i < NONCES; i++) {
		if (nonces[i].until > now && memcmp(nonces[i].value, v, HWTR_ADMIN_NONCE_LEN) == 0) {
			nonces[i].until = 0;
			found = true;
			break;
		}
	}
	k_spin_unlock(&lock, k);

	return found;
}

bool hwtr_admin_check(const char *auth, const char *method, const char *path,
		      const uint8_t *body, size_t len)
{
	char nonce_hex[HWTR_ADMIN_NONCE_HEX];
	uint8_t nonce[HWTR_ADMIN_NONCE_LEN];
	uint8_t mac[ACL_MAC_LEN];
	uint8_t want[ACL_MAC_LEN];
	struct acl_hmac h;

	/* "<16 hex>:<64 hex>" */
	if (!have_key || auth == NULL ||
	    strlen(auth) != 2 * HWTR_ADMIN_NONCE_LEN + 1 + 2 * ACL_MAC_LEN ||
	    auth[2 * HWTR_ADMIN_NONCE_LEN] != ':') {
		return false;
	}
	memcpy(nonce_hex, auth, 2 * HWTR_ADMIN_NONCE_LEN);
	nonce_hex[2 * HWTR_ADMIN_NONCE_LEN] = '\0';
	if (acl_hex_decode(nonce_hex, nonce, sizeof(nonce)) != 0 ||
	    acl_hex_decode(&auth[2 * HWTR_ADMIN_NONCE_LEN + 1], mac, sizeof(mac)) != 0 ||
	    !nonce_take(nonce)) {
		return false;
	}

	acl_hmac_init(&h, key, sizeof(key));
	acl_hmac_update(&h, nonce_hex, strlen(nonce_hex));
	acl_hmac_update(&h, "\n", 1);
	acl_hmac_update(&h, method, strlen(method));
	acl_hmac_update(&h, "\n", 1);
	acl_hmac_update(&h, path, strlen(path));
	acl_hmac_update(&h, "\n", 1);
	acl_hmac_update(&h, body, len);
	acl_hmac_final(&h, want);

	return acl_equal(mac, want, sizeof(mac));
}

int hwtr_admin_set_key(const uint8_t *new_key)
{
	memcpy(key, new_key, sizeof(key));
	have_key = true;

	return cfg.save != NULL ? cfg.save(key) : 0;
}

int hwtr_admin_forget(void)
{
	memset(key, 0, sizeof(key));
	have_key = false;
	k_mutex_lock(&claim_lock, K_FOREVER);
	memset(&claim, 0, sizeof(claim));
	k_mutex_unlock(&claim_lock);

	return cfg.save != NULL ? cfg.save(NULL) : 0;
}

int hwtr_admin_claim_start(uint32_t ip, const uint8_t *offered, char *ticket_hex)
{
	if (have_key) {
		return -EALREADY;
	}

	k_mutex_lock(&claim_lock, K_FOREVER);
	memset(&claim, 0, sizeof(claim));
	random_fill(claim.ticket, sizeof(claim.ticket));
	claim.pending = true;
	claim.ip = ip;
	claim.until = k_uptime_get() + claim_ms();
	if (offered != NULL) {
		memcpy(claim.key, offered, sizeof(claim.key));
		claim.offered = true;
	}
	acl_hex_encode(claim.ticket, sizeof(claim.ticket), ticket_hex);
	k_mutex_unlock(&claim_lock);

	LOG_WRN("claim requested: %s within %u s",
		cfg.how_to_confirm ? cfg.how_to_confirm : "press BOOT (short)", claim_ms() / 1000);

	return 0;
}

bool hwtr_admin_claim_pending(void)
{
	return claim.pending && k_uptime_get() < claim.until;
}

int hwtr_admin_claim_confirm(void)
{
	int ret;

	k_mutex_lock(&claim_lock, K_FOREVER);
	if (!hwtr_admin_claim_pending()) {
		k_mutex_unlock(&claim_lock);
		return -ENOENT;
	}
	if (!claim.offered) {
		random_fill(claim.key, sizeof(claim.key));
	}

	ret = hwtr_admin_set_key(claim.key);
	claim.pending = false;
	claim.done = true;
	/* The claimer has this long to collect the key */
	claim.until = k_uptime_get() + claim_ms();
	k_mutex_unlock(&claim_lock);

	LOG_WRN("claimed: admin key set");

	return ret;
}

int hwtr_admin_claim_poll(uint32_t ip, const char *ticket_hex, char *key_hex, int *remaining_s)
{
	uint8_t ticket[HWTR_ADMIN_TICKET_LEN];
	int64_t now = k_uptime_get();
	int ret = 0;

	if (acl_hex_decode(ticket_hex, ticket, sizeof(ticket)) != 0) {
		return -ENOENT;
	}

	k_mutex_lock(&claim_lock, K_FOREVER);
	if ((!claim.pending && !claim.done) || claim.ip != ip ||
	    !acl_equal(ticket, claim.ticket, sizeof(ticket))) {
		ret = -ENOENT;
	} else if (now >= claim.until) {
		memset(&claim, 0, sizeof(claim));
		ret = -ETIMEDOUT;
	} else if (claim.pending) {
		*remaining_s = (int)((claim.until - now + 999) / 1000);
		ret = -EINPROGRESS;
	} else {
		acl_hex_encode(claim.key, sizeof(claim.key), key_hex);
		memset(&claim, 0, sizeof(claim));
	}
	k_mutex_unlock(&claim_lock);

	return ret;
}
