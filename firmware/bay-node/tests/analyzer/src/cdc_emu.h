/*
 * gusmanb's analyzer on the virtual bus (cdc_emu.c), for the tests
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef CDC_EMU_H_
#define CDC_EMU_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

struct cdc_emu {
	uint8_t got[1024];   /* what the host wrote */
	size_t got_len;
	uint16_t line_state; /* the last SET_CONTROL_LINE_STATE: DTR bit 0, RTS bit 1 */
	uint32_t line_sets;
	bool answer_id;      /* answer the ID request with cdc_emu_id */
};

extern struct cdc_emu cdc;
extern const char cdc_emu_id[];

int cdc_emu_init(void);
void cdc_emu_reset(void);
int cdc_emu_plug(void);
int cdc_emu_unplug(void);
/* Sends data to the host as it reads it (data must stay valid); -EBUSY while sending */
int cdc_emu_send(const uint8_t *data, size_t len);
/* Everything given to cdc_emu_send() went to the host */
bool cdc_emu_sent(void);

#endif /* CDC_EMU_H_ */
