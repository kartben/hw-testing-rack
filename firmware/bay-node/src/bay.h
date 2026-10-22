/*
 * hw-testing-rack bay node: shared declarations.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef BAY_H_
#define BAY_H_

#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <zephyr/kernel.h>
#include <zephyr/usb/usb_ch9.h>

#include <hwtr/acl.h>

/*
 * Large buffers that only the CPU touches (no DMA) go to the module's PSRAM
 * when it has some: internal DRAM is what the node runs short of.  The
 * section is zeroed at boot (esp_psram.c); flash operations lock the
 * interrupts, so an ISR may use it too.
 */
#if defined(CONFIG_ESP_SPIRAM)
#define BAY_EXT_RAM __attribute__((section(".ext_ram.bss.bay")))
#else
#define BAY_EXT_RAM
#endif

/* --- DUT power, fault, RESET/BOOT (dut.c) --------------------------------- */

struct dut_power_reading {
	int32_t bus_mv;
	int32_t current_ma;
	int32_t power_mw;
};

int dut_init(void);
int dut_power_set(bool on);
bool dut_power_get(void);
int dut_power_cycle(k_timeout_t off_time);
/* FAULT pin as it is right now (current limit / thermal shutdown) */
bool dut_fault_active(void);
/* Power was cut by the firmware after a persistent fault */
bool dut_fault_latched(void);
uint32_t dut_fault_count(void);
int dut_reset_set(bool asserted);
int dut_reset_pulse(k_timeout_t width);
int dut_boot_set(bool asserted);
/* BOOT held, RESET pulsed, BOOT released: most MCUs start their ROM loader */
int dut_enter_bootloader(void);
int dut_power_read(struct dut_power_reading *r);

/* --- DATA x4 ports (ports.c) ---------------------------------------------- */

struct port_info {
	uint8_t slot;     /* DATA x4 port, 1-4: sub-slot <bay>.<slot> */
	uint8_t hub_port; /* busid 1-1.<hub_port> */
	bool on;
	bool wanted;      /* to be on after each DUT_5V on */
	bool latched;     /* off after a fault, until switched on again */
	bool meter;       /* mv, ma, mw read */
	bool usb;         /* a device on its hub port: vid, pid */
	uint32_t faults;
	int32_t mv;
	int32_t ma;
	int32_t mw;
	uint16_t vid;
	uint16_t pid;
};

int ports_init(void);
/* Ports of the DATA x4 that answered, 0 without one (a one-port node) */
int ports_count(void);
/* slot 1..4; -ENOENT no such port, -ENODEV no board */
int ports_info(int slot, struct port_info *pi);
/*
 * -EBUSY: the budget has no room (others: what the other ports draw, mA, may
 * be NULL); -EAGAIN: the board is not set up (DUT_5V off)
 */
int ports_power(int slot, bool on, int32_t *others);
int ports_power_cycle(int slot, k_timeout_t off_time, int32_t *others);
int ports_reset_pulse(int slot, k_timeout_t width);
/* BOOT held across a RESET pulse, or across a power cycle of the port */
int ports_boot(int slot, bool power_cycle, int32_t *others);
/* dut.c: DUT_5V about to go off (false), or just on (true) */
void ports_dut_power(bool on);

/* --- USB data path (usb_mux.c) -------------------------------------------- */

enum bay_data_path {
	BAY_PATH_USBIP,   /* DUT <-> ESP32-S3 USB OTG, exported over USB/IP */
	BAY_PATH_CLASSIC, /* DUT <-> front PC port (laptop plugged or forced) */
	BAY_PATH_SERVICE, /* front PC port <-> ESP32-S3, DUT data disconnected */
};

int usb_mux_init(bool force_pc);
bool usb_mux_service(void);
bool usb_mux_pc_detected(void);
bool usb_mux_force_pc_get(void);
int usb_mux_force_pc_set(bool force);
enum bay_data_path usb_mux_path(void);
const char *bay_data_path_str(enum bay_data_path path);

/* --- USB host / USB/IP (usb_host.c) --------------------------------------- */

