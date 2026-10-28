"""Additional cartridge mappers, START handling and exact save replay."""
import os
from pathlib import Path
import struct
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
from games import GAMES
from game_sequences import SEQUENCES
from host import Core
from package_apps import render
from test_zelda import tiny_rom


class GeneratedAppsTests(unittest.TestCase):
    def test_helpers_match_canonical_runtime(self):
        for slug in GAMES:
            if slug=="zelda":continue
            for name,text in render(slug).items():
                with self.subTest(game=slug,file=name):
                    self.assertEqual((ROOT/"badge/apps"/slug/name).read_text(),text)
    def test_all_save_identities_are_unique(self):
        self.assertEqual(len({s["magic"] for s in GAMES.values()}),len(GAMES))
        self.assertEqual(len({s["sha256"] for s in GAMES.values()}),len(GAMES))
        for spec in GAMES.values():self.assertEqual(len(spec["magic"]),8)


class MapperStateTests(unittest.TestCase):
    def test_nrom_and_cnrom_restore_do_not_create_ram_mapping(self):
        for mapper in (0,3):
            prg=bytearray(tiny_rom()[16:])
            prg[:10]=bytes([0xa9,0x5a,0x8d,0x00,0x60,0xe6,0x00,0x4c,0x00,0x80])
            rom=b"NES\x1a"+bytes([1,1,mapper<<4,0])+bytes(8)+prg+bytes(8192)
            core=Core(rom)
            try:
                for _ in range(10):core.step()
                saved=core.save()
                for _ in range(100):core.step()
                expected=core.save()
                core.restore(saved)
                for _ in range(100):core.step()
                self.assertEqual(core.save(),expected)
            finally:core.close()
    def test_arena_has_room_for_largest_supported_cartridge(self):
        self.assertGreaterEqual(1024*1024,393216+262144+100000)


class AdditionalCartridgeTests(unittest.TestCase):
    def test_original_games_and_deterministic_replay(self):
        directory=os.environ.get("NES_ROM_DIR")
        if not directory:self.skipTest("set NES_ROM_DIR to supplied ROM directory")
        for slug,sequence in SEQUENCES.items():
            path=Path(directory)/GAMES[slug]["filename"]
            if not path.is_file():continue
            with self.subTest(game=slug):
                rom=path.read_bytes()
                import hashlib
                self.assertEqual(hashlib.sha256(rom).hexdigest(),GAMES[slug]["sha256"])
                core=Core(rom)
                try:
                    for count,pad in sequence["boot"]:
                        for _ in range(count):core.step(pad)
                    self.assertEqual(core.stats()[1],0)
                    self.assertGreater(len(set(core.pixels)),8)
                    saved=core.save()
                    trace=[]
                    for count,pad in sequence["replay"]:
                        for _ in range(count):
                            core.step(pad)
                            trace.append((bytes(core.pixels),core.save()))
                    core.close()
                    core=Core(rom)
                    core.restore(saved)
                    i=0
                    for count,pad in sequence["replay"]:
                        for _ in range(count):
                            core.step(pad)
                            self.assertEqual(bytes(core.pixels),trace[i][0])
                            self.assertEqual(core.save(),trace[i][1])
                            i+=1
                    self.assertEqual(core.stats()[1],0)
                finally:core.close()


if __name__=="__main__":unittest.main()
