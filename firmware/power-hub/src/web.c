/*
 * The hub's web page, JSON API and Prometheus /metrics (HTTP/1.1, port 80).
 *
 *   GET  /                 status page (web/index.html, gzipped in flash)
 *   GET  /api/status       PD contract and offers, rows, nodes, rack bus
 *   GET  /api/events       recent events, newest first
 *   POST /api/row          {"row": "A", "action": "on" | "off" | "cycle", "ms": 2000}
 *   POST /api/pd           {"pref": "epr" | "20v"}
 *   POST /api/enumerate    {}
 *   POST /api/node         {"id": 35, "action": "identify" | "reset" | "bootloader" |
 *                           "power-on" | "power-off" | "power-cycle" | "reboot"}
 *   GET  /metrics          Prometheus text format
 *   GET  /api/access/nonce single-use nonce for an admin request
 *   POST /api/access/claim {} | {"key": "<hex>"}, then {"ticket": "<hex>"} until claimed
 *   POST /api/access/check {}: 200 if signed with the admin key, else 403
 *   GET  /api/update       the firmware; POST /api/update/begin, /api/update: an
 *                          update over the network (firmware/common/web/update_http.c)
 *
 * Reading is open; every POST but the claim is an admin request, signed with
 * the hub's admin key (X-Bay-Auth, firmware/common/lib/admin.c), as on the
 * bay nodes.  The first key comes from a claim confirmed with a press on the
 * hub's BOOT button.
 *
 * The JSON is written by hand: nested arrays of rows and nodes.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>

#include <zephyr/kernel.h>
#include <zephyr/data/json.h>
#include <zephyr/net/hostname.h>
#include <zephyr/net/http/server.h>
#include <zephyr/net/http/service.h>
#include <zephyr/net/socket.h>
#include <zephyr/logging/log.h>
#include <zephyr/app_version.h>

#include <hwtr/admin.h>
#include <hwtr/net.h>
#include <hwtr/update.h>
#include <hwtr/web.h>

#include "hub.h"

LOG_MODULE_REGISTER(web, CONFIG_HUB_LOG_LEVEL);

/* Responses are built in the HTTP server thread, one at a time */
static char resp_buf[6144];

/* X-Bay-Auth, kept from the first callback of a request */
HWTR_WEB_AUTH_CAPTURE(hub_auth_header);

static void capture_auth(const struct http_request_ctx *req, char *out, size_t size)
{
	if (req->headers_status == HTTP_HEADER_STATUS_NONE) {
		return;
	}
	out[0] = '\0';
	for (size_t i = 0; i < req->header_count; i++) {
		if (strcasecmp(req->headers[i].name, "X-Bay-Auth") == 0) {
			strncpy(out, req->headers[i].value, size - 1);
			out[size - 1] = '\0';
		}
	}
}

static uint32_t peer_ip(int fd)
{
	struct net_sockaddr_in sa = {0};
	net_socklen_t len = sizeof(sa);

	if (zsock_getpeername(fd, (struct net_sockaddr *)&sa, &len) < 0 ||
	    sa.sin_family != NET_AF_INET) {
		return 0;
	}
	return net_ntohl(sa.sin_addr.s_addr);
}

/* --- A tiny JSON / text writer ---------------------------------------------- */

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

static void respond(struct http_response_ctx *rsp, struct out *o)
{
	if (o->overflow) {
		rsp->status = HTTP_500_INTERNAL_SERVER_ERROR;
		strcpy(resp_buf, "{\"error\":\"response too large\"}");
		o->len = strlen(resp_buf);
	}
	rsp->body = resp_buf;
	rsp->body_len = o->len;
	rsp->final_chunk = true;
}

static void respond_error(struct http_response_ctx *rsp, enum http_status status,
			  const char *msg)
{
	struct out o = {resp_buf, sizeof(resp_buf)};

	put(&o, "{\"error\":\"%s\"}", msg);
	rsp->status = status;
	respond(rsp, &o);
}

/* --- /api/status ------------------------------------------------------------ */

