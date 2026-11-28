"""New Believers: Heathen Tribe Expansion and Evolution's nursing, Rascals, mask caps and purple masters ("VVFP Heathen
Aging.dll", native/vvfp_heathen_aging/heathen_tribe.inc; the owner, 2026-11-27/28).

EMULATED on the stock New Believers executable, as tests/test_vv5_heathen_evolution.py (whose Evo village this uses):

* NURSING -- the Heathen AI's carrier test 0x46EAB8 run as the game reaches it (esi the AI object, the AI's own frame
  on the stack): a carrier of a baby this companion conceived gets the believers' mothers' routine 0x46A1D0 (stood
  in for) and the AI returns; a puzzle Heathen carrier, or a mother the routine passes over, the stock carry 0x46EAC6;
  nobody carrying 0x46EACD.
* RASCALS -- the Details panel's child title test 0x4430C6 run as the game reaches it: an orange or red Heathen child
  is titled "Rascal" (0x4430CE), any other "Child" (0x4430E3).
* MASK CAPS -- at most 10 orange / 10 red Heathens, and the village's 1 or 2 Rascals of each colour among the
  children, kept in the tribe file; an existing mask is never changed.
* PURPLE MASTERS -- the first camp Heathen to master each skill wears the purple mask through the Origins mask store,
  one a skill, the next one after a death."""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from story_emulator import RETURN, STACK_TOP  # noqa: E402
from test_vv5_heathen_aging import AGE, ORANGE, PRESENT, RED, ROLE, SKILLS, _skip  # noqa: E402
from test_vv5_heathen_evolution import Evo, _couple, first_output  # noqa: E402

NURSE_SITE, NURSE_CARRY, NURSE_ROLE = 0x46EAB8, 0x46EAC6, 0x46EACD
MOTHERS = 0x46A1D0
RASCAL_SITE, RASCAL_TITLE, CHILD_TITLE = 0x4430C6, 0x4430CE, 0x4430E3
STORE = 0x0B600000
TRIBE_FILE = "Heathen Tribe - Save 1.dat"


class Looks(Evo):
    """An Evo with the mothers' routine, the carry and the Origins mask store stood in for."""

    def before_start(self) -> None:
        super().before_start()
        self.mothers: list[int] = []
        self.mothers_answer = 1
        self.carried: list[tuple[int, int]] = []
        self.kept: list[tuple[int, int]] = []
        self.store_on = False
        self.stub(MOTHERS, lambda p: (self.mothers.append(p.reg("ecx")), (self.mothers_answer, 0))[1])
        self.stub(0x466420, lambda p: (self.carried.append((p.reg("ecx"), p.arg(0) & 0xFFFFFFFF)), (0, 4))[1])
        keep = self.alloc(0x10)
        self.stub(keep, lambda p: (self.kept.append((p.arg(0), p.arg(1))), (1, 8))[1])
        self.keep_export = keep

    def _module(self, p):
        name = p.cstring(p.arg(0)) if p.arg(0) else ""
        if self.store_on and name in ("VVFP Origins Icons.dll", "VVFP Heathens Keep Masks.dll"):
            return STORE, 4
        return super()._module(p)

    def _proc(self, p):
        if p.arg(0) == STORE:
            return (self.keep_export if p.cstring(p.arg(1)) == "VvfpMaskKeep" else 0), 8
        return super()._proc(p)

    def heathen_ai_carrier_test(self, record: int, until: int) -> None:
        """0x46EAB8 as the Heathen AI reaches it: esi the AI object (its +0x1B88 the record), ebx 0, the frame
        `sub esp, 0x20; push ebx; push esi` above the return address."""
        ai = self.alloc(0x1C00)
        self.put32(ai + 0x1B88, record)
        esp = STACK_TOP - 0x2000
        self.write(esp, bytes(0x28))
        self.put32(esp + 0x28, RETURN)
        self.set_reg("esp", esp)
        self.set_reg("esi", ai)
        self.set_reg("ebx", 0)
        self.run(NURSE_SITE, until)
        self.last_ai = ai

    def child_title(self, record: int, until: int) -> None:
        self.set_reg("esp", STACK_TOP - 0x2000)
        self.set_reg("eax", record)
        self.set_reg("ebx", 0)
        self.run(RASCAL_SITE, until)


def _mother(v: Looks) -> tuple[int, int]:
    """A Heathen couple's woman, expecting a baby this companion conceived (an embrace that met)."""
    man, woman = _couple(v)
    v.seed(first_output((4800, lambda r: True), (600, 0), (2, 1)))
    v.credit(man, 1)
    v.spots[man] = v.spots[woman] = (1, 1)
    v.look(1)
    assert v.conceived, "the embrace conceived"
    return man, woman


