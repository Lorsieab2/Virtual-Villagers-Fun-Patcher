"""Fix Vanilla Bugs (all five games): a second pickup of an item already taken removes no other item.

The owner (2026-11-27, New Believers, seen live): one Hand of Bloom cast grew several mushrooms; eight children dropped
on one red mushroom each brought a red one back and were paid for it, but the island's other red mushrooms vanished,
while the brown ones stayed.  "put this in Vanilla Bugs ... just in case, cover collectibles too. this patch goes into
all 5 games".

What the games do, read from the executables:

* The Secret City, The Tree of Life, New Believers: a child dropped on an item (the drop hit-test, collectible manager
  vf2, accepts the first item within 30 pixels: distance squared below 0x384) gets the pick action, which plays the
  pick animation where the child stands and then puts the item in its hands (the carry setter: VV5 0x466420 -> the
  item listeners 0x413750 -> the manager's vf0).  vf0 (VV3 0x42D5E0, VV4 0x4139A0, VV5 0x413DC0) does not know which
  item the child was dropped on: it removes the item of the carried kind (the same id) NEAREST the child, out to
  1,000 pixels (distance squared below 1,000,000, the `mov ebx/edi, 0xF4240`).  The first child removes its own item;
  every later child (the Duplication Cheat lets them in) removes the next nearest item of the same kind, up to 1,000
  pixels away.  It returns 1 either way, so every child still carries and is paid.
  The fix: vf0 looks only as far as the drop reached (distance squared below 0x384, the hit-test's own limit).  A
  child stands, unmoved, within that reach of the item it was dropped on, so a single pickup removes exactly what it
  removed before; a later child whose item is gone removes nothing.
* A New Home: one mushroom at a time ([manager+0xACAC] its end time, 0 none).  The pick (job-step callback 42,
  0x43A24B) sets the end time to 1, which the next update (0x4236F4) takes as "gone" and clears.  It does so for
  every child, so a child picking after the first, once a new mushroom has grown elsewhere, made the new one vanish.
* The Lost Children: one item at a time (the item object [villagers+0xE574F4]).  The pick callbacks (0x3E mushroom
  0x461D52, 0x3F collectible 0x461DF4) remove it (0x415280) whatever it is by then, so a later child removed a new
  mushroom or collectible that had appeared anywhere.
  The fix for both: the callback's jump-table entry (VV1 0x43B510, VV2 0x4643E8 / 0x4643EC) goes to a short test, in
  int3 padding no code or row uses, that reads the map's area under the child exactly as the drop did (the map at
  [villagers+0x3E014] / [villagers+0xE574D8], the point (x + 0x14, y + 0x41)): the item's own area (VV1 0x21; VV2
  0x2F mushroom, 0x30 collectible) -> the stock case, unchanged; anything else -> the stock code just after the
  removal (VV1 0x43A25B: the map update and the epilogue; VV2 0x461D5F / 0x461E01: the cancel loop, or with the
  Duplication Cheat its jump past it).  The item a child stands on is the one it was dropped on.

Pinned here: the bytes; every piece decodes and lies in int3 padding no stock branch reaches and no other row writes;
the real vf0 / the real callbacks RUN in an emulator on the stock and the rendered bytes, with and without the
Duplication Cheat: N children on one item give N pickups, the first removes it, a same-kind item elsewhere stays
(stock: it goes); a single pickup is unchanged.
"""
from __future__ import annotations

import functools
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import pefile
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
    from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX,
                                   UC_X86_REG_EDI, UC_X86_REG_EDX, UC_X86_REG_EIP, UC_X86_REG_ESI,
                                   UC_X86_REG_ESP)
except ImportError:  # pragma: no cover
    pefile = None

STOCK_DIR = ROOT / "research" / "stock-executables"
EXES = {"vv1": "Virtual Villagers - A New Home.exe", "vv2": "Virtual Villagers - The Lost Children.exe",
        "vv3": "Virtual Villagers - The Secret City.exe", "vv4": "Virtual Villagers - The Tree of Life.exe",
        "vv5": "Virtual Villagers - New Believers.exe"}
BASE = 0x400000
MODES = ("stock", "collection_progression", "immediate_fixed")
CHEAT = "{}_everyone_collects_like_vv1"
NO_STOCK = "stock executables are not available"


def _h(text: str) -> bytes:
    return bytes.fromhex(text)


