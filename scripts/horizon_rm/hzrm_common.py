"""Shared helpers for two of the owner's 2026-11-15 sources (scripts/horizon_rm/gen_hz.py, gen_rm.py):

  * "Isola - Beyond the Horizon" (collection_lib.HORIZON, source "horizon"): a separate companion anthology, EVENT
    001-080, one line per part of an event;
  * "Role Models and Good Examples" (collection_lib.ROLEMODELS, source "rolemodels"): RM-01..RM-40, the WHOLE event on
    one line.

Both ship as collection events like the Living Event Engine's volumes (scripts/living_vols/living_common.py, whose
roles, effect helpers and weights these reuse): one v6 file per event in data/event_collection/<horizon |
rolemodels>/<section>/<id>.json, rows from data/event_collection/manifest.json, checked by
scripts/collection_check.py --format.

THE EVENT SHAPE (both sources): the setup is the question page with the labels A-C (Horizon) or A-D (Role Models);
each label leads to its OWN two outcomes, which are mutually exclusive alternatives (the sources: "Choose one outcome
from the selected choice, never both"): a silent branch, one page each, equally likely (neither source gives odds,
and neither has a harmful outcome).  "SETUP:", "A.", "A1." are structural markers.  Horizon's "Content note: ..." and
"VV3: ..." lines after an event are the designer's notes (ledger "note"); its "small Building experience" / "modest
Research experience" are instructions carried out as the node's skill effect (ledger "instruction").  A Role Models
line's heading "EVENT RM-01 — THE FAIR SHARE SETUP:" is the title (ledger "structural" cut); each page's text is its
part of the one line (the fidelity check finds it inside the line).

THE KEYWORD TABLE ON ONE-LINE EVENTS: collection_check scans a node's whole source line for words that promise a
change ("food", "experience", ...).  A Role Models node's line is the whole event, so a word in another part of it is
not this page's: such a node carries a text_only entry saying so (and naming the words); a word on the page's own text
that changes nothing in the game gets its own reason.

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
sys.path.insert(0, str(ROOT / "scripts" / "living_vols"))
import collection_check as cc  # noqa: E402
import collection_lib as lib  # noqa: E402
import living_common as lc  # noqa: E402

VILLAGER, GROWN, CHILD, ELDER, YOUNG = lc.VILLAGER, lc.GROWN, lc.CHILD, lc.ELDER, lc.YOUNG
skilled, sk, T, description_ok = lc.skilled, lc.sk, lc.T, lc.description_ok


def L(n: int) -> str:
    return f"L{n}"


def rows(source: str, section: str | None = None) -> list[dict]:
    data = json.loads(lib.MANIFEST.read_text(encoding="utf-8"))
    out = [r for r in data["rows"] if r.get("source") == source and r["kind"] == "event"
           and (section is None or r["section"] == section)]
    return sorted(out, key=lambda r: r["lines"][0])


def num_of(row: dict) -> int:
    return int(re.match(r"(?:hz|rm)(\d+)_", row["id"]).group(1))


def keywords_on(text: str) -> list[str]:
    """The effect-table words (collection_check.KEYWORDS) on `text`, in order, each once."""
    out = []
    for rx, _ in cc.KEYWORDS:
        for m in rx.finditer(text):
            if m.group(0).lower() not in out:
                out.append(m.group(0).lower())
    return out


def _kinds(effects: list[dict]) -> set[str]:
    return {cc.EFFECT_KIND.get(e["do"], e["do"]) for e in effects}


def _uncovered_words(text: str, effects: list[dict]) -> list[str]:
    kinds = _kinds(effects)
    out = []
    for rx, want in cc.KEYWORDS:
        if kinds & want:
            continue
        for m in rx.finditer(text):
            if m.group(0).lower() not in out:
                out.append(m.group(0).lower())
    return out


def _page(name: str, text: str, src: str, effects: list[dict], text_only: list[dict]) -> dict:
    page = {"name": name, "text": text, "src": src}
    if effects:
        page["effects"] = [dict(e, src=src) for e in effects]
    if text_only:
        page["text_only"] = [dict(t, src=src) for t in text_only]
    return page


def _doc(row: dict, roles: dict, desc: str, ledger: list[dict], q_text: str, q_src: str, q_to: list[dict],
         letters: str, labels: dict, outcomes: dict, srcs: dict, fx: dict, to: dict) -> dict:
    """The v6 document of the shape in the module docstring."""
    assert description_ok(desc), (row["id"], desc)
    unknown = (set(fx) | set(to)) - {0} - {f"{k}{i}" for k in letters for i in (1, 2)}
    assert not unknown, (row["id"], unknown)
    choices, nodes = [], {}
    for k in letters:
        choices.append({"label": labels[k], "next": k, "src": srcs[k]})
        kids = []
        for j in (1, 2):
            key = f"{k}{j}"
            eff = fx.get(key, [])
            kids.append({"next": key, "rarity": lc.rarity_of(eff)})
            nodes[key] = _page(f"Outcome {key.upper()}", outcomes[key], srcs[key], eff, to.get(key, []))
        if any(kd["rarity"] for kd in kids) and kids[0]["rarity"] != kids[1]["rarity"]:
            for kd in kids:
                kd["weight"] = cc.RARITY_WEIGHTS[kd["rarity"]]
                if not kd["rarity"]:
                    del kd["rarity"]
        else:
            for kd in kids:
                kd.pop("rarity")
        nodes[k] = {"type": "branch", "name": f"Answer {k.upper()}", "children": kids}
    q = {"type": "question", "name": "The setup", "text": q_text, "src": q_src, "choices": choices}
    if q_to:
        q["text_only"] = [dict(t, src=q_src) for t in q_to]
    order = ["setup"] + [x for k in letters for x in (k, f"{k}1", f"{k}2")]
    nodes = {"setup": q, **nodes}
    nodes = {key: nodes[key] for key in order}
    used = {e.get("role") for n in nodes.values() for e in n.get("effects", [])} - {None, "all"}
    col = {"id": row["id"], "title_src": L(row["lines"][0]), "ledger": ledger, "description": desc}
    cast_only = [r for r in roles if r not in used]
    if cast_only:
        col["cast_only"] = cast_only
    return {"format": "vvfp-cie-graph", "version": 6, "title": row["title"], "games": row["games"],
            "collection": col, "requirement": {"min_eligible": len(roles)}, "roles": roles, "start": "setup",
            "nodes": nodes}


def _first_sentence(text: str) -> str:
    m = re.match(r"^(.+?[.!?])(?:\s|$)", text)
    return m.group(1) if m else text


def auto_description(setup: str) -> str | None:
    """The setup, or its first sentence, when it is a plain Pick Island Event sentence."""
    for t in (setup, _first_sentence(setup)):
        if description_ok(t):
            return t
    return None


# ---- Beyond the Horizon: one line per part ----------------------------------------------------------------------------

INSTRUCTION_WHY = "an instruction inside the outcome, never shown: the node's skill effect"
NOTE_WHY = {
    "Content note:": "Content note: the owner's per-event content note (the coming per-event content-notes feature "
                     "shows it; listed in the build report's content-note table), never part of a page",
    "VV3:": "VV3: the designer's game note (the Tribal Chief only observes; no event replaces or deposes the Chief): "
            "nothing in the event casts or changes the Chief, so it holds in every game",
}


# Why a Beyond the Horizon page's effect-table word changes nothing (every page is talk, imagination or a small
# harmless trial; the source: "quiet scenes may give none").  Keyed by the word's effect kind.
HZ_WORD_WHY = {
    "food": "food talked about or imagined; the village's stores do not change",
    "tech": "technology talked about or imagined; no tech points change",
    "skill": "\"experience\" / \"skill\" in the everyday sense (what a person has lived through or can do), "
             "not a skill gain",
    "celebrate": "a celebration imagined or discussed (or a feeling of joy); no celebration happens in the game",
    "health": "an injury imagined or discussed; nobody is hurt",
    "preference": "a feeling in the moment, not a lasting dislike",
    "damage": "a small model collapses; no building of the village is damaged",
    "vanish": "the word's everyday sense (a thing or a duty disappears); nobody goes missing",
}


def hz_text_only(text: str, effects: list[dict]) -> list[dict]:
    """text_only entries for the effect-table words on a Horizon page (HZ_WORD_WHY)."""
    kinds = _kinds(effects)
    out = []
    for rx, want in cc.KEYWORDS:
        if kinds & want:
            continue
        words = []
        for m in rx.finditer(text):
            if m.group(0).lower() not in words:
                words.append(m.group(0).lower())
        if words:
            kind = sorted(want)[0] if want != {"health", "health_change"} else "health"
            assert kind in HZ_WORD_WHY, (kind, words, text)
            out.append(T(", ".join(f'"{w}"' for w in words), HZ_WORD_WHY[kind]))
    return out


def hz_shown(n: int, cuts: dict[int, list[str]]) -> str:
    with lib.use_source(lib.HORIZON_ID):
        p = cc.processed_line(n, cuts, {})
    return p[:1].upper() + p[1:]


def hz_line(n: int) -> str:
    with lib.use_source(lib.HORIZON_ID):
        return lib.normalize_source_text(lib.line(n))


def build_hz(row: dict, roles: dict, desc: str | None, opts: dict) -> dict:
    """One Beyond the Horizon event.  opts: fx {"a1": [effects]}, to {0 | "a1": [text_only]},
    instr {"a1": "; small Building experience"} (an instruction cut from that outcome's line)."""
    h, last = row["lines"]
    letters = "abc"
    setup = h + 1
    assert hz_line(setup).startswith("SETUP: "), row["id"]
    ledger, cuts = [], {}
    labels, outcomes, srcs = {}, {}, {}
    for i, k in enumerate(letters):
        lab = h + 2 + 3 * i
        assert hz_line(lab).startswith(f"{k.upper()}. "), (row["id"], k)
        labels[k], srcs[k] = hz_shown(lab, {}), L(lab)
        for j in (1, 2):
            o, key = lab + j, f"{k}{j}"
            assert hz_line(o).startswith(f" {k.upper()}{j}. "), (row["id"], key)
            if key in opts.get("instr", {}):
                cut = opts["instr"][key]
                assert cut in hz_line(o), (row["id"], key, cut)
                cuts[o] = [cut]
                ledger.append({"src": L(o), "kind": "instruction", "text": cut, "why": INSTRUCTION_WHY})
            outcomes[key], srcs[key] = hz_shown(o, cuts), L(o)
    for n in range(h + 11, last + 1):
        s = hz_line(n)
        tag = next((t for t in NOTE_WHY if s.startswith(t)), None)
        assert tag, (row["id"], n, s)
        ledger.append({"src": L(n), "kind": "note", "why": NOTE_WHY[tag]})
    q_text = hz_shown(setup, {})
    desc = desc or auto_description(q_text)
    assert desc, (row["id"], "needs a description", q_text)
    fx = opts.get("fx", {})
    to = {0: hz_text_only(q_text, [])}
    for key, text in outcomes.items():
        to[key] = hz_text_only(text, fx.get(key, []))
    to = {k: v for k, v in to.items() if v}
    return _doc(row, roles, desc, ledger, q_text, L(setup), to.get(0, []), letters, labels,
                outcomes, srcs, fx, to)


# ---- Role Models and Good Examples: the whole event on one line -------------------------------------------------------

RM_HEAD = re.compile(r"^(EVENT RM-\d{2}\s+-\s+.+? SETUP:)\s+(.*)$")
RM_MARK = re.compile(r"\s([A-D][12]?)\.\s")
ONE_LINE_WHY = ("the source puts the whole event on one line: {words} is in another part of it (another page's "
                "words), not this page's")


def rm_parts(n: int) -> tuple[str, dict[str, str]]:
    """Line n's heading and its parts: {"setup", "a", "a1", "a2", ..., "d2"} (normalised, as the line has them)."""
    with lib.use_source(lib.ROLEMODELS_ID):
        s = lib.normalize_source_text(lib.line(n))
    m = RM_HEAD.match(s)
    assert m, n
    head, rest = m.group(1), m.group(2).strip()
    bits = RM_MARK.split(rest)
    want = [x for k in "ABCD" for x in (k, f"{k}1", f"{k}2")]
    assert bits[1::2] == want, (n, bits[1::2])
    parts = {"setup": bits[0].strip()}
    for mark, text in zip(bits[1::2], bits[2::2]):
        parts[mark.lower()] = text.strip()
    return head, parts


def build_rm(row: dict, roles: dict, desc: str | None, opts: dict) -> dict:
    """One Role Models event.  opts: fx {"a1": [effects]}, to {0 | "a1": [text_only]} (a word on the page's own
    text that changes nothing in the game; the one-line entries are made here)."""
    n = row["lines"][0]
    head, parts = rm_parts(n)
    letters = "abcd"
    ledger = [{"src": L(n), "kind": "structural", "text": head,
               "why": "the event's number and title (the title) and the SETUP: marker; the source puts the whole "
                      "event on one line"}]
    fx, to = opts.get("fx", {}), {k: list(v) for k, v in opts.get("to", {}).items()}
    line_words = keywords_on(" ".join(parts.values()))
    for key in [0] + [f"{k}{j}" for k in letters for j in (1, 2)]:
        # the question page shows the setup and the labels
        text = " ".join([parts["setup"]] + [parts[k] for k in letters]) if key == 0 else parts[key]
        own = _uncovered_words(text, fx.get(key, []))
        assert not own or to.get(key), (row["id"], key, "needs a text_only reason for", own)
        others = [w for w in line_words if w not in keywords_on(text)]
        kinds = _kinds(fx.get(key, []))
        others = [w for w in others if not any(rx.fullmatch(w) and kinds & want for rx, want in cc.KEYWORDS)]
        if others and not to.get(key):
            to.setdefault(key, []).append(T(", ".join(f'"{w}"' for w in others),
                                            ONE_LINE_WHY.format(words=", ".join(f'"{w}"' for w in others))))
    labels = {k: parts[k] for k in letters}
    outcomes = {f"{k}{j}": parts[f"{k}{j}"] for k in letters for j in (1, 2)}
    srcs = {k: L(n) for k in list(letters) + list(outcomes)}
    desc = desc or auto_description(parts["setup"])
    assert desc, (row["id"], "needs a description", parts["setup"])
    return _doc(row, roles, desc, ledger, parts["setup"], L(n), to.get(0, []), letters, labels, outcomes, srcs, fx,
                to)


# ---- Writing ----------------------------------------------------------------------------------------------------------

def write_and_check(docs: list[tuple[Path, dict]]) -> int:
    paths = []
    for p, doc in docs:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(cc.canonical(doc), encoding="utf-8", newline="\n")
        paths.append(str(p))
    return subprocess.call([sys.executable, str(ROOT / "scripts" / "collection_check.py"), "--format", *paths])
