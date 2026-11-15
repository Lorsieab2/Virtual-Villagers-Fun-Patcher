"""Living Event Engine: data/living_events/bank.json against the frozen owner source.

Pinned here:
  * the source in the repo is the owner's final file (SHA-256 in data/living_events/SOURCE.sha256);
  * the bank's counts equal the source's: 120 seeds / 30 roles / 24 personalities / 15 lenses / 34 approaches /
    38 archetypes / 60 MIX / 95 MC situations with 760 outcomes / 35 MJ seeds;
  * every text field is the owner's text on its `src` line, and every MIX reproduces its source lines exactly;
  * ids are unique and namespaced (le_*, mc_*, mj_*), every reference resolves;
  * the compatibility table (owner decision 2026-11-15) is exactly what its rules derive, the owner's MIX examples that
    break it are listed, and `combination_problems` refuses a combination the table forbids;
  * MC effects stay off strangers; MJ is held with no outcomes and no effects.

`combination_problems(bank, combo)` is the check a generator's output must pass (see living-events.md).
"""
from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANK_PATH = ROOT / "data" / "living_events" / "bank.json"
SHA_PATH = ROOT / "data" / "living_events" / "SOURCE.sha256"
SRC_PATH = ROOT / "docs" / "more-island-events" / "Isola_ALL_IN_ONE_Modular_Living_Event_Engine.txt"

BANK = json.loads(BANK_PATH.read_text(encoding="utf-8"))
LINES = SRC_PATH.read_bytes().decode("utf-8").split("\n")


def line(src: str) -> str:
    m = re.fullmatch(r"L(\d+)", src)
    assert m, src
    return LINES[int(m.group(1)) - 1]


def walk(o, path=""):
    if isinstance(o, dict):
        yield path, o
        for k, v in o.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, f"{path}[{i}]")


def index(bank: dict) -> dict:
    out = {}
    for _, d in walk(bank):
        if isinstance(d.get("id"), str):
            out.setdefault(d["id"], d)
    return out


def combination_problems(bank: dict, combo: dict) -> list[str]:
    """combo = {"seed": id, "first": {"role", "personality"}, "second": {...}, "choices": [ids],
    "archetypes": [ids]}: every rule of bank["compat"] the combination breaks."""
    ex = bank["compat"]["exclusions"]
    s = combo["seed"]
    out = []
    sides = [combo["first"], combo["second"]]
    if sides[0]["role"] == sides[1]["role"] and sides[0]["personality"] == sides[1]["personality"]:
        out.append("the two villagers are described identically")
    for side in sides:
        if side["role"] in ex["seed_role"].get(s, []):
            out.append(f"seed {s} x role {side['role']}")
        if side["personality"] in ex["role_personality"].get(side["role"], []):
            out.append(f"role {side['role']} x personality {side['personality']}")
    for c in combo["choices"]:
        key = "seed_approach" if c.startswith("le_app_") else "seed_choice"
        if c in ex[key].get(s, []):
            out.append(f"seed {s} x {c}")
    for a in combo["archetypes"]:
        if a in ex["seed_archetype"].get(s, []):
            out.append(f"seed {s} x archetype {a}")
        for side in sides:
            if a in ex["role_archetype"].get(side["role"], []):
                out.append(f"role {side['role']} x archetype {a}")
    return sorted(set(out))


def mix_combo(mx: dict) -> dict:
    return {"seed": mx["seed"], "first": mx["first"], "second": mx["second"],
            "choices": [c["choice"] for c in mx["choices"]],
            "archetypes": [o["archetype"] for pair in mx["outcomes"] for o in pair]}


class SourceTest(unittest.TestCase):
    def test_frozen_source_hash(self):
        want, path = SHA_PATH.read_text(encoding="utf-8").split()
        self.assertEqual(path, "docs/more-island-events/Isola_ALL_IN_ONE_Modular_Living_Event_Engine.txt")
        self.assertEqual(hashlib.sha256(SRC_PATH.read_bytes()).hexdigest(), want)
        self.assertEqual((len(LINES), LINES[-1]), (26868, ""))   # 26,867 lines, the last one ended by "\n"

    def test_bank_is_lf_utf8(self):
        raw = BANK_PATH.read_bytes()
        self.assertNotIn(b"\r", raw)
        self.assertTrue(raw.endswith(b"\n"))