static const char *node_state(const struct rack_hub_node *n)
{
	uint8_t f = n->status.flags;

	switch (n->state) {
	case RACK_NODE_LOST:
		return "lost";
	case RACK_NODE_FAILED:
		return "failed";
	case RACK_NODE_INCOMPATIBLE:
		return "incompatible";
	default:
		break;
	}
	if (!n->have_status) {
		return "usbip";
	}
	if (f & RACK_ST_DUT_FAULT) {
		return "fault";
	}
	if (f & RACK_ST_SERVICE) {
		return "service";
	}
	if (f & RACK_ST_CLASSIC) {
		return "classic";
	}
	if (!(f & RACK_ST_DUT_ON)) {
		return "off";
	}
	if (f & RACK_ST_USBIP) {
		return "attached";
	}
	return (f & RACK_ST_USB_DEVICE) ? "enumerated" : "usbip";
}

/* The bay's camera, from its STATUS (nodes before the camera say nothing) */
static const char *node_camera(const struct rack_hub_node *n)
{
	uint8_t f = n->status.flags2;

	if (!n->have_status || !(f & RACK_ST2_CAMERA)) {
		return "none";
	}
	return (f & RACK_ST2_CAMERA_ON) ? "active" : "ready";
}

static const char *pdo_type(enum ch224a_pdo_type t)
{
	static const char *const names[] = {"none", "fixed", "pps", "avs", "other"};

	return names[t];
}

static void write_pd(struct out *o, const struct hub_pd_status *pd)
{
	static const char *const states[] = {"usb", "starting", "spr", "epr"};
	uint32_t max_mw = 0;
	bool first = true;

	put(o, "\"pd\":{\"state\":\"%s\",\"pref\":\"%s\",\"final\":%s,", states[pd->state],
	    pd->epr_pref ? "epr" : "20v", pd->final ? "true" : "false");
	if (pd->contract_mv != 0) {
		put(o, "\"contract\":{\"mv\":%u,\"ma\":%u,\"epr\":%s,\"pdo\":%d},", pd->contract_mv,
		    pd->contract_ma, pd->state == HUB_PD_EPR ? "true" : "false", pd->selected);
	} else {
		put(o, "\"contract\":null,");
	}
	/* The sink measures nothing: VBUS from the ADC, the current from the rows' IMON */
	put(o, "\"vbus_mv\":%u,\"rows_ma\":%d,\"asked_mv\":%u,\"granted_ma\":%u,\"pg\":%s,"
	    "\"epr_refused\":%s,\"pdos\":[",
	    pd->vbus_mv, rows_total_ma(), pd->asked_mv, pd->granted_ma,
	    pd->power_good ? "true" : "false", pd->epr_refused ? "true" : "false");
	for (int i = 0; i < CH224A_PDO_COUNT; i++) {
		const struct ch224a_pdo *p = &pd->pdos[i];

		if (p->type == CH224A_PDO_NONE || p->type == CH224A_PDO_OTHER) {
			continue;
		}
		max_mw = MAX(max_mw, p->type == CH224A_PDO_AVS ? p->pdp_w * 1000U
							       : p->max_mv * p->max_ma / 1000);
		put(o, "%s{\"index\":%d,\"type\":\"%s\",\"mv\":%u,\"mv_min\":%u,\"ma\":%u,\"epr\":%s",
		    first ? "" : ",", i + 1, pdo_type(p->type), p->max_mv, p->min_mv, p->max_ma,
		    p->epr ? "true" : "false");
		if (p->type == CH224A_PDO_AVS) {
			put(o, ",\"w\":%u", p->pdp_w);
		}
		if (i + 1 == pd->selected) {
			put(o, ",\"selected\":true");
		} else if (p->max_mv > 28000) {
			put(o, ",\"refused\":\"above 28 V\"");
		}
		put(o, "}");
		first = false;
	}
	put(o, "],\"max_mw\":%u}", max_mw);
}

