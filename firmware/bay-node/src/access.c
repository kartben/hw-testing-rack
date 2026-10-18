/*
 * Access control: who may use the bay's services, the CI reservation, the
 * admin key.  The rules themselves are in firmware/common/lib/acl.c, the
 * admin key, claim and signatures in firmware/common/lib/admin.c (shared
 * with the power hub); this file applies them.
 *
 *   - TCP to USB/IP, the telnet shell and the AUX ports: Zephyr's packet
 *     filter (local-in hook) drops what the rules refuse, so even servers
 *     that Zephyr runs itself (USB/IP, telnet) never see a refused client;
 *     aux_console.c checks again at accept() (host sockets on native_sim
 *     bypass the filter).
 *   - HTTP: web.c asks for every request (403 or 423 when refused).
 *
 * Admin: whoever holds the node's key.  The first key comes from a claim
 * confirmed by physical presence (a short press on BOOT, or "bay access
 * claim" on the local shell); after that, admin requests carry
 * X-Bay-Auth: <nonce>:<HMAC-SHA256(key, nonce \n method \n path \n body)>,
 * with a single-use nonce from GET /api/access/nonce, so the key itself
 * crosses the network once, at claim time.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/data/json.h>
#include <zephyr/net/net_ip.h>
#include <zephyr/net/socket.h>
#include <zephyr/random/random.h>
#include <zephyr/settings/settings.h>
#include <zephyr/logging/log.h>

#if defined(CONFIG_NET_PKT_FILTER_LOCAL_IN_HOOK)
#include <zephyr/net/net_pkt.h>
#include <zephyr/net/net_pkt_filter.h>
#endif

#if defined(CONFIG_USBIP) || defined(CONFIG_SHELL_BACKEND_TELNET)
#include <zephyr/net/net_context.h>
#define HAS_STACK_SERVERS 1
#endif

#include <hwtr/admin.h>

#include "bay.h"

LOG_MODULE_REGISTER(access, CONFIG_BAY_LOG_LEVEL);

#define CLAIM_MS     (CONFIG_BAY_ACCESS_CLAIM_S * MSEC_PER_SEC)
#define KICK_MS      (CONFIG_BAY_ACCESS_KICK_S * MSEC_PER_SEC)
#define TICKET_LEN   8
#define TICKET_MS    10000
#define TICKETS      2

static struct k_spinlock lock;
static struct acl_state st;

static struct {
	uint8_t value[TICKET_LEN];
	uint32_t ip;
	int64_t until;
} tickets[TICKETS];
static unsigned int ticket_next;


static int64_t now_ms(void)
{
	return k_uptime_get();
}

static void random_fill(void *buf, size_t len)
{
	if (sys_csrand_get(buf, len) != 0) {
		sys_rand_get(buf, len);
	}
}

/* --- Settings: "access/rules", "access/key" ----------------------------------- */

static int access_settings_set(const char *name, size_t len, settings_read_cb read_cb,
			       void *cb_arg)
{
	ssize_t n;

	if (settings_name_steq(name, "rules", NULL)) {
		struct acl_rules r;

		/* A record from another firmware layout is ignored */
		if (len != sizeof(r)) {
			return 0;
		}
		n = read_cb(cb_arg, &r, sizeof(r));
		if (n == sizeof(r) && r.version == ACL_RULES_VERSION &&
		    r.count <= ACL_MAX_SOURCES) {
			st.rules = r;
		}
		return n < 0 ? (int)n : 0;
	}

	if (settings_name_steq(name, "key", NULL)) {
		uint8_t key[ACL_KEY_LEN];

		if (len != sizeof(key)) {
			return 0;
		}
		n = read_cb(cb_arg, key, sizeof(key));
		if (n == sizeof(key)) {
			hwtr_admin_load(key);
		}
		return n < 0 ? (int)n : 0;
	}

	return -ENOENT;
}

SETTINGS_STATIC_HANDLER_DEFINE(access, "access", NULL, access_settings_set, NULL, NULL);

static int save_rules(const struct acl_rules *r)
{
	return settings_save_one("access/rules", r, sizeof(*r));
}

/* hwtr_admin's storage: the key, or NULL to forget it */
static int save_key(const uint8_t *key)
{
	return key != NULL ? settings_save_one("access/key", key, ACL_KEY_LEN)
			   : settings_delete("access/key");
}

/* --- Checks ---------------------------------------------------------------------- */

