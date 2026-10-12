"""The Secret City's Clear All Skill Preferences and Check Highest Skill rows.

The owner, 2026-10-11: "add an option to uncheck all skill preferences too!
... Should cost half the equal division of labor cost", then two Check
Highest Skill rows (Includes Parenting / No Parenting) priced like the
matching Equal Division row.

Tech-screen rows 14, 15 and 16 (buttons 1014, 1015, 1016).  The executable's
payload routes rows only up to 13, so the companion runs these three itself:
show_upgrade_menu catches the confirmed row, calls the export and hands the
executable -1 (close the menu), as it does after Equal Division of Labor.

Besides the source/resource pins, the exports are RUN: the built companion is
mapped into unicorn with every Windows import stubbed, a fake villager table
is laid out where the executable keeps it (manager pointer at 0x4279B4,
records at +0x14, stride 0x1F8C, slot bound at 0x42883A, tech pool at
0x582644), and the test reads back each villager's preference (+0xEC0), the
tech pool and the message the player sees.
"""
from __future__ import annotations

import re
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native" / "vv3_full_mastery_candidate"
DLL_C = NATIVE / "vv3_full_mastery_candidate.c"
DLL_DEF = NATIVE / "vv3_full_mastery_candidate.def"
DLL_RC = NATIVE / "vv3_full_mastery_candidate.rc"
DLL = ROOT / "data" / "candidates" / "VVFP VV3 Safe Upgrades.dll"
CANONICAL = ROOT / "data" / "candidates" / "VVFP VV3 Full Mastery Candidate.dll"
MANIFEST = ROOT / "data" / "vv3_origins_feature.json"

MANAGER_IMM = 0x4279B4
SLOT_BOUND = 0x42883A
TECH = 0x582644
MANAGER = 0x01000000
STRIDE = 0x1F8C
ACTIVE, CHIEF, GENDER, PREF, SKILL0 = 0xF10, 0xE80, 0xDC8, 0xEC0, 0xEAC
FARMING, PARENTING, HEALING, RESEARCH, BUILDING = 0, 1, 2, 3, 4


class SourceAndResourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.c = DLL_C.read_text(encoding="utf-8")
        self.rc = DLL_RC.read_text(encoding="utf-8")
        self.deff = DLL_DEF.read_text(encoding="utf-8")

    def test_rows_are_in_the_tech_dialog_with_their_prices(self) -> None:
        tech = self.rc[self.rc.index("201 DIALOGEX"): self.rc.index("202 DIALOGEX")]
        for label, cost, control in (
            ("Clear All Skill Preferences", "500,000 tech points", 1014),
            ("Check Highest Skill (Includes Parenting)", "1,000,000 tech points", 1015),
            ("Check Highest Skill (No Parenting)", "1,000,000 tech points", 1016),
        ):
            with self.subTest(label=label):
                self.assertRegex(
                    tech,
                    rf'LTEXT\s+"{re.escape(label)}"[^\n]*\n\s*LTEXT\s+"{cost}"'
                    rf'[^\n]*\n\s*PUSHBUTTON\s+"Buy", {control},',
                )
        self.assertIn("ID_BUY_LAST = 1016", self.c)
        # The confirm prompt names each upgrade and its price.
        self.assertIn('"Clear All Skill Preferences",\n    "Check Highest Skill '
                      '(Includes Parenting)",\n    "Check Highest Skill (No Parenting)"',
                      self.c)
        self.assertIn('"1,000,000", "1,000,000", "450,000", "500,000", "1,000,000", '
                      '"1,000,000"', self.c)
        # Rows 15/16 sit below Clear All, which sits below the Equal Division rows.
        def y(control: int) -> int:
            return int(re.search(rf'"Buy", {control}, \d+, (\d+)', tech).group(1))
        self.assertLess(y(1012), y(1014))
        self.assertLess(y(1014), y(1015))
        self.assertLess(y(1015), y(1016))
        # Change Appearance for All (still control 1013) is drawn last.
        self.assertLess(y(1016), y(1013))

    def test_exports_and_dll_side_routing(self) -> None:
        self.assertIn("ClearAllSkillPreferences=_ClearAllSkillPreferences@0", self.deff)
        self.assertIn("CheckHighestSkill=_CheckHighestSkill@4", self.deff)
        show = self.c[self.c.index("static int show_upgrade_menu"):]
        show = show[: show.index("\n}\n")]
        self.assertIn("result == VV3_ROW_CLEAR_PREFS", show)
        self.assertIn("ClearAllSkillPreferences();", show)
        self.assertIn("CheckHighestSkill(result == VV3_ROW_HIGHEST_PARENTING);", show)
        self.assertIn("result = -1;", show)
        self.assertIn("#define VV3_ROW_CLEAR_PREFS         14", self.c)
        self.assertIn("#define VV3_ROW_HIGHEST_PARENTING   15", self.c)
        self.assertIn("#define VV3_ROW_HIGHEST_NO_PARENTING 16", self.c)

    def test_prices_go_through_the_story_price(self) -> None:
        self.assertIn("#define CSP_COST       500000", self.c)
        self.assertIn("#define CHS_COST       1000000", self.c)
        self.assertEqual(self.c.count("vvfp_story_price(3, CSP_COST)"), 2)
        self.assertEqual(self.c.count("vvfp_story_price(3, CHS_COST)"), 2)

    def test_built_companion_is_current_and_deployed(self) -> None:
        import hashlib
        import json
        data = DLL.read_bytes()
        self.assertEqual(data, CANONICAL.read_bytes())
        for name in (b"ClearAllSkillPreferences\0", b"CheckHighestSkill\0"):
            self.assertIn(name, data)
        for label in ("Clear All Skill Preferences",
                      "Check Highest Skill (Includes Parenting)",
                      "Check Highest Skill (No Parenting)"):
            self.assertIn(label.encode("utf-16le"), data)
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        row = [r for r in manifest["companion_files"] if r["source"].endswith("Safe Upgrades.dll")][0]
        self.assertEqual(row["sha256"], hashlib.sha256(data).hexdigest().upper())
        self.assertIn("Clear All Skill Preferences (500,000 tech points)", manifest["description"])
        self.assertIn("Check Highest Skill (Includes Parenting) / (No Parenting)",
                      manifest["description"])


