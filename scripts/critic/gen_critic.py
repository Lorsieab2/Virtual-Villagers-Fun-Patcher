"""Build "(Name1)'s Harshest Critic" (the owner's event, 2026-11-16, Expanded v3) as six collection files.

    python scripts/critic/gen_critic.py            # write data/event_collection/critic/hc/<id>.json, then check them
    python scripts/critic/gen_critic.py --review   # print every pronoun's owner, for reading

The source is the owner's file frozen byte for byte (collection_lib.CRITIC; docs/event-collection/authoring-rules.md
15i).  It is a random-pool event in the Cooking Contest's layout: a setup with letter slots (A the profession, B the
task, T the difficulty, C the privilege, C2 a flavor line, D the punishment, E the line before the question), four
choices whose labels are drawn from the owner's label lists, a first popup per choice, and 112 routes, each drawn at
random with equal chance.  The owner's text is kept: every slot is a pool (a "(a / b / c)" list is a pool of its own,
each item the owner's words), every pool line is an item.  The profession decides the skill (the owner's rules at the
top of the file): a branch picks the skill group first, and every profession-, task- and quote-pool line of a group
carries {"visited": "g_<group>"}; a skill reward is a branch over the groups.

The routes are too much text for one .cieg (CG_MAX_FILE), so the event is six files, one route family each, one series
(collection_manifest.CRITIC_ROWS).  Each file holds the whole setup and the pools its routes name.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import collection_lib as lib  # noqa: E402

OUT = lib.CRITIC_DIR / "hc"
SRC = lib.CRITIC_ID
GROUPS = ("farm", "build", "res", "heal", "par", "dev")
SKILLS = {"farm": ["Farming"], "build": ["Building"], "res": ["Research"], "heal": ["Healing"],
          "par": ["Parenting"],
          # the owner's Devotion rule (top of the file): VV5 Devotion or a skill that fits the task, VV1-VV4 one that
          # fits (reading omens and old texts = Research, teaching the old prayers = Parenting); a skill a game lacks
          # is skipped
          "dev": ["Devotion", "Research", "Parenting"]}
POTION_SKILLS = ["Research", "Healing"]      # the owner: potions, remedies, poultices = Research OR Healing
SIZES = {"small": (5, 10), "normal": (10, 20), "large": (20, 40)}

# ---- the source ----------------------------------------------------------------------------------------------------

CUTS = {   # ledger text cuts: words on a line that are a note or a label, never shown
    692: ["(the second sentence only sometimes)"],
    2057: ["(mentor):"],
    2058: ["(name2):"],
    2059: ["an official:"],
    2060: ["(name1):"],
}
NOTE_LINES = {2, 3, 4, 6, 7, 8, 9, 10, 11, 1070, 1080, 1103, 1156, 1157, 1211, 1212, 1213, 1214, 1296, 1297, 1298,
              1376, 1377, 1616, 1617, 1618, 1619, 1620, 1621, 1622, 1623, 1624, 1859, 1860, 1861, 1862, 1863, 2036,
              2037, 2038, 2101, 2102}
GRAMMAR = [   # docs/event-collection/grammar-fixes.md rows "| critic L<n> |"
    {"src": "L762", "before": "(Name1) (C-result).", "after": "The reward: (C-result)."},
]


def raw(n: int) -> str:
    s = lib.normalize_source_text(lib.line(n)).rstrip("\r")
    for c in CUTS.get(n, []):
        s = s.replace(c, " ")
    for f in GRAMMAR:
        if f["src"] == f"L{n}":
            s = s.replace(f["before"], f["after"])
    return s


def clean(n: int) -> str:
    return re.sub(r"\s+", " ", lib.strip_structural(raw(n))).strip()


def fmt(lines: list[int]) -> str:
    out, run = [], None
    for n in sorted(lines):
        if run and n == run[1] + 1:
            run[1] = n
        else:
            if run:
                out.append(lib.fmt_src(*run))
            run = [n, n]
    out.append(lib.fmt_src(*run))
    return ",".join(out)


def split_top(s: str, sep: str = "/") -> list[str]:
    parts, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return [p.strip() for p in parts]


def pick(s: str, alt: str) -> str:
    """`s` with the "(a / b / c)" group that holds `alt` as one alternative replaced by `alt` (a src_pick page)."""
    i = 0
    while True:
        i = s.find("(", i)
        if i < 0:
            raise ValueError(f"{alt!r} is no alternative of a group in {s!r}")
        j = close_of(s, i)
        if alt in split_top(s[i + 1:j]):
            return s[:i] + alt + s[j + 1:]
        i += 1


def close_of(s: str, i: int) -> int:
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "(":
            depth += 1
        elif s[j] == ")":
            depth -= 1
            if depth == 0:
                return j
    raise ValueError(f"unclosed parenthesis in {s!r}")


# ---- converting the owner's words into the format's tokens ---------------------------------------------------------

PRONOUNS = {"he/she": "he/she", "his/her": "his/her", "him/her": "him/her", "himself/herself": "himself/herself",
            "him/herself": "himself/herself"}
ASIDES = {"somehow", "good luck", "which nobody has ever managed", "nobody has ever done this", "yes, it's spiky"}
SINGLES = {"healing", "an official", "a new treatment or medicine", "a faraway village",
           "a ridiculously complicated dish", "COCONUT CREAM", "a notoriously hard idea"}
SLOTS = {"A": "PROF", "B": "TASK", "C": "PRIV", "C-result": "PRIV", "D": "PUN", "T": "DIFF", "E": "FLAV",
         "F": "F", "G": "G", "H": "H", "K": "K", "L": "L", "M": "M", "N": "N", "O": "O", "P": "P", "Q": "Q", "Y": "Y",
         "Z1": "Z1", "Z2": "Z2", "Z3": "Z3", "Z4": "Z4", "Z5": "Z5", "Z6": "Z6", "Z7": "Z7", "Z8": "Z8",
         "SA": "SA", "SB": "SB", "SP": "SP", "number": "NUMBER", "thing": "JOB", "crop": "CROP",
         "recipient": "p125_0"}

# The owner of each pronoun, where the nearest name before it is not the one meant: {line: [role, ...]} in the order
# the pronouns stand on the line (None keeps the guess).  Read with --review.
OWNERS: dict[int, list] = {
    481: ["subject"], 496: ["chief"], 507: ["official"], 599: ["subject"], 604: ["subject"], 633: ["subject"],
    640: ["subject"], 659: ["subject"], 666: ["subject"], 674: ["subject", "subject"], 737: ["subject", "subject"],
    745: ["subject"], 789: ["subject"], 811: ["subject"], 813: ["subject", "subject"], 830: ["subject"],
    1119: ["subject"], 1251: ["subject"], 1352: ["examiner"], 1437: ["chief"], 1482: ["patient"],
    1528: ["official"], 1608: ["subject"], 1738: ["official"], 1778: ["examiner"], 1780: ["elder"],
    1968: ["subject"], 2019: ["subject"], 2058: ["rival"], 2077: ["official"], 2080: [None, "subject"],
}
UNKNOWN: set[str] = set()
SEEN: set = set()


class State:
    def __init__(self, n: int, default: str, name2: str):
        self.n, self.last, self.name2 = n, default, name2
        self.k = 0          # slash groups made on the line
        self.p = 0          # pronouns met on the line
        self.log: list[tuple[str, str]] = []

    def owner(self, word: str) -> str:
        fix = OWNERS.get(self.n, [])
        got = fix[self.p] if self.p < len(fix) and fix[self.p] else self.last
        self.p += 1
        self.log.append((word, got))
        return got


class Conv:
    """Turns source text into the file's text, making the pools its "(a / b)" lists are."""

    def __init__(self):
        self.pools: dict[str, dict] = {}
        self.review: list[tuple[int, str, list]] = []

    def text(self, s: str, n: int, src: str, st: State, slots: dict) -> str:
        out, i = [], 0
        while i < len(s):
            if s[i] == "(":
                j = close_of(s, i)
                out.append(self.group(s[i + 1:j], n, src, st, slots))
                i = j + 1
            else:
                k = s.find("(", i)
                k = len(s) if k < 0 else k
                out.append(chief_words(s[i:k]))
                i = k
        return "".join(out)

    def group(self, inner: str, n: int, src: str, st: State, slots: dict) -> str:
        key = inner.strip()
        kl = key.lower()
        role = {"name1": "subject", "mentor": "mentor", "name2": st.name2, "name3": "prankster"}.get(kl)
        if role:
            st.last = role
            return "(" + (role.upper() if key.isupper() else role.capitalize() if key[0].isupper() else role) + ")"
        if kl in PRONOUNS:
            w = PRONOUNS[kl]
            if key[0].isupper():
                w = "/".join(x.capitalize() for x in w.split("/"))
            return f"({st.owner(key)}.{w})"
        if key in slots:
            return "{" + slots[key] + "}"
        if key in ASIDES:
            return "\\(" + key + "\\)"
        if key in SINGLES:
            name = f"p{n}_{st.k}"
            st.k += 1
            self.pools.setdefault(name, {"items": [{"text": key, "src": src}]})
            return "{" + name + "}"
        alts = split_top(inner)
        if len(alts) < 2:
            UNKNOWN.add(f"L{n}: ({inner})")
            return "(" + inner + ")"
        name = f"p{n}_{st.k}"
        st.k += 1
        last = st.last
        items = []
        for a in alts:
            st.last = last
            items.append(item(self.text(a, n, src, st, slots), src))
        st.last = last
        self.pools.setdefault(name, {"items": items})
        return "{" + name + "}"