# (file offset, stock bytes, fixed bytes), in the order they sit in each <game>_fix_vanilla_bugs row.
FIXES = {
    "vv1": (
        (0x54642, b"\xCC" * 14, _h("8B44241469C0D803000001F0EB32")),   # slot record
        (0x54682, b"\xCC" * 12, _h("8B480883C141518B5004EB34")),       # the point, as the drop
        (0x546C2, b"\xCC" * 12, _h("83C214528B8E14E00300EB74")),       # ... and the area map
        (0x54742, b"\xCC" * 12, _h("E8B9FAFBFF83F8217536EB54")),       # area 0x21?
        (0x54782, b"\xCC" * 5, _h("E9D45AFEFF")),                      # no: 0x43A25B
        (0x547A2, b"\xCC" * 5, _h("E9A45AFEFF")),                      # yes: 0x43A24B (stock)
        (0x3B510, _h("4BA24300"), _h("42464500")),                     # callback 42's table entry
    ),
    "vv2": (
        (0x716C2, b"\xCC" * 14, _h("8B44242069C08CE4000001F0EB32")),   # the test: slot record
        (0x71702, b"\xCC" * 12, _h("8B480883C141518B5004EB34")),       # the point, as the drop
        (0x71742, b"\xCC" * 12, _h("83C214528B8ED874E500EB74")),       # ... and the area map
        (0x717C2, b"\xCC" * 12, _h("E8096AFAFF3B442404C20400")),       # area == the one asked for
        (0x71802, b"\xCC" * 14, _h("6A2FE8B9FEFFFF7517E94205FFFF")),   # mushroom: 0x2F -> 0x461D52
        (0x71822, b"\xCC" * 5, _h("E93805FFFF")),                      # else 0x461D5F
        (0x71862, b"\xCC" * 14, _h("6A30E859FEFFFF7567E98405FFFF")),   # collectible: 0x30 -> 0x461DF4
        (0x718D2, b"\xCC" * 5, _h("E92A05FFFF")),                      # else 0x461E01
        (0x643E8, _h("521D4600"), _h("02184700")),                     # case 0x3E's table entry
        (0x643EC, _h("F41D4600"), _h("62184700")),                     # case 0x3F's table entry
    ),
    "vv3": ((0x2D5EE, _h("BF40420F00"), _h("BF84030000")),),           # vf0 0x42D5E0: mov edi, 900
    "vv4": ((0x139AE, _h("BB40420F00"), _h("BB84030000")),),           # vf0 0x4139A0: mov ebx, 900
    "vv5": ((0x13DCE, _h("BB40420F00"), _h("BB84030000")),),           # vf0 0x413DC0: mov ebx, 900
}


def dupe_pickup_fixes(game: str) -> tuple:
    """The (file offset, stock bytes, fixed bytes) this fix adds to <game>_fix_vanilla_bugs."""
    return FIXES[game]


def _have(game: str) -> bool:
    return pefile is not None and (STOCK_DIR / EXES[game]).is_file()


@functools.lru_cache(maxsize=None)
def _stock(game: str) -> bytes:
    return (STOCK_DIR / EXES[game]).read_bytes()


@functools.lru_cache(maxsize=None)
def _render(game: str, mode: str, ids: tuple) -> bytes:
    import vv_fun_patcher as vfp
    build = next(b for b in vfp.load_builds() if b.id == game)
    data, _ = vfp.render_patched_bytes(STOCK_DIR / EXES[game], build, mode, list(ids))
    return bytes(data)


def _fixed(game: str, cheat: bool = False) -> bytes:
    ids = (f"{game}_fix_vanilla_bugs",) + ((CHEAT.format(game),) if cheat else ())
    return _render(game, "immediate_fixed", ids)


def _others(game: str) -> tuple:
    import vv_fun_patcher as vfp
    return tuple(p.id for p in vfp.load_public_fun_patches()
                 if p.game_id == game and p.id != f"{game}_fix_vanilla_bugs"
                 and p.id not in vfp.EXPERIMENTAL_FUN_PATCH_IDS and p.id not in vfp.ALTERNATIVE_FUN_PATCH_IDS)


@functools.lru_cache(maxsize=None)
def _image(exe: bytes) -> bytes:
    return pefile.PE(data=exe, fast_load=True).get_memory_mapped_image()


