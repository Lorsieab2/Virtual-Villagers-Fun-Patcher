from __future__ import annotations

import hashlib
import json
import os
import stat
import struct
import subprocess
import shutil
import sys
import tempfile
import unittest
from copy import deepcopy
from unittest.mock import patch as mock_patch
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    FunPatch,
    PatcherError,
    _pe_checksum_layout,
    _remove_feature_bytes,
    load_builds,
    load_fun_patches,
    pe_checksum,
    render_patched_bytes,
)
import vv_fun_patcher as patcher  # noqa: E402


STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"
GENERATOR = ROOT / "scripts" / "build_vv2_full_mastery_candidate.py"
MANIFEST = ROOT / "data" / "candidates" / "vv2_full_mastery_all_candidate.json"
MAP = ROOT / "data" / "candidates" / "vv2_full_mastery_all_candidate_map.json"
DOC = ROOT / "docs" / "vv2-full-mastery-stage-a-candidate.md"
TRANSPARENCY_DOC = ROOT / "docs" / "transparency-log.md"
RUNTIME_CHECKLIST = ROOT / "docs" / "origins-player-runtime-checklist.md"
READINESS_DOC = ROOT / "docs" / "origins-playtest-readiness.md"
VILLAGE_WIDE_DOC = ROOT / "docs" / "origins-village-wide-upgrades.md"
TRANSPARENCY_GENERATOR = ROOT / "scripts" / "generate_transparency_docs.py"
DLL = ROOT / "data" / "candidates" / "VVFP VV2 Full Mastery Candidate.dll"
IMPLEMENTATION_COMMIT = "895340333d55273e599f2dce5ab0db42cbc6d0ab"
AUDIT = ROOT / "outputs" / "vv2-c138-native-audit"
MODES = (
    "collection_progression",
    "immediate_fixed",
)
REJECTED_MODES = (
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
)
SKILLS = ("farming", "building", "research", "healing", "parenting")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def call_targets(page: bytes, base: int = 0x4B3000) -> list[int]:
    targets: list[int] = []
    for offset, byte in enumerate(page[:-4]):
        if byte != 0xE8:
            continue
        rel = struct.unpack_from("<i", page, offset + 1)[0]
        targets.append(base + offset + 5 + rel)
    return targets


def semantic_walk(records: list[dict[str, object]], commit: bool) -> tuple[int, list[int]]:
    changed = 0
    snapshot = [0] * len(records)
    for index, record in enumerate(records):
        if not record["active"] or int(record["health"]) <= 0 or record["is_totem"]:
            continue
        skills = record["skills"]
        assert isinstance(skills, dict)
        if all(int(skills[name]) == 100 for name in SKILLS):
            continue
        changed += 1
        if not commit:
            continue
        snapshot[index] = 1 if int(record["elder"]) == 0 else 2
        for name in SKILLS:
            if int(skills[name]) != 100:
                skills[name] = 100
    return changed, snapshot


def telemetry_model(records: list[dict[str, object]], snapshot: list[int]) -> tuple[int, int]:
    new_markers = 0
    changed_but_unmarked = 0
    for index, state in enumerate(snapshot):
        if state == 0:
            continue
        record = records[index]
        if record["elder"]:
            if state == 1:
                new_markers += 1
        elif sum(int(record["skills"][name]) < 88 for name in SKILLS) >= 3:
            changed_but_unmarked += 1
    return new_markers, changed_but_unmarked


def transaction(
    records: list[dict[str, object]],
    balance: int,
    confirm: int,
    mutate_before_final=None,
) -> tuple[str, int, int, int]:
    for record in records:
        if record["active"] and int(record["health"]) > 0 and not record["is_totem"]:
            if any(int(record["skills"][name]) < 0 or int(record["skills"][name]) > 100 for name in SKILLS):
                return "invalid", balance, 0, 0
    first, _ = semantic_walk(records, False)
    if first == 0:
        return "no_change", balance, 0, 0
    if balance < 1_000_000:
        return "insufficient", balance, 0, 0
    if confirm != 1:
        return "cancel", balance, 0, 0
    if mutate_before_final:
        mutate_before_final(records)
    final, _ = semantic_walk(records, False)
    if final == 0:
        return "no_change", balance, 0, 0
    committed, snapshot = semantic_walk(records, True)
    if any(int(item["skills"][name]) != 100 for item in records for name in SKILLS):
        return "recheck_failed", balance, committed, sum(1 for item in snapshot if item)
    balance -= 1_000_000
    return "committed", balance, committed, sum(1 for item in snapshot if item)


