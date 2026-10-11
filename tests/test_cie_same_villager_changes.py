"""Custom Island Event: several 'Villager changes' entries for the SAME villager (the owner, 2026-10-10).

The bug (found live in A New Home, v1.35.68): adding 'whale meat' as one entry and
'butterflies' as another for one villager applied only one of them.  The changes dialog
merges every entry for a villager into one (ce_merge), and the merge kept ONE like slot
per entry (like_add / like_remove / dislike_add / dislike_remove), so the later entry
replaced the earlier one.  The Island Events log reads the whole event's before and after
(a snapshot per villager), so it showed only the surviving like.

The fix: a villager's likes and dislikes changes are an ordered list (story_custom.h
ce_change.pref_ops, CE_PREF_OP).  Every entry appends; the same list and preference
changed again replaces the earlier change (the later entry wins); every other field is
replaced field by field (the later entry wins); a villager who dies or disappears gets
nothing else.  Edit keeps the entry's other likes and dislikes changes.

Everything runs the shipped bytes in the emulator, as tests/test_story_custom_island_event.py does,
for each game whose stock executable is present (the tests skip cleanly without them).
"""
from __future__ import annotations

import struct
import unittest

from story_custom_fixtures import KEEP, Change, Event
from test_story_custom_island_event import (
    EVENT_BUF,
    RESULT_BUF,
    ROOT,
    SCRATCH,
    SOURCE,
    TEXT_BUF,
    Story,
    _stories,
    emulated,
    have_stock,
)
from story_custom_fixtures import RESULT_SIZE, unpack_result

FATE_KILL, FATE_VANISH = 1, 2
CHANGES_AT = 4 + 48 + 600 + 4 * 7 + 8 * Event.SPAWN_SIZE   # change_count, then the changes
LIKE, DISLIKE = 0, 1
ADD, REMOVE = 0, 1


def _merge(story, index, *changes, fingerprint=0x77, fresh=True):
    """The dialog's Add for villager `index`, once per change, in order (ce_merge)."""
    p = story.proc
    if fresh:
        p.write(EVENT_BUF, Event(game=story.n).pack())
    results = []
    for change in changes:
        p.write(SCRATCH, change.pack())
        results.append(p.export("VvfpStoryProbeMerge", EVENT_BUF, SCRATCH, index, fingerprint))
    return results


def _live(story, index, *changes, fresh=True):
    """The same Add, for a villager who is in the village (the identity the delivery checks)."""
    return _merge(story, index, *changes, fingerprint=story.village.identity(index), fresh=fresh)


def _count(story):
    return struct.unpack("<i", story.proc.read(EVENT_BUF + CHANGES_AT, 4))[0]


def _entry(story, k=0):
    return story.proc.read(EVENT_BUF + CHANGES_AT + 4 + k * Change.SIZE, Change.SIZE)


def _apply(story):
    """Deliver the event the merges built (not repacked: exactly what the dialog queued)."""
    p = story.proc
    ok = p.export("VvfpStoryProbeApply", story.n, EVENT_BUF, RESULT_BUF, TEXT_BUF, 4096)
    return ok, unpack_result(p.read(RESULT_BUF, RESULT_SIZE)), p.cstring(TEXT_BUF)


def _prepare(story, index=2):
    """A villager with no likes or dislikes; the kill hooks the later games need."""
    v = story.village
    L = v.L
    v.put(index, sex="f", years=30, name="Picky")
    for k in range(L["slots"]):
        story.proc.put32(v.record(index) + L["likes"] + 4 * k, 0xFFFFFFFF)
        story.proc.put32(v.record(index) + L["dislikes"] + 4 * k, 0xFFFFFFFF)
    if story.game == "vv4":
        story.record_call(0x468C60, 0)
    if story.game == "vv5":
        story.record_call(0x473440, 0)
    return v


def _lists(v, index=2):
    return ([x for x in v.prefs(index, "likes") if x >= 0],
            [x for x in v.prefs(index, "dislikes") if x >= 0])


def _same(i, **fields):
    return Change(index=i, fingerprint=0x77, **fields)


