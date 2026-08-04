from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    FunPatch,
    PatcherError,
    _pe_checksum_layout,
    _certified_vv4_full_mastery_records,
    _remove_feature_bytes,
    _remove_companion_files,
    load_builds,
    load_fun_patches,
    pe_checksum,
    render_patched_bytes,
    VV4_FULL_MASTERY_CANDIDATE_PATHS,
    VV4_FULL_MASTERY_LEGACY_ASSET_KEYS,
    VV4_FULL_MASTERY_LEGACY_STATIC_ASSET_KEYS,
)
from vv4_individual_mastery import (  # noqa: E402
    NOOP_MESSAGE,
    PRICE,
    apply_plan,
    plan_transaction,
)


STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Tree of Life.exe"
GENERATOR = ROOT / "scripts" / "build_vv4_full_mastery_candidate.py"
BASE = ROOT / "data" / "candidates" / "vv4_origins_full_mastery_base_candidate.json"
FEATURE = ROOT / "data" / "candidates" / "vv4_full_mastery_all_candidate.json"
MAP = ROOT / "data" / "candidates" / "vv4_full_mastery_all_candidate_map.json"
DOC = ROOT / "docs" / "vv4-full-mastery-stage-a-candidate.md"
PLAYTEST_INSTRUCTIONS = ROOT / "docs" / "vv4-full-mastery-playtest-instructions.txt"
DLL = ROOT / "data" / "candidates" / "VVFP VV4 Full Mastery Candidate.dll"
PROVENANCE = ROOT / "assets" / "candidates" / "vv4_full_mastery" / "provenance"
MODES = (
    "collection_progression",
    "immediate_fixed",
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
)
SKILLS = ("farming", "parenting", "healing", "research", "building")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def rel32_targets(code: bytes, base: int) -> list[int]:
    targets = []
    for offset in range(len(code) - 4):
        if code[offset] == 0xE8:
            displacement = int.from_bytes(
                code[offset + 1 : offset + 5], "little", signed=True
            )
            targets.append(base + offset + 5 + displacement)
    return targets


def walk(records: list[dict[str, object]], commit: bool):
    changed = 0
    writer_calls: list[tuple[int, int, int]] = []
    writer_calls: list[tuple[int, int, float]] = []
    for index, record in enumerate(records):
        if not record["active"] or int(record["health"]) <= 0:
            continue
        skills = record["skills"]
        assert isinstance(skills, dict)
        values = [float(skills[name]) for name in SKILLS]
        if any(not (0.0 <= value <= 100.0) for value in values):
            return 0, True, []
        if all(value == 100 for value in values):
            continue
        changed += 1
        if commit:
            for skill_index, name in enumerate(SKILLS):
                current = int(skills[name])
                if current < 100:
                    writer_calls.append((index, skill_index, 100.0 - current))
                    skills[name] = 100.0
    return changed, False, writer_calls


def transaction(records, balance, confirm, mutate=None):
    if balance < 1_000_000:
        return "insufficient", balance, [], []
    changed, invalid, _ = walk(records, False)
    if invalid:
        return "invalid", balance, [], []
    if changed == 0:
        return "no_change", balance, [], []
    if confirm != 1:
        return "cancel", balance, [], []
    if mutate:
        mutate(records)
    changed, invalid, _ = walk(records, False)
    if invalid:
        return "invalid", balance, [], []
    if changed == 0:
        return "no_change", balance, [], []
    if balance < 1_000_000:
        return "insufficient", balance, [], []
    balance -= 1_000_000
    committed, invalid, calls = walk(records, True)
    assert not invalid and committed == changed
    return "committed", balance, calls, []