uint32_t access_ip(const struct net_sockaddr *addr)
{
	if (addr == NULL || addr->sa_family != NET_AF_INET) {
		return 0;
	}

	return net_ntohl(net_sin(addr)->sin_addr.s_addr);
}

uint32_t access_peer(int fd)
{
	struct net_sockaddr_in sa = {0};
	net_socklen_t len = sizeof(sa);

	if (zsock_getpeername(fd, (struct net_sockaddr *)&sa, &len) < 0) {
		return 0;
	}

	return access_ip((struct net_sockaddr *)&sa);
}

enum acl_verdict access_check(enum acl_service svc, uint32_t ip)
{
	k_spinlock_key_t k = k_spin_lock(&lock);
	int64_t now = now_ms();
	enum acl_verdict v = acl_check(&st, now, svc, ip);

	if (v != ACL_OK) {
		acl_refused(&st, now, ip, svc, v);
	}
	k_spin_unlock(&lock, k);

	if (v != ACL_OK) {
		char who[ACL_IP_STR_LEN];

		acl_format_ip(ip, who);
		LOG_INF("refused %s from %s (%s)", acl_service_name(svc), who, acl_verdict_name(v));
	}

	return v;
}

uint8_t access_allowed(uint32_t ip)
{
	k_spinlock_key_t k = k_spin_lock(&lock);
	int64_t now = now_ms();
	uint8_t mask = 0;

	for (int svc = 0; svc < ACL_SERVICES; svc++) {
		if (acl_check(&st, now, svc, ip) == ACL_OK) {
			mask |= ACL_BIT(svc);
		}
	}
	k_spin_unlock(&lock, k);

	return mask;
}

bool access_enabled(void)
{
	return st.rules.enabled != 0;
}

bool access_claimed(void)
{
	return hwtr_admin_claimed();
}

uint32_t access_refused_total(void)
{
	return st.refused_total;
}

/* --- Packet filter: TCP to USB/IP, telnet, the AUX ports ---------------------------- */

static __maybe_unused int service_of_port(uint16_t port)
{
	if (port == 0) {
		return -1;
	}
#if defined(CONFIG_USBIP)
	if (port == CONFIG_USBIP_SERVICE_PORT) {
		return ACL_USBIP;
	}
#endif
#if defined(CONFIG_SHELL_BACKEND_TELNET)
	if (port == CONFIG_SHELL_TELNET_PORT) {
		return ACL_SHELL;
	}
#endif
	if (port == CONFIG_BAY_AUX_TCP_PORT || port == CONFIG_BAY_RFC2217_PORT) {
		return ACL_CONSOLE;
	}

	return -1;
}

#if defined(CONFIG_NET_PKT_FILTER_LOCAL_IN_HOOK)

#define TCP_SYN 0x02
#define TCP_ACK 0x10

/* True: drop the packet */
static bool filter_tcp(struct net_pkt *pkt, void *user_data)
{
	struct net_pkt_cursor backup;
	struct net_ipv4_hdr *ip_hdr;
	uint8_t tcp[14];
	enum acl_verdict v;
	uint32_t ip;
	int svc;
	int ret;

	ARG_UNUSED(user_data);

	if (net_pkt_family(pkt) != NET_AF_INET) {
		return false;
	}
	ip_hdr = NET_IPV4_HDR(pkt);
	if (ip_hdr == NULL || ip_hdr->proto != NET_IPPROTO_TCP) {
		return false;
	}

	/* Source port, destination port, ..., flags: the first 14 bytes */
	net_pkt_cursor_backup(pkt, &backup);
	net_pkt_cursor_init(pkt);
	ret = net_pkt_skip(pkt, net_pkt_ip_hdr_len(pkt) + net_pkt_ipv4_opts_len(pkt));
	if (ret == 0) {
		ret = net_pkt_read(pkt, tcp, sizeof(tcp));
	}
	net_pkt_cursor_restore(pkt, &backup);
	if (ret != 0) {
		return false;
	}

	svc = service_of_port((uint16_t)(tcp[2] << 8 | tcp[3]));
	if (svc < 0) {
		return false;
	}

	ip = (uint32_t)ip_hdr->src[0] << 24 | (uint32_t)ip_hdr->src[1] << 16 |
	     (uint32_t)ip_hdr->src[2] << 8 | ip_hdr->src[3];

	k_spinlock_key_t k = k_spin_lock(&lock);

	v = acl_check(&st, now_ms(), svc, ip);
	/* Log connection attempts, not every segment of a dying connection */
	if (v != ACL_OK && (tcp[13] & (TCP_SYN | TCP_ACK)) == TCP_SYN) {
		acl_refused(&st, now_ms(), ip, svc, v);
	}
	k_spin_unlock(&lock, k);

	return v != ACL_OK;
}

