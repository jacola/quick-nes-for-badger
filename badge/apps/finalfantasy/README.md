# Final Fantasy (USA)

Play the original Final Fantasy with manual checkpoints on the Universe 2026 badge.

This is a ROM-free app profile for [QuickNES for Badger](../../../README.md).
The emulator executes your original cartridge program; the package does not
contain a ROM or download one. It requires the Universe 2026 RP2350 badge and
compatible native `.mpy` v6.3 firmware, not the 2025/RP2040 badge.

## Controls

- Directional controls: NES D-pad.
- SELECT / A: NES A. BACK / B: NES B.
- **UP + DOWN together: START / pause.** Release both to re-arm.
- MENU release: optional START alias. MENU + BACK: NES SELECT.
- **LEFT + RIGHT together: save once.** Release both to re-arm.
- **HOME: exit without saving.**

A confirms/interacts and B cancels. START opens the field menu. Create and name the party through the original menus; make a badge checkpoint even after an in-game inn/tent save.

A green border dot confirms a completed checkpoint; red means failure. There
are no periodic or exit-hook saves. Launch resumes the most recent completed
checkpoint; all later progress is lost on exit/reset/power-off unless you save.
The original game's battery RAM is included in the checkpoint.

## Exact cartridge identity

The installer accepts only this profile's complete original file. Its filename
may differ; the hash and size are decisive. Use only a copy you are entitled to use.

```text
Profile: finalfantasy
Reference filename: Final Fantasy (USA).nes
Bytes: 262160
Mapper: 1
SHA-256: d360beeee19a69d1c92d02292167c57f2d3ca8405b79101fc8c2f39dea549667
```

The disk file and game program/graphics bytes are not modified. The one known
NES 2.0 Mario header is adapted in RAM only; unknown headers are not silently
normalized. Different ROM revisions need separately reviewed profiles.

## Install

From the complete project checkout, with the badge's app volume mounted:

```sh
python3 tools/nes/install.py --game finalfantasy --rom "/path/to/your-own-game.nes" --mount /Volumes/BADGER
# Review the dry run, then repeat with --write. Use --replace for an update.
```

Use your actual mount path. Eject cleanly and restart the badge. Only this app
is installed; firmware, the launcher, other apps, and saves are not replaced.
See the [setup guide](../../../docs/setup.md) for other platforms and troubleshooting.

## Saves and limitations

Checkpoints are isolated under `/state/finalfantasy/autosave.0` and `autosave.1`.
The historical filenames do **not** mean automatic saving. Two verified
generations, ROM/ABI identity, checksums, and atomic rename protect persistence;
unreadable checkpoints are preserved instead of silently overwritten.

The complete 256×240 image is centered on 320×240, without frame skipping or
cropping. One controller; no speaker output or SNES support. Full original speed,
cycle-perfect equivalence, and complete playthroughs are not guaranteed.
[Compatibility and validation](../../../docs/compatibility.md).

Corresponding source/build instructions: [tools/nes](../../../tools/nes/README.md).
Licenses: `NOTICE.md`, `COPYING`, `COPYING.LESSER`, `COPYING.MICROPYTHON` and the
complete project's `LICENSES/`. Emulator licenses do not license a game ROM.
