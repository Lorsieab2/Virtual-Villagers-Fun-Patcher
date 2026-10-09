"""New Believers: Reanimate refused for want of a record says why in the gray message bar.

v1.35.58's record guard (scripts/build_record_guards_vv345.py) refuses
Reanimate, nothing spent, while every villager record is taken (records in use
plus babies owed), because the stock spell crashed on a NULL record.  The owner
tried it at 256 of 256 and the power silently did nothing; he wants the gray
bar to say:

    There's no room in your village to revive this person.

The game's own god-power refusals (not enough energy, 0x595 ...) call
Bar::SetText(stringId, -1) @ 0x44EF60 on the bar 0x520F68, which copies the
sm.xml string into the bar with strncpy(bar, text, 0xFF) and sets
[bar + 0x100] to the game clock + 5.  sm.xml has no such string (and the
patcher never changes the game's assets), so the guard runs that same tail
with its own text.

Every check runs the RENDERED executable in an emulator: Owner's Defaults
with and without 256 Villagers, and nothing ticked, in all three population
modes.  On refusal the bar holds exactly the text, its clock is set as
SetText sets it, the bar is written once (one message per click), and the
spell handler leaves through its "nothing cast" exit (0x422F56 -> al = 0) --
never reaching the energy charge 0x424FD0, the cast sound 0x44C440 or the
spell-slot finder.  With room the guard hands over to the slot finder exactly
as the stock code did, and the bar is untouched.
"""
from __future__ import annotations

import functools
import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import vv_fun_patcher as vfp  # noqa: E402

STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
needs_stock = unittest.skipUnless(STOCK.is_file(), "the stock executables are not in this checkout")

TEXT = b"There's no room in your village to revive this person."
MODES = ("stock", "collection_progression", "immediate_fixed")

BAR, BAR_UNTIL = 0x520F68, 0x520F68 + 0x100
SET_TEXT, STRING_MGR, STRING_OF = 0x44EF60, 0x450D40, 0x4506D0
STRNCPY, CLOCK, SECONDS = 0x47D7C0, 0x425950, 0x4036E0
SITE, BACK = 0x42341A, 0x42341F        # Reanimate's call of the spell-slot finder
SLOT_FINDER = 0x4206F0
NOTHING_CAST, HANDLER_EXIT = 0x422F56, 0x423029
ENERGY, CAST_SOUND = 0x424FD0, 0x44C440

STRIDE, ACTIVE, PREGNANT = 0x2F44, 0x1CD4, 0x1C4C        # the pregnancy, then the litter owed
BASE = {150: 0x554190, 256: 0x800048}
STACK, STACK_TOP = 0x32000000, 0x32000000 + 0x10000 - 0x100
OBJ, CLOCK_OBJ, NOW = 0x31000000, 0x31001000, 4242
SENTINEL = 0x0BADF00D
STOCK_TEXT = 0x31002000                # a stand-in sm.xml string for the stock SetText


def owners_defaults() -> tuple[str, ...]:
    from vv_fun_patcher_gui import owners_default_fun_patch_selection
    ids = [p.id for p in vfp.load_public_fun_patches()
           if p.game_id == "vv5" and owners_default_fun_patch_selection(p.id)]
    return tuple(vfp.resolve_fun_patch_ids(ids, game_id="vv5"))


def builds():
    """(label, mode, patch ids, slots) of every New Believers build checked."""
    full = owners_defaults()
    assert "vv5_population_256" in full, "Owner's Defaults ticks 256 Villagers (Experimental)"
    without = tuple(vfp.resolve_fun_patch_ids([i for i in full if i != "vv5_population_256"], game_id="vv5"))
    for mode in MODES:
        yield f"Owner's Defaults, {mode}", mode, full, 256
        yield f"Owner's Defaults without 256, {mode}", mode, without, 150
        yield f"nothing ticked, {mode}", mode, (), 150


