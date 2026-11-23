"""Write the owner's GO files (collection_lib.GO_SOURCES) as collection events, their mixer seeds as procedural pieces,
then format and check them:

    python scripts/go_events/gen_go.py                 # both files: events, docs tables, pieces; then the checks
    python scripts/go_events/gen_go.py --report        # the events left out and the EFFECT phrases kept as story

  rewrites  Isola Rewritten Events S001-MY115.txt   315 events (S001-S100, NEW-001..NEW-100, MY-001..MY-115)
  balance   Isola Balance Events B001-B360.txt      360 events (B001-B360)

THE OWNER'S GO (2026-11-16).  The events are built through the Player Events importer's reader of the owner's own
layout (src/vv_player_events.py _parse_owner, src/vv_owner_layout.py): the opening story is the question page, each
"Choice X:" a button, a choice's "First popup:" its own page, and its endings equally likely outcomes after it
("Every ending within a choice is equally likely"; the files' own 50% / 33% chances) with the effects each EFFECT:
names.  The text is the owner's, word for word: the only changes are the placeholders as the engine writes them
(role names when an event has two villagers), plain typography, the grammar fixes below (each a grammar_fixes entry
and a row of docs/event-collection/grammar-fixes.md) and the Guardians of Isola Rewrite forms for New Believers (each
a row of docs/event-collection/guardians-wording.md).

LENIENT EFFECTS.  An EFFECT phrase the phrase table cannot map (docs/player-events-format.md 10) is kept as story
only: the ending still shows, without that one change, and the ledger names the phrase ("instruction", for the
owner's review).  An event the engine cannot build at all is left out and listed (--report).

AMOUNTS.  The owner's own skill amounts ("gains 20 to 30 Farming") are kept exactly (collection.exact_amounts: the
owner's numbers, not the skill table's sizes); food and tech use the owner's size words.

GRAMMAR (the owner: "fix any grammar mistakes automatically"): a doubled word ("the the") and "a" before a vowel
sound ("a apple" -> "an apple").  Nothing stylistic.

MIXER SEEDS.  Each "MIXER SEED" block becomes procedural pieces (a setup, its approaches, its outcome pool, its
flavour lines) in data/procedural_pieces/go_seeds.json, the procedural pieces' input for these files (its own
families, one per seed); the static event's own mixer versions come from scripts/living_from_static.py as for every
collection event.

Nothing here touches a game, a save or an exe.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import collection_check as cc  # noqa: E402
import collection_lib as lib  # noqa: E402
import vv_owner_layout as owner  # noqa: E402
import vv_player_events as pe  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import go_role_fixes as role_fixes  # noqa: E402

PIECES_OUT = ROOT / "data" / "procedural_pieces" / "go_seeds.json"
GRAMMAR_MARK = ("<!-- GO grammar fixes: written by scripts/go_events/gen_go.py -->",
                "<!-- end of GO grammar fixes -->")
GUARDIANS_MARK = ("<!-- GO Guardians wording: written by scripts/go_events/gen_go.py -->",
                  "<!-- end of GO Guardians wording -->")
STORY_WHY = ("the word in the owner's story; what changes in the game is the ending's own EFFECT line (the ledger), "
             "so this word alone changes nothing")
UNMAPPED_WHY = ("an EFFECT phrase the engine cannot do yet (docs/player-events-format.md 10): kept as story only, the "
                "ending shown without it, for the owner's review")
VILLAGE_EFFECTS = {"food", "tech", "pay_award", "repair", "celebrate", "new_villager"}
AWARD_LOSS = r"\s*Your villag\w* (?:lose|loses) \(award\)[^.]*\."
CHIEF_WORDS = {"chief": {"3": "chief", "*": "leader"}, "Chief": {"3": "Chief", "*": "Leader"}}


def game_words(text: str) -> str:
    """"Chief" as the game's own word ({@chief}: The Secret City's chief, elsewhere the leader)."""
    return re.sub(r"(?<![{@\w(.])([Cc])hief\b(?![\w)])", lambda m: "{@" + m.group(1) + "hief}", text)


def escape_bare(text: str) -> str:
    """A parenthesis that is not a placeholder is a literal one (\\( \\)): "(leaving (child) safely outside)"."""
    out, i = [], 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and text[i + 1:i + 2] in ("(", ")"):
            out.append(text[i:i + 2])
            i += 2
            continue
        if ch == "{":
            j = text.find("}", i)
            if j > 0:
                out.append(text[i:j + 1])
                i = j + 1
                continue
        if ch == "(":
            m = re.match(r"\(([^()\n]*)\)", text[i:])
            if m and pe._PH_OK.match(m.group(1)):
                out.append(m.group(0))
                i += len(m.group(0))
                continue
            out.append("\\(")
        elif ch == ")":
            out.append("\\)")
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def _pr(role, partner=None, babies=None, **kw):
    e = {"do": "pregnant", "role": role}
    if partner:
        e["partner"] = partner
    if babies:
        e["babies"] = babies
    if partner and not kw.get("any_birth_sex"):
        e["partner_may_carry"] = True      # a couple's pregnancy (vv_owner_layout's rule; engine flags bit 3)
    return {**e, **kw}


# EFFECT lines the phrase table cannot read, mapped by hand (the coordinator, 2026-11-16): (event id, line) -> (what,
# [effects] or, for "one of these, 50:50", [[effects], [effects]] as equally likely branches after the page).  A
# couple's pregnancy (b260, b336; the owner, 2026-11-18): one of the couple carries the baby, the other is the other
# parent -- partner_may_carry, so whoever the engine has carry is named in the logs; nothing says born female.
OVERRIDES: dict[tuple[str, int], tuple[str, list[list[dict]]]] = {
    ("s001_spring_talks_back", 27): (
        "one of two, 50:50: loses a dislike at random, or 10 to 20 in a random skill other than Farming",
        [[{"do": "preference", "role": "subject", "dislike": "random", "remove": True}],
         [{"do": "skill", "role": "subject", "skills": ["Building", "Research", "Healing", "Parenting"],
           "min": 10, "max": 20}]]),
    ("s016_fertility_stone", 747): ("twins or triplets, 50:50",
                                    [[_pr("subject", "friend", 2)], [_pr("subject", "friend", 3)]]),
    ("b158_shrine_basket", 7300): ("a nursing baby (any birth sex)",
                                   [[{"do": "nursing", "role": "subject", "any_birth_sex": True}]]),
    ("b172_trader_baby", 7980): ("the baby is a nursing baby of (name2) (any birth sex)",
                                 [[{"do": "nursing", "role": "friend", "any_birth_sex": True}]]),
    ("b187_elder_hat", 8696): ("a new look and the old head look for (name2)",
                               [[{"do": "appearance", "role": "friend", "head": "random"},
                                 {"do": "old_look", "role": "friend"}]]),
    ("b218_lost_little_ones", 10150): (
        "two adults (the second the mother, born female, nursing the baby), then the girl",
        [[{"do": "new_villager", "age": "adult"}, {"do": "new_villager", "age": "adult", "sex": "female"},
          {"do": "nursing", "role": "$newest"}, {"do": "new_villager", "age": "child", "sex": "female"}]]),
    ("b218_lost_little_ones", 10156): (
        "two adults (the second the mother, born female, nursing the baby), the teen, then the girl",
        [[{"do": "new_villager", "age": "adult"}, {"do": "new_villager", "age": "adult", "sex": "female"},
          {"do": "nursing", "role": "$newest"}, {"do": "new_villager", "age": "teen"},
          {"do": "new_villager", "age": "child", "sex": "female"}]]),
    ("b260_warm_stone", 12142): ("one of the couple carries the baby, with the other; twins or triplets, 50:50",
                                 [[_pr("subject", "friend", 2)], [_pr("subject", "friend", 3)]]),
    ("b260_warm_stone", 12148): ("one of the couple carries the baby, with the other, one baby",
                                 [[_pr("subject", "friend")]]),
    ("b280_two_carved_totems", 13054): ("a body swap between the two", [[{"do": "body_swap", "role": "subject",
                                                                          "with": "friend"}]]),
    ("b304_waterfall_two", 14117): ("10 in a best skill for each (the engine's best skill is the villager's own)",
                                    [[{"do": "skill", "role": "subject", "best": True, "min": 10, "max": 10},
                                      {"do": "skill", "role": "friend", "best": True, "min": 10, "max": 10}]]),
    ("b305_coconut_cried", 14159): ("a nursing baby for the healer (any birth sex)",
                                    [[{"do": "nursing", "role": "healer", "any_birth_sex": True}]]),
    ("b308_moon_shell", 14306): ("(neighbour name) pregnant, the engine's own partner",
                                 [[_pr("neighbour")]]),
    ("b324_hollow_log_drum", 15014): ("the young head look for (eldest name)",
                                      [[{"do": "young_look", "role": "eldest"}]]),
    ("b336_lazy_river", 15551): ("one of the couple carries the baby, with the other, one baby",
                                 [[_pr("subject", "friend")]]),
}


# COUNT TOKENS (the owner's rule 13: text about several new villagers or babies fits any count).  A page that makes
# two or more villagers (new_villager, clone) or babies (pregnant, nursing) makes only as many as the game's room
# allows, so its fixed words become a count token ({#made:A|B|C}, {#babies:A|B|C}; cie-v6-binary.md 33): A for one,
# B for two, C for three or more.  The smallest edit: the sentence that says who stays, or the counted words; the
# owner's text is the last option.  (source, line) -> [(before, after)], each `before` once on its line.
_ROOM = "the village has no room for more"


def _stay(n: int, full: str, one: str = f"Only one of them can stay; {_ROOM}",
          two: str = f"Only two of them can stay; {_ROOM}") -> str:
    return "{#made:" + "|".join([one, two, full] if n >= 3 else [one, full]) + "}"


COUNT_TOKENS: dict[tuple[str, int], list[tuple[str, str]]] = {
    ("rewrites", 270): [("They decide to stay.", _stay(3, "They decide to stay") + ".")],
    ("rewrites", 1512): [("They decide to stay.", _stay(3, "They decide to stay") + ".")],
    ("rewrites", 1524): [("The adult and the child stay.",
                          _stay(2, "The adult and the child stay", one=f"Only the adult can stay; {_ROOM}") + ".")],
    ("rewrites", 4242): [("and the baby, and stay.", "and the baby, and " + _stay(
        3, "stay", one=f"only one of them can stay; {_ROOM}", two=f"only two of them can stay; {_ROOM}") + ".")],
    ("balance", 139): [("They decide to stay.", _stay(3, "They decide to stay") + ".")],
    ("balance", 540): [("They just did.", _stay(3, "They just did", one=f"Only one of them can, as {_ROOM}",
                                                two=f"Only two of them can, as {_ROOM}") + ".")],
    ("balance", 543): [("They decide to stay.", _stay(3, "They decide to stay") + ".")],
    ("balance", 552): [("There is. They decide to stay.", _stay(
        3, "There is, and they decide to stay", one="There is, but only for one of them, who stays",
        two="There is, but only for two of them, who stay") + ".")],
    ("balance", 1312): [("They decide to stay.", _stay(3, "They decide to stay") + ".")],
    ("balance", 1315): [("They decide to stay.", _stay(3, "They decide to stay") + ".")],
    ("balance", 1324): [("They decide to stay.", _stay(3, "They decide to stay") + ".")],
    ("balance", 1552): [("They decide to stay.", _stay(3, "They decide to stay") + ".")],
    ("balance", 2231): [("They decide to stay.", _stay(3, "They decide to stay") + ".")],
    ("balance", 2584): [("They decide to stay.", _stay(3, "They decide to stay") + ".")],
    ("balance", 2593): [("They decide to stay, and are very glad, they say, to sleep under a proper roof.", _stay(
        3, "They decide to stay, and are very glad, they say, to sleep under a proper roof") + ".")],
    ("balance", 2729): [("They decide to stay.", _stay(3, "They decide to stay") + ".")],
    ("balance", 3267): [("The strangers decide to stay.", _stay(
        3, "The strangers decide to stay", one=f"Only one of the strangers can stay; {_ROOM}",
        two=f"Only two of the strangers can stay; {_ROOM}") + ".")],
    ("balance", 3581): [("They decide to stay.", _stay(3, "They decide to stay") + ".")],
    ("balance", 3584): [("They decide to stay,", _stay(3, "They decide to stay", one=f"Only one of them can stay, as {_ROOM}",
                                                        two=f"Only two of them can stay, as {_ROOM}") + ",")],
    ("balance", 3593): [("They decide to stay.", _stay(3, "They decide to stay") + ".")],
    ("balance", 5733): [("The couple stay.", _stay(3, "The couple stay") + ".")],
    ("balance", 5775): [("Then, a moment later, another.", "{#made:Then nothing more|Then, a moment later, another}."),
                        ("They both have (name)'s face", "{#made:The copy has|They both have} (name)'s face"),
                        ("They take the names (new name) and (new name 2), and they don't agree with each other about anything "
                         "either.", "{#made:The copy takes the name (new name), and doesn't agree with (name) about "
                                    "anything either|They take the names (new name) and (new name 2), and they don't agree "
                                    "with each other about anything either}.")],
    ("balance", 5962): [("They stay.", _stay(3, "They stay") + ".")],
    ("balance", 5971): [("They stay.", _stay(3, "They stay") + ".")],
    ("balance", 6254): [("splitting into two in mid-air, each half turning into a perfect (name) before it lands",
                         "{#made:turning into a perfect (name) in mid-air before it lands|splitting into two in "
                         "mid-air, each half turning into a perfect (name) before it lands}"),
                        ("Now there are three of (name)", "Now there are {#made:two|three} of (name)"),
                        ("The two copies take the names (new name) and (new name 2), and argue",
                         "{#made:The copy takes the name (new name), and they argue|The two copies take the names "
                         "(new name) and (new name 2), and argue}")],
    ("balance", 6443): [("The couple and their baby stay, and so does the old man.",
                         _stay(3, "The couple and their baby stay, and so does the old man") + ".")],
    ("balance", 6446): [("The second canoe stays:", _stay(
        3, "The second canoe stays", one="The second canoe stays, though the village has room for only one of them",
        two="The second canoe stays, though the village has room for only two of them") + ":")],
    ("balance", 6452): [("The couple and their baby stay.", _stay(3, "The couple and their baby stay") + ".")],
    ("balance", 7255): [("They all stay.", _stay(3, "They all stay") + ".")],
    ("balance", 7258): [("So she stays with them,", "So " + _stay(
        3, "she stays with them", one="she stays, though the village has room for no one else",
        two=f"she stays with one of them, as {_ROOM}") + ",")],
    ("balance", 7304): [("both babies scream until", "{#babies:the baby screams|both babies scream} until"),
                        ("They raise the twins together", "They raise {#babies:the baby|the twins} together")],
    ("balance", 7310): [("says two more won't", "says {#made:one more|two more} won't"),
                        ("The babies grow up", "{#made:The baby grows|The babies grow} up"),
                        ("and both of them, when they are old enough, become healers.",
                         "and {#made:when old enough, becomes a healer|both of them, when they are old enough, "
                         "become healers}.")],
    ("balance", 7313): [("The babies go home with", "{#babies:The baby goes|The babies go} home with")],
    ("balance", 7447): [("there are three of (him/her) standing",
                         "there are {#made:two|three} of (him/her) standing"),
                        ("as the three of them walk", "as the {#made:two|three} of them walk"),
                        ("Two of them take the names (new name) and (new name 2).",
                         "{#made:One of them takes the name (new name)|Two of them take the names (new name) and (new name 2)}.")],
    ("balance", 7495): [("and a second one climbs out after it", "{#made:but nothing else comes out|and a second one "
                                                                      "climbs out after it}"),
                        ("Two of them: (name)'s face, twice, and two completely different people inside",
                         "{#made:One of them: (name)'s face, and a completely different person inside|Two of them: "
                         "(name)'s face, twice, and two completely different people inside}"),
                        ("Both of them disagree with (name) and with each other",
                         "{#made:The copy disagrees with (name) about everything|Both of them disagree with "
                         "(subject) and with each other}"),
                        ("They take the names (new name) and (new name 2)",
                         "{#made:The copy takes the name (new name)|They take the names (new name) and (new name 2)}")],
    ("balance", 8353): [("They stay.", _stay(3, "They stay") + ".")],
    ("balance", 8362): [("The family stay.", _stay(3, "The family stay") + ".")],
    ("balance", 9727): [("Two more (name)s climb out, one from each pond: one warm and cheerful, one cold and cross.",
                         "{#made:One more (name) climbs out of one pond, warm and cheerful|Two more (name)s climb "
                         "out, one from each pond: one warm and cheerful, one cold and cross}."),
                        ("walk all three home", "walk all {#made:two|three} home"),
                        ("The newcomers take the names (new name) and (new name 2).",
                         "{#made:The newcomer takes the name (new name)|The newcomers take the names (new name) and "
                         "(made2)}.")],
    ("balance", 10151): [("and the four of them stay,", "and " + _stay(
        3, "the four of them stay", one=f"only one of them can stay, as {_ROOM}",
        two=f"only two of them can stay, as {_ROOM}") + ",")],
    ("balance", 10157): [("They stay.", _stay(3, "They stay") + ".")],
    ("balance", 10336): [("but the parents, their teenage daughter and their little son stay", "but " + _stay(
        3, "the parents, their teenage daughter and their little son stay",
        one=f"only one of them can stay, as {_ROOM}", two=f"only two of them can stay, as {_ROOM}"))],
    ("balance", 10348): [("good enough for them.", _stay(
        3, "good enough for them", one="good enough for them, though the village has room for only one of them",
        two="good enough for them, though the village has room for only two of them") + ".")],
    ("balance", 10998): [("Three heads come up", "{#made:Two heads|Three heads} come up"),
                         ("Three identical (name)s sit", "{#made:Two|Three} identical (name)s sit"),
                         ("and then all three, at once,", "and then {#made:both|all three}, at once,"),
                         ("The two new ones take the names (new name) and (new name 2), and bring home three times the crabs.",
                          "{#made:The new one takes the name (new name), and they bring home twice the crabs|The two new "
                          "ones take the names (new name) and (new name 2), and bring home three times the crabs}.")],
    ("balance", 11196): [("and her son, his wife and the tall grandson stay with the other", "and " + _stay(
        3, "her son, his wife and the tall grandson stay with the other",
        one=f"only her son can stay, as {_ROOM}", two=f"only her son and his wife can stay, as {_ROOM}"))],
    ("balance", 11323): [("The couple decide on the spot to stay.",
                          _stay(2, "The couple decide on the spot to stay") + ".")],
    ("balance", 11326): [("brings them in,", "brings them " + _stay(
        3, "in", one="in, though the village has room for only one of them",
        two="in, though the village has room for only two of them") + ",")],
    ("balance", 11332): [("they say, and they never leave.", _stay(
        2, "they say, and they never leave", one=f"they say; only one of them can stay, as {_ROOM}") + ".")],
    ("balance", 11789): [("The family stays in the village;", _stay(
        3, "The family stays in the village", one="Only one of them can stay in the village",
        two="Only two of them can stay in the village") + ";")],
    ("balance", 12095): [("and the family stays.", "and " + _stay(
        3, "the family stays", one="the village has room for only one of them",
        two="the village has room for only two of them") + ".")],
    ("balance", 12241): [("They never go back to their cove.", _stay(2, "They never go back to their cove") + ".")],
    ("balance", 13001): [("The family decides to stay,", _stay(
        2, "The family decides to stay", one=f"Only one of them can stay, as {_ROOM}") + ",")],
    ("balance", 13004): [("They stay.", _stay(3, "They stay") + ".")],
    ("balance", 13010): [("with a baby.", "with a " + _stay(
        2, "baby", one="baby, though the village has room for only one of them") + ".")],
    ("balance", 13581): [("brings the three of them home", "brings " + _stay(
        2, "the three of them home", one=f"one of them home, as {_ROOM}"))],
    ("balance", 13584): [("in the last hut standing.", "in the last hut " + _stay(
        3, "standing", one="standing, though the village has room for only one of them",
        two="standing, though the village has room for only two of them") + ".")],
    ("balance", 13590): [("They stay.", _stay(2, "They stay") + ".")],
    ("balance", 14172): [("They stay in the village.", _stay(
        2, "They stay in the village", one="Only one of them can stay in the village; there is no room for more") + ".")],
    ("balance", 14429): [("They stay.", _stay(2, "They stay") + ".")],
    ("balance", 14432): [("The family stays.", _stay(3, "The family stays") + ".")],
    ("balance", 14438): [("They stay.", _stay(2, "They stay") + ".")],
    ("balance", 14962): [("The village shares out the stores to feed three more, and nobody minds.", _stay(
        2, "The village shares out the stores to feed three more, and nobody minds",
        one="The village has room for only one of them") + ".")],
    ("balance", 14965): [("takes them all in", "takes " + _stay(
        3, "them all in", one=f"in one of them, as {_ROOM}", two=f"in two of them, as {_ROOM}"))],
    ("balance", 14971): [("brings the cousin, the cousin's partner and their baby home", "brings " + _stay(
        2, "the cousin, the cousin's partner and their baby home", one=f"the cousin home, as {_ROOM}"))],
    ("balance", 15588): [("and the little family moves into the village", "and " + _stay(
        2, "the little family moves into the village", one="one of them moves into the village, which has no room "
                                                           "for more"))],
    ("balance", 15594): [("insist on bringing the family back to the village", "insist on bringing " + _stay(
        2, "the family back to the village", one="one of them back to the village, which has no room for more"))],
    ("balance", 16621): [("and they move straight in", "and " + _stay(
        2, "they move straight in", one=f"one of them moves straight in, as {_ROOM}"))],
}
COUNT_USED: set[tuple[str, int]] = set()
COUNT_WHY = ("the owner's rule 13: the page makes several villagers or babies, as many as the game's room allows, so "
             "its words fit any count (a count token: one, two, three or more)")


class LeftOut(Exception):
    """An event the collection cannot take as written (listed for the owner)."""


PLACEHOLDER_FIXES = {"(Grandfather/Grandmother)": "Grand(father/mother)",
                     "(grandfather/grandmother)": "grand(father/mother)"}
A_AN_KEEP = re.compile(r"^(?:one|once|uni\w*|use\w*|usu\w*|euro\w*|ewe\w*|U\b|eu\w*|ut\w*|uk\w*)$", re.I)
VOWEL = re.compile(r"^[aeio]|^u(?!ni|s|t|r[aeiou]|k|ga|bi)|^hour|^honest|^honou?r|^heir", re.I)


# ---- Grammar fixes ----------------------------------------------------------------------------------------------------

def grammar_fixes(n: int) -> list[tuple[str, str, str]]:
    """(before, after, why) for line n: a doubled word, "a" before a vowel sound."""
    s = lib.normalize_source_text(lib.line(n))
    out = []
    for m in re.finditer(r"\b([A-Za-z]+) \1\b", s):
        w = m.group(1)
        if w.lower() in ("ha", "no", "very", "so", "far", "on", "bye", "knock", "tap", "drip", "boom", "round", "more",
                         "had", "that", "is", "again", "and", "over", "out", "back", "down", "away", "up", "slowly",
                         "deeper", "closer", "higher", "louder", "faster", "shh", "hush", "yes", "oh", "ah", "come",
                         "go", "run", "pull", "push", "row", "hush", "ow", "wait", "hey", "now", "baa", "la", "hm",
                         "mm", "tick", "tock", "thump", "splash", "crack", "plop", "bump", "chop", "swish", "hello",
                         "please", "help", "stop", "there", "never", "little", "many", "much", "long", "ago", "by"):
            continue
        before = s[max(0, m.start() - 12):m.end() + 1]
        if s.count(before) != 1:
            continue
        out.append((before, before.replace(f"{w} {w}", w, 1), f'"{w} {w}": a doubled word'))
    for m in re.finditer(r"(?<![A-Za-z'])([Aa]) ([A-Za-z]+)", s):
        art, word = m.groups()
        if A_AN_KEEP.match(word) or not VOWEL.match(word) or len(word) == 1:
            continue
        if s[max(0, m.start() - 1):m.start()] in ("-", "."):
            continue
        before_a = s[:m.start()].rstrip()
        if art == "A" and before_a and before_a[-1] not in '.!?"\'(':
            continue      # a capital "A" inside a sentence is a label ("Choice A", "Choices A and B"), not "a"
        before = s[max(0, m.start() - 8):m.end()]
        if s.count(before) != 1:
            continue
        out.append((before, before[:len(before) - len(m.group(0))] + f"{art}n {word}",
                    f'"{art} {word}": "an" before a vowel sound'))
    for m in re.finditer(r"\{#(?:babies|made):[^{}\n]*\}", s):
        after = owner.fix_count_tokens(m.group(0))
        if after != m.group(0) and s.count(m.group(0)) == 1:
            out.append((m.group(0), after, "a count token's options hold no . ! ? (the engine's rule): a comma "
                                           "instead, the closing mark dropped"))
    for before, after in PLACEHOLDER_FIXES.items():
        if before in s:
            out.append((before, after, f"the engine has no {before} word: {after} reads the same"))
    for before, after in COUNT_TOKENS.get((lib.active_source(), n), []):
        assert s.count(before) == 1, (lib.active_source(), n, before)
        out.append((before, after, COUNT_WHY))
        COUNT_USED.add((lib.active_source(), n))
    return out


# ---- One event --------------------------------------------------------------------------------------------------------

def L(n: int) -> str:
    return f"L{n}"


def span_src(lines: list[int]) -> str:
    out, run = [], None
    for n in lines:
        if run and n == run[1] + 1:
            run[1] = n
        else:
            if run:
                out.append(lib.fmt_src(*run))
            run = [n, n]
    if run:
        out.append(lib.fmt_src(*run))
    return ",".join(out)


class Layout:
    """Where each part of one event's block is: the heading, WHO, the story, the choices, popups, endings, the seed."""

    def __init__(self, a: int, b: int):
        self.head = a
        self.who: list[int] = []
        self.marks: list[int] = []            # EVENT TEXT, CHOICE X: headers
        self.notes: list[int] = []            # anything else outside the pages
        self.intro: list[int] = []
        self.labels: dict[str, int] = {}
        self.lead: dict[str, list[int]] = {}
        self.endings: dict[str, list[tuple[int, list[int]]]] = {}
        self.order: list[str] = []
        self.seed: tuple[int, int] | None = None
        mode, cur = "head", None
        for n in range(a + 1, b + 1):
            s = lib.line(n).strip()
            if not s or lib.is_separator(s):
                if mode == "lead":
                    mode = "choice"
                continue
            if owner._SEED.match(s):
                self.seed = (n, b)
                break
            if s.startswith("WHO:"):
                self.who.append(n)
                continue
            if s == "EVENT TEXT":
                self.marks.append(n)
                mode = "intro"
                continue
            mc = owner._CHOICE_LIST.match(s)
            if mc and mode in ("intro", "choices"):
                mode = "choices"
                self.labels[mc.group(1)] = n
                self.order.append(mc.group(1))
                continue
            mh = owner._CHOICE_HEAD.match(s)
            if mh:
                self.marks.append(n)
                cur, mode = mh.group(1), "choice"
                continue
            if s.startswith("First popup:") and cur:
                self.lead.setdefault(cur, []).append(n)
                mode = "lead"
                continue
            me = owner._ENDING.match(s)
            if me:
                self.endings.setdefault(me.group(1), []).append((n, []))
                cur, mode = me.group(1), "ending"
                continue
            if mode == "intro":
                self.intro.append(n)
            elif mode == "lead" and cur:
                self.lead[cur].append(n)
            elif mode == "ending" and cur:
                self.endings[cur][-1][1].append(n)
            else:
                self.notes.append(n)


