"""The owner's own event layout ("S001. Title [VV1, ...]"), read by the Player Events importer (v1.35.97).

The owner (2026-11-16): the 315 rewritten events and the balance events are written in this layout and are built
through the importer when the owner says GO.  A block looks like:

    S001. The Spring That Talks Back   [VV1, VV2, VV3, VV4, VV5]
    WHO: one villager aged 14 or older (not protected)
    EVENT TEXT
    <the opening story, one paragraph a line>
    Choice A: Ask What to Be Good At
    Choice B: Ask Nothing and Just Drink
    CHOICE A: ASK WHAT TO BE GOOD AT
    First popup: <the choice's own popup>
    Ending A1 -- THE GREEN THUMB. Chance 50%. EFFECT: gains 20 to 30 Farming; now likes farming
    <the ending's story>
    ...
    MIXER SEED S001
    Premise: <a setup's text>
    Roles:
      seeker: one villager aged 14 or older (not protected)
    Approaches: Ask What to Be Good At | Just Drink | ...
    Outcome pool:
      - <text> [answers: Ask What to Be Good At] [mood: warm] [EFFECT: ...]
    Flavour lines:
      - <a line>

Lines starting "^" are the owner's notes and are skipped.  The EFFECT phrases are free English; owner_effects() maps
them with a phrase table built from the owner's own files (docs/player-events-format.md 10).  A phrase it cannot map
is a line-numbered problem (the event is left out); the static event and the mixer seed become an ordinary event and
procedural pieces.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

import vv_cie_graph as cie

HEADING = re.compile(r"^([A-Z]+-?\d+[A-Z]?)\.\s+(.+?)\s+\[([^\]]*(?:VV[1-5]|[Aa]ll)[^\]]*)\]\s*$")
_ENDING = re.compile(r"^Ending\s+([A-Z])(\d+)\s+--\s+(.*?)\.?\s+Chance\s+(\d+)%\.\s+EFFECT:\s*(.*)$")
_CHOICE_LIST = re.compile(r"^Choice\s+([A-Z])\s*:\s*(.+)$")
_CHOICE_HEAD = re.compile(r"^CHOICE\s+([A-Z])\s*:\s*(.+)$")
_SEED = re.compile(r"^MIXER SEED\b\s*(\S*)")
SKILLS = ("Farming", "Building", "Research", "Healing", "Parenting")
SKILL_ALIASES = {"fishing": "Farming", "gathering": "Farming", "science": "Research", "medicine": "Healing",
                 "devotion": "Devotion", "fishing, or the game's closest skill": "Farming",
                 "fishing, or the skill the game uses for fishing": "Farming"}
SIZE_WORDS = {"a little": "small", "some": "normal", "a lot": "large", "hugely": "huge"}
MOODS = {"warm": 0, "funny": 0, "happy": 0, "silly": 0, "sweet": 0, "social": 1, "curious": 1, "mixed": 1,
         "tense": 2, "eerie": 2, "sad": 2, "serious": 2, "solemn": 2, "mysterious": 2, "bittersweet": 2}
GROUP_NOUNS = {"healer": "Healing", "builder": "Building", "farmer": "Farming", "researcher": "Research",
               "scholar": "Research", "parent": "Parenting", "fisher": "Farming"}
NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
# A like or dislike the owner names that is not a game word: the words to try, in order ("or similar if available";
# style guide 8a: never a job, the thing itself).
PREF_SIMILAR = {
    "farming": ("plants", "turnips", "dirt"), "gathering": ("fruit", "berries", "bushes"),
    "gathering food": ("fruit", "berries"), "building": ("wood", "rough wood", "rocks", "lifting"),
    "working": ("work",), "research": ("learning", "exploring"), "learning": ("learning", "exploring"),
    "healing": ("medicine", "herbs"), "parenting": ("children", "playing"), "crabs": ("crab meat",),
    "boats": ("the ocean", "swimming"), "jewelry": ("pearls", "coral"), "jewellery": ("pearls", "coral"),
    "eating": ("eating", "fruit"), "running": ("running",), "sleeping": ("sleeping", "resting"),
}


class Unmapped(Exception):
    pass


def split_top(text: str, seps: str = ";") -> list[str]:
    """`text` split at `seps` outside round brackets."""
    out, depth, cur = [], 0, ""
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch in seps and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [p.strip() for p in out if p.strip()]


def role_of(token: str | None) -> str | None:
    """A role id from the owner's words for a villager: None is the event's main villager."""
    if token is None:
        return None
    t = token.strip().strip("()").strip().lower()
    t = re.sub(r"^(the|a|an)\s+", "", t)
    t = re.sub(r"'s$", "", t)
    if t in ("name", "name1", "villager", "main villager", "", "him", "her", "them"):
        return None
    if t in ("name2", "friend", "partner", "other villager"):
        return "friend"
    if t in ("new name", "newcomer", "new villager"):
        return "$newest"
    if t in ("younger villager",):
        return "young"
    t = re.sub(r"\s+name$", "", t)
    t = re.sub(r"[^a-z0-9]+", "_", t).strip("_")
    return t or None


def pref_word(word: str, games: Iterable[int]) -> tuple[str | None, str]:
    """A game like/dislike word for the owner's word in every game of the event, and a note when it was swapped."""
    games = list(games)
    w = word.strip().strip('"').lower()
    w = re.sub(r"\s+or similar if available$", "", w)
    options = [x.strip() for x in re.split(r"\s+or\s+|/", w) if x.strip()]
    tries = []
    for o in options:
        tries.append(o)
        tries += list(PREF_SIMILAR.get(o, ()))
    for t in tries:
        if all(t in cie.GAMES[g].preferences for g in games):
            return t, "" if t == options[0] else f"\"{word}\" is not a like/dislike word in every game: {t!r} used"
    return None, f"\"{word}\": no like/dislike word fits every game of the event"


