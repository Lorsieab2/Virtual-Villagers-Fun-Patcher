"""Harder Fishing Unlock in VV4 (The Tree of Life): no cloth below Science 3, no fixing the piers below Construction 3.
The traces are in scripts/build_vv4_harder_fishing_unlock_feature.py.

Run stock and patched in unicorn on the stock exe:
  * the vines' drop handler 0x436D40 (its first case) at Science 1, 2 and 3 with the Clothing Hut finished and
    unfinished; the action it starts (0x45DEC0's first argument) is recorded: 0x1A with the refusal string 0x249, or
    0x7A, cutting the pulpy vines;
  * the Fishing Nets drop handler 0x433440 (case 0), the Building dispatcher's pier test 0x463DD8 and the task-30
    continuation 0x46384D at Construction 1, 2 and 3 with the piers unfixed, part-done and fixed (and the nets under
    way), the Clothing Hut finished and unfinished and project 11 finished and unfinished; the action started, its
    data, the villager's task, whether "Fixing the piers" is listed, and whether the task resumes are recorded, and no
    run may write the piers' object.
"""
from __future__ import annotations

import itertools
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402
import vv_fun_patcher_gui as gui  # noqa: E402

try:
    import pefile
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UC_MODE_32, Uc
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EIP, UC_X86_REG_ESP
    HAVE = True
except ImportError:  # pragma: no cover
    HAVE = False

ID = "vv4_harder_fishing_unlock"
EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Tree of Life.exe"
FEATURE = json.loads((ROOT / "data" / "vv4_harder_fishing_unlock_feature.json").read_text("utf-8"))
VINES, NETS, FINISHED, START_ACTION = 0x436D40, 0x433440, 0x438960, 0x45DEC0
DISPATCH, OFFERED, NOT_OFFERED = 0x463DD8, 0x463DF6, 0x463E27
CONTINUE, RESUMED, CLEARED = 0x46384D, 0x463874, 0x4636DD
SCIENCE, CONSTRUCTION, PIERS = 0x4D6F5C, 0x4D6F68, 0x4D86A8
STACK, RETURN, VILLAGER = 0x0100_0000, 0x0100_F000, 0x0200_0000
TASK = 0x1C54
# (stage, pier counter, nets counter): untouched, part-done (one step, three steps), fixed, nets under way.
PIER_STATES = ((0, 100, 0), (0, 80, 0), (1, 40, 0), (2, 0, 0), (3, 0, 4))
UNFIXED = {(0, 100, 0), (0, 80, 0), (1, 40, 0)}
_IMAGES: dict = {}


def image(patched: bool) -> bytes:
    if patched not in _IMAGES:
        data = bytearray(EXE.read_bytes())
        if patched:
            for p in FEATURE["patches"]:
                at, before, after = int(p["offset"], 16), bytes.fromhex(p["before"]), bytes.fromhex(p["after"])
                assert data[at:at + len(before)] == before
                data[at:at + len(after)] = after
        _IMAGES[patched] = bytes(data)
    return _IMAGES[patched]


def _no_pier_writes(uc, access, address, size, value, _):
    raise AssertionError("the piers' object was written at 0x%X" % address)