def _after_a_jump(raw: bytes, offset: int) -> bool:
    """The bytes right before `offset` decode to whole instructions ending in an unconditional jmp or a ret."""
    for back in range(5, 16):
        insns = list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(raw[offset - back:offset], BASE + offset - back))
        if sum(i.size for i in insns) == back and insns[-1].mnemonic in ("jmp", "ret"):
            return True
    return False


def _emulator(exe: bytes) -> Uc:
    image = _image(exe)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(BASE, (len(image) + 0xFFFF) & ~0xFFFF)
    mu.mem_write(BASE, image)
    return mu


HALT, STACK = 0x0F000000, 0x0E000000


# ---- The Secret City, The Tree of Life, New Believers: the manager's pickup vf0 ----------------------------------
# game: (vf0, the villager position routine it calls, slots, the hit-test entry and its accept block)
VF0 = {"vv3": (0x42D5E0, 0x455EF0, 2), "vv4": (0x4139A0, 0x45ED00, 2), "vv5": (0x413DC0, 0x466350, 0x3E)}
MGR, VILLAGER = 0x20000000, 0x21000000
RED, BROWN = 0x81, 0x80


def _pickup(exe: bytes, game: str, items: list, at: tuple) -> tuple[list, int]:
    """Run vf0(villager at `at`, carried id items[0]'s kind) over a manager holding `items`
    [(active, id, x, y), ...].  Returns (the items' active flags after, al)."""
    entry, position, slots = VF0[game]
    mu = _emulator(exe)
    mu.mem_map(MGR, 0x10000)
    mu.mem_map(VILLAGER, 0x10000)
    mu.mem_map(STACK - 0x10000, 0x20000)
    mu.mem_map(HALT, 0x1000)
    manager = bytearray(4 + 0x1C * slots)
    for i, (active, item, x, y) in enumerate(items):
        struct.pack_into("<B3xiiiiii", manager, 4 + 0x1C * i, active, item, 0, x, y, -1, 0)
    mu.mem_write(MGR, bytes(manager))
    carried = next(item for active, item, _, _ in items if item >= 0)

    def hook(uc, address, size, _):
        if address == position:                      # thiscall(villager), arg: the point out; ret 4
            esp = uc.reg_read(UC_X86_REG_ESP)
            ret, out = struct.unpack("<II", uc.mem_read(esp, 8))
            assert uc.reg_read(UC_X86_REG_ECX) == VILLAGER
            uc.mem_write(out, struct.pack("<ii", *at))
            uc.reg_write(UC_X86_REG_EAX, out)
            uc.reg_write(UC_X86_REG_ESP, esp + 8)
            uc.reg_write(UC_X86_REG_EIP, ret)
        elif address == HALT:
            uc.emu_stop()

    mu.hook_add(UC_HOOK_CODE, hook)
    esp = STACK - 0x100
    mu.mem_write(esp, struct.pack("<III", HALT, VILLAGER, carried))
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.reg_write(UC_X86_REG_ECX, MGR)
    saved = ((UC_X86_REG_EBX, 0xB0B0B0B0), (UC_X86_REG_ESI, 0x51515151), (UC_X86_REG_EDI, 0xD1D1D1D1),
             (UC_X86_REG_EBP, 0xB9B9B9B9))
    for reg, value in saved:
        mu.reg_write(reg, value)
    mu.emu_start(entry, 0, count=20000)
    assert mu.reg_read(UC_X86_REG_EIP) == HALT
    assert mu.reg_read(UC_X86_REG_ESP) == esp + 12, "ret 8"
    assert [mu.reg_read(r) for r, _ in saved] == [v for _, v in saved]
    after = mu.mem_read(MGR, len(manager))
    return [after[4 + 0x1C * i] for i in range(len(items))], mu.reg_read(UC_X86_REG_EAX) & 0xFF


def _n_children(exe: bytes, game: str, n: int, mine=(RED, 1000, 800), other=(RED, 1200, 900)) -> tuple[list, list]:
    """N children dropped on one item (mine), standing 3/4 pixels off it, pick one after another; another item
    (other) lies elsewhere.  Returns (each pickup's al, the two items' active flags at the end)."""
    items = [[1, mine[0], mine[1], mine[2]], [1, other[0], other[1], other[2]]]
    results = []
    for _child in range(n):
        flags, al = _pickup(exe, game, [tuple(i) for i in items], (mine[1] + 3, mine[2] + 4))
        results.append(al)
        for item, flag in zip(items, flags):
            item[0] = flag
    return results, [item[0] for item in items]


