"""Mario cartridge metadata, manual checkpoints and original-game regressions."""
import binascii
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "badge/apps/mario"
sys.path.insert(0,str(APP))
import mario_game
import mario_checkpoint
from mario_controls import Controls
from host import Core
from test_zelda import tiny_rom, Badge
from test_frontend import Backend, Screen, Watchdog, Clock


def synthetic_mario_cart():
    prg=tiny_rom()[16:]
    return mario_game.SOURCE_HEADER+prg+prg+bytes(8192)


class MarioMetadataTests(unittest.TestCase):
    def test_header_translation_never_changes_code_or_graphics(self):
        original=synthetic_mario_cart()
        translated=mario_game.core_rom(original)
        self.assertEqual(bytes(translated[16:]),original[16:])
        self.assertEqual(original[:16],mario_game.SOURCE_HEADER)
        self.assertEqual(bytes(translated[:8]),b"NES\x1a\x02\x01\x01\0")
        self.assertEqual(bytes(translated[8:16]),bytes(8))
    def test_unknown_metadata_is_not_silently_normalized(self):
        original=synthetic_mario_cart()
        for index in (4,5,6,7,8,9,10,11,12,13,14,15):
            changed=bytearray(original);changed[index]^=1
            with self.subTest(index=index):
                with self.assertRaises(ValueError):mario_game.core_rom(changed)
        with self.assertRaises(ValueError):mario_game.core_rom(original[:-1])
    def test_standalone_controls_match_zelda(self):
        self.assertEqual((APP/"mario_controls.py").read_text(),
                         (ROOT/"badge/apps/zelda/controls.py").read_text())
    def test_checkpoint_behavior_matches_except_game_identity(self):
        mario=(APP/"mario_checkpoint.py").read_text()
        mario=mario.replace("/state/mario","/state/zelda").replace("MARIOST1","ZELDAST1").replace("Mario checkpoint","Zelda checkpoint")
        self.assertEqual(mario,(ROOT/"badge/apps/zelda/checkpoint.py").read_text())


class MarioFrontendTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.rom=Path(self.tmp.name)/"game.nes"
        self.data=synthetic_mario_cart();self.rom.write_bytes(self.data)
        self.backend,self.badge,self.screen=Backend(),Badge(),Screen()
        self.clock,self.wdt=Clock(),Watchdog()
        self.patches=[mock.patch.object(mario_game,"time",self.clock),
            mock.patch.object(mario_game,"ROM_SHA256",hashlib.sha256(self.data).hexdigest())]
        for p in self.patches:p.start()
    def tearDown(self):
        self.backend.close()
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def game(self):
        return mario_game.Game(self.backend,self.badge,self.screen,("u","d","l","r","a","b","m"),
            self.wdt,str(self.rom),self.tmp.name+"/mario")
    def test_manual_save_no_autosave_and_resume(self):
        g=self.game()
        for _ in range(200):g.update()
        self.assertFalse(Path(self.tmp.name,"mario").exists())
        self.badge.h=("l","r");g.update()
        saved=g.checkpoints.last_frame
        for _ in range(120):g.update()
        self.assertEqual(g.checkpoints.generation,1)
        self.badge.h=();g.close()
        restored=self.game()
        self.assertTrue(restored.resumed)
        self.assertEqual(self.backend.stats()[0],saved)
    def test_rom_identity_rejected_before_loading(self):
        data=bytearray(self.data);data[100]^=1;self.rom.write_bytes(data)
        with self.assertRaises(ValueError):self.game()
        self.assertIsNone(self.backend.vm)
    def test_cannot_restore_another_games_checkpoint(self):
        from checkpoint import Checkpoints
        self.game().update()
        with tempfile.TemporaryDirectory() as path:
            store=Checkpoints(hashlib.sha256(self.data).digest(),path+"/shared")
            self.assertTrue(store.save(self.backend))
            other=mario_checkpoint.Checkpoints(hashlib.sha256(self.data).digest(),path+"/shared")
            with self.assertRaises(mario_checkpoint.CheckpointError):other.restore(self.backend)
            self.assertFalse(other.writable)


MARIO_ROM=os.environ.get("MARIO_ROM")


@unittest.skipUnless(MARIO_ROM and Path(MARIO_ROM).is_file(),"set MARIO_ROM to supplied World ROM")
class MarioIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.original=Path(MARIO_ROM).read_bytes()
        self.assertEqual(hashlib.sha256(self.original).hexdigest(),mario_game.ROM_SHA256)
        self.core=Core(mario_game.core_rom(self.original))
    def tearDown(self):self.core.close()
    def frames(self,n,pad=0):
        for _ in range(n):self.core.step(pad)
    def test_start_play_jump_and_restore_exactly(self):
        self.frames(120)
        title=bytes(self.core.pixels)
        self.assertGreater(len(set(self.core.pixels)),8)
        self.frames(2,8);self.frames(200)
        self.assertNotEqual(bytes(self.core.pixels),title)
        before=self.core.save()
        self.frames(90,0x82)
        self.frames(30,0x83)
        self.frames(50,0x82)
        after=self.core.save();pixels=bytes(self.core.pixels)
        self.core.close()
        self.core=Core(mario_game.core_rom(self.original))
        self.core.restore(before)
        self.frames(90,0x82);self.frames(30,0x83);self.frames(50,0x82)
        self.assertEqual(self.core.save(),after)
        self.assertEqual(bytes(self.core.pixels),pixels)
        self.assertEqual(self.core.stats()[1],0)
    def test_no_chr_ram_is_serialized(self):
        self.frames(120)
        self.assertEqual(len(self.core.save()),12792)


if __name__=="__main__":
    unittest.main()
