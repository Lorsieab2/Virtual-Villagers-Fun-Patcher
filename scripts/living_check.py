"""Check the Living Event Engine's packs (assets/event_collection/vvN/living.pak, docs/event-collection/living-pack.md).

Reads every pack, decompiles every variant and checks, independently of how the mixer composed it:

  * FIDELITY: every text a player can read is an indexed owner line (a seed, a role word, a personality, a choice or
    approach, an archetype, an MC situation, approach or outcome; typography made plain) or the frame
    (living-events.md section 1); every pool item and game word expanded for each game; every title is the category's;
  * QUALITY (design section D): every choice reaches a GOOD and a MIXED or BAD page; a path with no effect;
    supernatural seeds never resolve; consent offered on medical seeds; VV3 / VV5 roles and seeds only in their game;
    no "Chief" outside VV3, no "Heathen" or "convert"; supported effects only, never on a stranger; MC never kills or
    makes anyone vanish;
  * COMPAT: every exclusion of the bank's compat table and the mixer's sensitivity rules S1-S9 on every variant;
  * COUNTS: the bank's counts, K variants per active seed, one manifest row per seed per game.

    python scripts/living_check.py          # prints OK, or the problems
"""
from __future__ import annotations

import hashlib
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_cie_graph as cg  # noqa: E402
import vv_living_mixer as mx  # noqa: E402

ASSETS = ROOT / "assets" / "event_collection"
LIVING_SOURCE = ROOT / "docs" / "more-island-events" / "Isola_ALL_IN_ONE_Modular_Living_Event_Engine.txt"
COUNTS = {"seeds": 120, "roles": 30, "personalities": 24, "approaches": 34, "archetypes": 38, "mix": 60,
          "mc_situations": 95, "lenses": 15}
FRAME_RE = re.compile(r"^(?P<seed>.+?) \(first\), (?P<a>.+?), and \(second\), (?P<b>.+?), "
                      + re.escape(mx.FRAME_TAIL) + "$")
SUPPORTED = {"skill", "food", "tech", "mood", "celebrate", "health_change", "kill", "vanish", "die_unrecovered",
             "preference", "appearance", "old_look", "sick", "baby_lost"}
STRANGER_SAFE = {"food", "tech", "celebrate"}


def pack_path(game: int) -> Path:
    return ASSETS / f"vv{game}" / "living.pak"


def source_lines() -> list[str]:
    return LIVING_SOURCE.read_text(encoding="utf-8").split("\n")


def expand_words(text: str, words: dict, game: int) -> str:
    """Game words filled for `game` (authoring-rules.md 10)."""
    def one(m):
        vals = words[m.group(1)]
        return vals.get(str(game), vals.get("*"))
    return re.sub(r"\{@([A-Za-z0-9_]+)\}", one, text)


class Index:
    """Every owner text the packs may show, by its plain form."""

    def __init__(self, bank: mx.Bank):
        self.bank = bank
        self.archetype = {mx.plain(a["text"]): a["id"] for a in bank.archetypes}
        self.choice = {mx.plain(c["text"]): ("choice", c["id"]) for c in bank.choice.values()}
        self.choice.update({mx.plain(a["text"]): ("approach", a["id"]) for a in bank.approaches})
        self.personality = {mx.personality_item(bank, p["id"]): p["id"] for p in bank.pers}


def chief_form(text: str, game: int) -> str:
    """The owner's chief words as `game` says them (VV3 as written; the others the village leader)."""
    if game == 3:
        return text
    out = text
    for src, name in (("the village chief", "village_chief"), ("The chief", "Chief"), ("the chief's", "chiefs_possessive"),
                      ("A chief", "A_chief"), ("the chief", "chief")):
        out = out.replace(src, mx.CHIEF_WORDS[name]["*"])
    return out


# ---- One variant ----------------------------------------------------------------------------------------------------