def lenient_effects(text: str, games):
    """owner.owner_effects, a phrase it cannot map kept as story (UNMAPPED, with the phrase)."""
    try:
        return _real_owner_effects(text, games)
    except owner.Unmapped:
        pass
    out, roles, notes = [], {}, []
    for raw in owner.split_top(text.strip().rstrip(".")):
        try:
            e, r, nt = _real_owner_effects(raw, games)
        except owner.Unmapped:
            notes.append("UNMAPPED " + raw.strip())
            continue
        out += e
        roles.update(r)
        notes += nt
    return out, roles, notes


_real_owner_effects = owner.owner_effects


PRONOUN_RE = r"(?:he/she|his/her|him/her|himself/herself|his/hers|man/woman|woman/man|boy/girl|mother/father|" \
             r"father/mother|son/daughter)"


def prefix_roles(text: str, main: str, second: str | None) -> str:
    """An event of two or more villagers names each in every placeholder (collection rule): "(Name1)" ->
    "(subject)", "(he/she)" -> "(subject.he/she)", "(Name2)" -> "(friend)"."""
    def ph(m: re.Match) -> str:
        inner = m.group(1)
        low = inner.lower()
        if low in ("name", "name1"):
            return f"({main})"
        if low == "name2" and second:
            return f"({second})"
        if re.fullmatch(PRONOUN_RE, low):
            return f"({main}.{inner})"
        return m.group(0)
    return re.sub(r"(?<!\\)\(([^()\n]*)\)", ph, text)


