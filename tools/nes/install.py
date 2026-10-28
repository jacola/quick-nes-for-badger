#!/usr/bin/env python3
"""Verify and install one NES app on a mounted badge; no firmware/save writes.

The standard repository installer excludes .mpy files, so this installer has
an explicit native-aware file list. Default is dry-run. Existing app versions
require --replace and are preserved outside apps/ before an atomic directory
rename. This never changes the menu, main.py, credentials, or /state.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import uuid
from games import GAMES

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "badge/apps/zelda"
ROM_HASH = "89232edf4f9b52e3cb872094bc78973de080befca2ddea893b6e936066514d4e"
FILES = (
    "game.py", "controls.py", "checkpoint.py", "_nes_core.mpy",
    "_nes_core.build.json", "icon.png", "README.md", "NOTICE.md",
    "COPYING", "COPYING.LESSER", "COPYING.MICROPYTHON", "__init__.py",
)

MARIO_ROM_HASH = "0b3d9e1f01ed1668205bab34d6c82b0e281456e137352e4f36a9b2cfa3b66dea"
MARIO_FILES = tuple({"game.py":"mario_game.py", "controls.py":"mario_controls.py",
                     "checkpoint.py":"mario_checkpoint.py"}.get(name,name) for name in FILES)


def game_profile(slug):
    if slug == "zelda":
        return APP, ROM_HASH, FILES
    if slug not in GAMES:
        raise ValueError("Unsupported NES app")
    spec = GAMES[slug]
    names = {name:spec["prefix"]+name for name in ("game.py","controls.py","checkpoint.py")}
    files = tuple(names.get(name,name) for name in FILES)
    return ROOT / "badge/apps" / slug, spec["sha256"], files


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_sources(app, rom, rom_hash=None, files=FILES):
    if rom_hash is None:
        rom_hash = ROM_HASH
    for name in files:
        path = app / name
        if not path.is_file() or path.is_symlink():
            raise ValueError("Missing or unsafe package file: " + str(path))
    if rom.is_symlink() or not rom.is_file() or sha(rom) != rom_hash:
        raise ValueError("ROM does not match the selected game's original image")
    manifest = json.loads((app / "_nes_core.build.json").read_text())
    if manifest.get("sha256") != sha(app / "_nes_core.mpy"):
        raise ValueError("Native module checksum does not match its build manifest")
    if manifest.get("mpy_version") != "6.3" or manifest.get("cpu") != "cortex-m33":
        raise ValueError("Native module targets another runtime")
    return [(app / name, name) for name in files] + [(rom, "game.nes")]


def install(mount, rom, write=False, replace=False, app=APP,
            slug="zelda", rom_hash=None, files=FILES):
    mount, app, rom = Path(mount).resolve(), Path(app).resolve(), Path(rom).absolute()
    if slug not in GAMES:
        raise ValueError("Unsupported NES app")
    sources = validate_sources(app, rom, rom_hash, files)
    if not mount.is_dir() or not (mount / "main.py").is_file() or not (mount / "apps").is_dir():
        raise ValueError("Not a badge /system volume: " + str(mount))
    if (mount / "apps").is_symlink():
        raise ValueError("Refusing a symlinked apps directory")
    destination = mount / "apps" / slug
    if destination.exists() and not replace:
        raise FileExistsError(slug + " already exists; --replace preserves it in a backup")
    if destination.is_symlink():
        raise ValueError("Refusing a symlinked application directory")
    # Include cluster overhead and enough headroom for staging without removing
    # the installed version or any unrelated assets to make space.
    required = sum(((p.stat().st_size + 4095) // 4096) * 4096 for p, _ in sources) + 65536
    if shutil.disk_usage(mount).free < required:
        raise OSError("Insufficient free space for a verified staged installation")
    print(("Installing" if write else "Would install") + " " + slug + " -> " + str(destination))
    if not write:
        print("Dry run: ROM and native module checksums verified; use --write to install.")
        return destination
    staging = mount / ("." + slug + "-stage-" + uuid.uuid4().hex)
    staging.mkdir()
    backup = None
    installed = False
    expected = {name: sha(source) for source, name in sources}
    try:
        # Entry point is copied last; the staging directory is outside apps/.
        sources.sort(key=lambda item: item[1] == "__init__.py")
        for source, name in sources:
            target = staging / name
            shutil.copyfile(source, target)
            if expected[name] != sha(target):
                raise OSError("Copy verification failed: " + name)
        if destination.exists():
            backup_dir = mount / ("." + slug + "-backups")
            if backup_dir.is_symlink():
                raise ValueError("Refusing a symlinked backup directory")
            backup_dir.mkdir(exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
            backup = backup_dir / (slug + "-" + stamp)
            destination.rename(backup)
        staging.rename(destination)
        installed = True
        for source, name in sources:
            if expected[name] != sha(destination / name):
                raise OSError("Installed file failed verification: " + name)
    except Exception:
        if installed and destination.exists():
            destination.rename(mount / ("." + slug + "-failed-" + uuid.uuid4().hex))
        if backup is not None and backup.exists() and not destination.exists():
            backup.rename(destination)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    print("Verified installation. Saves and all unrelated files were untouched.")
    if backup is not None: print("Previous app preserved at", backup)
    print("Eject the volume cleanly, then reset the badge.")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", choices=tuple(GAMES), default="zelda")
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--mount", type=Path, default=Path("/Volumes/BADGER"))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--wait", type=float, default=0,
                        help="wait up to this many seconds for the volume, then install once")
    args = parser.parse_args()
    app, rom_hash, files = game_profile(args.game)
    validate_sources(app, args.rom, rom_hash, files)
    end = time.monotonic() + args.wait
    if not args.mount.is_dir() and args.wait:
        print("Waiting for", args.mount, "(no firmware/serial operations)", flush=True)
    while not args.mount.is_dir() and time.monotonic() < end:
        time.sleep(2)
    install(args.mount, args.rom, args.write, args.replace, app,
            args.game, rom_hash, files)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as exc:
        print("Not installed:", exc, file=sys.stderr)
        sys.exit(1)
