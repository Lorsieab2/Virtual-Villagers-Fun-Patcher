"""Procedural island events, the data side (v1.35.97): split the owner's events into pieces, tag them, write the
pieces-<group>.pcb files, validate many compositions with the Python twin (src/vv_procedural.py) and write the
owner's sample.

    python scripts/procedural_pieces.py build      # split, tag, write assets/event_collection/pieces/*.pcb
    python scripts/procedural_pieces.py validate   # build, then compose N per game and check; bad pairs become
                                                   # NEVER WITH pairs (data/event_collection/procedural_never_with.json)
                                                   # and the build reruns until clean
    python scripts/procedural_pieces.py sample OUT # 100 composed events per game, readable text

Sources: every collection event (data/event_collection/<source>/**.json, through collection_check.graph_for_engine,
exactly what the engine reads) and the Living bank (data/living_events/bank.json: the Living Engine's seeds,
approaches, choices, archetypes and frames; the MC situations).  The owner's words are never changed: pieces are the
events' own texts; the only joins are where the engine composes (an intro popup and its question, a linear chain of
popups, the Living frame the living mixer already writes).  docs/event-collection/procedural-pieces-data.md says what
is split and how, and what is left out and why.

Single process, no game, no save, no install touched.
"""
from __future__ import annotations

import argparse
import collections
import copy
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import collection_check as cc            # noqa: E402
import vv_cie_graph as cg                # noqa: E402
import vv_event_content as ec            # noqa: E402
import vv_living_mixer as lm             # noqa: E402
import vv_procedural as vp               # noqa: E402
from vv_procedural import Effect, Link, Piece, Slot  # noqa: E402

COLLECTION = ROOT / "data" / "event_collection"
OUT_DIR = ROOT / "assets" / "event_collection" / "pieces"
NEVER_FILE = COLLECTION / "procedural_never_with.json"
REPORT_FILE = ROOT / "docs" / "event-collection" / "procedural-pieces-report.json"
FILE_BUDGET = 900_000                    # bytes: a group is split into parts below the engine's 1 MB
GAMES = (1, 2, 3, 4, 5)
ALL_GAMES = 0x1F

SERIOUS = {"F01", "F02", "F03", "F04", "F05", "F06", "F08", "F09", "F10", "F11", "F12", "F14", "F15", "F18", "F19",
           "F21", "F22"}

# Text cues for the owner's four blocks (tags only; the words are never changed).
ROMANCE_RE = re.compile(r"(?<![A-Za-z])(kiss\w*|in love|courting|courtship|sweetheart|flirt\w*|romance|romantic|"
                        r"crush on|fall(s|en)? for|propos(e|es|ed|al) (marriage|to)|wedding|marry|marries|married|"
                        r"lovers?|beloved)(?![A-Za-z])", re.I)
POWER_RE = re.compile(r"(?<![A-Za-z])(orders? (him|her|them|the)|forbids?|forbidden to|commands?|must obey|"
                      r"decides? for|decide who|chooses? for (him|her|them)|arranged marriage|forced to|"
                      r"against (his|her|their) will)(?![A-Za-z])", re.I)
LIGHT_RE = re.compile(r"(?<![A-Za-z])(laugh(s|ed)? it off|make light of|shrug(s|ged)? it off|just a joke|"
                      r"tease|teases|teasing|prank\w*)(?![A-Za-z])", re.I)
LESSER_RE = re.compile(r"(?<![A-Za-z])(mock\w*|ridicul\w+|make fun of|makes fun of|laugh(s|ed)? at|belittl\w+|"
                       r"inferior|lesser)(?![A-Za-z])", re.I)


# ---- Effects ---------------------------------------------------------------------------------------------------------


def encode_effect(e: dict, idx: dict[str, int]) -> Effect:
    """A normalized graph effect as a piece effect record (cie-v6-binary.md; the role byte a local slot)."""
    do = e["do"]
    code = cg.EFFECT_CODES["skill_set" if do == "skill" and "set" in e else do]
    r = cg.effect_role(e)
    slot = idx[r] if r is not None else vp.EVERY
    flags, a, b, st = 0, 0, 0, None
    if do in ("food", "tech"):
        flags, a = (1 if e["scaled"] else 0) | (2 if e["defer"] else 0), e["amount"]
        b = e.get("max") or 0
        if e.get("per_game"):
            st = cg.per_game_text(e["per_game"])
    elif do == "kill":
        st = e["cause"]
    elif do == "status":
        a = cg.STATUS_CODES[e["status"]]
    elif do in ("health", "health_change", "damage"):
        a, b = e["min"], e["max"]
        if do == "damage":
            st = cg.DAMAGE_ANY if e["structures"] == cg.DAMAGE_ANY else ",".join(e["structures"])
    elif do == "preference":
        flags = (4 if e["list"] == "dislikes" else 0) | (cg.PREF_RANDOM_FLAG if e["preference"] == cg.PREF_RANDOM
                                                         else 0) | (cg.PREF_REMOVE_FLAG if e.get("remove") else 0)
        st = None if e["preference"] == cg.PREF_RANDOM else e["preference"]
    elif do == "skill" and "set" in e:
        a, st = e["set"], ",".join(e["skills"])
    elif do == "skill":
        a, b, st = e["min"], e["max"], ",".join(e["skills"])
    elif do == "action":
        st = e["action"]
    elif do == "mood":
        a = 1 if e["mood"] == "good" else -1
    elif do == "appearance":
        a, b = (cg.LOOK_KEEP if e.get(p) is None else cg.LOOK_RANDOM if e[p] == "random" else e[p]
                for p in ("head", "body"))
    elif do in ("die_unrecovered", "birth_then_die"):
        st = e["cause"]
    elif do == "deliver_early" and "min" in e:
        a, b = e["min"], e["max"]
    elif do == "new_villager":
        a = cg.NEW_VILLAGER_AGES[e.get("age", "any")]
    elif do in ("pregnant", "nursing"):
        flags = cg.ANY_BIRTH_SEX_FLAG if e.get("any_birth_sex") else 0
        a = idx[e["partner"]] if e.get("partner") else vp.EVERY
    elif do == "body_swap":
        a = idx[e["with"]]
    elif do == "change_age":
        if "to" in e:
            flags = cg.CHANGE_AGE_TO[e["to"]]
        else:
            flags, (a, b) = cg.CHANGE_AGE_ADD, e["years"]
    elif do == "trait":
        st = e["trait"]
    return Effect(code, slot, flags, a, b, st)


def effect_roles(e: dict) -> list[str]:
    out = [r for r in (cg.effect_role(e), e.get("partner"), e.get("with")) if r]
    if e.get("do") == "new_villager" and e.get("copy_of"):
        out.append(e["copy_of"])
    return list(dict.fromkeys(out))


# ---- Slots -----------------------------------------------------------------------------------------------------------

SEX = {"any": 0, "male": 1, "female": 2, "random": 0}
SPECIAL = {None: 0, "golden_child": 1, "tribal_chief": 2}


def role_slot(name: str, r: dict, speaks: set[str], harmed: set[str], carriers: dict[str, bool]) -> Slot:
    if r["kind"] == "stranger":
        return Slot(name, 1, SEX.get(r.get("sex", "any"), 0))
    special = SPECIAL[r.get("special")]
    flags = (vp.SF_OPTIONAL if r.get("optional") else 0) | (vp.SF_BELIEVERS if r.get("believers_only", True) else 0)
    if name in speaks:
        flags |= vp.SF_SPEAKS
    if name in harmed:
        flags |= vp.SF_HARM
    min_age = r.get("min_age") or 0
    if name in carriers:
        special = special or vp.SPECIAL_CARRIER
        min_age = max(min_age, 18)
        if carriers[name]:
            flags |= vp.SF_ANY_BIRTH_SEX
    return Slot(name, 0, SEX.get(r.get("sex", "any"), 0), min_age, r.get("max_age") or 0, special, flags)


# ---- Splitting one collection event --------------------------------------------------------------------------------


