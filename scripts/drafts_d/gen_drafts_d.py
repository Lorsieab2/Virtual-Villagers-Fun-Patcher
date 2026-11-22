"""Write the owner-approved files, group D (collection_lib.DRAFTS_D), as collection events, then format and check them:

    python scripts/drafts_d/gen_drafts_d.py [source id ...]
    python scripts/drafts_d/gen_drafts_d.py --sheet <source id>     # the review sheet: each event's text and edits

  draft_rm2   Role Models and Good Examples RM-41..RM-90           50  setup, four choices, two outcomes each
  draft_hz2   Beyond the Horizon 081-130                           50  setup, three choices, two outcomes each
  fathers30   Fathers, Pregnancy and Parenthood 01-30              30  setup, four choices, two outcomes each
  moments500  the 500 Tiny Island Moments as 125 moments T001-T125 125  one popup: the opening and one of 4 endings
  draft_tim2  Tiny Island Moments T126-T175                        50  one popup: the opening and one of 4 endings
  openq97     the armor moments M01-M35 (Completed Open Questions) 35  one popup: the opening and its follow-up
  armor45     Armor, Weapons and Inherited Traditions 01-45        45  one popup: the event's sentences
  draft_arm2  Armor, Weapons and Heirlooms ARM-46..ARM-95          50  one popup: the event's sentences

THE SHAPES.  A choice event's setup is the question page (its labels in title case, the owner 2026-11-15); each label
leads to a branch whose two outcomes are equally likely alternatives (the sources: "the game picks one outcome from
the chosen choice"; no outcome harms anyone, so no rarity weights).  A moment is a branch of equally likely pages: the
owner's Question 1 answer A ("When one appears, the game picks one of its 4 endings at random"), each page the opening
and one ending.  Every file is one series (collection_manifest.DRAFTS_D_SERIES), so a file counts as one draw in the
rare roll.

THE OWNER'S ORDERS (2026-11-15).  Text verbatim; things need not exist in the game to appear in the text; no swaps;
no rule-driven rewording; obvious grammar fixes only.  "Use names and pronouns instead of vague roles": the person an
event is about, named in its setup (or a moment's opening, or an armor event's sentence) by a role word, is a cast
villager shown by name -- "(name1), an elder," keeps the role word as flavor ("the job is flavor only"), a plain "a
villager" / "someone" becomes the name.  Each such change is a ledger "sensitivity" entry (before -> after; the
owner's naming order, not a content change).  The other people of an event keep the source's words.

THE ANNOTATIONS (scripts/drafts_d/annotations/<source id>.txt; one block per event code, e.g. "RM-41", "T001", "M01",
"ARM-01", "FAT-01"):
  DESC: the Pick Island Event sentence (else the first plain sentence of the setup / opening, its names as "a villager")
  ROLES: name1=3-13 name2=18+/m          (ages; "/m" "/f" a sex; "/nursing" the game's nursing parent; a name2 not
                                          shown is a cast-only villager)
  REL: name1=parent_of:name2             (a recorded kinship relation: the subject is the parent of the friend)
  NAME: "A child" => "(Name1), a child,"  (the naming edit on the setup / opening / sentence; else the automatic one
                                          below; "NAME: none" keeps the text unnamed)
  EDIT <part>: "before" => "after"       (another naming edit: part S, a label A-D, an outcome A1-D2, an ending E1-E4)
  TODO: a ledger note for a pending piece
  REVIEW: ok | the 15-point review's finding

Effects: none.  None of these files marks a reward or a harm (the RM / Horizon files: "Rewards, where given, are
small ... or none"; none is given), so every event is story only; an effect-table word gets a text_only reason.

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

ANN_DIR = Path(__file__).resolve().parent / "annotations"
STORY_ONLY = "story only: the file marks no effect (no new mechanics)"
WORD_WHY = {
    "food": "food in the story (a meal, a catch, fruit); the village's stores do not change -- " + STORY_ONLY,
    "tech": "technology talked about in the story; no tech points change -- " + STORY_ONLY,
    "skill": "\"experience\" / \"skill\" in the everyday sense, not a skill gain -- " + STORY_ONLY,
    "celebrate": "a celebration or a happy feeling in the story; no celebration happens in the game -- " + STORY_ONLY,
    "health": "health or an injury talked about in the story; nobody's health changes -- " + STORY_ONLY,
    "preference": "a feeling in the moment, not a lasting dislike -- " + STORY_ONLY,
    "kill": "a death only talked about (or the word's everyday sense); nobody dies -- " + STORY_ONLY,
    "vanish": "the word's everyday sense (a thing or a sound gone); nobody leaves the village -- " + STORY_ONLY,
    "damage": "a small thing breaks in the story; no building is damaged -- " + STORY_ONLY,
}
NAMING_WHY = ("the owner (2026-11-15): the person the event is about is a cast villager shown by name, the role word "
              "kept as flavor (the villager need not have that job)")
KEEP = re.compile(r"\((?:[Nn]ame[12]|he/she|He/she|him/her|his/her|His/her)\)")

# ---- Ages and the automatic naming ------------------------------------------------------------------------------------

PEOPLE = {   # role word -> casting age
    "villager": "3+", "child": "3-13", "toddler": "3-7", "youngster": "3-17", "teenager": "14-17", "teen": "14-17",
    "elder": "55+", "grandparent": "40+", "veteran": "40+",
    "parent": "18+", "father": "18+/m", "mother": "18+/f", "man": "18+/m", "woman": "18+/f",
    "fisher": "18+", "healer": "18+", "builder": "18+", "farmer": "18+", "gardener": "18+", "scholar": "18+",
    "researcher": "18+", "artisan": "18+", "carver": "18+", "craftsperson": "18+", "apprentice": "14+",
    "hunter": "18+", "bowyer": "18+", "bowmaker": "18+", "armorer": "18+", "carpenter": "18+", "cook": "18+",
    "weaver": "18+", "navigator": "18+", "drummer": "14+", "dancer": "14+", "musician": "14+",
    "storyteller": "18+", "keeper": "18+", "historian": "18+", "toolmaker": "18+", "potter": "18+",
    "neighbor": "18+", "newcomer": "18+", "skeptic": "18+", "archer": "18+", "teacher": "18+", "cook's": "18+",
    "mediator": "18+", "singer": "14+", "fisherman": "18+", "traveler": "18+", "dyer": "18+", "netmaker": "18+",
    "boatbuilder": "18+", "sculptor": "18+", "painter": "18+", "baker": "18+", "herbalist": "18+",
}
ADJ = (r"(?:(?:young|quiet|old|older|small|little|curious|seasoned|new|shy|elderly|experienced|tired|lonely|aging"
       r"|expert|skilled|nervous|proud|patient|busy)\s+)")
LEAD = re.compile(r"\b([Aa]n?) (" + ADJ + r"{0,2})(" + "|".join(sorted(PEOPLE, key=len, reverse=True)) + r")\b")
PLAIN = {"villager"}


def auto_name(text: str) -> tuple[str, str, str] | None:
    """(before, after, age) for the first "a <role>" in the text, or None."""
    if re.search(r"\([Nn]ame[12]\)", text):
        return None
    m = re.match(r"^(Someone)\b", text)
    if m:
        return "Someone", "(Name1)", "3+"
    m = LEAD.search(text)
    if not m:
        return None
    art, adj, noun = m.groups()
    before = m.group(0)
    if text[m.end():m.end() + 2] in ("'s", "s'") or text[m.end():m.end() + 4] == " who":
        return None          # a possessive or a "who" clause: the annotation's NAME line words it
    start = m.start() == 0 or text[:m.start()].rstrip().endswith((".", "!", "?"))
    nm = "(Name1)" if start else "(name1)"
    age = PEOPLE[noun]
    if "young" in adj.split():
        age = "3-17" if noun == "villager" else "14-25" if age in ("18+", "14+") else age
    if set(adj.split()) & {"old", "older", "elderly", "aging"} and age in ("18+", "14+", "40+"):
        age = "55+"
    if noun in PLAIN and not adj:
        return before, nm, age
    nxt = text[m.end():m.end() + 1]
    tail = "" if nxt in (",", ".", "!", "?", ";", ":") else ","
    return before, f"{nm}, {art.lower()} {adj}{noun}{tail}", age


# ---- Annotations ------------------------------------------------------------------------------------------------------

def read_annotations(sid: str) -> dict[str, dict]:
    path = ANN_DIR / f"{sid}.txt"
    out: dict[str, dict] = {}
    cur = None
    if not path.exists():
        return out
    for s in path.read_text(encoding="utf-8").splitlines():
        s = s.rstrip()
        if not s.strip() or s.startswith("#"):
            continue
        if re.fullmatch(r"[A-Z]+-?\d{2,3}", s.strip()):
            cur = out.setdefault(s.strip(), {})
            continue
        if cur is None:
            raise SystemExit(f"{path.name}: {s!r} before any event code")
        m = re.match(r'^NAME:\s*"(.*)" => "(.*)"$', s)
        if m:
            cur["NAME"] = m.groups()
            continue
        if s.strip() == "NAME: none":
            cur["NAME"] = None
            continue
        m = re.match(r'^EDIT (S|[A-D]|[A-D][12]|E[1-4]):\s*"(.*)" => "(.*)"$', s)
        if m:
            cur.setdefault("EDITS", []).append(m.groups())
            continue
        m = re.match(r"^(DESC|ROLES|REL|TODO|REVIEW):\s*(.*)$", s)
        if m:
            key, val = m.groups()
            if key in ("ROLES", "REL"):
                cur[key] = dict(x.split("=", 1) for x in val.split())
            elif key == "TODO":
                cur.setdefault("TODO", []).append(val.strip())
            else:
                cur[key] = val.strip()
            continue
        raise SystemExit(f"{path.name}: unreadable line {s!r}")
    return out


def age_spec(spec: str) -> dict:
    nursing = spec.endswith("/nursing")
    if nursing:
        spec = spec[:-len("/nursing")]
    sex = None
    if spec.endswith(("/m", "/f")):
        spec, sx = spec.rsplit("/", 1)
        sex = {"m": "male", "f": "female"}[sx]
    m = re.fullmatch(r"(\d+)(?:\+|-(\d+))", spec)
    assert m, spec
    out = {"kind": "villager", "min_age": int(m.group(1))}
    if m.group(2):
        out["max_age"] = int(m.group(2))
    if sex:
        out["sex"] = sex
    if nursing:
        out["special"] = "nursing_parent"
    return out


# ---- Text -------------------------------------------------------------------------------------------------------------

def L(n: int) -> str:
    return f"L{n}"


def norm(n: int) -> str:
    return lib.normalize_source_text(lib.line(n))


def shown(n: int, cuts: dict, fixes: dict) -> str:
    """Line n as the page shows it: the checker's own processing (cuts, edits, structural markers), the literal
    parentheses escaped."""
    p = cc.processed_line(n, cuts, fixes)
    out, i = [], 0
    for m in KEEP.finditer(p):
        out.append(p[i:m.start()].replace("(", r"\(").replace(")", r"\)"))
        out.append(m.group(0))
        i = m.end()
    out.append(p[i:].replace("(", r"\(").replace(")", r"\)"))
    return "".join(out)


def text_only(text: str) -> list[dict]:
    out = []
    for rx, want in cc.KEYWORDS:
        words = []
        for m in rx.finditer(text):
            if m.group(0).lower() not in words:
                words.append(m.group(0).lower())
        if words:
            kind = "health" if "health_change" in want else "kill" if "kill" in want else sorted(want)[0]
            out.append({"what": ", ".join(f'"{w}"' for w in words), "reason": WORD_WHY[kind]})
    return out


def description(text: str) -> str | None:
    """The first plain sentence of the (unedited) text, its names as "a villager"."""
    t = re.sub(r"^\(Name1\)|^\(name1\)", "A villager", text.strip())
    t = re.sub(r"\([Nn]ame1\)", "a villager", t)
    t = re.sub(r"\([Nn]ame2\)'s", "a friend's", t)
    t = re.sub(r"\([Nn]ame2\)", "a friend", t)
    t = t.replace('"', "").replace("(", "").replace(")", "")
    t = re.sub(r"\s+", " ", t).strip()
    for cand in (t, re.match(r"^(.+?[.!?])(?:\s|$)", t).group(1) if re.match(r"^(.+?[.!?])(?:\s|$)", t) else t):
        cand = cand[:1].upper() + cand[1:]
        if cc.DESCRIPTION_RE.fullmatch(cand) and len(cand) <= cc.DESCRIPTION_MAX:
            return cand
    return None


# ---- One event --------------------------------------------------------------------------------------------------------

class Build:
    """One event's ledger, edits and pages."""

    def __init__(self, sid: str, row: dict, code: str, ann: dict):
        self.sid, self.row, self.code, self.ann = sid, row, code, ann
        self.ledger: list[dict] = []
        self.cuts: dict[int, list[str]] = {}
        self.fixes: dict[int, list[tuple[str, str]]] = {}
        self.problems: list[str] = []
        self.ages: dict[str, str] = {}

    def cut(self, n: int, text: str, kind: str = "structural", why: str = "a structural marker") -> None:
        assert text in norm(n), (self.code, n, text)
        self.cuts.setdefault(n, []).append(text)
        self.ledger.append({"src": L(n), "kind": kind, "text": text, "why": why})

    def whole(self, n: int, kind: str, why: str) -> None:
        self.ledger.append({"src": L(n), "kind": kind, "why": why})

    def edit(self, n: int, before: str, after: str) -> None:
        if norm(n).count(before) != 1:
            self.problems.append(f"{self.code} L{n}: {before!r} occurs {norm(n).count(before)} times")
            return
        self.fixes.setdefault(n, []).append((before, after))
        self.ledger.append({"src": L(n), "kind": "sensitivity", "before": before, "after": after,
                            "why": NAMING_WHY})

    def name(self, lines: list[int], lead_text: str) -> None:
        """The naming edit on `lines` (the same words on each: a moment's four entries share the opening)."""
        if "NAME" in self.ann:
            nm = self.ann["NAME"]
            if nm is None:
                return
            before, after = nm
            m = re.search(r"\b(" + "|".join(sorted(PEOPLE, key=len, reverse=True)) + r")\b", before)
            age = PEOPLE[m.group(1)] if m else "3+"
        else:
            got = auto_name(lead_text)
            if not got:
                return
            before, after, age = got
        for n in lines:
            self.edit(n, before, after)
        if age and "name1" not in self.ann.get("ROLES", {}):
            self.ages.setdefault("name1", age)

    def roles(self, texts: list[str]) -> dict:
        used = set()
        for t in texts:
            used |= {m.group(1) for m in re.finditer(r"\([Nn]ame([12])\)", t)}
        spec = dict(self.ages, **self.ann.get("ROLES", {}))
        out = {}
        for d, rid in (("1", "subject"), ("2", "friend")):
            if d in used or spec.get(f"name{d}"):
                out[rid] = age_spec(spec.get(f"name{d}", "3+"))
        if not out:
            out["subject"] = age_spec(spec.get("name1", "14+"))
        for key, val in self.ann.get("REL", {}).items():
            # "name1=parent_of:name2": the subject is that relation of the friend (cie-v6-binary.md 21)
            kind, other = val.split(":")
            out[{"name1": "subject", "name2": "friend"}[key]]["relation"] = {
                kind: {"name1": "subject", "name2": "friend"}[other]}
        return out

    def doc(self, nodes: dict, texts: list[str], desc_from: str) -> dict:
        roles = self.roles(texts)
        desc = self.ann.get("DESC") or description(desc_from)
        if not desc or not (cc.DESCRIPTION_RE.fullmatch(desc) and len(desc) <= cc.DESCRIPTION_MAX):
            self.problems.append(f"{self.code}: needs a DESC ({desc_from[:100]!r})")
            desc = "X."
        for t in self.ann.get("TODO", []):
            self.ledger.append({"src": self.row_src(), "kind": "note", "why": "TODO: " + t})
        col = {"id": self.row["id"], "title_src": self.title_src, "ledger": self.ledger, "description": desc,
               "label_case": "title", "cast_only": list(roles)}
        doc = {"format": "vvfp-cie-graph", "version": 6, "title": self.row["title"], "games": self.row["games"],
               "collection": col, "requirement": {"min_eligible": len(roles)}, "roles": roles, "start": "setup",
               "nodes": nodes}
        if len(roles) > 1:
            doc = json.loads(json.dumps(doc).replace("(name1)", "(subject)").replace("(Name1)", "(subject)")
                             .replace("(name2)", "(friend)").replace("(Name2)", "(friend)"))
            # the ledger keeps the edit's own words
            doc["collection"]["ledger"] = self.ledger
        return doc

    def row_src(self) -> str:
        return L(self.row["lines"][0])

    def page(self, name: str, lines: list[int]) -> dict:
        text = " ".join(shown(n, self.cuts, self.fixes) for n in lines)
        nd = {"name": name, "text": text, "src": ",".join(L(n) for n in lines)}
        to = text_only(text)
        if to:
            nd["text_only"] = [dict(t, src=nd["src"]) for t in to]
        return nd


