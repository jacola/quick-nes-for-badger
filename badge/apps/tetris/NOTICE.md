# Third-party notices

This app is part of [QuickNES for Badger](https://github.com/jacola/quick-nes-for-badger).
The complete project includes the corresponding native source and build scripts.

## QuickNES / Nes_Emu

The native core comes from https://github.com/libretro/QuickNES_Core at revision
`26bb785c9deddb66a17717b21bb4e328f03ade32`. Nes_Emu was originally written by
Shay Green (blargg). The upstream GPL v2 text is retained as `COPYING`; legacy
component LGPL v2.1-or-later notices and text are retained as `COPYING.LESSER`.
Per-file notices remain in `tools/nes/vendor/quicknes/` in the complete project.
Local changes are documented there in `PORT.md`.

## MicroPython and compiler runtime

The native ABI glue uses MicroPython's MIT-licensed dynamic-runtime headers.
Copyright (c) 2019 Damien P. George and other MicroPython contributors.
See `COPYING.MICROPYTHON`. GCC arithmetic runtime support is covered by its
Runtime Library Exception; corresponding texts are in the project's `LICENSES/`.

## Badge integration and redistribution

The frontend, checkpoint/input handling, bridge, build/install tools, and original
launcher icons are available under the project's badge-integration MIT license.
Copyright (c) Pimoroni & GitHub; Copyright (c) 2026 Jacques Lalancette (jacola).
The combined emulator distribution is offered under GPL v2, retaining the
individual component notices. See the complete project's `THIRD_PARTY.md` and
`LICENSES/`. Do not redistribute only this app's native binary without the
applicable notices and corresponding source obligations.

## Games

No ROM is included or downloaded. A locally supplied ROM is not covered by the
emulator licenses. Game names identify supported cartridges and belong to their
respective owners. This project is not affiliated with or endorsed by Nintendo,
any game publisher, Pimoroni, GitHub, or the libretro project.
