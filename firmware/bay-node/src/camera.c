/*
 * The bay camera (an Arducam Mega on J6) and its light, on their own TCP port
 * (CONFIG_BAY_CAMERA_PORT):
 *
 *   GET /snapshot.jpg[?light=on|off|auto]   one JPEG
 *   GET /stream.mjpg[?light=on|off|auto]    MJPEG (multipart/x-mixed-replace)
 *
 * One thread owns the sensor and serves every client: it takes a frame when
 * someone waits for a snapshot or watches the stream (at most
 * CONFIG_BAY_CAMERA_FPS a second) and sends it to all of them, so the page
 * and a script share the camera.  The port has its own access right
 * ("camera"), checked on accept and by the packet filter (access.c).
 *
 * Optional: without a camera (its driver finds nothing on SPI) the port
 * answers 503, /api/camera says so and the node runs as before.
 *
 * Frames land in two buffers in PSRAM, each large enough for a whole frame,
 * so the Mega's FIFO comes over in one read.  A frame larger than a buffer
 * arrives in pieces that share a timestamp, cut at the JPEG's end
 * (hwtr/jpeg.h): the FIFO may run on past it.
 *
 * The upstream driver (video_arducam_mega.c) captures from a work item that
 * a 30 ms timer submits while streaming; video_stream_stop() does not stop
 * it, and the item resubmits itself in a loop while no buffer is queued.  So
 * captures are switched on and off by plugging the driver's work queue
 * (drained, with the buffers handed back so the frame in progress can
 * finish), and that queue runs at the lowest application priority: its SPI
 * reads and any spin give way to the network.
 *
 * The light: lit while frames are taken for a client that wants it (the
 * bay's setting, or ?light=), the first frame waits for the sensor's auto
 * exposure; off when nobody watches.  While the bay is reserved, only the
 * lease holder switches it on.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <stdio.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/led.h>
#include <zephyr/net/socket.h>
#include <zephyr/settings/settings.h>
#include <zephyr/sys/atomic.h>
#include <zephyr/video/video.h>
#include <zephyr/video/controls.h>
#include <zephyr/logging/log.h>

#include <hwtr/acl.h>
#include <hwtr/jpeg.h>

#include "bay.h"

LOG_MODULE_REGISTER(camera, CONFIG_BAY_LOG_LEVEL);

static const struct device *const cam = DEVICE_DT_GET(DT_NODELABEL(camera));
#if DT_NODE_HAS_STATUS_OKAY(DT_NODELABEL(camera_light))
static const struct device *const light_dev = DEVICE_DT_GET(DT_NODELABEL(camera_light));
#else
static const struct device *const light_dev;
#endif

/* The driver's work queue (video_arducam_mega.c) */
extern struct k_work_q ac_work_q;

#define NBUF              2 /* CONFIG_VIDEO_BUFFER_POOL_NUM_MAX */
#define FRAME_TIMEOUT_MS  3000
#define REQUEST_MAX       4096
#define RECV_TIMEOUT_MS   1000
#define SEND_TIMEOUT_MS   3000
#define PRIORITY          K_PRIO_PREEMPT(8)

/* The driver's JPEG sizes, the 96x96 and 128x128 thumbnails aside */
static const struct {
	uint16_t w;
	uint16_t h;
	const char *name;
} resolutions[] = {
	{320, 240, "320x240"},   {640, 480, "640x480"},     {1280, 720, "1280x720"},
	{1600, 1200, "1600x1200"}, {1920, 1080, "1920x1080"},
};
/* The Mega's JPEG quality levels, in its order */
static const char *const qualities[] = {"high", "default", "low"};

/* --- Settings: "cam/cfg" -------------------------------------------------------- */

struct cam_cfg {
	uint8_t res;     /* index in resolutions[] */
	uint8_t quality; /* index in qualities[] */
	uint8_t light;   /* 1: lit unless a client says otherwise */
	uint8_t pad;
};

static struct cam_cfg cfg = {.res = 1, .quality = 1, .light = 1};

static int cam_settings_set(const char *key, size_t len, settings_read_cb read_cb, void *cb_arg)
{
	struct cam_cfg c;

	if (!settings_name_steq(key, "cfg", NULL) || len != sizeof(c)) {
		return 0;
	}
	if (read_cb(cb_arg, &c, sizeof(c)) == sizeof(c) && c.res < ARRAY_SIZE(resolutions) &&
	    c.quality < ARRAY_SIZE(qualities)) {
		cfg = c;
	}
	return 0;
}