def check_le(bank: mx.Bank, idx: Index, seed: dict, v: dict, d: dict, game: int, out: list[str]) -> dict:
    """Fidelity of an LE variant; returns what it found (roles, personalities, choices, archetype paths)."""
    where = f"vv{game} {mx.plain(seed['code'])} k={v['k']}"
    words = d.get("words") or {}
    if d["title"] != bank.cat[seed["category"]]["title"]:
        out.append(f"{where}: title {d['title']!r}")
    a = bank.roles[v["role_a"]]["id"]
    b = bank.roles[v["role_b"]]["id"]
    start = d["nodes"][d["start"]]
    m = FRAME_RE.match(start["text"])
    found = {"roles": (a, b), "pers": [], "choices": [], "paths": []}
    if not m:
        out.append(f"{where}: the setup is not the frame: {start['text'][:80]!r}")
        return found
    if expand_words(m["seed"], words, game) != chief_form(mx.plain(seed["text"]), game):
        out.append(f"{where}: the seed sentence differs: {m['seed']!r}")
    pools = d.get("pools") or {}
    for slot, part, rid, pool in (("first", m["a"], a, "PA"), ("second", m["b"], b, "PB")):
        word = bank.role[rid]["word"]
        if not part.endswith(" " + word):
            out.append(f"{where}: {slot} is not a {word}: {part!r}")
            continue
        head = part[:-len(word) - 1]
        if head == "{" + pool + "}":
            items = [i if isinstance(i, str) else i["text"] for i in pools[pool]["items"]]
            bad = [i for i in items if i not in idx.personality]
            if bad:
                out.append(f"{where}: pool {pool} holds {bad}")
            found["pers"].append([idx.personality.get(i) for i in items])
            if pool == "PB" and "PA" in pools and pools["PB"].get("distinct_from") != ["PA"]:
                out.append(f"{where}: PB is not distinct from PA")
        elif head in idx.personality:
            if not v["flags"] & mx.FLAG_MIX:
                out.append(f"{where}: a fixed personality outside a MIX")
            found["pers"].append([idx.personality[head]])
        elif head == bank.role[rid]["article"] and v["flags"] & mx.FLAG_MIX:
            found["pers"].append([])          # the doubled-word grammar fix
        else:
            out.append(f"{where}: {slot}'s personality {head!r} is not the bank's")
    for spec_key, rid in (("first", a), ("second", b)):
        role = d["roles"][spec_key]
        cast = bank.role[rid]["cast"]
        if role["kind"] != cast["kind"]:
            out.append(f"{where}: {spec_key} is not cast as the bank says")
        elif cast["kind"] == "villager":
            if role["min_age"] < cast.get("min_age", 14) or (cast.get("max_age") and role["max_age"] != cast["max_age"]) \
                    or role.get("special") != cast.get("special"):
                out.append(f"{where}: {spec_key}'s cast differs from the bank's")
    for c in start["choices"]:
        label = expand_words(c["label"], words, game)
        hit = None
        for text, ident in idx.choice.items():
            if chief_form(text, game) == label:
                hit = ident
        if hit is None:
            out.append(f"{where}: label {label!r} is not a bank choice")
            continue
        found["choices"].append(hit)
        br = d["nodes"][c["next"]]
        kids = br["children"]
        arcs = []
        for kid in kids:
            node = d["nodes"][kid["next"]]
            arc = idx.archetype.get(node["text"])
            if arc is None or node["children"] or node["choices"]:
                out.append(f"{where}: outcome {node['text'][:60]!r} is not an archetype ending")
                continue
            arcs.append((arc, kid["weight"]))
            want = mx.archetype_effects(bank, arc, a, b, sorted(d["games"]))
            got = [(e["do"], e.get("role")) for e in node["effects"]]
            exp = [(e["do"], e.get("role")) for e in want]
            if got != exp:
                out.append(f"{where}: {arc} effects {got} != {exp}")
            if bool(node["effects"]) != bool(node.get("auto_text")):
                out.append(f"{where}: {arc} auto lines do not match its effects")
        groups = [bank.arc[x]["group"] for x, _w in arcs]
        weights = [w for _x, w in arcs]
        if not (groups[:1] == ["good"] and len(groups) >= 2 and groups[1] in ("mixed", "bad")
                and weights[:2] == [mx.W_GOOD, mx.W_ADVERSE]
                and (len(groups) == 2 or (len(groups) == 3 and groups[2] == "rare" and weights[2] == mx.W_RARE))):
            out.append(f"{where}: choice {label!r} branches {groups} {weights}")
        found["paths"].append([x for x, _w in arcs])
    return found


