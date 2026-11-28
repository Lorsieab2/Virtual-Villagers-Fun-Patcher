"""New Believers: Heathen Tribe Expansion and Evolution, workstream W-A ("VVFP Heathen Aging.dll" with the row's flag
"VVFP Heathen Tribe Evolution.txt"; docs/heathen-tribe-expansion-design.md and the owner's decisions of 2026-11-26 in
docs/heathen-tribe-expansion-decisions.md; the shared names in native/shared/heathen_evo.h).

EMULATED on the stock New Believers executable, as tests/test_vv5_heathen_aging.py (whose Village this extends): the
game's own age credit, life tick, believer count 0x4713F0 and room-check bytes run; the game routines the Heathen
path calls are stood in for.  The companion's own numbers (its xorshift, never the game's rand) are steered by
writing its seed: the seed is found in the DLL's data, and `first_output` searches for a first output whose
successive outputs meet each roll a test needs (the xorshift is inverted to give that first output).

What each test proves: the slider rates (exact roll boundaries for 0.1x, 1x, 10x and the tribe's W), arrivals before
and after The Last Heathen, groups and couples with children, couples and the kin test, litters, the mask mix of
arrivals and newborns, roles (for show and real), the record cap in all three population modes and the 256 build,
the Life bridge, the log calls (the Conception-record fix, Couple formed, Took the role, Arrived words), the couples
file, and the refusals."""
from __future__ import annotations

import random
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from test_vv5_heathen_aging import (  # noqa: E402
    AGE, BODY, DLL, FACTION, FATHER_BODY, FATHER_HEAD, FATHER_NAME, HEAD, HEALTH, LITTER, MOTHER_BODY, MOTHER_HEAD,
    MOTHER_NAME, NAME, ORANGE, PREGNANT, PRESENT, PROCESSED, RED, ROLE, SAVE_MANAGER_WORD, SEX, SKILLS, SLOT_FIELD,
    STRIDE, TRIBE, TWINS, Village, _due_to_die, _identity, _skip,
)

EVO = "VVFP Heathen Tribe Evolution.txt"
BIRTHS_FILE, ARRIVALS_FILE, OPTIONS_FILE = ("VVFP Heathen Tribe Births.txt", "VVFP Heathen Arrivals.txt",
                                            "VVFP Heathen Options.txt")
SICK = 0x1C48
LIFE, STORY = 0x0B400000, 0x0B500000
M32 = 0xFFFFFFFF
BELIEVERS, COLLECTION, DEMAND = 0x4713F0, 0x414690, 0x4944C0
EMBRACE_TEXTS, EMBRACE_TEXT, EMBRACE_BEHAVIOUR, EMBRACE_POSITION = 0x450D40, 0x4506D0, 0x465580, 0x466350
JOB_SKILL = 0x1C74
CAP_BONUS, CAP_BASE, DETOUR = 0x472C04, 0x472C49, 0x494500


# ---- the companion's own numbers ------------------------------------------------------------------------------
def xs(x: int) -> int:
    x ^= (x << 13) & M32
    x ^= x >> 17
    x ^= (x << 5) & M32
    return x


def _inv_shl(y: int, s: int) -> int:
    r = y
    for _ in range(32):
        r = (y ^ (r << s)) & M32
    return r


def _inv_shr(y: int, s: int) -> int:
    r = y
    for _ in range(32):
        r = y ^ (r >> s)
    return r


def unxs(x: int) -> int:
    """The seed whose next output is x."""
    return _inv_shl(_inv_shr(_inv_shl(x, 5), 17), 13)


def first_output(*rolls: tuple[int, object]) -> int:
    """A first output whose successive outputs meet each (modulus, wanted) -- wanted an int, or a predicate."""
    rng = random.Random(20261126)
    modulus0, wanted0 = rolls[0]
    for k in range(5_000_000):
        if callable(wanted0):
            x = rng.getrandbits(32) or 1
        else:                                            # every output that meets an exact first roll, in turn
            x = wanted0 + modulus0 * (k + 1 + rng.randrange(1000))
            if x > M32:
                break
        y, ok = x, True
        for modulus, wanted in rolls:
            r = y % modulus
            if not (wanted(r) if callable(wanted) else r == wanted):
                ok = False
                break
            y = xs(y)
        if ok:
            return x
    raise AssertionError("no seed found")


def _seed_va() -> int:
    import pefile
    pe = pefile.PE(str(DLL))
    found = []
    for s in pe.sections:
        if s.Characteristics & 0x80000000:                      # writable: the initial seed 0x6D2B79F5
            data = s.get_data()
            at = data.find(struct.pack("<I", 0x6D2B79F5))
            while at >= 0:
                found.append(pe.OPTIONAL_HEADER.ImageBase + s.VirtualAddress + at)
                at = data.find(struct.pack("<I", 0x6D2B79F5), at + 1)
    assert len(found) == 1, found
    return found[0]


