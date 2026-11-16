"""Player Events (v1.35.97; the owner, 2026-11-15): island events and procedural mixer pieces a player writes in plain
text files, checked and compiled at patch time into the game's "Island Event Collection".

The owner: "if the player wants to add more they add text files to the mixer/additional events folders/sections in
the patcher in each game. or the event creator there accommodates them." and "in that patcher section, add a default
prompt so that users can paste it into an AI and get a compatible text file."  Later: "add as many features to that
section as needed so they can perfectly emulate my existing added events."

The format is docs/player-events-format.md.  In short, one .txt file holds any number of items:

* a SIMPLE event (the owner's own layouts: "Title: / Applies to: / Event: / Choice 1: / * Outcome A:" and
  "NEW-001 -- TITLE [VV1, ...]" / "[Choice]" / "(Random outcome 1 of 2)", with plain-word effect lines and the
  "ID | SLOT | EFFECT | quote" effect table);
* a FULL event (any event the engine can play: every page, question, random branch, role, list, game word, variant,
  condition and effect of docs/event-collection/cie-v6-binary.md, one line each).  The built-in collection events
  write out as FULL events and compile back to the same bytes (tests/test_player_events.py);
* a mixer PIECE (docs/event-collection/procedural-pieces.md: setup, approach, outcome, flavour line, personality
  frame), compiled into a VPCB v1 file.

Nothing here touches a save or an exe: the compiled files are written only into the patched game's own
"Virtual Villagers Fun Patcher Files" folder (outside files, the owner's rule), and the player's source files live in
the patcher's "Player Events" folder.
"""
from __future__ import annotations

import copy
import json
import os
import random
import re
import shutil
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import vv_cie_graph as cie
import vv_event_content as content
import vv_owner_layout as owner

ROOT = Path(__file__).resolve().parents[1]
PLAYER_FOLDER = ROOT / "Player Events"                     # the patcher's own folder for them
# Every shipped default file (the AI prompt, the tone reference, the style guide, the themes and outcomes lists) sits
# in "Player Events", in the patcher and in each patched game.
DEFAULTS_FOLDER = PLAYER_FOLDER
OWNER_DOCS = ROOT / "docs" / "more-island-events"
PROMPT_NAME = "Player Events - AI Prompt.txt"
TONE_NAME = "Island Event Tone Reference - Lorsieab2's Handwritten Events.txt"
TONE_SOURCE = OWNER_DOCS / TONE_NAME
# The owner's style guide (from Lorsieab2's own edits): every added event follows it, except the owner's handwritten
# ones; shipped byte for byte beside the prompt and the tone reference.
STYLE_NAME = "Isola Island Event Style Guide.txt"
STYLE_SOURCE = OWNER_DOCS / STYLE_NAME
# The owner's default lists (2026-11-15: "ship these outcome files and themes files in the patcher as default"), byte
# for byte: every theme of the added events (the "favour these themes" picker offers them) and every kind of outcome.
THEMES_NAME = "Island Event Themes - All Added Events.txt"
OUTCOMES_NAME = "Island Event Outcomes - Every Kind.txt"
# The owner's 20 rewritten events (S001-S020): the format and style example the AI prompt names.  Reference only:
# never compiled or installed as playable events.
EXAMPLE_NAME = "Example Events - Lorsieab2 (S001-S020).txt"
OWNER_FILES = (TONE_NAME, STYLE_NAME, THEMES_NAME, OUTCOMES_NAME, EXAMPLE_NAME)   # byte for byte (docs/more-island-events)


def shipped_file(name: str) -> Path:
    """One of the owner's shipped files: the "Player Events" copy, else docs/more-island-events."""
    shipped = DEFAULTS_FOLDER / name
    return shipped if shipped.is_file() else OWNER_DOCS / name


def style_guide() -> Path:
    return shipped_file(STYLE_NAME)


def default_themes(path: Path | None = None) -> list[str]:
    """The themes of the owner's themes file, as short phrases for the picker: each list line split at its commas,
    semicolons and colons, without the event names in brackets; the drafts still waiting for the owner's GO are left
    out."""
    try:
        text = (path or shipped_file(THEMES_NAME)).read_text(encoding="utf-8-sig")
    except OSError:
        return []
    out: list[str] = []
    waiting = False
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s == s.upper() and not s.startswith("-"):
            waiting = s.startswith("WAITING")
            continue
        if waiting:
            continue
        if s.startswith("- "):
            s = s[2:]
        elif not line.startswith("  "):
            continue
        s = re.sub(r"\([^)]*\)", "", s)
        for part in re.split(r"[,;:]", s):
            p = re.sub(r"\s+", " ", part).strip(" .-").lower()
            p = re.sub(r"^(and|the) ", "", p)
            if 2 < len(p) <= 48 and not re.search(r"\d", p) and p not in out:
                out.append(p)
    return out


def theme_hit(themes: Iterable[str], favour: Iterable[str]) -> bool:
    """An item's themes meet a favoured theme: the same words, or one inside the other ("sea" and "dolphins and the
    sea")."""
    fav = [f.lower().strip() for f in favour if f.strip()]
    for t in (t.lower().strip() for t in themes):
        if t and any(t == f or re.search(r"\b" + re.escape(t) + r"\b", f) or re.search(r"\b" + re.escape(f) + r"\b", t)
                     for f in fav):
            return True
    return False


RULES_NAME = "Your Rules and Themes.txt"
SETTINGS_NAME = "Player Events Settings.json"
FORMAT_DOC = ROOT / "docs" / "player-events-format.md"
COLLECTION_FOLDER = "Island Event Collection"
PATCHER_FILES = "Virtual Villagers Fun Patcher Files"
INSTALLED_FOLDER = "Player Events"                         # beside the collection, in the game's patcher folder
GAME_NAMES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life",
              5: "New Believers"}
ID_PREFIX = "pl_"
GROUP_PREFIX = "pl_"                 # a player file's group: manifest-pl_<x>.txt, pieces-pl_<x>.pcb, pl_<x>_<n>.cieg
VV1_ID_MAX = 22
ID_MAX = 30
GROUP_NAME_MAX = 9                   # "manifest-<group>.txt" within VV1's 22-character file names (the collection's rule)
THEME_FAVOUR = 3                     # a favoured theme's events and pieces weigh this much more in the draw
MAX_DRAW_WEIGHT = cie.MAX_WEIGHT
GUARDIANS_PATCH = "guardians_of_isola"
CHIEF_WORDS = {"chief": {"3": "the Chief", "*": "the village leader"},
               "Chief": {"3": "The Chief", "*": "The village leader"}}

# The rules a player may tick: each one the importer enforces (an event or piece that breaks one is left out, with
# the reason).  Free-text rules go only into the AI prompt.
RULES: dict[str, tuple[str, tuple[str, ...]]] = {
    "no_deaths": ("No deaths", ("kill", "die_unrecovered", "birth_then_die")),
    "no_disappearances": ("No disappearances", ("vanish", "die_unrecovered")),
    "no_pregnancy": ("No pregnancy, births or pregnancy loss",
                     ("pregnant", "nursing", "baby_lost", "birth_then_die", "deliver_early")),
    "no_lasting_changes": ("No lasting changes to a villager (looks, sex, name, age, body swaps, copies)",
                           ("appearance", "old_look", "sex_change", "body_swap", "lose_name", "change_name",
                            "change_age", "clone")),
    "no_losses": ("No food or tech losses", ()),
    "no_new_villagers": ("No new villagers", ("new_villager", "clone")),
}

DEADLY = ("kill", "vanish", "die_unrecovered", "birth_then_die", "baby_lost")
LAST_REPORTS: dict[int, Any] = {}    # game -> the InstallReport of its last patch (the GUI shows what was left out)


# ---- Settings ------------------------------------------------------------------------------------------------------

@dataclass
class Settings:
    """One game's Player Events choices (kept in its folder, SETTINGS_NAME)."""
    count: int = 1                                  # how many events the AI prompt asks for
    favour: list[str] = field(default_factory=list)  # favoured themes (draw weight x THEME_FAVOUR)
    only_my_themes: bool = False                    # player content limited to the favoured themes
    rules: dict[str, bool] = field(default_factory=dict)
    reference: str = ""                             # the player's own tone reference file (empty: the owner's)
    enabled: bool = True                            # install the player events at all

    def to_json(self) -> dict:
        return {"count": self.count, "favour": list(self.favour), "only_my_themes": self.only_my_themes,
                "rules": {k: True for k, v in self.rules.items() if k in RULES and v},
                "reference": self.reference, "enabled": self.enabled}

    @classmethod
    def from_json(cls, data: Any) -> "Settings":
        s = cls()
        if not isinstance(data, dict):
            return s
        try:
            s.count = max(1, min(50, int(data.get("count", 1))))
        except (TypeError, ValueError):
            s.count = 1
        s.favour = [str(t) for t in data.get("favour", []) if isinstance(t, str) and t.strip()]
        s.only_my_themes = bool(data.get("only_my_themes", False))
        rules = data.get("rules", {})
        s.rules = {k: True for k in RULES if rules.get(k)} if isinstance(rules, dict) else {}
        s.reference = str(data.get("reference", "") or "")
        s.enabled = bool(data.get("enabled", True))
        return s


def game_folder(game: int, root: Path | None = None) -> Path:
    """The game's own folder of player files: "Player Events\\VV<n> - <name>"."""
    return (root or PLAYER_FOLDER) / f"VV{game} - {GAME_NAMES[game]}"


def ensure_game_folder(game: int, root: Path | None = None) -> Path:
    folder = game_folder(game, root)
    folder.mkdir(parents=True, exist_ok=True)
    rules = folder / RULES_NAME
    if not rules.exists():
        rules.write_text(RULES_TEMPLATE, encoding="utf-8")
    return folder


def load_settings(game: int, root: Path | None = None) -> Settings:
    path = game_folder(game, root) / SETTINGS_NAME
    try:
        return Settings.from_json(json.loads(path.read_text(encoding="utf-8-sig")))
    except (OSError, ValueError):
        return Settings()


