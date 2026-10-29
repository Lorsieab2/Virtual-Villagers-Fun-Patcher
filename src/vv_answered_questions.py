"""Answered questions: a real answer is never asked again (all five games).

The owner (v1.35.80): "once I answer a question it shouldn't be asked again (goes to an answered
questions section where I can change the answer)".

WHY QUESTIONS CAME BACK.  Repair Saves & Logs' questions (src/vv_log_additions.py, the contradictions
of src/vv_log_contradictions.py) were remembered only when the answer was "Retroactively edit
records?" No; every other answer that leaves the records as they are -- "Only from now on (add
nothing)", "Keep it", "Keep both" -- was asked again at every Repair.  And many questions were told
apart by the line their record starts on in a named log file ("born|<file>|<line>"), so a record
moved by a repair above it, a log rolled into a new numbered file, or Move Files to Save Folders made
it a new question; others held a count ("lost-many|...|7"), a save's file time (which changes at
every save) or a record number that the game renumbers ("Arrived 11", a totem's record).

THE KEY.  Every question is now told apart by the FACT it asks about, never by where it is written:
its kind, the villager(s) it is about -- (name, head, body), followed through every rename the
patcher makes (src/vv_last_names.py keeps them in the Log Decisions file, vv_log_decisions
ALIAS_KIND) -- and what the record itself says (`fingerprint`: its lines, without its number, the
names, and the lines a repair adds or rewrites).  Questions that are alike in every way (two
byte-identical backfilled records) are told apart by their order, and an answer given while there
were N of them is taken only while there are N.

THE ANSWERS are kept in the slot's Log Decisions file (src/vv_log_decisions.py) as decisions of the
kind "answered": {"kind": "answered", "village", "field": <the key>, "source": <kind id>, "fact",
"who": [[name, head, body]...], "ordinal", "of", "question": <its words>, "options": [...], "verdict":
<the answer>, "label", "legacy": <the question's old key>, "date"}.  "Don't know" -- any answer that
begins "Don't know" -- is never kept: it is the only answer that is asked again.

A REMEMBERED ANSWER is not asked: its question is taken out of the checklist's questions
(`hold_back`) and its answer given to Repair as if the player had chosen it again, so what it does
still holds (a record it took out that a restored backup brought back is taken out again, with the
backup first and a Repairs Made record, as the first time).

THE ANSWERED QUESTIONS SECTION (Repair Saves & Logs, per save) lists every answer kept -- this
file's, the reconciliation's ("reconcile"), "Retroactively edit records?" No ("born_arrived",
"contradiction_left") and the graves' ("grave") -- with its date and whether it still matches a
question now (`listing`).  The player may change an answer (it is then applied as a first answer is,
when Repair runs: backup first, a Repairs Made record) or clear it (asked again).  An answer that no
longer matches any question is shown as such, never dropped.

OLD ANSWERS keep working: the reconciliation's ids are read under their old form too (and copied to
the new one at the next Repair), the contradictions' identities likewise, and every answer follows its
villager's renames.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import vv_log_decisions as decisions

KIND = "answered"
# The decisions the section lists, and what each is called there.
LISTED = {KIND: "Repair Saves & Logs", "reconcile": "Reconciliation", "born_arrived": "Backfilled Arrived records",
          "contradiction_left": "Records that contradict each other", "grave": "Grave information"}
YES, NO = "Yes", "No"

# The lines a repair adds to a record or rewrites in it, and the names (followed through the renames
# instead): left out of a record's fingerprint, so the fact stays the same after a repair.
_UNSTABLE = {"Name", "Child", "Mother", "Father", "Likes", "Dislikes", "Sex", "Special villager", "Custom title",
             "Mask", "Faction", "Born as", "Note", "Nursing", "Epitaph", "Last name", "Grave", "Cause of death",
             "Cause"}
_LABEL = re.compile(r"^\s*([A-Za-z][A-Za-z /'-]*):")


def dont_know(answer: str | None) -> bool:
    """No answer, or a "Don't know" (the only answer asked again)."""
    return not answer or answer.strip().lower().startswith("don't know")


def fingerprint(lines: list[str]) -> str:
    """What a record says, the same wherever it is written: its heading without its number, and a
    checksum of its other lines without the names and the lines a repair adds or rewrites."""
    if not lines:
        return ""
    heading = re.sub(r"\s+\d+\s*$", "", lines[0].strip())
    kept = []
    for line in lines[1:]:
        m = _LABEL.match(line)
        if m and m.group(1).strip() in _UNSTABLE:
            continue
        if line.strip():
            kept.append(line.strip())
    digest = hashlib.sha1("\n".join(kept).encode("latin-1", "replace")).hexdigest()[:16]
    return f"{heading}:{digest}"


def _who_text(who: tuple) -> str:
    return "|".join(f"{n}#{h}#{b}" for n, h, b in who)


def _canon(who, renamed: dict) -> tuple:
    out = []
    for w in who or ():
        if isinstance(w, (list, tuple)) and len(w) == 3:
            out.append(decisions.forward(tuple(w), renamed))
    return tuple(out)


def base_of(source: str, fact: str, who: tuple, renamed: dict | None = None) -> str:
    """A question's key: its kind, its fact and its villagers (under their latest names)."""
    return f"{source}|{fact}|{_who_text(_canon(who, renamed or {}))}"


