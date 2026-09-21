"""VV2 names its skills in the order the RECORD stores them, not the order the
Details screen lists them.

The Lost Children displays Farming, Building, Research, Healing, Parenting and
stores Parenting, Building, Farming, Healing, Research. Labelling the array in
screen order named the wrong skill in three slots out of five.

Every slot is measured against the owner's running village -- none is inferred
by elimination:

  Jade  [61, 0, 0, 100, 0]   two bars: Healing full, Parenting ~60%
                             -> index 0 = Parenting, index 3 = Healing
  Buru  [0, 91, 0, 0, 0]     one bar: Building      -> index 1 = Building
  Dodo  [0, 0, 93, 0, 100]   two bars: Farming and Research, Research at 100
                             -> index 2 = Farming, index 4 = Research
  Tatau [0, 0, 0, 46, 0]     one bar: Healing       -> index 3 = Healing

Building and Healing sit at the symmetric middle positions and so happened to
be correct in the old order too, which is why the bug was not obvious.

VV2 calls this first skill Parenting where VV1 calls it Breeding. They are the
same skill; each game is labelled with the word its own screen uses.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POP_C = ROOT / "native" / "population_export" / "population_export.c"

VV2_STORAGE_ORDER = ("Parenting", "Building", "Farming", "Healing", "Research")
VV2_DISPLAY_ORDER = ("Farming", "Building", "Research", "Healing", "Parenting")

# name -> (values by storage index, the skill the game's own screen shows as
# that villager's highest). Read live from the running game.
LIVE_VILLAGERS = {
    "Jade": ([61, 0, 0, 100, 0], "Healing"),
    "Buru": ([0, 91, 0, 0, 0], "Building"),
    "Dodo": ([0, 0, 93, 0, 100], "Research"),
    "Tatau": ([0, 0, 0, 46, 0], "Healing"),
    "Tapu": ([0, 0, 0, 14, 100], "Research"),
    "Hokou": ([0, 0, 96, 0, 0], "Farming"),
    "Ongo": ([0, 98, 0, 0, 0], "Building"),
}

# Each slot and the villager whose screen named it, so a regression says which
# observation it contradicts.
SLOT_EVIDENCE = {
    0: ("Parenting", "Jade", 61),
    1: ("Building", "Buru", 91),
    2: ("Farming", "Dodo", 93),
    3: ("Healing", "Tatau", 46),
    4: ("Research", "Dodo", 100),
}


def c_string_list(source: str, symbol: str) -> list[str]:
    match = re.search(
        r"static const char \*const " + re.escape(symbol) + r"\[[^\]]*\]\s*=\s*\{(.*?)\};",
        source,
        re.S,
    )
    assert match, "%s not found" % symbol
    return re.findall(r'"([^"]*)"', match.group(1))


class Vv2SkillNameOrderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pop = POP_C.read_text(encoding="utf-8")
        self.names = c_string_list(self.pop, "SKILL_NAMES_VV2")

    def test_the_storage_and_display_orders_really_do_differ(self):
        self.assertNotEqual(VV2_STORAGE_ORDER, VV2_DISPLAY_ORDER)

    def test_vv2_table_is_in_storage_order(self):
        self.assertEqual(tuple(self.names[:5]), VV2_STORAGE_ORDER)

    def test_vv2_table_is_not_the_display_order(self):
        self.assertNotEqual(
            tuple(self.names[:5]),
            VV2_DISPLAY_ORDER,
            "VV2 is labelled in Details-screen order again",
        )

    def test_every_slot_matches_the_villager_that_named_it(self):
        for slot, (skill, who, value) in SLOT_EVIDENCE.items():
            with self.subTest(slot=slot, villager=who):
                self.assertEqual(
                    self.names[slot],
                    skill,
                    "slot %d was named %s by %s (bar read %d)"
                    % (slot, skill, who, value),
                )

    def test_every_live_villager_is_labelled_as_the_game_labels_them(self):
        for who, (values, expected) in LIVE_VILLAGERS.items():
            with self.subTest(villager=who):
                best = max(range(len(values)), key=lambda i: values[i])
                self.assertEqual(self.names[best], expected)

    def test_the_display_order_would_fail_that_check(self):
        """Proves the test detects the bug it exists for."""
        wrong = 0
        for values, expected in LIVE_VILLAGERS.values():
            best = max(range(len(values)), key=lambda i: values[i])
            if VV2_DISPLAY_ORDER[best] != expected:
                wrong += 1
        self.assertGreater(wrong, 0)

    def test_vv2_uses_its_own_table(self):
        self.assertIn("if (game_id == GAME_VV2) { return SKILL_NAMES_VV2; }", self.pop)

    def test_the_log_prints_the_per_game_table(self):
        self.assertIn("skill_names_for(game_id)[skill]", self.pop)
        self.assertNotIn("SKILL_NAMES[skill]", self.pop)

    def test_unverified_games_are_left_alone(self):
        """Every other game keeps the names it has always had.

        This is the shared table as it shipped -- six entries, because VV5 has
        a sixth slot -- and it must not be reordered on VV2's evidence. Each
        remaining game is corrected only after being checked against its own
        screen.
        """
        other = c_string_list(self.pop, "SKILL_NAMES_UNVERIFIED")
        self.assertEqual(
            tuple(other[:6]),
            ("Farming", "Building", "Research", "Healing", "Breeding", "Parenting"),
        )


if __name__ == "__main__":
    unittest.main()


VISIBLE_AT = 5  # a bar below this does not render


class Vv2DisassemblyLabelsAreNotEvidenceTests(unittest.TestCase):
    """The stock dispatch's OFFSETS are real; its NAMES are an assumption.

    Codex raised a P1 on #412: the five-job dispatch at 0x449DE9..0x449E09,
    pinned in tests/test_vv2_birth_control.py, is annotated

        0x449DE9  mov esi, [edi+0x7EC]   Research
        0x449DF1  mov esi, [edi+0x7E4]   Farming
        0x449DF9  mov esi, [edi+0x7F0]   Healing
        0x449E01  mov esi, [edi+0x7E8]   Building
        0x449E09  mov esi, [edi+0x7F4]   Parenting

    which would make the storage order Farming, Building, Research, Healing,
    Parenting -- the Details-screen order, contradicting this table.

    The offsets are the executable's own and are not in question. The NAMES
    beside them are a human annotation written from the screen order, which is
    the very assumption this bug is about, and the owner's running game
    settles it against them:

        Dodo [0, 0, 93, 0, 100] shows exactly two filled bars, Farming and
        Research, with RESEARCH at 100. Under the annotation the lit bars
        would be Research (93) and Parenting (100) -- Parenting would show a
        full bar. It is empty on screen.

    Runtime behaviour outranks a comment. This test records the contradiction
    so the annotation cannot be cited again without this evidence.
    """

    DISPATCH_ANNOTATION = ("Farming", "Building", "Research", "Healing", "Parenting")
    DODO = [0, 0, 93, 0, 100]
    DODO_LIT = {"Farming", "Research"}
    DODO_AT_100 = "Research"

    def test_the_annotation_contradicts_the_running_game(self):
        lit = {
            self.DISPATCH_ANNOTATION[i]
            for i, v in enumerate(self.DODO)
            if v >= VISIBLE_AT
        }
        self.assertNotEqual(
            lit,
            self.DODO_LIT,
            "if the dispatch annotation matched the game, this PR would be wrong",
        )

    def test_the_measured_order_reproduces_the_running_game(self):
        names = c_string_list(POP_C.read_text(encoding="utf-8"), "SKILL_NAMES_VV2")
        lit = {names[i] for i, v in enumerate(self.DODO) if v >= VISIBLE_AT}
        self.assertEqual(lit, self.DODO_LIT)

    def test_the_skill_at_one_hundred_is_the_one_the_owner_named(self):
        names = c_string_list(POP_C.read_text(encoding="utf-8"), "SKILL_NAMES_VV2")
        hundred = [names[i] for i, v in enumerate(self.DODO) if v == 100]
        self.assertEqual(hundred, [self.DODO_AT_100])
