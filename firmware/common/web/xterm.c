/*
 * The vendored xterm.js (vendor/xterm, MIT) on the application's HTTP
 * service (HWTR_WEB_SERVICE, set by hwtr_web_xterm() in web.cmake).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <hwtr/web.h>

static const uint8_t xterm_mjs_gz[] = {
#include "xterm.mjs.gz.inc"
};

static const uint8_t xterm_css_gz[] = {
#include "xterm.css.gz.inc"
};

static const uint8_t addon_fit_mjs_gz[] = {
#include "addon-fit.mjs.gz.inc"
};

static const uint8_t xterm_license_gz[] = {
#include "xterm-LICENSE.txt.gz.inc"
};

static struct http_resource_detail_static xterm_mjs_detail =
	HWTR_WEB_STATIC_GZ(xterm_mjs_gz, "text/javascript");
static struct http_resource_detail_static xterm_css_detail =
	HWTR_WEB_STATIC_GZ(xterm_css_gz, "text/css");
static struct http_resource_detail_static addon_fit_mjs_detail =
	HWTR_WEB_STATIC_GZ(addon_fit_mjs_gz, "text/javascript");
static struct http_resource_detail_static xterm_license_detail =
	HWTR_WEB_STATIC_GZ(xterm_license_gz, "text/plain");

HWTR_HTTP_RESOURCE_DEFINE(hwtr_xterm_mjs_res, HWTR_WEB_SERVICE, "/xterm.mjs", &xterm_mjs_detail);
HWTR_HTTP_RESOURCE_DEFINE(hwtr_xterm_css_res, HWTR_WEB_SERVICE, "/xterm.css", &xterm_css_detail);
HWTR_HTTP_RESOURCE_DEFINE(hwtr_addon_fit_mjs_res, HWTR_WEB_SERVICE, "/addon-fit.mjs",
			  &addon_fit_mjs_detail);
HWTR_HTTP_RESOURCE_DEFINE(hwtr_xterm_license_res, HWTR_WEB_SERVICE, "/xterm-LICENSE.txt",
			  &xterm_license_detail);
