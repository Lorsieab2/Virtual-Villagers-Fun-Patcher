"""The Remembrance Ceremony and The Rumblings: the owner's single-popup island events for all five games (2026-11-13),
in "More Island Events".

Static (always run): the words are the owner's (src/vv_remembrance_ceremony.py, src/vv_the_rumblings.py, the
companion's table generated from them, a translation row for every piece), in letters every game's font draws.

EMULATED (unicorn, each stock executable, the built "VVFP More Island Events.dll"; tests/story_emulator.py and the
villagers in the game's own records as tests/test_aspiring_adventurer.py puts them):
  * the spawn rules: no grave / one grave; New Believers: The Last Heathen not done / done; one puzzle missing / all
    solved; no finished structure / one; a structure that is a puzzle never counts;
  * the draw: never a share of the game's own (stock island event chances never change) -- each comes only when it
    is due (Pick Island Event or the rare roll): A New Home's and The Lost Children's chooser is redirected for the
    one constructor call only then (and put back; with nothing due the chooser runs on the stock bytes, its stock
    bound), the due case past the stock cases shows the event (its text in the event's own buffer); the later three:
    the due object in slot 0 and no entry added to the selector's list, the event happening once, inside the
    presenter's constructor;
  * The Remembrance Ceremony: everyone living and present goes -- children, babies that are records, nursing mothers
    and fathers, the protected (the Golden Child, the Tribal Chief, Esteemed Elders that are not statues...), puzzle
    workers -- each through the game's own stop and starter, to the game's own actions (50/50 where there are two);
    New Believers: believers only, the mausoleum, and with the hovel patch's bytes the hovel 50% (Honoring or
    Reflecting 50% each, through the patch's own code so its marks re-aim the walks); the feast -10 food each, never
    below 0;
  * The Rumblings: each finished structure at rand(100) < 25, at least one; the loss 10 + rand(91); the states
    written (A New Home / The Lost Children: the flag and the progress, the game's refresh; The Secret City: on the
    work above the new village, its record; The Tree of Life / New Believers: set state 3, the progress, under
    construction, the effect handle freed); 100% is the new village's state; puzzles untouched, nobody harmed, the
    population and the room test as the game reads them;
  * one Island Events log entry each, with the exact title and the event's own lines.

The live game is NOT exercised here.
"""
from __future__ import annotations

import json
import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

import vv_remembrance_ceremony as rc  # noqa: E402
import vv_the_rumblings as rb  # noqa: E402
from test_aspiring_adventurer import DLL, HAVE_EMULATOR, HAVE_STOCK, TABLES, TOP, Village  # noqa: E402
from test_more_island_events_pages import fake_log, logged  # noqa: E402

try:
    from story_emulator import STACK_TOP  # noqa: E402
except ImportError:                       # pragma: no cover
    STACK_TOP = 0

NATIVE = ROOT / "native" / "vvfp_more_island_events"
REMEMBRANCE, RUMBLINGS = 0, 1


def pick_index(game: int, which: int) -> int:
    """The registry index (mie_pick.inc) of `which` in `game`: The Remembrance Ceremony 7 (New Believers' own line 8),
    The Rumblings 9."""
    return 9 if which == RUMBLINGS else (8 if game == 5 else 7)
ACT_HONOR, ACT_REFLECT, ACT_HOVEL_HONOR, ACT_HOVEL_REFLECT = 1, 2, 3, 4
NEEDS = unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(),
                            "needs unicorn, pefile and the stock executables")

V1_PUZZLES = (0x9FA8, 0x9FB0, 0x9FB8, 0x9FC0, 0x9FC8, 0x9FD8, 0x9FE0, 0x9FE8,
              0xA000, 0xA008, 0xA050, 0xA058, 0xA080, 0xA088, 0xA090, 0xA098)
V2_PUZZLES = (0x2E768, 0x2E770, 0x2E778, 0x2E780, 0x2E788, 0x2E790, 0x2E798, 0x2E7A0,
              0x2E7A8, 0x2E7B0, 0x2E7B8, 0x2E7C0, 0x2E7C8, 0x2E7D8, 0x2E7E0, 0x2E7E8)
V3_PUZZLE_DONE_AT = (1, 1, 5, 700, 1, 1, 1800, 1400, 2, 1, 1, 6, 1, 1, 1, 1)
V5_PUZZLES = (2, 3, 4, 6, 7, 8, 10, 11, 12, 14, 15)
# Each game's structures: (flag or object, progress, done at, start).
V1_HUTS = ((0x9FF0, 0x9FEC, 400, 0), (0x9FF8, 0x9FF4, 600, 0))
V2_HUTS = ((0x2E818, 0x2E814, 450, 205), (0x2E820, 0x2E81C, 700, 0), (0x2E828, 0x2E824, 900, 0))
V3_START = (1750, 400, 0, 0)
V3_STATE = (1, 2, 3, 3)
V3_LEFT = (250, 1600, 2000, 2000)
V4_OBJECTS = ((19, 0x4D8588), (20, 0x4D8250), (21, 0x4D8478), (22, 0x4D82D8), (23, 0x4D83F0), (24, 0x4D8500),
              (25, 0x4D8360))
