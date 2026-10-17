/*
 * Web page, JSON API and Prometheus metrics (Zephyr HTTP server, port 80).
 *
 *   GET  /             status page (web/index.html, gzipped into the image)
 *   GET  /api/status   node state as JSON
 *   POST /api/power    {"action": "on" | "off" | "cycle", "ms": 1000}
 *   POST /api/reset    {"ms": 100}
 *   POST /api/boot     {}                 DUT into its bootloader
 *   POST /api/mode     {"mode": "usbip" | "classic"}
 *   GET  /metrics      Prometheus exposition format
 *
 *   GET  /api/aux        AUX UART settings and clients
 *   POST /api/aux        {"baud": 115200, "data_bits": 8, "parity": "none",
 *                         "stop_bits": 1, "enter": "cr" | "lf" | "crlf",
 *                         "echo": false, "esptool_reset": false}  (any subset, saved)
 *   POST /api/aux/break  {"ms": 250}
 *   GET  /console/ws/<n> WebSocket to the AUX UART (see aux_console.c)
 *   GET  /xterm.mjs, /xterm.css, /addon-fit.mjs, /xterm-LICENSE.txt  vendored xterm.js
 *
 * Every POST under /api/ except /api/aux answers with the new /api/status
 * document, errors with {"error": "..."} and a 4xx/5xx status.  No
 * authentication: lab network only.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdio.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/version.h>
#include <zephyr/data/json.h>
#include <zephyr/net/hostname.h>
#include <zephyr/net/http/server.h>
#include <zephyr/net/http/service.h>
#include <zephyr/net/prometheus/collector.h>
#include <zephyr/net/prometheus/counter.h>
#include <zephyr/net/prometheus/formatter.h>
#include <zephyr/net/prometheus/gauge.h>
#include <zephyr/logging/log.h>

#include "bay.h"

LOG_MODULE_REGISTER(web, CONFIG_BAY_LOG_LEVEL);

/* Longest the HTTP server thread may be held by a power cycle or a reset */
#define MAX_ACTION_MS 10000

/* --- /api/status --------------------------------------------------------- */

struct status_usb {
	bool running;
	int32_t devices;
	int32_t sessions;
};

struct status_dut {
	bool on;
	bool fault;
	bool latched;
	bool meter;
	int32_t faults;
	int32_t mv;
	int32_t ma;
	int32_t mw;
};

struct status_aux {
	int32_t baud;
	const char *format; /* "8N1" */
	int32_t port;       /* raw TCP */
	int32_t rfc2217_port;
	int32_t web_clients;
	bool rfc2217;
	bool raw;
	int32_t rx;
	int32_t tx;
	int32_t dropped;
	char format_buf[4];
};

struct status_doc {
	const char *id;
	const char *hostname;
	const char *ip;
	const char *version;
	const char *path;
	int32_t uptime_s;
	bool service;
	bool pc_detected;
	bool force_classic;
	struct status_usb usb;
	struct status_dut dut;
	struct status_aux aux;
};

static const struct json_obj_descr status_usb_descr[] = {
	JSON_OBJ_DESCR_PRIM(struct status_usb, running, JSON_TOK_TRUE),
	JSON_OBJ_DESCR_PRIM(struct status_usb, devices, JSON_TOK_NUMBER),
	JSON_OBJ_DESCR_PRIM(struct status_usb, sessions, JSON_TOK_NUMBER),
};

static const struct json_obj_descr status_dut_descr[] = {
	JSON_OBJ_DESCR_PRIM(struct status_dut, on, JSON_TOK_TRUE),
	JSON_OBJ_DESCR_PRIM(struct status_dut, fault, JSON_TOK_TRUE),
	JSON_OBJ_DESCR_PRIM(struct status_dut, latched, JSON_TOK_TRUE),
	JSON_OBJ_DESCR_PRIM(struct status_dut, meter, JSON_TOK_TRUE),
	JSON_OBJ_DESCR_PRIM(struct status_dut, faults, JSON_TOK_NUMBER),
	JSON_OBJ_DESCR_PRIM(struct status_dut, mv, JSON_TOK_NUMBER),
	JSON_OBJ_DESCR_PRIM(struct status_dut, ma, JSON_TOK_NUMBER),
	JSON_OBJ_DESCR_PRIM(struct status_dut, mw, JSON_TOK_NUMBER),
};

