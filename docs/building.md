# Build and test from source

Building needs no game ROM and no badge. The prebuilt module is optional; its
manifest records its binary/source hashes, compiler, optimization, and revisions.
The commands below are for macOS/Linux. Windows users can use WSL for builds;
ordinary installation of a prebuilt app uses standard Python on Windows too.

## 1. Host environment

Use Python 3.10+ and a C++17 compiler (`c++`, or set `CXX`).

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r tools/nes/requirements-test.txt
# Only needed to regenerate/check the original launcher artwork:
python -m pip install -r tools/nes/requirements-assets.txt
```

Build the same engine as a host test library:

```sh
python tools/nes/build.py --host
python -m unittest discover -s tools/nes -p 'test_*.py' -v
```

Without ROM environment variables, commercial-game integration cases skip.
The remaining tests generate tiny original test programs in temporary files or
memory. Do not copy those generated files into the repository or a release.

## 2. Pinned native toolchain

The supplied binary was built with **xPack GNU Arm Embedded GCC 15.2.1-1.1**:
[official downloads](https://github.com/xpack-dev-tools/arm-none-eabi-gcc-xpack/releases/tag/v15.2.1-1.1).
Choose the archive for your host and put its `bin/` on PATH, or pass `--cross`
with the full `arm-none-eabi-` prefix. Do not confuse the host compiler with the
cross compiler. The known macOS ARM64 archive SHA-256 is
`574082d35e49a2bcbdc355836b2a3ae5e5bb3b9456c9f5e37177db2ab4aad870`.
The Linux x64 archive used by CI has SHA-256
`da6a49ad4003944b823c6c93702a8787c922ab34bd7e918ec0eaf6933a9b1ff6`.
CI verifies the archive before extraction and compares its rebuilt `.mpy` with
the supplied prebuilt module.

Obtain the pinned MicroPython source (headers and native linker, not firmware):

```sh
git clone https://github.com/micropython/micropython .toolchain/micropython
git -C .toolchain/micropython checkout 29d45e488c0c194014db7dc63dd974d11f393ef2
```

The builder rejects a different MicroPython revision. The vendored QuickNES
revision is `26bb785c9deddb66a17717b21bb4e328f03ade32`; see its `PORT.md` for local
changes. No game code is embedded in the native build.

## 3. Build the native module and app bundles

From the repository root:

```sh
python tools/nes/build.py --micropython .toolchain/micropython \
  --output badge/apps/zelda/_nes_core.mpy
python tools/nes/package_apps.py
python tools/nes/package_apps.py --check
python tools/nes/generate_library_assets.py --check
```

If the cross compiler is not on PATH, add
`--cross /path/to/toolchain/bin/arm-none-eabi-` to the build command.

The builder emits `_nes_core.build.json` beside the module, and a symbol map/link
report under ignored `tools/nes/build-armv7m/`. Rebuild before ARM tests so the
symbol map corresponds to the tested module. All app binaries/manifests must be
regenerated together; `package_apps.py` copies them from the canonical Zelda app.

The core is PIC Thumb code in a `.mpy` v6.3 container. Its 1 MiB arena, explicit
BSS/arena roots, no-unaligned-access flags, and entry/GOT checks are important
safety constraints. See [architecture](architecture.md); do not remove these
just to silence a build failure. No firmware flash or overclock is part of this.

## 4. Native ARM smoke test without a commercial ROM

```sh
python tools/nes/smoke_arm.py
```

This executes the real `.mpy` ARM code in Unicorn and compares frames/state with
the host C++ core using locally generated tiny programs. It checks relocation
and replay, not badge performance. If you built to another path, use `--module`
and `--symbols` to select the matching pair.

## 5. Optional local-ROM and sanitizer checks

You must supply your own ROMs outside the repository. No test downloads one.

```sh
NES_ROM_DIR=/path/to/private-roms \
ZELDA_ROM=/path/to/private-zelda.nes \
MARIO_ROM="/path/to/private-mario.nes" \
python -m unittest discover -s tools/nes -p 'test_*.py' -v

python tools/nes/build.py --sanitize
UBSAN_OPTIONS=halt_on_error=1 tools/nes/build-host/sanitizer /path/to/private-game.nes
python tools/nes/test_arm.py /path/to/private-zelda.nes
python tools/nes/test_mario_arm.py /path/to/private-mario.nes
python tools/nes/test_library_arm.py --rom-dir /path/to/private-roms \
  --module badge/apps/zelda/_nes_core.mpy
```

Use a compiler/platform with ASan/UBSan support for the sanitizer harness. The
full ARM/game sequences can take considerably longer than the host tests.

## 6. Optional physical-device checks

Read [setup safety](setup.md), save/pause any active game, rediscover the serial
port, and allow only one serial client. Native probes arm a watchdog before
import, use scratch saves rather than player directories, and reset afterward.
The disconnect on reset is expected; require the explicit PASS marker.

```sh
mpremote devs
mpremote connect <port> run tools/nes/hardware_probe.py
mpremote connect <port> run tools/nes/mario_hardware_probe.py
mpremote connect <port> run tools/nes/lifecycle_probe.py
```

These examples require the corresponding app and your matching ROM already
installed. The library/lifecycle probes accept prepended `NES_PROBE`/`NES_APP`
configuration; inspect their module docstrings. Do not publish their outputs if
they contain ROM frames, private paths, device identities, or user state.

## Publication checks

Before sharing changes or making a release:

```sh
python tools/publication_audit.py
python tools/nes/package_apps.py --check
python tools/nes/generate_library_assets.py --check
```

The publication audit checks tracked/indexed file content, ROM signatures,
forbidden private artifacts, native-binary manifests, and licensing files. Never
bypass it with `git add -f` to add a ROM or test dump. Distribute the complete
ROM-free source project, not just an isolated native binary.
