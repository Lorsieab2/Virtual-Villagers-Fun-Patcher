from __future__ import annotations

import hashlib
import importlib.util
import json
import struct
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_fun_patcher as patcher  # noqa: E402


SPEC = importlib.util.spec_from_file_location(
    "vv3_expanded_time_warp_builder",
    ROOT / "scripts/build_vv3_expanded_time_warp.py",
)
assert SPEC and SPEC.loader
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)

MANIFEST_PATH = ROOT / "data/vv3_expanded_time_warp.json"
MAP_PATH = ROOT / "data/candidates/vv3_expanded_time_warp_map.json"
CORE_PATH = ROOT / "data/vv3_expanded_time_warp_core.json"
COMPANION = ROOT / "data/candidates/VVFP VV5 Task9 Origins Icons.dll"
MODES = (
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def rel32_calls(blob: bytes, blob_va: int, target: int) -> list[int]:
    found: list[int] = []
    for offset in range(len(blob) - 4):
        if blob[offset] != 0xE8:
            continue
        displacement = int.from_bytes(
            blob[offset + 1 : offset + 5], "little", signed=True
        )
        if blob_va + offset + 5 + displacement == target:
            found.append(offset)
    return found


def jump_target(blob: bytes, blob_va: int, offset: int) -> int:
    if blob[offset] != 0xE9:
        raise AssertionError(f"not a rel32 jump at {offset:#x}")
    displacement = int.from_bytes(blob[offset + 1 : offset + 5], "little", signed=True)
    return blob_va + offset + 5 + displacement


class VV3ExpandedTimeWarpArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.artifact = json.loads(MAP_PATH.read_text(encoding="utf-8"))
        cls.core = json.loads(CORE_PATH.read_text(encoding="utf-8"))
        cls.page, cls.layout = builder.build_page()

    def test_catalog_is_hidden_explicit_expanded_only_and_source_bound(self) -> None:
        catalog = {
            item.id: item
            for item in patcher.load_fun_patches(include_expanded_time_warp=True)
        }
        self.assertIn(builder.FEATURE_ID, catalog)
        self.assertNotIn(builder.FEATURE_ID, {item.id for item in patcher.load_fun_patches()})
        self.assertTrue(self.manifest["enabled"])
        self.assertTrue(self.manifest["catalog_hidden"])
        self.assertFalse(self.manifest["catalog_enabled"])
        self.assertTrue(self.manifest["experimental_explicit_selection"])
        self.assertEqual(self.manifest["supported_modes"], list(MODES))
        self.assertEqual(
            self.manifest["rejected_modes"],
            ["collection_progression", "immediate_fixed"],
        )
        for binding in self.manifest["source_bindings"].values():
            self.assertEqual(
                patcher.source_text_sha256((ROOT / binding["path"]).read_bytes()),
                binding["source_text_sha256"],
            )

    def test_companion_owner_contract_is_exact(self) -> None:
        self.assertEqual(COMPANION.stat().st_size, builder.COMPANION_SIZE)
        self.assertEqual(digest(COMPANION.read_bytes()), builder.COMPANION_SHA256)
        self.assertEqual(self.manifest["companion_files"], [builder.companion()])
        native = (ROOT / "native/vv5_task9_origins/vv5_task9_origins.c").read_text(
            encoding="utf-8"
        )
        for export in ("BeginOriginsOwner", "GetOriginsOwner", "EndOriginsOwner"):
            self.assertIn(export, native)
        for api in ("GetForegroundWindow", "GetWindowThreadProcessId", "GetCurrentProcessId", "IsWindow"):
            self.assertIn(api, native)

    def test_exact_isolated_page_header_hooks_and_no_rdata_execute_change(self) -> None:
        self.assertEqual(len(self.page), 0x1000)
        self.assertEqual(digest(self.page), self.layout["page_sha256"])
        self.assertEqual(self.artifact["section_header_raw"], "0x2C8")
        self.assertEqual(bytes.fromhex(self.artifact["section_header"]), builder.HEADER)
        self.assertEqual(len(builder.HEADER), 40)
        self.assertEqual(builder.HEADER[-4:], bytes.fromhex("20000060"))
        self.assertEqual(
            [(row["offset"], row["before"], row["after"]) for row in self.artifact["hooks"]],
            [
                ("0x6547D", "8B4C243C5F", "E9FE2B3500"),
                ("0x65640", "6AFF64A100000000", "E9FB293500909090"),
            ],
        )
        self.assertEqual(jump_target(bytes.fromhex("E9FE2B3500"), 0x46547D, 0), 0x7B8080)
        self.assertEqual(jump_target(bytes.fromhex("E9FB293500909090"), 0x465640, 0), 0x7B8040)
        transaction = self.manifest["pe_append_transaction"]["layouts"][MODES[0]]
        self.assertEqual(transaction["append_offset"], "0xCB000")
        self.assertEqual(transaction["virtual_address"], "0x7B8000")
        self.assertEqual(
            transaction["header_patches"],
            self.manifest["pe_append_transaction"]["layouts"][MODES[1]]["header_patches"],
        )

    def test_handler_only_claims_message8_event15_and_fallback_is_exact(self) -> None:
        routine = self.layout["routines"]["handler"]
        start = int(routine["offset"], 0)
        handler = self.page[start : start + routine["length"]]
        self.assertEqual(handler[:14], bytes.fromhex("837C2404087511837C24080F750A"))
        fallback = bytes.fromhex("6AFF64A100000000")
        self.assertIn(fallback, handler)
        fallback_at = handler.index(fallback)
        self.assertEqual(jump_target(handler, builder.HANDLER, fallback_at + len(fallback)), 0x465648)
        self.assertEqual(rel32_calls(handler, builder.HANDLER, builder.TRANSACTION), [0xE])

    def test_constructor_uses_exact_current_epilogue(self) -> None:
        routine = self.layout["routines"]["constructor"]
        start = int(routine["offset"], 0)
        constructor = self.page[start : start + routine["length"]]
        epilogue = bytes.fromhex(
            "8B4C243C5F89F05E5D5B64890D0000000083C438C3"
        )
        self.assertTrue(constructor.endswith(epilogue))
        self.assertEqual(rel32_calls(constructor, builder.CONSTRUCTOR, 0x46EC93), [0x2])
        self.assertEqual(rel32_calls(constructor, builder.CONSTRUCTOR, 0x42E9D0), [0x10])
        self.assertEqual(rel32_calls(constructor, builder.CONSTRUCTOR, 0x4019F0), [0x30])
        self.assertEqual(rel32_calls(constructor, builder.CONSTRUCTOR, 0x40C1F0), [0x57])

    def test_transaction_abi_order_math_and_direct_charge_are_exact(self) -> None:
        routine = self.layout["routines"]["transaction"]
        start = int(routine["offset"], 0)
        tx = self.page[start : start + routine["length"]]
        self.assertEqual(rel32_calls(tx, builder.TRANSACTION, 0x428B60), [0x81, 0x105])
        self.assertEqual(rel32_calls(tx, builder.TRANSACTION, 0x403530), [])
        self.assertEqual(rel32_calls(tx, builder.TRANSACTION, 0x41E300), [])
        self.assertEqual(tx.count(bytes.fromhex("813D3A88420000010000")), 2)
        self.assertNotIn(bytes.fromhex("833D3A88420064"), tx)
        self.assertEqual(tx.count((0x7598).to_bytes(4, "little")), 2)
        self.assertEqual(tx.count((0x12F20).to_bytes(4, "little")), 2)
        self.assertIn((999).to_bytes(4, "little"), tx)
        self.assertIn((3600).to_bytes(4, "little"), tx)
        self.assertIn(bytes.fromhex("812D4426580050C30000"), tx)
        charge = tx.index(bytes.fromhex("812D4426580050C30000"))
        confirmation = tx.index(bytes.fromhex("83F801"))
        fresh_getter = rel32_calls(tx, builder.TRANSACTION, 0x428B60)[1]
        clock_write = tx.index(bytes.fromhex("290510424A00"))
        self.assertLess(confirmation, fresh_getter)
        self.assertLess(fresh_getter, charge)
        self.assertLess(charge, clock_write)
        self.assertEqual(tx.count(bytes.fromhex("812D4426580050C30000")), 1)
        for marker in (b"BeginOriginsOwner\0", b"GetOriginsOwner\0", b"EndOriginsOwner\0"):
            self.assertIn(marker, self.page)
        self.assertIn((0x3E00).to_bytes(4, "little"), tx)
        self.assertIn(
            b"This upgrade makes permanent changes to your village. Are you sure you want to continue?\0",
            self.page,
        )

    def test_static_and_atomic_pages_retain_exact_certified_bytes(self) -> None:
        for mode in MODES:
            parent = builder.expanded_parent(mode)
            time_warp = builder.install_time_warp(parent, self.page)
            static = builder.install_static(time_warp)
            self.assertEqual(digest(static[0xCC000:0xCD000]), builder.STATIC_PAGE_SHA256)
            atomic, metadata = builder.install_atomic(static)
            self.assertEqual(
                digest(atomic[0xCC400 : 0xCC400 + metadata["writer_length"]]),
                builder.ATOMIC_WRITER_SHA256,
            )
            self.assertEqual(digest(atomic[0xCD000:0xCE000]), builder.ATOMIC_IMPORT_SHA256)
            self.assertEqual(atomic[0x10E:0x110], bytes.fromhex("0800"))
            self.assertEqual(atomic[0x158:0x15C], bytes.fromhex("00B03B00"))

    def test_deterministic_regeneration_check(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts/build_vv3_expanded_time_warp.py"), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


class VV3ExpandedTimeWarpRendererTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.core = json.loads(CORE_PATH.read_text(encoding="utf-8"))
        cls.build = next(item for item in patcher.load_builds() if item.id == "vv3")
        cls.source = ROOT / "research/stock-executables" / cls.build.input_name

    def render(self, mode: str, ids: list[str]) -> bytes:
        data, _ = patcher.render_patched_bytes(
            self.source, self.build, mode, fun_patch_ids=ids
        )
        return bytes(data)

    def test_stock_outputs_are_frozen_and_selection_fails_closed(self) -> None:
        expected = {
            "collection_progression": "D83FF587DB844C29515ECEDAE0E8C390038BA44854A4DF83DE16F3186F0AD27F",
            "immediate_fixed": "BB87E3ECFACCB1290860028FFC9444B8D15AF19392FE8D1448FDC6FC672378C1",
        }
        for mode, wanted in expected.items():
            with self.subTest(mode=mode):
                self.assertEqual(digest(self.render(mode, [])), wanted)
                with self.assertRaisesRegex(patcher.PatcherError, "stock modes are byte-frozen"):
                    self.render(mode, [builder.FEATURE_ID])

    def test_both_expanded_identity_chains_and_statistics_composition_are_exact(self) -> None:
        for mode in MODES:
            chain = self.core["modes"][mode]
            parent = self.render(mode, [])
            installed = self.render(mode, [builder.FEATURE_ID])
            statistics = self.render(
                mode, [builder.FEATURE_ID, "vv3_write_village_statistics"]
            )
            parent_before_healer_repair = bytearray(parent)
            parent_before_healer_repair[0x5FA46:0x5FA4A] = bytes.fromhex(
                patcher.VV3_EXPANDED_HEALER_ENDPOINT_REPAIR["before"]
            )
            patcher._canonicalize_pe_checksum(parent_before_healer_repair)
            self.assertEqual(
                digest(parent_before_healer_repair),
                chain["expanded_parent"]["sha256"],
            )
            repaired = patcher.VV3_EXPANDED_HEALER_TIME_WARP_RESULTS[mode]
            self.assertEqual(digest(installed), repaired["atomic_result"]["sha256"])
            self.assertEqual(
                digest(statistics), repaired["statistics_result"]["sha256"]
            )
            self.assertEqual(len(installed), 0xCE000)
            self.assertEqual(installed[0x2C8:0x2F0], builder.HEADER)
            self.assertEqual(installed[0x2F0:0x318], bytes.fromhex("2E767633737600000010000000903B000010000000C00C0000000000000000000000000020000060"))
            self.assertEqual(installed[0x318:0x340], bytes.fromhex("2E767633690000000010000000A03B000010000000D00C00000000000000000000000000400000C0"))
            self.assertEqual(installed[0xA3180:0xA4000], parent[0xA3180:0xA4000])
            self.assertEqual(installed[0x24C:0x250], parent[0x24C:0x250])
            checksum_raw, _ = patcher._pe_checksum_layout(installed)
            self.assertEqual(
                installed[checksum_raw : checksum_raw + 4].hex().upper(),
                repaired["atomic_result"]["checksum"],
            )

    def test_origins_running_profile_is_mutually_exclusive(self) -> None:
        ids = [
            builder.FEATURE_ID,
            "vv3_enable_origins_exclusive_features",
        ]
        with self.assertRaisesRegex(patcher.PatcherError, "conflicts with the Origins/Running core"):
            self.render(MODES[0], ids)


if __name__ == "__main__":
    unittest.main()
