from __future__ import annotations

import hashlib
import importlib.util
import json
import struct
import sys
import unittest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import vv_fun_patcher as patcher  # noqa: E402
from expanded_atomic_writer import CONFIGS  # noqa: E402
from vv5_individual_transactions import VV5Villager, execute  # noqa: E402


SPEC = importlib.util.spec_from_file_location(
    "vv5_task9_builder", ROOT / "scripts/build_vv5_task9_native_actions.py"
)
assert SPEC and SPEC.loader
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


MANIFEST = ROOT / "data/vv5_task9_native_actions.json"
MAP = ROOT / "data/candidates/vv5_task9_native_actions_map.json"
DLL = ROOT / "data/candidates/VVFP VV5 Task9 Origins Icons.dll"
ACTIVE = ROOT / "data/vv5_origins_feature.json"
NATIVE = ROOT / "native/vv5_task9_origins/vv5_task9_origins.c"
DEF = ROOT / "native/vv5_task9_origins/vv5_task9_origins.def"
RC = ROOT / "native/vv5_task9_origins/vv5_task9_origins.rc"
MODES = tuple(builder.LAYOUTS)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def canonical(value: object) -> str:
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii"))


def rel32_at(blob: bytes, blob_va: int, target: int) -> int:
    count = 0
    for offset in range(len(blob) - 4):
        if blob[offset] != 0xE8:
            continue
        displacement = int.from_bytes(blob[offset + 1 : offset + 5], "little", signed=True)
        if blob_va + offset + 5 + displacement == target:
            count += 1
    return count


def call_target(blob: bytes, blob_va: int, opcode_offset: int) -> int:
    if blob[opcode_offset] != 0xE8:
        raise AssertionError(f"no rel32 call at {opcode_offset:#x}")
    displacement = int.from_bytes(
        blob[opcode_offset + 1 : opcode_offset + 5], "little", signed=True
    )
    return blob_va + opcode_offset + 5 + displacement