SETTINGS_STATIC_HANDLER_DEFINE(bay_cam, "cam", NULL, cam_settings_set, NULL, NULL);

/* --- State ---------------------------------------------------------------------- */

struct cam_client {
	int fd;
	bool stream;  /* else a snapshot, closed after one frame */
	int8_t light; /* -1 the bay's setting, 0 off, 1 on */
	uint32_t ip;
	uint16_t port;
	int64_t since;
};

static struct cam_client clients[CONFIG_BAY_CAMERA_CLIENTS];
static atomic_t kick_mask;
static K_MUTEX_DEFINE(lock); /* cfg, the counters, clients[] for the readers */

static bool present;
static const char *model = "";
static bool fmt_dirty = true;
static bool capturing;
static bool lit;
static uint32_t frames, errors, last_size, last_ms;
static int64_t fps_t0;
static uint32_t fps_frames, fps_x10;

/* --- The light -------------------------------------------------------------------- */

static void light_set(bool on)
{
	if (light_dev == NULL || !device_is_ready(light_dev) || on == lit) {
		return;
	}
	(void)(on ? led_on(light_dev, 0) : led_off(light_dev, 0));
	lit = on;
}

/* --- The sensor ------------------------------------------------------------------- */

/*
 * video_set_ctrl() skips a value equal to the one it has cached, and that
 * cache starts at the control's default without the camera being written
 * (quality 0, "high", would never reach it after a boot): the first time,
 * go through another value so that the camera gets this one
 */
static int set_ctrl_written(uint32_t id, int32_t val, bool *written)
{
	struct video_control c = {.id = id};

	if (!*written && video_get_ctrl(cam, &c) == 0 && c.val == val) {
		c.val = val == 0 ? 1 : 0;
		(void)video_set_ctrl(cam, &c);
	}
	c.val = val;
	*written = true;
	return video_set_ctrl(cam, &c);
}

static int apply_format(void)
{
	static bool quality_written;
	struct video_format fmt = {
		.type = VIDEO_BUF_TYPE_OUTPUT,
		.pixelformat = VIDEO_PIX_FMT_JPEG,
	};
	int32_t quality;
	int ret;

	k_mutex_lock(&lock, K_FOREVER);
	fmt.width = resolutions[cfg.res].w;
	fmt.height = resolutions[cfg.res].h;
	quality = cfg.quality;
	fmt_dirty = false;
	k_mutex_unlock(&lock);

	ret = video_set_format(cam, &fmt);
	if (ret == 0) {
		ret = set_ctrl_written(VIDEO_CID_JPEG_COMPRESSION_QUALITY, quality,
				       &quality_written);
	}
	if (ret != 0) {
		LOG_ERR("format %ux%u, quality %d: %d", fmt.width, fmt.height, quality, ret);
	}
	return ret;
}

/* Every finished piece back to the driver (an ISR: k_fifo only) */
static void recycle(struct k_timer *timer)
{
	struct video_buffer *b;

	ARG_UNUSED(timer);
	while (video_dequeue(cam, &b, K_NO_WAIT) == 0) {
		(void)video_enqueue(cam, b);
	}
}

static K_TIMER_DEFINE(recycle_timer, recycle, NULL);

static void capture_on(void)
{
	if (capturing) {
		return;
	}
	if (fmt_dirty) {
		(void)apply_format();
	}
	(void)video_stream_start(cam, VIDEO_BUF_TYPE_OUTPUT);
	(void)k_work_queue_unplug(&ac_work_q);
	capturing = true;
}

/*
 * No more captures: the frame being read finishes, with the buffers handed
 * back as it fills them, and the work queue stays plugged
 */
static void capture_off(void)
{
	if (!capturing) {
		return;
	}
	(void)video_stream_stop(cam, VIDEO_BUF_TYPE_OUTPUT);
	k_timer_start(&recycle_timer, K_MSEC(5), K_MSEC(5));
	(void)k_work_queue_drain(&ac_work_q, true);
	k_timer_stop(&recycle_timer);
	recycle(NULL);
	capturing = false;
}

/* --- Clients -------------------------------------------------------------------- */

