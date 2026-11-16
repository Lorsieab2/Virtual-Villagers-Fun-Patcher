"""The island events' content controls (v1.35.97, the owner 2026-11-15): content notes and content filters for the
NEW island events (the Isola Grand Event Collection's sources and the Living Event Engine's variants).
The game's own events are never touched.

THE TAGS.  Every node of a new event carries the content filters (F01-F28) its own words or effects touch.  They come
from the tag table of the event's source (data/event_collection/content_tags/<source>.json, written by
scripts/build_event_content_tags.py, so the event files themselves are never churned); an event a table does not hold
yet is tagged the same way at build time (tag_graph).  Filters never hide a kind of person: diversity, disability,
identity, sex or gender changes, same-sex relationships, religion, romance in general, family forms and singlehood are
never a filter (a sex change or a change of faith is never tagged).

WHAT THE BUILD WRITES INTO EACH COMPILED EVENT (inject), so the game needs nothing but the installed patches' list
("Installed Patches.txt": every filter the player ticked is a patch id there, island_event_filter_fNN):
  * a random child (any node's weighted children; never a player's choice) whose own part of the graph -- the nodes
    that can no longer be reached without it -- carries filters gets the condition "none of those filters on": the
    filtered outcome is dropped and the others keep their shares;
  * the event's requirement gets "not skipped": the event is left out of the random draw at a natural island event's draw (and Pick Island Event
    and the library say the content filters keep it out) when a ticked filter's content can still be reached -- it is
    on the way to every outcome, or behind a player's choice -- or when the ticked filters would drop every child of
    one node.  Applied BEFORE the draw picks an event (the requirement is part of the strict cast);
  * the content note (Content Notes for Island Events, island_event_content_notes): the first text the event shows
    gets a variant that starts with "Content note: <labels>" -- the labels of what the event may contain, never
    which outcome comes -- each label left out while the ticked filters drop all of its content;
  * STORY TRAITS (the owner, 2026-11-15): "The Quiet Hands" (Inner Life 3, il003_*) gives the villager it casts the
    story trait "mute" (a "trait" effect, code 26, kept in the same per-villager file); every role whose words have
    them speak (a "speaks" role: speaking_roles) never takes a story-mute villager.
"""
from __future__ import annotations

import copy
import itertools
import json
import re
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
TAGS_DIR = ROOT / "data" / "event_collection" / "content_tags"

# The owner's content filters (2026-11-15), in the order the patcher lists them.
FILTERS: dict[str, str] = {
    "F01": "Child and baby deaths",
    "F02": "Pregnancy loss, stillbirth and death in childbirth",
    "F03": "All deaths in events",
    "F04": "Disappearances",
    "F05": "Grief and bereavement",
    "F06": "Serious injury, permanent impairment and amputation",
    "F07": "Burns, scars and lasting visible injuries",
    "F08": "Serious illness and medical emergencies",
    "F09": "Epidemics and contagion",
    "F10": "Difficult births and premature babies",
    "F11": "Severe emotional distress",
    "F12": "Hopelessness",
    "F13": "Unsettling and eerie scenes",
    "F14": "Implied past abuse",
    "F15": "Historical war, persecution, slavery and displacement",
    "F16": "Bullying and social cruelty",
    "F17": "Prejudice and discrimination as a subject",
    "F18": "Children in danger",
    "F19": "Abandonment and orphanhood",
    "F20": "Hunger and poverty",
    "F21": "Serious disasters",
    "F22": "Deep water and drowning",
    "F23": "Fires",
    "F24": "Animal death and serious animal injury",
    "F25": "Hunting and fishing",
    "F26": "Creepy-crawlies (snakes, spiders, insects)",
    "F27": "Lasting changes to a villager",
    "F28": "Teen romance and intimacy",
}
FILTER_IDS = tuple(FILTERS)
NOTES_PATCH = "island_event_content_notes"


def filter_patch(fid: str) -> str:
    """The installed patches' id (without the game's vvN_ prefix) of content filter `fid`."""
    return "island_event_filter_" + fid.lower()


