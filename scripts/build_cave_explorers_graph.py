"""Write data/cie_graphs/the_cave_explorers.json: The Cave Explorers (the owner's island event for A New Home,
2026-11-12) as a branching Custom Island Event -- the Custom Island Event Library's second example, built only from
what the vvfp-cie-graph format (version 2: questions anywhere) can express.

The words are the event's own, from the one source src/vv_cave_explorers.py (the owner's text with the broken
placeholders fixed and the typography in the letters the game's font draws, as cave_text.inc has them); its tokens
become the format's placeholders: {a} (name1), {b} (name2), the screamer / the finder / the one who slips by the
branch that picks them, pronouns by that villager's role, %d the award.  The odds are the event's (KEEP_ENDINGS,
A_ENDINGS, B_FINDS, ...).

What the format cannot say, and how the example says it instead:
  * "only once The Cave puzzle is done" and "at most 5 years apart": no condition for them -- the roles are two
    villagers of 18 or more (Custom Island Events skip a shipped event's natural requirement in any case);
  * the random award sizes (normal, large 2x, huge 3x): a graph's amounts are fixed -- 2,000 tech points or 500 food
    (normal; the Aspiring Adventurer example's amounts), 1,000 food (large), 6,000 tech points (huge), each scaled by
    the Island Events Scale patches as the example's are;
  * the companion asks its next question in the same dialog right after a click; a Custom Island Event shows the
    answer's own page first, so "Explore the Cave" shows "Okay, let's go!..." and then asks "Toldja it'd be worth
    it..." on its own, and "Stay Here" shows the first two sentences before asking "Wait. I don't think...";
  * "Curses schmurses. I'm keeping them." is 35 characters; A New Home's buttons hold 34 in a Custom Island Event
    (the longest stock label), so the button reads without its full stop.

    python scripts/build_cave_explorers_graph.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_cave_explorers as cave  # noqa: E402

OUT = ROOT / "data" / "cie_graphs" / "the_cave_explorers.json"
TEXT = dict(cave.TEXTS)

# Fixed awards (see above).
NORMAL_TECH, NORMAL_FOOD = 2000, 500
AWARD = {"FIND_COINS": ("tech", NORMAL_TECH), "FIND_TREASURE": ("tech", 3 * NORMAL_TECH),
         "FIND_FOOD": ("food", 2 * NORMAL_FOOD), "RETURN_FOOD": ("food", NORMAL_FOOD),
         "RETURN_TECH": ("tech", NORMAL_TECH), "KEEP_RESEARCH": ("tech", NORMAL_TECH)}
KEEP_LABEL = "Curses schmurses. I'm keeping them"


def words(template: str, who: dict[str, str]) -> str:
    """The event's template with its tokens as the format's placeholders; `who` maps a token letter to a role."""
    def name(m: re.Match) -> str:
        return "(name1)" if who[m.group(1)] == "subject" else "(name2)"

    def pronoun(m: re.Match) -> str:
        pair = {"he": "he/she", "He": "He/She", "his": "his/her", "him": "him/her"}[m.group(1)]
        role = who[m.group(2)]
        return f"({pair})" if role == "subject" else f"({role}.{pair})"
    text = re.sub(r"\{(he|He|his|him)\.([a-z])\}", pronoun, template)
    text = re.sub(r"\{([a-z])\}", name, text)
    return text.replace("%d", "(award)")


AB = {"a": "subject", "b": "friend"}


def text(key: str, **extra: str) -> str:
    return words(TEXT[key], {**AB, **extra})


def award(key: str) -> list[dict]:
    kind, amount = AWARD[key]
    return [{"do": kind, "amount": amount, "scaled": True, "defer": True}, {"do": "pay_award"}]


def build() -> dict:
    stay_first, stay_rest = TEXT["STAY"].split(' "Wait.', 1)
    stay_rest = '"Wait.' + stay_rest
    n: dict[str, dict] = {}
    n["intro"] = {"type": "question", "text": text("INTRO"),
                  "choices": [{"label": TEXT["LABEL_EXPLORE"], "next": "explore"},
                              {"label": TEXT["LABEL_DONT"], "next": "dont"}]}
    n["dont"] = {"text": text("DONT"), "summary": "does not explore", "outcome": "nothing happens"}
    n["explore"] = {"text": text("EXPLORE_1"), "children": [{"next": "explore_q"}]}
    n["explore_q"] = {"type": "question", "text": text("EXPLORE_2"),
                      "choices": [{"label": TEXT["LABEL_PROCEED"], "next": "deeper"},
                                  {"label": TEXT["LABEL_STAY"], "next": "stay"}]}
    n["deeper"] = {"text": text("DEEPER"),
                   "children": [{"next": "a_scream", "weight": cave.PROCEED_A_PERCENT},
                                {"next": "b_search", "weight": 100 - cave.PROCEED_A_PERCENT}]}
    # A: who screams (1 in 2), what is wrong (1 in 4), the run.
    n["a_scream"] = {"type": "branch", "children": [{"next": "a_s1"}, {"next": "a_s2"}]}
    wrongs = [{"next": w.lower()} for w in cave.WRONG]
    n["a_s1"] = {"popup": "append", "join": "paragraph", "text": text("A_SCREAM", s="subject", o="friend"),
                 "children": wrongs}
    n["a_s2"] = {"popup": "append", "join": "paragraph", "text": text("A_SCREAM", s="friend", o="subject"),
                 "children": [dict(w) for w in wrongs]}
    for w in cave.WRONG:
        n[w.lower()] = {"popup": "append", "text": text(w), "children": [{"next": "run_q"}]}
    n["run_q"] = {"type": "question", "text": text("RUN", s="subject"),
                  "variants": [{"if": {"visited": "a_s2"}, "text": text("RUN", s="friend")}],
                  "choices": [{"label": TEXT["LABEL_LEFT"], "next": "run_left"},
                              {"label": TEXT["LABEL_RIGHT"], "next": "run_right"}]}
    ends = [{"next": "argue", "weight": cave.A_ENDINGS["ARGUE"]},
            {"next": "makeup", "weight": cave.A_ENDINGS["MAKEUP"]},
            {"next": "chasm", "weight": cave.A_ENDINGS["CHASM"]}]
    n["run_left"] = {"text": text("RUN_LEFT"), "children": ends}
    n["run_right"] = {"text": text("RUN_RIGHT"), "children": [dict(e) for e in ends]}
    n["argue"] = {"popup": "append", "join": "paragraph", "text": text("ARGUE"), "children": [{"next": "argue_2"}]}
    n["argue_2"] = {"popup": "append", "join": "paragraph", "text": text("ARGUE_2"),
                    "summary": "they argue", "outcome": "both come home"}
    n["makeup"] = {"popup": "append", "join": "paragraph", "text": text("MAKEUP"),
                   "summary": "they make up", "outcome": "both come home"}
    n["chasm"] = {"type": "branch", "children": [{"next": "chasm_1"}, {"next": "chasm_2"}]}
    n["chasm_1"] = {"popup": "append", "join": "paragraph", "text": text("CHASM", c="subject", d="friend"),
                    "effects": [{"do": "vanish", "role": "subject"}, {"do": "vanish", "role": "friend"}],
                    "summary": "the chasm, name1 slips first", "outcome": "both disappear, no graves"}
    n["chasm_2"] = {"popup": "append", "join": "paragraph", "text": text("CHASM", c="friend", d="subject"),
                    "effects": [{"do": "vanish", "role": "friend"}, {"do": "vanish", "role": "subject"}],
                    "summary": "the chasm, name2 slips first", "outcome": "both disappear, no graves"}
    # B: who finds it (1 in 2), what it is.
    n["b_search"] = {"type": "branch", "children": [{"next": "b_find_1"}, {"next": "b_find_2"}]}
    finds = [{"next": f.lower(), "weight": w} for f, w in cave.B_FINDS.items()]
    n["b_find_1"] = {"popup": "append", "join": "paragraph", "text": text("B_SEARCH", r="subject"),
                     "children": finds}
    n["b_find_2"] = {"popup": "append", "join": "paragraph", "text": text("B_SEARCH", r="friend"),
                     "children": [dict(f) for f in finds]}
    n["find_map"] = {"popup": "append", "text": text("FIND_MAP"),
                     "effects": [{"do": "vanish", "role": "subject"}, {"do": "vanish", "role": "friend"}],
                     "summary": "a map: both leave", "outcome": "both disappear, no graves"}
    for key, summary in (("FIND_COINS", "gold coins"), ("FIND_TREASURE", "a treasure map"),
                         ("FIND_FOOD", "preserved food")):
        n[key.lower()] = {"popup": "append", "text": text(key), "effects": award(key), "summary": summary,
                          "outcome": "both come home"}
    # Stay here.
    n["stay"] = {"text": words(stay_first, AB), "children": [{"next": "stay_q"}]}
    n["stay_q"] = {"type": "question", "text": words(stay_rest, AB),
                   "choices": [{"label": TEXT["LABEL_RETURN"], "next": "return"},
                               {"label": KEEP_LABEL, "next": "keep"}]}
    n["return"] = {"type": "branch", "children": [
        {"next": "return_food", "weight": cave.RETURN_FOOD_PERCENT},
        {"next": "return_tech", "weight": 100 - cave.RETURN_FOOD_PERCENT}]}
    n["return_food"] = {"text": text("RETURN_FOOD"), "effects": award("RETURN_FOOD"), "summary": "food",
                        "outcome": "both come home"}
    n["return_tech"] = {"text": text("RETURN_TECH"), "effects": award("RETURN_TECH"), "summary": "tech points",
                        "outcome": "both come home"}
    n["keep"] = {"text": text("KEEP") + ",", "children": [
        {"next": key.lower(), "weight": w} for key, w in cave.KEEP_ENDINGS.items()]}
    n["keep_research"] = {"popup": "append", "text": text("KEEP_RESEARCH"), "effects": award("KEEP_RESEARCH"),
                          "summary": "the researchers", "outcome": "both come home"}
    n["keep_both"] = {"popup": "append", "text": text("KEEP_BOTH"),
                      "effects": [{"do": "kill", "role": "friend", "cause": "unknown"},
                                  {"do": "kill", "role": "subject", "cause": "unknown"}],
                      "summary": "name2 dies, then name1", "outcome": "both die, graves"}
    n["keep_one"] = {"popup": "append", "text": text("KEEP_ONE"),
                     "effects": [{"do": "kill", "role": "friend", "cause": "unknown"}],
                     "summary": "name2 dies", "outcome": "name2 dies, a grave"}
    return {
        "format": "vvfp-cie-graph", "version": 2, "title": cave.TITLE, "games": [cave.GAME], "patches": [],
        "requirement": {"min_eligible": 2},
        "roles": {"subject": {"kind": "villager", "min_age": cave.ADULT_YEARS},
                  "friend": {"kind": "villager", "min_age": cave.ADULT_YEARS}},
        "start": "intro", "nodes": n,
    }


def main() -> int:
    OUT.write_text(json.dumps(build(), indent=2) + "\n", encoding="utf-8", newline="\n")
    print(OUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
