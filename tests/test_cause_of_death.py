"""Cause of Death (all five games): the deaths log, and the cause (and A New
Home's epitaph) on A New Home's and The Lost Children's graves.

The owner: "for the games that don't write a cause of death like VV1-VV2, can
you add them please?" (in the game, the way VV3-VV5 show it), "mention it for
all 5 games in the logs, age of death too" (in the game's own age units), and
"can you also put the epitaphs for VV1-VV2 too?".

Everything here RUNS: the executable the patcher renders (the row alone, and
every public patch of the game, in all three population modes) and the TEST
build of "VVFP Cause of Death.dll" are mapped into one emulated process
(tests/story_emulator.py); the DLL's installer writes its detours into that
executable, and each test runs the game's OWN instructions through a death
site, the burial's grave loop, an unburied body's decay and the grave popup's
Draw, with only leaf routines (rand, the string table, sprintf, the text
draw) scripted.  "VVFP Parentage Export.dll"'s WriteDeathRecord is a recording
stand-in: what the log is given is checked here, the log file itself by
native/parentage_export/death_log_harness.c (tests/test_deaths_log.py).

Pinned:
* every site's stock bytes, in the stock executable and in every render;
  install is all or nothing;
* each cause, from its own site, with the age the record held, worded as the
  later games' own grave dialog words it; a change that does not kill records
  nothing;
* a death no site reported (an island event, an edit) is found by the tick
  only for a villager seen alive on an earlier frame;
* the burial carries the cause (and A New Home's epitaph) to the grave the
  game itself writes; the popup draws it one line under Age (and the epitaph
  under the name); a grave dug before, a grave whose name or age differs,
  and a decayed body show nothing extra;
* the epitaph rule (child, best skill in the later games' order with ties to
  the earlier, nobody skilled -> Respected Citizen);
* VV3-VV5: both health arbiters, each cause id, alive->dead only, Reanimate's
  stand-in excluded, and the arbiters' own results unchanged.
"""
from __future__ import annotations

import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from story_emulator import Process  # noqa: E402

TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Cause of Death.test.dll"
SHIPPED_DLL = ROOT / "assets" / "cause_of_death" / "VVFP Cause of Death.dll"
TEST_BUILD_ABSENT = "test builds are not in the release source archive (tests/test_dlls)"
NAMES = {"vv1": "A New Home", "vv2": "The Lost Children", "vv3": "The Secret City",
         "vv4": "The Tree of Life", "vv5": "New Believers"}
STOCK = {g: ROOT / "research" / "stock-executables" / f"Virtual Villagers - {n}.exe"
         for g, n in NAMES.items()}
STOCK_ABSENT = "stock executables are not in the release source archive"
MODES = ("stock", "collection_progression", "immediate_fixed")

FAKE_PARENTAGE = 0x0C100000
WRITE_DEATH = 0x0C200000
SLOT_FN = 0x0C200100
DRAW_LOG = []


def manifest(game: str) -> dict:
    return json.loads((ROOT / "data" / f"{game}_cause_of_death_feature.json").read_text(encoding="utf-8"))


_RENDERS: dict = {}


def rendered(game: str, mode: str, everything: bool) -> bytes:
    key = (game, mode, everything)
    if key not in _RENDERS:
        import vv_fun_patcher as vfp
        build = next(b for b in vfp.load_builds() if b.id == game)
        if everything:
            rows = [p.id for p in vfp.load_public_fun_patches() if p.game_id == game]
        else:
            rows = [f"{game}_cause_of_death"]
        data, _ = vfp.render_patched_bytes(STOCK[game], build, mode, rows)
        _RENDERS[key] = bytes(data)
    return _RENDERS[key]


class Game:
    """One emulated game process with the test DLL installed."""

    def __init__(self, game: str, exe: bytes, slot: int = 0):
        self.game = game
        self.no = int(game[-1])
        self.p = p = Process(exe, TEST_DLL)
        self.logged: list[tuple] = []
        self.draws: list[tuple] = []
        self.slot = slot
        p.mu.mem_map(FAKE_PARENTAGE, 0x1000)
        p.mu.mem_map(WRITE_DEATH, 0x1000)
        p.api_handlers["LoadLibraryA"] = self._load_library
        p.api_handlers["GetProcAddress"] = self._get_proc
        p.api_handlers["VirtualAlloc"] = lambda proc: (proc.alloc(proc.arg(1)), 16)
        p.api_handlers["VirtualFree"] = lambda proc: (1, 12)
        p.stub(WRITE_DEATH, self._write_death)
        p.stub(SLOT_FN, lambda proc: (self.slot, 0))
        self.host = p.alloc(16)
        p.put32(self.host, 8)
        p.put32(self.host + 4, SLOT_FN)

    def _load_library(self, proc):
        name = proc.cstring(proc.arg(0))
        proc.loaded.append(name)
        return (FAKE_PARENTAGE if name.endswith("\\VVFP Parentage Export.dll") else 0), 4

    def _get_proc(self, proc):
        name = proc.cstring(proc.arg(1))
        return (WRITE_DEATH if proc.arg(0) == FAKE_PARENTAGE and name == "WriteDeathRecord" else 0), 8

    def _write_death(self, proc):
        self.logged.append((proc.arg(0), proc.arg(1), proc.arg(2), proc.cstring(proc.arg(3))))
        return 1, 16

    def install(self) -> int:
        return self.p.export("VvfpCauseInstall", self.no, self.host)

    def tick(self) -> None:
        self.p.export("VvfpCauseTick", self.no)

    def stats(self) -> dict:
        names = ("deaths", "unhooked", "burials", "graves_set", "draws", "logged", "published")
        values = struct.unpack("<7i", self.p.read(self.p.exports["VvfpCauseStats"], 28))
        return dict(zip(names, values))

    def force_roll(self, value: int) -> None:
        self.p.put32(self.p.exports["VvfpCauseRollTest"], value & 0xFFFFFFFF)


