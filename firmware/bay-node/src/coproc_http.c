/*
 * The DATA x4 co-processor's image over HTTP (coproc.c):
 *
 *   GET  /api/coproc             the stored image, the upload, the loads
 *   POST /api/coproc/begin       admin: {"size": N, "sha256": "<64 hex>"}
 *                                -> {"ticket": "<16 hex>"}
 *   POST /api/coproc?ticket=...  the image as bayctl coproc load makes it (a
 *                                64-byte header, then the bytes for SRAM),
 *                                written to the coproc partition as it
 *                                streams in -> {"state": "stored", ...}
 *
 * As the firmware updates (common/web/update_http.c): the begin request
 * carries the admin signature and the hash, the upload only the ticket.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/data/json.h>
#include <zephyr/net/socket.h>

#include <hwtr/acl.h>
#include <hwtr/admin.h>
#include <hwtr/web.h>

#include "bay.h"

/* One request at a time per resource (the server's holder); CPU only: PSRAM */
static BAY_EXT_RAM char resp[512];

static void reply(struct http_response_ctx *rsp, enum http_status status, const char *fmt, ...)
{
	va_list ap;
	int n;

	va_start(ap, fmt);
	n = vsnprintf(resp, sizeof(resp), fmt, ap);
	va_end(ap);
	rsp->status = status;
	rsp->body = resp;
	rsp->body_len = MIN((size_t)MAX(n, 0), sizeof(resp) - 1);
	rsp->final_chunk = true;
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

/* --- POST /api/coproc/begin --------------------------------------------------- */

struct begin_req {
	int32_t size;
	char *sha256;
};

static const struct json_obj_descr begin_descr[] = {
	JSON_OBJ_DESCR_PRIM(struct begin_req, size, JSON_TOK_NUMBER),
	JSON_OBJ_DESCR_PRIM(struct begin_req, sha256, JSON_TOK_STRING),
};

static int begin_handler(struct http_client_ctx *client, enum http_transaction_status status,
			 const struct http_request_ctx *req, struct http_response_ctx *rsp,
			 void *user_data)
{
	static uint8_t body[160];
	static size_t len;
	static bool too_long;
	static char auth[HWTR_WEB_AUTH_LEN + 8];
	char ticket[COPROC_TICKET_HEX];
	struct begin_req r = {0};
	uint8_t sha[32];
	const char *why = NULL;
	int fields;
	int ret;

	ARG_UNUSED(user_data);

	if (status == HTTP_SERVER_TRANSACTION_ABORTED ||
	    status == HTTP_SERVER_TRANSACTION_COMPLETE) {
		len = 0;
		too_long = false;
		auth[0] = '\0';
		return 0;
	}
	hwtr_web_capture_auth(req, auth, sizeof(auth));
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
		reply(rsp, HTTP_413_PAYLOAD_TOO_LARGE, "{\"error\":\"body too large\"}");
		return 0;
	}
	/* Before parsing: json_obj_parse() rewrites the body in place */
	if (!hwtr_admin_check(auth, "POST", "/api/coproc/begin", body, len)) {
		reply(rsp, HTTP_403_FORBIDDEN, "{\"error\":\"admin only: %s\"}",
		      hwtr_admin_claimed() ? "unlock with the admin key" : "claim the device first");
		return 0;
	}
	fields = json_obj_parse(body, len, begin_descr, ARRAY_SIZE(begin_descr), &r);
	if (fields < 0 || fields != (BIT(0) | BIT(1)) || r.size <= 0 ||
	    acl_hex_decode(r.sha256, sha, sizeof(sha)) != 0) {
		reply(rsp, HTTP_400_BAD_REQUEST,
		      "{\"error\":\"size and sha256 (64 hex digits) needed\"}");
		return 0;
	}

	ret = coproc_begin(peer_ip(client->fd), (uint32_t)r.size, sha, ticket, &why);
	if (ret != 0) {
		reply(rsp, ret == -EFBIG ? HTTP_413_PAYLOAD_TOO_LARGE : HTTP_409_CONFLICT,
		      "{\"error\":\"%s\"}", why);
		return 0;
	}
	reply(rsp, HTTP_200_OK, "{\"ticket\":\"%s\"}", ticket);

	return 0;
}

