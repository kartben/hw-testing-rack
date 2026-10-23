/*
 * The Zephyr board target of each slot (the bay's one DUT, or a DATA x4's
 * ports), for the CI host's hardware map: board, west runner, probe id,
 * console, and whether twister uses it.  Set from the page, saved in settings
 * ("brd/<port>") with the USB identity of the device it was set for: another
 * board in the slot shows up as a mismatch.  tools/bayctl.py hwmap reads them
 * from every node (GET /api/boards).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <ctype.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/data/json.h>
#include <zephyr/settings/settings.h>
#include <zephyr/logging/log.h>

#include "bay.h"

LOG_MODULE_REGISTER(boards, CONFIG_BAY_LOG_LEVEL);

#define REC_VERSION 1
#define BOARD_LEN   64
#define RUNNER_LEN  24
#define PROBE_LEN   48
#define CONSOLE_LEN 8

struct board_rec {
	uint8_t version; /* 0: no target */
	uint8_t map;     /* in twister's hardware map */
	uint8_t pinned;  /* vid, pid, serial: the device it was set for */
	uint8_t pad;
	uint16_t vid;
	uint16_t pid;
	char board[BOARD_LEN];
	char runner[RUNNER_LEN];
	char probe_id[PROBE_LEN];
	char console[CONSOLE_LEN];
	char serial[USB_STR_LEN];
};

static BAY_EXT_RAM struct board_rec recs[BOARDS_MAX];
static BAY_EXT_RAM struct usb_dev_info devs[USB_INFO_MAX];
static K_MUTEX_DEFINE(lock);

/* --- Settings: "brd/1" .. "brd/4" ------------------------------------------- */

static int boards_settings_set(const char *name, size_t len, settings_read_cb read_cb,
			       void *cb_arg)
{
	struct board_rec r;
	ssize_t n;

	if (name == NULL || name[0] < '1' || name[0] > '0' + BOARDS_MAX || name[1] != '\0') {
		return -ENOENT;
	}
	/* A record from another firmware layout is ignored */
	if (len != sizeof(r)) {
		return 0;
	}
	n = read_cb(cb_arg, &r, sizeof(r));
	if (n == sizeof(r) && r.version == REC_VERSION) {
		r.board[BOARD_LEN - 1] = '\0';
		r.runner[RUNNER_LEN - 1] = '\0';
		r.probe_id[PROBE_LEN - 1] = '\0';
		r.console[CONSOLE_LEN - 1] = '\0';
		r.serial[USB_STR_LEN - 1] = '\0';
		recs[name[0] - '1'] = r;
	}

	return n < 0 ? (int)n : 0;
}

SETTINGS_STATIC_HANDLER_DEFINE(boards, "brd", NULL, boards_settings_set, NULL, NULL);

int boards_slots(void)
{
	return ports_count() > 0 ? ports_count() : 1;
}

/* --- The device in a slot ----------------------------------------------------- */

/* busid is 1-1.<hub_port> or behind it (a board with its own hub) */
static bool on_hub_port(const char *busid, uint8_t hub_port)
{
	char prefix[12];
	size_t n = snprintf(prefix, sizeof(prefix), "1-1.%u", hub_port);

	return strncmp(busid, prefix, n) == 0 && (busid[n] == '\0' || busid[n] == '.');
}

/* A device a CI host flashes or reads a console through */
static bool useful(const struct usb_dev_info *u)
{
	return u->tty_n > 0 || (u->classes & USB_CLS_PROBE);
}

/*
 * What is in a slot now: of its devices (a board with a hub shows several),
 * the first with a tty or a probe, else the first; NULL when empty
 */