def check_mc(bank: mx.Bank, sit: dict, v: dict, d: dict, game: int, out: list[str]) -> None:
    where = f"vv{game} MC {sit['code']} k={v['k']}"
    words = d.get("words") or {}
    if d["title"] != mx.mc_title(bank.mc_cat[sit["category"]]["heading"]):
        out.append(f"{where}: title {d['title']!r}")
    start = d["nodes"][d["start"]]
    if expand_words(start["text"], words, game) != chief_form(mx.plain(sit["text"]), game):
        out.append(f"{where}: setup {start['text']!r}")
    labels = [expand_words(c["label"], words, game) for c in start["choices"]]
    want = [chief_form(mx.plain(ap["text"]), game) for ap in sit["approaches"]]
    if sorted(labels) != sorted(want) or len(labels) != 4:
        out.append(f"{where}: labels {labels}")
        return
    if v["k"] == 0 and labels != want:
        out.append(f"{where}: k=0 is not in the source order")
    for c in start["choices"]:
        ap = sit["approaches"][want.index(expand_words(c["label"], words, game))]
        kids = d["nodes"][c["next"]]["children"]
        if len(kids) != len(ap["outcomes"]):
            out.append(f"{where}: {ap['letter']} has {len(kids)} outcomes")
            continue
        for kid, o in zip(kids, ap["outcomes"]):
            node = d["nodes"][kid["next"]]
            if expand_words(node["text"], words, game) != chief_form(mx.plain(o["text"]), game):
                out.append(f"{where}: {o['id']} text {node['text']!r}")
            if kid["weight"] != o.get("weight", 1):
                out.append(f"{where}: {o['id']} weight {kid['weight']}")
            if [e["do"] for e in node["effects"]] != [e["do"] for e in o["effects"]]:
                out.append(f"{where}: {o['id']} effects differ from the bank's")
            for e in node["effects"]:
                if e["do"] in ("kill", "vanish", "die_unrecovered"):
                    out.append(f"{where}: {o['id']} {e['do']} in MC")


