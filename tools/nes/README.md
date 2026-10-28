# Emulator source and developer tools

See the [project quick start](../../README.md) to install a prebuilt, ROM-free app
profile with your own ROM. This directory contains the complete native source
and the tools used to build, test, and package it.

- [Build instructions](../../docs/building.md)
- [Architecture and native safety invariants](../../docs/architecture.md)
- [Compatibility and validation](../../docs/compatibility.md)
- [Checkpoint behavior](../../docs/saves.md)
- [Contributing / adding profiles](../../CONTRIBUTING.md)
- [Source provenance and licenses](../../THIRD_PARTY.md)

## Layout

| File | Purpose |
| --- | --- |
| `engine.cpp`, `bridge.h` | Bounded, single-VM QuickNES integration |
| `module.c` | MicroPython native API and explicit BSS/arena GC ownership |
| `support.c` | C library operations absent from the dynamic ABI |
| `vendor/quicknes/` | Upstream source, local changes, and license notices |
| `palette.h` | Generated 512-entry NTSC RGB565 palette |
| `build.py` | Host/native builds, link checks, source/binary manifests |
| `host.py` | ctypes adapter for the same C++ core |
| `games.py` | Tested cartridge hashes and isolated app/save identities |
| `package_apps.py` | Generate other app runtimes from the canonical Zelda frontend |
| `generate_library_assets.py` | Original icons and per-profile documentation; no ROM input |
| `inspect_rom.py` | Read-only ROM metadata/hash/profile inspection |
| `install.py` | Dry-run-first, native-aware, verified app installation |
| `test_*.py`, `sanitizer.cpp` | Host, frontend, installer, ARM, and memory-safety checks |
| `*_hardware_probe.py`, `hardware_probe.py`, `lifecycle_probe.py` | Optional real-device checks |

No build or packaging command downloads a ROM. Builds need no ROM or connected
badge. Commercial-ROM integration tests skip unless you explicitly provide local
paths; synthetic tests generate their own tiny test program in memory/temp files.
Test outputs and local cartridges must never be published.
