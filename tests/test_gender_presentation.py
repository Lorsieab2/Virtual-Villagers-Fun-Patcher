"""Gender presentation -- a villager drawn with the other sex's heads and bodies, keeping the recorded sex
("VVFP Gender Presentation.dll", native/vvfp_gender_presentation; the owner, 2026-11-15).

THE DRAWS.  Each game picks a villager's head and body sheets from the sex field inside its villager draw routines;
EVERY read of the field inside them is spliced (the DLL's SITES, read here from the C source):

  A New Home         0x437340 Details portrait, 0x4375F0 dialog figure, 0x437790 village, 0x4388E0 map (15 reads)
  The Lost Children  0x445540 Details portrait, 0x445950 strip figure, 0x445B50 village, 0x4478E0 map (22 reads)
  The Secret City    0x4568E0 Details portrait, 0x456CA0 figure, 0x4605F0 village (3 reads)
  The Tree of Life   0x45F550 figure, 0x45F7C0 portrait, 0x467DA0 village (3 compares, then setne)
  New Believers      0x466C40 figure, 0x466EF0 portrait, 0x4720E0 village (3 compares, then setne)

(the Head Look's and Grey Hair at 55's routines: every head and body draw of a villager goes through them).  Each read
is run in the emulator on the stock executable and on the executables the patcher renders (every population mode, all
of the game's patches): with the choice ON, every register and the flags after the read are exactly those of the stock
read of a villager whose field holds the OTHER sex; with it OFF, those of the stock read itself; the record is never
written.  So the routine draws the villager as it draws one of the other sex with the same head and body rows.

Also proved: a record that is not a villager of the game, and the special villagers (the Golden Child, The Secret
City's Tribal Chief, New Believers' story villagers) keep the field; the choice follows the villager across a packed
reload, a rename in play and a sex change, and is read back from the per-save file; nothing is written without a save
slot; all or none; another game installs nothing; no other read of the field is in those routines (stock and
rendered), and no patch moves a read out of them.

The live effect in a running game is NOT verified here.
"""
from __future__ import annotations

import functools
import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402

try:
    import capstone  # noqa: F401
    import pefile

    from gender_presentation_emulation import DLL, Game, presentation_file

    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

SOURCE = ROOT / "native" / "vvfp_gender_presentation" / "vvfp_gender_presentation.c"
MODES = ("stock", "collection_progression", "immediate_fixed")
REGS = ("eax", "ecx", "edx", "ebx", "esp", "ebp", "esi", "edi")
SEX_FIELD = {1: 0x350, 2: 0x538, 3: 0xDC8, 4: 0x1B90, 5: 0x1B90}
ROUTINES = {
    1: ((0x437340, 0x4375F0), (0x4375F0, 0x437790), (0x437790, 0x4388E0), (0x4388E0, 0x4392E0)),
    2: ((0x445540, 0x445950), (0x445950, 0x445B50), (0x445B50, 0x4478E0), (0x4478E0, 0x449000)),
    3: ((0x4568E0, 0x456CA0), (0x456CA0, 0x456F00), (0x4605F0, 0x460C00)),
    4: ((0x45F550, 0x45F7C0), (0x45F7C0, 0x45FA00), (0x467DA0, 0x468400)),
    5: ((0x466C40, 0x466EF0), (0x466EF0, 0x467200), (0x4720E0, 0x472800)),
}
FLAGS = 0x8D5      # CF PF AF ZF SF OF


def _sites() -> dict[int, list[dict]]:
    text = SOURCE.read_text(encoding="utf-8")
    out = {}
    for game in range(1, 6):
        body = text[text.index(f"static const gp_site VV{game}_SITES[] = {{"):]
        body = body[:body.index("};")]
        rows = []
        for m in re.finditer(r"\{ 0x([0-9A-F]+)u, (\d), GP_(LOAD|CMP), R_(\w+), R_(\w+), (GP_NONE|R_\w+), "
                             r"\{ ([^}]*) \} \}", body):
            rows.append(dict(va=int(m.group(1), 16), length=int(m.group(2)), kind=m.group(3), reg=m.group(4).lower(),
                             rec_a=m.group(5).lower(),
                             rec_b=None if m.group(6) == "GP_NONE" else m.group(6)[2:].lower(),
                             stock=bytes(int(x, 16) for x in m.group(7).split(","))))
        out[game] = rows
    return out


SITES = _sites()


@functools.lru_cache(maxsize=None)
def _build(game: int):
    return {b.id: b for b in patcher.load_builds()}[f"vv{game}"]