# ---- A New Home -------------------------------------------------------------
V1 = dict(array_global=0x48B614, stride=0x3D8, present=0x28, selected=0x29, health=0x344, age=0x348,
          name=0x370, skills=0x3BC, manager=0x3E010, graves=0xA31C, grave_stride=0x2C, grave_age=0x24,
          font=0x48B608)


class NewHome:
    """A New Home's villagers, manager and graves in the emulated process."""

    def __init__(self, g: Game):
        self.g = g
        p = g.p
        self.array = p.alloc(0x3E100)
        self.manager = p.alloc(0xB000)
        p.put32(V1["array_global"], self.array)
        p.put32(self.array + V1["manager"], self.manager)
        # The aging step's `this`: [esi] = manager, [esi+4] = array.
        self.step = p.alloc(16)
        p.put32(self.step, self.manager)
        p.put32(self.step + 4, self.array)

    def record(self, i: int) -> int:
        return self.array + i * V1["stride"]

    def villager(self, i: int, name: str, age: int, health: int, skills=(0, 0, 0, 0, 0)) -> int:
        """skills in storage order: Parenting, Building, Farming, Healing, Research."""
        r = self.record(i)
        p = self.g.p
        p.write(r, bytes(V1["stride"]))
        p.write(r + V1["present"], b"\x01")
        p.put32(r + V1["health"], health)
        p.put32(r + V1["age"], age)
        p.write(r + V1["name"], name.encode() + b"\0")
        for k, value in enumerate(skills):
            p.put32(r + V1["skills"] + 4 * k, value)
        return r

    def health(self, i: int) -> int:
        return struct.unpack("<i", self.g.p.read(self.record(i) + V1["health"], 4))[0]

    def grave(self, k: int) -> int:
        return self.manager + V1["graves"] + k * V1["grave_stride"]

    # The game's own instructions, from just before each site to just after.
    def old_age(self, i: int) -> None:
        p = self.g.p
        p.set_reg("ebx", self.record(i))
        p.set_reg("eax", 0)
        p.set_reg("ecx", 1)          # cmp eax, ecx; jge -- falls into the store
        p.set_reg("edi", i * V1["stride"])
        p.set_reg("esi", self.step)
        p.set_reg("esp", 0x0FF00000 - 0x2000)
        p.run(0x42EF01, 0x42EF15)

    def drain(self, start: int, stop: int, i: int) -> None:
        p = self.g.p
        p.set_reg("esi", self.step)
        p.set_reg("edi", i * V1["stride"])
        p.set_reg("esp", 0x0FF00000 - 0x2000)
        p.run(start, stop)

    def hunger(self, i: int) -> None:
        self.drain(0x42ECB4, 0x42ECC8, i)

    def no_food(self, i: int) -> None:
        self.drain(0x42ED34, 0x42ED48, i)

    def sickness(self, i: int) -> None:
        self.drain(0x42EDA0, 0x42EDB4, i)

    def injury(self, i: int, damage: int) -> None:
        """0x43A5B4: `sub [ebx], eax; mov eax, [esi+0x3E010]`."""
        p = self.g.p
        p.set_reg("ebx", self.record(i) + V1["health"])
        p.set_reg("eax", damage)
        p.set_reg("esi", self.array)
        p.set_reg("esp", 0x0FF00000 - 0x2000)
        p.run(0x43A5B4, 0x43A5BC)

    def bury(self, i: int, best_skill: int = 30) -> int:
        """The burial branch of the action runner, 0x448F2F..0x449008: the
        game's own presence/health guard, record free and grave loop.
        Returns the grave slot it wrote (or -1)."""
        p = self.g.p
        before = [p.u32(self.grave(k) + V1["grave_age"]) for k in range(50)]
        burier = p.alloc(0x400)
        p.put32(burier + 0x344 - 0x2EC, i)
        p.stub(0x4393E0, lambda proc: (0, 0))
        p.stub(0x43B520, lambda proc: (best_skill, 8))
        def sprintf(proc):
            text = proc.cstring(proc.arg(1)).encode("latin-1")
            proc.write(proc.arg(0), text + b"\0")
            return len(text), 0
        p.stub(0x44B23D, sprintf)
        p.set_reg("eax", i * V1["stride"])
        p.set_reg("edi", self.array)
        p.set_reg("esi", burier + 0x344)
        esp = 0x0FF00000 - 0x2000
        p.set_reg("esp", esp)
        p.run(0x448F2F, 0x449008)
        for k in range(50):
            if before[k] == 0 and p.u32(self.grave(k) + V1["grave_age"]) != 0:
                return k
        return -1

    def decay(self, i: int) -> None:
        p = self.g.p
        p.set_reg("edi", i * V1["stride"])
        p.set_reg("eax", self.array)
        p.set_reg("esi", self.step)
        p.set_reg("esp", 0x0FF00000 - 0x2000)
        p.run(0x42E9C3, 0x42E9C8)

    def popup(self, k: int) -> list[tuple[str, int, int]]:
        """The grave popup's own Draw (0x436440), every line it draws:
        (text, x, y - top)."""
        p = self.g.p
        draws: list[tuple[str, int, int]] = []
        top = 100
        strings = {0x93: "Here Lies ", 0x94: "Job", 0x95: "Age", 0x54: "Untrained", 0x57: "Trainee  ",
                   0x58: "Adept ", 0x59: "Master ", 0x5A: "Farmer", 0x5B: "Parent", 0x5C: "Scientist",
                   0x5D: "Builder", 0x5E: "Doctor"}
        pool = p.alloc(0x1000)
        where = {}
        for n, (key, text) in enumerate(strings.items()):
            where[key] = pool + n * 32
            p.write(pool + n * 32, text.encode() + b"\0")
        p.stub(0x408090, lambda proc: (0x0C300000, 0))
        p.stub(0x433970, lambda proc: (where[proc.arg(0)], 4))
        def sprintf(proc):
            fmt = proc.cstring(proc.arg(1))
            args = [proc.arg(2 + n) for n in range(4)]
            if fmt == "%s %i":
                text = proc.cstring(args[0]) + " " + str(struct.unpack("<i", struct.pack("<I", args[1]))[0])
            else:
                text = fmt.replace("%%", "%")
            proc.write(proc.arg(0), text.encode("latin-1") + b"\0")
            return len(text), 0
        p.stub(0x44B23D, sprintf)
        def draw(proc):
            draws.append((proc.cstring(proc.arg(0)), proc.arg(1), proc.arg(2) - top))
            return 0, 0x14
        p.stub(0x4094C0, draw)
        p.mu.mem_map(0x0C300000, 0x1000) if not p.mapped(0x0C300000, 1) else None
        popup = p.alloc(0x100)
        p.put32(popup + 0x14, 200)
        p.put32(popup + 0x1C, 520)
        p.put32(popup + 0x18, top)
        p.put32(popup + 0x60, k)
        p.put32(popup + 0x74, self.manager)
        p.put32(popup + 0x7C, 0x0C300800)
        p.call(0x436440, ecx=popup)
        return draws


