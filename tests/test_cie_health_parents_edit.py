"""Custom Island Event: Health, the new villagers' parents, and Edit (the owner, 2026-10-10).

1. Villager changes: a Health box (0-100, blank = no change) with a warning that 0 kills the
   villager.  The simplest method: health above 0 is written as each game's revive writes it
   (A New Home +0x344, The Lost Children +0x52C, The Secret City / The Tree of Life / New
   Believers through the game's own health setter, cause -1); 0 is the game's own death, as
   "Dies".
2. New villagers: the same Health, and Parents -- each parent a villager of the village,
   Unknown, Joey (The Tree of Life and New Believers' default father: "Joey", head 2, body 2)
   or Custom.  They are written where each game keeps a born villager's parents (The Lost
   Children on: the record's own parent fields; A New Home: the Show Parents sidecar through
   Vv1ParentageSetParents), and told to the Births log's Arrived record as its "Parents:"
   block.  The Villager changes' Parents gets the same choices; Unknown clears a parent.
3. Edit: an entry reopened in its dialog; OK replaces it in place.

Everything runs the shipped bytes in the emulator (tests/story_emulator.py), as
tests/test_story_custom_island_event.py does.
"""
from __future__ import annotations

import re
import struct
import unittest

from story_custom_fixtures import KEEP, PARENTS, Change, Event, Spawn
from test_story_custom_island_event import (
    EVENT_BUF,
    GAMES,
    ROOT,
    SCRATCH,
    SOURCE,
    Story,
    _room_until,
    _stories,
    emulated,
    have_stock,
    stock_path,
)

FATE_KILL = 1
UNKNOWN, VILLAGER, JOEY, CUSTOM = 1, 2, 3, 4
CAUSE = {"vv3": 0xE7C, "vv4": 0x1C44, "vv5": 0x1C44}
STOP = {"vv4": 0x468C60, "vv5": 0x473440}


def _arrival_blocks(story) -> list[str]:
    p = story.proc
    n = p.export("VvfpStoryProbeArrivalParents", 0, SCRATCH, 256)
    out = []
    for k in range(n):
        p.export("VvfpStoryProbeArrivalParents", k, SCRATCH, 256)
        out.append(p.cstring(SCRATCH))
    return out


def _vv1_with_show_parents(story) -> list:
    """A New Home with the Show Parents companion: Vv1ParentageSetParents stubbed, its calls kept."""
    p = story.proc
    export = p.alloc(0x10)
    seen = []
    p.api_handlers["LoadLibraryExW"] = lambda q: (
        0x71000000 if q.wstring(q.arg(0)).endswith(
            "\\Virtual Villagers Fun Patcher Files\\VVFP VV1 Parentage.dll") else 0, 12)
    p.api_handlers["GetProcAddress"] = lambda q: (
        export if q.cstring(q.arg(1)) == "Vv1ParentageSetParents" else 0, 8)

    def set_parents(q):
        seen.append((q.arg(0), q.cstring(q.arg(1)), struct.unpack("<i", struct.pack("<I", q.arg(2)))[0],
                     struct.unpack("<i", struct.pack("<I", q.arg(3)))[0], q.cstring(q.arg(4)),
                     struct.unpack("<i", struct.pack("<I", q.arg(5)))[0],
                     struct.unpack("<i", struct.pack("<I", q.arg(6)))[0]))
        return 1, 28
    p.stub(export, set_parents)
    return seen


def _stops(story):
    if story.game in STOP:
        story.record_call(STOP[story.game], 0)


