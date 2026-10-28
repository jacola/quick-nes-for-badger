"""Frontend, recovery, controls and actual-C-core regression tests (no badge I/O)."""
import binascii
import hashlib
import importlib.util
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "badge" / "apps" / "zelda"
sys.path.insert(0, str(APP))
from checkpoint import Checkpoints, CheckpointError, HEADER_SIZE, PREFIX, MAGIC, ABI
from controls import Controls, A, B, SELECT, START, UP, DOWN, LEFT, RIGHT
from host import Core

HASH = hashlib.sha256(b"test cartridge").digest()


class FakeCore:
    def __init__(self):
        self.frame = 1
        self.payload = b"machine registers and RAM" * 100
    def stats(self):
        return self.frame, 0, 0
    def save(self, target):
        data = struct.pack("<I", self.frame) + self.payload
        target[:len(data)] = data
        return len(data)
    def restore(self, data):
        if data[4:7] == b"BAD":
            raise RuntimeError("Bad machine state")
        self.frame = struct.unpack_from("<I", data)[0]
        self.payload = data[4:]


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = self.temp.name + "/zelda"
        self.store = Checkpoints(HASH, self.path)
        self.core = FakeCore()
    def tearDown(self):
        self.temp.cleanup()
    def another(self, digest=HASH):
        return Checkpoints(digest, self.path)
    def save(self, frame):
        self.core.frame = frame
        self.assertTrue(self.store.save(self.core), self.store.last_error)
    def test_missing_is_fresh(self):
        self.assertFalse(self.store.restore(self.core))
        self.assertTrue(self.store.writable)
    def test_full_state_after_restart(self):
        self.save(200)
        c = FakeCore()
        c.payload = b"different initial state"
        self.assertTrue(self.another().restore(c))
        self.assertEqual((c.frame, c.payload), (self.core.frame, self.core.payload))
    def test_two_generations_and_no_duplicate_writes(self):
        self.save(100)
        self.save(200)
        self.assertEqual(self.store.generation, 2)
        with mock.patch("checkpoint.os.rename", side_effect=AssertionError("unnecessary write")):
            self.assertTrue(self.store.save(self.core))
        self.assertTrue(Path(self.store._path(0)).exists())
        self.assertTrue(Path(self.store._path(1)).exists())
    def test_corrupt_latest_recovers_previous(self):
        self.save(100)
        self.save(200)
        p = Path(self.store._path(0))
        data = bytearray(p.read_bytes()); data[-3] ^= 128; p.write_bytes(data)
        store = self.another()
        self.assertTrue(store.restore(self.core))
        self.assertEqual(self.core.frame, 100)
        self.assertTrue(store.recovered)
    def test_truncated_latest_recovers_previous(self):
        self.save(100); self.save(200)
        p = Path(self.store._path(0)); data = p.read_bytes()
        for cut in (0, 1, HEADER_SIZE - 1, HEADER_SIZE, len(data) - 1):
            with self.subTest(cut=cut):
                p.write_bytes(data[:cut])
                self.another().restore(self.core)
                self.assertEqual(self.core.frame, 100)
    def test_failed_rename_keeps_prior_state_and_retry_works(self):
        self.save(100); previous = Path(self.store._path(1)).read_bytes()
        self.core.frame = 200
        with mock.patch("checkpoint.os.rename", side_effect=OSError("interrupted rename")):
            self.assertFalse(self.store.save(self.core))
        self.assertEqual(Path(self.store._path(1)).read_bytes(), previous)
        self.assertEqual(self.store.last_frame, 100)
        other = self.another(); other.restore(self.core)
        self.assertEqual(self.core.frame, 100)
        self.save(200)
        self.assertIsNone(self.store.last_error)
    def test_uncommitted_temp_file_is_ignored(self):
        self.save(100)
        Path(self.store._path(0) + ".tmp").write_bytes(b"partial new state")
        self.another().restore(self.core)
        self.assertEqual(self.core.frame, 100)
    def test_both_corrupt_are_preserved(self):
        self.save(100); self.save(200)
        for i in (0, 1): Path(self.store._path(i)).write_bytes(b"broken")
        other = self.another()
        with self.assertRaises(CheckpointError): other.restore(self.core)
        self.assertFalse(other.save(self.core))
        for i in (0, 1): self.assertEqual(Path(self.store._path(i)).read_bytes(), b"broken")
    def test_wrong_rom_never_overwrites(self):
        self.save(100)
        p = Path(self.store._path(1)); before = p.read_bytes()
        other = self.another(hashlib.sha256(b"another cartridge").digest())
        with self.assertRaises(CheckpointError): other.restore(self.core)
        self.assertFalse(other.save(self.core))
        self.assertEqual(p.read_bytes(), before)
    def test_header_corruption_is_detected(self):
        self.save(100); p = Path(self.store._path(1))
        data = bytearray(p.read_bytes()); data[15] ^= 1; p.write_bytes(data)
        with self.assertRaises(CheckpointError): self.another().restore(self.core)
    def test_bounded_file_size(self):
        self.save(100); p = Path(self.store._path(1))
        p.write_bytes(p.read_bytes() + b"x" * 10000)
        with self.assertRaises(CheckpointError): self.another().restore(self.core)
    def test_fallback_if_core_rejects_latest(self):
        self.save(100)
        self.core.payload = b"BAD" + b"x" * 100
        self.save(200)
        other = self.another(); self.assertTrue(other.restore(self.core))
        self.assertEqual(self.core.frame, 100)
        self.assertTrue(other.recovered)
    def test_decoder_only_firmware_saves_raw_state(self):
        import types
        decoder_only = types.SimpleNamespace(DeflateIO=object)
        with mock.patch("checkpoint.deflate", decoder_only):
            self.save(1234)
            saved = Path(self.store._path(1)).read_bytes()
            self.assertEqual(struct.unpack_from(PREFIX, saved)[4], 0)
            restored = FakeCore()
            self.assertTrue(self.another().restore(restored))
            self.assertEqual(restored.frame, 1234)
            self.assertEqual(restored.payload, self.core.payload)
    def test_incompressible_state(self):
        self.core.payload = os.urandom(20000)
        self.save(1234)
        other = FakeCore(); self.another().restore(other)
        self.assertEqual(other.payload, self.core.payload)
    def test_reentrant_save_is_not_attempted(self):
        self.store.saving = True
        self.assertFalse(self.store.save(self.core))
        self.assertFalse(Path(self.path).exists())
    def test_invalid_compressed_stream_falls_back(self):
        self.save(10)
        data = b"not zlib"
        prefix = struct.pack(PREFIX, MAGIC, ABI, 2, 20, 1, 200, len(data), HASH)
        crc = binascii.crc32(data, binascii.crc32(prefix)) & 0xffffffff
        Path(self.store._path(0)).write_bytes(prefix + struct.pack("<I", crc) + data)
        self.assertTrue(self.another().restore(self.core))
        self.assertEqual(self.core.frame, 10)