@functools.lru_cache(maxsize=None)
def render(mode: str, ids: tuple[str, ...]) -> pefile.PE:
    build = next(b for b in vfp.load_builds() if b.id == "vv5")
    data, _ = vfp.render_patched_bytes(STOCK, build, mode, list(ids))
    return pefile.PE(data=bytes(data))


class Game:
    """The rendered image with `occupied` records in use, the first mother owing
    `owed` babies; the game clock stubbed."""

    def __init__(self, pe: pefile.PE, slots: int, occupied: int, owed: int = 0):
        self.uc = uc = Uc(UC_ARCH_X86, UC_MODE_32)
        for section in pe.sections:
            va = 0x400000 + section.VirtualAddress
            size = (max(section.Misc_VirtualSize, section.SizeOfRawData) + 0xFFF) & ~0xFFF
            uc.mem_map(va, size)
            uc.mem_write(va, section.get_data()[:size])
        uc.mem_map(STACK, 0x10000)
        uc.mem_map(OBJ, 0x10000)
        uc.mem_map(SENTINEL & ~0xFFF, 0x1000)
        for i in range(occupied):
            uc.mem_write(BASE[slots] + i * STRIDE + ACTIVE, b"\x01")
        if owed:
            uc.mem_write(BASE[slots] + PREGNANT, struct.pack("<2I", 300, owed))
        # The game clock: 0x425950 returns the clock object, 0x4036E0 (on it) the seconds.
        uc.mem_write(CLOCK, bytes([0xB8]) + struct.pack("<I", CLOCK_OBJ) + b"\xC3")
        uc.mem_write(SECONDS, bytes([0xB8]) + struct.pack("<I", NOW) + b"\xC3")
        uc.mem_write(BAR, b"\xAA" * 0x100 + struct.pack("<I", 7))
        self.calls: dict[int, list] = {}
        self.stops: dict[int, str] = {}
        self.where = None
        uc.hook_add(UC_HOOK_CODE, self._hook)

    def _hook(self, uc, address, size, user):
        if address in (STRNCPY, SECONDS):
            esp = uc.reg_read(UC_X86_REG_ESP)
            self.calls.setdefault(address, []).append(
                (struct.unpack("<3I", uc.mem_read(esp + 4, 12)), uc.reg_read(UC_X86_REG_ECX)))
        if address in self.stops:
            self.where = self.stops[address]
            uc.emu_stop()

    def run(self, start, stops, regs=None, stack=()):
        self.stops = dict(stops)
        self.stops[SENTINEL] = "returned"
        esp = STACK_TOP - 4 * len(stack)
        for k, v in enumerate(stack):
            self.uc.mem_write(esp + 4 * k, struct.pack("<I", v & 0xFFFFFFFF))
        self.uc.reg_write(UC_X86_REG_ESP, esp)
        self.esp0 = esp
        for r, v in (regs or {}).items():
            self.uc.reg_write(r, v & 0xFFFFFFFF)
        self.where = None
        self.uc.emu_start(start, 0xFFFFFFFF, count=400000)
        return self.where

    def bar(self) -> tuple[bytes, int]:
        raw = bytes(self.uc.mem_read(BAR, 0x104))
        return raw[:0x100], struct.unpack("<I", raw[0x100:])[0]

    def reanimate(self):
        """Click Reanimate: the handler from the guarded call to its exit, the
        stock -1 argument already pushed (0x423400)."""
        return self.run(SITE, {SLOT_FINDER: "slot finder", HANDLER_EXIT: "nothing cast",
                               ENERGY: "energy spent", CAST_SOUND: "cast sound"},
                        {UC_X86_REG_EBX: OBJ}, stack=(0xFFFFFFFF,))