static const struct usb_dev_info *slot_device(int port, int n)
{
	const struct usb_dev_info *best = NULL;
	struct port_info pi;
	bool multi = ports_count() > 0;

	if (multi && ports_info(port, &pi) != 0) {
		return NULL;
	}
	for (int i = 0; i < n; i++) {
		const struct usb_dev_info *u = &devs[i];
		if ((u->classes & USB_CLS_HUB) || (multi && !on_hub_port(u->busid, pi.hub_port))) {
			continue;
		}
		if (best == NULL || (useful(u) && !useful(best))) {
			best = u;
		}
	}

	return best;
}

static bool mismatch(const struct board_rec *r, const struct usb_dev_info *u)
{
	if (r->version == 0 || !r->pinned || u == NULL) {
		return false;
	}
	if (r->serial[0] != '\0') {
		return strcmp(r->serial, u->serial) != 0;
	}

	return r->vid != u->vid || r->pid != u->pid;
}

/* --- JSON ------------------------------------------------------------------------ */

static char *put(char *p, char *end, const char *fmt, ...)
{
	va_list ap;
	int n;

	if (p >= end) {
		return end;
	}
	va_start(ap, fmt);
	n = vsnprintf(p, end - p, fmt, ap);
	va_end(ap);

	return n < 0 || n >= end - p ? end : p + n;
}

/* A string field, null when empty */
static char *str_or_null(char *p, char *end, const char *s)
{
	return p >= end ? end : bay_json_str(p, end, s);
}

static char *slot_json(char *p, char *end, int port, const struct usb_dev_info *u)
{
	const struct board_rec *r = &recs[port - 1];
	bool set = r->version != 0;
	char name[24];

	bay_slot_name(ports_count() > 0 ? port : 0, name, sizeof(name));
	p = put(p, end, "{\"slot\":\"%s\",\"port\":%d,\"board\":", name, port);
	p = str_or_null(p, end, set ? r->board : "");
	p = put(p, end, ",\"runner\":");
	p = str_or_null(p, end, set ? r->runner : "");
	p = put(p, end, ",\"probe_id\":");
	p = str_or_null(p, end, set ? r->probe_id : "");
	p = put(p, end, ",\"console\":\"%s\",\"map\":%s,\"pinned\":", set ? r->console : "usb",
		!set || r->map ? "true" : "false");
	if (set && r->pinned) {
		p = put(p, end, "{\"vid\":\"%04x\",\"pid\":\"%04x\",\"serial\":", r->vid, r->pid);
		p = str_or_null(p, end, r->serial);
		p = put(p, end, "}");
	} else {
		p = put(p, end, "null");
	}

	p = put(p, end, ",\"device\":");
	if (u != NULL) {
		p = put(p, end, "{\"busid\":\"%s\",\"vid\":\"%04x\",\"pid\":\"%04x\",",
			u->busid, u->vid, u->pid);
		p = put(p, end, "\"manufacturer\":");
		p = str_or_null(p, end, u->manufacturer);
		p = put(p, end, ",\"product\":");
		p = str_or_null(p, end, u->product);
		p = put(p, end, ",\"serial\":");
		p = str_or_null(p, end, u->serial);
		p = put(p, end, ",\"strings\":%s,\"ttys\":[", u->strings ? "true" : "false");
		for (int i = 0; i < u->tty_n; i++) {
			/* As udev numbers them: ID_USB_INTERFACE_NUM, a serial chip's port 0 */
			p = put(p, end, "%s{\"if\":\"%02x\"%s}", i ? "," : "", u->tty_if[i],
				u->tty_bridge ? ",\"port\":0" : "");
		}
		p = put(p, end, "]}");
	} else {
		p = put(p, end, "null");
	}

	return put(p, end, ",\"mismatch\":%s}", mismatch(r, u) ? "true" : "false");
}

int boards_json(char *buf, size_t size)
{
	char *p = buf, *end = buf + size;
	int n = usb_info_list(devs, ARRAY_SIZE(devs));

	k_mutex_lock(&lock, K_FOREVER);
	p = put(p, end, "{\"slots\":[");
	for (int port = 1; port <= boards_slots(); port++) {
		p = put(p, end, port > 1 ? "," : "");
		p = slot_json(p, end, port, slot_device(port, MAX(n, 0)));
	}
	p = put(p, end, "]}");
	k_mutex_unlock(&lock);

	return p < end ? p - buf : -ENOMEM;
}

