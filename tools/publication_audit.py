#!/usr/bin/env python3
"""Fail closed on ROMs/private artifacts and mismatched native source/binaries.

Default: audit exact Git index blobs (what a commit would contain), not merely
working files. --worktree includes non-ignored untracked files for preparation.
This is defense in depth, not a substitute for human review of public commits.
"""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_SUFFIXES = {".nes", ".fds", ".unf", ".unif", ".sfc", ".smc", ".gb", ".gbc", ".gba",
    ".sav", ".sram", ".state", ".zip", ".7z", ".rar", ".gz", ".xz", ".tar", ".log",
    ".pid", ".tmp", ".bin", ".uf2", ".elf", ".o", ".a", ".so", ".dylib", ".exe",
    ".dll", ".dmp", ".rgb565", ".ppm", ".pem", ".key", ".pyc", ".pyo"}
FORBIDDEN_PARTS = {"roms", "saves", "state", "private", "backups", "build", "dist", "build-deploy",
    ".venv", "venv", ".toolchain", "__pycache__", ".git"}
PRIVATE_TEXT = (
    (re.compile(rb"/(?:Users|home)/[^/\s]+/"), "personal absolute filesystem path"),
    (re.compile(rb"/tmp/" + rb"badge-[^\s]*"), "private development-workspace path"),
    (re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}"), "possible GitHub token"),
    (re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"), "possible GitHub token"),
    (re.compile(rb"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"), "private-key material"),
    (re.compile(rb"(?i)(?:serial|serial_number)[^\n]{0,60}\b[0-9a-f]{16}\b"), "possible device serial"),
)
SOURCE_FILES = ("module.c", "support.c", "engine.cpp", "bridge.h", "palette.h", "build.py")
REQUIRED = ("LICENSE", "THIRD_PARTY.md", "LICENSES/Badge-integration-MIT.txt",
    "LICENSES/LGPL-2.1.txt", "LICENSES/MicroPython-MIT.txt", "LICENSES/GCC-Runtime-Exception.txt",
    "LICENSES/GPL-3.0.txt", "tools/nes/vendor/quicknes/LICENSE",
    "tools/nes/vendor/quicknes/COPYING.LESSER", "tools/nes/vendor/quicknes/PORT.md")


def policy_issues(name, data):
    p = PurePosixPath(name)
    issues = []
    if p.is_absolute() or ".." in p.parts or "\\" in name:
        issues.append("unsafe path")
    if p.suffix.lower() in FORBIDDEN_SUFFIXES or any(part.lower() in FORBIDDEN_PARTS or part.lower().startswith(("build-", ".mpy_ld_cache-")) for part in p.parts):
        issues.append("ROM/private/build/archive artifact path")
    lower = p.name.lower()
    if lower == "secrets.py" or lower.startswith(("autosave.", "wifi_networks", ".env", "._")) or lower == ".ds_store":
        issues.append("private/state/host-metadata filename")
    if data.startswith((b"NES\x1a", b"UNIF", b"FDS\x1a")):
        issues.append("cartridge signature, regardless of filename")
    if data.startswith((b"\x7fELF", b"MZ", b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf")):
        issues.append("unexpected executable/firmware artifact")
    icon = len(p.parts) == 4 and p.parts[:2] == ("badge", "apps") and p.name == "icon.png"
    native = len(p.parts) == 4 and p.parts[:2] == ("badge", "apps") and p.name == "_nes_core.mpy"
    if p.suffix.lower() == ".png":
        if not icon or not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) < 24:
            issues.append("only original app icon PNGs may be published")
        else:
            width, height = struct.unpack(">II", data[16:24])
            if not (24 <= width <= 256 and width == height and len(data) < 65536):
                issues.append("unexpected icon geometry/size")
    elif p.suffix.lower() == ".mpy":
        if not native or not data.startswith(b"M\x06\x17"):
            issues.append("unrecognized native-module artifact")
    else:
        if b"\x00" in data:
            issues.append("unexpected binary data outside audited icons/native module")
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            issues.append("unexpected non-UTF-8 source/data")
    for pattern, reason in PRIVATE_TEXT:
        if pattern.search(data):
            issues.append(reason)
    return issues


def native_source_hash(files):
    names = {"tools/nes/" + name for name in SOURCE_FILES}
    names.update(name for name in files if name.startswith("tools/nes/vendor/quicknes/nes_emu/"))
    digest = hashlib.sha256()
    for name in sorted(names):
        if name not in files:
            raise ValueError("Missing native source: " + name)
        digest.update(name[len("tools/nes/"):].encode() + b"\x00" + files[name])
    return digest.hexdigest()


def profiles_from(files):
    tree = ast.parse(files["tools/nes/games.py"].decode())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "GAMES" for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError("No literal game profile registry")


def audit_project(files):
    failures = []
    if not files:
        return ["No files to audit; stage the reviewed project or use --worktree"]
    for name, data in files.items():
        failures.extend(name + ": " + reason for reason in policy_issues(name, data))
    for name in REQUIRED:
        if name not in files:
            failures.append("Missing license/provenance file: " + name)
    try:
        source_hash = native_source_hash(files)
        profiles = profiles_from(files)
        binaries = set()
        for slug in profiles:
            prefix = "badge/apps/" + slug + "/"
            for name in ("__init__.py", "README.md", "icon.png", "NOTICE.md", "COPYING", "COPYING.LESSER", "COPYING.MICROPYTHON"):
                if prefix + name not in files:
                    failures.append("Incomplete app: " + prefix + name)
            module = files[prefix + "_nes_core.mpy"]
            manifest = json.loads(files[prefix + "_nes_core.build.json"])
            checksum = hashlib.sha256(module).hexdigest()
            binaries.add(checksum)
            if manifest.get("sha256") != checksum or manifest.get("bytes") != len(module):
                failures.append(slug + ": native binary/manifest mismatch")
            if manifest.get("source_sha256") != source_hash:
                failures.append(slug + ": native source hash mismatch; rebuild and repackage")
            if (manifest.get("mpy_version"), manifest.get("architecture"), manifest.get("cpu"), manifest.get("unaligned_access")) != ("6.3", "armv7m", "cortex-m33", False):
                failures.append(slug + ": unexpected native target or alignment configuration")
            for name, data in files.items():
                if name.startswith(prefix) and hashlib.sha256(data).hexdigest() == profiles[slug]["sha256"]:
                    failures.append(name + ": known cartridge data was included")
        if len(binaries) != 1:
            failures.append("Game apps do not share the same native binary")
        for name in files:
            if name.startswith("badge/apps/") and PurePosixPath(name).parts[2] not in profiles:
                failures.append("Unreviewed app directory: " + name)
    except (KeyError, ValueError, TypeError, SyntaxError) as exc:
        failures.append("Package/source metadata cannot be verified: " + str(exc))
    # Check local Markdown links so the extracted standalone project is usable.
    for name, data in files.items():
        if not name.endswith(".md"):
            continue
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", data.decode("utf-8", errors="replace")):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = target.split("#", 1)[0]
            parts = list(PurePosixPath(name).parent.parts)
            for part in PurePosixPath(target).parts:
                if part == "..":
                    if parts:
                        parts.pop()
                elif part != ".":
                    parts.append(part)
            resolved = "/".join(parts)
            if resolved not in files and not any(p.startswith(resolved.rstrip("/") + "/") for p in files):
                failures.append(name + ": broken local link: " + target)
    return failures


def git_index(root):
    raw = subprocess.check_output(["git", "ls-files", "--stage", "-z"], cwd=root)
    entries = []
    for item in raw.split(b"\x00"):
        if not item:
            continue
        metadata, name = item.split(b"\t", 1)
        mode, digest, stage = metadata.split()
        if mode not in (b"100644", b"100755") or stage != b"0":
            raise ValueError("Symlink/submodule/unmerged index entry: " + name.decode())
        entries.append((name.decode(), digest))
    if not entries:
        return {}
    result = subprocess.run(["git", "cat-file", "--batch"], cwd=root,
        input=b"".join(digest + b"\n" for _, digest in entries), stdout=subprocess.PIPE, check=True)
    stream = io.BytesIO(result.stdout)
    files = {}
    for name, expected in entries:
        digest, kind, size = stream.readline().split()
        if digest != expected or kind != b"blob":
            raise ValueError("Unexpected Git object: " + name)
        files[name] = stream.read(int(size))
        if stream.read(1) != b"\n":
            raise ValueError("Truncated Git blob: " + name)
    return files


def working_tree(root):
    raw = subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=root)
    files = {}
    for item in raw.split(b"\x00"):
        if not item:
            continue
        name = item.decode()
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("Missing or symlinked working file: " + name)
        files[name] = path.read_bytes()
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree", action="store_true", help="Inspect non-ignored working files before staging")
    args = parser.parse_args()
    try:
        files = working_tree(ROOT) if args.worktree else git_index(ROOT)
        failures = audit_project(files)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        failures = [str(exc)]
        files = {}
    if failures:
        print("PUBLICATION AUDIT FAILED", file=sys.stderr)
        for message in failures:
            print("- " + message, file=sys.stderr)
        raise SystemExit(1)
    print("PUBLICATION_AUDIT_PASS: %d files; ROM/private-artifact and native-source checks passed." % len(files))


if __name__ == "__main__":
    main()
