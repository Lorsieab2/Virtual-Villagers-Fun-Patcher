from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import sys
import unittest
from copy import deepcopy
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


STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
GENERATOR = ROOT / "scripts" / "build_vv3_full_mastery_candidate.py"
BASE = ROOT / "data" / "candidates" / "vv3_origins_full_mastery_base_candidate.json"
FEATURE = ROOT / "data" / "candidates" / "vv3_full_mastery_all_candidate.json"
MAP = ROOT / "data" / "candidates" / "vv3_full_mastery_all_candidate_map.json"
DOC = ROOT / "docs" / "vv3-full-mastery-stage-a-candidate.md"
DLL = ROOT / "data" / "candidates" / "VVFP VV3 Full Mastery Candidate.dll"
MODES = (
    "collection_progression",
    "immediate_fixed",
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
)
SKILLS = ("farming", "parenting", "healing", "research", "building")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def walk(records: list[dict[str, object]], commit: bool):
    changed = 0
    writer_calls: list[tuple[int, int, int]] = []
    awards: list[int] = []
    for index, record in enumerate(records):
        if not record["active"] or int(record["health"]) <= 0:
            continue
        skills = record["skills"]
        assert isinstance(skills, dict)
        values = [int(skills[name]) for name in SKILLS]
        if any(value < 0 or value > 100 for value in values):
            return 0, True, [], []
        if all(value == 100 for value in values):
            continue
        changed += 1
        if commit:
            for skill_index, name in enumerate(SKILLS):
                current = int(skills[name])
                if current < 100:
                    writer_calls.append((index, skill_index, 100 - current))
                    skills[name] = 100
            awards.append(index)
    return changed, False, writer_calls, awards


def transaction(records, balance, confirm, mutate=None):
    if balance < 1_000_000:
        return "insufficient", balance, [], []
    changed, invalid, _, _ = walk(records, False)
    if invalid:
        return "invalid", balance, [], []
    if changed == 0:
        return "no_change", balance, [], []
    if confirm != 1:
        return "cancel", balance, [], []
    if mutate:
        mutate(records)
    changed, invalid, _, _ = walk(records, False)
    if invalid:
        return "invalid", balance, [], []
    if changed == 0:
        return "no_change", balance, [], []
    if balance < 1_000_000:
        return "insufficient", balance, [], []
    balance -= 1_000_000
    committed, invalid, calls, awards = walk(records, True)
    assert not invalid and committed == changed
    return "committed", balance, calls, awards


