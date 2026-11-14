"""Branching Custom Island Events: the node-graph format, its checks, its binary form and its odds.

The owner (v1.35.97): "allow the player to create multiple branching complicated outcome events like I just made for
Aspiring Adventurer in Custom Island Events".  The owner's rules: outside files instead of squeezing things into the
game; Custom Island Events skip the natural-event requirement (two eligible villagers); risky effects are allowed with a
warning (refuse only a crash or corruption); patched text never runs off the screen.

Phase 1 is this module: the JSON format a graph is written in, every check a graph must pass, the compact binary .cieg
the Story / Cheat Upgrades companion reads (phase 2), and the "chances of every outcome" table.  Nothing here touches a
game, a save or an exe.

THE JSON FORMAT  ("format": "vvfp-cie-graph", "version": 2; version 1 is still read, and checked by its own rules)
------------------------------------------------------------
  VERSION 2 (v1.35.97, the owner: "build branching events as complex as The Cave Explorers") lets a question be ANY
  node, any number of times on a history, mixed freely with chance splits, conditions and changes; it adds the
  double quote to the characters text may use.  Its rules: a question makes no changes itself; after each answer a
  page (a "popup" node) is shown before the next question or the end (the game shows the answer's result page at the
  click: it cannot be a question); changes before a question come with a page of their own; at most
  MAX_QUESTIONS_PER_RUN questions and MAX_POPUPS_PER_RUN_V2 popups on one history.  Version 1 keeps exactly its old
  rules (a question only at the start, six popups), and its .cieg is the same bytes as before.

  VERSION 3 (the owner, 2026-11-13: "add all three") adds
    * award ranges: {"do": "food" | "tech", "amount": min, "max": max, ...} -- each amount min..max equally likely,
      drawn with the walk that reaches it (the game's own random routine), then scaled by "Island Events Scale" as a
      fixed amount is; the (award) placeholder shows the amount drawn;
    * "only after a puzzle is solved": requirement {"puzzles": {"<game>": ["<puzzle>", ...]}} with each game's
      puzzles as PUZZLES lists them -- the purchase is refused until every one listed for the game played is solved;
    * "at most N years apart": a villager role's {"max_age_gap": {"role": other, "years": N}} -- the roles are
      filled only by villagers within N years of each other; no such pair: the purchase is refused, as when no
      villager fits a role (and at delivery the event keeps waiting).
  Version 1 and 2 graphs load, compile and play exactly as before.

  VERSION 5 (the owner, v1.35.97: "per-game award ranges in one reward step"): a food / tech effect may carry
  "per_game": {"<game>": [min, max], ...} -- each listed game's own amount (min = max) or range, drawn and scaled as
  a version 3 range is; a game not listed uses the effect's "amount" (and "max").  In the .cieg it is the effect's
  string, "<game>:<min>-<max>;..." (games increasing), which a version 1-4 effect never has.  Versions 1 to 4 load,
  compile and play exactly as before.

  VERSION 4 (the owner, 2026-11-13: "Make the 2-4 option thing general"): a question has 2, 3 or 4 "choices", each
  with its own label and its own next part.  The game shows them in its own two-choice popup with one or two more
  buttons made as it makes its two (native/shared/vvfp_multi_answer.h; vvfp_multi_answer_12.h for A New Home and The
  Lost Children),
  stacked and centred; the keys 1 to 4 pick them where the game delivers keys.  The question's popup (and its
  answer's first page, shown in it) keeps ANSWER_LINES text lines for each answer past two, so it is no taller than
  with two.  Every other rule is version 3's.  Versions 1, 2 and 3 load, compile and play exactly as before.

  {
    "format": "vvfp-cie-graph", "version": 2,
    "title": "The Aspiring Adventurer",          # the popups' title: 47 bytes, one line in every game listed
    "games": [1, 2, 3, 4, 5],                     # the games it is made for (A New Home .. New Believers)
    "patches": ["guardians_of_isola"],            # patch ids the conditions may name ([a-z0-9_])
    "requirement": {"min_eligible": 2},           # a shipped event's natural requirement (eligible villagers);
                                                  # IGNORED by Custom Island Events (the owner: the player decides)
    "roles": {
      "subject":  {"kind": "villager"},           # the main villager; the first role is "subject"
      "friend":   {"kind": "villager", "optional": true},
      "stranger": {"kind": "stranger", "sex": "random"}
    },
    "start": "intro",
    "nodes": { "<id>": NODE, ... }
  }

  ROLE (villager): "optional" (default false: the event needs it), "sex" "any" | "male" | "female", "min_age" years
  (default 14), "exclude_nursing" (default true: never a mother or father nursing a baby), "exclude_special" (default
  true: SPECIAL_VILLAGERS below), "believers_only" (default true: New Believers' believers only).  Two villager roles are
  always two different villagers.  ROLE (stranger): no record, only a sex: "random" (default), "male" or "female".

  NODE:
    "type": "popup" (default) | "question" | "branch"
        popup     text shown in a popup;
        question  text and two "choices" [{"label", "next"}] (the game's two-button popup) -- version 4: two to
                  four; version 1: the start node only;
        branch    no text and no popup: a silent weighted split (e.g. "survives" vs "deadly").
    "popup": "new" (default) | "append"           append: the text continues the popup open on the path
    "join": "space" (default) | "paragraph"       how an appended text joins the popup's text
    "text": "..."                                 paragraphs split by "\n"; placeholders below
    "variants": [{"if": COND, "text": "..."}]     the first whose condition holds replaces "text"
    "effects": [EFFECT, ...]                      applied when the node is reached
    "children": [{"next": id, "weight": 1.., "if": COND, "else": id}]
        one child is drawn, weighted.  A child whose "if" fails is replaced by its "else" (same weight) or, with no
        "else", left out.  None left: the node's "else"; no children at all: the event ends here.
    "else": id                                    the fallback when no child is left
    "summary": "..."                              the ending's words in the chances table (never shown in game)
    "outcome": "..."                              the "In all" group of the chances table (default from the effects)

  COND: {"visited": id} | {"role": id} (bound in this event) | {"game": n or [n, ...]} | {"patch": id} |
        {"not": COND} | {"all": [COND, ...]} | {"any": [COND, ...]}

  EFFECT ("role" defaults to "subject"; every villager effect needs a villager role):
    {"do": "food" | "tech", "amount": n, "scaled": bool, "defer": bool}
        add (or, below 0, take) food / tech points; "scaled": the "Island Events Scale ..." patches apply;
        "defer": not given yet -- the event's award, given by a later {"do": "pay_award"} (once)
    {"do": "pay_award"}
    {"do": "kill", "role": r, "cause": "custom" | "unknown" | "<words>"}
        custom = "Died in a custom island event" (today's CIE), unknown = "Unknown causes" (the stock island events)
    {"do": "vanish", "role": r}                    gone for good, no grave
    {"do": "status", "role": r, "status": "heathen"}   New Believers only
    {"do": "health", "role": r, "min": 1..100, "max": 1..100}    ("value": n for min = max)
    {"do": "preference", "role": r, "list": "likes" | "dislikes", "preference": "<the game's own word>"}
    {"do": "skill", "role": r, "skills": ["Farming", ...], "min": n, "max": n}   one skill at random, + min..max
    {"do": "sick", "role": r}

  PLACEHOLDERS in text and labels (a role prefix "friend." / "stranger." picks the role; no prefix = the subject):
    (name) (Name)                          the villager's name (never a stranger's)
    (name1) (Name1) / (name2) (Name2)      the subject / the role "friend"
    (he/she) (He/She) (his/her) (His/Her) (him/her) (Him/Her) (man/woman) (Man/Woman)   by that role's sex
    (award) (award_unit)                   the award's amount actually given, and "food" / "tech points"
  Text is the Custom Island Event's character set: letters, digits, space and . , ! ? : - ' -- and, in version 2, the
  double quote " (every game's font draws it: src/vv_font_glyphs.py) -- so a parenthesis is only ever a placeholder.

WHAT A GRAPH MUST PASS (validate):  every next / else / start names a node; no cycle; every node reachable; on every
history (every game, every patch on or off, every optional role bound or not) a node with children has one or an else;
weights 1..MAX_WEIGHT; a question has exactly two choices -- version 4: two to four (version 1: and is the start
node; version 2: the page
rules above); titles, labels and text fit each game
with the longest names (FIT below); only the allowed characters; every effect is one the game's Custom Island Event
supports (GAMES[g].caps, the CAP_* bits of native/vvfp_story_upgrades/story_custom.h and story_c1..c5.inc); no more than
MAX_POPUPS_PER_RUN popups on any history; a role used where it may be unbound, an award paid that was never deferred,
or an effect on a villager already gone are errors.

FIT.  The text is laid out as the companion's ce_wrap lays it out (words wrapped at the popup's characters a line;
a word longer than a line is cut), with the longest name the game holds (GAMES[g].name_room characters -- (name) is
the FULL name when the patcher's Last Names are on, the owner 2026-11-12, and Last Names never makes "first last"
longer than this room: vv_last_names.ROOM, pinned equal in tests/test_cie_graph.py), the longer
pronoun, and the award's widest amount.  Without scrolling a popup is shown in pages (whole paragraphs where they fit,
else whole sentences, as the shipped Aspiring Adventurer pages its text): a sentence taller than a page, or more than
MAX_PAGES pages, runs off the screen.  With scrolling (v1.35.97's popup scrollbars) any height fits and only the bytes
the game's popup holds (POPUP_TEXT_MAX) count.

THE BINARY .cieg (version 1 or 2, little-endian) -- see compile_graph / decompile_graph.  Version 2 is laid out exactly as
version 1; its number says a question may be any node (and text may hold "), so a companion that reads only version 1
refuses it cleanly instead of misreading it.  A version 1 graph is compiled as version 1.  Version 4 is laid out as
version 3; its number says a question's children may be two to four choices (a companion that reads only up to
version 3 refuses it).
  header (80 bytes)
     0 4s magic "CIEG"          4 H version (1, 2)         6 H header bytes (80)     8 I file bytes
    12 I crc32 of the whole file with this field 0      16 I games mask (bit g-1)
    20 H title string           22 H start node          24 H requirement min_eligible (0 = none)
    26 H role count  28 H node count  30 H child count  32 H effect count  34 H cond count  36 H variant count
    38 H string count  40 H patch count  42 H the requirement's condition (version 3: an ALL of puzzle conditions,
    op 8: a = the puzzle's name, b = its game; NONE = none; 0 in versions 1 and 2)
    44 I roles  48 I nodes  52 I children  56 I effects  60 I conds  64 I variants  68 I patches  72 I strings (offsets)
    76 I 0
  role     8 bytes: B kind (0 villager, 1 stranger), B flags (1 optional, 2 exclude_nursing, 4 exclude_special,
                    8 believers_only), B sex (0 any, 1 male, 2 female, 3 random), B min_age years, H id string,
                    B age-gap role + 1 (0 none), B its years (version 3; 0 0 before)
  node    28 bytes: B type (0 popup, 1 question, 2 branch), B popup (0 new, 1 append), B join (0 space, 1 paragraph),
                    B 0, H id string, H text string, H first variant, H variants, H first child, H children
                    (a question's: its two choices), H else node, H first effect, H effects, H summary string,
                    H outcome string, H 0
  child   12 bytes: H next node, H weight, H cond, H else node, H label string (choices only), H 0
  effect  16 bytes: B type (EFFECT_CODES), B role, B flags (1 scaled, 2 defer, 4 dislikes), B 0, i a, i b, H string, H 0
                    food/tech a = amount (b = a range's top, version 3; 0 = fixed); health a..b; skill a..b and string = the skills, comma separated;
                    preference string = the word; kill string = the cause; status a = 1 (heathen)
  cond     8 bytes: B op (COND_CODES), B operand count, H a, H b, H 0 -- visited a = node, role a = role, game a = mask,
                    patch a = patch, not a = operand, all / any: operands a .. a + count - 1 (consecutive)
  variant  4 bytes: H cond, H text string
  patch    2 bytes: H id string
  strings: I offset[count] from the strings section, then NUL-terminated ASCII.  NONE = 0xFFFF everywhere.
"""
from __future__ import annotations

import copy
import json
import re
import struct
import sys
import zlib
from dataclasses import dataclass, field, replace
from fractions import Fraction
from functools import lru_cache
from itertools import product
from pathlib import Path
from typing import Any, Iterable

FORMAT = "vvfp-cie-graph"
VERSION = 3                   # what new events are written in (a third answer makes an event version 4)
VERSION_ANSWERS = 4           # the first version whose questions may have three or four answers
VERSION_PER_GAME = 5          # the first version whose food / tech effect may give each game its own amount or range
VERSION_V6 = 6               # the Isola Grand Event Collection: pools, game words, aliases, requirements, 5-7 answers
VERSIONS = (1, 2, 3, 4, 5, 6)  # what this patcher reads
BINARY_MAGIC = b"CIEG"
BINARY_VERSION = 6            # a graph is compiled as its own version (1 to 5 byte for byte as before)
MIN_ANSWERS = 2               # a question's answers (version 4: 2..4; version 6: 2..7; before: exactly 2)
MAX_ANSWERS = 7               # version 6: up to seven buttons (vvfp_multi_answer.h)
MAX_ANSWERS_V4 = 4            # versions 4 and 5: the game's two-choice popup with up to two more buttons
ANSWER_LINES = 3              # text lines a third or fourth answer's button takes (1.5 button heights of 20-px lines)
NONE = 0xFFFF

TITLE_BYTES = 47              # CE_TITLE_BYTES 48, NUL included
BUTTON_BYTES = 39             # CE_BUTTON_BYTES 40, NUL included
NODE_TEXT_MAX = 1990          # a node's text, bytes
POPUP_TEXT_MAX = 1990         # a popup's text, bytes (the later games build the popup text in 2,000)
MAX_PAGES = 10                # pages a popup may take without scrolling (the shipped event's ADV_MAX_PAGES)
MAX_POPUPS_PER_RUN = 6        # popups on one history, the question's included (version 1)
MAX_POPUPS_PER_RUN_V2 = 16    # ... version 2 (questions anywhere): the companion keeps 96 pages a run
MAX_QUESTIONS_PER_RUN = 16    # questions on one history (version 2; story_graph.inc CG_MAX_QUESTIONS)
MAX_WEIGHT = 10000
MAX_NODES = 1000
MAX_PATHS = 200000
MAX_AMOUNT = 0x7FFFFFFF - 1000000   # CE_MAX_AMOUNT
HEALTH_MAX = 100
SKILL_ADD_MAX = 100
REFUSAL_LINES = 2             # a blank line and "N changes could not be made." under a popup with villager effects
AWARD_WIDEST = 10             # a scaled award's widest amount, digits (CE_MAX_AMOUNT)
CAUSE_BYTES = 63
ID_RE = re.compile(r"^[A-Za-z0-9_]{1,32}$")
NAME_MAX = 60                 # a part's name (node "name"): the editor's words for it, never compiled


def name_problem(name: str) -> str | None:
    """Why `name` cannot be a part's name (the owner: what the author sees is plain words, never a code label), or
    None: 1 to NAME_MAX letters, digits, spaces and . , ! ? : - ' ( ) /, starting with a letter or digit."""
    if not isinstance(name, str) or not name.strip() or len(name) > NAME_MAX:
        return f"is 1 to {NAME_MAX} characters"
    if not (name[0].isascii() and name[0].isalnum()):
        return "starts with a letter or a digit"
    if not all((c.isascii() and c.isalnum()) or c in " .,!?:-'()/" for c in name):
        return "has only letters, digits, spaces and . , ! ? : - ' ( ) /"
    return None
PATCH_RE = re.compile(r"^[a-z0-9_]{1,48}$")

# ---- The games: the CAP bits and popups of native/vvfp_story_upgrades (story_custom.h, story_c1..c5.inc) ----

CAP_FOOD = 0x00000001
CAP_TECH = 0x00000002
CAP_REFILL = 0x00000004
CAP_SPAWN = 0x00000008
CAP_KILL = 0x00000010
CAP_VANISH = 0x00000020
CAP_SICK = 0x00000040
CAP_PREGNANT = 0x00000080
CAP_PREFS = 0x00000100
CAP_APPEARANCE = 0x00000200
CAP_SKILLS = 0x00000400
CAP_PARENTS = 0x00000800
CAP_TITLE = 0x00001000
CAP_MASK = 0x00002000
CAP_STATUS = 0x00004000
CAP_BEHAVIOUR = 0x00008000
CAP_VILLAGE = 0x00010000
CAP_SPAWN_NAME = 0x00020000
CAP_SPAWN_FACTION = 0x00040000
CAP_MALE_PREGNANCY = 0x00080000
CAP_VALUES = 0x00100000
CAP_PUZZLES = 0x00200000
CAP_CANCEL = 0x00400000
CAP_RELITTER = 0x00800000
CAP_UNBORN = 0x01000000
CAP_REVIVE = 0x02000000
CAP_CHOICE = 0x04000000
CAP_FAITH = 0x08000000

_COMMON = (CAP_FOOD | CAP_TECH | CAP_REFILL | CAP_SPAWN | CAP_KILL | CAP_VANISH | CAP_SICK | CAP_PREGNANT | CAP_PREFS
           | CAP_APPEARANCE | CAP_SKILLS | CAP_PARENTS | CAP_TITLE | CAP_MASK | CAP_BEHAVIOUR | CAP_SPAWN_NAME
           | CAP_MALE_PREGNANCY | CAP_VALUES | CAP_PUZZLES | CAP_CANCEL | CAP_RELITTER | CAP_UNBORN | CAP_REVIVE
           | CAP_CHOICE)

_PREFS_VV1 = ("ants,crowds,resting,laundry,medicine,turnips,butterflies,flowers,bees,the dark,caves,herbs,berries,"
              "snakes,wind,rocks,rough wood,the ocean,playing,exploring,blue,green,red,yellow,drums,bushes,bananas,"
              "coconuts,sand,sunlight,drift wood,crab meat,whale meat,fish,fruit,papaya,flies,swimming,running,"
              "dancing,monkeys,birds,work,lifting,surprises,jokes,sleeping")
_PREFS_VV2 = ("ants,crowds,resting,laundry,medicine,turnips,butterflies,flowers,bees,the dark,caves,herbs,berries,"
              "snakes,wind,rocks,heights,the ocean,playing,exploring,blue,green,red,yellow,drums,bushes,bananas,"
              "coconuts,sand,sunlight,wood,crab meat,whale meat,fish,fruit,papaya,flies,swimming,running,learning,"
              "dancing,monkeys,parrots,work,lifting,surprises,jokes,sleeping,jumping,cooking,fire,eating,dragonflies,"
              "owls,dreaming,children,talking,holidays,vegetables,quiet,clouds,dirt")
_PREFS_VV3 = (_PREFS_VV2 + ",alchemy,potions,magic,plants,rain,fog,sitting,sharks,honey,stories,coral,thunder,"
              "lightning,pearls,stars,mango,nature")
_PREFS_VV45 = (_PREFS_VV2 + ",frogs,soap,magic,plants,rain,fog,sitting,sharks,honey,stories,coral,thunder,"
               "lightning,pearls,stars,mango,nature")


@dataclass(frozen=True)
class Layout:
    width: int           # characters a line
    lines: int           # lines, the title's included when with_title
    with_title: bool     # the text starts with the title and four line breaks (A New Home, The Lost Children)


@dataclass(frozen=True)
class Game:
    number: int
    name: str
    caps: int
    name_room: int       # the longest name the game holds, characters
    title_width: int
    plain: Layout        # the plain island-event popup (a graph whose start is not a question)
    question: Layout     # the two-choice question popup
    result: Layout       # every later popup
    label_width: int     # a label's characters: the bytes the companion keeps (CE_BUTTON_BYTES - 1)
    skills: tuple[str, ...]
    preferences: tuple[str, ...]
    statuses: dict[str, int]          # status word -> the game's status list index
    special: str                      # who exclude_special leaves out (the companion applies it)


GAMES: dict[int, Game] = {
    1: Game(1, "A New Home", _COMMON | CAP_VILLAGE | CAP_STATUS, 27, 51,
            Layout(51, 14, True), Layout(49, 13, True), Layout(49, 13, True), 39,
            ("Parenting", "Building", "Farming", "Healing", "Research"), tuple(_PREFS_VV1.split(",")), {},
            "the Golden Child"),
    2: Game(2, "The Lost Children", _COMMON | CAP_STATUS, 23, 46,
            Layout(46, 20, True), Layout(46, 16, True), Layout(46, 16, True), 39,
            ("Parenting", "Building", "Farming", "Healing", "Research"), tuple(_PREFS_VV2.split(",")), {},
            "the Esteemed Elders' totem statues"),
    3: Game(3, "The Secret City", _COMMON | CAP_STATUS, 23, 30,
            Layout(48, 14, False), Layout(48, 11, False), Layout(48, 11, False), 39,
            ("Farming", "Parenting", "Healing", "Research", "Building"), tuple(_PREFS_VV3.split(",")), {},
            "the tribal chief"),
    4: Game(4, "The Tree of Life", _COMMON | CAP_VILLAGE, 23, 30,
            Layout(48, 14, False), Layout(48, 11, False), Layout(48, 11, False), 39,
            ("Farming", "Parenting", "Healing", "Research", "Building"), tuple(_PREFS_VV45.split(",")), {},
            "no one else"),
    5: Game(5, "New Believers", _COMMON | CAP_STATUS | CAP_SPAWN_FACTION | CAP_FAITH, 23, 30,
            Layout(48, 14, False), Layout(48, 11, False), Layout(48, 17, False), 39,
            ("Farming", "Parenting", "Healing", "Research", "Building", "Devotion"), tuple(_PREFS_VV45.split(",")),
            {"heathen": 1},
            "the Heathens (believers_only), the chief, the Retired Chief, the other special roles the game never "
            "sends on events, and Reanimated spirits"),
}

# ---- Puzzles (version 3: "only after a puzzle is solved") ----------------------------------------------------------
#
# Each game's puzzles as its Custom Island Event adapter lists them (native/vvfp_story_upgrades/story_c1..c5.inc
# C<n>_PUZZLE_DEFS, mirrored in tests/test_cie_graph.py).  The companion reads a puzzle solved from the same flag the
# game's Puzzles and Statistics screens read (the adapter's puzzle_solved: A New Home's world bytes, e.g. The Cave
# [world +0x9FA8], world = [0x48AEDC]; the other games' tables beside it).

PUZZLES: dict[int, tuple[str, ...]] = {
    1: ("The Well", "The Hut (the first small hut)", "The Beach", "The School", "The Lagoon",
        "The Magic Fish of Fertility", "The Cemetery", "Herb Mastery", "The Garden", "The Magic Plant of Life",
        "The Temple", "The Idol", "The Butterflies", "The Treasure", "The Cave",
        "The second small hut (not on the Puzzles screen)", "The third small hut (not on the Puzzles screen)"),
    2: ("The Lovely Hut (not on the Puzzles screen)", "Fire", "The Scarecrow", "The Elder Totem", "The Hospital",
        "Herb Mastery", "The Sewing Hut", "The Dam", "The Cutting Tool", "The Stew", "The Vine Wall",
        "The Ancient Mosaic", "The Boxed Gong Piece", "The Sunken Gong Piece", "The Inlaid Gong Piece",
        "The Overgrown Gong Piece", "Sustainable Fishing"),
    3: ("The First Chief", "The Bee Hive", "The Alchemy Lab", "The Roster of the Dead", "Weather Dancing", "The Lift",
        "The Ruins", "The Ancient Bath", "The Statue", "The Orchard", "The Sharks", "Aromatherapy", "The Ash Key",
        "The Cliff Key", "The Clam Key", "The Chief and the Princess"),
    4: ("The Cutting Tool", "The Stream", "Boiling Water", "Soap Invented", "The Butterflies", "The Frog Rescue",
        "The Cooking Pit", "Cloth Invented", "The Nursery School", "The Mossy Rocks", "The Grand Feast",
        "Fishing Nets", "Pruning the Tree", "Honoring the Tree", "Purify Tree", "Decorating the Tree"),
    5: ("The Nursery School (the milestone, not on the Puzzles screen)", "The Prison Break", "The Hungry Totem",
        "The Knowing Totem", "The Buried Mausoleum", "The Blocking Totem", "The Hollow Totem", "The Lake",
        "The Pain Totem", "The Rainbow Totem", "The Tribute Statue", "The Blind Totem",
        "Hut 1 (not on the Puzzles screen)", "Hut 2 (not on the Puzzles screen)", "Hut 3 (not on the Puzzles screen)",
        "The clothing hut", "The love shack", "The nursery school building"),
}
MAX_AGE_GAP = 80              # years

