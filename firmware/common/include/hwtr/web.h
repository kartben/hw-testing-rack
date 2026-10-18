/*
 * HTTP helpers shared by the bay node and the power hub web servers.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef HWTR_WEB_H_
#define HWTR_WEB_H_

#include <string.h>
#include <strings.h>

#include <zephyr/net/http/server.h>
#include <zephyr/net/http/service.h>
#include <zephyr/sys/util.h>

/* A file gzipped into the image (generate_inc_file_for_target --gzip), served as is */
#define HWTR_WEB_STATIC_GZ(_data, _type)                                                           \
	{                                                                                          \
		.common = {                                                                        \
			.type = HTTP_RESOURCE_TYPE_STATIC,                                         \
			.bitmask_of_supported_http_methods = BIT(HTTP_GET),                        \
			.content_encoding = "gzip",                                                \
			.content_type = _type,                                                     \
		},                                                                                 \
		.static_data = _data,                                                              \
		.static_data_len = sizeof(_data),                                                  \
	}

/* HTTP_RESOURCE_DEFINE with a service name that is itself a macro (expanded first) */
#define HWTR_HTTP_RESOURCE_DEFINE(_name, _service, _resource, _detail)                             \
	HTTP_RESOURCE_DEFINE(_name, _service, _resource, _detail)

/*
 * Capture X-Bay-Auth (hwtr/admin.h) for the admin requests.  Without
 * CONFIG_HTTP_SERVER_CAPTURE_HEADERS the registration compiles but nothing
 * is captured, and every admin request is refused: hence the checks.
 */
#define HWTR_WEB_AUTH_CAPTURE(_id)                                                                 \
	BUILD_ASSERT(IS_ENABLED(CONFIG_HTTP_SERVER_CAPTURE_HEADERS),                               \
		     "admin requests need CONFIG_HTTP_SERVER_CAPTURE_HEADERS");                    \
	BUILD_ASSERT(CONFIG_HTTP_SERVER_MAX_HEADER_LEN >= HWTR_WEB_AUTH_LEN + 2,                   \
		     "X-Bay-Auth is longer than CONFIG_HTTP_SERVER_MAX_HEADER_LEN");               \
	BUILD_ASSERT(CONFIG_HTTP_SERVER_CAPTURE_HEADER_BUFFER_SIZE >=                              \
			     sizeof("X-Bay-Auth") + HWTR_WEB_AUTH_LEN + 1,                         \
		     "CONFIG_HTTP_SERVER_CAPTURE_HEADER_BUFFER_SIZE too small for X-Bay-Auth");    \
	HTTP_SERVER_REGISTER_HEADER_CAPTURE(_id, "X-Bay-Auth")

/* "<16 hex nonce>:<64 hex HMAC>" */
#define HWTR_WEB_AUTH_LEN 81

/* X-Bay-Auth from the first callback of a request (kept in out until the next) */
static inline void hwtr_web_capture_auth(const struct http_request_ctx *req, char *out,
					 size_t size)
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

#endif /* HWTR_WEB_H_ */