class VV4FullMasteryCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_raw = json.loads(BASE.read_text(encoding="utf-8"))
        cls.feature_raw = json.loads(FEATURE.read_text(encoding="utf-8"))
        cls.map = json.loads(MAP.read_text(encoding="utf-8"))
        cls.base = FunPatch(cls.base_raw)
        cls.feature = FunPatch(cls.feature_raw)
        cls.build = next(item for item in load_builds() if item.id == "vv4")

    def test_vv4_cure_truth_is_withdrawn_in_manifest_and_transparency(self):
        active_text = json.dumps(self.base_raw, ensure_ascii=False).casefold()
        self.assertNotIn("plus cure all villagers for 30,000 tech points", active_text)
        self.assertNotIn("cure all villagers clears sickness", active_text)
        for phrase in ("withdrawn", "unavailable", "unreachable", "not part of this playtest"):
            self.assertIn(phrase, active_text)

        transparency = (ROOT / "docs" / "transparency-log.md").read_text(encoding="utf-8")
        marker = "#### Enable Origins-Exclusive Features (`vv4_enable_origins_exclusive_features`)"
        self.assertIn(marker, transparency)
        vv4_section = transparency.split(marker, 1)[1].split("\n#### ", 1)[0]
        self.assertNotIn("Plus Cure all Villagers for 30,000 tech points", vv4_section)
        self.assertNotIn("Cure all Villagers clears sickness", vv4_section)
        folded = vv4_section.casefold()
        for phrase in ("withdrawn", "unavailable", "unreachable", "not part of this playtest"):
            self.assertIn(phrase, folded)

    def test_playtest_instructions_mark_png_as_provenance_only(self):
        instructions = PLAYTEST_INSTRUCTIONS.read_text(encoding="utf-8")
        folded = instructions.casefold()
        self.assertIn(r"images\btn_upgrades_297x35.png", folded)
        self.assertIn("provenance", folded)
        self.assertIn("not a runtime dependency", folded)
        self.assertIn("native cached ordinal `0x8c`", folded)
        self.assertIn("btn_trophies.png", folded)
        self.assertIn("withdrawn, unavailable, unreachable", folded)
        self.assertNotIn("runtime dependency: images\\btn_upgrades_297x35.png", folded)

    def test_d33_c28_stock_candidate_is_catalog_visible(self):
        self.assertTrue(self.base_raw["enabled"])
        self.assertTrue(self.feature_raw["enabled"])
        active = {item.id: item for item in load_fun_patches()}
        self.assertIn("vv4_enable_origins_exclusive_features", active)
        self.assertIn(self.feature_raw["id"], active)
        self.assertIn("D33/C28", self.feature_raw["certification_status"])
        self.assertEqual(self.feature_raw["dependencies"], [self.base_raw["id"]])
        contract = self.feature_raw["transaction_contract"]
        self.assertEqual((contract["command"], contract["price"]), (7, 1_000_000))
        self.assertIsNone(contract["ownership"])
        folded = json.dumps(self.feature_raw).casefold()
        self.assertNotIn("command 6", folded)
        self.assertNotIn("command 8", folded)
        self.assertNotIn("remove state", folded)

    def test_every_legacy_custom_asset_key_fails_closed(self):
        def assert_rejected(mutated_map):
            mutated_map["ui_asset_gate"]["status"] = "independent metadata recertification GO"
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                base = deepcopy(self.base_raw)
                feature = deepcopy(self.feature_raw)
                base["enabled"] = True
                feature["enabled"] = True
                paths = {"base": root / "base.json", "feature": root / "feature.json", "map": root / "map.json"}
                paths["base"].write_text(json.dumps(base), encoding="utf-8")
                paths["feature"].write_text(json.dumps(feature), encoding="utf-8")
                paths["map"].write_text(json.dumps(mutated_map), encoding="utf-8")
                with mock.patch.dict(VV4_FULL_MASTERY_CANDIDATE_PATHS, paths, clear=False):
                    with self.assertRaisesRegex(PatcherError, "legacy .*custom-asset metadata is forbidden"):
                        _certified_vv4_full_mastery_records({})

        for key in sorted(VV4_FULL_MASTERY_LEGACY_ASSET_KEYS):
            with self.subTest(level="ui_asset_gate", key=key):
                mutated = deepcopy(self.map)
                mutated["ui_asset_gate"][key] = None
                assert_rejected(mutated)
        for key in sorted(VV4_FULL_MASTERY_LEGACY_STATIC_ASSET_KEYS):
            with self.subTest(level="static_asset_contract", key=key):
                mutated = deepcopy(self.map)
                mutated["ui_asset_gate"]["runtime_wrapper_contract"]["static_asset_contract"][key] = None
                assert_rejected(mutated)

    def test_catalog_visible_and_expanded_mode_fail_closed(self):
        vv4_records = {
            item.id
            for item in load_fun_patches()
            if item.game_id == "vv4"
        }
        self.assertIn("vv4_enable_origins_exclusive_features", vv4_records)
        self.assertIn("vv4_full_mastery_all_stage_a_candidate", vv4_records)
        for mode in ("experimental_expanded_256", "experimental_expanded_256_progression"):
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(PatcherError, "ON HOLD"):
                    render_patched_bytes(
                        STOCK,
                        self.build,
                        mode,
                        fun_patch_ids=(
                            "vv4_enable_origins_exclusive_features",
                            "vv4_full_mastery_all_stage_a_candidate",
                        ),
                    )

    def test_exact_live_geometry_constructor_and_nonoverlap_contract(self):
        payload = next(
            item
            for item in self.base_raw["patches"]
            if int(item["offset"], 0) == 0x89373
        )
        code = bytes.fromhex(payload["after"])
        tech = code[0x40:0xC0]
        detail = code[0x100:0x180]
        helper = code[0xC0:0xE2]
        self.assertIn(bytes.fromhex("68E0EE4B006A0D"), tech)
        self.assertIn(bytes.fromhex("6838F54B006A02"), detail)
        self.assertNotIn(bytes.fromhex("83F863"), tech)
        self.assertNotIn(bytes.fromhex("83F823"), tech)
        self.assertNotIn(bytes.fromhex("83F863"), detail)
        self.assertNotIn(bytes.fromhex("83F823"), detail)
        self.assertNotIn("0x401470", json.dumps(self.map))
        self.assertNotIn("0x4014B0", json.dumps(self.map))
        factory_info = self.map["candidate_ui_payload"]["native_factory"]
        factory = code[0xBC4 : 0xBC4 + factory_info["length"]]
        self.assertEqual(factory_info["length"], 145)
        self.assertEqual(code[0xC84:0xC8D], b"Upgrades\0")
        for target in (0x470C5C, 0x44CCF0, 0x44CB60, 0x401C20, 0x401600, 0x401630, 0x470B7B):
            self.assertIn(target, rel32_targets(factory, 0x489F37))
        self.assertLess(factory.index(bytes.fromhex("6A14")), factory.index(bytes.fromhex("688C000000")))
        self.assertIn(bytes.fromhex("688C00000089D9E8"), factory)
        self.assertIn(bytes.fromhex("6A00566A046A4850"), factory)
        self.assertIn(bytes.fromhex("FF74241489F9E8"), factory)
        self.assertNotIn(b"Images\\btn_upgrades", code)
        self.assertIn(0x40C190, rel32_targets(tech, 0x4893B3))  # sub_40C190
        self.assertIn(0x40C190, rel32_targets(detail, 0x489473))  # sub_40C190
        self.assertNotIn(b"\xA0\xD8\x40", tech + detail)
        self.assertIn(bytes.fromhex("6A01FFD2"), helper)
        self.assertIn(bytes.fromhex("C7437400000000"), helper)
        self.assertIn(bytes.fromhex("8BCB"), helper)
        self.assertIn(bytes.fromhex("8BCBE8"), helper)
        call_at = helper.index(b"\xE8")
        jump_at = helper.index(b"\xE9")
        self.assertEqual(
            0x489433 + call_at + 5 + int.from_bytes(helper[call_at + 1 : call_at + 5], "little", signed=True),
            0x40C340,
        )
        self.assertEqual(
            0x489433 + jump_at + 5 + int.from_bytes(helper[jump_at + 1 : jump_at + 5], "little", signed=True),
            0x43E23D,
        )
        self.assertEqual(self.map["candidate_ui_payload"]["destructor_helper"]["length"], 34)
        self.assertEqual(
            self.map["candidate_ui_payload"]["destructor_helper"]["no_wrapper_branch_va"],
            "0x489449",
        )
        self.assertEqual(self.map["ui_asset_gate"]["tech_wrapper"]["helper_length"], 34)
        self.assertEqual(
            self.map["ui_asset_gate"]["runtime_wrapper_contract"],
            {
                "nonnull_outer_and_inner": {"attach": True, "tech_slot": "this+0x74"},
                "null_outer": {"attach": False, "tech_slot": None},
                "null_inner": {"attach": False, "scalar_destroy_flag": 1, "tech_slot": None},
                "loader_null": {"raw_deallocator": "sub_470B7B", "abi": "cdecl push pointer; caller add esp,4", "virtual_destructor": False},
                "static_asset_contract": {"ordinal": "0x8C", "asset": "btn_trophies.png", "dimensions": [100, 39], "bounds_half_open": [72, 4, 172, 43], "ownership": "borrowed native cache"},
                "runtime_dimension_accessors": "none; wrapper vtable +0x0C/+0x10 are not image dimensions",
            },
        )
        ui = self.map["ui_asset_gate"]
        self.assertEqual(ui["runtime_source"], r"native cached VV4 Images\btn_trophies.png")
        self.assertEqual(ui["ordinal"], "0x8C")
        self.assertEqual(ui["dimensions"], [100, 39])
        self.assertEqual(ui["bounds_half_open"], [72, 4, 172, 43])
        self.assertIsNone(ui["custom_runtime_companion"])
        self.assertEqual(ui["factory"], "sub_401C20")
        self.assertEqual(ui["local"], [72, 4])
        self.assertEqual(ui["events"], {"tech": 13, "detail": 2})
        self.assertEqual(ui["add_child"], "sub_40C190")
        self.assertEqual(ui["status"], "independent metadata recertification GO")
        self.assertEqual(self.map["metadata_recertification"]["status"], "independent metadata recertification GO")
        self.assertEqual(self.map["metadata_enablement_audit"]["status"], "GO")
        self.assertEqual(self.map["playtest3_withdrawal"]["fault_va"], "0x489E0C")
        self.assertEqual(self.map["candidate_ui_payload"]["result_call_repairs"], [{"call_va": "0x4897CA", "before_target": "0x489573", "after_target": "0x489ACA", "before": "E8A4FDFFFF", "after": "E8FB020000"}, {"call_va": "0x489ABB", "before_target": "0x489573", "after_target": "0x489ACA", "before": "E8B3FAFFFF", "after": "E80A000000"}])
        helper = self.map["candidate_ui_payload"]["result_helper"]
        self.assertEqual(helper["va"], "0x489ACA")
        self.assertEqual(helper["file_offset"], "0x89ACA")
        self.assertEqual(helper["length"], 54)
        self.assertEqual(helper["guard_length"], 64)
        self.assertEqual(helper["bytes"], "53568B5C240C8B74241068E39E4800FF15E0A1480085C0741868EE9E480050FF15DCA1480085C074086A0053566A00FFD05E5BC20800")
        self.assertNotIn("0x489583", json.dumps(self.map))
        self.assertEqual(self.map["acceptance_commit"], "8182c235548bc92f304e5571ed61ada3c5abfa4b")
        self.assertEqual(self.map["independent_recertification"]["review"], "D19")
        self.assertEqual(self.map["independent_recertification"]["status"], "independent payload recertification GO")
        self.assertEqual(self.map["independent_recertification"]["commit"], "8182c235548bc92f304e5571ed61ada3c5abfa4b")
        self.assertEqual(self.map["independent_recertification"]["scope"], "VV4 Full Mastery stock-mode candidate only; Expanded-256 ON HOLD/fail-closed")
        self.assertEqual(
            self.map["independent_recertification"]["hashes"],
            {
                "native_factory": "58E21A9597EB6ABF6949A1E607C3B607FABAF1AE5D280D899A062F5D021ACE21",
                "helper": "C7379FB1AFDDD44F06CF48FAEED14C1701D796F5FC2568E10745337DADE13DB1",
                "tech_constructor": "1D710074D6F5717A420646B2DCEE2BCC351754B4DC0CCFB5A32F586E2E258BDC",
                "detail_constructor": "AC2A88CBD0B7805941EA34261D765F4A727187B35B5443BFB7CDEA8DF43A7E8C",
                "command7_slot": "023CF384A52CB6A6A49511B8B069B952718DC70E771FEE15CAC8A0777FB5F6DE",
                "cure": "2BB7A32344293DCACB4D0359818C6839AC1FBBAEE8F9E3D00DB59C274238D726",
                "dll": "4E1A83683A875EFE6F67116CDD862927BE1ABCB17DB7AE18143E58E98EAD01E7",
            },
        )
        self.assertEqual(sha((PROVENANCE / "VV4 mockup.jpg").read_bytes()), "B404465B960BE3875F4DF0BFE32796B8045A9E938A356FF33448331AB2840A24")
        withdrawal = self.map["playtest_withdrawal"]
        self.assertEqual(withdrawal["status"], "HARD WITHDRAWN")
        self.assertEqual(withdrawal["crash"], {"exception": "0xC0000005", "fault_rva": "0x21570", "fault_va": "0x421570", "instruction": "8B4108", "observed_count": 2})
        self.assertEqual(withdrawal["malformed_sub_401C20_args"]["tech"], {"event": 4, "asset": "0x48", "x": "0x489F37", "y": 3, "parent": 1, "flags": 13})
        self.assertEqual(withdrawal["malformed_sub_401C20_args"]["detail"], {"event": 4, "asset": "0x48", "x": "0x489F37", "y": 3, "parent": 1, "flags": 2})

    def test_runtime_null_success_attach_and_cleanup(self):
        """Model the emitted null/nonnull ownership behavior without launching the game."""

        def attach_result(wrapper, tech=False, existing_slot=None):
            slot = existing_slot
            attached = []
            if wrapper is None:
                if tech:
                    slot = None
                return slot, attached
            if tech:
                slot = wrapper
            attached.append(wrapper)
            return slot, attached

        slot, attached = attach_result(None, tech=True, existing_slot=None)
        self.assertIsNone(slot)
        self.assertEqual(attached, [])
        wrapper = object()
        slot, attached = attach_result(wrapper, tech=True, existing_slot=None)
        self.assertIs(slot, wrapper)
        self.assertEqual(attached, [wrapper])
        slot, attached = attach_result(wrapper, tech=False)
        self.assertIsNone(slot)
        self.assertEqual(attached, [wrapper])

        # The paired Tech destructor is null/repeated safe and restores ECX for
        # stock cleanup on both the null and non-null paths.
        parent = object()

        def helper_cleanup(slot):
            destroyed = []
            if slot is not None:
                destroyed.append(slot)
                slot = None
            return parent, slot, destroyed

        ecx, slot, destroyed = helper_cleanup(None)
        self.assertIs(ecx, parent)
        self.assertIsNone(slot)
        self.assertEqual(destroyed, [])
        ecx, slot, destroyed = helper_cleanup(None)
        self.assertIs(ecx, parent)
        self.assertIsNone(slot)
        self.assertEqual(destroyed, [])
        wrapper = object()
        ecx, slot, destroyed = helper_cleanup(wrapper)
        self.assertIs(ecx, parent)
        self.assertIsNone(slot)
        self.assertEqual(destroyed, [wrapper])

    def test_exact_fingerprint_layout_bounds_and_fixed_base(self):
        source = STOCK.read_bytes()
        self.assertEqual(len(source), 929_792)
        self.assertEqual(
            sha(source),
            "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220",
        )
        self.assertEqual(self.map["layouts"]["collection_progression"]["bound"], 150)
        self.assertEqual(self.map["layouts"]["experimental_expanded_256"]["bound"], 256)
        self.assertEqual(self.map["references"]["base_relocations"], [])
        for mode in MODES:
            layout = self.base_raw["pe_append_transaction"]["layouts"][mode]
            self.assertEqual(layout["append_offset"], "0xE3000")
            self.assertEqual(layout["append_length"], 0x2000)
            self.assertEqual(layout["header_patches"][2]["offset"], "0x2C0")
            self.assertTrue(bytes.fromhex(layout["header_patches"][2]["after"]).startswith(b".vv4fm\0\0"))

    def test_native_writer_evaluator_semantics_and_domain_gate(self):
        excluded = [
            {"active": False, "health": 100, "skills": {name: object() for name in SKILLS}},
            {"active": True, "health": 0, "skills": {name: object() for name in SKILLS}},
        ]
        target = {"active": True, "health": 1, "skills": dict(zip(SKILLS, (99, 90, 100, 88, 0))), "unrelated": 77}
        records = [*excluded, target]
        changed, invalid, calls = walk(records, True)
        self.assertEqual((changed, invalid), (1, False))
        self.assertEqual(calls, [(2, 0, 1.0), (2, 1, 10.0), (2, 3, 12.0), (2, 4, 100.0)])
        self.assertEqual(target["unrelated"], 77)
        self.assertEqual(target["skills"], {name: 100.0 for name in SKILLS})
        for invalid in (-1.0, 100.01, float("inf"), float("nan")):
            invalid_record = [{"active": True, "health": 1, "skills": {name: (invalid if name == "research" else 100.0) for name in SKILLS}}]
            self.assertEqual(walk(invalid_record, True), (0, True, []))

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
        self.assertEqual(
            (status, balance, calls, awards),
            ("committed", 0xFFFFFFFF - 1_000_000, [(0, 0, 1.0)], []),
        )

    def test_exact_result_export_strings_and_abi(self):
        exports = self.map["companion"]["exports"]
        self.assertIn("ShowVV4FullMasteryResult", exports)
        self.assertIn("_ShowVV4FullMasteryResult@8", exports)
        self.assertIn("ShowOriginsVillageWideResult@20", exports)
        source = (ROOT / "native" / "vv4_full_mastery_candidate" / "vv4_full_mastery_candidate.c").read_text(encoding="utf-8")
        for text in (
            "Everyone is already fully mastered.",
            "No tech points have been deducted.",
            "Not enough tech points.",
            "out-of-range skill.",
            "Fully mastered %u villagers.",
        ):
            self.assertIn(text, source)
        resources = (ROOT / "native" / "vv4_full_mastery_candidate" / "vv4_full_mastery_candidate.rc").read_text(encoding="utf-8")
        tech_resource = resources.split("201 DIALOGEX", 1)[1].split("202 DIALOGEX", 1)[0]
        isolated = resources.split("203 DIALOGEX", 1)[1]
        self.assertNotIn('1005,', tech_resource)
        self.assertIn('PUSHBUTTON  "Buy", 1007', isolated)
        self.assertNotIn('1005,', isolated)
        self.assertNotIn('1006,', isolated)
        self.assertNotIn('1008,', isolated)
        self.assertIn("ID_BUY_FIRST + 5", source)

    def test_individual_mastery_is_enabled_only_for_certified_stock_mode(self):
        contract = self.map["individual_full_mastery"]
        self.assertTrue(contract["status"].startswith("GO"))
        self.assertTrue(self.feature_raw["enabled"])
        self.assertIn("stock-mode Detail route", contract["emitted"])
        self.assertEqual(contract["implementation_source"], "src/vv4_individual_mastery.py")
        self.assertEqual(contract["required_contract"]["command"], 1)
        self.assertTrue(contract["required_contract"]["five_float_complete_dry_run"])
        self.assertIn("same_physical_index_reacquisition", contract["required_contract"])
        self.assertFalse(contract["required_contract"]["direct_skill_stores"])

    def test_individual_native_transaction_model_is_two_pass_and_no_store(self):
        record = {"active": True, "health": 1, "skills": [99.0, 90.0, 100.0, 88.0, 0.0]}
        records = [record]
        calls = []
        deductions = []
        plan = plan_transaction(records, 0, PRICE, True, lambda: (0, records, PRICE))
        self.assertEqual(plan.status, "commit")
        self.assertEqual([(c.skill_index, c.delta) for c in plan.calls], [(0, 1.0), (1, 10.0), (3, 12.0), (4, 100.0)])
        self.assertEqual(plan.deduction, PRICE)
        apply_plan(plan, lambda index, skill, delta: calls.append((index, skill, delta)), deductions.append)
        self.assertEqual(calls, [(0, 0, 1.0), (0, 1, 10.0), (0, 3, 12.0), (0, 4, 100.0)])
        self.assertEqual(deductions, [PRICE])
        self.assertEqual(record["skills"], [99.0, 90.0, 100.0, 88.0, 0.0])

        all_done = [{"active": True, "health": 1, "skills": [100.0] * 5}]
        noop = plan_transaction(all_done, 0, 0, True, lambda: (0, all_done, 0))
        self.assertEqual((noop.status, noop.message, noop.calls, noop.deduction), ("no_change", NOOP_MESSAGE, (), 0))
        self.assertEqual(plan_transaction(records, 0, PRICE, False, lambda: (0, records, PRICE)).status, "cancel")
        self.assertEqual(plan_transaction(records, 0, PRICE, True, lambda: (1, records, PRICE)).status, "race")
        invalid = [{"active": True, "health": 1, "skills": [float("nan")] + [100.0] * 4}]
        self.assertEqual(plan_transaction(invalid, 0, PRICE, True, lambda: (0, invalid, PRICE)).status, "invalid")

    def test_individual_emitted_helper_is_guarded_and_native_only(self):
        installed = self.map["layouts"]["collection_progression"]["slot_map"]["installed"]
        helper = bytes.fromhex(installed["individual_bytes"])
        base = int(installed["individual_va"], 16)
        targets = rel32_targets(helper, base)
        self.assertEqual(targets.count(0x41FE70), 2)
        self.assertEqual(targets.count(0x466040), 2)
        self.assertEqual(targets.count(0x46AD80), 5)
        self.assertEqual(targets.count(0x41E300), 1)
        self.assertEqual(targets.count(0x489ACA), 5)
        self.assertEqual(targets.count(0x740C00), 1)  # dedicated confirmation; never command-7 generic helper
        self.assertIn(b"\x89\x7D\xF0", helper)  # saved physical index at [ebp-0x10]
        self.assertIn(b"\xC7\x45\xEC", helper)  # changed-mask local at [ebp-0x14]
        self.assertNotIn(b"\x89\x7D\xFC", helper)  # never clobber saved EBX
        self.assertNotIn(b"\x83\xC4\x04", helper)  # sub_466040 is callee-clean
        self.assertTrue(helper.endswith(b"\x8D\x65\xF4\x5F\x5E\x5B\x5D\xC3"))
        self.assertIn(b"\x68\x60\x79\xFE\xFF", helper)  # push -100000
        for raw_store in (b"\xC7\x83\x5C\x1C", b"\xC7\x83\x60\x1C", b"\xC7\x83\x64\x1C", b"\xC7\x83\x68\x1C", b"\xC7\x83\x6C\x1C"):
            self.assertNotIn(raw_store, helper)
        self.assertEqual(installed["individual_status"], "emitted in installed page; stock-mode route catalog-visible after D33/C28 GO")
        self.assertIn("stock-mode Detail route", self.map["individual_full_mastery"]["emitted"])
        contract = installed["individual_contract"]
        self.assertEqual(contract["confirmation"], "Grant Full Mastery to this villager for 100,000 tech points?\r\nPress OK to confirm, or Cancel.")
        self.assertIn("exact Float32 100.0", contract["post_write_verification"])
        self.assertIn("partial changes may remain", contract["partial_commit_policy"])
        caption = int(installed["strings"]["caption"], 16).to_bytes(4, "little")
        message_keys = ("individual_success", "individual_noop", "individual_insufficient", "individual_invalid", "individual_failure")
        for key in message_keys:
            message = int(installed["strings"][key], 16).to_bytes(4, "little")
            self.assertEqual(helper.count(b"\x68" + message + b"\x68" + caption), 1)
        confirmation = bytes.fromhex(installed["individual_confirmation_bytes"])
        self.assertEqual(installed["individual_confirmation_offset"], "0x1C00")
        self.assertEqual(len(confirmation), installed["individual_confirmation_length"])
        self.assertEqual(sha(confirmation), installed["individual_confirmation_sha256"])
        self.assertLess(len(confirmation), installed["individual_confirmation_guard_length"])
        self.assertIn(b"\x6A\x01", confirmation)  # MB_OKCANCEL
        self.assertEqual(self.map["individual_detail_route"]["collection_progression"]["message"], 8)
        self.assertEqual(self.map["individual_detail_route"]["collection_progression"]["event"], 2)
        self.assertEqual(self.map["individual_detail_route"]["collection_progression"]["command"], 1)

    def test_individual_detail_route_has_exact_guard_and_preserves_other_commands(self):
        route = self.map["individual_detail_route"]["collection_progression"]
        self.assertEqual(route["hook_va"], "0x4899D6")
        self.assertEqual(route["hook_file_offset"], "0x899D6")
        self.assertEqual(route["hook_before"], "8B049D279F4800")
        self.assertEqual(route["hook_after"], "E9560000009090")
        self.assertEqual(route["cave_va"], "0x489A31")
        self.assertEqual(route["cave_file_offset"], "0x89A31")
        self.assertEqual(route["cave_length"], 0x32)
        cave = bytes.fromhex(route["cave_after"])
        self.assertEqual(len(cave), 0x32)
        self.assertEqual(route["cave_after_sha256"], sha(cave))
        self.assertEqual(route["cave_after_sha256"], "79600D55513838D55E9FAD6D9680A516A2CF6BBC5107B721B7B8E28D59B3168F")
        self.assertEqual(route["section"], ".text")
        self.assertEqual(route["continuation_va"], "0x4899DD")
        self.assertEqual(route["epilogue_va"], "0x489AC5")
        self.assertEqual(route["epilogue_bytes"], "5D5F5E5BC3")
        self.assertIn(b"\x81\x3D\x00\xF0\x73\x00\x56\x46\x4D\x34", cave)
        self.assertIn(b"\x83\x3D\x0C\xF1\x73\x00\x01", cave)
        self.assertIn(0x73FB00, rel32_targets(cave, int(route["cave_va"], 16)))
        self.assertEqual(cave[0x2B:0x30], bytes.fromhex("E97CFFFFFF"))
        payload = next(item for item in self.base_raw["patches"] if int(item["offset"], 0) == 0x89373)
        rendered_payload = bytes.fromhex(payload["after"])
        self.assertEqual(rendered_payload[0x663:0x66A], bytes.fromhex("E9560000009090"))
        self.assertEqual(rendered_payload[0x6BE:0x6BE + 0x32], cave)
        self.assertEqual(rendered_payload[0x752:0x757], bytes.fromhex("5D5F5E5BC3"))
        rendered, _ = render_patched_bytes(
            STOCK, self.build, "collection_progression", _fun_patches_override=[self.base, self.feature]
        )
        self.assertEqual(rendered[0x899D6:0x899DD], bytes.fromhex("E9560000009090"))
        self.assertEqual(rendered[0x89A31:0x89A31 + 0x32], cave)
        self.assertEqual(rendered[0xE4C00:0xE4C00 + 73], bytes.fromhex(
            self.map["layouts"]["collection_progression"]["slot_map"]["installed"]["individual_confirmation_bytes"]
        ))
        self.assertEqual(rendered[0xE4C00 + 73:0xE4C00 + 0x100], b"\0" * 183)
        self.assertEqual(route["atomic_components"], [
            "detail_hook", "detail_cave", "balanced_epilogue", "installed_slot",
            "confirmation_cave", "page_header", "manifests",
        ])

    def test_whole_render_has_no_reachable_cure_target(self):
        rendered, _ = render_patched_bytes(
            STOCK,
            self.build,
            "collection_progression",
            _fun_patches_override=[self.base],
        )
        refs = []
        for i in range(len(rendered) - 4):
            if rendered[i] not in (0xE8, 0xE9):
                continue
            target = 0x400000 + i + 5 + int.from_bytes(rendered[i + 1 : i + 5], "little", signed=True)
            if target == 0x728004:
                refs.append(i)
        self.assertEqual(refs, [])

    def test_all_modes_render_checksum_composition_and_uninstall(self):
        compatible = [
            item for item in load_fun_patches()
            if item.game_id == "vv4"
            and item.id
            not in {
                "vv4_enable_origins_exclusive_features",
                "vv4_full_mastery_all_stage_a_candidate",
            }
        ]
        for mode in MODES:
            with self.subTest(mode=mode):
                baseline, _ = render_patched_bytes(STOCK, self.build, mode)
                base_render, _ = render_patched_bytes(STOCK, self.build, mode, _fun_patches_override=[self.base])
                rendered, applied = render_patched_bytes(STOCK, self.build, mode, _fun_patches_override=[self.base, self.feature, *compatible])
                self.assertEqual(len(rendered), 0xE5000)
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

    def test_enabled_vv4_candidate_and_withdrawn_vv3_running_catalog_state(self):
        active = {item.id: item for item in load_fun_patches()}
        self.assertIn("vv4_enable_origins_exclusive_features", active)
        self.assertIn(self.feature_raw["id"], active)
        self.assertNotIn("vv3_enable_origins_exclusive_features_running_candidate", active)
        self.assertNotIn("vv3_all_villagers_like_running_candidate", active)

    def test_cure_row_and_command5_dispatch_are_fail_closed(self):
        payload = next(item for item in self.base_raw["patches"] if int(item["offset"], 0) == 0x89373)
        code = bytes.fromhex(payload["after"])
        self.assertEqual(code[0x29C:0x2A1], bytes.fromhex("E941FEFFFF"))
        self.assertEqual(
            code[0xE2:0xF5],
            bytes.fromhex("89C383FB050F847901000083FB03E9AC010000"),
        )
        early_jump = int.from_bytes(code[0x29D:0x2A1], "little", signed=True)
        self.assertEqual(0x48960F + 5 + early_jump, 0x489455)
        early_reject = int.from_bytes(code[0xE9:0xED], "little", signed=True)
        self.assertEqual(0x489455 + 0xB + early_reject, 0x4895D9)
        early_resume = int.from_bytes(code[0xF1:0xF5], "little", signed=True)
        self.assertEqual(0x489455 + 0x13 + early_resume, 0x489614)
        self.assertEqual(code[0x2A6], 0x77)
        self.assertNotEqual(code[0x2A6], 0x73)
        self.assertEqual(code[0x3C8:0x3CD], b"\x90" * 5)
        self.assertEqual(code[0x3C0:0x3C5], b"\x90" * 5)
        self.assertEqual(code[0x3D2:0x3D7], b"\x90" * 5)
        self.assertNotIn(bytes.fromhex("E8CCE82900"), code)
        self.assertNotIn(bytes.fromhex("E8C4E82900"), code)
        self.assertNotIn(bytes.fromhex("E8BAE82900"), code)
        self.assertIn(bytes.fromhex("83FB0574"), code[0x340:0x3C0])
        self.assertIn(bytes.fromhex("814C241000200000"), code[0x1B0:0x210])
        containment = self.map["cure_containment"]
        self.assertEqual(containment["dispatch"]["early_capture_va"], "0x48960F")
        self.assertEqual(containment["dispatch"]["early_helper_va"], "0x489455")
        self.assertFalse(containment["public_row"]["selectable"])
        self.assertFalse(containment["dispatch"]["charge_before_guard"])
        self.assertFalse(containment["dispatch"]["forbidden_target_reachable"])
        cure = next(item for item in self.base_raw["patches"] if int(item["offset"], 0) == 0xCC004)
        self.assertEqual(sha(bytes.fromhex(cure["after"])), "2BB7A32344293DCACB4D0359818C6839AC1FBBAEE8F9E3D00DB59C274238D726")

    def test_corruption_and_deterministic_generation(self):
        rendered, _ = render_patched_bytes(
            STOCK, self.build, "collection_progression", _fun_patches_override=[self.base, self.feature]
        )
        slot_work = bytearray(rendered)
        slot_work[0xE3100] ^= 1
        with self.assertRaises(PatcherError):
            _remove_feature_bytes(slot_work, self.feature, "collection_progression")
        for offset in (0x3E165, 0x2C0, 0x899D6, 0x89A31, 0xE4C00, len(rendered) - 1):
            with self.subTest(offset=hex(offset)):
                work = bytearray(rendered)
                work[offset] ^= 1
                if offset == 0xE4C00:
                    with self.assertRaises(PatcherError):
                        _remove_feature_bytes(work, self.feature, "collection_progression")
                    continue
                _remove_feature_bytes(work, self.feature, "collection_progression")
                with self.assertRaises(PatcherError):
                    _remove_feature_bytes(work, self.base, "collection_progression")
        # Canonicalize once before taking the determinism snapshot; preceding
        # tests may have exercised an in-place generator.
        subprocess.run([sys.executable, str(GENERATOR)], cwd=ROOT, check=True)
        before = {
            path: sha(path.read_bytes())
            for path in (BASE, FEATURE, MAP, DOC, DLL)
        }
        subprocess.run([sys.executable, str(GENERATOR)], cwd=ROOT, check=True)
        after = {
            path: sha(path.read_bytes())
            for path in (BASE, FEATURE, MAP, DOC, DLL)
        }
        self.assertEqual(before, after)

    def test_companion_preflight_and_exact_removal_guards(self):
        bad = deepcopy(self.base_raw)
        self.assertEqual(len(bad["companion_files"]), 1)
        bad["companion_files"][0]["sha256"] = "0" * 64
        stock_before = STOCK.read_bytes()
        with self.assertRaises(PatcherError):
            render_patched_bytes(
                STOCK,
                self.build,
                "collection_progression",
                _fun_patches_override=[FunPatch(bad), self.feature],
            )
        self.assertEqual(STOCK.read_bytes(), stock_before)
        missing = deepcopy(self.base_raw)
        missing["companion_files"][0]["source"] = "data/candidates/missing.dll"
        with self.assertRaisesRegex(PatcherError, "missing"):
            render_patched_bytes(
                STOCK,
                self.build,
                "collection_progression",
                _fun_patches_override=[FunPatch(missing), self.feature],
            )
        self.assertEqual(STOCK.read_bytes(), stock_before)
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            for item in self.base_raw["companion_files"]:
                destination = output / Path(item["destination"].replace("\\", "/"))
                destination.parent.mkdir(parents=True, exist_ok=True)
                source = ROOT / item["source"]
                destination.write_bytes(source.read_bytes())
            removed = _remove_companion_files(output, [self.base])
            self.assertEqual(len(removed), 1)
            self.assertFalse((output / "VVFP Origins Icons.dll").exists())
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            item = self.base_raw["companion_files"][0]
            destination = output / Path(item["destination"].replace("\\", "/"))
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"corrupt")
            with self.assertRaises(PatcherError):
                _remove_companion_files(output, [self.base])


if __name__ == "__main__":
    unittest.main()

