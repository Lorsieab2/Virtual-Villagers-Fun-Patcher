"""Write the owner's More Island Events (collection_lib.MIE: "Additional Virtual Villagers Events By Lorsieab2.txt")
as collection events, their pieces as procedural pieces, then format and check them:

    python scripts/go_events/gen_mie.py

THE COORDINATOR (2026-11-16).  The nine events "VVFP More Island Events.dll" runs (The Aspiring Adventurer, The Cave
Explorers, The Climb, The Troubling Signs, Diving for Treasure, The Mysterious Mask, The Playful Dolphins, The
Remembrance Ceremony, The Rumblings) become collection events with collection.mixer_only: they compile and validate,
get mixer versions (scripts/living_from_static.py) and procedural pieces, but their static form is in no manifest:
the originals keep running unchanged from the DLL.

Each event is a small hand-mapped section below (one function each): the owner's text word for word (the
placeholders as the engine writes them: role names, role-prefixed pronouns), the owner's chances, rewards,
requirements, protections and casting where the format can express them.  The engine draws every child of a random
node equally (collection_check.graph_for_engine drops weights: the owner's "ignore weights"), so the owner's odds are
made with repeated children ("50%, 25%, 25%" is the first child twice) or nested equal splits.  Everything the format
cannot express is an APPROXIMATION, listed in the event's ledger (kind "note", "APPROXIMATION: ...") and printed.

Nothing here touches a game, a save or an exe.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import collection_check as cc  # noqa: E402
import collection_lib as lib  # noqa: E402

PIECES_OUT = ROOT / "data" / "procedural_pieces" / "mie_seeds.json"
GRAMMAR_MARK = ("<!-- MIE grammar fixes: written by scripts/go_events/gen_mie.py -->",
                "<!-- end of MIE grammar fixes -->")
GUARDIANS_MARK = ("<!-- MIE Guardians wording: written by scripts/go_events/gen_mie.py -->",
                  "<!-- end of MIE Guardians wording -->")
GUARDIANS = "guardians_of_isola"
STORY_WHY = ("the word in the owner's story; what changes in the game is the outcome's own effects (the owner's "
             "spec beside it), so this word alone changes nothing")
PRONOUNS = {"he/she", "his/her", "him/her", "himself/herself", "man/woman", "father/mother", "mother/father"}
AWARDS = {"award", "large award", "huge award"}

# The grammar fixes this file needs (docs/event-collection/grammar-fixes.md, written below): (line, before, after,
# event, why).
GRAMMAR = [
    (718, "(fisherman/fisherwoman)", "fisher(man/woman)", "The Playful Dolphins",
     "the engine has no (fisherman/fisherwoman) word: fisher(man/woman) reads the same"),
]


def L(n: int) -> str:
    return f"L{n}"


def src_of(lines) -> str:
    if isinstance(lines, int):
        return L(lines)
    out, run = [], None
    for n in lines:
        if run and n == run[1] + 1:
            run[1] = n
        else:
            if run:
                out.append(lib.fmt_src(*run))
            run = [n, n]
    out.append(lib.fmt_src(*run))
    return ",".join(out)


def raw(n: int) -> str:
    """Line n as the checker reads it (plain typography), with this file's grammar fixes made."""
    s = lib.normalize_source_text(lib.line(n)).strip()
    for ln, before, after, _t, _w in GRAMMAR:
        if ln == n:
            s = s.replace(before, after)
    return s