def stock_path(game: int) -> Path:
    return ROOT / "inputs" / f"vv{game}-stock-copy" / _build(game).input_name


@functools.lru_cache(maxsize=None)
def stock_exe(game: int) -> bytes:
    return stock_path(game).read_bytes()


def have(game: int) -> bool:
    return HAVE_EMULATOR and stock_path(game).is_file() and DLL.is_file()


def _public(game: int) -> list[str]:
    return [p.id for p in patcher.load_fun_patches()
            if p.game_id == f"vv{game}" and not p.raw.get("catalog_hidden") and p.raw.get("catalog_enabled", True)
            and p.raw.get("enabled", True) and p.id not in patcher.ALTERNATIVE_FUN_PATCH_IDS]


@functools.lru_cache(maxsize=None)
def rendered(game: int, mode: str) -> bytes:
    selection = _public(game)
    data, applied = patcher.render_patched_bytes(stock_path(game), _build(game), mode, list(selection))
    features = patcher._attach_automatic_companions(f"vv{game}", patcher._selected_fun_patches(_build(game),
                                                                                             list(selection)))
    patcher._finalize_published_bytes(data, _build(game), features, applied)
    return bytes(data)


def _image(exe: bytes) -> bytes:
    return pefile.PE(data=exe).get_memory_mapped_image()


def sex_reads(exe: bytes, game: int) -> list[int]:
    """Every instruction in the game's draw routines that reads the sex field."""
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    from capstone import x86
    img = _image(exe)
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    found = []
    for start, end in ROUTINES[game]:
        for i in md.disasm(img[start - 0x400000:end - 0x400000], start):
            if any(o.type == x86.X86_OP_MEM and o.mem.disp == SEX_FIELD[game] for o in i.operands):
                found.append(i.address)
    return found


def _skip(game: int):
    return unittest.skipUnless(have(game), f"unicorn/pefile/capstone, the stock VV{game} or the DLL is missing")


def run_site(g: Game, site: dict, record: int, *, other: int = 0, flags: int = 0x202) -> dict:
    """Run one read for `record` (the record in rec_a; rec_b 0); every register and the flags after it."""
    regs = {"eax": 0x11, "ecx": 0x33, "edx": 0x44, "ebx": 0x22, "ebp": 0x66, "esi": 0x77, "edi": 0x55}
    if site["kind"] == "CMP":
        regs[site["reg"]] = other
    regs[site["rec_a"]] = record
    if site["rec_b"]:
        regs[site["rec_b"]] = 0
    g.run(site["va"], regs=regs, until=site["va"] + site["length"], flags=flags)
    assert g.p.reg("eip") == site["va"] + site["length"], hex(g.p.reg("eip"))
    out = {r: g.p.reg(r) for r in REGS}
    out["flags"] = g.p.reg("eflags") & FLAGS
    return out