def chief_words(s: str) -> str:
    """The Chief outside A New Home's ... The Secret City's: the game words (authoring-rules.md 10)."""
    def one(m: re.Match) -> str:
        w = m.group(0)
        if w.lower().startswith("the "):
            return "{@Chief}" if w[0] == "T" else "{@chief}"
        return "{@chiefs}" if w.lower().endswith("s") else "{@chiefw}"
    return re.sub(r"\b(?:[Tt]he [Cc]hief\b(?!s)|[Cc]hiefs\b|[Cc]hief\b)", one, s)


WORDS = {"chief": {"3": "the Chief", "*": "the village leader"},
         "Chief": {"3": "The Chief", "*": "The village leader"},
         "chiefw": {"3": "chief", "*": "leader"},
         "chiefs": {"3": "chiefs", "*": "leaders"}}


def item(text: str, src: str, cond=None) -> dict:
    d = {"text": text, "src": src}
    if cond is not None:
        d["if"] = cond
    return d


# ---- the event ------------------------------------------------------------------------------------------------------

def visited(g: str) -> dict:
    return {"visited": f"g_{g}"}


NOT_DEV = {"not": visited("dev")}


def copy_v(g: str, c: int) -> dict:
    return {"visited": f"c_{g}{c}"}


class Builder:
    """Everything one file needs: the setup (every file) and its route family."""

    def __init__(self, fid: str, review: bool = False):
        self.fid = fid
        self.cv = Conv()
        self.nodes: dict[str, dict] = {}
        self.pools: dict[str, dict] = {}
        self.consumed: set[int] = set()
        self.review = review
        self.reviewed: list = []
        self.text_only: dict[str, list] = {}

    # -- text helpers
    def conv(self, lines: list[int], default="subject", name2="master", slots=None, picks=None) -> str:
        s = " ".join(clean(n) for n in lines)
        for _n, alt in (picks or []):
            s = pick(s, alt)
        st = State(lines[0], default, name2)
        src = fmt(lines)
        out = self.cv.text(s, lines[0], src, st, slots or SLOTS)
        if st.log:
            self.reviewed.append((src, s, st.log))
        self.consumed.update(lines)
        return out

    def items(self, ranges, cond=None, default="subject", name2="master", split=False, slots=None) -> list[dict]:
        out = []
        for a, b in ranges:
            for n in range(a, b + 1):
                if lib.is_blank_or_separator(n) or n in NOTE_LINES:
                    continue
                if not clean(n):
                    continue
                if split:
                    for alt in split_top(clean(n)):
                        st = State(n, default, name2)
                        out.append(item(self.cv.text(alt, n, f"L{n}", st, slots or SLOTS), f"L{n}", cond))
                        if st.log:
                            self.reviewed.append((f"L{n}", alt, st.log))
                else:
                    st = State(n, default, name2)
                    out.append(item(self.cv.text(clean(n), n, f"L{n}", st, slots or SLOTS), f"L{n}", cond))
                    if st.log:
                        self.reviewed.append((f"L{n}", clean(n), st.log))
                self.consumed.add(n)
        return out

    def pool(self, name: str, items: list[dict]) -> None:
        assert items, name
        self.pools[name] = {"items": items}

    def node(self, nid: str, **kw) -> str:
        assert nid not in self.nodes, nid
        self.nodes[nid] = {k: v for k, v in kw.items() if v is not None}
        return nid


# Profession lines, the skill group of every pool line (the owner's B, T, C ... banks).
PROF_LINES = {"farm": [(51, 51), (56, 58), (70, 74)], "build": [(52, 52), (59, 61), (75, 79)],
              "res": [(53, 53), (62, 64), (80, 84)], "heal": [(54, 54), (65, 66), (85, 89)],
              "par": [(55, 55), (67, 68), (90, 94)], "dev": [(95, 116)]}
TASK_LINES = {"farm": [(119, 134), (136, 152), (361, 367)], "build": [(154, 164), (166, 182), (369, 375)],
              "res": [(184, 193), (195, 211), (213, 232), (377, 383)],
              "heal": [(234, 244), (246, 262), (385, 390)], "par": [(264, 271), (274, 290), (392, 397)],
              "dev": [(293, 332), (399, 403)]}
TASK_ANY = [(336, 353), (405, 408)]
NAMED_LINES = {"farm": [(1217, 1224)], "build": [(1227, 1234)], "res": [(1237, 1244)], "heal": [(1247, 1254)],
               "par": [(1257, 1264)], "dev": [(1267, 1278)]}