@emulated
class HealthTests(unittest.TestCase):
    def test_a_villagers_health_is_written_as_the_revive_writes_it(self):
        for game, story in _stories():
            v = story.village
            L = v.L
            v.put(2, sex="f", years=30, name="Tired")
            v.put(3, sex="m", years=30, name="Bystander")
            _stops(story)
            ok, r, _ = story.apply(Event(changes=[story.change(2, health=55)]))
            with self.subTest(game=game):
                self.assertEqual(r["died"], 0)
                self.assertEqual(v.i32(2, L["health"]), 55)
                self.assertEqual(v.byte(2, L["active"]), 1)
                self.assertEqual(v.i32(3, L["health"]), 90, "nobody else is touched")
                if game in CAUSE:
                    self.assertEqual(v.i32(2, CAUSE[game]), -1, "the living cause (-1), as the revive writes it")
                if game in STOP:
                    self.assertNotIn(STOP[game], story.calls, "a living villager's task goes on")

    def test_health_0_kills_with_the_games_own_death(self):
        for game, story in _stories():
            v = story.village
            L = v.L
            v.put(2, sex="f", years=30, name="Doomed")
            _stops(story)
            ok, r, _ = story.apply(Event(changes=[story.change(2, health=0, sick=1, litter=1)]))
            with self.subTest(game=game):
                self.assertEqual(r["died"], 1)
                self.assertEqual(v.i32(2, L["health"]), 0)
                self.assertEqual(v.byte(2, L["active"]), 1, "the body stays, for the skeleton")
                self.assertEqual(v.sick(2), 0, "a villager who dies gets no other change")
                self.assertEqual(v.i32(2, L["pregnant"]), 0, "nor a pregnancy")
                if game in CAUSE:
                    self.assertEqual(v.i32(2, CAUSE[game]), -1, "Unknown causes, as Dies")
                if game in STOP:
                    self.assertEqual(story.calls[STOP[game]], [[v.record(2)]], "the task stops, as Dies")

    def test_blank_health_is_no_change(self):
        for game, story in _stories():
            v = story.village
            L = v.L
            v.put(2, sex="f", years=30, name="Same")
            story.apply(Event(changes=[story.change(2, sick=1)]))
            with self.subTest(game=game):
                self.assertEqual(v.i32(2, L["health"]), 90)

    def test_a_new_villagers_health(self):
        for game, story in _stories():
            v = story.village
            L = v.L
            v.put(0, sex="m", years=30, name="Founder")
            _stops(story)
            ok, r, _ = story.apply(Event(spawns=[Spawn(count=1, sex=2, age=400, health=40),
                                                 Spawn(count=1, sex=1, age=400, health=0)]))
            with self.subTest(game=game):
                (alive, _, _), (dead, _, _) = story.creations
                self.assertEqual(r["born"], 2)
                self.assertEqual(v.i32(alive, L["health"]), 40)
                self.assertEqual(r["died"], 1, "health 0: made, then the game's own death")
                self.assertEqual(v.i32(dead, L["health"]), 0)
                self.assertEqual(v.byte(dead, L["active"]), 1, "a skeleton, as Dies leaves one")


def _parents_of(story, i):
    fname, mname, cap, fh, fb, mh, mb = PARENTS[story.game]
    p = story.proc
    r = story.village.record(i)
    name = lambda off: p.read(r + off, cap).split(b"\0")[0].decode()  # noqa: E731
    i32 = lambda off: struct.unpack("<i", p.read(r + off, 4))[0]  # noqa: E731
    return (name(fname), i32(fh), i32(fb)), (name(mname), i32(mh), i32(mb))


