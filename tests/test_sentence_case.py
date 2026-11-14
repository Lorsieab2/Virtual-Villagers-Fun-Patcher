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

CASES = [
    ("WHICH LESSON SHOULD (Parent) TEACH?", "Which lesson should (parent) teach?"),
    ("TELL (NAME1) TO STOP BEFORE ANYONE IS HURT.", "Tell (name1) to stop before anyone is hurt."),
    ("HONESTY", "Honesty"),
    ("THINK BEFORE ACTING", "Think before acting"),
    ("KINDNESS AND SHARING", "Kindness and sharing"),
    ("Parenting skill: MODERATE GAIN.", "Parenting skill: moderate gain."),
    ("It was HUGE, said (Name).", "It was HUGE, said (Name)."),       # one word inside ordinary text: as written
    ("OK then", "OK then"),
    ("I THINK I'M READY. YOU ARE NOT!", "I think I'm ready. You are not!"),
    ("Line one.\nAN ALL CAPS LINE.", "Line one.\nAn all caps line."),
    ("\"STOP!\" (HE) SHOUTS.", "\"Stop!\" (He) shouts."),
    ("Already in sentence case.", "Already in sentence case."),
    ("THE {@tribe} GATHERS. {FOODS} ARE SHARED.", "The {@tribe} gathers. {FOODS} are shared."),
]
TITLES = [("THE PARENT'S LESSON", "The Parent's Lesson"), ("The Parent's Lesson", "The Parent's Lesson"),
          ("(NAME)'S BIG DAY", "(Name)'s Big Day"), ("A", "A")]


class TheRule(unittest.TestCase):
    def test_cases(self):
        for text, shown in CASES:
            self.assertEqual(cg.sentence_case(text), shown, text)
            self.assertEqual(cg.sentence_case(shown), shown, "shown text stays as it is")

    def test_titles(self):
        for title, shown in TITLES:
            self.assertEqual(cg.title_case(title), shown)

    def test_a_pool_item_does_not_start_a_sentence(self):
        self.assertEqual(cg.sentence_case("A HUGE FISH", item=True), "a huge fish")

    def test_names_keep_their_capitals_and_the_bytes_stay(self):
        g = cg.load({"format": "vvfp-cie-graph", "version": 6, "title": "THE TEST", "games": [3],
                     "roles": {"pal": {"kind": "villager"}}, "start": "a",
                     "nodes": {"a": {"text": "TELL (PAL) TO STOP BEFORE ANYONE IS HURT."}}})
        lg = cg.lower(g)
        b = {"pal": cg.Binding("Ana", "f")}
        self.assertEqual(cg.expand_v6(g["nodes"]["a"]["text"], lg, b), "Tell Ana to stop before anyone is hurt.")
        self.assertEqual(g["nodes"]["a"]["text"], "TELL (PAL) TO STOP BEFORE ANYONE IS HURT.", "data unchanged")


def collection_texts() -> list[tuple[str, int]]:
    """(text, 1 for a title) of every node, label, pool item and title of the collection."""
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
                    out.append((c["label"], 0))
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
        texts = [(t, 0, 0) for t, _ in CASES] + [(t, 0, 1) for t, _ in TITLES] + [("A HUGE FISH", 1, 0)]
        texts += [(t, 0, k) for t, k in collection_texts()]
        checked = 0
        for text, item, title in texts:
            raw = text.encode("latin-1", "replace")
            if len(raw) >= 8000:
                continue
            r.p.write(TEXT_BUF, raw + b"\0")
            r.p.export("VvfpStoryProbeSentenceCase", TEXT_BUF, item, title)
            native = r.p.cstring(TEXT_BUF, 9000)
            want = cg.title_case(text) if title else cg.sentence_case(text, item=bool(item))
            self.assertEqual(native, want.encode("latin-1", "replace").decode("latin-1"), text[:80])
            checked += 1
        self.assertGreater(checked, 1000)


if __name__ == "__main__":
    unittest.main()
