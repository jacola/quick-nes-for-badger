# Contributing

Keep this project reproducible, ROM-free, and safe for users' existing badges.
Do not commit ROMs (including test/demo cartridge binaries), firmware dumps,
checkpoints, save files, credentials, device captures, private paths, or temporary
build/deployment outputs. Do not attach them to issues, pull requests, or releases.

## Development checks

See [building.md](docs/building.md). At minimum:

```sh
python tools/nes/build.py --host
python -m unittest discover -s tools/nes -p 'test_*.py' -v
python tools/nes/package_apps.py --check
python tools/nes/generate_library_assets.py --check
python tools/publication_audit.py
```

To reject unsafe files before a local commit as well as in CI, opt into the
included hook for this checkout:

```sh
git config core.hooksPath .githooks
```

The audit defaults to the exact Git index blobs. Use `--worktree` during local
preparation before staging; it also checks non-ignored untracked files. Publication
checks require a Git checkout and are skipped in a plain source ZIP.

Native/ABI changes also need a pinned native rebuild, actual ARM execution,
sanitizer checks, and appropriate physical-device testing. Explain what you
actually tested; do not describe injected inputs or an unpaced benchmark as a
complete physical playthrough or a guaranteed full frame rate.

## Adding another cartridge profile

The core implements mappers 0–4; a profile is not a promise that every cartridge
using one of those mappers works. Other mappers, trainers, PAL timing, and unknown
NES 2.0 metadata need separate engineering, not just a changed hash.

1. Keep your lawful ROM outside the checkout. Run `inspect_rom.py --json` locally.
   Share only the filename/revision, size, mapper, and complete-file SHA-256—not
   the ROM or graphics extracted from it.
2. Add a reviewed entry to `tools/nes/games.py` with a safe lowercase app slug,
   display title/label, unique helper prefix, ROM filename/size/hash, mapper, and
   unique **eight-byte ASCII checkpoint magic**. Use only letters/digits/underscores
   in slugs/prefixes. Never use firmware app names such as `menu`, `settings`,
   `startup`, `system`, or `mass_storage`.
3. Generate the independent app:

   ```sh
   python tools/nes/package_apps.py --game your_profile
   python tools/nes/generate_library_assets.py --game your_profile
   ```

   The asset generator has an original generic icon fallback. Add useful game
   instructions there if appropriate; do not import a game's sprites or fonts.
4. Add deterministic input/replay coverage in `game_sequences.py` and tests.
   Verify the exact ROM identity, mapper behavior, bounded arena use, pixel/state
   replay, save isolation, and graceful failure paths.
5. Test the real badge and report the scope/limitations. Use scratch checkpoints,
   never someone else's player directory. Keep normal gameplay code/assets intact.

Do not change an existing profile's identity to accept a different dump: make a
separate profile when needed, and avoid colliding with existing save directories.
The recognized Mario NES 2.0 header conversion is deliberately specific; it is not
a general header-rewriting feature.

## Shared runtime changes

`badge/apps/zelda/` is the canonical frontend. Edit shared behavior there, then run
`package_apps.py`; generated game/checkpoint/control helpers must remain in parity.
Maintain manual-only saving, START/save chord debounce, safe display fences,
late-callback guards, and teardown only after the actual run loop returns.

Keep the original QuickNES notices and document vendor patches in `PORT.md`.
The engine's native memory/GC/unaligned-access assumptions need extra care;
read [architecture.md](docs/architecture.md) before changing them.

## Releases and issue reports

Use a fresh, audited source tree and include corresponding source and all licenses
with native binaries. The `.gitignore` is a convenience, not proof of cleanliness;
run the publication audit and inspect the commit/release contents.

Useful bug reports include the app profile, ROM hash (not contents), firmware and
native ABI, symptom, reproduction inputs, and whether a previous valid checkpoint
is preserved. Remove personal identifiers, credentials, and local paths from logs.
