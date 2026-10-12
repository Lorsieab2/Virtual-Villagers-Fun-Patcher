"""The Villager Details name box is written back only to the villager it shows.

A New Home (Fix Vanilla Bugs, vv1_fix_vanilla_bugs).  The Details screen's
message handler 0x44A700 (vtable 0x482208[3]) handles Done (+0x4C), the right
arrow (+0x58) and the left arrow (+0x54).  Each first copies the name box
(+0x94) into the SELECTED villager's name, record[state+0xAD34]+0x370
(getText 0x40BB70 at 0x44A748 / 0x44A7A4 / 0x44A859), then sets the reload
flag +0x24 and, for the arrows, moves the selection (0x4393E0, store at
0x44A7FF / 0x44A8B4).  The box is refilled with the newly selected villager's
name only by the once-per-frame update 0x44A630 (vtable +0x20), which clears
+0x24.  The SDL_PollEvent loop 0x403970..0x403C82 handles every queued event
before the frame's update, so two arrow clicks -- or an arrow and Done -- in
one frame copied villager A's name onto villager B.  Seen in the owner's
village: Iruwa Okelani became a second "Tiki Alosaka".

The fix: the three write-backs call a guard in the NOP gap at 0x44A6F2 that
skips getText while +0x24 is set (the box has not been refilled for the
villager now selected).  These tests run the real handler and update in
unicorn, stock and patched, in every mode, and fail on the stock bytes.

The Lost Children, The Secret City, The Tree of Life and New Believers do not
have the bug: their Details screens refill the name box synchronously, inside
the same handler that changes the selection, and when the screen is shown; their
per-frame updates never touch the name box.  The static tests below pin that
from the stock executables.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import load_builds, render_patched_bytes  # noqa: E402

STOCK_DIR = ROOT / "research" / "stock-executables"
EXES = {
    "vv1": "Virtual Villagers - A New Home.exe",
    "vv2": "Virtual Villagers - The Lost Children.exe",
    "vv3": "Virtual Villagers - The Secret City.exe",
    "vv4": "Virtual Villagers - The Tree of Life.exe",
    "vv5": "Virtual Villagers - New Believers.exe",
}
MODES = ("stock", "collection_progression", "immediate_fixed")
FIX = "vv1_fix_vanilla_bugs"
FULL_NAMES = "vv1_details_full_names"

# A New Home addresses.
HANDLER = 0x44A700
UPDATE = 0x44A630
SPRINTF = 0x44B23D        # stock refill: sprintf(buf, name)
STRCPY = 0x44F380         # Fix Vanilla Bugs' refill: strcpy(buf, name)
SET_TEXT = 0x40BB30
SOUND = 0x431470
CLOSE = 0x40AE10
STUBS = {SOUND: 4, CLOSE: 4, SPRINTF: 0, STRCPY: 0, SET_TEXT: 4}

STRIDE = 0x3D8
NAME = 0x370
SELECTED = 0xAD34
DONE_ID, PREV_ID, NEXT_ID = 0x101, 0x102, 0x103

STACK = 0x70000000
SCREEN = 0x20000000
STATE = 0x21000000
ARRAY = 0x22000000
BOX = 0x23000000
BOX_INNER = BOX + 0x100
BOX_TEXT = BOX + 0x1000
SOUND_OBJ = 0x24000000
RETURN = 0x0BAD0000


def _render(game: str, mode: str, ids) -> bytes:
    build = next(b for b in load_builds() if b.id == game)
    rendered, _ = render_patched_bytes(STOCK_DIR / EXES[game], build, mode, list(ids))
    return bytes(rendered)


class DetailsScreen:
    """The real Details handler and update of one rendered A New Home exe."""

    def __init__(self, exe: bytes, names: list[str], selected: int, box_limit: int = 28) -> None:
        pe = pefile.PE(data=exe)
        image = pe.get_memory_mapped_image()
        self.mu = mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(0x400000, (len(image) + 0xFFFF) & ~0xFFFF)
        mu.mem_write(0x400000, image)
        mu.mem_map(STACK - 0x10000, 0x20000)
        for base in (SCREEN, STATE, BOX, SOUND_OBJ, RETURN):
            mu.mem_map(base, 0x10000)
        mu.mem_map(ARRAY, 0x40000)
        self.box_limit = box_limit
        mu.mem_write(SCREEN + 0x0C, struct.pack("<I", STATE))
        mu.mem_write(SCREEN + 0x10, struct.pack("<I", ARRAY))
        mu.mem_write(SCREEN + 0x1C, struct.pack("<I", SOUND_OBJ))
        mu.mem_write(SCREEN + 0x4C, struct.pack("<I", DONE_ID))
        mu.mem_write(SCREEN + 0x54, struct.pack("<I", PREV_ID))
        mu.mem_write(SCREEN + 0x58, struct.pack("<I", NEXT_ID))
        mu.mem_write(SCREEN + 0x94, struct.pack("<I", BOX))
        mu.mem_write(BOX + 0x10, struct.pack("<I", BOX_INNER))
        mu.mem_write(BOX_INNER + 0x30, struct.pack("<I", BOX_TEXT))
        mu.mem_write(ARRAY + 0x3E010, struct.pack("<I", STATE))   # 0x4393E0's village state
        for index, name in enumerate(names):
            rec = ARRAY + index * STRIDE
            mu.mem_write(rec + 0x28, b"\x01")                     # occupied
            mu.mem_write(rec + 0x344, struct.pack("<i", 100))     # living
            mu.mem_write(rec + NAME, name.encode("latin-1") + b"\0")
        mu.mem_write(STATE + SELECTED, struct.pack("<i", selected))
        mu.mem_write(SCREEN + 0x24, b"\x01")                      # the constructor's reload flag
        mu.hook_add(UC_HOOK_CODE, self._on_code)
        self.closed = 0

    def _on_code(self, uc, address, size, user_data) -> None:
        if address not in STUBS:
            return
        esp = uc.reg_read(UC_X86_REG_ESP)
        ret, a1, a2 = struct.unpack("<III", uc.mem_read(esp, 12))
        if address in (SPRINTF, STRCPY):                          # (dst, src), cdecl
            text = bytes(uc.mem_read(a2, 64)).split(b"\0")[0]
            uc.mem_write(a1, text + b"\0")
        elif address == SET_TEXT:                                 # thiscall(text)
            text = bytes(uc.mem_read(a1, 64)).split(b"\0")[0]
            uc.mem_write(BOX_TEXT, text + b"\0")
        elif address == CLOSE:
            self.closed += 1
        uc.reg_write(UC_X86_REG_EAX, 0)
        uc.reg_write(UC_X86_REG_ESP, esp + 4 + STUBS[address])
        uc.reg_write(UC_X86_REG_EIP, ret)

    def _call(self, entry: int, *args: int) -> None:
        esp = STACK - 0x100 - 4 * len(args)
        self.mu.mem_write(esp, struct.pack("<I" + "I" * len(args), RETURN, *args))
        self.mu.reg_write(UC_X86_REG_ESP, esp)
        self.mu.reg_write(UC_X86_REG_ECX, SCREEN)
        self.mu.emu_start(entry, RETURN, count=200000)
        assert self.mu.reg_read(UC_X86_REG_ESP) == esp + 4 + 4 * len(args)

    # What the player does.
    def frame(self) -> None:
        self._call(UPDATE)

    def click(self, button: int) -> None:
        self._call(HANDLER, 8, button)

    def type_name(self, text: str) -> None:
        self.mu.mem_write(BOX_TEXT, text.encode("latin-1") + b"\0")

    # What there is.
    def name(self, index: int) -> str:
        raw = bytes(self.mu.mem_read(ARRAY + index * STRIDE + NAME, 28))
        return raw.split(b"\0")[0].decode("latin-1")

    def box(self) -> str:
        return bytes(self.mu.mem_read(BOX_TEXT, 64)).split(b"\0")[0].decode("latin-1")

    def selected(self) -> int:
        return struct.unpack("<i", self.mu.mem_read(STATE + SELECTED, 4))[0]


NAMES = ["Tiki Alosaka", "Iruwa Okelani", "Kito Kalahuna", "Chika Kalahuna"]


class ANewHomeEmulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.builds = {}
        for mode in MODES:
            cls.builds[(mode, "stock")] = _render("vv1", mode, [])
            cls.builds[(mode, "full names")] = _render("vv1", mode, [FULL_NAMES])
            cls.builds[(mode, "fixed")] = _render("vv1", mode, [FIX])
            cls.builds[(mode, "fixed + full names")] = _render("vv1", mode, [FIX, FULL_NAMES])

    def screens(self):
        """(mode, build, exe, fixed, cut): `cut` is what a write-back keeps of
        a name -- 10 characters in the base game's box, 27 with Full Names
        (the separate cut-names bug, vv1_details_full_names)."""
        for (mode, label), exe in self.builds.items():
            limit = 27 if "full names" in label else 10
            yield mode, label, exe, label.startswith("fixed"), (lambda name, n=limit: name[:n])

    def test_two_arrow_clicks_in_one_frame(self) -> None:
        for mode, label, exe, fixed, cut in self.screens():
            for button, moved_to in ((NEXT_ID, 1), (PREV_ID, 3)):
                with self.subTest(mode=mode, build=label, button=button):
                    s = DetailsScreen(exe, NAMES, 0)
                    s.frame()
                    self.assertEqual(s.box(), "Tiki Alosaka")
                    s.click(button)
                    s.click(button)                     # same frame: no update between
                    s.frame()
                    expected = [cut(NAMES[0])] + NAMES[1:]
                    if not fixed:                       # the base game's bug
                        expected[moved_to] = cut("Tiki Alosaka")
                    self.assertEqual([s.name(i) for i in range(4)], expected)
                    self.assertEqual(s.box(), s.name(s.selected()))

    def test_arrow_then_done_in_one_frame(self) -> None:
        for mode, label, exe, fixed, cut in self.screens():
            with self.subTest(mode=mode, build=label):
                s = DetailsScreen(exe, NAMES, 1)
                s.frame()
                s.click(NEXT_ID)
                s.click(DONE_ID)
                self.assertEqual(s.closed, 1)
                self.assertEqual(s.selected(), 2)
                expected = [NAMES[0], cut(NAMES[1]), NAMES[2], NAMES[3]]
                if not fixed:
                    expected[2] = cut("Iruwa Okelani")
                self.assertEqual([s.name(i) for i in range(4)], expected)

    def test_done_before_the_first_frame_keeps_the_name(self) -> None:
        """The constructor sets the reload flag and the box holds the sizing
        text until the first update; a Done handled before it no longer
        writes that text into the villager."""
        for mode, label, exe, fixed, cut in self.screens():
            with self.subTest(mode=mode, build=label):
                s = DetailsScreen(exe, NAMES, 2)
                s.type_name("wwwwwwwww")
                s.click(DONE_ID)
                self.assertEqual(s.name(2), "Kito Kalahuna" if fixed else "wwwwwwwww")

    def test_a_typed_name_is_still_saved_to_its_villager(self) -> None:
        for mode, label, exe, fixed, cut in self.screens():
            for button in (NEXT_ID, PREV_ID, DONE_ID):
                with self.subTest(mode=mode, build=label, button=button):
                    s = DetailsScreen(exe, NAMES, 1)
                    s.frame()
                    s.type_name("Leilani Kahale")
                    s.click(button)
                    s.frame()
                    self.assertEqual([s.name(i) for i in range(4)],
                                     [NAMES[0], cut("Leilani Kahale"), NAMES[2], NAMES[3]])

    def test_one_click_per_frame_walks_and_keeps_every_name(self) -> None:
        for mode, label, exe, fixed, cut in self.screens():
            with self.subTest(mode=mode, build=label):
                s = DetailsScreen(exe, NAMES, 0)
                s.frame()
                seen = []
                for button in (NEXT_ID,) * 5 + (PREV_ID,) * 3:
                    s.click(button)
                    s.frame()
                    seen.append(s.selected())
                    self.assertEqual(s.box(), s.name(s.selected()))
                self.assertEqual(seen, [1, 2, 3, 0, 1, 0, 3, 2])
                self.assertEqual([s.name(i) for i in range(4)], [cut(n) for n in NAMES])

    def test_typed_name_then_two_arrows_in_one_frame(self) -> None:
        """The first arrow saves the typed name to the villager shown; the
        second (same frame) writes nothing."""
        for mode, label, exe, fixed, cut in self.screens():
            with self.subTest(mode=mode, build=label):
                s = DetailsScreen(exe, NAMES, 0)
                s.frame()
                s.type_name("Moana")
                s.click(NEXT_ID)
                s.click(NEXT_ID)
                s.frame()
                expected = ["Moana"] + NAMES[1:]
                if not fixed:
                    expected[1] = "Moana"               # the base game gives it to Iruwa too
                self.assertEqual([s.name(i) for i in range(4)], expected)
                self.assertEqual(s.selected(), 2)
                self.assertEqual(s.box(), "Kito Kalahuna")


class ANewHomeStaticTests(unittest.TestCase):
    """The chain the fix relies on, pinned in the stock executable."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.pe = pefile.PE(str(STOCK_DIR / EXES["vv1"]))
        cls.image = cls.pe.get_memory_mapped_image()
        cls.md = Cs(CS_ARCH_X86, CS_MODE_32)
        cls.md.skipdata = True

    def _insns(self, start: int, end: int):
        return list(self.md.disasm(self.image[start - 0x400000:end - 0x400000], start))

    def test_vtable(self) -> None:
        slots = struct.unpack_from("<10I", self.image, 0x482208 - 0x400000)
        self.assertEqual(slots[3], HANDLER)
        self.assertEqual(slots[8], UPDATE)

    def test_the_only_name_box_write_backs_are_the_three_handlers(self) -> None:
        text = next(s for s in self.pe.sections if s.Name.startswith(b".text"))
        sites = [i.address for i in self.md.disasm(text.get_data(), 0x400000 + text.VirtualAddress)
                 if i.mnemonic == "call" and i.op_str == "0x40bb70" and 0x449000 <= i.address < 0x44B000]
        self.assertEqual(sites, [0x44A748, 0x44A7A4, 0x44A859])

    def test_the_reload_flag_and_the_refill(self) -> None:
        writes = [(i.address, i.op_str) for i in self._insns(0x449000, 0x44A8E0)
                  if i.mnemonic == "mov" and i.op_str.startswith("byte ptr [esi + 0x24],")]
        self.assertEqual(writes, [(0x4498EA, "byte ptr [esi + 0x24], 1"), (0x44A64E, "byte ptr [esi + 0x24], bl"),
                                  (0x44A751, "byte ptr [esi + 0x24], 1"), (0x44A7AC, "byte ptr [esi + 0x24], 1"),
                                  (0x44A861, "byte ptr [esi + 0x24], 1")])
        # The update's only setText is the name box, behind the flag.
        update = self._insns(UPDATE, 0x44A6F2)
        self.assertEqual([i.address for i in update if i.mnemonic == "call" and i.op_str == "0x40bb30"], [0x44A67D])
        self.assertEqual((update[4].mnemonic, update[4].op_str), ("mov", "al, byte ptr [esi + 0x24]"))

    def test_the_gap_is_padding_nothing_jumps_into(self) -> None:
        self.assertEqual(self.image[0x44A6F2 - 0x400000:0x44A700 - 0x400000], b"\x90" * 14)
        text = next(s for s in self.pe.sections if s.Name.startswith(b".text"))
        for i in self.md.disasm(text.get_data(), 0x400000 + text.VirtualAddress):
            if i.mnemonic == "call" or i.mnemonic.startswith("j"):
                try:
                    target = int(i.op_str, 16)
                except ValueError:
                    continue
                self.assertFalse(0x44A6F2 <= target < 0x44A700, hex(i.address))

    def test_every_queued_event_is_handled_before_the_frame(self) -> None:
        loop = self._insns(0x403970, 0x403C88)
        thunk = self._insns(0x44A9EE, 0x44A9F4)[0]
        sdl_poll = next(f.address for e in self.pe.DIRECTORY_ENTRY_IMPORT for f in e.imports
                        if f.name == b"SDL_PollEvent")
        self.assertEqual((thunk.mnemonic, thunk.op_str), ("jmp", "dword ptr [0x%x]" % sdl_poll))
        polls = [i.address for i in loop if i.mnemonic == "call" and i.op_str == "0x44a9ee"]
        self.assertEqual(polls, [0x403983, 0x403C78])
        back = next(i for i in loop if i.address == 0x403C82)
        self.assertEqual((back.mnemonic, back.op_str), ("jne", "0x4039a0"))