def save_settings(game: int, settings: Settings, root: Path | None = None) -> None:
    folder = ensure_game_folder(game, root)
    tmp = folder / (SETTINGS_NAME + ".tmp")
    tmp.write_text(json.dumps(settings.to_json(), indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, folder / SETTINGS_NAME)


RULES_TEMPLATE = (
    "# Your Rules and Themes for this game's Player Events.\n"
    "# Anything you write here is added to the AI prompt as rules the AI must follow.\n"
    "# A line starting with \"Themes:\" lists your themes (comma separated): the Player Events section lets you\n"
    "# favour them in the draw.  Lines starting with # are notes and are not sent.\n"
    "Themes: \n")


def read_rules(game: int, root: Path | None = None) -> str:
    try:
        return (game_folder(game, root) / RULES_NAME).read_text(encoding="utf-8-sig")
    except OSError:
        return ""


def write_rules(game: int, text: str, root: Path | None = None) -> None:
    folder = ensure_game_folder(game, root)
    tmp = folder / (RULES_NAME + ".tmp")
    tmp.write_text(text if text.endswith("\n") or not text else text + "\n", encoding="utf-8")
    os.replace(tmp, folder / RULES_NAME)


def rules_body(text: str) -> str:
    """The rules text the prompt carries: without # notes and empty lines."""
    return "\n".join(line.rstrip() for line in text.splitlines()
                     if line.strip() and not line.lstrip().startswith("#")
                     and not (line.lower().startswith("themes:") and not line.split(":", 1)[1].strip()))


def rules_themes(text: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        if line.lower().startswith("themes:"):
            out += split_list(line.split(":", 1)[1])
    return list(dict.fromkeys(t.lower() for t in out))


def split_list(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"[,;]", text) if p.strip()]


# ---- Relaxed values: JSON, with bare words for plain strings --------------------------------------------------------

_BARE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_BARE_AT = re.compile(r"[A-Za-z_@*][A-Za-z0-9_]*")
_NUMBER_AT = re.compile(r"-?\d+(?:\.\d+)?")
_DECODER = json.JSONDecoder()


def dump(v: Any) -> str:
    """A value in the relaxed form: JSON with plain words unquoted.  dump(parse(x)) round-trips exactly."""
    if v is True:
        return "true"
    if v is False:
        return "false"
    if v is None:
        return "null"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return json.dumps(v)
    if isinstance(v, str):
        return v if _BARE.match(v) and v not in ("true", "false", "null") else json.dumps(v)
    if isinstance(v, list):
        return "[" + ", ".join(dump(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{_key(k)}: {dump(x)}" for k, x in v.items()) + "}"
    raise TypeError(f"cannot write {type(v).__name__}")


def _key(k: str) -> str:
    return k if _BARE.match(k) and k not in ("true", "false", "null") else json.dumps(k)


class ValueSyntax(ValueError):
    pass


def parse_value_at(s: str, i: int) -> tuple[Any, int]:
    """One relaxed value of `s` at `i`: (value, the index after it)."""
    n = len(s)
    while i < n and s[i] in " \t":
        i += 1
    if i >= n:
        raise ValueSyntax("a value is missing")
    c = s[i]
    if c == '"':
        try:
            return _DECODER.raw_decode(s, i)
        except ValueError as exc:
            raise ValueSyntax(f"a quoted text is not closed or not valid ({exc.msg})") from None
    if c in "[{":
        close = "]" if c == "[" else "}"
        out: Any = [] if c == "[" else {}
        i += 1
        while True:
            while i < n and s[i] in " \t":
                i += 1
            if i < n and s[i] == close:
                return out, i + 1
            if c == "[":
                v, i = parse_value_at(s, i)
                out.append(v)
            else:
                k, i = parse_value_at(s, i)
                if not isinstance(k, (str, int)) or isinstance(k, bool):
                    raise ValueSyntax("a key is a word or a quoted text")
                while i < n and s[i] in " \t":
                    i += 1
                if i >= n or s[i] != ":":
                    raise ValueSyntax(f"\":\" is missing after {k!r}")
                v, i = parse_value_at(s, i + 1)
                out[str(k)] = v
            while i < n and s[i] in " \t":
                i += 1
            if i < n and s[i] == ",":
                i += 1
                continue
            if i < n and s[i] == close:
                return out, i + 1
            raise ValueSyntax(f"\",\" or \"{close}\" is missing")
    m = _NUMBER_AT.match(s, i)
    if m and (m.end() >= n or not (s[m.end()].isalnum() or s[m.end()] == "_")):
        text = m.group(0)
        return (float(text) if "." in text else int(text)), m.end()
    m = _BARE_AT.match(s, i)
    if m:
        word = m.group(0)
        return {"true": True, "false": False, "null": None}.get(word, word), m.end()
    raise ValueSyntax(f"unexpected {c!r}")


def parse_value(s: str) -> Any:
    v, i = parse_value_at(s, 0)
    if s[i:].strip():
        raise ValueSyntax(f"unexpected text after the value: {s[i:].strip()[:30]!r}")
    return v


def parse_attrs(s: str) -> dict[str, Any]:
    """key=value key=value ... (each value relaxed)."""
    out: dict[str, Any] = {}
    i, n = 0, len(s)
    while True:
        while i < n and s[i] in " \t":
            i += 1
        if i >= n:
            return out
        m = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=").match(s, i)
        if not m:
            raise ValueSyntax(f"expected key=value at {s[i:i + 30]!r}")
        v, i = parse_value_at(s, m.end())
        out[m.group(1)] = v


def dump_attrs(d: dict, skip: Iterable[str] = ()) -> str:
    return " ".join(f"{k}={dump(v)}" for k, v in d.items() if k not in skip)


# ---- What a parse gives --------------------------------------------------------------------------------------------

@dataclass
class Problem:
    file: str
    line: int
    text: str

    def __str__(self) -> str:
        return f"{self.file}, line {self.line}: {self.text}"


@dataclass
class Item:
    kind: str                              # "event" or "piece"
    file: str
    line: int
    last_line: int
    title: str
    style: str = "simple"                  # "simple", "full" or "piece"
    graph: dict | None = None              # an event's graph (before validate)
    meta: dict = field(default_factory=dict)
    piece: dict | None = None
    problems: list[Problem] = field(default_factory=list)
    code: str = ""                         # the owner's "NEW-001" code, for the effect table
    warnings: list[Problem] = field(default_factory=list)   # shown, never a reason to leave the item out

    def problem(self, line: int, text: str) -> None:
        self.problems.append(Problem(self.file, line, text))

    def warn(self, line: int, text: str) -> None:
        self.warnings.append(Problem(self.file, line, "Warning (not an error): " + text))


# The owner's rule: a "?" name only comes from a bump on the head or something like it (a fall, a fever, magic, or
# anything that takes the villager's memory), never a villager choosing or being given "?" as a name.
LOSE_NAME_WORDS = re.compile(r"(?i)\b(head\w*|bump\w*|fall\w*|fell|knock\w*|fever\w*|forg[eo]t\w*|memor\w*|"
                             r"magic\w*|spell\w*|charm\w*)\b")
LOSE_NAME_RULE = ("a \"?\" name only comes from a bump on the head or something like it (a fall, a fever, magic or "
                  "anything that takes the villager's memory), never from choosing or being given \"?\" as a name")


def lose_name_warnings(it: Item) -> None:
    """A soft warning for each page with LOSE NAME whose text says nothing of a bump, a fall, a fever, magic or a lost
    memory (the owner's rule)."""
    for nid, n in ((it.graph or {}).get("nodes") or {}).items():
        effects = n.get("effects") or []
        if not any(isinstance(e, dict) and e.get("do") == "lose_name" for e in effects):
            continue
        texts = [n.get("text") or ""] + [v.get("text") or "" for v in n.get("variants") or []]
        if not any(LOSE_NAME_WORDS.search(t) for t in texts):
            line = it.meta.get("node_lines", {}).get(nid, it.line)
            it.warn(line, f"page {nid} has LOSE NAME but its text says nothing of a head, a bump, a fall, a knock, a "
                          f"fever, forgetting, memory, magic, a spell or a charm: {LOSE_NAME_RULE}")


# The owner's rule (style guide 9): narration is always third person; first and second person only in quoted speech
# or a character's quoted thought.  A soft warning, never an error; the reward line "Your villagers gain ..." is the
# games' own wording and is left alone.
_QUOTED = re.compile(r'"[^"\n]*"|“[^”\n]*”')
_FIRST_SECOND = re.compile(r"\b(I|I'm|I've|I'll|I'd|[Mm]e|[Mm]y|[Ww]e|[Yy]ou|[Yy]our|[Yy]ou're|[Yy]ourself)\b")
_REWARD_LINE = re.compile(r"(?i)\byour villagers gain\b")


LIKES_FILE = ROOT / "data" / "player_events_likes_dislikes.json"   # the style guide's Appendix A, as data
_likes_cache: dict | None = None


def likes_table() -> dict[int, dict]:
    """Each game's like/dislike words and what each does ({"like": ..., "dislike": ...}; Appendix A)."""
    global _likes_cache
    if _likes_cache is None:
        try:
            raw = json.loads(LIKES_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = {}
        _likes_cache = {int(k[2]): {w: v for w, v in val.items() if isinstance(v, dict)}
                        for k, val in raw.items() if re.match(r"^VV[1-5]\b", k) and isinstance(val, dict)}
    return _likes_cache


def like_problems(word: str, kind: str, games: Iterable[int]) -> list[str]:
    """Why a like / dislike word is a poor choice in the event's games: missing there, or doing nothing there."""
    table = likes_table()
    out = []
    for g in games:
        words = table.get(g)
        if words is None:
            continue
        entry = words.get(word.lower())
        if entry is None:
            out.append(f"{word!r} is not a like/dislike word in VV{g}")
        elif str(entry.get(kind, "")).lower().startswith("nothing"):
            out.append(f"{kind} {word!r} does nothing in VV{g} (cosmetic)")
    return out


def likes_warnings(it: Item) -> None:
    """A soft warning for each like/dislike that is missing or does nothing in a game of the event (Appendix A); the
    AI prompt asks for per-game words from it."""
    games = (it.graph or {}).get("games", [1, 2, 3, 4, 5]) if it.kind == "event" else it.piece["games"]
    effects = [(it.meta.get("node_lines", {}).get(nid, it.line), e)
               for nid, n in ((it.graph or {}).get("nodes") or {}).items() for e in n.get("effects") or []] \
        if it.kind == "event" else list(it.piece["effects"])
    for ln, e in effects:
        if not isinstance(e, dict) or e.get("do") != "preference" or e.get("remove"):
            continue
        kind = "dislike" if "dislike" in e or e.get("list") == "dislikes" else "like"
        word = e.get(kind) or e.get("preference")
        if not isinstance(word, str) or word == cie.PREF_RANDOM:
            continue
        probs = like_problems(word, kind, games)
        if probs:
            it.warn(ln, "; ".join(probs) + " (see the style guide's Appendix A)")


def person_problem(text: str) -> str | None:
    """The first "I / me / my / we / you / your" outside quotes, or None."""
    for line in text.split("\n"):
        if _REWARD_LINE.search(line):
            continue
        bare = _QUOTED.sub(" ", re.sub(r"\([^)]*\)|\{[^}]*\}", " ", line))
        m = _FIRST_SECOND.search(bare)
        if m:
            return m.group(1)
    return None


def person_warnings(it: Item) -> None:
    """A soft warning for each page told in the first or second person outside quoted speech (style guide 9)."""
    for nid, n in ((it.graph or {}).get("nodes") or {}).items():
        for t in [n.get("text") or ""] + [v.get("text") or "" for v in n.get("variants") or []]:
            word = person_problem(t)
            if word:
                line = it.meta.get("node_lines", {}).get(nid, it.line)
                it.warn(line, f"page {nid} says {word!r} outside quoted speech: the story is told in the third "
                              "person; I / me / my / we / you / your only inside quotes")
                break


# ---- Games ---------------------------------------------------------------------------------------------------------

_GAME_WORDS = {"vv1": 1, "a new home": 1, "vv2": 2, "the lost children": 2, "vv3": 3, "the secret city": 3,
               "vv4": 4, "the tree of life": 4, "vv5": 5, "new believers": 5}


def parse_games(text: str) -> list[int] | None:
    t = text.strip().strip("[]").strip()
    low = t.lower()
    if low in ("all", "all games", "all five games", "every game", "vv1-vv5", "vv1-5", "vv1 - vv5", "1-5"):
        return [1, 2, 3, 4, 5]
    out = []
    for part in re.split(r"[,;/]| and ", low):
        part = part.strip().rstrip(".")
        if not part:
            continue
        m = re.fullmatch(r"vv([1-5])\s*-\s*(?:vv)?([1-5])", part)
        if m:
            out += range(int(m.group(1)), int(m.group(2)) + 1)
            continue
        if part.isdigit() and 1 <= int(part) <= 5:
            out.append(int(part))
        elif part in _GAME_WORDS:
            out.append(_GAME_WORDS[part])
        else:
            return None
    return sorted(set(out)) or None


def games_words(games: Iterable[int]) -> str:
    return ", ".join(f"VV{g}" for g in sorted(games))


# ---- Title Case ----------------------------------------------------------------------------------------------------

MINOR_WORDS = {"a", "an", "the", "and", "but", "or", "nor", "for", "so", "yet", "as", "at", "by", "in", "of", "on",
               "to", "up", "off", "out", "per", "via", "with", "from", "into", "onto", "than", "over", "vs"}


def title_case_problem(text: str) -> str | None:
    """None when `text` is in Title Case (or all capitals, which the game shows in title case); else the first word
    that should start with a capital."""
    plain = re.sub(r"\([^)]*\)|\{[^}]*\}", " X ", text)
    words = re.findall(r"[A-Za-z][A-Za-z'\-]*", plain)
    if not words:
        return None
    if all(w.upper() == w for w in words):
        return None
    for k, w in enumerate(words):
        if w[0].isupper():
            continue
        if k != 0 and k != len(words) - 1 and w.lower() in MINOR_WORDS:
            continue
        return w
    return None


def caps_title(text: str) -> str:
    """A title written in capitals in Title Case, the small words small ("THE BASKET LEFT IN THE RAIN": "The Basket
    Left in the Rain")."""
    t = cie.title_case(text)
    words = list(re.finditer(r"(?<![({@.\w'])[A-Za-z][A-Za-z']*", t))
    out = t
    for k, m in reversed(list(enumerate(words))):
        if 0 < k < len(words) - 1 and m.group(0).lower() in MINOR_WORDS:
            out = out[:m.start()] + m.group(0).lower() + out[m.end():]
    return out


def to_title_case(text: str) -> str:
    def fix(m: re.Match) -> str:
        w = m.group(0)
        return w if w[0].isupper() or (m.start() > 0 and w.lower() in MINOR_WORDS) else w[0].upper() + w[1:]
    return re.sub(r"(?<![({@.\w])[A-Za-z][A-Za-z']*", fix, text)


# ---- Plain-word effects (simple events and pieces) -----------------------------------------------------------------

SKILL_WORDS = {"a little": "small", "a bit": "small", "small": "small", "some": "normal", "normal": "normal",
               "a lot": "large", "large": "large", "hugely": "huge", "huge": "huge", "a great deal": "large"}
INJURY_SIZES = {"minor": (-20, -10), "": (-40, -20), "serious": (-60, -40), "grave": (-90, -60)}
DEFAULT_TARGETS = ("villager", "the villager", "subject", "")


@dataclass
class PlainEffect:
    effects: list[dict]
    roles: dict[str, dict]          # roles it needs: id -> the facts the effect asks of it (min_age, special, ...)
    note: str = ""


def _target(word: str | None) -> str | None:
    """A role id from an effect's target words, None for the event's main villager."""
    if word is None:
        return None
    w = word.strip().strip("()").strip().lower()
    w = re.sub(r"^the\s+", "", w)
    if w in DEFAULT_TARGETS:
        return None
    if w in ("newcomer", "new villager", "newest"):
        return "$newest"                  # the villager this event made last (role byte 253)
    if w in ("previous newcomer", "first newcomer", "other newcomer"):
        return "$previous"                # the one it made before (252)
    w = re.sub(r"\s+", "_", w)
    return w if cie.ID_RE.match(w) else "!" + word


_T = r"\(?([A-Za-z][A-Za-z0-9_]*(?: [A-Za-z0-9_]+)?)\)?"          # a target: one or two words, maybe in ()
EFFECT_VOCABULARY = (
    "FOOD GAIN (small|normal|large|huge)", "FOOD LOSS (size)", "TECH GAIN (size)", "TECH LOSS (size)",
    "FOOD GAIN 500", "FOOD GAIN 200 TO 800", "FOOD AWARD (size)", "TECH AWARD (size)", "PAY AWARD",
    "SKILL + <skill> a little|some|a lot|hugely", "SKILL - <skill> ...", "MASTER <skill>", "SKILL SET <skill> <0-100>",
    "LIKE + <word>", "DISLIKE + <word>", "LIKE - <word>", "DISLIKE - <word>", "LIKE + random", "DISLIKE + random",
    "INJURY <who> [(minor|serious|grave)]", "ILLNESS <who>", "HEALTH <who> +10 TO +20", "HEALTH <who> -30",
    "HEAL <who>", "DEATH <who> [CAUSE \"words\"]", "DISAPPEARS <who>", "LOST FOREVER <who>",
    "PREGNANCY LOSS <who>", "BIRTH THEN DEATH <who>", "EARLY BIRTH <who>",
    "NEW VILLAGER (child|teen|adult|elder|any)", "DUPLICATE OF <who>", "CLONE OF <who>", "CLONE OF <who> (2)",
    "TWO CLONES OF <who>",
    "PREGNANT <who> [WITH <who>] [(ANY BIRTH SEX)]", "NURSING <who> [WITH <who>] [(ANY BIRTH SEX)]",
    "NEW LOOK (head|body|both) <who>", "OLD LOOK <who>", "SEX CHANGE <who>", "BODY SWAP <who> WITH <who>",
    "LOSE NAME <who>", "CHANGE NAME <who>", "CHANGE NAME <who> TO <name>", "CHANGE AGE <who> YOUNGER|OLDER <n> YEARS",
    "CHANGE AGE <who> TO child|teen|18|adult|50|elder", "MOOD GOOD|BAD <who>", "CELEBRATE [<who>|everyone]",
    "ACTION <who> \"<the game's action words>\"", "DAMAGE (small|normal|large|huge) [ON <structures>]",
    "BECOMES HEATHEN <who>", "STORY MUTE <who>", "CURE <who>", "REPAIR", "YOUNG LOOK <who>",
    "SKILL + BEST a little|some|a lot|hugely", "EVERYONE: MOOD GOOD", "EVERY HEALER: SKILL + Healing some",
    "3 RANDOM VILLAGERS: ILLNESS", "NEW VILLAGER (adult woman)", "NEW BABY OF THE NEWCOMERS",
    "PREGNANT <who> WITH <who> (TWINS OR TRIPLETS)", "CHANGE AGE <who> OLDER <n> YEARS (NEVER PAST ELDER)")


GROUP_SKILLS = {"healer": "Healing", "builder": "Building", "farmer": "Farming", "researcher": "Research",
                "scholar": "Research", "scientist": "Research", "parent": "Parenting", "nanny": "Parenting",
                "priest": "Devotion", "devout": "Devotion"}
_GROUP = re.compile(r"^(everyone|every villager|all villagers|every (healer|builder|farmer|researcher|scholar|scientist|"
                    r"parent|nanny|priest|devout)|(\d+|one|two|three|four|five) random villagers?)\s*:\s*", re.I)
_NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}


def plain_effect(line: str) -> PlainEffect | str:
    """One plain-word effect line (docs/player-events-format.md 4): the effects and the roles they need, or the
    problem in words.  "EVERYONE: ...", "EVERY HEALER: ..." (every villager with 50 or more of that skill) and
    "3 RANDOM VILLAGERS: ..." put the effect on a group (engine 3a3651283)."""
    s = line.strip().strip("-*").strip()
    s = re.sub(r"^effect\s*:\s*", "", s, flags=re.I).strip().rstrip(".")
    m = _GROUP.match(s)
    if m:
        word = m.group(1).lower()
        target = {"all": True} if word in ("everyone", "every villager", "all villagers") else \
            {"skill": GROUP_SKILLS[m.group(2).lower()]} if m.group(2) else \
            {"random": int(m.group(3)) if m.group(3).isdigit() else _NUM_WORDS[m.group(3).lower()]}
        inner = plain_effect(s[m.end():])
        if isinstance(inner, str):
            return inner
        for e in inner.effects:
            if e["do"] not in cie.TARGET_EFFECTS:
                return f"{e['do']} cannot be given to a group (only {', '.join(cie.TARGET_EFFECTS)})"
            e.pop("role", None)
            e.pop("who", None)
            e["target"] = dict(target)
        return PlainEffect(inner.effects, {k: v for k, v in inner.roles.items() if k}, inner.note)
    roles: dict[str, dict] = {}

    def need(rid: str | None, **facts) -> str | None:
        if rid is not None and rid.startswith("!"):
            raise _Bad(f"{rid[1:]!r} is not a role name (letters, digits and _)")
        if rid is not None and rid.startswith("$"):
            return rid                    # a villager this event made: no role to cast
        key = rid or ""
        roles.setdefault(key, {}).update(facts)
        return rid

    def fx(**kw) -> dict:
        return {k: v for k, v in kw.items() if v is not None}

    try:
        m = re.fullmatch(r"(food|tech)(?: points)? (gain|loss|award)(?: \(?(small|normal|large|huge)\)?)?", s, re.I)
        if m:
            kind, how, size = m.group(1).lower(), m.group(2).lower(), (m.group(3) or "normal").lower()
            e = {"do": kind, "size": size, "scaled": True}
            if how == "loss":
                e["loss"] = True
            if how == "award":
                e["defer"] = True
            return PlainEffect([e], roles)
        m = re.fullmatch(r"(food|tech)(?: points)? (gain|loss) (\d+)(?: to (\d+))?", s, re.I)
        if m:
            sign = -1 if m.group(2).lower() == "loss" else 1
            lo, hi = int(m.group(3)), int(m.group(4) or m.group(3))
            if hi < lo:
                lo, hi = hi, lo
            e = {"do": m.group(1).lower(), "amount": sign * (hi if sign < 0 else lo), "scaled": True}
            if hi != lo:
                e["max"] = sign * (lo if sign < 0 else hi)
            return PlainEffect([e], roles)
        if re.fullmatch(r"pay (the )?award", s, re.I):
            return PlainEffect([{"do": "pay_award"}], roles)
        tail_target = None
        m = re.search(r"\s+(?:for|to|on)\s+" + _T + r"$|\s+\(([a-z][a-z0-9_]*)\)$", s, re.I)
        m2 = re.fullmatch(r"(skill|master|like|dislike).*", s, re.I)
        if m and m2:
            word = m.group(1) or m.group(2)
            if word.lower() not in SKILL_WORDS and word.lower() not in ("small", "normal", "large", "huge"):
                tail_target = _target(word)
                s = s[:m.start()]
        m = re.fullmatch(r"skill ([+-]) ([A-Za-z]+)(?: (a little|a bit|some|a lot|hugely|a great deal|small|normal|"
                         r"large|huge))?", s, re.I)
        if m:
            best = m.group(2).lower() == "best"          # SKILL + BEST: the villager's own best skill
            e = {"do": "skill", "role": need(tail_target), "skills": None if best else [m.group(2).title()],
                 "best": True if best else None, "size": SKILL_WORDS[(m.group(3) or "a little").lower()]}
            if m.group(1) == "-":
                e["loss"] = True
            return PlainEffect([fx(**e)], roles)
        m = re.fullmatch(r"cure(?:d)?(?: " + _T + r")?", s, re.I)
        if m:
            return PlainEffect([fx(do="cure", role=need(_target(m.group(1))))], roles)
        if re.fullmatch(r"repair(?: the damaged (?:huts|buildings))?", s, re.I):
            return PlainEffect([{"do": "repair", "structures": cie.DAMAGE_ANY}], roles)
        m = re.fullmatch(r"young look(?: " + _T + r")?", s, re.I)
        if m:
            return PlainEffect([fx(do="young_look", role=need(_target(m.group(1))))], roles)
        m = re.fullmatch(r"master(?:s)? ([A-Za-z]+)", s, re.I)
        if m:
            return PlainEffect([fx(do="skill", role=need(tail_target), skills=[m.group(1).title()], set=100)], roles)
        m = re.fullmatch(r"skill set ([A-Za-z]+) (\d+)", s, re.I)
        if m:
            return PlainEffect([fx(do="skill", role=need(tail_target), skills=[m.group(1).title()],
                                   set=int(m.group(2)))], roles)
        m = re.fullmatch(r"(like|dislike) ([+-]) (.+)", s, re.I)
        if m:
            word = m.group(3).strip().strip('"')
            e = {"do": "preference", "role": need(tail_target), m.group(1).lower(): word.lower()
                 if word.lower() == "random" else word}
            if m.group(2) == "-":
                e["remove"] = True
            return PlainEffect([fx(**e)], roles)
        m = re.fullmatch(r"(?:illness ?/ ?)?injury " + _T + r"(?: \((minor|serious|grave)\))?", s, re.I)
        if m and not s.lower().startswith("illness"):
            lo, hi = INJURY_SIZES[(m.group(2) or "").lower()]
            return PlainEffect([fx(do="health_change", role=need(_target(m.group(1))), min=lo, max=hi)], roles)
        m = re.fullmatch(r"(?:illness|sickness|sick|illness ?/ ?injury)(?: " + _T + ")?", s, re.I)
        if m:
            return PlainEffect([fx(do="sick", role=need(_target(m.group(1))))], roles)
        m = re.fullmatch(r"health " + _T + r" ([+-]\d+)(?: to ([+-]?\d+))?", s, re.I)
        if m:
            lo, hi = int(m.group(2)), int(m.group(3) or m.group(2))
            lo, hi = min(lo, hi), max(lo, hi)
            return PlainEffect([fx(do="health_change", role=need(_target(m.group(1))), min=lo, max=hi)], roles)
        m = re.fullmatch(r"heal(?:ed|s)? " + _T, s, re.I)
        if m:
            return PlainEffect([fx(do="health", role=need(_target(m.group(1))), value=cie.HEALTH_MAX)], roles)
        m = re.fullmatch(r"(?:death|dies|killed) " + _T + r'(?: cause "([^"]*)")?', s, re.I)
        if m:
            return PlainEffect([fx(do="kill", role=need(_target(m.group(1)), harm=True),
                                   cause=m.group(2) if m.group(2) else None)], roles)
        m = re.fullmatch(r"(?:disappears|vanishes|disappearance) " + _T, s, re.I)
        if m:
            return PlainEffect([fx(do="vanish", role=need(_target(m.group(1)), harm=True))], roles)
        m = re.fullmatch(r"(?:lost forever|dies unrecovered|body never found) " + _T, s, re.I)
        if m:
            return PlainEffect([fx(do="die_unrecovered", role=need(_target(m.group(1)), harm=True))], roles)
        m = re.fullmatch(r"pregnancy loss(?: \(miscarriage\))?(?: " + _T + r")?", s, re.I)
        if m:
            return PlainEffect([fx(do="baby_lost", role=need(_target(m.group(1)), special="nursing_parent",
                                                               min_age=18))], roles)
        m = re.fullmatch(r"birth then death(?: " + _T + r')?(?: cause "([^"]*)")?', s, re.I)
        if m:
            return PlainEffect([fx(do="birth_then_die", role=need(_target(m.group(1)), special="nursing_parent",
                                                                    min_age=18),
                                   cause=m.group(2) if m.group(2) else None)], roles)
        m = re.fullmatch(r"early birth(?: " + _T + r")?", s, re.I)
        if m:
            return PlainEffect([fx(do="deliver_early", role=need(_target(m.group(1)), special="nursing_parent",
                                                                   min_age=18))], roles)
        m = re.fullmatch(r"new villager(?: \((child|teen|adult|elder|any)(?: (male|female|man|woman|boy|girl))?\))?"
                         r"( child of the newcomers)?", s, re.I)
        if m:
            age = (m.group(1) or "any").lower()
            sex = {"man": "male", "boy": "male", "woman": "female", "girl": "female"}.get(
                (m.group(2) or "").lower(), (m.group(2) or "").lower() or None)
            return PlainEffect([fx(do="new_villager", age=None if age == "any" else age, sex=sex,
                                   child_of_newest=True if m.group(3) else None)], roles)
        if re.fullmatch(r"new baby of the newcomers|their baby joins the village", s, re.I):
            return PlainEffect([{"do": "new_villager", "age": "child", "child_of_newest": True}], roles)
        m = re.fullmatch(r"(?:duplicate|lookalike|double) of " + _T + r"(?: \((child|teen|adult|elder|any)\))?", s,
                         re.I)
        if m:
            age = (m.group(2) or "any").lower()
            return PlainEffect([fx(do="new_villager", copy_of=need(_target(m.group(1))) or "@default",
                                   age=None if age == "any" else age)], roles)
        m = re.fullmatch(r"(two clones|clones|clone)(?: of)? " + _T + r"(?: \((\d+)\))?", s, re.I)
        if m:
            # One or two clones (the owner): "CLONE OF <who> (2)" or "TWO CLONES OF <who>".
            count = 2 if m.group(1).lower() == "two clones" else int(m.group(3) or 1)
            if m.group(1).lower() == "two clones" and m.group(3) and int(m.group(3)) != 2:
                return "TWO CLONES takes no other count"
            if count not in (1, 2):
                return f"an event makes 1 or 2 clones of a villager, not {count}"
            return PlainEffect([fx(do="clone", role=need(_target(m.group(2))),
                                   count=2 if count == 2 else None)], roles)
        m = re.fullmatch(r"(pregnant|nursing)(?: (?!\((?:any birth sex|twins|triplets)\b)" + _T + r")?(?: with " + _T +
                         r")?((?: \((?:any birth sex|twins|triplets|twins or triplets)\))*)", s, re.I)
        if m:
            carrier = need(_target(m.group(2)), min_age=18, carrier=True)
            partner = need(_target(m.group(3)), min_age=18) if m.group(3) else None
            mods = (m.group(4) or "").lower()
            babies = "roll" if "twins or triplets" in mods else 3 if "triplets" in mods else 2 if "twins" in mods \
                else None
            return PlainEffect([fx(do=m.group(1).lower(), role=carrier, partner=partner or None,
                                   any_birth_sex=True if "any birth sex" in mods else None, babies=babies)], roles)
        m = re.fullmatch(r"new look(?: \((head|body|clothes|both)\))?(?: " + _T + r")?", s, re.I)
        if m:
            part = (m.group(1) or "head").lower()
            e = {"do": "appearance", "role": need(_target(m.group(2)))}
            if part in ("head", "both"):
                e["head"] = "random"
            if part in ("body", "clothes", "both"):
                e["body"] = "random"
            return PlainEffect([fx(**e)], roles)
        m = re.fullmatch(r"changes? name(?: (?!to\b)" + _T + r")?(?: to (.+))?", s, re.I)
        if m:
            # Code 33: a fixed name (TO <name>, the engine's rule), or a random one from the game's own lists.
            rid = need(_target(m.group(1)))
            e = {"do": "change_name", "role": rid}
            if m.group(2) is not None:
                name = m.group(2).strip().strip('"').strip()
                if not cie.CHANGE_NAME_RE.match(name):
                    return (f"CHANGE NAME TO {name!r}: a name is 1 to {cie.CHANGE_NAME_MAX} letters, spaces, "
                            "apostrophes, hyphens or full stops, starting with a letter")
                e["name"] = name
            return PlainEffect([fx(**e)], roles)
        m = re.fullmatch(r"(old look|sex change|lose name|loses name|story mute|"
                         r"becomes heathen)(?: " + _T + r")?(?: to (\w+))?", s, re.I)
        if m:
            what = m.group(1).lower().replace("loses", "lose")
            rid = need(_target(m.group(2)))
            note = ""
            if m.group(3):
                return f"{m.group(1)} takes no \"TO\""
            do = {"old look": "old_look", "sex change": "sex_change", "lose name": "lose_name"}.get(what)
            if what == "story mute":
                return PlainEffect([fx(do="trait", role=rid, trait="mute")], roles)
            if what == "becomes heathen":
                return PlainEffect([fx(do="status", role=rid, status="heathen")], roles)
            return PlainEffect([fx(do=do, role=rid)], roles, note)
        m = re.fullmatch(r"body swap " + _T + r" with " + _T, s, re.I)
        if m:
            a = need(_target(m.group(1)))
            b = need(_target(m.group(2)))
            return PlainEffect([fx(do="body_swap", role=a, **{"with": b or "@default"})], roles)
        m = re.fullmatch(r"change age " + _T + r" (younger|older) (\d+)(?: ?(?:to|-) ?(\d+))? years?"
                         r"(?: \(never past (elder|\d+)\))?", s, re.I)
        if m:
            lo, hi = int(m.group(3)), int(m.group(4) or m.group(3))
            lo, hi = min(lo, hi), max(lo, hi)
            years = [-hi, -lo] if m.group(2).lower() == "younger" else [lo, hi]
            cap = None if not m.group(5) else 75 if m.group(5).lower() == "elder" else int(m.group(5))
            return PlainEffect([fx(do="change_age", role=need(_target(m.group(1))), years=years, max_age=cap)],
                               roles)
        m = re.fullmatch(r"change age " + _T + r" to (child|teen|18|adult|50|elder)", s, re.I)
        if m:
            return PlainEffect([fx(do="change_age", role=need(_target(m.group(1))), to=m.group(2).lower())], roles)
        m = re.fullmatch(r"mood (good|bad)(?: " + _T + r")?", s, re.I)
        if m:
            return PlainEffect([fx(do="mood", role=need(_target(m.group(2))), mood=m.group(1).lower())], roles)
        m = re.fullmatch(r"celebrate(?: " + _T + r")?", s, re.I)
        if m:
            who = (m.group(1) or "everyone").lower()
            if who in ("everyone", "all", "everybody", "the village"):
                return PlainEffect([{"do": "celebrate", "who": "all"}], roles)
            return PlainEffect([{"do": "celebrate", "who": need(_target(who)) or "@default"}], roles)
        m = re.fullmatch(r"action " + _T + r' "([^"]+)"', s, re.I)
        if m:
            return PlainEffect([fx(do="action", role=need(_target(m.group(1))), action=m.group(2))], roles)
        m = re.fullmatch(r"damage(?: \((small|normal|large|huge)\))?(?: on (.+))?", s, re.I)
        if m:
            st = split_list(m.group(2)) if m.group(2) else cie.DAMAGE_ANY
            return PlainEffect([{"do": "damage", "size": (m.group(1) or "normal").lower(), "structures": st}], roles)
    except _Bad as exc:
        return str(exc)
    return f"{line.strip()!r} is not an effect this format knows (docs/player-events-format.md 4)"


class _Bad(Exception):
    pass


def harmful_kinds() -> tuple[str, ...]:
    return DEADLY


# ---- Text helpers --------------------------------------------------------------------------------------------------

_PH = re.compile(r"(?<!\\)\(([^()\n]*)\)")
_PH_OK = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z/]*)?(?:\|[A-Za-z/]+)?\Z|[A-Za-z]+/[A-Za-z]+\Z")


