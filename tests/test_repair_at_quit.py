"""The cross-check's quit hook sits after the game's own quit save, before
anything is freed (native/shared/crosscheck_bridge.h).

The owner (2026-10-05): no repair prompt during gameplay; with "Check logs
automatically" on, the question comes when the game is closed, and only if
something is confirmed wrong.  Repair must then be able to complete there and
then, from the state the quit save just wrote.  That rests on where the hook
is, which this file proves from the five stock executables:

* WinMain creates the application object, runs it (vtable +0x18) and then
  shuts it down (vtable +0x14) before deleting it -- every clean quit goes
  through that shutdown;
* the shutdown saves the current slot -- read from the save manager at
  [application+4] + the slot field -- and then slot 0 (the settings), both
  through the save manager's vtable +0x38, and the hook's five bytes are
  the very next instruction(s): nothing runs between the quit save and the
  hook but the settings save;
* the instructions right after the hook start freeing the application's
  screens (a scalar deleting destructor, `push 1; call [vtable]`), so
  nothing is freed before it;
* the displaced bytes are position-independent and no branch anywhere in
  the executable lands inside them;
* the companions' save-time hooks take slots 1-5 only, so the settings save
  between the quit save and the hook runs none of them.

The header's own tables (VVFP_XC_QUIT, VVFP_XC_SLOT_FIELD) must be these.
tests/test_startup_loader.py proves the hook is written at game start in
every build that ships the Origins companion (and in none other) and that
its stub hands the game back every register and flag; native/shared/
crosscheck_bridge_harness.c tests what the hook does.
"""
from __future__ import annotations

import re
import struct
import sys
import unittest
from pathlib import Path

import capstone
import pefile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as vfp  # noqa: E402

STOCK = ROOT / "research" / "stock-executables"
GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")

# game: (application vtable, quit site, displaced bytes, slot field)
QUIT = {
    "vv1": (0x45965C, 0x41B25B, "8B4E0C85C9", 0xABE4),
    "vv2": (0x4768FC, 0x423C5B, "8B4E0C85C9", 0x30378),
    "vv3": (0x4808BC, 0x427331, "8B4E083BCF", 0x12F24),
    "vv4": (0x48D5DC, 0x41E4F1, "8B4E083BCF", 0x17114),
    "vv5": (0x498A94, 0x4239A1, "8B4E083BCF", 0x17D80),
}


def build_of(game: str):
    return next(b for b in vfp.load_builds() if b.id == game)


def stock_path(game: str) -> Path:
    return STOCK / build_of(game).input_name


STOCK_PRESENT = all(stock_path(g).is_file() for g in GAMES)


class Image:
    def __init__(self, game: str):
        self.pe = pefile.PE(str(stock_path(game)))
        self.base = self.pe.OPTIONAL_HEADER.ImageBase
        self.data = self.pe.get_memory_mapped_image()
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        self.md.detail = True

    def dword(self, va: int) -> int:
        return struct.unpack_from("<I", self.data, va - self.base)[0]

    def code(self, va: int, size: int) -> list:
        return list(self.md.disasm(bytes(self.data[va - self.base:va - self.base + size]), va))

    def text(self):
        return next(s for s in self.pe.sections if s.Name.startswith(b".text"))


def vcall_offset(body: list, k: int) -> int | None:
    """The vtable offset an indirect call at body[k] goes through: `call
    dword ptr [reg + off]`, or `call reg` after `mov reg, dword ptr [reg2 +
    off]` (a few instructions earlier); None for any other instruction."""
    ins = body[k]
    if ins.mnemonic != "call":
        return None
    m = re.fullmatch(r"dword ptr \[e[a-z]{2}(?: \+ (0x[0-9a-f]+))?\]", ins.op_str)
    if m:
        return int(m.group(1) or "0", 16)
    if re.fullmatch(r"e[a-z]{2}", ins.op_str):
        for previous in reversed(body[max(0, k - 4):k]):
            m = re.fullmatch(rf"{ins.op_str}, dword ptr \[e[a-z]{{2}}(?: \+ (0x[0-9a-f]+))?\]", previous.op_str)
            if previous.mnemonic == "mov" and m:
                return int(m.group(1) or "0", 16)
    return None