class CountTest(unittest.TestCase):
    def count(self, lo, hi, pattern):
        return sum(1 for n in range(lo, hi + 1) if re.match(pattern, LINES[n - 1]))

    def test_counts_against_source(self):
        b = BANK
        src_counts = {
            "seeds": self.count(23836, 23978, r"^  [A-Z]{3}-\d\d: "),
            "roles": len(line("L23980").split(": ", 1)[1].split("; ")),
            "personalities": len(line("L23981").split(": ", 1)[1].split("; ")),
            "approaches": self.count(23983, 24025, r"^ - "),
            "archetypes": self.count(24027, 24071, r"^ - "),
            "mix": self.count(24091, 25113, r"^MIX-\d{3} — "),
            "mc_situations": self.count(25134, 25664, r"^\[[A-Z]{3}-\d\d\] SETUP: "),
            "mc_outcomes": self.count(25667, 26616, r"^  [A-D][12]\. "),
            "mj_seeds": self.count(26617, 26867, r"^\[[A-Z]{3}-\d\d\] "),
        }
        self.assertEqual(src_counts, {"seeds": 120, "roles": 30, "personalities": 24, "approaches": 34,
                                      "archetypes": 38, "mix": 60, "mc_situations": 95, "mc_outcomes": 760,
                                      "mj_seeds": 35})
        have = {
            "seeds": len(b["seeds"]), "roles": len(b["roles"]), "personalities": len(b["personalities"]),
            "approaches": len(b["approaches"]), "archetypes": len(b["archetypes"]), "mix": len(b["mix"]),
            "mc_situations": len(b["mc"]["situations"]),
            "mc_outcomes": sum(len(a["outcomes"]) for m in b["mc"]["situations"] for a in m["approaches"]),
            "mj_seeds": len(b["mj"]["seeds"]),
        }
        self.assertEqual(have, src_counts)
        self.assertEqual(len(b["lenses"]), 15)
        self.assertEqual(len(b["categories"]), 12)
        self.assertEqual(len(b["choice_sets"]), 7)
        self.assertEqual(len(b["choices"]), 28)
        self.assertEqual([len(v) for v in b["mc"]["pools"].values()], [20, 23, 15])
        for k, v in have.items():
            self.assertEqual(b["counts"][k], v, k)

    def test_families_and_groups(self):
        fam = {}
        for a in BANK["approaches"]:
            fam[a["family"]] = fam.get(a["family"], 0) + 1
        self.assertEqual(fam, {"consult": 7, "act": 8, "relate": 8, "withdraw": 6, "play": 5})
        grp = {}
        for a in BANK["archetypes"]:
            grp[a["group"]] = grp.get(a["group"], 0) + 1
        self.assertEqual(grp, {"good": 10, "mixed": 10, "bad": 10, "rare": 8})
        per = {}
        for s in BANK["seeds"]:
            per[s["category"]] = per.get(s["category"], 0) + 1
        self.assertEqual(set(per.values()), {10})
        mc = {}
        for s in BANK["mc"]["situations"]:
            mc[s["category"]] = mc.get(s["category"], 0) + 1
        self.assertEqual(mc, {"mc_cat_isl": 20, "mc_cat_dis": 15, "mc_cat_aft": 15, "mc_cat_los": 15,
                              "mc_cat_tra": 15, "mc_cat_bel": 15})