_TYPOGRAPHY = {"‘": "'", "’": "'", "“": '"', "”": '"', "—": "-", "–": "-",
               "…": "...", " ": " "}


def plain_typography(text: str) -> str:
    """Curly quotes, dashes and the ellipsis made plain (what every game's font has)."""
    for a, b in _TYPOGRAPHY.items():
        text = text.replace(a, b)
    return text


def escape_prose(text: str) -> str:
    """A simple event's text: typography made plain, and parentheses that are not placeholders become literal
    ones."""
    text = plain_typography(text)
    def fix(m: re.Match) -> str:
        inner = m.group(1)
        return m.group(0) if _PH_OK.match(inner) else "\\(" + inner + "\\)"
    return _PH.sub(fix, text)


def placeholder_roles(text: str) -> list[str]:
    """The role ids a simple event's text names: "" for the main villager (an unprefixed name or pronoun)."""
    out: list[str] = []
    for m in _PH.finditer(text):
        inner = m.group(1).split("|")[0]
        if not _PH_OK.match(m.group(1)):
            continue
        role, dot, word = inner.rpartition(".")
        low = (role if dot else word).lower()
        if not dot and (word.lower() in cie.PRONOUNS_V6 or word.lower() in ("name", "name1")):
            out.append("")
        elif not dot and word.lower() == "name2":
            out.append("friend")
        elif not dot and word.lower() in ("award", "award_unit") + tuple(cie.MADE_PLACEHOLDERS):
            continue
        elif dot or "/" not in low:
            out.append(low)
    return out


# The owner (2026-11-16): with VV5's Guardians of Isola Rewrite, "believer(s)" in new events reads "the tribe" /
# "a tribe member" / "the newcomers" (whichever fits the sentence), alongside Heathen -> Isolan.  The game's own name
# "New Believers" is never changed.
BELIEVER_WORDS = (
    (r"\bthe new(?:ly converted)? believers\b", "the newcomers"),
    (r"\bnew(?:ly converted)? believers\b", "newcomers"),
    (r"\ba new believer\b", "a newcomer"),
    (r"\bthe believers\b", "the tribe"),
    (r"\ball (?:the )?believers\b", "the whole tribe"),
    (r"\b(?:our|their|its) believers\b", "the tribe"),
    (r"\bbelievers\b", "tribe members"),
    (r"\ba believer\b", "a tribe member"),
    (r"\bthe believer\b", "the tribe member"),
    (r"\bbeliever\b", "tribe member"),
)


def _keep_case(old: str, new: str) -> str:
    return new.upper() if old.isupper() and len(old) > 1 else new[0].upper() + new[1:] if old[0].isupper() else new


def _guardians(text: str) -> str:
    """The Guardians of Isola words (guardians-wording.md and the owner's 2026-11-16 rule): Heathen -> Isolan, and
    believer(s) -> the tribe / a tribe member / the newcomers, keeping the case."""
    def rep(m: re.Match) -> str:
        w = m.group(0)
        base = "Isolan" + w[len("Heathen"):]
        return base.upper() if w.isupper() else base if w[0].isupper() else base.lower()
    text = re.sub(r"(?i)heathen(s|-born)?", rep, text)
    keep = "\x00NB\x00"
    text = text.replace("New Believers", keep)           # the game's name
    for pattern, new in BELIEVER_WORDS:
        text = re.sub(pattern, lambda m, new=new: _keep_case(m.group(0), new), text, flags=re.I)
    return text.replace(keep, "New Believers")


def _has_heathen(text: str) -> bool:
    """Text that Guardians of Isola words change (Heathen, believer)."""
    return re.search(r"(?i)heathen", text) is not None or \
        re.search(r"(?i)\bbelievers?\b", text.replace("New Believers", "")) is not None


# ---- Parsing a file ------------------------------------------------------------------------------------------------

_HEAD_NEW = re.compile(r"^([A-Z][A-Z0-9]*-\d+[A-Z]?)\s+[\u2014\u2013-]+\s+(.+?)\s*\[([^\]]+)\]\s*$")
_HEAD_NEW2 = re.compile(r"^(\S.*?)\s+\[([^\]]*VV[1-5][^\]]*|all[^\]]*)\]\s+\[([A-Z][A-Z0-9]*-\d+[A-Z]?)\]\s*$")
_HEAD_TITLE = re.compile(r"^title\s*:\s*(.*)$", re.I)
_HEAD_PIECE = re.compile(r"^piece\s*:\s*(.*)$", re.I)
_CHOICE = re.compile(r"^(?:choice(?:\s+[A-Za-z0-9]+)?\s*:|\[choice\])\s*(.*)$", re.I)
_OUTCOME = re.compile(r"^(?:[*\-\u2022]\s*)?(?:outcome\s*[A-Za-z0-9]*|\(random outcome \d+ of \d+\))"
                      r"(?:\s*\((?:weight|chance)\s*(\d+)\))?\s*:?\s*(.*)$", re.I)
_TABLE = re.compile(r"^([A-Z][A-Z0-9]*-\d+[A-Z]?)\s*\|\s*([A-Z])(\d+)\s*\|\s*([^|]+?)\s*(?:\|\s*(.*))?$")
_SEPARATOR = re.compile(r"^(?:[=#\-_*~]{4,}.*|#.*)$")
_KEY = re.compile(r"^([A-Za-z][A-Za-z_ ()]*?)\s*:\s?(.*)$")
_BLOCK = re.compile(r"^(Page|Question|Random)\s+([A-Za-z0-9_]+)\s*:\s*$")


def parse_text(text: str, file: str = "events.txt") -> list[Item]:
    """Every event and piece in one player file, each with its own problems (a bad item never stops the rest)."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines and lines[0].startswith("\ufeff"):
        lines[0] = lines[0][1:]
    starts: list[tuple[int, str]] = []
    table: list[tuple[int, str, str, int, str, str]] = []
    for k, raw in enumerate(lines):
        line = raw.strip()
        in_piece = bool(starts) and starts[-1][1] == "piece"
        after_gap = k == 0 or not lines[k - 1].strip() or bool(_SEPARATOR.match(lines[k - 1].strip()))
        if owner.HEADING.match(raw) and not raw[:1].isspace():
            starts.append((k, "owner"))       # "S001. Title [VV..]" (src/vv_owner_layout.py)
        elif _HEAD_NEW.match(line) or (_HEAD_NEW2.match(raw) and not raw[:1].isspace()):
            starts.append((k, "new"))
        elif _HEAD_TITLE.match(raw) and not raw[:1].isspace() and (not in_piece or after_gap):
            # A piece's own "Title:" (a setup's title) is one of its lines: only after a blank line does a
            # "Title:" end a piece and start an event.
            starts.append((k, "title"))
        elif _HEAD_PIECE.match(raw) and not raw[:1].isspace():
            starts.append((k, "piece"))
        m = _TABLE.match(line)
        if m:
            table.append((k + 1, m.group(1), m.group(2), int(m.group(3)), m.group(4), m.group(5) or ""))
    items: list[Item] = []
    table_lines = {t[0] - 1 for t in table}
    for n, (k, how) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        block = [(j + 1, lines[j]) for j in range(k, end) if j not in table_lines]
        while block and (not block[-1][1].strip() or _SEPARATOR.match(block[-1][1].strip())):
            block.pop()
        if how == "piece":
            items.append(_parse_piece(block, file))
        elif how == "owner":
            items += _parse_owner(block, file)
        elif any(re.match(r"^start\s*:", b[1], re.I) for b in block):
            items.append(_parse_full(block, file))
        else:
            items.append(_parse_simple(block, file, how))
    by_code = {it.code: it for it in items if it.code}
    for ln, code, letter, num, words, quote in table:
        it = by_code.get(code)
        if it is None:
            if items:
                items[-1].problem(ln, f"the effect table names {code}, which no event in this file has")
            continue
        _apply_table_effect(it, ln, letter, num, words, quote)
    for it in items:
        if it.kind == "event" and it.style in ("simple", "owner") and it.graph is not None:
            _finish_simple(it)
        if it.kind == "event":
            lose_name_warnings(it)
            person_warnings(it)
        if it.kind in ("event", "piece") and (it.graph or it.piece):
            likes_warnings(it)
        elif it.kind == "piece" and any(e.get("do") == "lose_name" for _ln, e in it.piece["effects"]) \
                and not LOSE_NAME_WORDS.search(it.piece["text"]):
            it.warn(it.line, f"piece {it.piece['id']} has LOSE NAME but its text says nothing of a head, a bump, a "
                             f"fall, a fever, forgetting, memory or magic: {LOSE_NAME_RULE}")
    return items


def parse_file(path: Path) -> tuple[list[Item], list[Problem]]:
    """The items of a file and the problems of the file itself (unreadable, empty)."""
    name = path.name
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return [], [Problem(name, 0, f"the file could not be read: {exc}")]
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    items = parse_text(text, name)
    if not items:
        return [], [Problem(name, 1, "no event or piece in this file (an event starts with \"Title:\", a piece "
                                    "with \"Piece:\")")]
    return items, []


# ---- Simple events -------------------------------------------------------------------------------------------------

def _parse_simple(block: list[tuple[int, str]], file: str, how: str) -> Item:
    first_ln, first = block[0]
    it = Item("event", file, first_ln, block[-1][0], "", "simple")
    g: dict[str, Any] = {"format": cie.FORMAT, "version": cie.VERSION_V6, "title": "", "games": [1, 2, 3, 4, 5],
                         "roles": {}, "nodes": {}}
    meta: dict[str, Any] = {"themes": [], "filters": [], "role_lines": {}, "choices": [], "intro": [],
                            "intro_line": first_ln, "pools": {}, "words": {}, "requires": [], "coda": []}
    it.graph, it.meta = g, meta
    if how == "new":
        m = _HEAD_NEW.match(first.strip())
        if m:
            code, title, games_text = m.group(1), m.group(2), m.group(3)
        else:                                  # "Title   [VV1, ...]   [MY-001]"
            m = _HEAD_NEW2.match(first)
            code, title, games_text = m.group(3), m.group(1), m.group(2)
        it.code = code
        it.title = title.strip()
        games = parse_games(games_text)
        if games is None:
            it.problem(first_ln, f"[{games_text}] is not a list of games (VV1..VV5)")
        else:
            g["games"] = games
    else:
        rest = _HEAD_TITLE.match(first).group(1).strip()
        mg = re.match(r"^(.*?)\s*\[([^\]]+)\]\s*$", rest)
        if mg and parse_games(mg.group(2)) is not None:
            rest, g["games"] = mg.group(1), parse_games(mg.group(2))
        it.title = rest
    it.title = plain_typography(it.title)
    if it.title.isupper():
        it.title = caps_title(it.title)
    g["title"] = it.title
    mode = "head"                      # head, intro, choice, outcome, coda, pool
    choice: dict | None = None
    outcome: dict | None = None
    pool: list | None = None
    for ln, raw in block[1:]:
        line = raw.strip()
        if not line or _SEPARATOR.match(line):
            continue
        mc = _CHOICE.match(line)
        mo = _OUTCOME.match(line)
        if mc and not mo:
            label = mc.group(1).strip()
            choice = {"label": label, "line": ln, "outcomes": [], "lead": []}
            meta["choices"].append(choice)
            outcome, mode = None, "choice"
            continue
        if mo and choice is not None and re.match(r"^(?:[*\-\u2022]\s*)?(?:outcome|\(random outcome)", line, re.I):
            outcome = {"text": [mo.group(2).strip()] if mo.group(2).strip() else [], "line": ln, "effects": [],
                       "weight": int(mo.group(1)) if mo.group(1) else 1, "filters": [], "auto": None}
            choice["outcomes"].append(outcome)
            mode = "outcome"
            continue
        key = _KEY.match(line)
        kname = key.group(1).strip().lower() if key else ""
        if key and kname in ("effect", "effects"):
            target = outcome if outcome is not None else None
            for part in [p for p in re.split(r";\s*", key.group(2)) if p.strip()]:
                if target is None:
                    it.problem(ln, "an Effect line belongs under an outcome")
                    break
                target["effects"].append((ln, part))
            continue
        if key and kname == "filters" and mode in ("outcome",):
            outcome["filters"] += split_list(key.group(2))
            continue
        if key and kname in ("auto lines", "auto_lines") and outcome is not None:
            outcome["auto"] = key.group(2).strip().lower() in ("yes", "on", "true")
            continue
        if mode in ("head", "intro") and key and _head_key(it, meta, kname, key.group(1), key.group(2), ln):
            if kname == "event":
                mode = "intro"
                if key.group(2).strip():
                    meta["intro"].append(key.group(2).strip())
                meta["intro_line"] = ln
            if kname.startswith("pool "):
                pool, mode = meta["pools"][kname[5:].strip()], "pool"
            continue
        if mode == "pool" and line.startswith("-"):
            pool.append(line[1:].strip())
            continue
        if key and kname == "coda":
            mode = "coda"
            if key.group(2).strip():
                meta["coda"].append(key.group(2).strip())
            continue
        if mode == "pool":
            mode = "head"
        if mode in ("head", "intro"):
            if mode == "head" and how == "new" or mode == "intro":
                meta["intro"].append(line)
                mode = "intro"
                continue
            it.problem(ln, f"{line[:60]!r}: expected \"Event:\" (the opening text) or a header line such as "
                           "\"Applies to:\"")
            continue
        if mode == "choice":
            choice["lead"].append(line)
            continue
        if mode == "outcome":
            if re.match(r"^(?:[A-Z ]+(?:GAIN|LOSS|\+|-)|INJURY|ILLNESS|DEATH|DISAPPEARS|NEW VILLAGER|NEW LOOK)\b",
                        line) and not isinstance(plain_effect(line), str):
                outcome["effects"].append((ln, line))
            else:
                outcome["text"].append(line)
            continue
        if mode == "coda":
            meta["coda"].append(line)
            continue
    return it


def _head_key(it: Item, meta: dict, kname: str, kraw: str, value: str, ln: int) -> bool:
    """A simple event's header line; False when it is not one."""
    g = it.graph
    v = value.strip()
    if kname in ("applies to", "games", "game"):
        games = parse_games(v)
        if games is None:
            it.problem(ln, f"{v!r} is not a list of games (VV1..VV5, or all)")
        else:
            g["games"] = games
    elif kname == "event":
        pass
    elif kname in ("description", "credit", "series"):
        meta[kname] = v
    elif kname in ("weight", "draw weight"):
        if not v.isdigit() or not 1 <= int(v) <= MAX_DRAW_WEIGHT:
            it.problem(ln, f"Weight is a whole number 1..{MAX_DRAW_WEIGHT}")
        else:
            meta["weight"] = int(v)
    elif kname == "themes":
        meta["themes"] += [t.lower() for t in split_list(v)]
    elif kname in ("filters", "content filters"):
        meta["filters"] += split_list(v)
    elif kname in ("auto lines",):
        meta["auto"] = v.lower() in ("yes", "on", "true")
    elif kname in ("requires", "requirement", "requirements"):
        meta["requires"].append((ln, v))
    elif kname.startswith("role "):
        rid = kname[5:].strip().replace(" ", "_")
        meta["role_lines"][rid] = (ln, v)
    elif kname.startswith("word "):
        meta["words"][kraw.strip()[5:].strip()] = (ln, v)
    elif kname.startswith("pool "):
        meta["pools"][kname[5:].strip()] = split_list(v) if v else []
    elif kname in ("title (guardians of isola)", "guardians title"):
        meta["guardians_title"] = v
    elif kname in ("id",):
        meta["id"] = v
    else:
        return False
    return True