static void write_nodes(struct out *o, int row, uint32_t now)
{
	static struct rack_hub_node nodes[RACK_POSITIONS + 1];
	bool first = true;
	char name[4];

	(void)bus_row_nodes(row, nodes);
	for (int p = 1; p <= RACK_POSITIONS; p++) {
		const struct rack_hub_node *n = &nodes[p];
		uint8_t id = RACK_NODE_ID(row, p);

		if (n->state == RACK_NODE_NONE) {
			continue;
		}
		put(o, "%s{\"id\":%u,\"pos\":\"%s\",\"name\":\"\",\"ip\":\"%u.%u.%u.%u\","
		       "\"state\":\"%s\",\"camera\":\"%s\",\"dut_ma\":%u,\"dut_mv\":%u,"
		       "\"seen_s\":%u,\"version\":\"%u.%u.%u\","
		       "\"mac\":\"%02x:%02x:%02x:%02x:%02x:%02x\"}",
		    first ? "" : ",", id, rack_node_name(id, name), n->info.ipv4[0], n->info.ipv4[1],
		    n->info.ipv4[2], n->info.ipv4[3], node_state(n), node_camera(n),
		    n->status.dut_ma == RACK_NO_READING ? 0 : n->status.dut_ma,
		    n->status.dut_mv == RACK_NO_READING ? 0 : n->status.dut_mv,
		    (now - n->seen_ms) / 1000, n->info.fw[0], n->info.fw[1],
		    n->info.fw[2], n->mac[0], n->mac[1], n->mac[2], n->mac[3], n->mac[4], n->mac[5]);
		first = false;
	}
}

static void respond_status(struct http_response_ctx *rsp)
{
	static const char *const can_states[] = {"error-active", "error-warning", "error-passive",
						 "bus-off", "stopped"};
	struct out o = {resp_buf, sizeof(resp_buf)};
	struct hub_pd_status pd;
	struct hub_bus_status bus;
	int64_t now = k_uptime_get();
	uint32_t used_mw = 0;

	pd_status(&pd);
	bus_status(&bus);

	put(&o, "{\"hostname\":\"%s\",\"ip\":\"%s\",\"version\":\"%s\",\"uptime_s\":%u,"
		"\"access\":{\"claimed\":%s,\"claim_pending\":%s},",
	    net_hostname_get(), hwtr_net_addr(), APP_VERSION_STRING, (uint32_t)(now / 1000),
	    hwtr_admin_claimed() ? "true" : "false", hwtr_admin_claim_pending() ? "true" : "false");
	write_pd(&o, &pd);

	put(&o, ",\"rows\":[");
	for (int r = 0; r < HUB_ROWS; r++) {
		struct hub_row_status st;
		uint32_t mw;
		bool on;

		rows_status(r, &st);
		on = st.state == HUB_ROW_ON;
		mw = on ? (uint32_t)st.ma * pd.contract_mv / 1000 : 0;
		used_mw += mw;
		put(&o, "%s{\"name\":\"%c\",\"state\":\"%s\",\"on\":%s,\"wanted\":%s,\"fault\":%s,"
			"\"faults\":%u,\"ma\":%d,\"mw\":%u,\"nodes\":[",
		    r ? "," : "", 'A' + r, st.fault ? "fault" : rows_state_str(st.state),
		    on ? "true" : "false", st.wanted ? "true" : "false", st.fault ? "true" : "false",
		    st.faults, st.ma, mw);
		write_nodes(&o, r, (uint32_t)now);
		put(&o, "]}");
	}

	put(&o, "],\"budget\":{\"contract_mw\":%u,\"used_mw\":%u,\"shed_order\":\"%s\"},",
	    pd.contract_mv * pd.contract_ma / 1000, used_mw, rows_shed_order());
	put(&o, "\"can\":{\"state\":\"%s\",\"bitrate\":%u,\"nodes\":%d,\"lost\":%d,\"rx_fps\":%u,"
		"\"errors\":%u,\"tx_errors\":%u,\"bus_off\":%u,\"enumerating\":%s,"
		"\"enumerated_s\":%d,\"enumerations\":%u}",
	    can_states[MIN(bus.state, ARRAY_SIZE(can_states) - 1)], RACK_BITRATE, bus.nodes,
	    bus.lost, bus.rx_fps, bus.err.rx_err_cnt + bus.err.tx_err_cnt, bus.tx_errors,
	    bus.bus_off, bus.enumerating ? "true" : "false",
	    bus.enumerated_ms ? (int)((now - bus.enumerated_ms) / 1000) : -1, bus.enumerations);
#if defined(CONFIG_HWTR_UPDATE)
	put(&o, ",\"firmware\":");
	if (!o.overflow) {
		int n = hwtr_update_json(o.buf + o.len, o.size - o.len);

		if (n < 0) {
			o.overflow = true;
		} else {
			o.len += n;
		}
	}
#endif
	put(&o, "}");

	respond(rsp, &o);
}