POTION_PROFS = ("alchemist", "potion maker", "maker of poultices")
MOCKING = {927, 930, 969, 978, 1085}   # G quotes aimed at the person, not the work (left out in Variant 2)
ROMANCE = {1507, 1698, 1706}           # a proposal or a marriage: only when (name1) is an adult
NUMBER_SRC = [("two", 223), ("three", 221), ("five", 220), ("seven", 319), ("nine", 222), ("twelve", 306),
              ("forty", 427)]
CROP_SRC = [("taro", 131), ("fruit", 152)]


def setup(b: Builder, with_c2: bool = True) -> None:
    """The setup, its pools and the four choices' first popups (every file)."""
    cv = b.cv
    # Each group's four question copies (branch nodes c_<group><k>, all visited conditions: a run-time "drew" fact per
    # profession would make the checks try every combination of them):
    #   1: the professions whose "a (A)" and "(A)s" read right, the group's tasks;
    #   2: the same professions, the named master challenges only (their difficulty lines need one);
    #   3: the other professions ("an alchemist", "keepers of the gardens"), the group's tasks;
    #   4: the potion and poultice makers (Research, Healing: Research OR Healing, the owner's rule), else as 3.
    # A line that says "a (A)" or "(A)s" is never drawn on copies 3 and 4.
    prof = []
    b.odd_copies = []
    for g in GROUPS:
        items = b.items(PROF_LINES[g], None, split=True)
        potion = [i for i in items if i["text"] in POTION_PROFS]
        odd = [i for i in items if i not in potion and (i["text"][0] in "aeiou" or re.search(
            r" (?:of|to|between)\b", i["text"]) or i["text"].endswith(("s", "wife")))]
        normal = [i for i in items if i not in potion and i not in odd]
        assert normal and odd, g
        for i in normal:
            i["if"] = {"any": [copy_v(g, 1), copy_v(g, 2)]}
        for i in odd:
            i["if"] = copy_v(g, 3) if potion else {"any": [copy_v(g, 3), copy_v(g, 4)]}
        for i in potion:
            i["if"] = copy_v(g, 4)
        prof += items
        b.odd_copies += [copy_v(g, 3), copy_v(g, 4)]
    texts = [i["text"] for i in prof]
    assert len(texts) == len(set(texts)), "profession texts repeat"
    b.pool("PROF", prof)
    b.potion = None
    # tasks: the group's own and (not for Devotion) the any-profession ones; the named master challenges on copy 2
    task, named = [], []
    for g in GROUPS:
        task += b.items(TASK_LINES[g], visited(g), name2="master")
        named += b.items(NAMED_LINES[g], visited(g), name2="master")
    task += b.items(TASK_ANY, NOT_DEV)
    b.pool("TASK", task)
    b.pool("TASKN", named)          # copy 2's question names this pool for "(B)"
    b.pool("NUMBER", [item(w, f"L{n}") for w, n in NUMBER_SRC])
    b.pool("CROP", [item(w, f"L{n}") for w, n in CROP_SRC])
    # T: every profession; Devotion's own; the named master's only after a named master challenge (copy 2)
    b.pool("DIFF", b.items([(413, 514)]) + b.items([(517, 541)], visited("dev"))
           + b.items([(1281, 1292)], {"any": [copy_v(g, 2) for g in GROUPS]}, name2="master"))
    b.pool("PRIV", b.items([(544, 588)]) + b.items([(614, 629)], visited("dev")))
    b.pool("C2", b.items([(590, 612)]))
    b.pool("PUN", b.items([(632, 679)]) + b.items([(829, 844)], visited("dev")))
    b.pool("FLAV", b.items([(681, 688), (691, 715), (718, 733)]) + b.items([(847, 861)], visited("dev")))
    for letter, first, alts in (("A", 735, (742, 745)), ("B", 736, (746, 749)), ("C", 737, (750, 753)),
                                ("D", 738, (754, 757))):
        b.pool(f"FP{letter}", b.items([(first, first), alts]))
    b.pool("V2", b.items([(1158, 1169), (1172, 1189)]) + b.items([(1192, 1206)], visited("dev"), default="mentor"))
    # the four choices' label lists (one from each list per question)
    labels = {"A": [], "B": [], "C": [], "D": []}
    for letter, first, more in (("A", 22, 27), ("B", 23, 28), ("C", 24, 29), ("D", 25, 30)):
        for n in (first, more):
            for alt in split_top(clean(n)):
                labels[letter].append((alt, n))
    for n in range(33, 49):
        letter = re.match(r"^\[new\] Choice ([A-D]):", lib.normalize_source_text(lib.line(n))).group(1)
        for alt in split_top(clean(n)):
            labels[letter].append((alt, n))
    assert {k: len(v) for k, v in labels.items()} == {"A": 21, "B": 21, "C": 21, "D": 21}, \
        {k: len(v) for k, v in labels.items()}
    b.consumed.update(range(22, 26))
    b.consumed.update(range(27, 31))
    b.consumed.update(range(33, 49))

    def label(alt: str, n: int) -> str:
        st = State(n, "subject", "master")
        return lib.title_case_label(cv.text(alt, n, f"L{n}", st, SLOTS))

    # the question: 6 groups x 4 copies, each copy one label set (21 sets, the first three again); "C2 ... sometimes":
    # two copies of each group's four show it
    qtext = b.conv([15, 16, 17])
    diff = b.conv([18])
    flav = b.conv([19])
    ask = b.conv([20])
    assert (diff, flav) == ("{DIFF}", "{FLAV}"), (diff, flav)
    b.node("start", type="branch", children=[{"next": f"g_{g}"} for g in GROUPS])
    k = 0
    for gi, g in enumerate(GROUPS):
        kids = []
        for c in range(4):
            s = k % 21
            k += 1
            qid = f"q_{g}{c + 1}"
            body = "\n".join([qtext.replace("{TASK}", "{TASKN}") if c == 1 else qtext]
                             + (["{C2}"] if c in (0, 2) else []) + ["{DIFF}", "{FLAV}", ask])
            b.node(qid, type="question", text=body, src="L15-20", choices=[
                {"label": label(*labels[L][s]), "next": f"fp{L}", "src": f"L{labels[L][s][1]}"}
                for L in "ABCD"])
            b.node(f"c_{g}{c + 1}", type="branch", children=[{"next": qid}])
            kids.append({"next": f"c_{g}{c + 1}"})
        b.node(f"g_{g}", type="branch", children=kids)
    for L in "ABCD":
        b.node(f"fp{L}", text="{FP" + L + "}", children=[{"next": "routes"}])
    b.node("end", type="branch")


# ---- rewards, Variant 2 --------------------------------------------------------------------------------------------

def skill_fx(role: str, skills: list[str], size: str) -> dict:
    lo, hi = SIZES[size]
    return {"do": "skill", "role": role, "skills": skills, "min": lo, "max": hi}


