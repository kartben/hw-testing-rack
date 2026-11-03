/*
 * The DATA x4's pin matrix over HTTP (wires.c):
 *
 *   GET  /api/wires    the buses' names, the pins asked for (each with whether
 *                      its switch is closed now), each port's state
 *   POST /api/wires    {"pins": [{"port": 2, "pin": 1, "bus": "A"}, ...],
 *                       "names": ["UART", "", ...]}: the pins from now on
 *                      (every pin left out off the buses; "pins": [] opens
 *                      them all), the names if given.  Control right; a port
 *                      whose pins change must not be leased to another
 *                      address.  -> the same as GET, and "changed": the
 *                      switches moved.
 *   GET  /wires-card.mjs  the bay page's card for it (web/wires-card.mjs)
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <stdio.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/net/http/server.h>
#include <zephyr/net/http/service.h>

#include <hwtr/acl.h>
#include <hwtr/web.h>

#include "bay.h"

/* One request at a time (the server's thread); CPU only: PSRAM */
static BAY_EXT_RAM char resp[2048];
static BAY_EXT_RAM char body[1536];
static BAY_EXT_RAM char names[WIRES_BUSES][WIRES_NAME_LEN];

static void reply(struct http_response_ctx *rsp, enum http_status status, int n)
{
	rsp->status = status;
	rsp->body = resp;
	rsp->body_len = MIN((size_t)MAX(n, 0), sizeof(resp) - 1);
	rsp->final_chunk = true;
}

static void error(struct http_response_ctx *rsp, enum http_status status, const char *why)
{
	reply(rsp, status, snprintf(resp, sizeof(resp), "{\"error\":\"%s\"}", why));
}

/* A port whose pins change, leased to another address: its name, else NULL */
static const char *leased_port(const int8_t wanted[WIRES_PINS], uint32_t ip, char *slot, size_t size)
{
	int8_t now[WIRES_PINS];

	wires_get(now, NULL);
	for (int port = 1; port <= WIRES_PORTS; port++) {
		const int first = (port - 1) * WIRES_PORT_PINS;

		if (memcmp(&now[first], &wanted[first], WIRES_PORT_PINS) != 0 &&
		    access_check_port(ACL_CONTROL, port, ip) == ACL_RESERVED) {
			bay_slot_name(port, slot, size);
			return slot;
		}
	}
	return NULL;
}

static int wires_handler(struct http_client_ctx *client, enum http_transaction_status status,
			 const struct http_request_ctx *req, struct http_response_ctx *rsp,
			 void *user_data)
{
	static size_t len;
	static bool too_long;
	const bool post = client->method == HTTP_POST;
	const uint32_t ip = access_peer(client->fd);
	int8_t wanted[WIRES_PINS];
	bool has_pins, has_names;
	const char *why = NULL;
	enum acl_verdict verdict;
	char slot[24];
	int changed = -1;

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
		error(rsp, verdict == ACL_RESERVED ? HTTP_423_LOCKED : HTTP_403_FORBIDDEN,
		      verdict == ACL_RESERVED ? "reserved: another address holds the lease"
					      : "not allowed from this address");
		return 0;
	}
	if (post) {
		if (too_long) {
			error(rsp, HTTP_413_PAYLOAD_TOO_LARGE, "body too large");
			return 0;
		}
		if (wires_parse(body, len, wanted, &has_pins, names, &has_names, &why) != 0) {
			error(rsp, HTTP_400_BAD_REQUEST, why);
			return 0;
		}
		if (has_pins && leased_port(wanted, ip, slot, sizeof(slot)) != NULL) {
			reply(rsp, HTTP_423_LOCKED,
			      snprintf(resp, sizeof(resp),
				       "{\"error\":\"%s is reserved by another address\"}", slot));
			return 0;
		}
		for (int b = 0; has_names && b < WIRES_BUSES; b++) {
			wires_name(b, names[b]);
		}
		changed = 0;
		if (has_pins) {
			changed = wires_set(wanted);
			if (changed < 0) {
				reply(rsp, HTTP_500_INTERNAL_SERVER_ERROR, wires_json(resp, sizeof(resp), -1));
				return 0;
			}
		}
	}
	reply(rsp, HTTP_200_OK, wires_json(resp, sizeof(resp), changed));

	return 0;
}

static struct http_resource_detail_dynamic wires_detail = {
	.common = {
		.type = HTTP_RESOURCE_TYPE_DYNAMIC,
		.bitmask_of_supported_http_methods = BIT(HTTP_GET) | BIT(HTTP_POST),
		.content_type = "application/json",
	},
	.cb = wires_handler,
};

static const uint8_t card_mjs_gz[] = {
#include "wires-card.mjs.gz.inc"
};

static struct http_resource_detail_static card_detail =
	HWTR_WEB_STATIC_GZ(card_mjs_gz, "text/javascript");

HWTR_HTTP_RESOURCE_DEFINE(bay_wires_res, bay_http, "/api/wires", &wires_detail);
HWTR_HTTP_RESOURCE_DEFINE(bay_wires_card_res, bay_http, "/wires-card.mjs", &card_detail);