static int status_handler(struct http_client_ctx *client, enum http_transaction_status status,
			  const struct http_request_ctx *req, struct http_response_ctx *rsp,
			  void *user_data)
{
	ARG_UNUSED(client);
	ARG_UNUSED(req);
	ARG_UNUSED(user_data);

	if (status == HTTP_SERVER_REQUEST_DATA_FINAL) {
		respond_status(rsp);
	}
	return 0;
}

/* --- /api/events ------------------------------------------------------------ */

static void json_string(struct out *o, const char *s)
{
	put(o, "\"");
	for (; *s != '\0'; s++) {
		if (*s == '"' || *s == '\\') {
			put(o, "\\%c", *s);
		} else if ((unsigned char)*s >= 0x20) {
			put(o, "%c", *s);
		}
	}
	put(o, "\"");
}

static int events_handler(struct http_client_ctx *client, enum http_transaction_status status,
			  const struct http_request_ctx *req, struct http_response_ctx *rsp,
			  void *user_data)
{
	static struct hub_event ev[CONFIG_HUB_EVENTS];
	struct out o = {resp_buf, sizeof(resp_buf)};
	int64_t now = k_uptime_get();
	int n;

	ARG_UNUSED(client);
	ARG_UNUSED(req);
	ARG_UNUSED(user_data);

	if (status != HTTP_SERVER_REQUEST_DATA_FINAL) {
		return 0;
	}

	n = hub_events_get(ev, ARRAY_SIZE(ev));
	put(&o, "[");
	for (int i = 0; i < n; i++) {
		put(&o, "%s{\"age_s\":%u,\"kind\":\"%s\",\"text\":", i ? "," : "",
		    (uint32_t)((now - ev[i].t_ms) / 1000), hub_ev_kind_str(ev[i].kind));
		json_string(&o, ev[i].text);
		put(&o, "}");
	}
	put(&o, "]");
	respond(rsp, &o);

	return 0;
}

/* --- POST /api/... ------------------------------------------------------------ */

enum api_action {
	API_ROW,
	API_PD,
	API_ENUMERATE,
	API_NODE,
	API_CHECK,
};

struct api_req {
	char *row;
	char *action;
	char *pref;
	int32_t ms;
	int32_t id;
};

static const struct json_obj_descr api_descr[] = {
	JSON_OBJ_DESCR_PRIM(struct api_req, row, JSON_TOK_STRING),
	JSON_OBJ_DESCR_PRIM(struct api_req, action, JSON_TOK_STRING),
	JSON_OBJ_DESCR_PRIM(struct api_req, pref, JSON_TOK_STRING),
	JSON_OBJ_DESCR_PRIM(struct api_req, ms, JSON_TOK_NUMBER),
	JSON_OBJ_DESCR_PRIM(struct api_req, id, JSON_TOK_NUMBER),
};

#define F_ROW    BIT(0)
#define F_ACTION BIT(1)
#define F_PREF   BIT(2)
#define F_MS     BIT(3)
#define F_ID     BIT(4)

static const char *do_row(const struct api_req *r, int fields)
{
	int row;
	int ret;

	if (!(fields & F_ROW) || !(fields & F_ACTION) || strlen(r->row) != 1) {
		return "row and action needed";
	}
	row = (r->row[0] & ~0x20) - 'A';
	if (row < 0 || row >= HUB_ROWS) {
		return "row must be A-D";
	}
	if (strcmp(r->action, "on") == 0) {
		ret = rows_set(row, true);
	} else if (strcmp(r->action, "off") == 0) {
		ret = rows_set(row, false);
	} else if (strcmp(r->action, "cycle") == 0) {
		ret = rows_cycle(row, (fields & F_MS) ? (uint32_t)CLAMP(r->ms, 100, 60000) : 0);
		if (ret == -EALREADY) {
			return "row is not on";
		}
	} else {
		return "action must be on, off or cycle";
	}

	return ret != 0 ? "failed" : NULL;
}

