"""Each villager's own rule "Random last name from the list" (the owner, v1.35.79), and two audits the owner
asked for with it: "Make sure random last names are truly random" and "Make sure from the mother is truly
from the mother".

The rule: a living villager's own rule for their children's last name may be "list" -- Random last name
from the list.  Whose rule applies is decided as for every own rule (decide(): one parent's own; both
parents' when they agree; the village's when they disagree or neither has one).

  * In the game, VVFP Last Names.dll's VvfpRuleLastName2 gives each child, at its birth, a last name drawn
    from the game's own list of 50 (the list the family names come from): every name equally likely, a
    fresh draw for each child -- twins and triplets each their own.
  * In the patcher, inherited() keeps the list name such a child carries (the draw the game made) and
    gives a child with none (or another) a draw of their own, the same each time for the same villager.
  * An older reader skips the "list" line: the DLL's own_line_of wants six letters, and the patcher's
    OWN_RULES had no "list", so there the village's rule applies.

The emulator half runs the SHIPPED companion with each stock executable: VvfpStartup reads the game's real
list from the executable, the game's own naming routine names the baby at its birth, and then
VvfpRuleLastName2 runs as the parentage companions call it, its Windows calls answered here (the Last
Names record is served from memory).  The v1.35.79 DLL from before this rule, out of git, runs the same
births: it never crashes and gives the village's rule.
"""
from __future__ import annotations

import collections
import random
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import vv_last_names as ln  # noqa: E402
import vv_log_tools as tools  # noqa: E402

# The chi-square bound for 49 degrees of freedom (50 names) at p = 0.001 is 85.35.
CHI_50 = 90.0
# The main branch's v1.35.79, before the rule: its Last Names DLL is the "older build".
OLDER_COMMIT = "521d622b"
OLDER_DLL = "assets/last_names/VVFP Last Names.dll"


def person(name: str, sex: str, head: int = 1, body: int = 1, alive: bool = True, arrived: bool = False) -> ln.Living:
    return ln.Living(0, name, sex, head, body, 1, "Akikai", alive=alive, arrived=arrived)


def chi_square(counts: dict, names: list[str], draws: int) -> float:
    expected = draws / len(names)
    return sum((counts.get(n, 0) - expected) ** 2 / expected for n in names)


def carried_in(game: int):
    return lambda name: ln.split_name(game, name)[1]


