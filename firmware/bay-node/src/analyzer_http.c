/*
 * The logic analyzer relay over HTTP (analyzer.c):
 *
 *   GET  /api/analyzer         its owner, whether it is there, the page on it
 *   POST /api/analyzer         {"owner": "page" | "usbip"}: Control right
 *   GET  /analyzer/ws?t=...    the page's WebSocket: binary messages both
 *                              ways, the analyzer's own protocol.  The ticket
 *                              comes from POST /api/console/ticket (Console
 *                              right), as for the web consoles.
 *   GET  /analyzer/card.mjs    the bay page's card for it (web/analyzer-card.mjs);
 *                              the modules it imports are firmware/common's
 *                              (hwtr_web_analyzer())
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <stdio.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/data/json.h>
#include <zephyr/net/http/server.h>
#include <zephyr/net/http/service.h>
#include <zephyr/net/websocket.h>

#include <hwtr/acl.h>
#include <hwtr/web.h>

#include "bay.h"

BUILD_ASSERT(CONFIG_WEBSOCKET_MAX_CONTEXTS >= CONFIG_BAY_CONSOLE_WEB_CLIENTS + 1,
	     "one websocket context per web console, one for the analyzer");

#define WS_SEND_MS 200 /* a page slower than that is dropped */

/* --- The page's WebSocket ------------------------------------------------------ */

/*
 * Two: a page reloaded connects again before the relay lets go of the old one.
 * fd is -1 while free; the relay closes them, the server thread opens them.
 */
static struct ws_page {
	struct analyzer_page page;
	atomic_t fd;
} pages[2] = {{.fd = ATOMIC_INIT(-1)}, {.fd = ATOMIC_INIT(-1)}};

static int ws_send(struct analyzer_page *p, const uint8_t *data, size_t len)
{
	struct ws_page *w = CONTAINER_OF(p, struct ws_page, page);

	return websocket_send_msg(atomic_get(&w->fd), data, len, WEBSOCKET_OPCODE_DATA_BINARY,
				  false, true, WS_SEND_MS);
}

static int ws_recv(struct analyzer_page *p, uint8_t *buf, size_t size)
{
	struct ws_page *w = CONTAINER_OF(p, struct ws_page, page);
	uint64_t remaining;
	uint32_t type = 0;
	int n;

	n = websocket_recv_msg(atomic_get(&w->fd), buf, size, &type, &remaining, 0);
	if (n == -EAGAIN) {
		return 0;
	}
	if (n < 0 || (type & WEBSOCKET_FLAG_CLOSE)) {
		return -ENOTCONN;
	}
	if (type & WEBSOCKET_FLAG_PING) {
		return websocket_send_msg(atomic_get(&w->fd), buf, n, WEBSOCKET_OPCODE_PONG, false,
					  true, WS_SEND_MS) < 0 ? -EIO : 0;
	}

	return type & (WEBSOCKET_FLAG_BINARY | WEBSOCKET_FLAG_TEXT) ? n : 0;
}

static void ws_close(struct analyzer_page *p)
{
	struct ws_page *w = CONTAINER_OF(p, struct ws_page, page);

	(void)websocket_unregister(atomic_get(&w->fd));
	atomic_set(&w->fd, -1);
}

/* A WebSocket descriptor has no peer address: the ticket gives it */
static int ws_setup(int ws_socket, struct http_request_ctx *request_ctx, void *user_data)
{
	char ticket[17] = "";
	struct ws_page *w = NULL;
	const char *t = NULL;
	uint32_t ip;
	int ret;

	ARG_UNUSED(user_data);

	if (request_ctx->data != NULL) {
		t = strstr((const char *)request_ctx->data, "t=");
	}
	if (t != NULL) {
		strncpy(ticket, t + 2, sizeof(ticket) - 1);
		ticket[strcspn(ticket, "&")] = '\0';
	}
	ip = access_console_redeem(ticket);
	if (ip == 0 || access_check(ACL_CONSOLE, ip) != ACL_OK) {
		return -EACCES;
	}

	ARRAY_FOR_EACH_PTR(pages, p) {
		if (atomic_cas(&p->fd, -1, ws_socket)) {
			w = p;
			break;
		}
	}
	if (w == NULL) {
		return -EBUSY;
	}
	w->page = (struct analyzer_page){.send = ws_send, .recv = ws_recv, .close = ws_close};
	ret = analyzer_attach(&w->page, ip);
	if (ret != 0) {
		/* The server closes it */
		atomic_set(&w->fd, -1);
	}

	return ret;
}

/* The server reads the WebSocket's frames through this */
static BAY_EXT_RAM uint8_t ws_buf[256];