def machine(patched: bool, science: int = 1, construction: int = 1, piers=(0, 100, 0)) -> Uc:
    data = image(patched)
    pe = pefile.PE(data=data, fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    text = next(s for s in pe.sections if s.Name.startswith(b".text"))
    lo = (base + text.VirtualAddress) & ~0xFFF
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    uc.mem_map(lo, ((base + text.VirtualAddress + text.Misc_VirtualSize + 0xFFF) & ~0xFFF) - lo)
    uc.mem_write(base + text.VirtualAddress, bytes(data[text.PointerToRawData:text.PointerToRawData
                                                       + text.SizeOfRawData][:text.Misc_VirtualSize]))
    uc.mem_map(SCIENCE & ~0xFFF, 0x3000)                              # the tech levels and the puzzle objects
    uc.mem_write(SCIENCE, struct.pack("<6i", science, 1, 1, construction, 1, 1))
    uc.mem_write(PIERS, struct.pack("<4i", 0x48E818, *piers))
    uc.mem_map(STACK, 0x10000)
    uc.mem_map(VILLAGER, 0x4000)
    uc.mem_write(VILLAGER + TASK, struct.pack("<i", 30))
    uc.hook_add(UC_HOOK_MEM_WRITE, _no_pier_writes, begin=PIERS, end=PIERS + 0x10)
    return uc


def _calls_hook(finished: dict, got: list):
    """0x438960 answers from `finished` (project id -> bool); 0x45DEC0 records (action, data) and returns."""
    def hook(uc, address, size, _):
        esp = uc.reg_read(UC_X86_REG_ESP)
        ret = struct.unpack("<I", uc.mem_read(esp, 4))[0]
        if address == FINISHED:                      # thiscall, 1 argument
            project = struct.unpack("<i", uc.mem_read(esp + 4, 4))[0]
            uc.reg_write(UC_X86_REG_EAX, int(finished[project]))
            uc.reg_write(UC_X86_REG_ESP, esp + 8)
        elif address == START_ACTION:                # thiscall, 2 arguments: the action, a pointer to its data
            action = struct.unpack("<i", uc.mem_read(esp + 4, 4))[0]
            arg = struct.unpack("<I", uc.mem_read(esp + 8, 4))[0]
            value = struct.unpack("<i", uc.mem_read(arg, 4))[0] if action == 0x1A else uc.mem_read(arg, 1)[0]
            got.append((action, value))
            uc.reg_write(UC_X86_REG_ESP, esp + 12)
        else:
            return
        uc.reg_write(UC_X86_REG_EIP, ret)
    return hook


def handler(uc: Uc, entry: int, finished: dict) -> list:
    got: list = []
    uc.hook_add(UC_HOOK_CODE, _calls_hook(finished, got))
    esp = STACK + 0x8000
    uc.mem_write(esp, struct.pack("<III", RETURN, 0, VILLAGER))   # return, case 0, the villager
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.emu_start(entry, RETURN, count=300)
    assert uc.reg_read(UC_X86_REG_ESP) == esp + 4                 # the handler's own stack balanced (plain ret)
    return got


def vines(patched: bool, science: int, hut: bool) -> tuple[int, int]:
    got = handler(machine(patched, science=science), VINES, {0x16: hut})
    assert len(got) == 1, got
    return got[0]


def nets_drop(patched: bool, construction: int, piers, hut: bool, project_11: bool = False):
    uc = machine(patched, construction=construction, piers=piers)
    uc.mem_write(VILLAGER + TASK, struct.pack("<i", 0))
    got = handler(uc, NETS, {0x0B: project_11, 0x16: hut})
    assert len(got) == 1, got
    return got[0], struct.unpack("<i", uc.mem_read(VILLAGER + TASK, 4))[0]


def fragment(uc: Uc, entry: int, stops: tuple, finished: dict | None = None) -> int:
    seen = []

    def hook(uc, address, size, _):
        if address in stops:
            seen.append(address)
            uc.emu_stop()
        elif address == FINISHED:
            esp = uc.reg_read(UC_X86_REG_ESP)
            project = struct.unpack("<i", uc.mem_read(esp + 4, 4))[0]
            uc.reg_write(UC_X86_REG_EAX, int(finished[project]))
            uc.reg_write(UC_X86_REG_EIP, struct.unpack("<I", uc.mem_read(esp, 4))[0])
            uc.reg_write(UC_X86_REG_ESP, esp + 8)

    uc.hook_add(UC_HOOK_CODE, hook)
    uc.reg_write(UC_X86_REG_ESP, STACK + 0x8000)
    uc.emu_start(entry, RETURN, count=100)
    assert len(seen) == 1, seen
    return seen[0]


def offered(patched: bool, construction: int, piers) -> bool:
    """Whether the Building dispatcher lists option 6, "Fixing the piers" (it goes on to 0x463DF6)."""
    return fragment(machine(patched, construction=construction, piers=piers), DISPATCH,
                    (OFFERED, NOT_OFFERED)) == OFFERED


def resumes(patched: bool, construction: int, piers, project_11: bool = False) -> bool:
    """Whether a villager on task 30 starts fixing the piers again (0x463874) rather than dropping the task."""
    return fragment(machine(patched, construction=construction, piers=piers), CONTINUE, (RESUMED, CLEARED),
                    {0x0B: project_11}) == RESUMED


@unittest.skipUnless(HAVE, "unicorn / pefile not installed")
class Emulated(unittest.TestCase):
    def setUp(self) -> None:
        if not EXE.is_file():
            self.skipTest("stock executable not present")

    def test_vines_stock(self) -> None:
        for science in (1, 2, 3):
            self.assertEqual(vines(False, science, True)[0], 0x7A)
            self.assertEqual(vines(False, science, False), (0x1A, 0x249))

    def test_vines_patched_waits_for_science_3(self) -> None:
        for science in (1, 2):
            self.assertEqual(vines(True, science, True), (0x1A, 0x249), science)
            self.assertEqual(vines(True, science, False), (0x1A, 0x249), science)
        self.assertEqual(vines(True, 3, True)[0], 0x7A)
        self.assertEqual(vines(True, 3, False), (0x1A, 0x249))

    def test_stock_piers(self) -> None:
        # The stock game, as traced: unfixed piers -> fix (action 0x80, task 30) at any Construction; fixed -> the
        # nets (0x7F with the Clothing Hut, else "They need cloth for this!"); project 11 done -> fish (0x81, task 28).
        for construction, piers, hut in itertools.product((1, 2, 3), PIER_STATES, (False, True)):
            got = nets_drop(False, construction, piers, hut)
            if piers in UNFIXED:
                self.assertEqual(got, ((0x80, 0), 30))
            elif hut:
                self.assertEqual(got, ((0x7F, 0), 0))
            else:
                self.assertEqual(got, ((0x1A, 0x136), 0))
            self.assertEqual(nets_drop(False, construction, piers, hut, True), ((0x81, 0), 28))
            self.assertEqual(offered(False, construction, piers), piers in UNFIXED and piers[1] < 100)
            self.assertEqual(resumes(False, construction, piers), piers in UNFIXED)
            self.assertFalse(resumes(False, construction, piers, True))

    def test_patched_piers_wait_for_construction_3(self) -> None:
        for construction, piers, hut in itertools.product((1, 2, 3), PIER_STATES, (False, True)):
            with self.subTest(construction=construction, piers=piers, hut=hut):
                locked = construction < 3 and piers in UNFIXED
                got = nets_drop(True, construction, piers, hut)
                if locked:
                    self.assertEqual(got, ((0x1A, 0x75), 0))     # "Additional research may be necessary."
                else:
                    self.assertEqual(got, nets_drop(False, construction, piers, hut))
                self.assertEqual(nets_drop(True, construction, piers, hut, True),
                                 nets_drop(False, construction, piers, hut, True))
                self.assertEqual(offered(True, construction, piers),
                                 not locked and offered(False, construction, piers))
                self.assertEqual(resumes(True, construction, piers),
                                 not locked and resumes(False, construction, piers))
                self.assertEqual(resumes(True, construction, piers, True), resumes(False, construction, piers, True))

    def test_the_refusal_is_the_huts_construction_text(self) -> None:
        # Hut 2's drop below Construction 2 (0x46F38A) and Hut 3's below 3 (0x46F477) say string 0x75 (action 0x1A).
        stock = image(False)
        pe = pefile.PE(data=stock, fast_load=True)

        def at(va: int, n: int) -> bytes:
            off = pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase)
            return stock[off:off + n]

        self.assertEqual(at(0x46F38F, 3), bytes.fromhex("83F802"))
        self.assertEqual(at(0x46F47C, 3), bytes.fromhex("83F803"))
        for push, say in ((0x46F399, 0x46F39D), (0x46F48A, 0x46F48C)):
            self.assertEqual(at(push, 2), bytes.fromhex("6A1A"))
            self.assertEqual(at(say + 4, 4), struct.pack("<I", 0x75))