static int send_all(int fd, const void *data, size_t len)
{
	const uint8_t *p = data;

	while (len > 0) {
		ssize_t n = zsock_send(fd, p, len, 0);

		if (n < 0) {
			return -errno;
		}
		p += n;
		len -= n;
	}
	return 0;
}

static void client_close(struct cam_client *c)
{
	k_mutex_lock(&lock, K_FOREVER);
	if (c->fd >= 0) {
		zsock_close(c->fd);
		c->fd = -1;
	}
	k_mutex_unlock(&lock);
}

static void reply_text(int fd, const char *status, const char *text)
{
	char head[160];
	int n = snprintf(head, sizeof(head),
			 "HTTP/1.1 %s\r\nContent-Type: text/plain\r\nContent-Length: %u\r\n"
			 "Connection: close\r\n\r\n",
			 status, (unsigned int)strlen(text));

	(void)send_all(fd, head, n);
	(void)send_all(fd, text, strlen(text));
}

/*
 * The request line, and the headers read up to the blank line: a socket
 * closed with unread bytes resets the connection and the reply can be lost
 */
static int read_request(int fd, char *line, size_t size)
{
	char buf[128];
	size_t len = 0;
	size_t total = 0;
	uint32_t tail = 0;
	bool have_line = false;

	while (total < REQUEST_MAX) {
		ssize_t n = zsock_recv(fd, buf, sizeof(buf), 0);

		if (n <= 0) {
			return -EIO;
		}
		for (ssize_t i = 0; i < n; i++) {
			char c = buf[i];

			if (!have_line) {
				if (c == '\n') {
					have_line = true;
				} else if (c != '\r' && len < size - 1) {
					line[len++] = c;
				}
			}
			tail = tail << 8 | (uint8_t)c;
			if (tail == 0x0d0a0d0a || (tail & 0xffff) == 0x0a0a) {
				line[len] = '\0';
				return 0;
			}
		}
		total += n;
	}
	return -E2BIG;
}

/* "GET /stream.mjpg?light=on HTTP/1.1": 0 snapshot, 1 stream, <0 an error sent */
static int parse_request(int fd, char *req, int8_t *light)
{
	static const char usage[] = "GET /snapshot.jpg or /stream.mjpg [?light=on|off|auto]\n";
	char *path;
	char *q;

	*light = -1;
	if (strncmp(req, "GET ", 4) != 0) {
		reply_text(fd, "405 Method Not Allowed", usage);
		return -1;
	}
	path = req + 4;
	q = strchr(path, ' ');
	if (q != NULL) {
		*q = '\0';
	}
	q = strchr(path, '?');
	if (q != NULL) {
		*q++ = '\0';
		if (strstr(q, "light=on") != NULL) {
			*light = 1;
		} else if (strstr(q, "light=off") != NULL) {
			*light = 0;
		}
	}
	if (strcmp(path, "/snapshot.jpg") == 0) {
		return 0;
	}
	if (strcmp(path, "/stream.mjpg") == 0) {
		return 1;
	}
	reply_text(fd, "404 Not Found", usage);
	return -1;
}