class _Ctx:
    def __init__(self, games: Iterable[int]):
        self.games = list(games)
        self.notes: list[str] = []
        self.roles: dict[str, dict] = {}

    def need(self, rid: str | None, **facts) -> str | None:
        if rid is not None and not rid.startswith("$"):
            self.roles.setdefault(rid, {}).update(facts)
        elif rid is None and facts:
            self.roles.setdefault("", {}).update(facts)
        return rid


def _fx(**kw) -> dict:
    return {k: v for k, v in kw.items() if v is not None}


def _subjects(s: str) -> tuple[list[str | None], str, bool]:
    """(the villagers a phrase is about, the rest of it, "each"/"both").  "(name) and (name2) each gain ...",
    "(young name) gains ...", "the chief gains ...", "both ..."."""
    m = re.match(r"^\(([^)]+)\)\s+and\s+\(([^)]+)\)\s+(each\s+|both\s+)?(.*)$", s)
    if m:
        a, b = role_of(m.group(1)), role_of(m.group(2))
        if a == b:
            b = "friend" if a is None else None
        return [a, b], m.group(4), True
    m = re.match(r"^both\s+(.*)$", s)
    if m:
        return [None, "friend"], m.group(1), True
    m = re.match(r"^\(([^)]+)\)(?:'s)?\s+(.*)$", s)
    if m and not re.match(r"^(any birth sex|small|normal|large|huge)", m.group(1)):
        return [role_of(m.group(1))], m.group(2), False
    m = re.match(r"^the\s+(chief|keeper|villager|farmer|fisher|teacher|worker|woodcutter|resident|navigator|healer|"
                 r"builder|elder|novice|apprentice|traveler|traveller|mother|father|child)\s+(.*)$", s)
    if m:
        return [role_of(m.group(1))], m.group(2), False
    return [None], s, False


def owner_effects(phrase_text: str, games: Iterable[int]) -> tuple[list[dict], dict[str, dict], list[str]]:
    """Every effect of one EFFECT: text (the phrases between ";"), the roles they need and the notes; Unmapped (with
    the phrase) when one phrase is not in the table."""
    ctx = _Ctx(games)
    out: list[dict] = []
    for raw in split_top(phrase_text.strip().rstrip(".")):
        out += _one(raw, ctx)
    return out, ctx.roles, ctx.notes


