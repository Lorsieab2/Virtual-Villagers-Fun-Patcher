"""Shared builder for the owner-approved drafts of 2026-11-15, set A (scripts/drafts_a/gen_<file>.py).

Twelve draft files, each its own frozen source (collection_lib.DRAFTS_A; rows from scripts/collection_manifest.py
_draft_rows): Inner Life I-X (events 1-200), What's That Doing Here (WD-01..50), Luck, Omens and Lavastones
(LO-01..50).  One v6 file per event in data/event_collection/drafts_a/<section>/<id>.json, checked by
scripts/collection_check.py --format.  docs/event-collection/authoring-rules.md 15d.

THE EVENT SHAPE (every file):
  "12. Title" / "WD-01. Title" / "LO-01. Title"       the title (title_src)
  "(picks ...)"                                         the casting line: a ledger note (the roles carry it)
  setup paragraph(s)                                    the question page (or the only page of a single popup)
  "Label:" then its outcome paragraph(s)                one answer page per choice
LO's odds lines inside an outcome ("(About 6 in 10) ...", "(Otherwise) ...") are alternatives of that answer: the
answer page shows the lines before them, then a silent branch picks one, weighted by the text's own odds (the
rulebook: "your text's own odds win"; each child's authoring key "odds" names them).  "[effect: ...]" and
"[no effect]" are instructions: a ledger cut, and the effect on that page.  "⸻" lines are separators (ledger
structural).

ROLES: (name1) is the role "subject", (name2) the role "friend" (vv_cie_graph's name aliases), so the owner's
"(name1)" ships as written.  (he/she), (him/her), (his/her) follow a role: by default the name mentioned last before
it on the page (a label: the label's own name, else the setup's last name); an event's "pron" table overrides one
occurrence ({node: {k: role}}, k counting that node's pronouns from 0).  A pronoun that starts a sentence is written
with a capital.  The casting line's ages (child 3-13, teen 14-17, young adult 18-25, elder 55+, adult 18+ unless
said) are read here; an event's "roles" entry overrides them.

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
import collection_check as cc  # noqa: E402
import collection_lib as lib  # noqa: E402

ALL = [1, 2, 3, 4, 5]
ROLE_OF = {"name1": "subject", "name2": "friend"}

# Roles
ANY = {"kind": "villager", "min_age": 3}
VILLAGER = {"kind": "villager", "min_age": 14}
ADULT = {"kind": "villager", "min_age": 18}
CHILD = {"kind": "villager", "min_age": 3, "max_age": 13}
TEEN = {"kind": "villager", "min_age": 14, "max_age": 17}
YOUNG_ADULT = {"kind": "villager", "min_age": 18, "max_age": 25}
ELDER = {"kind": "villager", "min_age": 55}


def ages(lo: int, hi: int | None = None) -> dict:
    r = {"kind": "villager", "min_age": lo}
    if hi is not None:
        r["max_age"] = hi
    return r


def skilled(base: dict, skill: str) -> dict:
    return dict(base, skill={"names": [skill], "min": 1})


def related(base: dict, kind: str, other: str) -> dict:
    return dict(base, relation={kind: other})


# Effects
def sk(role: str, skill, size: str = "small") -> dict:
    lo, hi = cc.SKILL_SIZES[size]
    return {"do": "skill", "role": role, "skills": [skill] if isinstance(skill, str) else list(skill),
            "min": lo, "max": hi}


def sk_loss(role: str, skill, size: str = "small") -> dict:
    lo, hi = cc.SKILL_SIZES[size]
    return {"do": "skill", "role": role, "skills": [skill] if isinstance(skill, str) else list(skill),
            "min": -hi, "max": -lo}


def food(size: str = "small", loss: bool = False) -> dict:
    e = {"do": "food", "size": size, "scaled": True}
    if loss:
        e["loss"] = True
    return e


def tech(size: str = "small") -> dict:
    return {"do": "tech", "size": size, "scaled": True}


def celebrate(role: str | None = None) -> dict:
    return {"do": "celebrate", "who": role or "all"}


def health(role: str, lo: int, hi: int) -> dict:
    return {"do": "health_change", "role": role, "min": lo, "max": hi}


MINOR, SERIOUS, BETTER, SMALL_BETTER = (-30, -10), (-60, -40), (10, 30), (5, 15)


def sick(role: str) -> dict:
    return {"do": "sick", "role": role}


def die(role: str) -> dict:
    return {"do": "kill", "role": role, "cause": "unknown"}


def dislike(role: str, what: str) -> dict:
    return {"do": "preference", "role": role, "list": "dislikes", "preference": what}


def old_look(role: str) -> dict:
    return {"do": "old_look", "role": role}


def T(what: str, reason: str) -> dict:
    return {"what": what, "reason": reason}


# The bracketed instructions every file uses the same way (the text inside "[effect: ...]", as the source has it,
# names replaced by their roles).  A file's own table (opts "fx") adds or overrides per event.
EFFECTS = {
    "(name1) celebrates": [celebrate("subject")],
    "(name2) celebrates": [celebrate("friend")],
    "small food gain": [food("small")],
    "small tech gain, only where the game has tech points": [tech("small")],
}

# Why an effect-table word on a page changes nothing (keyed by its effect kind): every page is a passing moment
# (the drafts' own notes: "Everything else is story only").
WORD_WHY = {
    "food": "food in the story (a meal, a snack, a basket of fruit); the village's stores do not change",
    "tech": "technology talked about in the story; no tech points change",
    "skill": "\"skill\" / \"experience\" in its everyday sense, not a skill gain (the draft: story only)",
    "kill": "death talked about or remembered in the story; nobody dies",
    "vanish": "the word's everyday sense (a thing, a sound or a worry disappears); nobody goes missing",
    "celebrate": "a celebration in the story (a feast, a moment of joy); no village celebration happens in the game",
    "preference": "a feeling in the moment, not a lasting dislike (the draft: nothing becomes a permanent trait)",
    "health": "health or an injury talked about in the story; nobody's health changes",
    "damage": "a small thing collapses in the story (a tower of shells, a pile); no building is damaged",
}


def L(n: int) -> str:
    return f"L{n}"


def line(n: int) -> str:
    return lib.normalize_source_text(lib.line(n)).rstrip("\r")


LABEL_RE = re.compile(r'^[A-Z(][^.!?"]{0,100}:$')
ODDS_RE = re.compile(r"^\((About (\d+) in (\d+)|Otherwise)\)\s+")
BRACKET_RE = re.compile(r"\s*\[[^\]]*\]")
PH_RE = re.compile(r"\(([^()]*)\)")
PRONOUN_FORMS = {"he/she", "him/her", "his/her", "himself/herself"}


def rows(source: str) -> list[dict]:
    data = json.loads(lib.MANIFEST.read_text(encoding="utf-8"))
    out = [r for r in data["rows"] if r.get("source") == source and r["kind"] == "event"]
    return sorted(out, key=lambda r: r["lines"][0])


def num_of(row: dict) -> int:
    return int(re.match(r"(?:il|wd|lo)(\d+)_", row["id"]).group(1))


# ---- Parsing ------------------------------------------------------------------------------------------------------

def parse(row: dict) -> dict:
    """The event's parts: {"head", "cast", "setup": [lines], "answers": [{"label", "lines": [...]}], "seps": [...]}."""
    h, last = row["lines"]
    out = {"head": h, "cast": None, "setup": [], "answers": [], "seps": []}
    cur = out["setup"]
    for n in range(h + 1, last + 1):
        s = line(n).strip()
        if not s or lib.is_separator(s):
            continue
        if s == "⸻":
            out["seps"].append(n)
            continue
        if out["cast"] is None and not out["setup"] and s.startswith("(picks"):
            out["cast"] = n
            continue
        if LABEL_RE.match(s):
            out["answers"].append({"label": n, "lines": []})
            cur = out["answers"][-1]["lines"]
            continue
        cur.append(n)
    assert out["cast"], (row["id"], "no casting line")
    assert out["setup"], (row["id"], "no setup")
    assert all(a["lines"] for a in out["answers"]), (row["id"], "an answer without text")
    return out