class Ev:
    """One event being written: its row, roles, nodes, ledger and approximations."""

    def __init__(self, eid: str):
        data = json.loads(lib.MANIFEST.read_text(encoding="utf-8"))
        self.row = next(r for r in data["rows"] if r["id"] == eid)
        self.id = eid
        self.roles: dict[str, dict] = {}
        self.nodes: dict[str, dict] = {}
        self.ledger: list[dict] = []
        self.approx: list[str] = []
        self.pools: dict[str, dict] = {}
        self.label_lines: dict[int, list[str]] = {}
        self.cuts: dict[int, list[str]] = {}      # ledger text cuts made by hand
        self.requirement: dict = {}
        self.words: dict = {}
        self.patches: list[str] = []
        self.fixes: list[dict] = []
        self.gpairs: list[tuple[str, str, str]] = []
        self.description = ""

    # ---- text --------------------------------------------------------------------------------------------------------
    def conv(self, s: str, prons, names: dict[str, str]) -> str:
        """The owner's placeholders as the engine's: each (name...) by `names` (lower-cased inner -> role id or a
        literal replacement starting with "{"), each pronoun by `prons` (a role id, or a list taken in order)."""
        queue = list(prons) if isinstance(prons, (list, tuple)) else None

        def ph(m: re.Match) -> str:
            inner = m.group(1)
            low = inner.lower()
            if low in PRONOUNS:
                role = queue.pop(0) if queue is not None else prons
                word = "/".join(w[:1].upper() + w[1:] for w in inner.split("/")) if inner[:1].isupper() else low
                return f"({role}.{word})"
            if low in AWARDS:
                return "(award)"
            if low in names:
                v = names[low]
                if v.startswith("{"):
                    return v
                return "(" + (v[:1].upper() + v[1:] if inner[:1].isupper() else v) + ")"
            if "/" in inner:
                return m.group(0)        # a slash list the caller picks from ("(food/tech points)")
            raise ValueError(f"{self.id}: no mapping for ({inner})")
        out = re.sub(r"\(([^()]*)\)", ph, s)
        if queue:
            raise ValueError(f"{self.id}: {len(queue)} pronoun roles left over in {s[:60]!r}")
        return out

    def text(self, lines, prons, names, part: tuple[str | None, str | None] | None = None) -> str:
        """The lines' text (one paragraph each), converted; `part` (start, end) keeps the words between two markers of
        a single line (inclusive)."""
        ls = [lines] if isinstance(lines, int) else list(lines)
        paras = []
        for n in ls:
            s = raw(n)
            if part and len(ls) == 1:
                a, b = part
                i = s.index(a) if a else 0
                j = s.index(b) + len(b) if b else len(s)
                s = s[i:j]
            paras.append(s)
        return self.conv("\n".join(paras), prons, names)

    # ---- nodes -------------------------------------------------------------------------------------------------------
    def page(self, nid: str, lines, text: str, *, kids=None, effects=None, append=False, paragraph=False, **kw):
        n = {"text": text, "src": src_of(lines)}
        if append:
            n["popup"] = "append"
            if paragraph:
                n["join"] = "paragraph"
        if effects:
            n["effects"] = effects
        if kids:
            n["children"] = [k if isinstance(k, dict) else {"next": k} for k in kids]
        n.update(kw)
        self.nodes[nid] = n
        return n

    def ask(self, nid: str, lines, text: str, choices: list[tuple[str, int, str]], **kw):
        """A question: choices (owner's label words, the line they are on, next)."""
        n = {"type": "question", "text": text, "src": src_of(lines), "choices": []}
        for label, ln, nxt in choices:
            s = raw(ln)
            if label.lower() not in s.lower():
                raise ValueError(f"{self.id}: label {label!r} is not on L{ln}")
            self.label_lines.setdefault(ln, []).append(label)
            n["choices"].append({"label": lib.title_case_label(label), "next": nxt, "src": L(ln)})
        n.update(kw)
        self.nodes[nid] = n

    def branch(self, nid: str, kids: list, effects=None):
        n = {"type": "branch", "children": [k if isinstance(k, dict) else {"next": k} for k in kids]}
        if effects:
            n["effects"] = effects
        self.nodes[nid] = n

    # ---- finishing ----------------------------------------------------------------------------------------------------
    def _used_lines(self) -> set[int]:
        used = set()
        for n in self.nodes.values():
            if n.get("src"):
                used.update(lib.src_lines(n["src"]))
            # a variant's line (the owner's own Guardians of Isola form) is a ledger note: the check reads the
            # variant against the plain text and guardians-wording.md
        for p in self.pools.values():
            for it in p["items"]:
                used.update(lib.src_lines(it["src"]))
        return used

    def finish(self, title_line: int, start: str) -> dict:
        a, b = self.row["lines"]
        used = self._used_lines()
        # the label lines: everything but the labels is cut (the owner's spec words around them)
        for ln, labels in sorted(self.label_lines.items()):
            s = raw(ln)
            rx = "(" + "|".join(re.escape(x) for x in sorted(labels, key=len, reverse=True)) + ")"
            for frag in re.split(rx, s, flags=re.I):
                if frag and frag.strip() and not any(frag.lower() == x.lower() for x in labels):
                    self.ledger.append({"src": L(ln), "kind": "structural", "text": frag.strip(),
                                        "why": "the owner's spec around the choice labels"})
            used.add(ln)
        for ln, frags in self.cuts.items():
            for frag, why in frags:
                self.ledger.append({"src": L(ln), "kind": "structural", "text": frag, "why": why})
        rest = [n for n in range(a, b + 1) if n not in used and n != title_line and not lib.is_blank_or_separator(n)]
        run: list[int] = []
        for n in rest + [None]:
            if n is not None and (not run or n == run[-1] + 1):
                run.append(n)
                continue
            if run:
                self.ledger.append({"src": src_of(run), "kind": "note",
                                    "why": "the owner's spec (requirements, casting, chances, effects): carried out "
                                           "as the roles, the requirement, the branches and the pages' effects"})
            run = [n] if n is not None else []
        # text_only: an effect-table word a page says without that effect
        for n in self.nodes.values():
            if not n.get("src"):
                continue
            kinds = {cc.EFFECT_KIND.get(e.get("do"), e.get("do")) for e in n.get("effects", []) or []}
            tos = []
            for ln in lib.src_lines(n["src"]):
                s = raw(ln)
                words = []
                for rx, want in cc.KEYWORDS:
                    if not (kinds & want):
                        words += [m.group(0).lower() for m in rx.finditer(s)]
                if words:
                    tos.append({"src": L(ln), "what": ", ".join(f'"{w}"' for w in dict.fromkeys(words)),
                                "reason": STORY_WHY})
            if tos:
                n["text_only"] = tos
        col = {"id": self.id, "title_src": L(title_line), "ledger": self.ledger, "description": self.description,
               "label_case": "title", "exact_amounts": True, "mixer_only": True}
        if self.approx:
            col["approximations"] = self.approx
        doc = {"format": "vvfp-cie-graph", "version": 6, "title": self.row["title"], "games": self.row["games"],
               "collection": col}
        if self.patches:
            doc["patches"] = self.patches
        if self.words:
            doc["words"] = self.words
        if self.pools:
            doc["pools"] = self.pools
        if self.requirement:
            doc["requirement"] = self.requirement
        doc["roles"] = self.roles
        doc["start"] = start
        doc["nodes"] = self.nodes
        if self.fixes:
            doc["grammar_fixes"] = self.fixes
        return doc


def V(min_age=14, **kw) -> dict:
    """A villager role (the owner: protected villagers are never picked, so "exclude")."""
    return {"kind": "villager", "min_age": min_age, "protected": "exclude", **kw}


