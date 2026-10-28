# How the badge port works

```text
User-supplied ROM
       │ exact identity/header checks
       ▼
MicroPython app ── input chords / frame pacing / checkpoint files
       │ native API
       ▼
_nes_core.mpy ── engine.cpp ── vendored QuickNES CPU/PPU/APU/mappers
       │                         │
       │ private emulated frame  └── bounded 1 MiB arena
       ▼
RGB565 present() ── fenced badge framebuffer ── asynchronous LCD transfer
```

QuickNES runs the original cartridge program; the Python frontend is not a remake
of the game. The badge integration adds a bounded allocator, native ABI bindings,
framebuffer conversion, controls, persistence, packaging, and safe installation.

## Native boundary

`engine.cpp` and `bridge.h` expose one VM through C-callable operations. `module.c`
wraps them as a MicroPython native dynamic module. `support.c` supplies missing
libc operations without importing a desktop C++ runtime. The linked mapper set is
intentionally limited to 0–4. Exceptions, RTTI, and static constructors are disabled.

BSS and the arena have explicit Python-owned GC roots. The entry trampoline is kept
in the expected ordinary `.text` section and the build checks BSS/GOT layout.
Cortex-M33 unaligned-access restrictions are handled with both the upstream
`NO_UNALIGNED_ACCESS` option and `-mno-unaligned-access`.

**Do not casually remove these flags/roots/link checks.** A passing desktop build
alone cannot validate native relocation, ABI compatibility, or GC lifetime.
The frontend arms a watchdog before importing the native module, but that is not
a substitute for matching firmware and testing the actual target.

## Display pipeline

`advance()` emulates a full frame into private memory while the previous LCD
transfer may still be running. `display.set_async(False)` drains that transfer
before `present()` copies into `screen.raw`; the next transfer is then enabled.
The same fence is used before save I/O and teardown. No shared framebuffer is
modified while the display is reading it. The original combined `step()` API is
retained for synchronous fallback/testing.

No game ticks are deliberately discarded to catch up. A long pause bounds the
next deadline rather than skipping CPU/PPU frames or changing game rules.

## Runtime templates and identity

`badge/apps/zelda/` is the canonical tested runtime template. `games.py` specifies
cartridge size/hash, app slug, unique helper-module prefix, and checkpoint magic.
`package_apps.py` derives other independent apps. Keep shared fixes in the canonical
frontend and regenerate; do not hand-fork the generated helper modules.

Each app has its own ROM identity and `/state/<slug>` checkpoint directory, even
when two versions of the same game are installed. `on_exit()` notifications do
not save or destroy a still-running VM. Teardown happens after `run(update)` returns;
late/repeated callbacks are guarded.

## Tests

Host ctypes tests execute the same C++ core. Unicorn tests relocate and execute
the actual `.mpy` ARM code and compare frames/state. Tiny original test programs
are generated at test time; no game ROM is bundled. Optional local-ROM integration
checks exercise real cartridge paths. Hardware probes test the actual badge APIs,
GC, persistence, and launcher lifecycle in scratch locations, not player saves.

The public repository deliberately excludes development dumps, screenshots,
checkpoints, device identities, local filesystem paths, and recovery-worker logs.
