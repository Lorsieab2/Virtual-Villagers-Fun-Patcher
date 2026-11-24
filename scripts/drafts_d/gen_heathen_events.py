"""Write New Believers' Heathen-Exclusive Events HE-01..HE-45 (the owner's approval of 2026-11-23; collection_lib.DRAFTS_D
"heathen_ex", the frozen "Heathen-Only Events (draft for owner).txt") as collection events, then format and check them:

    python scripts/drafts_d/gen_heathen_events.py
    python scripts/drafts_d/gen_heathen_events.py --sheet     # the review sheet: each page, its roles and effects

THE SHAPE.  "HE-01. Title", then its casting line "(picks ...)", "(based on ...)" notes and "Requirement: ...", the
setup, then each "Label:" with its outcome text and its "Effects:" line; or "(no choice; one popup)" and one page.  A
choice leads to its own one outcome page (the draft: "Outcome odds: one per choice" / "equal" -- each label one
outcome).  The casting line, the requirement, the effects line, the odds, the notes in parentheses and the "Guardians
of Isola title:" line are ledger entries; the owner's text is never reworded (the draft's own "(no effect)" lines are
shown as written: an engine that adds "(no effect)" to an outcome that changes nothing never adds it twice, PR #853's
ends_no_effect).

THE OWNER'S ANSWERS (2026-11-23, every one approved):
- Every villager role is an ordinary Heathen ("heathens": "only": never roles 12-17, never sick, alive), but HE-13's
  and HE-25's believer.  Without the row "Heathens can be selected in Island Events/Heathen-Exclusive Events" an "only"
  role is never filled, so none of these is offered; once every Heathen has joined the tribe none can be cast.  These
  events replace vanilla's "only cast a Heathen when it is about joining the tribe" rule for this row.
- No Heathen's Faith ever rises; nobody dies, vanishes, or moves between the tribe and the Heathens.
- The encampment's honoring and reflecting (E9, cie-v6-binary.md 46): the hovel patch's own entries when "Memorial
  Actions Can Also Occur at the Heathen Hovel" is installed, else they sit where they are.  HE-10 and HE-24: every
  Heathen (E10), each honoring or reflecting, 50% each (the Remembrance Ceremony's split).
- HE-05 and HE-13: the mausoleum (the game's own "Honoring the dead", behaviour 17), with at least one grave (E8).
- HE-29 keeps the Heathens' own "Scratching for roots".  HE-17: the stock nectar's age, 16 and a half.
- "An elder, 50 or older, or the oldest adult / any adult if there is none" (HE-24, HE-34, HE-43): the oldest the role
  may take ("prefer": "oldest").  HE-06's "Building 30 or more, or any Heathen adult": the best builder.
- A requirement of "at least N Heathens" the text does not name is a cast-only Heathen role each (HE-10, HE-24).
- Flavor only: food, tech points and structures in these texts are the Heathens' village's, story text only; the
  draft writes their "(no effect)" itself.
- Guardians of Isola Rewrite: the draft's pairs (Heathen -> Isolan, Heathens -> Isolans, a Heathen -> an Isolan), made
  on every text that says Heathen (title variants, page variants, description variants; guardians-wording.md rows,
  written here between the markers).  Nothing calls anyone "Guardians".
- Odds: as every added event -- the file is one series (dr_he), each event draw weight 1.

Nothing here touches a game, a save or an exe.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "drafts_b"))
import collection_check as cc  # noqa: E402
import collection_lib as lib  # noqa: E402
from gen_drafts_b import kinds  # noqa: E402

SID = "heathen_ex"
SECTION = lib.DRAFTS_D[SID][2]
OUT_DIR = lib.DRAFTS_D_DIR / SECTION
G_IF = cc.GUARDIANS_IF
# The draft's Guardians of Isola pairs, in the order they are made (the article first).
HEATHEN_PAIRS = [("A Heathen", "An Isolan"), ("a Heathen", "an Isolan"), ("Heathens", "Isolans"),
                 ("Heathen", "Isolan")]
LABEL_RE = re.compile(r"^[A-Z][^.!?:]{0,80}:$")
PRONOUN_RE = re.compile(r"\((he/she|He/she|him/her|Him/Her|his/her|His/Her|himself/herself|Himself/Herself)\)")
NAME_RE = re.compile(r"\((name[123])\)")
ROLE_FOR = {"1": "subject", "2": "friend", "3": "third", "o": "other"}
NAME_ROLE = {"name1": "subject", "name2": "friend", "name3": "third"}

HONOR = "Honoring the dead (at the encampment)"
REFLECT = "Reflecting (at the encampment)"
EITHER = "Honoring the dead or reflecting (at the encampment)"
MAUSOLEUM = "Honoring the dead [Day of Honor]"       # behaviour 17, the game's own everyday "Honoring the dead"

FLAVOR_WHY = ("the owner's flavor rule (2026-11-23): only Heathens are in this event, so the Heathens' village's {what} "
              "is story text only -- the game is not changed, and the draft's line ends \"(no effect)\"")
STORY_WHY = {
    "skill": "\"skill\" / \"experience\" in the everyday sense; the outcome's own effects are the draft's -- story only",
    "health": "health or an injury talked about in the story; the outcome's own effects are the draft's -- story only",
    "celebrate": "a feast or a happy feeling in the story; the outcome's own effects are the draft's -- story only",
    "kill": "the Heathens' dead, mentioned plainly in the story; nobody dies -- story only",
    "vanish": "the word's everyday sense; nobody leaves the camp -- story only",
    "preference": "a feeling in the moment; the outcome's own effects are the draft's -- story only",
    "damage": "a small thing in the story; no building is damaged -- story only",
    "food": FLAVOR_WHY.format(what="food"),
    "tech": FLAVOR_WHY.format(what="tech points"),
}


# ---- Effects ----------------------------------------------------------------------------------------------------------

def act(r: str, words: str) -> dict:
    return {"do": "action", "role": ROLE_FOR[r], "action": words}


def like(r: str, word: str) -> dict:
    return {"do": "preference", "role": ROLE_FOR[r], "list": "likes", "preference": word}


def dislike(r: str, word: str) -> dict:
    return {"do": "preference", "role": ROLE_FOR[r], "list": "dislikes", "preference": word}


def skill(r: str, name: str, lo: int = 10, hi: int = 20) -> dict:
    return {"do": "skill", "role": ROLE_FOR[r], "skills": [name], "min": lo, "max": hi}


def hp(r: str, lo: int, hi: int | None = None) -> dict:
    return {"do": "health_change", "role": ROLE_FOR[r], "min": lo, "max": lo if hi is None else hi}


def everyone(words: str) -> dict:
    return {"do": "action", "target": {"heathens": "all"}, "action": words}


# ---- The events: roles (age spec, "b" a believer), pronoun marks, effects, the Pick Island Event sentence ---------------
#
# roles: {"1": "18+", ...}; "+o": "18+/oldest", a cast-only role "c2": "0+"; a believer's role ends "/b".
# marks: {part: "1121"}: whose each pronoun is, in order (S the setup, L1.. the labels, O1.. the outcomes); a part not
#   listed is all "1".  Only events with more than one role need them.
# fx: {part: [effects]}.  desc: the Pick Island Event sentence.

HE: dict[int, dict] = {
    1: dict(roles={"1": "18+"}, fx={"O1": [act("1", HONOR), like("1", "stars")], "O2": [act("1", REFLECT)]},
            desc="A Heathen sits by the old mud hut at the edge of the encampment, laying out white shells."),
    2: dict(roles={"1": "8+"}, fx={"O1": [like("1", "flowers"), act("1", HONOR)], "O2": [skill("1", "Parenting")]},
            desc="Someone has been leaving fresh flowers on the old mud hut, and a Heathen finally sees who."),
    3: dict(roles={"1": "18+"}, fx={"O1": [act("1", HONOR)]},
            desc="A Heathen stands in front of the mud hut holding a small mask that belonged to someone they lost."),
    4: dict(roles={"1": "8+", "2": "8+"},
            fx={"O1": [like("1", "stories"), act("1", HONOR), act("2", HONOR)], "O2": [skill("1", "Devotion")]},
            marks={"S": "11", "O1": "", "O2": "1111"},
            desc="A Heathen will lead the camp's song of names for the first time, and a friend offers to help."),
    5: dict(roles={"1": "18+"}, graves=1, fx={"O1": [act("1", MAUSOLEUM)], "O2": [act("1", "Sitting")]},
            desc="A Heathen stands at the edge of the encampment, looking toward the mausoleum where an old friend "
                 "rests."),
    6: dict(roles={"1": "18+/builder", "o": "female"}, fx={"O1": [skill("1", "Building"), like("1", "stories")],
                                                           "O2": [skill("1", "Building")]},
            marks={"S": "o"},
            desc="A Heathen is asked to carve a new mark on the camp's memorial post for an elder long gone."),
    7: dict(roles={"1": "3-13", "2": "18+"}, fx={"O1": [skill("2", "Parenting")], "O2": [act("1", "Sitting"),
                                                                                     act("2", "Sitting")]},
            marks={"S": "1", "L1": "1", "O1": "2111", "L2": "1", "O2": "1"},
            desc="A Heathen child asks a grown-up why everyone goes quiet when they walk past the old mud hut."),
    8: dict(roles={"1": "8+"}, fx={"O1": [act("1", "Washing up in the stream"), like("1", "rain")]},
            desc="On the first day of the rains, a Heathen has a pocketful of stones to drop into the stream."),
    9: dict(roles={"1": "14+", "2": "14+", "3": "14+"},
            fx={"O1": [act("1", "Resting"), act("2", "Resting"), act("3", "Resting"), like("1", "fire")],
                "O2": [like("1", "talking"), like("2", "talking"), like("3", "talking")]},
            marks={"O1": "1"},
            desc="Three Heathens keep the camp's fire burning all night by the mud hut, for the ones they have lost."),
    10: dict(roles={"1": "18+", "c2": "0+"},
             fx={"S": [everyone(EITHER), skill("1", "Devotion")]},
             desc="The Heathens set aside a day of their own to honor their dead."),
    11: dict(roles={"1": "18+", "2": "18+"}, fx={"O1": [skill("1", "Research")]},
             marks={"O1": "1", "O2": "2"},
             desc="Two Heathens disagree about an old carving on the memorial post that nobody can name."),
    12: dict(roles={"1": "18+", "2": "8+"}, fx={"O2": [skill("2", "Parenting")]},
             marks={"S": "1", "L1": "2", "O1": "211", "L2": "2", "O2": "21"},
             desc="A Heathen keeps an empty place at the fire, and a newcomer to that fire nearly sits in it."),
    13: dict(roles={"1": "18+", "2": "18+/b"}, graves=1,
             fx={"O1": [act("1", MAUSOLEUM), act("2", MAUSOLEUM)], "O2": [act("1", "Reflecting")]},
             marks={"O1": "2", "O2": "1"},
             desc="A Heathen and a villager who both lost someone long ago meet by chance at the mausoleum."),
    14: dict(roles={"1": "14+"}, fx={"O1": [hp("1", -5), dislike("1", "sleeping")],
                                     "O2": [hp("1", -15), act("1", "Itchy")]},
             desc="Something is living in a Heathen's sleeping mat, and it is not paying rent."),
    15: dict(roles={"1": "14+"}, fx={"O1": [like("1", "running"), like("1", "jumping"), dislike("1", "work")],
                                     "O2": [dislike("1", "jumping"), dislike("1", "dancing")]},
             desc="Young Heathens are daring each other to jump off the rocks by the waterfall."),
    16: dict(roles={"1": "18+"}, fx={"O1": [like("1", "surprises")]},
             desc="A beautifully woven straw hat has washed up near the encampment."),
    17: dict(roles={"1": "18+"}, fx={"O1": [{"do": "change_age", "role": "subject", "to": "16.5"},
                                            {"do": "young_look", "role": "subject"}]},
             desc="A Heathen finds a gourd of sweet-smelling nectar that glows faintly in the shade."),
    18: dict(roles={"1": "3-13"}, fx={"O1": [skill("1", "Farming"), like("1", "nature")],
                                      "O2": [skill("1", "Farming", 25, 25)]},
             desc="A huge cloud of fruit bats has settled on the noni bushes near the encampment."),
    19: dict(roles={"1": "3-13", "2": "18+"},
             fx={"O1": [skill("1", "Research"), skill("2", "Parenting")],
                 "O2": [hp("1", -10), skill("1", "Research")]},
             desc="The Heathen children have been mixing powders behind the camp again, and there have been bangs."),
    20: dict(roles={"1": "18+"}, fx={"O1": [like("1", "dreaming")], "O2": [act("1", "In a trance")]},
             desc="A Heathen wakes certain they dreamed of a great turtle swimming slowly through the sky."),
    21: dict(roles={"1": "14+"}, fx={"O1": [skill("1", "Farming")], "O2": [dislike("1", "running")]},
             desc="A Heathen's basket of noni rolls down the hill and into the tribe's side of the island."),
    22: dict(roles={"1": "14+", "2": "14+"},
             fx={"O1": [act("1", "Trying to get warm"), act("2", "Trying to get warm"), like("1", "fire")],
                 "O2": [act("1", "Trying to get warm (another way)"), act("2", "Trying to get warm (another way)")]},
             desc="A cold fog has rolled in overnight and the encampment's fire has gone out."),
    23: dict(roles={"1": "3-13"}, fx={"S": [act("1", "Celebrating mushrooms"), like("1", "rain")]},
             desc="After a night of rain, the ground around the encampment is covered in mushrooms."),
    24: dict(roles={"1": "18+/oldest", "c2": "0+", "c3": "0+"}, fx={"S": [everyone(EITHER)]},
             desc="The whole encampment gathers at the mud hut at dusk to remember the people the camp has lost."),
    25: dict(roles={"1": "3-13", "2": "3-13/b"},
             fx={"O1": [like("1", "playing"), like("2", "playing")], "O2": [skill("1", "Building")]},
             marks={"S": "111", "O1": "1", "L2": "2", "O2": "211"},
             desc="A Heathen child spots a lost toy in the hands of a child from the village."),
    26: dict(roles={"1": "18+"}, fx={"O1": [hp("1", 10), act("1", "Soaking in the pools")],
                                     "O2": [act("1", "Bathing")]},
             desc="A Heathen has had a long day, and the warm pools are steaming in the moonlight."),
    27: dict(roles={"1": "3-13", "2": "3-13", "3": "18+"},
             fx={"O1": [hp("1", -5), hp("2", -5), skill("3", "Parenting")],
                 "O2": [dislike("1", "the dark"), dislike("2", "the dark")]},
             marks={"O1": "13"},
             desc="Two Heathen children went exploring after lunch and have not come back, and it is getting dark."),
    28: dict(roles={"1": "14-17"}, fx={"O1": [like("1", "surprises")], "O2": [skill("1", "Building")]},
             desc="A Heathen teen has grown so much that the mask grandmother made now sits halfway up their forehead."),
    29: dict(roles={"1": "18+"}, fx={"S": [act("1", "Scratching for roots (Unsafe)"), skill("1", "Farming")]},
             desc="A Heathen with a gift for finding sweet roots comes back with a basketful for the whole camp."),
    30: dict(roles={"1": "18+", "2": "18+"}, fx={"O2": [like("1", "talking"), like("2", "talking")]},
             desc="Two Heathens have been arguing for a week about moving the camp's fire pit."),
    31: dict(roles={"1": "18+"}, fx={"S": [skill("1", "Building"), like("1", "children")]},
             desc="A Heathen is asked to carve a tiny mask to hang over a neighbour's newborn's sleeping mat."),
    32: dict(roles={"1": "14+"}, fx={"O1": [like("1", "talking")], "O2": [like("1", "quiet")]},
             desc="A Heathen sings while working, and one evening a voice from across the stream sings back."),
    33: dict(roles={"1": "14+", "2": "14+"}, fx={"S": [like("2", "stars"), act("1", "Resting")]},
             marks={"S": "1122"},
             desc="Nobody at the camp has slept properly in a week because one Heathen has started snoring."),
    34: dict(roles={"1": "18+/oldest", "2": "3-13"},
             fx={"O1": [skill("2", "Research"), skill("1", "Parenting")],
                 "O2": [like("2", "playing"), skill("1", "Parenting")]},
             desc="An older Heathen is teaching a child to count with pebbles on a flat stone by the hut."),
    35: dict(roles={"1": "18+"}, fx={"S": [skill("1", "Building")]},
             desc="A Heathen has woven a beautiful new roof for the mud hut. It also leaks."),
    36: dict(roles={"1": "3-13", "2": "18+"}, fx={"O1": [like("1", "surprises")], "O2": [like("1", "nature")]},
             marks={"O2": "11"},
             desc="A wild piglet has wandered into the encampment and fallen asleep on a Heathen child's mat."),
    37: dict(roles={"1": "18+", "2": "18+"}, fx={"S": [skill("1", "Building", 5, 10), skill("2", "Building", 5, 10)]},
             desc="It is mending day at the camp, and two Heathens who had a sharp word are given the same net."),
    38: dict(roles={"1": "8+"}, fx={"O1": [like("1", "the ocean")], "O2": [like("1", "quiet")]},
             desc="A Heathen has found a shell they have never seen before: a long pink spiral that hums."),
    39: dict(roles={"1": "18+"}, fx={"O1": [skill("1", "Farming")], "O2": [act("1", "Hic!"), like("1", "cooking")]},
             desc="A Heathen has made a stew so spicy that two people had to sit in the stream afterwards."),
    40: dict(roles={"1": "8+", "2": "8+", "3": "8+"},
             fx={"S": [act("1", "Rain dancing"), act("2", "Rain dancing"), act("3", "Rain dancing")]},
             desc="It has not rained in weeks, and three Heathens try the old rain dance, mostly for fun."),
    41: dict(roles={"1": "8-17", "2": "8-17"},
             fx={"S": [act("1", "Washing the laundry"), act("2", "Washing the laundry"), like("1", "jokes"),
                       like("2", "jokes")]},
             desc="Two young Heathens discover that if they swap masks, almost nobody at camp can tell them apart."),
    42: dict(roles={"1": "18+"}, fx={"S": [act("1", "Watching the clouds"), hp("1", 5, 10)]},
             desc="A Heathen decides, for no particular reason, to do nothing at all today."),
    43: dict(roles={"1": "18+/oldest", "2": "8+"},
             fx={"O1": [act("1", "Telling a story"), like("2", "stories")],
                 "O2": [like("1", "talking"), like("2", "talking")]},
             marks={"S": "1", "O1": "2"},
             desc="An old Heathen has been telling the same story at the fire for three nights, and it is not done."),
    44: dict(roles={"1": "18-19"}, fx={"S": [like("1", "surprises")]},
             desc="At the camp, the day you turn eighteen, everyone gives you advice and a small gift."),
    45: dict(roles={"1": "8+", "2": "8+"}, fx={"S": [act("1", "Relaxing"), act("2", "Relaxing")]},
             desc="It is a still, warm night at the encampment, and two Heathens watch the fireflies."),
}
# HE-18: the draft's note says "Watch Them" adds this line after its text (its own source line's quoted words).
EXTRA_LINE = {18: ("O1", "The Heathens' village learns more about farming. (no effect)")}


def role_spec(spec: str) -> dict:
    parts = spec.split("/")
    m = re.fullmatch(r"(\d+)(?:\+|-(\d+))", parts[0])
    if not m:
        return {"kind": "stranger", "sex": parts[0]}
    out: dict = {"kind": "villager", "min_age": int(m.group(1))}
    if m.group(2):
        out["max_age"] = int(m.group(2))
    if "b" not in parts[1:]:
        out["heathens"] = "only"
    if "oldest" in parts[1:]:
        out["prefer"] = "oldest"
    if "builder" in parts[1:]:
        out["skill"] = {"names": ["Building"], "min": 0, "pick": "highest"}
    return out


def guardians_form(text: str) -> str:
    for before, after in HEATHEN_PAIRS:
        text = text.replace(before, after)
    return text


def L(n: int) -> str:
    return f"L{n}"


def raw(n: int) -> str:
    return lib.normalize_source_text(lib.line(n)).rstrip()


def escape(text: str) -> str:
    """A literal parenthesis of the draft's prose is \\( \\); the placeholders stay."""
    keep = re.compile(r"\((?:name[123]|" + PRONOUN_RE.pattern[3:-3] + r")\)")
    out, i = [], 0
    for m in keep.finditer(text):
        out.append(text[i:m.start()].replace("(", r"\(").replace(")", r"\)"))
        out.append(m.group(0))
        i = m.end()
    out.append(text[i:].replace("(", r"\(").replace(")", r"\)"))
    return "".join(out)


