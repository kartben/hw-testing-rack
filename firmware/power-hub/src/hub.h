/*
 * hw-testing-rack power hub: shared declarations.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef HUB_H_
#define HUB_H_

#include <stdbool.h>
#include <stdint.h>

#include <zephyr/kernel.h>
#include <zephyr/drivers/can.h>
#include <zephyr/drivers/mfd/ap33772s.h>

#include <hwtr/rack_hub.h>

#define HUB_ROWS RACK_ROWS

/* --- Events: what the web page and "hub events" show (events.c) ----------- */

enum hub_ev_kind {
	HUB_EV_PD,
	HUB_EV_ROW,
	HUB_EV_FAULT,
	HUB_EV_CAN,
	HUB_EV_NODE,
};

struct hub_event {
	int64_t t_ms; /* uptime */
	uint8_t kind;
	char text[80];
};

void hub_event(enum hub_ev_kind kind, const char *fmt, ...);
/* Newest first; returns how many */
int hub_events_get(struct hub_event *out, int max);
const char *hub_ev_kind_str(uint8_t kind);

/* --- USB-C PD input (pd.c) ------------------------------------------------- */

enum hub_pd_state {
	HUB_PD_NONE,     /* no VBUS: the controller runs from its console USB-C */
	HUB_PD_STARTING, /* VBUS up, talking to the sink */
	HUB_PD_SPR,      /* contract up to 20 V */
	HUB_PD_EPR,      /* 28 V EPR contract */
};

struct hub_pd_status {
	enum hub_pd_state state;
	bool epr_pref;
	bool final;          /* contract stable: rows may be on */
	uint32_t vbus_mv;    /* VBUS_SENSE (ADC) */
	uint32_t contract_mv;
	uint32_t contract_ma;
	int selected;        /* PDO number, 0 none */
	uint32_t meter_mv;   /* the sink's own measurements */
	uint32_t meter_ma;
	int temp_c;
	uint8_t faults;      /* BIT(enum mfd_ap33772s_event) seen since boot */
	int npdos;
	struct ap33772s_pdo pdos[AP33772S_PDO_COUNT];
};

int pd_init(bool epr);
void pd_status(struct hub_pd_status *st);
const char *pd_state_str(enum hub_pd_state state);
/* Ask for 28 V EPR when offered (true) or stay at 20 V; renegotiates */
int pd_set_epr(bool epr);

/* --- Rows: eFuses, IMON, sequencing, shedding (rows.c) --------------------- */

enum hub_row_state {
	HUB_ROW_OFF,      /* switched off (by hand, or never on) */
	HUB_ROW_WAITING,  /* wanted on, waits for the contract or its turn */
	HUB_ROW_ON,
	HUB_ROW_SHED,     /* off for lack of power, comes back by itself */
	HUB_ROW_CYCLING,
};

struct hub_row_status {
	enum hub_row_state state;
	bool wanted;   /* on unless switched off by hand (saved) */
	bool fault;    /* eFuse FLT asserted now */
	uint32_t faults;
	int32_t ma;    /* IMON, at VRACK */
};

int rows_init(uint8_t wanted, const char *shed_order);
void rows_status(int row, struct hub_row_status *st);
uint8_t rows_on_mask(void);
uint8_t rows_fault_mask(void);
uint8_t rows_shed_mask(void);
int32_t rows_total_ma(void);
/* By hand, saved: on or off */
int rows_set(int row, bool on);
int rows_cycle(int row, uint32_t off_ms);
/* From pd.c: the contract (final or not) */
void rows_contract(bool final, uint32_t mv, uint32_t ma);
int rows_set_shed_order(const char *order);
const char *rows_shed_order(void);
/* The row's POS line (bus.c) */
void rows_pos(int row, bool high);
const char *rows_state_str(enum hub_row_state state);

/* --- Rack bus master (bus.c) ---------------------------------------------- */

struct hub_bus_status {
	enum can_state state;
	struct can_bus_err_cnt err;
	uint32_t rx;
	uint32_t tx;
	uint32_t tx_errors;
	uint32_t bus_off;
	uint32_t rx_fps;
	bool enumerating;
	int64_t enumerated_ms; /* uptime of the last enumeration, 0 never */
	uint32_t enumerations;
	int nodes;
	int lost;
};

int bus_init(void);
/* Enumerate the rows that are on, settle_ms from now */
void bus_enumerate(uint32_t settle_ms);
void bus_row_off(int row);
/* CMD to a node; the result arrives as an event.  Returns the sequence number */
int bus_cmd(uint8_t node, uint8_t op, const uint8_t *args, uint8_t nargs);
void bus_status(struct hub_bus_status *st);
/* Copy of a row's nodes, [1..RACK_POSITIONS]; returns the row's node count */
int bus_row_nodes(int row, struct rack_hub_node nodes[RACK_POSITIONS + 1]);

/* --- Settings (main.c) ----------------------------------------------------- */

int hub_settings_save_id(const char *id);
int hub_settings_save_epr(bool epr);
int hub_settings_save_rows(uint8_t wanted);
int hub_settings_save_shed(const char *order);

/* --- Web page, JSON API, /metrics (web.c) --------------------------------- */

int web_init(void);

#endif /* HUB_H_ */