def _one(raw: str, ctx: _Ctx) -> list[dict]:
    s = raw.strip().replace("“", '"').replace("”", '"').replace("’", "'")
    s = re.sub(r"\s+", " ", s).strip().rstrip(".")
    s = re.sub(r"\((?:name\d|[a-z ]+)\s*:\s*(his/her|he/she|him/her)\)", r"(\1)", s, flags=re.I)  # "(name2: his/her)"
    low = s.lower()
    low = re.sub(r"^then\s+", "", low)
    low = re.sub(r",\s*(peacefully(?: of old age)?|quietly|in (?:his|her|their) sleep)$", "", low)
    low = re.sub(r",? or (?:the game's closest skill|the skill the game uses for fishing)", "", low)
    low = re.sub(r"\),\s*a villager aged [^,]*,\s*", ") ", low)          # "(name2), a villager aged 14 ..., DIES"
    # "(name2), another villager, ..." / "(sick name), the sickest villager, ..." / "(grandchild name), (his/her)
    # grandchild, ...": the owner's description of who it is (the WHO line casts them)
    low = re.sub(r"^(\([^)]+\)),\s*(?:another villager|one of the [a-z]+|the [a-z ]+?|a [a-z ]+?|\(his/her\) [a-z ]+?)"
                 r"(?:\s*\([^)]*\))?,\s*", r"\1 ", low)
    low = re.sub(r"^(\([^)]+\)),?\s+another villager\s*\(", r"\1 (", low)
    low = re.sub(r",\s*(?:of old age|after a fever|if \(he/she\) has one)$", "", low)
    low = re.sub(r",? with the [a-z']+ help$", "", low)
    if "every other sick villager" in low and "cured" in low:
        return [{"do": "cure", "target": {"all": True}}]
    m = re.fullmatch(r"(?:the )?young head look for both(?: \(([^)]+)\) and \(([^)]+)\))?|"
                     r"\(([^)]+)\) and \(([^)]+)\) both get a new look \(the young head look\)", low)
    if m:
        a, b = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4)) if m.group(3) else (None, "name2")
        return [_fx(do="young_look", role=ctx.need(role_of(a))), _fx(do="young_look", role=ctx.need(role_of(b)))]
    m = re.fullmatch(r"new look for \(([^)]+)\) and \(([^)]+)\)(?: \((.+)\))?", low)
    if m:
        part = "head" if m.group(3) and ("head" in m.group(3) or "face" in m.group(3)) else "body"
        return [_fx(do="appearance", role=ctx.need(role_of(x)), **{part: "random"}) for x in (m.group(1), m.group(2))]
    m = re.fullmatch(r"changes name \(([^)]+)\) to \"?([a-z]+)\"?(.*)", low)
    if m:
        rid = ctx.need(role_of(m.group(1)))
        if re.search(r"\b(male|female|if)\b", m.group(3)):
            ctx.notes.append(f"{raw.strip()}: a name for each sex cannot be chosen by the engine; a random default "
                             "name from the game's own lists is given instead")
            return [_fx(do="change_name", role=rid)]
        return [_fx(do="change_name", role=rid, name=m.group(2).title())]
    m = re.fullmatch(r"(?:\(([^)]+)\) )?loses two dislikes \(at random\)", low)
    if m:
        rid = ctx.need(role_of(m.group(1)))
        return [_fx(do="preference", role=rid, dislike="random", remove=True)] * 2
    any_sex = False
    if low.startswith("(any birth sex) "):
        any_sex, low = True, low[len("(any birth sex) "):]
    # No change at all.
    if re.fullmatch(r"(none|nothing else|no effect|no lasting change)(\s*\(.*\))?", low) or \
            re.fullmatch(r"(both |and )?joins? the village|both join the village|the baby joins the village|"
                         r"the mother was never a villager.*|injured \(the travell?er.*not a villager\)|"
                         r"body swap, then swapped back.*|body swap reversed.*", low):
        return []
    m = re.fullmatch(r"(food|tech) (gain|loss) \((small|normal|large|huge)(?: amount)?\)(?: \(.*\))?", low)
    if m:
        e = {"do": m.group(1), "size": m.group(3), "scaled": True}
        if m.group(2) == "loss":
            e["loss"] = True
        return [e]
    m = re.fullmatch(r"every villager is happier.*", low)
    if m:
        return [{"do": "mood", "mood": "good", "target": {"all": True}}]
    if re.fullmatch(r"(?:the )?damaged huts are repaired.*", low):
        return [{"do": "repair", "structures": cie.DAMAGE_ANY}]
    m = re.fullmatch(r"all sick villagers are cured.*|every (?:ill|sick) villager's illness is cured.*|"
                     r"illness cured \(for every sick villager\)", low)
    if m:
        return [{"do": "cure", "target": {"all": True}}]
    m = re.fullmatch(r"(one|two|three|four|five|\d+) random villagers? (?:has|have) (?:their|his|her) illness cured.*",
                     low)
    if m:
        return [{"do": "cure", "target": {"random": NUMBERS.get(m.group(1)) or int(m.group(1))}}]
    m = re.fullmatch(r"(every villager|(one|two|three|four|five|\d+) random villagers?) gains? (\d+)(?: to (\d+))? in "
                     r"(?:\(his/her\)|their|his|her) best skill", low)
    if m:
        lo, hi = int(m.group(3)), int(m.group(4) or m.group(3))
        tg = {"all": True} if m.group(1) == "every villager" else \
            {"random": NUMBERS.get(m.group(2)) or int(m.group(2))}
        return [{"do": "skill", "best": True, "min": lo, "max": hi, "target": tg}]
    m = re.fullmatch(r"(one|two|three|four|five|\d+) random villagers? (?:has|have) an illness.*", low)
    if m:
        n = NUMBERS.get(m.group(1)) or int(m.group(1))
        return [{"do": "sick", "target": {"random": n}}]
    m = re.fullmatch(r"every (healer|builder|farmer|researcher|scholar|parent) gains (\d+)(?: to (\d+))? (\w+)", low)
    if m:
        lo, hi = int(m.group(2)), int(m.group(3) or m.group(2))
        return [{"do": "skill", "skills": [_skill(m.group(4))], "min": lo, "max": hi,
                 "target": {"skill": GROUP_NOUNS[m.group(1)]}}]
    m = re.fullmatch(r"every (?:working )?villager(?: in the [a-z ]+)? gains (\d+)(?: to (\d+))? (?:in )?"
                     r"(a skill they don't usually use|a random skill|\w+)", low)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
        sk = list(SKILLS) if " " in m.group(3) else [_skill(m.group(3))]
        return [{"do": "skill", "skills": sk, "min": lo, "max": hi, "target": {"all": True}}]
    m = re.fullmatch(r"new look for (one|two|three|four|five|\d+) random villagers?(?: \((.*)\))?", low)
    if m:
        # Engine 5ee2b3dc0: a group appearance, each member drawing their own look.
        n = NUMBERS.get(m.group(1)) or int(m.group(1))
        what = (m.group(2) or "head").lower()
        part = "head" if ("head" in what or "face" in what or "hair" in what) else "body"
        return [{"do": "appearance", part: "random", "target": {"random": n}}]
    if re.fullmatch(r"story only.*|the travell?er was never a villager.*|nothing changes.*", low):
        return []
    # A group: "every villager ...", "every healer ...", "3 random villagers each ...", "three random villagers' ..."
    m = re.fullmatch(r"(every villager|all villagers|every (healer|builder|farmer|fisher|researcher|scholar|parent)|"
                     r"(\d+|one|two|three|four|five) random villagers?(?:')?)\s+(?:each\s+)?(.+)", low)
    if m:
        tg = {"all": True} if m.group(1) in ("every villager", "all villagers") else \
            {"skill": GROUP_NOUNS.get(m.group(2), "Farming")} if m.group(2) else \
            {"random": NUMBERS.get(m.group(3)) or int(m.group(3))}
        rest = m.group(4)
        rest = re.sub(r"^(?:are|is|get|gets)\s+", lambda x: "" if x.group(0).strip() in ("are", "is") else "gets ",
                      rest)
        rest = re.sub(r"^illness(?:es)? (?:is |are )?cured.*", "illness cured", rest)
        rest = re.sub(r"^lose\b", "loses", rest)
        rest = re.sub(r"^gain\b", "gains", rest)
        effects = _predicate(rest, None, ctx, any_sex, raw, True)
        for e in effects:
            if e["do"] not in cie.TARGET_EFFECTS:
                raise Unmapped(raw + f" ({e['do']} cannot go to a group)")
            if e["do"] == "preference" and e.get("_games"):
                raise Unmapped(raw + " (a group's like or dislike must exist in every game)")
            e.pop("role", None)
            e["target"] = dict(tg)
        ctx.roles.pop("", None)
        return effects
    subjects, rest, each = _subjects(low)
    out: list[dict] = []
    for who in subjects:
        out += _predicate(rest, who, ctx, any_sex, raw, len(subjects) > 1)
    return out