def _fact(question) -> tuple[str, tuple]:
    fact = getattr(question, "fact", "") or f"key:{question.key}"
    return fact, tuple(tuple(w) for w in (getattr(question, "who", ()) or ()))


def annotate(kinds: list, renamed: dict | None = None) -> None:
    """Each question's key, and its order among questions alike in every way (`_base`, `_ordinal`, `_of`)."""
    renamed = renamed or {}
    for kind in kinds:
        if getattr(kind, "id", None) == "reconcile":
            continue
        groups: dict[str, list] = {}
        every = list(kind.questions.values()) + [q for q, _e in getattr(kind, "remembered", {}).values()]
        for q in every:
            fact, who = _fact(q)
            q._base = base_of(kind.id, fact, who, renamed)
            groups.setdefault(q._base, []).append(q)
        for same in groups.values():
            for n, q in enumerate(same, 1):
                q._ordinal, q._of = n, len(same)


def _key(q) -> str:
    return q._base + (f"#{q._ordinal}/{q._of}" if q._of > 1 else "")


def _entries(folder: Path, game: int, slot: int, villages: set[str] | None) -> tuple[list[dict], dict]:
    found = decisions.load(Path(folder), game, slot)
    renamed = decisions.aliases(found)
    return [d for d in found if d.get("kind") == KIND and isinstance(d.get("field"), str)
            and (villages is None or d.get("village") in villages or d.get("village") is None)], renamed


def _stored_key(d: dict, renamed: dict) -> tuple[str, int, int]:
    base = base_of(str(d.get("source", "")), str(d.get("fact", "")), tuple(tuple(w) for w in d.get("who") or ()),
                   renamed)
    return base, int(d.get("ordinal") or 1), int(d.get("of") or 1)


def _villages(folder: Path, game: int, slot: int):
    import vv_log_additions as additions
    return additions.current_villages(Path(folder), game, slot)


def hold_back(folder: Path, game: int, slot: int, kinds: list) -> int:
    """Take every question the player has already answered out of its kind's questions, into
    kind.remembered (key -> (question, the kept answer)).  Returns how many."""
    entries, renamed = _entries(folder, game, slot, _villages(folder, game, slot))
    annotate(kinds, renamed)
    stored: dict[tuple, dict] = {}
    for d in sorted(entries, key=lambda d: str(d.get("date", ""))):
        stored[_stored_key(d, renamed)] = d          # the latest answer of a key wins
    held = 0
    for kind in kinds:
        if getattr(kind, "id", None) == "reconcile":
            continue                                # the reconciliation keeps its own (vv_reconcile.answered)
        if not hasattr(kind, "remembered"):
            kind.remembered = {}
        for key, q in list(kind.questions.items()):
            d = stored.get((q._base, q._ordinal, q._of))
            if d is None:
                continue
            applied = _applied(str(d.get("verdict")), q.options)
            if applied is None:
                continue                            # the answer no longer fits its choices: asked again
            kind.remembered[key] = (q, {**d, "applied": applied})
            del kind.questions[key]
            held += 1
    return held


