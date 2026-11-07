"""Triple Tech Cost (all five games; ids vv1_triple_tech_cost .. vv5_triple_tech_cost), off by default.

The owner (2026-11-06): "Default OFF: "Triple Tech Cost" = triples all technologies so they have 3x the normal cost.
makes the game super hard." and "7 should be default off for everything. players who want it must explicitly choose
it": Default Patches, Owner's Defaults and Select All leave it unticked.

Where each game keeps its prices, and the change, are in scripts/build_triple_tech_cost_features.py.  These tests
check the manifests against the generator and the stock bytes, and run each game's own Tech screen code from the
stock and the rendered executable in unicorn, for every technology at every level it can be bought from:

  * the hover label and the information box are given the price the game would print (the sprintf argument in A New
    Home and The Lost Children; the price getter's answer at its call in the later games);
  * the purchase is run with exactly the price, and with one point less: with the price it is bought and exactly
    the price is taken, with one less it is refused (the game's own message) and nothing is taken.

Stock gives the stock table, patched exactly 3 times it, all three readers agreeing.  Tests that need the stock
executables or unicorn skip when they are absent (GitHub CI has no stock executables).
"""
from __future__ import annotations

import importlib.util
import json
import re
import struct
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402
import vv_fun_patcher_gui as gui  # noqa: E402

try:
    import capstone
    import pefile
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
    from unicorn.x86_const import (
        UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI, UC_X86_REG_EIP,
        UC_X86_REG_ESI, UC_X86_REG_ESP,
    )
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