def vv1(mode: str = "stock", everything: bool = True, slot: int = 0) -> tuple[Game, NewHome]:
    g = Game("vv1", rendered("vv1", mode, everything), slot)
    world = NewHome(g)
    assert g.install() == 1
    return g, world


@unittest.skipUnless(STOCK["vv1"].is_file(), STOCK_ABSENT)
@unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
class NewHomeCauseOfDeath(unittest.TestCase):
    def test_install_writes_every_site_in_every_mode_alone_and_with_everything(self):
        for mode in MODES:
            for everything in (False, True):
                g = Game("vv1", rendered("vv1", mode, everything))
                NewHome(g)
                for d in manifest("vv1")["runtime_detours"]:
                    va = int(d["va"], 16)
                    self.assertEqual(g.p.read(va, len(bytes.fromhex(d["stock_bytes"]))),
                                     bytes.fromhex(d["stock_bytes"]), (mode, everything, d["va"]))
                self.assertEqual(g.install(), 1, (mode, everything))
                for d in manifest("vv1")["runtime_detours"]:
                    self.assertEqual(g.p.read(int(d["va"], 16), 1), b"\xE9", (mode, everything, d["va"]))

    def test_one_wrong_byte_anywhere_installs_nothing(self):
        for d in manifest("vv1")["runtime_detours"]:
            g = Game("vv1", rendered("vv1", "stock", True))
            NewHome(g)
            va = int(d["va"], 16)
            g.p.write(va + 1, bytes([g.p.read(va + 1, 1)[0] ^ 0xFF]))
            self.assertEqual(g.install(), 0, d["va"])
            for other in manifest("vv1")["runtime_detours"]:
                if other is not d:
                    self.assertNotEqual(g.p.read(int(other["va"], 16), 1), b"\xE9", (d["va"], other["va"]))

    def test_each_cause_is_recorded_at_its_own_site_with_the_age(self):
        for mode in MODES:
            g, w = vv1(mode)
            w.villager(3, "Olda", 1500, 40)
            w.old_age(3)
            w.villager(4, "Sicky", 700, 1)
            g.p.put32(w.record(4) + 0x354, 1)
            w.sickness(4)
            w.villager(5, "Hungry", 800, 1)
            w.hunger(5)
            w.villager(6, "Empty", 900, 1)
            w.no_food(6)
            w.villager(7, "Worker", 1000, 5)
            w.injury(7, 9)
            w.villager(8, "Exact", 1100, 6)     # an injury to exactly 0 kills too
            w.injury(8, 6)
            self.assertEqual([w.health(i) for i in (3, 4, 5, 6, 8)], [0, 0, 0, 0, 0], mode)
            self.assertEqual(w.health(7), -4, mode)
            self.assertEqual(g.logged, [
                (1, w.record(3), 1500, "Old age"),
                (1, w.record(4), 700, "Disease"),
                (1, w.record(5), 800, "Starvation"),
                (1, w.record(6), 900, "Starvation"),
                (1, w.record(7), 1000, "Work accident"),
                (1, w.record(8), 1100, "Work accident"),
            ], mode)

    def test_a_change_that_does_not_kill_records_nothing(self):
        g, w = vv1()
        w.villager(4, "Sicky", 700, 2)
        w.sickness(4)
        w.villager(7, "Worker", 1000, 10)
        w.injury(7, 9)
        w.villager(8, "Bones", 1000, 0)      # already dead
        w.old_age(8)
        w.injury(8, 3)
        self.assertEqual((w.health(4), w.health(7)), (1, 1))
        self.assertEqual(g.logged, [])
        self.assertEqual(g.stats()["deaths"], 0)

    def test_an_unreported_death_is_found_only_for_a_villager_seen_alive(self):
        g, w = vv1()
        w.villager(10, "Eventa", 600, 50)
        w.villager(11, "Loaded", 650, 0)      # a body the village was loaded with
        g.tick()
        g.p.put32(w.record(10) + V1["health"], 0)   # an island event's store
        g.tick()
        g.tick()
        self.assertEqual(g.logged, [(1, w.record(10), 600, "Unknown causes")])
        self.assertEqual(g.stats()["unhooked"], 1)

    def test_the_grave_shows_the_cause_and_the_epitaph(self):
        for mode in MODES:
            g, w = vv1(mode)
            g.force_roll(1)
            w.villager(3, "Olda", 1500, 40, skills=(10, 70, 20, 30, 40))  # best: Building
            w.old_age(3)
            k = w.bury(3)
            self.assertEqual(k, 0, mode)
            self.assertEqual(g.p.read(w.record(3) + V1["present"], 1), b"\x00")
            lines = w.popup(k)
            texts = [t for t, _, _ in lines]
            self.assertIn("Here Lies Olda", texts, mode)
            self.assertIn(("\"Strong Arms, Big Heart\"", 0x46), [(t, y) for t, _, y in lines], mode)
            self.assertIn(("Old age", 0xD2), [(t, y) for t, _, y in lines], mode)
            # Same centre as the game's own lines.
            self.assertEqual(len({x for _, x, _ in lines}), 1, mode)
            self.assertEqual(g.stats()["graves_set"], 1, mode)

    def test_graves_from_before_and_changed_graves_show_nothing_extra(self):
        g, w = vv1()
        # A grave the game wrote before the patch (no entry).
        g.p.write(w.grave(5), b"Ancestor\0")
        g.p.put32(w.grave(5) + V1["grave_age"], 1300)
        self.assertEqual([t for t, _, _ in w.popup(5)], ["Here Lies Ancestor", "Job", "Untrained", "Age 65"])
        # A body already lying when installed: no cause, but an epitaph.
        w.villager(6, "Lying", 1200, 0, skills=(0, 0, 0, 0, 0))
        k = w.bury(6)
        texts = [t for t, _, _ in w.popup(k)]
        self.assertIn("\"Respected Citizen\"", texts)
        self.assertFalse(any(t in texts for t in ("Old age", "Unknown causes", "Disease")))
        # A recorded grave whose name no longer matches shows nothing extra.
        w.villager(7, "Real", 1400, 30)
        w.old_age(7)
        k = w.bury(7)
        g.p.write(w.grave(k), b"Other\0")
        self.assertEqual(len(w.popup(k)), 4)

    def test_a_decayed_body_takes_its_cause_with_it(self):
        g, w = vv1()
        w.villager(12, "Gone", 1500, 30)
        w.old_age(12)
        w.decay(12)
        self.assertEqual(g.p.read(w.record(12) + V1["present"], 1), b"\x00")
        # The same villager's record is buried after all (an edit restores it):
        # nothing recorded remains, so only the epitaph its data decides shows.
        g.p.write(w.record(12) + V1["present"], b"\x01")
        k = w.bury(12)
        texts = [t for t, _, _ in w.popup(k)]
        self.assertNotIn("Old age", texts)

    def test_the_epitaph_rule(self):
        cases = [
            # (age, skills Parenting, Building, Farming, Healing, Research), roll -> epitaph
            ((300, (90, 90, 90, 90, 90)), 0, "Curious and Playful"),
            ((300, (0, 0, 0, 0, 0)), 1, "Loving and Special"),
            ((400, (0, 0, 0, 0, 0)), 0, "Respected Citizen"),
            ((400, (0, 0, 5, 0, 0)), 0, "Child of the Earth"),
            ((400, (0, 0, 5, 0, 0)), 1, "Nature's Friend"),
            ((400, (7, 0, 0, 0, 0)), 0, "Parent, Teacher, Friend"),
            ((400, (7, 0, 0, 0, 0)), 1, "Dedicated to Children"),
            ((400, (0, 0, 0, 9, 0)), 0, "Guardian of Health"),
            ((400, (0, 0, 0, 9, 0)), 1, "Dedicated to Others"),
            ((400, (0, 0, 0, 0, 3)), 0, "Dedicated Student"),
            ((400, (0, 0, 0, 0, 3)), 1, "Inspired Inventor"),
            ((400, (0, 4, 0, 0, 0)), 0, "Inspired Architect"),
            ((400, (0, 4, 0, 0, 0)), 1, "Strong Arms, Big Heart"),
            # Ties keep the earlier in Farming, Parenting, Healing, Research, Building.
            ((400, (50, 50, 50, 50, 50)), 0, "Child of the Earth"),
            ((400, (50, 50, 0, 50, 50)), 0, "Parent, Teacher, Friend"),
            ((400, (0, 50, 0, 50, 50)), 0, "Guardian of Health"),
            ((400, (0, 50, 0, 0, 50)), 0, "Dedicated Student"),
            ((359, (0, 9, 0, 0, 0)), 0, "Curious and Playful"),
            ((360, (0, 9, 0, 0, 0)), 0, "Inspired Architect"),
        ]
        g, w = vv1()
        for n, ((age, skills), roll, want) in enumerate(cases):
            g.force_roll(roll)
            i = 20 + n
            w.villager(i, f"V{n}", age, 30, skills)
            w.old_age(i)
            k = w.bury(i)
            self.assertIn(f"\"{want}\"", [t for t, _, _ in w.popup(k)], (age, skills, roll))


