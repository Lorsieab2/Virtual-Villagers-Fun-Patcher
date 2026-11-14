"""Empty the Stew Pot from the Science Hut Door (The Lost Children): vv2_empty_stew_pot.

The owner (2026-11-14): a villager aged 14 or older dropped on the doorway of the science hut while a READY stew is in
the pot walks to the pot and empties it ("Emptying the pot"), as The Secret City and The Tree of Life let the player
empty theirs.  A villager who dislikes cooking refuses and runs away, as at the pot.  At the doorway the emptying wins
over the drop-on-another-villager code.  With no ready stew (none, or one still being made), or a villager under 14,
the drop is the stock game's, unchanged.

Everything below RUNS the shipped "VVFP VV2 Empty Stew.dll" beside the stock executable (or the executable as the
patcher renders it with every other row, in every mode), started as VVFP Startup.dll starts it
(tests/story_emulator.py's Process):

* the map is the game's own: its builder 0x418660 runs on the map object and the drop reads it with 0x4181D0;
* the village drop routine runs whole from 0x430AB4 (where it takes the dropped villager's record) to its stock tail
  0x430F63, the routines it hands off to (the area dispatch 0x42FB20, the villager under the mouse 0x4490C0, the
  child jobs, the tips, the pairing) are stand-ins that record their arguments, and every run is compared with the
  same drop without the companion: calls, the villager's record and the pot;
* the job the companion queues is built by the game's own push 0x449B70 and its dislike test 0x4454E0, its callback
  goes through the real dispatcher 0x461B10 (detoured) into the game's own pot routine 0x425B20.

What is NOT run here: the game's frame loop, the player's drag itself, the walk and the look of the job (not yet
verified in play).
"""
from __future__ import annotations

import functools
import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as vfp  # noqa: E402

try:
    import pefile
    from story_emulator import Process
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"
DLL_NAME = "VVFP VV2 Empty Stew.dll"
DLL = ROOT / "assets" / "vv2_empty_stew" / DLL_NAME
ROW = "vv2_empty_stew_pot"
NAME = "Empty the Stew Pot from the Science Hut Door"
MODES = ("stock", "collection_progression", "immediate_fixed")
NEEDS = unittest.skipUnless(HAVE_EMULATOR and EXE.is_file() and DLL.is_file(),
                            "unicorn/pefile, the stock executable or the companion is missing")

# The detours (va, stock bytes) and the stock code the companion checks before writing anything.
DETOURS = ((0x430AF9, "8B8840050000"), (0x4642EB, "5E5B59C20800"))
CHECKED = ((0x430AB4, "8B86E40100008B4E2069C08CE4000003C1"), (0x430AFF, "85C9"), (0x430F63, "8B8EE4010000"),
           (0x461B18, "4883F845568BF1895C24080F87C2270000"), (0x449B70, "83EC188B4424208B"),
           (0x44FBB0, "8B4424048BD069D2"),
           (0x4454E0, "8B54240433C069D2"), (0x44B010, "5356578B7C24108B"), (0x425B20, "33C089814C040300"))

DROP_FROM, DROP_DONE = 0x430AB4, 0x430F63
DISPATCH = 0x461B10
RECORD, LABEL, AGE, EXPECTING, DISLIKES = 0xE48C, 0x4FC, 0x530, 0x540, 0x6E8
STEW, STEW_END, STARTED = 0x3044C, 0x30450, 0x30448
CB_EMPTY = 0x0E57
SLOT, OTHER = 5, 9
# The hand-offs of the drop routine, each a stand-in (pops): the area dispatch, the child jobs, the tips, the
# villager under the mouse, the pairing calls and the job queue's clear.
HANDOFFS = {0x42FB20: 8, 0x45BCA0: 4, 0x45BF10: 4, 0x4257A0: 8, 0x4490C0: 0xC, 0x4492A0: 4, 0x45D4B0: 4,
            0x45D510: 4, 0x45D580: 4, 0x44B310: 0}
START, RUN_AWAY = 0x44FBB0, 0x44B010
DOOR = (790, 580)                      # the feet on the hut's door (x 780..819, y 550..609)
STEP = (800, 605)                      # the feet on the open ground in front of the step
BENCH = (900, 590)                     # area 6: "Researching"
PORCH = (900, 630)                     # area 45: "Researching"
WALL = (760, 520)                      # the hut's blocked ground, away from the door
POT = (740, 850)                       # area 19: the pot