class TextTest(unittest.TestCase):
    def test_every_text_is_on_its_src_line(self):
        n = 0
        for path, d in walk(BANK):
            if "text" in d and "src" in d:
                # A sensitivity edit (living-events.md section 7) keeps the owner's words as source_text.
                self.assertIn(d.get("source_text", d["text"]), line(d["src"]), path)
                n += 1
        self.assertGreater(n, 120 + 30 + 24 + 15 + 34 + 38 + 28 + 95 + 380 + 760 + 35 + 140)

    def test_exact_line_shapes(self):
        for s in BANK["seeds"]:
            self.assertEqual(line(s["src"]), f"  {s['code']}: {s.get('source_text', s['text'])}")
        for a in BANK["approaches"] + BANK["archetypes"]:
            self.assertEqual(line(a["src"]), f" - {a['text']}")
        for c in BANK["categories"]:
            self.assertEqual(line(c["src"]), c["heading"])
        for m in BANK["mc"]["situations"]:
            self.assertEqual(line(m["src"]), f"[{m['code']}] SETUP: {m.get('source_text', m['text'])}")
            self.assertEqual(line(m["outcomes_src"]), f"[{m['code']}]")
            for a in m["approaches"]:
                self.assertEqual(line(a["src"]), f"  {a['letter']}. {a['text']}")
                for k, o in enumerate(a["outcomes"], 1):
                    self.assertEqual(line(o["src"]), f"  {a['letter']}{k}. {o['text']}")
        for m in BANK["mj"]["seeds"]:
            self.assertEqual(line(m["title_src"]), f"[{m['code']}] {m['title']}")
            self.assertEqual(line(m["src"]), f"SETUP: {m['text']}")
            for a in m["approaches"]:
                self.assertEqual(line(a["src"]), f"  {a['letter']}. {a['text']}")

    def test_roles_and_personalities(self):
        for r in BANK["roles"]:
            self.assertEqual(r["text"], f"{r['article']} {r['word']}")
        for p in BANK["personalities"]:
            self.assertEqual(p["article"], "an" if p["text"][0] in "aeiou" else "a", p["text"])

    def test_every_mix_reproduces_its_lines(self):
        ix = index(BANK)
        fixed = BANK["frame"]["fixed_text"]
        for mx in BANK["mix"]:
            seed = ix[mx["seed"]]
            pa, ra = ix[mx["first"]["personality"]], ix[mx["first"]["role"]]
            pb, rb = ix[mx["second"]["personality"]], ix[mx["second"]["role"]]
            self.assertEqual(line(mx["setup_src"]),
                             f"SETUP: {seed['text']} A {pa['text']} {ra['text']} and a {pb['text']} {rb['text']} "
                             f"{fixed}", mx["id"])
            self.assertEqual(line(mx["title_src"]), f"{mx['code']} — {seed['text'].rstrip('.').upper()}")
            self.assertTrue(line(mx["seed_src"]).startswith(f"SOURCE SEED: {seed['code']} | LENS: "))
            for k, (c, pair) in enumerate(zip(mx["choices"], mx["outcomes"])):
                letter = "ABCD"[k]
                self.assertEqual(line(c["src"]), f" {letter}. {ix[c['choice']]['text']}", mx["id"])
                for j, o in enumerate(pair, 1):
                    self.assertEqual(line(o["src"]), f"  {letter}{j}. {ix[o['archetype']]['text']}", mx["id"])
                # X1 GOOD, X2 MIXED or BAD (design)
                self.assertEqual(ix[pair[0]["archetype"]]["group"], "good", mx["id"])
                self.assertIn(ix[pair[1]["archetype"]]["group"], ("mixed", "bad"), mx["id"])
            # a MIX uses its seed category's choice set, in order
            cat = ix[seed["category"]]
            self.assertEqual([c["choice"] for c in mx["choices"]], ix[cat["choice_set"]]["choices"], mx["id"])