# ---- The Lost Children ------------------------------------------------------
V2 = dict(pool_global=0x499F24, stride=0xE48C, present=0x30, selected=0x31, health=0x52C, age=0x530,
          name=0x564, skills=0x7E4, totem=0x558, world=0xE574D4, graves=0x2EB0C, grave_stride=0x7C,
          grave_age=0x74)


class LostChildren:
    def __init__(self, g: Game):
        self.g = g
        p = g.p
        self.pool = p.alloc(V2["world"] + 0x100)
        self.world = p.alloc(0x31000)
        p.put32(V2["pool_global"], self.pool)
        p.put32(self.pool + V2["world"], self.world)
        self.step = p.alloc(16)
        p.put32(self.step, self.world)
        p.put32(self.step + 4, self.pool)

    def record(self, i: int) -> int:
        return self.pool + i * V2["stride"]

    def villager(self, i: int, name: str, age: int, health: int) -> int:
        r = self.record(i)
        p = self.g.p
        p.write(r, bytes(0x900))
        p.write(r + V2["present"], b"\x01")
        p.put32(r + V2["health"], health)
        p.put32(r + V2["age"], age)
        p.write(r + V2["name"], name.encode() + b"\0")
        return r

    def health(self, i: int) -> int:
        return struct.unpack("<i", self.g.p.read(self.record(i) + V2["health"], 4))[0]

    def grave(self, k: int) -> int:
        return self.world + V2["graves"] + k * V2["grave_stride"]

    def run(self, start: int, stop: int, **regs) -> None:
        p = self.g.p
        p.set_reg("esp", 0x0FF00000 - 0x2000)
        for name, value in regs.items():
            p.set_reg(name, value)
        p.run(start, stop)

    def old_age(self, i: int) -> None:
        self.run(0x43BDEA, 0x43BDFE, ebx=self.record(i), eax=0, ecx=1)

    def sickness(self, i: int) -> None:
        self.run(0x43BC39, 0x43BC4D, esi=self.step, edi=i * V2["stride"])

    def hunger(self, i: int) -> None:
        self.run(0x43BAE1, 0x43BAF5, esi=self.step, edi=i * V2["stride"])

    def no_food(self, i: int) -> None:
        self.run(0x43BB7B, 0x43BB87, esi=self.step, edi=i * V2["stride"])

    def injury(self, i: int, damage: int) -> None:
        self.run(0x462AD9, 0x462AE1, edi=self.record(i) + V2["health"], eax=damage, esi=self.pool)

    def bury(self, i: int) -> int:
        """The burial's grave loop, 0x465042..0x465334 (the record already
        freed by 0x46503B, as the game does just before)."""
        p = self.g.p
        before = [p.u32(self.grave(k) + V2["grave_age"]) for k in range(50)]
        burier = p.alloc(0x100)
        p.put32(burier + 0x60, i)
        p.write(self.record(i) + V2["present"], b"\x00")
        p.stub(0x44B4D0, lambda proc: (30, 8))
        p.stub(0x4031A0, lambda proc: (0, 0))
        strings = p.alloc(0x100)
        p.write(strings, b"Respected Citizen\0")
        p.stub(0x441680, lambda proc: (strings, 4))
        def sprintf(proc):
            text = proc.cstring(proc.arg(1)).encode("latin-1")
            proc.write(proc.arg(0), text + b"\0")
            return len(text), 0
        p.stub(0x4682BD, sprintf)
        self.run(0x465040, 0x465334, esi=self.pool, edi=burier, ebx=0)
        for k in range(50):
            if before[k] == 0 and p.u32(self.grave(k) + V2["grave_age"]) != 0:
                return k
        return -1

    def decay(self, i: int) -> None:
        self.run(0x43B78D, 0x43B792, eax=self.pool, edi=i * V2["stride"], esi=self.step)

    def panel(self, k: int) -> list[tuple[str, int, int]]:
        p = self.g.p
        draws: list[tuple[str, int, int]] = []
        top = 100
        pool = p.alloc(0x100)
        p.write(pool, b"Age\0")
        p.write(pool + 0x20, b"Here Lies \0")
        p.stub(0x408320, lambda proc: (0x0C300000, 0))
        p.stub(0x441680, lambda proc: ((pool + 0x20 if proc.arg(0) == 0xCF else pool), 4))
        def sprintf(proc):
            fmt = proc.cstring(proc.arg(1))
            if fmt == "%s %i":
                text = proc.cstring(proc.arg(2)) + " " + str(proc.arg(3))
            elif "%" in fmt:
                text = fmt.replace("%s", proc.cstring(proc.arg(2)))
            else:
                text = fmt
            proc.write(proc.arg(0), text.encode("latin-1") + b"\0")
            return len(text), 0
        p.stub(0x4682BD, sprintf)
        def draw(proc):
            draws.append((proc.cstring(proc.arg(0)), proc.arg(1), proc.arg(2) - top))
            return 0, 0x14
        p.stub(0x4096B0, draw)
        p.stub(0x40C510, lambda proc: (0, 0))
        textbox = p.alloc(0x40)
        vtable = p.alloc(0x40)
        ret = p.alloc(0x10)
        p.write(ret, b"\xC3")
        p.put32(textbox, vtable)
        p.put32(vtable + 0xC, ret)
        panel = p.alloc(0x100)
        p.put32(panel + 0x14, 200)
        p.put32(panel + 0x1C, 520)
        p.put32(panel + 0x18, top)
        p.put32(panel + 0x60, k)
        p.put32(panel + 0x78, self.world)
        p.put32(panel + 0x80, 0x0C300800)
        p.put32(panel + 0x84, textbox)
        p.call(0x444490, ecx=panel)
        return draws