def reward(b: Builder, key: tuple) -> str:
    """A branch giving each (role, size) of `key` the profession's skill; "end" for no reward."""
    if not key:
        return "end"
    nid = "rw_" + "_".join(f"{r}{s[0]}" for r, s in key)
    if nid in b.nodes:
        return nid
    kids = []
    for g in GROUPS:
        gid = f"{nid}_{g}"
        if g in ("res", "heal"):
            b.node(f"{gid}p", type="branch", effects=[skill_fx(r, POTION_SKILLS, s) for r, s in key])
            b.node(f"{gid}n", type="branch", effects=[skill_fx(r, SKILLS[g], s) for r, s in key])
            b.node(gid, type="branch", children=[{"next": f"{gid}p", "if": copy_v(g, 4), "else": f"{gid}n"}])
        else:
            b.node(gid, type="branch", effects=[skill_fx(r, SKILLS[g], s) for r, s in key])
        kids.append({"next": gid, "if": visited(g)})
    b.node(nid, type="branch", children=kids)
    return nid


def v2_page(b: Builder, key: tuple) -> str:
    """Variant 2's kind word after a fail or a stumble; "the lesson sticks": a small gain when the route gives none."""
    nid = "v2_" + ("_".join(f"{r}{s[0]}" for r, s in key) or "none")
    if nid not in b.nodes:
        after = key if any(r == "subject" for r, _ in key) else tuple(sorted(key + (("subject", "small"),)))
        b.node(nid, popup="append", join="paragraph", text="{V2}", children=[{"next": reward(b, after)}])
    return nid


def after(b: Builder, key: tuple, coda: bool) -> str:
    """What follows an outcome's page: Variant 2's word half the time (a fail or stumble), then the reward."""
    if not coda:
        return reward(b, key)
    nid = "cd_" + ("_".join(f"{r}{s[0]}" for r, s in key) or "none")
    if nid not in b.nodes:
        b.node(nid, type="branch", children=[{"next": v2_page(b, key)}, {"next": reward(b, key)}])
    return nid


# ---- routes ---------------------------------------------------------------------------------------------------------
# Each outcome: (its lines, skill key, coda, page effects).  The owner's EFFECT words, on the skill table's sizes
# (authoring-rules.md 9): +5 / +5-10 small, +10 / +10-15 / +10-20 / +15 normal, +15-25 / +20 / +20-30 large.

S, N_, L_ = "small", "normal", "large"
TEXT_ONLY = {   # an effect-table word on a page that promises nothing the page itself does
    "r49f": [{"src": "L1583", "what": "asking for help is a skill",
              "reason": "a figure of speech; the route's own small skill gain is made on the step after this page"}],
    "r82": [{"src": "L1992", "what": "a yearly celebration of spectacular mistakes",
             "reason": "rule 7: a festival the village plans is told only"}],
    "r84": [{"src": "L1998", "what": "a celebrated mistake", "reason": "describes the mistake, not a celebration"}],
}
HAPPY = [{"do": "mood", "role": "subject", "mood": "good"}, {"do": "mood", "role": "mentor", "mood": "good"}]
HAPPY_SUBJECT = [{"do": "mood", "role": "subject", "mood": "good"}]


def k(*pairs) -> tuple:
    return tuple(sorted(pairs))


def page(b: Builder, nid: str, lines, nxt: str, fx=None, slots=None, picks=None, default="subject",
         name2="master", text_only=None, new=False) -> str:
    text = b.conv(list(lines), default=default, name2=name2, slots=slots, picks=picks)
    kw = {} if new else {"popup": "append", "join": "paragraph"}
    if picks:
        kw["src_pick"] = [{"src": f"L{n}", "alt": a} for n, a in picks]
    b.node(nid, text=text, src=fmt(list(lines)), effects=fx or None, children=[{"next": nxt}],
           text_only=text_only or TEXT_ONLY.get(nid), **kw)
    return nid


def simple(b, rid, lines, key=(), coda=False, fx=None, **kw) -> str:
    return page(b, rid, lines, after(b, key, coda), fx=fx, **kw)


def branching(b, rid, lead, outs, fx=None, **kw) -> str:
    """A lead page, then equally likely outcomes [(suffix, lines, key, coda, fx)]."""
    kids = []
    for suf, lines, key, coda, ofx in outs:
        kids.append({"next": page(b, f"{rid}{suf}", lines, after(b, key, coda), fx=ofx, **kw)})
    b.node(f"{rid}_br", type="branch", children=kids)
    return page(b, rid, lead, f"{rid}_br", fx=fx, **kw)


def core_pools(b: Builder) -> None:
    v2g = {"not": {"any": [{"visited": "r2_v2"}, {"visited": "r4f_v2"}]}}
    gen = []
    for a, bb in ((927, 978), (980, 1012)):
        for n in range(a, bb + 1):
            if lib.is_blank_or_separator(n):
                continue
            gen += b.items([(n, n)], v2g if n in MOCKING else None, default="mentor")
    b.pool("F", b.items([(864, 879), (881, 908)], default="mentor")
           + b.items([(910, 924)], visited("dev"), default="mentor"))
    g2 = []
    for g, rs in (("farm", [(1048, 1053)]), ("build", [(1055, 1064)]), ("res", [(1066, 1069), (1071, 1075)]),
                  ("heal", [(1077, 1079), (1081, 1084)]), ("par", [(1087, 1091)])):
        g2 += b.items(rs, visited(g), default="mentor")
    g2 += b.items([(1085, 1085)], {"all": [visited("heal"), v2g]}, default="mentor")
    b.pool("G", gen + b.items([(1014, 1044)], visited("dev"), default="mentor") + g2)
    b.pool("H", b.items([(1094, 1102), (1104, 1119), (1122, 1137)])
           + b.items([(1139, 1153)], visited("dev")))
    b.pool("JOB", [item(w.strip(), f"L{n}") for n in (356, 357) for w in clean(n).split(",") if w.strip()])


