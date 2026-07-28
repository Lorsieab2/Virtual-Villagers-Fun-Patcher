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


STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"
GENERATOR = ROOT / "scripts" / "build_vv2_full_mastery_candidate.py"
MANIFEST = ROOT / "data" / "candidates" / "vv2_full_mastery_all_candidate.json"
MAP = ROOT / "data" / "candidates" / "vv2_full_mastery_all_candidate_map.json"
DOC = ROOT / "docs" / "vv2-full-mastery-stage-a-candidate.md"
DLL = ROOT / "data" / "candidates" / "VVFP VV2 Full Mastery Candidate.dll"
MODES = (
    "collection_progression",
    "immediate_fixed",
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
)
SKILLS = ("farming", "building", "research", "healing", "parenting")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


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


def transaction(
    records: list[dict[str, object]],
    balance: int,
    confirm: int,
    mutate_before_final=None,
) -> tuple[str, int, int, int]:
    if balance < 1_000_000:
        return "insufficient", balance, 0, 0
    first, _ = semantic_walk(records, False)
    if first == 0:
        return "no_change", balance, 0, 0
    if confirm != 1:
        return "cancel", balance, 0, 0
    if mutate_before_final:
        mutate_before_final(records)
    if balance < 1_000_000:
        return "insufficient", balance, 0, 0
    final, _ = semantic_walk(records, False)
    if final == 0:
        return "no_change", balance, 0, 0
    balance -= 1_000_000
    committed, snapshot = semantic_walk(records, True)
    return "committed", balance, committed, sum(1 for item in snapshot if item)


class VV2FullMasteryCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.map = json.loads(MAP.read_text(encoding="utf-8"))
        cls.candidate = FunPatch(cls.raw)
        cls.build = next(item for item in load_builds() if item.id == "vv2")

    def test_candidate_is_certified_visible_and_command_seven_only(self) -> None:
        self.assertTrue(self.raw["enabled"])
        self.assertEqual(self.raw["id"], "vv2_full_mastery_all_stage_a_candidate")
        self.assertIn(self.raw["id"], {item.id for item in load_fun_patches()})
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
        # push ebp; mov ebp,esp; push ebx; push esi; mov esi,ecx; push edi.
        # The saved ESI is restored by the existing epilogue.
        self.assertTrue(entry.startswith(bytes.fromhex("5589E5535689CE57")))

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
        longest = (
            "Fully mastered 4294967295 villagers.\r\n"
            "4294967295 villagers became Esteemed Elders.\r\n"
            "4294967295 fully mastered villagers remain without the Elder marker "
            "because the native 50-totem limit was reached."
        )
        self.assertLessEqual(len(longest.encode("ascii")) + 1, 256)

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

    def test_generator_is_deterministic(self) -> None:
        before = {
            path: sha(path.read_bytes())
            for path in (MANIFEST, MAP, DOC, DLL)
        }
        subprocess.run([sys.executable, str(GENERATOR)], cwd=ROOT, check=True)
        after = {
            path: sha(path.read_bytes())
            for path in (MANIFEST, MAP, DOC, DLL)
        }
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
