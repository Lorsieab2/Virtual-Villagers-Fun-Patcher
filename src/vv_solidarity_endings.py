"""Village Solidarity: the tag of an added event's ENDING (the owner, 2026-11-20: "add tags to every single event").

Every ending of every event the patcher adds (the Isola Grand Event Collection, the Living Event Engine, the
procedural pieces, More Island Events' own events, the Custom Island Event examples) carries one tag, read from the
ending's text AND its effects, by the owner's rule (the same as the stock events' tags):

  RAISE    good for the whole village: food, tech or a tech level gained, everyone healed or cured, new villagers,
           celebrations and gatherings, cooperation, reconciliation, kindness that brings people together;
  LOWER    bad for the whole village: food, crops or tech lost, several villagers sick or hurt, a death or a
           disappearance, a believer turning Heathen, conflict that divides the village, a heavy injury that can kill;
  NEUTRAL  only one villager's own skills, likes, looks or age, or a small hurt; mixed results; nothing changes;
           story-only endings.

`classify` is the rule as code: the effects decide first (a death, a disappearance, a lost baby, a Heathen or damaged
huts always lower; village gains raise, village losses lower, both neutral), then the words of the page (a gathering,
a reconciliation or a whole village's joy raise; a quarrel, a feud or a divided village lower; both or neither
neutral).  scripts/tag_village_solidarity.py applies it to the collection (with the reviewed judgement calls in
data/event_collection/solidarity_review.json); src/vv_living_mixer.py and scripts/procedural_pieces.py to theirs.
"""
from __future__ import annotations

import re

TAGS = ("raise", "lower", "neutral")

# ---- The effects ----------------------------------------------------------------------------------------------------

ALWAYS_LOWER = {"kill": "a death", "vanish": "a disappearance", "die_unrecovered": "a death",
                "baby_lost": "a lost pregnancy", "birth_then_die": "a death", "damage": "huts damaged"}


def _whole(e: dict) -> bool:
    """The effect lands on the whole village (every villager) or on several."""
    t = e.get("target")
    if isinstance(t, dict) and (t.get("all") or (t.get("random") or 0) >= 2):
        return True
    return e.get("who") == "all"


def _num(v, default=0):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else default


def effect_signals(effects: list[dict]) -> tuple[list[str], list[str], list[str]]:
    """(always-lower reasons, village gains, village losses) of a page's effects."""
    strong, good, bad = [], [], []
    for e in effects or []:
        do = e.get("do")
        if do in ALWAYS_LOWER:
            strong.append(ALWAYS_LOWER[do])
        elif do == "status" and e.get("status") == "heathen":
            strong.append("a believer turns Heathen")
        elif do in ("food", "tech"):
            (bad if e.get("loss") else good).append(f"{do} {'lost' if e.get('loss') else 'gained'}")
        elif do == "pay_award":
            good.append("an award paid")
        elif do == "supply":
            n = _num(e.get("min")) + _num(e.get("max"))
            if n > 0:
                good.append(f"{e.get('item', 'supplies')} gained")
            elif n < 0:
                bad.append(f"{e.get('item', 'supplies')} lost")
        elif do == "celebrate" and _whole(e):
            good.append("everyone celebrates")
        elif do == "group" and e.get("kind") == "sick":
            bad.append("the village falls sick")
        elif do == "group" and _whole(e) and e.get("kind") != "effect":   # "effect": a passing quirk, the words'
            good.append(f"a village gathering ({e.get('kind', 'together')})")
        elif do in ("new_villager", "clone"):
            good.append("a new villager")
        elif do in ("pregnant", "nursing"):
            good.append("a baby on the way" if do == "pregnant" else "a new baby")
        elif do == "repair":
            good.append("huts repaired")
        elif do == "village" and e.get("what") == "tech_level" and _num(e.get("step")) > 0:
            good.append("a tech level gained")
        elif do == "cure" and _whole(e):
            good.append("villagers cured")
        elif do == "mood" and _whole(e):
            (good if e.get("mood") == "good" else bad).append(f"everyone's mood {e.get('mood')}")
        elif do in ("health_change", "health"):
            lo = min(_num(e.get("min")), _num(e.get("max")))
            hi = max(_num(e.get("min")), _num(e.get("max")))
            if _whole(e):
                if hi < 0:
                    bad.append("several villagers hurt")
                elif lo > 0:
                    good.append("villagers healed")
            # one villager's hurt, however hard, is that villager's own (neutral): the events that can kill say so
            # with a death of their own
        elif do == "sick":
            if _whole(e):
                bad.append("several villagers sick")
            else:
                strong.append("a villager falls sick (it can kill)")
        elif do == "trade":
            good.append(f"{e.get('get')} gained in a trade")
            bad.append(f"{e.get('give')} given in a trade")
    return strong, good, bad


# ---- The words ------------------------------------------------------------------------------------------------------

