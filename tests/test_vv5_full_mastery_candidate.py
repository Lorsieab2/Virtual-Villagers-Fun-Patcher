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
sys.path.insert(0, str(ROOT / "scripts"))

from vv_fun_patcher import (  # noqa: E402
    FunPatch,
    PatcherError,
    VV5_FULL_MASTERY_CERTIFIED_SHA256,
    _validate_companion_sources,
    _pe_checksum_layout,
    _remove_feature_bytes,
    load_builds,
    load_fun_patches,
    pe_checksum,
    render_patched_bytes,
)
from runtime_freeze import isolated_runtime_freeze  # noqa: E402


STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
GENERATOR = ROOT / "scripts" / "build_vv5_full_mastery_candidate.py"
BASE = ROOT / "data" / "candidates" / "vv5_origins_full_mastery_base_candidate.json"
FEATURE = ROOT / "data" / "candidates" / "vv5_full_mastery_all_candidate.json"
MAP = ROOT / "data" / "candidates" / "vv5_full_mastery_all_candidate_map.json"
DOC = ROOT / "docs" / "vv5-full-mastery-stage-a-candidate.md"
DLL = ROOT / "data" / "candidates" / "VVFP VV5 Full Mastery Candidate.dll"
PROVENANCE_ASSET = ROOT / "assets" / "candidates" / "vv5_full_mastery" / "provenance" / "btn_trophies.png"
MODES = (
    "collection_progression",
    "immediate_fixed",
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
)
SKILLS = ("farming", "parenting", "healing", "research", "building", "devotion")


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
    writer_calls: list[tuple[int, int, float]] = []
    for index, record in enumerate(records):
        if (
            not record["active"]
            or int(record["health"]) <= 0
            or int(record["faction"]) != 0
        ):
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
                current = float(skills[name])
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


