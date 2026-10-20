"""Repair Saves & Logs for "Esteemed Elders' Totems Use No Villager Records" (src/vv_vv2_totem_store.py):
ElderTotems.dat, Move Totems Out of the Save, Put Totems Back Into the Save, Change Totem Colour, the
village's give-automatically setting and the warning before a build without the patch.

Each test builds a save folder by hand (tests/test_vv2_totem_repairs.py's helpers), never the owner's.
"""
from __future__ import annotations

import random
import struct
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_log_tools as tools  # noqa: E402
import vv_vv2_totem_store as ts  # noqa: E402
import vv_vv2_totems as vt  # noqa: E402
from test_vv2_totem_repairs import NoGame, Running, Village, crowd, death, elder_and_totem, person  # noqa: E402

NOW = datetime(2026, 10, 20, 9, 0, 0)


def statues(v: Village) -> list[str]:
    data = v.save.read_bytes()
    return [vt._text(data, at, vt.NAME_CAP) for _k, at in ts.statues_in_save(data)]


class ThePath(unittest.TestCase):
    def test_the_file_is_exactly_elder_totems_dat_in_each_saves_own_folder(self):
        base = Path("C:/Docs/LDW/Virtual Villagers - The Lost Children")
        for slot in range(1, 6):
            self.assertEqual(
                ts.store_path(base, slot),
                base / "Virtual Villagers Fun Patcher" / f"Save {slot}" / "Data" / "Elder Totems" / "ElderTotems.dat")
        with self.assertRaises(ts.StoreError):
            ts.store_path(base, 6)

    def test_the_companion_builds_the_same_path(self):
        source = (ROOT / "native" / "vvfp_vv2_totems" / "vvfp_vv2_totems.c").read_text(encoding="utf-8")
        self.assertIn(r'"\\Virtual Villagers Fun Patcher\\Save %d\\Data\\Elder Totems\\ElderTotems.dat"', source)


class TheFormat(unittest.TestCase):
    def test_round_trip_and_the_check(self):
        entry = bytearray(ts.ENTRY)
        entry[ts.E_NAME:ts.E_NAME + 4] = b"Kona"
        store = ts.Store(3, [("Kona", 1, 2, 1)], [ts.Totem(bytes(entry))])
        data = ts.serialize(store)
        again = ts.parse(data)
        self.assertEqual((again.roster, [t.name for t in again.totems]), (store.roster, ["Kona"]))
        broken = bytearray(data)
        broken[ts.HEADER + 3] ^= 1
        with self.assertRaises(ts.StoreError):
            ts.parse(bytes(broken))
        with self.assertRaises(ts.StoreError):
            ts.parse(data[:-1])

    def test_new_type_keeps_the_games_range(self):
        self.assertEqual(ts.new_type(123, 0), 120)
        self.assertEqual(ts.new_type(1, 7), 7)
        self.assertEqual(ts.new_type(42, 5) % 8, 5)
        for old in range(1, 124):
            for face in range(8):
                value = ts.new_type(old, face)
                self.assertTrue(1 <= value <= 123 and value % 8 == face)


