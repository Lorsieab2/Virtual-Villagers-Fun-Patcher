"""The Lost Children: "Restore Missing Island Events" (vv2_restore_missing_island_events).

The single-result island events are chosen by 0x434570: rand(28) at 0x434607
is the case, checked through the condition jump table 0x434868 (0x434822
accepts, 0x434824 rejects and draws again -- up to 10 draws, then case 10).
The stock table rejects cases 4, 18, 20 and 26 always.  The row accepts 18
(The Mosquito Swarm), 20 (The Dragonfly Migration) and 26 (Science Awareness
Day), whose bodies in the case runner 0x433600 are complete, and gives the
empty case 4 a body that shows one of three lore pages (strings 698-700) the
game ships without code: The Tattered Diary, The Doctrine of Magicians, The
Doctrine of Naturalists -- popup only, no effect (owner, 2026-10-04).

The case-4 body is written over the trigger's single-result branch for a
positive "kind" (0x42F032-0x42F066), which can never run: its kind is
0x426110(), whose whole body is `xor eax, eax; ret`.  The tests pin that
proof on every render (all three modes, alone and with every public VV2
patch, with Story / Cheat Upgrades' Pick Island Event installed and armed),
the bytes, the odds of the game's own roll, each event's effect run through
the real code, and Pick Island Event's delivery of the three new pages.
"""
from __future__ import annotations

import functools
import random
import struct
import sys
import unittest
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs
from unicorn import UC_HOOK_CODE

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

import story_island_events  # noqa: E402
import vv_fun_patcher as patcher  # noqa: E402
from story_emulator import Process  # noqa: E402

FEATURE_ID = "vv2_restore_missing_island_events"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Story Upgrades.test.dll"
MODES = ("stock", "collection_progression", "immediate_fixed")

# Game addresses.
SELECTOR = 0x434570          # family C chooser (thiscall: kind, magnitude; ret 8)
RUNNER = 0x433600            # family C case runner (thiscall: case, magnitude; ret 8)
CONDITION_TABLE = 0x434868
RUNNER_TABLE = 0x4344F4
ACCEPT, REJECT = 0x434822, 0x434824
EPILOGUE = 0x4344ED
RAND = 0x4031A0
STRING_OF = 0x441680
SPRINTF = 0x4682BD
KIND = 0x426110              # `xor eax, eax; ret`
CAVE, CAVE_END = 0x42F032, 0x42F067
DEAD_END = 0x42F09E          # the negative-kind branch 0x42F069-0x42F09D is dead too
# Never runs: both kind branches; 0x42F067 `jge 0x42F09E` between them is live.
DEAD = frozenset(range(CAVE, CAVE_END)) | frozenset(range(CAVE_END + 2, DEAD_END))
PAGE_SITE = 0x42F034
STRIDE = 0xE48C
RECORDS = 256
FIRST = 0x30
RESTORED = {18: 0x2C2, 20: 0x2AD, 26: 0x2B7}
PAGES = {0: 698, 1: 699, 2: 700}
PAGE_TITLES = ("The Tattered Diary", "The Doctrine of Magicians", "The Doctrine of Naturalists")
# Conditional cases and the routine each one's condition calls.
CONDITIONAL = {8: 0x426160, 11: 0x4261D0, 14: 0x4261D0, 15: 0x4261D0, 16: 0x425860,
               17: 0x4261D0, 21: 0x44B310, 25: 0x44B310}


@functools.lru_cache(maxsize=None)
def _vv2():
    return next(b for b in patcher.load_builds() if b.id == "vv2")


@functools.lru_cache(maxsize=None)
def _public_vv2_ids() -> tuple[str, ...]:
    return tuple(p.id for p in patcher.load_public_fun_patches()
                 if p.game_id == "vv2" and p.id not in patcher.EXPERIMENTAL_FUN_PATCH_IDS)


@functools.lru_cache(maxsize=None)
def _render(mode: str, ids: tuple[str, ...]) -> bytes:
    data, _ = patcher.render_patched_bytes(STOCK, _vv2(), mode, list(ids))
    return bytes(data)