def _skill(word: str) -> str:
    w = word.strip().lower()
    if w in SKILL_ALIASES:
        return SKILL_ALIASES[w]
    if w.title() in SKILLS + ("Devotion",):
        return w.title()
    raise Unmapped(f"{word!r} is not a skill")


def _target_tail(s: str) -> tuple[str, str | None]:
    """'... for (young name)' / '... for the novice': the rest and the role."""
    m = re.search(r"\s+for\s+(\([^)]+\)|the [a-z ]+?)(?=\s*(?:\(|$))", s)
    if m:
        return s[:m.start()] + s[m.end():], role_of(m.group(1))
    return s, None


def _predicate(s: str, who: str | None, ctx: _Ctx, any_sex: bool, raw: str, group: bool) -> list[dict]:
    s = s.strip()
    s, tail = _target_tail(s)
    who = tail if tail is not None else who
    r = ctx.need(who)
    if re.fullmatch(r"(?:is |are |now )?(?:each |both )?(?:dies|die)(?: \(a grave[^)]*\))?", s):
        ctx.need(who, harm=True)
        return [_fx(do="kill", role=r)]
    if re.fullmatch(r"(?:is |are )?disappears?(?: \(.*\))?", s):
        return [_fx(do="vanish", role=r)]
    m = re.fullmatch(r"skill \+ (\w+),? \(?(a little|some|a lot)(?:, \+\d+)?\)?(?: \(.*\))?", s)
    if m:
        return [_fx(do="skill", role=r, skills=[_skill(m.group(1))], size=SIZE_WORDS[m.group(2)])]
    m = re.fullmatch(r"(?:skill \+ )?(\w+) becomes master(?: \(\d+\))?", s)
    if m:
        return [_fx(do="skill", role=r, skills=[_skill(m.group(1))], set=100)]
    m = re.fullmatch(r"(?:each )?gains? (\d+)(?: to (\d+))? (?:in )?(?:\(his/her\) |their )?(best skill|the other's best "
                     r"skill|\w+)(?: and now likes (.+))?(?: \([^)]*\))?", s)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
        e = _fx(do="skill", role=r, min=lo, max=hi)
        if "best" in m.group(3):
            e["best"] = True
        else:
            e["skills"] = [_skill(m.group(3))]
        out = [e]
        if m.group(4):
            out += _pref("like", m.group(4), r, ctx)
        return out
    m = re.fullmatch(r"gains? (\d+) in a random skill", s)
    if m:
        return [_fx(do="skill", role=r, skills=list(SKILLS), min=int(m.group(1)), max=int(m.group(1)))]
    m = re.fullmatch(r"loses (\d+)(?: to (\d+))? (\w+)", s)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
        return [_fx(do="skill", role=r, skills=[_skill(m.group(3))], min=-hi, max=-lo)]
    m = re.fullmatch(r"(?:each |both )?loses? the (like|dislike) of (.+)", s)
    if m:
        return _pref(m.group(1), m.group(2), r, ctx, remove=True)
    m = re.fullmatch(r"(?:each |both )?(?:now )?(likes?|dislikes?) (?!\+)(.+)", s)
    if m and "favourite job" not in s and "favorite job" not in s:
        return _pref("like" if m.group(1).startswith("like") else "dislike", m.group(2), r, ctx)
    m = re.fullmatch(r"(like|dislike) \+ (.+)", s)
    if m:
        return _pref(m.group(1), m.group(2), r, ctx)
    m = re.fullmatch(r"(?:each )?loses? (?:one|a different|a) dislike \((?:an? (\w+) dislike, )?at random\)", s)
    if m:
        if m.group(1):
            word, note = pref_word(m.group(1), ctx.games)
            if word:
                return [_fx(do="preference", role=r, dislike=word, remove=True)]
        return [_fx(do="preference", role=r, dislike="random", remove=True)]
    m = re.fullmatch(r"(?:is |are |both )?(?:injured|loses? health)(?: \((.*?)\)?)?(?: \(.*\))?", s)
    if m:
        ctx.need(who, harm=True)
        lo, hi = (-20, -10) if m.group(1) and "minor" in m.group(1) else (-40, -20)
        return [_fx(do="health_change", role=r, min=lo, max=hi)]
    m = re.fullmatch(r"(?:has a )?permanent disability \(health loss (\d+)%\)", s)
    if m:
        n = int(m.group(1))
        return [_fx(do="health_change", role=r, min=-n, max=-n)]
    if re.fullmatch(r"(?:is |are )?(?:ill|sick)(?: \(.*\))?|(?:has an )?illness(?: \(.*\))?|"
                    r"has an illness(?: \(.*\))?|needs the healers.*", s):
        return [_fx(do="sick", role=r)]
    if re.fullmatch(r"(?:'s )?illness (?:is )?cured(?: \(.*\))?|illness cured(?: \(.*\))?|is cured|cured", s):
        return [_fx(do="cure", role=r)]
    m = re.fullmatch(r"new villager \(a baby\) joins the village, nursed by (\([^)]+\)|the arriving adult)(?:, with "
                     r"\(([^)]+)\) as the other parent)?", s)
    if m:
        carrier = "$newest" if m.group(1) == "the arriving adult" else \
            ctx.need(role_of(m.group(1)), min_age=18, carrier=True)
        partner = role_of(m.group(2)) if m.group(2) else None
        return [_fx(do="nursing", role=carrier, partner=partner, any_birth_sex=True if any_sex else None)]
    m = re.fullmatch(r"new villagers? \((.+?)\)(?: \((\d+)\))?(?:, each with a different name)?"
                     r"(?: (?:arrives?|arrive)(?: and stays?)?| joins the village| arrive and stay)?(,? with their baby)?"
                     r"(?:: .*)?", s)
    if m:
        out = _newcomers(m.group(1), int(m.group(2) or 0))
        if m.group(3):
            out.append({"do": "new_villager", "age": "child", "child_of_newest": True})
        return out
    m = re.fullmatch(r"(?:a )?(?:second )?duplicate(?: of \(([^)]+)\))?(?:,? named \((?:new name(?: \d)?|made\d)\))?"
                     r"(?: \(different name\))?", s)
    if m:
        return [_fx(do="new_villager", copy_of=ctx.need(role_of(m.group(1))) or "@default")]
    m = re.fullmatch(r"clone of \(([^)]+)\)(?: \((\d)\))?(?:,? named .*?)?(?: \(different name\))?(?:, each a different "
                     r"name)?", s)
    if m:
        n = int(m.group(2) or 1)
        if n not in (1, 2):
            raise Unmapped(raw + " (one or two clones only)")
        return [_fx(do="clone", role=ctx.need(role_of(m.group(1))), count=2 if n == 2 else None)]
    m = re.fullmatch(r"body swap (?:between \(([^)]+)\) and \(([^)]+)\)|\(([^)]+)\) with \(([^)]+)\))(?: \(.*\))?", s)
    if m:
        a, b = role_of(m.group(1) or m.group(3)), role_of(m.group(2) or m.group(4))
        if a == b:
            b = "friend" if a is None else None
        return [_fx(do="body_swap", role=ctx.need(a), **{"with": ctx.need(b) or "@default"})]
    if re.fullmatch(r"loses name.*|(?:they )?(?:is|are) now called \"\?\"", s):
        return [_fx(do="lose_name", role=r)]
    if re.fullmatch(r"changes name \(to a random default name\)|changes name", s):
        return [_fx(do="change_name", role=r)]
    m = re.fullmatch(r"changes name: (?:\(([^)]+)\)|the ([a-z ]+?))'s first name becomes (\w+)", s)
    if m:
        name = m.group(3).title()
        return [_fx(do="change_name", role=ctx.need(role_of(m.group(1) or m.group(2))), name=name)]
    m = re.fullmatch(r"(?:each )?changes? age \((\d+) years? (older|younger)(?:; never past (elder|\d+))?"
                     r"(?:; never (?:younger than|below) (\d+))?\)", s)
    if m:
        n = int(m.group(1))
        cap = None if not m.group(3) else 75 if m.group(3) == "elder" else int(m.group(3))
        if m.group(4):
            ctx.notes.append(f"\"never younger than {m.group(4)}\": the engine has no lower age limit; the role is "
                             f"cast {int(m.group(4)) + n} or older instead")
            ctx.need(who, min_age=int(m.group(4)) + n)
        return [_fx(do="change_age", role=r, years=[n, n] if m.group(2) == "older" else [-n, -n], max_age=cap)]
    m = re.fullmatch(r"changes age: \(([^)]+)\) becomes (\d+) years (younger|older)", s)
    if m:
        n = int(m.group(2))
        return [_fx(do="change_age", role=ctx.need(role_of(m.group(1))),
                    years=[n, n] if m.group(3) == "older" else [-n, -n])]
    m = re.fullmatch(r"(?:each )?changes? age \(to ([a-z0-9]+)(?:, ([a-z0-9]+))?\)", s)
    if m:
        return [_fx(do="change_age", role=r, to=_age_class(m.group(1), m.group(2)))]
    if re.fullmatch(r"(?:new look \(the |gets the |the )?\"old\" head look\)?", s):
        return [_fx(do="old_look", role=r)]
    if re.fullmatch(r"(?:new look \(the |gets the |the |gets? a new look \(the )?young head look\)?", s):
        return [_fx(do="young_look", role=r)]
    m = re.fullmatch(r"new look(?: for \(([^)]+)\)| for the ([a-z ]+?))?(?: \((.+?)\))?(?: for \(([^)]+)\))?", s)
    if m:
        target = role_of(m.group(1) or m.group(2) or m.group(4)) if (m.group(1) or m.group(2) or m.group(4)) \
            else who
        what = (m.group(3) or "head").lower()
        r2 = ctx.need(target)
        if "old" in what and "head" in what:
            return [_fx(do="old_look", role=r2)]
        if "young" in what:
            return [_fx(do="young_look", role=r2)]
        if "head" in what or "face" in what:
            return [_fx(do="appearance", role=r2, head="random")]
        return [_fx(do="appearance", role=r2, body="random")]
    m = re.fullmatch(r"(?:is )?pregnant(?: with one baby)?(?:: one of the couple \(any birth sex.*?\) with the other)?"
                     r"(?:, with \(([^)]+)\) as the other parent)?(?: \((.*?)\))?", s)
    if m:
        partner = role_of(m.group(1)) if m.group(1) else ("friend" if "couple" in s else None)
        note = (m.group(2) or "").lower()
        babies = "roll" if "twins or triplets" in note else 2 if "twins" in note else None
        carrier = ctx.need(who, min_age=18, carrier=True)
        if partner is not None:
            ctx.need(partner, min_age=18)
        any_birth = any_sex or "magic" in note or "couple" in s
        # A couple's pregnancy (a partner, no reason for any birth sex): the partner may carry by the player's chance
        # (engine flags bit 3; the owner, 2026-11-16).  A reason-based one keeps its any_birth_sex alone.
        return [_fx(do="pregnant", role=carrier, partner=partner, babies=babies,
                    any_birth_sex=True if any_birth else None,
                    partner_may_carry=True if partner is not None and not any_birth else None)]
    m2 = re.match(r"becomes nursing (?:both|the two) [a-z' ]*?babies", s)
    if m2:
        s = s.replace(m2.group(0), "becomes nursing a baby", 1)
        twins = True
    else:
        twins = False
    m = re.fullmatch(r"becomes nursing (?:(?:the|a|an) [a-z' ]*?baby|one of \(([^)]+)\)'s twins)(?: \(single parent\))?"
                     r"(?:,? with \((?:his/her\) partner \()?([^)]+)\) as the other parent|,? with \(his/her\) partner if "
                     r"\(he/she\) has one|, as its second parent)?(?: \(.*\))?(?: \(single parent\))?", s)
    if m:
        carrier = ctx.need(who, min_age=18, carrier=True)
        partner = role_of(m.group(1) or m.group(2)) if (m.group(1) or m.group(2)) else None
        return [_fx(do="nursing", role=carrier, partner=partner, any_birth_sex=True if any_sex else None,
                    babies=2 if twins else None)]
    raise Unmapped(raw)