# ---- Effects, conditions, placeholders ----------------------------------------------------------------------------

EFFECT_CODES = {"food": 1, "tech": 2, "pay_award": 3, "kill": 4, "vanish": 5, "status": 6, "health": 7,
                "preference": 8, "skill": 9, "sick": 10}
EFFECT_CAPS = {"food": CAP_FOOD, "tech": CAP_TECH, "pay_award": 0, "kill": CAP_KILL, "vanish": CAP_VANISH,
               "status": CAP_STATUS, "health": 0, "preference": CAP_PREFS, "skill": CAP_SKILLS, "sick": CAP_SICK}
VILLAGER_EFFECTS = ("kill", "vanish", "status", "health", "preference", "skill", "sick")
GONE_EFFECTS = ("kill", "vanish")
STATUS_CODES = {"heathen": 1}
CAUSES = ("custom", "unknown")
COND_CODES = {"visited": 1, "role": 2, "game": 3, "patch": 4, "not": 5, "all": 6, "any": 7}
COND_PUZZLE = 8              # version 3, the requirement only: a = the puzzle's name, b = its game
SEX_CODES = {"any": 0, "male": 1, "female": 2, "random": 3}

# ---- Version 6 (docs/event-collection/cie-v6-binary.md is the engine's contract) ---------------------------------

V6_EFFECTS = ("celebrate", "action", "mood", "health_change", "damage")     # the new "do" words
EFFECT_CODES.update({"celebrate": 11, "action": 12, "mood": 13, "health_change": 14, "skill_set": 15, "damage": 16})
EFFECT_CAPS.update({"celebrate": CAP_BEHAVIOUR, "action": CAP_BEHAVIOUR, "mood": CAP_BEHAVIOUR, "health_change": 0,
                    "skill_set": CAP_SKILLS, "damage": 0})
VILLAGER_EFFECTS_V6 = VILLAGER_EFFECTS + ("action", "mood", "health_change")
V6_CONDS = ("harmable", "special_present", "min_population", "min_children")
COND_CODES.update({"harmable": 9, "special_present": 10, "min_population": 11, "min_children": 12})
STATIC_CONDS = ("game", "patch", "role", "special_present", "not", "all", "any")   # a choice's "if"
SPECIAL_CODES = {"golden_child": 1, "tribal_chief": 2, "nursing_parent": 3}
SPECIAL_GAMES = {"golden_child": (1,), "tribal_chief": (3,), "nursing_parent": (1, 2, 3, 4, 5)}
PRESENT_CODES = {"golden_child": 1, "tribal_chief": 2}
PROTECTED_MODES = ("auto", "exclude", "allow")
PICK_CODES = {"random": 0, "highest": 1}
ROLE_FLAG_HARM = 16
ROLE_FLAG_PROTECT = 32
LABEL_BYTES_V6 = 95           # a version 6 label (cg_labels[7][96])
HEADER_BYTES_V6 = 96
MAX_POOLS = 1000
MAX_ITEMS = 8000
MAX_INSTANCE = 8              # {A.1} .. {A.8}
MAX_POOL_DEPTH = 3            # a pool's item may hold pool tokens, three deep at most
MAX_PICKS = 256               # pool instances a run holds (CG_MAX_PICKS)
DAMAGE_ANY = "any"
POOL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_]{0,31}$")    # an author's pool name ("_" and "@" are the compiler's)
COLLECTION_ID_RE = re.compile(r"^[a-z0-9_]{1,64}$")
KEYWORDS = ("name", "name1", "name2", "award", "award_unit")
PRONOUNS_V6 = {"he/she": ("he", "she"), "his/her": ("his", "her"), "him/her": ("him", "her"),
               "man/woman": ("man", "woman"), "himself/herself": ("himself", "herself"),
               "woman/man": ("man", "woman"), "boy/girl": ("boy", "girl"), "son/daughter": ("son", "daughter")}
HINT_PRONOUNS = ("he/she", "him/her", "his/her", "himself/herself")   # a label name's fallback forms (section 15)
HINT_DEFAULT = "him/her"
GLYPH_FALLBACK = {";": ",", "(": "-", ")": "-", "&": "and", "%": " percent"}
FALLBACK_GAMES = (1, 2)       # A New Home and The Lost Children's fonts lack ; ( ) & %
SIZES = {"small": (1, 2), "normal": (1, 1), "large": (2, 1), "huge": (3, 1)}     # multiply, divide (rounding down)
SIZE_TABLE = {"food": {1: (200, 1500), 2: (100, 1500), 3: (200, 600), 4: (300, 300), 5: (50, 300)},
              "tech": {1: (500, 4999), 2: (500, 3000), 3: (1000, 2000), 4: (500, 5000), 5: (500, 3000)}}
AUTHORING_KEYS = ("name", "src", "text_only_reason")    # kept by normalize, never compiled (without_names drops them)
SHARED_POOLS = Path(__file__).resolve().parents[1] / "data" / "event_collection" / "shared_pools.json"
ACTIONS = Path(__file__).resolve().parents[1] / "data" / "cie_actions.json"
_ACTION_TABLE: dict | None = None


def size_range(kind: str, size: str, game: int) -> tuple[int, int]:
    """A size word's amount range in `game` (design A3): the normal range halved, doubled or tripled."""
    lo, hi = SIZE_TABLE[kind][game]
    mul, div = SIZES[size]
    return lo * mul // div, hi * mul // div


def actions(game: int) -> dict[str, dict]:
    """The game's Custom Island Event villager actions by label: {"group", "unsafe"} (data/cie_actions.json)."""
    global _ACTION_TABLE
    if _ACTION_TABLE is None:
        _ACTION_TABLE = json.loads(ACTIONS.read_text(encoding="utf-8"))["games"]
    return {a["label"]: a for a in _ACTION_TABLE[str(game)]}


def glyph_fallback(text: str, game: int, unicode: bool = False) -> str:
    """The text as A New Home and The Lost Children draw it without the Unicode Text companion (section 9)."""
    if unicode or game not in FALLBACK_GAMES:
        return text
    return "".join(GLYPH_FALLBACK.get(c, c) for c in text)
NODE_TYPES = ("popup", "question", "branch")
UNITS = {"food": "food", "tech": "tech points"}

PLACEHOLDER_RE = re.compile(r"\(([^()\n]*)\)")
PRONOUNS = {"he/she": ("he", "she"), "his/her": ("his", "her"), "him/her": ("him", "her"),
            "man/woman": ("man", "woman")}
_NAME_ALIASES = {"name1": "subject", "name2": "friend"}


def answer_letter(b: int) -> str:
    """An answer as the chances table names it: A to G (an eighth, which the checks refuse, by its number)."""
    return "ABCDEFG"[b] if 0 <= b < 7 else str(b + 1)