class Task9ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.map = json.loads(MAP.read_text(encoding="utf-8"))
        cls.active = json.loads(ACTIVE.read_text(encoding="utf-8"))

    def test_pinned_active_base_and_c342_ledger_are_byte_frozen(self) -> None:
        self.assertEqual(patcher.source_text_sha256(ACTIVE.read_bytes()), builder.ACTIVE_SOURCE_TEXT_SHA256)
        active_rows = self.active["expanded_shr_relocations"]["patches"]
        task9_rows = self.manifest["expanded_shr_relocations"]["patches"]
        self.assertEqual(task9_rows, active_rows)
        self.assertEqual(len(task9_rows), 66)
        self.assertEqual(canonical(task9_rows), builder.C342_ROWS_SHA256)
        self.assertEqual(self.map["nonoverlap"]["c342_new_row_count"], 0)

    def test_generated_pages_match_manifest_and_map_exactly(self) -> None:
        for mode, layout in builder.LAYOUTS.items():
            page, page_map = builder.build_page(layout["page_va"])
            emitted = bytes.fromhex(
                self.manifest["pe_append_transaction"]["layouts"][mode]["append_bytes"]
            )
            self.assertEqual(emitted, page)
            self.assertEqual(digest(page), page_map["page_sha256"])
            self.assertEqual(digest(page), self.map["layouts"][mode]["page_sha256"])
            self.assertEqual(len(page), 0x8000)

    def test_resource_geometry_and_constructor_manager_abi_are_exact(self) -> None:
        payload = bytes.fromhex(next(
            row["after"] for row in self.manifest["patches"]
            if int(row["offset"], 0) == builder.PAYLOAD_OFFSET
        ))
        self.assertNotIn(bytes.fromhex("89F96A6A"), payload[0x40:0x180])
        self.assertEqual(payload.count(bytes.fromhex("6802000000")), 2)
        self.assertEqual(payload.count(bytes.fromhex("6889000000")), 2)
        self.assertNotIn(bytes.fromhex("6A48"), payload[0x40:0x180])
        stock = builder.STOCK.read_bytes()
        native_ctor = bytes.fromhex("B802000000506A6A8BCFE8")
        native_sequence = stock.find(native_ctor, 0x44920, 0x44960)
        self.assertEqual(native_sequence, 0x44946)
        self.assertEqual(call_target(stock, builder.IMAGE_BASE, 0x44950), 0x44FA20)

        build = next(item for item in patcher.load_builds() if item.id == "vv5")
        feature = next(
            item for item in patcher.load_fun_patches()
            if item.id == "vv5_enable_origins_exclusive_features"
        )
        source = ROOT / "research/stock-executables" / build.input_name
        for mode in MODES:
            rendered, _ = patcher.render_patched_bytes(source, build, mode, [feature.id])
            expanded = mode.startswith("experimental_expanded_256")
            payload_va = builder.EXPANDED_PAYLOAD_VA if expanded else builder.PAYLOAD_VA
            page_va = builder.LAYOUTS[mode]["page_va"]
            page_raw = builder.LAYOUTS[mode]["append_offset"]
            helper_raw = page_raw + builder.OFF["constructor_resource"]
            helper = rendered[helper_raw : helper_raw + builder.SIZES["constructor_resource"]]
            self.assertEqual(helper[0], 0xE8)
            self.assertEqual(call_target(helper, page_va + builder.OFF["constructor_resource"], 0), 0x44FBB0)
            self.assertEqual(helper[5:12], bytes.fromhex("89C15A6A6AFFE2"))
            for label, ctor_offset in (("tech", 0x40), ("detail", 0x100)):
                with self.subTest(mode=mode, constructor=label):
                    bridge_operand = int(
                        self.map["payload"]["geometry"][label]["allocation_bridge_operand_offset"],
                        0,
                    )
                    bridge_opcode = bridge_operand - 1
                    self.assertEqual(rendered[bridge_opcode - 1], 0x97)
                    self.assertEqual(
                        call_target(
                            rendered,
                            payload_va - builder.PAYLOAD_OFFSET,
                            bridge_opcode,
                        ),
                        page_va + builder.OFF["constructor_resource"],
                    )
                    lookup_opcode = builder.PAYLOAD_OFFSET + ctor_offset + 0x14
                    self.assertEqual(lookup_opcode, bridge_opcode + 5)
                    self.assertEqual(
                        call_target(
                            rendered,
                            payload_va - builder.PAYLOAD_OFFSET,
                            lookup_opcode,
                        ),
                        0x44FA20,
                    )
                    ctor = rendered[
                        builder.PAYLOAD_OFFSET + ctor_offset :
                        builder.PAYLOAD_OFFSET + ctor_offset + 0x80
                    ]
                    factory = ctor.find(bytes.fromhex("6A0D89F9E8"))
                    self.assertGreaterEqual(factory, 0)
                    self.assertEqual(
                        call_target(ctor, payload_va + ctor_offset, factory + 4),
                        0x401BD0,
                    )

    def test_resolver_guard_precedes_dereference_without_changing_c342_rows(self) -> None:
        payload = bytes.fromhex(next(
            row["after"] for row in self.manifest["patches"]
            if int(row["offset"], 0) == builder.PAYLOAD_OFFSET
        ))
        self.assertEqual(payload[0x271:0x276], bytes.fromhex("E8DA36C7FF"))
        self.assertEqual(payload[0x276], 0x68)
        self.assertEqual(payload[0x27B], 0xC3)
        for raw in (0xDB272, 0xDB283, 0xDB292):
            active_row = next(row for row in self.active["expanded_shr_relocations"]["patches"] if int(row["offset"], 0) == raw)
            relative = raw - builder.PAYLOAD_OFFSET
            expected = bytes.fromhex(active_row["before"])
            self.assertEqual(payload[relative : relative + 4], expected)
        for mode, layout in builder.LAYOUTS.items():
            page = bytes.fromhex(self.manifest["pe_append_transaction"]["layouts"][mode]["append_bytes"])
            helper = page[builder.OFF["resolve_manager"] : builder.OFF["resolve_manager"] + builder.SIZES["resolve_manager"]]
            self.assertLess(helper.find(bytes.fromhex("85C0")), helper.find(bytes.fromhex("8B98247E0100")))

    def test_record_resolution_never_enters_withdrawn_transitive_helpers(self) -> None:
        self.assertEqual(
            self.map["resolver_contract"],
            {
                "record_pointer_resolver": "0x46F950",
                "forbidden_transitive_helpers": ["0x466170", "0x471840"],
                "eligibility_order": [
                    "+0x1CD4 != 0",
                    "+0x1C40 signed > 0",
                    "+0x1CEC == 0",
                ],
            },
        )
        source = (ROOT / "scripts/build_vv5_task9_native_actions.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("call 0x471840", source)
        self.assertNotIn("call 0x466170", source)
        for mode, layout in builder.LAYOUTS.items():
            with self.subTest(mode=mode):
                page = bytes.fromhex(
                    self.manifest["pe_append_transaction"]["layouts"][mode][
                        "append_bytes"
                    ]
                )
                self.assertEqual(rel32_at(page, layout["page_va"], 0x471840), 0)
                self.assertEqual(rel32_at(page, layout["page_va"], 0x466170), 0)
                self.assertEqual(rel32_at(page, layout["page_va"], 0x46F950), 2)
                for name in ("resolve_index", "resolve_manager"):
                    routine = page[
                        builder.OFF[name] : builder.OFF[name] + builder.SIZES[name]
                    ]
                    active = routine.find(bytes.fromhex("80B8D41C000000"))
                    health = routine.find(bytes.fromhex("83B8401C000000"))
                    faction = routine.find(bytes.fromhex("80B8EC1C000000"))
                    self.assertGreaterEqual(active, 0)
                    self.assertLess(active, health)
                    self.assertLess(health, faction)

    def test_unsigned_detail_command_bound_is_before_any_action_resolution(self) -> None:
        page = bytes.fromhex(self.manifest["pe_append_transaction"]["layouts"]["collection_progression"]["append_bytes"])
        routine = page[builder.OFF["detail_menu"] : builder.OFF["detail_menu"] + builder.SIZES["detail_menu"]]
        bound = routine.find(bytes.fromhex("83FB03"))
        unsigned_above = routine.find(bytes.fromhex("77"), bound + 3)
        self.assertGreaterEqual(bound, 0)
        self.assertEqual(unsigned_above, bound + 3)
        self.assertNotIn(bytes.fromhex("E11C0000"), page)

    def test_exact_native_writer_and_single_charge_call_sites(self) -> None:
        layout = builder.LAYOUTS["collection_progression"]
        page = bytes.fromhex(self.manifest["pe_append_transaction"]["layouts"]["collection_progression"]["append_bytes"])
        page_va = layout["page_va"]
        contracts = {
            "age": {0x46F7F0: 1, 0x4237B0: 1},
            "mastery": {0x475730: 1, 0x4237B0: 1},
            "running": {0x464F90: 1, 0x464AD0: 1, 0x4649E0: 1, 0x4237B0: 1},
            "heal": {0x4758B0: 1, 0x413450: 3, 0x4237B0: 1},
        }
        for name, targets in contracts.items():
            routine = page[builder.OFF[name] : builder.OFF[name] + builder.SIZES[name]]
            routine_va = page_va + builder.OFF[name]
            for target, expected in targets.items():
                self.assertEqual(rel32_at(routine, routine_va, target), expected, (name, hex(target)))
        heal = page[builder.OFF["heal"] : builder.OFF["heal"] + builder.SIZES["heal"]]
        health_call = next(
            offset for offset in range(len(heal) - 4)
            if heal[offset] == 0xE8
            and page_va + builder.OFF["heal"] + offset + 5
            + int.from_bytes(heal[offset + 1 : offset + 5], "little", signed=True) == 0x4758B0
        )
        self.assertEqual(heal[health_call - 10 : health_call], bytes.fromhex("6AFF6A648D8E341C0000"))

    def test_companion_owner_abi_has_no_foreground_fallback(self) -> None:
        source = NATIVE.read_text(encoding="utf-8")
        generator = (ROOT / "scripts/build_vv5_task9_native_actions.py").read_text(encoding="utf-8")
        exports = DEF.read_text(encoding="utf-8")
        self.assertEqual(source.count("GetForegroundWindow()"), 1)
        self.assertIn("validate_same_process_window(GetForegroundWindow())", source)
        self.assertIn("GetWindowThreadProcessId", source)
        self.assertIn("GetCurrentProcessId", source)
        self.assertIn("IsWindow", source)
        self.assertIn("HWND owner = GetOriginsOwner();", source)
        self.assertNotIn("GetForegroundWindow(),\n            message", source)
        owner_started = generator.index("mov dword ptr [ebp-0x38], 1")
        begin_call = generator.index("call eax", owner_started)
        fullscreen_leave = generator.index("call 0x40A270", begin_call)
        centralized_cleanup = generator.index("cleanup:", fullscreen_leave)
        restore = generator.index("call 0x40A280", centralized_cleanup)
        end_owner = generator.index("end_owner:", restore)
        owner_end = generator.index("call dword ptr [ebp-0x34]", end_owner)
        self.assertLess(owner_started, begin_call)
        self.assertLess(begin_call, fullscreen_leave)
        self.assertLess(centralized_cleanup, restore)
        self.assertLess(restore, owner_end)
        for name in (
            "BeginOriginsOwner", "GetOriginsOwner", "EndOriginsOwner",
            "ShowOriginsUpgradeMenuState", "ConfirmVV5Task9Action", "ShowVV5Task9Result",
        ):
            self.assertIn(name, exports)
            self.assertIn(name.encode("ascii") + b"\0", DLL.read_bytes())

    def test_dialog_resources_expose_exact_six_plus_four_rows(self) -> None:
        resources = RC.read_text(encoding="utf-8")
        tech, detail = resources.split("202 DIALOGEX", 1)
        self.assertEqual(tech.count('PUSHBUTTON "Buy"'), 6)
        self.assertEqual(detail.count('PUSHBUTTON "Buy"'), 4)
        self.assertIn("Full Heal / Cure All", tech)
        self.assertIn("Grant Running", detail)

    def test_append_layouts_preserve_atomic_ranges_and_exact_pe_guards(self) -> None:
        layouts = self.manifest["pe_append_transaction"]["layouts"]
        for mode in ("collection_progression", "immediate_fixed"):
            self.assertEqual(int(layouts[mode]["append_offset"], 0), 0xF2000)
            self.assertEqual(int(layouts[mode]["page_virtual_address"], 0), 0x7C9000)
        for mode in ("experimental_expanded_256", "experimental_expanded_256_progression"):
            self.assertEqual(int(layouts[mode]["append_offset"], 0), 0xF4000)
            self.assertEqual(int(layouts[mode]["page_virtual_address"], 0), 0x904000)
            self.assertEqual(int(layouts[mode]["header_patches"][2]["offset"], 0), 0x308)
        self.assertEqual(self.map["nonoverlap"]["task9_expanded_append_range"], ["0xF4000", "0xFC000"])

    def test_expanded_hook_fix_is_task9_owned_and_outside_frozen_c342(self) -> None:
        expected = {
            mode: [builder.TASK9_EXPANDED_HOOK]
            for mode in (
                "experimental_expanded_256",
                "experimental_expanded_256_progression",
            )
        }
        self.assertEqual(
            self.manifest["task9_expanded_post_relocation_patches"], expected
        )
        offsets = {
            int(row["offset"], 0)
            for row in self.manifest["expanded_shr_relocations"]["patches"]
        }
        self.assertNotIn(0x415F1, offsets)
        audit = self.map["expanded_cross_section_hook_audit"]
        self.assertEqual(audit["hook_count"], 7)
        self.assertEqual(audit["hooks"], builder.TASK9_CROSS_SECTION_HOOKS)
        self.assertEqual(audit["task9_post_relocation_hook_offset"], "0x415F0")
        self.assertEqual(audit["task9_post_relocation_operand_offset"], "0x415F1")
        self.assertFalse(audit["c342_changed"])

    def test_source_bindings_are_closed_and_current(self) -> None:
        bindings = self.manifest["source_bindings"]
        self.assertEqual(bindings, self.map["source_bindings"])
        self.assertEqual(set(bindings), set(builder.SOURCE_PATHS))
        for name, path in builder.SOURCE_PATHS.items():
            with self.subTest(source=name):
                self.assertEqual(bindings[name]["path"], path)
                self.assertEqual(
                    bindings[name]["source_text_sha256"],
                    patcher.source_text_sha256((ROOT / path).read_bytes()),
                )
        expected_atomic = {
            "commit": builder.ATOMIC_CORE_COMMIT,
            "generator_source_text_sha256": builder.ATOMIC_SOURCE_TEXT_SHA256[
                "atomic_generator"
            ],
            "contract_source_text_sha256": builder.ATOMIC_SOURCE_TEXT_SHA256[
                "atomic_contract"
            ],
        }
        self.assertEqual(self.manifest["atomic_core"], expected_atomic)
        self.assertEqual(self.map["atomic_core"], expected_atomic)

    def test_heal_type12_and_withdrawn_gate_are_fail_closed_in_emitted_bytes(self) -> None:
        serialized = json.dumps(self.manifest, sort_keys=True).upper()
        self.assertNotIn("1CE1", serialized)
        self.assertNotIn("E11C0000", serialized)
        self.assertEqual(
            self.manifest["task9_contract"]["actions"]["full_heal"]["unsupported_type"],
            "+0x1CFC == 12 when sick",
        )
        page = bytes.fromhex(
            self.manifest["pe_append_transaction"]["layouts"]["collection_progression"]["append_bytes"]
        )
        heal = page[builder.OFF["heal"] : builder.OFF["heal"] + builder.SIZES["heal"]]
        self.assertEqual(heal.count(bytes.fromhex("837F100C")), 1)
        self.assertIn(bytes.fromhex("C686481C00000080BE481C000000"), heal)

    def test_running_rollback_requires_an_exact_evolving_reacquire(self) -> None:
        source = (ROOT / "scripts/build_vv5_task9_native_actions.py").read_text(encoding="utf-8")
        rollback = source[source.index("rollback_dislikes:") : source.index("invalid:", source.index("rollback_dislikes:"))]
        self.assertGreaterEqual(rollback.count("call running_reacquire_evolving"), 2)
        self.assertNotIn("call 0x{page_va + OFF['resolve_index']:X}", rollback)


class Task9ReferenceAdversarialTests(unittest.TestCase):
    def villager(self, **changes: object) -> VV5Villager:
        base = VV5Villager(
            index=4,
            identity="villager-4",
            record_pointer="0x12340000",
            active=True,
            health=75,
            faction=0,
            age=900,
            age_companion=1200,
            age_timer=1600,
            skills=(10.0, 20.0, 30.0, 40.0, 50.0, 60.0),
            likes=(-1, 7, -1),
            dislikes=(38, 9, 38),
        )
        return replace(base, **changes)

    def run_action(self, villager: VV5Villager, action: str, confirm: int = 1, funds: int = 200000, **kw: object):
        return execute(
            villager,
            funds,
            action,
            confirm,
            before_reacquire=kw.pop("before_reacquire", lambda value: value),
            before_funds_reacquire=kw.pop("before_funds_reacquire", lambda value: value),
            **kw,
        )

    def test_cancel_noop_insufficient_and_identity_change_never_charge(self) -> None:
        cancelled = self.run_action(self.villager(), "youth", confirm=2)
        noop = self.run_action(self.villager(likes=(38, 7, -1)), "running")
        insufficient = self.run_action(self.villager(), "full_mastery", funds=99999)
        changed = self.run_action(
            self.villager(),
            "age_18",
            before_reacquire=lambda value: replace(value, record_pointer="0xDEADBEEF"),
        )
        self.assertEqual(
            [cancelled.status, noop.status, insufficient.status, changed.status],
            ["cancelled", "no_change", "insufficient_funds", "recheck_failed"],
        )
        self.assertTrue(all(not item.charged for item in (cancelled, noop, insufficient, changed)))
        self.assertEqual(noop.villager.dislikes, (38, 9, 38))

    def test_age18_uses_one_signed_delta_for_both_companions(self) -> None:
        result = self.run_action(self.villager(age=900, age_companion=1200, age_timer=1600), "age_18")
        self.assertEqual(result.status, "committed")
        self.assertEqual((result.villager.age, result.villager.age_companion, result.villager.age_timer), (360, 660, 1060))
        zero_timer = self.run_action(self.villager(age_timer=0), "age_18")
        self.assertEqual(zero_timer.villager.age_timer, 0)

    def test_write_failure_discloses_retained_effects_without_charge(self) -> None:
        result = self.run_action(self.villager(), "full_mastery", force_postverify_failure=True)
        self.assertEqual(result.status, "postverify_failed")
        self.assertTrue(result.effects_may_have_occurred)
        self.assertFalse(result.charged)
        self.assertEqual(result.charge_truth, "not_attempted")

    def test_charge_readback_failure_never_claims_no_charge(self) -> None:
        result = self.run_action(self.villager(), "running", force_charge_failure=True)
        self.assertEqual(result.status, "charge_failed")
        self.assertTrue(result.effects_may_have_occurred)
        self.assertFalse(result.funds_known)
        self.assertEqual(result.charge_truth, "unknown")
        self.assertNotIn("No tech points have been deducted", result.message)


class Task9RendererMatrixTests(unittest.TestCase):
    def test_legacy_same_id_record_remains_c342_only_without_task9_post_hook(self) -> None:
        build = next(item for item in patcher.load_builds() if item.id == "vv5")
        source = ROOT / "research/stock-executables" / build.input_name
        legacy = patcher.FunPatch(json.loads(ACTIVE.read_text(encoding="utf-8")))
        self.assertEqual(legacy.id, "vv5_enable_origins_exclusive_features")
        self.assertNotIn("task9_expanded_post_relocation_patches", legacy.raw)
        for mode in (
            "experimental_expanded_256",
            "experimental_expanded_256_progression",
        ):
            with self.subTest(mode=mode):
                rendered, applied = patcher.render_patched_bytes(
                    source,
                    build,
                    mode,
                    _fun_patches_override=[legacy],
                )
                self.assertEqual(
                    [
                        row for row in applied
                        if row.get("relocation_status")
                        == "task9_post_relocation_hook"
                    ],
                    [],
                )
                self.assertEqual(
                    bytes(rendered[0x415F0 : 0x415F8]),
                    bytes.fromhex(builder.TASK9_EXPANDED_HOOK["before"]),
                )

    def test_atomic_core_is_an_exact_noop_in_all_six_stock_compositions(self) -> None:
        sources = {
            "vv3": ROOT / "research/stock-executables/Virtual Villagers - The Secret City.exe",
            "vv4": ROOT / "inputs/vv4-stock-copy/Virtual Villagers - The Tree of Life.exe",
            "vv5": ROOT / "inputs/vv5-stock-copy/Virtual Villagers - New Believers.exe",
        }
        for game_id, source in sources.items():
            build = patcher.identify(source)
            for mode in ("collection_progression", "immediate_fixed"):
                with self.subTest(game=game_id, mode=mode):
                    data = bytearray(source.read_bytes())
                    before = bytes(data)
                    records, ranges = patcher._apply_reviewed_expanded_atomic_writer(
                        data, build, mode
                    )
                    self.assertEqual(records, [])
                    self.assertEqual(ranges, [])
                    self.assertEqual(bytes(data), before)

    def test_stock_and_expanded_final_layouts(self) -> None:
        build = next(item for item in patcher.load_builds() if item.id == "vv5")
        feature = next(
            item for item in patcher.load_fun_patches()
            if item.id == "vv5_enable_origins_exclusive_features"
        )
        source = ROOT / "research/stock-executables" / build.input_name
        expected = {
            "collection_progression": (0xFA000, 6, 0x3D1000),
            "immediate_fixed": (0xFA000, 6, 0x3D1000),
            "experimental_expanded_256": (0xFC000, 8, 0x50C000),
            "experimental_expanded_256_progression": (0xFC000, 8, 0x50C000),
        }
        for mode in MODES:
            rendered, _ = patcher.render_patched_bytes(source, build, mode, [feature.id])
            pe = struct.unpack_from("<I", rendered, 0x3C)[0]
            self.assertEqual(len(rendered), expected[mode][0])
            self.assertEqual(struct.unpack_from("<H", rendered, pe + 6)[0], expected[mode][1])
            self.assertEqual(struct.unpack_from("<I", rendered, pe + 24 + 56)[0], expected[mode][2])
            append = int(self.manifest_layout(mode)["append_offset"], 0)
            page = bytes.fromhex(self.manifest_layout(mode)["append_bytes"])
            self.assertEqual(bytes(rendered[append : append + len(page)]), page)
            if mode.startswith("experimental"):
                self.assertEqual(bytes(rendered[0xF2000:0xF4000]), self.atomic_parent(mode))

    def test_final_pe_cross_section_hooks_are_all_relocated_or_explicitly_preserved(self) -> None:
        build = next(item for item in patcher.load_builds() if item.id == "vv5")
        feature = next(
            item for item in patcher.load_fun_patches()
            if item.id == "vv5_enable_origins_exclusive_features"
        )
        source = ROOT / "research/stock-executables" / build.input_name
        native_overrides = {
            0x1EB6F: bytes.fromhex("85F67E3456"),
            0x237B0: bytes.fromhex("568B742408"),
        }
        for mode in MODES:
            rendered, applied = patcher.render_patched_bytes(
                source, build, mode, [feature.id]
            )
            expanded = mode.startswith("experimental_expanded_256")
            post = [
                row for row in applied
                if row.get("relocation_status") == "task9_post_relocation_hook"
            ]
            self.assertEqual(len(post), 1 if expanded else 0)
            for raw_text, contract in builder.TASK9_CROSS_SECTION_HOOKS.items():
                raw = int(raw_text, 0)
                with self.subTest(mode=mode, hook=raw_text):
                    if expanded and contract["expanded_policy"] == "native_override_preserved":
                        self.assertEqual(rendered[raw : raw + 5], native_overrides[raw])
                        continue
                    self.assertEqual(rendered[raw], 0xE9)
                    source_va = int(
                        patcher._virtual_address_for_offset(rendered, raw), 0
                    )
                    target = source_va + 5 + int.from_bytes(
                        rendered[raw + 1 : raw + 5], "little", signed=True
                    )
                    self.assertEqual(
                        target,
                        int(
                            contract[
                                "expanded_target" if expanded else "stock_target"
                            ],
                            0,
                        ),
                    )

    def test_six_expanded_optional_statistics_compositions_keep_atomic_inner_writer(self) -> None:
        sources = {
            "vv3": ROOT / "research/stock-executables/Virtual Villagers - The Secret City.exe",
            "vv4": ROOT / "inputs/vv4-stock-copy/Virtual Villagers - The Tree of Life.exe",
            "vv5": ROOT / "inputs/vv5-stock-copy/Virtual Villagers - New Believers.exe",
        }
        catalog = {item.id: item for item in patcher.load_fun_patches()}
        vv3_core = [
            patcher.FunPatch(json.loads((
                ROOT / "data/candidates/vv3_origins_running_base_candidate.json"
            ).read_text(encoding="utf-8"))),
            patcher.FunPatch(json.loads((
                ROOT / "data/candidates/vv3_all_villagers_like_running_candidate.json"
            ).read_text(encoding="utf-8"))),
        ]
        for game_id, source in sources.items():
            build = patcher.identify(source)
            statistics = catalog[f"{game_id}_write_village_statistics"]
            features = [*vv3_core, statistics] if game_id == "vv3" else [statistics]
            if game_id == "vv5":
                features.insert(0, catalog["vv5_enable_origins_exclusive_features"])
            wrapper = next(
                row for row in statistics.patches
                if len(patcher._patch_bytes(row, "after")) == 0x200
                and patcher._patch_bytes(row, "before") == bytes(0x200)
            )
            wrapper_raw = int(wrapper["offset"], 0)
            outer = next(
                row for row in statistics.patches
                if int(row["offset"], 0) in {raw for raw, _, _ in CONFIGS[game_id].callsites}
            )
            for mode in (
                "experimental_expanded_256",
                "experimental_expanded_256_progression",
            ):
                with self.subTest(game=game_id, mode=mode):
                    rendered, applied = patcher.render_patched_bytes(
                        source,
                        build,
                        mode,
                        _fun_patches_override=features,
                    )
                    outer_raw = int(outer["offset"], 0)
                    self.assertEqual(
                        rendered[outer_raw : outer_raw + len(patcher._patch_bytes(outer, "after"))],
                        patcher._patch_bytes(outer, "after"),
                    )
                    wrapper_bytes = bytes(rendered[wrapper_raw : wrapper_raw + 0x200])
                    wrapper_va = int(
                        patcher._virtual_address_for_offset(rendered, wrapper_raw), 0
                    )
                    self.assertEqual(
                        rel32_at(wrapper_bytes, wrapper_va, CONFIGS[game_id].writer_va),
                        1,
                    )
                    self.assertEqual(
                        rel32_at(wrapper_bytes, wrapper_va, CONFIGS[game_id].stock_writer_va),
                        0,
                    )
                    atomic = patcher._expanded_atomic_writer_summary(
                        applied, digest(rendered)
                    )
                    self.assertEqual(
                        [row["atomic_writer_id"] for row in atomic],
                        [f"{game_id}_expanded_atomic_writer"],
                    )
                    if game_id == "vv5":
                        layout = self.manifest_layout(mode)
                        append = int(layout["append_offset"], 0)
                        self.assertEqual(
                            bytes(rendered[append : append + 0x8000]),
                            bytes.fromhex(layout["append_bytes"]),
                        )

    @staticmethod
    def manifest_layout(mode: str) -> dict[str, object]:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))["pe_append_transaction"]["layouts"][mode]

    @staticmethod
    def atomic_parent(mode: str) -> bytes:
        build = next(item for item in patcher.load_builds() if item.id == "vv5")
        source = ROOT / "research/stock-executables" / build.input_name
        parent, _ = patcher.render_patched_bytes(source, build, mode, _fun_patches_override=[])
        return bytes(parent[0xF2000:0xF4000])


if __name__ == "__main__":
    unittest.main()
