# Licensing and source provenance

## Distribution

The complete emulator distribution is offered under GNU GPL version 2
([LICENSE](LICENSE)). This does not erase the more permissive or component-specific
licenses below. Preserve original per-file copyright/license notices.

The repository contains no game ROMs, save files, or firmware images. Users must
supply ROMs they are entitled to use. Game names are compatibility identifiers,
not an endorsement or grant of game-content rights.

## QuickNES / Nes_Emu

- Upstream: https://github.com/libretro/QuickNES_Core
- Revision: `26bb785c9deddb66a17717b21bb4e328f03ade32`
- Original Nes_Emu author: Shay Green (blargg).
- Upstream root license: GPL version 2.
- Legacy Nes_Emu / Blip_Buffer / related headers retain LGPL version 2.1-or-later
  notices. Their license text is included in `LICENSES/LGPL-2.1.txt` and the vendor tree.
- Vendored source: `tools/nes/vendor/quicknes/`.
- Local modifications: [vendor PORT.md](tools/nes/vendor/quicknes/PORT.md).

All relevant upstream source files and their notices are retained. The unused
precompiled Linux `nes_emu/tools/proto` utility is omitted; its C++ source remains.
It is not linked into the badge module. The palette is generated from QuickNES's
original color table, not from a game's graphics.

## Badge integration

The original frontend, checkpoint store, input handling, C/C++ bridge, host/ARM
adapters, build/install tools, publication tooling, and original launcher artwork
are available under [the MIT license](LICENSES/Badge-integration-MIT.txt).
The original Pimoroni/GitHub badge-project notice is retained alongside the
jacola integration notice. Vendored code and the generated upstream palette are
not relicensed as MIT by this statement.

## MicroPython

- Upstream: https://github.com/micropython/micropython
- Pinned build revision: `29d45e488c0c194014db7dc63dd974d11f393ef2`
- Native dynamic-runtime headers / linker tooling: MIT.
- Notice: [MicroPython-MIT.txt](LICENSES/MicroPython-MIT.txt).

The complete MicroPython firmware is not bundled or installed. The build obtains
its headers/tools from a user-provided checkout at the pinned revision.

## GCC runtime

The native link uses arithmetic support from `libgcc` supplied by GNU Arm GCC.
The compiler used for the supplied build is recorded in `_nes_core.build.json`.
GCC runtime files carry GPL v3 with the GCC Runtime Library Exception; the exception
permits qualifying compiled target-code combinations under their chosen terms.
The [GPL v3 text](LICENSES/GPL-3.0.txt) and
[Runtime Library Exception](LICENSES/GCC-Runtime-Exception.txt) are included.
The compiler/toolchain itself is not redistributed here.

## Redistribution

Use the complete ROM-free project source package when redistributing this port.
It includes the native core's corresponding source, local modifications, palette,
build/install scripts, pinned revisions, and license texts. Do not present an
isolated app folder or `_nes_core.mpy` as the complete corresponding source.
Retain applicable source availability and notice obligations when making your
own binary distribution. Do not add a commercial ROM to a release or commit.
