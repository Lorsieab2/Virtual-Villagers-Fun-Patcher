"""A New Home and The Lost Children: one partner per catch-up try, with or without Birth Control.

The owner (2026-11-21): Birth Control must work more or less the same in all five games, so in A New Home and The
Lost Children the catch-up embrace pairs ONE partner per try whether Birth Control is ticked or not, as in The Secret
City, The Tree of Life and New Believers.  A man who tries picks his one partner from every woman who can pair; a
woman who tries picks hers from every man who can.  One conception roll per try.  Birth Control only changes how often
a Children-choice villager with Parenting ticked tries (every such job turn instead of 6 in 100), and bounds the
partner under 50 as it does in the later games.

The catch-up embrace is one step of each game's step runner (A New Home 0x446C70 opcode 9, The Lost Children
0x464680 opcode 12), reached only from the catch-up job turn.  Stock runs two scans over all 256 villager slots and
calls the pregnancy writer for every villager who passes, never stopping at a conception, so one man's job turn can
make every eligible woman pregnant.  The patcher's automatic safety rows (every mode) replace the start of the first
scan with a one-partner pick using the stock scans' own eligibility, and end the embrace after that one attempt.
Live play already pairs one partner at a time (A New Home 0x43DAD0, The Lost Children 0x44F610) and is not changed.

The step runner is EMULATED FROM ITS ENTRY, in the stock executable and in the executable the patcher renders in all
three population modes, with and without Birth Control.  Its leaf calls (the RNG, the skill check, the room check, the
best-skill lookup, the pregnancy writer, the queue pop and the update) are scripted; any other call into the game's
code stops the run and fails the test.
"""
from __future__ import annotations

import json
import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import load_builds, load_fun_patches, render_patched_bytes, resolve_fun_patch_ids  # noqa: E402

STACK_TOP = 0x0F000000
SENTINEL = 0x0E000000
ARRAY = 0x20000000          # the runner's this: the villager array (record_base 0 in both games)
GLOBALS = 0x40000000
MODES = ("stock", "collection_progression", "immediate_fixed")
ADULT, YOUNG, OLD = 600, 300, 1000          # internal age units: 30, 15, 50 years
MALE, FEMALE = 1, 2

G = {
    "vv1": dict(runner=0x446C70, step=9, stride=0x3D8, alive=0x28, steptype=0x44, health=0x344, age=0x348, sex=0x350,
                sick=0x354, preg=0x358, look=0x36C, parenting=0x3BC, gptr=0x3E010, food=0xA2EC, food_ok=400,
                tech=0xA2DC, writer=0x43BBC0, writer_return=0x44723D, pick_return=0x446F0F, text_end=0x457000,
                calls={0x402F10: ("rand", 0), 0x43D440: ("skill", 8), 0x43A1A0: ("room", 0), 0x43B520: ("best", 8),
                       0x43BBC0: ("writer", 16), 0x445C50: ("pop", 4), 0x439470: ("update", 4)},
                runner_span=(0x446C70, 0x447294),
                safety=((0x46E70, 208), (0x4723D, 8)), overlays=((0x46ECE, 8),)),
    "vv2": dict(runner=0x464680, step=12, stride=0xE48C, alive=0x30, steptype=0x4C, health=0x52C, age=0x530,
                sex=0x538, sick=0x53C, preg=0x540, look=0x548, parenting=0x7E4, gptr=0xE574D4, food=0x2EAA4,
                food_ok=300, tech=0x2EA8C, writer=0x44B980, writer_return=0x464C52, pick_return=0x464901,
                text_end=0x474000,
                calls={0x4031A0: ("rand", 0), 0x44E170: ("skill", 8), 0x44B310: ("room", 0), 0x44B4D0: ("best", 8),
                       0x44B980: ("writer", 28), 0x449380: ("pop", 4), 0x4492A0: ("update", 4)},
                runner_span=(0x464680, 0x464CC8),
                safety=((0x64847, 231), (0x64C52, 5)), overlays=((0x6487E, 25), (0x648C0, 8))),
}
BUILDS = {build.id: build for build in load_builds()}
STOCK = {g: ROOT / "research" / "stock-executables" / BUILDS[g].input_name for g in G}
STOCK_PRESENT = all(path.is_file() for path in STOCK.values())
_RENDERS: dict[tuple[str, bool, str, bool], bytes] = {}


def rendered(game: str, birth_control: bool, mode: str = "stock", origins: bool = False) -> bytes:
    key = (game, birth_control, mode, origins)
    if key not in _RENDERS:
        wanted = ([f"{game}_birth_control"] if birth_control else []) + (
            [f"{game}_enable_origins_exclusive_features"] if origins else [])
        ids = resolve_fun_patch_ids(wanted, game_id=game, patches=load_fun_patches()) if wanted else []
        data, _ = render_patched_bytes(STOCK[game], BUILDS[game], mode, ids)
        _RENDERS[key] = bytes(data)
    return _RENDERS[key]


