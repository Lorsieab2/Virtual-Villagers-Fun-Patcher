"""The Living Event Engine's quality rules (design section D) and the owner's content rules (sensitivity S1-S9).

  * every generated variant obeys the bank's compat table and the mixer's sensitivity rules (checked on the
    mixer's own plan, independently of scripts/living_check.py's decompiled reading);
  * the rules themselves hold for the cases the owner named: a minor never in a romantic, secret-keeping or
    coercive frame with an adult; no injury on a child; no joke that hurts; no trial that injures; no trait blamed;
  * MC: no kill or vanish, no effect on a stranger;
  * the sensitivity rules are documented in living-events.md.
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
                for (kind, ident), trio in zip(v.plan["choices"], v.plan["outcomes"]):
                    for x in trio:
                        if x:
                            self.assertTrue(mx.archetype_possible(BANK, seed["id"], x, a, b), x)
                            self.assertTrue(mx.arc_ok_after(BANK, kind, ident, x), (ident, x))

    def test_personalities(self) -> None:
        for v in LE:
            seed = BANK.seed[v.seed]
            a, b = v.plan["roles"]
            arcs = [x for t in v.plan["outcomes"] for x in t if x]
            slots = mx.sensitive_slots(BANK, arcs, a, b, v.games)
            ps = pools(v)
            fixed = v.plan["personalities"]
            for slot, rid, pool, f in (("first", a, "PA", fixed[0]), ("second", b, "PB", fixed[1])):
                items = ps.get(pool) or ([f] if f and f != "pool" else [])
                for p in items:
                    with self.subTest(seed=v.seed, k=v.k, slot=slot, p=p):
                        self.assertTrue(mx.personality_ok(BANK, seed, rid, p, slot in slots))

    def test_the_bank_table_is_applied_to_the_pairs(self) -> None:
        for v in LE:
            a, b = v.plan["roles"]
            if v.flags & mx.FLAG_MIX:
                continue
            self.assertNotEqual(a, b)
            self.assertFalse(mx.is_stranger(BANK, a))


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

    def test_supernatural_never_resolves(self) -> None:
        for v in LE:
            if "supernatural" in BANK.seed[v.seed]["tags"]:
                for t in v.plan["outcomes"]:
                    for x in t:
                        if x:
                            self.assertNotIn("resolves", BANK.arc[x]["tags"])

    def test_beliefs_are_never_mocked_or_corrected(self) -> None:
        """S10 (owner world rule, 2026-11-15): belief and spirit seeds take no mocking choice and no outcome that
        corrects or settles a belief."""
        for v in LE:
            seed = BANK.seed[v.seed]
            if not mx.belief_seed(seed):
                continue
            for kind, ident in v.plan["choices"]:
                self.assertNotIn("mocking", mx.choice_classes(BANK, kind, ident), (v.seed, v.k, ident))
            for t in v.plan["outcomes"]:
                for x in t:
                    if x:
                        self.assertFalse(mx.belief_corrected(BANK, seed, x), (v.seed, v.k, x))

    def test_a_wrong_act_is_never_rewarded_or_excused(self) -> None:
        """S11 (owner, 2026-11-15): a prank, alleged cheating or a rule meant only for outsiders is never laughed
        off, celebrated or kept; following the unjust custom is never offered (the owner's example keeps its own
        choice, and its good outcome acknowledges the people affected)."""
        self.assertTrue(mx.WRONG_ACT_SEEDS)
        for v in LE:
            seed = BANK.seed[v.seed]
            if v.seed not in mx.WRONG_ACT_SEEDS:
                continue
            for (kind, ident), outs in zip(v.plan["choices"], v.plan["outcomes"]):
                if not v.flags & mx.FLAG_MIX:
                    self.assertNotIn("mocking", mx.choice_classes(BANK, kind, ident), (v.seed, v.k, ident))
                    self.assertNotIn(ident, mx.ENDORSE_CHOICES.get(v.seed, set()), (v.seed, v.k))
                for x in outs:
                    if x:
                        self.assertNotIn("light", BANK.arc[x]["tags"], (v.seed, v.k, x))
                        self.assertNotIn(x, mx.UNJUST_KEEP, (v.seed, v.k, x))
                        self.assertTrue(mx.endorse_ok(BANK, seed, kind, ident, x), (v.seed, v.k, ident, x))

    def test_appearance_is_never_a_punchline(self) -> None:
        """S12 (owner rules 15-18): a seed about looks or the body takes no mocking choice (outside the owner's own
        example) and no outcome that blames or embarrasses."""
        for v in LE:
            if v.seed not in mx.APPEARANCE_SEEDS:
                continue
            for (kind, ident), outs in zip(v.plan["choices"], v.plan["outcomes"]):
                if not v.flags & mx.FLAG_MIX:
                    self.assertNotIn("mocking", mx.choice_classes(BANK, kind, ident), (v.seed, v.k, ident))
                for x in outs:
                    if x:
                        self.assertNotIn("blame", BANK.arc[x]["tags"], (v.seed, v.k, x))

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


class Sensitivity(unittest.TestCase):
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

    def test_no_injury_on_a_minor(self) -> None:
        """S8."""
        for v in LE:
            for name, n in v.graph["nodes"].items():
                for e in n.get("effects", []):
                    if e["do"] == "health_change" and e["min"] < 0:
                        rid = v.plan["roles"][0 if e["role"] == "first" else 1]
                        self.assertFalse(mx.minor_role(BANK, rid), (v.seed, v.k))

    def test_no_experiment_on_an_animal(self) -> None:
        """S9."""
        for v in LE:
            if mx.animal_seed(BANK.seed[v.seed]):
                self.assertFalse(any(i in mx.ANIMAL_NO for _k, i in v.plan["choices"]), (v.seed, v.k))

    def test_named_cases(self) -> None:
        """The rules on the cases they were written for."""
        # S2: a joke never hurts
        self.assertFalse(mx.arc_ok_after(BANK, "choice", "le_cs_cel_odd_a", "le_arc_bad_05"))
        self.assertFalse(mx.arc_ok_after(BANK, "approach", "le_app_play_02", "le_arc_bad_04"))
        self.assertTrue(mx.arc_ok_after(BANK, "choice", "le_cs_cel_odd_a", "le_arc_good_08"))
        # S3: a trial never injures or kills
        self.assertFalse(mx.arc_ok_after(BANK, "approach", "le_app_act_01", "le_arc_bad_05"))
        self.assertFalse(mx.arc_ok_after(BANK, "approach", "le_app_act_07", "le_arc_rare_02"))
        # S4: a firm boundary never drives anyone away
        self.assertFalse(mx.arc_ok_after(BANK, "approach", "le_app_relate_05", "le_arc_rare_01"))
        # S1: an insecure villager is never the one a blame outcome could point at
        seed = BANK.seed["le_odd_09"]
        self.assertFalse(mx.personality_ok(BANK, seed, "le_role_cook", "le_pers_insecure", True))
        # S5: believers are never called superstitious
        self.assertFalse(mx.personality_ok(BANK, BANK.seed["le_bel_01"], "le_role_cook", "le_pers_superstitious", False))
        # S7: a love letter never casts a minor
        self.assertFalse(mx.possible_pair(BANK, BANK.seed["le_fam_05"], "le_role_cook", "le_role_teenager"))
        # S8: no injury on a child
        self.assertFalse(mx.cast_ok(BANK, "le_arc_bad_05", "le_role_child", "le_role_cook"))
        self.assertTrue(mx.cast_ok(BANK, "le_arc_bad_05", "le_role_cook", "le_role_child"))

    def test_rules_documented(self) -> None:
        doc = mx.DOC.read_text(encoding="utf-8")
        for rule, text in mx.SENSITIVITY_RULES.items():
            self.assertIn(f"| {rule} | {text} |", doc)


if __name__ == "__main__":
    unittest.main()
