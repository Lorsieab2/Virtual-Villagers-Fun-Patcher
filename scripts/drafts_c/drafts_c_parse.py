"""Read the owner-approved draft event files, group C (collection_lib.DRAFTS_C), and their authoring annotations.

THE DRAFT SHAPE (as group B, scripts/drafts_b/drafts_b_parse.py):
  PREFIX-NN. Title / (picks ...) casting line / the setup / Label: / its outcome / Label: / its outcome [/ Label: /
  its outcome]
Some events are one popup with no choice; HEA-15 offers three choices.  (name1) .. (name4) are the cast roles;
(he/she), (him/her), (his/her) follow a role's sex; [effect: ...] is an instruction, never shown.

THE ANNOTATIONS (scripts/drafts_c/annotations/<prefix>.txt, one block per event, written while reading each event):
  HEA-01
  DESC: the Pick Island Event sentence
  ROLES: name1=18+ name2=55+/f        (ages "18+", "3-13"; "/f" "/m" a sex the casting line asks for;
                                       "stranger" a named outsider: VV5's Isolans are never cast)
  REL: name2=parent_of:name1          (a relation the casting line asks for "where the game records it")
  FIX O1: 3=2 5=1                     (the n-th pronoun of the part is that role's: the reviewed answers where
                                       guess() below is wrong; 1-4 the names, s / a letter a figure)
  FIG: e=elder:55+                    (a person the draft names by a role word: cast, and shown by name)
  EDIT S: "An elder is" => "[e], an elder, is"   ([e] the figure's name, [e:he/she] a pronoun)
  WORD: chief                         (the text's "chief" is the game word {@chief})
  REVIEW: ok | the 15-point review's finding

Nothing here touches a game, a save or an exe.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import collection_lib as lib  # noqa: E402

ANN_DIR = Path(__file__).resolve().parent / "annotations"
PRONOUN_RE = re.compile(r"\((he/she|He/she|him/her|his/her|His/her|his/hers)\)")
NAME_RE = re.compile(r"\(name([1-4])\)")
PARTS = ("S", "L1", "O1", "L2", "O2", "L3", "O3")


@dataclass
class Event:
    sid: str
    row: dict
    code: str                      # "HEA-01"
    picks: int                     # line of the casting line
    parts: dict[str, int]          # "S", "L1", "O1", ... -> line
    ann: dict = field(default_factory=dict)


def rows(sid: str) -> list[dict]:
    data = json.loads(lib.MANIFEST.read_text(encoding="utf-8"))
    return sorted((r for r in data["rows"] if r.get("source") == sid and r["kind"] == "event"),
                  key=lambda r: r["lines"][0])


def raw(sid: str, n: int) -> str:
    with lib.use_source(sid):
        return lib.line(n)


def events(sid: str) -> list[Event]:
    pre = lib.DRAFTS_C[sid][3]
    out = []
    for r in rows(sid):
        h, e = r["lines"]
        code = re.match(rf"^({pre}-\d\d)\. ", raw(sid, h)).group(1)
        assert raw(sid, h + 1).startswith("(picks "), code
        body = [n for n in range(h + 2, e + 1) if raw(sid, n).strip()]
        keys = PARTS[:len(body)]
        assert len(body) in (1, 5, 7), (code, len(body))
        ev = Event(sid, r, code, h + 1, dict(zip(keys, body)))
        for k in keys:
            if k.startswith("L"):
                assert raw(sid, ev.parts[k]).rstrip().endswith(":"), code
        out.append(ev)
    return out


def _sentence_start(text: str, pos: int) -> int:
    best = 0
    for m in re.finditer(r"[.!?][\"']?\s+", text[:pos]):
        best = m.end()
    return best


def guess(text: str, part: str, before: str = "") -> str:
    """A first guess at each pronoun's role: the name mentioned last before it (in this paragraph, else the event's
    earlier text); for "(him/her)" (not "...self") whose nearest name is in its own sentence, the last OTHER name.
    The annotations' FIX lines hold the reviewed answers."""
    out = []
    for m in PRONOUN_RE.finditer(text):
        prior = NAME_RE.findall(before + " " + text[:m.start()])
        prior_here = [(x.start(), x.group(1)) for x in NAME_RE.finditer(text[:m.start()])]
        after = NAME_RE.findall(text[m.end():])
        if not prior:
            out.append(after[0] if after else "1")
            continue
        who = prior[-1]
        reflexive = text[m.end():m.end() + 4] == "self"
        if m.group(1) == "him/her" and not reflexive and prior_here:
            sstart = _sentence_start(text, m.start())
            if prior_here[-1][0] >= sstart:
                others = [x for x in prior if x != who]
                if others:
                    who = others[-1]
        out.append(who)
    return "".join(out)