static NPF_LOCAL_IN_MATCH(tcp_refused, filter_tcp, NULL);
static NPF_RULE(drop_refused, NET_DROP, tcp_refused);

#endif /* CONFIG_NET_PKT_FILTER_LOCAL_IN_HOOK */

/* --- Admin key, nonces, signatures, claim: firmware/common/lib/admin.c ----------- */

int access_nonce(char *out)
{
	return hwtr_admin_nonce(out);
}

bool access_admin(const char *auth, const char *method, const char *path, const uint8_t *body,
		  size_t len)
{
	return hwtr_admin_check(auth, method, path, body, len);
}

int access_set_key(const uint8_t *new_key)
{
	return hwtr_admin_set_key(new_key);
}

int access_claim_start(uint32_t ip, const uint8_t *offered, char *ticket_hex)
{
	return hwtr_admin_claim_start(ip, offered, ticket_hex);
}

bool access_claim_pending(void)
{
	return hwtr_admin_claim_pending();
}

int access_claim_confirm(void)
{
	return hwtr_admin_claim_confirm();
}

int access_claim_poll(uint32_t ip, const char *ticket_hex, char *key_hex, int *remaining_s)
{
	return hwtr_admin_claim_poll(ip, ticket_hex, key_hex, remaining_s);
}

/* --- Rules ------------------------------------------------------------------------ */

void access_rules_get(struct acl_rules *r)
{
	k_spinlock_key_t k = k_spin_lock(&lock);

	*r = st.rules;
	k_spin_unlock(&lock, k);
}

static void enforce(void);

int access_rules_set(const struct acl_rules *r)
{
	k_spinlock_key_t k = k_spin_lock(&lock);

	st.rules = *r;
	st.rules.version = ACL_RULES_VERSION;
	k_spin_unlock(&lock, k);

	enforce();

	return save_rules(&st.rules);
}

int access_set_enabled(bool on)
{
	struct acl_rules r;

	access_rules_get(&r);
	r.enabled = on;

	return access_rules_set(&r);
}

/* Back to an unclaimed, open node: the local recovery */
int access_reset(void)
{
	struct acl_state fresh;
	k_spinlock_key_t k;
	int ret;

	acl_init(&fresh);
	k = k_spin_lock(&lock);
	st.rules = fresh.rules;
	memset(&st.lease, 0, sizeof(st.lease));
	memset(st.blocks, 0, sizeof(st.blocks));
	k_spin_unlock(&lock, k);

	ret = hwtr_admin_forget();
	if (ret == 0) {
		ret = save_rules(&st.rules);
	}
	LOG_WRN("access reset: no admin key, no rules");

	return ret;
}

/* --- Lease -------------------------------------------------------------------------- */

int access_lease_take(uint32_t ip, uint32_t ttl_s, const char *note)
{
	k_spinlock_key_t k = k_spin_lock(&lock);
	bool renew = acl_lease_active(&st, now_ms()) && st.lease.holder == ip;
	int ret = acl_lease_take(&st, now_ms(), ip, ttl_s, note);

	k_spin_unlock(&lock, k);

	if (ret == 0 && !renew) {
		char who[ACL_IP_STR_LEN];

		acl_format_ip(ip, who);
		LOG_INF("reserved by %s for %u s", who, ttl_s);
		/* The holder's sessions stay, everyone else's go */
		enforce();
	}

	return ret;
}

int access_lease_release(uint32_t ip, bool force)
{
	k_spinlock_key_t k = k_spin_lock(&lock);
	int ret = acl_lease_release(&st, now_ms(), ip, force);

	k_spin_unlock(&lock, k);

	return ret;
}

bool access_lease_get(struct acl_lease *l, uint32_t *remaining_s)
{
	k_spinlock_key_t k = k_spin_lock(&lock);
	int64_t now = now_ms();
	bool active = acl_lease_active(&st, now);

	*l = st.lease;
	*remaining_s = active ? (uint32_t)((st.lease.until - now + 999) / 1000) : 0;
	k_spin_unlock(&lock, k);

	return active;
}