# The content notes (the owner's labels, in this order) and the filters whose content each one names.
NOTE_LABELS: dict[str, tuple[str, ...]] = {
    "Child death": ("F01",),
    "Pregnancy loss": ("F02",),
    "Bereavement": ("F03", "F05"),
    "Serious injury": ("F06",),
    "Disappearance": ("F04",),
    "Historical suffering": ("F15",),
    "Emotional distress": ("F11", "F12"),
}
NOTE_PREFIX = "Content note: "
MAX_REMOVABLE_LABELS = 4            # past this many, every label is always shown (no combinations)


# Effects and the filters they always carry.  A sex change and a change of faith are never filtered (a kind of person
# is never hidden).
EFFECT_FILTERS: dict[str, tuple[str, ...]] = {
    "kill": ("F03", "F05"),
    "die_unrecovered": ("F03", "F05"),
    "vanish": ("F04",),
    "baby_lost": ("F02", "F05"),
    "birth_then_die": ("F02", "F03", "F05"),
    "deliver_early": ("F10",),
    "sick": ("F08",),
    "old_look": ("F27",),
    "appearance": ("F27",),
    "damage": ("F21",),
}

# The words that tag a node (case-insensitive; whole words).  A careful pass over the new events' text: each pattern
# names the subject itself, never a kind of person.
_W = r"(?<![A-Za-z])"
_E = r"(?![A-Za-z])"
KEYWORDS: dict[str, str] = {
    "F01": r"(child|baby|infant|newborn|toddler|son|daughter)('s)?\s+(\w+\s+){0,4}(died|dies|death|did not survive|"
           r"does not survive|was lost|is lost|passed away)|death of (a|the|their|her|his) (child|baby|son|daughter)",
    "F02": r"miscarr\w*|stillb\w*|lost the baby|loses the baby|lose the baby|died in childbirth|dies in childbirth|"
           r"death in childbirth|baby (was|is) lost|lost (her|their) (unborn|baby)|pregnancy (ends|ended|loss)",
    "F03": r"dies|died|passes away|passed away|is dead|was dead|funeral|burial|buried|death of|deaths?|"
           r"did not survive|does not survive|killed|perish\w*|last breath",
    "F04": r"disappear(s|ed|ance)?|vanish(es|ed)?|never seen again|never returns?|never returned|"
           r"(is|was|goes|went) missing|without a trace",
    "F05": r"grief|griev\w+|mourn\w*|bereave\w*|funeral|widow(ed|er)?|loss of (a|the|their|his|her)\s+\w+|"
           r"memorial (for|to) the dead|in memory of",
    "F06": r"amputat\w+|paraly[sz]\w*|crippl\w+|lasting impairment|permanent (injury|impairment|damage)|"
           r"(broken|shattered|crushed) (leg|arm|hand|foot|bone|back|spine|ribs?)|"
           r"(badly|seriously|gravely|severely) (hurt|injured|wounded|burned)|"
           r"lost (his|her|their|an?) (leg|arm|hand|foot|eye|fingers?)|reduced mobility|never walk|"
           r"serious(ly)? (injury|injuries)|grave injur\w+",
    "F07": r"burn(s|ed|t)?|scald\w*|scar(s|red|ring)?|disfigur\w+",
    "F08": r"(seriously|gravely|critically|deathly|dangerously) ill|fever(s|ish)?|infection|infected|"
           r"medical emergency|unconscious|collaps(es|ed)|sickness spreads|grows weaker|"
           r"(serious|grave|dangerous|mysterious) (illness|sickness|condition|disease)",
    "F09": r"epidemic\w*|contagi\w+|plague\w*|quarantin\w+|outbreak|spread(s|ing)? (through|among|to) the village|"
           r"catch(es)? it from",
    "F10": r"prematur\w+|difficult (birth|labou?r|delivery)|born (too )?early|(labou?r|birth) (begins|began|comes|came)"
           r" early|early (labou?r|birth)",
    "F11": r"despair\w*|anguish\w*|breaks? down (in tears|sobbing)|sobb\w+|traumat\w+|panic(s|ked)?|"
           r"inconsolable|distraught|cannot stop (crying|shaking)|weeps? uncontrollably|terrif(ied|ying)",
    "F12": r"hopeless\w*|no reason to (live|go on)|lost all hope|gives? up on (life|living|everything)|"
           r"no hope left|wants? to die",
    "F13": r"eerie|uncann\w+|creep(y|ier|iest)|haunt\w*|ghosts?|ghostly|phantoms?|spectral|sinister|ominous|"
           r"chill (runs|ran) down|shiver(s|ed)? down|unsettl\w+|nightmar\w+",
    "F14": r"abus(e|ed|ive|er)|mistreat\w*|beaten by|beat (him|her|them) as",
    "F15": r"wars?|warfare|battles?|enslav\w+|slaver\w*|slaves?|persecut\w+|massacr\w+|conquer\w*|invad\w+|"
           r"invasion|refugees?|displaced|driven from (their|his|her) (home|land)|exiled",
    "F16": r"bull(y|ies|ied|ying)|taunt\w*|ridicul\w+|ostraci[sz]\w+|shunn?(ed|s|ing)?|cruel(ty|ly)?|"
           r"humiliat\w+|laughed at|picked on",
    "F17": r"prejudic\w+|discriminat\w+|bigot\w*|looked down on because|because (he|she|they) (is|are|was|were) "
           r"different|treated (as|like) (an )?outsiders?",
    "F18": r"(child|children|boy|girl|toddler|baby|little ones?|youngster)\w*\s+(\w+\s+){0,5}(in danger|trapped|"
           r"drown\w*|fell (into|from|off)|falls (into|from|off)|lost in|swept away|stranded)|danger to the children",
    "F19": r"orphan\w*|abandon\w*|left behind|foundling",
    "F20": r"hunger|hungry|starv\w+|famine|not enough food|poverty|food (runs|ran) out|nothing to eat",
    "F21": r"hurricanes?|floods?|flooding|earthquakes?|tsunamis?|volcan\w+|erupt\w+|landslides?|mudslides?|"
           r"disasters?|wildfires?|cyclones?|typhoons?|great storm|terrible storm|violent storm",
    "F22": r"drown\w*|deep water|undertow|swept out to sea|pulled under|riptide|current (pulls|pulled|drags|dragged)",
    "F23": r"blaze|flames|on fire|caught fire|catch(es)? fire|wildfires?|fire spread\w*|fire broke out|"
           r"(hut|house|home|roof|forest|storehouse|field)s? (burns?|burned|burning)",
    "F24": r"(animal|bird|dolphin|turtle|fish|goat|pig|dog|monkey|creature|crab|parrot|whale|seal|lizard)s?"
           r"\s+(\w+\s+){0,3}(died|dies|dead|killed|injured|wounded|hurt)|carcass\w*|dead (animal|bird|fish|dolphin)",
    "F25": r"hunt(s|ed|ing|ers?)?|fishing|fished|fisher(man|men|woman|women|s)?|spearfish\w*|catch(es|ing)? fish|"
           r"caught (a |the )?fish|traps? (for )?animals|snares?",
    "F26": r"snakes?|serpents?|spiders?|scorpions?|centipedes?|millipedes?|insects?|beetles?|cockroach\w*|"
           r"wasps?|hornets?|leech\w*|mosquito\w*|ants|termites?|maggots?|worms?|bugs?|tarantula\w*",
    "F27": r"permanent(ly)?|for the rest of (his|her|their) li(fe|ves)|never (be )?the same again|"
           r"changed forever|lasting (change|mark|effects?)",
    "F28": r"(kiss\w*|crush|in love|courting|sweetheart|flirt\w*|romance|romantic)",
}
_COMPILED = {f: re.compile(_W + "(" + p + ")" + _E, re.IGNORECASE) for f, p in KEYWORDS.items()}
# Teen romance needs a teenager: a role of 13 to 17 (its age range) or the words.
_TEEN = re.compile(_W + r"(teen\w*|adolescen\w*|young (couple|lovers)|first love)" + _E, re.IGNORECASE)


