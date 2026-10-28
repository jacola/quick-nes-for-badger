#!/usr/bin/env python3
"""Run actual native ARM code against tiny generated programs, not game ROMs."""
import argparse
from pathlib import Path
import struct
import time

from host import Core
from test_arm import ArmCore, ROOT


def synthetic_cartridge(mapper):
    # Original test program: disable IRQs, increment zero-page RAM, loop.
    # Repeat in each PRG bank so all supported default mappings see valid code.
    bank = bytearray([0xea]) * 16384
    bank[:8] = bytes([0x78, 0xe6, 0x00, 0x4c, 0x01, 0x80, 0x40, 0x40])
    bank[-6:] = struct.pack("<3H", 0x8006, 0x8000, 0x8007)
    chr_banks = 0 if mapper == 2 else 1  # UNROM uses CHR RAM, not CHR ROM.
    return b"NES\x1a" + bytes([2, chr_banks, mapper << 4, 0]) + bytes(8) + bank * 2 + bytes(chr_banks * 8192)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", type=Path, default=ROOT.parents[1] / "badge/apps/zelda/_nes_core.mpy")
    parser.add_argument("--symbols", type=Path, default=ROOT / "build-armv7m/_nes_core.symbols.json")
    args = parser.parse_args()
    if not args.symbols.is_file():
        parser.error("Rebuild the native module first; a matching symbol map is required")
    started = time.monotonic()
    for mapper in range(5):
        rom = synthetic_cartridge(mapper)
        arm, host = ArmCore(args.module, args.symbols, rom), Core(rom)
        try:
            for i in range(8):
                pad = (1, 16, 0, 128)[i % 4]
                arm.step(pad)
                host.step(pad)
                assert arm.pixels() == bytes(host.pixels)
                assert arm.save() == host.save()
            saved = arm.save()
            trace = []
            for i in range(8):
                arm.step(i & 1)
                host.step(i & 1)
                assert arm.pixels() == bytes(host.pixels)
                assert arm.save() == host.save()
                trace.append((arm.pixels(), arm.save()))
            arm.reset()
            arm.restore(saved)
            for i, (pixels, state) in enumerate(trace):
                arm.step(i & 1)
                assert arm.pixels() == pixels and arm.save() == state
            assert arm.call("bnes_errors") == 0
            print("ARM_SYNTHETIC_PASS mapper=%d arena=%d" % (mapper, arm.call("bnes_arena_used")))
        finally:
            host.close()
    print("All five mapper reset/replay paths match host frames/state; %.2fs (not hardware FPS)." % (time.monotonic() - started))


if __name__ == "__main__":
    main()
