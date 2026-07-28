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


STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
GENERATOR = ROOT / "scripts" / "build_vv1_full_mastery_candidate.py"
MANIFEST = ROOT / "data" / "candidates" / "vv1_full_mastery_all_candidate.json"
MAP = ROOT / "data" / "candidates" / "vv1_full_mastery_all_candidate_map.json"
DOC = ROOT / "docs" / "vv1-full-mastery-stage-a-candidate.md"
DLL = ROOT / "data" / "candidates" / "VVFP VV1 Full Mastery Candidate.dll"
MODES = (
    "collection_progression",
    "immediate_fixed",
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
)
SKILLS = ("parenting", "building", "farming", "healing", "research")
SKILL_CODES = (2, 4, 1, 5, 3)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def semantic_walk(
    records: list[dict[str, object]], commit: bool
) -> tuple[int, bool, list[tuple[int, int, int]]]:
    changed = 0
    calls: list[tuple[int, int, int]] = []
    for index, record in enumerate(records):
        if (
            not record["occupied"]
            or int(record["health"]) <= 0
            or int(record["special"]) == 199
        ):
            continue
        skills = record["skills"]
        assert isinstance(skills, dict)
        values = [int(skills[name]) for name in SKILLS]
        if any(value < 0 or value > 100 for value in values):
            return 0, True, []
        if all(value == 100 for value in values):
            continue
        changed += 1
        if commit:
            for name, code in zip(SKILLS, SKILL_CODES):
                current = int(skills[name])
                if current < 100:
                    calls.append((index, code, 100 - current))
                    skills[name] = 100
    return changed, False, calls


def transaction(
    records: list[dict[str, object]],
    balance: int,
    confirm: int,
    result_export_available: bool = True,
    mutate_before_final=None,
) -> tuple[str, int, list[tuple[int, int, int]]]:
    if not result_export_available:
        return "unavailable", balance, []
    if balance < 1_000_000:
        return "insufficient", balance, []
    changed, invalid, _ = semantic_walk(records, False)
    if invalid:
        return "invalid", balance, []
    if changed == 0:
        return "no_change", balance, []
    if confirm != 1:
        return "cancel", balance, []
    if mutate_before_final:
        mutate_before_final(records)
    changed, invalid, _ = semantic_walk(records, False)
    if invalid:
        return "invalid", balance, []
    if changed == 0:
        return "no_change", balance, []
    if balance < 1_000_000:
        return "insufficient", balance, []
    balance -= 1_000_000
    committed, invalid, calls = semantic_walk(records, True)
    assert not invalid and committed == changed
    return "committed", balance, calls