@emulated
class NewVillagerParentsTests(unittest.TestCase):
    def _spawn(self):
        return Spawn(count=1, sex=2, age=100, name="Kiri", parents_set=1,
                     father_name="Joey", father_head=2, father_body=2, father_kind=JOEY,
                     mother_name="Ana Moana", mother_head=0, mother_body=0, mother_kind=CUSTOM)

    def test_on_the_new_villagers_record_where_the_game_keeps_a_born_villagers(self):
        for game, story in _stories(("vv2", "vv3", "vv4", "vv5")):
            v = story.village
            v.put(0, sex="m", years=30, name="Founder")
            story.proc.export("VvfpStoryProbeArrivalReset")
            ok, r, _ = story.apply(Event(spawns=[self._spawn()]))
            i = story.creations[0][0]
            with self.subTest(game=game):
                self.assertEqual((r["born"], r["refused"]), (1, 0))
                self.assertEqual(_parents_of(story, i), (("Joey", 2, 2), ("Ana Moana", 0, 0)),
                                 "0 is a real head and body")
                self.assertEqual(_parents_of(story, 0), (("", 0, 0), ("", 0, 0)), "nobody else is touched")

    def test_a_new_home_keeps_them_in_the_show_parents_sidecar(self):
        if not have_stock("vv1"):
            self.skipTest("no stock executable")
        story = Story("vv1")
        seen = _vv1_with_show_parents(story)
        story.village.put(0, sex="m", years=30, name="Founder")
        ok, r, _ = story.apply(Event(spawns=[self._spawn()]))
        i = story.creations[0][0]
        self.assertEqual(r["refused"], 0)
        self.assertEqual(seen, [(i, "Joey", 2, 2, "Ana Moana", 0, 0)])
        # Without the Show Parents row there is nowhere to keep them: refused, said why.
        story = Story("vv1")
        story.village.put(0, sex="m", years=30, name="Founder")
        ok, r, text = story.apply(Event(spawns=[self._spawn()]))
        self.assertEqual((r["born"], r["refused"]), (1, 1))
        self.assertIn("Show Parents", text.replace("\n", " "))

    def test_the_births_logs_arrived_record_gets_the_parents_block(self):
        """The "Parents:" block of every Village History record (population_export.c), which
        the Family Tree and the Matchmaker read (src/vv_genealogy.py _snapshot_parents)."""
        for game, story in _stories():
            if game == "vv1":
                _vv1_with_show_parents(story)
            story.village.put(0, sex="m", years=30, name="Founder")
            story.proc.export("VvfpStoryProbeArrivalReset")
            only_mother = Spawn(count=1, sex=1, age=60, parents_set=1, father_kind=UNKNOWN,
                                mother_name="Lani", mother_head=7, mother_body=1, mother_kind=VILLAGER,
                                mother_record=0)
            nobody = Spawn(count=1, sex=1, age=60, parents_set=0, father_kind=UNKNOWN, mother_kind=UNKNOWN)
            _room_until(story, 3)
            story.apply(Event(spawns=[self._spawn(), only_mother, nobody]))
            with self.subTest(game=game):
                self.assertEqual(_arrival_blocks(story), [
                    "  Parents:\n    Father: Joey\n      Head: 2\n      Body: 2\n"
                    "    Mother: Ana Moana\n      Head: 0\n      Body: 0\n",
                    "  Parents:\n    Mother: Lani\n      Head: 7\n      Body: 1\n",
                    "",
                ])

    def test_the_block_is_what_the_family_tree_reads(self):
        import sys
        sys.path.insert(0, str(ROOT / "src"))
        import vv_genealogy
        block = ("Arrived 3\n  Name: Kiri\n  Age at arrival: 100\n  Sex: Female\n  Head: 4\n  Body: 5\n"
                 "  How: Custom Island Event\n  Parents:\n    Father: Joey Joerson\n      Head: 2\n"
                 "      Body: 2\n    Mother: Ana Moana\n      Head: 0\n      Body: 0\n").splitlines()
        self.assertEqual(vv_genealogy._snapshot_parents(block),
                         {"Father": ("Joey Joerson", 2, 2), "Mother": ("Ana Moana", 0, 0)})


@emulated
class ChangeParentsTests(unittest.TestCase):
    def test_unknown_clears_a_parent_and_joey_is_written_whole(self):
        for game, story in _stories(("vv2", "vv3", "vv4", "vv5")):
            v = story.village
            v.put(2, sex="f", years=8, name="Kid")
            story.apply(Event(changes=[story.change(2, parents_set=1, father_name="Kalani", father_head=4,
                                                    father_body=5, mother_name="Moana", mother_head=6,
                                                    mother_body=7)]))
            ok, r, _ = story.apply(Event(changes=[story.change(2, parents_set=1, father_kind=UNKNOWN,
                                                               mother_kind=JOEY, mother_name="Joey",
                                                               mother_head=2, mother_body=2)]))
            with self.subTest(game=game):
                self.assertEqual(r["refused"], 0)
                self.assertEqual(_parents_of(story, 2), (("", 0, 0), ("Joey", 2, 2)))

    def test_a_new_home_unknown_is_a_head_of_minus_2(self):
        if not have_stock("vv1"):
            self.skipTest("no stock executable")
        story = Story("vv1")
        seen = _vv1_with_show_parents(story)
        story.village.put(2, sex="f", years=8, name="Kid")
        ok, r, _ = story.apply(Event(changes=[story.change(2, parents_set=1, father_kind=UNKNOWN,
                                                           mother_kind=CUSTOM, mother_name="Mele Ana",
                                                           mother_head=0, mother_body=19)]))
        self.assertEqual(r["refused"], 0)
        self.assertEqual(seen, [(2, "", -2, -1, "Mele Ana", 0, 19)])