/* --- GET /api/coproc, POST /api/coproc?ticket=... --------------------------------- */

/* The ticket from the request's query string */
static void url_ticket(const struct http_client_ctx *client, char out[COPROC_TICKET_HEX])
{
	const char *q = strstr((const char *)client->url_buffer, "ticket=");

	out[0] = '\0';
	if (q != NULL) {
		q += strlen("ticket=");
		for (int i = 0; i < COPROC_TICKET_HEX - 1 && q[i] != '\0' && q[i] != '&'; i++) {
			out[i] = q[i];
			out[i + 1] = '\0';
		}
	}
}

static int upload_handler(struct http_client_ctx *client, enum http_transaction_status status,
			  const struct http_request_ctx *req, struct http_response_ctx *rsp)
{
	static bool answered; /* refused: the rest of the body is ignored */
	char ticket[COPROC_TICKET_HEX];
	const char *why = NULL;
	int n;
	int ret;

	if (status == HTTP_SERVER_TRANSACTION_ABORTED) {
		coproc_abort("upload interrupted");
		answered = false;
		return 0;
	}
	if (status == HTTP_SERVER_TRANSACTION_COMPLETE) {
		answered = false;
		return 0;
	}
	if (answered) {
		return 0;
	}

	url_ticket(client, ticket);
	ret = coproc_write(peer_ip(client->fd), ticket, req->data, req->data_len, &why);
	if (ret != 0) {
		answered = true;
		reply(rsp, ret == -EPERM ? HTTP_403_FORBIDDEN : HTTP_400_BAD_REQUEST,
		      "{\"error\":\"%s\"}", why);
		return 0;
	}
	if (status != HTTP_SERVER_REQUEST_DATA_FINAL) {
		return 0;
	}

	answered = true;
	ret = coproc_finish(&why);
	if (ret != 0) {
		reply(rsp, HTTP_400_BAD_REQUEST, "{\"error\":\"%s\"}", why);
		return 0;
	}
	n = coproc_json(resp, sizeof(resp));
	rsp->status = HTTP_200_OK;
	rsp->body = resp;
	rsp->body_len = MAX(n, 0);
	rsp->final_chunk = true;

	return 0;
}

static int coproc_handler(struct http_client_ctx *client, enum http_transaction_status status,
			  const struct http_request_ctx *req, struct http_response_ctx *rsp,
			  void *user_data)
{
	int n;

	ARG_UNUSED(user_data);

	if (client->method != HTTP_GET) {
		return upload_handler(client, status, req, rsp);
	}
	if (status == HTTP_SERVER_REQUEST_DATA_FINAL) {
		n = coproc_json(resp, sizeof(resp));
		rsp->body = resp;
		rsp->body_len = MAX(n, 0);
		rsp->final_chunk = true;
	}
	return 0;
}

/* --- Resources ----------------------------------------------------------------------- */

static struct http_resource_detail_dynamic begin_detail = {
	.common = {
		.type = HTTP_RESOURCE_TYPE_DYNAMIC,
		.bitmask_of_supported_http_methods = BIT(HTTP_POST),
		.content_type = "application/json",
	},
	.cb = begin_handler,
};

static struct http_resource_detail_dynamic coproc_detail = {
	.common = {
		.type = HTTP_RESOURCE_TYPE_DYNAMIC,
		.bitmask_of_supported_http_methods = BIT(HTTP_GET) | BIT(HTTP_POST),
		.content_type = "application/json",
	},
	.cb = coproc_handler,
};

HWTR_HTTP_RESOURCE_DEFINE(bay_coproc_res, bay_http, "/api/coproc", &coproc_detail);
HWTR_HTTP_RESOURCE_DEFINE(bay_coproc_begin_res, bay_http, "/api/coproc/begin", &begin_detail);
