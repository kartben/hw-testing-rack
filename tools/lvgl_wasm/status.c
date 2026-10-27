/* The bay node's front display (firmware/bay-node/src/display.c) for the viewer: the same labels, fonts,
 * places and colours, its values from the page (site/bay_screen.js) instead of the node.  The page writes one
 * line per label into status_buf(), each its colour's letter and its text, and status_apply() draws them. */
#include "lvgl.h"

#define NPORTS 4
#define NLINES (4 + NPORTS + 1)

static lv_obj_t *labels[NLINES];      /* id, address, DUT, fault, the ports, USB */
static char buf[1024];

static lv_obj_t *label_add(const lv_font_t *font, lv_align_t align, int32_t x, int32_t y)
{
	lv_obj_t *label = lv_label_create(lv_screen_active());

	lv_obj_set_style_text_font(label, font, 0);
	lv_obj_align(label, align, x, y);
	lv_label_set_text(label, "");

	return label;
}

void status_create(void)
{
	lv_obj_t *screen = lv_screen_active();

	lv_obj_set_style_bg_color(screen, lv_color_black(), 0);
	lv_obj_set_style_text_color(screen, lv_color_white(), 0);

	labels[0] = label_add(&lv_font_montserrat_28, LV_ALIGN_TOP_LEFT, 10, 8);
	labels[1] = label_add(&lv_font_montserrat_14, LV_ALIGN_TOP_RIGHT, -10, 16);
	labels[2] = label_add(&lv_font_montserrat_28, LV_ALIGN_LEFT_MID, 10, -6);
	labels[3] = label_add(&lv_font_montserrat_14, LV_ALIGN_RIGHT_MID, -10, -6);
	for (int i = 0; i < NPORTS; i++) {
		labels[4 + i] = label_add(&lv_font_montserrat_14, LV_ALIGN_BOTTOM_LEFT, 10 + i * 77, -34);
	}
	labels[4 + NPORTS] = label_add(&lv_font_montserrat_14, LV_ALIGN_BOTTOM_LEFT, 10, -10);
}

static lv_color_t color(char c)
{
	switch (c) {
	case 'g': return lv_palette_main(LV_PALETTE_GREEN);
	case 'G': return lv_palette_main(LV_PALETTE_GREY);
	case 'o': return lv_palette_main(LV_PALETTE_ORANGE);
	case 'r': return lv_palette_main(LV_PALETTE_RED);
	default: return lv_color_white();
	}
}

__attribute__((export_name("status_buf"))) char *status_buf(void)
{
	return buf;
}

/* The lines in status_buf() onto the labels, and the whole screen redrawn into the frame buffer */
__attribute__((export_name("status_apply"))) void status_apply(void)
{
	char *p = buf;

	for (int i = 0; i < NLINES && *p; i++) {
		char *end = p;

		while (*end && *end != '\n') end++;
		char c = *p, keep = *end;

		*end = '\0';
		lv_label_set_text(labels[i], p + 1);
		lv_obj_set_style_text_color(labels[i], color(c), 0);
		*end = keep;
		p = keep ? end + 1 : end;
	}
	lv_obj_invalidate(lv_screen_active());
	lv_refr_now(NULL);
}