class IdTest(unittest.TestCase):
    def test_ids_unique_and_namespaced(self):
        seen = {}
        for path, d in walk(BANK):
            i = d.get("id")
            if not isinstance(i, str) or path.startswith(".mc.pools") or path.startswith(".mc.contract"):
                continue
            self.assertNotIn(i, seen, f"{path} repeats {seen.get(i)}")
            seen[i] = path
            want = "mc_" if path.startswith(".mc.") else "mj_" if path.startswith(".mj.") else "le_"
            if not path.startswith(".compat"):
                self.assertTrue(i.startswith(want), (path, i))
        self.assertIn("le_bel_01", seen)
        self.assertIn("mc_bel_01", seen)
        pool_ids = [p["id"] for v in BANK["mc"]["pools"].values() for p in v]
        self.assertEqual(len(pool_ids), len(set(pool_ids)))

    def test_references_resolve(self):
        ix = index(BANK)
        for s in BANK["seeds"]:
            self.assertIn(s["category"], ix)
        for c in BANK["categories"]:
            self.assertIn(c["choice_set"], ix)
        for cs in BANK["choice_sets"]:
            for c in cs["choices"]:
                self.assertEqual(ix[c]["set"], cs["id"])
        for mx in BANK["mix"]:
            for k in (mx["seed"], mx["first"]["role"], mx["first"]["personality"], mx["second"]["role"],
                      mx["second"]["personality"]):
                self.assertIn(k, ix, mx["id"])
        for table in BANK["compat"]["exclusions"].values():
            for k, vs in table.items():
                self.assertIn(k, ix)
                for v in vs:
                    self.assertIn(v, ix)


class EffectTest(unittest.TestCase):
    ALLOWED = {"skill", "mood", "tech", "food", "celebrate", "health_change", "vanish", "kill"}

    def test_archetype_effects(self):
        for a in BANK["archetypes"]:
            for e in a["effects"]:
                self.assertIn(e["do"], self.ALLOWED, a["id"])
                if e["do"] == "kill":
                    self.assertEqual((a["id"], e["role"], e["cause"]), ("le_arc_rare_02", "elder", "unknown"))
                    self.assertIn("needs_elder", a["tags"])
                if e["do"] == "vanish":
                    self.assertEqual(a["id"], "le_arc_rare_01")
            self.assertEqual(a["protection"], "allow" if any(
                e["do"] in ("kill", "vanish", "health_change", "mood") for e in a["effects"]) else "auto")
        # every group keeps at least one effect-free outcome
        for g in ("good", "mixed", "bad", "rare"):
            self.assertTrue(any(not a["effects"] for a in BANK["archetypes"] if a["group"] == g), g)

    def test_mc_effects_follow_the_contract(self):
        for m in BANK["mc"]["situations"]:
            for a in m["approaches"]:
                self.assertEqual(len(a["outcomes"]), 2)
                for o in a["outcomes"]:
                    for e in o["effects"]:
                        self.assertIn(e["do"], self.ALLOWED, o["id"])
                        if "role" in e:
                            self.assertEqual(e["role"], "subject")
                            self.assertEqual(m["subject"]["kind"], "villager", o["id"])
                        if e["do"] in ("food", "tech", "skill"):
                            self.assertEqual(e["size"], "small", o["id"])

    def test_mj_is_held(self):
        self.assertTrue(BANK["mj"]["status"].startswith("held"))
        for m in BANK["mj"]["seeds"]:
            self.assertEqual(m["outcomes_status"], "held")
            self.assertTrue(all(a["outcomes"] == [] for a in m["approaches"]))
        self.assertIn(BANK["mj"]["contract"]["text"], line(BANK["mj"]["contract"]["src"]))
        self.assertTrue(BANK["mc"]["status"].startswith("active"))


