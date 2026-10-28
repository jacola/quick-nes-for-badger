// SPDX-License-Identifier: MIT
#ifndef BADGE_NES_BRIDGE_H
#define BADGE_NES_BRIDGE_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define BNES_ARENA_SIZE (1024 * 1024)
#define BNES_STATE_SIZE (32 * 1024)
#define BNES_SCREEN_BYTES (320 * 240 * 2)
const char *bnes_open(const uint8_t *rom, size_t length, void *arena, size_t arena_size);
void bnes_close(void);
const char *bnes_step(uint16_t *screen, unsigned pad1, unsigned pad2);
const char *bnes_advance(unsigned pad1, unsigned pad2);
const char *bnes_present(uint16_t *screen);
const char *bnes_save(uint8_t *out, size_t capacity, size_t *written);
const char *bnes_load(const uint8_t *state, size_t length);
unsigned bnes_frame_count(void);
unsigned bnes_errors(void);
size_t bnes_arena_used(void);
#ifdef __cplusplus
}
#endif
#endif