def text_only(text: str, effects: list[dict]) -> list[dict]:
    have, out = kinds(effects), []
    for rx, want in cc.KEYWORDS:
        if have & want:
            continue
        words = []
        for m in rx.finditer(text):
            if m.group(0).lower() not in words:
                words.append(m.group(0).lower())
        if words:
            kind = "health" if "health_change" in want else "kill" if "kill" in want else sorted(want)[0]
            out.append({"what": ", ".join(f'"{w}"' for w in words), "reason": STORY_WHY[kind]})
    return out


class Event:
    """One event's lines, parted: S the setup, L1.. the labels, O1.. the outcomes; the ledger lines."""

    def __init__(self, row: dict):
        self.row = row
        self.num = int(re.match(r"^he(\d\d)_", row["id"]).group(1))
        h, e = row["lines"]
        self.title_line = h
        self.parts: dict[str, list[int]] = {}
        self.ledger: list[dict] = []
        cur, k, popup = None, 0, False
        for n in range(h + 1, e + 1):
            s = raw(n)
            st = s.strip()
            if not st or lib.is_blank_or_separator(n):
                continue
            if st == "(no choice; one popup)":
                popup = True
                self.ledger.append({"src": L(n), "kind": "structural", "why": "the draft's shape: one popup, no choice"})
            elif st.startswith("Requirement:"):
                self.ledger.append({"src": L(n), "kind": "note",
                                    "why": "the requirement and odds, carried out as the roles (an ordinary Heathen "
                                           "each, their count), the grave requirement and the series' draw"})
            elif st.startswith("Effects:"):
                self.ledger.append({"src": L(n), "kind": "instruction",
                                    "why": "the draft's effects, never shown: the page's effects"})
            elif st.startswith("Outcome odds:"):
                self.ledger.append({"src": L(n), "kind": "note", "why": "the outcome odds: one outcome per choice"})
            elif st.startswith("Guardians of Isola"):
                self.ledger.append({"src": L(n), "kind": "note",
                                    "why": "the Guardians of Isola Rewrite wording, carried out as the title / page / "
                                           "description variants (guardians-wording.md)"})
            elif st.startswith("(") and st.endswith(")") and not st.startswith("(name"):
                self.ledger.append({"src": L(n), "kind": "note",
                                    "why": "the draft's note (casting, what it is based on, what is story text), "
                                           "carried out as the roles and effects"})
            elif LABEL_RE.match(st) and not popup:
                k += 1
                self.parts[f"L{k}"] = [n]
                cur = f"O{k}"
            else:
                key = cur or "S"
                self.parts.setdefault(key, []).append(n)
        self.choices = k
        assert "S" in self.parts, self.num