static void accept_client(int lfd)
{
	static const char stream_head[] =
		"HTTP/1.1 200 OK\r\n"
		"Content-Type: multipart/x-mixed-replace; boundary=frame\r\n"
		"Cache-Control: no-store\r\nConnection: close\r\n\r\n";
	struct net_sockaddr_in addr = {0};
	net_socklen_t addr_len = sizeof(addr);
	struct zsock_timeval rcv = {.tv_usec = RECV_TIMEOUT_MS * 1000};
	struct zsock_timeval snd = {.tv_sec = SEND_TIMEOUT_MS / 1000};
	struct cam_client *slot = NULL;
	char req[128];
	int8_t light;
	uint32_t ip;
	int kind;
	int fd;

	fd = zsock_accept(lfd, (struct net_sockaddr *)&addr, &addr_len);
	if (fd < 0) {
		return;
	}
	ip = access_ip((struct net_sockaddr *)&addr);
	if (access_check(ACL_CAMERA, ip) != ACL_OK) {
		zsock_close(fd);
		return;
	}
	(void)zsock_setsockopt(fd, ZSOCK_SOL_SOCKET, ZSOCK_SO_RCVTIMEO, &rcv, sizeof(rcv));
	(void)zsock_setsockopt(fd, ZSOCK_SOL_SOCKET, ZSOCK_SO_SNDTIMEO, &snd, sizeof(snd));

	if (read_request(fd, req, sizeof(req)) != 0) {
		zsock_close(fd);
		return;
	}
	kind = parse_request(fd, req, &light);
	if (kind < 0) {
		zsock_close(fd);
		return;
	}
	if (!present) {
		reply_text(fd, "503 Service Unavailable", "no camera on this bay\n");
		zsock_close(fd);
		return;
	}

	k_mutex_lock(&lock, K_FOREVER);
	for (int i = 0; i < ARRAY_SIZE(clients); i++) {
		if (clients[i].fd < 0) {
			slot = &clients[i];
			*slot = (struct cam_client){
				.fd = fd, .stream = kind == 1, .light = light, .ip = ip,
				.port = net_ntohs(addr.sin_port), .since = k_uptime_get(),
			};
			break;
		}
	}
	k_mutex_unlock(&lock);
	if (slot == NULL) {
		reply_text(fd, "503 Service Unavailable", "camera busy: too many clients\n");
		zsock_close(fd);
		return;
	}
	if (slot->stream && send_all(fd, stream_head, sizeof(stream_head) - 1) != 0) {
		client_close(slot);
	}
}

static int nclients(void)
{
	int n = 0;

	for (int i = 0; i < ARRAY_SIZE(clients); i++) {
		n += clients[i].fd >= 0;
	}
	return n;
}

/* Lit for this frame?  Only the lease holder switches the light during a lease */
static bool want_light(void)
{
	struct acl_lease lease;
	uint32_t remaining;
	bool leased = access_lease_get(&lease, &remaining);
	bool on = false;

	k_mutex_lock(&lock, K_FOREVER);
	for (int i = 0; i < ARRAY_SIZE(clients); i++) {
		const struct cam_client *c = &clients[i];

		if (c->fd < 0 || (leased && c->ip != lease.holder)) {
			continue;
		}
		on |= c->light < 0 ? cfg.light != 0 : c->light == 1;
	}
	k_mutex_unlock(&lock);

	return on;
}

/* A frame's headers: its length when it came whole, else the boundary or close ends it */
static void send_heads(size_t total)
{
	char head[192];

	for (int i = 0; i < ARRAY_SIZE(clients); i++) {
		struct cam_client *c = &clients[i];
		int n;

		if (c->fd < 0) {
			continue;
		}
		n = snprintf(head, sizeof(head), "%sContent-Type: image/jpeg\r\n",
			     c->stream ? "--frame\r\n"
				       : "HTTP/1.1 200 OK\r\nCache-Control: no-store\r\n"
					 "Connection: close\r\n");
		if (total != 0) {
			n += snprintf(head + n, sizeof(head) - n, "Content-Length: %u\r\n",
				      (unsigned int)total);
		}
		n += snprintf(head + n, sizeof(head) - n, "\r\n");
		if (send_all(c->fd, head, n) != 0) {
			client_close(c);
		}
	}
}

static void send_piece(const uint8_t *p, size_t n, bool lead_ff)
{
	static const uint8_t ff = 0xFF;

	for (int i = 0; i < ARRAY_SIZE(clients); i++) {
		struct cam_client *c = &clients[i];

		if (c->fd < 0) {
			continue;
		}
		if ((lead_ff && send_all(c->fd, &ff, 1) != 0) || send_all(c->fd, p, n) != 0) {
			client_close(c);
		}
	}
}

/* After a frame: snapshots are done, streams get the part's end */
static void frame_sent(void)
{
	for (int i = 0; i < ARRAY_SIZE(clients); i++) {
		struct cam_client *c = &clients[i];

		if (c->fd >= 0 && (!c->stream || send_all(c->fd, "\r\n", 2) != 0)) {
			client_close(c);
		}
	}
}

