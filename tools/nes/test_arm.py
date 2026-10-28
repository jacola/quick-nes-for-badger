#!/usr/bin/env python3
"""Execute the built .mpy's real ARM instructions in Unicorn's Cortex-M33.

This verifies relocation, the native allocator, rendering and cross-reset
snapshots. It is NOT a speed measurement or substitute for a physical badge.
Install the optional test dependency: pip install unicorn
"""
import argparse
import io
import json
from pathlib import Path
import struct
import time
import zlib

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import (UC_CPU_ARM_CORTEX_M33, UC_ARM_REG_R0,
    UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP,
    UC_ARM_REG_LR, UC_ARM_REG_PC)

ROOT = Path(__file__).resolve().parent
CODE, RAM, STUB = 0x10000000, 0x20000000, 0x10080000
BSS, QSTR, FUN = RAM, RAM + 0x1000, RAM + 0x2000
ARENA, ROM, FB, SNAP = RAM + 0x10000, RAM + 0x200000, RAM + 0x300000, RAM + 0x400000
STACK, STOP = RAM + 0x7ff000, STUB + 0xff00


class ArmCore:
    def __init__(self, module, symbols, rom):
        f = io.BytesIO(Path(module).read_bytes())
        def byte():
            b = f.read(1)
            if not b: raise ValueError("Truncated native module")
            return b[0]
        def uint():
            n = 0
            for _ in range(10):
                b = byte(); n = (n << 7) | (b & 127)
                if b < 128: return n
            raise ValueError("Invalid varint")
        header = f.read(4)
        assert header[:3] == b"M\x06\x17", "Expected ARMv7M .mpy v6.3"
        nq, no = uint(), uint()
        assert no == 0
        for _ in range(nq):
            n = uint()
            if not n & 1: f.read((n >> 1) + 1)
        kind = uint()
        assert (kind & 7) == 2, "Expected one native-viper raw code"
        code = bytearray(f.read(kind >> 3))
        flags = uint()
        ro_size = uint() if flags & 0x20 else 0
        bss_size = uint() if flags & 0x40 else 0
        ro = bytearray(f.read(ro_size))
        assert bss_size < 0x800 and ro_size < 0x800
        functions = [STUB + i * 4 + 1 for i in range(90)]
        # Mirror MicroPython's mp_native_relocate (32-bit native pointers).
        index, destbuf = 0, code
        if flags & 0x10:
            while True:
                op = byte()
                if op == 255: break
                if op & 1:
                    addr = uint()
                    destbuf = ro if addr & 1 else code
                    index = (addr >> 1) * 4
                op >>= 1
                n = 1
                if op <= 5:
                    if op & 1: n = uint()
                    dest = [CODE, BSS + 0x800, BSS][op >> 1]
                elif op == 6: dest = QSTR
                elif op == 7: dest = QSTR + 0x100
                elif op == 8: dest = FUN
                else: dest = functions[op - 9]
                for _ in range(n):
                    old = struct.unpack_from("<I", destbuf, index)[0]
                    struct.pack_into("<I", destbuf, index, (old + dest) & 0xffffffff)
                    index += 4
        assert not f.read(), "Unexpected data after native module"
        self.m = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        self.m.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M33)
        self.m.mem_map(CODE, 0x100000)
        self.m.mem_map(RAM, 0x800000)
        self.m.mem_write(CODE, bytes(code))
        if ro: self.m.mem_write(BSS + 0x800, bytes(ro))
        self.m.mem_write(FUN, struct.pack("<90I", *functions))
        self.m.mem_write(QSTR, struct.pack("<%dH" % nq, *range(nq)))
        self.m.mem_write(STUB, b"\x70\x47\x00\xbf" * 100)
        self.m.hook_add(UC_HOOK_CODE, self._stub, begin=STUB, end=STUB + 400)
        self.symbols = json.loads(Path(symbols).read_text())
        self.rom = bytes(rom)
        self.m.mem_write(ROM, self.rom)
        self.reset()

    def _stub(self, machine, address, size, user):
        index = (address - STUB) // 4
        a, b, n = (machine.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2))
        if n > 1024 * 1024:
            raise RuntimeError("Unbounded native memory operation")
        if index == 50:
            if n: machine.mem_write(a, bytes([b & 255]) * n)
        elif index == 51:
            if n: machine.mem_write(a, bytes(machine.mem_read(b, n)))
        else:
            raise RuntimeError("Unexpected MicroPython ABI call " + str(index))
        machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))

    def call(self, name, *args):
        for reg, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3), args):
            self.m.reg_write(reg, value)
        self.m.reg_write(UC_ARM_REG_SP, STACK)
        self.m.reg_write(UC_ARM_REG_LR, STOP | 1)
        self.m.emu_start(CODE + self.symbols[name], STOP, timeout=5000000, count=20000000)
        if self.m.reg_read(UC_ARM_REG_PC) != STOP:
            raise RuntimeError("Native call did not return: " + name)
        return self.m.reg_read(UC_ARM_REG_R0)

    def check(self, result):
        if result:
            message = bytes(self.m.mem_read(result, 160)).split(b"\0", 1)[0].decode()
            raise RuntimeError(message)

    def reset(self):
        self.check(self.call("bnes_open", ROM, len(self.rom), ARENA, 1024 * 1024))

    def step(self, p1=0, p2=0):
        self.check(self.call("bnes_step", FB, p1, p2))

    def pixels(self):
        return bytes(self.m.mem_read(FB, 153600))

    def save(self):
        self.check(self.call("bnes_save", SNAP, 32768, SNAP + 32768))
        length = struct.unpack("<I", self.m.mem_read(SNAP + 32768, 4))[0]
        return bytes(self.m.mem_read(SNAP, length))

    def restore(self, state):
        self.m.mem_write(SNAP, state)
        self.check(self.call("bnes_load", SNAP, len(state)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--module", type=Path, default=ROOT.parents[1] / "badge/apps/zelda/_nes_core.mpy")
    parser.add_argument("--symbols", type=Path, default=ROOT / "build-armv7m/_nes_core.symbols.json")
    args = parser.parse_args()
    from host import Core
    rom = args.rom.read_bytes()
    arm, host = ArmCore(args.module, args.symbols, rom), Core(rom)
    started = time.monotonic()
    def frames(count, pad=0, capture=False):
        trace = []
        for _ in range(count):
            arm.step(pad); host.step(pad)
            pixels, state = arm.pixels(), arm.save()
            assert pixels == host.pixels
            assert state == host.save()
            if capture:
                trace.append((pixels, state))
        return trace
    def press(pad):
        frames(2, pad); frames(30)

    frames(600)
    assert zlib.crc32(arm.pixels()) == 0xc2d244c6
    press(8); press(8); press(1)
    for _ in range(3): press(4)
    press(8); press(8); frames(120)
    assert arm.call("bnes_frame_count") == 976
    checkpoint = arm.save()
    expected = frames(110, 16, capture=True) + frames(100, capture=True)
    arm.reset()
    arm.restore(checkpoint)
    for index, (pixels, state) in enumerate(expected):
        arm.step(16 if index < 110 else 0)
        assert arm.pixels() == pixels
        assert arm.save() == state
    assert arm.call("bnes_errors") == 0
    print("PASS: actual ARM .mpy matches host through 1186 game frames;")
    print("      fresh-VM restore/replay matches every pixel and state byte.")
    print("      arena bytes:", arm.call("bnes_arena_used"))
    print("      simulation time (not hardware FPS): %.2fs" % (time.monotonic() - started))
    host.close()


if __name__ == "__main__":
    main()
