# Compatibility and validation

## Hardware and firmware

The supplied module was built for the GitHub Universe **2026 Badger 2350**:
RP2350 Cortex-M33, 8 MB PSRAM, 320×240 RGB565 framebuffer, stock 230 MHz clock.
It uses the firmware's `badge`, `screen`, `display`, `run`, and launcher APIs.
The tested firmware identifies as MicroPython `1.29.0-preview` with native
`.mpy` **v6.3** (`sys.implementation._mpy == 7942`).

It is not a binary for RP2040/2025 badges, an arbitrary Pico board, another native
ABI, or desktop Python. An ABI/version match is necessary, not sufficient, for a
different firmware. The native container is ARMv7M with Cortex-M33 instructions;
rebuild/test rather than guessing compatibility. No firmware image is included.

## Game profiles

Each profile pins a complete-file SHA-256, byte length, helper-module prefix,
checkpoint magic, and save directory. The hash is what identifies the cartridge,
not its filename. Use `python3 tools/nes/inspect_rom.py /path/to/your-own-game.nes`
and see [`games.py`](../tools/nes/games.py) for the full hashes.

| `--game` | Tested cartridge | Mapper | Bytes |
| --- | --- | ---: | ---: |
| `zelda` | The Legend of Zelda (USA, Rev A) | 1 | 131088 |
| `mario` | Super Mario Bros. (World), the recognized NES 2.0 image | 0 | 40976 |
| `contra` | Contra (USA) | 2 | 131088 |
| `mario3` | Super Mario Bros. 3 (USA, Rev 1) | 4 | 393232 |
| `megaman2` | Mega Man 2 (USA) | 1 | 262160 |
| `tetris` | Tetris (USA, **Tengen**, unlicensed version) | 3 | 49168 |
| `finalfantasy` | Final Fantasy (USA) | 1 | 262160 |
| `finalfantasyjp` | Final Fantasy (Japan, Rev B) | 1 | 262160 |

The two Final Fantasy versions keep distinct ROM identities and checkpoints;
Japanese text/graphics are not translated or modified. Different revisions,
translations, patches, or dumps require a separately reviewed profile. This is
not a blanket claim that every cartridge using mappers 0–4 works.

## Implemented cartridge hardware

- 0: NROM
- 1: MMC1
- 2: UNROM
- 3: CNROM
- 4: MMC3

The current bounded loader accepts at most **256 KiB PRG ROM and 128 KiB CHR
ROM**, with additional mapper-specific limits: NROM is at most 32 KiB PRG / 8 KiB
CHR; UNROM requires CHR RAM; CNROM requires CHR ROM and at most 32 KiB PRG; MMC3
requires at least 32 KiB PRG. Arena capacity can impose further limits.

Unsupported mappers/header variants are rejected. The core normally expects
legacy iNES metadata, NTSC timing, and no trainer/four-screen variant. Only the
recognized Mario NES 2.0 header is adapted to iNES metadata **in RAM**, after
verifying the original complete-file hash. Its PRG/CHR bytes and disk file remain
unchanged. Unknown NES 2.0 metadata is not silently normalized.

## Display, timing, audio, and memory

The full 256×240 image is centered on 320×240; no cropping/scaling, deliberate
frame dropping, gameplay patching, or sprite-limit removal is used. The NTSC
palette is generated from QuickNES's 512-color table. The frontend targets the
NES frame interval, but cannot promise that the badge always keeps up.

A fenced asynchronous display pipeline overlaps emulation with the preceding
LCD transfer. It drains that transfer before writing the shared framebuffer,
saving, or destroying the VM. A synchronous fallback is available. The integration
reserves a bounded 1 MiB arena; decoded cartridge use varies with PRG/CHR size.
Measured arena use ranged from about 178 KB for Mario to 776 KB for Mario 3.

The badge has no onboard speaker: **no audio is played**, although APU timing and
state still run. One controller only. SNES and enhancement-chip support are not
part of this project. QuickNES is not claimed to be cycle-perfect hardware.

## What was validated

Development checks included:

- Actual ARM `.mpy` instructions and relocations compared with the host C++ core.
- Frame/state equality, fresh-VM checkpoint restoration, and deterministic replay.
- Host ASan/UBSan, bounded native memory, garbage collection, and native lifetime.
- Original title/menu/gameplay paths across the eight profiles, including both
  Final Fantasy party-creation/overworld paths and MMC3 Mario 3.
- Physical-device rendering, manual-save debounce, no periodic/exit writes,
  launcher lifecycle, and relaunch from the most recent checkpoint.
- Corruption fallback, ROM/ABI mismatches, interrupted writes, and preservation
  of unreadable saves.

Sampled complete-app performance was around **54–57 FPS** for Zelda/Mario and
**56–57 FPS** in tested Final Fantasy scenes. Native-only or unpaced pipeline
benchmarks can be faster, but are not the same as sustained physical play.
An explicit checkpoint still pauses briefly for flash I/O; periodic-save pauses
were removed by the manual-only policy.

These are scoped development results, **not complete playthroughs or a promise
of perfect 60.0988 Hz, identical timing, all-scene correctness, or hands-on testing
of every orientation/control combination**. Public CI does not contain commercial
ROMs; ROM-dependent integration checks require local files and otherwise skip.
