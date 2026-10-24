/*
 * Two DUTs for the Wi-Fi coexistence simulation (tools/bsim-wifi-coex), on
 * nrf52_bsim with Zephyr's own Bluetooth stack and controller.
 *
 *   -testid=peripheral  advertises every 100 ms; connected and subscribed,
 *                       it notifies 200-byte values as fast as it can
 *   -testid=central     scans, connects (30-50 ms interval, 4 s supervision
 *                       timeout), asks for a 247-byte MTU, subscribes and
 *                       counts; it scans again after a disconnection
 *   -testid=central_disc
 *                       discovery: scan, connect, wait 100 ms, disconnect,
 *                       again, timing each scan-to-connected
 *
 * -argstest wifi_ch=<n> makes the central classify the data channels within
 * 11 MHz of Wi-Fi channel n as bad (LE Set Host Channel Classification), the
 * only channel assessment Zephyr's controller acts on.
 *
 * The central prints RESULT lines just before RUN_S, which the sweep parses.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdlib.h>
#include <string.h>

#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/conn.h>
#include <zephyr/bluetooth/gatt.h>
#include <zephyr/bluetooth/hci.h>
#include <zephyr/bluetooth/uuid.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#include "bs_tracing.h"
#include "bs_types.h"
#include "bstests.h"

#define RUN_S        60
#define PAYLOAD      200
#define MAX_CYCLES   256
#define IN_FLIGHT    4
#define DISC_HOLD_MS 100

static const struct bt_uuid_128 svc_uuid =
	BT_UUID_INIT_128(BT_UUID_128_ENCODE(0x636f6578, 0x0000, 0x1000, 0x8000, 0x00805f9b34fb));
static const struct bt_uuid_128 chr_uuid =
	BT_UUID_INIT_128(BT_UUID_128_ENCODE(0x636f6578, 0x0001, 0x1000, 0x8000, 0x00805f9b34fb));

static struct bt_conn *conn;
static bool subscribed;
static bool disc_mode;
static int wifi_ch;

/* Central's counts */
static int64_t scan_started;
static int64_t connected_at;
static int64_t connected_total;
static int64_t first_connect_ms = -1;
static uint64_t rx_bytes;
static uint32_t notifications;
static uint32_t disconnects;
static uint32_t timeouts;
static uint32_t failed;
static uint32_t cycle_ms[MAX_CYCLES];
static uint32_t cycles;

/* Peripheral's counts */
static uint32_t sent;
static K_SEM_DEFINE(in_flight, IN_FLIGHT, IN_FLIGHT);

static void ccc_changed(const struct bt_gatt_attr *attr, uint16_t value)
{
	ARG_UNUSED(attr);

	subscribed = value == BT_GATT_CCC_NOTIFY;
}

BT_GATT_SERVICE_DEFINE(coex_svc, BT_GATT_PRIMARY_SERVICE(&svc_uuid),
		       BT_GATT_CHARACTERISTIC(&chr_uuid.uuid, BT_GATT_CHRC_NOTIFY, BT_GATT_PERM_NONE,
					      NULL, NULL, NULL),
		       BT_GATT_CCC(ccc_changed, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE));

static const struct bt_data ad[] = {
	BT_DATA_BYTES(BT_DATA_FLAGS, (BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR)),
	BT_DATA(BT_DATA_NAME_COMPLETE, "dut", 3),
};

/* --- Central ---------------------------------------------------------------- */

static void scan_start(void);

static uint8_t on_notify(struct bt_conn *c, struct bt_gatt_subscribe_params *params,
			 const void *data, uint16_t length)
{
	ARG_UNUSED(c);
	ARG_UNUSED(params);

	if (data != NULL) {
		rx_bytes += length;
		notifications++;
	}
	return BT_GATT_ITER_CONTINUE;
}

static struct bt_gatt_subscribe_params sub_params = {
	.notify = on_notify,
	.value = BT_GATT_CCC_NOTIFY,
};

static uint8_t on_discover(struct bt_conn *c, const struct bt_gatt_attr *attr,
			   struct bt_gatt_discover_params *params)
{
	if (attr == NULL) {
		return BT_GATT_ITER_STOP;
	}
	/* The CCC follows the value in this server's layout */
	sub_params.value_handle = bt_gatt_attr_value_handle(attr);
	sub_params.ccc_handle = sub_params.value_handle + 1;
	(void)bt_gatt_subscribe(c, &sub_params);
	return BT_GATT_ITER_STOP;
}

static struct bt_gatt_discover_params disc_params = {
	.uuid = &chr_uuid.uuid,
	.func = on_discover,
	.start_handle = BT_ATT_FIRST_ATTRIBUTE_HANDLE,
	.end_handle = BT_ATT_LAST_ATTRIBUTE_HANDLE,
	.type = BT_GATT_DISCOVER_CHARACTERISTIC,
};

