"""Two audit findings (v1.35.98) that must not come back with a rebuild.

1. A role's pronoun is the engine's placeholder, never literal text.  The owner writes "(healer: his/her)"; the engine
   writes "(healer.his/her)".  Left as written it was escaped ("\\(healer: his/her\\)") and the player saw the
   brackets and the slash in all five games (The Weaver's Pattern, The Midwife's Dream).  No event text, label or
   procedural piece holds a role-colon pronoun or an escaped pronoun placeholder -- in the sources or in the built
   files the games read (assets/event_collection: .cieg, .pak, .pcb).

2. One award of a kind per outcome (the owner, 2026-11-22: keep the NORMAL tech award, drop the SMALL one).  The
   text-implied food / tech pass (scripts/food_tech_additions.py) and the outcome pass (scripts/outcome_effects.py)
   each added a tech gain to 23 outcomes.  No node pays two tech gains, two tech losses, two food gains or two food
   losses.

Static: no game, no executable.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT / "data" / "event_collection"
PIECES = ROOT / "data" / "procedural_pieces"
ASSETS = ROOT / "assets" / "event_collection"

PRONOUNS = r"(?:he/she|his/her|him/her|himself/herself|his/hers|she/he|her/his|her/him|herself/himself)"
# "(healer: his/her)", escaped or not; and an escaped placeholder of any kind: "\(subject.he/she\)", "\(he/she\)".
BAD_TEXT = re.compile(r"\\?\([A-Za-z]+: " + PRONOUNS + r"\\?\)|\\\((?:[A-Za-z]+[.:] ?)?" + PRONOUNS + r"\\\)", re.I)
BAD_BYTES = re.compile(BAD_TEXT.pattern.encode(), re.I)


def strings(node, where=""):
    if isinstance(node, str):
        yield where, node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from strings(v, f"{where}/{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from strings(v, f"{where}[{i}]")


def json_files():
    for path in sorted(COLLECTION.rglob("*.json")):
        yield path
    for path in sorted(PIECES.glob("*.json")):
        yield path


class RolePronouns(unittest.TestCase):
    def test_the_pattern_catches_the_forms_that_shipped(self):
        for bad in ("(elder: his/her)", "\\(Healer: He/She\\)", "\\(healer: him/her\\)", "\\(subject.he/she\\)"):
            self.assertRegex(bad, BAD_TEXT)
        for good in ("(elder.his/her)", "(healer.He/She)", "(he/she)", "(subject)", "\\(leaving (child) outside\\)"):
            self.assertNotRegex(good, BAD_TEXT)

    def test_no_source_text_holds_a_literal_role_pronoun(self):
        bad = []
        for path in json_files():
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            for where, text in strings(doc):
                for m in BAD_TEXT.finditer(text):
                    bad.append(f"{path.relative_to(ROOT)} {where}: {m.group(0)}")
        self.assertEqual(bad, [])

    def test_no_built_event_file_holds_a_literal_role_pronoun(self):
        files = [p for p in ASSETS.rglob("*") if p.suffix in (".cieg", ".pak", ".pcb")]
        if not files:
            self.skipTest("no built event files in this checkout")
        bad = [f"{p.relative_to(ROOT)}: {m.group(0)!r}" for p in sorted(files)
               for m in BAD_BYTES.finditer(p.read_bytes())]
        self.assertEqual(bad, [])


class OneAwardOfAKind(unittest.TestCase):
    def test_no_node_pays_two_awards_of_the_same_kind(self):
        bad = []
        nodes_seen = 0
        for path in sorted(COLLECTION.rglob("*.json")):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if not isinstance(doc, dict) or not isinstance(doc.get("nodes"), dict):
                continue
            for nid, node in doc["nodes"].items():
                nodes_seen += 1
                kinds: dict[tuple, int] = {}
                for e in node.get("effects") or []:
                    if not isinstance(e, dict) or e.get("do") not in ("tech", "food"):
                        continue
                    loss = bool(e.get("loss")) or (isinstance(e.get("min"), int) and e["min"] < 0)
                    key = (e["do"], "loss" if loss else "gain")
                    kinds[key] = kinds.get(key, 0) + 1
                for (what, way), n in kinds.items():
                    if n > 1:
                        bad.append(f"{path.relative_to(ROOT)} {nid}: {n} {what} {way}s")
        self.assertGreater(nodes_seen, 1000)
        self.assertEqual(bad, [])

    def test_the_small_tech_rows_are_gone_from_the_source_table(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("food_tech_additions", ROOT / "scripts" / "food_tech_additions.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        rows = {(eid, node) for eid, node, kind, _size, _why in module.ADDITIONS if kind == ("tech", False)}
        for eid, node in (("vv2_cooking_contest", "v13a_b5"), ("all_conundrums", "a5"), ("all_v24_revolutionary", "e1"),
                          ("all_v24_revolutionary", "a1_food"), ("all_v27_24_explorer", "a")):
            self.assertNotIn((eid, node), rows)


if __name__ == "__main__":
    unittest.main()