V5_OBJECTS = ((19, 0x51DCD8), (20, 0x51DA28), (21, 0x51DBC8), (22, 0x51DAB0), (23, 0x51DB40))
LATE = {4: dict(objects=V4_OBJECTS, projects=0x4D8BF8, done_at=0x4D8B20, set_state=0x430430, slot=0x40,
                pool=0x4D69D0),
        5: dict(objects=V5_OBJECTS, projects=0x51E008, done_at=0x51DF30, set_state=0x434F60, slot=0x44,
                pool=0x51CF40)}
COUNT = {1: 0x41CF90, 2: 0x425860, 4: 0x467610, 5: 0x4713F0}


def s32(v: int) -> int:
    return v - (1 << 32) if v >> 31 else v


class Ceremony(Village):
    """One game with the companion, its villagers, graves, puzzles and structures, and its single-result popup."""

    def __init__(self, game: int):
        super().__init__(game)
        p = self.p
        self.sent: list[tuple] = []
        self.pop = 0
        if game == 1:
            self.base = p.alloc(0x3E100)                     # the villagers' object reaches +0x3E024
            p.put32(0x48B614, self.base)
            p.put32(self.base + 0x3E010, self.world)            # the villagers' own world pointer
            self.nav, self.scene = p.alloc(16), p.alloc(16)
            p.put32(self.base + 0x3E014, self.nav)
            p.put32(self.base + 0x3E024, self.scene)
            p.stub(0x439470, lambda pr: (self.sent.append(("stop", pr.arg(0))) or 0, 4))
            p.stub(0x4401E0, lambda pr: (self.sent.append(("honor", pr.arg(0))) or 0, 4))
            p.stub(0x414590, lambda pr: (self.sent.append(("nav",)) or 0, 0))
            p.stub(0x416380, lambda pr: (self.sent.append(("scene",)) or 0, 0))
        elif game == 2:
            self.base = p.alloc(0xE58000)                    # the pool reaches +0xE574E8
            p.put32(0x499F24, self.base)
            p.put32(self.world + 0x305A4, self.base)
            self.nav, self.scene = p.alloc(16), p.alloc(16)
            p.put32(self.base + 0xE574D8, self.nav)
            p.put32(self.base + 0xE574E8, self.scene)
            p.stub(0x4492A0, lambda pr: (self.sent.append(("stop", pr.arg(0))) or 0, 4))
            p.stub(0x454890, lambda pr: (self.sent.append(("honor", pr.arg(0))) or 0, 4))
            p.stub(0x4523A0, lambda pr: (self.sent.append(("reflect", pr.arg(0))) or 0, 4))
            p.stub(0x418660, lambda pr: (self.sent.append(("nav",)) or 0, 0))
            p.stub(0x41C1D0, lambda pr: (self.sent.append(("scene",)) or 0, 0))
        elif game == 3:
            p.stub(0x460F70, lambda pr: (self.sent.append(("stop", self.index_of(pr.reg("ecx")))) or 0, 4))
            p.stub(0x455570, lambda pr: (self.sent.append(("do", self.index_of(pr.reg("ecx")), pr.arg(0))) or 0, 8))
            p.stub(0x461BF0, lambda pr: (self.sent.append(("kick", self.index_of(pr.reg("ecx")))) or 0, 4))

            def picker(pr):
                pr.put32(pr.arg(3), self.pop)
                return 0, 16
            p.stub(0x45D460, picker)
            for k in range(50):                               # the Roster of the Dead: no grave
                p.put32(0x5973F0 + 0x2C * k, 0xFFFFFFFF)
        elif game == 4:
            p.stub(0x45DEC0, lambda pr: (self.sent.append(("do", self.index_of(pr.reg("ecx")), pr.arg(0))) or 0, 8))
            p.stub(0x46A030, lambda pr: (self.sent.append(("kick", self.index_of(pr.reg("ecx")))) or 0, 0))
        else:
            def start(pr):
                self.sent.append(("do", self.index_of(pr.reg("ecx")), pr.arg(0), pr.u32(pr.reg("esp"))))
                return 0, 8
            p.stub(0x465580, start)
            p.stub(0x457E90, lambda pr: (self.sent.append(("reflect", self.index_of(pr.arg(0)),
                                                           pr.u32(pr.reg("esp")))) or 0, 0))
        if game in COUNT:
            p.stub(COUNT[game], lambda pr: (self.pop, 0))

    def index_of(self, record: int) -> int:
        return (record - self.base - self.first) // self.stride

    # -- the village -------------------------------------------------------------------------------------------
    def graves(self, n: int) -> None:
        p = self.p
        if self.game == 1:
            for k in range(50):
                p.put32(self.world + 0xA340 + 0x2C * k, 1 if k < n else 0)
        elif self.game == 2:
            for k in range(50):
                p.put32(self.world + 0x2EB80 + 0x7C * k, 1 if k < n else 0)
        elif self.game == 3:
            for k in range(50):
                p.put32(0x5973F0 + 0x2C * k, k if k < n else 0xFFFFFFFF)
        else:
            base = 0x5025C8 if self.game == 4 else 0x5481A8
            for k in range(60):
                p.put32(base + 0x5C * k + 0x1C, 1 if k < n else 0)

    def last_heathen(self, done: bool) -> None:
        self.p.put32(0x51DF30 + 4 * 25, 1)
        self.p.put32(0x51E008 + 8 * 25, 1 if done else 0)

    def puzzles(self, missing: int | None = None) -> None:
        p = self.p
        if self.game in (1, 2):
            for k, off in enumerate(V1_PUZZLES if self.game == 1 else V2_PUZZLES):
                p.write(self.world + off, b"\x00" if k == missing else b"\x01")
        elif self.game == 3:
            for k, done_at in enumerate(V3_PUZZLE_DONE_AT):
                p.put32(0x594990 + 8 * k, done_at - 1 if k == missing else done_at)
        else:
            L = LATE[self.game]
            ids = range(16) if self.game == 4 else V5_PUZZLES
            for k, pid in enumerate(ids):
                p.put32(L["done_at"] + 4 * pid, 5)
                p.put32(L["projects"] + 8 * pid, 4 if k == missing else 5)

    def puzzle_bytes(self) -> bytes:
        p = self.p
        if self.game == 1:
            return b"".join(p.read(self.world + off - 4, 8) for off in V1_PUZZLES)
        if self.game == 2:
            return b"".join(p.read(self.world + off - 4, 8) for off in V2_PUZZLES)
        if self.game == 3:
            return p.read(0x594990, 16 * 8)
        L = LATE[self.game]
        return p.read(L["projects"], 19 * 8)

    def structures(self) -> int:
        return len(rb.STRUCTURES[self.game])

    def v3_id(self, k: int) -> int:
        return self.p.u32(0x49D0D0 + 4 * k)

    def finish(self, k: int, done: bool = True) -> None:
        """Structure k (rb.STRUCTURES' order) finished (or not started)."""
        p, g = self.p, self.game
        if g == 1:
            flag, progress, done_at, _ = V1_HUTS[k]
            p.write(self.world + flag, b"\x01" if done else b"\x00")
            p.put32(self.world + progress, done_at if done else 0)
        elif g == 2:
            flag, progress, done_at, start = V2_HUTS[k]
            p.write(self.world + flag, b"\x01" if done else b"\x00")
            p.put32(self.world + progress, (24 if k == 0 else done_at) if done else start)
        elif g == 3:
            pid = self.v3_id(k)
            p.put32(0x594990 + 8 * pid, 2000 if done else V3_START[k])
            hut = 0x594620 + 4 + 0x14 * k
            p.write(hut, b"\x00")
            p.put32(hut + 4, V3_STATE[k])
            p.put32(hut + 8, V3_LEFT[k] if done else 0)
            p.put32(hut + 0xC, 7 if done else 0xFFFFFFFF)
        else:
            L = LATE[g]
            pid, obj = L["objects"][k]
            if not hasattr(self, "vtable"):
                self.vtable = p.alloc(0x100)
                p.put32(self.vtable + L["slot"], L["set_state"])
            p.put32(obj, self.vtable)
            p.put32(obj + 8, pid)
            p.put32(L["done_at"] + 4 * pid, 2000)
            p.put32(L["projects"] + 8 * pid, 2000 if done else 0)
            p.write(obj + 0x30, b"\x00")
            p.put32(obj + 0x34, 0 if done else 3)
            p.put32(obj + 0x38, 2000)
            p.put32(obj + 0x3C, 9 if done else 0xFFFFFFFF)

    def progress(self, k: int) -> int:
        p, g = self.p, self.game
        if g == 1:
            return p.u32(self.world + V1_HUTS[k][1])
        if g == 2:
            return p.u32(self.world + V2_HUTS[k][1])
        if g == 3:
            return p.u32(0x594990 + 8 * self.v3_id(k))
        L = LATE[g]
        return p.u32(L["projects"] + 8 * L["objects"][k][0])

    def food(self) -> int:
        return s32(self.stores()[0])

    def set_food(self, value: int) -> None:
        if self.game == 1:
            self.p.put32(self.world + 0xA2EC, value)
        elif self.game == 2:
            self.p.put32(self.world + 0x2EAA4, value)
        else:
            self.p.put32(self.t["food"], value)

    def possible(self, which: int) -> int:                   # noqa: D401 (the companion's own answer)
        return self.p.export("VvfpCeremonyPossible", which)

    def cr_state(self) -> list[int]:
        out = self.p.alloc(15 * 4)
        self.p.export("VvfpCeremonyState", out)
        return [s32(self.p.u32(out + 4 * k)) for k in range(15)]

    def act(self, i: int) -> int:
        return self.p.export("VvfpCeremonyAct", i)

    # -- the draw and the popup ------------------------------------------------------------------------------------
    def happen(self, which: int, rolls: list[int]) -> str:
        """`which` drawn through the game's own island-event code and its popup built: the text the popup shows."""
        p, g = self.p, self.game
        if g in (1, 2):
            ctor, chooser, site, cases = ((0x4286B0, 0x428470, 0x423A06, 15) if g == 1
                                          else (0x4348E0, 0x434570, 0x42F0F7, 28))
            rel = (chooser - (ctor + 5)) & 0xFFFFFFFF
            p.mu.mem_write(ctor, b"\xE9" + struct.pack("<I", rel))      # the constructor stood in for: its chooser
            p.mu.ctl_flush_tb()
            event = p.alloc(0x6000)
            p.put32(event + 0x50A4, self.world if g == 1 else self.base)
            p.put32(event + 0x50A8, self.base)
            p.put32(event + 0x50AC, self.world)
            self.due = pick_index(g, which)                              # due: Pick Island Event or the rare roll
            self.rolls = list(rolls)
            esp = STACK_TOP - 0x3000
            p.put32(esp, 2)
            p.put32(esp + 4, 3)
            p.set_reg("esp", esp)
            p.set_reg("ecx", event)
            self.draw_site_during = None
            p.run(site, site + 5)
            self.draw_site = p.read(0x4284DB if g == 1 else 0x434607, 5)
            return p.cstring(event + 0x277F, 6000)
        t = self.t
        obj = p.export("VvfpCeremonyObject", which)
        entries, slot0 = self.list_draw(which)
        if slot0 != obj:
            raise AssertionError("not drawn")
        # The presenter's constructor stood in for: it keeps the object and asks its title (+0x08), as the game's.
        code = t["ctor"]
        p.mu.mem_write(code, bytes.fromhex("8B44240489415051" "8BC88B01FF500858" "C20400"))
        p.mu.ctl_flush_tb()
        self.dlg = p.alloc(0x1000)
        self.rolls = list(rolls)
        esp = STACK_TOP - 0x3000 - 4
        p.put32(esp, obj)
        p.set_reg("esp", esp)
        p.set_reg("ecx", self.dlg)
        p.run(*t["site"])
        entry = p.u32(t["strings"] + 4 * {3: 0x3A7, 4: 0x35F, 5: 0x3B3}[g])
        title = p.cstring(p.u32(entry + 8), 400)
        body = p.call(p.u32(p.u32(obj) + 0xC), [], ecx=obj)
        text = p.cstring(p.u32(p.u32(t["strings"] + 4 * body) + 8), 4000)
        return title + "\n" + text

    def list_draw(self, which: int) -> tuple[int, int]:
        """The selector's loop with every stock slot empty and `which` due: (entries added, the object in slot 0)."""
        self.due = pick_index(self.game, which)
        added = self.run_list(0)
        return added, self.obj

    def due_can_happen(self, which: int) -> bool:
        """`which` due, the selector's loop run: its object in slot 0, no entry added, and its own condition."""
        added, slot0 = self.list_draw(which)
        if added != 0 or slot0 != self.p.export("VvfpCeremonyObject", which):
            raise AssertionError((added, slot0))
        return self.can_fire(slot0)


