/*
 * Flat functions over acl.c for test_acl.py (ctypes): one access state,
 * addresses as dotted strings, no structs across the boundary.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdio.h>
#include <string.h>

#include <hwtr/acl.h>

#if defined(_WIN32)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

static struct acl_state st;

static uint32_t ip_of(const char *s)
{
	uint32_t ip = 0;

	(void)acl_parse_ip(s, &ip);

	return ip;
}

EXPORT void shim_reset(void)
{
	acl_init(&st);
}

EXPORT void shim_rules(int enabled, int everyone)
{
	st.rules.enabled = (uint8_t)enabled;
	st.rules.everyone = (uint8_t)everyone;
}

EXPORT int shim_add(const char *name, const char *cidr, int allow)
{
	uint32_t addr;
	uint8_t prefix;

	if (acl_parse_cidr(cidr, &addr, &prefix) != 0) {
		return -1000;
	}

	return acl_add_source(&st.rules, name, addr, prefix, (uint8_t)allow);
}

EXPORT int shim_rights(const char *ip)
{
	return acl_rights(&st.rules, ip_of(ip));
}

EXPORT int shim_source_of(const char *ip)
{
	return acl_source_of(&st.rules, ip_of(ip));
}

EXPORT int shim_check(long long now, int svc, const char *ip)
{
	return acl_check(&st, now, (enum acl_service)svc, ip_of(ip));
}

EXPORT int shim_lease_take(long long now, const char *ip, unsigned int ttl_s, const char *note)
{
	return acl_lease_take(&st, now, ip_of(ip), ttl_s, note);
}

EXPORT int shim_lease_release(long long now, const char *ip, int force)
{
	return acl_lease_release(&st, now, ip_of(ip), force != 0);
}

EXPORT const char *shim_lease_note(void)
{
	return st.lease.note;
}

EXPORT void shim_block(long long now, const char *ip, int services, unsigned int ms)
{
	acl_block(&st, now, ip_of(ip), (uint8_t)services, ms);
}

EXPORT void shim_refused(long long now, const char *ip, int svc, int why)
{
	acl_refused(&st, now, ip_of(ip), (enum acl_service)svc, (enum acl_verdict)why);
}

EXPORT unsigned int shim_refused_total(void)
{
	return st.refused_total;
}

/* Entry i of the log: "ip service reason count first last", "" when free */
EXPORT void shim_log(int i, char *out, size_t size)
{
	const struct acl_refusal *e = &st.log[i];
	char ip[ACL_IP_STR_LEN];

	if (e->count == 0) {
		out[0] = '\0';
		return;
	}
	acl_format_ip(e->ip, ip);
	snprintf(out, size, "%s %s %s %u %lld %lld", ip,
		 acl_service_name((enum acl_service)e->service),
		 acl_verdict_name((enum acl_verdict)e->reason), e->count, (long long)e->first,
		 (long long)e->last);
}

/* The parsed CIDR formatted back, or the error */
EXPORT int shim_cidr(const char *in, char *out)
{
	uint32_t addr;
	uint8_t prefix;
	int ret = acl_parse_cidr(in, &addr, &prefix);

	if (ret == 0) {
		acl_format_cidr(addr, prefix, out);
	}

	return ret;
}

EXPORT int shim_ip(const char *in, char *out)
{
	uint32_t ip;
	int ret = acl_parse_ip(in, &ip);

	if (ret == 0) {
		acl_format_ip(ip, out);
	}

	return ret;
}

EXPORT int shim_service_mask(const char *name)
{
	return acl_service_mask(name);
}

EXPORT void shim_copy_text(const char *in, char *out, size_t size)
{
	acl_copy_text(out, size, in);
}

EXPORT int shim_name_valid(const char *name)
{
	return acl_name_valid(name);
}

EXPORT void shim_sha256(const unsigned char *data, size_t len, size_t chunk, unsigned char *out)
{
	struct acl_sha256 c;

	acl_sha256_init(&c);
	for (size_t off = 0; off < len; off += chunk) {
		acl_sha256_update(&c, data + off, len - off < chunk ? len - off : chunk);
	}
	acl_sha256_final(&c, out);
}

EXPORT void shim_hmac(const unsigned char *key, size_t key_len, const unsigned char *msg,
		      size_t len, unsigned char *out)
{
	struct acl_hmac h;

	acl_hmac_init(&h, key, key_len);
	acl_hmac_update(&h, msg, len);
	acl_hmac_final(&h, out);
}

EXPORT int shim_equal(const unsigned char *a, const unsigned char *b, size_t len)
{
	return acl_equal(a, b, len);
}

EXPORT int shim_hex_decode(const char *hex, unsigned char *out, size_t len)
{
	return acl_hex_decode(hex, out, len);
}

EXPORT void shim_hex_encode(const unsigned char *in, size_t len, char *out)
{
	acl_hex_encode(in, len, out);
}