static const char *do_node(const struct api_req *r, int fields)
{
	static const struct {
		const char *name;
		uint8_t op;
		uint8_t arg;
	} actions[] = {
		{"identify", RACK_CMD_IDENTIFY, 10},  {"reset", RACK_CMD_RESET, 0},
		{"bootloader", RACK_CMD_BOOTLOADER, 0}, {"power-off", RACK_CMD_POWER, 0},
		{"power-on", RACK_CMD_POWER, 1},      {"power-cycle", RACK_CMD_POWER, 2},
		{"reboot", RACK_CMD_REBOOT, 0},
	};

	if (!(fields & F_ID) || !(fields & F_ACTION) || !RACK_NODE_VALID(r->id)) {
		return "id (a node id) and action needed";
	}
	for (int i = 0; i < ARRAY_SIZE(actions); i++) {
		if (strcmp(r->action, actions[i].name) == 0) {
			uint8_t args[3] = {actions[i].arg, 0, 0};
			uint8_t nargs = actions[i].op == RACK_CMD_POWER ? 3 :
					actions[i].op == RACK_CMD_IDENTIFY ? 1 : 0;

			return bus_cmd((uint8_t)r->id, actions[i].op, args, nargs) < 0
				       ? "rack bus busy"
				       : NULL;
		}
	}

	return "unknown action";
}

static const char *const api_paths[] = {
	[API_ROW] = "/api/row",
	[API_PD] = "/api/pd",
	[API_ENUMERATE] = "/api/enumerate",
	[API_NODE] = "/api/node",
	[API_CHECK] = "/api/access/check",
};

static int api_handler(struct http_client_ctx *client, enum http_transaction_status status,
		       const struct http_request_ctx *req, struct http_response_ctx *rsp,
		       void *user_data)
{
	static uint8_t body[128];
	static size_t len;
	static bool too_long;
	static char auth[96];
	struct api_req areq = {0};
	enum api_action what = (enum api_action)POINTER_TO_INT(user_data);
	const char *err = NULL;
	int fields = 0;

	ARG_UNUSED(client);

	if (status == HTTP_SERVER_TRANSACTION_ABORTED ||
	    status == HTTP_SERVER_TRANSACTION_COMPLETE) {
		len = 0;
		too_long = false;
		auth[0] = '\0';
		return 0;
	}

	capture_auth(req, auth, sizeof(auth));
	if (len + req->data_len > sizeof(body)) {
		too_long = true;
	} else {
		memcpy(body + len, req->data, req->data_len);
		len += req->data_len;
	}
	if (status != HTTP_SERVER_REQUEST_DATA_FINAL) {
		return 0;
	}
	if (too_long) {
		respond_error(rsp, HTTP_413_PAYLOAD_TOO_LARGE, "body too large");
		return 0;
	}
	/* Before parsing: json_obj_parse() rewrites the body in place */
	if (!hwtr_admin_check(auth, "POST", api_paths[what], body, len)) {
		respond_error(rsp, HTTP_403_FORBIDDEN,
			      hwtr_admin_claimed() ? "admin only: unlock with the hub's admin key"
						   : "admin only: claim the hub first (its BOOT button)");
		return 0;
	}
	if (len > 0) {
		fields = json_obj_parse(body, len, api_descr, ARRAY_SIZE(api_descr), &areq);
		if (fields < 0) {
			respond_error(rsp, HTTP_400_BAD_REQUEST, "bad JSON");
			return 0;
		}
	}

	switch (what) {
	case API_ROW:
		err = do_row(&areq, fields);
		break;
	case API_PD:
		if (!(fields & F_PREF) ||
		    (strcmp(areq.pref, "epr") != 0 && strcmp(areq.pref, "20v") != 0)) {
			err = "pref must be epr or 20v";
		} else {
			(void)pd_set_epr(strcmp(areq.pref, "epr") == 0);
		}
		break;
	case API_ENUMERATE:
		bus_enumerate(0);
		break;
	case API_NODE:
		err = do_node(&areq, fields);
		break;
	case API_CHECK:
		/* The signature was the point */
		break;
	}

	if (err != NULL) {
		respond_error(rsp, HTTP_400_BAD_REQUEST, err);
		return 0;
	}
	respond_status(rsp);

	return 0;
}

