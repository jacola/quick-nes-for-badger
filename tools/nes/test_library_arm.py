#!/usr/bin/env python3
"""Compare the actual ARM module with the host for added mappers and games."""
import argparse
from pathlib import Path
import sys
import zlib

from games import GAMES
from game_sequences import SEQUENCES
from host import Core
from test_arm import ArmCore,ROOT


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom-dir",type=Path,required=True)
    parser.add_argument("--game",action="append",choices=tuple(SEQUENCES))
    parser.add_argument("--module",type=Path,default=ROOT/"build-armv7m/_nes_core.mpy")
    parser.add_argument("--symbols",type=Path,default=ROOT/"build-armv7m/_nes_core.symbols.json")
    args=parser.parse_args()
    for slug in args.game or list(SEQUENCES):
        rom=(args.rom_dir/GAMES[slug]["filename"]).read_bytes()
        arm,host=ArmCore(args.module,args.symbols,rom),Core(rom)
        sequence=SEQUENCES[slug]
        def frames(count,pad,capture=False):
            trace=[]
            for _ in range(count):
                arm.step(pad);host.step(pad)
                pixels,state=arm.pixels(),arm.save()
                assert pixels==host.pixels,(slug,"pixels",host.stats())
                assert state==host.save(),(slug,"state",host.stats())
                if capture:trace.append((pixels,state))
            return trace
        for n,p in sequence["boot"]:frames(n,p)
        saved=arm.save()
        print(slug,"GAMEPLAY",host.stats(),"arena",arm.call("bnes_arena_used"),flush=True)
        trace=[]
        for n,p in sequence["replay"]:trace.extend(frames(n,p,True))
        arm.reset();arm.restore(saved)
        pos=0
        for n,p in sequence["replay"]:
            for _ in range(n):
                arm.step(p)
                assert arm.pixels()==trace[pos][0]
                assert arm.save()==trace[pos][1]
                pos+=1
        assert arm.call("bnes_errors")==0
        print(slug,"ARM_REPLAY_PASS",host.stats(),hex(zlib.crc32(arm.pixels())),flush=True)
        host.close()


if __name__=="__main__":main()