/* --- Connections, kick ---------------------------------------------------------------- */

#if defined(HAS_STACK_SERVERS)

/* When each connection to a Zephyr-run server was first listed */
static struct {
	uint32_t ip;
	uint16_t port;
	uint8_t svc;
	int64_t since;
} seen[4];

struct stack_scan {
	struct access_conn *out;
	int max;
	int n;
};

static void scan_context(struct net_context *ctx, void *user_data)
{
	struct stack_scan *scan = user_data;
	struct access_conn *c;
	int svc;

	if (scan->n >= scan->max || net_context_get_proto(ctx) != NET_IPPROTO_TCP ||
	    net_context_get_state(ctx) != NET_CONTEXT_CONNECTED ||
	    net_context_get_family(ctx) != NET_AF_INET) {
		return;
	}
	svc = service_of_port(net_ntohs(net_sin(&ctx->local)->sin_port));
	if (svc != ACL_USBIP && svc != ACL_SHELL) {
		return;
	}

	c = &scan->out[scan->n++];
	c->service = svc;
	c->ip = access_ip(&ctx->remote);
	c->port = net_ntohs(net_sin(&ctx->remote)->sin_port);
	c->since = 0;
	snprintf(c->id, sizeof(c->id), "%s:%u", acl_service_name(svc), c->port);
	c->label = svc == ACL_USBIP ? "USB/IP" : "telnet";
}

static int stack_connections(struct access_conn *out, int max)
{
	struct stack_scan scan = {.out = out, .max = max};
	int64_t now = now_ms();

	net_context_foreach(scan_context, &scan);

	/* Keep the first time each was seen, forget the ones that are gone */
	for (int i = 0; i < ARRAY_SIZE(seen); i++) {
		bool live = false;

		for (int j = 0; j < scan.n; j++) {
			live |= seen[i].ip == out[j].ip && seen[i].port == out[j].port &&
				seen[i].svc == out[j].service;
		}
		if (!live) {
			seen[i].ip = 0;
		}
	}
	for (int j = 0; j < scan.n; j++) {
		int free_slot = -1;

		for (int i = 0; i < ARRAY_SIZE(seen); i++) {
			if (seen[i].ip == out[j].ip && seen[i].port == out[j].port &&
			    seen[i].svc == out[j].service) {
				out[j].since = seen[i].since;
				free_slot = -2;
				break;
			}
			if (seen[i].ip == 0 && free_slot == -1) {
				free_slot = i;
			}
		}
		if (free_slot >= 0) {
			seen[free_slot].ip = out[j].ip;
			seen[free_slot].port = out[j].port;
			seen[free_slot].svc = out[j].service;
			seen[free_slot].since = now;
		}
		if (free_slot != -2) {
			out[j].since = now;
		}
	}

	return scan.n;
}

#endif /* HAS_STACK_SERVERS */

int access_connections(struct access_conn *out, int max)
{
	struct aux_client_info aux[2 + CONFIG_BAY_CONSOLE_WEB_CLIENTS];
	int n = aux_clients_get(aux, ARRAY_SIZE(aux));
	int count = 0;

	for (int i = 0; i < n && count < max; i++) {
		struct access_conn *c = &out[count++];

		c->service = ACL_CONSOLE;
		c->ip = aux[i].ip;
		c->port = aux[i].port;
		c->since = aux[i].since;
		if (aux[i].id == AUX_CLIENT_RAW) {
			strcpy(c->id, "raw");
			c->label = "raw TCP";
		} else if (aux[i].id == AUX_CLIENT_RFC2217) {
			strcpy(c->id, "rfc2217");
			c->label = "RFC 2217";
		} else {
			strcpy(c->id, "web0");
			c->id[3] += aux[i].id - AUX_CLIENT_WEB;
			c->label = "web console";
		}
	}

#if defined(HAS_STACK_SERVERS)
	count += stack_connections(&out[count], max - count);
#endif

	return count;
}

#if defined(HAS_STACK_SERVERS)

