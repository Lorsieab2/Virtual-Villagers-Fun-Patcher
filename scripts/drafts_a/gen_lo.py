"""Write the owner-approved draft "New Events - Luck, Omens and Lavastones" (LO-01..50) as collection events, then
format and check them (scripts/drafts_a/da_common.py has the shape and the defaults; this table is the authoring
record).

Review (the rulebook's 15 checks, 2026-11-15): no hard-rule break, no sensitivity edit.  Luck and omens (1-30) end
without proof either way; lavastones (31-50) harm only by chance, never in a villager's hands against someone, and
their origins are never settled (34, 45, 50 keep every theory open).  LO-42's death says plainly that nobody could
have known; it is the stone, not a punishment for curiosity.

Effects, as the draft's brackets: small food 1 A, 18 A, 28 B, 32 A, 32 B, 41 A; celebrates 15 B, 21 B (the
subject), 47 A1 (the village: "villagers nearby"); small Farming 24 A (the friend); small Building or Farming 40 A
and 40 B (the work the setup names: building, carrying, digging); small tech 42 A1.
Harm (the text's own odds win; LO's "(About N in M)" lines are weighted alternatives):
  33 A1 (6 in 10) the friend gains health; A2 (3 in 10) nothing; A3 (1 in 10) the friend gains a little health,
     "loses some later" is text only (rule 9: no later change).
  38 A1 (7 in 10) the subject is sick; A2 (3 in 10) sick, and the lasting dislike of "the jungle edge" is text
     only: no game has a fitting preference word (owner question).
  40 A the subject loses a little health (MINOR), with the skill gain.
  42 A1 (7 in 10) tech; A2 (2 in 10) the subject dislikes "learning" (VV2-VV5; A New Home has no "learning", so
     there the outcome is the same text with no dislike: a game-conditioned child); A3 (1 in 20) the subject dies,
     Unknown causes, with a grave (FLAG: higher than the usual very rare; the text's odds kept); A4 (otherwise,
     1 in 20) nothing.
  43 A and B the subject gets the old head look (cast 18-54 so the change shows).
  44 B both villagers lose a little health (MINOR).
  47 A2 (4 in 10) the subject is sick.
Protected villagers stay protected (no "allow").

Grammar fix (grammar-fixes.md, Group 4): (his/hers) in 48.

Casting (the owner's naming rule, 2026-11-15: a person named only by role is a cast villager, named at the first
mention): 2 the visitor, 3 the neighbor, 6 the third villager (named at every mention), 20 the child, 30 the
other villager, the third and the friend, 43 the grey-haired elder, 49 the visitor.  Left alone: groups (elders,
neighbors, fishers, healers), 6's old friend from another village (arrives only in the telling), 21's couple
(the casting line: story only), 22's two unnamed answers, memories (grandmothers, an uncle).

Story-only notes (narrative is not gameplay, kept as written): 14's baby goats, 20's gold coin (all five games),
21's wedding, 33's fever (no role condition can ask for a sick or low-health villager).

    python scripts/drafts_a/gen_lo.py [--review <folder>]
"""
from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import da_common as c  # noqa: E402