/* One frame, from the sensor to every client.  *sent: the clients got part of it */
static int one_frame(bool *sent)
{
	struct hwtr_jpeg_scan scan;
	int64_t t0 = k_uptime_get();
	uint32_t ts = 0;

	*sent = false;
	hwtr_jpeg_scan_init(&scan);
	capture_on();
	for (;;) {
		struct video_buffer *b;
		size_t start;
		size_t n;
		bool done;

		if (video_dequeue(cam, &b, K_MSEC(FRAME_TIMEOUT_MS)) != 0) {
			capture_off();
			return -ETIMEDOUT;
		}
		if (*sent && b->timestamp != ts) {
			/* The next capture: this frame ended before its EOI */
			(void)video_enqueue(cam, b);
			capture_off();
			return -EBADMSG;
		}
		ts = b->timestamp;
		n = hwtr_jpeg_scan_feed(&scan, b->buffer, b->bytesused, &start);
		if (scan.state == HWTR_JPEG_ERROR || scan.state == HWTR_JPEG_SOI) {
			(void)video_enqueue(cam, b);
			capture_off();
			return -EBADMSG;
		}
		done = hwtr_jpeg_scan_done(&scan);
		if (done) {
			/* The sensor rests while the frame goes out */
			capture_off();
		}
		if (!*sent) {
			send_heads(done ? n + scan.lead_ff : 0);
			*sent = true;
		}
		send_piece(b->buffer + start, n, scan.lead_ff);
		(void)video_enqueue(cam, b);
		if (done) {
			break;
		}
	}

	k_mutex_lock(&lock, K_FOREVER);
	frames++;
	last_size = scan.size;
	last_ms = (uint32_t)(k_uptime_get() - t0);
	k_mutex_unlock(&lock);
	return 0;
}

static void frame_failed(int ret, bool sent)
{
	int64_t now = k_uptime_get();

	k_mutex_lock(&lock, K_FOREVER);
	errors++;
	k_mutex_unlock(&lock);
	LOG_WRN("frame lost (%d)", ret);

	/* Streams carry on; a snapshot fails once cut, or after a while */
	for (int i = 0; i < ARRAY_SIZE(clients); i++) {
		struct cam_client *c = &clients[i];

		if (c->fd < 0 || c->stream) {
			continue;
		}
		if (sent) {
			client_close(c);
		} else if (ret == -ETIMEDOUT || now - c->since > FRAME_TIMEOUT_MS) {
			reply_text(c->fd, "504 Gateway Timeout", "no frame from the camera\n");
			client_close(c);
		}
	}
}

static void update_fps(void)
{
	int64_t now = k_uptime_get();

	fps_frames++;
	if (now - fps_t0 >= 5000) {
		k_mutex_lock(&lock, K_FOREVER);
		fps_x10 = (uint32_t)(fps_frames * 10000 / (now - fps_t0));
		k_mutex_unlock(&lock);
		fps_frames = 0;
		fps_t0 = now;
	}
}

static int listen_on(uint16_t port)
{
	struct net_sockaddr_in addr = {
		.sin_family = NET_AF_INET,
		.sin_port = net_htons(port),
	};
	int reuse = 1;
	int fd = zsock_socket(NET_AF_INET, NET_SOCK_STREAM, NET_IPPROTO_TCP);

	if (fd < 0) {
		LOG_ERR("no socket for tcp/%u: %d", port, errno);
		return -1;
	}
	(void)zsock_setsockopt(fd, ZSOCK_SOL_SOCKET, ZSOCK_SO_REUSEADDR, &reuse, sizeof(reuse));
	if (zsock_bind(fd, (struct net_sockaddr *)&addr, sizeof(addr)) < 0 ||
	    zsock_listen(fd, 2) < 0) {
		LOG_ERR("cannot listen on tcp/%u: %d", port, errno);
		zsock_close(fd);
		return -1;
	}
	return fd;
}

/* Closed by the peer, kicked, or bytes after the request (ignored) */
static void poll_clients(struct zsock_pollfd *fds, int n)
{
	atomic_val_t kicks = atomic_clear(&kick_mask);

	for (int i = 0; i < ARRAY_SIZE(clients); i++) {
		if (clients[i].fd >= 0 && (kicks & BIT(i))) {
			LOG_INF("camera client %d kicked", i);
			client_close(&clients[i]);
		}
	}
	for (int i = 1; i < n; i++) {
		char sink[32];
		bool gone = fds[i].revents & (ZSOCK_POLLHUP | ZSOCK_POLLERR | ZSOCK_POLLNVAL);

		if (!gone && (fds[i].revents & ZSOCK_POLLIN)) {
			gone = zsock_recv(fds[i].fd, sink, sizeof(sink), ZSOCK_MSG_DONTWAIT) == 0;
		}
		for (int j = 0; gone && j < ARRAY_SIZE(clients); j++) {
			if (clients[j].fd == fds[i].fd) {
				client_close(&clients[j]);
			}
		}
	}
}