def _apply_table_effect(it: Item, ln: int, letter: str, num: int, words: str, quote: str) -> None:
    k = ord(letter.upper()) - ord("A")
    choices = it.meta.get("choices", [])
    if not (0 <= k < len(choices)) or not (1 <= num <= len(choices[k]["outcomes"])):
        it.problem(ln, f"{it.code} {letter}{num}: that event has no choice {letter} outcome {num}")
        return
    outcome = choices[k]["outcomes"][num - 1]
    q = quote.strip().strip('"').strip()
    text = " ".join(outcome["text"])
    if q and q[:40] not in text and text[:40] not in q:
        it.problem(ln, f"{it.code} {letter}{num}: its quote is not that outcome's text (check the slot)")
        return
    outcome["effects"].append((ln, words))


_ROLE_SPECIAL = {"golden child": "golden_child", "tribal chief": "tribal_chief", "the chief": "tribal_chief",
                 "nursing parent": "nursing_parent", "expecting parent": "nursing_parent"}
_RELATIONS = {"spouse of": "spouse_of", "partner of": "spouse_of", "parent of": "parent_of", "child of": "child_of",
              "sibling of": "sibling_of", "grandparent of": "grandparent_of", "grandchild of": "grandchild_of",
              "aunt or uncle of": "aunt_or_uncle_of", "cousin of": "cousin_of"}


def plain_role(words: str) -> tuple[dict, dict, list[str]]:
    """A plain-word role ("male, 18 to 50, skill Fishing 20+, spouse of farmer, speaks"): (the role, its extras
    {"speaks"}, the problems)."""
    role: dict[str, Any] = {"kind": "villager"}
    extras: dict[str, Any] = {}
    problems: list[str] = []
    for part in split_list(words):
        p = part.lower().strip()
        m = None
        if p in ("villager", "required"):
            continue
        if p == "stranger" or p == "a stranger":
            role = {"kind": "stranger", "sex": role.get("sex", "random") if role.get("sex") != "any" else "random"}
        elif p in ("named", "named stranger"):
            role = {"kind": "stranger", "sex": role.get("sex", "random"), "named": True}
        elif p in ("male", "female", "any sex", "random sex"):
            role["sex"] = {"any sex": "any", "random sex": "random"}.get(p, p)
            if role["kind"] == "villager" and role["sex"] == "random":
                role["sex"] = "any"
        elif p == "optional":
            role["optional"] = True
        elif p in ("believers only",):
            role["believers_only"] = True
        elif p in ("any faith", "heathens too", "isolans too", "conversion role", "heathen may take it"):
            role["believers_only"] = False
        elif p in ("anyone", "protected allowed", "may be protected", "allow protected"):
            role["protected"] = "allow"
        elif p in ("never protected", "exclude protected"):
            role["protected"] = "exclude"
        elif p == "speaks":
            extras["speaks"] = True
        elif p in ("carrier", "can carry a baby"):
            role["min_age"] = max(18, role.get("min_age", 18))
        elif p in _ROLE_SPECIAL:
            role["special"] = _ROLE_SPECIAL[p]
            if role["special"] == "nursing_parent":
                role["min_age"] = max(18, role.get("min_age", 18))
        elif p in ("child", "children"):
            role["min_age"], role["max_age"] = 1, 13
        elif p in ("teen", "teenager"):
            role["min_age"], role["max_age"] = 14, 17
        elif p in ("adult",):
            role["min_age"] = 18
        elif p in ("elder", "old"):
            role["min_age"] = 55
        elif p in ("any age",):
            role["min_age"] = 0
        elif (m := re.fullmatch(r"(?:age\s*)?(\d+)\s*\+", p)):
            role["min_age"] = int(m.group(1))
        elif (m := re.fullmatch(r"(?:age\s*)?(\d+)\s*(?:to|-)\s*(\d+)", p)):
            role["min_age"], role["max_age"] = int(m.group(1)), int(m.group(2))
        elif (m := re.fullmatch(r"(?:age\s*)?under\s*(\d+)", p)):
            role["min_age"], role["max_age"] = 0, int(m.group(1)) - 1
        elif (m := re.fullmatch(r"(best at|skill)\s+([a-z]+)(?:\s+(\d+)\s*\+)?", p)):
            role["skill"] = {"names": [m.group(2).title()], "min": int(m.group(3) or 1),
                             "pick": "highest" if m.group(1) == "best at" else "random"}
        elif (m := re.fullmatch(r"(spouse of|partner of|parent of|child of|sibling of|grandparent of|grandchild of|"
                                r"aunt or uncle of|cousin of)\s+([a-z0-9_]+)", p)):
            role["relation"] = {_RELATIONS[m.group(1)]: m.group(2)}
        elif (m := re.fullmatch(r"within\s+(\d+)\s+years\s+of\s+([a-z0-9_]+)", p)):
            role["max_age_gap"] = {"role": m.group(2), "years": int(m.group(1))}
        elif (m := re.fullmatch(r"one of\s+(.+)", p)):
            role = {"kind": "alias", "of": [x.strip() for x in re.split(r"\s+or\s+|\s+", m.group(1)) if x.strip()]}
        elif (m := re.fullmatch(r"the other of\s+([a-z0-9_]+)", p)):
            role = {"kind": "other", "of": m.group(1)}
        elif (m := re.fullmatch(r"new name for\s+([a-z0-9_]+)(?:\s+(same|other|random|male|female) sex)?"
                                r"(?:\s+(same|different|random) last name)?", p)):
            role = {"kind": "stranger", "named": True, "new_name_for": m.group(1),
                    "sex": m.group(2) or "same", "last_name": m.group(3) or "same"}
        else:
            problems.append(f"{part!r} is not a role word (docs/player-events-format.md 3)")
    return role, extras, problems


def _requirement(it: Item, ln: int, text: str, req: dict, conds: list) -> None:
    for part in split_list(text):
        p = part.lower()
        if (m := re.fullmatch(r"(\d+)\s+(?:eligible\s+)?villagers?", p)):
            req["min_eligible"] = int(m.group(1))
        elif (m := re.fullmatch(r"population\s+(\d+)\s*\+?|(\d+)\s*\+?\s+population", p)):
            conds.append({"min_population": int(m.group(1) or m.group(2))})
        elif (m := re.fullmatch(r"(\d+)\s*\+?\s+children|children\s+(\d+)\s*\+?", p)):
            conds.append({"min_children": int(m.group(1) or m.group(2))})
        elif p in ("golden child present", "the golden child present"):
            conds.append({"special_present": "golden_child"})
        elif p in ("tribal chief present", "chief present", "the chief present"):
            conds.append({"special_present": "tribal_chief"})
        elif (m := re.fullmatch(r"puzzle\s+(.+?)\s*\((vv[1-5])\)", part, re.I)):
            req.setdefault("puzzles", {}).setdefault(str(int(m.group(2)[2])), []).append(m.group(1).strip())
        elif (m := re.fullmatch(r"patch\s+([a-z0-9_]+)", p)):
            conds.append({"patch": m.group(1)})
            it.graph.setdefault("patches", []).append(m.group(1))
        elif (m := re.fullmatch(r"not patch\s+([a-z0-9_]+)", p)):
            conds.append({"not": {"patch": m.group(1)}})
            it.graph.setdefault("patches", []).append(m.group(1))
        elif re.fullmatch(r"(food|tech)\b.*", p):
            it.problem(ln, f"{part!r}: the engine has no food or tech requirement; leave it out")
        else:
            it.problem(ln, f"{part!r} is not a requirement this format knows (docs/player-events-format.md 3)")


def _finish_simple(it: Item) -> None:
    """A simple event's graph from its parts: the opening question, each choice's random outcomes, the roles the text
    and effects name, the requirement and the Guardians of Isola words."""
    g, meta = it.graph, it.meta
    choices = meta["choices"]
    if not meta["intro"]:
        it.problem(it.line, "the event has no opening text (\"Event:\" and the story)")
    if not 2 <= len(choices) <= cie.MAX_ANSWERS:
        it.problem(it.line, f"an event has 2 to {cie.MAX_ANSWERS} choices (this one has {len(choices)})")
    bad = title_case_problem(it.title)
    if bad:
        it.problem(it.line, f"the title is not in Title Case ({bad!r}): {to_title_case(it.title)!r}")
    if len(it.title) > cie.TITLE_BYTES:
        it.problem(it.line, f"the title is longer than {cie.TITLE_BYTES} characters")
    texts: list[str] = ["\n".join(meta["intro"])]
    nodes: dict[str, dict] = {}
    role_need: dict[str, dict] = {}
    order: list[str] = []

    def note_roles(text: str) -> None:
        for r in placeholder_roles(text):
            if r not in order:
                order.append(r)

    intro = escape_prose("\n".join(meta["intro"]))
    note_roles(intro)
    q = {"type": "question", "text": intro, "choices": []}
    nodes["ask"] = q
    coda = escape_prose("\n".join(meta["coda"])) if meta["coda"] else ""
    if coda:
        note_roles(coda)
    for k, c in enumerate(choices, 1):
        label = c["label"]
        bad = title_case_problem(label)
        if bad:
            it.problem(c["line"], f"the choice is not in Title Case ({bad!r}): {to_title_case(label)!r}")
        note_roles(label)
        cid = f"c{k}"
        q["choices"].append({"label": escape_prose(label), "next": cid})
        if not c["outcomes"]:
            it.problem(c["line"], "a choice needs at least one outcome (\"* Outcome A:\")")
            continue
        outs = []
        for j, o in enumerate(c["outcomes"], 1):
            oid = f"c{k}o{j}"
            text = escape_prose("\n".join(o["text"]))
            note_roles(text)
            if not text.strip():
                it.problem(o["line"], "an outcome needs its story text")
            node: dict[str, Any] = {"text": text}
            if c["lead"] and not meta.get("lead_own_popup"):
                node.update(popup="append", join="paragraph")
            effects = []
            for ln, words in o["effects"]:
                pe = words if isinstance(words, PlainEffect) else plain_effect(words)
                if isinstance(pe, str):
                    it.problem(ln, pe)
                    continue
                if pe.note:
                    it.meta.setdefault("notes", []).append((ln, pe.note))
                for rid, facts in pe.roles.items():
                    role_need.setdefault(rid, {}).update(facts)
                    if rid not in order:
                        order.append(rid)
                effects += pe.effects
            if effects:
                node["effects"] = effects
            auto = o["auto"] if o["auto"] is not None else meta.get("auto")
            if auto:
                node["auto_text"] = True
            if coda:
                node["children"] = [{"next": "coda"}]
            if o["filters"]:
                meta.setdefault("node_filters", {})[oid] = o["filters"]
            nodes[oid] = node
            meta.setdefault("node_lines", {})[oid] = o["line"]
            outs.append({"next": oid, "weight": o["weight"]})
        if c["lead"]:
            lead = escape_prose("\n".join(c["lead"]))
            note_roles(lead)
            nodes[cid] = {"text": lead, "children": outs}
        elif len(outs) == 1:
            q["choices"][-1]["next"] = outs[0]["next"]
        else:
            nodes[cid] = {"type": "branch", "children": outs}
    if coda:
        nodes["coda"] = {"popup": "append", "join": "paragraph", "text": coda}
    # The roles: the ones the text and effects name, in order of first use; "" is the main villager ("subject").
    declared = meta["role_lines"]
    # The main villager: "subject", or "villager" when the text calls them (villager) (the owner's drafts).
    main = "villager" if "villager" in order and "" not in order and "subject" not in declared else "subject"
    names = [(main if r in ("", "subject") else r) for r in order]
    if "" in order or main in declared or not names or role_need.get(""):
        names = [main] + [n for n in names if n != main]
    elif main in names:
        names = [main] + [n for n in names if n != main]
    for rid in declared:
        if rid not in names:
            names.append(rid)
    roles: dict[str, dict] = {}
    speaks: list[str] = []
    harmed = set()
    for n in nodes.values():
        for e in n.get("effects", []):
            if e.get("do") in DEADLY + ("sick", "deliver_early") or (e.get("do") == "health_change" and e["min"] < 0) \
                    or e.get("loss"):
                harmed.add(e.get("role") or main)
    for rid in dict.fromkeys(names):
        if rid in declared:
            ln, words = declared[rid]
            role, extras, probs = plain_role(words)
            for p in probs:
                it.problem(ln, p)
            if extras.get("speaks"):
                speaks.append(rid)
        else:
            role = dict(meta.get("role_facts", {}).get(rid, {"kind": "villager"}))
        facts = role_need.get(rid, {})
        if rid == main:
            facts = {**role_need.get("subject", {}), **role_need.get(main, {}), **role_need.get("", {})}
        if role["kind"] == "villager":
            if facts.get("min_age") and role.get("min_age", 14) < facts["min_age"]:
                if rid in declared and "min_age" in role:
                    it.problem(declared[rid][0], f"role {rid}: a carrier or expecting parent is 18 or more")
                role["min_age"] = facts["min_age"]
            if facts.get("special") and not role.get("special"):
                role["special"] = facts["special"]
            if role.get("special") and role.get("protected") is None and rid in harmed:
                # A special role (it MUST be that villager) that the event harms: the author's "allow" (as the
                # collection's own events do), else its own villager would be kept out.
                role["protected"] = "allow"
        roles[rid] = role
    for e in [e for n in nodes.values() for e in n.get("effects", [])]:
        for key in ("copy_of", "with", "who"):
            if e.get(key) == "@default":
                e[key] = main
    g["roles"] = roles
    g["start"] = "ask"
    g["nodes"] = nodes
    req: dict[str, Any] = {"min_eligible": sum(1 for r in roles.values()
                                               if r["kind"] == "villager" and not r.get("optional"))}
    conds: list = []
    for ln, text in meta["requires"]:
        _requirement(it, ln, text, req, conds)
    if conds:
        req["if"] = conds[0] if len(conds) == 1 else {"all": conds}
    g["requirement"] = req
    # Words: the chief's (A New Home .. New Believers say "the village leader" outside The Secret City), and the
    # player's own; lists.
    all_text = intro + coda + "".join(n.get("text", "") for n in nodes.values()) + "".join(
        c["label"] for c in q["choices"])
    words: dict[str, dict] = {}
    for w, (ln, spec) in meta["words"].items():
        per: dict[str, str] = {}
        for part in re.split(r";\s*", spec):
            if "=" not in part:
                it.problem(ln, f"a game word is \"VV3 = the Chief; other = the village leader\" ({part!r})")
                continue
            k, _eq, v = part.partition("=")
            k = k.strip().lower()
            key = "*" if k in ("other", "others", "*", "all", "every game") else \
                str(parse_games(k)[0]) if parse_games(k) and len(parse_games(k)) == 1 else None
            if key is None:
                for gn in parse_games(k) or []:
                    per[str(gn)] = v.strip()
                if not parse_games(k):
                    it.problem(ln, f"{k!r} is not a game (VV1..VV5) or \"other\"")
                continue
            per[key] = v.strip()
        words[w] = per
    for w, per in CHIEF_WORDS.items():
        if "{@" + w + "}" in all_text and w not in words:
            words[w] = dict(per)
    if words:
        g["words"] = words
    pools = {}
    for name, items in meta["pools"].items():
        pools[name] = {"items": [escape_prose(x) for x in items]}
    if pools:
        g["pools"] = pools
    if meta.get("guardians_title") or (_has_heathen(it.title) and 5 in g["games"]):
        g["title_variants"] = [{"if": {"patch": GUARDIANS_PATCH},
                                "title": meta.get("guardians_title") or _guardians(it.title)}]
        g.setdefault("patches", []).append(GUARDIANS_PATCH)
    if 5 in g["games"]:
        for n in nodes.values():
            if n.get("text") and _has_heathen(n["text"]):
                n["variants"] = [{"if": {"patch": GUARDIANS_PATCH}, "text": _guardians(n["text"])}]
                if GUARDIANS_PATCH not in g.setdefault("patches", []):
                    g["patches"].append(GUARDIANS_PATCH)
    if "patches" in g:
        g["patches"] = list(dict.fromkeys(g["patches"]))
    meta["speaks"] = speaks
    meta["auto_filters"] = True
    meta["auto_speakers"] = True


# ---- The owner's own layout ("S001. Title [VV..]", src/vv_owner_layout.py) ----------------------------------------

_PRONOUN_WORDS = set(cie.PRONOUNS_V6) | {"name", "name1"}


def _slotify(text: str, main: str, second: str | None) -> str:
    """A seed's text with its unprefixed names and pronouns given to the piece's slots ("(Name)" -> "(Seeker)")."""
    def ph(m: re.Match) -> str:
        inner = m.group(1)
        low = inner.lower()
        if low in ("name", "name1"):
            return "(" + (main[0].upper() + main[1:] if inner[0].isupper() else main) + ")"
        if low == "name2" and second:
            return "(" + (second[0].upper() + second[1:] if inner[0].isupper() else second) + ")"
        if low in cie.PRONOUNS_V6:
            return f"({main}.{inner})"
        return m.group(0)
    return re.sub(r"\(([^()\n.]*)\)", ph, text)


def _parse_owner(block: list[tuple[int, str]], file: str) -> list[Item]:
    """One block of the owner's layout: the static event and, after "MIXER SEED", its procedural pieces."""
    ln0, first = block[0]
    m = owner.HEADING.match(first.strip())
    code, title, games_text = m.group(1), plain_typography(m.group(2).strip()), m.group(3)
    it = Item("event", file, ln0, block[-1][0], title, "owner")
    it.code = code
    games = parse_games(games_text)
    if games is None:
        it.problem(ln0, f"[{games_text}] is not a list of games (VV1..VV5)")
        games = [1, 2, 3, 4, 5]
    g: dict[str, Any] = {"format": cie.FORMAT, "version": cie.VERSION_V6, "title": title, "games": games,
                         "roles": {}, "nodes": {}}
    meta: dict[str, Any] = {"themes": [], "filters": [], "role_lines": {}, "choices": [], "intro": [],
                            "intro_line": ln0, "pools": {}, "words": {}, "requires": [], "coda": [],
                            "lead_own_popup": True, "role_facts": {}, "phrases": [0, 0]}
    it.graph, it.meta = g, meta
    mode = "head"
    choices: dict[str, dict] = {}
    order: list[str] = []
    current: dict | None = None
    outcome: dict | None = None
    seed: dict[str, Any] | None = None
    seed_line = 0
    who_text = ""

    def effects_of(ln: int, text: str, target: dict) -> None:
        phrases = owner.split_top(text.strip().rstrip("."))
        meta["phrases"][1] += len(phrases)
        try:
            effects, roles, notes = owner.owner_effects(text, games)
        except owner.Unmapped as exc:
            it.problem(ln, f"EFFECT phrase not in the phrase table (docs/player-events-format.md 10): {exc}")
            return
        meta["phrases"][0] += len(phrases)
        for n in notes:
            it.warn(ln, n)
        target["effects"].append((ln, PlainEffect(effects, roles)))

    for ln, raw in block[1:]:
        line = raw.strip()
        if not line or line.startswith("^") or _SEPARATOR.match(line):
            continue
        if seed is not None:
            _seed_line(seed, ln, raw, line, it)
            continue
        ms = owner._SEED.match(line)
        if ms:
            seed = {"code": ms.group(1) or code, "premise": "", "roles": [], "approaches": [], "outcomes": [],
                    "flavour": [], "mode": "", "line": ln}
            seed_line = ln
            continue
        if line.startswith("WHO:"):
            who_text = line[4:].strip()
            continue
        if line == "EVENT TEXT":
            mode = "intro"
            continue
        mc = owner._CHOICE_LIST.match(line)
        if mc and mode in ("intro", "choices"):
            mode = "choices"
            letter = mc.group(1)
            choices[letter] = {"label": plain_typography(mc.group(2).strip()), "line": ln, "outcomes": [], "lead": []}
            order.append(letter)
            continue
        mh = owner._CHOICE_HEAD.match(line)
        if mh:
            current = choices.get(mh.group(1))
            if current is None:
                it.problem(ln, f"CHOICE {mh.group(1)} is not in the list of choices (\"Choice {mh.group(1)}: ...\")")
                current = {"label": mh.group(2).title(), "line": ln, "outcomes": [], "lead": []}
            outcome, mode = None, "choice"
            continue
        if line.startswith("First popup:") and current is not None:
            current["lead"].append(owner.normalize_text(plain_typography(line[len("First popup:"):].strip())))
            mode = "lead"
            continue
        me = owner._ENDING.match(line)
        if me:
            if current is None or current is not choices.get(me.group(1)):
                current = choices.get(me.group(1)) or current
            if current is None:
                it.problem(ln, "an Ending before any CHOICE section")
                continue
            outcome = {"text": [], "line": ln, "effects": [], "weight": max(1, int(me.group(4))), "filters": [],
                       "auto": None}
            current["outcomes"].append(outcome)
            effects_of(ln, me.group(5), outcome)
            mode = "ending"
            continue
        text = owner.normalize_text(plain_typography(line))
        if mode == "intro":
            meta["intro"].append(text)
        elif mode == "lead" and current is not None:
            current["lead"].append(text)
        elif mode == "ending" and outcome is not None:
            outcome["text"].append(text)
        # Anything else before EVENT TEXT is the owner's note ("(Source title: ...)"), never shown.
    meta["choices"] = [choices[k] for k in order]
    # "(award)" in an ending's text names the amount its food or tech gain gives: that gain is an award (defer),
    # paid on the same page (cie-v6-binary.md: pay_award).
    for c in meta["choices"]:
        for o in c["outcomes"]:
            if "(award)" not in " ".join(o["text"]).lower():
                continue
            paid = False
            for _ln, pe_ in o["effects"]:
                gains = [e for e in pe_.effects if e["do"] in ("food", "tech") and not e.get("loss")]
                if gains:
                    gains[0]["defer"] = True
                    pe_.effects.append({"do": "pay_award"})
                    paid = True
                    break
            if not paid:
                # A loss names no amount in the engine: the owner's "Your village loses (award) food." becomes the
                # game's own automatic line ("The village loses food.").
                o["text"] = [re.sub(r"\s*Your villag\w* (?:lose|loses|gain|gains) \(award\)[^.]*\.", "", t)
                             for t in o["text"]]
                o["text"] = [t for t in o["text"] if t.strip()]
                o["auto"] = True
                it.warn(o["line"], "\"(award)\" with a loss: its sentence is shown as the game's automatic line")
    # The roles the WHO line names (ages, birth sex, the chief, an Isolan), and the new villager's name.
    facts = owner.who_roles(who_text)
    for rid, f in facts.items():
        role = owner.role_dict(f)
        for name in ([("subject"), "villager"] if rid == "" else [rid]):
            meta["role_facts"][name] = role
    items = [it]
    if seed is not None:
        items += _seed_pieces(seed, it, games, choices, order, seed_line)
    return items