static struct http_resource_detail_websocket ws_detail = {
	.common = {
		.type = HTTP_RESOURCE_TYPE_WEBSOCKET,
		.bitmask_of_supported_http_methods = BIT(HTTP_GET),
	},
	.cb = ws_setup,
	.data_buffer = ws_buf,
	.data_buffer_len = sizeof(ws_buf),
};

/* --- /api/analyzer --------------------------------------------------------------- */

/* One request at a time per resource (the server's holder); CPU only: PSRAM */
static BAY_EXT_RAM char resp[320];

static void reply(struct http_response_ctx *rsp, enum http_status status, int n)
{
	rsp->status = status;
	rsp->body = resp;
	rsp->body_len = MIN((size_t)MAX(n, 0), sizeof(resp) - 1);
	rsp->final_chunk = true;
}

struct owner_req {
	char *owner;
};

static const struct json_obj_descr owner_descr[] = {
	JSON_OBJ_DESCR_PRIM(struct owner_req, owner, JSON_TOK_STRING),
};

static int analyzer_handler(struct http_client_ctx *client, enum http_transaction_status status,
			    const struct http_request_ctx *req, struct http_response_ctx *rsp,
			    void *user_data)
{
	static uint8_t body[48];
	static size_t len;
	static bool too_long;
	const bool post = client->method == HTTP_POST;
	const uint32_t ip = access_peer(client->fd);
	struct owner_req r = {0};
	enum analyzer_owner owner;
	enum acl_verdict verdict;
	int ret;

	ARG_UNUSED(user_data);

	if (status == HTTP_SERVER_TRANSACTION_ABORTED ||
	    status == HTTP_SERVER_TRANSACTION_COMPLETE) {
		len = 0;
		too_long = false;
		return 0;
	}
	if (len + req->data_len > sizeof(body)) {
		too_long = true;
	} else {
		memcpy(body + len, req->data, req->data_len);
		len += req->data_len;
	}
	if (status != HTTP_SERVER_REQUEST_DATA_FINAL) {
		return 0;
	}

	verdict = access_check(post ? ACL_CONTROL : ACL_STATUS, ip);
	if (verdict != ACL_OK) {
		reply(rsp, verdict == ACL_RESERVED ? HTTP_423_LOCKED : HTTP_403_FORBIDDEN,
		      snprintf(resp, sizeof(resp), "{\"error\":\"%s\"}",
			       verdict == ACL_RESERVED ? "reserved: another address holds the lease"
						       : "not allowed from this address"));
		return 0;
	}
	if (post) {
		if (!too_long &&
		    json_obj_parse(body, len, owner_descr, ARRAY_SIZE(owner_descr), &r) == BIT(0) &&
		    (strcmp(r.owner, "page") == 0 || strcmp(r.owner, "usbip") == 0)) {
			owner = r.owner[0] == 'p' ? ANALYZER_PAGE : ANALYZER_USBIP;
		} else {
			reply(rsp, HTTP_400_BAD_REQUEST,
			      snprintf(resp, sizeof(resp),
				       "{\"error\":\"owner: \\\"page\\\" or \\\"usbip\\\"\"}"));
			return 0;
		}
		ret = analyzer_set_owner(owner);
		if (ret != 0) {
			reply(rsp, HTTP_409_CONFLICT,
			      snprintf(resp, sizeof(resp),
				       "{\"error\":\"the analyzer is busy: try again (%d)\"}", ret));
			return 0;
		}
	}
	reply(rsp, HTTP_200_OK, analyzer_json(resp, sizeof(resp)));

	return 0;
}

static struct http_resource_detail_dynamic analyzer_detail = {
	.common = {
		.type = HTTP_RESOURCE_TYPE_DYNAMIC,
		.bitmask_of_supported_http_methods = BIT(HTTP_GET) | BIT(HTTP_POST),
		.content_type = "application/json",
	},
	.cb = analyzer_handler,
};

/* --- /analyzer/card.mjs ------------------------------------------------------------ */

static const uint8_t card_mjs_gz[] = {
#include "analyzer-card.mjs.gz.inc"
};

static struct http_resource_detail_static card_detail =
	HWTR_WEB_STATIC_GZ(card_mjs_gz, "text/javascript");

HWTR_HTTP_RESOURCE_DEFINE(bay_analyzer_res, bay_http, "/api/analyzer", &analyzer_detail);
HWTR_HTTP_RESOURCE_DEFINE(bay_analyzer_card_res, bay_http, "/analyzer/card.mjs", &card_detail);
HWTR_HTTP_RESOURCE_DEFINE(bay_analyzer_ws_res, bay_http, "/analyzer/ws", &ws_detail);