def description(texts: list[str], title: str) -> str:
    """One plain sentence for Pick Island Event: the story's first sentence that reads without placeholders once its
    names are "a villager"."""
    for t in texts:
        t = re.sub(r"\\[()]", "", t)
        for sent in re.split(r"(?<=[.!?])\s+", t):
            s = re.sub(r"^\((?:Name1?|subject|villager)\)", "A villager", sent)
            s = re.sub(r"\((?:[Nn]ame1?|subject|villager)\)", "a villager", s)
            s = re.sub(r"\((?:[Nn]ame2|friend)\)", "another villager", s)
            s = s.replace('"', "")
            s = re.sub(r"\s+", " ", s).strip()
            if s[:1].islower():
                s = s[:1].upper() + s[1:]
            if cc.DESCRIPTION_RE.fullmatch(s) and len(s) <= cc.DESCRIPTION_MAX and len(s) > 25:
                return s
    t = re.sub(r"[^A-Za-z0-9 ,'-]", "", title).strip()
    return f"An island event: {t}."


def guardians_pairs(text: str, form: str) -> list[tuple[str, str]]:
    """The sentences `form` changes (the Guardians form of `text`), as (before, after) pairs."""
    a = re.split(r"(?<=[.!?])\s+|\n", text)
    b = re.split(r"(?<=[.!?])\s+|\n", form)
    if len(a) != len(b):
        return [(text, form)]
    return [(x, y) for x, y in zip(a, b) if x != y]