#define API_RESOURCE(_action)                                                                      \
	{                                                                                          \
		.common = {                                                                        \
			.type = HTTP_RESOURCE_TYPE_DYNAMIC,                                        \
			.bitmask_of_supported_http_methods = BIT(HTTP_POST),                       \
			.content_type = "application/json",                                        \
		},                                                                                 \
		.cb = api_handler,                                                                 \
		.user_data = INT_TO_POINTER(_action),                                              \
	}

static struct http_resource_detail_dynamic row_detail = API_RESOURCE(API_ROW);
static struct http_resource_detail_dynamic pd_detail = API_RESOURCE(API_PD);
static struct http_resource_detail_dynamic enumerate_detail = API_RESOURCE(API_ENUMERATE);
static struct http_resource_detail_dynamic node_detail = API_RESOURCE(API_NODE);
static struct http_resource_detail_dynamic check_detail = API_RESOURCE(API_CHECK);

static struct http_resource_detail_dynamic status_detail = {
	.common = {
		.type = HTTP_RESOURCE_TYPE_DYNAMIC,
		.bitmask_of_supported_http_methods = BIT(HTTP_GET),
		.content_type = "application/json",
	},
	.cb = status_handler,
};

static struct http_resource_detail_dynamic events_detail = {
	.common = {
		.type = HTTP_RESOURCE_TYPE_DYNAMIC,
		.bitmask_of_supported_http_methods = BIT(HTTP_GET),
		.content_type = "application/json",
	},
	.cb = events_handler,
};

/* --- /api/access/nonce, /api/access/claim ----------------------------------------- */

static int nonce_handler(struct http_client_ctx *client, enum http_transaction_status status,
			 const struct http_request_ctx *req, struct http_response_ctx *rsp,
			 void *user_data)
{
	struct out o = {resp_buf, sizeof(resp_buf)};
	char hex[HWTR_ADMIN_NONCE_HEX];

	ARG_UNUSED(client);
	ARG_UNUSED(req);
	ARG_UNUSED(user_data);

	if (status == HTTP_SERVER_REQUEST_DATA_FINAL) {
		(void)hwtr_admin_nonce(hex);
		put(&o, "{\"nonce\":\"%s\"}", hex);
		respond(rsp, &o);
	}
	return 0;
}

struct claim_req {
	char *key;
	char *ticket;
};

static const struct json_obj_descr claim_descr[] = {
	JSON_OBJ_DESCR_PRIM(struct claim_req, key, JSON_TOK_STRING),
	JSON_OBJ_DESCR_PRIM(struct claim_req, ticket, JSON_TOK_STRING),
};

static void respond_claim(struct http_response_ctx *rsp, uint32_t ip, const struct claim_req *r,
			  int fields)
{
	struct out o = {resp_buf, sizeof(resp_buf)};
	uint8_t offered[ACL_KEY_LEN];
	char hex[HWTR_ADMIN_KEY_HEX];
	int remaining = 0;
	int ret;

	if (fields & BIT(1)) {
		ret = hwtr_admin_claim_poll(ip, r->ticket, hex, &remaining);
		if (ret == -EINPROGRESS) {
			put(&o, "{\"state\":\"pending\",\"remaining_s\":%d}", remaining);
		} else if (ret == 0) {
			put(&o, "{\"state\":\"done\",\"key\":\"%s\"}", hex);
		} else {
			respond_error(rsp, HTTP_404_NOT_FOUND,
				      ret == -ETIMEDOUT ? "nobody pressed BOOT in time"
							: "no such claim from this address");
			return;
		}
		respond(rsp, &o);
		return;
	}

	if ((fields & BIT(0)) && acl_hex_decode(r->key, offered, sizeof(offered)) != 0) {
		respond_error(rsp, HTTP_400_BAD_REQUEST, "key: 64 hex digits");
		return;
	}
	ret = hwtr_admin_claim_start(ip, (fields & BIT(0)) ? offered : NULL, hex);
	if (ret == -EALREADY) {
		respond_error(rsp, HTTP_409_CONFLICT,
			      "already claimed: unlock with the admin key, or reset the hub");
		return;
	}
	put(&o, "{\"state\":\"pending\",\"ticket\":\"%s\",\"remaining_s\":%d}", hex,
	    CONFIG_HWTR_ADMIN_CLAIM_S);
	respond(rsp, &o);
}