SOURCE = "da_lo"
STORY_PRONOUN = "a pronoun for a story-only person (not a cast villager) would name a villager"
TABLE: dict[int, dict] = {
    1: {"desc": "A fisher realizes halfway to the reef that they forgot their lucky fishing song: turn back, or keep going."},
    2: {"roles": {"subject": c.ADULT, "friend": c.ADULT, "visitor": c.ADULT},
        "cast": [(27, "a visitor from another village turns up", "(visitor), a visitor from another village, turns up")],
        "desc": "Three birds land together on a villager's roof, and an old family saying says a visitor is coming."},
    3: {"roles": {"subject": c.ADULT, "friend": c.ADULT, "neighbor": c.ADULT}, "pron": {"a": {0: "friend"}},
        "cast": [(42, "a neighbor brings over", "(neighbor), a neighbor, brings over")],
        "desc": "A villager's palm has been itching all morning, which means a gift is coming: wait for it, or forget it."},
    4: {"pron": {"setup": {0: "friend"}, "b": "subject"},
        "desc": "A villager watches in horror as a friend steps over a digging stick, which is said to be bad luck."},
    5: {"desc": "Two villagers find they had exactly the same dream: a white canoe with a blue sail on a sea of flowers."},
    6: {"roles": {"subject": c.ADULT, "friend": c.ADULT, "third": c.ADULT},
        "cast": [(72, "talking about a third villager", "talking about (third), a third villager"),
                 (72, "the third villager walks", "(third) walks"),
                 (75, "The third villager looks", "(third) looks"),
                 (78, "After the third villager has gone", "After (third) has gone")],
        "desc": "Two villagers are talking about someone, and that very moment the person walks round the corner."},
    7: {"desc": "A villager's old lucky sandals snap in half on the morning of the harvest feast: mend them, or go without."},
    8: {"pron": {"setup": "subject"},
        "desc": "A villager throws spilled salt over a shoulder for luck, straight into the face of the friend behind them."},
    9: {"pron": {"setup": "subject"},
        "desc": "A villager will not carry seven of anything, and a friend has stacked exactly seven baskets to carry."},
    10: {"roles": {"subject": c.ages(10), "friend": c.ADULT}, "pron": {"b": "subject"},
         "desc": "A villager sees a shooting star and gets a wish for the first time: make one, or give it away."},
    11: {"pron": {"b": "subject"},
         "desc": "A villager has had one of those days, one small bad thing after another: is it bad luck, or just a day?"},
    12: {"desc": "A villager boasts that the roof never leaks, then looks for wood to knock on, and the nearest is a stick."},
    13: {"desc": "A villager has won six nights running from the same seat by the fire, and tonight a friend is in it."},
    14: {"desc": "A moth settles in a villager's hut, and an old family saying says that news is coming."},
    15: {"fx": {"b": [c.celebrate("subject")]},
         "desc": "A villager finds a rare double coconut: keep it whole for luck, or crack it open and share it."},
    16: {"desc": "A friend sneezes just as a villager promises to finish a new roof, and that means it must be true."},
    17: {"desc": "A villager always steps out left foot first for luck, and a doubting friend decides to test it."},
    18: {"roles": {"subject": c.ages(30), "friend": c.YOUNG_ADULT},
         "desc": "On the first fishing day, a younger fisher pulls in a beautiful first fish that should go back to the sea."},
    19: {"desc": "A teenager whistles after dark on purpose, and a gust of wind rattles every roof in the village."},
    20: {"roles": {"subject": c.ADULT, "friend": c.ADULT, "child": c.CHILD}, "pron": {"b": "subject"},
         "cast": [(246, "sees a child pick it up", "sees (child), a child, pick it up")],
         "desc": "A villager finds an old gold coin lying face up on the path: keep it for luck, or leave it for the next person."},
    21: {"fx": {"b": [c.celebrate("subject")]},
         "desc": "It pours with rain on a wedding day, and an old friend insists that rain is the best luck there is."},
    22: {"pron": {"b": "subject"},
         "desc": "A villager's left ear has been ringing all morning, which means somebody is saying something nice."},
    23: {"desc": "Two friends swap secret presents and find they have both carved exactly the same little turtle."},
    24: {"fx": {"a": [c.sk("friend", "Farming")]}, "pron": {"a_label": "friend"},
         "desc": "Everything a villager plants grows, and a friend arrives with a basket of seeds to plant for luck."},
    25: {"desc": "A friend asks a villager why they never take one path in the village, and they cannot remember."},
    26: {"desc": "A small spider builds a web across a villager's doorway, and some neighbors say it is very lucky."},
    27: {"desc": "Two villagers swap their lucky charms for a day, just to see what happens."},
    28: {"fx": {"b": [c.food("small")]}, "pron": {"b_label": "friend"},
         "desc": "A villager hooks a huge fish, and a friend says they have got it before it is in the canoe."},
    29: {"pron": {"b": "subject"},
         "desc": "A villager has had the hiccups for an hour, and a friend knows a cure that has never failed."},
    30: {"roles": {"subject": c.ELDER, "friend": c.ADULT, "cook": c.ADULT, "third": c.ADULT, "pal": c.ADULT},
         "cast": [(363, "Another villager tries", "(cook), another villager, tries"),
                  (363, "A third finally asks a friend to go fishing, and the friend says yes",
                   "A third, (third), finally asks (pal), a friend, to go fishing, and (pal) says yes")],
         "desc": "An elder announces that today is a lucky day: try something bold, or carry on as normal."},
    31: {"desc": "A villager wading in the stream finds a warm, glowing stone: a lavastone."},
    32: {"desc": "The plants around the lavastone in a villager's garden are growing twice as fast as anything else."},
    33: {"fx": {"a1": [c.health("friend", *c.BETTER)], "a3": [c.health("friend", *c.SMALL_BETTER)]},
         "to": {"a3": [c.T("feels oddly drained for a long while afterward (\"loses some later\")",
                           "rule 9: no game makes a later health loss; the gain now is the effect")]},
         "note": "the casting line asks for a villager who is sick or has low health: no role condition can ask for "
                 "that, so the fever is story text",
         "desc": "A villager with a fever is not getting better, and a friend has a lavastone some say can help the sick."},
    34: {"desc": "Two villagers have argued politely all afternoon over a lavastone: a rare rock, or something sacred?"},
    35: {"desc": "A family lavastone that has glowed by the fire for generations cracks in two, and light leaks out."},
    36: {"pron": {"setup": "subject", "a": "subject"},
         "desc": "A villager showing a friend a little lavastone in the canoe drops it over the side into deep water."},
    37: {"desc": "Two villagers find a lavastone together, and it glows warm in only one of their hands."},
    38: {"fx": {"a1": [c.sick("subject")], "a2": [c.sick("subject")]},
         "to": {"a2": [c.T("dislikes the jungle edge (lasting)",
                           "rule 8: no game has a fitting preference word for the jungle edge (the draft: only "
                           "where the game has a fitting dislike)")]},
         "desc": "A villager brings home a lavastone that glows a cold purple, and has not slept well since."},
    39: {"desc": "A child has found a pretty orange stone on the beach, and an adult sees that it is a lavastone."},
    40: {"pron": {"setup": "subject"},
         "fx": {"a": [c.sk("subject", ["Building", "Farming"]), c.health("subject", *c.MINOR)],
                "b": [c.sk("subject", ["Building", "Farming"])]},
         "desc": "A villager with a lavastone necklace can work all day without tiring, but a friend thinks they look thin."},
    41: {"desc": "In a dry spell, a villager notices a lavastone grows warmer near the low ground by the cliffs."},
    42: {"pron": {"b": "subject"},
         "fx": {"a2": [c.dislike("subject", "learning")], "a3": [c.die("subject")]},
         "note": "the 1 in 20 death on Try It is higher than the usual very rare: the text's own odds kept, for the "
                 "owner's review",
         "desc": "A villager who has studied a lavastone for weeks wants to try to draw out its power on purpose."},
    43: {"roles": {"subject": c.ages(18, 54), "friend": c.ADULT, "elder": c.ELDER}, "pron": {"a": {7: "subject"}},
         "cast": [(531, "One of them, with grey hair", "One of them, (elder), with grey hair")],
         "fx": {"a": [c.old_look("subject")], "b": [c.old_look("subject")]},
         "desc": "A villager picks up an old lavastone bare-handed, and walks out into the light looking years older."},
    44: {"fx": {"b": [c.health("subject", *c.MINOR), c.health("friend", *c.MINOR)]},
         "desc": "Two villagers caught in a storm shelter in a cave with no fire, and one has a cold, dark lavastone."},
    45: {"desc": "Two villagers digging a garden find a lavastone that somebody buried long ago, ringed with stones."},
    46: {"roles": {"subject": c.ADULT},
         "desc": "A villager who always sleeps wonderfully finds a glowing lavastone under the floor, beneath the mat."},
    47: {"fx": {"a1": [c.celebrate()], "a2": [c.sick("subject")]},
         "desc": "A humming lavastone has been giving people headaches, and a villager has been asked to break it."},
    48: {"roles": {"subject": c.ADULT},
         "fixes": [(590, "It's still (his/hers).", "It's still (his/her) own.")],
         "desc": "The lavastone a villager has carried for most of their life has gone cold, and its glow is gone."},
    49: {"roles": {"subject": c.ADULT, "visitor": c.ADULT},
         "cast": [(599, "A visitor from another village has come", "(visitor), a visitor from another village, has come")],
         "desc": "A visitor from another village presses a small, green, glowing lavastone into a villager's hand."},
    50: {"pron": {"setup": {0: "subject"}, "a": {0: "friend"}},
         "desc": "A child holding a lavastone asks where they come from, and an adult has heard too many answers."},
}

