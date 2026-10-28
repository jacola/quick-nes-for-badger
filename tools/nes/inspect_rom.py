#!/usr/bin/env python3
"""Read local cartridge metadata and identify a tested profile; never modify it."""
import argparse
import hashlib
import json
from pathlib import Path

from games import GAMES

MAPPERS = {0: "NROM", 1: "MMC1", 2: "UNROM", 3: "CNROM", 4: "MMC3"}
MAX_INSPECTION_BYTES = 16 * 1024 * 1024


def inspect_rom(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Provide a regular, non-symlinked local ROM file")
    if path.stat().st_size > MAX_INSPECTION_BYTES:
        raise ValueError("File exceeds this tool's 16 MiB inspection limit")
    with path.open("rb") as stream:
        header = stream.read(16)
        if len(header) != 16 or header[:4] != b"NES\x1a":
            raise ValueError("Expected an uncompressed iNES/NES 2.0 file, not a ZIP, FDS image, or HTML download")
        digest = hashlib.sha256(header)
        size = len(header)
        for chunk in iter(lambda: stream.read(65536), b""):
            size += len(chunk)
            if size > MAX_INSPECTION_BYTES:
                raise ValueError("File grew beyond the inspection limit")
            digest.update(chunk)
    nes2 = header[7] & 12 == 8
    mapper = (header[6] >> 4) | (header[7] & 240)
    if nes2:
        mapper |= (header[8] & 15) << 8
    checksum = digest.hexdigest()
    matches = [slug for slug, spec in GAMES.items()
               if spec["sha256"] == checksum and spec["size"] == size]
    return {"filename": path.name, "bytes": size, "sha256": checksum,
            "header": "NES 2.0" if nes2 else "iNES", "mapper": mapper,
            "mapper_name": MAPPERS.get(mapper, "not implemented in this build"),
            "mapper_implemented": mapper in MAPPERS, "trainer": bool(header[6] & 4),
            "matching_profile": matches[0] if matches else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path, nargs="?")
    parser.add_argument("--list", action="store_true", help="List available tested profiles")
    parser.add_argument("--json", action="store_true", help="Print machine-readable metadata")
    args = parser.parse_args()
    if args.list:
        for slug, spec in GAMES.items():
            print("%-16s mapper %-2d %7d bytes  %s" % (slug, spec["mapper"], spec["size"], spec["title"]))
        if args.rom is None:
            return
    if args.rom is None:
        parser.error("provide a local ROM path or --list")
    try:
        result = inspect_rom(args.rom)
    except (OSError, ValueError) as exc:
        parser.exit(1, "Cannot inspect: " + str(exc) + "\n")
    if args.json:
        print(json.dumps(result, indent=2))
        return
    for key in ("filename", "bytes", "sha256", "header", "mapper", "mapper_name"):
        print("%s: %s" % (key, result[key]))
    if result["matching_profile"]:
        print("Matching installer profile: --game " + result["matching_profile"])
    else:
        print("No tested profile matches this exact file. See CONTRIBUTING.md.")
        print("A supported mapper alone does not establish compatibility; no file was changed.")


if __name__ == "__main__":
    main()
