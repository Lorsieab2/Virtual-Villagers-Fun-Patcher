"""Repair Saves & Logs: "Restore Heathen Masks..." (New Believers; src/vv5_heathen_masks_restore.py).

The owner (2026-11-22): "I would like an option in repair logs to restore the proper masks to heathens that
reconverted into heathens."  Each test builds a save folder by hand (in a temporary folder): the villager table
where the game keeps it (faction, kind bytes and role as the game's save writer 0x4652F0 packs them), the Former
Heathens file, the Village Masks file and the logs.  Only the Village Masks file -- a patcher file -- is ever
written; the save never is.
"""
from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_last_names as ln  # noqa: E402
import vv_log_tools as tools  # noqa: E402
from test_lost_titles import NoGame, Running, former_file, person, save_for  # noqa: E402

import vv5_heathen_masks_restore as hm  # noqa: E402

LOGS = "Virtual Villagers Fun Patcher Logs"
DATA = "Virtual Villagers Fun Patcher Data"
NOW = datetime(2026, 11, 22, 12, 0, 0)
VILLAGE = "Village: Tribe (Save 1)"

# (person, faction, orange, red, role)
KAI = (person("Kai", 4, 4, male=True), 0, 0, 0, 0)            # a believer
NOBU = (person("Nobu", 5, 5, male=True), 1, 0, 0, 6)          # went back; a former Master (the file); a camp job
TAMA = (person("Tama", 6, 6), 1, 0, 0, 0)                     # went back; red (her Former Heathen title in the logs)
POI = (person("Poi", 7, 7), 1, 1, 0, 0)                       # an orange Heathen the game draws orange
RINO = (person("Rino", 8, 8, male=True), 1, 0, 0, 15)         # a Master now (a puzzle Heathen)
LULU = (person("Lulu", 9, 9), 1, 0, 0, 0)                     # went back; the logs never say which mask
MOMO = (person("Momo", 10, 10), 1, 0, 0, 0)                   # went back; orange (the file); the masks file lacks her
UDU = (person("Udu", 11, 11, male=True), 1, 0, 0, 0)          # an ordinary blue Heathen, never a believer
PEOPLE = [KAI, NOBU, TAMA, POI, RINO, LULU, MOMO, UDU]


def save_with_factions(people) -> bytes:
    data = bytearray(save_for(5, [p for p, *_ in people]))
    for at, (_p, faction, orange, red, role) in zip(ln._entries(5, bytes(data)), people):
        data[at + hm.FACTION], data[at + hm.ORANGE], data[at + hm.RED] = faction, orange, red
        struct.pack_into("<i", data, at + hm.ROLE, role)
    return bytes(data)


def villager_page(n: int, name: str, head: int, body: int, extra: str = "") -> str:
    return (f"Villager {n}\n  Name: {name}\n{extra}  Age: 400\n  Sex: Female\n  Head: {head}\n  Body: {body}\n"
            f"  Likes: (none)\n  Dislikes: (none)\n\n")


