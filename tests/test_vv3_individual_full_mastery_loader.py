from __future__ import annotations

import hashlib
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace
from pathlib import Path

import vv3_individual_full_mastery as loader
import vv_fun_patcher


ROOT = Path(__file__).resolve().parents[1]
PARENTS = ROOT / "outputs" / "vv3-vv4-c257-determinism-a"


class VV3IndividualFullMasteryLoaderTests(unittest.TestCase):
    def _parent(self, mode: str) -> bytes:
        name = f"vv3_fullscreen_safe_candidate_{mode}.exe"
        return (PARENTS / name).read_bytes()

    def test_hidden_registration_is_not_public_catalog(self):
        hidden = vv_fun_patcher.load_hidden_vv3_individual_full_mastery_candidate()
        self.assertFalse(hidden.raw["enabled"])
        self.assertTrue(hidden.raw["catalog_hidden"])
        self.assertNotIn(hidden.id, {p.id for p in vv_fun_patcher.load_fun_patches()})

    def test_render_and_remove_exact_both_parents(self):
        expected = {
            "collection_progression": "BFFA0B5F54CD084138EABD68D3EA67F834CEFE915F7DB0000F81639F34BF90F1",
            "immediate_fixed": "6550141AFFAEF3F7965E89F1B32A3F4CB929E8E217778C5BBCB512AAC499E59C",
        }
        for mode, digest in expected.items():
            parent = self._parent(mode)
            candidate = loader.render_parent(parent, mode)
            self.assertEqual(len(candidate), 0xCF000)
            self.assertEqual(hashlib.sha256(candidate).hexdigest().upper(), digest)
            self.assertEqual(loader.remove_candidate(candidate, mode), parent)

    def test_pe_section_and_dispatcher_guards(self):
        candidate = loader.render_parent(self._parent("collection_progression"), "collection_progression")
        self.assertEqual(candidate[0x10E:0x110], bytes.fromhex("0900"))
        self.assertEqual(candidate[0x158:0x15C], bytes.fromhex("00302E00"))
        self.assertEqual(candidate[0x340:0x348], b".vv3im\0\0")
        self.assertEqual(candidate[0xA38C3:0xA38C8], loader.HOOK_AFTER)
        self.assertEqual(candidate[0xCE000:0xCE000 + 4], bytes.fromhex("83FB010F"))

    def test_patcher_append_resolver_uses_generated_page(self):
        feature = vv_fun_patcher.load_hidden_vv3_individual_full_mastery_candidate()
        layout = feature.raw["pe_append_transaction"]["layouts"]["collection_progression"]
        page = vv_fun_patcher._resolve_append_bytes(feature, layout)
        self.assertEqual(len(page), 0x1000)
        self.assertEqual(hashlib.sha256(page).hexdigest().upper(), loader._sha(page))
        work = bytearray(self._parent("collection_progression"))
        vv_fun_patcher._apply_pe_append_transactions(work, [feature], "collection_progression")
        self.assertEqual(len(work), 0xCF000)
        self.assertEqual(bytes(work[0xCE000:]), page)

    def test_unknown_or_corrupt_parent_fails_before_output(self):
        parent = bytearray(self._parent("collection_progression"))
        parent[0x200] ^= 1
        with self.assertRaises(vv_fun_patcher.PatcherError):
            loader.render_parent(bytes(parent), "collection_progression")
        with self.assertRaises(vv_fun_patcher.PatcherError):
            loader.render_parent(self._parent("collection_progression"), "experimental_expanded_256")

    def test_atomic_new_destination_and_collision(self):
        parent = PARENTS / "vv3_fullscreen_safe_candidate_collection_progression.exe"
        with tempfile.TemporaryDirectory() as td:
            destination = Path(td) / "candidate.exe"
            companion_source = ROOT / "data" / "candidates" / "VVFP VV3 Full Heal Candidate.dll"
            companion_restore = ROOT / "data" / "candidates" / "VVFP VV3 Full Mastery Candidate.dll"
            companion_destination = Path(td) / "VVFP VV3 Full Mastery Candidate.dll"
            loader.install_atomic(parent, destination, "collection_progression", companion_source=companion_source, companion_destination=companion_destination)
            self.assertTrue(destination.is_file())
            self.assertTrue(companion_destination.is_file())
            before = destination.read_bytes()
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader.install_atomic(parent, destination, "collection_progression", companion_source=companion_source, companion_destination=companion_destination)
            self.assertEqual(destination.read_bytes(), before)
            companion_before = companion_restore.read_bytes()
            loader.remove_atomic(destination, "collection_progression", companion_destination=companion_destination, companion_restore_source=companion_restore)
            self.assertEqual(destination.read_bytes(), parent.read_bytes())
            self.assertEqual(companion_destination.read_bytes(), companion_before)

    def test_companion_is_mandatory_and_wrong_existing_preimage_is_rejected(self):
        parent = PARENTS / "vv3_fullscreen_safe_candidate_collection_progression.exe"
        companion_source = ROOT / "data" / "candidates" / "VVFP VV3 Full Heal Candidate.dll"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader.install_atomic(parent, root / "candidate.exe", "collection_progression")
            destination = root / "candidate.exe"
            companion_destination = root / "VVFP VV3 Full Mastery Candidate.dll"
            destination.write_bytes(b"foreign")
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader.install_atomic(parent, destination, "collection_progression", companion_source=companion_source, companion_destination=companion_destination)
            self.assertEqual(destination.read_bytes(), b"foreign")
            self.assertFalse(companion_destination.exists())

    def test_publication_requires_one_destination_parent(self):
        parent = PARENTS / "vv3_fullscreen_safe_candidate_collection_progression.exe"
        candidate_dll = ROOT / "data" / "candidates" / "VVFP VV3 Full Heal Candidate.dll"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaises(vv_fun_patcher.PatcherError):
                loader.install_atomic(parent, root / "a" / "candidate.exe", "collection_progression", companion_source=candidate_dll, companion_destination=root / "b" / "VVFP VV3 Full Mastery Candidate.dll")

    def test_second_member_replace_failure_rolls_back_both_without_mixed_pair(self):
        parent = PARENTS / "vv3_fullscreen_safe_candidate_collection_progression.exe"
        candidate_dll = ROOT / "data" / "candidates" / "VVFP VV3 Full Heal Candidate.dll"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            destination = root / "candidate.exe"
            companion_destination = root / "VVFP VV3 Full Mastery Candidate.dll"
            real_replace = loader.os.replace
            calls = {"publish": 0}
            def fail_second(src, dst):
                if str(src).endswith(".stage") and Path(dst) in {destination, companion_destination}:
                    calls["publish"] += 1
                    if calls["publish"] == 2:
                        raise OSError("injected second-member replace failure")
                return real_replace(src, dst)
            with mock.patch.object(loader, "render_parent", return_value=b"CANDIDATE-EXE"):
                with mock.patch.object(loader.os, "replace", side_effect=fail_second):
                    with self.assertRaises(vv_fun_patcher.PatcherError):
                        loader.install_atomic(parent, destination, "collection_progression", companion_source=candidate_dll, companion_destination=companion_destination)
            self.assertFalse(destination.exists())
            self.assertFalse(companion_destination.exists())
            self.assertFalse(list(root.glob("*.stage")))

    def test_reparse_ancestor_rejected_before_any_write(self):
        parent = PARENTS / "vv3_fullscreen_safe_candidate_collection_progression.exe"
        candidate_dll = ROOT / "data" / "candidates" / "VVFP VV3 Full Heal Candidate.dll"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            real_lstat = loader.os.lstat
            def fake_lstat(path):
                st = real_lstat(path)
                if Path(path) == root:
                    return SimpleNamespace(st_mode=st.st_mode, st_file_attributes=0x400, st_dev=st.st_dev, st_ino=st.st_ino, st_size=st.st_size)
                return st
            with mock.patch.object(loader.os, "lstat", side_effect=fake_lstat):
                with self.assertRaises(vv_fun_patcher.PatcherError):
                    loader.install_atomic(parent, root / "candidate.exe", "collection_progression", companion_source=candidate_dll, companion_destination=root / "VVFP VV3 Full Mastery Candidate.dll")
            self.assertEqual(list(root.iterdir()), [])

    def test_unresolved_failure_retains_replayable_report(self):
        parent = PARENTS / "vv3_fullscreen_safe_candidate_collection_progression.exe"
        candidate_dll = ROOT / "data" / "candidates" / "VVFP VV3 Full Heal Candidate.dll"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            destination = root / "candidate.exe"
            companion_destination = root / "VVFP VV3 Full Mastery Candidate.dll"
            real_replace = loader.os.replace
            calls = {"publish": 0}
            def fail_second(src, dst):
                if str(src).endswith(".stage") and Path(dst) in {destination, companion_destination}:
                    calls["publish"] += 1
                    if calls["publish"] == 2:
                        raise OSError("injected second-member replace failure")
                return real_replace(src, dst)
            with mock.patch.object(loader, "render_parent", return_value=b"CANDIDATE-EXE"):
                with mock.patch.object(loader, "_restore_member", return_value=False):
                    with mock.patch.object(loader.os, "replace", side_effect=fail_second):
                        with self.assertRaises(vv_fun_patcher.PatcherError):
                            loader.install_atomic(parent, destination, "collection_progression", companion_source=candidate_dll, companion_destination=companion_destination)
            reports = list(root.glob(".vv3im-recovery-*.json"))
            self.assertEqual(len(reports), 1)
            loader.recover_vv3_transaction(reports[0])
            self.assertFalse(destination.exists())
            self.assertFalse(companion_destination.exists())
            self.assertFalse(list(root.glob(".vv3im-*")))


if __name__ == "__main__":
    unittest.main()
