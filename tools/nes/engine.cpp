// SPDX-License-Identifier: MIT
// Runs QuickNES's CPU/PPU/APU and mapper unchanged; no game logic is recreated.
#include "bridge.h"
#include "Nes_Core.h"
#include "Nes_Cart.h"
#include "Nes_State.h"
#include "Nes_Mapper.h"
#include "palette.h"
#include <new>
#include <cstring>

struct Engine {
    Nes_Core core;
    Nes_Cart cart;
    Nes_State snapshot;
    short palette[256];
    // QuickNES requires a one-line and eight-pixel guard around the picture.
    alignas(4) uint8_t pixels[Nes_Ppu::buffer_width * (Nes_Ppu::buffer_height + 2)];
};

// Native .mpy data must be externally linked so ARM PIC accesses use the GOT.
Engine *engine;
uint8_t *arena_begin;
size_t arena_capacity, arena_position;

static void *arena_alloc(size_t size) {
    if (size > arena_capacity || arena_position > arena_capacity - size ||
        size > SIZE_MAX - 31) return nullptr;
    size_t amount = (size + 31) & ~(size_t)15;
    if (amount > arena_capacity - arena_position) return nullptr;
    uint8_t *block = arena_begin + arena_position;
    arena_position += amount;
    *(size_t *)block = size;
    void *result = block + 16;
    memset(result, 0, amount - 16);
    return result;
}

#ifdef NES_NATIVE
// All emulator allocations are inside one Python-owned, GC-rooted arena.
// No malloc ABI or firmware addresses are hard-coded, and no allocation is
// performed per frame. Free is a no-op until close/reload resets the arena.
extern "C" void *malloc(size_t size) { return arena_alloc(size); }
extern "C" void free(void *) {}
extern "C" void *realloc(void *old, size_t size) {
    if (!size) return nullptr;
    void *next = arena_alloc(size);
    if (next && old) {
        size_t old_size = *(size_t *)((uint8_t *)old - 16);
        memcpy(next, old, size < old_size ? size : old_size);
    }
    return next;
}
extern "C" void *calloc(size_t n, size_t size) {
    if (size && n > SIZE_MAX / size) return nullptr;
    return arena_alloc(n * size);
}
void *operator new(size_t size) { return arena_alloc(size); }
void *operator new[](size_t size) { return arena_alloc(size); }
void operator delete(void *) noexcept {}
void operator delete[](void *) noexcept {}
void operator delete(void *, size_t) noexcept {}
void operator delete[](void *, size_t) noexcept {}
extern "C" void __cxa_pure_virtual() { __builtin_trap(); }
#endif

extern "C" void bnes_close(void) {
    if (engine) engine->~Engine();
    engine = nullptr;
    arena_begin = nullptr;
    arena_capacity = arena_position = 0;
}

