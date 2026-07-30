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


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    FunPatch,
    PatcherError,
    _pe_checksum_layout,
    _remove_feature_bytes,
    _remove_companion_files,
    load_builds,
    load_fun_patches,
    pe_checksum,
    render_patched_bytes,
)


STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Tree of Life.exe"
GENERATOR = ROOT / "scripts" / "build_vv4_full_mastery_candidate.py"
BASE = ROOT / "data" / "candidates" / "vv4_origins_full_mastery_base_candidate.json"
FEATURE = ROOT / "data" / "candidates" / "vv4_full_mastery_all_candidate.json"
MAP = ROOT / "data" / "candidates" / "vv4_full_mastery_all_candidate_map.json"
DOC = ROOT / "docs" / "vv4-full-mastery-stage-a-candidate.md"
DLL = ROOT / "data" / "candidates" / "VVFP VV4 Full Mastery Candidate.dll"
ASSET = ROOT / "assets" / "candidates" / "vv4_full_mastery" / "Images" / "btn_upgrades_297x35.png"
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

    def test_new_placement_candidate_disabled_and_command_seven_only(self):
        self.assertTrue(self.base_raw["enabled"])
        self.assertFalse(self.feature_raw["enabled"])
        active = {item.id: item for item in load_fun_patches()}
        self.assertIn("vv4_enable_origins_exclusive_features", active)
        self.assertNotIn(self.base_raw["id"], active)
        self.assertNotIn(self.feature_raw["id"], active)
        self.assertIn("baked canonical mockup asset", self.feature_raw["certification_status"])
        self.assertEqual(self.feature_raw["dependencies"], [self.base_raw["id"]])
        contract = self.feature_raw["transaction_contract"]
        self.assertEqual((contract["command"], contract["price"]), (7, 1_000_000))
        self.assertIsNone(contract["ownership"])
        folded = json.dumps(self.feature_raw).casefold()
        self.assertNotIn("command 6", folded)
        self.assertNotIn("command 8", folded)
        self.assertNotIn("remove state", folded)

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
        self.assertIn(bytes.fromhex("6A0D"), tech)
        self.assertIn(bytes.fromhex("6A02"), detail)
        self.assertIn(bytes.fromhex("6A0D6A016A03"), tech)
        self.assertIn(bytes.fromhex("6A026A016A03"), detail)
        self.assertIn(bytes.fromhex("83F863"), tech)
        self.assertIn(bytes.fromhex("83F823"), tech)
        self.assertIn(bytes.fromhex("83F863"), detail)
        self.assertIn(bytes.fromhex("83F823"), detail)
        self.assertIn(bytes.fromhex("E84988F7FF"), tech)  # sub_401C20
        self.assertIn(bytes.fromhex("E88987F7FF"), detail)  # sub_401C20
        self.assertIn(bytes.fromhex("E88E2DF8FF"), tech)  # sub_40C190
        self.assertIn(bytes.fromhex("E8D12CF8FF"), detail)  # sub_40C190
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
            self.map["ui_asset_gate"]["runtime_dimension_guard"],
            {
                "accessors": {
                    "width": {"wrapper_vtable_offset": "0x0C", "va": "0x401470"},
                    "height": {"wrapper_vtable_offset": "0x10", "va": "0x4014B0"},
                },
                "required_frame_dimensions": [99, 35],
                "static_strip_dimensions": [297, 35],
                "static_grid": [3, 1],
                "reject": {"scalar_destructor_flag": 1, "attach": False, "tech_slot": None},
                "tech_constructor_guarded": True,
                "detail_constructor_guarded": True,
            },
        )
        ui = self.map["ui_asset_gate"]
        self.assertEqual(ui["destination"], r"Images\btn_upgrades_297x35.png")
        self.assertEqual(ui["dimensions"], [297, 35])
        self.assertEqual(ui["frame_order"], ["normal", "hover", "pressed"])
        self.assertEqual(ui["factory"], "sub_401C20")
        self.assertEqual(ui["grid"], [3, 1])
        self.assertEqual(ui["local"], [72, 4])
        self.assertEqual(ui["events"], {"tech": 13, "detail": 2})
        self.assertEqual(ui["add_child"], "sub_40C190")
        self.assertEqual(ui["status"], "disabled pending independent emitted-byte recertification")
        self.assertEqual(ui["png_sha256"], "F03D57038CA7745A99C0D7D58A2558A4411828BF3243D85C8BAFE2E04036BE4B")
        self.assertEqual(sha(ASSET.read_bytes()), ui["png_sha256"])
        self.assertEqual(sha((PROVENANCE / "VV4 mockup.jpg").read_bytes()), "B404465B960BE3875F4DF0BFE32796B8045A9E938A356FF33448331AB2840A24")

    def test_runtime_dimension_guard_rejects_fallback_before_attachment(self):
        """Model the emitted guard's observable ownership behavior without launching the game."""

        def attach_result(dimensions, tech=False, existing_slot=None):
            slot = existing_slot
            attached = []
            destroyed = 0
            if dimensions is None:
                if tech:
                    slot = None
                return slot, attached, destroyed
            if tuple(dimensions) != (99, 35):
                destroyed = 1
                if tech:
                    slot = None
                return slot, attached, destroyed
            wrapper = object()
            if tech:
                slot = wrapper
            attached.append(wrapper)
            return slot, attached, destroyed

        for dimensions in (None, (100, 100), (297, 35), (99, 34), (98, 35)):
            with self.subTest(dimensions=dimensions):
                slot, attached, destroyed = attach_result(dimensions, tech=True, existing_slot=None)
                if dimensions == (99, 35):
                    self.assertIsNotNone(slot)
                    self.assertEqual(len(attached), 1)
                    self.assertEqual(destroyed, 0)
                else:
                    self.assertIsNone(slot)
                    self.assertEqual(attached, [])
                    self.assertEqual(destroyed, 0 if dimensions is None else 1)

        slot, attached, destroyed = attach_result((100, 100), tech=False)
        self.assertIsNone(slot)
        self.assertEqual(attached, [])
        self.assertEqual(destroyed, 1)

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
        isolated = resources.split("203 DIALOGEX", 1)[1]
        self.assertIn('PUSHBUTTON  "Buy", 1007', isolated)
        self.assertNotIn('1006,', isolated)
        self.assertNotIn('1008,', isolated)

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

    def test_old_origins_and_withdrawn_running_collide_fail_closed(self):
        active = {item.id: item for item in load_fun_patches()}
        for feature_id in ("vv4_enable_origins_exclusive_features",):
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
        slot_work[0xE3100] ^= 1
        with self.assertRaises(PatcherError):
            _remove_feature_bytes(slot_work, self.feature, "collection_progression")
        for offset in (0x3E165, 0x2C0, len(rendered) - 1):
            with self.subTest(offset=hex(offset)):
                work = bytearray(rendered)
                work[offset] ^= 1
                _remove_feature_bytes(work, self.feature, "collection_progression")
                with self.assertRaises(PatcherError):
                    _remove_feature_bytes(work, self.base, "collection_progression")
        before = {
            path: sha(path.read_bytes())
            for path in (BASE, FEATURE, MAP, DOC, DLL, ASSET)
        }
        subprocess.run([sys.executable, str(GENERATOR)], cwd=ROOT, check=True)
        after = {
            path: sha(path.read_bytes())
            for path in (BASE, FEATURE, MAP, DOC, DLL, ASSET)
        }
        self.assertEqual(before, after)

    def test_companion_preflight_and_exact_removal_guards(self):
        bad = deepcopy(self.base_raw)
        bad["companion_files"][1]["sha256"] = "0" * 64
        with self.assertRaises(PatcherError):
            render_patched_bytes(
                STOCK,
                self.build,
                "collection_progression",
                _fun_patches_override=[FunPatch(bad), self.feature],
            )
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            for item in self.base_raw["companion_files"]:
                destination = output / Path(item["destination"].replace("\\", "/"))
                destination.parent.mkdir(parents=True, exist_ok=True)
                source = ROOT / item["source"]
                destination.write_bytes(source.read_bytes())
            removed = _remove_companion_files(output, [self.base])
            self.assertEqual(len(removed), 2)
            self.assertFalse((output / "Images" / "btn_upgrades_297x35.png").exists())
            self.assertFalse((output / "VVFP Origins Icons.dll").exists())
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            item = self.base_raw["companion_files"][1]
            destination = output / Path(item["destination"].replace("\\", "/"))
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"corrupt")
            with self.assertRaises(PatcherError):
                _remove_companion_files(output, [self.base])


if __name__ == "__main__":
    unittest.main()

