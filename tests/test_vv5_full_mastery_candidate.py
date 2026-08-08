from __future__ import annotations

import hashlib
import json
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch as mock_patch


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
import vv_fun_patcher as patcher_module  # noqa: E402
from runtime_freeze import isolated_runtime_freeze  # noqa: E402
import build_vv5_full_mastery_candidate as vv5_builder  # noqa: E402


STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
GENERATOR = ROOT / "scripts" / "build_vv5_full_mastery_candidate.py"
BASE = ROOT / "data" / "candidates" / "vv5_origins_full_mastery_base_candidate.json"
FEATURE = ROOT / "data" / "candidates" / "vv5_full_mastery_all_candidate.json"
MAP = ROOT / "data" / "candidates" / "vv5_full_mastery_all_candidate_map.json"
DOC = ROOT / "docs" / "vv5-full-mastery-stage-a-candidate.md"
DLL = ROOT / "data" / "candidates" / "VVFP VV5 Full Mastery Candidate.dll"
CURE_PROJECTION = ROOT / "data" / "candidates" / "VVFP VV5 Cure Containment Projection.dll"
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

    def test_dependent_metadata_follows_disabled_base_and_command_seven_stays_static(self):
        self.assertFalse(self.base_raw["enabled"])
        self.assertTrue(self.base_raw["catalog_hidden"])
        self.assertFalse(self.feature_raw["enabled"])
        self.assertTrue(self.feature_raw["catalog_hidden"])
        active = {item.id: item for item in load_fun_patches()}
        self.assertIn("vv5_enable_origins_exclusive_features", active)
        self.assertNotIn(self.base_raw["id"], active)
        self.assertNotIn(self.feature_raw["id"], active)
        self.assertIn("base parent is disabled", self.feature_raw["certification_status"])
        self.assertFalse(self.map["candidate_enabled"])
        self.assertFalse(self.map["catalog_enabled"])
        self.assertTrue(self.map["catalog_hidden"])
        self.assertEqual(self.map["allowed_modes"], ["collection_progression", "immediate_fixed"])
        self.assertTrue(self.map["expanded_fail_closed"])
        self.assertEqual(
            self.map["confirmation_contract"]["individual_string_sha256"],
            "60C9A875AFC93174041B78B3A185B4E1BAE468404F20C3AFC1CF1F127802FD3C",
        )
        self.assertEqual(
            self.map["confirmation_contract"]["village_string_sha256"],
            "56BC07733ED0F93F211BA0D1887502F8A45E03A4187B8C17067F32FF87117D46",
        )
        self.assertEqual(self.feature_raw["dependencies"], [self.base_raw["id"]])
        builder_source = (ROOT / "scripts" / "build_vv5_full_mastery_candidate.py").read_text(encoding="utf-8")
        self.assertIn('feature_enabled = base.get("enabled") is True', builder_source)
        contract = self.feature_raw["transaction_contract"]
        self.assertEqual((contract["command"], contract["price"]), (7, 1_000_000))
        self.assertIsNone(contract["ownership"])
        folded = json.dumps(self.feature_raw).casefold()
        self.assertNotIn("command 6", folded)
        self.assertNotIn("command 8", folded)
        self.assertNotIn("remove state", folded)

    def test_d259_sdl_symbol_pointer_starts_after_module_nul(self):
        source = GENERATOR.read_text(encoding="utf-8")
        self.assertIn('sdl_string_va + len(b"SDL2.dll") + 1', source)
        self.assertNotIn("len(b'SDL2.dll\\0')", source)
        blob = vv5_builder.FULLSCREEN_STRING
        module_end = blob.index(b"\0")
        symbol_start = module_end + 1
        self.assertEqual(blob[symbol_start : symbol_start + len(b"SDL_GetWindowFlags")], b"SDL_GetWindowFlags")
        self.assertNotEqual(blob[symbol_start - 1 : symbol_start - 1 + len(b"DL_GetWindowFlags")], b"DL_GetWindowFlags")

    def test_d259_emitted_pointer_byte_and_unrelated_hashes(self):
        common = vv5_builder.build_fullscreen_wrapper(
            vv5_builder.PAYLOAD_VA + vv5_builder.FULLSCREEN_COMMON_OFFSET,
            vv5_builder.PAYLOAD_VA + vv5_builder.FULLSCREEN_STRING_OFFSET,
        )
        self.assertIn(bytes.fromhex("68632A7B00"), common)
        self.assertNotIn(bytes.fromhex("68642A7B00"), common)
        self.assertEqual(sha(common), "7520FC2B5524938005769DA34F6CE93FEC38FE64689F71CB0077F0F406F14727")

    def test_d259_freezes_full_mastery_page_companion_and_transaction_bytes(self):
        self.assertEqual(sha(DLL.read_bytes()), "29927CECB448B64944E18E2BA11893DC84C91B39241FBB2549FC2A464E0BE2ED")
        self.assertEqual(sha(CURE_PROJECTION.read_bytes()), "A1C55063B548F195B9ECDA492E1799D35EBA5437862353D96BE780D9FCC2E1C8")
        collection_layout = self.map["layouts"]["collection_progression"]
        self.assertEqual(collection_layout["base_page_sha256"], "BB57A17F7EEA8EBCEAC1164E802494B66B7D4DFE8326AFE7A85E8DB79E942C8F")
        self.assertEqual(collection_layout["installed_page_sha256"], "9B191EE433100638E2C45AD6BC14B65C73C05BFC02DF6553F892F570CD2FC586")
        feature_patches = {int(item["offset"], 0): item for item in self.feature_raw["patches"]}
        self.assertEqual(sha(bytes.fromhex(feature_patches[0xF2100]["after"])), "00CB45CEFDD687FDBDAE5A75BF90E677315A92D2BEAC1E1C5D06C650F10F9A92")
        self.assertEqual(sha(bytes.fromhex(feature_patches[0xDB766]["after"])), "21DC81FEB317303F366D95380D2FBE5017453B7179540C6C6567B63D1B73B0B9")
        self.assertEqual(self.feature_raw["transaction_contract"]["price"], 1_000_000)

    def _render_with_loader_mutation(self, mode: str, mutation: str):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp = Path(temp_dir)
            paths = {}
            for key, source in patcher_module.VV5_FULL_MASTERY_CANDIDATE_PATHS.items():
                target = temp / source.name
                if source.is_file():
                    target.write_bytes(source.read_bytes())
                paths[key] = target
            for key in ("base", "feature", "map"):
                data = json.loads(paths[key].read_text(encoding="utf-8"))
                # The base dependency remains an internal disabled record; the
                # isolated mutation projection must satisfy the normal loader gate.
                if key == "base":
                    data["enabled"] = True
                    data["catalog_hidden"] = False
                elif key == "feature":
                    data["enabled"] = True
                    data["catalog_hidden"] = False
                elif key == "map":
                    # This is an isolated positive projection for mutation
                    # coverage only; production metadata remains disabled by
                    # the base-parent gate.
                    data["candidate_enabled"] = True
                    data["catalog_enabled"] = True
                    data["catalog_hidden"] = False
                if mutation == "acceptance_commit" and key == "map":
                    data["acceptance_commit"] = "0000000000000000000000000000000000000000"
                elif mutation == "stock_page" and key == "map":
                    for layout in data["layouts"].values():
                        if isinstance(layout, dict) and "installed_page_sha256" in layout:
                            layout["installed_page_sha256"] = "0" * 64
                elif mutation == "resource_id" and key == "base":
                    data["ui_geometry_contract"]["resource_id"] = "0x53"
                elif mutation == "missing_detail" and key == "feature":
                    data["ui_geometry_contract"].pop("detail")
                elif mutation == "dimensions" and key == "feature":
                    data["ui_geometry_contract"]["native_dimensions"] = [100, 39]
                elif key == "map" and mutation.startswith("map_wrong_"):
                    field = mutation.removeprefix("map_wrong_")
                    wrong = {
                        "asset": "Images\\wrong.png",
                        "provenance": "assets/wrong.png",
                        "asset_sha256": "0" * 64,
                        "resource_id": "0x53",
                        "native_dimensions": [96, 40],
                        "tech.local_x": 138,
                        "tech.local_y": 3,
                        "tech.event": 2,
                        "tech.factory": "0x401C20",
                        "tech.ownership": "0x40C681",
                        "detail.local_x": 138,
                        "detail.local_y": 3,
                        "detail.event": 2,
                        "detail.factory": "0x401C20",
                        "detail.ownership": "0x40C681",
                    }[field]
                    target = data["ui_geometry_contract"]
                    parts = field.split(".")
                    for part in parts[:-1]:
                        target = target[part]
                    target[parts[-1]] = wrong
                elif key == "map" and mutation.startswith("map_missing_"):
                    field = mutation.removeprefix("map_missing_")
                    target = data["ui_geometry_contract"]
                    parts = field.split(".")
                    for part in parts[:-1]:
                        target = target[part]
                    target.pop(parts[-1])
                elif key == "map" and mutation.startswith("map_type_"):
                    field = mutation.removeprefix("map_type_")
                    wrong_type = {
                        "asset": 106,
                        "provenance": None,
                        "asset_sha256": ["0" * 64],
                        "resource_id": 106,
                        "native_dimensions": "96x39",
                        "tech.local_x": "137",
                        "tech.local_y": True,
                        "tech.event": "13",
                        "tech.factory": 0x401BD0,
                        "tech.ownership": None,
                        "detail.local_x": "137",
                        "detail.local_y": True,
                        "detail.event": "13",
                        "detail.factory": 0x401BD0,
                        "detail.ownership": None,
                    }[field]
                    target = data["ui_geometry_contract"]
                    parts = field.split(".")
                    for part in parts[:-1]:
                        target = target[part]
                    target[parts[-1]] = wrong_type
                paths[key].write_text(json.dumps(data), encoding="utf-8")
            if mutation == "missing_asset":
                paths["provenance_asset"] = temp / "missing-btn_trophies.png"
            elif mutation == "corrupt_asset":
                paths["provenance_asset"].write_bytes(
                    paths["provenance_asset"].read_bytes() + b"corrupt"
                )
            with mock_patch.object(
                patcher_module, "VV5_FULL_MASTERY_CANDIDATE_PATHS", paths
            ):
                temp_base = json.loads(paths["base"].read_text(encoding="utf-8"))
                temp_feature = json.loads(paths["feature"].read_text(encoding="utf-8"))
                # Exercise the production immutable VV5 validator against the
                # isolated projection before rendering its bytes directly.
                patcher_module._certified_vv5_full_mastery_records(temp_base)
                return render_patched_bytes(
                    STOCK,
                    self.build,
                    mode,
                    _fun_patches_override=[FunPatch(temp_base), FunPatch(temp_feature)],
                )

    def test_c103_loader_contract_and_asset_mutations_fail_before_output(self):
        mutations = (
            ("acceptance_commit", "acceptance_commit"),
            ("stock_page", "stock page hash"),
            ("resource_id", "UI contract"),
            ("missing_detail", "UI contract"),
            ("dimensions", "UI contract"),
            ("missing_asset", "provenance btn_trophies asset is missing"),
            ("corrupt_asset", "provenance btn_trophies asset hash mismatch"),
        )
        for mutation, message in mutations:
            for mode in ("collection_progression", "immediate_fixed"):
                with self.subTest(mutation=mutation, mode=mode):
                    with self.assertRaisesRegex(PatcherError, message):
                        self._render_with_loader_mutation(mode, mutation)

    def test_c103_loader_accepts_both_certified_stock_modes(self):
        expected = {
            "collection_progression": "857E22D7C361B802508BF789C3CC486E42E76021F5AA579BB1D16CC6E0D017A0",
            "immediate_fixed": "E93822F752F730ECB751EBAA87021194C992984721B4370FF0015D5FC4BB2E9A",
        }
        for mode, digest in expected.items():
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(PatcherError, "Unknown optional patch"):
                    render_patched_bytes(
                        STOCK,
                        self.build,
                        mode,
                        [
                            "vv5_enable_origins_exclusive_features_full_mastery_candidate",
                            "vv5_full_mastery_all_stage_a_candidate",
                        ],
                    )
                rendered, _ = render_patched_bytes(
                    STOCK,
                    self.build,
                    mode,
                    _fun_patches_override=[self.base, self.feature],
                )
                self.assertEqual(sha(rendered), digest)

    def test_c105_map_ui_contract_mutations_fail_before_output(self):
        fields = (
            "asset",
            "provenance",
            "asset_sha256",
            "resource_id",
            "native_dimensions",
            "tech.local_x",
            "tech.local_y",
            "tech.event",
            "tech.factory",
            "tech.ownership",
            "detail.local_x",
            "detail.local_y",
            "detail.event",
            "detail.factory",
            "detail.ownership",
        )
        for prefix in ("map_wrong_", "map_missing_", "map_type_"):
            for field in fields:
                mutation = prefix + field
                for mode in ("collection_progression", "immediate_fixed"):
                    with self.subTest(mutation=mutation, mode=mode):
                        with self.assertRaisesRegex(PatcherError, "candidate map UI contract"):
                            self._render_with_loader_mutation(mode, mutation)

    def test_exact_fingerprint_layout_bounds_and_fixed_base(self):
        source = STOCK.read_bytes()
        self.assertEqual(len(source), 991_232)
        self.assertEqual(
            sha(source),
            "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D",
        )
        self.assertEqual(self.map["layouts"]["collection_progression"]["bound"], 150)
        self.assertEqual(
            set(self.map["layouts"]), {"collection_progression", "immediate_fixed"}
        )
        for mode in MODES[2:]:
            self.assertEqual(
                self.map["rendered_candidates"][mode],
                {"rejected": True, "reason": "Expanded-256 fail-closed"},
            )
        self.assertNotIn("base_expanded_payload_sha256", self.map)
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
            "0DD467627B8C8DCF69E0A800D1662B084FDFC7518D22353D3497F628037F6D67",
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

    def test_c254_cure_projection_is_resource_only_and_parent_is_frozen(self):
        parent = DLL.read_bytes()
        projection = CURE_PROJECTION.read_bytes()
        self.assertEqual(sha(parent), vv5_builder.COMPANION_PARENT_SHA256)
        cure = self.base_raw["cure_containment"]
        self.assertEqual(cure["parent_dll_sha256"], vv5_builder.COMPANION_PARENT_SHA256)
        self.assertEqual(cure["projection"]["size"], len(projection))
        self.assertEqual(cure["projection"]["sha256"], sha(projection))
        # The deterministic projection changes only the two Cure-bearing
        # dialog leaves; dialog 202 remains byte-identical to the parent.
        self.assertEqual(projection[0x47070:0x474F0], parent[0x47070:0x474F0])
        for raw, end, old_count, new_count in (
            (0x466C0, 0x47070, 46, 41),
            (0x474F0, 0x47C88, 36, 31),
        ):
            before = vv5_builder._vv5_dialog_item_spans(parent[raw:end], old_count)
            after = vv5_builder._vv5_dialog_item_spans(projection[raw:end], new_count)
            self.assertEqual(len(before) - len(after), 5)
            self.assertNotIn("Cure all Villagers", [title for _, _, title in after])

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
        self.assertEqual(
            helper[:19].hex().upper(),
            "83FB01740E83FB020F845D8AFEFFE97D8AFEFF",
        )
        self.assertEqual(helper.count(bytes.fromhex("B948415500")), 4)
        self.assertIn(bytes.fromhex("3D96000000"), helper)
        self.assertIn(bytes.fromhex("81E2FFFFFF7F"), helper)
        self.assertIn(bytes.fromhex("A0860100"), helper)
        for key in ("individual_insufficient", "individual_cancel", "individual_recheck", "individual_postverify"):
            self.assertIn(key, self.map["layouts"]["collection_progression"]["slot_map"]["installed"]["strings"])

    def test_individual_confirmation_and_recheck_strings_are_emitted_and_referenced(self):
        strings = self.map["layouts"]["collection_progression"]["slot_map"]["installed"]["strings"]
        page = bytes.fromhex(
            self.base_raw["pe_append_transaction"]["layouts"]["collection_progression"]["append_bytes"]
        )
        slot = bytes.fromhex(self.feature_raw["patches"][0]["after"])
        installed_page = page[:0x100] + slot + page[0x100 + len(slot) :]
        confirmation = installed_page[0x100 + 0x800 : 0x100 + 0x850]
        village_confirmation = installed_page[0x100 + 0x850 : 0x100 + 0xC00]
        confirm_ptr = int(strings["individual_confirm"], 0).to_bytes(4, "little")
        village_ptr = int(strings["village_confirm"], 0).to_bytes(4, "little")
        warning_ptr = int(strings["warning"], 0).to_bytes(4, "little")
        self.assertEqual(confirmation.count(b"\x68" + confirm_ptr), 1)
        self.assertNotIn(b"\x68" + warning_ptr, confirmation)
        self.assertEqual(village_confirmation.count(b"\x68" + village_ptr), 1)
        self.assertNotIn(b"\x68" + confirm_ptr, village_confirmation)
        self.assertNotIn(b"\x68" + warning_ptr, village_confirmation)
        self.assertIn(
            b"Grant Full Mastery to this villager for 100,000 tech points?\r\n"
            b"Press OK to confirm, or Cancel.\0",
            installed_page,
        )
        self.assertIn(
            b"Grant Full Mastery to all eligible villagers for 1,000,000 tech points?\r\n"
            b"Press OK to confirm, or Cancel.\0",
            installed_page,
        )
        self.assertIn(
            b"The selected villager changed or no longer passed the final checks.\r\n"
            b"No tech points have been deducted.\0",
            installed_page,
        )

        slot = bytes.fromhex(self.feature_raw["patches"][0]["after"])
        installed = self.map["layouts"]["collection_progression"]["slot_map"]["installed"]
        page_va = self.map["layouts"]["collection_progression"]["page_va"]
        slot_va = page_va + int(self.map["slot_layout"]["offset"], 0)
        confirm_va = slot_va + int(installed["confirmation_offset"])
        village_confirm_va = slot_va + int(installed["village_confirmation_offset"])
        entry_offset = int(self.map["slot_layout"]["entry_offset"], 0)
        entry = slot[entry_offset : entry_offset + installed["entry_length"]]
        entry_va = slot_va + entry_offset
        individual_offset = int(installed["individual_offset"])
        individual = slot[individual_offset : individual_offset + installed["individual_length"]]
        individual_va = slot_va + individual_offset
        self.assertIn(village_confirm_va, rel32_targets(entry, entry_va))
        self.assertNotIn(confirm_va, rel32_targets(entry, entry_va))
        self.assertIn(confirm_va, rel32_targets(individual, individual_va))
        self.assertEqual(installed["confirmation_sha256"], "234E2D9320A75D6B95DED0A682F13087294AE5E48F126DF30269C6F37653C18F")
        self.assertEqual(installed["individual_sha256"], "00AEE03769489F44BF308385F869D1B26AA64BA25083E38FC7C734C56D97C19B")
        self.assertEqual(self.feature_raw["transaction_contract"]["price"], 1_000_000)
        self.assertEqual(self.feature_raw["transaction_contract"]["individual_transaction"]["price"], 100_000)

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
        # The final-tree rebind makes generation deterministic again. Run it in
        # a disposable repository copy so discovery cannot rewrite tracked
        # authenticated manifests in this checkout.
        tracked = (BASE, FEATURE, MAP, DOC, DLL)
        originals = {path: path.read_bytes() for path in tracked}
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            replica = Path(temp_dir) / "repo"
            shutil.copytree(
                ROOT,
                replica,
                ignore=shutil.ignore_patterns(
                    ".git", ".tools", "outputs", "build", "__pycache__", ".tmp*", "tmp*"
                ),
            )
            result = subprocess.run(
                [sys.executable, str(replica / "scripts" / GENERATOR.name)],
                cwd=replica,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(originals, {path: path.read_bytes() for path in tracked})

    def test_c253_source_repair_is_explicitly_disabled_until_emitted_recertification(self):
        source = GENERATOR.read_text(encoding="utf-8")
        self.assertIn("NATIVE_FULLSCREEN_TRANSITION_VA = 0x404700", source)
        self.assertIn('feature_enabled = base.get("enabled") is True', source)
        self.assertIn("FULLSCREEN_TECH_OFFSET = 0xB40", source)
        self.assertIn("FULLSCREEN_DETAIL_OFFSET = 0xB47", source)
        self.assertIn("FULLSCREEN_COMMON_OFFSET = 0xB4C", source)
        self.assertIn("SDL_GET_MODULE_HANDLE_IAT = 0x4951D8", source)
        self.assertIn("SDL_GET_WINDOW_FLAGS_IAT = 0x4951DC", source)
        self.assertIn("NATIVE_FULLSCREEN_GETTER_VA = 0x4080C0", source)
        self.assertIn("NATIVE_FULLSCREEN_LEAVE_VA = 0x40A270", source)
        self.assertIn("NATIVE_FULLSCREEN_ENTER_VA = 0x40A280", source)
        self.assertIn("native_engine_transition_proof", source)
        self.assertIn("candidate remains disabled/catalog-hidden", source)
        self.assertNotIn("disabled C251 candidate", source)
        self.assertIn("strip_vv5_cure_rows", source)
        self.assertIn("cmp ebx, 5", source)
        self.assertIn("candidate-only; requires independent emitted DLL recertification", source)

    def test_c253_wrapper_contract_uses_native_engine_state_and_plain_menu_abi(self):
        source = GENERATOR.read_text(encoding="utf-8")
        wrapper = source[source.index("def build_fullscreen_wrapper"):source.index("def build_fullscreen_entry")]
        self.assertIn("mov edi, dword ptr [esi]", source)
        self.assertIn("mov eax, dword ptr [edi+0x38]", source)
        self.assertIn("movzx ebx, byte ptr [edi+0x1E]", source)
        self.assertIn("call 0x{NATIVE_FULLSCREEN_LEAVE_VA:X}", source)
        self.assertIn("call 0x{NATIVE_FULLSCREEN_ENTER_VA:X}", source)
        self.assertIn("mov ecx, esi\n            call 0x{NATIVE_FULLSCREEN_LEAVE_VA:X}", wrapper)
        self.assertNotIn("mov ecx, edi\n            call 0x{NATIVE_FULLSCREEN_LEAVE_VA:X}", wrapper)
        self.assertIn("and edx, 0x1001", wrapper)
        self.assertGreaterEqual(wrapper.count("and edx, 0x1001"), 2)
        self.assertIn("call 0x{NATIVE_FULLSCREEN_GETTER_VA:X}", wrapper)
        enter_index = wrapper.index("call 0x{NATIVE_FULLSCREEN_ENTER_VA:X}")
        leave_index = wrapper.index("call 0x{NATIVE_FULLSCREEN_LEAVE_VA:X}")
        self.assertLess(wrapper.find("call reacquire"), leave_index)
        self.assertNotEqual(wrapper.find("call 0x{NATIVE_FULLSCREEN_GETTER_VA:X}", enter_index), -1)
        self.assertNotIn("call dword ptr [0x{SDL_GET_MODULE_HANDLE_IAT:X}]\n            add esp", wrapper)
        self.assertNotIn("call dword ptr [0x{SDL_GET_WINDOW_FLAGS_IAT:X}]\n            add esp", wrapper)
        self.assertIn("ret\n        \"\"\"", source)
        self.assertNotIn("SDL_GET_KEYBOARD_FOCUS_RVA", source)
        self.assertNotIn("SDL_SET_WINDOW_FULLSCREEN_RVA", source)
        self.assertNotIn("ret 8", source[source.index("def build_fullscreen_wrapper"):source.index("def build_fullscreen_entry")])

    def test_c254_emitted_wrapper_disassembly_catches_d251_defects(self):
        from capstone import CS_ARCH_X86, CS_MODE_32, Cs

        active = json.loads((ROOT / "data" / "vv5_origins_feature.json").read_text(encoding="utf-8"))
        payload_patch = next(
            item for item in active["patches"] if int(item["offset"], 0) == vv5_builder.PAYLOAD_OFFSET
        )
        payload = vv5_builder.build_base_payload(
            bytes.fromhex(payload_patch["after"]).ljust(vv5_builder.PAYLOAD_SIZE, bytes([0])),
            vv5_builder.LAYOUTS["collection_progression"]["page_va"],
        )
        wrapper = vv5_builder.build_fullscreen_wrapper(
            vv5_builder.PAYLOAD_VA + vv5_builder.FULLSCREEN_COMMON_OFFSET,
            vv5_builder.PAYLOAD_VA + vv5_builder.FULLSCREEN_STRING_OFFSET,
        )
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        instructions = list(
            md.disasm(
                payload[
                    vv5_builder.FULLSCREEN_COMMON_OFFSET : vv5_builder.FULLSCREEN_COMMON_OFFSET + len(wrapper)
                ],
                vv5_builder.PAYLOAD_VA + vv5_builder.FULLSCREEN_COMMON_OFFSET,
            )
        )
        # Every SDL query is followed by a semantic 0x1001 mask, including the
        # post-leave query before the modal call.
        self.assertEqual(sum(1 for ins in instructions if ins.mnemonic == "and" and ins.op_str == "edx, 0x1001"), 3)
        flags_calls = [
            i for i, ins in enumerate(instructions)
            if ins.mnemonic == "call" and ins.op_str == "dword ptr [ebp - 0x28]"
        ]
        self.assertEqual(len(flags_calls), 3)
        for index in flags_calls:
            self.assertEqual(instructions[index - 1].mnemonic, "push")
            self.assertEqual(instructions[index - 1].op_str, "dword ptr [ebp - 0x20]")
            self.assertEqual(instructions[index + 1].mnemonic, "add")
            self.assertEqual(instructions[index + 1].op_str, "esp, 4")
        leave_index = next(i for i, ins in enumerate(instructions) if ins.mnemonic == "call" and f"0x{vv5_builder.NATIVE_FULLSCREEN_LEAVE_VA:x}" in ins.op_str)
        self.assertEqual(instructions[leave_index - 1].mnemonic, "mov")
        self.assertEqual(instructions[leave_index - 1].op_str, "ecx, esi")
        enter_index = next(i for i, ins in enumerate(instructions) if ins.mnemonic == "call" and f"0x{vv5_builder.NATIVE_FULLSCREEN_ENTER_VA:x}" in ins.op_str)
        self.assertTrue(any(ins.mnemonic == "call" and f"0x{vv5_builder.NATIVE_FULLSCREEN_GETTER_VA:x}" in ins.op_str for ins in instructions[enter_index + 1 :]))
        self.assertTrue(any(ins.mnemonic == "cmp" and ins.op_str == "edi, dword ptr [ebp - 0x1c]" for ins in instructions[leave_index:]))
        self.assertTrue(sum(ins.mnemonic == "cmp" and ins.op_str == "edi, dword ptr [ebp - 0x1c]" for ins in instructions) >= 3)
        self.assertTrue(any(ins.mnemonic == "call" and f"0x{vv5_builder.NATIVE_FULLSCREEN_GETTER_VA:x}" in ins.op_str for ins in instructions[enter_index + 1 :]))
        for i, ins in enumerate(instructions):
            if ins.mnemonic == "call" and ins.op_str in ("dword ptr [0x4951d8]", "dword ptr [0x4951dc]"):
                self.assertFalse(i + 1 < len(instructions) and instructions[i + 1].mnemonic == "add")
        for transition in (vv5_builder.NATIVE_FULLSCREEN_LEAVE_VA, vv5_builder.NATIVE_FULLSCREEN_ENTER_VA):
            index = next(i for i, ins in enumerate(instructions) if ins.mnemonic == "call" and f"0x{transition:x}" in ins.op_str)
            self.assertNotIn(instructions[index + 1].mnemonic, ("test", "cmp"))
        wrapper_lo = vv5_builder.PAYLOAD_VA + vv5_builder.FULLSCREEN_COMMON_OFFSET
        wrapper_hi = wrapper_lo + len(wrapper)
        self.assertTrue(
            any(
                ins.mnemonic == "call"
                and ins.op_str.startswith("0x")
                and wrapper_lo <= int(ins.op_str, 16) < wrapper_hi
                for ins in instructions
            )
        )
        self.assertEqual(instructions[-1].mnemonic, "ret")
        self.assertEqual(instructions[-1].op_str, "")
        self.assertFalse(vv5_builder.sha(wrapper).startswith("ED1059"))
        source = GENERATOR.read_text(encoding="utf-8")
        self.assertEqual(source.count("restore_start:"), 1)
        self.assertIn("jmp restore_start", source[source.index("post_leave_failed:"):source.index("restore_failed:")])

    def test_d252_candidate_companion_is_projection_with_exact_restore_parent(self):
        companion = self.base_raw["companion_files"]
        self.assertEqual(companion, [{
            "source": "data/candidates/VVFP VV5 Cure Containment Projection.dll",
            "destination": "VVFP Origins Icons.dll",
            "sha256": "A1C55063B548F195B9ECDA492E1799D35EBA5437862353D96BE780D9FCC2E1C8",
            "size": 298496,
            "preimage_sha256": "29927CECB448B64944E18E2BA11893DC84C91B39241FBB2549FC2A464E0BE2ED",
            "restore_source": "data/candidates/VVFP VV5 Full Mastery Candidate.dll",
            "restore_sha256": "29927CECB448B64944E18E2BA11893DC84C91B39241FBB2549FC2A464E0BE2ED",
            "parent": "data/candidates/VVFP VV5 Full Mastery Candidate.dll",
        }])
        self.assertEqual(self.map["companion"]["sha256"], companion[0]["sha256"])
        self.assertEqual(sha(CURE_PROJECTION.read_bytes()), companion[0]["sha256"])
        self.assertEqual(sha(DLL.read_bytes()), companion[0]["preimage_sha256"])
        self.assertTrue(self.base_raw["cure_containment"]["atomic_install_remove"])

    def test_c256_active_base_pin_and_fullscreen_cdecl_contract(self):
        active = ROOT / "data" / "vv5_origins_feature.json"
        certified_parent = {
            "path": "data/vv5_origins_feature.json",
            "size": 53747,
            "sha256": "F9643E2B7D115B6ECDDD4D8AD4BFFC73F2FF6937995E40E991041B6AF6463D44",
        }
        self.assertEqual(self.base_raw["active_base"], certified_parent)
        self.assertEqual(self.map["active_base"], certified_parent)
        self.assertEqual(active.stat().st_size, certified_parent["size"])
        self.assertEqual(sha(active.read_bytes()), certified_parent["sha256"])
        self.assertEqual(
            self.map["base_manifest_sha256"],
            sha(BASE.read_bytes()),
        )
        self.assertEqual(
            self.map["feature_manifest_sha256"],
            sha(FEATURE.read_bytes()),
        )
        sdl = self.base_raw["fullscreen_dialog_contract"]["sdl"]
        self.assertEqual(sdl["calls"], 3)
        self.assertEqual(sdl["abi"], "push SDL_Window*; indirect call; add esp,4 for each invocation")
        asset = self.base_raw["cure_containment"]["asset_policy"]
        self.assertEqual(asset["destination"], "Images\\btn_trophies.png")
        self.assertEqual(asset["sha256"], "F39E94CBDF24776631D803D1218EFCCDE555081C9C8C644DD073B75EC7DD2095")
        self.assertEqual(asset["operation"], "preserve-and-verify-stock-asset")
        self.assertEqual(self.map["asset_policy"], asset)

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