def _seed_line(seed: dict, ln: int, raw: str, line: str, it: Item) -> None:
    for key in ("Premise:", "Roles:", "Approaches:", "Outcome pool:", "Flavour lines:", "Flavor lines:"):
        if line.startswith(key):
            seed["mode"] = key.rstrip(":").split()[0].lower()
            rest = line[len(key):].strip()
            if seed["mode"] == "premise":
                seed["premise"] = rest
            elif seed["mode"] == "roles" and rest:
                seed["roles"].append((ln, rest))
            elif seed["mode"] == "approaches":
                seed["approaches"] = [(ln, a.strip()) for a in re.split(r"\s*[|/]\s*(?![^()]*\))|,\s+", rest)
                                      if a.strip()]
            return
    if seed["mode"] == "roles":
        seed["roles"].append((ln, line))
    elif seed["mode"] in ("outcome", "flavour", "flavor") and line.startswith("-"):
        (seed["outcomes"] if seed["mode"] == "outcome" else seed["flavour"]).append((ln, line[1:].strip()))
    elif seed["mode"] == "premise":
        seed["premise"] += " " + line
    elif seed["mode"] in ("flavour", "flavor"):
        seed["mode"] = "done"                 # the seed is over: the file's own notes follow (never read)
    elif seed["mode"] != "done":
        it.problem(ln, f"{line[:60]!r}: not a mixer seed line (Premise, Roles, Approaches, Outcome pool, Flavour lines)")


def _seed_pieces(seed: dict, ev: Item, games: list[int], choices: dict, order: list[str], ln0: int) -> list[Item]:
    """The seed's pieces: a setup (the premise), an approach per approach, an outcome per pool line, a flavour line
    per flavour line; the slots from its role lines."""
    fam = re.sub(r"[^a-z0-9_]+", "_", seed["code"].lower()).strip("_")
    slots: dict[str, tuple[dict, str]] = {}
    for ln, whole in seed["roles"]:
        for text in re.split(r";\s*(?=\()", whole):
            m = re.match(r"^\(?([A-Za-z][A-Za-z0-9 ]*?)\)?\s*:\s*(.+)$", text.strip())
            if not m:
                continue
            rid = owner.role_of(m.group(1)) or "subject"
            facts = owner.who_roles("(x) " + m.group(2)).get("x", owner.who_roles(m.group(2)).get("", {}))
            slots[rid] = (owner.role_dict(facts), m.group(2).lower())
    if not slots:
        slots["subject"] = ({"kind": "villager"}, "")
    main = next(iter(slots))
    second = list(slots)[1] if len(slots) > 1 else None
    out: list[Item] = []

    def piece(pid: str, kind: int, ln: int, text: str, **kw) -> Item:
        it = Item("piece", ev.file, ln, ln, pid, "piece")
        it.piece = {"id": pid, "kind": kind, "mood": kw.get("mood", 1), "games": list(games), "family": kw.get(
            "family", ""), "text": _slotify(owner.normalize_text(plain_typography(text)), main, second),
                    "label": kw.get("label", ""), "weight": 1, "tags": [], "never": [], "age_band": 0,
                    "slots": {k: (dict(v[0]), v[1]) for k, v in slots.items()}, "effects": [], "links": [],
                    "filters": [], "themes": [], "speaks": []}
        it.meta = {"phrases": [0, 0]}
        return it

    moods = [owner.MOODS.get(re.search(r"\[mood:\s*([a-z]+)", t).group(1), 1)
             for _ln, t in seed["outcomes"] if re.search(r"\[mood:\s*([a-z]+)", t)]
    mood = max(set(moods), key=moods.count) if moods else 1
    setup = piece(f"{fam}_setup", 1, seed["line"], seed["premise"] or ev.title, family=fam, label=ev.title, mood=mood)
    out.append(setup)
    labels = {}
    lead_of = {plain_typography(choices[k]["label"]).lower(): " ".join(choices[k]["lead"]) for k in order}
    for k, (ln, label) in enumerate(seed["approaches"], 1):
        aid = f"{fam}_a{k}"
        labels[label.lower()] = aid
        out.append(piece(aid, 2, ln, lead_of.get(label.lower()) or label + ".", family=fam,
                         label=plain_typography(label)))
    for k, (ln, line) in enumerate(seed["outcomes"], 1):
        tags = dict(re.findall(r"\[(answers|mood|effect):\s*([^\]]*)\]", line, re.I))
        tags = {a.lower(): b for a, b in tags.items()}
        text = re.sub(r"\s*\[[a-zA-Z]+:[^\]]*\]", "", line).strip()
        it = piece(f"{fam}_o{k}", 3, ln, text, mood=owner.MOODS.get(tags.get("mood", "").strip().lower(), 1))
        for ans in [a.strip() for a in tags.get("answers", "").split(",") if a.strip()]:
            aid = labels.get(ans.lower())
            if aid is None:
                it.problem(ln, f"[answers: {ans}] is not one of the seed's approaches")
            else:
                it.piece["links"].append((aid, 1))
        eff = tags.get("effect", "none")
        phrases = owner.split_top(eff.strip().rstrip("."))
        it.meta["phrases"][1] += len(phrases)
        try:
            effects, roles, notes = owner.owner_effects(eff, games)
            it.meta["phrases"][0] += len(phrases)
            for e in effects:
                for key in ("role", "partner", "with", "copy_of", "who"):
                    if key in e and e[key] in (None, "@default"):
                        e[key] = main
                if "role" not in e and e["do"] not in ("food", "tech", "pay_award", "damage", "repair",
                                                       "new_villager", "celebrate") and not e.get("target"):
                    e["role"] = main
                for key in ("role", "partner", "with", "copy_of"):
                    rid = e.get(key)
                    if isinstance(rid, str) and not rid.startswith("$") and rid not in it.piece["slots"]:
                        it.piece["slots"][rid] = ({"kind": "villager"}, "")
                it.piece["effects"].append((ln, e))
            for n in notes:
                it.warn(ln, n)
        except owner.Unmapped as exc:
            it.problem(ln, f"EFFECT phrase not in the phrase table (docs/player-events-format.md 10): {exc}")
        out.append(it)
    for k, (ln, line) in enumerate(seed["flavour"], 1):
        out.append(piece(f"{fam}_f{k}", 4, ln, line, mood=mood))
    for it in out:
        finish_piece(it, it.line, romance_is_error=False)
        if not it.piece["slots"] or it.piece["kind"] == 4:
            pass
    return out


def owner_coverage(items: list[Item]) -> tuple[int, int]:
    """(EFFECT phrases mapped, phrases in all) over the owner-layout items."""
    done = total = 0
    for it in items:
        ph = (it.meta or {}).get("phrases")
        if ph:
            done += ph[0]
            total += ph[1]
    return done, total


# ---- Full events ---------------------------------------------------------------------------------------------------

TOP_KEYS = {"title": "title", "applies to": "games", "games": "games", "version": "version", "start": "start",
            "collection": "collection", "requirement": "requirement", "patches": "patches",
            "title variants": "title_variants", "words": "words", "include pools": "include_pools",
            "grammar fixes": "grammar_fixes"}
META_KEYS = {"description": "description", "description variants": "description_variants", "themes": "themes",
             "credit": "credit", "series": "series", "weight": "weight", "id": "id", "auto filters": "auto_filters",
             "auto speakers": "auto_speakers", "speakers": "speaks", "traits": "traits", "filters": "filters"}
NODE_TYPE_WORDS = {"Page": "popup", "Question": "question", "Random": "branch"}
TYPE_WORDS = {v: k for k, v in NODE_TYPE_WORDS.items()}


def _parse_full(block: list[tuple[int, str]], file: str) -> Item:
    it = Item("event", file, block[0][0], block[-1][0], "", "full")
    g: dict[str, Any] = {"format": cie.FORMAT}
    meta: dict[str, Any] = {"themes": [], "filters": [], "node_filters": {}, "speaks": [], "traits": [],
                            "auto_filters": True, "auto_speakers": True}
    roles: dict[str, dict] = {}
    pools: dict[str, dict] = {}
    nodes: dict[str, dict] = {}
    it.graph, it.meta = g, meta
    node: dict | None = None
    nid = ""
    pool: dict | None = None
    text_target: tuple[dict, str] | None = None      # the dict and key the "|" lines continue

    def value(ln: int, s: str, what: str) -> Any:
        try:
            return parse_value(s)
        except ValueSyntax as exc:
            it.problem(ln, f"{what}: {exc}")
            return None

    def attrs(ln: int, s: str, what: str) -> dict:
        try:
            return parse_attrs(s)
        except ValueSyntax as exc:
            it.problem(ln, f"{what}: {exc}")
            return {}

    for ln, raw in block:
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("|"):
            body = stripped[1:]
            body = body[1:] if body.startswith(" ") else body
            if text_target is None:
                it.problem(ln, "a \"|\" line continues a Text, a Variant or a quoted field")
                continue
            d, k = text_target
            d[k] = body if d.get(k) is None else d[k] + "\n" + body
            continue
        if _SEPARATOR.match(stripped) and not stripped.startswith("-"):
            continue
        text_target = None
        mb = _BLOCK.match(stripped)
        if mb:
            nid = mb.group(2)
            if nid in nodes:
                it.problem(ln, f"two pages are called {nid}")
            node = {}
            if mb.group(1) != "Page":
                node["type"] = NODE_TYPE_WORDS[mb.group(1)]
            nodes[nid] = node
            pool = None
            continue
        if pool is not None and stripped.startswith("- "):
            item = stripped[2:]
            if item.startswith("{") or item.startswith('"'):
                v = value(ln, item, "a list item")
                if v is not None:
                    pool["items"].append(v)
            else:
                pool["items"].append(item)
            continue
        m = re.match(r"^(Role|Pool)\s+([A-Za-z0-9_@]+)\s*:\s*(.*)$", stripped)
        if m and node is None:
            a = attrs(ln, m.group(3), f"{m.group(1)} {m.group(2)}")
            if m.group(1) == "Role":
                if a.pop("speaks", False):
                    meta["speaks"].append(m.group(2))
                roles[m.group(2)] = a
                pool = None
            else:
                a["items"] = []
                pools[m.group(2)] = a
                pool = a
            continue
        key = _KEY.match(stripped)
        if not key:
            it.problem(ln, f"{stripped[:60]!r}: not a line this format knows")
            continue
        kname, rest = key.group(1).strip(), key.group(2)
        low = kname.lower()
        if node is None:
            if low in TOP_KEYS:
                k = TOP_KEYS[low]
                if k == "title":
                    g["title"] = rest.strip()
                    it.title = rest.strip()
                    text_target = (g, "title")
                elif k == "games":
                    games = parse_games(rest)
                    if games is None:
                        it.problem(ln, f"{rest!r} is not a list of games")
                    else:
                        g["games"] = games
                elif k == "start":
                    g["start"] = rest.strip()
                else:
                    v = value(ln, rest, kname)
                    if v is not None or rest.strip() == "null":
                        g[k] = v
            elif low in META_KEYS:
                k = META_KEYS[low]
                if k in ("themes", "speaks", "filters"):
                    meta[k] += [t.lower() if k == "themes" else t for t in split_list(rest)]
                elif k in ("auto_filters", "auto_speakers"):
                    meta[k] = rest.strip().lower() in ("yes", "on", "true")
                elif k in ("description_variants", "traits"):
                    v = value(ln, rest, kname)
                    if v is not None:
                        meta[k] = v
                elif k == "weight":
                    v = value(ln, rest, kname)
                    if isinstance(v, int) and 1 <= v <= MAX_DRAW_WEIGHT:
                        meta[k] = v
                    else:
                        it.problem(ln, f"Weight is a whole number 1..{MAX_DRAW_WEIGHT}")
                else:
                    meta[k] = rest.strip()
                    text_target = (meta, k)
            else:
                it.problem(ln, f"{kname!r} is not an event line (docs/player-events-format.md 5)")
            continue
        # A page's lines.
        if low == "text":
            node["text"] = rest
            text_target = (node, "text")
        elif low == "variant":
            v = {"if": None}
            v.update(attrs(ln, rest, "Variant"))
            v["text"] = None
            node.setdefault("variants", []).append(v)
            text_target = (v, "text")
        elif low == "effect":
            parts = rest.strip().split(None, 1)
            do = parts[0] if parts else ""
            if do in cie.EFFECT_CODES or do in ("skill",):
                e = {"do": do}
                e.update(attrs(ln, parts[1] if len(parts) > 1 else "", f"Effect {do}"))
                node.setdefault("effects", []).append(e)
            else:
                pe = plain_effect(rest)
                if isinstance(pe, str):
                    it.problem(ln, pe)
                else:
                    for e in pe.effects:
                        for key2 in ("copy_of", "with", "who"):
                            if e.get(key2) == "@default":
                                e[key2] = cie.default_role_of(roles)
                        if "role" in e and e["role"] is None:
                            e.pop("role")
                    node.setdefault("effects", []).extend(pe.effects)
        elif low == "next":
            parts = rest.strip().split(None, 1)
            if not parts:
                it.problem(ln, "Next names a page")
                continue
            c = {"next": parts[0]}
            c.update(attrs(ln, parts[1] if len(parts) > 1 else "", "Next"))
            node.setdefault("children", []).append(c)
        elif low == "choice":
            r = rest.strip()
            if r.startswith('"'):
                try:
                    label, at = _DECODER.raw_decode(r)
                except ValueError:
                    it.problem(ln, "Choice: the quoted label is not closed")
                    continue
                r2 = r[at:].strip()
            else:
                cut = r.rfind(" -> ")
                if cut < 0:
                    it.problem(ln, "a Choice is \"<label> -> <page>\"")
                    continue
                label, r2 = r[:cut], r[cut:].strip()
            if not r2.startswith("->"):
                it.problem(ln, "a Choice is \"<label> -> <page>\"")
                continue
            parts = r2[2:].strip().split(None, 1)
            if not parts:
                it.problem(ln, "a Choice names the page it leads to")
                continue
            c = {"label": label, "next": parts[0]}
            c.update(attrs(ln, parts[1] if len(parts) > 1 else "", "Choice"))
            node.setdefault("choices", []).append(c)
        elif low == "filters":
            meta["node_filters"].setdefault(nid, []).extend(split_list(rest))
        elif _BARE.match(kname):
            v = value(ln, rest, kname)
            if v is not None or rest.strip() == "null":
                node[kname] = v
                if isinstance(v, str):
                    text_target = (node, kname)
        else:
            it.problem(ln, f"{kname!r} is not a page line")
    for v in [v for n in nodes.values() for v in n.get("variants", [])]:
        if v["text"] is None:
            v["text"] = ""
    g.setdefault("version", cie.VERSION_V6)
    g["roles"] = roles
    if pools:
        g["pools"] = pools
    g["nodes"] = nodes
    # The top level in normalize's order (the compiled strings follow it).
    order = ("format", "version", "title", "games", "collection", "grammar_fixes", "words", "patches",
             "title_variants", "requirement", "roles", "include_pools", "pools", "start", "nodes")
    it.graph = {k: g[k] for k in order if k in g} | {k: v for k, v in g.items() if k not in order}
    if not it.title:
        it.problem(it.line, "the event has no Title")
    return it


def full_text(graph: dict, meta: dict | None = None) -> str:
    """An event in the FULL format: every part of the graph, one line each (parse_text reads it back exactly)."""
    meta = meta or {}
    g = graph
    out: list[str] = []

    def text_lines(key: str, text: str, indent: str = "") -> None:
        first, *rest = text.split("\n")
        out.append(f"{indent}{key}: {first}".rstrip() if first else f"{indent}{key}:")
        out.extend(f"{indent}| {line}" if line else f"{indent}|" for line in rest)

    text_lines("Title", g["title"])
    out.append(f"Applies to: {games_words(g.get('games', [1, 2, 3, 4, 5]))}")
    out.append(f"Version: {g.get('version', cie.VERSION_V6)}")
    for k in ("collection", "grammar_fixes", "words", "patches", "title_variants", "requirement", "include_pools"):
        if k in g:
            pretty = next(p for p, kk in TOP_KEYS.items() if kk == k and p != "games")
            out.append(f"{pretty.title()}: {dump(g[k])}")
    if meta.get("id"):
        out.append(f"Id: {meta['id']}")
    for k in ("description", "credit", "series"):
        if meta.get(k):
            text_lines(k.title(), meta[k])
    if meta.get("weight"):
        out.append(f"Weight: {meta['weight']}")
    if meta.get("description_variants"):
        out.append(f"Description Variants: {dump(meta['description_variants'])}")
    if meta.get("themes"):
        out.append(f"Themes: {', '.join(meta['themes'])}")
    if "auto_filters" in meta:
        out.append(f"Auto Filters: {'yes' if meta['auto_filters'] else 'no'}")
    if "auto_speakers" in meta:
        out.append(f"Auto Speakers: {'yes' if meta['auto_speakers'] else 'no'}")
    if meta.get("traits"):
        out.append(f"Traits: {dump(meta['traits'])}")
    out.append(f"Start: {g['start']}")
    speaks = set(meta.get("speaks", []))
    for rid, r in g.get("roles", {}).items():
        extra = " speaks=true" if rid in speaks else ""
        out.append(f"Role {rid}: {dump_attrs(r)}{extra}".rstrip())
    for name, p in g.get("pools", {}).items():
        out.append(f"Pool {name}: {dump_attrs(p, ('items',))}".rstrip())
        for item in p.get("items", []):
            if isinstance(item, str) and not item.startswith(("{", '"')) and item == item.strip() and item \
                    and "\n" not in item:
                out.append(f"- {item}")
            else:
                out.append(f"- {dump(item)}")
    tags = meta.get("node_filters", {})
    for nid, n in g["nodes"].items():
        out.append("")
        out.append(f"{TYPE_WORDS.get(n.get('type', 'popup'), 'Page')} {nid}:")
        for k, v in n.items():
            if k in ("type", "text", "variants", "effects", "children", "choices"):
                continue
            out.append(f"  {k}: {dump(v)}")
        if "text" in n:
            text_lines("Text", n["text"], "  ")
        for v in n.get("variants", []):
            out.append(f"  Variant: {dump_attrs({k: x for k, x in v.items() if k != 'text'})}".rstrip())
            out.extend(f"  | {line}" if line else "  |" for line in v.get("text", "").split("\n"))
        for e in n.get("effects", []):
            out.append(f"  Effect: {e['do']} {dump_attrs(e, ('do',))}".rstrip())
        for c in n.get("children", []):
            out.append(f"  Next: {c['next']} {dump_attrs(c, ('next',))}".rstrip())
        for c in n.get("choices", []):
            label = c["label"]
            shown = label if label == label.strip() and label and " -> " not in label and not label.startswith('"') \
                and "\n" not in label else json.dumps(label)
            out.append(f"  Choice: {shown} -> {c['next']} {dump_attrs(c, ('label', 'next'))}".rstrip())
        if tags.get(nid):
            out.append(f"  Filters: {', '.join(tags[nid])}")
    return "\n".join(out) + "\n"


