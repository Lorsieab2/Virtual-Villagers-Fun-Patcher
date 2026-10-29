"""Grey Hair at 55 and Show Parents on the A New Home Details portrait (native/vv1_grey_hair,
native/vv1_parentage).

The Origins Details-portrait wrapper (scripts/build_vv1_origins_feature.py, the four head calls of
0x437340) draws the head from a copy of its seven draw arguments -- the draw Grey Hair turns grey -- and
then hands the untouched arguments to "VVFP VV1 Origins Icons.dll" Vv1DrawPortraitMask, which calls
"VVFP VV1 Parentage.dll" Vv1ParentageDrawPortrait: for a villager under 18 with a recorded parent it
draws the parents, then the child's body and head again over them.  Those arguments' sprite is the young
sheet, so the head drawn last was the young one even when the portrait's own draw was grey (a child set
to Old).  The parentage companion now asks Grey Hair's Vv1GreyHairSheetFor for the sheet first.

Here a full collection_progression build runs in an emulator from the portrait's read of the head sheet
(0x437405) to the instruction after its call (0x437420): the wrapper, the real Origins Icons DLL, the
parentage DLL's replay and every engine draw, with Grey Hair in the game and without it:

* Old, a 5-year-old with a recorded mother: both head draws are the grey sheet with the portrait's own
  arguments, so the head on top is grey; the mother's small picture stays young;
* Young (under 18 and at 1,100): every head drawn is young; Auto: young under 55 (both draws), grey at 55
  (no parents then);
* the Origins mask is still drawn over the head, after it, in the head's own column;
* without Grey Hair (the row off): every head is young, replayed with the same arguments, and the mask
  is drawn;
* no file is written on the way (WriteFile, MoveFile and the like are not answered here).

The parentage DLL is its TEST build (tests/test_dlls: the same source with probe exports), which lets the
test record the mother without the save files.  The live effect in a running game is NOT verified here.
"""
from __future__ import annotations

import functools
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import test_vv1_grey_hair as grey  # noqa: E402

if grey.HAVE_EMULATOR:
    import pefile

ORIGINS = ROOT / "assets" / "origins" / "VVFP VV1 Origins Icons.dll"
PARENTAGE = ROOT / "tests" / "test_dlls" / "VVFP VV1 Parentage.test.dll"
ORIGINS_BASE, PARENTAGE_BASE = 0x30000000, 0x38000000
READ, AFTER_CALL = 0x437405, 0x437420                 # the portrait's man's-head read; after its call
CELL_RECT, PLACE_SCALED = 0x409F90, 0x407ED0           # the parent figures' cell and placement
RECORDS_PTR, CAPTURED_SLOT = 0x48B614, 0x4911F4
MASK_TABLE = 0x491000                                  # .vv1md: a nibble per record, 0 none
AUTO, YOUNG, OLD = 0, 1, 2
CHILD, MOTHER = 12, 3


def have() -> bool:
    return grey.have() and ORIGINS.is_file() and PARENTAGE.is_file()


@functools.lru_cache(maxsize=None)
def _without_grey_hair() -> bytes:
    """Every public A New Home row but Grey Hair at 55."""
    selection = [i for i in grey._public_vv1() if i != "vv1_grey_hair"]
    build = grey._build()
    data, applied = grey.patcher.render_patched_bytes(grey.stock_path(), build, "collection_progression", selection)
    features = grey.patcher._attach_automatic_companions("vv1", grey.patcher._selected_fun_patches(build, selection))
    assert "vv1_grey_hair" not in {f.id for f in features}
    grey.patcher._finalize_published_bytes(data, build, features, applied)
    return bytes(data)


def _shown(draws) -> list[tuple[str, ...]]:
    return [tuple(hex(v) for v in d) for d in draws]


