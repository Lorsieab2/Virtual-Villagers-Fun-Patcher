"""Read the owner-approved draft event files, group B (collection_lib.DRAFTS_B), and their authoring annotations.

THE DRAFT SHAPE (every event of the eight files):
  PREFIX-NN. Title / (picks ...) casting line / the setup / Label: / its outcome / Label: / its outcome
A few events are one popup with no choice (PREFIX-NN. Title / (picks ...) / the text).  (name1) / (name2) are the cast
roles; (he/she), (him/her), (his/her) follow a role's sex; [effect: ...] is an instruction, never shown.

THE ANNOTATIONS (scripts/drafts_b/annotations/<prefix>.txt, one block per event, written while reading each event):
  HUM-01
  DESC: the Pick Island Event sentence
  ROLES: name1=18+ name2=18+          (ages: "18+", "3-13", "55+"; "s" = a text figure's pronouns, sex random)
  S: 11        L1:        O1: 2122     L2:        O2: 11
               (for each paragraph, the role -- 1, 2 or s -- of each pronoun in order; omitted when it has none)
  FIG: e=elder:55+                    (a person the draft names by a role word: cast, and shown by name)
  EDIT S: "An elder is" => "[e], an elder, is"   ([e] the figure's name, [e:he/she] / [1:his/her] a pronoun)
  REVIEW: ok | the 15-point review's finding
(pronoun marks may also be a figure's letter)

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
NAME_RE = re.compile(r"\(name([12])\)")
PARTS = ("S", "L1", "O1", "L2", "O2")


@dataclass
class Event:
    sid: str
    row: dict
    code: str                      # "HUM-01"
    picks: int                     # line of the casting line
    parts: dict[str, int]          # "S", "L1", "O1", "L2", "O2" -> line
    ann: dict = field(default_factory=dict)


def rows(sid: str) -> list[dict]:
    data = json.loads(lib.MANIFEST.read_text(encoding="utf-8"))
    return sorted((r for r in data["rows"] if r.get("source") == sid and r["kind"] == "event"),
                  key=lambda r: r["lines"][0])


def raw(sid: str, n: int) -> str:
    with lib.use_source(sid):
        return lib.line(n)


def events(sid: str) -> list[Event]:
    pre = lib.DRAFTS_B[sid][3]
    out = []
    for r in rows(sid):
        h, e = r["lines"]
        code = re.match(rf"^({pre}-\d\d)\. ", raw(sid, h)).group(1)
        assert raw(sid, h + 1).startswith("(picks "), code
        body = [n for n in range(h + 2, e + 1) if raw(sid, n).strip()]
        keys = PARTS if len(body) == 5 else ("S",)
        assert len(body) == len(keys), (code, len(body))
        ev = Event(sid, r, code, h + 1, dict(zip(keys, body)))
        if len(keys) == 5:
            assert raw(sid, body[1]).endswith(":") and raw(sid, body[3]).endswith(":"), code
        out.append(ev)
    return out


def guess(text: str, part: str) -> str:
    """A first guess at each pronoun's role: the name mentioned last before it in the paragraph (else the next one,
    else name1).  The annotations hold the reviewed answer."""
    out = []
    for m in PRONOUN_RE.finditer(text):
        before = NAME_RE.findall(text[:m.start()])
        after = NAME_RE.findall(text[m.end():])
        out.append(before[-1] if before else (after[0] if after and part.startswith("O") else "1"))
    return "".join(out)


def read_annotations(sid: str) -> dict[str, dict]:
    """{code: {"DESC": ..., "ROLES": {...}, "S": "11", ..., "REVIEW": ...}}"""
    pre = lib.DRAFTS_B[sid][3]
    path = ANN_DIR / f"{pre.lower()}.txt"
    out: dict[str, dict] = {}
    cur = None
    for s in path.read_text(encoding="utf-8").splitlines():
        s = s.rstrip()
        if re.fullmatch(rf"{pre}-\d\d", s.strip()):
            cur = out.setdefault(s.strip(), {})
            continue
        m = re.match(r'^EDIT (S|L1|O1|L2|O2):\s*"(.*)" => "(.*)"$', s)
        if m and cur is not None:
            cur.setdefault("EDITS", []).append(m.groups())
            continue
        m = re.match(r"^(DESC|ROLES|FIG|S|L1|O1|L2|O2|REVIEW):\s*(.*)$", s)
        if m and cur is not None:
            key, val = m.groups()
            if key == "ROLES":
                cur[key] = dict(x.split("=", 1) for x in val.split())
            elif key in PARTS:
                cur[key] = val.replace(" ", "")
            else:
                cur[key] = val.strip()
    return out