def _age_class(a: str, b: str | None) -> str:
    for w in (a, b or ""):
        if w in ("child", "teen", "adult", "elder", "18", "50"):
            return w
    n = int(a) if a.isdigit() else int(b) if b and b.isdigit() else None
    if n is None:
        raise Unmapped(f"changes age (to {a})")
    return "child" if n < 14 else "teen" if n < 18 else "18" if n < 20 else "adult" if n < 50 else "50" if n < 55 \
        else "elder"


_GAME_SPEC = re.compile(r"^vv\s*(\d)(?:\s*-\s*vv\s*(\d))?(?:\s*only)?$")


def _spec_games(spec: str) -> list[int] | None:
    out: list[int] = []
    for part in re.split(r",\s*|\s+and\s+", spec.strip().lower()):
        m = _GAME_SPEC.match(part.strip())
        if not m:
            return None
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        out += range(a, b + 1)
    return out


def _pref(kind: str, words: str, r: str | None, ctx: _Ctx, remove: bool = False) -> list[dict]:
    """A like or dislike in the owner's words: "swimming", "heights (vv2: ...; story only in vv4)" (commentary in
    brackets is the owner's note), "wood (vv2-vv5) or rocks (vv1)" (a word per game).  A word a game of the event
    lacks is given only in the games that have it (the effect's "_games": the event gates it by game), as the owner's
    notes say ("story only" elsewhere)."""
    w = re.sub(r"\s+or similar if available$", "", words.strip().strip('"').lower())
    pairs = re.findall(r"vv([1-5]):\s*([a-z ]+?)(?:\s+or\s+[a-z ]+?)?\s*(?=;|\)|$)", w)
    if len(pairs) >= 2 and re.search(r"\(\s*vv[1-5]:", w):
        # "berry picking (vv1: berries; vv2: coconuts; ...)": a word for each game
        out = []
        for g, word in pairs:
            g = int(g)
            if g in ctx.games and word.strip() in cie.GAMES[g].preferences:
                e = _fx(do="preference", role=r, remove=True if remove else None, **{kind: word.strip()})
                e["_games"] = [g]
                out.append(e)
        if out:
            merged: dict[str, dict] = {}
            for e in out:                    # one effect per word, its games together
                key = e[kind]
                if key in merged:
                    merged[key]["_games"] = sorted(set(merged[key]["_games"]) | set(e["_games"]))
                else:
                    merged[key] = e
            for e in merged.values():
                if set(e["_games"]) == set(ctx.games):
                    del e["_games"]
            return list(merged.values())
    parts = [p.strip() for p in re.split(r"\s+or\s+(?![^()]*\))", w) if p.strip()]
    explicit: list[tuple[str, list[int]]] = []
    for p in parts:
        m = re.match(r"^(.+?)\s*\(([^()]*)\)\s*$", p)
        games = _spec_games(m.group(2)) if m else None
        if m and games is not None:
            explicit.append((m.group(1).strip(), games))
    if explicit and len(explicit) == len(parts):
        out = []
        for word, games in explicit:
            have = [g for g in ctx.games if g in games and word in cie.GAMES[g].preferences]
            if have:
                e = _fx(do="preference", role=r, remove=True if remove else None, **{kind: word})
                if set(have) != set(ctx.games):
                    e["_games"] = have
                out.append(e)
        if not out:
            raise Unmapped(f"{kind} {words} (no game of the event has these words)")
        return out
    word = re.sub(r"\s*\(.*\)\s*$", "", parts[0]).strip()       # the owner's commentary in brackets
    word = re.sub(r"\s*\(.*$", "", word).strip()
    have = [g for g in ctx.games if word in cie.GAMES[g].preferences]
    if not have:
        alt, note = pref_word(word, ctx.games)
        if alt is None:
            raise Unmapped(f"{kind} {words} ({note})")
        ctx.notes.append(note)
        word, have = alt, list(ctx.games)
    e = _fx(do="preference", role=r, remove=True if remove else None, **{kind: word})
    if set(have) != set(ctx.games):
        e["_games"] = have           # given where the game has the word; the owner's "story only" elsewhere
    return [e]