class Badge:
    def __init__(self, held=(), pressed=()):
        self.h, self.p = held, pressed
    def held(self, key): return key in self.h
    def pressed(self, key): return key in self.p


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.c = Controls(("up", "down", "left", "right", "a", "b", "menu"))
    def get(self, *held): return self.c.sample(Badge(held))
    def test_directions_and_actions(self):
        for key, bit in (("up",UP),("down",DOWN),("left",LEFT),("right",RIGHT),("a",A),("b",B)):
            with self.subTest(key=key): self.assertEqual(self.get(key), bit)
    def test_simultaneous_movement_and_sword(self):
        self.assertEqual(self.get("up", "right", "a"), UP | RIGHT | A)
    def test_command_chords_suppress_dpad_states(self):
        self.assertEqual(self.get("up", "down", "left", "right"), START)
        self.assertTrue(self.c.save_requested)
    def test_new_press_counts_even_before_held(self):
        self.assertEqual(self.c.sample(Badge(pressed=("a",))), A)
    def test_menu_short_tap_is_visible_for_four_nes_frames(self):
        self.assertEqual(self.get("menu"), 0)
        self.assertEqual(self.get("menu"), 0)
        for _ in range(4):self.assertEqual(self.get(), START)
        self.assertEqual(self.get(), 0)
    def test_physical_up_down_start_is_held_without_bounce(self):
        self.assertEqual(self.get("up","down"), START)
        for _ in range(12):self.assertEqual(self.get("up","down"), START)
        self.assertEqual(self.get("up"), START)
        self.assertEqual(self.get("up","down"), START)
        self.assertEqual(self.get(), 0)
        self.assertEqual(self.get("up","down"), START)
    def test_short_up_down_tap_is_stretched(self):
        self.assertEqual(self.get("up","down"), START)
        for _ in range(3):self.assertEqual(self.get(), START)
        self.assertEqual(self.get(), 0)
    def test_touch_only_menu_and_back_are_recognized(self):
        class TouchBadge(Badge):
            touches=()
            def touched(self,key):return key in self.touches
        b=TouchBadge()
        b.touches=("menu",)
        self.assertEqual(self.c.sample(b),0)
        b.touches=()
        self.assertEqual(self.c.sample(b),START)
        self.c=Controls(("up","down","left","right","a","b","menu"))
        b.touches=("menu","b")
        self.assertEqual(self.c.sample(b),SELECT)
        b.touches=()
        self.assertEqual(self.c.sample(b),0)
    def test_manual_save_fires_once_and_requires_both_released(self):
        self.assertEqual(self.get("left"), LEFT)
        self.assertFalse(self.c.save_requested)
        self.assertEqual(self.get("left", "right"), 0)
        self.assertTrue(self.c.save_requested)
        for _ in range(10):
            self.assertEqual(self.get("left", "right"), 0)
            self.assertFalse(self.c.save_requested)
        self.get("left")
        self.get("left", "right")
        self.assertFalse(self.c.save_requested)
        self.get()
        self.get("left", "right")
        self.assertTrue(self.c.save_requested)
    def test_manual_save_chord_does_not_remove_other_nes_actions(self):
        self.assertEqual(self.get("left", "right", "a"), A)
        self.assertTrue(self.c.save_requested)
    def test_select_chord_does_not_press_start_or_b(self):
        self.assertEqual(self.get("menu"), 0)
        self.assertEqual(self.get("menu", "b"), SELECT)
        self.assertEqual(self.get("b"), 0)
        self.assertEqual(self.get(), 0)
        self.assertEqual(self.get("b"), B)