/* A socket that a Zephyr server owns: SHUT_RD wakes its reader with an EOF */
static int shutdown_peer(int svc, uint32_t ip, uint16_t port)
{
	for (int fd = 0; fd < CONFIG_ZVFS_OPEN_MAX; fd++) {
		struct net_sockaddr_in sa;
		net_socklen_t len = sizeof(sa);

		if (zsock_getsockname(fd, (struct net_sockaddr *)&sa, &len) < 0 ||
		    sa.sin_family != NET_AF_INET ||
		    service_of_port(net_ntohs(sa.sin_port)) != svc) {
			continue;
		}
		len = sizeof(sa);
		if (zsock_getpeername(fd, (struct net_sockaddr *)&sa, &len) < 0 ||
		    access_ip((struct net_sockaddr *)&sa) != ip || net_ntohs(sa.sin_port) != port) {
			continue;
		}

		return zsock_shutdown(fd, ZSOCK_SHUT_RD) < 0 ? -errno : 0;
	}

	return -ENOENT;
}

#endif /* HAS_STACK_SERVERS */

static int close_conn(const struct access_conn *c)
{
	if (strcmp(c->id, "raw") == 0) {
		return aux_client_kick(AUX_CLIENT_RAW);
	}
	if (strcmp(c->id, "rfc2217") == 0) {
		return aux_client_kick(AUX_CLIENT_RFC2217);
	}
	if (strncmp(c->id, "web", 3) == 0) {
		return aux_client_kick(AUX_CLIENT_WEB + (c->id[3] - '0'));
	}
#if defined(HAS_STACK_SERVERS)
	return shutdown_peer(c->service, c->ip, c->port);
#else
	return -ENOENT;
#endif
}

int access_kick(const char *id)
{
	struct access_conn conns[ACCESS_MAX_CONNS];
	int n = access_connections(conns, ARRAY_SIZE(conns));

	for (int i = 0; i < n; i++) {
		if (strcmp(conns[i].id, id) == 0) {
			k_spinlock_key_t k = k_spin_lock(&lock);

			acl_block(&st, now_ms(), conns[i].ip, ACL_BIT(conns[i].service), KICK_MS);
			k_spin_unlock(&lock, k);

			return close_conn(&conns[i]);
		}
	}

	return -ENOENT;
}

/* After a rules change or a new lease: close what is no longer allowed */
static void enforce(void)
{
	struct access_conn conns[ACCESS_MAX_CONNS];
	int n = access_connections(conns, ARRAY_SIZE(conns));

	for (int i = 0; i < n; i++) {
		k_spinlock_key_t k = k_spin_lock(&lock);
		enum acl_verdict v = acl_check(&st, now_ms(), conns[i].service, conns[i].ip);

		k_spin_unlock(&lock, k);
		if (v != ACL_OK) {
			LOG_INF("closing %s (%s)", conns[i].id, acl_verdict_name(v));
			(void)close_conn(&conns[i]);
		}
	}
}

/* --- Web console tickets: a WebSocket has no peer address of its own --------------- */

int access_console_ticket(uint32_t ip, char *out)
{
	uint8_t v[TICKET_LEN];
	k_spinlock_key_t k;

	random_fill(v, sizeof(v));
	k = k_spin_lock(&lock);
	memcpy(tickets[ticket_next].value, v, sizeof(v));
	tickets[ticket_next].ip = ip;
	tickets[ticket_next].until = now_ms() + TICKET_MS;
	ticket_next = (ticket_next + 1) % TICKETS;
	k_spin_unlock(&lock, k);

	acl_hex_encode(v, sizeof(v), out);

	return 0;
}

uint32_t access_console_redeem(const char *hex)
{
	uint8_t v[TICKET_LEN];
	uint32_t ip = 0;
	k_spinlock_key_t k;

	if (acl_hex_decode(hex, v, sizeof(v)) != 0) {
		return 0;
	}

	k = k_spin_lock(&lock);
	for (int i = 0; i < TICKETS; i++) {
		if (tickets[i].until > now_ms() && acl_equal(tickets[i].value, v, sizeof(v))) {
			ip = tickets[i].ip;
			tickets[i].until = 0;
			break;
		}
	}
	k_spin_unlock(&lock, k);

	return ip;
}

/* --- JSON --------------------------------------------------------------------------- */

struct jw {
	char *buf;
	size_t size;
	size_t len;
	bool full;
};

static void jw_add(struct jw *w, const char *fmt, ...)
{
	va_list ap;
	int n;

	if (w->full) {
		return;
	}
	va_start(ap, fmt);
	n = vsnprintf(&w->buf[w->len], w->size - w->len, fmt, ap);
	va_end(ap);
	if (n < 0 || (size_t)n >= w->size - w->len) {
		w->full = true;
		w->buf[w->len] = '\0';
		return;
	}
	w->len += n;
}