int boards_slot_json(char *buf, size_t size, int port)
{
	char *p;
	int n;

	if (port < 1 || port > boards_slots()) {
		return -ENOENT;
	}
	n = usb_info_list(devs, ARRAY_SIZE(devs));
	k_mutex_lock(&lock, K_FOREVER);
	p = slot_json(buf, buf + size, port, slot_device(port, MAX(n, 0)));
	k_mutex_unlock(&lock);

	return p < buf + size ? p - buf : -ENOMEM;
}

/* --- PUT /api/ports/<n>/board ---------------------------------------------------- */

struct pin_req {
	char *vid;
	char *pid;
	char *serial;
};

struct board_req {
	char *board;
	char *runner;
	char *probe_id;
	char *console;
	bool map;
	struct pin_req pin;
};

static const struct json_obj_descr pin_descr[] = {
	JSON_OBJ_DESCR_PRIM(struct pin_req, vid, JSON_TOK_STRING),
	JSON_OBJ_DESCR_PRIM(struct pin_req, pid, JSON_TOK_STRING),
	JSON_OBJ_DESCR_PRIM(struct pin_req, serial, JSON_TOK_STRING),
};

/* Null values are skipped: as if the field were not there */
static const struct json_obj_descr board_descr[] = {
	JSON_OBJ_DESCR_PRIM(struct board_req, board, JSON_TOK_STRING),
	JSON_OBJ_DESCR_PRIM(struct board_req, runner, JSON_TOK_STRING),
	JSON_OBJ_DESCR_PRIM(struct board_req, probe_id, JSON_TOK_STRING),
	JSON_OBJ_DESCR_PRIM(struct board_req, console, JSON_TOK_STRING),
	JSON_OBJ_DESCR_PRIM(struct board_req, map, JSON_TOK_TRUE),
	JSON_OBJ_DESCR_OBJECT(struct board_req, pin, pin_descr),
};

#define F_BOARD   BIT(0)
#define F_RUNNER  BIT(1)
#define F_PROBE   BIT(2)
#define F_CONSOLE BIT(3)
#define F_MAP     BIT(4)
#define F_PIN     BIT(5)

/* 1 to max characters, each one ok() */
static bool made_of(const char *s, size_t max, bool (*ok)(char c))
{
	size_t n = strlen(s);

	if (n == 0 || n > max) {
		return false;
	}
	for (size_t i = 0; i < n; i++) {
		if (!ok(s[i])) {
			return false;
		}
	}

	return true;
}

static bool alnum(char c)
{
	return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9');
}

/* Zephyr board targets: nucleo_g474re, mimxrt1060_evk@B/mimxrt1062/qspi */
static bool board_char(char c)
{
	return alnum(c) || strchr("_@./+-", c) != NULL;
}