NO_LEARNING = [1]   # A New Home has no "learning" preference (vv_cie_graph GAMES[1].preferences)


def patch(doc: dict) -> None:
    """LO-42 A2: the dislike of "learning" only where the game has the word; in A New Home the same page, no effect
    (a child "if"/"else", the engine's own form; da_common cannot express it)."""
    if doc["collection"]["id"] != "lo42_stone_burned":
        return
    a2 = doc["nodes"]["a2"]
    alt = copy.deepcopy(a2)
    alt.pop("effects", None)
    alt["name"] = "Outcome A2 (A New Home)"
    alt["text_only"] = alt.get("text_only", []) + [{
        "what": "dislikes research or learning (lasting)", "src": a2["src"],
        "reason": "rule 8: A New Home has no fitting preference word (no \"learning\"); the draft: only where the "
                  "game has a fitting dislike"}]
    doc["nodes"]["a2_anh"] = alt
    for k in doc["nodes"]["a"]["children"]:
        if k["next"] == "a2":
            k["if"] = {"game": [g for g in doc["games"] if g not in NO_LEARNING]}
            k["else"] = "a2_anh"


def run(review: str | None) -> int:
    """da_common.run with patch() before each write."""
    with c.lib.use_source(SOURCE):
        paths, reports = [], []
        for r in c.rows(SOURCE):
            doc, _log = c.build(r, TABLE.get(c.num_of(r), {}))
            patch(doc)
            p = c.lib.DRAFTS_A_DIR / SOURCE / f"{r['id']}.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(c.cc.canonical(c.cc.with_outcome_effects(doc, p)), encoding="utf-8", newline="\n")
            paths.append(str(p))
            reports.append(c.pron_report(r, doc))
    if review:
        out = Path(review) / f"{SOURCE}.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n\n".join(reports) + "\n", encoding="utf-8", newline="\n")
        print(f"review: {out}")
    return subprocess.call([sys.executable, str(c.ROOT / "scripts" / "collection_check.py"), "--format", *paths])


if __name__ == "__main__":
    sys.exit(run(sys.argv[sys.argv.index("--review") + 1] if "--review" in sys.argv else None))