static void on_mtu(struct bt_conn *c, uint8_t err, struct bt_gatt_exchange_params *params)
{
	ARG_UNUSED(err);
	ARG_UNUSED(params);

	(void)bt_gatt_discover(c, &disc_params);
}

static struct bt_gatt_exchange_params mtu_params = {.func = on_mtu};

static bool is_dut(struct bt_data *data, void *user_data)
{
	bool *found = user_data;

	if (data->type == BT_DATA_NAME_COMPLETE && data->data_len == 3 &&
	    memcmp(data->data, "dut", 3) == 0) {
		*found = true;
		return false;
	}
	return true;
}

static void device_found(const bt_addr_le_t *addr, int8_t rssi, uint8_t type,
			 struct net_buf_simple *buf)
{
	bool found = false;

	ARG_UNUSED(rssi);

	if (conn != NULL || type != BT_GAP_ADV_TYPE_ADV_IND) {
		return;
	}
	bt_data_parse(buf, is_dut, &found);
	if (!found) {
		return;
	}
	if (bt_le_scan_stop() == 0 &&
	    bt_conn_le_create(addr, BT_CONN_LE_CREATE_CONN, BT_LE_CONN_PARAM_DEFAULT, &conn) != 0) {
		conn = NULL;
		scan_start();
	}
}

static void scan_start(void)
{
	scan_started = k_uptime_get();
	(void)bt_le_scan_start(BT_LE_SCAN_PASSIVE, device_found);
}

static void disconnect_work_handler(struct k_work *work)
{
	ARG_UNUSED(work);

	if (conn != NULL) {
		(void)bt_conn_disconnect(conn, BT_HCI_ERR_REMOTE_USER_TERM_CONN);
	}
}

static K_WORK_DELAYABLE_DEFINE(disconnect_work, disconnect_work_handler);

static void central_connected(struct bt_conn *c, uint8_t err)
{
	int64_t now = k_uptime_get();

	if (err != 0) {
		/* Connection failed to be established: scan again */
		failed++;
		bt_conn_unref(conn);
		conn = NULL;
		scan_start();
		return;
	}
	connected_at = now;
	if (first_connect_ms < 0) {
		first_connect_ms = now - scan_started;
	}
	if (disc_mode) {
		if (cycles < MAX_CYCLES) {
			cycle_ms[cycles++] = (uint32_t)(now - scan_started);
		}
		k_work_schedule(&disconnect_work, K_MSEC(DISC_HOLD_MS));
	} else {
		(void)bt_gatt_exchange_mtu(c, &mtu_params);
	}
}

static void central_disconnected(struct bt_conn *c, uint8_t reason)
{
	ARG_UNUSED(c);

	connected_total += k_uptime_get() - connected_at;
	disconnects++;
	timeouts += reason == BT_HCI_ERR_CONN_TIMEOUT;
	bt_conn_unref(conn);
	conn = NULL;
	scan_start();
}

static int cmp_u32(const void *a, const void *b)
{
	uint32_t x = *(const uint32_t *)a, y = *(const uint32_t *)b;

	return (x > y) - (x < y);
}

static void central_report(void)
{
	if (conn != NULL) {
		connected_total += k_uptime_get() - connected_at;
		connected_at = k_uptime_get();
	}
	if (!disc_mode) {
		printk("RESULT flow first_connect_ms=%lld connected_ms=%lld rx_bytes=%llu "
		       "notifications=%u throughput_Bps=%llu disconnects=%u timeouts=%u failed=%u\n",
		       first_connect_ms, connected_total, rx_bytes, notifications,
		       connected_total > 0 ? rx_bytes * 1000 / connected_total : 0, disconnects,
		       timeouts, failed);
		return;
	}
	qsort(cycle_ms, cycles, sizeof(cycle_ms[0]), cmp_u32);
	uint64_t sum = 0;

	for (uint32_t i = 0; i < cycles; i++) {
		sum += cycle_ms[i];
	}
	printk("RESULT disc cycles=%u failed=%u timeouts=%u avg_ms=%llu p50_ms=%u p90_ms=%u "
	       "max_ms=%u\n",
	       cycles, failed, timeouts, cycles ? sum / cycles : 0, cycles ? cycle_ms[cycles / 2] : 0,
	       cycles ? cycle_ms[cycles * 9 / 10] : 0, cycles ? cycle_ms[cycles - 1] : 0);
}

/* --- Peripheral ------------------------------------------------------------- */

static void adv_start(void)
{
	(void)bt_le_adv_start(BT_LE_ADV_PARAM(BT_LE_ADV_OPT_CONN, 160, 160, NULL), ad,
			      ARRAY_SIZE(ad), NULL, 0);
}

static void notify_done(struct bt_conn *c, void *user_data)
{
	ARG_UNUSED(c);
	ARG_UNUSED(user_data);

	sent++;
	k_sem_give(&in_flight);
}