def food(size="normal", loss=False):
    e = {"do": "food", "size": size, "scaled": True, "defer": True}
    if loss:
        e["loss"] = True
    return [e, {"do": "pay_award"}]


def tech(size="normal", loss=False):
    e = {"do": "tech", "size": size, "scaled": True, "defer": True}
    if loss:
        e["loss"] = True
    return [e, {"do": "pay_award"}]


def kill(r):
    return {"do": "kill", "role": r, "cause": "unknown"}


def vanish(r):
    return {"do": "vanish", "role": r}


# ======================================================================================================================
# The Aspiring Adventurer (all five games), L33-302
# ======================================================================================================================

def adventurer() -> Ev:
    e = Ev("mie_adventurer")
    e.description = "A villager spots something glinting off the jungle path: go and investigate, or stay on the safe path."
    S, F = "subject", "friend"
    e.roles = {S: V(14), F: V(14), "stranger": {"kind": "stranger", "sex": "random"}}
    nm = {"name": S, "name1": S, "name2": F}
    e.requirement = {"min_eligible": 2}
    e.page("intro", [82], e.text(82, S, nm), kids=["ask"])
    e.ask("ask", [83], e.text(83, S, nm), [("Go investigate!", 85, "a_open"), ("Stay on the safe path", 86, "b_open")])
    # Choice A: the find (50 / 25 / 25: the dirt twice), then half surviving, half deadly
    e.page("a_open", 95, e.text(95, S, nm), kids=[{"next": "find_dirt"}, {"next": "find_dirt"}, {"next": "find_meat"},
                                                   {"next": "find_chest"}])
    e.page("find_dirt", 98, e.text(98, S, nm), append=True, kids=["dirt_safe", "deadly"])
    e.page("find_meat", 101, e.text(101, S, nm), append=True, kids=["meat_safe", "deadly"])
    e.page("find_chest", 104, e.text(104, S, nm), append=True, kids=["chest_safe", "deadly"])
    e.branch("dirt_safe", ["a7", "a9"])
    e.branch("deadly", ["a2", "a3", "a4", "a6"])
    # the reward only in A1, A5 and A8, by the find: a copy of each for the food and for the tech points
    for kind, cut, eff in (("food", "/tech points", food()), ("tech", "food/", tech())):
        p = "meat" if kind == "food" else "chest"
        e.branch(f"{p}_safe", [f"a1_{kind}", f"a5_{kind}", f"a8_{kind}"])
        e.page(f"a1_{kind}", 110, e.text(110, S, nm), effects=copy.deepcopy(eff),
               src_cut=[{"src": "L110", "text": cut}])
        e.page(f"a5_{kind}", [128, 129], e.text([128, 129], S, nm), effects=copy.deepcopy(eff),
               src_cut=[{"src": "L129", "text": cut}])
        e.page(f"a8_{kind}", [143, 144], e.text([143, 144], S, nm), effects=copy.deepcopy(eff),
               src_cut=[{"src": "L144", "text": cut}])
    for nid in list(e.nodes):
        n = e.nodes[nid]
        if "src_cut" in n:
            n["text"] = n["text"].replace(n["src_cut"][0]["text"], "")
    e.page("a2", [113, 114, 115], e.text([113, 114, 115], S, nm), effects=[kill(S)])
    e.page("a3", [118, 119, 120], e.text([118, 119, 120], S, nm), effects=[vanish(S)])
    st = "stranger"
    e.page("a4", [123, 124, 125], e.text([123, 124, 125], [S] * 4 + [st, st] + [S, S], nm), effects=[kill(S)])
    e.page("a6", [132, 133, 134], e.text([132, 133, 134], [S] * 4 + [st, st] + [S], nm), effects=[vanish(S)])
    e.page("a7", 137, e.text(137, S, nm))
    e.page("a9", 140, e.text(140, S, nm))
    # Choice B: home safe 90%, lost 10% (nine children to one)
    e.page("b_open", 153, e.text(153, S, nm), kids=[{"next": "b_home"}] * 9 + [{"next": "b_lost"}])
    e.page("b_home", 156, e.text(156, S, nm), append=True)
    e.page("b_lost", 158, e.text(158, S, nm), append=True,
           kids=[{"next": "lost1"}, {"next": "lost2", "if": {"game": [1, 2, 3, 4]}, "else": "lost2_vv5"},
                 {"next": "lost3"}, {"next": "lost4"}, {"next": "lost5"}, {"next": "lost6"}])
    e.page("lost1", 164, e.text(164, S, nm), kids=[{"next": "heal1"}, {"next": "heal2"}, {"next": "heal3"}])
    e.page("heal1", 167, e.text(167, S, nm), effects=[kill(S)])
    e.page("heal2", 170, e.text(170, S, nm))
    e.page("heal3", 173, e.text(173, S, nm), effects=[
        {"do": "health", "role": S, "min": 10, "max": 50},
        {"do": "preference", "role": S, "list": "dislikes", "preference": "running"}])
    e.page("lost2", 176, e.text(176, S, nm), effects=[vanish(S)])
    plain = e.text(198, S, nm)
    form = e.text(201, S, nm)
    e.page("lost2_vv5", 198, plain, effects=[{"do": "status", "role": S, "status": "heathen"}],
           variants=[{"if": {"patch": GUARDIANS}, "text": form, "src": "L201"}])
    e.gpairs.append(("page (lost2_vv5)", "heathens' tribe", "Isolans' tribe"))
    e.patches = [GUARDIANS]
    e.page("lost3", 179, e.text(179, S, nm), effects=[
        {"do": "skill", "role": S, "skills": ["Farming", "Building", "Research", "Healing"], "min": 20, "max": 30}])
    e.page("lost4", 182, e.text(182, S, nm), effects=[kill(S)])
    e.page("lost5", 185, e.text(185, S, nm), effects=[kill(S)])
    e.page("lost6", 188, e.text(188, S, nm), effects=[vanish(S)])
    e.approx += [
        "the friend in A8 is a second villager cast for every run (the event needs two who can be picked, as the "
        "owner's requirement says); a Custom Island Event bought with one villager cannot be cast (the owner's "
        "'then A8 becomes A5' is not made)",
        "the protected villagers are kept out of both roles by the engine's protected filter (nursing parents, the "
        "Golden Child, The Secret City's chief, the totems, New Believers' special roles and Heathens)",
    ]
    return e


