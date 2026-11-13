"""Diving for Treasure: the owner's island event for The Secret City (2026-11-13) -- its words and its rules.

The one source of the event's English: scripts/build_more_island_events.py writes it into the companion
(native/vvfp_more_island_events/dive_text.inc) and into the translation template
(data/translations/patcher_strings.json), and the Game Mechanics page reads the rules below.

THE OWNER'S TEXT, as pasted in chat (2026-11-13), unaltered but for what the owner approved and the brief asked for:
  * the grammar fixes (the same policy the owner approved for The Troubling Signs, "fix any obvious grammatical
    mistakes"): "(name1)" -> (name); "In (his/her) heart, he apologizes" -> "(he/she) apologizes"; "(him/herself)" ->
    (himself/herself); "they/them/their/themselves" meaning the diver -> the diver's pronouns; "It's large
    rectangular" -> "It's a large rectangular";
  * the notes in parentheses or after "--" ("(25% each)", "-- normal tech reward", ...) are instructions, never shown;
  * (Name) / (name) is the diver's full name, (he/she), (his/her), (him/her), (himself/herself), (father/mother) the
    diver's; (random name) is the "head Doctor" (the owner, 2026-11-13: flavour text only -- any random villager of 18
    or more who is not protected, never the diver); (award) the amount;
  * typography the game's font cannot draw is written in the letters it can (The Secret City's ldwBurweed27 has no
    curly quotes or ellipsis: src/vv_font_glyphs.py missing("vv3", "ldwBurweed27") lists U+2018/2019/201C/201D/2026):
    the curly quotes and apostrophes as " and ', the ellipsis as ...;
  * a pronoun opening a sentence is capitalised.

Each piece is written in one form per sex of the diver when it uses a pronoun (else one form), with each name as %s
and an amount as %d; each form is its own translation row, so a translation never has to guess a pronoun.

TOKENS:  {n} the diver's name   {d} the head Doctor's name
         {he} {He} {his} {His} {him} {himself} {father}  the diver's pronouns (and "father" / "mother")
"""
from __future__ import annotations

import re

STEM = "vvfp.more_island_events/dive_text"
CONTEXT = ("VVFP More Island Events.dll (the island event Diving for Treasure, The Secret City: its popups, in the "
           "game's own island-event popup)")

TITLE = "Diving for Treasure"
GAME = 3

# (key, template).  Order is the C table's order (dive_text.inc DV_*).
TEXTS: tuple[tuple[str, str], ...] = (
    ("TITLE", TITLE),
    ("INTRO", "{n} is a diver. {He} regularly swims around the sea using a complex setup of reeds and animal skins to "
              "carry air. During one of {his} dives, {he} sees something shimmering deep down in the bottom of the "
              "reef. Should {he} swim down and look?"),
    ("LABEL_DEEPER", "Swim deeper"),
    ("LABEL_NOT", "Better not"),
    ("DEEPER", "{n} swims deeper towards the shimmering object. {He} can feel the pressure of the ocean getting heavier "
               "and heavier all around {him}. Just a little bit closer, and..."),
    ("FIND_A", "It's an abandoned net wrapped around a seaweed-encrusted crate. When {n} surfaces, {he} cracks it open "
               "to find a bunch of golden doubloons! Your village gains %d tech points."),
    ("FIND_B", "It's a chewed-up buoy, which to {n}, is some heavy striped ball. Whatever it is, it certainly has no "
               "use now. {n} lets go of the mysterious heavy ball and swims up to the surface. Maybe next time {he} "
               "will find something worthwhile."),
    ("FIND_C", "It's a large rectangular shipping container, all rusted from the salt. To {n}, it's just some random "
               "container, but it must contain something to be so heavy. {He} carefully swims to the surface and "
               "hauls it ashore. Turns out, it's full of exotic ingredients, the likes of which {n} has never seen "
               "before! Your village gains %d food."),
    ("FIND_D", "POP! Before {n} can react, one of {his} makeshift air tanks pops like a balloon. {He} stares wide-eyed "
               "in horror as the air rises to the surface in a large bubble before exploding in a deafening blast. "
               "{n} forgets {his} training and starts clawing through the water like a drowning animal."),
    ("D1", "After some agonizingly long minutes, {n} heaves {himself} ashore, gasping for breath. {His} eyes, nose and "
           "mouth sting from the salty water, and {he} is dazed for a while. Eventually, {n} manages to recover enough "
           "to make {his} way to the healers'. {n} spends several days recovering from {his} near-death experience "
           "and is now afraid of the unforgiving ocean."),
    ("D2_1", "After some agonizingly long minutes, {n} struggles harder and harder to make it to the surface. {His} "
             "body becomes weaker and more painful with every stroke and {his} lungs are ready to burst. The sunlight "
             "starts becoming fainter as {n} begins sinking towards the briny blue depths..."),
    ("D2_2", "{n}'s last thoughts before inhaling water are of {his} family, and the foolish dreams {he} once had of "
             "taming the great, blue ocean..."),
    ("D2A", "Eventually, {n}'s body washes ashore, to the dismay and grief of the villagers. They bury {n} and "
            "mournfully lament the loss of a great sea explorer."),
    ("D2B", "Several days pass, and {n}'s body is never found. {n}'s friends, family and the entire village gather to "
            "remember {n} and mourn the loss of a great sea explorer."),
    ("D2C_1", "\"Thank goodness, {he}'s alive!\" {n} coughs hard, bringing up water. \"Wh-where am I?!\" {he} "
              "sputters. {n} opens {his} eyes to see the faces of many doctors, friends, as well as {his} family "
              "huddled over {him}. {d}, the head Doctor, says, \"We found you unconscious here on the shore. We "
              "performed lifesaving measures until you started moving again.\" {n} sits up to see worried loved ones "
              "crying in distress, and is moved with pity. {He} goes to hug them and thanks everyone for saving {his} "
              "life."),
    ("D2C_2", "Once {he} has sufficiently recovered from {his} near-death experience, {he} makes a silent, solemn vow "
              "to the majestic Ocean. In {his} heart, {he} apologizes for almost throwing {his} life away for the "
              "sake of some tempting treasure, and promises never to take Them for granted again. {n} devotes "
              "{himself} to the healing arts in gratitude towards those who saved {him} that day."),
    ("NOT", "{n} knows that diving can be dangerous, and the sea can be both generous and cruel. Gambling with the "
            "ocean's patience could spell death, and {n} has a family waiting back home. {n} hangs up {his} diving "
            "equipment to be a gentle {father} to {his} spouse and children."),
)

