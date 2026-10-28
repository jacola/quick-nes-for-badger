#!/usr/bin/env python3
"""Generate original controller icons and profile docs without reading any ROM."""
import argparse
import io
from pathlib import Path

from PIL import Image, ImageDraw
from games import GAMES

ROOT = Path(__file__).resolve().parents[2]
# Simple original 3x5 letter marks; no game sprites, fonts, or screenshots.
LETTERS = {"Z": (7, 1, 2, 4, 7), "M": (5, 7, 7, 5, 5), "C": (7, 4, 4, 4, 7),
           "3": (7, 1, 7, 1, 7), "2": (7, 1, 7, 4, 7), "T": (7, 2, 2, 2, 2),
           "F": (7, 4, 6, 4, 4), "J": (7, 1, 1, 5, 7), "N": (5, 7, 7, 7, 5)}
MARKS = {"zelda": "Z", "mario": "M", "contra": "C", "mario3": "3",
         "megaman2": "2", "tetris": "T", "finalfantasy": "F", "finalfantasyjp": "J"}
COLORS = ((73, 190, 129), (235, 87, 87), (231, 141, 64), (236, 191, 66),
          (72, 157, 223), (164, 111, 226), (74, 184, 209), (216, 111, 193))
HINTS = {
    "zelda": "START opens the inventory. On the original name-registration screen, A enters letters and NES SELECT moves between registration rows; choose REGISTER END and press START to finish.",
    "mario": "A jumps; B runs or throws fireballs. START leaves the original title screen and pauses during play.",
    "contra": "A jumps and B shoots. Choose 1 PLAYER; two-controller play is not implemented.",
    "mario3": "A jumps; B runs, carries, or uses the equipped projectile. Enter a numbered map stage with A.",
    "megaman2": "A jumps; B fires. START confirms difficulty/boss selection and opens the weapon menu.",
    "tetris": "A and B rotate; LEFT/RIGHT move and DOWN speeds the fall. START confirms the original game menus. This is the Tengen version.",
    "finalfantasy": "A confirms/interacts and B cancels. START opens the field menu. Create and name the party through the original menus; make a badge checkpoint even after an in-game inn/tent save.",
    "finalfantasyjp": "The original Japanese text and graphics are unchanged. Create/name the party through the original menus. Checkpoints are separate from the USA version; in-game saves still need a badge checkpoint to persist.",
}


def icon(slug):
    canvas = Image.new("RGB", (48, 48), (15, 20, 32))
    draw = ImageDraw.Draw(canvas)
    index = list(GAMES).index(slug)
    accent = COLORS[index % len(COLORS)]
    draw.rectangle((2, 2, 45, 45), outline=accent, width=2)
    for y, bits in enumerate(LETTERS.get(MARKS.get(slug, "N"), LETTERS["N"])):
        for x in range(3):
            if bits & (1 << (2 - x)):
                draw.rectangle((19 + x * 3, 6 + y * 3, 21 + x * 3, 8 + y * 3), fill=accent)
    draw.rounded_rectangle((7, 26, 40, 40), radius=3, fill=(160, 169, 181))
    draw.rectangle((13, 29, 16, 37), fill=(24, 29, 40))
    draw.rectangle((10, 32, 19, 34), fill=(24, 29, 40))
    draw.ellipse((27, 33, 31, 37), fill=(203, 65, 77))
    draw.ellipse((33, 29, 37, 33), fill=(203, 65, 77))
    output = io.BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    return output.getvalue()


def readme(slug):
    spec = GAMES[slug]
    return f'''# {spec['title']}

{spec['description']}

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

{HINTS.get(slug, "Use the original game's controls and menus.")}

A green border dot confirms a completed checkpoint; red means failure. There
are no periodic or exit-hook saves. Launch resumes the most recent completed
checkpoint; all later progress is lost on exit/reset/power-off unless you save.
The original game's battery RAM is included in the checkpoint.

## Exact cartridge identity

The installer accepts only this profile's complete original file. Its filename
may differ; the hash and size are decisive. Use only a copy you are entitled to use.

```text
Profile: {slug}
Reference filename: {spec['filename']}
Bytes: {spec['size']}
Mapper: {spec['mapper']}
SHA-256: {spec['sha256']}
```

The disk file and game program/graphics bytes are not modified. The one known
NES 2.0 Mario header is adapted in RAM only; unknown headers are not silently
normalized. Different ROM revisions need separately reviewed profiles.

## Install

From the complete project checkout, with the badge's app volume mounted:

```sh
python3 tools/nes/install.py --game {slug} --rom "/path/to/your-own-game.nes" --mount /Volumes/BADGER
# Review the dry run, then repeat with --write. Use --replace for an update.
```

Use your actual mount path. Eject cleanly and restart the badge. Only this app
is installed; firmware, the launcher, other apps, and saves are not replaced.
See the [setup guide](../../../docs/setup.md) for other platforms and troubleshooting.

## Saves and limitations

Checkpoints are isolated under `/state/{slug}/autosave.0` and `autosave.1`.
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
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", action="append", choices=tuple(GAMES))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for slug in args.game or GAMES:
        folder = ROOT / "badge/apps" / slug
        expected = {"icon.png": icon(slug), "README.md": readme(slug).encode()}
        if args.check:
            for name, data in expected.items():
                if (folder / name).read_bytes() != data:
                    raise SystemExit("Generated asset is stale: " + str(folder / name))
        else:
            folder.mkdir(parents=True, exist_ok=True)
            for name, data in expected.items():
                (folder / name).write_bytes(data)
        print(("Checked " if args.check else "Generated ") + slug)


if __name__ == "__main__":
    main()