@emulated
class EditTests(unittest.TestCase):
    """Edit: OK replaces the entry in place (same position), with exactly the dialog's
    values -- what the earlier entry held and the dialog no longer does is gone."""

    def test_replace_keeps_the_position_and_takes_only_the_new_values(self):
        if not have_stock("vv3"):
            self.skipTest("no stock executable")
        story = Story("vv3")
        p = story.proc
        p.write(EVENT_BUF, Event().pack())
        for change, index in ((Change(index=0, fingerprint=0, sick=1, head=5), 4),
                              (Change(index=0, fingerprint=0, fate=1), 7),
                              (Change(index=0, fingerprint=0, head=2), 9)):
            p.write(SCRATCH, change.pack())
            self.assertEqual(p.export("VvfpStoryProbeMerge", EVENT_BUF, SCRATCH, index, 0x11), 1)
        p.write(SCRATCH, Change(index=-1, fingerprint=0, health=30, parents_set=1, father_kind=JOEY,
                                father_name="Joey", father_head=2, father_body=2).pack())
        self.assertEqual(p.export("VvfpStoryProbeReplace", EVENT_BUF, 0, SCRATCH, 0x22), 1)
        self.assertEqual(p.export("VvfpStoryProbeReplace", EVENT_BUF, 3, SCRATCH, 0x22), 0, "no entry 3")
        at = 4 + 48 + 600 + 4 * 7 + 8 * Event.SPAWN_SIZE
        self.assertEqual(struct.unpack("<i", p.read(EVENT_BUF + at, 4))[0], 3, "still three entries")

        def entry(k):
            raw = p.read(EVENT_BUF + at + 4 + k * Change.SIZE, Change.SIZE)
            index, fp, fate, sick = struct.unpack("<iIii", raw[:16])
            head = struct.unpack("<i", raw[28:32])[0]
            health, father_kind = struct.unpack("<2i", raw[Change.SIZE - 20:Change.SIZE - 12])
            father = raw[128:156].split(b"\0")[0].decode()
            return index, fp, fate, sick, head, health, father_kind, father
        self.assertEqual(entry(0), (4, 0x22, 0, 0, KEEP, 30, JOEY, "Joey"),
                         "the villager kept, the old sick and head gone, the new health and father in")
        self.assertEqual(entry(1)[:3], (7, 0x11, 1), "the others untouched, in their places")
        self.assertEqual(entry(2)[:1] + entry(2)[4:5], (9, 2))