def _applied(verdict: str, options: list[str]) -> str | None:
    """What a kept answer is now among a question's choices: itself; or, for "From <snapshot date>"
    (a title or mask from a date on, src/vv_log_additions.py), "Only from now on" once every snapshot
    still without the line is older than that date -- the ones from it on have it already."""
    if verdict in options:
        return verdict
    import vv_log_additions as additions
    if verdict.startswith("From ") and additions.FROM_NOW in options:
        dates = [o[len("From "):] for o in options if o.startswith("From ")]
        if all(d < verdict[len("From "):] for d in dates):
            return additions.FROM_NOW
    return None


def kept_lookup(folder: Path, game: int, slot: int):
    """`said(source, fact, who)`: the latest answer kept for that fact (any order among look-alikes), or
    None -- for the readers that follow an answer without asking (Check Saves & Logs)."""
    entries, renamed = _entries(folder, game, slot, _villages(folder, game, slot))
    latest: dict[str, dict] = {}
    for d in sorted(entries, key=lambda d: str(d.get("date", ""))):
        latest[_stored_key(d, renamed)[0]] = d

    def said(source: str, fact: str, who: tuple) -> str | None:
        d = latest.get(base_of(source, fact, tuple(who or ()), renamed))
        return None if d is None else str(d.get("verdict"))
    return said


def remembered_answers(kinds: list) -> dict[str, str]:
    """The kept answers of the questions held back: what Repair applies for them."""
    return {key: str(d.get("applied", d.get("verdict"))) for kind in kinds
            for key, (_q, d) in getattr(kind, "remembered", {}).items()}


def village_header(folder: Path, game: int, slot: int) -> str | None:
    """The header the answers are kept under: the village's own, as vv_reconcile.remember names it."""
    villages = _villages(folder, game, slot)
    if not villages:
        return None
    village = sorted(villages)[0]
    try:
        import vv_log_tools as tools
        import vv_tribe_rename
        games = {g.number: g for g in vv_tribe_rename.GAMES}
        name = vv_tribe_rename.save_name(games[game], (Path(folder) / f"{tools.load_checker().SAVE_STEMS[game]}"
                                                                      f"{slot}.ldw").read_bytes())
        return vv_tribe_rename.village_header(name, slot) if name else village
    except (OSError, KeyError, ValueError):
        return village


def record(folder: Path, game: int, slot: int, kinds: list, chosen: set[str], answers: dict[str, str],
           now: datetime | None = None) -> list[str]:
    """Keep every real answer to the questions of the ticked kinds (the reconciliation keeps its own).
    Returns the lines for the Repairs Made record ("Answered: ..." / "Answer changed: ...")."""
    entries, renamed = _entries(folder, game, slot, None)
    if any(not hasattr(q, "_base") for kind in kinds for q in getattr(kind, "questions", {}).values()):
        annotate(kinds, renamed)
    before = {str(d.get("field")): d for d in entries}
    village = village_header(folder, game, slot)
    out, lines = [], []
    for kind in kinds:
        if getattr(kind, "id", None) in (None, "reconcile") or kind.id not in chosen:
            continue
        for key, q in kind.questions.items():
            answer = answers.get(key)
            if dont_know(answer) or answer not in q.options:
                continue
            # "Retroactively edit records?" belongs to the question before it: with that one left at
            # "Don't know", it was never really answered (both are asked again).
            partner = key[:-len("|retro")] if key.endswith("|retro") else (
                "contradiction|" + key[len("retro|"):] if key.startswith("retro|") else None)
            if partner is not None and (partner in kind.questions or partner in getattr(kind, "remembered", {})) \
                    and dont_know(answers.get(partner)):
                continue
            fact, who = _fact(q)
            field_ = _key(q)
            out.append({"kind": KIND, "village": village, "field": field_, "source": kind.id, "fact": fact,
                        "who": [list(w) for w in who], "ordinal": q._ordinal, "of": q._of,
                        "question": q.text, "options": list(q.options), "verdict": answer, "label": kind.label,
                        "legacy": key, "edited": False})
            old = before.get(field_)
            if old is not None and old.get("verdict") != answer:
                lines.append(f"Answer changed: {q.text[:160]} -- {answer} (was: {old.get('verdict')})")
            elif old is None:
                lines.append(f"Answered: {q.text[:160]} -- {answer}")
    if out:
        decisions.record(Path(folder), game, slot, out, now)
    return lines