class MoveOut(unittest.TestCase):
    def test_statues_move_into_the_file_and_their_entries_are_freed(self):
        e1, t1 = elder_and_totem("Hoto Kenobi", head=14, body=5)
        e2, t2 = elder_and_totem("Topaz Kenobi", head=2, body=8)
        alive = person("Marked Alive", totem=True, health=40)
        v = Village(self, crowd(4) + [e1, t1, e2, alive, t2])
        result = ts.move_out(v.folder, 1, processes=NoGame(), now=NOW)
        self.assertEqual([t.name for t in result.moved], ["Hoto Kenobi", "Topaz Kenobi"])
        self.assertEqual(result.kept_alive, ["Marked Alive"])
        self.assertEqual(statues(v), [])
        self.assertEqual(len(v.entries()), 7)               # 9 entries less the 2 statues
        stored = ts.read(v.folder, 1)
        self.assertEqual([t.name for t in stored.totems], ["Hoto Kenobi", "Topaz Kenobi"])
        self.assertEqual((stored.totems[0].x, stored.totems[0].y), (400, 900))
        self.assertTrue(ts.bound(stored, v.save.read_bytes()))
        self.assertIn("Totem moved into ElderTotems.dat", v.repairs())
        self.assertTrue(v.backups())

    def test_a_statue_already_in_the_file_is_not_doubled(self):
        e1, t1 = elder_and_totem("Hoto Kenobi", head=14, body=5)
        v = Village(self, crowd(4) + [e1, t1])
        ts.move_out(v.folder, 1, processes=NoGame(), now=NOW)
        v.save.write_bytes(__import__("test_vv2_totem_repairs").save_for(crowd(4) + [e1, t1]))  # a restored save
        result = ts.move_out(v.folder, 1, processes=NoGame(), now=NOW)
        self.assertEqual((len(result.moved), len(result.already)), (0, 1))
        self.assertEqual(len(ts.read(v.folder, 1).totems), 1)
        self.assertEqual(statues(v), [])

    def test_refused_while_the_game_runs_and_with_nothing_to_move(self):
        e1, t1 = elder_and_totem("Hoto Kenobi", head=14, body=5)
        v = Village(self, crowd(4) + [e1, t1])
        before = v.save.read_bytes()
        with self.assertRaises(tools.LogToolError):
            ts.move_out(v.folder, 1, processes=Running(), now=NOW)
        self.assertEqual(v.save.read_bytes(), before)
        w = Village(self, crowd(4))
        with self.assertRaises(ts.StoreError):
            ts.move_out(w.folder, 1, processes=NoGame(), now=NOW)

    def test_another_villages_file_is_never_added_to(self):
        e1, t1 = elder_and_totem("Hoto Kenobi", head=14, body=5)
        v = Village(self, crowd(4) + [e1, t1])
        other = ts.Store(1, [("Somebody Else", 1, 1, 1), ("Another", 2, 2, 2)], [])
        path = ts.store_path(v.folder, 1)
        path.parent.mkdir(parents=True)
        path.write_bytes(ts.serialize(other))
        before = v.save.read_bytes()
        with self.assertRaises(ts.StoreError):
            ts.move_out(v.folder, 1, processes=NoGame(), now=NOW)
        self.assertEqual(v.save.read_bytes(), before)
        self.assertEqual(path.read_bytes(), ts.serialize(other))


class PutBack(unittest.TestCase):
    def test_every_totem_goes_back_when_there_is_room(self):
        e1, t1 = elder_and_totem("Hoto Kenobi", head=14, body=5)
        v = Village(self, crowd(4) + [e1, t1])
        ts.move_out(v.folder, 1, processes=NoGame(), now=NOW)
        result = ts.put_back(v.folder, 1, processes=NoGame(), now=NOW)
        self.assertEqual([t.name for t in result.put_back], ["Hoto Kenobi"])
        self.assertEqual(result.left, [])
        self.assertEqual(statues(v), ["Hoto Kenobi"])
        self.assertEqual(ts.read(v.folder, 1).totems, [])
        data = v.save.read_bytes()
        at = ts.statues_in_save(data)[0][1]
        self.assertEqual(struct.unpack_from("<ii", data, at + vt.X), (400, 900))

    def test_only_as_many_as_fit_the_rest_stay_and_the_player_is_told(self):
        pairs = [elder_and_totem(f"Elder{chr(65 + k)}", head=k, body=k) for k in range(3)]
        people = crowd(250) + [e for e, _t in pairs] + [t for _e, t in pairs]
        v = Village(self, people)
        ts.move_out(v.folder, 1, processes=NoGame(), now=NOW)       # 253 villagers: 3 records free
        mother = v.save.read_bytes()
        # One mother carrying twins: 2 of the 3 free records are owed.
        save = bytearray(mother)
        at = v.entries()[0]
        struct.pack_into("<ii", save, at + vt.CONCEIVED, 1, 2)
        v.save.write_bytes(bytes(save))
        result = ts.put_back(v.folder, 1, processes=NoGame(), now=NOW)
        self.assertEqual((len(result.put_back), len(result.left), result.free), (1, 2, 1))
        self.assertIn("stay in ElderTotems.dat", result.summary())
        self.assertEqual(len(ts.read(v.folder, 1).totems), 2)
        self.assertIn("Left in ElderTotems.dat", v.repairs())


