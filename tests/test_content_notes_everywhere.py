"""Content Notes for Island Events reach every copy of an event (R6 live check, 2026-11-21).

The note ("Content note: <labels>", src/vv_event_content.py) was on the static collection events and the Living
Event Engine's own variants, but NOT on (a) More Island Events' own events (its DLL builds their text itself) nor
(b) the mixer versions of the static events (scripts/living_from_static.py compiled each version without the content
controls), so Pick Island Event listed those titles twice and neither copy had the note.

Shown here, on the SHIPPED files:
  * every shipped static event (assets/event_collection/<id>.cieg) whose tag table names a content note carries it;
  * every mixer version of a static event in every game's living-st_*.pak carries the note when its static event
    does, with its labels (a version shows the static event's words, so it may contain the same content); a version
    without it is rebuilt and shown to have left out every outcome with noted content;
  * More Island Events: each of its events whose tag table (content_tags/mie.json) names labels has exactly that
    note line in the companion's source (MIE_NOTE_*), shown first in its question's popup (adv_popup_noted), and the
    line is in the shipped DLL; an event without labels has none.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import vv_event_content as content  # noqa: E402
import vv_living_mixer as living  # noqa: E402

ASSETS = ROOT / "assets" / "event_collection"
TAGS = ROOT / "data" / "event_collection" / "content_tags"
MIE_DIR = ROOT / "native" / "vvfp_more_island_events"
MIE_DLL = ROOT / "assets" / "more_island_events" / "VVFP More Island Events.dll"
NOTE = content.NOTE_PREFIX.encode("ascii")
NOTE_LINE = re.compile(rb"Content note: [A-Za-z ,]+")

# More Island Events: each event's note define and the file that composes its question.
MIE_NOTES = {"mie_adventurer": ("MIE_NOTE_ADVENTURER", "adv_core.inc"),
             "mie_cave_explorers": ("MIE_NOTE_CAVE", "cave_core.inc"),
             "mie_climb": ("MIE_NOTE_CLIMB", "climb_core.inc"),
             "mie_diving": ("MIE_NOTE_DIVING", "dive_core.inc"),
             "mie_dolphins": ("MIE_NOTE_DOLPHINS", "dolphin_core.inc"),
             "mie_mysterious_mask": ("MIE_NOTE_MASK", "mask_core.inc"),
             "mie_troubling_signs": ("MIE_NOTE_TROUBLING", "troubling_core.inc")}


def tables() -> dict[str, dict]:
    """{event id: its tag table entry} of every source."""
    out: dict[str, dict] = {}
    for path in sorted(TAGS.glob("*.json")):
        out.update(json.loads(path.read_text(encoding="utf-8")).get("events", {}))
    return out


def notes_in(blob: bytes) -> set[bytes]:
    """The labels every content note line of a compiled event names."""
    found: set[bytes] = set()
    for m in NOTE_LINE.finditer(blob):
        found.update(x.strip() for x in m.group()[len(NOTE):].split(b","))
    return found


class TheStaticEvents(unittest.TestCase):
    def test_every_tagged_static_event_carries_its_note(self) -> None:
        missing = []
        checked = 0
        for ident, entry in tables().items():
            path = ASSETS / f"{ident}.cieg"
            if not entry.get("notes") or not path.is_file():
                continue
            checked += 1
            if NOTE not in path.read_bytes():
                missing.append(ident)
        self.assertGreater(checked, 100)
        self.assertEqual(missing, [])


class TheMixerVersions(unittest.TestCase):
    def test_every_version_of_a_noted_static_event_carries_its_note(self) -> None:
        static = {living_seed: path for path in ASSETS.glob("*.cieg")
                  for living_seed in ["living_st_" + hashlib.sha1(path.stem.encode("utf-8")).hexdigest()[:6]]}
        packs = sorted(ASSETS.glob("vv*/living-st_*.pak"))
        self.assertEqual(len({p.parent.name for p in packs}), 5)          # every game has them
        missing, checked = [], 0
        unnoted: set[tuple[str, int]] = set()
        for pack in packs:
            data = living.read_pack(pack.read_bytes())
            for seed_index, seed in enumerate(data["seeds"]):
                if seed["bank"] != 2:
                    continue
                path = static.get(seed["id"])
                self.assertIsNotNone(path, f"{pack.name}: {seed['id']} is no shipped static event's version")
                want = notes_in(path.read_bytes())
                if not want:
                    continue
                for v in data["variants"]:
                    if v["seed"] != seed_index:
                        continue
                    checked += 1
                    got = notes_in(v["blob"])
                    if not got <= want:
                        missing.append(f"{pack.parent.name}/{pack.name} {path.stem} k={v['k']}: {sorted(got)}")
                    elif not got:
                        unnoted.add((path.stem, v["k"]))
        self.assertGreater(checked, 500)
        self.assertEqual(missing[:20], [])
        # A version without the note is one that left out every outcome with noted content (quiet_versions: one
        # random outcome left out): rebuilt here, its own plan names no label.
        self.assertLess(len(unnoted), 50)
        if unnoted:
            import build_event_collection_features as bf
            import living_from_static as lfs
            import vv_cie_graph as cg
            events = {e["id"]: e for e in bf.compile_events(only={ident for ident, _k in unnoted})}
            bank = living.Bank()
            pers = lfs.personalities(bank)
            for ident, k in sorted(unnoted):
                with self.subTest(event=ident, k=k):
                    e = events[ident]
                    version = next(v for v in lfs.versions(e, bank, pers)[0] if v["k"] == k)
                    g, problems = cg.validate(version["graph"], scrolling=True)
                    self.assertEqual(problems, [])
                    self.assertIsNotNone(version.get("drop"))
                    tags = content.node_tags_for(e["source"], ident, g)
                    self.assertEqual(content.plan(g, tags)["labels"], [])
                    self.assertNotEqual(content.plan(e["graph"], content.node_tags_for(e["source"], ident,
                                                                                        e["graph"]))["labels"], [])


class TheMoreIslandEventsCompanion(unittest.TestCase):
    def test_each_event_shows_its_tag_tables_note_first(self) -> None:
        mie = json.loads((TAGS / "mie.json").read_text(encoding="utf-8"))["events"]
        core = (MIE_DIR / "adv_core.inc").read_text(encoding="utf-8")
        dll = MIE_DLL.read_bytes()
        for ident, entry in mie.items():
            with self.subTest(event=ident):
                if not entry["notes"]:
                    self.assertNotIn(ident, MIE_NOTES)
                    continue
                define, source = MIE_NOTES[ident]
                line = content.note_line(entry["notes"])
                m = re.search(rf'#define {define}\s+"([^"]+)"', core)
                self.assertIsNotNone(m, define)
                self.assertEqual(m.group(1), line)
                # the question that starts the event is composed with its note first
                text = (MIE_DIR / source).read_text(encoding="utf-8")
                self.assertEqual(len(re.findall(rf"adv_popup_noted\([^;]*{define}", text)), 1)
                self.assertIn(line.encode("ascii") + b"\0", dll)

    def test_the_note_needs_the_content_notes_row(self) -> None:
        core = (MIE_DIR / "adv_core.inc").read_text(encoding="utf-8")
        self.assertIn('#define ADV_NOTES_ROW "island_event_content_notes"', core)
        self.assertEqual(content.NOTES_PATCH, "island_event_content_notes")
        self.assertIn(b"VVFP Installed Patches.txt", MIE_DLL.read_bytes())


if __name__ == "__main__":
    unittest.main()