# ---- Mixer pieces --------------------------------------------------------------------------------------------------

PIECE_KINDS = {"setup": 1, "approach": 2, "outcome": 3, "flavour": 4, "flavor": 4, "opening": 4,
               "flavour line": 4, "frame": 5, "personality frame": 5}
MOODS = {"warm": 0, "funny": 0, "ordinary": 0, "social": 1, "curious": 1, "mixed": 1, "serious": 2, "solemn": 2,
         "mysterious": 2}
BLOCK_TAGS = {"power dynamics": 0, "invalidating pain": 1, "portraying anyone as lesser": 2, "lesser": 2,
              "romance": 3, "minor": 4}
_ROMANCE = re.compile(r"(?i)\b(romanc\w*|courting|sweetheart\w*|kiss\w*|in love|falls? for|crush)\b")


def _parse_piece(block: list[tuple[int, str]], file: str) -> Item:
    ln0, first = block[0]
    pid = _HEAD_PIECE.match(first).group(1).strip()
    it = Item("piece", file, ln0, block[-1][0], pid, "piece")
    p: dict[str, Any] = {"id": pid, "kind": 0, "mood": 0, "games": [1, 2, 3, 4, 5], "family": "", "text": "",
                         "label": "", "weight": 1, "tags": [], "never": [], "age_band": 0, "slots": {},
                         "effects": [], "links": [], "filters": [], "themes": [], "speaks": []}
    it.piece = p
    if not re.fullmatch(r"[a-z0-9_]{1,40}", pid):
        it.problem(ln0, "a piece's id is 1..40 of a-z, 0-9 and _")
    text_key: str | None = None
    for ln, raw in block[1:]:
        s = raw.strip()
        if not s or (_SEPARATOR.match(s) and not s.startswith("-")):
            continue
        if s.startswith("|") and text_key:
            body = s[1:]
            body = body[1:] if body.startswith(" ") else body
            p[text_key] = (p[text_key] + "\n" + body) if p[text_key] else body
            continue
        text_key = None
        key = _KEY.match(s)
        if not key:
            it.problem(ln, f"{s[:60]!r}: not a piece line (docs/player-events-format.md 6)")
            continue
        k, v = key.group(1).strip().lower(), key.group(2).strip()
        if k == "kind":
            if v.lower() not in PIECE_KINDS:
                it.problem(ln, "Kind is Setup, Approach, Outcome, Flavour or Frame")
            p["kind"] = PIECE_KINDS.get(v.lower(), 0)
        elif k == "mood":
            if v.lower() not in MOODS:
                it.problem(ln, "Mood is warm, social or serious")
            p["mood"] = MOODS.get(v.lower(), 0)
        elif k in ("applies to", "games"):
            gs = parse_games(v)
            if gs is None:
                it.problem(ln, f"{v!r} is not a list of games")
            else:
                p["games"] = gs
        elif k == "family":
            p["family"] = v.lower()
        elif k in ("text",):
            p["text"] = v
            text_key = "text"
        elif k in ("title", "label"):
            p["label"] = v
        elif k == "weight":
            if not v.isdigit() or not 1 <= int(v) <= 1000:
                it.problem(ln, "a piece's Weight is 1..1000")
            else:
                p["weight"] = int(v)
        elif k in ("tags",):
            p["tags"] += [t.lower() for t in split_list(v)]
        elif k in ("never with",):
            p["never"] += [t.lower() for t in split_list(v)]
        elif k == "age band":
            p["age_band"] = {"any": 0, "adult romance": 1, "adults": 1, "teen romance": 2, "teens": 2}.get(
                v.lower(), -1)
            if p["age_band"] < 0:
                it.problem(ln, "Age Band is any, adult romance or teen romance")
                p["age_band"] = 0
        elif k in ("filters",):
            p["filters"] += split_list(v)
        elif k == "themes":
            p["themes"] += [t.lower() for t in split_list(v)]
        elif k.startswith("role ") or k.startswith("slot "):
            rid = k.split(None, 1)[1].strip().replace(" ", "_")
            role, extras, probs = plain_role(v)
            for pr in probs:
                it.problem(ln, pr)
            if extras.get("speaks"):
                p["speaks"].append(rid)
            p["slots"][rid] = (role, v.lower())
        elif k == "effect":
            pe = plain_effect(v)
            if isinstance(pe, str):
                it.problem(ln, pe)
            else:
                for rid, facts in pe.roles.items():
                    p["slots"].setdefault(rid or "subject", ({"kind": "villager", **(
                        {"min_age": facts["min_age"]} if "min_age" in facts else {})}, ""))
                p["effects"] += [(ln, e) for e in pe.effects]
        elif k in ("answers",):
            for part in split_list(v):
                m = re.fullmatch(r"([a-z0-9_]+)(?:\s*\((?:weight\s*)?(\d+)\))?", part.strip())
                if not m:
                    it.problem(ln, f"{part!r}: Answers lists approach ids, each with an optional (weight)")
                    continue
                p["links"].append((m.group(1), int(m.group(2) or 1)))
        else:
            it.problem(ln, f"{key.group(1)!r} is not a piece line")
    return finish_piece(it, ln0)


def finish_piece(it: Item, ln0: int, romance_is_error: bool = True) -> Item:
    """A piece's own checks and the owner's four mixer blocks (shared by every layout that makes pieces)."""
    p = it.piece
    if p["kind"] == 0:
        it.problem(ln0, "a piece needs its Kind")
    if not p["text"].strip():
        it.problem(ln0, "a piece needs its Text")
    if p["kind"] in (1, 2) and not p["label"]:
        it.problem(ln0, "a setup needs its Title and an approach its Label")
    if p["kind"] in (1, 2) and not p["family"]:
        it.problem(ln0, "a setup or an approach needs its Family")
    if p["kind"] == 3 and not p["links"]:
        it.problem(ln0, "an outcome lists the approaches it Answers")
    if p["label"]:
        bad = title_case_problem(p["label"])
        if bad:
            it.problem(ln0, f"the {'title' if p['kind'] == 1 else 'label'} is not in Title Case ({bad!r})")
    for t in p["tags"] + p["never"]:
        if not re.fullmatch(r"[a-z0-9 _-]{1,40}", t):
            it.problem(ln0, f"{t!r} is not a tag (letters, digits, spaces)")
    # The owner's four mixer blocks: a romance piece is tagged romance and never meets a minor; a piece centred on a
    # minor is tagged minor and never meets romance (docs/event-collection/procedural-pieces.md 2.3).
    minor = any(r[0].get("kind") == "villager" and r[0].get("max_age") is not None and r[0]["max_age"] < 18
                for r in p["slots"].values())
    if minor and "minor" not in p["tags"]:
        p["tags"].append("minor")
    if _ROMANCE.search(p["text"] + " " + p["label"]) and "romance" not in p["tags"]:
        if romance_is_error:
            it.problem(ln0, "this piece reads as romance: add \"Tags: romance\" (it then never meets a minor)")
        else:
            p["tags"].append("romance")       # the owner's seeds have no Tags line: tagged here
    if "romance" in p["tags"]:
        if "minor" not in p["never"]:
            p["never"].append("minor")
        if p["age_band"] == 0:
            p["age_band"] = 1
        for rid, (role, _w) in p["slots"].items():
            if role.get("kind") == "villager":
                if p["age_band"] == 1 and role.get("min_age", 14) < 18:
                    role["min_age"] = 18
                if p["age_band"] == 2:
                    role["min_age"], role["max_age"] = max(14, role.get("min_age", 14)), 17
    if "minor" in p["tags"] and "romance" not in p["never"]:
        p["never"].append("romance")
    if "romance" in p["tags"] and "minor" in p["tags"]:
        it.problem(ln0, "a piece cannot be both romance and centred on a minor")
    return it


def compile_pieces(items: list[Item], game: int, multiplier: dict[str, int] | None = None) -> tuple[bytes, list]:
    """The VPCB v1 file of the usable pieces (docs/event-collection/procedural-pieces.md 2) and the problems."""
    problems: list[Problem] = []
    pieces = [it for it in items if it.kind == "piece" and not it.problems and game in it.piece["games"]]
    if not pieces:
        return b"", problems
    strings = bytearray()
    sidx: dict[str, int] = {}

    def s(text: str | None) -> int:
        if not text:
            return 0xFFFFFFFF
        if text not in sidx:
            sidx[text] = len(strings)
            strings.extend(text.encode("ascii", "replace") + b"\0")
        return sidx[text]

    tag_bits: dict[str, int] = dict(BLOCK_TAGS)
    free = 5
    for it in pieces:
        for t in it.piece["tags"] + it.piece["never"]:
            if t not in tag_bits:
                if free > 31:
                    problems.append(Problem(it.file, it.line, "more than 27 free tags in one game's pieces"))
                    continue
                tag_bits[t] = free
                free += 1
    topic_bits: dict[str, int] = {}
    fam_ids: dict[str, int] = {}
    recs = bytearray()
    slots_b = bytearray()
    effects_b = bytearray()
    links_b = bytearray()
    n_slot = n_fx = n_link = 0
    ids = {it.piece["id"] for it in pieces}
    for it in pieces:
        p = it.piece
        names = list(p["slots"])
        local = {r: k for k, r in enumerate(names)}
        first_slot, first_fx, first_link = n_slot, n_fx, n_link
        believers = False
        deadly = False
        for rid in names:
            role, words = p["slots"][rid]
            flags = 0
            if role.get("optional"):
                flags |= 1
            if role.get("believers_only") is True and "believers only" in words:
                flags |= 2
                believers = True
            if rid in p["speaks"]:
                flags |= 4
            harm = any(e.get("role", "subject") == rid and e["do"] in DEADLY + ("health_change", "sick")
                       for _ln, e in p["effects"])
            if harm:
                flags |= 8
            if role.get("believers_only") is False:
                flags |= 16
            special = {"golden_child": 1, "tribal_chief": 2}.get(role.get("special") or "", 0)
            carrier = any(e["do"] in ("pregnant", "nursing") and e.get("role", "subject") == rid
                          for _ln, e in p["effects"])
            if carrier or role.get("special") == "nursing_parent":
                special = 3
                if any(e.get("any_birth_sex") for _ln, e in p["effects"] if e.get("role", "subject") == rid):
                    flags |= 32
            sex = {"male": 1, "female": 2}.get(role.get("sex", "any"), 0)
            slots_b += struct.pack("<IBBBBBBHI", s(rid), 1 if role.get("kind") == "stranger" else 0, sex,
                                   min(255, role.get("min_age", 0) or 0), min(255, role.get("max_age") or 0),
                                   special, flags, 0, 0)
            n_slot += 1
        for ln, e in p["effects"]:
            code, flags, a, b, st, bad = _effect_record(e, local, game)
            if bad:
                problems.append(Problem(it.file, ln, bad))
                continue
            deadly |= e["do"] in DEADLY
            effects_b += struct.pack("<BBBBiiI", code, local.get(e.get("role", "subject"), 0xFF)
                                     if e["do"] not in ("food", "tech", "pay_award", "damage", "celebrate") else 0xFF,
                                     flags, 0, a, b, s(st))
            n_fx += 1
        for aid, w in p["links"]:
            if aid not in ids:
                problems.append(Problem(it.file, it.line, f"{p['id']} answers {aid}, which is not a piece here"))
            links_b += struct.pack("<II", s(aid), min(1000, max(1, w)))
            n_link += 1
        fam = 0
        if p["family"]:
            fam = fam_ids.setdefault(p["family"], len(fam_ids) + 1)
        topic = 0
        for t in p["themes"]:
            if t not in topic_bits and len(topic_bits) < 32:
                topic_bits[t] = len(topic_bits)
            if t in topic_bits:
                topic |= 1 << topic_bits[t]
        filt = 0
        for f in p["filters"]:
            fid = _filter_id(f)
            if fid:
                filt |= 1 << (int(fid[1:]) - 1)
        for e in [e for _ln, e in p["effects"]]:
            for fid in content.EFFECT_FILTERS.get(e["do"], ()):
                filt |= 1 << (int(fid[1:]) - 1)
        notes = 0
        for k, (label, fs) in enumerate(content.NOTE_LABELS.items()):
            if any(filt >> (int(f[1:]) - 1) & 1 for f in fs):
                notes |= 1 << k
        weight = p["weight"] * (multiplier or {}).get(p["id"], 1)
        tags = sum(1 << tag_bits[t] for t in p["tags"] if t in tag_bits)
        never = sum(1 << tag_bits[t] for t in p["never"] if t in tag_bits)
        mask = sum(1 << (g - 1) for g in p["games"])
        recs += struct.pack("<IBBBBIIIIIIIIIHHIHHIHH", s(p["id"]), p["kind"], p["mood"],
                            (1 if deadly else 0) | (2 if believers else 0), mask, topic, fam, filt, notes, never, tags,
                            s(p["text"]), s(p["label"] if p["kind"] in (1, 2) else ""), first_slot, n_slot - first_slot,
                            min(1000, weight), first_fx, n_fx - first_fx, p["age_band"], first_link,
                            n_link - first_link, 0)
    header = 64
    pieces_at = header
    strings_at = pieces_at + len(recs)
    effects_at = strings_at + len(strings)
    effects_at += (-effects_at) % 4
    slots_at = effects_at + len(effects_b)
    links_at = slots_at + len(slots_b)
    size = links_at + len(links_b)
    body = bytearray(size)
    body[pieces_at:strings_at] = recs
    body[strings_at:strings_at + len(strings)] = strings
    body[effects_at:slots_at] = effects_b
    body[slots_at:links_at] = slots_b
    body[links_at:size] = links_b
    mask_all = 1 << (game - 1)
    struct.pack_into("<4sHHIIBBHIIIIIIIIIII", body, 0, b"VPCB", 1, 64, size, 0, mask_all, 0, 0, len(pieces),
                     pieces_at, strings_at, len(strings), effects_at, n_fx, slots_at, n_slot, links_at, n_link, 0)
    crc = zlib.crc32(bytes(body)) & 0xFFFFFFFF
    struct.pack_into("<I", body, 12, crc)
    if size > 0x100000:
        problems.append(Problem(pieces[0].file, 0, "the pieces file is over its 1 MB limit"))
    return bytes(body), problems


def _effect_record(e: dict, local: dict[str, int], game: int) -> tuple[int, int, int, int, str, str]:
    """(code, flags, a, b, string, problem) for a piece's effect, as the .cieg encodes it (cie-v6-binary.md 8)."""
    do = e["do"]
    if do not in cie.EFFECT_CODES:
        return 0, 0, 0, 0, "", f"{do} is not an effect"
    if e.get("target") or any(str(e.get(k, "")).startswith("$") for k in ("role", "partner", "with", "copy_of")):
        # The piece record (procedural-pieces.md 2.5) has no group target or "the newcomer" yet.
        return 0, 0, 0, 0, "", f"{do}: a group or the newcomer is not in mixer pieces yet (write it in an event)"
    code = cie.EFFECT_CODES[do]
    flags = a = b = 0
    st = ""
    try:
        if do in ("food", "tech"):
            if "size" in e:
                lo, hi = cie.size_range(do, e["size"], game)
                a, b = (-hi, -lo) if e.get("loss") else (lo, hi)
            else:
                a = e["amount"]
                b = e.get("max", a)
            flags = (1 if e.get("scaled") else 0) | (2 if e.get("defer") else 0)
        elif do == "skill":
            if "set" in e:
                code, a = cie.EFFECT_CODES["skill_set"], e["set"]
            else:
                lo, hi = cie.SKILL_SIZES[e.get("size", "small")] if "size" in e else (e["min"], e["max"])
                a, b = (-hi, -lo) if e.get("loss") else (lo, hi)
            st = ",".join(e["skills"])
        elif do == "preference":
            word = e.get("like", e.get("dislike", e.get("preference")))
            flags = (4 if "dislike" in e or e.get("list") == "dislikes" else 0) | \
                (cie.PREF_RANDOM_FLAG if word == cie.PREF_RANDOM else 0) | (cie.PREF_REMOVE_FLAG if e.get("remove") else 0)
            st = "" if word == cie.PREF_RANDOM else word
        elif do == "health_change":
            a, b = e["min"], e["max"]
        elif do == "health":
            a = b = e.get("value", e.get("min"))
        elif do in ("kill", "birth_then_die"):
            st = e.get("cause", "custom" if do == "kill" else "unknown")
        elif do == "die_unrecovered":
            st = "unknown"
        elif do == "mood":
            a = 1 if e["mood"] == "good" else -1
        elif do == "action":
            st = e["action"]
        elif do == "damage":
            a, b = cie.DAMAGE_SIZES[e.get("size", "normal")]
            st = e["structures"] if isinstance(e["structures"], str) else ",".join(e["structures"])
        elif do == "appearance":
            a = cie.LOOK_KEEP if e.get("head") is None else cie.LOOK_RANDOM if e["head"] == "random" else e["head"]
            b = cie.LOOK_KEEP if e.get("body") is None else cie.LOOK_RANDOM if e["body"] == "random" else e["body"]
        elif do == "new_villager":
            a = cie.NEW_VILLAGER_AGES[e.get("age", "any")]
        elif do in ("pregnant", "nursing"):
            flags = cie.ANY_BIRTH_SEX_FLAG if e.get("any_birth_sex") else 0
            a = local[e["partner"]] if e.get("partner") else 0xFF
        elif do == "body_swap":
            a = local[e["with"]]
        elif do == "change_name":
            st = e.get("name", "")
        elif do == "clone":
            a = 2 if e.get("count") == 2 else 0
        elif do == "change_age":
            if "to" in e:
                flags = cie.CHANGE_AGE_TO[e["to"]]
            else:
                flags, (a, b) = cie.CHANGE_AGE_ADD, e["years"]
        elif do == "status":
            a = cie.STATUS_CODES[e["status"]]
        elif do == "trait":
            a = cie.TRAIT_CODES[e["trait"]]
    except (KeyError, TypeError) as exc:
        return 0, 0, 0, 0, "", f"{do}: {exc} is missing or unknown"
    return code, flags, a, b, st, ""


def _filter_id(f: str) -> str | None:
    f = f.strip()
    if re.fullmatch(r"[Ff]\d\d", f) and f.upper() in content.FILTERS:
        return f.upper()
    for fid, name in content.FILTERS.items():
        if name.lower() == f.lower():
            return fid
    return None


# ---- Compiling events ----------------------------------------------------------------------------------------------

@dataclass
class Compiled:
    id: str
    title: str
    games: list[int]
    weight: int
    series: str
    credit: str
    description: str
    graph: dict
    cieg: bytes
    themes: list[str]
    guardians_title: str = ""
    guardians_description: str = ""


def _shared_pools():
    return cie.SHARED_POOLS if cie.SHARED_POOLS.is_file() else None


def event_graph(it: Item, ident: str | None, section: str = "player") -> tuple[dict, dict, dict]:
    """The graph to validate (with its collection block), the content tags and the extras (speaking roles, traits)."""
    g = copy.deepcopy(it.graph)
    meta = it.meta
    if ident is not None:
        col = dict(g.get("collection") or {})
        col.update({"id": ident, "source": col.get("source", "player"), "lines": col.get("lines", [it.line,
                                                                                                    it.last_line]),
                    "section": col.get("section", section),
                    "credit": meta.get("credit", col.get("credit", "")) or "",
                    "draw_weight": meta.get("weight", col.get("draw_weight", 1)) or 1,
                    "series": meta.get("series") or col.get("series")})
        if col["series"] is not None and not cie.COLLECTION_ID_RE.match(str(col["series"])):
            col["series"] = re.sub(r"[^a-z0-9_]+", "_", str(col["series"]).lower()).strip("_")[:64] or None
        keys = ("id", "source", "lines", "section", "credit", "draw_weight", "series")
        g["collection"] = {k: col[k] for k in keys}
        order = ("format", "version", "title", "games", "collection")
        g = {k: g[k] for k in order if k in g} | {k: v for k, v in g.items() if k not in order}
    return g, meta, {}