# ---- The shapes -------------------------------------------------------------------------------------------------------

def build_choices(b: Build, kind: str) -> dict:
    """draft_rm2 / draft_hz2 / fathers30: setup, labels A-D, two outcomes each."""
    h, e = b.row["lines"]
    b.title_src = L(h)
    setup, labels, outs = None, {}, {}
    for n in range(h + 1, e + 1):
        s = norm(n)
        if lib.is_blank_or_separator(n):
            continue
        st = s.strip()
        m = re.match(r"^([A-D])\. ", st)
        m2 = re.match(r"^([A-D])([12])\. ", st)
        m3 = re.match(r"^(Outcome ([12]):)", st)
        if st.startswith("SETUP: "):
            setup = n
        elif m:
            labels[m.group(1)] = n
            cur = m.group(1)
        elif m2:
            outs[f"{m2.group(1)}{m2.group(2)}"] = n
        elif m3:
            b.cut(n, m3.group(1))
            outs[f"{cur}{m3.group(2)}"] = n
        elif st.startswith("Content note:"):
            b.whole(n, "note", "Content note: the owner's per-event content note (the per-event content-notes feature "
                                "shows it), never part of a page")
        elif st.startswith(("THEME:", "CAST / CONDITIONS:")):
            b.whole(n, "note", "the event's theme / casting line, carried out as the roles' casting")
        elif st == "CHOICES AND POSSIBLE OUTCOMES:":
            b.whole(n, "structural", "a structural heading")
        elif kind == "fathers30" and setup is None:
            setup = n
        else:
            raise SystemExit(f"{b.code}: unexpected line {n}: {st!r}")
    assert setup and len(outs) == 2 * len(labels), (b.code, setup, labels, outs)
    b.name([setup], cc.processed_line(setup, {}, {}))
    for part, before, after in b.ann.get("EDITS", []):
        n = setup if part == "S" else labels.get(part) or outs[part]
        b.edit(n, before, after)
    q = b.page("The setup", [setup])
    q = {"type": "question", **q, "choices": []}
    nodes = {"setup": q}
    texts = [q["text"]]
    for k, ln in labels.items():
        lab = lib.title_case_label(shown(ln, b.cuts, b.fixes))
        q["choices"].append({"label": lab, "next": k.lower(), "src": L(ln)})
        texts.append(lab)
        nodes[k.lower()] = {"type": "branch", "name": f"Answer {k}",
                            "children": [{"next": f"{k.lower()}1"}, {"next": f"{k.lower()}2"}]}
        for j in (1, 2):
            pg = b.page(f"Outcome {k}{j}", [outs[f"{k}{j}"]])
            nodes[f"{k.lower()}{j}"] = pg
            texts.append(pg["text"])
    return b.doc(nodes, texts, cc.processed_line(setup, {}, {}))