# ---------------------------------------------------------------------------
# One yes / no question asked on its own (the lost titles, The Lost Children's totems)
# ---------------------------------------------------------------------------

def asked_before(folder: Path, game: int, slot: int, source: str, fact: str, who: tuple) -> str | None:
    """The kept answer ("Yes" / "No") to one yes / no question, or None (ask it)."""
    entries, renamed = _entries(folder, game, slot, _villages(folder, game, slot))
    want = base_of(source, fact, who, renamed)
    found = [d for d in entries if _stored_key(d, renamed)[0] == want and d.get("verdict") in (YES, NO)]
    return str(max(found, key=lambda d: str(d.get("date", ""))).get("verdict")) if found else None


def keep_yes_no(folder: Path, game: int, slot: int, source: str, label: str, fact: str, who: tuple,
                text: str, answer: bool, now: datetime | None = None) -> None:
    """Keep the player's yes / no answer to one question (asked_before reads it)."""
    entries, renamed = _entries(folder, game, slot, None)
    field_ = base_of(source, fact, who, renamed)
    decisions.record(Path(folder), game, slot, [{
        "kind": KIND, "village": village_header(folder, game, slot), "field": field_, "source": source,
        "fact": fact, "who": [list(w) for w in who], "ordinal": 1, "of": 1, "question": text,
        "options": [YES, NO], "verdict": YES if answer else NO, "label": label, "edited": False, "alone": True}], now)


# ---------------------------------------------------------------------------
# The same villager, or two? (the Family Tree Maker, all five games)
# ---------------------------------------------------------------------------
# The owner (v1.35.80 update): "A change in body, head and mask does not mean they disappeared.  A change in
# title or special villager status does not mean they disappeared." and "Please add prompts in the Family
# Tree Maker to ask if a villager that's changed is the same or different."  When the records cannot settle
# whether an older record (an older look, an older title) and a villager now are one villager, the Family
# Tree Maker asks; the answer is kept here, under both identities (followed through every rename the patcher
# makes), listed in Answered questions (to change or clear: cleared, it is asked again), and every reader
# honours it: the tree and the Matchmaker (vv_genealogy), the reconciliation, numbering, the records.
IDENTITY_SOURCE = "identity"
IDENTITY_FACT = "same-villager"
SAME, DIFFERENT = "Same villager", "Different villagers"
IDENTITY_OPTIONS = [SAME, DIFFERENT]
IDENTITY_LABEL = "Family Tree Maker: the same villager?"


def identity_answers(folder: Path, game: int, slot: int) -> dict[tuple, str]:
    """{(older (name, head, body), newer (name, head, body)): SAME or DIFFERENT}, the latest answer of each
    pair, both identities under their latest names.  Reads only; nothing when the file cannot be read."""
    try:
        entries, renamed = _entries(folder, game, slot, _villages(folder, game, slot))
    except (OSError, ValueError):
        return {}
    out: dict[tuple, str] = {}
    for d in sorted(entries, key=lambda d: str(d.get("date", ""))):
        if d.get("source") != IDENTITY_SOURCE or d.get("verdict") not in IDENTITY_OPTIONS:
            continue
        who = _canon(d.get("who"), renamed)
        if len(who) == 2:
            out[(who[0], who[1])] = str(d["verdict"])
    return out


