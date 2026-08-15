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
                self.assertEqual(
                    source.count("mov eax, 0x{s['show_result_export']:X}"),
                    2,
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
                target = "done" if game == 5 else "menu_done"
                self.assertIn(
                    f"call 0x{{HEAL_CAVE_VA:X}}\n            jmp {target}",
                    source,
                )

    def test_vv1_shr_mapping_and_cure_dialog_abi_are_emitted(self) -> None:
        manifest = json.loads(
            (ROOT / "data" / "vv1_origins_feature.json").read_text(encoding="utf-8")
        )
        patches = {item["offset"]: item for item in manifest["patches"]}
        self.assertEqual(patches["0x8B004"]["after"], "E927050000")
        self.assertEqual(patches["0x270"]["after"], "00100000")
        self.assertEqual(patches["0x28C"]["after"], "600000F0")
        source = (ROOT / "scripts" / "build_vv1_origins_feature.py").read_text(
            encoding="utf-8"
        )
        cure_result = source.split("cure_suffix:", 1)[1].split("add esp, 40", 1)[0]
        self.assertIn(
            "push 0\n            push 0x{s['title']:X}\n            push eax\n"
            "            call 0x452DB6\n            add esp, 0x0C",
            cure_result,
        )

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
        """
        source = (ROOT / "scripts" / "build_vv1_origins_feature.py").read_text(
            encoding="utf-8"
        )
        helper = source.split("barrel_main_helper_code = assemble(", 1)[1].split(
            "patch(\n        HEAL_CAVE_FILE_OFFSET", 1
        )[0]
        self.assertIn(
            "mov ecx, ebx\n            call 0x427620",
            helper,
        )
        self.assertNotIn("call 0x42AB60", helper)
        self.assertNotIn("call 0x42A6A0", helper)

    def test_vv2_tech_helpers_resolve_the_certified_pool(self) -> None:
        source = (ROOT / "scripts" / "build_vv2_origins_feature.py").read_text(
            encoding="utf-8"
        )
        helper = source.split("cure_code = assemble(", 1)[1].split(
            "preflight_code = assemble(", 1
        )[0]
        self.assertIn("call 0x44F4E0", helper)
        self.assertIn("lea ecx, [eax + 0x52C]", helper)
        self.assertNotIn("[esi + 0x10]", helper)

    def test_vv5_statue_fault_sites_use_record_adapters(self) -> None:
        builds = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
        feature = next(
            item
            for item in builds["fun_patches"]
            if item["id"] == "vv5_statue_polishing_or_honoring"
        )
        patches = {item["offset"]: item for item in feature["patches"]}
        self.assertEqual(patches["0x6CC39"]["after"], "E827780200")
        self.assertEqual(patches["0x6CDED"]["after"], "E8BA760200")
        trampoline = bytes.fromhex(patches["0x94460"]["after"])
        self.assertEqual(trampoline[5:16], bytes.fromhex("8B8E881B0000E9D0020000"))
        self.assertEqual(trampoline[0x4C:0x57], bytes.fromhex("8B8E881B0000E989030000"))
        confused = bytes.fromhex(patches["0x947B0"]["after"])
        self.assertIn(bytes.fromhex("6BC081051F0000000FB6C0"), confused)


if __name__ == "__main__":
    unittest.main()