class VV3FullMasteryCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_raw = json.loads(BASE.read_text(encoding="utf-8"))
        cls.feature_raw = json.loads(FEATURE.read_text(encoding="utf-8"))
        cls.map = json.loads(MAP.read_text(encoding="utf-8"))
        cls.base = FunPatch(cls.base_raw)
        cls.feature = FunPatch(cls.feature_raw)
        cls.build = next(item for item in load_builds() if item.id == "vv3")

    def test_both_records_disabled_hidden_and_command_seven_only(self):
        self.assertFalse(self.base_raw["enabled"])
        self.assertFalse(self.feature_raw["enabled"])
        active = {item.id for item in load_fun_patches()}
        self.assertNotIn(self.base_raw["id"], active)
        self.assertNotIn(self.feature_raw["id"], active)
        self.assertEqual(self.feature_raw["dependencies"], [self.base_raw["id"]])
        contract = self.feature_raw["transaction_contract"]
        self.assertEqual((contract["command"], contract["price"]), (7, 1_000_000))
        self.assertIsNone(contract["ownership"])
        folded = json.dumps(self.feature_raw).casefold()
        self.assertNotIn("command 6", folded)
        self.assertNotIn("command 8", folded)
        self.assertNotIn("remove state", folded)

    def test_exact_fingerprint_layout_bounds_and_fixed_base(self):
        source = STOCK.read_bytes()
        self.assertEqual(len(source), 831_488)
        self.assertEqual(
            sha(source),
            "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503",
        )
        self.assertEqual(self.map["layouts"]["collection_progression"]["bound"], 150)
        self.assertEqual(self.map["layouts"]["experimental_expanded_256"]["bound"], 256)
        self.assertEqual(self.map["references"]["base_relocations"], [])
        for mode in MODES:
            layout = self.base_raw["pe_append_transaction"]["layouts"][mode]
            self.assertEqual(layout["append_offset"], "0xCB000")
            self.assertEqual(layout["append_length"], 0x1000)
            self.assertEqual(layout["header_patches"][2]["offset"], "0x2C8")
            self.assertTrue(bytes.fromhex(layout["header_patches"][2]["after"]).startswith(b".vv3fm\0\0"))

    def test_native_writer_evaluator_semantics_and_domain_gate(self):
        excluded = [
            {"active": False, "health": 100, "skills": {name: object() for name in SKILLS}},
            {"active": True, "health": 0, "skills": {name: object() for name in SKILLS}},
        ]
        target = {"active": True, "health": 1, "skills": dict(zip(SKILLS, (99, 90, 100, 88, 0))), "unrelated": 77}
        records = [*excluded, target]
        changed, invalid, calls, awards = walk(records, True)
        self.assertEqual((changed, invalid), (1, False))
        self.assertEqual(calls, [(2, 0, 1), (2, 1, 10), (2, 3, 12), (2, 4, 100)])
        self.assertEqual(awards, [2])
        self.assertEqual(target["unrelated"], 77)
        self.assertEqual(target["skills"], {name: 100 for name in SKILLS})
        invalid_record = [{"active": True, "health": 1, "skills": {name: (-1 if name == "research" else 100) for name in SKILLS}}]
        self.assertEqual(walk(invalid_record, True), (0, True, [], []))

    def test_sparse_150_256_and_transaction_races(self):
        empty = {"active": False, "health": 0, "skills": {name: 100 for name in SKILLS}}
        for bound in (150, 256):
            records = [deepcopy(empty) for _ in range(bound)]
            for index in (0, bound - 1):
                records[index] = {"active": True, "health": 1, "skills": {name: (99 if name == "building" else 100) for name in SKILLS}}
            self.assertEqual(walk(records, False)[:2], (2, False))
        base = [{"active": True, "health": 1, "skills": {name: (99 if name == "farming" else 100) for name in SKILLS}}]
        self.assertEqual(transaction(deepcopy(base), 999_999, 1), ("insufficient", 999_999, [], []))
        for answer in (0, 2, 99):
            self.assertEqual(transaction(deepcopy(base), 1_000_000, answer), ("cancel", 1_000_000, [], []))

        def finish(records):
            records[0]["skills"] = {name: 100 for name in SKILLS}

        self.assertEqual(transaction(deepcopy(base), 1_000_000, 1, finish), ("no_change", 1_000_000, [], []))
        status, balance, calls, awards = transaction(deepcopy(base), 0xFFFFFFFF, 1)
        self.assertEqual((status, balance, calls, awards), ("committed", 0xFFFFFFFF - 1_000_000, [(0, 0, 1)], [0]))

    def test_exact_result_export_strings_and_abi(self):
        exports = self.map["companion"]["exports"]
        self.assertIn("ShowOriginsFullMasteryResult", exports)
        self.assertIn("_ShowOriginsFullMasteryResult@8", exports)
        self.assertIn("ShowOriginsVillageWideResult@20", exports)
        source = (ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.c").read_text(encoding="utf-8")
        for text in (
            "Everyone is already fully mastered.",
            "No tech points have been deducted.",
            "Not enough tech points.",
            "out-of-range skill.",
            "Fully mastered %u villagers.",
        ):
            self.assertIn(text, source)
        resources = (ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.rc").read_text(encoding="utf-8")
        isolated = resources.split("203 DIALOGEX", 1)[1]
        self.assertIn('PUSHBUTTON  "Buy", 1007', isolated)
        self.assertNotIn('1006,', isolated)
        self.assertNotIn('1008,', isolated)

    def test_all_modes_render_checksum_composition_and_uninstall(self):
        compatible = [
            item for item in load_fun_patches()
            if item.game_id == "vv3"
            and item.id not in {"vv3_enable_origins_exclusive_features", "vv3_all_villagers_like_running"}
        ]
        for mode in MODES:
            with self.subTest(mode=mode):
                baseline, _ = render_patched_bytes(STOCK, self.build, mode)
                base_render, _ = render_patched_bytes(STOCK, self.build, mode, _fun_patches_override=[self.base])
                rendered, applied = render_patched_bytes(STOCK, self.build, mode, _fun_patches_override=[self.base, self.feature, *compatible])
                self.assertEqual(len(rendered), 0xCC000)
                self.assertEqual(sha(rendered), self.map["rendered_candidates"][mode]["all_current_compatible_sha256"])
                checksum_offset, _ = _pe_checksum_layout(rendered)
                stored = struct.unpack_from("<I", rendered, checksum_offset)[0]
                copy = bytearray(rendered)
                struct.pack_into("<I", copy, checksum_offset, 0)
                self.assertEqual(stored, pe_checksum(copy))
                self.assertIn(f"feature:{self.feature.id}", {item["owner"] for item in applied})
                pair, _ = render_patched_bytes(
                    STOCK, self.build, mode, _fun_patches_override=[self.base, self.feature]
                )
                blocked = bytearray(pair)
                with self.assertRaises(PatcherError):
                    _remove_feature_bytes(blocked, self.base, mode)
                work = bytearray(pair)
                _remove_feature_bytes(work, self.feature, mode)
                self.assertEqual(work, base_render)
                _remove_feature_bytes(work, self.base, mode)
                self.assertEqual(work, baseline)

    def test_old_origins_and_withdrawn_running_collide_fail_closed(self):
        active = {item.id: item for item in load_fun_patches()}
        for feature_id in ("vv3_enable_origins_exclusive_features", "vv3_all_villagers_like_running"):
            with self.assertRaises(PatcherError):
                render_patched_bytes(
                    STOCK,
                    self.build,
                    "collection_progression",
                    _fun_patches_override=[self.base, active[feature_id]],
                )

    def test_corruption_and_deterministic_generation(self):
        rendered, _ = render_patched_bytes(
            STOCK, self.build, "collection_progression", _fun_patches_override=[self.base, self.feature]
        )
        slot_work = bytearray(rendered)
        slot_work[0xCB100] ^= 1
        with self.assertRaises(PatcherError):
            _remove_feature_bytes(slot_work, self.feature, "collection_progression")
        for offset in (0x6547D, 0x2C8, len(rendered) - 1):
            with self.subTest(offset=hex(offset)):
                work = bytearray(rendered)
                work[offset] ^= 1
                _remove_feature_bytes(work, self.feature, "collection_progression")
                with self.assertRaises(PatcherError):
                    _remove_feature_bytes(work, self.base, "collection_progression")
        before = {path: sha(path.read_bytes()) for path in (BASE, FEATURE, MAP, DOC, DLL)}
        subprocess.run([sys.executable, str(GENERATOR)], cwd=ROOT, check=True)
        after = {path: sha(path.read_bytes()) for path in (BASE, FEATURE, MAP, DOC, DLL)}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
