"""Exercise frame pacing/manual checkpoints with the actual host-built core."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "badge/apps/zelda"))
import game
from host import Core
from test_zelda import tiny_rom, Badge


class Clock:
    def __init__(self): self.now = 0
    def ticks_us(self): return self.now % (1 << 30)
    def ticks_ms(self): return (self.now // 1000) % (1 << 30)
    def ticks_add(self, a, b): return (a + b) % (1 << 30)
    def ticks_diff(self, a, b): return ((a - b + (1 << 29)) % (1 << 30)) - (1 << 29)
    def sleep_us(self, value): self.now += value


class Backend:
    ABI, ARENA_SIZE = 1, 1024 * 1024
    def __init__(self): self.vm = None; self.inputs = []
    def load(self, rom, arena):
        self.vm = Core(rom)
    def step(self, target, p1, p2):
        self.inputs.append((p1,p2))
        self.vm.step(p1,p2)
        target[:] = self.vm.pixels
    def stats(self): return self.vm.stats() + (0,)
    def save(self, target): return self.vm.save(target)
    def restore(self, data): return self.vm.restore(data)
    def close(self):
        if self.vm: self.vm.close(); self.vm = None


class Screen:
    def __init__(self): self.raw = bytearray(153600)


class Watchdog:
    def __init__(self): self.feeds = 0
    def feed(self): self.feeds += 1


class FrontendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rom = Path(self.tmp.name) / "game.nes"
        self.data = tiny_rom()
        self.rom.write_bytes(self.data)
        self.clock, self.backend = Clock(), Backend()
        self.badge, self.screen, self.wdt = Badge(), Screen(), Watchdog()
        self.patches = [
            mock.patch.object(game, "time", self.clock),
            mock.patch.object(game, "ROM_SIZE", len(self.data)),
            mock.patch.object(game, "ROM_SHA256", hashlib.sha256(self.data).hexdigest()),
        ]
        for patch in self.patches: patch.start()
    def tearDown(self):
        self.backend.close()
        for patch in reversed(self.patches): patch.stop()
        self.tmp.cleanup()
    def create(self):
        return game.Game(self.backend,self.badge,self.screen,("u","d","l","r","a","b","m"),
                         self.wdt,str(self.rom),self.tmp.name + "/state")
    def test_initialization_and_frame_pacing(self):
        g = self.create()
        self.assertFalse(g.resumed)
        for _ in range(10): g.update()
        self.assertEqual(self.backend.stats()[0],10)
        self.assertEqual(self.clock.now,9*game.FRAME_US)
        self.assertGreater(self.wdt.feeds,10)
    def test_no_periodic_or_exit_writes(self):
        g = self.create()
        with mock.patch.object(g.checkpoints,"save",side_effect=AssertionError("implicit save")):
            for _ in range(600):g.update()
            self.assertTrue(g.close())
        self.assertEqual(g.checkpoints.last_frame,-1)
        self.assertFalse(Path(self.tmp.name,"state").exists())
    def test_manual_save_survives_restart_without_saving_later_progress(self):
        g = self.create()
        for _ in range(7):g.update()
        self.badge.h=("l","r")
        g.update()
        saved=g.checkpoints.last_frame
        self.assertEqual(saved,8)
        generation=g.checkpoints.generation
        for _ in range(130):g.update()
        self.assertEqual(g.checkpoints.generation,generation)
        self.badge.h=()
        self.assertTrue(g.close())
        self.assertTrue(g.closed)
        self.assertTrue(g.close())
        restored=self.create()
        self.assertTrue(restored.resumed)
        self.assertEqual(self.backend.stats()[0],saved)
    def test_late_updates_and_saves_after_close_are_harmless(self):
        g=self.create();g.update()
        self.assertTrue(g.close())
        calls=len(self.backend.inputs)
        g.update()
        self.assertEqual(len(self.backend.inputs),calls)
        self.assertTrue(g.save())
    def test_exit_callback_neither_writes_nor_destroys_running_vm(self):
        import types
        source=(ROOT/"badge/apps/zelda/__init__.py").read_text()
        self.badge.default_clear=None
        self.badge.mode=lambda mode=None:3
        self.screen.clear=lambda:None
        self.screen.text=lambda *a:None
        self.screen.rectangle=lambda *a:None
        self.screen.measure_text=lambda text:(len(text)*4,8)
        errors=[]
        scope={"is_dir":lambda p:False,"badge":self.badge,"screen":self.screen,
               "HIRES":1,"font":types.SimpleNamespace(nope=None),
               "color":types.SimpleNamespace(rgb=lambda *a:a),
               "display":types.SimpleNamespace(update=lambda:None),
               "rect":lambda *a:a,"BUTTON_UP":"u","BUTTON_DOWN":"d",
               "BUTTON_LEFT":"l","BUTTON_RIGHT":"r","BUTTON_SELECT":"a",
               "BUTTON_BACK":"b","BUTTON_MENU":"m","BUTTON_HOME":"h"}
        def loop(update):
            for _ in range(6):
                update()
                scope["on_exit"]()
                scope["on_exit"]()
                self.assertFalse(scope["game"].closed)
                self.assertIsNotNone(self.backend.vm)
        scope["run"]=loop
        original_store=game.Checkpoints
        def store(digest,directory="/state/zelda"):
            return original_store(digest,self.tmp.name+"/state")
        import os
        cwd=os.getcwd()
        paths=list(sys.path)
        try:
            os.chdir(self.tmp.name)
            with mock.patch.dict(sys.modules,{"_nes_core":self.backend,"time":self.clock,
                    "machine":types.SimpleNamespace(WDT=lambda **kw:self.wdt)}), \
                 mock.patch.object(game,"Checkpoints",side_effect=store), \
                 mock.patch.object(sys,"print_exception",side_effect=errors.append,create=True):
                exec(source,scope)
            self.assertFalse(errors)
            self.assertTrue(scope["game"].closed)
            self.assertEqual(scope["game"].checkpoints.last_frame,-1)
            self.assertFalse(Path(self.tmp.name,"state").exists())
        finally:
            os.chdir(cwd)
            sys.path[:]=paths
    def test_failed_manual_save_keeps_vm_live_for_explicit_retry(self):
        g=self.create()
        self.badge.h=("l","r")
        with mock.patch.object(g.checkpoints,"save",return_value=False) as save:
            g.update()
            self.assertFalse(g.save_ok)
            self.assertFalse(g.closed)
            self.assertIsNotNone(self.backend.vm)
            for _ in range(10):g.update()
            self.assertEqual(save.call_count,1)
        self.badge.h=();g.update()
        self.badge.h=("l","r");g.update()
        self.assertTrue(g.save_ok)
        self.assertEqual(g.checkpoints.generation,1)
    def test_async_pipeline_fences_screen_and_saves(self):
        events=[]
        class Display:
            enabled=False
            def set_async(self,enabled):
                self.enabled=enabled
                events.append(("async",enabled))
        display=Display()
        def advance(p1,p2):
            events.append("advance")
            self.backend.vm.advance(p1,p2)
        def present(target):
            self.assertFalse(display.enabled)
            events.append("present")
            self.backend.vm.present()
            target[:]=self.backend.vm.pixels
        self.backend.advance=advance
        self.backend.present=present
        g=game.Game(self.backend,self.badge,self.screen,("u","d","l","r","a","b","m"),
                    self.wdt,str(self.rom),self.tmp.name+"/state",display=display)
        events.clear()
        g.update()
        self.assertEqual(events,["advance",("async",False),"present",("async",True)])
        self.badge.h=("l","r")
        def save(core):
            self.assertFalse(display.enabled)
            events.append("save")
            return True
        events.clear()
        with mock.patch.object(g.checkpoints,"save",side_effect=save):
            g.update()
        self.assertLess(events.index("present"),events.index("save"))
        self.assertEqual(events[-1],("async",True))
        g.close()
        self.assertFalse(display.enabled)
    def test_async_pipeline_fences_after_emulation_error(self):
        class Display:
            enabled=False
            def set_async(self,enabled):self.enabled=enabled
        display=Display()
        self.backend.advance=mock.Mock(side_effect=RuntimeError("test failure"))
        self.backend.present=mock.Mock()
        g=game.Game(self.backend,self.badge,self.screen,("u","d","l","r","a","b","m"),
                    self.wdt,str(self.rom),self.tmp.name+"/state",display=display)
        display.enabled=True
        with self.assertRaises(RuntimeError):g.update()
        self.assertFalse(display.enabled)
        self.backend.present.assert_not_called()
    def test_invalid_rom_never_runs(self):
        changed=bytearray(self.data);changed[30]^=1;self.rom.write_bytes(changed)
        with self.assertRaises(ValueError):self.create()
        self.assertIsNone(self.backend.vm)
    def test_wrong_rom_size_never_runs(self):
        self.rom.write_bytes(self.data+b"extra")
        with self.assertRaises(ValueError):self.create()
        self.assertIsNone(self.backend.vm)
    def test_wrong_native_abi_is_rejected(self):
        self.backend.ABI=99
        with self.assertRaises(ValueError):self.create()
        self.assertIsNone(self.backend.vm)
    def test_long_delay_does_not_skip_game_frames(self):
        g=self.create();g.update();self.clock.now+=10_000_000;g.update()
        self.assertEqual(self.backend.stats()[0],2)
        self.assertEqual(g.frame_due,self.clock.ticks_us())
    def test_microsecond_wrap_does_not_stall(self):
        self.clock.now=(1<<30)-5000
        g=self.create();g.update();g.update()
        self.assertEqual(self.backend.stats()[0],2)
        self.assertEqual(self.clock.now,(1<<30)-5000+game.FRAME_US)
    def test_orientation_abstracted_logical_actions(self):
        g=self.create()
        self.badge.h=("r","a")
        g.update()
        self.assertEqual(self.backend.inputs[-1],(0x81,0))


if __name__ == "__main__":
    unittest.main()