def mark_text(text: str, marks: str | None, multi: bool, where: str, problems: list[str]) -> str:
    found = PRONOUN_RE.findall(text)
    if marks is None:
        marks = "1" * len(found)
    if len(marks) != len(found):
        problems.append(f"{where}: {len(found)} pronouns, {len(marks)} marks")
        marks = (marks + "1" * len(found))[:len(found)]
    it = iter(marks)
    text = escape(text)
    if multi:
        text = PRONOUN_RE.sub(lambda m: f"({ROLE_FOR[next(it)]}.{m.group(1)})", text)
        text = NAME_RE.sub(lambda m: f"({NAME_ROLE[m.group(1)]})", text)
    return text


def build(row: dict) -> tuple[dict, list[str]]:
    ev = Event(row)
    spec = HE[ev.num]
    problems: list[str] = []
    roles: dict = {}
    for key, s in spec["roles"].items():
        rid = ROLE_FOR.get(key) or {"c2": "friend", "c3": "third"}[key]
        roles[rid] = role_spec(s)
    multi = len(roles) > 1
    marks = spec.get("marks", {})
    shown: dict[str, str] = {}
    for part, lines in ev.parts.items():
        text = "\n".join(raw(n) for n in lines)
        if part.startswith("L"):
            text = text.rstrip(":")
        t = mark_text(text, marks.get(part), multi, f"HE-{ev.num:02d} {part}", problems)
        if part.startswith("L"):
            t = lib.title_case_label(t)
        shown[part] = t
    fx = spec.get("fx", {})
    for part in fx:
        if part not in ev.parts:
            problems.append(f"HE-{ev.num:02d}: effects for {part}, which the event does not have")

    def page(part: str, name: str) -> dict:
        lines = list(ev.parts[part])
        text = shown[part]
        if ev.num in EXTRA_LINE and EXTRA_LINE[ev.num][0] == part:
            words = EXTRA_LINE[ev.num][1]
            at = next(n for n in range(row["lines"][0], row["lines"][1] + 1) if words in raw(n))
            text += "\n" + escape(words)
            lines.append(at)
            before, after = raw(at).split(words)
            for cut in (before, after):
                ev.ledger.append({"src": L(at), "kind": "note", "text": cut.strip(),
                                  "why": "the draft's note around the line it adds to this outcome (its quoted words "
                                         "are the page's last line)"})
        nd: dict = {"name": name, "text": text, "src": ",".join(L(n) for n in lines)}
        fx_line = next((n for n in range(lines[-1], row["lines"][1] + 1)
                        if raw(n).strip().startswith("Effects:")), None)
        eff = [dict(e, src=L(fx_line if fx_line else lines[-1])) for e in fx.get(part, [])]
        if eff:
            nd["effects"] = eff
            nd["auto_text"] = True
        to = [dict(t, src=nd["src"]) for t in text_only(" ".join(raw(n) for n in lines), fx.get(part, []))]
        if fx_line:
            # the effects line's own words (its notes: "the stock event's food gain ... text only here")
            to += [dict(t, src=L(fx_line)) for t in text_only(raw(fx_line), fx.get(part, []))]
            if "Celebrating" in raw(fx_line) and not any(e["do"] == "celebrate" for e in fx.get(part, [])):
                to.append({"what": '"celebrating"', "src": L(fx_line),
                           "reason": "the game's own action \"Celebrating mushrooms\", made as the action effect"})
        if to:
            nd["text_only"] = to
        if cc.GUARDIANS_WORDS.search(text):
            nd["variants"] = [{"if": G_IF, "text": guardians_form(text), "src": nd["src"]}]
        return nd

    if ev.choices:
        q = page("S", "The setup")
        choices = []
        for k in range(1, ev.choices + 1):
            ch = {"label": shown[f"L{k}"], "next": f"o{k}", "src": L(ev.parts[f"L{k}"][0])}
            if cc.GUARDIANS_WORDS.search(ch["label"]):
                choices += [dict(ch, **{"if": {"not": G_IF}}),
                            dict(ch, label=guardians_form(ch["label"]), **{"if": G_IF})]
            else:
                choices.append(ch)
        nodes = {"setup": {"type": "question", **q, "choices": choices}}
        for k in range(1, ev.choices + 1):
            nodes[f"o{k}"] = page(f"O{k}", f"Outcome {'ABCDEFG'[k - 1]}")
    else:
        nodes = {"setup": page("S", "The scene")}
    desc = spec["desc"]
    if not (cc.DESCRIPTION_RE.fullmatch(desc) and len(desc) <= cc.DESCRIPTION_MAX):
        problems.append(f"HE-{ev.num:02d}: description {desc!r}")
    used = {e.get("role") for nd in nodes.values() for e in nd.get("effects", [])} - {None}
    col: dict = {"id": row["id"], "title_src": L(ev.title_line), "ledger": ev.ledger, "description": desc,
                 "label_case": "title",
                 "exact_amounts": True}          # the owner's own numbers ("+10 to +20", "+25", "-5 health")
    if cc.GUARDIANS_WORDS.search(desc):
        col["description_variants"] = [{"if": G_IF, "description": guardians_form(desc)}]
    cast_only = [r for r, s in roles.items() if s["kind"] == "villager" and r not in used]
    if cast_only:
        col["cast_only"] = cast_only
    villagers = sum(1 for r in roles.values() if r["kind"] == "villager")
    doc: dict = {"format": "vvfp-cie-graph", "version": 6, "title": row["title"], "games": row["games"],
                 "collection": col, "requirement": {"min_eligible": villagers}, "roles": roles, "start": "setup",
                 "nodes": nodes}
    if spec.get("graves"):
        doc["requirement"]["if"] = {"min_graves": spec["graves"]}
    if cc.GUARDIANS_WORDS.search(row["title"]):
        doc["title_variants"] = [{"if": G_IF, "title": guardians_form(row["title"])}]
    if any(cc.GUARDIANS_WORDS.search(json.dumps(x)) for x in (row["title"], desc, nodes)):
        doc["patches"] = ["guardians_of_isola"]
    return doc, problems