def routes_core(b: Builder) -> list:
    core_pools(b)
    R = []
    R.append(simple(b, "r1", [761, 762], k(("subject", L_))))
    # R2: Variant 2 decided first, so its mentor never mocks (name1) as a person
    page(b, "r2_v1", [765, 766], "end")
    page(b, "r2_v2", [765, 766], v2_page(b, ()))
    R.append(b.node("r2", type="branch", children=[{"next": "r2_v1"}, {"next": "r2_v2"}]))
    R.append(simple(b, "r3", [769, 770], k(("subject", S))))
    page(b, "r4p", [774], after(b, k(("subject", N_)), True))
    page(b, "r4f_v1", [775], "end")
    page(b, "r4f_v2", [775], v2_page(b, ()))
    b.node("r4f", type="branch", children=[{"next": "r4f_v1"}, {"next": "r4f_v2"}])
    b.node("r4_br", type="branch", children=[{"next": "r4p"}, {"next": "r4f"}])
    R.append(page(b, "r4", [773], "r4_br"))
    R.append(branching(b, "r5", [778, 779], [("p", [780], k(("subject", N_)), True, HAPPY),
                                             ("f", [781], (), True, None)]))
    R.append(simple(b, "r6", [784, 785, 786], k(("subject", N_)), default="mentor"))
    page(b, "r7p", [789, 790], reward(b, k(("subject", N_), ("mentor", N_))), picks=[(790, "passing")])
    page(b, "r7f", [789, 790], after(b, (), True), picks=[(790, "failing")])
    R.append(b.node("r7", type="branch", children=[{"next": "r7p"}, {"next": "r7f"}]))
    page(b, "r8c", [793, 794, 795], reward(b, k(("subject", N_))))
    page(b, "r8n", [793, 794, 795], "end")
    R.append(b.node("r8", type="branch", children=[{"next": "r8c"}, {"next": "r8n"}]))
    R.append(simple(b, "r9", [799], k(("subject", N_))))
    R.append(simple(b, "r10", [801], k(("subject", N_)), fx=HAPPY))
    R.append(simple(b, "r11", [803], k(("subject", N_))))
    R.append(simple(b, "r12", [805], k(("subject", S))))
    R.append(simple(b, "r13", [807], k(("subject", S)), fx=HAPPY))
    R.append(simple(b, "r14", [809], k(("subject", S))))
    R.append(simple(b, "r15", [811], k(("subject", L_))))
    R.append(simple(b, "r16", [813], (), True))
    b.node("r17_tech", type="branch", effects=[{"do": "tech", "size": "small", "scaled": True}],
           children=[{"next": reward(b, k(("subject", N_)))}])
    page(b, "r17", [815], "x")
    b.nodes["r17"]["children"] = [{"next": "r17_tech", "if": visited("res"), "else": reward(b, k(("subject", N_)))}]
    R.append("r17")
    R.append(simple(b, "r18", [817], k(("subject", N_))))
    R.append(simple(b, "r19", [819], k(("subject", S))))
    R.append(simple(b, "r20", [821]))
    R.append(simple(b, "r21", [823], k(("subject", S))))
    R.append(simple(b, "r22", [825], k(("subject", S)), True))
    R.append(simple(b, "r23", [827], k(("subject", S)), fx=HAPPY))
    return R


def routes_pleas(b: Builder) -> list:
    R = []
    R.append(branching(b, "r24", [1301], [("p", [1302], k(("subject", S)), False, None),
                                          ("f", [1303], (), True, None)]))
    R.append(branching(b, "r25", [1306], [("p", [1307], k(("subject", S)), False, None),
                                          ("f", [1308], (), True, None)]))
    R.append(branching(b, "r26", [1311], [("v", [1312], k(("subject", N_)), False, None),
                                          ("m", [1313], k(("subject", S)), False, None)]))
    R.append(branching(b, "r27", [1316], [("p", [1317], k(("subject", N_)), False, None),
                                          ("f", [1318], (), True, None)]))
    R.append(simple(b, "r28", [1321], k(("subject", S)), True))
    R.append(branching(b, "r29", [1324], [("p", [1325], k(("subject", N_)), False, HAPPY),
                                          ("f", [1326], (), True, None)]))
    R.append(branching(b, "r30", [1329], [("u", [1330], k(("subject", N_)), False, None),
                                          ("d", [1331], k(("subject", N_)), False, None),
                                          ("f", [1332], (), True, None)]))
    R.append(simple(b, "r31", [1335], k(("subject", N_))))
    R.append(simple(b, "r32", [1338], k(("subject", N_))))
    R.append(simple(b, "r33", [1341], k(("subject", S)), fx=HAPPY))
    R.append(simple(b, "r34", [1344], (), True))
    R.append(simple(b, "r35", [1347], k(("subject", N_))))
    R.append(branching(b, "r36", [1350], [("p", [1351], k(("subject", N_)), False, None),
                                          ("f", [1352], k(("subject", S)), True, None)]))
    R.append(simple(b, "r37", [1355], fx=HAPPY))
    R.append(branching(b, "r38", [1358], [("p", [1359], k(("subject", N_)), False, None),
                                          ("f", [1360], k(("subject", S)), True, None)]))
    R.append(branching(b, "r39", [1363], [("p", [1364], k(("subject", N_)), False, None),
                                          ("f", [1365], k(("subject", S)), True, None)]))
    R.append(simple(b, "r40", [1368], k(("subject", N_))))
    R.append(simple(b, "r41", [1371], k(("subject", N_)), fx=HAPPY_SUBJECT))
    return R


def disaster_pools(b: Builder) -> None:
    k_items = b.items([(1380, 1404)])
    for g, (a, z) in zip(GROUPS, ((1407, 1424), (1427, 1444), (1447, 1464), (1467, 1484), (1487, 1504),
                                  (1507, 1524))):
        for n in range(a, z + 1):
            if lib.is_blank_or_separator(n):
                continue
            cond = visited(g)
            if n in ROMANCE:
                cond = {"all": [cond, {"age": {"role": "subject", "min": 18}}]}
            k_items += b.items([(n, n)], cond)
    b.pool("K", k_items)
    b.pool("L", b.items([(1527, 1538)]))
    b.pool("M", b.items([(1541, 1555)], default="mentor"))


def routes_disasters(b: Builder) -> list:
    disaster_pools(b)
    R = []
    R.append(simple(b, "r42", [1558], (), True))
    b.node("r43_dis", type="branch", effects=[{"do": "preference", "role": "subject", "list": "dislikes",
                                                "preference": "thunder"}], children=[{"next": after(b, (), True)}])
    b.node("r43_br", type="branch", children=[{"next": "r43_dis", "if": {"game": [3, 4, 5]},
                                               "else": after(b, (), True)}, {"next": after(b, (), True)}])
    R.append(page(b, "r43", [1561], "r43_br"))
    R.append(simple(b, "r44", [1564], k(("subject", N_)), fx=HAPPY))
    R.append(simple(b, "r45", [1567], (), True))
    R.append(simple(b, "r46", [1570], (), True, fx=HAPPY))
    R.append(branching(b, "r47", [1573], [("d", [1574], k(("subject", S)), True, None),
                                          ("c", [1575], (), False, None)]))
    R.append(simple(b, "r48", [1578], (), True))
    R.append(branching(b, "r49", [1581], [("p", [1582], k(("subject", N_)), False, None),
                                          ("f", [1583], k(("subject", S)), True, None)]))
    R.append(simple(b, "r50", [1586], (), True))
    R.append(simple(b, "r51", [1589], k(("subject", S))))
    R.append(branching(b, "r52", [1592], [("p", [1593], k(("subject", N_)), False, None),
                                          ("f", [1594], (), True, None)]))
    R.append(simple(b, "r53", [1597], (), True, fx=HAPPY))
    R.append(simple(b, "r54", [1600], k(("subject", S))))
    R.append(simple(b, "r55", [1603], k(("subject", N_)), fx=HAPPY))
    R.append(branching(b, "r56", [1606], [("p", [1607], k(("subject", L_)), False, None),
                                          ("f", [1608], k(("subject", S)), True, None)]))
    R.append(simple(b, "r57", [1611], fx=HAPPY))
    return R