static int claim_handler(struct http_client_ctx *client, enum http_transaction_status status,
			 const struct http_request_ctx *req, struct http_response_ctx *rsp,
			 void *user_data)
{
	static uint8_t body[160];
	static size_t len;
	struct claim_req r = {0};
	int fields = 0;

	ARG_UNUSED(user_data);

	if (status == HTTP_SERVER_TRANSACTION_ABORTED ||
	    status == HTTP_SERVER_TRANSACTION_COMPLETE) {
		len = 0;
		return 0;
	}
	if (len + req->data_len <= sizeof(body)) {
		memcpy(body + len, req->data, req->data_len);
		len += req->data_len;
	}
	if (status != HTTP_SERVER_REQUEST_DATA_FINAL) {
		return 0;
	}
	if (len > 0) {
		fields = json_obj_parse(body, len, claim_descr, ARRAY_SIZE(claim_descr), &r);
		if (fields < 0) {
			respond_error(rsp, HTTP_400_BAD_REQUEST, "bad JSON");
			return 0;
		}
	}
	respond_claim(rsp, peer_ip(client->fd), &r, fields);

	return 0;
}

static struct http_resource_detail_dynamic nonce_detail = {
	.common = {
		.type = HTTP_RESOURCE_TYPE_DYNAMIC,
		.bitmask_of_supported_http_methods = BIT(HTTP_GET),
		.content_type = "application/json",
	},
	.cb = nonce_handler,
};

static struct http_resource_detail_dynamic claim_detail = {
	.common = {
		.type = HTTP_RESOURCE_TYPE_DYNAMIC,
		.bitmask_of_supported_http_methods = BIT(HTTP_POST),
		.content_type = "application/json",
	},
	.cb = claim_handler,
};

/* --- /metrics ----------------------------------------------------------------- */

