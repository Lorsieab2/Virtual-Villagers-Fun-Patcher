"""Check Isola Grand Event Collection files (design E4 a-h) against the frozen source and the v6 format.

    python scripts/collection_check.py                  # every data/event_collection/<section>/<id>.json
    python scripts/collection_check.py FILE [FILE ...]  # just these
    python scripts/collection_check.py --report FILE    # also print the ledger summary (owner packet material)

The checks (each problem names its check):
  a SCHEMA    vv_cie_graph.normalize / validate for every game listed (needs the v6 format: ENGINE SEAM below)
  b FIDELITY  every text with a "src" tag is the source's text, word for word, apart from: the authoring table
              (collection_lib.NORMALIZE), structural markers (collection_lib.STRUCTURAL_INLINE), text the ledger takes
              out (designer notes, instructions), the event's grammar_fixes (each listed in
              docs/event-collection/grammar-fixes.md), and tokens: a placeholder "(...)" or a pool "{P}" stands for
              one source parenthesis group, an inline pick "{a|b|c}" for the source's "(a/b/c)", a game word
              "{@w}" for one of its words, "\\(" "\\)" for literal parentheses
  c COVERAGE  every line of the event's source lines is consumed by a src or a ledger entry, and every word on a
              line a text consumes is matched by some text or taken out by the ledger: zero unconsumed
  d TOKENS    pools defined and non-empty; bank sizes equal the manifest's; roles referenced and declared;
              pronouns role-prefixed when the event has two or more roles; "Chief" only where the text can show
              only in VV3; never "GLORIOUSLY OFFENSIVE"; only the v6 characters
  e EFFECTS   the effects keyword table over each node's source lines: each hit is an effect of that kind on the
              node or a text_only entry with a reason; food / tech by size words (design A3), skills by the skill
              size table, skill names that exist in the event's games
  f SAFETY    the harm-capable roles (derived here independently of the compiler) never allow protected villagers
              and are never special roles; VV5 roles are believers only
  g ROUND     normalize -> compile -> decompile -> normalize gives the graph back; compile is deterministic (needs
              the v6 format: ENGINE SEAM)
  h CHANCES   every node reachable; a split's weights equal unless a rarity word gives them (rare 1/4, very rare
              1/10, exceptionally rare 1/20 of a normal outcome: weights 20 / 5 / 2 / 1)

ENGINE SEAM.  Track A owns src/vv_cie_graph.py and its v6 format.  graph_for_engine() takes the authoring-only keys
out of a collection file ("src", node "text_only" and "set", child / item "rarity", collection "ledger",
"title_src", "inline_sets") and hands the rest to vv_cie_graph.  Until vv_cie_graph reads version 6,
checks a and g are reported SKIPPED (never passed silently).
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collection_lib as lib  # noqa: E402

sys.path.insert(0, str(lib.ROOT / "src"))

# ---- Constants the authoring rules name ---------------------------------------------------------------------------

RARITY_WEIGHTS = {None: 20, "rare": 5, "very_rare": 2, "exceptionally_rare": 1}
SIZES = ("small", "normal", "large", "huge")
# Skill amounts (design A3 "experience" = normal, "a little / small" = small; rule 10 doubles and triples for the
# larger words).  A loss is the same range, negative.  "masters" is {"set": 100}.
SKILL_SIZES = {"small": (5, 10), "normal": (10, 20), "large": (20, 40), "huge": (30, 60)}
ALL_SKILLS = {1: ("Parenting", "Building", "Farming", "Healing", "Research"),
              2: ("Parenting", "Building", "Farming", "Healing", "Research"),
              3: ("Farming", "Parenting", "Healing", "Research", "Building"),
              4: ("Farming", "Parenting", "Healing", "Research", "Building"),
              5: ("Farming", "Parenting", "Healing", "Research", "Building", "Devotion")}
SPECIALS = ("golden_child", "tribal_chief", "nursing_parent")
SECTIONS = ("original", "universal", "vv5_isolan", "v6", "v8", "v9", "v10", "v11", "v13", "v14", "exclusive", "v17",
            "v18", "v20", "v21", "v22", "v23", "v24", "v26")
LEDGER_KINDS = ("structural", "note", "instruction", "bank_ref", "gap")
AUTHORING_TOP = ("ledger", "title_src", "inline_sets", "shared_lines")

# The effects keyword table (design E4e): source words that promise a change -> the effect kinds that keep it.
KEYWORDS = [
    (re.compile(r"\bfood\b(?! (?:stall|safety))", re.I), {"food"}),
    (re.compile(r"\btech(?:nology)?\b(?! (?:points?)? ?if)|\btech points\b", re.I), {"tech"}),
    (re.compile(r"\bexperience\b|\bskill\b", re.I), {"skill"}),
    (re.compile(r"\bdies\b|\bdeath\b|\bdie\b", re.I), {"kill"}),
    (re.compile(r"\bdisappears?\b|\bvanish\w*|\bflees\b", re.I), {"vanish"}),
    (re.compile(r"\bcelebrat\w*", re.I), {"celebrate"}),
    (re.compile(r"\bdislik\w*", re.I), {"preference"}),
    (re.compile(r"\binjur\w*|\blose health\b|\bhealth\b", re.I), {"health", "health_change"}),
    (re.compile(r"\bcollaps\w*", re.I), {"damage"}),
]
EFFECT_KIND = {"skill": "skill", "food": "food", "tech": "tech", "kill": "kill", "vanish": "vanish",
               "celebrate": "celebrate", "preference": "preference", "health": "health",
               "health_change": "health_change", "damage": "damage", "sick": "health", "mood": "mood",
               "action": "action", "status": "status", "pay_award": "food"}

PRONOUN_WORDS = {"he/she", "his/her", "him/her", "man/woman", "himself/herself", "woman/man", "boy/girl",
                 "son/daughter"}
NAME_WORDS = {"name", "name1", "name2"}
ALLOWED_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,!?:-'\"\n;/&%")

PH_RE = r"\((?:[^()]|\([^()]*\))*\)"         # one source parenthesis group (two levels deep)


# ---- Problems ------------------------------------------------------------------------------------------------------


@dataclass
class Report:
    path: str
    problems: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def add(self, check: str, msg: str) -> None:
        self.problems.append(f"{check}: {msg}")

    @property
    def ok(self) -> bool:
        return not self.problems


# ---- Engine seam ---------------------------------------------------------------------------------------------------


def engine():
    """vv_cie_graph when it reads version 6, else None."""
    try:
        import vv_cie_graph as cg
    except Exception:  # pragma: no cover - a broken src tree is reported by its own tests
        return None
    return cg if 6 in getattr(cg, "VERSIONS", ()) else None


def graph_for_engine(doc: dict) -> dict:
    """The collection file without its authoring-only keys: what vv_cie_graph (v6) reads."""
    g = copy.deepcopy(doc)

    def scrub(x):
        if isinstance(x, dict):
            for k in ("src", "rarity"):
                x.pop(k, None)
            for v in x.values():
                scrub(v)
        elif isinstance(x, list):
            for v in x:
                scrub(v)
    for n in g.get("nodes", {}).values():
        n.pop("text_only", None)
        n.pop("set", None)
        n.pop("src_pick", None)
    for p in g.get("pools", {}).values():
        p.pop("set", None)
        p.pop("mirror_of", None)
        p["items"] = [i["text"] if isinstance(i, dict) and set(i) <= {"text", "src"} else i for i in p["items"]]
    for k in AUTHORING_TOP:
        g.get("collection", {}).pop(k, None)
    scrub(g)
    return g


# ---- Text fields ---------------------------------------------------------------------------------------------------


@dataclass
class Field:
    where: str
    text: str
    src: str | None
    node: str | None = None
    kind: str = "text"          # text | label | item | variant | title
    picks: list = field(default_factory=list)   # the node's src_pick: [{"src": "L592", "alt": "..."}]


def text_fields(doc: dict) -> list[Field]:
    out: list[Field] = []
    col = doc.get("collection", {})
    out.append(Field("title", doc.get("title", ""), col.get("title_src"), kind="title"))
    for nid, n in doc.get("nodes", {}).items():
        if n.get("text"):
            out.append(Field(f"node {nid}", n["text"], n.get("src"), nid, picks=n.get("src_pick", []) or []))
        for i, v in enumerate(n.get("variants", []) or []):
            out.append(Field(f"node {nid} variant {i + 1}", v.get("text", ""), v.get("src"), nid, "variant"))
        for i, c in enumerate(n.get("choices", []) or []):
            out.append(Field(f"node {nid} choice {i + 1}", c.get("label", ""), c.get("src"), nid, "label"))
    for pname, p in doc.get("pools", {}).items():
        for i, it in enumerate(p.get("items", [])):
            if isinstance(it, dict):
                out.append(Field(f"pool {pname} item {i + 1}", it.get("text", ""), it.get("src"), kind="item"))
            else:
                out.append(Field(f"pool {pname} item {i + 1}", it, None, kind="item"))
    return out


# ---- Token scanning ------------------------------------------------------------------------------------------------


def scan(text: str):
    """Split display text into ('lit', s) / ('ph', inner) / ('brace', inner) / ('esc', '(' or ')') pieces."""
    out, i, buf = [], 0, ""
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text) and text[i + 1] in "()":
            if buf:
                out.append(("lit", buf))
                buf = ""
            out.append(("esc", text[i + 1]))
            i += 2
        elif ch == "(":
            j = text.find(")", i)
            if j < 0:
                buf += text[i:]
                break
            if buf:
                out.append(("lit", buf))
                buf = ""
            out.append(("ph", text[i + 1:j]))
            i = j + 1
        elif ch == "{":
            depth, j = 0, i
            while j < len(text):
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            if buf:
                out.append(("lit", buf))
                buf = ""
            out.append(("brace", text[i + 1:j]))
            i = j + 1
        else:
            buf += ch
            i += 1
    if buf:
        out.append(("lit", buf))
    return out


def split_alts(inner: str) -> list[str]:
    parts, depth, cur = [], 0, ""
    for ch in inner:
        if ch in "{(":
            depth += 1
        elif ch in "})":
            depth -= 1
        if ch == "|" and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return [re.sub(r"^\d+:", "", p) for p in parts]


def is_pool_ref(inner: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\.\d)?", inner))


def text_regex(text: str, words: dict, top: bool = True, pools: dict | None = None) -> str:
    """A regex the normalised source must contain for this display text to be faithful."""
    parts = []
    for kind, s in scan(text):
        if kind == "lit":
            toks = re.split(r"(\s+)", s)
            for t in toks:
                if not t:
                    continue
                parts.append(r"\s+" if t.isspace() else re.escape(t))
        elif kind == "esc":
            parts.append(re.escape(s))
        elif kind == "ph":
            parts.append(PH_RE)
        elif kind == "brace":
            if s.startswith("@"):
                # the source has one of the word's own values, or (the mapping rule) the Chief it replaces
                vals = sorted({v for v in words.get(s[1:], {}).values()}, key=len, reverse=True)
                alts = [re.escape(v) for v in vals] + [r"(?:[Tt]he |[Aa] )?Chiefs?"]
                parts.append("(?:" + "|".join(alts) + ")" if vals else r"(?!x)x")
            elif is_pool_ref(s):
                # one source parenthesis group, or the pool's own items as the source's bare "a/b/c" list
                items = (pools or {}).get(s.split(".")[0], [])
                bare = r"\s*/\s*".join(re.escape(i) for i in items)
                parts.append(f"(?:{PH_RE}|{bare})" if len(items) > 1 else PH_RE)
            else:
                alts = [text_regex(a, words, False, pools) for a in split_alts(s)]
                parts.append(r"\(?" + r"\s*/\s*".join(alts) + r"\)?")
    rx = "".join(parts)
    if top:
        m = re.match(r"([A-Za-z])", text)
        if m:   # the first letter's case is free (a list item that starts a sentence, or the reverse)
            rx = f"[{m.group(1).upper()}{m.group(1).lower()}]" + rx[1:]
    return rx


# ---- Source spans --------------------------------------------------------------------------------------------------


@dataclass
class Span:
    text: str
    starts: list[tuple[int, int]]   # (offset in text, line number)
    maps: dict = field(default_factory=dict)   # line -> [processed-line index of each character] where a pick applies


def apply_pick(p: str, alt: str) -> tuple[str, list[int]] | None:
    """`p` with the slash group "(... / alt / ...)" that holds `alt` as one whole alternative replaced by `alt` alone
    (a node that fixes one option of the source's list, e.g. to route by it), and the index map back into `p`."""
    stack = []
    for i, ch in enumerate(p):
        if ch == "(":
            stack.append(i)
        elif ch == ")" and stack:
            gs = stack.pop()
            inner = p[gs + 1:i]
            depth, start, alts = 0, 0, []
            for j, c in enumerate(inner):
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                elif c == "/" and depth == 0:
                    alts.append((start, j))
                    start = j + 1
            alts.append((start, len(inner)))
            if len(alts) < 2:
                continue
            for a, b in alts:
                if inner[a:b].strip() == alt:
                    lo = gs + 1 + a + (len(inner[a:b]) - len(inner[a:b].lstrip()))
                    hi = lo + len(alt)
                    text = p[:gs] + p[lo:hi] + p[i + 1:]
                    return text, list(range(gs)) + list(range(lo, hi)) + list(range(i + 1, len(p)))
    return None


def processed_line(n: int, ledger_cuts: dict[int, list[str]], fixes: dict[int, list[tuple[str, str]]]) -> str:
    s = lib.normalize_source_text(lib.line(n))
    for before, after in fixes.get(n, []):
        s = s.replace(before, after)
    for cut in ledger_cuts.get(n, []):
        s = s.replace(cut, "\x00")
    s = re.sub(r"\s*\x00\s*(?=[.,;:!?])", "", s).replace("\x00", " ")   # a cut before a full stop leaves none
    s = lib.strip_structural(s)
    return re.sub(r"\s+", " ", s).strip()


def build_span(lines: list[int], cuts, fixes, picks: dict[int, list[str]] | None = None,
               problems: list[str] | None = None) -> Span:
    text, starts, maps = "", [], {}
    for n in lines:
        p = processed_line(n, cuts, fixes)
        if not p:
            continue
        for alt in (picks or {}).get(n, []):
            got = apply_pick(p, alt)
            if got is None:
                if problems is not None:
                    problems.append(f"src_pick {alt!r} is not one alternative of a \"(a/b/c)\" list on L{n}")
                continue
            prev = maps.get(n)
            p, m = got
            maps[n] = [prev[k] for k in m] if prev else m
        if text:
            text += " "
        starts.append((len(text), n))
        text += p
    return Span(text, starts, maps)


def span_lines(span: Span, a: int, b: int) -> dict[int, tuple[int, int]]:
    """{line: (start, end) within that line's processed text} for the match a..b."""
    out = {}
    bounds = span.starts + [(len(span.text) + 1, None)]
    for (off, n), (nxt, _) in zip(bounds, bounds[1:]):
        end = nxt - 1
        lo, hi = max(a, off), min(b, end)
        if lo < hi:
            out[n] = (lo - off, hi - off)
    return out


# ---- The checks ----------------------------------------------------------------------------------------------------


def manifest_rows() -> dict[str, dict]:
    if not lib.MANIFEST.exists():
        return {}
    return {r["id"]: r for r in json.loads(lib.MANIFEST.read_text(encoding="utf-8"))["rows"]}


def grammar_doc_fixes() -> set[tuple[int, str, str]]:
    """(line, before, after) of every fix in docs/event-collection/grammar-fixes.md (table rows
    "| L104 | `before` | `after` | ... |")."""
    out = set()
    if not lib.GRAMMAR_FIXES_DOC.exists():
        return out
    for row in lib.GRAMMAR_FIXES_DOC.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*L(\d+)\s*\|\s*`(.*?)`\s*\|\s*`(.*?)`\s*\|", row)
        if m:
            out.add((int(m.group(1)), m.group(2), m.group(3)))
    return out


def shared_pools() -> dict:
    if lib.SHARED_POOLS.exists():
        return json.loads(lib.SHARED_POOLS.read_text(encoding="utf-8")).get("pools", {})
    return {}


def ledger_maps(doc: dict, rep: Report):
    col = doc.get("collection", {})
    cuts: dict[int, list[str]] = {}
    whole: set[int] = set()
    for i, e in enumerate(col.get("ledger", []) or []):
        where = f"ledger entry {i + 1}"
        if not isinstance(e, dict) or e.get("kind") not in LEDGER_KINDS or "src" not in e:
            rep.add("c COVERAGE", f"{where}: needs src and a kind ({', '.join(LEDGER_KINDS)})")
            continue
        try:
            lines = lib.src_lines(e["src"])
        except ValueError as ex:
            rep.add("c COVERAGE", f"{where}: {ex}")
            continue
        if e.get("text"):
            if len(lines) != 1:
                rep.add("c COVERAGE", f"{where}: a text cut names one line")
                continue
            if e["text"] not in lib.normalize_source_text(lib.line(lines[0])):
                rep.add("c COVERAGE", f"{where}: {e['text']!r} is not on L{lines[0]}")
            cuts.setdefault(lines[0], []).append(e["text"])
        else:
            whole.update(lines)
        if e["kind"] in ("note", "instruction") and not e.get("why") and e["kind"] == "note":
            pass
    fixes: dict[int, list[tuple[str, str]]] = {}
    doc_fixes = grammar_doc_fixes()
    for i, f in enumerate(doc.get("grammar_fixes", []) or []):
        where = f"grammar fix {i + 1}"
        try:
            (n,) = lib.src_lines(f["src"])
        except (ValueError, KeyError, TypeError):
            rep.add("b FIDELITY", f"{where}: src names one line")
            continue
        before, after = f.get("before", ""), f.get("after", "")
        if before not in lib.normalize_source_text(lib.line(n)):
            rep.add("b FIDELITY", f"{where}: {before!r} is not on L{n}")
        if (n, before, after) not in doc_fixes:
            rep.add("b FIDELITY", f"{where}: L{n} {before!r} -> {after!r} is not in docs/event-collection/"
                                  "grammar-fixes.md")
        fixes.setdefault(n, []).append((before, after))
    return cuts, whole, fixes


def check_fidelity_and_coverage(doc: dict, row: dict | None, rep: Report) -> None:
    cuts, whole, fixes = ledger_maps(doc, rep)
    words = doc.get("words", {}) or {}
    pool_texts = {name: [i["text"] if isinstance(i, dict) else i for i in p.get("items", [])]
                  for name, p in (doc.get("pools", {}) or {}).items()}
    consumed: set[int] = set(whole)
    matched: dict[int, list[tuple[int, int]]] = {}
    text_lines: set[int] = set()
    for f in text_fields(doc):
        if f.kind == "title":
            if f.src:
                try:
                    lines = lib.src_lines(f.src)
                except ValueError as ex:
                    rep.add("b FIDELITY", f"title: {ex}")
                    continue
                consumed.update(lines)
                head = " ".join(lib.normalize_source_text(lib.line(n)) for n in lines).lower()
                if re.sub(r"[^a-z0-9]+", " ", f.text.lower()).strip() not in re.sub(r"[^a-z0-9]+", " ", head):
                    rep.add("b FIDELITY", f"title {f.text!r} is not the heading on {f.src}")
            else:
                rep.add("b FIDELITY", "title has no collection.title_src")
            continue
        if not f.src:
            literal = "".join(s for k, s in scan(f.text) if k in ("lit", "esc"))
            if literal.strip():   # a text of tokens only ("{END}") carries no source words of its own
                rep.add("b FIDELITY", f"{f.where}: no src tag")
            continue
        try:
            lines = lib.src_lines(f.src)
        except ValueError as ex:
            rep.add("b FIDELITY", f"{f.where}: {ex}")
            continue
        consumed.update(lines)
        text_lines.update(lines)
        picks: dict[int, list[str]] = {}
        for pk in f.picks:
            try:
                (pn,) = lib.src_lines(pk["src"])
                picks.setdefault(pn, []).append(pk["alt"])
            except (ValueError, KeyError, TypeError):
                rep.add("b FIDELITY", f"{f.where}: a src_pick is {{\"src\": one line, \"alt\": one alternative}}")
        pick_problems: list[str] = []
        span = build_span(lines, cuts, fixes, picks, pick_problems)
        for x in pick_problems:
            rep.add("b FIDELITY", f"{f.where}: {x}")
        for para in [p for p in f.text.split("\n") if p.strip()]:
            if not "".join(s for k, s in scan(para) if k in ("lit", "esc")).strip():
                continue   # a paragraph of tokens only ("{WRONG}"): its items carry their own src
            rx = text_regex(para.strip(), words, pools=pool_texts)
            m = re.search(rx, span.text)
            if not m:
                rep.add("b FIDELITY", f"{f.where} ({f.src}): {para.strip()[:90]!r} is not the source text "
                                      f"{span.text[:160]!r}")
                continue
            for n, (a, b) in span_lines(span, m.start(), m.end()).items():
                mp = span.maps.get(n)
                idx = {mp[k] for k in range(a, min(b, len(mp)))} if mp else set(range(a, b))
                matched.setdefault(n, set()).update(idx)
    for e in doc.get("collection", {}).get("ledger", []) or []:
        if isinstance(e, dict) and e.get("text"):
            try:
                consumed.update(lib.src_lines(e["src"]))
            except ValueError:
                pass
    if row is None:
        rep.add("c COVERAGE", "no manifest row for collection.id")
        return
    a, b = row["lines"]
    # A line that is nothing but structural markers ("Go to (3).") needs no ledger entry.
    missing = [n for n in range(a, b + 1) if n not in consumed and not lib.is_blank_or_separator(n)
               and processed_line(n, cuts, fixes)]
    if missing:
        rep.add("c COVERAGE", f"{len(missing)} source lines consumed by nothing: {compress(missing)}")
    # Lines outside the event's own: only a section's shared text (a festival's setting paragraph that each of its
    # contests opens with), named in collection.shared_lines and belonging to a notes row of the manifest.
    shared: set[int] = set()
    for spec in doc.get("collection", {}).get("shared_lines", []) or []:
        try:
            shared.update(lib.src_lines(spec))
        except ValueError as ex:
            rep.add("c COVERAGE", f"shared_lines: {ex}")
    notes_lines = {n for r in manifest_rows().values() if r["kind"] == "notes"
                   for n in range(r["lines"][0], r["lines"][1] + 1)}
    if shared - notes_lines:
        rep.add("c COVERAGE", f"shared_lines outside a notes section: {compress(sorted(shared - notes_lines))}")
    stray = sorted(n for n in consumed if not a <= n <= b and n not in shared)
    if stray:
        rep.add("c COVERAGE", f"src outside the event's lines {a}-{b}: {compress(stray)}")
    for n in sorted(text_lines - whole):
        p = processed_line(n, cuts, fixes)
        mask = [False] * len(p)
        for k in matched.get(n, set()):
            if k < len(p):
                mask[k] = True
        left = [w.group(0) for w in lib.WORD_RE.finditer(p) if not all(mask[w.start():w.end()])]
        left = [w for w in left if not re.fullmatch(r"[A-Z]\d*", w)]
        if left:
            rep.add("c COVERAGE", f"L{n}: words no text consumes: {' '.join(left)[:120]!r}")


def compress(ns: list[int]) -> str:
    out, run = [], None
    for n in ns:
        if run and n == run[1] + 1:
            run[1] = n
        else:
            if run:
                out.append(lib.fmt_src(*run))
            run = [n, n]
    if run:
        out.append(lib.fmt_src(*run))
    return ", ".join(out)


def placeholders_in(text: str):
    for kind, s in scan(text):
        if kind == "ph":
            yield s
        elif kind == "brace" and not s.startswith("@") and not is_pool_ref(s):
            for alt in split_alts(s):
                yield from placeholders_in(alt)


def braces_in(text: str):
    for kind, s in scan(text):
        if kind == "brace":
            yield s
            if not s.startswith("@") and not is_pool_ref(s):
                for alt in split_alts(s):
                    yield from braces_in(alt)


def check_tokens(doc: dict, row: dict | None, rep: Report) -> None:
    roles = doc.get("roles", {}) or {}
    ids = {r.lower(): r for r in roles}
    pools = dict(doc.get("pools", {}) or {})
    shared = shared_pools()
    for name in doc.get("include_pools", []) or []:
        if name not in shared:
            rep.add("d TOKENS", f"include_pools {name!r} is not in shared_pools.json")
        else:
            pools[name] = shared[name]
    words = doc.get("words", {}) or {}
    used_roles: set[str] = set()
    games = set(doc.get("games", []))
    multi = len(roles) >= 2 or "subject" not in roles
    for f in text_fields(doc):
        if f.kind == "title":
            continue
        t = f.text
        for inner in placeholders_in(t):
            if "." in inner:
                r, w = inner.split(".", 1)
                if r.lower() not in ids:
                    rep.add("d TOKENS", f"{f.where}: ({inner}) names no role")
                else:
                    used_roles.add(ids[r.lower()])
                if w.lower() not in PRONOUN_WORDS | {"name"}:
                    rep.add("d TOKENS", f"{f.where}: ({inner}) is not a role word")
            elif inner.lower() in ids:
                used_roles.add(ids[inner.lower()])
            elif inner.lower() in PRONOUN_WORDS or inner.lower() in NAME_WORDS:
                if multi:
                    rep.add("d TOKENS", f"{f.where}: ({inner}) is not role-prefixed (the event has "
                                        f"{len(roles)} roles)")
                else:
                    used_roles.add("subject")
            elif inner in ("award", "award_unit"):
                pass
            else:
                rep.add("d TOKENS", f"{f.where}: ({inner}) is not a placeholder (a literal parenthesis is \\( \\))")
        for inner in braces_in(t):
            if inner.startswith("@"):
                if inner[1:] not in words:
                    rep.add("d TOKENS", f"{f.where}: game word {{{inner}}} is not in words")
            elif is_pool_ref(inner):
                p = pools.get(inner.split(".")[0])
                if not p or not p.get("items"):
                    rep.add("d TOKENS", f"{f.where}: pool {{{inner}}} is not defined or is empty")
        bare = "".join(s for k, s in scan(t) if k == "lit")
        bad = sorted({c for c in bare if c not in ALLOWED_CHARS})
        if bad:
            rep.add("d TOKENS", f"{f.where}: characters a v6 text may not hold: {''.join(bad)!r}")
        if "gloriously offensive" in t.lower():
            rep.add("d TOKENS", f"{f.where}: 'GLORIOUSLY OFFENSIVE' must never reach the game")
        if re.search(r"\bChiefs?\b", bare) and (games - {3}) and not vv3_only(doc, f):
            rep.add("d TOKENS", f"{f.where}: 'Chief' in text a VV1/VV2/VV4/VV5 game can show (use {{@chief}})")
    for w, vals in words.items():
        v3 = vals.get("3")
        for g, v in vals.items():
            if v3 and g != "3" and v3.split()[-1].endswith("s") != v.split()[-1].endswith("s"):
                rep.add("d TOKENS", f"words {w}: {v3!r} and {v!r} differ in number (verb agreement)")
    for n in doc.get("nodes", {}).values():
        for e in n.get("effects", []) or []:
            if e.get("role") and e["role"] not in roles:
                rep.add("d TOKENS", f"effect role {e['role']!r} is not declared")
            elif e.get("role"):
                used_roles.add(e["role"])
            if e.get("who") and e["who"] != "all":
                used_roles.add(e["who"])
        for c in n.get("choices", []) or []:
            collect_cond_roles(c.get("if"), used_roles)
        for c in n.get("children", []) or []:
            collect_cond_roles(c.get("if"), used_roles)
    # an included shared pool's items (a coda's "(coda1.he/she)", "(Name1)") use the event's roles too
    for name in doc.get("include_pools", []) or []:
        for it in (shared.get(name) or {}).get("items", []):
            for inner in placeholders_in(it.get("text", "") if isinstance(it, dict) else it):
                r = inner.split(".", 1)[0] if "." in inner else inner
                if r.lower() in ids:
                    used_roles.add(ids[r.lower()])
                elif "." in inner:
                    rep.add("d TOKENS", f"shared pool {name}: ({inner}) names no role of this event")
    for rid, r in roles.items():
        for m in r.get("of", []) or []:
            used_roles.add(m)
            if m not in roles:
                rep.add("d TOKENS", f"role {rid}: alias member {m!r} is not declared")
    for rid in roles:
        if rid not in used_roles and not roles[rid].get("special"):   # casting a special villager is the need
            rep.add("d TOKENS", f"role {rid} is declared but never used")
    # bank sizes against the manifest
    if row is not None:
        have: dict[str, int] = {}
        for pname, p in (doc.get("pools", {}) or {}).items():
            if p.get("mirror_of"):
                # the same bank with its pronouns on the other role (a gap until pool items can follow the role
                # of the instance): same items, same lines, counted once
                orig = (doc.get("pools") or {}).get(p["mirror_of"])
                if orig is None:
                    rep.add("d TOKENS", f"pool {pname}: mirror_of {p['mirror_of']!r} is not a pool")
                    continue
                a = [i.get("src") if isinstance(i, dict) else None for i in orig.get("items", [])]
                b = [i.get("src") if isinstance(i, dict) else None for i in p.get("items", [])]
                if a != b:
                    rep.add("d TOKENS", f"pool {pname}: a mirror has the same items (src) as {p['mirror_of']}")
                continue
            if p.get("set"):
                have[p["set"]] = have.get(p["set"], 0) + len(p.get("items", []))
        for nid, n in doc.get("nodes", {}).items():
            if n.get("set"):
                have[n["set"]] = have.get(n["set"], 0) + len({c["next"] for c in n.get("children", []) or []})
        for e in doc.get("collection", {}).get("ledger", []) or []:
            # a bank item the format cannot express yet: listed (kind gap) so the count still matches the source
            if isinstance(e, dict) and e.get("kind") == "gap" and e.get("set"):
                have[e["set"]] = have.get(e["set"], 0) + 1
        inline = set(doc.get("collection", {}).get("inline_sets", []) or [])
        for label, size in row.get("pools", {}).items():
            if label in have:
                if have[label] != size:
                    rep.add("d TOKENS", f"bank {label}: {have[label]} items, the manifest (source) says {size}")
            elif label not in inline:
                rep.add("d TOKENS", f"bank {label} ({size} in the source) is in no pool or branch \"set\" "
                                    "(and not listed in collection.inline_sets)")
        for label in have:
            if label not in row.get("pools", {}):
                rep.add("d TOKENS", f"set {label!r} is not a bank of the manifest row")


def collect_cond_roles(c, out: set) -> None:
    if isinstance(c, dict):
        for k, v in c.items():
            if k in ("role", "harmable") and isinstance(v, str):
                out.add(v)
            else:
                collect_cond_roles(v, out)
    elif isinstance(c, list):
        for v in c:
            collect_cond_roles(v, out)


def vv3_only(doc: dict, f: Field) -> bool:
    """A field only ever shown in VV3: a variant whose if is {"game": 3} or {"game": [3]}."""
    if f.kind != "variant":
        return False
    node = doc["nodes"][f.node]
    i = int(f.where.rsplit(" ", 1)[1]) - 1
    g = (node.get("variants") or [])[i].get("if", {}).get("game")
    return g == 3 or g == [3]


def node_source_lines(n: dict) -> set[int]:
    out = set()
    for spec in [n.get("src")] + [e.get("src") for e in n.get("effects", []) or []] + \
            [t.get("src") for t in n.get("text_only", []) or []]:
        if spec:
            try:
                out.update(lib.src_lines(spec))
            except ValueError:
                pass
    return out


def check_effects(doc: dict, rep: Report) -> None:
    games = doc.get("games", [])
    cuts_whole = {}
    for nid, n in doc.get("nodes", {}).items():
        effs = n.get("effects", []) or []
        kinds = {EFFECT_KIND.get(e.get("do"), e.get("do")) for e in effs}
        covered = set()
        for t in n.get("text_only", []) or []:
            if not t.get("reason") or not t.get("src"):
                rep.add("e EFFECTS", f"node {nid}: a text_only entry needs src and reason")
                continue
            try:
                covered.update(lib.src_lines(t["src"]))
            except ValueError as ex:
                rep.add("e EFFECTS", f"node {nid}: {ex}")
        for ln in sorted(node_source_lines(n)):
            s = lib.normalize_source_text(lib.line(ln))
            for rx, want in KEYWORDS:
                m = rx.search(s)
                if m and not (kinds & want) and ln not in covered:
                    rep.add("e EFFECTS", f"node {nid}: L{ln} says {m.group(0)!r} but the node has no "
                                         f"{'/'.join(sorted(want))} effect and no text_only reason for that line")
        for i, e in enumerate(effs):
            where = f"node {nid} effect {i + 1}"
            do = e.get("do")
            if do in ("food", "tech"):
                if e.get("size") not in SIZES or "amount" in e or "per_game" in e:
                    rep.add("e EFFECTS", f"{where}: food / tech give a size word ({', '.join(SIZES)}), never "
                                         "an amount (design A3)")
                if e.get("scaled") is not True:
                    rep.add("e EFFECTS", f"{where}: food / tech are scaled (design A3)")
            elif do == "skill":
                names = e.get("skills") or []
                if not names:
                    rep.add("e EFFECTS", f"{where}: a skill effect names its skills")
                for g in games:
                    if not any(s in ALL_SKILLS[g] for s in names):
                        rep.add("e EFFECTS", f"{where}: none of {names} exists in VV{g}")
                if "set" in e:
                    if e["set"] != 100:
                        rep.add("e EFFECTS", f"{where}: set is 100 ('masters') only")
                else:
                    pair = (abs(e.get("min", 0)), abs(e.get("max", 0)))
                    sign = e.get("min", 0) < 0
                    if sorted(pair) not in [list(v) for v in SKILL_SIZES.values()] or \
                            (sign and not e.get("max", 0) < 0):
                        rep.add("e EFFECTS", f"{where}: skill +-{pair} is not a size of the skill table "
                                             f"{SKILL_SIZES}")
            elif do == "kill" and not e.get("cause"):
                rep.add("e EFFECTS", f"{where}: a kill names its cause")
    _ = cuts_whole


HARMFUL = {"kill", "vanish", "sick"}


def harmful(e: dict) -> bool:
    do = e.get("do")
    if do in HARMFUL:
        return True
    if do == "health" and e.get("max", e.get("value", 100)) < 100:
        return True
    if do == "health_change" and e.get("min", 0) < 0:
        return True
    if do == "preference" and e.get("list") == "dislikes":
        return True
    if do == "skill" and "set" not in e and (e.get("min", 0) < 0 or e.get("max", 0) < 0):
        return True
    if do == "mood" and e.get("mood") == "bad":
        return True
    return False


def harm_roles(doc: dict) -> set[str]:
    """The roles a harmful effect can reach, derived here independently of the compiler."""
    roles = doc.get("roles", {}) or {}
    harm: set[str] = set()
    for n in doc.get("nodes", {}).values():
        for e in n.get("effects", []) or []:
            if harmful(e) and e.get("role"):
                harm.add(e["role"])
                harm.update(roles.get(e["role"], {}).get("of", []) or [])
    return harm


def check_safety(doc: dict, rep: Report) -> None:
    roles = doc.get("roles", {}) or {}
    harm = harm_roles(doc)
    for n in doc.get("nodes", {}).values():
        for e in n.get("effects", []) or []:
            if e.get("do") == "celebrate" and e.get("who") not in (None, "all") and e["who"] not in roles:
                rep.add("f SAFETY", f"celebrate names an unknown role {e['who']!r}")
    for rid, r in roles.items():
        if rid in harm:
            if r.get("protected") == "allow":
                rep.add("f SAFETY", f"role {rid}: can be harmed, so protected villagers can never be allowed")
            if r.get("special"):
                rep.add("f SAFETY", f"role {rid}: a special villager ({r['special']}) is never harmed")
            if r.get("kind") == "stranger":
                rep.add("f SAFETY", f"role {rid}: a stranger cannot take a villager effect")
        if r.get("special") and r["special"] not in SPECIALS:
            rep.add("f SAFETY", f"role {rid}: special is one of {SPECIALS}")
        if 5 in doc.get("games", []) and r.get("kind", "villager") == "villager" and r.get("believers_only") is False:
            rep.add("f SAFETY", f"role {rid}: New Believers' Heathens are never cast (believers_only)")
    rep.notes.append(f"harm-capable roles: {', '.join(sorted(harm)) or 'none'}")


def check_chances(doc: dict, rep: Report) -> None:
    nodes = doc.get("nodes", {}) or {}
    start = doc.get("start")
    seen, todo = set(), [start]
    while todo:
        x = todo.pop()
        if x in seen or x not in nodes:
            if x not in nodes:
                rep.add("h CHANCES", f"{x!r} is named but is not a node")
            continue
        seen.add(x)
        n = nodes[x]
        for c in (n.get("children") or []) + (n.get("choices") or []):
            todo.append(c["next"])
            if c.get("else"):
                todo.append(c["else"])
        if n.get("else"):
            todo.append(n["else"])
    for nid in nodes:
        if nid not in seen:
            rep.add("h CHANCES", f"node {nid} is never reached")
    for nid, n in nodes.items():
        kids = n.get("children") or []
        weighted_set(f"node {nid}", kids, rep)
    for pname, p in (doc.get("pools", {}) or {}).items():
        items = [i if isinstance(i, dict) else {"text": i} for i in p.get("items", [])]
        weighted_set(f"pool {pname}", items, rep)


def weighted_set(where: str, kids: list[dict], rep: Report) -> None:
    if len(kids) < 2:
        return
    rar = [k.get("rarity") for k in kids]
    for r in rar:
        if r not in RARITY_WEIGHTS:
            rep.add("h CHANCES", f"{where}: rarity {r!r} is not one of rare, very_rare, exceptionally_rare")
            return
    ws = [k.get("weight", 1) for k in kids]
    if any(rar):
        for k, r, w in zip(kids, rar, ws):
            if w != RARITY_WEIGHTS[r]:
                rep.add("h CHANCES", f"{where}: weight {w} for {'a ' + r if r else 'a normal'} outcome; the "
                                     f"rarity table gives {RARITY_WEIGHTS[r]} (normal 20, rare 5, very rare 2, "
                                     "exceptionally rare 1)")
    elif len(set(ws)) > 1:
        rep.add("h CHANCES", f"{where}: weights {ws} differ but the source gives no odds (equal weights)")


def check_engine(doc: dict, rep: Report) -> None:
    cg = engine()
    if cg is None:
        rep.skipped.append("a SCHEMA / g ROUND: vv_cie_graph does not read version 6 yet (Track A)")
        return
    g = graph_for_engine(doc)
    shared = {"pools": shared_pools()}
    norm = None
    for scrolling in (False, True):   # the text fits with and without Scrolling Popups
        try:
            n2, problems = cg.validate(g, scrolling=scrolling, shared_pools=shared)
        except Exception as ex:  # a crash is a problem, never a pass
            rep.add("a SCHEMA", f"validate raised {type(ex).__name__}: {ex}")
            return
        for p in problems:
            rep.add("a SCHEMA", f"{'(scrolling) ' if scrolling else ''}{p}")
        norm = norm or (None if problems else n2)
    if norm is None:
        return
    # f SAFETY cross-check: the compiler's harm-capable roles are the ones derived here
    if hasattr(cg, "harm_capable"):
        theirs = set(cg.harm_capable(norm))
        ours = harm_roles(doc)
        if theirs != ours:
            rep.add("f SAFETY", f"harm-capable roles differ: compiler {sorted(theirs)}, checker {sorted(ours)}")
    try:
        blob = cg.compile_graph(norm)
        if blob != cg.compile_graph(cg.validate(g, scrolling=True, shared_pools=shared)[0]):
            rep.add("g ROUND", "compile is not deterministic")
        back = cg.decompile_graph(blob)
        if back != cg.without_names(norm):
            rep.add("g ROUND", "compile -> decompile does not give the graph back")
        if cg.compile_graph(back) != blob:
            rep.add("g ROUND", "decompile -> compile does not give the same bytes")
        if cg.normalize(json.loads(canonical(g)), shared)[0] != cg.normalize(g, shared)[0]:
            rep.add("g ROUND", "normalize is not stable through the canonical JSON")
    except Exception as ex:
        rep.add("g ROUND", f"compile / decompile raised {type(ex).__name__}: {ex}")


def check_shape(doc: dict, path: Path, rows: dict, rep: Report) -> dict | None:
    col = doc.get("collection")
    if doc.get("format") != "vvfp-cie-graph" or doc.get("version") != 6:
        rep.add("a SCHEMA", "a collection file is format vvfp-cie-graph, version 6")
    if not isinstance(col, dict):
        rep.add("a SCHEMA", "no collection block")
        return None
    cid = col.get("id")
    if not isinstance(cid, str) or not re.fullmatch(r"[a-z0-9_]+", cid or ""):
        rep.add("a SCHEMA", "collection.id is [a-z0-9_]")
    if path.stem != cid:
        rep.add("a SCHEMA", f"file name {path.name} is not collection.id {cid}.json")
    row = rows.get(cid)
    if row is None:
        rep.add("a SCHEMA", f"collection.id {cid!r} has no manifest row")
        return None
    if path.parent.name != row["section"]:
        rep.add("a SCHEMA", f"file is in {path.parent.name}/, the manifest's section is {row['section']}/")
    if col.get("lines") != row["lines"]:
        rep.add("a SCHEMA", f"collection.lines {col.get('lines')} is not the manifest's {row['lines']}")
    if col.get("source") != "v26":
        rep.add("a SCHEMA", "collection.source is 'v26'")
    if col.get("credit") != row["credit"]["text"]:
        rep.add("a SCHEMA", "collection.credit is not the verbatim credit text of the manifest row")
    if col.get("series") != row["series"]:
        rep.add("a SCHEMA", f"collection.series {col.get('series')!r} is not the manifest's {row['series']!r}")
    if sorted(doc.get("games", [])) != sorted(row["games"]):
        rep.add("a SCHEMA", f"games {doc.get('games')} are not the manifest's {row['games']}")
    choices = max((len(n.get("choices", []) or []) for n in doc.get("nodes", {}).values()), default=0)
    if choices != row["choices"]:
        rep.add("d TOKENS", f"the widest question has {choices} choices; the source has {row['choices']}")
    return row


def check_file(path: Path, rows: dict | None = None) -> Report:
    rows = manifest_rows() if rows is None else rows
    rep = Report(str(path.relative_to(lib.ROOT)) if path.is_relative_to(lib.ROOT) else str(path))
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as ex:
        rep.add("a SCHEMA", f"not readable JSON: {ex}")
        return rep
    row = check_shape(doc, path, rows, rep)
    check_fidelity_and_coverage(doc, row, rep)
    check_tokens(doc, row, rep)
    check_effects(doc, rep)
    check_safety(doc, rep)
    check_chances(doc, rep)
    check_engine(doc, rep)
    text = path.read_text(encoding="utf-8")
    if text != canonical(doc):
        rep.add("g ROUND", "the file is not in canonical form (python scripts/collection_check.py --format FILE)")
    return rep


def fill_from_manifest(doc: dict, rows: dict) -> None:
    """--format: copy the manifest row's source facts into collection (source, lines, section, credit, series), so an
    author never types the credit by hand."""
    col = doc.get("collection")
    row = rows.get(col.get("id")) if isinstance(col, dict) else None
    if row is None:
        return
    fresh = {"id": row["id"], "source": "v26", "lines": row["lines"], "section": row["section"],
             "credit": row["credit"]["text"], "draw_weight": col.get("draw_weight", 1), "series": row["series"]}
    rest = {k: v for k, v in col.items() if k not in fresh}
    doc["collection"] = {**fresh, **rest}


def canonical(doc: dict) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def check_shared_pools() -> list[str]:
    """data/event_collection/shared_pools.json: each item is its source text (its own src) and every pool name is
    a v6 pool name.  Returned as problems (empty = fine)."""
    out = []
    if not lib.SHARED_POOLS.exists():
        return ["data/event_collection/shared_pools.json is missing"]
    data = json.loads(lib.SHARED_POOLS.read_text(encoding="utf-8"))
    if data.get("format") != "vvfp-event-collection-pools" or not isinstance(data.get("pools"), dict):
        return ["shared_pools.json: format vvfp-event-collection-pools with a pools object"]
    for name, p in data["pools"].items():
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_]{0,31}", name):
            out.append(f"shared pool {name}: not a pool name")
        for i, it in enumerate(p.get("items", [])):
            if not isinstance(it, dict) or not it.get("src") or not isinstance(it.get("text"), str):
                out.append(f"shared pool {name} item {i + 1}: {{\"text\", \"src\"}}")
                continue
            try:
                span = build_span(lib.src_lines(it["src"]), {}, {})
            except ValueError as ex:
                out.append(f"shared pool {name} item {i + 1}: {ex}")
                continue
            if not re.search(text_regex(it["text"], {}), span.text):
                out.append(f"shared pool {name} item {i + 1}: {it['text'][:60]!r} is not the source text")
    return out


