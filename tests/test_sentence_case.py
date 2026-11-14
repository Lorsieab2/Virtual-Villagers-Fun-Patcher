"""The sentence-case rule (the owner, 2026-11-14: "the entire event text is shown in sentence case"; docs/event-
collection/cie-v6-binary.md 19): one rule in the patcher (src/vv_cie_graph.py sentence_case / title_case: the fit,
the walk, the simulation) and in Story / Cheat Upgrades (story_graph.inc cg_sentence_case / cg_title_case: what the
game shows), the same byte for byte -- checked here on the rule's own cases and on every text, label and title of
the Isola Grand Event Collection, run through the companion's test build in the emulator.  The data is never
changed: only what is shown.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_cie_graph as cg  # noqa: E402
from test_story_custom_island_event import HAVE_EMULATOR, TEXT_BUF, emulated, have_stock  # noqa: E402

# Story text (the owner's rule, 2026-11-14, every part).
CASES = [
    # Other narration in capitals (no lower-case letter, no "!", not quoted): sentence case.
    ("WHICH LESSON SHOULD (Parent) TEACH?", "Which lesson should (parent) teach?"),
    ("TELL (NAME1) TO STOP BEFORE ANYONE IS HURT.", "Tell (name1) to stop before anyone is hurt."),
    ("HONESTY", "Honesty"),
    ("Line one.\nAN ALL CAPS LINE.", "Line one.\nAn all caps line."),
    ("ROUND ONE - THE TEST OF SKILL\nThe competitors cook.", "Round one - the test of skill\nThe competitors cook."),
    ("THE {@tribe} GATHERS. {FOODS} ARE SHARED.", "The {@tribe} gathers. {FOODS} are shared."),
    ("I THINK I'M READY.", "I think I'm ready."),
    ("WE SAIL FOR ISOLA'S REEF.", "We sail for Isola's reef."),           # the island's name keeps its capital
    # Emphasis: a word or a phrase in capitals inside a sentence with a lower-case letter stays.
    ("It was HUGE, said (Name).", "It was HUGE, said (Name)."),
    ("It was the BEST.", "It was the BEST."),
    ("OK then", "OK then"),
    ("I said DO NOT TOUCH the pot.", "I said DO NOT TOUCH the pot."),
    ("Parenting skill: MODERATE GAIN.", "Parenting skill: MODERATE GAIN."),    # not a heading: "skill" is lower case
    ("The village speaks of THE GREAT STENCH for generations.",
     "The village speaks of THE GREAT STENCH for generations."),
    # Speech: capitals in quotation marks stay, a whole sentence too -- straight, single and curly (cp1252) quotes.
    ("The rival shouts, \"I HATE YOUR GUTS!\"", "The rival shouts, \"I HATE YOUR GUTS!\""),
    ("\"I HATE YOUR GUTS.\"", "\"I HATE YOUR GUTS.\""),
    ("'THE FEELING IS MUTUAL.' (HE) SAYS.", "'THE FEELING IS MUTUAL.' (He) says."),
    ("\x93I HATE YOUR GUTS.\x94 (HE) SAYS.", "\x93I HATE YOUR GUTS.\x94 (He) says."),
    ("\"STOP!\" (HE) SHOUTS.", "\"STOP!\" (He) shouts."),
    # Shouting: a sentence in capitals ending in "!" or "!?" stays.
    ("I THINK I'M READY. YOU ARE NOT!", "I think I'm ready. YOU ARE NOT!"),
    ("CLOSE IT! CLOSE THE WRETCHED THING!", "CLOSE IT! CLOSE THE WRETCHED THING!"),
    ("WHAT IS THAT!? RUN.", "WHAT IS THAT!? Run."),
    # Headings: capitals from a text's or a paragraph's start up to a ":".
    ("THE TINY TYRANT: The child decrees that everyone must play.",
     "The tiny tyrant: The child decrees that everyone must play."),
    ("A quiet day.\nTHE ROYAL FEAST: The child demands a feast.", "A quiet day.\nThe royal feast: The child demands a feast."),
    ("THE PEOPLE'S CHIEF: Two adults share.", "The people's chief: Two adults share."),
    ("MASTER STONEWRIGHT (CRITIC):\nAn elderly craftsperson.", "Master stonewright (critic):\nAn elderly craftsperson."),
    ("WARNING: DO NOT TOUCH.", "Warning: Do not touch."),
    ("Already in sentence case.", "Already in sentence case."),
]
# Button labels: a label with no lower-case letter is shown in sentence case as a whole, "!" too; quoted text stays.
LABELS = [
    ("TELL (NAME1) TO STOP BEFORE ANYONE IS HURT.", "Tell (name1) to stop before anyone is hurt."),
    ("HONESTY", "Honesty"),
    ("THINK BEFORE ACTING", "Think before acting"),
    ("KINDNESS AND SHARING", "Kindness and sharing"),
    ("RUN! HIDE!", "Run! Hide!"),
    ("A LANDSCAPE OF ISOLA", "A landscape of Isola"),
    ("\"I HATE YOUR GUTS!\"", "\"I HATE YOUR GUTS!\""),
    ("SAY \"NO\" FIRMLY", "Say \"NO\" firmly"),
    ("Ask THE ELDER first", "Ask THE ELDER first"),
]
TITLES = [("THE PARENT'S LESSON", "The Parent's Lesson"), ("The Parent's Lesson", "The Parent's Lesson"),
          ("(NAME)'S BIG DAY", "(Name)'s Big Day"), ("A", "A")]


class TheRule(unittest.TestCase):
    def test_cases(self):
        for text, shown in CASES:
            self.assertEqual(cg.sentence_case(text), shown, text)
            self.assertEqual(cg.sentence_case(shown), shown, "shown text stays as it is")

    def test_labels(self):
        for text, shown in LABELS:
            self.assertEqual(cg.sentence_case(text, label=True), shown, text)
            self.assertEqual(cg.sentence_case(shown, label=True), shown, "shown text stays as it is")
        self.assertEqual(cg.sentence_case("RUN! HIDE!"), "RUN! HIDE!", "the same words in the story: shouting")

    def test_titles(self):
        for title, shown in TITLES:
            self.assertEqual(cg.title_case(title), shown)

    def test_a_pool_item_does_not_start_a_sentence(self):
        self.assertEqual(cg.sentence_case("A HUGE FISH", item=True), "a huge fish")
        self.assertEqual(cg.sentence_case("THE INSULT: A judge calls.", item=True), "The insult: A judge calls.",
                         "a heading starts one, in an item too")

    def test_names_keep_their_capitals_and_the_bytes_stay(self):
        g = cg.load({"format": "vvfp-cie-graph", "version": 6, "title": "THE TEST", "games": [3],
                     "roles": {"pal": {"kind": "villager"}}, "start": "a",
                     "nodes": {"a": {"text": "TELL (PAL) TO STOP BEFORE ANYONE IS HURT."}}})
        lg = cg.lower(g)
        b = {"pal": cg.Binding("Ana", "f")}
        self.assertEqual(cg.expand_v6(g["nodes"]["a"]["text"], lg, b), "Tell Ana to stop before anyone is hurt.")
        self.assertEqual(g["nodes"]["a"]["text"], "TELL (PAL) TO STOP BEFORE ANYONE IS HURT.", "data unchanged")
        # A label is cased as one (cie-v6-binary.md 19): "RUN!" on a button is "Run!", in the story it is shouted.
        self.assertEqual(cg.label_shown("RUN, (PAL)!", lg, b, 3), "Run, Ana!")
        self.assertEqual(cg.expand_v6("RUN, (PAL)!", lg, b), "RUN, ANA!")


def collection_texts() -> list[tuple[str, int]]:
    """(text, 1 for a title, 2 for a label) of every node, label and title of the collection."""
    out: list[tuple[str, int]] = []
    for path in sorted((ROOT / "data" / "event_collection").rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("format") != cg.FORMAT:
            continue
        out.append((data.get("title", ""), 1))
        for node in data.get("nodes", {}).values():
            for key in ("text",):
                if isinstance(node.get(key), str):
                    out.append((node[key], 0))
            if isinstance(node.get("title"), str):
                out.append((node["title"], 1))
            for c in node.get("choices", []):
                if isinstance(c.get("label"), str):
                    out.append((c["label"], 2))
            for v in node.get("variants", []) or []:
                if isinstance(v, dict) and isinstance(v.get("text"), str):
                    out.append((v["text"], 0))
    return [(t, k) for t, k in out if t]


@emulated
class NativeIsTheSame(unittest.TestCase):
    def test_every_collection_text_and_the_cases(self):
        from test_story_cie_graph_runtime import Run
        game = next((g for g in ("vv3", "vv1", "vv2", "vv4", "vv5") if have_stock(g)), None)
        if game is None:
            self.skipTest("no stock executable")
        r = Run(game)
        texts = [(t, 0, 0) for t, _ in CASES] + [(t, 0, 1) for t, _ in TITLES] + [(t, 0, 2) for t, _ in LABELS]
        texts += [("A HUGE FISH", 1, 0), ("THE INSULT: A judge calls.", 1, 0), ("RUN! HIDE!", 1, 2)]
        texts += [(t, 0, k) for t, k in collection_texts()]
        checked = 0
        for text, item, kind in texts:
            raw = text.encode("latin-1", "replace")
            if len(raw) >= 8000:
                continue
            r.p.write(TEXT_BUF, raw + b"\0")
            r.p.export("VvfpStoryProbeSentenceCase", TEXT_BUF, item, kind)
            native = r.p.cstring(TEXT_BUF, 9000)
            want = cg.title_case(text) if kind == 1 else cg.sentence_case(text, item=bool(item), label=kind == 2)
            self.assertEqual(native, want.encode("latin-1", "replace").decode("latin-1"), text[:80])
            checked += 1
        self.assertGreater(checked, 1000)


if __name__ == "__main__":
    unittest.main()