class Villager:
    def __init__(self, sex: int, age: int = ADULT, alive: bool = True, health: int = 100, sick: bool = False,
                 pregnant: bool = False):
        self.sex, self.age, self.alive, self.health, self.sick, self.pregnant = sex, age, alive, health, sick, pregnant


class Runner:
    """One game's step runner, run from its entry for the villager in slot 0 with one embrace step queued."""

    def __init__(self, game: str, exe: bytes):
        self.g = G[game]
        pe = pefile.PE(data=exe, fast_load=True)
        base = pe.OPTIONAL_HEADER.ImageBase
        mu = Uc(UC_ARCH_X86, UC_MODE_32)
        size = (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF
        mu.mem_map(base, size)
        mu.mem_write(base, exe[:pe.OPTIONAL_HEADER.SizeOfHeaders])
        for section in pe.sections:
            raw = exe[section.PointerToRawData:section.PointerToRawData + section.SizeOfRawData]
            mu.mem_write(base + section.VirtualAddress, raw[:max(0, size - section.VirtualAddress)])
        mu.mem_map(STACK_TOP - 0x100000, 0x100000)
        mu.mem_map(SENTINEL, 0x1000)
        mu.mem_map(ARRAY, 0x1000000)
        mu.mem_map(GLOBALS, 0x100000)
        mu.hook_add(UC_HOOK_CODE, self._hook)
        self.mu = mu

    def _w(self, address: int, value: int) -> None:
        self.mu.mem_write(address, struct.pack("<i", value))

    def _hook(self, mu, address, size, user_data):
        if address == SENTINEL:
            self.returned = True
            mu.emu_stop()
            return
        if not 0x401000 <= address < self.g["text_end"] or self.g["runner_span"][0] <= address < self.g["runner_span"][1]:
            return
        leaf = self.g["calls"].get(address)
        if leaf is None:
            self.unexpected.append(address)
            mu.emu_stop()
            return
        name, pops = leaf
        sp = mu.reg_read(UC_X86_REG_ESP)
        (ret,) = struct.unpack("<I", mu.mem_read(sp, 4))
        value = 0
        if name == "rand":
            (bound,) = struct.unpack("<i", mu.mem_read(sp + 4, 4))
            if ret == self.g["pick_return"]:     # the partner pick, rand(count)
                value = self.pick
                self.picks.append(bound)
            else:
                value = self.rng(bound)
                self.rolls.append(bound)
        elif name in ("skill", "room"):
            value = 1
        elif name == "best":
            (out,) = struct.unpack("<I", mu.mem_read(sp + 8, 4))
            self._w(out, 0)
        elif name == "writer":
            (mother,) = struct.unpack("<i", mu.mem_read(sp + 4, 4))
            self.writes.append((mother, ret))
            self._w(ARRAY + mother * self.g["stride"] + self.g["preg"], 7)
        elif name == "pop":
            self._w(ARRAY + self.g["steptype"], 0)
        mu.reg_write(UC_X86_REG_EAX, value)
        mu.reg_write(UC_X86_REG_ESP, sp + 4 + pops)
        mu.reg_write(UC_X86_REG_EIP, ret)

    def embrace(self, village: list[Villager], *, pick: int = 0, conceive: bool = True, food: int | None = None,
                refuse: bool = False) -> "Runner":
        """Slot 0 initiates.  The RNG answers `pick` to the partner pick, 0 or 299 to the conception roll, 99
        (refused) or 0 to the low-food refusal, and 0 to the child's skill points."""
        g, mu = self.g, self.mu
        mu.mem_write(ARRAY, bytes(0x1000000))
        mu.mem_write(GLOBALS, bytes(0x100000))
        self._w(ARRAY + g["gptr"], GLOBALS)
        self._w(GLOBALS + g["food"], g["food_ok"] if food is None else food)
        self._w(GLOBALS + g["tech"], 1)
        for slot, v in enumerate(village):
            r = ARRAY + slot * g["stride"]
            mu.mem_write(r + g["alive"], b"\x01" if v.alive else b"\x00")
            self._w(r + g["health"], v.health)
            self._w(r + g["age"], v.age)
            self._w(r + g["sex"], v.sex)
            self._w(r + g["sick"], 1 if v.sick else 0)
            self._w(r + g["preg"], 5 if v.pregnant else 0)
            self._w(r + g["parenting"], 100)
            self._w(r + g["look"], 1000 + slot)
        self._w(ARRAY + g["steptype"], g["step"])

        def rng(bound: int) -> int:
            if bound == 300:
                return 0 if conceive else 299
            if bound == 100:
                return 99 if refuse else 0
            return 0

        self.rng, self.pick, self.picks, self.rolls = rng, pick, [], []
        self.writes, self.unexpected, self.returned = [], [], False
        sp = STACK_TOP - 0x1000
        sp -= 4
        mu.mem_write(sp, struct.pack("<I", 0))          # the initiator's index
        sp -= 4
        mu.mem_write(sp, struct.pack("<I", SENTINEL))
        mu.reg_write(UC_X86_REG_ESP, sp)
        mu.reg_write(UC_X86_REG_ECX, ARRAY)
        mu.emu_start(g["runner"], 0xFFFFFFFF, count=3_000_000)
        assert not self.unexpected, [hex(a) for a in self.unexpected]
        assert self.returned, "the runner did not return"
        assert mu.reg_read(UC_X86_REG_ESP) == STACK_TOP - 0x1000, hex(mu.reg_read(UC_X86_REG_ESP))
        return self

    @property
    def mothers(self) -> list[int]:
        return [mother for mother, _ in self.writes]


def village(initiator: int = MALE) -> list[Villager]:
    """Slot 0 initiates; slots 1-10 are partners of the other sex who can pair; 11-16 are of the other sex but cannot
    (expecting, sick, 15, 50, dead, no health); 17-21 are of the initiator's sex."""
    other = FEMALE if initiator == MALE else MALE
    return ([Villager(initiator)] + [Villager(other) for _ in range(10)] + [
        Villager(other, pregnant=True), Villager(other, sick=True), Villager(other, age=YOUNG),
        Villager(other, age=OLD), Villager(other, alive=False), Villager(other, health=0)]
        + [Villager(initiator) for _ in range(5)])


def _stock_rows(game: str) -> list[dict[str, str]]:
    data = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
    return next(item for item in data["games"] if item["id"] == game)["safety_patches"]


@unittest.skipUnless(STOCK_PRESENT, "the stock executables (research/stock-executables) are gitignored and absent")
class OnePartnerTests(unittest.TestCase):
    def test_stock_one_man_makes_every_woman_who_passes_pregnant(self) -> None:
        # The emulation's reference: the untouched stock runner.  A New Home has no upper age on the scan, so the
        # 50-year-old woman conceives too; The Lost Children refuses a woman of 50 or older.
        expected = {"vv1": list(range(1, 11)) + [14], "vv2": list(range(1, 11))}
        for game in G:
            with self.subTest(game=game):
                run = Runner(game, STOCK[game].read_bytes()).embrace(village())
                self.assertEqual(sorted(run.mothers), expected[game])
                self.assertEqual(run.picks, [])

    def test_the_runner_edits_are_the_safety_rows_and_birth_controls_age_bound_only(self) -> None:
        for game, g in G.items():
            stock = STOCK[game].read_bytes()
            lo, hi = (va - 0x400000 for va in g["runner_span"])
            safety = {o for start, n in g["safety"] for o in range(start, start + n)}
            overlays = {o for start, n in g["overlays"] for o in range(start, start + n)}
            rows = {int(row["offset"], 16) for row in _stock_rows(game)}
            self.assertLessEqual({start for start, _ in g["safety"]}, rows)
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    off = rendered(game, False, mode)
                    on = rendered(game, True, mode)
                    self.assertLessEqual({o for o in range(lo, hi) if off[o] != stock[o]}, safety)
                    self.assertEqual({o for o in range(lo, hi) if on[o] != off[o]} - overlays, set())
                    self.assertTrue({o for o in range(lo, hi) if on[o] != off[o]})

    def test_a_man_picks_one_woman_from_every_woman_who_can_pair(self) -> None:
        # Unticked, the women he can pick from are exactly the women stock would make pregnant; Birth Control bounds
        # the partner under 50 in both games.
        expected = {("vv1", False): list(range(1, 11)) + [14], ("vv2", False): list(range(1, 11)),
                    ("vv1", True): list(range(1, 11)), ("vv2", True): list(range(1, 11))}
        for game, g in G.items():
            for bc in (False, True):
                for mode in MODES:
                    runner = Runner(game, rendered(game, bc, mode))
                    count = len(expected[(game, bc)])
                    for pick in range(count):
                        with self.subTest(game=game, birth_control=bc, mode=mode, pick=pick):
                            run = runner.embrace(village(), pick=pick)
                            self.assertEqual(run.picks, [count])
                            self.assertEqual(run.rolls.count(300), 1)
                            self.assertEqual(run.mothers, [expected[(game, bc)][pick]])
                            # Through the stock call site, so the parentage hooks see the frame they expect.
                            self.assertEqual(run.writes[0][1], g["writer_return"])

    def test_a_woman_picks_one_man_from_every_man_who_can_pair(self) -> None:
        # She is the mother; the pick's count is how many men she picks from.  Unticked: A New Home has no upper
        # age, The Lost Children bounds only the woman, so the 50-year-old man counts in both; Birth Control bounds
        # the partner under 50.
        counts = {("vv1", False): 11, ("vv2", False): 11, ("vv1", True): 10, ("vv2", True): 10}
        for game in G:
            for bc in (False, True):
                for mode in MODES:
                    runner = Runner(game, rendered(game, bc, mode))
                    for pick in (0, 6, counts[(game, bc)] - 1):
                        with self.subTest(game=game, birth_control=bc, mode=mode, pick=pick):
                            run = runner.embrace(village(FEMALE), pick=pick)
                            self.assertEqual(run.picks, [counts[(game, bc)]])
                            self.assertEqual(run.rolls.count(300), 1)
                            self.assertEqual(run.mothers, [0])

    def test_a_woman_who_tries_at_50(self) -> None:
        # Stock The Lost Children refuses a woman of 50 or older who tries; Birth Control, like The Tree of Life,
        # bounds only the partner.  Stock A New Home has no upper age.
        expected = {("vv1", False): [0], ("vv1", True): [0], ("vv2", False): [], ("vv2", True): [0]}
        for game in G:
            for bc in (False, True):
                with self.subTest(game=game, birth_control=bc):
                    folk = village(FEMALE)
                    folk[0].age = OLD
                    run = Runner(game, rendered(game, bc)).embrace(folk)
                    self.assertEqual(run.mothers, expected[(game, bc)])
                    if not expected[(game, bc)]:
                        self.assertEqual((run.picks, run.rolls), ([], []))

    def test_a_failed_roll_is_the_whole_try(self) -> None:
        for game in G:
            for bc in (False, True):
                for mode in MODES:
                    with self.subTest(game=game, birth_control=bc, mode=mode):
                        run = Runner(game, rendered(game, bc, mode)).embrace(village(), pick=3, conceive=False)
                        self.assertEqual(run.mothers, [])
                        self.assertEqual(run.rolls.count(300), 1)
                        self.assertEqual(len(run.picks), 1)

    def test_the_low_food_refusal_ends_the_try(self) -> None:
        for game in G:
            for bc in (False, True):
                with self.subTest(game=game, birth_control=bc):
                    run = Runner(game, rendered(game, bc)).embrace(village(), pick=2, food=0, refuse=True)
                    self.assertEqual(run.mothers, [])
                    self.assertEqual(run.rolls, [100])
                    run = Runner(game, rendered(game, bc)).embrace(village(), pick=2, food=0, refuse=False)
                    self.assertEqual(run.mothers, [3])

    def test_no_one_to_pair_with_ends_the_try_without_a_roll(self) -> None:
        lonely = [Villager(MALE), Villager(FEMALE, pregnant=True), Villager(FEMALE, sick=True), Villager(MALE)]
        for game in G:
            for bc in (False, True):
                for initiator in (Villager(MALE, age=YOUNG), Villager(MALE, sick=True)):
                    with self.subTest(game=game, birth_control=bc, initiator=vars(initiator)):
                        run = Runner(game, rendered(game, bc)).embrace([initiator] + [Villager(FEMALE)] * 3)
                        self.assertEqual((run.mothers, run.picks, run.rolls), ([], [], []))
                with self.subTest(game=game, birth_control=bc, village="no partner"):
                    run = Runner(game, rendered(game, bc)).embrace(lonely)
                    self.assertEqual((run.mothers, run.picks, run.rolls), ([], [], []))

    def test_every_slot_can_be_picked(self) -> None:
        for game in G:
            for bc in (False, True):
                with self.subTest(game=game, birth_control=bc):
                    folk = [Villager(MALE)] + [Villager(MALE)] * 254 + [Villager(FEMALE)]
                    run = Runner(game, rendered(game, bc, "immediate_fixed")).embrace(folk)
                    self.assertEqual((run.picks, run.mothers), ([1], [255]))

    def test_a_new_home_with_origins_keeps_the_one_partner_pick(self) -> None:
        for bc in (False, True):
            with self.subTest(birth_control=bc):
                run = Runner("vv1", rendered("vv1", bc, "collection_progression", origins=True)).embrace(
                    village(), pick=4)
                self.assertEqual((run.picks, run.mothers), ([11 if not bc else 10], [5]))

    def test_the_rows_say_so_in_plain_words(self) -> None:
        catalog = {p.id: p for p in load_fun_patches()}
        for game in G:
            with self.subTest(game=game):
                text = catalog[f"{game}_birth_control"].description
                self.assertIn("one partner", text)
                self.assertIn("whether Birth Control is ticked or not", text)
                self.assertNotIn("Without Birth Control, one try goes through the whole village", text)


if __name__ == "__main__":
    unittest.main()