static void camera_thread(void *a, void *b, void *c)
{
	struct zsock_pollfd fds[1 + CONFIG_BAY_CAMERA_CLIENTS];
	int64_t next_frame = 0;
	int lfd;

	ARG_UNUSED(a);
	ARG_UNUSED(b);
	ARG_UNUSED(c);

	lfd = listen_on(CONFIG_BAY_CAMERA_PORT);
	if (lfd < 0) {
		return;
	}
	LOG_INF("camera on tcp/%u: /snapshot.jpg, /stream.mjpg", CONFIG_BAY_CAMERA_PORT);

	for (;;) {
		int timeout = -1;
		int n = 1;
		bool sent;
		int ret;

		/* Idle: wait for a client.  Busy: until the next frame is due */
		if (nclients() > 0) {
			timeout = (int)CLAMP(next_frame - k_uptime_get(), 0, 1000);
		}
		fds[0] = (struct zsock_pollfd){.fd = lfd, .events = ZSOCK_POLLIN};
		for (int i = 0; i < ARRAY_SIZE(clients); i++) {
			if (clients[i].fd >= 0) {
				fds[n++] = (struct zsock_pollfd){.fd = clients[i].fd,
								 .events = ZSOCK_POLLIN};
			}
		}
		if (zsock_poll(fds, n, timeout) > 0 && (fds[0].revents & ZSOCK_POLLIN)) {
			accept_client(lfd);
		}
		poll_clients(fds, n);

		if (nclients() == 0) {
			light_set(false);
			continue;
		}
		if (want_light() != lit) {
			light_set(!lit);
			if (lit) {
				/* The sensor's auto exposure catches up with the light */
				next_frame = MAX(next_frame,
						 k_uptime_get() + CONFIG_BAY_CAMERA_LIGHT_SETTLE_MS);
			}
		}
		if (k_uptime_get() < next_frame) {
			continue;
		}
		next_frame = k_uptime_get() + 1000 / CONFIG_BAY_CAMERA_FPS;

		ret = one_frame(&sent);
		if (ret != 0) {
			frame_failed(ret, sent);
			continue;
		}
		frame_sent();
		update_fps();
	}
}

K_THREAD_STACK_DEFINE(camera_stack, CONFIG_BAY_CAMERA_STACK_SIZE);
static struct k_thread camera_thread_data;

/* --- API ---------------------------------------------------------------------------- */

int camera_init(void)
{
	struct video_caps vc = {.type = VIDEO_BUF_TYPE_OUTPUT};
	uint32_t max_w = 0;

	for (int i = 0; i < ARRAY_SIZE(clients); i++) {
		clients[i].fd = -1;
	}

	if (!device_is_ready(cam)) {
		LOG_INF("no camera");
	} else {
		/* The 3 MP and 5 MP Megas differ by their largest frame */
		if (video_get_caps(cam, &vc) == 0) {
			for (const struct video_format_cap *f = vc.format_caps; f->pixelformat != 0;
			     f++) {
				max_w = MAX(max_w, f->width_max);
			}
		}
		model = max_w >= 2592 ? "Arducam Mega 5MP"
			: max_w >= 2048 ? "Arducam Mega 3MP" : "Arducam Mega";

		for (int i = 0; i < NBUF; i++) {
			struct video_buffer *b = video_buffer_aligned_alloc(
				CONFIG_BAY_CAMERA_FRAME_KB * 1024, 64, K_NO_WAIT);

			if (b == NULL) {
				LOG_ERR("no PSRAM for %d KB frame buffers", CONFIG_BAY_CAMERA_FRAME_KB);
				return -ENOMEM;
			}
			b->type = VIDEO_BUF_TYPE_OUTPUT;
			(void)video_enqueue(cam, b);
		}

		/* Plugged until a client wants a frame; below the network */
		(void)k_work_queue_drain(&ac_work_q, true);
		k_thread_priority_set(k_work_queue_thread_get(&ac_work_q),
				      K_LOWEST_APPLICATION_THREAD_PRIO);
		present = true;
		LOG_INF("%s, frames up to %d KB in PSRAM", model, CONFIG_BAY_CAMERA_FRAME_KB);
	}

	/* Without a camera too: the port says so */
	fps_t0 = k_uptime_get();
	k_thread_create(&camera_thread_data, camera_stack, K_THREAD_STACK_SIZEOF(camera_stack),
			camera_thread, NULL, NULL, NULL, PRIORITY, 0, K_NO_WAIT);
	k_thread_name_set(&camera_thread_data, "camera");

	return present ? 0 : -ENODEV;
}