class Colour(unittest.TestCase):
    def test_a_totem_in_the_file_changes_face(self):
        e1, t1 = elder_and_totem("Hoto Kenobi", head=14, body=5, kind=10)
        v = Village(self, crowd(4) + [e1, t1])
        ts.move_out(v.folder, 1, processes=NoGame(), now=NOW)
        [t] = ts.list_totems(v.folder, 1)
        result = ts.change_colour(v.folder, 1, t.key, 6, processes=NoGame(), now=NOW)
        self.assertEqual((result.old_face, result.new_face), (10 % 8, 6))
        self.assertEqual(ts.read(v.folder, 1).totems[0].type % 8, 6)
        self.assertIn(ts.LABEL_COLOUR, v.repairs())

    def test_a_totem_still_in_the_save_changes_face_there(self):
        e1, t1 = elder_and_totem("Hoto Kenobi", head=14, body=5, kind=9)
        v = Village(self, crowd(4) + [e1, t1])
        [t] = ts.list_totems(v.folder, 1)
        ts.change_colour(v.folder, 1, t.key, 3, processes=NoGame(), now=NOW)
        data = v.save.read_bytes()
        self.assertEqual(struct.unpack_from("<i", data, ts.statues_in_save(data)[0][1] + vt.TYPE)[0] % 8, 3)


class SeveralColours(unittest.TestCase):
    """Change Totem Colour with several totems ticked: one colour for every ticked totem, in one go."""

    def village(self):
        pairs = [elder_and_totem(f"Elder{chr(65 + k)}", head=k, body=k, kind=9 + k) for k in range(3)]
        v = Village(self, crowd(3) + [e for e, _t in pairs] + [t for _e, t in pairs])
        ts.move_out(v.folder, 1, processes=NoGame(), now=NOW)
        return v

    def faces(self, v):
        return {t.name: t.face for t in ts.read(v.folder, 1).totems}

    def test_select_all_applies_to_every_totem(self):
        v = self.village()
        keys = [t.key for t in ts.list_totems(v.folder, 1)]
        result = ts.change_colours(v.folder, 1, keys, 4, processes=NoGame(), now=NOW)
        self.assertEqual(len(result.changed), 3)
        self.assertEqual(self.faces(v), {"ElderA": 4, "ElderB": 4, "ElderC": 4})
        log = v.repairs()
        for name, old in (("ElderA", 9 % 8), ("ElderB", 10 % 8), ("ElderC", 11 % 8)):
            self.assertIn(f"{name}'s totem from {vt.face(old)} to {vt.face(4)}", log)
        self.assertEqual(len([b for b in v.backups() if "colour" in b.name]), 1)   # one backup for all

    def test_a_subset_changes_only_the_ticked_ones(self):
        v = self.village()
        found = {t.name: t.key for t in ts.list_totems(v.folder, 1)}
        ts.change_colours(v.folder, 1, [found["ElderA"], found["ElderC"]], 7, processes=NoGame(), now=NOW)
        self.assertEqual(self.faces(v), {"ElderA": 7, "ElderB": 10 % 8, "ElderC": 7})

    def test_none_ticked_changes_nothing_and_says_so(self):
        v = self.village()
        path = ts.store_path(v.folder, 1)
        before = path.read_bytes()
        with self.assertRaisesRegex(ts.StoreError, "No totem was ticked"):
            ts.change_colours(v.folder, 1, [], 2, processes=NoGame(), now=NOW)
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse([b for b in v.backups() if "colour" in b.name])

    def test_a_totem_in_the_file_and_one_in_the_save_together(self):
        e1, t1 = elder_and_totem("Hoto Kenobi", head=14, body=5, kind=10)
        e2, t2 = elder_and_totem("Topaz Kenobi", head=2, body=8, kind=11)
        v = Village(self, crowd(3) + [e1, t1])
        ts.move_out(v.folder, 1, processes=NoGame(), now=NOW)
        data = __import__("test_vv2_totem_repairs").save_for(crowd(3) + [e1, e2, t2])  # one statue still saved
        v.save.write_bytes(data)
        keys = [t.key for t in ts.list_totems(v.folder, 1)]
        self.assertEqual(len(keys), 2)
        result = ts.change_colours(v.folder, 1, keys, 1, processes=NoGame(), now=NOW)
        self.assertEqual(len(result.files), 2)
        self.assertEqual([t.face for t in ts.list_totems(v.folder, 1)], [1, 1])