def tiny_rom(battery=False):
    # Original test program, not commercial game data. Increment RAM forever.
    prg = bytearray([0xea]) * 16384
    prg[:8] = bytes([0x78, 0xe6, 0x00, 0x4c, 0x01, 0x80, 0x40, 0x40])
    prg[-6:] = struct.pack("<3H", 0x8006, 0x8000, 0x8007)
    return b"NES\x1a" + bytes([1, 0, 2 if battery else 0, 0]) + bytes(8) + prg


class NativeCoreTests(unittest.TestCase):
    def setUp(self): self.core = Core(tiny_rom())
    def tearDown(self): self.core.close()
    def test_homemade_nrom_and_snapshot(self):
        for _ in range(50): self.core.step()
        self.assertEqual(self.core.stats(), (50, 0))
        state = self.core.save()
        for _ in range(100): self.core.step()
        after = self.core.save()
        self.core.restore(state)
        for _ in range(100): self.core.step()
        self.assertEqual(after, self.core.save())
    def test_split_render_matches_combined_and_present_does_not_advance(self):
        for _ in range(10): self.core.step()
        start=self.core.save()
        for _ in range(30): self.core.step(1)
        expected_pixels=bytes(self.core.pixels)
        expected_state=self.core.save()
        self.core.restore(start)
        for _ in range(30):
            self.core.advance(1)
            self.core.present()
        self.assertEqual(bytes(self.core.pixels),expected_pixels)
        self.assertEqual(self.core.save(),expected_state)
        self.core.present()
        self.assertEqual(self.core.save(),expected_state)
    def test_invalid_state_does_not_change_vm(self):
        for _ in range(4): self.core.step()
        state = self.core.save()
        for data in (b"", state[:7], state[:-1], state + b"extra", b"x" * 32769):
            with self.subTest(length=len(data)):
                with self.assertRaises(RuntimeError): self.core.restore(data)
                self.assertEqual(self.core.save(), state)
    def test_bad_rom_is_rejected_before_reset(self):
        for _ in range(3): self.core.step()
        before = self.core.save()
        rom = tiny_rom()
        for bad in (b"", b"bad", rom[:-1], rom + b"x", rom[:4] + bytes(12)):
            err = self.core.lib.bnes_open(bad, len(bad), self.core.arena, len(self.core.arena))
            self.assertIsNotNone(err)
            self.assertEqual(before, self.core.save())
    def test_misaligned_arena_is_rejected_before_reset(self):
        import ctypes
        before=self.core.save()
        rom=tiny_rom()
        shifted=ctypes.addressof(self.core.arena)+4
        err=self.core.lib.bnes_open(rom,len(rom),shifted,len(self.core.arena))
        self.assertIsNotNone(err)
        self.assertEqual(self.core.save(),before)
    def test_unsupported_header_variants(self):
        for byte_index, value in ((4,0),(4,255),(6,4),(6,8),(6,0x50),(7,8),(9,1)):
            data = bytearray(tiny_rom()); data[byte_index] = value
            err = self.core.lib.bnes_open(bytes(data), len(data), self.core.arena, len(self.core.arena))
            self.assertIsNotNone(err)
    def test_state_length_corruption_rejected(self):
        state = bytearray(self.core.save())
        for size in (0,1,0x7fffffff,0xffffffff):
            changed = bytearray(state);struct.pack_into("<I",changed,12,size)
            with self.assertRaises(RuntimeError): self.core.restore(bytes(changed))
    def test_guard_borders_are_not_overwritten(self):
        self.core.pixels[:] = b"\x55" * len(self.core.pixels)
        self.core.step()
        for y in range(240):
            self.assertEqual(self.core.pixels[y*640:y*640+64], b"\x55"*64)
            self.assertEqual(self.core.pixels[y*640+576:(y+1)*640], b"\x55"*64)