# ======================================================================================================================
# The Cave Explorers (A New Home), L306-439
# ======================================================================================================================

def cave() -> Ev:
    e = Ev("mie_cave_explorers")
    e.description = "Two friends wonder what lies deeper in the cave: explore it together, or stay out of it."
    S, F = "subject", "friend"
    e.roles = {S: V(18), F: V(18, max_age_gap={"role": S, "years": 5})}
    e.requirement = {"min_eligible": 2, "puzzles": {"1": ["The Cave"]}}
    nm = {"name1": S, "name2": F}
    e.ask("intro", 322, e.text(322, [S, S, S], nm),
          [("Explore the Cave", 320, "explore"), ("Don't explore", 320, "dont")])
    e.page("dont", 327, e.text(327, [F, S, F, S], nm))
    e.page("explore", 332, e.text(332, [], nm), kids=["explore_q"])
    e.nodes["explore"]["children"] = [{"next": "explore_q"}]
    e.ask("explore_q", 333, e.text(333, [S], nm), [("Proceed Further", 330, "deeper"), ("Stay Here", 330, "stay")])
    e.page("deeper", 338, e.text(338, [], nm), kids=[{"next": "scream1"}, {"next": "scream2"},
                                                      {"next": "dig1"}, {"next": "dig2"}])
    # A, the chase: the screamer is name1 or name2 at random (a copy for each); one of four quotes
    e.pools["SCREAM"] = {"items": [{"text": raw(n), "src": L(n)} for n in (347, 348, 349, 350)]}
    for k, (scr, oth) in enumerate(((S, F), (F, S)), 1):
        names = dict(nm, screamer=scr, **{"other name": oth})
        e.page(f"scream{k}", 344, e.text(344, [scr], names), append=True, paragraph=True, kids=[f"what{k}"])
        e.nodes[f"scream{k}"]["children"] = [{"next": f"what{k}"}]
        e.page(f"what{k}", [347, 348, 349, 350], "{SCREAM}", append=True, paragraph=True, kids=[f"run_q{k}"])
        e.nodes[f"what{k}"].pop("src")
        e.nodes[f"what{k}"]["children"] = [{"next": f"run_q{k}"}]
        e.ask(f"run_q{k}", 353, e.text(353, [scr], names), [("Run towards the left path", 355, "run_left"),
                                                             ("Run towards the right path", 355, "run_right")])
    ends = [{"next": "fall_out"}] + [{"next": "make_up"}] * 8 + [{"next": "chasm1"}]   # 10 / 80 / 10
    t = e.text(356, [], nm)
    e.page("run_left", 356, t.replace("left/right", "left"), kids=ends, src_cut=[{"src": "L356", "text": "/right"}])
    e.page("run_right", 356, t.replace("left/right", "right"), kids=ends, src_cut=[{"src": "L356", "text": "left/"}])
    e.page("fall_out", [361, 362], e.text([361, 362], [], nm), append=True, paragraph=True)
    e.page("make_up", 365, e.text(365, [], nm), append=True, paragraph=True)
    # A3: the one who slips is name1 or name2 at random: one more equal split
    e.nodes["run_left"]["children"] = e.nodes["run_right"]["children"] = \
        [{"next": "fall_out"}] * 2 + [{"next": "make_up"}] * 16 + [{"next": "chasm1"}, {"next": "chasm2"}]
    for k, (sl, oth) in enumerate(((S, F), (F, S)), 1):
        names = dict(nm, **{"random name": sl, "other name": oth})
        e.page(f"chasm{k}", 368, e.text(368, [sl, oth], names), append=True, paragraph=True,
               effects=[vanish(sl), vanish(oth)])
    # B, the dig: the finder is name1 or name2 at random; 30 / 10 / 30 / 30
    finds = [{"next": "coins"}] * 3 + [{"next": "map"}] + [{"next": "treasure"}] * 3 + [{"next": "preserved"}] * 3
    for k, fi in enumerate((S, F), 1):
        e.page(f"dig{k}", 374, e.text(374, [], dict(nm, finder=fi)), append=True, paragraph=True, kids=finds)
    e.page("coins", 379, e.text(379, [], nm), append=True, effects=tech())
    e.page("map", 382, e.text(382, [], nm), append=True, effects=[vanish(S), vanish(F)])
    e.page("treasure", 385, e.text(385, [], nm), append=True, effects=tech("huge"))
    e.page("preserved", 388, e.text(388, [], nm), append=True, effects=food("large"))
    # Stay here
    # the answer's own page (the engine's rule), then the question: L393 split before the quote
    t = e.text(393, [F], nm)
    q = t.index('"Wait.')
    e.page("stay", 393, t[:q].rstrip(), kids=["stay_q"])
    e.ask("stay_q", 393, t[q:], [("You're right, I'll return them.", 391, "returned"),
                                 ("Curses schmurses. I'm keeping them.", 391, "keep")])
    e.branch("returned", ["ret_food", "ret_tech"])
    t = e.text(397, [F], nm)
    e.page("ret_food", 397, t.replace("(food/strange devices)", "food").replace("(food/tech points)", "food"),
           effects=food(), src_pick=[{"src": "L397", "alt": "food"}, {"src": "L397", "alt": "food"}])
    e.page("ret_tech", 397, t.replace("(food/strange devices)", "strange devices").replace("(food/tech points)",
                                                                                         "tech points"),
           effects=tech(), src_pick=[{"src": "L397", "alt": "strange devices"}, {"src": "L397", "alt": "tech points"}])
    e.page("keep", 401, e.text(401, [], nm), kids=[{"next": "k3"}, {"next": "k3"}, {"next": "k1"}, {"next": "k2"}])
    e.page("k1", 406, e.text(406, [F, F, S, S], nm), append=True, effects=[kill(F), kill(S)])
    e.page("k2", 409, e.text(409, [F, F, F], nm), append=True, effects=[kill(F)])
    e.page("k3", 412, e.text(412, [], nm), append=True, effects=tech())
    return e


