/*
 * Access rules of a bay node (see acl.h).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "acl.h"

static const char *const service_names[ACL_SERVICES] = {
	[ACL_STATUS] = "status",
	[ACL_CONTROL] = "control",
	[ACL_CONSOLE] = "console",
	[ACL_USBIP] = "usbip",
	[ACL_SHELL] = "shell",
};

void acl_init(struct acl_state *s)
{
	memset(s, 0, sizeof(*s));
	s->rules.version = ACL_RULES_VERSION;
	s->rules.everyone = ACL_BIT(ACL_STATUS);
}

static uint32_t mask_of(uint8_t prefix)
{
	return prefix == 0 ? 0 : 0xffffffffU << (32 - prefix);
}

static bool source_matches(const struct acl_source *src, uint32_t ip)
{
	return ip != 0 && (ip & mask_of(src->prefix)) == src->addr;
}

uint8_t acl_rights(const struct acl_rules *r, uint32_t ip)
{
	uint8_t rights = r->everyone;

	if (!r->enabled) {
		return ACL_ALL;
	}
	for (int i = 0; i < r->count && i < ACL_MAX_SOURCES; i++) {
		if (source_matches(&r->src[i], ip)) {
			rights |= r->src[i].allow;
		}
	}

	return rights & ACL_ALL;
}

int acl_source_of(const struct acl_rules *r, uint32_t ip)
{
	int best = -1;

	for (int i = 0; i < r->count && i < ACL_MAX_SOURCES; i++) {
		if (source_matches(&r->src[i], ip) &&
		    (best < 0 || r->src[i].prefix > r->src[best].prefix)) {
			best = i;
		}
	}

	return best;
}

bool acl_lease_active(const struct acl_state *s, int64_t now)
{
	return s->lease.holder != 0 && now < s->lease.until;
}

enum acl_verdict acl_check(const struct acl_state *s, int64_t now, enum acl_service svc,
			   uint32_t ip)
{
	if (svc >= ACL_SERVICES) {
		return ACL_NOT_ALLOWED;
	}
	for (int i = 0; i < ACL_MAX_BLOCKS; i++) {
		const struct acl_block *b = &s->blocks[i];

		if (b->ip != 0 && b->ip == ip && now < b->until && (b->services & ACL_BIT(svc))) {
			return ACL_KICKED;
		}
	}
	if ((ACL_LEASED & ACL_BIT(svc)) && acl_lease_active(s, now) && ip != s->lease.holder) {
		return ACL_RESERVED;
	}
	if (!(acl_rights(&s->rules, ip) & ACL_BIT(svc))) {
		return ACL_NOT_ALLOWED;
	}

	return ACL_OK;
}

int acl_lease_take(struct acl_state *s, int64_t now, uint32_t ip, uint32_t ttl_s,
		   const char *note)
{
	if (ip == 0 || ttl_s < ACL_LEASE_MIN_S || ttl_s > ACL_LEASE_MAX_S) {
		return -EINVAL;
	}
	if (acl_lease_active(s, now) && s->lease.holder != ip) {
		return -EBUSY;
	}

	s->lease.holder = ip;
	s->lease.until = now + (int64_t)ttl_s * 1000;
	acl_copy_text(s->lease.note, sizeof(s->lease.note), note != NULL ? note : "");

	return 0;
}

int acl_lease_release(struct acl_state *s, int64_t now, uint32_t ip, bool force)
{
	if (!acl_lease_active(s, now)) {
		return -ENOENT;
	}
	if (!force && s->lease.holder != ip) {
		return -EPERM;
	}

	memset(&s->lease, 0, sizeof(s->lease));

	return 0;
}

void acl_block(struct acl_state *s, int64_t now, uint32_t ip, uint8_t services, uint32_t ms)
{
	struct acl_block *slot = &s->blocks[0];

	for (int i = 0; i < ACL_MAX_BLOCKS; i++) {
		struct acl_block *b = &s->blocks[i];

		if (b->ip == ip && now < b->until) {
			slot = b;
			services |= b->services;
			break;
		}
		/* A free or expired slot, else the one that ends first */
		if (b->ip == 0 || now >= b->until || b->until < slot->until) {
			slot = b;
		}
	}

	slot->ip = ip;
	slot->services = services;
	slot->until = now + ms;
}

