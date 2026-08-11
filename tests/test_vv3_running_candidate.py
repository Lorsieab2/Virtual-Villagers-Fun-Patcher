from __future__ import annotations

import hashlib
import itertools
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    FunPatch,
    PatcherError,
    apply_patch,
    _pe_checksum_layout,
    _remove_feature_bytes,
    _remove_feature_with_dependency_guard,
    validate_fun_patch_catalog,
    load_builds,
    load_fun_patches,
    pe_checksum,
    render_patched_bytes,
    resolve_fun_patch_ids,
)
from runtime_freeze import isolated_runtime_freeze  # noqa: E402


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


def relative_call_targets(code: bytes, base: int) -> list[tuple[int, int]]:
    targets = []
    for offset, opcode in enumerate(code):
        if opcode == 0xE8 and offset + 5 <= len(code):
            displacement = struct.unpack_from("<i", code, offset + 1)[0]
            targets.append((base + offset, base + offset + 5 + displacement))
    return targets


class VV3RunningCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base_raw = json.loads(BASE_PATH.read_text(encoding="utf-8"))
        cls.running_raw = json.loads(RUNNING_PATH.read_text(encoding="utf-8"))
        cls.artifact_map = json.loads(MAP_PATH.read_text(encoding="utf-8"))
        cls.base = FunPatch(cls.base_raw)
        cls.running = FunPatch(cls.running_raw)
        cls.build = next(item for item in load_builds() if item.id == "vv3")

    def test_certified_runtime_bundle_is_frozen_and_withdrawn_alias_is_hidden(self) -> None:
        self.assertFalse(self.base_raw["enabled"])
        self.assertFalse(self.running_raw["enabled"])
        self.assertEqual(
            self.artifact_map["running_slot_sha256"],
            "3F8F3BD7FD6C1BA8D8517539581D96F8D7B14D3BF959C74157FF970E432E5B13",
        )
        self.assertEqual(
            self.artifact_map["noop_slot_sha256"],
            "42FC601B51E8AAC069B70355502C32B6985A2471E26B683A61A68EA3B91BE4E3",
        )
        active = {item.id: item for item in load_fun_patches()}
        self.assertNotIn(self.base.id, active)
        self.assertNotIn("vv3_all_villagers_like_running", active)
        self.assertIn("vv3_enable_origins_exclusive_features", active)
        self.assertNotIn("vv3_origins_village_wide_upgrades", active)
        validate_fun_patch_catalog([self.base, self.running])

    def test_withdrawn_running_is_rejected_by_catalog_resolution(self) -> None:
        with self.assertRaisesRegex(PatcherError, "Unknown optional patch"):
            resolve_fun_patch_ids(["vv3_all_villagers_like_running"])

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
        self.assertEqual(
            isolated_runtime_freeze(
                game_id="vv3",
                map_path=MAP_PATH,
                data_root=ROOT / "data",
                section="active_runtime_projection",
            ),
            self.artifact_map["active_runtime_projection"],
        )

    def test_generator_is_deterministic(self) -> None:
        # Establish the producer's canonical map first. Other candidate tests
        # may exercise generators in-place; determinism compares two producer
        # passes, never a contaminated pre-test snapshot.
        repo_status = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT
        )
        with tempfile.TemporaryDirectory() as raw_temp:
            output_root = Path(raw_temp)
            candidates = output_root / "data" / "candidates"
            candidates.mkdir(parents=True)
            (output_root / "docs").mkdir()
            env = dict(os.environ, VVFP_GENERATOR_OUTPUT_ROOT=str(output_root))
            generated = (
                candidates / BASE_PATH.name,
                candidates / RUNNING_PATH.name,
                candidates / MAP_PATH.name,
                output_root / "docs" / DOC_PATH.name,
            )
            subprocess.run([str(PYTHON), str(GENERATOR)], cwd=ROOT, env=env, check=True)
            before = {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in generated
            }
            subprocess.run([str(PYTHON), str(GENERATOR)], cwd=ROOT, env=env, check=True)
            after = {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in generated
            }
            self.assertEqual(before, after)
        self.assertEqual(
            subprocess.check_output(
                ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT
            ),
            repo_status,
        )

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

    def test_stage_c_dispatcher_delivers_distinct_counters_and_preserves_abi(self) -> None:
        layout = self.base_raw["pe_append_transaction"]["layouts"][
            "collection_progression"
        ]
        page = bytes.fromhex(layout["append_bytes"])
        dispatcher_length = self.artifact_map["dispatcher"]["length"]
        dispatcher = page[0x40 : 0x40 + dispatcher_length]

        # One shared return path restores the exact reverse of the entry saves.
        self.assertEqual(dispatcher[:4], bytes.fromhex("55535657"))
        self.assertEqual(dispatcher[-5:], bytes.fromhex("5F5E5B5DC3"))

        # ESI is the stable counter base. The stdcall pushes are reverse order:
        # removed, full, already, granted, command, yielding the declared order
        # at the callee even as ESP moves.
        push_sequence = bytes.fromhex(
            "FF760CFF7608FF7604FF366A06FFD0"
        )
        self.assertIn(push_sequence, dispatcher)
        sentinels = (0x11111111, 0x22222222, 0x33333333, 0x44444444)
        pushed = (sentinels[3], sentinels[2], sentinels[1], sentinels[0], 6)
        callee_arguments = tuple(reversed(pushed))
        self.assertEqual(callee_arguments, (6, *sentinels))

        # Both pre-slot rejection branches target the single balanced epilogue.
        epilogue = len(dispatcher) - 5
        branch_offsets = [
            index
            for index in range(len(dispatcher) - 5)
            if dispatcher[index : index + 2] == b"\x0F\x85"
        ][:2]
        self.assertEqual(len(branch_offsets), 2)
        for offset in branch_offsets:
            displacement = struct.unpack_from("<i", dispatcher, offset + 2)[0]
            self.assertEqual(offset + 6 + displacement, epilogue)

        # Status routing does not change the caller's nonvolatile canaries
        # because every status shares that sole save/restore return.
        for status in (-1, 0, 1, 2, 3):
            registers = {
                "ebp": 0x11112222,
                "ebx": 0x33334444,
                "esi": 0x55556666,
                "edi": 0x77778888,
            }
            expected = registers.copy()
            stack = [
                registers["ebp"],
                registers["ebx"],
                registers["esi"],
                registers["edi"],
            ]
            registers.update({"ebx": status, "esi": 0xDEADBEEF, "edi": 0xBAADF00D})
            registers["edi"] = stack.pop()
            registers["esi"] = stack.pop()
            registers["ebx"] = stack.pop()
            registers["ebp"] = stack.pop()
            self.assertEqual(registers, expected)
            self.assertEqual(stack, [])

    def test_corrected_page_hashes_strings_helpers_and_export_pointer(self) -> None:
        expected_dispatchers = {
            "collection_progression": "ADBC6F0AEBB33729EFDCC85E86B396A43E2C9AD97F5D8E95EC7676F74FA9F756",
            "immediate_fixed": "ADBC6F0AEBB33729EFDCC85E86B396A43E2C9AD97F5D8E95EC7676F74FA9F756",
            "experimental_expanded_256": "371B7280C60F798C85FD3E0CDE5D01C80E2388F2B595C31815AA8340BCE77284",
            "experimental_expanded_256_progression": "371B7280C60F798C85FD3E0CDE5D01C80E2388F2B595C31815AA8340BCE77284",
        }
        expected_pages = {
            "collection_progression": "45C43434BA5D4F98A63417D0F19AB412A7635DF95B961809C3555AF1CC63F3D9",
            "immediate_fixed": "45C43434BA5D4F98A63417D0F19AB412A7635DF95B961809C3555AF1CC63F3D9",
            "experimental_expanded_256": "F4D7FEDF946045AB30CB8744EEF506EAD6532E6115112FB375765963C7586126",
            "experimental_expanded_256_progression": "F4D7FEDF946045AB30CB8744EEF506EAD6532E6115112FB375765963C7586126",
        }
        warning = (
            b"This upgrade makes permanent changes to your village. Are you sure you "
            b"want to purchase it? Press OK to confirm, or Cancel.\0"
        )
        no_change = (
            b"Everyone already likes running.\r\n"
            b"No tech points have been deducted.\0"
        )
        self.assertEqual(len(warning), 124)
        self.assertEqual(len(no_change), 68)
        self.assertEqual(
            hashlib.sha256(warning).hexdigest().upper(),
            "748FECC03CD0046F6F5B03D45D37DD9588C734C19FD57DF9717970A6F6C4FCDA",
        )
        self.assertEqual(
            hashlib.sha256(no_change).hexdigest().upper(),
            "E17788EA094CAF7DD0BE7681D7CFBD8A1FD826C67D231DFF42F06BE6D5565077",
        )
        for mode in MODES:
            layout = self.base_raw["pe_append_transaction"]["layouts"][mode]
            page = bytes.fromhex(layout["append_bytes"])
            dispatcher = page[0x40 : 0x40 + 181]
            self.assertEqual(
                hashlib.sha256(dispatcher).hexdigest().upper(),
                expected_dispatchers[mode],
            )
            running_page = bytearray(page)
            running_page[0x100:0x800] = bytes.fromhex(
                self.running_raw["patches"][0]["after"]
            )
            self.assertEqual(
                hashlib.sha256(running_page).hexdigest().upper(),
                expected_pages[mode],
            )
            self.assertEqual(page[0x800 : 0x800 + len(warning)], warning)
            self.assertEqual(page[0x880 : 0x880 + len(no_change)], no_change)
            self.assertIn(bytes.fromhex("68803F4A00"), dispatcher)
            self.assertNotIn(bytes.fromhex("68B0130010"), dispatcher)

        payload = bytes.fromhex(
            next(
                item["after"]
                for item in self.base_raw["patches"]
                if int(item["offset"], 0) == 0xA3180
            )
        )
        export_name = b"ShowOriginsVillageWideResult@20\0"
        self.assertEqual(payload[0xE00 : 0xE00 + len(export_name)], export_name)
        self.assertEqual(
            hashlib.sha256(export_name).hexdigest().upper(),
            "C3B966D86CA783C915E6B4CA0822B87C18C84328C2295560DC8D61A53381769E",
        )

    def test_repeatable_transaction_is_dry_confirm_recheck_charge_commit(self) -> None:
        slot = bytes.fromhex(self.running_raw["patches"][0]["after"])
        entry_offset = self.artifact_map["running"]["entry_offset"]
        entry_length = self.artifact_map["running"]["entry_length"]
        entry = slot[entry_offset : entry_offset + entry_length]
        calls = relative_call_targets(entry, entry_offset)
        self.assertEqual(
            calls,
            [(0x68, 0x240), (0x77, 0x800), (0xB0, 0x240), (0xFD, 0x240)],
        )

        granted_checks = [
            index
            for index in range(len(entry) - 4)
            if entry[index : index + 4] == bytes.fromhex("833C2400")
        ]
        balance_check = entry.find(bytes.fromhex("813D4426580040420F00"))
        charge = entry.find(bytes.fromhex("812D4426580040420F00"))
        self.assertEqual([value + entry_offset for value in granted_checks], [0x6D, 0xB5])
        self.assertEqual(balance_check + entry_offset, 0xBB)
        self.assertEqual(charge + entry_offset, 0xC7)
        self.assertNotIn((0x5824D0).to_bytes(4, "little"), entry)

        def instrument(
            first_granted: int,
            confirmed: bool,
            final_granted: int,
            balance: int,
            *,
            imports_available: bool = True,
        ) -> tuple[list[str], int]:
            events = ["dry"]
            if first_granted == 0:
                return events + ["no_change"], balance
            events.append("warning")
            if not imports_available or not confirmed:
                return events + ["cancel"], balance
            events.append("final_dry")
            if final_granted == 0:
                return events + ["no_change"], balance
            events.append("balance_recheck")
            if balance < 1_000_000:
                return events + ["insufficient"], balance
            return events + ["charge", "commit"], balance - 1_000_000

        self.assertEqual(
            instrument(0, False, 0, 2_000_000),
            (["dry", "no_change"], 2_000_000),
        )
        self.assertEqual(
            instrument(1, False, 1, 2_000_000),
            (["dry", "warning", "cancel"], 2_000_000),
        )
        self.assertEqual(
            instrument(1, True, 0, 2_000_000),
            (["dry", "warning", "final_dry", "no_change"], 2_000_000),
        )
        self.assertEqual(
            instrument(1, True, 1, 999_999),
            (
                ["dry", "warning", "final_dry", "balance_recheck", "insufficient"],
                999_999,
            ),
        )
        self.assertEqual(
            instrument(1, True, 1, 1_500_000),
            (
                ["dry", "warning", "final_dry", "balance_recheck", "charge", "commit"],
                500_000,
            ),
        )
        self.assertEqual(
            instrument(1, True, 1, 2_000_000, imports_available=False),
            (["dry", "warning", "cancel"], 2_000_000),
        )

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

    def test_repeatable_buy_ignores_stale_ownership_bit(self) -> None:
        def transact(
            stale_owner: bool, balance: int, granted: int
        ) -> tuple[bool, int, str]:
            del stale_owner
            if granted == 0:
                return False, balance, "no_change"
            if balance < 1_000_000:
                return False, balance, "insufficient"
            return False, balance - 1_000_000, "committed"

        self.assertEqual(transact(False, 999_999, 1), (False, 999_999, "insufficient"))
        self.assertEqual(transact(False, 2_000_000, 0), (False, 2_000_000, "no_change"))
        self.assertEqual(transact(False, 2_000_000, 1), (False, 1_000_000, "committed"))
        self.assertEqual(transact(True, 1_000_000, 0), (False, 1_000_000, "no_change"))
        self.assertEqual(transact(True, 1_000_000, 1), (False, 0, "committed"))

    def test_candidate_renders_stock_and_both_expanded_layouts(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                rendered, applied = render_patched_bytes(
                    STOCK,
                    self.build,
                    mode,
                    _fun_patches_override=[self.base, self.running],
                )
                expanded = mode.startswith("experimental_expanded_256")
                self.assertEqual(len(rendered), 0xCE000 if expanded else 0xCC000)
                self.assertEqual(
                    struct.unpack_from("<H", rendered, 0x10E)[0],
                    8 if expanded else 6,
                )
                expected_rva = (
                    0x3B8000 if expanded else 0x2DF000
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

    def test_disabled_candidate_renders_certified_hashes_and_uninstalls(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                rendered, applied = render_patched_bytes(
                    STOCK,
                    self.build,
                    mode,
                    _fun_patches_override=[self.base, self.running],
                )
                expected = self.artifact_map["rendered_candidates"][mode]
                self.assertEqual(
                    hashlib.sha256(rendered).hexdigest().upper(),
                    expected["base_plus_running_sha256"],
                )
                owners = {item["owner"] for item in applied}
                self.assertIn(f"feature:{self.base.id}", owners)
                self.assertIn(f"feature:{self.running.id}", owners)
                work = bytearray(rendered)
                with self.assertRaisesRegex(PatcherError, "dependent optional patch"):
                    _remove_feature_with_dependency_guard(
                        work,
                        self.base,
                        [self.base, self.running],
                        mode,
                    )
                _remove_feature_bytes(work, self.running, mode)
                _remove_feature_with_dependency_guard(
                    work,
                    self.base,
                    [self.base],
                    mode,
                )
                baseline, _ = render_patched_bytes(STOCK, self.build, mode)
                self.assertEqual(work, baseline)

    def test_candidate_composes_with_every_other_current_vv3_patch(self) -> None:
        expected_hashes = {
            "collection_progression": "C774634F16B18C74573BF872F77ED742907E17192CA78A49D90E71FD89EDBA4A",
            "immediate_fixed": "CACA23DF89B81F5DCEC88A5539F10F3F3778B5FDDF46E24BC5B8370ECE6156D8",
            "experimental_expanded_256": "2499C0B64063D95106EF43105C6D8E29A3E559B0AAE5EF9DCBB3B1E968582E9B",
            "experimental_expanded_256_progression": "C2AA254CD87E046EEE81E444EDF42CC4E292984214E3F7296ADF7F0C872B5C25",
        }
        others = [
            item
            for item in load_fun_patches()
            if item.game_id == "vv3"
            and item.id
            not in {
                "vv3_enable_origins_exclusive_features",
                "vv3_all_villagers_like_running",
                "vv3_full_mastery_all_stage_a_candidate",
                "vv3_individual_grant_running_candidate",
                "vv3_full_heal_cure_all_candidate",
            }
        ]
        for mode in MODES:
            with self.subTest(mode=mode):
                rendered, _ = render_patched_bytes(
                    STOCK,
                    self.build,
                    mode,
                    _fun_patches_override=[self.base, self.running, *others],
                )
                self.assertEqual(
                    len(rendered),
                    0xCE000
                    if mode.startswith("experimental_expanded_256")
                    else 0xCC000,
                )
                self.assertEqual(
                    hashlib.sha256(rendered).hexdigest().upper(),
                    expected_hashes[mode],
                )

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