# ======================================================================================================================
# The Climb (The Lost Children), L443-484
# ======================================================================================================================

def climb() -> Ev:
    e = Ev("mie_climb")
    e.description = "A researcher plans to climb the Great Falls: go with the plan, or follow the scientists' advice."
    S = "subject"
    e.roles = {S: V(18, skill={"names": ["Research"], "min": 20})}
    nm = {"name": S}
    e.ask("intro", 461, e.text(461, S, nm), [("Go with the plan", 459, "plan"),
                                            ("Follow the scientists' advice", 459, "advice")])
    e.page("plan", 466, e.text(466, S, nm), kids=[{"next": "fall"}, {"next": "summit"}])
    e.page("fall", 469, e.text(469, S, nm), effects=[kill(S)])
    e.page("summit", 472, e.text(472, S, nm),
           effects=[{"do": "skill", "role": S, "skills": ["Research"], "set": 100}, *tech("large"),
                    {"do": "celebrate", "who": "all"}])
    e.page("advice", 477, e.text(477, S, nm),
           effects=[{"do": "skill", "role": S, "skills": ["Research"], "min": 10, "max": 20}])
    return e


# ======================================================================================================================
# The Troubling Signs (The Secret City), L488-558
# ======================================================================================================================

def troubling() -> Ev:
    e = Ev("mie_troubling_signs")
    e.description = "Strange misfortunes trouble the village, and the chief must decide whose advice to follow."
    C = "leader"
    e.roles = {C: {"kind": "villager", "special": "tribal_chief", "min_age": 14}}
    for k in range(1, 5):
        e.roles[f"advisor{k}"] = V(18)
    for k in range(1, 6):
        e.roles[f"traveller{k}"] = V(18)
    e.requirement = {"min_eligible": 10, "if": {"min_population": 61}}
    nm = {"name": C, "tribe name": "{@tribe}"}
    e.page("intro", 509, e.text(509, C, nm), kids=["ask"])
    e.nodes["intro"]["children"] = [{"next": "ask"}]
    e.ask("ask", 510, e.text(510, C, nm), [("Consult the spiritual leaders", 514, "adv1"),
                                          ("Ask the magicians for advice", 517, "adv2"),
                                          ("Call the naturalists to a discussion", 520, "adv3"),
                                          ("Talk with the scientists and healers", 523, "adv4")])
    # A loss cannot be a deferred (award) (the engine: "an award is a gain"): the loss is made at once and the
    # page's automatic line says it ("The village loses food."), the owner's "Your village loses (award) food." cut.
    loss_food = {"do": "food", "size": "normal", "loss": True, "scaled": True}
    loss_tech = {"do": "tech", "size": "normal", "loss": True, "scaled": True}
    decree = {1: ([532, 533, 534], [loss_food]), 2: ([537, 538, 539], tech()), 3: ([542, 543, 544], food()),
              4: ([547, 548, 549], [loss_tech])}
    e.cuts[534] = [("Your village loses (award) food.", "the loss's own automatic line says it (an award is "
                                                        "a gain in the engine)")]
    for k, ln in enumerate((515, 518, 521, 524), 1):
        names = dict(nm, **{"random name": f"advisor{k}"})
        e.page(f"adv{k}", ln, e.text(ln, C, names), kids=[f"hear{k}"])
        e.page(f"hear{k}", 527, e.text(527, C, nm), append=True, paragraph=True, kids=[f"decree{k}"])
        lines, eff = decree[k]
        t = e.text(lines, C, nm).replace(" Your village loses (award) food.", "")
        extra = {"auto_text": True} if k in (1, 4) else {}
        e.page(f"decree{k}", lines, t, append=True, paragraph=True, effects=copy.deepcopy(eff), kids=["leave"],
               **extra)
    # the five representatives leave for good as the decree page shows (a silent branch: no automatic lines)
    e.branch("leave", [], effects=[vanish(f"traveller{j}") for j in range(1, 6)])
    e.approx += [
        "the spiritual leaders' and the scientists' losses are made at once and told by the game's own line (\"The "
        "village loses food.\" / \"The village loses tech points.\"): the engine's (award) is a gain only, so the "
        "owner's \"Your village loses (award) food / tech points.\" is not shown with the amount",
        "the five travellers and four advisors are ten villagers the event casts (min_eligible 10: the chief and "
        "nine others); the advisor not asked is cast but never named",
    ]
    return e


