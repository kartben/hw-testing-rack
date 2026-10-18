/* The 3D viewer's LVGL screen: LVGL's own demos rendered by its software renderer into a frame buffer that
 * the page copies into a texture (site/screen.js).  Built freestanding for wasm32 by build.sh. */
#include "lvgl.h"
#include "demos/lv_demos.h"

#define MAX_W 800
#define MAX_H 800
static uint32_t fb[MAX_W * MAX_H];
static volatile int dirty;

static void flush(lv_display_t *d, const lv_area_t *a, uint8_t *px)
{
	(void)a; (void)px;
	dirty = 1;
	lv_display_flush_ready(d);
}

__attribute__((export_name("screen_init"))) uint32_t *screen_init(int w, int h, int demo)
{
	if (w > MAX_W || h > MAX_H) return 0;
	lv_init();
	lv_display_t *disp = lv_display_create(w, h);
	lv_display_set_color_format(disp, LV_COLOR_FORMAT_XRGB8888);
	lv_display_set_buffers(disp, fb, NULL, (uint32_t)(w * h * 4), LV_DISPLAY_RENDER_MODE_DIRECT);
	lv_display_set_flush_cb(disp, flush);
	if (demo == 0) {
		lv_demo_music();
	} else {
		lv_demo_widgets();
		lv_demo_widgets_start_slideshow();
	}
	return fb;
}

/* Advance LVGL's clock and run its timers; 1 when the frame buffer changed. */
__attribute__((export_name("screen_tick"))) int screen_tick(int ms)
{
	dirty = 0;
	lv_tick_inc((uint32_t)ms);
	lv_timer_handler();
	return dirty;
}

/* What the compiler may call on its own for copies and clears (no libc here). */
void *memcpy(void *d, const void *s, size_t n) { unsigned char *a = d; const unsigned char *b = s; while (n--) *a++ = *b++; return d; }
void *memmove(void *d, const void *s, size_t n) {
	unsigned char *a = d; const unsigned char *b = s;
	if (a < b) while (n--) *a++ = *b++; else { a += n; b += n; while (n--) *--a = *--b; }
	return d;
}
void *memset(void *d, int c, size_t n) { unsigned char *a = d; while (n--) *a++ = (unsigned char)c; return d; }
int memcmp(const void *x, const void *y, size_t n) {
	const unsigned char *a = x, *b = y;
	for (; n; n--, a++, b++) if (*a != *b) return *a - *b;
	return 0;
}