@emulated
class SameVillagerLikesTests(unittest.TestCase):
    def test_two_entries_adding_a_like_each_both_apply(self):
        for game, story in _stories():
            v = _prepare(story)
            self.assertEqual(_live(story, 2, _same(2, like_add=7), _same(2, like_add=9)), [1, 1])
            ok, r, _ = _apply(story)
            with self.subTest(game=game):
                self.assertEqual(_count(story), 1, "one entry for the villager")
                self.assertEqual(_lists(v), ([7, 9], []), "both likes, in the order they were added")
                self.assertEqual((r["changed"], r["refused"]), (1, 0))

    def test_likes_and_dislikes_across_four_entries(self):
        for game, story in _stories():
            v = _prepare(story)
            story.proc.put32(v.record(2) + v.L["likes"], 5)
            story.proc.put32(v.record(2) + v.L["dislikes"], 6)
            _live(story, 2, _same(2, like_add=7), _same(2, dislike_add=8), _same(2, like_remove=5),
                   _same(2, dislike_remove=6, like_add=9))
            _apply(story)
            with self.subTest(game=game):
                # (entries apply in order: 7 takes the free slot, then 5 goes, then 9 takes its slot)
                self.assertEqual((sorted(_lists(v)[0]), _lists(v)[1]), ([7, 9], [8]))

    def test_the_same_preference_changed_twice_the_later_entry_wins(self):
        for game, story in _stories():
            v = _prepare(story)
            story.proc.put32(v.record(2) + v.L["likes"], 7)
            # add 9 then remove 9: gone; remove 7 then add 7: kept (its own slot may move)
            _live(story, 2, _same(2, like_add=9), _same(2, like_remove=9),
                   _same(2, like_remove=7), _same(2, like_add=7))
            expect = Change(index=2, fingerprint=v.identity(2), pref_ops=((LIKE, REMOVE, 9), (LIKE, ADD, 7)))
            with self.subTest(game=game, part="merged"):
                self.assertEqual(_entry(story), expect.pack(), "one change per preference, the later one")
            _apply(story)
            with self.subTest(game=game, part="applied"):
                self.assertEqual(_lists(v), ([7], []))

    def test_a_dislike_and_a_like_of_the_same_word_are_separate_changes(self):
        for game, story in _stories():
            v = _prepare(story)
            _live(story, 2, _same(2, like_add=4), _same(2, dislike_add=4))
            _apply(story)
            with self.subTest(game=game):
                self.assertEqual(_lists(v), ([4], [4]))

    def test_a_full_list_refuses_the_extra_like_and_keeps_the_others(self):
        for game, story in _stories():
            v = _prepare(story)
            slots = v.L["slots"]
            if slots >= v.L["prefs"]:
                continue                   # The Lost Children: a list can hold every word, never full
            # two free slots; three entries each add a like
            for k in range(slots - 2):
                story.proc.put32(v.record(2) + v.L["likes"] + 4 * k, 40 + k)
            _live(story, 2, _same(2, like_add=1), _same(2, like_add=2), _same(2, like_add=3))
            ok, r, _ = _apply(story)
            with self.subTest(game=game):
                self.assertEqual(_lists(v)[0], [40 + k for k in range(slots - 2)] + [1, 2],
                                 "the first two entries' likes fit, in order")
                self.assertEqual(r["refused"], 1, "the third has no room: refused, the others kept")

    def test_other_villagers_stay_apart(self):
        for game, story in _stories():
            v = _prepare(story)
            v.put(3, sex="m", years=30, name="Other")
            _live(story, 2, _same(2, like_add=1))
            _live(story, 3, _same(3, like_add=2), fresh=False)
            _live(story, 2, _same(2, like_add=3), fresh=False)
            _apply(story)
            with self.subTest(game=game):
                self.assertEqual(_count(story), 2)
                self.assertEqual(_lists(v, 2), ([1, 3], []))
                self.assertEqual(v.prefs(3, "likes")[0], 2)

    def test_more_than_sixty_four_distinct_changes_are_refused_and_nothing_is_lost(self):
        story = _first_story()
        if story is None:
            self.skipTest("no stock executable")
        for k in range(64):
            change = _same(2, like_add=k) if k < 40 else _same(2, dislike_add=k - 40)
            self.assertEqual(_merge(story, 2, change, fresh=(k == 0)), [1])
        before = _entry(story)
        # 40 likes (0..39) + 24 dislikes (0..23) = 64 distinct; one more is refused ...
        self.assertEqual(_merge(story, 2, _same(2, dislike_add=30), fresh=False), [0])
        self.assertEqual(_entry(story), before, "a refused Add changes nothing")
        # ... but changing a preference that is already there needs no room
        self.assertEqual(_merge(story, 2, _same(2, like_remove=3), fresh=False), [1])
        self.assertEqual(_count(story), 1)