def remembrance_village(game: int) -> Ceremony:
    v = Ceremony(game)
    v.villager(0, "Ana", True)
    v.villager(1, "Ben")
    v.graves(1)
    if game == 5:
        v.last_heathen(True)
    return v


def rumblings_village(game: int) -> Ceremony:
    v = Ceremony(game)
    v.villager(0, "Ana", True)
    v.villager(1, "Ben")
    v.puzzles()
    for k in range(v.structures()):
        v.finish(k, False)
    return v


def words(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# ---- Static -----------------------------------------------------------------------------------------------------

class TheWords(unittest.TestCase):
    def test_the_owners_text_unaltered(self) -> None:
        owner = {
            rc: ROOT / "tests" / "data" / "remembrance_owner_text.txt",
            rb: ROOT / "tests" / "data" / "rumblings_owner_text.txt",
        }
        for module, path in owner.items():
            source = path.read_text(encoding="utf-8")
            self.assertIn(module.english("TEXT"), words(source))
            self.assertIn(module.TITLE.upper(), source)

    def test_every_game_draws_every_letter(self) -> None:
        for module in (rc, rb):
            for _key, text in module.TEXTS:
                self.assertTrue(all(32 <= ord(c) < 127 for c in text), text)

    def test_the_companions_table_is_generated(self) -> None:
        import build_more_island_events as builder
        self.assertEqual((NATIVE / "ceremony_text.inc").read_text(encoding="utf-8"), builder.ceremony_text_inc())

    def test_every_piece_is_a_key_row(self) -> None:
        rows = json.loads((ROOT / "data" / "translations" / "patcher_strings.json").read_text(encoding="utf-8"))
        by_stem = {r["stem"]: r for r in rows["strings"]}
        for module in (rc, rb):
            for stem, _key, english, _ in module.rows():
                self.assertIn(stem, by_stem)
                self.assertEqual(by_stem[stem]["english"], english)
                self.assertEqual(by_stem[stem]["games"], ["vv1", "vv2", "vv3", "vv4", "vv5"])

    def test_the_game_mechanics_pages_list_both_with_the_patch(self) -> None:
        import importlib
        for game in (1, 2, 3, 4, 5):
            events = importlib.import_module(f"vv_game_mechanics_events_vv{game}").EVENTS
            mine = {e.title: e for e in events if e.title in (rc.TITLE, rb.TITLE)}
            self.assertEqual(set(mine), {rc.TITLE, rb.TITLE}, game)
            for event in mine.values():
                self.assertEqual(event.only_with, f"vv{game}_more_island_events")
                self.assertIn("wall clock", event.text)
            text = " ".join(str(s) for s in mine[rc.TITLE].subs)
            self.assertIn("children", text)
            self.assertIn("nursing mothers and fathers", text)
            self.assertIn("never below 0", text)
            text = " ".join(str(s) for s in mine[rb.TITLE].subs)
            self.assertIn("over its population limit keeps everyone", text)
            self.assertIn("Solved puzzles stay solved", text)

    def test_the_damage_rule(self) -> None:
        self.assertEqual(rb.progress_after(2000, 1750, 100), 1750)
        self.assertEqual(rb.progress_after(2000, 1750, 10), 1975)
        self.assertEqual(rb.progress_after(450, 205, 100), 205)
        self.assertEqual(rb.progress_after(400, 0, 55), 180)


# ---- Emulated ---------------------------------------------------------------------------------------------------

@NEEDS
class WhenItCanHappen(unittest.TestCase):
    def test_the_remembrance_ceremony_needs_one_grave(self) -> None:
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                v = remembrance_village(game)
                v.graves(0)
                self.assertEqual(v.possible(REMEMBRANCE), 0)
                v.graves(1)
                self.assertEqual(v.possible(REMEMBRANCE), 1)

    def test_new_believers_needs_the_last_heathen(self) -> None:
        v = remembrance_village(5)
        v.last_heathen(False)
        self.assertEqual(v.possible(REMEMBRANCE), 0)
        v.last_heathen(True)
        self.assertEqual(v.possible(REMEMBRANCE), 1)

    def test_the_rumblings_needs_every_puzzle_and_a_finished_structure(self) -> None:
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                v = rumblings_village(game)
                self.assertEqual(v.possible(RUMBLINGS), 0)        # no structure finished
                v.finish(v.structures() - 1)
                self.assertEqual(v.possible(RUMBLINGS), 1)
                v.puzzles(missing=3)
                self.assertEqual(v.possible(RUMBLINGS), 0)        # one puzzle missing
                v.puzzles()
                self.assertEqual(v.possible(RUMBLINGS), 1)

    def test_a_puzzle_structure_never_counts(self) -> None:
        v = rumblings_village(1)
        v.p.write(v.world + 0x9FE8, b"\x01")                     # "The Hut" (a puzzle) done: not a candidate
        self.assertEqual(v.possible(RUMBLINGS), 0)
        v = rumblings_village(2)
        for flag in (0x2E760, 0x2E780, 0x2E790):                  # the Lovely Hut, the Hospital, the Sewing Hut
            v.p.write(v.world + flag, b"\x01")
        self.assertEqual(v.possible(RUMBLINGS), 0)
        v = rumblings_village(5)
        v.p.put32(0x51DC50, 0)
        v.p.put32(0x51DC50 + 8, 24)                                 # the nursery school: left out
        v.p.put32(0x51DF30 + 4 * 24, 2000)
        v.p.put32(0x51E008 + 8 * 24, 2000)
        self.assertEqual(v.possible(RUMBLINGS), 0)


@NEEDS
class TheRemembranceCeremony(unittest.TestCase):
    def everyone(self, v: Ceremony) -> list[int]:
        """Villagers of every kind: 0 Ana, 1 Ben, 2 a toddler, 3 a nursing mother, 4 a protected one, 5 a teen."""
        g = v.game
        v.villager(2, "Tot", years=0)
        v.villager(3, "Mum", True, years=25, carrying=1)
        special = {1: (0x36C, 4, 0xC7), 2: None, 3: (0xE80, 1, 1), 4: None, 5: None}[g]
        v.villager(4, "Pro", years=40, special=special)
        v.villager(5, "Teen", years=15)
        if g == 3:
            v.p.write(v.rec(5) + 0xF13, b"\x01")                 # a puzzle's worker
            v.p.put32(v.rec(2) + 0xF20, 3)                       # a child holding an object
        return [0, 1, 2, 3, 4, 5]

    def test_everyone_goes_through_the_games_own_starter(self) -> None:
        expected_do = {3: (0xA, 0x16), 4: (9,), 5: (17,)}
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                v = remembrance_village(game)
                people = self.everyone(v)
                v.pop = len(people)
                v.set_food(1000)
                rolls = [0, 99] * 3
                text = v.happen(REMEMBRANCE, rolls)
                self.assertIn(rc.TITLE, text)
                self.assertEqual(words(text).replace(rc.TITLE, "").strip(), rc.english("TEXT"))
                state = v.cr_state()
                self.assertEqual(state[0], REMEMBRANCE)
                self.assertEqual(state[1], len(people))
                for i in people:
                    self.assertIn(v.act(i), (ACT_HONOR, ACT_REFLECT))
                if game in (1, 2):
                    stops = [s[1] for s in v.sent if s[0] == "stop"]
                    self.assertEqual(stops, people)
                    if game == 1:
                        self.assertEqual([s[1] for s in v.sent if s[0] == "honor"], people)
                    else:
                        self.assertEqual([v.act(i) for i in people], [ACT_HONOR, ACT_REFLECT] * 3)
                        self.assertEqual([s[0] for s in v.sent if s[0] in ("honor", "reflect")],
                                         ["honor", "reflect"] * 3)
                else:
                    did = [s for s in v.sent if s[0] == "do"]
                    self.assertEqual([d[1] for d in did], people)
                    for d in did:
                        self.assertIn(d[2], expected_do[game])
                    if game == 3:
                        self.assertEqual([d[2] for d in did], [0xA, 0x16] * 3)
                        self.assertEqual([s[1] for s in v.sent if s[0] == "kick"], people)
                    if game == 4:
                        self.assertEqual([s[1] for s in v.sent if s[0] == "kick"], people)
                    stops = [c for c in v.calls if c[0] == "stop"] if game in (4, 5) else \
                        [s for s in v.sent if s[0] == "stop"]
                    self.assertEqual(len(stops), len(people))

    def test_never_the_dead_the_absent_or_heathens(self) -> None:
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                v = remembrance_village(game)
                v.villager(2, "Dead", health=0)
                v.villager(3, "Gone")
                v.p.write(v.rec(3) + v.L["present"], b"\x00")
                if game == 5:
                    v.villager(4, "Heathen", special=(0x1CEC, 1, 1))
                if game == 4:
                    v.villager(4, "Ghost", special=(0x1CC7, 1, 1))
                if game == 3:
                    v.villager(4, "Double", special=(0xE94, 1, 1))
                v.set_food(1000)
                v.happen(REMEMBRANCE, [0] * 8)
                self.assertEqual(v.cr_state()[1], 2)
                for i in (2, 3, 4):
                    self.assertEqual(v.act(i), 0)

    def test_the_feast_ten_food_each_never_below_zero(self) -> None:
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                v = remembrance_village(game)
                v.pop = 7
                v.set_food(500)
                v.happen(REMEMBRANCE, [0] * 4)
                self.assertEqual(v.food(), 430)
                self.assertEqual(v.cr_state()[3], 70)
                v = remembrance_village(game)
                v.pop = 7
                v.set_food(30)
                v.happen(REMEMBRANCE, [0] * 4)
                self.assertEqual(v.food(), 0)

    def test_new_believers_with_the_hovel_patch(self) -> None:
        import build_vv5_hovel_memorial_actions as hovel
        v = remembrance_village(5)
        self.assertEqual(v.p.export("VvfpCeremonyHovelPatch"), 0)
        v.happen(REMEMBRANCE, [0] * 4)
        self.assertEqual([v.act(0), v.act(1)], [ACT_HONOR, ACT_HONOR])   # no patch: the mausoleum, no rolls
        v = remembrance_village(5)
        for patch in hovel.feature()["patches"]:
            v.p.mu.mem_write(0x400000 + int(patch["offset"], 16), bytes.fromhex(patch["after"]))
        v.p.mu.ctl_flush_tb()
        self.assertEqual(v.p.export("VvfpCeremonyHovelPatch"), 1)
        v.villager(2, "Cid")
        _, _, at = hovel.caves()
        # Ana: the hovel, Honoring; Ben: the hovel, Reflecting; Cid: the mausoleum.
        v.happen(REMEMBRANCE, [0, 0, 0, 99, 99])
        self.assertEqual([v.act(0), v.act(1), v.act(2)], [ACT_HOVEL_HONOR, ACT_HOVEL_REFLECT, ACT_HONOR])
        starts = [s for s in v.sent if s[0] == "do"]
        self.assertEqual([(s[1], s[2]) for s in starts], [(0, 17), (2, 17)])
        self.assertEqual(starts[0][3], at["honor_mark"])          # the patch's own mark: its walks go to the hovel
        self.assertNotEqual(starts[1][3], at["honor_mark"])
        reflect = [s for s in v.sent if s[0] == "reflect"]
        self.assertEqual(reflect, [("reflect", 1, at["reflect_mark"])])
        self.assertEqual(v.p.u32(v.rec(1) + 0x1D10), 29)
        self.assertEqual(v.cr_state()[2], 2)

    def test_one_log_entry(self) -> None:
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                v = remembrance_village(game)
                calls = fake_log(v)
                v.set_food(100)
                v.happen(REMEMBRANCE, [0] * 4)
                writes = [c for c in calls if c[0] == "write"]
                self.assertEqual(len(writes), 1)
                self.assertEqual(writes[0][3], 1)                    # final: handed over once, complete
                entry = writes[0][2]
                self.assertTrue(entry.startswith(f"  Event: {rc.TITLE}\n"), entry)
                self.assertIn("  Villagers at the ceremony: 2\n", entry)
                self.assertEqual([c[0] for c in calls], ["begin", "end", "write"])
                self.assertEqual(logged(v, rc.TITLE), 1)


@NEEDS
class TheRumblings(unittest.TestCase):
    def test_each_at_25_percent_and_the_loss(self) -> None:
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                v = rumblings_village(game)
                n = v.structures()
                for k in range(n):
                    v.finish(k)
                before = v.puzzle_bytes()
                health = [v.health(0), v.health(1)]
                # The first damaged (24 < 25), the rest not (25); its loss 10 + 45 = 55%.
                text = v.happen(RUMBLINGS, [24] + [25] * (n - 1) + [45])
                self.assertIn(rb.TITLE, text)
                self.assertEqual(words(text).replace(rb.TITLE, "").strip(), rb.english("TEXT"))
                state = v.cr_state()
                self.assertEqual(state[4], n)
                self.assertEqual(state[5], 0)
                self.assertEqual(state[7:7 + n], [55] + [0] * (n - 1))
                _, done_at, start = rb.STRUCTURES[game][0]
                self.assertEqual(v.progress(0), rb.progress_after(done_at, start, 55))
                for k in range(1, n):
                    self.assertEqual(v.progress(k), rb.STRUCTURES[game][k][1] if game != 2 or k else 24)
                self.assertEqual(v.puzzle_bytes(), before)            # solved puzzles stay solved
                self.assertEqual([v.health(0), v.health(1)], health)  # no one is hurt
                self.assertEqual([v.present(0), v.present(1)], [1, 1])

    def test_at_least_one_and_every_one(self) -> None:
        for game in (1, 3, 4):
            with self.subTest(game=game):
                v = rumblings_village(game)
                n = v.structures()
                for k in range(n):
                    v.finish(k)
                v.happen(RUMBLINGS, [99] * n + [TOP, 0])               # none drawn: the last picked, 10%
                state = v.cr_state()
                self.assertEqual(state[5], 1)
                self.assertEqual(state[7:7 + n], [0] * (n - 1) + [10])
                v = rumblings_village(game)
                for k in range(n):
                    v.finish(k)
                v.happen(RUMBLINGS, [0] * n + [0] * n)                # every one damaged
                self.assertEqual(v.cr_state()[7:7 + n], [10] * n)

    def test_100_percent_is_the_new_village(self) -> None:
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                v = rumblings_village(game)
                v.finish(0)
                v.happen(RUMBLINGS, [0, TOP])
                self.assertEqual(v.cr_state()[7], 100)
                p = v.p
                if game == 1:
                    self.assertEqual(p.read(v.world + 0x9FF0, 1), b"\x00")
                    self.assertEqual(v.progress(0), 0)
                    self.assertIn(("nav",), v.sent)
                    self.assertIn(("scene",), v.sent)
                elif game == 2:
                    self.assertEqual(p.read(v.world + 0x2E818, 1), b"\x00")
                    self.assertEqual(v.progress(0), 205)
                    self.assertIn(("nav",), v.sent)
                elif game == 3:
                    hut = 0x594620 + 4
                    self.assertEqual(v.progress(0), 1750)
                    self.assertEqual(p.read(hut, 1), b"\x00")
                    self.assertEqual([p.u32(hut + 4), p.u32(hut + 8), s32(p.u32(hut + 0xC))], [1, 0, -1])
                else:
                    obj = LATE[game]["objects"][0][1]
                    self.assertEqual(v.progress(0), 0)
                    self.assertEqual(p.read(obj + 0x30, 1), b"\x00")       # unbuilt: it can be moved
                    self.assertEqual([p.u32(obj + 0x34), p.u32(obj + 0x38), s32(p.u32(obj + 0x3C))], [3, 2000, -1])

    def test_partial_damage_is_a_construction_under_way(self) -> None:
        for game in (3, 4, 5):
            with self.subTest(game=game):
                v = rumblings_village(game)
                v.finish(1)
                v.happen(RUMBLINGS, [0, 30])                            # 40%
                p = v.p
                if game == 3:
                    hut = 0x594620 + 4 + 0x14
                    self.assertEqual(v.progress(1), 400 + (1600 * 60) // 100)
                    self.assertEqual(p.read(hut, 1), b"\x01")
                    self.assertEqual([p.u32(hut + 4), p.u32(hut + 8), s32(p.u32(hut + 0xC))], [2, 1600, -1])
                else:
                    obj = LATE[game]["objects"][1][1]
                    self.assertEqual(v.progress(1), 1200)
                    self.assertEqual(p.read(obj + 0x30, 1), b"\x01")
                    self.assertEqual([p.u32(obj + 0x34), p.u32(obj + 0x38), s32(p.u32(obj + 0x3C))], [3, 2000, -1])

    def test_the_three_huts_trophy_still_needs_three_different_huts(self) -> None:
        for game, entry in ((4, 0x4CBB98 + 0x2D * 12), (5, 0x4DB358 + 0x31 * 12)):
            with self.subTest(game=game):
                v = rumblings_village(game)
                v.finish(0)
                v.finish(3)                                             # the clothing hut: not this trophy
                v.p.write(entry, b"\x00")
                v.p.put32(entry + 4, 2)                                 # locked, two huts counted
                v.happen(RUMBLINGS, [0, 0, 30, 30])                     # both damaged
                self.assertEqual(v.cr_state()[7:11], [40, 0, 0, 40])
                self.assertEqual(v.p.u32(entry + 4), 1)                 # only the hut's count taken back
                v = rumblings_village(game)
                v.finish(0)
                v.p.write(entry, b"\x01")
                v.p.put32(entry + 4, 3)                                 # unlocked: left alone
                v.happen(RUMBLINGS, [0, 30])
                self.assertEqual(v.p.u32(entry + 4), 3)

    def test_the_tree_of_lifes_nursery_teacher_let_go(self) -> None:
        v = rumblings_village(4)
        v.villager(2, "Teacher", True, years=30)
        v.p.put32(v.rec(2) + 0x1C54, 0x10)
        v.finish(5)                                                     # the nursery school
        v.p.stub(0x4374C0, lambda pr: (0, 0))
        v.happen(RUMBLINGS, [0, 0])
        self.assertEqual(v.p.u32(v.rec(2) + 0x1C54), 0)
        self.assertIn(("stop", v.rec(2)), v.calls)

    def test_over_the_limit_keeps_everyone(self) -> None:
        """A New Home: 30 villagers need the second hut; damaged, the game's own room test says no room -- and
        everyone is still there, alive."""
        v = rumblings_village(1)
        v.pop = 30
        for i in range(30):
            v.villager(i, f"V{i}")
        v.finish(0)
        v.finish(1)
        for off in (0x9FE8,):
            v.p.write(v.world + off, b"\x01")
        room_before = v.p.call(0x43A1A0, [], ecx=v.base) & 0xFF
        v.happen(RUMBLINGS, [0, 99, 50])
        room_after = v.p.call(0x43A1A0, [], ecx=v.base) & 0xFF
        self.assertEqual(room_before, 1)
        self.assertEqual(room_after, 0)
        self.assertEqual([v.present(i) for i in range(30)], [1] * 30)
        self.assertEqual([v.health(i) for i in range(30)], [100] * 30)

    def test_one_log_entry_with_each_damaged_structure(self) -> None:
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                v = rumblings_village(game)
                v.finish(0)
                calls = fake_log(v)
                v.happen(RUMBLINGS, [0, 40])
                writes = [c for c in calls if c[0] == "write"]
                self.assertEqual(len(writes), 1)
                entry = writes[0][2]
                name = rb.STRUCTURES[game][0][0]
                self.assertTrue(entry.startswith(f"  Event: {rb.TITLE}\n"), entry)
                self.assertTrue(entry.endswith(f"  Damaged: {name}, 50% of its building work lost\n"), entry)


@NEEDS
class TheDraw(unittest.TestCase):
    def test_a_new_home_and_the_lost_children_never_widen_and_put_it_back(self) -> None:
        for game, site, stock in ((1, 0x4284DB, "E830AAFDFF"), (2, 0x434607, "E894EBFCFF")):
            with self.subTest(game=game):
                v = remembrance_village(game)
                widths = []
                rand = v.rand

                def spy(pr, inner=v._rand):
                    widths.append(pr.arg(0))
                    return inner(pr)
                v.p.stub(rand, spy)
                v.happen(REMEMBRANCE, [])
                self.assertNotIn((15 if game == 1 else 28) + 1, widths)     # never one wider
                self.assertEqual(v.draw_site.hex().upper(), stock)           # put back
                self.assertEqual(v.cr_state()[0], REMEMBRANCE)
                self.assertEqual(v.done, [(game, 1)])

    def test_nothing_due_the_chooser_is_stock(self) -> None:
        """Both events possible and nothing due: the chooser's draw is never redirected and keeps its stock bound."""
        from unicorn import UC_HOOK_MEM_WRITE
        for game, draw_site, cases in ((1, 0x4284DB, 15), (2, 0x434607, 28)):
            with self.subTest(game=game):
                v = remembrance_village(game)
                v.puzzles()
                for k in range(v.structures()):
                    v.finish(k, False)
                v.finish(0)
                self.assertTrue(v.possible(REMEMBRANCE) and v.possible(RUMBLINGS))
                widths: list[int] = []

                def spy(pr, inner=v._rand):
                    widths.append(pr.arg(0))
                    return inner(pr)
                v.p.stub(v.rand, spy)
                writes: list[int] = []
                v.p.mu.hook_add(UC_HOOK_MEM_WRITE, lambda mu, a, address, size, value, d: writes.append(address),
                                begin=draw_site, end=draw_site + 4)
                v.due = -1
                p, g = v.p, game
                ctor, chooser, site = (0x4286B0, 0x428470, 0x423A06) if g == 1 else (0x4348E0, 0x434570, 0x42F0F7)
                rel = (chooser - (ctor + 5)) & 0xFFFFFFFF
                p.mu.mem_write(ctor, b"\xE9" + struct.pack("<I", rel))
                p.mu.ctl_flush_tb()
                event = p.alloc(0x6000)
                p.put32(event + 0x50A4, v.world if g == 1 else v.base)
                p.put32(event + 0x50A8, v.base)
                p.put32(event + 0x50AC, v.world)
                v.rolls = [0] * 12
                esp = STACK_TOP - 0x3000
                p.put32(esp, 2)
                p.put32(esp + 4, 3)
                p.set_reg("esp", esp)
                p.set_reg("ecx", event)
                p.run(site, site + 5)
                self.assertTrue(widths)
                self.assertEqual(set(widths), {cases})                       # the stock bound only
                self.assertEqual(writes, [])                                 # the draw's call never written
                self.assertEqual(v.cr_state()[6], 0)                         # nothing of ours happened

    def test_the_later_games_add_no_entry_and_put_the_due_one_in_slot_0(self) -> None:
        for game in (3, 4, 5):
            with self.subTest(game=game):
                v = Ceremony(game)
                v.villager(0, "Ana", True, years=10)                 # no other event can happen (one child)
                self.assertFalse(v.due_can_happen(REMEMBRANCE))
                self.assertFalse(v.due_can_happen(RUMBLINGS))
                v.graves(1)
                if game == 5:
                    v.last_heathen(True)
                self.assertTrue(v.due_can_happen(REMEMBRANCE))
                self.assertFalse(v.due_can_happen(RUMBLINGS))
                v.puzzles()
                for k in range(v.structures()):
                    v.finish(k, False)
                v.finish(0)
                self.assertTrue(v.due_can_happen(REMEMBRANCE))
                self.assertTrue(v.due_can_happen(RUMBLINGS))
                v.due = -1
                self.assertEqual(v.run_list(0), 0)                   # nothing due: still no entry

    def test_it_happens_once_only_in_the_presenter(self) -> None:
        v = remembrance_village(3)
        obj = v.p.export("VvfpCeremonyObject", REMEMBRANCE)
        v.p.call(v.p.u32(v.p.u32(obj) + 8), [], ecx=obj)        # asked outside the presenter: nothing happens
        self.assertEqual(v.cr_state()[6], 0)
        v.set_food(200)
        v.happen(REMEMBRANCE, [0] * 4)
        self.assertEqual(v.cr_state()[6], 1)
        food = v.food()
        obj_title = v.p.u32(v.p.u32(obj) + 8)
        v.p.call(obj_title, [], ecx=obj)                           # asked again: not twice
        self.assertEqual(v.food(), food)


if __name__ == "__main__":
    unittest.main()
