"""Village scores: Village Solidarity (the owner, 2026-11-17), built so another village score can reuse it.

THE RULES (the same as native/vvfp_village_solidarity/vvfp_village_solidarity.c, pinned by
tests/test_village_solidarity.py):

  * a score is 0..100 and starts at 50; it is kept OUTSIDE the save, in the save's own
    "Virtual Villagers Fun Patcher\\Save <S>\\Data\\Village Scores\\Village Scores - Save <S>.txt"
    (a header line, then "<name> <score>" lines);
  * an event page tagged "raise" moves it +STEP, "lower" -STEP, "neutral" not at all: every item by the
    same amount, always within 0..100;
  * it changes ONLY odds: an item favoured by a high score (cooperative and celebration events, cooperative
    endings) or by a low score (repair, peace and apology events, tense endings) has its own chance weight
    multiplied by factor() per mille -- 1000 + 2 x the strength in tenths x the score's distance from 50
    on the item's side, else 1000.  Nothing is ever lowered or forced;
  * the strength is the row's slider, 0.1x to 10x (1x the normal strength), written beside the companion as
    SOLIDARITY_CHOICE_FILE ("1", "0.5", "2.5"), the same text the 0.1x-10x sliders use.

ANOTHER SCORE ("same for any other village score like happiness", the owner): add a Score to SCORES (append
only: its index is its id in the companion's exports) and the companion's VS_SCORES row; the file, the moves,
the clamp, the factor, the tags' format and the slider are shared.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

MIN_SCORE = 0
MAX_SCORE = 100
START = 50
STEP = 5                                   # every raise and every lower: the same amount (the owner)
FILE_HEADER = "Virtual Villagers Fun Patcher - Village Scores 1"
DATA_KIND = "Village Scores"

TAGS = ("raise", "lower", "neutral")       # an event page's "solidarity" tag
TAG_CODES = {"raise": 1, "lower": 2, "neutral": 3}
EVENT_KINDS = ("cooperative", "repair")    # an event's own "solidarity" kind (the collection draw's odds)
FAVOUR_NONE, FAVOUR_HIGH, FAVOUR_LOW = 0, 1, 2

STRENGTH_MIN_TENTHS = 1                    # 0.1x
STRENGTH_MAX_TENTHS = 100                  # 10x
STRENGTH_DEFAULT = 1                       # the normal strength

SOLIDARITY_NAME = "Village Solidarity"
SOLIDARITY_ROW_SUFFIX = "_village_solidarity"
SOLIDARITY_DLL = "VVFP Village Solidarity.dll"
SOLIDARITY_CHOICE_FILE = "VVFP Village Solidarity.txt"


@dataclass(frozen=True)
class Score:
    name: str                              # the file's, the log's and the counter's word for it
    log_folder: str                        # its log's folder ("...Logs\\<folder>\\<folder> Log.txt")


SCORES = (Score(SOLIDARITY_NAME, "Village Solidarity"),)   # APPEND ONLY


def moved(score: int, tag: str | None) -> int:
    """`score` after a page tagged `tag` (raise / lower / neutral / None), kept within 0..100."""
    step = STEP if tag == "raise" else -STEP if tag == "lower" else 0
    return max(MIN_SCORE, min(MAX_SCORE, score + step))


def favour_of_tag(tag: str | None) -> int:
    """A branch leading to a page tagged `tag`: raise = a cooperative ending (favoured by a high score), lower = a
    tense ending (favoured by a low score)."""
    return FAVOUR_HIGH if tag == "raise" else FAVOUR_LOW if tag == "lower" else FAVOUR_NONE


def favour_of_kind(kind: str | None) -> int:
    """An event's kind: cooperative (and celebration) by a high score, repair (peace, apology) by a low one."""
    return FAVOUR_HIGH if kind == "cooperative" else FAVOUR_LOW if kind == "repair" else FAVOUR_NONE


def factor(score: int, favour: int, strength_tenths: int = 10) -> int:
    """The weight factor per mille (1000 = unchanged) of an item favoured by `favour` at `score`."""
    if not (MIN_SCORE <= score <= MAX_SCORE) or not (STRENGTH_MIN_TENTHS <= strength_tenths <= STRENGTH_MAX_TENTHS):
        return 1000
    if favour == FAVOUR_HIGH and score > START:
        return 1000 + 2 * strength_tenths * (score - START)
    if favour == FAVOUR_LOW and score < START:
        return 1000 + 2 * strength_tenths * (START - score)
    return 1000


