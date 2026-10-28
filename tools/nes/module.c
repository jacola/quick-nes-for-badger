// SPDX-License-Identifier: MIT
#include "py/dynruntime.h"
#include "bridge.h"

// Keep the entire native BSS allocation visible to the GC, even on firmware
// builds whose executable allocator does not trace pointers from machine code.
// This is the first BSS section (module.o is linked first). The list owns a
// by-reference view of this block and, after load(), the emulator arena.
struct { mp_obj_t holder; } bnes_native_roots;

static void check(const char *error) {
    if (error) mp_raise_msg(&mp_type_RuntimeError, error);
}
static mp_obj_t load(mp_obj_t rom_obj, mp_obj_t arena_obj) {
    mp_buffer_info_t rom, arena;
    mp_get_buffer_raise(rom_obj, &rom, MP_BUFFER_READ);
    mp_get_buffer_raise(arena_obj, &arena, MP_BUFFER_WRITE);
    check(bnes_open(rom.buf, rom.len, arena.buf, arena.len));
    // Native globals are not used as the sole owners of heap storage.
    mp_obj_subscr(bnes_native_roots.holder, MP_OBJ_NEW_SMALL_INT(1), arena_obj);
    return mp_obj_new_int(bnes_arena_used());
}
static MP_DEFINE_CONST_FUN_OBJ_2(load_obj, load);

static mp_obj_t step(mp_obj_t target, mp_obj_t p1, mp_obj_t p2) {
    mp_buffer_info_t fb;
    mp_get_buffer_raise(target, &fb, MP_BUFFER_WRITE);
    if (fb.len != BNES_SCREEN_BYTES)
        mp_raise_ValueError(MP_ERROR_TEXT("Expected 320x240 RGB565 framebuffer"));
    check(bnes_step(fb.buf, mp_obj_get_int(p1), mp_obj_get_int(p2)));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_3(step_obj, step);

static mp_obj_t advance(mp_obj_t p1, mp_obj_t p2) {
    check(bnes_advance(mp_obj_get_int(p1), mp_obj_get_int(p2)));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_2(advance_obj, advance);

static mp_obj_t present(mp_obj_t target) {
    mp_buffer_info_t fb;
    mp_get_buffer_raise(target, &fb, MP_BUFFER_WRITE);
    if (fb.len != BNES_SCREEN_BYTES)
        mp_raise_ValueError(MP_ERROR_TEXT("Expected 320x240 RGB565 framebuffer"));
    check(bnes_present(fb.buf));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(present_obj, present);

static mp_obj_t save(mp_obj_t target) {
    mp_buffer_info_t state;
    mp_get_buffer_raise(target, &state, MP_BUFFER_WRITE);
    size_t written = 0;
    check(bnes_save(state.buf, state.len, &written));
    return mp_obj_new_int(written);
}
static MP_DEFINE_CONST_FUN_OBJ_1(save_obj, save);

static mp_obj_t restore(mp_obj_t source) {
    mp_buffer_info_t state;
    mp_get_buffer_raise(source, &state, MP_BUFFER_READ);
    check(bnes_load(state.buf, state.len));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(restore_obj, restore);

static mp_obj_t stats(void) {
    mp_obj_t values[3] = {mp_obj_new_int(bnes_frame_count()),
        mp_obj_new_int(bnes_errors()), mp_obj_new_int(bnes_arena_used())};
    return mp_obj_new_tuple(3, values);
}
static MP_DEFINE_CONST_FUN_OBJ_0(stats_obj, stats);

static mp_obj_t close_core(void) {
    bnes_close();
    mp_obj_subscr(bnes_native_roots.holder, MP_OBJ_NEW_SMALL_INT(1), mp_const_none);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(close_obj, close_core);

mp_obj_t mpy_init(mp_obj_fun_bc_t *self, size_t n_args, size_t n_kw, mp_obj_t *args) {
    MP_DYNRUNTIME_INIT_ENTRY
    mp_obj_t roots[2] = {
        mp_obj_new_bytearray_by_ref(sizeof(bnes_native_roots), &bnes_native_roots),
        mp_const_none
    };
    bnes_native_roots.holder = mp_obj_new_list(2, roots);
    mp_store_global(MP_QSTR__roots, bnes_native_roots.holder);
    mp_store_global(MP_QSTR_load, MP_OBJ_FROM_PTR(&load_obj));
    mp_store_global(MP_QSTR_step, MP_OBJ_FROM_PTR(&step_obj));
    mp_store_global(MP_QSTR_advance, MP_OBJ_FROM_PTR(&advance_obj));
    mp_store_global(MP_QSTR_present, MP_OBJ_FROM_PTR(&present_obj));
    mp_store_global(MP_QSTR_save, MP_OBJ_FROM_PTR(&save_obj));
    mp_store_global(MP_QSTR_restore, MP_OBJ_FROM_PTR(&restore_obj));
    mp_store_global(MP_QSTR_stats, MP_OBJ_FROM_PTR(&stats_obj));
    mp_store_global(MP_QSTR_close, MP_OBJ_FROM_PTR(&close_obj));
    mp_store_global(MP_QSTR_ARENA_SIZE, mp_obj_new_int(BNES_ARENA_SIZE));
    mp_store_global(MP_QSTR_STATE_SIZE, mp_obj_new_int(BNES_STATE_SIZE));
    mp_store_global(MP_QSTR_ABI, mp_obj_new_int(1));
    MP_DYNRUNTIME_INIT_EXIT
}