class DialogTests(unittest.TestCase):
    """The dialogs as the owner asked for them (static: the shipped resource and source)."""

    def setUp(self):
        self.rc = (SOURCE / "vvfp_story_upgrades.rc").read_text(encoding="utf-8")
        self.ui = (SOURCE / "story_custom_ui.inc").read_text(encoding="utf-8")

    def dialog(self, number: int) -> str:
        start = self.rc.index(f"{number} DIALOGEX")
        return self.rc[start:self.rc.index("\nEND", start)]

    def test_every_list_has_an_edit_button_and_double_click(self):
        main = self.dialog(302)
        for button in (1115, 1125, 1140):
            self.assertRegex(main, rf'PUSHBUTTON  "Edit\.\.\.", {button},')
        for listbox in (1111, 1121, 1131):
            line = next(l for l in main.splitlines() if l.strip().startswith(f"LISTBOX     {listbox},"))
            self.assertIn("LBS_NOTIFY", line)
        for edit in ("IDC_CE_SPAWN_EDIT", "IDC_CE_CHANGE_EDIT", "IDC_CE_OTHER_EDIT"):
            self.assertIn(f"id == {edit} ||", self.ui)
        self.assertEqual(self.ui.count("HIWORD(wparam) == LBN_DBLCLK"), 3)

    def test_health_boxes_with_the_warning_under_them(self):
        changes = self.dialog(303)
        spawn = self.dialog(304)
        self.assertIn("EDITTEXT    2084,", changes)
        self.assertIn('"Health (0-100):"', changes)
        self.assertIn("EDITTEXT    3163,", spawn)
        self.assertIn('"Health (0-100):"', spawn)
        y = lambda text, cid: int(re.search(rf"\b{cid}, \d+, (\d+),", text).group(1))  # noqa: E731
        self.assertGreater(y(changes, 2085), y(changes, 2084), "the warning is under the box")
        self.assertGreater(y(spawn, 3164), y(spawn, 3163))
        self.assertIn('"Warning: health 0 kills the villager', self.ui)
        self.assertIn("SetDlgItemTextA(window, IDC_CH_HEALTH_NOTE, UI_HEALTH_WARNING);", self.ui)
        self.assertIn("SetDlgItemTextA(window, IDC_SP_HEALTH_NOTE, UI_HEALTH_WARNING);", self.ui)

    def test_parents_choices(self):
        parents = self.dialog(305)
        for combo in (3208, 3210):
            self.assertIn(f"COMBOBOX    {combo},", parents)
        for box in (3201, 3209, 3204, 3211):          # first and last names
            self.assertIn(f"EDITTEXT    {box},", parents)
        self.assertIn('ui_combo_add(window, id, "Unknown", CE_PARENT_UNKNOWN);', self.ui)
        self.assertIn('"Custom (type the name and looks below)", CE_PARENT_CUSTOM', self.ui)
        self.assertIn("return ui.game == 4 || ui.game == 5;", self.ui, "Joey: The Tree of Life and New Believers")
        self.assertIn('PUSHBUTTON  "Parents...", 3165,', self.dialog(304))


class JoeyInTheExecutablesTests(unittest.TestCase):
    """Joey is The Tree of Life's and New Believers' own: their village seeding passes the
    string "Joey", head 2 and body 2 to the conception routine (VV4 0x467C00..0x467C15, VV5
    0x471B58..0x471B6D); A New Home to The Secret City have no "Joey" but the Villager
    Details screen's width probe "Joey Joerson", which every game has."""

    SITES = {"vv4": (0x467C00, 0x467C15, 0x45E7B0), "vv5": (0x471B58, 0x471B6D, 0x465E00)}

    def _image(self, game):
        import pefile
        path = stock_path(game)
        if not path.is_file():
            self.skipTest("no stock executable")
        pe = pefile.PE(str(path))
        return pe.OPTIONAL_HEADER.ImageBase, pe.get_memory_mapped_image(), path.read_bytes()

    def test_the_seeding_passes_joey_head_2_body_2(self):
        for game, (start, call, routine) in self.SITES.items():
            base, image, _ = self._image(game)
            code = image[start - base:call + 5 - base]
            with self.subTest(game=game):
                # push 2 ; push 2 ; push offset "Joey"
                self.assertEqual(code[:5], b"\x6A\x02\x6A\x02\x68")
                joey = struct.unpack("<I", code[5:9])[0]
                self.assertEqual(image[joey - base:joey - base + 5], b"Joey\0")
                self.assertEqual(code[-5], 0xE8)
                self.assertEqual(call + 5 + struct.unpack("<i", code[-4:])[0], routine)

    def test_only_those_two_games_name_joey(self):
        for game in GAMES:
            path = stock_path(game)
            if not path.is_file():
                continue
            data = path.read_bytes()
            with self.subTest(game=game):
                self.assertIn(b"Joey Joerson\0", data, "the Details screen's width probe")
                self.assertEqual(b"\0Joey\0" in data, game in ("vv4", "vv5"))


if __name__ == "__main__":
    unittest.main()
