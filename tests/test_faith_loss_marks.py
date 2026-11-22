"""Faith Loss is Doubled/Gains Halved: believers in a crisis are decided once per cause per crisis (New Believers).

The owner (2026-11-08): "villagers should preferentially die if their faith decrease-turn heathen is due to starvation
or disease", then: decided once per villager, not on every roll (a roll each age unit would still convert nearly
everyone over a long famine), 1 in 10 become Heathens.  The owner (2026-11-20, after a village of 5 to 7 believers
lost five to the Heathens and none to death): once per villager PER CAUSE per crisis -- starvation (food under 10),
hunger (food 10 to 250), sickness, and too few believers (fewer than 12) now too -- each crisis ending on its own
(food above 250; cured; 12 or more believers).  The owner (2026-11-22): each cause its own odds -- starvation 1 in 20,
sickness 1 in 25, hunger and too few believers 1 in 50 (1 in 10 for each before).

"VVFP Faith Loss.dll" (the shipped DLL) runs in the emulator beside New Believers' executable rendered with the row,
with the drift 0x468040's own code: the game routines it asks are stubbed, rand gives a seeded random stream, and
the marks file lives in an emulated file system, so a "reload" is a new process reading the same file.  Villagers
sit in the game's own villager table (the stock one, and 256 Villagers' moved one) so the companion's identities
and its "living believers only" rule see them where the game keeps them.
"""
from __future__ import annotations

import random
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402

try:
    import pefile  # noqa: F401
    from unicorn import UC_HOOK_CODE
    from story_emulator import API_STUBS, Process
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

DLL = ROOT / "assets" / "faith_loss" / "VVFP Faith Loss.dll"
STOCK = ROOT / "inputs" / "vv5-stock-copy" / "Virtual Villagers - New Believers.exe"
FAITH_LOSS = "vv5_faith_loss_doubled_gains_halved"
POP256 = "vv5_population_256"

DRIFT, RAND, PROJECT_DONE, STATUE_STAGE, TECH, BELIEVERS = 0x468040, 0x403660, 0x43AE80, 0x4271C0, 0x423600, 0x4713F0
FAITH_ADD, MANAGER_OF, TO_HEATHEN, TO_BELIEVER, FOOD = 0x468020, 0x425950, 0x4669E0, 0x4668B0, 0x51D34C
SAVE_MANAGER, SLOT_FIELD = 0x4DACE0, 0x17D80
STRIDE, FIRST = 0x2F44, 0x48
NAME, HEALTH, SICK, PRESENT, HEATHEN, FAITH, LIKES = 0x1B9C, 0x1C40, 0x1C48, 0x1CD4, 0x1CEC, 0x1CF0, 0x1F5C
AGE, DISLIKES = 0x1B8C, 0x1F68
STARVATION, HUNGER, SICKNESS, TOO_FEW = 1, 2, 4, 8          # a mark's causes
# Each cause's decision is rand(N) < 1 (the owner, 2026-11-22: starvation 1 in 20, sickness 1 in 25, hunger and too
# few believers 1 in 50; the cave's own rule without the companion is rand(10)).
ODDS = {STARVATION: 20, SICKNESS: 25, HUNGER: 50, TOO_FEW: 50}
DECIDE_ODDS = (10, 20, 25, 50)

_renders: dict = {}


def rendered(ids: tuple, mode: str = "collection_progression") -> bytes:
    if not STOCK.is_file():
        raise unittest.SkipTest("stock New Believers is not in inputs/")
    key = (ids, mode)
    if key not in _renders:
        build = next(b for b in patcher.load_builds() if b.id == "vv5")
        resolved = patcher.resolve_fun_patch_ids(list(ids), game_id="vv5")
        _renders[key] = bytes(patcher.render_patched_bytes(STOCK, build, mode, resolved)[0])
    return _renders[key]