# ---- guardians-wording.md ---------------------------------------------------------------------------------------------

GUARDIANS_START = "<!-- HE Guardians rows: written by scripts/drafts_d/gen_heathen_events.py -->"
GUARDIANS_END = "<!-- end of the HE Guardians rows -->"


def write_guardians_doc(docs: list[dict]) -> None:
    p = ROOT / "docs" / "event-collection" / "guardians-wording.md"
    body = [GUARDIANS_START, "",
            "## New Believers' Heathen-Exclusive Events (HE-01 to HE-45)", "",
            "The owner's approved draft (2026-11-23): with Guardians of Isola Rewrite every text below reads with the "
            "owner's pairs, made in this order in the title, the pages, a label and the Pick Island Event sentence: "
            "a Heathen -> an Isolan, Heathens -> Isolans (Heathens' -> Isolans'), Heathen -> Isolan. Nobody is called "
            "\"Guardians\".", "",
            "| Event | Where | Before | After |", "|---|---|---|---|"]
    for doc in docs:
        texts = json.dumps([doc["title"], doc["collection"]["description"], doc["nodes"]])
        for before, after in HEATHEN_PAIRS:
            if before in texts:
                body.append(f"| `{doc['collection']['id']}` | its texts | {before} | {after} |")
                texts = texts.replace(before, after)
    body += ["", GUARDIANS_END]
    s = p.read_text(encoding="utf-8")
    if GUARDIANS_START in s:
        a, b = s.index(GUARDIANS_START), s.index(GUARDIANS_END) + len(GUARDIANS_END)
        s = s[:a] + "\n".join(body) + s[b:]
    else:
        s = s.rstrip("\n") + "\n\n" + "\n".join(body) + "\n"
    p.write_text(s, encoding="utf-8", newline="\n")


