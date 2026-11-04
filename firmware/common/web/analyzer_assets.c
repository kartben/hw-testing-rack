/*
 * The logic analyzer's modules (web/analyzer: the protocol, the capture,
 * the decoders, the viewer, the .vcd, the node's relay as a transport) at
 * /analyzer/<name>.mjs on the application's HTTP service (HWTR_WEB_SERVICE,
 * set by hwtr_web_analyzer() in web.cmake), for its page's analyzer card.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <hwtr/web.h>

static const uint8_t capture_mjs_gz[] = {
#include "analyzer-capture.mjs.gz.inc"
};

static const uint8_t decoders_mjs_gz[] = {
#include "analyzer-decoders.mjs.gz.inc"
};

static const uint8_t decoding_mjs_gz[] = {
#include "analyzer-decoding.mjs.gz.inc"
};

static const uint8_t panel_mjs_gz[] = {
#include "analyzer-panel.mjs.gz.inc"
};

static const uint8_t protocol_mjs_gz[] = {
#include "analyzer-protocol.mjs.gz.inc"
};

static const uint8_t relay_mjs_gz[] = {
#include "analyzer-relay.mjs.gz.inc"
};

static const uint8_t vcd_mjs_gz[] = {
#include "analyzer-vcd.mjs.gz.inc"
};

static const uint8_t viewer_mjs_gz[] = {
#include "analyzer-viewer.mjs.gz.inc"
};

#define MODULE(_name)                                                                              \
	static struct http_resource_detail_static _name##_mjs_detail =                             \
		HWTR_WEB_STATIC_GZ(_name##_mjs_gz, "text/javascript");                             \
	HWTR_HTTP_RESOURCE_DEFINE(hwtr_analyzer_##_name##_res, HWTR_WEB_SERVICE,                   \
				  "/analyzer/" #_name ".mjs", &_name##_mjs_detail)

MODULE(capture);
MODULE(decoders);
MODULE(decoding);
MODULE(panel);
MODULE(protocol);
MODULE(relay);
MODULE(vcd);
MODULE(viewer);