def compile_item(it: Item, ident: str | None = None, keep_collection: bool = False) -> tuple[Compiled | None,
                                                                                               list[str]]:
    """One event's .cieg through the collection's own steps (validate with Scrolling Popups, the content controls
    written in, compile).  `ident` None with keep_collection: the file's own collection block, unchanged."""
    g, meta, _ = event_graph(it, None if keep_collection else (ident or "pl_check"))
    # A story trait (STORY MUTE) is kept for the villager whatever the path, as the collection writes it: on the
    # start (content.inject's extras), never as a page's own effect.
    traits = list(meta.get("traits", []))
    for n in g.get("nodes", {}).values():
        kept = []
        for e in n.get("effects", []) or []:
            if isinstance(e, dict) and e.get("do") == "trait":
                t = {"role": e.get("role") or cie.default_role_of(g.get("roles", {})), "trait": e.get("trait", "mute")}
                if t not in traits:
                    traits.append(t)
            else:
                kept.append(e)
        if "effects" in n:
            n["effects"] = kept
    meta = dict(meta, traits=traits)
    norm, problems = cie.validate(g, scrolling=True, shared_pools=_shared_pools())
    if problems:
        return None, problems
    tags: dict[str, list[str]] = content.tag_graph(norm) if meta.get("auto_filters", True) else {}
    bad: list[str] = []
    for nid, fs in meta.get("node_filters", {}).items():
        if nid not in norm["nodes"]:
            bad.append(f"Filters names page {nid}, which the event does not have")
            continue
        for f in fs:
            fid = _filter_id(f)
            if fid is None:
                bad.append(f"{f!r} is not a content filter (F01..F28 or its name)")
            else:
                tags.setdefault(nid, [])
                if fid not in tags[nid]:
                    tags[nid].append(fid)
    for f in meta.get("filters", []):
        fid = _filter_id(f)
        if fid is None:
            bad.append(f"{f!r} is not a content filter (F01..F28 or its name)")
        elif fid not in tags.setdefault(norm["start"], []):
            tags[norm["start"]].append(fid)
    tags = {n: sorted(t) for n, t in tags.items() if t}
    if bad:
        return None, bad
    speaks = [r for r in meta.get("speaks", []) if r in norm["roles"]]
    if meta.get("auto_speakers", True):
        speaks += [r for r in content.speaking_roles(norm) if r not in speaks]
    extras = {"speaks": speaks, "traits": [t for t in meta.get("traits", []) if t.get("role") in norm["roles"]]}
    final = content.inject(norm, tags, extras)[0]
    try:
        cieg = cie.compile_graph(final)
    except (KeyError, ValueError, UnicodeEncodeError, struct.error) as exc:
        return None, [f"the event could not be compiled: {exc}"]
    col = norm.get("collection") or {}
    title = " ".join(norm["title"].split())
    return Compiled(col.get("id") or ident or "", title, list(norm["games"]), int(col.get("draw_weight", 1) or 1),
                    str(col.get("series") or ""), " ".join(str(col.get("credit", "")).split()),
                    " ".join(str(meta.get("description", "")).split()), final, cieg,
                    list(meta.get("themes", []))), []


def check_items(items: list[Item]) -> list[Problem]:
    """Every problem of the items, the compile's included, and the warnings (Check File).  A problem leaves its item
    out at patch time; a warning ("Warning (not an error): ...") does not."""
    out: list[Problem] = []
    for it in items:
        out += it.problems
        if it.kind == "event" and not it.problems:
            _c, probs = compile_item(it)
            out += [Problem(it.file, it.line, f"{it.title or 'the event'}: {p}") for p in probs]
        out += it.warnings
    return out


def rule_problem(it: Item, rules: dict[str, bool]) -> str | None:
    """The first ticked rule the event or piece breaks."""
    effects = [e for n in (it.graph or {}).get("nodes", {}).values() for e in n.get("effects", []) or []] \
        if it.kind == "event" else [e for _ln, e in it.piece["effects"]]
    for key, (words, kinds) in RULES.items():
        if not rules.get(key):
            continue
        for e in effects:
            if e.get("do") in kinds:
                return f"breaks your rule \"{words}\" ({e['do']})"
            if key == "no_losses" and e.get("do") in ("food", "tech") and (
                    e.get("loss") or (isinstance(e.get("amount"), int) and e["amount"] < 0)):
                return f"breaks your rule \"{words}\""
    return None


def themes_ok(themes: Iterable[str], settings: Settings) -> tuple[bool, int]:
    """(kept, weight multiplier) for an item's themes under the favoured themes and "Only my themes"."""
    fav = {t.lower() for t in settings.favour}
    hit = theme_hit(themes, fav)
    if settings.only_my_themes and fav and not hit:
        return False, 1
    return True, THEME_FAVOUR if hit else 1


def group_name(stem: str, taken: set[str]) -> tuple[str, str]:
    """A player file's group: "pl_" and at most 6 more characters, so "manifest-<group>.txt" stays within VV1's
    22-character file names (the collection's own deep-folder rule).  A short name is used as it is; a longer one is
    its first two characters and a hash of the whole name (the same file always gets the same group).  Two files that
    still meet get the next hash, and the note says so."""
    base = re.sub(r"[^a-z0-9_]+", "_", stem.lower()).strip("_") or "events"
    room = GROUP_NAME_MAX - len(GROUP_PREFIX)
    name = GROUP_PREFIX + base if len(base) <= room else \
        GROUP_PREFIX + base[:room - 4] + f"{zlib.crc32(stem.lower().encode('utf-8')) & 0xFFFF:04x}"
    note = ""
    k = 0
    while name in taken:
        k += 1
        h = zlib.crc32(f"{stem.lower()}#{k}".encode("utf-8")) & 0xFFFF
        clash = name
        name = GROUP_PREFIX + base[:room - 4] + f"{h:04x}"
        note = f"{stem}: its short name {clash} was already taken by another file, so it is {name}"
    taken.add(name)
    return name, note


def manifest_line(game: int, c: Compiled) -> str:
    title = " ".join(cie.event_title(c.graph, game).split())
    extra = ["", ""]
    if game == 5:
        alt = " ".join(cie.event_title(c.graph, game, (GUARDIANS_PATCH,)).split())
        extra = [alt if alt != title else "", ""]
    clean = lambda s: " ".join(str(s).replace("\t", " ").split())   # noqa: E731
    return "\t".join([c.id, clean(title), ",".join(map(str, c.games)), str(c.weight), clean(c.series),
                      clean(c.credit), clean(c.description)[:150]] + extra)


@dataclass
class InstallReport:
    installed: list[str] = field(default_factory=list)      # "file: title"
    pieces: int = 0
    skipped: list[str] = field(default_factory=list)        # "file, line n: why"
    files: list[Path] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)          # e.g. two files' short names met


def compile_folder(game: int, folder: Path, settings: Settings) -> tuple[dict[str, bytes], InstallReport]:
    """Every player file of the game's folder compiled: {file name in the collection folder: bytes} and the report."""
    report = InstallReport()
    out: dict[str, bytes] = {}
    if not folder.is_dir():
        return out, report
    taken: set[str] = set()
    used_ids: set[str] = set()
    cap = VV1_ID_MAX if game == 1 else ID_MAX
    for path in sorted(folder.glob("*.txt"), key=lambda p: p.name.lower()):
        if path.name in (RULES_NAME, PROMPT_NAME) + OWNER_FILES:
            continue
        items, file_problems = parse_file(path)
        report.skipped += [str(p) for p in file_problems]
        if not items:
            continue
        group, note = group_name(path.stem, taken)
        if note:
            report.notes.append(note)
        rows = ["# Player Events: " + path.name.replace("\t", " "),
                "# id\ttitle\tgames\tdraw weight\tseries\tcredit\tdescription\tGuardians title\tGuardians description"]
        pieces: list[Item] = []
        mult: dict[str, int] = {}
        k = 0
        for it in items:
            label = f"{path.name}, line {it.line}: {it.title or it.kind}"
            report.notes += [str(w) for w in it.warnings]
            if it.problems:
                report.skipped += [str(p) for p in it.problems]
                continue
            broken = rule_problem(it, settings.rules)
            if broken:
                report.skipped.append(f"{label}: {broken}")
                continue
            themes = it.meta.get("themes", []) if it.kind == "event" else it.piece["themes"]
            kept, m = themes_ok(themes, settings)
            if not kept:
                report.skipped.append(f"{label}: not one of your themes (Only my themes)")
                continue
            if it.kind == "piece":
                if game in it.piece["games"]:
                    pieces.append(it)
                    mult[it.piece["id"]] = m
                continue
            if game not in (it.graph or {}).get("games", [1, 2, 3, 4, 5]):
                continue
            k += 1
            ident = (it.meta.get("id") or f"{group}_{k:03d}").lower()
            if not ident.startswith(ID_PREFIX):
                ident = ID_PREFIX + ident
            ident = re.sub(r"[^a-z0-9_]", "_", ident)[:cap]
            if ident in used_ids:
                again = f"{group}_{k:03d}"
                report.notes.append(f"{label}: its Id {ident} is already used, so it is {again}")
                ident = again
            used_ids.add(ident)
            c, probs = compile_item(it, ident)
            if c is None:
                report.skipped += [f"{label}: {p}" for p in probs]
                continue
            if game not in c.games:
                continue
            c.weight = min(MAX_DRAW_WEIGHT, c.weight * m)
            out[f"{ident}.cieg"] = c.cieg
            rows.append(manifest_line(game, c))
            report.installed.append(f"{path.name}: {c.title}")
        if len(rows) > 2:
            out[f"manifest-{group}.txt"] = ("\n".join(rows) + "\n").encode("utf-8")
        if pieces:
            data, probs = compile_pieces(pieces, game, mult)
            report.skipped += [str(p) for p in probs]
            if data:
                out[f"pieces-{group}.pcb"] = data
                report.pieces += len(pieces)
    return out, report


def _owned(name: str) -> bool:
    low = name.lower()
    return (low.startswith(f"manifest-{GROUP_PREFIX}") and low.endswith(".txt")) or \
        (low.startswith(f"pieces-{GROUP_PREFIX}") and low.endswith(".pcb")) or \
        (low.startswith(ID_PREFIX) and low.endswith(".cieg"))


def install(game: int, game_folder_path: Path, source: Path | None = None, settings: Settings | None = None,
            root: Path | None = None) -> InstallReport:
    """Write the game's player events into "<game folder>\\Virtual Villagers Fun Patcher Files\\Island Event
    Collection" (this patcher's own earlier files there replaced; nothing else touched), and the AI prompt, the tone
    reference and a copy of the player's files into "...\\Player Events"."""
    source = source or game_folder(game, root)
    settings = settings or load_settings(game, root)
    files_dir = game_folder_path / PATCHER_FILES
    coll = files_dir / COLLECTION_FOLDER
    report = InstallReport()
    if coll.is_dir():
        for p in coll.iterdir():
            if p.is_file() and _owned(p.name):
                p.unlink()
    if not settings.enabled:
        install_references(game, files_dir, settings, root)
        return report
    out, report = compile_folder(game, source, settings)
    if out:
        coll.mkdir(parents=True, exist_ok=True)
        for name, data in out.items():
            tmp = coll / (name + ".tmp")
            tmp.write_bytes(data)
            os.replace(tmp, coll / name)
            report.files.append(coll / name)
    shown = install_references(game, files_dir, settings, root)
    if source.is_dir():
        for p in source.glob("*.txt"):
            shutil.copyfile(p, shown / p.name)
    report_text = "\n".join(["Player Events installed for " + GAME_NAMES[game] + ":"] +
                            [f"  {x}" for x in report.installed] + [f"  pieces: {report.pieces}"] +
                            (["Left out:"] + [f"  {x}" for x in report.skipped] if report.skipped else []) +
                            (["Notes:"] + [f"  {x}" for x in report.notes] if report.notes else []))
    (shown / "Player Events Report.txt").write_text(report_text + "\n", encoding="utf-8")
    return report


def install_references(game: int, files_dir: Path, settings: Settings, root: Path | None = None) -> Path:
    """The AI prompt, the player's own tone reference (when chosen) and the owner's files (the tone reference, the
    style guide, the themes and outcomes lists), byte for byte, in "<game folder>\\Virtual Villagers Fun Patcher
    Files\\Player Events"."""
    shown = files_dir / INSTALLED_FOLDER
    shown.mkdir(parents=True, exist_ok=True)
    (shown / PROMPT_NAME).write_text(ai_prompt(game, settings, read_rules(game, root)), encoding="utf-8")
    ref = reference_file(settings)
    if ref.is_file() and ref != default_reference() and ref.name not in OWNER_FILES:
        shutil.copyfile(ref, shown / ref.name)
    for name in OWNER_FILES:
        if shipped_file(name).is_file():
            shutil.copyfile(shipped_file(name), shown / name)
    return shown


def default_reference() -> Path:
    return shipped_file(TONE_NAME)


def reference_file(settings: Settings) -> Path:
    if settings.reference:
        p = Path(settings.reference)
        if p.is_file():
            return p
    return default_reference()


# ---- Preview -------------------------------------------------------------------------------------------------------

PREVIEW_NAMES = {"m": ("Kai", "Makoa", "Tane", "Ikaika", "Nalu", "Koa", "Keoni", "Ari"),
                 "f": ("Leilani", "Nani", "Malia", "Kalani", "Hina", "Moana", "Ilima", "Lani")}


def preview(it: Item, game: int | None = None, seed: int | None = None) -> str:
    """The event as the game would show it, with random villagers, random outcomes and a random answer at each
    question (the patcher's own walk, cie.simulate)."""
    if it.kind != "event":
        return "A mixer piece is composed with others at draw time; Check File checks it."
    c, probs = compile_item(it)
    if c is None:
        return "This event has problems:\n" + "\n".join(f"- {p}" for p in probs)
    rng = random.Random(seed)
    games = c.graph["games"]
    game = game if game in games else rng.choice(games)
    lg = c.graph
    bindings = {}
    used: set[str] = set()
    for rid, r in lg["roles"].items():
        if r["kind"] in ("villager", "stranger"):
            sex = r.get("sex", "any")
            sx = "m" if sex == "male" else "f" if sex == "female" else rng.choice("mf")
            name = rng.choice([n for n in PREVIEW_NAMES[sx] if n not in used] or PREVIEW_NAMES[sx])
            used.add(name)
            bindings[rid] = cie.Binding(name, sx)
    questions = [len(n["choices"]) for n in lg["nodes"].values() if n["type"] == "question"]
    low = min(questions) if questions else 2
    for _attempt in range(60):
        rolls = [rng.randrange(1 << 30) for _ in range(4000)]
        answers = [rng.randrange(low) for _ in range(64)]
        try:
            run = cie.simulate(lg, game, rolls, bindings, answers)
        except (ValueError, IndexError, KeyError):
            continue
        cast = ", ".join(f"{r} = {b.name}" for r, b in bindings.items())
        path = run["nodes"]
        chosen = [next((ch["label"] for ch in lg["nodes"][nid]["choices"] if ch["next"] == path[k + 1]), "?")
                  for k, nid in enumerate(path[:-1]) if lg["nodes"][nid]["type"] == "question"]
        head = f"{c.title} ({GAME_NAMES[game]})\nCast: {cast or 'nobody'}\n"
        if chosen:
            head += "Chosen: " + " / ".join(cie.title_case(x) for x in chosen) + "\n"
        return head + "\n\n".join(f"[Popup {k}]\n{t}" for k, t in enumerate(run["popups"], 1))
    return "No path through this event could be shown (its conditions hold only in the game)."


# ---- The AI prompt -------------------------------------------------------------------------------------------------

FORMAT_SECTION = """\
9. Output Format
Write the events in EXACTLY this plain-text format, which my patcher reads directly. Put each event one after another.
Lines in [square brackets] here are instructions, not text to copy.

Title: [Event Title In Title Case]
Applies to: [VV1, VV2, VV3, VV4, VV5, or the right subset]
Themes: [two or three short theme words, comma separated]
Role [name]: [only for a villager the text names who needs a rule, e.g. "Role fisher: adult, skill Farming 10+"]
Event:
[Introductory story and dilemma. One paragraph per line.]
Choice 1: [Specific Action In Title Case]
* Outcome A: [Complete, unique narrative]
  Effect: [one gameplay effect from the list below, or leave the line out]
* Outcome B: [Different, complete narrative]
Choice 2: [Specific Action In Title Case]
* Outcome A: [...]
* Outcome B: [...]
[Continue for as many choices as the story naturally requires: 2 to 7 choices; any number of outcomes per choice.
An outcome may have several Effect lines. "* Outcome A (weight 3):" makes that outcome three times as likely.]

Example (a short one, to show the layout only):

Title: The Coconut That Would Not Open
Applies to: VV1, VV2, VV3, VV4, VV5
Themes: comedy, food
Event:
(Name) has been trying to open the same coconut since sunrise. (He/She) has tried rocks, teeth and a firm talking-to.
Choice 1: Lend a Hand
* Outcome A: (Name) and two neighbours finally crack it open together, and the milk is the sweetest anyone has tasted.
  Effect: FOOD GAIN (small)
* Outcome B: The coconut flies out of everyone's hands and rolls into the sea. (Name) waves goodbye to it.
Choice 2: Leave (Him/Her) to It
* Outcome A: By sunset (name) has invented a clever splitting wedge, and the builders want one too.
  Effect: SKILL + Building a little
* Outcome B: (Name) falls asleep hugging the coconut, still unopened.

Names and pronouns (use these exactly, with the round brackets):
- (Name) / (name): the main villager's full name, capitalised or not. (He/She), (he/she), (His/Her), (his/her),
  (Him/Her), (him/her), (himself/herself), (man/woman), (boy/girl), (son/daughter) follow that villager's sex.
- A second villager: (name2) and (name2.he/she). Any other villager gets a short role name, used the same way:
  (fisher), (Fisher), (fisher.his/her). Every role name you use in the text or an effect becomes a villager of the
  village (14 or older unless a Role line says otherwise).
- (award): the food or tech amount actually given by a FOOD AWARD or TECH AWARD effect.
- {@chief} / {@Chief}: "the Chief" in The Secret City, "the village leader" in the other games.
- {this|that|the other}: one of these words, picked at random each time.
- {#babies:a baby|twins|triplets} and {#made:one|two|three or more}: in the story text only (never a title or a
  choice), the words for what the page's effects actually made: the first for one (or none), the second for two,
  the third for three or more; 1 to 3 choices of up to 160 letters, digits, spaces, , : - ' " ; / & % and names
  or pronouns like (name) or (made1) (no braces, no . ! ?).
- (made1): the name of the newest villager the event made (NEW VILLAGER, DUPLICATE, CLONE); (made2) the one made
  before it. Story text only, never a title or a choice.
- (his/hers): the possessive that stands alone ("the choice was (his/hers)"), also (friend.his/hers).
- Plain round brackets in the story are fine; they are shown as written.
- Tell the story in the third person. "I", "me", "my", "we", "you" and "your" belong only inside quoted speech or a
  villager's quoted thought.

Gameplay effects (one per Effect line, written exactly like this; <who> is a role name, or leave it out for the
main villager):
- FOOD GAIN (small|normal|large|huge), FOOD LOSS (size), TECH GAIN (size), TECH LOSS (size): food or tech points, in
  the game's own ranges. FOOD AWARD (size) / TECH AWARD (size) gives an amount the text can name with (award);
  PAY AWARD on a later outcome pays it then.
- SKILL + <skill> a little|some|a lot|hugely, SKILL - <skill> ..., MASTER <skill> (sets it to 100), SKILL SET <skill>
  <0-100>. Skills: Farming, Building, Research, Healing, Parenting, and Devotion (VV5 only). Add "FOR <who>" for
  another villager.
  SKILL + BEST a little|some|a lot|hugely raises the villager's own best skill.
- LIKE + <thing>, DISLIKE + <thing>, LIKE - <thing> (no longer likes it), DISLIKE - <thing> (gets over it),
  LIKE + random, DISLIKE + random. Things are the game's own likes words (for example swimming, dancing, fruit).
  Likes and dislikes are not jobs: never write that someone "hates (a job), so" gains a dislike; name the thing the
  villager actually comes to like or dislike (the water, the dark, bees). Pick the words from the style guide's
  Appendix A for each game the event applies to: a word missing from a game cannot be given there, and one that
  does nothing in a game is only cosmetic.
- INJURY <who> (a health loss; add (minor), (serious) or (grave)), ILLNESS <who> (falls sick), HEALTH <who> +10 TO +20,
  HEAL <who> (full health), CURE <who> (an illness cured), REPAIR (the damaged huts are repaired).
- Groups: put "EVERYONE:", "EVERY HEALER:" (also builder, farmer, researcher, parent: every villager good at that
  skill) or "3 RANDOM VILLAGERS:" before a health, illness, cure, skill, like, mood or look effect, for example
  "EVERYONE: MOOD GOOD", "EVERY HEALER: SKILL + Healing some" or "3 RANDOM VILLAGERS: ILLNESS".
- DEATH <who> (a grave is left), DISAPPEARS <who> (never seen again), LOST FOREVER <who> (dies, the body is never
  found), PREGNANCY LOSS <who>, BIRTH THEN DEATH <who>, EARLY BIRTH <who>. These are rare and serious.
- NEW VILLAGER (child|teen|adult|elder|any), NEW VILLAGER (adult woman) (or man, boy, girl), DUPLICATE OF <who> (a
  newcomer who looks just like them), CLONE OF <who> (an exact double; CLONE OF <who> (2) or TWO CLONES OF <who>
  makes two, never more). A family: NEW VILLAGER (adult man), NEW VILLAGER (adult woman), then
  NEW BABY OF THE NEWCOMERS. "newcomer" as <who> is the villager the event just made (and "previous newcomer" the one before).
- PREGNANT <who> [WITH <who>], NURSING <who> [WITH <who>] (a new baby now): the carrier is born female and 18 or
  older. Add (ANY BIRTH SEX) only when the story is magical (a spell, a blessing, an enchanted spring, a spirit, a
  potion), or for NURSING when a father is caring for a baby. Add (TWINS), (TRIPLETS) or (TWINS OR TRIPLETS) for
  more than one baby.
- NEW LOOK (head|body|both) <who>, OLD LOOK <who> (looks older), SEX CHANGE <who>, BODY SWAP <who> WITH <who>,
  LOSE NAME <who> (the name becomes "?"; it only comes from a bump on the head or something like it: a fall, a fever,
  magic or anything that takes the villager's memory, never a villager choosing or being given "?" as a name),
  CHANGE NAME <who> (a new name from the game's own list),
  CHANGE NAME <who> TO <name> (that name: letters, spaces, ' - . only, up to 31),
  CHANGE AGE <who> YOUNGER|OLDER <n> YEARS (add "(NEVER PAST ELDER)" to stop at old age),
  CHANGE AGE <who> TO child|teen|18|adult|50|elder, YOUNG LOOK <who> (looks younger).
- MOOD GOOD <who>, MOOD BAD <who>, CELEBRATE (everyone dances), ACTION <who> "<the game's own action words>",
  DAMAGE (small|normal|large|huge) (damages huts and buildings), STORY MUTE <who> (never speaks in events).
- VV5 only: BECOMES HEATHEN <who>.
Optional lines: "Requires: population 20+" (or "3 children+", "golden child present", "chief present"),
"Filters: F05" under an outcome (content filter tags: the patcher adds most by itself), "Description: one sentence for
the Pick Island Event list", "Coda:" (a closing paragraph shown after every outcome).
Role words: adult, child, teen, elder, 18 to 50, 30+, male, female, skill Healing 20+, best at Healing, spouse of
<who>, parent of <who>, child of <who>, sibling of <who>, within 10 years of <who>, optional, speaks, carrier,
golden child, tribal chief, stranger, named stranger, any faith (VV5: an Isolan may take it).
"""