def identity_said(answers: dict[tuple, str], a: tuple, b: tuple) -> str | None:
    """The answer kept for the pair, whichever way round it was asked."""
    return answers.get((a, b)) or answers.get((b, a))


def keep_identity(folder: Path, game: int, slot: int, older: tuple, newer: tuple, verdict: str | None,
                  text: str, now: datetime | None = None) -> None:
    """Keep the player's answer to "is <older> the same villager as <newer>?"; "Don't know" (or None) takes
    a kept answer out, so the question is asked again."""
    entries, renamed = _entries(folder, game, slot, None)
    who = (tuple(older), tuple(newer))
    field_ = base_of(IDENTITY_SOURCE, IDENTITY_FACT, who, renamed)
    swapped = base_of(IDENTITY_SOURCE, IDENTITY_FACT, (who[1], who[0]), renamed)
    if verdict not in IDENTITY_OPTIONS:
        if any(str(d.get("field")) in (field_, swapped) for d in entries):
            decisions.rewrite(Path(folder), game, slot,
                              lambda found: [d for d in found if not (d.get("kind") == KIND
                                                                      and str(d.get("field")) in (field_, swapped))])
        return
    if any(str(d.get("field")) == swapped for d in entries):
        decisions.rewrite(Path(folder), game, slot,
                          lambda found: [d for d in found if not (d.get("kind") == KIND
                                                                  and str(d.get("field")) == swapped)])
    decisions.record(Path(folder), game, slot, [{
        "kind": KIND, "village": village_header(folder, game, slot), "field": field_, "source": IDENTITY_SOURCE,
        "fact": IDENTITY_FACT, "who": [list(w) for w in who], "ordinal": 1, "of": 1, "question": text,
        "options": list(IDENTITY_OPTIONS), "verdict": verdict, "label": IDENTITY_LABEL, "edited": False,
        "alone": True}], now)


# ---------------------------------------------------------------------------
# Which of two living namesakes is the parent? (the Family Tree Maker, all five games)
# ---------------------------------------------------------------------------
# The owner (v1.35.85): two living villagers of one name, head and body are two people; a child is linked to the
# one old enough to be the parent, and when both could be the Family Tree Maker asks.  The answer is the parent's
# place by age among the namesakes ("The oldest", "The second oldest"...: vv_genealogy.RANK_WORDS), which stays
# true while they live, kept under the child and the parent's name and look, and listed in Answered questions.
PARENT_SOURCE = "parent"
PARENT_LABEL = "Family Tree Maker: which villager is the parent?"


def _child_rank(d: dict) -> int:
    """The child's place by age among their living namesakes the answer was given for; 0 for a child with none
    (and for an answer kept before the rank was: it applies only to a child with no living namesake)."""
    try:
        return max(0, int(d.get("child_rank") or 0))
    except (TypeError, ValueError):
        return 0


def _parent_field(label: str, who: tuple, renamed: dict, child_rank: int) -> str:
    base = base_of(PARENT_SOURCE, label, who, renamed)
    return f"{base}|child#{child_rank}" if child_rank else base


def parent_answers(folder: Path, game: int, slot: int) -> dict[tuple, str]:
    """{(child (name, head, body), parent (name, head, body), "Father"/"Mother", the child's namesake rank (0:
    none)): the answer}, the latest of each.  Reads only; nothing when the file cannot be read."""
    try:
        entries, renamed = _entries(folder, game, slot, _villages(folder, game, slot))
    except (OSError, ValueError):
        return {}
    out: dict[tuple, str] = {}
    for d in sorted(entries, key=lambda d: str(d.get("date", ""))):
        if d.get("source") != PARENT_SOURCE or not d.get("verdict") or dont_know(str(d.get("verdict"))):
            continue
        who = _canon(d.get("who"), renamed)
        if len(who) == 2:
            out[(who[0], who[1], str(d.get("fact")), _child_rank(d))] = str(d["verdict"])
    return out