extern "C" const char *bnes_open(const uint8_t *rom, size_t length,
                                 void *arena, size_t arena_size) {
    // Reject malformed/unsupported cartridges BEFORE changing the running VM.
    if (length < 16 || memcmp(rom, "NES\x1a", 4)) return "Not an iNES ROM";
    unsigned mapper = (rom[6] >> 4) | (rom[7] & 0xf0);
    if (rom[7] & 0x0f) return "Only standard NTSC iNES cartridges are supported";
    if (mapper > 4) return "Supported mappers: NROM, MMC1, UNROM, CNROM, MMC3";
    if ((rom[6] & 0x0c) || rom[9]) return "Trainer, four-screen and PAL ROMs are unsupported";
    if (!rom[4] || rom[4] > 16 || rom[5] > 16 ||
        (mapper == 0 && (rom[4] > 2 || rom[5] > 1)) ||
        (mapper == 2 && rom[5] != 0) ||
        (mapper == 3 && (rom[4] > 2 || rom[5] == 0)) ||
        (mapper == 4 && rom[4] < 2))
        return "Invalid cartridge bank count";
    size_t expected = 16 + (size_t)rom[4] * 16384 + (size_t)rom[5] * 8192;
    if (length != expected) return "Incorrect ROM length";
    if (!arena || ((uintptr_t)arena & 15) || arena_size < BNES_ARENA_SIZE)
        return "Emulator needs an aligned 1 MiB arena";

    bnes_close();
    arena_begin = (uint8_t *)arena;
    arena_capacity = arena_size;
    void *storage = arena_alloc(sizeof(Engine));
    if (!storage) return "Insufficient emulator memory";
    engine = new (storage) Engine();
    Mem_File_Reader reader(rom, length);
    const char *error = engine->cart.load_ines(reader);
    if (!error) error = engine->core.open(&engine->cart);
    if (error) {
        bnes_close();
        return error;
    }
    engine->core.ppu.host_row_bytes = Nes_Ppu::buffer_width;
    engine->core.ppu.palette_begin = 0;
    engine->core.ppu.sprite_limit = 8; // Preserve original NES sprite flicker.
    engine->core.ppu.host_palette = engine->palette;
    engine->core.ppu.max_palette_size = 256;
    // APU still executes (including DMC reads/interrupts), but the badge has
    // no onboard audio output. Null outputs skip sample synthesis only.
    engine->palette[252] = 0x0f;
    engine->palette[254] = 0x30;
    engine->palette[255] = 0x0f;
    return nullptr;
}

extern "C" const char *bnes_advance(unsigned pad1, unsigned pad2) {
    if (!engine) return "No cartridge loaded";
    Nes_Core &core = engine->core;
    core.current_joypad[0] = pad1 | ~0xffu;
    core.current_joypad[1] = pad2 | ~0xffu;
    core.ppu.host_pixels = engine->pixels + Nes_Ppu::buffer_width;
    core.emulate_frame();
    return nullptr;
}

extern "C" const char *bnes_present(uint16_t *screen) {
    if (!engine) return "No cartridge loaded";
    if (!screen || ((uintptr_t)screen & 3)) return "Unaligned framebuffer";
    Nes_Core &core = engine->core;
    if (!core.ppu.host_pixels) return "No frame has been rendered";
    // Keep the lookup table on the fast native stack, not in external PSRAM.
    // Four source pixels per aligned word and two destination pixels per word
    // substantially reduce QSPI bus transactions, without changing any pixel.
    uint16_t rgb[256];
    for (unsigned i = 0; i < 256; ++i)
        rgb[i] = NES_RGB565[(unsigned)engine->palette[i] & 511];
    const uint8_t *src = core.ppu.host_pixels + Nes_Ppu::image_left;
    // Complete 256x240 output, centered on 320x240. No overscan cropping,
    // rescaling, tile redrawing, unlimited sprites, or gameplay patches.
    for (unsigned y = 0; y < 240; ++y) {
        uint32_t *dst = (uint32_t *)(screen + y * 320 + 32);
        const uint32_t *packed = (const uint32_t *)src;
        for (unsigned x = 0; x < 64; ++x) {
            uint32_t p = packed[x];
            dst[x * 2] = (uint32_t)rgb[p & 255] | ((uint32_t)rgb[(p >> 8) & 255] << 16);
            dst[x * 2 + 1] = (uint32_t)rgb[(p >> 16) & 255] | ((uint32_t)rgb[p >> 24] << 16);
        }
        src += Nes_Ppu::buffer_width;
    }
    return nullptr;
}

extern "C" const char *bnes_step(uint16_t *screen, unsigned pad1, unsigned pad2) {
    // Preserve the original combined API for old frontends and test tools.
    if (!screen || ((uintptr_t)screen & 3)) return "Unaligned framebuffer";
    const char *error = bnes_advance(pad1, pad2);
    return error ? error : bnes_present(screen);
}