# ======================================================================================================================
# Diving for Treasure (The Secret City), L561-616
# ======================================================================================================================

def diving() -> Ev:
    e = Ev("mie_diving")
    e.description = "A diver sees something shimmering at the bottom of the reef: swim deeper, or better not."
    S, D = "subject", "doctor"
    e.roles = {S: V(18), D: V(18)}
    nm = {"name": S, "random name": D}
    e.ask("intro", 569, e.text(569, S, nm), [("Swim deeper", 571, "deeper"), ("Better not", 609, "better")])
    e.page("deeper", 572, e.text(572, S, nm), kids=[{"next": "doubloons"}, {"next": "buoy"}, {"next": "container"},
                                                    {"next": "tank"}])
    e.page("doubloons", 577, e.text(577, S, nm), append=True, paragraph=True, effects=tech())
    e.page("buoy", 580, e.text(580, S, nm), append=True, paragraph=True)
    e.page("container", 583, e.text(583, S, nm), append=True, paragraph=True, effects=food())
    e.page("tank", 586, e.text(586, S, nm), append=True, paragraph=True,
           kids=[{"next": "ashore"}] * 3 + [{"next": "sinks"}])
    e.page("ashore", 591, e.text(591, S, nm), append=True, paragraph=True,
           effects=[{"do": "preference", "role": S, "list": "dislikes", "preference": "swimming"}])
    e.page("sinks", [594, 595], e.text([594, 595], S, nm), append=True, paragraph=True,
           kids=[{"next": "dies"}, {"next": "lost"}] + [{"next": "rescued"}] * 4)
    e.page("dies", 600, e.text(600, S, nm), append=True, paragraph=True, effects=[kill(S)])
    e.page("lost", 603, e.text(603, S, nm), append=True, paragraph=True, effects=[vanish(S)])
    e.page("rescued", [606, 607], e.text([606, 607], S, nm), append=True, paragraph=True,
           effects=[{"do": "skill", "role": S, "skills": ["Healing"], "min": 10, "max": 20}])
    e.page("better", 610, e.text(610, S, nm),
           effects=[{"do": "skill", "role": S, "skills": ["Parenting"], "min": 10, "max": 20}])
    e.approx.append("after the sinking: dies 1 in 6, disappears 1 in 6, rescued 4 in 6 (16.7% / 16.7% / 66.7%) for "
                    "the owner's 17% / 17% / 66%: the engine draws equal children")
    return e


# ======================================================================================================================
# The Mysterious Mask (The Tree of Life), L619-691
# ======================================================================================================================

def mask() -> Ev:
    e = Ev("mie_mysterious_mask")
    e.description = "Children playing at the forest's edge find a strange carved mask: wait, cry for help, or walk."
    C1, C2 = "child1", "child2"
    child = {"kind": "villager", "min_age": 0, "max_age": 13, "protected": "exclude"}
    e.roles = {C1: dict(child), C2: dict(child), "child3": dict(child, optional=True),
               "child4": dict(child, optional=True)}
    for k in range(1, 6):
        e.roles[f"volunteer{k}"] = V(18)
    e.requirement = {"min_eligible": 7, "if": {"all": [{"min_population": 61}, {"min_children": 2}]}}
    nm = {"name1": C1, "name2": C2}
    s = raw(639)
    cut = s.index("What shall they do?")
    e.page("intro", 639, e.conv(s[:cut].rstrip(), [C1, C1], nm), kids=["ask"])
    e.nodes["intro"]["children"] = [{"next": "ask"}]
    e.ask("ask", 639, "What shall they do?", [("Wait for their parents to come", 637, "wait"),
                                              ("Cry for help", 637, "cry"),
                                              ("Walk towards the clearing", 637, "clearing"),
                                              ("Walk towards the forest", 637, "forest")])
    e.page("wait", 643, e.text(643, [C1], nm), kids=["f_waited"])
    e.page("cry", 646, e.text(646, [C1], nm), kids=["f_cried"])
    e.page("clearing", 649, e.text(649, [C1], nm), kids=["back", "lost"])
    e.page("forest", 652, e.text(652, [C1], nm), kids=["back", "lost"])
    e.page("back", 655, e.text(655, [C1], nm), append=True, kids=["f_back"])
    e.page("lost", 658, e.text(658, [], nm), append=True,
           kids=["captured", "rescued", "rescued", "rescued"])    # 25 / 75
    e.page("captured", 661, e.text(661, [], nm), append=True, effects=[vanish(C1), vanish(C2)],
           kids=[{"next": "cap3", "if": {"role": "child3"}, "else": "cap4q"}])
    e.branch("cap3", [{"next": "cap4", "if": {"role": "child4"}, "else": "f_captured"}], effects=[vanish("child3")])
    e.branch("cap4q", [{"next": "cap4", "if": {"role": "child4"}, "else": "f_captured"}])
    e.branch("cap4", ["f_captured"], effects=[vanish("child4")])
    e.page("rescued", 664, e.text(664, [C1, C1, C1, C1, C1], nm), append=True, kids=["f_rescued"])
    for nid in ("wait", "cry", "clearing", "forest", "back", "lost", "rescued"):
        e.nodes[nid]["children"] = [k if isinstance(k, dict) else {"next": k} for k in e.nodes[nid]["children"]]
    for tag, ln, mark in (("captured", 672, "(captured)"), ("rescued", 673, "(rescued)"),
                          ("back", 674, "(made it back)"), ("waited", 675, "(waited)"), ("cried", 676, "(cried)")):
        body = raw(ln)
        assert body.startswith(mark + " "), (ln, body[:20])
        e.page(f"f_{tag}", [669, ln], e.text(669, [], nm) + " " + e.conv(body[len(mark) + 1:], [], nm),
               kids=["f_end_short" if tag == "rescued" else "f_end"])
        e.cuts.setdefault(ln, []).append((mark, "which way to the elders the line is for: the page's own path"))
    gone = [vanish(f"volunteer{k}") for k in range(1, 6)]
    e.page("f_end", [679, 680, 681], e.text([679, 680, 681], [], nm), append=True, paragraph=True,
           effects=copy.deepcopy(gone))
    # After a walk, lost and rescued, the one text (the click to the end) would be about 50 bytes over The Tree of
    # Life's 1990 at most with the longest names.  The elders' words there open a fresh scroll page ("new_page",
    # cie-v6-binary.md 19a: a popup node that starts the event's one popup afresh), so the owner's whole L679-681,
    # "The other villagers rally behind them, and hope for an end to the madness." included, shows on every path.
    e.page("f_end_short", [679, 680, 681], e.text([679, 680, 681], [], nm), new_page=True,
           effects=copy.deepcopy(gone))
    e.approx += [
        "the group is two children always and a third and fourth when the village has them (optional roles); the "
        "owner's 'preferably 3-4' is the engine's casting: an optional role is filled whenever someone fits",
        "the five volunteers are five adults the event casts (any adult, family ties don't matter)",
    ]
    return e