def keep_parent(folder: Path, game: int, slot: int, child: tuple, parent: tuple, label: str, options: list[str],
                verdict: str | None, text: str, now: datetime | None = None, child_rank: int = 0) -> None:
    """Keep the player's answer to "which of these is <child>'s father (mother)?"; "Don't know" (or None)
    takes a kept answer out, so the question is asked again.  `child_rank` is the child's place by age among
    their living namesakes (0: none), so two children of one name and look keep an answer each."""
    entries, renamed = _entries(folder, game, slot, None)
    who = (tuple(child), tuple(parent))
    child_rank = max(0, int(child_rank or 0))
    field_ = _parent_field(label, who, renamed, child_rank)
    if any(str(d.get("field")) == field_ for d in entries):
        decisions.rewrite(Path(folder), game, slot,
                          lambda found: [d for d in found if not (d.get("kind") == KIND and str(d.get("field")) == field_)])
    if verdict is None or dont_know(verdict):
        return
    decisions.record(Path(folder), game, slot, [{
        "kind": KIND, "village": village_header(folder, game, slot), "field": field_, "source": PARENT_SOURCE,
        "fact": label, "who": [list(w) for w in who], "ordinal": 1, "of": 1, "question": text,
        "options": list(options), "verdict": verdict, "label": PARENT_LABEL, "edited": False, "alone": True,
        **({"child_rank": child_rank} if child_rank else {})}], now)


# ---------------------------------------------------------------------------
# The section: every answer kept, changed or cleared
# ---------------------------------------------------------------------------

@dataclass
class Row:
    ident: tuple                    # the decision it is: (kind, village, name, head, body, field)
    group: str                      # where it was asked (LISTED)
    text: str                       # the question
    answer: str
    date: str
    matches: bool                   # a question asked now is this one
    options: list[str] = field(default_factory=list)   # empty: it can only be cleared
    live: tuple | None = None       # (kind, key, question) of the question held back now

    @property
    def status(self) -> str:
        if self.matches is None:
            if self.group == IDENTITY_LABEL:
                return ("Asked by the Family Tree Maker: your answer is used by the tree, the reconciliation, "
                        "numbering and the records, and it is not asked again (cleared, it is asked again).")
            return "Asked on its own when Repair runs: your answer is used each time, and it is not asked."
        return ("Matches a question now: your answer is used, and the question is not asked."
                if self.matches else "No longer matches any question now (your answer was carried out, or the "
                                     "records it was about changed); kept, and used again if it ever comes back.")


def _left_ident(d: dict) -> str | None:
    """The contradiction identity vv_log_contradictions.remember keeps for an answer of that kind."""
    legacy = str(d.get("legacy") or "")
    if d.get("source") != "contradictions":
        return None
    for prefix in ("contradiction|", "retro|"):
        if legacy.startswith(prefix):
            return legacy[len(prefix):]
    return None


def count(folder: Path, game: int, slot: int) -> int:
    """How many answers the slot's file keeps (every kind the section lists).  Reads only the file."""
    return sum(1 for d in decisions.load(Path(folder), game, slot) if d.get("kind") in LISTED)


def ident_of(d: dict) -> tuple:
    return tuple(d.get(k) for k in ("kind", "village", "name", "head", "body", "field"))