static void peripheral_connected(struct bt_conn *c, uint8_t err)
{
	if (err == 0) {
		conn = bt_conn_ref(c);
	}
}

static void peripheral_disconnected(struct bt_conn *c, uint8_t reason)
{
	ARG_UNUSED(c);
	ARG_UNUSED(reason);

	subscribed = false;
	bt_conn_unref(conn);
	conn = NULL;
}

static void peripheral_recycled(void)
{
	adv_start();
}

/* --- Tests ------------------------------------------------------------------ */

static bool is_central;

static void on_connected(struct bt_conn *c, uint8_t err)
{
	if (is_central) {
		central_connected(c, err);
	} else {
		peripheral_connected(c, err);
	}
}

static void on_disconnected(struct bt_conn *c, uint8_t reason)
{
	if (is_central) {
		central_disconnected(c, reason);
	} else {
		peripheral_disconnected(c, reason);
	}
}

static void on_recycled(void)
{
	if (!is_central) {
		peripheral_recycled();
	}
}

BT_CONN_CB_DEFINE(conn_cb) = {
	.connected = on_connected,
	.disconnected = on_disconnected,
	.recycled = on_recycled,
};

static void test_init(void)
{
	bst_ticker_set_next_tick_absolute((RUN_S * 1000000ULL) - 500000ULL);
}

static void central_tick(bs_time_t time)
{
	ARG_UNUSED(time);

	central_report();
}

static void peripheral_tick(bs_time_t time)
{
	ARG_UNUSED(time);

	printk("RESULT peripheral sent=%u\n", sent);
}

static void test_args(int argc, char *argv[])
{
	for (int i = 0; i < argc; i++) {
		if (strncmp(argv[i], "wifi_ch=", 8) == 0) {
			wifi_ch = atoi(&argv[i][8]);
		}
	}
}

/* The data channels within 11 MHz of the Wi-Fi channel's centre, marked bad */
static void avoid_wifi(void)
{
	uint8_t map[5] = {0xFF, 0xFF, 0xFF, 0xFF, 0x1F};
	int fc = 2407 + 5 * wifi_ch;

	for (int ch = 0; ch < 37; ch++) {
		int f = ch < 11 ? 2404 + 2 * ch : 2428 + 2 * (ch - 11);

		if (abs(f - fc) <= 11) {
			WRITE_BIT(map[ch / 8], ch % 8, 0);
		}
	}
	if (bt_le_set_chan_map(map) != 0) {
		bs_trace_error_line("bt_le_set_chan_map failed\n");
	}
}

static void central_main(void)
{
	is_central = true;
	if (bt_enable(NULL) != 0) {
		bs_trace_error_line("bt_enable failed\n");
	}
	if (wifi_ch > 0) {
		avoid_wifi();
	}
	scan_start();
}

static void central_disc_main(void)
{
	disc_mode = true;
	central_main();
}

static void peripheral_main(void)
{
	static uint8_t value[PAYLOAD];

	if (bt_enable(NULL) != 0) {
		bs_trace_error_line("bt_enable failed\n");
	}
	adv_start();

	while (true) {
		struct bt_gatt_notify_params params = {
			.uuid = &chr_uuid.uuid,
			.data = value,
			.func = notify_done,
		};
		struct bt_conn *c = conn;

		if (c == NULL || !subscribed || bt_gatt_get_mtu(c) < PAYLOAD + 3) {
			k_sleep(K_MSEC(10));
			continue;
		}
		k_sem_take(&in_flight, K_FOREVER);
		params.len = PAYLOAD;
		value[0]++;
		if (bt_gatt_notify_cb(c, &params) != 0) {
			k_sem_give(&in_flight);
			k_sleep(K_MSEC(5));
		}
	}
}

static const struct bst_test_instance tests[] = {
	{
		.test_id = "central",
		.test_descr = "Scan, connect, subscribe and count the notifications",
		.test_pre_init_f = test_init,
		.test_tick_f = central_tick,
		.test_main_f = central_main,
		.test_args_f = test_args,
	},
	{
		.test_id = "central_disc",
		.test_descr = "Scan, connect, disconnect, again: time to connect",
		.test_pre_init_f = test_init,
		.test_tick_f = central_tick,
		.test_main_f = central_disc_main,
		.test_args_f = test_args,
	},
	{
		.test_id = "peripheral",
		.test_descr = "Advertise; notify as fast as the link takes it",
		.test_pre_init_f = test_init,
		.test_tick_f = peripheral_tick,
		.test_main_f = peripheral_main,
	},
	BSTEST_END_MARKER,
};

static struct bst_test_list *install(struct bst_test_list *list)
{
	return bst_add_tests(list, tests);
}

bst_test_install_t test_installers[] = {install, NULL};

int main(void)
{
	bst_main();
	return 0;
}