def comic_pools(b: Builder, which: str) -> None:
    n_items = b.items([(1628, 1647)])
    for g, (a, z) in zip(GROUPS, ((1720, 1724), (1728, 1732), (1736, 1740), (1744, 1748), (1752, 1756),
                                  (1760, 1764))):
        n_items += b.items([(a, z)], visited(g))
    b.pool("N", n_items)
    b.pool("O", b.items([(1651, 1670)]))
    b.pool("P", b.items([(1674, 1693)]))
    q = []
    for n in range(1697, 1717):
        q += b.items([(n, n)], {"age": {"role": "subject", "min": 18}} if n in ROMANCE else None)
    b.pool("Q", q)
    b.pool("Y", b.items([(1768, 1782)], default="mentor"))
    b.consumed.update(range(1614, 1785))   # the pools R..X and their headings belong to the comic pools' row


def routes_noises(b: Builder) -> list:
    comic_pools(b, "noises")
    R = []
    R.append(simple(b, "r58", [1790], k(("subject", S)), fx=HAPPY))
    R.append(simple(b, "r59", [1794], fx=HAPPY))
    R.append(simple(b, "r60", [1798]))
    R.append(branching(b, "r61", [1802], [("p", [1803], k(("subject", N_)), False, None),
                                          ("f", [1804], k(("subject", S)), True, None)]))
    R.append(simple(b, "r62", [1808], k(("subject", S)), fx=HAPPY))
    R.append(simple(b, "r63", [1812]))
    R.append(simple(b, "r64", [1816]))
    R.append(simple(b, "r65", [1820], k(("subject", S)), fx=HAPPY))
    R.append(simple(b, "r66", [1824], k(("subject", N_)), fx=HAPPY))
    R.append(simple(b, "r67", [1828], k(("subject", L_)), fx=HAPPY))
    R.append(simple(b, "r68", [1832], k(("subject", S)), fx=HAPPY))
    R.append(simple(b, "r69", [1836]))
    R.append(simple(b, "r70", [1840], fx=HAPPY))
    R.append(branching(b, "r71", [1844], [("p", [1845], k(("subject", N_)), False, None),
                                          ("f", [1846], k(("subject", S)), True, None)]))
    R.append(simple(b, "r72", [1850], k(("subject", S))))
    R.append(simple(b, "r73", [1854], fx=HAPPY))
    return R


def routes_victories(b: Builder) -> list:
    comic_pools(b, "victories")
    b.pool("Z1", b.items([(1866, 1885)]))
    for z, (a, e) in zip(("Z2", "Z3", "Z4", "Z5", "Z6", "Z7"), ((1888, 1895), (1898, 1905), (1908, 1915),
                                                               (1918, 1925), (1928, 1935), (1938, 1945))):
        b.pool(z, b.items([(a, e)]))
    b.pool("Z8", b.items([(1948, 1963)], default="mentor"))
    R = []
    R.append(simple(b, "r74", [1968], k(("subject", N_)), True, fx=HAPPY))
    R.append(simple(b, "r75", [1971], (), True, fx=HAPPY))

    def only(rid, line, g, skill, size, extra):
        lo, hi = SIZES[size]
        page(b, rid, [line], "end", fx=[{"do": "skill", "role": "subject", "skills": skill, "min": lo, "max": hi}]
             + extra)
        return rid
    R.append(("r76", only("r76", 1974, "farm", ["Farming"], N_,
                          [{"do": "food", "size": "small", "scaled": True}]), "farm"))
    R.append(("r77", only("r77", 1977, "build", ["Building"], N_, HAPPY), "build"))
    R.append(("r78", only("r78", 1980, "res", ["Research"], L_, []), "res"))
    R.append(("r79", only("r79", 1983, "heal", ["Healing"], N_, []), "heal"))
    R.append(("r80", only("r80", 1986, "par", ["Parenting"], N_, HAPPY), "par"))
    R.append(("r81", only("r81", 1989, "dev", SKILLS["dev"], N_, HAPPY), "dev"))
    R.append(simple(b, "r82", [1992], fx=HAPPY))
    R.append(simple(b, "r83", [1995], k(("subject", N_))))
    R.append(simple(b, "r84", [1998], k(("subject", S)), fx=HAPPY))
    R.append(simple(b, "r85", [2001], k(("subject", N_)), fx=HAPPY))
    R.append(simple(b, "r86", [2004], (), True, fx=HAPPY))
    R.append(simple(b, "r87", [2007], k(("subject", S)), fx=HAPPY))
    R.append(simple(b, "r88", [2010], k(("subject", N_)), fx=HAPPY))
    R.append(simple(b, "r89", [2013], (), True, fx=HAPPY))
    R.append(simple(b, "r90", [2016], k(("subject", N_)), True, fx=HAPPY))
    R.append(simple(b, "r91", [2019], k(("subject", L_))))
    R.append(simple(b, "r92", [2022], k(("subject", N_)), fx=HAPPY))
    R.append(simple(b, "r93", [2025], k(("subject", N_), ("mentor", S))))
    R.append(simple(b, "r94", [2028], (), True, fx=HAPPY))
    R.append(simple(b, "r95", [2031], k(("subject", N_)), fx=HAPPY))
    return R


def sabotage_pools(b: Builder) -> None:
    sa = []
    for n, gs in ((2041, ["farm"]), (2042, ["build"]), (2043, ["res"]), (2044, ["heal"]), (2045, ["par"]),
                  (2046, ["dev"])):
        sa += b.items([(n, n)], visited(gs[0]), split=True, name2="rival")
    b.pool("SA", sa)
    b.pool("SB", b.items([(2049, 2054)], name2="rival"))
    for name, n, default in (("SCM", 2057, "mentor"), ("SCR", 2058, "rival"), ("SCO", 2059, "official"),
                             ("SCS", 2060, "subject")):
        b.pool(name, b.items([(n, n)], split=True, default=default, name2="rival"))
    # the prank, by the profession its prefix names ("Any" for all)
    sp = []
    for n in range(2105, 2201):
        if lib.is_blank_or_separator(n):
            continue
        pre = re.match(r"^\s*(?:\[(?:new|added|owner)\]\s*)+([A-Za-z/]+(?: \(VV5\))?):",
                       lib.normalize_source_text(lib.line(n)))
        names = [x.lower() for x in pre.group(1).replace(" (VV5)", "").split("/")]
        gs = {"farming": "farm", "building": "build", "research": "res", "healing": "heal", "parenting": "par",
              "devotion": "dev"}
        cond = None if "any" in names else ({"any": [visited(gs[x]) for x in names]} if len(names) > 1
                                            else visited(gs[names[0]]))
        sp += b.items([(n, n)], cond, name2="rival")
    b.pool("SP", sp)
    b.pool("SPC", [item(i["text"], i["src"]) for i in sp if int(i["src"][1:]) in (2105, 2106)])