def _first_story():
    for game in ("vv1", "vv2", "vv3", "vv4", "vv5"):
        if have_stock(game):
            return Story(game)
    return None


@emulated
class SameVillagerOtherFieldsTests(unittest.TestCase):
    """Every other field: the later entry replaces the earlier value of that field only."""

    CASES = {
        "head and body": ([dict(head=3), dict(body=4)], dict(head=3, body=4)),
        "head twice": ([dict(head=3), dict(head=5)], dict(head=5)),
        "skills set in two entries": ([dict(skills=(10, KEEP, KEEP, KEEP, KEEP, KEEP)),
                                       dict(skills=(KEEP, 20, KEEP, KEEP, KEEP, KEEP))],
                                      dict(skills=(10, 20, KEEP, KEEP, KEEP, KEEP))),
        "a skill set twice": ([dict(skills=(10, KEEP, KEEP, KEEP, KEEP, KEEP)),
                               dict(skills=(55, KEEP, KEEP, KEEP, KEEP, KEEP))],
                              dict(skills=(55, KEEP, KEEP, KEEP, KEEP, KEEP))),
        "health": ([dict(health=40), dict(health=70)], dict(health=70)),
        "title then clear": ([dict(title_op=1, title="Elder"), dict(title_op=2)], dict(title_op=2)),
        "clear then title": ([dict(title_op=2), dict(title_op=1, title="Elder")],
                             dict(title_op=1, title="Elder")),
        "title then mask": ([dict(title_op=1, title="Elder"), dict(mask=2)],
                            dict(title_op=1, title="Elder", mask=2)),
        "mask twice": ([dict(mask=1), dict(mask=3)], dict(mask=3)),
        "status and behaviour": ([dict(status=1), dict(behaviour=2)], dict(status=1, behaviour=2)),
        "status twice": ([dict(status=1), dict(status=2)], dict(status=2)),
        "faith": ([dict(faith=-50), dict(faith=60)], dict(faith=60)),
        "sick stays": ([dict(sick=1), dict(head=2)], dict(sick=1, head=2)),
        "pregnancy then another": ([dict(litter=1, father=4, father_fingerprint=9), dict(litter=3)],
                                   dict(litter=3, father=-1)),
        "pregnancy kept by a like": ([dict(litter=2, father=4, father_fingerprint=9), dict(like_add=1)],
                                     dict(litter=2, father=4, father_fingerprint=9,
                                          pref_ops=((LIKE, ADD, 1),))),
        "fate then nothing": ([dict(fate=FATE_KILL), dict(head=2)], dict(fate=FATE_KILL, head=2)),
        "dies then disappears": ([dict(fate=FATE_KILL), dict(fate=FATE_VANISH)], dict(fate=FATE_VANISH)),
        "parents then parents": ([dict(parents_set=1, father_name="Kalani", father_head=4, father_body=5),
                                  dict(parents_set=1, mother_name="Moana", mother_head=6, mother_body=7)],
                                 dict(parents_set=1, father_name="Kalani", father_head=4, father_body=5,
                                      mother_name="Moana", mother_head=6, mother_body=7)),
        "unborn father": ([dict(unborn_set=1, unborn_name="Kai", unborn_head=1, unborn_body=2), dict(head=1)],
                          dict(unborn_set=1, unborn_name="Kai", unborn_head=1, unborn_body=2, head=1)),
    }

    def test_each_field_combines_as_the_later_entry_overrides_the_same_field(self):
        story = _first_story()
        if story is None:
            self.skipTest("no stock executable")
        for name, (entries, expected) in self.CASES.items():
            _merge(story, 4, *[_same(4, **e) for e in entries])
            with self.subTest(case=name):
                self.assertEqual(_count(story), 1)
                self.assertEqual(_entry(story), _same(4, **expected).pack())

    def test_appearance_and_skills_of_two_entries_both_apply_in_every_game(self):
        for game, story in _stories():
            v = _prepare(story)
            _live(story, 2, _same(2, head=3), _same(2, body=4),
                   _same(2, skills=(11, KEEP, KEEP, KEEP, KEEP, KEEP)),
                   _same(2, skills=(KEEP, 22, KEEP, KEEP, KEEP, KEEP)))
            _apply(story)
            with self.subTest(game=game):
                self.assertEqual((v.i32(2, v.L["head"]), v.i32(2, v.L["body"])), (3, 4))


