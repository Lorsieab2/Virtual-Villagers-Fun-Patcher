"""Check Isola Grand Event Collection files (design E4 a-h) against the frozen source and the v6 format.

    python scripts/collection_check.py                  # every data/event_collection/<section>/<id>.json
    python scripts/collection_check.py FILE [FILE ...]  # just these
    python scripts/collection_check.py --report FILE    # also print the ledger summary (owner packet material)
    python scripts/collection_check.py --allow-report   # every harm-capable role with protected allow (owner review)

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
  f SAFETY    the harm-capable roles (derived here independently of the compiler): a special role among them needs
              protected allow (the owner's model of 2026-11-14; --allow-report lists every allow on a harmed role
              for the owner); VV5 roles are believers only
  g ROUND     normalize -> compile -> decompile -> normalize gives the graph back; compile is deterministic (needs
              the v6 format: ENGINE SEAM)
  h CHANCES   every node reachable; a split's weights equal unless a rarity word gives them (occasional 1/2, rare 1/4, very rare
              1/10, exceptionally rare 1/20 of a normal outcome: weights 20 / 10 / 5 / 2 / 1)
  i PICK      collection.description: the Pick Island Event list's one sentence (plain, at most DESCRIPTION_MAX
              characters, no placeholder); an owner's title change (docs/event-collection/owner-title-changes.md)
              is the title
  j GUARDIANS every text New Believers can show (title, page, variant, label, list item, description) that says
              Heathen or convert has a Guardians of Isola Rewrite form ({"patch": "guardians_of_isola"}): the
              same text with the event's pairs of docs/event-collection/guardians-wording.md made, saying neither

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
import supply_effects  # noqa: E402

sys.path.insert(0, str(lib.ROOT / "src"))

# ---- Constants the authoring rules name ---------------------------------------------------------------------------

# "occasional" (10): the V27 global rule's "minor setback/occasional" (the lead, 2026-11-14).
RARITY_WEIGHTS = {None: 20, "occasional": 10, "rare": 5, "very_rare": 2, "exceptionally_rare": 1}
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
            "v18", "v20", "v21", "v22", "v23", "v24", "v27",
            "c5", "lbl", "fwk", "sss", "cat",    # the Companion Anthology's volumes (data/event_collection/companion/)
            "lv_med", "lv_life", "lv_circle",    # the Living Event Engine's volumes (data/event_collection/living/)
            "lv_peoples", "lv_unseen", "lv_ways", "lv_auth",
            "hz_world", "hz_vol2",               # Beyond the Horizon (data/event_collection/horizon/)
            "rm",                                # Role Models and Good Examples (data/event_collection/rolemodels/)
            *lib.DRAFTS_A) \
    + tuple(v[2] for v in lib.DRAFTS_B.values()) \
    + tuple(v[2] for v in lib.DRAFTS_C.values()) \
    + tuple(v[2] for v in lib.DRAFTS_D.values()) \
    + tuple(lib.GO_SECTIONS) \
    + tuple(lib.ANTHOLOGY_SECTIONS) \
    + (lib.MIE_SECTION, "hc")       # More Island Events (mie/); the GO files (rewrites/, balance/); the drafts: set A, groups B-D (drafts_a/ .. drafts_d/); the Animals anthology; the Harshest Critic
LEDGER_KINDS = ("structural", "note", "instruction", "bank_ref", "gap", "sensitivity", "casting")
AUTHORING_TOP = ("ledger", "title_src", "inline_sets", "shared_lines", "addons", "bank_slots", "description",
                 "description_variants", "cast_only", "label_case",
                 "exact_amounts",   # the owner's own skill amounts (the GO files: "gains 20 to 30 Farming")
                 "mixer_only",      # only its mixer versions ship (More Island Events: its DLL runs the static)
                 "approximations",  # where the format cannot say the owner's spec exactly (scripts/go_events/gen_mie.py)
                 "list_title")      # the lists' title (the Harshest Critic's "(1 of 6)" .. "(6 of 6)")
# i PICK: the Pick Island Event list's sentence (story_collection.inc sc_pick_fill; its box is 306 x 52 dialog
# units in Segoe UI 9, about six lines, shared with "Not possible right now: ..."): two lines at most.
DESCRIPTION_MAX = 130          # and under story_collection.inc sc_entry.description (160 bytes)
DESCRIPTION_RE = re.compile(r"[A-Z][A-Za-z0-9 .,!?:;'-]*[.!?]")
# j GUARDIANS (the owner, 2026-11-14): with Guardians of Isola Rewrite, New Believers says neither of these.
GUARDIANS_PATCH = "guardians_of_isola"
GUARDIANS_IF = {"patch": GUARDIANS_PATCH}
GUARDIANS_WORDS = re.compile(r"heathen|convert|(?<!new )\bbelievers?\b", re.I)   # believers: the owner, 2026-11-16

# The effects keyword table (design E4e): source words that promise a change -> the effect kinds that keep it.
KEYWORDS = [
    (re.compile(r"\bfood\b(?! (?:stall|safety))", re.I), {"food"}),
    (re.compile(r"\btech(?:nology)?\b(?! (?:points?)? ?if)|\btech points\b", re.I), {"tech"}),
    (re.compile(r"\bexperience\b|\bskill\b", re.I), {"skill"}),
    (re.compile(r"\bdies\b|\bdeath\b|\bdie\b", re.I), {"kill", "die_unrecovered", "birth_then_die"}),
    (re.compile(r"\bdisappears?\b|\bvanish\w*|\bflees\b", re.I), {"vanish"}),
    (re.compile(r"\bcelebrat\w*", re.I), {"celebrate"}),
    (re.compile(r"\bdislik\w*", re.I), {"preference"}),
    (re.compile(r"\binjur\w*|\blose health\b|\bhealth\b", re.I), {"health", "health_change", "deliver_early"}),
    (re.compile(r"\bcollaps\w*", re.I), {"damage"}),
]
EFFECT_KIND = {"skill": "skill", "food": "food", "tech": "tech", "kill": "kill", "vanish": "vanish",
               "celebrate": "celebrate", "preference": "preference", "health": "health",
               "health_change": "health_change", "damage": "damage", "sick": "health", "mood": "mood",
               "action": "action", "status": "status", "pay_award": "food", "appearance": "appearance",
               "die_unrecovered": "die_unrecovered", "baby_lost": "baby_lost",
               "birth_then_die": "birth_then_die", "deliver_early": "deliver_early", "old_look": "appearance",
               "sex_change": "appearance", "presentation": "appearance"}


def effect_kinds(e: dict) -> set[str]:
    """The keyword kinds one effect answers (EFFECT_KIND; cie-v6-binary.md 39-40: a trade or supply of food or tech
    answers "food" / "tech", a group celebration or song "celebrate", group sickness or cure "health")."""
    do = e.get("do")
    out = {EFFECT_KIND.get(do, do)}
    if do == "trade":
        out |= {g for g in (e.get("give"), e.get("get")) if g in ("food", "tech")}
    elif do == "supply" and e.get("item") in ("food", "tech"):
        out.add(e["item"])
    elif do == "group":
        out |= {"celebrate"} if e.get("kind") in ("celebrate", "song") else \
            {"health"} if e.get("kind") in ("sick", "cure") else set()
    return out

PRONOUN_WORDS = {"he/she", "his/her", "him/her", "his/hers", "man/woman", "himself/herself", "woman/man", "boy/girl", "mother/father", "father/mother",
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


# The owner, 2026-11-15: in the new events the villager who dies or disappears can be anyone, of any age or status,
# children under 14 included (always, not only with No Safeguards).  A role a kill / birth_then_die / vanish /
# die_unrecovered effect lands on is cast with protected "allow" and no age minimum, except the roles below, whose
# own text needs their age (the role keeps its file's min_age; max_age, sex, skill and kinship always stay).
DEATH_EFFECTS = ("kill", "birth_then_die", "vanish", "die_unrecovered")
DEATH_ROLE_KEEPS_AGE = {
    ("lvauth20_elder_lesson", "elder"): "the elder (55+)",
    ("lvmed09_heart_falters", "elder"): "the elder (55+)",
    ("all_v27_25_crossing", "elder"): "the elder (55+)",
    ("lvmed01_borrowed_organ", "patient"): "\"a gravely ill adult\" (18+)",
    ("lvmed15_last_treatment", "patient"): "\"A gravely ill adult\" (18+)",
    ("all_v27_24_explorer", "explorer"): "\"An adult explorer leaves alone\" (18-54)",
    ("all_v20_d1_two_lives", "parent"): "the mother of the birth (nursing parent, 18+)",
    ("all_v27_10_supper", "child"): "a child (3-13) who walks off after a stranger",
    ("lbl026_midnight_raft", "teen2"): "a teenager (14-17) on a midnight raft",
    ("all_v27_13_raft", "teen1"): "a teenager (14-17) on a raft",
    ("all_v27_14_proof", "teen"): "a teenager (14-17) proving a dare",
    ("fwk046_lost_apprentice", "apprentice"): "an apprentice with a mentor (14+, the collection's apprentice age)",
    ("lvuns16_scientist", "scientist"): "a young scientist with Research (14-25)",
    ("lvuns32_watcher", "explorer"): "\"A solitary explorer\" who investigates alone (14+)",
    ("all_v27_55_deep_pool", "diver"): "a villager who \"wants to dive alone\" (14+)",
    ("all_v27_56_empty_boat", "crew1"): "a canoe's crew at sea (14+)",
    ("all_v27_56_empty_boat", "crew2"): "a canoe's crew at sea (14+)",
    ("sss018_silver_seam", "worker"): "a miner at the rock face (14+)",
}


# The owner, 2026-11-15: "LEADERS ARE NOT THE SAME AS THE CHIEF. THE LEADER CAN BE ANYONE."  A leader / council role
# is cast from any villager: no age, sex or protection limit, never the Tribal Chief requirement (only a role that is
# explicitly VV3's Chief keeps "special": "tribal_chief").
LEADER_ROLE = re.compile(r"^(?:leader|leaders|village_leader|councilor|councillor|council\w*)$")


def open_leader_roles(g: dict) -> None:
    for rid, r in (g.get("roles") or {}).items():
        if isinstance(r, dict) and r.get("kind") == "villager" and LEADER_ROLE.match(rid) \
                and r.get("special") != "tribal_chief":
            for k in ("max_age", "sex", "exclude_nursing", "exclude_special"):
                r.pop(k, None)
            r["min_age"] = 0
            r["protected"] = "allow"


def open_death_roles(g: dict) -> None:
    """The owner's rule above, on an engine graph (in place)."""
    eid = (g.get("collection") or {}).get("id")
    roles = g.get("roles") or {}
    hit = set()
    for n in (g.get("nodes") or {}).values():
        for e in n.get("effects", []) or []:
            if isinstance(e, dict) and e.get("do") in DEATH_EFFECTS and e.get("role") in roles:
                r = roles[e["role"]]
                hit.update(r.get("of", []) if r.get("kind") == "alias" else [e["role"]])
    for rid in hit:
        r = roles.get(rid)
        if not isinstance(r, dict) or r.get("kind") != "villager":
            continue
        r.pop("exclude_nursing", None)
        r.pop("exclude_special", None)
        r["protected"] = "allow"
        if (eid, rid) not in DEATH_ROLE_KEEPS_AGE:
            r["min_age"] = 0


