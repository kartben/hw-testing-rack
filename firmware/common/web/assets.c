/*
 * /rack.css and /rack.mjs on the application's HTTP service
 * (HWTR_WEB_SERVICE, set by hwtr_web_assets() in web.cmake).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <hwtr/web.h>

static const uint8_t rack_css_gz[] = {
#include "rack.css.gz.inc"
};

static const uint8_t rack_mjs_gz[] = {
#include "rack.mjs.gz.inc"
};

static struct http_resource_detail_static rack_css_detail =
	HWTR_WEB_STATIC_GZ(rack_css_gz, "text/css");
static struct http_resource_detail_static rack_mjs_detail =
	HWTR_WEB_STATIC_GZ(rack_mjs_gz, "text/javascript");

HWTR_HTTP_RESOURCE_DEFINE(hwtr_rack_css_res, HWTR_WEB_SERVICE, "/rack.css", &rack_css_detail);
HWTR_HTTP_RESOURCE_DEFINE(hwtr_rack_mjs_res, HWTR_WEB_SERVICE, "/rack.mjs", &rack_mjs_detail);