ROM_PATH = os.environ.get("ZELDA_ROM")


@unittest.skipUnless(ROM_PATH and Path(ROM_PATH).is_file(), "set ZELDA_ROM to the supplied ROM")
class ZeldaIntegrationTests(unittest.TestCase):
    def setUp(self): self.core = Core(Path(ROM_PATH).read_bytes())
    def tearDown(self): self.core.close()
    def wait(self,n,pad=0):
        for _ in range(n): self.core.step(pad)
    def press(self,pad):
        self.wait(2,pad);self.wait(30)
    def test_original_title_and_file_selection(self):
        self.wait(600)
        self.assertEqual(self.core.stats(), (600,0))
        # Matches the ARM .mpy execution and the original QuickNES frontend.
        self.assertEqual(binascii.crc32(self.core.pixels), 0xc2d244c6)
        self.press(START)
        self.assertNotEqual(binascii.crc32(self.core.pixels), 0xc2d244c6)
    def test_gameplay_checkpoint_replays_pixel_and_state_exactly(self):
        self.wait(600); self.press(START); self.press(START); self.press(A)
        for _ in range(3): self.press(SELECT)
        self.press(START); self.press(START); self.wait(120)
        self.assertEqual(self.core.stats(), (976,0))
        with tempfile.TemporaryDirectory() as path:
            digest = hashlib.sha256(Path(ROM_PATH).read_bytes()).digest()
            store = Checkpoints(digest, path + "/zelda")
            self.assertTrue(store.save(self.core))
            self.wait(110,UP); self.wait(100)
            pixels, state = bytes(self.core.pixels), self.core.save()
            # Recreate the emulator, as after a real reset/power cycle.
            self.core.close(); self.core = Core(Path(ROM_PATH).read_bytes())
            self.assertTrue(Checkpoints(digest,path + "/zelda").restore(self.core))
            self.wait(110,UP);self.wait(100)
            self.assertEqual(bytes(self.core.pixels), pixels)
            self.assertEqual(self.core.save(), state)
            self.assertEqual(self.core.stats()[1], 0)


if __name__ == "__main__":
    unittest.main()
