"""Read-only inspection and profile matching; all data is generated in tests."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import inspect_rom


class InspectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "own-cartridge.nes"
        self.data = b"NES\x1a" + bytes([1, 0, 0, 0]) + bytes(8) + bytes(16384)
        self.path.write_bytes(self.data)

    def test_hash_metadata_and_file_unchanged(self):
        before = self.path.stat().st_mtime_ns
        result = inspect_rom.inspect_rom(self.path)
        self.assertEqual(result["sha256"], hashlib.sha256(self.data).hexdigest())
        self.assertEqual(result["bytes"], len(self.data))
        self.assertEqual(result["mapper"], 0)
        self.assertEqual(result["header"], "iNES")
        self.assertTrue(result["mapper_implemented"])
        self.assertIsNone(result["matching_profile"])
        self.assertEqual(self.path.read_bytes(), self.data)
        self.assertEqual(self.path.stat().st_mtime_ns, before)

    def test_only_exact_profile_size_and_hash_match(self):
        profiles = {"test": {"sha256": hashlib.sha256(self.data).hexdigest(), "size": len(self.data)}}
        with mock.patch.object(inspect_rom, "GAMES", profiles):
            self.assertEqual(inspect_rom.inspect_rom(self.path)["matching_profile"], "test")
            profiles["test"]["size"] += 1
            self.assertIsNone(inspect_rom.inspect_rom(self.path)["matching_profile"])

    def test_nes2_extended_mapper_is_reported_not_normalized(self):
        data = bytearray(self.data)
        data[6], data[7], data[8] = 0x40, 0x28, 1
        self.path.write_bytes(data)
        result = inspect_rom.inspect_rom(self.path)
        self.assertEqual(result["header"], "NES 2.0")
        self.assertEqual(result["mapper"], 0x124)
        self.assertFalse(result["mapper_implemented"])
        self.assertEqual(self.path.read_bytes(), bytes(data))

    def test_bad_header_or_archive_is_rejected(self):
        for data in (b"", b"NES\x1a", b"PK" + bytes(32), b"<html>not a cartridge</html>"):
            self.path.write_bytes(data)
            with self.assertRaises(ValueError):
                inspect_rom.inspect_rom(self.path)

    def test_symlink_and_directory_are_rejected(self):
        link = self.path.with_name("link.nes")
        link.symlink_to(self.path)
        for path in (link, self.path.parent):
            with self.assertRaises(ValueError):
                inspect_rom.inspect_rom(path)

    def test_inspection_limit_is_enforced(self):
        with mock.patch.object(inspect_rom, "MAX_INSPECTION_BYTES", 16):
            with self.assertRaises(ValueError):
                inspect_rom.inspect_rom(self.path)


if __name__ == "__main__":
    unittest.main()