# cie-v6-binary.md 32 (the owner, 2026-11-15): a new villager (code 27), a pregnancy (28), a nursing baby (29).
PENDING_EFFECTS = {"new_villager": 27, "pregnant": 28, "nursing": 29, "clone": 30, "body_swap": 31, "lose_name": 32,
                   "change_name": 33, "change_age": 34}
NEW_VILLAGER_AGES = ("child", "teen", "adult", "elder")
# The villagers this event made (engine 3a3651283): "$newest" / "$previous" stand for a role anywhere a villager role
# does (an effect's role, a partner, a copy, a swap); no declared role is needed.
NEW_ROLES = ("$newest", "$previous")
TARGET_EFFECTS = ("health", "preference", "skill", "sick", "action", "mood", "health_change", "cure", "young_look",
                  "old_look", "celebrate", "appearance")   # role byte 254: {"all": true} | {"skill": name} | {"random": n}
CARRIER_MIN_AGE = 18          # the carrier of a pregnancy or a nursing baby: born female, 18 or older


def _engine_knows(do: str) -> bool:
    try:
        import vv_cie_graph as cg
    except ImportError:
        return False
    return do in getattr(cg, "EFFECT_CODES", {})


def graph_for_engine(doc: dict) -> dict:
    """The collection file without its authoring-only keys: what vv_cie_graph (v6) reads."""
    g = copy.deepcopy(doc)
    open_death_roles(g)
    open_leader_roles(g)
    # "heathen_ok": true (VV5, the owner 2026-11-16: a real Isolan villager cast as vanilla does): until the engine's
    # own role flag is in vv_cie_graph, the engine graph says it as believers_only false.
    for r in (g.get("roles") or {}).values():
        if isinstance(r, dict) and r.pop("heathen_ok", None) is True:
            r["believers_only"] = False

    def scrub(x):
        if isinstance(x, dict):
            for k in ("src", "rarity", "odds"):
                x.pop(k, None)
            for v in x.values():
                scrub(v)
        elif isinstance(x, list):
            for v in x:
                scrub(v)
    for n in g.get("nodes", {}).values():
        # The owner, 2026-11-15 ("ignore weights"): every random outcome of a random node is equally likely in the
        # game.  The files keep their rarity words and weights (check h still reads them); the engine never sees them.
        for c in n.get("children") or []:
            if isinstance(c, dict):
                c.pop("weight", None)
        # Effects the engine does not know yet (new_villager 27, pregnant 28, nursing 29: cie-v6-binary.md 32) are
        # checked here (check_effects) and reach the engine once src/vv_cie_graph.py has their codes.
        if n.get("effects"):
            n["effects"] = [e for e in n["effects"]
                            if not (isinstance(e, dict) and e.get("do") in PENDING_EFFECTS and not _engine_knows(e["do"]))]
        n.pop("text_only", None)
        n.pop("set", None)
        n.pop("src_pick", None)
        n.pop("src_cut", None)
    for r in (g.get("roles") or {}).values():
        if isinstance(r, dict):
            r.pop("heathen_ok", None)    # the engine's role flag is pending (check_safety's heathen_ok rules)
    for p in g.get("pools", {}).values():
        p.pop("set", None)
        p.pop("mirror_of", None)
        p["items"] = [i["text"] if isinstance(i, dict) and set(i) <= {"text", "src"} else i for i in p["items"]]
    for k in AUTHORING_TOP:
        g.get("collection", {}).pop(k, None)
    scrub(g)
    # every new event's choice labels in title case (collection_lib), unless the file keeps the owner's case
    # (collection.label_case "source": a label whose title case would not fit the screen)
    if (doc.get("collection") or {}).get("label_case") != "source":
        lib.title_case_graph_labels(g)
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
    cuts: list = field(default_factory=list)    # the node's src_cut: [{"src": "L10598", "text": "..."}]