static bool runner_char(char c)
{
	return (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_' || c == '-';
}

/* A probe's serial number: printable, no space, quote or backslash (JSON as is) */
static bool probe_char(char c)
{
	return c > ' ' && c <= '~' && c != '"' && c != '\\';
}

static bool serial_char(char c)
{
	return c >= ' ' && c <= '~' && c != '"' && c != '\\';
}

static bool hex4(const char *s, uint16_t *v)
{
	char *e;
	unsigned long n = strtoul(s, &e, 16);

	if (strlen(s) != 4 || *e != '\0') {
		return false;
	}
	*v = (uint16_t)n;

	return true;
}

static bool console_valid(const char *c)
{
	return strcmp(c, "usb") == 0 || strcmp(c, "aux") == 0 || strcmp(c, "none") == 0 ||
	       (strncmp(c, "usb:", 4) == 0 && strlen(c) == 6 && isxdigit((int)c[4]) &&
		isxdigit((int)c[5]) && !isupper((int)c[4]) && !isupper((int)c[5]));
}

static int save(int port)
{
	char key[8];

	snprintf(key, sizeof(key), "brd/%d", port);

	return recs[port - 1].version != 0
		       ? settings_save_one(key, &recs[port - 1], sizeof(recs[port - 1]))
		       : settings_delete(key);
}

const char *boards_put(int port, char *body, size_t len)
{
	static struct board_req req;
	struct board_rec r = {.version = REC_VERSION, .map = 1};
	int fields;
	int n;

	if (port < 1 || port > boards_slots()) {
		return "no such port";
	}
	memset(&req, 0, sizeof(req));
	fields = json_obj_parse(body, len, board_descr, ARRAY_SIZE(board_descr), &req);
	if (fields < 0) {
		return "bad JSON";
	}

	/* No board: the slot has no target any more */
	if (!(fields & F_BOARD) || req.board[0] == '\0') {
		k_mutex_lock(&lock, K_FOREVER);
		memset(&recs[port - 1], 0, sizeof(recs[port - 1]));
		k_mutex_unlock(&lock);
		return save(port) == 0 ? NULL : "not saved";
	}

	if (!made_of(req.board, BOARD_LEN - 1, board_char)) {
		return "board: a Zephyr board target, 1-63 of A-Z a-z 0-9 _ @ . / + -";
	}
	strcpy(r.board, req.board);
	if ((fields & F_RUNNER) && req.runner[0] != '\0') {
		if (!made_of(req.runner, RUNNER_LEN - 1, runner_char)) {
			return "runner: a west runner, 1-23 of a-z 0-9 _ -";
		}
		strcpy(r.runner, req.runner);
	}
	if ((fields & F_PROBE) && req.probe_id[0] != '\0') {
		if (!made_of(req.probe_id, PROBE_LEN - 1, probe_char)) {
			return "probe_id: 1-47 printable characters, no space, quote or backslash";
		}
		strcpy(r.probe_id, req.probe_id);
	}
	strcpy(r.console, "usb");
	if ((fields & F_CONSOLE) && req.console[0] != '\0') {
		if (!console_valid(req.console)) {
			return "console: usb, usb:<interface, 2 hex digits>, aux or none";
		}
		if (strcmp(req.console, "aux") == 0 && ports_count() > 0) {
			return "console: a DATA x4 port has no AUX UART: its board's USB, or none";
		}
		strcpy(r.console, req.console);
	}
	if (fields & F_MAP) {
		r.map = req.map;
	}

	/* Pinned to the body's device (a restore), else to the one in the slot now */
	if (fields & F_PIN) {
		if (req.pin.vid == NULL || req.pin.pid == NULL || !hex4(req.pin.vid, &r.vid) ||
		    !hex4(req.pin.pid, &r.pid) ||
		    (req.pin.serial != NULL && req.pin.serial[0] != '\0' &&
		     !made_of(req.pin.serial, USB_STR_LEN - 1, serial_char))) {
			return "pin: {\"vid\": \"0483\", \"pid\": \"374b\", \"serial\": \"...\"}";
		}
		if (req.pin.serial != NULL) {
			strcpy(r.serial, req.pin.serial);
		}
		r.pinned = 1;
	} else {
		const struct usb_dev_info *u;

		n = usb_info_list(devs, ARRAY_SIZE(devs));
		k_mutex_lock(&lock, K_FOREVER);
		u = slot_device(port, MAX(n, 0));
		if (u != NULL) {
			r.pinned = 1;
			r.vid = u->vid;
			r.pid = u->pid;
			strcpy(r.serial, u->serial);
		}
		k_mutex_unlock(&lock);
	}

	k_mutex_lock(&lock, K_FOREVER);
	recs[port - 1] = r;
	k_mutex_unlock(&lock);
	LOG_INF("port %d: board %s", port, r.board);

	return save(port) == 0 ? NULL : "not saved";
}
