# QuickNES for Badger

Play original NES games on the **GitHub Universe 2026 Badger 2350** badge.

This is an unofficial badge port of [QuickNES](https://github.com/libretro/QuickNES_Core),
not a new emulator written from scratch. The C/C++ core runs as a native
MicroPython `.mpy` module; a small Python frontend handles the badge display,
buttons, and manual checkpoints. It runs locally, without Wi-Fi or a connected PC.

**No ROMs are included or downloaded.** Supply your own lawfully obtained copy.
The repository includes the prebuilt emulator **and its corresponding source and
build scripts**. Game names identify compatibility; no game artwork is extracted
from ROMs for the launcher icons.

## Before you start

- **Supported hardware:** Universe **2026** RP2350 / Cortex-M33 badge with 8 MB
  PSRAM and the 320×240 screen. This is **not** a package for the RP2040/2025 badge.
- **Firmware:** the tested badge runs the 2026 MonaOS/Badgeware API and MicroPython
  native `.mpy` **v6.3** (`sys.implementation._mpy == 7942`). Different firmware or
  native ABIs may need a rebuild; see [compatibility](docs/compatibility.md).
- **Computer:** Python 3.10+ and a USB data cable. The normal installer uses only
  Python's standard library. `mpremote` is optional for serial access.
- **ROM:** one of the exact revisions in [the supported-profile table](docs/compatibility.md#game-profiles).
  The initial release has eight tested profiles; it does not accept arbitrary
  ROMs merely because they use a supported mapper.
- **Space:** enough free space to stage the chosen app and its ROM. Existing apps
  and saves are never deleted automatically to make room.

No firmware flashing or overclocking is required.

## Quick start

### 1. Get the project

Clone it, or use GitHub's **Code → Download ZIP** and extract the complete project:

```sh
git clone https://github.com/jacola/quick-nes-for-badger.git
cd quick-nes-for-badger
```

Keep the full checkout: the app folders alone are not the complete source package.
The native module is already supplied in each app. Building it yourself is optional.

### 2. Identify your ROM

```sh
python3 tools/nes/inspect_rom.py --list
python3 tools/nes/inspect_rom.py "/path/to/your-own-game.nes"
```

This only reads the file and reports its hash/header and matching profile. It
never downloads or rewrites a ROM. A different region, revision, or patched dump
will not match; do not edit the expected hash just to suppress an error.

### 3. Put the badge in USB mass-storage mode

Save any current game, connect USB, and open the badge's **Mass Storage** app.
The volume normally appears as `BADGER` on macOS, under `/media/...` on Linux,
or as a drive letter on Windows.

**`RP2350` is the bootloader drive, not the app drive. Do not copy this project or
a ROM onto it, and do not flash firmware to install this emulator.** See
[USB/setup troubleshooting](docs/setup.md).

### 4. Install one game

For example, for the matching Super Mario Bros. (World) profile:

```sh
# Preview and verify; nothing is written:
python3 tools/nes/install.py --game mario \
  --rom "/path/to/Super Mario Bros. (World).nes" --mount /Volumes/BADGER

# After reviewing the preview:
python3 tools/nes/install.py --game mario \
  --rom "/path/to/Super Mario Bros. (World).nes" --mount /Volumes/BADGER --write
```

Use your actual mount path. On Windows, use `python` instead of `python3` if needed,
and put each command on one line. Add `--replace` only when updating an existing
app: it preserves the previous app directory in a backup outside `apps/`.

The installer checks the ROM and native-module hashes, stages and verifies the
selected app, then promotes it. It does **not** replace firmware, `main.py`, the
launcher, credentials, other apps, or `/state` saves. Do not use a generic copier
that omits `.mpy` files.

### 5. Eject and play

Eject the app volume cleanly and restart the badge if it does not restart itself.
Choose the new game from the launcher. Each game is independently installable.

## Controls and saving

Use logical badge controls; do not infer touch-pad positions from another badge model.

| Badge action | NES action |
| --- | --- |
| Directional controls | D-pad |
| SELECT / A | A |
| BACK / B | B |
| **UP + DOWN together** | **START / pause** |
| MENU release | Optional START alias |
| MENU + BACK | SELECT |
| **LEFT + RIGHT together** | **Save one full checkpoint** |
| **HOME** | **Exit without saving** |

Release both buttons after a chord to re-arm it. START taps last at least four
emulated frames. A green border dot confirms a completed checkpoint; red means
failure. **Save before HOME, reset, or power-off.**

There is **no periodic autosave and no exit-time save**. Launch resumes the most
recent completed manual checkpoint. Original battery-backed game saves also live
in the emulated state: make a badge checkpoint to persist them. Checkpoints use
two generations, checksums, ROM identity, and verified atomic writes. Different
games/versions have separate save directories. See [save behavior](docs/saves.md).

## What to expect

- Full **256×240** NES picture centered on 320×240, without scaling, cropping,
  frame skipping, or game-code patches.
- Mappers **0–4**: NROM, MMC1, UNROM, CNROM, MMC3. One controller.
- Roughly mid-50s FPS in sampled tested scenes at the stock 230 MHz. **Not a
  guarantee of full NES speed or cycle-perfect emulation.**
- **No sound output:** APU timing/state is emulated, but the badge has no onboard
  speaker. No SNES support.
- Up to a bounded 1 MiB native arena, using the existing PSRAM.

[Compatibility and measured validation](docs/compatibility.md) ·
[Build from source](docs/building.md) · [Architecture](docs/architecture.md) ·
[Contributing / adding a profile](CONTRIBUTING.md)

## Credits and licensing

The emulator comes from **QuickNES / Nes_Emu**, originally by **Shay Green (blargg)**,
via the [libretro project](https://github.com/libretro/QuickNES_Core). MicroPython
provides the native-module ABI; Pimoroni and GitHub provide the badge platform.
The badge integration and packaging are by [jacola](https://github.com/jacola).

The combined emulator distribution is provided under **GPL v2**, with the original
component licenses retained. New badge integration code remains available under
MIT; legacy QuickNES components carry LGPL notices, and MicroPython ABI glue is
MIT. See [LICENSE](LICENSE), [THIRD_PARTY.md](THIRD_PARTY.md), and [LICENSES/](LICENSES/).
Do not redistribute the native binary without the applicable source/license
obligations. These licenses do not grant rights to any game ROM.

This project is not affiliated with or endorsed by Nintendo, the game publishers,
Pimoroni, GitHub, or the libretro project.
