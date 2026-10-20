from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TechScreenUpgradeCrashHotfixTests(unittest.TestCase):
    def test_all_five_base_builders_balance_loadlibrary_result_lookup(self) -> None:
        for game in range(1, 6):
            source = (ROOT / "scripts" / f"build_vv{game}_origins_feature.py").read_text(
                encoding="utf-8"
            )
            with self.subTest(game=game):
                if game == 5:
                    # New Believers' base payload no longer resolves any
                    # result export: the legacy Tech menu and dispatch helper
                    # that did were unreachable (Task9 owns the VV5 menus)
                    # and were removed.
                    self.assertNotIn("show_result_export", source)
                    continue
                if game == 3:
                    # VV3 centralizes result display in the show_result /
                    # village-wide trampolines instead of two literal
                    # `mov eax, show_result_export` sites.  The crash-safety
                    # invariant still holds: every result export is resolved
                    # via GetProcAddress (call [0x47C128]) and only then
                    # called, so LoadLibrary/lookup stays balanced.
                    self.assertIn("jmp show_result", source)
                    self.assertIn(
                        "push 0x{s['result_export']:X}\n"
                        "            push eax\n"
                        "            call dword ptr [0x47C128]",
                        source,
                    )
                    self.assertIn(
                        "push 0x{s['show_result_export']:X}\n"
                        "            push ebp\n"
                        "            call dword ptr [0x47C128]",
                        source,
                    )
                    self.assertNotIn(
                        "push 0x{s['show_result_export']:X}\n"
                        "            push 0x{s['icons_dll']:X}\n"
                        "            call",
                        source,
                    )
                    continue
                # VV1's village_wide dispatch now resolves the icons DLL
                # handle once for all of its Running/Mastery/Age18 result
                # branches (see village_wide's own comment in
                # build_vv1_origins_feature.py) instead of once per
                # branch, so it has one fewer of these vestigial
                # "mov eax, export"-before-LoadLibrary sites than the
                # other three games' (VV2/VV4/VV5) still-per-branch
                # pattern. VV1's own separate, untouched
                # VILLAGE_PREFLIGHT_VA signature check still has its own,
                # unrelated one, so it isn't 0. VV4's own village_wide
                # dispatch was independently consolidated the same way
                # (a single trampoline resolves the DLL handle once for
                # Running/Mastery/Age18 together, at build_vv4_origins_
                # feature.py's own "village_wide:" label), so it gets the
                # same single-site count.
                # VV2 lost its second site with the unreachable village-wide
                # preflight, which was the other one, and its last with the
                # Cure helper's rows 6-8 arm, which no row reached (#506
                # review): its village-wide rows report from the companion.
                expected = {1: 1, 2: 0, 4: 1}.get(game, 2)
                self.assertEqual(
                    source.count("mov eax, 0x{s['show_result_export']:X}"),
                    expected,
                )
                self.assertNotIn(
                    "push 0x{s['show_result_export']:X}\n"
                    "            push 0x{s['icons_dll']:X}\n"
                    "            call",
                    source,
                )

    def test_all_five_base_tech_menus_return_after_cure_result(self) -> None:
        for game in range(1, 6):
            source = (ROOT / "scripts" / f"build_vv{game}_origins_feature.py").read_text(
                encoding="utf-8"
            )
            with self.subTest(game=game):
                if game == 5:
                    # The VV5 cure row lived in the removed legacy Tech menu;
                    # Full Heal/Cure All is the Task9 page's.
                    self.assertNotIn("HEAL_CAVE_VA", source)
                    continue
                target = "menu_done"
                self.assertIn(
                    f"call 0x{{HEAL_CAVE_VA:X}}\n            jmp {target}",
                    source,
                )

    def test_vv1_shr_mapping_and_cure_dialog_abi_are_emitted(self) -> None:
        manifest = json.loads(
            (ROOT / "data" / "vv1_origins_feature.json").read_text(encoding="utf-8")
        )
        patches = {item["offset"]: item for item in manifest["patches"]}
        # The .shr+0x004 dispatch stub is gone: every caller calls the Cure
        # entry directly, so nothing ever reached it.
        self.assertNotIn("0x8B004", patches)
        self.assertEqual(patches["0x270"]["after"], "00100000")
        self.assertEqual(patches["0x28C"]["after"], "600000F0")
        source = (ROOT / "scripts" / "build_vv1_origins_feature.py").read_text(
            encoding="utf-8"
        )
        # Full Heal/Cure All Villagers has two distinct result paths now
        # instead of one hand-formatted "Cured %d villagers" message: a
        # plain fixed-text MessageBox when nothing needed curing (no
        # charge), and a resolved DLL export call with both counts when
        # something did (charge only just before that call).
        cure_all = source.split("cure_all:", 1)[1].split("cure_done:", 1)[0]
        no_change = cure_all.split("cure_check_result:", 1)[1].split(
            "cure_resolve:", 1
        )[0]
        self.assertIn(
            "push 0\n            push 0x{s['title']:X}\n            push eax\n"
            "            call 0x452DB6\n            add esp, 0x0C",
            no_change,
        )
        self.assertIn("s['cure_no_change']", no_change)
        resolve = cure_all.split("cure_resolve:", 1)[1]
        self.assertIn("s['show_cure_result']", resolve)
        self.assertIn("sub dword ptr [edi + 0xA2FC], 30000", resolve)

    def test_vv1_uses_state_for_tech_and_legacy_for_villager_details(self) -> None:
        source = (ROOT / "scripts" / "build_vv1_origins_feature.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            '"show_icon_dialog_state",\n        "ShowOriginsUpgradeMenuState",',
            source,
        )
        self.assertIn(
            '"show_icon_dialog_legacy", "ShowOriginsUpgradeMenu"',
            source,
        )
        self.assertIn("cmp dword ptr [esp + 0x0C], 0", source)
        resolver = source.split("        show_dialog,", 1)[1].split(
            "    put(\n        tech_increment", 1
        )[0]
        self.assertLess(
            resolver.index("cmp dword ptr [esp + 0x0C], 0"),
            resolver.index("or dword ptr [esp + 0x10], 0x20000"),
        )
        self.assertIn("jne icon_dialog_export_selected", resolver)
        self.assertNotIn("or edi, 0x1800", source)

    def test_vv1_barrel_uses_stock_scalar_deleting_destructor(self) -> None:
        """Regression test for a real reported crash (buying Barrel of
        Babies, then a crash on the next startup). 0x42AB60 is not a
        destructor for the sub_4286B0-constructed message object at all --
        confirmed by decompiling the stock binary with IDA -- it is an
        unrelated method on a different class/vtable that itself calls
        sub_42A6A0 (the destructor for a *different* constructor variant,
        sub_42D0E0) under a flag check. Calling it on a sub_4286B0 object
        walks the wrong vtable and frees fields at the wrong offsets,
        corrupting the heap; the corruption then surfaces later as an
        access violation in unrelated code. The correct match for
        sub_4286B0's own vtable (off_459AE4) is sub_427620, a plain
        thiscall taking no stack arguments.

        The helper's event comes from operator new (0x44AF03), so since
        v1.35.45 it is released through that SAME class's scalar deleting
        destructor, sub_427A00 -- vtable off_459AE4 slot 0 -- with flag 1:
        it runs sub_427620 and then returns the block to operator delete
        (0x44AEAE).  Calling sub_427620 alone leaked the 0x50F0 bytes.
        """
        source = (ROOT / "scripts" / "build_vv1_origins_feature.py").read_text(
            encoding="utf-8"
        )
        # Slice from where the helper's ASSEMBLY now begins, not from the
        # assemble() call: the body was split into a reusable prefix so the
        # disarm stub can measure the restore label's offset, and that moved
        # the assemble() call to after the destructor this test guards.
        helper = source.split("barrel_main_helper_source_prefix = f", 1)[1].split(
            "patch(\n        HEAL_CAVE_FILE_OFFSET", 1
        )[0]
        self.assertIn(
            "push 1\n            mov ecx, ebx\n            call 0x427A00",
            helper,
        )
        self.assertNotIn("call 0x427620", helper.split("barrel_main_helper_code = assemble", 1)[0])
        self.assertNotIn("call 0x42AB60", helper)
        self.assertNotIn("call 0x42A6A0", helper)

    def test_vv2_tech_helpers_resolve_the_certified_pool(self) -> None:
        source = (ROOT / "scripts" / "build_vv2_origins_feature.py").read_text(
            encoding="utf-8"
        )
        helper = source.split("cure_code = assemble(", 1)[1].split(
            "preflight_code = assemble(", 1
        )[0]
        # Cure walks the pool the game's own singleton getter returns. (The
        # rows 6-8 arm that also handed it to the village-wide payload as
        # `lea ecx, [eax + 0x52C]` could never run and was removed -- #506.)
        self.assertIn("call 0x44F4E0", helper)
        self.assertIn("call 0x44F4E0\n            test eax, eax\n            je cure_invalid_after_recheck\n"
                      "            mov edx, eax", helper)
        self.assertNotIn("[esi + 0x10]", helper)

    def test_vv5_statue_fault_sites_are_not_hooked_at_all(self) -> None:
        """The sites that needed a record adapter are no longer hooked.

        This guard used to require that the statue feature reach `0x6CC39`
        and `0x6CDED` through an adapter which materialises the villager
        pointer, because hooking them without one dispatched on a stale
        register and faulted.

        The feature no longer hooks them. Its scope is the completed statue
        only -- the one state where Polishing and Honoring are both genuinely
        available -- so the construction-state and upgradeable-statue
        dispatches keep the stock behaviour the game already selects by
        statue state. An unhooked site cannot read a villager pointer at all,
        which removes the fault rather than handling it.

        Asserting the absence is the stronger property, so this checks that no
        patch touches either offset AND that no remaining patch body contains
        the adapter's `mov ecx, [esi+0x1B88]`, which would mean a selector
        somewhere still wants a villager record.
        """
        builds = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
        feature = next(
            item
            for item in builds["fun_patches"]
            if item["id"] == "vv5_statue_polishing_or_honoring"
        )
        offsets = {item["offset"] for item in feature["patches"]}
        for site in ("0x6CC39", "0x6CDED", "0x6BF60", "0x796B3", "0x79726", "0x6C45D"):
            with self.subTest(site=site):
                self.assertNotIn(
                    site,
                    offsets,
                    f"{site} is decided by statue state in stock and must stay unhooked",
                )
        # The selector's body grew with the owner's 14% rule (2026-10-20: the
        # task continuation's pick is gated by the villager's own checkmark),
        # so 0x94840 is now only a jump to its body in the free code at
        # 0x94D30 -- the same selector, at a new address, not a new hook of
        # any game site.
        self.assertEqual(
            offsets,
            {"0x6BF9A", "0x796EB", "0x94460", "0x94840", "0x94D30"},
            "only the two completed-statue dispatches, the trampoline and the "
            "selector (entry and body) may be patched",
        )
        adapter = bytes.fromhex("8B8E881B0000")
        for item in feature["patches"]:
            with self.subTest(offset=item["offset"]):
                self.assertNotIn(
                    adapter,
                    bytes.fromhex(item["after"]),
                    "no patch may still materialise a villager pointer",
                )

    def test_vv5_statue_selector_preserves_ecx_across_the_random_call(self) -> None:
        """The selector must not leak the RNG's clobber of ECX to its caller.

        Both hooked sites replace a `push 0x9D` that sits between a load of
        ECX and a use of it, so ECX is live across the call the selector
        makes:

        * `0x6BF9A` is preceded by `mov ecx, [esi+0x1B88]`.
        * `0x796EB` is preceded by `mov ecx, [esp+0x10]`, and the very next
          stock instruction after the hook is `mov [ecx+0x1C54], 0x1A` --
          a *write* through ECX.

        The stock random function at `0x403660` destroys ECX: both of its
        paths call `0x47CFD8`, which runs `mov ecx, [eax+0x14]`,
        `imul ecx, ecx, 0x343FD`, `add ecx, 0x269EC3`. Without a save and
        restore the write above lands on the multiplied LCG state instead of
        the villager record. `docs/vv5-statue-training-research.md` records
        that exact defect reaching players once already, as a `0xC0000005`
        at `0x0046558A`.

        Dropping the skill reads removed the selector's *own* use of ECX but
        not the caller's, so this pins the surviving ABI requirement.
        """
        builds = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
        feature = next(
            item
            for item in builds["fun_patches"]
            if item["id"] == "vv5_statue_polishing_or_honoring"
        )
        selector = next(
            item for item in feature["patches"] if item["offset"] == "0x94840"
        )
        self.assertEqual(
            len(selector["after"]),
            len(selector["before"]),
            "the selector must not change the patch length",
        )
        # The selector's entry is a jump to its body (the 14% rule made the
        # body too long for 0x94840; see the test above).  Follow it: the
        # guarantee is about the code that runs, wherever it sits.
        import capstone

        cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        patches = {int(item["offset"], 16): bytes.fromhex(item["after"]) for item in feature["patches"]}
        entry = next(cs.disasm(patches[0x94840], 0x494840))
        self.assertEqual(entry.mnemonic, "jmp", "the selector's entry jumps to its body")
        target = int(entry.op_str, 16)
        self.assertIn(target - 0x400000, patches, "the body is one of this feature's own patches")
        code = list(cs.disasm(patches[target - 0x400000], target))
        randoms = [k for k, ins in enumerate(code) if ins.mnemonic == "call" and ins.op_str == "0x403660"]
        self.assertTrue(randoms, "the selector still draws its pick from the game's random function")
        for k in randoms:
            with self.subTest(call=hex(code[k].address)):
                # push ecx; push <n>; call rand; pop ecx (the argument); pop ecx (restored)
                self.assertEqual((code[k - 2].mnemonic, code[k - 2].op_str), ("push", "ecx"),
                                 "ECX must be pushed before the random call")
                self.assertEqual((code[k + 1].mnemonic, code[k + 1].op_str), ("pop", "ecx"))
                self.assertEqual((code[k + 2].mnemonic, code[k + 2].op_str), ("pop", "ecx"),
                                 "ECX must be popped right after the random call")
        pops = {k + 1 for k in randoms} | {k + 2 for k in randoms}
        for k, ins in enumerate(code):
            if k in pops:
                continue
            with self.subTest(instruction=f"{ins.address:#x} {ins.mnemonic} {ins.op_str}"):
                # Nothing else in the body may write ECX: the caller's ECX
                # (0x796EB writes through it next) reaches it unchanged.
                self.assertFalse(
                    ins.mnemonic in ("mov", "lea", "pop", "xor", "add", "sub", "imul", "xchg", "movzx", "inc", "dec")
                    and ins.op_str.split(",")[0].strip() in ("ecx", "cx", "cl", "ch"),
                    "only the saved ECX may be written back",
                )


if __name__ == "__main__":
    unittest.main()