def text_fields(doc: dict) -> list[Field]:
    out: list[Field] = []
    col = doc.get("collection", {})
    out.append(Field("title", doc.get("title", ""), col.get("title_src"), kind="title"))
    for nid, n in doc.get("nodes", {}).items():
        if n.get("text"):
            out.append(Field(f"node {nid}", n["text"], n.get("src"), nid, picks=n.get("src_pick", []) or [],
                             cuts=n.get("src_cut", []) or []))
        for i, v in enumerate(n.get("variants", []) or []):
            # j: a Guardians of Isola Rewrite form is checked against its page's text, not the source
            out.append(Field(f"node {nid} variant {i + 1}", v.get("text", ""), v.get("src"), nid,
                             "guardians" if v.get("if") == GUARDIANS_IF else "variant"))
        for i, c in enumerate(n.get("choices", []) or []):
            # j: a choice shown only with Guardians of Isola Rewrite is its sibling's form, checked against it
            out.append(Field(f"node {nid} choice {i + 1}", c.get("label", ""), c.get("src"), nid,
                             "guardians" if c.get("if") == GUARDIANS_IF else "label"))
    for pname, p in doc.get("pools", {}).items():
        for i, it in enumerate(p.get("items", [])):
            if isinstance(it, dict):
                # j: an item shown only with Guardians of Isola Rewrite is its sibling's form, checked against it
                g = lib.guardians_split(it.get("if"))[1] == "with"
                out.append(Field(f"pool {pname} item {i + 1}", it.get("text", ""), it.get("src"),
                                 kind="guardians" if g else "item"))
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
            # a pronoun or role-sex word placeholder may also stand for either of its own words written bare in the
            # source ("(child.he/she)" for "he"): its male form is the source's word (the owner, 2026-11-16: the
            # Golden Child's and a carrier's words follow the villager)
            pair = s.rsplit(".", 1)[-1]
            if pair.lower() in PRONOUN_WORDS:
                bare = [rf"(?<![A-Za-z])[{w[0].upper()}{w[0].lower()}]{re.escape(w[1:])}(?![A-Za-z])"
                        for w in pair.split("/")]
                parts.append("(?:" + PH_RE + "|" + "|".join(bare) + ")")
            else:
                parts.append(PH_RE)
        elif kind == "brace":
            if s.lower() == "@tribe":
                # G5: the built-in tribe or village name stands for one source parenthesis group ("(tribe name)")
                parts.append(PH_RE)
            elif s.startswith("@"):
                # the source has one of the word's own values, or (the mapping rule) the Chief it replaces
                vals = sorted({v for v in words.get(s[1:], {}).values()}, key=len, reverse=True)
                alts = [re.escape(v) for v in vals] + [r"(?:[Tt]he |[Aa] )?[Cc]hiefs?"]   # the source may write "chief"
                parts.append("(?:" + "|".join(alts) + ")" if vals else r"(?!x)x")
            elif is_pool_ref(s):
                # one source parenthesis group, or the pool's own items as the source's bare "a/b/c" list
                items = (pools or {}).get(s.split(".")[0], [])
                bare = r"\s*/\s*".join(re.escape(i) for i in items)
                parts.append(f"(?:{PH_RE}|{bare})" if len(items) > 1 else PH_RE)
            else:
                count = None
                if s.startswith("#"):
                    # a count token {#babies:A|B|C} (cie-v6-binary.md 33): its options are the source's "(A/B/C)",
                    # or the token itself where the source already writes it (the GO files' rule 13)
                    count, _c, s = s.partition(":")
                alts = [text_regex(a, words, False, pools) for a in split_alts(s)]
                rx_alts = r"\(?" + r"\s*/\s*".join(alts) + r"\)?"
                if count:
                    rx_alts = f"(?:{rx_alts}|" + re.escape("{" + count + ":") + r"\|".join(alts) + r"\})"
                parts.append(rx_alts)
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


def apply_cut(p: str, cut: str) -> tuple[str, list[int]] | None:
    """`p` (a processed line) without `cut` -- a node's src_cut: the words of a sub-branch the node does not show
    ("A fall causes severe injury or death." is "A fall causes severe injury." on one page and "A fall causes death."
    on the other) -- with a ledger cut's spacing (no space before punctuation, never two, none at the ends), and the
    index map back into `p`."""
    at = p.find(cut)
    if at < 0 or not cut.strip():
        return None
    keep = [i for i in range(len(p)) if not at <= i < at + len(cut)]
    out: list[int] = []
    for k, i in enumerate(keep):
        if p[i] == " ":
            nxt = next((p[j] for j in keep[k + 1:] if p[j] != " "), "")
            if not out or p[out[-1]] == " " or nxt in ".,;:!?":
                continue
        out.append(i)
    while out and p[out[-1]] == " ":
        out.pop()
    return "".join(p[i] for i in out), out


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
               problems: list[str] | None = None, node_cuts: dict[int, list[str]] | None = None) -> Span:
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
        for cut in (node_cuts or {}).get(n, []):
            got = apply_cut(p, cut)
            if got is None:
                if problems is not None:
                    problems.append(f"src_cut {cut!r} is not on L{n} (after the ledger's cuts)")
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


def grammar_doc_fixes(source: str = lib.SOURCE_ID) -> set[tuple[int, str, str]]:
    """(line, before, after) of every fix of `source` in docs/event-collection/grammar-fixes.md (table rows
    "| L104 | `before` | `after` | ... |" for the Grand collection's source, "| companion L7542 | ..." for the
    Companion Anthology's)."""
    out = set()
    if not lib.GRAMMAR_FIXES_DOC.exists():
        return out
    prefix = "" if source == lib.SOURCE_ID else re.escape(source) + r"\s+"
    for row in lib.GRAMMAR_FIXES_DOC.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*" + prefix + r"L(\d+)\s*\|\s*`(.*?)`\s*\|\s*`(.*?)`\s*\|", row)
        if m:
            out.add((int(m.group(1)), m.group(2), m.group(3)))
    return out


def shared_pools() -> dict:
    if lib.SHARED_POOLS.exists():
        return json.loads(lib.SHARED_POOLS.read_text(encoding="utf-8")).get("pools", {})
    return {}


def _fixed(s: str, pairs: list[tuple[str, str]]) -> str:
    """A source line with its grammar fixes and sensitivity edits applied (the title's heading)."""
    for before, after in pairs:
        s = s.replace(before, after)
    return s


def ledger_maps(doc: dict, rep: Report):
    col = doc.get("collection", {})
    cuts: dict[int, list[str]] = {}
    whole: set[int] = set()
    sensitivity: dict[int, list[tuple[str, str]]] = {}
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
        if e["kind"] in ("sensitivity", "casting"):
            # The owner's content rules (2026-11-14): the smallest piece of the owner's words changed, logged for
            # the owner's review.  "before" must be on the one line; "after" replaces it wherever the line shows.
            before, after = e.get("before"), e.get("after")
            if len(lines) != 1 or not isinstance(before, str) or not before or not isinstance(after, str) \
                    or not e.get("why"):
                rep.add("b FIDELITY", f"{where}: a sensitivity edit names one line, before, after and why")
            elif before not in lib.normalize_source_text(lib.line(lines[0])):
                rep.add("b FIDELITY", f"{where}: {before!r} is not on L{lines[0]}")
            else:
                sensitivity.setdefault(lines[0], []).append((before, after))
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
    doc_fixes = grammar_doc_fixes(lib.active_source())
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
    for n, pairs in sensitivity.items():
        fixes.setdefault(n, []).extend(pairs)
    # A bank slot (mapping, rule 4.5): a "(N)" inside a sentence that inserts bank N's item, not a route, so the
    # trailing-route rule must not strip it ("The judges (6)." -> "The judges {JUDGING}.").
    for i, s in enumerate(doc.get("collection", {}).get("bank_slots", []) or []):
        try:
            (n,) = lib.src_lines(s["src"])
            slot = s["slot"]
        except (ValueError, KeyError, TypeError):
            rep.add("c COVERAGE", f"bank slot {i + 1}: {{\"src\": one line, \"slot\": \"(N)\"}}")
            continue
        if not re.fullmatch(r"\(\d+\)", slot) or slot not in lib.normalize_source_text(lib.line(n)):
            rep.add("c COVERAGE", f"bank slot {i + 1}: {slot!r} is not a bank number on L{n}")
            continue
        fixes.setdefault(n, []).insert(0, (slot, f"(bank {slot[1:-1]})"))
    return cuts, whole, fixes