class CompatTest(unittest.TestCase):
    def derive(self):
        b = BANK
        tags ={s["id"]: set(s["tags"]) for s in b["seeds"]}
        keymap = {"approaches": "seed_approach", "choices": "seed_choice", "archetypes": "seed_archetype",
                  "roles": "seed_role"}
        ex = {k: {} for k in ("seed_approach", "seed_choice", "seed_archetype", "seed_role", "role_personality",
                              "role_archetype")}
        for r in b["compat"]["seed_rules"]:
            for sid, t in tags.items():
                if sid in r.get("except_seeds", []):
                    continue
                hit = bool(t & set(r["seeds_with_any"])) if "seeds_with_any" in r else r["seeds_without"] not in t
                if hit:
                    for k, v in r["exclude"].items():
                        ex[keymap[k]].setdefault(sid, set()).update(v)
        for r in b["compat"]["role_rules"]:
            for ro in b["roles"]:
                if set(ro["tags"]) & set(r["roles_with_any"]):
                    for k, v in r["exclude"].items():
                        key = "role_archetype" if k == "archetypes" else "role_personality"
                        ex[key].setdefault(ro["id"], set()).update(v)
        for r in b["compat"]["pair_rules"]:
            ex["role_personality"].setdefault(r["role"], set()).update(r["personalities"])
        return {k: {i: sorted(v) for i, v in sorted(d.items())} for k, d in ex.items()}

    def test_table_is_what_the_rules_derive(self):
        self.assertEqual(self.derive(), BANK["compat"]["exclusions"])

    def test_rule_targets_are_tagged(self):
        ix = index(BANK)
        # the owner's examples of what must never pair
        ex = BANK["compat"]["exclusions"]
        chief = next(a["id"] for a in BANK["approaches"] if a["text"] == "Ask the chief to decide")
        magic = next(a["id"] for a in BANK["approaches"] if a["text"].startswith("Try a magical method"))
        for s in BANK["seeds"]:
            t = set(s["tags"])
            if "medical" in t:
                self.assertIn(chief, ex["seed_approach"][s["id"]])
            if "personal" in t:
                self.assertIn(magic, ex["seed_approach"][s["id"]])
            if "adult_only" in t:
                self.assertEqual(ex["seed_role"][s["id"]], ["le_role_child", "le_role_teenager"])
        # everything else is kept (owner decision, 2026-11-15): no seed or role x archetype, no seed x choice exclusion
        self.assertEqual(ex["role_archetype"], {})
        self.assertEqual(ex["seed_archetype"], {})
        self.assertEqual(ex["seed_choice"], {})
        for s in ("le_res_02", "le_res_09", "le_emo_10", "le_fam_02"):
            self.assertIn(s, ix)
            self.assertIn("somber", ix[s]["tags"])
        self.assertEqual({s["id"] for s in BANK["seeds"] if "elder_death_ok" in s["tags"]},
                         {"le_art_03", "le_art_09"})

    def test_owner_example_conflicts_are_listed(self):
        listed = {c["mix"]: c["conflicts"] for c in BANK["compat"]["owner_example_conflicts"]}
        found = {}
        for mx in BANK["mix"]:
            p = combination_problems(BANK, mix_combo(mx))
            if p:
                found[mx["id"]] = p
        self.assertEqual(set(found), set(listed))
        for k in found:
            self.assertEqual(len(found[k]), len(listed[k]), k)

    def test_checker_refuses_forbidden_combinations(self):
        combo = {"seed": "le_fam_06", "first": {"role": "le_role_child", "personality": "le_pers_forgetful"},
                 "second": {"role": "le_role_confident_novice", "personality": "le_pers_confident"},
                 "choices": ["le_app_act_07"], "archetypes": ["le_arc_good_08", "le_arc_rare_01"]}
        p = combination_problems(BANK, combo)
        self.assertTrue(any("x role le_role_child" in x for x in p))
        self.assertTrue(any("personality le_pers_confident" in x for x in p))
        self.assertTrue(any("le_app_act_07" in x for x in p))
        self.assertFalse(any("le_pers_forgetful" in x or "le_arc_good_08" in x or "le_arc_rare_01" in x for x in p))
        ok = {"seed": "le_art_09", "first": {"role": "le_role_storyteller", "personality": "le_pers_curious"},
              "second": {"role": "le_role_elderly_villager", "personality": "le_pers_warm"},
              "choices": ["le_cs_art_per_a"], "archetypes": ["le_arc_good_01", "le_arc_rare_02"]}
        self.assertEqual(combination_problems(BANK, ok), [])

    def test_shape(self):
        b = BANK
        self.assertEqual((b["format"], b["version"]), ("vvfp-living-bank", 1))
        self.assertEqual(b["rare_roll"]["series"], "category")
        self.assertIn("(first)", b["frame"]["shipped_template"])
        for s in b["seeds"]:
            self.assertTrue(set(s["games"]) <= {1, 2, 3, 4, 5} and s["games"])
            if s["vv5_only"]:
                self.assertEqual(s["games"], [5])
            for sub, word in s["chief_words"]:
                self.assertIn(sub, s["text"])
        for r in b["roles"]:
            self.assertIn(r["cast"]["kind"], ("villager", "stranger"))


if __name__ == "__main__":
    unittest.main()