@emulated
class SameVillagerFateTests(unittest.TestCase):
    """A villager who dies or disappears gets nothing else, whichever entry said so."""

    def test_dies_in_the_first_entry_ignores_the_later_likes(self):
        for game, story in _stories():
            v = _prepare(story)
            _live(story, 2, _same(2, fate=FATE_KILL), _same(2, like_add=7))
            ok, r, _ = _apply(story)
            with self.subTest(game=game):
                self.assertEqual((r["died"], r["changed"]), (1, 1))
                self.assertEqual(_lists(v), ([], []), "no like for a villager who dies")
                self.assertEqual(v.i32(2, v.L["health"]), 0)

    def test_dies_in_the_second_entry_ignores_the_earlier_likes(self):
        for game, story in _stories():
            v = _prepare(story)
            _live(story, 2, _same(2, like_add=7), _same(2, fate=FATE_KILL))
            ok, r, _ = _apply(story)
            with self.subTest(game=game):
                self.assertEqual(r["died"], 1)
                self.assertEqual(_lists(v), ([], []))

    def test_health_zero_in_one_entry_kills_like_dies(self):
        for game, story in _stories():
            v = _prepare(story)
            _live(story, 2, _same(2, health=0), _same(2, like_add=7))
            ok, r, _ = _apply(story)
            with self.subTest(game=game):
                self.assertEqual(r["died"], 1)
                self.assertEqual(_lists(v), ([], []))


@emulated
class SameVillagerEditTests(unittest.TestCase):
    """Edit shows the last like / remove-a-like / dislike / remove-a-dislike change of a
    combined entry; OK replaces those, and the entry's other like and dislike changes stay."""

    def replace(self, story, change, position=0, fingerprint=0x88):
        story.proc.write(SCRATCH, change.pack())
        return story.proc.export("VvfpStoryProbeReplace", EVENT_BUF, position, SCRATCH, fingerprint)

    def test_edit_keeps_the_entrys_other_likes(self):
        story = _first_story()
        if story is None:
            self.skipTest("no stock executable")
        _merge(story, 2, _same(2, like_add=7), _same(2, like_add=9), _same(2, dislike_add=3), _same(2, head=5))
        # the dialog opens with the last like (9) and the dislike (3); the player changes the like to 11
        self.assertEqual(self.replace(story, _same(2, like_add=11, dislike_add=3)), 1)
        expect = Change(index=2, fingerprint=0x88, pref_ops=((LIKE, ADD, 7), (LIKE, ADD, 11), (DISLIKE, ADD, 3)))
        self.assertEqual(_entry(story), expect.pack(), "the 7 stays, the 9 becomes 11 in its place, head gone")

    def test_edit_clearing_a_choice_drops_only_that_change(self):
        story = _first_story()
        if story is None:
            self.skipTest("no stock executable")
        _merge(story, 2, _same(2, like_add=7), _same(2, like_add=9), _same(2, dislike_add=3))
        self.assertEqual(self.replace(story, _same(2, dislike_add=-1, like_add=9)), 1)
        expect = Change(index=2, fingerprint=0x88, pref_ops=((LIKE, ADD, 7), (LIKE, ADD, 9)))
        self.assertEqual(_entry(story), expect.pack())

    def test_edit_to_a_preference_the_entry_already_changes_leaves_one_change(self):
        story = _first_story()
        if story is None:
            self.skipTest("no stock executable")
        _merge(story, 2, _same(2, like_add=7), _same(2, like_add=9))
        self.assertEqual(self.replace(story, _same(2, like_add=7)), 1)
        expect = Change(index=2, fingerprint=0x88, pref_ops=((LIKE, ADD, 7),))
        self.assertEqual(_entry(story), expect.pack())

    def test_edit_adding_a_like_to_an_entry_without_one(self):
        story = _first_story()
        if story is None:
            self.skipTest("no stock executable")
        _merge(story, 2, _same(2, head=1))
        self.assertEqual(self.replace(story, _same(2, like_add=2)), 1)
        self.assertEqual(_entry(story), Change(index=2, fingerprint=0x88, pref_ops=((LIKE, ADD, 2),)).pack())