def _all(mode: str) -> bytes:
    return _render(mode, _public_vv2_ids())


def _all_but_row(mode: str) -> bytes:
    return _render(mode, tuple(i for i in _public_vv2_ids() if i != FEATURE_ID))


def _row_only(mode: str) -> bytes:
    return _render(mode, (FEATURE_ID,))


def _feature():
    return next(p for p in patcher.load_fun_patches() if p.id == FEATURE_ID)


def _spans() -> set[int]:
    out = set()
    for p in _feature().raw["patches"]:
        start = int(p["offset"], 16)
        out |= set(range(start, start + len(bytes.fromhex(p["after"]))))
    return out


def _changed(before: bytes, after: bytes) -> set[int]:
    field = pefile.PE(data=after, fast_load=True).OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    return {i for i in range(min(len(before), len(after)))
            if before[i] != after[i] and not field <= i < field + 4}


def _u32(data: bytes, va: int) -> int:
    return struct.unpack_from("<I", data, va - 0x400000)[0]


def _strings(data: bytes) -> dict[int, str]:
    """The game's English string table (0x496300: id, English, German)."""
    pe = pefile.PE(data=data, fast_load=True)
    image = pe.get_memory_mapped_image()
    out = {}
    for i in range(0x36C):
        sid, english, _ = struct.unpack_from("<3I", image, 0x96300 + 12 * i)
        end = image.index(b"\0", english - 0x400000)
        out[sid] = image[english - 0x400000:end].decode("latin-1")
    return out


# ---------------------------------------------------------------------------
# The row
# ---------------------------------------------------------------------------

