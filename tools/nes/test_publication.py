"""Publication safeguards, including Git-index vs working-file differences."""
import importlib.util
import json
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("publication_audit", ROOT / "tools/publication_audit.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class PublicationPolicyTests(unittest.TestCase):
    def test_rom_extensions_are_case_insensitive(self):
        for name in ("game.nes", "GAME.NES", "game.FdS", "x.unif", "x.smc", "x.gba"):
            with self.subTest(name=name):
                self.assertTrue(audit.policy_issues(name, b"placeholder"))

    def test_renamed_cartridge_is_rejected_by_signature(self):
        for signature in (b"NES\x1a", b"UNIF", b"FDS\x1a"):
            self.assertTrue(audit.policy_issues("notes.txt", signature + bytes(16)))

    def test_private_artifact_paths_are_rejected(self):
        for name in ("state/data.json", "backups/app.txt", "secrets.py", "wifi_networks.json",
                     "autosave.0", "tools/nes/build-deploy/report.json", ".env.local",
                     "tools/nes/.mpy_ld_cache-armv7m/archive", "source.zip"):
            with self.subTest(name=name):
                self.assertTrue(audit.policy_issues(name, b"placeholder"))

    def test_source_can_discuss_roms_without_bundling_one(self):
        source = b'def header(): return b"NES\\x1a"\n# Users supply their own ROM.\n'
        self.assertEqual(audit.policy_issues("tools/test_program.py", source), [])

    def test_private_paths_tokens_and_key_material_are_flagged(self):
        samples = [b"/" + b"Users/anyone/Documents/file", b"/" + b"home/anyone/file",
                   b"/tmp/" + b"badge-work/file", b"gh" + b"p_" + b"X" * 36,
                   b"-----BEGIN " + b"RSA PRIVATE KEY-----", b"serial=" + b"a1b2" * 4]
        for data in samples:
            with self.subTest(data=data[:12]):
                self.assertTrue(audit.policy_issues("notes.md", data))

    def test_unrelated_executable_and_screenshot_are_rejected(self):
        for data in (b"\x7fELF" + bytes(12), b"MZ" + bytes(12)):
            self.assertTrue(audit.policy_issues("vendor/tool", data))
        self.assertTrue(audit.policy_issues("screenshots/game.png", b"\x89PNG\r\n\x1a\n" + bytes(20)))

    def test_empty_tree_cannot_pass(self):
        self.assertTrue(audit.audit_project({}))


class PackagePublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (ROOT / ".git").exists() or not shutil.which("git"):
            raise unittest.SkipTest("Publication checks require a Git checkout, not a plain source ZIP")
        cls.files = audit.working_tree(ROOT)

    def test_complete_working_project_passes(self):
        self.assertEqual(audit.audit_project(self.files), [])

    def test_source_change_without_rebuild_fails(self):
        files = dict(self.files)
        files["tools/nes/engine.cpp"] += b"\n// hypothetical source change\n"
        self.assertTrue(any("source hash mismatch" in x for x in audit.audit_project(files)))

    def test_native_binary_tampering_fails(self):
        files = dict(self.files)
        files["badge/apps/zelda/_nes_core.mpy"] += b"extra"
        self.assertTrue(any("binary/manifest mismatch" in x for x in audit.audit_project(files)))

    def test_wrong_native_target_fails(self):
        files = dict(self.files)
        name = "badge/apps/zelda/_nes_core.build.json"
        manifest = json.loads(files[name])
        manifest["cpu"] = "another-cpu"
        files[name] = json.dumps(manifest).encode()
        self.assertTrue(any("unexpected native target" in x for x in audit.audit_project(files)))

    def test_missing_license_fails(self):
        files = dict(self.files)
        del files["LICENSES/LGPL-2.1.txt"]
        self.assertTrue(any("Missing license" in x for x in audit.audit_project(files)))

    def test_broken_standalone_documentation_link_fails(self):
        files = dict(self.files)
        files["docs/missing-link.md"] = b"[setup](not-present.md)\n"
        self.assertTrue(any("broken local link" in x for x in audit.audit_project(files)))


class GitIndexAuditTests(unittest.TestCase):
    def setUp(self):
        if not shutil.which("git"):
            self.skipTest("Git is required for index-blob tests")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_staged_bad_blob_is_detected_even_if_working_file_is_clean(self):
        path = self.root / "notes.txt"
        path.write_bytes(b"NES\x1a" + bytes(16))
        self.git("add", "--", "notes.txt")
        path.write_text("clean working copy\n")
        indexed = audit.git_index(self.root)
        self.assertTrue(audit.policy_issues("notes.txt", indexed["notes.txt"]))
        self.assertEqual(audit.policy_issues("notes.txt", path.read_bytes()), [])

    def test_index_symlink_is_rejected_without_following_it(self):
        target = self.root / "target.txt"
        target.write_text("owned test file")
        (self.root / "link.txt").symlink_to(target)
        self.git("add", "--", "link.txt")
        with self.assertRaises(ValueError):
            audit.git_index(self.root)


if __name__ == "__main__":
    unittest.main()