@unittest.skipIf(_skip(), _skip() or "")
class Nursing(unittest.TestCase):
    def test_a_heathen_mother_nurses_with_the_believers_mothers_routine(self):
        v = Looks()
        _man, woman = _mother(v)
        v.heathen_ai_carrier_test(woman, RETURN)
        self.assertEqual(v.mothers, [v.last_ai], "0x46A1D0 on the AI object")
        self.assertEqual(v.carried, [(woman, 3)], "she holds the baby (carry 3), as the stock Heathen carry")

    def test_a_mother_the_routine_passes_over_gets_the_stock_carry(self):
        v = Looks()
        _man, woman = _mother(v)
        v.mothers_answer = 0                          # the routine's 20% "nothing": the stock Heathen AI goes on
        v.heathen_ai_carrier_test(woman, NURSE_CARRY)

    def test_a_puzzle_heathen_and_another_pregnancy_keep_the_stock_carry(self):
        v = Looks()
        mommy = v.villager(5, heathen=True, sex=1, role=17, name="Mommy")
        v.put32(mommy + 0x1C4C, 400)
        v.heathen_ai_carrier_test(mommy, NURSE_CARRY)
        stranger = v.villager(6, heathen=True, sex=1, name="Turned")
        v.put32(stranger + 0x1C4C, 400)              # a pregnancy from before she turned Heathen
        v.heathen_ai_carrier_test(stranger, NURSE_CARRY)
        self.assertEqual(v.mothers, [])

    def test_nobody_carrying_goes_to_the_camp_role(self):
        v = Looks()
        h = v.villager(5, heathen=True, sex=1, name="Lani")
        v.heathen_ai_carrier_test(h, NURSE_ROLE)
        self.assertEqual((v.mothers, v.carried), ([], []))

    def test_the_baby_is_born_forty_units_after_the_conception(self):
        v = Looks()
        _man, woman = _mother(v)
        at = v.i32(woman, 0x1C4C)
        v.put32(woman + AGE, at + 41)
        v.rand_answers.extend([0, 0, 1])
        v.life_tick()
        self.assertEqual(len(v.created), 0, "still nursing at 40 units")
        v.put32(woman + AGE, at + 42)
        v.rand_answers.extend([0, 0, 1])
        v.life_tick()
        self.assertEqual(len(v.created), 1, "born a two-year-old child, as believers' babies")
        self.assertEqual(v.created[0][1][4], 40)


@unittest.skipIf(_skip(), _skip() or "")
class Rascals(unittest.TestCase):
    def test_orange_or_red_heathen_children_are_rascals(self):
        v = Looks()
        for i, (orange, red, until) in enumerate(((1, 0, RASCAL_TITLE), (0, 1, RASCAL_TITLE), (0, 0, CHILD_TITLE))):
            with self.subTest(orange=orange, red=red):
                kid = v.villager(10 + i, heathen=True, age=100, orange=orange, red=red, name=f"Kid{i}")
                v.child_title(kid, until)


def _tribe_words(v: Looks) -> list[int]:
    path = next(k for k in v.files if k.endswith(TRIBE_FILE))
    data = v.files[path]
    assert struct.unpack_from("<5I", data, 0)[:4] == (0x31544856, 1, 5, 8)
    return list(struct.unpack_from("<8I", data, 20))


@unittest.skipIf(_skip(), _skip() or "")
class MaskCaps(unittest.TestCase):
    def test_the_rascal_caps_are_drawn_once_and_kept_in_the_tribe_file(self):
        v = Looks()
        v.villager(0, heathen=True)
        for _ in range(3):
            v.look(0)
        words = _tribe_words(v)
        self.assertIn(words[0], (1, 2))
        self.assertIn(words[1], (1, 2))
        self.assertEqual(words[2:], [0] * 6)

    def test_a_newborn_is_blue_once_the_rascals_are_at_the_cap(self):
        v = Looks()
        _man, woman = _mother(v)
        for i in range(2):                            # two orange children already: at any cap (1 or 2)
            v.villager(20 + i, heathen=True, age=100, orange=1, name=f"Rascal{i}")
        at = v.i32(woman, 0x1C4C)
        v.put32(woman + AGE, at + 42)
        v.seed(first_output((100, 0)))                # the roll asks for orange
        v.rand_answers.extend([0, 0, 1])
        v.life_tick()
        self.assertEqual(tuple(v.created[0][1][5:7]), (0, 0), "blue: the orange Rascals are at the cap")
        self.assertEqual([v.read(v.record(20 + i) + ORANGE, 1) for i in range(2)], [b"\x01"] * 2,
                         "an existing child's mask is never changed")

    def test_never_more_than_ten_orange_heathens(self):
        v = Looks(arrivals="10")
        for i in range(10):
            v.villager(i, heathen=True, orange=1, age=100, name=f"O{i}")   # children: no pairing roll
        v.look(0)
        v.seed(first_output((4800, 0), (100, lambda r: r < 40), (2, lambda r: True), (6, lambda r: r != 0),
                            (100, 0)))
        v.credit(v.record(0), 1)
        self.assertEqual(tuple(v.created[0][1][5:7]), (0, 0), "an orange roll, but ten orange already: blue")