def strength_tenths(value) -> int | None:
    """A slider number (0.1 to 10, at most one decimal place) as tenths, else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        tenths = value * 10
    elif isinstance(value, float):
        tenths = round(value * 10)
        if abs(tenths - value * 10) > 1e-9:
            return None
    elif isinstance(value, str) and re.fullmatch(r"\d{1,3}(\.\d)?", value.strip()):
        whole, _, frac = value.strip().partition(".")
        tenths = int(whole) * 10 + (int(frac) if frac else 0)
    else:
        return None
    return tenths if STRENGTH_MIN_TENTHS <= tenths <= STRENGTH_MAX_TENTHS else None


def strength_text(value) -> str:
    """The slider's number as the companion reads it: "1", "0.5", "2.5"."""
    tenths = strength_tenths(value)
    if tenths is None:
        raise ValueError(f"{SOLIDARITY_NAME}: the strength must be a number from 0.1 to 10 in steps of 0.1, "
                         f"not {value!r}")
    return str(tenths // 10) if tenths % 10 == 0 else f"{tenths // 10}.{tenths % 10}"


def strength_number(value) -> int | float:
    """The canonical number (int when whole)."""
    tenths = strength_tenths(value)
    if tenths is None:
        raise ValueError(f"not a strength: {value!r}")
    return tenths // 10 if tenths % 10 == 0 else tenths / 10


# ---- the scores file ------------------------------------------------------------------------------------------

def file_name(slot: int) -> str:
    return f"Village Scores - Save {slot}.txt"


def file_path(save_folder: Path, slot: int) -> Path:
    """The save's own place for the file (the layout native/shared/per_save.h routes a new file to)."""
    return Path(save_folder) / "Virtual Villagers Fun Patcher" / f"Save {slot}" / "Data" / DATA_KIND / file_name(slot)


def parse(text: str) -> dict[str, int] | None:
    """The scores in a file's text ({name: score}, every known score present, START when not written), or None
    when the file is unreadable (no header, a known name twice, a value not 0..100) -- as the companion reads it."""
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0] != FILE_HEADER:
        return None
    out = {s.name: START for s in SCORES}
    seen: set[str] = set()
    for line in lines[1:]:
        if not line:
            continue
        for s in SCORES:
            if line.startswith(s.name + " "):
                value = line[len(s.name) + 1:]
                if not re.fullmatch(r"\d{1,3}", value) or s.name in seen or not MIN_SCORE <= int(value) <= MAX_SCORE:
                    return None
                seen.add(s.name)
                out[s.name] = int(value)
                break
    return out


def render(values: dict[str, int]) -> str:
    """A file's text, as the companion writes it."""
    return FILE_HEADER + "\r\n" + "".join(f"{s.name} {values.get(s.name, START)}\r\n" for s in SCORES)


def read_scores(save_folder: Path, slot: int) -> dict[str, int] | None:
    """The village's scores, or None when the file is missing or unreadable (the companion then starts at 50)."""
    path = file_path(save_folder, slot)
    try:
        return parse(path.read_text(encoding="ascii"))
    except (OSError, UnicodeDecodeError):
        return None


def write_scores(save_folder: Path, slot: int, values: dict[str, int]) -> Path:
    path = file_path(save_folder, slot)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(render(values).encode("ascii"))
    return path


# ---- tagging by the owner's feeling words ---------------------------------------------------------------------

# The owner's lists (2026-11-17).  A page's text "clearly carries" a feeling when one of these words is in it.
RAISE_WORDS = (
    "happiness", "happy", "joy", "joyful", "unity", "united", "together", "togetherness", "trust", "trusted",
    "comfort", "comforted", "comforting", "gratitude", "grateful", "thankful", "pride", "proud", "hope", "hopeful",
    "courage", "brave", "respect", "respected", "relief", "relieved", "reconciled", "reconciliation", "forgave",
    "forgiven", "inspired", "inspiration", "celebrate", "celebrated", "celebration", "sang together", "feast",
    "welcomed",
)
LOWER_WORDS = (
    "tension", "tense", "distrust", "mistrust", "suspicion", "suspicious", "unfair", "unfairness", "resentment",
    "resent", "resented", "fear", "afraid", "frightened", "worry", "worried", "ashamed", "humiliated", "embarrassed",
    "divided", "division", "quarrel", "argued", "broken promise", "betrayed", "grudge", "unresolved",
)
NEUTRAL_WORDS = ("remembrance", "quietly reflect", "bittersweet", "in silence", "mourned", "solemn")


def _hits(text: str, words: tuple[str, ...]) -> int:
    low = text.lower()
    return sum(1 for w in words if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", low))


def tag_for_text(text: str) -> str | None:
    """The tag a page's own text clearly carries: raise or lower when only that side's words are in it, neutral
    when only the quiet words are, else None (mixed or none: left untagged)."""
    up, down, still = _hits(text, RAISE_WORDS), _hits(text, LOWER_WORDS), _hits(text, NEUTRAL_WORDS)
    if up and not down and not still:
        return "raise"
    if down and not up and not still:
        return "lower"
    if still and not up and not down:
        return "neutral"
    return None