PROMPT_TEMPLATE = """\
Write {count_words} Original Virtual Villagers Island Event{plural}
You are writing {count_words} original Island Event{plural} for my Virtual Villagers 1–5 Fun Patcher.
Your goal is to create memorable, imaginative, self-contained events that feel like they belong in the original Virtual Villagers games, while closely resembling the tone, narrative style, creativity, and structure of my own handwritten Island Events.
1. Study My Events First
Read the handwritten events and my event-writing rules in the reference file I provide: "{reference}". It is my DEFAULT source for event tone.
Pay particular attention to my events such as The Aspiring Adventurer, The Cave Explorers, The Remembrance Ceremony, The Climb, and The Troubling Signs.
Use these as your primary stylistic references. Do not imitate generic AI-generated events.
My writing combines ordinary village life, whimsical humor, interesting choices, surprising consequences, emotional realism, and the mysteries of Isola.
Also follow my style guide, "{style}" (I provide it too): it applies to every added island event, including yours (it does not apply to my own handwritten events, which are its source). Its appendices list the possible outcomes of every vanilla island event in all five games, and every like and dislike each game has and what it does: use them to keep your outcomes and likes true to the games.
My example events, "{example}" (I provide them too), are rewritten in my own hand: they are the format and style example, showing how an event is built (the opening, the choices, a first popup for a choice, the endings with their chances and effects) and how much story each popup and ending carries. Write yours with the same parts, laid out in the format of section 9 (my patcher reads that layout; my example's headings are for my notes). They are examples only: do not copy them.
THE KEY: my handwritten events ("{reference}") and my 20 example events ("{example}") are the key to my style guide and your primary references; the guide is drawn from them. Study both before you write anything, and when in doubt, write like them.
2. Create an Interesting Story
Write {count_words} completely original Island Event{plural}.{distinct}
Each should feel like a little adventure, dilemma, discovery, or incident in the lives of the villagers.
Use the themes in my themes list, "{themes}" (I provide it too): pick from it, or from the player's own themes below when there are any. Possible themes include:

* Everyday village life, relationships, friendships, celebrations, and leisure.
* Exploration, scientific discoveries, inventions, experiments, and accidents.
* Mysterious visitors, unusual objects, strange creatures, legends, and folklore.
* Love, family, childhood, aging, illness, recovery, grief, and loss.
* Unexpected misfortune, difficult decisions, miracles, and extraordinary experiences.
* Comedy, absurd situations, misunderstandings, and delightful surprises.

Not every event needs to be serious, supernatural, or dangerous. Ordinary, happy days should be much more common than tragedies.
Each event should have a distinctive premise rather than a generic situation.
3. Follow the Virtual Villagers Event Format
Write each event with:

1. A unique, creative title in Title Case.
2. An introductory narrative establishing what happened and presenting the player's dilemma.
3. Two to four meaningful choices, depending on what naturally fits the situation, each written in Title Case.
4. Two individually written, randomized outcomes per choice, unless the reference event format calls for a different number.
5. Specific gameplay consequences, where appropriate.

The choices must be unique to the situation, not generic options that could be applied to any event.
Each outcome must tell a complete little story about what happens after the player's decision.
An outcome may be positive, negative, neutral, funny, surprising, mysterious, or bittersweet.
Do not make every outcome predictable.
4. Match My Writing Style

* Use natural, charming, expressive prose appropriate for Virtual Villagers.
* Keep the storytelling concise enough for an in-game popup, but detailed enough to be interesting.
* Use villagers' names and pronouns naturally, following my existing placeholder conventions (listed in section 9).
* Include dialogue when it adds personality.
* Let characters have believable reactions, emotions, flaws, and relationships.
* Allow genuine surprises, irony, humor, and unexpected twists.
* Avoid repetitive sentence structures and artificial moral lessons.
* Do not end every outcome with the villagers learning a lesson or becoming wiser.
* Narrate in the third person, always. First and second person ("I", "me", "my", "we", "you", "your") only inside quoted speech or a villager's quoted thought.
* Likes and dislikes are not jobs: never "hates (a job), so a dislike". Name the thing the villager actually comes to like or dislike.
* No contradictions: every line must agree with the rest of the event (no "won't explain" followed by the explanation; nothing that "never" happens then happens).

Most importantly, write actual events, not vague descriptions of events.
For example, don't say, "The villagers investigate and discover something interesting." Describe exactly what they discover and what happens afterward.
5. Respect My Content Rules
The tone is PG-13, respectful, and emotionally realistic.
Unfortunate things happen, but people can survive them.
Death, serious illness, injury, disappearance, grief, and other tragedies are permitted when appropriate, including events involving children, but should be uncommon and never gratuitously graphic.
Villagers are generally peaceful, imperfect people. They may make mistakes, disagree, or act foolishly, but they do not deliberately murder or abuse others.
Treat people of all ages, abilities, appearances, and backgrounds with dignity.
Do not sugarcoat difficult experiences, but do not sensationalize suffering.
Avoid explicit sexual content and exploitative situations. Never write romance between a minor and an adult.
6. Respect Isola's World and Lore
Isola is a tribal society with its own traditions, science, history, and mysteries.

* Use language appropriate to the setting.
* Basic science and scholarly terminology are allowed.
* Describe unfamiliar advanced technology through its appearance or function.
* Magic and unexplained phenomena can occur.
* The existence of supernatural beings or divine intervention should remain open to interpretation.
* Creatures resembling mermaids, sirens, spirits, monsters, and other legendary beings may appear, but do not explicitly identify or confirm them.
* Different villagers may hold different beliefs, all of which deserve respect.
* Outsiders and the origins of mysterious objects may remain unknown.
* Follow the appropriate game-specific lore and terminology.
* In VV5, use my respectful Guardians of Isola terminology, including Isolans rather than Heathens, and "the tribe", "a tribe member" or "the newcomers" (whichever fits the sentence) rather than "believers". In VV5 a Heathen (Isolan) is only ever in an event about meeting them or coming to live with the tribe; give such a role "any faith".

7. Make the Outcomes Matter
Depending on the story, outcomes may include:

* Food or technology points gained or lost.
* Skill improvements or losses.
* Changes in health or illness.
* Injuries or recovery.
* New villagers arriving.
* Death or disappearance.
* Changes in appearance or other supported attributes.
* No mechanical effect, if the narrative itself is sufficient.

Use the kinds of outcome in my outcomes list, "{outcomes}" (I provide it too), balancing them: over many events every kind should come up about equally, not only food and tech. A kind that list marks as still being added cannot be used yet.
Use gameplay effects only when the story supports them, and only the effects listed in section 9.
Don't artificially balance every choice with one good outcome and one bad outcome.
Some choices may have two good outcomes, two unfortunate outcomes, or two entirely different neutral outcomes.
Death should be very rare, serious harm uncommon, and minor setbacks occasional, unless the particular event warrants otherwise.
The patcher's casting rules: a pregnancy or a new baby (PREGNANT, NURSING) always goes to a villager born female and 18 or older, unless the story is magical or (for NURSING) a father caring for a baby, and then the effect says (ANY BIRTH SEX). Events that can kill a villager or make one disappear only happen in villages of 61 or more.
8. Quality Requirements
Before presenting the events, check that:

* The premise is original and interesting.
* Every choice makes sense for that specific situation.
* The randomized outcomes are meaningfully different.
* Each outcome contains concrete narrative developments.
* The story is neither excessively sanitized nor needlessly tragic.
* The event resembles my handwritten writing style.
* It would be enjoyable to encounter during an actual Virtual Villagers playthrough.
* The title and every choice are in Title Case.

Do not use generic filler such as "the villagers learn something valuable," "everyone agrees to move forward," or "the matter is resolved peacefully" without describing what actually happens.
{rules}{format}
Final Instruction
Write {count_words} carefully crafted Island Event{plural}{collection_note}.
Prioritize creativity, personality, originality, believable consequences, and the charm of the original Virtual Villagers games.
Take inspiration from my handwritten events, not from formulaic AI writing.
Make each event feel like something that could genuinely happen to the people of Isola—whether ordinary, extraordinary, joyful, mysterious, or tragic.
Output only the finished Island Event{plural}, in the format of section 9, as plain text.
"""

_NUMBER_WORDS = {1: "ONE", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine",
                 10: "Ten"}


def ai_prompt(game: int | None = None, settings: Settings | None = None, rules_text: str = "") -> str:
    """The prompt a player pastes into any AI: the owner's own prompt, with the player's number of events, rules and
    themes, and this format."""
    settings = settings or Settings()
    n = max(1, settings.count)
    count_words = _NUMBER_WORDS.get(n, str(n))
    body = rules_body(rules_text)
    rules = ""
    ticked = [RULES[k][0] for k, v in settings.rules.items() if v and k in RULES]
    if body or ticked or settings.favour:
        lines = ["THE PLAYER'S OWN RULES AND THEMES (you must follow every one of these; where they disagree with "
                 "anything above, these win, except the content rules of section 5)"]
        lines += [f"- {t}" for t in ticked]
        if settings.favour:
            lines.append("- Favour these themes: " + ", ".join(settings.favour))
        if body:
            lines.append(body)
        lines.append("END OF THE PLAYER'S RULES AND THEMES")
        rules = "\n".join(lines) + "\n"
    if game is not None:
        rules += (f"These events are for {GAME_NAMES[game]} (VV{game}): write \"Applies to: VV{game}\" unless an "
                  "event truly fits other games too.\n")
    return PROMPT_TEMPLATE.format(
        count_words=count_words, plural="" if n == 1 else "s",
        distinct="" if n == 1 else " Each event must be distinct from the others: a different premise, different "
                                   "villagers and different kinds of choices.",
        reference=TONE_NAME if not settings.reference else Path(settings.reference).name, style=STYLE_NAME,
        themes=THEMES_NAME, outcomes=OUTCOMES_NAME, example=EXAMPLE_NAME,
        rules=rules, format=FORMAT_SECTION,
        collection_note=", not a collection" if n == 1 else "")


def write_shipped_prompt(path: Path | None = None) -> Path:
    path = path or (PLAYER_FOLDER / PROMPT_NAME)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(ai_prompt(), encoding="utf-8", newline="\r\n")
    return path


# ---- Writing an editor event as a player file ----------------------------------------------------------------------

def event_file_text(g: dict, description: str = "", themes: Iterable[str] = ()) -> str:
    """A Custom Island Event (the library's graph) as a FULL player event."""
    graph = {k: v for k, v in g.items() if k != "collection"}
    meta: dict[str, Any] = {}
    if description:
        meta["description"] = description
    if themes:
        meta["themes"] = list(themes)
    return ("# Player Events file written by the Custom Island Event Library.\n"
            "# docs/player-events-format.md explains every line.\n\n" + full_text(graph, meta))


def pieces_file_text(g: dict, family: str | None = None) -> str:
    """A Custom Island Event as mixer pieces: its opening question as a setup, each answer as an approach and each of
    the pages an answer can reach as an outcome (with its effects).  Only the first question is used."""
    norm, problems = cie.validate(g, scrolling=True, shared_pools=_shared_pools())
    if problems:
        norm, _p = cie.normalize(g, _shared_pools())
    nodes = norm.get("nodes", {})
    stem = re.sub(r"[^a-z0-9_]+", "_", norm.get("title", "event").lower()).strip("_")[:24] or "event"
    family = family or stem
    q_id = next((n for n in [norm.get("start")] + list(nodes) if n in nodes and nodes[n]["type"] == "question"), None)
    if q_id is None:
        raise ValueError("the event has no question to make approaches from")
    q = nodes[q_id]
    roles = norm.get("roles", {})
    out = ["# Mixer pieces written by the Custom Island Event Library from \"" + norm.get("title", "") + "\".",
           "# docs/player-events-format.md 6 explains every line.", ""]
    games = games_words(norm.get("games", [1, 2, 3, 4, 5]))

    def role_lines() -> list[str]:
        lines = []
        for rid, r in roles.items():
            if r.get("kind") != "villager":
                continue
            words = []
            if r.get("sex") in ("male", "female"):
                words.append(r["sex"])
            if r.get("max_age"):
                words.append(f"{r.get('min_age', 0)} to {r['max_age']}")
            elif r.get("min_age") is not None:
                words.append(f"{r['min_age']}+")
            if r.get("optional"):
                words.append("optional")
            lines.append(f"Role {rid}: {', '.join(words) or 'villager'}")
        return lines

    def effect_lines(n: dict) -> list[str]:
        return [f"Effect: {_plain_of(e)}" for e in n.get("effects", []) if _plain_of(e)]

    text = q["text"]
    out += [f"Piece: {stem}_setup", "Kind: Setup", "Mood: social", f"Family: {family}", f"Applies to: {games}",
            f"Title: {norm.get('title', '')}"] + role_lines() + _text_piece_lines(text) + [""]
    for k, c in enumerate(q["choices"], 1):
        aid = f"{stem}_a{k}"
        first = nodes.get(c["next"], {})
        out += [f"Piece: {aid}", "Kind: Approach", f"Family: {family}", f"Applies to: {games}",
                f"Label: {to_title_case(cie.title_case(c['label']))}"] + role_lines() + \
            _text_piece_lines(first.get("text") or c["label"]) + [""]
        ends: list[tuple[str, int]] = []
        stack = [(c["next"], 1)]
        seen: set[str] = set()
        while stack:
            nid, w = stack.pop(0)
            if nid in seen or nid not in nodes:
                continue
            seen.add(nid)
            n = nodes[nid]
            if n["type"] == "branch" or (n["children"] and len(n["children"]) > 1):
                stack += [(ch["next"], ch["weight"]) for ch in n["children"]]
            elif n["type"] == "popup" and nid != c["next"]:
                ends.append((nid, w))
            elif n["children"]:
                stack += [(ch["next"], ch["weight"]) for ch in n["children"]]
        if not ends and first:
            ends = [(c["next"], 1)]
        for j, (nid, w) in enumerate(ends, 1):
            n = nodes[nid]
            out += [f"Piece: {aid}_o{j}", "Kind: Outcome", f"Applies to: {games}",
                    f"Answers: {aid} ({min(1000, max(1, w))})"] + role_lines() + _text_piece_lines(n["text"]) + \
                effect_lines(n) + [""]
    return "\n".join(out) + "\n"


def _text_piece_lines(text: str) -> list[str]:
    first, *rest = (text or "").split("\n")
    return [f"Text: {first}"] + [f"| {line}" for line in rest]


def _plain_of(e: dict) -> str:
    """An effect in the plain words (best effort; "" when it has none)."""
    who = e.get("role")
    tail = f" {who}" if who and who != "subject" else ""
    do = e["do"]
    if do in ("food", "tech"):
        if "per_game" in e:
            lo, hi = next(iter(e["per_game"].values()))
            return f"{do.upper()} {'LOSS' if lo < 0 else 'GAIN'} {abs(lo)} TO {abs(hi)}"
        return f"{do.upper()} {'LOSS' if e['amount'] < 0 else 'GAIN'} {abs(e['amount'])}"
    if do == "skill":
        if "set" in e:
            return f"SKILL SET {e['skills'][0]} {e['set']}" + (f" FOR {who}" if tail else "")
        size = next((k for k, v in cie.SKILL_SIZES.items() if v == (abs(e['min']), abs(e['max']))), None)
        words = {"small": "a little", "normal": "some", "large": "a lot", "huge": "hugely"}.get(size or "", "some")
        return f"SKILL {'-' if e['min'] < 0 else '+'} {e['skills'][0]} {words}" + (f" FOR {who}" if tail else "")
    if do == "preference":
        return f"{'DISLIKE' if e['list'] == 'dislikes' else 'LIKE'} {'-' if e.get('remove') else '+'} " \
               f"{e['preference']}" + (f" FOR {who}" if tail else "")
    simple = {"kill": "DEATH", "vanish": "DISAPPEARS", "die_unrecovered": "LOST FOREVER", "sick": "ILLNESS",
              "baby_lost": "PREGNANCY LOSS", "birth_then_die": "BIRTH THEN DEATH", "deliver_early": "EARLY BIRTH",
              "old_look": "OLD LOOK", "sex_change": "SEX CHANGE", "lose_name": "LOSE NAME",
              "change_name": "CHANGE NAME", "clone": "CLONE OF"}
    if do == "clone" and e.get("count") == 2:
        return "TWO CLONES OF" + (tail or " villager")
    if do in simple:
        return simple[do] + (tail or " villager")
    if do == "health_change":
        return f"HEALTH{tail or ' villager'} {e['min']:+d} TO {e['max']:+d}"
    if do == "mood":
        return f"MOOD {e['mood'].upper()}{tail}"
    if do == "change_name" and e.get("name"):
        return f"CHANGE NAME{tail or ' villager'} TO {e['name']}"
    if do == "celebrate":
        return "CELEBRATE"
    if do == "new_villager":
        return f"NEW VILLAGER ({e.get('age', 'any')})" if not e.get("copy_of") else f"DUPLICATE OF {e['copy_of']}"
    return ""