# ======================================================================================================================
# The Playful Dolphins (The Tree of Life), L694-732
# ======================================================================================================================

def dolphins() -> Ev:
    e = Ev("mie_dolphins")
    e.description = "A villager sees dolphins playing just offshore: swim towards them, or hang back."
    S = "subject"
    e.roles = {S: V(14)}
    e.requirement = {"min_eligible": 2}
    nm = {"name": S}
    e.ask("intro", 710, e.text(710, S, nm), [("Swim towards the dolphins", 708, "swim"), ("Hang back", 708, "hang")])
    e.page("swim", 714, e.text(714, S, nm), kids=[{"next": "hunt"}, {"next": "slap"}])
    e.page("hunt", [717, 718], e.text([717, 718], S, nm), append=True,
           effects=[{"do": "skill", "role": S, "skills": ["Farming"], "set": 100}, *food("large")])
    e.page("slap", 721, e.text(721, S, nm), append=True,
           effects=[{"do": "health_change", "role": S, "min": -50, "max": -30}])
    e.page("hang", 725, e.text(725, S, nm), effects=food("small"))
    e.fixes.append({"src": "L718", "before": "(fisherman/fisherwoman)", "after": "fisher(man/woman)"})
    e.approx.append("'loses 30 to 50% health' is a health change of -30..-50 points (the engine clamps at 1: "
                    "never dies from it)")
    return e


# ======================================================================================================================
# The Remembrance Ceremony (all five games), L735-769
# ======================================================================================================================

HONOR = {1: ["Honoring the Dead"], 2: ["Honoring the Dead (Day of Honor)", "Reflecting"],
         3: ["Honoring the Dead", "Reflecting"], 4: ["Honoring the dead (Day of Honor)"],
         5: ["Honoring the dead [Day of Honor]"]}


def remembrance() -> Ev:
    e = Ev("mie_remembrance")
    e.description = "The villagers gather for the Day of Remembrance, to honor those who came before them."
    e.roles = {}
    kids = []
    for g, acts in HONOR.items():
        for k, act in enumerate(acts, 1):
            nid = f"day{g}_{k}"
            e.page(nid, 751, raw(751), effects=[{"do": "action", "target": {"all": True}, "action": act}])
            kids.append({"next": nid, "if": {"game": g}})
    e.branch("start", kids)
    e.approx += [
        "everyone honors (or, in The Lost Children and The Secret City, everyone reflects: one of the two for the "
        "whole village, 50% each) -- the owner's 50% per villager needs a per-villager pick the format lacks",
        "the requirement (at least one grave; New Believers also The Last Heathen done) has no condition in the "
        "format: not checked",
        "the feast's 10 food a villager has no effect in the format: not made",
        "New Believers' hovel destination (with the Memorial Actions patch) is not made: everyone honors at the "
        "mausoleum's action",
    ]
    return e


# ======================================================================================================================
# The Rumblings (all five games), L772-812
# ======================================================================================================================

def rumblings() -> Ev:
    e = Ev("mie_rumblings")
    e.description = "A violent shaking damages some of the village's buildings, and the builders have work to do."
    e.roles = {}
    puzzles = {str(g): [p for p in __import__("vv_cie_graph").PUZZLES[g] if "not on the Puzzles screen" not in p
                        and not (g == 5 and p in ("The clothing hut", "The love shack", "The nursery school building"))]
               for g in range(1, 6)}
    e.requirement = {"puzzles": puzzles}
    e.page("start", 784, raw(784), effects=[{"do": "damage", "structures": "any", "min": 10, "max": 100}])
    e.approx += [
        "one structure is damaged (10-100%), the engine's pick; the owner's 25% each, at least one, needs a "
        "per-structure roll the format lacks",
        "the structures it may damage are the engine's 'any' (the owner's lists exclude the puzzle buildings and New "
        "Believers' nursery: the engine's own damage rules)",
        "every puzzle of the game's Puzzles screen is required (the patcher's lists: 15 in A New Home, 16 in the "
        "others but New Believers' 11); the 'one finished hut' requirement is not checked",
    ]
    return e


EVENTS = (adventurer, cave, climb, troubling, diving, mask, dolphins, remembrance, rumblings)


# ---- Procedural pieces -------------------------------------------------------------------------------------------------