def listing(folder: Path, game: int, slot: int, kinds: list) -> list[Row]:
    """Every answer kept for this slot's village, newest first."""
    villages = _villages(folder, game, slot)
    found = decisions.load(Path(folder), game, slot)
    renamed = decisions.aliases(found)
    held = {}
    for kind in kinds:
        for key, (q, d) in getattr(kind, "remembered", {}).items():
            held[ident_of(d)] = (kind, key, q)
    rk = next((k for k in kinds if getattr(k, "id", None) == "reconcile"), None)
    import vv_reconcile
    # A contradiction answered here is also kept by its identity (vv_log_contradictions.remember): one row.
    shown_left = {_left_ident(d) for d in found if d.get("kind") == KIND}
    rows = []
    for d in found:
        kind = d.get("kind")
        if kind == decisions.LEFT_KIND and d.get("field") in shown_left:
            continue
        if kind not in LISTED or (villages is not None and d.get("village") not in villages
                                  and d.get("village") is not None):
            continue
        ident = ident_of(d)
        answer = str(d.get("verdict", ""))
        date = str(d.get("date", ""))
        if kind == KIND:
            live = held.get(ident)
            where = (IDENTITY_LABEL if d.get("source") == IDENTITY_SOURCE
                     else f"{LISTED[kind]}: {d.get('label') or d.get('source')}")
            rows.append(Row(ident, where,
                            str(d.get("question") or d.get("field")), answer, date,
                            None if d.get("alone") else live is not None,
                            [o for o in d.get("options") or [] if isinstance(o, str)], live))
        elif kind == "reconcile":
            live = None
            if rk is not None:
                key = vv_reconcile.answer_key(Path(folder), str(d.get("field")), renamed)
                # An answer kept under an older id: the question it holds for now (vv_reconcile migrated).
                moved = {kept: qid for qid, (kept, _a) in (rk.context.get("migrated") or {}).items()}
                key = moved.get(vv_reconcile._answer_id(Path(folder), str(d.get("field"))), key)
                hit = getattr(rk, "remembered", {}).get(key)
                if hit is not None:
                    live = (rk, key, hit[0])
            text = live[2].text if live else f"Reconciliation question {d.get('field')}"
            rows.append(Row(ident, LISTED[kind], text, answer, date, live is not None,
                            list(live[2].options) if live else [], live))
        elif kind == "born_arrived":
            rows.append(Row(ident, LISTED[kind], f"{d.get('name')} (head {d.get('head')}, body {d.get('body')}): a "
                            "backfilled \"How: unknown\" Arrived record of a villager already recorded. Remove it?",
                            f"Remove; Retroactively edit records? No (the log left as it is)", date, True))
        elif kind == "contradiction_left":
            rows.append(Row(ident, LISTED[kind], f"Contradiction: {d.get('field')}",
                            "Left in the past records (Retroactively edit records? No, or Keep both)", date, True))
        elif kind == "grave":
            rows.append(Row(ident, LISTED[kind], f"The grave of {d.get('name')} (head {d.get('head')}, body "
                            f"{d.get('body')}): {d.get('field')}", f"{d.get('verdict')}, the records left as they "
                            "were", date, True))
    return sorted(rows, key=lambda r: r.date, reverse=True)


def change(folder: Path, game: int, slot: int, changed: dict[tuple, str], cleared: set[tuple],
           now: datetime | None = None) -> list[str]:
    """The section's changes to answers no question is asked about now (the held-back ones are asked
    again in Repair, so their new answer is kept and applied as a first answer is): `changed` sets a
    new answer, `cleared` takes an answer out (its question is asked again).  Returns the lines for the
    Repairs Made record."""
    if not changed and not cleared:
        return []
    when = (now or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    lines: list[str] = []

    def edit(found: list[dict]) -> list[dict]:
        # A contradiction's answer cleared takes the identity an older build kept for it too
        # ("contradiction_left", vv_log_contradictions.remember), or it would still hold.
        gone = {_left_ident(d) for d in found if ident_of(d) in cleared and d.get("kind") == KIND}
        out = []
        for d in found:
            ident = ident_of(d)
            if d.get("kind") == decisions.LEFT_KIND and d.get("field") in gone:
                continue
            if ident in cleared:
                lines.append(f"Answer cleared (asked again): {str(d.get('question') or d.get('field'))[:160]} -- "
                             f"was: {d.get('verdict')}")
                continue
            if ident in changed and changed[ident] != d.get("verdict"):
                lines.append(f"Answer changed: {str(d.get('question') or d.get('field'))[:160]} -- {changed[ident]} "
                             f"(was: {d.get('verdict')})")
                d = {**d, "verdict": changed[ident], "date": when}
            out.append(d)
        return out

    if decisions.rewrite(Path(folder), game, slot, edit) is None:
        raise OSError("the answered questions file could not be read, so no answer was changed")
    return lines