static const struct json_obj_descr status_aux_descr[] = {
	JSON_OBJ_DESCR_PRIM(struct status_aux, baud, JSON_TOK_NUMBER),
	JSON_OBJ_DESCR_PRIM(struct status_aux, format, JSON_TOK_STRING),
	JSON_OBJ_DESCR_PRIM(struct status_aux, port, JSON_TOK_NUMBER),
	JSON_OBJ_DESCR_PRIM(struct status_aux, rfc2217_port, JSON_TOK_NUMBER),
	JSON_OBJ_DESCR_PRIM(struct status_aux, web_clients, JSON_TOK_NUMBER),
	JSON_OBJ_DESCR_PRIM(struct status_aux, rfc2217, JSON_TOK_TRUE),
	JSON_OBJ_DESCR_PRIM(struct status_aux, raw, JSON_TOK_TRUE),
	JSON_OBJ_DESCR_PRIM(struct status_aux, rx, JSON_TOK_NUMBER),
	JSON_OBJ_DESCR_PRIM(struct status_aux, tx, JSON_TOK_NUMBER),
	JSON_OBJ_DESCR_PRIM(struct status_aux, dropped, JSON_TOK_NUMBER),
};

static const struct json_obj_descr status_descr[] = {
	JSON_OBJ_DESCR_PRIM(struct status_doc, id, JSON_TOK_STRING),
	JSON_OBJ_DESCR_PRIM(struct status_doc, hostname, JSON_TOK_STRING),
	JSON_OBJ_DESCR_PRIM(struct status_doc, ip, JSON_TOK_STRING),
	JSON_OBJ_DESCR_PRIM(struct status_doc, version, JSON_TOK_STRING),
	JSON_OBJ_DESCR_PRIM(struct status_doc, path, JSON_TOK_STRING),
	JSON_OBJ_DESCR_PRIM(struct status_doc, uptime_s, JSON_TOK_NUMBER),
	JSON_OBJ_DESCR_PRIM(struct status_doc, service, JSON_TOK_TRUE),
	JSON_OBJ_DESCR_PRIM(struct status_doc, pc_detected, JSON_TOK_TRUE),
	JSON_OBJ_DESCR_PRIM(struct status_doc, force_classic, JSON_TOK_TRUE),
	JSON_OBJ_DESCR_OBJECT(struct status_doc, usb, status_usb_descr),
	JSON_OBJ_DESCR_OBJECT(struct status_doc, dut, status_dut_descr),
	JSON_OBJ_DESCR_OBJECT(struct status_doc, aux, status_aux_descr),
};

/* Responses are built in the HTTP server thread, one at a time */
static char resp_buf[768];

static void status_fill(struct status_doc *s)
{
	struct dut_power_reading r = {0};
	struct aux_config cfg;
	struct aux_stats st;
	int devices = usb_host_device_count();

	s->id = bay_id();
	s->hostname = net_hostname_get();
	s->ip = bay_net_addr();
	s->version = KERNEL_VERSION_STRING;
	s->path = bay_data_path_str(usb_mux_path());
	s->uptime_s = (int32_t)(k_uptime_get() / MSEC_PER_SEC);
	s->service = usb_mux_service();
	s->pc_detected = usb_mux_pc_detected();
	s->force_classic = usb_mux_force_pc_get();

	s->usb.running = usb_host_running();
	s->usb.devices = MAX(devices, 0);
	s->usb.sessions = usb_host_usbip_sessions();

	s->dut.on = dut_power_get();
	s->dut.fault = dut_fault_active();
	s->dut.latched = dut_fault_latched();
	s->dut.faults = (int32_t)dut_fault_count();
	s->dut.meter = dut_power_read(&r) == 0;
	s->dut.mv = r.bus_mv;
	s->dut.ma = r.current_ma;
	s->dut.mw = r.power_mw;

	aux_config_get(&cfg, false);
	aux_stats_get(&st);
	s->aux.baud = (int32_t)cfg.baud;
	/* "8N1": the fields are validated, one character each */
	s->aux.format_buf[0] = '0' + cfg.data_bits;
	s->aux.format_buf[1] = "NOE"[cfg.parity];
	s->aux.format_buf[2] = '0' + cfg.stop_bits;
	s->aux.format_buf[3] = '\0';
	s->aux.format = s->aux.format_buf;
	s->aux.port = CONFIG_BAY_AUX_TCP_PORT;
	s->aux.rfc2217_port = CONFIG_BAY_RFC2217_PORT;
	s->aux.web_clients = st.web_clients;
	s->aux.rfc2217 = st.rfc2217_client;
	s->aux.raw = st.raw_client;
	s->aux.rx = (int32_t)st.rx;
	s->aux.tx = (int32_t)st.tx;
	s->aux.dropped = (int32_t)st.dropped;
}