def routes_sabotage(b: Builder) -> list:
    sabotage_pools(b)
    R = []
    R.append(branching(b, "r96", [2063], [("p", [2064], k(("subject", N_)), False, None),
                                          ("f", [2065], k(("subject", S)), True, None)]))
    b.node("r97_g", type="branch", effects=[{"do": "mood", "role": "subject", "mood": "good"}],
           children=[{"next": reward(b, k(("subject", N_)))}])
    b.node("r97_b", type="branch", effects=[{"do": "mood", "role": "subject", "mood": "bad"}],
           children=[{"next": reward(b, k(("subject", N_)))}])
    b.node("r97_br", type="branch", children=[{"next": "r97_g"}, {"next": "r97_b"}])
    R.append(page(b, "r97", [2068], "r97_br", slots=dict(SLOTS, SC="SCM"), name2="rival"))
    b.node("r98_d", type="branch", effects=[{"do": "preference", "role": "rival", "list": "dislikes",
                                              "preference": "work"}],
           children=[{"next": reward(b, k(("subject", N_)))}])
    b.node("r98_br", type="branch", children=[{"next": "r98_d"}, {"next": reward(b, k(("subject", N_)))}])
    R.append(("r98", page(b, "r98", [2071], "r98_br", slots=dict(SLOTS, SC="SCR"), name2="rival"), "rival"))
    R.append(("r99", page(b, "r99", [2074], reward(b, k(("subject", N_), ("rival", N_))),
                          fx=HAPPY_SUBJECT + [{"do": "mood", "role": "rival", "mood": "good"}],
                          slots=dict(SLOTS, SC="SCR"), name2="rival"), "rival"))
    R.append(page(b, "r100", [2077], reward(b, k(("subject", N_))), fx=HAPPY, slots=dict(SLOTS, SC="SCO"),
                  name2="rival"))
    R.append(page(b, "r101", [2080], reward(b, k(("subject", S))), fx=HAPPY_SUBJECT, slots=dict(SLOTS, SC="SCS"),
                  name2="rival"))
    R.append(simple(b, "r102", [2083], k(("subject", S)), name2="rival"))
    R.append(simple(b, "r103", [2086], k(("subject", L_)), fx=HAPPY, name2="rival"))
    R.append(simple(b, "r104", [2089], k(("subject", N_)), fx=HAPPY_SUBJECT, name2="rival"))
    R.append(simple(b, "r105", [2092], fx=HAPPY, name2="rival"))
    # R106: (S) and (SC) must name the same saboteur, so one page set per saboteur (never (name1) or the prankster,
    # who have no reason line here or cannot be caught by (name1))
    kids = []
    for suf, s_item, sc, need in (("m", "(mentor)", "SCM", None), ("r", "a rival apprentice (rival)", "SCR", "rival"),
                                  ("o", "one of the officials or judges", "SCO", None)):
        b.pool(f"S{suf.upper()}", [item(s_item, "L2036")])
        sl = dict(SLOTS, S=f"S{suf.upper()}", SC=sc)
        lead = branching(b, f"r106{suf}", [2095], [("p", [2096], k(("subject", N_)), False, None),
                                                   ("f", [2097], k(("subject", S)), True, None)],
                         slots=sl, name2="rival")
        kids.append({"next": lead, **({"if": {"role": need}} if need else {})})
    R.append(b.node("r106", type="branch", children=kids))
    R.append(simple(b, "r107", [2203], fx=HAPPY, name2="rival"))
    R.append(("r108", simple(b, "r108", [2206], k(("subject", N_)), slots=dict(SLOTS, SP="SPC"), name2="rival"),
              "prankster"))
    R.append(simple(b, "r109", [2209], k(("subject", S)), name2="rival"))
    # R110: the prank that saves the day is the one the line names (one page per example)
    kids = []
    for suf, lines, alt in (("c", [2105, 2106], "the candles that won't go out keep the ceremony lit through the rain"),
                            ("k", [2130], "the extra coconuts feed the judges"),
                            ("t", [2114], "the tied-together tools stop one from falling into the sea")):
        b.pool(f"SP{suf.upper()}0", [item(i["text"], i["src"]) for i in b.pools["SP"]["items"]
                                     if int(i["src"][1:]) in lines])
        kids.append({"next": page(b, f"r110{suf}", [2212], reward(b, k(("subject", N_))), fx=HAPPY,
                                  slots=dict(SLOTS, SP=f"SP{suf.upper()}0"), picks=[(2212, alt)], name2="rival")})
    R.append(b.node("r110", type="branch", children=kids))
    R.append(simple(b, "r111", [2215], k(("subject", N_)), fx=HAPPY, name2="rival"))
    R.append(simple(b, "r112", [2218], k(("subject", S)), fx=HAPPY, slots=dict(SLOTS, SP="SPC"), name2="rival"))
    return R


FILES = {   # id: (route builder, its add-on rows, Pick Island Event sentence)
    "hc1_routes": (routes_core, ["hc_setup", "hc_setup_devotion", "hc_mentor_reactions", "hc_variant2",
                                 "hc_named_master"],
                   "A strict mentor sets an apprentice a near impossible task: plan it, trust instinct, ask, or "
                   "practice all night."),
    "hc2_pleas": (routes_pleas, ["hc_setup", "hc_setup_devotion", "hc_variant2", "hc_named_master"],
                  "An apprentice faces a strict mentor's impossible task, then pleads, bargains or tries again in "
                  "secret."),
    "hc3_disasters": (routes_disasters, ["hc_setup", "hc_setup_devotion", "hc_variant2", "hc_named_master"],
                      "An apprentice's examination under a strict mentor turns into a spectacular, harmless "
                      "disaster."),
    "hc4_noises": (routes_noises, ["hc_setup", "hc_setup_devotion", "hc_variant2", "hc_named_master",
                                   "hc_comic_pools"],
                   "An apprentice's examination for a strict mentor is undone by a bang, a smell or a badly timed "
                   "noise."),
    "hc5_victories": (routes_victories, ["hc_setup", "hc_setup_devotion", "hc_variant2", "hc_named_master",
                                         "hc_comic_pools"],
                      "An apprentice fails a strict mentor's impossible task and wins something anyway, for the "
                      "wrong reason."),
    "hc6_sabotage": (routes_sabotage, ["hc_setup", "hc_setup_devotion", "hc_variant2", "hc_named_master"],
                     "Someone has sabotaged an apprentice's work before a strict mentor's impossible task. Who "
                     "did it?"),
}

ROLE_DEFS = {
    "subject": {"kind": "villager", "min_age": 14},
    "mentor": {"kind": "villager", "min_age": 25},
    "rival": {"kind": "villager", "min_age": 14, "optional": True},
    "prankster": {"kind": "villager", "min_age": 14, "optional": True},
    "master": {"kind": "stranger", "sex": "random", "named": True},
    "official": {"kind": "stranger", "sex": "random"},
    "examiner": {"kind": "stranger", "sex": "random"},
    "elder": {"kind": "stranger", "sex": "random"},
    "chief": {"kind": "stranger", "sex": "random"},
    "patient": {"kind": "stranger", "sex": "random"},
}


def used_pools(texts: list[str], pools: dict) -> set[str]:
    seen, todo = set(), list(texts)
    while todo:
        t = todo.pop()
        for m in re.finditer(r"\{([A-Za-z_][A-Za-z0-9_]*)(?:\.\d)?\}", t):
            p = m.group(1)
            if p in pools and p not in seen:
                seen.add(p)
                todo += [i["text"] for i in pools[p]["items"]]
    return seen


