/*
 * The RP2350 bootloader on the virtual bus (picoboot_emu.c), for the tests
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOBOOT_EMU_H_
#define PICOBOOT_EMU_H_

#include <stdbool.h>
#include <stdint.h>

#include <zephyr/kernel.h>

struct picoboot_emu {
	uint8_t sram[0x82000];   /* the RP2350's 520 KB at 0x20000000 */
	uint32_t cmds;
	uint32_t bad;            /* malformed or out-of-order commands */
	uint32_t written;
	uint8_t exclusive;
	uint32_t reboots;
	uint32_t reboot_flags;
	uint32_t reboot_delay;
	uint32_t reboot_p0;
	uint32_t reboot_p1;
	bool stall_write;        /* halt the OUT endpoint at a WRITE */
	bool mute;               /* never acknowledge */
};

extern struct picoboot_emu emu;
/* Given when it left the bus after a REBOOT2 */
extern struct k_sem picoboot_emu_left;

int picoboot_emu_init(void);
void picoboot_emu_reset(void);
int picoboot_emu_plug(void);
int picoboot_emu_unplug(void);

#endif /* PICOBOOT_EMU_H_ */
