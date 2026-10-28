#!/usr/bin/env python3
"""Bundle standalone game apps from the tested Zelda runtime and game registry.

Zelda is the canonical runtime; it is not rewritten. Helpers use distinct names
in other apps, and checksums/magics/save directories remain game-specific.
No ROM is read/copied/downloaded here. Use install.py with the supplied ROM.
"""
import argparse
from pathlib import Path
import shutil
from games import GAMES

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "badge/apps/zelda"
COMMON = ("_nes_core.mpy", "_nes_core.build.json", "NOTICE.md",
          "COPYING", "COPYING.LESSER", "COPYING.MICROPYTHON")


def replace(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Runtime template changed; review substitution: " + old)
    return text.replace(old, new, 1)


def render(slug):
    spec = GAMES[slug]
    prefix = spec["prefix"]
    game = (BASE / "game.py").read_text()
    game = replace(game, "from checkpoint import Checkpoints", "from " + prefix + "checkpoint import Checkpoints")
    game = replace(game, "from controls import Controls", "from " + prefix + "controls import Controls")
    game = replace(game, 'ROM_SHA256 = "' + GAMES["zelda"]["sha256"] + '"',
                   'ROM_SHA256 = "' + spec["sha256"] + '"')
    game = replace(game, "ROM_SIZE = 131088", "ROM_SIZE = " + str(spec["size"]))
    game = replace(game, 'state_dir="/state/zelda"', 'state_dir="/state/' + slug + '"')
    game = game.replace("Zelda", spec["label"])
    if "nes2_header" in spec:
        header = repr(bytes.fromhex(spec["nes2_header"]))
        helper = '''SOURCE_HEADER = %s


def core_rom(data):
    """Adapt only known NES 2.0 metadata in RAM; never change PRG/CHR/file bytes."""
    if len(data) != ROM_SIZE or bytes(data[:16]) != SOURCE_HEADER:
        raise ValueError("Unsupported cartridge metadata")
    adapted = bytearray(data)
    adapted[7] = 0
    adapted[8:16] = bytes(8)
    return adapted


''' % header
        game = replace(game, "class Game:\n", helper + "class Game:\n")
        game = replace(game, "core.load(rom, self.arena)", "core.load(core_rom(rom), self.arena)")

    checkpoint = (BASE / "checkpoint.py").read_text()
    checkpoint = checkpoint.replace("/state/zelda", "/state/" + slug)
    checkpoint = checkpoint.replace("ZELDAST1", spec["magic"])
    checkpoint = checkpoint.replace("Zelda checkpoint", spec["label"] + " checkpoint")

    entry = (BASE / "__init__.py").read_text()
    entry = entry.replace("/apps/zelda", "/apps/" + slug)
    entry = replace(entry, "from game import Game", "from " + prefix + "game import Game")
    entry = replace(entry, '"""The original Legend of Zelda ROM running locally in a native NES emulator."""',
                    '"""' + spec["title"] + ' running locally in a native NES emulator."""')
    entry = entry.replace("Zelda", spec["label"])
    return {
        "__init__.py":entry,
        prefix+"game.py":game,
        prefix+"checkpoint.py":checkpoint,
        prefix+"controls.py":(BASE/"controls.py").read_text(),
        ".gitignore":"game.nes\n__pycache__/\n*.state\n*.tmp\n",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", action="append", choices=[g for g in GAMES if g != "zelda"])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for slug in args.game or [g for g in GAMES if g != "zelda"]:
        target = ROOT / "badge/apps" / slug
        expected = {name:text.encode() for name,text in render(slug).items()}
        expected.update({name:(BASE/name).read_bytes() for name in COMMON})
        if args.check:
            for name,data in expected.items():
                if not (target/name).is_file() or (target/name).read_bytes() != data:
                    raise SystemExit("Package is stale: " + str(target/name))
        else:
            target.mkdir(parents=True,exist_ok=True)
            for name,data in expected.items():(target/name).write_bytes(data)
        print(("Checked " if args.check else "Packaged ") + slug)


if __name__ == "__main__":
    main()