@emulated
class EditIsTransactionalAndOrderFree(unittest.TestCase):
    """Codex review of #583: Edit worked out its four replacements category by category."""

    def replace(self, story, change, fingerprint=0x88):
        story.proc.write(SCRATCH, change.pack())
        return story.proc.export("VvfpStoryProbeReplace", EVENT_BUF, 0, SCRATCH, fingerprint)

    def test_swapping_two_preferences_between_categories_loses_nothing(self):
        # add A (3), remove B (5); Edit to: add B (5), remove A (3)
        story = _first_story()
        if story is None:
            self.skipTest("no stock executable")
        _merge(story, 2, _same(2, like_add=3), _same(2, like_remove=5))
        self.assertEqual(self.replace(story, _same(2, like_add=5, like_remove=3)), 1)
        expect = Change(index=2, fingerprint=0x88, pref_ops=((LIKE, ADD, 5), (LIKE, REMOVE, 3)))
        self.assertEqual(_entry(story), expect.pack(), "both changes survive, the dialog's two")

    def test_a_full_entry_refuses_a_new_category_and_is_left_untouched(self):
        story = _first_story()
        if story is None:
            self.skipTest("no stock executable")
        for k in range(40):
            _merge(story, 2, _same(2, like_add=k), fresh=(k == 0))
        for k in range(24):
            _merge(story, 2, _same(2, dislike_add=k), fresh=False)      # 64 changes, no remove-a-like yet
        before = _entry(story)
        self.assertEqual(self.replace(story, _same(2, like_add=39, dislike_add=23, like_remove=41)), 0)
        self.assertEqual(_entry(story), before, "refused: nothing changed")
        # a change that needs no extra room still works
        self.assertEqual(self.replace(story, _same(2, like_add=45, dislike_add=23)), 1)


class EditRefusalIsShown(unittest.TestCase):
    def test_the_dialog_stays_open_with_a_message_when_edit_has_no_room(self):
        ui = (SOURCE / "story_custom_ui.inc").read_text(encoding="utf-8")
        self.assertIn("if (!ce_replace(&ui.draft", ui)
        self.assertIn("already holds 64 likes and dislikes changes", ui)

class DialogSourceTests(unittest.TestCase):
    """The warning the player sees at Add time (static: the shipped source and resource)."""

    def setUp(self):
        self.ui = (SOURCE / "story_custom_ui.inc").read_text(encoding="utf-8")
        self.rc = (SOURCE / "vvfp_story_upgrades.rc").read_text(encoding="utf-8")

    def test_the_count_line_warns_that_entries_are_combined(self):
        self.assertIn("already has changes in this event: they are combined", self.ui)
        self.assertIn("a later entry overrides the same field", self.ui)
        self.assertIn("other changes to them are ignored", self.ui)

    def test_the_count_label_has_room_for_the_warning(self):
        line = next(l for l in self.rc.splitlines() if l.strip().startswith('LTEXT       "", 2007,'))
        height = int(line.rstrip().split(",")[-1])
        self.assertGreaterEqual(height, 40)

    def test_there_is_no_single_like_slot_left(self):
        header = (SOURCE / "story_custom.h").read_text(encoding="utf-8")
        for stale in ("int like_add;", "int like_remove;", "int dislike_add;", "int dislike_remove;"):
            self.assertNotIn(stale, header)
        self.assertIn("pref_ops[CE_MAX_PREF_OPS]", header)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