def _text_filters(text: str) -> set[str]:
    out = {f for f, rx in _COMPILED.items() if f != "F28" and rx.search(text)}
    if _COMPILED["F28"].search(text) and _TEEN.search(text):
        out.add("F28")
    return out


def _node_words(g: dict, node: dict) -> str:
    """Everything a node can show: its text, its variants, its choices' labels and the items of the pools its text
    draws from (a pool's words are part of the node that shows them)."""
    parts = [node.get("text") or ""]
    parts += [v.get("text") or "" for v in node.get("variants", [])]
    parts += [c.get("label") or "" for c in node.get("choices", [])]
    pools = g.get("pools", {}) or {}
    for name in re.findall(r"\{([A-Za-z0-9_]+)(?:\.\d+)?\}", " ".join(parts)):
        for it in (pools.get(name) or {}).get("items", []):
            parts.append(it.get("text") if isinstance(it, dict) else str(it))
    return "\n".join(p for p in parts if p)


def _young_role(g: dict, rid: str | None) -> bool:
    r = (g.get("roles") or {}).get(rid or "", {})
    return r.get("kind") == "villager" and r.get("max_age") is not None and r["max_age"] < 14


def tag_graph(g: dict) -> dict[str, list[str]]:
    """Each node's filters (only the tagged ones), from its effects and its words."""
    out: dict[str, list[str]] = {}
    for nid, node in g["nodes"].items():
        tags = _text_filters(_node_words(g, node))
        for e in node.get("effects", []):
            do = e.get("do")
            tags.update(EFFECT_FILTERS.get(do, ()))
            if do in ("food",) and isinstance(e.get("amount"), int) and e["amount"] < 0:
                tags.add("F20")
            if do == "health_change" and isinstance(e.get("min"), int) and e["min"] <= -25:
                tags.add("F06")
            if do in ("kill", "die_unrecovered", "vanish") and _young_role(g, e.get("role")):
                tags.update(("F01", "F18"))
        if tags:
            out[nid] = sorted(tags)
    return out


