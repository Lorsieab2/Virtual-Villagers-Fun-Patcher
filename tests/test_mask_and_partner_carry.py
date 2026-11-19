"""Two v1.35.97 follow-ups of PR #772 (feat/97-island-events-ui-3), once round 6's data was beside it:

* The Mysterious Mask, the procedural mixer's copy (data/event_collection/mie/mie/mie_mysterious_mask.json, built by
  scripts/go_events/gen_mie.py): walk -> lost -> rescued -> the elders now opens a fresh scroll page ("new_page"),
  so the owner's whole L679-681 shows, "The other villagers rally behind them, and hope for an end to the madness."
  included.  It was cut there before (one 1990-byte text).
* "A man may carry the baby by chance": pregnant / nursing flags bit 3 (value 8, "partner_may_carry").  The compiler
  takes it; every couple pregnancy of the new events carries it (a pregnant effect with a partner and no
  any_birth_sex); a single parent, a reason-based one (any_birth_sex) and a nursing foundling never do.

Static: no game, no save.
"""
from __future__ import annotations

import copy
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import collection_check as cc  # noqa: E402
import vv_cie_graph as cg  # noqa: E402
import vv_owner_layout as owner  # noqa: E402
import vv_player_events as pe  # noqa: E402
import vv_procedural as vp  # noqa: E402

COLLECTION = ROOT / "data" / "event_collection"
MASK = COLLECTION / "mie" / "mie" / "mie_mysterious_mask.json"
MASK_CIEG = ROOT / "assets" / "event_collection" / "mie_mysterious_mask.cieg"
OWNER_FILE = ROOT / "docs" / "more-island-events" / "Additional Virtual Villagers Events By Lorsieab2.txt"
GO_SEEDS = ROOT / "data" / "procedural_pieces" / "go_seeds.json"
PIECES = ROOT / "assets" / "event_collection" / "pieces"
LAST = "The other villagers rally behind them, and hope for an end to the madness."
GO_SOURCES = ("balance", "rewrites")


def couple(e: dict) -> bool:
    """A couple's pregnancy: pregnant, with a partner, not reason-based (any_birth_sex)."""
    return e.get("do") == "pregnant" and bool(e.get("partner")) and not e.get("any_birth_sex")


def births(o) -> list[dict]:
    out = []
    if isinstance(o, dict):
        if o.get("do") in ("pregnant", "nursing"):
            out.append(o)
        for v in o.values():
            out += births(v)
    elif isinstance(o, list):
        for v in o:
            out += births(v)
    return out


def tiny(effect: dict) -> dict:
    return {"format": "vvfp-cie-graph", "version": 6, "title": "Two Hearts", "games": [1, 2, 3, 4, 5],
            "roles": {"subject": {"kind": "villager", "min_age": 18}, "friend": {"kind": "villager", "min_age": 18}},
            "start": "a", "nodes": {"a": {"text": "(Subject) and (friend) smile.", "effects": [effect]}}}