static int metrics_handler(struct http_client_ctx *client, enum http_transaction_status status,
			   const struct http_request_ctx *req, struct http_response_ctx *rsp,
			   void *user_data)
{
	struct out o = {resp_buf, sizeof(resp_buf)};
	struct hub_pd_status pd;
	struct hub_bus_status bus;

	ARG_UNUSED(client);
	ARG_UNUSED(req);
	ARG_UNUSED(user_data);

	if (status != HTTP_SERVER_REQUEST_DATA_FINAL) {
		return 0;
	}

	pd_status(&pd);
	bus_status(&bus);

	put(&o, "# HELP hub_contract_volts USB PD contract voltage\n# TYPE hub_contract_volts gauge\n"
		"hub_contract_volts %u.%03u\n", pd.contract_mv / 1000, pd.contract_mv % 1000);
	put(&o, "# HELP hub_contract_amps USB PD contract current\n# TYPE hub_contract_amps gauge\n"
		"hub_contract_amps %u.%03u\n", pd.contract_ma / 1000, pd.contract_ma % 1000);
	put(&o, "# HELP hub_vbus_volts VBUS (VRACK) on the controller's ADC\n"
		"# TYPE hub_vbus_volts gauge\nhub_vbus_volts %u.%03u\n", pd.vbus_mv / 1000,
	    pd.vbus_mv % 1000);
	put(&o, "# HELP hub_row_on Row switched on\n# TYPE hub_row_on gauge\n");
	for (int r = 0; r < HUB_ROWS; r++) {
		struct hub_row_status st;

		rows_status(r, &st);
		put(&o, "hub_row_on{row=\"%c\"} %d\n", 'A' + r, st.state == HUB_ROW_ON);
	}
	put(&o, "# HELP hub_row_amps Row current (eFuse IMON)\n# TYPE hub_row_amps gauge\n");
	for (int r = 0; r < HUB_ROWS; r++) {
		struct hub_row_status st;

		rows_status(r, &st);
		put(&o, "hub_row_amps{row=\"%c\"} %d.%03d\n", 'A' + r, st.ma / 1000, st.ma % 1000);
	}
	put(&o, "# HELP hub_row_faults_total eFuse faults since boot\n"
		"# TYPE hub_row_faults_total counter\n");
	for (int r = 0; r < HUB_ROWS; r++) {
		struct hub_row_status st;

		rows_status(r, &st);
		put(&o, "hub_row_faults_total{row=\"%c\"} %u\n", 'A' + r, st.faults);
	}
	put(&o, "# HELP hub_nodes Nodes on the rack bus\n# TYPE hub_nodes gauge\nhub_nodes %d\n"
		"# HELP hub_nodes_lost Nodes gone silent\n# TYPE hub_nodes_lost gauge\n"
		"hub_nodes_lost %d\n", bus.nodes, bus.lost);
	put(&o, "# HELP hub_can_frames_total CAN frames received\n"
		"# TYPE hub_can_frames_total counter\nhub_can_frames_total %u\n", bus.rx);
	put(&o, "# HELP hub_can_bus_off_total Bus-off events\n"
		"# TYPE hub_can_bus_off_total counter\nhub_can_bus_off_total %u\n", bus.bus_off);

	respond(rsp, &o);
	rsp->final_chunk = true;

	return 0;
}

static struct http_resource_detail_dynamic metrics_detail = {
	.common = {
		.type = HTTP_RESOURCE_TYPE_DYNAMIC,
		.bitmask_of_supported_http_methods = BIT(HTTP_GET),
		.content_type = "text/plain; version=0.0.4",
	},
	.cb = metrics_handler,
};

/* --- Static: the page --------------------------------------------------------- */

static const uint8_t index_html_gz[] = {
#include "index.html.gz.inc"
};

static struct http_resource_detail_static index_detail =
	HWTR_WEB_STATIC_GZ(index_html_gz, "text/html");

/* --- Service ------------------------------------------------------------------ */

static uint16_t http_port = CONFIG_HUB_HTTP_PORT;

HTTP_SERVICE_DEFINE(hub_http, NULL, &http_port, CONFIG_HTTP_SERVER_MAX_CLIENTS, 4, NULL, NULL,
		    NULL);

HTTP_RESOURCE_DEFINE(index_res, hub_http, "/", &index_detail);
HTTP_RESOURCE_DEFINE(status_res, hub_http, "/api/status", &status_detail);
HTTP_RESOURCE_DEFINE(events_res, hub_http, "/api/events", &events_detail);
HTTP_RESOURCE_DEFINE(row_res, hub_http, "/api/row", &row_detail);
HTTP_RESOURCE_DEFINE(pd_res, hub_http, "/api/pd", &pd_detail);
HTTP_RESOURCE_DEFINE(enumerate_res, hub_http, "/api/enumerate", &enumerate_detail);
HTTP_RESOURCE_DEFINE(node_res, hub_http, "/api/node", &node_detail);
HTTP_RESOURCE_DEFINE(metrics_res, hub_http, "/metrics", &metrics_detail);
HTTP_RESOURCE_DEFINE(nonce_res, hub_http, "/api/access/nonce", &nonce_detail);
HTTP_RESOURCE_DEFINE(claim_res, hub_http, "/api/access/claim", &claim_detail);
HTTP_RESOURCE_DEFINE(check_res, hub_http, "/api/access/check", &check_detail);

int web_init(void)
{
	int ret = http_server_start();

	if (ret == 0) {
		LOG_INF("web page and API on http port %d", CONFIG_HUB_HTTP_PORT);
	}
	return ret;
}