_spec = importlib.util.spec_from_file_location(
    "build_triple_tech_cost_features", ROOT / "scripts" / "build_triple_tech_cost_features.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

GAMES = range(1, 6)
IDS = {game: f"vv{game}_triple_tech_cost" for game in GAMES}
BASE = gen.IMAGE_BASE
BUILDS = {game: next(b for b in patcher.load_builds() if b.id == f"vv{game}") for game in GAMES}
MODES = ("stock", "collection_progression", "immediate_fixed")


def stock_path(game: int) -> Path:
    return ROOT / "research" / "stock-executables" / BUILDS[game].input_name


def stock_bytes(game: int) -> bytes:
    path = stock_path(game)
    if not path.is_file():
        raise unittest.SkipTest(f"stock vv{game} exe not present in this checkout")
    return path.read_bytes()


def manifest(game: int) -> dict:
    return json.loads(gen.out_path(game).read_text(encoding="utf-8"))


def stock_table(game: int) -> dict[tuple[str, int], int]:
    """(technology, level bought) -> stock price, from the page's own tables (src/vv_game_mechanics_items_vv<N>)."""
    import vv_game_mechanics_tech_time as tt
    return {(name, level): tt.stock_price(game, name, level) for name, level in tt.every_level(game)}


_RENDERED: dict[tuple[int, str], bytes] = {}


def rendered(game: int, ids: tuple[str, ...]) -> bytes:
    key = (game, ",".join(ids))
    if key not in _RENDERED:
        _RENDERED[key] = bytes(patcher.render_patched_bytes(
            stock_path(game), BUILDS[game], patcher.DEFAULT_PATCH_MODE, list(ids))[0])
    return _RENDERED[key]


# ---------------------------------------------------------------------------------------------------------------
# A small emulator: the image at its base, a stack, a heap for the screen object and the village state, and stubs
# for the routines the Tech screen calls that are not about prices (strings, labels, sounds, messages).
# ---------------------------------------------------------------------------------------------------------------
HEAP, HEAP_SIZE = 0x10000000, 0x100000
STACK, STACK_SIZE = 0x30000000, 0x100000
SENTINEL = 0x50000000
STRING_TAG = 0x20000000          # a stubbed string getter returns STRING_TAG | id (never dereferenced)


class Emu:
    def __init__(self, exe: bytes):
        pe = pefile.PE(data=exe, fast_load=True)
        image = pe.get_memory_mapped_image()
        size = (len(image) + 0xFFFF) & ~0xFFFF
        self.uc = Uc(UC_ARCH_X86, UC_MODE_32)
        self.uc.mem_map(BASE, size)
        self.uc.mem_write(BASE, image)
        self.uc.mem_map(HEAP, HEAP_SIZE)
        self.uc.mem_map(STACK, STACK_SIZE)
        self.uc.mem_map(SENTINEL, 0x1000)
        self.uc.mem_map(0, 0x1000)                 # fs:[0] (the routines' exception frames; fs base 0)
        self.uc.mem_write(SENTINEL, b"\xC3")
        self.stubs: dict[int, tuple[int, object]] = {}
        self.stops: set[int] = {SENTINEL}
        self.calls: list[tuple[int, list[int]]] = []
        self.stopped_at = None
        self.uc.hook_add(UC_HOOK_CODE, self._hook)

    def reset(self) -> "Emu":
        """Ready for the next run: no stubs, calls or stops, an empty heap (the image keeps the run's writes to the
        levels and points, which every run sets again)."""
        self.stubs, self.stops, self.calls, self.stopped_at = {}, {SENTINEL}, [], None
        self.uc.mem_write(HEAP, bytes(HEAP_SIZE))
        return self

    def stub(self, address: int, args: int, result=0, stop: bool = False) -> None:
        """A callee-clean routine of `args` dword arguments returning `result` (or result(args))."""
        self.stubs[address] = (args, result, stop)

    def dword(self, address: int) -> int:
        return struct.unpack("<i", self.uc.mem_read(address, 4))[0]

    def put(self, address: int, value: int) -> None:
        self.uc.mem_write(address, struct.pack("<i", value))

    def _hook(self, uc, address, size, user):
        if address in self.stops:
            self.stopped_at = address
            uc.emu_stop()
            return
        if address in self.stubs:
            args, result, stop = self.stubs[address]
            esp = uc.reg_read(UC_X86_REG_ESP)
            ret = struct.unpack("<I", uc.mem_read(esp, 4))[0]
            values = list(struct.unpack(f"<{max(args, 8)}I", uc.mem_read(esp + 4, 4 * max(args, 8))))
            self.calls.append((address, values))
            if stop:
                self.stopped_at = address
                uc.emu_stop()
                return
            uc.reg_write(UC_X86_REG_EAX, result(values) if callable(result) else result)
            uc.reg_write(UC_X86_REG_ESP, esp + 4 + 4 * args)
            uc.reg_write(UC_X86_REG_EIP, ret)

    def run(self, start: int, regs: dict, stack: list[int]) -> None:
        esp = STACK + STACK_SIZE - 0x1000 - 4 * len(stack)
        self.uc.mem_write(esp, b"".join(struct.pack("<I", v & 0xFFFFFFFF) for v in stack))
        self.uc.reg_write(UC_X86_REG_ESP, esp)
        for reg, value in regs.items():
            self.uc.reg_write(reg, value & 0xFFFFFFFF)
        self.uc.emu_start(start, 0, count=20_000)
        if self.stopped_at is None:
            raise AssertionError(f"emulation from {start:#x} ran away")


_EMUS: dict[int, "Emu"] = {}


def fresh(exe: bytes) -> "Emu":
    """One emulator per executable (each new one maps the whole image), reset for each run."""
    if id(exe) not in _EMUS:
        _EMUS[id(exe)] = Emu(exe)
    return _EMUS[id(exe)].reset()


def string_result(values: list[int]) -> int:
    return STRING_TAG | (values[0] & 0xFFFF)


def printed_price(values: list[int], count: int) -> int:
    """The price among a sprintf's `count` arguments after the buffer and the format: the one number that is not a
    string or the level (the hover label: string, price, string; the information box: name, string, level, string,
    price, string)."""
    numbers = [v for v in values[2:2 + count] if not v & STRING_TAG]
    return numbers[-1]


# A New Home and The Lost Children: the screen object (esi) and the village state ([esi + 0xC]).
SCREEN = HEAP
STATE = HEAP + 0x1000
IMMEDIATE = {
    1: dict(levels={"Farming": 0xA2E4, "Fertility": 0xA2DC, "Science": 0xA2C4, "Medicine": 0xA2D4,
                    "Construction": 0xA2CC, "Spirituality": 0xA2BC}, points=0xA2FC,
            string=0x433970, label=0x40BB30, rect=0x417BF0, sprintf=0x44B23D, sound=0x431470, message=0x434570,
            clock=0x402F70, bought=0x435DCD, info_first=0x1FB, refused=0x25, buy_order=(
                "Farming", "Fertility", "Science", "Medicine", "Construction", "Spirituality")),
    2: dict(levels={"Culture": 0x2EA74, "Science": 0x2EA7C, "Engineering": 0x2EA84, "Medicine": 0x2EA8C,
                    "Exploration": 0x2EA94, "Farming": 0x2EA9C}, points=0x2EADC,
            string=0x441680, label=0x40C510, rect=0x413590, sprintf=0x4682BD, sound=0x43F010, message=0x442280,
            clock=None, bought=0x443A8D, info_first=0x2DA, refused=0x3F, buy_order=(
                "Farming", "Exploration", "Science", "Medicine", "Engineering", "Culture")),
}
RECT_FIELDS = (0x5C, 0x6C, 0x7C)          # the hover label's first three buttons: x1, y1, x2, y2 inline
RECT_OBJECTS = (0x8C, 0x9C, 0xAC)         # its last three: rect objects tested by the rect routine


def _immediate_emu(game: int, exe: bytes, level: int, points: int = 0) -> "Emu":
    c = IMMEDIATE[game]
    emu = fresh(exe)
    emu.put(SCREEN + 0xC, STATE)
    for offset in c["levels"].values():
        emu.put(STATE + offset, level)
    emu.put(STATE + c["points"], points)
    emu.stub(c["string"], 1, string_result)
    emu.stub(c["label"], 1)
    emu.stub(c["sound"], 1)
    if c["clock"]:
        emu.stub(c["clock"], 0)
    return emu


def hover_prices(game: int, exe: bytes, level: int) -> list[int]:
    """The price the hover label prints for each of the six buttons, every technology at `level`."""
    c = IMMEDIATE[game]
    start = gen.ROUTINES[game]["hover label"][0]
    out = []
    for button in range(6):
        emu = _immediate_emu(game, exe, level)
        for k, field in enumerate(RECT_FIELDS):        # the mouse at (5, 5): inside this button's box only
            box = (0, 0, 10, 10) if k == button else (100, 100, 90, 90)
            for j, v in enumerate(box):
                emu.put(SCREEN + field + 4 * j, v)
        target = SCREEN + RECT_OBJECTS[button - 3] if button >= 3 else None
        emu.stubs[c["rect"]] = (2, lambda values, t=target, e=emu: 1 if e.uc.reg_read(UC_X86_REG_ECX) == t else 0,
                                False)
        emu.stub(c["sprintf"], 0, stop=True)
        emu.run(start, {UC_X86_REG_ECX: SCREEN}, [SENTINEL, 1, 5, 5])
        address, values = emu.calls[-1]
        assert address == c["sprintf"], hex(address)
        out.append(printed_price(values, 3))
    return out


def info_prices(game: int, exe: bytes, level: int) -> list[int]:
    """The price the information box prints for each technology (its six "?" ids), every technology at `level`."""
    c = IMMEDIATE[game]
    start = gen.ROUTINES[game]["information box"][0]
    out = []
    for k in range(6):
        emu = _immediate_emu(game, exe, level)
        emu.stub(c["sprintf"], 0, stop=True)
        emu.run(start, {UC_X86_REG_ECX: SCREEN}, [SENTINEL, c["info_first"] + k])
        address, values = emu.calls[-1]
        assert address == c["sprintf"], hex(address)
        out.append(printed_price(values, 6))
    return out


def buy(game: int, exe: bytes, tech: str, level: int, points: int) -> tuple[bool, int, int, list[int]]:
    """Click tech's buy button with every technology at `level` and `points` tech points: (bought, points after,
    tech's level after, the messages shown)."""
    c = IMMEDIATE[game]
    start = gen.ROUTINES[game]["buy"][0]
    emu = _immediate_emu(game, exe, level, points)
    button = c["buy_order"].index(tech)
    for k in range(6):
        emu.put(SCREEN + 0xC0 + 4 * k, 0x100 + k)
    emu.stub(c["message"], 1)
    emu.stops.add(c["bought"])
    # The buy code runs inside the click handler: esi pushed, then the handler's return and its two arguments.
    emu.run(start, {UC_X86_REG_EAX: 0x100 + button, UC_X86_REG_ESI: SCREEN}, [SCREEN, SENTINEL, 0, 0])
    messages = [values[0] for address, values in emu.calls if address == c["message"]]
    return (emu.stopped_at == c["bought"], emu.dword(STATE + c["points"]), emu.dword(STATE + c["levels"][tech]),
            messages)


# The Secret City, The Tree of Life and New Believers: the getter's callers, each run from the push of its argument
# to the instruction after the call (the price in eax), and the purchase from the same push to after the charge.
TABLE_GAMES = {
    3: dict(levels=0x582618, points=0x582644, label=(0x464E41, UC_X86_REG_EBX, 0x464E4C),
            info=(0x464C7E, UC_X86_REG_EDI, 0x464C89), buy=(0x465700, UC_X86_REG_ESI), bought=0x4657D5,
            message=0x42E0F0, refused=0x34),
    4: dict(levels=0x4D6F5C, points=0x4D6F88, label=(0x43E575, UC_X86_REG_EBP, 0x43E582),
            info=(0x43E8FA, UC_X86_REG_EDI, 0x43E905), buy=(0x43EA70, UC_X86_REG_EDI), bought=0x43EAF8,
            message=0x44C290, refused=0x97),
    5: dict(levels=0x51D5CC, points=0x51D5F8, label=(0x440DC2, UC_X86_REG_EBP, 0x440DCF),
            info=(0x44129A, UC_X86_REG_EDI, 0x4412A5), buy=(0x441670, UC_X86_REG_ESI), bought=0x4416AC,
            message=0x44EF60, refused=0x88),
}


def _table_emu(game: int, exe: bytes, tech_id: int, level: int, points: int = 0) -> "Emu":
    c = TABLE_GAMES[game]
    emu = fresh(exe)
    for k in range(len(gen.TABLES[game][2])):
        emu.put(c["levels"] + 4 * k, 0 if game == 3 and k >= 5 else 1)
    emu.put(c["levels"] + 4 * tech_id, level)
    emu.put(c["points"], points)
    return emu


def getter_price(game: int, exe: bytes, caller: str, tech_id: int, level: int) -> int:
    start, reg, after = TABLE_GAMES[game][caller]
    emu = _table_emu(game, exe, tech_id, level)
    emu.stops.add(after)
    emu.run(start, {reg: tech_id}, [SENTINEL])
    assert emu.stopped_at == after
    return emu.uc.reg_read(UC_X86_REG_EAX)


def table_buy(game: int, exe: bytes, tech_id: int, level: int, points: int) -> tuple[bool, int, list[int]]:
    c = TABLE_GAMES[game]
    start, reg = c["buy"]
    emu = _table_emu(game, exe, tech_id, level, points)
    emu.stub(c["message"], 2, stop=True)
    emu.stops.add(c["bought"])
    if game == 4:
        emu.stub(0x412F90, 2)                      # the purchase's sound
    if game == 3:                                  # a faction's confirmation box: answered "yes"
        screen = HEAP
        emu.stub(0x42F190, 1, string_result)
        emu.stub(0x41C7A0, 3)
        emu.stub(0x401AF0, 2, 0)
        emu.stub(0x41C2F0, 0)
        emu.uc.reg_write(UC_X86_REG_EBX, screen)
        emu.uc.reg_write(UC_X86_REG_EBP, screen)
    emu.run(start, {reg: tech_id}, [SENTINEL, 0, 0, 0])
    messages = [values[0] for address, values in emu.calls if address == c["message"]]
    return emu.stopped_at == c["bought"], emu.dword(c["points"]), messages


# ---------------------------------------------------------------------------------------------------------------
class ManifestTests(unittest.TestCase):
    def test_each_manifest_is_what_the_generator_writes(self):
        for game in GAMES:
            with self.subTest(game=game):
                self.assertEqual(manifest(game), gen.feature(game, stock_bytes(game)))

    def test_one_row_per_game_named_as_the_owner_said(self):
        for game in GAMES:
            with self.subTest(game=game):
                m = manifest(game)
                self.assertEqual((m["id"], m["game_id"], m["name"]), (IDS[game], f"vv{game}", "Triple Tech Cost"))
                self.assertTrue(m["description"].endswith("**Needs no other patch.** Makes the game super hard."))
                self.assertIn("3 times its normal price", m["description"])
                self.assertEqual(m["companion_files"], [])

    def test_every_edit_is_a_price_times_three_in_place(self):
        for game in GAMES:
            stock = stock_bytes(game)
            for p in manifest(game)["patches"]:
                with self.subTest(game=game, offset=p["offset"]):
                    offset = int(p["offset"], 16)
                    before, after = bytes.fromhex(p["before"]), bytes.fromhex(p["after"])
                    self.assertEqual((len(before), len(after)), (4, 4))
                    self.assertEqual(stock[offset:offset + 4], before)
                    old, new = struct.unpack("<i", before)[0], struct.unpack("<i", after)[0]
                    self.assertGreater(old, 0)
                    self.assertEqual(new, 3 * old)

    def test_the_sites_are_every_technology_level(self):
        """The immediates' prices are the page's table (each routine has each price once per technology level;
        the information box shares one site between two levels of the same price); the tables' entries are the
        page's table, every level."""
        for game in (1, 2):
            stock = stock_bytes(game)
            want = Counter(stock_table(game).values())
            sites = gen.immediate_sites(game, stock)
            for routine in gen.ROUTINES[game]:
                got = Counter(value for r, _, value in sites if r == routine)
                with self.subTest(game=game, routine=routine):
                    if routine == "information box":
                        shared = +(want - got)
                        self.assertEqual(sum(shared.values()), 1)
                        self.assertEqual(set(got), set(want))
                    else:
                        self.assertEqual(got, want)
        for game in (3, 4, 5):
            with self.subTest(game=game):
                got = {(name, level): value for name, level, _, value in gen.table_sites(game, stock_bytes(game))}
                self.assertEqual(got, stock_table(game))

    def test_tripled_prices_fit_and_show_at_most_six_digits(self):
        for game in GAMES:
            for (name, level), price in stock_table(game).items():
                with self.subTest(game=game, tech=name, level=level):
                    self.assertLess(3 * price, 2 ** 31)
                    self.assertLessEqual(len(str(3 * price)), 6)

    @unittest.skipUnless(HAVE_EMULATOR, "requires capstone and pefile")
    def test_the_tables_have_one_reader_and_it_has_three_callers(self):
        for game in (3, 4, 5):
            stock = stock_bytes(game)
            getter, table, _ = gen.TABLES[game]
            pe = pefile.PE(data=stock, fast_load=True)
            text = pe.sections[0]
            lo, hi = text.PointerToRawData, text.PointerToRawData + text.SizeOfRawData
            with self.subTest(game=game):
                refs = [m.start() for m in re.finditer(re.escape(struct.pack("<I", table)), stock)]
                self.assertEqual(len(refs), 1)
                self.assertTrue(getter < pe.get_rva_from_offset(refs[0]) + BASE < getter + 0x20)   # its mov eax
                for va in range(table + 4, table + 4 * (3 * len(gen.TABLES[game][2]) + 1), 4):
                    self.assertNotIn(struct.pack("<I", va), stock[lo:hi], hex(va))
                callers = [pe.get_rva_from_offset(o) + BASE for o in range(lo, hi - 5)
                           if stock[o] in (0xE8, 0xE9)
                           and pe.get_rva_from_offset(o) + BASE + 5 + struct.unpack_from("<i", stock, o + 1)[0]
                           == getter]
                self.assertEqual(tuple(callers), gen.GETTER_CALLERS[game])

    def test_no_other_manifest_claims_the_bytes(self):
        for game in GAMES:
            mine = set()
            for p in manifest(game)["patches"]:
                mine |= set(range(int(p["offset"], 16), int(p["offset"], 16) + 4))
            for path in sorted((ROOT / "data").glob("*.json")):
                if path.name == gen.out_path(game).name:
                    continue
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except ValueError:
                    continue
                items = data if isinstance(data, list) else [data] + list(
                    data.get("features", []) if isinstance(data, dict) else [])
                if isinstance(data, dict):
                    items += list(data.get("fun_patches", []))
                for item in items:
                    if not isinstance(item, dict) or item.get("game_id") not in (None, f"vv{game}"):
                        continue
                    for p in item.get("patches", []) or []:
                        try:
                            off = int(str(p.get("offset")), 16)
                            n = len(p.get("before", "")) // 2
                        except (TypeError, ValueError):
                            continue
                        with self.subTest(game=game, other=path.name):
                            self.assertFalse(mine & set(range(off, off + n)), (item.get("id"), p.get("offset")))


@unittest.skipUnless(HAVE_EMULATOR, "requires unicorn, capstone and pefile")
class EmulatedTechScreenTests(unittest.TestCase):
    """Every reader of the prices, from the stock exe and from the patcher's render with the row ticked."""

    def exes(self, game: int):
        stock_bytes(game)
        return (("stock", rendered(game, ()), 1), ("tripled", rendered(game, (IDS[game],)), 3))

    def test_immediate_games_label_box_and_purchase(self):
        for game in (1, 2):
            c = IMMEDIATE[game]
            table = stock_table(game)
            for kind, exe, factor in self.exes(game):
                for level in (1, 2):
                    want = Counter(factor * p for (name, lvl), p in table.items() if lvl == level + 1)
                    with self.subTest(game=game, exe=kind, level=level):
                        self.assertEqual(Counter(hover_prices(game, exe, level)), want)
                        self.assertTrue(set(info_prices(game, exe, level)) <= set(want))
                        self.assertEqual(sorted(info_prices(game, exe, level)), sorted(
                            factor * table[(name, level + 1)] for name in self.info_order(game)))
                    for name in c["levels"]:
                        price = factor * table[(name, level + 1)]
                        with self.subTest(game=game, exe=kind, tech=name, level=level):
                            self.assertEqual(buy(game, exe, name, level, price), (True, 0, level + 1, []))
                            self.assertEqual(buy(game, exe, name, level, price + 7), (True, 7, level + 1, []))
                            self.assertEqual(buy(game, exe, name, level, price - 1),
                                             (False, price - 1, level, [c["refused"]]))

    def info_order(self, game: int) -> list[str]:
        return list(IMMEDIATE[game]["levels"])

    def test_table_games_label_box_and_purchase(self):
        for game in (3, 4, 5):
            c = TABLE_GAMES[game]
            names = gen.TABLES[game][2]
            table = stock_table(game)
            for kind, exe, factor in self.exes(game):
                for (name, bought), stock_price in table.items():
                    tech_id, level, price = names.index(name), bought - 1, factor * stock_price
                    with self.subTest(game=game, exe=kind, tech=name, level=level):
                        self.assertEqual(getter_price(game, exe, "label", tech_id, level), price)
                        self.assertEqual(getter_price(game, exe, "info", tech_id, level), price)
                        self.assertEqual(table_buy(game, exe, tech_id, level, price), (True, 0, []))
                        self.assertEqual(table_buy(game, exe, tech_id, level, price + 7), (True, 7, []))
                        self.assertEqual(table_buy(game, exe, tech_id, level, price - 1),
                                         (False, price - 1, [c["refused"]]))
                for tech_id in range(len(names)):          # the top level: no price, nothing to buy
                    self.assertEqual(getter_price(game, exe, "label", tech_id, 3), 0)

    def test_every_public_patch_in_every_mode_keeps_the_tripled_prices(self):
        public = [p for p in patcher.load_public_fun_patches() if p.id not in patcher.ALTERNATIVE_FUN_PATCH_IDS]
        for game in GAMES:
            stock = stock_bytes(game)
            ids = [p.id for p in public if p.game_id == f"vv{game}"]
            self.assertIn(IDS[game], ids)
            sites = manifest(game)["patches"]
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    exe = bytes(patcher.render_patched_bytes(stock_path(game), BUILDS[game], mode, ids)[0])
                    without = bytes(patcher.render_patched_bytes(
                        stock_path(game), BUILDS[game], mode, [i for i in ids if i != IDS[game]])[0])
                    checksum = struct.unpack_from("<I", stock, 0x3C)[0] + 0x58
                    mine = {o for p in sites for o in range(int(p["offset"], 16), int(p["offset"], 16) + 4)}
                    diff = {i for i in range(len(exe)) if exe[i] != without[i]}
                    self.assertTrue(diff - mine <= set(range(checksum, checksum + 4)), sorted(diff - mine)[:5])
                    for p in sites:
                        o = int(p["offset"], 16)
                        self.assertEqual(exe[o:o + 4].hex().upper(), p["after"])
                        self.assertEqual(without[o:o + 4].hex().upper(), p["before"])


class RegistrationTests(unittest.TestCase):
    def test_registered_off_everywhere_bundled_and_documented(self):
        public = {p.id: p for p in patcher.load_public_fun_patches()}
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        howto = (ROOT / "How to Use.txt").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        doc = (ROOT / "docs" / "transparency-log.md").read_text(encoding="utf-8")
        self.assertIn("TRIPLE TECH COST (ALL FIVE GAMES)", howto)
        for game in GAMES:
            with self.subTest(game=game):
                row = public[IDS[game]]
                self.assertEqual(row.name, "Triple Tech Cost")
                self.assertEqual(patcher.patch_requirement_text(row, list(public.values())),
                                 "Requires no other patch to be ticked.")
                self.assertIn(f'"data/vv{game}_triple_tech_cost_feature.json"', release)
                self.assertIn(f"- Patch ID: `{IDS[game]}`", readme)
                self.assertIn(f"#### Triple Tech Cost (`{IDS[game]}`)", doc)

    def test_only_its_own_row_ticks_it(self):
        """The owner: "7 should be default off for everything. players who want it must explicitly choose it."
        Default Patches (and a fresh install), Owner's Defaults and Select All all leave every game's row off."""
        for game in GAMES:
            with self.subTest(game=game):
                self.assertFalse(gui.default_fun_patch_selection(IDS[game]))
                self.assertFalse(gui.owners_default_fun_patch_selection(IDS[game]))
                self.assertFalse(gui.select_all_fun_patch_selection(IDS[game]))
                self.assertNotIn(IDS[game], gui.COTICKED_FUN_PATCH_IDS.values())
        # Nothing else in those sets moved: every other patch keeps its own answer.
        self.assertTrue(gui.select_all_fun_patch_selection("vv5_fix_vanilla_bugs"))
        self.assertTrue(gui.owners_default_fun_patch_selection("vv3_population_256"))

    def test_no_patch_needs_it(self):
        for p in patcher.load_public_fun_patches():
            deps = set(p.raw.get("dependencies") or ()) | {n["id"] for n in p.raw.get("needs_on") or ()}
            with self.subTest(patch=p.id):
                self.assertFalse(deps & set(IDS.values()))


class GameMechanicsTests(unittest.TestCase):
    class Village:
        def __init__(self, game: int, has: bool | None):
            self.game, self._has = game, has

        def has(self, feature: str):
            return self._has if feature.endswith("_triple_tech_cost") else False

    def facts(self, game: int):
        import importlib
        module = importlib.import_module(f"vv_game_mechanics_items_vv{game}")
        try:
            return list(module.item_facts(None))
        except TypeError:
            return list(module.item_facts())

    def test_every_technology_level_shows_stock_then_tripled_only_with_the_patch(self):
        import vv_game_mechanics_tech_time as tt
        for game in GAMES:
            facts = self.facts(game)
            with self.subTest(game=game):
                for has in (False, None):
                    self.assertEqual(tt.triple_item_facts(self.Village(game, has), facts), facts)
                out = tt.triple_item_facts(self.Village(game, True), facts)
                changed = [b.text for a, b in zip(facts, out) if a.text != b.text]
                self.assertEqual(len(changed), len(stock_table(game)))
                for (name, level), price in stock_table(game).items():
                    self.assertTrue(any(t.startswith(f"{name} level {level}") and
                                        f"{price:,} tech points normally, {3 * price:,} with \"Triple Tech Cost\""
                                        in t for t in changed), (name, level))

    def test_the_catch_up_times_use_the_tripled_prices(self):
        import vv_game_mechanics_tech_time as tt
        for game in GAMES:
            levels = {name: (0 if game == 3 and name in ("Nature", "Magic") else 1)
                      for name, _ in tt.every_level(game)}
            rate = lambda owned: 10.0  # noqa: E731
            stock = tt.goals(game, levels, 0, rate, True)
            tripled = tt.goals(game, levels, 0, rate, True, tripled=True)
            with self.subTest(game=game):
                self.assertEqual([(g.name, g.level) for g in stock], [(g.name, g.level) for g in tripled])
                for a, b in zip(stock, tripled):
                    self.assertEqual(b.cost, 3 * a.cost)
                    self.assertEqual(b.needed, 3 * a.needed)
                    self.assertAlmostEqual(b.units, 3 * a.units)
                    self.assertEqual(tt.sum_cost(b, levels, game, True), 3 * tt.sum_cost(a, levels, game))


if __name__ == "__main__":
    unittest.main()