def answer_room(answers: int, layout: "Layout | None" = None) -> int:
    """The text lines a question's popup (and its answer's first page, shown in it) keeps for its buttons beyond the
    game's two, as story_graph.inc cg_answer_room keeps them (its CG_ANSWER_LINES table; tests/test_cie_graph_v6.py
    pins the two together).  Up to four answers: 1.5 button heights (3 lines of 20 px) each past two.  Five to
    seven (version 6): the buttons stand 1.25 heights apart (vvfp_multi_answer.h ma_step), so the first stands
    (n - 1) x 1.25 - 1.5 heights above the game's own first: ceil(2.5 (n - 1) - 3) lines; and, laid out in
    `layout`, never so many that a page keeps fewer than three text lines below the title the popup leads with
    (A New Home and The Lost Children: the title and four line breaks, 5 lines)."""
    if answers <= MAX_ANSWERS_V4:
        return ANSWER_LINES * max(0, answers - 2)
    room = -(-(5 * (answers - 1) - 6) // 2)
    if layout is None:
        return room
    most = layout.lines - (5 if layout.with_title else 0) - 3
    return max(0, most) if room > most else room


V6_EXTRA_CHARS = ";/&%"       # version 6 text adds these (VV1/VV2 show them through GLYPH_FALLBACK)


def text_char_ok(c: str, version: int = 1) -> bool:
    """story_custom.inc ce_text_char_ok, line breaks allowed; version 2 adds the double quote, which every game's
    font draws (src/vv_font_glyphs.py: A New Home's and The Lost Children's fonts hold ! " ' , . ? / ` : -);
    version 6 adds ; / & % (docs/event-collection/cie-v6-binary.md section 5)."""
    return (c.isascii() and c.isalnum()) or c in " .,!?:-'\n" or (version >= 2 and c == '"') \
        or (version >= VERSION_V6 and c in V6_EXTRA_CHARS)


# ---- Button labels (the owner, 2026-11-13: a label may run off its button, as long as it is readable) ----------
#
# Each game draws a question's two labels in its story font, centred on its button, the two buttons one above the
# other in the middle of the screen (scripts/build_cie_label_widths.py): a label is limited only by the bytes the
# companion keeps (BUTTON_BYTES) and by the screen's width, measured with the game's own font widths.

LABEL_WIDTHS = Path(__file__).resolve().parents[1] / "data" / "cie_label_widths.json"
_LABEL_TABLE: dict | None = None


def _label_table(game: int) -> dict:
    global _LABEL_TABLE
    if _LABEL_TABLE is None:
        _LABEL_TABLE = json.loads(LABEL_WIDTHS.read_text(encoding="utf-8"))["games"]
    return _LABEL_TABLE[str(game)]


def label_px(game: int, text: str) -> int:
    """`text` measured as the game measures it (its story font, ldwBurweed27)."""
    t = _label_table(game)
    if not text:
        return 0
    w = t["widths"]
    total = sum(w[ord(c) - 32] if 32 <= ord(c) < 127 else w[ord("A") - 32] for c in text)
    return total + t["spacing"] * (len(text) - 1)


# ---- Titles in The Secret City, The Tree of Life and New Believers (version 6) ---------------------------------
#
# Their island-event dialog draws the title as a string of its own, on ONE line, centred: the body draw (VV3
# 0x418510, VV4 0x416EC0, VV5 0x417660) calls the centred text draw (0x40A070 / 0x409BE0 / 0x409EB0) with the title
# [dialog+0x54], at x = [+0x848] (half the panel) and y = [+0x84C], in the dialog's font [+0x82C] -- the font the
# constructor (0x4192F0 / 0x417790 / 0x418020) copies from the text manager, the one its body text uses
# (tests/scrolling_popups_emulation.py: ldwarialbold).  Nothing wraps or cuts it.  A version 6 title is therefore
# checked by its pixels in that font (data/font_glyph_tables.json), against the width the body text gets (the panel
# less 0x28 at each side: 0x1B0 in VV3 / VV4, 0x270 in VV5), so it stands inside the panel with the text's margins;
# tests/test_cie_graph_v6.py pins the measure against the emulated stock dialog.  Versions 1-5 keep their
# 30-character rule; A New Home and The Lost Children wrap the title into the text (title_width).

FONT_TABLES = Path(__file__).resolve().parents[1] / "data" / "font_glyph_tables.json"
TITLE_FONT = "ldwarialbold"
TITLE_BOX_PX = {3: 0x200 - 0x50, 4: 0x200 - 0x50, 5: 0x2C0 - 0x50}
_TITLE_TABLE: dict = {}


def title_px(game: int, text: str) -> int:
    """`text` as the later games' dialog draws its title: each glyph's box (a character the font lacks as "A") plus
    the font's spacing between them."""
    if game not in _TITLE_TABLE:
        font = json.loads(FONT_TABLES.read_text(encoding="utf-8"))["games"][f"vv{game}"]["fonts"][TITLE_FONT]
        _TITLE_TABLE[game] = ({e[0]: e[3] - e[1] for e in font["entries"]}, font["spacing"])
    widths, spacing = _TITLE_TABLE[game]
    if not text:
        return 0
    return sum(widths.get(ord(c), widths[ord("A")]) for c in text) + spacing * (len(text) - 1)


def label_max_px(game: int) -> int:
    """The widest label the game's screen shows whole, centred."""
    return _label_table(game)["max_px"]


VILLAGER_NAMES = Path(__file__).resolve().parents[1] / "data" / "cie_villager_names.json"


@lru_cache(maxsize=None)
def villager_names(game: int) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The game's own first-name lists, male then female (scripts/build_cie_villager_names.py): a named stranger's
    name is drawn from them (cie-v6-binary.md 16)."""
    d = json.loads(VILLAGER_NAMES.read_text(encoding="utf-8"))["games"][str(game)]
    return tuple(d["male"]), tuple(d["female"])


def stranger_name_room(game: int) -> int:
    """The longest name in the game's lists: a named stranger's worst case."""
    return max(len(n) for names in villager_names(game) for n in names)


def label_fits(game: int, text: str) -> bool:
    """A version 6 label as shown fits: at most LABEL_BYTES_V6 bytes and the screen's width (section 15)."""
    return len(text) <= LABEL_BYTES_V6 and label_px(game, text) <= label_max_px(game)


def label_shown(label: str, g: dict, bindings: dict, game: int, aliases: dict | None = None,
                tribe: str | None = None, unicode: bool = False, picks: dict | None = None) -> str:
    """A version 6 button label as the player reads it (`g` lowered): the real names, or -- when that does not fit
    the screen (label_fits) -- every name as its role's pronoun (cie-v6-binary.md 15)."""
    real = expand_v6(label, g, bindings, picks, None, game, unicode, aliases, tribe=tribe)
    if label_fits(game, real):
        return real
    return expand_v6(label, g, bindings, picks, None, game, unicode, aliases, tribe=tribe, pronoun_names=True)


class GraphError(ValueError):
    """A graph that does not pass; .problems lists every reason."""

    def __init__(self, problems: list[str]):
        super().__init__("\n".join(problems))
        self.problems = problems


# ---- Loading: shape checks and the normalized form ----------------------------------------------------------------


def _norm_cond(c: Any, where: str, problems: list[str], version: int = 1) -> Any:
    if c is None:
        return None
    if not isinstance(c, dict) or len(c) != 1:
        problems.append(f"{where}: a condition is one of visited / role / game / patch / not / all / any"
                        + (" / harmable / special_present / min_population / min_children"
                           if version >= VERSION_V6 else ""))
        return None
    (op, arg), = c.items()
    if op in V6_CONDS:
        if version < VERSION_V6:
            problems.append(f"{where}: the condition {op} needs format version {VERSION_V6}")
            return None
        if op == "harmable" and not isinstance(arg, str):
            problems.append(f"{where}: harmable names one role")
            return None
        if op == "special_present" and arg not in PRESENT_CODES:
            problems.append(f"{where}: special_present is golden_child or tribal_chief")
            return None
        if op in ("min_population", "min_children") and not _int_in(arg, 1, 255):
            problems.append(f"{where}: {op} is 1..255")
            return None
        return {op: arg}
    if op in ("visited", "role", "patch"):
        if not isinstance(arg, str):
            problems.append(f"{where}: {op} names one id")
            return None
        return {op: arg}
    if op == "game":
        games = arg if isinstance(arg, list) else [arg]
        if not games or any(not isinstance(g, int) or g not in GAMES for g in games):
            problems.append(f"{where}: game is 1..5 or a list of them")
            return None
        return {"game": sorted(set(games))}
    if op == "not":
        inner = _norm_cond(arg, where, problems, version)
        return None if inner is None else {"not": inner}
    if op in ("all", "any"):
        if not isinstance(arg, list) or not arg or len(arg) > 255:
            problems.append(f"{where}: {op} takes 1..255 conditions")
            return None
        parts = [_norm_cond(x, where, problems, version) for x in arg]
        return None if any(p is None for p in parts) else {op: parts}
    problems.append(f"{where}: unknown condition {op!r}")
    return None


def _int_in(v: Any, lo: int, hi: int) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi


def effect_amount(e: dict, game: int):
    """A food / tech effect's amount in `game`: an int, or (min, max) for a range -- its own for the game when it
    lists one (version 5 per_game), else the effect's."""
    per = (e.get("per_game") or {}).get(str(game))
    if per is not None:
        return per[0] if per[0] == per[1] else (per[0], per[1])
    return (e["amount"], e["max"]) if e.get("max") is not None else e["amount"]


def per_game_text(per: dict) -> str:
    """The .cieg's string for a per_game: "<game>:<min>-<max>;..." (the companion's story_graph.inc cg_per_game)."""
    return ";".join(f"{k}:{v[0]}-{v[1]}" for k, v in sorted(per.items()))


def per_game_parse(text: str) -> dict:
    out = {}
    for part in text.split(";"):
        k, _, r = part.partition(":")
        lo, _, hi = r[1:].partition("-") if r.startswith("-") else r.partition("-")
        lo = -int(lo) if r.startswith("-") else int(lo)
        out[k] = [lo, int(hi)]
    return out


_EFFECTS_V1_5 = ("food", "tech", "pay_award", "kill", "vanish", "status", "health", "preference", "skill", "sick")


def _norm_effect(e: Any, where: str, problems: list[str], version: int = 1, games: list[int] | None = None,
                 default_role: str = "subject") -> dict | None:
    v6 = version >= VERSION_V6
    dos = _EFFECTS_V1_5 + (V6_EFFECTS if v6 else ())
    if not isinstance(e, dict) or e.get("do") not in dos:
        if isinstance(e, dict) and e.get("do") in V6_EFFECTS:
            problems.append(f"{where}: {e['do']} needs format version {VERSION_V6}")
        else:
            problems.append(f"{where}: an effect is {{\"do\": one of {', '.join(dos)}}}")
        return None
    do = e["do"]
    known = {"do"} | ({"src"} if v6 else set())
    out: dict[str, Any] = {"do": do}
    if v6 and do in ("food", "tech") and "size" in e:
        # Version 6: a size word (design A3), expanded here into each game's own range (a version 5 per_game).
        known |= {"size", "loss", "scaled", "defer"}
        size, loss = e.get("size"), e.get("loss", False)
        if size not in SIZES or not isinstance(loss, bool):
            problems.append(f"{where}: size is one of {', '.join(SIZES)}; loss is true or false")
            size, loss = "normal", False
        for k in ("amount", "max", "per_game"):
            if k in e:
                problems.append(f"{where}: give a size or an amount, not both")
                break
        per: dict[str, list[int]] = {}
        for gn in games or []:
            lo, hi = size_range(do, size, gn)
            per[str(gn)] = [-hi, -lo] if loss else [lo, hi]
        first = per[str(games[0])] if games else [1, 1]
        out.update(amount=first[0], scaled=bool(e.get("scaled", False)), defer=bool(e.get("defer", False)))
        if first[0] != first[1]:
            out["max"] = first[1]
        out["per_game"] = per
        if out["defer"] and loss:
            problems.append(f"{where}: an award (defer) is a gain")
        if "src" in e:
            out["src"] = e["src"]
        extra = set(e) - known
        if extra:
            problems.append(f"{where}: {do} does not take {', '.join(sorted(extra))}")
        return out
    if do in ("food", "tech"):
        known |= {"amount", "max", "scaled", "defer", "per_game"}
        amount = e.get("amount")
        if not _int_in(amount, -MAX_AMOUNT, MAX_AMOUNT) or amount == 0:
            problems.append(f"{where}: {do} amount is a whole number, not 0, at most {MAX_AMOUNT} either way")
        out.update(amount=amount, scaled=bool(e.get("scaled", False)), defer=bool(e.get("defer", False)))
        if "max" in e:
            # Version 3: a range -- amount .. max, each equally likely, rolled with its page's walk (the
            # "Island Events Scale" patches then scale the roll, as they scale a fixed amount).
            hi = e["max"]
            if version < 3:
                problems.append(f"{where}: an amount range needs format version 3")
            elif not _int_in(hi, -MAX_AMOUNT, MAX_AMOUNT) or not isinstance(amount, int) or hi <= amount \
                    or (hi > 0) != (amount > 0):
                problems.append(f"{where}: {do} range: its top is above its amount, on the same side of 0")
            out["max"] = hi
        if "per_game" in e:
            per = e["per_game"]
            if version < VERSION_PER_GAME:
                problems.append(f"{where}: amounts per game need format version {VERSION_PER_GAME}")
            if not isinstance(per, dict) or not per:
                problems.append(f"{where}: per_game is {{\"<game>\": [min, max], ...}}")
                per = {}
            norm: dict[str, list[int]] = {}
            for key in sorted(per, key=str):
                pair = per[key]
                if str(key) not in {str(n) for n in range(1, 6)} or not isinstance(pair, (list, tuple)) \
                        or len(pair) != 2 or not all(_int_in(v, -MAX_AMOUNT, MAX_AMOUNT) for v in pair) \
                        or pair[0] == 0 or pair[1] < pair[0] or (pair[0] > 0) != (pair[1] > 0):
                    problems.append(f"{where}: {do} amount for game {key}: [min, max], not 0, min at most max, "
                                    "on one side of 0")
                    continue
                norm[str(key)] = [pair[0], pair[1]]
            out["per_game"] = norm
            if out["defer"] and any(lo < 0 for lo, _hi in norm.values()):
                problems.append(f"{where}: an award (defer) is a gain")
        if out["defer"] and isinstance(amount, int) and amount < 0:
            problems.append(f"{where}: an award (defer) is a gain")
    elif do == "pay_award":
        pass
    elif do == "celebrate":
        known.add("who")
        who = e.get("who", "all")
        if not isinstance(who, str):
            problems.append(f"{where}: celebrate's who is all or a role")
            who = "all"
        out["who"] = who
    elif do == "damage":
        known |= {"structures", "min", "max", "size"}
        if "size" in e:
            # G9: a size word, expanded to its percent range.
            if e["size"] not in DAMAGE_SIZES or "min" in e or "max" in e:
                problems.append(f"{where}: damage size is one of {', '.join(DAMAGE_SIZES)} (and no min or max)")
            e = dict(e, min=DAMAGE_SIZES.get(e["size"], (10, 30))[0], max=DAMAGE_SIZES.get(e["size"], (10, 30))[1])
        st = e.get("structures", DAMAGE_ANY)
        if st != DAMAGE_ANY and (not isinstance(st, list) or not st or any(
                not isinstance(x, str) or not x or not x.isascii() or "," in x for x in st)
                or len(set(st)) != len(st)):
            problems.append(f"{where}: damage structures is \"any\" or a list of the game's structure names")
            st = DAMAGE_ANY
        lo, hi = e.get("min"), e.get("max")
        if not (_int_in(lo, 1, 100) and _int_in(hi, 1, 100) and lo <= hi):
            problems.append(f"{where}: damage is 1..100 percent, min <= max")
        out.update(structures=st if st == DAMAGE_ANY else list(st), min=lo, max=hi)
    else:
        known.add("role")
        out["role"] = e.get("role", default_role)
        if do == "action":
            known.add("action")
            act = e.get("action")
            if not isinstance(act, str) or not act or not act.isascii():
                problems.append(f"{where}: action names the game's own action words")
            out["action"] = act
        elif do == "mood":
            known.add("mood")
            if e.get("mood") not in ("good", "bad"):
                problems.append(f"{where}: mood is good or bad")
            out["mood"] = e.get("mood")
        elif do == "health_change":
            known |= {"min", "max"}
            lo, hi = e.get("min"), e.get("max")
            if not (_int_in(lo, -99, 99) and _int_in(hi, -99, 99) and lo <= hi) or lo == hi == 0:
                problems.append(f"{where}: health_change is -99..99, min <= max, not 0")
            out.update(min=lo, max=hi)
        elif do == "skill" and v6 and "set" in e:
            known |= {"skills", "set"}
            skills = e.get("skills")
            if not isinstance(skills, list) or not skills or not all(isinstance(s, str) for s in skills) \
                    or len(set(skills)) != len(skills):
                problems.append(f"{where}: skill lists one or more different skills")
                skills = []
            if not _int_in(e.get("set"), 0, SKILL_ADD_MAX):
                problems.append(f"{where}: skill set is 0..{SKILL_ADD_MAX}")
            if "min" in e or "max" in e:
                problems.append(f"{where}: a skill set takes no min or max")
            out.update(skills=list(skills), set=e.get("set"))
        if do == "kill":
            known.add("cause")
            cause = e.get("cause", "custom")
            if not isinstance(cause, str) or not cause or len(cause) > CAUSE_BYTES or not all(
                    text_char_ok(ch) and ch != "\n" for ch in cause):
                problems.append(f"{where}: kill cause is custom, unknown or up to {CAUSE_BYTES} allowed characters")
            out["cause"] = cause
        elif do == "status":
            known.add("status")
            if e.get("status") not in STATUS_CODES:
                problems.append(f"{where}: status is one of {', '.join(STATUS_CODES)}")
            out["status"] = e.get("status")
        elif do == "health":
            known |= {"min", "max", "value"}
            lo, hi = (e.get("value"), e.get("value")) if "value" in e else (e.get("min"), e.get("max"))
            if not (_int_in(lo, 1, HEALTH_MAX) and _int_in(hi, 1, HEALTH_MAX) and lo <= hi):
                problems.append(f"{where}: health is 1..{HEALTH_MAX} (0 is kill), min <= max")
            out.update(min=lo, max=hi)
        elif do == "preference":
            known |= {"list", "preference"}
            if e.get("list") not in ("likes", "dislikes"):
                problems.append(f"{where}: preference list is likes or dislikes")
            if not isinstance(e.get("preference"), str):
                problems.append(f"{where}: preference names the game's own word")
            out.update(list=e.get("list"), preference=e.get("preference"))
        elif do == "skill" and "set" not in out:
            known |= {"skills", "min", "max"}
            if v6 and "size" in e:
                # A size word: small 5-10, normal 10-20, large 20-40, huge 30-60 ("loss": the same, taken away).
                known |= {"size", "loss"}
                lo, hi = SKILL_SIZES.get(e["size"], (5, 10))
                if e["size"] not in SKILL_SIZES or "min" in e or "max" in e or not isinstance(e.get("loss", False), bool):
                    problems.append(f"{where}: skill size is one of {', '.join(SKILL_SIZES)} (and no min or max)")
                e = dict(e, min=-hi if e.get("loss") else lo, max=-lo if e.get("loss") else hi)
            skills = e.get("skills")
            if not isinstance(skills, list) or not skills or not all(isinstance(s, str) for s in skills) \
                    or len(set(skills)) != len(skills):
                problems.append(f"{where}: skill lists one or more different skills")
                skills = []
            lo, hi = e.get("min"), e.get("max")
            ok = _int_in(lo, 1, SKILL_ADD_MAX) and _int_in(hi, 1, SKILL_ADD_MAX) and lo <= hi
            if v6 and not ok:
                # Version 6: a loss too (both below 0), which makes the role harm-capable.
                ok = _int_in(lo, -SKILL_ADD_MAX, -1) and _int_in(hi, -SKILL_ADD_MAX, -1) and lo <= hi
            if not ok:
                problems.append(f"{where}: skill adds 1..{SKILL_ADD_MAX}"
                                + (f" (or takes -{SKILL_ADD_MAX}..-1)" if v6 else "") + ", min <= max")
            out.update(skills=list(skills), min=lo, max=hi)
    if v6 and "src" in e:
        out["src"] = e["src"]
    extra = set(e) - known
    if extra:
        problems.append(f"{where}: {do} does not take {', '.join(sorted(extra))}")
    return out


def normalize(data: Any, shared_pools: Any = None) -> tuple[dict, list[str]]:
    """The graph with every default filled in, and the shape problems found.  Version 6 sugar is expanded here: a
    size word into per_game, a game word's "*" into each game, include_pools into pools (from `shared_pools`, a
    dict or a path, default SHARED_POOLS), and every inline pick into its canonical form."""
    problems: list[str] = []
    if not isinstance(data, dict):
        return {}, ["the file is not a JSON object"]
    if data.get("format") != FORMAT:
        problems.append(f"format is not {FORMAT!r}")
    version = data.get("version")
    if version not in VERSIONS:
        problems.append(f"version {version!r} is not one this patcher reads ({', '.join(map(str, VERSIONS))})")
        version = VERSION
    v6 = version >= VERSION_V6
    if not v6:
        for key in ("words", "pools", "include_pools", "collection", "grammar_fixes"):
            if key in data:
                problems.append(f"{key} needs format version {VERSION_V6}")
    g: dict[str, Any] = {"format": FORMAT, "version": version}
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        problems.append("title is missing")
        title = ""
    g["title"] = title
    games = data.get("games", sorted(GAMES))
    if not isinstance(games, list) or not games or any(not isinstance(x, int) or x not in GAMES for x in games):
        problems.append("games is a list of 1..5")
        games = []
    g["games"] = sorted(set(games))
    patches = data.get("patches", [])
    if not isinstance(patches, list) or any(not isinstance(p, str) or not PATCH_RE.match(p) for p in patches):
        problems.append("patches is a list of patch ids (a-z, 0-9, _)")
        patches = []
    if len(patches) > 8:
        problems.append("at most 8 patches may be named")
    g["patches"] = list(dict.fromkeys(patches))
    req = data.get("requirement", {})
    min_el = req.get("min_eligible", 0) if isinstance(req, dict) else None
    version = g["version"]
    if not _int_in(min_el, 0, 255):
        problems.append("requirement.min_eligible is 0..255")
        min_el = 0
    g["requirement"] = {"min_eligible": min_el}
    puzzles = req.get("puzzles") if isinstance(req, dict) else None
    if puzzles is not None:
        # Version 3: "only after a puzzle is solved", per game: {"1": ["The Cave"], ...}.  Custom Island Events
        # keep this part of the requirement: the purchase is refused until every listed puzzle of the game being
        # played is solved.
        fixed: dict[str, list[str]] = {}
        if version < 3:
            problems.append("needing a puzzle solved needs format version 3")
        elif not isinstance(puzzles, dict):
            problems.append("the puzzles needed are listed per game")
        else:
            for key, names in puzzles.items():
                gn = int(key) if isinstance(key, (int, str)) and str(key).isdigit() else None
                if gn not in GAMES or gn not in g["games"]:
                    problems.append(f"puzzles needed: {key!r} is not one of the event's games")
                    continue
                if not isinstance(names, list) or not names or any(n not in PUZZLES[gn] for n in names):
                    problems.append(f"puzzles needed: {GAMES[gn].name}'s puzzles are "
                                    + ", ".join(PUZZLES[gn]))
                    continue
                fixed[str(gn)] = list(dict.fromkeys(names))
        if fixed:
            g["requirement"]["puzzles"] = {k: fixed[k] for k in sorted(fixed)}
    if isinstance(req, dict):
        extra = set(req) - {"min_eligible", "puzzles"} - ({"if"} if v6 else set())
        if extra and v6:
            problems.append(f"requirement: unknown fields {', '.join(sorted(extra))}")
        if v6 and req.get("if") is not None:
            # Version 6: the natural roll's and Pick Island Event's condition (Custom Island Events ignore it).
            c = _norm_cond(req["if"], "requirement", problems, version)
            if c is not None:
                if _cond_ops(c) & {"visited", "harmable"}:
                    problems.append("requirement: its condition cannot use visited or harmable")
                g["requirement"]["if"] = c

    roles_in = data.get("roles")
    roles: dict[str, dict] = {}
    if not isinstance(roles_in, dict) or (not roles_in and not (v6 and roles_in == {})):   # v6: no roles at all
        problems.append("roles is missing")
        roles_in = {}
    kinds = ("villager", "stranger", "alias", "other") if v6 else ("villager", "stranger")
    for rid, r in roles_in.items():
        where = f"role {rid}"
        if not ID_RE.match(rid):
            problems.append(f"{where}: an id is 1..32 letters, digits or _")
        if not isinstance(r, dict) or r.get("kind") not in kinds:
            problems.append(f"{where}: kind is villager, stranger, alias or other" if v6
                            else f"{where}: kind is villager or stranger")
            continue
        if v6 and rid.lower() in KEYWORDS:
            problems.append(f"{where}: a role id cannot be {rid.lower()} (a placeholder word)")
        if r["kind"] == "other":
            # G2: the member of a two-member alias that the alias did not draw.
            extra = set(r) - {"kind", "of"}
            if not isinstance(r.get("of"), str):
                problems.append(f"{where}: an other role is \"of\": the alias role it follows")
            roles[rid] = {"kind": "other", "of": r.get("of") if isinstance(r.get("of"), str) else ""}
        elif r["kind"] == "alias":
            # Version 6: one of the listed villager roles, drawn at the start of the run.
            extra = set(r) - {"kind", "of"}
            of = r.get("of")
            if not isinstance(of, list) or not of or len(of) > 16 or any(not isinstance(x, str) for x in of) \
                    or len(set(of)) != len(of):
                problems.append(f"{where}: an alias is \"of\": a list of other villager roles")
                of = []
            roles[rid] = {"kind": "alias", "of": list(of)}
        elif r["kind"] == "stranger":
            extra = set(r) - {"kind", "sex"} - ({"named"} if v6 else set())
            sex = r.get("sex", "random")
            if sex not in ("random", "male", "female"):
                problems.append(f"{where}: a stranger's sex is random, male or female")
            roles[rid] = {"kind": "stranger", "sex": sex}
            if v6 and r.get("named") is not None:
                # Section 16: a first name from the game's own lists, drawn at bind time.
                if not isinstance(r["named"], bool):
                    problems.append(f"{where}: named is true or false")
                elif r["named"]:
                    roles[rid]["named"] = True
        else:
            extra = set(r) - {"kind", "optional", "sex", "min_age", "exclude_nursing", "exclude_special",
                              "believers_only", "max_age_gap"}
            sex = r.get("sex", "any")
            if sex not in ("any", "male", "female"):
                problems.append(f"{where}: a villager's sex is any, male or female")
            min_age = r.get("min_age", 14)
            if not _int_in(min_age, 0, 80):
                problems.append(f"{where}: min_age is 0..80 years")
            if v6:
                extra -= {"max_age", "skill", "special", "protected"}
                roles[rid] = _norm_role_v6(r, where, problems, sex, min_age)
            else:
                roles[rid] = {"kind": "villager", "optional": bool(r.get("optional", False)), "sex": sex,
                              "min_age": min_age, "exclude_nursing": bool(r.get("exclude_nursing", True)),
                              "exclude_special": bool(r.get("exclude_special", True)),
                              "believers_only": bool(r.get("believers_only", True))}
            gap = r.get("max_age_gap")
            if gap is not None:
                # Version 3: at most `years` apart from another villager role (both bound: the purchase is refused
                # when no pair fits, as when no villager fits a role).
                if version < 3:
                    problems.append(f"{where}: an age gap needs format version 3")
                elif not isinstance(gap, dict) or set(gap) != {"role", "years"} or not isinstance(gap["role"], str) \
                        or not _int_in(gap["years"], 0, MAX_AGE_GAP):
                    problems.append(f"{where}: an age gap is 0..{MAX_AGE_GAP} years from another role")
                else:
                    roles[rid]["max_age_gap"] = {"role": gap["role"], "years": gap["years"]}
        if extra:
            problems.append(f"{where}: unknown fields {', '.join(sorted(extra))}")
    if v6:
        # Version 6: any id; the first role is a villager the event needs or a stranger (G7; an unprefixed
        # placeholder names "subject" when there is one, else the first role, as the companion's cg_parse_ph does).
        first = next(iter(roles.values()), None)
        if first is not None and first["kind"] != "stranger" and (first["kind"] != "villager" or first["optional"]):
            problems.append("the first role is a villager the event needs (not optional) or a stranger")
        lower = [r.lower() for r in roles]
        if len(set(lower)) != len(lower):
            problems.append("two role ids differ only in capitals")
        for rid, r in roles.items():
            if r["kind"] == "alias":
                for m in r["of"]:
                    if m == rid or roles.get(m, {}).get("kind") != "villager":
                        problems.append(f"role {rid}: an alias's members are other villager roles ({m!r} is not)")
                # Members in role order: the .cieg keeps them as a mask, and the draw takes them in that order.
                r["of"] = [m for m in roles if m in r["of"]] + [m for m in r["of"] if m not in roles]
            elif r["kind"] == "other":
                alias = roles.get(r["of"])
                if alias is None or alias["kind"] != "alias" or len(alias["of"]) != 2:
                    problems.append(f"role {rid}: an other role follows an alias of exactly two villager roles")
            elif r["kind"] == "villager" and r.get("special") and \
                    any(gn not in SPECIAL_GAMES[r["special"]] for gn in g["games"]):
                problems.append(f"role {rid}: {r['special']} is only in "
                                + ", ".join(GAMES[x].name for x in SPECIAL_GAMES[r["special"]]))
    else:
        if roles and next(iter(roles)) != "subject":
            problems.append("the first role is subject")
    if "subject" in roles and (roles["subject"]["kind"] != "villager" or roles["subject"].get("optional")) \
            and not (v6 and roles["subject"]["kind"] == "stranger"):
        problems.append("subject is a villager the event needs (not optional)")
    if len(roles) > 16:
        problems.append("at most 16 roles")
    for rid, r in roles.items():
        gap = r.get("max_age_gap")
        if gap is None:
            continue
        other = roles.get(gap["role"])
        if gap["role"] == rid or other is None or other["kind"] != "villager":
            problems.append(f"role {rid}: the age gap names another villager role")
        elif other.get("max_age_gap", {}).get("role") == rid:
            problems.append(f"role {rid}: give the age gap on one of the two roles only")
    g["roles"] = roles

    start = data.get("start")
    g["start"] = start if isinstance(start, str) else ""
    nodes_in = data.get("nodes")
    if not isinstance(nodes_in, dict) or not nodes_in:
        problems.append("nodes is missing")
        nodes_in = {}
    if len(nodes_in) > MAX_NODES:
        problems.append(f"at most {MAX_NODES} nodes")
    nodes: dict[str, dict] = {}
    node_keys = {"type", "popup", "join", "text", "variants", "effects", "children", "choices", "else", "summary",
                 "outcome", "name"} | ({"src", "text_only_reason", "title"} if v6 else set())
    pool_names = pool_names_of(data) if v6 else set()
    canon = (lambda s: _canon_text(s, pool_names)) if v6 else (lambda s: s)
    default_role = default_role_of(roles) if v6 else "subject"
    for nid, n in nodes_in.items():
        where = f"node {nid}"
        if not ID_RE.match(nid):
            problems.append(f"{where}: an id is 1..32 letters, digits or _")
        if not isinstance(n, dict):
            problems.append(f"{where}: not an object")
            continue
        extra = set(n) - node_keys
        if extra:
            problems.append(f"{where}: unknown fields {', '.join(sorted(extra))}")
        t = n.get("type", "popup")
        if t not in NODE_TYPES:
            problems.append(f"{where}: type is popup, question or branch")
            t = "popup"
        popup = n.get("popup", "new")
        join = n.get("join", "space")
        if popup not in ("new", "append") or join not in ("space", "paragraph"):
            problems.append(f"{where}: popup is new or append; join is space or paragraph")
        text = n.get("text", "")
        if not isinstance(text, str):
            problems.append(f"{where}: text is a string")
            text = ""
        text = canon(text)
        variants = []
        vkeys = {"if", "text"} | ({"src"} if v6 else set())
        for i, v in enumerate(n.get("variants", []) or []):
            if not isinstance(v, dict) or not isinstance(v.get("text"), str) or "if" not in v or set(v) - vkeys:
                problems.append(f"{where}: variant {i + 1} is {{\"if\": condition, \"text\": \"...\"}}")
                continue
            variants.append({"if": _norm_cond(v["if"], f"{where} variant {i + 1}", problems, version),
                             "text": canon(v["text"])})
            if v6 and "src" in v:
                variants[-1]["src"] = v["src"]
        effects = [x for x in (_norm_effect(e, f"{where} effect {i + 1}", problems, version, g["games"], default_role)
                               for i, e in enumerate(n.get("effects", []) or [])) if x is not None]
        children = []
        for i, c in enumerate(n.get("children", []) or []):
            cw = f"{where} child {i + 1}"
            if not isinstance(c, dict) or not isinstance(c.get("next"), str) or set(c) - {"next", "weight", "if", "else"}:
                problems.append(f"{cw}: a child is {{\"next\": id, \"weight\": n, \"if\": condition, \"else\": id}}")
                continue
            w = c.get("weight", 1)
            if not _int_in(w, 1, MAX_WEIGHT):
                problems.append(f"{cw}: weight is a whole number 1..{MAX_WEIGHT}")
            els = c.get("else")
            if els is not None and not isinstance(els, str):
                problems.append(f"{cw}: else names a node")
                els = None
            if els is not None and "if" not in c:
                problems.append(f"{cw}: an else needs an if")
            children.append({"next": c["next"], "weight": w, "if": _norm_cond(c.get("if"), cw, problems, version),
                             "else": els})
        choices = []
        ckeys = {"label", "next"} | ({"if", "src"} if v6 else set())
        for i, c in enumerate(n.get("choices", []) or []):
            if not isinstance(c, dict) or not isinstance(c.get("label"), str) or not isinstance(c.get("next"), str) \
                    or set(c) - ckeys:
                problems.append(f"{where} choice {i + 1}: a choice is {{\"label\": \"...\", \"next\": id}}"
                                + (" (and \"if\")" if v6 else ""))
                continue
            choices.append({"label": canon(c["label"]), "next": c["next"]})
            if v6:
                # Version 6: a choice shown only when its (static) condition holds.
                cif = _norm_cond(c.get("if"), f"{where} choice {i + 1}", problems, version)
                if cif is not None and _cond_ops(cif) - set(STATIC_CONDS):
                    problems.append(f"{where} choice {i + 1}: a choice's if uses only game, patch, role and "
                                    "special_present (with not, all, any)")
                choices[-1]["if"] = cif
                if "src" in c:
                    choices[-1]["src"] = c["src"]
        els = n.get("else")
        if els is not None and not isinstance(els, str):
            problems.append(f"{where}: else names a node")
            els = None
        name = n.get("name", "")
        if name != "" and name_problem(name):
            problems.append(f"{where}: its name {name_problem(name)}")
            name = ""
        summary, outcome = n.get("summary", ""), n.get("outcome", "")
        if not isinstance(summary, str) or not isinstance(outcome, str) or not (summary + outcome).isascii():
            problems.append(f"{where}: summary and outcome are plain ASCII words")
            summary, outcome = "", ""
        if t == "question":
            top = MAX_ANSWERS if v6 else MAX_ANSWERS_V4
            if version >= VERSION_ANSWERS and not MIN_ANSWERS <= len(choices) <= top:
                problems.append(f"{where}: a question has {MIN_ANSWERS} to {top} answers"
                                + ("" if v6 or len(choices) < MIN_ANSWERS or len(choices) > MAX_ANSWERS
                                   else f" (five to seven need format version {VERSION_V6})"))
            elif version < VERSION_ANSWERS and len(choices) != 2:
                problems.append(f"{where}: a question has exactly two choices" + (
                    " (three or four answers need format version 4)" if 2 < len(choices) <= MAX_ANSWERS_V4 else ""))
            if children or els is not None or popup != "new":
                problems.append(f"{where}: a question has choices only (no children, else or append)")
            if version >= 2 and n.get("effects"):
                problems.append(f"{where}: a question makes no changes (put them on the page before it, or on an "
                                "answer's page)")
        elif choices:
            problems.append(f"{where}: only a question has choices")
        if t == "branch" and (text or variants):
            problems.append(f"{where}: a branch has no text")
        if t in ("popup", "question") and not text.strip():
            problems.append(f"{where}: a {t} needs text")
        nodes[nid] = {"type": t, "popup": popup if t == "popup" else "new", "join": join, "text": text,
                      "variants": variants, "effects": effects, "children": children, "choices": choices,
                      "else": els, "summary": summary, "outcome": outcome}
        if name:
            nodes[nid]["name"] = name   # only when given: a graph without names normalizes as before
        if v6:
            for k in ("src", "text_only_reason"):
                if k in n:
                    if not isinstance(n[k], str):
                        problems.append(f"{where}: {k} is a string")
                    nodes[nid][k] = n[k]
            ntitle = n.get("title")
            if ntitle is not None:
                # Per-node popup title (cie-v6-binary.md 14): in force from this node's page on.
                if not isinstance(ntitle, str) or not ntitle.strip():
                    problems.append(f"{where}: its popup title is a string (leave it out for none)")
                elif t == "branch":
                    problems.append(f"{where}: a branch shows no text, so it has no popup title")
                else:
                    nodes[nid]["title"] = ntitle
    g["nodes"] = nodes
    if v6:
        _normalize_v6_extras(data, g, problems, shared_pools)
    return g, problems


# ---- Version 6: roles, words, pools, the collection block, inline picks -------------------------------------------


def default_role_of(roles: dict) -> str:
    """The role an unprefixed placeholder or effect names: "subject" when there is one, else the first role."""
    return "subject" if "subject" in roles else next(iter(roles), "subject")


def _cond_ops(c: Any) -> set[str]:
    if c is None:
        return set()
    (op, arg), = c.items()
    if op == "not":
        return {op} | _cond_ops(arg)
    if op in ("all", "any"):
        out = {op}
        for x in arg:
            out |= _cond_ops(x)
        return out
    return {op}


def _norm_role_v6(r: dict, where: str, problems: list[str], sex: str, min_age: Any) -> dict:
    """A version 6 villager role: requirements (sex, ages, skill, special) and safety (protected, believers_only).
    exclude_nursing / exclude_special normalise into protected (either false: "allow")."""
    protected = r.get("protected")
    if protected is None:
        protected = "allow" if r.get("exclude_nursing", True) is False or r.get("exclude_special", True) is False \
            else "auto"
    elif "exclude_nursing" in r or "exclude_special" in r:
        problems.append(f"{where}: give protected, not exclude_nursing or exclude_special")
    if protected not in PROTECTED_MODES:
        problems.append(f"{where}: protected is auto, exclude or allow")
        protected = "auto"
    max_age = r.get("max_age")
    if max_age is not None and (not _int_in(max_age, 1, 80) or (_int_in(min_age, 0, 80) and max_age < min_age)):
        problems.append(f"{where}: max_age is 1..80 years, at least min_age")
    skill = r.get("skill")
    if skill is not None:
        names = skill.get("names") if isinstance(skill, dict) else None
        smin = skill.get("min", 1) if isinstance(skill, dict) else None
        pick = skill.get("pick", "random") if isinstance(skill, dict) else None
        known_skills = {s for gm in GAMES.values() for s in gm.skills}
        if not isinstance(skill, dict) or set(skill) - {"names", "min", "pick"} or not isinstance(names, list) \
                or not names or any(n not in known_skills for n in names) or len(set(names)) != len(names) \
                or not _int_in(smin, 0, 100) or pick not in PICK_CODES:
            problems.append(f"{where}: skill is {{\"names\": [skills], \"min\": 0..100, \"pick\": random or "
                            f"highest}} (skills: {', '.join(sorted(known_skills))})")
            skill = None
        else:
            skill = {"names": list(names), "min": smin, "pick": pick}
    special = r.get("special")
    if special is not None and special not in SPECIAL_CODES:
        problems.append(f"{where}: special is golden_child, tribal_chief or nursing_parent")
        special = None
    return {"kind": "villager", "optional": bool(r.get("optional", False)), "sex": sex, "min_age": min_age,
            "max_age": max_age, "skill": skill, "special": special, "protected": protected,
            "believers_only": bool(r.get("believers_only", True))}


_INLINE_WEIGHT = re.compile(r"^(\d+):(.*)$", re.S)
_TOKEN_V6 = re.compile(r"\\.|\([^()\n]*\)|\{(?:[^{}\n]|\{@[A-Za-z0-9_]+\})*\}")   # a game word may sit in a pick
TRIBE_WORDS = ("tribe", "Tribe")          # G5: built-in game words, filled at run time with the save's tribe name
TRIBE_ROOM = {1: 31, 2: 31, 3: 19, 4: 19, 5: 19}   # the longest tribe name each game makes (src/vv_tribe_rename.py)
NO_TRIBE = {"tribe": "the village", "Tribe": "The village"}
DAMAGE_SIZES = {"small": (10, 30), "normal": (25, 50), "large": (50, 75), "huge": (75, 100)}    # G9
SKILL_SIZES = {"small": (5, 10), "normal": (10, 20), "large": (20, 40), "huge": (30, 60)}
_POOL_TOKEN = re.compile(r"^([A-Za-z0-9_@][A-Za-z0-9_]{0,32})(?:\.([1-9]))?$")


def parse_inline(inner: str) -> list[tuple[int, str]] | None:
    """'3:red|1:blue' -> [(3, 'red'), (1, 'blue')]; None when it is not an inline pick of two or more."""
    if "|" not in inner:
        return None
    out = []
    for alt in inner.split("|"):
        m = _INLINE_WEIGHT.match(alt)
        w, t = (int(m.group(1)), m.group(2)) if m else (1, alt)
        out.append((w, t))
    return out


def inline_text(alts: list[tuple[int, str]]) -> str:
    """The canonical inline pick: "{a|b}" with equal weights of 1, else every weight written."""
    if all(w == 1 for w, _ in alts):
        return "{" + "|".join(t for _, t in alts) + "}"
    return "{" + "|".join(f"{w}:{t}" for w, t in alts) + "}"


def _canon_text(text: str, pools: Iterable[str] | None = None) -> str:
    """Version 6 text with each inline pick in its canonical form.  With `pools` (the event's pool names), a
    one-option brace {x} whose x cannot be a list or game-word name (a space, or a character outside a name) is
    just its text (G4); an identifier-shaped {x} stays, and the checks refuse it unless it names a list."""
    names = set(pools) if pools is not None else None

    def one(m: re.Match) -> str:
        raw = m.group(0)
        if raw[0] != "{":
            return raw
        inner = raw[1:-1]
        alts = parse_inline(inner)
        if alts is not None:
            return inline_text(alts)
        if names is None or inner.startswith("@"):
            return raw
        tok = _POOL_TOKEN.match(inner)
        return raw if tok else inner          # identifier-shaped: a list (checked), never text (G4)
    return _TOKEN_V6.sub(one, text) if isinstance(text, str) else text


def text_tokens(text: str) -> list[tuple[str, str]]:
    """Version 6 text as (kind, raw) pieces: "lit" (plain characters), "esc" (\\( or \\)), "ph" ((...)), "brace"
    ({...}).  Stray markup characters stay inside "lit" pieces (the checks refuse them)."""
    out: list[tuple[str, str]] = []
    pos = 0
    for m in _TOKEN_V6.finditer(text):
        if m.start() > pos:
            out.append(("lit", text[pos:m.start()]))
        raw = m.group(0)
        out.append(("esc" if raw[0] == "\\" else "ph" if raw[0] == "(" else "brace", raw))
        pos = m.end()
    if pos < len(text):
        out.append(("lit", text[pos:]))
    return out


def parse_brace(inner: str) -> tuple:
    """A brace token's inside: ("word", key) for @key, ("pool", name, instance) for NAME / NAME.k, ("inline",
    [(w, text), ...]) for a|b; ("bad", why) otherwise."""
    if inner.startswith("@"):
        return ("word", inner[1:]) if ID_RE.match(inner[1:]) else ("bad", "a game word is {@word}")
    alts = parse_inline(inner)
    if alts is not None:
        return ("inline", alts)
    m = _POOL_TOKEN.match(inner)
    if not m:
        return ("bad", "a pool is {NAME} or {NAME.k}")
    k = int(m.group(2) or 1)
    if k > MAX_INSTANCE:
        return ("bad", f"a pool's instance is 1..{MAX_INSTANCE}")
    return ("pool", m.group(1), k)


def _load_shared_pools(shared_pools: Any) -> tuple[dict, str | None]:
    if isinstance(shared_pools, dict):
        return shared_pools.get("pools", shared_pools), None
    path = Path(shared_pools) if shared_pools is not None else SHARED_POOLS
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return {}, f"include_pools: the shared pools cannot be read ({e})"
    return data.get("pools", {}) if isinstance(data, dict) else {}, None


def pool_names_of(data: dict) -> set[str]:
    """The pool names a version 6 graph's text may name: its own pools and the shared ones it includes."""
    names = set(data.get("pools") or {}) if isinstance(data.get("pools"), dict) else set()
    include = data.get("include_pools") or []
    return names | ({x for x in include if isinstance(x, str)} if isinstance(include, list) else set())


def _norm_pool(name: str, p: Any, where: str, problems: list[str], version: int,
               names: set[str] | None = None) -> dict:
    if not isinstance(p, dict) or set(p) - {"items", "distinct", "src", "distinct_from"} \
            or not isinstance(p.get("items"), list) or not p["items"]:
        problems.append(f"{where}: a pool is {{\"items\": [text or {{\"text\", \"weight\", \"if\"}}, ...], "
                        "\"distinct\": bool}")
        return {"items": [], "distinct": False}
    items = []
    for i, it in enumerate(p["items"]):
        iw = f"{where} item {i + 1}"
        if isinstance(it, str):
            it = {"text": it}
        if not isinstance(it, dict) or not isinstance(it.get("text"), str) or set(it) - {"text", "weight", "if", "src"}:
            problems.append(f"{iw}: an item is text or {{\"text\": \"...\", \"weight\": n, \"if\": condition}}")
            continue
        w = it.get("weight", 1)
        if not _int_in(w, 1, MAX_WEIGHT):
            problems.append(f"{iw}: weight is a whole number 1..{MAX_WEIGHT}")
        item = {"text": _canon_text(it["text"], names), "weight": w,
                "if": _norm_cond(it.get("if"), iw, problems, version)}
        if "src" in it:
            item["src"] = it["src"]
        items.append(item)
    out = {"items": items, "distinct": bool(p.get("distinct", False))}
    frm = p.get("distinct_from")
    if frm is not None:
        # G3: never an item whose text another listed pool's instance has already drawn.
        if not isinstance(frm, list) or any(not isinstance(x, str) for x in frm) or len(set(frm)) != len(frm):
            problems.append(f"{where}: distinct_from is a list of pool names")
        elif frm:
            out["distinct_from"] = list(frm)
    if "src" in p:
        out["src"] = p["src"]
    return out


def _normalize_v6_extras(data: dict, g: dict, problems: list[str], shared_pools: Any) -> None:
    """words, pools (and include_pools), collection and grammar_fixes of a version 6 graph, into `g`."""
    version = g["version"]
    names = pool_names_of(data)
    words_in = data.get("words", {})
    words: dict[str, dict[str, str]] = {}
    if not isinstance(words_in, dict):
        problems.append("words is {\"word\": {\"<game>\" or \"*\": \"text\"}}")
        words_in = {}
    for key, per in words_in.items():
        where = f"word {key}"
        if key in TRIBE_WORDS:
            problems.append(f"{where}: {{@{key}}} is built in (the save's tribe name); choose another word")
            continue
        if not ID_RE.match(str(key)) or not isinstance(per, dict) or not per \
                or any(not isinstance(v, str) for v in per.values()):
            problems.append(f"{where}: a game word is {{\"<game>\" or \"*\": \"text\"}}")
            continue
        out = {}
        for gn in g["games"]:
            text = per.get(str(gn), per.get("*"))
            if text is None:
                problems.append(f"{where}: no word for {GAMES[gn].name} (give it, or \"*\")")
                continue
            out[str(gn)] = text
        for k in per:
            if k != "*" and k not in {str(x) for x in g["games"]}:
                problems.append(f"{where}: {k!r} is not one of the event's games")
        words[key] = out
    g["words"] = words

    pools: dict[str, dict] = {}
    pools_in = data.get("pools", {})
    if not isinstance(pools_in, dict):
        problems.append("pools is {\"NAME\": pool}")
        pools_in = {}
    for name, p in pools_in.items():
        if not POOL_RE.match(str(name)):
            problems.append(f"pool {name}: a pool name is 1..32 letters, digits or _, starting with a letter or digit")
            continue
        pools[name] = _norm_pool(name, p, f"pool {name}", problems, version, names)
    include = data.get("include_pools", [])
    if include:
        if not isinstance(include, list) or any(not isinstance(x, str) for x in include):
            problems.append("include_pools is a list of shared pool names")
            include = []
        shared, why = _load_shared_pools(shared_pools)
        if why:
            problems.append(why)
        for name in include:
            if name in pools:
                problems.append(f"include_pools: {name} is also one of the event's own pools")
            elif name not in shared:
                problems.append(f"include_pools: {name} is not a shared pool")
            elif not POOL_RE.match(name):
                problems.append(f"include_pools: {name} is not a pool name")
            else:
                pools[name] = _norm_pool(name, shared[name], f"shared pool {name}", problems, version, names)
    g["pools"] = pools

    col = data.get("collection")
    if col is not None:
        keys = ("id", "source", "lines", "section", "credit", "draw_weight", "series")
        if not isinstance(col, dict) or set(col) - set(keys):
            problems.append("collection: its fields are " + ", ".join(keys))
            col = {}
        out = {"id": col.get("id"), "source": col.get("source", ""), "lines": col.get("lines"),
               "section": col.get("section", ""), "credit": col.get("credit", ""),
               "draw_weight": col.get("draw_weight", 1), "series": col.get("series")}
        if not isinstance(out["id"], str) or not COLLECTION_ID_RE.match(out["id"]):
            problems.append("collection: id is 1..64 of a-z, 0-9 and _")
        lines = out["lines"]
        if not (isinstance(lines, list) and len(lines) == 2 and all(_int_in(x, 1, 10 ** 7) for x in lines)
                and lines[0] <= lines[1]):
            problems.append("collection: lines is [first, last]")
        for k in ("source", "section", "credit"):
            if not isinstance(out[k], str):
                problems.append(f"collection: {k} is text")
        if not _int_in(out["draw_weight"], 1, MAX_WEIGHT):
            problems.append(f"collection: draw_weight is 1..{MAX_WEIGHT}")
        if out["series"] is not None and (not isinstance(out["series"], str)
                                          or not COLLECTION_ID_RE.match(out["series"])):
            problems.append("collection: series is null or 1..64 of a-z, 0-9 and _")
        g["collection"] = out
    if "grammar_fixes" in data:
        if not isinstance(data["grammar_fixes"], list):
            problems.append("grammar_fixes is a list")
        g["grammar_fixes"] = data["grammar_fixes"]


# ---- Placeholders --------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Placeholder:
    role: str | None      # None for award / award_unit
    what: str             # "name", a PRONOUNS key, "award", "award_unit"
    capital: bool
    upper: bool = False   # version 6: written in capitals, (NAME1) (HE/SHE): the word in capitals
    hint: str | None = None   # version 6 labels: a name's pronoun fallback form, (ACCUSED|HE/SHE) (section 15)


def parse_placeholder(token: str) -> Placeholder | None:
    """'(friend.His/Her)' -> Placeholder('friend', 'his/her', True); None when it is not one."""
    role, _, word = token.rpartition(".")
    role = role or None
    low = word.lower()
    if low in ("award", "award_unit"):
        return None if role else Placeholder(None, low, False)
    if low in _NAME_ALIASES:
        return None if role else Placeholder(_NAME_ALIASES[low], "name", word[0].isupper())
    if low == "name" or low in PRONOUNS:
        if word[0].isupper() != (word.split("/")[0][0].isupper()):
            return None
        return Placeholder(role or "subject", low, word[0].isupper())
    return None


def placeholders(text: str) -> list[tuple[str, Placeholder | None]]:
    return [(m.group(0), parse_placeholder(m.group(1))) for m in PLACEHOLDER_RE.finditer(text)]


@dataclass
class Binding:
    """Who a role is in one run: a name (villagers) and a sex ("m" / "f")."""
    name: str
    sex: str


def expand(text: str, bindings: dict[str, Binding], award: tuple[str, int] | None = None) -> str:
    """The text as the player reads it: placeholders filled.  award = (kind, amount actually given)."""
    def one(m: re.Match) -> str:
        p = parse_placeholder(m.group(1))
        if p is None:
            raise KeyError(f"not a placeholder: {m.group(0)}")
        if p.what == "award":
            return str(award[1]) if award else ""
        if p.what == "award_unit":
            return UNITS[award[0]] if award else ""
        b = bindings[p.role]
        word = b.name if p.what == "name" else PRONOUNS[p.what][0 if b.sex == "m" else 1]
        return word[0].upper() + word[1:] if p.capital and word else word
    return PLACEHOLDER_RE.sub(one, text)


def worst_case(text: str, game: Game, award: tuple[str, int, bool] | None) -> str:
    """The text at its widest in `game`: the longest names, the longer pronouns, the widest award."""
    def one(m: re.Match) -> str:
        p = parse_placeholder(m.group(1))
        if p is None:
            return m.group(0)
        if p.what == "award":
            if award is None:
                return ""
            widest = max(abs(x) for x in award[1]) if isinstance(award[1], tuple) else abs(award[1])
            return "9" * (AWARD_WIDEST if award[2] else len(str(widest)))
        if p.what == "award_unit":
            return UNITS[award[0]] if award else UNITS["tech"]
        if p.what == "name":
            return "W" * game.name_room
        return max(PRONOUNS[p.what], key=len)
    return PLACEHOLDER_RE.sub(one, text)


# ---- Version 6 text: placeholders, pools, game words, escapes (cie-v6-binary.md sections 5 and 6) -------------------


def parse_placeholder_v6(token: str, roles: dict) -> Placeholder | None:
    """A version 6 placeholder's inside: v5's, the four new pronouns, and the role shorthand (gardener1) /
    (Gardener1) -- that role's name, the id matched ignoring capitals.  A keyword always wins.  All in capitals
    ((NAME1), (HIM/HER), (FRIEND.HE/SHE), (GARDENER1)): the same word in capitals, the role prefix matched ignoring
    capitals.  A name may end in a pronoun hint, (ACCUSED|HE/SHE): its label fallback's form (section 15)."""
    if "|" in token:
        base, _bar, hint = token.partition("|")
        p = parse_placeholder_v6(base, roles)
        if p is None or p.what != "name" or hint.lower() not in HINT_PRONOUNS:
            return None
        return replace(p, hint=hint.lower())
    role, dot, word = token.rpartition(".")
    if dot and not role:
        return None
    low = word.lower()
    if not word:
        return None
    upper = sum(c.isalpha() for c in token) >= 2 and not any(c.islower() for c in token)
    if upper and role and role not in roles:
        role = next((r for r in roles if r.lower() == role.lower()), role)
    if low in ("award", "award_unit"):
        return None if role else Placeholder(None, low, False, upper)
    if low in _NAME_ALIASES:
        target = _NAME_ALIASES[low]
        return None if role or target not in roles else Placeholder(target, "name", word[0].isupper(), upper)
    if low == "name" or low in PRONOUNS_V6:
        if word[0].isupper() != (word.split("/")[0][0].isupper()):
            return None
        rid = role or default_role_of(roles)
        return Placeholder(rid, low, word[0].isupper(), upper) if rid in roles else None
    if role:
        return None
    for rid in roles:
        if rid.lower() == low:
            return Placeholder(rid, "name", word[0].isupper(), upper)
    return None


def _role_of_ph(p: Placeholder, roles: dict) -> dict | None:
    return roles.get(p.role) if p.role else None


def expand_v6(text: str, g: dict, bindings: dict[str, Binding], picks: dict[tuple[str, int], int] | None = None,
              award: tuple[str, int] | None = None, game: int | None = None, unicode: bool = False,
              aliases: dict[str, str] | None = None, _depth: int = 0, tribe: str | None = None,
              pronoun_names: bool = False) -> str:
    """Version 6 text as the player reads it.  `g` is a lowered graph (lower()); `picks` maps (pool, instance) to
    the item drawn; `aliases` maps an alias (or other) role to the member drawn; `tribe` is the save's tribe name
    ({@tribe}; None: "the village").  The glyph fallback is applied last."""
    picks = picks or {}
    aliases = aliases or {}
    out = []
    for kind, raw in text_tokens(text):
        if kind == "lit":
            out.append(raw)
        elif kind == "esc":
            out.append(raw[1])
        elif kind == "ph":
            p = parse_placeholder_v6(raw[1:-1], g["roles"])
            if p is None:
                raise KeyError(f"not a placeholder: {raw}")
            if p.what == "award":
                out.append(str(award[1]) if award else "")
                continue
            if p.what == "award_unit":
                unit = UNITS[award[0]] if award else ""
                out.append(unit.upper() if p.upper else unit)
                continue
            b = bindings[aliases.get(p.role, p.role)]
            if p.what == "name" and pronoun_names:      # section 15: a label too wide shows pronouns
                word = PRONOUNS_V6[p.hint or HINT_DEFAULT][0 if b.sex == "m" else 1]
            else:
                word = b.name if p.what == "name" else PRONOUNS_V6[p.what][0 if b.sex == "m" else 1]
            out.append(word.upper() if p.upper else word[0].upper() + word[1:] if p.capital and word else word)
        else:
            tok = parse_brace(raw[1:-1])
            if tok[0] == "word" and tok[1] in TRIBE_WORDS:
                # G5: the save's tribe name, filled at run time.
                name = tribe if tribe else NO_TRIBE[tok[1]]
                out.append(name[0].upper() + name[1:] if tok[1] == "Tribe" and tribe else name)
                continue
            name, k = ("@" + tok[1], 1) if tok[0] == "word" else (tok[1], tok[2])
            idx = picks.get((name, k))
            if idx is None or _depth >= MAX_POOL_DEPTH:
                continue
            out.append(expand_v6(g["pools"][name]["items"][idx]["text"], g, bindings, picks, award, game, True,
                                 aliases, _depth + 1, tribe))
    text = "".join(out)
    return text if _depth or game is None else glyph_fallback(text, game, unicode)


def worst_v6(text: str, g: dict, game: Game, award: tuple | None, holds=None, _depth: int = 0,
             pronoun_names: bool = False) -> str:
    """Version 6 text at its widest in `game` (`g` lowered): the longest names, the longer pronouns, the widest
    award, each pool instance as its longest eligible item (after its own worst case; the first on a tie), then
    the glyph fallback (VV1/VV2).  `holds(cond)` says whether an item's condition can hold (default: always)."""
    out = []
    for kind, raw in text_tokens(text):
        if kind == "lit":
            out.append(raw)
        elif kind == "esc":
            out.append(raw[1])
        elif kind == "ph":
            p = parse_placeholder_v6(raw[1:-1], g["roles"])
            if p is None:
                out.append(raw)
            elif p.what == "award":
                if award is not None:
                    widest = max(abs(x) for x in award[1]) if isinstance(award[1], tuple) else abs(award[1])
                    out.append("9" * (AWARD_WIDEST if award[2] else len(str(widest))))
            elif p.what == "award_unit":
                unit = UNITS[award[0]] if award else UNITS["tech"]
                out.append(unit.upper() if p.upper else unit)
            elif p.what == "name" and pronoun_names:      # section 15: the label's pronoun fallback
                word = max(PRONOUNS_V6[p.hint or HINT_DEFAULT], key=len)
                out.append(word.upper() if p.upper else word.capitalize() if p.capital else word)
            elif p.what == "name" and g["roles"].get(p.role, {}).get("kind") == "stranger":
                out.append("W" * stranger_name_room(game.number))     # 16: the longest name in the game's lists
            elif p.what == "name":
                out.append("W" * game.name_room)
            else:
                word = max(PRONOUNS_V6[p.what], key=len)
                out.append(word.upper() if p.upper else word.capitalize() if p.capital else word)
        else:
            tok = parse_brace(raw[1:-1])
            if tok[0] == "word" and tok[1] in TRIBE_WORDS:
                out.append("W" * TRIBE_ROOM[game.number])           # G5: the longest tribe name the game makes
                continue
            name = "@" + tok[1] if tok[0] == "word" else tok[1] if tok[0] == "pool" else None
            pool = g["pools"].get(name) if name else None
            if pool is None or _depth >= MAX_POOL_DEPTH:
                continue
            best = ""
            for it in pool["items"]:
                if holds is not None and not holds(it["if"]):
                    continue
                w = worst_v6(it["text"], g, game, award, holds, _depth + 1)
                if len(w) > len(best):
                    best = w
            out.append(best)
    text = "".join(out)
    return text if _depth else glyph_fallback(text, game.number)


def pool_refs(text: str) -> list[tuple[str, int]]:
    """The (pool, instance) tokens of lowered version 6 text, in order (game words as ("@word", 1))."""
    out = []
    for kind, raw in text_tokens(text):
        if kind == "brace":
            tok = parse_brace(raw[1:-1])
            if tok[0] == "word":
                out.append(("@" + tok[1], 1))
            elif tok[0] == "pool":
                out.append((tok[1], tok[2]))
    return out


def placeholders_v6(text: str, roles: dict) -> list[tuple[str, Placeholder | None]]:
    """The placeholders of version 6 text (escapes and braces skipped; those inside inline picks included)."""
    out = []
    for kind, raw in text_tokens(text):
        if kind == "ph":
            out.append((raw, parse_placeholder_v6(raw[1:-1], roles)))
        elif kind == "brace":
            tok = parse_brace(raw[1:-1])
            if tok[0] == "inline":
                for _w, alt in tok[1]:
                    out.extend(placeholders_v6(alt, roles))
    return out


# ---- Version 6 lowering: what the .cieg holds (inline picks and game words as pools; the harm guards) -------------


def _harmful(e: dict, games: Iterable[int]) -> bool:
    """An effect that can harm its villager (cie-v6-binary.md section 7)."""
    do = e["do"]
    if do in ("kill", "vanish", "sick"):
        return True
    if do == "health":
        return e["max"] < HEALTH_MAX
    if do == "health_change":
        return e["min"] < 0
    if do == "preference":
        return e["list"] == "dislikes"
    if do == "skill":
        return "set" not in e and e["min"] < 0
    if do == "mood":
        return e["mood"] == "bad"
    if do == "action":
        for gn in games:
            a = actions(gn).get(e["action"])
            if a is not None and (a["group"] == "MOOD" or a["unsafe"]):
                return True
    return False


def effect_role(e: dict) -> str | None:
    """The role an effect acts on, or None (food, tech, an award, damage, a celebration of everyone)."""
    if e["do"] == "celebrate":
        return None if e["who"] == "all" else e["who"]
    return e.get("role") if e["do"] in VILLAGER_EFFECTS_V6 else None


def harm_capable(g: dict) -> set[str]:
    """Version 6: the roles a harmful effect can reach (an alias harmed makes each of its members harm-capable)."""
    out: set[str] = set()
    roles = g.get("roles", {})
    for n in g.get("nodes", {}).values():
        for e in n["effects"]:
            r = effect_role(e)
            if r is None or r not in roles or not _harmful(e, g["games"]):
                continue
            out.add(r)
            out.update(members_of(roles, r))
    return out


def members_of(roles: dict, rid: str) -> list[str]:
    """The villager roles an alias, or an other role (G2: its alias's), can stand for; [] for the rest."""
    r = roles.get(rid, {})
    if r.get("kind") == "alias":
        return list(r["of"])
    if r.get("kind") == "other":
        return list(roles.get(r["of"], {}).get("of", []))
    return []


def protect_excluded(g: dict, rid: str, harm: set[str] | None = None) -> bool:
    """Whether role `rid` keeps protected villagers out (flag 32)."""
    r = g["roles"][rid]
    if r["kind"] != "villager":
        return False
    if r["protected"] == "exclude":
        return True
    return r["protected"] == "auto" and rid in (harm if harm is not None else harm_capable(g))


def _guard_for(g: dict, node: dict, harm: set[str]) -> Any:
    """The harm guard of a child edge into `node`: harmable(r) for each protected-excluding role it harms."""
    rs: list[str] = []
    for e in node["effects"]:
        r = effect_role(e)
        if r is None or r not in g["roles"] or not _harmful(e, g["games"]):
            continue
        role = g["roles"][r]
        guarded = any(protect_excluded(g, m, harm) for m in members_of(g["roles"], r)) \
            if role["kind"] in ("alias", "other") else protect_excluded(g, r, harm)
        if guarded and r not in rs:
            rs.append(r)
    if not rs:
        return None
    return {"harmable": rs[0]} if len(rs) == 1 else {"all": [{"harmable": r} for r in rs]}


def lower(g: dict) -> dict:
    """A normalized version 6 graph as the .cieg holds it: each inline pick its own pool _iN (the text says
    {_iN}), each game word the pool @word (one item per text, its condition the games using it), every pool's
    items as {"text", "weight", "if"}, and each child's harm guard ("guard")."""
    out = without_names(g)
    pools: dict[str, dict] = {}
    for name, p in out.get("pools", {}).items():
        pools[name] = {"items": [{"text": it["text"], "weight": it["weight"], "if": it["if"]} for it in p["items"]],
                       "distinct": p["distinct"], **({"distinct_from": list(p["distinct_from"])}
                                                     if p.get("distinct_from") else {})}
    for word, per in out.get("words", {}).items():
        texts: dict[str, list[int]] = {}
        for gn, text in per.items():
            texts.setdefault(text, []).append(int(gn))
        pools["@" + word] = {"items": [{"text": t, "weight": 1, "if": {"game": sorted(gs)}}
                                       for t, gs in texts.items()], "distinct": False}
    inline: dict[str, dict] = {}

    def sub(text: str) -> str:
        def one(m: re.Match) -> str:
            raw = m.group(0)
            if raw[0] != "{":
                return raw
            alts = parse_inline(raw[1:-1])
            if alts is None:
                return raw
            name = f"_i{len(inline) + 1}"
            inline[name] = {"items": [{"text": t, "weight": w, "if": None} for w, t in alts], "distinct": False}
            return "{" + name + "}"
        return _TOKEN_V6.sub(one, text)

    for n in out["nodes"].values():
        n["text"] = sub(n["text"])
        for v in n["variants"]:
            v["text"] = sub(v["text"])
    for name in list(pools):
        if not name.startswith("@"):
            for it in pools[name]["items"]:
                it["text"] = sub(it["text"])
    pools.update(inline)
    out["pools"] = pools
    harm = harm_capable(g)
    for n in out["nodes"].values():
        for c in n["children"]:
            c["guard"] = _guard_for(g, out["nodes"][c["next"]], harm) if c["next"] in out["nodes"] else None
    out["harm"] = sorted(harm)
    return out


def lift(lg: dict) -> dict:
    """lower()'s inverse: the normalized graph (without its authoring keys) of a lowered one."""
    out = copy.deepcopy(lg)
    out.pop("harm", None)
    pools = out.pop("pools", {})
    words: dict[str, dict[str, str]] = {}
    named: dict[str, dict] = {}
    for name, p in pools.items():
        if name.startswith("@"):
            per: dict[str, str] = {}
            for it in p["items"]:
                for gn in it["if"]["game"]:
                    per[str(gn)] = it["text"]
            words[name[1:]] = {k: per[k] for k in sorted(per, key=int)}
        elif not name.startswith("_"):
            named[name] = p

    def sub(text: str) -> str:
        def one(m: re.Match) -> str:
            raw = m.group(0)
            if raw[0] == "{" and raw[1:3] == "_i" and raw[1:-1] in pools:
                return inline_text([(it["weight"], it["text"]) for it in pools[raw[1:-1]]["items"]])
            return raw
        return _TOKEN_V6.sub(one, text)

    for n in out["nodes"].values():
        n["text"] = sub(n["text"])
        for v in n["variants"]:
            v["text"] = sub(v["text"])
        for c in n["children"]:
            c.pop("guard", None)
    for p in named.values():
        for it in p["items"]:
            it["text"] = sub(it["text"])
    out["words"] = words
    out["pools"] = named
    if "collection" in out:
        out["collection"] = out.pop("collection")       # after words and pools, as normalize orders it
    return out


# ---- Line layout (story_custom.inc ce_wrap) and pages ------------------------------------------------------------


def wrap(text: str, width: int) -> list[str]:
    """The lines ce_wrap makes of `text` at `width` characters (the player's line breaks kept)."""
    if not text:
        return []
    lines = [""]
    i = 0
    while i < len(text):
        c = text[i]
        if c == "\r":
            i += 1
            continue
        if c == "\n":
            lines.append("")
            i += 1
            continue
        if c == " ":
            if 0 < len(lines[-1]) < width:
                lines[-1] += " "
            i += 1
            continue
        j = i
        while j < len(text) and text[j] not in " \n\r":
            j += 1
        if lines[-1] and len(lines[-1]) + (j - i) > width:
            if lines[-1].endswith(" "):
                lines[-1] = lines[-1][:-1]
            lines.append("")
        for ch in text[i:j]:
            if len(lines[-1]) >= width:
                lines.append("")
            lines[-1] += ch
        i = j
    return lines


def popup_lines(layout: Layout, title: str, text: str) -> int:
    """The panel lines the popup takes (ce_lines_used_in): the title and four breaks first when it leads the text."""
    return len(wrap(title + "\n\n\n\n" + text if layout.with_title else text, layout.width))


_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def paginate(layout: Layout, title: str, text: str, reserve: int = 0) -> tuple[list[str], str | None]:
    """The pages the popup is shown in without scrolling (whole paragraphs where they fit, else whole sentences),
    and why it cannot be (a sentence taller than a page), else None."""
    limit = layout.lines - reserve
    pages: list[str] = []
    page = ""

    def fits(t: str) -> bool:
        return popup_lines(layout, title, t) <= limit

    def put(piece: str, sep: str) -> str | None:
        nonlocal page
        trial = page + sep + piece if page else piece
        if fits(trial):
            page = trial
            return None
        if page:
            pages.append(page)
            page = ""
        if fits(piece):
            page = piece
            return None
        return piece

    for para in text.split("\n"):
        left = put(para, "\n")
        if left is None:
            continue
        for sentence in _SENTENCE_RE.split(left):
            if put(sentence, " ") is not None:
                return pages, f"a sentence is taller than the popup ({sentence[:40]}...)"
    if page:
        pages.append(page)
    return pages, None


# ---- The walk: every history, in every context ---------------------------------------------------------------------


@dataclass(frozen=True)
class Context:
    game: int
    patches: frozenset[str]
    roles: frozenset[str]      # the roles bound in this run
    facts: frozenset[str] = frozenset()      # version 6: "harmable:<role>", "special_present:<kind>",
                                             # "min_population:<n>", "min_children:<n>" that hold
    aliases: frozenset[tuple[str, str]] = frozenset()   # version 6: (alias, member drawn)


def cond_holds(c: Any, ctx: Context, visited: Iterable[str]) -> bool:
    if c is None:
        return True
    (op, arg), = c.items()
    if op == "harmable":
        member = dict(ctx.aliases).get(arg, arg)
        return member in ctx.roles and f"harmable:{member}" in ctx.facts
    if op in ("special_present", "min_population", "min_children"):
        return f"{op}:{arg}" in ctx.facts
    if op == "visited":
        return arg in visited
    if op == "role":
        return arg in ctx.roles
    if op == "game":
        return ctx.game in arg
    if op == "patch":
        return arg in ctx.patches
    if op == "not":
        return not cond_holds(arg, ctx, visited)
    if op == "all":
        return all(cond_holds(x, ctx, visited) for x in arg)
    return any(cond_holds(x, ctx, visited) for x in arg)


def with_aliases(g: dict, bound: Iterable[str]) -> frozenset[str]:
    """`bound` (villager and stranger roles) with each alias bound when one of its members is, and each other role
    (G2) when both of its alias's members are."""
    rset = {r for r in bound if g["roles"].get(r, {}).get("kind") not in ("alias", "other")}
    out = set(rset)
    for a, v in g["roles"].items():
        if v["kind"] == "alias" and any(m in rset for m in v["of"]):
            out.add(a)
        elif v["kind"] == "other":
            ms = members_of(g["roles"], a)
            if ms and all(m in rset for m in ms):
                out.add(a)
    return frozenset(out)


def contexts(g: dict, games: Iterable[int] | None = None) -> list[Context]:
    """Every game x every patch on or off x every optional role bound or not."""
    optional = [r for r, v in g["roles"].items() if v.get("optional")]
    always = frozenset(r for r in g["roles"] if r not in optional and g["roles"][r]["kind"] not in ("alias", "other"))
    v6 = g.get("version", 1) >= VERSION_V6
    out = []
    for game in (games if games is not None else g["games"]):
        for pbits in product((False, True), repeat=len(g["patches"])):
            pset = frozenset(p for p, on in zip(g["patches"], pbits) if on)
            for rbits in product((False, True), repeat=len(optional)):
                rset = always | {r for r, on in zip(optional, rbits) if on}
                if not v6:
                    out.append(Context(game, pset, frozenset(rset)))
                    continue
                rset = with_aliases(g, rset)
                for facts in _fact_sets(g, rset):
                    out.append(Context(game, pset, frozenset(rset), facts))
    return out


def _all_conds(g: dict) -> Iterable[Any]:
    for n in g["nodes"].values():
        for v in n["variants"]:
            yield v["if"]
        for c in n["children"]:
            yield c["if"]
        for c in n["choices"]:
            yield c.get("if")
    for p in g.get("pools", {}).values():
        for it in p["items"]:
            yield it["if"]


def _cond_leaves(c: Any, out: list) -> None:
    if c is None:
        return
    (op, arg), = c.items()
    if op == "not":
        _cond_leaves(arg, out)
    elif op in ("all", "any"):
        for x in arg:
            _cond_leaves(x, out)
    else:
        out.append((op, arg))


def _fact_sets(g: dict, bound: frozenset[str]) -> list[frozenset[str]]:
    """Version 6: every combination of the run-time facts the graph's conditions ask about.  A role that keeps
    protected villagers out is always harmable when bound (it is cast unprotected); other roles' harmable, and
    each special present, may go either way; the population and children thresholds rise together."""
    harm = harm_capable(g)
    base = {f"harmable:{r}" for r in bound if g["roles"][r]["kind"] == "villager" and protect_excluded(g, r, harm)}
    leaves: list = []
    for c in _all_conds(g):
        _cond_leaves(c, leaves)
    free = sorted({f"harmable:{a}" for op, a in leaves if op == "harmable" and a in bound
                   and g["roles"].get(a, {}).get("kind") == "villager" and f"harmable:{a}" not in base}
                  | {f"special_present:{a}" for op, a in leaves if op == "special_present"})
    pops = sorted({a for op, a in leaves if op == "min_population"})
    kids = sorted({a for op, a in leaves if op == "min_children"})
    out = []
    for bits in product((False, True), repeat=len(free)):
        on = {f for f, b in zip(free, bits) if b}
        for i in range(len(pops) + 1):
            for j in range(len(kids) + 1):
                out.append(frozenset(base | on | {f"min_population:{n}" for n in pops[:i]}
                                     | {f"min_children:{n}" for n in kids[:j]}))
    return out


def default_facts(g: dict, bound: Iterable[str]) -> frozenset[str]:
    """The facts a chances table assumes: every bound villager harmable, every threshold met, no special present."""
    leaves: list = []
    for c in _all_conds(g):
        _cond_leaves(c, leaves)
    return frozenset({f"harmable:{r}" for r in bound if g["roles"].get(r, {}).get("kind") == "villager"}
                     | {f"{op}:{a}" for op, a in leaves if op in ("min_population", "min_children")})


@dataclass
class Popup:
    layout: str                         # "plain", "question", "result"
    text: str = ""                      # the raw text, as the nodes join it
    worst: str = ""                     # at its widest in the game
    effects: bool = False               # carries villager effects (refusal lines)
    nodes: list[str] = field(default_factory=list)
    room: int = 0                       # lines kept for a question's third and fourth buttons (answer_room)
    answers: int = 0                    # a question's buttons shown (version 6: its answer's page room)
    titles: list[str] = field(default_factory=list)   # the titles in force on it ("" = the event's), in order


@dataclass
class History:
    """One history from the start to an ending."""
    choice: int | None                  # the first question's button (0, 1), None without a question
    nodes: tuple[str, ...]
    chance: Fraction
    popups: list[Popup]
    award: tuple | None                       # the award deferred or paid: (kind, amount or (min, max), scaled)
    paid: bool
    effects: list[tuple[str, dict]]           # (node, effect) in order
    ctx: Context
    answers: tuple[tuple[str, int], ...] = ()  # every question on the way and the button answered, in order

    @property
    def end(self) -> str:
        return self.nodes[-1]


def node_text(node: dict, ctx: Context, visited: Iterable[str]) -> str:
    for v in node["variants"]:
        if cond_holds(v["if"], ctx, visited):
            return v["text"]
    return node["text"]


def _resolved_children(node: dict, ctx: Context, visited: tuple[str, ...]) -> list[tuple[str, int]]:
    out = []
    for c in node["children"]:
        # Version 6: a child's harm guard (lower()) must hold too.
        if cond_holds(c["if"], ctx, visited) and cond_holds(c.get("guard"), ctx, visited):
            out.append((c["next"], c["weight"]))
        elif c["else"] is not None:
            out.append((c["else"], c["weight"]))
    if not out and node["else"] is not None:
        out.append((node["else"], 1))
    return out


def walk(g: dict, ctx: Context, problems: list[str] | None = None) -> list[History]:
    """Every history of the graph in `ctx`, with its chance (each question button counts as 1).  Problems on a
    history (an unbound role, an award never deferred, a dead end, ...) are added to `problems`.  Version 6: the
    walk runs over the lowered graph (lower()); each alias's member is a chance split at the start."""
    v6 = g.get("version", 1) >= VERSION_V6
    lg = lower(g) if v6 else g
    nodes = lg["nodes"]
    game = GAMES[ctx.game]
    found: list[History] = []
    seen: set[str] = set()
    ctx0 = ctx

    def say(msg: str) -> None:
        if problems is not None and msg not in seen:
            seen.add(msg)
            problems.append(msg)

    where = f"{game.name}" + (f" with {', '.join(sorted(ctx.patches))}" if ctx.patches else "") + \
        ("" if all(r in ctx.roles for r in g["roles"]) else
         f" without {', '.join(r for r in g['roles'] if r not in ctx.roles)}")

    v2 = g.get("version", 1) >= 2
    max_popups = MAX_POPUPS_PER_RUN_V2 if v2 else MAX_POPUPS_PER_RUN

    # seg: (a question has been answered on the way, a page was shown since the last question (or the start),
    #       a node with changes was reached since then) -- the companion shows each answer's own page first, and a
    #       change needs a page to come with (version 2).
    def visit(nid: str, choice, path: tuple, chance: Fraction, popups: list[Popup], award, paid: bool,
              gone: frozenset, effects: list, answers: tuple = (), seg: tuple = (False, False, False),
              title: str = "") -> None:
        if len(found) >= MAX_PATHS:
            say(f"more than {MAX_PATHS} histories: the graph is too big")
            return
        node = nodes[nid]
        path = path + (nid,)
        popups = [Popup(p.layout, p.text, p.worst, p.effects, list(p.nodes), p.room, p.answers, list(p.titles))
                  for p in popups]
        ntitle = node.get("title", "") if node["type"] != "branch" else ""   # cie-v6-binary.md 14
        effects = list(effects)
        # Effects first: an award deferred here is the (award) of this node's own text.
        for e in node["effects"]:
            do = e["do"]
            cap = EFFECT_CAPS[do]
            if cap and not game.caps & cap:
                say(f"node {nid}: {do} is not offered in {game.name}'s Custom Island Event")
            if do in ("food", "tech") and e["defer"]:
                if award is not None and not paid:
                    say(f"node {nid} ({where}): an award is deferred while another is still unpaid")
                amount = effect_amount(e, game.number)
                award, paid = (do, amount, e["scaled"]), False
            elif do == "pay_award":
                if award is None or paid:
                    say(f"node {nid} ({where}): pay_award with no award deferred on the way here")
                paid = True
            if v6:
                if "set" in e and not game.caps & CAP_SKILLS:
                    say(f"node {nid}: skill is not offered in {game.name}'s Custom Island Event")
                r = effect_role(e)
                if r is not None:
                    kind = g["roles"].get(r, {}).get("kind")
                    member = dict(ctx.aliases).get(r, r)
                    if kind not in ("villager", "alias", "other"):
                        say(f"node {nid}: {do} acts on {r!r}, which is not a villager role")
                    elif r not in ctx.roles:
                        say(f"node {nid} ({where}): {do} acts on {r}, who may not be bound here")
                    elif member in gone:
                        say(f"node {nid} ({where}): {do} acts on {r}, who is already gone")
                    if do in GONE_EFFECTS:
                        gone = gone | {member}
                    if do == "status" and e.get("status") not in game.statuses:
                        say(f"node {nid}: status {e.get('status')} is not in {game.name}")
                    if do == "preference" and e.get("preference") not in game.preferences:
                        say(f"node {nid}: {e.get('preference')!r} is not one of {game.name}'s preferences")
                effects.append((nid, e))
                continue
            if do in VILLAGER_EFFECTS:
                r = e["role"]
                if r not in g["roles"] or g["roles"][r]["kind"] != "villager":
                    say(f"node {nid}: {do} acts on {r!r}, which is not a villager role")
                elif r not in ctx.roles:
                    say(f"node {nid} ({where}): {do} acts on {r}, who may not be bound here")
                elif r in gone:
                    say(f"node {nid} ({where}): {do} acts on {r}, who is already gone")
                if do in GONE_EFFECTS:
                    gone = gone | {r}
                if do == "status" and e.get("status") not in game.statuses:
                    say(f"node {nid}: status {e.get('status')} is not in {game.name}")
                if do == "preference" and e.get("preference") not in game.preferences:
                    say(f"node {nid}: {e.get('preference')!r} is not one of {game.name}'s preferences")
                if do == "skill":
                    for s in e["skills"]:
                        if s not in game.skills:
                            say(f"node {nid}: {s!r} is not one of {game.name}'s skills")
            effects.append((nid, e))

        asked, paged, changed = seg
        changed = changed or bool(node["effects"])
        text = node_text(node, ctx, path) if node["type"] != "branch" else ""
        if node["type"] == "question":
            if nid != g["start"] and not v2:
                say(f"node {nid}: a question can only be the start node in a version 1 event (version 2 asks "
                    "anywhere)")
            if v2 and not paged and (asked or changed):
                say(f"node {nid} ({where}): " + ("an answer must show a page of its own before the next question"
                                                 if asked else "the changes before this question need a page"))
            if len(answers) >= MAX_QUESTIONS_PER_RUN:
                say(f"the history {' > '.join(path)} asks more than {MAX_QUESTIONS_PER_RUN} questions")
            if v6:
                shown = [i for i, c in enumerate(node["choices"]) if cond_holds(c.get("if"), ctx, path)]
                if len(shown) < MIN_ANSWERS:
                    say(f"node {nid} ({where}): only {len(shown)} of its answers are shown; at least {MIN_ANSWERS}")
                room = answer_room(len(shown), game.question)
            else:
                shown = node["choices"]
                room = answer_room(len(node["choices"]))
            popups.append(Popup("question", text, nodes=[nid], room=room, answers=len(shown),
                                titles=[ntitle or title]))
        elif node["type"] == "popup":
            paged = True
            if node["popup"] == "append":
                if not popups or popups[-1].layout == "question":
                    say(f"node {nid} ({where}): append with no popup open to append to")
                    popups.append(Popup("result"))
                last = popups[-1]
                sep = " " if node["join"] == "space" else "\n"
                last.text = last.text + sep + text if last.text else text
                last.nodes.append(nid)
                if ntitle:
                    last.titles.append(ntitle)
            else:
                # An answer's first page is shown in the question's own popup, keeping room for its buttons (two to
                # four).  G1: after five or more buttons it starts a fresh popup -- the island-event notice the
                # engine shows it through, whose layout is the plain popup's (story_graph.inc cg_notice_layout:
                # New Believers 14 lines, not the result's 17), with no room for buttons.
                after = popups and popups[-1].layout == "question"
                room = 0
                kind = "plain" if not popups else "result"
                if after:
                    if not v6:
                        room = popups[-1].room
                    elif popups[-1].answers <= MAX_ANSWERS_V4:
                        room = answer_room(popups[-1].answers, game.result)
                    else:
                        kind = "plain"
                # 14: a page shown in the question's own popup keeps that popup's title.
                in_question = after and (not v6 or popups[-1].answers <= MAX_ANSWERS_V4)
                titles = [title] + ([ntitle] if ntitle else []) if in_question else [ntitle or title]
                popups.append(Popup(kind, text, nodes=[nid], room=room, titles=titles))
        title = ntitle or title
        if node["type"] != "branch" and v6:
            _walk_text_v6(lg, nid, text, ctx, path, award, where, say,
                          [c["label"] for c in node["choices"] if cond_holds(c.get("if"), ctx, path)])
        elif node["type"] != "branch":
            for raw, p in placeholders(text):
                if p is None:
                    say(f"node {nid}: {raw} is not a placeholder (parentheses are only placeholders)")
                elif p.role is not None:
                    role = g["roles"].get(p.role)
                    if role is None:
                        say(f"node {nid}: {raw} names no role")
                    elif p.what == "name" and role["kind"] != "villager":
                        say(f"node {nid}: {raw}: a stranger has no name")
                    elif p.role not in ctx.roles:
                        say(f"node {nid} ({where}): {raw} is shown while {p.role} may not be bound")
                elif award is None:
                    say(f"node {nid} ({where}): {raw} is shown with no award on the way here")
        villager_fx = VILLAGER_EFFECTS_V6 + ("celebrate",) if v6 else VILLAGER_EFFECTS
        if any(e["do"] in villager_fx for e in node["effects"]) and popups and node["type"] != "question":
            popups[-1].effects = True
        if node["type"] != "branch" and popups:
            if v6:
                popups[-1].worst = worst_v6(popups[-1].text, lg, game, award,
                                            lambda c, _p=path: cond_holds(c, ctx, _p))
            else:
                popups[-1].worst = worst_case(popups[-1].text, game, award)

        if node["type"] == "question":
            for i, c in enumerate(node["choices"]):
                if v6 and not cond_holds(c.get("if"), ctx, path):
                    continue
                if c["next"] in nodes:
                    visit(c["next"], i if choice is None else choice, path, chance, popups, award, paid, gone,
                          effects, answers + ((nid, i),), (True, False, False), title)
            return
        kctx = ctx
        if v6 and gone:
            kctx = replace(ctx, facts=ctx.facts - {f"harmable:{x}" for x in gone})
        kids = _resolved_children(node, kctx, path)
        if not kids:
            if node["children"]:
                say(f"node {nid} ({where}): no child applies on the history {' > '.join(path)}, and no else")
            if v2 and not paged and (asked or changed or not popups):
                say(f"node {nid} ({where}): " + ("an answer must show a page of its own before the event ends"
                                                 if asked else "the event must show a page"))
            n_new = len(popups)
            if n_new > max_popups:
                say(f"the history {' > '.join(path)} shows {n_new} popups; at most {max_popups}")
            found.append(History(choice, path, chance, popups, award, paid, effects, ctx, answers))
            return
        total = sum(w for _, w in kids)
        for nxt, w in kids:
            if nxt in nodes:
                visit(nxt, choice, path, chance * Fraction(w, total), popups, award, paid, gone, effects, answers,
                      (asked, paged, changed), title)

    if g["start"] not in nodes:
        return found
    if not v6:
        visit(g["start"], None, (), Fraction(1), [], None, False, frozenset(), [])
        return found
    # Version 6: each alias is drawn at the start among its bound members, equally.
    aliases = [(a, [m for m in r["of"] if m in ctx0.roles]) for a, r in g["roles"].items()
               if r["kind"] == "alias"]
    aliases = [(a, ms) for a, ms in aliases if ms]
    combos = list(product(*[ms for _a, ms in aliases])) if aliases else [()]
    for combo in combos:
        drawn = dict((a, m) for (a, _ms), m in zip(aliases, combo))
        drawn.update(others_drawn(g["roles"], drawn, ctx0.roles))
        ctx = replace(ctx0, aliases=frozenset(drawn.items()))
        visit(g["start"], None, (), Fraction(1, len(combos)), [], None, False, frozenset(), [])
    return found


def others_drawn(roles: dict, drawn: dict[str, str], bound: Iterable[str]) -> dict[str, str]:
    """G2: each other role -> its alias's member the alias did not draw (bound only)."""
    bound = set(bound)
    out = {}
    for o, v in roles.items():
        if v["kind"] == "other" and v["of"] in drawn:
            rest = [m for m in members_of(roles, o) if m != drawn[v["of"]] and m in bound]
            if rest:
                out[o] = rest[0]
    return out


def _walk_text_v6(lg: dict, nid: str, text: str, ctx: Context, path: tuple, award, where: str, say,
                  labels: list[str]) -> None:
    """A version 6 node's text (and its shown labels) on one history: every placeholder's role bound, every pool
    used with an item that can be drawn here, the award on the way."""
    roles = lg["roles"]
    texts = [text] + labels
    done: set[str] = set()
    k = 0
    while k < len(texts):
        t = texts[k]
        k += 1
        for raw, p in placeholders_v6(t, roles):
            if p is None:
                say(f"node {nid}: {raw} is not a placeholder (write \\( \\) for a parenthesis)")
            elif p.role is not None:
                role = roles.get(p.role)
                if role is None:
                    say(f"node {nid}: {raw} names no role")
                elif p.what == "name" and role["kind"] == "stranger" and not role.get("named"):
                    say(f"node {nid}: {raw}: a stranger has no name")
                elif p.role not in ctx.roles:
                    say(f"node {nid} ({where}): {raw} is shown while {p.role} may not be bound")
            elif award is None:
                say(f"node {nid} ({where}): {raw} is shown with no award on the way here")
        for name, _inst in pool_refs(t):
            pool = lg["pools"].get(name)
            if pool is None or name in done:
                continue
            done.add(name)
            items = [it for it in pool["items"] if cond_holds(it["if"], ctx, path)]
            if not items:
                say(f"node {nid} ({where}): " + (f"no word {name[1:]} for this game" if name.startswith("@")
                                                 else f"pool {name} has no item that can be drawn here"))
            texts.extend(it["text"] for it in items)


# ---- Validation ----------------------------------------------------------------------------------------------------


def _edges(node: dict) -> list[str]:
    out = [c["next"] for c in node["children"]] + [c["else"] for c in node["children"] if c["else"]]
    out += [c["next"] for c in node["choices"]]
    if node["else"]:
        out.append(node["else"])
    return out


def _cond_refs(c: Any, out: list[tuple[str, str]]) -> None:
    if c is None:
        return
    (op, arg), = c.items()
    if op in ("visited", "role", "patch", "harmable"):
        out.append((op, arg))
    elif op == "not":
        _cond_refs(arg, out)
    elif op in ("all", "any"):
        for x in arg:
            _cond_refs(x, out)


def _check_refs(g: dict, where: str, refs: list[tuple[str, str]], problems: list[str]) -> None:
    for op, ref in refs:
        if op == "visited" and ref not in g["nodes"]:
            problems.append(f"{where}: visited {ref!r} names no node")
        if op in ("role", "harmable") and ref not in g["roles"]:
            problems.append(f"{where}: {op} {ref!r} names no role")
        if op == "patch" and ref not in g["patches"]:
            problems.append(f"{where}: patch {ref!r} is not in patches")


def _check_text_v6(where: str, text: str, problems: list[str], g: dict, label: bool = False,
                   uses: dict | None = None) -> None:
    """Version 6 text: the character set, every placeholder, escape and brace token (cie-v6-binary.md 5).  `uses`
    collects each pool's highest instance."""
    if len(text.encode("ascii", "replace")) > NODE_TEXT_MAX:
        problems.append(f"{where}: text is longer than {NODE_TEXT_MAX} characters")
    bad: set[str] = set()
    for kind, raw in text_tokens(text):
        if kind == "lit":
            bad |= {c for c in raw if not text_char_ok(c, VERSION_V6) or c in "(){}\\|@"}
        elif kind == "esc":
            if raw not in ("\\(", "\\)"):
                problems.append(f"{where}: {raw} is not \\( or \\)")
        elif kind == "ph":
            ph = parse_placeholder_v6(raw[1:-1], g["roles"])
            if ph is None:
                problems.append(f"{where}: {raw} is not a placeholder (write \\( \\) for a parenthesis)")
            elif ph.hint and not label:
                problems.append(f"{where}: {raw}: a pronoun hint is only for button labels")
        else:
            tok = parse_brace(raw[1:-1])
            if tok[0] == "bad":
                problems.append(f"{where}: {raw}: {tok[1]}")
            elif tok[0] == "word":
                if tok[1] not in g.get("words", {}) and tok[1] not in TRIBE_WORDS:
                    problems.append(f"{where}: {raw} names no game word")
            elif label:
                problems.append(f"{where}: a label shows game words only, not {raw}")
            elif tok[0] == "pool":
                if tok[1] not in g.get("pools", {}):
                    problems.append(f"{where}: {raw}: unknown list {tok[1]} (names no pool)")
                elif uses is not None:
                    uses[tok[1]] = max(uses.get(tok[1], 0), tok[2])
            else:
                for w, alt in tok[1]:
                    if not _int_in(w, 1, MAX_WEIGHT) or not alt.strip():
                        problems.append(f"{where}: {raw}: each choice is text, weight 1..{MAX_WEIGHT}")
                        break
                for alt_kind, alt_raw in text_tokens("".join(a for _w, a in tok[1])):
                    if alt_kind == "lit":
                        bad |= {c for c in alt_raw if not text_char_ok(c, VERSION_V6) or c in "(){}\\|@\n"}
                    elif alt_kind == "ph" and parse_placeholder_v6(alt_raw[1:-1], g["roles"]) is None:
                        problems.append(f"{where}: {alt_raw} is not a placeholder")
                    elif alt_kind == "brace":
                        inner = parse_brace(alt_raw[1:-1])
                        if inner[0] != "word" or (inner[1] not in g.get("words", {}) and inner[1] not in TRIBE_WORDS):
                            problems.append(f"{where}: {raw}: inside a pick only a game word may stand ({alt_raw}); "
                                            "use a named list")
    if bad:
        problems.append(f"{where}: characters the game cannot show: {' '.join(repr(c) for c in sorted(bad))} "
                        "(letters, digits, space and . , ! ? : - ' \" ; / & % only; markup ( ) { } | @ \\ only "
                        "as placeholders, pools, game words and \\( \\))")


def _pool_depth(g: dict, name: str, stack: tuple = ()) -> int:
    """How deep pool `name` nests (1 = its items hold no pool); MAX_POOL_DEPTH + 1 on a loop."""
    if name in stack or len(stack) > MAX_POOL_DEPTH:
        return MAX_POOL_DEPTH + 1
    deepest = 0
    for it in g["pools"][name]["items"]:
        for kind, raw in text_tokens(it["text"]):
            if kind == "brace":
                tok = parse_brace(raw[1:-1])
                if tok[0] == "pool" and tok[1] in g["pools"]:
                    deepest = max(deepest, _pool_depth(g, tok[1], stack + (name,)))
    return 1 + deepest


def _validate_v6(g: dict, problems: list[str]) -> None:
    """Version 6's own checks: pools, game words, roles' requirements and safety, the new effects' words."""
    uses: dict[str, int] = {}
    for nid, n in g["nodes"].items():
        if n["type"] != "branch":
            _check_text_v6(f"node {nid}", n["text"], [], g, uses=uses)
            for v in n["variants"]:
                _check_text_v6(f"node {nid}", v["text"], [], g, uses=uses)
    for name, p in g["pools"].items():
        refs: list[tuple[str, str]] = []
        for i, it in enumerate(p["items"]):
            _check_text_v6(f"pool {name} item {i + 1}", it["text"], problems, g, uses=uses)
            if not it["text"].strip():
                problems.append(f"pool {name} item {i + 1}: an item has text")
            _cond_refs(it["if"], refs)
        _check_refs(g, f"pool {name}", refs, problems)
        if _pool_depth(g, name) > MAX_POOL_DEPTH:
            problems.append(f"pool {name}: its items nest pools more than {MAX_POOL_DEPTH} deep, or name "
                            "themselves")
    for name, p in g["pools"].items():
        for other in p.get("distinct_from", []):
            if other not in g["pools"] and other != name:
                problems.append(f"pool {name}: distinct_from names no pool ({other})")
    for name, k in uses.items():
        p = g["pools"].get(name)
        if p is not None and p["distinct"] and k > len(p["items"]):
            problems.append(f"pool {name}: {k} different items are used; it has {len(p['items'])}")
    for word, per in g["words"].items():
        for gn, text in per.items():
            _check_text_v6(f"word {word}", text, problems, g)
            for kind, raw in text_tokens(text):
                if kind == "brace":
                    problems.append(f"word {word}: a game word holds no pools or words")
    refs = []
    _cond_refs(g["requirement"].get("if"), refs)
    _check_refs(g, "requirement", refs, problems)
    lg = lower(g)
    if len(lg["pools"]) > MAX_POOLS or sum(len(p["items"]) for p in lg["pools"].values()) > MAX_ITEMS:
        problems.append(f"at most {MAX_POOLS} pools and {MAX_ITEMS} items (game words and inline picks included)")
    harm = harm_capable(g)
    collection = "collection" in g
    for rid, r in g["roles"].items():
        if r["kind"] != "villager":
            continue
        if rid in harm and r["protected"] == "allow" and collection:
            problems.append(f"role {rid}: can be harmed, so protected villagers stay out (protected cannot be "
                            "allow in a collection event)")
        if rid in harm and r["special"] and collection:
            problems.append(f"role {rid}: a {r['special']} role is never harmed")
        if r["skill"] and not any(s in GAMES[gn].skills for s in r["skill"]["names"] for gn in g["games"]):
            problems.append(f"role {rid}: none of its skills is in the event's games")
    all_skills = {s for gm in GAMES.values() for s in gm.skills}
    for nid, n in g["nodes"].items():
        for i, e in enumerate(n["effects"]):
            where = f"node {nid} effect {i + 1}"
            if e["do"] == "celebrate" and e["who"] != "all" and \
                    g["roles"].get(e["who"], {}).get("kind") not in ("villager", "alias", "other"):
                problems.append(f"{where}: celebrate's who is all or a villager role")
            if e["do"] == "action" and isinstance(e["action"], str) and \
                    not any(e["action"] in actions(gn) for gn in g["games"]):
                problems.append(f"{where}: {e['action']!r} is not an action of the event's games")
            if e["do"] == "skill":
                for s in e["skills"]:
                    if s not in all_skills:
                        problems.append(f"{where}: {s!r} is not a skill in any game")


def _check_text(where: str, text: str, problems: list[str], version: int = 1, g: dict | None = None,
                label: bool = False) -> None:
    if version >= VERSION_V6 and g is not None:
        _check_text_v6(where, text, problems, g, label)
        return
    if len(text.encode("ascii", "replace")) > NODE_TEXT_MAX:
        problems.append(f"{where}: text is longer than {NODE_TEXT_MAX} characters")
    for raw, p in placeholders(text):
        if p is None:
            problems.append(f"{where}: {raw} is not a placeholder (parentheses are only placeholders)")
    bare = PLACEHOLDER_RE.sub("", text)
    bad = sorted({c for c in bare if not text_char_ok(c, version)})
    if bad:
        problems.append(f"{where}: characters the game cannot show: {' '.join(repr(c) for c in bad)} (letters, "
                        "digits, space and . , ! ? : - ' only" + (', and "' if version >= 2 else '') + ")")


def fit_problems(g: dict, paths: list[History], scrolling: bool) -> list[str]:
    """The popups of `paths` (one context's) against the game's popups."""
    problems: list[str] = []
    done: set[tuple] = set()
    for p in paths:
        game = GAMES[p.ctx.game]
        for pop in p.popups:
            key = (game.number, pop.layout, pop.worst, pop.effects, pop.room, tuple(pop.titles))
            if key in done:
                continue
            done.add(key)
            layout = getattr(game, pop.layout)
            nodes = "+".join(pop.nodes)
            if len(pop.worst.encode("ascii", "replace")) > POPUP_TEXT_MAX:
                problems.append(f"{game.name}: the popup of {nodes} is longer than {POPUP_TEXT_MAX} bytes "
                                "with the longest names")
                continue
            if scrolling:
                continue
            pages, why = paginate(layout, widest_title(g, pop.titles, layout, game), pop.worst,
                                  (REFUSAL_LINES if pop.effects else 0) + pop.room)
            if why:
                problems.append(f"{game.name}: the popup of {nodes} runs off the screen without scrolling: {why}")
            elif len(pages) > MAX_PAGES:
                problems.append(f"{game.name}: the popup of {nodes} takes {len(pages)} pages; at most {MAX_PAGES}")
    return problems


def title_problems(g: dict, title: str, what: str) -> list[str]:
    """A title's problems (the event's, or a node's popup title, cie-v6-binary.md 5 and 14) in every game of `g`."""
    v6 = g["version"] >= VERSION_V6
    out: list[str] = []
    if not v6:
        if len(title) > TITLE_BYTES:
            out.append(f"{what} is longer than {TITLE_BYTES} characters")
        if PLACEHOLDER_RE.search(title):
            out.append(f"{what} has no placeholders")
        if not all(text_char_ok(c) and c != "\n" for c in title):
            out.append(f"{what} has characters the game cannot show")
        for gn in g["games"]:
            if len(title) > GAMES[gn].title_width:
                out.append(f"{GAMES[gn].name}: {what} is longer than its {GAMES[gn].title_width} characters")
        return out
    # Version 6 (sections 5, 14, 17): placeholders allowed; the rest as before.
    bad = False
    for kind, raw in text_tokens(title):
        if kind == "lit":
            bad = bad or not all((text_char_ok(c) or c == "\"") and c not in "\n(){}\\|@" for c in raw)
        elif kind != "ph":
            out.append(f"{what} holds placeholders only, not {raw}")
        else:
            p = parse_placeholder_v6(raw[1:-1], g["roles"])
            if p is None or p.role is None:
                out.append(f"{what}: {raw} is not a placeholder a title can show")
            elif any(g["roles"].get(m, {}).get("optional") for m in [p.role] + members_of(g["roles"], p.role)):
                out.append(f"{what}: {raw} names {p.role}, who may not be bound")
            elif p.what == "name" and g["roles"][p.role]["kind"] == "stranger" and not g["roles"][p.role].get("named"):
                out.append(f"{what}: {raw}: a stranger has no name")
    if bad:
        out.append(f"{what} has characters the game cannot show")
    if len(title) > LABEL_BYTES_V6:
        out.append(f"{what} is longer than {LABEL_BYTES_V6} characters as written")   # the .cieg's raw title
    if out:
        return out
    for gn in g["games"]:
        game = GAMES[gn]
        worst = worst_v6(title, g, game, None)
        if title_fits(gn, worst) or title_fits(gn, worst_v6(title, g, game, None, pronoun_names=True)):
            continue
        if len(worst) > TITLE_BYTES:
            out.append(f"{what} is longer than {TITLE_BYTES} characters" + (" with the longest names"
                                                                            if worst != title else ""))
        elif gn in TITLE_BOX_PX:
            out.append(f"{game.name}: {what} is {title_px(gn, worst)} pixels wide; its popup shows "
                       f"{TITLE_BOX_PX[gn]}")
        else:
            out.append(f"{game.name}: {what} is longer than its {game.title_width} characters")
    return out


def title_fits(game: int, text: str) -> bool:
    """A version 6 title as shown fits the game (cie-v6-binary.md 5 and 17)."""
    if len(text) > TITLE_BYTES:
        return False
    return title_px(game, text) <= TITLE_BOX_PX[game] if game in TITLE_BOX_PX else len(text) <= GAMES[game].title_width


def title_worst(g: dict, title: str, game: "Game") -> str:
    """A title at its widest as the game shows it: with the longest names when that fits, else with the names as
    pronouns (section 17)."""
    if g["version"] < VERSION_V6:
        return title
    worst = worst_v6(title, g, game, None)
    return worst if title_fits(game.number, worst) else worst_v6(title, g, game, None, pronoun_names=True)


def title_shown(g: dict, title: str, game: int, bindings: dict, aliases: dict | None = None,
                unicode: bool = False) -> str:
    """A title as the player reads it (section 17): the real names, else -- when that does not fit -- pronouns."""
    real = expand_v6(title, g, bindings, None, None, game, unicode, aliases)
    if title_fits(game, real):
        return real
    return expand_v6(title, g, bindings, None, None, game, unicode, aliases, pronoun_names=True)


_READ_PRONOUN = {k: f"{a} or {b}" for k, (a, b) in PRONOUNS_V6.items()}
_READ_PRONOUN["woman/man"] = "woman or man"


def readable_title(title: str) -> str:
    """A title's readable form (section 17) for the log, Pick Island Event and the library: each name as
    "someone", each pronoun as "he or she" ..., in the case written; at most TITLE_BYTES."""
    def one(m: re.Match) -> str:
        token = m.group(1).partition("|")[0]
        word = token.rpartition(".")[2]
        out = _READ_PRONOUN.get(word.lower(), "someone")
        upper = sum(c.isalpha() for c in token) >= 2 and not any(c.islower() for c in token)
        if upper:
            return out.upper()
        return out[0].upper() + out[1:] if word[:1].isupper() else out
    return PLACEHOLDER_RE.sub(one, title)[:TITLE_BYTES]


def widest_title(g: dict, titles: Iterable[str], layout: "Layout", game: "Game") -> str:
    """Of the titles in force on a popup ("" = the event's own), the one whose worst case wraps into the most
    lines at the layout's width (the first on a tie): the popup is paged with it (cie-v6-binary.md 14)."""
    best, most = g["title"], -1
    for t in titles or [""]:
        t = title_worst(g, t or g["title"], game)     # 17: at its widest as shown
        n = len(wrap(t, layout.width))
        if n > most:
            best, most = t, n
    return best


def validate(data: Any, scrolling: bool = False, shared_pools: Any = None) -> tuple[dict, list[str]]:
    """(the normalized graph, every problem).  No problems = the graph may be compiled and played."""
    g, problems = normalize(data, shared_pools)
    if problems and not g.get("nodes"):
        return g, problems
    v6 = g["version"] >= VERSION_V6
    nodes = g["nodes"]
    if g["start"] not in nodes:
        problems.append(f"start {g['start']!r} names no node")
    for nid, n in nodes.items():
        for t in _edges(n):
            if t not in nodes:
                problems.append(f"node {nid}: {t!r} names no node")
        refs: list[tuple[str, str]] = []
        for v in n["variants"]:
            _cond_refs(v["if"], refs)
        for c in n["children"]:
            _cond_refs(c["if"], refs)
        for c in n["choices"] if v6 else ():
            _cond_refs(c.get("if"), refs)
        _check_refs(g, f"node {nid}", refs, problems)
        if n["type"] != "branch":
            _check_text(f"node {nid}", n["text"], problems, g["version"], g)
            for i, v in enumerate(n["variants"]):
                _check_text(f"node {nid} variant {i + 1}", v["text"], problems, g["version"], g)
    if v6:
        _validate_v6(g, problems)
    if problems:
        return g, problems

    # No cycle (a DAG): depth first, grey = on the stack.
    colour: dict[str, int] = {}

    def dfs(nid: str, stack: list[str]) -> None:
        colour[nid] = 1
        for t in _edges(nodes[nid]):
            if colour.get(t) == 1:
                cyc = stack[stack.index(t):] + [nid, t] if t in stack else [nid, t]
                problems.append(f"a cycle: {' > '.join(cyc)}")
            elif t not in colour:
                dfs(t, stack + [nid])
        colour[nid] = 2

    dfs(g["start"], [])
    for nid in nodes:
        if nid not in colour:
            problems.append(f"node {nid} is never reached from start")
    if problems:
        return g, problems

    # The title and the labels, in every game.
    lg_labels = lower(g) if v6 else None
    problems.extend(title_problems(g, g["title"], "the title"))
    for nid, n in nodes.items():
        if n.get("title"):
            problems.extend(title_problems(g, n["title"], f"node {nid}: its popup title"))
    for gn in g["games"]:
        game = GAMES[gn]
        for nid, n in nodes.items():
            for c in n["choices"]:
                if v6:
                    label = worst_v6(c["label"], lg_labels, game, None)
                    if not label_fits(gn, label):
                        # Section 15: the engine shows the names as pronouns when they do not fit.
                        fallback = worst_v6(c["label"], lg_labels, game, None, pronoun_names=True)
                        if label_fits(gn, fallback):
                            continue
                    if len(label) > LABEL_BYTES_V6:
                        problems.append(f"{game.name}: the label {c['label']!r} is {len(label)} characters with "
                                        f"the longest names; at most {LABEL_BYTES_V6}")
                    elif label_px(gn, label) > label_max_px(gn):
                        problems.append(f"{game.name}: the label {c['label']!r} runs off the screen with the "
                                        f"longest names ({label_px(gn, label)} of {label_max_px(gn)} pixels)")
                    continue
                label = worst_case(c["label"], game, None)
                if len(label) > min(game.label_width, BUTTON_BYTES):
                    problems.append(f"{game.name}: the label {c['label']!r} is {len(label)} characters with the "
                                    f"longest names; at most {min(game.label_width, BUTTON_BYTES)}")
                elif label_px(gn, label) > label_max_px(gn):
                    problems.append(f"{game.name}: the label {c['label']!r} runs off the screen with the longest "
                                    f"names ({label_px(gn, label)} of {label_max_px(gn)} pixels)")
    for nid, n in nodes.items():
        for c in n["choices"]:
            _check_text(f"node {nid} label", c["label"], problems, g["version"], g, label=True)
            if "\n" in c["label"]:
                problems.append(f"node {nid}: a label is one line")
            phs = placeholders_v6(c["label"], g["roles"]) if v6 else placeholders(c["label"])
            for raw, p in phs:
                if p is None or p.what in ("award", "award_unit") or (p.role and p.role not in g["roles"]):
                    problems.append(f"node {nid}: the label's {raw} is not a placeholder a label can show")
                elif g["roles"][p.role].get("optional"):
                    problems.append(f"node {nid}: the label's {raw} names {p.role}, who may not be bound")

    # Every history in every context.
    for ctx in contexts(g):
        paths = walk(g, ctx, problems)
        problems.extend(x for x in fit_problems(g, paths, scrolling) if x not in problems)
    return g, problems


def load(path_or_data: Any, scrolling: bool = False, shared_pools: Any = None) -> dict:
    """The normalized graph from a file (or parsed JSON); GraphError when it does not pass."""
    data = path_or_data
    if isinstance(path_or_data, (str, Path)):
        data = json.loads(Path(path_or_data).read_text(encoding="utf-8"))
    g, problems = validate(data, scrolling, shared_pools)
    if problems:
        raise GraphError(problems)
    return g


# ---- The binary .cieg ----------------------------------------------------------------------------------------------

_HEADER = struct.Struct("<4sHHIII HHH HHHHHHHH H IIIIIIII I")
_ROLE = struct.Struct("<BBBBHH")
_NODE = struct.Struct("<BBBBHHHHHHHHHHHH")
_CHILD = struct.Struct("<HHHHHH")
_EFFECT = struct.Struct("<BBBBiiHH")
_COND = struct.Struct("<BBHHH")
_VARIANT = struct.Struct("<HH")
_PATCH = struct.Struct("<H")
assert _HEADER.size == 80 and _ROLE.size == 8 and _NODE.size == 28 and _CHILD.size == 12
assert _EFFECT.size == 16 and _COND.size == 8 and _VARIANT.size == 4


_HEADER6 = struct.Struct("<4sHHIII HHH HHHHHHHH H IIIIIIII II HH HH I")
_ROLE6 = struct.Struct("<BBBBHBB BBHBBH")
_POOL = struct.Struct("<HHHBBHH")       # G3: + the distinct_from string, + 0
_ITEM = struct.Struct("<HHHH")
assert _HEADER6.size == HEADER_BYTES_V6 and _ROLE6.size == 16 and _POOL.size == 12 and _ITEM.size == 8
ROLE_FLAG_SAID_EXCLUDE = 64   # the author wrote protected "exclude" (decompiling only; the engine reads 32)
ROLE_FLAG_SAID_ALLOW = 128    # the author wrote protected "allow"


def _compile_v6(g: dict) -> bytes:
    """A version 6 graph's .cieg (docs/event-collection/cie-v6-binary.md)."""
    lg = lower(g)
    harm = set(lg["harm"])
    strings: list[str] = []
    sidx: dict[str, int] = {}

    def s(text: str | None) -> int:
        if text is None or text == "":
            return NONE
        if text not in sidx:
            text.encode("ascii")
            sidx[text] = len(strings)
            strings.append(text)
        return sidx[text]

    role_ids = list(lg["roles"])
    node_ids = list(lg["nodes"])
    nidx = {n: i for i, n in enumerate(node_ids)}
    ridx = {r: i for i, r in enumerate(role_ids)}
    pidx = {p: i for i, p in enumerate(lg["patches"])}
    conds: list[bytes | None] = []

    def cond(c: Any) -> int:
        if c is None:
            return NONE
        at = len(conds)
        conds.append(None)
        _fill(at, c)
        return at

    def _fill(at: int, c: Any) -> None:
        (op, arg), = c.items()
        code = COND_CODES[op]
        if op == "visited":
            conds[at] = _COND.pack(code, 0, nidx[arg], 0, 0)
        elif op in ("role", "harmable"):
            conds[at] = _COND.pack(code, 0, ridx[arg], 0, 0)
        elif op == "game":
            conds[at] = _COND.pack(code, 0, sum(1 << (x - 1) for x in arg), 0, 0)
        elif op == "patch":
            conds[at] = _COND.pack(code, 0, pidx[arg], 0, 0)
        elif op == "special_present":
            conds[at] = _COND.pack(code, 0, PRESENT_CODES[arg], 0, 0)
        elif op in ("min_population", "min_children"):
            conds[at] = _COND.pack(code, 0, arg, 0, 0)
        elif op == "not":
            conds[at] = _COND.pack(code, 1, cond(arg), 0, 0)
        else:
            first = len(conds)
            conds.extend([None] * len(arg))
            conds[at] = _COND.pack(code, len(arg), first, 0, 0)
            for k, x in enumerate(arg):
                _fill(first + k, x)

    roles = b""
    for r in role_ids:
        v = lg["roles"][r]
        if v["kind"] == "stranger":
            roles += _ROLE6.pack(1, 1 if v.get("named") else 0, SEX_CODES[v["sex"]], 0, s(r), 0, 0, 0, 0, NONE, 0,
                                 0, 0)
        elif v["kind"] == "alias":
            mask = sum(1 << ridx[m] for m in v["of"])
            roles += _ROLE6.pack(2, ROLE_FLAG_HARM if r in harm else 0, 0, 0, s(r), 0, 0, 0, 0, NONE, 0, 0, mask)
        elif v["kind"] == "other":
            roles += _ROLE6.pack(3, ROLE_FLAG_HARM if r in harm else 0, 0, 0, s(r), 0, 0, 0, 0, NONE, 0, 0,
                                 1 << ridx[v["of"]])
        else:
            protect = protect_excluded(g, r, harm)
            flags = (1 if v["optional"] else 0) | (6 if protect else 0) | (8 if v["believers_only"] else 0) \
                | (ROLE_FLAG_HARM if r in harm else 0) | (ROLE_FLAG_PROTECT if protect else 0) \
                | {"auto": 0, "exclude": ROLE_FLAG_SAID_EXCLUDE, "allow": ROLE_FLAG_SAID_ALLOW}[v["protected"]]
            gap = v.get("max_age_gap")
            sk = v["skill"]
            roles += _ROLE6.pack(0, flags, SEX_CODES[v["sex"]], v["min_age"], s(r),
                                 ridx[gap["role"]] + 1 if gap else 0, gap["years"] if gap else 0,
                                 v["max_age"] or 0, SPECIAL_CODES.get(v["special"], 0),
                                 s(",".join(sk["names"])) if sk else NONE, sk["min"] if sk else 0,
                                 PICK_CODES[sk["pick"]] if sk else 0, 0)
    nodes = children = effects = variants = b""
    n_child = n_effect = n_variant = 0
    for nid in node_ids:
        n = lg["nodes"][nid]
        v_first, c_first, e_first = n_variant, n_child, n_effect
        for v in n["variants"]:
            variants += _VARIANT.pack(cond(v["if"]), s(v["text"]))
            n_variant += 1
        for c in n["choices"]:
            children += _CHILD.pack(nidx[c["next"]], 1, cond(c.get("if")), NONE, s(c["label"]), NONE)
            n_child += 1
        for c in n["children"]:
            children += _CHILD.pack(nidx[c["next"]], c["weight"], cond(c["if"]),
                                    nidx[c["else"]] if c["else"] else NONE, NONE, cond(c.get("guard")))
            n_child += 1
        for e in n["effects"]:
            do = e["do"]
            code = EFFECT_CODES["skill_set" if do == "skill" and "set" in e else do]
            r = effect_role(e)
            role = ridx[r] if r is not None else 0xFF
            flags, a, b, st = 0, 0, 0, NONE
            if do in ("food", "tech"):
                flags, a = (1 if e["scaled"] else 0) | (2 if e["defer"] else 0), e["amount"]
                b = e.get("max") or 0
                if e.get("per_game"):
                    st = s(per_game_text(e["per_game"]))
            elif do == "kill":
                st = s(e["cause"])
            elif do == "status":
                a = STATUS_CODES[e["status"]]
            elif do in ("health", "health_change", "damage"):
                a, b = e["min"], e["max"]
                if do == "damage":
                    st = s(DAMAGE_ANY if e["structures"] == DAMAGE_ANY else ",".join(e["structures"]))
            elif do == "preference":
                flags, st = (4 if e["list"] == "dislikes" else 0), s(e["preference"])
            elif do == "skill" and "set" in e:
                a, st = e["set"], s(",".join(e["skills"]))
            elif do == "skill":
                a, b, st = e["min"], e["max"], s(",".join(e["skills"]))
            elif do == "action":
                st = s(e["action"])
            elif do == "mood":
                a = 1 if e["mood"] == "good" else -1
            effects += _EFFECT.pack(code, role, flags, 0, a, b, st, 0)
            n_effect += 1
        nodes += _NODE.pack(NODE_TYPES.index(n["type"]), 1 if n["popup"] == "append" else 0,
                            1 if n["join"] == "paragraph" else 0, 0, s(nid), s(n["text"]),
                            v_first if n["variants"] else NONE, len(n["variants"]),
                            c_first, n_child - c_first, nidx[n["else"]] if n["else"] else NONE,
                            e_first if n["effects"] else NONE, len(n["effects"]), s(n["summary"]),
                            s(n["outcome"]), s(n.get("title")))
    patches = b"".join(_PATCH.pack(s(p)) for p in lg["patches"])
    pools = items = b""
    n_item = 0
    for name, p in lg["pools"].items():
        pools += _POOL.pack(s(name), n_item, len(p["items"]), 1 if p["distinct"] else 0, 0,
                            s(",".join(p.get("distinct_from") or [])), 0)
        for it in p["items"]:
            items += _ITEM.pack(s(it["text"]), it["weight"], cond(it["if"]), 0)
            n_item += 1
    title = s(lg["title"])
    req_puzzles = [(int(gn), name) for gn, names in lg["requirement"].get("puzzles", {}).items() for name in names]
    req_if = lg["requirement"].get("if")
    requirement = NONE
    if req_puzzles or req_if is not None:
        requirement = len(conds)
        count = len(req_puzzles) + (1 if req_if is not None else 0)
        conds.append(_COND.pack(COND_CODES["all"], count, requirement + 1, 0, 0))
        conds.extend([None] * count)
        for k, (gn, name) in enumerate(req_puzzles):
            conds[requirement + 1 + k] = _COND.pack(COND_PUZZLE, 0, s(name), gn, 0)
        if req_if is not None:
            _fill(requirement + 1 + len(req_puzzles), req_if)
    col = NONE
    if "collection" in lg:
        col = s(json.dumps(lg["collection"], ensure_ascii=True, separators=(",", ":")))
    blob = b""
    offsets = []
    for t in strings:
        offsets.append(len(blob))
        blob += t.encode("ascii") + b"\0"
    for count in (len(role_ids), len(node_ids), n_child, n_effect, len(conds), n_variant, len(strings),
                  len(lg["pools"]), n_item):
        if count >= NONE:
            raise GraphError(["the graph is too big for the .cieg format"])
    sections = [roles, nodes, children, effects, b"".join(conds), variants, patches, pools, items,
                b"".join(struct.pack("<I", o) for o in offsets) + blob]
    at = _HEADER6.size
    offs = []
    for sec in sections:
        offs.append(at)
        at += len(sec)
    head = _HEADER6.pack(BINARY_MAGIC, VERSION_V6, _HEADER6.size, at, 0,
                         sum(1 << (x - 1) for x in lg["games"]), title, nidx[lg["start"]],
                         lg["requirement"]["min_eligible"], len(role_ids), len(node_ids), n_child, n_effect,
                         len(conds), n_variant, len(strings), len(lg["patches"]), requirement,
                         offs[0], offs[1], offs[2], offs[3], offs[4], offs[5], offs[6], offs[9],
                         offs[7], offs[8], len(lg["pools"]), n_item, 1, col, 0)
    data = bytearray(head + b"".join(sections))
    struct.pack_into("<I", data, 12, zlib.crc32(bytes(data)))
    return bytes(data)


def _decompile_v6(data: bytes) -> dict:
    h = _HEADER6.unpack_from(data, 0)
    (_magic, version, _hsize, _fsize, _crc, games_mask, title, start, min_el, n_role, n_node, n_child, n_effect,
     _n_cond, n_variant, n_string, n_patch, req_cond, o_role, o_node, o_child, o_effect, o_cond, o_variant, o_patch,
     o_string, o_pool, o_item, n_pool, _n_item, _flags, col, _z) = h
    offs = [struct.unpack_from("<I", data, o_string + 4 * i)[0] for i in range(n_string)]
    base = o_string + 4 * n_string

    def s(i: int) -> str:
        if i == NONE:
            return ""
        start_ = base + offs[i]
        return data[start_:data.index(b"\0", start_)].decode("ascii")

    roles_raw = [_ROLE6.unpack_from(data, o_role + i * _ROLE6.size) for i in range(n_role)]
    role_ids = [s(r[4]) for r in roles_raw]
    nodes_raw = [_NODE.unpack_from(data, o_node + i * _NODE.size) for i in range(n_node)]
    node_ids = [s(n[4]) for n in nodes_raw]
    patches = [s(_PATCH.unpack_from(data, o_patch + i * 2)[0]) for i in range(n_patch)]
    sex_names = {v: k for k, v in SEX_CODES.items()}
    code_cond = {v: k for k, v in COND_CODES.items()}
    code_effect = {v: k for k, v in EFFECT_CODES.items()}
    code_status = {v: k for k, v in STATUS_CODES.items()}
    code_special = {v: k for k, v in SPECIAL_CODES.items()}
    code_present = {v: k for k, v in PRESENT_CODES.items()}
    code_pick = {v: k for k, v in PICK_CODES.items()}

    def cond(i: int) -> Any:
        if i == NONE:
            return None
        op, count, a, _b, _ = _COND.unpack_from(data, o_cond + i * _COND.size)
        name = code_cond[op]
        if name == "visited":
            return {name: node_ids[a]}
        if name in ("role", "harmable"):
            return {name: role_ids[a]}
        if name == "game":
            return {name: [x for x in range(1, 6) if a & (1 << (x - 1))]}
        if name == "patch":
            return {name: patches[a]}
        if name == "special_present":
            return {name: code_present[a]}
        if name in ("min_population", "min_children"):
            return {name: a}
        if name == "not":
            return {name: cond(a)}
        return {name: [cond(a + k) for k in range(count)]}

    roles: dict[str, dict] = {}
    for rid, raw in zip(role_ids, roles_raw):
        kind, flags, sex, min_age, _sid, gap_role, gap_years, max_age, special, skills, smin, pick, mask = raw
        if kind == 1:
            roles[rid] = {"kind": "stranger", "sex": sex_names[sex]}
            if flags & 1:
                roles[rid]["named"] = True
        elif kind == 2:
            roles[rid] = {"kind": "alias", "of": [role_ids[k] for k in range(n_role) if mask & (1 << k)]}
        elif kind == 3:
            roles[rid] = {"kind": "other", "of": next(role_ids[k] for k in range(n_role) if mask & (1 << k))}
        else:
            said = "exclude" if flags & ROLE_FLAG_SAID_EXCLUDE else "allow" if flags & ROLE_FLAG_SAID_ALLOW \
                else "auto"
            roles[rid] = {"kind": "villager", "optional": bool(flags & 1), "sex": sex_names[sex], "min_age": min_age,
                          "max_age": max_age or None,
                          "skill": {"names": s(skills).split(","), "min": smin, "pick": code_pick[pick]}
                          if skills != NONE else None,
                          "special": code_special.get(special), "protected": said,
                          "believers_only": bool(flags & 8)}
            if gap_role:
                roles[rid]["max_age_gap"] = {"role": role_ids[gap_role - 1], "years": gap_years}
    nodes = {}
    for nid, n in zip(node_ids, nodes_raw):
        (t, popup, join, _p, _id, text, v_first, v_count, c_first, c_count, els, e_first, e_count, summary,
         outcome, ntitle) = n
        typ = NODE_TYPES[t]
        variants = []
        for k in range(v_count):
            vc, vt = _VARIANT.unpack_from(data, o_variant + (v_first + k) * _VARIANT.size)
            variants.append({"if": cond(vc), "text": s(vt)})
        kids, choices = [], []
        for k in range(c_count):
            nxt, w, cc, ce, label, _guard = _CHILD.unpack_from(data, o_child + (c_first + k) * _CHILD.size)
            if typ == "question":
                choices.append({"label": s(label), "next": node_ids[nxt], "if": cond(cc)})
            else:
                kids.append({"next": node_ids[nxt], "weight": w, "if": cond(cc),
                             "else": node_ids[ce] if ce != NONE else None})
        effects = []
        for k in range(e_count):
            code, role, flags, _q, a, b, st, _ = _EFFECT.unpack_from(data, o_effect + (e_first + k) * _EFFECT.size)
            do = code_effect[code]
            e: dict[str, Any] = {"do": "skill" if do == "skill_set" else do}
            if do in ("food", "tech"):
                e.update(amount=a, scaled=bool(flags & 1), defer=bool(flags & 2))
                if b:
                    e["max"] = b
                if st != NONE:
                    e["per_game"] = per_game_parse(s(st))
            elif do == "celebrate":
                e["who"] = "all" if role == 0xFF else role_ids[role]
            elif do == "damage":
                words = s(st)
                e.update(structures=DAMAGE_ANY if words == DAMAGE_ANY else words.split(","), min=a, max=b)
            elif do != "pay_award":
                e["role"] = role_ids[role]
                if do == "kill":
                    e["cause"] = s(st)
                elif do == "status":
                    e["status"] = code_status[a]
                elif do in ("health", "health_change"):
                    e.update(min=a, max=b)
                elif do == "preference":
                    e.update(list="dislikes" if flags & 4 else "likes", preference=s(st))
                elif do == "skill":
                    e.update(skills=s(st).split(","), min=a, max=b)
                elif do == "skill_set":
                    e.update(skills=s(st).split(","), set=a)
                elif do == "action":
                    e["action"] = s(st)
                elif do == "mood":
                    e["mood"] = "good" if a > 0 else "bad"
            effects.append(e)
        nodes[nid] = {"type": typ, "popup": "append" if popup else "new", "join": "paragraph" if join else "space",
                      "text": s(text), "variants": variants, "effects": effects, "children": kids,
                      "choices": choices, "else": node_ids[els] if els != NONE else None, "summary": s(summary),
                      "outcome": s(outcome)}
        if ntitle != NONE:
            nodes[nid]["title"] = s(ntitle)
    requirement: dict[str, Any] = {"min_eligible": min_el}
    if req_cond != NONE:
        _op, count, first, _b, _ = _COND.unpack_from(data, o_cond + req_cond * _COND.size)
        puzzles: dict[str, list[str]] = {}
        req_if = None
        for k in range(count):
            op, _c, name, gn, _ = _COND.unpack_from(data, o_cond + (first + k) * _COND.size)
            if op == COND_PUZZLE:
                puzzles.setdefault(str(gn), []).append(s(name))
            else:
                req_if = cond(first + k)
        if puzzles:
            requirement["puzzles"] = {k: puzzles[k] for k in sorted(puzzles)}
        if req_if is not None:
            requirement["if"] = req_if
    pools: dict[str, dict] = {}
    for i in range(n_pool):
        name, first, count, pflags, _, frm, _z = _POOL.unpack_from(data, o_pool + i * _POOL.size)
        its = []
        for k in range(count):
            it, w, c, _ = _ITEM.unpack_from(data, o_item + (first + k) * _ITEM.size)
            its.append({"text": s(it), "weight": w, "if": cond(c)})
        pools[s(name)] = {"items": its, "distinct": bool(pflags & 1)}
        if frm != NONE:
            pools[s(name)]["distinct_from"] = s(frm).split(",")
    lg = {"format": FORMAT, "version": version, "title": s(title),
          "games": [x for x in range(1, 6) if games_mask & (1 << (x - 1))], "patches": patches,
          "requirement": requirement, "roles": roles, "start": node_ids[start], "nodes": nodes, "pools": pools}
    if col != NONE:
        lg["collection"] = json.loads(s(col))
    return lift(lg)


def compile_graph(g: dict) -> bytes:
    """The .cieg of a normalized, validated graph (load())."""
    if g.get("version", 1) >= VERSION_V6:
        return _compile_v6(g)
    strings: list[str] = []
    sidx: dict[str, int] = {}

    def s(text: str | None) -> int:
        if text is None or text == "":
            return NONE
        if text not in sidx:
            text.encode("ascii")
            sidx[text] = len(strings)
            strings.append(text)
        return sidx[text]

    role_ids = list(g["roles"])
    node_ids = list(g["nodes"])
    nidx = {n: i for i, n in enumerate(node_ids)}
    ridx = {r: i for i, r in enumerate(role_ids)}
    pidx = {p: i for i, p in enumerate(g["patches"])}
    conds: list[bytes | None] = []

    def cond(c: Any) -> int:
        if c is None:
            return NONE
        at = len(conds)
        conds.append(None)
        _fill(at, c)
        return at

    def _fill(at: int, c: Any) -> None:
        (op, arg), = c.items()
        code = COND_CODES[op]
        if op == "visited":
            conds[at] = _COND.pack(code, 0, nidx[arg], 0, 0)
        elif op == "role":
            conds[at] = _COND.pack(code, 0, ridx[arg], 0, 0)
        elif op == "game":
            conds[at] = _COND.pack(code, 0, sum(1 << (x - 1) for x in arg), 0, 0)
        elif op == "patch":
            conds[at] = _COND.pack(code, 0, pidx[arg], 0, 0)
        elif op == "not":
            conds[at] = _COND.pack(code, 1, cond(arg), 0, 0)
        else:
            first = len(conds)
            conds.extend([None] * len(arg))             # the operands, consecutive
            conds[at] = _COND.pack(code, len(arg), first, 0, 0)
            for k, x in enumerate(arg):
                _fill(first + k, x)

    roles = b""
    for r in role_ids:
        v = g["roles"][r]
        if v["kind"] == "stranger":
            roles += _ROLE.pack(1, 0, SEX_CODES[v["sex"]], 0, s(r), 0)
        else:
            flags = (1 if v["optional"] else 0) | (2 if v["exclude_nursing"] else 0) | \
                (4 if v["exclude_special"] else 0) | (8 if v["believers_only"] else 0)
            gap = v.get("max_age_gap")
            extra = (ridx[gap["role"]] + 1) | (gap["years"] << 8) if gap else 0
            roles += _ROLE.pack(0, flags, SEX_CODES[v["sex"]], v["min_age"], s(r), extra)
    nodes = children = effects = variants = b""
    n_child = n_effect = n_variant = 0
    for nid in node_ids:
        n = g["nodes"][nid]
        v_first, c_first, e_first = n_variant, n_child, n_effect
        for v in n["variants"]:
            variants += _VARIANT.pack(cond(v["if"]), s(v["text"]))
            n_variant += 1
        for c in n["choices"]:
            children += _CHILD.pack(nidx[c["next"]], 1, NONE, NONE, s(c["label"]), 0)
            n_child += 1
        for c in n["children"]:
            children += _CHILD.pack(nidx[c["next"]], c["weight"], cond(c["if"]),
                                    nidx[c["else"]] if c["else"] else NONE, NONE, 0)
            n_child += 1
        for e in n["effects"]:
            do = e["do"]
            role = ridx.get(e.get("role", ""), 0xFF) if do in VILLAGER_EFFECTS else 0xFF
            flags, a, b, st = 0, 0, 0, NONE
            if do in ("food", "tech"):
                flags, a = (1 if e["scaled"] else 0) | (2 if e["defer"] else 0), e["amount"]
                b = e.get("max") or 0       # version 3: a range's top (0: the amount alone)
                if e.get("per_game"):
                    st = s(per_game_text(e["per_game"]))     # version 5: each game's own amount or range
            elif do == "kill":
                st = s(e["cause"])
            elif do == "status":
                a = STATUS_CODES[e["status"]]
            elif do == "health":
                a, b = e["min"], e["max"]
            elif do == "preference":
                flags, st = (4 if e["list"] == "dislikes" else 0), s(e["preference"])
            elif do == "skill":
                a, b, st = e["min"], e["max"], s(",".join(e["skills"]))
            effects += _EFFECT.pack(EFFECT_CODES[do], role, flags, 0, a, b, st, 0)
            n_effect += 1
        nodes += _NODE.pack(NODE_TYPES.index(n["type"]), 1 if n["popup"] == "append" else 0,
                            1 if n["join"] == "paragraph" else 0, 0, s(nid), s(n["text"]),
                            v_first if n["variants"] else NONE, len(n["variants"]),
                            c_first, n_child - c_first, nidx[n["else"]] if n["else"] else NONE,
                            e_first if n["effects"] else NONE, len(n["effects"]), s(n["summary"]),
                            s(n["outcome"]), 0)
    patches = b"".join(_PATCH.pack(s(p)) for p in g["patches"])
    title = s(g["title"])
    # Version 3: the requirement's puzzles, one ALL condition over puzzle conditions (a = the name, b = the game).
    requirement = NONE if g.get("version", 1) >= 3 else 0
    req_puzzles = [(int(gn), name) for gn, names in g["requirement"].get("puzzles", {}).items() for name in names]
    if req_puzzles:
        requirement = len(conds)
        conds.append(_COND.pack(COND_CODES["all"], len(req_puzzles), requirement + 1, 0, 0))
        for gn, name in req_puzzles:
            conds.append(_COND.pack(COND_PUZZLE, 0, s(name), gn, 0))
    blob = b""
    offsets = []
    for t in strings:
        offsets.append(len(blob))
        blob += t.encode("ascii") + b"\0"
    for count in (len(role_ids), len(node_ids), n_child, n_effect, len(conds), n_variant, len(strings)):
        if count >= NONE:
            raise GraphError(["the graph is too big for the .cieg format"])
    sections = [roles, nodes, children, effects, b"".join(conds), variants, patches,
                b"".join(struct.pack("<I", o) for o in offsets) + blob]
    at = _HEADER.size
    offs = []
    for sec in sections:
        offs.append(at)
        at += len(sec)
    version = g.get("version", 1)          # each version's own number (1 and 2 byte for byte as before)
    head = _HEADER.pack(BINARY_MAGIC, version, _HEADER.size, at, 0,
                        sum(1 << (x - 1) for x in g["games"]), title, nidx[g["start"]],
                        g["requirement"]["min_eligible"], len(role_ids), len(node_ids), n_child, n_effect,
                        len(conds), n_variant, len(strings), len(g["patches"]), requirement, *offs, 0)
    data = bytearray(head + b"".join(sections))
    struct.pack_into("<I", data, 12, zlib.crc32(bytes(data)))
    return bytes(data)


def without_names(g: dict) -> dict:
    """`g` without its parts' names: what a .cieg holds of it (the names are the editor's, never compiled)."""
    out = copy.deepcopy(g)
    out.pop("grammar_fixes", None)
    for n in out.get("nodes", {}).values():
        for k in AUTHORING_KEYS:
            n.pop(k, None)
        for x in n.get("variants", []) + n.get("choices", []) + n.get("effects", []):
            x.pop("src", None)
    for p in out.get("pools", {}).values():
        p.pop("src", None)
        for it in p["items"]:
            it.pop("src", None)
    return out


def decompile_graph(data: bytes) -> dict:
    """The normalized graph a .cieg holds (what compile_graph was given, without its parts' names); GraphError when
    the file is damaged."""
    if len(data) < _HEADER.size:
        raise GraphError(["the file is shorter than a .cieg header"])
    h = _HEADER.unpack_from(data, 0)
    (magic, version, hsize, fsize, crc, games_mask, title, start, min_el, n_role, n_node, n_child, n_effect, n_cond,
     n_variant, n_string, n_patch, req_cond, o_role, o_node, o_child, o_effect, o_cond, o_variant, o_patch, o_string,
     _z2) = h
    want = HEADER_BYTES_V6 if version >= VERSION_V6 else _HEADER.size
    if magic != BINARY_MAGIC or version not in VERSIONS or hsize != want or fsize != len(data) or len(data) < want:
        raise GraphError(["not a version 1 to 6 .cieg file"])
    check = bytearray(data)
    struct.pack_into("<I", check, 12, 0)
    if zlib.crc32(bytes(check)) != crc:
        raise GraphError(["the .cieg file is damaged (checksum)"])
    if version >= VERSION_V6:
        return _decompile_v6(data)
    offs = [struct.unpack_from("<I", data, o_string + 4 * i)[0] for i in range(n_string)]
    base = o_string + 4 * n_string

    def s(i: int) -> str:
        if i == NONE:
            return ""
        start_ = base + offs[i]
        return data[start_:data.index(b"\0", start_)].decode("ascii")

    roles_raw = [_ROLE.unpack_from(data, o_role + i * _ROLE.size) for i in range(n_role)]
    role_ids = [s(r[4]) for r in roles_raw]
    nodes_raw = [_NODE.unpack_from(data, o_node + i * _NODE.size) for i in range(n_node)]
    node_ids = [s(n[4]) for n in nodes_raw]
    patches = [s(_PATCH.unpack_from(data, o_patch + i * 2)[0]) for i in range(n_patch)]
    sex_names = {v: k for k, v in SEX_CODES.items()}
    code_cond = {v: k for k, v in COND_CODES.items()}
    code_effect = {v: k for k, v in EFFECT_CODES.items()}
    code_status = {v: k for k, v in STATUS_CODES.items()}

    def cond(i: int) -> Any:
        if i == NONE:
            return None
        op, count, a, _b, _ = _COND.unpack_from(data, o_cond + i * _COND.size)
        name = code_cond[op]
        if name == "visited":
            return {name: node_ids[a]}
        if name == "role":
            return {name: role_ids[a]}
        if name == "game":
            return {name: [x for x in range(1, 6) if a & (1 << (x - 1))]}
        if name == "patch":
            return {name: patches[a]}
        if name == "not":
            return {name: cond(a)}
        return {name: [cond(a + k) for k in range(count)]}

    roles = {}
    for rid, (kind, flags, sex, min_age, _sid, extra) in zip(role_ids, roles_raw):
        if kind == 1:
            roles[rid] = {"kind": "stranger", "sex": sex_names[sex]}
        else:
            roles[rid] = {"kind": "villager", "optional": bool(flags & 1), "sex": sex_names[sex], "min_age": min_age,
                          "exclude_nursing": bool(flags & 2), "exclude_special": bool(flags & 4),
                          "believers_only": bool(flags & 8)}
            if version >= 3 and extra & 0xFF:
                roles[rid]["max_age_gap"] = {"role": role_ids[(extra & 0xFF) - 1], "years": extra >> 8}
    nodes = {}
    for nid, n in zip(node_ids, nodes_raw):
        (t, popup, join, _p, _id, text, v_first, v_count, c_first, c_count, els, e_first, e_count, summary,
         outcome, _z4) = n
        typ = NODE_TYPES[t]
        variants = []
        for k in range(v_count):
            vc, vt = _VARIANT.unpack_from(data, o_variant + (v_first + k) * _VARIANT.size)
            variants.append({"if": cond(vc), "text": s(vt)})
        kids, choices = [], []
        for k in range(c_count):
            nxt, w, cc, ce, label, _ = _CHILD.unpack_from(data, o_child + (c_first + k) * _CHILD.size)
            if typ == "question":
                choices.append({"label": s(label), "next": node_ids[nxt]})
            else:
                kids.append({"next": node_ids[nxt], "weight": w, "if": cond(cc),
                             "else": node_ids[ce] if ce != NONE else None})
        effects = []
        for k in range(e_count):
            code, role, flags, _q, a, b, st, _ = _EFFECT.unpack_from(data, o_effect + (e_first + k) * _EFFECT.size)
            do = code_effect[code]
            e: dict[str, Any] = {"do": do}
            if do in ("food", "tech"):
                e.update(amount=a, scaled=bool(flags & 1), defer=bool(flags & 2))
                if b:
                    e["max"] = b
                if st != NONE:
                    e["per_game"] = per_game_parse(s(st))
            elif do in VILLAGER_EFFECTS:
                e["role"] = role_ids[role]
                if do == "kill":
                    e["cause"] = s(st)
                elif do == "status":
                    e["status"] = code_status[a]
                elif do == "health":
                    e.update(min=a, max=b)
                elif do == "preference":
                    e.update(list="dislikes" if flags & 4 else "likes", preference=s(st))
                elif do == "skill":
                    e.update(skills=s(st).split(","), min=a, max=b)
            effects.append(e)
        nodes[nid] = {"type": typ, "popup": "append" if popup else "new", "join": "paragraph" if join else "space",
                      "text": s(text), "variants": variants, "effects": effects, "children": kids,
                      "choices": choices, "else": node_ids[els] if els != NONE else None, "summary": s(summary),
                      "outcome": s(outcome)}
    requirement: dict[str, Any] = {"min_eligible": min_el}
    if version >= 3 and req_cond != NONE:
        op, count, first, _b, _ = _COND.unpack_from(data, o_cond + req_cond * _COND.size)
        puzzles: dict[str, list[str]] = {}
        for k in range(count):
            _op, _c, name, gn, _ = _COND.unpack_from(data, o_cond + (first + k) * _COND.size)
            puzzles.setdefault(str(gn), []).append(s(name))
        requirement["puzzles"] = {k: puzzles[k] for k in sorted(puzzles)}
    return {"format": FORMAT, "version": version, "title": s(title),
            "games": [x for x in range(1, 6) if games_mask & (1 << (x - 1))], "patches": patches,
            "requirement": requirement, "roles": roles, "start": node_ids[start], "nodes": nodes}


# ---- Version 6: the engine's walk, roll for roll (cie-v6-binary.md section 6) --------------------------------------


def simulate(g: dict, game: int, rolls: Iterable[int], bindings: dict[str, Binding], answers: Iterable[int] = (),
             patches: Iterable[str] = (), facts: frozenset[str] | None = None, unicode: bool = False,
             tribe: str | None = None) -> dict:
    """One run of a version 6 graph as the companion makes it, given the random stream `rolls` (each roll taken
    `% n`; none is taken for n <= 1, as ce_random_below), the villagers bound (`bindings`: role -> Binding; a
    villager role not listed is unbound; a stranger's Binding gives its sex) and the answer clicked at each
    question (its choice index).  The facts (default_facts) are taken to stay as they are for the whole run.

    Returns {"nodes", "fx" ([a, b] per effect made, as cg_roll_effect), "picks" ([pool, instance, item] in draw
    order; item None when nothing could be drawn), "aliases" ({alias: member}), "popups" (each popup's text as the
    player reads it, before paging), "rolls_used"}.  Scaling ("Island Events Scale ...") is not applied."""
    lg = lower(g)
    gm = GAMES[game]
    stream = list(rolls)
    used = [0]

    def below(n: int) -> int:
        if n <= 1:
            return 0
        if used[0] >= len(stream):
            raise IndexError("the random stream ran out")
        v = stream[used[0]]
        used[0] += 1
        return v % n

    def roll_index(weights: list[int], roll: int) -> int:
        for i, w in enumerate(weights[:-1]):
            if roll < w:
                return i
            roll -= w
        return len(weights) - 1

    roles = lg["roles"]
    bound = {r for r, v in roles.items() if v["kind"] == "stranger" or (v["kind"] == "villager" and r in bindings)}
    aliases: dict[str, str] = {}
    for a, v in roles.items():
        if v["kind"] == "alias":
            ms = [m for m in v["of"] if m in bound]
            if ms:
                aliases[a] = ms[below(len(ms))]
                bound.add(a)
    others = others_drawn(roles, aliases, bound)
    aliases.update(others)
    bound |= set(others)
    ctx = Context(game, frozenset(patches), frozenset(bound),
                  default_facts(g, bound) if facts is None else frozenset(facts),
                  frozenset(aliases.items()))

    def roll_effect(e: dict) -> list[int]:
        do = e["do"]
        if do in ("food", "tech"):
            lo, hi = e["amount"], e.get("max") or 0
            per = (e.get("per_game") or {}).get(str(game))
            if per is not None:
                lo, hi = per
                if hi == lo:
                    hi = 0
            if hi != 0:
                lo += below(hi - lo + 1)
            return [lo, 0]
        if do in ("health", "health_change", "damage"):
            return [e["min"] + below(e["max"] - e["min"] + 1), 0]
        if do == "skill":
            have = [s for s in e["skills"] if s in gm.skills]
            va = gm.skills.index(have[below(len(have))]) if have else -1
            if "set" in e:
                return [va, e["set"]]
            return [va, e["min"] + below(e["max"] - e["min"] + 1)]
        return [0, 0]

    def scan(text: str, visited: tuple, picks: list, depth: int = 0) -> None:
        for name, k in pool_refs(text):
            if any(p[0] == name and p[1] == k for p in picks) or name not in lg["pools"]:
                continue
            pool = lg["pools"][name]
            eligible = [i for i, it in enumerate(pool["items"]) if cond_holds(it["if"], ctx, visited)]
            left = eligible
            if pool["distinct"]:
                taken = {p[2] for p in picks if p[0] == name}
                left = [i for i in left if i not in taken]
            if pool.get("distinct_from"):
                # G3: never a text an instance of a listed pool has already drawn.
                seen = {lg["pools"][p[0]]["items"][p[2]]["text"] for p in picks
                        if p[0] in pool["distinct_from"] and p[2] is not None}
                left = [i for i in left if pool["items"][i]["text"] not in seen]
            eligible = left or eligible
            if not eligible:
                picks.append([name, k, None])
                continue
            weights = [pool["items"][i]["weight"] for i in eligible]
            idx = eligible[roll_index(weights, below(sum(weights)))]
            picks.append([name, k, idx])
            if depth + 1 < MAX_POOL_DEPTH + 1:
                scan(pool["items"][idx]["text"], visited, picks, depth + 1)

    def segment(start: str, path: list, picks: list) -> dict:
        h = {"nodes": [], "fx": [], "picks": []}
        nid: str | None = start
        while nid is not None:
            n = lg["nodes"][nid]
            h["nodes"].append(nid)
            visited = tuple(path + h["nodes"])
            if n["type"] != "question":
                for e in n["effects"]:
                    h["fx"].append(roll_effect(e))
            if n["type"] != "branch":
                state = picks + h["picks"]
                scan(node_text(n, ctx, visited), visited, state)
                for c in n["choices"]:
                    if cond_holds(c.get("if"), ctx, visited):
                        scan(c["label"], visited, state)
                h["picks"] = state[len(picks):]
            if n["type"] == "question":
                break
            targets, weights = [], []
            for c in n["children"]:
                if cond_holds(c["if"], ctx, visited) and cond_holds(c.get("guard"), ctx, visited):
                    targets.append(c["next"])
                elif c["else"] is not None:
                    targets.append(c["else"])
                else:
                    continue
                weights.append(c["weight"])
            if not targets:
                nid = n["else"]
                continue
            nid = targets[roll_index(weights, below(sum(weights)))]
        return h

    path: list[str] = []
    fx: list[list[int]] = []
    picks: list[list] = []
    seg = segment(lg["start"], path, picks)
    answers = list(answers)
    qi = 0
    while True:
        path += seg["nodes"]
        fx += seg["fx"]
        picks += seg["picks"]
        last = lg["nodes"][path[-1]]
        if last["type"] != "question":
            break
        visited = tuple(path)
        shown = [i for i, c in enumerate(last["choices"]) if cond_holds(c.get("if"), ctx, visited)]
        segs = {i: segment(last["choices"][i]["next"], path, picks) for i in shown}
        pick = answers[qi]
        qi += 1
        if pick not in segs:
            raise ValueError(f"answer {pick} is not shown at {path[-1]}")
        seg = segs[pick]

    # The popups, joined as walk() joins them, then read as the player reads them.
    award = None
    k = 0
    for nid in path:
        for e in lg["nodes"][nid]["effects"] if lg["nodes"][nid]["type"] != "question" else ():
            if e["do"] in ("food", "tech") and e["defer"]:
                award = (e["do"], fx[k][0])
            k += 1
    texts: list[str] = []
    titles: list[str] = []             # 14: the title each popup's first page shows
    title = lg["title"]
    room_after = False                 # the last popup was a question showing 2 to 4 buttons
    seen: tuple = ()
    for nid in path:
        n = lg["nodes"][nid]
        seen = seen + (nid,)
        if n["type"] == "branch":
            continue
        t = node_text(n, ctx, seen)
        if n["type"] == "popup" and n["popup"] == "append" and texts:
            texts[-1] = texts[-1] + (" " if n["join"] == "space" else "\n") + t if texts[-1] else t
            title = n.get("title") or title
        else:
            texts.append(t)
            if room_after and n["type"] == "popup":
                titles.append(title)   # shown in the question's own popup: its title
                title = n.get("title") or title
            else:
                title = n.get("title") or title
                titles.append(title)
        room_after = n["type"] == "question" and \
            sum(1 for c in n["choices"] if cond_holds(c.get("if"), ctx, seen)) <= MAX_ANSWERS_V4
    pick_map = {(p[0], p[1]): p[2] for p in picks if p[2] is not None}
    popups = [expand_v6(t, lg, bindings, pick_map, award, game, unicode, aliases, tribe=tribe) for t in texts]
    titles = [title_shown(lg, t, game, bindings, aliases, unicode) for t in titles]     # 17
    labels = []                        # 15: each question's shown buttons, as read
    seen = ()
    for nid in path:
        seen = seen + (nid,)
        n = lg["nodes"][nid]
        if n["type"] == "question":
            labels.append([label_shown(c["label"], lg, bindings, game, aliases, tribe, unicode, pick_map)
                           for c in n["choices"] if cond_holds(c.get("if"), ctx, seen)])
    return {"nodes": path, "fx": fx, "picks": picks, "aliases": aliases, "popups": popups, "titles": titles,
            "labels": labels, "rolls_used": used[0]}


# ---- The chances of every outcome ----------------------------------------------------------------------------------


def default_outcome(effects: list[tuple[str, dict]]) -> str:
    for _, e in effects:
        if e.get("role") == "subject":
            if e["do"] == "kill":
                return "dies"
            if e["do"] == "vanish":
                return "disappears"
            if e["do"] == "status":
                return "becomes a Heathen"
    return "lives"


def award_words(p: History) -> str:
    if p.award is None or not p.paid:
        return "nothing"
    kind, amount, _ = p.award
    if isinstance(amount, tuple):
        return f"+{amount[0]:,} to {amount[1]:,} {UNITS[kind]}"
    return f"+{amount:,} {UNITS[kind]}"


@dataclass
class Row:
    key: str
    words: str
    chance: Fraction
    by_award: dict[str, Fraction]


def chances(g: dict, game: int, patches: Iterable[str] = (), roles: Iterable[str] | None = None,
            facts: frozenset[str] | None = None) -> dict[int | None, dict[str, list[Row]]]:
    """For each question button (None without a question) -- or, when a question is asked after the start
    (version 2), each run of answers ((question, button), ...) -- "ends": each ending's chance out of every time
    those answers are given -- and "outcomes", the "In all" groups, each split by the award paid."""
    bound = frozenset(roles) if roles is not None else frozenset(g["roles"])
    ctx = Context(game, frozenset(patches), bound)
    if g.get("version", 1) >= VERSION_V6:
        bound = with_aliases(g, bound)
        ctx = Context(game, frozenset(patches), bound, default_facts(g, bound) if facts is None else facts)
    out: dict[int | None, dict[str, list[Row]]] = {}
    ends: dict[int | None, dict[str, Row]] = {}
    groups: dict[int | None, dict[str, Row]] = {}
    paths = walk(g, ctx)
    by_answers = any(q != g["start"] for p in paths for q, _b in p.answers)
    for p in paths:
        node = g["nodes"][p.end]
        aw = award_words(p)
        key = (p.answers or None) if by_answers else p.choice
        e = ends.setdefault(key, {}).setdefault(p.end, Row(p.end, node["summary"], Fraction(0), {}))
        e.chance += p.chance
        e.by_award[aw] = e.by_award.get(aw, Fraction(0)) + p.chance
        name = node["outcome"] or default_outcome(p.effects)
        o = groups.setdefault(key, {}).setdefault(name, Row(name, name, Fraction(0), {}))
        o.chance += p.chance
        o.by_award[aw] = o.by_award.get(aw, Fraction(0)) + p.chance
    for choice in ends:
        # Out of every time these answers are given (a later question is reached only on some draws: its keys' rows
        # are taken out of the draws that reach it).  Version 1's buttons already add up to 1.
        total = sum(r.chance for r in ends[choice].values())
        for r in list(ends[choice].values()) + list(groups[choice].values()):
            r.chance /= total
            r.by_award = {k: v / total for k, v in r.by_award.items()}
        out[choice] = {"ends": list(ends[choice].values()), "outcomes": list(groups[choice].values())}
    return out


def percent(f: Fraction) -> str:
    """As the owner writes a chance: 12.5%, 8.33%, 90%, 0.56%."""
    text = f"{float(f * 100):.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


def part_name(g: dict, nid: str) -> str:
    """A part as the author sees it: its name, else its id (a graph saved before parts had names)."""
    n = g.get("nodes", {}).get(nid)
    return (n.get("name") if isinstance(n, dict) else None) or nid


def chances_table(g: dict, game: int, patches: Iterable[str] = (), roles: Iterable[str] | None = None) -> str:
    """The "chances of every outcome" table, as the owner's design file sets it out."""
    lines = [f"{g['title']}: {GAMES[game].name}" + (f", with {', '.join(patches)}" if patches else "")]
    start = g["nodes"][g["start"]]

    def lab(c: dict) -> str:
        """A label with its game words as the game shows them (version 6)."""
        if g.get("version", 1) < VERSION_V6:
            return c["label"]
        return re.sub(r"\{@([A-Za-z0-9_]+)\}", lambda m: g["words"].get(m.group(1), {}).get(str(game), m.group(0)),
                      c["label"])

    for choice, rows in chances(g, game, patches, roles).items():
        lines.append("")
        if choice is None:
            lines.append("THE EVENT")
            out_of = "out of every time the event happens"
        elif isinstance(choice, tuple):
            words = " > ".join(f"{part_name(g, q)} {answer_letter(b)}: {lab(g['nodes'][q]['choices'][b]).upper()}"
                               for q, b in choice)
            lines.append(f"CHOICES {words}")
            out_of = "out of every time these choices are picked"
        else:
            label = lab(start["choices"][choice])
            lines.append(f"CHOICE {answer_letter(choice)}: {label.upper()}")
            out_of = "out of every time this choice is picked"
        lines.append(f"Each ending, {out_of}:")
        for r in rows["ends"]:
            key = part_name(g, r.key)
            name = f"{key} ({r.words})" if r.words else key
            split = ""
            if len(r.by_award) > 1:
                split = "  (" + ", ".join(f"{percent(v)} {k}" for k, v in r.by_award.items()) + ")"
            lines.append(f"  {name} {'.' * max(3, 46 - len(name))} {percent(r.chance)}{split}")
        lines.append("In all:")
        for r in rows["outcomes"]:
            lines.append(f"  {r.words} {'.' * max(3, 46 - len(r.words))} {percent(r.chance)}")
            if len(r.by_award) > 1:
                for k, v in r.by_award.items():
                    words = f"with {k}"
                    lines.append(f"     {words} {'.' * max(3, 43 - len(words))} {percent(v)}")
    return "\n".join(lines)


# ---- The library (the owner, 2026-11-12: the editor lives in the patcher) ------------------------------------------
#
# The patcher's "Custom Island Event Library" window keeps each event as two files, side by side, in the game's save
# folder (not a slot's: an event is played in any village of that game):
#
#     <save folder>\Virtual Villagers Fun Patcher\Custom Island Events\
#         <name>.json   the event as written (this format): what the player edits, keeps and shares
#         <name>.cieg   compiled from it at each save: what the game's companion reads to queue it
#
# A .json is only ever compiled after it passes validate(); a .cieg whose .json is missing, newer, or does not pass
# is never offered in the game.  The in-game editor stays for simple events.

LIBRARY_FOLDER = ("Virtual Villagers Fun Patcher", "Custom Island Events")
GRAPH_SUFFIX = ".json"
BINARY_SUFFIX = ".cieg"


def library_folder(save_folder: str | Path) -> Path:
    return Path(save_folder).joinpath(*LIBRARY_FOLDER)


def library_stem(title: str) -> str:
    """A file name for an event's title: letters, digits, space, - and _ (Windows-safe), at most 64."""
    stem = re.sub(r"[^A-Za-z0-9 _-]+", "", readable_title(title)).strip()[:64].strip()
    return stem or "Custom Island Event"


def save_to_library(g: dict, save_folder: str | Path, stem: str | None = None) -> tuple[Path, Path]:
    """Write a validated graph and its .cieg into the library (each through a .tmp moved over the old file)."""
    folder = library_folder(save_folder)
    folder.mkdir(parents=True, exist_ok=True)
    stem = stem or library_stem(g["title"])
    out = []
    for suffix, payload in ((GRAPH_SUFFIX, (json.dumps(g, indent=2) + "\n").encode("utf-8")),
                            (BINARY_SUFFIX, compile_graph(g))):
        path = folder / (stem + suffix)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(payload)
        tmp.replace(path)
        out.append(path)
    return out[0], out[1]


def read_library(save_folder: str | Path, scrolling: bool = False) -> dict[str, tuple[dict | None, list[str]]]:
    """Every event in the library: stem -> (the graph, or None, and its problems)."""
    out: dict[str, tuple[dict | None, list[str]]] = {}
    folder = library_folder(save_folder)
    for path in sorted(folder.glob("*" + GRAPH_SUFFIX)) if folder.is_dir() else []:
        try:
            g, problems = validate(json.loads(path.read_text(encoding="utf-8")), scrolling)
        except (OSError, ValueError) as e:
            out[path.stem] = (None, [f"cannot be read: {e}"])
            continue
        out[path.stem] = (None if problems else g, problems)
    return out


# ---- Command line --------------------------------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Check, compile or show the chances of a branching Custom Island Event.")
    ap.add_argument("command", choices=("validate", "compile", "chances"))
    ap.add_argument("graph")
    ap.add_argument("--out", help="compile: the .cieg to write")
    ap.add_argument("--game", type=int, default=None, help="chances: 1..5 (default: every game the graph lists)")
    ap.add_argument("--scrolling", action="store_true", help="the popups scroll (v1.35.97)")
    a = ap.parse_args(argv)
    try:
        g = load(a.graph, a.scrolling)
    except GraphError as e:
        print("\n".join(e.problems))
        return 1
    if a.command == "validate":
        print("OK")
    elif a.command == "compile":
        out = Path(a.out or Path(a.graph).with_suffix(".cieg"))
        out.write_bytes(compile_graph(g))
        print(out)
    else:
        for game in ([a.game] if a.game else g["games"]):
            print(chances_table(g, game))
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
