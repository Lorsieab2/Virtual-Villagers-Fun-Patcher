"""A carrier whose sex is changed to male mid-pregnancy: each game's own delivery, run in an emulator (all five).

The owner (2026-11-15): the sex change is offered for carrying and nursing villagers too, KEEPING the pregnancy --
the villager carries as male, and stays the carrying parent (the mother slot at conception) whatever their sex.
In every game "nursing" is the same state as carrying: the pregnancy field holds the age at conception, the
villager holds the baby in their arms until the delivery 40 age units later (native/population_export's
"Nursing: yes" is that field), and the delivery turns the babies into villagers of their own -- no game keeps a
nursing state after it.

What runs is each stock executable's own delivery block (tests/sex_carrier_harness.py), from its "carrying?"
test to its join, with every routine it calls run for real: the creators, the twin / triplet copies, the
births' clocks, rand, the messages.  A memory-read hook on the carrier's sex field records every read of it,
whoever makes it.  Proved here, for a male carrier against the same run with a female carrier:

  * the delivery comes at the same age (not before conception + 40 is passed, and then at once), also when the
    sex is changed part-way through the pregnancy;
  * the same babies (one, twins, triplets) are made, into the same records;
  * the babies' parents are filled from the carrier: the father's name in the father slot, the carrier's in
    the mother slot (VV2-VV5; A New Home keeps no parents on the record);
  * the carrier's pregnancy and litter fields are cleared and their hands emptied, as for a female carrier;
  * every byte of the village's records is the same apart from the carrier's sex field;
  * no crash, no unexpected Windows call;
  * the delivery never reads the carrier's sex -- except, in a village of six or fewer, each game's
    small-village sex balance (called at VV1 0x42EFAB, VV2 0x43BE39, VV3 0x460376, VV4 0x468810,
    VV5 0x4730DF), which counts the living by their sex now to pick the new baby's sex.  That read is
    harmless: a male carrier is counted as the man he now is, and nothing else depends on it.
"""
from __future__ import annotations

import unittest

import sex_carrier_harness as h

GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")
DUE = h.CONCEIVED + 41            # the first age the block delivers at (conception + 0x28 < age)
# The litter field per game for one baby, twins and triplets (VV1 / VV2 leave 0 for one; VV3-VV5 write 1).
LITTERS = {g: ((0, 1), (2, 2), (3, 3)) if g in ("vv1", "vv2") else ((1, 1), (2, 2), (3, 3)) for g in GAMES}
# Where each game's small-village sex balance reads a villager's sex (the only read on the path).
BALANCE_READS = {"vv1": 0x42E6D0, "vv2": 0x43B410, "vv3": 0x45EB04, "vv4": 0x4676D3, "vv5": 0x471523}


def village(game: str, male: bool, litter: int, crowd: bool = True) -> h.Village:
    v = h.Village(game)
    if crowd:
        v.crowd(8)
    v.carrier(sex_male=male, litter=litter)
    return v


class TheDeliveryWithAMaleCarrier(unittest.TestCase):
    def each_game(self, check):
        ran = 0
        for game in GAMES:
            if not h.available(game):
                continue
            ran += 1
            with self.subTest(game=game):
                check(game)
        if not ran:
            self.skipTest("unicorn or the inputs/vvN-stock-copy executables are missing")

    # ---- the same babies, records and parents --------------------------------------------------------------
    def test_same_babies_same_records_same_parents_as_a_female_carrier(self):
        self.each_game(self.same_as_female)

    def same_as_female(self, game):
        for litter, babies in LITTERS[game]:
            runs = {}
            for male in (False, True):
                v = village(game, male, litter)
                result = v.deliver(DUE)
                runs[male] = (v, result, v.snapshot())
                g = v.g
                self.assertEqual(len(result["babies"]), babies, (game, male, litter))
                self.assertEqual(result["pregnant"], 0, "the pregnancy field cleared")
                self.assertEqual(result["litter"], 0, "the litter field cleared")
                self.assertEqual(result["sex_reads"], [], "a village of more than six: the sex is never read")
                self.assertEqual(v.get(v.rec(h.CARRIER) + g["sex"]), g["male"] if male else g["female"],
                                 "the delivery leaves the carrier's sex as it is")
                for baby in result["babies"]:
                    rec = v.rec(baby)
                    if "child_father" in g:
                        self.assertEqual(v.text(rec + g["child_father"]), b"Father", "the father slot")
                        self.assertEqual(v.text(rec + g["child_mother"]), b"Carrier", "the carrier: mother slot")
                if "hands" in g:
                    self.assertEqual(v.get(v.rec(h.CARRIER) + g["hands"]), g["empty_hands"], "hands emptied")
            (vf, rf, sf), (vm, rm, sm) = runs[False], runs[True]
            self.assertEqual(rf["babies"], rm["babies"], "the same records")
            self.assertEqual(rf["calls"], rm["calls"], "the same Windows calls")
            sex_at = h.CARRIER * vf.g["stride"] + vf.g["sex"]
            differ = [i for i in range(len(sf)) if sf[i] != sm[i]]
            self.assertTrue(all(sex_at <= i < sex_at + 4 for i in differ),
                            f"{game}: only the carrier's sex differs, not {[hex(i) for i in differ[:8]]}")

    # ---- on time, with the sex changed part-way --------------------------------------------------------------
    def test_the_delivery_is_on_time_with_the_sex_changed_part_way(self):
        self.each_game(self.on_time)

    def on_time(self, game):
        # Conceived female; carried (nursing) 20 age units; changed to male; carried on: delivered at the same age
        # as a female carrier, not a tick before, with the twins she conceived.
        litter = LITTERS[game][1][0]
        ages = {}
        for change in (False, True):
            v = village(game, False, litter)
            delivered = None
            for age in range(h.CONCEIVED + 1, DUE + 1):
                if change and age == h.CONCEIVED + 20:
                    v.set_sex(True)
                result = v.deliver(age)
                if result["babies"]:
                    delivered = age
                    self.assertEqual(len(result["babies"]), 2)
                    self.assertEqual(result["pregnant"], 0)
                    break
                self.assertEqual(result["pregnant"], h.CONCEIVED, "still carrying before the delivery")
                self.assertEqual(result["litter"], litter, "the litter kept before the delivery")
            ages[change] = delivered
        self.assertEqual(ages[False], DUE)
        self.assertEqual(ages[True], DUE, "a sex change mid-pregnancy keeps the delivery on time")

    # ---- the one read: a small village's sex balance -----------------------------------------------------
    def test_a_small_village_reads_the_sex_only_in_its_sex_balance(self):
        self.each_game(self.small_village)

    def small_village(self, game):
        # Six or fewer villagers: each game picks the baby's sex to balance the village, counting the living by
        # their sex now -- the one read, and a male carrier is counted as male.  The delivery still happens.
        for male in (False, True):
            v = village(game, male, LITTERS[game][0][0], crowd=False)
            result = v.deliver(DUE)
            self.assertEqual(len(result["babies"]), 1)
            self.assertEqual(result["pregnant"], 0)
            want = v.g["male"] if male else v.g["female"]
            self.assertEqual(result["sex_reads"], [(BALANCE_READS[game], want)], (game, male))


if __name__ == "__main__":
    unittest.main()
