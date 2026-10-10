"""The save slot of a village made in the running session, and the causes of
death that depend on it.

Live (2026-10-10): in The Lost Children a tribe made with Change Tribe in
slot 2 lost the causes of three deaths recorded in its first session (the
Deaths log said "not recorded"), and that session's quit asked nothing about
its arrivals with no last name; in A New Home the first village of a fresh
save folder wrote its Cross-Check and Parentage Records files as "Save 5".
The companions knew the slot only from the executable's save-path stub,
which holds the last number the game built a "%s%d.ldw" path for: 5 after
A New Home reads slots 1..5 to list them, and slot + 20 after every
save-all (autosave, Change Tribe, a new tribe) in The Lost Children, The
Secret City and The Tree of Life. The game's own save manager holds the
slot it saves to (native/shared/game_save_slot.h); every host and A New
Home's parentage table now read that first. And A New Home's and The Lost
Children's graves file is written at every save to the slot saved, so the
causes never depend on the per-frame tick having a slot.

* native/vvfp_cause_of_death/save_slot_harness.c compiles the Cause of
  Death source in with the Documents folder redirected to a throwaway
  folder (never the real Documents\\LDW) and runs two sessions per game:
  the village is made in slot 2 after slot 1 was loaded, three die, the
  quit saves; the next session buries them and each grave shows its cause.
* The static checks pin the save manager's address and the slot's offset
  in each game's stock executable, where the research copies are present.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

try:
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs

    HAVE_CAPSTONE = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_CAPSTONE = False

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native"
HEADER = NATIVE / "shared" / "game_save_slot.h"
CL = Path(
    r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC"
    r"\14.51.36231\bin\Hostx64\x86\cl.exe"
)
STOCK = ROOT / "research" / "stock-executables"
EXES = {
    1: "Virtual Villagers - A New Home.exe",
    2: "Virtual Villagers - The Lost Children.exe",
    3: "Virtual Villagers - The Secret City.exe",
    4: "Virtual Villagers - The Tree of Life.exe",
    5: "Virtual Villagers - New Believers.exe",
}
MANAGER = {1: 0x48AEDC, 2: 0x4997BC, 3: 0x4B309C, 4: 0x4CB51C, 5: 0x4DACE0}
FIELD = {1: 0xABE4, 2: 0x30378, 3: 0x12F24, 4: 0x17114, 5: 0x17D80}
# The call of the save manager's constructor whose result is stored in the
# singleton, and an instruction that reads the slot to save it.
CONSTRUCTED_AT = {1: 0x41D53E, 2: 0x426D7E, 3: 0x428B9E, 4: 0x41FEB9, 5: 0x425999}
SLOT_READ = {
    1: (0x41B245, "mov", "edx, dword ptr [ecx + 0xabe4]"),        # the quit save: Save([+0xABE4])
    2: (0x423C45, "mov", "edx, dword ptr [ecx + 0x30378]"),       # the quit save
    3: (0x427DAF, "mov", "ecx, dword ptr [esi + 0x12f24]"),       # save-all: slot + 0x14 next
    4: (0x41E4D8, "mov", "edx, dword ptr [ecx + 0x17114]"),       # the quit save
    5: (0x424501, "lea", "eax, [esi + 0x17d80]"),                 # Save(0): the meta block from the slot field
}


class _Pe:
    def __init__(self, path: Path) -> None:
        import struct

        self.data = path.read_bytes()
        pe = struct.unpack_from("<I", self.data, 0x3C)[0]
        count = struct.unpack_from("<H", self.data, pe + 6)[0]
        optional = struct.unpack_from("<H", self.data, pe + 20)[0]
        base = struct.unpack_from("<I", self.data, pe + 24 + 28)[0]
        self.sections = []
        for i in range(count):
            h = pe + 24 + optional + 40 * i
            vsize, va, rsize, raw = struct.unpack_from("<IIII", self.data, h + 8)
            self.sections.append((base + va, max(vsize, rsize), raw))

    def at(self, va: int, size: int) -> bytes:
        for start, span, raw in self.sections:
            if start <= va < start + span:
                return self.data[raw + va - start: raw + va - start + size]
        raise ValueError(hex(va))

    def disasm(self, va: int, size: int):
        return list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(self.at(va, size), va))


@unittest.skipUnless(HAVE_CAPSTONE, "capstone is not installed")
class TheGamesOwnSlot(unittest.TestCase):
    def test_header_names_each_games_manager_and_field(self) -> None:
        text = HEADER.read_text(encoding="utf-8")
        managers = re.search(r"VV_GAME_SAVE_MANAGER\[6\] = \{\s*0, (.*?)\s*\};", text, re.S).group(1)
        self.assertEqual([int(v.rstrip("u"), 16) for v in managers.split(", ")],
                         [MANAGER[g] for g in range(1, 6)])
        fields = re.search(r"VV_GAME_SAVE_SLOT_FIELD\[6\] = \{ 0, (.*?) \};", text).group(1)
        self.assertEqual([int(v.rstrip("u"), 16) for v in fields.split(", ")], [FIELD[g] for g in range(1, 6)])

    def test_stock_executables_keep_the_slot_there(self) -> None:
        for game, name in EXES.items():
            path = STOCK / name
            if not path.is_file():
                continue
            with self.subTest(game=game):
                pe = _Pe(path)
                after = pe.disasm(CONSTRUCTED_AT[game], 0x20)
                self.assertEqual(after[0].mnemonic, "call")
                stores = [i for i in after[1:4] if i.mnemonic == "mov"
                          and i.op_str == f"dword ptr [{MANAGER[game]:#x}], eax"]
                self.assertTrue(stores, [f"{i.mnemonic} {i.op_str}" for i in after[:4]])
                va, mnemonic, operands = SLOT_READ[game]
                ins = pe.disasm(va, 0x10)[0]
                self.assertEqual((ins.mnemonic, ins.op_str), (mnemonic, operands))

    def test_save_all_saves_the_backup_generation_last(self) -> None:
        # Why the stub's number is not the slot: Save(slot), then Save(slot + 20).
        for game, va in ((2, 0x424C1F), (3, 0x427DAF), (4, 0x41F18A)):
            path = STOCK / EXES[game]
            if not path.is_file():
                continue
            with self.subTest(game=game):
                listing = [f"{i.mnemonic} {i.op_str}" for i in _Pe(path).disasm(va, 0x14)]
                self.assertTrue(any(line.endswith(", 0x14") and line.startswith("add") for line in listing),
                                listing)


class HostsAndTablesUseIt(unittest.TestCase):
    def test_every_host_answers_the_games_own_slot_first(self) -> None:
        hosts = {
            1: ("vv1_origins_icons/vv1_origins_icons.c", "vv_current_save_slot(1, vv1_mask_current_slot())"),
            2: ("vv2_origins_icons/vv2_origins_icons.c", "vv_current_save_slot(2, VV2_MASK_SLOT)"),
            3: ("vv3_full_mastery_candidate/vv3_full_mastery_candidate.c",
                "vv_current_save_slot(3, vv3_mask_captured_slot())"),
            4: ("vv4_origins_icons/vv4_origins_icons.c", "vv_current_save_slot(4, vv_captured_save_slot())"),
            5: ("vv5_task9_origins/vv5_task9_origins.c",
                "vv_current_save_slot(5, *(volatile int *)VV5_SLOT_SCRATCH)"),
        }
        for game, (relative, call) in hosts.items():
            with self.subTest(game=game):
                source = (NATIVE / relative).read_text(encoding="utf-8")
                body = source.split(f"static int __stdcall vv{game}_story_slot(void) {{", 1)[1].split("\n}", 1)[0]
                self.assertIn(call, body)

    def test_a_new_homes_parentage_table_follows_the_games_slot(self) -> None:
        source = (NATIVE / "vv1_parentage" / "vv1_parentage.c").read_text(encoding="utf-8")
        body = source.split("static int vv1_slot(void) {", 1)[1].split("}", 1)[0]
        self.assertIn("vv_current_save_slot(1,", body)

    def test_the_graves_file_is_written_at_every_save(self) -> None:
        roster = (NATIVE / "vvfp_cause_of_death" / "cod_roster.inc").read_text(encoding="utf-8")
        done = roster.split("static void cod_save_done(int slot, const void *save_buffer) {", 1)[1]
        done = done.split("\n}\n", 1)[0]
        self.assertLess(done.index("vv12_saved(slot);"), done.index("backfill_at_save(slot, save_buffer);"))
        self.assertIn("saved_slot = slot;", done)
        main = (NATIVE / "vvfp_cause_of_death" / "vvfp_cause_of_death.c").read_text(encoding="utf-8")
        self.assertIn("return slot >= 1 && slot <= 5 ? slot : saved_slot;", main)


@unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
class CausesSurviveTheSaveAndAReload(unittest.TestCase):
    def test_harness(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vvfp_cause_slot_docs_") as docs:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                 str(ROOT / "scripts" / "build_cause_save_slot_harness.ps1"), "-Docs", docs],
                capture_output=True, text=True, timeout=600,
            )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertNotIn("FAIL", output)
        self.assertEqual(output.count("all passed"), 8, output)


if __name__ == "__main__":
    unittest.main()
