"""The same topics on all five Game Mechanics tabs (src/vv_game_mechanics_parity.py; the owner, 2026-10-27: "Same
between the virtual villagers games"): every topic any tab has is on every tab, as its entry or as one "Not in" line
that says what was checked; a verified "Not in" is pinned against the stock exe's own text."""
from __future__ import annotations

import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import island_event_exe as exe  # noqa: E402
import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_parity as parity  # noqa: E402

NOW = 1_800_000_000
TABS = {game: gm.general(game, now=NOW) for game in range(1, 6)}

# The parity table as it stands: topic -> the five games' state (E entry, N verified Not in, U unconfirmed Not in).
PINNED = {
    "Technology levels 1 to 3": "EEEEE",
    "Puzzles": "EEEEE",
    "Population huts": "EEEEE",
    "Fixing huts": "EEEEE",
    "The fire": "NEEEE",
    "Mushrooms": "EEEEE",
    "Collections": "EEEEE",
    "A snack at the food store": "EEEEE",
    "Fishing": "EEEEE",
    "New clothes": "EEEEE",
    "Herbs": "EEEEU",
    "Stews": "NEUEU",
    "Potions": "NNEUU",
    "Totems": "NEUUE",
    "Statues": "NUEUE",
    "God powers": "NNNNE",
    "Faith and Heathens": "NNNNE",
    "Golden Child": "EUNNU",
    "The Tribal Chief's powers": "NNEUU",
    "Factions": "NNEUU",
    "The Gong of Wonder": "NENNN",
    "Origins upgrades": "EEEEE",
}
LETTER = {"entry": "E", "Not in": "N", "UNCONFIRMED": "U", "missing": "-"}


def _texts(game: int) -> list[str]:
    """Every printable text in the game's stock exe (as tests/../scratch searches read it)."""
    data = exe.path(game).read_bytes()
    return [m.group().decode("latin-1") for m in re.finditer(rb"[ -~]{4,}", data)]


class Parity(unittest.TestCase):
    def test_every_topic_is_on_every_tab(self) -> None:
        got = {name: "".join(LETTER[row[g]] for g in range(1, 6)) for name, row in parity.table(TABS).items()}
        self.assertEqual(got, PINNED)
        for name, row in got.items():
            self.assertNotIn("-", row, name)

    def test_each_game_is_an_entry_or_a_not_in_never_both(self) -> None:
        for topic in parity.TOPICS:
            self.assertEqual(set(topic.entry) | set(topic.not_in), {1, 2, 3, 4, 5}, topic.name)
            self.assertFalse(set(topic.entry) & set(topic.not_in), topic.name)
            for game, facts in TABS.items():
                lines = [f for f in facts if f.text.startswith(f"{topic.name}: Not in ")]
                self.assertEqual(len(lines), 1 if game in topic.not_in else 0, (topic.name, game))

    def test_the_not_in_lines(self) -> None:
        for game, facts in TABS.items():
            village = gm.Village(Path("."), game, 1, Path("x"), gm.blank_save(game, NOW), None, NOW, general=True)
            mine = parity.parity_facts(village)
            for fact in mine:
                self.assertEqual(fact.group, gm.ITEMS)                    # no new group (the window's links)
                self.assertIn(f"Not in {parity.GAME_NAMES[game]}. Checked: ", fact.text)
                self.assertIn(fact.verified, (gm.CODE, False))
                self.assertIn(fact, facts)
                rendered = gm.render([fact], NOW)
                self.assertEqual(gm.UNCONFIRMED in rendered, not fact.confirmed)
            # an unconfirmed Not in says why: text the code was not traced to reach
            for fact in mine:
                if not fact.confirmed:
                    self.assertTrue("not traced" in fact.text or "only in" in fact.text, fact.text)

    def test_no_tab_gains_a_group(self) -> None:
        for facts in TABS.values():
            self.assertTrue({f.group for f in facts} <= set(gm.GROUPS))
        self.assertNotIn("God powers", {f.group for f in TABS[1]})

    def test_the_same_on_a_saves_page(self) -> None:
        # read() and general() both take the item lines from gm.items_facts, which adds the Not in lines.
        for game in range(1, 6):
            village = gm.Village(Path("."), game, 1, Path("x"), gm.blank_save(game, NOW), frozenset(), NOW)
            texts = [f.text for f in gm.items_facts(village)]
            for topic in parity.TOPICS:
                if game in topic.not_in:
                    self.assertIn(parity.not_in_text(topic, game), texts)


@unittest.skipUnless(all(exe.available(g) for g in range(1, 6)), "the stock exes are not here")
class AgainstTheExes(unittest.TestCase):
    def test_a_verified_not_in_names_words_the_exe_does_not_hold(self) -> None:
        for topic in parity.TOPICS:
            for game, (checked, label) in topic.not_in.items():
                match = re.search(r"holds no text with (.+?) in it", checked)
                if label == gm.CODE and match:
                    texts = _texts(game)
                    words = re.findall(r'"([^"]+)"', match.group(1))
                    self.assertTrue(words, (topic.name, game))
                    for word in words:
                        hits = [t for t in texts if word.lower() in t.lower()]
                        self.assertEqual(hits, [], (topic.name, game, word))
                elif label == gm.CODE:
                    self.fail(f"{topic.name}, game {game}: a verified Not in must name the words searched")

    def test_an_unconfirmed_not_in_quotes_text_the_exe_does_hold(self) -> None:
        for topic in parity.TOPICS:
            for game, (checked, label) in topic.not_in.items():
                match = re.search(r"still holds (.+?), text the game's code", checked)
                if not match:
                    continue
                self.assertIs(label, False, (topic.name, game))
                texts = _texts(game)
                for word in re.findall(r'"([^"]+)"', match.group(1)):
                    self.assertTrue(any(word in t for t in texts), (topic.name, game, word))

    def test_new_believers_snack_on_its_path(self) -> None:
        """The New Believers snack entry: the Eating action queues work event 0x57, the dispatcher's table sends it
        to 0x46CEF6, which tests health < 100, food > 0 and rand(100) < 50, then takes 1 food."""
        game = exe.exe(5)
        self.assertEqual(game.bytes_at(0x4641AF, 7), b"\x68" + struct.pack("<I", 0x457D30) + b"\x6a\x33")
        self.assertEqual(game.bytes_at(0x457DBB, 2), b"\x6a\x57")
        self.assertEqual(game.instruction(0x46CE67), "add eax, -0xb")
        self.assertEqual(game.u32(0x46DEB0 + 4 * (0x57 - 0xB))[0], 0x46CEF6)
        self.assertEqual(game.instruction(0x46CEFC), "cmp dword ptr [edx + 0x1c40], 0x64")
        self.assertEqual(game.instruction(0x46CF16), "push 0x64")
        self.assertEqual(game.instruction(0x46CF20), "cmp eax, 0x32")
        self.assertEqual(game.instruction(0x46CF48), "push -1")
        self.assertEqual(exe.text(5, 0x4C4), "Eating")


if __name__ == "__main__":
    unittest.main()