def _newcomers(inner: str, count: int) -> list[dict]:
    """'an adult woman, the mother' / 'two adults' / 'one adult, one teen aged 14 to 17, one child' / 'adult' ->
    new_villager effects."""
    out: list[dict] = []
    parts = re.split(r",\s*|\s+and\s+", inner.lower())
    for part in parts:
        p = part.strip()
        if not p or re.match(r"^(the|with) ", p):
            continue
        m = re.match(r"^(?:(a|an|one|two|three|\d+)\s+)?(baby|babies|child|children|teen|teens|adult|adults|elder|"
                     r"elders|man|men|woman|women|boy|girl)\b(?: (man|woman|boy|girl))?", p)
        if not m:
            if out:
                continue
            raise Unmapped(f"new villager ({inner})")
        n = NUMBERS.get(m.group(1) or "one") or (int(m.group(1)) if (m.group(1) or "").isdigit() else 1)
        if m.group(2) in ("babies", "children", "teens", "adults", "elders", "men", "women") and not m.group(1):
            n = 2
        noun = m.group(2).rstrip("s").replace("childre", "child").replace("babie", "baby").replace("men", "man")
        age = {"baby": "child", "child": "child", "boy": "child", "girl": "child", "teen": "teen", "adult": "adult",
               "man": "adult", "woman": "adult", "wo": "adult", "elder": "elder"}.get(noun, "adult")
        sexword = m.group(3) or (noun if noun in ("man", "woman", "boy", "girl") else "")
        sex = {"man": "male", "boy": "male", "woman": "female", "girl": "female"}.get(sexword)
        for _ in range(n):
            out.append(_fx(do="new_villager", age=age, sex=sex))
    if count > 1 and len(out) == 1:
        out = out * count
    return [dict(e) for e in out]


