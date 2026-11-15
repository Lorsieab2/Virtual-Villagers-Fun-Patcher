"""The Living Event Engine's quality rules (design section D) and what the mixer never combines (owner decision,
2026-11-15: obviously problematic power dynamics, invalidating pain or trauma, portraying anyone as lesser, a
minor-adult romance or power imbalance; and genuine contradictions).

  * every generated variant obeys the bank's compat table and the mixer's rules S7 and S17 (checked on the mixer's
    own plan, independently of scripts/living_check.py's decompiled reading);
  * the rules hold for the cases they were written for: a minor never in a romantic, secret-keeping or coercive frame
    with an adult; the chief never decides a couple's, a lover's or a lonely villager's matter; an outcome naming an
    elder only with an elder in the scene;
  * everything else is kept: jokes, embarrassment, injuries, experiments (on animals too) and any personality;
  * MC: no kill or vanish, no effect on a stranger;
  * the rules are documented in living-events.md.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_living_mixer as mx  # noqa: E402

BANK = mx.Bank()
VARIANTS = mx.generate(BANK)
LE = [v for v in VARIANTS if v.bank == 0]
MC = [v for v in VARIANTS if v.bank == 1]


def pools(v: mx.Variant) -> dict[str, list[str]]:
    by_text = {mx.personality_item(BANK, p["id"]): p["id"] for p in BANK.pers}
    out = {}
    for name, p in (v.graph.get("pools") or {}).items():
        out[name] = [by_text[i] for i in p["items"]]
    return out


class Compat(unittest.TestCase):
    def test_roles_choices_archetypes(self) -> None:
        for v in LE:
            seed = BANK.seed[v.seed]
            a, b = v.plan["roles"]
            with self.subTest(seed=v.seed, k=v.k):
                for rid in (a, b):
                    self.assertTrue(BANK.seed_allows(seed["id"], "role", rid))
                for kind, ident in v.plan["choices"]:
                    self.assertTrue(BANK.seed_allows(seed["id"], kind, ident))
                for x in [x for trio in v.plan["outcomes"] for x in trio] + v.plan.get("alternatives", []):
                    if x:
                        self.assertTrue(mx.archetype_possible(BANK, seed["id"], x, a, b), x)

    def test_personalities(self) -> None:
        for v in LE:
            a, b = v.plan["roles"]
            ps = pools(v)
            fixed = v.plan["personalities"]
            for slot, rid, pool, f in (("first", a, "PA", fixed[0]), ("second", b, "PB", fixed[1])):
                items = ps.get(pool) or ([f] if f and f != "pool" else [])
                for p in items:
                    with self.subTest(seed=v.seed, k=v.k, slot=slot, p=p):
                        self.assertTrue(BANK.role_allows_personality(rid, p))

    def test_the_bank_table_is_applied_to_the_pairs(self) -> None:
        for v in LE:
            a, b = v.plan["roles"]
            if v.flags & mx.FLAG_MIX:
                continue
            self.assertNotEqual(a, b)
            self.assertFalse(mx.is_stranger(BANK, a))

    def test_an_elder_outcome_has_an_elder(self) -> None:
        """Coherence: an outcome naming an elder is drawn only with an elder in the scene."""
        for v in LE:
            a, b = v.plan["roles"]
            for trio in v.plan["outcomes"]:
                for x in trio:
                    if x and "needs_elder" in BANK.arc[x]["tags"]:
                        self.assertIsNotNone(mx.resolve_role(BANK, "elder", a, b), (v.seed, v.k, x))


class QualityD(unittest.TestCase):
    def test_every_choice_reaches_good_and_adverse(self) -> None:
        for v in LE:
            for g, d, _r in v.plan["outcomes"]:
                self.assertEqual(BANK.arc[g]["group"], "good")
                self.assertIn(BANK.arc[d]["group"], ("mixed", "bad"))

    def test_an_effect_free_path(self) -> None:
        for v in LE:
            arcs = [x for g, d, _r in v.plan["outcomes"] for x in (g, d)]
            self.assertTrue(any(not BANK.arc[x]["effects"] for x in arcs), (v.seed, v.k))

    def test_medical_offers_consent(self) -> None:
        for v in LE:
            if BANK.seed[v.seed]["consent_choice_required"]:
                self.assertTrue(any(mx.consent_choice(BANK, k, i) for k, i in v.plan["choices"]), (v.seed, v.k))

    def test_mc_never_kills_and_no_effect_on_a_stranger(self) -> None:
        for v in MC:
            subject = v.graph["roles"]["subject"]
            for n in v.graph["nodes"].values():
                for e in n.get("effects", []):
                    self.assertNotIn(e["do"], ("kill", "vanish", "die_unrecovered"))
                    if e.get("role") == "subject":
                        self.assertEqual(subject["kind"], "villager")


class NeverCombined(unittest.TestCase):
    def test_minors_never_in_an_adult_frame(self) -> None:
        """S7: romantic, secret-keeping and coercive frames cast adults only."""
        hits = 0
        for v in LE:
            seed = BANK.seed[v.seed]
            if not mx.adult_frame(seed, v.plan["choices"]):
                continue
            hits += 1
            for key, rid in zip(("first", "second"), v.plan["roles"]):
                self.assertFalse(mx.minor_role(BANK, rid), (v.seed, v.k, rid))
                r = v.graph["roles"][key]
                if r["kind"] == "villager" and not r.get("special"):
                    self.assertGreaterEqual(r["min_age"], mx.ADULT_AGE, (v.seed, v.k, key))
        self.assertGreater(hits, 40)

    def test_no_secret_with_a_child_or_teenager(self) -> None:
        for v in LE:
            if any(mx.minor_role(BANK, r) for r in v.plan["roles"]):
                self.assertFalse(any(i in mx.SECRET_CHOICES for _k, i in v.plan["choices"]), (v.seed, v.k))

    def test_the_chief_never_decides_love_or_care(self) -> None:
        """S17 and the bank's C3: the chief never decides a relationship seed's or a medical seed's matter."""
        for v in LE:
            seed = BANK.seed[v.seed]
            if v.seed not in mx.RELATIONSHIP_SEEDS and "medical" not in seed["tags"]:
                continue
            for kind, ident in v.plan["choices"]:
                if kind == "approach":
                    self.assertNotEqual(BANK.app[ident]["kind"], "authority", (v.seed, v.k, ident))

    def test_everything_else_is_kept(self) -> None:
        """The owner's decision keeps jokes, embarrassment, injuries, experiments and every personality: the mixer
        draws them somewhere, and the owner's MIX examples keep their own words."""
        arcs = {x for v in LE for t in v.plan["outcomes"] for x in t if x}
        for x in ("le_arc_mixed_08", "le_arc_bad_06", "le_arc_bad_05", "le_arc_good_06", "le_arc_rare_04"):
            self.assertIn(x, arcs)
        apps = {i for v in LE for k, i in v.plan["choices"] if k == "approach"}
        self.assertIn("le_app_play_02", apps)
        pers = {p for v in LE for ps in pools(v).values() for p in ps}
        for p in ("le_pers_superstitious", "le_pers_forgetful", "le_pers_tired", "le_pers_insecure", "le_pers_blunt"):
            self.assertIn(p, pers)
        changed = {c["mix"] for c in mx.MIX_CHANGES if c["rule"] != mx.ALT_RULE}
        self.assertEqual(changed, {"MIX-002", "MIX-027", "MIX-050", "MIX-054", "MIX-057"})

    def test_mix_alternatives_keep_the_owners_original(self) -> None:
        """Owner (2026-11-15): where an earlier rule swapped a MIX piece, the owner's original and the replacement
        are both kept, as equal alternatives."""
        alts = [c for c in mx.MIX_CHANGES if c["rule"] == mx.ALT_RULE]
        self.assertEqual(len(alts), sum(len(d) for d in mx.MIX_ALTERNATIVES.values()))
        self.assertEqual(len(alts), 52)
        for v in LE:
            if not v.flags & mx.FLAG_MIX:
                continue
            code = next(m["code"] for m in BANK.mix if m["id"] == v.plan["mix"])
            for key, new in mx.MIX_ALTERNATIVES.get(code, {}).items():
                if key in ("first", "second"):
                    pool = pools(v)["PA" if key == "first" else "PB"]
                    orig = v.plan["personalities"][0 if key == "first" else 1]
                    self.assertEqual(pool, [orig, new], (code, key))
                    continue
                i, j = int(key[0]), int(key[1])
                orig = v.plan["outcomes"][i][j]
                kids = v.graph["nodes"][f"c{i + 1}"]["children"]
                pair = [k for k in kids if k["next"] in ("o_" + orig[7:], "o_" + new[7:])]
                self.assertEqual([(k["next"], k["weight"]) for k in pair],
                                 [("o_" + orig[7:], mx.W_ALT), ("o_" + new[7:], mx.W_ALT)], (code, key))

    def test_named_cases(self) -> None:
        """The rules on the cases they were written for."""
        # S7 / C9: a love letter never casts a minor
        self.assertFalse(mx.possible_pair(BANK, BANK.seed["le_fam_05"], "le_role_cook", "le_role_teenager"))
        # S7: no secret kept between a minor and an adult
        self.assertFalse(mx.approach_allowed(BANK, BANK.seed["le_odd_09"], "le_app_withdraw_03", "le_role_cook",
                                             "le_role_child"))
        # S17: the chief never decides whether a couple has a child
        self.assertFalse(mx.approach_allowed(BANK, BANK.seed["le_fam_06"], "le_app_consult_05", "le_role_cook",
                                             "le_role_fisher"))
        # coherence: the elder's death needs an elder in the scene
        self.assertFalse(mx.archetype_possible(BANK, "le_art_09", "le_arc_rare_02", "le_role_cook", "le_role_fisher"))
        self.assertTrue(mx.archetype_possible(BANK, "le_art_09", "le_arc_rare_02", "le_role_cook",
                                              "le_role_elderly_villager"))
        # kept: a joke may lead anywhere, an injury may land on a child
        self.assertTrue(mx.archetype_possible(BANK, "le_odd_09", "le_arc_bad_05", "le_role_child", "le_role_cook"))

    def test_rules_documented(self) -> None:
        doc = mx.DOC.read_text(encoding="utf-8")
        for rule, text in mx.SENSITIVITY_RULES.items():
            self.assertIn(f"| {rule} | {text} |", doc)


if __name__ == "__main__":
    unittest.main()