class MixedRecolourIsOneOperation(unittest.TestCase):
    def test_a_failed_save_write_puts_the_file_back_and_records_nothing(self):
        """Codex #598: a totem in ElderTotems.dat and one in the save; the save write fails."""
        from unittest import mock

        import vv_last_names as ln
        e1, t1 = elder_and_totem("Hoto Kenobi", head=14, body=5, kind=10)
        e2, t2 = elder_and_totem("Topaz Kenobi", head=2, body=8, kind=11)
        v = Village(self, crowd(3) + [e1, t1])
        ts.move_out(v.folder, 1, processes=NoGame(), now=NOW)
        v.save.write_bytes(__import__("test_vv2_totem_repairs").save_for(crowd(3) + [e1, e2, t2]))
        file_before = ts.store_path(v.folder, 1).read_bytes()
        save_before = v.save.read_bytes()
        log_before = v.repairs()
        keys = [t.key for t in ts.list_totems(v.folder, 1)]
        with mock.patch.object(ln, "_write", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(ts.StoreError, "No colour was changed"):
                ts.change_colours(v.folder, 1, keys, 3, processes=NoGame(), now=NOW)
        self.assertEqual(ts.store_path(v.folder, 1).read_bytes(), file_before)
        self.assertEqual(v.save.read_bytes(), save_before)
        self.assertEqual(v.repairs(), log_before)


class EmptyVillageBinding(unittest.TestCase):
    def test_an_empty_roster_binds_by_the_village_name(self):
        entry = bytes(ts.ENTRY)
        e1, t1 = elder_and_totem("Hoto Kenobi", head=14, body=5)
        v = Village(self, [t1])                                    # only a statue in the save
        name = ts.village_of(v.save.read_bytes())
        mine = ts.Store(1, [], [ts.Totem(entry)], name)
        self.assertEqual(ts.parse(ts.serialize(mine)).village, name)
        if name:
            self.assertTrue(ts.bound(mine, v.save.read_bytes()))
        self.assertFalse(ts.bound(ts.Store(1, [], [ts.Totem(entry)], "Another Tribe"), v.save.read_bytes()))
        w = Village(self, crowd(3) + [t1])                          # villagers in the save: not an empty village
        self.assertFalse(ts.bound(ts.Store(1, [], [ts.Totem(entry)], ts.village_of(w.save.read_bytes()) or "x"),
                                  w.save.read_bytes()))


class GiveIntoTheFile(unittest.TestCase):
    def test_a_missing_elders_totem_goes_into_the_file_even_when_the_village_is_full(self):
        e1, t1 = elder_and_totem("Hoto Kenobi", head=14, body=5)
        dead = death(1, "Nina Jumapili", 10, 21)
        v = Village(self, crowd(254) + [e1, t1], deaths=dead)
        ts.move_out(v.folder, 1, processes=NoGame(), now=NOW)
        # Fill the freed record again: 256 records in use.
        v.save.write_bytes(__import__("test_vv2_totem_repairs").save_for(crowd(255) + [e1]))
        s = vt.survey(v.folder, 1)
        self.assertTrue(s.in_store)
        self.assertEqual([e.name for e in s.missing], ["Nina Jumapili"])   # Hoto's totem is in the file
        before = v.save.read_bytes()
        result = vt.give_totems(v.folder, 1, processes=NoGame(), now=NOW, rng=random.Random(4))
        self.assertEqual([g.elder.name for g in result.given], ["Nina Jumapili"])
        self.assertEqual(v.save.read_bytes(), before)
        self.assertEqual([t.name for t in ts.read(v.folder, 1).totems], ["Hoto Kenobi", "Nina Jumapili"])
        self.assertIn("in ElderTotems.dat", v.repairs())


class Settings(unittest.TestCase):
    def test_the_give_automatically_setting_is_per_village(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.assertFalse(ts.auto_give(folder, 2))
            path = ts.set_auto_give(folder, 2, True)
            self.assertEqual(path, ts.store_path(folder, 2).with_name("Elder Totem Settings.dat"))
            self.assertTrue(ts.auto_give(folder, 2))
            self.assertFalse(ts.auto_give(folder, 3))
            ts.set_auto_give(folder, 2, False)
            self.assertFalse(ts.auto_give(folder, 2))


class PendingForTheCompanion(unittest.TestCase):
    def test_passed_away_elders_without_a_totem_are_listed_only_with_the_setting_on(self):
        e1, t1 = elder_and_totem("Hoto Kenobi", head=14, body=5)
        v = Village(self, crowd(4) + [e1, t1], deaths=death(1, "Nina Jumapili", 10, 21)
                    + death(2, "Hoto Kenobi", 14, 5, sex="Male"))
        self.assertEqual(ts.write_pending(v.folder, 1), [])
        self.assertFalse(ts.pending_path(v.folder, 1).exists())
        ts.set_auto_give(v.folder, 1, True)
        listed = ts.write_pending(v.folder, 1)
        self.assertEqual(listed, [("Nina Jumapili", vt.FEMALE, 10, 21, 1400)])   # Hoto's statue stands
        slot, roster, pending, renames = ts.parse_pending(ts.pending_path(v.folder, 1).read_bytes())
        self.assertEqual((slot, pending), (1, listed))
        self.assertEqual(len(roster), 5)
        self.assertEqual(ts.pending_path(v.folder, 1).name, "PendingElderTotems.dat")
        self.assertEqual(ts.pending_path(v.folder, 1).parent, ts.store_path(v.folder, 1).parent)

    def test_the_format_matches_the_companions_reader(self):
        source = (ROOT / "native" / "vvfp_vv2_totems" / "vvfp_vv2_totems.c").read_text(encoding="utf-8")
        self.assertIn('#define PENDING_MAGIC "VVFP VV2 PENDING"', source)
        self.assertIn("#define PENDING_HEADER 44u", source)
        data = ts.serialize_pending(2, [("A", 1, 2, 1)], [("B", 2, 3, 4, 5)], [("Old", "New", 6, 7)])
        self.assertEqual(len(data), ts.PENDING_HEADER + 36 + 40 + 56 + 4)
        self.assertEqual(ts.parse_pending(data), (2, [("A", 1, 2, 1)], [("B", 2, 3, 4, 5)], [("Old", "New", 6, 7)]))


class RemovalWarning(unittest.TestCase):
    def test_warned_only_when_the_patch_is_being_left_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = ts.store_path(folder, 4)
            path.parent.mkdir(parents=True)
            entry = bytes(ts.ENTRY)
            path.write_bytes(ts.serialize(ts.Store(4, [], [ts.Totem(entry), ts.Totem(entry)])))
            text = ts.removal_warning([ts.DLL, "VVFP Startup.dll"], ["vv2_last_names"], folder)
            self.assertIn(ts.LABEL_PUT_BACK, text)
            self.assertIn("Save 4: 2", text)
            self.assertIsNone(ts.removal_warning([ts.DLL], [ts.FEATURE_ID], folder))
            self.assertIsNone(ts.removal_warning(["VVFP Startup.dll"], [], folder))

    def test_the_patcher_asks_before_building_over_a_copy_with_the_patch(self):
        from unittest import mock

        import patcher_files
        import vv_fun_patcher_gui as gui
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "Copy"
            (copy / patcher_files.PATCHER_FILES_FOLDER).mkdir(parents=True)
            (copy / patcher_files.PATCHER_FILES_FOLDER / ts.DLL).write_bytes(b"MZ")
            outputs = [(copy, copy / "Virtual Villagers - The Lost Children.exe")]
            with mock.patch.object(ts, "save_folder_of", return_value=None), \
                    mock.patch.object(gui.messagebox, "askyesno", return_value=False) as asked:
                self.assertFalse(gui.App._confirm_totems_kept(None, outputs, ["vv2_last_names"]))
                self.assertIn(ts.LABEL_PUT_BACK, asked.call_args.args[1])
            with mock.patch.object(ts, "save_folder_of", return_value=None), \
                    mock.patch.object(gui.messagebox, "askyesno", return_value=False) as asked:
                self.assertTrue(gui.App._confirm_totems_kept(None, outputs, [ts.FEATURE_ID]))
                asked.assert_not_called()


if __name__ == "__main__":
    unittest.main()
