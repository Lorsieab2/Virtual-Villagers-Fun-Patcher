"""The Playful Dolphins: the owner's island event for The Tree of Life (2026-11-13) -- its words and its rules.

The one source of the event's English: scripts/build_more_island_events.py writes it into the companion
(native/vvfp_more_island_events/dolphin_text.inc) and into the translation template
(data/translations/patcher_strings.json), and the Game Mechanics page reads the rules below.

THE OWNER'S TEXT, as pasted in chat (2026-11-13), unaltered but for the fixes the owner approved:
  * "hold their breath" -> "hold (his/her) breath"; "shares his observations" -> "shares (his/her) observations";
    "doubts that (he/she) it's a good idea" -> "doubts that it's a good idea"; quote marks around What magnificent
    creatures!; a sentence-start "(he/she)" -> "(He/she)"; "exits the beach" -> "leaves the beach"; "accidentally got
    hit" -> "accidentally gotten hit" (the owner, 2026-11-13); "aquaculture" kept (the owner); "a skilled fisherman"
    -> "a skilled (fisherman/fisherwoman)", by the swimmer's sex (the owner, 2026-11-13);
  * the notes in parentheses or after "--" ("(then A or B, 50% each)", "-- a SMALL food reward") are instructions,
    never shown;
  * (Name) / (name) is the swimmer's full name, (he/she), (his/her) the swimmer's; (award) the amount;
  * typography the game's font cannot draw is written in the letters it can (The Tree of Life's ldwBurweed27 has no
    curly quotes or ellipsis: src/vv_font_glyphs.py missing("vv4", "ldwBurweed27") lists U+2018/2019/201C/201D/2026):
    the curly quotes and apostrophes as " and ', the ellipsis as ....

Each piece is written in one form per sex of the swimmer when it uses a pronoun (else one form), with the name as %s
and an amount as %d; each form is its own translation row, so a translation never has to guess a pronoun.

TOKENS:  {n} the swimmer's name   {he} {He} {his} {His}  the swimmer's pronouns
         {fisherman}  "fisherman" or "fisherwoman", by the swimmer's sex (the owner, 2026-11-13)
"""
from __future__ import annotations

import re

STEM = "vvfp.more_island_events/dolphin_text"
CONTEXT = ("VVFP More Island Events.dll (the island event The Playful Dolphins, The Tree of Life: its popups, in the "
           "game's own island-event popup)")

TITLE = "The Playful Dolphins"
GAME = 4

# (key, template).  Order is the C table's order (dolphin_text.inc DP_*).
TEXTS: tuple[tuple[str, str], ...] = (
    ("TITLE", TITLE),
    ("INTRO", "{n} has been swimming underwater as a hobby. One day, {he} spots a pod of dolphins playing just "
              "offshore! They seem to be chasing something, but {n} is unsure whether {he} can hold {his} breath long "
              "enough to see what. What should {he} do?"),
    ("LABEL_SWIM", "Swim towards the dolphins"),
    ("LABEL_BACK", "Hang back"),
    ("SWIM", "{n} swims towards the dolphins, being careful not to disturb them."),
    ("HUNT_1", "{He} gleefully watches the clever dolphins herd shoals of fish through giant bubble rings, "
               "disorienting them enough to become easy prey. \"What magnificent creatures!\" {he} thinks."),
    ("HUNT_2", "Later, {he} shares {his} observations with the researchers and farmers, which revolutionize their "
               "catches that season. {n} becomes a skilled {fisherman} and is lauded as a pioneer of aquaculture. Your "
               "villagers gain %d food."),
    ("SLAP", "Ouch! {n} is blinded by the slap of a large fluke in {his} face. {He} must have gotten too close to one "
             "of them and accidentally gotten hit by their tail flipper. {n} holds {his} nose to prevent any more red "
             "coming out. Luckily, {n} is not too far from the surface, but if {he} had been any deeper... {he} "
             "shudders to think about what might happen. {He} surfaces, leaves the beach, and heads off to the doctors "
             "for some medical treatment."),
    ("BACK", "{n} doubts that it's a good idea to follow the dolphins. They clearly seem to be busy doing something "
             "important, and {he} is second-guessing whether they're playing anyway. {n} resolves to stick to the "
             "shallows and gather shellfish and seaweed on the nearby rocks. Your village gains %d food."),
)