# ---- A New Home: job-step callback 42 (the mushroom pick) ------------------------------------------------------
V1_DISPATCH, V1_TAIL, V1_UPDATE, V1_LOOKUP = 0x43A230, 0x43A266, 0x416380, 0x414200
VILLAGERS, MAP, MANAGER, DRAW = 0x20000000, 0x22000000, 0x23000000, 0x24000000
SLOT = 3


def _map_area(mu, stride: int, rect: tuple, area: int) -> None:
    x0, y0, x1, y1 = rect                            # the map's cells are 10 pixels (the lookup's x / 10, y / 10)
    for cx in range(x0 // 10, (x1 + 9) // 10):
        for cy in range(y0 // 10, (y1 + 9) // 10):
            mu.mem_write(MAP + 4 * (cx * stride + cy), struct.pack("<i", area))


def _villagers(mu, stride: int, size: int, at: tuple) -> None:
    mu.mem_map(VILLAGERS, size)
    mu.mem_write(VILLAGERS + SLOT * stride + 4, struct.pack("<ii", at[0] - 0x14, at[1] - 0x41))


def _run_case(mu, entry: int, args: tuple, stops: set, saved) -> tuple[int, int]:
    """Run from the dispatcher entry; returns (where it stopped, esp there)."""
    state = {}

    def hook(uc, address, size, _):
        if address in stops:
            state["at"] = address
            uc.emu_stop()

    handle = mu.hook_add(UC_HOOK_CODE, hook)
    mu.mem_map(STACK - 0x10000, 0x20000)
    mu.mem_map(HALT, 0x1000)
    esp = STACK - 0x100
    mu.mem_write(esp, struct.pack("<I", HALT) + b"".join(struct.pack("<I", a) for a in args))
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.reg_write(UC_X86_REG_ECX, VILLAGERS)
    for reg, value in saved:
        mu.reg_write(reg, value)
    mu.emu_start(entry, 0, count=20000)
    mu.hook_del(handle)
    return state.get("at"), mu.reg_read(UC_X86_REG_ESP) - esp


def _vv1_pick(exe: bytes, *, mushroom_rect, mushroom_end: int, at: tuple) -> dict:
    """Callback 42 for the child in SLOT standing at `at` (the drop's point); the map shows area 0x21 over
    mushroom_rect (None: no mushroom on the map).  Returns the mushroom's end time after, and what ran."""
    mu = _emulator(exe)
    _villagers(mu, 0x3D8, 0x50000, at)
    mu.mem_write(VILLAGERS + 0x3E010, struct.pack("<III", MANAGER, MAP, 0))
    mu.mem_write(VILLAGERS + 0x3E024, struct.pack("<I", DRAW))
    for region in (MAP, MANAGER, DRAW):
        mu.mem_map(region, 0x40000)
    if mushroom_rect:
        _map_area(mu, 0xA8, mushroom_rect, 0x21)
    mu.mem_write(MANAGER + 0xACAC, struct.pack("<i", mushroom_end))
    calls = []

    def update(uc, address, size, _):
        if address == V1_UPDATE:                     # thiscall, no argument
            calls.append(uc.reg_read(UC_X86_REG_ECX))
            esp = uc.reg_read(UC_X86_REG_ESP)
            uc.reg_write(UC_X86_REG_EIP, struct.unpack("<I", uc.mem_read(esp, 4))[0])
            uc.reg_write(UC_X86_REG_ESP, esp + 4)

    mu.hook_add(UC_HOOK_CODE, update)
    saved = ((UC_X86_REG_EBX, 0xB0B0B0B0), (UC_X86_REG_ESI, 0x51515151), (UC_X86_REG_EDI, 0xD1D1D1D1),
             (UC_X86_REG_EBP, 0xB9B9B9B9))
    at_tail, depth = _run_case(mu, V1_DISPATCH, (SLOT, 42), {V1_TAIL}, saved)
    assert at_tail == V1_TAIL, "the case ends at its own epilogue"
    assert depth == -0x10, "the dispatcher's own four saves"
    assert mu.reg_read(UC_X86_REG_ESI) == VILLAGERS
    mu.emu_start(V1_TAIL, HALT, count=100)          # the stock epilogue: pop x4, ret 8
    assert mu.reg_read(UC_X86_REG_ESP) == STACK - 0x100 + 12
    assert [mu.reg_read(r) for r, _ in saved] == [v for _, v in saved]
    end = struct.unpack("<i", mu.mem_read(MANAGER + 0xACAC, 4))[0]
    return {"end": end, "updates": calls}


# ---- The Lost Children: pick callbacks 0x3E (mushroom) and 0x3F (collectible) ---------------------------------
V2_DISPATCH, V2_REMOVE_MAP = 0x461B10, 0x418660
V2_AFTER = {0x3E: 0x461D5F, 0x3F: 0x461E01}
ITEM, ITEM_MAP = 0x25000000, 0x26000000


def _vv2_pick(exe: bytes, callback: int, *, item_active: bool, area_rect, area: int, at: tuple) -> dict:
    mu = _emulator(exe)
    _villagers(mu, 0xE48C, 0xE58000, at)
    mu.mem_write(VILLAGERS + 0xE574D8, struct.pack("<I", MAP))
    mu.mem_write(VILLAGERS + 0xE574F4, struct.pack("<I", ITEM))
    for region in (MAP, ITEM, ITEM_MAP):
        mu.mem_map(region, 0x40000)
    if area_rect:
        _map_area(mu, 0xAA, area_rect, area)
    mu.mem_write(ITEM, bytes([1 if item_active else 0]))
    mu.mem_write(ITEM + 0x24, struct.pack("<iiii", 777, 0x31, 0, ITEM_MAP))
    rebuilt = []

    def rebuild(uc, address, size, _):
        if address == V2_REMOVE_MAP:
            rebuilt.append(uc.reg_read(UC_X86_REG_ECX))
            esp = uc.reg_read(UC_X86_REG_ESP)
            uc.reg_write(UC_X86_REG_EIP, struct.unpack("<I", uc.mem_read(esp, 4))[0])
            uc.reg_write(UC_X86_REG_ESP, esp + 4)

    mu.hook_add(UC_HOOK_CODE, rebuild)
    saved = ((UC_X86_REG_ESI, 0x51515151), (UC_X86_REG_EDI, 0xD1D1D1D1), (UC_X86_REG_EBP, 0xB9B9B9B9))
    stop, depth = _run_case(mu, V2_DISPATCH, (SLOT, callback), {V2_AFTER[callback]}, saved)
    assert stop == V2_AFTER[callback], "the case goes on where the stock removal ends"
    assert depth == -0x14, "the dispatcher's own five saves"
    assert mu.reg_read(UC_X86_REG_ESI) == VILLAGERS
    assert struct.unpack("<I", mu.mem_read(mu.reg_read(UC_X86_REG_ESP) + 0x18, 4))[0] == SLOT
    return {"active": mu.mem_read(ITEM, 1)[0], "expiry": struct.unpack("<i", mu.mem_read(ITEM + 0x24, 4))[0],
            "rebuilt": rebuilt}


class Manifest(unittest.TestCase):
    def test_each_row_carries_the_fix_at_its_end(self) -> None:
        from vv_fun_patcher import load_fun_patches
        for game, fixes in FIXES.items():
            with self.subTest(game=game):
                row = next(p for p in load_fun_patches() if p.id == f"{game}_fix_vanilla_bugs").raw
                pinned = [(int(p["offset"], 16), bytes.fromhex(p["before"]), bytes.fromhex(p["after"]))
                          for p in row["patches"]]
                self.assertEqual(pinned[-len(fixes):], list(fixes))
                self.assertIn("picks up", row["description"])
                self.assertIn("vanish", row["description"])


class Stock(unittest.TestCase):
    def test_the_stock_bytes(self) -> None:
        for game, fixes in FIXES.items():
            if not _have(game):
                self.skipTest(NO_STOCK)
            stock = _stock(game)
            for offset, before, after in fixes:
                with self.subTest(game=game, offset=hex(offset)):
                    self.assertEqual(stock[offset:offset + len(before)], before)
                    self.assertEqual(len(before), len(after))
                    pe = pefile.PE(data=stock, fast_load=True)
                    self.assertEqual(pe.get_offset_from_rva(offset), offset, "file offset == RVA")

    def test_vf0_takes_the_nearest_of_the_kind_out_to_1000_pixels_and_the_drop_reaches_30(self) -> None:
        hit = {"vv3": (0x42DDB0, 0x384), "vv4": (0x413A20, 0x384), "vv5": (0x413E40, 0x384)}
        for game, (entry, position, _slots) in VF0.items():
            if not _have(game):
                self.skipTest(NO_STOCK)
            with self.subTest(game=game):
                code = list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(_image(_stock(game))[entry - BASE:entry - BASE + 0x80],
                                                               entry))
                self.assertIn(f"call {position:#x}", [f"{i.mnemonic} {i.op_str}" for i in code])
                self.assertIn("0xf4240", " ".join(i.op_str for i in code))
                start, limit = hit[game]
                test = list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(_image(_stock(game))[start - BASE:start - BASE + 0x60],
                                                               start))
                self.assertIn(f"{limit:#x}", " ".join(i.op_str for i in test))

    def test_the_callbacks_are_reached_only_through_their_table_entries(self) -> None:
        sites = {"vv1": ((0x43B510, 0x43A24B), (None, 0x43A25B)),
                 "vv2": ((0x4643E8, 0x461D52), (0x4643EC, 0x461DF4), (None, 0x461D5F), (None, 0x461E01))}
        for game, entries in sites.items():
            if not _have(game):
                self.skipTest(NO_STOCK)
            stock = _stock(game)
            for table, case in entries:
                with self.subTest(game=game, case=hex(case)):
                    needle = struct.pack("<I", case)
                    hits = [i for i in range(len(stock)) if stock.startswith(needle, i)]
                    self.assertEqual([BASE + h for h in hits], [table] if table else [])
                    pe = pefile.PE(data=stock, fast_load=True)
                    text = pe.sections[0]
                    code = stock[text.PointerToRawData:text.PointerToRawData + text.SizeOfRawData]
                    for insn in Cs(CS_ARCH_X86, CS_MODE_32).disasm(code, BASE + text.VirtualAddress):
                        if insn.mnemonic.startswith("j") or insn.mnemonic == "call":
                            self.assertNotEqual(insn.op_str, f"{case:#x}", hex(insn.address))
                    # an instruction starts there (walked from the case's own first instruction)
                    begin = 0x43A24B if game == "vv1" else (0x461D52 if case < 0x461DF4 else 0x461DF4)
                    walk = [i.address for i in
                            Cs(CS_ARCH_X86, CS_MODE_32).disasm(_image(stock)[begin - BASE:begin - BASE + 0x20], begin)]
                    self.assertIn(case, walk)

    def test_the_pieces_are_padding_no_code_or_row_reaches(self) -> None:
        from vv_fun_patcher import load_fun_patches
        for game in ("vv1", "vv2"):
            if not _have(game):
                self.skipTest(NO_STOCK)
            stock = _stock(game)
            pe = pefile.PE(data=stock, fast_load=True)
            text = pe.sections[0]
            code = stock[text.PointerToRawData:text.PointerToRawData + text.SizeOfRawData]
            targets = set()
            for insn in Cs(CS_ARCH_X86, CS_MODE_32).disasm(code, BASE + text.VirtualAddress):
                if insn.mnemonic.startswith("j") or insn.mnemonic == "call":
                    try:
                        targets.add(int(insn.op_str, 16))
                    except ValueError:
                        pass
            pieces = [(o, len(b)) for o, b, _ in FIXES[game] if set(b) == {0xCC}]
            self.assertEqual(len(pieces), len(FIXES[game]) - (1 if game == "vv1" else 2))
            for offset, size in pieces:
                with self.subTest(game=game, piece=hex(offset)):
                    self.assertLess(offset + size, text.VirtualAddress + text.Misc_VirtualSize)
                    self.assertTrue(stock[offset - 1] == 0xCC or _after_a_jump(stock, offset),
                                    "after int3 or after a jmp/ret, never reached by falling through")
                    self.assertFalse(any(BASE + offset <= t < BASE + offset + size for t in targets))
            for p in load_fun_patches():
                if p.game_id != game or p.id == f"{game}_fix_vanilla_bugs":
                    continue
                for patch in p.raw.get("patches", []):
                    o = int(patch["offset"], 16)
                    n = len(bytes.fromhex(patch.get("before") or patch.get("after") or ""))
                    for lo, size, _ in ((x, len(b), 0) for x, b, _ in FIXES[game]):
                        self.assertFalse(o < lo + size and lo < o + n, (p.id, hex(o)))

    def test_every_piece_decodes_whole(self) -> None:
        for game in ("vv1", "vv2"):
            for offset, _before, after in FIXES[game]:
                if len(after) == 4:
                    continue
                with self.subTest(game=game, piece=hex(offset)):
                    insns = list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(after, BASE + offset))
                    self.assertEqual(sum(i.size for i in insns), len(after))
                    self.assertIn(insns[-1].mnemonic, ("jmp", "ret"))