def build_moment500(b: Build) -> dict:
    h, e = b.row["lines"]
    b.title_src = L(h + 1)
    bodies = []
    for k in range(4):
        a = h + 4 * k
        assert re.fullmatch(r"\[M\d{3}\]", lib.line(a)) and lib.line(a + 1).startswith("Title: "), (b.code, a)
        b.whole(a, "structural", "the entry's number (the four entries are one moment: the owner's Question 1, A)")
        if k:
            b.whole(a + 1, "structural", "the entry's title by position (the owner's Question 2, A: one title per "
                                         "moment, the first entry's line renamed in owner-title-changes.md)")
        bodies.append(a + 2)
    texts = [norm(n) for n in bodies]
    pre = re.match(r"^(.*?[.!?])\s", texts[0]).group(1)
    assert all(t.startswith(pre + " ") for t in texts), (b.code, texts)
    b.name(bodies, pre)
    return moment(b, [[n] for n in bodies], pre)


def build_moment_tim2(b: Build) -> dict:
    h, e = b.row["lines"]
    b.title_src = L(h)
    op = h + 1
    b.cut(op, "Opening:")
    ends = []
    for k in range(1, 5):
        b.cut(op + k, f"Ending {k}:")
        ends.append(op + k)
    b.name([op], cc.processed_line(op, b.cuts, {}))
    for part, before, after in b.ann.get("EDITS", []):
        b.edit(op if part == "S" else ends[int(part[1]) - 1], before, after)
    return moment(b, [[op, n] for n in ends], cc.processed_line(op, b.cuts, {}))


