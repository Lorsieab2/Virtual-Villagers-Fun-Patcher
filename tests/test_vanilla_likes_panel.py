"""Fix Vanilla Bugs, all five games: the Details screen's Likes and Dislikes.

The stock Details panel builds each line from a slot list (4 slots in A New
Home at +0x398 / +0x3A8, 62 in The Lost Children at +0x5F0 / +0x6E8, 3 in the
later games) and the game's own comma-separated word list.

A New Home (0x43BA20 / 0x43BAF0, called from 0x449140) and The Lost Children
(0x44B7E0 / 0x44B8B0, called from 0x4654B0) copy the list into a stack buffer
and then, for each slot,
  1. copy the chosen word up to the next comma -- the list's LAST word
     ("sleeping" / "dirt") has none, so the copy runs on past the list's NUL
     through whatever the stack holds; the NUL it copied ends the line early,
     so every later filled slot vanishes (or stray bytes show);
  2. count commas with no end check -- an index past the end of the list walks
     into stale stack bytes and shows garbage;
  3. append into a 256-byte stack buffer and sprintf it (as a format!) into the
     caller's 256-byte buffer, with no bound -- The Lost Children's 62 slots
     overflow both (four slots of the longest word, A New Home's worst case,
     are 52 characters and fit).
The fix rewrites each builder in place, in its own 0xC8 bytes, as one bounded
loop over the list the game's own text lookup returns: no copy of the list, a
word stops at a comma or at the list's end, a negative slot or one past the end
is skipped, and at most 255 characters plus the NUL are written into the
caller's buffer, a line that does not fit ending in "...".  Words and commas are
joined exactly as the stock code joins them (each word keeps the space that
follows the list's comma), so every line the stock code shows correctly is
shown byte for byte the same.

The Secret City, The Tree of Life and New Believers already stop at the list's
NUL and bound their 1024-byte global buffer (3 slots cannot fill it), but like
the two earlier games show a negative slot other than -1 as the list's first
word ("ants"); their 'cmp edi,-1; je skip' becomes 'cmp edi,0; jl skip', so
every negative slot is left out in all five games.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc, UcError
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX,
    UC_X86_REG_EDI, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    load_builds,
    load_fun_patches,
    load_public_fun_patches,
    render_patched_bytes,
)

STOCK_DIR = ROOT / "research" / "stock-executables"
EXES = {
    "vv1": "Virtual Villagers - A New Home.exe",
    "vv2": "Virtual Villagers - The Lost Children.exe",
    "vv3": "Virtual Villagers - The Secret City.exe",
    "vv4": "Virtual Villagers - The Tree of Life.exe",
    "vv5": "Virtual Villagers - New Believers.exe",
}
MODES = ("stock", "collection_progression", "immediate_fixed")
BUILDER_LEN = 0xC8

_TAIL = (
    "8B0E89D885C97C3F740F8A104084D2743680FA2C75F44975F18A1084D2742880FA2C74233B7C241C740839EF"
    "7323C6072C478A1084D2740F80FA2C740A39EF731088174740EBEB83C604FF0C2475B1EB09C745FD2E2E2E00"
    "89EF59C6070089F82B4424185D5F5E5BC20800" + "CC" * 40
)


def _builder(table: int, sid: int, call_rel: int, stride: int, slots: int, count: int) -> bytes:
    """The rewritten builder: prologue (text lookup, slot pointer, output
    bounds) then the shared loop, padded with int3 to the stock 0xC8 bytes."""
    head = (
        bytes.fromhex("5356575589CE8B8E") + struct.pack("<I", table)
        + b"\x68" + struct.pack("<I", sid) + b"\xE8" + struct.pack("<i", call_rel)
        + bytes.fromhex("89C38B44241469C0") + struct.pack("<I", stride)
        + bytes.fromhex("8DB406") + struct.pack("<I", slots)
        + bytes.fromhex("8B7C24188DAFFF0000006A") + bytes([count])
    )
    code = head + bytes.fromhex(_TAIL)
    assert len(code) == BUILDER_LEN
    return code


# (game, address, string id, slot offset); stock bytes are read from the exe.
BUILDERS = {
    "vv1": [(0x43BA20, 0xD5, 0x398), (0x43BAF0, 0xD6, 0x3A8)],
    "vv2": [(0x44B7E0, 0x144, 0x5F0), (0x44B8B0, 0x145, 0x6E8)],
}
LOOKUP = {"vv1": 0x433970, "vv2": 0x441680}
TEXT_TABLE = {"vv1": 0x3E02C, "vv2": 0xE574F0}
STRIDE = {"vv1": 0x3D8, "vv2": 0xE48C}
SLOTS = {"vv1": 4, "vv2": 62}
SPRINTF = {"vv1": 0x44B23D, "vv2": 0x4682BD}
LANGUAGES = {"vv1": (0, 1, 2, 3), "vv2": (0, 1)}


def _patched_builder(game: str, address: int, sid: int, slots: int) -> bytes:
    rel = LOOKUP[game] - (address + 0x11 + 5)
    return _builder(TEXT_TABLE[game], sid, rel, STRIDE[game], slots, SLOTS[game])


# The later games' builders: (address of 'cmp edi,-1', builder, getter, lookup, global buffer).
NEGATIVE = {
    "vv3": [(0x45537C, 0x455350, 0x42F740, 0x42F190, 0x59DC08), (0x4547FC, 0x4547D0, 0x42F740, 0x42F190, 0x596FE0)],
    "vv4": [(0x45D79C, 0x45D770, 0x44DA20, 0x44D3D0, 0x50E150), (0x45D23C, 0x45D210, 0x44DA20, 0x44D3D0, 0x5021B8)],
    "vv5": [(0x464FDC, 0x464FB0, 0x450D40, 0x4506D0, 0x553D30), (0x464A3C, 0x464A10, 0x450D40, 0x4506D0, 0x547D98)],
}


def _stock(game: str) -> bytes:
    return (STOCK_DIR / EXES[game]).read_bytes()


def likes_fixes(game: str) -> tuple:
    """(file offset, stock bytes, patched bytes) of this fix in `game`'s
    Fix Vanilla Bugs row, in the row's order.

    Called by the other Fix Vanilla Bugs tests at import time to build their FIXES tables, so it
    must not need the stock executable then: with none (a clean checkout, CI -- research/
    stock-executables is not committed) it returns (), and every test that needs these bytes also
    reads the stock executable itself and is skipped as a missing input by tests/conftest.py."""
    if not (STOCK_DIR / EXES[game]).is_file():
        return ()
    stock = _stock(game)
    if game in BUILDERS:
        out = []
        for address, sid, slots in BUILDERS[game]:
            off = address - 0x400000
            out.append((off, stock[off:off + BUILDER_LEN], _patched_builder(game, address, sid, slots)))
        return tuple(out)
    return tuple((a - 0x400000, bytes.fromhex("83FFFF") + stock[a - 0x400000 + 3:a - 0x400000 + 4],
                  bytes.fromhex("83FF007C")) for a, *_ in NEGATIVE[game])


def _build(game: str):
    return next(b for b in load_builds() if b.id == game)


def _render(game: str, mode: str, ids) -> bytes:
    rendered, _ = render_patched_bytes(STOCK_DIR / EXES[game], _build(game), mode, list(ids))
    return bytes(rendered)


STACK = 0x70000000
THIS = 0x20000000
TEXT = 0x30000000
OUT = 0x40000000
RETURN = 0x0BAD0000
CANARY = b"\xEE" * 64
GARBAGE = b"GARBAGE,"


class _Machine:
    def __init__(self, exe: bytes) -> None:
        pe = pefile.PE(data=exe)
        image = pe.get_memory_mapped_image()
        self.mu = mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(0x400000, (len(image) + 0xFFFF) & ~0xFFFF)
        mu.mem_write(0x400000, image)
        mu.mem_map(STACK - 0x10000, 0x20000)
        mu.mem_map(THIS, 0x1000000)
        mu.mem_map(TEXT, 0x1000)
        mu.mem_map(OUT, 0x1000)
        mu.mem_map(RETURN, 0x1000)
        self.calls = []

    def run(self, start: int, esp: int, count: int = 2_000_000):
        try:
            self.mu.emu_start(start, RETURN, count=count)
        except UcError as error:
            return error
        if self.mu.reg_read(UC_X86_REG_EIP) != RETURN:
            return "did not return"
        return None


def _list_text(exe: bytes, game: str, sid: int, language: int) -> bytes:
    """The word list the game's own text lookup returns."""
    m = _Machine(exe)
    m.mu.mem_write(TEXT, struct.pack("<II", 0, TEXT + 0x100))
    m.mu.mem_write(TEXT + 0x100, struct.pack("<i", language))
    top = STACK - 0x100
    m.mu.mem_write(top, struct.pack("<II", RETURN, sid))
    m.mu.reg_write(UC_X86_REG_ESP, top)
    m.mu.reg_write(UC_X86_REG_ECX, TEXT)
    assert m.run(LOOKUP[game], top) is None
    pointer = m.mu.reg_read(UC_X86_REG_EAX)
    text = bytes(m.mu.mem_read(pointer, 0x1000))
    return text[:text.index(b"\0")]