class RowTests(unittest.TestCase):
    def test_row_named_described_and_on_by_default(self):
        sys.path.insert(0, str(ROOT / "src"))
        import vv_fun_patcher_gui as gui
        row = {p.id: p for p in patcher.load_public_fun_patches()}[FEATURE_ID]
        self.assertEqual(row.game_id, "vv2")
        self.assertEqual(row.raw["name"], "Restore Missing Island Events")
        self.assertIn("**Needs no other patch.**", row.raw["description"])
        for title in ("The Mosquito Swarm", "The Dragonfly Migration", "Science Awareness Day",
                      *PAGE_TITLES):
            self.assertIn(title, row.raw["description"])
        self.assertTrue(gui.default_fun_patch_selection(FEATURE_ID))
        self.assertTrue(gui.owners_default_fun_patch_selection(FEATURE_ID))
        self.assertTrue(gui.select_all_fun_patch_selection(FEATURE_ID))
        self.assertEqual(row.raw.get("companion_files"), [])

    def test_manifest_is_the_generators_output(self):
        import importlib
        import json
        import tempfile
        gen = importlib.import_module("build_vv2_restore_missing_island_events_feature")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "row.json"
            old = gen.OUT
            gen.OUT = out
            try:
                gen.main()
            finally:
                gen.OUT = old
            self.assertEqual(json.loads(out.read_text(encoding="utf-8")),
                             json.loads((ROOT / "data" / f"{FEATURE_ID}_feature.json").read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# Bytes, modes and every public patch
# ---------------------------------------------------------------------------

class ByteTests(unittest.TestCase):
    def test_exact_stock_bytes_and_patched_bytes(self):
        stock = STOCK.read_bytes()
        for p in _feature().raw["patches"]:
            start = int(p["offset"], 16)
            before = bytes.fromhex(p["before"])
            self.assertEqual(stock[start:start + len(before)], before, p["purpose"])
        table = [_u32(stock, CONDITION_TABLE + 4 * i) for i in range(28)]
        self.assertEqual({i for i, t in enumerate(table) if t == REJECT}, {4, 18, 20, 26})
        self.assertEqual(_u32(stock, RUNNER_TABLE + 16), EPILOGUE)

    def test_row_alone_changes_only_its_spans_in_every_mode(self):
        stock = STOCK.read_bytes()
        for mode in MODES:
            with self.subTest(mode=mode):
                base = _render(mode, ())
                data = _row_only(mode)
                self.assertLessEqual(_changed(base, data), _spans())
                for p in _feature().raw["patches"]:
                    start = int(p["offset"], 16)
                    after = bytes.fromhex(p["after"])
                    self.assertEqual(data[start:start + len(after)], after)
                for i in (4, 18, 20, 26):
                    self.assertEqual(_u32(data, CONDITION_TABLE + 4 * i), ACCEPT)
                self.assertEqual(_u32(data, RUNNER_TABLE + 16), CAVE)
                self.assertEqual(stock[0x26110:0x26113], data[0x26110:0x26113])

    def test_every_public_vv2_patch_no_overlap_in_every_mode(self):
        self.assertIn(FEATURE_ID, _public_vv2_ids())
        for mode in MODES:
            with self.subTest(mode=mode):
                without = _all_but_row(mode)
                full = _all(mode)
                self.assertLessEqual(_changed(without, full), _spans(),
                                     "the row changes a byte outside its spans")
                for p in _feature().raw["patches"]:
                    start = int(p["offset"], 16)
                    after = bytes.fromhex(p["after"])
                    self.assertEqual(full[start:start + len(after)], after)
                # And no other row's bytes in these spans differ from stock.
                stock = STOCK.read_bytes()
                for i in _spans():
                    self.assertEqual(without[i], stock[i])

    def test_no_runtime_detour_touches_the_row_or_the_dead_branch_proof(self):
        """No companion of any public VV2 row writes inside the row's spans,
        at 0x426110, or between 0x426110's call (0x42EEF7) and the branch
        (0x42F030) -- except Story / Cheat Upgrades' two family rolls, plain
        cdecl calls that keep edi (tested in DeadBranchTests)."""
        allowed = {0x42EF28, 0x42EF4A}
        spans = {0x400000 + i for i in _spans()}
        for p in patcher.load_public_fun_patches():
            if p.game_id != "vv2":
                continue
            for d in p.raw.get("runtime_detours", []):
                va = int(d["va"], 16)
                n = len(bytes.fromhex(d["stock_bytes"]))
                touched = set(range(va, va + n))
                with self.subTest(row=p.id, va=hex(va)):
                    self.assertFalse(touched & spans)
                    self.assertFalse(touched & set(range(KIND, KIND + 3)))
                    if touched & set(range(0x42EEF7, 0x42F032)):
                        self.assertIn(va, allowed)


# ---------------------------------------------------------------------------
# The dead branch the case-4 body replaces
# ---------------------------------------------------------------------------

class DeadBranchTests(unittest.TestCase):
    def test_kind_is_always_zero_and_nothing_reaches_the_branch(self):
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        for mode in MODES:
            for name, data in (("row only", _row_only(mode)), ("all", _all(mode))):
                with self.subTest(mode=mode, render=name):
                    pe = pefile.PE(data=data)
                    image = pe.get_memory_mapped_image()
                    self.assertEqual(image[KIND - 0x400000:KIND - 0x400000 + 3], b"\x33\xC0\xC3")
                    # The kind's only producer and consumer.
                    code = image[0x2EEF2:0x2F032]
                    listing = list(md.disasm(code, 0x42EEF2))
                    # 0x42EEF2 mov ecx, [esi+0x10]; 0x42EEF5 mov ebp, eax;
                    # 0x42EEF7 call 0x426110; 0x42EEFC cmp ebp, -1; 0x42EEFF mov edi, eax
                    self.assertEqual(listing[2].mnemonic, "call")
                    self.assertEqual(listing[2].op_str, hex(KIND))
                    self.assertEqual((listing[4].mnemonic, listing[4].op_str), ("mov", "edi, eax"))
                    # Every way to the single-result branch: 0x42EF00-0x42EF71 (the
                    # family rolls; 0x42EF55 and 0x42EF6C jump to 0x42EFF9) and
                    # 0x42EFF9-0x42F027.  Nothing there writes edi (the calls are
                    # cdecl / thiscall, which keep it).
                    on_path = [ins for ins in listing[5:]
                               if 0x42EF00 <= ins.address < 0x42EF72 or 0x42EFF9 <= ins.address < 0x42F028]
                    self.assertGreater(len(on_path), 30)
                    for ins in on_path:
                        self.assertFalse(ins.op_str.startswith("edi,") and ins.mnemonic != "cmp",
                                         f"0x{ins.address:X} {ins.mnemonic} {ins.op_str}")
                    self.assertEqual(image[0x2F028:0x2F032].hex().upper(), "3BFB898DE0EA02007E35")
                    # No branch, call or pointer anywhere reaches the dead branches.
                    dead = DEAD
                    pointers = []
                    for section in pe.sections:
                        start = section.VirtualAddress
                        blob = image[start:start + section.Misc_VirtualSize]
                        executable = bool(section.Characteristics & 0x20000000)
                        for i in range(len(blob) - 4):
                            va = 0x400000 + start + i
                            if va in dead or (va + 5 > CAVE and va < DEAD_END):
                                continue
                            word = struct.unpack_from("<I", blob, i)[0]
                            if word in dead:
                                pointers.append((va, word))
                            if not executable:
                                continue
                            b = blob[i]
                            if b in (0xE8, 0xE9):
                                self.assertNotIn(va + 5 + struct.unpack_from("<i", blob, i + 1)[0], dead,
                                                 f"rel32 at 0x{va:X}")
                            if b == 0x0F and 0x80 <= blob[i + 1] <= 0x8F and i + 6 <= len(blob):
                                self.assertNotIn(va + 6 + struct.unpack_from("<i", blob, i + 2)[0], dead,
                                                 f"jcc at 0x{va:X}")
                            if 0x70 <= b <= 0x7F or b == 0xEB:
                                target = va + 2 + struct.unpack_from("<b", blob, i + 1)[0]
                                if target in dead:
                                    # a byte that merely looks like a short jump: only
                                    # instructions of the trigger can be that close
                                    self.assertFalse(0x42EF00 <= va < 0x42F120,
                                                     f"short jump at 0x{va:X}")
                    # The only pointer in: the row's own runner-table entry for case 4.
                    self.assertEqual(pointers, [(RUNNER_TABLE + 16, CAVE)])

    @unittest.skipUnless(TEST_DLL.is_file(), "Story test DLL not built")
    def test_trigger_skips_the_dead_branch_with_every_patch_and_every_pick(self):
        """Run the trigger's real code (all public VV2 patches, Story's Pick
        Island Event installed) from the kind's call to the single-result
        popup, for natural rolls, a pick of each family and a lore page."""
        for mode in MODES:
            data = _all(mode)
            for label, pick, rolls in (("natural C", None, (60, 10)),
                                       ("natural B", None, (60, 70)),
                                       ("pick C", 18, ()), ("pick page", 29, ()),
                                       ("pick A", (1 << 6) | 5, ()),
                                       ("pick B", (2 << 6) | 3, ())):
                with self.subTest(mode=mode, run=label):
                    proc, world, owner = _trigger_process(data, pick, rolls)
                    seen = []
                    proc.mu.hook_add(UC_HOOK_CODE, lambda mu, a, s, u: seen.append(a) if a in DEAD else None,
                                     None, CAVE, DEAD_END - 1)
                    # The trigger's own frame is 0x5150 bytes above esp.
                    proc.call(0x42EEF2, [], regs={"esi": owner, "eax": 0, "ebx": 0,
                                                  "esp": 0x0FF00000 - 0x8000}, until=0x42F1F9)
                    self.assertEqual(seen, [], "the dead branch ran")
                    family = {"natural C": "C", "pick C": "C", "pick page": "C", "natural B": "B",
                              "pick A": "A", "pick B": "B"}[label]
                    expect = {"C": (0x4348E0, 2), "B": (0x439DD0,), "A": (0x422380,)}[family]
                    self.assertEqual(proc.popups[0], expect)


def _trigger_process(data: bytes, pick, rolls):
    proc = Process(data, TEST_DLL)
    world = proc.alloc(0x31000)
    proc.put32(0x4997BC, world)
    pool = proc.alloc(FIRST + STRIDE * RECORDS + 0x100)
    proc.put32(0x499F24, pool)
    adult = pool + FIRST
    proc.write(adult, b"\1")
    proc.put32(adult + 0x4FC, 100)
    proc.put32(adult + 0x500, 400)
    proc.put32(adult + 0x504, 400)                 # +0x534 equals the age (0x42EF1A)
    proc.put32(world + 0x2E51C, 3)                 # not the first island event
    owner = proc.alloc(0x200)
    proc.put32(owner + 0x10, world)
    proc.put32(owner + 0x18, proc.alloc(0x100))
    proc.put32(owner + 0x20, pool)
    proc.stub(0x403200, lambda p: (1_700_000_000, 0))  # clock
    proc.stub(0x43F010, lambda p: (0, 4))           # sound
    proc.stub(0x425860, lambda p: (9, 0))           # population
    # The popups' constructors, show call (0x401AD0, two arguments) and
    # destructors; the single-result constructor (kind, magnitude) is recorded.
    proc.popups = []
    for popup in (0x437180, 0x433190, 0x41F040, 0x422380, 0x439DD0):
        proc.stub(popup, lambda p, a=popup: (p.popups.append((a,)) or 0, 0))
    proc.stub(0x401AD0, lambda p: (0, 8))
    proc.stub(0x4348E0, lambda p: (p.popups.append((0x4348E0, p.arg(0))) or 0, 8))
    proc.stub(RAND, _script(rolls))
    proc.export("VvfpStoryInstall", 2)
    proc.export("VvfpStoryProbeSetTick", 0)
    if pick is not None:
        position = [e["slot"] for e in story_island_events.EVENTS["vv2"]].index(pick)
        proc.export("VvfpStoryProbeSetPick", 2, position, 0)
    return proc, world, owner


def _script(values):
    values = list(values)

    def rand(proc):
        bound = proc.arg(0)
        value = values.pop(0) if values else 0
        return min(value, bound - 1), 0
    return rand


# ---------------------------------------------------------------------------
# The chooser's own odds
# ---------------------------------------------------------------------------

class _Chooser:
    """The real selector 0x434570 on a rendered image.  Every conditional
    case's condition answers `conditions`; rand answers a script (then 0)."""

    def __init__(self, data: bytes, conditions: bool):
        self.proc = Process(data)
        p = self.proc
        self.event = p.alloc(0x5100)
        self.pool = p.alloc(FIRST + STRIDE * RECORDS + 0x100)
        p.put32(self.event + 0x50A8, self.pool)
        p.put32(self.event + 0x50A4, p.alloc(0x31000))
        answer = 1 if conditions else 0
        for routine in set(CONDITIONAL.values()):
            if routine == 0x425860:
                p.stub(routine, lambda pr, a=answer: (61 if a else 0, 0))
            else:
                p.stub(routine, lambda pr, a=answer: (a, 0))
        if conditions:
            # Where Are The Infants?: a living mother (+0x540 set) aged 18 or over.
            mother = self.pool + FIRST
            p.write(mother, b"")
            p.put32(mother + 0x4FC, 100)
            p.put32(mother + 0x500, 0x168)
            p.put32(mother + 0x510, 400)
        self.cases = []
        p.stub(RUNNER, lambda pr: (self.cases.append(pr.arg(0)) or 0, 8))

    def choose(self, draws) -> int:
        self.proc.stub(RAND, _script(draws))
        self.proc.call(SELECTOR, [2, 5], ecx=self.event)
        return self.cases[-1]


def _accepted(data: bytes, conditions: bool) -> set[int]:
    chooser = _Chooser(data, conditions)
    # First draw v; if it is rejected the second draw (case 0, always valid) is taken.
    return {v for v in range(28) if chooser.choose((v, 0)) == v}


def _odds(accepted: set[int]) -> dict[int, float]:
    """Exact: each draw is 1 in 28; a rejected draw draws again, up to 10
    draws, then case 10."""
    reject = (28 - len(accepted)) / 28
    each = sum(reject ** i for i in range(10)) / 28
    odds = {k: each for k in accepted}
    odds[10] = odds.get(10, 0) + reject ** 10
    return odds


class OddsTests(unittest.TestCase):
    def test_restored_cases_are_accepted_like_every_unconditional_case(self):
        stock = _render("collection_progression", ())
        unconditional = set(range(28)) - set(CONDITIONAL) - {4, 18, 20, 26}
        for conditions in (False, True):
            with self.subTest(conditions=conditions):
                base = _accepted(stock, conditions)
                self.assertEqual(base, unconditional | (set(CONDITIONAL) if conditions else set()))
                for mode in MODES:
                    for data in (_row_only(mode), _all(mode)):
                        self.assertEqual(_accepted(data, conditions), base | {4, 18, 20, 26})

    def test_each_restored_event_has_a_typical_events_chance_and_each_page_a_third(self):
        for conditions in (False, True):
            with self.subTest(conditions=conditions):
                odds = _odds(_accepted(_all("collection_progression"), conditions))
                typical = odds[22]                       # The West Wind: no condition
                for case in RESTORED:
                    self.assertAlmostEqual(odds[case], typical, places=12)
                # Case 4 is as likely as a typical event; rand(3) splits it.
                self.assertAlmostEqual(odds[4], typical, places=12)
                self.assertAlmostEqual(sum(odds.values()), 1.0, places=12)

    def test_monte_carlo_of_the_real_selector_and_page_roll(self):
        """Random draws through the real selector and the real case-4 body:
        the restored events land as often as The West Wind, each page about a
        third of that."""
        data = _all("collection_progression")
        rng = random.Random(20261004)
        chooser = _Chooser(data, conditions=False)
        p = chooser.proc
        mgr, lang = p.alloc(0x10), p.alloc(0x10)
        p.put32(mgr + 4, lang)
        p.put32(chooser.event + 0x50AC, mgr)
        p.stub(SPRINTF, lambda pr: (pr.write(pr.arg(0), pr.cstring(pr.arg(1), 4096).encode("latin-1") + b"\0") or 0, 0))
        p.stub(RAND, lambda pr: (rng.randrange(pr.arg(0)), 0))
        landed = {k: 0 for k in (4, 18, 20, 22, 26)}
        pages = {t: 0 for t in PAGE_TITLES}
        trials = 5600
        for _ in range(trials):
            p.call(SELECTOR, [2, 5], ecx=chooser.event)
            case = chooser.cases[-1]
            if case in landed:
                landed[case] += 1
            if case == 4:
                # The real case-4 body (the other bodies start villager routines).
                runner = p.stubs.pop(RUNNER)
                p.call(RUNNER, [4, 5], ecx=chooser.event)
                p.stubs[RUNNER] = runner
                text = p.cstring(chooser.event + 0x277F, 4096)
                pages[next(t for t in PAGE_TITLES if t in text)] += 1
        expected = _odds(_accepted(data, False))[22] * trials
        for k in (18, 20, 26, 4):
            self.assertLess(abs(landed[k] - expected), 5 * expected ** 0.5, (k, landed[k], expected))
        for title, n in pages.items():
            self.assertLess(abs(n - expected / 3), 5 * (expected / 3) ** 0.5, (title, n))


# ---------------------------------------------------------------------------
# Each event's effect, run through the real case runner
# ---------------------------------------------------------------------------

class _Village:
    """The real runner 0x433600 with a pool of villagers; villager routines
    are recorded, not run (they start animations)."""

    def __init__(self, data: bytes, rolls=()):
        self.proc = p = Process(data)
        self.event = p.alloc(0x5100)
        self.pool = p.alloc(FIRST + STRIDE * RECORDS + 0x100)
        self.world = p.alloc(0x31000)
        p.put32(self.event + 0x50A8, self.pool)
        p.put32(self.event + 0x50A4, self.world)
        mgr, lang = p.alloc(0x10), p.alloc(0x10)
        p.put32(mgr + 4, lang)                      # [lang] == 0: English
        p.put32(self.event + 0x50AC, mgr)
        self.calls = []
        for routine, pop in ((0x4492A0, 4), (0x451690, 4), (0x44AEA0, 4)):
            p.stub(routine, lambda pr, r=routine, n=pop: (self.calls.append((r, pr.arg(0))) or 0, n))
        p.stub(SPRINTF, lambda pr: (pr.write(pr.arg(0), pr.cstring(pr.arg(1), 4096).encode("latin-1") + b"\0") or 0, 0))
        self.rolls = []
        script = list(rolls)

        def rand(pr):
            bound = pr.arg(0)
            value = script.pop(0) if script else 0
            self.rolls.append(bound)
            return min(value, bound - 1), 0
        p.stub(RAND, rand)

    def add(self, i, *, age, health=80, sick=0, pregnant=0, research=10, task=7):
        r = self.pool + i * STRIDE
        p = self.proc
        p.write(r + 0x30, b"\1")
        p.put32(r + 0x52C, health)
        p.put32(r + 0x530, age)
        p.put32(r + 0x53C, sick)
        p.put32(r + 0x540, pregnant)
        p.put32(r + 0x7F4, research)
        p.put32(r + 0x7E0, task)

    def field(self, i, offset) -> int:
        return self.proc.u32(self.pool + i * STRIDE + offset)

    def run(self, case: int) -> str:
        self.proc.call(RUNNER, [case, 5], ecx=self.event)
        return self.proc.cstring(self.event + 0x277F, 4096)

    def state(self) -> bytes:
        """The villagers and the world (not the popup's own text)."""
        return self.proc.read(self.pool, FIRST + STRIDE * 8) + self.proc.read(self.world, 0x31000)


class EffectTests(unittest.TestCase):
    def setUp(self):
        self.data = _all("collection_progression")
        self.text = _strings(self.data)

    def test_the_mosquito_swarm(self):
        # rolls: one rand(100) per living villager (sick below 20).
        v = _Village(self.data, rolls=(5, 50, 19, 20))
        v.add(0, age=400)                  # sick, swims
        v.add(1, age=400, pregnant=410)    # pregnant: stays
        v.add(2, age=100)                  # child, sick: does not swim
        v.add(3, age=600, health=0)        # dead: nothing
        v.add(4, age=300)                  # adult (300 > 280), healthy, swims
        text = v.run(18)
        self.assertEqual(text, self.text[0x2C2])
        self.assertEqual([v.field(i, 0x53C) for i in range(5)], [1, 0, 1, 0, 0])
        swims = [i for r, i in v.calls if r == 0x451690]
        self.assertEqual(swims, [0, 4])
        self.assertEqual([v.field(i, 0x7E0) for i in range(5)], [0, 0, 0, 7, 0])
        self.assertEqual([v.field(i, 0x52C) for i in range(5)], [80, 80, 80, 0, 80], "no damage")

    def test_the_dragonfly_migration(self):
        v = _Village(self.data)
        v.add(0, age=400, health=12, sick=1)
        v.add(1, age=100, health=99, sick=0)
        v.add(2, age=600, health=0, sick=1)  # dead: untouched
        text = v.run(20)
        self.assertEqual(text, self.text[0x2AD])
        self.assertEqual([v.field(i, 0x52C) for i in range(3)], [100, 100, 0])
        self.assertEqual([v.field(i, 0x53C) for i in range(3)], [0, 0, 1])

    def test_science_awareness_day(self):
        # rolls per living villager: chance rand(100) (< 100 always), then rand(5) + 3.
        v = _Village(self.data, rolls=(0, 4, 0, 0, 0, 2))
        v.add(0, age=100, research=10)       # child: +7
        v.add(1, age=200, research=98)       # child: +3, capped at 100
        v.add(2, age=400, research=10)       # adult: unchanged
        v.add(3, age=150, research=50, health=0)  # dead child: unchanged
        text = v.run(26)
        self.assertEqual(text, self.text[0x2B7])
        self.assertEqual([v.field(i, 0x7F4) for i in range(4)], [17, 100, 10, 50])
        self.assertEqual(sorted(i for r, i in v.calls if r == 0x44AEA0), [0, 1, 2])

    def test_the_lore_pages_show_their_text_and_change_nothing(self):
        for page in range(3):
            with self.subTest(page=PAGE_TITLES[page]):
                v = _Village(self.data, rolls=(page,))
                v.add(0, age=400)
                v.add(1, age=100)
                before = v.state()
                text = v.run(4)
                after = v.state()
                self.assertEqual(text, self.text[PAGES[page]])
                self.assertIn(PAGE_TITLES[page], text.splitlines()[0])
                self.assertEqual(v.rolls, [3])
                self.assertEqual(before, after, "the page changed a villager or the world")
                self.assertEqual(v.calls, [])

    def test_case_4_is_still_empty_without_the_row(self):
        v = _Village(_all_but_row("collection_progression"))
        self.assertEqual(v.run(4), "")
        self.assertEqual(v.rolls, [])


# ---------------------------------------------------------------------------
# Story / Cheat Upgrades' Pick Island Event
# ---------------------------------------------------------------------------

@unittest.skipUnless(TEST_DLL.is_file(), "Story test DLL not built")
class PickTests(unittest.TestCase):
    def _proc(self, data, pick):
        proc, world, _ = _trigger_process(data, None, ())
        installed = proc.export("VvfpStoryProbeInstallPageRoll")
        if pick is not None:
            position = [e["slot"] for e in story_island_events.EVENTS["vv2"]].index(pick)
            proc.export("VvfpStoryProbeSetPick", 2, position, 0)
        return proc, installed

    def test_the_three_pages_are_listed(self):
        slots = {e["slot"]: e for e in story_island_events.EVENTS["vv2"]}
        for k, title in enumerate(PAGE_TITLES):
            self.assertEqual(slots[28 + k]["title"], title)
            self.assertIn("Restore Missing Island Events", slots[28 + k]["requires"])

    def test_a_picked_page_is_delivered_as_case_4_with_its_page(self):
        for mode in MODES:
            for k in range(3):
                with self.subTest(mode=mode, page=PAGE_TITLES[k]):
                    proc, installed = self._proc(_all(mode), 28 + k)
                    self.assertEqual(installed, 1)
                    event = proc.alloc(0x5100)
                    pool = proc.u32(0x499F24)
                    proc.put32(event + 0x50A8, pool)
                    proc.put32(event + 0x50A4, proc.u32(0x4997BC))
                    mgr, lang = proc.alloc(0x10), proc.alloc(0x10)
                    proc.put32(mgr + 4, lang)
                    proc.put32(event + 0x50AC, mgr)
                    proc.stub(SPRINTF, lambda pr: (pr.write(pr.arg(0), pr.cstring(pr.arg(1), 4096).encode("latin-1") + b"\0") or 0, 0))
                    proc.stub(RAND, _script((7, 2, 1, 0)))   # natural rolls would give case 7
                    proc.call(SELECTOR, [2, 5], ecx=event)
                    text = proc.cstring(event + 0x277F, 4096)
                    self.assertEqual(text, _strings(_all(mode))[PAGES[k]])
                    self.assertEqual(proc.export("VvfpStoryProbeArmedSlot"), 0xFFFFFFFF, "pick taken")
                    # The next case-4 page is the game's own roll again.
                    proc.stub(RAND, _script((4, 2)))
                    proc.call(SELECTOR, [2, 5], ecx=event)
                    self.assertEqual(proc.cstring(event + 0x277F, 4096), _strings(_all(mode))[PAGES[2]])

    def test_restored_events_are_ordinary_with_the_row_and_unlocked_without(self):
        positions = {e["slot"]: i for i, e in enumerate(story_island_events.EVENTS["vv2"])}
        for data, expect_restored in ((_all("stock"), 1), (_all_but_row("stock"), 0)):
            proc, installed = self._proc(data, None)
            self.assertEqual(installed, expect_restored)
            for slot in (18, 20, 26, 28, 29, 30):
                with self.subTest(restored=expect_restored, slot=slot):
                    self.assertEqual(proc.export("VvfpStoryProbePossible", 2, positions[slot]),
                                     expect_restored)

    def test_the_page_site_is_left_alone_without_the_row(self):
        data = _all_but_row("collection_progression")
        proc, installed = self._proc(data, None)
        self.assertEqual(installed, 0)
        self.assertEqual(proc.read(PAGE_SITE - 2, 0x35), data[0x2F032:0x2F067])


if __name__ == "__main__":
    unittest.main()