def moment(b: Build, pages: list[list[int]], opening: str) -> dict:
    nodes = {"setup": {"type": "branch", "name": "One of the endings",
                       "children": [{"next": f"e{i + 1}"} for i in range(len(pages))]}}
    texts = []
    for i, lines in enumerate(pages):
        pg = b.page(f"Ending {i + 1}", lines)
        nodes[f"e{i + 1}"] = pg
        texts.append(pg["text"])
    return b.doc(nodes, texts, opening)


def build_armor_moment(b: Build) -> dict:
    h, e = b.row["lines"]
    b.title_src = L(h + 1)
    b.cut(h, re.match(r"^\[M\d\d\]", lib.line(h)).group(0), why="the moment's number")
    b.cut(h + 2, "Follow-up:")
    b.name([h], cc.processed_line(h, b.cuts, {}))
    for part, before, after in b.ann.get("EDITS", []):
        b.edit(h if part == "S" else h + 2, before, after)
    pg = b.page("The moment", [h, h + 2])
    return b.doc({"setup": pg}, [pg["text"]], cc.processed_line(h, b.cuts, {}))


def build_armor(b: Build) -> dict:
    h, _ = b.row["lines"]
    b.title_src = L(h)
    s = norm(h)
    head = s[:s.index(" - ") + 2]
    b.cut(h, head, why="the event's number and title (the title) and the dash before its text")
    body = cc.processed_line(h, b.cuts, {})
    b.name([h], body)
    for part, before, after in b.ann.get("EDITS", []):
        b.edit(h, before, after)
    pg = b.page("The scene", [h])
    return b.doc({"setup": pg}, [pg["text"]], body)