def _va_bytes(data: bytes, va: int, n: int) -> str:
    pe = pefile.PE(data=data, fast_load=True)
    off = pe.get_offset_from_rva(va - 0x400000)
    return data[off:off + n].hex().upper()


@functools.lru_cache(maxsize=None)
def _rendered(ids: tuple[str, ...], mode: str) -> bytes:
    build = next(b for b in vfp.load_builds() if b.id == "vv2")
    data, _ = vfp.render_patched_bytes(EXE, build, mode, list(ids))
    return bytes(data)


def _others() -> list[str]:
    alts = set(vfp.ALTERNATIVE_FUN_PATCH_IDS)
    return [p.id for p in vfp.load_public_fun_patches()
            if p.game_id == "vv2" and p.id not in alts and p.id != ROW]


class Village:
    """The Lost Children in memory: the scene, its map (built by the game), the villagers and the game state."""

    def __init__(self, exe: bytes | None = None, *, with_dll: bool = True):
        self.p = p = Process(exe if exe is not None else EXE.read_bytes(), DLL)
        self.calls: list[tuple[int, tuple[int, ...]]] = []
        self.installed = 0
        if with_dll:
            p.export("VvfpStartup", 2, 0)
            self.installed = p.export("VvfpVv2EmptyStewInstalled")
        self.scene = p.alloc(0x400)
        self.mgr = p.alloc(0xE58000)
        self.state = p.alloc(0x40000)
        self.map = p.alloc(0x1C400)
        p.put32(self.scene + 0x10, self.state)
        p.put32(self.scene + 0x14, self.map)
        p.put32(self.scene + 0x20, self.mgr)
        p.put32(self.mgr + 0xE574D4, self.state)
        p.put32(self.map + 0x1C394, self.state)
        p.put32(self.scene + 0x1E4, SLOT)
        # The cauldron is placed (+0x2E8A8, "Retrieving a cauldron"): there is no stew without it, and the map
        # then has the pot's place (area 19).
        p.write(self.state + 0x2E8A8, b"\x01")
        p.put32(self.state + 0x2EAC4, 1000)            # the fire burns (the map's area 19, not the unlit pit's 61)
        # The map builder's own reads: the clock, the population and the puzzle checks, the lying item.
        for va, pop, value in ((0x403200, 0, 0), (0x425860, 0, 0), (0x426180, 4, 0), (0x416060, 0, 0),
                               (0x4152D0, 0, 0), (0x4152E0, 0, 0)):
            self.stub(va, pop, value)
        p.call(0x418660, [], ecx=self.map)
        for va in (0x403200, 0x425860, 0x426180, 0x416060, 0x4152D0, 0x4152E0):
            del p.stubs[va]
        self.calls.clear()
        self.under_mouse = -1
        for va, pop in HANDOFFS.items():
            self.stub(va, pop, (lambda v, a, e: v.under_mouse) if va == 0x4490C0 else 0)
        self.stub(START, 4)
        self.stub(RUN_AWAY, 4)
        self.stub(0x41C1D0, 0)                         # the pot's puzzle redraw (the stock stew start's)
        for slot in (SLOT, OTHER):
            self.villager(slot, age=600)

    def stub(self, va: int, pop: int, result=0) -> None:
        def fn(p):
            args = tuple(p.arg(i) for i in range(4))
            self.calls.append((va, args[:pop // 4]))
            value = result(self, args, p.reg("ecx")) if callable(result) else result
            return value & 0xFFFFFFFF, pop
        self.p.stub(va, fn)

    def record(self, slot: int = SLOT) -> int:
        return self.mgr + slot * RECORD

    def villager(self, slot: int, *, age: int, dislikes: tuple[int, ...] = (), expecting: int = 0) -> None:
        r = self.record(slot)
        self.p.put32(r + AGE, age)
        self.p.put32(r + EXPECTING, expecting)
        for i in range(0x3E):
            self.p.put32(r + DISLIKES + 4 * i, dislikes[i] if i < len(dislikes) else 0xFFFF)

    def stew(self, number: int, end: int = 1000, *, started: int = 0, herbs: tuple[int, int, int] = (0, 0, 0)) -> None:
        self.p.put32(self.state + STEW, number)
        self.p.put32(self.state + STEW_END, end)
        self.p.write(self.state + STARTED, bytes([started]))
        for i, h in enumerate(herbs):
            self.p.put32(self.state + 0x3043C + 4 * i, h)

    def pot(self) -> bytes:
        return self.p.read(self.state + 0x3043C, 0x1C)

    def drop(self, feet: tuple[int, int], slot: int = SLOT) -> None:
        """The held villager released with its feet at `feet` (the drop reads the map at record x + 0x14,
        y + 0x41): the drop routine from 0x430AB4 to its stock tail."""
        r = self.record(slot)
        self.p.put32(r + 4, feet[0] - 0x14)
        self.p.put32(r + 8, feet[1] - 0x41)
        self.p.put32(self.scene + 0x1E4, slot)
        self.p.call(DROP_FROM, [0] * 16, regs={"esi": self.scene}, until=DROP_DONE, limit=500_000)

    def steps(self, slot: int = SLOT) -> list[tuple[int, ...]]:
        out = []
        for i in range(0x31):
            entry = struct.unpack("<6I", self.p.read(self.record(slot) + 0x4C + i * 24, 24))
            if entry[0] == 0:
                break
            out.append(entry)
        return out

    def finish(self, slot: int = SLOT) -> None:
        """The job played to its end: each step 17 through the game's dispatcher."""
        for step, *_rest, param in self.steps(slot):
            if step == 0x11:
                self.p.call(DISPATCH, [slot, param], ecx=self.mgr)

    def label(self, slot: int = SLOT) -> str:
        return self.p.cstring(self.record(slot) + LABEL, 0x30)

    def snapshot(self, slot: int = SLOT):
        return (self.calls[:], self.p.read(self.record(slot), 0x7F0), self.pot())


def _area(v: Village, feet: tuple[int, int]) -> int:
    return v.p.call(0x4181D0, [feet[0], feet[1]], ecx=v.map)


@NEEDS
class DoorwayTests(unittest.TestCase):
    def test_the_companion_installs_on_the_stock_game(self):
        v = Village()
        self.assertEqual(v.installed, 1)
        for va, stock in DETOURS:
            self.assertEqual(v.p.read(va, 1), b"\xE9")
            self.assertNotEqual(v.p.read(va, len(stock) // 2).hex().upper(), stock)

    def test_the_places(self):
        v = Village(with_dll=False)
        self.assertEqual(_area(v, DOOR), 1)            # the hut's blocked ground
        self.assertEqual(_area(v, STEP), 0)
        self.assertEqual(_area(v, BENCH), 6)
        self.assertEqual(_area(v, PORCH), 45)
        self.assertEqual(_area(v, WALL), 1)
        self.assertEqual(_area(v, POT), 19)
        # every cell of the doorway is the hut's ground or open ground: no place of the game's own
        for x in range(780, 820, 10):
            for y in range(550, 610, 10):
                self.assertIn(_area(v, (x, y)), (0, 1), (x, y))

    def test_a_ready_stew_is_emptied_after_the_trip(self):
        for feet in (DOOR, STEP, (780, 550), (819, 609)):
            with self.subTest(feet=feet):
                v = Village()
                v.stew(7, 5000)
                v.drop(feet)
                self.assertEqual(v.label(), "Emptying the pot")
                self.assertEqual([c for c in v.calls if c[0] == START], [(START, (SLOT,))])
                self.assertNotIn(0x42FB20, [c[0] for c in v.calls])     # no stock hand-off
                steps = v.steps()
                self.assertEqual([(s[0], s[5]) for s in steps],
                                 [(3, 0x64), (0xB, 0), (0x15, 0x41), (0x11, CB_EMPTY), (2, 1), (0x16, 0)])
                self.assertEqual(steps[0][1:3], (0x30B, 0x37F))          # the pot
                self.assertEqual(v.p.u32(v.state + STEW), 7, "the pot is emptied at the pot, not at the drop")
                v.finish()
                self.assertEqual(v.pot(), bytes(0x1C))                    # the game's own empty: 0x425B20

    def test_no_stew_or_a_stew_being_made_is_the_stock_drop(self):
        for name, setup in (("no stew", lambda v: None),
                            ("started", lambda v: v.stew(0, 0, started=1, herbs=(0x30, 0x31, 0))),
                            ("timed out", lambda v: v.stew(0, 0))):
            for feet in (DOOR, STEP):
                for under in (-1, OTHER):
                    with self.subTest(name=name, feet=feet, under=under):
                        runs = []
                        for with_dll in (False, True):
                            v = Village(with_dll=with_dll)
                            v.under_mouse = under
                            setup(v)
                            v.drop(feet)
                            runs.append(v.snapshot())
                        self.assertEqual(runs[0], runs[1])
                        self.assertNotIn(START, [c[0] for c in runs[1][0]])

    def test_under_14_is_the_stock_drop(self):
        for age in (0, 100, 279):
            for expecting in (0, 1):
                with self.subTest(age=age, expecting=expecting):
                    runs = []
                    for with_dll in (False, True):
                        v = Village(with_dll=with_dll)
                        v.villager(SLOT, age=age, expecting=expecting)
                        v.stew(3, 900)
                        v.drop(DOOR)
                        runs.append(v.snapshot())
                    self.assertEqual(runs[0], runs[1])
                    self.assertEqual(runs[1][2][0x10:0x14], struct.pack("<I", 3))

    def test_from_14_anyone_empties_it(self):
        for age, expecting in ((280, 0), (300, 1), (1200, 0)):
            with self.subTest(age=age, expecting=expecting):
                v = Village()
                v.villager(SLOT, age=age, expecting=expecting)
                v.stew(12, 777)
                v.drop(DOOR)
                v.finish()
                self.assertEqual(v.p.u32(v.state + STEW), 0)

    def test_a_cooking_hater_runs_away(self):
        v = Village()
        v.villager(SLOT, age=600, dislikes=(0x10, 0x31))
        v.stew(4, 2000)
        v.drop(DOOR)
        self.assertEqual([c for c in v.calls if c[0] in (RUN_AWAY, START)], [(RUN_AWAY, (SLOT,))])
        self.assertEqual(v.steps(), [])
        self.assertEqual(v.p.u32(v.state + STEW), 4)
        # another dislike is no refusal
        v = Village()
        v.villager(SLOT, age=600, dislikes=(0x10, 0x30))
        v.stew(4, 2000)
        v.drop(DOOR)
        self.assertNotIn(RUN_AWAY, [c[0] for c in v.calls])

    def test_the_doorway_wins_over_the_villager_under_the_mouse(self):
        v = Village()
        v.under_mouse = OTHER
        v.stew(9, 3000)
        v.drop(DOOR)
        self.assertNotIn(0x4490C0, [c[0] for c in v.calls])
        v.finish()
        self.assertEqual(v.p.u32(v.state + STEW), 0)

    def test_a_newer_stew_is_never_emptied(self):
        # the stew ran out and a new one was cooked before the villager reached the pot
        v = Village()
        v.stew(7, 5000)
        v.drop(DOOR)
        v.stew(11, 5900)
        v.finish()
        self.assertEqual(v.p.u32(v.state + STEW), 11)
        # the stew ran out on the way: nothing to empty, nothing else touched
        v = Village()
        v.stew(7, 5000)
        v.drop(DOOR)
        v.stew(0, 0, started=1, herbs=(0x32, 0, 0))
        before = v.pot()
        v.finish()
        self.assertEqual(v.pot(), before)
        # two villagers: the second finds the pot already empty and a new stew is safe from it
        v = Village()
        v.stew(7, 5000)
        v.drop(DOOR, SLOT)
        v.drop(DOOR, OTHER)
        v.finish(SLOT)
        v.stew(2, 6100)
        v.finish(OTHER)
        self.assertEqual(v.p.u32(v.state + STEW), 2)
        # a callback the job did not queue (a job from before a reload) does nothing
        v = Village()
        v.stew(7, 5000)
        v.p.call(DISPATCH, [SLOT, CB_EMPTY], ecx=v.mgr)
        self.assertEqual(v.p.u32(v.state + STEW), 7)

    def test_drops_elsewhere_on_the_hut_are_unchanged(self):
        for feet in (BENCH, PORCH, WALL, POT, (779, 580), (820, 580), (800, 549), (800, 610)):
            for stew in (0, 5):
                with self.subTest(feet=feet, stew=stew):
                    runs = []
                    for with_dll in (False, True):
                        v = Village(with_dll=with_dll)
                        v.stew(stew, 1000 if stew else 0)
                        v.drop(feet)
                        runs.append(v.snapshot())
                    self.assertEqual(runs[0], runs[1])
        # the research drop is the game's: area 6 and 45 go to the area dispatch
        v = Village()
        v.stew(5, 1000)
        v.drop(BENCH)
        self.assertEqual([c for c in v.calls if c[0] == 0x42FB20], [(0x42FB20, (SLOT, 6))])

    def test_the_game_s_own_callbacks_are_unchanged(self):
        # "Starting to prepare a stew" (callback 44) and an id the game does not know, with and without
        runs = []
        for with_dll in (False, True):
            v = Village(with_dll=with_dll)
            v.p.call(DISPATCH, [SLOT, 0x2C], ecx=v.mgr)
            v.p.call(DISPATCH, [SLOT, 0x47], ecx=v.mgr)
            runs.append((v.calls[:], v.pot()))
        self.assertEqual(runs[0], runs[1])
        self.assertEqual(runs[1][1][0x0C], 1)                          # the stew started (+0x30448)

    def test_with_every_other_patch_in_every_mode(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                exe = _rendered(tuple(_others()), mode)
                v = Village(exe)
                self.assertEqual(v.installed, 1)
                v.stew(7, 5000)
                v.drop(DOOR)
                v.finish()
                self.assertEqual(v.p.u32(v.state + STEW), 0)
                # Hospital Recovery Heals' callback 126 (through the dispatcher entry's cave), with and without
                runs = []
                for with_dll in (False, True):
                    w = Village(exe, with_dll=with_dll)
                    w.p.put32(w.record() + 0x52C, 40)
                    w.p.call(DISPATCH, [SLOT, 0x7E], ecx=w.mgr)
                    runs.append(w.p.u32(w.record() + 0x52C))
                self.assertEqual(runs, [41, 41])


@NEEDS
class AllOrNoneTests(unittest.TestCase):
    def test_a_site_that_is_not_stock_installs_nothing(self):
        for va, stock in DETOURS + CHECKED:
            with self.subTest(changed=hex(va)):
                data = bytearray(EXE.read_bytes())
                pe = pefile.PE(data=bytes(data), fast_load=True)
                data[pe.get_offset_from_rva(va - 0x400000)] ^= 0xFF
                v = Village(bytes(data))
                self.assertEqual(v.installed, 0)
                for other_va, other_stock in DETOURS:
                    if other_va != va:
                        self.assertEqual(v.p.read(other_va, len(other_stock) // 2).hex().upper(), other_stock)

    def test_another_game_installs_nothing(self):
        for game in (1, 3, 4, 5):
            v = Village(with_dll=False)
            v.p.export("VvfpStartup", game, 0)
            self.assertEqual(v.p.export("VvfpVv2EmptyStewInstalled"), 0)
            for va, stock in DETOURS:
                self.assertEqual(v.p.read(va, len(stock) // 2).hex().upper(), stock)


# ---------------------------------------------------------------------------------------------------------------
# The row, the defaults and the documents.
# ---------------------------------------------------------------------------------------------------------------
class RowTests(unittest.TestCase):
    def test_row_and_defaults(self):
        from vv_fun_patcher_gui import (
            DEFAULT_OFF_FUN_PATCH_IDS, OWNERS_DEFAULT_OFF_FUN_PATCH_IDS, default_fun_patch_selection,
            owners_default_fun_patch_selection)
        rows = {p.id: p.raw for p in vfp.load_fun_patches()}
        self.assertIn(ROW, {p.id for p in vfp.load_public_fun_patches()})
        row = rows[ROW]
        self.assertEqual(row["name"], NAME)
        self.assertEqual(row["game_id"], "vv2")
        self.assertIn("**Needs no other patch.**", row["description"])
        # new content with no cost and no cheat: on by default, and in Owner's Defaults
        self.assertNotIn(ROW, DEFAULT_OFF_FUN_PATCH_IDS)
        self.assertNotIn(ROW, OWNERS_DEFAULT_OFF_FUN_PATCH_IDS)
        self.assertTrue(default_fun_patch_selection(ROW))
        self.assertTrue(owners_default_fun_patch_selection(ROW))

    def test_the_row_ships_the_companion_and_no_executable_byte(self):
        row = {p.id: p.raw for p in vfp.load_fun_patches()}[ROW]
        self.assertEqual(row["patches"], [])
        self.assertEqual([(c["source"], c["destination"]) for c in row["companion_files"]],
                         [("assets/vv2_empty_stew/" + DLL_NAME, DLL_NAME)])
        if DLL.is_file():
            self.assertEqual(row["companion_files"][0]["sha256"], hashlib.sha256(DLL.read_bytes()).hexdigest().upper())
        self.assertIn(DLL_NAME, row["description"])
        self.assertEqual([(int(d["va"], 16), d["stock_bytes"]) for d in row["runtime_detours"]], list(DETOURS))
        for d in row["runtime_detours"]:
            self.assertEqual(len(d["written_bytes"]), len(d["stock_bytes"]))
        self.assertIn(DLL_NAME, vfp.STARTUP_LOADER_COMPANIONS_2)

    def test_the_detours_are_the_ones_the_companion_holds(self):
        import re
        source = (ROOT / "native" / "vvfp_vv2_empty_stew" / "vvfp_vv2_empty_stew.c").read_text(encoding="utf-8")
        # the byte arrays, read without comments and line breaks
        flat = re.sub(r"\s+", " ", re.sub(r"/\*.*?\*/", " ", source, flags=re.S))
        for va, stock in DETOURS + CHECKED:
            self.assertIn(f"0x{va:X}", source)
            self.assertIn(", ".join(f"0x{b:02X}" for b in bytes.fromhex(stock)), flat, hex(va))

    @unittest.skipUnless(EXE.is_file(), "the stock executable is missing")
    def test_no_other_row_claims_a_site(self):
        pe = pefile.PE(str(EXE), fast_load=True)
        ranges = [(va, va + len(stock) // 2) for va, stock in DETOURS + CHECKED]
        # the shared support patches some rows bring (the dispatcher's entry cave of Teaching Children Grants Skill
        # and Hospital Recovery Heals, 0x461B10..0x461B14, sits just before the range test the companion checks)
        builds = __import__("json").loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
        for support in builds["fun_patch_support"]:
            if support["game_id"] != "vv2":
                continue
            for patch in support["patches"]:
                rva = pe.get_rva_from_offset(int(patch["offset"], 16))
                if rva is None:
                    continue
                va, n = 0x400000 + rva, len(patch["before"]) // 2
                for start, end in ranges:
                    self.assertFalse(va < end and start < va + n, (support["when_any"], hex(va), hex(start)))
        for p in vfp._load_fun_patch_records():
            if p.raw.get("game_id") != "vv2" or p.id == ROW:
                continue
            claims = []
            for patch in p.raw.get("patches", []) or []:
                rva = pe.get_rva_from_offset(int(patch["offset"], 16))
                if rva is not None:
                    claims.append((0x400000 + rva, len(patch.get("before", "")) // 2 or 1))
            for d in p.raw.get("runtime_detours", []) or []:
                claims.append((int(str(d["va"]), 0), len(bytes.fromhex(d["stock_bytes"]))))
            for va, n in claims:
                for start, end in ranges:
                    self.assertFalse(va < end and start < va + n, (p.id, hex(va), hex(start)))

    @unittest.skipUnless(EXE.is_file(), "the stock executable is missing")
    def test_stock_bytes(self):
        data = EXE.read_bytes()
        row = {p.id: p.raw for p in vfp.load_fun_patches()}[ROW]
        for d in row["runtime_detours"]:
            self.assertEqual(_va_bytes(data, int(d["va"], 16), len(d["stock_bytes"]) // 2), d["stock_bytes"])
        for va, stock in CHECKED:
            self.assertEqual(_va_bytes(data, va, len(stock) // 2), stock)

    def test_readme_guide_mechanics_and_log(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"`{ROW}`", readme)
        guides = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        self.assertIn(ROW, {i for e in guides["patches"] for i in e["ids"]})
        log = (ROOT / "docs" / "transparency-log.md").read_text(encoding="utf-8")
        self.assertIn(f"(`{ROW}`)", log)
        import vv_game_mechanics_items_vv2 as items2
        import vv_game_mechanics_vv2 as gm2
        self.assertEqual(gm2.EMPTY_STEW, ROW)
        self.assertIn("science hut's doorway", gm2.EMPTY_STEW_EFFECT)
        self.assertTrue(any(NAME in line for e in items2.ITEMS if e.name == "Stews" for line, _ok in e.lines))
        strings = json.loads((ROOT / "data" / "translations" / "patcher_strings.json").read_text(encoding="utf-8"))
        stem = "vvfp.vv2_empty_stew/vvfp_vv2_empty_stew.EMPTYING_EN.s0"
        row = next(r for r in strings["strings"] if r["stem"] == stem)
        self.assertEqual((row["english"], row["games"], row.get("route")), ("Emptying the pot", ["vv2"], "key"))


if __name__ == "__main__":
    unittest.main()