void acl_refused(struct acl_state *s, int64_t now, uint32_t ip, enum acl_service svc,
		 enum acl_verdict why)
{
	struct acl_refusal *slot = &s->log[0];

	s->refused_total++;

	for (int i = 0; i < ACL_LOG_SIZE; i++) {
		struct acl_refusal *e = &s->log[i];

		if (e->ip == ip && e->service == svc && e->reason == why && e->count > 0) {
			if (e->count < UINT16_MAX) {
				e->count++;
			}
			e->last = now;
			return;
		}
		/* A free entry, else the one seen least recently */
		if (slot->count != 0 && (e->count == 0 || e->last < slot->last)) {
			slot = e;
		}
	}

	*slot = (struct acl_refusal){
		.ip = ip, .service = svc, .reason = why, .count = 1, .first = now, .last = now,
	};
}

bool acl_name_valid(const char *name)
{
	size_t len = strlen(name);

	if (len == 0 || len > ACL_NAME_LEN) {
		return false;
	}
	for (size_t i = 0; i < len; i++) {
		char c = name[i];

		if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') ||
		      c == '-' || c == '_' || c == '.')) {
			return false;
		}
	}

	return true;
}

void acl_copy_text(char *dst, size_t size, const char *src)
{
	size_t i;

	if (size == 0) {
		return;
	}
	for (i = 0; i + 1 < size && src[i] != '\0'; i++) {
		char c = src[i];
		bool ok = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
			  (c >= '0' && c <= '9') || strchr(" ._:#/+-", c) != NULL;

		dst[i] = ok ? c : '_';
	}
	dst[i] = '\0';
}

int acl_add_source(struct acl_rules *r, const char *name, uint32_t addr, uint8_t prefix,
		   uint8_t allow)
{
	struct acl_source *src;

	if (!acl_name_valid(name) || prefix > 32 || (allow & ~ACL_ALL) != 0) {
		return -EINVAL;
	}
	if (r->count >= ACL_MAX_SOURCES) {
		return -ENOSPC;
	}

	src = &r->src[r->count++];
	memset(src, 0, sizeof(*src));
	strcpy(src->name, name);
	src->addr = addr & mask_of(prefix);
	src->prefix = prefix;
	src->allow = allow;

	return 0;
}

/* --- Text ------------------------------------------------------------------- */

/* Decimal 0..max, at least one digit, no leading zeros; returns the end or NULL */
static const char *parse_dec(const char *s, unsigned int max, unsigned int *out)
{
	unsigned int v = 0;
	const char *p = s;

	while (*p >= '0' && *p <= '9') {
		v = v * 10 + (unsigned int)(*p - '0');
		p++;
		if (v > max || p - s > 3) {
			return NULL;
		}
	}
	if (p == s || (p - s > 1 && *s == '0')) {
		return NULL;
	}
	*out = v;

	return p;
}

static const char *parse_quad(const char *s, uint32_t *ip)
{
	uint32_t v = 0;

	for (int i = 0; i < 4; i++) {
		unsigned int octet;

		s = parse_dec(s, 255, &octet);
		if (s == NULL || (i < 3 && *s++ != '.')) {
			return NULL;
		}
		v = (v << 8) | octet;
	}
	*ip = v;

	return s;
}

int acl_parse_ip(const char *s, uint32_t *ip)
{
	s = parse_quad(s, ip);

	return (s != NULL && *s == '\0') ? 0 : -EINVAL;
}

int acl_parse_cidr(const char *s, uint32_t *addr, uint8_t *prefix)
{
	unsigned int bits = 32;
	uint32_t ip;

	s = parse_quad(s, &ip);
	if (s == NULL) {
		return -EINVAL;
	}
	if (*s == '/') {
		s = parse_dec(s + 1, 32, &bits);
		if (s == NULL) {
			return -EINVAL;
		}
	}
	if (*s != '\0') {
		return -EINVAL;
	}

	*prefix = (uint8_t)bits;
	*addr = ip & mask_of(*prefix);

	return 0;
}

