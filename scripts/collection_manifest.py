"""Build data/event_collection/manifest.json: the Isola Grand Event Collection checklist (design E2).

One row per event, add-on, bank and notes section of the frozen source (scripts/collection_lib.SOURCE), from the three
inventories (lines 1-3519, 3520-6836, 6837-10431; V27 and V28 from the V28 source itself), each row re-verified against the source text itself:
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
    "v27": ("mixed", [(10436, 10438)]),
    "v28": ("mixed", [(10950, 10951)]),
    "ledger": ("ledger", [(1, 91)]),
    # The Companion Anthology (its own lines): the anthology's credit (L4-5) and each volume's or part's own.
    "comp_ledger": ("ledger", [(1, 16)], "companion"),
    "comp_c5a": ("mixed", [(4, 5), (57, 58)], "companion"),
    "comp_c5b": ("mixed", [(4, 5), (1127, 1128)], "companion"),
    "comp_c5c": ("mixed", [(4, 5), (2031, 2032)], "companion"),
    "comp_c5": ("mixed", [(4, 5), (28, 29)], "companion"),
    "comp_lbl": ("mixed", [(4, 5), (3775, 3776)], "companion"),
    "comp_fwk": ("mixed", [(4, 5), (5404, 5405)], "companion"),
    "comp_sss": ("mixed", [(4, 5), (6053, 6053)], "companion"),
    "comp_sss2": ("mixed", [(4, 5), (6771, 6771)], "companion"),
    "comp_cat": ("mixed", [(4, 5), (7088, 7088)], "companion"),
}

SERIES = ("v14_golden_child", "v17_contests", "v18_trials", "v20_crises")
# The Living Catalogue's templates (the same text, the species swapped): each group is one series (the owner,
# 2026-11-14: "Series, such as the Living Catalogue templates, still count as one").
COMPANION_SERIES = ("cat_bodies", "cat_fins", "cat_foliage", "cat_flowers", "cat_magic_fish", "cat_magic_plants",
                    "cat_creatures")
ALL = [1, 2, 3, 4, 5]
# The owner (2026-11-16): chief events run in every game; their chief role prefers The Secret City's robed Tribal Chief
# (cie-v6-binary.md 35).  The V17 sculpture contest stays The Secret City's shore's.
CHIEF_GAMES = ALL
CHIEF_EXCLUSIVE = ("The Child Who Claimed to Be Chief", "The Chief's Impossible Question")

ROWS: list[dict] = []


def R(id, title, games, a, b, kind, section, credit, choices=0, pools=None, effects=(), deaths=False, series=None,
      source=lib.SOURCE_ID, **extra):
    """One manifest row.  pools: {label: n} -- n an int (a bank under that heading), or (n, line) for an inline
    "(a/b/c)" bank on that line, or (n, None) for a count the script cannot locate (unverified).  `source`: the
    frozen source whose lines `a`..`b` are (collection_lib.SOURCES)."""
    if games:
        id = short_id(id, VV1_ID_MAX if 1 in games else ID_MAX)     # its .cieg's path must fit a deep game folder
    ROWS.append(dict(id=id, title=title, games=list(games), lines=[a, b], kind=kind, section=section, credit=credit,
                     choices=choices, pools=dict(pools or {}), effects=list(effects), deaths=deaths, series=series,
                     source=source, **extra))


ID_MAX = 30          # an event id's longest (scripts/build_event_collection_features.py ID_MAX)
VV1_ID_MAX = 22      # ... and in an event A New Home shows (build_event_collection_features.py VV1_ID_MAX)


# Where cutting at a word boundary would leave an id that no longer names its event: the short id to use instead.
SHORT_NAMES = {
    "all_grand_isolan_scholasticon": "all_scholasticon",
    "all_great_beautification": "all_beautification",
    "all_isolan_storytelling": "all_storytelling",
    "all_impossible_invention": "all_invention",
    "all_council_of_conundrums": "all_conundrums",
    "all_panel_of_impossible": "all_panel_standards",
    "all_everybodys_a_winner": "all_everybodys_winner",
    "all_no_good_very_bad_day": "all_very_bad_day",
    "vv1_v14_06_the_song_of_isola": "vv1_v14_06_song_isola",
    "all_v18_03_great_question": "all_v18_03_question",
    "all_v18_04_philosophers_duel": "all_v18_04_duel",
    "all_v18_09_great_trivia_trial": "all_v18_09_trivia",
    "all_v18_isolan_decathlon": "all_v18_decathlon",
    "all_v20_d3_experimental_cure": "all_v20_d3_cure",
}


def short_id(id: str, cap: int = ID_MAX) -> str:
    """A collection id the packager accepts (at most `cap` characters, the game's long-path limit): its SHORT_NAMES
    entry, else drop "the" words, then cut at the last word boundary that fits."""
    if len(id) <= cap:
        return id
    if len(SHORT_NAMES.get(id, "x" * (cap + 1))) <= cap:
        return SHORT_NAMES[id]
    id = re.sub(r"_the(?=_)", "", id)
    while len(id) > cap:
        id = id.rsplit("_", 1)[0]
    return id


def N(id, title, a, b, section, credit="ledger", pools=None, source=lib.SOURCE_ID):
    R(id, title, [], a, b, "notes", section, credit, pools=pools, source=source)


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
R("vv3_chiefs_monumental_speech", "The Chief's Monumental Speech", CHIEF_GAMES, 2996, 3041, "event", "v6", "v6v8", 0,
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
R("vv3_chief_and_the_pearl", "The Chief and the Pearl", CHIEF_GAMES, 4874, 4934, "event", "v9", "v9", 4,
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
    R(short_id(f"vv{_g}_{_slug}"), _t, CHIEF_GAMES if _t in CHIEF_EXCLUSIVE else [_g], _a, _b, "event", "exclusive",
      "exclusive", 2, {},
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
# D1 reads the owner's newer copy in the Living Event Engine file (its own line numbers): the same D1 with the owner's
# outcomes A6-A15, B5-B14 and C4-C37 added (2026-11-15).  Its V28 lines are a notes row.
_D1_LIVING = (8957, 9056)
for _d, _t, _a, _b, _c, _dead in _V20:
    _slug = _V20_SLUGS[_d]
    if _d == "D1":
        R(f"all_v20_{_d.lower()}_{_slug}", _t, ALL, *_D1_LIVING, "event", "v20", "liv_v20", _c, {},
          ["kill", "health_change"], deaths=True, series="v20_crises", source=lib.LIVING_ID)
        N("notes_v20_d1_v28", "Two Lives, One Decision: the V28 text (the event reads the Living Engine file's copy)",
          _a, _b, "v20", "v20")
        continue
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
# V26 (the materials of Isola, old lines 10432-10571) is not in the V28 source: the owner removed it.

# ---- V27 and V28 (the owner's V28 file, 2026-11-14) ---------------------------------------------------------------------
# V27: 57 short events, each eight lines from its heading: "EVENT V27-NNN - Title", AGE/CAST, SETUP, OUTCOME A-C,
# FOLLOW-UP.  Ids at most VV1_ID_MAX (every V27 event is in all five games).
V27_FIRST = 10489
V27_EVENTS = [
    ("all_v27_01_cry", "The Unsolvable Cry"),
    ("all_v27_02_little_grip", "The Little Grip"),
    ("all_v27_03_recognition", "The First Recognition"),
    ("all_v27_04_crawling", "The Crawling Expedition"),
    ("all_v27_05_lullaby", "The Borrowed Lullaby"),
    ("all_v27_06_grove", "The Forbidden Grove"),
    ("all_v27_07_secret", "The Friend's Secret"),
    ("all_v27_08_cruel_joke", "The Cruel Joke"),
    ("all_v27_09_kingdom", "The River Kingdom"),
    ("all_v27_10_supper", "The Missing Child at Supper"),
    ("all_v27_11_legend", "The Hero of the Legend"),
    ("all_v27_12_new_friend", "The New Friend"),
    ("all_v27_13_raft", "The Midnight Raft"),
    ("all_v27_14_proof", "The Dangerous Proof"),
    ("all_v27_15_embarrass", "The Public Embarrassment"),
    ("all_v27_16_swap", "The Apprenticeship Swap"),
    ("all_v27_17_pact", "The Reckless Pact"),
    ("all_v27_18_heartbreak", "The First Heartbreak"),
    ("all_v27_19_beam", "The Faulty Beam"),
    ("all_v27_20_favor", "The Unasked Favor"),
    ("all_v27_21_councilor", "The Loud Councilor"),
    ("all_v27_22_doubt", "The Secret Doubt"),
    ("all_v27_23_watcher", "The Night Watcher"),
    ("all_v27_24_explorer", "The Vanishing Explorer"),
    ("all_v27_25_crossing", "The Last Crossing"),
    ("all_v27_26_teacher", "The Stubborn Teacher"),
    ("all_v27_27_empty_chair", "The Empty Chair"),
    ("all_v27_28_beginning", "The New Beginning"),
    ("all_v27_29_route", "The Forgotten Route"),
    ("all_v27_30_basket", "The Creature in the Basket"),
    ("all_v27_31_guardian", "The Fierce Little Guardian"),
    ("all_v27_32_fish", "The Fish That Followed"),
    ("all_v27_33_insect", "The Unusual Insect"),
    ("all_v27_34_pet", "The Unwelcome Pet"),
    ("all_v27_35_pets_last", "The Pet's Last Morning"),
    ("all_v27_36_hatchling", "The Strange Hatchling"),
    ("all_v27_37_returned", "The Animal That Returned"),
    ("all_v27_38_rough_patch", "The Parents' Rough Patch"),
    ("all_v27_39_marriage", "The Quiet Marriage"),
    ("all_v27_40_siblings", "The Sibling Rivalry"),
    ("all_v27_41_promise", "The Childhood Promise"),
    ("all_v27_42_special", "The Special Friend"),
    ("all_v27_43_lovers", "The Lovers' Argument"),
    ("all_v27_44_courtship", "The Awkward Courtship"),
    ("all_v27_45_coworkers", "The Rival Coworkers"),
    ("all_v27_46_ally", "The Ally Who Disagreed"),
    ("all_v27_47_grief", "The Neighbor's Grief"),
    ("all_v27_48_mentor", "The Unlikely Mentor"),
    ("all_v27_49_chosen", "The Chosen Family"),
    ("all_v27_50_reunion", "The Reunion That Hurt"),
    ("all_v27_51_apology", "The Caregiver's Apology"),
    ("all_v27_52_unexpected", "The Friendship Nobody Expected"),
    ("all_v27_53_shore", "The Unmarked Shore"),
    ("all_v27_54_fever", "The Fever After the Expedition"),
    ("all_v27_55_deep_pool", "The Legend of the Deep Pool"),
    ("all_v27_56_empty_boat", "The Boat That Came Back Empty"),
    ("all_v27_57_bell", "The Forbidden Bell"),
]
N("notes_v27_header", "V27 - All ages, personality, relationships and consequences: credits and global engine rules",
  10433, 10487, "v27", "v27")
for _i, (_id, _title) in enumerate(V27_EVENTS):
    R(_id, _title, ALL, V27_FIRST + 8 * _i, V27_FIRST + 8 * _i + 6, "event", "v27", "v27", 0)
N("notes_v27_end", "END OF V27 ADDITION", 10945, 10945, "v27", "v27")
N("notes_v28_addendum", "V28 Addendum - consequences that follow the villagers, and the retrofit instructions", 10948,
  11125, "v28", "v28")

# ---- The Companion Anthology (the second source, collection_lib.COMPANION; its own line numbers) ----------------------
#
# Five volumes, 749 events (the anthology's contents, L7-14).  Its notes sections (headers, rules, credits, the
# implementation prompts) are the rows below, by hand; its events are found by their headings inside each volume's
# lines.  An event runs from its heading -- or from the group heading just above it ("POTTERY", "TEXTILES, CRAFTS AND
# HOMES" with its rule lines), which its file's ledger takes as structural -- to its last line before the next event,
# the next notes row or the volume's end.  Files go in data/event_collection/companion/<section>/<id>.json.

COMP = lib.COMPANION_ID
COMPANION_NOTES = [
    ("cnotes_header", "Companion anthology: title, credits and contents", 1, 16, "c5", "comp_ledger"),
    ("cnotes_c5_rules", "Companion Volume 5: header, contents and rules", 20, 47, "c5", "comp_c5"),
    ("cnotes_c5a_notes", "Vol 1 Part 1: credits, canon and the event format", 51, 84, "c5", "comp_c5a"),
    ("cnotes_c5a_end", "Vol 1 Part 1: end", 1117, 1117, "c5", "comp_c5a"),
    ("cnotes_c5b_notes", "Vol 1 Part 2: credits and design notes", 1121, 1140, "c5", "comp_c5b"),
    ("cnotes_c5b_end", "Vol 1 Part 2: end", 2017, 2017, "c5", "comp_c5b"),
    ("cnotes_c5c_notes", "Vol 1 Part 3: credits and the volume's rules", 2021, 2038, "c5", "comp_c5c"),
    ("cnotes_c5c_end", "Vol 1 Part 3: end", 2653, 2653, "c5", "comp_c5c"),
    ("cnotes_c5d_header", "Vol 1 Part 4: heading", 2657, 2659, "c5", "comp_c5"),
    ("cnotes_c5d_end", "Vol 1 Part 4: end", 3310, 3310, "c5", "comp_c5"),
    ("cnotes_c5e_header", "Vol 1 Part 5: heading", 3313, 3317, "c5", "comp_c5"),
    ("cnotes_c5e_pool_engine", "Vol 1 Part 5: further tribal activity pool and engine notes", 3745, 3762, "c5",
     "comp_c5"),
    ("cnotes_lbl_rules", "The Lives Between Legends: credits, engine rules and implementation prompt", 3766, 3790,
     "lbl", "comp_lbl"),
    ("cnotes_lbl_end", "The Lives Between Legends: end", 5393, 5393, "lbl", "comp_lbl"),
    ("cnotes_fwk_rules", "The Four Ways of Knowing: credits, rules and Part I", 5397, 5415, "fwk", "comp_fwk"),
    ("cnotes_fwk_part2", "The Four Ways of Knowing: Part II", 5857, 5858, "fwk", "comp_fwk"),
    ("cnotes_fwk_part3", "The Four Ways of Knowing: Part III retrofit prompt", 6040, 6043, "fwk", "comp_fwk"),
    ("cnotes_sss_notes", "Stone, Spirit, Strangers: credits and integration notes", 6046, 6067, "sss", "comp_sss"),
    ("cnotes_sss_prompt", "Stone, Spirit, Strangers: expansion prompt", 6759, 6765, "sss", "comp_sss"),
    ("cnotes_sss2_rules", "Volume II, The Inner Lives of Isola: credits and narration rules", 6768, 6773, "sss",
     "comp_sss2"),
    ("cnotes_sss2_end", "Volume II: retroactive integration note", 7075, 7079, "sss", "comp_sss2"),
    ("cnotes_cat_rules", "The Living Catalogue: credits, rules and taxonomy", 7082, 7107, "cat", "comp_cat"),
    ("cnotes_cat_prompt", "The Living Catalogue: implementation prompt", 8957, 8961, "cat", "comp_cat"),
]

# (key, first line, last line, heading regex, id prefix, section, credit, choice_re or None, expected choices)
# expected choices: an int, or a function of the event's lines (the format the event uses).
_NONE = r"^(?!)"
_LETTERS = r"^[A-D]\.\s"          # an indented " A. ..." choice line (the line is stripped first)


def _p2_choices(text: str) -> int:
    return 2 if "TWO CHOICES:" in text else 3 if "THREE CHOICES:" in text else 0


def _p3_choices(text: str) -> int:
    return 2 if re.search(r"^CHOICES:\s*$", text, re.M) else 0


COMPANION_VOLUMES = [
    ("c5a", 85, 1116, r"^EVENT (\d{3}) — (.+)$", "c5a", "c5", "comp_c5a", _LETTERS, 3),
    ("c5b", 1141, 2016, r"^EVENT (\d{3}) — (.+)$", "c5b", "c5", "comp_c5b", _LETTERS, _p2_choices),
    ("c5c", 2039, 2652, r"^SMALL LIFE EVENT (\d{3}) — (.+)$", "c5c", "c5", "comp_c5c", _LETTERS, _p3_choices),
    ("c5d", 2660, 3309, r"^EVENT N(\d{3}) — (.+)$", "c5dn", "c5", "comp_c5", None, 0),
    ("c5e", 3318, 3744, r"^EVENT V(\d{3}) — (.+)$", "c5ev", "c5", "comp_c5", _NONE, 0),
    ("lbl", 3791, 5392, r"^EVENT (\d{3}) — (.+)$", "lbl", "lbl", "comp_lbl", r"^PLAYER RESPONSE [A-C]\b", 3),
    ("fwk", 5416, 6039, r"^EVENT (\d{3}) — (.+)$", "fwk", "fwk", "comp_fwk", None, 4),
    ("sss", 6068, 7074, r"^EVENT (\d{3}): (.+)$", "sss", "sss", "comp_sss", None, 3),
    ("cat", 7108, 8956, r"^EVENT (\d{3}) — (.+)$", "cat", "cat", "comp_cat", None, 4),
]
# Part 5's V060 offers three numbered player options (L3728-3731).
COMPANION_CHOICES = {"c5ev060": (r"^[1-3]\.\s", 3)}
CAT_SERIES = [(1, 28, "cat_bodies"), (29, 56, "cat_fins"), (57, 79, "cat_foliage"), (80, 116, "cat_flowers"),
              (117, 123, "cat_magic_fish"), (124, 129, "cat_magic_plants"), (130, 134, "cat_creatures")]
# The source's title where it carries a designer suffix (the owner may rename it: inventory Q7).
COMPANION_TITLES = {"c5ev060": "How Did We Get Here?"}
# Where the word rule (companion_slug) would leave an id that no longer names its event: the id to use instead.
COMPANION_IDS: dict[str, str] = {
    "c5a007": "c5a007_transmutation", "c5a015": "c5a015_hidden_garden", "c5a018": "c5a018_lab_spill",
    "c5a026": "c5a026_bridge_calc", "c5a028": "c5a028_diagnosis", "c5a029": "c5a029_first_patient",
    "c5a039": "c5a039_outrigger", "c5a042": "c5a042_vessel_no_oars", "c5a044": "c5a044_interpreter",
    "c5a045": "c5a045_cartographer", "c5a046": "c5a046_mechanist", "c5a048": "c5a048_congress",
    "c5c004": "c5c004_empty_nest", "c5c009": "c5c009_pebbles", "c5c010": "c5c010_goodbye",
    "c5c012": "c5c012_ordinary_win", "c5c014": "c5c014_seatmates", "c5c017": "c5c017_brave",
    "c5c021": "c5c021_tidy_doorsteps", "c5c024": "c5c024_real_friend", "c5c025": "c5c025_small_sandals",
    "c5c026": "c5c026_unasked", "c5c027": "c5c027_sea_no_answer", "c5c028": "c5c028_anniversary",
    "c5b006": "c5b006_hard_question", "c5b011": "c5b011_watching_over", "c5b030": "c5b030_fairness",
    "c5b035": "c5b035_resemblance", "c5c032": "c5c032_same_gesture", "c5c033": "c5c033_pot_washer",
    "c5c038": "c5c038_after_festival", "c5c046": "c5c046_morning_after",
    "cat125": "cat125_knowledge", "cat132": "cat132_pufferfish",
    "sss006": "sss006_between_names", "sss010": "sss010_reads_slowly", "sss012": "sss012_argument_help",
    "sss055": "sss055_argument_chair", "sss057": "sss057_was_wrong", "sss060": "sss060_changed_mind",
    "sss062": "sss062_shortcut",
    "sss086": "sss086_heard_too_much", "sss089": "sss089_cheerfulness",
    "sss094": "sss094_one_instruction", "cat139": "cat139_orchid_memory", "cat146": "cat146_masterpiece",
    "cat151": "cat151_ants",
    # K7: The Four Ways of Knowing
    "fwk004": "fwk004_doorway_dream", "fwk005": "fwk005_knows_my_name", "fwk007": "fwk007_forest_memory",
    "fwk009": "fwk009_unanswered_pray", "fwk015": "fwk015_silent_reef", "fwk019": "fwk019_reflection",
    "fwk020": "fwk020_fire_not_catch", "fwk025": "fwk025_child_questions", "fwk030": "fwk030_festival_signs",
    "fwk035": "fwk035_two_stories", "fwk039": "fwk039_no_one_answers", "fwk041": "fwk041_trembling_hands",
    "fwk043": "fwk043_hates_research", "fwk046": "fwk046_lost_apprentice", "fwk047": "fwk047_scholar_error",
    "fwk050": "fwk050_explorer_risk", "fwk054": "fwk054_rival_invite", "fwk055": "fwk055_skill_fading",
    "fwk058": "fwk058_surpassed",
}

# Companion events limited to some games (the lead, 2026-11-14): an event where a magician acts is VV3-VV5 only
# (magic is VV3-VV5 lore); a magician mentioned in passing keeps every game.
COMPANION_GAMES: dict[str, list[int]] = {"sss032": [3, 4, 5], "sss043": [3, 4, 5], "sss045": [3, 4, 5],
                                         # K9: the Living Catalogue's magic fish (a magician observes, choice C) and
                                         # The Conch With Two Voices (a magician claims it answers questions)
                                         **{f"cat{n}": [3, 4, 5] for n in (117, 118, 119, 120, 121, 122, 123, 150)}}


def companion_subject(title: str) -> str:
    """The words an id names: the species of a Living Catalogue template, else the title."""
    for rx in (r"^A Record of the (.+)$", r"^The (.+?)(?: Fin)? Fin Question$", r"^The (.+) (?:Study|Bloom)$",
               r"^Magic (?:Fish|Plant) of (.+?):", r"^([^:]+): (?:A Question of Cause|The Uncertain Gift|"
               r"A Living Record)$"):
        m = re.match(rx, title)
        if m:
            return m.group(1) + (" fin" if "Fin Question" in title and not m.group(1).endswith("Fin") else "")
    return title
SMALL_WORDS = {"a", "an", "and", "as", "at", "by", "for", "in", "of", "on", "or", "the", "to", "with", "from", "into"}


def title_case(t: str) -> str:
    """An all-capitals heading (The Four Ways of Knowing) in title case; any other title as written."""
    if t != t.upper():
        return t
    words = t.lower().split(" ")
    return " ".join(w if (i and w in SMALL_WORDS) else w[:1].upper() + w[1:] for i, w in enumerate(words))


SLUG_STOP = {"the", "a", "an", "of", "in", "that", "to", "and", "who", "with", "for", "on", "at", "by", "from", "is",
             "it", "its", "was", "be", "into", "or", "as", "than", "no", "not"}
SLUG_GENERIC = {"great", "first", "little", "small", "new", "old", "very", "unexpected", "quiet", "day", "one",
                "almost", "too", "last", "different", "kind", "real", "unlikely", "strange", "secret", "single"}


def companion_slug(title: str, room: int) -> str:
    """The title's words for an id: no little words, then no generic ones while too long, then cut at a word; at
    most `room` characters (an A New Home id is at most 22 with its prefix)."""
    t = lib.normalize_source_text(title).lower().replace("'s ", " ").replace("'", "")
    t = re.sub(r"\(.*?\)", "", t)
    words = [w for w in re.split(r"[^a-z0-9]+", t) if w]
    words = [w for w in words if w not in SLUG_STOP] or words
    if len("_".join(words)) > room:
        words = [w for w in words if w not in SLUG_GENERIC] or words
    while len(words) > 1 and len("_".join(words)) > room:
        words = words[:-1]
    return "_".join(words)[:room]


def _is_heading_line(s: str) -> bool:
    """A group heading's line (capitals only, or a separator): part of the next event's block."""
    s = s.strip()
    return bool(s) and (lib.is_separator(s) or (s == s.upper() and re.search(r"[A-Z]", s) is not None))


def _companion_rows() -> None:
    with lib.use_source(COMP):
        notes = sorted((a, b) for _, _, a, b, _, _ in COMPANION_NOTES)
        in_notes = {n for a, b in notes for n in range(a, b + 1)}
        for nid, title, a, b, section, credit in COMPANION_NOTES:
            N(nid, title, a, b, section, credit, source=COMP)
        for key, first, last, heading, prefix, section, credit, choice_re, want in COMPANION_VOLUMES:
            rx = re.compile(heading)
            heads = [n for n in range(first, last + 1) if rx.match(lib.line(n))]
            starts = []
            for h in heads:                       # the block: the group heading above the event belongs to it
                s, n = h, h - 1
                while n >= first and n not in in_notes and n not in heads and (
                        not lib.line(n).strip() or _is_heading_line(lib.line(n))):
                    if lib.line(n).strip():
                        s = n
                    n -= 1
                starts.append(s)
            for i, h in enumerate(heads):
                stop = starts[i + 1] if i + 1 < len(heads) else last + 1
                stop = min([stop] + [a for a, _ in notes if h < a < stop])
                e = stop - 1
                while lib.is_blank_or_separator(e):
                    e -= 1
                m = rx.match(lib.line(h))
                num, src_title = m.group(1), lib.normalize_source_text(m.group(2)).strip()
                eid = f"{prefix}{num.lower()}"
                title = COMPANION_TITLES.get(eid, title_case(src_title))
                text = "\n".join(lib.line(n) for n in range(h, e + 1))
                c_re, c_want = COMPANION_CHOICES.get(eid, (choice_re, want))
                series = None
                if key == "cat":
                    series = next(s for lo, hi, s in CAT_SERIES if lo <= int(num) <= hi) \
                        if int(num) <= CAT_SERIES[-1][1] else None
                cr = "comp_sss2" if key == "sss" and int(num) >= 68 else credit
                extra = {"choice_re": c_re} if c_re else {}
                subject = companion_subject(COMPANION_TITLES.get(eid, src_title))
                R(COMPANION_IDS.get(eid) or f"{eid}_{companion_slug(subject, VV1_ID_MAX - len(eid) - 1)}",
                  title, COMPANION_GAMES.get(eid, ALL), starts[i], e,
                  "event", section, cr, c_want(text) if callable(c_want) else c_want, series=series, source=COMP,
                  **extra)


_companion_rows()

# ---- The Living Event Engine's fixed event volumes (the third source, collection_lib.LIVING; its own line numbers) --
#
# The owner's all-in-one file (2026-11-14) holds, after the Grand and Companion parts, volumes of fixed events: a
# heading "MED-01 — THE BORROWED ORGAN", the setup ("SETUP:" or bare), three choices A-C, each with two outcomes
# (A1, A2 ...), and a CALLBACKS line.  Only the volumes listed here are rows (the rest of the file is the Living
# Event bank's, data/living_events/); "uncovered" is checked inside these volumes.  Files go in
# data/event_collection/living/<section>/<id>.json.

LIV = lib.LIVING_ID
CREDITS.update({
    "liv_med": ("mixed", [(1, 2), (20206, 20206)], LIV),
    "liv_life": ("mixed", [(1, 2), (20625, 20627)], LIV),
    "liv_circle": ("mixed", [(1, 2), (21229, 21230)], LIV),
    # LV-B's volumes credit nobody in their own headings: the file's credit only
    "liv_peoples": ("mixed", [(1, 2)], LIV),
    "liv_unseen": ("mixed", [(1, 2)], LIV),
    "liv_ways": ("mixed", [(1, 2)], LIV),
    "liv_auth": ("mixed", [(1, 2)], LIV),
    # D1 (Two Lives, One Decision) from this file's copy of V20: V20's own credit block (the V28 file's L8906-8909)
    "liv_v20": ("mixed", [(8913, 8916)], LIV),
})
# (prefix in the source, first and last line of the volume's events, id prefix, section, credit, its notes rows)
LIVING_VOLUMES = [
    ("MED", 20219, 20620, "lvmed", "lv_med", "liv_med",
     [("lnotes_med_rules", "Experimental Medicine, Last Resorts and Comfort Care: credits and implementation rules",
       20201, 20217)]),
    ("LIFE", 20642, 21225, "lvlife", "lv_life", "liv_life",
     [("lnotes_life_rules", "The Healer's Hands, the Farmer's Fields, and the Weaver's Dreams: heading and rules",
       20624, 20639)]),
    ("CIRCLE", 21244, 21645, "lvcir", "lv_circle", "liv_circle",
     [("lnotes_circle_rules", "The Circle of Life, Rights, and Remembrance: heading and guidance", 21228, 21242)]),
    ("PEOPLES", 21665, 22160, "lvppl", "lv_peoples", "liv_peoples",
     [("lnotes_peoples_rules", "Colors, Masks, Peoples and Choice: heading and implementation rules", 21649, 21663)]),
    ("UNSEEN", 22180, 22685, "lvuns", "lv_unseen", "liv_unseen",
     [("lnotes_unseen_rules", "The Unseen Horizon, Cryptids, and the Silent Gods: heading and canon rules",
       22164, 22177)]),
    ("WAYS", 22704, 23310, "lvway", "lv_ways", "liv_ways",
     [("lnotes_ways_rules", "The Many Ways of Isola: heading and rules", 22688, 22702)]),
    ("AUTH", 23331, 23809, "lvauth", "lv_auth", "liv_auth",
     [("lnotes_auth_rules", "The Weight of a Name: heading and implementation notes", 23314, 23329)]),
]
# Volumes whose events have four choices (A-D); the others have three (A-C).
LIVING_CHOICES: dict[str, int] = {"WAYS": 4, "AUTH": 4}
# Events limited to some games: a Magic practitioner acts (magic is VV3-VV5 lore; the lead, 2026-11-14).
LIVING_GAMES: dict[str, list[int]] = {"lvmed19": [3, 4, 5]}
# LV-B: a Magic master or healer acts in the setup itself (VV3-VV5; an event whose magic is only one choice keeps every
# game and limits that choice); the source's "VV5 ONLY" events (masks, Heathens, the neighbouring community).
LIVING_GAMES.update({"lvway13": [3, 4, 5], "lvway35": [3, 4, 5]})
LIVING_GAMES.update({f"lvppl{n:02d}": [5] for n in (6, 7, 8, 9, 10, 11, 12, 13, 14, 22, 23, 25, 26, 32, 33, 34)})
LIVING_GAMES.update({"lvauth17": [5], "lvauth18": [5]})
LIVING_IDS: dict[str, str] = {
    "lvmed04": "lvmed04_draught", "lvmed30": "lvmed30_animal_trial", "lvmed31": "lvmed31_choose_healer",
    "lvlife02": "lvlife02_draught", "lvlife03": "lvlife03_reed_breath", "lvlife29": "lvlife29_new_clothes",
    "lvlife30": "lvlife30_shell_robe", "lvlife37": "lvlife37_winter_cloak", "lvcir14": "lvcir14_tide_go",
    "lvcir19": "lvcir19_departed", "lvcir27": "lvcir27_stranger", "lvcir31": "lvcir31_whale",
}


def living_span() -> list[tuple[int, int]]:
    """The line ranges the living rows cover (notes and events): where "uncovered" is checked."""
    out = []
    for _, first, last, _, _, _, notes in LIVING_VOLUMES:
        out += [(a, b) for _, _, a, b in notes] + [(first, last)]
    return out + [_D1_LIVING]


def _living_rows() -> None:
    with lib.use_source(LIV):
        for key, first, last, prefix, section, credit, notes in LIVING_VOLUMES:
            for nid, title, a, b in notes:
                N(nid, title, a, b, section, credit, source=LIV)
            rx = re.compile(r"^" + key + r"-(\d+) — (.+)$")
            heads = [n for n in range(first, last + 1) if rx.match(lib.line(n))]
            for i, h in enumerate(heads):
                e = (heads[i + 1] if i + 1 < len(heads) else last + 1) - 1
                while lib.is_blank_or_separator(e):
                    e -= 1
                m = rx.match(lib.line(h))
                num, src_title = m.group(1), lib.normalize_source_text(m.group(2)).strip()
                # a game tag on the heading ("(VV5 ONLY)", "(GUARDIANS OF ISOLA VV5 ONLY)") is the row's games
                src_title = re.sub(r"\s*\((?:GUARDIANS OF ISOLA )?VV\d ONLY\)$", "", src_title)
                eid = f"{prefix}{num}"
                nc = LIVING_CHOICES.get(key, 3)
                R(LIVING_IDS.get(eid) or f"{eid}_{companion_slug(src_title, VV1_ID_MAX - len(eid) - 1)}",
                  title_case(src_title), LIVING_GAMES.get(eid, ALL), h, e, "event", section, credit, nc,
                  source=LIV, choice_re=r"^[A-C]\.\s" if nc == 3 else r"^[A-D]\.\s")


_living_rows()

# ---- Beyond the Horizon (the fourth source, collection_lib.HORIZON; its own line numbers) ------------------------------
#
# The owner's separate companion anthology "Isola - Beyond the Horizon" (2026-11-15): The World We Imagine (EVENT
# 001-040, in five PARTs) and Expansion Volume II (EVENT 041-080).  Each event: a heading "EVENT 001 — THE OTHER
# BREAKFAST", "SETUP: ...", three choices A-C, each with two alternate outcomes (" A1. ...", " A2. ..."), and at times a
# "Content note: ..." or "VV3: ..." line.  The PART headings, the rules and the flavor/continuity notes are notes rows.
# Series (the lead, 2026-11-15: "one series per Part, so each Part counts as one in the rare roll"): each of the five
# PARTs of volume I is a series, and Expansion Volume II (which has no PARTs) is one more.

HZ = lib.HORIZON_ID
CREDITS.update({
    "hz_world": ("mixed", [(1, 3)], HZ),
    "hz_vol2": ("mixed", [(1, 3), (546, 547)], HZ),
})
HORIZON_NOTES = [
    ("hznotes_intro", "Beyond the Horizon: title, creative premise, editorial and implementation rules, format", 1, 17,
     "hz_world", "hz_world"),
    ("hznotes_part1", "Beyond the Horizon: Part I heading", 20, 20, "hz_world", "hz_world"),
    ("hznotes_part2", "Beyond the Horizon: Part II heading", 121, 121, "hz_world", "hz_world"),
    ("hznotes_part3", "Beyond the Horizon: Part III heading", 221, 221, "hz_world", "hz_world"),
    ("hznotes_part4", "Beyond the Horizon: Part IV heading", 335, 335, "hz_world", "hz_world"),
    ("hznotes_part5", "Beyond the Horizon: Part V heading", 426, 426, "hz_world", "hz_world"),
    ("hznotes_flavor", "Beyond the Horizon: game-specific flavor inserts, continuity threads and the volume's end",
     527, 542, "hz_world", "hz_world"),
    ("hznotes_vol2", "Beyond the Horizon: Expansion Volume II heading and creative and canon guidance", 546, 584,
     "hz_vol2", "hz_vol2"),
    ("hznotes_vol2_end", "Beyond the Horizon: Expansion Volume II continuity threads and end", 1068, 1080,
     "hz_vol2", "hz_vol2"),
]
# (first line of the PART's events, series) in source order; Expansion Volume II from L587
HORIZON_SERIES = [(23, "hz_part1"), (124, "hz_part2"), (224, "hz_part3"), (338, "hz_part4"), (429, "hz_part5"),
                  (587, "hz_vol2")]
HORIZON_SERIES_NAMES = tuple(s for _, s in HORIZON_SERIES)
HORIZON_EVENTS = (23, 1065)
# Where the title's first words would not name the event: the id to use instead (at most 22 characters).
HORIZON_IDS = {
    "hz002": "hz002_children_ask_why", "hz003": "hz003_come_home", "hz005": "hz005_mourn_as_we_do",
    "hz006": "hz006_day_unremarkable", "hz008": "hz008_celebration", "hz010": "hz010_city_never_sleeps",
    "hz012": "hz012_job_no_one_sees", "hz014": "hz014_sky_travelers", "hz019": "hz019_unseen_illness",
    "hz021": "hz021_prevention", "hz022": "hz022_false_stars", "hz027": "hz027_unseen_line",
    "hz029": "hz029_being_different", "hz031": "hz031_wants_to_leave", "hz032": "hz032_cannot_stop",
    "hz034": "hz034_unseen_animal", "hz038": "hz038_too_much_little", "hz040": "hz040_wonder_about_us",
    "hz045": "hz045_construct_suffer", "hz050": "hz050_invisible_library", "hz051": "hz051_moving_portraits",
    "hz055": "hz055_city_waste", "hz056": "hz056_never_goes_dark", "hz072": "hz072_under_glass",
    "hz073": "hz073_festival_strangers", "hz074": "hz074_dream_sold", "hz075": "hz075_many_families",
    "hz076": "hz076_machine_rights",
}


def _horizon_rows() -> None:
    with lib.use_source(HZ):
        for nid, title, a, b, section, credit in HORIZON_NOTES:
            N(nid, title, a, b, section, credit, source=HZ)
        starts = sorted(a for _, _, a, _, _, _ in HORIZON_NOTES)
        rx = re.compile(r"^EVENT (\d{3}) — (.+)$")
        first, last = HORIZON_EVENTS
        heads = [n for n in range(first, last + 1) if rx.match(lib.line(n))]
        for i, h in enumerate(heads):
            stop = heads[i + 1] if i + 1 < len(heads) else last + 1
            stop = min([stop] + [a for a in starts if h < a < stop])
            e = stop - 1
            while lib.is_blank_or_separator(e):
                e -= 1
            m = rx.match(lib.line(h))
            num, src_title = m.group(1), lib.normalize_source_text(m.group(2)).strip()
            eid = f"hz{num}"
            vol2 = int(num) > 40
            series = [s for a, s in HORIZON_SERIES if a <= h][-1]
            R(HORIZON_IDS.get(eid) or f"{eid}_{companion_slug(src_title, VV1_ID_MAX - len(eid) - 1)}",
              title_case(src_title), ALL, h, e,
              "event", "hz_vol2" if vol2 else "hz_world", "hz_vol2" if vol2 else "hz_world", 3, series=series,
              source=HZ, choice_re=r"^[A-C]\.\s")


_horizon_rows()

# ---- Role Models and Good Examples (the fifth source, collection_lib.ROLEMODELS; its own line numbers) --------------
#
# The owner's "Role Models and Good Examples — 40 New Isola Events" (2026-11-15): one event per line, "EVENT RM-01 —
# THE FAIR SHARE SETUP: ... A. ... A1. ... A2. ... B. ... D2. ..." (four choices A-D, two outcomes each).  Lines 1-3
# (title and introduction) and 85 (closing) are notes rows.  No series: every event is drawn on its own.

RMS = lib.ROLEMODELS_ID
CREDITS.update({"rm": ("mixed", [(1, 3)], RMS)})
ROLEMODEL_IDS = {"rm38": "rm38_apprentice_noticed", "rm40": "rm40_example_no_one"}


def _rolemodel_rows() -> None:
    with lib.use_source(RMS):
        N("rmnotes_intro", "Role Models and Good Examples: title and introduction", 1, 3, "rm", "rm", source=RMS)
        N("rmnotes_end", "Role Models and Good Examples: closing note", 85, 85, "rm", "rm", source=RMS)
        rx = re.compile(r"^EVENT RM-(\d{2}) — (.+?) SETUP: ")
        for n in range(4, 85):
            m = rx.match(lib.line(n))
            if not m:
                continue
            num, src_title = m.group(1), lib.normalize_source_text(m.group(2)).strip()
            eid = f"rm{num}"
            R(ROLEMODEL_IDS.get(eid) or f"{eid}_{companion_slug(src_title, VV1_ID_MAX - len(eid) - 1)}",
              title_case(src_title), ALL, n, n,
              "event", "rm", "rm", 4, source=RMS)


_rolemodel_rows()

# ---- The owner-approved drafts, set A (2026-11-15; collection_lib.DRAFTS_A, each file its own source) ---------------
#
# Inner Life I-X (events 1-200), What's That Doing Here (WD-01..50), Luck, Omens and Lavastones (LO-01..50).  Each
# event: a heading "12. The Wrong Dream" / "WD-01. ..." / "LO-01. ...", a "(picks ...)" casting line, the setup, then
# each choice's label line "Label:" and its outcome (none for a single popup).  The lines before the first heading
# (the draft's title, its notes to the owner, Part II's ChatGPT preamble) and the closing NOTES FOR THE OWNER (Part II:
# "A few more directions ...") are notes rows.  Series (the lead, 2026-11-15): one per file, so each file counts as one
# draw in the rare roll.  Ids: il001_, wd01_, lo01_ and a slug of the title.

DRAFT_HEAD_RE = re.compile(r"^(?:(WD|LO)-)?(\d{1,3})\.\s+(.+)$")
DRAFT_LABEL_RE = r'^[A-Z(][^.!?"]{0,100}:$'
DRAFT_END_RE = re.compile(r"^(?:NOTES FOR THE OWNER|A few more directions for the next batch)")
# (first, last) credit lines of each draft: its title line(s)
DRAFT_CREDIT_LINES = {"da_il02": (15, 17)}
DRAFT_IDS: dict[str, str] = {}


def _draft_rows() -> None:
    for sid in lib.DRAFTS_A:
        with lib.use_source(sid):
            n_all = lib.n_lines()
            heads = [n for n in range(1, n_all + 1) if DRAFT_HEAD_RE.match(lib.line(n).rstrip("\r"))]
            end = next(n for n in range(heads[-1], n_all + 1) if DRAFT_END_RE.match(lib.line(n)))
            CREDITS[sid] = ("mixed", [DRAFT_CREDIT_LINES.get(sid, (1, 1))], sid)
            a_end = heads[0] - 1
            while lib.is_blank_or_separator(a_end):
                a_end -= 1
            N(f"danotes_{sid[3:]}_intro", f"Draft {sid}: title, notes to the owner", 1, a_end, sid, sid, source=sid)
            N(f"danotes_{sid[3:]}_end", f"Draft {sid}: closing notes to the owner", end, n_all, sid, sid, source=sid)
            for i, h in enumerate(heads):
                stop = heads[i + 1] if i + 1 < len(heads) else end
                e = stop - 1
                while lib.is_blank_or_separator(e):
                    e -= 1
                m = DRAFT_HEAD_RE.match(lib.line(h).rstrip("\r"))
                pre, num, src_title = m.group(1), int(m.group(2)), lib.normalize_source_text(m.group(3)).strip()
                eid = f"{pre.lower()}{num:02d}" if pre else f"il{num:03d}"
                choices = sum(1 for n in range(h, e + 1)
                              if re.match(DRAFT_LABEL_RE, lib.normalize_source_text(lib.line(n)).strip()))
                R(DRAFT_IDS.get(eid) or f"{eid}_{companion_slug(src_title, VV1_ID_MAX - len(eid) - 1)}",
                  title_case(src_title), ALL, h, e, "event", sid, sid, choices, series=sid, source=sid,
                  choice_re=DRAFT_LABEL_RE)


_draft_rows()


# ---- The owner-approved draft event files, group B (collection_lib.DRAFTS_B; each file its own source) ---------------
#
# "New Events - <Topic> (draft for owner).txt" (2026-11-15): lines 1-5 (title, premise, how to read it) and the closing
# "NOTES FOR THE OWNER" block are notes rows; each "HUM-01. Title" heading starts an event (casting line, setup, two
# "Label:" lines each followed by its outcome; a few are one popup with no choice).  One series per file (each file
# counts as one draw in the rare roll).  Built by scripts/drafts_b/gen_drafts_b.py.

for _sid, (_topic, _n, _sec, _pre) in lib.DRAFTS_B.items():
    CREDITS[_sec] = ("mixed", [(1, 3)], _sid)
DRAFTS_B_SERIES = {sid: v[2] for sid, v in lib.DRAFTS_B.items()}      # source id -> its one series (the section)


def _drafts_b_rows() -> None:
    for sid, (topic, _n, sec, pre) in lib.DRAFTS_B.items():
        with lib.use_source(sid):
            heads = [n for n in range(1, lib.n_lines() + 1) if re.match(rf"^{pre}-\d\d\. ", lib.line(n))]
            notes = next(n for n in range(1, lib.n_lines() + 1) if lib.line(n).startswith("NOTES FOR THE OWNER"))
            last = max(n for n in range(1, lib.n_lines() + 1) if lib.line(n).strip())
            N(f"{sec}_notes_intro", f"{topic}: title, premise and how to read the draft", 1, 5, sec, sec, source=sid)
            N(f"{sec}_notes_end", f"{topic}: notes for the owner", notes, last, sec, sec, source=sid)
            for i, h in enumerate(heads):
                stop = heads[i + 1] if i + 1 < len(heads) else notes
                e = stop - 1
                while lib.is_blank_or_separator(e):
                    e -= 1
                m = re.match(rf"^{pre}-(\d\d)\. (.+)$", lib.line(h))
                num, src_title = m.group(1), lib.normalize_source_text(m.group(2)).strip()
                eid = f"{pre.lower()}{num}"
                nc = 2 if e - h > 3 else 0
                R(f"{eid}_{companion_slug(src_title, VV1_ID_MAX - len(eid) - 1)}",
                  lib.title_case_label(src_title.replace('"', '')),              # a title holds no '"' (gap G6)
                  ALL, h, e, "event", sec, sec, nc, series=sec, source=sid, choice_re=r"^[^.!?]{1,80}:$")


_drafts_b_rows()

# ---- The owner-approved draft event files, group C (collection_lib.DRAFTS_C), wired as group B ------------------------
#
# The same shape, plus: an event may offer three choices (HEA-15), and a heading's "(VV5 only)" tag is a game note
# (the row is New Believers only; the tag is cut from the title).  Built by scripts/drafts_c/gen_drafts_c.py.

for _sid, (_topic, _n, _sec, _pre) in lib.DRAFTS_C.items():
    CREDITS[_sec] = ("mixed", [(1, 3)], _sid)
DRAFTS_C_SERIES = {sid: v[2] for sid, v in lib.DRAFTS_C.items()}      # source id -> its one series (the section)
DRAFTS_C_VV5_TAG = " (VV5 only)"
DRAFTS_C_VV4_TAG = " (VV4 only)"      # Tree of Life Supplies (draft_sup): The Tree of Life only


def _drafts_c_rows() -> None:
    for sid, (topic, _n, sec, pre) in lib.DRAFTS_C.items():
        with lib.use_source(sid):
            heads = [n for n in range(1, lib.n_lines() + 1) if re.match(rf"^{pre}-\d\d\. ", lib.line(n))]
            notes = next(n for n in range(1, lib.n_lines() + 1) if lib.line(n).startswith("NOTES FOR THE OWNER"))
            last = max(n for n in range(1, lib.n_lines() + 1) if lib.line(n).strip())
            N(f"{sec}_notes_intro", f"{topic}: title, premise and how to read the draft", 1, 5, sec, sec, source=sid)
            N(f"{sec}_notes_end", f"{topic}: notes for the owner", notes, last, sec, sec, source=sid)
            for i, h in enumerate(heads):
                stop = heads[i + 1] if i + 1 < len(heads) else notes
                e = stop - 1
                while lib.is_blank_or_separator(e):
                    e -= 1
                m = re.match(rf"^{pre}-(\d\d)\. (.+)$", lib.line(h))
                num, src_title = m.group(1), lib.normalize_source_text(m.group(2)).strip()
                games = ALL
                one = re.search(r" \(VV([1-5]) only\)$", src_title)   # DRAFTS_C_VV5_TAG, _VV4_TAG; Traders: any
                if one:
                    games, src_title = [int(one.group(1))], src_title[:one.start()]
                eid = f"{pre.lower()}{num}"
                nc = sum(1 for n in range(h + 2, e + 1) if re.match(r"^[^.!?]{1,80}:$", lib.line(n).strip()))
                R(f"{eid}_{companion_slug(src_title, VV1_ID_MAX - len(eid) - 1)}",
                  lib.title_case_label(src_title.replace('"', '')),              # a title holds no '"' (gap G6)
                  games, h, e, "event", sec, sec, nc, series=sec, source=sid, choice_re=r"^[^.!?]{1,80}:$")


_drafts_c_rows()

# ---- The owner-approved files, group D (collection_lib.DRAFTS_D; each file its own source and its own series) --------
#
# Five shapes (built by scripts/drafts_d/gen_drafts_d.py):
#   draft_rm2   "EVENT RM-41 — TITLE", SETUP:, choices A-D each with two outcomes A1/A2 (Role Models' shape, a line each)
#   draft_hz2   "EVENT 081 — TITLE", SETUP:, choices A-C each with two outcomes (Beyond the Horizon's shape)
#   fathers30   "EVENT 01: Title", THEME / CAST lines (notes), the setup, choices A-D each with "Outcome 1/2:"
#   moments500  125 moments: four "[M001] / Title: / text" entries share an opening (the owner's Question 1: one moment,
#               its four endings equally likely); the title is the owner's T001-T125 (owner-title-changes.md)
#   draft_tim2  "[T126] Title", "Opening:", "Ending 1:" .. "Ending 4:" (the same moment shape)
#   openq97     the armor moments "[M01] opening" / "Title:" / "Follow-up:" (one popup); the rest of the file is notes
#   armor45, draft_arm2   "NN. Title — one or two sentences" (one popup; one line each, so consecutive lines)
# Lines between events (headers, flavor blocks, the owner's notes) are notes rows.

NEVER = r"^(?!)"           # a one-popup event's choice_re: no line is a choice
for _sid, (_name, _n, _sec, _topic) in lib.DRAFTS_D.items():
    CREDITS[_sec] = ("mixed", [(1, 2)], _sid)
DRAFTS_D_SERIES = {sid: v[2] for sid, v in lib.DRAFTS_D.items()}      # source id -> its one series (the section)


def _d_end(h: int, stop: int) -> int:
    e = stop - 1
    while lib.is_blank_or_separator(e):
        e -= 1
    return e


def _d_notes(sid: str, sec: str, topic: str, spans: list[tuple[int, int, str]]) -> None:
    for i, (a, b, what) in enumerate(spans):
        N(f"{sec}_notes{i + 1}", f"{topic}: {what}", a, b, sec, sec, source=sid)


def moment_titles() -> dict[int, str]:
    """The owner's titles T001-T125 for the 500 moments (Completed Open Questions, Question 2): {1: "The Leaf Lantern"}.
    They are owner-title-changes.md rows; here they only name the ids."""
    out = {}
    with lib.use_source("openq97"):
        for n in range(1, lib.n_lines()):
            m = re.match(r"^\[T(\d{3})\] ", lib.line(n))
            if m and lib.line(n + 1).startswith("Title: "):
                out[int(m.group(1))] = lib.normalize_source_text(lib.line(n + 1))[len("Title: "):].strip()
    assert sorted(out) == list(range(1, 126)), sorted(set(range(1, 126)) - set(out))
    return out


def _drafts_d_rows() -> None:
    def heads_of(rx: str) -> list[int]:
        return [n for n in range(1, lib.n_lines() + 1) if re.match(rx, lib.line(n))]

    def event(sid, sec, eid, title, h, e, nc, one_line=False, slug_from=None):
        R(f"{eid}_{companion_slug(slug_from or title, VV1_ID_MAX - len(eid) - 1)}", title, ALL, h, e, "event", sec, sec, nc,
          series=sec, source=sid, choice_re=(r"^\s*[A-D]\.\s" if nc else NEVER), **({"one_line": True} if one_line
                                                                                   else {}))

    D = lib.DRAFTS_D
    # Role Models RM-41..RM-90 and Beyond the Horizon 081-130
    for sid, rx, prefix, notes_from in (("draft_rm2", r"^EVENT RM-(\d\d) — (.+)$", "rm", 760),
                                        ("draft_hz2", r"^EVENT (\d{3}) — (.+)$", "hz", 618)):
        _name, _n, sec, topic = D[sid]
        with lib.use_source(sid):
            heads = heads_of(rx)
            _d_notes(sid, sec, topic, [(1, _d_end(1, heads[0]), "title, premise and rules"),
                                       (notes_from, lib.n_lines(), "notes for the owner")])
            for i, h in enumerate(heads):
                e = _d_end(h, heads[i + 1] if i + 1 < len(heads) else notes_from)
                num, t = re.match(rx, lib.line(h)).groups()
                t = lib.normalize_source_text(t)
                nc = sum(1 for n in range(h, e + 1) if re.match(r"^\s*[A-D]\.\s", lib.line(n)))
                # the owner (2026-11-15): titles in title case, the last word capitalized ("The Last Canoe In")
                event(sid, sec, f"{prefix}{num}", lib.title_case_label(title_case(t.strip())), h, e, nc)
    # Fathers, Pregnancy and Parenthood
    sid = "fathers30"
    _name, _n, sec, topic = D[sid]
    with lib.use_source(sid):
        heads = heads_of(r"^EVENT \d\d: ")
        _d_notes(sid, sec, topic, [(1, 9, "title, format, scope and casting"), (432, 432, "the additional events"),
                                   (644, 645, "end of the collection")])
        for i, h in enumerate(heads):
            e = _d_end(h, heads[i + 1] - 1 if i + 1 < len(heads) else 643)
            if e >= 432 > h:
                e = _d_end(h, 431)
            num, t = re.match(r"^EVENT (\d\d): (.+)$", lib.normalize_source_text(lib.line(h))).groups()
            event(sid, sec, f"fat{num}", lib.title_case_label(t.strip()), h, e, 4)
    # The 500 Tiny Island Moments (T001-T125)
    sid = "moments500"
    _name, _n, sec, topic = D[sid]
    with lib.use_source(sid):
        ms = heads_of(r"^\[M\d{3}\]$")
        assert len(ms) == 500
        new = moment_titles()
        _d_notes(sid, sec, topic, [(1, 7, "title and introduction")]
                 + [(n, n, "a section heading") for n in heads_of(r"^SECTION \d\d — ")])
        for g in range(125):
            h = ms[4 * g]
            title = lib.normalize_source_text(lib.line(h + 1))[len("Title: "):].strip()
            event(sid, sec, f"tim{g + 1:03d}", title, h, ms[4 * g + 3] + 2, 0, slug_from=new[g + 1])
    # Tiny Island Moments T126-T175
    sid = "draft_tim2"
    _name, _n, sec, topic = D[sid]
    with lib.use_source(sid):
        heads = heads_of(r"^\[T\d{3}\] ")
        _d_notes(sid, sec, topic, [(1, 5, "title, premise and shape"), (359, lib.n_lines(), "notes for the owner")])
        for h in heads:
            num, t = re.match(r"^\[T(\d{3})\] (.+)$", lib.normalize_source_text(lib.line(h))).groups()
            event(sid, sec, f"tim{num}", t.strip(), h, h + 5, 0)
    # The armor moments M01-M35 (Completed Open Questions, Question 4)
    sid = "openq97"
    _name, _n, sec, topic = D[sid]
    with lib.use_source(sid):
        heads = heads_of(r"^\[M\d\d\] ")
        assert len(heads) == 35
        _d_notes(sid, sec, topic, [(1, heads[0] - 2, "the owner's answers to the open questions (Questions 1-4; "
                                                     "Question 2's titles are owner-title-changes.md rows)")])
        for h in heads:
            num = re.match(r"^\[M(\d\d)\] ", lib.line(h)).group(1)
            title = lib.normalize_source_text(lib.line(h + 1))[len("Title: "):].strip()
            event(sid, sec, f"armm{num}", title, h, h + 2, 0)
    # Armor, Weapons and Inherited Traditions 01-45, and ARM-46..ARM-95
    for sid, notes in (("armor45", [(1, 7, "title, style rules and heading"),
                                    (40, 40, "the Passing Things Down heading"),
                                    (58, 96, "the Living Event Engine flavor text (mixer seeds: pending) and end")]),
                       ("draft_arm2", [(1, 8, "title, premise, style rules and heading"),
                                       (61, lib.SOURCES["draft_arm2"][2], "the Living Event Engine flavor text "
                                                                          "(mixer seeds: pending) and notes for the "
                                                                          "owner")])):
        _name, _n, sec, topic = D[sid]
        with lib.use_source(sid):
            _d_notes(sid, sec, topic, notes)
            for h in heads_of(r"^\d\d\. .+ — "):
                num, t = re.match(r"^(\d\d)\. (.+?) — ", lib.line(h)).groups()
                event(sid, sec, f"arm{num}", lib.normalize_source_text(t).strip(), h, h, 0, one_line=True)
    # New Believers' Heathen-Exclusive Events HE-01..HE-45 (the owner's approval, 2026-11-23): "HE-01. Title", its
    # casting and requirement lines, the setup, "Label:" choices each with its outcome and "Effects:" line (or "(no
    # choice; one popup)"), notes; VV5 only.  The file's headers, section introductions and engine notes are notes rows.
    sid = "heathen_ex"
    _name, _n, sec, topic = D[sid]
    with lib.use_source(sid):
        heads = heads_of(r"^HE-\d\d\. ")
        assert len(heads) == 45, len(heads)
        sections = heads_of(r"^[A-C]\. [A-Z]")
        end = heads_of(r"^WHAT THE ENGINE CAN DO TODAY")[0]
        _d_notes(sid, sec, topic, [(1, _d_end(1, sections[0] - 1), "title, casting, the owner's rules, Guardians of "
                                                                     "Isola wording, effect tags and odds")]
                 + [(s - 1, _d_end(s, heads_of(r"^HE-\d\d\. ")[[h > s for h in heads].index(True)] - 1),
                     f"section {lib.line(s)[0]}: its heading and introduction") for s in sections]
                 + [(end - 1, lib.n_lines(), "what the engine can do, the engine changes and the open questions")])
        for i, h in enumerate(heads):
            stop = heads[i + 1] if i + 1 < len(heads) else end - 1      # (end - 1: the "####" rule above it)
            nxt = [s - 1 for s in sections if h < s - 1 < stop]
            e = _d_end(h, nxt[0] if nxt else stop)
            num, t = re.match(r"^HE-(\d\d)\. (.+)$", lib.normalize_source_text(lib.line(h))).groups()
            nc = sum(1 for n in range(h, e + 1) if re.match(HE_LABEL_RE, lib.line(n)))
            # A title cannot show a literal parenthesis (a title's parentheses are placeholders, vv_cie_graph
            # title_problems): HE-40's title is the owner's own answer (2026-11-23), "The Rain Dance That Worked,
            # Probably".
            title = re.sub(r" \((\w+)\)$", r", \1", t.strip())
            R(f"he{num}_{companion_slug(t, ID_MAX - 5)}", title, [5], h, e, "event", sec, sec, nc, series=sec,
              source=sid, choice_re=HE_LABEL_RE)


HE_LABEL_RE = r"^[A-Z][^.!?:]{0,80}:$"     # a Heathen-Exclusive Event's choice label ("Sit Quietly With (Him/Her):")
_drafts_d_rows()


# ---- The owner's GO files (collection_lib.GO_SOURCES; the owner's own layout, src/vv_owner_layout.py) --------------
#
# "S001. Title   [VV1, ...]", WHO:, EVENT TEXT, the story, "Choice A: Label" lines, then per choice "CHOICE A: LABEL",
# "First popup: ...", "Ending A1 -- NAME. Chance 50%. EFFECT: ..." with its text, then "MIXER SEED <code>" (the mixer's
# pieces, built by scripts/go_events/gen_go.py).  An event's row runs from its heading to its seed's last flavour line;
# the file's other lines (headings, the writers' count tables) are notes rows.  Each section is one series.
GO_CREDITS = {   # credit key: the owner's words for the events (Credits.txt and each event's credit)
    "go_rw": "Created by Lorsieab2; drafted with ChatGPT; rewritten with Claude to Lorsieab2's style guide.",
    "go_rw_own": "Written by Lorsieab2.",
    "go_bal": "Written by Claude to Lorsieab2's style guide and direction.",
}
GO_HEADING = re.compile(r"^([A-Z]+-?)(\d+)\.\s+(.+?)\s+\[([^\]]*)\]\s*$")
GO_OWN = 20          # S001-S020: the owner's own (the example events, "written by Lorsieab2")


def _go_rows() -> None:
    for sid, (_name, _n, secs) in lib.GO_SOURCES.items():
        with lib.use_source(sid):
            n_all = lib.n_lines()
            heads = [n for n in range(1, n_all + 1) if GO_HEADING.match(lib.line(n).strip())]
            taken: set[int] = set()
            for i, h in enumerate(heads):
                stop = heads[i + 1] if i + 1 < len(heads) else n_all + 1
                e, flav = h, False
                for n in range(h, stop):
                    s = lib.line(n)
                    if s.startswith("#") or (lib.is_separator(s) and n > h):
                        break
                    if s.strip().startswith(("Flavour lines:", "Flavor lines:")):
                        flav = True
                    elif flav and not s.strip().startswith("-"):
                        if s.strip():
                            break
                        if e > h and lib.line(e).strip().startswith("-"):
                            break
                        continue
                    if s.strip():
                        e = n
                pre, num, title, games = GO_HEADING.match(lib.line(h).strip()).groups()
                sec, _topic = secs[pre]
                code = f"{pre.rstrip('-').lower()}{num}"
                gs = sorted({int(g) for g in re.findall(r"VV\s*([1-5])", games)}) or ALL
                if re.search(r"\b[Aa]ll\b", games):
                    gs = ALL
                credit = "go_bal" if sid == "balance" else "go_rw_own" if pre == "S" and int(num) <= GO_OWN \
                    else "go_rw"
                nc = sum(1 for n in range(h, e + 1) if re.match(r"^Choice [A-Z]\s*:", lib.line(n)))
                R(f"{code}_{companion_slug(title, VV1_ID_MAX - len(code) - 1)}", lib.normalize_source_text(title).strip(),
                  gs, h, e, "event", sec, credit, nc, series=sec, source=sid, choice_re=r"^Choice [A-Z]\s*:")
                taken.update(range(h, e + 1))
            # the rest: notes rows (runs of lines outside the events, cut at blank lines before a heading)
            k, sec0 = 0, next(iter(secs.values()))[0]
            n = 1
            while n <= n_all:
                if n in taken or lib.is_blank_or_separator(n):
                    n += 1
                    continue
                a = n
                while n + 1 <= n_all and n + 1 not in taken and not (
                        lib.is_blank_or_separator(n + 1) and (n + 2 > n_all or n + 2 in taken
                                                             or lib.is_blank_or_separator(n + 2))):
                    n += 1
                b = n
                while lib.is_blank_or_separator(b):
                    b -= 1
                k += 1
                N(f"{sec0}_notes{k}", f"{lib.GO_SECTIONS[sec0][1]}: the writers' notes", a, b, sec0, "go_bal"
                  if sid == "balance" else "go_rw", source=sid)
                n += 1


for _k in GO_CREDITS:
    CREDITS[_k] = ("mixed", [(1, 1)], "balance" if _k == "go_bal" else "rewrites")
_go_rows()


# ---- The owner's More Island Events file (collection_lib.MIE; scripts/go_events/gen_mie.py) ----------------------------
#
# Nine events, each from its "THE ... (games)" heading to its CHANCES table; the file's header (lines 1-29) and The
# Cooking Contest's draft (816 on: not one of the nine) are notes rows.  Their static form never ships
# (collection.mixer_only: "VVFP More Island Events.dll" runs them); only their mixer versions do.
MIE_CREDITS = {"mie_own": "Written by Lorsieab2."}
MIE_EVENTS = (   # (id, title, games, heading line, the widest question's choices, a regex matching exactly its
    #               choice lines: the count is recounted from the source)
    ("mie_adventurer", "The Aspiring Adventurer", ALL, 33, 2, r"^Choice [AB]: "),
    ("mie_cave_explorers", "The Cave Explorers", [1], 306, 2, r"^(Don't explore -- |Explore the Cave\. )"),
    ("mie_climb", "The Climb", [2], 443, 2, r"^(Go with the plan\. |Follow the scientists' advice -- )"),
    ("mie_troubling_signs", "The Troubling Signs", [3], 488, 4, r"^Choice [1-4] -- "),
    ("mie_diving", "Diving for Treasure", [3], 561, 2, r'^Choice "'),
    ("mie_mysterious_mask", "The Mysterious Mask", [4], 619, 4, r'^(?:[WH] -- "|"Walk towards the )'),
    ("mie_dolphins", "The Playful Dolphins", [4], 694, 2, r'^"(?:Swim towards the dolphins|Hang back)"'),
    ("mie_remembrance", "The Remembrance Ceremony", ALL, 735, 0, r"(?!)"),
    ("mie_rumblings", "The Rumblings", ALL, 772, 0, r"(?!)"),
)
MIE_COOKING = 816      # The Lost Children - The Cooking Contest (a draft; not one of the nine)


def _mie_rows() -> None:
    with lib.use_source(lib.MIE_ID):
        heads = [h for _i, _t, _g, h, _n, _c in MIE_EVENTS] + [MIE_COOKING]
        for k, (eid, title, games, h, choices, choice_re) in enumerate(MIE_EVENTS):
            stop = heads[k + 1] - 1
            while lib.is_blank_or_separator(stop):
                stop -= 1
            R(eid, title, games, h, stop, "event", lib.MIE_SECTION, "mie_own", choices, series=None, source=lib.MIE_ID,
              choice_re=choice_re)
        N("mie_notes_head", "More Island Events: the file's title, list and rules for every event", 1, 29,
          lib.MIE_SECTION, "mie_own", source=lib.MIE_ID)
        N("mie_notes_cooking", "More Island Events: The Cooking Contest's draft (not one of the nine events)",
          MIE_COOKING, lib.n_lines(), lib.MIE_SECTION, "mie_own", source=lib.MIE_ID)


CREDITS["mie_own"] = ("lorsieab2_original", [(1, 1)], lib.MIE_ID)
_mie_rows()


# ---- The owner's all-in-one Animals anthology, its newest volumes (collection_lib.ANTHOLOGY; its own line numbers) ----
#
# The owner's newest all-in-one file (2026-11-15) is the Living Event Engine file with the GLOBAL EDITORIAL OVERRIDE
# (MOM-01..08) in front and new volumes after it.  Only those newest volumes are rows (the rest is the Living file's,
# built from collection_lib.LIVING): a heading ("[REL-01] The First Shared Walk", "CHILD-01 — The Shell ...",
# "EVENT-AGE-001 — The Tiny Gap"), an optional "ELIGIBILITY:" line (the casting), the setup ("SETUP:"), and choices
# A-B (MOM) or A-D, each with two outcomes (A1, A2 ...).  Each volume is one series (the lead, 2026-11-15) and its
# contract block is a notes row.  Files: data/event_collection/anthology/<section>/<id>.json, built by
# scripts/anthology_new/gen_anthology.py; "uncovered" is checked inside the volumes.

ANT = lib.ANTHOLOGY_ID
# (section, heading regex (number, title), id prefix, choices, notes row title)
ANTHOLOGY_VOLUMES = [
    ("an_mom", r"^\[MOM-(\d+)\] (.+)$", "anmom", 2, "Global Editorial Override: the full emotional spectrum"),
    ("an_rel", r"^\[REL-(\d+)\] (.+)$", "anrel", 4, "Love by Choice, Coming Out, Names and Presentation: contract"),
    ("an_child", r"^CHILD-(\d+) — (.+)$", "anchd", 4, "Childhood Curiosity, Puppy Love and Questions: contract"),
    ("an_fam", r"^\[FAM-(\d+)\] (.+)$", "anfam", 4, "Family Friction and Reconciliation: social-conflict override"),
    ("an_joy", r"^JOY-(\d+) — (.+)$", "anjoy", 4, "Celebrations, Leisure, Remembrance and Body Art: global rules"),
    ("an_hs", r"^EVENT-HS-(\d+) — (.+)$", "anhs", 4, "The Human Spectrum: controlling additions"),
    ("an_age", r"^EVENT-AGE-(\d+) — (.+)$", "anage", 4, "Every Age in the Limelight: implementation notes"),
    ("an_jus", r"^EVENT-JUSTICE-(\d+) — (.+)$", "anjus", 4, "Justice, Trauma, Recovery and Defense: contract"),
    ("an_expr", r"^EVENT-EXPRESSION-(\d+) — (.+)$", "anexp", 4, "Self-Expression and Island Society: contract"),
    ("an_fauna", r"^EVENT-FAUNA-(\d+) — (.+)$", "anfau", 4, "Animals of Fur, Feathers, Scales, Claws and Hooves: contract"),
]
for _sec, *_ in ANTHOLOGY_VOLUMES:
    CREDITS[_sec] = ("mixed", [(1, 2)], ANT)
ANTHOLOGY_SPANS: list[tuple[int, int]] = []


def anthology_event_end(h: int, choices: int) -> int:
    """An event's last line: heading, [ELIGIBILITY], setup, then three lines a choice."""
    elig = lib.line(h + 1).startswith("ELIGIBILITY:")
    return h + 1 + elig + 3 * choices


def _anthology_rows() -> None:
    with lib.use_source(ANT):
        n_all = lib.n_lines()
        for sec, rx_s, prefix, nc, notes_title in ANTHOLOGY_VOLUMES:
            rx = re.compile(rx_s)
            heads = [n for n in range(1, n_all + 1) if rx.match(lib.line(n))]
            assert heads, sec
            # the contract block: back from the first heading to the gap of two blank lines before it
            b = heads[0] - 1
            while not lib.line(b).strip():
                b -= 1
            a = b
            while lib.line(a - 1).strip() or lib.line(a - 2).strip():
                a -= 1
            N(f"{sec}_notes", notes_title, a, b, sec, sec, source=ANT)
            last = b
            for h in heads:
                e = anthology_event_end(h, nc)
                assert not lib.line(e + 1).strip() or rx.match(lib.line(e + 1)), (sec, h)
                m = rx.match(lib.line(h))
                num, src_title = m.group(1), lib.normalize_source_text(m.group(2)).strip()
                eid = f"{prefix}{int(num):02d}"
                R(f"{eid}_{companion_slug(src_title, VV1_ID_MAX - len(eid) - 1)}",
                  lib.title_case_label(src_title), ALL, h, e, "event", sec, sec, nc, series=sec, source=ANT,
                  choice_re=r"^[A-D]\.\s")
                last = e
            ANTHOLOGY_SPANS.append((a, last))


_anthology_rows()


# ---- "(Name1)'s Harshest Critic" (collection_lib.CRITIC; its own line numbers) -----------------------------------------
#
# The owner's random-pool event (2026-11-16, Expanded v3), laid out as the Cooking Contest is: one event whose setup and
# shared pools are add-on rows.  Its 112 routes are too much text for one .cieg (story_graph.inc CG_MAX_FILE), so the
# event ships as six collection files, one per route family, ONE series ("hc_critic": one draw in the rare roll); each
# file lists the add-on rows it shows (collection.addons).  Every line belongs to one row; the rows touch with no blank
# line between them, so they carry one_line (no blank-line boundary check).  The credit is the owner's own line
# (2026-11-17), its own one-line file.  Files: data/event_collection/critic/hc/<id>.json, built by
# scripts/critic/gen_critic.py.

CRIT = lib.CRITIC_ID
CREDITS["hc"] = ("mixed", [(1, 1)], lib.CRITIC_CREDIT_ID)
CRITIC_TITLE = "(Name1)'s Harshest Critic"
# (id, kind, first line, last line, the row's title after the event's: the heading found at the row's top)
CRITIC_ROWS = [
    ("hc_setup", "addon", 1, 757, ""),
    ("hc1_routes", "event", 758, 827, "Routes"),
    ("hc_setup_devotion", "addon", 828, 862, "Devotion-Specific Punishments"),
    ("hc_mentor_reactions", "addon", 863, 1154, "The Mentor's Reaction"),
    ("hc_variant2", "addon", 1155, 1208, "Variant 2: The Harshest Critic Is (Name1)"),
    ("hc_named_master", "addon", 1209, 1293, "Additional Mad-Lib Module"),
    ("hc2_pleas", "event", 1294, 1373, "Additional Outcome Routes"),
    ("hc3_disasters", "event", 1374, 1613, "Catastrophic Examination Disasters"),
    ("hc_comic_pools", "addon", 1614, 1784, "Expansion: The Big Bang"),
    ("hc4_noises", "event", 1785, 1856, "Explosions, Noises, Odors, and Corpsing"),
    ("hc5_victories", "event", 1857, 2033, "Unintended Victories"),
    ("hc6_sabotage", "event", 2034, 2218, "The Sabotage Twist"),
]


def _critic_rows() -> None:
    with lib.use_source(CRIT):
        for rid, kind, a, b, what in CRITIC_ROWS:
            while not lib.line(b).strip():      # a row ends on its last line with words (the blank before the next)
                b -= 1
            title = f"{CRITIC_TITLE}: {what}" if what else CRITIC_TITLE
            R(rid, title, ALL, a, b, kind, "hc", "hc", 4 if rid == "hc_setup" else 0, series="hc_critic",
              source=CRIT, one_line=True, choice_re=(r"^Choice [A-D]: " if rid == "hc_setup" else NEVER))


_critic_rows()

# ---- Re-verification against the source ------------------------------------------------------------------------------


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", lib.normalize_source_text(s).lower()).strip()


def title_found(row: dict) -> bool | None:
    """The row's title at the top of its lines (None for a notes row: its title is the manifest's own words)."""
    if row["kind"] in ("notes", "bank"):
        return None
    a = row["lines"][0]
    head = " ".join(_norm(lib.line(n)) for n in range(a, min(a + 8, lib.n_lines() + 1)))
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
    if row.get("one_line"):
        return out          # a source whose events are one line each, one after another (collection_lib.DRAFTS_D)
    if a > 1 and not lib.is_blank_or_separator(a - 1) and not lib.is_separator(lib.line(a)):
        out.append(f"line {a - 1} before the row is not blank")
    if b < lib.n_lines() and not lib.is_blank_or_separator(b + 1):
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
    while m <= lib.n_lines() and re.match(r"^\s+\S", lib.line(m)):
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


# The owner, 2026-11-15: the three handwritten events are credited to the owner alone (in place of the ledger's lines).
OWNER_CREDITS = {
    "cooking": "* The Cooking Contest (VV2): written by Lorsieab2.",
    "child": "* The Child of Legend (VV1): written by Lorsieab2.",
    "faith": "* The Meaning of \"Faith\" (VV5): written by Lorsieab2.",
}


def credit_text(key: str) -> dict:
    who, ranges, *src = CREDITS[key]
    with lib.use_source(src[0] if src else lib.SOURCE_ID):
        text = OWNER_CREDITS.get(key) or GO_CREDITS.get(key) or MIE_CREDITS.get(key) or "\n".join(lib.line(n) for x, y in ranges for n in range(x, y + 1))
        out = {"who": who, "lines": [lib.fmt_src(x, y) for x, y in ranges], "text": text}
    if src and src[0] == lib.CRITIC_CREDIT_ID:
        out["source"] = src[0]      # a credit kept in a file of its own, not in the row's source
    return out


def uncovered(rows: list[dict]) -> list[str]:
    covered = set()
    for r in rows:
        covered.update(range(r["lines"][0], r["lines"][1] + 1))
    out, run = [], None
    for n in range(1, lib.n_lines() + 1):
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
        with lib.use_source(row["source"]):
            checks, dis = verify(row)       # against the source's own heading
        owner = lib.owner_titles().get(row["id"])
        if owner is not None:
            # the owner's rename (docs/event-collection/owner-title-changes.md): the title every game shows; the
            # source's own heading stays as source_title
            if owner["old"] != row["title"]:
                dis.append(f"owner-title-changes.md: old title {owner['old']!r} is not the source's {row['title']!r}")
            rest = {k: v for k, v in row.items() if k not in ("id", "title")}
            row = {"id": row["id"], "title": owner["new"], "source_title": row["title"], **rest}
        row.pop("choice_re", None)
        row.pop("extra_labels", None)
        row.pop("one_line", None)
        row["credit"] = credit_text(r["credit"])
        row["source_check"] = checks
        rows.append(row)
        all_dis.extend({"id": row["id"], "lines": lib.fmt_src(*row["lines"]), "what": d} for d in dis)

    def counts(mine: list[dict], series: tuple) -> dict:
        return {"rows": len(mine), "events": sum(r["kind"] == "event" for r in mine),
                "addons": sum(r["kind"] == "addon" for r in mine), "banks": sum(r["kind"] == "bank" for r in mine),
                "notes": sum(r["kind"] == "notes" for r in mine),
                "events_and_addons": sum(r["kind"] in ("event", "addon") for r in mine),
                "series": {s: sum(r["series"] == s for r in mine) for s in series}}

    grand = [r for r in rows if r["source"] == lib.SOURCE_ID]
    comp = [r for r in rows if r["source"] == lib.COMPANION_ID]
    with lib.use_source(lib.COMPANION_ID):
        companion = {
            "source": str(lib.COMPANION.relative_to(lib.ROOT)).replace("\\", "/"),
            "source_sha256": lib.source_sha256(lib.COMPANION_ID),
            "counts": counts(comp, COMPANION_SERIES),
            "uncovered_lines": uncovered(comp),
            "overlaps": overlaps(comp),
        }
    liv = [r for r in rows if r["source"] == lib.LIVING_ID]
    with lib.use_source(lib.LIVING_ID):
        inside = {n for a, b in living_span() for n in range(a, b + 1)}
        living = {
            "source": str(lib.LIVING.relative_to(lib.ROOT)).replace("\\", "/"),
            "source_sha256": lib.source_sha256(lib.LIVING_ID),
            "volumes": [lib.fmt_src(a, b) for a, b in living_span()],
            "counts": counts(liv, ()),
            # only lines inside the volumes above: the rest of the file is the Living Event bank's
            "uncovered_lines": [u for u in uncovered(liv) if lib.src_lines(u)[0] in inside],
            "overlaps": overlaps(liv),
        }

    ant = [r for r in rows if r["source"] == lib.ANTHOLOGY_ID]
    with lib.use_source(lib.ANTHOLOGY_ID):
        inside = {n for a, b in ANTHOLOGY_SPANS for n in range(a, b + 1)}
        anthology = {
            "source": str(lib.ANTHOLOGY.relative_to(lib.ROOT)).replace("\\", "/"),
            "source_sha256": lib.source_sha256(lib.ANTHOLOGY_ID),
            "volumes": [lib.fmt_src(a, b) for a, b in ANTHOLOGY_SPANS],
            "counts": counts(ant, tuple(lib.ANTHOLOGY_SECTIONS)),
            # only lines inside the volumes above: the rest of the file is the Living Event Engine file's
            "uncovered_lines": [u for u in uncovered(ant) if lib.src_lines(u)[0] in inside],
            "overlaps": overlaps(ant),
        }

    def whole_file(source: str, path, series: tuple) -> dict:
        """A source whose every line belongs to a row (Beyond the Horizon, Role Models and Good Examples)."""
        mine = [r for r in rows if r["source"] == source]
        with lib.use_source(source):
            return {"source": str(path.relative_to(lib.ROOT)).replace("\\", "/"),
                    "source_sha256": lib.source_sha256(source), "counts": counts(mine, series),
                    "uncovered_lines": uncovered(mine), "overlaps": overlaps(mine)}
    return {
        "format": "vvfp-event-collection-manifest", "version": 1,
        "source": str(lib.SOURCE.relative_to(lib.ROOT)).replace("\\", "/"),
        "source_sha256": lib.source_sha256(),
        "counts": counts(grand, SERIES),
        "disagreements": all_dis,
        "inventory_disagreements": INVENTORY_DISAGREEMENTS,
        "uncovered_lines": uncovered(grand),
        "overlaps": overlaps(grand),
        # The second source (collection_lib.COMPANION): its rows are in "rows" with "source": "companion".
        "companion": companion,
        # The third source (collection_lib.LIVING): its rows are in "rows" with "source": "living".
        "living": living,
        # The fourth and fifth sources (collection_lib.HORIZON, collection_lib.ROLEMODELS): rows with "source"
        # "horizon" / "rolemodels".
        "horizon": whole_file(lib.HORIZON_ID, lib.HORIZON, HORIZON_SERIES_NAMES),
        "rolemodels": whole_file(lib.ROLEMODELS_ID, lib.ROLEMODELS, ()),
        # The owner-approved drafts, set A (collection_lib.DRAFTS_A): one block per file, one series each.
        "drafts_a": {sid: whole_file(sid, lib.SOURCES[sid][0], (sid,)) for sid in lib.DRAFTS_A},
        # The approved drafts, group B (collection_lib.DRAFTS_B): rows with "source" "draft_hum", ...
        **{sid: whole_file(sid, lib.SOURCES[sid][0], (DRAFTS_B_SERIES[sid],)) for sid in lib.DRAFTS_B},
        # The approved drafts, group C (collection_lib.DRAFTS_C): rows with "source" "draft_hea", ...
        **{sid: whole_file(sid, lib.SOURCES[sid][0], (DRAFTS_C_SERIES[sid],)) for sid in lib.DRAFTS_C},
        # The approved files, group D (collection_lib.DRAFTS_D): rows with "source" "draft_rm2", ...
        **{sid: whole_file(sid, lib.SOURCES[sid][0], (DRAFTS_D_SERIES[sid],)) for sid in lib.DRAFTS_D},
        # The Animals anthology's newest volumes (collection_lib.ANTHOLOGY): rows with "source" "anthology"
        "anthology": anthology,
        # The owner's GO files (collection_lib.GO_SOURCES): rows with "source" "rewrites" / "balance"
        **{sid: whole_file(sid, lib.SOURCES[sid][0], tuple(sec for sec, _t in v[2].values()))
           for sid, v in lib.GO_SOURCES.items()},
        # The owner's More Island Events file (collection_lib.MIE): rows with "source" "mie"
        lib.MIE_ID: whole_file(lib.MIE_ID, lib.MIE, ()),
        # "(Name1)'s Harshest Critic" (collection_lib.CRITIC): rows with "source" "critic"
        "critic": whole_file(lib.CRITIC_ID, lib.CRITIC, ("hc_critic",)),
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
    c = data["companion"]
    print(f"companion: {c['counts']}, uncovered {c['uncovered_lines']}, overlaps {c['overlaps']}")
    lv = data["living"]
    print(f"living: {lv['counts']}, uncovered {lv['uncovered_lines']}, overlaps {lv['overlaps']}")
    for key in ("horizon", "rolemodels", *lib.DRAFTS_B, *lib.DRAFTS_C, *lib.DRAFTS_D, "anthology",
                *lib.GO_SOURCES, lib.MIE_ID, "critic"):
        s = data[key]
        print(f"{key}: {s['counts']}, uncovered {s['uncovered_lines']}, overlaps {s['overlaps']}")
    for key, s in data["drafts_a"].items():
        print(f"{key}: {s['counts']['events']} events, uncovered {s['uncovered_lines']}, overlaps {s['overlaps']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
