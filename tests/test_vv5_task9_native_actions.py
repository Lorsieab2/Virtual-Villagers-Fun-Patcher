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
MODES = ("collection_progression", "immediate_fixed")


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
        # The 66-row expanded-256 relocation ledger is removed: it only ever
        # served a mode that is not selectable and that no variant applies,
        # while its hand-recorded byte snapshots blocked every payload edit.
        # The guard now asserts it stays gone rather than staying frozen.
        self.assertEqual(len(task9_rows), 0)
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

    def test_tech_result_paths_exit_the_custom_menu_once(self) -> None:
        sys.path.insert(0, str(ROOT / ".tools" / "capstone"))
        from capstone import CS_ARCH_X86, CS_MODE_32, Cs

        # The stock layout (0x7C9000) enables Time Warp (command 0), Island Event
        # (command 1), and Barrel of Babies (command 2), adding three result
        # paths and shifting the offsets/`done` target; the expanded-256 baseline
        # keeps the original seven paths.
        stock_offsets = [
            0x124, 0x1D5, 0x1E2, 0x1EF, 0x1FC, 0x209, 0x216, 0x223,
            0x230, 0x23A, 0x244, 0x24E, 0x258, 0x262, 0x273, 0x284, 0x295, 0x2A6,
        ]
        stock_done = 0xAEB
        expanded_offsets = [0xB6, 0x118, 0x122, 0x133, 0x144, 0x155, 0x166]
        expanded_done = 0x9AB
        for mode, layout in builder.LAYOUTS.items():
            page, page_map = builder.build_page(layout["page_va"])
            start = builder.OFF["tech_menu"]
            size = page_map["routine_length"]["tech_menu"]
            instructions = list(
                Cs(CS_ARCH_X86, CS_MODE_32).disasm(
                    page[start : start + size], layout["page_va"] + start
                )
            )
            jumps = {
                item.address - (layout["page_va"] + start): int(item.op_str, 16)
                for item in instructions
                if item.mnemonic == "jmp"
            }
            native_time_warp = layout["page_va"] == 0x7C9000
            expected_offsets = stock_offsets if native_time_warp else expanded_offsets
            done_target = stock_done if native_time_warp else expanded_done
            with self.subTest(mode=mode):
                self.assertEqual(
                    [jumps[offset] for offset in expected_offsets],
                    [layout["page_va"] + done_target] * len(expected_offsets),
                )

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
        # These three rel32 operands must not move when the resolver guard is
        # added. They used to be cross-checked against the expanded-256
        # relocation ledger; with that ledger removed the expected bytes are
        # pinned directly, which is what the check always actually meant.
        for raw, expected_hex in (
            (0xDB272, "DA36C7FF"),
            (0xDB283, "B9F5CBFF"),
            (0xDB292, "BAD6CBFF"),
        ):
            relative = raw - builder.PAYLOAD_OFFSET
            self.assertEqual(
                payload[relative : relative + 4], bytes.fromhex(expected_hex),
                f"payload rel32 operand at {raw:#x} moved",
            )
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
                    "+0x1CE1 == 0",
                    "+0x1CEC == 0",
                    "+0x1C40 signed > 0",
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
                    mask = routine.find(bytes.fromhex("80B8E11C000000"))
                    health = routine.find(bytes.fromhex("83B8401C000000"))
                    faction = routine.find(bytes.fromhex("80B8EC1C000000"))
                    self.assertGreaterEqual(active, 0)
                    self.assertLess(active, mask)
                    self.assertLess(mask, faction)
                    self.assertLess(faction, health)

    def test_unsigned_detail_command_bound_is_before_any_action_resolution(self) -> None:
        page = bytes.fromhex(self.manifest["pe_append_transaction"]["layouts"]["collection_progression"]["append_bytes"])
        routine = page[builder.OFF["detail_menu"] : builder.OFF["detail_menu"] + builder.SIZES["detail_menu"]]
        # Stock layout enables Change Appearance as command 4, so the unsigned
        # command bound is `cmp ebx, 4` (83FB04) before any action resolution.
        bound = routine.find(bytes.fromhex("83FB04"))
        unsigned_above = routine.find(bytes.fromhex("77"), bound + 3)
        self.assertGreaterEqual(bound, 0)
        self.assertEqual(unsigned_above, bound + 3)

    def test_stock_full_support_and_expanded_limited_capability_are_distinct(self) -> None:
        native = NATIVE.read_text(encoding="utf-8")
        self.assertIn("STATE_LIMITED_CAPABILITY = 0x400000", native)
        self.assertIn("int first_unsupported_row = villager_menu ? 4 : 6;", native)
        self.assertIn(
            "if (limited_capability && row >= first_unsupported_row)", native
        )
        self.assertIn('SetDlgItemTextA(window, ID_BUY_FIRST + row, "Unavailable")', native)

        stock, _ = builder.build_page(0x7C9000)
        expanded, _ = builder.build_page(0x904000)
        stock_tech = stock[builder.OFF["tech_menu"] : builder.OFF["tech_menu"] + builder.SIZES["tech_menu"]]
        expanded_tech = expanded[builder.OFF["tech_menu"] : builder.OFF["tech_menu"] + builder.SIZES["tech_menu"]]
        stock_detail = stock[builder.OFF["detail_menu"] : builder.OFF["detail_menu"] + builder.SIZES["detail_menu"]]
        expanded_detail = expanded[builder.OFF["detail_menu"] : builder.OFF["detail_menu"] + builder.SIZES["detail_menu"]]
        expanded_show = expanded[builder.OFF["show_menu"] : builder.OFF["show_menu"] + builder.SIZES["show_menu"]]

        # Stock carries no architecture flag and accepts all fourteen Tech
        # rows plus all five Details rows.
        self.assertIn(bytes.fromhex("B800000000"), stock_tech)
        stock_tech_bound = stock_tech.find(bytes.fromhex("83FB0D"))
        stock_detail_bound = stock_detail.find(bytes.fromhex("83FB04"))
        self.assertGreaterEqual(stock_tech_bound, 0)
        self.assertGreaterEqual(stock_detail_bound, 0)
        # The stock Tech routine is larger, so Keystone uses a near unsigned
        # jump there; both forms are an immediate fail-closed bound.
        self.assertIn(stock_tech[stock_tech_bound + 3], (0x77, 0x0F))
        if stock_tech[stock_tech_bound + 3] == 0x0F:
            self.assertEqual(stock_tech[stock_tech_bound + 4], 0x87)  # ja done
        self.assertEqual(stock_detail[stock_detail_bound + 3], 0x77)  # ja done

        # Expanded carries the dedicated flag, and its unsigned bounds reject
        # the first unsupported Tech/Details rows before any action dispatch.
        self.assertIn(
            (
                bytes([0xB8])
                + (0x700).to_bytes(4, "little")
            ),
            expanded_tech,
        )
        self.assertIn(
            (bytes([0x0D]) + builder.STATE_LIMITED_CAPABILITY.to_bytes(4, "little")),
            expanded_show,
        )
        self.assertIn(
            bytes.fromhex("89C38B450C0D0000400050FF7508FFD3"), expanded_show
        )
        # The separate Expanded Time Warp overlay still sees its exact Task9
        # Tech-menu preimages; capability state is injected in show_menu.
        self.assertEqual(
            expanded_tech[0x6:0x10], bytes.fromhex("B800070000F70588D351")
        )
        self.assertEqual(
            expanded_tech[0x6B:0x74], bytes.fromhex("83FB030F82B3000000")
        )
        expanded_tech_bound = expanded_tech.find(bytes.fromhex("83FB05"))
        expanded_detail_bound = expanded_detail.find(bytes.fromhex("83FB03"))
        self.assertGreaterEqual(expanded_tech_bound, 0)
        self.assertGreaterEqual(expanded_detail_bound, 0)
        self.assertIn(expanded_tech[expanded_tech_bound + 3], (0x77, 0x0F))  # row 6+ -> done
        if expanded_tech[expanded_tech_bound + 3] == 0x0F:
            self.assertEqual(expanded_tech[expanded_tech_bound + 4], 0x87)
        self.assertEqual(expanded_detail[expanded_detail_bound + 3], 0x77)  # row 4+ -> done

    def test_limited_capability_state_is_disjoint_from_dialog_state_bits(self) -> None:
        # The companion interprets bits 0..13 as row-state bits and bits 8..21
        # as unavailable-row bits. STATE_VILLAGER is bit 16; include it
        # explicitly even though it lies inside the existing unavailable range
        # so this test protects the named ABI contract as well.
        row_state_bits = sum(1 << row for row in range(14))
        unavailable_bits = sum(1 << (8 + row) for row in range(14))
        state_villager = 0x10000
        used_dialog_bits = row_state_bits | unavailable_bits | state_villager
        flag = builder.STATE_LIMITED_CAPABILITY

        self.assertEqual(row_state_bits, 0x3FFF)
        self.assertEqual(unavailable_bits, 0x3FFF00)
        self.assertEqual(used_dialog_bits, 0x3FFFFF)
        self.assertEqual(flag, 1 << used_dialog_bits.bit_length())
        self.assertGreater(flag, used_dialog_bits)
        self.assertEqual(flag & used_dialog_bits, 0)

    def test_exact_native_writer_and_single_charge_call_sites(self) -> None:
        layout = builder.LAYOUTS["collection_progression"]
        page = bytes.fromhex(self.manifest["pe_append_transaction"]["layouts"]["collection_progression"]["append_bytes"])
        page_va = layout["page_va"]
        contracts = {
            "age": {0x46F7F0: 1, 0x4237B0: 1},
            "mastery": {0x475730: 1, 0x4237B0: 1},
            "running": {0x464F90: 1, 0x464AD0: 1, 0x4649E0: 2, 0x4237B0: 1},
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
        # One in the owner capture (BeginOriginsOwner) and one as the modal
        # parent of the Change Appearance picker; neither is an owner fallback.
        self.assertEqual(source.count("GetForegroundWindow()"), 2)
        self.assertIn("validate_same_process_window(GetForegroundWindow())", source)
        self.assertIn("GetWindowThreadProcessId", source)
        self.assertIn("GetCurrentProcessId", source)
        self.assertIn("IsWindow", source)
        self.assertIn("HWND owner = GetOriginsOwner();", source)
        self.assertNotIn("GetForegroundWindow(),\n            message", source)
        # VV5-specific safest fullscreen fix (VV2 general approach): modal_common
        # captures the same-process owner (BeginOriginsOwner), invokes the menu
        # owner-parented, and releases it (EndOriginsOwner) -- with NO SDL
        # fullscreen leave/restore. The game stays in its borderless (desktop)
        # fullscreen behind the owned modal instead of being dropped to a window.
        self.assertNotIn("call 0x40A270", generator)  # no fullscreen-leave
        self.assertNotIn("call 0x40A280", generator)  # no fullscreen-restore
        owner_started = generator.index("mov dword ptr [ebp-0x38], 1")
        begin_call = generator.index("call eax", owner_started)
        invoke = generator.index("call dword ptr [ebp-0x10]", begin_call)
        end_owner = generator.index("end_owner:", invoke)
        owner_end = generator.index("call eax", end_owner)  # EndOriginsOwner
        self.assertLess(owner_started, begin_call)
        self.assertLess(begin_call, invoke)
        self.assertLess(invoke, end_owner)
        self.assertLess(end_owner, owner_end)
        for name in (
            "BeginOriginsOwner", "GetOriginsOwner", "EndOriginsOwner",
            "ShowOriginsUpgradeMenuState", "ConfirmVV5Task9Action", "ShowVV5Task9Result",
        ):
            self.assertIn(name, exports)
            self.assertIn(name.encode("ascii") + b"\0", DLL.read_bytes())

    def test_equal_division_of_labor_rows_wired_and_believer_gated(self) -> None:
        native = NATIVE.read_text(encoding="utf-8")
        exports = DEF.read_text(encoding="utf-8")
        dll = DLL.read_bytes()
        # The two Tech rows (commands 11/12) drive the companion DLL export
        # ApplyVV5EqualDivision(base, parenting).
        self.assertIn("ApplyVV5EqualDivision=_ApplyVV5EqualDivision@8", exports)
        self.assertIn(b"ApplyVV5EqualDivision\0", dll)
        self.assertIn("Equal Division of Labor (Includes Parenting)", native)
        self.assertIn("Equal Division of Labor (No Parenting)", native)
        # Seat -> preferred-skill-index cycles: Includes = Farming, Building,
        # Research, Healing, Parenting, Devotion; No-Parenting drops Parenting.
        self.assertIn("index_parenting[6] = { 0, 4, 3, 2, 1, 5 }", native)
        self.assertIn("index_no_parenting[5] = { 0, 4, 3, 2, 5 }", native)
        # Believer-only gate + the preferred-skill index field it overwrites.
        for offset in ("0x1CD4", "0x1CE1", "0x1CEC", "0x1C40", "0x1B90", "0x1C74"):
            self.assertIn(offset, native)
        # The result box is parented to the captured origins owner, never a
        # GetForegroundWindow() fullscreen-drop fallback.
        self.assertIn("HWND owner = GetOriginsOwner();", native)
        self.assertNotIn("GetForegroundWindow(), message", native)
        # The count is now pluralised, so the noun is a %s the helper fills
        # in ("Set 1 Villager's ..." against "Set 4 Villagers' ..."). Pin the
        # invariant part plus the chooser rather than the old fixed literal.
        self.assertIn("Set %u %s Job Preferences.", native)
        self.assertIn("vpl_pos", native)
        # The two native routines and the DLL-call helper exist only in the stock
        # layout; the expanded-256 baseline page stays byte-identical.
        _, stock_map = builder.build_page(0x7C9000)
        _, expanded_map = builder.build_page(0x904000)
        for name in ("division_parenting", "division_no_parenting", "apply_division"):
            self.assertIn(name, stock_map["routine_length"])
            self.assertNotIn(name, expanded_map["routine_length"])

    def test_dialog_resources_expose_exact_fourteen_plus_five_rows(self) -> None:
        resources = RC.read_text(encoding="utf-8")
        tech, detail = resources.split("202 DIALOGEX", 1)
        # Fourteen tech rows now: Time Warp, Island Event, Barrel of Babies, Tech
        # Point Doubler, Food Point Doubler, Full Heal/Cure All, Grant Running to
        # All Villagers, Grant Full Mastery to All Villagers, Set all Villagers to
        # 18, Complete all Collections, Reset all Collections, the two Equal
        # Division of Labor rows (Includes Parenting / No Parenting), and Change
        # Appearance for All.
        self.assertEqual(tech.count('PUSHBUTTON "Buy"'), 14)
        # Five villager rows: Youth, Mastery, Running, Age 18, Change Appearance.
        # The picker dialog 203 uses arrow/OK/Cancel, not "Buy".
        self.assertEqual(detail.count('PUSHBUTTON "Buy"'), 5)
        self.assertIn("Full Heal / Cure All", tech)
        self.assertIn("Complete All Collections", tech)
        self.assertIn("Reset All Collections", tech)
        self.assertIn("Grant Running to All Villagers", tech)
        self.assertIn("Grant Full Mastery to All Villagers", tech)
        self.assertIn("All Villagers are Exactly 18", tech)
        self.assertIn("Equal Division of Labor (Includes Parenting)", tech)
        self.assertIn("Equal Division of Labor (No Parenting)", tech)
        self.assertIn("Change Appearance for All", tech)
        self.assertIn("Grant Running", detail)
        self.assertIn("Change Appearance", detail)
        # Both Upgrade menus advertise the ESC exit hint.
        self.assertIn("Press ESC to exit this menu.", tech)
        self.assertIn("Press ESC to exit this menu.", detail)

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
        self.assertIn("1CE1", serialized)
        self.assertEqual(
            self.manifest["task9_contract"]["actions"]["full_heal"]["unsupported_type"],
            "+0x1CFC == 12 when sick on an otherwise eligible Believer",
        )
        page = bytes.fromhex(
            self.manifest["pe_append_transaction"]["layouts"]["collection_progression"]["append_bytes"]
        )
        heal = page[builder.OFF["heal"] : builder.OFF["heal"] + builder.SIZES["heal"]]
        # Clean single-pass heal (VV2/VV4-style): a count pass and a heal pass, each
        # re-reading the live record (no stale before/after snapshot). Both passes
        # apply the believer gate and refuse the unsupported sickness type 12.
        self.assertEqual(heal.count(bytes.fromhex("83BEFC1C00000C")), 2)  # cmp [esi+0x1CFC],12 x2
        self.assertEqual(heal.count(bytes.fromhex("80BEE11C000000")), 2)  # masked Heathen +0x1CE1 gate
        self.assertEqual(heal.count(bytes.fromhex("80BEEC1C000000")), 2)  # off-faction +0x1CEC gate
        self.assertEqual(heal.count(bytes.fromhex("C686481C000000")), 1)  # clear sickness +0x1C48
        self.assertIn(bytes.fromhex("FF0568D35100"), heal)               # bump People Cured stat 0x51D368
        # Native health writer 0x4758B0 (no raw health store), one per heal; three
        # cured-statistic writes 0x413450.
        sys.path.insert(0, str(ROOT / ".tools" / "capstone"))
        from capstone import CS_ARCH_X86, CS_MODE_32, Cs

        calls = [
            int(i.op_str, 16)
            for i in Cs(CS_ARCH_X86, CS_MODE_32).disasm(heal, 0x7C9000 + builder.OFF["heal"])
            if i.mnemonic == "call"
        ]
        self.assertEqual(calls.count(0x4758B0), 1)
        self.assertEqual(calls.count(0x413450), 3)

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
        for mode in MODES:
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
            "vv4": ROOT / "research/stock-executables/Virtual Villagers - The Tree of Life.exe",
            "vv5": ROOT / "research/stock-executables/Virtual Villagers - New Believers.exe",
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

    def test_public_final_layouts(self) -> None:
        build = next(item for item in patcher.load_builds() if item.id == "vv5")
        feature = next(
            item for item in patcher.load_fun_patches()
            if item.id == "vv5_enable_origins_exclusive_features"
        )
        source = ROOT / "research/stock-executables" / build.input_name
        expected = {
            "collection_progression": (0xFA000, 6, 0x3D1000),
            "immediate_fixed": (0xFA000, 6, 0x3D1000),
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

    def test_final_pe_cross_section_hooks_are_all_relocated_or_explicitly_preserved(self) -> None:
        build = next(item for item in patcher.load_builds() if item.id == "vv5")
        feature = next(
            item for item in patcher.load_fun_patches()
            if item.id == "vv5_enable_origins_exclusive_features"
        )
        source = ROOT / "research/stock-executables" / build.input_name
        for mode in MODES:
            rendered, applied = patcher.render_patched_bytes(
                source, build, mode, [feature.id]
            )
            post = [
                row for row in applied
                if row.get("relocation_status") == "task9_post_relocation_hook"
            ]
            self.assertEqual(len(post), 0)
            for raw_text, contract in builder.TASK9_CROSS_SECTION_HOOKS.items():
                raw = int(raw_text, 0)
                with self.subTest(mode=mode, hook=raw_text):
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
                                "stock_target"
                            ],
                            0,
                        ),
                    )

    @unittest.skip("Expanded-256 modes were removed from the public patcher.")
    def test_six_expanded_optional_statistics_compositions_keep_atomic_inner_writer(self) -> None:
        sources = {
            "vv3": ROOT / "research/stock-executables/Virtual Villagers - The Secret City.exe",
            "vv4": ROOT / "research/stock-executables/Virtual Villagers - The Tree of Life.exe",
            "vv5": ROOT / "research/stock-executables/Virtual Villagers - New Believers.exe",
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