# ---- Who speaks -----------------------------------------------------------------------------------------------------

SPEECH_VERBS = (r"says|said|asks|asked|replies|replied|whispers|whispered|shouts|shouted|tells|told|answers|answered|"
                r"explains|explained|announces|announced|declares|declared|admits|admitted|insists|insisted|"
                r"suggests|suggested|exclaims|exclaimed|mutters|muttered|murmurs|murmured|calls out|called out|"
                r"sings|sang|speaks|spoke|says aloud|cries out|cried out|jokes|joked|promises|promised|"
                r"protests|protested|argues|argued|begs|begged|laughs and says|adds|added")
_ROLE_TOKEN = r"\((?P<tok>[A-Za-z0-9_]+)(?:\.[A-Za-z]+)?\)"
_SPEAKS_AFTER = re.compile(_ROLE_TOKEN + r"[^.!?\n\"]{0,40}?\b(?:" + SPEECH_VERBS + r")\b", re.IGNORECASE)
_SPEAKS_BEFORE = re.compile(r"\b(?:" + SPEECH_VERBS + r")\s+" + _ROLE_TOKEN, re.IGNORECASE)
_SPEAKS_COLON = re.compile(_ROLE_TOKEN + r"\s*:\s*\"")
_PRONOUN_TOKENS = {"name", "he/she", "his/her", "him/her", "man/woman", "himself/herself", "boy/girl", "son/daughter"}


