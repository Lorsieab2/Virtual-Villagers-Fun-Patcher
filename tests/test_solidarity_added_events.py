"""Village Solidarity on EVERY added event's ending (the owner, 2026-11-20: "add tags to every single event!!!").

Every event the patcher adds -- the Isola Grand Event Collection (each compiled .cieg), the Living Event Engine's
packs (living-*.pak, the static events' mixer versions among them), the procedural pieces (pieces-*.pcb: each
outcome piece), the Custom Island Event Library's two examples (data/cie_graphs) and More Island Events' own events
(its DLL) -- carries a raise / lower / neutral tag on every ending, by the owner's rule (src/vv_solidarity_endings.py).
The original games' own events are not here (feat/97-solidarity-stock-events).

What this file proves (each fails without the change):
  * NO SHIPPED ENDING IS UNTAGGED: every ending page of every compiled collection event and every Living variant,
    every outcome piece, every example ending; an explicit allow-list names the only exceptions (none: a page with
    nowhere to go is an ending);
  * THE RULE: spot checks of the classifier (a death lowers, food raises, one villager's skill is neutral, a quarrel
    lowers, a gathering raises, mixed results are neutral), and a raise / lower / neutral ending compiled to its node
    flags bits;
  * THE TABLE: every collection event's every ending is in data/event_collection/solidarity_tags.json; the reviewed
    judgement calls are applied; the Living Culture drafts keep their own tags;
  * MORE ISLAND EVENTS: each ending calls "VVFP Village Solidarity.dll"'s VvfpVillageScoreTag once, with the tag its
    collection form carries (data/event_collection/mie), only when that companion is loaded -- emulated on the stock
    The Secret City with Diving for Treasure.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

import vv_cie_graph as cg  # noqa: E402
import vv_procedural as vp  # noqa: E402
import vv_solidarity_endings as se  # noqa: E402

ASSETS = ROOT / "assets" / "event_collection"
TAGS = ROOT / "data" / "event_collection" / "solidarity_tags.json"
LIVING_TAGS = ROOT / "data" / "living_events" / "solidarity_tags.json"
REVIEW = ROOT / "data" / "event_collection" / "solidarity_review.json"
MIE = ROOT / "native" / "vvfp_more_island_events"
SOL = {1: "raise", 2: "lower", 3: "neutral"}

# Pages with nowhere to go that are NOT endings, by (file, node): none.  A page added here must say why.
NOT_ENDINGS: dict[tuple[str, str], str] = {}


def untagged_endings(g: dict, where: str) -> list[str]:
    return [f"{where} {nid}" for nid, n in g["nodes"].items()
            if se.is_ending(n) and n.get("solidarity") not in SOL.values() and (where, nid) not in NOT_ENDINGS]


class TheRule(unittest.TestCase):
    def test_the_effects_decide_first(self) -> None:
        cases = [([{"do": "kill", "role": "subject"}, {"do": "food", "size": "large"}], "lower"),
                 ([{"do": "vanish", "role": "subject"}], "lower"),
                 ([{"do": "baby_lost", "role": "parent"}], "lower"),
                 ([{"do": "status", "role": "subject", "status": "heathen"}], "lower"),
                 ([{"do": "damage", "structures": "any", "size": "small"}], "lower"),
                 ([{"do": "food", "size": "small"}], "raise"),
                 ([{"do": "tech", "size": "small", "loss": True}], "lower"),
                 ([{"do": "new_villager", "age": "adult"}], "raise"),
                 ([{"do": "cure", "target": {"all": True}}], "raise"),
                 ([{"do": "celebrate", "who": "all"}], "raise"),
                 ([{"do": "skill", "role": "subject", "min": 5, "max": 10}], "neutral"),
                 ([{"do": "health_change", "role": "subject", "min": -40, "max": -20}], "neutral"),
                 ([{"do": "food", "size": "small"}, {"do": "tech", "size": "small", "loss": True}], "neutral"),
                 ([{"do": "trade", "get": "tech", "give": "food"}], "neutral")]
        for effects, want in cases:
            with self.subTest(effects=effects):
                self.assertEqual(se.classify("(Name) walks home.", effects)[0], want)

    def test_the_words_of_the_whole_village(self) -> None:
        self.assertEqual(se.classify("The whole village cheers and sings together.", [])[0], "raise")
        self.assertEqual(se.classify("The accusation divides the village.", [])[0], "lower")
        self.assertEqual(se.classify("Their argument lasts all night until both storm off.", [])[0], "lower")
        # two villagers' own moment, quiet remembrance, or nothing at all: neutral
        self.assertEqual(se.classify("They sit on the beach together and watch the lights.", [])[0], "neutral")
        self.assertEqual(se.classify("The village holds a quiet remembrance.", [])[0], "neutral")
        self.assertEqual(se.classify("(Name) finds a shell.", [])[0], "neutral")

    def test_a_tag_compiles_to_its_node_flags_bits(self) -> None:
        g = {"format": "vvfp-cie-graph", "version": 6, "title": "Three Ends", "games": [1, 2, 3, 4, 5],
             "roles": {"subject": {"kind": "villager"}}, "start": "q",
             "nodes": {"q": {"type": "question", "text": "(Name) wonders.",
                             "choices": [{"label": "Up", "next": "up"}, {"label": "Down", "next": "down"},
                                         {"label": "Still", "next": "still"}]},
                       "up": {"text": "Food!", "effects": [{"do": "food", "size": "small"}], "solidarity": "raise"},
                       "down": {"text": "Gone.", "solidarity": "lower"},
                       "still": {"text": "Nothing.", "solidarity": "neutral"}}}
        n, problems = cg.validate(g, scrolling=True)
        self.assertEqual(problems, [])
        back = cg.decompile_graph(cg.compile_graph(n))
        self.assertEqual({k: back["nodes"][k].get("solidarity") for k in ("up", "down", "still")},
                         {"up": "raise", "down": "lower", "still": "neutral"})
        self.assertEqual(cg.SOLIDARITY_CODES, {"raise": 1, "lower": 2, "neutral": 3})


class TheCollection(unittest.TestCase):
    def test_every_compiled_event_ending_is_tagged(self) -> None:
        files = sorted(ASSETS.glob("*.cieg"))
        self.assertGreater(len(files), 3000)
        missing: list[str] = []
        counts = {t: 0 for t in SOL.values()}
        for path in files:
            g = cg.decompile_graph(path.read_bytes())
            missing += untagged_endings(g, path.name)
            for n in g["nodes"].values():
                if se.is_ending(n) and n.get("solidarity") in counts:
                    counts[n["solidarity"]] += 1
        self.assertEqual(missing[:20], [])
        self.assertTrue(all(counts.values()), counts)

    def test_the_table_tags_every_event_and_only_known_words(self) -> None:
        table = json.loads(TAGS.read_text(encoding="utf-8"))
        ids = {p.stem for p in ASSETS.glob("*.cieg")}
        self.assertLessEqual(ids, set(table))
        for ident, entry in table.items():
            self.assertTrue(entry.get("nodes"), ident)
            self.assertLessEqual(set(entry["nodes"].values()), set(SOL.values()), ident)

    def test_the_reviewed_calls_are_applied(self) -> None:
        table = json.loads(TAGS.read_text(encoding="utf-8"))
        review = json.loads(REVIEW.read_text(encoding="utf-8"))
        living = json.loads(LIVING_TAGS.read_text(encoding="utf-8"))
        for ident, nodes in review.items():
            for nid, (tag, why) in nodes.items():
                with self.subTest(ident=ident, nid=nid):
                    self.assertTrue(why.startswith("read:"))
                    got = living.get(nid) if ident == "living_bank" else table[ident]["nodes"].get(nid)
                    self.assertEqual(got, tag)

    def test_living_culture_keeps_its_own_tags(self) -> None:
        import tag_village_solidarity as tv
        table = json.loads(TAGS.read_text(encoding="utf-8"))
        seen = 0
        for path in sorted((ROOT / "data" / "event_collection" / "drafts_c").glob("dr_lc?/*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            for nid, tag in tv.ledger_tags(data).items():
                seen += 1
                self.assertEqual(table[data["collection"]["id"]]["nodes"].get(nid), tag, f"{path.name} {nid}")
        self.assertGreater(seen, 900)


class TheLivingEngineAndThePieces(unittest.TestCase):
    def test_every_living_variant_ending_is_tagged(self) -> None:
        import vv_living_mixer as lm
        packs = sorted(ASSETS.glob("vv*/living-*.pak"))
        self.assertTrue(packs)
        missing: list[str] = []
        variants = 0
        for path in packs:
            for v in lm.read_pack(path.read_bytes())["variants"]:
                variants += 1
                missing += untagged_endings(cg.decompile_graph(v["blob"]), f"{path.parent.name}/{path.name}")
        self.assertGreater(variants, 1000)
        self.assertEqual(missing[:20], [])

    def test_every_archetype_and_mc_outcome_has_its_tag(self) -> None:
        import vv_living_mixer as lm
        bank = lm.Bank()
        ids = {a["id"] for a in bank.archetypes} | {o["id"] for s in bank.mc_sits for a in s["approaches"]
                                                   for o in a["outcomes"]}
        living = json.loads(LIVING_TAGS.read_text(encoding="utf-8"))
        self.assertEqual(ids - set(living), set())
        self.assertEqual(lm.solidarity_tag("le_arc_rare_02"), "lower")     # a beloved elder dies

    def test_every_outcome_piece_is_tagged(self) -> None:
        files = sorted((ASSETS / "pieces").glob("pieces-*.pcb"))
        self.assertTrue(files)
        missing, outcomes = [], 0
        for path in files:
            for p in vp.read_pcb(path.read_bytes(), path.stem).pieces:
                if p.kind == vp.KIND_OUTCOME:
                    outcomes += 1
                    if vp.solidarity_of(p.flags) is None:
                        missing.append(f"{path.name} {p.id}")
                elif p.flags & vp.PF_SOLIDARITY_MASK:
                    missing.append(f"{path.name} {p.id}: a tag on a piece that is not an outcome")
        self.assertGreater(outcomes, 1000)
        self.assertEqual(missing[:20], [])

    def test_the_story_dll_reads_the_piece_tag(self) -> None:
        src = (ROOT / "native" / "vvfp_story_upgrades" / "story_procedural.inc").read_text(encoding="utf-8")
        self.assertIn("#define PC_F_SOLIDARITY 0x18u", src)
        self.assertIn("(((o[6] & PC_F_SOLIDARITY) >> PC_F_SOLIDARITY_SHIFT) << 2)", src)
        self.assertEqual(vp.PF_SOLIDARITY_MASK, 0x18)
        self.assertEqual(vp.solidarity_of(vp.solidarity_flags("lower") | vp.PF_AUTO_LINES), "lower")


class TheExamples(unittest.TestCase):
    def test_both_examples_tag_every_ending(self) -> None:
        for path in sorted((ROOT / "data" / "cie_graphs").glob("*.json")):
            with self.subTest(path=path.name):
                g, problems = cg.validate(json.loads(path.read_text(encoding="utf-8")), scrolling=True)
                self.assertEqual(problems, [])
                self.assertEqual(untagged_endings(g, path.name), [])
                back = cg.decompile_graph(cg.compile_graph(g))
                self.assertEqual(untagged_endings(back, path.name), [])

    def test_the_cave_explorers_generator_writes_them(self) -> None:
        import build_cave_explorers_graph as cave
        path = ROOT / "data" / "cie_graphs" / "the_cave_explorers.json"
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), cave.build())


# ---- More Island Events' own events ---------------------------------------------------------------------------------

# Each native ending's tag (the C source), and the same ending in the event's collection form.
NATIVE_TAGS = {
    "mie_diving": {"doubloons": "raise", "container": "raise", "buoy": "neutral", "ashore": "neutral",
                   "dies": "lower", "lost": "lower", "rescued": "neutral", "better": "neutral"},
    "mie_dolphins": {"hunt": "raise", "slap": "neutral", "hang": "raise"},
    "mie_climb": {"fall": "lower", "summit": "raise", "advice": "neutral"},
    "mie_cave_explorers": {"dont": "neutral", "fall_out": "lower", "make_up": "raise", "chasm1": "lower",
                           "chasm2": "lower", "map": "lower", "coins": "raise", "treasure": "raise",
                           "preserved": "raise", "ret_food": "raise", "ret_tech": "raise", "k1": "lower",
                           "k2": "lower", "k3": "raise"},
    "mie_adventurer": {"a1_food": "raise", "a1_tech": "raise", "a5_food": "raise", "a5_tech": "raise",
                       "a8_food": "raise", "a8_tech": "raise", "a2": "lower", "a3": "lower", "a4": "lower",
                       "a6": "lower", "a7": "neutral", "a9": "neutral", "b_home": "neutral", "heal1": "lower",
                       "heal2": "neutral", "heal3": "neutral", "lost2": "lower", "lost2_vv5": "lower",
                       "lost3": "neutral", "lost4": "lower", "lost5": "lower", "lost6": "lower"},
    "mie_rumblings": {"*": "lower"},
    "mie_remembrance": {"*": "neutral"},
    "mie_mysterious_mask": {"*": "lower"},
    "mie_troubling_signs": {"*": "lower"},
}


class MoreIslandEvents(unittest.TestCase):
    def test_the_collection_form_carries_the_native_tags(self) -> None:
        table = json.loads(TAGS.read_text(encoding="utf-8"))
        for ident, want in NATIVE_TAGS.items():
            with self.subTest(ident=ident):
                got = table[ident]["nodes"]
                if "*" in want:
                    self.assertEqual(set(got.values()), {want["*"]})
                else:
                    self.assertEqual(got, want)

    def test_every_ending_function_passes_its_tag_once(self) -> None:
        core = (MIE / "adv_core.inc").read_text(encoding="utf-8")
        self.assertIn('GetModuleHandleA("VVFP Village Solidarity.dll")', core)
        self.assertIn('"VvfpVillageScoreTag"', core)
        for name, fn in (("adv_core.inc", "adv_make_effects"), ("cave_core.inc", "cave_effects"),
                         ("climb_core.inc", "climb_effects"), ("dive_core.inc", "dv_effects"),
                         ("dolphin_core.inc", "dp_effects"), ("mask_core.inc", "mk_effects"),
                         ("troubling_core.inc", "ts_effects"), ("ceremony_core.inc", "cr_effects")):
            with self.subTest(name=name):
                src = (MIE / name).read_text(encoding="utf-8")
                body = re.search(r"static void " + fn + r"\([^)]*\) \{(.*?)\n\}", src, re.S).group(1)
                self.assertEqual(body.count("adv_solidarity("), 1)
                self.assertIn("effects_made = 1", body)


try:
    from test_diving_for_treasure import NEEDS, dive_rolls, three  # noqa: E402
except Exception:  # noqa: BLE001
    NEEDS = unittest.skip("the More Island Events harness is not available")

FAKE_SOLIDARITY = 0x0EC00000


def fake_solidarity(v) -> list[tuple]:
    """"VVFP Village Solidarity.dll" stood in for on `v`: each VvfpVillageScoreTag call (game, score, tag, title)."""
    p = v.p
    calls: list[tuple] = []
    code = p.alloc(16)
    p.write(code, b"\xC3" * 16)

    def tag(pr):
        calls.append((pr.arg(0), pr.arg(1), pr.arg(2), pr.cstring(pr.arg(3)) if pr.arg(3) else ""))
        return 55, 16
    p.stub(code, tag)
    module, proc = p.api_handlers["GetModuleHandleA"], p.api_handlers["GetProcAddress"]
    p.api_handlers["GetModuleHandleA"] = lambda pr, m=module: (
        (FAKE_SOLIDARITY, 4) if pr.arg(0) and pr.cstring(pr.arg(0)) == "VVFP Village Solidarity.dll" else m(pr))
    p.api_handlers["GetProcAddress"] = lambda pr, c=proc: (
        ((code if pr.cstring(pr.arg(1)) == "VvfpVillageScoreTag" else 0), 8) if pr.arg(0) == FAKE_SOLIDARITY
        else c(pr))
    return calls


@NEEDS
class TheDllMovesTheScore(unittest.TestCase):
    """Diving for Treasure, emulated on the stock The Secret City: each ending passes its tag once, with the game."""

    def play(self, answer: int = 0, solidarity: bool = True, **kw) -> list[tuple]:
        v = three()
        calls = fake_solidarity(v) if solidarity else None
        self.assertTrue(v.open(dive_rolls(**kw)))
        v.play(answer)
        return calls

    def test_each_ending_its_tag(self) -> None:
        for kw, answer, tag in ((dict(find=0), 0, 1),                                   # doubloons: raise
                                (dict(find=2), 0, 1),                                   # the container: raise
                                (dict(find=1), 0, 3),                                   # the buoy: neutral
                                (dict(find=3, survive=False, sink="dies"), 0, 2),       # drowned: lower
                                (dict(find=3, survive=False, sink="disappears"), 0, 2),  # lost at sea: lower
                                (dict(find=3, survive=False, sink="rescued"), 0, 3),     # rescued: neutral
                                (dict(find=0), 1, 3)):                                  # "Better Not": neutral
            with self.subTest(kw=kw, answer=answer):
                calls = self.play(answer, **kw)
                self.assertEqual([(c[0], c[1], c[2]) for c in calls], [(3, 0, tag)])

    def test_without_the_companion_nothing_is_called(self) -> None:
        self.assertIsNone(self.play(solidarity=False, find=0))      # and the event runs to its end as before


if __name__ == "__main__":
    unittest.main()