class TheRule(unittest.TestCase):
    """inherited(): the patcher's reading of a parent's own "Random last name from the list"."""

    def setUp(self):
        self.pool = list(tools.load_checker().LAST_NAMES[3])
        self.dad = person("Ago Bahati", "Male", 5, 6)
        self.mum = person("Aipi Wanjiko", "Female", 7, 8)

    def given(self, children, own, rule="father"):
        parents = {c.identity: (self.dad.identity, self.mum.identity) for c in children}
        return ln.inherited([self.dad, self.mum, *children], parents, rule, self.pool, None, carried_in(3), own)

    def test_the_label_and_the_code(self):
        self.assertEqual(ln.OWN_RULES["list"], "Random last name from the list")
        self.assertEqual(ln.OWN_LIST, "list")
        self.assertEqual(list(ln.OWN_RULES)[-1], "list", "the last entry of the window's dropdown")

    def test_a_child_gets_a_name_from_the_list(self):
        for own in ({ln.own_key(self.dad): "list"}, {ln.own_key(self.mum): "list"},
                    {ln.own_key(self.dad): "list", ln.own_key(self.mum): "list"}):
            with self.subTest(own=own):
                kid = person("Kid", "Male", 2, 2)
                got = self.given([kid], own)[kid.identity]
                self.assertIn(got, self.pool)
                self.assertEqual(got, self.given([kid], own)[kid.identity], "the same each time")

    def test_the_draw_the_game_made_is_kept(self):
        for last in (self.pool[0], self.pool[-1], "Bahati" if "Bahati" in self.pool else self.pool[7]):
            kid = person(f"Kid {last}", "Male", 2, 2)
            self.assertEqual(self.given([kid], {ln.own_key(self.dad): "list"})[kid.identity], last)

    def test_a_name_not_from_the_list_is_given_one_from_it(self):
        kid = person("Kid Chapstick", "Male", 2, 2)
        self.assertIn(self.given([kid], {ln.own_key(self.dad): "list"})[kid.identity], self.pool)

    def test_twins_and_triplets_each_get_a_draw(self):
        # Each child is its own draw: across many deliveries the litter-mates differ about 49 times in 50.
        same = 0
        for k in range(400):
            litter = [person("Kid", "Male", k, 1), person("Kid", "Female", k, 2), person("Kid", "Male", k, 3)]
            got = self.given(litter, {ln.own_key(self.dad): "list"})
            same += got[litter[0].identity] == got[litter[1].identity]
        self.assertLess(same, 30)

    def test_every_name_is_reachable_and_evenly_drawn(self):
        counts = collections.Counter()
        draws = 5000
        own = {ln.own_key(self.dad): "list"}
        children = [person(f"Kid{k}", "Male" if k % 2 else "Female", k % 64, k // 64) for k in range(draws)]
        got = self.given(children, own)
        for c in children:
            counts[got[c.identity]] += 1
        self.assertEqual(set(counts), set(self.pool), "the first and the last name of the list too")
        self.assertLess(chi_square(counts, self.pool, draws), CHI_50)

    def test_disagreeing_parents_use_the_village_rule(self):
        kid = person("Kid", "Male", 2, 2)
        self.assertEqual(self.given([kid], {ln.own_key(self.dad): "list", ln.own_key(self.mum): "mother"})
                         [kid.identity], "Bahati")

    def test_an_arrival_gets_none(self):
        kid = person("Kid", "Male", 2, 2, arrived=True)
        self.assertEqual(self.given([kid], {ln.own_key(self.dad): "list"})[kid.identity], "")

    def test_the_father_and_mother_rules_are_unchanged(self):
        kid = person("Kid", "Male", 2, 2)
        self.assertEqual(self.given([kid], {})[kid.identity], "Bahati")
        self.assertEqual(self.given([kid], {}, "mother")[kid.identity], "Wanjiko")
        self.assertEqual(self.given([kid], {ln.own_key(self.dad): "mother"})[kid.identity], "Wanjiko")
        self.assertEqual(self.given([kid], {ln.own_key(self.mum): "father"}, "mother")[kid.identity], "Bahati")

    def test_the_check_marks_no_drawn_child_wrong(self):
        own = {ln.own_key(self.dad): "list"}
        kid = person(f"Kid {self.pool[3]}", "Male", 2, 2)
        parents = {kid.identity: (self.dad.identity, self.mum.identity)}
        want = ln.expected_last_names([self.dad, self.mum, kid], parents, "father", self.pool, {}, carried_in(3), own)
        should, used, either = want[kid.identity]
        self.assertEqual(used, "list")
        self.assertFalse(ln.wrong_last_name(self.pool[3], should, either))
        self.assertEqual(ln.wrong_last_name_mark("Bahati", "list", "father"),
                         "should be Bahati: a parent's own rule, Random last name from the list, applies")


class FromTheMotherIsTheMothers(unittest.TestCase):
    """The owner: "Make sure from the mother is truly from the mother" -- the patcher's half."""

    def setUp(self):
        self.pool = list(tools.load_checker().LAST_NAMES[2])

    def run_rule(self, people, parents, rule="mother", own=None):
        return ln.inherited(people, parents, rule, self.pool, None, carried_in(2), own or {})

    def test_every_case(self):
        dad, mum = person("Ago Bahati", "Male", 5, 6), person("Aipi Wanjiko", "Female", 7, 8)
        triplets = [person("Kid", "Male", 1, 1), person("Kid", "Female", 1, 2), person("Kid", "Male", 1, 3)]
        parents = {t.identity: (dad.identity, mum.identity) for t in triplets}
        got = self.run_rule([dad, mum, *triplets], parents)
        self.assertEqual([got[t.identity] for t in triplets], ["Wanjiko"] * 3, "triplets: each the mother's")
        # A mother renamed before the birth: the records name her by her name now.
        renamed = person("Aipi Okelani", "Female", 7, 8)
        kid = person("Kid", "Male", 2, 2)
        self.assertEqual(self.run_rule([dad, renamed, kid], {kid.identity: (dad.identity, renamed.identity)})
                         [kid.identity], "Okelani")
        # A numbered mother: her last name, not her numeral.
        numbered = person("Aipi Wanjiko II", "Female", 7, 8)
        self.assertEqual(self.run_rule([dad, numbered, kid], {kid.identity: (dad.identity, numbered.identity)})
                         [kid.identity], "Wanjiko")
        # A mother with no last name: never the father's.  A living one is given her own in the same
        # repair (separate, else her family's), and her child takes that one.  A dead one with none (the
        # logs': nobody gives her one now) leaves the child none.
        plain = person("Aipi", "Female", 7, 8)
        for pool in (self.pool, None):
            got = ln.inherited([dad, plain, kid], {kid.identity: (dad.identity, plain.identity)}, "mother",
                               pool, None, carried_in(2))
            self.assertEqual(got[kid.identity], got[plain.identity])
            self.assertNotEqual(got[kid.identity], "Bahati")
        gone = person("Aipi", "Female", 7, 8, alive=False)
        self.assertEqual(self.run_rule([dad, kid], {kid.identity: (dad.identity, gone.identity)})[kid.identity], "")
        # A mother who died at the birth (in the logs, not in the save) still gives hers.
        dead = person("Aipi Wanjiko", "Female", 7, 8, alive=False)
        self.assertEqual(self.run_rule([dad, kid], {kid.identity: (dad.identity, dead.identity)})[kid.identity],
                         "Wanjiko")
        self.assertEqual(self.run_rule([dad, dead, kid], {kid.identity: (dad.identity, dead.identity)})
                         [kid.identity], "Wanjiko")
        # Her own From the mother under the village's From the father; his own From the mother too.
        self.assertEqual(self.run_rule([dad, mum, kid], {kid.identity: (dad.identity, mum.identity)}, "father",
                                       {ln.own_key(mum): "mother"})[kid.identity], "Wanjiko")
        self.assertEqual(self.run_rule([dad, mum, kid], {kid.identity: (dad.identity, mum.identity)}, "father",
                                       {ln.own_key(dad): "mother"})[kid.identity], "Wanjiko")


class InEveryGame(unittest.TestCase):
    """The patcher's half in each of the five games, with each game's own list."""

    def test_the_rule_the_draws_and_the_mother_in_every_game(self):
        for game in range(1, 6):
            with self.subTest(game=game):
                pool = list(tools.load_checker().LAST_NAMES[game])
                self.assertEqual(len(pool), 50)
                carried = carried_in(game)
                dad, mum = person("Ago Bahati", "Male", 5, 6), person("Aipi Wanjiko", "Female", 7, 8)
                kids = [person(f"Kid{k}", "Male" if k % 2 else "Female", k % 64, k // 64) for k in range(4000)]
                parents = {k.identity: (dad.identity, mum.identity) for k in kids}
                got = ln.inherited([dad, mum, *kids], parents, "father", pool, None, carried,
                                   {ln.own_key(mum): "list"})
                counts = collections.Counter(got[k.identity] for k in kids)
                self.assertEqual(set(counts), set(pool), "every name of this game's list, first and last too")
                self.assertLess(chi_square(counts, pool, len(kids)), CHI_50)
                kept = person(f"Kid {pool[-1]}", "Male", 99, 99)
                self.assertEqual(ln.inherited([dad, mum, kept], {kept.identity: (dad.identity, mum.identity)},
                                              "father", pool, None, carried, {ln.own_key(dad): "list"})
                                 [kept.identity], pool[-1], "the game's draw at the birth is kept")
                got = ln.inherited([dad, mum, *kids[:3]], parents, "mother", pool, None, carried)
                self.assertEqual({got[k.identity] for k in kids[:3]}, {"Wanjiko"}, "From the mother: hers")
                got = ln.inherited([dad, mum, *kids[:3]], parents, "father", pool, None, carried)
                self.assertEqual({got[k.identity] for k in kids[:3]}, {"Bahati"}, "From the father: his")


class TheRecordFile(unittest.TestCase):
    def test_the_new_code_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            own = {("Ago Bahati", 5, 6, "Male"): "list", ("Aipi Wanjiko", 7, 8, "Female"): "mother"}
            ln.write_record(folder, 4, 1, "father", {}, own=own)
            text = ln.record_path(folder, 4, 1).read_text(encoding="utf-8")
            self.assertIn("villager\tAgo Bahati\t5\t6\tM\tlist\n", text)
            self.assertEqual(ln.read_own(folder, 4, 1), own)
            self.assertEqual(ln.read_record(folder, 4, 1)[0], "father", "the village rule line is unchanged")

    def test_an_older_reader_skips_it_safely(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            own = {("Ago Bahati", 5, 6, "Male"): "list", ("Aipi Wanjiko", 7, 8, "Female"): "mother"}
            ln.write_record(folder, 4, 1, "father", {}, own=own)
            older = {k: v for k, v in ln.OWN_RULES.items() if k != "list"}   # the v1.35.79 table
            with mock.patch.dict(ln.OWN_RULES, older, clear=True):
                self.assertEqual(ln.read_own(folder, 4, 1), {("Aipi Wanjiko", 7, 8, "Female"): "mother"})
                dad, mum, kid = (person("Ago Bahati", "Male", 5, 6), person("Aipi Wanjiko", "Female", 7, 8),
                                 person("Kid", "Male"))
                got = ln.inherited([dad, mum, kid], {kid.identity: (dad.identity, mum.identity)}, "father", None,
                                   None, carried_in(4), ln.read_own(folder, 4, 1))
                self.assertEqual(got[kid.identity], "Wanjiko", "the mother's own rule alone: never a crash")


class TheRandomDraws(unittest.TestCase):
    """The owner: "Make sure random last names are truly random" -- every random pick of the patcher."""

    def setUp(self):
        self.pool = list(tools.load_checker().LAST_NAMES[3])

    def test_random_last_names_reaches_every_name(self):
        counts = collections.Counter()
        people = [person(f"Kid{k}", "Male", k, 0) for k in range(60)]
        draws = 0
        for seed in range(1, 120):
            changed, _ = ln.random_last_names(3, people, {}, seed, pool=self.pool)
            counts.update(changed.values())
            draws += len(changed)
        self.assertEqual(set(counts), set(self.pool))
        self.assertLess(chi_square(counts, self.pool, draws), CHI_50)

    def test_a_reroll_draws_another(self):
        people = [person(f"Kid{k}", "Male", k, 0) for k in range(10)]
        a = ln.random_last_names(3, people, {}, 11, pool=self.pool)[0]
        b = ln.random_last_names(3, people, {}, 12, pool=self.pool)[0]
        self.assertNotEqual(a, b)
        self.assertEqual(a, ln.random_last_names(3, people, {}, 11, pool=self.pool)[0], "the same seed, the same")
        seeds = {ln.random_seed() for _ in range(50)}
        self.assertGreater(len(seeds), 45, "Reroll seeds come from the system's random source")

    def test_the_village_random_from_list_rule_reaches_every_name(self):
        counts = collections.Counter()
        people = [person(f"Kid{k}", "Male", k % 50, k // 50) for k in range(5000)]
        got = ln.inherited(people, {}, "list", self.pool)
        counts.update(got.values())
        self.assertEqual(set(counts), set(self.pool))
        self.assertLess(chi_square(counts, self.pool, len(people)), CHI_50)

    def test_fifty_fifty_is_even(self):
        dad, mum = person("Ago Bahati", "Male", 5, 6), person("Aipi Wanjiko", "Female", 7, 8)
        kids = [person("Kid", "Male", k, 9) for k in range(2000)]
        got = ln.inherited([dad, mum, *kids], {k.identity: (dad.identity, mum.identity) for k in kids}, "random",
                           self.pool, None, carried_in(3))
        fathers = sum(got[k.identity] == "Bahati" for k in kids)
        self.assertTrue(880 < fathers < 1120, fathers)

    def test_an_arrivals_own_name_is_even_among_the_free_ones(self):
        # Before v1.35.79 the list was walked from a place the villager decided and the first free name
        # taken: a free name after a run of taken ones came up far more often.
        taken = set(self.pool[:10]) | set(self.pool[30:40])
        free = [n for n in self.pool if n not in taken]
        counts = collections.Counter()
        draws = 6000
        for k in range(draws):
            v = ln.Living(0, f"Kalea{k}", "Female", k % 97, k // 97, 3, "", arrived=True)
            counts[ln.unique_last_name(3, v, taken, set())] += 1
        self.assertEqual(set(counts), set(free), "never a taken one, and every free one")
        expected = draws / len(free)
        self.assertLess(sum((counts[n] - expected) ** 2 / expected for n in free), 60.0)   # 29 df, p < 0.001
        v = ln.Living(0, "Kalea", "Female", 1, 1, 3, "", arrived=True)
        self.assertEqual(ln.unique_last_name(3, v, set(self.pool[1:]), set()), self.pool[0],
                         "only one free: that one (the first of the list is reachable)")
        self.assertEqual(ln.unique_last_name(3, v, set(self.pool[:-1]), set()), self.pool[-1],
                         "only the last free: that one")


# ---------------------------------------------------------------------------------------------------------
# The shipped DLL at a birth, in an emulator, in every game
# ---------------------------------------------------------------------------------------------------------

try:
    import pefile
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_ESP, UC_X86_REG_FS, UC_X86_REG_GDTR
    from unicorn.x86_const import UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS
    HAVE_EMULATOR = True
except ImportError:                                   # pragma: no cover
    HAVE_EMULATOR = False

if HAVE_EMULATOR:
    import test_last_names as tln

STOCK_PRESENT = HAVE_EMULATOR and tln.STOCK_PRESENT
STUBS, HEAP, DATA, STACK, RETURN = 0x7E000000, 0x7D000000, 0x60000000, 0x70000000, 0x7F000000
PTD = 0x6F000000                 # the C runtime's per-thread data, answered by FlsGetValue
GDT, TEB = 0x6E000000, 0x6E010000
INVALID = 0xFFFFFFFF
# stdcall argument bytes of every Windows call the companion makes at startup and at a birth.
ARGS = {b"VirtualQuery": 12, b"VirtualAlloc": 16, b"VirtualProtect": 16, b"VirtualFree": 12,
        b"FlushInstructionCache": 12, b"GetCurrentProcess": 0, b"SHGetSpecialFolderPathA": 16,
        b"GetModuleFileNameA": 12, b"CreateFileA": 28, b"ReadFile": 20, b"CloseHandle": 4,
        b"MultiByteToWideChar": 24, b"QueryPerformanceCounter": 4, b"GetTickCount": 0,
        b"GetCurrentProcessId": 0, b"GetCurrentThreadId": 0, b"FlsGetValue": 4, b"TlsGetValue": 4,
        b"GetLastError": 0, b"SetLastError": 4, b"EnterCriticalSection": 4, b"LeaveCriticalSection": 4}


class Birth:
    """One stock executable and a Last Names DLL (`dll`: its bytes) in an emulator, as at a birth."""

    def __init__(self, game: str, dll: bytes):
        self.game = game
        self.no = tln.GAME_NO[game]
        exe = pefile.PE(str(tln.STOCK / tln.EXE[game]))
        image = exe.get_memory_mapped_image()
        routine, rand, *_ = tln.SITES[game]
        mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(0x400000, (len(image) + 0xFFF) & ~0xFFF)
        mu.mem_write(0x400000, bytes(image))
        mu.mem_write(rand, b"\xC3")
        sprintf = tln.SPRINTF.get(game)
        if sprintf:
            mu.mem_write(sprintf, b"\xC3")
        pe = pefile.PE(data=dll)
        base = pe.OPTIONAL_HEADER.ImageBase
        mu.mem_map(base, (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF)
        mu.mem_write(base, pe.get_memory_mapped_image())
        mu.mem_map(STUBS, 0x10000)
        self.stubs: dict[int, bytes] = {}
        for entry in pe.DIRECTORY_ENTRY_IMPORT:
            for imp in entry.imports:
                stub = STUBS + 0x10 * len(self.stubs)
                self.stubs[stub] = imp.name
                n = ARGS.get(imp.name)
                mu.mem_write(stub, b"\xCC" if n is None else (b"\xC2" + struct.pack("<H", n)))
                mu.mem_write(imp.address, struct.pack("<I", stub))
        self.exports = {e.name.decode(): base + e.address for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
        mu.mem_map(HEAP, 0x10000)
        mu.mem_map(PTD, 0x10000)
        mu.mem_map(DATA, 0x400000)
        mu.mem_map(STACK - 0x40000, 0x80000)
        mu.mem_map(RETURN, 0x1000)
        mu.mem_write(RETURN, b"\xC3")
        # A thread block for the C runtime's exception frames (fs:[0]): fs is a GDT data segment based there.
        mu.mem_map(GDT, 0x1000)
        mu.mem_map(TEB, 0x1000)
        mu.mem_write(TEB, struct.pack("<7I", INVALID, STACK, STACK - 0x40000, 0, 0, 0, TEB))
        mu.mem_write(GDT + 8, struct.pack("<Q", (0xFFF) | ((TEB & 0xFFFFFF) << 16) | (0x92 << 40) | (0x4 << 52)
                                          | (((TEB >> 24) & 0xFF) << 56)))
        mu.mem_write(GDT + 16, struct.pack("<Q", 0xFFFF | (0x92 << 40) | (0xF << 48) | (0xC << 52)))
        mu.reg_write(UC_X86_REG_GDTR, (0, GDT, 0x20, 0))
        mu.reg_write(UC_X86_REG_FS, 1 << 3)
        for flat in (UC_X86_REG_SS, UC_X86_REG_DS, UC_X86_REG_ES):
            mu.reg_write(flat, 2 << 3)
        self.mu, self.heap, self.rand_va, self.sprintf_va = mu, HEAP, rand, sprintf
        self.rolls: list[int] = []
        self.record = b""
        self.opened: list[str] = []
        self.counter = 0x123456789
        mu.hook_add(UC_HOOK_CODE, self._stub, begin=STUBS, end=STUBS + 0xFFFF)
        mu.hook_add(UC_HOOK_CODE, self._game, begin=rand, end=rand)
        if sprintf:
            mu.hook_add(UC_HOOK_CODE, self._game, begin=sprintf, end=sprintf)
        self.call(self.exports["VvfpStartup"], [self.no, 0])

    def _arg(self, i: int) -> int:
        esp = self.mu.reg_read(UC_X86_REG_ESP)
        return struct.unpack("<I", self.mu.mem_read(esp + 4 + 4 * i, 4))[0]

    def _text(self, at: int) -> str:
        raw = bytes(self.mu.mem_read(at, 0x200))
        return raw[:raw.index(b"\0")].decode("latin-1")

    def _game(self, mu, address, size, user_data):
        if address == self.rand_va:
            mu.reg_write(UC_X86_REG_EAX, self.rolls.pop(0))
        else:                                               # the game's sprintf(buffer, list)
            source = bytes(mu.mem_read(self._arg(1), 0x800))
            source = source[:source.index(b"\0")]
            mu.mem_write(self._arg(0), source + b"\0")
            mu.reg_write(UC_X86_REG_EAX, len(source))

    def _stub(self, mu, address, size, user_data):
        name = self.stubs.get(address)
        if name is None:
            return
        arg, ret = self._arg, (lambda v: mu.reg_write(UC_X86_REG_EAX, v & 0xFFFFFFFF))
        if name == b"VirtualQuery":
            at, info = arg(0), arg(1)
            region = next(r for r in mu.mem_regions() if r[0] <= at <= r[1])
            mu.mem_write(info, struct.pack("<7I", region[0], region[0], 0x40, region[1] + 1 - region[0],
                                           0x1000, 0x20, 0x1000000))
            ret(28)
        elif name == b"VirtualAlloc":
            ret(self.heap)
            self.heap += 0x1000
        elif name == b"VirtualProtect":
            mu.mem_write(arg(3), struct.pack("<I", 0x20))
            ret(1)
        elif name in (b"FlushInstructionCache", b"VirtualFree", b"CloseHandle", b"EnterCriticalSection",
                      b"LeaveCriticalSection", b"SetLastError"):
            ret(1)
        elif name == b"GetCurrentProcess":
            ret(INVALID)
        elif name == b"SHGetSpecialFolderPathA":
            mu.mem_write(arg(1), b"C:\\Docs\0")
            ret(1)
        elif name == b"GetModuleFileNameA":
            text = b"C:\\Game\\Game.exe"
            mu.mem_write(arg(1), text + b"\0")
            ret(len(text))
        elif name == b"CreateFileA":
            path = self._text(arg(0))
            self.opened.append(path)
            ret(0x100 if self.record and path.endswith(
                f"\\Virtual Villagers {self.no} Last Names - Save 1.dat") else INVALID)
        elif name == b"ReadFile":
            data = self.record[:arg(2)]
            mu.mem_write(arg(1), data)
            mu.mem_write(arg(3), struct.pack("<I", len(data)))
            ret(1)
        elif name in (b"MultiByteToWideChar", b"GetLastError"):
            ret(0)
        elif name == b"QueryPerformanceCounter":
            mu.mem_write(arg(0), struct.pack("<Q", self.counter))
            ret(1)
        elif name == b"GetTickCount":
            ret(1000)                                       # every birth in the same tick
        elif name in (b"GetCurrentProcessId", b"GetCurrentThreadId"):
            ret(0x1234)
        elif name in (b"FlsGetValue", b"TlsGetValue"):
            ret(PTD)
        else:
            raise AssertionError(f"the companion called {name!r}")

    def call(self, va: int, args: list[int], ecx: int = 0, frame=None) -> None:
        mu = self.mu
        esp = STACK - 0x1000
        back = RETURN
        mu.mem_write(esp, b"\0" * 0x400)
        if frame is not None:
            back, slots = frame
            for offset, value in slots.items():
                mu.mem_write(esp + offset, struct.pack("<I", value))
        mu.mem_write(esp, struct.pack(f"<{1 + len(args)}I", back, *(a & 0xFFFFFFFF for a in args)))
        mu.reg_write(UC_X86_REG_ESP, esp)
        mu.reg_write(UC_X86_REG_ECX, ecx)
        mu.emu_start(va, back, count=5_000_000)
        assert mu.reg_read(UC_X86_REG_ESP) == esp + 4 + 4 * len(args), "stdcall: the arguments popped"

    def born(self, father: str | None, father_looks, mother: str | None, mother_looks, family: int = 9,
             first_roll: int = 3) -> str:
        """The game names a baby at its delivery (the detour gives it the family's last name), then the
        parentage companion hands it to VvfpRuleLastName2 with its parents; returns its name."""
        routine = tln.SITES[self.game][0]
        frame = tln.a_birth(self.game)
        if self.game in tln.RECORD:
            stride, sex_at, family_at, number_at = tln.RECORD[self.game]
            record = DATA + 3 * stride
            self.mu.mem_write(record + sex_at, struct.pack("<i", 1))
            self.mu.mem_write(record + family_at, struct.pack("<i", family))
            self.mu.mem_write(record + number_at, struct.pack("<i", first_roll + 1))
            name_at = DATA + 0x300000
            self.mu.mem_write(name_at, b"\xEE" * 28)
            self.call(routine, [3, name_at], ecx=DATA, frame=frame)
        else:
            villager = DATA + 0x1000
            self.mu.mem_write(villager, b"\0" * 0x40)
            self.rolls = [first_roll]
            self.call(routine, [family], ecx=villager, frame=frame)
            name_at = villager + 0x10
        father_at, mother_at = DATA + 0x380000, DATA + 0x380100
        self.mu.mem_write(father_at, (father or "").encode("latin-1") + b"\0")
        self.mu.mem_write(mother_at, (mother or "").encode("latin-1") + b"\0")
        self.counter += 1
        self.call(self.exports["VvfpRuleLastName2"],
                  [name_at, tln.ROOM[self.game], father_at if father is not None else 0, *father_looks,
                   mother_at if mother is not None else 0, *mother_looks, 1])
        return self._text(name_at)

    def file(self, rule: str | None, lines: str = "") -> None:
        self.record = (f"VVFP LAST NAMES v1 game={self.no}\n" + (f"rule\t{rule}\n" if rule else "")
                       + lines).encode("utf-8")


def shipped() -> bytes:
    return (ROOT / OLDER_DLL).read_bytes()


def older() -> bytes | None:
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "show", f"{OLDER_COMMIT}:{OLDER_DLL}"], capture_output=True,
                             timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 and out.stdout[:2] == b"MZ" else None


DAD, MUM = ("Ago Bahati", (5, 6)), ("Aipi Wanjiko", (7, 8))
FATHER_LIST = "villager\tAgo Bahati\t5\t6\tM\tlist\n"


@unittest.skipUnless(STOCK_PRESENT, "stock executables are not in the release source archive")
class TheShippedDllAtABirth(unittest.TestCase):
    def lists(self, game):
        image = pefile.PE(str(tln.STOCK / tln.EXE[game])).get_memory_mapped_image()
        _, _, last, male, _ = tln.SITES[game]
        return tln.names(image, last), tln.names(image, male)

    def test_random_last_name_from_the_list_in_every_game(self):
        for game in tln.EXE:
            with self.subTest(game=game):
                last, male = self.lists(game)
                first = male[4]
                b = Birth(game, shipped())
                b.file("father", FATHER_LIST)
                draws = 2000
                counts = collections.Counter()
                for _ in range(draws):
                    name = b.born(DAD[0], DAD[1], MUM[0], MUM[1])
                    self.assertTrue(name.startswith(first + " "), name)
                    counts[name[len(first) + 1:]] += 1
                self.assertTrue(b.opened[-1].endswith(f"Virtual Villagers {b.no} Last Names - Save 1.dat"))
                self.assertEqual(set(counts), set(last), "every one of the game's 50, the first and last too")
                self.assertLess(chi_square(counts, last, draws), CHI_50)
                # Twins and triplets: births in the same tick, each its own draw.
                same = sum(b.born(DAD[0], DAD[1], MUM[0], MUM[1]) == b.born(DAD[0], DAD[1], MUM[0], MUM[1])
                           for _ in range(300))
                self.assertLess(same, 25)
                # Her own rule draws too; disagreeing parents use the village's.
                b.file("father", "villager\tAipi Wanjiko\t7\t8\tF\tlist\n")
                self.assertIn(b.born(DAD[0], DAD[1], MUM[0], MUM[1])[len(first) + 1:], last)
                b.file("father", FATHER_LIST + "villager\tAipi Wanjiko\t7\t8\tF\tmother\n")
                self.assertEqual(b.born(DAD[0], DAD[1], MUM[0], MUM[1]), f"{first} Bahati")

    def test_fifty_fifty_twins_each_draw_in_every_game(self):
        for game in tln.EXE:
            with self.subTest(game=game):
                _, male = self.lists(game)
                b = Birth(game, shipped())
                b.file("random")
                dad = differ = 0
                for _ in range(400):
                    one = b.born(DAD[0], DAD[1], MUM[0], MUM[1])
                    dad += one == f"{male[4]} Bahati"
                    differ += one != b.born(DAD[0], DAD[1], MUM[0], MUM[1])
                self.assertTrue(150 < dad < 250, dad)
                self.assertTrue(150 < differ < 250, differ)

    def test_from_the_mother_is_the_mothers_in_every_game(self):
        for game in tln.EXE:
            with self.subTest(game=game):
                last, male = self.lists(game)
                first = male[4]
                b = Birth(game, shipped())
                b.file("mother")
                self.assertEqual([b.born(DAD[0], DAD[1], MUM[0], MUM[1]) for _ in range(3)], [f"{first} Wanjiko"] * 3,
                                 "a delivery's triplets: each the mother's")
                self.assertEqual(b.born(DAD[0], DAD[1], "Aipi Okelani", MUM[1]), f"{first} Okelani",
                                 "renamed before the birth: her name at the birth")
                self.assertEqual(b.born(DAD[0], DAD[1], "Aipi", MUM[1]), first, "no last name: none, never his")
                self.assertEqual(b.born(DAD[0], DAD[1], None, (-1, -1), family=9), f"{first} {last[8]}",
                                 "the mother unknown: the family's stays")
                b.file("father", "villager\tAipi Wanjiko\t7\t8\tF\tmother\n")
                self.assertEqual(b.born(DAD[0], DAD[1], MUM[0], MUM[1]), f"{first} Wanjiko")

    def test_the_older_dll_skips_the_new_rule_safely(self):
        dll = older()
        if dll is None:
            self.skipTest("git history (v1.35.79's DLL) is not available")
        for game in tln.EXE:
            with self.subTest(game=game):
                _, male = self.lists(game)
                b = Birth(game, dll)
                b.file("father", FATHER_LIST)
                self.assertEqual(b.born(DAD[0], DAD[1], MUM[0], MUM[1]), f"{male[4]} Bahati",
                                 "an older build: no own rule, the village's From the father")
                b.file("mother", FATHER_LIST)
                self.assertEqual(b.born(DAD[0], DAD[1], MUM[0], MUM[1]), f"{male[4]} Wanjiko")


if __name__ == "__main__":
    unittest.main()
