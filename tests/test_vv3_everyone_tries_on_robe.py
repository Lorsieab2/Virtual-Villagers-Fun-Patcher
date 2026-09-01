from __future__ import annotations

import hashlib
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher


FEATURE_ID = "vv3_everyone_tries_on_robe"
MODES = (
    "collection_progression",
    "immediate_fixed",
)
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
EXPANDED_PROTOTYPE = ROOT / "research" / "vv3-expanded-prototype.exe"
PAYLOAD_SHA256 = "4810476C53CDBC4108100E10DF7404F7FBB0476CFF850110CEF4E761C9ADE9B8"
ZERO_CAVE_SHA256 = "22B94C6893BFC091BE2A9F454A045184DF6C0398CFFA2B4E90C0065DD6EEB1B0"
ISOLATED_RESULTS = {
    "stock": (
        "4A7A2BB6D4C5D564EC6ABD6A929842D800C6E784C2B77B21DD657C87F77E60E2",
        "A8EC0C00",
    ),
}
RENDERED_RESULTS = {
    "collection_progression": (
        "5B5988A2D493C4867F9C4356A46613A782FD35812232A76F8D1C26C8568E9ADE",
        "A2C60C00",
    ),
    "immediate_fixed": (
        "9A4E6DF88BD51BBBE2E33CA1118EA518817B0C1E161977D83DB609012E920B51",
        "A0080D00",
    ),
}
BASE_RESULTS = {
    "collection_progression": "AF6F2817D9AA6C15466DCE73E0B27EDB1EF9C7238BBA4597889BFBADF0985F90",
    "immediate_fixed": "551A1716FE73EC983747133C12FDDFA3A1C7CBCA70B84F71631FFF4F064B42C6",
}
EXPANDED_COMPOSITION_RESULTS = {
    "experimental_expanded_256": (
        "20B68A0F5BA4E9869C4F7FD9C53E6E81610EDC259E9F4906C201CF7D519E237C",
        "67E80C00",
    ),
    "experimental_expanded_256_progression": (
        "CC0A7F1B17099C6F29BE0BC163BBDBDB94F43398CB6BC10905811645842A2282",
        "71630D00",
    ),
}
STOCK_CATALOG_COMPOSITION_RESULTS = {
    "collection_progression": (
        "B848EE8D1DAE9BADF56FDCB71401C69ADAA4C357AE1368F421632D38FA90C83F",
        "9CBB0D00",
    ),
    "immediate_fixed": (
        "15D9492D24B7E4D7BB5838175D3506570D072B4D7E719BF6EBBC741F25C7E188",
        "9BFD0C00",
    ),
}


def digest(data: bytes | bytearray) -> str:
    return hashlib.sha256(data).hexdigest().upper()


class VV3EveryoneTriesOnRobeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.build = next(item for item in patcher.load_builds() if item.id == "vv3")
        cls.feature = patcher.get_fun_patch(FEATURE_ID)
        cls.payload_row = next(
            row for row in cls.feature.patches if row["offset"] == "0xB4100"
        )
        cls.payload = bytes.fromhex(cls.payload_row["after"])

    def test_visible_optional_catalog_entry_is_unselected_by_default(self) -> None:
        raw = self.feature.raw
        self.assertTrue(raw["enabled"])
        self.assertTrue(raw["catalog_enabled"])
        self.assertFalse(raw["catalog_hidden"])
        self.assertFalse(raw["default_selected"])
        self.assertEqual(tuple(raw["supported_modes"]), ("stock", *MODES))
        self.assertEqual(raw.get("dependencies", []), [])
        self.assertEqual(
            patcher.resolve_fun_patch_ids([], game_id="vv3"),
            [],
        )
        self.assertEqual(
            patcher.resolve_fun_patch_ids([FEATURE_ID], game_id="vv3"),
            [FEATURE_ID],
        )

    def test_exact_reviewed_payload_and_three_owned_ranges(self) -> None:
        self.assertEqual(len(self.payload), 235)
        self.assertEqual(digest(self.payload), PAYLOAD_SHA256)
        self.assertEqual(self.payload[0xCD], 0x90)
        zero_cave = bytes.fromhex(self.payload_row["before"])
        self.assertEqual(len(zero_cave), 235)
        self.assertEqual(digest(zero_cave), ZERO_CAVE_SHA256)

        common = {row["offset"]: row for row in self.feature.patches}
        self.assertEqual(set(common), {"0x280", "0x29C", "0xB4100"})
        self.assertEqual(common["0x280"]["before"], "04000000")
        self.assertEqual(common["0x280"]["after"], "00100000")
        # D166 fix: the VirtualSize patch above only extended the declared
        # size of .shr; it never set the section's own executable
        # permission bit, so the robe wrapper it maps was written into a
        # page Windows would refuse to execute. This second patch adds the
        # missing permission bit (0x20000000) while preserving every other
        # bit already set on the section.
        self.assertEqual(common["0x29C"]["before"], "400000D0")
        self.assertEqual(common["0x29C"]["after"], "600000F0")
        for mode in MODES:
            rows = self.feature.raw["patch_mode_overrides"][mode]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["offset"], "0x22B2A")
            self.assertEqual(rows[0]["before"], "60194200")
            expected = "00117A00" if mode.startswith("experimental_") else "00816C00"
            self.assertEqual(rows[0]["after"], expected)

    def test_initiator_uses_stock_callback_and_fanout_assigns_the_robe_action(self) -> None:
        """The initiator keeps the complete stock drop path; everyone else is
        interrupted into the robe action through the stock dispatcher.

        The wrapper used to broadcast by calling the stock drop handler
        ``0x421960`` once per villager.  That function is gated on the
        robe-candidate flag ``[record+0xE80]`` and returns ``xor al,al`` without
        assigning anything when it is clear, so for every non-candidate the
        broadcast was a silent no-op: they kept their current action and never
        walked to the amphitheatre.

        The fanout calls ``0x455570(record, 0x38, ptr)``: the same action
        dispatcher the stock success path uses, writing the villager's action
        field ``+0xF24`` and dispatching through the global table at
        ``0x596970``.

        The action id is ``0x38``, not ``0x39``.  An instruction-level trace of
        the stock success path shows it assigns TWO different ids:

            0x45E0C0(0x38, 7, -1, 0) on the manager 0x59E110
                -> 0x45DDE0 sweeps 150 slots, filters, and calls
                   0x455570(record, 0x38, scratch) for EACH selected villager
            0x455570(initiator, 0x39, ptr)

        So ``0x38`` is the crowd action every other villager receives and
        ``0x39`` belongs to the one the player dropped.  The fanout previously
        assigned ``0x39`` to everybody -- the initiator's action -- and ran
        after the stock selector, overwriting the ``0x38`` the game had just
        assigned.  That is why one villager robed and the rest performed a
        different action.
        """
        stock_call = bytes.fromhex("B860194200FFD0")   # mov eax,0x421960 ; call eax
        dispatch = bytes.fromhex("B870554500FFD0")     # mov eax,0x455570 ; call eax

        # Exactly one stock drop call remains: the dropped initiator.
        self.assertEqual(self.payload.count(stock_call), 1)
        # ...and it is the first thing the wrapper does, with AL preserved.
        self.assertLess(self.payload.index(stock_call), self.payload.index(dispatch))
        self.assertIn(bytes.fromhex("88C384C0"), self.payload)  # mov bl,al ; test al,al

        # The fanout assigns the robe action through the stock dispatcher.
        self.assertEqual(self.payload.count(dispatch), 1)
        # 0x39 IS the robe attempt: the stock success path dispatches it to the
        # dropped villager at 0x421995, and no stock site passes 0x38 to this
        # dispatcher at all. Fanning out 0x38 instead re-applies the spectator
        # action to the whole village, which is the reported bug.
        self.assertIn(bytes.fromhex("6A39"), self.payload)      # push 0x39
        self.assertNotIn(
            bytes.fromhex("6A38"), self.payload,
            "fanning out the crowd action makes everyone spectate instead of "
            "trying the robe on",
        )
        self.assertIn(bytes.fromhex("89F9"), self.payload)      # mov ecx,edi (thiscall)
        # The loop counter and record cursor are preserved across game code.
        self.assertIn(bytes.fromhex("5157"), self.payload)      # push ecx ; push edi
        self.assertIn(bytes.fromhex("5F59"), self.payload)      # pop edi ; pop ecx

        # The initiator gate: active, living, non-nursing, and left by the stock
        # handler in a robe action.
        #
        # 0x39 MUST be among the accepted ids. The stock callback's success path
        # ends with 0x455570(initiator, 0x39, ptr), whose first instruction is
        # `mov [ecx+0xF24], eax` with eax = 0x39 -- so that is the value sitting
        # in the field the moment the callback returns. Accepting only 0x78/0x79
        # made this gate unsatisfiable, the fanout never ran, and the village
        # kept stock behaviour: one villager robed and the stock crowd call
        # 0x45E0C0(0x38, 7, -1, 0) sent seven others to lecture.
        for label, encoding in (
            ("initiator active +0xF10", "83BE100F000000"),
            ("initiator living +0xE78", "83BE780E000000"),
            ("initiator non-nursing +0xE8C", "83BE8C0E000000"),
            ("initiator action +0xF24 accepts 0x39", "8B86240F000083F839"),
            ("initiator action +0xF24 accepts 0x78", "83F878"),
            ("initiator action +0xF24 accepts 0x79", "83F879"),
        ):
            with self.subTest(gate=label):
                self.assertIn(bytes.fromhex(encoding), self.payload)

        # Only the two exact stock runtime bounds are accepted, and the scan
        # walks the record array by its exact stride.
        self.assertIn(bytes.fromhex("81F996000000"), self.payload)   # cmp ecx,150
        self.assertIn(bytes.fromhex("81F900010000"), self.payload)   # cmp ecx,256
        self.assertIn(bytes.fromhex("BF24E15900"), self.payload)     # mov edi,record base
        self.assertIn(bytes.fromhex("81C78C1F0000"), self.payload)   # add edi,0x1F8C

        # Each fanned-out record repeats the same eligibility gate.
        for label, encoding in (
            ("follower active +0xF10", "83BF100F000000"),
            ("follower living +0xE78", "83BF780E000000"),
            ("follower non-nursing +0xE8C", "83BF8C0E000000"),
        ):
            with self.subTest(gate=label):
                self.assertIn(bytes.fromhex(encoding), self.payload)

        # The native chief selector is untouched: the candidate-selection
        # fields +0xE80 and +0xE88 are never read or written, and no other
        # game routine is called.
        self.assertNotIn(bytes.fromhex("800E0000"), self.payload)
        self.assertNotIn(bytes.fromhex("880E0000"), self.payload)
        self.assertNotIn(bytes.fromhex("B8B0114600FFD0"), self.payload)
        self.assertNotIn(bytes.fromhex("B8301C4500FFD0"), self.payload)
        self.assertNotIn(bytes.fromhex("6A006A646A05"), self.payload)
        # The old candidate-gated broadcast sequence must be gone.
        self.assertNotIn(bytes.fromhex("5157B860194200FFD083C40459"), self.payload)

        self.assertIn(bytes.fromhex("88D88D65F45F5E5B5DC3"), self.payload)

    def test_every_supported_mode_actually_hooks_the_wrapper(self) -> None:
        """Installing the wrapper is useless unless the callback is repointed.

        patch_mode_overrides declared the 0x22B2A hook only for
        collection_progression and immediate_fixed, while supported_modes also
        advertises stock.  In stock mode the renderer therefore applied the
        three common ranges, left the callback pointing at the stock handler
        0x421960, and the feature silently did nothing -- the catalog offered a
        patch that could not fire.  The existing mode tests missed it because
        their MODES tuple excludes stock.
        """
        overrides = self.feature.raw["patch_mode_overrides"]
        supported = tuple(self.feature.raw["supported_modes"])
        for mode in supported:
            with self.subTest(mode=mode):
                self.assertIn(
                    mode, overrides, "supported mode has no callback hook"
                )

        if not STOCK.is_file():
            self.skipTest("stock VV3 executable fixture is unavailable")
        for mode in supported:
            with self.subTest(rendered=mode):
                rendered, _ = patcher.render_patched_bytes(
                    STOCK, self.build, mode, [FEATURE_ID]
                )
                target = int.from_bytes(rendered[0x22B2A:0x22B2E], "little")
                self.assertEqual(
                    target,
                    0x6C8100,
                    f"{mode} does not repoint the robe callback at the wrapper",
                )
                self.assertNotEqual(target, 0x421960)

    def test_payload_matches_its_generator(self) -> None:
        """The cave is generated, not hand-written hex.

        This patch had no builder for its entire life: the 235-byte wrapper
        lived only as a literal in data/builds.json, which is why a broadcast
        that assigned nothing to most villagers went unnoticed.
        """
        import importlib.util

        builder_path = ROOT / "scripts" / "build_vv3_everyone_tries_on_robe.py"
        self.assertTrue(builder_path.is_file(), "the robe cave builder is missing")
        spec = importlib.util.spec_from_file_location("vv3_robe_builder", builder_path)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:  # pragma: no cover - keystone is optional
            self.skipTest(f"robe builder unavailable: {exc}")
        self.assertEqual(module.build_wrapper(), self.payload)
        self.assertEqual(module.PAYLOAD_LEN, len(self.payload))
        self.assertEqual(module.PAYLOAD_FILE_OFFSET, 0xB4100)

    def test_authenticated_stock_preimages_and_native_action_registrations(self) -> None:
        source = STOCK.read_bytes()
        self.assertEqual(len(source), 831488)
        self.assertEqual(digest(source), self.build.sha256)
        self.assertEqual(source[0x278:0x280].split(b"\0", 1)[0], b".shr")
        self.assertEqual(source[0x280:0x284], bytes.fromhex("04000000"))
        self.assertEqual(source[0x284:0x288], bytes.fromhex("00802C00"))
        self.assertEqual(source[0x288:0x28C], bytes.fromhex("00100000"))
        self.assertEqual(source[0x28C:0x290], bytes.fromhex("00400B00"))
        self.assertEqual(source[0x29C:0x2A0], bytes.fromhex("400000D0"))
        self.assertEqual(source[0x22B2A:0x22B2E], bytes.fromhex("60194200"))
        self.assertEqual(source[0x2883A:0x2883E], bytes.fromhex("96000000"))
        self.assertEqual(
            source[0x542E6:0x542F2],
            bytes.fromhex("68B01B45006A78E8BECEFEFF"),
        )
        self.assertEqual(
            source[0x542F2:0x542FE],
            bytes.fromhex("68301C45006A79E8B2CEFEFF"),
        )
        self.assertEqual(digest(source[0xB4000:0xB5000]), "AD7FACB2586FC6E966C004D7D1D16B024F5805FF7CB47C7A85DABD8B48892CA7")
        self.assertEqual(digest(source[0xB4100:0xB41EB]), ZERO_CAVE_SHA256)

    def test_isolated_authenticated_stock_and_expanded_prototype_results(self) -> None:
        cases = (
            ("stock", STOCK, "collection_progression"),
        )
        for name, path, mode in cases:
            with self.subTest(name=name):
                data = bytearray(path.read_bytes())
                rows = [
                    *self.feature.patches,
                    *self.feature.raw["patch_mode_overrides"][mode],
                ]
                for row in rows:
                    offset = int(row["offset"], 0)
                    before = bytes.fromhex(row["before"])
                    after = bytes.fromhex(row["after"])
                    self.assertEqual(data[offset : offset + len(before)], before)
                    data[offset : offset + len(after)] = after
                checksum_offset, _ = patcher._pe_checksum_layout(data)
                struct.pack_into("<I", data, checksum_offset, 0)
                struct.pack_into("<I", data, checksum_offset, patcher.pe_checksum(data))
                expected_hash, expected_checksum = ISOLATED_RESULTS[name]
                self.assertEqual(digest(data), expected_hash)
                self.assertEqual(data[checksum_offset : checksum_offset + 4].hex().upper(), expected_checksum)

    def test_current_renderer_modes_and_exact_uninstall_roundtrip(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                rendered, applied = patcher.render_patched_bytes(
                    STOCK, self.build, mode, [FEATURE_ID]
                )
                expected_hash, expected_checksum = RENDERED_RESULTS[mode]
                self.assertEqual(digest(rendered), expected_hash)
                self.assertEqual(rendered[0x160:0x164].hex().upper(), expected_checksum)
                owner = [
                    row for row in applied
                    if row.get("owner") == f"feature:{FEATURE_ID}"
                ]
                self.assertEqual(len(owner), 4)
                intervals = sorted(
                    (int(row["offset"], 0), int(row["offset"], 0) + len(bytes.fromhex(row["after"])))
                    for row in owner
                )
                self.assertTrue(all(left[1] <= right[0] for left, right in zip(intervals, intervals[1:])))
                self.assertEqual(rendered[0x280:0x284], bytes.fromhex("00100000"))
                self.assertEqual(digest(rendered[0xB4100:0xB41EB]), PAYLOAD_SHA256)
                # D166 fix: .shr is now actually marked executable (bit
                # 0x20000000 added), not just declared bigger.
                self.assertEqual(rendered[0x29C:0x2A0], bytes.fromhex("600000F0"))
                if mode.startswith("experimental_"):
                    self.assertEqual(rendered[0x284:0x288], bytes.fromhex("00103A00"))
                    self.assertEqual(rendered[0x22B2A:0x22B2E], bytes.fromhex("00117A00"))
                    self.assertEqual(rendered[0x2883A:0x2883E], bytes.fromhex("00010000"))
                    self.assertEqual(rendered[0x27A39:0x27A3D], bytes.fromhex("E4040000"))
                    details = [
                        row for row in applied
                        if row.get("owner") == "automatic:vv3-expanded-detail-roster-layout"
                    ]
                    self.assertEqual(len(details), 151)
                    self.assertEqual(
                        len([
                            row for row in applied
                            if row.get("owner")
                            == "automatic:vv3-expanded-chief-candidate-assignment"
                        ]),
                        1,
                    )
                else:
                    self.assertEqual(rendered[0x284:0x288], bytes.fromhex("00802C00"))
                    self.assertEqual(rendered[0x22B2A:0x22B2E], bytes.fromhex("00816C00"))
                    self.assertEqual(rendered[0x2883A:0x2883E], bytes.fromhex("96000000"))

                baseline, _ = patcher.render_patched_bytes(STOCK, self.build, mode, [])
                self.assertEqual(digest(baseline), BASE_RESULTS[mode])
                removed = bytearray(rendered)
                rows = patcher._remove_feature_bytes(removed, self.feature, mode)
                self.assertEqual(len(rows), 4)
                self.assertEqual(removed, baseline)

    @unittest.skip("Expanded-256 modes were removed from the public patcher")
    def test_expanded_composition_keeps_automatic_repairs_and_removes_cleanly(self) -> None:
        compatible = [
            "vv3_nature_honey_refill",
            "vv3_nature_level_three_alters_mortality",
            "vv3_rare_collectible_retry",
            "vv3_write_village_statistics",
        ]
        for mode, expected in EXPANDED_COMPOSITION_RESULTS.items():
            with self.subTest(mode=mode):
                rendered, applied = patcher.render_patched_bytes(
                    STOCK, self.build, mode, [*compatible, FEATURE_ID]
                )
                self.assertEqual(digest(rendered), expected[0])
                self.assertEqual(rendered[0x160:0x164].hex().upper(), expected[1])
                self.assertEqual(rendered[0x27A39:0x27A3D], bytes.fromhex("E4040000"))
                self.assertEqual(
                    len([
                        row for row in applied
                        if row.get("owner") == "automatic:vv3-expanded-detail-roster-layout"
                    ]),
                    151,
                )
                self.assertEqual(
                    len([
                        row for row in applied
                        if row.get("owner")
                        == "automatic:vv3-expanded-chief-candidate-assignment"
                    ]),
                    1,
                )
                parent, _ = patcher.render_patched_bytes(
                    STOCK, self.build, mode, compatible
                )
                removed = bytearray(rendered)
                patcher._remove_feature_bytes(removed, self.feature, mode)
                self.assertEqual(removed, parent)

    def test_stock_composition_with_complete_current_vv3_catalog_is_exact(self) -> None:
        selected = [
            item.id for item in patcher.load_fun_patches()
            if item.game_id == "vv3"
        ]
        self.assertNotIn("vv3_full_mastery_all_stage_a_candidate", selected)
        for mode, expected in STOCK_CATALOG_COMPOSITION_RESULTS.items():
            with self.subTest(mode=mode):
                rendered, _ = patcher.render_patched_bytes(
                    STOCK, self.build, mode, selected
                )
                self.assertEqual(digest(rendered), expected[0])
                self.assertEqual(rendered[0x160:0x164].hex().upper(), expected[1])
                parent, _ = patcher.render_patched_bytes(
                    STOCK,
                    self.build,
                    mode,
                    [item for item in selected if item != FEATURE_ID],
                )
                removed = bytearray(rendered)
                patcher._remove_feature_bytes(removed, self.feature, mode)
                self.assertEqual(removed, parent)

    def test_owned_ranges_do_not_collide_with_existing_manifests_or_repairs(self) -> None:
        owned = ((0x280, 0x284), (0x22B2A, 0x22B2E), (0xB4100, 0xB41EB))
        ranges: list[tuple[int, int, str]] = []

        def add(row: dict, owner: str) -> None:
            offset = int(row["offset"], 0)
            if "before" in row:
                length = len(bytes.fromhex(row["before"]))
            else:
                length = int(row["length"])
            ranges.append((offset, offset + length, owner))

        manifest = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
        for game in manifest["games"]:
            if game["id"] != "vv3":
                continue
            for row in game["safety_patches"]:
                add(row, "automatic:safety")
            for mode, variant in game["variants"].items():
                for row in variant["patches"]:
                    add(row, f"automatic:{mode}")
        for feature in patcher.load_fun_patches():
            if feature.game_id != "vv3" or feature.id == FEATURE_ID:
                continue
            for row in feature.patches:
                add(row, feature.id)
            for mode, rows in feature.raw.get("patch_mode_overrides", {}).items():
                for row in rows:
                    add(row, f"{feature.id}:{mode}")
        # expanded-256 rows are removed; nothing to collide with.
        for row in (
            patcher.VV3_EXPANDED_HEALER_ENDPOINT_REPAIR,
            *patcher.VV3_EXPANDED_CAPACITY_CORRECTIONS,
            patcher.VV3_EXPANDED_CHIEF_CANDIDATE_ASSIGNMENT_REPAIR,
            patcher.VV3_EXPANDED_DETAIL_ROSTER_CLASS_SIZE,
        ):
            add(row, "automatic:reviewed-repair")
        ranges.extend(
            (offset, offset + 4, "automatic:details")
            for offset, _before, _after in patcher.VV3_EXPANDED_DETAIL_ROSTER_DISPLACEMENTS
        )
        collisions = [
            (hex(start), hex(end), owner, hex(left), hex(right))
            for start, end, owner in ranges
            for left, right in owned
            if start < right and left < end
        ]
        self.assertEqual(collisions, [])

    def test_corrupt_owned_preimages_fail_without_touching_source(self) -> None:
        for offset, label in ((0x280, "section"), (0x22B2A, "hook"), (0xB4100, "cave")):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / STOCK.name
                data = bytearray(STOCK.read_bytes())
                data[offset] ^= 1
                path.write_bytes(data)
                before = path.read_bytes()
                with self.assertRaisesRegex(patcher.PatcherError, "Byte guard failed"):
                    patcher.render_patched_bytes(
                        path, self.build, "collection_progression", [FEATURE_ID]
                    )
                self.assertEqual(path.read_bytes(), before)

    def test_shr_section_is_actually_executable_in_the_real_render(self) -> None:
        """Regression test for a crash-causing bug found by an independent
        PE re-parse of the real rendered output: the 0x280 patch extends
        .shr's declared VirtualSize, but a section's VirtualSize has no
        effect on whether Windows will execute code from it -- that's
        controlled by the section's own Characteristics bit 0x20000000,
        which nothing patched. The 235-byte robe wrapper this feature
        writes to 0xB4100 lived in a page Windows would refuse to execute.
        This feature has no dependency on the Origins feature (which fixes
        .shr's permissions for other VV3 patches), so any player selecting
        only "Everyone Tries on Robe" would hit this. Verified against the
        actual rendered PE section table, not the patch manifest's claims.
        """
        try:
            import pefile
        except ImportError:
            self.skipTest("pefile not available")

        for mode in MODES:
            with self.subTest(mode=mode):
                rendered, _ = patcher.render_patched_bytes(
                    STOCK, self.build, mode, [FEATURE_ID]
                )
                pe = pefile.PE(data=bytes(rendered), fast_load=True)
                shr = next(s for s in pe.sections if s.Name.rstrip(b"\0") == b".shr")
                self.assertTrue(
                    bool(shr.Characteristics & 0x20000000),
                    ".shr is still not marked executable",
                )
                self.assertGreaterEqual(shr.Misc_VirtualSize, 0x1000)


if __name__ == "__main__":
    unittest.main()