class Render(unittest.TestCase):
    def test_alone_with_the_cheat_and_with_every_other_patch_in_every_mode(self) -> None:
        for game, fixes in FIXES.items():
            if not _have(game):
                self.skipTest(NO_STOCK)
            others = _others(game)
            for mode in MODES:
                for ids in ((f"{game}_fix_vanilla_bugs",), (f"{game}_fix_vanilla_bugs", CHEAT.format(game)),
                            others + (f"{game}_fix_vanilla_bugs",)):
                    data = _render(game, mode, ids)
                    for offset, _before, after in fixes:
                        with self.subTest(game=game, mode=mode, n=len(ids), offset=hex(offset)):
                            self.assertEqual(data[offset:offset + len(after)], after)
                without = _render(game, mode, others)
                for offset, before, _after in fixes:
                    with self.subTest(game=game, mode=mode, without=True, offset=hex(offset)):
                        self.assertEqual(without[offset:offset + len(before)], before)


@unittest.skipUnless(all(_have(g) for g in ("vv3", "vv4", "vv5")), NO_STOCK)
class LaterGames(unittest.TestCase):
    def test_stock_a_later_child_takes_another_item_of_the_kind(self) -> None:
        for game in VF0:
            with self.subTest(game=game):
                results, left = _n_children(_stock(game), game, 3)
                self.assertEqual(results, [1, 1, 1])
                self.assertEqual(left, [0, 0], "stock: the second child takes the red mushroom elsewhere")

    def test_fixed_n_children_on_one_item_leave_the_other_item(self) -> None:
        for game in VF0:
            for cheat in (False, True):
                exe = _fixed(game, cheat)
                for n in (1, 2, 8):
                    with self.subTest(game=game, cheat=cheat, n=n):
                        results, left = _n_children(exe, game, n)
                        self.assertEqual(results, [1] * n, "every child still carries its copy")
                        self.assertEqual(left, [0, 1], "its own item went; the other one stays")

    def test_fixed_a_different_kind_is_never_touched(self) -> None:
        for game in VF0:
            with self.subTest(game=game):
                results, left = _n_children(_fixed(game, True), game, 4, other=(BROWN, 1001, 801))
                self.assertEqual((results, left), ([1] * 4, [0, 1]))

    def test_a_single_pickup_is_unchanged(self) -> None:
        # The child is within the drop's reach of its item: stock and fixed take the same one, the nearest.
        cases = (
            ([(1, RED, 1000, 800), (1, RED, 1200, 900)], (1003, 804)),
            ([(1, RED, 1200, 900), (1, RED, 1000, 800)], (1003, 804)),
            ([(1, RED, 1000, 800), (1, RED, 1010, 805)], (1003, 804)),     # two in reach: the nearer
            ([(1, RED, 1000, 800), (1, RED, 1010, 805)], (1012, 806)),
            ([(1, RED, 1000, 800), (0, RED, 1001, 800)], (1000, 829)),     # 29 pixels: still in reach
            ([(1, BROWN, 1000, 800), (1, RED, 1000, 800)], (1000, 800)),
        )
        for game in VF0:
            for items, at in cases:
                with self.subTest(game=game, items=items, at=at):
                    stock = _pickup(_stock(game), game, items, at)
                    for cheat in (False, True):
                        self.assertEqual(_pickup(_fixed(game, cheat), game, items, at), stock)

    def test_the_hit_test_still_gates_the_drop(self) -> None:
        from test_everyone_collects import _hit_test
        for game in VF0:
            with self.subTest(game=game):
                self.assertEqual(_hit_test(game, _fixed(game), reserver=5), "refused", "a claimed item, no cheat")
                self.assertEqual(_hit_test(game, _fixed(game, True), reserver=5), "accepted", "with the cheat")
                self.assertEqual(_hit_test(game, _fixed(game), reserver=-1), "accepted")