# ---------------------------------------------------------------- emulation

class _Emulator:
    API_BASE = 0x0E000000
    STACK = 0x0F000000
    RETURN = 0x0D000000
    STORY = 0x70000000

    def __init__(self, free: bool = False) -> None:
        import pefile
        from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
        from unicorn.x86_const import UC_X86_REG_ESP

        self.free = free
        self.messages: list[str] = []
        self.api_calls: list[str] = []
        self.mu = mu = Uc(UC_ARCH_X86, UC_MODE_32)
        pe = pefile.PE(data=DLL.read_bytes())
        self.base = base = pe.OPTIONAL_HEADER.ImageBase
        mu.mem_map(base, (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF)
        mu.mem_write(base, pe.header)
        for section in pe.sections:
            mu.mem_write(base + section.VirtualAddress, section.get_data())
        self.stubs: dict[int, str] = {}
        address = self.API_BASE
        mu.mem_map(self.API_BASE, 0x100000)
        for entry in pe.DIRECTORY_ENTRY_IMPORT:
            for imp in entry.imports:
                name = imp.name.decode() if imp.name else f"#{imp.ordinal}"
                self.stubs[address] = name
                mu.mem_write(imp.address, struct.pack("<I", address))
                address += 16
        self.exports = {
            e.name.decode(): base + e.address
            for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name
        }
        # The story companion, when "shipped": every export answers 1.
        self.story_stubs: dict[int, str] = {}
        mu.mem_map(self.STORY, 0x10000)
        mu.mem_map(self.RETURN, 0x1000)
        mu.mem_map(self.STACK - 0x100000, 0x100000)
        mu.mem_map(0x00400000, 0x00200000)        # the executable's globals
        mu.mem_map(MANAGER, 0x00400000)
        mu.mem_map(0x20000000, 0x00100000)        # scratch for API answers
        mu.reg_write(UC_X86_REG_ESP, self.STACK - 0x1000)
        mu.hook_add(UC_HOOK_CODE, self._hook, begin=self.API_BASE,
                    end=self.API_BASE + 0x100000)
        mu.hook_add(UC_HOOK_CODE, self._story_hook, begin=self.STORY,
                    end=self.STORY + 0x10000)

    # -- memory helpers
    def u32(self, va: int) -> int:
        return struct.unpack("<I", self.mu.mem_read(va, 4))[0]

    def i32(self, va: int) -> int:
        return struct.unpack("<i", self.mu.mem_read(va, 4))[0]

    def put(self, va: int, value: int) -> None:
        self.mu.mem_write(va, struct.pack("<i" if value < 0 else "<I", value))

    def cstr(self, va: int) -> bytes:
        out = bytearray()
        while True:
            chunk = bytes(self.mu.mem_read(va + len(out), 64))
            end = chunk.find(b"\0")
            if end >= 0:
                return bytes(out + chunk[:end])
            out += chunk

    def _arg(self, n: int) -> int:
        from unicorn.x86_const import UC_X86_REG_ESP
        return self.u32(self.mu.reg_read(UC_X86_REG_ESP) + 4 + 4 * n)

    def _return(self, value: int, pops: int) -> None:
        from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EIP, UC_X86_REG_ESP
        esp = self.mu.reg_read(UC_X86_REG_ESP)
        ret = self.u32(esp)
        self.mu.reg_write(UC_X86_REG_EAX, value & 0xFFFFFFFF)
        self.mu.reg_write(UC_X86_REG_ESP, esp + 4 + 4 * pops)
        self.mu.reg_write(UC_X86_REG_EIP, ret)

    def _wsprintf(self) -> int:
        out_va, fmt = self._arg(0), self.cstr(self._arg(1)).decode("latin-1")
        n = 2
        out = []
        i = 0
        while i < len(fmt):
            if fmt[i] == "%":
                i += 1
                while fmt[i] in "0123456789-l":
                    i += 1
                spec = fmt[i]
                if spec == "%":
                    out.append("%")
                elif spec == "s":
                    out.append(self.cstr(self._arg(n)).decode("latin-1")); n += 1
                elif spec == "u":
                    out.append(str(self._arg(n))); n += 1
                elif spec == "d":
                    out.append(str(struct.unpack("<i", struct.pack("<I", self._arg(n)))[0])); n += 1
                else:
                    raise AssertionError(f"unsupported wsprintfA conversion %{spec}")
            else:
                out.append(fmt[i])
            i += 1
        text = "".join(out).encode("latin-1")
        self.mu.mem_write(out_va, text + b"\0")
        return len(text)

    def _hook(self, mu, address, size, user_data) -> None:
        name = self.stubs.get(address)
        if name is None:
            return
        self.api_calls.append(name)
        if name == "MessageBoxA":
            self.messages.append(self.cstr(self._arg(1)).decode("latin-1"))
            self._return(1, 4)
        elif name == "GetForegroundWindow":
            self._return(0x1234, 0)
        elif name == "wsprintfA":
            self._return(self._wsprintf(), 0)          # cdecl
        elif name == "lstrcatA":
            dst, src = self._arg(0), self._arg(1)
            mu.mem_write(dst, self.cstr(dst) + self.cstr(src) + b"\0")
            self._return(dst, 2)
        elif name == "lstrcpyA":
            dst, src = self._arg(0), self._arg(1)
            mu.mem_write(dst, self.cstr(src) + b"\0")
            self._return(dst, 2)
        elif name == "lstrlenA":
            self._return(len(self.cstr(self._arg(0))), 1)
        elif name in ("GetModuleFileNameW", "GetModuleFileNameA"):
            path = "C:\\Games\\Village\\Game.exe"
            wide = name.endswith("W")
            data = (path.encode("utf-16le") + b"\0\0") if wide else (path.encode() + b"\0")
            mu.mem_write(self._arg(1), data)
            self._return(len(path), 3)
        elif name in ("LoadLibraryW", "LoadLibraryA", "LoadLibraryExW", "LoadLibraryExA"):
            pops = 3 if "Ex" in name else 1
            self._return(self.STORY if self.free else 0, pops)
        elif name in ("GetModuleHandleW", "GetModuleHandleA"):
            self._return(0, 1)
        elif name in ("GetFileAttributesW", "GetFileAttributesA"):
            self._return(0xFFFFFFFF if not self.free else 0x80, 1)
        elif name == "GetProcAddress":
            proc = self.cstr(self._arg(1)).decode()
            stub = self.STORY + 0x10 * (len(self.story_stubs) + 1)
            self.story_stubs[stub] = proc
            self._return(stub, 2)
        elif name in ("GetLastError", "SetLastError"):
            self._return(0, 1 if name == "SetLastError" else 0)
        else:
            raise AssertionError(f"unexpected Windows call {name}")

    def _story_hook(self, mu, address, size, user_data) -> None:
        proc = self.story_stubs.get(address)
        if proc is None:
            return
        self.api_calls.append("story:" + proc)
        # every story export is stdcall(int game[, ...]); answer 1
        pops = 2 if proc in ("VvfpStoryAttachHost", "VvfpStoryPickIslandEvent",
                             "VvfpStoryCustomIslandEvent", "VvfpStoryChooseTimeSkip") else 1
        self._return(1, pops)

    # -- the village
    def village(self, villagers: list[dict], tech: int, bound: int = 150) -> None:
        self.put(MANAGER_IMM, MANAGER)
        self.put(SLOT_BOUND, bound)
        self.put(TECH, tech)
        for index, v in enumerate(villagers):
            rec = MANAGER + 0x14 + index * STRIDE
            self.mu.mem_write(rec + ACTIVE, bytes([1]))
            self.mu.mem_write(rec + CHIEF, bytes([1 if v.get("chief") else 0]))
            self.mu.mem_write(rec + GENDER, bytes([1 if v.get("female") else 0]))
            self.put(rec + PREF, v.get("pref", -1))
            for k, value in enumerate(v.get("skills", (0, 0, 0, 0, 0))):
                self.put(rec + SKILL0 + 4 * k, value)

    def prefs(self, count: int) -> list[int]:
        return [self.i32(MANAGER + 0x14 + i * STRIDE + PREF) for i in range(count)]

    def call(self, export: str, *args: int) -> int:
        from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ESP
        esp = self.STACK - 0x1000 - 4 * (len(args) + 1)
        self.mu.mem_write(esp, struct.pack(f"<{len(args) + 1}I", self.RETURN, *args))
        self.mu.reg_write(UC_X86_REG_ESP, esp)
        self.mu.emu_start(self.exports[export], self.RETURN, count=5_000_000)
        self.assertEqual_esp = self.mu.reg_read(UC_X86_REG_ESP)
        return struct.unpack("<i", struct.pack("<I", self.mu.reg_read(UC_X86_REG_EAX)))[0]


def _has_unicorn() -> bool:
    try:
        import pefile  # noqa: F401
        import unicorn  # noqa: F401
    except ImportError:
        return False
    return DLL.is_file()


@unittest.skipUnless(_has_unicorn(), "unicorn/pefile or the built companion is missing")
class ClearAllSkillPreferencesRuns(unittest.TestCase):
    VILLAGE = [
        {"pref": FARMING},
        {"pref": -1},
        {"pref": BUILDING, "female": True},
        {"chief": True, "pref": RESEARCH},
        {"pref": PARENTING},
    ]

    def test_clears_every_preference_but_the_chief_and_charges_500000(self) -> None:
        emu = _Emulator()
        emu.village(self.VILLAGE, tech=2_000_000, bound=5)
        self.assertEqual(emu.call("ClearAllSkillPreferences"), 3)
        self.assertEqual(emu.prefs(5), [-1, -1, -1, RESEARCH, -1])
        self.assertEqual(emu.i32(TECH), 1_500_000)
        self.assertEqual(emu.messages, [
            "Cleared 3 Villagers' Skill Preferences.\r\n\r\n"
            "Skipped 1 Villager: is Tribal Chief."
        ])

    def test_singular_possessive(self) -> None:
        emu = _Emulator()
        emu.village([{"pref": HEALING}, {"pref": -1}], tech=500_000, bound=2)
        self.assertEqual(emu.call("ClearAllSkillPreferences"), 1)
        self.assertEqual(emu.i32(TECH), 0)
        self.assertTrue(emu.messages[0].startswith("Cleared 1 Villager's Skill Preferences."))
        self.assertIn("Skipped 0 Villagers: is Tribal Chief.", emu.messages[0])

    def test_nothing_to_clear_charges_nothing(self) -> None:
        emu = _Emulator()
        emu.village([{"pref": -1}, {"pref": -1}, {"chief": True, "pref": 2}],
                    tech=900_000, bound=3)
        self.assertEqual(emu.call("ClearAllSkillPreferences"), 0)
        self.assertEqual(emu.i32(TECH), 900_000)
        self.assertEqual(emu.prefs(3), [-1, -1, 2])
        self.assertEqual(emu.messages, [
            "Every villager's skill preference is already cleared. "
            "No tech points have been deducted."
        ])

    def test_not_enough_tech_points(self) -> None:
        emu = _Emulator()
        emu.village([{"pref": FARMING}], tech=499_999, bound=1)
        self.assertEqual(emu.call("ClearAllSkillPreferences"), 0)
        self.assertEqual(emu.i32(TECH), 499_999)
        self.assertEqual(emu.prefs(1), [FARMING])
        self.assertEqual(emu.messages, ["Not enough tech points."])

    def test_nobody_eligible(self) -> None:
        emu = _Emulator()
        emu.village([{"chief": True, "pref": 0}], tech=900_000, bound=1)
        self.assertEqual(emu.call("ClearAllSkillPreferences"), 0)
        self.assertEqual(emu.i32(TECH), 900_000)
        self.assertEqual(emu.messages, [
            "No villagers were eligible. No tech points have been deducted."
        ])

    def test_free_upgrades_cost_nothing(self) -> None:
        emu = _Emulator(free=True)
        emu.village([{"pref": FARMING}], tech=0, bound=1)
        self.assertEqual(emu.call("ClearAllSkillPreferences"), 1)
        self.assertEqual(emu.prefs(1), [-1])
        self.assertEqual(emu.i32(TECH), 0)
        self.assertIn("story:VvfpStoryActive", emu.api_calls)


@unittest.skipUnless(_has_unicorn(), "unicorn/pefile or the built companion is missing")
class CheckHighestSkillRuns(unittest.TestCase):
    def _village(self):
        # skills are indexed by the preference value: F, P, H, R, B
        return [
            {"skills": (10, 90, 20, 30, 40), "pref": -1},              # P (incl) / B (no)
            {"skills": (50, 0, 50, 50, 50), "pref": HEALING, "female": True},  # tie -> Farming
            {"skills": (0, 0, 0, 0, 0), "pref": RESEARCH},              # no progress
            {"skills": (0, 0, 0, 70, 70), "pref": -1, "female": True},  # tie B/R -> Building
            {"skills": (99, 99, 99, 99, 99), "chief": True, "pref": -1},
            {"skills": (5, 0, 80, 0, 0), "pref": HEALING},              # already
        ]

    def test_includes_parenting(self) -> None:
        emu = _Emulator()
        emu.village(self._village(), tech=3_000_000, bound=6)
        # Every villager given their highest skill is counted, including one
        # who already had it checked -- as the other four games count.
        self.assertEqual(emu.call("CheckHighestSkill", 1), 4)
        self.assertEqual(emu.prefs(6),
                         [PARENTING, FARMING, RESEARCH, BUILDING, -1, HEALING])
        self.assertEqual(emu.i32(TECH), 2_000_000)
        self.assertEqual(emu.messages, [
            "Set 4 Villagers' Job Preferences."
            "\r\n\r\nFarming: 1 Villager (0 Male, 1 Female)."
            "\r\n\r\nBuilding: 1 Villager (0 Male, 1 Female)."
            "\r\n\r\nResearch: 0 Villagers (0 Male, 0 Female)."
            "\r\n\r\nHealing: 1 Villager (1 Male, 0 Female)."
            "\r\n\r\nBreeding: 1 Villager (1 Male, 0 Female)."
            "\r\n\r\nSkipped 1 Villager: no skill progress yet."
            "\r\n\r\nSkipped 1 Villager: is Tribal Chief."
        ])

    def test_no_parenting_ignores_parenting(self) -> None:
        emu = _Emulator()
        emu.village(self._village(), tech=1_000_000, bound=6)
        self.assertEqual(emu.call("CheckHighestSkill", 0), 4)
        self.assertEqual(emu.prefs(6),
                         [BUILDING, FARMING, RESEARCH, BUILDING, -1, HEALING])
        self.assertEqual(emu.i32(TECH), 0)
        self.assertNotIn("Breeding:", emu.messages[0])
        self.assertIn("Building: 2 Villagers (1 Male, 1 Female).", emu.messages[0])

    def test_only_parenting_progress_counts_as_none_without_parenting(self) -> None:
        emu = _Emulator()
        emu.village([{"skills": (0, 60, 0, 0, 0), "pref": -1}], tech=5_000_000, bound=1)
        self.assertEqual(emu.call("CheckHighestSkill", 0), 0)
        self.assertEqual(emu.prefs(1), [-1])
        self.assertEqual(emu.i32(TECH), 5_000_000)
        self.assertEqual(emu.messages, [
            "Every villager already has their highest skill checked. "
            "No tech points have been deducted."
        ])

    def test_not_enough_tech_points(self) -> None:
        emu = _Emulator()
        emu.village(self._village(), tech=999_999, bound=6)
        self.assertEqual(emu.call("CheckHighestSkill", 1), 0)
        self.assertEqual(emu.i32(TECH), 999_999)
        self.assertEqual(emu.prefs(6), [-1, HEALING, RESEARCH, -1, -1, HEALING])
        self.assertEqual(emu.messages, ["Not enough tech points."])

    def test_free_upgrades_cost_nothing(self) -> None:
        emu = _Emulator(free=True)
        emu.village(self._village(), tech=7, bound=6)
        self.assertEqual(emu.call("CheckHighestSkill", 1), 4)
        self.assertEqual(emu.i32(TECH), 7)


if __name__ == "__main__":
    unittest.main()