class VV2FullMasteryCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.map = json.loads(MAP.read_text(encoding="utf-8"))
        cls.candidate = FunPatch(cls.raw)
        cls.build = next(item for item in load_builds() if item.id == "vv2")

    def test_candidate_is_enabled_for_stock_modes_and_command_seven_only(self) -> None:
        self.assertTrue(self.raw["enabled"])
        self.assertEqual(self.raw["id"], "vv2_full_mastery_all_stage_a_candidate")
        loaded = [item for item in load_fun_patches() if item.id == self.raw["id"]]
        self.assertEqual(len(loaded), 1)
        self.assertFalse(self.raw["catalog_hidden"])
        self.assertEqual(self.raw["supported_modes"], list(MODES))
        self.assertEqual(self.raw["rejected_modes"], list(REJECTED_MODES))
        self.assertIn("runtime/player confirmation remains pending", self.raw["description"].casefold())
        contract = self.raw["transaction_contract"]
        self.assertEqual(contract["command"], 7)
        self.assertEqual(contract["price"], 1_000_000)
        self.assertIsNone(contract["ownership"])
        folded = json.dumps(self.raw).casefold()
        self.assertNotIn("command 6", folded)
        self.assertNotIn("command 8", folded)
        self.assertNotIn("remove state", folded)
        self.assertNotIn("0x2e514", folded)
        self.assertNotIn("0x9a000", folded)
        self.assertEqual(
            {int(item["offset"], 0) for item in self.raw["patches"]},
            {0x435EF, 0x437C0},
        )

    def test_enabled_metadata_and_docs_use_exact_global_evaluator_truth(self) -> None:
        expected = (
            "native sub_44d4c0 runs exactly once globally after complete exact-100 "
            "postverification"
        )
        generated_records = (
            json.dumps(self.raw),
            json.dumps(self.map),
            GENERATOR.read_text(encoding="utf-8"),
            DOC.read_text(encoding="utf-8"),
            TRANSPARENCY_GENERATOR.read_text(encoding="utf-8"),
            TRANSPARENCY_DOC.read_text(encoding="utf-8"),
            RUNTIME_CHECKLIST.read_text(encoding="utf-8"),
            READINESS_DOC.read_text(encoding="utf-8"),
            VILLAGE_WIDE_DOC.read_text(encoding="utf-8"),
        )
        stale = (
            "append the disabled command-7",
            "add the disabled candidate .vv2fm",
            "sub_44d4c0 exactly once per changed villager",
        )
        for text in generated_records:
            folded = " ".join(text.casefold().split())
            self.assertIn(expected, folded)
            for phrase in stale:
                self.assertNotIn(phrase, folded)
        readiness = " ".join(READINESS_DOC.read_text(encoding="utf-8").casefold().split())
        self.assertNotIn("913be6982bc17d606470f31d3df3d3430942cb6a", readiness)
        self.assertIn("13f4341201fa7757d23f77c5c17602bbe7bbf21d", readiness)
        self.assertIn("895340333d55273e599f2dce5ab0db42cbc6d0ab", readiness)
        self.assertIn("statically enabled and catalog-visible only", readiness)
        self.assertIn("runtime/player confirmation remains pending", readiness)

        required_current_truth = (
            "statically enabled and catalog-visible only",
            "five fresh manager/state acquisition boundaries",
            "changed-only native",
            "exact 100",
            "exactly once globally",
            "native 50-totem cap",
            "one 1,000,000-point deduction",
            "buy-only",
            "no remove",
            "runtime/player confirmation remains pending",
            "expanded-256 modes reject before output",
            "partial skill changes may remain",
            "no technology points are deducted",
        )
        stale_current_claims = (
            "also keeps command 7 on hold",
            "the candidate writes 90",
            "the disabled candidate iterates the supplied physical bound",
            "it writes 90 to all five fields",
            "vv2 remains on hold",
            "returns zero counts",
        )
        readiness_vv2 = readiness.split("vv2 full mastery", 1)[1].split(
            "vv1, vv3, and vv4 doubler", 1
        )[0]
        village = " ".join(VILLAGE_WIDE_DOC.read_text(encoding="utf-8").casefold().split())
        village_vv2 = village.split("### vv2 full mastery exact-build boundary", 1)[1].split(
            "### vv1 full mastery exact-build boundary", 1
        )[0]
        for section in (readiness_vv2, village_vv2):
            for phrase in required_current_truth:
                self.assertIn(phrase, section)
            for phrase in stale_current_claims:
                self.assertNotIn(phrase, section)

    def test_provenance_binds_full_implementation_and_independent_static_acceptance(self) -> None:
        for record in (self.raw, self.map):
            self.assertEqual(record["source_commit"], IMPLEMENTATION_COMMIT)
            self.assertEqual(record["implementation_commit"], IMPLEMENTATION_COMMIT)
            self.assertIsNone(record["acceptance_commit"])
            self.assertIsNone(record["audit_commit"])
            self.assertEqual(record["audit_status"], "static emitted-byte GO; runtime/player confirmation pending")
            static = record["static_acceptance"]
            self.assertEqual(static["status"], "GO")
            self.assertEqual(static["evidence_commit"], "13f4341201fa7757d23f77c5c17602bbe7bbf21d")
            self.assertEqual(static["implementation_commit"], IMPLEMENTATION_COMMIT)
            self.assertEqual(static["runtime_player_status"], "pending")
            self.assertEqual(static["allowed_modes"], list(MODES))
            self.assertEqual(static["rejected_modes"], list(REJECTED_MODES))
        self.assertEqual(len(self.raw["implementation_commit"]), 40)
        self.assertEqual(len(self.map["implementation_commit"]), 40)

    def test_generator_output_root_isolated_and_provenance_parity(self) -> None:
        tracked = (MANIFEST, MAP, DOC)
        before = {path: sha(path.read_bytes()) for path in (*tracked, DLL)}
        with tempfile.TemporaryDirectory(dir=ROOT / "outputs") as temp:
            output_root = Path(temp) / "fresh-candidate"
            subprocess.run(
                [
                    sys.executable,
                    str(GENERATOR),
                    "--output-root",
                    str(output_root),
                    "--emit-executables",
                ],
                cwd=ROOT,
                check=True,
            )
            generated_manifest = json.loads(
                (output_root / "data" / "candidates" / MANIFEST.name).read_text(encoding="utf-8")
            )
            generated_map = json.loads(
                (output_root / "data" / "candidates" / MAP.name).read_text(encoding="utf-8")
            )
            self.assertEqual(generated_manifest, self.raw)
            self.assertEqual(generated_map, self.map)
            self.assertEqual(
                (output_root / "docs" / DOC.name).read_text(encoding="utf-8"),
                DOC.read_text(encoding="utf-8"),
            )
            audit_manifest = json.loads(
                (output_root / "audit" / "artifact-manifest.json").read_text(encoding="utf-8")
            )
            audit_map = json.loads(
                (output_root / "audit" / "source-map.json").read_text(encoding="utf-8")
            )
            self.assertEqual(audit_map, self.map)
            self.assertEqual(audit_manifest["candidate_id"], self.raw["id"])
            for record in (self.raw, self.map, audit_manifest, audit_map):
                self.assertEqual(record["source_commit"], IMPLEMENTATION_COMMIT)
                self.assertEqual(record["implementation_commit"], IMPLEMENTATION_COMMIT)
                self.assertIsNone(record["acceptance_commit"])
                self.assertIsNone(record["audit_commit"])
                self.assertEqual(record["audit_status"], "static emitted-byte GO; runtime/player confirmation pending")
                self.assertEqual(record["static_acceptance"]["evidence_commit"], "13f4341201fa7757d23f77c5c17602bbe7bbf21d")
            self.assertEqual(
                sha((output_root / "audit" / "collection_progression.exe").read_bytes()),
                sha((AUDIT / "collection_progression.exe").read_bytes()),
            )
            self.assertEqual(
                sha((output_root / "audit" / "immediate_fixed.exe").read_bytes()),
                sha((AUDIT / "immediate_fixed.exe").read_bytes()),
            )
            self.assertEqual(before, {path: sha(path.read_bytes()) for path in (*tracked, DLL)})
        self.assertEqual(before, {path: sha(path.read_bytes()) for path in (*tracked, DLL)})

    def test_loader_pins_manifest_map_bytes_and_composition_identities(self) -> None:
        self.assertEqual(sha(MANIFEST.read_bytes()), patcher.VV2_FULL_MASTERY_MANIFEST_SHA256)
        self.assertEqual(sha(MAP.read_bytes()), patcher.VV2_FULL_MASTERY_MAP_SHA256)
        self.assertEqual(
            self.map["static_acceptance"]["collection_composition_sha256"],
            "C7C0BEC312B6537B5F1DD692D2C90ED0D0963D6CE3A7F5271AF4A6C680B8ACBC",
        )
        self.assertEqual(
            self.map["static_acceptance"]["immediate_composition_sha256"],
            "6AEE09C69C3E7C1AD12284EA5B5A188AF05DA3D87AD6149545CEE65D896E6774",
        )
        self.assertEqual(self.map["static_acceptance"]["dll_size"], 109056)
        self.assertEqual(self.map["static_acceptance"]["stock_size"], 724992)

    def test_manifest_or_map_byte_mutation_fails_before_catalog_trust(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest_copy = root / MANIFEST.name
            map_copy = root / MAP.name
            dll_copy = root / DLL.name
            manifest_bytes = bytearray(MANIFEST.read_bytes())
            manifest_bytes[-2] ^= 1
            manifest_copy.write_bytes(manifest_bytes)
            map_copy.write_bytes(MAP.read_bytes())
            dll_copy.write_bytes(DLL.read_bytes())
            with mock_patch.object(
                patcher,
                "VV2_FULL_MASTERY_CANDIDATE_PATHS",
                {"manifest": manifest_copy, "map": map_copy, "dll": dll_copy},
            ):
                with self.assertRaises(PatcherError):
                    patcher._certified_vv2_full_mastery_record()
            manifest_copy.write_bytes(MANIFEST.read_bytes())
            map_bytes = bytearray(MAP.read_bytes())
            map_bytes[-2] ^= 1
            map_copy.write_bytes(map_bytes)
            with mock_patch.object(
                patcher,
                "VV2_FULL_MASTERY_CANDIDATE_PATHS",
                {"manifest": manifest_copy, "map": map_copy, "dll": dll_copy},
            ):
                with self.assertRaises(PatcherError):
                    patcher._certified_vv2_full_mastery_record()

    def test_generator_output_root_containment_fails_before_write(self) -> None:
        for invalid in (ROOT, ROOT / "data", ROOT / "docs"):
            result = subprocess.run(
                [sys.executable, str(GENERATOR), "--output-root", str(invalid)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0, invalid)
        with tempfile.TemporaryDirectory(dir=ROOT / "outputs") as parent:
            invalid = Path(parent) / "missing" / "root"
            result = subprocess.run(
                [sys.executable, str(GENERATOR), "--output-root", str(invalid)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(invalid.exists())

    def test_generator_rejects_existing_empty_and_nonempty_destinations(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "outputs") as temp:
            parent = Path(temp)
            for name, populated in (("empty", False), ("nonempty", True)):
                destination = parent / name
                destination.mkdir()
                if populated:
                    (destination / "sentinel.txt").write_text("keep", encoding="utf-8")
                result = subprocess.run(
                    [sys.executable, str(GENERATOR), "--output-root", str(destination)],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(destination.is_dir())
                if populated:
                    self.assertEqual((destination / "sentinel.txt").read_text(encoding="utf-8"), "keep")

    def test_generator_rejects_outside_and_traversal_roots(self) -> None:
        with tempfile.TemporaryDirectory() as outside:
            result = subprocess.run(
                [sys.executable, str(GENERATOR), "--output-root", outside],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
        result = subprocess.run(
            [sys.executable, str(GENERATOR), "--output-root", str(ROOT / "outputs" / "safe" / ".." / "escape")],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_lexical_broken_destination_is_rejected_when_supported(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("vv2_generator_broken_link", GENERATOR)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(dir=ROOT / "outputs") as temp:
            parent = Path(temp)
            destination = parent / "broken-destination"
            target = parent / "missing-target"
            try:
                destination.symlink_to(target, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unavailable")
            with self.assertRaises(ValueError):
                module.resolve_output_paths(destination)
            self.assertTrue(destination.is_symlink())
            self.assertFalse(target.exists())

    def test_lexical_destination_checks_have_deterministic_mock_fallback(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("vv2_generator_lexical_mock", GENERATOR)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(dir=ROOT / "outputs") as temp:
            parent = Path(temp)
            destination = parent / "mocked-destination"
            original_lexists = module.os.path.lexists
            module.os.path.lexists = lambda path: os.fspath(path) == os.fspath(destination)
            try:
                with self.assertRaises(ValueError):
                    module.resolve_output_paths(destination)
            finally:
                module.os.path.lexists = original_lexists
            self.assertFalse(destination.exists())

    def test_lexical_race_check_precedes_rename(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("vv2_generator_lexical_race", GENERATOR)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(dir=ROOT / "outputs") as temp:
            parent = Path(temp)
            destination = parent / "lexical-race"
            original_lexists = module.os.path.lexists
            calls = {"destination": 0}

            def race_lexists(path):
                if os.fspath(path) == os.fspath(destination):
                    calls["destination"] += 1
                    return calls["destination"] >= 2
                return original_lexists(path)

            module.os.path.lexists = race_lexists
            rename_called = {"value": False}

            def unexpected_rename(stage, final):
                rename_called["value"] = True
                raise AssertionError("rename should not be reached")

            try:
                with self.assertRaises(FileExistsError):
                    module.write_output_bundle(
                        destination,
                        {"probe.txt": b"x"},
                        replace_func=unexpected_rename,
                    )
            finally:
                module.os.path.lexists = original_lexists
            self.assertFalse(rename_called["value"])
            self.assertFalse(destination.exists())
            self.assertEqual(list(parent.glob(".lexical-race.staging-*")), [])

    def test_parent_identity_recheck_blocks_publish(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("vv2_generator_parent_identity", GENERATOR)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(dir=ROOT / "outputs") as temp:
            parent = Path(temp)
            destination = parent / "parent-identity"
            original_entry_matches = module._entry_matches
            checks = {"parent": 0}

            def changed_parent(path, expected):
                if path == parent:
                    checks["parent"] += 1
                    if checks["parent"] >= 2:
                        return False
                return original_entry_matches(path, expected)

            module._entry_matches = changed_parent
            rename_called = {"value": False}

            def unexpected_rename(stage, final):
                rename_called["value"] = True
                raise AssertionError("rename should not be reached")

            try:
                with self.assertRaises(RuntimeError):
                    module.write_output_bundle(
                        destination,
                        {"probe.txt": b"x"},
                        replace_func=unexpected_rename,
                    )
            finally:
                module._entry_matches = original_entry_matches
            self.assertGreaterEqual(checks["parent"], 2)
            self.assertFalse(rename_called["value"])
            self.assertFalse(destination.exists())
            self.assertEqual(list(parent.glob(".parent-identity.staging-*")), [])

    def test_invalid_destinations_are_rejected_before_build(self) -> None:
        import importlib.util
        import types

        spec = importlib.util.spec_from_file_location("vv2_generator_prebuild", GENERATOR)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        calls = {"build": 0}

        def unexpected_build():
            calls["build"] += 1
            raise AssertionError("build must not run for invalid output roots")

        module.build = unexpected_build
        with tempfile.TemporaryDirectory(dir=ROOT / "outputs") as temp:
            parent = Path(temp)
            outside = ROOT.parent / "c154-outside-destination"
            existing = parent / "existing"
            existing.mkdir()
            invalid = [
                ROOT,
                ROOT / "data",
                ROOT / "docs",
                outside,
                ROOT / "outputs" / "safe" / ".." / "escape",
                existing,
            ]
            for destination in invalid:
                with self.assertRaises((ValueError, AssertionError)):
                    module.main(["--output-root", str(destination)])
                self.assertEqual(calls["build"], 0)
            broken = parent / "broken"
            try:
                broken.symlink_to(parent / "missing-target", target_is_directory=True)
            except (OSError, NotImplementedError):
                pass
            else:
                with self.assertRaises(ValueError):
                    module.main(["--output-root", str(broken)])
                self.assertEqual(calls["build"], 0)

            ancestor = parent / "ancestor"
            ancestor.mkdir()
            candidate = ancestor / "candidate"
            original_lstat = module.os.lstat
            fake_link = types.SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0)

            def fake_lstat(path):
                if os.fspath(path) == os.fspath(ancestor):
                    return fake_link
                return original_lstat(path)

            module.os.lstat = fake_lstat
            try:
                with self.assertRaises(ValueError):
                    module.main(["--output-root", str(candidate)])
            finally:
                module.os.lstat = original_lstat
            self.assertEqual(calls["build"], 0)
            self.assertFalse(candidate.exists())

    def test_atomic_bundle_cleans_staging_on_write_and_rename_failure(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("vv2_generator", GENERATOR)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(dir=ROOT / "outputs") as temp:
            parent = Path(temp)
            final = parent / "write-failure"

            def fail_write(path, data):
                raise OSError("injected write failure")

            with self.assertRaises(OSError):
                module.write_output_bundle(final, {"probe.txt": b"x"}, write_func=fail_write)
            self.assertFalse(final.exists())
            self.assertEqual(list(parent.glob(".write-failure.staging-*")), [])

            final = parent / "rename-failure"

            def fail_replace(stage, destination):
                destination.mkdir()
                (destination / "partial.txt").write_text("partial", encoding="utf-8")
                raise OSError("injected rename failure")

            with self.assertRaises(OSError):
                module.write_output_bundle(final, {"probe.txt": b"x"}, replace_func=fail_replace)
            self.assertTrue(final.exists())
            self.assertEqual((final / "partial.txt").read_text(encoding="utf-8"), "partial")
            self.assertEqual(list(parent.glob(".rename-failure.staging-*")), [])

            transferred = parent / "rename-success"
            module.write_output_bundle(transferred, {"probe.txt": b"x"})
            self.assertEqual((transferred / "probe.txt").read_bytes(), b"x")
            self.assertEqual(list(parent.glob(".rename-success.staging-*")), [])

            raced = parent / "foreign-race"

            def foreign_race(stage, destination):
                destination.mkdir()
                (destination / "sentinel.txt").write_bytes(b"foreign")
                raise FileExistsError("foreign destination appeared")

            with self.assertRaises(FileExistsError):
                module.write_output_bundle(raced, {"probe.txt": b"x"}, replace_func=foreign_race)
            self.assertTrue(raced.exists())
            self.assertEqual((raced / "sentinel.txt").read_bytes(), b"foreign")
            self.assertEqual(list(parent.glob(".foreign-race.staging-*")), [])

    def test_partial_write_unknown_file_preserves_suspect_staging(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("vv2_generator_partial_write", GENERATOR)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(dir=ROOT / "outputs") as temp:
            parent = Path(temp)
            final = parent / "partial-write"

            def partial_write(path, data):
                path.write_bytes(b"partial")
                raise OSError("injected partial write")

            with self.assertRaises(OSError):
                module.write_output_bundle(final, {"probe.txt": b"x"}, write_func=partial_write)
            self.assertFalse(final.exists())
            suspect = list(parent.glob(".partial-write.staging-*"))
            self.assertEqual(len(suspect), 1)
            self.assertEqual((suspect[0] / "probe.txt").read_bytes(), b"partial")
            (suspect[0] / "probe.txt").unlink()
            suspect[0].rmdir()

    def test_unknown_entries_and_replaced_files_preserve_suspect_staging(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("vv2_generator_inventory_mismatch", GENERATOR)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(dir=ROOT / "outputs") as temp:
            parent = Path(temp)

            def add_sentinel(path, data):
                path.write_bytes(data)
                (path.parent / "sentinel.txt").write_bytes(b"foreign")

            final = parent / "unknown-file"
            with self.assertRaises(ValueError):
                module.write_output_bundle(final, {"probe.txt": b"x"}, write_func=add_sentinel)
            suspect = list(parent.glob(".unknown-file.staging-*"))
            self.assertEqual(len(suspect), 1)
            self.assertEqual((suspect[0] / "sentinel.txt").read_bytes(), b"foreign")
            (suspect[0] / "probe.txt").unlink()
            (suspect[0] / "sentinel.txt").unlink()
            suspect[0].rmdir()

            first_path: Path | None = None

            def replace_first(path, data):
                nonlocal first_path
                if first_path is None:
                    path.write_bytes(data)
                    first_path = path
                    return
                first_path.unlink()
                first_path.write_bytes(b"replaced")
                path.write_bytes(data)

            final = parent / "replaced-file"
            with self.assertRaises(ValueError):
                module.write_output_bundle(
                    final,
                    {"first.bin": b"first", "second.bin": b"second"},
                    write_func=replace_first,
                )
            suspect = list(parent.glob(".replaced-file.staging-*"))
            self.assertEqual(len(suspect), 1)
            self.assertEqual((suspect[0] / "first.bin").read_bytes(), b"replaced")
            (suspect[0] / "first.bin").unlink()
            (suspect[0] / "second.bin").unlink()
            suspect[0].rmdir()

    def test_hardlink_substitution_preserves_suspect_staging_when_supported(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("vv2_generator_hardlink", GENERATOR)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(dir=ROOT / "outputs") as temp:
            parent = Path(temp)
            first_path: Path | None = None

            def make_hardlink(path, data):
                nonlocal first_path
                if first_path is None:
                    path.write_bytes(data)
                    first_path = path
                    return
                hardlink = path.parent / "hardlink.bin"
                try:
                    os.link(first_path, hardlink)
                except (OSError, NotImplementedError):
                    raise unittest.SkipTest("hardlinks unavailable")
                path.write_bytes(data)

            final = parent / "hardlink"
            try:
                module.write_output_bundle(
                    final,
                    {"first.bin": b"first", "second.bin": b"second"},
                    write_func=make_hardlink,
                )
            except unittest.SkipTest as exc:
                self.skipTest(str(exc))
            except ValueError:
                pass
            else:
                self.fail("hardlink substitution did not fail closed")
            suspect = list(parent.glob(".hardlink.staging-*"))
            if suspect:
                for path in suspect[0].iterdir():
                    path.unlink()
                suspect[0].rmdir()

    def test_companion_missing_or_hash_altered_fails_before_output_creation(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("vv2_generator_companion", GENERATOR)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        original = module.COMPANION
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp) / "candidate.dll"
            temp_path.write_bytes(original.read_bytes())
            module.COMPANION = temp_path
            temp_path.unlink()
            with self.assertRaises(RuntimeError):
                module.build()
            temp_path.write_bytes(original.read_bytes()[:-1] + b"X")
            with self.assertRaises(RuntimeError):
                module.build()
            module.COMPANION = original

    def test_output_root_reparse_ancestor_is_rejected_when_supported(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "outputs") as temp:
            parent = Path(temp)
            external = Path(tempfile.mkdtemp())
            link = parent / "link"
            try:
                link.symlink_to(external, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unavailable")
            result = subprocess.run(
                [sys.executable, str(GENERATOR), "--output-root", str(link / "candidate")],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((external / "candidate").exists())

    def test_staging_reparse_substitution_is_not_deleted_when_supported(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("vv2_generator_stage_reparse", GENERATOR)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(dir=ROOT / "outputs") as temp:
            parent = Path(temp)
            final = parent / "stage-reparse"
            substituted: dict[str, Path] = {}

            def substitute_stage(path, data):
                stage = path.parent
                backup = parent / "substituted-stage-backup"
                stage.rename(backup)
                try:
                    stage.symlink_to(backup, target_is_directory=True)
                except (OSError, NotImplementedError):
                    backup.rename(stage)
                    raise unittest.SkipTest("directory symlinks unavailable")
                substituted["stage"] = stage
                substituted["backup"] = backup
                raise OSError("injected staging substitution")

            try:
                module.write_output_bundle(final, {"probe.txt": b"x"}, write_func=substitute_stage)
            except unittest.SkipTest as exc:
                self.skipTest(str(exc))
            except OSError:
                pass
            else:
                self.fail("staging substitution did not fail closed")
            if substituted:
                self.assertTrue(substituted["stage"].is_symlink())
                self.assertTrue(substituted["backup"].is_dir())
                substituted["stage"].unlink()
                shutil.rmtree(substituted["backup"], ignore_errors=True)


    def test_staging_identity_substitution_is_not_deleted(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("vv2_generator_stage_identity", GENERATOR)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(dir=ROOT / "outputs") as temp:
            parent = Path(temp)
            replaced = parent / "stage-identity"
            foreign: dict[str, Path] = {}

            def replace_stage_with_foreign_directory(path, data):
                stage = path.parent
                backup = parent / "owned-stage-moved"
                stage.rename(backup)
                stage.mkdir()
                foreign["stage"] = stage
                foreign["backup"] = backup
                raise OSError("injected ordinary staging substitution")

            with self.assertRaises(OSError):
                module.write_output_bundle(
                    replaced,
                    {"probe.txt": b"x"},
                    write_func=replace_stage_with_foreign_directory,
                )
            self.assertTrue(foreign["stage"].is_dir())
            self.assertTrue(foreign["backup"].is_dir())
            foreign["stage"].rmdir()
            shutil.rmtree(foreign["backup"], ignore_errors=True)

    def test_source_fingerprint_section_geometry_and_iat_guards(self) -> None:
        source = STOCK.read_bytes()
        self.assertEqual(len(source), 724_992)
        self.assertEqual(
            sha(source),
            "46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677",
        )
        self.assertEqual(source[0x6FE49:0x6FE54].hex().upper(), "6838104900FF1510404700")
        self.assertEqual(
            source[0x6FE5E:0x6FE6C].hex().upper(),
            "8B35D4404700682C10490057FFD6",
        )
        section = self.map["section"]
        self.assertEqual(section["raw_offset"], "0xB1000")
        self.assertEqual(section["rva"], "0xB3000")
        self.assertEqual(section["va"], "0x4B3000")
        self.assertEqual(section["characteristics"], "0x60000020 executable/readable/non-writable")
        self.assertEqual(section["new_file_length"], "0xB3000")
        self.assertEqual(section["new_size_of_image"], "0xB5000")

    def test_exact_confirmation_abi_and_non_ok_matrix(self) -> None:
        confirmation = self.map["confirmation"]
        self.assertEqual(confirmation["load_library_iat"], "0x474010")
        self.assertEqual(confirmation["get_proc_address_iat"], "0x4740D4")
        self.assertEqual(
            confirmation["return_matrix"],
            {"0": 0, "1": 1, "2": 0, "arbitrary_non_1": 0},
        )
        page = bytes.fromhex(
            self.raw["pe_append_transaction"]["layouts"]["collection_progression"]["append_bytes"]
        )
        self.assertIn(b"user32.dll\0", page)
        self.assertIn(b"MessageBoxA\0", page)
        self.assertIn(
            b"This upgrade makes permanent changes to your village. Are you sure "
            b"you want to purchase it? Press OK to confirm, or Cancel.\0",
            page,
        )
        self.assertIn(b"Origins Upgrades\0", page)
        confirm_offset = int(self.map["offsets"]["confirmation"], 0)
        confirm = page[confirm_offset:confirm_offset + 0xC0]
        self.assertIn(bytes.fromhex("FF1510404700"), confirm)
        self.assertIn(bytes.fromhex("FF15D4404700"), confirm)
        self.assertIn(bytes.fromhex("83F8010F94C00FB6C0"), confirm)

    def test_handler_transports_thiscall_receiver_without_clobbering_saved_esi(self) -> None:
        page = bytes.fromhex(
            self.raw["pe_append_transaction"]["layouts"]["collection_progression"]["append_bytes"]
        )
        entry_offset = int(self.map["offsets"]["entry"], 0)
        entry = page[entry_offset:entry_offset + 16]
        self.assertTrue(entry.startswith(bytes.fromhex("5589E5535657")))

    def test_native_abi_and_transaction_order_are_emitted(self) -> None:
        page = bytes.fromhex(self.raw["pe_append_transaction"]["layouts"]["collection_progression"]["append_bytes"])
        text = json.dumps(self.map)
        for needle in ("0x44F4E0", "0x445430", "0x44D4C0", "0x426290"):
            self.assertIn(needle, text)
        self.assertEqual(self.map["allowed_modes"], list(MODES))
        self.assertEqual(self.map["rejected_modes"], list(REJECTED_MODES))
        self.assertEqual(page.count(bytes.fromhex("E8DBC1F9FF")), 0)
        self.assertNotIn(bytes.fromhex("C704240064000000"), page)
        self.assertEqual(
            self.raw["transaction_contract"]["native_evaluator"],
            "native sub_44D4C0 runs exactly once globally after complete exact-100 postverification; thiscall ECX=manager",
        )
        self.assertEqual(self.raw["transaction_contract"]["native_tech_writer"], "sub_426290 thiscall ECX=state; push signed -1000000; callee ret 4 exactly once after evaluator")
        targets = call_targets(page)
        self.assertEqual(targets.count(0x44F4E0), 5)
        self.assertEqual(targets.count(0x44D4C0), 1)
        self.assertEqual(targets.count(0x426290), 1)
        self.assertEqual(targets.count(0x445430), 5)
        self.assertEqual(
            self.raw["transaction_contract"]["skills"],
            {
                "farming": "+0x7E4 -> native skill 3",
                "building": "+0x7E8 -> native skill 2",
                "research": "+0x7EC -> native skill 1",
                "healing": "+0x7F0 -> native skill 5",
                "parenting": "+0x7F4 -> native skill 4",
            },
        )
        self.assertEqual(self.raw["transaction_contract"]["walker_locals"]["mode"], "[ebp-0x10]")
        self.assertEqual(self.raw["transaction_contract"]["walker_locals"]["bound"], "[ebp-0x14]")
        self.assertIn("both menu and result exports", self.raw["transaction_contract"]["result_preflight"])
        self.assertEqual(
            self.raw["transaction_contract"]["result_pointer_local"],
            "[ebp-0x10], outside the 256-byte snapshot; every post-preflight result uses the saved stdcall pointer",
        )
        self.assertEqual(len(self.raw["transaction_contract"]["fresh_manager_boundaries"]), 5)
        entry_offset = int(self.map["offsets"]["entry"], 0)
        entry = page[entry_offset:0x380]
        self.assertNotIn(0x4B3C00, call_targets(entry, 0x4B3000 + entry_offset))
        self.assertEqual(entry.count(bytes.fromhex("FF55D4")), 0)
        self.assertEqual(entry.count(bytes.fromhex("FF55F0")), 7)
        self.assertNotIn(bytes.fromhex("FF55D4"), entry)
        self.assertIn(bytes.fromhex("8945F0"), entry)
        self.assertIn(bytes.fromhex("8955EC"), entry)
        self.assertIn(bytes.fromhex("FF75EC"), entry)
        self.assertNotIn(bytes.fromhex("8955D8"), entry)
        self.assertNotIn(bytes.fromhex("FF75D8"), entry)
        self.assertEqual(entry.count(bytes.fromhex("81BADC EA020040420F00".replace(" ", ""))), 3)
        self.assertEqual(
            self.raw["transaction_contract"]["result_statuses"]["4"],
            "Full Mastery was canceled; No tech points have been deducted.",
        )
        for field in (0x7E4, 0x7E8, 0x7EC, 0x7F0, 0x7F4):
            self.assertNotIn(b"\xC7\x86" + struct.pack("<I", field), page)

    def test_expanded_modes_fail_before_output_and_invalid_values_fail_closed(self) -> None:
        self.assertEqual(self.raw["supported_modes"], list(MODES))
        self.assertEqual(self.raw["rejected_modes"], list(REJECTED_MODES))
        invalid = [{
            "active": True,
            "health": 100,
            "is_totem": False,
            "elder": 0,
            "skills": {name: (101 if name == "farming" else 100) for name in SKILLS},
        }]
        self.assertEqual(transaction(deepcopy(invalid), 2_000_000, 1), ("invalid", 2_000_000, 0, 0))
        with self.assertRaises(PatcherError):
            render_patched_bytes(STOCK, self.build, REJECTED_MODES[0], _fun_patches_override=[self.candidate])

    def test_semantic_walker_excludes_before_skill_access_and_writes_only_below_100(self) -> None:
        records = [
            {"active": False, "health": 100, "is_totem": False, "elder": 0, "skills": {name: object() for name in SKILLS}},
            {"active": True, "health": 0, "is_totem": False, "elder": 0, "skills": {name: object() for name in SKILLS}},
            {"active": True, "health": 100, "is_totem": True, "elder": 0, "skills": {name: object() for name in SKILLS}},
            {"active": True, "health": 100, "is_totem": False, "elder": 0, "skills": dict(zip(SKILLS, (100, 99, 88, 100, -1)))},
            {"active": True, "health": 100, "is_totem": False, "elder": 1, "skills": {name: 100 for name in SKILLS}},
        ]
        changed, snapshot = semantic_walk(records, True)
        self.assertEqual(changed, 1)
        self.assertEqual(snapshot, [0, 0, 0, 1, 0])
        self.assertEqual(records[3]["skills"], {name: 100 for name in SKILLS})
        self.assertEqual(records[4]["elder"], 1)

    def test_sparse_first_last_bound_and_dry_commit_parity(self) -> None:
        empty = {
            "active": False,
            "health": 0,
            "is_totem": False,
            "elder": 0,
            "skills": {name: 100 for name in SKILLS},
        }
        records = [deepcopy(empty) for _ in range(256)]
        for index in (0, 255):
            records[index] = {
                "active": True,
                "health": 1,
                "is_totem": False,
                "elder": 0,
                "skills": {name: (99 if name == "research" else 100) for name in SKILLS},
            }
        dry, _ = semantic_walk(deepcopy(records), False)
        commit, snapshot = semantic_walk(records, True)
        self.assertEqual((dry, commit), (2, 2))
        self.assertEqual([i for i, value in enumerate(snapshot) if value], [0, 255])

    def test_transaction_vectors_no_charge_cancel_race_and_success(self) -> None:
        base = [{
            "active": True,
            "health": 100,
            "is_totem": False,
            "elder": 0,
            "skills": {name: (99 if name == "farming" else 100) for name in SKILLS},
        }]
        self.assertEqual(transaction(deepcopy(base), 999_999, 1), ("insufficient", 999_999, 0, 0))
        self.assertEqual(transaction(deepcopy(base), 1_000_000, 0), ("cancel", 1_000_000, 0, 0))
        self.assertEqual(transaction(deepcopy(base), 1_000_000, 2), ("cancel", 1_000_000, 0, 0))
        self.assertEqual(transaction(deepcopy(base), 1_000_000, 77), ("cancel", 1_000_000, 0, 0))
        mastered = deepcopy(base)
        mastered[0]["skills"] = {name: 100 for name in SKILLS}
        self.assertEqual(transaction(mastered, 1_000_000, 1), ("no_change", 1_000_000, 0, 0))

        def finish_before_ok(records):
            records[0]["skills"] = {name: 100 for name in SKILLS}

        self.assertEqual(
            transaction(deepcopy(base), 1_000_000, 1, finish_before_ok),
            ("no_change", 1_000_000, 0, 0),
        )
        self.assertEqual(transaction(deepcopy(base), 1_000_000, 1), ("committed", 0, 1, 1))

    def test_exact_no_change_and_bounded_uint_max_result(self) -> None:
        source = (ROOT / "native" / "vv2_full_mastery_candidate" / "vv2_full_mastery_candidate.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("Everyone is already fully mastered.\\r\\n", source)
        self.assertIn("No tech points have been deducted.", source)
        self.assertIn("Full Mastery was canceled.\\r\\n", source)
        self.assertEqual(
            self.raw["transaction_contract"]["result_statuses"]["4"],
            "Full Mastery was canceled; No tech points have been deducted.",
        )
        longest = (
            "Fully mastered 4294967295 villagers.\r\n"
            "4294967295 villagers became Esteemed Elders.\r\n"
            "4294967295 fully mastered villagers remain without the Elder marker "
            "because the native 50-totem limit was reached."
        )
        self.assertLessEqual(len(longest.encode("ascii")) + 1, 256)

    def test_constructor_pointer_is_valid_and_snapshot_states_are_emitted(self) -> None:
        page = bytes.fromhex(self.raw["pe_append_transaction"]["layouts"]["collection_progression"]["append_bytes"])
        button_va = int(self.map["strings"]["button"], 0)
        self.assertEqual(struct.unpack_from("<I", page, 0x7D)[0], button_va)
        self.assertIn(b"Origins Upgrades\0", page[0x1000:])
        entry = page[int(self.map["offsets"]["entry"], 0):]
        self.assertIn(bytes.fromhex("31C0B940000000F3AB"), entry)  # zero 256-byte snapshot
        self.assertIn(bytes.fromhex("80BEFC07000000"), page)
        self.assertIn(bytes.fromhex("C6041F01"), page)
        self.assertIn(bytes.fromhex("C6041F02"), page)

    def test_entry_scalar_intervals_and_high_index_telemetry_are_disjoint(self) -> None:
        contract = self.raw["transaction_contract"]
        page = bytes.fromhex(self.raw["pe_append_transaction"]["layouts"]["collection_progression"]["append_bytes"])
        entry = page[int(self.map["offsets"]["entry"], 0):0x380]
        self.assertEqual(contract["entry_snapshot_interval"], "[ebp-0x124..ebp-0x25] inclusive (256 bytes)")
        expected = {
            "result_pointer": -0x10,
            "changed_but_unmarked": -0x14,
            "changed_count": -0x18,
            "manager": -0x1C,
            "state": -0x20,
            "new_elder_count": -0x24,
        }
        actual = {
            name: int(value.removeprefix("[ebp-").removesuffix("]"), 16) * -1
            for name, value in contract["entry_scalar_locals"].items()
        }
        self.assertEqual(actual, expected)
        snapshot = (-0x124, -0x25)
        saved = [(-0x04, -0x01), (-0x08, -0x05), (-0x0C, -0x09)]
        for offset in actual.values():
            span = (offset, offset + 3)
            self.assertFalse(span[0] <= snapshot[1] and span[1] >= snapshot[0])
            self.assertFalse(any(span[0] <= slot[1] and span[1] >= slot[0] for slot in saved))

        empty = {
            "active": False,
            "health": 100,
            "is_totem": False,
            "elder": 0,
            "skills": {name: 99 for name in SKILLS},
        }
        records = [deepcopy(empty) for _ in range(256)]
        entry_before = entry
        for index in range(248, 256):
            records[index]["active"] = True
            records[index]["skills"]["farming"] = 99 - (index - 248)
        changed, snapshot_values = semantic_walk(records, True)
        self.assertEqual(changed, 8)
        self.assertEqual(snapshot_values[248:256], [1] * 8)
        for index in range(248, 256):
            records[index]["elder"] = 1
        self.assertEqual(telemetry_model(records, snapshot_values), (8, 0))
        self.assertEqual(entry, entry_before)

    def test_all_modes_render_checksum_and_exact_uninstall_roundtrip(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                baseline, _ = render_patched_bytes(STOCK, self.build, mode)
                rendered, applied = render_patched_bytes(
                    STOCK,
                    self.build,
                    mode,
                    _fun_patches_override=[self.candidate],
                )
                expected = self.map["rendered_candidates"][mode]
                self.assertEqual(sha(rendered), expected["candidate_sha256"])
                self.assertEqual(len(rendered), 0xB3000)
                page = bytes.fromhex(
                    self.raw["pe_append_transaction"]["layouts"][mode]["append_bytes"]
                )
                self.assertEqual(rendered[0xB1000:0xB3000], page)
                self.assertEqual(rendered[0x2B0:0x2B6], b".vv2fm")
                checksum_offset, _ = _pe_checksum_layout(rendered)
                stored = struct.unpack_from("<I", rendered, checksum_offset)[0]
                copy = bytearray(rendered)
                struct.pack_into("<I", copy, checksum_offset, 0)
                self.assertEqual(stored, pe_checksum(copy))
                self.assertIn(
                    f"feature:{self.candidate.id}",
                    {item["owner"] for item in applied},
                )
                work = bytearray(rendered)
                _remove_feature_bytes(work, self.candidate, mode)
                self.assertEqual(work, baseline)

    def test_corrupted_hook_header_and_tail_fail_closed(self) -> None:
        baseline, _ = render_patched_bytes(STOCK, self.build, "collection_progression")
        rendered, _ = render_patched_bytes(
            STOCK,
            self.build,
            "collection_progression",
            _fun_patches_override=[self.candidate],
        )
        for offset in (0x435EF, 0xF6, 0x2B0, len(rendered) - 1):
            with self.subTest(offset=hex(offset)):
                work = bytearray(rendered)
                work[offset] ^= 1
                with self.assertRaises(PatcherError):
                    _remove_feature_bytes(work, self.candidate, "collection_progression")
        self.assertEqual(len(baseline), 0xB1000)

    def test_composes_with_every_current_vv2_patch_without_origins(self) -> None:
        others = [
            item
            for item in load_fun_patches()
            if item.game_id == "vv2" and item.id != self.candidate.id
        ]
        self.assertNotIn("vv2_enable_origins_exclusive_features", {item.id for item in others})
        for mode in MODES:
            with self.subTest(mode=mode):
                rendered, _ = render_patched_bytes(
                    STOCK,
                    self.build,
                    mode,
                    _fun_patches_override=[self.candidate, *others],
                )
                self.assertEqual(len(rendered), 0xB3000)

if __name__ == "__main__":
    unittest.main()