class Files:
    """The Windows file calls the companion makes (sidecar_io.h), over a dict of path -> bytes."""

    def __init__(self, docs: bytes = b"C:\\Docs", exe: bytes | None = None):
        self.files: dict[str, bytes] = {}
        self.handles: dict[int, list] = {}
        self.next = 0x100
        self.error = 0
        self.docs, self.exe = docs, exe

    def install(self, p: "Process") -> None:
        h = p.api_handlers
        if self.exe is not None:
            p.exe_path = self.exe

        def special(q):
            q.write(q.arg(1), self.docs + b"\0")
            return 1, 16
        h["SHGetSpecialFolderPathA"] = special
        h["CreateDirectoryA"] = lambda q: (1, 8)
        h["GetLastError"] = lambda q: (self.error, 0)

        def create(q):
            path, disposition = q.cstring(q.arg(0)).lower(), q.arg(4)
            if disposition == 3:                       # OPEN_EXISTING
                if path not in self.files:
                    self.error = 2
                    return 0xFFFFFFFF, 28
                data, writing = bytearray(self.files[path]), False
            else:
                data, writing = bytearray(), True
            self.next += 4
            self.handles[self.next] = [path, data, 0, writing]
            return self.next, 28
        h["CreateFileA"] = create

        def read(q):
            entry = self.handles[q.arg(0)]
            chunk = bytes(entry[1][entry[2]:entry[2] + q.arg(2)])
            entry[2] += len(chunk)
            q.write(q.arg(1), chunk)
            q.put32(q.arg(3), len(chunk))
            return 1, 20
        h["ReadFile"] = read

        def write(q):
            entry = self.handles[q.arg(0)]
            entry[1] += q.read(q.arg(1), q.arg(2))
            q.put32(q.arg(3), q.arg(2))
            return 1, 20
        h["WriteFile"] = write
        h["FlushFileBuffers"] = lambda q: (1, 4)

        def close(q):
            entry = self.handles.pop(q.arg(0))
            if entry[3]:
                self.files[entry[0]] = bytes(entry[1])
            return 1, 4
        h["CloseHandle"] = close

        def move(q):
            self.files[q.cstring(q.arg(1)).lower()] = self.files.pop(q.cstring(q.arg(0)).lower())
            return 1, 12
        h["MoveFileExA"] = move

        def delete(q):
            self.files.pop(q.cstring(q.arg(0)).lower(), None)
            return 1, 4
        h["DeleteFileA"] = delete

    def entries(self) -> list[tuple]:
        (data,) = [v for k, v in self.files.items() if k.endswith("believers kept - save 1.dat")]
        magic, version, game, slot, count = struct.unpack_from("<5I", data)
        self.assertion = (magic, version, game, slot)
        assert len(data) == 20 + 24 * count, len(data)
        return [struct.unpack_from("<6I", data, 20 + 24 * i) for i in range(count)]

    def marks(self) -> list[int]:
        return [e[0] for e in self.entries()]

    def causes(self) -> list[int]:
        return [e[5] for e in self.entries()]


class Game:
    """The rendered executable and the companion, a village of `n` believers in the game's own villager table, the
    save slot, and the routines the drift asks stubbed.  rand is a seeded random stream (or the next `forced`)."""

    def __init__(self, exe: bytes, files: Files, n: int = 20, *, seed: int = 1, slot: int = 1, dll: bool = True):
        self.p = p = Process(exe, DLL if dll else None)
        # Only the stubs and the API stubs are hooked (every instruction through Python is too slow for a famine).
        p.mu.hook_del(p.code_hook)
        files.install(p)
        self.rng = random.Random(seed)
        self.forced: list[int] = []
        self.decisions = 0
        self.decided_with: list[int] = []
        self.food, self.believers = 100, 20
        manager = p.alloc(0x20000)
        p.put32(SAVE_MANAGER, manager)
        p.put32(manager + SLOT_FIELD, slot)
        game = p.alloc(0x20000)
        p.write(game + 0x17E39, b"\x01")
        self.table = p.u32(0x494051) + FIRST          # the villager manager the executable names (150 or 256)

        def rand(q):
            n = q.arg(0)
            if n in DECIDE_ODDS:                       # a decision (every other roll is rand(100))
                self.decisions += 1
                self.decided_with.append(n)
            value = self.forced.pop(0) if self.forced else self.rng.randrange(32768)
            return value % n, 0

        def to_heathen(q):
            q.write(q.reg("ecx") + HEATHEN, b"\x01")
            return 0, 0
        for va, fn in ((RAND, rand), (PROJECT_DONE, lambda q: (0, 4)), (STATUE_STAGE, lambda q: (0, 0)),
                       (TECH, lambda q: (0, 4)), (BELIEVERS, lambda q: (self.believers, 0)),
                       (MANAGER_OF, lambda q: (game, 0)), (TO_HEATHEN, to_heathen),
                       (TO_BELIEVER, lambda q: (0, 0))):
            p.stub(va, fn)
            p.mu.hook_add(UC_HOOK_CODE, p._on_code, begin=va, end=va)
        p.mu.hook_add(UC_HOOK_CODE, p._on_code, begin=API_STUBS, end=API_STUBS + 0xFFFF)
        if dll:
            p.export("VvfpStartup", 5, 0)
        self.records = []
        for i in range(n):
            rec = self.table + i * STRIDE
            p.write(rec + NAME, f"Villager {i}".encode() + b"\0")
            p.put32(rec + LIKES, i)
            p.put32(rec + HEALTH, 50)
            p.write(rec + PRESENT, b"\x01")
            p.put32(rec + FAITH, 2)
            p.put32(rec + AGE, 400)
            self.records.append(rec)

    def drift(self, rec: int, *, sick: int = 0) -> None:
        p = self.p
        p.put32(FOOD, self.food)
        p.write(rec + SICK, bytes([sick]))
        p.call(DRIFT, ecx=rec)

    def unit(self, *, sick: int = 0) -> None:
        """One age unit: the drift for every living believer, as the life tick runs it."""
        for rec in self.records:
            if not self.heathen(rec) and self.p.u32(rec + HEALTH) > 0:
                self.drift(rec, sick=sick)

    def heathen(self, rec: int) -> bool:
        return self.p.read(rec + HEATHEN, 1) != b"\0"

    def faith(self, rec: int) -> int:
        return struct.unpack("<i", self.p.read(rec + FAITH, 4))[0]

    def marked(self) -> int:
        return self.p.export("VvfpFaithLossMarked")