def cast_roles(text: str, two: bool) -> dict:
    """Roles from the casting line (module docstring)."""
    t = text.lower()

    def spec(part: str) -> dict:
        m = re.search(r"aged (\d+)\s*-\s*(\d+)", part)
        if m:
            return ages(int(m.group(1)), int(m.group(2)))
        m = re.search(r"aged (\d+) or older", part)
        if m:
            return ages(int(m.group(1)))
        if "young adult" in part:
            return dict(YOUNG_ADULT)
        if re.search(r"\bteen", part) and "adult" not in part:
            return dict(TEEN)
        if re.search(r"\bteen", part):
            return dict(VILLAGER)
        if re.search(r"\b(child|toddler)", part):
            return dict(CHILD)
        if re.search(r"\belder", part):
            return dict(ELDER)
        if "any villager" in part or "anyone" in part:
            return dict(ANY)
        return dict(ADULT)
    parts = re.split(r"\band\b|;|, and ", t, maxsplit=1)
    roles = {"subject": spec(parts[0])}
    if two:
        roles["friend"] = spec(parts[1]) if len(parts) > 1 and re.search(
            r"child|teen|elder|adult|villager|aged", parts[1]) else dict(ADULT)
    return roles


# ---- Text -----------------------------------------------------------------------------------------------------------

