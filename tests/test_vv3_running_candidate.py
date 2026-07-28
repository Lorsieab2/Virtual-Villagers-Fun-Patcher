from __future__ import annotations

import hashlib
import itertools
import json
import struct
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    FunPatch,
    PatcherError,
    _pe_checksum_layout,
    _remove_feature_bytes,
    _remove_feature_with_dependency_guard,
    validate_fun_patch_catalog,
    load_builds,
    load_fun_patches,
    pe_checksum,
    render_patched_bytes,
)


PYTHON = Path(sys.executable)
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
BASE_PATH = ROOT / "data" / "candidates" / "vv3_origins_running_base_candidate.json"
RUNNING_PATH = ROOT / "data" / "candidates" / "vv3_all_villagers_like_running_candidate.json"
MAP_PATH = ROOT / "data" / "candidates" / "vv3_running_candidate_map.json"
DOC_PATH = ROOT / "docs" / "vv3-running-stage-a-candidate.md"
GENERATOR = ROOT / "scripts" / "build_vv3_running_candidate.py"
DLL = ROOT / "assets" / "origins" / "VVFP Origins Icons.dll"
MODES = (
    "collection_progression",
    "immediate_fixed",
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
)


def mutate_record(
    likes: tuple[int, int, int],
    dislikes: tuple[int, int, int],
    *,
    commit: bool,
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, int, int, int]]:
    out_likes = list(likes)
    out_dislikes = list(dislikes)
    if 38 in likes:
        return tuple(out_likes), tuple(out_dislikes), (0, 1, 0, 0)
    try:
        empty = out_likes.index(-1)
    except ValueError:
        return tuple(out_likes), tuple(out_dislikes), (0, 0, 1, 0)
    removed = int(38 in out_dislikes)
    if commit:
        out_dislikes = [-1 if item == 38 else item for item in out_dislikes]
        out_likes[empty] = 38
    return tuple(out_likes), tuple(out_dislikes), (1, 0, 0, removed)


def canonical_sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
    ).hexdigest().upper()