def read_annotations(sid: str) -> dict[str, dict]:
    """{code: {"DESC": ..., "ROLES": {...}, "REL": {...}, "FIX": {"S": {3: "2"}}, ..., "REVIEW": ...}}"""
    pre = lib.DRAFTS_C[sid][3]
    path = ANN_DIR / f"{pre.lower()}.txt"
    out: dict[str, dict] = {}
    cur = None
    if not path.exists():
        return out
    for s in path.read_text(encoding="utf-8").splitlines():
        s = s.rstrip()
        if re.fullmatch(rf"{pre}-\d\d", s.strip()):
            cur = out.setdefault(s.strip(), {})
            continue
        if cur is None or not s.strip():
            continue
        m = re.match(r'^EDIT (S|L1|O1|L2|O2|L3|O3):\s*"(.*)" => "(.*)"$', s)
        if m:
            cur.setdefault("EDITS", []).append(m.groups())
            continue
        m = re.match(r"^FIX (S|L1|O1|L2|O2|L3|O3):\s*(.*)$", s)
        if m:
            fx = cur.setdefault("FIX", {}).setdefault(m.group(1), {})
            for item in m.group(2).split():
                i, who = item.split("=")
                fx[int(i)] = who
            continue
        m = re.match(r"^(DESC|ROLES|REL|FIG|WORD|SKILL|REVIEW):\s*(.*)$", s)
        if m:
            key, val = m.groups()
            if key in ("ROLES", "REL"):
                cur[key] = dict(x.split("=", 1) for x in val.split())
            else:
                cur[key] = val.strip()
            continue
        raise SystemExit(f"{path.name}: unreadable line {s!r}")
    return out


def marks(ev: Event, ann: dict) -> dict[str, str]:
    """Each part's pronoun owners: guess() with the annotation's FIX answers."""
    out, before = {}, ""
    for k, n in ev.parts.items():
        s = raw(ev.sid, n)
        g = list(guess(s, k, before if k.startswith(("O", "L")) else ""))
        for i, who in ann.get("FIX", {}).get(k, {}).items():
            g[i - 1] = who
        out[k] = "".join(g)
        if k == "S":
            before = s
    return out


def view(sid: str, codes: set[str] | None = None) -> str:
    """The review sheet: each event with every pronoun's current owner shown after it as {n:who}."""
    anns = read_annotations(sid)
    lines = []
    for ev in events(sid):
        if codes and ev.code not in codes:
            continue
        mk = marks(ev, anns.get(ev.code, {}))
        lines.append(f"### {ev.code} {ev.row['title']} | {raw(sid, ev.picks)}")
        for k, n in ev.parts.items():
            s, it = raw(sid, n), iter(enumerate(mk[k], 1))

            def tag(m, it=it):
                i, who = next(it)
                return f"{m.group(0)}{{{i}:{who}}}"
            lines.append(f"{k}: " + PRONOUN_RE.sub(tag, s).replace("(name", "(N"))
    return "\n".join(lines)


if __name__ == "__main__":
    pre = sys.argv[1].upper()
    sid = next(s for s, v in lib.DRAFTS_C.items() if v[3] == pre)
    sys.stdout.reconfigure(encoding="utf-8")
    print(view(sid, set(sys.argv[2:]) or None))