def pieces_of(doc: dict) -> list[dict]:
    """A setup (the first question's text), its approaches (each choice: its label and its answer's first page) and
    its outcomes (each page that ends a path), as the GO seeds' pieces (data/procedural_pieces/go_seeds.json)."""
    nodes, eid = doc["nodes"], doc["collection"]["id"]
    q = next((n for n in nodes.values() if n.get("type") == "question"), None)
    if q is None:
        return []
    fam = eid
    slots = {r: {k: v for k, v in role.items() if k in ("kind", "min_age", "max_age")}
             for r, role in doc["roles"].items() if role.get("kind") == "villager"}
    base = {"age_band": 0, "event": eid, "filters": [], "games": doc["games"], "never": [], "slots": slots,
            "source": lib.MIE_ID, "speaks": [], "tags": [], "themes": [], "weight": 1}
    out = [dict(base, id=f"{eid}_setup", kind=1, mood=1, family=fam, label=doc["title"], links=[], effects=[],
                src=q["src"], text=q["text"])]

    def silent(k):        # a childless branch after a page (its effects belong to that page's outcome)
        return nodes[k].get("type") == "branch" and not nodes[k].get("children")

    def leaves(nid, seen):
        n = nodes[nid]
        kids = [c["next"] for c in n.get("children", []) or []] + [c["else"] for c in n.get("children", []) or []
                                                                     if c.get("else")]
        if n.get("type") == "question":
            return []
        if n.get("text") and kids and all(silent(k) for k in kids):
            return [nid]
        if not kids:
            return [nid]
        res = []
        for k in dict.fromkeys(kids):
            if k not in seen:
                res += leaves(k, seen | {k})
        return res
    outcomes: dict[str, list] = {}
    for i, c in enumerate(q["choices"], 1):
        first = nodes[c["next"]]
        aid = f"{eid}_a{i}"
        out.append(dict(base, id=aid, kind=2, mood=1, family=fam, label=c["label"], links=[], effects=[],
                        src=c["src"], text=first.get("text") or c["label"] + "."))
        for leaf in dict.fromkeys(leaves(c["next"], {c["next"]})):
            outcomes.setdefault(leaf, []).append(aid)
    for k, (leaf, aids) in enumerate(outcomes.items(), 1):
        n = nodes[leaf]
        if not n.get("text"):
            continue
        after = [x for c in n.get("children", []) or [] if silent(c["next"])
                 for x in nodes[c["next"]].get("effects", []) or []]
        effs = [{k2: v for k2, v in x.items() if k2 != "defer"} for x in (n.get("effects", []) or []) + after
                if x.get("do") != "pay_award"]
        deadly = any(x.get("do") in ("kill", "vanish", "die_unrecovered") for x in effs)
        out.append(dict(base, id=f"{eid}_o{k}", kind=3, mood=2 if deadly else 1, family="", label="",
                        links=[[a, 1] for a in aids], effects=effs, src=n["src"], text=n["text"]))
    return out


# ---- The files ---------------------------------------------------------------------------------------------------------

def write_section(path: Path, marks: tuple[str, str], body: list[str], heading: str) -> None:
    text = path.read_text(encoding="utf-8")
    block = marks[0] + "\n" + "\n".join(body) + "\n" + marks[1]
    if marks[0] in text:
        pre, rest = text.split(marks[0], 1)
        post = rest.split(marks[1], 1)[1]
        text = pre + block + post
    else:
        text = text.rstrip("\n") + "\n\n" + heading + "\n\n" + block + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    docs, pieces, guard = [], [], []
    with lib.use_source(lib.MIE_ID):
        for make in EVENTS:
            ev = make()
            title_line = ev.row["lines"][0]
            start = "start" if "start" in ev.nodes else "intro"
            doc = ev.finish(title_line, start)
            docs.append((lib.MIE_DIR / lib.MIE_SECTION / f"{ev.id}.json", doc))
            pieces += pieces_of(doc)
            for where, before, after in ev.gpairs:
                guard.append(f"| `{ev.id}` | {where} | {before} | {after} |")
            for a in ev.approx:
                print(f"APPROXIMATION {ev.id}: {a}")
    write_section(lib.GRAMMAR_FIXES_DOC, GRAMMAR_MARK,
                  ["The owner's More Island Events file (2026-11-16; scripts/go_events/gen_mie.py).", "",
                   "| Line | Before | After | Event | Why |", "|---|---|---|---|---|",
                   *[f"| mie L{n} | `{b}` | `{a}` | {t} | {w} |" for n, b, a, t, w in GRAMMAR]],
                  "### More Island Events")
    write_section(lib.GUARDIANS_DOC, GUARDIANS_MARK,
                  ["The owner's More Island Events file (2026-11-16): the owner's own Guardians of Isola form.", "",
                   "| Event | Where | Before | After |", "|---|---|---|---|", *guard],
                  "## More Island Events")
    lib.guardians_pairs.cache_clear()
    paths = []
    for old in lib.MIE_DIR.glob("*/*.json"):
        old.unlink()
    for p, doc in docs:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(cc.canonical(doc), encoding="utf-8", newline="\n")
        paths.append(str(p))
    body = ",\n".join(json.dumps(p, ensure_ascii=False, sort_keys=True) for p in pieces)
    PIECES_OUT.write_text('{"format": "vvfp-go-pieces", "version": 1, "pieces": [\n' + body + "\n]}\n",
                          encoding="utf-8", newline="\n")
    print(f"{len(docs)} events written, {len(pieces)} pieces")
    return cc.main(["--format", *paths])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