class VV3RunningCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base_raw = json.loads(BASE_PATH.read_text(encoding="utf-8"))
        cls.running_raw = json.loads(RUNNING_PATH.read_text(encoding="utf-8"))
        cls.artifact_map = json.loads(MAP_PATH.read_text(encoding="utf-8"))
        cls.base = FunPatch(cls.base_raw)
        cls.running = FunPatch(cls.running_raw)
        cls.build = next(item for item in load_builds() if item.id == "vv3")

    def test_candidate_is_disabled_and_absent_from_active_catalog(self) -> None:
        self.assertFalse(self.base_raw["enabled"])
        self.assertFalse(self.running_raw["enabled"])
        active = {item.id for item in load_fun_patches()}
        self.assertNotIn(self.base.id, active)
        self.assertNotIn(self.running.id, active)
        self.assertNotIn("vv3_origins_village_wide_upgrades", active)
        validate_fun_patch_catalog([self.base, self.running])

    def test_current_handler_constructor_and_other_runtime_projections_are_frozen(self) -> None:
        stock_payload = bytes.fromhex(
            next(
                item["after"]
                for item in self.base_raw["patches"]
                if int(item["offset"], 0) == 0xA3180
            )
        )
        self.assertEqual(
            hashlib.sha256(stock_payload[:37]).hexdigest().upper(),
            "65B28B7DBCBDAFABDE8C1C55A48266CE3DCB62CAC4DBF958BB92E8272661B219",
        )
        self.assertEqual(
            hashlib.sha256(stock_payload[0x40:0x40 + 113]).hexdigest().upper(),
            "869AF96EAE3EC16294D5ABE566F74907E589C99B7FB571BA822610B71B99E636",
        )
        for game in range(1, 6):
            manifest = json.loads(
                (ROOT / "data" / f"vv{game}_origins_feature.json").read_text(
                    encoding="utf-8"
                )
            )
            projection = {
                key: manifest.get(key)
                for key in (
                    "patches",
                    "patch_mode_overrides",
                    "expanded_shr_relocations",
                    "dependencies",
                )
            }
            self.assertEqual(
                canonical_sha(projection),
                self.artifact_map["active_runtime_projection"][
                    f"vv{game}_origins_feature.json"
                ],
            )

    def test_generator_is_deterministic(self) -> None:
        before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (BASE_PATH, RUNNING_PATH, MAP_PATH, DOC_PATH)
        }
        subprocess.run([str(PYTHON), str(GENERATOR)], cwd=ROOT, check=True)
        after = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (BASE_PATH, RUNNING_PATH, MAP_PATH, DOC_PATH)
        }
        self.assertEqual(before, after)

    def test_exact_slot_layout_and_artifact_hashes(self) -> None:
        item = self.running_raw["patches"][0]
        self.assertEqual(int(item["offset"], 0), 0xCB100)
        before = bytes.fromhex(item["before"])
        after = bytes.fromhex(item["after"])
        self.assertEqual(len(before), 0x700)
        self.assertEqual(len(after), 0x700)
        self.assertEqual(before[:8], b"VVRNSLT\0")
        self.assertEqual(after[:8], b"VVRNSLT\0")
        self.assertEqual(struct.unpack_from("<I", before, 12)[0], 0)
        self.assertEqual(struct.unpack_from("<I", after, 12)[0], 1)
        self.assertEqual(
            hashlib.sha256(before).hexdigest().upper(),
            self.artifact_map["noop_slot_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(after).hexdigest().upper(),
            self.artifact_map["running_slot_sha256"],
        )
        self.assertEqual(self.artifact_map["running"]["entry_offset"], 0x20)
        self.assertEqual(self.artifact_map["running"]["walker_offset"], 0x240)

    def test_companion_has_five_argument_export_and_256_byte_contract(self) -> None:
        companion = self.artifact_map["companion"]
        self.assertEqual(companion["sha256"], hashlib.sha256(DLL.read_bytes()).hexdigest().upper())
        export = companion["exports"]["ShowOriginsVillageWideResult@20"]
        self.assertEqual(export, {"ordinal": 4, "rva": 0x11B0})
        self.assertEqual(companion["result_buffer_bytes"], 256)
        dll = DLL.read_bytes()
        pe = struct.unpack_from("<I", dll, 0x3C)[0]
        coff = pe + 4
        count = struct.unpack_from("<H", dll, coff + 2)[0]
        optional_size = struct.unpack_from("<H", dll, coff + 16)[0]
        table = coff + 20 + optional_size
        function_offset = None
        for index in range(count):
            section = table + index * 40
            virtual_size, rva, raw_size, raw_offset = struct.unpack_from(
                "<IIII", dll, section + 8
            )
            if rva <= export["rva"] < rva + max(virtual_size, raw_size):
                function_offset = raw_offset + export["rva"] - rva
                break
        self.assertIsNotNone(function_offset)
        self.assertIn(bytes.fromhex("C21400"), dll[function_offset:function_offset + 0x100])
        source = (ROOT / "native" / "vv1_origins_icons" / "vv1_origins_icons.c").read_text()
        self.assertIn("char message[256];", source)
        for exact in (
            "Granted Running to %u villagers",
            "Skipped over %u villagers. Reason: already likes running",
            "Skipped over %u villagers. Reason: all like slots are occupied",
            "Removed running dislike from %u villagers",
        ):
            self.assertIn(exact, source)

    def test_exhaustive_three_by_three_atomic_vectors(self) -> None:
        values = (-1, 7, 38)
        for likes in itertools.product(values, repeat=3):
            for dislikes in itertools.product(values, repeat=3):
                with self.subTest(likes=likes, dislikes=dislikes):
                    dry_likes, dry_dislikes, dry_counts = mutate_record(
                        likes, dislikes, commit=False
                    )
                    committed_likes, committed_dislikes, commit_counts = mutate_record(
                        likes, dislikes, commit=True
                    )
                    self.assertEqual(dry_likes, likes)
                    self.assertEqual(dry_dislikes, dislikes)
                    self.assertEqual(dry_counts, commit_counts)
                    if 38 in likes:
                        self.assertEqual(committed_likes, likes)
                        self.assertEqual(committed_dislikes, dislikes)
                    elif -1 not in likes:
                        self.assertEqual(committed_likes, likes)
                        self.assertEqual(committed_dislikes, dislikes)
                    else:
                        self.assertEqual(committed_likes.count(38), likes.count(38) + 1)
                        self.assertNotIn(38, committed_dislikes)
                        for index, value in enumerate(dislikes):
                            if value != 38:
                                self.assertEqual(committed_dislikes[index], value)

    def test_purchase_remove_repurchase_model(self) -> None:
        def transact(owner: bool, balance: int, granted: int) -> tuple[bool, int, str]:
            if owner:
                return False, balance, "removed"
            if granted == 0:
                return False, balance, "no_change"
            if balance < 1_000_000:
                return False, balance, "insufficient"
            return True, balance - 1_000_000, "purchased"

        self.assertEqual(transact(False, 999_999, 1), (False, 999_999, "insufficient"))
        self.assertEqual(transact(False, 2_000_000, 0), (False, 2_000_000, "no_change"))
        self.assertEqual(transact(False, 2_000_000, 1), (True, 1_000_000, "purchased"))
        self.assertEqual(transact(True, 1_000_000, 0), (False, 1_000_000, "removed"))
        self.assertEqual(transact(False, 1_000_000, 1), (True, 0, "purchased"))

    def test_candidate_renders_stock_and_both_expanded_layouts(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                rendered, applied = render_patched_bytes(
                    STOCK,
                    self.build,
                    mode,
                    _fun_patches_override=[self.base, self.running],
                )
                self.assertEqual(len(rendered), 0xCC000)
                self.assertEqual(struct.unpack_from("<H", rendered, 0x10E)[0], 6)
                expected_rva = (
                    0x3B8000 if mode.startswith("experimental_expanded_256") else 0x2DF000
                )
                self.assertEqual(struct.unpack_from("<I", rendered, 0x2D4)[0], expected_rva)
                self.assertEqual(bytes(rendered[0xCB100:0xCB800]), bytes.fromhex(
                    self.running_raw["patches"][0]["after"]
                ))
                checksum_offset, _ = _pe_checksum_layout(rendered)
                stored = struct.unpack_from("<I", rendered, checksum_offset)[0]
                copy = bytearray(rendered)
                struct.pack_into("<I", copy, checksum_offset, 0)
                self.assertEqual(stored, pe_checksum(copy))
                owners = {item["owner"] for item in applied}
                self.assertIn(f"feature:{self.base.id}", owners)
                self.assertIn(f"feature:{self.running.id}", owners)

    def test_candidate_composes_with_every_other_current_vv3_patch(self) -> None:
        others = [
            item
            for item in load_fun_patches()
            if item.game_id == "vv3"
            and item.id != "vv3_enable_origins_exclusive_features"
        ]
        for mode in MODES:
            with self.subTest(mode=mode):
                rendered, _ = render_patched_bytes(
                    STOCK,
                    self.build,
                    mode,
                    _fun_patches_override=[self.base, self.running, *others],
                )
                self.assertEqual(len(rendered), 0xCC000)

    def test_remove_slot_then_base_exact_roundtrip_and_dependency_block(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                baseline, _ = render_patched_bytes(STOCK, self.build, mode)
                rendered, _ = render_patched_bytes(
                    STOCK,
                    self.build,
                    mode,
                    _fun_patches_override=[self.base, self.running],
                )
                with self.assertRaisesRegex(PatcherError, "dependent optional patch"):
                    _remove_feature_with_dependency_guard(
                        bytearray(rendered), self.base, [self.base, self.running], mode
                    )
                work = bytearray(rendered)
                _remove_feature_bytes(work, self.running, mode)
                self.assertEqual(
                    bytes(work[0xCB100:0xCB800]),
                    bytes.fromhex(self.running_raw["patches"][0]["before"]),
                )
                _remove_feature_with_dependency_guard(work, self.base, [self.base], mode)
                self.assertEqual(bytes(work), bytes(baseline))

    def test_corrupt_slot_refuses_running_and_base_removal(self) -> None:
        rendered, _ = render_patched_bytes(
            STOCK,
            self.build,
            "collection_progression",
            _fun_patches_override=[self.base, self.running],
        )
        rendered[0xCB123] ^= 1
        with self.assertRaisesRegex(PatcherError, "Removal guard"):
            _remove_feature_bytes(rendered, self.running, "collection_progression")

    def test_commands_seven_and_eight_are_not_in_candidate_dispatch(self) -> None:
        stock_payload = bytes.fromhex(
            next(
                item["after"]
                for item in self.base_raw["patches"]
                if int(item["offset"], 0) == 0xA3180
            )
        )
        tech = stock_payload[0x340:0x650]
        self.assertNotIn(bytes.fromhex("83FB07"), tech)
        self.assertNotIn(bytes.fromhex("83FB08"), tech)
        self.assertNotIn(b"Grant Full Mastery to All Villagers", tech)
        self.assertNotIn(b"All Villagers are 18", tech)


if __name__ == "__main__":
    unittest.main()