static void respond_status(struct http_response_ctx *rsp)
{
	struct status_doc s;
	int ret;

	status_fill(&s);
	ret = json_obj_encode_buf(status_descr, ARRAY_SIZE(status_descr), &s, resp_buf,
				  sizeof(resp_buf));
	if (ret != 0) {
		LOG_ERR("status encoding failed: %d", ret);
		rsp->status = HTTP_500_INTERNAL_SERVER_ERROR;
		strcpy(resp_buf, "{\"error\":\"encoding\"}");
	}

	rsp->body = resp_buf;
	rsp->body_len = strlen(resp_buf);
	rsp->final_chunk = true;
}

static void respond_error(struct http_response_ctx *rsp, enum http_status status,
			  const char *msg)
{
	snprintf(resp_buf, sizeof(resp_buf), "{\"error\":\"%s\"}", msg);
	rsp->status = status;
	rsp->body = resp_buf;
	rsp->body_len = strlen(resp_buf);
	rsp->final_chunk = true;
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

/* --- POST /api/... ------------------------------------------------------- */

enum api_action {
	API_POWER,
	API_RESET,
	API_BOOT,
	API_MODE,
	API_BREAK,
};

/* Default length of a BREAK, as pyserial's send_break() */
#define BREAK_MS 250

struct action_req {
	char *action;
	char *mode;
	int32_t ms;
};

static const struct json_obj_descr action_descr[] = {
	JSON_OBJ_DESCR_PRIM(struct action_req, action, JSON_TOK_STRING),
	JSON_OBJ_DESCR_PRIM(struct action_req, mode, JSON_TOK_STRING),
	JSON_OBJ_DESCR_PRIM(struct action_req, ms, JSON_TOK_NUMBER),
};

#define ACTION_FIELD_ACTION BIT(0)
#define ACTION_FIELD_MODE   BIT(1)
#define ACTION_FIELD_MS     BIT(2)

static const char *do_action(enum api_action what, const struct action_req *req, int fields)
{
	uint32_t ms;
	int ret;

	if ((fields & ACTION_FIELD_MS) && (req->ms <= 0 || req->ms > MAX_ACTION_MS)) {
		return "ms must be 1..10000";
	}

	switch (what) {
	case API_POWER:
		if (!(fields & ACTION_FIELD_ACTION)) {
			return "action must be on, off or cycle";
		}
		if (strcmp(req->action, "on") == 0) {
			ret = dut_power_set(true);
		} else if (strcmp(req->action, "off") == 0) {
			ret = dut_power_set(false);
		} else if (strcmp(req->action, "cycle") == 0) {
			ms = (fields & ACTION_FIELD_MS) ? req->ms : CONFIG_BAY_POWER_CYCLE_MS;
			ret = dut_power_cycle(K_MSEC(ms));
		} else {
			return "action must be on, off or cycle";
		}
		break;
	case API_RESET:
		ms = (fields & ACTION_FIELD_MS) ? req->ms : CONFIG_BAY_RESET_PULSE_MS;
		ret = dut_reset_pulse(K_MSEC(ms));
		break;
	case API_BOOT:
		ret = dut_enter_bootloader();
		break;
	case API_MODE:
		if (!(fields & ACTION_FIELD_MODE)) {
			return "mode must be usbip or classic";
		}
		if (strcmp(req->mode, "classic") == 0) {
			ret = usb_mux_force_pc_set(true);
		} else if (strcmp(req->mode, "usbip") == 0) {
			ret = usb_mux_force_pc_set(false);
		} else {
			return "mode must be usbip or classic";
		}
		break;
	case API_BREAK:
		ret = aux_break((fields & ACTION_FIELD_MS) ? req->ms : BREAK_MS);
		if (ret == -EIO) {
			return "the DUT is powered off";
		}
		if (ret == -ENOTSUP) {
			return "no BREAK on this board (no tx-gpios)";
		}
		break;
	default:
		return "unknown action";
	}

	return ret == 0 ? NULL : "action failed";
}

static int action_handler(struct http_client_ctx *client, enum http_transaction_status status,
			  const struct http_request_ctx *req, struct http_response_ctx *rsp,
			  void *user_data)
{
	static uint8_t body[96];
	static size_t len;
	static bool too_long;
	struct action_req areq = {0};
	const char *err;
	int fields = 0;

	ARG_UNUSED(client);

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

	if (too_long) {
		respond_error(rsp, HTTP_413_PAYLOAD_TOO_LARGE, "body too large");
		return 0;
	}

	if (len > 0) {
		fields = json_obj_parse(body, len, action_descr, ARRAY_SIZE(action_descr), &areq);
		if (fields < 0) {
			respond_error(rsp, HTTP_400_BAD_REQUEST, "bad JSON");
			return 0;
		}
	}

	err = do_action((enum api_action)POINTER_TO_INT(user_data), &areq, fields);
	if (err != NULL) {
		respond_error(rsp, HTTP_400_BAD_REQUEST, err);
		return 0;
	}

	respond_status(rsp);

	return 0;
}

#define ACTION_RESOURCE(_action)                                                                   \
	{                                                                                          \
		.common = {                                                                        \
			.type = HTTP_RESOURCE_TYPE_DYNAMIC,                                        \
			.bitmask_of_supported_http_methods = BIT(HTTP_POST),                       \
			.content_type = "application/json",                                        \
		},                                                                                 \
		.cb = action_handler,                                                              \
		.user_data = INT_TO_POINTER(_action),                                              \
	}

static struct http_resource_detail_dynamic power_detail = ACTION_RESOURCE(API_POWER);
static struct http_resource_detail_dynamic reset_detail = ACTION_RESOURCE(API_RESET);
static struct http_resource_detail_dynamic boot_detail = ACTION_RESOURCE(API_BOOT);
static struct http_resource_detail_dynamic mode_detail = ACTION_RESOURCE(API_MODE);
static struct http_resource_detail_dynamic break_detail = ACTION_RESOURCE(API_BREAK);

/* --- /api/aux ------------------------------------------------------------ */

struct aux_req {
	int32_t baud;
	int32_t data_bits;
	char *parity;
	int32_t stop_bits;
	char *enter;
	bool echo;
	bool esptool_reset;
};

static const struct json_obj_descr aux_req_descr[] = {
	JSON_OBJ_DESCR_PRIM(struct aux_req, baud, JSON_TOK_NUMBER),
	JSON_OBJ_DESCR_PRIM(struct aux_req, data_bits, JSON_TOK_NUMBER),
	JSON_OBJ_DESCR_PRIM(struct aux_req, parity, JSON_TOK_STRING),
	JSON_OBJ_DESCR_PRIM(struct aux_req, stop_bits, JSON_TOK_NUMBER),
	JSON_OBJ_DESCR_PRIM(struct aux_req, enter, JSON_TOK_STRING),
	JSON_OBJ_DESCR_PRIM(struct aux_req, echo, JSON_TOK_TRUE),
	JSON_OBJ_DESCR_PRIM(struct aux_req, esptool_reset, JSON_TOK_TRUE),
};

static int index_of(const char *s, const char *const *names, int count)
{
	for (int i = 0; i < count; i++) {
		if (strcmp(s, names[i]) == 0) {
			return i;
		}
	}

	return -1;
}

/* Fields of the request over the saved settings; NULL or an error message */
static const char *aux_update(struct aux_config *cfg, const struct aux_req *req, int fields)
{
	static const char *const parities[] = {"none", "odd", "even"};
	static const char *const enters[] = {"cr", "lf", "crlf"};
	int i;

	if (fields & BIT(0)) {
		cfg->baud = req->baud;
	}
	if (fields & BIT(1)) {
		cfg->data_bits = req->data_bits;
	}
	if (fields & BIT(2)) {
		i = index_of(req->parity, parities, ARRAY_SIZE(parities));
		if (i < 0) {
			return "parity must be none, odd or even";
		}
		cfg->parity = i;
	}
	if (fields & BIT(3)) {
		cfg->stop_bits = req->stop_bits;
	}
	if (fields & BIT(4)) {
		i = index_of(req->enter, enters, ARRAY_SIZE(enters));
		if (i < 0) {
			return "enter must be cr, lf or crlf";
		}
		cfg->enter = i;
	}
	if (fields & BIT(5)) {
		cfg->echo = req->echo;
	}
	if (fields & BIT(6)) {
		cfg->esptool_reset = req->esptool_reset;
	}

	return NULL;
}

static void respond_aux(struct http_response_ctx *rsp)
{
	struct aux_stats st;
	int len = aux_config_json(resp_buf, sizeof(resp_buf), "aux");

	aux_stats_get(&st);
	/* Append the clients to the settings object */
	snprintf(&resp_buf[len - 1], sizeof(resp_buf) - len + 1,
		 ",\"web_clients\":%u,\"web_slots\":%d,\"rfc2217\":%s,\"rfc2217_port\":%d,"
		 "\"raw\":%s,\"raw_port\":%d,\"rx\":%u,\"tx\":%u,\"dropped\":%u}",
		 st.web_clients, CONFIG_BAY_CONSOLE_WEB_CLIENTS, st.rfc2217_client ? "true" : "false",
		 CONFIG_BAY_RFC2217_PORT, st.raw_client ? "true" : "false", CONFIG_BAY_AUX_TCP_PORT,
		 st.rx, st.tx, st.dropped);

	rsp->body = resp_buf;
	rsp->body_len = strlen(resp_buf);
	rsp->final_chunk = true;
}

static int aux_handler(struct http_client_ctx *client, enum http_transaction_status status,
		       const struct http_request_ctx *req, struct http_response_ctx *rsp,
		       void *user_data)
{
	static uint8_t body[192];
	static size_t len;
	static bool too_long;
	struct aux_req areq = {0};
	struct aux_config cfg;
	const char *err;
	int fields;
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

	if (client->method == HTTP_POST) {
		if (too_long) {
			respond_error(rsp, HTTP_413_PAYLOAD_TOO_LARGE, "body too large");
			return 0;
		}
		fields = json_obj_parse(body, len, aux_req_descr, ARRAY_SIZE(aux_req_descr), &areq);
		if (fields < 0) {
			respond_error(rsp, HTTP_400_BAD_REQUEST, "bad JSON");
			return 0;
		}

		aux_config_get(&cfg, true);
		err = aux_update(&cfg, &areq, fields);
		if (err != NULL) {
			respond_error(rsp, HTTP_400_BAD_REQUEST, err);
			return 0;
		}
		ret = aux_config_set(&cfg, true);
		if (ret == -EINVAL) {
			respond_error(rsp, HTTP_400_BAD_REQUEST,
				      "baud 300..5000000, data bits 5..8, stop bits 1 or 2");
			return 0;
		}
		if (ret != 0) {
			respond_error(rsp, HTTP_500_INTERNAL_SERVER_ERROR, "the UART refused it");
			return 0;
		}
	}

	respond_aux(rsp);

	return 0;
}

static struct http_resource_detail_dynamic aux_detail = {
	.common = {
		.type = HTTP_RESOURCE_TYPE_DYNAMIC,
		.bitmask_of_supported_http_methods = BIT(HTTP_GET) | BIT(HTTP_POST),
		.content_type = "application/json",
	},
	.cb = aux_handler,
};

static struct http_resource_detail_dynamic status_detail = {
	.common = {
		.type = HTTP_RESOURCE_TYPE_DYNAMIC,
		.bitmask_of_supported_http_methods = BIT(HTTP_GET),
		.content_type = "application/json",
	},
	.cb = status_handler,
};

/* --- /metrics ------------------------------------------------------------ */

PROMETHEUS_COLLECTOR_DEFINE(bay_collector);

/* The library wants one label per metric: the bay id (set per scrape) */
#define BAY_LABEL ({.key = "bay", .value = ""})

PROMETHEUS_GAUGE_DEFINE(bay_dut_vbus_volts, "DUT VBUS voltage after the switch", BAY_LABEL,
			&bay_collector);
PROMETHEUS_GAUGE_DEFINE(bay_dut_current_amperes, "DUT VBUS current", BAY_LABEL, &bay_collector);
PROMETHEUS_GAUGE_DEFINE(bay_dut_power_watts, "DUT VBUS power", BAY_LABEL, &bay_collector);
PROMETHEUS_GAUGE_DEFINE(bay_dut_power_on, "DUT VBUS switch on (1) or off (0)", BAY_LABEL,
			&bay_collector);
PROMETHEUS_GAUGE_DEFINE(bay_dut_fault, "DUT VBUS in current limit or cut by a fault", BAY_LABEL,
			&bay_collector);
PROMETHEUS_COUNTER_DEFINE(bay_dut_faults_total, "DUT VBUS faults since boot", BAY_LABEL,
			  &bay_collector);
PROMETHEUS_GAUGE_DEFINE(bay_usb_devices, "USB devices enumerated on the DUT port", BAY_LABEL,
			&bay_collector);
PROMETHEUS_GAUGE_DEFINE(bay_usbip_sessions, "Open USB/IP sessions", BAY_LABEL, &bay_collector);
PROMETHEUS_COUNTER_DEFINE(bay_aux_rx_bytes_total, "Bytes from the DUT console to the client",
			  BAY_LABEL, &bay_collector);
PROMETHEUS_COUNTER_DEFINE(bay_aux_tx_bytes_total, "Bytes from the client to the DUT console",
			  BAY_LABEL, &bay_collector);

static struct prometheus_metric *const metrics[] = {
	&bay_dut_vbus_volts.base,   &bay_dut_current_amperes.base, &bay_dut_power_watts.base,
	&bay_dut_power_on.base,     &bay_dut_fault.base,           &bay_dut_faults_total.base,
	&bay_usb_devices.base,      &bay_usbip_sessions.base,      &bay_aux_rx_bytes_total.base,
	&bay_aux_tx_bytes_total.base,
};

static char metrics_buf[2048];

static void metrics_update(void)
{
	struct status_doc s;
	const char *label = bay_id()[0] != '\0' ? bay_id() : net_hostname_get();

	status_fill(&s);

	ARRAY_FOR_EACH(metrics, i) {
		metrics[i]->labels[0].value = label;
	}

	/* Gauges reject negative values: clamp the INA226 offset around 0 A */
	prometheus_gauge_set(&bay_dut_vbus_volts, MAX(s.dut.mv, 0) / 1000.0);
	prometheus_gauge_set(&bay_dut_current_amperes, MAX(s.dut.ma, 0) / 1000.0);
	prometheus_gauge_set(&bay_dut_power_watts, MAX(s.dut.mw, 0) / 1000.0);
	prometheus_gauge_set(&bay_dut_power_on, s.dut.on ? 1.0 : 0.0);
	prometheus_gauge_set(&bay_dut_fault, (s.dut.fault || s.dut.latched) ? 1.0 : 0.0);
	prometheus_counter_set(&bay_dut_faults_total, (uint64_t)s.dut.faults);
	prometheus_gauge_set(&bay_usb_devices, s.usb.devices);
	prometheus_gauge_set(&bay_usbip_sessions, s.usb.sessions);
	prometheus_counter_set(&bay_aux_rx_bytes_total, (uint32_t)s.aux.rx);
	prometheus_counter_set(&bay_aux_tx_bytes_total, (uint32_t)s.aux.tx);
}

static int metrics_handler(struct http_client_ctx *client, enum http_transaction_status status,
			   const struct http_request_ctx *req, struct http_response_ctx *rsp,
			   void *user_data)
{
	int ret;

	ARG_UNUSED(client);
	ARG_UNUSED(req);
	ARG_UNUSED(user_data);

	if (status != HTTP_SERVER_REQUEST_DATA_FINAL) {
		return 0;
	}

	metrics_update();
	ret = prometheus_format_exposition(&bay_collector, metrics_buf, sizeof(metrics_buf));
	if (ret < 0) {
		LOG_ERR("metrics formatting failed: %d", ret);
		return ret;
	}

	rsp->body = metrics_buf;
	rsp->body_len = strlen(metrics_buf);
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

/* --- Static files: the page and xterm.js, gzipped into the image ----------- */

static const uint8_t index_html_gz[] = {
#include "index.html.gz.inc"
};

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

#define STATIC_DETAIL(_data, _type)                                                                \
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

static struct http_resource_detail_static index_detail =
	STATIC_DETAIL(index_html_gz, "text/html");
static struct http_resource_detail_static xterm_mjs_detail =
	STATIC_DETAIL(xterm_mjs_gz, "text/javascript");
static struct http_resource_detail_static xterm_css_detail =
	STATIC_DETAIL(xterm_css_gz, "text/css");
static struct http_resource_detail_static addon_fit_mjs_detail =
	STATIC_DETAIL(addon_fit_mjs_gz, "text/javascript");
static struct http_resource_detail_static xterm_license_detail =
	STATIC_DETAIL(xterm_license_gz, "text/plain");

/* --- /console/ws/<slot>: one WebSocket resource (and buffer) per console --- */

static int console_ws_setup(int ws_socket, struct http_request_ctx *request_ctx, void *user_data)
{
	ARG_UNUSED(request_ctx);

	return aux_console_ws_attach(POINTER_TO_INT(user_data), ws_socket);
}

/*
 * The server registers each WebSocket with its resource's data buffer, so
 * two consoles on one resource would share it: one resource per slot.
 */
#define CONSOLE_WS(_slot, _)                                                                       \
	static uint8_t console_ws_buf_##_slot[256];                                                \
	static struct http_resource_detail_websocket console_ws_detail_##_slot = {                 \
		.common = {                                                                        \
			.type = HTTP_RESOURCE_TYPE_WEBSOCKET,                                      \
			.bitmask_of_supported_http_methods = BIT(HTTP_GET),                        \
		},                                                                                 \
		.cb = console_ws_setup,                                                            \
		.data_buffer = console_ws_buf_##_slot,                                             \
		.data_buffer_len = sizeof(console_ws_buf_##_slot),                                 \
		.user_data = INT_TO_POINTER(_slot),                                                \
	}

/* --- Service ------------------------------------------------------------- */

static uint16_t http_port = CONFIG_BAY_HTTP_PORT;

HTTP_SERVICE_DEFINE(bay_http, NULL, &http_port, CONFIG_HTTP_SERVER_MAX_CLIENTS, 4, NULL, NULL,
		    NULL);

HTTP_RESOURCE_DEFINE(index_res, bay_http, "/", &index_detail);
HTTP_RESOURCE_DEFINE(status_res, bay_http, "/api/status", &status_detail);
HTTP_RESOURCE_DEFINE(power_res, bay_http, "/api/power", &power_detail);
HTTP_RESOURCE_DEFINE(reset_res, bay_http, "/api/reset", &reset_detail);
HTTP_RESOURCE_DEFINE(boot_res, bay_http, "/api/boot", &boot_detail);
HTTP_RESOURCE_DEFINE(mode_res, bay_http, "/api/mode", &mode_detail);
HTTP_RESOURCE_DEFINE(metrics_res, bay_http, "/metrics", &metrics_detail);
HTTP_RESOURCE_DEFINE(aux_res, bay_http, "/api/aux", &aux_detail);
HTTP_RESOURCE_DEFINE(break_res, bay_http, "/api/aux/break", &break_detail);
HTTP_RESOURCE_DEFINE(xterm_mjs_res, bay_http, "/xterm.mjs", &xterm_mjs_detail);
HTTP_RESOURCE_DEFINE(xterm_css_res, bay_http, "/xterm.css", &xterm_css_detail);
HTTP_RESOURCE_DEFINE(addon_fit_mjs_res, bay_http, "/addon-fit.mjs", &addon_fit_mjs_detail);
HTTP_RESOURCE_DEFINE(xterm_license_res, bay_http, "/xterm-LICENSE.txt", &xterm_license_detail);

#define CONSOLE_WS_RESOURCE(_slot, _)                                                              \
	CONSOLE_WS(_slot, _);                                                                      \
	HTTP_RESOURCE_DEFINE(console_ws_res_##_slot, bay_http, "/console/ws/" STRINGIFY(_slot),    \
			     &console_ws_detail_##_slot)

LISTIFY(CONFIG_BAY_CONSOLE_WEB_CLIENTS, CONSOLE_WS_RESOURCE, (;));

int web_init(void)
{
	int ret;

	/* The collector lists metrics in reverse registration order */
	for (int i = ARRAY_SIZE(metrics) - 1; i >= 0; i--) {
		ret = prometheus_collector_register_metric(&bay_collector, metrics[i]);
		if (ret != 0) {
			return ret;
		}
	}

	ret = http_server_start();
	if (ret != 0) {
		return ret;
	}

	LOG_INF("web page and API on http port %d", CONFIG_BAY_HTTP_PORT);

	return 0;
}
