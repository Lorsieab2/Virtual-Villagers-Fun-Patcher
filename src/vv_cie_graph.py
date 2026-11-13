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
        question  text and exactly two "choices" [{"label", "next"}] (the game's two-button popup); version 1: the
                  start node only;
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
weights 1..MAX_WEIGHT; a question has exactly two choices (version 1: and is the start node; version 2: the page
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
refuses it cleanly instead of misreading it.  A version 1 graph is compiled as version 1.
  header (80 bytes)
     0 4s magic "CIEG"          4 H version (1, 2)         6 H header bytes (80)     8 I file bytes
    12 I crc32 of the whole file with this field 0      16 I games mask (bit g-1)
    20 H title string           22 H start node          24 H requirement min_eligible (0 = none)
    26 H role count  28 H node count  30 H child count  32 H effect count  34 H cond count  36 H variant count
    38 H string count  40 H patch count  42 H 0
    44 I roles  48 I nodes  52 I children  56 I effects  60 I conds  64 I variants  68 I patches  72 I strings (offsets)
    76 I 0
  role     8 bytes: B kind (0 villager, 1 stranger), B flags (1 optional, 2 exclude_nursing, 4 exclude_special,
                    8 believers_only), B sex (0 any, 1 male, 2 female, 3 random), B min_age years, H id string, H 0
  node    28 bytes: B type (0 popup, 1 question, 2 branch), B popup (0 new, 1 append), B join (0 space, 1 paragraph),
                    B 0, H id string, H text string, H first variant, H variants, H first child, H children
                    (a question's: its two choices), H else node, H first effect, H effects, H summary string,
                    H outcome string, H 0
  child   12 bytes: H next node, H weight, H cond, H else node, H label string (choices only), H 0
  effect  16 bytes: B type (EFFECT_CODES), B role, B flags (1 scaled, 2 defer, 4 dislikes), B 0, i a, i b, H string, H 0
                    food/tech a = amount; health a..b; skill a..b and string = the skills, comma separated;
                    preference string = the word; kill string = the cause; status a = 1 (heathen)
  cond     8 bytes: B op (COND_CODES), B operand count, H a, H b, H 0 -- visited a = node, role a = role, game a = mask,
                    patch a = patch, not a = operand, all / any: operands a .. a + count - 1 (consecutive)
  variant  4 bytes: H cond, H text string
  patch    2 bytes: H id string
  strings: I offset[count] from the strings section, then NUL-terminated ASCII.  NONE = 0xFFFF everywhere.
"""
from __future__ import annotations

import json
import re
import struct
import sys
import zlib
from dataclasses import dataclass, field
from fractions import Fraction
from itertools import product
from pathlib import Path
from typing import Any, Iterable

FORMAT = "vvfp-cie-graph"
VERSION = 2                   # what new events are written in
VERSIONS = (1, 2)             # what this patcher reads
BINARY_MAGIC = b"CIEG"
BINARY_VERSION = 2            # a version 1 graph is still compiled as version 1, byte for byte as before
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
SEX_CODES = {"any": 0, "male": 1, "female": 2, "random": 3}
NODE_TYPES = ("popup", "question", "branch")
UNITS = {"food": "food", "tech": "tech points"}

PLACEHOLDER_RE = re.compile(r"\(([^()\n]*)\)")
PRONOUNS = {"he/she": ("he", "she"), "his/her": ("his", "her"), "him/her": ("him", "her"),
            "man/woman": ("man", "woman")}
_NAME_ALIASES = {"name1": "subject", "name2": "friend"}


def text_char_ok(c: str, version: int = 1) -> bool:
    """story_custom.inc ce_text_char_ok, line breaks allowed; version 2 adds the double quote, which every game's
    font draws (src/vv_font_glyphs.py: A New Home's and The Lost Children's fonts hold ! " ' , . ? / ` : -)."""
    return (c.isascii() and c.isalnum()) or c in " .,!?:-'\n" or (version >= 2 and c == '"')


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


def label_max_px(game: int) -> int:
    """The widest label the game's screen shows whole, centred."""
    return _label_table(game)["max_px"]


class GraphError(ValueError):
    """A graph that does not pass; .problems lists every reason."""

    def __init__(self, problems: list[str]):
        super().__init__("\n".join(problems))
        self.problems = problems


# ---- Loading: shape checks and the normalized form ----------------------------------------------------------------


def _norm_cond(c: Any, where: str, problems: list[str]) -> Any:
    if c is None:
        return None
    if not isinstance(c, dict) or len(c) != 1:
        problems.append(f"{where}: a condition is one of visited / role / game / patch / not / all / any")
        return None
    (op, arg), = c.items()
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
        inner = _norm_cond(arg, where, problems)
        return None if inner is None else {"not": inner}
    if op in ("all", "any"):
        if not isinstance(arg, list) or not arg or len(arg) > 255:
            problems.append(f"{where}: {op} takes 1..255 conditions")
            return None
        parts = [_norm_cond(x, where, problems) for x in arg]
        return None if any(p is None for p in parts) else {op: parts}
    problems.append(f"{where}: unknown condition {op!r}")
    return None


def _int_in(v: Any, lo: int, hi: int) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi


def _norm_effect(e: Any, where: str, problems: list[str]) -> dict | None:
    if not isinstance(e, dict) or e.get("do") not in EFFECT_CODES:
        problems.append(f"{where}: an effect is {{\"do\": one of {', '.join(EFFECT_CODES)}}}")
        return None
    do = e["do"]
    known = {"do"}
    out: dict[str, Any] = {"do": do}
    if do in ("food", "tech"):
        known |= {"amount", "scaled", "defer"}
        amount = e.get("amount")
        if not _int_in(amount, -MAX_AMOUNT, MAX_AMOUNT) or amount == 0:
            problems.append(f"{where}: {do} amount is a whole number, not 0, at most {MAX_AMOUNT} either way")
        out.update(amount=amount, scaled=bool(e.get("scaled", False)), defer=bool(e.get("defer", False)))
        if out["defer"] and isinstance(amount, int) and amount < 0:
            problems.append(f"{where}: an award (defer) is a gain")
    elif do == "pay_award":
        pass
    else:
        known.add("role")
        out["role"] = e.get("role", "subject")
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
        elif do == "skill":
            known |= {"skills", "min", "max"}
            skills = e.get("skills")
            if not isinstance(skills, list) or not skills or not all(isinstance(s, str) for s in skills) \
                    or len(set(skills)) != len(skills):
                problems.append(f"{where}: skill lists one or more different skills")
                skills = []
            lo, hi = e.get("min"), e.get("max")
            if not (_int_in(lo, 1, SKILL_ADD_MAX) and _int_in(hi, 1, SKILL_ADD_MAX) and lo <= hi):
                problems.append(f"{where}: skill adds 1..{SKILL_ADD_MAX}, min <= max")
            out.update(skills=list(skills), min=lo, max=hi)
    extra = set(e) - known
    if extra:
        problems.append(f"{where}: {do} does not take {', '.join(sorted(extra))}")
    return out


def normalize(data: Any) -> tuple[dict, list[str]]:
    """The graph with every default filled in, and the shape problems found."""
    problems: list[str] = []
    if not isinstance(data, dict):
        return {}, ["the file is not a JSON object"]
    if data.get("format") != FORMAT:
        problems.append(f"format is not {FORMAT!r}")
    version = data.get("version")
    if version not in VERSIONS:
        problems.append(f"version {version!r} is not one this patcher reads ({', '.join(map(str, VERSIONS))})")
        version = VERSION
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
    if not _int_in(min_el, 0, 255):
        problems.append("requirement.min_eligible is 0..255")
        min_el = 0
    g["requirement"] = {"min_eligible": min_el}

    roles_in = data.get("roles")
    roles: dict[str, dict] = {}
    if not isinstance(roles_in, dict) or not roles_in:
        problems.append("roles is missing")
        roles_in = {}
    for rid, r in roles_in.items():
        where = f"role {rid}"
        if not ID_RE.match(rid):
            problems.append(f"{where}: an id is 1..32 letters, digits or _")
        if not isinstance(r, dict) or r.get("kind") not in ("villager", "stranger"):
            problems.append(f"{where}: kind is villager or stranger")
            continue
        if r["kind"] == "stranger":
            extra = set(r) - {"kind", "sex"}
            sex = r.get("sex", "random")
            if sex not in ("random", "male", "female"):
                problems.append(f"{where}: a stranger's sex is random, male or female")
            roles[rid] = {"kind": "stranger", "sex": sex}
        else:
            extra = set(r) - {"kind", "optional", "sex", "min_age", "exclude_nursing", "exclude_special",
                              "believers_only"}
            sex = r.get("sex", "any")
            if sex not in ("any", "male", "female"):
                problems.append(f"{where}: a villager's sex is any, male or female")
            min_age = r.get("min_age", 14)
            if not _int_in(min_age, 0, 80):
                problems.append(f"{where}: min_age is 0..80 years")
            roles[rid] = {"kind": "villager", "optional": bool(r.get("optional", False)), "sex": sex,
                          "min_age": min_age, "exclude_nursing": bool(r.get("exclude_nursing", True)),
                          "exclude_special": bool(r.get("exclude_special", True)),
                          "believers_only": bool(r.get("believers_only", True))}
        if extra:
            problems.append(f"{where}: unknown fields {', '.join(sorted(extra))}")
    if roles and next(iter(roles)) != "subject":
        problems.append("the first role is subject")
    if "subject" in roles and (roles["subject"]["kind"] != "villager" or roles["subject"]["optional"]):
        problems.append("subject is a villager the event needs (not optional)")
    if len(roles) > 16:
        problems.append("at most 16 roles")
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
                 "outcome"}
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
        variants = []
        for i, v in enumerate(n.get("variants", []) or []):
            if not isinstance(v, dict) or not isinstance(v.get("text"), str) or "if" not in v or set(v) - {"if", "text"}:
                problems.append(f"{where}: variant {i + 1} is {{\"if\": condition, \"text\": \"...\"}}")
                continue
            variants.append({"if": _norm_cond(v["if"], f"{where} variant {i + 1}", problems), "text": v["text"]})
        effects = [x for x in (_norm_effect(e, f"{where} effect {i + 1}", problems)
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
            children.append({"next": c["next"], "weight": w, "if": _norm_cond(c.get("if"), cw, problems),
                             "else": els})
        choices = []
        for i, c in enumerate(n.get("choices", []) or []):
            if not isinstance(c, dict) or not isinstance(c.get("label"), str) or not isinstance(c.get("next"), str) \
                    or set(c) - {"label", "next"}:
                problems.append(f"{where} choice {i + 1}: a choice is {{\"label\": \"...\", \"next\": id}}")
                continue
            choices.append({"label": c["label"], "next": c["next"]})
        els = n.get("else")
        if els is not None and not isinstance(els, str):
            problems.append(f"{where}: else names a node")
            els = None
        summary, outcome = n.get("summary", ""), n.get("outcome", "")
        if not isinstance(summary, str) or not isinstance(outcome, str) or not (summary + outcome).isascii():
            problems.append(f"{where}: summary and outcome are plain ASCII words")
            summary, outcome = "", ""
        if t == "question":
            if len(choices) != 2:
                problems.append(f"{where}: a question has exactly two choices")
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
    g["nodes"] = nodes
    return g, problems


# ---- Placeholders --------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Placeholder:
    role: str | None      # None for award / award_unit
    what: str             # "name", a PRONOUNS key, "award", "award_unit"
    capital: bool


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
            return "9" * (AWARD_WIDEST if award[2] else len(str(abs(award[1]))))
        if p.what == "award_unit":
            return UNITS[award[0]] if award else UNITS["tech"]
        if p.what == "name":
            return "W" * game.name_room
        return max(PRONOUNS[p.what], key=len)
    return PLACEHOLDER_RE.sub(one, text)


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


def cond_holds(c: Any, ctx: Context, visited: Iterable[str]) -> bool:
    if c is None:
        return True
    (op, arg), = c.items()
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


def contexts(g: dict, games: Iterable[int] | None = None) -> list[Context]:
    """Every game x every patch on or off x every optional role bound or not."""
    optional = [r for r, v in g["roles"].items() if v.get("optional")]
    always = frozenset(r for r in g["roles"] if r not in optional)
    out = []
    for game in (games if games is not None else g["games"]):
        for pbits in product((False, True), repeat=len(g["patches"])):
            pset = frozenset(p for p, on in zip(g["patches"], pbits) if on)
            for rbits in product((False, True), repeat=len(optional)):
                rset = always | {r for r, on in zip(optional, rbits) if on}
                out.append(Context(game, pset, frozenset(rset)))
    return out


@dataclass
class Popup:
    layout: str                         # "plain", "question", "result"
    text: str = ""                      # the raw text, as the nodes join it
    worst: str = ""                     # at its widest in the game
    effects: bool = False               # carries villager effects (refusal lines)
    nodes: list[str] = field(default_factory=list)


@dataclass
class History:
    """One history from the start to an ending."""
    choice: int | None                  # the first question's button (0, 1), None without a question
    nodes: tuple[str, ...]
    chance: Fraction
    popups: list[Popup]
    award: tuple[str, int, bool] | None       # the award deferred or paid: (kind, amount, scaled)
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
        if cond_holds(c["if"], ctx, visited):
            out.append((c["next"], c["weight"]))
        elif c["else"] is not None:
            out.append((c["else"], c["weight"]))
    if not out and node["else"] is not None:
        out.append((node["else"], 1))
    return out


def walk(g: dict, ctx: Context, problems: list[str] | None = None) -> list[History]:
    """Every history of the graph in `ctx`, with its chance (each question button counts as 1).  Problems on a
    history (an unbound role, an award never deferred, a dead end, ...) are added to `problems`."""
    nodes = g["nodes"]
    game = GAMES[ctx.game]
    found: list[History] = []
    seen: set[str] = set()

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
              gone: frozenset, effects: list, answers: tuple = (), seg: tuple = (False, False, False)) -> None:
        if len(found) >= MAX_PATHS:
            say(f"more than {MAX_PATHS} histories: the graph is too big")
            return
        node = nodes[nid]
        path = path + (nid,)
        popups = [Popup(p.layout, p.text, p.worst, p.effects, list(p.nodes)) for p in popups]
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
                award, paid = (do, e["amount"], e["scaled"]), False
            elif do == "pay_award":
                if award is None or paid:
                    say(f"node {nid} ({where}): pay_award with no award deferred on the way here")
                paid = True
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
            popups.append(Popup("question", text, nodes=[nid]))
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
            else:
                popups.append(Popup("plain" if not popups else "result", text, nodes=[nid]))
        if node["type"] != "branch":
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
        if any(e["do"] in VILLAGER_EFFECTS for e in node["effects"]) and popups and node["type"] != "question":
            popups[-1].effects = True
        if node["type"] != "branch" and popups:
            popups[-1].worst = worst_case(popups[-1].text, game, award)

        if node["type"] == "question":
            for i, c in enumerate(node["choices"]):
                if c["next"] in nodes:
                    visit(c["next"], i if choice is None else choice, path, chance, popups, award, paid, gone,
                          effects, answers + ((nid, i),), (True, False, False))
            return
        kids = _resolved_children(node, ctx, path)
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
                      (asked, paged, changed))

    if g["start"] in nodes:
        visit(g["start"], None, (), Fraction(1), [], None, False, frozenset(), [])
    return found


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
    if op in ("visited", "role", "patch"):
        out.append((op, arg))
    elif op == "not":
        _cond_refs(arg, out)
    elif op in ("all", "any"):
        for x in arg:
            _cond_refs(x, out)


def _check_text(where: str, text: str, problems: list[str], version: int = 1) -> None:
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
            key = (game.number, pop.layout, pop.worst, pop.effects)
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
            pages, why = paginate(layout, g["title"], pop.worst, REFUSAL_LINES if pop.effects else 0)
            if why:
                problems.append(f"{game.name}: the popup of {nodes} runs off the screen without scrolling: {why}")
            elif len(pages) > MAX_PAGES:
                problems.append(f"{game.name}: the popup of {nodes} takes {len(pages)} pages; at most {MAX_PAGES}")
    return problems


def validate(data: Any, scrolling: bool = False) -> tuple[dict, list[str]]:
    """(the normalized graph, every problem).  No problems = the graph may be compiled and played."""
    g, problems = normalize(data)
    if problems and not g.get("nodes"):
        return g, problems
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
        for op, ref in refs:
            if op == "visited" and ref not in nodes:
                problems.append(f"node {nid}: visited {ref!r} names no node")
            if op == "role" and ref not in g["roles"]:
                problems.append(f"node {nid}: role {ref!r} names no role")
            if op == "patch" and ref not in g["patches"]:
                problems.append(f"node {nid}: patch {ref!r} is not in patches")
        if n["type"] != "branch":
            _check_text(f"node {nid}", n["text"], problems, g["version"])
            for i, v in enumerate(n["variants"]):
                _check_text(f"node {nid} variant {i + 1}", v["text"], problems, g["version"])
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
    title = g["title"]
    if len(title) > TITLE_BYTES:
        problems.append(f"the title is longer than {TITLE_BYTES} characters")
    if PLACEHOLDER_RE.search(title):
        problems.append("the title has no placeholders")
    if not all(text_char_ok(c) and c != "\n" for c in title):
        problems.append("the title has characters the game cannot show")
    for gn in g["games"]:
        game = GAMES[gn]
        if len(title) > game.title_width:
            problems.append(f"{game.name}: the title is longer than its {game.title_width} characters")
        for nid, n in nodes.items():
            for c in n["choices"]:
                label = worst_case(c["label"], game, None)
                if len(label) > min(game.label_width, BUTTON_BYTES):
                    problems.append(f"{game.name}: the label {c['label']!r} is {len(label)} characters with the "
                                    f"longest names; at most {min(game.label_width, BUTTON_BYTES)}")
                elif label_px(gn, label) > label_max_px(gn):
                    problems.append(f"{game.name}: the label {c['label']!r} runs off the screen with the longest "
                                    f"names ({label_px(gn, label)} of {label_max_px(gn)} pixels)")
    for nid, n in nodes.items():
        for c in n["choices"]:
            _check_text(f"node {nid} label", c["label"], problems, g["version"])
            if "\n" in c["label"]:
                problems.append(f"node {nid}: a label is one line")
            for raw, p in placeholders(c["label"]):
                if p is None or p.what in ("award", "award_unit") or (p.role and p.role not in g["roles"]):
                    problems.append(f"node {nid}: the label's {raw} is not a placeholder a label can show")
                elif g["roles"][p.role].get("optional"):
                    problems.append(f"node {nid}: the label's {raw} names {p.role}, who may not be bound")

    # Every history in every context.
    for ctx in contexts(g):
        paths = walk(g, ctx, problems)
        problems.extend(x for x in fit_problems(g, paths, scrolling) if x not in problems)
    return g, problems


def load(path_or_data: Any, scrolling: bool = False) -> dict:
    """The normalized graph from a file (or parsed JSON); GraphError when it does not pass."""
    data = path_or_data
    if isinstance(path_or_data, (str, Path)):
        data = json.loads(Path(path_or_data).read_text(encoding="utf-8"))
    g, problems = validate(data, scrolling)
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


def compile_graph(g: dict) -> bytes:
    """The .cieg of a normalized, validated graph (load())."""
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
            roles += _ROLE.pack(0, flags, SEX_CODES[v["sex"]], v["min_age"], s(r), 0)
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
    version = 1 if g.get("version", 1) == 1 else BINARY_VERSION
    head = _HEADER.pack(BINARY_MAGIC, version, _HEADER.size, at, 0,
                        sum(1 << (x - 1) for x in g["games"]), title, nidx[g["start"]],
                        g["requirement"]["min_eligible"], len(role_ids), len(node_ids), n_child, n_effect,
                        len(conds), n_variant, len(strings), len(g["patches"]), 0, *offs, 0)
    data = bytearray(head + b"".join(sections))
    struct.pack_into("<I", data, 12, zlib.crc32(bytes(data)))
    return bytes(data)


def decompile_graph(data: bytes) -> dict:
    """The normalized graph a .cieg holds (what compile_graph was given); GraphError when the file is damaged."""
    if len(data) < _HEADER.size:
        raise GraphError(["the file is shorter than a .cieg header"])
    h = _HEADER.unpack_from(data, 0)
    (magic, version, hsize, fsize, crc, games_mask, title, start, min_el, n_role, n_node, n_child, n_effect, n_cond,
     n_variant, n_string, n_patch, _z, o_role, o_node, o_child, o_effect, o_cond, o_variant, o_patch, o_string,
     _z2) = h
    if magic != BINARY_MAGIC or version not in (1, BINARY_VERSION) or hsize != _HEADER.size or fsize != len(data):
        raise GraphError(["not a version 1 or 2 .cieg file"])
    check = bytearray(data)
    struct.pack_into("<I", check, 12, 0)
    if zlib.crc32(bytes(check)) != crc:
        raise GraphError(["the .cieg file is damaged (checksum)"])
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
    for rid, (kind, flags, sex, min_age, _sid, _z3) in zip(role_ids, roles_raw):
        if kind == 1:
            roles[rid] = {"kind": "stranger", "sex": sex_names[sex]}
        else:
            roles[rid] = {"kind": "villager", "optional": bool(flags & 1), "sex": sex_names[sex], "min_age": min_age,
                          "exclude_nursing": bool(flags & 2), "exclude_special": bool(flags & 4),
                          "believers_only": bool(flags & 8)}
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
    return {"format": FORMAT, "version": version, "title": s(title),
            "games": [x for x in range(1, 6) if games_mask & (1 << (x - 1))], "patches": patches,
            "requirement": {"min_eligible": min_el}, "roles": roles, "start": node_ids[start], "nodes": nodes}


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
    return f"+{amount:,} {UNITS[kind]}"


@dataclass
class Row:
    key: str
    words: str
    chance: Fraction
    by_award: dict[str, Fraction]


def chances(g: dict, game: int, patches: Iterable[str] = (), roles: Iterable[str] | None = None) \
        -> dict[int | None, dict[str, list[Row]]]:
    """For each question button (None without a question) -- or, when a question is asked after the start
    (version 2), each run of answers ((question, button), ...) -- "ends": each ending's chance out of every time
    those answers are given -- and "outcomes", the "In all" groups, each split by the award paid."""
    bound = frozenset(roles) if roles is not None else frozenset(g["roles"])
    ctx = Context(game, frozenset(patches), bound)
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


def chances_table(g: dict, game: int, patches: Iterable[str] = (), roles: Iterable[str] | None = None) -> str:
    """The "chances of every outcome" table, as the owner's design file sets it out."""
    lines = [f"{g['title']}: {GAMES[game].name}" + (f", with {', '.join(patches)}" if patches else "")]
    start = g["nodes"][g["start"]]
    for choice, rows in chances(g, game, patches, roles).items():
        lines.append("")
        if choice is None:
            lines.append("THE EVENT")
            out_of = "out of every time the event happens"
        elif isinstance(choice, tuple):
            words = " > ".join(f"{q} {'AB'[b]}: {g['nodes'][q]['choices'][b]['label'].upper()}" for q, b in choice)
            lines.append(f"CHOICES {words}")
            out_of = "out of every time these choices are picked"
        else:
            label = start["choices"][choice]["label"]
            lines.append(f"CHOICE {'AB'[choice]}: {label.upper()}")
            out_of = "out of every time this choice is picked"
        lines.append(f"Each ending, {out_of}:")
        for r in rows["ends"]:
            name = f"{r.key} ({r.words})" if r.words else r.key
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
    stem = re.sub(r"[^A-Za-z0-9 _-]+", "", title).strip()[:64].strip()
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