@unittest.skipIf(_skip(), _skip() or "")
class PurpleMasters(unittest.TestCase):
    def _master(self, v: Looks, index: int, skill: int, *, role: int = 0, name: str = "") -> int:
        r = v.villager(index, heathen=True, role=role, name=name or f"M{index}")
        v.write(r + SKILLS + 4 * skill, struct.pack("<f", 100.0))
        return r

    def test_the_first_master_of_each_skill_wears_the_purple_mask(self):
        v = Looks()
        v.store_on = True
        farmer = self._master(v, 1, 0)
        v.write(farmer + ORANGE, b"\x01")
        second = self._master(v, 2, 0)
        builder = self._master(v, 3, 4)
        v.look(1)
        self.assertEqual(sorted(v.kept), sorted([(farmer, 4), (builder, 4)]), "one a skill: Farming and Building")
        self.assertEqual(v.read(farmer + ORANGE, 1), b"\x00")
        self.assertNotIn((second, 4), v.kept)
        v.look(1)                                     # (the file written at most once a second)
        words = _tribe_words(v)
        self.assertNotEqual(words[2], 0, "Farming's master kept in the tribe file")
        self.assertNotEqual(words[6], 0, "Building's")

    def test_the_next_master_takes_it_after_a_death(self):
        v = Looks()
        v.store_on = True
        first = self._master(v, 1, 2)
        second = self._master(v, 2, 2)
        v.look(1)
        self.assertEqual(v.kept, [(first, 4)])
        self.assertEqual(v.export("VvfpHeathenAgingEventGone", 5, 1, 0, 5), 2, "an island event's death")
        self.assertIn((first, 1), v.kept, "the dead master's stored mask back to blue")
        v.look(2)
        self.assertIn((second, 4), v.kept)

    def test_never_a_puzzle_heathen_and_nothing_without_the_mask_store(self):
        v = Looks()
        v.store_on = True
        self._master(v, 1, 3, role=14)                # the Heathen Scientist keeps his own mask
        v.look(1)
        self.assertEqual(v.kept, [])
        v = Looks()
        self._master(v, 1, 3)
        v.look(1)
        self.assertEqual(v.kept, [], "without Origins Icons and Heathens Keep Masks: no purple")
        v.look(1)
        self.assertEqual(_tribe_words(v)[5], 0, "and nobody written down")


def _clock_index(v: Looks) -> int:
    """The village's clock: the first living record (its age credit moves the clock)."""
    return next(i for i in range(v.slots) if v.read(v.record(i) + PRESENT, 1) != b"\0")


@unittest.skipIf(_skip(), _skip() or "")
class Generations(unittest.TestCase):
    def test_a_heathen_born_in_the_camp_grows_up_and_pairs_but_never_with_a_parent_or_sibling(self):
        v = Looks()
        man, woman = _mother(v)
        at = v.i32(woman, 0x1C4C)
        v.put32(woman + AGE, at + 42)
        v.rand_answers.extend([0, 0, 1])
        v.life_tick()
        (child_index, _args), = v.created
        child = v.record(child_index)
        self.assertEqual(v.read(child + PRESENT, 1), b"\x01")
        v.put32(child + AGE, 600)                     # grown up
        v.put32(child + 0x1C3C, 600)
        v.put32(child + 0x1B90, 1)                    # a daughter
        for _ in range(6):
            v.credit(v.record(_clock_index(v)), 1)
        self.assertEqual(v.couple_of(child_index), -1, "never paired with her father (her parents are a couple)")
        stranger = v.villager(30, heathen=True, sex=0, name="Rua")
        for _ in range(6):
            v.credit(v.record(_clock_index(v)), 1)
            if v.couple_of(child_index) >= 0:
                break
        self.assertEqual(v.couple_of(child_index), 30, "she pairs with someone who is not kin: a new generation")
        self.assertEqual(stranger, v.record(30))


if __name__ == "__main__":
    unittest.main()