def _run_builder(exe: bytes, game: str, address: int, slot_offset: int, values, language: int = 0, index: int = 3):
    """Call a VV1/VV2 builder as 0x449140 / 0x4654B0 does; return (text,
    canary intact, error, return-contract ok, sprintf calls)."""
    m = _Machine(exe)
    mu = m.mu
    mu.mem_write(THIS + TEXT_TABLE[game], struct.pack("<I", TEXT))
    mu.mem_write(TEXT, struct.pack("<II", 0, TEXT + 0x100))
    mu.mem_write(TEXT + 0x100, struct.pack("<i", language))
    record = THIS + index * STRIDE[game]
    slots = list(values) + [-1] * (SLOTS[game] - len(values))
    for base in (0x398, 0x3A8) if game == "vv1" else (0x5F0, 0x6E8):
        mu.mem_write(record + base, struct.pack("<%di" % SLOTS[game], *([-1] * SLOTS[game])))
    mu.mem_write(record + slot_offset, struct.pack("<%di" % SLOTS[game], *slots))
    # Stale stack bytes below the caller, as a real stack holds them.
    mu.mem_write(STACK - 0x10000, GARBAGE * (0x10000 // len(GARBAGE)))
    mu.mem_write(OUT, b"\0" * 256 + CANARY)
    top = STACK - 0x100
    mu.mem_write(top, struct.pack("<III", RETURN, index, OUT))
    mu.reg_write(UC_X86_REG_ESP, top)
    mu.reg_write(UC_X86_REG_ECX, THIS)
    saved = (0x5EED0001, 0x5EED0002, 0x5EED0003, 0x5EED0004)
    for reg, value in zip((UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP), saved):
        mu.reg_write(reg, value)
    sprintf_calls = []

    def on_code(uc, addr, size, user_data):
        if addr != SPRINTF[game]:
            return
        esp = uc.reg_read(UC_X86_REG_ESP)
        ret, dst, src = struct.unpack("<III", uc.mem_read(esp, 12))
        text = bytes(uc.mem_read(src, 0x2000))
        text = text[:text.index(b"\0")] if b"\0" in text else text
        sprintf_calls.append(len(text))
        uc.mem_write(dst, text + b"\0")
        uc.reg_write(UC_X86_REG_EAX, len(text))
        uc.reg_write(UC_X86_REG_ESP, esp + 4)
        uc.reg_write(UC_X86_REG_EIP, ret)

    mu.hook_add(UC_HOOK_CODE, on_code)
    error = m.run(address, top)
    out = bytes(mu.mem_read(OUT, 256 + len(CANARY)))
    text = out[:out.index(b"\0")] if b"\0" in out else out
    contract = error is None and mu.reg_read(UC_X86_REG_ESP) == top + 12 and tuple(
        mu.reg_read(r) for r in (UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP)) == saved
    return text, out[256:] == CANARY, error, contract, sprintf_calls


def expected(words_text: bytes, values) -> bytes:
    """What the fixed panel shows: each valid slot's word, joined by commas as
    the base game joins them, at most 255 characters ending in '...'."""
    words = words_text.split(b",")
    shown = [words[v] for v in values if 0 <= v < len(words) and words[v]]
    line = b",".join(shown)
    if len(line) > 255:
        line = line[:252] + b"..."
    return line


class ManifestTests(unittest.TestCase):
    def test_rows_carry_the_fix_and_say_so(self) -> None:
        rows = {p.id: p.raw for p in load_fun_patches()}
        public = {p.id for p in load_public_fun_patches()}
        for game in EXES:
            with self.subTest(game=game):
                raw = rows[f"{game}_fix_vanilla_bugs"]
                self.assertIn(f"{game}_fix_vanilla_bugs", public)
                pinned = [(int(p["offset"], 16), bytes.fromhex(p["before"]), bytes.fromhex(p["after"]))
                          for p in raw["patches"]]
                for fix in likes_fixes(game):
                    self.assertIn(fix, pinned)
                description = raw["description"]
                self.assertTrue(description.endswith("**Needs no other patch.**"))
                if game in BUILDERS:
                    self.assertIn("The Likes and Dislikes on the Details screen are always shown correctly", description)
                    self.assertIn("sleeping" if game == "vv1" else "dirt", description)
                    self.assertIn("a number that is not a word is left out", description)
                else:
                    self.assertIn("left out of the Details screen instead of being shown as \"ants\"", description)
                if game == "vv2":
                    self.assertIn("ends in \"...\"", description)

    def test_stock_bytes_are_the_builders(self) -> None:
        for game in BUILDERS:
            stock = _stock(game)
            for (offset, before, _after), (address, sid, slots) in zip(likes_fixes(game), BUILDERS[game]):
                with self.subTest(game=game, address=hex(address)):
                    self.assertEqual(before[:6], bytes.fromhex("81ECC4030000"))       # sub esp,0x3C4
                    self.assertEqual(before[-3:], bytes.fromhex("C20800"))            # ret 8
                    self.assertEqual(stock[offset + BUILDER_LEN:offset + BUILDER_LEN + 8], b"\x90" * 8)
                    self.assertIn(struct.pack("<I", sid), before)
                    self.assertIn(struct.pack("<I", slots), before)
        for game, sites in NEGATIVE.items():
            stock = _stock(game)
            for cmp_at, *_ in sites:
                o = cmp_at - 0x400000
                self.assertEqual(stock[o:o + 3], bytes.fromhex("83FFFF"))
                self.assertEqual(stock[o + 3], 0x74)
                self.assertEqual(stock[o + 5:o + 7], bytes.fromhex("33ED"))   # the scan follows

    def test_patched_builders_decode_and_only_call_the_lookup(self) -> None:
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        for game in BUILDERS:
            for (offset, _before, after), (address, _sid, _slots) in zip(likes_fixes(game), BUILDERS[game]):
                with self.subTest(game=game, address=hex(address)):
                    listing = list(md.disasm(after, address))
                    end = next(i for i in listing if i.mnemonic == "ret")
                    self.assertEqual(end.op_str, "8")
                    self.assertTrue(all(b == 0xCC for b in after[end.address + 3 - address:]))
                    calls = [i.op_str for i in listing if i.mnemonic == "call"]
                    self.assertEqual(calls, [hex(LOOKUP[game])])
                    jumps = [int(i.op_str, 16) for i in listing if i.mnemonic.startswith("j")]
                    self.assertTrue(all(address <= t <= end.address for t in jumps))

    def test_nothing_else_branches_into_the_builders(self) -> None:
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.skipdata = True
        for game in BUILDERS:
            pe = pefile.PE(str(STOCK_DIR / EXES[game]))
            text = next(s for s in pe.sections if s.Name.startswith(b".text"))
            starts = [a for a, *_ in BUILDERS[game]]
            incoming = []
            for ins in md.disasm(text.get_data(), 0x400000 + text.VirtualAddress):
                if not (ins.mnemonic.startswith("j") or ins.mnemonic == "call"):
                    continue
                try:
                    target = int(ins.op_str, 16)
                except ValueError:
                    continue
                for start in starts:
                    if start < target < start + BUILDER_LEN and not start <= ins.address < start + BUILDER_LEN:
                        incoming.append((hex(ins.address), hex(target)))
            with self.subTest(game=game):
                self.assertEqual(incoming, [])

    def test_render_in_every_mode_alone_and_with_every_other_patch(self) -> None:
        for game in EXES:
            fid = f"{game}_fix_vanilla_bugs"
            others = [p.id for p in load_public_fun_patches() if p.game_id == game and p.id != fid]
            sets = [[], others]
            if game in NEGATIVE:
                sets.append(others + [f"{game}_population_256"])
            for mode in MODES:
                for extra in sets:
                    with self.subTest(game=game, mode=mode, others=len(extra)):
                        without = _render(game, mode, extra)
                        rendered = _render(game, mode, extra + [fid])
                        for offset, before, after in likes_fixes(game):
                            self.assertEqual(without[offset:offset + len(before)], before)
                            self.assertEqual(rendered[offset:offset + len(after)], after)


class EarlyGamesEmulationTests(unittest.TestCase):
    """The real builders, stock and patched, called with the caller's contract."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.exes = {}
        for game in BUILDERS:
            cls.exes[(game, "base")] = _stock(game)
            for mode in MODES:
                cls.exes[(game, mode)] = _render(game, mode, [f"{game}_fix_vanilla_bugs"])
        cls.lists = {}
        for game in BUILDERS:
            for _address, sid, _slots in BUILDERS[game]:
                for language in LANGUAGES[game]:
                    cls.lists[(game, sid, language)] = _list_text(cls.exes[(game, "base")], game, sid, language)

    def _cases(self):
        for game in BUILDERS:
            for address, sid, slots in BUILDERS[game]:
                yield game, address, sid, slots

    def test_word_lists(self) -> None:
        self.assertTrue(self.lists[("vv1", 0xD5, 0)].endswith(b", jokes, sleeping"))
        self.assertEqual(self.lists[("vv1", 0xD5, 0)].count(b",") + 1, 47)
        self.assertTrue(self.lists[("vv2", 0x144, 0)].endswith(b", clouds, dirt"))
        self.assertEqual(self.lists[("vv2", 0x144, 0)].count(b",") + 1, 62)
        for (game, sid, language), text in self.lists.items():
            with self.subTest(game=game, sid=sid, language=language):
                self.assertFalse(text.endswith(b","))
                self.assertNotIn(b"%", text)

    def test_valid_slots_show_exactly_what_the_base_game_shows(self) -> None:
        for game, address, sid, slots in self._cases():
            n = self.lists[(game, sid, 0)].count(b",") + 1
            samples = [[0], [5, 0], [n - 2, 1, 2], [-1, 3, -1, 7], []]
            for values in samples:
                values = values[:SLOTS[game]]
                stock = _run_builder(self.exes[(game, "base")], game, address, slots, values)
                for mode in MODES:
                    with self.subTest(game=game, builder=hex(address), values=values, mode=mode):
                        text, canary, error, contract, calls = _run_builder(self.exes[(game, mode)], game, address, slots, values)
                        self.assertTrue(contract, error)
                        self.assertTrue(canary)
                        self.assertEqual(calls, [])
                        self.assertEqual(text, stock[0])
                        self.assertEqual(text, expected(self.lists[(game, sid, 0)], values))

    def test_a_the_last_word_shows_and_later_slots_still_show(self) -> None:
        for game, address, sid, slots in self._cases():
            for language in LANGUAGES[game]:
                words = self.lists[(game, sid, language)]
                last = words.count(b",")
                values = [last, 0, 5] if game == "vv1" else [3, last, 0, 5, 9]
                want = expected(words, values)
                self.assertTrue(want.endswith(words.split(b",")[5]) if game == "vv1" else want.endswith(words.split(b",")[9]))
                stock = _run_builder(self.exes[(game, "base")], game, address, slots, values, language)
                with self.subTest(game=game, builder=hex(address), language=language, build="stock"):
                    self.assertNotEqual(stock[0], want)          # the base game's bug
                for mode in MODES:
                    with self.subTest(game=game, builder=hex(address), language=language, mode=mode):
                        text, canary, error, contract, _ = _run_builder(self.exes[(game, mode)], game, address, slots, values, language)
                        self.assertTrue(contract, error)
                        self.assertTrue(canary)
                        self.assertEqual(text, want)
                        self.assertIn(words.split(b",")[last], text)

    def test_b_indexes_past_the_end_and_negative_indexes_are_skipped(self) -> None:
        for game, address, sid, slots in self._cases():
            words = self.lists[(game, sid, 0)]
            n = words.count(b",") + 1
            for bad in (n, n + 3, 1000, 0x7FFFFFFF, -2, -1000, -0x80000000):
                values = [1, bad, 2]
                want = expected(words, values)
                self.assertEqual(want, words.split(b",")[1] + b"," + words.split(b",")[2])
                stock = _run_builder(self.exes[(game, "base")], game, address, slots, values)
                with self.subTest(game=game, builder=hex(address), bad=bad, build="stock"):
                    self.assertNotEqual(stock[0], want)
                    if bad >= n:
                        self.assertTrue(stock[2] is not None or b"GARBAGE" in stock[0] or not stock[1], stock[0][:40])
                    else:
                        self.assertIn(words.split(b",")[0], stock[0])   # stock shows "ants"
                for mode in MODES:
                    with self.subTest(game=game, builder=hex(address), bad=bad, mode=mode):
                        text, canary, error, contract, _ = _run_builder(self.exes[(game, mode)], game, address, slots, values)
                        self.assertTrue(contract, error)
                        self.assertTrue(canary)
                        self.assertEqual(text, want)

    def test_a_new_home_can_never_reach_its_buffer(self) -> None:
        for language in LANGUAGES["vv1"]:
            for sid in (0xD5, 0xD6):
                words = self.lists[("vv1", sid, language)].split(b",")
                longest = max(len(w) for w in words)
                self.assertLess(4 * longest + 3, 255)

    def test_c_the_lost_children_all_62_slots_never_overflow(self) -> None:
        for address, sid, slots in BUILDERS["vv2"]:
            for language in LANGUAGES["vv2"]:
                words = self.lists[("vv2", sid, language)]
                split = words.split(b",")
                longest = max(range(len(split)), key=lambda i: len(split[i]))
                for values in ([longest] * 62, list(range(62)), list(range(61, -1, -1))):
                    want = expected(words, values)
                    self.assertEqual(len(want), 255)
                    self.assertTrue(want.endswith(b"..."))
                    stock = _run_builder(self.exes[("vv2", "base")], "vv2", address, slots, values, language)
                    with self.subTest(builder=hex(address), language=language, first=values[0], build="stock"):
                        if values[0] >= len(split) - 1:
                            # the last word (or, in the 47-word German list, a
                            # number past it) first: the line is cut short or garbled
                            self.assertNotEqual(stock[0], want)
                        else:
                            # the base game writes past the 256-byte buffer (or faults)
                            self.assertTrue(stock[2] is not None or not stock[1])
                    for mode in MODES:
                        with self.subTest(builder=hex(address), language=language, first=values[0], mode=mode):
                            text, canary, error, contract, _ = _run_builder(self.exes[("vv2", mode)], "vv2", address, slots, values, language)
                            self.assertTrue(contract, error)
                            self.assertTrue(canary)
                            self.assertEqual(text, want)


class LaterGamesEmulationTests(unittest.TestCase):
    """The Secret City, The Tree of Life, New Believers: the real builders with
    the text getter and lookup answered with the exe's own English word list."""

    @staticmethod
    def _list(exe: bytes) -> int:
        at = exe.find(b"ants, crowds, resting")
        while exe[at - 1] not in (0,):
            at -= 1
        pe = pefile.PE(data=exe, fast_load=True)
        return 0x400000 + pe.get_rva_from_offset(at)

    def _run(self, exe: bytes, site, values):
        _cmp, builder, getter, lookup, buffer = site
        m = _Machine(exe)
        mu = m.mu
        listing = self._list(exe)
        mu.mem_write(THIS, struct.pack("<3i", *values))
        top = STACK - 0x100
        mu.mem_write(top, struct.pack("<I", RETURN))
        mu.reg_write(UC_X86_REG_ESP, top)
        mu.reg_write(UC_X86_REG_ECX, THIS)

        def on_code(uc, addr, size, user_data):
            if addr not in (getter, lookup):
                return
            esp = uc.reg_read(UC_X86_REG_ESP)
            ret = struct.unpack("<I", uc.mem_read(esp, 4))[0]
            uc.reg_write(UC_X86_REG_EAX, TEXT if addr == getter else listing)
            uc.reg_write(UC_X86_REG_ESP, esp + (4 if addr == getter else 8))
            uc.reg_write(UC_X86_REG_EIP, ret)

        mu.hook_add(UC_HOOK_CODE, on_code)
        self.assertIsNone(m.run(builder, top))
        self.assertEqual(mu.reg_read(UC_X86_REG_EAX), buffer)
        out = bytes(mu.mem_read(buffer, 1024))
        words = bytes(mu.mem_read(listing, 0x1000))
        return out[:out.index(b"\0")], words[:words.index(b"\0")]

    def test_negative_slots_are_skipped_and_everything_else_is_unchanged(self) -> None:
        for game, sites in NEGATIVE.items():
            stock = _stock(game)
            patched = {mode: _render(game, mode, [f"{game}_fix_vanilla_bugs"]) for mode in MODES}
            for site in sites:
                for values in ([-2, 5, -1], [-1000, -0x80000000, 3], [0, -1, 4], [-1, -1, -1], [7, 2, 0], [500, 1, -5]):
                    s_text, words = self._run(stock, site, values)
                    for mode in MODES:
                        with self.subTest(game=game, builder=hex(site[1]), values=values, mode=mode):
                            text, _ = self._run(patched[mode], site, values)
                            self.assertEqual(text, expected(words, values))
                            if all(v >= 0 or v == -1 for v in values):
                                self.assertEqual(text, s_text)
                            else:
                                self.assertNotEqual(s_text, text)     # stock showed the first word
                                self.assertIn(words.split(b",")[0], s_text.split(b","))


if __name__ == "__main__":
    unittest.main()