static void jw_services(struct jw *w, uint8_t mask)
{
	bool first = true;

	jw_add(w, "[");
	if (mask == ACL_ALL) {
		jw_add(w, "\"all\"");
	} else {
		for (int svc = 0; svc < ACL_SERVICES; svc++) {
			if (mask & ACL_BIT(svc)) {
				jw_add(w, "%s\"%s\"", first ? "" : ",", acl_service_name(svc));
				first = false;
			}
		}
	}
	jw_add(w, "]");
}

int access_json(char *buf, size_t size, uint32_t ip, bool admin)
{
	struct jw w = {.buf = buf, .size = size};
	/* The web server calls this, one request at a time: keep its stack small */
	static struct access_conn conns[ACCESS_MAX_CONNS];
	static struct acl_rules rules;
	struct acl_lease lease;
	uint32_t remaining;
	char a[ACL_CIDR_STR_LEN];
	int64_t now = now_ms();
	int n = access_connections(conns, ARRAY_SIZE(conns));
	int src;

	access_rules_get(&rules);
	src = acl_source_of(&rules, ip);
	acl_format_ip(ip, a);
	jw_add(&w, "{\"enabled\":%s,\"claimed\":%s,\"admin\":%s,\"you\":\"%s\",\"source\":\"%s\","
		   "\"allow\":",
	       rules.enabled ? "true" : "false", hwtr_admin_claimed() ? "true" : "false",
	       admin ? "true" : "false", a, src >= 0 ? rules.src[src].name : "");
	jw_services(&w, access_allowed(ip));

	if (access_lease_get(&lease, &remaining)) {
		acl_format_ip(lease.holder, a);
		jw_add(&w, ",\"lease\":{\"holder\":\"%s\",\"note\":\"%s\",\"remaining_s\":%u,"
			   "\"yours\":%s}",
		       a, lease.note, remaining, lease.holder == ip ? "true" : "false");
	} else {
		jw_add(&w, ",\"lease\":null");
	}

	jw_add(&w, ",\"connections\":[");
	for (int i = 0; i < n; i++) {
		acl_format_ip(conns[i].ip, a);
		jw_add(&w, "%s{\"id\":\"%s\",\"service\":\"%s\",\"label\":\"%s\",\"peer\":\"%s\","
			   "\"port\":%u,\"since_s\":%u}",
		       i ? "," : "", conns[i].id, acl_service_name(conns[i].service),
		       conns[i].label, a, conns[i].port, (uint32_t)((now - conns[i].since) / 1000));
	}
	jw_add(&w, "],\"refused_total\":%u,\"claim\":\"%s\"", st.refused_total,
	       access_claim_pending() ? "pending" : "none");

	if (admin) {
		static struct acl_refusal log[ACL_LOG_SIZE];
		bool first = true;
		k_spinlock_key_t k;

		jw_add(&w, ",\"rules\":{\"everyone\":");
		jw_services(&w, rules.everyone);
		jw_add(&w, ",\"sources\":[");
		for (int i = 0; i < rules.count; i++) {
			acl_format_cidr(rules.src[i].addr, rules.src[i].prefix, a);
			jw_add(&w, "%s{\"name\":\"%s\",\"cidr\":\"%s\",\"allow\":", i ? "," : "",
			       rules.src[i].name, a);
			jw_services(&w, rules.src[i].allow);
			jw_add(&w, "}");
		}
		jw_add(&w, "]}");

		k = k_spin_lock(&lock);
		memcpy(log, st.log, sizeof(log));
		k_spin_unlock(&lock, k);

		/* Most recent first, as many as fit */
		jw_add(&w, ",\"refused\":[");
		while (!w.full && w.size - w.len > 128) {
			int best = -1;

			for (int i = 0; i < ACL_LOG_SIZE; i++) {
				if (log[i].count > 0 &&
				    (best < 0 || log[i].last > log[best].last)) {
					best = i;
				}
			}
			if (best < 0) {
				break;
			}
			acl_format_ip(log[best].ip, a);
			jw_add(&w, "%s{\"ip\":\"%s\",\"service\":\"%s\",\"reason\":\"%s\","
				   "\"count\":%u,\"first_s\":%u,\"last_s\":%u}",
			       first ? "" : ",", a, acl_service_name(log[best].service),
			       acl_verdict_name(log[best].reason), log[best].count,
			       (uint32_t)((now - log[best].first) / 1000),
			       (uint32_t)((now - log[best].last) / 1000));
			log[best].count = 0;
			first = false;
		}
		jw_add(&w, "]");
	}
	jw_add(&w, "}");

	return w.full ? -ENOMEM : (int)w.len;
}