class Pron:
    """Pronoun resolution across an event: the last name seen, per-node overrides."""

    def __init__(self, two: bool, overrides: dict, extra: tuple = ()):
        self.two = two
        self.last = "subject"
        self.over = overrides
        self.extra = {r.lower(): r for r in extra}     # roles the casting edits name: "(visitor)"
        self.log: list[tuple[str, int, str, str]] = []

    def render(self, node: str, text: str, carry: bool = True) -> str:
        last = self.last
        k = 0
        out = []
        pos = 0
        for m in PH_RE.finditer(text):
            out.append(text[pos:m.start()])
            pos = m.end()
            inner = m.group(1)
            low = inner.lower()
            if low in ROLE_OF:
                last = ROLE_OF[low]
                out.append(f"({last})" if self.two else m.group(0))
            elif low.split(".")[0] in self.extra and "." not in low:
                last = self.extra[low]
                out.append(m.group(0))
            elif low in PRONOUN_FORMS or low == "his/hers":
                ov = self.over.get(node, {})
                role = ov if isinstance(ov, str) else ov.get(k, last)
                self.log.append((node, k, inner, role))
                k += 1
                before = "".join(out).rstrip(" ")
                # a sentence's start is a capital; after a closing quote ("...?" he asks) the source's case stands
                inq = before.rstrip("\"'")
                start = (not before or before[-1] in ".!?"
                         or (before[-1] in "\"'" and (inner[:1].isupper() or inq.endswith("."))))
                word = inner
                if start:
                    word = "/".join(w[:1].upper() + w[1:] for w in word.split("/"))
                out.append(f"({role}.{word})" if self.two else f"({word})")
            else:
                out.append("\\(" + inner + "\\)")
        out.append(text[pos:])
        if carry:
            self.last = last
        return "".join(out)


def keywords_uncovered(text: str, effects: list[dict]) -> list[dict]:
    kinds = {cc.EFFECT_KIND.get(e["do"], e["do"]) for e in effects}
    out = []
    for rx, want in cc.KEYWORDS:
        if kinds & want:
            continue
        words = []
        for m in rx.finditer(text):
            if m.group(0).lower() not in words:
                words.append(m.group(0).lower())
        if words:
            kind = sorted(want)[0] if want != {"health", "health_change", "deliver_early"} else "health"
            kind = {"birth_then_die": "kill", "die_unrecovered": "kill"}.get(kind, kind)
            out.append(T(", ".join(f'"{w}"' for w in words), WORD_WHY[kind]))
    return out