class VV1FullMasteryCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.map = json.loads(MAP.read_text(encoding="utf-8"))
        cls.candidate = FunPatch(cls.raw)
        cls.build = next(item for item in load_builds() if item.id == "vv1")

    def test_disabled_hidden_command_seven_only(self) -> None:
        self.assertFalse(self.raw["enabled"])
        self.assertNotIn(self.raw["id"], {item.id for item in load_fun_patches()})
        contract = self.raw["transaction_contract"]
        self.assertEqual((contract["command"], contract["price"]), (7, 1_000_000))
        self.assertIsNone(contract["ownership"])
        folded = json.dumps(self.raw).casefold()
        self.assertNotIn("command 6", folded)
        self.assertNotIn("command 8", folded)
        self.assertNotIn("remove state", folded)
        self.assertEqual(
            {int(item["offset"], 0) for item in self.raw["patches"]},
            {0x358DC, 0x35AB0},
        )

    def test_fingerprint_geometry_guards_and_native_writer(self) -> None:
        source = STOCK.read_bytes()
        self.assertEqual(len(source), 581_632)
        self.assertEqual(
            sha(source),
            "1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D",
        )
        self.assertEqual(source[0x52DC9:0x52DD4].hex().upper(), "68082E4800FF1510704500")
        self.assertEqual(source[0x52DDE:0x52DEC].hex().upper(), "8B35D470450068FC2D480057FFD6")
        self.assertEqual(self.map["section"]["raw_offset"], "0x8E000")
        self.assertEqual(self.map["section"]["rva"], "0x90000")
        self.assertEqual(self.map["section"]["va"], "0x490000")
        self.assertIn("0x437230 native skill writer", self.map["absolute_references"])
        self.assertEqual(self.map["base_relocations"], [])

    def test_thiscall_transport_modal_and_result_abis(self) -> None:
        page = bytes.fromhex(
            self.raw["pe_append_transaction"]["layouts"]["collection_progression"]["append_bytes"]
        )
        entry_offset = int(self.map["offsets"]["entry"], 0)
        self.assertTrue(page[entry_offset:entry_offset + 8].startswith(bytes.fromhex("5589E5535689CE57")))
        confirmation = self.map["confirmation"]
        self.assertEqual(confirmation["load_library_iat"], "0x457010")
        self.assertEqual(confirmation["get_proc_address_iat"], "0x4570D4")
        self.assertEqual(confirmation["return_matrix"], {"0": 0, "1": 1, "2": 0, "arbitrary_non_1": 0})
        exports = self.map["companion"]["exports"]
        self.assertIn("ShowVV1FullMasteryMenu", exports)
        self.assertIn("ShowVV1FullMasteryResult", exports)
        self.assertEqual(
            self.map["command_abi"]["result"],
            "stdcall(status,changed,retained_export); ret 12; retained export itself is stdcall(status,changed), ret 8",
        )
        entry = page[entry_offset:int(self.map["offsets"]["walker"], 0)]
        load = bytes.fromhex("FF1510704500")
        lookup = bytes.fromhex("FF15D4704500")
        deduct = bytes.fromhex("812A40420F00")
        self.assertGreaterEqual(entry.find(load), 0)
        self.assertGreaterEqual(entry.find(lookup), 0)
        self.assertGreater(entry.find(deduct), entry.find(lookup))
        self.assertNotIn(load, entry[entry.find(deduct):])
        self.assertNotIn(lookup, entry[entry.find(deduct):])
        result_offset = int(self.map["offsets"]["result_resolver"], 0)
        result_helper = page[result_offset:result_offset + 0x40]
        self.assertNotIn(load, result_helper)
        self.assertNotIn(lookup, result_helper)

    def test_walker_domain_exclusions_bound_and_writer_order(self) -> None:
        excluded = [
            {"occupied": False, "health": 100, "special": 0, "skills": {name: object() for name in SKILLS}},
            {"occupied": True, "health": 0, "special": 0, "skills": {name: object() for name in SKILLS}},
            {"occupied": True, "health": 100, "special": 199, "skills": {name: object() for name in SKILLS}},
        ]
        changed = {
            "occupied": True,
            "health": 1,
            "special": 0,
            "skills": dict(zip(SKILLS, (99, 90, 100, 0, 88))),
            "preference": 77,
        }
        records = [*excluded, changed]
        count, invalid, calls = semantic_walk(records, True)
        self.assertEqual((count, invalid), (1, False))
        self.assertEqual(calls, [(3, 2, 1), (3, 4, 10), (3, 5, 100), (3, 3, 12)])
        self.assertEqual(changed["preference"], 77)
        self.assertEqual(changed["skills"], {name: 100 for name in SKILLS})

        empty = {"occupied": False, "health": 0, "special": 0, "skills": {name: 100 for name in SKILLS}}
        bounded = [deepcopy(empty) for _ in range(256)]
        for index in (0, 255):
            bounded[index] = {"occupied": True, "health": 1, "special": 0, "skills": {name: (99 if name == "research" else 100) for name in SKILLS}}
        self.assertEqual(semantic_walk(bounded, False)[:2], (2, False))
        invalid_record = [{"occupied": True, "health": 1, "special": 0, "skills": {name: (-1 if name == "farming" else 100) for name in SKILLS}}]
        self.assertEqual(semantic_walk(invalid_record, True), (0, True, []))

    def test_transaction_matrix_is_atomic_and_unsigned(self) -> None:
        base = [{"occupied": True, "health": 100, "special": 0, "skills": {name: (99 if name == "farming" else 100) for name in SKILLS}}]
        self.assertEqual(transaction(deepcopy(base), 999_999, 1), ("insufficient", 999_999, []))
        self.assertEqual(
            transaction(deepcopy(base), 1_000_000, 1, False),
            ("unavailable", 1_000_000, []),
        )
        for answer in (0, 2, 77):
            self.assertEqual(transaction(deepcopy(base), 1_000_000, answer), ("cancel", 1_000_000, []))
        mastered = deepcopy(base)
        mastered[0]["skills"] = {name: 100 for name in SKILLS}
        self.assertEqual(transaction(mastered, 1_000_000, 1), ("no_change", 1_000_000, []))

        def finish(records):
            records[0]["skills"] = {name: 100 for name in SKILLS}

        self.assertEqual(
            transaction(deepcopy(base), 1_000_000, 1, mutate_before_final=finish),
            ("no_change", 1_000_000, []),
        )
        status, balance, calls = transaction(deepcopy(base), 0xFFFFFFFF, 1)
        self.assertEqual((status, balance), ("committed", 0xFFFFFFFF - 1_000_000))
        self.assertEqual(calls, [(0, 1, 1)])

    def test_exact_result_copy_and_buffer_bounds(self) -> None:
        source = (ROOT / "native" / "vv1_full_mastery_candidate" / "vv1_full_mastery_candidate.c").read_text(encoding="utf-8")
        for text in (
            "Everyone is already fully mastered.",
            "Not enough tech points.",
            "Full Mastery cannot be applied because an eligible villager has ",
            "No tech points have been deducted.",
            "Fully mastered %u villagers.",
        ):
            self.assertIn(text, source)
        longest = (
            "Full Mastery cannot be applied because an eligible villager has an "
            "out-of-range skill.\r\nNo tech points have been deducted."
        )
        self.assertLessEqual(len(longest.encode("ascii")) + 1, 256)

    def test_all_modes_checksum_composition_and_exact_uninstall(self) -> None:
        others = [
            item for item in load_fun_patches()
            if item.game_id == "vv1" and item.id != "vv1_enable_origins_exclusive_features"
        ]
        old_origins = next(item for item in load_fun_patches() if item.id == "vv1_enable_origins_exclusive_features")
        for mode in MODES:
            with self.subTest(mode=mode):
                baseline, _ = render_patched_bytes(STOCK, self.build, mode)
                rendered, applied = render_patched_bytes(
                    STOCK, self.build, mode, _fun_patches_override=[self.candidate, *others]
                )
                self.assertEqual(len(rendered), 0x90000)
                self.assertEqual(rendered[0x8E000:0x90000], bytes.fromhex(self.raw["pe_append_transaction"]["layouts"][mode]["append_bytes"]))
                checksum_offset, _ = _pe_checksum_layout(rendered)
                stored = struct.unpack_from("<I", rendered, checksum_offset)[0]
                copy = bytearray(rendered)
                struct.pack_into("<I", copy, checksum_offset, 0)
                self.assertEqual(stored, pe_checksum(copy))
                self.assertIn(f"feature:{self.candidate.id}", {item["owner"] for item in applied})
                candidate_only, _ = render_patched_bytes(STOCK, self.build, mode, _fun_patches_override=[self.candidate])
                work = bytearray(candidate_only)
                _remove_feature_bytes(work, self.candidate, mode)
                self.assertEqual(work, baseline)
                with self.assertRaises(PatcherError):
                    render_patched_bytes(STOCK, self.build, mode, _fun_patches_override=[self.candidate, old_origins])

    def test_corruption_fails_closed_and_generation_is_deterministic(self) -> None:
        rendered, _ = render_patched_bytes(
            STOCK, self.build, "collection_progression", _fun_patches_override=[self.candidate]
        )
        for offset in (0x358DC, 0x2B8, len(rendered) - 1):
            with self.subTest(offset=hex(offset)):
                work = bytearray(rendered)
                work[offset] ^= 1
                with self.assertRaises(PatcherError):
                    _remove_feature_bytes(work, self.candidate, "collection_progression")
        before = {path: sha(path.read_bytes()) for path in (MANIFEST, MAP, DOC, DLL)}
        subprocess.run([sys.executable, str(GENERATOR)], cwd=ROOT, check=True)
        after = {path: sha(path.read_bytes()) for path in (MANIFEST, MAP, DOC, DLL)}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