@unittest.skipUnless(_have("vv1"), NO_STOCK)
class ANewHome(unittest.TestCase):
    RECT = (700, 200, 750, 260)          # the mushroom's area: (x, y) .. (x + 50, y + 60), as 0x4234E4 writes it
    ON = (720, 230)                      # the child's point (x + 0x14, y + 0x41) on it

    def test_a_single_pick_is_unchanged(self) -> None:
        for exe in (_stock("vv1"), _fixed("vv1")):
            got = _vv1_pick(exe, mushroom_rect=self.RECT, mushroom_end=5000, at=self.ON)
            self.assertEqual(got, {"end": 1, "updates": [DRAW]})

    def test_a_later_pick_once_it_is_cleared_leaves_a_new_mushroom(self) -> None:
        # The first child took it (end 1), the update cleared it, and a new one grew elsewhere (end 7000).
        elsewhere = (300, 500, 350, 560)
        stock = _vv1_pick(_stock("vv1"), mushroom_rect=elsewhere, mushroom_end=7000, at=self.ON)
        self.assertEqual(stock["end"], 1, "stock: the new mushroom is taken by the later child")
        for mode in MODES:
            fixed = _vv1_pick(_render("vv1", mode, ("vv1_fix_vanilla_bugs",)), mushroom_rect=elsewhere,
                              mushroom_end=7000, at=self.ON)
            self.assertEqual(fixed, {"end": 7000, "updates": [DRAW]}, mode)

    def test_a_later_pick_before_the_update_changes_nothing(self) -> None:
        for exe in (_stock("vv1"), _fixed("vv1")):
            self.assertEqual(_vv1_pick(exe, mushroom_rect=self.RECT, mushroom_end=1, at=self.ON)["end"], 1)

    def test_eight_children(self) -> None:
        fixed, stock = _fixed("vv1"), _stock("vv1")
        for exe, last in ((fixed, 7000), (stock, 1)):
            end, rect = 5000, self.RECT
            for child in range(8):
                end = _vv1_pick(exe, mushroom_rect=rect, mushroom_end=end, at=self.ON)["end"]
                if child == 0:
                    self.assertEqual(end, 1)
                    end, rect = 7000, (300, 500, 350, 560)      # cleared; a new one grows elsewhere
            self.assertEqual(end, last)