def _words(*ws: str) -> re.Pattern:
    return re.compile(r"(?<![a-z])(?:" + "|".join(ws) + r")(?![a-z])", re.I)


# Words count only in a sentence about the village as a whole (COMMUNAL): two villagers' private moment is theirs
# (neutral), the whole village's cheer or quarrel is the village's.  A strong word scores 2, a weak one 1.
RAISE_STRONG = _words(
    r"celebrat\w*", r"feast\w*", r"festival\w*", r"reconcil\w*", r"forgiv\w*", r"forgave", r"made peace",
    r"make peace", r"making peace", r"makes peace", r"ma(?:k|d)e amends", r"making amends", r"so sorry",
    r"welcom\w*", r"together", r"gratitude", r"grateful", r"unity", r"united",
    r"help(?:s|ed|ing)? (?:each other|one another|out)", r"(?:come|came|comes|want|wants) (?:out )?to help",
    r"offers? (?:practical )?help", r"pitch(?:ed|es)? in", r"sing(?:s|ing|ers?)?", r"sang", r"songs?",
    r"danc(?:e|es|ed|ing)", r"join\w* in", r"apologi[sz]\w*",
    r"thank(?:s|ed|ing)? (?:everyone|everybody|each other|the village|the villagers|them all)", r"cheer(?:s|ed|ing)?",
    r"applau\w*", r"gather(?:s|ed|ing)?", r"shared?", r"sharing", r"cooperat\w*", r"mutual\w*")
RAISE_WEAK = _words(r"laugh\w*", r"smil\w*", r"happ(?:y|ily|iness)", r"proud", r"pride", r"hug\w*", r"embrac\w*",
                    r"kind(?:ness)?", r"trust\w*", r"comfort\w*", r"hope\w*", r"relie(?:f|ved)", r"respect\w*",
                    r"admir\w*", r"prais\w*", r"warm\w*", r"delight\w*", r"glad", r"joy\w*")
LOWER_STRONG = _words(
    r"quarrel\w*", r"feud\w*", r"divided", r"divides", r"division", r"resent\w*", r"grudge\w*", r"betray\w*",
    r"distrust\w*", r"mistrust\w*", r"tension\w*", r"rift", r"take sides", r"taking sides", r"took sides",
    r"not speaking", r"stopped speaking", r"refuses? to speak", r"storm(?:s|ed)? off", r"hostil\w*",
    r"splits? the village", r"(?:is|was) split", r"starv\w*", r"famine", r"blam\w*", r"accus\w*", r"bitterly", r"bitterness", r"argu\w*", r"angr\w*",
    r"anger", r"furious", r"fight\w*", r"fought", r"unfair\w*", r"dispute[sd]?", r"disputing",
    r"deepens? the distance", r"torn between", r"prolongs? (?:the )?separation")
LOWER_WEAK = _words(r"jealous\w*", r"envy", r"envious", r"suspic\w*", r"humiliat\w*", r"ashamed", r"shame\w*",
                    r"sulk\w*", r"glar\w*", r"insult\w*", r"mock\w*", r"grumbl\w*", r"scold\w*", r"tense",
                    r"worr(?:y|ied|ies)", r"afraid", r"fear\w*", r"frighten\w*", r"ruin\w*", r"spoil\w*")
COMMUNAL = _words(r"everyone", r"everybody", r"(?:the )?whole village", r"(?:the )?entire village", r"the village",
                  r"the villagers", r"the tribe", r"neighbou?rs", r"families", r"each other", r"one another",
                  r"the crowd", r"all of them", r"half the village", r"the others")
QUIET = _words(r"remembrance", r"solemn\w*", r"bittersweet", r"in silence", r"mourn\w*", r"quietly reflect\w*")
NEGATED = re.compile(r"(?<![a-z])(?:not|never|no longer|nobody|no one|without|doesn't|does not|didn't|isn't|"
                     r"won't|no|rather than|instead of)\s+(?:\w+\s+){0,2}$", re.I)
MENDED = _words(r"apologi[sz]\w*", r"forgiv\w*", r"forgave", r"together", r"agree\w*", r"friends", r"made up",
                r"make up", r"makes up", r"ma(?:k|d)e amends", r"laugh\w*", r"happily", r"reconcil\w*")
SENTENCE = re.compile(r"(?<=[.!?])[\"')\]]*\s+|\n+")


def _hits(pattern: re.Pattern, text: str) -> list[str]:
    out = []
    for m in pattern.finditer(text):
        if NEGATED.search(text[max(0, m.start() - 40):m.start()]):
            continue
        out.append(m.group(0).lower())
    return out


