"""The Family Tree marks every special villager by itself (all five games).

The owner (2026-10-22): "Family Tree: All Tribal Chiefs in VV3 will now be automatically marked under Special
Villager status", then every special or custom status in all five games: a converted Heathen by their mask
colour, the Golden Child, the Retired Heathen Chief, the Tribal Chief, the Scholar, the Esteemed Elder, every
other title the patcher knows and the player's own Custom titles -- each a mark of its own, several at once,
a former holder keeping it.  From every source: the save, every log record's Special villager / Custom title
lines, the graves and the patcher's own files; a change of looks or title never makes a new villager.  The
player can untick one and it stays off (the tree's own data, never the save); a tree saved before gains the
marks on opening without losing the player's own.

Covered here, on the repository's fixture saves of all five games (tests/fixtures/rename_tribe) and on
villages built by hand.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
import vv_genealogy as gen  # noqa: E402
import vv_genealogy_window as gw  # noqa: E402
import vv_last_names as ln  # noqa: E402
import vv_villager_info as info  # noqa: E402
from test_identity_through_looks import T1, T2, Changed, history_text  # noqa: E402
from test_reconcile import CASES, Base  # noqa: E402

GAMES = CASES[:5]               # one fixture save of each game


def death(number: int, name: str, head: int, body: int, age: int, *lines: str) -> str:
    more = "".join(f"  {line}\n" for line in lines)
    return (f"Death {number}\n  Name: {name}\n{more}  Age at death: {age}\n  Sex: Male\n  Head: {head}\n"
            f"  Body: {body}\n\n")


def holder(village: gen.Village, name: str, alive: bool | None = None) -> gen.Person:
    found = [p for p in village.people.values() if p.name == name and (alive is None or p.alive == alive)]
    assert len(found) == 1, [(p.key, p.alive, p.statuses) for p in found]
    return found[0]


class TheTitlesAsMarks(unittest.TestCase):
    def test_each_logged_title_names_its_mark(self) -> None:
        self.assertEqual(gen.status_marks("Tribal Chief"), ["Tribal Chief"])
        self.assertEqual(gen.status_marks("Retired Heathen Chief"), ["Retired Heathen Chief"])
        self.assertEqual(gen.status_marks("Former Heathen (red mask)"), ["Converted Red Mask Heathen"])
        self.assertEqual(gen.status_marks("Former Heathen (blue mask)"), ["Converted Blue Mask Heathen"])
        self.assertEqual(gen.status_marks("Former Heathen Master (purple mask)"),
                         ["Former Heathen Master", "Converted Purple Mask Heathen"])
        self.assertEqual(gen.status_marks("Heathen Mommy"), ["Heathen Mommy"])
        for nothing in (None, "", "none", "(none)"):
            self.assertEqual(gen.status_marks(nothing), [])

    def test_every_status_has_its_own_preset_colour_and_the_old_presets_keep_theirs(self) -> None:
        for label in gen.STATUS_ORDER:
            self.assertIn(label, ft.STATUS_COLOURS, label)
            self.assertEqual(gw.PRESET_MARKS[label], ft.STATUS_COLOURS[label])
        self.assertEqual(len(set(ft.STATUS_COLOURS.values())), len(ft.STATUS_COLOURS), "each its own colour")
        self.assertEqual((gw.PRESET_MARKS["Tribal Chief"], gw.PRESET_MARKS["Esteemed Elder"],
                          gw.PRESET_MARKS["Scholar"], gw.PRESET_MARKS["Golden Child"]),
                         ("#d4a017", "#7b68ee", "#1e90ff", "#ffb000"))
        self.assertEqual(ft.status_colour("Keeper of Shells"), ft.status_colour("Keeper of Shells"))
        self.assertIn(ft.status_colour("Keeper of Shells"), ft.CUSTOM_MARK_COLOURS)


class FromTheLogs(Base):
    TITLES = {1: ["Golden Child"], 2: ["Esteemed Elder"], 3: ["Tribal Chief"], 4: ["Scholar"],
              5: ["Retired Heathen Chief", "Former Heathen (red mask)", "Heathen Mommy"]}

    def test_a_dead_holder_and_a_former_holder_keep_every_status_and_custom_title(self) -> None:
        for tag, game in GAMES:
            with self.subTest(game=game):
                v = self.village(tag, game)
                data = v.save_path(1).read_bytes()
                people = v.people(data)
                x = people[0]
                titles = self.TITLES[game]
                # x held the title (and a Custom title) in the earlier snapshot only: still theirs.
                history_text(v, [(T1, people), (T2, people)],
                                {(T1, x.name): [f"Special villager: {titles[0]}", "Custom title: Keeper of Shells"]})
                v.deaths("".join(death(k + 1, f"Gone{k}", 3, 4, 900 + k, f"Special villager: {t}",
                                       "Custom title: Old Wise One") for k, t in enumerate(titles)))
                village = gen.load_village(v.folder, game, 1)
                own = holder(village, x.name, alive=True).statuses
                for label in gen.status_marks(titles[0]) + ["Keeper of Shells"]:
                    self.assertIn(label, own)
                for k, t in enumerate(titles):
                    dead = holder(village, f"Gone{k}")
                    self.assertEqual(dead.gone, "died")
                    self.assertEqual(dead.statuses, gen.status_marks(t) + ["Old Wise One"])

    def test_an_island_event_change_gives_both_titles(self) -> None:
        v = self.village("huttest", 3)
        people = v.people(v.save_path(1).read_bytes())
        x = people[0]
        history_text(v, [(T1, people)], {(T1, x.name): ["Custom title: Fisher -> Diver"]})
        village = gen.load_village(v.folder, 3, 1)
        self.assertEqual(holder(village, x.name, alive=True).statuses[-2:], ["Fisher", "Diver"])

    def test_a_conversion_with_no_mask_colour_is_a_former_heathen(self) -> None:
        v = self.village("huttest", 5)
        v.births("Arrived 1\n  Name: Turned\n  Age at arrival: 400\n  Sex: Male\n  Head: 2\n  Body: 3\n"
                 "  How: Converted from the Heathens\n\n")
        village = gen.load_village(v.folder, 5, 1)
        self.assertEqual(holder(village, "Turned").statuses, ["Former Heathen"])


class FromTheSave(Base):
    def test_the_save_keeps_each_games_status(self) -> None:
        for tag, game in GAMES[:4]:
            with self.subTest(game=game):
                v = self.village(tag, game)
                data = bytearray(v.save_path(1).read_bytes())
                at = v.entries(bytes(data))[0]
                want = {1: "Golden Child", 2: "Esteemed Elder", 3: "Tribal Chief", 4: "Scholar"}[game]
                if game == 1:
                    struct.pack_into("<i", data, at + ln.FIELDS[1].family, 199)
                elif game == 2:
                    data[at + gen.VV2_ELDER_FROM_NAME] = 1
                elif game == 3:
                    data[at + gen.VV3_CHIEF_FROM_NAME] = 1
                else:
                    struct.pack_into("<5f", data, at + gen.VV4_SKILLS_FROM_NAME, 88.0, 90.0, 99.0, 100.0, 88.5)
                v.write_save(1, bytes(data))
                x = v.people(bytes(data))[0]
                village = gen.load_village(v.folder, game, 1)
                self.assertIn(want, holder(village, x.name, alive=True).statuses)

    def test_secret_city_elder_by_three_master_skills_and_not_by_two(self) -> None:
        v = self.village("huttest", 3)
        data = bytearray(v.save_path(1).read_bytes())
        first, second = v.entries(bytes(data))[:2]
        struct.pack_into("<5i", data, first + gen.VV3_SKILLS_FROM_NAME, 88, 90, 100, 0, 0)
        struct.pack_into("<5i", data, second + gen.VV3_SKILLS_FROM_NAME, 88, 90, 87, 0, 0)
        self.assertEqual(gen.save_statuses(3, bytes(data), first), ["Esteemed Elder"])
        self.assertEqual(gen.save_statuses(3, bytes(data), second), [])

    def test_no_status_byte_no_mark(self) -> None:
        v = self.village("huttest", 3)
        data = bytearray(v.save_path(1).read_bytes())
        at = v.entries(bytes(data))[0]
        data[at + gen.VV3_CHIEF_FROM_NAME] = 0
        struct.pack_into("<5i", data, at + gen.VV3_SKILLS_FROM_NAME, 0, 0, 0, 0, 0)
        self.assertEqual(gen.save_statuses(3, bytes(data), at), [])


class FromTheGravesAndFiles(Base):
    def test_a_secret_city_grave_keeps_a_dead_chief(self) -> None:
        import vv_graves
        v = self.village("huttest", 3)
        data = bytearray(v.save_path(1).read_bytes())
        lay = vv_graves.LAYOUTS[3]
        at = lay.base                   # the first grave: the dead chief, age 900
        data[at:at + lay.name_cap] = b"Oldchief".ljust(lay.name_cap, b"\0")
        struct.pack_into("<i", data, at + lay.age, 900)
        data[at + lay.chief] = 1
        v.write_save(1, bytes(data))
        v.deaths(death(1, "Oldchief", 3, 4, 900) + death(2, "Other", 3, 5, 901))
        village = gen.load_village(v.folder, 3, 1)
        self.assertEqual(holder(village, "Oldchief").statuses, ["Tribal Chief"])
        self.assertEqual(holder(village, "Other").statuses, [])

    def test_new_believers_former_heathens_file(self) -> None:
        import vv_lost_titles as lt
        import vv_save_layout as layout
        v = self.village("huttest", 5)
        data = v.save_path(1).read_bytes()
        f = ln.FIELDS[5]
        living = [at for at in v.entries(data) if data[at + gen.VV5_FACTION_FROM_NAME] == 0]
        at = living[0]
        path = layout.route(v.folder, lt.FORMER_FILE.format(slot=1))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"VFH1" + struct.pack("<III", 1, 5, 1) + struct.pack("<II", ln._title_identity(data, at, f), 2))
        name = data[at:at + f.name_cap].split(b"\0")[0].decode("latin-1")
        village = gen.load_village(v.folder, 5, 1)
        p = next(p for p in village.people.values() if p.alive and p.name == name)
        self.assertIn("Converted Red Mask Heathen", p.statuses)


class ThroughLooksAndTitles(Changed):
    def test_a_chief_robed_with_a_new_body_is_one_villager_with_the_mark(self) -> None:
        v, old, now, x, new_body = self.setup_game("huttest", 3)
        history_text(v, [(T1, v.people(old)), (T2, v.people(now))], {(T1, x.name): ["Special villager: Tribal Chief"]})
        village = gen.load_village(v.folder, 3, 1)
        mine = self.one_of(village, x.name)
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0].key, (x.name, x.head, new_body))
        self.assertIn("Tribal Chief", mine[0].statuses)
        edits = ft.Edits()
        ft.apply_auto_marks(edits, village)
        self.assertIn("Tribal Chief", edits.entries[f"{x.name}|{x.head}|{new_body}"]["marks"])

    def test_a_replaced_chief_and_the_new_one_are_both_marked(self) -> None:
        v = self.village("huttest", 3)
        people = v.people(v.save_path(1).read_bytes())
        a, b = people[0], people[1]
        history_text(v, [(T1, people), (T2, people)], {(T1, a.name): ["Special villager: Tribal Chief"],
                                                       (T2, b.name): ["Special villager: Tribal Chief"]})
        village = gen.load_village(v.folder, 3, 1)
        self.assertIn("Tribal Chief", holder(village, a.name, alive=True).statuses)
        self.assertIn("Tribal Chief", holder(village, b.name, alive=True).statuses)


def hand_village() -> gen.Village:
    people = {1: gen.Person(1, "Chief", 1, 1, sex="Male", age=900, alive=True, statuses=["Tribal Chief", "Esteemed Elder"]),
              2: gen.Person(2, "Plain", 2, 2, sex="Female", age=800, alive=True),
              3: gen.Person(3, "Old", 3, 3, sex="Male", age=1200, gone="died",
                            statuses=["Converted Red Mask Heathen", "Keeper of Shells"])}
    v = gen.Village(3, 1, "Test Tribe", people)
    gen._generations(v, {})
    gen.number_people(v)
    return v


class TheTreesEdits(unittest.TestCase):
    def test_marks_given_in_their_colours_once(self) -> None:
        v, e = hand_village(), ft.Edits()
        self.assertTrue(ft.apply_auto_marks(e, v))
        self.assertEqual(e.entries["Chief|1|1"]["marks"], ["Tribal Chief", "Esteemed Elder"])
        self.assertEqual(e.entries["Chief|1|1"]["mark"], "Tribal Chief")
        self.assertEqual(e.entries["Old|3|3"]["marks"], ["Converted Red Mask Heathen", "Keeper of Shells"])
        self.assertNotIn("Plain|2|2", e.entries)
        self.assertEqual(e.marks["Tribal Chief"], "#d4a017")
        self.assertEqual(e.marks["Keeper of Shells"], ft.status_colour("Keeper of Shells"))
        before = e.to_data()
        self.assertFalse(ft.apply_auto_marks(e, v), "the second time changes nothing")
        self.assertEqual(e.to_data(), before)

    def test_an_old_tree_gains_the_marks_and_keeps_the_players_own(self) -> None:
        v = hand_village()
        old = {"format": 1, "marks": {"Favourite": "#ff1493", "Tribal Chief": "#123456"},
               "entries": {"Chief|1|1": {"mark": "Favourite", "lines": ["Our chief"]}, "Plain|2|2": {"mark": "Favourite"}}}
        e = ft.Edits.from_data(old)
        ft.apply_auto_marks(e, v)
        self.assertEqual(e.entries["Chief|1|1"]["marks"], ["Favourite", "Tribal Chief", "Esteemed Elder"])
        self.assertEqual(e.entries["Chief|1|1"]["mark"], "Favourite")
        self.assertEqual(e.entries["Chief|1|1"]["lines"], ["Our chief"])
        self.assertEqual(ft.entry_marks(e.entries["Plain|2|2"]), ["Favourite"])
        self.assertEqual(e.marks["Tribal Chief"], "#123456", "the player's own colour is kept")
        back = ft.Edits.from_data(e.to_data())
        self.assertEqual(back.entries, e.entries)

    def test_an_old_pages_own_mark_is_kept_beside_the_new_ones(self) -> None:
        v = hand_village()
        e = ft.Edits.from_data({"format": 1, "marks": {"Favourite": "#ff1493"},
                                "page_edits": {"1": {"entries": {"Chief|1|1": {"mark": "Favourite"}}}}})
        ft.apply_auto_marks(e, v)
        view = ft.page_view(e, v, 0)
        self.assertEqual(ft.entry_marks(view.entries["Chief|1|1"]), ["Favourite", "Tribal Chief", "Esteemed Elder"])

    def test_unmarked_stays_off_and_removed_from_everyone_stays_off(self) -> None:
        v = hand_village()
        e = ft.Edits(entries={"Chief|1|1": {"unmarked": ["Tribal Chief"]}})
        ft.apply_auto_marks(e, v)
        self.assertEqual(e.entries["Chief|1|1"]["marks"], ["Esteemed Elder"])
        e = ft.Edits(marks_off=["Esteemed Elder"])
        ft.apply_auto_marks(e, v)
        self.assertEqual(e.entries["Chief|1|1"]["marks"], ["Tribal Chief"])
        self.assertNotIn("Esteemed Elder", e.marks)
        e = ft.Edits(mark_names={"Tribal Chief": "Big Chief"}, marks={"Big Chief": "#000001"})
        ft.apply_auto_marks(e, v)
        self.assertEqual(e.entries["Chief|1|1"]["marks"], ["Big Chief", "Esteemed Elder"])
        self.assertNotIn("Tribal Chief", e.marks)
        back = ft.Edits.from_data(ft.Edits(mark_names={"A": "B"}, marks_off=["C"],
                                           entries={"k": {"marks": ["X", "Y"], "mark": "X", "unmarked": ["Z"]}}).to_data())
        self.assertEqual((back.mark_names, back.marks_off, back.entries["k"]),
                         ({"A": "B"}, ["C"], {"marks": ["X", "Y"], "mark": "X", "unmarked": ["Z"]}))

    def test_every_mark_is_drawn_and_in_the_key(self) -> None:
        for style in ("border", "glow"):
            with self.subTest(style=style):
                v, e = hand_village(), ft.Edits(mark_style=style)
                ft.apply_auto_marks(e, v)
                sc = ft.scene(ft.layout(v, e), "Virtual Villagers - The Secret City", {})
                rings = {i.target[1] for i in sc.items if isinstance(i, ft.Shape) and i.pid == 1
                         and i.target and i.target[0] == "mark"}
                self.assertEqual(rings, {"Tribal Chief", "Esteemed Elder"})
                self.assertTrue(any(isinstance(i, ft.Shape) and i.pid == 1 and i.stroke == "#7b68ee" for i in sc.items))
                texts = [i.text for i in sc.items if isinstance(i, ft.Text)]
                for label in ("Tribal Chief", "Esteemed Elder", "Converted Red Mask Heathen", "Keeper of Shells"):
                    self.assertIn(label, texts)

    def test_villager_info_lists_every_mark(self) -> None:
        v, e = hand_village(), ft.Edits()
        ft.apply_auto_marks(e, v)
        text = info.plain_text(info.info_lines(v, e, 1))
        self.assertIn("Special marks: Tribal Chief, Esteemed Elder", text)

    def test_search_finds_a_status(self) -> None:
        v = hand_village()
        self.assertEqual(gw.find_villagers(v, ft.Edits(), "tribal chief"), [1])


class FakeEditor:
    """The Villagers tab's mark buttons and tick boxes, without a window."""
    _entry = gw.TreeEditor._entry
    _entry_by_key = gw.TreeEditor._entry_by_key
    _pkey = gw.TreeEditor._pkey
    _set_entry = gw.TreeEditor._set_entry
    _set_entry_key = gw.TreeEditor._set_entry_key
    _set_marks = gw.TreeEditor._set_marks
    _give_mark = gw.TreeEditor._give_mark
    _take_mark = gw.TreeEditor._take_mark
    _tick_mark = gw.TreeEditor._tick_mark
    _apply_mark = gw.TreeEditor._apply_mark
    _remove_mark = gw.TreeEditor._remove_mark
    _rename_mark = gw.TreeEditor._rename_mark
    _all_entries = gw.TreeEditor._all_entries

    def __init__(self, village, edits):
        self.village = self.full_village = village
        self.edits = edits
        self.page = 0
        self.selected = [1]
        self.picked = None
        self.mark_var = mock.Mock()

    def _saved(self):
        self.edits.page_edits = ft.clean_page_edits(self.edits.page_edits)

    def _refresh_marks(self):
        pass

    def _mark_at(self):
        return self.picked

    def shown(self, pid=1):
        return ft.entry_marks(ft.page_view(self.edits, self.village, 0).entries.get(
            ft.entry_key(self.village, self.village.people[pid]), {}))


