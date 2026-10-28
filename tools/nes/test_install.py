"""Safe native-module installation; all volumes here are temporary directories."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import install


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.app, self.mount = self.root / "source", self.root / "BADGER"
        self.app.mkdir(); self.mount.mkdir(); (self.mount / "apps").mkdir()
        (self.mount / "main.py").write_text("unchanged startup")
        (self.mount / "apps/other").mkdir()
        (self.mount / "apps/other/keep.txt").write_text("user data")
        for name in install.FILES: (self.app / name).write_bytes(name.encode())
        self.rom = self.root / "provided.nes"; self.rom.write_bytes(b"test ROM")
        self.patch = mock.patch.object(install, "ROM_HASH", install.sha(self.rom)); self.patch.start()
        self.manifest()
    def manifest(self):
        (self.app / "_nes_core.build.json").write_text(json.dumps({
            "sha256":install.sha(self.app / "_nes_core.mpy"),
            "mpy_version":"6.3","cpu":"cortex-m33"}))
    def tearDown(self):
        self.patch.stop(); self.temp.cleanup()
    def run_install(self, write=True, replace=False):
        return install.install(self.mount,self.rom,write,replace,self.app)
    def test_native_mpy_and_rom_included_and_unrelated_untouched(self):
        dst=self.run_install()
        self.assertEqual((dst/"_nes_core.mpy").read_bytes(),b"_nes_core.mpy")
        self.assertEqual((dst/"game.nes").read_bytes(),self.rom.read_bytes())
        self.assertEqual((self.mount/"main.py").read_text(),"unchanged startup")
        self.assertEqual((self.mount/"apps/other/keep.txt").read_text(),"user data")
    def test_dry_run_changes_nothing(self):
        self.run_install(write=False)
        self.assertFalse((self.mount/"apps/zelda").exists())
        self.assertFalse(list(self.mount.glob(".zelda-*")))
    def test_modified_rom_is_rejected(self):
        self.rom.write_bytes(b"changed")
        with self.assertRaises(ValueError):self.run_install()
        self.assertFalse((self.mount/"apps/zelda").exists())
    def test_corrupt_mpy_is_rejected(self):
        (self.app/"_nes_core.mpy").write_bytes(b"changed")
        with self.assertRaises(ValueError):self.run_install()
    def test_existing_app_requires_explicit_replace(self):
        self.run_install()
        with self.assertRaises(FileExistsError):self.run_install()
    def test_replace_keeps_verified_previous_directory(self):
        dst=self.run_install()
        (dst/"my-old-file.txt").write_text("old")
        self.run_install(replace=True)
        backups=list((self.mount/".zelda-backups").glob("zelda-*"))
        self.assertEqual(len(backups),1)
        self.assertEqual((backups[0]/"my-old-file.txt").read_text(),"old")
    def test_copy_failure_preserves_installed_version(self):
        dst=self.run_install(); before=(dst/"__init__.py").read_bytes()
        with mock.patch.object(install.shutil,"copyfile",side_effect=OSError("USB disconnected")):
            with self.assertRaises(OSError):self.run_install(replace=True)
        self.assertEqual((dst/"__init__.py").read_bytes(),before)
        self.assertFalse(list(self.mount.glob(".zelda-stage-*")))
    def test_post_install_verification_failure_restores_old_version(self):
        dst=self.run_install()
        old=(dst/"game.py").read_bytes()
        (self.app/"game.py").write_bytes(b"new version")
        real_sha=install.sha
        def damaged_read(path):
            if Path(path)==dst/"game.py":
                return "bad checksum"
            return real_sha(path)
        with mock.patch.object(install,"sha",side_effect=damaged_read):
            with self.assertRaises(OSError):self.run_install(replace=True)
        self.assertEqual((dst/"game.py").read_bytes(),old)
        failed=list(self.mount.glob(".zelda-failed-*"))
        self.assertEqual(len(failed),1)
        self.assertEqual((failed[0]/"game.py").read_bytes(),b"new version")
    def test_mario_installs_separately_and_preserves_zelda(self):
        zelda=self.run_install()
        before=(zelda/"__init__.py").read_bytes()
        for old,new in (("game.py","mario_game.py"),("controls.py","mario_controls.py"),
                        ("checkpoint.py","mario_checkpoint.py")):
            (self.app/new).write_bytes((self.app/old).read_bytes())
        mario=install.install(self.mount,self.rom,True,False,self.app,
                              "mario",install.sha(self.rom),install.MARIO_FILES)
        self.assertEqual(mario,(self.mount/"apps/mario").resolve())
        self.assertTrue((mario/"mario_game.py").is_file())
        self.assertEqual((zelda/"__init__.py").read_bytes(),before)
    def test_invalid_app_slug_cannot_escape_apps(self):
        with self.assertRaises(ValueError):
            install.install(self.mount,self.rom,True,False,self.app,slug="../other")
    def test_non_badge_mount_is_rejected(self):
        (self.mount/"main.py").unlink()
        with self.assertRaises(ValueError):self.run_install()


if __name__ == "__main__":
    unittest.main()