# ---- heathen_roles.json: the Heathen-Exclusive Events' rows ------------------------------------------------------------

def write_heathen_roles(docs: list[dict]) -> None:
    """Each event's Heathen roles in data/event_collection/heathen_roles.json (cie-v6-binary.md 45, applied before the
    build validates an event): every villager role "only", and "exclusive": true where no believer is cast (all but
    HE-13 and HE-25).  Every other event's row is left as it is."""
    p = lib.COLLECTION_DIR / "heathen_roles.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    events = {k: v for k, v in (data.get("events") or {}).items() if not re.match(r"^he\d\d_", k)}
    for doc in docs:
        roles = {rid: r["heathens"] for rid, r in doc["roles"].items() if r.get("heathens")}
        believers = [rid for rid, r in doc["roles"].items() if r["kind"] == "villager" and not r.get("heathens")]
        entry: dict = {"roles": roles}
        if not believers:
            entry["exclusive"] = True
        events[doc["collection"]["id"]] = entry
    data["events"] = dict(sorted(events.items()))
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


# ---- The files --------------------------------------------------------------------------------------------------------

def rows() -> list[dict]:
    data = json.loads(lib.MANIFEST.read_text(encoding="utf-8"))
    return sorted((r for r in data["rows"] if r.get("source") == SID and r["kind"] == "event"),
                  key=lambda r: r["lines"][0])