def vv2(mode: str = "stock", everything: bool = True) -> tuple[Game, LostChildren]:
    g = Game("vv2", rendered("vv2", mode, everything))
    world = LostChildren(g)
    assert g.install() == 1
    return g, world


@unittest.skipUnless(STOCK["vv2"].is_file(), STOCK_ABSENT)
@unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
class LostChildrenCauseOfDeath(unittest.TestCase):
    def test_install_writes_every_site_in_every_mode_alone_and_with_everything(self):
        for mode in MODES:
            for everything in (False, True):
                g = Game("vv2", rendered("vv2", mode, everything))
                LostChildren(g)
                self.assertEqual(g.install(), 1, (mode, everything))
                for d in manifest("vv2")["runtime_detours"]:
                    self.assertEqual(g.p.read(int(d["va"], 16), 1), b"\xE9", (mode, everything, d["va"]))

    def test_one_wrong_byte_anywhere_installs_nothing(self):
        for d in manifest("vv2")["runtime_detours"]:
            g = Game("vv2", rendered("vv2", "stock", True))
            LostChildren(g)
            va = int(d["va"], 16)
            g.p.write(va, b"\xCC")
            self.assertEqual(g.install(), 0, d["va"])

    def test_each_cause_is_recorded_at_its_own_site_with_the_age(self):
        for mode in MODES:
            g, w = vv2(mode)
            w.villager(3, "Olda", 1500, 40)
            w.old_age(3)
            w.villager(4, "Sicky", 700, 1)
            w.sickness(4)
            w.villager(5, "Hungry", 800, 1)
            w.hunger(5)
            w.villager(6, "Empty", 900, 1)
            w.no_food(6)
            w.villager(7, "Worker", 1000, 5)
            w.injury(7, 9)
            w.villager(8, "Fine", 1000, 50)
            w.injury(8, 9)
            self.assertEqual(g.logged, [
                (2, w.record(3), 1500, "Old age"),
                (2, w.record(4), 700, "Disease"),
                (2, w.record(5), 800, "Starvation"),
                (2, w.record(6), 900, "Starvation"),
                (2, w.record(7), 1000, "Work accident"),
            ], mode)
            self.assertEqual(w.health(8), 41)

    def test_a_totem_is_never_a_death(self):
        g, w = vv2()
        w.villager(9, "Statue", 900, 50)
        g.p.write(w.record(9) + V2["totem"], b"\x01")
        g.tick()
        g.p.put32(w.record(9) + V2["health"], 0)
        g.tick()
        self.assertEqual(g.logged, [])

    def test_the_grave_shows_the_cause_under_the_age_and_keeps_its_own_epitaph(self):
        for mode in MODES:
            g, w = vv2(mode)
            w.villager(3, "Olda", 1500, 40)
            w.old_age(3)
            k = w.bury(3)
            self.assertGreaterEqual(k, 0)
            lines = w.panel(k)
            self.assertIn(("Old age", 0xD2), [(t, y) for t, _, y in lines], mode)
            self.assertIn(("Age 75", 0xB4), [(t, y) for t, _, y in lines], mode)
            # No epitaph from here: the game's own stays in its text box, between
            # the two quote marks the game itself draws.
            self.assertEqual([t for t, _, _ in lines if t.startswith("\"")], ["\"", "\""], mode)
            self.assertEqual(g.stats()["draws"], 1, mode)
            self.assertEqual(bytes(g.p.read(w.grave(k) + 0x19, 18)), b"Respected Citizen\0")

    def test_graves_from_before_and_decayed_bodies_show_nothing_extra(self):
        g, w = vv2()
        g.p.write(w.grave(4), b"Ancestor\0")
        g.p.put32(w.grave(4) + V2["grave_age"], 1300)
        self.assertNotIn(0xD2, [y for _, _, y in w.panel(4)])
        w.villager(12, "Gone", 1500, 30)
        w.old_age(12)
        w.decay(12)
        g.p.write(w.record(12) + V2["present"], b"\x01")
        k = w.bury(12)
        self.assertNotIn(0xD2, [y for _, _, y in w.panel(k)])


