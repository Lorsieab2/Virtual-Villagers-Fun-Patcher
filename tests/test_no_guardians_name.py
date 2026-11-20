"""The owner (2026-11-19): "don't use 'Guardians' to refer to our villagers. You can use it in other contexts like
'stone guardian, guardian of a child, guardians of the village' etc".

Pinned here (docs/event-collection/guardians-wording.md, "No Guardians as the villagers' name"):
  * no event text the games show (the collection's titles, title variants, pages, page variants, labels, pool items,
    game words and Pick Island Event descriptions, every Guardians of Isola Rewrite form among them; the Living Event
    Engine's bank; the procedural pieces; the branching graphs of data/cie_graphs) uses a capitalised "Guardian(s)",
    the people's name, other than the ordinary uses listed in ORDINARY;
  * no text names "the Guardians of Harmony" / "the Guardians of Isola" (the patches' names are never event text);
  * no Guardians of Isola Rewrite pair (guardians-wording.md) writes "guardian" into a text.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import collection_lib as lib  # noqa: E402

COLLECTION = ROOT / "data" / "event_collection"
NAME = re.compile(r"\bGuardians?\b")                             # capitalised: a name
PATCH_NAMES = re.compile(r"guardians of (harmony|isola)", re.I)   # the patches' names
# Capitalised only because they are titles or title-case labels; each is an ordinary guardian, not our villagers.
ORDINARY = (
    "The Guardian Dance at Dawn",        # lcc41: the warriors' dance
    "The River's Guardians",             # lch27: villagers chosen to watch the river
    "Form the Guardians",                # lch27: the same river guardians (a title-case label)
    "The River's Little Guardians",      # lcj19: children who watch the river
    "The Ugliest Guardian",              # vv4_v17_sculpture: a carved figure
    "The Fierce Little Guardian",        # all_v27_31_guardian: a child guarding
)


def _named(text: str) -> list[str]:
    """Each capitalised Guardian(s) in `text` that no ORDINARY phrase covers, and each patch name."""
    spans = [(m.start(), m.end()) for o in ORDINARY for m in re.finditer(re.escape(o), text)]
    bad = [m.group(0) for m in NAME.finditer(text)
           if not any(a <= m.start() and m.end() <= b for a, b in spans)]
    return bad + [m.group(0) for m in PATCH_NAMES.finditer(text)]


def collection_texts(doc: dict):
    """(where, text) for every text an event of the collection can show."""
    yield "title", doc.get("title", "")
    for i, tv in enumerate(doc.get("title_variants") or []):
        yield f"title variant {i + 1}", tv.get("title", "")
    for nid, n in (doc.get("nodes") or {}).items():
        yield f"node {nid} name", n.get("name", "")
        yield f"node {nid}", n.get("text", "")
        for i, v in enumerate(n.get("variants") or []):
            yield f"node {nid} variant {i + 1}", v.get("text", "")
        for i, c in enumerate(n.get("choices") or []):
            yield f"node {nid} choice {i + 1}", c.get("label", "")
    for pname, p in (doc.get("pools") or {}).items():
        for i, it in enumerate(p.get("items") or []):
            yield f"pool {pname} item {i + 1}", it.get("text", "") if isinstance(it, dict) else it
    for word, per in (doc.get("words") or {}).items():
        for g, t in per.items():
            yield f"word {word} ({g})", t
    col = doc.get("collection") or {}
    yield "description", col.get("description") or ""
    for i, v in enumerate(col.get("description_variants") or []):
        yield f"description variant {i + 1}", v.get("description", "") if isinstance(v, dict) else v


def all_strings(o, skip: tuple = ()):
    if isinstance(o, dict):
        for k, v in o.items():
            if k not in skip:
                yield from all_strings(v, skip)
    elif isinstance(o, list):
        for v in o:
            yield from all_strings(v, skip)
    elif isinstance(o, str):
        yield o


class NoGuardiansName(unittest.TestCase):
    def test_collection_texts(self):
        bad = []
        files = [p for p in COLLECTION.rglob("*.json") if p.name not in ("manifest.json", "shared_pools.json")
                 and "content_tags" not in p.parts]
        self.assertGreater(len(files), 4000)
        for p in files:
            doc = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(doc, dict) or "nodes" not in doc:
                continue
            for where, text in collection_texts(doc):
                for w in _named(text or ""):
                    bad.append(f"{p.relative_to(ROOT)} {where}: {w!r} in {text[:120]!r}")
        self.assertEqual(bad, [])

    def test_living_bank_pieces_and_graphs(self):
        bad = []
        sources = [(ROOT / "data" / "living_events" / "bank.json", ("credit", "contract", "credit_question", "source")),
                   (ROOT / "data" / "procedural_pieces" / "go_seeds.json", ())]
        sources += [(p, ("credit",)) for p in sorted((ROOT / "data" / "cie_graphs").glob("*.json"))]
        for path, skip in sources:
            for text in all_strings(json.loads(path.read_text(encoding="utf-8")), skip):
                # a patch id ("guardians_of_isola") is a condition, not text
                for w in _named(text.replace("guardians_of_isola", "")):
                    bad.append(f"{path.relative_to(ROOT)}: {w!r} in {text[:120]!r}")
        self.assertEqual(bad, [])

    def test_no_pair_writes_guardian(self):
        bad = [(eid, before, after) for eid, rows in lib.guardians_pairs().items() for _w, before, after in rows
               if re.search(r"guardian", after, re.I)]
        self.assertEqual(bad, [])

    def test_the_check_catches_a_villager_name(self):
        self.assertEqual(_named("The Guardians gather at the shrine."), ["Guardians"])
        self.assertEqual(_named("A Guardian prays."), ["Guardian"])
        self.assertEqual(_named("Our villagers are the Guardians of Harmony."),
                         ["Guardians", "Guardians of Harmony"])
        self.assertEqual(_named("The child's guardian and a stone guardian."), [])
        self.assertEqual(_named("The River's Guardians"), [])


if __name__ == "__main__":
    unittest.main()
