from __future__ import annotations

import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (
    EXPANDED_256_PUBLICATION_ENABLED,
    EXPANDED_PATCH_MODES,
    FunPatch,
    PatcherError,
    load_builds,
    load_fun_patches,
    render_patched_bytes,
)

STOCK = ROOT / "research/stock-executables/Virtual Villagers - New Believers.exe"
MANIFEST = ROOT / "data/vv5_origins_feature.json"
BUILDER = ROOT / "scripts/build_vv5_origins_feature.py"
COMPANION = ROOT / "assets/origins/VVFP Origins Icons.dll"
FEATURE_ID = "vv5_enable_origins_exclusive_features"


class VV5OriginsFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stock = STOCK.read_bytes()
        cls.feature = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.payload_patch = next(
            item
            for item in cls.feature["patches"]
            if int(item["offset"], 0) == 0xDB000
        )
        cls.payload = bytes.fromhex(cls.payload_patch["after"])
        cls.source = BUILDER.read_text(encoding="utf-8")

    def test_exact_build_and_companion_identity(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.stock).hexdigest().upper(),
            "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D",
        )
        companion = ROOT / self.feature["companion_files"][0]["source"]
        self.assertEqual(
            hashlib.sha256(companion.read_bytes()).hexdigest().upper(),
            self.feature["companion_files"][0]["sha256"],
        )
        self.assertEqual(
            self.feature["companion_files"][0]["sha256"],
            hashlib.sha256(companion.read_bytes()).hexdigest().upper(),
        )

    def test_d37_mockup_provenance_is_self_contained_and_exact(self) -> None:
        provenance = ROOT / "assets/candidates/vv5_full_mastery/provenance"
        expected = {
            "VV5Mockup.jpg": "4EF2DFC0DAE6C733C452CCB4BEA4023C0E2601EEF2396A1A38D75A4DCD57B00F",
            "VV5Mockup2.jpg": "104B1BE5873B1660EE4BC2E02A886C6EBB99B06CB6F0D723D20638C2B0949144",
        }
        for name, digest in expected.items():
            path = provenance / name
            self.assertTrue(path.is_file())
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest().upper(), digest)
        self.assertEqual(self.feature["provenance"]["vv5_mockups"], expected)

    def test_constructor_transports_thiscall_receiver_before_stock_ctor(self) -> None:
        self.assertEqual(
            self.source.count("mov edi, eax\n            mov ecx, edi\n            push 72"),
            2,
        )
        self.assertEqual(self.payload.count(bytes.fromhex("89F96A48")), 2)

    def test_grant_youth_label_explains_age_floor(self) -> None:
        label = "Grant Youth (-35 years, min age 5)"
        self.assertIn(label.encode("utf-16le"), COMPANION.read_bytes())

    def test_all_guards_match_stock_and_payload_is_isolated(self) -> None:
        for item in self.feature["patches"]:
            offset = int(item["offset"], 0)
            before = bytes.fromhex(item["before"])
            self.assertEqual(self.stock[offset : offset + len(before)], before)
            self.assertEqual(len(before), len(bytes.fromhex(item["after"])))
        self.assertEqual(len(self.payload), 0xF60)
        self.assertEqual(
            self.stock[0xDB000 : 0xDB000 + len(self.payload)],
            b"\0" * len(self.payload),
        )
        pe = struct.unpack_from("<I", self.stock, 0x3C)[0]
        section_table = pe + 24 + struct.unpack_from("<H", self.stock, pe + 20)[0]
        shr = section_table + 3 * 40
        self.assertEqual(self.stock[shr : shr + 8].rstrip(b"\0"), b".shr")
        characteristics = struct.unpack_from("<I", self.stock, shr + 36)[0]
        self.assertFalse(characteristics & 0x20000000)
        section_patch = next(
            item
            for item in self.feature["patches"]
            if int(item["offset"], 0) == shr + 36
        )
        self.assertEqual(section_patch["before"], "400000D0")
        self.assertEqual(section_patch["after"], "400000F0")
        # The expanded-256 overlap check is gone with the data: those rows
        # only ever applied to modes that are not selectable, and the file
        # they lived in has been removed.

    def test_no_expanded_relocation_ledger_is_emitted(self) -> None:
        """The 66-row IDA ledger is removed.

        Every row existed to relocate the payload for expanded-256, which is
        not a selectable patch mode and which no variant applies, so the rows
        could never run -- while their hand-recorded byte snapshots aborted the
        build on any legitimate payload edit.

        The "discovery-only" rule it enforced still holds and is kept: sites
        must never be found by sweeping raw payload bytes.
        """
        relocation = self.feature["expanded_shr_relocations"]
        self.assertEqual(relocation["patches"], [])
        self.assertIn("not emitted", relocation["status"])
        self.assertNotIn("for payload_offset in range(len(payload) - 3)", self.source)
        for gone in ("VV5_IDA_PAYLOAD_ABSOLUTE_RELOCATIONS",
                     "VV5_IDA_CROSS_SECTION_REL32_RELOCATIONS",
                     "VV5_IDA_EXTERNAL_ABSOLUTE_RELOCATIONS"):
            with self.subTest(symbol=gone):
                self.assertNotIn(gone, self.source)
    def test_expanded_modes_stay_unpublished_and_overrides_remain_declared(self) -> None:
        """The expanded-mode guards that still mean something.

        The relocation-row half of this check went with the ledger; the native
        hook overrides are declared in patch_mode_overrides and still are.
        """
        self.assertEqual(set(EXPANDED_PATCH_MODES), {
            "experimental_expanded_256",
            "experimental_expanded_256_progression",
        })
        self.assertFalse(EXPANDED_256_PUBLICATION_ENABLED)
        for mode in EXPANDED_PATCH_MODES:
            self.assertIn(mode, self.feature["patch_mode_overrides"])
            self.assertEqual(
                {
                    item["offset"]: item["after"]
                    for item in self.feature["patch_mode_overrides"][mode]
                },
                {"0x237B0": "568B742408", "0x1EB6F": "85F67E3456"},
            )

    def test_the_removed_ledger_leaves_no_frozen_site_sets(self) -> None:
        """The frozen rel32/external site sets went with the ledger."""
        relocation = self.feature["expanded_shr_relocations"]
        self.assertEqual(relocation["patches"], [])
        self.assertNotIn("evidence", relocation)

    def test_time_warp_is_exactly_three_displayed_years(self) -> None:
        self.assertIn("mov eax, 129600", self.source)
        self.assertIn("idiv ecx", self.source)
        self.assertIn("sub dword ptr [0x4C6250], eax", self.source)
        self.assertIn("sbb dword ptr [0x4C6254], 0", self.source)
        self.assertIn("Time Warp", self.feature["description"])
        self.assertNotIn("displayed villager years", self.feature["description"])

    def test_active_task9_time_warp_keeps_the_vv5_inverse_speed_clock_shift(self) -> None:
        """Regression test guarding against applying VV1-VV4's proportional
        Time Warp formula to VV5.

        VV5's offline catch-up MULTIPLIES the injected elapsed-clock shift by
        the game-speed code, so a constant three-displayed-year advance needs
        the inverse ``129600 / speed``.  VV1 through VV4 divide by speed and
        therefore need ``speed * 3600`` (pinned by
        tests/test_vv4_origins_feature.py).  The two forms are not an
        inconsistency between games -- they are the same three-year result
        expressed for two different engine conventions.

        Swapping VV5 onto the proportional form looks correct at normal speed
        (both give 21,600) but makes the paid 50,000-point warp advance about
        0.75 displayed years at half speed and about 8.3 at double speed.

        The equivalent VV4 test already existed; VV5 had none, which is how a
        proportional VV5 build shipped in v1.34.18.  This pins the ACTIVE
        Task9 page, which is what the public modes actually render -- not the
        superseded base builder that the older source-text check covers.
        """
        task9 = json.loads(
            (ROOT / "data/vv5_task9_native_actions.json").read_text(encoding="utf-8")
        )
        blobs = [
            bytes.fromhex(item["after"])
            for item in task9.get("patches", [])
            if item.get("after")
        ]
        transaction = task9.get("pe_append_transaction") or {}
        for layout in (transaction.get("layouts") or {}).values():
            if layout.get("append_bytes"):
                blobs.append(bytes.fromhex(layout["append_bytes"]))
        page = b"".join(blobs)
        self.assertTrue(page, "no VV5 Task9 payload bytes were found")

        # mov eax, 129600 ; xor edx, edx ; div ecx
        self.assertIn(bytes.fromhex("B840FA0100"), page)
        self.assertIn(bytes.fromhex("F7F1"), page)
        # The speed code is normalized to 3 / 6 / 10 before dividing, so an
        # unexpected value cannot produce an arbitrary advance or a div fault.
        for label, encoding in (
            ("cmp ecx, 3", "83F903"),
            ("cmp ecx, 10", "83F90A"),
            ("mov ecx, 6", "B906000000"),
        ):
            with self.subTest(check=label):
                self.assertIn(bytes.fromhex(encoding), page)
        # VV1-VV4's proportional form must never appear in the VV5 page.
        self.assertNotIn(
            bytes.fromhex("69C0100E0000"),
            page,
            "VV5 Time Warp must not use VV1-VV4's proportional speed * 3600 shift",
        )

    def test_unsafe_native_time_and_event_rows_are_disabled_for_heathen_safety(self) -> None:
        self.assertEqual(
            self.feature["native_event_safety"]["disabled_rows"],
            ["Time Warp", "Island Event", "Barrel of Babies"],
        )
        self.assertIn("not verified safe for Heathens", self.source)
        self.assertIn(b"3 displayed years", self.payload)

    def test_cure_row_truth_is_withdrawn_and_eb5f_contained(self) -> None:
        self.assertIn("Full Heal/Cure All", self.feature["description"])
        self.assertNotIn("30,000", self.feature["description"])
        cure = next(
            item for item in self.feature["patches"] if int(item["offset"], 0) == 0x94EA0
        )
        purpose = cure["purpose"].casefold()
        self.assertIn("eb5f", purpose)
        self.assertIn("unavailable", purpose)
        self.assertIn("unreachable", purpose)
        self.assertNotIn("preserve cure", purpose)

    def test_generated_vv5_transparency_section_matches_cure_truth(self) -> None:
        transparency = (ROOT / "docs" / "transparency-log.md").read_text(encoding="utf-8")
        # Derive the section heading from the task9 manifest (name + id) rather than
        # hardcoding the literal title. The heading is a GENERATED artifact; pinning
        # its exact string here would make this test pass only while the doc is in
        # sync AND silently desync on the next patch rename (which is exactly what
        # happened when the patch gained "+ Heathen Mask Cosmetics"). Mirrors the
        # derive-from-data pattern in tests/test_doubler_audit.py.
        task9 = json.loads(
            (ROOT / "data" / "vv5_task9_native_actions.json").read_text(encoding="utf-8")
        )
        marker = f"#### {task9['name']} (`{task9['id']}`)"
        section = transparency.split(marker, 1)[1].split("\n#### ", 1)[0].casefold()
        self.assertIn("full heal/cure all", section)
        self.assertIn("time warp", section)
        self.assertNotIn("30,000", section)
        self.assertNotIn("preserve cure", section)

    def test_barrel_uses_native_index_and_dynamic_150_256_guard(self) -> None:
        self.assertIn("call 0x4944C0", self.source)
        self.assertIn("mov ecx, dword ptr [0x41F1E6]", self.source)
        self.assertIn("sub ecx, 3", self.source)
        self.assertIn("or dword ptr [0x51D388], 4", self.source)
        self.assertIn("mov esi, 25", self.source)
        self.assertIn("and dword ptr [0x51D388], 0xFFFFFFFB", self.source)
        # This used to also assert that expanded-256 rewrote the slot-bound
        # immediate at 0x1F1E6 from 150 to 256. That data is removed. The stock
        # half is asserted directly instead: 0x41F1E6 is the immediate of a
        # `cmp ... 0x96`, which is what the barrel gate reads as the bound.
        stock = STOCK.read_bytes()
        self.assertEqual(
            int.from_bytes(stock[0x1F1E6:0x1F1EA], "little"), 150,
            "the VV5 slot-bound immediate the barrel gate reads is not 150",
        )

    def test_d37_selector_repair_exact_body_hook_and_guards(self) -> None:
        selector = self.feature["selector_repair"]
        self.assertEqual(selector["stock_fingerprint"]["sha256"], "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D")
        hook = selector["hook"]
        self.assertEqual(hook["file_offset"], "0x1890F")
        self.assertEqual(hook["before"], "8B7484146A64E8")
        self.assertEqual(hook["after"], "E96C9839009090")
        self.assertEqual(hook["uninstall_after"], hook["before"])
        body = selector["body"]
        expected_body = bytes.fromhex(
            "8B748414F70588D3510004000000740C832588D35100FBBE19000000"
            "6A64E8BD14C5FFE97267C6FF"
        )
        self.assertEqual(body["file_offset"], "0xDB180")
        self.assertEqual(body["virtual_address"], "0x7B2180")
        self.assertEqual(bytes.fromhex(body["after"]), expected_body)
        self.assertEqual(bytes.fromhex(body["before"]), b"\0" * 40)
        self.assertEqual(body["uninstall_after"], body["before"])
        self.assertEqual(body["sha256"], hashlib.sha256(expected_body).hexdigest().upper())
        self.assertEqual(self.payload[0x180:0x1A8], expected_body)
        self.assertEqual(self.payload[0x180:0x1A8].hex().upper(), body["after"])
        self.assertEqual(selector["native_call_virtual_address"], "0x403660")
        self.assertEqual(selector["continuation_virtual_address"], "0x41891A")
        self.assertEqual(selector["forbidden_branch_targets"], ["0x418916", "0x418917", "0x418918", "0x418919"])
        self.assertEqual(selector["shr_guard"]["header_patch"], {"file_offset": "0x28C", "before": "400000D0", "after": "400000F0"})
        self.assertTrue(selector["atomic_install_uninstall"])
        self.assertIn("jmp 0x41891A", self.source)
        self.assertNotIn("jmp 0x418916", self.source)

        rendered, _ = render_patched_bytes(
            STOCK,
            next(item for item in load_builds() if item.id == "vv5"),
            "collection_progression",
            [FEATURE_ID],
        )
        self.assertEqual(bytes(rendered[0x1890F:0x18916]).hex().upper(), "E96C9839009090")
        rendered_body = bytes(rendered[0xDB180:0xDB1A8])
        self.assertEqual(rendered_body, expected_body)
        call_at = 0xDB180 + expected_body.index(bytes.fromhex("E8BD14C5FF"))
        call_va = 0x7B2180 + expected_body.index(bytes.fromhex("E8BD14C5FF"))
        call_target = call_va + 5 + struct.unpack_from("<i", rendered, call_at + 1)[0]
        self.assertEqual(call_target, 0x403660)
        jump_at = 0xDB180 + len(expected_body) - 5
        jump_va = 0x7B2180 + len(expected_body) - 5
        continuation = jump_va + 5 + struct.unpack_from("<i", rendered, jump_at + 1)[0]
        self.assertEqual(continuation, 0x41891A)
        self.assertNotIn(continuation, {0x418916, 0x418917, 0x418918, 0x418919})
        self.assertNotIn(bytes.fromhex("E96E67C6FF"), rendered_body)

    def test_doublers_are_save_scoped_and_encode_candidate_guards(self) -> None:
        self.assertIn("test dword ptr [0x51D388], 1", self.source)
        self.assertIn("test dword ptr [0x51D388], 2", self.source)
        self.assertIn("cmp dword ptr [0x41F1E6], 0x96", self.source)
        self.assertIn("cmp ebx, 4", self.source)
        self.assertIn("or dword ptr [0x51D388], 2", self.source)
        self.assertIn("test esi, esi", self.source)
        self.assertIn("test eax, eax", self.source)
        manifest = json.loads((ROOT / "data" / "vv5_origins_feature.json").read_text(encoding="utf-8"))
        evidence = manifest["doubler_evidence"]
        contract = manifest["doubler_composition_contract"]
        self.assertIn("stock-layout implemented", evidence["hook_status"])
        self.assertIn("expanded-256", contract["status"])
        self.assertEqual(
            contract["exclusions"],
            ["Island Event tech-point gain", "Duplicate Collectibles tech-point gain"],
        )
        self.assertEqual(
            manifest["doubler_purchase_status"]["new_purchase"],
            "Tech and Food available in stock layout at 500,000 tech points after their exact positive-whitelist wrappers; both unavailable in expanded-256",
        )
        self.assertEqual(
            manifest["doubler_purchase_status"]["repurchase"],
            "full-price repurchase after zero-cost/no-refund removal in stock layout for both doublers; expanded-256 remains unavailable for new purchases",
        )

    def test_tech_wrapper_exact_stock_bytes_and_three_return_whitelist(self) -> None:
        evidence = self.feature["doubler_evidence"]["tech_writer_hook"]
        self.assertEqual(evidence["virtual_address"], "0x4237B0")
        self.assertEqual(evidence["file_offset"], "0x237B0")
        self.assertEqual(evidence["before"], "568B742408")
        self.assertEqual(evidence["after"], "E94BF23800")
        self.assertEqual(evidence["wrapper_virtual_address"], "0x7B2A00")
        self.assertEqual(evidence["wrapper_file_offset"], "0xDBA00")
        expected = (
            "8B44240485C07E2BF70588D3510001000000741F"
            "813C244DDE46007412813C247CDE46007409813C24A5DE46007504"
            "D1642404568B7424080131E9780DC7FF"
        )
        wrapper = bytes.fromhex(evidence["wrapper_bytes"])
        self.assertEqual(wrapper.hex().upper(), expected)
        self.assertEqual(len(wrapper), 63)
        self.assertEqual(evidence["ownership_mask"], "0x1")
        self.assertEqual(
            evidence["eligible_returns"],
            ["0x46DE4D", "0x46DE7C", "0x46DEA5"],
        )
        self.assertEqual(evidence["excluded_refund_return"], "0x419EA3")
        self.assertEqual(evidence["branch_destinations"], ["0x7B2A4A", "0x7B2A4E", "0x4237B7"])
        self.assertEqual(
            self.feature["doubler_evidence"]["tech_exclusions"],
            [
                "all 16 Island Event outcomes",
                "Duplicate Collectibles (returns 0x4147BE, 0x4147DD, and 0x4147F9)",
                "all eight writer tail paths",
                "technology purchase/spending/deduction paths",
                "zero and negative deltas",
                "unknown caller returns",
            ],
        )
        payload_offset = 0xDB000 + (0x7B2A00 - 0x7B2000)
        self.assertEqual(self.payload[payload_offset - 0xDB000 : payload_offset - 0xDB000 + 63], wrapper)

    def test_tech_mode_marker_and_purchase_matrix(self) -> None:
        self.assertIn("tech_owned_remove", self.source)
        self.assertIn("cmp dword ptr [0x41F1E6], 0x96", self.source)
        self.assertIn("or dword ptr [0x51D388], 1", self.source)
        overrides = self.feature["patch_mode_overrides"]
        for mode in ("experimental_expanded_256", "experimental_expanded_256_progression"):
            entries = overrides[mode]
            tech = next(item for item in entries if item["offset"] == "0x237B0")
            self.assertEqual(tech["before"], "E94BF23800")
            self.assertEqual(tech["after"], "568B742408")
            self.assertIn("no expanded Tech Doubler detour", tech["purpose"])

        def tech_action(owned: bool, marker: int) -> str:
            if owned:
                return "remove"
            return "purchase" if marker == 0x96 else "unavailable"

        for expanded, marker in ((False, 0x96), (True, 0x100)):
            with self.subTest(expanded=expanded):
                self.assertEqual(tech_action(False, marker), "purchase" if not expanded else "unavailable")
                self.assertEqual(tech_action(True, marker), "remove")
        build = next(item for item in load_builds() if item.id == "vv5")
        for mode, expected_hook, expected_marker in (
            ("collection_progression", "E94BF23800", "96000000"),
            ("immediate_fixed", "E94BF23800", "96000000"),
        ):
            with self.subTest(mode=mode):
                rendered, _ = render_patched_bytes(
                    STOCK, build, mode, [FEATURE_ID]
                )
                self.assertEqual(bytes(rendered[0x237B0 : 0x237B5]).hex().upper(), expected_hook)
                self.assertEqual(bytes(rendered[0x1F1E6 : 0x1F1EA]).hex().upper(), expected_marker)

    def test_tech_positive_whitelist_reference_matrix(self) -> None:
        eligible = {0x46DE4D, 0x46DE7C, 0x46DEA5}
        excluded = {0x4147BE, 0x4147DD, 0x4147F9, 0x419EA3, 0x420000, 0x46CED1}

        def adjusted(owner: bool, return_va: int, delta: int) -> int:
            if not owner or delta <= 0 or return_va not in eligible:
                return delta
            return delta * 2

        for return_va in eligible:
            with self.subTest(return_va=hex(return_va)):
                self.assertEqual(adjusted(True, return_va, 5), 10)
                self.assertEqual(adjusted(False, return_va, 5), 5)
        for return_va in excluded:
            with self.subTest(return_va=hex(return_va)):
                self.assertEqual(adjusted(True, return_va, 5), 5)
        for delta in (0, -1, -500000):
            self.assertEqual(adjusted(True, 0x4147BE, delta), delta)
        # The wrapper receives the final positive delta and doubles only once.
        self.assertEqual(adjusted(True, 0x46DE4D, 5), 10)

    def test_food_wrapper_exact_stock_bytes_and_whitelist(self) -> None:
        evidence = self.feature["doubler_evidence"]["stock_hook"]
        self.assertEqual(evidence["virtual_address"], "0x41EB6F")
        self.assertEqual(evidence["file_offset"], "0x1EB6F")
        self.assertEqual(evidence["before"], "85F67E3456")
        self.assertEqual(evidence["after"], "E98C3F3900")
        self.assertEqual(evidence["wrapper_virtual_address"], "0x7B2B00")
        self.assertEqual(evidence["wrapper_file_offset"], "0xDBB00")
        wrapper = bytes.fromhex(evidence["wrapper_bytes"])
        self.assertEqual(
            wrapper.hex().upper(),
            "85F67E18F70588D3510002000000740C817C240870494100750201F685F67E0656E94EC0C6FFE97CC0C6FF",
        )
        self.assertEqual(len(wrapper), 43)
        self.assertEqual(evidence["branch_destinations"], ["0x41EB74", "0x41EBA7"])
        self.assertEqual(evidence["eligible_return"], "0x414970")
        self.assertEqual(evidence["ownership_mask"], "0x2")
        payload_offset = 0xDB000 + (0x7B2B00 - 0x7B2000)
        self.assertEqual(self.payload[payload_offset - 0xDB000 : payload_offset - 0xDB000 + 43], wrapper)

    def test_food_mode_marker_and_purchase_matrix(self) -> None:
        self.assertIn("cmp dword ptr [0x41F1E6], 0x96", self.source)
        self.assertIn("or eax, 0x0800", self.source)
        self.assertIn("or eax, 0x1000", self.source)
        self.assertIn("food_owned", self.source)
        self.assertIn("food_owned_remove", self.source)
        self.assertIn("or dword ptr [0x51D388], 2", self.source)
        self.assertEqual(self.stock[0x1F1E6 : 0x1F1EA], bytes.fromhex("96000000"))
        overrides = self.feature["patch_mode_overrides"]
        self.assertEqual(set(overrides), {"experimental_expanded_256", "experimental_expanded_256_progression"})
        for mode, entries in overrides.items():
            self.assertEqual(len(entries), 2)
            food = next(item for item in entries if item["offset"] == "0x1EB6F")
            self.assertEqual(food["before"], "E98C3F3900")
            self.assertEqual(food["after"], "85F67E3456")
            self.assertIn("no expanded Food Doubler detour", food["purpose"])

        def food_action(owned: bool, marker: int) -> str:
            if owned:
                return "remove"
            return "purchase" if marker == 0x96 else "unavailable"

        for expanded, marker in ((False, 0x96), (True, 0x100)):
            with self.subTest(expanded=expanded):
                self.assertEqual(food_action(False, marker), "purchase" if not expanded else "unavailable")
                self.assertEqual(food_action(True, marker), "remove")
                state = 0x0800  # Tech row remains unavailable in every mode.
                if expanded:
                    state |= 0x1000
                self.assertEqual(bool(state & 0x1000), expanded)
                owned_state = state | 0x10
                self.assertTrue(owned_state & 0x10)
        self.assertEqual(food_action(False, 0), "unavailable")
        build = next(item for item in load_builds() if item.id == "vv5")
        for mode, expected_hook, expected_marker in (
            ("collection_progression", "E98C3F3900", "96000000"),
            ("immediate_fixed", "E98C3F3900", "96000000"),
        ):
            with self.subTest(mode=mode):
                rendered, _ = render_patched_bytes(
                    STOCK, build, mode, [FEATURE_ID]
                )
                self.assertEqual(bytes(rendered[0x1EB6F : 0x1EB74]).hex().upper(), expected_hook)
                self.assertEqual(bytes(rendered[0x1F1E6 : 0x1F1EA]).hex().upper(), expected_marker)

    def test_patch_override_schema_rejects_malformed_lengths(self) -> None:
        from vv_fun_patcher import PatcherError, Record, validate_fun_patch_catalog

        malformed = Record(
            {
                "id": "vv5_test_override",
                "name": "VV5 test override",
                "game_id": "vv5",
                "patches": [],
                "patch_mode_overrides": {
                    "experimental_expanded_256": [
                        {
                            "offset": "0x1EB6F",
                            "before": "85F67E3456",
                            "after": "90",
                            "purpose": "malformed test",
                        }
                    ]
                },
            }
        )
        with self.assertRaises(PatcherError):
            validate_fun_patch_catalog([malformed])

    def test_food_mastery_final_delta_reference_matrix(self) -> None:
        for native, doubled in ((6, 12), (35, 70), (9, 18), (52, 104), (12, 24), (70, 140)):
            with self.subTest(native=native):
                self.assertEqual(native * 2, doubled)
        self.assertEqual(0, 0)
        self.assertLessEqual(-5, 0)

    def test_food_mastery_exact_build_and_positive_whitelist_metadata(self) -> None:
        manifest = json.loads((ROOT / "data" / "vv5_origins_feature.json").read_text(encoding="utf-8"))
        evidence = manifest["doubler_evidence"]
        self.assertEqual(evidence["build"], {
            "filename": "Virtual Villagers - New Believers.exe",
            "size": 991232,
            "sha256": "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D",
        })
        mastery = evidence["food_mastery"]
        self.assertEqual(mastery["technology_id"], 4)
        self.assertEqual(mastery["costs"], {"level_1_to_2": 3000, "level_2_to_3": 40000})
        self.assertEqual(mastery["collection_return"], "0x414970")
        self.assertEqual(mastery["collection_base_to_native"], {"6": [6, 9, 12], "35": [35, 52, 70]})
        self.assertIn("unknown callers remain native", evidence["island_event_producers"][0])

    def test_food_mastery_metadata_change_does_not_change_runtime_payload_fields(self) -> None:
        runtime = {
            key: self.feature[key]
            for key in ("patches", "expanded_shr_relocations")
        }
        digest = hashlib.sha256(
            json.dumps(runtime, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest().upper()
        self.assertEqual(
            digest,
            "CDD9D25ADD4C084E8B2D6DD101C21121DC4A62B47118299902CD77738C5D3E59",
        )
        self.assertEqual(
            self.feature["companion_files"][0]["sha256"],
            "2ED1100E7F2EA5B8E522C2DE11F6B00CA8A02B968319C251365E9EFD634BCAF9",
        )

    def test_six_float_skills_and_age_companions_are_written(self) -> None:
        for offset in (7260, 7264, 7268, 7272, 7276, 7280):
            self.assertIn(
                f"mov dword ptr [edx + {offset}], 0x42C80000", self.source
            )
        self.assertIn("cmp eax, 100", self.source)
        self.assertIn("mov eax, 100", self.source)
        self.assertIn("mov eax, 360", self.source)
        self.assertIn("add dword ptr [edx + 7228], ecx", self.source)
        self.assertIn("add dword ptr [edx + 7244], ecx", self.source)

    def test_running_changes_only_selected_record_preferences(self) -> None:
        self.assertIn("lea ecx, [edx + 8028]", self.source)
        self.assertIn("lea ecx, [edx + 8040]", self.source)
        self.assertIn("RUNNING_PREFERENCE_ID = 38", self.source)
        self.assertIn("mov dword ptr [ecx], {RUNNING_PREFERENCE_ID}", self.source)
        self.assertIn("mov dword ptr [ecx], -1", self.source)
        self.assertIn("all Like slots are full", self.source)
        running_block = self.source.split("running:", 1)[1].split(
            "detail_success:", 1
        )[0]
        for forbidden in ("0x17D7C", "movement", "speed"):
            self.assertNotIn(forbidden, running_block)

    def test_all_individual_origins_actions_preflight_current_believer(self) -> None:
        detail = self.source.split('"detail_menu",', 1)[1].split('"tech_increment",', 1)[0]
        for check in (
            "cmp byte ptr [edx + 0x1CD4], 0",
            "cmp byte ptr [edx + 0x1CE1], 0",
            "cmp dword ptr [edx + 0x1C40], 0",
            "cmp byte ptr [edx + 0x1CEC], 0",
        ):
            self.assertGreaterEqual(detail.count(check), 2)
        self.assertNotIn("mov byte ptr [edx + 0x1CEC]", detail)

    def test_composes_with_every_vv5_feature_in_public_modes(self) -> None:
        build = next(item for item in load_builds() if item.id == "vv5")
        all_vv5 = [
            item
            for item in load_fun_patches()
            if item.game_id == "vv5"
            and item.id
            not in {
                FEATURE_ID,
                "vv5_full_mastery_all_stage_a_candidate",
            }
        ]
        active_ids = {item.id for item in load_fun_patches() if item.game_id == "vv5"}
        self.assertIn(FEATURE_ID, active_ids)
        self.assertNotIn("vv5_full_mastery_all_stage_a_candidate", active_ids)
        for mode in ("collection_progression", "immediate_fixed"):
            with self.subTest(mode=mode):
                rendered, applied = render_patched_bytes(
                    STOCK,
                    build,
                    mode,
                    _fun_patches_override=[FunPatch(self.feature), *all_vv5],
                )
                self.assertGreater(len(applied), len(self.feature["patches"]))
                expected_payload = bytearray(self.payload)
                self.assertEqual(
                    bytes(rendered[0xDB000 : 0xDB000 + len(self.payload)]),
                    bytes(expected_payload),
                )

    @unittest.skip("Expanded-256 modes were removed from the public patcher.")
    def test_expanded_mode_relocates_all_origins_shr_pointers(self) -> None:
        build = next(item for item in load_builds() if item.id == "vv5")
        rendered, applied = render_patched_bytes(
            STOCK,
            build,
            "experimental_expanded_256",
            _fun_patches_override=[FunPatch(self.feature)],
        )
        relocation = self.feature["expanded_shr_relocations"]
        delta = int(relocation["expanded_virtual_address"], 0) - int(
            relocation["stock_virtual_address"], 0
        )
        relocation_offsets = {item["offset"] for item in relocation["patches"]}
        applied_offsets = {
            item["offset"] for item in applied if item["offset"] in relocation_offsets
        }
        self.assertEqual(applied_offsets, relocation_offsets)
        for item in relocation["patches"]:
            offset = int(item["offset"], 0)
            actual = bytes(rendered[offset : offset + 4])
            if item.get("expanded_skip_before"):
                self.assertEqual(actual.hex().upper(), item["expanded_skip_before"])
                continue
            if item.get("kind", "absolute") == "absolute":
                expected = int.from_bytes(bytes.fromhex(item["before"]), "little") + delta
                self.assertEqual(actual, expected.to_bytes(4, "little"))
                continue
            source = int(item["source_expanded_virtual_address"], 0)
            target = int(item["target_expanded_virtual_address"], 0)
            expected = (target - (source + 5)).to_bytes(4, "little", signed=True)
            self.assertEqual(actual, expected)

        self.assertEqual(relocation["evidence"]["cross_section_rel32_sites"], 36)
        self.assertEqual(relocation["evidence"]["external_absolute_sites"], 7)
        self.assertEqual(relocation["evidence"]["complete_current_feature_relocation_sites"], 43)
        self.assertEqual(
            sum(item.get("kind", "absolute") == "rel32" for item in relocation["patches"]),
            36,
        )
        self.assertEqual(
            sum(
                item.get("kind", "absolute") == "absolute"
                and "external" in item.get("purpose", "")
                for item in relocation["patches"]
            ),
            7,
        )

    def test_stock_mode_keeps_origins_shr_pointers_unchanged(self) -> None:
        build = next(item for item in load_builds() if item.id == "vv5")
        rendered, applied = render_patched_bytes(
            STOCK,
            build,
            "collection_progression",
            _fun_patches_override=[FunPatch(self.feature)],
        )
        relocation = self.feature["expanded_shr_relocations"]
        relocation_offsets = {int(item["offset"], 0) for item in relocation["patches"]}
        self.assertFalse(
            any(int(item["offset"], 0) in relocation_offsets for item in applied)
        )
        for item in relocation["patches"]:
            offset = int(item["offset"], 0)
            self.assertEqual(
                rendered[offset : offset + 4], bytes.fromhex(item["before"])
            )

    @unittest.skip("Expanded-256 modes were removed from the public patcher.")
    def test_expanded_output_keeps_vanilla_name_and_stock_save_fallback(self) -> None:
        build = next(item for item in load_builds() if item.id == "vv5")
        render_patched_bytes(STOCK, build, "experimental_expanded_256", [FEATURE_ID])


if __name__ == "__main__":
    unittest.main()