bool camera_present(void)
{
	return present;
}

bool camera_active(void)
{
	bool active;

	k_mutex_lock(&lock, K_FOREVER);
	active = present && nclients() > 0;
	k_mutex_unlock(&lock);
	return active;
}

void camera_status(struct camera_status *st)
{
	k_mutex_lock(&lock, K_FOREVER);
	st->present = present;
	st->model = model;
	st->port = CONFIG_BAY_CAMERA_PORT;
	st->resolution = resolutions[cfg.res].name;
	st->quality = qualities[cfg.quality];
	st->light = cfg.light != 0;
	st->lit = lit;
	st->clients = 0;
	st->streams = 0;
	for (int i = 0; i < ARRAY_SIZE(clients); i++) {
		st->clients += clients[i].fd >= 0;
		st->streams += clients[i].fd >= 0 && clients[i].stream;
	}
	st->frames = frames;
	st->errors = errors;
	st->last_size = last_size;
	st->last_ms = last_ms;
	st->fps_x10 = st->streams ? fps_x10 : 0;
	k_mutex_unlock(&lock);
}

const char *camera_configure(const char *resolution, const char *quality, const char *light)
{
	struct cam_cfg c;
	int ret;

	k_mutex_lock(&lock, K_FOREVER);
	c = cfg;
	k_mutex_unlock(&lock);

	if (resolution != NULL) {
		int i;

		for (i = 0; i < ARRAY_SIZE(resolutions); i++) {
			if (strcmp(resolution, resolutions[i].name) == 0) {
				break;
			}
		}
		if (i == ARRAY_SIZE(resolutions)) {
			return "resolution: 320x240, 640x480, 1280x720, 1600x1200 or 1920x1080";
		}
		c.res = i;
	}
	if (quality != NULL) {
		int i;

		for (i = 0; i < ARRAY_SIZE(qualities); i++) {
			if (strcmp(quality, qualities[i]) == 0) {
				break;
			}
		}
		if (i == ARRAY_SIZE(qualities)) {
			return "quality: high, default or low";
		}
		c.quality = i;
	}
	if (light != NULL) {
		if (strcmp(light, "on") != 0 && strcmp(light, "off") != 0) {
			return "light: on or off";
		}
		c.light = strcmp(light, "on") == 0;
	}

	k_mutex_lock(&lock, K_FOREVER);
	fmt_dirty |= c.res != cfg.res || c.quality != cfg.quality;
	cfg = c;
	k_mutex_unlock(&lock);

	ret = settings_save_one("cam/cfg", &c, sizeof(c));
	if (ret != 0) {
		LOG_WRN("camera settings not saved (%d)", ret);
	}
	return NULL;
}

const char *camera_resolution_name(int i)
{
	return i >= 0 && i < ARRAY_SIZE(resolutions) ? resolutions[i].name : NULL;
}

const char *camera_quality_name(int i)
{
	return i >= 0 && i < ARRAY_SIZE(qualities) ? qualities[i] : NULL;
}

int camera_clients_get(struct camera_client_info *out, int max)
{
	int n = 0;

	k_mutex_lock(&lock, K_FOREVER);
	for (int i = 0; i < ARRAY_SIZE(clients) && n < max; i++) {
		if (clients[i].fd >= 0) {
			out[n++] = (struct camera_client_info){
				.slot = i, .stream = clients[i].stream, .ip = clients[i].ip,
				.port = clients[i].port, .since = clients[i].since,
			};
		}
	}
	k_mutex_unlock(&lock);
	return n;
}

int camera_client_kick(int slot)
{
	if (slot < 0 || slot >= ARRAY_SIZE(clients) || clients[slot].fd < 0) {
		return -ENOENT;
	}
	/* The camera thread closes it at its next turn (a frame at most) */
	atomic_or(&kick_mask, BIT(slot));
	return 0;
}