def speaking_roles(g: dict) -> list[str]:
    """The villager roles whose words the event's text gives them to say (a quoted line attributed to them, "(Name)
    says", "asks (friend.name)", "(Healer1): \"..."): such a role never takes a story-mute villager."""
    roles = g.get("roles", {})
    lower = {r.lower(): r for r in roles}
    default = "subject" if "subject" in roles else next(iter(roles), None)
    found: list[str] = []
    for node in g["nodes"].values():
        texts = [node.get("text") or ""] + [v.get("text") or "" for v in node.get("variants", [])]
        for text in texts:
            for rx in (_SPEAKS_AFTER, _SPEAKS_BEFORE, _SPEAKS_COLON):
                for m in rx.finditer(text):
                    tok = m.group("tok").lower()
                    rid = lower.get(tok, default if tok in _PRONOUN_TOKENS else None)
                    if rid is not None and roles[rid].get("kind") == "villager" and rid not in found:
                        found.append(rid)
    return found


# The story traits the owner named (2026-11-15): the event (its id's start) and the trait its cast villager keeps.
TRAIT_EVENTS = {"il003": "mute"}


def event_traits(event_id: str, g: dict) -> list[dict]:
    """The traits an event gives: [{"role", "trait"}] (The Quiet Hands: its subject keeps "mute")."""
    for prefix, trait in TRAIT_EVENTS.items():
        if event_id.startswith(prefix):
            roles = g.get("roles", {})
            rid = "subject" if "subject" in roles else next(iter(roles), None)
            return [{"role": rid, "trait": trait}] if rid else []
    return []


# ---- The tag tables ------------------------------------------------------------------------------------------------

_tables: dict[str, dict] = {}


def table_path(source: str) -> Path:
    return TAGS_DIR / f"{source}.json"


def load_table(source: str) -> dict:
    """A source's tag table: {event id: {"nodes": {node: [filters]}, "filters": [...], "notes": [...]}}."""
    if source not in _tables:
        path = table_path(source)
        _tables[source] = json.loads(path.read_text(encoding="utf-8"))["events"] if path.is_file() else {}
    return _tables[source]


def node_tags_for(source: str, event_id: str, g: dict) -> dict[str, list[str]]:
    """The event's node tags: its table's, or (not in the table yet) tagged now."""
    entry = load_table(source).get(event_id)
    if entry is not None:
        return {n: list(t) for n, t in entry.get("nodes", {}).items() if n in g["nodes"]}
    return tag_graph(g)


def table_entry(g: dict, node_tags: dict[str, list[str]], event_id: str = "") -> dict:
    """A tag table's entry for one event: its nodes' filters, every filter, the content notes it may show, the roles
    whose words have them speak and the story traits it gives."""
    every = sorted({f for t in node_tags.values() for f in t})
    entry = {"filters": every, "notes": [lab for lab, fs in NOTE_LABELS.items() if set(fs) & set(every)],
             "nodes": {n: list(t) for n, t in sorted(node_tags.items())}}
    speaks = speaking_roles(g)
    if speaks:
        entry["speaks"] = speaks
    traits = event_traits(event_id, g)
    if traits:
        entry["traits"] = traits
    return entry


def extras_for(source: str, event_id: str, g: dict) -> dict:
    """The event's speaking roles and traits: its table's, or (not in the table yet) found now."""
    entry = load_table(source).get(event_id)
    if entry is not None:
        return {"speaks": [r for r in entry.get("speaks", []) if r in g["roles"]],
                "traits": [t for t in entry.get("traits", []) if t.get("role") in g["roles"]]}
    return {"speaks": speaking_roles(g), "traits": event_traits(event_id, g)}


# ---- The graph's structure -----------------------------------------------------------------------------------------

def _edges(node: dict) -> list[tuple[str, str, int]]:
    """(kind, target, index): its weighted children ("child"), their else ("else"), its choices ("choice") and its
    own else ("node_else")."""
    out = []
    for i, c in enumerate(node.get("children", [])):
        out.append(("child", c["next"], i))
        if c.get("else"):
            out.append(("else", c["else"], i))
    for i, c in enumerate(node.get("choices", [])):
        out.append(("choice", c["next"], i))
    if node.get("else"):
        out.append(("node_else", node["else"], -1))
    return out