class Build:
    def __init__(self, sid: str, row: dict):
        self.sid, self.row = sid, row
        self.ledger: list[dict] = []
        self.fixes: list[dict] = []
        self.problems: list[str] = []
        self.unmapped: list[str] = []
        self.gpairs: list[tuple[str, str, str]] = []
        self.pieces: list[dict] = []
        self.left_pieces: list[str] = []

    def note(self, lines, kind: str, why: str, text: str | None = None) -> None:
        e = {"src": span_src(lines) if isinstance(lines, list) else L(lines), "kind": kind}
        if text is not None:
            e["text"] = text
        e["why"] = why
        self.ledger.append(e)

    def build(self) -> dict | None:
        a, b = self.row["lines"]
        lay = Layout(a, b)
        games = self.row["games"]
        # grammar fixes, made on the lines the importer reads
        fixed: dict[int, str] = {}
        for n in range(a, b + 1):
            s = lib.normalize_source_text(lib.line(n))
            if lay.seed and n >= lay.seed[0]:
                fixed[n] = s
                continue
            for before, after, why in grammar_fixes(n):
                s = s.replace(before, after)          # as the checker makes it (every occurrence)
                self.fixes.append({"src": L(n), "before": before, "after": after, "why": why})
            fixed[n] = s
        block = [(n, fixed[n]) for n in range(a, b + 1)]
        owner.owner_effects = lenient_effects
        try:
            items = pe._parse_owner(block, self.row["id"])
        finally:
            owner.owner_effects = _real_owner_effects
        it = items[0]
        pe._finish_simple(it)
        bad = [p for p in it.problems if "not in the phrase table" not in str(p)]
        if bad:
            self.problems += [f"{self.row['id']}: {p}" for p in bad]
        g = it.graph
        # the unmapped phrases, from each ending's notes
        for x, ends in lay.endings.items():
            for hl, _body in ends:
                m = owner._ENDING.match(lib.normalize_source_text(lib.line(hl)).strip())
                _e, _r, notes = lenient_effects(m.group(5), games)
                if (self.row["id"], hl) in OVERRIDES:
                    self.note(hl, "instruction", "the EFFECT mapped by hand (scripts/go_events/gen_go.py OVERRIDES): "
                                                 + OVERRIDES[(self.row["id"], hl)][0])
                    continue
                for nt in notes:
                    if nt.startswith("UNMAPPED "):
                        self.unmapped.append(f"{self.row['id']} L{hl}: {nt[9:]}")
                        self.note(hl, "instruction", f"{UNMAPPED_WHY}: {nt[9:]!r}")
        # ---- the ledger: everything that is not a page -----------------------------------------------------------
        self.note(lay.who, "note", "WHO: the event's casting, carried out as its roles (ages, sex, the head fisher "
                                   "or healer is flavor)") if lay.who else None
        for n in lay.marks:
            self.note(n, "structural", "a structural heading (EVENT TEXT, or a choice's own section heading)")
        for n in lay.notes:
            self.note(n, "note", "the writer's note, never shown")
        for x, n in lay.labels.items():
            self.note(n, "structural", "the choice's letter", text=re.match(r"^Choice [A-Z]\s*:",
                                                                           lib.normalize_source_text(lib.line(n)).strip()).group(0))
        for x, ns in lay.lead.items():
            self.note(ns[0], "structural", "the choice's own popup", text="First popup:")
        for x, ends in lay.endings.items():
            for hl, _body in ends:
                self.note(hl, "instruction", "the ending's name, chance and EFFECT: its branch weight and the page's "
                                             "effects")
        if lay.seed:
            self.note(list(range(lay.seed[0], lay.seed[1] + 1)), "note",
                      "the MIXER SEED: built as procedural pieces (data/procedural_pieces/go_seeds.json)")
            self.seed_pieces(items[1:])
        # ---- the pages' src --------------------------------------------------------------------------------------
        nodes = g["nodes"]
        roles = g["roles"]
        main = next(iter(roles))
        second = "friend" if "friend" in roles else None
        multi = len(roles) >= 2
        for r in roles.values():
            if r.get("believers_only") is False:
                # the owner (2026-11-16): "Heathens may be involved if needed for the event to make sense" -- the
                # role's WHO names an Isolan; collection_check's heathen_ok rules hold it to the safe effects
                r["heathen_ok"] = True
        # a loss's "Your village loses (award) food." is the game's own automatic line (the importer's rule)
        for k, x in enumerate(lay.order, 1):
            for j, (_hl, body) in enumerate(lay.endings.get(x, []), 1):
                if not nodes.get(f"c{k}o{j}", {}).get("auto_text"):
                    continue
                for n in body:
                    for m in re.finditer(AWARD_LOSS, lib.normalize_source_text(lib.line(n))):
                        self.note(n, "instruction", "a loss of (award): the game's own automatic line says it "
                                                    "(\"The village loses food.\")", text=m.group(0).strip())
        for rid, r in roles.items():
            if r.get("special") == "tribal_chief" and games != [3]:
                r.pop("special")      # the Chief is The Secret City's: elsewhere any villager leads (the checker's rule)
                self.note(lay.who or self.row["lines"][0], "note", f"WHO names the tribal chief for ({rid}); outside "
                                                                    "The Secret City any villager leads")
        nodes["ask"]["src"] = span_src(lay.intro)
        for k, x in enumerate(lay.order, 1):
            ch = nodes["ask"]["choices"][k - 1]
            ch["src"] = L(lay.labels[x])
            cid = f"c{k}"
            if x in lay.lead and cid in nodes and nodes[cid].get("text"):
                nodes[cid]["src"] = span_src(lay.lead[x])
            for j, (hl, body) in enumerate(lay.endings.get(x, []), 1):
                oid = f"c{k}o{j}"
                if oid in nodes:
                    nodes[oid]["src"] = span_src(body)
                    ov = OVERRIDES.get((self.row["id"], hl))
                    if ov:
                        alts = copy.deepcopy(ov[1])
                        nodes[oid].pop("effects", None)
                        if len(alts) == 1:
                            nodes[oid]["effects"] = alts[0]
                        else:          # "one of these, 50:50": equally likely branches after the page
                            assert not nodes[oid].get("children"), (self.row["id"], oid)
                            nodes[oid]["children"] = []
                            for i, effs in enumerate(alts, 1):
                                nodes[f"{oid}_r{i}"] = {"type": "branch", "effects": effs}
                                nodes[oid]["children"].append({"next": f"{oid}_r{i}"})
        # ---- placeholders, labels, effects -----------------------------------------------------------------------
        chief = games != [3]
        for n in nodes.values():
            n.pop("variants", None)
            if n.get("text"):
                t = prefix_roles(n["text"], main, second) if multi else n["text"]
                t = escape_bare(t)
                n["text"] = game_words(t) if chief else t
            if n.get("effects"):
                # a villager who leaves or dies goes last ("DISAPPEARS; CLONE of (name) ... in (his/her) place":
                # the copy is made first)
                n["effects"].sort(key=lambda e: e.get("do") in ("kill", "vanish", "die_unrecovered"))
            for c in n.get("choices", []) or []:
                lab = owner.normalize_text(c["label"].replace("\\(", "(").replace("\\)", ")"))
                lab = prefix_roles(lab, main, second) if multi else lab
                lab = lib.title_case_label(escape_bare(lab))
                c["label"] = game_words(lab) if chief else lab
            for e in n.get("effects", []) or []:
                if e.get("do") == "kill" and not e.get("cause"):
                    e["cause"] = "unknown"
                if not e.get("role") and not e.get("target") and e.get("do") not in VILLAGE_EFFECTS:
                    e["role"] = main          # the main villager, named (the collection's rule; the engine's default)
                if e.get("do") == "skill" and "size" in e:
                    lo, hi = cc.SKILL_SIZES[e.pop("size")]
                    e["min"], e["max"] = lo, hi
        # who a pronoun or an effect is about, where the main villager's is the wrong one (go_role_fixes.py)
        role_fixes.apply(self.row["id"], nodes)
        g.pop("title_variants", None)
        if "patches" in g:
            g["patches"] = [p for p in g["patches"] if p != pe.GUARDIANS_PATCH]
            if not g["patches"]:
                g.pop("patches")
        # ---- text_only: effect-table words a page says without that effect ------------------------------------------
        for n in nodes.values():
            if not n.get("src"):
                continue
            kinds = {cc.EFFECT_KIND.get(e.get("do"), e.get("do")) for e in n.get("effects", []) or []}
            tos = []
            for ln in lib.src_lines(n["src"]):
                s = lib.normalize_source_text(lib.line(ln))
                words = []
                for rx, want in cc.KEYWORDS:
                    if not (kinds & want):
                        words += [m.group(0).lower() for m in rx.finditer(s)]
                if words:
                    tos.append({"src": L(ln), "what": ", ".join(f'"{w}"' for w in dict.fromkeys(words)),
                                "reason": STORY_WHY})
            if tos:
                n["text_only"] = tos
        # ---- New Believers with Guardians of Isola Rewrite --------------------------------------------------------
        texts = [nodes["ask"]["text"]]
        if 5 in games:
            for nid, n in nodes.items():
                if n.get("text") and cc.GUARDIANS_WORDS.search(n["text"]):
                    form = pe._guardians(n["text"])
                    n["variants"] = [{"if": {"patch": pe.GUARDIANS_PATCH}, "text": form}]
                    self.gpairs += [(f"page ({nid})", x, y) for x, y in guardians_pairs(n["text"], form)]
                new_choices = []
                for c in n.get("choices", []) or []:
                    if cc.GUARDIANS_WORDS.search(c["label"]):
                        form = lib.title_case_label(pe._guardians(c["label"]))
                        self.gpairs.append((f"choice ({nid})", c["label"], form))
                        new_choices.append({**c, "if": {"not": {"patch": pe.GUARDIANS_PATCH}}})
                        new_choices.append({**c, "label": form, "if": {"patch": pe.GUARDIANS_PATCH}})
                    else:
                        new_choices.append(c)
                if n.get("choices"):
                    n["choices"] = new_choices
            if cc.GUARDIANS_WORDS.search(self.row["title"]):
                form = pe._guardians(self.row["title"])
                g["title_variants"] = [{"if": {"patch": pe.GUARDIANS_PATCH}, "title": form}]
                self.gpairs.append(("title", self.row["title"], form))
            if self.gpairs:
                g["patches"] = list(dict.fromkeys((g.get("patches") or []) + [pe.GUARDIANS_PATCH]))
        desc = description(texts, self.row["title"])
        col = {"id": self.row["id"], "title_src": L(a), "ledger": self.ledger, "description": desc,
               "label_case": "title", "exact_amounts": True}
        if 5 in games and cc.GUARDIANS_WORDS.search(desc):
            form = pe._guardians(desc)
            col["description_variants"] = [{"if": {"patch": pe.GUARDIANS_PATCH}, "description": form}]
            self.gpairs.append(("Pick Island Event description", desc, form))
        doc = {"format": "vvfp-cie-graph", "version": 6, "title": self.row["title"], "games": games,
               "collection": col}
        every = json.dumps(nodes)
        for w, per in CHIEF_WORDS.items():
            if "{@" + w + "}" in every:
                g.setdefault("words", {})[w] = dict(per)
        for k in ("title_variants", "patches", "words", "pools", "requirement", "roles", "start", "nodes"):
            if k in g:
                doc[k] = g[k]
        if self.fixes:
            doc["grammar_fixes"] = [{k: f[k] for k in ("src", "before", "after")} for f in self.fixes]
        # a villager cast only for the event's gate (a story that names nobody: "the granary gets wet")
        rep = cc.Report("x")
        with lib.use_source(self.sid):
            cc.check_tokens(doc, None, rep)
        unused = [m.group(1) for p in rep.problems for m in [re.search(r"role (\w+) is declared but never used", p)]
                  if m]
        if unused:
            col["cast_only"] = unused
        return doc

    def seed_pieces(self, items: list) -> None:
        for it in items:
            p = copy.deepcopy(it.piece)
            p["slots"] = {k: v[0] for k, v in p["slots"].items()}
            p["effects"] = [e for _ln, e in p["effects"]] if p["effects"] and isinstance(p["effects"][0], tuple) \
                else p["effects"]
            p["src"] = L(it.line)
            p["source"] = self.sid
            p["event"] = self.row["id"]
            p["family"] = p.get("family") or ""
            # the importer's stricter label rule ("Walk, and Follow") is not the collection's
            # (collection_lib.title_case_label): such a label is kept; any other problem leaves the piece out
            bad = [str(q) for q in it.problems if "not in Title Case" not in str(q)]
            if bad:
                self.left_pieces += [f"{self.row['id']} piece {p['id']}: {q}" for q in bad]
                continue
            p["label"] = lib.title_case_label(p["label"]) if p.get("label") and p["kind"] == 2 else p.get("label", "")
            self.pieces.append(p)