class Portrait:
    """A full build in the emulator with the Origins Icons and parentage DLLs mapped beside Grey Hair's, a
    village of a mother and her son, and every draw recorded instead of drawn."""

    def __init__(self, *, with_grey_hair: bool):
        exe = grey._rendered("collection_progression", True)[0] if with_grey_hair else _without_grey_hair()
        # Grey Hair's DLL is mapped either way (the emulator loads one DLL itself); without the row it is never
        # started and no module lookup finds it, as in a game it is not shipped to.
        self.g = g = grey.Game(exe, start=with_grey_hair)
        self.p = p = g.p
        self.modules = {
            "vvfp vv1 origins icons.dll": self._map(ORIGINS, ORIGINS_BASE),
            "vvfp vv1 parentage.dll": self._map(PARENTAGE, PARENTAGE_BASE),
        }
        if with_grey_hair:
            self.modules["vvfp vv1 grey hair.dll"] = (p.dll_base, dict(p.exports))
        self.looks: dict[int, int] = {}
        self.look_module, self.look_get = p.alloc(16), p.alloc(16)
        p.stub(self.look_get, lambda p: (self.looks.get(p.arg(1), AUTO), 8))
        p.api_handlers.update(
            GetModuleHandleA=self._module_handle, GetProcAddress=self._proc,
            LoadLibraryA=self._load_a, LoadLibraryExW=self._load_w,
            SHGetFolderPathA=self._documents, WideCharToMultiByte=self._narrow,
            # No file is there (the parentage records start empty), and none is written: WriteFile, MoveFileEx
            # and the like are not answered, so a write would stop the run.
            CreateDirectoryA=lambda p: (1, 8), CreateDirectoryW=lambda p: (1, 8),
            GetFileAttributesA=lambda p: (grey.INVALID, 4), GetFileAttributesExA=lambda p: (0, 12),
            CreateFileA=lambda p: (grey.INVALID, 28), FindFirstFileA=lambda p: (grey.INVALID, 8),
        )
        self.draws: list[tuple[int, ...]] = []           # (sprite, x, y, row, col, scale, flag) per engine draw
        self.parents: list[int] = []                     # the atlas of each parent figure cell
        self.sprites: dict[int, str] = {}                # every sprite the game's constructor built: its file
        for resume in grey.ENGINES.values():
            p.stub(resume, self._draw)
        p.stub(grey.CTOR, self._sprite)
        p.stub(CELL_RECT, self._cell)
        p.stub(PLACE_SCALED, lambda p: (0, 0x14))        # off screen: the figure's cell is chosen, not blitted
        # The village: the records the parentage companion reads, and the slot the game saves to.
        p.put32(RECORDS_PTR, g.game)
        p.put32(CAPTURED_SLOT, 1)
        self.mother = g.villager(MOTHER, age=600, head=2, male=False)
        p.write(self.mother + 0x370, b"Lani\0")
        self.child = g.villager(CHILD, age=100, head=4, male=True)
        p.write(self.child + 0x370, b"Keoni\0")
        self._probe("Vv1ParentageProbeReset")
        for _ in range(64):
            if self._probe("Vv1ParentageProbeSync", 1, g.game) == 1:
                break
        else:
            raise AssertionError("the parentage table never settled on the village")
        if self._probe("Vv1ParentageProbeBorn", g.game, self.child, self.mother) != CHILD:
            raise AssertionError("the mother was not recorded")

    # -- modules ------------------------------------------------------------------------------------------
    def _map(self, path: Path, base: int) -> tuple[int, dict[str, int]]:
        p = self.p
        pe = pefile.PE(str(path))
        pe.relocate_image(base)                          # the import slots move with it
        image = pe.get_memory_mapped_image(ImageBase=base)
        p.mu.mem_map(base, (len(image) + 0xFFF) & ~0xFFF)
        p.mu.mem_write(base, image)
        stub = max(p.api_names) + 16
        for entry in pe.DIRECTORY_ENTRY_IMPORT:
            for imp in entry.imports:
                p.mu.mem_write(stub, b"\xC3")
                p.api_names[stub] = imp.name.decode() if imp.name else f"#{imp.ordinal}"
                p.put32(imp.address, stub)
                stub += 16
        return base, {s.name.decode(): base + s.address for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name}

    def _probe(self, name: str, *args: int) -> int:
        return self.p.call(self.modules["vvfp vv1 parentage.dll"][1][name], list(args))

    def _by_name(self, name: str) -> int:
        leaf = name.replace("/", "\\").split("\\")[-1].lower()
        return self.modules.get(leaf, (0, {}))[0]

    def _module_handle(self, p):
        name = p.cstring(p.arg(0))
        return (self.look_module if name == "VVFP Head Look.dll" else self._by_name(name)), 4

    def _proc(self, p):
        module, name = p.arg(0), p.cstring(p.arg(1))
        if module == self.look_module:
            return (self.look_get if name == "VvfpHeadLookGet" else 0), 8
        for base, exports in self.modules.values():
            if base == module:
                return exports.get(name, 0), 8
        return 0, 8

    def _load_a(self, p):
        return self._by_name(p.cstring(p.arg(0))), 4

    def _load_w(self, p):
        return self._by_name(p.wstring(p.arg(0))), 12

    def _documents(self, p):
        p.write(p.arg(4), b"D:\\Documents\0")
        return 0, 20

    def _narrow(self, p):
        # WideCharToMultiByte(page, flags, wide, -1, out, room, ...): a companion narrows a path.
        text = p.wstring(p.arg(2)).encode("cp1252", errors="replace") + b"\0"
        if p.arg(5) == 0:
            return len(text), 32
        if len(text) > p.arg(5):
            return 0, 32
        p.write(p.arg(4), text)
        return len(text), 32

    # -- the game's routines ------------------------------------------------------------------------------
    def _draw(self, p):
        # At the engine entry's resume the displaced `sub esp, 0x10` has run: the arguments start at esp+0x14.
        esp = p.reg("esp")
        self.draws.append(tuple(p.u32(esp + 0x14 + 4 * i) for i in range(7)))
        p.set_reg("esp", esp + 0x10)
        return 0, 0x1C

    def _cell(self, p):
        self.parents.append(p.reg("ecx"))
        p.write(p.arg(2), struct.pack("<4i", 0, 0, 40, 65))
        return 0, 0xC

    def _sprite(self, p):
        self.sprites[p.reg("ecx")] = p.cstring(p.arg(0))
        return self.g._ctor(p)

    # -- the portrait -------------------------------------------------------------------------------------
    def run(self, *, look: int, age: int, mask: int = 0) -> list[tuple[int, ...]]:
        """Draw the son's Details portrait head at `age` under `look` with Origins mask `mask` (0 none):
        every engine draw, in order."""
        p, g = self.p, self.g
        p.put32(self.child + grey.REC_AGE, age)
        p.write(MASK_TABLE + CHILD // 2, bytes([mask << 4 if CHILD & 1 else mask]))
        self.looks[self.child] = look
        self.draws.clear()
        self.parents.clear()
        for reg in ("eax", "ebx", "ecx", "edx", "ebp"):
            p.set_reg(reg, g.scratch)
        p.set_reg("esi", g.game)
        p.set_reg("edi", self.child)
        p.set_reg("esp", grey.STACK_TOP - 0x4000)
        p.mu.emu_start(READ, AFTER_CALL, count=2_000_000)
        if p.reg("eip") != AFTER_CALL:
            raise AssertionError(f"the portrait stopped at {p.reg('eip'):#x}")
        return list(self.draws)

    def grey_sheet(self) -> int | None:
        """Grey Hair's grey men's sheet, once built."""
        return next((at for at, name in self.sprites.items() if name == "vvfp_grey_male_heads.png"), None)

    def heads(self, draws) -> list[tuple[int, ...]]:
        """The head draws: those of the young men's sheet or of the grey one."""
        return [d for d in draws if d[0] in (self.g.young[True], self.grey_sheet())]

    def masks_after_the_last_head(self, draws) -> list[tuple[int, ...]]:
        last = max(i for i, d in enumerate(draws) if d in self.heads(draws))
        return [d for d in draws[last + 1:]
                if d[0] not in (self.g.young[True], self.g.young[False], self.g.scratch, self.grey_sheet())]


def _skip():
    return unittest.skipUnless(have(), "unicorn/pefile, the stock A New Home, or a companion DLL is missing")


@_skip()
class WithGreyHair(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.portrait = Portrait(with_grey_hair=True)

    def test_old_son_with_a_mother_ends_grey(self):
        """The bug: a child set to Old was drawn grey, then covered by the young head Show Parents drew
        again over the parents.  Both head draws are now the grey sheet with the portrait's own arguments."""
        port = self.portrait
        draws = port.run(look=OLD, age=100)
        heads = port.heads(draws)
        self.assertEqual(len(heads), 2, _shown(draws))
        self.assertIsNotNone(port.grey_sheet())
        self.assertEqual(heads[0][0], port.grey_sheet())                     # the portrait's own draw
        self.assertEqual(heads[1], heads[0])                                 # drawn again: same sheet and tuple
        self.assertEqual(draws[-1], heads[1])                                # and nothing over it
        self.assertEqual(port.parents, [port.g.scratch, port.g.young[False]])  # the mother's head: young
        self.assertEqual(port.p.u32(port.child + grey.REC_HEAD), 4)          # the head value is not written

    def test_young_ends_young(self):
        port = self.portrait
        for age, count in ((100, 2), (1100, 1)):                             # 55: the parents step out
            with self.subTest(age=age):
                draws = port.run(look=YOUNG, age=age)
                self.assertEqual([h[0] for h in port.heads(draws)], [port.g.young[True]] * count, _shown(draws))

    def test_auto_is_as_before(self):
        port = self.portrait
        draws = port.run(look=AUTO, age=100)
        self.assertEqual([h[0] for h in port.heads(draws)], [port.g.young[True]] * 2, _shown(draws))
        self.assertEqual(len(port.parents), 2)
        draws = port.run(look=AUTO, age=1100)
        self.assertEqual([h[0] for h in port.heads(draws)], [port.grey_sheet()], _shown(draws))
        self.assertEqual(port.parents, [])

    def test_the_mask_is_still_drawn_over_the_grey_head(self):
        port = self.portrait
        draws = port.run(look=OLD, age=100, mask=3)
        heads = port.heads(draws)
        self.assertEqual([h[0] for h in heads], [port.grey_sheet()] * 2, _shown(draws))
        masks = port.masks_after_the_last_head(draws)
        self.assertEqual(len(masks), 1, _shown(draws))
        self.assertEqual(masks[0][3], 2)                                      # row: the mask's colour (3 - 1)
        self.assertEqual(masks[0][4], heads[-1][4])                           # column: the head's facing


@_skip()
class WithoutGreyHair(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.portrait = Portrait(with_grey_hair=False)

    def test_every_head_young_and_the_replay_unchanged(self):
        port = self.portrait
        for look, age, count in ((OLD, 100, 2), (AUTO, 100, 2), (YOUNG, 100, 2), (OLD, 1100, 1), (AUTO, 1100, 1)):
            with self.subTest(look=look, age=age):
                draws = port.run(look=look, age=age)
                heads = port.heads(draws)
                self.assertEqual([h[0] for h in heads], [port.g.young[True]] * count, _shown(draws))
                self.assertEqual(len(set(heads)), 1)                          # drawn again with the same tuple
                self.assertIsNone(port.grey_sheet())

    def test_the_mask_is_still_drawn(self):
        port = self.portrait
        draws = port.run(look=AUTO, age=100, mask=2)
        masks = port.masks_after_the_last_head(draws)
        self.assertEqual(len(masks), 1, _shown(draws))
        self.assertEqual(masks[0][3], 1)


if __name__ == "__main__":
    unittest.main()