class _Draws:
    GAME = 0

    def game(self, exe: bytes | None = None, **kw) -> Game:
        return Game(self.GAME, exe if exe is not None else stock_exe(self.GAME), **kw)

    def _same_as_stock(self, g: Game, stock: Game, index: int, drawn: int) -> None:
        """At every site, the hooked read of villager `index` equals the stock read of a villager whose field holds
        `drawn`."""
        r = g.record(index)
        field = g.g["sex"]
        before = g.p.read(r, g.g["stride"])
        stock.p.write(stock.record(index), before)
        stock.p.put32(stock.record(index) + field, drawn)
        for site in SITES[self.GAME]:
            for other in (0, 1, 2):
                for flags in (0x202, 0xAD7):
                    with self.subTest(site=hex(site["va"]), other=other, flags=hex(flags)):
                        self.assertEqual(run_site(g, site, r, other=other, flags=flags),
                                         run_site(stock, site, stock.record(index), other=other, flags=flags))
                        self.assertEqual(g.p.read(r, g.g["stride"]), before)          # the record is not written

    def test_installs_every_site(self):
        g = self.game()
        self.assertEqual(g.p.export("VvfpGenderPresentationInstalled", self.GAME), 1)
        for site in SITES[self.GAME]:
            with self.subTest(site=hex(site["va"])):
                self.assertEqual(g.p.read(site["va"], 1), b"\xE9")
                self.assertEqual(g.p.read(site["va"] + 5, site["length"] - 5), b"\x90" * (site["length"] - 5))

    def test_the_sites_are_every_read_in_the_draw_routines(self):
        reads = sex_reads(stock_exe(self.GAME), self.GAME)
        self.assertEqual(reads, [s["va"] for s in SITES[self.GAME]])
        img = _image(stock_exe(self.GAME))
        for site in SITES[self.GAME]:
            self.assertEqual(img[site["va"] - 0x400000:site["va"] - 0x400000 + site["length"]], site["stock"])

    def test_on_draws_the_other_sex_off_draws_the_field(self):
        stock = self.game(start=False, dll=False)
        for female in (False, True):
            g = self.game()
            g.villager(3, "Kalani", female=female)
            own = g.female if female else g.male
            other = g.male if female else g.female
            self._same_as_stock(g, stock, 3, own)                    # nothing chosen
            self.assertEqual(g.set(3, 1), 1)
            self.assertEqual(g.get(3), 1)
            self._same_as_stock(g, stock, 3, other)                  # on: the other sex's look
            self.assertEqual(g.p.u32(g.record(3) + g.g["sex"]), own)  # the field is never written
            self.assertEqual(g.set(3, 0), 1)
            self.assertEqual(g.get(3), 0)
            self._same_as_stock(g, stock, 3, own)                    # off again

    def test_only_the_chosen_villager(self):
        g = self.game()
        g.villager(0, "Ana", female=True)
        g.villager(1, "Bea", female=True)
        self.assertEqual(g.set(1, 1), 1)
        stock = self.game(start=False, dll=False)
        self._same_as_stock(g, stock, 0, g.female)
        self._same_as_stock(g, stock, 1, g.male)

    def test_a_record_that_is_not_a_villager_keeps_the_field(self):
        g = self.game()
        g.villager(1, "Ana", female=True)
        g.set(1, 1)
        fake = g.p.alloc(g.g["stride"] + 0x100)
        g.p.put32(fake + g.g["sex"], g.female)
        misaligned = g.record(1) + 4
        g.p.put32(misaligned + g.g["sex"], g.female)
        stock = self.game(start=False, dll=False)
        for site in SITES[self.GAME]:
            for rec in (fake, misaligned):
                with self.subTest(site=hex(site["va"]), rec=hex(rec)):
                    stock.p.write(rec, g.p.read(rec, g.g["stride"]))
                    self.assertEqual(run_site(g, site, rec), run_site(stock, site, rec))

    def test_follows_the_villager_across_a_packed_reload(self):
        g = self.game()
        g.villager(0, "Ana")
        g.villager(1, "Bea", female=True)
        g.villager(2, "Cal")
        self.assertEqual(g.set(2, 1), 1)
        g.p.write(g.record(1) + g.g["present"], b"\x00")          # Bea dies and is buried
        g.get(0)
        stride = g.g["stride"]
        g.p.write(g.record(1), g.p.read(g.record(2), stride))     # the reload packs Cal into record 1
        g.p.write(g.record(2), bytes(stride))
        fresh = self.game()
        fresh.disk.files = dict(g.disk.files)
        fresh.disk.folders = set(g.disk.folders)
        fresh.p.write(fresh.record(0), g.p.read(g.record(0), 3 * stride))
        self.assertEqual(fresh.get(1), 1)
        self.assertEqual(fresh.get(0), 0)
        self._same_as_stock(fresh, self.game(start=False, dll=False), 1, fresh.female)

    def test_the_file(self):
        g = self.game()
        g.villager(4, "Iolana", female=True)
        self.assertEqual(g.set(4, 1), 1)
        data = g.disk.files[presentation_file(1)]
        count = g.g["count"]
        self.assertEqual(data[:12], struct.pack("<III", 0x31504756, self.GAME, count))
        self.assertEqual(len(data), 12 + count * 9)
        self.assertEqual(data[12 + count * 8 + 4], 1)
        later = self.game()
        later.disk.files = dict(g.disk.files)
        later.disk.folders = set(g.disk.folders)
        later.villager(4, "Iolana", female=True)
        self.assertEqual(later.get(4), 1)

    def test_a_rename_in_play_keeps_it(self):
        g = self.game()
        g.villager(0, "Ana")
        g.villager(1, "Bea", female=True)
        g.villager(2, "Cal")
        self.assertEqual(g.set(1, 1), 1)
        g.p.write(g.record(1) + g.g["name"], b"Beatrix\0")
        g.p.tick += 5000
        self.assertEqual(g.get(1), 1)

    def test_a_sex_change_keeps_it(self):
        g = self.game()
        g.villager(0, "Ana")
        g.villager(1, "Bea", female=True)
        g.villager(2, "Cal")
        self.assertEqual(g.set(1, 1), 1)
        r = g.record(1)
        before = g.p.alloc(g.g["stride"])
        g.p.write(before, g.p.read(r, g.g["stride"]))
        g.p.put32(r + g.g["sex"], g.male)
        g.later()
        self.assertEqual(g.p.export("VvfpVillagerSexChanged", self.GAME, 1, r, before), 1)
        self.assertEqual(g.get(1), 1)
        # Now male, presenting with the other look: drawn as a woman.
        self._same_as_stock(g, self.game(start=False, dll=False), 1, g.female)
        later = self.game()
        later.disk.files = dict(g.disk.files)
        later.disk.folders = set(g.disk.folders)
        later.p.write(later.record(0), g.p.read(g.record(0), 3 * g.g["stride"]))
        self.assertEqual(later.get(1), 1)

    def test_no_slot_nothing_is_kept(self):
        g = self.game(slot=0)
        g.villager(1, "Ana")
        self.assertEqual(g.set(1, 1), 0)
        self.assertEqual(g.disk.files, {})

    def test_all_or_nothing(self):
        for site in SITES[self.GAME]:
            for k in (0, site["length"] - 1):
                exe = bytearray(stock_exe(self.GAME))
                pe = pefile.PE(data=bytes(exe))
                exe[pe.get_offset_from_rva(site["va"] + k - 0x400000)] ^= 0xFF
                g = self.game(bytes(exe))
                with self.subTest(va=hex(site["va"]), byte=k):
                    self.assertEqual(g.p.export("VvfpGenderPresentationInstalled", self.GAME), 0)
                    for other in SITES[self.GAME]:
                        if other["va"] != site["va"]:
                            self.assertNotEqual(g.p.read(other["va"], 1), b"\xE9")

    def test_another_game_installs_nothing(self):
        g = self.game(start=False)
        g.p.export("VvfpStartup", 1 if self.GAME != 1 else 2, 0)
        self.assertEqual(g.p.export("VvfpGenderPresentationInstalled", self.GAME), 0)
        for site in SITES[self.GAME]:
            self.assertNotEqual(g.p.read(site["va"], 1), b"\xE9")

    def test_every_mode_with_every_patch(self):
        for mode in MODES:
            exe = rendered(self.GAME, mode)
            with self.subTest(mode=mode):
                self.assertEqual(sex_reads(exe, self.GAME), [s["va"] for s in SITES[self.GAME]])
                g = self.game(exe)
                self.assertEqual(g.p.export("VvfpGenderPresentationInstalled", self.GAME), 1)
                g.villager(5, "Keoni")
                self.assertEqual(g.set(5, 1), 1)
                stock = Game(self.GAME, exe, start=False, dll=False)
                self._same_as_stock(g, stock, 5, g.female)