/* Devices enumerated on the DUT port (0 or 1 without a hub) */
int usb_host_device_count(void);
/* Open TCP sessions on the USB/IP port (an attached client keeps one) */
int usb_host_usbip_sessions(void);
/* The device on the hub's downstream port n (a DATA x4 port): 0, or -ENODEV */
int usb_host_port_device(uint8_t hub_port, uint16_t *vid, uint16_t *pid);
bool usb_host_running(void);
/* SERVICE mode: stop the host and route the PHY to USB-Serial-JTAG */
int usb_host_release_phy(void);
/* Back from SERVICE mode: take the PHY and start the host again */
int usb_host_claim_phy(void);
/* The USB/IP client attached to busid: its IPv4 address and for how long */
int usb_host_usbip_client(const char *busid, uint32_t *ip, uint32_t *since_s);
/* Whether USB/IP reads the device ahead (enum usbip_read_ahead, 0: no) */
int usb_host_read_ahead(const struct usb_device_descriptor *desc);

/* --- USB devices: identity, classes, strings (usb_info.c) ----------------- */

#define USB_INFO_MAX 8
#define USB_STR_LEN  64

#define USB_CLS_CDC_ACM   BIT(0)
#define USB_CLS_HID       BIT(1)
#define USB_CLS_MSC       BIT(2)
#define USB_CLS_DFU       BIT(3)
#define USB_CLS_VENDOR    BIT(4)
#define USB_CLS_HUB       BIT(5)
#define USB_CLS_AUDIO     BIT(6)
#define USB_CLS_VIDEO     BIT(7)
#define USB_CLS_OTHER     BIT(8)
#define USB_CLS_CMSIS_DAP BIT(9)  /* says so in its product string */
#define USB_CLS_PROBE     BIT(10) /* a known debug probe */

struct usb_dev_info {
	char busid[24];     /* as USB/IP names it: 1-1, 1-1.<port>, ... */
	uint8_t addr;
	uint8_t level;      /* 1: on the root port */
	uint8_t root_port;  /* behind the hub on the root port: its port; else 0 */
	uint8_t speed;      /* enum usb_device_speed */
	uint8_t read_ahead; /* enum usbip_read_ahead */
	uint16_t vid;
	uint16_t pid;
	uint16_t classes;   /* USB_CLS_* */
	bool strings;       /* the strings below were read */
	bool offered;       /* USB/IP exports it (not a hub, not past its sessions) */
	const char *known;  /* a name from the table of known IDs, or NULL */
	char manufacturer[USB_STR_LEN];
	char product[USB_STR_LEN];
	char serial[USB_STR_LEN];
};

/* The configured devices, at most max; the strings may still be on their way */
int usb_info_list(struct usb_dev_info *out, int max);

/* --- Status LED (status_led.c) -------------------------------------------- */

int status_led_init(void);
void status_led_update(void);

/* --- AUX UART: web console, RFC 2217, raw TCP (aux_console.c) ------------- */

enum aux_parity {
	AUX_PARITY_NONE,
	AUX_PARITY_ODD,
	AUX_PARITY_EVEN,
};

/* What the web console sends for the Enter key */
enum aux_enter {
	AUX_ENTER_CR,
	AUX_ENTER_LF,
	AUX_ENTER_CRLF,
};

struct aux_config {
	uint32_t baud;
	uint8_t data_bits;  /* 5..8 */
	uint8_t parity;     /* enum aux_parity */
	uint8_t stop_bits;  /* 1 or 2 */
	uint8_t enter;      /* enum aux_enter */
	bool echo;          /* web console local echo */
	bool esptool_reset; /* RFC 2217 DTR/RTS drive BOOT/RESET (ESP auto-reset) */
};

#define AUX_CONFIG_DEFAULT                                                                         \
	{.baud = 115200, .data_bits = 8, .parity = AUX_PARITY_NONE, .stop_bits = 1,                \
	 .enter = AUX_ENTER_CR}

struct aux_stats {
	uint32_t rx;
	uint32_t tx;
	uint32_t dropped;
	uint8_t web_clients;
	bool rfc2217_client;
	bool raw_client;
};