# ---- The Secret City, The Tree of Life, New Believers --------------------------
ARB = {"vv3": dict(set=0x462670, add=0x4626B0, block=0xE6C, age=0xDC4),
       "vv4": dict(set=0x46AF00, add=0x46AF40, block=0x1C34, age=0x1B8C),
       "vv5": dict(set=0x4758B0, add=0x4758F0, block=0x1C34, age=0x1B8C)}


class LaterGames(unittest.TestCase):
    def arbiter(self, g: Game, which: str, block: int, value: int, cause: int, ret: int | None = None) -> None:
        p = g.p
        esp = 0x0FF00000 - 0x2000
        p.put32(esp + 4, value & 0xFFFFFFFF)
        p.put32(esp + 8, cause & 0xFFFFFFFF)
        p.put32(esp, ret if ret is not None else 0x0D000000)
        if ret is not None and not p.mapped(ret, 1):
            p.mu.mem_map(ret & ~0xFFF, 0x1000)
        if ret is not None:
            p.write(ret, b"\xC3")
        p.set_reg("esp", esp)
        p.set_reg("ecx", block)
        p.run(ARB[g.game][which], ret if ret is not None else 0x0D000000)

    def test_each_arbiter_logs_alive_to_dead_with_the_games_words(self):
        for game in ("vv3", "vv4", "vv5"):
            if not STOCK[game].is_file() or not TEST_DLL.is_file():
                continue
            for mode in MODES:
                g = Game(game, rendered(game, mode, True))
                self.assertEqual(g.install(), 1, (game, mode))
                a = ARB[game]
                record = g.p.alloc(0x3000)
                block = record + a["block"]
                g.p.put32(record + a["age"], 1234)
                expect = []
                for which, health, value, cause, dies in (
                        ("set", 40, 0, 2, True), ("add", 3, -5, 0, True), ("add", 5, -1, -1, False),
                        ("set", 9, 0, -1, True), ("add", 1, -1, 1, True), ("add", 2, -9, 3, True),
                        ("set", 0, 0, 2, False), ("add", -3, -1, 0, False), ("set", 30, 50, 2, False)):
                    g.p.put32(block + 0xC, health & 0xFFFFFFFF)
                    g.p.put32(block + 0x10, 0xFFFFFFFF)
                    self.arbiter(g, which, block, value, cause)
                    result = health + value if which == "add" else value
                    stored = 0 if result <= 0 else min(result, 100)
                    self.assertEqual(struct.unpack("<i", g.p.read(block + 0xC, 4))[0], stored, (game, which))
                    self.assertEqual(struct.unpack("<i", g.p.read(block + 0x10, 4))[0],
                                     cause if result <= 0 else -1, (game, which))
                    if dies:
                        expect.append((int(game[-1]), record, 1234,
                                       {-1: "Unknown causes", 0: "Disease", 1: "Starvation", 2: "Old age",
                                        3: "Work accident"}[cause]))
                self.assertEqual(g.logged, expect, (game, mode))

    def test_reanimates_stand_in_is_not_a_death(self):
        if not STOCK["vv5"].is_file() or not TEST_DLL.is_file():
            self.skipTest(STOCK_ABSENT)
        g = Game("vv5", rendered("vv5", "stock", True))
        self.assertEqual(g.install(), 1)
        record = g.p.alloc(0x3000)
        block = record + 0x1C34
        g.p.put32(block + 0xC, 100)
        self.arbiter(g, "set", block, 0, -1, ret=0x46FE6B)
        self.assertEqual(g.logged, [])

    def test_one_wrong_byte_installs_nothing(self):
        for game in ("vv3", "vv4", "vv5"):
            if not STOCK[game].is_file() or not TEST_DLL.is_file():
                continue
            for d in manifest(game)["runtime_detours"]:
                g = Game(game, rendered(game, "stock", True))
                g.p.write(int(d["va"], 16) + 2, b"\x00")
                self.assertEqual(g.install(), 0, (game, d["va"]))