class LaterGamesRefillSynchronouslyTests(unittest.TestCase):
    """The Lost Children .. New Believers: the name box is refilled in the same
    handler that changes the selection, and when the screen is shown; the
    per-frame update never touches it.  So no game but A New Home has the bug.

    game: (vtable, name box field, getText, setText, the write-back sites,
           the selection's store, the refill after it, show handler's refill)
    """

    GAMES = {
        # The Lost Children: arrows inline in the handler 0x467720; the
        # refill 0x467945 follows both arrows' stores (0x46782B, 0x467908).
        "vv2": dict(vtable=0x490430, box=0x500, get=0x40C550, set=0x40C510,
                    writes=[0x467767, 0x4677F8, 0x4678C6], select_range=(0x46778D, 0x46794A),
                    refill=0x467945, show=0x466370, show_refill=0x4663A6),
        # The Secret City: arrows call select 0x46E460 (write-back 0x46E4A6,
        # store 0x46E4E7, refill 0x46E516); Done writes back at 0x46E581.
        "vv3": dict(vtable=0x49EAD0, box=0x308, get=0x40D1E0, set=0x40D1A0,
                    writes=[0x46E4A6, 0x46E581], select_range=(0x46E460, 0x46E51F),
                    refill=0x46E516, show=0x46E410, show_refill=0x46E449),
        "vv4": dict(vtable=0x48EFFC, box=0xA4, get=0x40D420, set=0x40D3E0,
                    writes=[0x448580, 0x448667], select_range=(0x448520, 0x448608),
                    refill=0x4485F3, show=0x4484E0, show_refill=0x448516),
        "vv5": dict(vtable=0x49A594, box=0xA8, get=0x40D910, set=0x40D8D0,
                    writes=[0x44BB90, 0x44BC77], select_range=(0x44BB30, 0x44BC18),
                    refill=0x44BC03, show=0x44BAF0, show_refill=0x44BB26),
    }

    def _setup(self, game):
        pe = pefile.PE(str(STOCK_DIR / EXES[game]))
        image = pe.get_memory_mapped_image()
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.skipdata = True
        text = next(s for s in pe.sections if s.Name.startswith(b".text"))
        everything = list(md.disasm(text.get_data(), 0x400000 + text.VirtualAddress))
        return pe, image, md, everything

    @staticmethod
    def _box_of(insns, index):
        """The ECX a call at insns[index] is made with (the last `mov ecx` before it)."""
        for j in range(index - 1, max(index - 12, 0), -1):
            if insns[j].mnemonic == "mov" and insns[j].op_str.startswith("ecx,"):
                return insns[j].op_str
        return None

    def test_each_game(self) -> None:
        for game, g in self.GAMES.items():
            with self.subTest(game=game):
                pe, image, md, everything = self._setup(game)
                slots = struct.unpack_from("<10I", image, g["vtable"] - 0x400000)
                self.assertEqual(slots[9], g["show"])
                box = "ecx, dword ptr [esi + 0x%x]" % g["box"]
                by_address = {i.address: n for n, i in enumerate(everything)}
                # Every write-back of this screen's name box.
                writes = [i.address for n, i in enumerate(everything)
                          if i.mnemonic == "call" and i.op_str == hex(g["get"]) and self._box_of(everything, n) == box]
                self.assertEqual(writes, g["writes"])
                # Every refill of the name box: the select/arrow path and the show handler.
                refills = [i.address for n, i in enumerate(everything)
                           if i.mnemonic == "call" and i.op_str == hex(g["set"]) and self._box_of(everything, n) == box]
                self.assertEqual(sorted(refills), sorted([g["refill"], g["show_refill"]]))
                lo, hi = g["select_range"]
                self.assertTrue(lo <= g["refill"] < hi)
                # The per-frame update (vtable +0x20) never sets the name box.
                update = slots[8]
                n = by_address[update]
                while everything[n].mnemonic != "ret":
                    if everything[n].mnemonic == "call" and everything[n].op_str == hex(g["set"]):
                        self.assertNotEqual(self._box_of(everything, n), box)
                    n += 1


if __name__ == "__main__":
    unittest.main()