def stock_bar_after_set_text(pe: pefile.PE) -> tuple[bytes, int]:
    """What the game's own Bar::SetText(id, -1) leaves in the bar for this text."""
    game = Game(pe, 150, 0)
    game.uc.mem_write(STOCK_TEXT, TEXT + b"\0")
    game.uc.mem_write(STRING_MGR, bytes([0xB8]) + struct.pack("<I", OBJ) + b"\xC3")
    game.uc.mem_write(STRING_OF, bytes([0xB8]) + struct.pack("<I", STOCK_TEXT) + b"\xC2\x04\x00")
    where = game.run(SET_TEXT, {}, {UC_X86_REG_ECX: BAR}, stack=(SENTINEL, 0x595, 0xFFFFFFFF))
    assert where == "returned", where
    return game.bar()


@needs_stock
class ReanimateNoRoomMessage(unittest.TestCase):
    def test_refused_reanimate_says_why_in_the_gray_bar_and_spends_nothing(self):
        for label, mode, ids, slots in builds():
            pe = render(mode, ids)
            # every record in use; or two free, both owed to a pregnant mother
            for occupied, owed in ((slots, 0), (slots - 2, 2)):
                with self.subTest(build=label, occupied=occupied, owed=owed):
                    self.check_refused(pe, Game(pe, slots, occupied, owed))

    def check_refused(self, pe: pefile.PE, game: Game) -> None:
        self.assertEqual(game.reanimate(), "nothing cast", "the handler's own nothing-cast exit")
        self.assertEqual(game.uc.reg_read(UC_X86_REG_EAX) & 0xFF, 0, "the click casts nothing")
        self.assertEqual(game.uc.reg_read(UC_X86_REG_ESP), game.esp0 + 4,
                         "the slot finder's argument popped as 0x4206F0 does")
        text, until = game.bar()
        self.assertEqual(text[:0xFF], TEXT + bytes(0xFF - len(TEXT)), "exactly the owner's text")
        self.assertEqual(until, NOW + 5, "the bar's five-second display, as SetText sets it")
        self.assertEqual(len(game.calls.get(STRNCPY, [])), 1, "one message per click")
        (dest, _, count), _ = game.calls[STRNCPY][0]
        self.assertEqual((dest, count), (BAR, 0xFF))
        self.assertEqual(game.calls[SECONDS][0][1], CLOCK_OBJ, "the seconds read from the game clock")
        self.assertEqual(game.bar(), stock_bar_after_set_text(pe),
                         "the bar exactly as the game's own SetText leaves it")

    def test_with_room_reanimate_goes_on_as_before_and_the_bar_is_untouched(self):
        for label, mode, ids, slots in builds():
            with self.subTest(build=label):
                game = Game(render(mode, ids), slots, slots - 2, owed=1)
                self.assertEqual(game.reanimate(), "slot finder")
                self.assertEqual(game.uc.reg_read(UC_X86_REG_ECX), OBJ, "mov ecx, ebx as the stock code")
                esp = game.uc.reg_read(UC_X86_REG_ESP)
                self.assertEqual(struct.unpack("<2I", game.uc.mem_read(esp, 8)), (BACK, 0xFFFFFFFF),
                                 "the stock return address and argument")
                self.assertEqual(game.bar(), (b"\xAA" * 0x100, 7))
                self.assertNotIn(STRNCPY, game.calls)

    def test_the_expanded_modes_keep_the_text_and_rescale_only_the_cap(self):
        """The (unpublished) Expanded-256 modes rewrite every safety row's 150 as
        256: the text survives it and the guard changes only its cap."""
        build = next(b for b in vfp.load_builds() if b.id == "vv5")
        text = TEXT.hex().upper() + "00"
        stock = {p["offset"]: p["after"] for p in build.safety_patches}
        guard = next(o for o, a in stock.items() if "68680F5200" in a)     # push 0x520F68, the bar
        for mode in sorted(vfp.EXPANDED_PATCH_MODES):
            with self.subTest(mode=mode):
                rows = {p["offset"]: p["after"] for p in vfp._safety_patches(build, mode)}
                self.assertIn(text, rows.values())
                self.assertEqual(rows[guard], stock[guard].replace("3D96000000", "3D00010000"))
                self.assertNotEqual(rows[guard], stock[guard])


if __name__ == "__main__":
    unittest.main()
