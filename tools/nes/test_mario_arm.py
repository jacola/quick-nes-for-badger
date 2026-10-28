#!/usr/bin/env python3
"""Run the actual ARM .mpy against the supplied Mario ROM, including resume."""
import argparse
from pathlib import Path
import sys
import zlib
from test_arm import ArmCore, ROOT
from host import Core
sys.path.insert(0,str(ROOT.parents[1]/'badge/apps/mario'))
from mario_game import core_rom


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('rom',type=Path)
    p.add_argument('--module',type=Path,default=ROOT.parents[1]/'badge/apps/mario/_nes_core.mpy')
    p.add_argument('--symbols',type=Path,default=ROOT/'build-armv7m/_nes_core.symbols.json')
    args=p.parse_args()
    rom=bytes(core_rom(args.rom.read_bytes()))
    arm,host=ArmCore(args.module,args.symbols,rom),Core(rom)
    def frames(count,pad=0,capture=False):
        trace=[]
        for _ in range(count):
            arm.step(pad);host.step(pad)
            pixels,state=arm.pixels(),arm.save()
            assert pixels==host.pixels
            assert state==host.save()
            if capture:trace.append((pixels,state))
        print('MARIO_ARM',host.stats()[0],hex(zlib.crc32(arm.pixels())))
        return trace
    frames(120);frames(2,8);frames(200)
    saved=arm.save()
    expected=frames(90,0x82,True)+frames(30,0x83,True)+frames(50,0x82,True)
    arm.reset();arm.restore(saved)
    for i,(pixels,state) in enumerate(expected):
        arm.step(0x82 if i<90 or i>=120 else 0x83)
        assert arm.pixels()==pixels
        assert arm.save()==state
    assert arm.call('bnes_errors')==0
    print('PASS: Mario ARM core matched every frame/state through title, 1-1, run/jump and fresh-VM resume.')
    print('Arena bytes:',arm.call('bnes_arena_used'))
    host.close()


if __name__=='__main__':main()