# ---- The files --------------------------------------------------------------------------------------------------------

def rows(sid: str) -> list[dict]:
    data = json.loads(lib.MANIFEST.read_text(encoding="utf-8"))
    return sorted((r for r in data["rows"] if r.get("source") == sid and r["kind"] == "event"),
                  key=lambda r: r["lines"][0])


def code_of(sid: str, row: dict) -> str:
    num = re.match(r"^[a-z]+(\d+)_", row["id"]).group(1)
    return {"draft_rm2": "RM-", "draft_hz2": "HZ-", "fathers30": "FAT-", "moments500": "T", "draft_tim2": "T",
            "openq97": "M", "armor45": "ARM-", "draft_arm2": "ARM-"}[sid] + num


def build(sid: str, row: dict, ann: dict) -> tuple[dict, list[str]]:
    b = Build(sid, row, code_of(sid, row), ann)
    with lib.use_source(sid):
        if sid in ("draft_rm2", "draft_hz2", "fathers30"):
            doc = build_choices(b, sid)
        elif sid == "moments500":
            doc = build_moment500(b)
        elif sid == "draft_tim2":
            doc = build_moment_tim2(b)
        elif sid == "openq97":
            doc = build_armor_moment(b)
        else:
            doc = build_armor(b)
    if ann.get("REVIEW") is None:
        b.problems.append(f"{b.code}: no REVIEW")
    return doc, b.problems