def _reach(g: dict, removed: frozenset = frozenset()) -> set[str]:
    """The nodes reachable from the start without the child edges in `removed` ((node, index))."""
    seen, stack = set(), [g["start"]]
    while stack:
        nid = stack.pop()
        if nid in seen or nid not in g["nodes"]:
            continue
        seen.add(nid)
        for kind, target, i in _edges(g["nodes"][nid]):
            if kind == "child" and (nid, i) in removed:
                continue
            stack.append(target)
    return seen


def _droppable(node: dict, i: int) -> bool:
    """A child the filters may drop: a weighted child with no else of its own (a failed condition leaves it out)."""
    return not node["children"][i].get("else")


def carried(g: dict, tags: dict[str, list[str]]) -> dict[tuple[str, int], frozenset]:
    """Each droppable child edge's filters: those of the nodes that cannot be reached without it."""
    every = _reach(g)
    out = {}
    for nid in every:
        node = g["nodes"][nid]
        if len(node.get("children", [])) < 2:
            continue                                 # one way on: nothing to choose between
        for i, c in enumerate(node.get("children", [])):
            if not _droppable(node, i):
                continue
            alone = every - _reach(g, frozenset({(nid, i)}))
            fs = frozenset(f for n in alone for f in tags.get(n, ()))
            if fs:
                out[(nid, i)] = fs
    return out


def _mask(fs: Iterable[str]) -> int:
    return sum(1 << (int(f[1:]) - 1) for f in set(fs))


def plan(g: dict, tags: dict[str, list[str]]) -> dict:
    """What the filters do to the event: each dropped edge's filters, the skip groups (the event is skipped when every
    member of one group meets a ticked filter), each content note's label and the filters that take it away."""
    edges = carried(g, tags)
    every = _reach(g)
    groups: list[list[frozenset]] = []
    present = sorted({f for n in every for f in tags.get(n, ())})
    for f in present:
        gone = frozenset(e for e, fs in edges.items() if f in fs)
        if any(f in tags.get(n, ()) for n in _reach(g, gone)):
            groups.append([frozenset({f})])          # still reachable with f on: f skips the event
    for nid in sorted(every):
        node = g["nodes"][nid]
        kids = node.get("children", [])
        if kids and all((nid, i) in edges for i in range(len(kids))):
            groups.append([edges[(nid, i)] for i in range(len(kids))])
    labels = []
    for label, fs in NOTE_LABELS.items():
        holders = {n for n in every if set(tags.get(n, ())) & set(fs)}
        if not holders:
            continue
        removers = []
        for f in FILTER_IDS:
            gone = frozenset(e for e, x in edges.items() if f in x)
            if not (holders & _reach(g, gone)):
                removers.append(f)
        labels.append((label, removers))
    return {"edges": edges, "groups": groups, "labels": labels, "present": present}


# ---- Writing it into the graph -------------------------------------------------------------------------------------

def _patch(f: str) -> dict:
    return {"patch": filter_patch(f)}


def _none_on(fs: Iterable[str]) -> dict:
    fs = sorted(set(fs))
    return {"not": _patch(fs[0])} if len(fs) == 1 else {"not": {"any": [_patch(f) for f in fs]}}


def _all(*cs: Any) -> Any:
    cs = [c for c in cs if c is not None]
    if not cs:
        return None
    if len(cs) == 1:
        return cs[0]
    flat = []
    for c in cs:
        flat += c["all"] if "all" in c else [c]
    return {"all": flat}


def _skip_cond(groups: list[list[frozenset]]) -> Any:
    """True when no group is covered: not(any group with every member meeting a ticked filter)."""
    covered = []
    for grp in groups:
        members = [({"any": [_patch(f) for f in sorted(fs)]} if len(fs) > 1 else _patch(next(iter(fs))))
                   for fs in grp]
        covered.append(members[0] if len(members) == 1 else {"all": members})
    if not covered:
        return None
    return {"not": covered[0] if len(covered) == 1 else {"any": covered}}