# ---- WHO lines -----------------------------------------------------------------------------------------------------

def who_roles(text: str) -> dict[str, dict]:
    """The roles a WHO line (or a seed's role line) describes: {"": main villager facts, "young": {...}, ...}."""
    out: dict[str, dict] = {}
    for seg in re.split(r"[.;]\s+|\.\s*$", text):
        seg = seg.strip()
        if not seg:
            continue
        m = re.match(r"^\(([^)]+)\)\s*(?:=|:)?\s*(.*)$", seg)
        rid = ""
        body = seg
        if m:
            rid = role_of(m.group(1)) or ""
            body = m.group(2)
        facts = _age_facts(body)
        if "born female" in body.lower():
            facts["sex"] = "female"
        if re.search(r"(?i)\bthe tribal chief\b", body):
            facts["special"] = "tribal_chief"
        if re.search(r"(?i)\b(an isolan|unconverted islander|heathen)\b", body):
            facts["believers_only"] = False
        if facts:
            out.setdefault(rid, {}).update(facts)
        for m2 in re.finditer(r"\(([^)]+)\)\s+(?:a|an)\s+[a-z ]+?:\s*any villager\s+(\d+)(?:\s*to\s*(\d+)|\+)", seg):
            rid2 = role_of(m2.group(1)) or ""
            f2 = {"min_age": int(m2.group(2))}
            if m2.group(3):
                f2["max_age"] = int(m2.group(3))
            out.setdefault(rid2, {}).update(f2)
    return out


