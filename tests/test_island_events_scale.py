"""Island Events Scale With Population (like The Lost Children) and Island Events Scale With Stored Food and Tech Points
(A New Home, The Tree of Life, New Believers): vvN_island_events_scale_with_population / _with_stored_amounts.

The owner (2026-11-12): island-event food and tech-point gains and losses are multiplied by k = 1 up to 25 living
villagers, 2 for 26 to 50 and 3 above 50 (The Lost Children's two-choice rule 0x41F720), the population as each
game's own routine counts it; or, the alternative, each becomes the stock amount plus a tenth of the food or tech
points stored.  Losses keep their stock floor; a rolled amount is scaled after the roll.

EMULATED with the shipped "VVFP Island Events Scale.dll" beside the stock executable (tests/story_emulator.py's
Process), started as VVFP Startup.dll starts it:

* every site of the three games is run from its own instruction to the game's food or tech writer (or, for a
  single-result setter, the setter is called), with the population built in the game's own villager records and
  counted by the game's own routine: k = 1, 2, 3 at 25, 26, 50 and 51 villagers, for gains and losses; babies being
  carried count, and New Believers' Heathens do not;
* the loss clamps: a single-result setter clamps the scaled loss to what is stored; the two-choice writers stop at 0;
* with the flag file the stored amounts: the stock amount plus floor(stored / 10), with its sign, never less;
* The Tree of Life and New Believers built with 256 Villagers (Experimental): the manager where that build moves it;
* every other public patch of each game, in every population mode, leaves every site's stock bytes in place and the
  companion installs on that executable (and with The Tree of Life's Origins tail jumps the scaled amount still
  reaches the writer);
* a site that is not stock: nothing is installed.

The live effect in a running game is NOT verified here.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import patcher_files  # noqa: E402
import vv_fun_patcher as patcher  # noqa: E402
import vv_fun_patcher_gui as gui  # noqa: E402

try:
    import pefile
    from story_emulator import RETURN, STACK_TOP, Process

    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

GAMES = (1, 4, 5)
DLL = ROOT / "assets" / "island_events_scale" / "VVFP Island Events Scale.dll"
FLAG = "VVFP Island Events Scale Stored.txt"
FLAG_PATH = ("C:\\Games\\Village\\" + patcher_files.PATCHER_FILES_FOLDER + "\\" + FLAG).lower()
MODES = ("stock", "collection_progression", "immediate_fixed")
STOCK = {g: ROOT / "research" / "stock-executables" / name for g, name in (
    (1, "Virtual Villagers - A New Home.exe"), (4, "Virtual Villagers - The Tree of Life.exe"),
    (5, "Virtual Villagers - New Believers.exe"))}
HAVE_STOCK = all(p.is_file() for p in STOCK.values())


def population_id(game: int) -> str:
    return f"vv{game}_island_events_scale_with_population"


def stored_id(game: int) -> str:
    return f"vv{game}_island_events_scale_with_stored_amounts"


def _builder():
    spec = importlib.util.spec_from_file_location("ies_builder", ROOT / "scripts" / "build_island_events_scale_features.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDER = _builder()
SITES = BUILDER.SITES

# Each game: the food and tech writers (thiscall(amount)) and where food and tech are kept.
WRITERS = {1: (0x41D140, 0x41D120), 4: (0x41D920, 0x41E300), 5: (0x41EB40, 0x4237B0)}
STORES = {4: (0x4D6DD0, 0x4D6F88), 5: (0x51D34C, 0x51D5F8)}
VV1_FOOD, VV1_TECH, VV1_WORLD, VV1_ROSTER = 0xA2EC, 0xA2FC, 0x50A4, 0xADE8
# The villager managers: (stock manager, first record, record size, slots); 256 Villagers moves it to 0x800000.
MANAGERS = {4: (0x50E568, 0x44, 0x2E3C, 150), 5: (0x554148, 0x48, 0x2F44, 150)}
# Achievement counters the writers call (the counter object is not built here): stood in for.
COUNTERS = {4: (0x412F90,), 5: (0x413450, 0x423600)}


def with_requirements(game: int, rows: list[str]) -> list[str]:
    """The rows and everything they require, dependency first."""
    by_id = {p.id: p for p in patcher.load_fun_patches()}
    chosen: list[str] = []

    def add(row: str) -> None:
        if row in chosen:
            return
        for dependency in patcher._dependency_ids(by_id[row]):
            if dependency in by_id:
                add(dependency)
        chosen.append(row)

    for row in rows:
        add(row)
    return patcher.resolve_fun_patch_ids(chosen, game_id=f"vv{game}")


def s32(v: int) -> int:
    return v - (1 << 32) if v & 0x80000000 else v


def k_of(n: int) -> int:
    return 3 if n > 50 else 2 if n > 25 else 1


class TheRows(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = {p.id: p.raw for p in patcher.load_fun_patches()}
        self.public = {p.id for p in patcher.load_public_fun_patches()}

    def test_six_public_rows_ship_the_companion_and_the_flag(self) -> None:
        dll_sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        flag_sha = hashlib.sha256((ROOT / "assets" / "island_events_scale" / FLAG).read_bytes()).hexdigest().upper()
        for game in GAMES:
            pop, stored = self.rows[population_id(game)], self.rows[stored_id(game)]
            self.assertIn(population_id(game), self.public)
            self.assertIn(stored_id(game), self.public)
            self.assertEqual(pop["name"], "Island Events Scale With Population (like The Lost Children)")
            self.assertEqual(stored["name"], "Island Events Scale With Stored Food and Tech Points")
            self.assertEqual(pop["patches"], [])
            self.assertEqual(stored["patches"], [])
            self.assertEqual([(c["destination"], c["sha256"]) for c in pop["companion_files"]],
                             [("VVFP Island Events Scale.dll", dll_sha)])
            self.assertEqual([(c["destination"], c["sha256"]) for c in stored["companion_files"]],
                             [("VVFP Island Events Scale.dll", dll_sha), (FLAG, flag_sha)])
            self.assertIn("**Needs no other patch.**", pop["description"])
            self.assertIn("**Cannot be ticked together with", pop["description"])
            self.assertIn("**Cannot be ticked together with", stored["description"])
        self.assertIn(FLAG, patcher_files.PATCHER_READS)
        self.assertEqual(patcher_files.installed_relative_path(FLAG).as_posix(),
                         patcher_files.PATCHER_FILES_FOLDER + "/" + FLAG)
        self.assertIn("VVFP Island Events Scale.dll", patcher.STARTUP_LOADER_COMPANIONS_2)

    def test_the_detours_are_the_sites_the_companion_holds(self) -> None:
        source = (ROOT / "native" / "vvfp_island_events_scale" / "vvfp_island_events_scale.c").read_text(encoding="utf-8")
        for game in GAMES:
            for row_id in (population_id(game), stored_id(game)):
                detours = self.rows[row_id]["runtime_detours"]
                self.assertEqual([(int(d["va"], 16), d["stock_bytes"]) for d in detours],
                                 [(va, stock) for va, stock, *_ in SITES[game]])
                for d in detours:
                    self.assertEqual(len(d["written_bytes"]), len(d["stock_bytes"]))
                    self.assertTrue(d["written_bytes"].startswith("E8XXXXXXXX"))
            # The C table holds the same sites, bytes and amounts.
            table = source.split(f"static const es_site VV{game}_SITES[] = {{")[1].split("};")[0]
            entries = [line for line in table.splitlines() if line.strip().startswith("{ 0x")]
            self.assertEqual(len(entries), len(SITES[game]))
            for line, (va, stock, _form, kind, amount, _what) in zip(entries, SITES[game]):
                fields = [f.strip() for f in line.strip()[1:].split(",")]
                self.assertEqual(int(fields[0].rstrip("u"), 16), va)
                self.assertEqual(int(fields[1]), len(bytes.fromhex(stock)))
                self.assertEqual(fields[3], "ES_FOOD" if kind == "food" else "ES_TECH")
                self.assertEqual(int(fields[4]), amount)
                expect = bytes(int(b.strip(" {}"), 16) for b in line.split("{", 2)[2].split("}")[0].split(","))
                self.assertEqual(expect.hex().upper(), stock)

    @unittest.skipUnless(HAVE_STOCK, "needs the stock executables")
    def test_every_site_holds_its_stock_bytes(self) -> None:
        for game in GAMES:
            pe = pefile.PE(str(STOCK[game]), fast_load=True)
            data = STOCK[game].read_bytes()
            for va, stock, *_ in SITES[game]:
                off = pe.get_offset_from_rva(va - 0x400000)
                self.assertEqual(data[off:off + len(stock) // 2].hex().upper(), stock, hex(va))

    def test_no_other_row_claims_a_site(self) -> None:
        """No exe patch and no runtime detour of any other row touches a site's bytes (Origins' tail jumps and
        Story / Cheat Upgrades' rand calls end where a site begins or begin where it ends)."""
        for game in GAMES:
            pe = pefile.PE(str(STOCK[game]), fast_load=True)
            mine = {population_id(game), stored_id(game)}
            ranges = [(va, va + len(stock) // 2) for va, stock, *_ in SITES[game]]
            for p in patcher._load_fun_patch_records():
                if p.raw.get("game_id") != f"vv{game}" or p.id in mine:
                    continue
                claims = []
                for patch in p.raw.get("patches", []) or []:
                    try:
                        va = 0x400000 + pe.get_rva_from_offset(int(patch["offset"], 16))
                    except Exception:
                        continue
                    claims.append((va, len(patch.get("before", "")) // 2 or int(patch.get("length", 1))))
                for d in p.raw.get("runtime_detours", []) or []:
                    claims.append((int(str(d["va"]), 0), len(bytes.fromhex(d["stock_bytes"]))))
                for va, n in claims:
                    for start, end in ranges:
                        self.assertFalse(va < end and start < va + n, (p.id, hex(va), hex(start)))

    def test_defaults_alternative_and_owners_defaults(self) -> None:
        for game in GAMES:
            pop, stored = population_id(game), stored_id(game)
            self.assertIn(pop, gui.DEFAULT_OFF_FUN_PATCH_IDS)
            self.assertNotIn(pop, gui.OWNERS_DEFAULT_OFF_FUN_PATCH_IDS)
            self.assertTrue(gui.owners_default_fun_patch_selection(pop))
            self.assertNotIn(pop, gui.SELECT_ALL_OFF_FUN_PATCH_IDS)
            self.assertIn(stored, patcher.ALTERNATIVE_FUN_PATCH_IDS)
            self.assertIn(stored, gui.DEFAULT_OFF_FUN_PATCH_IDS)
            self.assertIn(stored, gui.OWNERS_DEFAULT_OFF_FUN_PATCH_IDS)
            self.assertFalse(gui.owners_default_fun_patch_selection(stored))
            self.assertIn(stored, gui.SELECT_ALL_OFF_FUN_PATCH_IDS)

    def test_classic_vv_difficulty_ticks_the_population_row(self) -> None:
        for game in (4, 5):
            classic = self.rows[f"vv{game}_classic_vv_difficulty"]
            self.assertIn(population_id(game), classic["dependencies"])
            self.assertNotIn(stored_id(game), classic["dependencies"])
            self.assertIn("Island Events Scale With Population (like The Lost Children)", classic["description"])
            self.assertIn("part of Classic VV Difficulty", self.rows[population_id(game)]["description"])
        # A New Home has no Classic VV Difficulty row.
        self.assertNotIn("vv1_classic_vv_difficulty", self.rows)
        self.assertNotIn("Classic", self.rows[population_id(1)]["description"])

    def test_the_two_cannot_be_built_together(self) -> None:
        for game in GAMES:
            pop, stored = population_id(game), stored_id(game)
            self.assertEqual(self.rows[pop]["conflicts"], [stored])
            self.assertIn(pop, self.rows[stored]["conflicts"])
            self.assertEqual(patcher.resolve_fun_patch_ids([pop], game_id=f"vv{game}"), [pop])
            self.assertEqual(patcher.resolve_fun_patch_ids([stored], game_id=f"vv{game}"), [stored])
            with self.assertRaises(patcher.PatcherError):
                patcher.resolve_fun_patch_ids([pop, stored], game_id=f"vv{game}")
            # The window greys out the other one while one is ticked.
            fun = patcher.load_public_fun_patches()
            self.assertEqual(gui.conflict_blockers(stored, fun, {pop}), [self.rows[pop]["name"]])
            self.assertEqual(gui.conflict_blockers(pop, fun, {stored}), [self.rows[stored]["name"]])
        for game in (4, 5):
            # Classic VV Difficulty ticks the population row, so it cannot be built with the stored one either.
            classic = f"vv{game}_classic_vv_difficulty"
            self.assertIn(classic, self.rows[stored_id(game)]["conflicts"])
            with self.assertRaises(patcher.PatcherError):
                patcher.resolve_fun_patch_ids(
                    list(self.rows[classic]["dependencies"]) + [classic, stored_id(game)], game_id=f"vv{game}")


class GameMechanicsPages(unittest.TestCase):
    """Each game's Island events page defines k and the stored rule, and marks every scaled event, only with the
    patch in the game's exe."""

    def facts(self, game: int, installed: set[str]) -> list[str]:
        import vv_game_mechanics as gm
        import vv_game_mechanics_events as events
        village = gm.Village(folder=ROOT, game=game, slot=1, save=ROOT, data=b"", installed=frozenset(installed),
                             now=0.0)
        return [fact.text for fact in events.facts(village)]

    def test_the_rules_and_the_marks(self) -> None:
        import importlib
        for game in GAMES:
            module = importlib.import_module(f"vv_game_mechanics_events_vv{game}")
            titles = {event.title for event in module.EVENTS
                      if any(f == population_id(game) for f, _ in event.patched)}
            # The marked events are exactly the ones whose amounts the companion scales.
            named = {what.split(":")[0].split(",")[0].strip() for *_, what in SITES[game]}
            for title in titles:
                self.assertTrue(any(title.startswith(n) or n.startswith(title) for n in named), title)
            self.assertEqual(len(titles), {1: 4, 4: 12, 5: 18}[game])
            stock = self.facts(game, set())
            pop = self.facts(game, {population_id(game)})
            stored = self.facts(game, {stored_id(game)})
            self.assertFalse([t for t in stock if "Island Events Scale" in t])
            self.assertTrue(any("k is 1 up to 25 people, 2 up to 50, 3 above" in t for t in pop))
            self.assertEqual(sum("Island Events Scale With Population" in t for t in pop), 1 + len(titles))
            self.assertFalse([t for t in pop if "Stored Food and Tech Points" in t])
            self.assertTrue(any("plus a tenth of the food" in t for t in stored))
            self.assertEqual(sum("Island Events Scale With Stored Food and Tech Points" in t for t in stored),
                             1 + len(titles))
        heathens = [t for t in self.facts(5, {population_id(5)}) if "k is 1 up to 25" in t]
        self.assertIn("Heathens are not counted", heathens[0])


class Village:
    """A game's executable with the companion started, a population and the stores."""

    def __init__(self, game: int, stored: bool = False, exe: bytes | None = None, manager: int | None = None):
        self.game = game
        self.p = Process(exe if exe is not None else STOCK[game].read_bytes(), DLL)
        self.asked: list[str] = []

        def attributes(p):
            path = p.wstring(p.arg(0))
            self.asked.append(path.lower())
            return (0x20 if stored and path.lower() == FLAG_PATH else 0xFFFFFFFF), 4

        self.p.api_handlers["GetFileAttributesW"] = attributes
        for counter in COUNTERS.get(game, ()):
            self.p.stub(counter, lambda q: (0, 8))
        self.p.export("VvfpStartup", game, 0)
        if game == 1:
            self.world = self.p.alloc(0xB000)
            self.roster = self.p.alloc(256 * 0x3D8)
            self.p.put32(self.world + VV1_ROSTER, self.roster)
            self.encounter = self.p.alloc(0x6000)
            self.p.put32(self.encounter + VV1_WORLD, self.world)
        else:
            stock_manager, first, size, slots = MANAGERS[game]
            self.manager = manager if manager is not None else stock_manager
            self.first, self.size, self.slots = first, size, 256 if manager is not None else slots

    @property
    def installed(self) -> int:
        return self.p.export("VvfpIslandEventsScaleInstalled")

    def stores(self, food: int, tech: int) -> None:
        if self.game == 1:
            self.p.put32(self.world + VV1_FOOD, food)
            self.p.put32(self.world + VV1_TECH, tech)
        else:
            self.p.put32(STORES[self.game][0], food)
            self.p.put32(STORES[self.game][1], tech)

    def food(self) -> int:
        return s32(self.p.u32(self.world + VV1_FOOD if self.game == 1 else STORES[self.game][0]))

    def tech(self) -> int:
        return s32(self.p.u32(self.world + VV1_TECH if self.game == 1 else STORES[self.game][1]))

    def people(self, living: int, *, carried: int = 0, heathens: int = 0, dead: int = 0) -> None:
        """`living` living villagers (the first carrying `carried` babies), then `heathens` living Heathens (New
        Believers) and `dead` records that are occupied but not living."""
        if self.game == 1:
            for i in range(256):
                r = self.roster + i * 0x3D8
                alive = i < living + dead
                self.p.write(r + 0x28, bytes([1 if alive else 0]))
                self.p.put32(r + 0x344, 90 if i < living else 0)
                self.p.put32(r + 0x358, 1 if (i == 0 and carried) else 0)
                self.p.put32(r + 0x35C, carried)
            return
        for i in range(self.slots):
            r = self.manager + self.first + i * self.size
            here = i < living + heathens + dead
            living_here = i < living + heathens
            if self.game == 4:
                self.p.write(r + 0x1CC4, bytes([1 if here else 0]))
                self.p.write(r + 0x1CC7, bytes([0 if living_here else 1]))
            else:
                self.p.write(r + 0x1CD4, bytes([1 if here else 0]))
                self.p.write(r + 0x1CE1, bytes([1 if living <= i < living + heathens else 0]))
                self.p.write(r + 0x1CEC, bytes([0 if living_here else 1]))
            self.p.put32(r + 0x1C40, 90 if living_here else 0)
            self.p.put32(r + 0x1C4C, 1 if (i == 0 and carried) else 0)
            self.p.put32(r + 0x1C50, carried)

    def setter(self, va: int) -> int:
        """A single-result setter (vtable [14]): the amount it leaves at [this+8]."""
        obj = self.p.alloc(0x40)
        self.p.call(va, ecx=obj)
        return s32(self.p.u32(obj + 8))

    def to_writer(self, va: int, kind: str, *, eax: int = 0, until: int | None = None) -> int:
        """Run the site from its own instruction to the game's food or tech writer: the amount it is handed."""
        writer = until or WRITERS[self.game][0 if kind == "food" else 1]
        esp = STACK_TOP - 0x2000
        for i, word in enumerate((0x1234, RETURN, 0, 0, 0, 0)):
            self.p.put32(esp + 4 * i, word)
        self.p.set_reg("esp", esp)
        self.p.set_reg("eax", eax)
        self.p.set_reg("ecx", 0)
        if self.game == 1:
            self.p.set_reg("esi", self.encounter)
        self.p.run(va, writer, limit=200_000)
        return s32(self.p.u32(self.p.reg("esp") + 4))

    def tail_to_return(self, va: int, *, ecx: int) -> None:
        """A two-choice tail (mov [esp+4], amount ... jmp writer): run it, the real writer included."""
        esp = STACK_TOP - 0x2000
        self.p.put32(esp, RETURN)
        self.p.put32(esp + 4, 0)
        self.p.set_reg("esp", esp)
        self.p.set_reg("ecx", ecx)
        self.p.run(va, RETURN, limit=200_000)

    def amount(self, site, roll: int = 0) -> int:
        """What the site puts in place: the setter's [this+8], or the amount handed to the writer."""
        va, _stock, form, kind, _amount, _what = site
        if form == "setter":
            return self.setter(va)
        return self.to_writer(va, kind, eax=roll)


def stock_amount(site, roll: int = 0) -> int:
    """The game's own amount at a site, `roll` the rand result before it."""
    _va, _stock, form, _kind, amount, _what = site
    if form in ("add eax", "add push"):
        return amount + roll
    if form == "sub ecx":
        return amount - roll
    return amount


ROLLS = {"add eax": 123, "add push": 7, "sub ecx": 456}


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(), "needs unicorn, pefile and the stock executables")
class ScaledByThePopulation(unittest.TestCase):
    def test_every_site_at_25_26_50_51(self) -> None:
        for game in GAMES:
            v = Village(game)
            self.assertEqual(v.installed, 1)
            self.assertEqual(v.p.export("VvfpIslandEventsScaleMode"), 1)
            v.stores(1_000_000, 1_000_000)
            for n in (25, 26, 50, 51, 1, 0, 120):
                v.people(n)
                for site in SITES[game]:
                    roll = ROLLS.get(site[2], 0)
                    with self.subTest(game=game, n=n, site=hex(site[0])):
                        self.assertEqual(v.amount(site, roll), stock_amount(site, roll) * k_of(n))
                        self.assertEqual(v.p.export("VvfpIslandEventsScaleLastFactor"), k_of(n))

    def test_babies_being_carried_count(self) -> None:
        for game in GAMES:
            v = Village(game)
            v.stores(1_000_000, 1_000_000)
            site = next(s for s in SITES[game] if s[2] in ("push", "esp", "setter"))
            v.people(24, carried=1)                 # 25: still 1
            self.assertEqual(v.amount(site), site[4], game)
            v.people(24, carried=2)                 # 26 with twins on the way: 2
            self.assertEqual(v.amount(site), site[4] * 2, game)
            v.people(24, dead=10)                   # bodies are not people
            self.assertEqual(v.amount(site), site[4], game)

    def test_new_believers_heathens_do_not_count(self) -> None:
        v = Village(5)
        v.stores(1_000_000, 1_000_000)
        site = SITES[5][-1]                         # The Strange Nectar: +2,000 tech points
        v.people(30, heathens=40)                   # 30 believers: x2, not x3
        self.assertEqual(v.amount(site), 4000)
        v.people(20, heathens=40)
        self.assertEqual(v.amount(site), 2000)

    def test_a_gain_and_a_loss_in_each_game_reach_the_stores(self) -> None:
        # The Tree of Life: The Calabash Instrument (+3,000 / -2,000 tech points), its real tech writer.
        v = Village(4)
        v.people(51)
        v.stores(0, 10_000)
        v.tail_to_return(0x41585A, ecx=STORES[4][1])
        self.assertEqual(v.tech(), 10_000 + 9_000)
        v.tail_to_return(0x415867, ecx=STORES[4][1])
        self.assertEqual(v.tech(), 19_000 - 6_000)
        # New Believers: Spying on the Heathens (-40 food) and The Straw Hat (+200 food), its real food writer.
        v = Village(5)
        v.people(26)
        v.stores(1000, 0)
        v.tail_to_return(0x415F01, ecx=STORES[5][0])
        self.assertEqual(v.food(), 1000 - 80)
        # A New Home: The Brass Compass, its real tech writer (no loss is in its four encounters).
        v = Village(1)
        v.people(51)
        v.stores(0, 500)
        self.assertEqual(v.to_writer(0x41A367, "tech", eax=1000), 9000)

    def test_a_loss_takes_no_more_than_there_is(self) -> None:
        for game, setter, tail in ((4, 0x414980, 0x415867), (5, 0x414C60, 0x4169A9)):
            v = Village(game)
            v.people(51)
            v.stores(500, 3000)
            # The Mysterious Footprints (food lost): 300 x 3 = 900, clamped to the 500 stored (the {award} shown).
            self.assertEqual(v.setter(setter), 500)
            v.stores(5000, 3000)
            self.assertEqual(v.setter(setter), 900)
            # -2,000 x 3 tech points from 3,000: the writer stops at 0.
            v.stores(5000, 3000)
            v.tail_to_return(tail, ecx=STORES[game][1])
            self.assertEqual(v.tech(), 0)

    def test_a_population_the_game_cannot_count_leaves_the_stock_amount(self) -> None:
        v = Village(1)
        v.people(51)
        v.p.put32(v.encounter + VV1_WORLD, 0)       # no world: the count is not asked
        self.assertEqual(v.to_writer(0x41944F, "food"), 1000)
        self.assertEqual(v.p.export("VvfpIslandEventsScaleLastFactor"), 0)


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(), "needs unicorn, pefile and the stock executables")
class ScaledByTheStores(unittest.TestCase):
    def test_the_flag_is_looked_for_by_full_path_in_the_patchers_folder(self) -> None:
        for game in GAMES:
            on, off = Village(game, stored=True), Village(game)
            self.assertEqual(on.p.export("VvfpIslandEventsScaleMode"), 2)
            self.assertEqual(off.p.export("VvfpIslandEventsScaleMode"), 1)
            self.assertIn(FLAG_PATH, on.asked)

    def test_every_site_gets_a_tenth_of_the_stores(self) -> None:
        for game in GAMES:
            v = Village(game, stored=True)
            v.people(80)                            # the population plays no part
            for food, tech in ((5000, 50_000), (9, 9), (0, 0), (-50, -50), (123_457, 2_000_000)):
                v.stores(food, tech)
                for site in SITES[game]:
                    roll = ROLLS.get(site[2], 0)
                    stock = stock_amount(site, roll)
                    store = food if site[3] == "food" else tech
                    bonus = max(0, store) // 10
                    want = stock + bonus if stock >= 0 else stock - bonus
                    if site[2] == "setter" and ": -" in site[5]:
                        want = min(want, store)     # the setter's own clamp: no more than there is
                    with self.subTest(game=game, food=food, site=hex(site[0])):
                        self.assertEqual(v.amount(site, roll), want)

    def test_the_examples_in_the_description(self) -> None:
        v = Village(4, stored=True)
        v.stores(5000, 0)
        self.assertEqual(v.setter(0x414930), 800)    # +300 food with 5,000 stored
        self.assertEqual(v.setter(0x414980), 800)    # -300 food: a loss of 800 (5,000 stored covers it)
        v.stores(700, 0)
        self.assertEqual(v.setter(0x414980), 370)    # 300 + 70
        v.stores(100, 0)
        self.assertEqual(v.setter(0x414980), 100)    # 310, then the setter's rule: no more than there is
        v.stores(10_000, 0)
        self.assertEqual(v.setter(0x414730), 1100)   # The Creeping Mold


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(), "needs unicorn, pefile and the stock executables")
class EveryBuild(unittest.TestCase):
    def others(self, game: int) -> list[str]:
        return [p.id for p in patcher.load_public_fun_patches()
                if p.game_id == f"vv{game}" and p.id not in patcher.ALTERNATIVE_FUN_PATCH_IDS
                and p.id not in patcher.EXPERIMENTAL_FUN_PATCH_IDS
                and p.id not in (population_id(game), stored_id(game))]

    def render(self, game: int, mode: str, ids) -> bytes:
        build = next(b for b in patcher.load_builds() if b.id == f"vv{game}")
        data, _ = patcher.render_patched_bytes(STOCK[game], build, mode, list(ids))
        return bytes(data)

    def assert_sites_stock(self, game: int, exe: bytes) -> None:
        pe = pefile.PE(data=exe, fast_load=True)
        image = pe.get_memory_mapped_image()
        for va, stock, *_ in SITES[game]:
            self.assertEqual(image[va - 0x400000:va - 0x400000 + len(stock) // 2].hex().upper(), stock, hex(va))

    def test_with_every_other_patch_in_every_mode(self) -> None:
        for game in GAMES:
            others = self.others(game)
            self.assertGreater(len(others), 10)
            for mode in MODES:
                for ids in (others + [population_id(game)],
                            [i for i in others if i != f"vv{game}_classic_vv_difficulty"] + [stored_id(game)]):
                    with self.subTest(game=game, mode=mode, last=ids[-1]):
                        exe = self.render(game, mode, patcher.resolve_fun_patch_ids(ids, game_id=f"vv{game}"))
                        self.assert_sites_stock(game, exe)
                        v = Village(game, stored=ids[-1] == stored_id(game), exe=exe)
                        self.assertEqual(v.installed, 1)

    def test_with_256_villagers(self) -> None:
        for game in (4, 5):
            ids = self.others(game) + [f"vv{game}_population_256", population_id(game)]
            exe = self.render(game, "stock", patcher.resolve_fun_patch_ids(ids, game_id=f"vv{game}"))
            self.assert_sites_stock(game, exe)
            v = Village(game, exe=exe, manager=0x800000)
            self.assertEqual(v.installed, 1)
            v.stores(1_000_000, 1_000_000)
            for n in (25, 26, 50, 51, 200):
                v.people(n)
                site = next(s for s in SITES[game] if s[2] == "setter" and ": +" in s[5])
                with self.subTest(game=game, n=n):
                    self.assertEqual(v.amount(site), site[4] * k_of(n))

    def test_the_tree_of_life_origins_tail_jumps_keep_the_scaled_amount(self) -> None:
        ids = with_requirements(4, ["vv4_enable_origins_exclusive_features", population_id(4)])
        exe = self.render(4, "stock", ids)
        self.assert_sites_stock(4, exe)
        v = Village(4, exe=exe)
        v.people(51)
        v.stores(1_000_000, 1_000_000)
        # Origins' cave runs the writer's first two instructions itself (push esi / mov esi, [esp+8]) and goes on
        # at the writer + 5, past the doublers' hook: the amount it carries is in esi there.
        for site in SITES[4]:
            if site[2] == "esp":
                with self.subTest(site=hex(site[0])):
                    writer = WRITERS[4][0 if site[3] == "food" else 1]
                    v.to_writer(site[0], site[3], until=writer + 5)
                    self.assertEqual(s32(v.p.reg("esi")), site[4] * 3)

    def test_a_site_that_is_not_stock_installs_nothing(self) -> None:
        for game in GAMES:
            data = bytearray(STOCK[game].read_bytes())
            pe = pefile.PE(data=bytes(data), fast_load=True)
            va = SITES[game][-1][0]
            off = pe.get_offset_from_rva(va - 0x400000)
            data[off] ^= 0xFF
            v = Village(game, exe=bytes(data))
            self.assertEqual(v.installed, 0)
            for other_va, stock, *_ in SITES[game][:-1]:
                self.assertEqual(v.p.read(other_va, len(stock) // 2).hex().upper(), stock)

    def test_another_game_installs_nothing(self) -> None:
        p = Process(STOCK[4].read_bytes(), DLL)
        p.export("VvfpStartup", 2, 0)
        self.assertEqual(p.export("VvfpIslandEventsScaleInstalled"), 0)
        self.assertEqual(p.read(0x414930, 7).hex().upper(), "C741082C010000")


if __name__ == "__main__":
    unittest.main()