def check_quality(bank: mx.Bank, seed: dict, v: dict, d: dict, found: dict, game: int, out: list[str]) -> None:
    """Design section D, the compat table and the sensitivity rules on one LE variant."""
    where = f"vv{game} {seed['code']} k={v['k']}"
    a, b = found["roles"]
    games = sorted(d["games"])
    sid = seed["id"]
    # compat: roles
    for rid in (a, b):
        if not bank.seed_allows(sid, "role", rid):
            out.append(f"{where}: role {rid} excluded for the seed")
        if not set(bank.role[rid]["games"]) >= set(games):
            out.append(f"{where}: role {rid} is not in every game of the variant")
    if not set(seed["games"]) >= set(games):
        out.append(f"{where}: the variant has a game its seed does not")
    if mx.is_stranger(bank, a):
        if not v["flags"] & mx.FLAG_MIX:
            out.append(f"{where}: the first villager is a stranger")
    # personalities (compat P / R rules, S1, S5)
    all_arcs = [x for p in found["paths"] for x in p]
    slots = mx.sensitive_slots(bank, all_arcs, a, b, games)
    for slot, rid, pers in zip(("first", "second"), (a, b), found["pers"]):
        for p in pers:
            if p is None:
                continue
            if not mx.personality_ok(bank, seed, rid, p, slot in slots):
                out.append(f"{where}: {slot} {rid} may be {p} (compat / S1 / S5)")
    # choices (compat, S7, S9, consent)
    if len(found["choices"]) < 2 or len(found["choices"]) > 5:
        out.append(f"{where}: {len(found['choices'])} choices")
    for kind, ident in found["choices"]:
        if not bank.seed_allows(sid, kind, ident):
            out.append(f"{where}: {ident} excluded for the seed")
        if kind == "approach" and not mx.approach_allowed(bank, seed, ident, a, b):
            out.append(f"{where}: {ident} breaks S7 or S9")
    if seed["consent_choice_required"] and not any(mx.consent_choice(bank, k, i) for k, i in found["choices"]):
        out.append(f"{where}: a medical seed with no consent choice")
    if mx.adult_frame(seed, found["choices"]):
        for key in ("first", "second"):
            r = d["roles"][key]
            if r["kind"] == "villager" and not r.get("special") and r["min_age"] < mx.ADULT_AGE:
                out.append(f"{where}: S7: {key} may be younger than {mx.ADULT_AGE}")
    # outcomes (compat, S2-S4, S6, S8, D)
    free = False
    for (kind, ident), path in zip(found["choices"], found["paths"]):
        groups = {bank.arc[x]["group"] for x in path}
        if "good" not in groups or not groups & {"mixed", "bad"}:
            out.append(f"{where}: {ident} lacks a good or an adverse outcome")
        for x in path:
            if not mx.archetype_possible(bank, sid, x, a, b):
                out.append(f"{where}: {x} excluded (compat / S8)")
            if not mx.arc_ok_after(bank, kind, ident, x):
                out.append(f"{where}: {ident} -> {x} breaks S2-S6")
            if "supernatural" in seed["tags"] and "resolves" in bank.arc[x]["tags"]:
                out.append(f"{where}: supernatural seed resolved by {x}")
            rule = mx.seed_arc_rule(bank, seed, x)
            if rule:
                out.append(f"{where}: {rule}: {x} after {ident}")
            if not mx.endorse_ok(bank, seed, kind, ident, x):
                out.append(f"{where}: S11: {ident} -> {x} rewards following an unjust custom")
            if bank.arc[x]["group"] != "rare" and not bank.arc[x]["effects"]:
                free = True
        if mx.no_mocking(seed) and "mocking" in mx.choice_classes(bank, kind, ident) and not v["flags"] & mx.FLAG_MIX:
            out.append(f"{where}: S10-S12: the seed offers the mocking {ident}")
    if not free:
        out.append(f"{where}: no path without an effect")


def check_common(d: dict, game: int, where: str, out: list[str]) -> None:
    """Supported effects, never on a stranger; the chief, Heathen and convert words; the variant's games."""
    if game not in d["games"]:
        out.append(f"{where}: in vv{game}'s pack but not for that game")
    words = d.get("words") or {}
    for nid, n in d["nodes"].items():
        texts = [n["text"]] + [c["label"] for c in n["choices"]]
        for t in texts:
            shown = expand_words(t, words, game)
            if game != 3 and re.search(r"\bchief", shown, re.I):
                out.append(f"{where}: {nid} says chief outside VV3: {shown!r}")
            if re.search(r"heathen|convert", shown, re.I):
                out.append(f"{where}: {nid} says Heathen or convert")
        for e in n["effects"]:
            if e["do"] not in SUPPORTED:
                out.append(f"{where}: {nid} effect {e['do']} is not supported")
            role = e.get("role")
            if role and d["roles"].get(role, {}).get("kind") == "stranger" and e["do"] not in STRANGER_SAFE:
                out.append(f"{where}: {nid} effect {e['do']} on a stranger")


# ---- Everything -----------------------------------------------------------------------------------------------------