class ManifestsAndShipping(unittest.TestCase):
    def test_rows_are_public_default_on_and_pin_the_dll(self):
        import hashlib
        import vv_fun_patcher as vfp
        public = {p.id: p for p in vfp.load_public_fun_patches()}
        sha = hashlib.sha256(SHIPPED_DLL.read_bytes()).hexdigest().upper()
        for game in NAMES:
            m = manifest(game)
            self.assertIn(f"{game}_cause_of_death", public)
            self.assertTrue(m["enabled"] and m["catalog_enabled"] and not m["catalog_hidden"])
            self.assertEqual(m["patches"], [])
            self.assertEqual(m["companion_files"][0]["sha256"], sha)
            self.assertEqual(m["dependencies"], [f"{game}_enable_origins_exclusive_features"])
            self.assertEqual(m["needs_on"][0]["id"], f"{game}_write_parentage_log")
            self.assertIn("**", m["description"])

    def test_every_origins_companion_carries_the_bridge_wherever_the_story_bridge_runs(self):
        for source in ("native/vv1_origins_icons/vv1_origins_icons.c",
                       "native/vv2_origins_icons/vv2_origins_icons.c",
                       "native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c",
                       "native/vv4_origins_icons/vv4_origins_icons.c",
                       "native/vv5_task9_origins/vv5_task9_origins.c"):
            text = (ROOT / source).read_text(encoding="utf-8")
            lines = text.splitlines()
            calls = [n for n, line in enumerate(lines) if line.strip().startswith("vvfp_story_bridge(")]
            self.assertTrue(calls, source)
            for n in calls:
                self.assertTrue(lines[n + 1].strip().startswith("vvfp_cause_bridge("), (source, n))

    def test_start_over_tells_the_companion_by_its_shipped_name_and_export(self):
        reset = (ROOT / "native/save_reset_export/save_reset_export.c").read_text(encoding="utf-8")
        self.assertIn('GetModuleHandleA("VVFP Cause of Death.dll")', reset)
        self.assertIn('GetProcAddress(cause, "VvfpCauseVillageReset")', reset)
        self.assertLess(reset.index("notify_cause_of_death(game, slot);"),
                        reset.index("return vv_reset_slot_state(game, slot, header);"))
        for name in ("vvfp_cause_of_death.def", "vvfp_cause_of_death_test.def"):
            text = (ROOT / "native/vvfp_cause_of_death" / name).read_text(encoding="utf-8")
            self.assertIn("VvfpCauseVillageReset=_VvfpCauseVillageReset@8", text)

    def test_the_release_ships_the_dll(self):
        text = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn("assets/cause_of_death/VVFP Cause of Death.dll", text)


if __name__ == "__main__":
    unittest.main()
