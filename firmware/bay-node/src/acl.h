/*
 * Access rules of a bay node: who may use which service, the CI reservation
 * (lease), short blocks after a kick, the log of refused connections, and the
 * HMAC-SHA256 that signs admin requests.
 *
 * Plain C, no Zephyr: access.c feeds it the addresses seen by the packet
 * filter, the sockets and the web server, tests/acl builds it on the host.
 * A rack controller pushing rules over CAN would reuse it as is.
 *
 * Addresses are IPv4 in host byte order (192.168.1.23 is 0xc0a80117), times
 * are milliseconds of uptime.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef ACL_H_
#define ACL_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define ACL_MAX_SOURCES 8
#define ACL_NAME_LEN    15
#define ACL_NOTE_LEN    39
#define ACL_LOG_SIZE    16
#define ACL_MAX_BLOCKS  4
#define ACL_KEY_LEN     32
#define ACL_MAC_LEN     32

enum acl_service {
	ACL_STATUS,  /* the page, /api/status, /api/aux, /metrics */
	ACL_CONTROL, /* power, reset, boot, mode, AUX settings, taking a lease */
	ACL_CONSOLE, /* web console, raw AUX port, RFC 2217 */
	ACL_USBIP,   /* USB/IP */
	ACL_SHELL,   /* telnet shell */
	ACL_SERVICES,
};

#define ACL_BIT(svc) (1U << (svc))
#define ACL_ALL      ((1U << ACL_SERVICES) - 1)
/* What a lease keeps for its holder */
#define ACL_LEASED   (ACL_BIT(ACL_CONTROL) | ACL_BIT(ACL_CONSOLE) | ACL_BIT(ACL_USBIP))

enum acl_verdict {
	ACL_OK,
	ACL_NOT_ALLOWED, /* no rule gives this address the service */
	ACL_RESERVED,    /* another address holds the lease */
	ACL_KICKED,      /* kicked by an admin a moment ago */
};

struct acl_source {
	char name[ACL_NAME_LEN + 1];
	uint32_t addr;
	uint8_t prefix; /* 0..32 */
	uint8_t allow;  /* ACL_BIT() mask */
};

/* Saved as is in the node's settings: bump ACL_RULES_VERSION with the layout */
#define ACL_RULES_VERSION 1

struct acl_rules {
	uint8_t version;
	uint8_t enabled;  /* 0: every address may use every service */
	uint8_t everyone; /* services of addresses no source matches */
	uint8_t count;
	struct acl_source src[ACL_MAX_SOURCES];
};

struct acl_lease {
	uint32_t holder; /* 0: none */
	int64_t until;
	char note[ACL_NOTE_LEN + 1];
};

struct acl_block {
	uint32_t ip; /* 0: free */
	uint8_t services;
	int64_t until;
};

struct acl_refusal {
	uint32_t ip; /* 0: free */
	uint8_t service;
	uint8_t reason; /* enum acl_verdict */
	uint16_t count;
	int64_t first;
	int64_t last;
};

struct acl_state {
	struct acl_rules rules;
	struct acl_lease lease;
	struct acl_block blocks[ACL_MAX_BLOCKS];
	struct acl_refusal log[ACL_LOG_SIZE];
	uint32_t refused_total;
};

/* Open (rules disabled, everyone gets status only once enabled), no lease */
void acl_init(struct acl_state *s);

/* Services the rules give an address (all of them while the rules are off) */
uint8_t acl_rights(const struct acl_rules *r, uint32_t ip);
/* The most specific source matching an address, or -1 */
int acl_source_of(const struct acl_rules *r, uint32_t ip);
/* May this address open (or keep) a connection to this service now? */
enum acl_verdict acl_check(const struct acl_state *s, int64_t now, enum acl_service svc,
			   uint32_t ip);

bool acl_lease_active(const struct acl_state *s, int64_t now);
/* Take or renew; -EBUSY while another address holds it, -EINVAL for a bad ttl */
int acl_lease_take(struct acl_state *s, int64_t now, uint32_t ip, uint32_t ttl_s,
		   const char *note);
/* By its holder, or anyone with force (admin); -ENOENT none, -EPERM not yours */
int acl_lease_release(struct acl_state *s, int64_t now, uint32_t ip, bool force);
#define ACL_LEASE_MIN_S 10
#define ACL_LEASE_MAX_S 86400

/* Refuse these services to an address for a while (after a kick) */
void acl_block(struct acl_state *s, int64_t now, uint32_t ip, uint8_t services, uint32_t ms);
/* Log a refusal; the same address, service and reason add up in one entry */
void acl_refused(struct acl_state *s, int64_t now, uint32_t ip, enum acl_service svc,
		 enum acl_verdict why);

/* Rules editing: 0, or -EINVAL (bad name, prefix or mask), -ENOSPC (full) */
int acl_add_source(struct acl_rules *r, const char *name, uint32_t addr, uint8_t prefix,
		   uint8_t allow);

/* "a.b.c.d": 0 or -EINVAL */
int acl_parse_ip(const char *s, uint32_t *ip);
/* "a.b.c.d" or "a.b.c.d/n" (host bits cleared): 0 or -EINVAL */
int acl_parse_cidr(const char *s, uint32_t *addr, uint8_t *prefix);
#define ACL_IP_STR_LEN   16 /* "255.255.255.255" */
#define ACL_CIDR_STR_LEN 19 /* "255.255.255.255/32" */
void acl_format_ip(uint32_t ip, char *out);
/* No "/32" for a single host */
void acl_format_cidr(uint32_t addr, uint8_t prefix, char *out);

const char *acl_service_name(enum acl_service svc);
/* A service name, or "all": its ACL_BIT() mask, 0 when unknown */
uint8_t acl_service_mask(const char *name);
const char *acl_verdict_name(enum acl_verdict v);

/* Lease notes keep [A-Za-z0-9 ._:#/+-], anything else becomes '_' (safe in JSON) */
void acl_copy_text(char *dst, size_t size, const char *src);
/* Source names: 1..ACL_NAME_LEN of [A-Za-z0-9._-] */
bool acl_name_valid(const char *name);

/* --- SHA-256, HMAC-SHA256 ------------------------------------------------- */

struct acl_sha256 {
	uint32_t h[8];
	uint64_t len;
	uint8_t buf[64];
	size_t fill;
};

void acl_sha256_init(struct acl_sha256 *c);
void acl_sha256_update(struct acl_sha256 *c, const void *data, size_t len);
void acl_sha256_final(struct acl_sha256 *c, uint8_t out[32]);

struct acl_hmac {
	struct acl_sha256 inner;
	struct acl_sha256 outer;
};

void acl_hmac_init(struct acl_hmac *h, const uint8_t *key, size_t key_len);
void acl_hmac_update(struct acl_hmac *h, const void *data, size_t len);
void acl_hmac_final(struct acl_hmac *h, uint8_t mac[ACL_MAC_LEN]);

/* Constant time */
bool acl_equal(const void *a, const void *b, size_t len);
/* Exactly 2 * len hex digits: 0 or -EINVAL */
int acl_hex_decode(const char *hex, uint8_t *out, size_t len);
/* out: 2 * len + 1 bytes */
void acl_hex_encode(const uint8_t *in, size_t len, char *out);

#endif /* ACL_H_ */
