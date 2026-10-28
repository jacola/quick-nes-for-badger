# QuickNES source provenance and local changes

Source: https://github.com/libretro/QuickNES_Core
Revision: `26bb785c9deddb66a17717b21bb4e328f03ade32`

The upstream `nes_emu/` sources and root `LICENSE` are included. The unused
precompiled Linux utility `nes_emu/tools/proto` is deliberately omitted;
its corresponding `proto_fixedpoint_sinc.cpp` source is retained. It is not
linked into the badge module.
Per-file notices have not been removed. The root license is GPL v2; legacy
Nes_Emu and related component headers specify LGPL v2.1 or later. A copy of
that component license is included as `COPYING.LESSER`.

Local source edits:

1. `Nes_Mapper.cpp`: `BADGE_NES_BUILD` selects NROM/MMC1/UNROM/CNROM/MMC3,
   suppresses the unsupported-mapper stderr diagnostic, and gives the zero-size
   mapper-state sentinel external linkage for ARM PIC. `default_reset_state`
   first unmaps $6000-$7fff; RAM-capable mappers then explicitly re-enable it.
   This fixes NROM/CNROM gaining writable RAM merely by loading a snapshot;
   Tengen Tetris exposed the resulting replay divergence. Snapshot bytes and
   the state ABI are unchanged.
2. `Nes_Core.h`: adds a read-only error-counter accessor under
   `BADGE_NES_BUILD`.

The build uses upstream's existing `NO_UNALIGNED_ACCESS` option and ARM
`-mno-unaligned-access`. This corrects the machine access strategy, not NES
behavior. The separate `engine.cpp` uses the public core APIs and original
state format. It preserves the eight-sprite limit, complete image, CPU/APU/PPU
execution and game cartridge bytes. No Zelda-specific instruction or asset is
patched.

`palette.h` is generated from the original 512-entry `Nes_Emu::nes_colors`
table, converted to RGB565. Audio sample synthesis is disconnected because the
badge has no onboard audio output; APU execution and snapshots remain active.

All new build/integration/test sources are supplied alongside the binary;
see `tools/nes/README.md`. The ROM is intentionally excluded.
