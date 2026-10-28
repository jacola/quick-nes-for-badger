// SPDX-License-Identifier: MIT
// Optional host ASan/UBSan integration harness. Supply your own ROM path.
#include "bridge.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

static void check(const char *error) {
    if (error) { std::fprintf(stderr, "%s\n", error); std::exit(1); }
}
int main(int argc, char **argv) {
    if (argc != 2) return 2;
    FILE *f = std::fopen(argv[1], "rb");
    if (!f) return 2;
    std::fseek(f, 0, SEEK_END);
    size_t n = std::ftell(f);
    std::rewind(f);
    std::vector<uint8_t> rom(n), arena(BNES_ARENA_SIZE);
    if (std::fread(rom.data(), 1, n, f) != n) return 2;
    std::fclose(f);
    std::vector<uint16_t> fb(320*240), expected(320*240);
    std::vector<uint8_t> state(BNES_STATE_SIZE), after(BNES_STATE_SIZE), replay(BNES_STATE_SIZE);
    check(bnes_open(rom.data(), n, arena.data(), arena.size()));
    for (unsigned i=0; i<600; ++i) check(bnes_step(fb.data(), 0, 0));
    size_t before_n=0, after_n=0, replay_n=0;
    check(bnes_save(state.data(), state.size(), &before_n));
    for (unsigned i=0; i<400; ++i) check(bnes_step(fb.data(), i<2 ? 8 : 0, 0));
    expected = fb;
    check(bnes_save(after.data(), after.size(), &after_n));
    check(bnes_load(state.data(), before_n));
    for (unsigned i=0; i<400; ++i) check(bnes_step(fb.data(), i<2 ? 8 : 0, 0));
    check(bnes_save(replay.data(), replay.size(), &replay_n));
    if (expected != fb || after_n != replay_n || std::memcmp(after.data(),replay.data(),after_n))
        return 3;
    std::printf("Native engine: %u frames, %u CPU errors, deterministic snapshot replay.\n",
                bnes_frame_count(), bnes_errors());
    bnes_close();
    return 0;
}