class MysteriousMaskMixerCopy(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = json.loads(MASK.read_text(encoding="utf-8"))
        self.node = self.doc["nodes"]["f_end_short"]

    def test_the_owners_sentence_is_in_the_source(self) -> None:
        lines = OWNER_FILE.read_text(encoding="utf-8").splitlines()
        self.assertTrue(lines[680].rstrip().endswith(LAST), "L681 of the owner's file")

    def test_the_cut_node_is_a_fresh_page_with_the_whole_sentence(self) -> None:
        self.assertIs(self.node.get("new_page"), True)
        self.assertNotEqual(self.node.get("popup"), "append", "new_page is on a popup that opens a new popup")
        self.assertTrue(self.node["text"].endswith(LAST), self.node["text"][-120:])
        self.assertNotIn("src_cut", self.node)
        self.assertEqual(self.node["text"], self.doc["nodes"]["f_end"]["text"], "every path says the same words")
        self.assertFalse([a for a in self.doc["collection"].get("approximations", []) if "OWNER QUESTION" in a])

    def test_the_flag_survives_the_engines_compile(self) -> None:
        lg, problems = cg.validate(cc.graph_for_engine(copy.deepcopy(self.doc)), scrolling=True)
        self.assertEqual(problems, [])
        back = cg.decompile_graph(cg.compile_graph(lg))
        self.assertIs(back["nodes"]["f_end_short"].get("new_page"), True)
        self.assertTrue(back["nodes"]["f_end_short"]["text"].endswith(LAST))
        shipped = cg.decompile_graph(MASK_CIEG.read_bytes())
        self.assertIs(shipped["nodes"]["f_end_short"].get("new_page"), True, "the built .cieg")
        self.assertTrue(shipped["nodes"]["f_end_short"]["text"].endswith(LAST))

    def test_the_mixer_versions_in_the_living_pack(self) -> None:
        import vv_living_mixer as lm
        pack = lm.read_pack((ROOT / "assets" / "event_collection" / "vv4" / "living-st_mie.pak").read_bytes())
        masks = [g for g in (cg.decompile_graph(v["blob"]) for v in pack["variants"])
                 if g.get("title") == "The Mysterious Mask"]
        self.assertTrue(masks)
        for g in masks:
            self.assertIs(g["nodes"]["f_end_short"].get("new_page"), True)
            self.assertTrue(g["nodes"]["f_end_short"]["text"].endswith(LAST))

    def test_the_rescued_path_now_fits_its_scroll_pages(self) -> None:
        g, problems = cg.validate(cc.graph_for_engine(copy.deepcopy(self.doc)), scrolling=True)
        self.assertEqual(problems, [])


class CompilerTakesPartnerMayCarry(unittest.TestCase):
    def test_flag_value_matches_the_engine(self) -> None:
        engine = (ROOT / "native" / "vvfp_story_upgrades" / "story_graph.inc").read_text(encoding="utf-8")
        self.assertRegex(engine, r"#define CG_FX_PARTNER_MAY_CARRY 8u")
        self.assertEqual(cg.PARTNER_MAY_CARRY_FLAG, 8)

    def test_bit_8_compiles_and_round_trips(self) -> None:
        for do in ("pregnant", "nursing"):
            e = {"do": do, "role": "subject", "partner": "friend", "partner_may_carry": True}
            g = cg.load(tiny(e))
            data = cg.compile_graph(g)
            back = cg.decompile_graph(data)["nodes"]["a"]["effects"][0]
            self.assertIs(back.get("partner_may_carry"), True, do)
            self.assertEqual(back.get("partner"), "friend")
            plain = cg.decompile_graph(cg.compile_graph(cg.load(tiny({k: v for k, v in e.items()
                                                                        if k != "partner_may_carry"}))))
            self.assertNotIn("partner_may_carry", plain["nodes"]["a"]["effects"][0])
            self.assertNotEqual(data, cg.compile_graph(cg.load(tiny({k: v for k, v in e.items()
                                                                     if k != "partner_may_carry"}))))

    def test_with_the_other_flags(self) -> None:
        e = {"do": "pregnant", "role": "subject", "partner": "friend", "partner_may_carry": True, "babies": 3}
        back = cg.decompile_graph(cg.compile_graph(cg.load(tiny(e))))["nodes"]["a"]["effects"][0]
        self.assertEqual((back["babies"], back["partner_may_carry"]), (3, True))

    def test_refused_without_a_partner_or_not_a_bool(self) -> None:
        _, p = cg.normalize(tiny({"do": "pregnant", "role": "subject", "partner_may_carry": True}))
        self.assertTrue(any("partner_may_carry needs a partner" in x for x in p), p)
        _, p = cg.normalize(tiny({"do": "pregnant", "role": "subject", "partner": "friend",
                                  "partner_may_carry": "yes"}))
        self.assertTrue(any("partner_may_carry is true or false" in x for x in p), p)


class EveryCouplePregnancyIsFlagged(unittest.TestCase):
    def check(self, effects: list[dict], where: str) -> tuple[int, int]:
        flagged = others = 0
        for e in effects:
            if couple(e):
                self.assertIs(e.get("partner_may_carry"), True, f"{where}: {e}")
                flagged += 1
            else:
                self.assertNotIn("partner_may_carry", e, f"{where}: {e}")
                others += 1
        return flagged, others

    def test_the_go_collection_events(self) -> None:
        total = 0
        for sid in GO_SOURCES:
            for p in sorted((COLLECTION / sid).glob("*/*.json")):
                f, _ = self.check(births(json.loads(p.read_text(encoding="utf-8"))), p.name)
                total += f
        self.assertEqual(total, 67)

    def test_no_other_collection_event_has_the_flag_without_a_couple(self) -> None:
        for p in COLLECTION.rglob("*.json"):
            t = p.read_text(encoding="utf-8")
            if '"pregnant"' in t or '"nursing"' in t:
                self.check(births(json.loads(t)), p.name)

    def test_the_go_seeds(self) -> None:
        pieces = json.loads(GO_SEEDS.read_text(encoding="utf-8"))["pieces"]
        f, others = self.check([e for p in pieces for e in p["effects"] if e.get("do") in ("pregnant", "nursing")],
                               "go_seeds")
        self.assertEqual(f, 63)
        self.assertGreater(others, 0, "single parents, foundlings and reason-based ones stay unflagged")

    def test_the_built_collection_files(self) -> None:
        n = 0
        for sid in GO_SOURCES:
            for p in sorted((COLLECTION / sid).glob("*/*.json")):
                doc = json.loads(p.read_text(encoding="utf-8"))
                if not any(couple(e) for e in births(doc)):
                    continue
                cieg = ROOT / "assets" / "event_collection" / f"{doc['collection']['id']}.cieg"
                back = births(cg.decompile_graph(cieg.read_bytes()))
                n += self.check(back, cieg.name)[0]
        self.assertEqual(n, 67)

    def test_the_procedural_pieces(self) -> None:
        flagged = 0
        for p in sorted(PIECES.glob("*.pcb")):
            for piece in vp.read_pcb(p.read_bytes(), p.stem).pieces:
                for e in piece.effects:
                    if e.code != cg.EFFECT_CODES["pregnant"] and e.code != cg.EFFECT_CODES["nursing"]:
                        continue
                    j = vp.effect_json(e, [s.name for s in piece.slots])
                    j["do"] = "pregnant" if e.code == cg.EFFECT_CODES["pregnant"] else "nursing"
                    flagged += self.check([j], f"{p.name} {piece.id}")[0]
        self.assertGreater(flagged, 0)

    def test_b260_and_b336_one_of_the_couple_carries(self) -> None:
        """The owner (2026-11-18): the two hand-mapped couples are flagged, and nothing of theirs says the carrier
        is born female (the shown pages name no carrier; the ledger says one of the couple carries)."""
        for name, n in (("b260_warm_stone", 3), ("b336_lazy_river", 1)):
            doc = json.loads((COLLECTION / "balance" / "bal" / f"{name}.json").read_text(encoding="utf-8"))
            couples = [e for e in births(doc) if couple(e)]
            self.assertEqual(len(couples), n, name)
            self.assertTrue(all(e.get("partner_may_carry") is True for e in couples), name)
            self.assertNotIn("born female", json.dumps(doc), name)
            self.assertIn("one of the couple carries the baby", json.dumps(doc["collection"]), name)
        go = (ROOT / "scripts" / "go_events" / "gen_go.py").read_text(encoding="utf-8")
        self.assertNotIn("cast born female", go)

    def test_the_owner_layout_rule(self) -> None:
        """vv_owner_layout (the GO files and the Player Events importer's owner layout): one EFFECT phrase each."""
        def fx(phrase: str) -> dict:
            return [e for e in owner.owner_effects(phrase, [1])[0] if e["do"] in ("pregnant", "nursing")][0]
        self.assertIs(fx("(name1) is pregnant, with (name2) as the other parent").get("partner_may_carry"), True)
        self.assertNotIn("partner_may_carry", fx("(name1) is pregnant"))
        magic = fx("(name1) is pregnant, with (name2) as the other parent (magic)")
        self.assertTrue(magic.get("any_birth_sex"))
        self.assertNotIn("partner_may_carry", magic)
        nursing = fx("(name1) becomes nursing a baby, with (name2) as the other parent")
        self.assertNotIn("partner_may_carry", nursing)


class PlayerEventsImporter(unittest.TestCase):
    SIMPLE = ("Title: The Two Hearts\nApplies to: VV1, VV3\nThemes: romance\nEvent:\n"
              "(Name) and (friend) watch the sea.\nChoice 1: Stay\n* Outcome A: They stay.\n  Effect: {fx}\n"
              "Choice 2: Go Home\n* Outcome A: They go home.\n")

    def effect(self, fx: str) -> tuple[dict, bytes]:
        items = pe.parse_text(self.SIMPLE.format(fx=fx), "t.txt")
        self.assertEqual(len(items), 1)
        self.assertFalse(items[0].problems, [str(p) for p in items[0].problems])
        c, probs = pe.compile_item(items[0], "pl_test_001")
        self.assertIsNotNone(c, probs)
        e = [e for n in c.graph["nodes"].values() for e in n.get("effects", []) or []][0]
        return e, c.cieg

    def test_a_couple_pregnancy_is_flagged_and_compiled_with_bit_8(self) -> None:
        e, cieg = self.effect("PREGNANT subject WITH friend")
        self.assertIs(e.get("partner_may_carry"), True)
        back = births(cg.decompile_graph(cieg))
        self.assertIs(back[0].get("partner_may_carry"), True)

    def test_single_reason_based_and_nursing_are_not(self) -> None:
        for fx in ("PREGNANT subject", "PREGNANT subject WITH friend (ANY BIRTH SEX)", "NURSING subject WITH friend",
                   "NURSING subject"):
            e, _ = self.effect(fx)
            self.assertNotIn("partner_may_carry", e, fx)

    def test_with_twins_still_a_couple(self) -> None:
        e, _ = self.effect("PREGNANT subject WITH friend (TWINS)")
        self.assertEqual((e.get("babies"), e.get("partner_may_carry")), (2, True))

    def test_the_piece_record_carries_bit_8(self) -> None:
        e = {"do": "pregnant", "role": "subject", "partner": "friend", "partner_may_carry": True}
        _code, flags, *_ = pe._effect_record(e, {"subject": 0, "friend": 1}, 1)
        self.assertEqual(flags & cg.PARTNER_MAY_CARRY_FLAG, cg.PARTNER_MAY_CARRY_FLAG)

    def test_the_ai_prompt_says_what_the_parser_does(self) -> None:
        text = pe.ai_prompt()
        self.assertIn("PREGNANT <who> WITH <who> without (ANY BIRTH SEX) is a couple's pregnancy", text)
        self.assertIn("the partner may carry instead by the player's chance setting", text)
        # The format the prompt lists is the parser's: no new word, the couple is PREGNANT ... WITH ...
        self.assertIn("PREGNANT <who> [WITH <who>] [(ANY BIRTH SEX)]", pe.EFFECT_VOCABULARY)
        shipped = (pe.PLAYER_FOLDER / pe.PROMPT_NAME).read_text(encoding="utf-8")
        self.assertEqual(shipped.replace("\r\n", "\n"), text)
        self.assertTrue(re.search(r"couple's pregnancy", shipped))


if __name__ == "__main__":
    unittest.main()