void acl_format_ip(uint32_t ip, char *out)
{
	snprintf(out, ACL_IP_STR_LEN, "%u.%u.%u.%u", (unsigned int)(ip >> 24),
		 (unsigned int)(ip >> 16) & 0xff, (unsigned int)(ip >> 8) & 0xff,
		 (unsigned int)ip & 0xff);
}

void acl_format_cidr(uint32_t addr, uint8_t prefix, char *out)
{
	acl_format_ip(addr, out);
	if (prefix < 32) {
		size_t len = strlen(out);

		snprintf(&out[len], ACL_CIDR_STR_LEN - len, "/%u", prefix);
	}
}

const char *acl_service_name(enum acl_service svc)
{
	return svc < ACL_SERVICES ? service_names[svc] : "?";
}

uint8_t acl_service_mask(const char *name)
{
	if (strcmp(name, "all") == 0) {
		return ACL_ALL;
	}
	for (int i = 0; i < ACL_SERVICES; i++) {
		if (strcmp(name, service_names[i]) == 0) {
			return ACL_BIT(i);
		}
	}

	return 0;
}

const char *acl_verdict_name(enum acl_verdict v)
{
	switch (v) {
	case ACL_OK:
		return "ok";
	case ACL_RESERVED:
		return "reserved";
	case ACL_KICKED:
		return "kicked";
	default:
		return "not_allowed";
	}
}

/* --- SHA-256 (FIPS 180-4) ----------------------------------------------------- */

static const uint32_t k256[64] = {
	0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4,
	0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe,
	0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f,
	0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
	0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc,
	0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
	0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116,
	0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
	0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
	0xc67178f2,
};

#define ROTR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))

static void sha256_block(struct acl_sha256 *c, const uint8_t *p)
{
	uint32_t w[64];
	uint32_t a = c->h[0], b = c->h[1], d = c->h[3], e = c->h[4];
	uint32_t f = c->h[5], g = c->h[6], h = c->h[7], cc = c->h[2];

	for (int i = 0; i < 16; i++) {
		w[i] = (uint32_t)p[4 * i] << 24 | (uint32_t)p[4 * i + 1] << 16 |
		       (uint32_t)p[4 * i + 2] << 8 | (uint32_t)p[4 * i + 3];
	}
	for (int i = 16; i < 64; i++) {
		uint32_t s0 = ROTR(w[i - 15], 7) ^ ROTR(w[i - 15], 18) ^ (w[i - 15] >> 3);
		uint32_t s1 = ROTR(w[i - 2], 17) ^ ROTR(w[i - 2], 19) ^ (w[i - 2] >> 10);

		w[i] = w[i - 16] + s0 + w[i - 7] + s1;
	}
	for (int i = 0; i < 64; i++) {
		uint32_t s1 = ROTR(e, 6) ^ ROTR(e, 11) ^ ROTR(e, 25);
		uint32_t ch = (e & f) ^ (~e & g);
		uint32_t t1 = h + s1 + ch + k256[i] + w[i];
		uint32_t s0 = ROTR(a, 2) ^ ROTR(a, 13) ^ ROTR(a, 22);
		uint32_t maj = (a & b) ^ (a & cc) ^ (b & cc);
		uint32_t t2 = s0 + maj;

		h = g;
		g = f;
		f = e;
		e = d + t1;
		d = cc;
		cc = b;
		b = a;
		a = t1 + t2;
	}

	c->h[0] += a;
	c->h[1] += b;
	c->h[2] += cc;
	c->h[3] += d;
	c->h[4] += e;
	c->h[5] += f;
	c->h[6] += g;
	c->h[7] += h;
}

void acl_sha256_init(struct acl_sha256 *c)
{
	static const uint32_t iv[8] = {
		0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
		0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
	};

	memcpy(c->h, iv, sizeof(iv));
	c->len = 0;
	c->fill = 0;
}