def check_packs(packs: dict[int, bytes] | None = None, bank: mx.Bank | None = None) -> tuple[list[str], dict]:
    """(problems, stats) over every pack.  `packs` defaults to the shipped ones."""
    bank = bank or mx.Bank()
    idx = Index(bank)
    if packs is None:
        packs = {g: pack_path(g).read_bytes() for g in mx.GAMES}
    out: list[str] = []
    stats = {"variants": {}, "bytes": {}, "seeds": {}}
    decoded: dict[str, dict] = {}
    validated: set[str] = set()
    per_seed_k: dict[str, set] = defaultdict(set)
    for game, data in packs.items():
        p = mx.read_pack(data)
        stats["variants"][game] = len(p["variants"])
        stats["bytes"][game] = len(data)
        stats["seeds"][game] = len(p["seeds"])
        if p["game"] != game:
            out.append(f"vv{game}: the pack says game {p['game']}")
        for si, s in enumerate(p["seeds"]):
            if s["bank"] == 0:
                seed = bank.seeds[s["index"]]
                want_id = "living_" + seed["id"]
                want_series = "living_le_" + bank.cat[seed["category"]]["code"].lower()
            else:
                seed = bank.mc_sits[s["index"]]
                want_id = "living_" + seed["id"]
                want_series = "living_mc_" + bank.mc_cat[seed["category"]]["code"].lower()
            if (s["id"], s["series"]) != (want_id, want_series):
                out.append(f"vv{game}: seed {si} is {s['id']} / {s['series']}")
            if game not in seed["games"]:
                out.append(f"vv{game}: {s['id']} is not a seed of this game")
            for vi in range(s["first"], s["first"] + s["count"]):
                v = p["variants"][vi]
                if v["seed"] != si:
                    out.append(f"vv{game}: variant {vi} names seed {v['seed']}")
                per_seed_k[s["id"]].add(v["k"])
                key = hashlib.sha256(v["blob"]).hexdigest()
                if key not in decoded:
                    decoded[key] = cg.decompile_graph(v["blob"])
                d = decoded[key]
                if key not in validated:
                    _g, problems = cg.validate(d, scrolling=True)
                    if problems:
                        out.append(f"{s['id']} k={v['k']}: " + "; ".join(problems[:3]))
                    validated.add(key)
                where = f"vv{game} {s['id']} k={v['k']}"
                if not v["games"] & (1 << (game - 1)) or v["games"] != sum(1 << (g - 1) for g in d["games"]):
                    out.append(f"{where}: games mask")
                check_common(d, game, where, out)
                # the outcome map: every ending, with its archetype
                order = list(d["nodes"])
                ends = sorted(order.index(n) for n, node in d["nodes"].items()
                              if node["type"] != "branch" and not node["children"] and not node["choices"])
                if [o[0] for o in v["outcomes"]] != ends:
                    out.append(f"{where}: the outcome map is not every ending")
                for node_i, grp, arc in v["outcomes"]:
                    text = d["nodes"][order[node_i]]["text"]
                    if s["bank"] == 0:
                        if arc >= len(bank.archetypes) or mx.plain(bank.archetypes[arc]["text"]) != text \
                                or mx.GROUP_CODE[bank.archetypes[arc]["group"]] != grp:
                            out.append(f"{where}: outcome {node_i} maps to the wrong archetype")
                    elif arc != mx.NONE8 or grp not in (1, 3):
                        out.append(f"{where}: MC outcome {node_i} map")
                if s["bank"] == 0:
                    found = check_le(bank, idx, seed, v, d, game, out)
                    if found["paths"]:
                        check_quality(bank, seed, v, d, found, game, out)
                else:
                    check_mc(bank, seed, v, d, game, out)
    # counts
    raw = bank.raw
    for key, want in COUNTS.items():
        have = {"seeds": len(bank.seeds), "roles": len(bank.roles), "personalities": len(bank.pers),
                "approaches": len(bank.approaches), "archetypes": len(bank.archetypes), "mix": len(bank.mix),
                "mc_situations": len(bank.mc_sits), "lenses": len(bank.lenses)}[key]
        if have != want or raw["counts"].get(key, want) != want:
            out.append(f"the bank has {have} {key}, the source {want}")
    active = ["living_" + s["id"] for s in bank.seeds] + \
             ["living_" + s["id"] for s in bank.mc_sits if s.get("outcomes_status") == "active"]
    for sid in active:
        k_want = mx.MC_K if sid.startswith("living_mc_") else mx.K
        if per_seed_k.get(sid) != set(range(k_want)):
            out.append(f"{sid}: variants k {sorted(per_seed_k.get(sid, []))}, expected 0..{k_want - 1}")
    return out, stats


def main() -> int:
    problems, stats = check_packs()
    for game in mx.GAMES:
        print(f"vv{game}: {stats['seeds'][game]} seeds, {stats['variants'][game]} variants, "
              f"{stats['bytes'][game]:,} bytes")
    if problems:
        for p in problems[:200]:
            print(p)
        print(f"{len(problems)} problems")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
