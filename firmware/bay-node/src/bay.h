/*
 * hw-testing-rack bay node: shared declarations.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef BAY_H_
#define BAY_H_

#include <stdbool.h>
#include <stdint.h>
#include <zephyr/kernel.h>

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
bool usb_host_running(void);
/* SERVICE mode: stop the host and route the PHY to USB-Serial-JTAG */
int usb_host_release_phy(void);
/* Back from SERVICE mode: take the PHY and start the host again */
int usb_host_claim_phy(void);

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
/* web.c: a WebSocket on /console/ws/<slot> is ready */
int aux_console_ws_attach(int slot, int ws_sock);

/* --- Network, identity (net.c) -------------------------------------------- */

#define BAY_ID_MAX_LEN 15

int bay_net_init(const char *id);
bool bay_net_connected(void);
/* IPv4 address as a string, "" when there is none */
const char *bay_net_addr(void);
const char *bay_id(void);
int bay_id_set(const char *id);

/* --- Web page, JSON API, /metrics (web.c) --------------------------------- */

int web_init(void);

/* --- Settings (main.c) ---------------------------------------------------- */

int bay_settings_save_force_pc(bool force);
int bay_settings_save_id(const char *id);
int bay_settings_save_aux(const struct aux_config *cfg);

#endif /* BAY_H_ */