@unittest.skipUnless(_have("vv2"), NO_STOCK)
class TheLostChildren(unittest.TestCase):
    RECT = (700, 200, 750, 260)
    ON = (720, 230)

    def test_a_single_pick_is_unchanged(self) -> None:
        for callback, area in ((0x3E, 0x2F), (0x3F, 0x30)):
            for exe in (_stock("vv2"), _fixed("vv2"), _fixed("vv2", True)):
                with self.subTest(callback=hex(callback)):
                    got = _vv2_pick(exe, callback, item_active=True, area_rect=self.RECT, area=area, at=self.ON)
                    self.assertEqual(got, {"active": 0, "expiry": 0, "rebuilt": [ITEM_MAP]})

    def test_a_later_pick_leaves_a_new_item_elsewhere(self) -> None:
        elsewhere = (300, 500, 350, 560)
        for callback, area in ((0x3E, 0x2F), (0x3F, 0x30)):
            with self.subTest(callback=hex(callback)):
                stock = _vv2_pick(_stock("vv2"), callback, item_active=True, area_rect=elsewhere, area=area, at=self.ON)
                self.assertEqual(stock["active"], 0, "stock: the new item is taken by the later child")
                for cheat in (False, True):
                    for mode in MODES:
                        ids = ("vv2_fix_vanilla_bugs",) + (("vv2_everyone_collects_like_vv1",) if cheat else ())
                        fixed = _vv2_pick(_render("vv2", mode, ids), callback, item_active=True, area_rect=elsewhere,
                                          area=area, at=self.ON)
                        self.assertEqual(fixed, {"active": 1, "expiry": 777, "rebuilt": []}, (cheat, mode))

    def test_the_other_kind_of_area_is_not_the_item(self) -> None:
        # A mushroom pick standing on a collectible's area (or the reverse) removes nothing.
        for callback, area in ((0x3E, 0x30), (0x3F, 0x2F)):
            got = _vv2_pick(_fixed("vv2"), callback, item_active=True, area_rect=self.RECT, area=area, at=self.ON)
            self.assertEqual(got["active"], 1)


if __name__ == "__main__":
    unittest.main()