def collection_files() -> list[Path]:
    return sorted(p for p in lib.COLLECTION_DIR.glob("*/*.json"))


def ledger_summary(doc: dict) -> list[str]:
    col = doc.get("collection", {})
    out = [f"{doc.get('title')} ({col.get('id')}, lines {col.get('lines')})"]
    for f in doc.get("grammar_fixes", []) or []:
        out.append(f"  grammar {f['src']}: {f['before']!r} -> {f['after']!r}")
    for nid, n in doc.get("nodes", {}).items():
        for t in n.get("text_only", []) or []:
            out.append(f"  text only {t['src']} ({nid}): {t.get('what', '')} -- {t['reason']}")
    subs = set()
    for f in text_fields(doc):
        if f.src:
            for n in lib.src_lines(f.src):
                subs.update(lib.substitutions_in(lib.line(n)))
    if subs:
        out.append(f"  authoring substitutions: {', '.join(sorted(subs))}")
    fallback = sorted({c for f in text_fields(doc) for c in f.text if c in ";&%"} |
                      {"(" for f in text_fields(doc) if "\\(" in f.text})
    if fallback and set(doc.get("games", [])) & {1, 2}:
        out.append(f"  VV1/VV2 display fallback without Unicode Text: "
                   f"{', '.join(f'{c!r}->{lib.FONT_FALLBACK_VV12[c]!r}' for c in fallback)}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="*", type=Path)
    ap.add_argument("--report", action="store_true", help="print each file's ledger summary")
    ap.add_argument("--format", action="store_true", help="rewrite the files in canonical form, then check")
    args = ap.parse_args(argv)
    files = [p.resolve() for p in args.files] or collection_files()
    rows = manifest_rows()
    bad = 0
    for p in files:
        if args.format:
            doc = json.loads(p.read_text(encoding="utf-8"))
            fill_from_manifest(doc, rows)
            p.write_text(canonical(doc), encoding="utf-8", newline="\n")
        rep = check_file(p, rows)
        status = "OK" if rep.ok else f"{len(rep.problems)} PROBLEMS"
        print(f"{rep.path}: {status}")
        for x in rep.problems:
            print(f"  {x}")
        for x in rep.skipped:
            print(f"  SKIPPED {x}")
        if args.report:
            for x in rep.notes + ledger_summary(json.loads(p.read_text(encoding="utf-8"))):
                print(f"  {x}")
        bad += not rep.ok
    print(f"{len(files) - bad} of {len(files)} files pass")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