def skip_without_emulator(cls):
    return unittest.skipUnless(HAVE_EMULATOR, "unicorn/pefile not installed")(
        unittest.skipUnless(DLL.is_file(), "the companion is not built")(cls))


@skip_without_emulator
class OnceACrisis(unittest.TestCase):
    def test_installs_its_one_call_only_with_the_rows_cave(self):
        g = Game(rendered((FAITH_LOSS,)), Files(), n=1)
        self.assertEqual(g.p.export("VvfpFaithLossInstalled"), 1)
        call = g.p.read(0x494F14, 5)
        target = (0x494F14 + 5 + struct.unpack("<i", call[1:])[0]) & 0xFFFFFFFF
        self.assertTrue(g.p.dll_base <= target < g.p.dll_base + g.p.dll_size)
        bare = Process(rendered(()), DLL)
        bare.export("VvfpStartup", 5, 0)
        self.assertEqual(bare.export("VvfpFaithLossInstalled"), 0, "without the row's cave nothing is written")
        self.assertEqual(bare.read(0x494F14, 5), bytes(5))

    def test_a_long_famine_keeps_nearly_every_believer(self):
        """150 believers through 80 age units of food 100 (the food roll every unit at 20%): each is decided once, the
        first time hunger would take their last Faith; 1 in 50 becomes a Heathen (the owner, 2026-11-22), the rest
        stay believers at Faith 1 or more for the whole famine, however many more falls come."""
        g = Game(rendered((FAITH_LOSS,)), Files(), n=150, seed=7)
        for _ in range(80):
            g.unit()
        heathens = sum(g.heathen(r) for r in g.records)
        self.assertEqual(g.decisions, 150, "every believer reached the decision, once")
        self.assertEqual(set(g.decided_with), {ODDS[HUNGER]})
        self.assertLessEqual(heathens, 10, "about 3 of 150 expected")
        for rec in g.records:
            if not g.heathen(rec):
                self.assertGreaterEqual(g.faith(rec), 1, "never below 1 (a gain roll may still lift it)")
        self.assertEqual(g.marked(), 150 - heathens)

    def test_without_the_companion_every_fall_is_rolled_and_a_famine_converts_most(self):
        """The cave's own rule (the companion absent) rolls 1 in 10 at every such fall: over a long famine most
        believers end up Heathens -- what the per-villager mark prevents."""
        g = Game(rendered((FAITH_LOSS,)), Files(), n=60, seed=7, dll=False)
        for _ in range(80):
            g.unit()
        self.assertGreater(sum(g.heathen(r) for r in g.records), 30)

    def test_each_crisis_ends_on_its_own_and_the_next_is_decided_afresh(self):
        files = Files()
        g = Game(rendered((FAITH_LOSS,)), files, n=1)
        (rec,) = g.records
        g.p.put32(rec + FAITH, 1)
        g.forced = [0, 99, 5]                          # the hunger roll hits, the believers' roll misses, 5: stays
        g.drift(rec)
        self.assertEqual((g.faith(rec), g.heathen(rec), g.marked()), (1, False, 1))
        g.forced = [0, 99, 0]                          # marked for hunger: no decision, still Faith 1
        g.drift(rec)
        self.assertEqual((g.faith(rec), g.heathen(rec), g.decisions), (1, False, 1))
        g.forced = [99, 0, 99, 5]                      # hungry and now sick: sickness is decided on its own
        g.drift(rec, sick=1)
        self.assertEqual((g.faith(rec), g.decisions, files.causes()), (1, 2, [HUNGER | SICKNESS]))
        g.food = 251
        g.forced = [99, 99]
        g.drift(rec, sick=1)                           # fed but sick: hunger is over, sickness goes on
        self.assertEqual((g.marked(), files.causes()), (1, [SICKNESS]))
        g.forced = [99]
        g.drift(rec)                                   # cured: the sickness mark clears too
        self.assertEqual(g.marked(), 0)
        g.food = 100
        g.p.put32(rec + FAITH, 1)
        g.forced = [0, 99, 0]                          # a new hunger: decided afresh, 0: a Heathen
        g.drift(rec)
        self.assertEqual(g.decisions, 3)
        self.assertTrue(g.heathen(rec))

    def test_each_cause_is_decided_once_per_crisis_too_few_believers_included(self):
        """The owner (2026-11-20): one roll per villager per cause per crisis; too few believers goes through the
        same once-a-crisis decision (its own odds), and ends when the village has 12 or more believers again."""
        files = Files()
        g = Game(rendered((FAITH_LOSS,)), files, n=3)
        a, b, c = g.records
        g.food = 1000
        g.p.put32(a + FAITH, 1)
        g.forced = [0, 99, 5]                          # sickness takes the last Faith: decided, stays
        g.drift(a, sick=1)
        g.forced = [0, 99, 0]                          # again: held, no roll
        g.drift(a, sick=1)
        self.assertEqual((g.faith(a), g.heathen(a), g.decisions), (1, False, 1))
        g.believers = 3
        g.forced = [99, 0, 5]                          # too few believers takes the last Faith: its own roll
        g.drift(a, sick=1)
        self.assertEqual((g.faith(a), g.decisions, files.causes()), (1, 2, [SICKNESS | TOO_FEW]))
        g.forced = [99, 0, 0]
        g.drift(a, sick=1)                             # held, no roll
        g.food = 5
        g.forced = [0, 99, 99, 5]                      # starvation: its own roll
        g.drift(a, sick=1)
        g.food = 100
        g.forced = [0, 99, 99, 5]                      # hunger: its own roll
        g.drift(a, sick=1)
        self.assertEqual((g.faith(a), g.decisions), (1, 4))
        self.assertEqual(files.causes(), [STARVATION | HUNGER | SICKNESS | TOO_FEW])
        g.food = 5
        g.forced = [0, 0, 0, 0]                        # every cause at once: all held
        g.drift(a, sick=1)
        self.assertEqual((g.faith(a), g.heathen(a), g.decisions), (1, False, 4))
        g.believers = 12
        g.forced = [0, 0, 99, 0]
        g.drift(a, sick=1)                             # 12 believers again: that crisis is over
        self.assertEqual((g.decisions, files.causes()), (4, [STARVATION | HUNGER | SICKNESS]))
        g.believers = 3
        g.food = 1000
        g.forced = [99, 0, 0]                          # a new too-few crisis: decided afresh, 0: a Heathen
        g.drift(a, sick=1)
        self.assertEqual(g.decisions, 5)
        self.assertTrue(g.heathen(a))
        # Too few believers alone, never decided: 1 in 50 a Heathen, else held.
        g.p.put32(b + FAITH, 1)
        g.forced = [0, 0]
        g.drift(b)
        self.assertTrue(g.heathen(b))
        # Two losses in one drift at Faith 2: the hunger loss is made, too few believers takes the last Faith and is
        # the one decided.
        g.food = 100
        g.p.put32(c + FAITH, 2)
        g.forced = [0, 0, 5]
        g.drift(c)
        self.assertEqual((g.faith(c), g.heathen(c), g.decisions), (1, False, 7))
        self.assertIn(TOO_FEW, files.causes())

    def test_a_small_starving_village_mostly_stays_and_dies(self):
        """The owner's village (5 to 7 believers, hungry): 120 believers counted as 8 by the game through 300 age
        units of food 100.  Each is decided at most twice (hunger, too few believers, each 1 in 50: the owner,
        2026-11-22), so about 1 - 0.98^2 = 4% become Heathens; before the once-a-crisis rule, a believer held at Faith
        1 left on the first too-few roll (8% each age unit here), so nearly every one did."""
        g = Game(rendered((FAITH_LOSS,)), Files(), n=120, seed=11)
        g.believers = 8
        for rec in g.records:
            g.p.put32(rec + FAITH, 30)
        for _ in range(300):
            g.unit()
        heathens = sum(g.heathen(r) for r in g.records)
        self.assertLessEqual(g.decisions, 2 * 120)
        self.assertGreaterEqual(g.decisions, 120)
        self.assertEqual(set(g.decided_with), {ODDS[HUNGER], ODDS[TOO_FEW]})
        self.assertLessEqual(heathens, 15, "about 5 of 120 expected")
        for rec in g.records:
            if not g.heathen(rec):
                self.assertGreaterEqual(g.faith(rec), 1)

    def test_a_version_1_file_is_read_as_marked_for_food_and_sickness(self):
        files = Files()
        exe = rendered((FAITH_LOSS,))
        g = Game(exe, files, n=1)
        rec = g.records[0]
        g.p.put32(rec + FAITH, 1)
        g.forced = [0, 99, 5]
        g.drift(rec)
        (entry,) = files.entries()
        key = next(k for k in files.files if k.endswith("believers kept - save 1.dat"))
        files.files[key] = struct.pack("<5I", 0x314B4656, 1, 5, 1, 1) + struct.pack("<5I", *entry[:5])
        again = Game(exe, files, n=1)
        r = again.records[0]
        again.food = 5
        again.p.put32(r + FAITH, 1)
        again.forced = [0, 99, 0]
        again.drift(r, sick=1)                         # starvation and sickness: held, no roll
        self.assertEqual((again.heathen(r), again.decisions), (False, 0))
        again.believers = 3
        again.forced = [99, 99, 99, 0, 5]              # too few believers was never decided: its own roll
        again.drift(r, sick=1)
        self.assertEqual((again.decisions, files.causes()), (1, [STARVATION | HUNGER | SICKNESS | TOO_FEW]))
        self.assertEqual(files.assertion[1], 2, "written as version 2")

    def test_the_marks_survive_a_reload_and_keep_only_living_believers(self):
        files = Files()
        exe = rendered((FAITH_LOSS,))
        g = Game(exe, files, n=3)
        for rec in g.records:
            g.p.put32(rec + FAITH, 1)
            g.forced = [0, 99, 5]
            g.drift(rec)
        self.assertEqual(g.marked(), 3)
        self.assertEqual(len(files.marks()), 3)
        self.assertEqual(files.assertion, (0x314B4656, 2, 5, 1))
        self.assertEqual(files.causes(), [HUNGER] * 3)
        again = Game(exe, files, n=3)                  # the game quit and loaded again: the same village
        for rec in again.records:
            again.p.put32(rec + FAITH, 1)
            again.forced = [0, 99, 0]
            again.drift(rec)
        self.assertEqual(again.decisions, 0, "read before the first drift: no one is decided again")
        self.assertFalse(any(again.heathen(r) for r in again.records))
        again.p.put32(again.records[0] + HEALTH, 0)    # one has died: the next write keeps the living
        again.food = 1000
        again.forced = [99, 99, 99]
        again.drift(again.records[1])                  # fed and well: this one's mark clears, the file is written
        self.assertEqual(len(files.marks()), 1)

    def test_the_mark_follows_a_rename_or_new_likes_and_dislikes(self):
        """Codex (#732): the mark is not lost when the player renames the villager or the Custom Island Event (or an
        island event) changes their likes or dislikes -- no second roll -- and a write made meanwhile for somebody
        else's mark never prunes it; through a reload too."""
        files = Files()
        exe = rendered((FAITH_LOSS,))
        g = Game(exe, files, n=2)
        a, b = g.records
        g.p.put32(a + FAITH, 1)
        g.forced = [0, 99, 5]
        g.drift(a)                                          # a is marked
        g.p.write(a + NAME, b"Renamed Villager\0")          # renamed
        g.p.put32(b + FAITH, 1)
        g.forced = [0, 99, 5]
        g.drift(b)                                          # b is marked: a write, a's mark not pruned
        self.assertEqual(g.marked(), 2)
        self.assertEqual(len(files.marks()), 2)
        g.p.put32(a + LIKES, 77)                            # new likes too (a CIE edit)
        g.p.put32(a + AGE, 401)
        g.forced = [0, 99, 0]                               # a roll would make a Heathen: none is made
        g.drift(a)
        self.assertEqual((g.faith(a), g.heathen(a), g.decisions), (1, False, 2))
        again = Game(exe, files, n=2)                       # reloaded: the file has a's new identity
        again.p.write(again.records[0] + NAME, b"Renamed Villager\0")
        again.p.put32(again.records[0] + LIKES, 77)
        again.p.put32(again.records[0] + FAITH, 1)
        again.forced = [0, 99, 0]
        again.drift(again.records[0])
        self.assertEqual((again.heathen(again.records[0]), again.decisions), (False, 0))

    def test_a_newborn_in_a_marked_villagers_record_inherits_nothing(self):
        g = Game(rendered((FAITH_LOSS,)), Files(), n=1)
        (rec,) = g.records
        g.p.put32(rec + FAITH, 1)
        g.forced = [0, 99, 5]
        g.drift(rec)
        self.assertEqual(g.marked(), 1)
        # The marked villager died and a baby was put in the record: another name, younger.
        g.p.write(rec + NAME, b"Baby\0")
        g.p.put32(rec + LIKES, 5)
        g.p.put32(rec + AGE, 0)
        g.p.put32(rec + FAITH, 1)
        g.forced = [0, 99, 0]
        g.drift(rec)
        self.assertEqual(g.decisions, 2, "decided on its own")
        self.assertTrue(g.heathen(rec))

    def test_start_over_forgets_the_marks(self):
        """Codex (#732): Start Over in the same slot (the file deleted with the save's folder, the game not
        restarted) must not leave the old village's marks in memory, where a new founder in a marked record -- same
        sex and likes, another name, not younger -- could take the protection.  Forgotten by the reset VVFP Story
        Upgrades.dll forwards (VvfpFaithLossVillageReset), or, without it, once the file is seen gone."""
        for signal in ("reset export", "file gone"):
            with self.subTest(signal=signal):
                files = Files()
                g = Game(rendered((FAITH_LOSS,)), files, n=1)
                (rec,) = g.records
                g.p.put32(rec + FAITH, 1)
                g.forced = [0, 99, 5]
                g.drift(rec)
                self.assertEqual((g.marked(), len(files.files)), (1, 1))
                files.files.clear()                                 # Start Over deletes the save's folder
                if signal == "reset export":
                    g.p.export("VvfpFaithLossVillageReset", 5)
                else:
                    g.p.api_handlers["GetFileAttributesA"] = lambda q: (
                        0xFFFFFFFF if q.cstring(q.arg(0)).lower() not in files.files else 0x80, 4)
                    files.error = 2
                    g.p.tick = 10000
                g.p.write(rec + NAME, b"New Founder\0")             # same sex and likes, another name, older
                g.p.put32(rec + AGE, 600)
                g.p.put32(rec + FAITH, 1)
                g.forced = [0, 99, 0]
                g.drift(rec)
                self.assertEqual(g.decisions, 2, "the founder is decided on their own")
                self.assertTrue(g.heathen(rec))
                self.assertEqual(g.marked(), 0)

    def test_a_locked_marks_file_is_read_again_once_the_lock_clears(self):
        """Codex (#732): a marks file locked (or unreadable) at the village's first drift is retried on the gate's
        throttle, not taken as loaded and empty: the marked believers keep their protection, and a mark made while
        the file was locked reaches it once the lock clears."""
        files = Files()
        exe = rendered((FAITH_LOSS,))
        g = Game(exe, files, n=2)
        a, b = g.records
        g.p.put32(a + FAITH, 1)
        g.forced = [0, 99, 5]
        g.drift(a)                                          # a is marked and written
        self.assertEqual(len(files.marks()), 1)
        again = Game(exe, files, n=2)                       # reloaded while something holds the file
        create = again.p.api_handlers["CreateFileA"]
        locked = {"on": True}

        def maybe_locked(q):
            if locked["on"] and q.cstring(q.arg(0)).lower().endswith("believers kept - save 1.dat"):
                files.error = 32                            # ERROR_SHARING_VIOLATION
                return 0xFFFFFFFF, 28
            return create(q)
        again.p.api_handlers["CreateFileA"] = maybe_locked
        again.p.tick = 1000
        again.p.put32(again.records[1] + FAITH, 1)
        again.forced = [0, 99, 5]
        again.drift(again.records[1])                       # b is decided and marked while the file is locked
        self.assertEqual(again.decisions, 1)
        locked["on"] = False
        again.p.tick = 1000 + 2000                          # the gate's retry window has passed
        again.p.put32(again.records[0] + FAITH, 1)
        again.forced = [0, 99, 0]
        again.drift(again.records[0])                       # a: the file is read now, so a is still protected
        self.assertEqual((again.heathen(again.records[0]), again.decisions), (False, 1))
        self.assertEqual(sorted(files.marks()), sorted(set(files.marks())))
        self.assertEqual(len(files.marks()), 2, "b's mark, made while locked, reached the file")

    def test_a_full_table_drops_a_dead_villagers_mark_before_refusing_a_new_one(self):
        """Codex (#732): with every place taken (256 Villagers), a marked believer who died must not keep the table
        full, or the next believer in a crisis would be rolled again at every fall."""
        files = Files()
        g = Game(rendered((FAITH_LOSS, POP256)), files, n=256)
        for rec in g.records:
            g.p.put32(rec + FAITH, 1)
            g.forced = [0, 99, 5]
            g.drift(rec)
        self.assertEqual(g.marked(), 256)
        dead = g.records[0]
        g.p.put32(dead + HEALTH, 0)                         # died in the crisis
        g.p.write(dead + NAME, b"Newborn\0")                # a baby in the record
        g.p.put32(dead + LIKES, 999)
        g.p.put32(dead + AGE, 0)
        g.p.put32(dead + HEALTH, 50)
        g.p.put32(dead + FAITH, 1)
        g.forced = [0, 99, 5]
        g.drift(dead)                                       # decided: stays, and is marked
        before = g.decisions
        g.p.put32(dead + FAITH, 1)
        g.forced = [0, 99, 0]
        g.drift(dead)                                       # no second roll
        self.assertEqual((g.decisions, g.heathen(dead)), (before, False))

    def test_the_owners_long_256_folder_keeps_the_marks_through_a_restart(self):
        """The owner (2026-11-22): "i had 5 convert instead of die" from sickness, in "Virtual Villagers - New
        Believers - Modded 256" under OneDrive\\Documents.  Its marks file was never written: the path check guessed
        160 characters for everything after the Documents folder and the executable's name (33 + 46 + 160 = 239,
        over MAX_PATH less the set-aside name's 27), though the real path is 165.  The marks lived only in memory,
        so every game start (and its load-time catch-up) decided every held believer again.  A sick believer
        decided once stays decided through any number of restarts; a path really too long is still refused."""
        docs = b"C:\\Users\\Owner\\OneDrive\\Documents"
        exe_name = b"Virtual Villagers - New Believers - Modded 256"
        exe = (b"C:\\Users\\Owner\\OneDrive\\Desktop\\LDW Desktop Games!! And Other Stuff\\Current Modded LDW "
               b"Games\\Modded Games\\" + exe_name + b"\\" + exe_name + b".exe")
        files = Files(docs, exe)
        build = rendered((FAITH_LOSS, POP256))
        g = Game(build, files, n=1)
        (rec,) = g.records
        g.food = 1000
        g.p.put32(rec + FAITH, 1)
        g.forced = [0, 99, 5]                          # sickness takes the last Faith: decided, stays
        g.drift(rec, sick=1)
        self.assertEqual((g.heathen(rec), g.decisions), (False, 1))
        (path,) = files.files
        self.assertEqual(path, (docs + b"\\LDW\\" + exe_name + b"\\Virtual Villagers Fun Patcher\\Save 1\\Data\\"
                                b"Faith Loss\\Believers Kept - Save 1.dat").decode().lower())
        self.assertEqual(files.causes(), [SICKNESS])
        for restart in range(5):                       # the same illness, the game quit and started again
            again = Game(build, files, n=1)
            again.food = 1000
            again.p.put32(again.records[0] + FAITH, 1)
            again.forced = [0, 99, 0]                  # a roll now would make a Heathen
            again.drift(again.records[0], sick=1)
            self.assertEqual((again.heathen(again.records[0]), again.decisions), (False, 0), restart)
        # A Documents folder long enough that the whole path would not fit: refused, nothing written, no fault.
        long_files = Files(b"C:\\" + b"D" * 100, exe)  # 235 characters: with the set-aside name, over 259
        far = Game(build, long_files, n=1)
        far.food = 1000
        far.p.put32(far.records[0] + FAITH, 1)
        far.forced = [0, 99, 5]
        far.drift(far.records[0], sick=1)
        self.assertEqual((far.heathen(far.records[0]), far.decisions, long_files.files), (False, 1, {}))

    def test_each_cause_draws_the_owners_odds(self):
        """The owner (2026-11-22): starvation 1 in 20, sickness 1 in 25, hunger 1 in 50, too few believers 1 in 50 --
        each cause's decision is rand(N) < 1 with its own N."""
        for cause, setup in ((STARVATION, dict(food=5, sick=0, believers=20, forced=[0, 99, 5])),
                             (HUNGER, dict(food=100, sick=0, believers=20, forced=[0, 99, 5])),
                             (SICKNESS, dict(food=1000, sick=1, believers=20, forced=[0, 99, 5])),
                             (TOO_FEW, dict(food=1000, sick=0, believers=3, forced=[0, 5]))):
            with self.subTest(cause=cause):
                g = Game(rendered((FAITH_LOSS,)), Files(), n=1)
                (rec,) = g.records
                g.food, g.believers, g.forced = setup["food"], setup["believers"], setup["forced"]
                g.p.put32(rec + FAITH, 1)
                g.drift(rec, sick=setup["sick"])
                self.assertEqual(g.decided_with, [ODDS[cause]])
                self.assertFalse(g.heathen(rec))
        self.assertEqual(ODDS, {STARVATION: 20, SICKNESS: 25, HUNGER: 50, TOO_FEW: 50})

    def test_it_says_which_cause_decided_a_conversion(self):
        """VVFP Faith Notice.dll's popup must name the cause that decided (VvfpFaithLossDecided), not the first loss
        roll that hit: a believer held at Faith 1 for sickness is turned only by another cause's roll."""
        g = Game(rendered((FAITH_LOSS,)), Files(), n=2)
        a, b = g.records
        g.food = 1000
        g.p.put32(a + FAITH, 1)
        g.forced = [0, 99, 5]                          # sickness decided: held
        g.drift(a, sick=1)
        self.assertEqual(g.p.export("VvfpFaithLossDecided", 5, a), 0, "held: no conversion decided")
        g.believers = 3
        g.forced = [0, 0, 0]                           # sick (held) and too few hit; too few's roll: a Heathen
        g.drift(a, sick=1)
        self.assertTrue(g.heathen(a))
        self.assertEqual(g.p.export("VvfpFaithLossDecided", 5, a), TOO_FEW)
        self.assertEqual(g.p.export("VvfpFaithLossDecided", 4, a), 0, "only New Believers")
        self.assertEqual(g.p.export("VvfpFaithLossDecided", 5, b), 0, "another record's drift was not decided")
        g.believers = 20
        g.food = 5
        g.p.put32(b + FAITH, 1)
        g.forced = [0, 99, 0]                          # starvation's roll: a Heathen
        g.drift(b)
        self.assertEqual(g.p.export("VvfpFaithLossDecided", 5, b), STARVATION)
        self.assertEqual(g.p.export("VvfpFaithLossDecided", 5, a), 0, "the last drift was b's")

    def test_another_slot_has_its_own_marks(self):
        files = Files()
        exe = rendered((FAITH_LOSS,))
        g = Game(exe, files, n=1)
        g.p.put32(g.records[0] + FAITH, 1)
        g.forced = [0, 99, 5]
        g.drift(g.records[0])
        other = Game(exe, files, n=1, slot=2)
        other.p.put32(other.records[0] + FAITH, 1)
        other.forced = [0, 99, 5]
        other.drift(other.records[0])
        self.assertEqual(other.decisions, 1, "slot 2's village is decided on its own")
        self.assertEqual(sorted(k[-12:] for k in files.files), ["- save 1.dat", "- save 2.dat"])

    def test_every_mode_and_256_villagers(self):
        for mode in ("stock", "collection_progression", "immediate_fixed"):
            for extra in ((), (POP256,), (POP256, "vv5_new_heathens_get_heathen_faith")):
                with self.subTest(mode=mode, extra=extra):
                    exe = rendered((FAITH_LOSS,) + extra, mode)
                    g = Game(exe, Files(), n=2)
                    self.assertEqual(g.p.export("VvfpFaithLossInstalled"), 1)
                    self.assertEqual(g.table, (0x800000 if extra else 0x554148) + FIRST)
                    a, b = g.records
                    for rec, roll in ((a, 5), (b, 0)):
                        g.p.put32(rec + FAITH, 1)
                        g.forced = [0, 99, roll, 3]
                        g.drift(rec)
                    self.assertEqual((g.faith(a), g.heathen(a)), (1, False))
                    self.assertTrue(g.heathen(b))
                    if "vv5_new_heathens_get_heathen_faith" in extra:
                        self.assertEqual(g.faith(b), -41, "a blue Heathen at -38 - rand(30)")
                    self.assertEqual(g.marked(), 1)


if __name__ == "__main__":
    unittest.main()
