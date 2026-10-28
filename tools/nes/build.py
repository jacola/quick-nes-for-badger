#!/usr/bin/env python3
"""Build a native ARM .mpy or the same engine as a host test library.

Requires a MicroPython source checkout, pyelftools and arm-none-eabi-gcc for
native builds. No firmware, SDK, network access, or ROM is needed to build.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
VENDOR = ROOT / "vendor" / "quicknes" / "nes_emu"
MPY_REVISION = "29d45e488c0c194014db7dc63dd974d11f393ef2"
CORE_REVISION = "26bb785c9deddb66a17717b21bb4e328f03ade32"
SOURCES = [
    "abstract_file.cpp", "Data_Reader.cpp", "apu_state.cpp", "Blip_Buffer.cpp",
    "Nes_Apu.cpp", "Nes_Cart.cpp", "Nes_Core.cpp", "Nes_Cpu.cpp",
    "nes_data.cpp", "Nes_File.cpp", "Nes_Mapper.cpp", "Nes_Oscs.cpp",
    "Nes_Ppu.cpp", "Nes_Ppu_Impl.cpp", "Nes_Ppu_Rendering.cpp", "Nes_State.cpp",
]


def run(args):
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), check=True, cwd=ROOT)


def generate_palette():
    # Use the upstream emulator's complete 512-color NTSC palette, including
    # emphasis modes, rather than inventing colors or scaling game artwork.
    import re
    source = (VENDOR / "Nes_Emu.cpp").read_text()
    table = source.split("Nes_Emu::rgb_t const Nes_Emu::nes_colors [color_table_size] =", 1)[1]
    table = table.split("};", 1)[0]
    colors = re.findall(r"\{\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\}", table)
    if len(colors) != 512:
        raise ValueError("Upstream palette must have exactly 512 RGB entries")
    values = []
    for r, g, b in colors:
        r, g, b = int(r), int(g), int(b)
        values.append(((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3))
    content = "// Generated from QuickNES Nes_Emu.cpp; LGPL-2.1-or-later. Do not edit.\n"
    content += "#include <stdint.h>\nstatic const uint16_t NES_RGB565[512] = {\n"
    for i in range(0, 512, 8):
        content += "    " + ", ".join("0x%04x" % v for v in values[i:i + 8]) + ",\n"
    content += "};\n"
    path = ROOT / "palette.h"
    if not path.exists() or path.read_text() != content:
        path.write_text(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opt", choices=("O2", "O3", "Os"), default="O2")
    parser.add_argument("--host", action="store_true", help="build host test library, not .mpy")
    parser.add_argument("--sanitize", action="store_true", help="build standalone host ASan/UBSan harness")
    parser.add_argument("--micropython", type=Path, default=os.environ.get("MPY_DIR"))
    parser.add_argument("--cross", default=os.environ.get("CROSS", "arm-none-eabi-"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output is not None:
        args.output = args.output.resolve()
    generate_palette()
    cpp = [ROOT / "engine.cpp"] + [VENDOR / s for s in SOURCES]
    common = ["-" + args.opt, "-DNDEBUG", "-DBADGE_NES_BUILD", "-DNO_UNALIGNED_ACCESS",
              "-fno-strict-aliasing", "-Wno-multichar",
              "-I" + str(ROOT), "-I" + str(VENDOR)]
    if args.sanitize:
        out = args.output or ROOT / "build-host" / "sanitizer"
        out.parent.mkdir(parents=True, exist_ok=True)
        run([os.environ.get("CXX", "c++"), "-std=c++17", *common, "-O1", "-g",
             "-fsanitize=address,undefined", ROOT / "sanitizer.cpp", *cpp, "-o", out])
        print(out)
        return
    if args.host:
        out = args.output or ROOT / "build-host" / ("libbadge_nes.dylib" if sys.platform == "darwin" else "libbadge_nes.so")
        out.parent.mkdir(parents=True, exist_ok=True)
        run([os.environ.get("CXX", "c++"), "-std=c++17", *common,
             "-dynamiclib" if sys.platform == "darwin" else "-shared", "-fPIC",
             *cpp, "-o", out])
        print(out)
        return
    if not args.micropython:
        parser.error("--micropython or MPY_DIR is required (see README.md)")
    mpy = args.micropython.resolve()
    revision = subprocess.check_output(["git", "-C", str(mpy), "rev-parse", "HEAD"], text=True).strip()
    if revision != MPY_REVISION:
        parser.error("Use the pinned MicroPython revision " + MPY_REVISION)
    out = args.output or ROOT / "build-armv7m" / "_nes_core.mpy"
    out.parent.mkdir(parents=True, exist_ok=True)
    build = ROOT / "build-armv7m"
    build.mkdir(exist_ok=True)
    config = build / "_nes_core.config.h"
    linker = mpy / "tools" / "mpy_ld.py"
    run([sys.executable, linker, "--arch", "armv7m", "--preprocess",
         "-o", config, ROOT / "module.c"])
    flags = [*common, "-fPIC", "-fno-common", "-ffunction-sections", "-fdata-sections",
             "-fno-unwind-tables", "-fno-asynchronous-unwind-tables",
             "-mthumb", "-mcpu=cortex-m33", "-mfloat-abi=soft", "-mno-unaligned-access", "-DNES_NATIVE"]
    objects = []
    for source in [ROOT / "module.c", ROOT / "support.c", *cpp]:
        obj = build / (source.stem + ".o")
        objects.append(obj)
        if source.suffix == ".c":
            extra = ["-std=c99", "-I" + str(mpy), "-DNO_QSTR",
                     "-DMICROPY_ENABLE_DYNRUNTIME", "-DMICROPY_FLOAT_IMPL=MICROPY_FLOAT_IMPL_FLOAT",
                     "-DMP_CONFIGFILE=<" + str(config) + ">"]
            compiler = args.cross + "gcc"
        else:
            extra = ["-std=c++17", "-fno-rtti", "-fno-exceptions",
                     "-fno-threadsafe-statics", "-fno-use-cxa-atexit", "-fcheck-new"]
            compiler = args.cross + "g++"
        # mpy_ld computes its entry trampoline before laying out function
        # sections. Keep mpy_init in the first, ordinary .text section.
        compile_flags = flags if source.suffix != ".c" else [
            f for f in flags if f not in ("-ffunction-sections", "-fdata-sections")]
        run([compiler, *compile_flags, *extra, "-c", source, "-o", obj])
    # Dead-strip unreferenced library APIs before mpy_ld: this avoids bringing
    # in desktop I/O, audio sinks, constructors, or the rest of the C++ runtime.
    combined = build / "combined.o"
    run([args.cross + "ld", "-r", "--gc-sections", "-u", "mpy_init",
         *objects, "-o", combined])
    libgcc = subprocess.check_output(
        [args.cross + "gcc", "-mthumb", "-mcpu=cortex-m33", "-mfloat-abi=soft",
         "--print-libgcc-file-name"], text=True).strip()
    command = [sys.executable, str(linker), "-vv", "--arch", "armv7m",
               "--qstrs", str(config), "-l" + libgcc, "-o", str(out), str(combined)]
    linked = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    (build / "link.map").write_text(linked.stdout)
    if linked.returncode:
        raise RuntimeError(linked.stdout[-4000:])
    sections = {name: int(addr, 16) for addr, name in re.findall(
        r"  ([0-9a-f]{8}) (\S+) size=", linked.stdout)}
    if sections.get(".bss") != 0:
        raise RuntimeError("GC anchor is not at the start of the native BSS")
    symbols = {name.removeprefix(".text."): addr + 1
               for name, addr in sections.items() if name.startswith(".text.bnes_")}
    (build / "_nes_core.symbols.json").write_text(json.dumps(symbols, indent=2) + "\n")
    for line in linked.stdout.splitlines():
        if line.startswith(("arch:", "text size:", "bss size:", "GOT entries:")):
            print(line)
    source_hash = hashlib.sha256()
    for path in sorted([ROOT / p for p in ("module.c", "support.c", "engine.cpp", "bridge.h", "palette.h", "build.py")] +
                       [p for p in VENDOR.rglob("*") if p.is_file()]):
        source_hash.update(str(path.relative_to(ROOT)).encode() + b"\0" + path.read_bytes())
    manifest = {
        "module": out.name, "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        "bytes": out.stat().st_size, "mpy_version": "6.3", "architecture": "armv7m",
        "cpu": "cortex-m33", "unaligned_access": False, "optimization": args.opt,
        "source_sha256": source_hash.hexdigest(), "quicknes_revision": CORE_REVISION,
        "micropython_revision": MPY_REVISION,
        "compiler": subprocess.check_output([args.cross + "gcc", "--version"], text=True).splitlines()[0],
    }
    out.with_suffix(".build.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(out)


if __name__ == "__main__":
    main()