class Skip(Exception):
    pass


def _game_ok(c, game: int) -> bool:
    """A condition that only names games: does it hold in `game`?  Anything else: Skip."""
    if c is None:
        return True
    (op, arg), = c.items()
    if op == "game":
        return game in arg
    if op == "not":
        return not _game_ok(arg, game)
    if op == "all":
        return all(_game_ok(x, game) for x in arg)
    if op == "any":
        return any(_game_ok(x, game) for x in arg)
    raise Skip(f"a {op} condition")


def node_text(g: dict, node: dict, game: int) -> str:
    """The node's text in `game`: a game-only variant when one holds, else the base text (Guardians of Isola's
    patch variants are left to the base text: the composed event reads as with the patch off)."""
    text = node["text"] or ""
    for v in node["variants"]:
        try:
            if _game_ok(v["if"], game):
                text = v["text"]
                break
        except Skip:
            continue
    return expand_words(g, text, game)


_BRACE = re.compile(r"\{([^{}]*)\}")


def expand_words(g: dict, text: str, game: int) -> str:
    def one(m):
        name = m.group(1)
        if name in ("@tribe", "@Tribe"):
            return m.group(0)
        if name.startswith("@") and name[1:] in g.get("words", {}):
            w = g["words"][name[1:]]
            val = w.get(str(game), w.get("*"))
            if val is None:
                raise Skip("a game word with no text in this game")
            return val
        raise Skip("a pool or an inline pick")
    return _BRACE.sub(one, text)


def _chain(g: dict, nid: str, game: int, allow_effects: bool):
    """Follow a linear chain of popups from nid: (node ids, texts, effects, last node)."""
    nodes = g["nodes"]
    ids, texts, effects = [], [], []
    seen = set()
    while True:
        if nid in seen:
            raise Skip("a loop")
        seen.add(nid)
        n = nodes[nid]
        ids.append(nid)
        if n["type"] == "question":
            return ids, texts, effects, nid
        t = node_text(g, n, game) if n["type"] != "branch" else ""
        if t:
            texts.append((t, n["join"], n["popup"]))
        if n["effects"]:
            if not allow_effects:
                raise Skip("effects before the outcome")
            effects += n["effects"]
        kids = [c for c in n["children"] if _game_ok(c.get("if"), game)]
        if n.get("else") or any(c.get("else") for c in kids):
            raise Skip("an else")
        if len(kids) != 1 or n["type"] == "branch":
            return ids, texts, effects, nid
        nid = kids[0]["next"]


def _join(texts) -> str:
    out = ""
    for t, join, popup in texts:
        if not out:
            out = t
        elif popup == "append" and join == "space":
            out += " " + t
        else:
            out += "\n\n" + t
    return out


@dataclass
class EventSplit:
    """One game's reading of an event."""
    title: str
    setup_text: str
    setup_nodes: list[str]
    approaches: list[dict]       # {"label", "text", "nodes", "outcomes": [outcome key]}
    outcomes: dict               # key -> {"text", "nodes", "effects", "auto"}

    def key(self):
        return json.dumps([self.title, self.setup_text, self.approaches,
                           {k: [v["text"], v["effects"], v["auto"]] for k, v in self.outcomes.items()}],
                          sort_keys=True)


def split_event(g: dict, game: int) -> EventSplit:
    nodes = g["nodes"]
    ids, texts, effects, last = _chain(g, g["start"], game, allow_effects=False)
    q = nodes[last]
    if q["type"] != "question":
        raise Skip("no question (random outcomes only)")
    qt = node_text(g, q, game)
    if qt:
        texts.append((qt, q["join"], q["popup"]))
    setup_text = _join(texts)
    if not setup_text:
        raise Skip("no setup text")
    approaches, outcomes = [], {}
    for c in q["choices"]:
        if not _game_ok(c.get("if"), game):
            continue
        label = expand_words(g, c["label"], game)
        t = nodes[c["next"]]
        a_ids, a_texts, a_fx, a_last = _chain(g, c["next"], game, allow_effects=True)
        end = nodes[a_last]
        if end["type"] == "question" or end["choices"]:
            raise Skip("a second question")
        kids = [k for k in end["children"] if _game_ok(k.get("if"), game)]
        if not kids:
            # the choice leads to one ending: the whole chain is its outcome, the answer has no text of its own
            key = c["next"]
            outcomes.setdefault(key, {"text": _join(a_texts), "nodes": a_ids, "effects": a_fx,
                                      "auto": any(nodes[n].get("auto_text") for n in a_ids)})
            approaches.append({"label": label, "text": None, "nodes": [], "outcomes": [key]})
            continue
        if a_fx:
            raise Skip("effects on the answer's own popup")
        outs = []
        for k in kids:
            o_ids, o_texts, o_fx, o_last = _chain(g, k["next"], game, allow_effects=True)
            if nodes[o_last]["children"] or nodes[o_last]["choices"]:
                raise Skip("an outcome that branches again")
            key = k["next"]
            outcomes.setdefault(key, {"text": _join(o_texts), "nodes": o_ids, "effects": o_fx,
                                      "auto": any(nodes[n].get("auto_text") for n in o_ids)})
            outs.append(key)
        approaches.append({"label": label, "text": _join(a_texts) or None, "nodes": a_ids, "outcomes": outs})
    approaches = [a for a in approaches if all(outcomes[k]["text"] for k in a["outcomes"])]
    if len(approaches) < 2:
        raise Skip("fewer than 2 answers")
    return EventSplit(cg.event_title(g, game), setup_text, ids, approaches, outcomes)