/* stored: the settings saved in flash, or NULL for the defaults */
int aux_console_init(const struct aux_config *stored);
/* Settings in effect (an RFC 2217 client may change them), or the saved ones */
void aux_config_get(struct aux_config *cfg, bool saved);
/* Apply now; persist also saves them as the bay's settings */
int aux_config_set(const struct aux_config *cfg, bool persist);
int aux_config_json(char *buf, size_t len, const char *type);
const char *aux_parity_str(uint8_t parity);
const char *aux_enter_str(uint8_t enter);
/* Hold the DUT's RX line low for ms (needs the DUT powered) */
int aux_break(uint32_t ms);
/* DUT VBUS switched: release the TX pin while the DUT is off */
void aux_dut_power(bool on);
void aux_stats_get(struct aux_stats *st);
/* Test without a DUT: the UART loops TX back to RX (ESP32 only, else -ENOTSUP) */
int aux_loopback(bool on);
bool aux_loopback_get(void);
/* Queue bytes for the DUT like a client; returns how many fit */
size_t aux_send(const uint8_t *buf, size_t len);
/* web.c: a WebSocket on /console/ws/<slot> is ready, for a browser at ip */
int aux_console_ws_attach(int slot, int ws_sock, uint32_t ip);

/* Connected clients, for the access page: raw, RFC 2217, web console <n> */
#define AUX_CLIENT_RAW     0
#define AUX_CLIENT_RFC2217 1
#define AUX_CLIENT_WEB     2 /* + slot */

struct aux_client_info {
	int id;
	uint32_t ip;   /* IPv4, host order */
	uint16_t port; /* 0 for a web console */
	int64_t since; /* uptime, ms */
};

int aux_clients_get(struct aux_client_info *out, int max);
/* Close a client (from another thread: the console thread does it) */
int aux_client_kick(int id);

/* --- Rack bus: CAN client, POS token (rack.c) ----------------------------- */

#include <hwtr/rack_proto.h>

int bay_rack_init(void);
/* Node id from the hub (row x 16 + position), 0 until it gave one */
uint8_t bay_rack_id(void);
/* "C3", "" until the hub gave a position */
const char *bay_rack_position(void);
/* The hub's last RACK frame; false when none came for 3 s */
bool bay_rack_hub(struct rack_hub_state *st);
/* The IP address changed: INFO goes out at the next tick */
void bay_rack_info_changed(void);
/* The hub asked this node to show itself: the LED blinks */
bool bay_rack_identifying(void);

/* --- A fatal error restarts the node, reported after (fault.c) ------------ */

/* At boot: logs the fatal error that restarted the node, if any */
void fault_init(void);
/* That error ("fatal error <reason> in <thread>: <last log line>"), "" none */
const char *fault_last(void);
/* The warnings and errors logged just before it, "" none */
const char *fault_tail(void);
/* The warnings and errors since this boot (the last ones), into buf */
int fault_log_now(char *buf, size_t size);

/* --- Network, identity (net.c) -------------------------------------------- */

#define BAY_ID_MAX_LEN 15

int bay_net_init(const char *id);
bool bay_net_connected(void);
/* IPv4 address as a string, "" when there is none */
const char *bay_net_addr(void);
const char *bay_id(void);
int bay_id_set(const char *id);

/* --- Access control (access.c; rules in common/lib/acl.c, admin key in common/lib/admin.c) */

struct net_sockaddr;

#define ACCESS_MAX_CONNS 12

struct access_conn {
	char id[12];       /* "raw", "rfc2217", "web<n>", "cam<n>", "usbip:<port>", "shell:<port>" */
	const char *label; /* "RFC 2217", "USB/IP", ... */
	uint32_t ip;
	uint16_t port;
	uint8_t service; /* enum acl_service */
	int64_t since;
};

int access_init(void);
/* IPv4 address in host order, 0 when unknown */
uint32_t access_ip(const struct net_sockaddr *addr);
uint32_t access_peer(int fd);
/* May ip use svc now?  Refusals are logged */
enum acl_verdict access_check(enum acl_service svc, uint32_t ip);
/* What ip may use now (ACL_BIT() mask), nothing logged */
uint8_t access_allowed(uint32_t ip);
bool access_enabled(void);
bool access_claimed(void);
uint32_t access_refused_total(void);

/* Admin requests: X-Bay-Auth "<nonce>:<hmac>" over method, path and body */
int access_nonce(char *out);
bool access_admin(const char *auth, const char *method, const char *path, const uint8_t *body,
		  size_t len);
int access_set_key(const uint8_t *key);