def all_docs() -> tuple[list[tuple[Path, dict]], list[str]]:
    docs, problems = [], []
    with lib.use_source(SID):
        for r in rows():
            doc, probs = build(r)
            problems += probs
            docs.append((OUT_DIR / f"{r['id']}.json", doc))
    if len(docs) != 45 or set(HE) != set(range(1, 46)):
        problems.append(f"{len(docs)} events, {len(HE)} specs")
    return docs, problems


def sheet() -> str:
    out = []
    for p, doc in all_docs()[0]:
        out.append(f"### {doc['title']} | {json.dumps(doc['roles'])}")
        for nid, nd in doc["nodes"].items():
            out.append(f"  [{nid}] {nd.get('text', '')}")
            for c in nd.get("choices", []):
                out.append(f"    > {c['label']}")
            for e in nd.get("effects", []):
                out.append(f"    * {json.dumps({k: v for k, v in e.items() if k != 'src'})}")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if argv[:1] == ["--sheet"]:
        print(sheet())
        return 0
    docs, problems = all_docs()
    for p in problems:
        print("PROBLEM", p)
    paths = []
    for p, doc in docs:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(cc.canonical(cc.with_outcome_effects(doc, p)), encoding="utf-8", newline="\n")
        paths.append(str(p))
    write_guardians_doc([d for _p, d in docs])
    write_heathen_roles([d for _p, d in docs])
    rc = subprocess.call([sys.executable, str(ROOT / "scripts" / "collection_check.py"), "--format", *paths])
    return rc or (1 if problems else 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