# ---- Building ---------------------------------------------------------------------------------------------------------

DESC_SUBS = [(r"\((?:name1|subject)\)'s", "a villager's"), (r"\((?:name2|friend)\)'s", "another villager's"),
             (r"\((?:name1|subject)\)", "a villager"), (r"\((?:name2|friend)\)", "another villager")]


def auto_description(setup: str) -> str | None:
    m = re.match(r"^(.+?[.!?])(?:\s|$)", setup)
    t = m.group(1) if m else setup
    if re.search(r"\((?:he|him|his)", t, re.I):
        return None
    for a, b in DESC_SUBS:
        t = re.sub(a, b, t)
    t = t.replace('"', "").replace("\\(", "").replace("\\)", "")
    t = t[:1].upper() + t[1:]
    return t if cc.DESCRIPTION_RE.fullmatch(t) and len(t) <= cc.DESCRIPTION_MAX else None


def build(row: dict, opts: dict) -> tuple[dict, list]:
    """One event.  opts:
      roles {role: spec}            override the casting line's roles (and add relations, skills)
      desc "..."                    the Pick Island Event sentence (else the setup's first sentence, made plain)
      fx {node: [effects]}          effects on a page ("setup", "a", "b", "a1" ...); the bracket's instruction is cut
      pron {node: {k: role}}        pronoun overrides
      to {node: [text_only]}        extra text_only reasons
      sens [(line, before, after, why)]  sensitivity edits (a hard-rule break only)
      fixes [(line, before, after)] grammar fixes (rows of grammar-fixes.md)
      chief True                    "chief" in the text is the game word
      cast [(line, before, after)]  the owner's naming rule (2026-11-15): a person the draft names only by role
                                    ("a visitor", "the old fisher") is a cast villager, named at the first mention:
                                    after = "(visitor), a visitor" (or just "(visitor)" where that reads naturally);
                                    the role ("visitor") goes in roles, and later pronouns follow it (ledger kind
                                    "casting": the line's words with the name added, nothing else)
    Returns (doc, pronoun log)."""
    p = parse(row)
    h = p["head"]
    names = {m.lower() for n in range(h, row["lines"][1] + 1) for m in re.findall(r"\((name[12])\)", line(n), re.I)}
    two = "name2" in names
    roles = opts.get("roles") or cast_roles(line(p["cast"]), two)
    ledger = [{"src": L(p["cast"]), "kind": "note",
               "why": "the casting line (the roles carry it)" + (f"; {opts['note']}" if opts.get("note") else "")}]
    for n in p["seps"]:
        ledger.append({"src": L(n), "kind": "structural", "why": "a separator between events"})
    fixes = opts.get("fixes", [])
    sens = opts.get("sens", [])
    fix_map: dict[int, list[tuple[str, str]]] = {}
    for n, b, a in fixes:
        fix_map.setdefault(n, []).append((b, a))
    for n, b, a, why in sens:
        fix_map.setdefault(n, []).append((b, a))
        ledger.append({"src": L(n), "kind": "sensitivity", "before": b, "after": a, "why": why})
    for n, b, a in opts.get("cast", []):
        fix_map.setdefault(n, []).append((b, a))
        ledger.append({"src": L(n), "kind": "casting", "before": b, "after": a,
                       "why": "the owner's naming rule (2026-11-15): a person the draft names by role is a cast "
                              "villager, named at the first mention"})
    extra = tuple(r for r in roles if r not in ("subject", "friend"))
    pron = Pron(len(roles) > 1, opts.get("pron", {}), extra)
    fx = {k: list(v) for k, v in opts.get("fx", {}).items()}
    to_extra = opts.get("to", {})
    instr: dict[str, list[int]] = {}

    def shown(n: int, node: str) -> str:
        """Line n's text with its fixes, its bracketed instruction and odds marker taken out."""
        s = line(n)
        for b, a in fix_map.get(n, []):
            s = s.replace(b, a)
        for m in re.finditer(r"\[[^\]]*\]", s):
            ledger.append({"src": L(n), "kind": "instruction", "text": m.group(0),
                           "why": "the draft's effect note, never shown: " + (
                               "the page's effect" if m.group(0) != "[no effect]" else "no effect")})
            inner = m.group(0)[1:-1]
            if inner.startswith("effect: "):
                instr.setdefault(node, []).append(n)
                key = inner[len("effect: "):]
                if node not in opts.get("fx", {}):
                    assert key in EFFECTS, (row["id"], node, key, "needs fx")
                    fx.setdefault(node, []).extend(EFFECTS[key])
        s = BRACKET_RE.sub("", s)
        om = ODDS_RE.match(s)
        if om:
            ledger.append({"src": L(n), "kind": "structural", "text": om.group(0).strip(),
                           "why": "the outcome's odds: the branch's weight"})
            s = s[om.end():]
        s = re.sub(r"\s+", " ", s).strip()
        s = s[:1].upper() + s[1:] if not s.startswith("(") else s
        if opts.get("chief"):
            s = re.sub(r"\bchief\b", "{@chief}", s)
        return s

    def page(node: str, ns: list[int], name: str, extra: dict | None = None) -> dict:
        texts = [pron.render(node, shown(n, node)) for n in ns]
        eff = fx.get(node, [])
        src = ",".join(L(n) for n in ns)
        d = {"name": name}
        if extra:
            d.update(extra)
        d["text"] = "\n".join(texts)
        d["src"] = src
        if eff:
            esrc = ",".join(L(n) for n in instr.get(node, [])) or src
            d["effects"] = [dict(e, src=esrc) for e in eff]
        to = keywords_uncovered(" ".join(texts), eff) + list(to_extra.get(node, []))
        if to:
            d["text_only"] = [dict(t, src=src) for t in to]
        return d

    nodes: dict = {}
    setup_text_lines = p["setup"]
    letters = "abcdefg"
    if p["answers"]:
        q = page("setup", setup_text_lines, "The setup", {"type": "question"})
        q["choices"] = []
        nodes["setup"] = q
        after_setup = pron.last
        for i, a in enumerate(p["answers"]):
            k = letters[i]
            pron.last = "subject"       # a label without a name of its own means (name1)
            lab = line(a["label"])[:-1].strip()
            for b, x in fix_map.get(a["label"], []):
                lab = lab.replace(b, x)
            lab_r = pron.render(k + "_label", lab, carry=False)
            pron.last = after_setup
            q["choices"].append({"label": lib.title_case_label(lab_r), "next": k, "src": L(a["label"])})
            ls = a["lines"]
            odds = [n for n in ls if ODDS_RE.match(line(n))]
            if not odds:
                nodes[k] = page(k, ls, f"Answer {k.upper()}")
                continue
            lead = [n for n in ls if n < odds[0]]
            assert lead and all(n in odds for n in ls if n > odds[0]), (row["id"], k)
            base = page(k, lead, f"Answer {k.upper()}")
            kids = []
            weights = []
            for n in odds:
                om = ODDS_RE.match(line(n))
                weights.append((int(om.group(2)), int(om.group(3))) if om.group(2) else None)
            # weights out of the least common denominator; "Otherwise" takes the rest
            from math import lcm
            den = lcm(*[d for w in weights if w for _, d in [w]])
            ws = [w[0] * den // w[1] if w else None for w in weights]
            rest = den - sum(w for w in ws if w)
            ws = [w if w is not None else rest for w in ws]
            assert all(w > 0 for w in ws) and sum(ws) == den, (row["id"], k, ws)
            after_lead = pron.last
            for j, n in enumerate(odds):
                key = f"{k}{j + 1}"
                pron.last = after_lead
                nodes[key] = page(key, [n], f"Outcome {key.upper()}", {"popup": "append", "join": "paragraph"})
                kids.append({"next": key, "weight": ws[j], "odds": ODDS_RE.match(line(n)).group(1)})
            base["children"] = kids
            nodes[k] = base
    else:
        nodes["setup"] = page("setup", setup_text_lines, "The moment")
    unknown = set(fx) - set(nodes)
    assert not unknown, (row["id"], "fx on unknown nodes", unknown)
    desc = opts.get("desc") or auto_description(nodes["setup"]["text"].split("\n")[0])
    if not (desc and cc.DESCRIPTION_RE.fullmatch(desc) and len(desc) <= cc.DESCRIPTION_MAX):
        print(f"{row['id']}: needs a description (opts desc), got {desc!r}")
        desc = "TODO"
    title = row["title"]
    col = {"id": row["id"], "title_src": L(h), "ledger": ledger, "description": desc, "label_case": "title"}
    used = set()
    for nd in nodes.values():
        for f in ("text",):
            for m in PH_RE.finditer(nd.get(f, "")):
                tok = m.group(1).split(".")[0].lower()
                used.add(ROLE_OF.get(tok, tok))
        for c in nd.get("choices", []):
            for m in PH_RE.finditer(c["label"]):
                tok = m.group(1).split(".")[0].lower()
                used.add(ROLE_OF.get(tok, tok))
        for e in nd.get("effects", []):
            used.add(e.get("role"))
    for m in PH_RE.finditer(title):
        tok = m.group(1).split(".")[0].lower()
        used.add(ROLE_OF.get(tok, tok))
    cast_only = [r for r in roles if r not in used]
    if cast_only:
        col["cast_only"] = cast_only
    doc = {"format": "vvfp-cie-graph", "version": 6, "title": title, "games": opts.get("games", row["games"]),
           "collection": col, "requirement": {"min_eligible": sum(1 for r in roles.values()
                                                                   if r.get("kind") == "villager")},
           "roles": roles, "start": "setup", "nodes": nodes}
    if fixes:
        doc["grammar_fixes"] = [{"src": L(n), "before": b, "after": a} for n, b, a in fixes]
    if opts.get("chief"):
        doc["words"] = {"chief": {"3": "chief", "*": "leader"}}
    return doc, pron.log


def pron_report(row: dict, doc: dict) -> str:
    """The event's pages with each pronoun's role shown, for review."""
    out = [f"== {row['id']}  {row['title']}  roles={json.dumps(doc['roles'])}"]
    for k, nd in doc["nodes"].items():
        if "text" in nd:
            out.append(f"  [{k}] {nd['text']}")
        for c in nd.get("choices", []):
            out.append(f"  <{c['next']}> {c['label']}")
    return "\n".join(out)


def main(source: str, table: dict) -> int:
    """A generator's command line: [--review <folder>] writes the pronoun review there."""
    review = sys.argv[sys.argv.index("--review") + 1] if "--review" in sys.argv else None
    return run(source, table, review)


def run(source: str, table: dict, review: str | None = None) -> int:
    """Write every event of `source` (table: {number: opts}) and check them."""
    with lib.use_source(source):
        paths = []
        reports = []
        for r in rows(source):
            doc, _log = build(r, table.get(num_of(r), {}))
            p = lib.DRAFTS_A_DIR / source / f"{r['id']}.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(cc.canonical(doc), encoding="utf-8", newline="\n")
            paths.append(str(p))
            reports.append(pron_report(r, doc))
    if review:
        out = Path(review) / f"{source}.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n\n".join(reports) + "\n", encoding="utf-8", newline="\n")
        print(f"review: {out}")
    return subprocess.call([sys.executable, str(ROOT / "scripts" / "collection_check.py"), "--format", *paths])