@unittest.skipUnless(STOCK_PRESENT, "the stock executables are not in this checkout (research/stock-executables)")
class TheQuitHookFollowsTheQuitSave(unittest.TestCase):

    def test_winmain_runs_then_shuts_down_the_application(self):
        for game in GAMES:
            with self.subTest(game=game):
                image = Image(game)
                winmain = vfp.STARTUP_LOADER_WINMAIN_CALL[game][1]
                body = image.code(winmain, 0x120)
                rets = [i for i, ins in enumerate(body) if ins.mnemonic == "ret"]
                body = body[:rets[1] + 1]      # the second-instance return, then the main one
                offsets = [o for o in (vcall_offset(body, k) for k in range(len(body))) if o is not None]
                # init (+0x10), run (+0x18), shut down (+0x14), delete ([vtable], push 1)
                self.assertEqual(offsets[-4:], [0x10, 0x18, 0x14, 0x00])
                # The object is the application: its constructor stores the vtable.
                ctor_call = next(ins for ins in body if ins.mnemonic == "call" and ins.op_str.startswith("0x")
                                 and any(i.op_str == "ecx, eax" for i in body[body.index(ins) - 1:body.index(ins)]))
                ctor = image.code(int(ctor_call.op_str, 16), 0x80)
                self.assertTrue(any(i.mnemonic == "mov" and i.op_str == f"dword ptr [esi], {QUIT[game][0]:#x}"
                                    for i in ctor), "the application's constructor stores its vtable")

    def test_the_hook_is_right_after_the_quit_save_and_before_anything_is_freed(self):
        for game in GAMES:
            with self.subTest(game=game):
                image = Image(game)
                vtable, site, stock, slot_field = QUIT[game]
                shutdown = image.dword(vtable + 0x14)
                body = image.code(shutdown, site - shutdown + 0x20)
                upto = [ins for ins in body if ins.address < site]
                saves = [k for k in range(len(upto)) if vcall_offset(upto, k) == 0x38]
                self.assertEqual(len(saves), 2, "the current slot's save, then the settings'")
                self.assertEqual(upto[-1].address, upto[saves[1]].address,
                                 "the hook is the very next instruction after the second save")
                first = upto[:saves[0]]
                self.assertTrue(any(re.fullmatch(rf"e[a-z]{{2}}, dword ptr \[ecx \+ {slot_field:#x}\]", i.op_str)
                                    for i in first if i.mnemonic == "mov"),
                                "the first save is of the slot in the save manager's current-slot field")
                self.assertTrue(all(i.op_str == "ecx, dword ptr [esi + 4]" for i in upto
                                    if i.mnemonic == "mov" and i.op_str.startswith("ecx, dword ptr [esi")),
                                "both saves are the save manager's, [application+4]")
                between = upto[saves[0] + 1:saves[1]]
                self.assertIn(between[-2].op_str if between[-1].mnemonic == "mov" else between[-1].op_str,
                              ("0", "edi"))
                if any(i.op_str == "edi" for i in between if i.mnemonic == "push"):
                    self.assertTrue(any(i.mnemonic == "xor" and i.op_str == "edi, edi" for i in upto),
                                    "slot 0: edi is zeroed")
                self.assertFalse(any(i.mnemonic == "call" for i in between),
                                 "nothing else is called between the two saves")
                after = [ins for ins in body if ins.address >= site]
                self.assertEqual(bytes(image.data[site - image.base:site - image.base + 5]).hex().upper(), stock)
                self.assertEqual(after[0].mnemonic, "mov")
                frees = after[:8]
                self.assertTrue(any(i.mnemonic == "push" and i.op_str == "1" for i in frees)
                                and any(i.mnemonic == "call" and re.fullmatch(r"dword ptr \[e[a-z]{2}\]|e[a-z]{2}",
                                                                              i.op_str) for i in frees),
                                "right after the hook the shutdown starts deleting (push 1; call [vtable])")

    def test_the_displaced_bytes_are_whole_instructions_nothing_branches_into(self):
        for game in GAMES:
            with self.subTest(game=game):
                image = Image(game)
                _vtable, site, stock, _field = QUIT[game]
                decoded = image.code(site, 5)
                self.assertEqual(sum(i.size for i in decoded[:2]), 5, "two whole instructions")
                for ins in decoded[:2]:
                    self.assertNotIn("eip", ins.op_str)
                    self.assertFalse(ins.group(capstone.CS_GRP_JUMP) or ins.group(capstone.CS_GRP_CALL))
                text = image.text()
                lo, hi = text.VirtualAddress, text.VirtualAddress + text.Misc_VirtualSize
                data = image.data
                inside = set(range(site + 1, site + 5))
                landing = []
                for i in range(lo, hi - 6):
                    op = data[i]
                    if op in (0xE8, 0xE9) and image.base + i + 5 + struct.unpack_from("<i", data, i + 1)[0] in inside:
                        landing.append(image.base + i)
                    if (op == 0x0F and 0x80 <= data[i + 1] <= 0x8F
                            and image.base + i + 6 + struct.unpack_from("<i", data, i + 2)[0] in inside):
                        landing.append(image.base + i)
                    if ((0x70 <= op <= 0x7F or op == 0xEB)
                            and image.base + i + 2 + struct.unpack_from("<b", data, i + 1)[0] in inside):
                        landing.append(image.base + i)
                # rel8 scanning over raw bytes finds false positives in data;
                # only a decoded branch counts.
                real = [va for va in landing
                        if (lambda d: d and (d[0].group(capstone.CS_GRP_JUMP) or d[0].group(capstone.CS_GRP_CALL))
                            and int(d[0].op_str, 16) in inside)(image.code(va, 8))]
                self.assertEqual(real, [])
                for k in range(1, 5):
                    self.assertEqual(bytes(data).find(struct.pack("<I", site + k)), -1, "no table entry either")

    def test_the_header_uses_these_sites_and_fields(self):
        header = (ROOT / "native" / "shared" / "crosscheck_bridge.h").read_text(encoding="utf-8")
        table = header[header.index("} VVFP_XC_QUIT[6] = {"):]
        table = table[:table.index("};")]
        rows = re.findall(r"\{ 0x([0-9A-F]+)u, \{ ((?:0x[0-9A-F]{2}(?:, )?){5}) \} \}", table)
        self.assertEqual(len(rows), 5)
        for game, (va, stock) in zip(GAMES, rows):
            self.assertEqual(int(va, 16), QUIT[game][1])
            self.assertEqual("".join(b[2:] for b in stock.split(", ")), QUIT[game][2])
        fields = re.search(r"VVFP_XC_SLOT_FIELD\[6\] = \{ 0, ([^}]+) \};", header).group(1)
        self.assertEqual([int(f.strip().rstrip("u"), 16) for f in fields.split(",")],
                         [QUIT[g][3] for g in GAMES])


class TheSettingsSaveRunsNoPatcherHook(unittest.TestCase):
    """Between the quit save and the hook only the settings save (slot 0)
    runs; every companion save hook takes slots 1-5 only."""

    def test_the_save_hooks_take_slots_one_to_five(self):
        roster = (ROOT / "native" / "vvfp_cause_of_death" / "cod_roster.inc").read_text(encoding="utf-8")
        saved = roster[roster.index("static void roster_saved("):]
        saved = saved[:saved.index("\n}\n")]
        self.assertIn("slot >= 1 && slot <= 5", saved)
        written = roster[roster.index("static void vv1_written("):]
        written = written[:written.index("\n}\n")]
        self.assertIn("slot >= 1 && slot <= 5", written)
        self.assertIn("== 0xABDCu", written)      # the village's write, not the 0xC0 profile
        stats = (ROOT / "native" / "statistics_export" / "statistics_export.c").read_text(encoding="utf-8")
        save = stats[stats.index("__declspec(dllexport) int __stdcall SaveVillageStatistics("):]
        save = save[:save.index("\n}\n")]
        self.assertIn("save_id >= 1 && save_id <= 5", save)


if __name__ == "__main__":
    unittest.main()
