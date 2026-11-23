"""The v1.35.98 lines audit: event data that named the wrong villager or drew a line that could not follow.

* The Cooking Contest (data/event_collection/original/vv2_cooking_contest.json, the owner's event; only conditions
  change): the judges' praise {O} items that describe Cook 1's own choice ("devotion to family recipes" after "stick",
  "willingness to improvise" after "new") are never drawn when Cook 2 wins (win2), and Cook 1's gracious loser lines
  in Q2 ("stands proud at having gotten second place", "congratulates them for the win" ...) never follow a page
  where Cook 1 cheated, confessed, ruined the dish, was disqualified or poisoned the judges.  Both are checked on
  every path the graph can take (a walk of the whole graph, the visited set at each page).
* A kill on a page that tells of a peaceful death ("dies peacefully in (his/her) sleep") never says "suffers fatal
  injuries" (scripts/outcome_effects.py PEACEFUL), on every collection file.
* Pronouns in the GO events (the balance and rewritten events, scripts/go_events/gen_go.py): a sentence whose subject
  is another villager's name ("(fisher) shakes (subject.his/her) head") does not use the main villager's pronoun,
  unless the sentence is listed as read and right (ALLOWED: "(friend) grabs for (subject.him/her)").  The fixes
  themselves (scripts/go_events/go_role_fixes.py) are pinned against the written files.

Static: no game, no save.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "scripts" / "go_events")]

import go_role_fixes as fixes  # noqa: E402
import outcome_effects as oe  # noqa: E402

COLLECTION = ROOT / "data" / "event_collection"
GO_DIRS = ("balance", "rewrites")

# ---- The Cooking Contest ---------------------------------------------------------------------------------------------

COOK1_CHOICE_ITEMS = ("willingness to improvise", "devotion to family recipes", "sticking to well-known dishes",
                      "willingness to try flavor combinations that aren't normally paired together",
                      "willingness to think outside the box")
GRACIOUS_LOSER = ("vows to beat (cook2.him/her) next year", "congratulates them for the win", "pats them on the back",
                  "gives them a thumbs up", "celebrates with (cook2.him/her) in joy", "claps for them",
                  "stands proud at having gotten second place", "hugs (cook2.him/her)", "tearfully concedes",
                  "humbly takes the loss in stride", "pretends (cook1.he/she) did not lose",
                  "gives words of encouragement", "is thankful (cook1.he/she) got to compete with (cook2.him/her)",
                  "challenges (cook2.him/her) to another cook-off soon!")
# The pages after which Cook 1 did not lose a fair contest: sabotage caught (sab1, sab2), Cook 1's own sabotage
# (end_f), confession (a1_h), disqualification (d_out, a1_25_dq), and the judges handing Cook 2 the win after Cook 1
# ruined the dish on purpose (a1_24_win) -- unless the reason was that Cook 1 "secretly wanted (cook2) to win" (a1_18_2).
# An honest accident (f14: the judges fell ill from Cook 1's dish) is a fair loss: every gracious line fits.
NOT_A_FAIR_LOSS = ("sab1", "sab2", "end_f", "a1_h", "d_out", "a1_25_dq")
WATCH = NOT_A_FAIR_LOSS + ("a1_24_win", "a1_18_2", "f14", "a1_i")


def unfair(vis: frozenset) -> bool:
    return bool(vis & set(NOT_A_FAIR_LOSS)) or ("a1_24_win" in vis and "a1_18_2" not in vis)


# Every page that leads straight to win2, and Cook 1's two first choices
ROADS = ("d_out", "a1_25_dq", "f11_pretend", "a1_17_1", "a1_17_2b", "a1_17_3a", "a1_17_4a", "a1_24_win", "f14_other",
         "six1", "f15_other", "one2_2", "one3_2", "one4_2", "one5_2", "win_either", "v13a_a2", "sab1", "stick", "new")


def _holds(c, visited: frozenset) -> bool:
    """A pool item's or a child's condition, with every role bound (the walk is over the graph's shape)."""
    if c is None:
        return True
    (op, arg), = c.items()
    if op == "visited":
        return arg in visited
    if op == "not":
        return not _holds(arg, visited)
    if op == "all":
        return all(_holds(x, visited) for x in arg)
    if op == "any":
        return any(_holds(x, visited) for x in arg)
    return True          # role / game / patch: either way; the walk takes both


def _next(node: dict, visited: frozenset) -> list[str]:
    out = []
    for c in node.get("children") or []:
        if _holds(c.get("if"), visited) and _holds(c.get("guard"), visited):
            out.append(c["next"])
        elif c.get("else"):
            out.append(c["else"])
    out += [c["next"] for c in node.get("choices") or [] if c.get("next")]
    return out


def _refs(c, out: set) -> set:
    if isinstance(c, dict):
        for k, v in c.items():
            if k == "visited":
                out.add(v)
            else:
                _refs(v, out)
    elif isinstance(c, list):
        for x in c:
            _refs(x, out)
    return out


def walk(doc: dict, at: str, watch=()) -> list[frozenset]:
    """Every visited set the graph can have on reaching page `at` (that page included), kept to the pages a condition
    reads (and `watch`): a walk of (page, visited) -- the visited set is all any condition reads, so the walk covers
    every path the game can take."""
    nodes = doc["nodes"]
    keep = _refs(doc["nodes"], set()) | _refs(doc["pools"], set()) | {at, *watch}
    seen, found = set(), set()
    todo = deque([(doc["start"], frozenset({doc["start"]} & keep))])
    while todo:
        nid, vis = todo.popleft()
        if (nid, vis) in seen:
            continue
        seen.add((nid, vis))
        if nid == at:
            found.add(vis)
        for nxt in _next(nodes[nid], vis):
            todo.append((nxt, vis | ({nxt} & keep)))
    return sorted(found, key=sorted)


def eligible(doc: dict, pool: str, visited: frozenset) -> list[str]:
    return [it["text"] for it in doc["pools"][pool]["items"] if _holds(it.get("if"), visited)]


class CookingContest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads((COLLECTION / "original" / "vv2_cooking_contest.json").read_text(encoding="utf-8"))
        cls.win2 = walk(cls.doc, "win2", ROADS + WATCH)
        cls.win1 = walk(cls.doc, "win1", WATCH)

    def test_the_walk_reaches_every_road_to_win2(self):
        reached = set().union(*self.win2)
        for nid in ROADS:
            self.assertIn(nid, reached, nid)

    def test_win2_never_praises_cook1s_choice(self):
        for vis in self.win2:
            got = set(eligible(self.doc, "O", vis)) & set(COOK1_CHOICE_ITEMS)
            self.assertFalse(got, f"win2 after {sorted(vis & {'stick', 'new'})}: {sorted(got)}")

    def test_cook1s_choice_is_still_praised_when_cook1_wins(self):
        stick = [v for v in self.win1 if "stick" in v]
        new = [v for v in self.win1 if "new" in v]
        self.assertTrue(stick and new)
        self.assertIn("devotion to family recipes", eligible(self.doc, "O", stick[0]))
        self.assertIn("willingness to improvise", eligible(self.doc, "O", new[0]))

    def test_no_gracious_second_place_after_cheating_or_disqualification(self):
        for item in GRACIOUS_LOSER:
            self.assertIn(item, [it["text"] for it in self.doc["pools"]["Q2"]["items"]])
        bad = []
        for vis in self.win2:
            if not unfair(vis):
                continue
            got = set(eligible(self.doc, "Q2", vis)) & set(GRACIOUS_LOSER)
            if got:
                bad.append((sorted(vis & set(WATCH)), sorted(got)[:3]))
        self.assertFalse(bad, bad[:5])

    def test_a_fair_loss_keeps_every_line(self):
        """Every fair road to win2 (an honest accident, f14; Cook 1 wanting Cook 2 to win, a1_18_2; a plain loss)
        keeps all the gracious lines."""
        fair = [v for v in self.win2 if not unfair(v) and "seven" not in v]
        self.assertTrue(any("f14" in v for v in fair) and any("a1_18_2" in v for v in fair))
        for vis in fair:
            self.assertTrue(set(GRACIOUS_LOSER) <= set(eligible(self.doc, "Q2", vis)), sorted(vis & set(WATCH)))


# ---- A peaceful death never "suffers fatal injuries" ----------------------------------------------------------------

def _event_files():
    for p in sorted(COLLECTION.rglob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(d, dict) and isinstance(d.get("nodes"), dict):
            yield p, d


class PeacefulDeath(unittest.TestCase):
    def test_the_rule(self):
        page = {"text": "That night (subject) dies peacefully in (subject.his/her) sleep, by the knot that never "
                        "slips."}
        self.assertIsNone(oe.wording(page, {"do": "kill"}))
        self.assertEqual(oe.wording({"text": "(Name) slips on the rocks and falls."}, {"do": "kill"}), "injuries")
        # a violent death that mentions sleep keeps its injury line
        violent = {"text": "In the night the old tree falls on the hut, crushing (name) in (his/her) sleep."}
        self.assertEqual(oe.wording(violent, {"do": "kill"}), "injuries")
        self.assertEqual(oe.wording({"text": "(Name) was sleeping peacefully when the cliff collapsed."},
                                    {"do": "kill"}), "injuries")

    def test_no_file_says_fatal_injuries_for_a_peaceful_death(self):
        bad = []
        for p, d in _event_files():
            for nid, n in d["nodes"].items():
                words = " ".join([n.get("text") or ""] + [v.get("text") or "" for v in n.get("variants") or []])
                for e in n.get("effects") or []:
                    if e.get("do") == "kill" and e.get("line") == "injuries" and oe.PEACEFUL.search(words):
                        bad.append(f"{p.relative_to(COLLECTION)} {nid}")
        self.assertFalse(bad, bad)

    def test_the_two_pages(self):
        for rel, nid in (("balance/bal/b317_visitor_door.json", "c1o2"), ("rewrites/rw_s/s030_fisher_tide.json", "c1o1")):
            d = json.loads((COLLECTION / rel).read_text(encoding="utf-8"))
            kills = [e for e in d["nodes"][nid]["effects"] if e["do"] == "kill"]
            self.assertEqual(len(kills), 1)
            self.assertNotIn("line", kills[0], rel)


# ---- Pronouns of the GO events ---------------------------------------------------------------------------------------

PH = re.compile(r"\((\w+)(\.[^()]*)?\)")
SENT = re.compile(r"(?<=[.!?])\s+|\n")
# A sentence that starts with another villager's name and still says the main villager's pronoun, read and right:
# the pronoun is the main villager's (the object of the sentence: "(friend) grabs for (subject.him/her)"), or is about
# someone the event does not cast (a remembered ancestor), where no role name can say it.  (file stem, node, the
# sentence's start)
ALLOWED = {
    ("b026_sleepwalker", "c1o2", "(friend) grabs for (subject.him/her)"),
    ("b156_old_well", "c1o2", "(child) brings (subject.him/her) a cup"),
    ("b165_salve_clay_jar", "ask", "(healer), the oldest healer, says it was made by the healer before"),
    ("b186_dolphin_waits", "ask", "(fisher) says (subject.his/her) grandmother said a lot of things"),
    ("b210_grandchild_wish", "c1", "(child) scatters the dried flowers over (subject.his/her) head"),
    ("b225_fishing_contest", "c1o1", "(fisher) shakes (subject.his/her) hand"),
    ("b249_grandchild_spell", "c1", "(child) waves the bundle around (subject.his/her) head"),
    ("b287_fever_burns_away", "c2o2", "(healer) sits with (subject.him/her) until dawn, holding (subject.his/her) hand"),
    ("my115_stranger_season", "c2o1", "(grave2) used to sing me awake"),
    ("new133_fisher_hands", "c3o2", "(young) sits with (subject.him/her) while (subject.he/she) does"),
    ("b244_fisher_tide", "c1o2", "(young) carves (subject.his/her) name"),
    ("b258_game_went_too_far", "c2o2", "(friend) stands up, shakes (subject.his/her) hand"),
    ("b259_elder_wandered", "ask", "(friend) found (subject.his/her) basket"),
    ("b276_swamp_fever", "c1o2", "(sick) plants a fever tree beside (subject.his/her) grave"),
    ("b290_sleepwalker", "ask", "(friend) followed (subject.him/her) last night"),
    ("my072_jar_two_sunrises", "c2o2", "(storyteller), the village storyteller, grabs the jar"),
    ("my102_god_garden", "c4o1", "(friend) is starting to think (subject.he/she) might be right"),
    ("new169_old_couple_walk", "c1o1", "(friend) is quiet for a moment, then takes (subject.his/her) arm"),
    ("s078_second_name_day", "c1", "(elder), the oldest elder, lifts the feather staff high over (subject.his/her) head"),
}


def go_files():
    for sub in GO_DIRS:
        for p in sorted((COLLECTION / sub).glob("*/*.json")):
            yield p, json.loads(p.read_text(encoding="utf-8"))


def pronoun_suspects(doc: dict, stem: str) -> list[tuple[str, str, str]]:
    """(stem, node, sentence) for each sentence that opens with another villager's name, never names the main
    villager, and uses the main villager's he/she, his/her or himself/herself."""
    roles = doc.get("roles") or {}
    main = next(iter(roles), None)
    others = {r for r, v in roles.items() if r != main and v.get("kind") == "villager"}
    out = []
    if not others:
        return out
    for nid, n in doc["nodes"].items():
        for s in SENT.split(n.get("text") or ""):
            s = s.strip()
            m = PH.match(s)
            if not m or m.group(1).lower() not in others or m.group(2):
                continue
            names = {x.group(1).lower() for x in PH.finditer(s) if not x.group(2)}
            # "him/her" is most often the other villager acting on the main one ("(friend) carries (subject.him/her)
            # home"); he/she, his/her and himself/herself are what a sentence says of its own subject
            prons = {x.group(1).lower() for x in PH.finditer(s)
                     if x.group(2) and x.group(2).lower() in (".he/she", ".his/her", ".himself/herself")}
            if main not in names and main in prons:
                out.append((stem, nid, s))
    return out


def allowed(stem: str, nid: str, sentence: str, table=ALLOWED) -> bool:
    return any(stem == a and nid == b and sentence.startswith(c) for a, b, c in table)


# A sentence that names no villager, says the main villager's he/she / his/her / himself/herself, and comes after a
# sentence whose subject is another villager (with the main villager not named since), read and right or about
# someone the event does not cast.
ALLOWED_AFTER = {
    ("b186_dolphin_waits", "ask", "(subject.His/her) grandmother said dolphins"),
    ("b210_grandchild_wish", "c1o1", "The storyteller sits down heavily"),
    ("b258_game_went_too_far", "c2o2", "(subject.He/She) gives the bag of stones"),
    ("b261_dream_sharing_tea", "c2o1", '"Your knees,"'),
    ("b268_mask_carver_faces", "c2o2", "A few days later a fisher says"),
    ("my058_beggar_request", "c3o1", '"So many kind people,"'),
    ("my067_hidden_companion", "c2o2", "(subject.He/she) has never been inside the elders' hut"),
    ("my069_watcher_cliff", "c3o1", "My grandmother said (subject.he/she) never missed"),
    ("my071_visitor_final", "c3o2", "(subject.He/she) wanders through every few years"),
}
SUBJECT_FORMS = (".he/she", ".his/her", ".himself/herself")


def after_another_suspects(doc: dict, stem: str) -> list[tuple[str, str, str]]:
    roles = doc.get("roles") or {}
    main = next(iter(roles), None)
    others = {r for r, v in roles.items() if r != main and v.get("kind") == "villager"}
    out = []
    if not others:
        return out
    for nid, n in doc["nodes"].items():
        prev_other = None
        for s in (x.strip() for x in SENT.split(n.get("text") or "")):
            if not s:
                continue
            names = {m.group(1).lower() for m in PH.finditer(s) if not m.group(2)}
            prons = {m.group(1).lower() for m in PH.finditer(s) if m.group(2) and m.group(2).lower() in SUBJECT_FORMS}
            lead = PH.match(s)
            if prev_other and main in prons and not names & (others | {main}):
                out.append((stem, nid, s))
            if lead and lead.group(1).lower() in others and (lead.group(2) or main not in names):
                prev_other = lead.group(1).lower()
            elif names & (others | {main}) or (lead and lead.group(1).lower() == main and main in prons):
                prev_other = None
    return out


# Three more shapes, in events that cast two or more villagers:
#  A  the main villager's he/she / his/her acting on the main villager by name: "(subject.He/She) takes (subject) by
#     both shoulders" -- the pronoun is someone else's;
#  B  the main villager by name, then "stop / tell / help / with / to / beside / thanks" the main villager's him/her:
#     "(subject) sits with (subject.him/her) until morning";
#  C  a sentence that opens with a word or two before another villager's name ("Before (friend) can start, (name3) ...
#     in (subject.his/her) life"), with the main villager not named.
# Each hit is listed below as read and right, or about someone the event does not cast.  (stem, node, words of the hit)
SHAPE_A = re.compile(r"\(subject\.(?:he/she|his/her)\)[^.!?\"]{0,40}?\(subject\)(?!')", re.I)
SHAPE_B = re.compile(r"\(subject\)[^.!?\"]{0,30}?\b(?:stop|tell|help|with|to|beside|thanks)\s\(subject\.him/her\)")
LEAD_WORDS = re.compile(r"^(?:[A-Z][a-z]+,?\s+){1,3}\((\w+)\)")
ALLOWED_SHAPES = {
    ("b017_child_followed", "c2o1", "(subject.his/her) name to check, (subject)"),
    ("b026_sleepwalker", "c2o2", "where (subject.he/she) was standing, (subject)"),
    ("b137_red_fish_supper", "ask", "But (fisher)'s grandmother, (subject.he/she) remembers"),
    ("b142_fig_fruits_once", "c2o1", "tell (subject.him/her) to expect"),
    ("b174_falling_star", "c1o2", "settle beside (subject.him/her)"),
    ("b192_burning_fever", "c2", "sit with (subject.him/her) all night"),
    ("b194_canoe_shed_baby", "c1o1", "will show it to (subject.him/her)"),
    ("b199_chief_bad_day", "c1o2", "laughs so hard (subject.he/she) has to sit down, and says (subject)"),
    ("b203_sleepy_spell", "c2o1", "just tell (subject.him/her) why"),
    ("b256_traveller", "ask", "(subject.He/She) looks straight at (subject)"),
    ("b270_festival_floating", "c1o2", "for (subject.his/her) own family, (subject)"),
    ("b287_fever_burns_away", "c1o1", "asks how (subject.he/she) feels, (subject)"),
    ("b290_sleepwalker", "ask", "Should (friend) wake (subject.him/her)"),
    ("b310_carver_masks", "c2o1", "(subject.his/her) face has changed: still (subject)"),
    ("b320_sister_hills", "c2o2", "(subject.He/She) sits by (subject)"),
    ("my003_second_footprint", "c3o2", "(subject.he/she) spots (subject)"),
    ("my017_woman_last_house", "c1", "courage (subject.he/she) has, (subject)"),
    ("my058_beggar_request", "c2o1", "(subject.He/She) tells (subject)"),
    ("my062_flower_bloomed", "ask", "On (subject.his/her) morning walk"),
    ("my063_bargain_hidden", "c3o1", "Then (subject.he/she) tells (subject) the way"),
    ("my072_jar_two_sunrises", "c3o2", "(subject.He/she) and (subject) talk until sunset"),
    ("my073_dreamer_stranger", "c4o2", "(subject.He/she) just looks at (subject)"),
    ("my073_dreamer_stranger", "c4o2", "as though (subject.he/she) knows (subject)"),
    ("my075_stone_boat", "c4o1", "(subject.He/she) shows (subject)"),
    ("my091_unfinished", "c3o1", "(subject.He/she) looks at (subject) thoughtfully"),
    ("my098_stranger_funeral", "c1o1", "(subject.He/she) bows to (subject)"),
    ("my100_stranger_two", "c3o2", "where (subject.he/she) sat, (subject)"),
    ("my111_wandering", "ask", "(subject.he/she) is gone up the road before (subject)"),
    ("new114_council_empty", "c1o1", "Once (subject.he/she) understands, (subject)"),
    ("new121_scientist", "ask", "(subject.his/her) family's hut, little (subject)"),
    ("new124_teacher", "c1o1", "thanks (subject.him/her) in front of everyone"),
    ("new126_child_feared", "c3", "sits with (subject.him/her) in the doorway"),
    ("new140_bench_sun", "c1o2", "With (young) on one side"),
    ("new162_farmer_shy", "ask", "looks (subject.his/her) way, (subject)"),
    ("new181_apprentice", "c3", "beside (subject.him/her)"),
    ("new182_overworked", "ask", "(subject.his/her) table, (subject)"),
    ("new186_misunderstood", "c1", "The head builder clears (subject.his/her) throat"),
    ("new189_night_shift", "c1o1", "(subject.his/her) mat and looking at the walls, (subject)"),
    ("new190_worker_said", "ask", "listen to (subject.him/her)"),
    ("s030_fisher_tide", "c1o2", "happened to (subject.him/her) three times"),
    ("s090_baby_ferns", "c2o1", "(subject.his/her) heartbeat, and (subject)"),
}


def shape_suspects(doc: dict, stem: str) -> list[tuple[str, str, str]]:
    roles = doc.get("roles") or {}
    villagers = [r for r, v in roles.items() if v.get("kind") == "villager"]
    if len(villagers) < 2:
        return []
    main = next(iter(roles))
    others = {r for r in villagers if r != main}
    out = []
    for nid, n in doc["nodes"].items():
        t = n.get("text") or ""
        for rx in (SHAPE_A, SHAPE_B):
            out += [(stem, nid, t[max(0, m.start() - 60):m.end() + 40]) for m in rx.finditer(t)]
        for s in (x.strip() for x in SENT.split(t)):
            m = LEAD_WORDS.match(s)
            if not m or m.group(1).lower() not in others:
                continue
            names = {x.group(1).lower() for x in PH.finditer(s) if not x.group(2)}
            prons = {x.group(1).lower() for x in PH.finditer(s) if x.group(2) and x.group(2).lower() in SUBJECT_FORMS}
            if main not in names and main in prons:
                out.append((stem, nid, s))
    return out


def shape_allowed(stem: str, nid: str, words: str) -> bool:
    return any(stem == a and nid == b and c in words for a, b, c in ALLOWED_SHAPES)


class GoPronouns(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = {p.stem: d for p, d in go_files()}

    def test_no_main_pronoun_in_the_other_shapes(self):
        bad = []
        for stem, d in self.docs.items():
            bad += [x for x in shape_suspects(d, stem) if not shape_allowed(*x)]
        self.assertFalse(bad, "\n".join(f"{a} {b}: {c[-140:]}" for a, b, c in bad[:40]))

    def test_every_allowed_shape_is_still_there(self):
        found = {(a, b) for stem, d in self.docs.items() for a, b, c in shape_suspects(d, stem) if shape_allowed(a, b, c)}
        self.assertEqual({(a, b) for a, b, _ in ALLOWED_SHAPES} - found, set())

    def test_no_main_pronoun_in_another_villagers_sentence(self):
        bad = []
        for stem, d in self.docs.items():
            bad += [x for x in pronoun_suspects(d, stem) if not allowed(*x)]
        self.assertFalse(bad, "\n".join(f"{a} {b}: {c[:120]}" for a, b, c in bad[:30]))

    def test_every_allowed_sentence_is_still_there(self):
        found = {(a, b) for stem, d in self.docs.items() for a, b, c in pronoun_suspects(d, stem) if allowed(a, b, c)}
        self.assertEqual(found, {(a, b) for a, b, _ in ALLOWED})
        found = {(a, b) for stem, d in self.docs.items() for a, b, c in after_another_suspects(d, stem)
                 if allowed(a, b, c, ALLOWED_AFTER)}
        self.assertEqual(found, {(a, b) for a, b, _ in ALLOWED_AFTER})

    def test_no_main_pronoun_right_after_another_villagers_sentence(self):
        bad = []
        for stem, d in self.docs.items():
            bad += [x for x in after_another_suspects(d, stem) if not allowed(*x, ALLOWED_AFTER)]
        self.assertFalse(bad, "\n".join(f"{a} {b}: {c[:120]}" for a, b, c in bad[:30]))

    def test_the_pronoun_fixes_are_in_the_files(self):
        for (stem, nid), pairs in fixes.PRONOUNS.items():
            text = self.docs[stem]["nodes"][nid]["text"]
            for snippet, role in pairs:
                self.assertIn(snippet.replace("(subject.", f"({role}."), text, (stem, nid))
                self.assertIn(role, self.docs[stem]["roles"], (stem, role))

    def test_the_effect_fixes_are_in_the_files(self):
        for (stem, nid), moves in fixes.EFFECTS.items():
            nodes = self.docs[stem]["nodes"]
            mine = [e for k, n in nodes.items() if k == nid or k.startswith(nid + "_") for e in n.get("effects") or []]
            for do, old, new in moves:
                if new == fixes.ALL:
                    self.assertTrue(any(e["do"] == do and e.get("target") == {"all": True} and "role" not in e
                                        for e in mine), (stem, nid, do))
                else:
                    self.assertTrue(any(e["do"] == do and e.get("role") == new for e in mine), (stem, nid, do))
                self.assertFalse(any(e["do"] == do and e.get("role") == old for e in mine), (stem, nid, do, old))

    def test_the_named_pages(self):
        """The audit's own examples, page by page."""
        d = self.docs
        n = d["s026_chief_bad_idea"]["nodes"]["c2o2"]["effects"]
        self.assertEqual({(e["do"], e["role"]) for e in n}, {("preference", "subject"), ("skill", "subject")})
        n = d["s071_robe_shrank"]["nodes"]["c1o1"]["effects"]
        self.assertEqual([(e["do"], e["role"]) for e in n], [("appearance", "subject")])
        n = d["s037_coughing_season"]["nodes"]["c2o2"]
        self.assertNotIn("(subject.", n["text"])
        self.assertEqual({e["role"] for e in n["effects"]}, {"elder"})
        n = d["b334_fever_ward"]["nodes"]["c2o2"]
        self.assertNotIn("(subject.", n["text"])
        self.assertIn("buries (sick.him/her)", n["text"])
        self.assertEqual([e.get("role") for e in n["effects"] if e["do"] == "kill"], ["sick"])
        self.assertFalse([e for e in n["effects"] if e["do"] == "cure" and e.get("role")])


if __name__ == "__main__":
    unittest.main()
