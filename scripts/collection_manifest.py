"""Build data/event_collection/manifest.json: the Isola Grand Event Collection checklist (design E2).

One row per event, add-on, bank and notes section of the frozen source (scripts/collection_lib.SOURCE), from the three
inventories (lines 1-3519, 3520-6836, 6837-10571), each row re-verified against the source text itself:
  * the title is found at the top of the row's lines, and the lines start and end at a section boundary;
  * the choice count is recounted from the source where its choice lines have a recognisable shape;
  * each bank ("A:", "(1) ... choose one:", "D-CUISINE ...:") is recounted: its bullets, or its plain lines up to the
    next bank heading; an inline "(a/b/c)" bank is recounted from its slashes at the line given.
Where the inventory and the source disagree, the SOURCE wins: the row keeps the source's number and the disagreement
is listed in the manifest ("disagreements") for the owner packet.  A count the script cannot locate is "unverified"
and stays the inventory's number.  The whole file is also checked for lines no row covers.

    python scripts/collection_manifest.py            # write the manifest
    python scripts/collection_manifest.py --check    # exit 1 if the written manifest is stale
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collection_lib as lib  # noqa: E402

# ---- Credits: the ledger (lines 1-91) and each section's own credit block --------------------------------------------

CREDITS = {
    "cooking": ("lorsieab2_original", [(22, 24)]),
    "child": ("lorsieab2_original", [(25, 26)]),
    "faith": ("lorsieab2_original", [(27, 28)]),
    "universal": ("chatgpt_directed", [(39, 43)]),
    "vv5_isolan": ("chatgpt_directed", [(39, 39), (44, 47)]),
    "v6v8": ("chatgpt_directed", [(39, 39), (48, 50)]),
    "v9": ("mixed", [(51, 54)]),
    "v10": ("mixed", [(55, 59)]),
    "v11_life": ("mixed", [(60, 63)]),
    "v11_ideas": ("mixed", [(64, 70)]),
    "v13": ("mixed", [(6840, 6848)]),
    "v14": ("mixed", [(7627, 7634)]),
    "exclusive": ("chatgpt_directed", [(7838, 7839)]),
    "v17": ("mixed", [(8037, 8043)]),
    "v18": ("mixed", [(8496, 8499)]),
    "v20": ("mixed", [(8906, 8909)]),
    "v21": ("mixed", [(9367, 9368)]),
    "v22": ("mixed", [(9555, 9558)]),
    "v23": ("mixed", [(9973, 9974)]),
    "v24": ("mixed", [(10142, 10146)]),
    "v26": ("mixed", [(10435, 10436)]),
    "ledger": ("ledger", [(1, 91)]),
}

SERIES = ("v14_golden_child", "v17_contests", "v18_trials", "v20_crises")
ALL = [1, 2, 3, 4, 5]

ROWS: list[dict] = []


def R(id, title, games, a, b, kind, section, credit, choices=0, pools=None, effects=(), deaths=False, series=None,
      **extra):
    """One manifest row.  pools: {label: n} -- n an int (a bank under that heading), or (n, line) for an inline
    "(a/b/c)" bank on that line, or (n, None) for a count the script cannot locate (unverified)."""
    ROWS.append(dict(id=id, title=title, games=list(games), lines=[a, b], kind=kind, section=section, credit=credit,
                     choices=choices, pools=dict(pools or {}), effects=list(effects), deaths=deaths, series=series,
                     **extra))


def short_id(id: str) -> str:
    """A collection id the packager accepts (at most 30 characters, the game's long-path limit): drop "the" words,
    then cut at the last word boundary that fits."""
    if len(id) <= 30:
        return id
    id = re.sub(r"_the(?=_)", "", id)
    while len(id) > 30:
        id = id.rsplit("_", 1)[0]
    return id


def N(id, title, a, b, section, credit="ledger", pools=None):
    R(id, title, [], a, b, "notes", section, credit, pools=pools)


# ---- Part 1 (lines 1-3519) --------------------------------------------------------------------------------------------
N("notes_credit_ledger", "Authorship, concept and revision credits", 1, 91, "ledger")
N("notes_v11_header", "Original collection follows - text preserved from V11", 93, 95, "original")
R("vv2_cooking_contest", "The Cooking Contest", [2], 100, 626, "event", "original", "cooking", 2,
  {"A": 21, "B": 17, "C": 24, "(F)": 28, "D-CUISINE": 27, "D-STYLE": 13, "G": 15, "required ingredient": (12, 268),
   "H": 25, "I": 27, "J": 19, "L": 18, "K": 22, "M": 16, "O": 20, "P": 18, "Q": 27, "R": 22, "(1)": 6,
   "(5)": 4, "(8)": 4, "(9)": 5, "(13)": 10, "(6)": 10},
  ["food", "skill_set:Farming", "preference:dislikes"], choice_re=r"^(Stick with their original recipe|Try a new recipe):$")
R("vv2_cooking_addon1", "The Cooking Contest: the accusation, confession, self-sabotage and rivalry", [2], 632, 725,
  "addon", "original", "cooking", 0, {"(19)": 6, "(17)": 4, "(18)": 6, "(27)": 5, "(29)": 6}, ["food", "skill:Farming"],
  choice_re=r"^CHOICE\b")
N("notes_cooking_child_faith_branch_notes", "Editorial / branch notes (not displayed in-game)", 864, 870, "original")
R("vv2_cooking_addon2", "The Cooking Contest: extra drama and aftermath", [2], 872, 1154, "addon", "original",
  "cooking", 0, {"(17)": 7, "(22)": 5, "(25)": 8, "(26)": 5, "(28)": 8, "(30)": 8, "(31)": 6, "(32)": 5},
  ["food", "skill:Farming"], extra_labels={"(22)": [r"\(22\) AFTER THE BETRAYAL"]})
R("vv1_child_of_legend", "The Child of Legend", [1], 728, 791, "event", "original", "child", 2,
  {"(1)": 9, "(2)": 11, "(3)": 4, "(4)": 11}, ["tech", "food"], extra_labels={"(4)": [r"\(4\) ADDITIONAL"]},
  choice_re=r"^(Try to speak with him|Teach him something new):$")
R("vv5_meaning_of_faith", 'The Meaning of "Faith"', [5], 795, 862, "event", "original", "faith", 6,
  {"(3)": 6, "(4)": 15, "(6)": (8, 860)}, ["skill:Research", "skill:Research|Healing|Devotion"],
  choice_re=r'^("Faith" .*|Question the assignment itself):$', extra_labels={"(3)": [r"ADDITIONAL \(3\) OUTCOMES"]})
R("all_grand_isolan_scholasticon", "The Grand Isolan Scholasticon", ALL, 1156, 1329, "event", "universal",
  "universal", 3, {"A": 12, "B": 12, "(1)": 6, "(2)": 6, "(3)": 5, "(4)": 5}, ["tech", "skill:Research"])
R("all_great_beautification", "The Great Beautification Project", ALL, 1331, 1472, "event", "universal",
  "universal", 3, {"A": 9, "(1)": 5, "(2)": 6, "(3)": 5, "(6)": 6}, ["tech", "skill:Building"])
R("all_doctors_dilemma", "The Doctors' Dilemma", ALL, 1474, 1659, "event", "universal", "universal", 4,
  {"A": 7, "B": 6, "C": 6, "rule": (4, 1511), "(1)": 4, "(2)": 4, "(3)": 5, "(4)": 5, "(5)": (3, None), "(6)": 7},
  ["kill", "skill:Healing", "skill:Research", "tech"], deaths=True)
R("all_everybodys_a_winner", "Everybody's a Winner?", ALL, 1661, 1822, "event", "universal", "universal", 4,
  {"A": 10, "(1)": 6, "(2)": 6, "(3)": 5, "(4)": 5, "(6)": 5, "(7)": 5}, ["skill:Research", "tech"])
R("all_isolan_storytelling", "The Great Isolan Storytelling Contest", ALL, 1824, 2059, "event",
  "universal", "universal", 3, {"A": 12, "B": 12, "(1)": 5, "(2)": 5, "(3)": 5, "C": 8, "(5)": 6, "(7)": 8},
  ["skill:Devotion", "skill:Research", "tech"])
N("notes_final_implementation", "Final implementation and editorial notes", 2061, 2099, "universal")
R("vv5_great_woodworking", "The Great Woodworking Competition", [5], 2101, 2396, "event", "vv5_isolan",
  "vv5_isolan", 4, {"JUDGE": 6, "A": 10, "B": 4, "(4)": 4, "(5)": 9, "(6)": 8, "(7)": 7, "(8)": 5, "(9)": 5,
                    "(10)": 5, "(13)": 5, "(14)": 4}, ["skill:Building", "tech"])
R("vv5_potluck_dispute", "The Potluck Dispute", [5], 2398, 2487, "event", "vv5_isolan", "vv5_isolan", 4,
  {"A": 7, "B": 6, "(1)": 3, "(2)": 4, "(3)": 3, "(4)": 5, "(5)": 5}, ["food", "skill:Devotion|Farming"])
R("vv5_great_laundry_mishap", "The Great Laundry Mishap", [5], 2489, 2567, "event", "vv5_isolan", "vv5_isolan", 4,
  {"A": 7, "(1)": 3, "(2)": 3, "(3)": 3, "(4)": 4, "(5)": 5}, ["skill:Building|Research"])
R("vv5_field_day", "The Field Day", [5], 2569, 2645, "event", "vv5_isolan", "vv5_isolan", 4,
  {"A": 8, "(1)": 4, "(2)": 3, "(3)": 3, "(4)": 4, "(5)": 6}, ["skill"])
N("notes_vv5_integration", "VV5 event integration notes", 2647, 2664, "vv5_isolan")
N("notes_v6_guide_and_casting", "V6 additions: author's design guide and protected-villager contract", 2666, 2733, "v6",
  pools={"VOICE": (10, 2683), "MOTIVE": (8, 2685), "REACTION": (8, 2688), "SMALL HUMAN DETAIL": (7, 2690)})
R("vv1_unexpected_question", "The Unexpected Question", [1], 2735, 2822, "event", "v6", "v6v8", 4,
  {"A": 8, "(1)": 4, "(2)": 4, "(3)": 4, "(4)": 4, "(5)": 4, "(6)": 4}, ["skill:Research"])
R("vv1_elders_favorite_stone", "The Elder's Favorite Stone", [1], 2824, 2863, "event", "v6", "v6v8", 0, {"A": 6})
R("vv2_veterinary_visitor", "The Veterinary Visitor", [2], 2865, 2918, "event", "v6", "v6v8", 2,
  {"A": 5, "(1)": 4, "(2)": 4, "(3)": 4}, ["skill:Healing"])
R("vv2_hut_sharing_negotiation", "The Hut-Sharing Negotiation", [2], 2920, 2994, "event", "v6", "v6v8", 4,
  {"(1)": 3, "(2)": 4, "(3)": 4, "(4)": 4, "(5)": 5}, ["skill:Building"])
R("vv3_chiefs_monumental_speech", "The Chief's Monumental Speech", [3], 2996, 3041, "event", "v6", "v6v8", 0,
  {"A": 4, "B": 7})
R("vv3_gardening_contest", "The Gardening Contest", [3], 3043, 3096, "event", "v6", "v6v8", 2,
  {"A": 6, "(1)": 4, "(2)": 4, "(3)": 5}, ["skill:Farming"])
R("vv4_breadfruit_breakdown", "The Breadfruit Breakdown", [4], 3098, 3172, "event", "v6", "v6v8", 4,
  {"A": 6, "(1)": 4, "(2)": 5, "(3)": 4, "(4)": 4, "(5)": 5}, ["food", "skill:Farming"])
R("vv4_lullaby", "The Lullaby", [4], 3174, 3235, "event", "v6", "v6v8", 2, {"A": 6, "(1)": 4, "(2)": 4, "(3)": 5})
N("notes_dangerous_template", "Optional dangerous / disappearance event template (not auto-enabled)", 3237, 3291, "v6")
R("vv5_keeper_of_little_things", "The Keeper of Little Things", [5], 3293, 3354, "event", "v6", "v6v8", 0,
  {"A": 7, "B": 7, "C": 5}, ["tech", "skill:Research|Devotion"])
R("vv5_multicultural_festival", "The Multicultural Festival", [5], 3356, 3494, "event", "v6", "v6v8", 4,
  {"A": 7, "B": 8, "(1)": 4, "(2)": 4, "(3)": 5, "(4)": 4, "(5)": 6, "(6)": 6}, ["skill", "food", "tech"])
N("notes_vv5_eligibility", "VV5 additional character and eligibility notes", 3496, 3517, "v6")

# ---- Part 2 (lines 3520-6836) -----------------------------------------------------------------------------------------
N("notes_v8_intent", "V8 - The Heart of Isola: author's intent and implementation", 3519, 3537, "v8", "v6v8")
R("bank_v8_character_banks", "V8 character banks P, Q, R, S, T, U", [], 3539, 3685, "bank", "v8", "v6v8", 0,
  {"P": (28, r"^P\d+\."), "Q": (16, r"^Q\d+\."), "R": (30, r"^R\d+\."), "S": (28, r"^S\d+\."),
   "T": (12, r"^T\d+\."), "U": (16, r"^U\d+\.")})
R("vv1_masters_small_apprentice", "The Master's Small Apprentice", [1], 3687, 3759, "event", "v8", "v6v8", 2,
  {"(1)": 5, "(2)": 4, "(3)": 4, "(4)": 5}, ["skill:Building"])
R("vv1_last_song_before_sunset", "The Last Song Before Sunset", [1], 3761, 3804, "event", "v8", "v6v8", 0, {},
  ["skill:Devotion"])
R("vv2_packed_hospital", "The Packed Hospital", [2], 3806, 3894, "event", "v8", "v6v8", 4,
  {"A": 5, "B": 5, "(1)": 3, "(2)": 3, "(3)": 3, "(4)": 3, "(5)": 5, "(6)": 5}, ["skill:Healing", "tech"])
R("vv2_timid_child", "The Timid Child", [2], 3896, 3948, "event", "v8", "v6v8", 2,
  {"A": 6, "(1)": 4, "(2)": 4, "(3)": 5})
R("vv3_unfortunate_portrait", "The Unfortunate Portrait", [3], 3950, 4025, "event", "v8", "v6v8", 4,
  {"A": 8, "(1)": 3, "(2)": 3, "(3)": 3, "(4)": 4, "(5)": 5}, ["skill:Research|Building"])
R("vv3_tale_telling_elder", "The Tale-Telling Elder", [3], 4027, 4078, "event", "v8", "v6v8", 0, {"A": 8},
  ["skill:Devotion|Research"])
R("vv4_fruity_masterpiece", "The Fruity Masterpiece", [4], 4080, 4147, "event", "v8", "v6v8", 4,
  {"(1)": 3, "(2)": 4, "(3)": 4, "(4)": 4, "(5)": 5}, ["food", "skill:Farming"])
R("vv4_quiet_gardener", "The Quiet Gardener", [4], 4149, 4197, "event", "v8", "v6v8", 2,
  {"(1)": 4, "(2)": 4, "(3)": 5}, ["skill:Farming|Building"])
R("vv5_gift_or_insult", "Gift or Insult?", [5], 4199, 4274, "event", "v8", "v6v8", 4,
  {"A": 7, "(1)": 4, "(2)": 3, "(3)": 4, "(4)": 4, "(5)": 5}, ["skill:Building|Devotion"])
R("vv5_little_things_remember", "The Little Things They Remember", [5], 4276, 4329, "event", "v8", "v6v8", 0,
  {"A": 7}, ["skill:Devotion"])
R("bank_v8_codas", "Rare emotional codas C1-C16", ALL, 4331, 4439, "bank", "v8", "v6v8", 0, {"C": (16, r"^C\d+\b")})
N("notes_v8_safety_filter", "Strict target safety and continuity filter", 4441, 4490, "v8", "v6v8")
N("notes_v9_overrides", "V9 - The Age of Terrible Ideas: canon and gameplay overrides", 4493, 4521, "v9", "v9")
R("bank_v9_materials", "V9 material and flavour banks", ALL, 4523, 4593, "bank", "v9", "v9", 0,
  {"M": (16, r"^M\d\d\b")})
R("vv1_the_wall", "The Wall", [1], 4595, 4692, "event", "v9", "v9", 4,
  {"(1)": 5, "(2)": 4, "(3)": 4, "(4)": 4, "(5)": 3, "(7)": 3, "(8)": 5, "(9)": 5}, ["skill:Building", "tech"])
R("vv1_missing_pearl", "The Missing Pearl", [1], 4694, 4731, "event", "v9", "v9", 2, {"(1)": 4, "(2)": 4, "(3)": 4})
R("vv2_experimental_remedy", "The Experimental Remedy", [2], 4733, 4794, "event", "v9", "v9", 4,
  {"(1)": 4, "(2)": 4, "(3)": 3, "(4)": 3, "(5)": 4})
R("vv2_stolen_spoon", "The Stolen Spoon", [2], 4796, 4872, "event", "v9", "v9", 4,
  {"(1)": 4, "(2)": 4, "(3)": 4, "(4)": 4, "(8)": 3})
R("vv3_chief_and_the_pearl", "The Chief and the Pearl", [3], 4874, 4934, "event", "v9", "v9", 4,
  {"(1)": 4, "(2)": 4, "(3)": 4, "(4)": 4, "(5)": 3})
R("vv3_duel_terrible_inventors", "The Duel of the Terrible Inventors", [3], 4936, 4973, "event", "v9", "v9", 2,
  {"(1)": 4, "(2)": 4, "(3)": 5})
R("vv4_arbor_day_festival", "The Arbor-Day Festival", [4], 4975, 5032, "event", "v9", "v9", 4,
  {"(1)": 3, "(2)": 4, "(3)": 4, "(4)": 4, "(5)": 6})
R("vv4_rotten_structure", "The Rotten Structure", [4], 5034, 5078, "event", "v9", "v9", 2,
  {"(1)": 4, "(2)": 4, "(3)": 3, "(5)": 3}, ["damage"])
R("vv5_slug_race", "The Slug Race", [5], 5080, 5141, "event", "v9", "v9", 4,
  {"(1)": 4, "(2)": 4, "(3)": 4, "(4)": 4, "(7)": 5})
R("vv5_trial_shattered_pearls", "The Trial of the Shattered Pearls", [5], 5143, 5222, "event", "v9", "v9", 5,
  {"(1)": 4, "(2)": 4, "(3)": 4, "(4)": 4, "(5)": 4, "(7)": 4})
R("bank_v9_coda_bank", "Universal coda bank R1-R26", ALL, 5224, 5317, "bank", "v9", "v9", 0, {"R": (26, r"^R\d+\b")})
N("notes_v9_editorial", "V9 editorial / implementation note", 5319, 5336, "v9", "v9")
N("notes_v10_canon_and_reputations", "V10 canon gate and reputation states", 5338, 5383, "v10", "v10")
R("all_no_good_very_bad_day", "(Name1)'s No Good, Very Bad Day", ALL, 5385, 5522, "event", "v10", "v10", 4,
  {"A": 8, "(1)": 3, "(2)": 4, "(3)": 3, "(4)": 3, "(5)": 3, "(6)": 3, "(7)": 3, "(8)": 3, "(9)": 5, "(10)": 4,
   "(11)": 5, "(12)": 4, "(13)": 4})
R("all_impossible_invention", "The Village Idiot and the Impossible Invention", ALL, 5524, 5605,
  "event", "v10", "v10", 2, {"(1)": 5, "(2)": 4, "(3)": 4, "(4)": 5, "(5)": 5})
R("all_unlikely_advisor", "The Unlikely Advisor", ALL, 5607, 5681, "event", "v10", "v10", 4,
  {"A": 6, "(1)": 3, "(2)": 3, "(3)": 3, "(4)": 3, "(5)": 4, "(6)": 5})
R("all_teacher_who_failed", "The Teacher Who Failed", ALL, 5683, 5728, "event", "v10", "v10", 0, {})
R("all_great_appointment_scandal", "The Great Appointment Scandal", ALL, 5730, 5848, "event", "v10", "v10", 4,
  {"A": 9, "(1)": 3, "(2)": 4, "(3)": 4, "(4)": 4, "(5)": 4, "(6)": 3, "(7)": 3, "(8)": 5, "(9)": 5})
R("vv345_magician_naturalist", "The Magician and the Naturalist", [3, 4, 5], 5850, 5926, "event", "v10",
  "v10", 4, {"A": 6, "(1)": 3, "(2)": 3, "(3)": 3, "(4)": 3, "(5)": 7})
R("bank_v10_outcome_bank", "Additional outcome bank O1-O30", ALL, 5928, 6097, "bank", "v10", "v10", 0,
  {"O": (30, r"^O\d+\b")})
N("notes_v10_safeguards", "V10 patcher implementation safeguards", 6099, 6128, "v10", "v10")
N("notes_v11_editor", "V11 editor's note", 6131, 6139, "v11", "v11_life")
R("all_secret_of_life", "The Secret of Life", ALL, 6141, 6408, "event", "v11", "v11_life", 4,
  {"A": (6, None), "B": (6, None), "C": (7, None), "D": (6, None)}, ["skill:Research|Healing|Building", "food"])
R("all_invention_showcase", "The Invention Showcase", ALL, 6410, 6659, "event", "v11", "v11_ideas", 3,
  {"IDEA": (20, None), "A": (8, None), "B": (7, None), "C": (8, None)}, ["skill:Building|Research"])
R("all_council_of_conundrums", "The Council of Conundrums", ALL, 6661, 6810, "event", "v11", "v11_ideas", 3,
  {"A": (5, None), "B": (6, None), "C": (5, None)}, ["skill"])
N("notes_v11_implementation", "V11 implementation and continuity notes", 6812, 6834, "v11", "v11_life")

# ---- Part 3 (lines 6837-10571) ----------------------------------------------------------------------------------------
N("notes_v13_credit_and_canon", "V13 credit and canon", 6836, 6860, "v13", "v13")
R(short_id("vv2_cooking_judge_who_feared_no_dish"), "The Cooking Contest: The Judge Who Feared No Dish", [2], 6862, 7028,
  "addon", "v13", "v13", 4, {"A": (6, None), "B": (5, None), "C": (5, None), "D": (5, None)}, ["skill:Research"])
R(short_id("all_panel_of_impossible_standards"), "The Panel of Impossible Standards", ALL, 7030, 7099, "addon", "v13", "v13", 4,
  {"endings": (8, None)})
R("all_its_alive", "It's Alive!", ALL, 7101, 7199, "event", "v13", "v13", 3,
  {"A": (4, None), "B": (4, None), "C": (5, None)}, ["skill:Research"])
R("all_physics_defying_builder", "The Physics-Defying Builder", ALL, 7201, 7286, "event", "v13", "v13", 4,
  {"A": (3, None), "B": (4, None), "C": (3, None), "D": (3, None)})
R("all_strange_statue", "The Strange Statue", ALL, 7288, 7360, "event", "v13", "v13", 3,
  {"A": (4, None), "B": (4, None), "C": (3, None)})
R("all_verse_that_changed_history", "The Verse That Changed History", ALL, 7362, 7480, "event", "v13", "v13", 4,
  {"ERROR BANK": 8, "A": (4, None), "B": (4, None), "C": (4, None), "D": (5, None)})
R("all_inexplicable_idea", "The Inexplicable Idea", ALL, 7482, 7590, "event", "v13", "v13", 3,
  {"IDEA BANK": 20, "A": (5, None), "B": (5, None), "C": (5, None)})
N("notes_v13_integration", "V13 integration and gameplay notes", 7592, 7621, "v13", "v13")
N("notes_v14_framework", "V14 - The Golden Child's New Wonders: credits and scope", 7623, 7649, "v14", "v14")
_V14 = [(1, "The Impossible Equation", 7651, 7656, ["tech"]), (2, "The World's Simplest Explanation", 7658, 7664, ["tech"]),
        (3, "The Little Philosopher", 7666, 7671, ["tech"]), (4, "The Living Map", 7673, 7678, ["tech"]),
        (5, "The Lesson Nobody Expected", 7680, 7685, ["skill"]), (6, "The Song of Isola", 7687, 7692, ["tech"]),
        (7, "The Instrument That Never Existed", 7694, 7699, ["tech"]), (8, "The Tiny Conductor", 7701, 7705, ["tech"]),
        (9, "The Rainbow Maker", 7707, 7712, []), (10, "The Little Stormcaller", 7714, 7719, []),
        (11, "The Thirsty Garden", 7721, 7727, ["food"]), (12, "The Berry Bush's Blessing", 7729, 7735, ["food"]),
        (13, "The Curious Little Explorer", 7737, 7743, ["tech"]), (14, "The Stars Have Names", 7745, 7750, ["tech"]),
        (15, "The Little Healer", 7752, 7756, ["health_change"]),
        (16, "The Child Who Settled an Argument", 7758, 7763, ["tech"]),
        (17, "The Golden Child's First Debate", 7765, 7770, ["tech"]), (18, "The Little Architect", 7772, 7776, ["tech"]),
        (19, "The Golden Child's History Lesson", 7778, 7782, ["tech"]),
        (20, "The Question That Changed Everything", 7784, 7788, ["tech"]),
        (21, "The Little Peacemaker", 7790, 7794, []), (22, "The Golden Child's Great Experiment", 7796, 7800, ["food"]),
        (23, "The Little Inventor's Disaster", 7802, 7807, ["tech"]), (24, "The Boy Who Understood Grief", 7809, 7813, []),
        (25, "The Child Who Refused to Be an Adult", 7815, 7820, [])]
for _n, _t, _a, _b, _e in _V14:
    _slug = re.sub(r"[^a-z0-9]+", "_", _t.lower().replace("'", "")).strip("_")
    R(short_id(f"vv1_v14_{_n:02d}_{_slug}"), _t, [1], _a, _b, "event", "v14", "v14", 0,
      {"subject": (11, 7661)} if _n == 2 else {"discovery": (7, None)} if _n == 13 else {}, _e,
      series="v14_golden_child")
N("notes_v14_variation_rules", "V14 optional variation rules", 7822, 7833, "v14", "v14")
N("notes_exclusive_header", "New game-exclusive island events: credits", 7835, 7840, "exclusive", "exclusive")
_EXCL = [(2, "The Secret Behind the Waterfall", 7842, 7855), (2, "The Hospital's Most Difficult Patient", 7857, 7866),
         (2, "The Great Totem Dispute", 7868, 7877), (3, "The Child Who Claimed to Be Chief", 7879, 7891),
         (3, "The Chief's Impossible Question", 7893, 7902), (3, "The Weather Dance That Went Wrong", 7904, 7914),
         (3, "The City's Two Histories", 7916, 7925), (3, "The Statue That Judged Its Makers", 7927, 7936),
         (4, "The Unwelcome Landscaper", 7938, 7949), (4, "The Mask That Wouldn't Stay Hidden", 7951, 7960),
         (4, "The Great Water Argument", 7962, 7971), (4, "The Dolphins' Strange Gift", 7973, 7982),
         (5, "The Feast of Two Traditions", 7984, 7995), (5, "The Old Belief and the New Question", 7997, 8006),
         (5, "The Convert Who Missed Home", 8008, 8017), (5, "The Guardians' Disagreement", 8019, 8028)]
for _g, _t, _a, _b in _EXCL:
    _slug = re.sub(r"[^a-z0-9]+", "_", _t.lower().replace("'", "")).strip("_")
    R(short_id(f"vv{_g}_{_slug}"), _t, [_g], _a, _b, "event", "exclusive", "exclusive", 2, {},
      ["tech", "food"] if _g in (3, 4, 5) else ["tech", "health_change"])
R("bank_v17_framework", "V17 - The Five Shores Compete: framework and universal consequence pool", ALL, 8033, 8093,
  "notes", "v17", "v17", 4, {"U": (10, None)})   # notes: every contest shows its common choices (shared_lines)
_V17 = [
    ("a", 1, "intro", 8095, 8103, None, 0),
    ("a", 1, "The First Great Feast", 8105, 8119, "cooking", 3), ("a", 1, "A Shelter for the Next Storm", 8121, 8129, "building", 3),
    ("a", 1, "The Stone Table of Questions", 8131, 8135, "research", 0),
    ("a", 1, "The Face of the Southern Shore", 8137, 8141, "sculpture", 0),
    ("a", 1, "The Words We Brought With Us", 8143, 8148, "story", 2), ("a", 1, "The Seed and Soil Trial", 8150, 8153, "farming", 0),
    ("a", 1, "The Greatest Little Champion", 8155, 8158, "children", 0),
    ("b", 2, "intro", 8160, 8169, None, 0),
    ("b", 2, "The Bridge That Should Not Stand", 8171, 8178, "building", 2), ("b", 2, "The Great Falls Riddle", 8180, 8184, "research", 0),
    ("b", 2, "The Totem's Unfortunate Cousin", 8186, 8191, "sculpture", 0), ("b", 2, "The Founders' Ballad", 8193, 8197, "story", 0),
    ("b", 2, "The Great Berry Challenge", 8199, 8203, "farming", 0), ("b", 2, "The Children's Jury", 8205, 8208, "children", 0),
    ("c", 3, "intro", 8210, 8217, None, 0),
    ("c", 3, "The Chief's Table", 8219, 8230, "cooking", 3), ("c", 3, "The Statue and the Impossible Arch", 8232, 8236, "building", 0),
    ("c", 3, "Magic, Nature and Measurement", 8238, 8242, "research", 0),
    ("c", 3, "The Chief's Most Unflattering Likeness", 8244, 8249, "sculpture", 3),
    ("c", 3, "The Two Histories", 8251, 8255, "story", 0), ("c", 3, "The Garden of Rival Methods", 8257, 8261, "farming", 0),
    ("c", 3, "The Chief for a Moment", 8263, 8268, "children", 0),
    ("d", 4, "intro", 8270, 8276, None, 0),
    ("d", 4, "The Roots and River Feast", 8278, 8289, "cooking", 3), ("d", 4, "The Water's Unlikely Path", 8291, 8296, "building", 0),
    ("d", 4, "The Question of the Tree", 8298, 8302, "research", 0), ("d", 4, "The Ugliest Guardian", 8304, 8310, "sculpture", 3),
    ("d", 4, "The Tree Remembers", 8312, 8316, "story", 0), ("d", 4, "The Waterkeepers' Trial", 8318, 8321, "farming", 0),
    ("d", 4, "The Mask-Makers' Parade", 8323, 8326, "children", 0),
    ("e", 5, "intro", 8328, 8382, None, 4),
    ("e", 5, "The Questionable Feast", 8384, 8401, "cooking", 4), ("e", 5, "The Bridge Between Neighbors", 8403, 8410, "building", 0),
    ("e", 5, "Who Owns a Discovery?", 8412, 8420, "research", 4), ("e", 5, "The Two Faces of Isola", 8422, 8430, "sculpture", 4),
    ("e", 5, "Who Gets to Tell Isola's History?", 8432, 8442, "story", 4),
    ("e", 5, "The Harvest and the Border", 8444, 8450, "farming", 0),
    ("e", 5, "The Children's Peace, the Adults' Quarrel", 8452, 8461, "children", 3),
    ("e", 5, "epilogues", 8463, 8473, None, 0),
]
for _p, _g, _t, _a, _b, _kind, _c in _V17:
    if _kind is None:
        if _t == "intro":
            R(f"notes_v17{_p}_intro", f"V17-{_p.upper()} setting and cast", [_g], _a, _b, "notes", "v17", "v17", _c,
              {"P": (10, None)} if _p == "e" else {})
        else:
            R("bank_v17e_epilogues", "V17-E final VV5 epilogues E1-E5", [5], _a, _b, "bank", "v17", "v17", 0,
              {"E": (5, None)})
        continue
    # a contest with no choices of its own asks the common competition question first (4 choices, L8069-8073), or in
    # VV5 the political question (L8349-8352); one branch set per trigger (L8054)
    R(f"vv{_g}_v17_{_kind}", _t, [_g], _a, _b, "event", "v17", "v17", _c, {}, [], series="v17_contests",
      shared_choices=4 if _c == 0 else 0)
N("notes_exclusive_end", "End of new game-exclusive events", 8030, 8030, "exclusive", "exclusive")
N("notes_v17_implementation", "V17 implementation and attribution notes", 8475, 8489, "v17", "v17")
N("notes_v18_framework", "V18 - The Grand Festival of Twelve Trials: credits, rules and framing", 8491, 8521, "v18",
  "v18")
_V18 = [("The Warriors' Tournament", 8524, 8552), ("The Martial Arts Tournament", 8555, 8582),
        ("The Great Question", 8585, 8612), ("The Philosophers' Duel", 8615, 8642),
        ("The Alchemists' Trial", 8645, 8672), ("The Paradox Challenge", 8675, 8702),
        ("The Sixteenth Aria", 8705, 8732), ("The Poets' Tournament", 8735, 8762),
        ("The Great Trivia Trial", 8765, 8792), ("The Ball Tournament", 8795, 8822),
        ("The Stick Game", 8825, 8852), ("The Hoop Tournament", 8855, 8882)]
# Ids and file names at most 30 characters (the packaging long-path limit): short slugs.
_V18_SLUGS = ['warriors_tournament', 'martial_arts', 'great_question', 'philosophers_duel', 'alchemists_trial', 'paradox_challenge', 'sixteenth_aria', 'poets_tournament', 'great_trivia_trial', 'ball_tournament', 'stick_game', 'hoop_tournament']
for _i, (_t, _a, _b) in enumerate(_V18, 1):
    _slug = _V18_SLUGS[_i - 1]
    R(f"all_v18_{_i:02d}_{_slug}", _t, ALL, _a, _b, "event", "v18", "v18", 2, {}, ["tech", "food", "skill"],
      series="v18_trials")
R("all_v18_isolan_decathlon", "The Isolan Decathlon", ALL, 8885, 8900, "event", "v18", "v18", 0, {"D": (4, None)})
N("notes_v20_canon", "V20 credits and canon and setting guide", 8902, 8939, "v20", "v20")
N("notes_v20_crises_header", "The Doctors' Dilemma: additional medical crises (shared rules)", 8941, 8948, "v20", "v20")
_V20 = [("D1", "Two Lives, One Decision", 8950, 8968, 3, True), ("D2", "The Treatment That Does Not Exist", 8970, 8982, 2, True),
        ("D3", "The Experimental Cure", 8984, 8999, 3, True), ("D4", "The Half-Translated Remedy", 9001, 9014, 2, False),
        ("D5", "The Last Dose", 9016, 9029, 3, True), ("D6", "The Physician Who Refused", 9031, 9039, 3, True),
        ("D7", "The Patient Who Knew Too Much", 9041, 9046, 2, False),
        ("D8", "The Medicine That Works Too Well", 9048, 9053, 2, False),
        ("D9", "The Healer's Secret", 9055, 9061, 2, False), ("D10", "The Child Who Corrected the Masters", 9063, 9069, 2, False),
        ("D11", "The Ancient Oath", 9071, 9078, 2, True), ("D12", "The Doctor Who Could Not Save Everyone", 9080, 9087, 3, True)]
_V20_SLUGS = {'D1': 'two_lives', 'D2': 'no_such_treatment', 'D3': 'experimental_cure', 'D4': 'half_translated', 'D5': 'last_dose', 'D6': 'physician_refused', 'D7': 'patient_knew_much', 'D8': 'works_too_well', 'D9': 'healers_secret', 'D10': 'child_corrected', 'D11': 'ancient_oath', 'D12': 'cannot_save_all'}   # ids at most 30 characters
for _d, _t, _a, _b, _c, _dead in _V20:
    _slug = _V20_SLUGS[_d]
    R(f"all_v20_{_d.lower()}_{_slug}", _t, ALL, _a, _b, "event", "v20", "v20", _c, {},
      ["kill", "health_change"] if _dead else ["health_change"], deaths=_dead, series="v20_crises")
R("all_v20_between_life_and_death", "The Doctors' Dilemma: Between Life and Death", ALL, 9089, 9184, "event", "v20",
  "v20", 7, {"A": (4, None), "B": (4, None), "C": (4, None), "D": (4, None), "E": (4, None), "F": (5, None),
             "G": (5, None)}, ["kill", "skill:Healing", "tech", "preference:dislikes"], deaths=True)
R("bank_v20_relic_pool", "The Impossible Relics of Isola: relic pool", ALL, 9186, 9204, "bank", "v20", "v20", 0,
  {"relics": (12, None)})
R("all_v20_r1_should_not_exist", "The Thing That Should Not Exist", ALL, 9206, 9250, "event", "v20",
  "v20", 4, {}, ["tech"])
R("all_v20_r2_relic_trial", "The Trial of the Impossible Relic", ALL, 9252, 9283, "event", "v20",
  "v20", 3)
R("all_v20_r3_isola_discovered", "Has Isola Been Discovered?", ALL, 9285, 9311, "event", "v20", "v20", 4, {},
  ["food"])
R("all_v20_r4_relic_outlived", "The Relic That Outlived Its Discoverer", ALL, 9313, 9330, "event",
  "v20", "v20", 0, {}, ["tech"])
N("notes_v20_relic_variants_codas", "Relics: game-specific variants, optional codas and implementation notes", 9332,
  9363, "v20", "v20")
N("notes_v21_header", "V21 - The Potters' Trials and the Great Isolan Crafts Fair: credits and setting", 9364, 9372,
  "v21", "v21")
R("all_v21_c1_potters_trial", "The Great Potters' Trial", ALL, 9374, 9423, "event", "v21", "v21", 3, {}, ["tech"])
R("all_v21_c2_divided_statue", "The Statue That Divided the Village", ALL, 9425, 9463, "event", "v21",
  "v21", 3, {}, ["tech"])
R("all_v21_c3_crafts_fair", "The Great Isolan Crafts Fair", ALL, 9465, 9515, "event", "v21", "v21", 3, {},
  ["tech", "food", "celebrate"])
N("notes_v21_adaptations_codas", "V21 game-specific adaptations and optional codas", 9517, 9549, "v21", "v21")
N("notes_v22_header", "V22 - Drawing, Strength, Potion-Making and Parenting: credits", 9551, 9560, "v22", "v22")
R("all_v22_1_drawing_contest", "The Great Isolan Drawing Competition", ALL, 9562, 9629, "event",
  "v22", "v22", 4, {}, ["tech"])
R("all_v22_2_strength_trials", "The Great Isolan Strength Trials", ALL, 9631, 9704, "event", "v22", "v22",
  5, {}, ["tech"])
R("all_v22_3_potion_making", "The Great Isolan Potion-Making Trials", ALL, 9706, 9786, "event",
  "v22", "v22", 5, {}, ["skill:Healing", "skill:Research", "tech"])
R("all_v22_4_parents_lesson", "The Parent's Lesson", ALL, 9788, 9930, "event", "v22", "v22", 7,
  {"A": (4, None), "B": (4, None), "C": (4, None), "D": (4, None), "E": (4, None), "F": (4, None), "G": (4, None)},
  ["skill:Parenting"])
N("notes_v22_adaptations_codas", "V22 cross-game adaptations and long-term codas", 9932, 9966, "v22", "v22")
N("notes_v23_header", "V23 - Pranks, Misunderstandings and Everyday Chaos: credits", 9970, 9976, "v23", "v23")
R("all_v23_1_practical_joke", "The Practical Joke", ALL, 9978, 10011, "event", "v23", "v23", 3, {}, ["mood", "tech"])
R("all_v23_2_ill_timed_sneeze", "The Ill-Timed Sneeze", ALL, 10013, 10031, "event", "v23", "v23", 0, {"S": (7, None)},
  ["food"])
R("all_v23_3_strange_coincidence", "The Strange Coincidence", ALL, 10033, 10060, "event", "v23", "v23", 3, {}, ["tech"])
R("all_v23_4_missing_coconuts", "The Missing Coconuts", ALL, 10062, 10075, "event", "v23", "v23", 3)
R("all_v23_5_false_alarm", "The False Alarm", ALL, 10077, 10093, "event", "v23", "v23", 3)
R("all_v23_6_prank_war", "The Prank War", ALL, 10095, 10110, "event", "v23", "v23", 3, {}, ["celebrate"])
N("notes_v23_seeds_and_notes", "V23 short-title seeds, cross-game notes and parenting language", 10112, 10137, "v23",
  "v23")
R("all_v24_revolutionary", "The Revolutionary Invention / The Revolutionary Discovery", ALL, 10139, 10430,
  "event", "v24", "v24", 5, {"subject": (32, None)}, ["skill", "tech", "food"])
R("bank_v26_materials", "V26 - The Materials of Isola", ALL, 10432, 10571, "bank", "v26", "v26", 0)

# ---- Re-verification against the source ------------------------------------------------------------------------------


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", lib.normalize_source_text(s).lower()).strip()


def title_found(row: dict) -> bool | None:
    """The row's title at the top of its lines (None for a notes row: its title is the manifest's own words)."""
    if row["kind"] in ("notes", "bank"):
        return None
    a = row["lines"][0]
    head = " ".join(_norm(lib.line(n)) for n in range(a, min(a + 8, lib.SOURCE_LINES + 1)))
    want = _norm(row["title"].split(":")[-1].split(" / ")[0])
    want = re.sub(r"^the ", "", want)
    return want in head


def heading(row: dict) -> str:
    """The first line of the row that is not blank or a separator."""
    a, b = row["lines"]
    for n in range(a, b + 1):
        if not lib.is_blank_or_separator(n):
            return f"L{n}: {lib.normalize_source_text(lib.line(n)).strip()}"
    return ""


def boundary_problems(row: dict) -> list[str]:
    a, b = row["lines"]
    out = []
    if not lib.line(a).strip():
        out.append(f"line {a} (first) is blank")
    if not lib.line(b).strip():
        out.append(f"line {b} (last) is blank")
    if a > 1 and not lib.is_blank_or_separator(a - 1) and not lib.is_separator(lib.line(a)):
        out.append(f"line {a - 1} before the row is not blank")
    if b < lib.SOURCE_LINES and not lib.is_blank_or_separator(b + 1):
        out.append(f"line {b + 1} after the row is not blank")
    return out


# A line that opens the next bank: "(7)", "(F):", "C:", "D-STYLE (...):", "A - APPROACH:", "ADDITIONAL ...", "NOTE:".
_HEADING = re.compile(r"^(\(\d+\)|\([A-Z]\)\s*:|[A-Z]{3,}[A-Z\-/ ]*(?:\(|:|\s-\s|$)|[A-Z](?:-[A-Z]+)?\s*(?:\(|:|\s-\s)"
                      r"|NOTE:)")
_BULLET = re.compile(r"^\s*[-*]\s")


def _label_re(label: str) -> re.Pattern:
    if label.startswith("("):
        return re.compile(r"^" + re.escape(label) + r"(?=[\s:]|$)")
    return re.compile(r"^" + re.escape(label) + r"(?=\s*(?:\(|:|\s-\s|$))")


def _bank_items(n: int, b: int) -> int:
    """Items of the bank whose heading is line n: its bullets, or else every non-blank line, up to the next bank."""
    s = lib.normalize_source_text(lib.line(n)).strip()
    plain = bullets = 0
    after = s.split(":", 1)[1].strip() if ":" in s else ""
    if after[:1].islower():
        plain += 1
    # A plain bank is either one item a line (a blank line ends it) or one paragraph per item with blank lines between
    # (then only the next heading ends it): the gap before its second item decides which.
    m = n + 1
    paragraphs = None
    gap = False
    while m <= b:
        t = lib.normalize_source_text(lib.line(m))
        if lib.is_separator(t):
            break
        if not t.strip():
            if plain >= 2 and paragraphs is False and not bullets:
                break
            gap = True
        else:
            if _HEADING.match(t) and not _BULLET.match(t):
                break
            if _BULLET.match(t):
                bullets += 1
            elif not (bullets and re.match(r"^\s+\S", t)):
                if plain == 1 and paragraphs is None:
                    paragraphs = gap
                plain += 1
            gap = False
        m += 1
    if bullets:
        return bullets
    return plain


def count_bank(a: int, b: int, label: str, extra: list[str] | None = None) -> int | None:
    """Items of the first bank headed `label` in lines a..b, plus the banks under any extra headings (an add-on that
    extends the same bank, e.g. "ADDITIONAL (3) OUTCOMES"); None when there is no such heading."""
    first = _label_re(label)
    total, found = 0, False
    for n in range(a, b + 1):
        s = lib.normalize_source_text(lib.line(n))
        if s.startswith(" "):
            continue
        if first is not None and first.match(s.strip()):
            total += _bank_items(n, b)
            found, first = True, None
        elif any(re.match(r"^" + x, s.strip()) for x in (extra or [])):
            total += _bank_items(n, b)
            found = True
    return total if found else None


def _logical_line(n: int) -> str:
    """Line n with the indented lines that continue it."""
    s = lib.normalize_source_text(lib.line(n))
    m = n + 1
    while m <= lib.SOURCE_LINES and re.match(r"^\s+\S", lib.line(m)):
        s += " " + lib.normalize_source_text(lib.line(m)).strip()
        m += 1
    return s


def count_inline(n: int) -> int | None:
    """Alternatives in the first slash list on line n: '(a/b/c)' or 'Label: a / b / c'."""
    s = _logical_line(n)
    depth, start = 0, None
    for i, ch in enumerate(s):
        if ch == "(":
            if depth == 0:
                start = i
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0 and start is not None:
                inner = s[start + 1:i]
                if "/" in inner:
                    return _split_top(inner)
    if ":" in s and "/" in s:
        return _split_top(s.split(":", 1)[1])
    return None


def _split_top(inner: str) -> int:
    depth, parts = 0, 1
    for ch in inner:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "/" and depth == 0:
            parts += 1
    return parts


def count_matching(a: int, b: int, rx: str) -> int:
    pat = re.compile(rx)
    return sum(1 for n in range(a, b + 1) if pat.match(lib.normalize_source_text(lib.line(n))))


_CHOICE_LINE = re.compile(r"^CHOICE\b")
_CHOICE_LETTER = re.compile(r"(?:^|[.;]\s+)([A-G])(?:\.\s+|:\s+|\s+-\s+)(?=\S)")


def count_choices(row: dict) -> int | None:
    a, b = row["lines"]
    lines = [lib.normalize_source_text(lib.line(n)) for n in range(a, b + 1)]
    if row.get("choice_re"):
        rx = re.compile(row["choice_re"])
        return sum(1 for s in lines if rx.match(s.strip()))
    n = sum(1 for s in lines if _CHOICE_LINE.match(s.strip()))
    if n:
        return n
    letters = []
    for s in lines:
        if re.match(r"^[A-G](?:\.|:|\s+-\s+)\s*[A-Z][A-Z0-9 ,'/\-]*(?:\([^)]*\))?:\s*$", s.strip()):
            continue   # a bank heading such as "A - THE MEDICAL PROBLEM:", not a choice
        for m in _CHOICE_LETTER.finditer(s):
            if m.group(1) not in letters:
                letters.append(m.group(1))
    return len(letters)


def verify(row: dict) -> tuple[dict, list[str]]:
    a, b = row["lines"]
    checks: dict = {"heading": heading(row), "title_found": title_found(row), "boundary": boundary_problems(row)}
    disagreements = [f"boundary: {p}" for p in checks["boundary"]]
    if checks["title_found"] is False:
        disagreements.append(f"title {row['title']!r} not found at line {a}")
    if row["kind"] in ("event", "addon"):
        c = count_choices(row)
        checks["choices"] = "unverified" if c is None else "verified" if c == row["choices"] else f"source {c}"
        if c is not None and c != row["choices"]:
            disagreements.append(f"choices: inventory {row['choices']}, source {c}")
            row["choices"] = c
        if row.get("shared_choices"):
            # the event also shows a section's shared question (its own choices are verified above)
            row["own_choices"] = row["choices"]
            row["choices"] = max(row["choices"], row["shared_choices"])
    pools = {}
    for label, spec in row["pools"].items():
        if isinstance(spec, int):
            got = count_bank(a, b, label, row.get("extra_labels", {}).get(label))
            inv = spec
        else:
            inv, at = spec
            got = (count_inline(at) if isinstance(at, int) else count_matching(a, b, at) if isinstance(at, str)
                   else None)
            if got is None and re.fullmatch(r"[A-Z]", label):
                # a lettered outcome set "A1 - ...", "A1. ...", "A1: ..." (one per line)
                got = count_matching(a, b, rf"^\s*{label}\d+\s*(?:\.|:|\s-\s)") or None
        if got is None:
            checks.setdefault("pools_unverified", []).append(label)
            pools[label] = inv
        else:
            pools[label] = got
            if got != inv:
                disagreements.append(f"pool {label}: inventory {inv}, source {got}")
    row["pools"] = pools
    return checks, disagreements


def credit_text(key: str) -> dict:
    who, ranges = CREDITS[key]
    return {"who": who, "lines": [lib.fmt_src(x, y) for x, y in ranges],
            "text": "\n".join(lib.line(n) for x, y in ranges for n in range(x, y + 1))}


def uncovered(rows: list[dict]) -> list[str]:
    covered = set()
    for r in rows:
        covered.update(range(r["lines"][0], r["lines"][1] + 1))
    out, run = [], None
    for n in range(1, lib.SOURCE_LINES + 1):
        miss = n not in covered and not lib.is_blank_or_separator(n)
        if miss and run is None:
            run = [n, n]
        elif miss:
            run[1] = n
        elif run is not None and not lib.is_blank_or_separator(n):
            out.append(lib.fmt_src(*run))
            run = None
    if run:
        out.append(lib.fmt_src(*run))
    return out


def overlaps(rows: list[dict]) -> list[str]:
    spans = sorted((r["lines"][0], r["lines"][1], r["id"]) for r in rows)
    return [f"{x[2]} {x[0]}-{x[1]} overlaps {y[2]} {y[0]}-{y[1]}" for x, y in zip(spans, spans[1:]) if y[0] <= x[1]]


# Disagreements with the inventories found while building this table and settled by reading the source (the source
# wins).  The per-row counts above already carry the source's numbers.
INVENTORY_DISAGREEMENTS = [
    {"lines": "L8384-8461", "what": "V17-E has 7 contests (Cooking, Building, Research / Invention, Sculpture, "
                                    "Story / Song, Farming, Children's Games; headings at L8384, 8403, 8412, 8422, "
                                    "8432, 8444, 8452). Inventory part 3 counted 6, so V17 holds 34 contests, not "
                                    "33, and the collection 177 events and add-ons, not 176."},
    {"lines": "L4594-4595", "what": "The Wall starts at L4595 (its separator); L4594 is the blank line after the "
                                    "material banks. Inventory part 2 said 4594."},
    {"lines": "L7842, L7879, L7938, L7984", "what": "The game-exclusive events are grouped under per-game headings "
                                                   "(VV2 - THE LOST CHILDREN, ...) that the inventory did not "
                                                   "assign; each heading belongs to its group's first event here."},
    {"lines": "L8030, L8900, L9363", "what": "'END OF ...' lines the inventory did not assign: L8030 is its own "
                                             "notes row; L8900 belongs to the Isolan Decathlon, L9363 to the relic "
                                             "notes."},
]


def build() -> dict:
    rows, all_dis = [], []
    for r in ROWS:
        row = json.loads(json.dumps(r, default=list))
        row["pools"] = dict(r["pools"])
        checks, dis = verify(row)
        row.pop("choice_re", None)
        row.pop("extra_labels", None)
        row["credit"] = credit_text(r["credit"])
        row["source_check"] = checks
        rows.append(row)
        all_dis.extend({"id": row["id"], "lines": lib.fmt_src(*row["lines"]), "what": d} for d in dis)
    events = [r for r in rows if r["kind"] in ("event", "addon")]
    return {
        "format": "vvfp-event-collection-manifest", "version": 1,
        "source": str(lib.SOURCE.relative_to(lib.ROOT)).replace("\\", "/"),
        "source_sha256": lib.source_sha256(),
        "counts": {"rows": len(rows), "events": sum(r["kind"] == "event" for r in rows),
                   "addons": sum(r["kind"] == "addon" for r in rows), "banks": sum(r["kind"] == "bank" for r in rows),
                   "notes": sum(r["kind"] == "notes" for r in rows), "events_and_addons": len(events),
                   "series": {s: sum(r["series"] == s for r in rows) for s in SERIES}},
        "disagreements": all_dis,
        "inventory_disagreements": INVENTORY_DISAGREEMENTS,
        "uncovered_lines": uncovered(rows),
        "overlaps": overlaps(rows),
        "rows": rows,
    }


def dumps(data: dict) -> str:
    return json.dumps(data, indent=1, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="fail if data/event_collection/manifest.json is stale")
    args = ap.parse_args(argv)
    text = dumps(build())
    if args.check:
        if not lib.MANIFEST.exists() or lib.MANIFEST.read_text(encoding="utf-8") != text:
            print("manifest.json is stale: run python scripts/collection_manifest.py")
            return 1
        print("manifest.json is current")
        return 0
    lib.MANIFEST.write_text(text, encoding="utf-8", newline="\n")
    data = json.loads(text)
    print(f"wrote {lib.MANIFEST.relative_to(lib.ROOT)}: {data['counts']}")
    print(f"{len(data['disagreements'])} disagreements, uncovered {data['uncovered_lines']}, overlaps {data['overlaps']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