def text_signals(text: str) -> tuple[int, int, list[str], list[str]]:
    """(raise score, lower score, raise words, lower words) of a page's words, counted only in its sentences about
    the village as a whole; quiet remembrance counts on neither side."""
    up = down = 0
    upw: list[str] = []
    downw: list[str] = []
    private: dict[str, str] = {}
    for s in dict.fromkeys(x.strip() for x in SENTENCE.split(text) if x.strip()):    # a variant's repeat: once
        rs, rw, ls, lw = (_hits(p, s) for p in (RAISE_STRONG, RAISE_WEAK, LOWER_STRONG, LOWER_WEAK))
        if not COMMUNAL.search(s):
            for w in ls:                       # a quarrel of two: each kind of conflict word once
                private.setdefault(w[:5], w)
            continue
        up += 2 * len(rs) + len(rw)
        down += 2 * len(ls) + len(lw)
        upw += rs + rw
        downw += ls + lw
    if len(private) >= 2 and not MENDED.search(text):   # two kinds of conflict words: a falling-out, left so
        down += len(private)
        downw += list(private.values())
    return up, down, upw, downw


# ---- The tag --------------------------------------------------------------------------------------------------------

def classify(text: str, effects: list[dict]) -> tuple[str, str, bool]:
    """(tag, short reason, sure) of an ending: its words (every variant joined) and its effects.  `sure` False marks
    an ending whose words and effects pull apart, or whose words alone tip it narrowly: one to read."""
    strong, good, bad = effect_signals(effects)
    up, down, upw, downw = text_signals(text)
    if strong:
        return "lower", "; ".join(dict.fromkeys(strong)), not (good and up >= 4)
    if good and not bad:
        return "raise", "; ".join(dict.fromkeys(good)), down < 4
    if bad and not good:
        return "lower", "; ".join(dict.fromkeys(bad)), up < 4
    if good and bad:
        return "neutral", "mixed: " + "; ".join(dict.fromkeys(good + bad)), True
    quiet = bool(QUIET.search(text))
    net = up - down
    if not quiet and up >= 2 and net >= 2:
        return "raise", "words: " + ", ".join(dict.fromkeys(upw)), down == 0 and up >= 3
    if not quiet and down >= 2 and net <= -2:
        return "lower", "words: " + ", ".join(dict.fromkeys(downw)), up == 0 and down >= 3
    if up >= 2 and down >= 2:
        return "neutral", "mixed words: " + ", ".join(dict.fromkeys(upw + downw)), False
    return "neutral", ("quiet remembrance" if quiet else "story only" if not effects else
                       "one villager's own change"), up < 2 and down < 2


# ---- An event graph's endings ---------------------------------------------------------------------------------------

SPLIT = ("__fx", "__text")


def _targets(n: dict) -> list[str]:
    out = []
    for c in (n.get("children") or []) + (n.get("choices") or []):
        out += [x for x in (c.get("next"), c.get("else")) if isinstance(x, str)]
    if isinstance(n.get("else"), str):
        out.append(n["else"])
    return out


def is_ending(n: dict) -> bool:
    """A page the event ends on: a popup with nowhere to go."""
    return n.get("type", "popup") == "popup" and not _targets(n)


def endings(g: dict) -> dict[str, list[str]]:
    """{the tag's node id: the ending pages it covers} of a validated graph: an ending X, or (the outcome-effects
    pass, scripts/outcome_effects.py) a branch X over its two copies X__fx and X__text, both endings, tagged as X."""
    nodes = g["nodes"]
    out: dict[str, list[str]] = {}
    for nid, n in nodes.items():
        if not is_ending(n):
            continue
        key = nid
        for suf in SPLIT:
            base = nid[:-len(suf)]
            if nid.endswith(suf) and base in nodes and nodes[base].get("type") == "branch" \
                    and all(base + s in nodes for s in SPLIT):
                key = base
        out.setdefault(key, []).append(nid)
    return out


def ending_reading(g: dict, key: str, pages: list[str]) -> tuple[str, list[dict]]:
    """The words and effects an ending's tag is read from: its pages' text and variants, their effects, and the
    words and effects of the pages leading only to it (a linear run of popups before it)."""
    nodes = g["nodes"]
    preds: dict[str, list[str]] = {}
    for nid, n in nodes.items():
        for t in set(_targets(n)):
            preds.setdefault(t, []).append(nid)
    texts, effects = [], []
    for pid in pages:
        n = nodes[pid]
        texts += [n.get("text") or ""] + [v.get("text") or "" for v in n.get("variants") or []]
        effects += list(n.get("effects") or [])
    cur, seen = key, {key}
    while True:
        ps = preds.get(cur, [])
        if len(ps) != 1 or ps[0] in seen:
            break
        p = nodes[ps[0]]
        if p.get("type") != "popup" or set(_targets(p)) != {cur}:
            break
        texts.append(p.get("text") or "")
        effects += list(p.get("effects") or [])
        cur = ps[0]
        seen.add(cur)
    return " ".join(t for t in texts if t), effects