_PAIR_WORDS = sorted({w for p in PRONOUN_WORDS for w in p.split("/")}, key=len, reverse=True)


def _ph_blind(text: str) -> str:
    """A label with each placeholder emptied: a token stands for its source group ("(friend.he/she)" for
    "(he/she)") or for one of its own words written bare ("her"), so only the words around it are compared for title
    case."""
    text = re.sub(r"\([^()]*\)", "()", text)
    return re.sub(r"(?<![A-Za-z])(?:" + "|".join(_PAIR_WORDS) + r")(?![A-Za-z])", "()", text, flags=re.I)


def check_fidelity_and_coverage(doc: dict, row: dict | None, rep: Report) -> None:
    cuts, whole, fixes = ledger_maps(doc, rep)
    words = doc.get("words", {}) or {}
    pool_texts = {name: [i["text"] if isinstance(i, dict) else i for i in p.get("items", [])]
                  for name, p in (doc.get("pools", {}) or {}).items()}
    consumed: set[int] = set(whole)
    matched: dict[int, list[tuple[int, int]]] = {}
    text_lines: set[int] = set()
    owner = lib.owner_titles().get((doc.get("collection") or {}).get("id"))
    for f in text_fields(doc):
        if f.kind == "guardians":
            continue
        if f.kind == "title":
            if f.src:
                try:
                    lines = lib.src_lines(f.src)
                except ValueError as ex:
                    rep.add("b FIDELITY", f"title: {ex}")
                    continue
                consumed.update(lines)
                head = " ".join(_fixed(lib.normalize_source_text(lib.line(n)), fixes.get(n, []))
                                for n in lines).lower()
                if owner is not None:
                    # the owner's rename (owner-title-changes.md): exactly the new title, and the old one is the
                    # heading the rename replaces
                    if f.text != owner["new"]:
                        rep.add("b FIDELITY", f"title {f.text!r} is not the owner's new title {owner['new']!r}")
                    if re.sub(r"[^a-z0-9]+", " ", owner["old"].lower()).strip() \
                            not in re.sub(r"[^a-z0-9]+", " ", head):
                        rep.add("b FIDELITY", f"the owner's old title {owner['old']!r} is not the heading on {f.src}")
                elif re.sub(r"[^a-z0-9]+", " ", f.text.lower()).strip() not in re.sub(r"[^a-z0-9]+", " ", head):
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
        node_cuts: dict[int, list[str]] = {}
        for ct in f.cuts:
            try:
                (cn,) = lib.src_lines(ct["src"])
                node_cuts.setdefault(cn, []).append(ct["text"])
            except (ValueError, KeyError, TypeError):
                rep.add("b FIDELITY", f"{f.where}: a src_cut is {{\"src\": one line, \"text\": the words cut}}")
        pick_problems: list[str] = []
        span = build_span(lines, cuts, fixes, picks, pick_problems, node_cuts)
        for x in pick_problems:
            rep.add("b FIDELITY", f"{f.where}: {x}")
        for para in [p for p in f.text.split("\n") if p.strip()]:
            if not "".join(s for k, s in scan(para) if k in ("lit", "esc")).strip():
                continue   # a paragraph of tokens only ("{WRONG}"): its items carry their own src
            rx = text_regex(para.strip(), words, pools=pool_texts)
            titled = f.kind == "label" and (doc.get("collection") or {}).get("label_case") == "title"
            m = re.search(rx, span.text, re.IGNORECASE if titled else 0)
            if not m:
                rep.add("b FIDELITY", f"{f.where} ({f.src}): {para.strip()[:90]!r} is not the source text "
                                      f"{span.text[:160]!r}")
                continue
            # (a game word "{@Chief}" is compared as the source word it stands for, in the case it is written)
            as_words = re.sub(r"\{@(\w+)\}", lambda w: w.group(1), para.strip())
            if titled and _ph_blind(as_words) != _ph_blind(lib.title_case_label(m.group(0))):
                # collection_lib.title_case_label: the owner's words, only their case changed
                rep.add("b FIDELITY", f"{f.where}: {para.strip()!r} is not the title case of the source's "
                                      f"{m.group(0)!r} ({lib.title_case_label(m.group(0))!r})")
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
    spans = [(a, b)] + [tuple(s) for s in row.get("addon_lines", [])]    # an event's add-on rows (Q14)
    own = {n for lo, hi in spans for n in range(lo, hi + 1)}
    # A line that is nothing but structural markers ("Go to (3).") needs no ledger entry.
    missing = [n for n in sorted(own) if n not in consumed and not lib.is_blank_or_separator(n)
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
    notes_lines = {n for r in manifest_rows().values()
                   if r["kind"] == "notes" and r.get("source", lib.SOURCE_ID) == lib.active_source()
                   for n in range(r["lines"][0], r["lines"][1] + 1)}
    if shared - notes_lines:
        rep.add("c COVERAGE", f"shared_lines outside a notes section: {compress(sorted(shared - notes_lines))}")
    stray = sorted(n for n in consumed if n not in own and n not in shared)
    if stray:
        rep.add("c COVERAGE", f"src outside the event's lines {a}-{b} (and its add-ons): {compress(stray)}")
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
            elif inner in ("award", "award_unit", "award2") or inner.lower() in ("made1", "made2", "renamed"):
                pass                # the engine's own (cie-v6-binary.md: the villagers the event made, a new name)
            else:
                rep.add("d TOKENS", f"{f.where}: ({inner}) is not a placeholder (a literal parenthesis is \\( \\))")
        for inner in braces_in(t):
            if inner.startswith("@"):
                if inner[1:] not in words and inner[1:] not in ("tribe", "Tribe"):   # G5: built in, filled at run time
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
            if e.get("role") and e["role"] not in roles and e["role"] not in NEW_ROLES:
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
        of = r.get("of", []) or []
        for m in ([of] if isinstance(of, str) else of):    # an "other" role names one alias (G2)
            used_roles.add(m)
            if m not in roles:
                rep.add("d TOKENS", f"role {rid}: alias member {m!r} is not declared")
    # collection.cast_only: a villager cast only for the event's age or skill gate (V27's "a child", "an elder": the
    # source names nobody, so no text shows the name)
    cast_only = set((doc.get("collection") or {}).get("cast_only", []) or [])
    for rid in sorted(cast_only):
        if rid not in roles or roles[rid].get("kind", "villager") != "villager":
            rep.add("d TOKENS", f"cast_only {rid!r} is not a villager role")
    for rid in roles:
        # a special villager's role, or one that prefers one (cie-v6-binary.md 37: the chief's title words name it)
        if rid not in used_roles and not roles[rid].get("special") and not roles[rid].get("prefer") \
                and rid not in cast_only:
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


def node_games(doc: dict) -> dict[str, set]:
    """The games each node can be reached in, following a child's plain {"game": [...]} condition (and its else)."""
    nodes = doc.get("nodes", {}) or {}
    reach: dict[str, set] = {}
    todo = [(doc.get("start"), set(doc.get("games", [])))]
    while todo:
        nid, gs = todo.pop()
        if nid not in nodes or not gs or gs <= reach.get(nid, set()):
            continue
        reach[nid] = reach.get(nid, set()) | gs
        n = nodes[nid]
        for c in (n.get("children", []) or []) + (n.get("choices", []) or []):
            cond = c.get("if")
            if isinstance(cond, dict) and set(cond) == {"game"}:
                want = set(cond["game"] if isinstance(cond["game"], list) else [cond["game"]])
                todo.append((c.get("next"), gs & want))
                if c.get("else"):
                    todo.append((c["else"], gs - want))
            else:
                todo.append((c.get("next"), gs))
                if c.get("else"):
                    todo.append((c["else"], gs))
    return reach


def check_effects(doc: dict, rep: Report) -> None:
    all_games = doc.get("games", [])
    reach = node_games(doc)
    cuts_whole = {}
    for nid, n in doc.get("nodes", {}).items():
        games = sorted(reach.get(nid, set(all_games)))
        effs = n.get("effects", []) or []
        kinds = set().union(*(effect_kinds(e) for e in effs)) if effs else set()
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
            if (doc.get("roles") or {}).get(e.get("role"), {}).get("heathen_ok") and not (
                    do in ("action", "sick", "faith", "join") or
                    (do == "health_change" and -30 <= e.get("min", 0) and e.get("max", 0) <= -5)):
                rep.add("e EFFECTS", f"{where}: a heathen_ok role takes only faith, join, actions and minor harm "
                                     "(health -5..-30, sick)")
            tg = e.get("target")
            if tg is not None:
                ok = isinstance(tg, dict) and len(tg) == 1 and (
                    tg.get("all") is True or (isinstance(tg.get("skill"), str) and tg["skill"])
                    or (isinstance(tg.get("random"), int) and not isinstance(tg.get("random"), bool)
                        and 1 <= tg["random"] <= 255))
                if do not in TARGET_EFFECTS:
                    rep.add("e EFFECTS", f"{where}: {do} takes no group target")
                elif not ok:
                    rep.add("e EFFECTS", f"{where}: target is {{\"all\": true}}, {{\"skill\": name}} or "
                                         "{\"random\": 1..255}")
                elif "role" in e:
                    rep.add("e EFFECTS", f"{where}: a group target names no role")
            if do in ("food", "tech"):
                if e.get("size") not in SIZES or "amount" in e or "per_game" in e:
                    rep.add("e EFFECTS", f"{where}: food / tech give a size word ({', '.join(SIZES)}), never "
                                         "an amount (design A3)")
                if e.get("scaled") is not True:
                    rep.add("e EFFECTS", f"{where}: food / tech are scaled (design A3)")
            elif do == "skill" and e.get("best") is True:
                pass                      # the villager's best skill (flags 32): no skill named
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
                elif (doc.get("collection") or {}).get("exact_amounts") is True:
                    # the owner's own numbers (the GO files): any amount the game can give, one sign
                    lo, hi = e.get("min", 0), e.get("max", 0)
                    if not (lo <= hi and -100 <= lo and hi <= 100 and lo and hi and (lo > 0) == (hi > 0)):
                        rep.add("e EFFECTS", f"{where}: skill {lo}..{hi} is not an amount of one sign within 100")
                else:
                    pair = (abs(e.get("min", 0)), abs(e.get("max", 0)))
                    sign = e.get("min", 0) < 0
                    if sorted(pair) not in [list(v) for v in SKILL_SIZES.values()] or \
                            (sign and not e.get("max", 0) < 0):
                        rep.add("e EFFECTS", f"{where}: skill +-{pair} is not a size of the skill table "
                                             f"{SKILL_SIZES}")
            elif do == "new_villager":
                roles = doc.get("roles", {})
                if set(e) - {"do", "copy_of", "age", "sex", "child_of_newest", "src"}:
                    rep.add("e EFFECTS", f"{where}: new_villager takes copy_of, age, sex and child_of_newest only")
                if e.get("sex", "random") not in ("random", "male", "female"):
                    rep.add("e EFFECTS", f"{where}: new_villager sex is random, male or female")
                if e.get("child_of_newest", False) not in (True, False):
                    rep.add("e EFFECTS", f"{where}: child_of_newest is true or false")
                if "copy_of" in e and not (e["copy_of"] in NEW_ROLES or roles.get(e["copy_of"], {}).get("kind") == "villager"):
                    rep.add("e EFFECTS", f"{where}: new_villager copy_of names a villager role")
                if "age" in e and e["age"] not in NEW_VILLAGER_AGES:
                    rep.add("e EFFECTS", f"{where}: new_villager age is one of {', '.join(NEW_VILLAGER_AGES)}")
            elif do in ("pregnant", "nursing"):
                roles = doc.get("roles", {})
                r = roles.get(e.get("role"), {}) if e.get("role") not in NEW_ROLES else {"kind": "villager"}
                if set(e) - {"do", "role", "partner", "any_birth_sex", "babies", "partner_may_carry", "src"}:
                    rep.add("e EFFECTS", f"{where}: {do} takes role, partner, any_birth_sex, babies and "
                                         f"partner_may_carry only")
                if "babies" in e and (e["babies"] not in ("roll", 2, 3) or isinstance(e["babies"], bool)):
                    rep.add("e EFFECTS", f"{where}: {do} babies is \"roll\", 2 or 3 (left out: one)")
                if "any_birth_sex" in e and e["any_birth_sex"] is not True:
                    rep.add("e EFFECTS", f"{where}: any_birth_sex is true or left out")
                if "partner_may_carry" in e and (e["partner_may_carry"] is not True or "partner" not in e):
                    rep.add("e EFFECTS", f"{where}: partner_may_carry is true or left out, and needs a partner")
                if r.get("kind") != "villager":
                    rep.add("e EFFECTS", f"{where}: {do} acts on a villager role")
                elif r.get("max_age") is not None and r["max_age"] < CARRIER_MIN_AGE:
                    rep.add("e EFFECTS", f"{where}: {do}'s carrier is {CARRIER_MIN_AGE} or older (born female)")
                if "partner" in e and (e["partner"] == e.get("role") or not (e["partner"] in NEW_ROLES or roles.get(e["partner"], {}).get("kind") == "villager")):
                    rep.add("e EFFECTS", f"{where}: {do} partner names another villager role")
            elif do in ("clone", "lose_name", "body_swap", "change_name", "change_age"):
                roles = doc.get("roles", {})
                keys = {"do", "role", "src"} | ({"with"} if do == "body_swap" else set()) | \
                    ({"to", "years", "max_age"} if do == "change_age" else set()) | \
                    ({"name"} if do == "change_name" else set()) | \
                    ({"count"} if do == "clone" else set())
                if do == "clone" and "count" in e and (e["count"] not in (1, 2) or isinstance(e["count"], bool)):
                    rep.add("e EFFECTS", f"{where}: clone count is 1 or 2")
                if do == "change_name" and "name" in e and not (
                        isinstance(e["name"], str) and re.fullmatch(r"[A-Za-z](?:[A-Za-z '.-]{0,29}[A-Za-z'.-])?",
                                                                    e["name"])):
                    rep.add("e EFFECTS", f"{where}: change_name name is 1-31 characters, a letter first, then "
                                         "letters, spaces, apostrophes, hyphens or full stops, no trailing space")
                if do == "change_age" and "max_age" in e and not (
                        isinstance(e["max_age"], int) and not isinstance(e["max_age"], bool) and 1 <= e["max_age"] <= 120):
                    rep.add("e EFFECTS", f"{where}: change_age max_age is 1..120 years")
                if do == "change_age" and ("to" in e) == ("years" in e):
                    rep.add("e EFFECTS", f"{where}: change_age gives to or years, one of them")
                if set(e) - keys:
                    rep.add("e EFFECTS", f"{where}: {do} takes {', '.join(sorted(keys - {'do', 'src'}))} only")
                if not (e.get("role") in NEW_ROLES or roles.get(e.get("role"), {}).get("kind") == "villager"):
                    rep.add("e EFFECTS", f"{where}: {do} acts on a villager role")
                if do == "body_swap" and (e.get("with") == e.get("role") or not (e.get("with") in NEW_ROLES or roles.get(e.get("with"), {}).get("kind") == "villager")):
                    rep.add("e EFFECTS", f"{where}: body_swap with names another villager role")
            elif do in ("cure", "young_look") and not (e.get("role") in NEW_ROLES or doc.get("roles", {}).get(e.get("role"), {}).get("kind") == "villager") and not e.get("target"):
                rep.add("e EFFECTS", f"{where}: {do} acts on a villager role or a group target")
            elif do == "repair" and e.get("structures", "any") != "any" and not (
                    isinstance(e["structures"], list) and e["structures"]):
                rep.add("e EFFECTS", f"{where}: repair structures is \"any\" or a list")
            elif do == "kill" and not e.get("cause"):
                rep.add("e EFFECTS", f"{where}: a kill names its cause")
            elif do == "die_unrecovered" and e.get("cause", "unknown") != "unknown":
                rep.add("e EFFECTS", f"{where}: die_unrecovered is always \"Unknown causes\" (the owner's rule)")
    _ = cuts_whole


HARMFUL = {"kill", "vanish", "sick", "die_unrecovered", "baby_lost", "birth_then_die", "deliver_early"}


def harmful(e: dict) -> bool:
    do = e.get("do")
    if do in HARMFUL:
        return True
    if do == "health" and e.get("max", e.get("value", 100)) < 100:
        return True
    if do == "health_change" and e.get("min", 0) < 0:
        return True
    if do == "preference" and (e.get("list") == "dislikes" or "dislike" in e) != bool(e.get("remove")):   # 24: "dislike": w | "random"
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
            # The owner's protection model (2026-11-14): "allow" on a harmed role is the author's choice where the
            # event makes sense; each is listed by --allow-report for the owner.  A harmed special role needs it.
            if r.get("special") and r.get("protected") != "allow":
                rep.add("f SAFETY", f"role {rid}: a special villager ({r['special']}) who can be harmed needs "
                                    "protected allow")
            if r.get("kind") == "stranger":
                rep.add("f SAFETY", f"role {rid}: a stranger cannot take a villager effect")
        if r.get("special") and r["special"] not in SPECIALS:
            rep.add("f SAFETY", f"role {rid}: special is one of {SPECIALS}")
        # A heathen_ok role is a believers_only false role (graph_for_engine says it so to the engine); the files
        # written by scripts/food_tech_additions.py HEATHEN_ROLES carry heathen_ok alone.
        if 5 in doc.get("games", []) and r.get("kind", "villager") == "villager" and (
                r.get("believers_only") is False or r.get("heathen_ok") is True):
            for p in heathen_ok_problems(doc, rid, r):
                rep.add("f SAFETY", f"role {rid}: {p}")
        elif r.get("heathen_ok") is not None:
            rep.add("f SAFETY", f"role {rid}: heathen_ok is only for a New Believers role with believers_only false")
    rep.notes.append(f"harm-capable roles: {', '.join(sorted(harm)) or 'none'}")


# heathen_ok (the owner, 2026-11-16: "Heathens may be involved if needed for the event to make sense"; the rules from
# the vanilla New Believers research): a New Believers role whose own text is about an Isolan / Heathen may cast a real
# Heathen villager.  The engine side (never a Heathen role character -- the Doctor, the Chief, the three Masters,
# Mommy -- never a sick one) is the engine's role flag; until it lands, graph_for_engine leaves the key out and the
# role is believers_only false.  Only these effects may reach such a role: faith gain (+5..+35), joining the tribe (the
# Defector's way), actions, and minor harm (health -5..-30, sickness); never kill, vanish, age, re-skill or less faith.
HEATHEN_WORDS = re.compile(r"\b(?:isolans?|heathens?)\b", re.I)
HEATHEN_OK_EFFECTS = {"action", "sick", "health_change", "faith", "join"}


def heathen_ok_problems(doc: dict, rid: str, r: dict) -> list[str]:
    if r.get("heathen_ok") is not True:
        return ["New Believers' Heathens are never cast (believers_only), unless the role is heathen_ok"]
    out = []
    ph = re.compile(r"\(" + re.escape(rid) + r"(?:\.[^()]*)?\)", re.I)
    texts = [f.text for f in text_fields(doc) if f.kind != "title"]
    # ...or, when it is the event's only heathen_ok role, the event's own description says so ("An Isolan neighbor
    # gives the village a carving": scripts/food_tech_additions.py HEATHEN_ROLES' vv5_gift_or_insult visitor).
    only = [k for k, v in (doc.get("roles") or {}).items() if isinstance(v, dict) and v.get("heathen_ok")] == [rid]
    described = only and HEATHEN_WORDS.search(str((doc.get("collection") or {}).get("description", "")))
    if not described and not any(ph.search(par) and HEATHEN_WORDS.search(par) for t in texts
                                 for par in t.split("\n")):
        out.append("heathen_ok, but no paragraph that names it says Isolan or Heathen")
    for n in doc.get("nodes", {}).values():
        for e in n.get("effects", []) or []:
            if e.get("role") != rid and e.get("with") != rid and e.get("partner") != rid:
                continue
            do = e.get("do")
            if do not in HEATHEN_OK_EFFECTS:
                out.append(f"heathen_ok: {do} may never reach a Heathen")
            elif do == "health_change" and not (-30 <= e.get("min", 0) <= e.get("max", 0) <= -5):
                out.append("heathen_ok: a Heathen's health may change by -5..-30 only")
            elif do == "faith" and not (5 <= e.get("min", 0) <= e.get("max", 0) <= 35):
                out.append("heathen_ok: a Heathen's faith may only rise, by 5..35")
    return out


def _members(roles: dict, rid) -> list[str]:
    """An alias's members, or an other role's alias's; [] for the rest."""
    r = roles.get(rid, {}) if isinstance(rid, str) else {}
    if r.get("kind") == "other":
        r = roles.get(r.get("of"), {})
    of = r.get("of") if r.get("kind") == "alias" else None
    return list(of) if isinstance(of, list) else []


def allow_on_harm(doc: dict) -> list[tuple[str, str, list[str]]]:
    """Every harm-capable role whose author wrote protected "allow": (role, special or "", the harmful effects that
    reach it, as "node: do").  The owner reviews each (cie-v6-binary.md 7)."""
    roles = doc.get("roles", {}) or {}
    harm = harm_roles(doc)
    out = []
    for rid, r in roles.items():
        if rid not in harm or r.get("protected") != "allow":
            continue
        what = [f"{nid}: {e['do']}" for nid, n in (doc.get("nodes", {}) or {}).items()
                for e in n.get("effects", []) or [] if harmful(e)
                and (e.get("role") == rid or rid in _members(roles, e.get("role")))]
        out.append((rid, r.get("special") or "", what))
    return out


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
            rep.add("h CHANCES", f"{where}: rarity {r!r} is not one of occasional, rare, very_rare, exceptionally_rare")
            return
    ws = [k.get("weight", 1) for k in kids]
    if all(k.get("odds") for k in kids):
        # the source's own odds ("(About 6 in 10)"; the rulebook: the text's own odds win), each child's "odds"
        # naming them: its weight is out of the split's total
        return
    if any(rar):
        for k, r, w in zip(kids, rar, ws):
            if w != RARITY_WEIGHTS[r]:
                rep.add("h CHANCES", f"{where}: weight {w} for {'a ' + r if r else 'a normal'} outcome; the "
                                     f"rarity table gives {RARITY_WEIGHTS[r]} (normal 20, occasional 10, rare 5, very rare 2, "
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
    # The collection's rows require Scrolling Popups (lead's decision, 2026-11-14), so its popups are checked with
    # scrolling on: any height fits, and the byte limit still holds.
    try:
        n2, problems = cg.validate(g, scrolling=True, shared_pools=shared)
    except Exception as ex:  # a crash is a problem, never a pass
        rep.add("a SCHEMA", f"validate raised {type(ex).__name__}: {ex}")
        return
    for p in problems:
        rep.add("a SCHEMA", p)
    norm = None if problems else n2
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


def check_description(doc: dict, rep: Report) -> None:
    """i PICK: the one sentence Pick Island Event shows for the event."""
    col = doc.get("collection") or {}
    texts = [("collection.description", col.get("description"))]
    variants = col.get("description_variants")
    if variants is not None:
        if not isinstance(variants, list) or not variants:
            rep.add("i PICK", "collection.description_variants is a list of {\"if\": condition, \"description\"}")
            variants = []
        for i, v in enumerate(variants):
            if not isinstance(v, dict) or set(v) != {"if", "description"} or v.get("if") != GUARDIANS_IF:
                rep.add("i PICK", f"collection.description_variants {i + 1} is {{\"if\": {json.dumps(GUARDIANS_IF)}, "
                                  "\"description\": \"...\"}")
                continue
            texts.append((f"collection.description_variants {i + 1}", v["description"]))
    for where, t in texts:
        if not isinstance(t, str) or not t:
            rep.add("i PICK", f"{where} is missing: Pick Island Event would show the generic line")
            continue
        if len(t) > DESCRIPTION_MAX:
            rep.add("i PICK", f"{where} is {len(t)} characters; at most {DESCRIPTION_MAX}")
        if not DESCRIPTION_RE.fullmatch(t) or "  " in t:
            rep.add("i PICK", f"{where} {t!r} is not one plain sentence (a capital first, letters, digits, "
                              "space and . , ! ? : ; ' - only, a full stop last; no placeholder)")


def guardians_form(text: str, pairs: list[tuple[str, str, str]]) -> str:
    """`text` with each (where, before, after) pair of the event made (every occurrence)."""
    for _where, before, after in pairs:
        text = text.replace(before, after)
    return text


def check_guardians(doc: dict, rep: Report) -> None:
    """j GUARDIANS: New Believers with Guardians of Isola Rewrite never shows Heathen or convert in this event.  Blind
    to the event's ids: only the texts the game shows are read."""
    if 5 not in (doc.get("games") or []):
        return
    col = doc.get("collection") or {}
    pairs = lib.guardians_pairs().get(col.get("id"), [])
    used: set[int] = set()

    def want(where: str, text: str, forms: list[str]) -> None:
        if not GUARDIANS_WORDS.search(text):
            return
        good = guardians_form(text, pairs)
        for k, (_w, before, _a) in enumerate(pairs):
            if before in text:
                used.add(k)
        if GUARDIANS_WORDS.search(good):
            rep.add("j GUARDIANS", f"{where}: {text!r} has no pair in guardians-wording.md for every Heathen / "
                                   "convert word")
        elif good not in forms:
            rep.add("j GUARDIANS", f"{where}: says Heathen or convert, and has no Guardians of Isola Rewrite form "
                                   f"{good!r}")

    if GUARDIANS_WORDS.search(doc.get("title", "")) or any(tv.get("if") == GUARDIANS_IF
                                                           for tv in doc.get("title_variants") or []):
        if GUARDIANS_PATCH not in (doc.get("patches") or []):
            rep.add("j GUARDIANS", f"patches does not name {GUARDIANS_PATCH}")
    tvs = doc.get("title_variants") or []
    want("the title", doc.get("title", ""),
         [tv.get("title") for tv in tvs[:1] if tv.get("if") == GUARDIANS_IF])
    for i, tv in enumerate(tvs):
        if tv.get("if") == GUARDIANS_IF and GUARDIANS_WORDS.search(tv.get("title", "")):
            rep.add("j GUARDIANS", f"title variant {i + 1} says Heathen or convert")
    for nid, n in (doc.get("nodes") or {}).items():
        vs = n.get("variants") or []
        if GUARDIANS_WORDS.search(n.get("text", "")) and GUARDIANS_PATCH not in (doc.get("patches") or []):
            rep.add("j GUARDIANS", f"patches does not name {GUARDIANS_PATCH}")
        # the first variant whose condition holds wins: the Guardians form comes first
        want(f"node {nid}", n.get("text", ""), [v.get("text") for v in vs[:1] if v.get("if") == GUARDIANS_IF])
        for i, v in enumerate(vs):
            if v.get("if") == GUARDIANS_IF:
                if GUARDIANS_WORDS.search(v.get("text", "")):
                    rep.add("j GUARDIANS", f"node {nid} variant {i + 1} (Guardians) says Heathen or convert")
            elif GUARDIANS_WORDS.search(v.get("text", "")):
                want(f"node {nid} variant {i + 1}", v["text"], [])
        chs = n.get("choices") or []
        for i, c in enumerate(chs):
            if c.get("if") == GUARDIANS_IF:
                if GUARDIANS_WORDS.search(c.get("label", "")):
                    rep.add("j GUARDIANS", f"node {nid} choice {i + 1} (Guardians) says Heathen or convert")
                continue
            # a label shown only without the patch: its Guardians form is the sibling choice (same next) shown
            # only with it
            forms = [o.get("label") for o in chs if o.get("if") == GUARDIANS_IF and o.get("next") == c.get("next")] \
                if c.get("if") == {"not": GUARDIANS_IF} else []
            want(f"node {nid} choice {i + 1}", c.get("label", ""), forms)
    for pname, p in (doc.get("pools") or {}).items():
        items = [it if isinstance(it, dict) else {"text": it} for it in p.get("items", [])]
        for i, it in enumerate(items):
            base, mode = lib.guardians_split(it.get("if"))
            if mode == "with":
                if GUARDIANS_WORDS.search(it.get("text", "")):
                    rep.add("j GUARDIANS", f"pool {pname} item {i + 1} (Guardians) says Heathen or convert")
                continue
            # an item shown only without the patch: its Guardians form is the twin (the same condition) shown only
            # with it
            forms = [o.get("text") for o in items if lib.guardians_split(o.get("if")) == (base, "with")] \
                if mode == "without" else []
            if mode == "without" and GUARDIANS_PATCH not in (doc.get("patches") or []):
                rep.add("j GUARDIANS", f"patches does not name {GUARDIANS_PATCH}")
            want(f"pool {pname} item {i + 1}", it.get("text", ""), forms)
    for word, per in (doc.get("words") or {}).items():
        for gn, t in per.items():
            if gn in ("5", "*"):
                want(f"word {word}", t, [])
    dvs = col.get("description_variants") or []
    want("collection.description", col.get("description") or "",
         [v.get("description") for v in dvs[:1] if isinstance(v, dict) and v.get("if") == GUARDIANS_IF])
    for k, (where, before, _after) in enumerate(pairs):
        if k not in used:
            rep.add("j GUARDIANS", f"guardians-wording.md: {before!r} ({where}) is in none of the event's texts")


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
    if col.get("source") != row.get("source", lib.SOURCE_ID):
        rep.add("a SCHEMA", f"collection.source is {row.get('source', lib.SOURCE_ID)!r} (the manifest row's source)")
    if col.get("credit") != row["credit"]["text"]:
        rep.add("a SCHEMA", "collection.credit is not the verbatim credit text of the manifest row")
    if col.get("series") != row["series"]:
        rep.add("a SCHEMA", f"collection.series {col.get('series')!r} is not the manifest's {row['series']!r}")
    if sorted(doc.get("games", [])) != sorted(row["games"]):
        rep.add("a SCHEMA", f"games {doc.get('games')} are not the manifest's {row['games']}")
    # a Guardians of Isola Rewrite form of a choice stands in for its sibling: not one more button
    choices = max((len([c for c in n.get("choices", []) or [] if c.get("if") != GUARDIANS_IF])
                   for n in doc.get("nodes", {}).values()), default=0)
    widest = max([row["choices"]] + [rows[a]["choices"] for a in (col.get("addons", []) or []) if a in rows])
    if choices != widest:
        rep.add("d TOKENS", f"the widest question has {choices} choices; the source has {widest}")
    # Add-ons (Q14): an add-on row's branches live in its event's file, listed in collection.addons. Their lines
    # join the event's for coverage, and their banks are checked as "<add-on id> <bank>" so equal bank numbers of
    # two add-ons stay distinct.
    addons = col.get("addons", []) or []
    if addons:
        row = dict(row, pools=dict(row.get("pools", {})), addon_lines=[])
        for aid in addons:
            ar = rows.get(aid)
            if ar is None or ar["kind"] != "addon":
                rep.add("a SCHEMA", f"collection.addons: {aid!r} is not an add-on row of the manifest")
                continue
            row["addon_lines"].append(ar["lines"])
            for label, size in ar.get("pools", {}).items():
                row["pools"][f"{aid} {label}"] = size
    return row


def file_source(doc: dict, rows: dict) -> str:
    """The source a file's src tags mean: its manifest row's (the file's own collection.source when it has no row;
    check_shape reports any mismatch)."""
    col = doc.get("collection") if isinstance(doc.get("collection"), dict) else {}
    row = rows.get(col.get("id"))
    src = row.get("source", lib.SOURCE_ID) if row else col.get("source")
    return src if src in lib.SOURCES else lib.SOURCE_ID


def check_file(path: Path, rows: dict | None = None) -> Report:
    rows = manifest_rows() if rows is None else rows
    rep = Report(str(path.relative_to(lib.ROOT)) if path.is_relative_to(lib.ROOT) else str(path))
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as ex:
        rep.add("a SCHEMA", f"not readable JSON: {ex}")
        return rep
    with lib.use_source(file_source(doc, rows)):     # every src tag of the file means its source's lines
        row = check_shape(doc, path, rows, rep)
        check_fidelity_and_coverage(doc, row, rep)
        check_tokens(doc, row, rep)
        check_effects(doc, rep)
        check_safety(doc, rep)
        check_chances(doc, rep)
        check_engine(doc, rep)
        check_description(doc, rep)
        check_guardians(doc, rep)
    for x in supply_effects.missing(doc):          # the owner's audit of 2026-11-17 (scripts/supply_effects.py)
        rep.add("e EFFECTS", f"{x}: the supply effect scripts/supply_effects.py lists is missing (--format adds it)")
        check_outcome_effects(doc, path, rep)
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
    fresh = {"id": row["id"], "source": row.get("source", lib.SOURCE_ID), "lines": row["lines"],
             "section": row["section"],
             "credit": row["credit"]["text"], "draw_weight": col.get("draw_weight", 1), "series": row["series"]}
    rest = {k: v for k, v in col.items() if k not in fresh}
    doc["collection"] = {**fresh, **rest}


def canonical(doc: dict) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def _outcome_effects():
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    import outcome_effects
    return outcome_effects


def with_outcome_effects(doc: dict, path: Path) -> dict:
    """The owner's text-implied outcome effects (scripts/outcome_effects.py), added to a file as it is written."""
    return _outcome_effects().apply(doc, path)


def check_outcome_effects(doc: dict, path: Path, rep: Report) -> None:
    for msg in _outcome_effects().missing(doc, path):
        rep.add("e EFFECTS", msg)


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
    """Every event file: data/event_collection/<section>/<id>.json and
    data/event_collection/companion/<section>/<id>.json and data/event_collection/living/<section>/<id>.json, and the
    same under horizon/ and rolemodels/."""
    # content_tags/ holds the content tag tables (scripts/build_event_content_tags.py), not events
    return sorted([p for p in lib.COLLECTION_DIR.glob("*/*.json") if p.parent.name != "content_tags"]
                  + list(lib.COMPANION_DIR.glob("*/*.json"))
                  + list(lib.LIVING_DIR.glob("*/*.json")) + list(lib.HORIZON_DIR.glob("*/*.json"))
                  + list(lib.ROLEMODELS_DIR.glob("*/*.json")) + list(lib.DRAFTS_A_DIR.glob("*/*.json"))
                  + list(lib.DRAFTS_B_DIR.glob("*/*.json")) + list(lib.DRAFTS_C_DIR.glob("*/*.json"))
                  + list(lib.DRAFTS_D_DIR.glob("*/*.json")) + list(lib.ANTHOLOGY_DIR.glob("*/*.json"))
                  + [p for sid in lib.GO_SOURCES for p in (lib.COLLECTION_DIR / sid).glob("*/*.json")]
                  + list(lib.MIE_DIR.glob("*/*.json")) + list(lib.CRITIC_DIR.glob("*/*.json")))


def ledger_summary(doc: dict) -> list[str]:
    col = doc.get("collection", {})
    out = [f"{doc.get('title')} ({col.get('id')}, lines {col.get('lines')})"]
    for f in doc.get("grammar_fixes", []) or []:
        out.append(f"  grammar {f['src']}: {f['before']!r} -> {f['after']!r}")
    for e in col.get("ledger", []) or []:
        if e.get("kind") in ("sensitivity", "casting"):
            out.append(f"  sensitivity {e['src']}: {e.get('before')!r} -> {e.get('after')!r} -- {e.get('why')}")
    for nid, n in doc.get("nodes", {}).items():
        for t in n.get("text_only", []) or []:
            out.append(f"  text only {t['src']} ({nid}): {t.get('what', '')} -- {t['reason']}")
    subs = set()
    with lib.use_source(file_source(doc, manifest_rows())):
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
    ap.add_argument("--allow-report", action="store_true",
                    help="list every harm-capable role with protected allow (for the owner's review), and stop")
    args = ap.parse_args(argv)
    files = [p.resolve() for p in args.files] or collection_files()
    if args.allow_report:
        n = 0
        for p in files:
            doc = json.loads(p.read_text(encoding="utf-8"))
            for rid, special, what in allow_on_harm(doc):
                n += 1
                print(f"{p.relative_to(lib.ROOT) if p.is_relative_to(lib.ROOT) else p}: role {rid}"
                      f"{f' ({special})' if special else ''} may be harmed: {'; '.join(what)}")
        print(f"{n} harm-capable role(s) with protected allow in {len(files)} file(s)")
        return 0
    rows = manifest_rows()
    bad = 0
    for p in files:
        if args.format:
            doc = json.loads(p.read_text(encoding="utf-8"))
            fill_from_manifest(doc, rows)
            supply_effects.apply(doc)                  # the existing events' supply effects (the owner, 2026-11-17)
            p.write_text(canonical(with_outcome_effects(doc, p)), encoding="utf-8", newline="\n")
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