class RestoreHeathenMasks(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        named = mock.patch("vv_log_additions.current_villages", return_value={VILLAGE})
        named.start()
        self.addCleanup(named.stop)
        self.folder = Path(tmp.name)
        self.save = ln.save_path(self.folder, 5, 1)
        self.save.write_bytes(save_with_factions(PEOPLE))
        data = self.save.read_bytes()
        at = ln._entries(5, data)
        f = ln.FIELDS[5]
        checker = tools.load_checker()
        self.ids = [checker._villager(data, p, checker.LAYOUTS[5], i, 5).ident for i, p in enumerate(at)]
        titles = [ln._title_identity(data, p, f) for p in at]
        former = tools.layout.route(self.folder, f"{DATA}\\Former Heathens\\Former Heathens - Save 1.dat")
        former.parent.mkdir(parents=True, exist_ok=True)
        former.write_bytes(former_file([(titles[1], 3), (titles[6], 1), (titles[0], 2)]))
        roster = list(self.ids) + [0] * (150 - len(self.ids))
        roster[6] = 0                                   # the masks file does not name Momo yet
        nibbles = bytearray(75)
        nibbles[0] = 0x02                               # Kai (a believer) wears an orange Change Appearance mask
        self.masks = hm.masks_path(self.folder, 1)
        self.masks.parent.mkdir(parents=True, exist_ok=True)
        self.masks.write_bytes(b"VM06" + struct.pack("<150I", *roster) + bytes(nibbles))
        self.log("Tribe Population/Village Population 1.txt",
                 VILLAGE + "\n" + villager_page(3, "Tama", 6, 6, "  Special villager: Former Heathen (red mask)\n"))
        self.log("Births and Conceptions/Virtual Villagers 5 Births and Conceptions Log 1.txt",
                 f"{VILLAGE}\nArrived 1\n  Name: Lulu\n  Head: 9\n  Body: 9\n  How: Converted from the Heathens\n\n")
        self.log("Deaths/Virtual Villagers 5 Deaths Log 1.txt",
                 f"{VILLAGE}\nDisappeared 1\n  Name: Lulu\n  Head: 9\n  Body: 9\n"
                 "  What happened: Left the tribe: became a Heathen\n\n")

    def log(self, relative: str, text: str) -> None:
        path = self.folder / LOGS / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.replace("\n", "\r\n").encode("latin-1"))

    def nibble(self, index: int) -> int:
        byte = self.masks.read_bytes()[4 + 150 * 4 + (index >> 1)]
        return (byte >> 4 if index & 1 else byte) & 0x0F

    def test_the_survey_lists_who_and_which_mask(self):
        work = hm.survey(self.folder, 1)
        self.assertEqual([(f.name, f.mask, f.source) for f in work.restore],
                         [("Nobu", 4, "the Former Heathens file"),
                          ("Tama", 3, "their Former Heathen title in the logs")])
        self.assertEqual([(f.name, f.mask) for f in work.listed], [("Lulu", None), ("Momo", 2)])
        lines = work.lines()
        self.assertIn("Nobu (head 5, body 5): Purple Mask (from the Former Heathens file)", lines)
        self.assertIn("Lulu (head 9, body 9): mask unknown -- skipped (the logs show they joined the tribe and went "
                      "back, but not which mask they wore)", lines)
        self.assertTrue(any(line.startswith("Momo (head 10, body 10): Orange Mask") and "not restored" in line
                            for line in lines))
        self.assertFalse(any(n in " ".join(lines) for n in ("Kai", "Poi", "Rino", "Udu")),
                         "a believer, a Heathen the game draws, a puzzle Heathen, a Heathen never a believer")

    def test_restore_writes_only_the_masks_file_and_logs_it(self):
        save = self.save.read_bytes()
        before = self.masks.read_bytes()
        result = hm.restore(self.folder, 1, processes=NoGame(), now=NOW)
        self.assertEqual([f.name for f in result.restored], ["Nobu", "Tama"])
        self.assertEqual(self.save.read_bytes(), save, "the save is never written")
        self.assertEqual([self.nibble(i) for i in range(8)], [2, 4, 3, 0, 0, 0, 0, 0])
        after = self.masks.read_bytes()
        changed = [i for i in range(len(before)) if before[i] != after[i]]
        self.assertEqual(changed, [4 + 600, 4 + 601], "only the two villagers' nibbles (records 1 and 2)")
        copies = list((self.folder).rglob("*.bak*"))
        self.assertTrue(copies, "the file was copied into Copies Made Before Repairs")
        self.assertEqual(copies[0].read_bytes(), before)
        self.assertTrue(any(p.is_dir() for p in (self.folder / "Backups").iterdir()), "the save folder backed up")
        repairs = sorted(self.folder.rglob("Virtual Villagers 5 Repairs Log *.txt"))
        text = repairs[0].read_bytes().decode("latin-1")
        self.assertIn("  Restored: Nobu (head 5, body 5): Purple Mask (from the Former Heathens file)\r\n", text)
        self.assertIn("  Restored: Tama (head 6, body 6): Red Mask (from their Former Heathen title in the logs)", text)
        self.assertEqual(hm.survey(self.folder, 1).restore, [], "a second survey finds nothing more")

    def test_refused_while_the_game_runs(self):
        before = self.masks.read_bytes()
        with self.assertRaises(tools.LogToolError):
            hm.restore(self.folder, 1, processes=Running(), now=NOW)
        self.assertEqual(self.masks.read_bytes(), before)

    def test_titles_that_disagree_are_never_guessed(self):
        self.log("Tribe History/Village History 1.txt",
                 "=== Virtual Villagers 5 -- 2026-11-01 10:00 ===\n" + VILLAGE + "\n"
                 + villager_page(3, "Tama", 6, 6, "  Special villager: Former Heathen (orange mask)\n"))
        work = hm.survey(self.folder, 1)
        self.assertEqual([f.name for f in work.restore], ["Nobu"])
        self.assertIn(("Tama", None), [(f.name, f.mask) for f in work.listed])

    def still_coloured(self) -> tuple[list[int], bytes]:
        """Poi is a former orange Heathen (the Former Heathens file) and Udu went back wearing red (the logs: he
        joined and left; The Spa left his red kind byte): both still behave orange / red in the save."""
        data = bytearray(self.save.read_bytes())
        at = ln._entries(5, bytes(data))
        data[at[7] + hm.RED] = 1
        self.save.write_bytes(bytes(data))
        f = ln.FIELDS[5]
        titles = [ln._title_identity(bytes(data), p, f) for p in at]
        former = tools.layout.route(self.folder, f"{DATA}\\Former Heathens\\Former Heathens - Save 1.dat")
        former.write_bytes(former_file([(titles[1], 3), (titles[6], 1), (titles[0], 2), (titles[3], 1)]))
        self.log("Births and Conceptions/Virtual Villagers 5 Births and Conceptions Log 2.txt",
                 f"{VILLAGE}\nArrived 2\n  Name: Udu\n  Head: 11\n  Body: 11\n  How: Converted from the Heathens\n\n")
        self.log("Deaths/Virtual Villagers 5 Deaths Log 2.txt",
                 f"{VILLAGE}\nDisappeared 2\n  Name: Udu\n  Head: 11\n  Body: 11\n"
                 "  What happened: Left the tribe: became a Heathen\n\n")
        return at, bytes(data)

    def test_one_still_orange_or_red_in_the_save_behaves_as_blue_after(self):
        at, save = self.still_coloured()
        work = hm.survey(self.folder, 1)
        self.assertEqual([(f.name, f.mask, f.kind_byte) for f in work.restore],
                         [("Nobu", 4, 0), ("Tama", 3, 0), ("Poi", 2, 2), ("Udu", 3, 3)])
        self.assertTrue(any(line.startswith("Poi (head 7, body 7): Orange Mask (from the Former Heathens file); the "
                                            "save's orange Heathen behaviour cleared") for line in work.lines()))
        result = hm.restore(self.folder, 1, processes=NoGame(), now=NOW)
        self.assertEqual(len(result.copies), 2, "the masks file and the save, each copied first")
        after = self.save.read_bytes()
        changed = [i for i in range(len(save)) if save[i] != after[i]]
        self.assertEqual(changed, [at[3] + hm.ORANGE, at[7] + hm.RED], "only the two kind bytes")
        self.assertEqual([self.nibble(i) for i in (3, 7)], [2, 3], "drawn in their own colour")
        text = sorted(self.folder.rglob("Virtual Villagers 5 Repairs Log *.txt"))[0].read_bytes().decode("latin-1")
        self.assertIn("Udu (head 11, body 11): Red Mask (from the logs (joined the tribe and went back) and the mask "
                      "they wear); the save's red Heathen behaviour cleared", text)
        self.assertIn("Virtual Villagers - New Believers1.ldw -- copy kept:", text)

    def test_a_former_blue_heathen_with_a_believers_mask_goes_back_to_blue(self):
        """Codex (#843): Udu was a blue Heathen (the Former Heathens file), took a Change Appearance mask as a
        believer and went back under an older build: the file still holds that mask (the companion would draw it).
        He wore blue as a Heathen, so his entry is set to blue; nothing else changes."""
        data = self.save.read_bytes()
        at = ln._entries(5, data)
        f = ln.FIELDS[5]
        titles = [ln._title_identity(data, p, f) for p in at]
        former = tools.layout.route(self.folder, f"{DATA}\\Former Heathens\\Former Heathens - Save 1.dat")
        former.write_bytes(former_file([(titles[1], 3), (titles[6], 1), (titles[0], 2), (titles[7], 0)]))
        raw = bytearray(self.masks.read_bytes())
        raw[4 + 600 + 3] = (raw[4 + 600 + 3] & 0x0F) | (4 << 4)    # record 7: the Purple Mask he chose
        self.masks.write_bytes(bytes(raw))
        work = hm.survey(self.folder, 1)
        udu = [x for x in work.restore if x.name == "Udu"]
        self.assertEqual([(x.mask, x.nibble, x.kind_byte) for x in udu], [(1, True, 0)])
        self.assertIn("Udu (head 11, body 11): Blue Mask (from the Former Heathens file)", work.lines())
        hm.restore(self.folder, 1, processes=NoGame(), now=NOW)
        self.assertEqual(self.nibble(7), 1)
        self.assertEqual(self.save.read_bytes(), data, "the save is not written for it")

    def test_a_former_blue_heathen_already_blue_needs_nothing(self):
        data = self.save.read_bytes()
        at = ln._entries(5, data)
        titles = [ln._title_identity(data, p, ln.FIELDS[5]) for p in at]
        former = tools.layout.route(self.folder, f"{DATA}\\Former Heathens\\Former Heathens - Save 1.dat")
        former.write_bytes(former_file([(titles[7], 0)]))
        self.assertNotIn("Udu", [x.name for x in hm.survey(self.folder, 1).restore])

    def test_a_heathen_the_game_made_keeps_its_colour(self):
        """Poi carries the orange byte and nothing shows she was ever a believer: never touched."""
        save = self.save.read_bytes()
        work = hm.survey(self.folder, 1)
        self.assertNotIn("Poi", [f.name for f in work.restore + work.listed])
        hm.restore(self.folder, 1, processes=NoGame(), now=NOW)
        self.assertEqual(self.save.read_bytes(), save)

    def test_a_failed_save_write_puts_every_file_back(self):
        _at, save = self.still_coloured()
        masks = self.masks.read_bytes()
        real = ln._write

        def failing(path, data):
            if path.suffix == ".ldw":
                raise OSError("disk full")
            real(path, data)
        with mock.patch.object(ln, "_write", side_effect=failing):
            with self.assertRaises(hm.HeathenMasksError) as raised:
                hm.restore(self.folder, 1, processes=NoGame(), now=NOW)
        self.assertIn("every file was put back", str(raised.exception))
        self.assertEqual((self.save.read_bytes(), self.masks.read_bytes()), (save, masks))

    def test_no_masks_file_writes_nothing(self):
        self.masks.unlink()
        work = hm.survey(self.folder, 1)
        self.assertEqual(work.restore, [])
        self.assertIn("no Village Masks file", " ".join(work.lines()))
        with self.assertRaises(hm.HeathenMasksError):
            hm.restore(self.folder, 1, processes=NoGame(), now=NOW)


if __name__ == "__main__":
    unittest.main()