def _age_facts(body: str) -> dict:
    b = body.lower()
    m = re.search(r"(?:aged\s+)?(\d+)\s*to\s*(\d+)", b)
    if m:
        return {"min_age": int(m.group(1)), "max_age": int(m.group(2))}
    m = re.search(r"(?:aged\s+)?(\d+)\s*(?:or older|\+)", b)
    if m:
        return {"min_age": int(m.group(1))}
    if re.search(r"\belder\b", b):
        return {"min_age": 55}
    if "any age" in b:
        return {"min_age": 0}
    return {}


def role_dict(facts: dict) -> dict:
    role = {"kind": "villager"}
    for k in ("min_age", "max_age", "sex", "special", "believers_only"):
        if k in facts:
            role[k] = facts[k]
    if role.get("max_age") and role.get("max_age", 80) < role.get("min_age", 14):
        role.pop("max_age")
    return role


# ---- Placeholders ----------------------------------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """The owner's placeholders as the engine's: "(young name)" -> "(young)", "(Young Name)" -> "(Young)",
    "(new name)" -> "(made1)" and "(new name 2)" -> "(made2)" (engine 5ee2b3dc0: the villagers the event made, also
    inside count tokens), "(name2.he/she)" -> "(friend.he/she)" (name2 is the role "friend")."""
    def ph(m: re.Match) -> str:
        inner = m.group(1)
        md = re.fullmatch(r"(?i)(name[12])(?:\.|:\s*)(.+)", inner)    # "(name2.he/she)", "(name2: he/she)"
        if md:          # "(name2.he/she)": the second villager's ("friend"), "(name1.he/she)" the first's
            return f"(friend.{md.group(2)})" if md.group(1).lower() == "name2" else f"({md.group(2)})"
        mr = re.fullmatch(r"(?i)([a-z][a-z ]*?) name(?:\.|:\s*)([A-Za-z]+/[A-Za-z]+)", inner)
        if mr and role_of(mr.group(1) + " name"):    # "(healer name: his/her)" -> "(healer.his/her)"
            return f"({role_of(mr.group(1) + ' name')}.{mr.group(2)})"
        mc = re.fullmatch(r"([A-Z][a-z]+)\.([A-Za-z]+/[A-Za-z]+)", inner)
        if mc and mc.group(1).lower() not in ("name", "name1", "name2"):    # "(Child.He/She)" -> "(child.He/She)"
            return f"({mc.group(1).lower()}.{mc.group(2)})"
        mm = re.fullmatch(r"([A-Za-z]+) (name|Name)( \d)?", inner)
        if mm:
            if mm.group(1).lower() == "new":
                made = "(made2)" if (mm.group(3) or "").strip() == "2" else "(made1)"
                return made if mm.group(2) == "name" else made.replace("made", "Made")
            word = mm.group(1)
            return "(" + (word.lower() if mm.group(2) == "name" else word[0].upper() + word[1:].lower()) + ")"
        if inner.lower() == "him/hers":
            return "(" + ("His/Hers" if inner[0].isupper() else "his/hers") + ")"     # the standalone possessive
        mn = re.fullmatch(r"([A-Z][a-z]+)/([A-Z][a-z]+)", inner)
        kin = {"grandfather", "grandmother", "father", "mother", "son", "daughter", "brother", "sister", "uncle", "aunt",
               "husband", "wife", "boy", "girl", "man", "woman", "king", "queen", "lord", "lady", "sir", "madam",
               "grandpa", "grandma", "dad", "mom", "nephew", "niece", "prince", "princess", "he", "she"}
        if mn and inner.lower() not in cie.PRONOUNS_V6 and not ({mn.group(1).lower(), mn.group(2).lower()} & kin):
            return "(renamed)"        # "(Gin/Ginger)": the new name by sex -- the latest change_name's (renamed)
        return m.group(0)
    text = re.sub(r"\(([^()\n]*)\)", ph, text)
    return fix_count_tokens(text)


def fix_count_tokens(text: str) -> str:
    """A count token's options hold no . ! ? (engine 0853e8327): "One. Just the one" -> "One, just the one"; a
    closing mark is dropped."""
    def opt(o: str) -> str:
        o = re.sub(r"[.!?]+\s+([A-Za-z])", lambda m: ", " + m.group(1).lower(), o)
        o = re.sub(r"[.!?]+(\"?)\s*$", r"\1", o)
        return re.sub(r"[.!?]+", ",", o)

    def tok(m: re.Match) -> str:
        kind, opts = m.group(1), m.group(2).split("|")
        return "{#" + kind + ":" + "|".join(opt(o) for o in opts) + "}"
    return re.sub(r"\{#(babies|made):([^{}\n]*)\}", tok, text)