class Catalog(unittest.TestCase):
    def test_defaults_and_classic(self) -> None:
        self.assertIn(ID, {p.id for p in patcher.load_public_fun_patches()})
        self.assertEqual(FEATURE["name"], "Harder Fishing Unlock in VV4")
        self.assertTrue(FEATURE["description"].startswith("**Needs no other patch.**"))
        self.assertFalse(gui.default_fun_patch_selection(ID))
        self.assertTrue(gui.owners_default_fun_patch_selection(ID))
        self.assertNotIn(ID, gui.UNTICKING_CONFLICT_IDS)
        classic = json.loads((ROOT / "data" / "vv4_classic_vv_difficulty_feature.json").read_text("utf-8"))
        self.assertIn(ID, classic["dependencies"])

    def test_the_removed_and_renamed_ids_are_gone(self) -> None:
        ids = {p.id for p in patcher.load_public_fun_patches()}
        for gone in ("vv4_no_fishing_at_science_2", "vv4_clothmaking_at_science_3"):
            self.assertNotIn(gone, ids)
            self.assertNotIn(gone, gui.UNTICKING_CONFLICT_IDS)
            self.assertFalse((ROOT / "data" / f"{gone}_feature.json").exists())

    def test_an_old_saved_selection_naming_the_removed_patch_is_ignored(self) -> None:
        # _load_settings ticks each catalog patch by its membership in the saved list, so an id no patch has
        # ticks nothing and is dropped on the next save.
        source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text("utf-8")
        self.assertIn("for patch in self.fun_patches:\n                self.fun_patch_vars[patch.id].set(patch.id in "
                      "selected_fun)", source)


if __name__ == "__main__":
    unittest.main()