def sheet(sid: str) -> str:
    anns = read_annotations(sid)
    out = []
    for r in rows(sid):
        doc, probs = build(sid, r, anns.get(code_of(sid, r), {}))
        out.append(f"### {code_of(sid, r)} {doc['title']} | roles {json.dumps(doc['roles'])}")
        out.append(f"  DESC {doc['collection']['description']}")
        for e in doc["collection"]["ledger"]:
            if e["kind"] == "sensitivity":
                out.append(f"  EDIT {e['src']}: {e['before']!r} => {e['after']!r}")
        first = next(iter(doc["nodes"].values()))
        if first.get("text"):
            out.append("  " + first["text"])
        else:
            out.append("  " + doc["nodes"]["e1"]["text"])
        out += ["  PROBLEM " + p for p in probs]
    return "\n".join(out)


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if argv[:1] == ["--sheet"]:
        print(sheet(argv[1]))
        return 0
    docs, problems = [], []
    for sid, (_name, _n, sec, _topic) in lib.DRAFTS_D.items():
        if argv and sid not in argv:
            continue
        anns = read_annotations(sid)
        codes = {code_of(sid, r) for r in rows(sid)}
        problems += [f"{sid}: annotation for unknown event {c}" for c in set(anns) - codes]
        for r in rows(sid):
            doc, probs = build(sid, r, anns.get(code_of(sid, r), {}))
            problems += probs
            docs.append((lib.DRAFTS_D_DIR / sec / f"{r['id']}.json", doc))
    for p in problems:
        print("PROBLEM", p)
    paths = []
    for p, doc in docs:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(cc.canonical(cc.with_outcome_effects(doc, p)), encoding="utf-8", newline="\n")
        paths.append(str(p))
    rc = subprocess.call([sys.executable, str(ROOT / "scripts" / "collection_check.py"), "--format", *paths])
    return rc or (1 if problems else 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