def manifest_rows() -> dict:
    return {r["id"]: r for r in json.loads(lib.MANIFEST.read_text(encoding="utf-8"))["rows"]}


def build_file(fid: str, rows: dict, review: bool) -> tuple[dict, Builder]:
    fn, addons, desc = FILES[fid]
    b = Builder(fid, review)
    setup(b)
    routes = fn(b)
    kids = []
    for r in routes:
        if isinstance(r, tuple):
            rid, nid, need = r
            cond = {"role": need} if need in ("rival", "prankster") else visited(need)
            kids.append({"next": nid, "if": cond})
        else:
            kids.append({"next": r})
    b.node("routes", type="branch", children=kids)
    pools = dict(b.cv.pools)
    pools.update(b.pools)
    texts = [n.get("text", "") for n in b.nodes.values()] + \
        [c["label"] for n in b.nodes.values() for c in n.get("choices", [])]
    keep = used_pools(texts, pools)
    pools = {k: v for k, v in sorted(pools.items()) if k in keep}
    # "a (A)" / "(A)s": never with a profession whose article or plural would not read right (copies 3 and 4)
    odd = {"not": {"any": b.odd_copies}}
    for p in pools.values():
        for i in p["items"]:
            if re.search(r"\ba \{PROF\}|\{PROF\}s", i["text"]):
                i["if"] = {"all": [i["if"], odd]} if "if" in i else odd
    blob = json.dumps([b.nodes, pools])
    roles = {}
    for rid, r in ROLE_DEFS.items():
        if re.search(r"\(" + rid + r"[.)]", blob, re.I) or f'"role": "{rid}"' in blob:
            roles[rid] = r
    # every own line that no text shows: a ledger entry
    row = rows[fid]
    own = set(range(row["lines"][0], row["lines"][1] + 1))
    for a in addons:
        own |= set(range(rows[a]["lines"][0], rows[a]["lines"][1] + 1))
    shown: set[int] = set()
    for n in b.nodes.values():
        for spec in [n.get("src")] + [c.get("src") for c in n.get("choices", [])]:
            if spec:
                shown.update(lib.src_lines(spec))
    for p in pools.values():
        for i in p["items"]:
            shown.update(lib.src_lines(i["src"]))
    ledger = []
    for n in sorted(own):
        for c in CUTS.get(n, []):
            ledger.append({"src": f"L{n}", "kind": "structural" if n >= 2057 else "note", "text": c,
                           "why": "the saboteur a reason line belongs to" if n >= 2057
                           else "designer note: the second sentence is the other item, L691"})
        if lib.is_blank_or_separator(n) or (n in shown and n not in NOTE_LINES):
            continue
        s = lib.normalize_source_text(lib.line(n))
        if n in NOTE_LINES:
            ledger.append({"src": f"L{n}", "kind": "note", "why": "designer note, never displayed"})
        elif "EFFECT" in s:
            ledger.append({"src": f"L{n}", "kind": "instruction",
                           "why": "the route's heading and its EFFECT: made by the route's effects (subroute "
                                  "headings are never shown)"})
        elif n == 1:
            continue
        elif n in (356, 357) or not re.search(r":\s*$|^[A-Z0-9 ()'\-/,:;.]+$|^\s*\[?[a-z]*\]?\s*[A-Z][A-Z]",
                                             lib.strip_structural(s).strip() or ":"):
            ledger.append({"src": f"L{n}", "kind": "note",
                           "why": "a pool line this file's routes never draw (another file of the series does)"})
        else:
            ledger.append({"src": f"L{n}", "kind": "structural", "why": "heading"})
    games = [1, 2, 3, 4, 5]
    doc = {
        "format": "vvfp-cie-graph", "version": 6, "title": "(Name1)'s Harshest Critic", "games": games,
        "collection": {"id": fid, "source": SRC, "lines": row["lines"], "section": "hc", "credit": "",
                       "draw_weight": 1, "series": "hc_critic", "title_src": "L1", "ledger": ledger,
                       "addons": addons, "description": desc, "label_case": "title"},
        "grammar_fixes": [dict(f) for f in GRAMMAR] if fid == "hc1_routes" else [],
        "words": WORDS,
        "requirement": {"min_eligible": 2},
        "roles": roles,
        "start": "start",
        "nodes": b.nodes,
        "pools": pools,
    }
    if not doc["grammar_fixes"]:
        del doc["grammar_fixes"]
    return doc, b


MAX_CONTEXTS = 32


def bounded(fid: str, doc: dict) -> None:
    """Refuse a file the checks could not walk in bounded time and memory, or the engine could not load.

    The checks walk every history in every context (game x patch x optional role x run-time fact,
    vv_cie_graph.contexts): each "drew" condition is one more run-time fact and DOUBLES the contexts, so a draft of
    this event with a "drew" per profession and task (about 70) asked for 2^70 of them and ran a PC out of memory.
    Every condition here is "visited" (a static fact of the path) instead; one age fact and the optional roles are
    the only run-time ones."""
    sys.path.insert(0, str(ROOT / "src"))
    import vv_cie_graph as cg
    from collection_check import graph_for_engine
    assert '"drew"' not in json.dumps(doc), f"{fid}: a drew condition (run-time facts double the checks' contexts)"
    g, problems = cg.normalize(graph_for_engine(doc))
    assert not problems, (fid, problems[:3])
    n = len(cg.contexts(g))
    assert n <= MAX_CONTEXTS, f"{fid}: {n} contexts for the checks to walk (at most {MAX_CONTEXTS})"
    size = len(cg.compile_graph(g))
    assert size <= 0x20000, f"{fid}: {size} bytes, more than the engine reads (story_graph.inc CG_MAX_FILE)"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--review", action="store_true")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--no-check", action="store_true", help="write the files only")
    args = ap.parse_args(argv)
    rows = manifest_rows()
    OUT.mkdir(parents=True, exist_ok=True)
    written = []
    with lib.use_source(SRC):
        for fid in FILES:
            if args.only and fid not in args.only:
                continue
            doc, b = build_file(fid, rows, args.review)
            if UNKNOWN:
                print("\n".join(sorted(UNKNOWN)))
                return 1
            if args.review:
                for src, s, log in b.reviewed:
                    if (src, s) in SEEN:
                        continue
                    SEEN.add((src, s))
                    # a line where a pronoun could be someone else's: another name on it, or no name before it
                    if any(o != "subject" for _, o in log) or re.search(r"\((?:mentor|name2|name3)\)", s, re.I) \
                            or not re.match(r"^\(Name1\)", s, re.I):
                        print(f"{src}: {s}\n    " + ", ".join(f"{w}->{o}" for w, o in log))
                continue
            bounded(fid, doc)
            path = OUT / f"{fid}.json"
            path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
            written.append(path)
    if written and not args.no_check:
        return subprocess.call([sys.executable, str(ROOT / "scripts" / "collection_check.py"), "--format",
                                *[str(p) for p in written]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