class Evo(Village):
    """A village with the expansion's row (and its slider and options files) and the export stand-ins."""

    def __init__(self, extra: tuple[str, ...] = (), *, births: str | None = None, arrivals: str | None = None,
                 options: str | None = None, collections: tuple[int, ...] = (), flags: tuple[str, ...] | None = None,
                 life: bool = False, story: bool = False, slot: int = 1, **kw):
        self.settings: dict[str, bytes] = {}
        for name, text in ((BIRTHS_FILE, births), (ARRIVALS_FILE, arrivals), (OPTIONS_FILE, options)):
            if text is not None:
                self.settings[name] = text.encode()
        self.collections = set(collections)
        self.life_on, self.story_on = life, story
        self.life_answer = 0
        # The embraces' game calls (heathen_tribe.inc): each record's spot, the behaviours given, the look steps.
        self.spots: dict[int, tuple[int, int]] = {}
        self.behaviours: list[tuple[int, int]] = []
        self.steps: list[tuple[str, int, tuple]] = []
        self.litter_answer = 1
        self.life_calls: list[tuple[int, int]] = []
        self.conceptions: list[tuple[int, int, int]] = []     # (mother, father, litter at the call)
        self.couples_logged: list[tuple[int, int]] = []
        self.roles_logged: list[tuple[int, int]] = []
        self.titles: list[tuple[int, str]] = []
        super().__init__(flags if flags is not None else (EVO,) + tuple(extra), **kw)
        if slot:
            self.save_manager = self.alloc(SLOT_FIELD + 0x10)
            self.put32(SAVE_MANAGER_WORD, self.save_manager)
            self.put32(self.save_manager + SLOT_FIELD, slot)

    def before_start(self) -> None:
        self.api_handlers["CreateFileW"] = self._create_file_w
        self.api_handlers["GetCurrentProcessId"] = lambda p: (0x1234, 0)
        self.stub(COLLECTION, lambda p: (int(p.arg(0) in self.collections), 4))
        stubs = self.alloc(0x70)
        self.retired_logged: list[tuple[int, int]] = []
        self.cod_exports["VvfpCauseHeathenRetired"] = stubs + 0x50
        self.stub(stubs + 0x50, lambda p: (self.retired_logged.append((p.arg(1), p.arg(2))), (0, 12))[1])
        self.parentage_exports["WriteParentageRecordWithFather"] = stubs
        self.parentage_exports["WriteParentageHeathenCouple"] = stubs + 0x10
        self.cod_exports["VvfpCauseHeathenRole"] = stubs + 0x20
        self.life_export = stubs + 0x30
        self.title_export = stubs + 0x40
        self.stub(stubs, self._conception)
        self.stub(stubs + 0x10, lambda p: (self.couples_logged.append((p.arg(2), p.arg(3))), (1, 16))[1])
        self.stub(stubs + 0x20, lambda p: (self.roles_logged.append((p.arg(1), p.arg(2))), (0, 12))[1])
        self.stub(stubs + 0x30, self._life)
        self.stub(stubs + 0x40, lambda p: (self.titles.append((p.arg(1), p.cstring(p.arg(2)) if p.arg(2) else "")),
                                           (1, 12))[1])
        words = self.alloc(0x20)
        self.write(words, b"Embracing\0")
        self.stub(EMBRACE_TEXTS, lambda p: (0x0BA00000, 0))
        self.stub(EMBRACE_TEXT, lambda p: (words, 4))
        self.stub(EMBRACE_BEHAVIOUR, lambda p: (self.behaviours.append((p.reg("ecx"), p.arg(0))), (0, 8))[1])
        self.stub(EMBRACE_POSITION, self._spot)
        for name, va, pops in (("walk", 0x4745A0, 0x10), ("gesture", 0x474450, 8), ("wait", 0x4747E0, 4),
                               ("start", 0x473590, 0)):
            self.stub(va, lambda p, name=name, pops=pops: (
                self.steps.append((name, p.reg("ecx"), tuple(p.arg(i) for i in range(pops // 4)))), (0, pops))[1])

        conceive = self._conceive

        def conceive_with_litter(p):              # the game's routine sets the litter by Medicine: as asked here
            answer = conceive(p)
            p.put32(p.reg("ecx") + LITTER, self.litter_answer)
            return answer
        self.stub(0x465E00, conceive_with_litter)

    def _spot(self, p):
        record = p.reg("ecx")
        x, y = self.spots.get(record, (100, 100))
        p.put32(p.arg(0), x & M32)
        p.put32(p.arg(0) + 4, y & M32)
        return p.arg(0), 4

    def _conception(self, p):
        mother = p.arg(2)
        self.conceptions.append((mother, p.arg(3), self.i32(mother, LITTER)))
        return 1, 16

    def _life(self, p):
        self.life_calls.append((p.arg(0), p.arg(1)))
        return self.life_answer, 8

    def _create_file_w(self, p):
        name = p.wstring(p.arg(0))
        for leaf, data in self.settings.items():
            if name.endswith(leaf):
                self.files[name] = data
                handle = 0x900 + 4 * len(self.handles)
                self.handles[handle] = [name, 0]
                return handle, 28
        self.last_error = 2
        return 0xFFFFFFFF, 28

    def _module(self, p):
        name = p.arg(0)
        if name and self.life_on and p.cstring(name) == "VVFP Heathen Life.dll":
            return LIFE, 4
        if name and self.story_on and p.cstring(name) == "VVFP Story Upgrades.dll":
            return STORY, 4
        return super()._module(p)

    def _proc(self, p):
        if p.arg(0) == LIFE:
            return (self.life_export if p.cstring(p.arg(1)) == "VvfpHeathenLifeUnit" else 0), 8
        if p.arg(0) == STORY:
            return (self.title_export if p.cstring(p.arg(1)) == "VvfpStorySetCustomTitle" else 0), 8
        return super()._proc(p)

    # ---- helpers ----------------------------------------------------------------------------------------
    def seed(self, first: int) -> None:
        self.put32(SEED_VA, unxs(first))

    def couple_of(self, index: int) -> int:
        return struct.unpack("<i", struct.pack("<I", self.export("VvfpHeathenAgingCoupleOf", index)))[0]

    def look(self, index: int = 0) -> None:
        """One age credit (no units): the throttled look -- the files, the couples, the arrivals' clock."""
        self.credit(self.record(index), 0)

    def known_entries(self) -> list[tuple[int, int]]:
        path = next(k for k in self.files if k.endswith("Heathen Aging - Save 1.dat"))
        data = self.files[path]
        count = struct.unpack_from("<I", data, 12)[0]
        return [struct.unpack_from("<II", data, 20 + 8 * k) for k in range(count)]


class Evo256(Evo):
    """The "256 Villagers (Experimental)" build's table: the manager at 0x800000 with 256 records, as the two
    immediates vv5_villager_table.h reads say (the believer count stood in for: the stock one walks 150)."""
    manager, slots = 0x800000, 256

    def edit_exe(self, exe: bytearray) -> None:
        import pefile
        pe = pefile.PE(data=bytes(exe))
        at = pe.get_offset_from_rva(0x94051)
        exe[at:at + 4] = struct.pack("<I", 0x800000)
        at = pe.get_offset_from_rva(0x1F1E6)
        exe[at:at + 4] = struct.pack("<I", 256)

    def before_start(self) -> None:
        self.mu.mem_map(0x800000, (0x48 + 256 * STRIDE + 0x1000 + 0xFFF) & ~0xFFF)
        super().before_start()
        self.stub(BELIEVERS, lambda p: (self.believers(), 0))

    def believers(self) -> int:
        n = 0
        for i in range(256):
            r = self.record(i)
            if self.read(r + PRESENT, 1) != b"\0" and self.read(r + FACTION, 1) == b"\0" and self.i32(r, HEALTH) > 0:
                n += 1 + (self.i32(r, LITTER) if self.i32(r, PREGNANT) else 0)
        return n


SEED_VA = _seed_va() if _skip() is None else 0


def _detour(v: Evo, base: int, *, fixed_bonus: int | None = None) -> None:
    """The population rows' room check in this emulated image (data/builds.json, data/vv5_population_256_feature.json):
    0x472C49 `jmp 0x494500`; there `add esi, base; call 0x4944C0` (total demand, stood in for); Immediate Fixed's
    `mov esi, bonus` at 0x472C04."""
    v.write(CAP_BASE, b"\xE9" + struct.pack("<i", DETOUR - (CAP_BASE + 5)) + b"\x90\x90")
    v.write(DETOUR, b"\x81\xC6" + struct.pack("<i", base) + b"\xE8" + struct.pack("<i", DEMAND - (DETOUR + 11)))
    if fixed_bonus is not None:
        v.write(CAP_BONUS, b"\xBE" + struct.pack("<i", fixed_bonus) + b"\x90" * 5)

    def demand(p):
        n = 0
        for i in range(v.slots):
            r = v.record(i)
            if v.read(r + PRESENT, 1) != b"\0":
                n += 1 + (v.i32(r, LITTER) if v.i32(r, PREGNANT) else 0)
        return n, 0
    v.stub(DEMAND, demand)


def _clock(v: Evo, units: int = 1) -> None:
    """The village's clock moves `units` (a look first, so the clock record is known): at most one new couple."""
    first = next(i for i in range(v.slots) if v.read(v.record(i) + PRESENT, 1) != b"\0")
    v.look(first)
    v.credit(v.record(first), units)


def _couple(v: Evo, man_i: int = 1, woman_i: int = 2, **kw) -> tuple[int, int]:
    man = v.villager(man_i, heathen=True, sex=0, name=kw.pop("man_name", "Kalo"))
    woman = v.villager(woman_i, heathen=True, sex=1, name=kw.pop("woman_name", "Mele"))
    _clock(v)                                          # the clock moves: they pair
    return man, woman


def _preset(v: Evo, pairs: list[tuple[int, int]]) -> None:
    """The slot's couples file, as a save that already had these couples."""
    path = ("C:\\Docs\\LDW\\Game\\Virtual Villagers Fun Patcher\\Save 1\\Data\\Heathen Couples\\"
            "Heathen Couples - Save 1.dat")
    v.files[path] = struct.pack("<5I", 0x31434856, 1, 5, len(pairs), 1) + b"".join(
        struct.pack("<4I", _identity(v, v.record(a)), _identity(v, v.record(b)), 600, 0) for a, b in pairs)


def _force_arrival(v: Evo, *rolls, tenths: int = 100, clock: int = 0) -> list[int]:
    """One arrival roll that succeeds, then `rolls`: the records it made."""
    v.look(clock)                                       # the clock record is known from this look on
    before = len(v.created)
    v.seed(first_output((4800, lambda r: r < tenths), *rolls))
    v.credit(v.record(clock), 1)                        # one unit on the clock: one roll
    return [i for i, _ in v.created[before:]]


SINGLE = ((100, lambda r: r < 40), (2, lambda r: True), (6, lambda r: r != 0))
FOUR_AS_A_COUPLE = ((100, lambda r: r >= 90), (2, 0))


@unittest.skipIf(_skip(), _skip() or "")
class Installs(unittest.TestCase):
    def test_the_rows_flag_alone_installs_and_folds_the_three_rows(self):
        v = Evo()
        self.assertEqual(v.installed, 1)
        self.assertEqual(v.export("VvfpHeathenAgingEvolution"), 1)
        camp = v.villager(1, heathen=True)
        v.credit(camp, 3)
        self.assertEqual(v.i32(camp, AGE), 603, "every Heathen ages (Heathen Tribe Ages)")
        v.villager(9, heathen=True, name="Other")
        self.assertEqual(v.export("VvfpHeathenAgingEventGone", 5, 1, 0, 5), 2,
                         "island events carry Heathens, and every Heathen leaves a skeleton")
        self.assertEqual(v.read(camp + PRESENT, 1), b"\x01")

    def test_old_flags_still_install_without_the_expansion(self):
        v = Evo(flags=(TRIBE,))
        self.assertEqual((v.installed, v.export("VvfpHeathenAgingEvolution")), (1, 0))
        self.assertEqual(v.couple_of(1), -1)

    def test_stock_bytes_refused_all_or_none(self):
        class Altered(Evo):
            def edit_exe(self, exe):
                import pefile
                at = pefile.PE(data=bytes(exe)).get_offset_from_rva(0x72CB7)
                exe[at] = 0x90
        v = Altered()
        self.assertEqual(v.installed, 0, "a site not holding the stock bytes: nothing installed")
        camp = v.villager(1, heathen=True)
        v.credit(camp, 3)
        self.assertEqual(v.i32(camp, AGE), 600)
        self.assertEqual(v.read(0x470077, 2), b"\x38\x9E", "the other site left as it was")


@unittest.skipIf(_skip(), _skip() or "")
class Embraces(unittest.TestCase):
    """The owner, 2026-11-27/28: Heathen couples (and a Heathen titled Parent with any eligible Heathen) walk together
    and embrace as believers do, and conceive through the embrace -- about 1-2 conceptions for the whole tribe every
    6-12 hours on Normal at 1x: one roll a unit of the village's clock, 1 in 600 / t (t the births slider's tenths),
    after the unit's arrival roll (1 in 4,800)."""

    def _start(self, births: str | None, roll, **kw) -> tuple[Evo, int, int]:
        v = Evo(births=births, **kw)
        man, woman = _couple(v)
        if "tribe_max" in (kw.get("options") or ""):            # the tribe size's rolls (heathen_evo.h section 2)
            rolls = ((1200000, lambda r: True), (6000000, lambda r: r < 10000), (2, 1))
        else:
            rolls = ((4800, lambda r: True), (600, roll), (2, 1))
        v.seed(first_output(*rolls))                             # she seeks him
        v.behaviours.clear()
        v.steps.clear()
        v.rand_calls.clear()
        v.credit(man, 1)                                  # one unit on the clock (the man: record 1, the first)
        return v, man, woman

    def test_the_roll_boundaries_at_0_1x_1x_and_10x(self):
        for births, tenths in (("0.1", 1), ("1", 10), (None, 10), ("0.5", 5), ("10", 100), ("25", 100)):
            with self.subTest(births=births):
                v, man, woman = self._start(births, tenths - 1)
                self.assertEqual(v.behaviours, [(man, 6)], "below t: an embrace -- the partner waits (behaviour 6)")
                self.assertEqual(v.rand_calls, [], "the game's rand is never drawn for the roll")
                v, man, woman = self._start(births, tenths)
                self.assertEqual(v.behaviours, [], "t and above: none")

    def test_the_seeker_walks_to_the_partner_with_the_believers_embrace_look(self):
        v, man, woman = self._start(None, 0)
        self.assertEqual(v.cstring(woman + 0x1D14), "Embracing")
        walks = [s for s in v.steps if s[0] == "walk"]
        self.assertEqual([(who,) + args for _n, who, args in walks], [(woman, 100, 110, 300, 0)],
                         "0x46CCF9: to the partner's spot +10 down, distance 300")
        self.assertIn(("gesture", woman, (1, 0)), v.steps, "0x45D03F: gesture 1 of animation 0")
        self.assertIn(("start", woman, ()), v.steps)
        self.assertEqual(v.conceived, [], "no conception before they meet")

    def test_they_meet_conceive_and_embrace_where_they_stand_without_the_love_shack(self):
        v, man, woman = self._start(None, 0)
        v.spots[man] = v.spots[woman] = (400, 400)
        v.steps.clear()
        v.look(1)
        carrier, args = v.conceived[0]
        self.assertEqual((carrier, v.cstring(args[3]), args[6]), (woman, "Kalo", 1), "forced, the man the father")
        self.assertEqual(v.u32(TWINS), 0, "the statistics' twins put back")
        self.assertEqual(v.conceptions, [(woman, man, 1)], "the Conception record, the litter already set")
        self.assertIn(("gesture", man, (1, 0)), v.steps)
        self.assertIn(("gesture", woman, (1, 0)), v.steps)
        self.assertEqual([b for _r, b in v.behaviours if b == 7], [], "no Love Shack yet")

    def test_with_the_love_shack_both_go_inside(self):
        v, man, woman = self._start(None, 0)
        v.solve(23)
        v.spots[man] = v.spots[woman] = (400, 400)
        v.behaviours.clear()
        v.look(1)
        self.assertEqual(sorted(v.behaviours), sorted([(man, 7), (woman, 7)]), "0x468B50: behaviour 7 for both")
        self.assertEqual(len(v.conceived), 1)

    def test_an_embrace_that_never_meets_is_given_up(self):
        v, man, woman = self._start(None, 0)
        v.spots[man], v.spots[woman] = (100, 100), (900, 900)
        v.seed(first_output(*([(4800, lambda r: True), (600, lambda r: r >= 10)] * 5)))
        for _ in range(5):
            v.credit(man, 1)
        self.assertEqual(v.conceived, [])
        v.spots[woman] = (100, 100)
        v.look(1)
        self.assertEqual(v.conceived, [], "given up after 3 units: no conception when they meet later")

    def test_the_load_time_catch_up_conceives_at_once(self):
        v = Evo()
        man, woman = _couple(v)
        v.seed(first_output((4800, lambda r: True), (600, 0), (2, 1)))
        v.behaviours.clear()
        v.credit(man, 30)                                 # one look of 30 units: the catch-up
        self.assertEqual(len(v.conceived), 1)
        self.assertEqual(v.behaviours, [], "no walk in the catch-up")

    def test_the_baby_skill_is_0x467d20s(self):
        v, man, woman = self._start(None, 0)
        for k, value in enumerate((10.0, 60.0, 5.0, 0.0, 0.0, 0.0)):     # her best: Parenting
            v.write(woman + SKILLS + 4 * k, struct.pack("<f", value))
        for k, value in enumerate((0.0, 0.0, 0.0, 70.0, 0.0, 0.0)):      # his: Research
            v.write(man + SKILLS + 4 * k, struct.pack("<f", value))
        v.spots[man] = v.spots[woman] = (1, 1)
        v.seed(first_output((50, 7), (3, 2)))
        v.look(1)
        _carrier, args = v.conceived[0]
        self.assertEqual((args[1], args[2]), (1, 7), "her best skill (1 in 50 his), value rand(3) + 5")

    def test_births_go_on_after_the_last_heathen(self):
        v, man, woman = self._start(None, 0)
        v.solve(25)
        v.spots[man] = v.spots[woman] = (1, 1)
        v.look(1)
        self.assertEqual(len(v.conceived), 1, "decision 2: births continue after The Last Heathen")
        at = v.i32(woman, PREGNANT)
        v.put32(woman + AGE, at + 42)
        v.seed(first_output((100, 50)))
        v.rand_answers.extend([0, 0, 1])
        v.life_tick()
        self.assertEqual(len(v.created), 1, "and the baby is born")

    def test_no_partner_no_conception_and_never_the_old_roll(self):
        v = Evo()
        woman = v.villager(2, heathen=True, sex=1, name="Mele")
        v.look(2)
        v.seed(first_output((4800, lambda r: True), (600, 0)))
        v.credit(woman, 1)
        v.put32(woman + AGE, v.i32(woman, AGE) + 1)
        v.life_tick()
        self.assertEqual((v.conceived, v.behaviours), ([], []))

    def test_a_heathen_titled_parent_embraces_an_eligible_heathen_who_is_not_their_partner(self):
        v = Evo()
        parent = v.villager(1, heathen=True, sex=0, name="Tama")
        v.put32(parent + JOB_SKILL, M32)                                  # no job ticked
        for k, value in enumerate((10.0, 40.0, 0.0, 0.0, 0.0, 0.0)):     # the title says Parent
            v.write(parent + SKILLS + 4 * k, struct.pack("<f", value))
        other = v.villager(2, heathen=True, sex=1, name="Lani")
        kin = v.villager(3, heathen=True, sex=1, name="Sina")
        v.write(kin + FATHER_NAME, b"Tama\0")                            # his daughter: kin
        v.put32(kin + FATHER_HEAD, v.i32(parent, HEAD))
        v.put32(kin + FATHER_BODY, v.i32(parent, BODY))
        v.villager(4, heathen=True, sex=0, name="Ioane")
        v.villager(5, heathen=True, sex=0, name="Rua")
        _preset(v, [(2, 4), (3, 5)])                      # both women in couples: "any eligible" candidate
        v.look(1)
        # the rolls: arrival, conception, each couple's seeker (two), then the pick -- the first pair, his
        v.seed(first_output((4800, lambda r: True), (600, 0), (2, 1), (2, 1), (3, 0)))
        v.credit(parent, 1)
        self.assertEqual(v.behaviours[0], (other, 6), "the one eligible candidate waits; never his kin")
        self.assertEqual(v.cstring(parent + 0x1D14), "Embracing")

    def test_a_parent_title_needs_parenting_highest_and_20(self):
        # 0x4755C0: a skill wins when above the best so far cut to a whole number (25.5 after 25.9: the best is 25)
        for skills, job, embraces in (((10.0, 19.0, 0, 0, 0, 0), -1, False), ((30.0, 25.0, 0, 0, 0, 0), -1, False),
                                      ((25.9, 25.0, 0, 0, 0, 0), -1, False), ((25.9, 25.5, 0, 0, 0, 0), -1, True),
                                      ((10.0, 40.0, 0, 0, 0, 0), 0, False), ((40.0, 30.0, 0, 0, 0, 0), 1, True)):
            with self.subTest(skills=skills, job=job):
                v = Evo(flags=(EVO,))
                parent = v.villager(1, heathen=True, sex=0, name="Tama")
                v.put32(parent + JOB_SKILL, job & M32)                    # the ticked job's skill wins
                for k, value in enumerate(skills):
                    v.write(parent + SKILLS + 4 * k, struct.pack("<f", float(value)))
                v.villager(2, heathen=True, sex=1, name="Lani")
                v.villager(4, heathen=True, sex=0, name="Ioane")
                _preset(v, [(2, 4)])
                v.look(1)
                v.seed(first_output((4800, lambda r: True), (600, 0), (2, 1), (2, 0)))
                v.credit(parent, 1)
                self.assertEqual(v.cstring(parent + 0x1D14) == "Embracing", embraces)

    def test_a_puzzle_heathen_embraces_only_once_the_puzzle_is_solved(self):
        for solved in (False, True):
            with self.subTest(solved=solved):
                v = Evo()
                if solved:
                    v.solve(16)
                man = v.villager(1, heathen=True, sex=0, name="Chief", role=13)
                woman = v.villager(2, heathen=True, sex=1, name="Mele")
                _preset(v, [(2, 1)])
                v.look(1)
                v.seed(first_output((4800, lambda r: True), (600, 0), (2, 1)))
                v.credit(man, 1)
                self.assertEqual(bool(v.behaviours), solved)

    def test_a_sick_or_held_heathen_is_never_asked(self):
        for offset in (SICK, 0x1CD6):
            with self.subTest(offset=hex(offset)):
                v = Evo()
                man, woman = _couple(v)
                v.write(man + offset, b"\x01")
                v.seed(first_output((4800, lambda r: True), (600, 0), (2, 1)))
                v.credit(man, 1)
                self.assertEqual(v.behaviours, [])


@unittest.skipIf(_skip(), _skip() or "")
class Litters(unittest.TestCase):
    """The believers' own litter (the owner: "medicine tech applies"): the game's conception 0x465E00 sets it by
    Medicine (single below Medicine 3; 5.25% twins, 1.75% triplets at 3); the companion keeps it, as many as fit."""

    def _litter(self, game_litter: int, **kw) -> tuple[Evo, int, int]:
        v, man, woman = Embraces._start(self, None, 0, **kw)
        v.litter_answer = game_litter
        v.spots[man] = v.spots[woman] = (1, 1)
        v.look(1)
        return v, man, woman

    def test_the_games_litter_is_kept(self):
        for litter in (1, 2, 3):
            with self.subTest(litter=litter):
                v, _man, woman = self._litter(litter)
                self.assertEqual(v.i32(woman, LITTER), litter)
                self.assertEqual(v.conceptions[0][2], litter)

    def test_the_tribe_size_trims_a_litter_to_what_fits(self):
        v2, man, woman = Embraces._start(self, None, 0, options="tribe_max=10\n")
        for i in range(10, 17):
            v2.villager(i, heathen=True, age=100, name=f"Kid{i}")
        v2.litter_answer = 3
        v2.spots[man] = v2.spots[woman] = (1, 1)
        v2.look(1)
        self.assertEqual(v2.i32(woman, LITTER), 1, "9 in the camp, a limit of 10: one baby")

    def test_triplets_are_born_with_their_own_masks(self):
        """Decision 7: each newborn 90% blue, 7% orange, 3% red -- its own, not a parent's, within the Rascal caps."""
        v, man, woman = self._litter(3)
        v.write(woman + RED, b"\x01")                     # a red mother: no matter
        at = v.i32(woman, PREGNANT)
        v.put32(woman + AGE, at + 42)
        v.seed(first_output((100, 5), (100, 8), (100, 50)))
        v.rand_answers.extend([0, 0, 1] * 3)
        v.life_tick()
        self.assertEqual(len(v.created), 3)
        masks = [(args[5], args[6]) for _, args in v.created]
        self.assertEqual(masks, [(1, 0), (0, 1), (0, 0)], "orange, red, blue")
        for index, _ in v.created:
            baby = v.record(index)
            self.assertEqual((v.cstring(baby + FATHER_NAME), v.cstring(baby + MOTHER_NAME)), ("Kalo", "Mele"))


@unittest.skipIf(_skip(), _skip() or "")
class Couples(unittest.TestCase):
    """Decision 15: a woman and a man pair for life; kin never pair; the couple ends at a death or a conversion."""

    def test_a_pair_forms_is_logged_and_kept_in_the_file(self):
        v = Evo()
        man, woman = _couple(v)
        self.assertEqual((v.couple_of(1), v.couple_of(2)), (2, 1))
        self.assertEqual(v.couples_logged, [(woman, man)], "a Couple formed record")
        v.look(1)
        path = next(k for k in v.files if k.endswith("\\Data\\Heathen Couples\\Heathen Couples - Save 1.dat"))
        data = v.files[path]
        self.assertEqual(struct.unpack_from("<5I", data), (0x31434856, 1, 5, 1, 1))
        self.assertEqual(struct.unpack_from("<2I", data, 20), (_identity(v, woman), _identity(v, man)))
        self.assertEqual(struct.unpack_from("<I", data, 32)[0], 0, "active")

    def test_the_couple_is_read_back_from_the_file(self):
        v = Evo()
        for i, name in ((1, "Aa"), (2, "Bb"), (3, "Cc")):
            v.villager(i, heathen=True, sex=0, name=name)
        woman = v.villager(5, heathen=True, sex=1, name="Mele")
        path = ("C:\\Docs\\LDW\\Game\\Virtual Villagers Fun Patcher\\Save 1\\Data\\Heathen Couples\\"
                "Heathen Couples - Save 1.dat")
        v.files[path] = struct.pack("<5I", 0x31434856, 1, 5, 1, 1) + struct.pack(
            "<4I", _identity(v, woman), _identity(v, v.record(3)), 600, 0)
        v.look(1)                                       # no clock unit: no new couple, only the file's
        self.assertEqual(v.couple_of(5), 3, "the couple in the file")

    def test_kin_never_pair(self):
        def parents(r, father, mother):
            v.write(r + FATHER_NAME, father.encode() + b"\0")
            v.write(r + MOTHER_NAME, mother.encode() + b"\0")
            for off, value in ((FATHER_HEAD, 3), (FATHER_BODY, 4), (MOTHER_HEAD, 5), (MOTHER_BODY, 6)):
                v.put32(r + off, value)
        for case in ("full siblings", "half siblings by the father", "half siblings by the mother", "parent",
                     "siblings with the parents in opposite fields", "half siblings across the fields",
                     "unrelated", "same names, other parents"):
            with self.subTest(case=case):
                v = Evo()
                man = v.villager(1, heathen=True, sex=0, name="Kalo")
                woman = v.villager(2, heathen=True, sex=1, name="Mele")
                if case == "full siblings":
                    parents(man, "Dad", "Mum")
                    parents(woman, "Dad", "Mum")
                elif case == "half siblings by the father":
                    parents(man, "Dad", "Mum")
                    parents(woman, "Dad", "Other")
                elif case == "half siblings by the mother":
                    parents(man, "Dad", "Mum")
                    parents(woman, "Other", "Mum")
                elif case == "parent":
                    parents(woman, "Kalo", "Mum")
                    v.put32(woman + FATHER_HEAD, v.i32(man, HEAD))
                    v.put32(woman + FATHER_BODY, v.i32(man, BODY))
                elif case in ("siblings with the parents in opposite fields", "half siblings across the fields"):
                    # Codex, #883: a same-sex couple's children -- whichever partner carried is the Mother
                    parents(man, "Dad", "Mum")
                    parents(woman, "Mum", "Dad" if case.startswith("siblings") else "Other")
                    v.put32(woman + FATHER_HEAD, 5)          # the man's Mother, in her Father field
                    v.put32(woman + FATHER_BODY, 6)
                    v.put32(woman + MOTHER_HEAD, 3)
                    v.put32(woman + MOTHER_BODY, 4)
                elif case == "same names, other parents":
                    parents(man, "Dad", "Mum")
                    parents(woman, "Dad", "Mum")
                    v.put32(woman + FATHER_HEAD, 9)          # another Dad
                    v.put32(woman + MOTHER_HEAD, 9)          # another Mum
                _clock(v)
                pairs = case in ("unrelated", "same names, other parents")
                self.assertEqual(v.couple_of(2), 1 if pairs else -1)

    def test_a_death_or_a_conversion_ends_the_couple_and_she_pairs_again(self):
        for how in ("death", "conversion"):
            with self.subTest(how=how):
                v = Evo()
                man, woman = _couple(v)
                other = v.villager(3, heathen=True, sex=0, name="Tane")
                if how == "death":
                    v.write(man + PRESENT, b"\x00")
                else:
                    v.write(man + FACTION, b"\x00")
                v.look(2)
                self.assertEqual(v.couple_of(2), -1, "the couple ended")
                _clock(v)
                self.assertEqual(v.couple_of(2), 3, "she pairs again, with the one left")
                _ = other

    def test_a_renamed_partner_stays_her_partner(self):
        v = Evo()
        man, woman = _couple(v)
        v.write(man + NAME, b"Kalo Akikai\0")             # a last name given
        v.look(1)
        v.look(1)
        self.assertEqual(v.couple_of(2), 1)

    def test_never_the_heathen_mommy_and_never_a_child(self):
        v = Evo()
        v.villager(1, heathen=True, sex=0, name="Kalo")
        v.villager(2, heathen=True, sex=1, name="Mommy", role=17)
        v.villager(3, heathen=True, sex=1, name="Girl", age=200)
        _clock(v, 5)
        self.assertEqual((v.couple_of(2), v.couple_of(3)), (-1, -1))

    def test_same_sex_couples_form(self):
        for sex in (0, 1):
            with self.subTest(sex=sex):
                v = Evo()
                v.villager(1, heathen=True, sex=sex, name="Aa")
                v.villager(2, heathen=True, sex=sex, name="Bb")
                _clock(v)
                self.assertEqual(v.couple_of(1), 2, "the owner: same sex yes")

    def test_pairing_is_gradual_one_couple_a_clock_step(self):
        v = Evo()
        for i in range(1, 7):
            v.villager(i, heathen=True, sex=i % 2, name=f"P{i}")
        v.look(1)
        v.look(1)
        self.assertEqual(sum(v.couple_of(i) >= 0 for i in range(1, 7)), 0, "no clock step: nobody pairs")
        _clock(v)
        self.assertEqual(sum(v.couple_of(i) >= 0 for i in range(1, 7)), 2, "one couple")
        _clock(v, 50)
        self.assertEqual(sum(v.couple_of(i) >= 0 for i in range(1, 7)), 4, "one more a look, however far it moved")
        self.assertEqual(len(v.couples_logged), 2)

    def test_a_same_sex_couple_has_a_baby_only_through_an_island_event(self):
        v = Evo()
        a = v.villager(1, heathen=True, sex=0, name="Aa")
        b = v.villager(2, heathen=True, sex=0, name="Bb")
        _clock(v)
        v.seed(first_output((4800, lambda r: True), (600, 0)))
        v.credit(a, 1)                                    # an embrace roll that comes up
        v.look(1)
        self.assertEqual((v.conceived, v.behaviours), ([], []), "no natural conception, no embrace")
        self.assertEqual(v.export("VvfpHeathenAgingEventPregnancy", 5, 1, 0xFFFFFFFF, 1, 0), 1,
                         "an event: any two, the partner the other parent")
        carrier, args = v.conceived[0]
        self.assertEqual((carrier, v.cstring(args[3])), (a, "Bb"))
        self.assertEqual(v.conceptions, [(a, b, 1)])


@unittest.skipIf(_skip(), _skip() or "")
class Arrivals(unittest.TestCase):
    """Decisions 4-5 and 7: 1 in 4,800 / t a unit of the village's clock, a group of 1-4, masks 90/7/3."""

    def test_off_when_zero_or_missing(self):
        for arrivals in ("0", None):
            with self.subTest(arrivals=arrivals):
                v = Evo(arrivals=arrivals)
                v.villager(0, heathen=True)
                v.look(0)
                v.seed(first_output((4800, 0)))
                v.credit(v.record(0), 500)
                self.assertEqual(v.created, [])

    def test_the_roll_boundary_at_1x(self):
        for arrivals, roll, arrives in (("1", 9, True), ("1", 10, False), ("0.1", 0, True), ("0.1", 1, False),
                                        ("10", 99, True), ("10", 100, False)):
            with self.subTest(arrivals=arrivals, roll=roll):
                v = Evo(arrivals=arrivals)
                v.villager(0, heathen=True)
                v.look(0)
                v.seed(first_output((4800, roll), *SINGLE))
                v.rand_calls.clear()
                v.credit(v.record(0), 1)
                self.assertEqual(len(v.created), 1 if arrives else 0)
                self.assertEqual(v.rand_calls, [], "the game's rand is never drawn")

    def test_a_single_arrival_its_words_and_its_role(self):
        v = Evo(arrivals="10")
        v.villager(0, heathen=True)
        made = _force_arrival(v, *SINGLE)
        self.assertEqual(len(made), 1)
        _, args = v.created[0]
        self.assertIn(args[7], (1, 2, 4, 5, 6), "a role of the stock camp's ordinary Heathens")
        self.assertTrue(360 <= args[4] <= 800, "an adult of 18 to 40")
        self.assertTrue(-67 <= v.i32(v.record(made[0]), 0x1CF0) <= -38, "the camp's Faith")
        self.assertEqual(v.arrived, [(made[0], "Arrived at the Heathen camp")])

    def test_a_group_of_four_as_a_couple_with_two_children(self):
        v = Evo(arrivals="10")
        v.villager(0, heathen=True)
        made = _force_arrival(v, *FOUR_AS_A_COUPLE)
        self.assertEqual(len(made), 4)
        mother, father = v.record(made[0]), v.record(made[1])
        self.assertEqual((v.i32(mother, SEX), v.i32(father, SEX)), (1, 0))
        self.assertEqual((v.couple_of(made[0]), v.couple_of(made[1])), (made[1], made[0]))
        self.assertEqual(v.couples_logged, [(mother, father)])
        for index in made[2:]:
            child = v.record(index)
            self.assertTrue(40 <= v.i32(child, AGE) <= 240, "a child of 2 to 12")
            self.assertEqual(v.cstring(child + MOTHER_NAME), v.cstring(mother + NAME))
            self.assertEqual(v.cstring(child + FATHER_NAME), v.cstring(father + NAME))
            self.assertEqual((v.i32(child, MOTHER_HEAD), v.i32(child, FATHER_HEAD)),
                             (v.i32(mother, HEAD), v.i32(father, HEAD)))
        self.assertEqual(v.arrived, [(i, "Arrived at the Heathen camp with 3 others") for i in made])
        v.look(0)
        kept = v.known_entries()
        for index in made[2:]:
            self.assertIn((_identity(v, v.record(index)), 0), kept, "born a Heathen: never a former villager")

    def test_a_group_of_two_strangers(self):
        v = Evo(arrivals="10")
        v.villager(0, heathen=True)
        made = _force_arrival(v, (100, lambda r: 40 <= r < 70), (2, 1))
        self.assertEqual(len(made), 2)
        self.assertEqual(v.arrived, [(i, "Arrived at the Heathen camp with 1 other") for i in made])
        self.assertEqual(v.couples_logged, [])

    def test_the_group_size_option(self):
        v = Evo(arrivals="10", options="# the owner's choice\ngroup_max = 1\n")
        v.villager(0, heathen=True)
        self.assertEqual(len(_force_arrival(v, (100, 95))), 1)

    def test_masks_90_blue_7_orange_3_red(self):
        for roll, mask in ((0, (1, 0)), (6, (1, 0)), (7, (0, 1)), (9, (0, 1)), (10, (0, 0)), (99, (0, 0))):
            with self.subTest(roll=roll):
                v = Evo(arrivals="10")
                v.villager(0, heathen=True)
                _force_arrival(v, *SINGLE, (100, roll))
                self.assertEqual(tuple(v.created[0][1][5:7]), mask)

    def test_the_mask_mix_option(self):
        v = Evo(arrivals="10", options="mask_orange_percent=0\nmask_red_percent=0\n")
        v.villager(0, heathen=True)
        _force_arrival(v, *SINGLE, (100, 0))
        self.assertEqual(tuple(v.created[0][1][5:7]), (0, 0), "everyone blue")

    def test_before_the_last_heathen_never_from_nothing(self):
        v = Evo(arrivals="10")
        v.villager(0, heathen=False)                      # the clock: a believer; no Heathen alive
        self.assertEqual(_force_arrival(v, *SINGLE), [])

    def test_after_the_last_heathen_arrivals_come_with_nobody_there(self):
        v = Evo(arrivals="10")
        v.solve(25)
        v.villager(0, heathen=False)
        self.assertEqual(len(_force_arrival(v, *SINGLE)), 1)

    def test_the_clock_is_one_roll_per_unit(self):
        v = Evo(arrivals="10")
        v.villager(0, heathen=True)
        v.look(0)
        any_roll = (600, lambda r: True)                  # each unit's conception roll comes after its arrival roll
        v.seed(first_output((4800, lambda r: r >= 100), any_roll, (4800, lambda r: r >= 100), any_roll,
                            (4800, lambda r: r < 100), *SINGLE))
        v.credit(v.record(0), 3)
        self.assertEqual(len(v.created), 1, "three units: three rolls, the third arrives")


def _fill(v: Evo, believers: int, heathens: int) -> None:
    for i in range(believers):
        v.villager(i, heathen=False, name=f"B{i}")
    for i in range(believers, believers + heathens):
        v.villager(i, heathen=True, name=f"H{i}", age=200)   # children: none pairs


@unittest.skipIf(_skip(), _skip() or "")
class RecordCap(unittest.TestCase):
    """Decision 18 as the owner changed it (2026-11-26: "they should grow normally"): Heathens grow in every
    population mode; the limit is the technical one -- "Room kept for believers" (the owner, 2026-11-28: 20 unless
    moved, at least 10) records kept free, so the believers' own are never blocked and the game never runs out."""

    def _arrive_four(self, v: Evo) -> int:
        return len(_force_arrival(v, (100, 95), (2, 1)))

    def test_every_mode_keeps_the_room_free_150(self):
        # spare = 150 - B - H - room, whatever the believers' cap
        for room, cases in (("room_kept=10\n", ((80, 40, 4), (80, 58, 2), (80, 60, 0), (20, 20, 4))),
                            (None, ((80, 40, 4), (80, 48, 2), (80, 50, 0), (20, 20, 4)))):
            for mode in ("stock", "stock+collections", "progression", "fixed"):
                for believers, heathens, made in cases:
                    with self.subTest(room=room, mode=mode, b=believers, h=heathens):
                        v = Evo(arrivals="10", options=room,
                                collections=(0x68, 0x50) if mode.endswith("collections") else ())
                        if mode == "progression":
                            _detour(v, 135)
                        elif mode == "fixed":
                            _detour(v, 90, fixed_bonus=60)
                        _fill(v, believers, heathens)
                        self.assertEqual(self._arrive_four(v), made)

    def test_the_room_is_never_under_ten(self):
        v = Evo(arrivals="10", options="room_kept=3\n")
        _fill(v, 80, 58)
        self.assertEqual(self._arrive_four(v), 2, "room_kept below 10 reads as 10")

    def test_the_256_build_in_all_three_modes(self):
        for mode in ("stock", "progression", "fixed"):
            for believers, heathens, made in ((100, 100, 4), (120, 114, 2), (120, 116, 0)):
                with self.subTest(mode=mode, b=believers, h=heathens):
                    v = Evo256(arrivals="10")
                    if mode == "progression":
                        _detour(v, 241)
                    elif mode == "fixed":
                        _detour(v, 90, fixed_bonus=166)
                    _fill(v, believers, heathens)
                    self.assertEqual(self._arrive_four(v), made)
                    self.assertTrue(all(i >= 150 for i, _ in v.created), "records past 150")

    def test_a_conception_waits_for_the_room(self):
        v = Evo()
        _fill(v, 80, 50)                                  # 132 with the couple: 18 free, under the 20 kept
        man, woman = _couple(v, 140, 141)
        self.assertEqual(v.couple_of(141), 140)
        v.seed(first_output((4800, lambda r: True), (600, 0), (2, 1)))
        v.credit(v.record(0), 1)
        v.spots[man] = v.spots[woman] = (1, 1)
        v.look(0)
        self.assertEqual(v.conceived, [], "no conception into the room kept for believers")


@unittest.skipIf(_skip(), _skip() or "")
class TribeSize(unittest.TestCase):
    """The owner, 2026-11-28: "Heathen tribe size" (tribe_max), "How often the tribe changes" (change_tenths);
    growth slows over the last fifth of the limit and pauses at it; nobody is removed; children kept around."""

    def _arrivals(self, options: str, heathens: int, roll, *, arrivals: str = "10") -> list[int]:
        v = Evo(arrivals=arrivals, options=options)
        for i in range(heathens):
            v.villager(i, heathen=True, name=f"H{i}", age=600 if i < 2 else 100, sex=i % 2)
        _preset(v, [(1, 0)])                              # the two adults a couple already: no pairing roll
        v.look(0)
        v.seed(first_output((1200000, roll), *SINGLE))
        v.credit(v.record(0), 1)
        return v.created

    def test_an_arrival_rolls_a_x_c_x_f_in_1_200_000(self):
        # a = 100 (10x), c = 10, F = 100 below the slowing band: 100,000 of 1,200,000
        self.assertEqual(len(self._arrivals("tribe_max=50\n", 7, 99999)), 1)
        self.assertEqual(self._arrivals("tribe_max=50\n", 7, 100000), [])
        self.assertEqual(len(self._arrivals("tribe_max=50\nchange_tenths=20\n", 7, 199999)), 1,
                         "twice as often at 2x")

    def test_growth_slows_near_the_limit_and_pauses_at_it(self):
        # tribe_max 50: band 10; 45 in the camp, 5 left: F = 50
        self.assertEqual(len(self._arrivals("tribe_max=50\n", 45, 49999)), 1)
        self.assertEqual(self._arrivals("tribe_max=50\n", 45, 50000), [])
        self.assertEqual(self._arrivals("tribe_max=50\n", 50, 0), [], "at the limit: nothing")
        v = Evo(arrivals="10", options="tribe_max=10\n")
        for i in range(14):
            v.villager(i, heathen=True, name=f"H{i}")
        v.look(0)
        v.credit(v.record(0), 50)
        self.assertEqual([v.read(v.record(i) + PRESENT, 1) for i in range(14)], [b"\x01"] * 14,
                         "over the limit: nobody leaves")

    def test_a_group_never_passes_the_limit(self):
        v = Evo(arrivals="10", options="tribe_max=10\n")
        for i in range(8):
            v.villager(i, heathen=True, name=f"H{i}", age=600 if i < 2 else 100, sex=i % 2)
        _preset(v, [(1, 0)])
        v.look(0)
        v.seed(first_output((1200000, 0), (100, 95), (2, 1)))
        v.credit(v.record(0), 1)
        self.assertEqual(len(v.created), 2, "a group of four trimmed to the two places left")

    def test_short_of_children_an_arrival_is_a_family(self):
        made = self._arrivals("tribe_max=50\n", 3, 0)
        self.assertGreaterEqual(len(made), 3, "a couple with their children (fewer than 5 children of 50)")

    def test_the_limit_is_kept_within_the_table_and_at_least_ten(self):
        self.assertEqual(len(self._arrivals("tribe_max=4\n", 9, 0)), 1, "4 reads as 10")


@unittest.skipIf(_skip(), _skip() or "")
class Roles(unittest.TestCase):
    """Decision 6: the Chief and the Masters (13-16) go on in the camp once their puzzle is solved."""

    def _camp(self, v: Village, role: int) -> int:
        holder = v.villager(1, heathen=True, role=role, name="Holder", age=900)
        v.villager(3, heathen=True, role=2, name="Elder", age=700, orange=0, red=0)
        v.villager(4, heathen=True, role=1, name="Younger", age=500)
        v.villager(5, heathen=True, role=0, name="Child", age=100)
        v.villager(6, heathen=True, role=14, name="Scientist", age=990)
        return holder

    def test_for_show_before_the_last_heathen(self):
        for role, puzzle, skills, mask, title in (
                (13, 16, (100.0,) * 6, (0, 1), "Heathen Chief"),
                (16, 5, (90.0, 0, 0, 0, 0, 0), (1, 0), "Heathen Master Farmer"),
                (14, 13, (0, 0, 0, 90.0, 0, 0), (1, 0), "Heathen Master Scientist"),
                (15, 9, (0, 0, 0, 0, 90.0, 0), (1, 0), "Heathen Master Builder")):
            with self.subTest(role=role):
                v = Evo(story=True)
                v.solve(puzzle)
                holder = self._camp(v, role)
                _due_to_die(v, holder)
                v.life_tick()
                heir = v.record(3)
                self.assertEqual(v.i32(heir, ROLE), 2, "the role for show: still an ordinary Heathen")
                self.assertEqual(struct.unpack("<6f", v.read(heir + SKILLS, 24)), skills)
                self.assertEqual((v.read(heir + ORANGE, 1)[0], v.read(heir + RED, 1)[0]), mask)
                self.assertEqual(v.titles, [(3, title)])
                self.assertEqual(v.roles_logged, [(3, role)], "a Took the role record")

    def test_the_role_for_show_goes_on_at_the_heirs_death(self):
        v = Evo(story=True)
        v.solve(16)
        holder = self._camp(v, 13)
        _due_to_die(v, holder)
        v.life_tick()
        _due_to_die(v, v.record(3))
        v.life_tick()
        self.assertEqual(v.roles_logged, [(3, 13), (4, 13)])

    def test_a_show_chief_who_converts_is_a_real_retired_chief(self):
        """The owner, 2026-11-26: "Real role when he converts" -- role 13 on the believer (the game's own "Retired
        Chief" title and Spreading the Word), the show title taken off; any sex.  A show Master who converts just
        stops being one, and their "Heathen Master ..." title is taken off too (Codex, #883)."""
        for role, puzzle, sex in ((13, 16, 1), (13, 16, 0), (15, 9, 1)):
            with self.subTest(role=role, sex=sex):
                v = Evo(story=True)
                v.solve(puzzle)
                holder = self._camp(v, role)
                v.put32(v.record(3) + SEX, sex)
                _due_to_die(v, holder)
                v.life_tick()
                heir = v.record(3)
                v.write(heir + FACTION, b"\x00")              # preached to: a believer
                v.look(4)
                if role == 13:
                    self.assertEqual(v.i32(heir, ROLE), 13, "a real Retired Chief")
                    self.assertEqual(v.titles[-1], (3, ""), "the show title taken off")
                else:
                    self.assertEqual(v.i32(heir, ROLE), 2, "an ordinary believer")
                    self.assertEqual(v.titles, [(3, "Heathen Master Builder"), (3, "")],
                                     "the show Master's title taken off")
                v.write(heir + FACTION, b"\x01")              # a Heathen again: no longer a show holder
                v.put32(heir + ROLE, 2)
                v.look(4)
                _due_to_die(v, heir)
                v.life_tick()
                self.assertEqual(v.roles_logged, [(3, role)], "nothing passes on")

    def test_a_show_master_who_retires_hands_on_the_title_too(self):
        """Codex, #883: the "Heathen Master ..." title goes with the role -- off the retiring elder, onto the heir."""
        v = Evo(story=True)
        v.solve(9)
        holder = self._camp(v, 15)
        _due_to_die(v, holder)
        v.life_tick()
        heir = v.record(3)
        self.assertEqual(v.titles, [(3, "Heathen Master Builder")])
        v.put32(heir + AGE, ELDER_AT_MEDICINE_1)            # the show Master is an elder now
        v.look(4)
        self.assertEqual(v.titles, [(3, "Heathen Master Builder"), (3, ""), (4, "Heathen Master Builder")])
        self.assertEqual(v.retired_logged, [(3, 15)])

    def test_the_real_role_after_the_last_heathen(self):
        v = Evo()
        v.solve(16)
        v.solve(25)
        holder = self._camp(v, 13)
        v.write(v.record(3) + ORANGE, b"\x01")
        _due_to_die(v, holder)
        v.life_tick()
        heir = v.record(3)
        self.assertEqual(v.i32(heir, ROLE), 13, "the real role: the Chief's own mask art")
        self.assertEqual((v.read(heir + ORANGE, 1)[0], v.read(heir + RED, 1)[0]), (0, 0))
        self.assertEqual(v.roles_logged, [(3, 13)])
        self.assertEqual(v.titles, [])

    def test_for_show_masks_through_the_origins_store(self):
        """The owner: "for show masters = purple masks (no puzzles)"; the Chief's own mask art for show.  The game
        draws those only from the puzzle roles, so they go in the Origins store "Heathens Keep Their Masks When
        Converted" draws (4 purple, 5 the Chief's); the kind bytes stay 0.  A holder's death puts it back to blue."""
        for role, puzzle, mask in ((14, 13, 4), (13, 16, 5)):
            with self.subTest(role=role):
                v = Evo()
                kept = []
                stub = v.alloc(0x10)
                v.stub(stub, lambda p: (kept.append((p.arg(0), p.arg(1))), (1, 8))[1])
                base = v._module

                def module(p, base=base):
                    name = p.cstring(p.arg(0)) if p.arg(0) else ""
                    if name in ("VVFP Origins Icons.dll", "VVFP Heathens Keep Masks.dll"):
                        return 0x0B600000, 4
                    return base(p)
                proc = v._proc

                def find(p, proc=proc):
                    if p.arg(0) == 0x0B600000:
                        return (stub if p.cstring(p.arg(1)) == "VvfpMaskKeep" else 0), 8
                    return proc(p)
                v.api_handlers["GetModuleHandleA"] = module
                v.api_handlers["GetProcAddress"] = find
                v.solve(puzzle)
                holder = self._camp(v, role)
                _due_to_die(v, holder)
                v.life_tick()
                heir = v.record(3)
                self.assertEqual(kept, [(heir, mask)])
                self.assertEqual((v.read(heir + ORANGE, 1)[0], v.read(heir + RED, 1)[0]), (0, 0))
                _due_to_die(v, heir)
                v.life_tick()
                self.assertEqual(kept[1], (heir, 1), "its stored mask back to blue when it dies")

    def test_any_sex_holds_a_role(self):
        """The owner: every later holder "can be any sex" -- the eldest, man or woman; a replacement made in a
        puzzle role is of random sex (the creator's -1), the Chief and Farmer too."""
        v = Evo(story=True)
        v.solve(16)
        holder = self._camp(v, 13)
        v.put32(v.record(3) + SEX, 1)                     # the eldest is a woman
        _due_to_die(v, holder)
        v.life_tick()
        self.assertEqual(v.roles_logged, [(3, 13)])
        for role in (13, 16):
            with self.subTest(role=role):
                v = Evo()
                holder = self._camp(v, role)
                _due_to_die(v, holder)
                v.life_tick()
                self.assertEqual((v.created[0][1][7], v.created[0][1][3]), (role, -1), "random sex")

    def test_a_regrown_camp_gets_a_real_chief_and_masters(self):
        v = Evo()
        for puzzle in (1, 5, 9, 13, 16, 17, 25):
            v.solve(puzzle)
        for i in range(1, 6):
            v.villager(i, heathen=True, role=1, name=f"A{i}", age=400 + 20 * i, sex=i % 2)
        v.villager(9, heathen=True, role=0, name="Kid", age=100)
        v.look(1)
        self.assertEqual(v.roles_logged, [], "5 adults: not yet")
        v.villager(6, heathen=True, role=2, name="Sixth", age=900, sex=1)
        for _ in range(5):
            v.look(1)
        self.assertEqual(v.roles_logged, [(6, 13), (5, 14), (4, 15), (3, 16)], "one a look, the eldest first")
        self.assertEqual([v.i32(v.record(i), ROLE) for i in (6, 5, 4, 3)], [13, 14, 15, 16], "the real roles")

    def test_while_the_puzzle_is_unsolved_todays_rule(self):
        v = Evo(story=True)
        holder = self._camp(v, 13)
        _due_to_die(v, holder)
        v.life_tick()
        self.assertEqual(v.roles_logged, [])
        self.assertEqual(v.created[0][1][7], 13, "a new Chief by the stock camp's set-up")

    def test_not_without_the_expansion(self):
        v = Evo(flags=(TRIBE,), story=True)
        v.solve(16)
        holder = self._camp(v, 13)
        _due_to_die(v, holder)
        v.life_tick()
        self.assertEqual(v.roles_logged, [])


@unittest.skipIf(_skip(), _skip() or "")
class ConceptionLogFix(unittest.TestCase):
    """Every forced conception gets its Conception record (the game's hook at 0x465F34 skips forced ones)."""

    def test_the_tribe_rows_conception(self):
        v = Evo(flags=(TRIBE,))
        man = v.villager(1, heathen=True, sex=0, name="Kalo")
        woman = v.villager(2, heathen=True, sex=1, name="Mele")
        v.put32(woman + AGE, 601)
        v.rand_answers.extend([0, 0])
        v.life_tick()
        self.assertEqual(v.conceptions, [(woman, man, 1)])

    def test_the_heathen_mommys_infant(self):
        v = Evo(flags=(TRIBE,))
        other = v.villager(3, heathen=True, sex=1, name="Vaihi", age=400)
        r = v.villager(2, heathen=True, role=17, sex=1, name="Ahi")
        _due_to_die(v, r)
        v.life_tick()
        mommy = v.record(v.created[0][0])
        self.assertEqual(v.conceptions, [(mommy, other, 1)], "named, of either sex (the owner)")

    def test_an_island_events_pregnancy(self):
        v = Evo(flags=("VVFP Heathen Aging Events.txt",))
        man = v.villager(1, heathen=True, sex=0, name="Kalo")
        woman = v.villager(2, heathen=True, sex=1, name="Mele")
        self.assertEqual(v.export("VvfpHeathenAgingEventPregnancy", 5, 2, 1, 2, 0), 2)
        self.assertEqual(v.conceptions, [(woman, man, 2)])

    def test_the_mommys_other_parent_is_never_unknown(self):
        """No adult Heathen to name: her own infant's other parent; and nobody recorded: the eldest Heathen."""
        for recorded, expected in (("Old Partner", "Old Partner"), ("", "Little One")):
            with self.subTest(recorded=recorded):
                v = Evo(flags=(TRIBE,))
                v.villager(3, heathen=True, sex=1, name="Little One", age=100)
                r = v.villager(2, heathen=True, role=17, sex=1, name="Ahi")
                v.write(r + 0x1C10, recorded.encode() + b"\0")
                _due_to_die(v, r)
                v.life_tick()
                mommy = v.record(v.created[0][0])
                self.assertEqual(v.cstring(mommy + 0x1C10), expected, "her infant's other parent, by name")


@unittest.skipIf(_skip(), _skip() or "")
class LifeBridge(unittest.TestCase):
    """heathen_evo.h section 3: VvfpHeathenLifeUnit for every aging Heathen's unit, and the sick byte's question."""

    def test_a_unit_calls_life_and_an_idle_pass_asks_about_the_sick_byte(self):
        v = Evo(life=True)
        h = v.villager(1, heathen=True)
        v.look(1)                                         # the export found
        v.put32(h + AGE, 601)
        v.life_tick()
        self.assertIn((h, 0x101), v.life_calls, "HE_LIFE_UNIT | HE_LIFE_ROW")
        self.assertIn((h, 0x100), v.life_calls, "then idle (the tick's next pass)")

    def test_the_sick_byte_kept_only_when_life_says_so(self):
        for answer, sick in ((1, 1), (2, 0), (0, 0)):
            with self.subTest(answer=answer):
                v = Evo(life=True)
                h = v.villager(1, heathen=True)
                v.look(1)
                v.life_answer = answer
                v.write(h + SICK, b"\x01")
                v.life_tick()
                self.assertEqual(v.read(h + SICK, 1)[0], sick)

    def test_without_life_or_the_expansion_the_stock_skip(self):
        for flags in ((EVO,), (TRIBE,)):
            with self.subTest(flags=flags):
                v = Evo(flags=flags, life=flags == (TRIBE,))
                h = v.villager(1, heathen=True)
                v.look(1)
                v.life_answer = 1
                v.write(h + SICK, b"\x01")
                v.life_tick()
                self.assertEqual(v.read(h + SICK, 1)[0], 0)
                self.assertEqual(v.life_calls, [])


class OfflineFiles(unittest.TestCase):
    def test_copy_slot_retags_the_couples_file(self):
        import vv_copy_slot
        made = struct.pack("<5I", 0x31434856, 1, 5, 1, 1) + struct.pack("<4I", 7, 8, 600, 0)
        moved = vv_copy_slot.transform_binary(made, 1, 3, {}, "Tribe", "Tribe")
        self.assertEqual(struct.unpack_from("<I", moved, 16)[0], 3)
        self.assertEqual(moved[:16] + moved[20:], made[:16] + made[20:])

    def test_the_rename_planner_rekeys_both_partners(self):
        import tempfile
        import inspect
        import vv_last_names as ln
        self.assertIn('b"VHC1", {1: 16}, game, 20, 0, title_map', inspect.getsource(ln.plan_renames))
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "Heathen Couples - Save 1.dat"
            original = struct.pack("<5I", 0x31434856, 1, 5, 2, 1) + struct.pack(
                "<8I", 0xA1, 0xB1, 600, 0, 0xB2, 0xA1, 700, 0)
            path.write_bytes(original)
            plan = ln.Plan({})
            ln._plan_u32_file(plan, path, b"VHC1", {1: 16}, 5, 20, 0, {0xA1: 0xC1}, "Heathen Couples", {},
                              more_fields=(4,))
            after = plan.changes[0].updated
            self.assertEqual(struct.unpack_from("<8I", after, 20), (0xC1, 0xB1, 600, 0, 0xB2, 0xC1, 700, 0))


class TheHeader(unittest.TestCase):
    def test_the_shared_names(self):
        text = (ROOT / "native" / "shared" / "heathen_evo.h").read_text(encoding="utf-8")
        for name in (EVO, BIRTHS_FILE, ARRIVALS_FILE, OPTIONS_FILE, "VvfpHeathenLifeUnit", "VvfpHeathenAgingCoupleOf",
                     "VvfpHeathenMausoleumIsHeathenGrave", "VvfpHeathenMausoleumVillageReset",
                     "WriteParentageHeathenCouple", "VvfpCauseHeathenRole", "0x31434856u", "0x314D4856u"):
            self.assertIn(name, text)



def _couples_path(slot: int) -> str:
    return (f"C:\\Docs\\LDW\\Game\\Virtual Villagers Fun Patcher\\Save {slot}\\Data\\Heathen Couples\\"
            f"Heathen Couples - Save {slot}.dat")


class LockableEvo(Evo):
    """An Evo whose files in `locked` exist but cannot be opened (the game or another program holds them)."""

    def before_start(self) -> None:
        super().before_start()
        self.locked: set[str] = set()
        opener = self.api_handlers["CreateFileA"]

        def create(p):
            if p.cstring(p.arg(0)) in self.locked:
                self.last_error = 32                       # ERROR_SHARING_VIOLATION
                return 0xFFFFFFFF, 28
            return opener(p)
        self.api_handlers["CreateFileA"] = create


@unittest.skipIf(_skip(), _skip() or "")
class ChangeTribe(unittest.TestCase):
    """Codex, #883: a Change Tribe to a slot whose couples file is locked kept the last village's partner cache, so
    the new village's women could conceive with the old village's pairings.  Every per-village piece is forgotten at
    a slot change, and while the new slot's couples are unknown there is no couple, birth or arrival."""

    def test_a_locked_couples_file_in_the_new_slot_pauses_everything_and_nothing_of_the_old_village_is_used(self):
        v = LockableEvo(arrivals="10")
        man, woman = _couple(v, 1, 2)
        third = v.villager(3, heathen=True, sex=0, name="Ioane")
        self.assertEqual(v.couple_of(2), 1, "village A: Mele and Kalo")
        # Village B (slot 2): its own file pairs Mele with Ioane, and it is locked.
        v.files[_couples_path(2)] = struct.pack("<5I", 0x31434856, 1, 5, 1, 2) + struct.pack(
            "<4I", _identity(v, woman), _identity(v, third), 600, 0)
        v.locked.add(_couples_path(2))
        before = v.files[_couples_path(2)]
        v.put32(v.save_manager + SLOT_FIELD, 2)
        v.look(1)
        self.assertEqual(v.couple_of(2), -1, "A's pairing is gone from the cache")
        self.assertEqual(v.couple_of(1), -1)
        v.seed(first_output((4800, lambda r: True), (600, 0), (2, 1)))
        v.credit(man, 1)
        v.look(1)
        self.assertEqual((v.conceived, v.behaviours), ([], []), "no embrace while B's couples are unknown")
        made = _force_arrival(v, *SINGLE, clock=1)
        self.assertEqual(made, [], "no arrival either")
        _clock(v, 3)
        self.assertEqual(v.couples_logged[1:], [], "and no new couple")
        self.assertEqual(v.files[_couples_path(2)], before, "the locked file is never replaced")
        # Unlocked: B's own couple is read (the gate retries on its throttle).
        v.locked.clear()
        for _ in range(40):
            v.look(1)
            if v.couple_of(2) >= 0:
                break
        self.assertEqual(v.couple_of(2), 3, "B's own pairing: Mele and Ioane")
        v.seed(first_output((4800, lambda r: True), (600, 0), (2, 1)))
        v.credit(man, 1)
        v.look(1)
        self.assertEqual([v.cstring(args[3]) for _c, args in v.conceived], ["Ioane"], "the father is B's partner")


# ---- the owner, 2026-11-26: children grow up, elders retire and keep their pace, a reused record is no partner ---
ELDER_AT_MEDICINE_1 = 1000                              # 0x46F790: 160 x Medicine + 840
ROLE_FINDER = 0x470690
CHILD_WORDS = "Replaced a Heathen child who grew up"
OWED_CHILD = 0x20000


def _grow(v: Evo, index: int, *, orange: int = 0, parents: bool = False, role: int = 0) -> int:
    """A camp child one unit short of 280: the next life tick makes them an adult."""
    r = v.villager(index, heathen=True, age=280, orange=orange, parents=parents, role=role, name=f"Kid{index}")
    v.put32(r + PROCESSED, 279)
    return r


def _fill_records(v: Evo, keep_free: int) -> None:
    """Every record but `keep_free` (from the top) present, so only that many are free."""
    for i in range(v.slots - keep_free):
        if v.read(v.record(i) + PRESENT, 1) == b"\0":
            v.villager(i, heathen=False, age=400, name=f"B{i}")


@unittest.skipIf(_skip(), _skip() or "")
class GrowingUp(unittest.TestCase):
    """"if the heathen children age up immediately spawn replacements!!! especially the rascal!!!!!!!!!!" -- the
    Rascal is the camp's orange-masked child (the Details title 0x4430AE: younger than 280 and +0x1CED)."""

    def test_the_rascal_who_grows_up_is_replaced_by_a_new_rascal_at_once(self):
        v = Evo()
        v.villager(0, heathen=True, name="Elder")
        kid = _grow(v, 5, orange=1)
        v.life_tick()
        self.assertEqual(len(v.created), 1)
        index, args = v.created[0]
        lineage, skill, value, sex, age, orange, red, role, _faith = args
        self.assertEqual((skill, value, age, orange, red, role), (2, 0, 140, 1, 0, 0),
                         "the stock Rascal's set-up (0x424D23): Healing 0, age 140, orange, role 0")
        self.assertTrue(-67 <= v.i32(v.record(index), 0x1CF0) <= -38, "the stock camp's Faith")
        self.assertEqual(v.arrived, [(index, CHILD_WORDS)])
        self.assertEqual((v.i32(kid, AGE), v.read(kid + PRESENT, 1)), (280, b"\x01"), "the grown one stays")

    def test_a_blue_camp_child_gets_a_blue_child_in_the_same_role(self):
        v = Evo()
        v.villager(0, heathen=True)
        _grow(v, 5, role=0)
        v.life_tick()
        (_, args), = v.created
        self.assertIn(args[4], (120, 240), "a stock blue child's age")
        self.assertEqual((args[5], args[6], args[7]), (0, 0, 0))

    def test_a_couples_baby_is_the_tribes_growth_not_a_place(self):
        v = Evo()
        v.villager(0, heathen=True)
        _grow(v, 5, parents=True)
        v.life_tick()
        self.assertEqual(v.created, [])

    def test_no_room_owes_the_child_until_there_is(self):
        v = Evo(options="room_kept=10\n")
        v.villager(0, heathen=True)
        _grow(v, 5, orange=1)
        _fill_records(v, 10)                          # only the 10 kept free: none fits
        v.life_tick()
        self.assertEqual(v.created, [])
        v.look(0)
        self.assertTrue(any((who & 0x80000000) and (who & OWED_CHILD) for who, _kind in v.known_entries()),
                        "owed in the slot's file, marked a child")
        v.write(v.record(139) + PRESENT, b"\x00")     # room again (a believer of the filled ones gone)
        v.put32(v.record(0) + AGE, v.i32(v.record(0), AGE) + 1)
        v.life_tick()
        self.assertEqual([(args[4], args[5]) for _, args in v.created], [(140, 1)], "paid: a Rascal")

    def test_after_the_last_heathen_only_with_arrivals(self):
        for arrivals, made in (("0", 0), ("1", 1)):
            with self.subTest(arrivals=arrivals):
                v = Evo(arrivals=arrivals)
                v.solve(25)
                v.villager(0, heathen=True)
                _grow(v, 5, orange=1)
                v.life_tick()
                self.assertEqual(len(v.created), made)


@unittest.skipIf(_skip(), _skip() or "")
class PartnerReuse(unittest.TestCase):
    """Codex, #883: a partner who vanished in an island event, their record reused by the replacement in the same
    tick -- the newcomer is never taken for the partner."""

    def test_no_conception_with_the_newcomer_in_the_partners_record(self):
        v = Evo()
        v.villager(0, heathen=True, age=100, name="Child")   # record 0 taken (a child never pairs)
        man, woman = _couple(v, 1, 2)
        self.assertEqual(v.couple_of(2), 1)
        create = v._create

        def male_newcomer(p):                         # the replacement is a man, in the record the partner left
            answer = create(p)
            if answer[0] != 0xFFFFFFFF:
                v.put32(v.record(answer[0]) + SEX, 0)
            return answer
        v.stub(0x46FD20, male_newcomer)
        self.assertEqual(v.export("VvfpHeathenAgingEventGone", 5, 1, 1, 5), 1, "taken: the replacement is owed")
        v.put32(woman + AGE, v.i32(woman, AGE) + 1)
        v.life_tick()                                 # pays the owed replacement first, then her unit
        self.assertEqual([i for i, _ in v.created], [1], "the newcomer took the partner's record")
        self.assertEqual(v.conceived, [], "no conception with someone she never paired with")
        self.assertEqual(v.couple_of(2), -1)


def _role_holder(v: Evo, index: int, role: int, age: int = ELDER_AT_MEDICINE_1, **kw) -> int:
    return v.villager(index, heathen=True, age=age, role=role, name=f"R{index}", **kw)


@unittest.skipIf(_skip(), _skip() or "")
class Retirement(unittest.TestCase):
    """"above elderly age, heathens will "retire" and go to the encampment where younger ones will take their
    place"; "Puzzle roles too"; "the chief shouldn't retire"."""

    def test_a_camp_role_goes_to_the_eldest_younger_one(self):
        v = Evo()
        old = _role_holder(v, 3, 5)
        v.villager(4, heathen=True, age=500, name="Young")
        v.villager(6, heathen=True, age=700, name="Older")
        v.villager(7, heathen=True, age=999, name="Not yet")       # one short of an elder: the successor
        v.villager(8, heathen=True, age=1200, name="Elder")         # an elder never succeeds
        v.look(4)
        self.assertEqual(v.i32(old, ROLE), 0, "retired to the encampment (role 0: the camp wander)")
        self.assertEqual(v.i32(v.record(7), ROLE), 5)
        self.assertEqual((v.retired_logged, v.roles_logged), ([(3, 5)], [(7, 5)]))

    def test_with_nobody_younger_the_elder_keeps_the_place(self):
        v = Evo()
        old = _role_holder(v, 3, 5)
        v.villager(8, heathen=True, age=1200, name="Elder")
        v.villager(9, heathen=True, age=100, name="Child")
        v.look(3)
        self.assertEqual(v.i32(old, ROLE), 5)
        self.assertEqual((v.retired_logged, v.roles_logged), ([], []))

    def test_the_chief_never_retires(self):
        v = Evo()
        chief = _role_holder(v, 3, 13, age=1400)
        v.villager(4, heathen=True, age=500)
        v.look(4)
        self.assertEqual(v.i32(chief, ROLE), 13)
        self.assertEqual(v.retired_logged, [])

    def test_each_puzzle_role_goes_on_and_its_puzzle_still_finds_its_heathen(self):
        set_up = {12: (2, 70.0, -14), 14: (3, 90.0, -74), 15: (4, 90.0, -74), 16: (0, 90.0, -74), 17: (1, 70.0, -25)}
        for role, (skill, value, faith) in set_up.items():
            with self.subTest(role=role):
                v = Evo()
                old = _role_holder(v, 3, role)
                heir = v.villager(4, heathen=True, age=500, name="Heir", sex=1)
                v.look(4)
                self.assertEqual((v.i32(old, ROLE), v.i32(heir, ROLE)), (0, role))
                self.assertEqual(v.call(ROLE_FINDER, [role], ecx=v.manager), heir, "the role finder finds the heir")
                self.assertAlmostEqual(struct.unpack("<f", v.read(heir + SKILLS + 4 * skill, 4))[0], value)
                self.assertEqual(v.i32(heir, 0x1CF0), faith)
                self.assertEqual((v.retired_logged, v.roles_logged), ([(3, role)], [(4, role)]))
                if role == 17:
                    self.assertEqual(len(v.conceived), 1, "the Mommy's successor carries her infant")
                    self.assertEqual(v.i32(old, PREGNANT), 0, "the infant went with the role")

    def test_a_puzzle_role_takes_a_camp_role_holder_when_nobody_holds_none(self):
        v = Evo()
        old = _role_holder(v, 3, 14)
        worker = v.villager(4, heathen=True, age=500, role=6, name="Builder")
        v.look(4)
        self.assertEqual((v.i32(old, ROLE), v.i32(worker, ROLE)), (0, 14), "the puzzle comes first")

    def test_a_solved_puzzles_heathen_has_no_place_to_give_up(self):
        v = Evo()
        v.solve(1)                                     # the Heathen Doctor's puzzle (puzzle_of_role(12) = 1)
        old = _role_holder(v, 3, 12)
        v.villager(4, heathen=True, age=500)
        v.look(4)
        self.assertEqual(v.i32(old, ROLE), 12)


WALK_TEST, WALK_END, WALK = 0x4659C5, 0x465A0C, 0x0BC00000


@unittest.skipIf(_skip(), _skip() or "")
class ElderPace(unittest.TestCase):
    """"their speed must not be impacted at elderly age for balance reasons": the walk set-up 0x465980 gives an
    elder the slow pace 0x28 (40) at 0x465A06 -- never a Heathen with the row; a believer elder still slows."""

    def _pace(self, v: Evo, record: int) -> int:
        if not hasattr(v, "walk_mapped"):
            v.mu.mem_map(WALK, 0x1000)
            v.walk_mapped = True
        v.put32(WALK, 0x64)
        v.set_reg("esp", 0x0FF00000 - 0x3000)        # the emulator's stack (story_emulator STACK_TOP)
        v.set_reg("esi", record)
        v.set_reg("edi", WALK)
        v.run(WALK_TEST, WALK_END)
        return v.u32(WALK)

    def test_an_elder_heathen_keeps_their_pace_and_a_believer_elder_slows(self):
        v = Evo()
        self.assertEqual(v.read(WALK_TEST, 1), b"\xE9", "the site is spliced with the row")
        heathen = v.villager(3, heathen=True, age=1500)
        believer = v.villager(4, heathen=False, age=1500)
        young = v.villager(5, heathen=False, age=500)
        self.assertEqual(self._pace(v, heathen), 0x64, "an elder Heathen: their pace")
        self.assertEqual(self._pace(v, believer), 0x28, "a believer elder: the slow pace, as in the stock game")
        self.assertEqual(self._pace(v, young), 0x64)

    def test_without_the_row_nothing_is_spliced(self):
        v = Evo(flags=(TRIBE,))
        self.assertEqual(v.read(WALK_TEST, 11), bytes.fromhex("8D8E8C1B0000E8C09D0000"))


if __name__ == "__main__":
    unittest.main()