/* The first admin key: start (offered key or NULL), confirm by physical presence, poll */
int access_claim_start(uint32_t ip, const uint8_t *offered, char *ticket_hex);
bool access_claim_pending(void);
int access_claim_confirm(void);
/* 0 and the key once confirmed, -EINPROGRESS while pending, -ENOENT, -ETIMEDOUT */
int access_claim_poll(uint32_t ip, const char *ticket_hex, char *key_hex, int *remaining_s);
/* Local recovery: no key, no rules, no lease */
int access_reset(void);

void access_rules_get(struct acl_rules *r);
int access_rules_set(const struct acl_rules *r);
int access_set_enabled(bool on);
/* Rules from a JSON body (modified in place): NULL or an error message */
const char *access_rules_parse(char *body, size_t len, struct acl_rules *out);

int access_lease_take(uint32_t ip, uint32_t ttl_s, const char *note);
int access_lease_release(uint32_t ip, bool force);
/* True while a lease is held */
bool access_lease_get(struct acl_lease *l, uint32_t *remaining_s);

int access_connections(struct access_conn *out, int max);
/* Close a connection by id and refuse its address that service for a while */
int access_kick(const char *id);

/* A WebSocket has no peer address: the page gets a ticket first */
int access_console_ticket(uint32_t ip, char *out);
uint32_t access_console_redeem(const char *ticket);

/* GET /api/access document; admin adds the rules and the refusal log */
int access_json(char *buf, size_t size, uint32_t ip, bool admin);

/* --- Web page, JSON API, /metrics (web.c) --------------------------------- */

int web_init(void);

/* --- Bay camera and its light (camera.c) ---------------------------------- */

struct camera_status {
	bool present;
	const char *model;
	uint16_t port;
	const char *resolution; /* "640x480" */
	const char *quality;    /* "high", "default", "low" */
	bool light;          /* the bay's setting: lit while frames are taken */
	uint16_t rotation;   /* degrees clockwise, for the page */
	bool lit;            /* the light right now */
	uint8_t clients;     /* snapshots waiting and streams */
	uint8_t streams;
	uint32_t frames;
	uint32_t errors;
	uint32_t last_size; /* bytes */
	uint32_t last_ms;   /* capture and send */
	uint32_t fps_x10;   /* while streaming */
};

struct camera_client_info {
	int slot;
	bool stream;
	uint32_t ip;
	uint16_t port;
	int64_t since; /* uptime, ms */
};

#if defined(CONFIG_BAY_CAMERA)
/* -ENODEV without a camera (the port still answers, with 503) */
int camera_init(void);
bool camera_present(void);
/* A client is watching or waiting for a snapshot */
bool camera_active(void);
void camera_status(struct camera_status *st);
/*
 * Settings by name ("exposure" = "auto", "manual" or a value...), all or
 * none: NULL, or the first error and nothing changed.  reset: the image
 * settings back to automatic first (not the resolution, quality, light,
 * rotation).
 * Saved; they reach the camera between two frames.
 */
const char *camera_configure(const char *const *names, const char *const *values, int n,
			     bool reset);
/* Setting i: its name and its value as text; false past the last */
bool camera_setting(int i, const char **name, char *value, size_t size);
/* {"resolutions": [...], ..., "brightness": [-4, 4], ...}: what may be set */
int camera_choices_json(char *buf, size_t size);
int camera_clients_get(struct camera_client_info *out, int max);
int camera_client_kick(int slot);
#else
static inline bool camera_present(void)
{
	return false;
}
static inline bool camera_active(void)
{
	return false;
}
static inline int camera_clients_get(struct camera_client_info *out, int max)
{
	ARG_UNUSED(out);
	ARG_UNUSED(max);
	return 0;
}
static inline int camera_client_kick(int slot)
{
	ARG_UNUSED(slot);
	return -ENOENT;
}
#endif

/* --- Settings (main.c) ---------------------------------------------------- */

int bay_settings_save_force_pc(bool force);
int bay_settings_save_id(const char *id);
int bay_settings_save_aux(const struct aux_config *cfg);
/* A hub has given the node a rack address once (saved the first time) */
bool bay_settings_racked(void);
int bay_settings_save_racked(void);

#endif /* BAY_H_ */