class ThePlayerDecides(unittest.TestCase):
    def editor(self) -> FakeEditor:
        v, e = hand_village(), ft.Edits()
        ft.apply_auto_marks(e, v)
        return FakeEditor(v, e)

    def test_unticked_stays_off_when_the_tree_opens_again(self) -> None:
        ed = self.editor()
        ed._tick_mark("Tribal Chief", False)
        self.assertEqual(ed.shown(), ["Esteemed Elder"])
        again = ft.Edits.from_data(ed.edits.to_data())      # saved, and opened again
        ft.apply_auto_marks(again, ed.village)
        self.assertEqual(ft.entry_marks(ft.page_view(again, ed.village, 0).entries["Chief|1|1"]), ["Esteemed Elder"])
        ed._tick_mark("Tribal Chief", True)                 # ticked again: back, and no longer kept off
        self.assertEqual(ed.shown(), ["Esteemed Elder", "Tribal Chief"])
        self.assertNotIn("Tribal Chief", ed._entry(ed.village.people[1]).get("unmarked") or [])

    def test_remove_mark_with_none_picked_takes_every_mark_off(self) -> None:
        ed = self.editor()
        ed.mark_var.get.return_value = "(none)"
        ed._apply_mark(clear=True)
        self.assertEqual(ed.shown(), [])
        self.assertEqual(sorted(ed._entry(ed.village.people[1])["unmarked"]), ["Esteemed Elder", "Tribal Chief"])
        ed.mark_var.get.return_value = "Scholar"
        ed.edits.marks["Scholar"] = "#1e90ff"
        ed._apply_mark()                                    # Give mark adds beside the others
        self.assertEqual(ed.shown(), ["Scholar"])

    def test_removed_from_everyone_and_renamed(self) -> None:
        ed = self.editor()
        ed._rename_mark("Tribal Chief", "Big Chief")
        self.assertEqual(ed.edits.mark_names, {"Tribal Chief": "Big Chief"})
        self.assertEqual(ed.shown(), ["Big Chief", "Esteemed Elder"])
        self.assertFalse(ft.apply_auto_marks(ed.edits, ed.village), "the renamed mark is not given again")
        ed.picked = "Esteemed Elder"
        with mock.patch.object(gw.messagebox, "askyesno", return_value=True):
            ed._remove_mark()
        self.assertEqual(ed.shown(), ["Big Chief"])
        self.assertEqual(ed.edits.marks_off, ["Esteemed Elder"])
        ft.apply_auto_marks(ed.edits, ed.village)
        self.assertEqual(ed.shown(), ["Big Chief"])
        self.assertNotIn("Esteemed Elder", ed.edits.marks)

    def test_the_save_is_never_written(self) -> None:
        # The marks live in the tree's own edits: nothing here writes a save or a log.
        self.assertNotIn("write_bytes", gw.TreeEditor._take_mark.__code__.co_names)
        self.assertNotIn("write_bytes", ft.apply_auto_marks.__code__.co_names)


if __name__ == "__main__":
    unittest.main()