# ---- The files --------------------------------------------------------------------------------------------------------

def rows(sid: str) -> list[dict]:
    data = json.loads(lib.MANIFEST.read_text(encoding="utf-8"))
    return sorted((r for r in data["rows"] if r.get("source") == sid and r["kind"] == "event"),
                  key=lambda r: r["lines"][0])


def write_section(path: Path, marks: tuple[str, str], body: list[str], heading: str) -> None:
    text = path.read_text(encoding="utf-8")
    block = marks[0] + "\n" + "\n".join(body) + "\n" + marks[1]
    if marks[0] in text:
        pre, rest = text.split(marks[0], 1)
        post = rest.split(marks[1], 1)[1]
        text = pre + block + post
    else:
        text = text.rstrip("\n") + "\n\n" + heading + "\n\n" + block + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def cell(s: str) -> str:
    return s.replace("|", "/")


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    report = argv[:1] == ["--report"]
    want = list(lib.GO_SOURCES)          # always both: the docs tables and the pieces file hold both files
    docs, problems, unmapped, gram, guard, pieces, left_pieces = [], [], [], [], [], [], []
    for sid in lib.GO_SOURCES:
        if sid not in want:
            continue
        with lib.use_source(sid):
            for r in rows(sid):
                b = Build(sid, r)
                try:
                    doc = b.build()
                except Exception as ex:      # one event's failure never stops the rest; it is listed
                    problems.append(f"{r['id']}: could not be built: {type(ex).__name__}: {ex}")
                    continue
                problems += b.problems
                unmapped += b.unmapped
                pieces += b.pieces
                left_pieces += b.left_pieces
                for f in b.fixes:
                    gram.append(f"| {sid} {f['src']} | `{f['before']}` | `{f['after']}` | {cell(r['title'])} | "
                                f"{f['why']} |")
                for where, before, after in b.gpairs:
                    guard.append(f"| `{r['id']}` | {where} | {cell(before)} | {cell(after)} |")
                sec = r["section"]
                docs.append((lib.COLLECTION_DIR / sid / sec / f"{r['id']}.json", doc))
    stale = sorted(set(COUNT_TOKENS) - COUNT_USED)
    problems += [f"COUNT_TOKENS {k}: no event page reads this line" for k in stale]
    if report:
        for p in problems:
            print("LEFT OUT" if "LeftOut" in p else "PROBLEM", p)
        for p in left_pieces:
            print("PIECE LEFT OUT", p)
        for u in unmapped:
            print("STORY ONLY", u)
        return 0
    write_section(lib.GRAMMAR_FIXES_DOC, GRAMMAR_MARK,
                  ["The owner's GO files (rewrites, balance; 2026-11-16): fixed automatically by "
                   "scripts/go_events/gen_go.py (a doubled word, \"a\" before a vowel sound, a count token's "
                   "options without . ! ?, a word the engine has no placeholder for).", "",
                   "| Line | Before | After | Event | Why |", "|---|---|---|---|---|", *gram],
                  "### The GO files (rewritten and balance events)")
    write_section(lib.GUARDIANS_DOC, GUARDIANS_MARK,
                  ["The owner's GO files (2026-11-16): each sentence New Believers shows with the patch "
                   "(docs/event-collection/guardians-wording.md \"Believers\": by sense).", "",
                   "| Event | Where | Before | After |", "|---|---|---|---|", *guard],
                  "## The GO files (rewritten and balance events)")
    lib.guardians_pairs.cache_clear()
    for p in problems:
        print("LEFT OUT" if "LeftOut" in p else "PROBLEM", p)
    for p in left_pieces:
        print("PIECE LEFT OUT", p)
    print(f"{len(docs)} events written, {len(unmapped)} EFFECT phrases kept as story, {len(gram)} grammar fixes, "
          f"{len(pieces)} pieces")
    paths = []
    for sid in want:          # a file of an event now left out never lingers
        for old in (lib.COLLECTION_DIR / sid).glob("*/*.json"):
            old.unlink()
    for p, doc in docs:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(cc.canonical(doc), encoding="utf-8", newline="\n")
        paths.append(str(p))
    PIECES_OUT.parent.mkdir(parents=True, exist_ok=True)
    body = ",\n".join(json.dumps(p, ensure_ascii=False, sort_keys=True) for p in pieces)   # one piece a line
    PIECES_OUT.write_text('{"format": "vvfp-go-pieces", "version": 1, "pieces": [\n' + body + "\n]}\n",
                          encoding="utf-8", newline="\n")
    rc = cc.main(["--format", *paths])      # in process: 675 paths are too long for one command line
    return rc or (1 if [p for p in problems if "LeftOut" not in p] else 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