@_skip(1)
class ANewHome(_Draws, unittest.TestCase):
    GAME = 1

    def test_the_golden_child_is_never_reached(self):
        g = self.game()
        r = g.villager(2, "Golden Child")
        g.p.put32(r + 0x36C, 0xC7)
        self.assertEqual(g.set(2, 1), 0)
        self.assertEqual(g.get(2), 0)
        self._same_as_stock(g, self.game(start=False, dll=False), 2, g.male)


@_skip(2)
class TheLostChildren(_Draws, unittest.TestCase):
    GAME = 2


@_skip(3)
class TheSecretCity(_Draws, unittest.TestCase):
    GAME = 3

    def test_the_tribal_chief_is_never_reached(self):
        g = self.game()
        g.villager(0, "Ana")
        g.villager(1, "Bea", female=True)
        self.assertEqual(g.set(1, 1), 1)
        g.p.write(g.record(1) + 0xE80, b"\x01")                     # Bea becomes the Tribal Chief
        self._same_as_stock(g, self.game(start=False, dll=False), 1, g.female)
        self.assertEqual(g.set(1, 0), 0)


@_skip(4)
class TheTreeOfLife(_Draws, unittest.TestCase):
    GAME = 4


@_skip(5)
class NewBelievers(_Draws, unittest.TestCase):
    GAME = 5

    def test_story_villagers_are_never_reached(self):
        g = self.game()
        r = g.villager(1, "Ana", female=True)
        g.p.put32(r + 0x1CFC, 12)
        self.assertEqual(g.set(1, 1), 0)
        self._same_as_stock(g, self.game(start=False, dll=False), 1, g.female)


if __name__ == "__main__":
    unittest.main()