def _first_text_nodes(g: dict) -> list[str]:
    """The nodes whose text the event shows first: the start, or (a silent branch) the first text on each way on."""
    out, seen, stack = [], set(), [g["start"]]
    while stack:
        nid = stack.pop(0)
        if nid in seen or nid not in g["nodes"]:
            continue
        seen.add(nid)
        node = g["nodes"][nid]
        if node.get("type") != "branch" and (node.get("text") or node.get("variants")):
            out.append(nid)
            continue
        stack += [t for _k, t, _i in _edges(node)]
    return out


def note_line(labels: Iterable[str]) -> str:
    return NOTE_PREFIX + ", ".join(labels)


def _note_variants(node: dict, labels: list[tuple[str, list[str]]]) -> list[dict]:
    """The node's variants with the content note first: each set of labels that can be shown, as its condition."""
    fixed = [lab for lab, rem in labels if not rem]
    removable = [(lab, rem) for lab, rem in labels if rem]
    if len(removable) > MAX_REMOVABLE_LABELS:
        fixed = [lab for lab, _r in labels]
        removable = []
    order = [lab for lab in NOTE_LABELS]
    base = [(v["if"], v["text"]) for v in node.get("variants", [])] + [(None, node.get("text") or "")]
    out = []
    for keep in itertools.product((True, False), repeat=len(removable)):
        shown = fixed + [lab for (lab, _r), k in zip(removable, keep) if k]
        if not shown:
            continue
        conds = [{"patch": NOTES_PATCH}]
        for (lab, rem), k in zip(removable, keep):
            on = {"any": [_patch(f) for f in rem]} if len(rem) > 1 else _patch(rem[0])
            conds.append({"not": on} if k else on)
        line = note_line(sorted(shown, key=order.index))
        for cond, text in base:
            if not text:
                continue
            out.append({"if": _all(*conds, cond), "text": line + "\n" + text})
    return out + list(node.get("variants", []))


def _with_extras(g: dict, extras: dict | None) -> dict:
    """`g` (a copy when anything changes) with its speaking roles marked and its traits' effects written: on the
    start, or (a question, whose own effects are never made) on each of its answers' first nodes."""
    if not extras or not (extras.get("speaks") or extras.get("traits")):
        return g
    g = copy.deepcopy(g)
    for rid in extras.get("speaks", []):
        if g["roles"].get(rid, {}).get("kind") == "villager":
            g["roles"][rid]["speaks"] = True
    for t in extras.get("traits", []):
        start = g["nodes"][g["start"]]
        targets = [g["start"]] if start.get("type") != "question" else [c["next"] for c in start.get("choices", [])]
        for nid in dict.fromkeys(targets):
            node = g["nodes"][nid]
            effect = {"do": "trait", "role": t["role"], "trait": t["trait"]}
            if effect not in node.get("effects", []):
                node["effects"] = [effect] + list(node.get("effects", []))
    return g


def inject(g: dict, tags: dict[str, list[str]], extras: dict | None = None) -> tuple[dict, dict]:
    """The normalized graph `g` with the content controls written in (a copy) and the plan (for the reports)."""
    g = _with_extras(g, extras)
    if not tags:
        return g, {"edges": {}, "groups": [], "labels": [], "present": []}
    p = plan(g, tags)
    g = copy.deepcopy(g)
    patches = list(g.get("patches", []))

    def need(pid: str) -> None:
        if pid not in patches:
            patches.append(pid)

    for (nid, i), fs in p["edges"].items():
        child = g["nodes"][nid]["children"][i]
        child["if"] = _all(child.get("if"), _none_on(fs))
        for f in fs:
            need(filter_patch(f))
    skip = _skip_cond(p["groups"])
    if skip is not None:
        req = g.setdefault("requirement", {"min_eligible": 0})
        req["if"] = _all(req.get("if"), skip)
        for grp in p["groups"]:
            for fs in grp:
                for f in fs:
                    need(filter_patch(f))
    if p["labels"]:
        need(NOTES_PATCH)
        for lab, rem in p["labels"]:
            for f in rem:
                need(filter_patch(f))
        for nid in _first_text_nodes(g):
            node = g["nodes"][nid]
            node["variants"] = _note_variants(node, p["labels"])
    g["patches"] = patches
    return g, p