void acl_sha256_update(struct acl_sha256 *c, const void *data, size_t len)
{
	const uint8_t *p = data;

	c->len += len;
	while (len > 0) {
		size_t n = 64 - c->fill;

		if (n > len) {
			n = len;
		}
		memcpy(&c->buf[c->fill], p, n);
		c->fill += n;
		p += n;
		len -= n;
		if (c->fill == 64) {
			sha256_block(c, c->buf);
			c->fill = 0;
		}
	}
}

void acl_sha256_final(struct acl_sha256 *c, uint8_t out[32])
{
	uint64_t bits = c->len * 8;
	uint8_t pad = 0x80;
	uint8_t len_be[8];

	acl_sha256_update(c, &pad, 1);
	pad = 0;
	while (c->fill != 56) {
		acl_sha256_update(c, &pad, 1);
	}
	for (int i = 0; i < 8; i++) {
		len_be[i] = (uint8_t)(bits >> (56 - 8 * i));
	}
	acl_sha256_update(c, len_be, sizeof(len_be));

	for (int i = 0; i < 8; i++) {
		out[4 * i] = (uint8_t)(c->h[i] >> 24);
		out[4 * i + 1] = (uint8_t)(c->h[i] >> 16);
		out[4 * i + 2] = (uint8_t)(c->h[i] >> 8);
		out[4 * i + 3] = (uint8_t)c->h[i];
	}
}

void acl_hmac_init(struct acl_hmac *h, const uint8_t *key, size_t key_len)
{
	uint8_t block[64] = {0};

	if (key_len > sizeof(block)) {
		acl_sha256_init(&h->inner);
		acl_sha256_update(&h->inner, key, key_len);
		acl_sha256_final(&h->inner, block);
	} else {
		memcpy(block, key, key_len);
	}

	for (size_t i = 0; i < sizeof(block); i++) {
		block[i] ^= 0x36;
	}
	acl_sha256_init(&h->inner);
	acl_sha256_update(&h->inner, block, sizeof(block));

	for (size_t i = 0; i < sizeof(block); i++) {
		block[i] ^= 0x36 ^ 0x5c;
	}
	acl_sha256_init(&h->outer);
	acl_sha256_update(&h->outer, block, sizeof(block));

	memset(block, 0, sizeof(block));
}

void acl_hmac_update(struct acl_hmac *h, const void *data, size_t len)
{
	acl_sha256_update(&h->inner, data, len);
}

void acl_hmac_final(struct acl_hmac *h, uint8_t mac[ACL_MAC_LEN])
{
	uint8_t inner[32];

	acl_sha256_final(&h->inner, inner);
	acl_sha256_update(&h->outer, inner, sizeof(inner));
	acl_sha256_final(&h->outer, mac);
}

bool acl_equal(const void *a, const void *b, size_t len)
{
	const volatile uint8_t *x = a;
	const volatile uint8_t *y = b;
	uint8_t diff = 0;

	for (size_t i = 0; i < len; i++) {
		diff |= x[i] ^ y[i];
	}

	return diff == 0;
}

static int hex_digit(char c)
{
	if (c >= '0' && c <= '9') {
		return c - '0';
	}
	if (c >= 'a' && c <= 'f') {
		return c - 'a' + 10;
	}
	if (c >= 'A' && c <= 'F') {
		return c - 'A' + 10;
	}

	return -1;
}

int acl_hex_decode(const char *hex, uint8_t *out, size_t len)
{
	if (strlen(hex) != 2 * len) {
		return -EINVAL;
	}
	for (size_t i = 0; i < len; i++) {
		int hi = hex_digit(hex[2 * i]);
		int lo = hex_digit(hex[2 * i + 1]);

		if (hi < 0 || lo < 0) {
			return -EINVAL;
		}
		out[i] = (uint8_t)(hi << 4 | lo);
	}

	return 0;
}

void acl_hex_encode(const uint8_t *in, size_t len, char *out)
{
	static const char digits[] = "0123456789abcdef";

	for (size_t i = 0; i < len; i++) {
		out[2 * i] = digits[in[i] >> 4];
		out[2 * i + 1] = digits[in[i] & 0xf];
	}
	out[2 * len] = '\0';
}
