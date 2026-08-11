from __future__ import annotations

import hashlib
import importlib.util
import json
import struct
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402


SPEC = importlib.util.spec_from_file_location(
    "expanded_time_warp_builder", ROOT / "scripts/build_expanded_time_warp.py"
)
assert SPEC and SPEC.loader
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)

VV4_MANIFEST = ROOT / "data/vv4_expanded_time_warp.json"
VV4_MAP = ROOT / "data/candidates/vv4_expanded_time_warp_map.json"
VV5_MANIFEST = ROOT / "data/vv5_expanded_time_warp.json"
VV5_MAP = ROOT / "data/candidates/vv5_expanded_time_warp_map.json"
TASK9_MANIFEST = ROOT / "data/vv5_task9_native_actions.json"
TASK9_MAP = ROOT / "data/candidates/vv5_task9_native_actions_map.json"
COMPANION = ROOT / "data/candidates/VVFP VV5 Task9 Origins Icons.dll"
COMPANION_C = ROOT / "native/vv5_task9_origins/vv5_task9_origins.c"
MODES = (
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def rel32_calls(blob: bytes, blob_va: int, target: int) -> list[int]:
    offsets: list[int] = []
    for offset in range(len(blob) - 4):
        if blob[offset] != 0xE8:
            continue
        displacement = int.from_bytes(
            blob[offset + 1 : offset + 5], "little", signed=True
        )
        if blob_va + offset + 5 + displacement == target:
            offsets.append(offset)
    return offsets


def jump_target(blob: bytes, blob_va: int, opcode_offset: int) -> int:
    opcode = blob[opcode_offset]
    if opcode == 0xE9:
        operand_offset = opcode_offset + 1
        instruction_size = 5
    elif blob[opcode_offset : opcode_offset + 2] in (b"\x0F\x82", b"\x0F\x85"):
        operand_offset = opcode_offset + 2
        instruction_size = 6
    else:
        raise AssertionError(f"unsupported branch at {opcode_offset:#x}")
    displacement = int.from_bytes(
        blob[operand_offset : operand_offset + 4], "little", signed=True
    )
    return blob_va + opcode_offset + instruction_size + displacement


class ExpandedTimeWarpArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vv4 = json.loads(VV4_MANIFEST.read_text(encoding="utf-8"))
        cls.vv4_map = json.loads(VV4_MAP.read_text(encoding="utf-8"))
        cls.vv5 = json.loads(VV5_MANIFEST.read_text(encoding="utf-8"))
        cls.vv5_map = json.loads(VV5_MAP.read_text(encoding="utf-8"))
        cls.task9 = json.loads(TASK9_MANIFEST.read_text(encoding="utf-8"))
        cls.task9_map = json.loads(TASK9_MAP.read_text(encoding="utf-8"))

    def test_catalog_is_expanded_only_and_source_bound(self) -> None:
        catalog = {
            item.id: item
            for item in patcher.load_fun_patches(include_expanded_time_warp=True)
        }
        default_catalog_ids = {item.id for item in patcher.load_fun_patches()}
        for game_id, manifest in (("vv4", self.vv4), ("vv5", self.vv5)):
            with self.subTest(game=game_id):
                self.assertIn(manifest["id"], catalog)
                self.assertNotIn(manifest["id"], default_catalog_ids)
                self.assertFalse(manifest["catalog_enabled"])
                self.assertTrue(manifest["catalog_hidden"])
                self.assertEqual(manifest["supported_modes"], list(MODES))
                self.assertEqual(
                    manifest["rejected_modes"],
                    ["collection_progression", "immediate_fixed"],
                )
                self.assertEqual(manifest["patches"], [])
                for binding in manifest["source_bindings"].values():
                    self.assertEqual(
                        patcher.source_text_sha256(
                            (ROOT / binding["path"]).read_bytes()
                        ),
                        binding["source_text_sha256"],
                    )
        self.assertEqual(
            self.vv5["dependencies"], ["vv5_enable_origins_exclusive_features"]
        )
        self.assertEqual(
            self.vv4["conflicts"],
            [
                "vv4_enable_origins_exclusive_features",
                "vv4_enable_origins_exclusive_features_full_mastery_candidate",
                "vv4_full_mastery_all_stage_a_candidate",
            ],
        )

    def test_exact_shared_companion_and_owner_exports(self) -> None:
        self.assertEqual(COMPANION.stat().st_size, 297472)
        self.assertEqual(digest(COMPANION.read_bytes()), builder.COMPANION_SHA256)
        self.assertEqual(self.vv4["companion_files"], [builder.companion()])
        self.assertEqual(self.vv5["companion_contract"], builder.companion())
        self.assertNotIn("companion_files", self.vv5)
        native = COMPANION_C.read_text(encoding="utf-8")
        for export in ("BeginOriginsOwner", "GetOriginsOwner", "EndOriginsOwner"):
            self.assertIn(export, native)
        self.assertIn("validate_same_process_window(GetForegroundWindow())", native)
        self.assertIn("GetWindowThreadProcessId", native)
        self.assertIn("GetCurrentProcessId", native)
        self.assertNotIn("origins_owner = GetForegroundWindow", native)

    def test_vv4_exact_cave_hooks_fallback_ctor_and_transaction(self) -> None:
        payload, layout = builder.build_vv4_payload()
        patch_rows = self.vv4["patch_mode_overrides"][MODES[0]]
        self.assertEqual(len(payload), 0xC8D)
        self.assertEqual(bytes.fromhex(patch_rows[0]["after"]), payload)
        self.assertEqual(digest(payload), self.vv4_map["payload_sha256"])
        self.assertEqual(
            [(row["offset"], row["before"], row["after"]) for row in patch_rows[1:]],
            [
                ("0x3E165", "8BC68B4C244C", "E949B2040090"),
                ("0x3E9F0", "578BF9E828F00000", "E97EA90400909090"),
            ],
        )
        self.assertEqual(jump_target(bytes.fromhex(patch_rows[1]["after"]), 0x43E165, 0), 0x4893B3)
        self.assertEqual(jump_target(bytes.fromhex(patch_rows[2]["after"]), 0x43E9F0, 0), 0x489373)
        handler = payload[: layout["handler_length"]]
        self.assertIn(bytes.fromhex("5789CF"), handler)
        self.assertEqual(rel32_calls(handler, 0x489373, 0x44DA20), [0x1B])
        ctor = payload[0x40 : 0x40 + layout["constructor_length"]]
        self.assertIn(bytes.fromhex("89F08B4C244CE9"), ctor[-11:])
        self.assertEqual(jump_target(ctor, 0x4893B3, len(ctor) - 5), 0x43E16B)
        self.assertIn((0x3E00).to_bytes(4, "little"), payload[0x260:0xA00])
        self.assertEqual(rel32_calls(payload[0x260:0xA00], 0x4895D3, 0x41E300), [0x164])
        self.assertGreaterEqual(payload.count(b"BeginOriginsOwner\0"), 1)
        self.assertGreaterEqual(payload.count(b"GetOriginsOwner\0"), 1)
        self.assertGreaterEqual(payload.count(b"EndOriginsOwner\0"), 1)

    def test_vv5_stock_page_and_age_bytes_are_exactly_frozen(self) -> None:
        task9 = builder.load_task9_builder()
        stock, stock_map = task9.build_page(0x7C9000)
        expanded, expanded_map = task9.build_page(0x904000)
        self.assertEqual(digest(stock), "AB9C95497042A4846093DBA7D1A875D3BAA8963EF3E5C036FD2E746EA3B5785D")
        self.assertEqual(digest(expanded), "82FD9F2383D95E01B4165319347AC69A4FAE020A9D6E60BABCD5AAA28BA2E850")
        self.assertEqual(task9.SIZES["age"], 0x300)
        self.assertEqual(task9.OFF["time_warp"], 0x1000)
        self.assertEqual(task9.SIZES["time_warp"], 0x500)
        self.assertEqual(stock_map["routine_length"]["age"], 652)
        self.assertEqual(expanded_map["routine_length"]["age"], 652)
        manifest_stock = bytes.fromhex(
            self.task9["pe_append_transaction"]["layouts"]["collection_progression"]["append_bytes"]
        )
        self.assertEqual(manifest_stock, stock)
        self.assertFalse(any(stock[0x1000:0x1500]))

    def test_vv5_exact_dispatch_targets_and_row5_preservation(self) -> None:
        task9 = builder.load_task9_builder()
        base, _ = task9.build_page(0x904000)
        patches, layout = builder.build_vv5_overlay()
        self.assertEqual(
            [row["offset"] for row in patches],
            ["0xF4806", "0xF486B", "0xF5000", "0xFB09A"],
        )
        rendered = bytearray(base)
        for row in patches:
            offset = int(row["offset"], 0) - 0xF4000
            before = patcher._patch_bytes(row, "before")
            after = patcher._patch_bytes(row, "after")
            self.assertEqual(bytes(rendered[offset : offset + len(before)]), before)
            rendered[offset : offset + len(after)] = after
        self.assertEqual(bytes(rendered[0x806:0x810]), bytes.fromhex("B8001E0000E93F000000"))
        self.assertEqual(jump_target(rendered, 0x904000, 0x80B), 0x90484F)
        self.assertEqual(bytes(rendered[0x86B:0x874]), bytes.fromhex("83FB050F828C070000"))
        self.assertEqual(jump_target(rendered, 0x904000, 0x86E), 0x905000)
        dispatcher = bytes(rendered[0x1000:0x1500])
        self.assertEqual(dispatcher[:8], bytes.fromhex("85DB0F851CF9FFFF"))
        self.assertEqual(jump_target(dispatcher, 0x905000, 2), 0x904924)
        self.assertEqual(digest(bytes(rendered)), layout["expanded_time_warp_page_sha256"])
        owned = set(range(0x806, 0x810)) | set(range(0x86B, 0x874))
        owned |= set(range(0x1000, 0x1500))
        strings = int(layout["strings_offset"], 0)
        owned |= set(range(strings, strings + layout["strings_length"]))
        self.assertTrue(all(base[i] == rendered[i] for i in range(len(base)) if i not in owned))
        # The existing row-5 branch/call and Full Heal routine are not overlay-owned.
        self.assertEqual(base[0x874:0xA00], rendered[0x874:0xA00])
        self.assertEqual(base[0x3400:0x7000], rendered[0x3400:0x7000])

    def test_confirmation_cancel_pause_insufficient_and_recheck_precede_charge(self) -> None:
        vv4_payload, vv4_layout = builder.build_vv4_payload()
        vv4_tx = vv4_payload[0x260 : 0x260 + vv4_layout["transaction_length"]]
        vv5_patches, vv5_layout = builder.build_vv5_overlay()
        vv5_tx = bytes.fromhex(vv5_patches[2]["after"])[: vv5_layout["dispatcher_length"]]
        exact_warning = (
            b"This upgrade makes permanent changes to your village. "
            b"Are you sure you want to continue?\0"
        )
        for name, blob, va, writer, funds, clock in (
            ("vv4", vv4_tx, 0x4895D3, 0x41E300, 0x4D6F88, 0x4B8230),
            ("vv5", vv5_tx, 0x905000, 0x4237B0, 0x51D5F8, 0x4C6250),
        ):
            with self.subTest(game=name):
                calls = rel32_calls(blob, va, writer)
                self.assertEqual(len(calls), 1)
                charge = calls[0]
                self.assertLess(blob.find(bytes.fromhex("83F801")), charge)
                self.assertLess(blob.find((999).to_bytes(4, "little")), charge)
                self.assertLess(blob.find(funds.to_bytes(4, "little")), charge)
                self.assertGreater(blob.find(clock.to_bytes(4, "little"), charge), charge)
        self.assertIn(exact_warning, vv4_payload)
        vv5_strings = bytes.fromhex(vv5_patches[3]["after"])
        self.assertIn(exact_warning, vv5_strings)
        for strings in (vv4_payload, vv5_strings):
            self.assertIn(b"No tech points have been deducted.\0", strings)
            charge_message = strings[strings.find(b"charge outcome is unknown") - 32 :]
            self.assertNotIn(b"No tech points have been deducted", charge_message.split(b"\0", 1)[0])

    def test_exact_native_math_and_forbidden_record_fields(self) -> None:
        vv4_payload, vv4_layout = builder.build_vv4_payload()
        vv4_tx = vv4_payload[0x260 : 0x260 + vv4_layout["transaction_length"]]
        vv5_patches, vv5_layout = builder.build_vv5_overlay()
        vv5_tx = bytes.fromhex(vv5_patches[2]["after"])[: vv5_layout["dispatcher_length"]]
        self.assertEqual(rel32_calls(vv4_tx, 0x4895D3, 0x41FE70), [0x83, 0xEE])
        self.assertEqual(rel32_calls(vv4_tx, 0x4895D3, 0x41E300), [0x164])
        self.assertIn((0x17110).to_bytes(4, "little"), vv4_tx)
        self.assertIn((3600).to_bytes(4, "little"), vv4_tx)
        self.assertIn((0x4B8230).to_bytes(4, "little"), vv4_tx)
        self.assertEqual(rel32_calls(vv5_tx, 0x905000, 0x425950), [0x73, 0xDC])
        self.assertEqual(rel32_calls(vv5_tx, 0x905000, 0x4237B0), [0x14D])
        self.assertIn((0x17D7C).to_bytes(4, "little"), vv5_tx)
        self.assertIn((129600).to_bytes(4, "little"), vv5_tx)
        self.assertIn((0x4C6250).to_bytes(4, "little"), vv5_tx)
        for forbidden in (0x1CEC, 0x1CE1, 0x1CD4, 0x1C40):
            self.assertNotIn(forbidden.to_bytes(4, "little"), vv4_tx)
            self.assertNotIn(forbidden.to_bytes(4, "little"), vv5_tx)


class ExpandedTimeWarpRendererTests(unittest.TestCase):
    def render(self, game_id: str, mode: str, ids: list[str]) -> bytes:
        build = next(item for item in patcher.load_builds() if item.id == game_id)
        source = ROOT / "research/stock-executables" / build.input_name
        rendered, _ = patcher.render_patched_bytes(
            source, build, mode, fun_patch_ids=ids
        )
        return bytes(rendered)

    def test_stock_modes_are_exact_and_time_warp_selection_fails_closed(self) -> None:
        expected = {
            "vv4": {
                "collection_progression": "132516F4A5F7D2E9B539B14300207AEA5872FDCC0D34F13768435D9F4B6F76D4",
                "immediate_fixed": "EB0CDD4F7F5E41F7A03734D51F9417A126C3BE9D214B484A848DB688545CF5FB",
            },
            "vv5": {
                "collection_progression": "3540FA10994826A37205C6BF4F0CDC244B9E2AC5D99A5BFE54AF72B4B948D29A",
                "immediate_fixed": "08B81AFB590A0F7171CECECD66DD0A149115A4A383E8C5AA157343A7A242B7FF",
            },
        }
        for game_id in ("vv4", "vv5"):
            base_ids = [] if game_id == "vv4" else ["vv5_enable_origins_exclusive_features"]
            time_warp_ids = [*base_ids, patcher.EXPANDED_TIME_WARP_IDS[game_id]]
            for mode in ("collection_progression", "immediate_fixed"):
                with self.subTest(game=game_id, mode=mode):
                    self.assertEqual(digest(self.render(game_id, mode, base_ids)), expected[game_id][mode])
                    with self.assertRaisesRegex(patcher.PatcherError, "stock modes are byte-frozen"):
                        self.render(game_id, mode, time_warp_ids)

    def test_vv4_full_origins_conflict_and_vv5_dependency_are_fail_closed(self) -> None:
        vv4_ids = [
            "vv4_expanded_256_time_warp",
            "vv4_enable_origins_exclusive_features",
            "vv4_full_mastery_all_stage_a_candidate",
        ]
        with self.assertRaisesRegex(patcher.PatcherError, "conflicts with full Origins"):
            self.render("vv4", MODES[0], vv4_ids)
        with self.assertRaisesRegex(patcher.PatcherError, "requires prerequisite"):
            self.render("vv5", MODES[0], ["vv5_expanded_256_time_warp"])

    def test_all_four_expanded_renders_have_only_owned_time_warp_deltas(self) -> None:
        expected = {
            ("vv4", MODES[0]): "A9008B5135CF36BEC9792FB5A5E67986FD619396B522DDC89C104E16CF0C0C8A",
            ("vv4", MODES[1]): "B7E46D20596C6B335372FCAEF202BA7A25D7816A11078F4F0C27A308740A6622",
            ("vv5", MODES[0]): "65D81A31B9BA44AFA8E69E0A0B787ED680DFB0FC832B66FA8D11C899D2B80A5D",
            ("vv5", MODES[1]): "B6AD620FA4B1D339B18130BA737EDC17CB0C40E326D0D461AA43166B79ABAA88",
        }
        vv5_string_row = json.loads(VV5_MANIFEST.read_text(encoding="utf-8"))["patch_mode_overrides"][MODES[0]][3]
        for game_id in ("vv4", "vv5"):
            parent_ids = [] if game_id == "vv4" else ["vv5_enable_origins_exclusive_features"]
            installed_ids = [*parent_ids, patcher.EXPANDED_TIME_WARP_IDS[game_id]]
            for mode in MODES:
                with self.subTest(game=game_id, mode=mode):
                    parent = self.render(game_id, mode, parent_ids)
                    installed = self.render(game_id, mode, installed_ids)
                    self.assertEqual(digest(installed), expected[(game_id, mode)])
                    checksum, _ = patcher._pe_checksum_layout(installed)
                    allowed = set(range(checksum, checksum + 4))
                    if game_id == "vv4":
                        allowed |= set(range(0x89373, 0x8A000))
                        allowed |= set(range(0x3E165, 0x3E16B))
                        allowed |= set(range(0x3E9F0, 0x3E9F8))
                    else:
                        allowed |= set(range(0xF4806, 0xF4810))
                        allowed |= set(range(0xF486B, 0xF4874))
                        allowed |= set(range(0xF5000, 0xF5500))
                        string_start = int(vv5_string_row["offset"], 0)
                        allowed |= set(range(string_start, string_start + vv5_string_row["length"]))
                    changed = {
                        index
                        for index, (before, after) in enumerate(zip(parent, installed))
                        if before != after
                    }
                    self.assertTrue(changed)
                    self.assertTrue(changed <= allowed)
                    pe = struct.unpack_from("<I", installed, 0x3C)[0]
                    self.assertEqual(
                        struct.unpack_from("<H", installed, pe + 6)[0],
                        struct.unpack_from("<H", parent, pe + 6)[0],
                    )
                    self.assertEqual(
                        struct.unpack_from("<I", installed, pe + 24 + 56)[0],
                        struct.unpack_from("<I", parent, pe + 24 + 56)[0],
                    )
                    if game_id == "vv5":
                        self.assertEqual(installed[0xDB000:0xF4000], parent[0xDB000:0xF4000])

    def test_exact_feature_removal_restores_each_expanded_parent(self) -> None:
        for game_id in ("vv4", "vv5"):
            parent_ids = [] if game_id == "vv4" else ["vv5_enable_origins_exclusive_features"]
            feature = patcher.get_fun_patch(patcher.EXPANDED_TIME_WARP_IDS[game_id])
            for mode in MODES:
                with self.subTest(game=game_id, mode=mode):
                    parent = self.render(game_id, mode, parent_ids)
                    installed = bytearray(
                        self.render(game_id, mode, [*parent_ids, feature.id])
                    )
                    removed = patcher._remove_feature_bytes(
                        installed, feature, mode, output_folder=None
                    )
                    self.assertEqual(bytes(installed), parent)
                    self.assertEqual(
                        {row["owner"] for row in removed}, {f"feature:{feature.id}"}
                    )


if __name__ == "__main__":
    unittest.main()