PRONOUNS = {
    "m": {"he": "he", "He": "He", "his": "his", "His": "His", "fisherman": "fisherman"},
    "f": {"he": "she", "He": "She", "his": "her", "His": "Her", "fisherman": "fisherwoman"},
}
_PRONOUN = re.compile(r"\{(he|He|his|His|fisherman)\}")
_NAME = re.compile(r"\{(n)\}")

# The endings, in the C table's order (dolphin_core.inc DP_E_*), and the popups each shows: each a tuple of its
# paragraphs' keys ("Swim towards the dolphins" opens with SWIM and the ending's text in one popup).
ENDINGS = ("HUNT", "SLAP", "BACK")


def pages_of(ending: str) -> tuple[tuple[str, ...], ...]:
    """The popups an ending shows, each a tuple of its paragraphs' keys."""
    return {"HUNT": (("SWIM", "HUNT_1", "HUNT_2"),), "SLAP": (("SWIM", "SLAP"),), "BACK": (("BACK",),)}[ending]


def forms(key: str) -> tuple[str, ...]:
    """The forms a piece has: ("",) when it holds no pronoun, else ("m", "f") -- the swimmer's sex."""
    return ("m", "f") if _PRONOUN.search(dict(TEXTS)[key]) else ("",)


def english(key: str, form: str) -> str:
    """Piece `key` in form `form` ("m", "f" or ""), with %s for the name (and %d an amount)."""
    words = dict(PRONOUNS.get(form, PRONOUNS["m"]))
    words["n"] = "%s"
    return re.sub(r"\{(\w+)\}", lambda m: words[m.group(1)], dict(TEXTS)[key])


def names_in(key: str) -> tuple[str, ...]:
    """The names a piece's %s stand for, in order: n the swimmer."""
    return tuple(_NAME.findall(dict(TEXTS)[key]))


def stem(key: str, form: str) -> str:
    return f"{STEM}.{key}" + (f".{form}" if form else "")


def rows() -> list[tuple[str, str, str, tuple[str, ...]]]:
    """Every (stem, key, English, names) the companion asks the translations for."""
    out = []
    for key, _ in TEXTS:
        for form in forms(key):
            out.append((stem(key, form), key, english(key, form), names_in(key)))
    return out


def fill(key: str, form: str, swimmer: str = "", award: int = 0) -> str:
    """The English of a piece with the name (and %d) put in, as the companion fills it."""
    text = english(key, form if forms(key) != ("",) else "")
    return text.replace("%s", swimmer).replace("%d", str(award))


# ---- Who, the odds and the effects (the owner, 2026-11-13) -----------------------------------------------------------

ADULT_YEARS = 14                 # 280 age units (20 a year): "14 and up" (the owner)
HUNT_PERCENT = 50                # "Swim towards the dolphins": the hunt 50%, the tail slap 50%
SLAP_PERCENT = 50
SKILL_MAX = 100                  # the game's own cap: The Tree of Life's skill adder 0x46AD80 (fcom [0x48A7C0] 100.0)
SLAP_LOSS = (30, 50)             # the tail slap: health (out of 100) drops by this many points, inclusive
HEALTH_LEFT_AT_LEAST = 1         # ... never below 1: the slap never kills
AWARDS = {"HUNT": ("food", 2, 1), "BACK": ("food", 1, 2)}   # kind, times, parts: a LARGE (x2) and a SMALL (/2) award

EFFECTS = {
    "HUNT": "Farming becomes 100 (fully mastered, the game's maximum) and a large food award (twice a normal one)",
    "SLAP": "the swimmer loses 30 to 50 health, never below 1 (the slap never kills)",
    "BACK": "a small food award (half a normal one)",
}


def outcome_chances() -> dict[str, dict[str, float]]:
    """Each ending's chance (percent) out of every time the player picks that answer."""
    return {"SWIM": {"HUNT": float(HUNT_PERCENT), "SLAP": float(SLAP_PERCENT)}, "BACK": {"BACK": 100.0}}