extern "C" const char *bnes_save(uint8_t *out, size_t capacity, size_t *written) {
    if (!engine) return "No cartridge loaded";
    if (capacity < BNES_STATE_SIZE) return "State buffer must be at least 32 KiB";
    engine->core.save_state(&engine->snapshot);
    Mem_Writer writer(out, capacity);
    const char *error = engine->snapshot.write(writer);
    *written = error ? 0 : writer.size();
    return error;
}

// Accept only the complete, flat snapshot layout produced by this build.
// Validate before asking the legacy reader to interpret lengths or mutate state.
static bool state_block(const uint8_t *&p, const uint8_t *end,
                        const char *tag, unsigned size) {
    if ((size_t)(end - p) < 8u + size || memcmp(p, tag, 4)) return false;
    unsigned stored = p[4] | (unsigned)p[5] << 8 |
                      (unsigned)p[6] << 16 | (unsigned)p[7] << 24;
    if (stored != size) return false;
    p += 8 + size;
    return true;
}

static unsigned mapper_state_size(unsigned mapper) {
    switch (mapper) {
        case 0: return 0;
        case 1: return sizeof(mmc1_state_t);
        case 2: case 3: return 1;
        case 4: return sizeof(mmc3_state_t);
        default: return 0;
    }
}

extern "C" const char *bnes_load(const uint8_t *data, size_t length) {
    if (!engine) return "No cartridge loaded";
    if (length < 16 || length > BNES_STATE_SIZE) return "Invalid state length";
    const uint8_t *p = data + 8, *end = data + length;
    if (memcmp(data, "NESS\xff\xff\xff\xff", 8) ||
        !state_block(p, end, "TIME", 8) ||
        !state_block(p, end, "CPUR", 8) ||
        !state_block(p, end, "PPUR", sizeof(ppu_state_t)) ||
        !state_block(p, end, "APUR", sizeof(apu_state_t)) ||
        !state_block(p, end, "CTRL", sizeof(joypad_state_t)) ||
        !state_block(p, end, "MAPR", mapper_state_size(engine->cart.mapper_code())) ||
        !state_block(p, end, "LRAM", 2048) ||
        !state_block(p, end, "SPRT", 256) ||
        !state_block(p, end, "NTAB", 2048) ||
        (!engine->cart.chr_size() && !state_block(p, end, "CHRR", 8192)) ||
        !state_block(p, end, "SRAM", 8192) ||
        !state_block(p, end, "gend", 0) || p != end)
        return "Malformed or incompatible machine state";
    Nes_State_ &state = reinterpret_cast<Nes_State_ &>(engine->snapshot);
    state.clear();
    Mem_File_Reader reader(data, length);
    const char *error = engine->snapshot.read(reader);
    if (error) return error;
    if (!state.nes_valid || !state.cpu_valid || !state.ppu_valid ||
        !state.apu_valid || !state.joypad_valid || !state.mapper_valid ||
        !state.ram_valid || !state.spr_ram_valid ||
        state.nametable_size != 0x800 ||
        state.chr_size != (engine->cart.chr_size() ? 0 : 0x2000) ||
        state.sram_size != 0x2000 ||
        state.mapper->size < 0 || state.mapper->size > 256)
        return "Incomplete or incompatible machine state";
    if (engine->cart.mapper_code() == 1) {
        if (state.mapper->size != sizeof(mmc1_state_t))
            return "Invalid MMC1 state";
        const mmc1_state_t *mmc1 = (const mmc1_state_t *)state.mapper->data;
        if (mmc1->bit > 4) return "Invalid MMC1 shift register";
    }
    engine->core.load_state(state);
    return nullptr;
}

extern "C" unsigned bnes_frame_count(void) {
    return engine ? engine->core.nes.frame_count : 0;
}
extern "C" unsigned bnes_errors(void) {
    return engine ? engine->core.badge_error_count() : 0;
}
extern "C" size_t bnes_arena_used(void) { return arena_position; }