def _pid(text: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", text.lower())


@dataclass
class EventPieces:
    eid: str
    source: str
    section: str
    pieces: list[Piece] = field(default_factory=list)
    family_key: str = ""


STATS = collections.Counter()
SKIPS = collections.Counter()


def mask_of(games) -> int:
    return sum(1 << (x - 1) for x in games)


def filters_of(fs) -> int:
    return sum(1 << (int(f[1:]) - 1) for f in set(fs))


def notes_of(fs) -> int:
    fs = set(fs)
    return sum(1 << k for k, (_lab, need) in enumerate(ec.NOTE_LABELS.items()) if fs & set(need))


def mood_of(event_filters: set[str], villager_roles: int) -> int:
    if event_filters & SERIOUS:
        return 2
    return 1 if villager_roles >= 2 else 0


def text_roles(text: str | None, roles: dict) -> list[str]:
    if not text:
        return []
    out = []
    for _raw, p in cg.placeholders_v6(text, roles):
        if p is not None and p.role and p.role in roles:
            out.append(p.role)
    return list(dict.fromkeys(out))


def block_tags(text: str, slots: list[Slot]) -> tuple[int, int, int]:
    """(tags, never, age band) of the owner's four blocks for one piece (collection pieces: see the doc)."""
    tags = never = band = 0
    if POWER_RE.search(text):
        tags |= vp.TAG_POWER
    if LIGHT_RE.search(text):
        tags |= vp.TAG_INVALIDATING
    if LESSER_RE.search(text):
        tags |= vp.TAG_LESSER
    vill = [s for s in slots if s.kind == 0]
    minor = any(s.max_age and s.max_age < 18 for s in vill)
    if ROMANCE_RE.search(text):
        tags |= vp.TAG_ROMANCE
        teen = bool(vill) and all(s.max_age and s.max_age <= 17 and s.min_age >= 13 for s in vill)
        if teen:
            band = vp.AGE_BAND_TEEN
            tags |= vp.TAG_MINOR
            never |= vp.TAG_ADULT_ROMANCE | vp.TAG_POWER
        else:
            band = vp.AGE_BAND_ADULT
            tags |= vp.TAG_ADULT_ROMANCE
            never |= vp.TAG_MINOR | vp.TAG_POWER
    elif minor:
        tags |= vp.TAG_MINOR
        never |= vp.TAG_ROMANCE
    return tags, never, band


def event_pieces(path: Path, doc: dict, shared: dict) -> EventPieces | None:
    g, problems = cg.validate(cc.graph_for_engine(doc), scrolling=True, shared_pools=shared)
    eid = doc["collection"]["id"]
    if problems:
        SKIPS["the event does not validate"] += 1
        return None
    roles = g["roles"]
    if any(r["kind"] in ("alias", "other") for r in roles.values()):
        SKIPS["an alias role"] += 1
        return None
    if any(r.get("special") == "nursing_parent" for r in roles.values()):
        SKIPS["a nursing-parent role (no slot special for it)"] += 1
        return None
    if not any(r["kind"] in ("villager", "stranger") and not r.get("optional") for r in roles.values()):
        SKIPS["no needed villager and no stranger (the composer rejects it)"] += 1
        return None
    if g.get("relations"):
        SKIPS["a kinship relation"] += 1
        return None
    if g["requirement"].get("if") or g["requirement"].get("puzzles"):
        SKIPS["a requirement condition"] += 1
        return None
    source = doc["collection"].get("source", "")
    section = doc["collection"].get("section") or path.parent.name
    games = [x for x in g["games"] if x in GAMES]
    reads: dict[str, list[int]] = {}
    splits: dict[str, EventSplit] = {}
    try:
        for game in games:
            sp = split_event(g, game)
            k = sp.key()
            reads.setdefault(k, []).append(game)
            splits[k] = sp
    except Skip as why:
        SKIPS[str(why)] += 1
        return None
    except KeyError as why:
        SKIPS["unreadable: " + str(why)] += 1
        return None
    tags = ec.node_tags_for(source, eid, g)
    extras = ec.extras_for(source, eid, g)
    speaks = set(extras.get("speaks", []))
    every_filters = {f for t in tags.values() for f in t}
    n_vill = sum(1 for r in roles.values() if r["kind"] == "villager")
    mood = mood_of(every_filters, n_vill)
    STATS["skill requirement dropped"] += sum(1 for r in roles.values() if r.get("skill"))
    STATS["age gap dropped"] += sum(1 for r in roles.values() if r.get("max_age_gap"))
    default = cg.default_role_of(roles) if roles else None
    ev = EventPieces(eid, source, section)
    base = _pid(eid)
    vv5_only = games == [5]
    multi = len(reads) > 1
    has_teen_romance = False
    for k, gl in reads.items():
        sp = splits[k]
        gm = mask_of(gl)
        suf = f"_g{gm}" if multi else ""
        aid = {}

        def mk(kind, pid, text, label, refs, fx_list, node_ids, auto=False, extra_needed=()):
            carriers = {}
            harmed = set()
            for e in fx_list:
                if e["do"] in ("pregnant", "nursing"):
                    carriers[e["role"]] = bool(e.get("any_birth_sex"))
                if cg._harmful(e, gl):
                    harmed.add(cg.effect_role(e))
            refs = list(dict.fromkeys(list(extra_needed) + refs + [r for e in fx_list for r in effect_roles(e)]))
            refs = [r for r in refs if r in roles]
            slots = [role_slot(r, roles[r], speaks, harmed, carriers) for r in refs]
            idx = {r: i for i, r in enumerate(refs)}
            fx = [encode_effect(e, idx) for e in fx_list]
            fs = {f for n in node_ids for f in tags.get(n, ())}
            t, nw, band = block_tags(" ".join(x for x in (text, label) if x), slots)
            flags = (vp.PF_DEADLY if any(e.code in vp.DEADLY_CODES for e in fx) else 0) \
                | (vp.PF_BELIEVERS if vv5_only else 0) | (vp.PF_AUTO_LINES if auto and fx else 0)
            return Piece(pid, kind, mood, flags, gm, 0, 0, filters_of(fs), notes_of(fs), nw, t, text, label, slots,
                         1, fx, band, [], src=f"{path.relative_to(ROOT).as_posix()}")

        def refs_of(*texts):
            out = []
            for t in texts:
                out += text_roles(t, roles)
            if default and any(p is not None and p.role == default and "." not in raw
                               for t in texts if t for raw, p in cg.placeholders_v6(t, roles)):
                out.append(default)
            return out

        need = [r for r, v in roles.items() if not v.get("optional")]
        setup = mk(vp.KIND_SETUP, f"{base}{suf}_s", sp.setup_text, vp.title_case(sp.title),
                   refs_of(sp.setup_text), [], sp.setup_nodes, extra_needed=need)
        ev.pieces.append(setup)
        for i, a in enumerate(sp.approaches):
            pid = f"{base}{suf}_a{i}"
            aid[i] = pid
            ev.pieces.append(mk(vp.KIND_APPROACH, pid, a["text"], vp.title_case(a["label"]),
                                refs_of(a["text"], a["label"]), [], a["nodes"]))
        for key, o in sp.outcomes.items():
            links = [Link(aid[i], 1) for i, a in enumerate(sp.approaches) if key in a["outcomes"]]
            if not links:
                continue
            p = mk(vp.KIND_OUTCOME, f"{base}{suf}_o_{_pid(key)}", o["text"], None, refs_of(o["text"]),
                   o["effects"], o["nodes"], auto=o["auto"])
            p.links = links
            ev.pieces.append(p)
        has_teen_romance |= any(p.age_band == vp.AGE_BAND_TEEN for p in ev.pieces)
    if has_teen_romance:
        # the owner's own teen-teen romance: its minor-centred pieces keep away from adult romance only
        for p in ev.pieces:
            if p.tags & vp.TAG_MINOR and not p.tags & vp.TAG_ROMANCE:
                p.never = (p.never & ~vp.TAG_ROMANCE) | vp.TAG_ADULT_ROMANCE
    for p in ev.pieces:
        if not all(ord(c) < 128 for c in (p.text or "") + (p.label or "")):
            SKIPS["a character outside ASCII"] += 1
            return None
    return ev


# ---- The Living bank: Living Engine (LE) and MC ---------------------------------------------------------------------

ADULT = lm.ADULT_AGE if hasattr(lm, "ADULT_AGE") else 18
GROUP_LINK = {"good": 20, "mixed": 10, "bad": 10, "rare": 2}


def _normalize_effects(effects: list[dict], roles: dict, games: list[int]) -> list[dict]:
    if not effects:
        return []
    g = {"format": "vvfp-cie-graph", "version": 6, "title": "Effects", "games": games, "roles": roles,
         "start": "o", "nodes": {"o": {"text": "x", "effects": effects}}}
    n, problems = cg.validate(g, scrolling=True)
    if problems:
        raise ValueError("; ".join(problems[:3]))
    return n["nodes"]["o"]["effects"]


def le_text(text: str) -> str:
    return lm.plain(text)


def le_split_words(text: str, words: dict, games: list[int]) -> list[tuple[str, list[int]]]:
    """A Living text with {@w} game words: one text per set of games that read it the same."""
    out: dict[str, list[int]] = {}
    for game in games:
        t = text
        for name, vals in words.items():
            t = t.replace("{@" + name + "}", vals.get(str(game), vals.get("*")))
        out.setdefault(t, []).append(game)
    return list(out.items())


def slot_from_spec(name: str, spec: dict) -> Slot:
    if spec["kind"] == "stranger":
        return Slot(name, 1, 0)
    return Slot(name, 0, SEX.get(spec.get("sex", "any"), 0), spec.get("min_age") or 0, spec.get("max_age") or 0,
                SPECIAL[spec.get("special")], vp.SF_BELIEVERS)


def le_bounds(bank, seed: dict, which: str) -> Slot:
    """The loosest villager slot every role the seed allows in that place fits (min of mins, max of maxes)."""
    roles = [r for r in bank.roles if not lm.is_stranger(bank, r["id"])]
    ok = []
    for r in roles:
        for o in roles:
            a, b = (r["id"], o["id"]) if which == "first" else (o["id"], r["id"])
            if lm.possible_pair(bank, seed, a, b):
                ok.append(r)
                break
    mins = [r["cast"].get("min_age", 0) or 0 for r in ok]
    maxs = [r["cast"].get("max_age") or 0 for r in ok]
    min_age = min(mins) if mins else 14
    max_age = 0 if (not maxs or 0 in maxs) else max(maxs)
    if lm.adult_seed(seed):
        min_age = max(min_age, ADULT)
    specials = {r["cast"].get("special") for r in ok}
    special = SPECIAL.get(next(iter(specials))) if len(specials) == 1 else 0
    return Slot(which, 0, 0, min_age, max_age, special or 0, vp.SF_BELIEVERS)


def le_file(bank, cat: dict, never_pairs) -> tuple[list[Piece], list[tuple[str, str, str]]]:
    """One Living Engine category: its seeds (setups), the bank's approaches and the category's choice set
    (approaches, family 1), the archetypes (outcomes), the role-pair frames.  Returns the pieces and the forbidden
    pairs the mixer's own rules give (the bits come later)."""
    seeds = [s for s in bank.seeds if s["category"] == cat["id"]]
    games_all = sorted({x for s in seeds for x in s["games"]})
    pieces: list[Piece] = []
    forbid: list[tuple[str, str, str]] = []
    mood = lm.MOODS.index(cat["mood"])
    code = cat["code"].lower()
    A0, B0 = "le_role_adult_villager", "le_role_friend"
    setups: dict[str, list[Piece]] = {}
    for s in seeds:
        text, words = lm.seed_text(bank, s)
        for i, (t, gl) in enumerate(le_split_words(text, words, s["games"])):
            pid = f"le_{s['id'][3:]}" + (f"_g{mask_of(gl)}" if len(words) else "")
            fs = ec._text_filters(t)
            p = Piece(pid, vp.KIND_SETUP, mood, 0, mask_of(gl), 1, 1, filters_of(fs), notes_of(fs), 0, 0, t,
                      vp.title_case(cat["title"]), [le_bounds(bank, s, "first"), le_bounds(bank, s, "second")],
                      src=f"bank {s['code']}")
            setups.setdefault(s["id"], []).append(p)
            pieces.append(p)
    # approaches: the bank's 34 and the category's choice set
    apps: dict[str, list[Piece]] = {}
    cs = bank.choice_sets[cat["choice_set"]]
    idents = [("approach", a["id"]) for a in bank.approaches] + [("choice", c) for c in cs["choices"]]
    for kind, ident in idents:
        label, words = lm.label_text(bank, kind, ident)
        for t, gl in le_split_words(label, words, games_all):
            pid = f"le_{code}_{ident[3:]}" + (f"_g{mask_of(gl)}" if words else "")
            slots = []
            if ident in lm.SECRET_CHOICES:
                slots = [Slot("first", 0, 0, ADULT, 0, 0, vp.SF_BELIEVERS),
                         Slot("second", 0, 0, ADULT, 0, 0, vp.SF_BELIEVERS)]
            cls = lm.choice_classes(bank, kind, ident)
            tags = (vp.TAG_INVALIDATING | vp.TAG_LESSER) if "mocking" in cls else 0
            if ident == "le_app_act_01":
                tags |= vp.TAG_POWER                 # the chief decides
            p = Piece(pid, vp.KIND_APPROACH, mood, 0, mask_of(gl), 1, 1, 0, 0, 0, tags, None, vp.title_case(t),
                      slots, src=f"bank {ident}")
            apps.setdefault(ident, []).append(p)
            pieces.append(p)
    # outcomes: the archetypes
    arcs: dict[str, Piece] = {}
    vulnerable_excl = set()
    for rr in bank.raw["compat"]["role_rules"]:
        if "vulnerable" in rr["roles_with_any"]:
            vulnerable_excl |= set(rr["exclude"].get("archetypes", []))
    for arc in bank.archetypes:
        aid = arc["id"]
        roles_json = {"first": {"kind": "villager", "min_age": 14}, "second": {"kind": "villager", "min_age": 14}}
        fx = lm.archetype_effects(bank, aid, A0, B0, games_all)
        for e in fx:
            if e.get("role") == "elder" or e.get("role") is None and "role" in e:
                e["role"] = "first"
        allow = {}
        for e in fx:
            if lm.harmful(e) and e.get("role") in ("first", "second") and (
                    arc["protection"] == "allow" or e["do"] in ("kill", "vanish", "die_unrecovered")):
                allow[e["role"]] = True
        for r in allow:
            roles_json[r]["protected"] = "allow"
        norm = _normalize_effects(fx, roles_json, games_all)
        refs = list(dict.fromkeys(r for e in norm for r in effect_roles(e)))
        slots = []
        for r in ("first", "second"):
            if r not in refs and aid not in vulnerable_excl:
                continue
            mn, mx = 0, 0
            if aid in vulnerable_excl:
                mn, mx = ADULT, 54                    # R1: never a child, a teenager or an elder
            if any(e["do"] == "health_change" and e.get("min", 0) < 0 and e.get("role") == r for e in norm):
                mn = max(mn, ADULT)                   # S8: no injury on a minor
            if "needs_elder" in arc["tags"] and r == "first":
                mn, mx = max(mn, 55), 0
            harm = any(cg._harmful(e, games_all) and e.get("role") == r for e in norm)
            slots.append(Slot(r, 0, 0, mn, mx, 0, vp.SF_BELIEVERS | (vp.SF_HARM if harm else 0)))
        idx = {sl.name: i for i, sl in enumerate(slots)}
        for e in norm:
            for r in effect_roles(e):
                if r not in idx:
                    idx[r] = len(slots)
                    slots.append(Slot(r, 0, 0, 14, 0, 0, vp.SF_BELIEVERS))
        effects = [encode_effect(e, idx) for e in norm]
        fs = set(lm.ARCHETYPE_FILTERS.get(aid, [])) | {f for e in norm for f in ec.EFFECT_FILTERS.get(e["do"], ())} \
            | ec._text_filters(arc["text"])
        tags = vp.TAG_INVALIDATING if "light" in arc["tags"] else 0
        flags = (vp.PF_DEADLY if any(e.code in vp.DEADLY_CODES for e in effects) else 0) \
            | (vp.PF_AUTO_LINES if effects else 0)
        links = []
        n_group = sum(1 for x in bank.archetypes if x["group"] == arc["group"])
        w = max(1, min(1000, round(GROUP_LINK[arc["group"]] * 50 / n_group)))
        for kind, ident in idents:
            if lm.arc_ok_after(bank, kind, ident, aid):
                for ap in apps[ident]:
                    links.append(Link(ap.id, w))
        p = Piece(f"le_{code}_{aid[7:]}", vp.KIND_OUTCOME, mood, flags, mask_of(games_all), 1, 0, filters_of(fs),
                  notes_of(fs), 0, tags, lm.plain(arc["text"]), None, slots, 1, effects, 0, links,
                  src=f"bank {aid}")
        arcs[aid] = p
        pieces.append(p)
    # frames: the role pairs the living mixer casts for these seeds (its variants), and the MIX personalities
    variants = [v for v in VARIANTS if v.bank == 0 and v.seed in {s["id"] for s in seeds}]
    frames: dict[tuple, Piece] = {}
    for v in variants:
        if "roles" not in v.plan:
            continue
        a, b = v.plan["roles"]
        pa, pb = v.plan["personalities"] if v.flags & 1 else (None, None)
        pa = None if pa == "pool" else pa
        pb = None if pb == "pool" else pb
        key = (a, pa, b, pb)
        if key in frames or lm.is_stranger(bank, a) or lm.is_stranger(bank, b):
            continue
        text = f"(first), {lm.frame_part(bank, a, pa, None)}, and (second), {lm.frame_part(bank, b, pb, None)}, " \
               f"{lm.FRAME_TAIL}"
        gl = sorted(lm.role_games(bank, a) & lm.role_games(bank, b) & set(games_all))
        if not gl or "{" in text:
            continue
        sa = slot_from_spec("first", lm.role_spec(bank, a, False))
        sb = slot_from_spec("second", lm.role_spec(bank, b, False))
        tags = vp.TAG_MINOR if (lm.minor_role(bank, a) or lm.minor_role(bank, b)) else 0
        n = len(frames)
        p = Piece(f"le_{code}_f{n:03d}", vp.KIND_FRAME, mood, 0, mask_of(gl), 1, 0, 0, 0,
                  vp.TAG_ROMANCE if tags else 0, tags, lm.plain(text), None, [sa, sb], src=f"living frame {a} {b}")
        p._roles = (a, pa, b, pb)   # type: ignore[attr-defined]
        frames[key] = p
        pieces.append(p)
    # the mixer's rules as forbidden pairs
    for s in seeds:
        allowed_choices = {c for _k, c in lm.choice_set_choices(bank, s)}
        for sp in setups[s["id"]]:
            for kind, ident in idents:
                ok = lm.approach_allowed(bank, s, ident, A0, B0) if kind == "approach" else ident in allowed_choices
                if not ok:
                    for ap in apps[ident]:
                        forbid.append((sp.id, ap.id, f"living rule: {s['code']} x {ident}"))
            for aid, op in arcs.items():
                if not bank.seed_allows(s["id"], "archetype", aid) or lm.seed_arc_rule(bank, s, aid):
                    forbid.append((sp.id, op.id, f"living rule: {s['code']} x {aid}"))
            for (a, pa, b, pb), fp in frames.items():
                ok = lm.possible_pair(bank, s, a, b) and all(
                    p is None or lm.personality_ok(bank, s, r, p, False) for r, p in ((a, pa), (b, pb)))
                if not ok:
                    forbid.append((sp.id, fp.id, f"living rule: {s['code']} x frame {a}/{b}"))
    for (a, pa, b, pb), fp in frames.items():
        for aid, op in arcs.items():
            ok = bank.role_allows_archetype(a, aid) and bank.role_allows_archetype(b, aid) and lm.cast_ok(bank, aid, a, b)
            if ok and "needs_elder" in bank.arc[aid]["tags"]:
                ok = lm.resolve_role(bank, "elder", a, b) is not None
            if ok and (pa or pb):
                sens = lm.sensitive_slots(bank, [aid], a, b, games_all)
                ok = not (("first" in sens and pa and lm.risky(bank, pa)) or ("second" in sens and pb and lm.risky(bank, pb)))
            if not ok:
                forbid.append((fp.id, op.id, f"living rule: frame {a}/{b} x {aid}"))
        for kind, ident in idents:
            if ident in lm.SECRET_CHOICES and (lm.minor_role(bank, a) or lm.minor_role(bank, b)):
                for ap in apps[ident]:
                    forbid.append((fp.id, ap.id, f"living rule S7: frame {a}/{b} x {ident}"))
    return pieces, forbid


def mc_events(bank) -> dict[str, list[tuple[str, dict]]]:
    """Each MC situation as the living mixer composes it (its four approaches, two outcomes each), by category."""
    out: dict[str, list] = {}
    for sit in bank.mc_sits:
        if sit.get("outcomes_status") != "active":
            continue
        graph, _outs = lm.compose_mc(bank, sit, (0, 1, 2, 3))
        cat = bank.mc_cat[sit["category"]]
        doc = dict(graph)
        doc["collection"] = {"id": f"living_{sit['id']}", "source": "living", "lines": [1, 1], "section": "mc",
                             "credit": "x", "draw_weight": 1, "series": None}
        out.setdefault(cat["code"].lower(), []).append((sit["id"], doc, cat))
    return out


# ---- Bits: forbidden pairs as NEVER WITH / TAGS ------------------------------------------------------------------


def assign_bits(pieces: list[Piece], forbid: list[tuple[str, str, str]], free=vp.FREE_BITS) -> int:
    """Encode the forbidden pairs with the free bits: each bit gives TAGS to a class of pieces with the same forbidden
    partners and NEVER WITH to those partners (greedy cover; never forbids an allowed pair).  Returns bits used;
    ValueError when the file needs more bits than it has."""
    by = {p.id: p for p in pieces}
    part: dict[str, set[str]] = collections.defaultdict(set)
    for a, b, _why in forbid:
        if a in by and b in by and a != b and vp.compatible(by[a], by[b]):
            part[a].add(b)
            part[b].add(a)
    left = {frozenset((a, b)) for a, s in part.items() for b in s}
    classes: dict[frozenset, list[str]] = collections.defaultdict(list)
    for pid, s in part.items():
        classes[frozenset(s)].append(pid)
    used = 0
    free = list(free)
    while left:
        best, gain = None, 0
        for partners, members in classes.items():
            g = sum(1 for m in members for x in partners if frozenset((m, x)) in left)
            if g > gain:
                best, gain = (partners, members), g
        if not free:
            raise ValueError(f"needs more than {len(vp.FREE_BITS)} pair bits")
        bit = 1 << free.pop(0)
        partners, members = best
        for m in members:
            by[m].tags |= bit
        for x in partners:
            by[x].never |= bit
        for m in members:
            for x in partners:
                left.discard(frozenset((m, x)))
        used += 1
        del classes[partners]
    return used


# ---- Building the files --------------------------------------------------------------------------------------------

VARIANTS: list = []


def load_never() -> list[dict]:
    if NEVER_FILE.is_file():
        return json.loads(NEVER_FILE.read_text(encoding="utf-8"))["pairs"]
    return []


def file_bytes(pieces: list[Piece]) -> int:
    return len(vp.write_pcb(pieces))


def build(write: bool = True) -> dict[str, list[Piece]]:
    """Every group's pieces, bits assigned; written to assets/event_collection/pieces when `write`."""
    never = load_never()
    if not _SPLIT:
        _SPLIT.append(_split_all(never))
    groups = copy.deepcopy(_SPLIT[0])
    return _assemble(groups, never, write)


_SPLIT: list = []


def _split_all(never) -> dict:
    """The pieces of every group before any pair bit (the slow part; cached between validation rounds)."""
    global VARIANTS
    STATS.clear()
    SKIPS.clear()
    shared = {"pools": cc.shared_pools()}
    bank = lm.Bank()
    VARIANTS = lm.generate(bank)
    groups: dict[str, list[tuple[list[Piece], list]]] = collections.OrderedDict()
    # collection events, by source and section
    for path in sorted(COLLECTION.rglob("*.json")):
        if path.parent == COLLECTION or "content_tags" in path.parts:
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("format") != "vvfp-cie-graph":
            continue
        STATS["collection events"] += 1
        ev = event_pieces(path, doc, shared)
        if ev is None:
            continue
        STATS["collection events split"] += 1
        rel = path.relative_to(COLLECTION).parts
        grp = _pid("_".join(rel[:-1]))[:20] or "misc"
        groups.setdefault(grp, []).append((ev.pieces, []))
    # MC situations
    for code, items in mc_events(bank).items():
        for sid, doc, cat in items:
            g, problems = cg.validate(doc, scrolling=True)
            if problems:
                SKIPS["MC: does not validate"] += 1
                continue
            try:
                ev = _graph_pieces(sid, g, lm.MOODS.index(cat["mood"]), lm.MC_CATEGORY_FILTERS[cat["code"]])
            except Skip as why:
                SKIPS["MC: " + str(why)] += 1
                continue
            groups.setdefault(f"mc_{code}", []).append((ev, []))
    # Living Engine categories
    for cat in bank.categories:
        ps, forbid = le_file(bank, cat, never)
        groups[f"le_{cat['code'].lower()}"] = [(ps, forbid)]
    return groups


def _worst(text: str) -> str:
    return re.sub(r"\([^()]*\)", "W" * 12, text)


def fit_games(pieces: list[Piece]) -> None:
    """Title case can widen a label or a title past what a game shows: that game is left out of the piece (the
    event's static form still runs there)."""
    for p in pieces:
        for game in GAMES:
            bit = 1 << (game - 1)
            if not p.games & bit:
                continue
            if p.kind == vp.KIND_APPROACH and p.label and not cg.label_fits(game, _worst(p.label)):
                p.games &= ~bit
                STATS["approach left out of a game: its title-case label is too wide"] += 1
            elif p.kind == vp.KIND_SETUP and p.label and not cg.title_fits(game, p.label):
                p.games &= ~bit
                STATS["setup left out of a game: its title-case title is too wide"] += 1


def _assemble(groups: dict, never: list, write: bool) -> dict[str, list[Piece]]:
    # parts below the file budget; family numbers per file
    files: dict[str, list[Piece]] = {}
    for grp, events in groups.items():
        parts: list[list[tuple[list[Piece], list]]] = [[]]
        size = 0
        for ev in events:
            est = sum(64 + 16 * (len(p.slots) + len(p.effects)) + 8 * len(p.links) + len(p.text or "")
                      + len(p.label or "") + len(p.id) + 4 for p in ev[0])
            if parts[-1] and size + est > FILE_BUDGET:
                parts.append([])
                size = 0
            parts[-1].append(ev)
            size += est
        for k, part in enumerate(parts):
            name = grp if len(parts) == 1 else f"{grp[:21]}_{k + 1}"
            pieces: list[Piece] = []
            forbid: list = []
            sections: list[str] = []
            for fam, (ps, fb) in enumerate(part, 1):
                for p in ps:
                    if not name.startswith("le_"):
                        if p.kind in (vp.KIND_SETUP, vp.KIND_APPROACH):
                            p.family = fam
                        sec = p.src.split("/")[-2] if "/" in p.src else name
                        if sec not in sections:
                            sections.append(sec)
                        p.topic = 1 << min(31, sections.index(sec))
                pieces += ps
                forbid += fb
            # pairs the validator found (by piece id), and merge conflicts the slots already show
            ids = {p.id for p in pieces}
            forbid += [(x["a"], x["b"], x["why"]) for x in never if x["a"] in ids and x["b"] in ids]
            forbid += merge_conflicts(pieces)
            if name.startswith("le_"):          # elsewhere pieces only meet their own event's
                forbid += block_pairs(pieces)
            fit_games(pieces)
            assign_bits(pieces, forbid)
            files[name] = pieces
    BUILT.clear()
    BUILT.update(files)
    if write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        for old in OUT_DIR.glob("pieces-*.pcb"):
            if old.stem[7:] not in files:
                old.unlink()
        for name, pieces in files.items():
            data = vp.write_pcb(pieces)
            if len(data) > vp.FILE_MAX:
                raise ValueError(f"{name}: {len(data)} bytes")
            vp.read_pcb(data, name)
            (OUT_DIR / f"pieces-{name}.pcb").write_bytes(data)
    return files


def _graph_pieces(eid: str, g: dict, mood: int, cat_filters: list[str]) -> list[Piece]:
    """An MC situation's graph as pieces (the collection splitter, one game reading)."""
    roles = g["roles"]
    sp = split_event(g, g["games"][0])
    pieces = []
    gm = mask_of(g["games"])
    tags = ec.tag_graph(g)
    base = _pid(eid)

    def slots_for(refs, fx):
        harmed = {cg.effect_role(e) for e in fx if cg._harmful(e, g["games"])}
        refs = [r for r in dict.fromkeys(refs + [r for e in fx for r in effect_roles(e)]) if r in roles]
        return refs, [role_slot(r, roles[r], set(), harmed, {}) for r in refs]
    refs, slots = slots_for(list(roles), [])
    fs = set(cat_filters) | {f for n in sp.setup_nodes for f in tags.get(n, ())}
    pieces.append(Piece(f"{base}_s", vp.KIND_SETUP, mood, 0, gm, 1, 0, filters_of(fs), notes_of(fs), 0, 0,
                        sp.setup_text, vp.title_case(sp.title), slots, src=f"bank {eid}"))
    for i, a in enumerate(sp.approaches):
        pieces.append(Piece(f"{base}_a{i}", vp.KIND_APPROACH, mood, 0, gm, 1, 0, 0, 0, 0, 0, a["text"],
                            vp.title_case(a["label"]), [], src=f"bank {eid}"))
    for key, o in sp.outcomes.items():
        refs, slots = slots_for(text_roles(o["text"], roles), o["effects"])
        idx = {r: i for i, r in enumerate(refs)}
        fx = [encode_effect(e, idx) for e in o["effects"]]
        fs = set(cat_filters) | {f for n in o["nodes"] for f in tags.get(n, ())}
        links = [Link(f"{base}_a{i}", 1) for i, a in enumerate(sp.approaches) if key in a["outcomes"]]
        flags = (vp.PF_DEADLY if any(e.code in vp.DEADLY_CODES for e in fx) else 0) | (vp.PF_AUTO_LINES if fx else 0)
        pieces.append(Piece(f"{base}_o_{_pid(key)}", vp.KIND_OUTCOME, mood, flags, gm, 1, 0, filters_of(fs),
                            notes_of(fs), 0, 0, o["text"], None, slots, 1, fx, 0, links, src=f"bank {eid}"))
    return pieces


GRIEF = filters_of(("F01", "F03", "F05", "F06", "F11", "F12"))
SCORN = filters_of(("F16", "F17"))


def block_pairs(pieces: list[Piece]) -> list[tuple[str, str, str]]:
    """The owner's blocks 1-3 as pairs, between pieces of different sources (two pieces of one owner event are the
    owner's own combination): power with romance, a light piece with grief, injury or distress, a mocking piece with
    bullying or prejudice."""
    out = []
    marked = [p for p in pieces if p.tags & (vp.TAG_POWER | vp.TAG_INVALIDATING | vp.TAG_LESSER)]
    for p in marked:
        for q in pieces:
            if q is p or q.src == p.src or not (p.games & q.games):
                continue
            if p.tags & vp.TAG_POWER and q.tags & vp.TAG_ROMANCE:
                out.append((p.id, q.id, "power dynamics with romance"))
            if p.tags & vp.TAG_INVALIDATING and q.filters & GRIEF:
                out.append((p.id, q.id, "invalidating pain"))
            if p.tags & vp.TAG_LESSER and q.filters & SCORN:
                out.append((p.id, q.id, "portraying someone as lesser"))
    return out


def merge_conflicts(pieces: list[Piece]) -> list[tuple[str, str, str]]:
    """Pairs that can meet in one composition and whose slots cannot merge (2.4): forbidden up front, so the composer
    never wastes a try on them."""
    out = []
    setups = [p for p in pieces if p.kind == vp.KIND_SETUP]
    apps = [p for p in pieces if p.kind == vp.KIND_APPROACH]
    outs = [p for p in pieces if p.kind == vp.KIND_OUTCOME]
    extra = [p for p in pieces if p.kind in (vp.KIND_FLAVOUR, vp.KIND_FRAME)]
    by_fam = collections.defaultdict(list)
    for a in apps:
        by_fam[a.family].append(a)
    linked = collections.defaultdict(list)
    for o in outs:
        for lk in o.links:
            linked[lk.approach].append(o)

    def clash(x, y):
        if not (x.games & y.games) or not vp.compatible(x, y):
            return False
        roles, _why = vp.merge_slots([(x, False), (y, False)])
        return roles is None
    for s in setups:
        for a in by_fam[s.family]:
            if clash(s, a):
                out.append((s.id, a.id, "slots cannot merge"))
            for o in linked[a.id]:
                if clash(s, o):
                    out.append((s.id, o.id, "slots cannot merge"))
        for f in extra:
            if clash(s, f):
                out.append((s.id, f.id, "slots cannot merge"))
    for a in apps:
        for o in linked[a.id]:
            if clash(a, o):
                out.append((a.id, o.id, "slots cannot merge"))
        for f in extra:
            if clash(a, f):
                out.append((a.id, f.id, "slots cannot merge"))
    for o in outs:
        for f in extra:
            if clash(o, f):
                out.append((o.id, f.id, "slots cannot merge"))
    return out


# ---- A model village (the validator's stand-in for the engine's casting) -----------------------------------------


@dataclass
class Villager:
    name: str
    sex: int            # 1 male, 2 female
    age: int
    born_female: bool
    golden: bool = False
    chief: bool = False
    heathen: bool = False
    busy_carrier: bool = False      # pregnant or nursing


NAMES_M = ["Ako", "Bane", "Cato", "Duro", "Eko", "Faro", "Galo", "Hemi", "Iro", "Joko", "Kai", "Lono", "Manu",
           "Niko", "Oro", "Pele", "Rangi", "Sefo", "Tane", "Vai"]
NAMES_F = ["Ana", "Bela", "Cora", "Dani", "Ema", "Fia", "Gina", "Hina", "Ila", "Jona", "Kala", "Lani", "Mele",
           "Nala", "Ofa", "Pua", "Rua", "Sina", "Tia", "Vea"]


def village(game: int, seed: int = 1) -> list[Villager]:
    ages = [2, 4, 6, 8, 10, 12, 13, 14, 15, 16, 17, 18, 19, 21, 24, 27, 30, 33, 36, 40, 44, 48, 52, 56, 60, 64, 68, 72,
            76, 80]
    out = []
    for i, age in enumerate(ages * 2):
        sex = 1 + (i + seed) % 2
        name = (NAMES_M if sex == 1 else NAMES_F)[i % 20] + ("" if i < 20 else str(i // 20 + 1))
        out.append(Villager(name, sex, age, sex == 2))
    out[3].busy_carrier = False
    out[20].busy_carrier = True
    if game == 1:
        out.append(Villager("Lumo", 1, 5, False, golden=True))
    if game == 3:
        out.append(Villager("Tama", 1, 50, False, chief=True))
    if game == 5:
        for v in out[::7]:
            v.heathen = True
    return out


def make_cast(game: int, rb, people: list[Villager]):
    def cast(roles: list) -> dict | None:
        used: set[str] = set()
        bound = {}
        for m in roles:
            if m.kind == 1:
                bound[m.name] = "a stranger"
                continue
            elig = []
            for v in people:
                if v.name in used:
                    continue
                if m.min_age and v.age < m.min_age or m.max_age and v.age > m.max_age:
                    continue
                if m.sex and v.sex != m.sex:
                    continue
                if m.special == 1 and not v.golden or m.special == 2 and not v.chief:
                    continue
                if m.special == 0 and (v.golden or v.chief) and m.flags & vp.SF_HARM:
                    continue
                if m.special == 3 and (v.age < 18 or v.busy_carrier or not (v.born_female or m.flags & vp.SF_ANY_BIRTH_SEX)):
                    continue
                if game == 5 and v.heathen and not m.flags & vp.SF_CONVERSION:
                    continue
                if m.flags & vp.SF_HARM and v.busy_carrier:
                    continue
                elig.append(v)
            if not elig:
                if m.optional:
                    continue
                return None
            v = elig[rb(len(elig))]
            used.add(v.name)
            bound[m.name] = v
        return bound
    return cast


# ---- Validation ----------------------------------------------------------------------------------------------------


def graph_problems(comp, game: int) -> list[str]:
    g = vp.graph_of(comp, game, notes=True)
    try:
        _n, problems = cg.validate(g, scrolling=True)
    except Exception as ex:      # a crash is a problem
        return [f"validate raised {type(ex).__name__}: {ex}"]
    return problems


def block_problems(comp) -> list[tuple[str, str, str]]:
    """The owner's four blocks and the sense checks, on one composition: [(piece a, piece b, why)]."""
    out = []
    ps = comp.pieces()
    roles = comp.roles
    # 4. minor-adult romance: a romance piece whose romance roles are not all one band
    for p in ps:
        if not p.tags & vp.TAG_ROMANCE:
            continue
        vill = [roles[sl.name] for sl in p.slots if sl.kind == 0]
        adult = [m for m in vill if m.min_age >= 18]
        young = [m for m in vill if m.max_age and m.max_age < 18]
        if adult and young:
            out.append((p.id, p.id, "minor-adult romance"))
    # the pairs the player can meet on one path: the start (setup, flavour, frame), one answer and one outcome
    # (outcomes of different answers are never shown together)
    start = [comp.setup] + [x for x in (comp.flavour, comp.frame) if x is not None]
    pairs = {}
    for a, os in zip(comp.approaches, comp.outcomes):
        for o in os:
            path = start + [a, o]
            for p in path:
                for q in path:
                    if p is not q:
                        pairs[(p.id, q.id)] = (p, q)
    for p, q in pairs.values():
        if p.tags & vp.TAG_ROMANCE and q.tags & vp.TAG_MINOR and p.age_band == vp.AGE_BAND_ADULT:
            out.append((p.id, q.id, "adult romance with a minor-centred piece"))
    # 1-3. power with romance; light words with grief, injury or distress; mocking with bullying or prejudice
    # (two pieces of one owner event are the owner's own combination: never a mixer block)
    for p, q in pairs.values():
        if p.src == q.src:
            continue
        if p.tags & vp.TAG_POWER and q.tags & vp.TAG_ROMANCE:
            out.append((p.id, q.id, "power dynamics with romance"))
        if p.tags & vp.TAG_INVALIDATING and q.filters & filters_of(("F01", "F03", "F05", "F06", "F11", "F12")):
            out.append((p.id, q.id, "invalidating pain"))
        if p.tags & vp.TAG_LESSER and q.filters & filters_of(("F16", "F17")):
            out.append((p.id, q.id, "portraying someone as lesser"))
    # sense: an outcome answers its approach; effects fit the cast roles
    for a, os in zip(comp.approaches, comp.outcomes):
        for o in os:
            if not any(lk.approach == a.id for lk in o.links):
                out.append((a.id, o.id, "the outcome does not answer this approach"))
            for e in o.effects:
                if e.slot == vp.EVERY:
                    continue
                m = roles[o.slots[e.slot].name]
                if e.code in (28, 29) and m.special != vp.SPECIAL_CARRIER:
                    out.append((o.id, o.id, "a pregnancy on a role that is not a carrier"))
                if e.code in (4, 5, 6, 7, 8, 9, 10, 14, 17, 18, 21, 22) and m.kind == 1:
                    out.append((o.id, o.id, "a villager effect on a stranger"))
    # title case
    if not vp.title_case_ok(comp.setup.label or ""):
        out.append((comp.setup.id, comp.setup.id, "title not in title case"))
    for a in comp.approaches:
        if not vp.title_case_ok(a.label or ""):
            out.append((a.id, a.id, "label not in title case"))
    return out


def draw_file(files, game, rb):
    """Spec 4: a file by the count of its usable setups."""
    st = vp.Settings(game)
    names = [n for n in files if any(p.kind == vp.KIND_SETUP and vp.usable(p, st) for p in files[n].pieces)]
    w = [sum(1 for p in files[n].pieces if p.kind == vp.KIND_SETUP and vp.usable(p, st)) for n in names]
    return vp.weighted(names, w, rb)


def validate(per_game: int = 2000, rounds: int = 8, quick: int = 300) -> dict:
    """Quick rounds (`quick` a game) until one is clean, then the full round (`per_game` a game); a full round that
    finds pairs goes back to quick rounds."""
    report = {}
    size = quick
    examples: dict[str, str] = {}
    for rnd in range(1, rounds + 1):
        files = {n: vp.read_pcb(vp.write_pcb(ps), n) for n, ps in build(write=True).items()}
        for n, pf in files.items():          # authoring sources for the checks (not in the file)
            src = {p.id: p.src for p in BUILT[n]} if n in BUILT else {}
            for p in pf.pieces:
                p.src = src.get(p.id, "")
        bad: dict[tuple[str, str], str] = {}
        stats = collections.Counter()
        reasons = collections.Counter()
        for game in GAMES:
            rb = vp.Lcg(1000 + game * 7919 + rnd)
            people = village(game)
            for _i in range(size):
                if _i and _i % 500 == 0:
                    print(f"  round {rnd} vv{game}: {_i}/{size}", flush=True)
                name = draw_file(files, game, rb)
                pf = files[name]
                st = vp.Settings(game, gate=False, notes=True)
                comp = vp.compose(pf, st, rb, cast=make_cast(game, rb, people))
                stats[f"vv{game} drawn"] += 1
                if comp is None:
                    stats[f"vv{game} no composition"] += 1
                    continue
                for _sid, why in comp.rejected:
                    reasons[why.split(":")[0]] += 1
                stats[f"vv{game} composed"] += 1
                probs = graph_problems(comp, game)
                if probs:
                    stats[f"vv{game} graph problems"] += 1
                    for pr in probs[:2]:
                        reasons["graph: " + pr[:80]] += 1
                        examples.setdefault(pr[:80], f"{name} {comp.setup.id} " + " ".join(
                            p.id for p in comp.pieces()))
                    for a, b in attribute(comp, game):
                        bad[(a, b)] = "graph: " + probs[0][:120]
                for a, b, why in block_problems(comp):
                    stats[f"vv{game} block or sense problems"] += 1
                    bad[(a, b)] = why
        report = {"round": rnd, "per_game": size, "graph_examples": examples, "stats": dict(stats), "rejections": dict(reasons.most_common(30)),
                  "new_pairs": [{"a": a, "b": b, "why": w} for (a, b), w in sorted(bad.items())]}
        print(json.dumps({"round": rnd, "per_game": size, "stats": dict(stats), "new pairs": len(bad),
                          "rejections": dict(reasons.most_common(12))}, indent=1), flush=True)
        if not bad:
            if size == per_game:
                break
            size = per_game
            continue
        size = quick
        pairs = load_never()
        have = {(x["a"], x["b"]) for x in pairs}
        for (a, b), w in sorted(bad.items()):
            if a == b:
                continue             # a piece wrong on its own is a splitter bug, never a pair
            if (a, b) not in have and (b, a) not in have:
                pairs.append({"a": a, "b": b, "why": w})
        selfs = [(a, w) for (a, b), w in bad.items() if a == b]
        if selfs:
            print("SINGLE-PIECE PROBLEMS (fix the splitter):", selfs[:20])
            break
        NEVER_FILE.write_text(json.dumps({"format": "vvfp-procedural-never-with", "version": 1,
                                          "note": "piece pairs the validator found (scripts/procedural_pieces.py "
                                                  "validate); the build turns each into NEVER WITH bits",
                                          "pairs": pairs}, indent=1) + "\n", encoding="utf-8")
    return report


def attribute(comp, game: int) -> list[tuple[str, str]]:
    """The smallest piece pair a failing graph comes from: the setup with one approach and one outcome, else the
    setup with the extras.  Returns pairs to forbid."""
    out = []
    base = [comp.setup] + [p for p in (comp.flavour, comp.frame) if p]
    if comp.flavour or comp.frame:
        trial = vp.Composition(comp.group, comp.setup, comp.approaches, comp.outcomes, None, None, comp.roles,
                               comp.cast)
        if not graph_problems(trial, game):
            for p in (comp.flavour, comp.frame):
                if p:
                    out.append((comp.setup.id, p.id))
            return out
    for a, os in zip(comp.approaches, comp.outcomes):
        for o in os:
            if len(o.text or "") + len(a.text or "") + len(comp.setup.text or "") > 1900:
                out.append((comp.setup.id, o.id))
    return out


BUILT: dict[str, list[Piece]] = {}


def summary(files: dict[str, list[Piece]]) -> dict:
    kinds = collections.Counter()
    per = {}
    for n, ps in files.items():
        c = collections.Counter(vp.KIND_NAMES[p.kind] for p in ps)
        kinds.update(c)
        per[n] = {"bytes": len(vp.write_pcb(ps)), **dict(c),
                  "pair bits": bin(sum(1 << b for b in vp.FREE_BITS) &
                                   (0 if not ps else __import__("functools").reduce(
                                       lambda x, y: x | y, [p.tags | p.never for p in ps]))).count("1")}
    return {"kinds": dict(kinds), "files": per, "stats": dict(STATS), "skipped": dict(SKIPS.most_common())}


# ---- The owner's sample --------------------------------------------------------------------------------------------


def readable(comp, game: int) -> str:
    g = vp.graph_of(comp, game, notes=True)
    n, problems = cg.validate(g, scrolling=True)
    bind = {}
    for name, v in comp.cast.items():
        if isinstance(v, Villager):
            bind[name] = cg.Binding(v.name, "m" if v.sex == 1 else "f")
        else:
            bind[name] = cg.Binding("Kaimana", "f")

    def ex(t):
        try:
            return cg.expand_v6(t, n, bind, game=game, tribe="the Tribe of Isola")
        except Exception:
            return t
    lines = [f"TITLE: {comp.setup.label}", f"  (file pieces-{comp.group}.pcb; setup {comp.setup.id})"]
    lines.append("")
    for para in n["nodes"]["q"]["text"].split("\n\n"):
        lines.append("  " + ex(para))
    lines.append("")
    for i, (a, os) in enumerate(zip(comp.approaches, comp.outcomes), 1):
        lines.append(f"  [{i}] {ex(a.label)}")
        if a.text:
            lines.append(f"      {ex(a.text)}")
        total = sum(next(lk.weight for lk in o.links if lk.approach == a.id) for o in os)
        for o in os:
            w = next(lk.weight for lk in o.links if lk.approach == a.id)
            fx = ", ".join(json.dumps(vp.effect_json(e, [s.name for s in o.slots])) for e in o.effects)
            lines.append(f"      -> ({w}/{total}) {ex(o.text)}" + (f"\n         effects: {fx}" if fx else ""))
    cast = ", ".join(f"{r} = {v.name} ({v.age})" if isinstance(v, Villager) else f"{r} = a stranger"
                     for r, v in comp.cast.items())
    lines.append(f"  cast: {cast}")
    if problems:
        lines.append("  CHECK: " + "; ".join(problems[:3]))
    return "\n".join(lines)


def sample(out: Path, per_game: int = 100) -> None:
    files = {n: vp.read_pcb(vp.write_pcb(ps), n) for n, ps in build(write=False).items()}
    parts = ["Procedural Mixer Sample (for owner review)",
             "=" * 44,
             "",
             "Events the run-time mixer composes from pieces of your events and the Living bank (v1.35.97).",
             "Every word is from your events; the mixer picks a setup, 2 to 4 of its answers, 1 to 3 of each",
             "answer's outcomes, sometimes an opening line and sometimes a frame. Names are a model village.",
             "The (n/m) before an outcome is its chance after that answer.",
             ""]
    for game in GAMES:
        parts += ["", "#" * 70, f"VIRTUAL VILLAGERS {game}", "#" * 70, ""]
        rb = vp.Lcg(424242 + game)
        people = village(game)
        k = 0
        tries = 0
        while k < per_game and tries < per_game * 20:
            tries += 1
            pf = files[draw_file(files, game, rb)]
            comp = vp.compose(pf, vp.Settings(game, notes=True), rb, cast=make_cast(game, rb, people))
            if comp is None:
                continue
            k += 1
            parts += [f"--- VV{game} event {k} ---", readable(comp, game), ""]
    out.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=("build", "validate", "sample", "summary"))
    ap.add_argument("out", nargs="?")
    ap.add_argument("--per-game", type=int, default=2000)
    ap.add_argument("--quick", type=int, default=300, help="compositions a game in the quick rounds")
    a = ap.parse_args(argv)
    if a.what == "build":
        files = build(write=True)
        print(json.dumps(summary(files), indent=1))
    elif a.what == "summary":
        files = build(write=False)
        print(json.dumps(summary(files), indent=1))
    elif a.what == "validate":
        rep = validate(a.per_game, quick=a.quick)
        files = build(write=True)
        rep["summary"] = summary(files)
        REPORT_FILE.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
        print(json.dumps(rep["stats"], indent=1))
    else:
        sample(Path(a.out), 100)


if __name__ == "__main__":
    main()