class VV5FullMasteryCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_raw = json.loads(BASE.read_text(encoding="utf-8"))
        cls.feature_raw = json.loads(FEATURE.read_text(encoding="utf-8"))
        cls.map = json.loads(MAP.read_text(encoding="utf-8"))
        cls.base = FunPatch(cls.base_raw)
        cls.feature = FunPatch(cls.feature_raw)
        cls.build = next(item for item in load_builds() if item.id == "vv5")

    def test_geometry_candidate_is_hidden_and_command_seven_only(self):
        self.assertTrue(self.base_raw["enabled"])
        self.assertFalse(self.feature_raw["enabled"])
        active = {item.id: item for item in load_fun_patches()}
        self.assertIn("vv5_enable_origins_exclusive_features", active)
        self.assertNotIn(self.base_raw["id"], active)
        self.assertNotIn(self.feature_raw["id"], active)
        self.assertIn("disabled candidate", self.feature_raw["certification_status"])
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
        self.assertEqual(len(source), 991_232)
        self.assertEqual(
            sha(source),
            "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D",
        )
        self.assertEqual(self.map["layouts"]["collection_progression"]["bound"], 150)
        self.assertEqual(self.map["layouts"]["experimental_expanded_256"]["bound"], 256)
        self.assertEqual(self.map["references"]["base_relocations"], [])
        for mode in MODES[:2]:
            layout = self.base_raw["pe_append_transaction"]["layouts"][mode]
            self.assertEqual(layout["append_offset"], "0xF2000")
            self.assertEqual(layout["append_length"], 0x2000)
            self.assertEqual(layout["header_patches"][2]["offset"], "0x2B8")
            self.assertTrue(bytes.fromhex(layout["header_patches"][2]["after"]).startswith(b".vv5fm\0\0"))

    def test_native_writer_evaluator_semantics_and_domain_gate(self):
        excluded = [
            {"active": False, "health": 100, "faction": 0, "skills": {name: object() for name in SKILLS}},
            {"active": True, "health": 0, "faction": 0, "skills": {name: object() for name in SKILLS}},
            {"active": True, "health": 100, "faction": 1, "skills": {name: object() for name in SKILLS}},
        ]
        target = {
            "active": True,
            "health": 1,
            "faction": 0,
            "legacy_flag_1ce1": 1,
            "skills": dict(zip(SKILLS, (99, 90, 100, 88, 0, 99.5))),
            "unrelated": 77,
        }
        records = [*excluded, target]
        changed, invalid, calls = walk(records, True)
        self.assertEqual((changed, invalid), (1, False))
        self.assertEqual(
            calls,
            [(3, 0, 1.0), (3, 1, 10.0), (3, 3, 12.0), (3, 4, 100.0), (3, 5, 0.5)],
        )
        self.assertEqual(target["unrelated"], 77)
        self.assertEqual(target["skills"], {name: 100.0 for name in SKILLS})
        for invalid in (-1.0, 100.01, float("inf"), float("nan")):
            invalid_record = [{"active": True, "health": 1, "faction": 0, "skills": {name: (invalid if name == "research" else 100.0) for name in SKILLS}}]
            self.assertEqual(walk(invalid_record, True), (0, True, []))

    def test_sparse_150_256_and_transaction_races(self):
        empty = {"active": False, "health": 0, "faction": 0, "skills": {name: 100 for name in SKILLS}}
        for bound in (150, 256):
            records = [deepcopy(empty) for _ in range(bound)]
            for index in (0, bound - 1):
                records[index] = {"active": True, "health": 1, "faction": 0, "skills": {name: (99 if name == "building" else 100) for name in SKILLS}}
            self.assertEqual(walk(records, False)[:2], (2, False))
        base = [{"active": True, "health": 1, "faction": 0, "skills": {name: (99 if name == "farming" else 100) for name in SKILLS}}]
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
        self.assertIn("ShowVV5FullMasteryResult", exports)
        self.assertIn("_ShowVV5FullMasteryResult@8", exports)
        self.assertIn("ShowOriginsVillageWideResult@20", exports)
        source = (ROOT / "native" / "vv5_full_mastery_candidate" / "vv5_full_mastery_candidate.c").read_text(encoding="utf-8")
        for text in (
            "Everyone is already fully mastered.",
            "No tech points have been deducted.",
            "Not enough tech points.",
            "out-of-range skill.",
            "Fully mastered %u villagers.",
        ):
            self.assertIn(text, source)
        resources = (ROOT / "native" / "vv5_full_mastery_candidate" / "vv5_full_mastery_candidate.rc").read_text(encoding="utf-8")
        isolated = resources.split("203 DIALOGEX", 1)[1]
        self.assertIn("Time Warp - Advances 3 Villager Years", isolated)
        self.assertNotIn("Time Warp - 3 villager years", resources)
        self.assertIn('PUSHBUTTON  "Buy", 1007', isolated)
        self.assertNotIn('1006,', isolated)
        self.assertNotIn('1008,', isolated)
        self.assertIn("Time Warp - Advances 3 Villager Years", resources)

    def test_corrected_time_warp_resource_identity_is_exact(self):
        label = "Time Warp - Advances 3 Villager Years"
        old_label = "Time Warp - 3 villager years"
        dll_bytes = DLL.read_bytes()
        self.assertEqual(dll_bytes.count(label.encode("utf-16le")), 2)
        self.assertNotIn(old_label.encode("utf-16le"), dll_bytes)
        resources = (ROOT / "native" / "vv5_full_mastery_candidate" / "vv5_full_mastery_candidate.rc").read_text(encoding="utf-8")
        self.assertEqual(resources.count(f'LTEXT       "{label}"'), 2)
        self.assertNotIn(old_label, resources)

    def test_unknown_or_corrupt_companion_fails_closed(self):
        from copy import deepcopy

        feature = deepcopy(self.base_raw)
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_path = Path(temp_dir) / "VV5-corrupt.dll"
            temp_path.write_bytes(b"not the certified VV5 companion")
            relative = temp_path.relative_to(ROOT).as_posix()
            feature["companion_files"][0]["source"] = relative
            feature["companion_files"][0]["sha256"] = VV5_FULL_MASTERY_CERTIFIED_SHA256["dll"]
            with self.assertRaisesRegex(PatcherError, "Companion file hash mismatch"):
                _validate_companion_sources([FunPatch(feature)])

        missing = deepcopy(self.base_raw)
        missing["companion_files"][0]["source"] = "data/candidates/does-not-exist-vv5.dll"
        with self.assertRaisesRegex(PatcherError, "Required companion file is missing"):
            _validate_companion_sources([FunPatch(missing)])

    def test_vv5_companion_validator_uses_authoritative_identity(self):
        self.assertEqual(
            VV5_FULL_MASTERY_CERTIFIED_SHA256["dll"],
            "29927CECB448B64944E18E2BA11893DC84C91B39241FBB2549FC2A464E0BE2ED",
        )
        self.assertNotEqual(
            VV5_FULL_MASTERY_CERTIFIED_SHA256["dll"],
            "BD80B1B0692FE3C0F2293A73CFF707C18198AECA8922355DB2E9EB169E112608",
        )

    def test_vv5_runtime_freeze_does_not_rewrite_vv3_certified_record(self):
        frozen = isolated_runtime_freeze(
            game_id="vv5",
            map_path=MAP,
            data_root=ROOT / "data",
        )
        self.assertEqual(
            frozen["vv3_origins_feature.json"],
            self.map["runtime_freeze"]["vv3_origins_feature.json"],
        )
        self.assertEqual(
            frozen["vv5_origins_feature.json"],
            "9A6635544D8506033D28CA594491C40299242F6D9A24D8B529763C8160FC8566",
        )

    def test_exact_current_context_native_calls_and_nonvolatile_frame(self):
        slot = bytes.fromhex(self.feature_raw["patches"][0]["after"])
        slot_map = self.map["layouts"]["collection_progression"]["slot_map"]["installed"]
        entry_offset = int(self.map["slot_layout"]["entry_offset"], 0)
        walker_offset = int(self.map["slot_layout"]["walker_offset"], 0)
        entry = slot[entry_offset : entry_offset + slot_map["entry_length"]]
        walker = slot[walker_offset : walker_offset + slot_map["walker_length"]]
        entry_va = 0x7C9000 + 0x100 + entry_offset
        walker_va = 0x7C9000 + 0x100 + walker_offset

        self.assertTrue(entry.startswith(bytes.fromhex("5589E553565783EC10")))
        self.assertNotIn(bytes.fromhex("89CE"), entry)
        self.assertIn(bytes.fromhex("8955F0"), entry)
        self.assertNotIn(bytes.fromhex("8955F4"), entry)
        self.assertEqual(entry.count(bytes.fromhex("6890415500")), 3)
        self.assertIn(bytes.fromhex("813DF8D5510040420F00"), entry)
        self.assertEqual(rel32_targets(entry, entry_va).count(walker_va), 3)
        self.assertIn(0x4237B0, rel32_targets(entry, entry_va))
        self.assertIn(0x475730, rel32_targets(walker, walker_va))

        active = bytes.fromhex("80BED41C000000")
        health = bytes.fromhex("83BE401C000000")
        faction = bytes.fromhex("80BEEC1C000000")
        skill_base = bytes.fromhex("8D965C1C0000")
        self.assertLess(walker.index(active), walker.index(health))
        self.assertLess(walker.index(health), walker.index(faction))
        self.assertLess(walker.index(faction), walker.index(skill_base))
        self.assertNotIn(bytes.fromhex("E11C0000"), walker)

    def test_base_hooks_cure_only_router_and_withdrawn_preflight_absence(self):
        patches = {int(item["offset"], 0): item for item in self.base_raw["patches"]}
        self.assertEqual(patches[0x40A24]["before"], "8BC68B4C244C")
        self.assertEqual(patches[0x415F0]["before"], "578BF9E848F70000")
        self.assertNotIn(0x94B37, patches)
        cure = bytes.fromhex(patches[0x94EA0]["after"])
        self.assertEqual(cure[:2], bytes.fromhex("EB5F"))
        self.assertEqual(cure[2:97], b"\x90" * 95)
        self.assertEqual(cure[97:105], bytes.fromhex("53555152565731C0"))

    def test_tech_and_detail_upgrades_use_native_top_left_resource_and_rectangle(self):
        patches = {int(item["offset"], 0): item for item in self.base_raw["patches"]}
        payload = bytes.fromhex(patches[0xDB000]["after"])
        tech_ctor = payload[0x40:0xC0]
        detail_ctor = payload[0x100:0x180]
        for ctor in (tech_ctor, detail_ctor):
            self.assertIn(bytes.fromhex("6A6A"), ctor)
            self.assertIn(bytes.fromhex("6802000000"), ctor)
            self.assertIn(bytes.fromhex("6889000000"), ctor)
            self.assertNotIn(bytes.fromhex("6A48"), ctor)
            self.assertNotIn(bytes.fromhex("6A53"), ctor)
            self.assertNotIn(bytes.fromhex("68B4000000"), ctor)
        self.assertNotIn(bytes.fromhex("68D2020000"), tech_ctor)
        self.assertNotIn(bytes.fromhex("68BC020000"), detail_ctor)
        contract = self.base_raw["ui_geometry_contract"]
        self.assertEqual(contract["asset_sha256"], "F39E94CBDF24776631D803D1218EFCCDE555081C9C8C644DD073B75EC7DD2095")
        self.assertEqual(contract["resource_id"], "0x6A")
        self.assertEqual(contract["native_dimensions"], [96, 39])
        self.assertEqual(contract["tech"]["local_x"], 137)
        self.assertEqual(contract["tech"]["local_y"], 2)
        self.assertEqual(contract["detail"]["local_x"], 137)
        self.assertEqual(contract["detail"]["local_y"], 2)
        self.assertEqual(sha(PROVENANCE_ASSET.read_bytes()), contract["asset_sha256"])

    def test_individual_transaction_uses_native_exact_100_contract(self):
        slot = bytes.fromhex(self.feature_raw["patches"][0]["after"])
        slot_map = self.map["layouts"]["collection_progression"]["slot_map"]["installed"]
        off = int(slot_map["individual_offset"])
        length = int(slot_map["individual_length"])
        helper = slot[off:off + length]
        self.assertIn(bytes.fromhex("00C842"), helper)
        self.assertNotIn(bytes.fromhex("00B442"), helper)
        self.assertIn(bytes.fromhex("E8"), helper)
        self.assertIn("individual_no_change", slot_map["strings"])
        self.assertEqual(slot_map["individual_offset"], 0xC00)
        self.assertGreater(length, 300)

    def test_command1_precharge_hook_and_fail_closed_contract(self):
        patches = {int(item["offset"], 0): item for item in self.feature_raw["patches"]}
        self.assertEqual(patches[0xDB766]["before"], "83FB027525")
        self.assertTrue(patches[0xDB766]["after"].startswith("E9"))
        payload = bytes.fromhex(
            next(item["after"] for item in self.base_raw["patches"] if int(item["offset"], 0) == 0xDB000)
        )
        self.assertEqual(payload[0x7B5:0x7BA].hex().upper(), "83FB017451")
        self.assertEqual(self.feature_raw["patch_mode_overrides"], {})
        helper = bytes.fromhex(self.feature_raw["patches"][0]["after"])[0xC00:0xC00 + 689]
        self.assertEqual(helper.count(bytes.fromhex("B948415500")), 4)
        self.assertIn(bytes.fromhex("3D96000000"), helper)
        self.assertIn(bytes.fromhex("81E2FFFFFF7F"), helper)
        self.assertIn(bytes.fromhex("A0860100"), helper)
        for key in ("individual_insufficient", "individual_cancel", "individual_recheck", "individual_postverify"):
            self.assertIn(key, self.map["layouts"]["collection_progression"]["slot_map"]["installed"]["strings"])

    def test_all_modes_render_checksum_composition_and_uninstall(self):
        compatible = [
            item for item in load_fun_patches()
            if item.game_id == "vv5"
            and item.id
            not in {
                "vv5_enable_origins_exclusive_features",
                "vv5_full_mastery_all_stage_a_candidate",
            }
        ]
        for mode in MODES[:2]:
            with self.subTest(mode=mode):
                baseline, _ = render_patched_bytes(STOCK, self.build, mode)
                base_render, _ = render_patched_bytes(STOCK, self.build, mode, _fun_patches_override=[self.base])
                rendered, applied = render_patched_bytes(STOCK, self.build, mode, _fun_patches_override=[self.base, self.feature, *compatible])
                self.assertEqual(len(rendered), 0xF4000)
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

        for mode in MODES[2:]:
            with self.subTest(expanded_mode=mode):
                with self.assertRaises(PatcherError):
                    render_patched_bytes(
                        STOCK, self.build, mode,
                        _fun_patches_override=[self.base, self.feature],
                    )

    def test_old_origins_and_withdrawn_running_collide_fail_closed(self):
        active = {item.id: item for item in load_fun_patches()}
        for feature_id in ("vv5_enable_origins_exclusive_features",):
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
        slot_work[0xF2100] ^= 1
        with self.assertRaises(PatcherError):
            _remove_feature_bytes(slot_work, self.feature, "collection_progression")
        for offset in (0x40A24, 0x2B8, len(rendered) - 1):
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

    def test_c37_audit_provenance_names_binary_and_documentation_commits(self):
        audit = ROOT / "outputs" / "vv5-c37-d40-audit"
        manifest_path = audit / "artifact-manifest.json"
        determinism_path = audit / "determinism.json"
        patch_log_path = audit / "patch-log.json"
        if not all(path.is_file() for path in (manifest_path, determinism_path, patch_log_path)):
            self.skipTest("ignored C37 audit bundle is not present")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        patch_log = json.loads(patch_log_path.read_text(encoding="utf-8"))
        determinism = json.loads(determinism_path.read_text(encoding="utf-8"))
        for record in (manifest, patch_log, determinism):
            self.assertEqual(
                record["binary_source_commit"],
                "2366397a9d01696d0726afddf829c508db3957d4",
            )
            self.assertEqual(
                record["documentation_commit"],
                "ba6da5e5bb25a4648f52aa8ccffe7d7a9ae801f9",
            )
            self.assertNotIn("source_commit", record)
        self.assertTrue(determinism["two_pass_identical"])
        self.assertEqual(
            manifest["companion"]["sha256"],
            "29927CECB448B64944E18E2BA11893DC84C91B39241FBB2549FC2A464E0BE2ED",
        )
        self.assertEqual(
            manifest["modes"]["collection_progression"]["exe_sha256"],
            "9180BC6BF371ED797BF1B519BF33AFAF94832642BEB531C10F0AB25E5217BD7F",
        )
        self.assertEqual(
            manifest["modes"]["immediate_fixed"]["exe_sha256"],
            "86D312E1ED4AB64E1CE559F1AC5D61FD5E35E823D4B86271369F50AF7234172C",
        )


if __name__ == "__main__":
    unittest.main()