PRONOUNS = {
    "m": {"he": "he", "He": "He", "his": "his", "His": "His", "him": "him", "himself": "himself", "father": "father"},
    "f": {"he": "she", "He": "She", "his": "her", "His": "Her", "him": "her", "himself": "herself", "father": "mother"},
}
_PRONOUN = re.compile(r"\{(he|He|his|His|him|himself|father)\}")
_NAME = re.compile(r"\{(n|d)\}")

# The endings, in the C table's order (dive_core.inc DV_E_*), and the popups each shows: each a tuple of its
# paragraphs' keys ("Swim deeper" opens with DEEPER and the find in one popup; the air tank's ending follows in a popup
# of its own, and the sinking's outcome in another).
ENDINGS = ("A", "B", "C", "D1", "D2A", "D2B", "D2C", "NOT")


def pages_of(ending: str) -> tuple[tuple[str, ...], ...]:
    """The popups an ending shows, each a tuple of its paragraphs' keys."""
    if ending == "NOT":
        return (("NOT",),)
    if ending in ("A", "B", "C"):
        return (("DEEPER", "FIND_" + ending),)
    first = ("DEEPER", "FIND_D")
    if ending == "D1":
        return (first, ("D1",))
    sink = ("D2_1", "D2_2")
    last = {"D2A": ("D2A",), "D2B": ("D2B",), "D2C": ("D2C_1", "D2C_2")}[ending]
    return (first, sink, last)


def forms(key: str) -> tuple[str, ...]:
    """The forms a piece has: ("",) when it holds no pronoun, else ("m", "f") -- the diver's sex."""
    return ("m", "f") if _PRONOUN.search(dict(TEXTS)[key]) else ("",)


def english(key: str, form: str) -> str:
    """Piece `key` in form `form` ("m", "f" or ""), with %s for each name (and %d an amount)."""
    words = dict(PRONOUNS.get(form, PRONOUNS["m"]))
    words.update({"n": "%s", "d": "%s"})
    return re.sub(r"\{(\w+)\}", lambda m: words[m.group(1)], dict(TEXTS)[key])


def names_in(key: str) -> tuple[str, ...]:
    """The names a piece's %s stand for, in order: n the diver, d the head Doctor."""
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


def fill(key: str, form: str, diver: str = "", doctor: str = "", award: int = 0) -> str:
    """The English of a piece with the names (and %d) put in, as the companion fills it."""
    text = english(key, form if forms(key) != ("",) else "")
    values = {"n": diver, "d": doctor}
    for who in names_in(key):
        text = text.replace("%s", values[who], 1)
    return text.replace("%d", str(award))


# ---- Who, the odds and the effects (the owner, 2026-11-13) -----------------------------------------------------------

ADULT_YEARS = 18                 # 360 age units (20 a year): the diver and the head Doctor
FIND_PERCENT = 25                # "Swim deeper": A, B, C, D 25% each
SURVIVE_PERCENT = 75             # D: survives (dislikes swimming) 75%, else sinks
DIES_PERCENT = 17                # sinks: dies 17%
DISAPPEARS_PERCENT = 17          # sinks: disappears 17%
RESCUED_PERCENT = 66             # sinks: rescued 66%
SKILL_GAIN = (10, 20)            # the rescued's Healing, "Better not"'s Parenting: + this much, inclusive
SKILL_MAX = 100                  # the game's own cap: The Secret City's skill adder 0x455740 (cmp edx, 0x64)
SWIMMING = 37                    # the preference "swimming": entry 37 of the game's preference list (file 0x97488)
AWARDS = {"A": ("tech", "normal"), "C": ("food", "normal")}

EFFECTS = {
    "A": "a normal tech-points award",
    "B": "nothing happens",
    "C": "a normal food award",
    "D1": "the diver now dislikes swimming (the game's own dislike)",
    "D2A": "the diver dies (the game's own death: a body and a grave, \"Unknown causes\")",
    "D2B": "the diver disappears (gone for good, no body, no grave)",
    "D2C": "the diver is rescued and gains 10 to 20 Healing, at most the game's maximum",
    "NOT": "the diver gains 10 to 20 Parenting, at most the game's maximum",
}


def outcome_chances() -> dict[str, dict[str, float]]:
    """Each ending's chance (percent) out of every time the player picks that answer."""
    find = FIND_PERCENT / 100
    sink = find * (100 - SURVIVE_PERCENT) / 100
    return {"DEEPER": {"A": find * 100, "B": find * 100, "C": find * 100,
                       "D1": find * SURVIVE_PERCENT, "D2A": sink * DIES_PERCENT,
                       "D2B": sink * DISAPPEARS_PERCENT, "D2C": sink * RESCUED_PERCENT},
            "NOT": {"NOT": 100.0}}