/* POST /api/access/rules */

struct src_req {
	char *name;
	char *cidr;
	char *allow[ACL_SERVICES + 1];
	size_t allow_len;
};

struct rules_req {
	bool enabled;
	char *everyone[ACL_SERVICES + 1];
	size_t everyone_len;
	struct src_req sources[ACL_MAX_SOURCES];
	size_t sources_len;
};

static const struct json_obj_descr src_descr[] = {
	JSON_OBJ_DESCR_PRIM(struct src_req, name, JSON_TOK_STRING),
	JSON_OBJ_DESCR_PRIM(struct src_req, cidr, JSON_TOK_STRING),
	JSON_OBJ_DESCR_ARRAY(struct src_req, allow, ACL_SERVICES + 1, allow_len, JSON_TOK_STRING),
};

static const struct json_obj_descr rules_descr[] = {
	JSON_OBJ_DESCR_PRIM(struct rules_req, enabled, JSON_TOK_TRUE),
	JSON_OBJ_DESCR_ARRAY(struct rules_req, everyone, ACL_SERVICES + 1, everyone_len,
			     JSON_TOK_STRING),
	JSON_OBJ_DESCR_OBJ_ARRAY(struct rules_req, sources, ACL_MAX_SOURCES, sources_len,
				 src_descr, ARRAY_SIZE(src_descr)),
};

static int services_of(char *const *names, size_t n, uint8_t *mask)
{
	*mask = 0;
	for (size_t i = 0; i < n; i++) {
		uint8_t m = acl_service_mask(names[i]);

		if (m == 0) {
			return -EINVAL;
		}
		*mask |= m;
	}

	return 0;
}

const char *access_rules_parse(char *body, size_t len, struct acl_rules *out)
{
	static struct rules_req req;
	int fields;

	memset(&req, 0, sizeof(req));
	fields = json_obj_parse(body, len, rules_descr, ARRAY_SIZE(rules_descr), &req);
	if (fields < 0) {
		return "bad JSON (at most 8 sources)";
	}

	/* Fields left out keep their current value */
	access_rules_get(out);
	if (fields & BIT(0)) {
		out->enabled = req.enabled;
	}
	if ((fields & BIT(1)) && services_of(req.everyone, req.everyone_len, &out->everyone) != 0) {
		return "everyone: services are status, control, console, usbip, shell or all";
	}
	if (fields & BIT(2)) {
		out->count = 0;
		for (size_t i = 0; i < req.sources_len; i++) {
			const struct src_req *s = &req.sources[i];
			uint32_t addr;
			uint8_t prefix;
			uint8_t allow;

			if (s->name == NULL || !acl_name_valid(s->name)) {
				return "source name: 1-15 letters, digits, '.', '_' or '-'";
			}
			if (s->cidr == NULL || acl_parse_cidr(s->cidr, &addr, &prefix) != 0) {
				return "source cidr: a.b.c.d or a.b.c.d/n";
			}
			if (services_of(s->allow, s->allow_len, &allow) != 0) {
				return "source allow: status, control, console, usbip, shell, all";
			}
			(void)acl_add_source(out, s->name, addr, prefix, allow);
		}
	}

	return NULL;
}

/* --- Init ------------------------------------------------------------------------------ */

int access_init(void)
{
	static const struct hwtr_admin_cfg admin = {
		.claim_ms = CLAIM_MS,
		.save = save_key,
		.how_to_confirm = "press BOOT (short) or run \"bay access claim\"",
	};

	hwtr_admin_init(&admin);

	/* acl_init() before settings_load() would wipe what it loaded: only fill the gaps */
	if (st.rules.version != ACL_RULES_VERSION) {
		struct acl_state fresh;

		acl_init(&fresh);
		st.rules = fresh.rules;
	}

#if defined(CONFIG_NET_PKT_FILTER_LOCAL_IN_HOOK)
	npf_append_local_in_recv_rule(&drop_refused);
	npf_append_local_in_recv_rule(&npf_default_ok);
#endif

	LOG_INF("access: %s, %s, %u source(s)", hwtr_admin_claimed() ? "claimed" : "not claimed",
		st.rules.enabled ? "rules on" : "rules off", st.rules.count);

	return 0;
}
